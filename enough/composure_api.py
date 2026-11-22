"""The `/api/composure*` routes, as one `APIRouter` `create_app` mounts.

Why a separate module: `enough/composure.py` is the pure core and imports
no FastAPI, so it can be exercised (and reasoned about) without a web
layer. This file is the thin translation between HTTP and that core —
path resolution, status codes, the SSE fan-out — and nothing else. Every
refusal it emits is a `ComposureError` message from the core, so a client
and a readvisor read the same sentence.

`build_router()` takes the three things `create_app` owns and the core does
not: the project directory, the path-safety helper (`_resolve_project_path`,
which also carries the `canon:` scheme),
and `session.emit`. That is the whole seam — no globals, and the router is
constructible in a test with three lambdas.

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
        """Every composure, newest first. `startup` marks the one the
        project is set to open with (launch mode `file`), which the
        composures menu labels and a composure's settings modal ticks."""
        from . import project_meta
        rows = await asyncio.to_thread(comp_core.list_composures, project_dir)
        setting = project_meta.load(project_dir)["composure"]
        startup = setting["path"] if setting["launch"] == "file" else ""
        for row in rows:
            row["startup"] = bool(startup) and row["path"] == startup
        return {"composures": rows}

    @router.get("/api/composure/forms")
    async def api_composure_forms() -> dict[str, Any]:
        return {"forms": comp_core.list_forms(project_dir)}

    @router.get("/api/composure/launch")
    async def api_composure_launch() -> dict[str, Any]:
        """What this project opens with. Resolves the stored setting against
        what is actually on disk: a missing target falls back to `auto` and
        says so in `notice`, rather than opening nothing."""
        from . import project_meta
        setting = project_meta.load(project_dir)["composure"]
        return await asyncio.to_thread(_resolve_launch, setting)

    def _resolve_launch(setting: dict[str, Any]) -> dict[str, Any]:
        mode = setting.get("launch") or "auto"
        missing = ""
        if mode == "file":
            rel = setting.get("path") or ""
            if rel and (project_dir / rel).is_file():
                return {"launch": "file", "path": rel, "form": None, "notice": ""}
            missing = f"the startup composure ({rel}) is no longer there" if rel else ""
        elif mode == "last":
            rel = setting.get("last") or ""
            if rel and (project_dir / rel).is_file():
                return {"launch": "file", "path": rel, "form": None, "notice": ""}
            missing = "no previously-used composure is available" if rel else ""
        elif mode == "form":
            name = setting.get("form") or ""
            if comp_core.form_path(name, project_dir) is not None:
                return {"launch": "form", "path": None, "form": name, "notice": ""}
            missing = (f"the form this project opened with ({name or 'none'}) "
                       f"is no longer installed")
        elif mode == "new":
            return {"launch": "blank", "path": None, "form": "blank", "notice": ""}
        # `auto`, and where every other mode lands when its target is gone.
        rel = _auto_pick(setting.get("last") or "")
        if rel:
            notice = f"{missing} — opening {Path(rel).name} instead." if missing else ""
            return {"launch": "file", "path": rel, "form": None, "notice": notice}
        notice = f"{missing} — opening a blank page instead." if missing else ""
        return {"launch": "blank", "path": None, "form": "blank", "notice": notice}

    def _auto_pick(last: str) -> str:
        """`auto`'s answer: the only composure with anything in it, else the
        last one used (when it still has something in it), else the newest.
        "" when nothing has content — an empty file is no better than a new
        page. Project forms are templates, not the user's composures."""
        forms = comp_core.PROJECT_FORMS_REL + "/"
        rows = [r for r in comp_core.list_composures(project_dir)
                if r["content"] and not r["path"].startswith(forms)]
        if len(rows) > 1 and any(r["path"] == last for r in rows):
            return last
        return rows[0]["path"] if rows else ""

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
        `.comp` previews as its own outline, which is what makes a plane of
        planes navigable."""
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

        Body: `{path, base_rev, ops: [...], create?, form?, title?,
        want_model?}`; the source is always `ui` (a `source` other than `ui`
        is refused). A `base_rev` behind the file is not an error — the
        reply carries `stale: true` and the ids that changed underneath, so
        the client refreshes exactly those modules."""
        body = await _body(request)
        target = _target(body.get("path") or "")
        rel = _rel(target)
        # 0.9 (route guards): the server sets the source. A batch over HTTP is the page's, `ui`; the readvisor writes
        # through its tools, the council and enough itself through the core, never this door. A body that names
        # another source is refused, not relabelled, so a client that thought it could claim one is told.
        claimed = body.get("source")
        if claimed not in (None, "", "ui"):
            raise HTTPException(
                403, f"source {str(claimed)!r} is not taken here: the server sets a batch's source, and one sent over "
                     f"HTTP is the page's (ui); the readvisor changes a composure through its tools")
        source = "ui"
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
                old_rel = new_rel
                if dest.exists():
                    raise HTTPException(
                        409, f"{dest.name} already exists — retitle without "
                             f"renaming the file, or pick another title")
                with comp_core.path_lock(target):
                    os.replace(target, dest)
                    comp_core.move_sidecars(target, dest)
                new_rel = _rel(dest)
                try:
                    from . import project_meta
                    project_meta.retarget_composure(project_dir, old_rel, new_rel)
                except Exception:  # noqa: BLE001 — the rename itself succeeded
                    log.exception("could not carry the launch setting across a rename")
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
        except ComposureError as e:
            raise HTTPException(409, str(e)) from None
        return {"ok": True, "id": id}

    return router


# ---------------------------------------------------------------------------
# The scaffold's lock, check, findings and export (0.8, E5 and E6)
# ---------------------------------------------------------------------------

def build_scaffold_router(
    *,
    project_dir: Path,
    resolve_path: Resolve,
    emit: Emit,
    jobs: Any = None,
    canon_mode: Callable[..., Awaitable[tuple[str, str]]] | None = None,
    start_job: Callable[..., dict] | None = None,
    model_complete: Callable[..., Any] | None = None,
    llm_url: str | None = None,
) -> APIRouter:
    """`/api/composure/scaffold*`: the scaffold's state, lock, unlock, check (a CanonJob of kind `scaffold`, started
    as the fabulap's build is), check cancel, accept, decline and export. Mounted after the canon jobs exist, so it
    is its own router beside `build_router`; without `jobs`/`start_job` (a test's three lambdas) the check routes
    answer 503 and everything else works.

    Every body carries `path` (a project-relative `.comp`). The person is the only source here: these are the
    page's buttons, and the readvisor has no tool for any of them."""
    from . import scaffold_check as _check
    from . import scaffold_export as _export
    from . import scaffolder as _sc

    router = APIRouter()

    def _target(path: str) -> Path:
        rel = (path or "").strip()
        if not rel or not rel.endswith(comp_core.SUFFIX):
            raise HTTPException(400, f"not a composure path: {rel!r} must end in {comp_core.SUFFIX}")
        target = resolve_path(rel)
        if not target.is_file():
            raise HTTPException(404, f"no composure at {rel}")
        return target

    def _rel(target: Path) -> str:
        try:
            return str(target.resolve().relative_to(project_dir.resolve())).replace(os.sep, "/")
        except ValueError:
            return target.name

    async def _body(request: Request) -> dict[str, Any]:
        try:
            data = await request.json()
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "expected a json body") from None
        return data if isinstance(data, dict) else {}

    def _job_for(target: Path) -> str | None:
        return jobs.running_for(str(target.resolve())) if jobs is not None else None

    def _state(target: Path) -> dict[str, Any]:
        comp = comp_core.load(target)
        view = comp_core.scaffold_view(comp)
        if view is None:
            raise ComposureError(f"{target.name} is not a scaffold")
        rel = _rel(target)
        doc = comp_core.load_comments(target, rel)
        job_id = _job_for(target)
        return {
            "path": rel, "rev": comp.rev, "scaffold": view, "locked": comp_core.scaffold_locked(comp),
            "empty": comp_core.empty_boxes(comp), "findings": comp_core.list_findings(target, rel),
            "check": doc.get("check"), "job": jobs.snapshot(job_id) if job_id else None,
            "exports": list(_export.FORMATS[view["thing"]]),
        }

    async def _announce(rel: str, rev: int, changed: list[str], **more: Any) -> None:
        await emit(EVENT, {"path": rel, "rev": rev, "changed": changed, "source": "ui", "created": False, **more})

    @router.get("/api/composure/scaffold")
    async def api_scaffold_state(path: str = Query(...)) -> dict[str, Any]:
        """The scaffold as its page needs it: the view, whether it is locked, the empty boxes (what the readvisor
        names before a lock), the findings, the last check, a running check job, and the formats it exports as."""
        target = _target(path)
        try:
            return await asyncio.to_thread(_state, target)
        except ComposureError as e:
            raise HTTPException(400, str(e)) from None

    @router.post("/api/composure/scaffold/lock")
    async def api_scaffold_lock(request: Request) -> dict[str, Any]:
        """`{path, empty?: [box ids the person was shown], base_rev?}` → the state, locked. Refused (400) while an
        empty box is not in `empty`, naming it."""
        body = await _body(request)
        target = _target(str(body.get("path") or ""))
        rel = _rel(target)
        base_rev = body.get("base_rev")
        try:
            result = await asyncio.to_thread(
                comp_core.apply_ops, target, int(base_rev) if base_rev is not None else None,
                [{"op": "lock_scaffold", "empty": body.get("empty") or []}], source="ui",
                project_dir=project_dir, rel_path=rel)
        except ComposureError as e:
            raise HTTPException(400, str(e)) from None
        await _announce(rel, result.rev, result.changed, scaffold="locked")
        return await asyncio.to_thread(_state, target)

    @router.post("/api/composure/scaffold/unlock")
    async def api_scaffold_unlock(request: Request) -> dict[str, Any]:
        """`{path}` → `{path: the new version's path, parent, version, state}`. The locked file stays as it is."""
        body = await _body(request)
        target = _target(str(body.get("path") or ""))
        if _job_for(target):
            raise HTTPException(409, "the check is running on this scaffold; wait for it, or cancel it")
        try:
            dest, comp = await asyncio.to_thread(comp_core.unlock_scaffold, target, project_dir)
        except ComposureError as e:
            raise HTTPException(400, str(e)) from None
        rel = _rel(dest)
        await emit(EVENT, {"path": rel, "rev": comp.rev, "changed": [], "source": "ui", "created": True})
        return {"path": rel, "parent": _rel(target), "version": (comp.scaffold or {}).get("version"),
                "state": await asyncio.to_thread(_state, dest)}

    def _complete_for(route: str) -> Callable[..., Any] | None:
        from . import llm as _llm
        from . import thym_host as _host
        if route == "local" and _llm._current_slot() != "opro-api":
            return model_complete
        return _host.route_complete(route, llm_url=llm_url, project_dir=project_dir)

    @router.post("/api/composure/scaffold/check")
    async def api_scaffold_check(request: Request) -> dict[str, Any]:
        """`{path, mode?: auto|model|rules, route?: local|cloud}` → `{job}`: the check as a CanonJob of kind
        `scaffold`, keyed by the composure. Agent-free, or no model answering, runs the rules pass and says so.
        409 when the scaffold is not locked or a check is already running on it."""
        if jobs is None or start_job is None or canon_mode is None:
            raise HTTPException(503, "the check needs the job runner, which this server was built without")
        body = await _body(request)
        target = _target(str(body.get("path") or ""))
        rel = _rel(target)
        try:
            await asyncio.to_thread(_check.target_of, target)
        except _check.CheckError as e:
            raise HTTPException(e.status, str(e)) from None
        except ComposureError as e:
            raise HTTPException(400, str(e)) from None
        want = str(body.get("mode") or "auto").strip().lower()
        if want not in ("auto", "model", "rules"):
            raise HTTPException(400, "mode is auto, model or rules")
        route = str(body.get("route") or "local").strip().lower()
        if route not in ("local", "cloud"):
            raise HTTPException(400, f"route is local or cloud, not {route!r}")
        if want == "rules":
            mode, why = "rules", ""
        else:
            try:
                mode, why = await canon_mode(route)
            except TypeError:
                mode, why = await canon_mode()
            if want == "model" and mode != "model":
                raise HTTPException(409, f"no model is answering ({why})")
        complete = _complete_for(route) if mode == "model" else None

        def work(ctx: Any) -> dict[str, Any]:
            return _check.run_check(target, rel, mode=mode, why=why, complete=complete,
                                    progress=lambda f: ctx.progress(f), check=ctx.check)

        on_cloud = " on the cloud" if mode == "model" and route == "cloud" else ""
        return start_job(kind=_check.JOB_KIND, path=rel, mode=mode, why=why, work=work,
                         key=str(target.resolve()), doing=f"checking {target.name}{on_cloud}")

    @router.post("/api/composure/scaffold/check/cancel")
    async def api_scaffold_check_cancel(request: Request) -> dict[str, Any]:
        """`{path}` → the job's snapshot, cancelling: the box being read finishes, then it stops, and no finding is
        written. 409 when no check is running on it."""
        body = await _body(request)
        target = _target(str(body.get("path") or ""))
        job_id = _job_for(target)
        if not job_id:
            raise HTTPException(409, f"no check of {target.name} is running")
        try:
            return jobs.cancel(job_id)
        except Exception as e:  # noqa: BLE001 - CanonJobError carries its status
            raise HTTPException(getattr(e, "status", 409), str(e)) from None

    async def _answer(request: Request, answer: str) -> dict[str, Any]:
        body = await _body(request)
        target = _target(str(body.get("path") or ""))
        rel = _rel(target)
        fid = str(body.get("finding") or "").strip()
        if not fid:
            raise HTTPException(400, "which finding? send 'finding': its id (f1, f2, …)")
        try:
            finding, result = await asyncio.to_thread(
                comp_core.answer_finding, target, fid, answer, doc_rel=rel, project_dir=project_dir)
        except KeyError:
            raise HTTPException(404, f"no finding {fid!r} on {rel}") from None
        except ComposureError as e:
            raise HTTPException(409, str(e)) from None
        if result is not None:
            await _announce(rel, result.rev, result.changed, finding=fid)
            return {"finding": finding, "rev": result.rev, "changed": result.changed}
        comp = await asyncio.to_thread(comp_core.load, target)
        await _announce(rel, comp.rev, [], finding=fid)
        return {"finding": finding, "rev": comp.rev, "changed": []}

    @router.post("/api/composure/scaffold/accept")
    async def api_scaffold_accept(request: Request) -> dict[str, Any]:
        """`{path, finding}` → `{finding, rev, changed}`: the fix applied as the person to the quoted span only
        (the one change a locked scaffold takes), and recorded on the finding. 409 when the finding is answered
        already, cannot be checked, has no fix, or its span is gone, stands twice or crosses formatting."""
        return await _answer(request, "accept")

    @router.post("/api/composure/scaffold/decline")
    async def api_scaffold_decline(request: Request) -> dict[str, Any]:
        """`{path, finding}` → `{finding, rev, changed: []}`: the person keeps their words; recorded."""
        return await _answer(request, "decline")

    @router.post("/api/composure/scaffold/export")
    async def api_scaffold_export(request: Request) -> dict[str, Any]:
        """`{path, as: html|pdf|pptx|md, reference?: a project-relative .pptx}` → `{written, path, as, thing,
        bytes, pages?, left_out, locked, open_findings}`: a new file beside the composure, never one written over.
        `as` must be one of the thing's formats (a page: html, pdf; a deck: pptx, pdf; a document: md, pdf)."""
        body = await _body(request)
        target = _target(str(body.get("path") or ""))
        reference = None
        if body.get("reference"):
            reference = resolve_path(str(body["reference"]))
            if reference.suffix.lower() != ".pptx":
                raise HTTPException(400, "a reference deck is a .pptx")
        try:
            out = await asyncio.to_thread(_export.export, target, str(body.get("as") or ""),
                                          project_dir=project_dir, reference=reference)
        except _export.ExportError as e:
            raise HTTPException(e.status, str(e)) from None
        except ComposureError as e:
            raise HTTPException(400, str(e)) from None
        out["path"] = _rel(Path(out["path"]))
        out["open_findings"] = sum(1 for f in comp_core.list_findings(target, _rel(target))
                                   if f.get("status") == "open")
        return out

    # ------------------------------------------------ the state, out and in (0.9)
    # The scaffolder's one-file state (`defaults/skills/scaffolder/references/state.md`), written and read by the
    # skill's own `scaffold_state.py` (loaded by `scaffolder.state_module`: one writer, one parser). Both doors are
    # the person's: the page's buttons. The words come in as the person's ops (`ui`), never the readvisor's.

    @router.get("/api/composure/scaffold/state")
    async def api_scaffold_state_file(path: str = Query(...)) -> dict[str, Any]:
        """`?path=` → `{path, name, text}`: the scaffold's state file, exactly as the skill's writer writes it.
        Locked or open."""
        target = _target(path)
        rel = _rel(target)
        try:
            text = await asyncio.to_thread(_sc.state_text, target, rel)
        except (ComposureError, ValueError) as e:
            raise HTTPException(400, str(e)) from None
        return {"path": rel, "name": _export.out_path(target, "scaffold.md").name, "text": text}

    @router.post("/api/composure/scaffold/state/out")
    async def api_scaffold_state_out(request: Request) -> dict[str, Any]:
        """`{path}` → `{written, path, bytes}`: the state file written beside the composure as a new file
        (`<name>.scaffold.md`, then `<name>-2.scaffold.md` …), never one written over. Locked or open."""
        body = await _body(request)
        target = _target(str(body.get("path") or ""))
        rel = _rel(target)

        def work() -> Path:
            data = _sc.state_text(target, rel).encode("utf-8")
            out = _export.out_path(target, "scaffold.md")
            _export._write_new(out, data)
            return out

        try:
            out = await asyncio.to_thread(work)
        except (ComposureError, ValueError) as e:
            raise HTTPException(400, str(e)) from None
        except _export.ExportError as e:
            raise HTTPException(e.status, str(e)) from None
        return {"written": True, "path": _rel(out), "bytes": out.stat().st_size}

    @router.post("/api/composure/scaffold/state/in")
    async def api_scaffold_state_in(request: Request) -> dict[str, Any]:
        """`{path, text, apply?, replace?, base_rev?, create?}`: a state file the person picked, read by the one
        parser. Without `apply`, what it would bring: how many of its boxes the scaffold has (`matching`), how many
        are new, how many of the scaffold's boxes it has no words for, and which boxes hold other words already
        (`replace`). With `apply`, the layout and the words come in as one batch of the person's ops (`ui`), and the
        reply carries `ops` and `undo` (one undo step for the page) and the new `model`. Boxes in `replace` must be
        answered: `replace` lists the ones to write over, and the rest keep their words; a reply without it is 409.
        A plectrum, a file that does not read, a state for another thing than the scaffold holds, or a locked
        scaffold is refused with a sentence. `create` makes the composure from the scaffold form first."""
        body = await _body(request)
        rel_in = str(body.get("path") or "").strip()
        if not rel_in.endswith(comp_core.SUFFIX):
            raise HTTPException(400, f"not a composure path: {rel_in!r} must end in {comp_core.SUFFIX}")
        target = resolve_path(rel_in)
        create = not target.is_file()
        if create and not body.get("create"):
            raise HTTPException(404, f"no composure at {rel_in}")
        text = body.get("text")
        if not isinstance(text, str) or not text.strip():
            raise HTTPException(400, "send the state file's text in 'text'")
        if len(text) > _STATE_MAX_CHARS:
            raise HTTPException(413, f"that file is larger than a scaffold's state can be "
                                     f"({_STATE_MAX_CHARS:,} characters)")
        rel = _rel(target)
        apply = bool(body.get("apply"))
        raw_replace = body.get("replace")
        if raw_replace is not None and not isinstance(raw_replace, list):
            raise HTTPException(400, "'replace' is the list of box ids whose words the state may write over")
        replace = [str(x) for x in raw_replace or []]

        def work() -> dict[str, Any]:
            model = _sc.read_state(text)
            if create:
                comp = comp_core.new_composure("scaffold", model.meta["title"], project_dir)
                here = 0
            else:
                comp = comp_core.load(target)
                here = len(comp_core.list_findings(target, rel))
            plan = _sc.bring_plan(model, comp, replace=replace, findings_here=here)
            if not apply:
                return {"path": rel, "preview": True, "rev": None if create else comp.rev, **plan.summary()}
            base_rev = body.get("base_rev")
            if not create and base_rev is not None and int(base_rev) != comp.rev:
                raise _sc.BringError("the scaffold changed since the state was read against it; read the state "
                                     "in again to see what it would bring now.", 409)
            if plan.replace and raw_replace is None:
                names = ", ".join(r["name"] for r in plan.replace)
                raise _sc.BringError(f"these boxes hold other words of yours already: {names}. Say which the state "
                                     f"may write over ('replace': their ids; an empty list keeps your words in "
                                     f"all of them).", 409)
            created = False
            if create:
                made = comp_core.apply_ops(target, None, [{"op": "set_scaffold", "thing": model.meta["thing"]}],
                                           source="ui", create=True, form="scaffold", title=model.meta["title"],
                                           project_dir=project_dir, rel_path=rel)
                created = made.created
                comp = made.composure
                plan = _sc.bring_plan(model, comp, replace=replace, findings_here=0)
            result = None
            if plan.ops:
                result = comp_core.apply_ops(target, None, plan.ops, source="ui", project_dir=project_dir,
                                             rel_path=rel, carried_plec_by=plan.plec_by)
            after = result.composure if result is not None else comp
            _sc.plectrum_path(target).write_text(_sc.state_module().dumps(model, "plectrum"), encoding="utf-8")
            brought = 0
            if model.findings:
                checked = model.meta.get("checked")
                stamp = {"at": checked, "version": int(model.meta.get("version") or 1)} if checked else None
                brought = comp_core.carry_findings(target, _sc.findings_from_state(model, after), stamp, rel)
            return {"path": rel, "applied": True, "created": created or bool(result and result.created),
                    "rev": after.rev, "changed": result.changed if result is not None else [],
                    "ops": plan.ops, "undo": None if plan.locked or result is None else _sc.undo_ops(comp, after),
                    "model": comp_core.model(after), **plan.summary(), "findings_brought": brought}

        try:
            out = await asyncio.to_thread(work)
        except _sc.BringError as e:
            raise HTTPException(e.status, str(e)) from None
        except ComposureError as e:
            raise HTTPException(400, str(e)) from None
        if out.get("applied"):
            await emit(EVENT, {"path": rel, "rev": out["rev"], "changed": out["changed"], "source": "ui",
                               "created": out["created"]})
        return out

    return router


#: The largest state file the state-in door reads (a composure's 200 modules at their caps fit well inside).
_STATE_MAX_CHARS = 2_000_000
