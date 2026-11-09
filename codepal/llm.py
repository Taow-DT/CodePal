"""OpenAI-compatible chat client built on the Python standard library only.

Works with DeepSeek, OpenAI, or any OpenAI-compatible /v1/chat/completions
endpoint, including tool / function calling.
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional


class LLMError(RuntimeError):
    pass


class LLMClient:
    """Minimal chat-completions client (no third-party dependencies)."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "deepseek-chat",
        temperature: float = 0.3,
        max_tokens: int = 2048,
        timeout: int = 120,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    def _url(self) -> str:
        # base_url may or may not include "/v1"; chat/completions is appended.
        return f"{self.base_url}/chat/completions"

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        stream: bool = False,
    ) -> Dict[str, Any]:
        """Send a chat request. Returns the first choice's message dict.

        The message dict has keys: role, content (str|None),
        tool_calls (list|None).
        """
        if not self.api_key:
            raise LLMError("未配置 API Key，请在设置中填写后重试。")

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._url(),
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            raise LLMError(f"HTTP {e.code}: {detail}") from e
        except urllib.error.URLError as e:
            raise LLMError(f"网络错误: {e.reason}") from e

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as e:
            raise LLMError(f"响应不是合法 JSON: {body[:300]}") from e

        if "error" in parsed:
            raise LLMError(f"API 错误: {parsed['error']}")

        choice = parsed["choices"][0]["message"]
        return {
            "role": choice.get("role", "assistant"),
            "content": choice.get("content"),
            "tool_calls": choice.get("tool_calls"),
        }
