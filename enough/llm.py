"""llama-server client (OpenAI-compatible /v1/chat/completions)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx


def check_llm_reachable(base_url: str, timeout: float = 3.0) -> tuple[bool, str]:
    """Synchronous health check. Returns (ok, reason)."""
    url = base_url.rstrip("/") + "/health"
    try:
        r = httpx.get(url, timeout=timeout)
    except httpx.ConnectError:
        return False, f"connection refused ({url})"
    except httpx.TimeoutException:
        return False, f"timeout ({url})"
    except httpx.HTTPError as e:
        return False, f"http error: {e}"
    if r.status_code == 200:
        return True, "ok"
    if r.status_code == 503:
        # llama-server returns 503 while loading — still "reachable".
        return True, "loading"
    return False, f"unexpected status {r.status_code}"


async def stream_chat(
    base_url: str,
    messages: list[dict[str, str]],
    *,
    client: httpx.AsyncClient,
    temperature: float = 0.7,
    max_tokens: int | None = None,
    stop: list[str] | None = None,
) -> AsyncIterator[str]:
    """Stream assistant content chunks from llama-server.

    Yields plain text content pieces as they arrive (SSE `data: {...}` from the
    OpenAI-compatible streaming format). Reasoning-channel content, if the
    model produces it, is yielded interleaved but prefixed with a sentinel so
    callers can strip or style it if they wish. For v0.01 we fold it into the
    stream transparently because Gemma 4 emits reasoning before final answer
    and users want to see the work.

    The caller is expected to handle connection lifecycle via the passed-in
    client (so we can cancel mid-stream by cancelling the task).
    """
    url = base_url.rstrip("/") + "/v1/chat/completions"
    payload: dict[str, Any] = {
        "model": "local",
        "messages": messages,
        "stream": True,
        "temperature": temperature,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if stop:
        payload["stop"] = stop

    async with client.stream("POST", url, json=payload, timeout=None) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line:
                continue
            if not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except json.JSONDecodeError:
                continue
            try:
                choice = obj["choices"][0]
            except (KeyError, IndexError):
                continue
            delta = choice.get("delta") or {}
            # Reasoning channel (Gemma 4 style) — emit as-is; the UI can style.
            if (rc := delta.get("reasoning_content")):
                yield rc
            if (c := delta.get("content")):
                yield c
            if choice.get("finish_reason"):
                break
