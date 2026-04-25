"""llama-server client (OpenAI-compatible /v1/chat/completions)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx


class LLMError(RuntimeError):
    """Raised when llama-server returns a 4xx/5xx on the streaming endpoint."""

    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(f"llama-server {status}: {detail}")


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
    include_reasoning: bool = False,
    usage_sink: dict[str, int] | None = None,
) -> AsyncIterator[str]:
    """Stream assistant content chunks from llama-server.

    Yields `content` tokens from the OpenAI-compatible streaming format. The
    model's `reasoning_content` channel (e.g. Gemma 4's thinking output) is
    dropped by default — it's emitted on a separate channel precisely because
    clients are expected to treat it as internal. Set `include_reasoning=True`
    if you want to surface it.

    If `usage_sink` is passed, llama-server is asked (via `stream_options`)
    to include the final `usage` object on the stream's terminal chunk; we
    update the sink in place with `prompt_tokens`, `completion_tokens`, and
    `total_tokens`. A dict (rather than a return value) keeps this an out-
    parameter — the caller can read it after the generator is exhausted
    without changing the streaming contract.

    The caller handles connection lifecycle via the passed-in client; we can
    cancel mid-stream by aclose()'ing the generator.
    """
    url = base_url.rstrip("/") + "/v1/chat/completions"
    payload: dict[str, Any] = {
        "model": "local",
        "messages": messages,
        "stream": True,
        "temperature": temperature,
    }
    if usage_sink is not None:
        payload["stream_options"] = {"include_usage": True}
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if stop:
        payload["stop"] = stop

    async with client.stream("POST", url, json=payload, timeout=None) as resp:
        if resp.status_code >= 400:
            # Read the body for context (llama-server returns useful JSON
            # errors, e.g. context-exceeded messages). aread() after
            # streaming-aware close is the supported way.
            body = await resp.aread()
            detail = body.decode("utf-8", errors="replace")[:500]
            raise LLMError(resp.status_code, detail)
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
            # Final chunk with `usage` typically has empty `choices`, so
            # check usage before bailing out on the choices lookup.
            if usage_sink is not None and (usage := obj.get("usage")):
                for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
                    if (v := usage.get(k)) is not None:
                        usage_sink[k] = int(v)
            try:
                choice = obj["choices"][0]
            except (KeyError, IndexError):
                continue
            delta = choice.get("delta") or {}
            if include_reasoning and (rc := delta.get("reasoning_content")):
                yield rc
            if (c := delta.get("content")):
                yield c
            if choice.get("finish_reason"):
                break
