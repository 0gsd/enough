"""The context-window preflight (the 16 GB context fix, 0.4.3).

A fresh project's system prompt is ~20k tokens (docs/ctx-16gb-plan.md §1),
and a model launched with a smaller window used to answer the first message
with llama-server's 400. This module asks the model, before anyone types,
whether enough's instructions fit: it builds the default system prompt
exactly as a chat turn does (`prompt.assemble_system_prompt`, the `chat`
profile, no pal block), counts it with llama-server's own tokenizer
(`POST /tokenize`, exact), reads the live window from `GET /props`
(`default_generation_settings.n_ctx`), and keeps a 2,048-token reserve for
the first message and a thinking reply.

The verdict (see `evaluate`) is what `GET /api/llm-status` exposes:

    prompt_tokens, n_ctx, reserve, fits, suggest_ctx, fix, fix_reason

plus `preflight`, the run's state. `fix` is `"switch"` only when enough
supervises the model AND `models.feasibility(entry, ctx=suggest_ctx)` puts
the RAM axis above "no"; the empty conversation then offers a one-click
`POST /api/model {cute, ctx: suggest_ctx}`. Otherwise `fix` is `"none"` and
`fix_reason` is a stable code the UI words in six languages:
`no_window` (no window this model supports holds the prompt),
`unsupervised` (enough does not run this llama-server, so it cannot resize
it) or `memory` (the window that would fit wants more memory than this
machine gives this model).

It never blocks a request and never raises into one: runs are background
tasks, a failure (the model still loading, an old build without
`/tokenize`, a timeout) leaves the verdict unknown (`fits: None`), and cloud
mode (`opro-api`) is skipped outright — the cloud's window is not ours to
measure. stdlib + httpx, like `llm.py`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Callable
from typing import Any

import httpx

from . import models as _models

log = logging.getLogger("enough.preflight")

#: Tokens kept free beside the system prompt: a first message (~200) and a
#: thinking reply (gemma-4 spends ~1k on a median one, plan §1a).
RESERVE = 2048
#: The windows the one-click fix chooses between, smallest first.
WINDOWS: tuple[int, ...] = (32768, 65536, 131072)
#: Per-request ceiling. llama-server tokenized the 20k-token prompt in
#: 0.02 s (plan §4d); a slow machine mid-load gets ten seconds, then the
#: verdict is simply unknown.
TIMEOUT_S = 10.0
CLOUD_SLOT = "opro-api"

#: The fix_reason codes (the UI's t() keys hang off these).
REASON_NO_WINDOW = "no_window"
REASON_UNSUPERVISED = "unsupervised"
REASON_MEMORY = "memory"


class PreflightError(RuntimeError):
    """llama-server answered, but not with what the preflight needs."""


# ---------------------------------------------------------------------------
# The arithmetic (pure)
# ---------------------------------------------------------------------------

def suggest_ctx(prompt_tokens: int, ctx_max: int | None,
                reserve: int = RESERVE) -> int | None:
    """The smallest of WINDOWS that holds `prompt_tokens + reserve` and is no
    larger than the model's `ctx_max` (unknown `ctx_max` → no ceiling).
    None when no such window exists."""
    need = int(prompt_tokens) + int(reserve)
    for window in WINDOWS:
        if window >= need and (not ctx_max or window <= int(ctx_max)):
            return window
    return None


def evaluate(prompt_tokens: int, n_ctx: int, *, entry: dict | None = None,
             supervised: bool = False, reserve: int = RESERVE) -> dict[str, Any]:
    """The verdict for one measurement.

    `entry` is the model's registry entry (None for a llama-server enough
    cannot name — an external one, or an adopted file not in the registry);
    `supervised` is whether enough can restart this model with another
    window (`/api/model` works). Reasons are checked most fundamental
    first: no window at all, then nobody to apply one, then memory."""
    prompt_tokens = int(prompt_tokens)
    n_ctx = int(n_ctx)
    fits = prompt_tokens + reserve <= n_ctx
    out: dict[str, Any] = {
        "prompt_tokens": prompt_tokens,
        "n_ctx": n_ctx,
        "reserve": reserve,
        "fits": fits,
        "suggest_ctx": None,
        "fix": "none",
        "fix_reason": None,
    }
    if fits:
        return out
    ctx_max = int(entry.get("ctx_max") or 0) if entry else None
    window = suggest_ctx(prompt_tokens, ctx_max, reserve)
    out["suggest_ctx"] = window
    if window is None:
        out["fix_reason"] = REASON_NO_WINDOW
    elif not supervised or not entry:
        out["fix_reason"] = REASON_UNSUPERVISED
    else:
        verdict = _models.feasibility(entry, ctx=window)
        if verdict.get("ram", verdict.get("verdict")) == "no":
            out["fix_reason"] = REASON_MEMORY
        else:
            out["fix"] = "switch"
    return out


# ---------------------------------------------------------------------------
# Asking llama-server
# ---------------------------------------------------------------------------

async def count_tokens(client: httpx.AsyncClient, llm_url: str, text: str, *,
                       timeout: float = TIMEOUT_S) -> int:
    """Exact token count of `text` in the running model's tokenizer.
    llama-server's `/tokenize` adds no BOS by default, so this is the raw
    count the plan measured (19,974 for a fresh project on gemma-4)."""
    r = await client.post(llm_url.rstrip("/") + "/tokenize",
                          json={"content": text, "with_pieces": False},
                          timeout=timeout)
    r.raise_for_status()
    tokens = r.json().get("tokens")
    if not isinstance(tokens, list):
        raise PreflightError("/tokenize returned no token list")
    return len(tokens)


async def read_n_ctx(client: httpx.AsyncClient, llm_url: str, *,
                     timeout: float = TIMEOUT_S) -> int:
    """The live per-slot window, from `/props`."""
    r = await client.get(llm_url.rstrip("/") + "/props", timeout=timeout)
    r.raise_for_status()
    n = (r.json().get("default_generation_settings") or {}).get("n_ctx")
    if not n:
        raise PreflightError("/props reported no n_ctx")
    return int(n)


_CTX_IN_ERROR_RE = re.compile(r"context size \((\d+) tokens?\)")


def n_ctx_from_error(detail: str) -> int | None:
    """The window an overflow 400 names. llama-server's body is JSON with
    `error.n_ctx` on current builds and says "…available context size
    (16384 tokens)" in `error.message` on all of them; the detail may be cut
    at 500 chars, so the regex is the fallback."""
    try:
        err = json.loads(detail).get("error") or {}
        if err.get("n_ctx"):
            return int(err["n_ctx"])
    except Exception:  # noqa: BLE001 — not JSON, or cut short
        pass
    m = _CTX_IN_ERROR_RE.search(detail or "")
    return int(m.group(1)) if m else None


def first_turn_advice(prompt_tokens: int, n_ctx: int | None, *,
                      estimated: bool = False, reserve: int = RESERVE) -> str:
    """What the overflow error says on a first turn (or whenever the
    instructions alone leave no room) in place of the later-turn "things to
    try": the two numbers, then the fix. Never /reset (the history is
    already empty) and never "disable skills" (every shipped skill ships
    off). Server-side English, like the neighbouring messages."""
    n = f"about {prompt_tokens:,}" if estimated else f"{prompt_tokens:,}"
    where = "open the model window (the model badge in the top bar)"
    if n_ctx and prompt_tokens + reserve <= n_ctx:
        # The instructions fit; this first message is what does not.
        return (f"enough's instructions are {n} tokens and this model's "
                f"window holds {n_ctx:,}, so this message is longer than the "
                f"room left beside them.\nsend it in shorter parts, or {where} "
                "and pick a larger context.")
    if n_ctx:
        lead = (f"enough's instructions alone are {n} tokens and this "
                f"model's window holds {n_ctx:,}, so not even a first "
                "message can fit.")
    else:
        lead = (f"enough's instructions alone are {n} tokens, more than this "
                "model's window leaves room for.")
    return (f"{lead}\n{where} and pick a larger context, or use the "
            "notice's button when it offers one.")


# ---------------------------------------------------------------------------
# The runner the server holds
# ---------------------------------------------------------------------------

def _registry_entry(cute: str | None) -> dict | None:
    if not cute:
        return None
    try:
        return _models._model_entry(_models.load_registry(), cute)
    except Exception:  # noqa: BLE001 — unknown model, unreadable registry
        return None


def _current_slot() -> str | None:
    try:
        return _models.load_state().get("current")
    except Exception:  # noqa: BLE001
        return None


class Preflight:
    """One project's preflight: a cached verdict and the background task
    that refreshes it.

    `schedule()` is the only trigger the server uses — from the supervisor's
    `on_ready` (launch, adopt, switch), at project open and on each page
    load. It never awaits: it starts a task, or asks a running one to go
    again when it is done (a prompt edited mid-run is measured on the rerun).
    """

    def __init__(self, *, llm_url: str, build_prompt: Callable[[], str],
                 supervisor: Any = None,
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.llm_url = llm_url.rstrip("/")
        self._build_prompt = build_prompt
        self._supervisor = supervisor
        self._transport = transport
        self._task: asyncio.Task[None] | None = None
        self._again = False
        #: idle | pending | done | failed | skipped
        self.state = "idle"
        self.result: dict[str, Any] | None = None
        self._key: tuple[Any, Any] | None = None

    # -- state ---------------------------------------------------------------

    def _model_key(self) -> tuple[Any, Any]:
        sup = self._supervisor
        if sup is None:
            return (None, None)
        return (getattr(sup, "current_cute", None), getattr(sup, "current_ctx", None))

    def invalidate(self) -> None:
        """Forget the verdict (a model or window switch is under way)."""
        self.result = None
        self._key = None
        self.state = "idle"

    def fields(self) -> dict[str, Any]:
        """The `/api/llm-status` additions. A verdict measured against a
        model or window that is no longer the live one reads as unknown."""
        r = self.result
        state = self.state
        if r is not None and self._supervisor is not None and self._key != self._model_key():
            r, state = None, "idle"
        r = r or {}
        return {
            "prompt_tokens": r.get("prompt_tokens"),
            "n_ctx": r.get("n_ctx"),
            "reserve": RESERVE,
            "fits": r.get("fits"),
            "suggest_ctx": r.get("suggest_ctx"),
            "fix": r.get("fix"),
            "fix_reason": r.get("fix_reason"),
            "preflight": state,
        }

    # -- running -------------------------------------------------------------

    def schedule(self, reason: str = "") -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        if _current_slot() == CLOUD_SLOT:
            self.invalidate()
            self.state = "skipped"
            return
        sup = self._supervisor
        if sup is not None and not getattr(sup, "ready", False):
            return              # its on_ready will call again
        if self._task is not None and not self._task.done():
            self._again = True
            return
        self._again = False
        self._task = loop.create_task(self._loop(reason))

    async def _loop(self, reason: str) -> None:
        while True:
            await self.run(reason)
            if not self._again:
                return
            self._again = False
            reason = "rerun"

    async def cancel(self) -> None:
        task = self._task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass

    async def run(self, reason: str = "") -> dict[str, Any] | None:
        """Measure once. Returns the verdict, or None when it is unknown
        (failure) or skipped (cloud). Never raises, except cancellation."""
        if _current_slot() == CLOUD_SLOT:
            self.invalidate()
            self.state = "skipped"
            return None
        key = self._model_key()
        cute = key[0]
        entry = _registry_entry(cute)
        supervised = self._supervisor is not None and entry is not None
        self.state = "pending"
        try:
            system_prompt = await asyncio.to_thread(self._build_prompt)
            async with httpx.AsyncClient(transport=self._transport) as client:
                tokens = await count_tokens(client, self.llm_url, system_prompt)
                n_ctx = await read_n_ctx(client, self.llm_url)
            result = evaluate(tokens, n_ctx, entry=entry, supervised=supervised)
        except asyncio.CancelledError:
            self.state = "idle"
            raise
        except Exception as e:  # noqa: BLE001 — unknown, never an error
            self.result = None
            self._key = None
            self.state = "failed"
            log.info("context preflight (%s): unknown — %s", reason or "run", e)
            return None
        if self._supervisor is not None and self._model_key() != key:
            # A switch landed while we measured; its own on_ready reruns.
            self.invalidate()
            return None
        self.result = result
        self._key = key
        self.state = "done"
        log.info(
            "context preflight (%s): instructions %d tokens + reserve %d vs "
            "window %d — %s",
            reason or "run", result["prompt_tokens"], RESERVE, result["n_ctx"],
            "fits" if result["fits"] else
            f"too small; fix={result['fix']} reason={result['fix_reason']} "
            f"suggest={result['suggest_ctx']}",
        )
        return result
