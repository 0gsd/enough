"""llama-server client (OpenAI-compatible /v1/chat/completions)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from . import agent_free as _agent_free


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

    Agent-free mode refuses here too (`LLMUnavailable`), behind the route
    gate that should have stopped the turn first.
    """
    if _agent_free.enabled():
        raise LLMUnavailable(_agent_free.REASON)
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
            # Don't break on finish_reason — llama-server sends the
            # `usage` chunk *after* the finish_reason chunk when
            # stream_options.include_usage is set, and breaking early
            # would silently drop the token counts. [DONE] (above) is
            # the authoritative terminator.


# ---------------------------------------------------------------------------
# One-shot completions (0.4.3): the derivation engine and the skill audit
# ---------------------------------------------------------------------------
#
# Lifted from `skillaudit._complete` so there is one non-streaming door to
# whichever model the user is actually running: the local llama-server, or
# the cloud slot (`opro-api`) when the cloud gate is open. A reasoning model
# spends much of its budget before the answer channel opens, so the budget
# is generous but never larger than the window llama-server was launched
# with (`/props` says what that is; `models.recommend_ctx()` can go as low
# as 4096 on a small machine).

DEFAULT_LLM_URL = "http://127.0.0.1:8080"
DEFAULT_MAX_TOKENS = 8_000
MIN_TOKENS = 1_200
CTX_HEADROOM = 512


class LLMUnavailable(RuntimeError):
    """No model can answer this completion: agent-free mode is on, or the
    cloud slot is chosen but the cloud gate is shut. Carries the plain reason
    as its message (`agent-free` for the first)."""


def message_text(message: dict[str, Any]) -> tuple[str, bool]:
    """`(text, came_from_reasoning)` for one completion message.

    Reasoning models put their thinking in `reasoning_content` and their
    answer in `content`. When the budget runs out one token before the
    answer channel opens, `content` is empty and the whole answer sits in
    `reasoning_content`; read it instead and let the caller decide what a
    reasoning-only answer is worth."""
    content = (message.get("content") or "").strip()
    if content:
        return content, False
    reasoning = (message.get("reasoning_content")
                 or message.get("reasoning") or "")
    reasoning = reasoning.strip() if isinstance(reasoning, str) else ""
    return reasoning, bool(reasoning)


def completion_budget(messages: list[dict[str, str]], base: str, *,
                      cap: int = DEFAULT_MAX_TOKENS, floor: int = MIN_TOKENS,
                      headroom: int = CTX_HEADROOM) -> int:
    """How many tokens a completion may spend: `cap`, unless llama-server's
    `/props` reports an `n_ctx` smaller than prompt + cap + headroom, then
    what is left — never below `floor` (if even that doesn't fit, the request
    fails loudly rather than truncating silently). No `/props` (an older
    build, a server still booting) → `cap`."""
    ctx: int | None = None
    try:
        r = httpx.get(f"{base}/props", timeout=5.0)
        if r.status_code == 200:
            n = (r.json().get("default_generation_settings") or {}).get("n_ctx")
            ctx = int(n) if n else None
    except Exception:  # noqa: BLE001 — a missing /props is not an error
        ctx = None
    if not ctx:
        return cap
    chars = sum(len(m.get("content") or "") for m in messages)
    prompt_tokens = chars // 3          # the rough estimator server.py uses
    room = ctx - prompt_tokens - headroom
    return max(floor, min(cap, room))


def _current_slot() -> str | None:
    """The model slot the user is running (`opro-api` is the cloud)."""
    from . import models as _models
    try:
        return _models.load_state().get("current")
    except Exception:  # noqa: BLE001
        return None


def complete(messages: list[dict[str, str]], *, llm_url: str | None,
             max_tokens: int | None = None, temperature: float = 0.2,
             timeout: float = 600.0, cloud_gate: bool = True) -> tuple[str, dict[str, Any]]:
    """One non-streaming completion, routed like chat: the cloud slot when
    `models.load_state()["current"] == "opro-api"` (only while the cloud
    gate is open, else `LLMUnavailable`), otherwise llama-server's
    `/v1/chat/completions` at `llm_url`. Returns `(text, meta)`, meta =
    `{model, route: local|cloud, from_reasoning, finish_reason}` (`"length"`
    when the answer was cut off by the budget or the window). Transport failures raise
    (httpx errors, `cloud.CloudError`); the caller turns them into words.

    `cloud_gate=False` is the skill audit's pre-0.4.3 behaviour (it never
    asked the gate); every new caller keeps the default. Agent-free mode
    refuses whatever the slot (`LLMUnavailable("agent-free")`)."""
    if _agent_free.enabled():
        raise LLMUnavailable(_agent_free.REASON)
    if _current_slot() == "opro-api":
        from . import cloud as _cloud
        if cloud_gate:
            gate = _cloud.gate_status()
            if not gate.get("open"):
                raise LLMUnavailable(gate.get("reason") or "the cloud gate is shut")
        resp = _cloud.chat_completion(messages, temperature=temperature,
                                      max_tokens=max_tokens, timeout=timeout)
        choice = (resp.get("choices") or [{}])[0]
        text, from_reasoning = message_text(choice.get("message") or {})
        return text, {"model": resp.get("model"), "route": "cloud",
                      "from_reasoning": from_reasoning,
                      "finish_reason": choice.get("finish_reason")}
    base = (llm_url or DEFAULT_LLM_URL).rstrip("/")
    r = httpx.post(f"{base}/v1/chat/completions", timeout=timeout, json={
        "messages": messages, "stream": False,
        "temperature": temperature,
        "max_tokens": completion_budget(messages, base,
                                        cap=max_tokens or DEFAULT_MAX_TOKENS),
    })
    r.raise_for_status()
    data = r.json()
    choice = (data.get("choices") or [{}])[0]
    text, from_reasoning = message_text(choice.get("message") or {})
    return text, {"model": data.get("model"), "route": "local",
                  "from_reasoning": from_reasoning,
                  "finish_reason": choice.get("finish_reason")}


def reachable(llm_url: str | None) -> tuple[bool, str]:
    """Can a one-shot completion be answered right now? `(ok, reason)`.

    The cloud gate when the cloud slot is chosen; otherwise llama-server's
    `/health`, where 503 ("loading") counts as NOT ready: a derivation that
    starts against a loading model fails on its first chunk, so the engine
    asks this before it starts and writes a labelled scaffold instead.

    Agent-free mode answers `(False, "agent-free")` before anything is
    probed: the derivations then take their rules path, and the reason rides
    on the job (`reason: agent-free`) so the UI can say why."""
    if _agent_free.enabled():
        return False, _agent_free.REASON
    if _current_slot() == "opro-api":
        from . import cloud as _cloud
        try:
            gate = _cloud.gate_status()
        except Exception as e:  # noqa: BLE001 — a keyring hiccup is "not ready"
            return False, f"the cloud gate could not be read ({e})"
        if gate.get("open"):
            return True, f"cloud ({gate.get('model_id') or 'openrouter'})"
        return False, gate.get("reason") or "the cloud gate is shut"
    ok, why = check_llm_reachable(llm_url or DEFAULT_LLM_URL)
    if ok and why == "loading":
        return False, "the model is still loading"
    return ok, why
