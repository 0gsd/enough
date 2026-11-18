"""Conversion and twins (`/api/convert*`), the raw blob (`/api/file/blob`), pagination (`/api/paginate*`).

Moved out of `enough/server.py`'s `create_app` in 0.8 (lane W2-SV), code unchanged: `build_router` is the old
factory's closure for this group, and the names it closed over come in on `ctx`."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse

from .. import convert as _convert
from .. import paginate as _paginate
from .common import AppContext
from ..server import _store_prefix


def build_router(ctx: AppContext) -> APIRouter:
    router = APIRouter()
    _emit_threadsafe = ctx._emit_threadsafe
    _resolve_project_path = ctx._resolve_project_path
    project_dir = ctx.project_dir
    session = ctx.session

    # ------------------------------------------------------------------
    # convert — editable markdown twins for PDFs, Word documents, and
    # friends. The registry, the state machine, and the manifest live in
    # convert.py; conversions and exports run in `enough.convert_worker`
    # subprocesses. Job progress streams on the `convert` SSE event and
    # extras installs on `convert-install`. Contract: docs/convert-plan.md §4.
    # ------------------------------------------------------------------

    convert_jobs = _convert.ConvertJobs(emit=_emit_threadsafe)
    extra_installer = _convert.ExtraInstaller(emit=_emit_threadsafe)

    def _convert_http(e: _convert.ConvertError) -> HTTPException:
        return HTTPException(e.status, str(e))

    def _convert_pair(path: str) -> tuple[Path | None, Path, str, str]:
        """`(original, twin, rel_original, rel_twin)` for a convert request.

        Every convert endpoint takes either end of the pair: the tree holds
        the original, the save hook and the agent hold the twin. `original` is
        None for a plain markdown file, which can still be exported (md → PDF
        works on every install) but has nothing to overwrite.

        Canon paths (`canon:`) are refused here on
        purpose — plan decision 9 scopes v1 to the project tree, and the
        store's catalog/sidecar write-guards have no opinion about twins."""
        if _store_prefix(path):
            raise HTTPException(400, "conversion works on project files only")
        target = _resolve_project_path(path)
        try:
            original, twin = _convert.pair_for(target)
        except _convert.ConvertError as e:
            raise _convert_http(e) from None
        if original is not None and target != original:
            rel_original = path[: -len(".md")]
        else:
            rel_original = path
        return original, twin, rel_original, f"{rel_original}.md"

    @router.get("/api/convert/formats")
    async def api_convert_formats() -> dict[str, Any]:
        """The format registry plus what each engine can do on this machine.
        ONE source of truth: the export modal, the `{{convert-formats}}` help
        token, and the system prompt all render this payload, so the supported
        types can't drift between the code and the documentation."""
        return await asyncio.to_thread(_convert.formats_view)

    @router.get("/api/convert/status")
    async def api_convert_status(path: str = Query(...)) -> dict[str, Any]:
        """State of one document: `fresh`, `edited`, `stale`, `conflict`,
        `unconverted`, or `engine-missing`, plus the manifest and the spec."""
        original, twin, rel_original, rel_twin = _convert_pair(path)
        if original is None:
            # Plain markdown: no pairing, but exportable all the same.
            return {"path": rel_twin, "state": None, "twin": None,
                    "manifest": None, "spec": None, "sync": False,
                    "export_targets": _convert.export_targets_for(None)}
        try:
            out = await asyncio.to_thread(_convert.status, original, rel=rel_original)
        except _convert.ConvertError as e:
            raise _convert_http(e) from None
        out["twin_path"] = rel_twin if twin.is_file() else None
        return out

    @router.post("/api/convert")
    async def api_convert_start(request: Request) -> dict[str, Any]:
        """Start a conversion. 409 when one is already running for this path,
        or when a twin exists and `force` wasn't set. A forced re-convert
        stashes the existing twin to its `.undo` first, so "re-convert from
        the new original" is undoable like any other write."""
        body = await request.json()
        path = (body.get("path") or "").strip()
        if not path:
            raise HTTPException(400, "missing path")
        original, _twin, rel_original, _rel_twin = _convert_pair(path)
        if original is None:
            raise HTTPException(400, f"{path} is not a convertible document")
        try:
            return convert_jobs.start(rel=rel_original, original=original,
                                      force=bool(body.get("force")))
        except _convert.ConvertError as e:
            raise _convert_http(e) from None

    @router.get("/api/convert/job/{job_id}")
    async def api_convert_job(job_id: str) -> dict[str, Any]:
        try:
            return convert_jobs.snapshot(job_id)
        except _convert.ConvertError as e:
            raise _convert_http(e) from None

    @router.post("/api/convert/job/{job_id}/cancel")
    async def api_convert_job_cancel(job_id: str) -> dict[str, Any]:
        """Kill the worker. Cancellation is a `kill` because most of a
        conversion happens inside pandoc (and, later, torch), where no
        cooperative flag would be noticed."""
        try:
            return convert_jobs.cancel(job_id)
        except _convert.ConvertError as e:
            raise _convert_http(e) from None

    @router.post("/api/convert/export")
    async def api_convert_export(request: Request) -> dict[str, Any]:
        """Write the twin out — over the original, or as a datestamped copy
        beside it. Overwrite stashes the original through the ordinary
        `stash_for_undo`, so the save/undo bar covers it like any other write;
        409 when the original changed outside enough since conversion."""
        body = await request.json()
        path = (body.get("path") or "").strip()
        target = (body.get("target") or "").strip().lower()
        mode = (body.get("mode") or "copy").strip().lower()
        if not path or not target:
            raise HTTPException(400, "missing path or target")
        original, twin, rel_original, rel_twin = _convert_pair(path)
        try:
            out = await asyncio.to_thread(
                _convert.export, twin=twin, original=original,
                target=target, mode=mode)
        except _convert.ConvertError as e:
            raise _convert_http(e) from None
        await session.emit(_convert.EVENT, {
            "job": None, "path": rel_original, "op": "export", "state": "done",
            "progress": 100, "message": f"exported {out['written']}",
            "result": out, "error": None})
        return out

    @router.post("/api/convert/sync")
    async def api_convert_sync(request: Request) -> dict[str, Any]:
        """Flip "keep the original in sync with my edits". pandoc-family
        originals only — a PDF's export is a re-typeset, not a round trip."""
        body = await request.json()
        path = (body.get("path") or "").strip()
        if not path:
            raise HTTPException(400, "missing path")
        original, _twin, rel_original, _rel_twin = _convert_pair(path)
        if original is None:
            raise HTTPException(400, f"{path} is not a converted document")
        try:
            out = await asyncio.to_thread(_convert.set_sync, original,
                                          bool(body.get("enabled")))
        except _convert.ConvertError as e:
            raise _convert_http(e) from None
        out["path"] = rel_original
        return out

    @router.post("/api/convert/resolve")
    async def api_convert_resolve(request: Request) -> dict[str, Any]:
        """Conflict resolution, one of three ways:

        `reconvert` — the original wins; the twin is stashed to `.undo` and
        the conversion re-runs. `keep` — the twin wins; the manifest records
        the original as it now stands, so `stale` clears without touching
        anybody's text. `export` — my twin over their original, the one call
        that bypasses the stale 409."""
        body = await request.json()
        path = (body.get("path") or "").strip()
        choice = (body.get("choice") or "").strip().lower()
        if not path:
            raise HTTPException(400, "missing path")
        original, twin, rel_original, _rel_twin = _convert_pair(path)
        if original is None:
            raise HTTPException(400, f"{path} is not a converted document")
        try:
            if choice == "reconvert":
                return convert_jobs.start(rel=rel_original, original=original, force=True)
            if choice == "keep":
                out = await asyncio.to_thread(_convert.accept_external_change, original)
                out["path"] = rel_original
                return out
            if choice == "export":
                return await asyncio.to_thread(
                    _convert.export, twin=twin, original=original,
                    target=original.suffix.lower(), mode="overwrite",
                    allow_stale=True)
        except _convert.ConvertError as e:
            raise _convert_http(e) from None
        raise HTTPException(400, "choice must be reconvert, keep, or export")

    @router.get("/api/file/blob")
    async def api_file_blob(path: str = Query(...), meta: int = Query(0)):
        """Raw bytes for the twin's images, the image viewer, and "view
        original". Same path guard as `/api/file`, plus an explicit media-type
        allowlist — never `text/html`, because a same-origin HTML document
        served from here would run script with the app's own origin.

        `&meta=1` answers with size and media type only. Width and height are
        deliberately null: Pillow is not a base dependency, and the viewer
        reads `naturalWidth`/`naturalHeight` off the loaded <img> anyway,
        which is both free and always right."""
        target = _resolve_project_path(path)
        if not target.exists():
            raise HTTPException(404, "not found")
        if target.is_dir():
            raise HTTPException(400, "is a directory")
        media = _convert.BLOB_MEDIA_TYPES.get(target.suffix.lower())
        if media is None:
            raise HTTPException(
                415, f"{target.suffix or 'this file type'} is not served as a blob")
        if meta:
            return {"path": path, "size": target.stat().st_size,
                    "media_type": media, "width": None, "height": None}
        headers = {"X-Content-Type-Options": "nosniff"}
        if media == "image/svg+xml":
            headers["Content-Security-Policy"] = _convert.SVG_CSP
        return FileResponse(target, media_type=media, headers=headers)

    # ------------------------------------------------------------------
    # paginate — a finished markdown document typeset into a PDF. The
    # options schema, the size table, the imposition arithmetic and the
    # `.typ` surgery live in paginate.py; the pipeline runs in the same
    # `enough.convert_worker` subprocess as export, synchronously, and
    # emits the `convert` SSE event so the tree picks the PDF up.
    # Contract: docs/paginate-plan.md §2.3.
    # ------------------------------------------------------------------

    def _paginate_http(e: _paginate.PaginateError) -> HTTPException:
        return HTTPException(e.status, str(e))

    @router.get("/api/paginate/status")
    async def api_paginate_status(path: str = Query(...)) -> dict[str, Any]:
        """What the modal draws itself from: the font list, the size table,
        the default export name, and whether the two engines are here. The
        frontend hardcodes none of it."""
        if _store_prefix(path):
            raise HTTPException(400, "pagination works on project files only")
        _resolve_project_path(path)          # traversal guard, same as /api/file
        try:
            return await asyncio.to_thread(_paginate.status, project_dir, path)
        except _paginate.PaginateError as e:
            raise _paginate_http(e) from None

    @router.post("/api/paginate")
    async def api_paginate(request: Request) -> dict[str, Any]:
        """Typeset one document. Body is the §2.2 options object; `path` is
        the only key in it that isn't an option. Runs the worker
        synchronously like export — a paginate is one document, not a queue —
        and answers `{ok, pdf, pages, viewer}`."""
        body = await request.json()
        if not isinstance(body, dict):
            raise HTTPException(400, "expected a paginate options object")
        path = (body.get("path") or "").strip()
        if not path:
            raise HTTPException(400, "missing path")
        if _store_prefix(path):
            raise HTTPException(400, "pagination works on project files only")
        _resolve_project_path(path)
        try:
            out = await asyncio.to_thread(_paginate.run_paginate, project_dir, body)
        except _paginate.PaginateError as e:
            raise _paginate_http(e) from None
        await session.emit(_convert.EVENT, {
            "job": None, "path": path, "op": "paginate", "state": "done",
            "progress": 100, "message": f"paginated {out['pdf']}",
            "result": out, "error": None})
        return out

    @router.post("/api/convert/install")
    async def api_convert_install(request: Request) -> dict[str, Any]:
        """Install an optional dependency group with the same `uv sync` the
        onboarding wizard runs, streaming uv's output on the `convert-install`
        SSE event. Idempotent; a dropped connection resumes (uv's own
        behaviour). The installed set is recorded in `extras.json` so the next
        `uv sync` — which is exact by default — is told to keep it."""
        body = await request.json()
        try:
            return extra_installer.start((body.get("extra") or "pdf").strip())
        except _convert.ConvertError as e:
            raise _convert_http(e) from None

    @router.get("/api/convert/install/status")
    async def api_convert_install_status() -> dict[str, Any]:
        return await asyncio.to_thread(extra_installer.status)

    return router
