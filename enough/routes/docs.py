"""The specifications (`/api/*-spec`, `/api/specs-status`) and the docs viewer (`/api/docs*`).

Moved out of `enough/server.py`'s `create_app` in 0.8 (lane W2-SV), code unchanged: `build_router` is the old
factory's closure for this group, and the names it closed over come in on `ctx`."""

from __future__ import annotations

import asyncio
import json
import threading
import time
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from .. import docoes as _docoes
from .. import language_library as _language_library
from .. import library_fetch as _library_fetch
from .. import macrocosm as _macrocosm
from .. import specs as _specs
from .common import AppContext
from ..server import STATIC_DIR, UI_LANGUAGES, _read_ui_config, _ui_language, log


def build_router(ctx: AppContext) -> APIRouter:
    router = APIRouter()
    _cosm_payload = ctx._cosm_payload
    _lens_payload = ctx._lens_payload

    async def _spec_markdown(slug: str, lang: str) -> PlainTextResponse:
        """One of the four specifications as raw markdown — the docs viewer
        reads the DocOES volume (`/api/docs`); these routes are the raw
        source, like `/api/help-center` for the manual. The file is the one
        DocOES builds from (0.5.4): the copy synced from cosmoes.org when one
        is in use, else the text bundled with enough (`docoes.spec_source`).
        `lang` picks static/i18n/<lang>/<FILE>.md when one ships (none does;
        the specifications are English only), else English. Home-accessible."""
        d = _docoes.DOCUMENTS[slug]
        name = Path(d.sources["en"]).name
        doc = _docoes.spec_source(slug)
        if lang in UI_LANGUAGES and lang != "en":
            translated = STATIC_DIR / "i18n" / lang / name
            if translated.is_file():
                doc = translated
        text = await asyncio.to_thread(
            lambda: doc.read_text(encoding="utf-8") if doc.is_file() else None)
        if text is None:
            raise HTTPException(
                404,
                f"{name} not found in this install — run /update-enough "
                "to pick up the bundled spec.")
        return PlainTextResponse(text, media_type="text/markdown; charset=utf-8")

    @router.get("/api/macrocosm-spec", response_class=PlainTextResponse)
    async def api_macrocosm_spec(lang: str = "en") -> PlainTextResponse:
        """MacroCOSM OES (docs/MACROCOSM_OES.md, or its synced copy) as raw markdown; see `_spec_markdown`."""
        return await _spec_markdown("macrocosm-oes", lang)

    @router.get("/api/thym-spec", response_class=PlainTextResponse)
    async def api_thym_spec(lang: str = "en") -> PlainTextResponse:
        """Thym (docs/THYM.md, or its synced copy) as raw markdown (0.5.0); see `_spec_markdown`."""
        return await _spec_markdown("thym", lang)

    @router.get("/api/ascribe-spec", response_class=PlainTextResponse)
    async def api_ascribe_spec(lang: str = "en") -> PlainTextResponse:
        """Ascribe (docs/ASCRIBE.md, or its synced copy) as raw markdown (0.5.4); see `_spec_markdown`."""
        return await _spec_markdown("ascribe", lang)

    @router.get("/api/comprise-spec", response_class=PlainTextResponse)
    async def api_comprise_spec(lang: str = "en") -> PlainTextResponse:
        """Comprise OES (docs/COMPRISE_OES.md, or its synced copy) as raw markdown (0.5.4); see `_spec_markdown`."""
        return await _spec_markdown("comprise-oes", lang)

    @router.get("/api/specs-status")
    async def api_specs_status() -> dict[str, Any]:
        """The launch check's report (0.5.4, `enough/specs.py`): whether it
        ran (`ran`, `reason`), `checked`, `updated`, `unchanged`, `errors`,
        `elapsed`, `at`, the base it asked and the specs root, and every
        document's `edition`, `revised` and `source` (cosmoes | bundled) — the
        docs viewer's badge title and QA read it. Home-accessible, read-only."""
        return await asyncio.to_thread(lambda: _specs.status(_read_ui_config()))

    # ---------- DocOES: the doc volumes at three densities (0.4.4) ----------
    #
    # A doc volume is built from the install's own documents into its state
    # (`ENOUGH_DOCS_ROOT`, ~/enough/docoes/), never into a project, so every
    # route here is home-accessible (HOME_PATHS) and, reading only, open
    # while agent-free. A telling is built by the first request that finds
    # it stale, in a worker thread (0.2–0.6 s); a request that arrives while
    # a build of that telling runs — that one, or a `POST /api/docs/build` —
    # gets 202 `{building: true, progress}` and asks again. Payloads are
    # encoded once per built volume (keyed by its digest and build time).

    DOCS_DENSITIES = ("atem", "short", "fabula")
    # A typed reference names a place in the prose: what "mentioned in" counts.
    DOCS_MENTION_FIELDS = frozenset({"mentions", "about", "see", "same_as", "also_defined_in"})
    # The tree: carried both ways on every item already, so never a backref.
    DOCS_TREE_FIELDS = frozenset({"parts", "parent", "chapter"})
    _docs_jobs: dict[tuple[str, str], dict[str, Any]] = {}
    _docs_guard = threading.Lock()
    _docs_cache: dict[tuple, bytes] = {}
    _docs_tasks: set[asyncio.Task[Any]] = set()

    def _docs_telling(doc: str | None, lang: str | None) -> tuple[str, str, str | None]:
        """`(doc, telling, requested)`: 404 for a document or a language
        enough does not have; a language the document has no telling in
        (the spec is English only) falls back to the author's telling, and
        `requested` says what was asked. No `lang`: the UI language."""
        slug = (doc or "").strip().removeprefix("doc/")
        if slug not in _docoes.DOCUMENTS:
            raise HTTPException(404, f"no document {doc!r}; enough has {', '.join(_docoes.DOCUMENTS)}")
        want = (lang or "").strip() or _ui_language()
        if want not in _docoes.LANGS:
            raise HTTPException(404, f"no language {lang!r}; enough's languages are {', '.join(_docoes.LANGS)}")
        tells = _docoes.tellings(slug)
        if want in tells:
            return slug, want, None
        return slug, ("en" if "en" in tells else tells[0]), want

    def _docs_new_job(keys: list[tuple[str, str]]) -> dict[str, Any]:
        """Register one build covering `keys` (call under `_docs_guard`)."""
        job = {"keys": list(keys), "done": 0, "total": len(keys),
               "current": f"{keys[0][0]}.{keys[0][1]}" if keys else None, "started": time.monotonic()}
        for k in keys:
            _docs_jobs[k] = job
        return job

    def _docs_finish(job: dict[str, Any]) -> None:
        with _docs_guard:
            for k in job["keys"]:
                if _docs_jobs.get(k) is job:
                    del _docs_jobs[k]

    def _docs_progress(job: dict[str, Any]) -> dict[str, Any]:
        return {"done": job["done"], "total": job["total"], "current": job["current"],
                "elapsed_s": round(time.monotonic() - job["started"], 2)}

    def _docs_step(job: dict[str, Any]) -> Callable[[int, int, str], None]:
        def step(done: int, total: int, current: str) -> None:
            job["done"], job["total"], job["current"] = done, total, current
        return step

    def _docs_202(slug: str, lang: str, job: dict[str, Any]) -> JSONResponse:
        return JSONResponse({"building": True, "doc": slug, "lang": lang,
                             "progress": _docs_progress(job)}, status_code=202)

    def _docs_is_fresh(slug: str, lang: str) -> bool:
        try:
            return _docoes.is_fresh(slug, lang)
        except (OSError, KeyError, UnicodeDecodeError):
            return False

    async def _docs_volume(slug: str, lang: str) -> "_macrocosm.Volume | JSONResponse":
        """The loaded telling, built first when stale; a 202 while a build of
        it runs; 503 when it has no volume and cannot be built."""
        key = (slug, lang)
        with _docs_guard:
            job = _docs_jobs.get(key)
        if job is not None:
            return _docs_202(slug, lang, job)
        if not await asyncio.to_thread(_docs_is_fresh, slug, lang):
            with _docs_guard:
                job = _docs_jobs.get(key)
                mine = job is None
                if mine:
                    job = _docs_new_job([key])
            if not mine:
                return _docs_202(slug, lang, job)
            try:
                await asyncio.to_thread(_docoes.ensure_built, slug, lang, on_step=_docs_step(job))
            finally:
                _docs_finish(job)
        try:
            return await asyncio.to_thread(_docoes.load_built, slug, lang, ensure=False)
        except _docoes.DocsUnavailable as e:
            raise HTTPException(503, f"the {slug} volume ({lang}) could not be built: {e}") from None

    def _docs_head(vol: "_macrocosm.Volume", slug: str, lang: str, requested: str | None,
                   density: str) -> dict[str, Any]:
        cat = vol.catalog
        built = cat.get("built") if isinstance(cat.get("built"), dict) else {}
        return {
            "doc": slug, "lang": lang, "requested_lang": requested, "density": density,
            "id": vol.id, "title": vol.name, "uri": _macrocosm.qualified_uri(vol),
            "telling": _macrocosm.jsonable(cat.get("telling")),
            "tellings": _macrocosm.jsonable(cat.get("tellings")) or [lang],
            "document": _macrocosm.jsonable(cat.get("document")),
            "chapters": _macrocosm.jsonable(cat.get("chapters") or []),
            "built": _macrocosm.jsonable({k: built.get(k) for k in ("at", "by", "digest")}),
        }

    _DOCS_LIGHT = ("number", "anchor", "chapter", "fallback", "in", "of", "defined_in")

    def _docs_light(it: "_macrocosm.Item") -> dict[str, Any]:
        d = it.data
        row = {"key": it.key, "id": it.id, "kind": it.kind, "module": it.module, "name": it.name,
               "atem": _macrocosm.jsonable(d.get("atem")), "order": d.get("order"),
               "level": d.get("level"), "parent": d.get("parent")}
        for k in _DOCS_LIGHT:
            row[k] = _macrocosm.jsonable(d.get(k))
        return row

    def _docs_edges(vol: "_macrocosm.Volume") -> list[tuple[str, str, str]]:
        """`(from key, to key, field or link rel)` for every declared
        reference and typed link that resolves, the tree aside."""
        out: list[tuple[str, str, str]] = []
        for it in vol.items.values():
            for a, b, label, style in _macrocosm._edges(vol, {}, it):
                if style == "tree" or label in DOCS_TREE_FIELDS or a.key == b.key:
                    continue
                out.append((a.key, b.key, label if style == "ref" else f"link:{label}"))
        return out

    def _docs_backrefs(edges: list[tuple[str, str, str]]) -> dict[str, list[str]]:
        back: dict[str, list[str]] = {}
        for a, b, _label in edges:
            seen = back.setdefault(b, [])
            if a not in seen:
                seen.append(a)
        return back

    def _docs_order(it: "_macrocosm.Item") -> int:
        o = it.data.get("order")
        return o if isinstance(o, int) else 0

    def _docs_short(vol: "_macrocosm.Volume") -> dict[str, Any]:
        edges = _docs_edges(vol)
        mentioned: dict[str, set[str]] = {}
        for a, b, label in edges:
            if label in DOCS_MENTION_FIELDS or label.startswith("link:"):
                mentioned.setdefault(b, set()).add(a)
        examples: dict[str, list[str]] = {}
        for it in vol.items.values():
            if it.kind == "example" and isinstance(it.data.get("in"), str):
                examples.setdefault(it.data["in"], []).append(it.id)
        sections = []
        for it in sorted((x for x in vol.items.values() if x.kind == "section"), key=_docs_order):
            d = it.data
            sections.append({
                "key": it.key, "id": it.id, "order": d.get("order"), "level": d.get("level"),
                "number": _macrocosm.jsonable(d.get("number")), "name": it.name,
                "anchor": d.get("anchor"), "heading": d.get("heading"), "body": d.get("body") or "",
                "atem": _macrocosm.jsonable(d.get("atem")), "parent": d.get("parent"),
                "chapter": d.get("chapter"), "fallback": d.get("fallback"),
                "mentioned_in": len(mentioned.get(it.key, ())), "examples": examples.get(it.id, []),
            })
        terms = []
        for it in vol.items.values():
            if it.kind != "term":
                continue
            d = it.data
            terms.append({"key": it.key, "id": it.id, "name": it.name,
                          "atem": _macrocosm.jsonable(d.get("atem")),
                          "summary": _macrocosm.jsonable(d.get("summary")),
                          "defined_in": d.get("defined_in"),
                          "also_defined_in": _macrocosm.jsonable(d.get("also_defined_in") or []),
                          "same_as": _macrocosm.jsonable(d.get("same_as") or []),
                          "chapter": d.get("chapter"), "fallback": d.get("fallback")})
        return {"sections": sections, "terms": terms}

    def _docs_inventories(slug: str) -> list[dict[str, Any]] | None:
        """The inventory rows of the documents this one's bubbles point into
        (the Help Center's `docs` bubble names a spec section), so those
        cross-volume references lint as resolved; built if stale (blocking).
        None when there are none, or one cannot be had."""
        others = sorted(set(_docoes.BUBBLE_DOCUMENT.values()) - {slug}) \
            if _docoes.DOCUMENTS[slug].bubbles else []
        rows: list[dict[str, Any]] = []
        for other in others:
            try:
                rows += _docoes.inventory(_docoes.load_built(other, "en"))
            except (_docoes.DocsUnavailable, KeyError, OSError):
                return None
        return rows or None

    def _docs_page(vol: "_macrocosm.Volume", section: str, module: str) -> set[str]:
        """The keys of one fabula page: a section with everything under it
        (its parts, the examples and decisions `in` them, the terms
        `defined_in` them), and/or one module."""
        keys = set(vol.items)
        if section:
            ref = section.strip()
            top = vol.item(ref) or vol.item(f"S:section/{ref.removeprefix('§').strip()}")
            if top is None or top.kind != "section":
                raise HTTPException(404, f"no section {section!r} in {vol.name}")
            ids, frontier = {top.id}, [top]
            while frontier:
                nxt = []
                for it in frontier:
                    for v in it.data.get("parts") or []:
                        t = _macrocosm.resolve_ref(vol, it, v)
                        if t is not None and t.id not in ids:
                            ids.add(t.id)
                            nxt.append(t)
                frontier = nxt
            keys = {k for k, it in vol.items.items()
                    if it.id in ids or it.data.get("in") in ids or it.data.get("defined_in") in ids}
        if module:
            keys = {k for k in keys if (vol.items[k].module or "") == module}
        return keys

    def _docs_fabula(vol: "_macrocosm.Volume", slug: str, lang: str, section: str,
                     module: str) -> dict[str, Any]:
        report = _docoes.lint_doc(vol, inventories=_docs_inventories(slug))
        payload = _cosm_payload(vol, f"docs:{slug}.{lang}", report=report)
        if section or module:
            keep = _docs_page(vol, section, module)
            for mod in payload["modules"]:
                kinds = []
                for k in mod["kinds"]:
                    items = [i for i in k["items"] if i["key"] in keep]
                    if items:
                        kinds.append({"kind": k["kind"], "items": items})
                mod["kinds"] = kinds
                mod["count"] = sum(len(k["items"]) for k in kinds)
            payload["page"] = {"section": section or None, "module": module or None,
                               "count": len(keep), "total": len(vol.items)}
        else:
            payload["page"] = None
        payload["backrefs"] = _docs_backrefs(_docs_edges(vol))
        payload["inventory"] = _macrocosm.jsonable(_docoes.inventory(vol))
        payload["declared_lenses"] = _docs_declared_lenses(vol)
        return payload

    def _docs_declared_lenses(vol: "_macrocosm.Volume") -> list[dict[str, Any]]:
        """The lenses a doc volume is drawn by, with the modules each draws:
        `[{id, kind, diagram, include, generic}]`. Every lens the manifest
        declares (a lens without `include` draws every module), then the
        reader's generic drawings it does not declare (`tree` over a volume
        with parts; `map` if the manifest had none), marked `generic` — the
        same set DocOES enumerates as the spec's `R:lens/doc.*` items, so the
        prism card's "renderings" reads one list for every telling."""
        if vol.manifest is None:
            return []
        letters = [str(x) for x in vol.manifest.modules()]
        out: list[dict[str, Any]] = []
        for spec in vol.manifest.lenses():
            include = [str(x) for x in (spec.get("include") or [])] or letters
            out.append({"id": spec["id"], "kind": spec.get("kind", "mermaid"), "diagram": spec.get("diagram"),
                        "include": include, "generic": False})
        declared = {d["id"] for d in out}
        for lid in _macrocosm.lenses(vol):
            if lid not in declared:
                out.append({"id": lid, "kind": "mermaid", "diagram": "flowchart", "include": letters,
                            "generic": True})
        return out

    def _docs_encoded(vol: "_macrocosm.Volume", slug: str, lang: str, requested: str | None,
                      density: str, section: str = "", module: str = "") -> Response:
        """One density of a telling, JSON-encoded once per built volume."""
        built = vol.catalog.get("built") if isinstance(vol.catalog.get("built"), dict) else {}
        key = (str(vol.path), str(built.get("digest")), str(built.get("at")), requested,
               density, section, module)
        with _docs_guard:
            hit = _docs_cache.get(key)
        if hit is None:
            out = _docs_head(vol, slug, lang, requested, density)
            if density == "fabula":                 # the modules carry every item, whole
                out = {**_docs_fabula(vol, slug, lang, section, module), **out}
            else:
                out["items"] = [_docs_light(it) for it in vol.items.values()]
                if density == "short":
                    out.update(_docs_short(vol))
            hit = json.dumps(out, ensure_ascii=False, default=str).encode("utf-8")
            with _docs_guard:
                _docs_cache[key] = hit
                while len(_docs_cache) > 24:
                    _docs_cache.pop(next(iter(_docs_cache)))
        return Response(content=hit, media_type="application/json")

    @router.get("/api/docs")
    async def api_docs(doc: str = Query(...), lang: str = Query(""), density: str = Query("short"),
                       section: str = Query(""), module: str = Query("")) -> Response:
        """A doc volume (DocOES) at one density — `doc` macrocosm-oes |
        help-center, `lang` one of the six (default: the UI language),
        `density` atem | short (default) | fabula. Every density carries the
        head `{doc, lang, requested_lang, density, id, title, uri, telling,
        tellings, document, chapters, built}`; atem adds `items` (all, light);
        short adds `sections` (telling order, bodies verbatim) and `terms`;
        fabula is the `/api/cosm` payload (+ `backrefs`, `inventory`,
        `declared_lenses`, `page`), one section's subtree with `section=`
        and/or one module with `module=`. Home-accessible; built on first
        use (202 while a build runs; 503 when it cannot be built)."""
        if density not in DOCS_DENSITIES:
            raise HTTPException(400, f"density is one of {', '.join(DOCS_DENSITIES)}")
        slug, telling, requested = _docs_telling(doc, lang)
        vol = await _docs_volume(slug, telling)
        if isinstance(vol, JSONResponse):
            return vol
        return await asyncio.to_thread(_docs_encoded, vol, slug, telling, requested, density,
                                       section.strip(), module.strip())

    @router.get("/api/docs/status")
    async def api_docs_status() -> dict[str, Any]:
        """Every document's tellings: `{root, ready, building, documents:
        [{doc, lang, built, fresh, digest, building, progress}]}` — `built`:
        a volume exists; `fresh`: it records the current digest; `digest`:
        the one it records."""

        def _build() -> dict[str, Any]:
            st = _docoes.status()
            with _docs_guard:
                running = {k: _docs_progress(j) for k, j in _docs_jobs.items()}
            rows = []
            for r in st["documents"]:
                k = (r["doc"], r["lang"])
                rows.append({"doc": r["doc"], "lang": r["lang"], "built": r["exists"], "fresh": r["fresh"],
                             "digest": _docoes.recorded_digest(Path(r["path"])),
                             "building": k in running, "progress": running.get(k)})
            return {"root": st["root"], "ready": st["ready"], "building": bool(running), "documents": rows}

        return await asyncio.to_thread(_build)

    @router.post("/api/docs/build")
    async def api_docs_build(request: Request) -> JSONResponse:
        """Build the stale tellings in the background — body `{doc?, lang?}`
        (nothing: every document and telling) — so a viewer can warm them
        before it opens. 202 `{building: true, progress}`; follow it on
        `GET /api/docs/status`. A build already running is reported, not
        doubled. Writes only into the docs root."""
        try:
            body = await request.json()
        except ValueError:
            body = None
        body = body if isinstance(body, dict) else {}
        doc, lang = (str(body.get("doc") or "").strip() or None), (str(body.get("lang") or "").strip() or None)
        slug: str | None = None
        telling: str | None = None
        if doc is not None:
            slug, resolved, _requested = _docs_telling(doc, lang or "en")
            telling = resolved if lang else None          # no lang: every telling of that document
        elif lang is not None:
            raise HTTPException(400, "a lang needs its doc")
        keys = [(s, lg) for s in ([slug] if slug else list(_docoes.DOCUMENTS))
                for lg in ([telling] if telling else _docoes.tellings(s))]
        with _docs_guard:
            running = next((_docs_jobs[k] for k in keys if k in _docs_jobs), None)
            job = running or _docs_new_job(keys)
        if running is None:
            def _run() -> None:
                try:
                    _docoes.ensure_built(slug, telling, on_step=_docs_step(job))
                except Exception:  # noqa: BLE001 — a background build never takes the server down
                    log.exception("docs: background build failed")
                finally:
                    _docs_finish(job)

            task = asyncio.get_running_loop().create_task(asyncio.to_thread(_run))
            _docs_tasks.add(task)
            task.add_done_callback(_docs_tasks.discard)
        return JSONResponse({"building": True, "doc": slug, "lang": telling,
                             "progress": _docs_progress(job)}, status_code=202)

    @router.get("/api/docs/lens")
    async def api_docs_lens(doc: str = Query(...), lang: str = Query(""), lens: str = Query(""),
                            around: str = Query(""), depth: int = Query(1)) -> Any:
        """One lens of a doc volume as merirmaid source — `/api/cosm/lens`'s
        payload (+ `doc`, `lang`). `around=<key>` draws that item's local
        graph (`lens` then defaults to `graph`, else `map`). Home-accessible."""
        slug, telling, _requested = _docs_telling(doc, lang)
        vol = await _docs_volume(slug, telling)
        if isinstance(vol, JSONResponse):
            return vol

        def _build() -> dict[str, Any]:
            out = _lens_payload(vol, lens.strip() or None, f"docs:{slug}.{telling}", around, depth)
            return {**out, "doc": slug, "lang": telling}

        return await asyncio.to_thread(_build)

    @router.post("/api/docs/compile")
    async def api_docs_compile(request: Request) -> Any:
        """The document again — body `{doc, lang?, chapter?}` — compiled as
        told from its volume: `{doc, lang, chapter, markdown}`, byte for byte
        the markdown it was enumerated from (a chapter's with `chapter`, a
        slug or `S:chapter/…` id). For "open raw" and download; writes nothing."""
        try:
            body = await request.json()
        except ValueError:
            body = None
        body = body if isinstance(body, dict) else {}
        slug, telling, _requested = _docs_telling(str(body.get("doc") or ""), str(body.get("lang") or ""))
        chapter = str(body.get("chapter") or "").strip() or None
        vol = await _docs_volume(slug, telling)
        if isinstance(vol, JSONResponse):
            return vol

        def _build() -> dict[str, Any]:
            if chapter is not None:
                cid = chapter if chapter.startswith("S:chapter/") else f"S:chapter/{chapter}"
                if vol.item(cid) is None:
                    raise HTTPException(404, f"no chapter {chapter!r} in {vol.name}")
            return {"doc": slug, "lang": telling, "chapter": chapter,
                    "markdown": _docoes.compile_doc(vol, chapter=chapter)}

        return await asyncio.to_thread(_build)

    @router.get("/api/docs/inventory")
    async def api_docs_inventory(doc: str = Query(...), lang: str = Query("")) -> Any:
        """The inventory lens's rows: `{doc, lang, rows: [{inventory, xref,
        id, kind, version, anchor, atem}]}` — what a cross-volume reference
        `<inventory>@<version>:<kind>:<id>` resolves through."""
        slug, telling, _requested = _docs_telling(doc, lang)
        vol = await _docs_volume(slug, telling)
        if isinstance(vol, JSONResponse):
            return vol
        return await asyncio.to_thread(lambda: {
            "doc": slug, "lang": telling, "rows": _macrocosm.jsonable(_docoes.inventory(vol))})

    # ------------------------------------------------------------------
    # The language library (0.8, lane W3-X2c): the texts a reliance's
    # `stated` cites, as synced into the install by scripts/sync_languages.py
    # (`enough/language_library.py`). Read-only and home-accessible
    # (HOME_PREFIXES has /api/library/); the index is built on first use in a
    # worker thread. A machine with no copy answers every citation with
    # state `not-aboard`, never an error.
    #
    # An installed enough has no synced shelf: a text a citation or the
    # viewer asks for is fetched on demand from cosmoes.org's library into
    # the cache (`enough/library_fetch.py`, ruled 2026-11-19). The routes
    # wait up to `wait` seconds (default 2) for that fetch, then answer
    # `fetching` (ask again) or, offline, `not-aboard`.

    def _library() -> "_language_library.Library | None":
        return _language_library.local()

    @router.get("/api/library/status")
    async def api_library_status() -> dict[str, Any]:
        """The shelf: `{source, index, present, current, problems,
        texts: [{shelf, text, version, name, what, aboard, here, volume}],
        fetch}`. `source` is the synced shelf, or the cache of fetched texts
        where there is none; `fetch` (null over a synced shelf) is `{allowed,
        reason, url, cache, registry, refreshed, cached: [{key, at, url,
        files, bytes, digest}], jobs: {key: {state, why, at}}}`: what is
        cached, and what is being fetched or failed."""
        lib = _library()
        fetch = await asyncio.to_thread(_library_fetch.status, _language_library.cache_dir())
        if lib is None:
            return {"source": str(_language_library.source_dir()), "index": str(_language_library.index_path()),
                    "present": False, "current": False, "texts": [], "fetch": fetch}
        body = await asyncio.to_thread(lib.status)
        body["fetch"] = fetch if lib.root == _language_library.cache_dir() else None
        return body

    @router.get("/api/library/section")
    async def api_library_section(in_: str = Query(..., alias="in"), version: str = Query(...),
                                  at: str = Query(...), digest: str = Query(""),
                                  section_digest: str = Query("", alias="section-digest"),
                                  wait: float = Query(2.0, ge=0, le=10)) -> dict[str, Any]:
        """One citation, opened: a reliance's `stated` as the query
        (`in`, `version`, `at`, optional `digest` and `section-digest`).
        Always 200 with `{cited, state, why, text, section}`: `state` is
        resolved | changed | unplaced | missing | fetching | not-aboard |
        unknown (`fetching`: the text is being fetched from cosmoes.org, ask
        again; offline it is `not-aboard`); `text` is the
        kept text's notice block (`name, publisher, version, licence {name,
        url}, copyright, changed, copy, notice, fetched, publisher_page,
        address, here, …`, null when the registry has no such text);
        `section` (null unless found) is `{id, page, file, anchor, heading,
        path, kind, level, lines, sha256, page_sha256, found_by, at, volume,
        body, parent, parts}`, `body` the section's lines verbatim."""
        stated = {"in": in_.strip(), "version": version.strip(), "at": at.strip()}
        if digest.strip():
            stated["digest"] = digest.strip()
        if section_digest.strip():
            stated["section-digest"] = section_digest.strip()
        if not all(stated[k] for k in ("in", "version", "at")):
            raise HTTPException(400, "in, version and at are each needed")
        lib = _library()
        if lib is None:
            return {"cited": stated, "state": "not-aboard", "text": None, "section": None,
                    "why": "no language library is synced here (scripts/sync_languages.py)"}
        return await asyncio.to_thread(lib.section, stated, wait)

    @router.get("/api/library/volume")
    async def api_library_volume(shelf: str = Query(...), text: str = Query(...), version: str = Query(...),
                                 page: str = Query(""), wait: float = Query(2.0, ge=0, le=10)) -> Any:
        """A kept text as a DocOES volume built at runtime: `{doc, id,
        title, document, nodes}` — without `page` the contents (the notice,
        then one section per page), with `page` that page's sections, bodies
        verbatim, each with `cite` (the `stated` that names it) and `sha256`.
        `document` carries the licence, copyright, change of form and the
        copy line. 404 for a text not kept here or a page it lacks; 503 when
        the shelf does not verify. A text the site keeps but this machine
        does not yet is fetched: 202 `{state: fetching, why}` (ask again);
        404 `{state: not-aboard, why}` when it cannot be (offline)."""
        lib = _library()
        if lib is None:
            raise HTTPException(404, "no language library is synced here (scripts/sync_languages.py)")
        pending = await asyncio.to_thread(lib.fetch_for, shelf, text, version, wait)
        if pending is not None:
            return JSONResponse({**pending, "detail": pending["why"]},
                                status_code=202 if pending["state"] == "fetching" else 404)
        try:
            cat = await asyncio.to_thread(lib.volume, shelf, text, version, page.strip() or None)
        except KeyError as e:
            raise HTTPException(404, str(e.args[0] if e.args else e)) from None
        except _language_library.LibraryUnavailable as e:
            raise HTTPException(503, str(e)) from None
        return {"doc": cat["id"], "id": cat["id"], "title": cat["name"], "oes": cat["oes"],
                "document": cat["document"], "nodes": cat["nodes"]}

    return router
