"""Minimal interactive Python debugger backend for CodePal.

Launches the user's Python file under a tracer that pauses at breakpoints and
on each step, exposing local variables. It talks to the frontend through JSON
protocol lines written to stdout (prefixed with ``CODEPAL_DEBUG_JSON:`` so they
can be told apart from the program's own prints).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from typing import Any, Dict, List, Optional

# The harness is executed by the user's real Python interpreter (not the frozen
# CodePal executable). It only uses the standard library.
HARNESS = r'''
import sys, json, runpy

TARGET = sys.argv[1]
try:
    BPS = set(int(x) for x in sys.argv[2].split(",") if x)
except Exception:
    BPS = set()
STEP = {"on": False}

def emit(obj):
    sys.stdout.write("CODEPAL_DEBUG_JSON:" + json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()

def trace(frame, event, arg):
    if event != "line":
        return trace
    if frame.f_code.co_filename != TARGET:
        return trace
    lineno = frame.f_lineno
    if lineno in BPS or STEP["on"]:
        loc = {}
        for k, v in frame.f_locals.items():
            try:
                loc[k] = repr(v)
            except Exception:
                loc[k] = "<unrepr>"
        emit({"event": "break", "line": lineno, "locals": loc, "file": frame.f_code.co_filename})
        cmd = ""
        try:
            cmd = sys.stdin.readline().strip()
        except Exception:
            cmd = "q"
        if cmd == "s":
            STEP["on"] = True
        elif cmd == "c":
            STEP["on"] = False
        elif cmd == "q":
            sys.exit(0)
    return trace

sys.settrace(trace)
try:
    runpy.run_path(TARGET, run_name="__main__")
except SystemExit:
    pass
except Exception as e:
    emit({"event": "error", "message": repr(e)})
emit({"event": "done"})
'''


def find_python() -> Optional[str]:
    for cand in ("python", "python3", "py"):
        exe = shutil.which(cand)
        if exe:
            return exe
    return None


class DebugSession:
    def __init__(self, workspace: str, rel_path: str, breakpoints: List[int]):
        self.workspace = workspace
        self.rel_path = rel_path
        self.breakpoints = breakpoints
        self.events: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self.ended = False
        self.proc: Optional[subprocess.Popen] = None
        self._harness_path: Optional[str] = None
        self._next_id = 0

    def push(self, ev: Dict[str, Any]) -> None:
        with self._lock:
            ev = dict(ev)
            ev["_id"] = self._next_id
            self._next_id += 1
            self.events.append(ev)
            if ev.get("event") in ("done", "error"):
                self.ended = True

    def drain(self, after: int) -> List[Dict[str, Any]]:
        with self._lock:
            return [e for e in self.events if e["_id"] > after]

    def start(self) -> Dict[str, Any]:
        py = find_python()
        if not py:
            return {"ok": False, "error": "未找到 Python 解释器，请先安装 Python 并加入系统 PATH 后重试。"}
        try:
            from .tools import resolve_path
            target = str(resolve_path(self.workspace, self.rel_path))
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        if not os.path.isfile(target):
            return {"ok": False, "error": f"文件不存在: {self.rel_path}"}
        fd, harness_path = tempfile.mkstemp(suffix=".py", prefix="codepal_dbg_")
        os.close(fd)
        with open(harness_path, "w", encoding="utf-8") as f:
            f.write(HARNESS)
        self._harness_path = harness_path
        bp_csv = ",".join(str(b) for b in self.breakpoints)
        try:
            self.proc = subprocess.Popen(
                [py, "-u", harness_path, target, bp_csv],
                cwd=os.path.abspath(self.workspace),
                stdout=subprocess.PIPE,
                stdin=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except Exception as e:
            try:
                os.remove(harness_path)
            except Exception:
                pass
            return {"ok": False, "error": f"启动调试失败: {e}"}
        threading.Thread(target=self._reader, daemon=True).start()
        return {"ok": True, "pid": self.proc.pid}

    def _reader(self) -> None:
        assert self.proc is not None and self.proc.stdout is not None
        try:
            for line in self.proc.stdout:
                line = line.rstrip("\n")
                if line.startswith("CODEPAL_DEBUG_JSON:"):
                    try:
                        self.push(json.loads(line[len("CODEPAL_DEBUG_JSON:"):]))
                    except Exception:
                        self.push({"event": "output", "text": line})
                elif line != "":
                    self.push({"event": "output", "text": line})
        except Exception:
            pass
        try:
            self.proc.wait(timeout=2)
        except Exception:
            pass
        if not self.ended:
            self.push({"event": "done"})
        if self._harness_path:
            try:
                os.remove(self._harness_path)
            except Exception:
                pass

    def command(self, cmd: str) -> None:
        if self.proc is not None and self.proc.stdin is not None and not self.ended:
            try:
                self.proc.stdin.write(cmd + "\n")
                self.proc.stdin.flush()
            except Exception:
                pass
        if cmd == "q":
            self.stop()

    def stop(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except Exception:
                pass
        self.ended = True


class DebugManager:
    def __init__(self) -> None:
        self.sessions: Dict[str, DebugSession] = {}
        self._counter = 0
        self._lock = threading.Lock()

    def new_session(self, workspace: str, rel: str, bps: List[int]):
        with self._lock:
            self._counter += 1
            sid = str(self._counter)
        s = DebugSession(workspace, rel, bps)
        with self._lock:
            self.sessions[sid] = s
        return sid, s

    def get(self, sid: str) -> Optional[DebugSession]:
        return self.sessions.get(sid)
