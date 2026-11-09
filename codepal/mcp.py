"""Minimal MCP (Model Context Protocol) stdio client.

Implements just enough of the JSON-RPC 2.0 stdio transport to connect to an
MCP server, enumerate its tools, and call them — no third-party SDK required.
This is what makes CodePal's toolset *extensible* beyond the four built-ins.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
from typing import Any, Dict, List, Optional


class MCPError(RuntimeError):
    pass


class MCPClient:
    """A synchronous JSON-RPC client talking to one MCP server over stdio."""

    def __init__(
        self,
        name: str,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        timeout: int = 30,
    ) -> None:
        self.name = name
        self.timeout = timeout
        full_cmd = [command] + list(args or [])
        child_env = dict(os.environ)
        if env:
            child_env.update(env)

        self.proc = subprocess.Popen(
            full_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=cwd,
            env=child_env,
        )
        self._wlock = threading.Lock()
        self._pending: Dict[int, "queue.Queue[Dict[str, Any]]"] = {}
        self._id = 0
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        self.initialize()

    # -- low level ----------------------------------------------------------
    def _send(self, obj: Dict[str, Any]) -> None:
        with self._wlock:
            self.proc.stdin.write(json.dumps(obj) + "\n")
            self.proc.stdin.flush()

    def _read_loop(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            rid = msg.get("id")
            if rid is not None and rid in self._pending:
                self._pending[rid].put(msg)
            # notifications (no id) are intentionally ignored here

    def _request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self._wlock:
            self._id += 1
            rid = self._id
            q: "queue.Queue[Dict[str, Any]]" = queue.Queue()
            self._pending[rid] = q
        try:
            self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}})
            resp = q.get(timeout=self.timeout)
        finally:
            self._pending.pop(rid, None)
        if "error" in resp:
            raise MCPError(str(resp["error"]))
        return resp.get("result", {})

    def _notify(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    # -- MCP protocol -------------------------------------------------------
    def initialize(self) -> Dict[str, Any]:
        result = self._request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "CodePal", "version": "1.0.0"},
            },
        )
        self._notify("notifications/initialized", {})
        return result

    def list_tools(self) -> List[Dict[str, Any]]:
        res = self._request("tools/list", {})
        return res.get("tools", [])

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("tools/call", {"name": name, "arguments": arguments})

    def is_alive(self) -> bool:
        return self.proc.poll() is None

    def close(self) -> None:
        try:
            self.proc.terminate()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Registry: merges several MCP servers into the agent's tool set.
# ---------------------------------------------------------------------------
def _mcp_tool_name(server: str, tool: str) -> str:
    return f"mcp__{server}__{tool}"


class MCPRegistry:
    def __init__(self) -> None:
        self._clients: Dict[str, MCPClient] = {}

    def connect(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        name = spec["name"]
        client = MCPClient(
            name=name,
            command=spec["command"],
            args=spec.get("args"),
            env=spec.get("env"),
            cwd=spec.get("cwd"),
        )
        tools = client.list_tools()
        self._clients[name] = client
        return {"server": name, "tool_count": len(tools),
                "tools": [t["name"] for t in tools]}

    def disconnect(self, name: str) -> None:
        c = self._clients.pop(name, None)
        if c:
            c.close()

    def disconnect_all(self) -> None:
        for c in self._clients.values():
            c.close()
        self._clients.clear()

    def servers(self) -> List[str]:
        return list(self._clients.keys())

    def tool_schemas(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for server, client in self._clients.items():
            for t in client.list_tools():
                out.append({
                    "type": "function",
                    "function": {
                        "name": _mcp_tool_name(server, t["name"]),
                        "description": f"[MCP:{server}] {t.get('description', '')}",
                        "parameters": t.get("inputSchema",
                                            {"type": "object", "properties": {}}),
                    },
                })
        return out

    def call(self, prefixed_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not prefixed_name.startswith("mcp__"):
            return {"ok": False, "error": "非 MCP 工具"}
        rest = prefixed_name[len("mcp__"):]
        server, _, tool = rest.partition("__")
        client = self._clients.get(server)
        if not client:
            return {"ok": False, "error": f"MCP 服务未连接: {server}"}
        try:
            res = client.call_tool(tool, arguments)
        except MCPError as e:
            return {"ok": False, "error": str(e)}
        # Normalise MCP content blocks into a plain string.
        parts: List[str] = []
        for block in res.get("content", []):
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        text = "\n".join(parts)
        return {"ok": not res.get("isError", False), "output": text}

    def snapshot(self) -> List[Dict[str, Any]]:
        out = []
        for server, client in self._clients.items():
            out.append({"server": server, "tools": [t["name"] for t in client.list_tools()]})
        return out
