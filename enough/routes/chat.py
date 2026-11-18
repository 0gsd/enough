"""The chat: a turn (`/api/chat`), the event stream, reset, the update check, the broker, usage and the orchestrator settings.

Moved out of `enough/server.py`'s `create_app` in 0.8 (lane W2-SV), code unchanged: `build_router` is the old
factory's closure for this group, and the names it closed over come in on `ctx`."""

from __future__ import annotations

import asyncio
import datetime as dt
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

from .. import broker as _broker
from .. import cloud as _cloud
from .. import intro as _intro
from .. import models as _models
from .. import pal_tools as _pal
from .. import prompt as prompt_mod
from ..logger import ExchangeLog, log_exchange
from .common import AppContext
from ..server import (
    _current_ctx_size,
    _escape_html,
    _load_orchestrator_config,
    _reply_without_turn,
    _run_turn,
    _save_orchestrator_config,
    _system_bubble,
    _user_bubble,
    log,
)


def build_router(ctx: AppContext) -> APIRouter:
    router = APIRouter()
    preflight = ctx.preflight
    project_dir = ctx.project_dir
    session = ctx.session

    @router.post("/api/chat", response_class=HTMLResponse)
    async def api_chat(request: Request) -> HTMLResponse:
        form = await request.form()
        message = (form.get("message") or "").strip()
        if not message:
            return HTMLResponse("")
        # A council turn is streaming. Councils and the chat share one model
        # and one `generation_lock`, so starting the turn here would queue it
        # silently behind the council and answer minutes later, against a
        # question the user has long since stopped waiting on. Say so instead
        # — and keep their message on screen, so it is one copy-paste away
        # rather than gone.
        from .. import council as _council
        if _council.turn_in_flight():
            return await _reply_without_turn(
                session,
                f'<div class="msg user"><div class="role">user</div>'
                f'<div class="body">{_escape_html(message)}</div></div>'
                f'<div class="msg system"><div class="role">enough</div>'
                f'<div class="body">a council is speaking right now, and it '
                f'uses the same model this chat does. your message was not '
                f'sent — wait for the turn to finish (or press pause on the '
                f'council) and send it again. to say something to the council '
                f'itself, use the composer at the foot of the canvas.</div>'
                f'</div>'
            )
        # `/pal` (P8). Four outcomes, and only one of them starts a turn.
        # The order is the order of the things the user needs told: what is
        # shut before what is missing, and what is missing before what is
        # pointless.
        # The brief introduction (0.4.1): a whole-message match on a short,
        # explicit list (`intro.INTRO_PHRASES`, first message only; `/intro`
        # any time) is answered on the spot, with no model turn. Not while a
        # turn is running — the history is that turn's until it ends — so
        # then it simply goes to the model like any other message.
        if (not session.generation_lock.locked()
                and _intro.is_intro_request(message,
                                            conversation_empty=not session.history)):
            text = await asyncio.to_thread(_intro.text_for)
            if text:
                session.history.append({"role": "user", "content": message})
                session.history.append({"role": "assistant", "content": text})
                try:
                    log_exchange(session.project_dir,
                                 ExchangeLog(user=message, assistant=text, tool_calls=[]),
                                 now=dt.datetime.now())
                except Exception:  # noqa: BLE001
                    log.exception("failed to write session log")
                return await _reply_without_turn(
                    session, _user_bubble(message) + _intro.bubble(text, prompt_mod.chief_name()))
        asked = _pal.strip_command(message)
        pal = False
        note = ""
        typed = message   # what the user wrote; `message` becomes what is sent
        if asked is not None:
            gate = await asyncio.to_thread(_cloud.gate_status)
            if not gate["open"]:
                # No LLM turn at all: nothing to think about locally when
                # the thing being thought toward cannot be reached.
                return await _reply_without_turn(
                    session, _user_bubble(message) + _system_bubble(gate["denial"]))
            if not asked:
                return await _reply_without_turn(
                    session, _user_bubble(message) + _system_bubble(_pal.USAGE_HINT))
            try:
                active = await asyncio.to_thread(
                    lambda: _models.load_state().get("current"))
            except Exception:  # noqa: BLE001 — an unreadable state file is not a refusal
                active = None
            if active == "opro-api":
                note = _system_bubble(_pal.ALREADY_CLOUD_NOTE)
            else:
                pal = True
            message = asked
        # Fire-and-forget generation. The SSE stream delivers output.
        asyncio.create_task(_run_turn(session, message, pal=pal, log_user=typed))
        # Return an HTML fragment htmx will swap into the conversation:
        # the user's message bubble + an empty assistant bubble the SSE will fill.
        return HTMLResponse(
            _user_bubble(typed)
            + note
            + f'<div class="msg assistant pending" id="current-response">'
            f'<div class="role">{_escape_html(prompt_mod.chief_name())}</div>'
            f'<div class="body"></div>'
            f'<div class="tool-indicators"></div>'
            f'</div>'
        )

    @router.get("/api/pal/status")
    async def api_pal_status() -> dict[str, Any]:
        """Is `/pal` usable right now, and against which model.

        The composer's command hint asks this so it can grey itself out with
        the reason rather than offering a command that will only be refused.
        Same gate, same answer, one helper: `cloud.gate_status`."""
        gate = await asyncio.to_thread(_cloud.gate_status)
        return {"available": bool(gate["open"]),
                "reason": gate["reason"],
                "model_id": gate["model_id"]}

    @router.get("/api/stream")
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

    @router.get("/api/reset", response_class=HTMLResponse)
    async def api_reset() -> HTMLResponse:
        session.history.clear()
        session.last_usage = {}
        # The empty conversation is back, and its notice should judge the
        # prompt as it is now.
        if preflight is not None:
            preflight.schedule("reset")
        # Echo a usage event so the gauge zeroes out without waiting for
        # the user to send their first post-reset turn.
        await session.emit("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
        return HTMLResponse("")

    @router.get("/api/update-enough")
    async def api_update_enough() -> dict[str, Any]:
        """Pull in any missing default files (paradigms, policies,
        knowledge dirs) from ~/enough/defaults/ that this project's
        `rness/` is missing. Idempotent: safe to call when nothing's
        missing.

        Returns a JSON summary the JS slash-command handler renders
        inline as a system notice."""
        from ..skeleton import apply_drift, detect_drift
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

    @router.get("/api/broker", response_class=HTMLResponse)
    async def api_broker_toggles() -> HTMLResponse:
        """Render the broker pane's toggle list. Each row is a clickable
        button that POSTs to /api/broker/toggle and re-renders this same
        list via htmx. Grouped by tool so additions to the catalog stay
        readable as the list grows."""
        cfg = _broker.load_config()
        rows: list[str] = []
        last_group: str | None = None
        for t in _broker.TOGGLES:
            if t.group != last_group:
                heading = {
                    "general": "general",
                    "read_file": "read_file",
                    "write_file": "write_file",
                    "shell": "shell",
                    "fetch_url": "fetch_url",
                }.get(t.group, t.group)
                rows.append(
                    f'<div class="broker-group-head">{_escape_html(heading)}</div>'
                )
                last_group = t.group
            on = cfg.get(t.key, t.default)
            cls = "on" if on else "off"
            marker = "●" if on else "○"
            rows.append(
                f'<div class="broker-row {cls}" title="{_escape_html(t.description)}">'
                f'  <button class="broker-toggle" '
                f'    hx-post="/api/broker/toggle" '
                f'    hx-vals=\'{{"key": "{_escape_html(t.key)}"}}\' '
                f'    hx-target="#broker-toggles" hx-swap="innerHTML">'
                f'    {marker}'
                f'  </button>'
                f'  <div class="broker-meta">'
                f'    <div class="broker-label">{_escape_html(t.label)}</div>'
                f'    <div class="broker-desc">{_escape_html(t.description)}</div>'
                f'  </div>'
                f'</div>'
            )
        return HTMLResponse("".join(rows))

    @router.post("/api/broker/toggle", response_class=HTMLResponse)
    async def api_broker_toggle(request: Request) -> HTMLResponse:
        form = await request.form()
        key = (form.get("key") or "").strip()
        if not key:
            raise HTTPException(400, "missing key")
        valid = {t.key for t in _broker.TOGGLES}
        if key not in valid:
            raise HTTPException(400, f"unknown toggle: {key}")
        cfg = _broker.load_config()
        cfg[key] = not cfg.get(key, True)
        _broker.save_config(cfg)
        return await api_broker_toggles()  # type: ignore[return-value]

    @router.get("/api/broker/journal-path")
    async def api_broker_journal_path() -> dict[str, str]:
        """Return the relative path to today's broker journal, for the UI
        to open in the file preview pane. Creates the file (empty) if
        missing so the preview pane has something to load."""
        now = dt.datetime.now()
        rel = f"rness/knowledge/session-logs/{now:%Y-%m-%d}-broker.md"
        target = project_dir / rel
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                f"# broker journal — {now:%Y-%m-%d}\n\n"
                "_(no broker activity logged yet today)_\n",
                encoding="utf-8",
            )
        return {"path": rel}

    @router.get("/api/usage")
    async def api_usage() -> dict[str, Any]:
        """Latest token-usage snapshot for the gauge. Used on modal open
        and on page load — SSE pushes keep it live during a session."""
        return {
            **session.last_usage,
            "ctx": _current_ctx_size(session),
        }

    @router.get("/api/orchestrator")
    async def api_orchestrator_get() -> dict[str, Any]:
        """Current auto-reset config (auto_reset bool + threshold_pct int)."""
        return _load_orchestrator_config()

    @router.post("/api/orchestrator")
    async def api_orchestrator_post(request: Request) -> dict[str, Any]:
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "expected json body") from None
        return _save_orchestrator_config(body or {})

    return router
