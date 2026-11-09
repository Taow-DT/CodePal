"""The four built-in tools — read, write, edit, bash.

Each tool is described by a ToolSpec (name, description, JSON schema) plus a
handler. Path operations are sandboxed to the workspace directory so the agent
cannot clobber files outside the project.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------
def resolve_path(workspace: str, p: str) -> Path:
    """Resolve ``p`` against the workspace, refusing to escape it."""
    ws = Path(os.path.abspath(workspace))
    if not p:
        raise ValueError("路径不能为空")
    if os.path.isabs(p):
        cand = Path(os.path.abspath(p))
    else:
        cand = (ws / p).resolve()
    ws_resolved = ws.resolve()
    try:
        cand.relative_to(ws_resolved)
    except ValueError:
        raise ValueError(f"路径越界，禁止访问工作区之外的文件: {p}")
    return cand


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------
READ_LIMIT = 200_000  # characters


def read_file(workspace: str, path: str) -> Dict[str, Any]:
    try:
        fp = resolve_path(workspace, path)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    if not fp.exists():
        return {"ok": False, "error": f"文件不存在: {path}"}
    if fp.is_dir():
        return {"ok": False, "error": f"这是一个目录，不是文件: {path}"}
    try:
        text = fp.read_text(encoding="utf-8", errors="replace")
    except Exception as e:  # pragma: no cover - permission / decode edge cases
        return {"ok": False, "error": f"读取失败: {e}"}
    truncated = len(text) > READ_LIMIT
    if truncated:
        text = text[:READ_LIMIT]
    lines = text.splitlines()
    body = "\n".join(f"{i + 1:>5}\t{ln}" for i, ln in enumerate(lines))
    note = " [已截断，仅显示前 %d 字符]" % READ_LIMIT if truncated else ""
    return {
        "ok": True,
        "path": str(fp),
        "lines": len(lines),
        "bytes": fp.stat().st_size,
        "content": body + note,
    }


def write_file(workspace: str, path: str, content: str) -> Dict[str, Any]:
    try:
        fp = resolve_path(workspace, path)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    try:
        if fp.exists():
            # Keep a single rolling backup so edits are reversible.
            backup = fp.with_suffix(fp.suffix + ".bak")
            backup.write_text(fp.read_text(encoding="utf-8", errors="replace"),
                              encoding="utf-8")
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
    except Exception as e:
        return {"ok": False, "error": f"写入失败: {e}"}
    return {
        "ok": True,
        "path": str(fp),
        "bytes": fp.stat().st_size,
        "message": f"已写入 {fp.stat().st_size} 字节",
    }


def edit_file(workspace: str, path: str, old_string: str,
              new_string: str) -> Dict[str, Any]:
    if not old_string:
        return {"ok": False, "error": "old_string 不能为空"}
    try:
        fp = resolve_path(workspace, path)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    if not fp.exists():
        return {"ok": False, "error": f"文件不存在: {path}"}
    try:
        text = fp.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"ok": False, "error": f"读取失败: {e}"}
    count = text.count(old_string)
    if count == 0:
        return {"ok": False, "error": "未在文件中找到 old_string"}
    if count > 1:
        return {
            "ok": False,
            "error": f"old_string 在文件中出现 {count} 次，存在歧义，请提供更多上下文",
        }
    new_text = text.replace(old_string, new_string, 1)
    try:
        fp.write_text(new_text, encoding="utf-8")
    except Exception as e:
        return {"ok": False, "error": f"写回失败: {e}"}
    return {
        "ok": True,
        "path": str(fp),
        "message": "已替换 1 处",
    }


def run_bash(workspace: str, command: str, timeout: int = 30) -> Dict[str, Any]:
    if not command.strip():
        return {"ok": False, "error": "命令不能为空"}
    cwd = os.path.abspath(workspace)
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"命令执行超时（>{timeout}s）"}
    except Exception as e:
        return {"ok": False, "error": f"执行失败: {e}"}
    out = (proc.stdout or "") + (proc.stderr or "")
    if len(out) > 50_000:
        out = out[:50_000] + "\n... [输出已截断]"
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "output": out,
    }


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------
TOOL_HANDLERS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "run_bash": run_bash,
}


def tool_schemas() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "读取工作区内某个文本文件的内容（带行号），用于查看代码或配置。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string",
                                 "description": "相对于工作区的文件路径，如 src/main.py"}
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "创建或覆盖写入一个文件。会保留上一版本的 .bak 备份。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "目标文件路径"},
                        "content": {"type": "string", "description": "要写入的完整内容"},
                    },
                    "required": ["path", "content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "edit_file",
                "description": "在文件中将 old_string 精确替换为 new_string（必须唯一匹配）。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "old_string": {"type": "string"},
                        "new_string": {"type": "string"},
                    },
                    "required": ["path", "old_string", "new_string"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_bash",
                "description": "在工作区目录执行一条 shell 命令，返回标准输出/错误与退出码。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string",
                                    "description": "要执行的 shell 命令"},
                        "timeout": {"type": "integer",
                                    "description": "超时秒数，默认 30"},
                    },
                    "required": ["command"],
                },
            },
        },
    ]


def dispatch(name: str, workspace: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a built-in tool by name and return its result dict."""
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return {"ok": False, "error": f"未知工具: {name}"}
    if name == "read_file":
        return handler(workspace, args.get("path", ""))
    if name == "write_file":
        return handler(workspace, args.get("path", ""), args.get("content", ""))
    if name == "edit_file":
        return handler(workspace, args.get("path", ""),
                       args.get("old_string", ""), args.get("new_string", ""))
    if name == "run_bash":
        return handler(workspace, args.get("command", ""),
                       int(args.get("timeout", 30)))
    return {"ok": False, "error": f"未实现: {name}"}
