"""The offline wiki: installs, articles, search, comments, saves, overrides, setup and download (`/api/wiki/*`).

Moved out of `enough/server.py`'s `create_app` in 0.8 (lane W2-SV), code unchanged: `build_router` is the old
factory's closure for this group, and the names it closed over come in on `ctx`."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from .. import broker as _broker
from ..wikisink import config as _wikisink_config
from .common import AppContext


def build_router(ctx: AppContext) -> APIRouter:
    router = APIRouter()
    project_dir = ctx.project_dir
    session = ctx.session

    # ------------------------------------------------------------------
    # Wikisink — local Wikipedia (🚰)
    # ------------------------------------------------------------------

    from ..wikisink import download as _wiki_download
    from ..wikisink import overlay as _wiki_overlay
    from ..wikisink import zim as _wiki_zim

    wiki_dl = _wiki_download.DownloadManager(emit=session.emit)

    def _wiki_503(e: Exception) -> HTTPException:
        # WikisinkUnavailable messages are user-facing and actionable.
        return HTTPException(503, str(e))

    @router.get("/api/wiki/status")
    async def api_wiki_status() -> dict[str, Any]:
        def _status() -> dict[str, Any]:
            cfg = _wikisink_config.load_config()
            installed = _wikisink_config.installed(cfg)
            info = None
            if installed:
                try:
                    info = _wiki_zim.snapshot_info()
                except (_wiki_zim.WikisinkUnavailable, RuntimeError) as e:
                    # libzim wheel missing, or the file is corrupt/truncated
                    # (a real possibility with removable drives)
                    installed = False
                    info = {"error": str(e)}
            try:
                comment_count = len(list(_wikisink_config.comments_dir(cfg).glob("*.json")))
            except OSError:
                comment_count = 0
            active_meta = _wikisink_config.active_zim_meta(cfg)
            install_rows = [{
                **i,
                "size_human": _wiki_download.bytes_to_human(i.get("size_bytes") or 0),
                "available": _wikisink_config.install_available(i),
                "active": i.get("id") == cfg.get("active_install"),
            } for i in _wikisink_config.installs(cfg)]
            return {
                # installed = the active archive is servable right now;
                # configured = installs exist, reachable or not. A detached
                # drive is configured-but-not-installed, and the reason
                # explains that in user words.
                "installed": installed,
                "configured": _wikisink_config.configured(cfg),
                "unavailable_reason": (None if installed
                                       else _wikisink_config.unavailable_reason(cfg)),
                "installs": install_rows,
                "active_install": cfg.get("active_install"),
                "zim": info,
                "flavor": active_meta.get("flavor"),
                "snapshot": active_meta.get("snapshot"),
                "storage_dir": str(active_meta.get("storage_dir")
                                   or _wikisink_config.DEFAULT_STORAGE_DIR),
                "data_dir": str(_wikisink_config.data_dir(cfg)),
                "download": cfg.get("download"),
                "download_active": wiki_dl.active,
                "last_viewed": cfg.get("last_viewed"),
                "last_wikisink_at": cfg.get("last_wikisink_at"),
                # cached_only: status must stay instant; the flavors call
                # made when the setup modal opens warms this cache.
                "newer_snapshot": _wiki_download.newer_snapshot_available(
                    cfg, cached_only=True) if installed else None,
                "counts": {
                    "watched": len(cfg.get("watched", [])),
                    "comments": comment_count,
                    "overrides": len(cfg.get("overrides", [])),
                },
                "overrides": cfg.get("overrides", []),
            }
        return await asyncio.to_thread(_status)

    @router.post("/api/wiki/installs/activate")
    async def api_wiki_install_activate(request: Request) -> dict[str, Any]:
        """Switch which registered archive is served. Switching to a
        currently unreachable install is allowed (the user may be about
        to plug the drive in) — the UI warns, nothing breaks."""
        body = await request.json()
        install = (body.get("id") or "").strip()
        entry = await asyncio.to_thread(_wikisink_config.set_active_install, install)
        if entry is None:
            raise HTTPException(404, f"no install {install!r}")
        _wiki_zim.reset_archive()
        _broker.trace(project_dir, tool="wiki_install", decision="allowed",
                      args={"op": "activate", "id": install},
                      result_ok=True, result_summary=entry.get("filename") or "")
        return {"ok": True, "active": entry,
                "available": _wikisink_config.install_available(entry)}

    @router.delete("/api/wiki/installs")
    async def api_wiki_install_forget(id: str = Query(...)) -> dict[str, Any]:
        """Forget an install (registry only). The archive file always
        stays on disk — deleting gigabytes is the user's own act."""
        removed = await asyncio.to_thread(_wikisink_config.remove_install, id)
        if removed is None:
            raise HTTPException(404, f"no install {id!r}")
        _wiki_zim.reset_archive()
        _broker.trace(project_dir, tool="wiki_install", decision="allowed",
                      args={"op": "forget", "id": id},
                      result_ok=True,
                      result_summary=f"file kept: {removed.get('filename')}")
        return {"ok": True, "file_kept": str(_wikisink_config.install_zim_path(removed))}

    @router.get("/api/wiki/article")
    async def api_wiki_article(
        path: str | None = Query(None), title: str | None = Query(None)
    ) -> dict[str, Any]:
        if not path and not title:
            raise HTTPException(400, "missing path or title")

        def _fetch() -> dict[str, Any]:
            art = _wiki_overlay.resolve_article(path=path, title=title)
            art["html"] = _wiki_zim.sanitize_and_rewrite(art["html"], art["path"])
            _wikisink_config.record_viewed(art["path"], art["title"])
            cfg = _wikisink_config.load_config()
            art["snapshot"] = (cfg.get("zim") or {}).get("snapshot")
            art["overridden"] = _wikisink_config.is_overridden(art["path"], cfg)
            return art

        try:
            return await asyncio.to_thread(_fetch)
        except KeyError:
            raise HTTPException(404, f"no article for {path or title!r} in the local archive") from None
        except _wiki_zim.WikisinkUnavailable as e:
            raise _wiki_503(e) from None

    @router.get("/api/wiki/search")
    async def api_wiki_search(
        q: str = Query(...), offset: int = Query(0, ge=0), n: int = Query(20, ge=1, le=50)
    ) -> dict[str, Any]:
        try:
            return await asyncio.to_thread(_wiki_zim.search, q, offset, n)
        except _wiki_zim.WikisinkUnavailable as e:
            raise _wiki_503(e) from None

    @router.get("/api/wiki/suggest")
    async def api_wiki_suggest(
        q: str = Query(...), n: int = Query(10, ge=1, le=25)
    ) -> dict[str, Any]:
        try:
            return {"results": await asyncio.to_thread(_wiki_zim.suggest, q, n)}
        except _wiki_zim.WikisinkUnavailable as e:
            raise _wiki_503(e) from None

    @router.get("/api/wiki/random")
    async def api_wiki_random() -> dict[str, Any]:
        try:
            return await asyncio.to_thread(_wiki_zim.random_article)
        except _wiki_zim.WikisinkUnavailable as e:
            raise _wiki_503(e) from None

    from ..wikisink import comments as _wiki_comments

    @router.get("/api/wiki/comments")
    async def api_wiki_comments_get(path: str = Query(...)) -> dict[str, Any]:
        return await asyncio.to_thread(_wiki_comments.load_comments, path)

    @router.post("/api/wiki/comments")
    async def api_wiki_comments_post(request: Request) -> dict[str, Any]:
        body = await request.json()
        path = (body.get("path") or "").strip()
        text = (body.get("body") or "").strip()
        if not path or not text:
            raise HTTPException(400, "missing path or body")
        entry = await asyncio.to_thread(
            _wiki_comments.add_comment, path,
            (body.get("title") or "").strip(), text, body.get("anchor"))
        _broker.trace(project_dir, tool="wiki_comment", decision="allowed",
                      args={"path": path, "op": "add", "id": entry["id"]},
                      result_ok=True, result_summary=text[:120])
        return entry

    @router.patch("/api/wiki/comments")
    async def api_wiki_comments_patch(request: Request) -> dict[str, Any]:
        body = await request.json()
        path = (body.get("path") or "").strip()
        cid = (body.get("id") or "").strip()
        try:
            entry = await asyncio.to_thread(
                _wiki_comments.update_comment, path, cid,
                body=body.get("body"), resolved=body.get("resolved"),
                state=body.get("state"))
        except KeyError:
            raise HTTPException(404, f"no comment {cid!r}") from None
        # State reconciliation (anchored/paragraph/orphaned) happens on
        # every render — journaling those would flood the log; only real
        # edits get traced.
        if body.get("body") is not None or body.get("resolved") is not None:
            _broker.trace(project_dir, tool="wiki_comment", decision="allowed",
                          args={"path": path, "op": "edit", "id": cid},
                          result_ok=True, result_summary="")
        return entry

    @router.post("/api/wiki/comments/reply")
    async def api_wiki_comments_reply(request: Request) -> dict[str, Any]:
        body = await request.json()
        path = (body.get("path") or "").strip()
        cid = (body.get("id") or "").strip()
        text = (body.get("body") or "").strip()
        if not text:
            raise HTTPException(400, "missing body")
        try:
            reply = await asyncio.to_thread(_wiki_comments.add_reply, path, cid, text)
        except KeyError:
            raise HTTPException(404, f"no comment {cid!r}") from None
        _broker.trace(project_dir, tool="wiki_comment", decision="allowed",
                      args={"path": path, "op": "reply", "id": cid},
                      result_ok=True, result_summary=text[:120])
        return reply

    @router.delete("/api/wiki/comments")
    async def api_wiki_comments_delete(
        path: str = Query(...), id: str = Query(...)
    ) -> dict[str, Any]:
        try:
            await asyncio.to_thread(_wiki_comments.delete_comment, path, id)
        except KeyError:
            raise HTTPException(404, f"no comment {id!r}") from None
        _broker.trace(project_dir, tool="wiki_comment", decision="allowed",
                      args={"path": path, "op": "delete", "id": id},
                      result_ok=True, result_summary="")
        return {"ok": True}

    @router.post("/api/wiki/save")
    async def api_wiki_save(request: Request) -> dict[str, Any]:
        from ..wikisink import save as _wiki_save

        body = await request.json()
        path = (body.get("path") or "").strip()
        dest = (body.get("dest") or "").strip()
        if not path:
            raise HTTPException(400, "missing path")
        try:
            result = await asyncio.to_thread(
                _wiki_save.save_article, project_dir, path, dest)
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        except KeyError:
            raise HTTPException(404, f"no article for {path!r}") from None
        except _wiki_zim.WikisinkUnavailable as e:
            raise _wiki_503(e) from None
        _broker.trace(project_dir, tool="wiki_save", decision="allowed",
                      args={"path": path, "dest": dest},
                      result_ok=True, result_summary=result["saved_path"])
        return result

    @router.get("/api/wiki/saved")
    async def api_wiki_saved(file: str = Query(...)) -> dict[str, Any]:
        """A saved article folder, rendered for the reader. Serves the
        stored verbatim copy through the same sanitize pipeline as live
        browsing — works even when no archive is installed/reachable
        (that's much of the point of saving)."""
        from ..wikisink import save as _wiki_save

        def _load() -> dict[str, Any]:
            art = _wiki_save.read_saved(project_dir, file)
            art["html"] = _wiki_zim.sanitize_and_rewrite(art["html"], art["path"])
            if art["path"]:
                _wikisink_config.record_viewed(art["path"], art["title"])
                cfg = _wikisink_config.load_config()
                art["overridden"] = _wikisink_config.is_overridden(art["path"], cfg)
            return art

        try:
            return await asyncio.to_thread(_load)
        except ValueError as e:
            raise HTTPException(404, str(e)) from None
        except OSError as e:
            raise HTTPException(500, f"couldn't read the saved article: {e}") from None

    @router.post("/api/wiki/unsave")
    async def api_wiki_unsave(request: Request) -> dict[str, Any]:
        """Delete a saved-article folder (user-initiated from the tree's
        trash affordance). Only the saved copy goes; the archive copy,
        comments, and overrides are untouched."""
        from ..wikisink import save as _wiki_save

        body = await request.json()
        ref = (body.get("dir") or "").strip()
        if not ref:
            raise HTTPException(400, "missing dir")
        try:
            result = await asyncio.to_thread(_wiki_save.unsave_article, project_dir, ref)
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        except OSError as e:
            raise HTTPException(500, f"unsave failed: {e}") from None
        _broker.trace(project_dir, tool="wiki_save", decision="allowed",
                      args={"dir": ref, "op": "unsave"},
                      result_ok=True, result_summary=result["removed"])
        return result

    @router.get("/api/wiki/flavors")
    async def api_wiki_flavors(force: bool = Query(False)) -> dict[str, Any]:
        return await asyncio.to_thread(_wiki_download.list_flavors, force)

    @router.get("/api/wiki/newer-snapshot")
    async def api_wiki_newer_snapshot() -> dict[str, Any]:
        """The reader's newer-snapshot check (docs/skills-round-plan.md §5).

        Deliberately NOT folded into `/api/wiki/status`, which is documented
        as instant and network-free — this one is allowed to go to
        download.kiwix.org, but at most once per 24 h (the clock is persisted
        as `listing_checked_at` in wikisink.json). Silent on failure; the
        reader fires it in the background after it renders."""
        return await asyncio.to_thread(_wiki_download.newer_snapshot_throttled)

    @router.get("/api/wiki/diskspace")
    async def api_wiki_diskspace(dir: str = Query(...)) -> dict[str, Any]:
        """Free-space readout for the setup modal's storage-dir field.
        Walks up to the nearest existing ancestor so a not-yet-created
        default like ~/enough/wikisink still reports its volume."""
        p = Path(dir).expanduser()
        probe = p
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        try:
            free = shutil.disk_usage(probe).free
        except OSError as e:
            raise HTTPException(400, f"can't inspect {p}: {e}") from None
        return {"dir": str(p), "free_bytes": free,
                "free_human": _wiki_download.bytes_to_human(free)}

    @router.post("/api/wiki/setup")
    async def api_wiki_setup(request: Request) -> dict[str, Any]:
        body = await request.json()
        flavor = (body.get("flavor") or "").strip()
        storage_dir = (body.get("storage_dir") or "").strip() or None
        replace_id = (body.get("replace_id") or "").strip() or None
        listing = await asyncio.to_thread(_wiki_download.list_flavors)
        entry = next((f for f in listing["flavors"] if f["flavor"] == flavor), None)
        if entry is None:
            raise HTTPException(404, f"unknown flavor {flavor!r}")
        # Same file into the same place = the install that's already
        # registered; switching to it beats re-downloading 16-49 GB.
        target = str(Path(storage_dir or str(
            _wikisink_config.DEFAULT_STORAGE_DIR)).expanduser())
        dupe = _wikisink_config.get_install(
            _wikisink_config.install_id(target, entry["filename"]))
        if dupe is not None and not replace_id:
            raise HTTPException(409, (
                f"{entry['filename']} is already installed at {target} — "
                "switch to it in the installs list instead of downloading again."
                if _wikisink_config.install_available(dupe) else
                f"{entry['filename']} is already registered at {target} but "
                "unreachable — reattach that drive, or forget the install "
                "first if it's gone for good."))
        try:
            wiki_dl.start(flavor=entry["flavor"], filename=entry["filename"],
                          url=entry["url"], size_bytes=entry["size_bytes"],
                          snapshot=entry["date"], storage_dir=storage_dir,
                          replace_id=replace_id)
        except _wiki_download.DownloadError as e:
            code = 409 if "already running" in str(e) else 400
            raise HTTPException(code, str(e)) from None
        await session.emit("system", {
            "kind": "wikisink_setup",
            "message": (
                f"wikisink: downloading {entry['label']} "
                f"({entry['size_human']}, snapshot {entry['date']}) from "
                "download.kiwix.org. this can take a while — it's resumable, "
                "survives restarts, and the 🚰 button shows progress. "
                "everything else keeps working meanwhile."
            ),
        })
        return {"started": True, "filename": entry["filename"],
                "size_bytes": entry["size_bytes"]}

    @router.get("/api/wiki/overrides")
    async def api_wiki_overrides_get() -> dict[str, Any]:
        cfg = _wikisink_config.load_config()
        return {"overrides": cfg.get("overrides", [])}

    @router.post("/api/wiki/override")
    async def api_wiki_override_post(request: Request) -> dict[str, Any]:
        """Deletion override: preserve this article's local copy forever
        and stop trying to update it. User-initiated only (the agent has
        deliberately no tool for this)."""
        body = await request.json()
        path = (body.get("path") or "").strip()
        if not path:
            raise HTTPException(400, "missing path")
        try:
            entry = await asyncio.to_thread(
                _wiki_overlay.preserve, path, body.get("title") or None,
                reason=(body.get("reason") or "").strip(),
                deletion_log_excerpt=(body.get("deletion_log_excerpt") or "").strip())
        except KeyError:
            raise HTTPException(404, f"no local copy of {path!r} to preserve") from None
        except _wiki_zim.WikisinkUnavailable as e:
            raise _wiki_503(e) from None
        _broker.trace(project_dir, tool="wiki_override", decision="allowed",
                      args={"path": path, "op": "preserve"},
                      result_ok=True, result_summary=entry["preserved_file"])
        return entry

    @router.delete("/api/wiki/override")
    async def api_wiki_override_delete(path: str = Query(...)) -> dict[str, Any]:
        removed = await asyncio.to_thread(_wikisink_config.remove_override, path)
        if removed is None:
            raise HTTPException(404, f"no override for {path!r}")
        # The preserved file stays on disk — deleting bytes is a separate,
        # user-confirmed act; un-overriding just resumes normal serving.
        _broker.trace(project_dir, tool="wiki_override", decision="allowed",
                      args={"path": path, "op": "remove"},
                      result_ok=True, result_summary="preserved file kept")
        return {"ok": True, "preserved_file_kept": removed.get("preserved_file")}

    @router.post("/api/wiki/wikisink")
    async def api_wiki_wikisink(request: Request) -> dict[str, Any]:
        """UI-triggered update run — same engine as the agent's wikisink
        tool. Progress streams over SSE `wiki_sink`; the report lands in
        chat as a copyable system message."""
        from ..wikisink import update as _wiki_update

        body = await request.json() if int(request.headers.get("content-length") or 0) else {}
        scope = body.get("scope") if body.get("scope") in ("watched", "report-only") else "watched"
        try:
            report = await asyncio.to_thread(
                _wiki_update.run_wikisink, project_dir, scope)
        except _wiki_zim.WikisinkUnavailable as e:
            raise _wiki_503(e) from None
        _broker.trace(project_dir, tool="wikisink", decision="allowed",
                      args={"scope": scope, "trigger": "ui"},
                      result_ok=True, result_summary=f"report {len(report)} chars")
        await session.emit("system", {"kind": "wikisink_report", "message": report})
        return {"ok": True, "report": report}

    @router.post("/api/wiki/download/{action}")
    async def api_wiki_download_ctl(action: str) -> dict[str, Any]:
        try:
            if action == "pause":
                wiki_dl.pause()
            elif action == "resume":
                wiki_dl.resume()
            elif action == "cancel":
                wiki_dl.cancel()
            else:
                raise HTTPException(404, f"unknown action {action!r}")
        except _wiki_download.DownloadError as e:
            raise HTTPException(400, str(e)) from None
        return {"ok": True, "action": action}

    return router
