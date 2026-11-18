"""Help: the bubbles and their defaults (`/api/help/*`), the help center, the brief introduction, and marking a request done (`/api/requests/done`).

Moved out of `enough/server.py`'s `create_app` in 0.8 (lane W2-SV), code unchanged: `build_router` is the old
factory's closure for this group, and the names it closed over come in on `ctx`."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse

from .. import intro as _intro
from ..prompt import get_help_bubbles, list_paradigms, list_roles, list_skills, set_help_bubbles
from .common import AppContext
from ..server import STATIC_DIR, UI_LANGUAGES


def build_router(ctx: AppContext) -> APIRouter:
    router = APIRouter()
    _is_request_file = ctx._is_request_file
    _resolve_project_path = ctx._resolve_project_path
    project_dir = ctx.project_dir

    @router.get("/api/help/defaults")
    async def api_help_defaults() -> dict[str, Any]:
        """Installed skills / readvisors / paradigms (name + description) for the
        help viewer's {{skills-list}} / {{roles-list}} / {{paradigms-list}}
        tokens, so the default lists in help stay in sync with what's actually
        present instead of drifting hand-maintained prose."""
        rness = project_dir / "rness"

        def _build() -> dict[str, Any]:
            from ..skeleton import resync_globals
            resync_globals(project_dir)  # pick up globals added since launch
            skills = [{"name": n, "desc": t} for n, _en, t in list_skills(rness)]
            roles = [{"name": n, "desc": t} for n, _en, t in list_roles(rness)]
            # Paradigms carry an agent-facing description; prefer the
            # user-facing tooltip when present (same rule as the sidebar).
            paradigms = [{"name": n, "desc": (t or d)}
                         for n, d, t in list_paradigms(rness)]
            return {"skills": skills, "roles": roles, "paradigms": paradigms}

        return await asyncio.to_thread(_build)

    @router.get("/api/help/bubbles")
    async def api_help_bubbles_get() -> dict[str, Any]:
        """Whether the sidebar's ``(?)`` help bubbles are shown for this
        project — a sticky per-folder boolean stored in the multipurpose
        `rness/active-paradigm` file, default on."""
        rness = project_dir / "rness"
        enabled = await asyncio.to_thread(get_help_bubbles, rness)
        return {"enabled": enabled}

    @router.post("/api/help/bubbles")
    async def api_help_bubbles_post(request: Request) -> dict[str, Any]:
        """Set the per-project help-bubble on/off state. Body
        ``{"enabled": bool}``; 400 on a non-boolean."""
        body = await request.json()
        enabled = body.get("enabled") if isinstance(body, dict) else None
        if not isinstance(enabled, bool):
            raise HTTPException(400, "enabled must be a boolean")
        await asyncio.to_thread(set_help_bubbles, project_dir / "rness", enabled)
        return {"enabled": enabled}

    @router.get("/api/help-center", response_class=PlainTextResponse)
    async def api_help_center(lang: str = "en") -> PlainTextResponse:
        """The full help-center manual, served as raw markdown for the
        read-only reference mode. `lang` (i18n round) picks a translated
        manual from static/i18n/<lang>/help-center.md when one exists;
        anything else — unknown code, missing translation, en itself —
        falls back to the English docs/HELP_CENTER.md. The whitelist
        check doubles as the path guard: `lang` is never used as a path
        unless it's one of ours."""
        doc = Path(__file__).resolve().parents[2] / "docs" / "HELP_CENTER.md"
        if lang in UI_LANGUAGES and lang != "en":
            translated = STATIC_DIR / "i18n" / lang / "help-center.md"
            if translated.is_file():
                doc = translated
        text = await asyncio.to_thread(
            lambda: doc.read_text(encoding="utf-8") if doc.is_file() else None)
        if text is None:
            raise HTTPException(
                404,
                "HELP_CENTER.md not found in this install — run /update-enough "
                "to pick up the bundled manual.")
        return PlainTextResponse(text, media_type="text/markdown; charset=utf-8")

    @router.get("/api/intro")
    async def api_intro(lang: str = "en") -> dict[str, Any]:
        """The brief introduction to enough, as markdown: `{text, lang}`.
        `lang` picks `static/i18n/<lang>/intro.md` when one ships, else the
        English `defaults/intro.md` — the `/api/help-center` rule, and the
        same whitelist doubling as the path guard. `lang` in the answer is
        the language actually served. No rendered html: the chat draws it
        with the same markdown renderer as everything else."""
        path = _intro.path_for(lang)
        text = await asyncio.to_thread(_intro.text_for, lang)
        if text is None:
            raise HTTPException(404, "intro.md not found in this install")
        served = lang if (lang in UI_LANGUAGES and path != _intro.english_path()) else "en"
        return {"text": text, "lang": served}

    @router.post("/api/requests/done", response_class=HTMLResponse)
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
        # No body needed — the caller closes the preview pane and refreshes
        # the file tree itself; this response just confirms the move.
        return HTMLResponse("")

    return router
