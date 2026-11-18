"""The page itself (`/`), the project's display metadata (`/api/project*`) and the file tree (`/api/files`).

Moved out of `enough/server.py`'s `create_app` in 0.8 (lane W2-SV), code unchanged: `build_router` is the old
factory's closure for this group, and the names it closed over come in on `ctx`."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from .. import __version__
from .. import agent_free as _agent_free
from .. import prompt as prompt_mod
from .common import AppContext
from ..server import (
    STATIC_DIR,
    _escape_html,
    _render_empty_hint,
    _render_turn_from_history,
    _tree_to_html,
    _ui_language,
    build_file_tree,
)


def build_router(ctx: AppContext) -> APIRouter:
    router = APIRouter()
    home = ctx.home
    preflight = ctx.preflight
    project_dir = ctx.project_dir
    session = ctx.session

    @router.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        # The mode marker the frontend gates on (home-plan §4). Templated into
        # the one `<body>` tag rather than checked into index.html, so the
        # static file stays a project page and home is a server decision.
        html = html.replace(
            "<body>", f'<body data-mode="{"home" if home else "project"}">', 1)
        # Render any existing history so a page refresh doesn't lose the
        # transcript. Home has neither a transcript nor a project.
        html = html.replace(
            "<!-- HISTORY -->",
            "" if home else _render_turn_from_history(session.history),
        )
        # A page load is a project (re)open: re-measure the preflight, so a
        # prompt that grew since (a skill switched on) is judged again.
        if preflight is not None:
            preflight.schedule("page")
        # State-aware empty-hint (drift notice, etc.). Empty-when-history-
        # exists semantics are still handled by the post-send htmx hook.
        html = html.replace(
            "<!-- EMPTY_HINT -->",
            "" if home else _render_empty_hint(session.project_dir),
        )
        html = html.replace("<!-- VERSION -->", f"v{__version__}")
        # Project display name in the header (folder basename unless the user
        # set a custom one). Templated so there's no first-paint flash.
        from .. import project_meta
        html = html.replace(
            "<!-- PROJECT_NAME -->",
            "" if home else _escape_html(project_meta.load(session.project_dir)["name"]),
        )
        # Boot UI state (uiscale round): the saved per-project display scales,
        # templated into the inline BOOT_UI_STATE literal so the zoom vars
        # apply before first paint — same no-flash reasoning as PROJECT_NAME.
        # Home has no project, hence no scales to apply (home:true tells the
        # frontend to leave the vars at 1). <-escape so no JSON string
        # can ever close the script element.
        # `chief_readvisor_name` rides along for the same no-flash reason as
        # the scales: it is in the byline of every history bubble the server
        # just rendered, and the panel header, so the page must not first
        # paint someone else's name.
        # `agent_free` rides along for the same reason: the readvisor panel
        # and every other model surface must not paint and then vanish.
        boot_ui: dict[str, Any] = {
            "home": home,
            "lang": _ui_language(),
            "chief_readvisor_name": prompt_mod.chief_name(),
            "agent_free": _agent_free.enabled(),
            # 0.5.1: stamps the page's static asset URLs (staticUrl() in
            # index.html) so an upgrade never shows the last release's icons.
            "version": __version__,
        }
        if not home:
            meta = project_meta.load(session.project_dir)
            # The whole `ui` block: the two zoom vars plus the readvisor
            # panel's docked/closed state (composure round, P3) — the panel
            # has to be sized before first paint or the layout visibly
            # reflows. `folder` rides along for the window title, which is
            # "enough 📁 <folder> 🖊️ <nice name>" (P1) and would otherwise
            # need a round trip to /api/project to know the basename.
            boot_ui.update(meta["ui"])
            boot_ui["folder"] = meta["folder"]
        html = html.replace(
            "/*UI_STATE_JSON*/null",
            json.dumps(boot_ui).replace("<", "\\u003c"),
            1,
        )
        # No-cache so edits-in-place don't require force-reload during dev.
        return HTMLResponse(html, headers={"Cache-Control": "no-store, must-revalidate"})

    @router.get("/api/project")
    async def api_project_get() -> dict[str, Any]:
        """Project display metadata: editable name + description + the
        read-only on-disk path. Powers the header title and its edit modal."""
        from .. import project_meta
        return project_meta.load(session.project_dir)

    @router.post("/api/project")
    async def api_project_set(request: Request) -> dict[str, Any]:
        """Persist the project's display name and/or description. Body:
        {"name": "...", "description": "..."}. The folder on disk is never
        renamed — only `rness/project.json` is written. Returns the refreshed
        metadata so the UI can update the header in place."""
        from .. import project_meta
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "expected json body") from None
        return project_meta.save(
            session.project_dir,
            (body or {}).get("name"),
            (body or {}).get("description"),
        )

    @router.post("/api/project/ui")
    async def api_project_ui_set(request: Request) -> dict[str, Any]:
        """Persist the per-project display block (uiscale round; the panel
        state joined it in the composure round). Body: {"ui_scale": 1.2,
        "text_scale": 1.0, "readvisor_panel": "open"|"closed"}. Separate from
        POST /api/project so the name/description editor and the display
        controls can't clobber each other's half of rness/project.json. An
        omitted `readvisor_panel` keeps the stored one. Returns the refreshed
        metadata (the cleaned values the frontend should display)."""
        from .. import project_meta
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "expected json body") from None
        return project_meta.save_ui(
            session.project_dir,
            (body or {}).get("ui_scale"),
            (body or {}).get("text_scale"),
            (body or {}).get("readvisor_panel"),
        )

    @router.post("/api/project/composure")
    async def api_project_composure_set(request: Request) -> dict[str, Any]:
        """Persist what the base-layer canvas opens with (composure round,
        P4d). Body: {"launch": "auto"|"new"|"last"|"file"|"form",
        "path": "…", "form": "…"} (`file` + `path` is the startup composure a
        composure's settings modal ticks; unticking it posts `auto`). Its own endpoint for the same reason /api/project/ui
        is: three independent controls write three independent halves of
        rness/project.json. `last` is bookkeeping and is never accepted
        here — it is stamped by GET /api/composure. Returns the refreshed
        metadata; GET /api/composure/launch resolves it against disk."""
        from .. import project_meta
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "expected json body") from None
        body = body or {}
        launch = body.get("launch")
        if launch not in project_meta.COMPOSURE_LAUNCH_MODES:
            raise HTTPException(
                400, "launch must be one of "
                     + ", ".join(project_meta.COMPOSURE_LAUNCH_MODES))
        return project_meta.save_composure(
            session.project_dir, launch, body.get("path"), body.get("form"))

    @router.get("/api/files", response_class=HTMLResponse)
    async def api_files() -> HTMLResponse:
        tree = build_file_tree(project_dir)
        return HTMLResponse(_tree_to_html(tree))

    return router
