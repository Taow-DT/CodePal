"""Configuration loading / saving for CodePal.

Runtime config lives in the user's home directory so it stays writable even
when the app is distributed as a frozen one-file executable.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict


DEFAULT_CONFIG: Dict[str, Any] = {
    "llm": {
        # OpenAI-compatible endpoint. Defaults to DeepSeek (per assignment path).
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "",
        "model": "deepseek-chat",
        "temperature": 0.3,
        "max_tokens": 2048,
    },
    # Working directory the agent operates in. Empty => current directory.
    "workspace": "",
    # MCP servers to auto-connect on startup. Each: {"name","command","args","env"}.
    "mcp_servers": [],
}


def config_path() -> Path:
    """Where the runtime config file is stored."""
    if os.environ.get("CODEPAL_CONFIG"):
        return Path(os.environ["CODEPAL_CONFIG"])
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    p = Path(appdata) / "CodePal" / "config.json"
    return p


def load_config(path: Path | None = None) -> Dict[str, Any]:
    path = path or config_path()
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                user = json.load(f)
            _deep_update(cfg, user)
        except Exception:
            pass
    # Normalise workspace
    if not cfg.get("workspace"):
        cfg["workspace"] = os.getcwd()
    cfg["workspace"] = os.path.abspath(os.path.expanduser(cfg["workspace"]))
    return cfg


def save_config(cfg: Dict[str, Any], path: Path | None = None) -> None:
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def mask_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy safe to send to the UI (hides the API key)."""
    out = json.loads(json.dumps(cfg))
    if out.get("llm", {}).get("api_key"):
        out["llm"]["api_key"] = "********"
    return out


def _deep_update(base: Dict[str, Any], override: Dict[str, Any]) -> None:
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_update(base[k], v)
        else:
            base[k] = v
