"""FastAPI app: UI + chat (with SSE streaming) + file-tree + preview.

Architecture
------------

- One `Session` per server process. v0.01 is localhost-only, single-user.
- The browser opens a persistent SSE connection to `/api/stream`. Every chunk
  the model generates — plus tool-call indicators — goes onto a per-session
  event queue, and the SSE coroutine drains it.
- POSTing to `/api/chat` appends a user message to the in-memory history and
  kicks off a generation task. The task streams from llama-server, watches for
  complete `<tool name="...">...</tool>` blocks, executes them, loops.
- Tool iterations are capped at 10 per user turn (per spec).
- System prompt is re-assembled from `rness/` on every user turn (no cache).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from . import __version__
from .llm import LLMError, stream_chat
from .logger import ExchangeLog, log_exchange
from .prompt import (
    assemble_system_prompt,
    get_active_paradigm,
    list_paradigms,
    list_roles,
    list_skills,
    set_active_paradigm,
    set_role_enabled,
    set_skill_enabled,
)
from .supervisor import LlamaSupervisor
from .tools import (
    ToolCall,
    execute,
    first_tool_call_end,
    parse_tool_calls,
)

log = logging.getLogger("enough")

STATIC_DIR = Path(__file__).parent / "static"
INSTALL_ROOT = Path(__file__).resolve().parents[1]
UI_CONFIG_TEMPLATE = INSTALL_ROOT / "defaults" / "ui-config.json"
UI_CONFIG_LIVE = Path.home() / "enough" / "config" / "ui.json"

WHISPER_DIR = Path.home() / "enough" / "weights" / "whisper"
WHISPER_DEFAULT_MODEL = "ggml-base.en.bin"

ORCHESTRATOR_CONFIG = Path.home() / "enough" / "config" / "orchestrator.json"
# Defaults are intentionally conservative: auto-reset off until the user
# opts in. Threshold sits below the wall (max ~85%) to give the
# checkpoint write itself enough headroom to complete.
ORCHESTRATOR_DEFAULTS = {"auto_reset": False, "threshold_pct": 75}

IGNORE_DIRS = {
    "__pycache__", ".git", "node_modules", ".venv", "venv",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "dist", "build",
    ".llama-server",
}
DEFAULT_MAX_TOOL_ITERS = 50

# How long we'll wait between streamed tokens before assuming llama-server
# has wedged. Long enough to ride out big-prefill pauses on slow hardware,
# short enough that a stuck process surfaces instead of leaving the UI
# spinning forever. Hit the limit and the user gets a real error message,
# not silence.
LLM_STREAM_INACTIVITY_TIMEOUT = 180.0


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

@dataclass
class Session:
    project_dir: Path
    llm_url: str
    max_tool_iters: int = DEFAULT_MAX_TOOL_ITERS
    history: list[dict[str, str]] = field(default_factory=list)  # OpenAI format
    # One queue per connected EventSource. A single shared queue would cause
    # zombie connections (e.g. after a page reload before the server notices)
    # to race living ones and steal events. Per-subscriber fan-out avoids
    # that at the cost of N*payload-size memory — negligible for v0.02.
    subscribers: list[asyncio.Queue[dict[str, Any]]] = field(default_factory=list)
    generation_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    client: httpx.AsyncClient | None = None
    # Most recent llama-server usage report. Populated after every
    # stream_chat call; powers the token-pressure gauge in the UI.
    # Keys: prompt_tokens, completion_tokens, total_tokens, ctx (snapshot
    # of the live ctx-size at the time the usage was recorded).
    last_usage: dict[str, int] = field(default_factory=dict)
    supervisor: Any = None  # LlamaSupervisor; stays Any to avoid forward-ref churn

    async def emit(self, event: str, data: Any) -> None:
        payload = {"event": event, "data": json.dumps(data)}
        for q in list(self.subscribers):  # snapshot — subscribers may unregister mid-iter
            await q.put(payload)


# ---------------------------------------------------------------------------
# File tree
# ---------------------------------------------------------------------------

def _walk_tree(
    root: Path,
    rel_parts: tuple[str, ...],
    visited: frozenset[Path],
) -> list[dict[str, Any]]:
    """Walk the project tree to arbitrary depth, with symlink-cycle protection.

    `visited` carries the set of canonical paths already in the current
    recursion chain. We snapshot it as we descend so sibling branches stay
    independent — if `infoworld/` and `rness/skills/` both happen to point
    into `~/enough/`, walking one doesn't poison the other."""
    abs_dir = root.joinpath(*rel_parts)
    try:
        real = abs_dir.resolve()
    except OSError:
        return []
    if real in visited:
        return []
    visited = visited | {real}
    try:
        entries = sorted(abs_dir.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for p in entries:
        if p.name.startswith("."):
            continue
        if p.name in IGNORE_DIRS:
            continue
        rel = "/".join(rel_parts + (p.name,))
        node = {
            "name": p.name,
            "path": rel,
            "is_dir": p.is_dir(),
            "is_symlink": p.is_symlink(),
        }
        if p.is_dir():
            node["children"] = _walk_tree(root, rel_parts + (p.name,), visited)
        out.append(node)
    return out


def build_file_tree(root: Path) -> list[dict[str, Any]]:
    return _walk_tree(root, (), frozenset())


# Paths in the project tree that get a [?] help affordance on hover.
# IDs match the keys in HELP_DOCS in static/index.html.
_HELP_IDS: dict[str, str] = {
    "rness": "rness",
    "rness/AGENT.md": "agent-md",
    "rness/MOTIVATION.md": "motivation-md",
    "rness/paradigms": "paradigms",
    "rness/policies": "policies",
    "rness/knowledge": "knowledge",
    "rness/io": "io",
    "infoworld": "infoworld",
}


def _tree_to_html(nodes: list[dict[str, Any]]) -> str:
    out = ['<ul class="tree">']
    for n in nodes:
        path = n["path"].replace('"', "&quot;")
        sym_cls = " symlink" if n.get("is_symlink") else ""
        help_id = _HELP_IDS.get(n["path"])
        help_attr = f' data-help="{help_id}"' if help_id else ""
        if n["is_dir"]:
            has_kids = bool(n.get("children"))
            dir_state_cls = " has-children" if has_kids else " empty-folder"
            # Zippy glyph: ▾ (expanded, default) if has children; nothing if empty.
            zippy = '<span class="zippy">▾</span>' if has_kids else '<span class="zippy-spacer"></span>'
            out.append(
                f'<li class="dir{sym_cls}{dir_state_cls}" data-path="{path}">'
                f'<span class="dir-row"{help_attr}>{zippy}<span class="dir-name">{n["name"]}/</span></span>'
            )
            if has_kids:
                out.append(_tree_to_html(n["children"]))
            out.append("</li>")
        else:
            out.append(
                f'<li class="file{sym_cls}">'
                f'<span class="file-row"{help_attr}><span class="zippy-spacer"></span>'
                f'<a href="#" '
                f'hx-get="/api/file?path={path}" hx-target="#preview-body" '
                f'hx-swap="innerHTML" '
                f'onclick="document.getElementById(\'preview\').classList.add(\'open\')"'
                f'>{n["name"]}</a></span></li>'
            )
    out.append("</ul>")
    return "".join(out)


# ---------------------------------------------------------------------------
# Chat generation
# ---------------------------------------------------------------------------

def _load_orchestrator_config() -> dict[str, Any]:
    """Read the orchestrator config (auto-reset toggle + threshold). Falls
    back to defaults for missing keys; never raises."""
    try:
        cfg = json.loads(ORCHESTRATOR_CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        cfg = {}
    out = dict(ORCHESTRATOR_DEFAULTS)
    if isinstance(cfg, dict):
        if isinstance(cfg.get("auto_reset"), bool):
            out["auto_reset"] = cfg["auto_reset"]
        # Clamp threshold to a sane range so a typo can't make the gauge
        # unreachable (1) or fire trivially (0).
        try:
            t = int(cfg.get("threshold_pct", out["threshold_pct"]))
            out["threshold_pct"] = max(40, min(95, t))
        except (TypeError, ValueError):
            pass
    return out


def _save_orchestrator_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Persist a sanitized orchestrator config and return the saved view."""
    current = _load_orchestrator_config()
    if "auto_reset" in cfg and isinstance(cfg["auto_reset"], bool):
        current["auto_reset"] = cfg["auto_reset"]
    if "threshold_pct" in cfg:
        try:
            current["threshold_pct"] = max(40, min(95, int(cfg["threshold_pct"])))
        except (TypeError, ValueError):
            pass
    ORCHESTRATOR_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    ORCHESTRATOR_CONFIG.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    return current


def _estimate_total_tokens(session: "Session", system_prompt: str) -> int:
    """Char-based token estimate, used when llama-server didn't ship a
    `usage` payload on the stream (older llama.cpp builds, pre-stream
    errors, etc.). Conservative ratio (~3 chars/token, slightly under
    the typical English norm) so we err toward triggering auto-reset
    earlier rather than later — better to pause one turn early than to
    overflow the context window mid-job."""
    chars = len(system_prompt or "")
    for msg in session.history:
        chars += len(msg.get("content", "") or "")
    return chars // 3


def _pressure_pct(session: "Session", system_prompt: str) -> int:
    """Best-effort context-window pressure as an integer percentage.
    Prefers the most recent llama-server usage report; falls back to
    `_estimate_total_tokens` when usage data isn't available. Returns 0
    if we can't even determine the ctx-size (e.g. external llama-server
    in --no-supervise mode where current_ctx is None)."""
    ctx = _current_ctx_size(session) or session.last_usage.get("ctx")
    if not ctx:
        return 0
    total = session.last_usage.get("total_tokens") or 0
    if not total:
        total = _estimate_total_tokens(session, system_prompt)
    return min(100, int((total / ctx) * 100))


def _should_auto_reset(session: "Session", system_prompt: str) -> bool:
    """Decide whether to fire auto-reset based on live config + current
    pressure. Pressure prefers real usage but falls back to a char-count
    estimate so that older llama.cpp builds (which may not ship `usage`
    on the stream) don't silently disable the safety net."""
    cfg = _load_orchestrator_config()
    if not cfg["auto_reset"]:
        return False
    return _pressure_pct(session, system_prompt) >= cfg["threshold_pct"]


def _current_ctx_size(session: "Session") -> int | None:
    """Best-effort lookup of llama-server's current ctx-size, used to scale
    the token-pressure gauge. Returns None if we can't determine it (no
    supervisor, server still booting); the gauge then renders absolute
    counts only."""
    sup = session.supervisor
    if sup is None:
        return None
    ctx = getattr(sup, "current_ctx", None)
    return int(ctx) if ctx else None


def _render_turn_from_history(history: list[dict[str, str]]) -> str:
    """Render the saved history as HTML for initial page load."""
    out: list[str] = []
    for msg in history:
        role = msg.get("role")
        text = msg.get("content", "") or ""
        if role == "user":
            # Strip tool_result wrappers for display
            if text.lstrip().startswith("<tool_result"):
                continue
            out.append(f'<div class="msg user"><div class="role">user</div>'
                       f'<div class="body">{_escape_html(text)}</div></div>')
        elif role == "assistant":
            out.append(f'<div class="msg assistant"><div class="role">agent</div>'
                       f'<div class="body">{_escape_html(text)}</div></div>')
    return "".join(out)


def _escape_html(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )


# ---------------------------------------------------------------------------
# Empty-hint rendering
# ---------------------------------------------------------------------------
#
# The empty-state pane (shown when the conversation is empty) is the
# right place to surface launch-time information the user actually needs
# to see — e.g. "new defaults are available, type /update-enough to
# apply". Terminal output is too easy to miss; an inline banner that
# tracks server state isn't.
#
# Each branch returns HTML for the contents of `<div id="empty-hint">`.
# The default branch keeps the original italic-faint hint; "notice"
# branches use the `.empty-hint--notice` class for bright, structured
# rendering. Add new branches as new launch states emerge (first-launch
# onboarding, model-not-running advisory, etc.).

_DEFAULT_EMPTY_HINT = (
    '<div class="empty-hint" id="empty-hint">'
    'awaiting your first message.<br>'
    'say hi, or ask me what i can do.'
    '</div>'
)


def _render_empty_hint(project_dir: Path) -> str:
    """Return the HTML for the empty-conversation pane. Picks the most
    salient state-aware notice if any apply; otherwise falls back to the
    default 'awaiting your first message' italic hint."""
    # Drift: ~/enough/defaults/ has shared defaults this rness/ is
    # missing. Surface them prominently with the /update-enough hook.
    from .skeleton import detect_drift
    missing = detect_drift(project_dir)
    if missing:
        n = len(missing)
        items = "".join(
            f'<li>{_escape_html(dst)}</li>'
            for (_src, dst, _mode) in missing
        )
        return (
            '<div class="empty-hint empty-hint--notice" id="empty-hint">'
            f'<div class="notice-title">'
            f'{n} new default{"s" if n != 1 else ""} '
            f'available from <code>~/enough/defaults/</code>'
            '</div>'
            f'<ul class="notice-list">{items}</ul>'
            '<div class="notice-cta">'
            'type <code>/update-enough</code> in the chat box to apply, '
            'or ignore.'
            '</div>'
            '</div>'
        )

    return _DEFAULT_EMPTY_HINT


# ---------------------------------------------------------------------------
# UI config (themes / fonts / zoom)
# ---------------------------------------------------------------------------

def _load_ui_config_template() -> dict[str, Any]:
    """Fallback config for when neither the live file nor the shipped
    template exists. Keeps the server usable in broken setups."""
    return {
        "current": {"theme": "enough-default", "font": "mono"},
        "fonts": {"mono": {"label": "Monospace", "stack": "ui-monospace, monospace"}},
        "themes": {"enough-default": {"label": "Enough Default", "colors": {}}},
    }


def _ensure_live_ui_config() -> Path:
    """Make sure ~/enough/config/ui.json exists. Seeds from the shipped
    template on first run; otherwise leaves it alone. Returns the path."""
    if not UI_CONFIG_LIVE.exists():
        UI_CONFIG_LIVE.parent.mkdir(parents=True, exist_ok=True)
        if UI_CONFIG_TEMPLATE.is_file():
            UI_CONFIG_LIVE.write_text(
                UI_CONFIG_TEMPLATE.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        else:
            UI_CONFIG_LIVE.write_text(
                json.dumps(_load_ui_config_template(), indent=2),
                encoding="utf-8",
            )
    return UI_CONFIG_LIVE


def _read_ui_config() -> dict[str, Any]:
    path = _ensure_live_ui_config()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        log.exception("failed to read live ui config; falling back to template")
        if UI_CONFIG_TEMPLATE.is_file():
            try:
                return json.loads(UI_CONFIG_TEMPLATE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return _load_ui_config_template()


def _write_ui_config(cfg: dict[str, Any]) -> None:
    path = _ensure_live_ui_config()
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")


def _validate_current(cfg: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any]:
    """Validate a proposed {theme, font} against the available options in
    `cfg`. Returns a sanitized dict — falls back to existing values for
    any unknown entries. Unknown keys in `selection` are silently ignored
    (e.g. legacy 'zoom' field from pre-0.0.5 configs — we just drop it)."""
    current = dict(cfg.get("current") or {})
    # Strip any legacy fields so they don't stick around in the saved file.
    current.pop("zoom", None)
    themes = cfg.get("themes") or {}
    fonts = cfg.get("fonts") or {}
    if "theme" in selection:
        t = str(selection["theme"])
        if t in themes:
            current["theme"] = t
    if "font" in selection:
        f = str(selection["font"])
        if f in fonts:
            current["font"] = f
    return current


CHECKPOINT_PROMPT = (
    "[harness] context window is approaching the auto-reset threshold. "
    "Before we lose continuity, do this in one short response:\n"
    "1. Run `ls rness/requests/*.md` to find your active request file (if any).\n"
    "2. If one exists, update its 'Continuation' section now: what you just "
    "did, what to do next, and any file paths or state the next turn must "
    "know about.\n"
    "3. End with a one-sentence summary of where things stand.\n"
    "Keep this whole reply under ~250 tokens. The conversation will be "
    "reset immediately after."
)

CONTINUE_PROMPT = (
    "[harness] the conversation has been reset to free up context. Resume the "
    "active work: list `rness/requests/*.md`, read the most recent one's "
    "Continuation section, and pick up from there."
)


async def _drive_message(
    session: Session,
    user_message: str,
    system_prompt: str,
    *,
    is_synthetic: bool = False,
    tool_calls_for_log: list[tuple[str, str]] | None = None,
    assistant_text_for_log: list[str] | None = None,
) -> None:
    """Drive a single user message through the LLM tool loop.

    Pulls the existing per-turn semantics out of `_run_turn` so synthetic
    messages (auto-reset checkpoint + continue) can reuse them without
    re-implementing the streaming, tool dispatch, and usage capture.

    Synthetic messages emit a `system_prompt` event (for the harness-driven
    user-side bubble) instead of `user`, so the UI can render them in a
    distinct style and the user understands they didn't type that. The
    message text still goes onto session.history under the `user` role —
    that's how llama-server learns what was asked. Errors propagate; the
    caller frames them.
    """
    assert session.client is not None
    client = session.client

    session.history.append({"role": "user", "content": user_message})
    await session.emit(
        "system_prompt" if is_synthetic else "user",
        {"text": user_message},
    )

    for _iter in range(session.max_tool_iters):
        messages = [{"role": "system", "content": system_prompt}] + session.history
        await session.emit("turn_start", {})
        buffer = ""
        usage_sink: dict[str, int] = {}
        agen = stream_chat(
            session.llm_url, messages, client=client, usage_sink=usage_sink,
        )
        stopped_at_tool = False
        try:
            # Iterate by hand so we can apply a per-chunk inactivity
            # timeout. If llama-server stops emitting tokens (a real
            # symptom we've seen when the KV cache is over-pressured),
            # an `async for` would just hang and the UI would spin
            # forever with no error. wait_for() turns that silence
            # into a visible failure.
            while True:
                try:
                    chunk = await asyncio.wait_for(
                        agen.__anext__(),
                        timeout=LLM_STREAM_INACTIVITY_TIMEOUT,
                    )
                except StopAsyncIteration:
                    break
                buffer += chunk
                await session.emit("token", {"text": chunk})
                end = first_tool_call_end(buffer)
                if end is not None:
                    # Truncate assistant message to end of tool call, stop stream.
                    buffer = buffer[:end]
                    stopped_at_tool = True
                    await agen.aclose()
                    break
        finally:
            # Ensure the generator is closed on any exit path.
            await agen.aclose()

        # Record the assistant turn (possibly truncated at the tool call).
        session.history.append({"role": "assistant", "content": buffer})
        if assistant_text_for_log is not None:
            assistant_text_for_log.append(buffer)
        # Persist usage from this completion + emit a live update.
        # llama-server reports prompt + completion tokens; for the
        # gauge, total_tokens is what was actually loaded into the
        # KV cache, so it's the truest pressure signal.
        if usage_sink:
            ctx = _current_ctx_size(session)
            session.last_usage = {**usage_sink, "ctx": ctx} if ctx else dict(usage_sink)
            await session.emit("usage", session.last_usage)
        await session.emit("turn_end", {})

        if not stopped_at_tool:
            return  # natural end — no tool call

        calls = parse_tool_calls(buffer)
        if not calls:
            # Shouldn't happen — first_tool_call_end said yes but parse failed.
            return
        call = calls[-1]  # the call we stopped at
        await _handle_tool(session, call, tool_calls_for_log if tool_calls_for_log is not None else [])

        # Mid-turn pressure check. Auto-reset's end-of-turn check is no
        # help during long tool loops (the agent never voluntarily ends
        # the turn — it just keeps emitting more tool calls). So after
        # each tool result is appended to history, evaluate pressure
        # against the threshold and exit early if we're at/over it. The
        # caller (_run_turn) will then decide whether to fire auto-reset
        # or just end the turn quietly.
        cfg = _load_orchestrator_config()
        pct = _pressure_pct(session, system_prompt)
        if pct >= cfg["threshold_pct"]:
            if not cfg["auto_reset"]:
                # Auto-reset is OFF. _run_turn won't fire anything; the
                # turn just stops. Emit a heads-up so the user knows
                # why and what to do.
                await session.emit("system", {
                    "kind": "pressure_pause",
                    "message": (
                        f"context at {pct}% (threshold {cfg['threshold_pct']}%) "
                        "— pausing mid-turn to avoid overflowing the window. "
                        "send a follow-up message to continue, or enable "
                        "auto-reset in the model modal for hands-free "
                        "continuation on long jobs."
                    ),
                })
            return
    else:
        await session.emit(
            "error",
            {"message": f"tool loop cap ({session.max_tool_iters}) reached"},
        )


async def _do_auto_reset(session: Session, system_prompt: str) -> None:
    """Run the checkpoint → reset → continue sequence inside the active
    generation lock. Emits `system` events with progress so the UI can
    explain what just happened, and a `reset` event so the conversation
    pane clears between the checkpoint and continuation.

    Re-entry is blocked by `session._in_auto_reset` — without that flag,
    the synthetic continue turn could itself trip the threshold and
    recurse forever.
    """
    cfg = _load_orchestrator_config()
    pct = _pressure_pct(session, system_prompt)
    await session.emit(
        "system",
        {
            "kind": "auto_reset_starting",
            "message": f"context at {pct}% (threshold {cfg['threshold_pct']}%) — "
                       "writing a checkpoint, then resetting to keep going.",
        },
    )

    session._in_auto_reset = True
    try:
        # 1. Checkpoint turn — agent writes Continuation block to its
        #    active request file. We let the existing tool loop handle
        #    write_file via the agent's own response.
        await _drive_message(session, CHECKPOINT_PROMPT, system_prompt, is_synthetic=True)

        # 2. Hard reset of in-memory state. On-disk state (the request
        #    file the agent just updated) is what carries us over.
        session.history.clear()
        session.last_usage = {}
        await session.emit("reset", {"reason": "auto_reset"})
        await session.emit(
            "usage",
            {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )
        await session.emit(
            "system",
            {"kind": "auto_reset_continuing",
             "message": "reset complete — continuing from the checkpoint."},
        )

        # 3. Continue turn — agent reads the request file and resumes.
        await _drive_message(session, CONTINUE_PROMPT, system_prompt, is_synthetic=True)
    finally:
        session._in_auto_reset = False


async def _run_turn(session: Session, user_message: str) -> None:
    """Drive one user turn: send to LLM, handle tool loop, emit SSE events.

    Emits:
      - event: user           { "text": <user msg> }  (ack to all listeners)
      - event: system_prompt  { "text": <synthetic harness-driven prompt> }
      - event: system         { "kind": ..., "message": ... }  (auto-reset chrome)
      - event: turn_start     { }
      - event: token          { "text": <chunk> }
      - event: tool           { "name": ..., "key": ..., "ok": ... }
      - event: turn_end       { }
      - event: usage          { prompt_tokens, completion_tokens, total_tokens, ctx }
      - event: reset          { "reason": ... }
      - event: done           { }
      - event: error          { "message": ... }
    """
    async with session.generation_lock:
        # Re-assemble system prompt fresh per spec.
        system_prompt = assemble_system_prompt(session.project_dir)

        tool_calls_for_log: list[tuple[str, str]] = []
        assistant_text_for_log: list[str] = []

        try:
            await _drive_message(
                session,
                user_message,
                system_prompt,
                is_synthetic=False,
                tool_calls_for_log=tool_calls_for_log,
                assistant_text_for_log=assistant_text_for_log,
            )
            # Auto-reset only fires for real user turns (not when we're
            # already in the middle of one) and only when the threshold
            # is breached + the toggle is on.
            if not getattr(session, "_in_auto_reset", False) and _should_auto_reset(session, system_prompt):
                await _do_auto_reset(session, system_prompt)
        except asyncio.TimeoutError:
            await session.emit("error", {"message": (
                f"the model went silent for over "
                f"{int(LLM_STREAM_INACTIVITY_TIMEOUT)}s mid-stream.\n"
                "this usually means the context window filled up while "
                "generating and llama-server stalled. things to try:\n"
                "  • type `/reset` in the chat input to clear the "
                "conversation, then re-state the task more compactly\n"
                "  • open the model modal and enable auto-reset (or pick "
                "a larger ctx) — that's what it's for\n"
                "  • disable skills you aren't using in the sidebar to "
                "shrink the system prompt"
            )})
            log.warning("llm stream timed out after %ss of silence", LLM_STREAM_INACTIVITY_TIMEOUT)
        except LLMError as e:
            # llama-server returned a 4xx/5xx before the stream began —
            # detect context-window exhaustion and give concrete remedies.
            low = e.detail.lower()
            looks_like_overflow = any(
                k in low for k in ("context", "exceed", "n_ctx", "too many tokens", "token limit")
            )
            if looks_like_overflow:
                msg = (
                    f"context window full (llm {e.status}): {e.detail}\n"
                    "things to try:\n"
                    "  • type `/reset` in the chat input to clear the "
                    "conversation, then re-state the task more compactly\n"
                    "  • open the model modal and enable auto-reset (or "
                    "pick a larger ctx, or switch to a model that fits "
                    "more context)\n"
                    "  • disable skills you aren't using in the sidebar to "
                    "shrink the system prompt"
                )
            else:
                msg = f"llm {e.status}: {e.detail}"
            await session.emit("error", {"message": msg})
            log.exception("llm error")
        except httpx.HTTPError as e:
            await session.emit("error", {"message": f"llm transport error: {e}"})
            log.exception("llm error")
        except Exception as e:  # noqa: BLE001
            await session.emit("error", {"message": f"server error: {e}"})
            log.exception("generation error")
        finally:
            await session.emit("done", {})

        # Persist to session log.
        try:
            log_exchange(
                session.project_dir,
                ExchangeLog(
                    user=user_message,
                    assistant="\n\n".join(t.strip() for t in assistant_text_for_log if t.strip()),
                    tool_calls=tool_calls_for_log,
                ),
                now=dt.datetime.now(),
            )
        except Exception:  # noqa: BLE001
            log.exception("failed to write session log")


async def _handle_tool(session: Session, call: ToolCall, sink: list[tuple[str, str]]) -> None:
    key = call.path or call.command or ""
    await session.emit(
        "tool",
        {"name": call.name, "key": key, "status": "running"},
    )
    # Run blocking tool exec in a thread so we don't stall the event loop.
    result = await asyncio.to_thread(execute, session.project_dir, call)
    sink.append((call.name, key))
    await session.emit(
        "tool",
        {"name": call.name, "key": key, "status": "ok" if result.ok else "error"},
    )
    session.history.append({"role": "user", "content": result.render()})


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(
    project_dir: Path,
    llm_url: str,
    max_tool_iters: int = DEFAULT_MAX_TOOL_ITERS,
    *,
    supervise: bool = True,
) -> FastAPI:
    session = Session(project_dir=project_dir, llm_url=llm_url, max_tool_iters=max_tool_iters)
    supervisor = LlamaSupervisor(llm_url=llm_url) if supervise else None
    session.supervisor = supervisor  # so _run_turn can read current ctx for the usage gauge

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        session.client = httpx.AsyncClient()
        if supervisor is not None:
            try:
                await supervisor.bootstrap()
            except Exception:  # noqa: BLE001
                log.exception("supervisor bootstrap failed")
        try:
            yield
        finally:
            if supervisor is not None:
                await supervisor.stop(only_if_owned=True)
            await session.client.aclose()

    app = FastAPI(title="enough", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        # Render any existing history so a page refresh doesn't lose the transcript.
        html = html.replace(
            "<!-- HISTORY -->",
            _render_turn_from_history(session.history),
        )
        # State-aware empty-hint (drift notice, etc.). Empty-when-history-
        # exists semantics are still handled by the post-send htmx hook.
        html = html.replace(
            "<!-- EMPTY_HINT -->",
            _render_empty_hint(session.project_dir),
        )
        html = html.replace("<!-- VERSION -->", f"v{__version__}")
        # No-cache so edits-in-place don't require force-reload during dev.
        return HTMLResponse(html, headers={"Cache-Control": "no-store, must-revalidate"})

    @app.get("/api/files", response_class=HTMLResponse)
    async def api_files() -> HTMLResponse:
        tree = build_file_tree(project_dir)
        return HTMLResponse(_tree_to_html(tree))

    @app.get("/api/paradigm", response_class=HTMLResponse)
    async def api_paradigm() -> HTMLResponse:
        rness = project_dir / "rness"
        items = list_paradigms(rness)
        if not items:
            return HTMLResponse('<div class="empty-note">no paradigms in rness/paradigms/</div>')
        active = get_active_paradigm(rness)
        rows = []
        for name, desc in items:
            is_active = name == active
            cls = "on" if is_active else "off"
            marker = "●" if is_active else "○"
            tip = _escape_html(desc) if desc else ""
            rows.append(
                f'<li class="paradigm-row {cls}" title="{tip}">'
                f'  <button class="paradigm-toggle" '
                f'    hx-post="/api/paradigm/set" '
                f'    hx-vals=\'{{"name": "{_escape_html(name)}"}}\' '
                f'    hx-target="#paradigm-list" hx-swap="innerHTML">'
                f'    {marker}'
                f'  </button>'
                f'  <span class="paradigm-name">{_escape_html(name)}</span>'
                f'</li>'
            )
        return HTMLResponse('<ul class="paradigms">' + "".join(rows) + "</ul>")

    @app.post("/api/paradigm/set", response_class=HTMLResponse)
    async def api_paradigm_set(request: Request) -> HTMLResponse:
        form = await request.form()
        name = (form.get("name") or "").strip()
        if not name:
            raise HTTPException(400, "missing name")
        rness = project_dir / "rness"
        # Validate: only allow names that resolve to an existing paradigm file.
        valid_names = {n for n, _d in list_paradigms(rness)}
        if name not in valid_names:
            raise HTTPException(400, f"unknown paradigm: {name}")
        set_active_paradigm(rness, name)
        return await api_paradigm()  # type: ignore[return-value]

    @app.get("/api/skills", response_class=HTMLResponse)
    async def api_skills() -> HTMLResponse:
        items = list_skills(project_dir / "rness")
        if not items:
            return HTMLResponse('<div class="empty-note">no skills in rness/skills/</div>')
        rows = []
        for name, enabled in items:
            cls = "on" if enabled else "off"
            next_val = "0" if enabled else "1"
            rows.append(
                f'<li class="skill-row {cls}">'
                f'  <button class="skill-toggle" '
                f'    hx-post="/api/skills/toggle" '
                f'    hx-vals=\'{{"name": "{_escape_html(name)}", "enabled": "{next_val}"}}\' '
                f'    hx-target="#skills-list" hx-swap="innerHTML">'
                f'    {"●" if enabled else "○"}'
                f'  </button>'
                f'  <span class="skill-name">{_escape_html(name)}</span>'
                f'</li>'
            )
        return HTMLResponse('<ul class="skills">' + "".join(rows) + "</ul>")

    @app.post("/api/skills/toggle", response_class=HTMLResponse)
    async def api_skills_toggle(request: Request) -> HTMLResponse:
        form = await request.form()
        name = (form.get("name") or "").strip()
        enabled_raw = (form.get("enabled") or "").strip()
        if not name:
            raise HTTPException(400, "missing name")
        set_skill_enabled(project_dir / "rness", name, enabled_raw == "1")
        return await api_skills()  # type: ignore[return-value]

    @app.get("/api/roles", response_class=HTMLResponse)
    async def api_roles() -> HTMLResponse:
        items = list_roles(project_dir / "rness")
        if not items:
            return HTMLResponse('<div class="empty-note">no roles in rness/roles/</div>')
        rows = []
        for name, enabled in items:
            cls = "on" if enabled else "off"
            next_val = "0" if enabled else "1"
            rows.append(
                f'<li class="role-row {cls}">'
                f'  <button class="role-toggle" '
                f'    hx-post="/api/roles/toggle" '
                f'    hx-vals=\'{{"name": "{_escape_html(name)}", "enabled": "{next_val}"}}\' '
                f'    hx-target="#roles-list" hx-swap="innerHTML">'
                f'    {"●" if enabled else "○"}'
                f'  </button>'
                f'  <span class="role-name">{_escape_html(name)}</span>'
                f'</li>'
            )
        return HTMLResponse('<ul class="roles">' + "".join(rows) + "</ul>")

    @app.post("/api/roles/toggle", response_class=HTMLResponse)
    async def api_roles_toggle(request: Request) -> HTMLResponse:
        form = await request.form()
        name = (form.get("name") or "").strip()
        enabled_raw = (form.get("enabled") or "").strip()
        if not name:
            raise HTTPException(400, "missing name")
        set_role_enabled(project_dir / "rness", name, enabled_raw == "1")
        return await api_roles()  # type: ignore[return-value]

    @app.get("/api/requests", response_class=HTMLResponse)
    async def api_requests() -> HTMLResponse:
        rdir = project_dir / "rness" / "requests"
        if not rdir.is_dir():
            return HTMLResponse('<div class="empty-note">no rness/requests/ yet</div>')
        active = sorted(
            (p for p in rdir.glob("*.md") if p.is_file()),
            key=lambda p: p.name,
            reverse=True,  # newest first (YYYY-MM-DD_HH-MM sorts chronologically)
        )
        if not active:
            return HTMLResponse('<div class="empty-note">no active requests</div>')
        rows = []
        for p in active:
            rel = f"rness/requests/{p.name}"
            label = _escape_html(p.stem)
            rows.append(
                f'<li class="request-row">'
                f'  <a href="#" '
                f'    hx-get="/api/file?path={_escape_html(rel)}" '
                f'    hx-target="#preview-body" hx-swap="innerHTML" '
                f'    onclick="document.getElementById(\'preview\').classList.add(\'open\')">'
                f'    {label}'
                f'  </a>'
                f'</li>'
            )
        return HTMLResponse('<ul class="requests">' + "".join(rows) + "</ul>")

    @app.post("/api/requests/done", response_class=HTMLResponse)
    async def api_requests_done(request: Request) -> HTMLResponse:
        form = await request.form()
        path = (form.get("path") or "").strip()
        if not path:
            raise HTTPException(400, "missing path")
        if not _is_request_file(path):
            raise HTTPException(400, "not an active request file")
        target = _resolve_project_path(path)
        if not target.is_file():
            raise HTTPException(404, "not found")
        done_dir = project_dir / "rness" / "requests" / "done"
        done_dir.mkdir(parents=True, exist_ok=True)
        dest = done_dir / target.name
        # If a file with the same name already exists in done/, disambiguate.
        if dest.exists():
            dest = done_dir / (target.stem + "_dup.md")
        target.rename(dest)
        # Return the new requests list so htmx can refresh the sidebar.
        return await api_requests()  # type: ignore[return-value]

    def _resolve_project_path(path: str) -> Path:
        """Shared path-safety helper for /api/file{,/raw} and POST writes.

        Containment check is done on the LOGICAL path (composition) so that
        symlinks living at a valid relative location inside rness/ and
        pointing outside the project — intentional, used for global
        defaults — aren't rejected. The tool layer has its own allowlist
        for follow-through reads; this helper guards only against path-
        string traversal (absolute paths and `..` components)."""
        p = Path(path)
        if p.is_absolute() or ".." in p.parts:
            raise HTTPException(400, "invalid path")
        # Compose against the resolved project root so we don't end up with
        # /tmp-vs-/private/tmp mismatches on macOS. Don't resolve the final
        # target — that would follow symlinks and break containment checks
        # for in-tree symlinks.
        project_root = project_dir.resolve()
        return project_root / p

    def _is_request_file(path: str) -> bool:
        p = Path(path)
        parts = p.parts
        # Active request = directly under rness/requests/ (not /done/).
        return (
            len(parts) >= 3
            and parts[0] == "rness"
            and parts[1] == "requests"
            and parts[2] != "done"
            and parts[-1].endswith(".md")
        )

    def _is_skill_file(path: str) -> bool:
        parts = Path(path).parts
        return len(parts) >= 2 and parts[0] == "rness" and parts[1] == "skills"

    def _is_role_file(path: str) -> bool:
        parts = Path(path).parts
        return len(parts) >= 2 and parts[0] == "rness" and parts[1] == "roles"

    def _is_external_symlink(path_str: str) -> tuple[bool, Path | None]:
        """Is `path` a symlink whose resolved target lives outside the project?
        Returns (yes_external, target_abs) for the truthy case."""
        raw = project_dir / path_str
        if not raw.is_symlink():
            return False, None
        target = raw.resolve(strict=False)
        try:
            target.relative_to(project_dir.resolve())
            return False, target  # resolves inside the project — treat as normal
        except ValueError:
            return True, target

    @app.get("/api/file", response_class=HTMLResponse)
    async def api_file(path: str = Query(...)) -> HTMLResponse:
        target = _resolve_project_path(path)
        if not target.exists():
            raise HTTPException(404, "not found")
        if target.is_dir():
            raise HTTPException(400, "is a directory")
        try:
            text = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return HTMLResponse(
                f'<div class="binary-file">binary file — {target.stat().st_size} bytes</div>'
            )
        # Preview chrome: path header, body, and context-sensitive action buttons.
        external, sym_target = _is_external_symlink(path)
        mark_done_btn = (
            f'<button class="mark-done" onclick="markRequestDone(\'{_escape_html(path)}\')">mark done</button>'
            if _is_request_file(path)
            else ""
        )
        if _is_skill_file(path):
            # Skills are global. No in-UI edit or customize — edit at the
            # source under ~/enough/defaults/skills/<name>/ instead.
            sym_note = (
                '<div class="symlink-note">'
                'skill file — edit globally at '
                '<code>~/enough/defaults/skills/</code>; '
                'toggle on/off for this project in the sidebar.'
                '</div>'
            )
            action_btn = ""
        elif _is_role_file(path):
            # Same pattern as skills — roles are global, edited at source.
            sym_note = (
                '<div class="symlink-note">'
                'role file — edit globally at '
                '<code>~/enough/defaults/roles/</code>; '
                'toggle on/off for this project in the sidebar.'
                '</div>'
            )
            action_btn = ""
        elif external:
            sym_note = (
                f'<div class="symlink-note">symlink → '
                f'<code>{_escape_html(str(sym_target))}</code></div>'
            )
            action_btn = (
                f'<button class="customize-btn" '
                f'onclick="customizeForProject(\'{_escape_html(path)}\')">'
                f'customize for this project</button>'
            )
        else:
            sym_note = ""
            action_btn = (
                '<button class="edit-btn" onclick="enterEditMode()">edit</button>'
            )
        return HTMLResponse(
            f'<div class="file-path" data-path="{_escape_html(path)}">{_escape_html(path)}</div>'
            f'{sym_note}'
            f'<div class="preview-actions">'
            f'  {mark_done_btn}'
            f'  {action_btn}'
            f'</div>'
            f'<pre class="file-body">{_escape_html(text)}</pre>'
        )

    @app.post("/api/file/customize", response_class=HTMLResponse)
    async def api_file_customize(request: Request) -> HTMLResponse:
        form = await request.form()
        path = (form.get("path") or "").strip()
        if not path:
            raise HTTPException(400, "missing path")
        raw = project_dir / path
        if not raw.is_symlink():
            raise HTTPException(400, "not a symlink — nothing to customize")
        external, sym_target = _is_external_symlink(path)
        if not external or sym_target is None:
            raise HTTPException(400, "symlink resolves inside the project")
        # Read the current target content, drop the symlink, write a copy.
        try:
            content = sym_target.read_text(encoding="utf-8")
        except OSError as e:
            raise HTTPException(500, f"could not read symlink target: {e}") from None
        try:
            raw.unlink()
        except OSError as e:
            raise HTTPException(500, f"could not remove symlink: {e}") from None
        raw.write_text(content, encoding="utf-8")
        # Return the refreshed preview fragment (now editable).
        return await api_file(path=path)  # type: ignore[return-value]

    @app.get("/api/file/raw", response_class=PlainTextResponse)
    async def api_file_raw(path: str = Query(...)) -> PlainTextResponse:
        target = _resolve_project_path(path)
        if not target.exists():
            raise HTTPException(404, "not found")
        if target.is_dir():
            raise HTTPException(400, "is a directory")
        try:
            text = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise HTTPException(415, "not utf-8 text") from None
        return PlainTextResponse(text)

    @app.post("/api/file", response_class=HTMLResponse)
    async def api_file_write(request: Request) -> HTMLResponse:
        form = await request.form()
        path = (form.get("path") or "").strip()
        content = form.get("content")
        if content is None:
            raise HTTPException(400, "missing content")
        if not path:
            raise HTTPException(400, "missing path")
        if _is_skill_file(path):
            raise HTTPException(
                403,
                "skill files are not editable from the project UI — "
                "edit globally at ~/enough/defaults/skills/",
            )
        if _is_role_file(path):
            raise HTTPException(
                403,
                "role files are not editable from the project UI — "
                "edit globally at ~/enough/defaults/roles/",
            )
        target = _resolve_project_path(path)
        if target.is_dir():
            raise HTTPException(400, "is a directory")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(content), encoding="utf-8")
        # Return the re-rendered preview fragment so the UI can swap it in.
        return await api_file(path=path)  # type: ignore[return-value]

    @app.post("/api/chat", response_class=HTMLResponse)
    async def api_chat(request: Request) -> HTMLResponse:
        form = await request.form()
        message = (form.get("message") or "").strip()
        if not message:
            return HTMLResponse("")
        # Fire-and-forget generation. The SSE stream delivers output.
        asyncio.create_task(_run_turn(session, message))
        # Return an HTML fragment htmx will swap into the conversation:
        # the user's message bubble + an empty assistant bubble the SSE will fill.
        return HTMLResponse(
            f'<div class="msg user"><div class="role">user</div>'
            f'<div class="body">{_escape_html(message)}</div></div>'
            f'<div class="msg assistant pending" id="current-response">'
            f'<div class="role">agent</div>'
            f'<div class="body"></div>'
            f'<div class="tool-indicators"></div>'
            f'</div>'
        )

    @app.get("/api/stream")
    async def api_stream(request: Request):
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        session.subscribers.append(q)

        async def event_gen():
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        item = await asyncio.wait_for(q.get(), timeout=15.0)
                        yield item
                    except asyncio.TimeoutError:
                        # Heartbeat so proxies don't close the connection.
                        yield {"event": "ping", "data": "{}"}
            finally:
                try:
                    session.subscribers.remove(q)
                except ValueError:
                    pass

        return EventSourceResponse(event_gen())

    @app.get("/api/reset", response_class=HTMLResponse)
    async def api_reset() -> HTMLResponse:
        session.history.clear()
        session.last_usage = {}
        # Echo a usage event so the gauge zeroes out without waiting for
        # the user to send their first post-reset turn.
        await session.emit("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
        return HTMLResponse("")

    @app.get("/api/update-enough")
    async def api_update_enough() -> dict[str, Any]:
        """Pull in any missing default files (paradigms, policies,
        knowledge dirs) from ~/enough/defaults/ that this project's
        `rness/` is missing. Idempotent: safe to call when nothing's
        missing.

        Returns a JSON summary the JS slash-command handler renders
        inline as a system notice."""
        from .skeleton import apply_drift, detect_drift
        # Detect first so we have a "what changed" view independent of
        # the apply step. The two should match in normal flow.
        before = detect_drift(session.project_dir)
        applied = apply_drift(session.project_dir)
        return {
            "applied": [
                {"src": src, "dst": dst, "mode": mode}
                for (src, dst, mode) in applied
            ],
            "remaining": [
                {"src": src, "dst": dst, "mode": mode}
                for (src, dst, mode) in detect_drift(session.project_dir)
            ],
            "had_drift": bool(before),
        }

    @app.get("/api/usage")
    async def api_usage() -> dict[str, Any]:
        """Latest token-usage snapshot for the gauge. Used on modal open
        and on page load — SSE pushes keep it live during a session."""
        return {
            **session.last_usage,
            "ctx": _current_ctx_size(session),
        }

    @app.get("/api/orchestrator")
    async def api_orchestrator_get() -> dict[str, Any]:
        """Current auto-reset config (auto_reset bool + threshold_pct int)."""
        return _load_orchestrator_config()

    @app.post("/api/orchestrator")
    async def api_orchestrator_post(request: Request) -> dict[str, Any]:
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "expected json body") from None
        return _save_orchestrator_config(body or {})

    @app.get("/api/ui-config")
    async def api_ui_config_get() -> dict[str, Any]:
        return _read_ui_config()

    @app.post("/api/ui-config")
    async def api_ui_config_post(request: Request) -> dict[str, Any]:
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "expected json body") from None
        cfg = _read_ui_config()
        cfg["current"] = _validate_current(cfg, body or {})
        _write_ui_config(cfg)
        return cfg

    @app.get("/api/models")
    async def api_models() -> dict[str, Any]:
        """Registry + per-model installed/recommended view + total RAM +
        supervisor status."""
        from . import models as _models  # late import: avoid circular
        payload: dict[str, Any] = {
            "total_ram_gb": _models.total_ram_gb(),
            "current": _models.load_state().get("current"),
            "models": _models.all_models_view(),
            "ctx_overrides": _models.load_state().get("ctx_overrides") or {},
        }
        payload["supervisor"] = supervisor.status() if supervisor else {"mode": "off"}
        return payload

    @app.get("/api/llm-status")
    async def api_llm_status() -> dict[str, Any]:
        """Lightweight poll target for the UI: is llama-server alive, what
        model is loaded, ready-for-requests?"""
        if supervisor is None:
            # Non-supervised mode: best-effort probe of /health.
            try:
                async with httpx.AsyncClient(timeout=2.0) as c:
                    r = await c.get(llm_url.rstrip("/") + "/health")
                return {"mode": "external", "ready": r.status_code == 200, "cute": None, "ctx": None}
            except httpx.HTTPError:
                return {"mode": "external", "ready": False, "cute": None, "ctx": None}
        return supervisor.status()

    @app.post("/api/model")
    async def api_model_switch(request: Request) -> dict[str, Any]:
        """Swap the loaded model and/or ctx. Body: {"cute": "g40-04",
        "ctx": 16384 (optional)}. Returns supervisor status; the UI
        should poll /api/llm-status for readiness."""
        if supervisor is None:
            raise HTTPException(
                400,
                "llama-server isn't supervised by this enough process — "
                "restart enough without --no-supervise to enable switching.",
            )
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "expected json body") from None
        cute = (body or {}).get("cute")
        ctx = (body or {}).get("ctx")
        if not cute:
            raise HTTPException(400, "missing 'cute' field")
        try:
            await supervisor.switch(str(cute), int(ctx) if ctx is not None else None)
        except RuntimeError as e:
            raise HTTPException(400, str(e)) from None
        except Exception as e:  # noqa: BLE001
            raise HTTPException(500, f"switch failed: {e}") from None
        # Also clear in-memory conversation history — new model = fresh brain.
        session.history.clear()
        session.last_usage = {}
        await session.emit("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
        return supervisor.status()

    @app.post("/api/transcribe")
    async def api_transcribe(request: Request) -> dict[str, Any]:
        """Speech-to-text via whisper.cpp. Accepts a multipart/form-data POST
        with an 'audio' field containing a 16 kHz mono WAV blob. Returns
        {"text": "transcribed words"} on success."""
        import shutil as _shutil
        import subprocess as _sp
        import tempfile as _tempfile

        whisper_bin = _shutil.which("whisper-cli")
        if not whisper_bin:
            raise HTTPException(
                503,
                "whisper-cli not found on PATH. install it with `brew install whisper-cpp` "
                "or re-run bootstrap.sh.",
            )
        model_path = WHISPER_DIR / WHISPER_DEFAULT_MODEL
        if not model_path.is_file():
            raise HTTPException(
                503,
                f"whisper model not found at {model_path}. re-run bootstrap.sh step 7 "
                "to download it.",
            )

        form = await request.form()
        blob = form.get("audio")
        if blob is None or not hasattr(blob, "read"):
            raise HTTPException(400, "missing 'audio' file part")
        data = await blob.read()
        if not data:
            raise HTTPException(400, "empty audio upload")

        # whisper-cli needs a file on disk. Temp-file the upload, pipe through,
        # discard.
        with _tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(data)
            in_path = Path(f.name)
        try:
            proc = await asyncio.to_thread(
                _sp.run,
                [
                    whisper_bin,
                    "-m", str(model_path),
                    "-f", str(in_path),
                    "-nt",              # no timestamps in output
                    "--no-prints",      # suppress progress spam
                    "-l", "en",         # English (matches base.en)
                    "--output-txt",     # write .txt next to the wav
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if proc.returncode != 0:
                raise HTTPException(
                    500,
                    f"whisper-cli failed (code {proc.returncode}): "
                    f"{proc.stderr[-400:] if proc.stderr else 'no stderr'}",
                )
            # whisper-cli writes <basename>.wav.txt alongside the input.
            txt_path = in_path.with_suffix(".wav.txt")
            if txt_path.is_file():
                text = txt_path.read_text(encoding="utf-8").strip()
                txt_path.unlink(missing_ok=True)
            else:
                # Fallback: some builds print to stdout.
                text = (proc.stdout or "").strip()
            return {"text": text}
        finally:
            in_path.unlink(missing_ok=True)

    @app.get("/favicon.ico")
    async def favicon():
        f = STATIC_DIR / "favicon.ico"
        if f.exists():
            return FileResponse(f)
        return HTMLResponse("", status_code=204)

    return app


def run(
    *,
    project_dir: Path,
    port: int,
    llm_url: str,
    max_tool_iters: int = DEFAULT_MAX_TOOL_ITERS,
    supervise: bool = True,
) -> None:
    app = create_app(project_dir, llm_url, max_tool_iters=max_tool_iters, supervise=supervise)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
