"""Build a one-file Windows executable for CodePal using PyInstaller.

Run from the project root:
    python packaging/build_windows.py
Result: dist/CodePal.exe  (a portable, double-click-to-run install package)
"""
from __future__ import annotations

import os
import sys

from PyInstaller.__main__ import run

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_SRC = os.path.join(ROOT, "codepal", "web")


def main() -> None:
    os.chdir(ROOT)
    sep = os.pathsep  # ';' on Windows
    args = [
        "run.py",
        "--name", "CodePal",
        "--onefile",
        "--noconsole",
        "--clean",
        "--paths", ROOT,
        "--add-data", f"{WEB_SRC}{sep}codepal/web",
        "--hidden-import", "codepal",
        "--hidden-import", "codepal.server",
        "--hidden-import", "codepal.agent",
        "--hidden-import", "codepal.llm",
        "--hidden-import", "codepal.mcp",
        "--hidden-import", "codepal.tools",
        "--hidden-import", "codepal.config",
        "--hidden-import", "codepal.main",
    ]
    icon = os.path.join(ROOT, "packaging", "icon.ico")
    if os.path.exists(icon):
        args += ["--icon", icon]
    run(args)
    print("BUILD DONE ->", os.path.join(ROOT, "dist", "CodePal.exe"))


if __name__ == "__main__":
    sys.exit(main())
