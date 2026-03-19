from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx

from core.config import minimax_api_key


def _chat_url(base: str) -> str:
    b = base.rstrip("/")
    if b.endswith("/v1"):
        return f"{b}/text/chatcompletion_v2"
    return f"{b}/v1/text/chatcompletion_v2"


def chat_completion(
    messages: List[Dict[str, Any]],
    *,
    model: str = "MiniMax-M2.5",
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    timeout_sec: float = 120.0,
) -> str:
    """
    Chat completion HTTP client (provider-specific endpoint).
    Auth: Bearer token in Authorization header.
    """
    key = api_key or minimax_api_key()
    if not key:
        raise ValueError("LLM API key is not set")

    base = api_base or os.environ.get("MINIMAX_API_BASE", "https://api.minimax.io")
    url = _chat_url(base)

    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=timeout_sec) as client:
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"LLM API response missing choices: {data}")

    message = choices[0].get("message") or {}
    content = message.get("content")
    if content is None:
        raise RuntimeError(f"LLM API response missing message.content: {data}")

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts).strip()

    return str(content).strip()
