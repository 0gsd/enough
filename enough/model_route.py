"""A model route per job (fabula P6): `local` (llama-server) or `cloud` (OpenRouter through the broker).

One factory, `make_complete`, gives a `complete(messages, **kw) -> (text, meta)` with the calling convention
`canon_derive` and Thym's `ModelCoprocessor` already take for an injected `complete`: positional messages, an
optional `max_tokens` (and `temperature`) keyword. The route is chosen for the job, not read from the session's
model slot:

- `local` asks llama-server at an explicit `llm_url` (`llm.complete_local`) and never the cloud, whatever slot the
  session is on.
- `cloud` asks `cloud.gate_status()` first and refuses with the gate's own denial when it is shut (`RouteRefused`,
  never a fall back to local); else `cloud.chat_completion`, then the cloud cache under the job's `source`, then one
  entry in the broker's journal naming the job, the model and the tokens, never the prompt's text.
- Agent-free mode refuses both, as `llm.complete` does (`RouteRefused("agent-free")`).

`meta` always carries `route`, `model` (cloud: the provider's resolved id; local: the id llama-server reports, the
cute name since it is launched with `--alias`), `provider` (`openrouter`, cloud only), `from_reasoning`,
`finish_reason`, and `usage` (`prompt_tokens`, `completion_tokens`, `total_tokens`) when the transport gives it.

`holds_generation_lock(route)` says whether a job on a route must hold `session.generation_lock` (the lock is for
llama-server's one slot); who takes it stays with the caller.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import agent_free as _agent_free
from . import broker as _broker
from . import cloud as _cloud
from . import llm as _llm

log = logging.getLogger(__name__)

ROUTES = ("local", "cloud")
PROVIDER = "openrouter"
JOURNAL_TOOL = "model_route"

CompleteFn = Callable[..., tuple[str, dict[str, Any]]]


class RouteRefused(_llm.LLMUnavailable):
    """The route cannot be used for this job: agent-free is on, or the cloud gate is shut. The message is the text
    to show (the gate's own denial, which says how to fix it; `agent-free` for agent-free). A subclass of
    `llm.LLMUnavailable`, so callers that already turn that into words keep doing so."""

    def __init__(self, route: str, message: str, *, reason: str | None = None) -> None:
        self.route = route
        self.reason = reason or message
        super().__init__(message)


def holds_generation_lock(route: str) -> bool:
    """Must a job on `route` hold the generation lock? `local`: yes (llama-server has one slot); `cloud`: no."""
    if route not in ROUTES:
        raise ValueError(f"unknown model route {route!r} (one of {', '.join(ROUTES)})")
    return route == "local"


def make_complete(route: str, *, model: str | None = None, llm_url: str | None = None,
                  project_dir: Path | str | None = None, source: str = "job",
                  temperature: float = 0.2, timeout: float = 600.0) -> CompleteFn:
    """`complete(messages, **kw) -> (text, meta)` for one job on `route`.

    - `route` — `"local"` or `"cloud"`.
    - `model` — cloud: the OpenRouter model id for this job (None: the configured one). Local: ignored (the model is
      whatever llama-server at `llm_url` is serving).
    - `llm_url` — local: llama-server's base url, required.
    - `project_dir` — cloud: the project whose `rness/io/cloud-cache/` and broker journal record the call, required.
    - `source` — the job's kind (`fabula`, `thym`, `canon`, …): the cloud cache's `source` and the journal's `job`.
    - `temperature`, `timeout` — defaults per call; `complete` takes `temperature=` and `max_tokens=` per call.
      Other keywords are accepted and ignored.

    Raises `ValueError` at once for an unknown route or a missing `llm_url`/`project_dir`; the returned `complete`
    raises `RouteRefused` (agent-free, a shut gate), and transport errors as `llm.complete` does (httpx errors,
    `cloud.CloudError`)."""
    if route not in ROUTES:
        raise ValueError(f"unknown model route {route!r} (one of {', '.join(ROUTES)})")
    if route == "local":
        if not llm_url:
            raise ValueError("the local route needs llama-server's llm_url")

        def complete_local(messages: list[dict[str, str]], **kw: Any) -> tuple[str, dict[str, Any]]:
            if _agent_free.enabled():
                raise RouteRefused("local", _agent_free.REASON)
            return _llm.complete_local(messages, llm_url=str(llm_url), max_tokens=kw.get("max_tokens"),
                                       temperature=_temp(kw, temperature), timeout=timeout)

        return complete_local

    if project_dir is None:
        raise ValueError("the cloud route needs the project_dir its cache and journal are written in")
    pdir = Path(project_dir)
    chosen = (model or "").strip() or None

    def complete_cloud(messages: list[dict[str, str]], **kw: Any) -> tuple[str, dict[str, Any]]:
        if _agent_free.enabled():
            raise RouteRefused("cloud", _agent_free.REASON)
        try:
            gate = _cloud.gate_status()
        except Exception as e:  # noqa: BLE001 - a keyring hiccup shuts the gate for this call
            raise RouteRefused("cloud", f"the cloud gate could not be read ({e})") from e
        if not gate.get("open"):
            reason = gate.get("reason") or "the cloud gate is shut"
            raise RouteRefused("cloud", gate.get("denial") or reason, reason=reason)
        asked = chosen or (gate.get("model_id") or None)
        max_tokens = kw.get("max_tokens")
        try:
            resp = _cloud.chat_completion(messages, model=asked, temperature=_temp(kw, temperature),
                                          max_tokens=max_tokens, timeout=timeout)
        except Exception as e:
            _journal(pdir, source=source, model=asked, usage=None, ok=False,
                     summary=f"{type(e).__name__}: {e}")
            raise
        choice = (resp.get("choices") or [{}])[0]
        text, from_reasoning = _llm.message_text(choice.get("message") or {})
        resolved = resp.get("model") or asked or "unknown"
        meta: dict[str, Any] = {"model": resolved, "route": "cloud", "provider": PROVIDER,
                                "from_reasoning": from_reasoning, "finish_reason": choice.get("finish_reason")}
        usage = _llm.usage_of(resp)
        if usage:
            meta["usage"] = usage
        cached: Path | None = None
        try:
            cached = _cloud.cache_completion(pdir, messages=messages, response_text=text, model=resolved,
                                             usage=usage, source=source)
            meta["cache"] = str(cached)
        except OSError as e:
            log.warning("cloud cache write failed for a %s job (%s)", source, e)
        _journal(pdir, source=source, model=resolved, usage=usage, ok=True,
                 summary=(f"cached {cached.name}" if cached else "not cached (the cache could not be written)"))
        return text, meta

    return complete_cloud


def _temp(kw: dict[str, Any], default: float) -> float:
    t = kw.get("temperature")
    return float(t) if isinstance(t, (int, float)) and not isinstance(t, bool) else default


def _journal(project_dir: Path, *, source: str, model: str | None, usage: dict[str, int] | None,
             ok: bool, summary: str) -> None:
    """One broker-journal entry for one cloud call of a job: the job, the provider, the model, the tokens. Never the
    prompt or the answer."""
    u = usage or {}
    p, c = u.get("prompt_tokens"), u.get("completion_tokens")
    t = u.get("total_tokens") or ((p or 0) + (c or 0) if (p is not None or c is not None) else None)
    tokens = f"{p if p is not None else '?'}/{c if c is not None else '?'}/{t if t is not None else '?'}"
    _broker.trace(project_dir, tool=JOURNAL_TOOL, decision=f"a {source} job used the cloud",
                  args={"job": source, "provider": PROVIDER, "model": model or "unknown",
                        "tokens (p/c/t)": tokens},
                  result_ok=ok, result_summary=summary)
