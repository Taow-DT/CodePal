"""CodePal entry point: build the app, start the local server, open the UI."""
from __future__ import annotations

import os
import sys
import logging
import threading
import webbrowser
from pathlib import Path

from .server import CodePalApp, make_server


def _setup_logging() -> None:
    if getattr(sys, "frozen", False):
        log_dir = Path(os.environ.get("TEMP", os.path.expanduser("~"))) / "CodePal"
        log_dir.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=log_dir / "codepal.log",
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
        )
        # Mirror unexpected tracebacks to the log file.
        sys.stdout = open(log_dir / "stdout.log", "a", encoding="utf-8")
        sys.stderr = open(log_dir / "stderr.log", "a", encoding="utf-8")


def _persist_url(url: str) -> None:
    """Drop a clickable shortcut + a plain-text fallback so the user can always
    reach the UI even if the browser fails to auto-open."""
    try:
        tmp = Path(os.environ.get("TEMP", os.path.expanduser("~"))) / "CodePal"
        tmp.mkdir(parents=True, exist_ok=True)
        (tmp / "last_url.txt").write_text(url, encoding="utf-8")
    except Exception:
        pass
    # Desktop .url shortcut (best-effort; may be blocked by OneDrive redirect).
    try:
        desktop = Path(os.path.expandvars("%USERPROFILE%")) / "Desktop"
        if not desktop.exists():
            desktop = Path.home() / "Desktop"
        if desktop.exists():
            shortcut = desktop / "CodePal 访问地址.url"
            shortcut.write_text(
                "[InternetShortcut]\nURL=" + url + "\n", encoding="utf-8"
            )
    except Exception:
        pass


def _open_browser(url: str) -> bool:
    """Open the URL as reliably as possible; returns True on a successful call.

    On Windows we prefer os.startfile (ShellExecute) which is the most reliable
    way to launch the default http handler from a frozen, console-less process.
    """
    # Retry a few times — the server is already listening, but the default
    # browser may take a moment on first launch.
    for _ in range(3):
        try:
            if sys.platform.startswith("win"):
                os.startfile(url)  # type: ignore[attr-defined]
                return True
        except Exception:
            pass
        try:
            if webbrowser.open(url, new=2):
                return True
        except Exception:
            pass
        threading.Event().wait(1.0)
    return False


def _show_fatal(message: str) -> None:
    """Surface a fatal error to the user even from a --noconsole EXE."""
    try:
        if sys.platform.startswith("win"):
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, "CodePal", 0x10)  # MB_ICONERROR
    except Exception:
        pass
    logging.error("FATAL: %s", message)


def main() -> None:
    try:
        _setup_logging()
        app = CodePalApp()
        # Fixed, memorable port with a fallback to a random one if busy.
        server = make_server(app, "127.0.0.1", 8731)
        try:
            port = server.server_address[1]
        except Exception:
            server = make_server(app, "127.0.0.1", 0)
            port = server.server_address[1]
        url = f"http://127.0.0.1:{port}"
        print(f"CodePal 已启动 -> {url}")
        print(f"工作区: {app.config['workspace']}")
        logging.info("CodePal started on %s (workspace=%s)", url, app.config["workspace"])
        _persist_url(url)

        # Open the browser shortly after startup (retry handled inside).
        threading.Timer(1.2, lambda: _open_browser(url)).start()

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            app.mcp.disconnect_all()
            server.server_close()
    except Exception as e:  # never die silently in a --noconsole build
        _show_fatal(f"CodePal 启动失败：\n{e}\n\n日志位于 %TEMP%\\CodePal\\codepal.log")
        raise


if __name__ == "__main__":
    main()
