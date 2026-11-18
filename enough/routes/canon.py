"""Canon, the global file store (`/api/canon/*` but its jobs), and the MacroCOSM viewer (`/api/cosm*`, `/api/macrocosm/manifests`).

Moved out of `enough/server.py`'s `create_app` in 0.8 (lane W2-SV), code unchanged: `build_router` is the old
factory's closure for this group, and the names it closed over come in on `ctx`."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Query, Request

from .. import agent_free as _agent_free
from .. import broker as _broker
from .. import canon as _canon
from .. import macrocosm as _macrocosm
from .. import retired_names as _retired_names
from ..wikisink import config as _wikisink_config
from .common import AppContext
from ..server import _store_prefix, build_file_tree, log


def build_router(ctx: AppContext) -> APIRouter:
    router = APIRouter()
    _resolve_project_path = ctx._resolve_project_path
    project_dir = ctx.project_dir

    # -----------------------------------------------------------------
    # Canon — the global file store (was: cacheawl). Backend for the
    # split-view Canon UI. Contract: docs/canon-043-plan.md §6. Every route
    # answers under /api/canon/<x> (the /api/cacheawl/<x> aliases 0.4.3 kept
    # were removed in 0.6). A volume is `volume` on the wire and the tree's
    # list is `volumes` (0.7); `box` and `cacheboxes`, the names before, still
    # answer for one release (retired_names.FIELDS).
    # -----------------------------------------------------------------
    _ingest_tasks: set[asyncio.Task[Any]] = set()

    def _canon_route(method: str, sub: str):
        """Register a handler under `/api/canon/<sub>`."""
        def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
            router.add_api_route("/api/canon/" + sub, fn, methods=[method])
            return fn
        return deco

    def _canon_http(e: "_canon.CanonError") -> HTTPException:
        """A missing volume or folder is a 404; every other refusal a 400."""
        return HTTPException(404 if isinstance(e, _canon.CanonNotFound) else 400, str(e))

    @_canon_route("GET", "tree")
    async def api_canon_tree() -> dict[str, Any]:
        """Project tree + every volume tree in one payload for the split
        view. Triggers a cheap reconcile per volume first so manual file
        drops the backend didn't see are reflected, and reconciles the
        project's catalog (rness/canon.cosm) — the Canon pane is one of the
        places it is kept fresh (plan §6.7). The list is `volumes`, and is
        also under its old key `cacheboxes` for one release."""

        def _build() -> dict[str, Any]:
            _canon.reconcile_all()
            try:
                _canon.project_catalog(project_dir)
            except Exception:  # noqa: BLE001 — the tree must not fail on the catalog
                log.exception("canon tree: project catalog failed")
            volumes = []
            for summary in _canon.list_volumes():
                # A volume can vanish (rename/delete race) or error between
                # the listing and its tree scan — skip it rather than
                # 500ing the whole two-pane view.
                try:
                    volumes.append(_canon.volume_tree(summary["name"]))
                except (_canon.CanonError, OSError):
                    log.warning("canon tree: skipping volume %r", summary["name"])
            return _retired_names.answer({
                "root": str(_canon.root()),
                "project": build_file_tree(project_dir),
                "volumes": volumes,
            })

        return await asyncio.to_thread(_build)

    @_canon_route("POST", "create")
    async def api_canon_create(request: Request) -> dict[str, Any]:
        body = await request.json()
        name = (body.get("name") or "").strip()
        try:
            summary = await asyncio.to_thread(_canon.create_volume, name)
        except _canon.CanonError as e:
            raise _canon_http(e) from None
        return summary

    @_canon_route("POST", "rename")
    async def api_canon_rename(request: Request) -> dict[str, Any]:
        body = await request.json()
        name = (body.get("name") or "").strip()
        new_name = (body.get("new_name") or "").strip()
        try:
            return await asyncio.to_thread(_canon.rename_volume, name, new_name)
        except _canon.CanonError as e:
            # Pre-0.4.3 this answered 400 for a missing volume too; kept.
            raise HTTPException(400, str(e)) from None

    @_canon_route("POST", "delete")
    async def api_canon_delete(request: Request) -> dict[str, Any]:
        """Delete a volume and its contents. Requires an explicit
        {confirm: true} — the no-deletes-without-confirmation discipline."""
        body = await request.json()
        name = (body.get("name") or "").strip()
        confirm = bool(body.get("confirm"))
        try:
            return await asyncio.to_thread(
                _canon.delete_volume, name, confirm=confirm)
        except _canon.CanonError as e:
            # A missing volume is a 404; an unconfirmed delete is a 400.
            raise _canon_http(e) from None

    @_canon_route("POST", "transfer")
    async def api_canon_transfer(request: Request) -> dict[str, Any]:
        """Copy/move a file or folder between the project dir and a volume
        (either direction) or within/between volumes. Body:
        {op, src:{root,volume?,path}, dst:{root,volume?,path}, overwrite?}, a
        side's `root` being "project" or "canon" (`box` for `volume` is read
        for one release)."""
        body = await request.json()
        op = (body.get("op") or "").strip()
        src = body.get("src") or {}
        dst = body.get("dst") or {}
        try:
            out = await asyncio.to_thread(
                _canon.transfer, project_dir, op=op,
                src_kind=(src.get("root") or "").strip(),
                src_box=(_retired_names.field(src, "volume") or None),
                src_path=(src.get("path") or ""),
                dst_kind=(dst.get("root") or "").strip(),
                dst_box=(_retired_names.field(dst, "volume") or None),
                dst_path=(dst.get("path") or ""),
                overwrite=bool(body.get("overwrite")),
            )
        except _canon.CanonError as e:
            raise HTTPException(400, str(e)) from None
        for side in ("src", "dst"):
            _retired_names.answer(out[side])
        return out

    @_canon_route("POST", "ingest")
    async def api_canon_ingest(request: Request) -> dict[str, Any]:
        """Start an ingest into a volume. Long-running work runs in the
        background; poll /api/canon/ingest-status. Obvious input errors
        fail fast with a 400."""
        body = await request.json()
        box = (_retired_names.field(body, "volume") or "").strip()
        source_type = (body.get("type") or "").strip().lower()
        value = (body.get("value") or "").strip()
        depth = body.get("depth", 1)
        all_flag = bool(body.get("all"))
        # Register the volume (status 'ingesting') synchronously so a
        # malformed request 400s up front and ingest-status is pollable
        # immediately — no window where the volume doesn't exist yet.
        try:
            origin = await asyncio.to_thread(
                _canon.register_ingest, box=box, source_type=source_type,
                value=value, depth=depth, all_flag=all_flag)
        except _canon.CanonError as e:
            raise HTTPException(400, str(e)) from None

        loop = asyncio.get_running_loop()

        def _run() -> None:
            try:
                _canon.run_ingest(
                    project_dir, box=box, source_type=source_type,
                    value=value, depth=depth, all_flag=all_flag)
            except Exception:  # noqa: BLE001 — status file records the failure
                log.exception("canon ingest failed for volume %s", box)

        task = loop.create_task(asyncio.to_thread(_run))
        _ingest_tasks.add(task)
        task.add_done_callback(_ingest_tasks.discard)
        return _retired_names.answer({"volume": box, "status": "ingesting", "origin": origin})

    def _volume_query(request: Request) -> str:
        """The `volume` a Canon GET names (`box` for one release); a 422 without one."""
        volume = (_retired_names.field(request.query_params, "volume") or "").strip()
        if not volume:
            raise HTTPException(422, "a volume is required: ?volume=<name>.")
        return volume

    @_canon_route("GET", "ingest-status")
    async def api_canon_ingest_status(request: Request) -> dict[str, Any]:
        box = _volume_query(request)
        try:
            _canon.require_volume(box)
        except _canon.CanonError as e:
            raise HTTPException(404, str(e)) from None
        return await asyncio.to_thread(_canon.ingest_status, box)

    @router.get("/api/canon/ingest-caps")
    async def api_canon_ingest_caps() -> dict[str, Any]:
        """What an ingest may do, for the plain confirmation the ingest bar
        shows before it posts `/api/canon/ingest` itself (agent-free mode,
        plan §13; no readvisor vets it): the three caps, the depth rule, the
        fetch gate a url crawl goes through (the `fetch_url` broker toggles
        and the project's internet allowlist; robots.txt is always obeyed)
        and whether a wikisink archive is there to ingest from. Read-only,
        no model, new in 0.4.4."""
        from .. import tools as _tools_mod

        def _build() -> dict[str, Any]:
            try:
                wiki_ok = bool(_wikisink_config.installed())
                wiki_why = None if wiki_ok else (_wikisink_config.unavailable_reason()
                                                 or "no local wikipedia archive is installed.")
            except Exception as e:  # noqa: BLE001 — a caps read never fails on wikisink
                wiki_ok, wiki_why = False, str(e)
            return {
                "caps": {"url_pages": _canon.INGEST_URL_PAGE_CAP,
                         "wiki_articles": _canon.INGEST_WIKI_ARTICLE_CAP,
                         "path_files": _canon.INGEST_PATH_FILE_CAP},
                "types": ["path", "url", "wikisink"],
                # 1-3 levels (folders / link layers / crosslink layers), or
                # `all: true` — never for wikisink.
                "depth": {"min": 1, "max": 3, "all": ["path", "url"]},
                "fetch": {"enabled": _broker.is_enabled("fetch_url_enabled"),
                          "tor_for_offlist": _broker.is_enabled("fetch_url_tor_for_offlist"),
                          "allowlist": _tools_mod._read_internet_allowlist(project_dir),
                          "robots": True},
                "wikisink": {"installed": wiki_ok, "reason": wiki_why},
                "agent_free": _agent_free.enabled(),
            }

        return await asyncio.to_thread(_build)

    @_canon_route("GET", "mirror")
    async def api_canon_mirror(request: Request, path: str = Query("")) -> dict[str, Any]:
        """Read-only mirror diagram for a volume (``path`` empty) or a
        subfolder within it (``path`` set), drawn on demand from current
        contents by `canon.folder_flowchart` and never written (the volume
        root is reconciled first, so its catalog is fresh too). Payload:
        ``{text, node_map, modality, subpath, volume_path}`` —
        ``node_map`` maps each rendered node id to ``{path, is_dir}`` (path
        relative to the volume root) so the viewer's shift-click menu can
        resolve nodes to disk. The MacroCOSM view of a volume is its catalog's lenses
        (`/api/cosm/lens`), not this. The volume is `?volume=` (`?box=` for
        one release)."""
        box = _volume_query(request)

        def _build() -> dict[str, Any]:
            subpath = (path or "").strip().strip("/")
            if not subpath:
                _canon.reconcile(box)
            text, node_map = _canon.build_mirror(box, subpath)
            where = str(_canon.volume_dir(box))
            return {"text": text, "node_map": node_map,
                    "modality": "mirror", "subpath": subpath,
                    "volume_path": where}

        try:
            return await asyncio.to_thread(_build)
        except _canon.CanonError as e:
            raise _canon_http(e) from None

    # ---------- Catalogs and .cosm volumes (read-only, new in 0.4.3) ----------

    def _parsed_volume(vol: "_macrocosm.Volume") -> dict[str, Any]:
        return {
            "catalog": _macrocosm.jsonable(
                {k: v for k, v in vol.catalog.items() if k != "nodes"}),
            "items": [_macrocosm.jsonable(it.data) for it in vol.items.values()],
        }

    def _problem_lines(vol: "_macrocosm.Volume") -> list[str]:
        return [str(p) for p in _macrocosm.lint(vol).problems()]

    @router.get("/api/canon/catalog")
    async def api_canon_catalog(volume: str = Query(...)) -> dict[str, Any]:
        """A volume's catalog, `canon.cosm`, reconciled first: `{volume,
        path, text, parsed: {catalog, items}, problems}`."""

        def _build() -> dict[str, Any]:
            box = _canon.require_volume(volume)
            _canon.reconcile(volume)
            cat = box / _canon.CATALOG_NAME
            if not cat.is_file():           # an ingest in flight skips reconcile
                _canon.regenerate_catalog(volume)
            vol = _macrocosm.load_volume(cat)
            return {"volume": volume, "path": f"canon:{volume}/{_canon.CATALOG_NAME}",
                    "text": cat.read_text(encoding="utf-8"),
                    "parsed": _parsed_volume(vol), "problems": _problem_lines(vol)}

        try:
            return await asyncio.to_thread(_build)
        except _canon.CanonError as e:
            raise _canon_http(e) from None

    @router.get("/api/canon/project-catalog")
    async def api_canon_project_catalog() -> dict[str, Any]:
        """This project's catalog, `rness/canon.cosm`, reconciled first
        (written only when its bytes change): `{path, text, parsed,
        problems}`. A project route — home mode 404s it."""

        def _build() -> dict[str, Any]:
            _canon.project_catalog(project_dir)
            cat = project_dir / _canon.PROJECT_CATALOG
            if not cat.is_file():
                raise HTTPException(404, "this project has no rness/ folder, so no catalog")
            vol = _macrocosm.load_volume(cat)
            return {"path": _canon.PROJECT_CATALOG, "text": cat.read_text(encoding="utf-8"),
                    "parsed": _parsed_volume(vol), "problems": _problem_lines(vol)}

        return await asyncio.to_thread(_build)

    def _cosm_volume(path: str) -> "_macrocosm.Volume":
        """Load the volume a cosm route names: a project-relative or Canon
        (`canon:`) path to a `.cosm` file or a volume folder.

        Reconciles first where enough keeps the file — the project's
        `rness/canon.cosm`, a Canon volume's `canon.cosm` (or the volume
        folder itself). A folder holding `holotype.cosm` loads as the
        Holotype; a Canon volume folder otherwise loads by its catalog's
        file path (macrocosm would prefer a Holotype or a COSM tree at the
        same root); any other folder loads by whatever catalog it holds.
        Blocking — call it from a worker thread."""
        path = (path or "").strip()
        if not path:
            raise HTTPException(400, "missing path")
        from .. import thym_api as _thym_api
        thym = _thym_api.thym_volume(project_dir, path)     # a run's plan or trace (thym:), a program (.thym)
        if thym is not None:
            return thym
        target = _resolve_project_path(path)
        prefix = _store_prefix(path)
        if prefix:
            parts = [p for p in path[len(prefix):].split("/") if p]
            if parts and (len(parts) == 1 or parts[1:] == [_canon.CATALOG_NAME]):
                try:
                    _canon.reconcile(parts[0])
                except _canon.CanonError:
                    pass
        else:
            try:
                if target.resolve() == (project_dir / _canon.PROJECT_CATALOG).resolve():
                    _canon.project_catalog(project_dir)
            except OSError:
                pass
        if not target.exists():
            raise HTTPException(404, f"no such file or folder: {path}")
        if target.is_dir():
            cat = target / _canon.CATALOG_NAME
            store_volume = False
            try:
                store_volume = target.resolve().parent == _canon.root().resolve()
            except OSError:
                pass
            if not _canon.is_holotype_folder(target) and store_volume and cat.is_file():
                return _macrocosm.load_volume(cat)
            return _macrocosm.load_volume(target)
        if target.suffix != ".cosm":
            raise HTTPException(400, f"{path} is not a .cosm file or a volume folder")
        return _macrocosm.load_volume(target)

    def _cosm_item(vol: "_macrocosm.Volume", it: "_macrocosm.Item") -> dict[str, Any]:
        d = it.data
        return {
            "id": it.id, "key": it.key,
            "path": _macrocosm.item_path(vol, it),
            "name": it.name,
            "summary": _macrocosm.jsonable(d.get("summary")),
            "status": _macrocosm.jsonable(d.get("status")),
            "visibility": _macrocosm.jsonable(d.get("visibility")),
            "file": it.file,
            "part": it.part,
            "data": _macrocosm.jsonable(d),
        }

    def _cosm_payload(vol: "_macrocosm.Volume", path: str,
                      report: "_macrocosm.Report | None" = None) -> dict[str, Any]:
        """The cosm viewer's view of a volume: catalog header, modules in the
        manifest's order → kinds → items, the lint problems and open
        questions, and the lenses it can be drawn in. `report` replaces the
        generic lint (a doc volume passes `docoes.lint_doc`'s)."""
        m = vol.manifest
        report_of = None
        if report is None:
            # A fabula's own checks are enough's (enough/fabula.py), and a holograph's Ascribe's (enough/ascribe.py:
            # the generic checks, the dialectic's and Ascribe's seven in one report, each finding with its advice):
            # run them, so the viewer shows them as run rather than as checks left to another tool. Any other
            # format: the generic checks.
            from .. import fabula as _fabula
            if vol.manifest is not None and vol.minicosm == "ascribe":
                from .. import ascribe as _ascribe
                report = _ascribe.lint_holograph(vol)
                report_of = _ascribe.report_dict
            else:
                report = _fabula.lint(vol) if _fabula.is_fabula(vol) else _macrocosm.lint(vol)
        report_d = report_of(report) if report_of is not None else report.to_dict()
        modules: list[dict[str, Any]] = []
        if m is not None:
            found = vol.by_module()
            # The core's module D, which every format inherits, shows only where the volume holds items of it.
            letters = [x for x in m.modules() if x not in m.inherited or x in found] \
                + [x for x in found if x not in m.modules()]
            for letter in letters:
                kinds_found = found.get(letter, {})
                declared = list(m.kinds(letter)) if letter in m.modules() else []
                order = declared + [k for k in kinds_found if k not in declared]
                spec = m.module(letter) if letter in m.modules() else {}
                modules.append({
                    "letter": letter,
                    "name": str(spec.get("name") or letter),
                    "subtitle": str(spec.get("subtitle") or ""),
                    "count": sum(len(v) for v in kinds_found.values()),
                    "kinds": [{"kind": k, "items": [_cosm_item(vol, it) for it in kinds_found[k]]}
                              for k in order if k in kinds_found],
                })
        refused = vol.refused is not None
        return {
            "path": path,
            "minicosm": vol.minicosm,
            "major": vol.major,
            # How the catalog named its format: `oes`, `old` (an old spelling such as `emf/1`, which `said` keeps),
            # `legacy` or `absent`.
            "declared": ({"how": vol.declaration.how, "said": vol.declaration.said}
                         if vol.declaration is not None else None),
            "title": vol.name,
            "manifest_title": m.title if m is not None else None,
            "uri": _macrocosm.qualified_uri(vol) if not refused else None,
            "catalog": _macrocosm.jsonable({k: v for k, v in vol.catalog.items() if k != "nodes"}),
            "modules": modules,
            "problems": [str(p) for p in report.problems()],
            "pending": report_d["pending"],
            # The checks panel: the same findings split by severity, and the
            # check ids this reader leaves to the MiniCOSM's own tools
            # (Comprise's fourteen rules and P checks), never failures.
            "report": {k: v for k, v in report_d.items()
                       if k in ("ok", "errors", "warnings", "notes", "not_run")},
            "files": list(vol.files),
            "lenses": _macrocosm.lenses(vol) if not refused else [],
            "refused": str(vol.refused) if refused else None,
        }

    @router.get("/api/cosm")
    async def api_cosm(path: str = Query(...)) -> dict[str, Any]:
        """Any `.cosm` volume, structured for the cosm viewer: a Canon
        catalog, a Holotype, an EMF twin, a standalone COSM tree. A
        declaration this reader can't read comes back with `refused` set and
        nothing loaded (200: the viewer shows the refusal)."""
        return await asyncio.to_thread(lambda: _cosm_payload(_cosm_volume(path), path))

    LENS_MAX_DEPTH = 4

    def _lens_payload(vol: "_macrocosm.Volume", lens: str | None, source: str,
                      around: str | None = None, depth: int = 1) -> dict[str, Any]:
        """One lens of a loaded volume as merirmaid source, `{text, node_map,
        lens, lenses, around}`: `macrocosm.to_mermaid` under `modality:
        mirror` frontmatter. `around` (an item's key, id or path) draws the
        local graph instead (`depth` steps, 0–4); `around` in the payload is
        the centre's key, else None. Blocking."""
        if vol.refused is not None:
            raise HTTPException(400, str(vol.refused))
        names = _macrocosm.lenses(vol)
        around = (around or "").strip() or None
        if not lens:
            lens = "graph" if around and "graph" in names else "map"
        if lens not in names:
            raise HTTPException(
                400, f"unknown lens {lens!r}; this volume can be drawn as: {', '.join(names)}")
        depth = max(0, min(int(depth), LENS_MAX_DEPTH))
        try:
            body, node_map = _macrocosm.to_mermaid(vol, lens, around=around, depth=depth)
        except ValueError as e:
            raise HTTPException(404 if around else 400, str(e)) from None
        centre = next((k for k, v in node_map.items() if v.get("focus")), None)
        centre_key = node_map[centre]["id"] if centre else None
        title = f"{vol.name} · {lens}"
        if centre_key:
            title += f" · around {vol.items[centre_key].name}"
        frontmatter = "\n".join([
            "---",
            "merirmaid: 1",
            f"title: {' '.join(title.split())}",
            "modality: mirror",
            "kind: cosm-lens",
            f"source: {source}#{lens}",
            "node-char-limit: 48",
            "---",
        ]) + "\n"
        return {"text": frontmatter + body, "node_map": _macrocosm.jsonable(node_map),
                "lens": lens, "lenses": names, "around": centre_key}

    @router.get("/api/cosm/lens")
    async def api_cosm_lens(path: str = Query(...), lens: str = Query("map"),
                            around: str = Query(""), depth: int = Query(1)) -> dict[str, Any]:
        """One lens of a volume as merirmaid source: `{text, node_map,
        lens, lenses, around}`. The Mermaid body is `macrocosm.to_mermaid`
        (no click lines — resolve nodes through `node_map`, whose `fs_path`
        is a Canon item's real path) under `modality: mirror` frontmatter,
        so the merirmaid viewer shows it read-only. `around=<key>` (+
        `depth`, default 1) draws that item's local graph, the centre node
        classed `focus` (0.4.4)."""
        return await asyncio.to_thread(
            lambda: _lens_payload(_cosm_volume(path), lens, path, around, depth))

    @router.post("/api/cosm/lint")
    async def api_cosm_lint(request: Request) -> dict[str, Any]:
        """MacroCOSM's generic checks on a volume — body `{path}` — as the
        report: `{ok, minicosm, refused, errors, warnings, notes, pending,
        not_run, checks}`. Comprise's own rules are listed in `not_run`
        (they need Comprise)."""
        try:
            body = await request.json()
        except ValueError:
            body = None
        path = (body.get("path") or "").strip() if isinstance(body, dict) else ""

        def _build() -> dict[str, Any]:
            # a fabula's own checks (enough/fabula.py), a holograph's Ascribe's, any other volume the generic ones:
            # the same choice the viewer's payload makes
            from .. import fabula as _fabula
            vol = _cosm_volume(path)
            if vol.manifest is not None and vol.minicosm == "ascribe":
                from .. import ascribe as _ascribe
                report = _ascribe.report_dict(_ascribe.lint_holograph(vol))
            else:
                report = (_fabula.lint(vol) if _fabula.is_fabula(vol) else _macrocosm.lint(vol)).to_dict()
            report["path"] = path
            return report

        return await asyncio.to_thread(_build)

    @router.get("/api/macrocosm/manifests")
    async def api_macrocosm_manifests() -> list[dict[str, Any]]:
        """The formats this install reads (the bundled registry), in
        registry order: `[{name, title, version, declaration, summary, core,
        old}]`: `core` true for a built-in of the core, false for a MiniCOSM;
        `old` the old spellings it also reads (the fabula's `emf/1`)."""

        def _build() -> list[dict[str, Any]]:
            out = []
            for m in _macrocosm.default_registry().manifests.values():
                decl = m.declaration.get("value")
                out.append({
                    "name": m.name, "title": m.title, "version": m.version,
                    "declaration": decl if isinstance(decl, str) else f"{m.name}/{m.version}",
                    "summary": _macrocosm.jsonable(m.data.get("summary")) or "",
                    "core": m.core, "old": list(m.old),
                })
            return out

        return await asyncio.to_thread(_build)

    # ---------- Inline volumes (0.4.4): a volume from the text a request carries ----------

    INLINE_MAX_BYTES = 256 * 1024

    async def _inline_volume(request: Request) -> tuple["_macrocosm.Volume", str, dict[str, Any]]:
        """`(volume, filename, body)` for a `{text, filename}` body: read by
        `macrocosm.load_volume_text`, nothing written. 400 without text, 413
        over 256 KB."""
        try:
            body = await request.json()
        except ValueError:
            body = None
        if not isinstance(body, dict) or not isinstance(body.get("text"), str) or not body["text"].strip():
            raise HTTPException(400, "send {text, filename}: the text of one .cosm catalog")
        text = body["text"]
        if len(text.encode("utf-8")) > INLINE_MAX_BYTES:
            raise HTTPException(413, f"an inline volume is at most {INLINE_MAX_BYTES // 1024} KB; "
                                     "open a file this large from the project instead")
        filename = str(body.get("filename") or "").strip() or "inline.cosm"
        vol = await asyncio.to_thread(_macrocosm.load_volume_text, text, filename=filename)
        return vol, Path(filename).name or "inline.cosm", body

    @router.post("/api/cosm/inline")
    async def api_cosm_inline(request: Request) -> dict[str, Any]:
        """The `/api/cosm` payload for a volume read from text — body
        `{text, filename}` — for the docs viewer's live examples: it loads,
        lints and lists its lenses exactly as the same file would. `path`
        is `inline:<filename>`; nothing is written. Read-only, so
        home-accessible and open while agent-free."""
        vol, name, _body = await _inline_volume(request)
        return await asyncio.to_thread(lambda: _cosm_payload(vol, f"inline:{name}"))

    @router.post("/api/cosm/inline/lens")
    async def api_cosm_inline_lens(request: Request) -> dict[str, Any]:
        """One lens of an inline volume — body `{text, filename, lens,
        around, depth}` — as `/api/cosm/lens` gives it."""
        vol, name, body = await _inline_volume(request)
        try:
            depth = int(body.get("depth") or 1)
        except (TypeError, ValueError):
            depth = 1
        return await asyncio.to_thread(lambda: _lens_payload(
            vol, str(body.get("lens") or "") or None, f"inline:{name}",
            str(body.get("around") or "") or None, depth))

    ctx._cosm_payload = _cosm_payload
    ctx._lens_payload = _lens_payload
    return router
