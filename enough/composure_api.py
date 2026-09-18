"""The `/api/composure*` routes, as one `APIRouter` `create_app` mounts.

Why a separate module: `enough/composure.py` is the pure core and imports
no FastAPI, so it can be exercised (and reasoned about) without a web
layer. This file is the thin translation between HTTP and that core —
path resolution, status codes, the SSE fan-out — and nothing else. Every
refusal it emits is a `ComposureError` message from the core, so a client
and a readvisor read the same sentence.

`build_router()` takes the three things `create_app` owns and the core does
not: the project directory, the path-safety helper (`_resolve_project_path`,
which also carries the `cacheawl:` scheme), and `session.emit`. That is the
whole seam — no globals, and the router is constructible in a test with
three lambdas.

Concurrency: every mutating route goes through `composure.apply_ops`, which
holds the per-path write lock for the whole load → mutate → save. Reads are
lock-free; a read that races a write sees one version or the other, never a
half-written file, because writes are tmp+rename.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, HTTPException, Query, Request

from . import broker
from . import composure as comp_core
from .composure import ComposureError

log = logging.getLogger("enough.composure")

#: The SSE event every applied batch emits, so an open canvas stays live.
#: Defined in the pure core and re-exported here, which is where callers
#: expect to find it.
EVENT = comp_core.EVENT

Emit = Callable[[str, dict[str, Any]], Awaitable[None]]
Resolve = Callable[[str], Path]


def build_router(
    *,
    project_dir: Path,
    resolve_path: Resolve,
    emit: Emit,
) -> APIRouter:
    """Build the composure router. One call in `create_app` wires it all."""
    router = APIRouter()

    # ---------------------------------------------------------------- paths

    def _target(path: str) -> Path:
        """Resolve a project-relative `.comp` path. The suffix is required
        at the door — every route below can then assume it, and a typo gets
        a 400 that names the rule instead of a confusing 404."""
        rel = (path or "").strip()
        if not rel:
            raise HTTPException(400, "missing path")
        if not rel.endswith(comp_core.SUFFIX):
            raise HTTPException(
                400, f"not a composure path: {rel!r} must end in "
                     f"{comp_core.SUFFIX}")
        return resolve_path(rel)

    def _load(path: str) -> tuple[Path, comp_core.Composure]:
        target = _target(path)
        try:
            return target, comp_core.load(target)
        except ComposureError as e:
            raise HTTPException(404 if not target.exists() else 400, str(e)) from None

    async def _body(request: Request) -> dict[str, Any]:
        try:
            data = await request.json()
        except Exception:  # noqa: BLE001 — any malformed body is the same 400
            raise HTTPException(400, "expected a json body") from None
        return data if isinstance(data, dict) else {}

    async def _announce(result: comp_core.OpsResult, source: str) -> None:
        """The `composure` SSE event. `changed` names module ids; the
        sentinel `"ink"` means the stroke layer moved. `source` lets an open
        canvas ignore the echo of its own batch."""
        await emit(EVENT, {
            "path": result.path,
            "rev": result.rev,
            "changed": result.changed,
            "source": source,
            "created": result.created,
        })

    def _rel(target: Path) -> str:
        """The project-relative form of a resolved path, for echoing back."""
        try:
            return str(target.resolve().relative_to(project_dir.resolve())
                       ).replace(os.sep, "/")
        except ValueError:
            return target.name

    # ----------------------------------------------------------------- read

    @router.get("/api/composure")
    async def api_composure_get(path: str = Query(...)) -> dict[str, Any]:
        """The JSON document model plus its rev. The canvas renders from
        this and never from the file's HTML.

        Opening a composure that has a real path also stamps it as the
        project's `last` composure, which is what the `"last"` launch
        setting resolves to (P4d)."""
        target, comp = _load(path)
        rel = _rel(target)
        try:
            from . import project_meta
            project_meta.touch_composure(project_dir, rel)
        except Exception:  # noqa: BLE001 — never fail a read over bookkeeping
            log.exception("could not record the last-opened composure")
        return {"path": rel, "rev": comp.rev, "model": comp_core.model(comp)}

    @router.get("/api/composure/list")
    async def api_composure_list() -> dict[str, Any]:
        rows = await asyncio.to_thread(comp_core.list_composures, project_dir)
        return {"composures": rows}

    @router.get("/api/composure/forms")
    async def api_composure_forms() -> dict[str, Any]:
        return {"forms": comp_core.list_forms(project_dir)}

    @router.get("/api/composure/launch")
    async def api_composure_launch() -> dict[str, Any]:
        """What this project opens with. Resolves the stored setting against
        what is actually on disk: a missing target falls back to `blank` and
        says so in `notice`, rather than opening nothing."""
        from . import project_meta
        setting = project_meta.load(project_dir)["composure"]
        return _resolve_launch(setting)

    def _resolve_launch(setting: dict[str, Any]) -> dict[str, Any]:
        mode = setting.get("launch") or "blank"
        notice = ""
        if mode == "file":
            rel = setting.get("path") or ""
            if rel and (project_dir / rel).is_file():
                return {"launch": "file", "path": rel, "form": None, "notice": ""}
            notice = (f"the composure this project opened with ({rel or 'none'}) "
                      f"is no longer there — opening a blank page instead.")
        elif mode == "last":
            rel = setting.get("last") or ""
            if rel and (project_dir / rel).is_file():
                return {"launch": "file", "path": rel, "form": None, "notice": ""}
            notice = ("no previously-used composure is available — opening a "
                      "blank page instead.") if rel else ""
        elif mode == "form":
            name = setting.get("form") or ""
            if comp_core.form_path(name, project_dir) is not None:
                return {"launch": "form", "path": None, "form": name, "notice": ""}
            notice = (f"the form this project opened with ({name or 'none'}) is "
                      f"no longer installed — opening a blank page instead.")
        return {"launch": "blank", "path": None, "form": "blank", "notice": notice}

    @router.get("/api/composure/link-preview")
    async def api_composure_link_preview(
        path: str = Query(...), module: str = Query(...),
    ) -> dict[str, Any]:
        """What a link-in module shows in view mode, resolved server-side so
        the canvas never has to know how to read a wiki archive or a twin."""
        _target_path, comp = _load(path)
        m = comp.module(module)
        if m is None:
            raise HTTPException(404, f"no module {module!r} on this composure")
        return await asyncio.to_thread(_link_preview, m)

    def _link_preview(m: comp_core.Module) -> dict[str, Any]:
        out: dict[str, Any] = {"module": m.id, "type": m.type, "ok": False,
                               "title": "", "body": "", "detail": ""}
        if m.type in ("doc", "image") and not m.href:
            out["detail"] = "no file chosen yet"
            return out
        if m.type == "doc":
            target = resolve_path(m.href)
            if not target.is_file():
                out["detail"] = f"{m.href} is not in this project any more"
                return out
            out.update(ok=True, title=target.name,
                       body=_doc_head(target), path=m.href)
            return out
        if m.type == "image":
            target = resolve_path(m.href)
            if not target.is_file():
                out["detail"] = f"{m.href} is not in this project any more"
                return out
            out.update(ok=True, title=target.name, path=m.href,
                       blob=f"/api/file/blob?path={m.href}")
            return out
        if m.type == "wiki":
            return _wiki_preview(m, out)
        if m.type in ("weblink", "webframe"):
            out.update(ok=True, title=m.title or m.url, url=m.url,
                       host=_host_of(m.url))
            if m.type == "webframe" and m.cache:
                cached = project_dir / m.cache
                if cached.is_file():
                    out["body"] = cached.read_text(
                        encoding="utf-8", errors="replace")[:20000]
                    out["as_of"] = _mtime_iso(cached)
                else:
                    out["detail"] = "not fetched yet — press refresh"
            elif m.type == "webframe":
                out["detail"] = "not fetched yet — press refresh"
            return out
        out["detail"] = f"{m.type} modules have no link preview"
        return out

    def _doc_head(target: Path, lines: int = 40) -> str:
        """Title + the first ~40 rendered lines of a project document. A
        `.comp` previews as its own outline, which is what makes a board of
        boards navigable."""
        if target.suffix == comp_core.SUFFIX:
            try:
                return comp_core.outline(comp_core.load(target), _rel(target))
            except ComposureError as e:
                return f"(unreadable composure: {e})"
        try:
            text = target.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return f"(unreadable: {e})"
        body = [ln for ln in text.splitlines() if ln.strip()][:lines]
        return "\n".join(body)[:20000]

    def _wiki_preview(m: comp_core.Module, out: dict[str, Any]) -> dict[str, Any]:
        """The article's lead, through wikisink's own HTML→markdown pipeline
        — the same text `read_wiki_article` returns, so a wiki module and a
        readvisor quoting it agree. A missing archive is a normal state, not
        an error: say so and let the user install one."""
        if not m.article:
            out["detail"] = "no article chosen yet"
            return out
        try:
            from .wikisink import save as _wsave
            from .wikisink import zim as _zim
            article = _zim.get_article(path=m.article)
            text, _ok = _wsave.article_markdown(article)
        except KeyError:
            out["detail"] = f"{m.article} is not in the installed archive"
            return out
        except Exception as e:  # noqa: BLE001 — no archive is a normal state
            out["detail"] = f"wikisink is not available ({e})"
            return out
        lead = "\n\n".join(
            [p for p in (text or "").split("\n\n") if p.strip()][:4])
        out.update(ok=True, title=article.get("title") or m.article,
                   body=lead[:4000], article=m.article)
        return out

    def _host_of(url: str) -> str:
        import urllib.parse
        try:
            return urllib.parse.urlparse(url).hostname or ""
        except ValueError:
            return ""

    def _mtime_iso(p: Path) -> str:
        import datetime as dt
        return dt.datetime.fromtimestamp(
            p.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ---------------------------------------------------------------- write

    @router.post("/api/composure/ops")
    async def api_composure_ops(request: Request) -> dict[str, Any]:
        """Apply a batch of ops. The one write door.

        Body: `{path, base_rev, ops: [...], create?, form?, title?, source?,
        want_model?}`. A `base_rev` behind the file is not an error — the
        reply carries `stale: true` and the ids that changed underneath, so
        the client refreshes exactly those modules."""
        body = await _body(request)
        target = _target(body.get("path") or "")
        rel = _rel(target)
        source = str(body.get("source") or "ui")
        if source not in comp_core.SOURCES:
            raise HTTPException(
                400, f"unknown source {source!r}; one of "
                     f"{', '.join(comp_core.SOURCES)}")
        base_rev = body.get("base_rev")
        try:
            result = await asyncio.to_thread(
                comp_core.apply_ops,
                target,
                int(base_rev) if base_rev is not None else None,
                body.get("ops") or [],
                source=source,
                create=bool(body.get("create")),
                form=str(body.get("form") or "blank"),
                title=str(body.get("title") or ""),
                project_dir=project_dir,
                rel_path=rel,
            )
        except ComposureError as e:
            raise HTTPException(400, str(e)) from None
        except (TypeError, ValueError) as e:
            raise HTTPException(400, f"bad ops payload: {e}") from None
        await _announce(result, source)
        out: dict[str, Any] = {
            "path": rel,
            "rev": result.rev,
            "changed": result.changed,
            "stale": result.stale,
            "stale_changed": result.stale_changed,
            "created": result.created,
        }
        if result.stale or body.get("want_model"):
            out["model"] = comp_core.model(result.composure)
        return out

    @router.post("/api/composure/new")
    async def api_composure_new(request: Request) -> dict[str, Any]:
        """Describe a new composure WITHOUT writing it.

        The reply carries the path it will take and the model it starts
        from; the file appears on the first op batch that sets `create:
        true` and echoes `form`/`title` back. A composure the user opens and
        never touches therefore writes nothing at all, which is the whole
        point of the lazy rule."""
        body = await _body(request)
        form = str(body.get("form") or "blank")
        title = str(body.get("title") or "")
        try:
            comp = comp_core.new_composure(form, title, project_dir)
        except ComposureError as e:
            raise HTTPException(400, str(e)) from None
        rel = comp_core.new_path(project_dir, comp.title)
        return {
            "path": None,             # nothing on disk yet — see the docstring
            "pending_path": rel,
            "form": comp.form,
            "title": comp.title,
            "rev": 0,
            "model": comp_core.model(comp),
        }

    @router.post("/api/composure/rename")
    async def api_composure_rename(request: Request) -> dict[str, Any]:
        """Retitle a composure and rename its file to match, carrying the
        comments sidecar. Refuses to overwrite an existing file — a rename
        that silently ate another composure would be unrecoverable."""
        body = await _body(request)
        target, comp = _load(body.get("path") or "")
        title = str(body.get("title") or "").strip()
        if not title:
            raise HTTPException(400, "a composure needs a title")
        try:
            result = await asyncio.to_thread(
                comp_core.apply_ops, target, None,
                [{"op": "set_meta", "title": title}],
                source="ui", rel_path=_rel(target),
            )
        except ComposureError as e:
            raise HTTPException(400, str(e)) from None
        new_rel = _rel(target)
        keep_name = bool(body.get("keep_filename"))
        if not keep_name:
            dest = target.parent / (
                f"{comp_core.slugify(result.composure.title)}"
                f"-{(comp.created or '')[:10] or comp_core._today()}"
                f"{comp_core.SUFFIX}")
            if dest != target:
                if dest.exists():
                    raise HTTPException(
                        409, f"{dest.name} already exists — retitle without "
                             f"renaming the file, or pick another title")
                with comp_core.path_lock(target):
                    os.replace(target, dest)
                    comp_core.move_sidecars(target, dest)
                new_rel = _rel(dest)
        await _announce(result, "ui")
        return {"path": new_rel, "rev": result.rev,
                "title": result.composure.title}

    @router.post("/api/composure/save-as-form")
    async def api_composure_save_as_form(request: Request) -> dict[str, Any]:
        body = await _body(request)
        _target_path, comp = _load(body.get("path") or "")
        name = str(body.get("name") or "").strip()
        if not name:
            raise HTTPException(400, "a form needs a name")
        try:
            dest = await asyncio.to_thread(
                comp_core.save_as_form, project_dir, comp, name)
        except ComposureError as e:
            raise HTTPException(400, str(e)) from None
        return {"form": dest.stem, "path": _rel(dest),
                "forms": comp_core.list_forms(project_dir)}

    # -------------------------------------------------------------- webframe

    @router.post("/api/composure/webframe/refresh")
    async def api_composure_webframe_refresh(request: Request) -> dict[str, Any]:
        """Refresh a webframe module through the SAME broker-gated pipeline
        as the `fetch_url` tool — toggles, allowlist/Tor rule, HTML→markdown,
        cache under `rness/io/input/`. Never fetches without the broker's
        say-so, and returns the broker's denial text verbatim when refused,
        so the canvas can show the user exactly what a readvisor would see.
        """
        body = await _body(request)
        target, comp = _load(body.get("path") or "")
        rel = _rel(target)
        module_id = str(body.get("module") or "")
        m = comp.module(module_id)
        if m is None:
            raise HTTPException(404, f"no module {module_id!r} on this composure")
        if m.type != "webframe":
            raise HTTPException(
                400, f"module {m.id} is a {m.type} module, not a webframe")
        if not m.url:
            raise HTTPException(400, f"module {m.id} has no url yet")

        from . import tools as _tools
        try:
            got = await asyncio.to_thread(_tools.fetch_and_cache, project_dir, m.url)
        except _tools.FetchDenied as e:
            # The broker's own words, unwrapped and unparaphrased.
            return {"path": rel, "module": m.id, "ok": False,
                    "denied": True, "detail": str(e)}
        except _tools.FetchError as e:
            return {"path": rel, "module": m.id, "ok": False,
                    "denied": False, "detail": str(e)}

        text = got.content if isinstance(got.content, str) else ""
        rich = (comp_core.md_to_rich(text) if got.cache_ext == "md"
                else comp_core.sanitize_rich(text))
        try:
            result = await asyncio.to_thread(
                comp_core.apply_ops, target, None,
                [
                    {"op": "update_module", "id": m.id, "cache": got.cache_rel,
                     "title": m.title or got.title},
                    {"op": "set_page", "module": m.id, "n": 1, "rich": rich},
                ],
                source="enough", rel_path=rel,
            )
        except ComposureError as e:
            raise HTTPException(400, str(e)) from None
        broker.trace(
            project_dir, tool="composure", decision="webframe refresh",
            args={"path": rel, "module": m.id, "url": m.url},
            result_ok=True,
            result_summary=f"cached {got.cache_rel} (HTTP {got.status})",
        )
        await _announce(result, "enough")
        return {
            "path": rel, "module": m.id, "ok": True, "denied": False,
            "rev": result.rev, "status": got.status, "url": got.url,
            "cache": got.cache_rel, "title": got.title,
            "used_tor": got.used_tor, "rich": rich,
        }

    # -------------------------------------------------------------- comments

    @router.get("/api/composure/comments")
    async def api_composure_comments_get(path: str = Query(...)) -> dict[str, Any]:
        target = _target(path)
        return comp_core.load_comments(target, _rel(target))

    @router.post("/api/composure/comments")
    async def api_composure_comments_post(request: Request) -> dict[str, Any]:
        body = await _body(request)
        target = _target(body.get("path") or "")
        text = str(body.get("body") or "").strip()
        if not text:
            raise HTTPException(400, "a comment needs a body")
        comment_id = body.get("comment")
        if comment_id:
            # A reply to an existing thread.
            try:
                return comp_core.add_reply(target, str(comment_id), text,
                                           _rel(target))
            except KeyError:
                raise HTTPException(404, f"no comment {comment_id!r}") from None
        return comp_core.add_comment(target, text, body.get("anchor"),
                                     _rel(target))

    @router.patch("/api/composure/comments")
    async def api_composure_comments_patch(request: Request) -> dict[str, Any]:
        body = await _body(request)
        target = _target(body.get("path") or "")
        comment_id = str(body.get("id") or "")
        state = body.get("state")
        if state is not None and state not in comp_core.COMMENT_STATES:
            raise HTTPException(
                400, f"unknown comment state {state!r}; one of "
                     f"{', '.join(comp_core.COMMENT_STATES)}")
        try:
            return comp_core.update_comment(
                target, comment_id,
                body=body.get("body"),
                resolved=body.get("resolved"),
                state=state,
                doc_rel=_rel(target),
            )
        except KeyError:
            raise HTTPException(404, f"no comment {comment_id!r}") from None

    @router.delete("/api/composure/comments")
    async def api_composure_comments_delete(
        path: str = Query(...), id: str = Query(...),
    ) -> dict[str, Any]:
        target = _target(path)
        try:
            comp_core.delete_comment(target, id, _rel(target))
        except KeyError:
            raise HTTPException(404, f"no comment {id!r}") from None
        return {"ok": True, "id": id}

    return router
