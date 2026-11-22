"""Reading and writing project files: reveal, view, customize, raw (`/api/reveal`, `/api/file*`), new folders and files, highlights (`/api/highlights`), saving, undo.

Moved out of `enough/server.py`'s `create_app` in 0.8 (lane W2-SV), code unchanged: `build_router` is the old
factory's closure for this group, and the names it closed over come in on `ctx`."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse

from .. import canon as _canon
from .. import convert as _convert
from ..tools import _read_allowlist, _under_any
from .common import AppContext
from ..server import _escape_html, _store_prefix

#: 0.9: the save's answer carries this header (value `1`) when it replaced a link to a shared file with the project's
#: own copy (`_replace_shared_link`); the page says so in one line.
UNLINKED_HEADER = "X-Enough-Unlinked"


def build_router(ctx: AppContext) -> APIRouter:
    router = APIRouter()
    _is_external_symlink = ctx._is_external_symlink
    _is_request_file = ctx._is_request_file
    _is_role_file = ctx._is_role_file
    _is_skill_file = ctx._is_skill_file
    _resolve_project_path = ctx._resolve_project_path
    project_dir = ctx.project_dir
    session = ctx.session

    @router.get("/api/reveal", response_class=HTMLResponse)
    async def api_reveal(path: str = Query(...)) -> HTMLResponse:
        """Pop open the platform file manager at the given path — Finder
        via `open -R` on macOS, whatever `xdg-open` resolves to on Linux.
        Used by the agent to drop clickable links into chat completions —
        e.g. "your new skill lives here:
        [Open in Finder](/api/reveal?path=rness/skills/foo)".

        Path-safety rules mirror `read_file`: project-relative paths are
        always OK; absolute (or `~`-prefixed) paths must resolve under
        the read-allowlist from `rness/policies/allowlists.md` (which
        transparently includes file-rw prefixes too)."""
        if not (sys.platform == "darwin" or sys.platform.startswith("linux")):
            raise HTTPException(
                501,
                f"reveal-in-file-manager needs macOS (`open -R`) or Linux "
                f"(`xdg-open`); this machine reports {sys.platform!r}.",
            )
        raw = path.strip()
        if not raw:
            raise HTTPException(400, "missing path")
        # Resolve to an absolute path. `~` expansion is convenient for
        # the agent when emitting `~/enough/...` links.
        p = Path(raw).expanduser()
        if p.is_absolute():
            target = p.resolve(strict=False)
            project_root = project_dir.resolve(strict=False)
            try:
                target.relative_to(project_root)
                inside_project = True
            except ValueError:
                inside_project = False
            if not inside_project:
                allowlist = _read_allowlist(project_dir)
                if not _under_any(target, allowlist):
                    raise HTTPException(
                        403,
                        f"{raw} is outside the project and off the read-"
                        "allowlist. add its prefix to rness/policies/"
                        "allowlists.md or use a project-relative path.",
                    )
        else:
            if ".." in p.parts:
                raise HTTPException(400, "invalid path")
            target = (project_dir / p).resolve(strict=False)
            try:
                target.relative_to(project_dir.resolve(strict=False))
            except ValueError:
                raise HTTPException(400, "path escapes project root")
        if not target.exists():
            raise HTTPException(404, f"not found: {target}")
        if sys.platform == "darwin":
            # `open` opens files in the default app and reveals folders in
            # Finder. Use `-R` to highlight a file in its parent folder
            # rather than opening it directly (more useful for "go check
            # out this newly-created file" cases).
            manager = "Finder"
            cmd = ["/usr/bin/open"]
            if target.is_file():
                cmd.extend(["-R", str(target)])
            else:
                cmd.append(str(target))
        else:
            import shutil as _shutil
            xdg = _shutil.which("xdg-open")
            if not xdg:
                raise HTTPException(
                    501,
                    "xdg-open isn't installed, so there's no way to ask this "
                    "desktop to open a folder. `sudo apt install xdg-utils` "
                    "(Debian/Ubuntu) or `sudo dnf install xdg-utils` (Fedora).",
                )
            # xdg-open has no `-R` equivalent — there is no cross-desktop
            # "select this file in its folder" verb. Opening a file would
            # launch it in its default application, which is emphatically
            # not what "reveal" means, so a file reveals as its PARENT
            # folder. Same intent, one click of divergence from macOS.
            manager = "your file manager"
            cmd = [xdg, str(target if target.is_dir() else target.parent)]
        try:
            subprocess.Popen(cmd)
        except OSError as e:
            raise HTTPException(500, f"open failed: {e}")
        # Tiny auto-closing page so the user's click doesn't leave a
        # blank tab behind. Falls back to a manual close-this-tab note.
        return HTMLResponse(
            "<!doctype html><meta charset=utf-8>"
            f"<title>Opened in {_escape_html(manager)}</title>"
            "<style>body{font-family:system-ui;padding:24px;color:#555}</style>"
            "<p>Opened <code>" + _escape_html(str(target)) + "</code> "
            f"in {_escape_html(manager)}. You can close this tab.</p>"
            "<script>setTimeout(()=>window.close(), 200)</script>"
        )

    @router.get("/api/file", response_class=HTMLResponse)
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
            # Same pattern as skills — readvisors are global, edited at
            # source. (A readvisor the user forged themselves lives in
            # ~/enough/readvisors/ instead; the note names the shipped case
            # because that is the one a user is most likely looking at.)
            sym_note = (
                '<div class="symlink-note">'
                'readvisor file — edit globally at '
                '<code>~/enough/defaults/readvisors/</code>; '
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
                '<button class="edit-btn" onclick="enterEditMode()">edit mode</button>'
            )
        # Review-mode button: only meaningful for markdown-ish text files.
        # Renders LEFT of the edit button, with a contrasting accent fill
        # so it stands out from the muted action row. Plain-text files
        # would technically render fine too (no markdown ⇒ paragraphs),
        # but for v1 we gate to .md/.markdown to keep the button's
        # promise honest.
        review_btn = ""
        lower = path.lower()
        if lower.endswith((".md", ".markdown")) and not _is_skill_file(path) and not _is_role_file(path):
            review_btn = (
                f'<button class="review-btn" '
                f'onclick="enterReviewMode(\'{_escape_html(path)}\')">'
                f'review mode</button>'
            )
        if lower.endswith(".girraph"):
            # Girraphs get their own editable panel; raw edit mode is
            # blocked for them (node-level ops only), so the girraph
            # button replaces the edit button.
            review_btn = (
                f'<button class="review-btn" '
                f'onclick="enterGirraphMode(\'{_escape_html(path)}\')">'
                f'🦒 girraph panel</button>'
            )
            action_btn = ""
        return HTMLResponse(
            f'<div class="file-path" data-path="{_escape_html(path)}">{_escape_html(path)}</div>'
            f'{sym_note}'
            f'<div class="preview-actions">'
            f'  {mark_done_btn}'
            f'  {review_btn}'
            f'  {action_btn}'
            f'</div>'
            f'<pre class="file-body">{_escape_html(text)}</pre>'
        )

    @router.post("/api/file/customize", response_class=HTMLResponse)
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

    @router.get("/api/file/raw", response_class=PlainTextResponse)
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

    # ---------- Tree create operations (new folder / new file) ----------
    #
    # Backing for the option-click context menu in the sidebar tree.
    # Validation is intentionally strict: names are single path segments
    # (no slashes, no `..`, no leading dot beyond the dotfile pattern,
    # no NUL). The parent must already exist as a directory inside the
    # project root (or inside an in-tree symlink target).
    # Existing entries are never clobbered.

    def _validate_new_name(name: str) -> str:
        name = (name or "").strip()
        if not name:
            raise HTTPException(400, "name is required")
        if "/" in name or "\\" in name or "\x00" in name:
            raise HTTPException(400, "name may not contain path separators")
        if name in (".", ".."):
            raise HTTPException(400, "invalid name")
        if len(name) > 255:
            raise HTTPException(400, "name too long")
        return name

    @router.post("/api/file/new-folder")
    async def api_file_new_folder(request: Request) -> dict[str, Any]:
        """Create a new directory at `<parent>/<name>`. Body JSON:
        {"parent": "rness/io/output", "name": "drafts"}. Parent must be
        an existing directory inside the project. Returns the new
        project-relative path."""
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "expected json body") from None
        parent_rel = (body.get("parent") or "").strip()
        name = _validate_new_name(body.get("name") or "")
        # Empty parent means project root, which is fine.
        parent = _resolve_project_path(parent_rel) if parent_rel else project_dir.resolve()
        if not parent.exists() or not parent.is_dir():
            raise HTTPException(404, "parent directory not found")
        target = parent / name
        if target.exists():
            raise HTTPException(409, f"already exists: {name}")
        try:
            target.mkdir()
        except OSError as e:
            raise HTTPException(500, f"could not create folder: {e}") from None
        return {"ok": True, "path": f"{parent_rel.rstrip('/')}/{name}" if parent_rel else name}

    @router.post("/api/file/new-file")
    async def api_file_new_file(request: Request) -> dict[str, Any]:
        """Create a new empty file at `<parent>/<name>`. Same shape as
        new-folder. The client may pass a bare name (e.g. `notes`); we
        append `.md` if no `.md`/`.markdown` extension is present, since
        the context-menu entry is "new md file" by intent."""
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "expected json body") from None
        parent_rel = (body.get("parent") or "").strip()
        name = _validate_new_name(body.get("name") or "")
        lower = name.lower()
        if not (lower.endswith(".md") or lower.endswith(".markdown")):
            name = name + ".md"
        parent = _resolve_project_path(parent_rel) if parent_rel else project_dir.resolve()
        if not parent.exists() or not parent.is_dir():
            raise HTTPException(404, "parent directory not found")
        target = parent / name
        if target.exists():
            raise HTTPException(409, f"already exists: {name}")
        try:
            target.write_text("", encoding="utf-8")
        except OSError as e:
            raise HTTPException(500, f"could not create file: {e}") from None
        return {"ok": True, "path": f"{parent_rel.rstrip('/')}/{name}" if parent_rel else name}

    # ---------- Highlights (review-mode color metadata) ----------
    #
    # Per-doc CRUD over the dotted JSON sidecar managed by
    # `enough.highlights`. The review-mode JS calls these on entry
    # (GET) and on every color-button toggle (POST/DELETE). Returns
    # plain JSON; the journal entry is written by the highlights
    # module so each call shows up alongside tool-call traces in
    # `rness/knowledge/session-logs/<date>-broker.md`.
    from .. import highlights as _highlights

    def _highlight_doc(path: str) -> str:
        """The `doc_rel` the highlights module takes. A project path passes
        through; a Canon path (`canon:`) becomes its absolute
        resolved location, so the sidecar lands beside the stored document
        (highlights composes `project_dir / doc_rel`, and an absolute
        `doc_rel` wins that join) instead of in a folder named after the
        prefix inside the project. The traversal guard runs either way."""
        target = _resolve_project_path(path)
        return str(target) if _store_prefix(path) else path

    @router.get("/api/highlights")
    async def api_highlights_get(path: str = Query(...)) -> dict[str, Any]:
        # Resolve through the same path-safety helper as /api/file so
        # off-allowlist paths get the same 4xx behavior.
        items = _highlights.load_highlights(project_dir, _highlight_doc(path))
        return {"path": path, "highlights": items}

    @router.post("/api/highlights")
    async def api_highlights_post(request: Request) -> dict[str, Any]:
        form = await request.form()
        path = (form.get("path") or "").strip()
        if not path:
            raise HTTPException(400, "missing path")
        doc = _highlight_doc(path)
        color = (form.get("color") or "").strip()
        snippet = form.get("snippet") or ""
        if not snippet:
            raise HTTPException(400, "missing snippet")
        before_anchor = form.get("before_anchor") or ""
        after_anchor = form.get("after_anchor") or ""
        # src_start / src_end are optional ints; missing/blank ⇒ None.
        def _maybe_int(name: str) -> int | None:
            v = form.get(name)
            if v is None or v == "":
                return None
            try:
                return int(v)
            except ValueError:
                raise HTTPException(400, f"{name} must be int") from None
        try:
            entry = _highlights.add_highlight(
                project_dir, doc,
                color=color,
                snippet=snippet,
                before_anchor=before_anchor,
                after_anchor=after_anchor,
                src_start=_maybe_int("src_start"),
                src_end=_maybe_int("src_end"),
            )
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        return {"path": path, "highlight": entry}

    @router.delete("/api/highlights")
    async def api_highlights_delete(
        path: str = Query(...),
        id: str = Query(...),
    ) -> dict[str, Any]:
        ok = _highlights.delete_highlight(project_dir, _highlight_doc(path), id)
        if not ok:
            raise HTTPException(404, "no such highlight id")
        return {"path": path, "id": id, "removed": True}

    @router.patch("/api/highlights")
    async def api_highlights_patch(request: Request) -> dict[str, Any]:
        """Mutate fields on an existing highlight — primarily the
        color, used by the per-highlight handle popup (Phase 5c) when
        the user clicks a different circle. Whitelist of safe fields
        is enforced inside highlights.update_highlight."""
        form = await request.form()
        path = (form.get("path") or "").strip()
        hl_id = (form.get("id") or "").strip()
        if not path or not hl_id:
            raise HTTPException(400, "missing path or id")
        doc = _highlight_doc(path)
        changes: dict[str, Any] = {}
        if (color := form.get("color")):
            color = color.strip().lower()
            if color not in _highlights.ALLOWED_COLORS:
                raise HTTPException(
                    400,
                    f"unknown color {color!r}; allowed: "
                    + ", ".join(_highlights.ALLOWED_COLORS),
                )
            changes["color"] = color
        if not changes:
            raise HTTPException(400, "no updatable fields supplied")
        updated = _highlights.update_highlight(project_dir, doc, hl_id, **changes)
        if updated is None:
            raise HTTPException(404, "no such highlight id")
        return {"path": path, "highlight": updated}

    def _replace_shared_link(path: str, target: Path) -> bool:
        """Remove the link at `target` when it is a link to a shared file, so
        the write that follows makes the project's own file. True when a link
        was removed.

        Shared: `rness/paradigms/<n>.md` and `rness/metaparadigms/<n>.md`
        whatever they point at (the readvisor's rule, `tools._replace_global_link`),
        and any file link into this install's `defaults/` (the policies the
        skeleton links, a paradigm linked by hand). The link must be the file
        itself, in a folder of the project that is not itself a link. A link
        to anything else (a file of the person's own outside the project, a
        Canon path) keeps writing through, as before. Skills and readvisors
        never get here: the route refuses them."""
        if _store_prefix(path) or not target.is_symlink():
            return False
        rel = Path(path)
        if rel.is_absolute() or ".." in rel.parts:
            return False
        root = project_dir.resolve()
        if target.parent.resolve(strict=False) != root / rel.parent:
            return False
        dest = target.resolve(strict=False)
        if not dest.is_file():
            return False
        paradigm = (len(rel.parts) == 3 and rel.parts[0] == "rness"
                    and rel.parts[1] in ("paradigms", "metaparadigms") and rel.suffix == ".md")
        from .. import skeleton as _skeleton
        defaults = _skeleton._install_defaults_root().resolve()
        if not (paradigm or dest.is_relative_to(defaults)):
            return False
        try:
            target.unlink()
        except OSError:
            return False
        return True

    @router.post("/api/file", response_class=HTMLResponse)
    async def api_file_write(request: Request) -> HTMLResponse:
        form = await request.form()
        path = (form.get("path") or "").strip()
        content = form.get("content")
        if content is None:
            raise HTTPException(400, "missing content")
        # Browsers CRLF-normalize multipart field values, so every UI save
        # would silently rewrite a file's line endings. Normalize back to LF
        # — offset-based tooling (footnotes, highlights) and the paginate
        # round-trip all assume the file matches what the UI measured.
        content = content.replace("\r\n", "\n")
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
                "readvisor files are not editable from the project UI — "
                "edit globally at ~/enough/defaults/readvisors/",
            )
        if path.endswith(".girraph"):
            # Same rule as the agent's write_file: girraphs change via
            # node-level ops only, so panel edits and agent edits can
            # interleave without clobbering. (Outside the harness, a
            # text editor can of course still edit the file directly —
            # files are the source of truth.)
            raise HTTPException(
                403,
                "girraph files are edited through the girraph panel "
                "(node ops), not whole-file writes",
            )
        target = _resolve_project_path(path)
        # Composure guard: the same rule again for `.comp` files and their
        # comments sidecar — module-level ops only, so canvas edits and
        # readvisor edits interleave without clobbering.
        from .. import composure as _composure
        if (why := _composure.write_denial(target)):
            raise HTTPException(403, why)
        # Catalog guard: the same rule as the agent's write_file. The files
        # enough keeps — a volume's canon.cosm, this project's
        # rness/canon.cosm, a volume's .canon.json (or pre-0.4.3
        # .cachebox.json, by name anywhere: a corrupted sidecar breaks
        # ingest-status and origin tracking), and a modality:mirror file in
        # the store — are regenerated from what they describe, so
        # whole-file edits are refused.
        if (why := _canon.catalog_write_denial(target, project_dir)):
            raise HTTPException(403, why)
        if target.is_dir():
            raise HTTPException(400, "is a directory")
        target.parent.mkdir(parents=True, exist_ok=True)
        # Stash the previous contents so the user-side "undo last
        # edit" affordance (Phase 4b) can revert. Cheap; no-op when
        # the file doesn't exist yet. (Through a link it reads the shared
        # text; the stash itself lands beside the link, in the project.)
        from .. import tools as _tools
        _tools.stash_for_undo(target)
        # 0.9 (route guards): a save to a link to a shared file (a paradigm,
        # a metaparadigm, a policy: every project links the same one) makes
        # the project's own copy in place of the link, as the readvisor's
        # write_file does, and says so. Other links keep writing through.
        unlinked = _replace_shared_link(path, target)
        from .. import prompt as _prompt
        content, _stamp_warning = _prompt.stamp_metaparadigm_on_save(target, str(content))
        target.write_text(str(content), encoding="utf-8")
        return await _api_file_write_answer(path, target, unlinked=unlinked)

    async def _api_file_write_answer(path: str, target: Path, *, unlinked: bool) -> HTMLResponse:
        """The rest of a save, after the write: the convert sync and the
        re-rendered preview. `unlinked` rides back twice: a header
        (`X-Enough-Unlinked: 1`) and a hidden `.file-unlinked` marker."""
        resp = await _api_file_write_tail(path, target)
        if not unlinked:
            return resp
        marker = (f'<div class="file-unlinked" hidden data-path="{_escape_html(path)}"></div>')
        out = HTMLResponse(marker + resp.body.decode("utf-8"))
        out.headers[UNLINKED_HEADER] = "1"
        return out

    async def _api_file_write_tail(path: str, target: Path) -> HTMLResponse:
        # convert §4: a twin whose manifest opted into "keep the original in
        # sync" exports itself over the original right after every save. The
        # twin is written FIRST and unconditionally — a stale original refuses
        # the export, and losing the user's text to that refusal would be the
        # worst possible answer. The refusal comes back as a flag for the UI
        # to open the conflict modal with.
        sync = await asyncio.to_thread(_convert.sync_after_save, target)
        # Return the re-rendered preview fragment so the UI can swap it in.
        resp = await api_file(path=path)  # type: ignore[misc]
        if sync is None:
            return resp
        # convert.sync_after_save reports the original's BASENAME (right for
        # prose); the SSE + marker need something resolvable, and here the
        # twin's project-relative `path` is in hand — the original is that
        # path minus the twin's `.md` (the pairing rule, convert-plan §3).
        rel_original = path[:-3] if path.lower().endswith(".md") else sync.get("original")
        await session.emit(_convert.EVENT, {
            "job": None, "path": path, "op": "sync", "state": sync["state"],
            "progress": None, "original": rel_original,
            "message": sync.get("detail") or f"exported {sync.get('written', '')}",
            "result": sync if sync["state"] == "synced" else None,
            "error": sync.get("detail") if sync["state"] != "synced" else None,
        })
        marker = (
            f'<div class="convert-sync" hidden '
            f'data-sync-state="{sync["state"]}" '
            f'data-original="{_escape_html(rel_original or "")}" '
            f'data-detail="{_escape_html(sync.get("detail") or "")}"></div>'
        )
        return HTMLResponse(marker + resp.body.decode("utf-8"))

    @router.post("/api/file/undo", response_class=HTMLResponse)
    async def api_file_undo(request: Request) -> HTMLResponse:
        """Restore a file from its `.<filename>.undo` sibling and
        delete the stash. Returns the re-rendered preview fragment so
        the UI can swap it in just like a save would. 404 when no
        undo is available — the UI uses that to grey out the button."""
        form = await request.form()
        path = (form.get("path") or "").strip()
        if not path:
            raise HTTPException(400, "missing path")
        target = _resolve_project_path(path)
        from .. import tools as _tools
        undo = _tools._undo_path(target)
        if not undo.is_file():
            raise HTTPException(404, "no undo stash for this path")
        try:
            prior = undo.read_bytes()
        except OSError as e:
            raise HTTPException(500, f"undo unreadable: {e}") from None
        try:
            target.write_bytes(prior)
        except OSError as e:
            raise HTTPException(500, f"could not restore: {e}") from None
        try:
            undo.unlink()
        except OSError:
            pass    # leaving a stale stash is harmless; just log via the warning above if needed
        return await api_file(path=path)  # type: ignore[return-value]

    @router.post("/api/file/dismiss-undo")
    async def api_file_dismiss_undo(request: Request) -> dict[str, Any]:
        """Drop the `.undo` stash without restoring — the user clicked
        "save" / "looks good", and we honor that by closing the door
        on undoing this edit later. Idempotent."""
        form = await request.form()
        path = (form.get("path") or "").strip()
        if not path:
            raise HTTPException(400, "missing path")
        target = _resolve_project_path(path)
        from .. import tools as _tools
        undo = _tools._undo_path(target)
        removed = False
        if undo.is_file():
            try:
                undo.unlink()
                removed = True
            except OSError as e:
                raise HTTPException(500, f"could not dismiss: {e}") from None
        return {"path": path, "dismissed": removed}

    return router
