"""The UI config (`/api/ui-config`), agent-free switching, and the chief readvisor (`/api/readvisor/chief`).

Moved out of `enough/server.py`'s `create_app` in 0.8 (lane W2-SV), code unchanged: `build_router` is the old
factory's closure for this group, and the names it closed over come in on `ctx`."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from .. import agent_free as _agent_free
from .. import prompt as prompt_mod
from .. import specs as _specs
from .common import AppContext
from ..server import UI_LANGUAGES, _read_ui_config, _validate_current, _write_ui_config, log


def build_router(ctx: AppContext) -> APIRouter:
    router = APIRouter()
    home = ctx.home
    preflight = ctx.preflight
    session = ctx.session
    supervisor = ctx.supervisor

    @router.get("/api/ui-config")
    async def api_ui_config_get() -> dict[str, Any]:
        return _read_ui_config()

    @router.post("/api/ui-config")
    async def api_ui_config_post(request: Request) -> dict[str, Any]:
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "expected json body") from None
        cfg = _read_ui_config()
        cfg["current"] = _validate_current(cfg, body or {})
        # The convert intro modal's "once per file type" flag (convert-plan
        # §1 decision 10) lives here — top-level, beside `current`, never
        # inside it (current is the theme/font *selection*). Union-merge so
        # two browser profiles can't un-see each other's types, and cap the
        # list so a hostile POST can't grow the config file unboundedly.
        seen = (body or {}).get("seen_convert_intro")
        if isinstance(seen, list):
            merged = list(dict.fromkeys(
                [*(cfg.get("seen_convert_intro") or []),
                 *(str(k).lstrip(".").lower() for k in seen
                   if isinstance(k, str) and k.strip())]))
            cfg["seen_convert_intro"] = merged[:32]
        # The home screen's icons/list choice (home-plan §4) — same top-level
        # round-trip as the flag above, and the same reason: the desktop
        # webview and a browser tab must agree. Two legal values, so an
        # unknown one is dropped rather than stored.
        view = (body or {}).get("home_view")
        if isinstance(view, str) and view in ("icons", "list"):
            cfg["home_view"] = view
        # The View-menu / home-screen "show hidden projects" toggle (§1.10).
        show_hidden = (body or {}).get("home_show_hidden")
        if isinstance(show_hidden, bool):
            cfg["home_show_hidden"] = show_hidden
        # The UI language (i18n round) — global like the theme, top-level
        # like the other flags. Whitelisted: an unknown code is dropped
        # rather than stored (same posture as home_view).
        lang = (body or {}).get("ui_language")
        if isinstance(lang, str) and lang in UI_LANGUAGES:
            cfg["ui_language"] = lang
        # The chief readvisor's name (P2) — global like the theme and the
        # language, and for the same reason: a user who renamed their chief
        # to "Mo" means Mo in every folder. Validated, not stored raw; an
        # unacceptable value is dropped rather than saved, matching the
        # posture above.
        chief = prompt_mod.valid_chief_name((body or {}).get("chief_readvisor_name"))
        if chief:
            cfg["chief_readvisor_name"] = chief
        # Agent-free mode (§13): machine-global, top-level like the language,
        # a bool or nothing. The model follows the switch once it is saved:
        # on stops it, off starts it through the ordinary startup choice.
        was_free = _agent_free.value(cfg)
        want_free = (body or {}).get(_agent_free.KEY)
        if isinstance(want_free, bool):
            cfg[_agent_free.KEY] = want_free
        # Keep the specifications current from cosmoes.org (0.5.4): machine-
        # global like the language, a bool or nothing; absent reads as on.
        # Takes effect at the next launch (the check runs once per launch).
        want_sync = (body or {}).get(_specs.PREF_KEY)
        if isinstance(want_sync, bool):
            cfg[_specs.PREF_KEY] = want_sync
        _write_ui_config(cfg)
        if isinstance(want_free, bool) and want_free != was_free:
            await _agent_free_switched(want_free)
        return cfg

    async def _agent_free_switched(on: bool) -> None:
        """The switch just flipped (and is saved, so the gate already reads
        the new value). On: running councils pause, the preflight forgets its
        verdict, the supervised model stops — owned or adopted, as a model
        switch would stop it. Off: the model starts the way a launch starts
        it (`supervisor.bootstrap()`: adopt-or-launch, `_resolve_startup_
        choice`). Home has no model either way. Announced on the stream as
        `agent-free` so every open window can follow."""
        if home:
            return
        if on:
            from .. import council as _council
            runs = [t for t in list(_council._RUNS.values()) if not t.done()]
            for task in runs:
                task.cancel()
            if runs:
                await asyncio.gather(*runs, return_exceptions=True)
            if preflight is not None:
                await preflight.cancel()
                preflight.schedule("agent-free")     # → skipped
            if supervisor is not None:
                try:
                    await supervisor.stop()
                except Exception:  # noqa: BLE001 — the gate is shut regardless
                    log.exception("agent-free: stopping the model failed")
        elif supervisor is not None:
            try:
                await supervisor.bootstrap()
            except Exception:  # noqa: BLE001
                log.exception("agent-free off: supervisor bootstrap failed")
        elif preflight is not None:
            preflight.schedule("agent-free off")
        await session.emit("agent-free", {
            "agent_free": on,
            "supervisor": supervisor.status() if supervisor is not None else None,
        })

    @router.get("/api/readvisor/chief")
    async def api_readvisor_chief_get() -> dict[str, Any]:
        """The chief readvisor's name, on its own.

        It lives in ui.json and so could be read through `/api/ui-config`,
        but that endpoint returns the entire theme catalog — several
        kilobytes of colors — and the rename button in the broker modal
        wants one string. The write side is the more useful half: POSTing
        the whole ui-config to change a name means a client has to send back
        every theme it was given, and a stale client would then overwrite a
        theme change made in another window."""
        return {"name": prompt_mod.chief_name(), "default": prompt_mod.CHIEF_NAME_DEFAULT,
                "max_length": prompt_mod.CHIEF_NAME_MAX}

    @router.post("/api/readvisor/chief")
    async def api_readvisor_chief_set(request: Request) -> dict[str, Any]:
        """Rename the chief readvisor. Body: `{"name": "..."}`.

        Unlike `/api/ui-config`, a name that doesn't validate is an ERROR
        here, not a silent drop: the user typed it into a box and pressed
        enter, so they are owed an answer about why it didn't take."""
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "expected json body") from None
        name = prompt_mod.valid_chief_name((body or {}).get("name"))
        if not name:
            raise HTTPException(
                400,
                f"a readvisor's name is 1–{prompt_mod.CHIEF_NAME_MAX} "
                f"characters of letters, digits, spaces, hyphens, "
                f"apostrophes and dots")
        cfg = _read_ui_config()
        cfg["chief_readvisor_name"] = name
        _write_ui_config(cfg)
        return {"ok": True, "name": name}

    return router
