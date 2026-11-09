"""Local HTTP server (standard library only) exposing the CodePal API and UI.

Endpoints
  GET  /                         -> SPA
  GET  /<asset>                  -> style.css / app.js
  GET  /api/files?path=...       -> list a directory in the workspace
  POST /api/tool/read|write|edit|bash -> run a built-in tool directly
  POST /api/chat                 -> stream agent events (NDJSON)
  GET  /api/config               -> current config (api key masked)
  POST /api/config               -> save config
  GET  /api/mcp                  -> connected MCP servers + tools
  POST /api/mcp/connect          -> connect an MCP server
  POST /api/mcp/disconnect       -> disconnect an MCP server
"""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse, parse_qs

from . import tools as builtin_tools
from .agent import Agent
from .config import load_config, save_config, mask_config
from .llm import LLMClient, LLMError
from .mcp import MCPRegistry, MCPError


def _web_dir() -> Path:
    here = Path(__file__).resolve().parent
    candidate = here / "web"
    if candidate.exists():
        return candidate
    # Frozen one-file build: assets are extracted next to the executable.
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", ""))
        cand = meipass / "codepal" / "web"
        if cand.exists():
            return cand
    return candidate


class CodePalApp:
    def __init__(self) -> None:
        self.config = load_config()
        self.mcp = MCPRegistry()
        self.llm: LLMClient | None = None
        self.agent: Agent | None = None
        self._rebuild()
        for spec in self.config.get("mcp_servers", []):
            try:
                self.mcp.connect(spec)
            except Exception:
                pass
        self._rebuild()

    # -- lifecycle ----------------------------------------------------------
    def _build_llm(self) -> LLMClient | None:
        llm_cfg = self.config.get("llm", {})
        if not llm_cfg.get("api_key"):
            return None
        return LLMClient(
            base_url=llm_cfg.get("base_url", "https://api.deepseek.com/v1"),
            api_key=llm_cfg["api_key"],
            model=llm_cfg.get("model", "deepseek-chat"),
            temperature=float(llm_cfg.get("temperature", 0.3)),
            max_tokens=int(llm_cfg.get("max_tokens", 2048)),
        )

    def _rebuild(self) -> None:
        self.llm = self._build_llm()
        self.agent = Agent(self.llm, self.config["workspace"], self.mcp) if self.llm else None

    def apply_config(self, new_cfg: Dict[str, Any]) -> None:
        # Preserve a previously entered (masked) key if the UI didn't resend it.
        if new_cfg.get("llm", {}).get("api_key") in (None, "", "********"):
            new_cfg.setdefault("llm", {})["api_key"] = self.config.get("llm", {}).get("api_key", "")
        self.config = new_cfg
        save_config(self.config)
        self._rebuild()

    # -- helpers ------------------------------------------------------------
    def _list_dir(self, rel: str) -> Dict[str, Any]:
        ws = self.config["workspace"]
        target = os.path.abspath(os.path.join(ws, rel or ""))
        base = os.path.abspath(ws)
        if not (target == base or target.startswith(base + os.sep)):
            return {"ok": False, "error": "路径越界"}
        if not os.path.isdir(target):
            return {"ok": False, "error": "目录不存在"}
        entries = []
        for e in sorted(os.scandir(target), key=lambda x: (x.is_file(), x.name.lower())):
            try:
                size = e.stat().st_size if e.is_file() else 0
            except OSError:
                size = 0
            entries.append({"name": e.name, "is_dir": e.is_dir(), "size": size})
        return {"ok": True, "path": os.path.relpath(target, base), "entries": entries}


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    app: CodePalApp
    protocol_version = "HTTP/1.1"

    # silence default logging noise
    def log_message(self, *args: Any) -> None:  # noqa: D401
        pass

    # -- routing ------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/" or path == "":
            return self._serve_file(_web_dir() / "index.html", "text/html; charset=utf-8")
        if path in ("/style.css", "/app.js"):
            ctype = "text/css; charset=utf-8" if path.endswith(".css") else "application/javascript; charset=utf-8"
            return self._serve_file(_web_dir() / path.lstrip("/"), ctype)
        if path == "/api/files":
            q = parse_qs(parsed.query)
            rel = q.get("path", [""])[0]
            return self._json(self.app._list_dir(rel))
        if path == "/api/config":
            return self._json(mask_config(self.app.config))
        if path == "/api/mcp":
            return self._json({"servers": self.app.mcp.snapshot()})
        return self._error(404, "Not found")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_body()
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            return self._error(400, "Invalid JSON")

        if path == "/api/chat":
            return self._stream_chat(data)
        if path == "/api/config":
            self.app.apply_config(data)
            return self._json({"ok": True})
        if path == "/api/mcp/connect":
            return self._mcp_connect(data)
        if path == "/api/mcp/disconnect":
            self.app.mcp.disconnect(data.get("name", ""))
            return self._json({"ok": True})
        if path.startswith("/api/tool/"):
            return self._direct_tool(path.split("/")[-1], data)
        return self._error(404, "Not found")

    # -- handlers -----------------------------------------------------------
    def _stream_chat(self, data: Dict[str, Any]) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        def emit(ev: Dict[str, Any]) -> None:
            try:
                self.wfile.write((json.dumps(ev, ensure_ascii=False) + "\n").encode("utf-8"))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

        agent = self.app.agent
        if agent is None:
            emit({"type": "error", "message": "尚未配置 API Key，请在右上角「设置」中填写后重试。"})
            return
        try:
            for ev in agent.run(data.get("message", ""), data.get("history")):
                emit(ev)
        except LLMError as e:
            emit({"type": "error", "message": str(e)})
        except Exception as e:  # pragma: no cover - defensive
            emit({"type": "error", "message": f"内部错误: {e}"})

    def _direct_tool(self, name: str, data: Dict[str, Any]) -> None:
        ws = self.app.config["workspace"]
        try:
            if name == "read":
                res = builtin_tools.read_file(ws, data.get("path", ""))
            elif name == "write":
                res = builtin_tools.write_file(ws, data.get("path", ""), data.get("content", ""))
            elif name == "edit":
                res = builtin_tools.edit_file(ws, data.get("path", ""),
                                             data.get("old_string", ""), data.get("new_string", ""))
            elif name == "bash":
                res = builtin_tools.run_bash(ws, data.get("command", ""), int(data.get("timeout", 30)))
            elif name == "mkdir":
                res = builtin_tools.make_dir(ws, data.get("path", ""))
            else:
                res = {"ok": False, "error": f"未知工具: {name}"}
        except Exception as e:
            res = {"ok": False, "error": str(e)}
        self._json(res)

    def _mcp_connect(self, data: Dict[str, Any]) -> None:
        try:
            info = self.app.mcp.connect(data)
            self._rebuild_agent_after_mcp()
            self._json({"ok": True, **info})
        except (MCPError, KeyError, Exception) as e:  # noqa: B014
            self._json({"ok": False, "error": str(e)})

    def _rebuild_agent_after_mcp(self) -> None:
        # agent already holds the same registry instance, just refresh llm/tools
        self.app._rebuild()

    # -- low level ----------------------------------------------------------
    def _read_body(self) -> str:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0:
            return ""
        return self.rfile.read(length).decode("utf-8", "replace")

    def _json(self, obj: Dict[str, Any]) -> None:
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _serve_file(self, path: Path, ctype: str) -> None:
        if not path.exists():
            return self._error(404, "Not found")
        payload = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _error(self, code: int, msg: str) -> None:
        payload = json.dumps({"ok": False, "error": msg}).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def make_server(app: CodePalApp, host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    handler = type("H", (Handler,), {"app": app})
    server = ThreadingHTTPServer((host, port), handler)
    return server
