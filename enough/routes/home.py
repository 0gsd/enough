"""The launch screen (`/api/home/*`), closing the project, shutdown, and the favicon.

Moved out of `enough/server.py`'s `create_app` in 0.8 (lane W2-SV), code unchanged: `build_router` is the old
factory's closure for this group, and the names it closed over come in on `ctx`."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from .. import home as _home
from .common import AppContext
from ..server import (
    DESKTOP_ENV,
    DESKTOP_TOKEN_ENV,
    DESKTOP_TOKEN_HEADER,
    HANDOFF_EXIT_CODE,
    STATIC_DIR,
    log,
    request_process_exec,
    request_process_exit,
)


def build_router(ctx: AppContext) -> APIRouter:
    router = APIRouter()
    llm_url = ctx.llm_url
    max_tool_iters = ctx.max_tool_iters
    port = ctx.port
    supervise = ctx.supervise
    supervisor = ctx.supervisor

    # -----------------------------------------------------------------------
    # enough home (home-plan §3). Registered in both modes; `ModeGate`
    # above is what makes `/api/home/*` home-only and `/api/close-project`
    # project-only — the one route that crosses the line, because closing a
    # project is the reverse of opening one.
    # -----------------------------------------------------------------------

    async def _json_body(request: Request) -> dict[str, Any]:
        """The request's JSON object, or `{}`. An empty body is meaningful
        here (`POST /api/home/add` with none raises the folder dialog), so a
        missing body is not an error the way it is elsewhere."""
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            return {}
        return body if isinstance(body, dict) else {}

    async def _handoff(target: Path | None) -> dict[str, Any]:
        """Hand this browser tab over to another mode (home-plan §1.7).

        Desktop: name the project in `.home-open` (nothing to name when we're
        closing one) and exit **42**; the shell's watcher reads the file,
        deletes it, and spawns that project — or home, when the file isn't
        there. CLI: re-exec ourselves on the same port, so the tab that is
        already open reconnects to the same URL after the loader page.
        """
        if supervisor is not None:
            # Same ordering as /api/shutdown: an *adopted* llama-server has to
            # survive us; an owned one goes with us.
            try:
                await supervisor.stop(only_if_owned=True)
            except Exception:  # noqa: BLE001 — never block the handoff
                log.exception("supervisor stop during the home handoff failed")
        if os.environ.get(DESKTOP_ENV) == "1":
            if target is not None:
                await asyncio.to_thread(_home.write_handoff, target)
            request_process_exit(code=HANDOFF_EXIT_CODE)
            log.info("home handoff → desktop (%s)", target or "home")
            return {"handoff": "desktop"}
        argv = _home.exec_argv(
            project_dir=target, port=port or 3456, llm_url=llm_url,
            max_tool_iters=max_tool_iters, supervise=supervise)
        request_process_exec(argv)
        log.info("home handoff → exec (%s)", target or "home")
        return {"handoff": "exec"}

    @router.get("/api/home/projects")
    async def api_home_projects() -> dict[str, Any]:
        """Every registered project, newest-opened first, with stats
        refreshed for the ones whose fingerprint moved (§1.5). Off the loop:
        an unchanged project costs one stat per markdown file, a changed one
        costs a read."""
        projects = await asyncio.to_thread(_home.list_projects)
        return {"projects": projects}

    @router.get("/api/home/mirror")
    async def api_home_mirror(path: str = Query(...)) -> dict[str, Any]:
        """The merirmaid source for a registered project's visible contents.
        Registered only: this is a launch screen, not a filesystem browser."""
        entry = await asyncio.to_thread(_home.entry_for, path)
        if entry is None:
            raise HTTPException(404, "that folder isn't on your home screen.")
        project_dir = Path(entry["path"])
        try:
            text = await asyncio.to_thread(_home.build_project_mirror, project_dir)
        except _home.HomeError as exc:
            raise HTTPException(404, str(exc)) from None
        from .. import project_meta
        return {"path": entry["path"],
                "name": project_meta.load(project_dir)["name"],
                "text": text}

    @router.post("/api/home/add")
    async def api_home_add(request: Request):
        """Enough-ify a folder and put it on the home screen.

        Body `{"path": "/abs/path"}`, or `{}` to raise the native folder
        chooser on the server side (§1.8 — the shell's webview can't open a
        Tauri dialog, and this way the CLI gets the same button). Answers:
        `{"project": …, "created": true}`, `{"cancelled": true}`,
        `{"dialog_unavailable": true, "detail": …}` (show the typed-path
        field), 409 + the existing entry when it's already listed, or 400 with
        the guard's reason.
        """
        body = await _json_body(request)
        raw = str(body.get("path") or "").strip()
        if not raw:
            try:
                chosen = await asyncio.to_thread(_home.choose_folder)
            except _home.DialogUnavailable as exc:
                return {"dialog_unavailable": True, "detail": str(exc)}
            if not chosen:
                return {"cancelled": True}
            raw = chosen
        try:
            project_dir = await asyncio.to_thread(_home.check_addable, raw)
        except _home.HomeError as exc:
            raise HTTPException(400, str(exc)) from None
        existing = await asyncio.to_thread(_home.entry_for, project_dir)
        if existing is not None and _home.is_project(project_dir):
            return JSONResponse(
                {"detail": f"{project_dir} is already on your home screen.",
                 "project": _home.row(existing)},
                status_code=409)
        try:
            project = await asyncio.to_thread(_home.add_project, project_dir)
        except _home.HomeError as exc:
            raise HTTPException(400, str(exc)) from None
        except OSError as exc:
            raise HTTPException(400, f"couldn't set that folder up: {exc}") from None
        return {"project": project, "created": True}

    @router.post("/api/home/open")
    async def api_home_open(request: Request) -> dict[str, Any]:
        """Open a registered project: stamp `last_opened`, then hand off."""
        body = await _json_body(request)
        raw = str(body.get("path") or "").strip()
        if not raw:
            raise HTTPException(400, "which project? send {\"path\": \"…\"}.")
        project_dir = _home.canonical(raw)
        if await asyncio.to_thread(_home.entry_for, project_dir) is None:
            raise HTTPException(404, "that folder isn't on your home screen.")
        if not _home.is_project(project_dir):
            raise HTTPException(
                409, f"{project_dir} isn't there any more (no rness/ folder). "
                     f"If the drive is unplugged, plug it back in; otherwise "
                     f"hide the project, or add it again.")
        await asyncio.to_thread(_home.touch_opened, project_dir)
        return await _handoff(project_dir)

    @router.post("/api/home/hide")
    async def api_home_hide(request: Request) -> dict[str, Any]:
        """Hide or unhide a project on the home screen. Registry only — the
        folder, its rness/ and every word in it are untouched (§1.10)."""
        body = await _json_body(request)
        raw = str(body.get("path") or "").strip()
        if not raw:
            raise HTTPException(400, "which project? send {\"path\": \"…\"}.")
        hidden = body.get("hidden")
        if not isinstance(hidden, bool):
            raise HTTPException(400, "hidden must be a boolean")
        project_dir = _home.canonical(raw)
        changed = await asyncio.to_thread(_home.set_hidden, project_dir, hidden)
        if not changed:
            raise HTTPException(404, "that project isn't registered")
        return {"path": str(project_dir), "hidden": hidden}

    @router.post("/api/close-project")
    async def api_close_project() -> dict[str, Any]:
        """Close this project and go back to home — the reverse of
        `/api/home/open`. Desktop ⌘W does the same thing from the shell
        side; this is the in-window row, and the only path a browser has."""
        return await _handoff(None)

    @router.post("/api/shutdown")
    async def api_shutdown(request: Request) -> dict[str, Any]:
        """Graceful stop — the desktop shell's quit path.

        Gated on ENOUGH_DESKTOP=1 (404 otherwise) plus, when the shell set
        one, a matching ENOUGH_DESKTOP_TOKEN in the X-Enough-Desktop-Token
        header (403 otherwise). See the DESKTOP_ENV block above for why.

        Order matters: stop the llama-server *first* with
        `only_if_owned=True` so an adopted one survives — quitting the app
        must behave exactly like ctrl-c'ing the CLI — then ask uvicorn to
        exit. The lifespan teardown repeats the stop; it's idempotent.
        """
        if os.environ.get(DESKTOP_ENV) != "1":
            raise HTTPException(404, "Not Found")
        token = os.environ.get(DESKTOP_TOKEN_ENV) or ""
        if token and request.headers.get(DESKTOP_TOKEN_HEADER) != token:
            raise HTTPException(403, "bad desktop token")
        if supervisor is not None:
            try:
                await supervisor.stop(only_if_owned=True)
            except Exception:  # noqa: BLE001 — never block the quit path
                log.exception("supervisor stop during /api/shutdown failed")
        request_process_exit()
        log.info("shutdown requested by the desktop shell")
        return {"ok": True, "stopping": True}

    @router.get("/favicon.ico")
    async def favicon():
        f = STATIC_DIR / "favicon.ico"
        if f.exists():
            return FileResponse(f)
        return HTMLResponse("", status_code=204)

    return router
