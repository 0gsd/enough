"""The `/api/dict/*` routes (FEED), as one `APIRouter` `create_app` mounts.

The same split as `composure_api.py`: `enough/dictionary.py` is the engine and imports no FastAPI; this file is
the HTTP translation over it. The dictionary is install-wide rather than per project, so the router closes over
nothing. Every handler is a plain `def`, which FastAPI runs on its thread pool: the engine opens one SQLite
connection per call.

Status codes: a bad sort, direction or filter is a 400 with the engine's sentence; a dictionary that is not built
yet is a 503 (the UI reads `/api/dict/status` for progress); an unknown word is a 404 on `/entry` but a normal
`{found: false, suggestions}` answer on `/lookup`. Adding and changing user entries goes through the readvisor
tools in 0.4.1, so the only write here is DELETE.
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Query

from . import dictionary as feed


def _call(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    try:
        return fn(*args, **kwargs)
    except feed.DictionaryUnavailable as e:
        raise HTTPException(503, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


def _filters(domain: str | None, pos: str | None, band: str | None, origin: str | None) -> dict:
    return {k: v for k, v in (("domain", domain), ("pos", pos), ("band", band), ("origin", origin)) if v}


def build_router() -> APIRouter:
    """Build the dictionary router. One call in `create_app` wires it all."""
    router = APIRouter()

    @router.get("/api/dict/status")
    def dict_status() -> dict:
        return feed.status()

    @router.get("/api/dict/lookup")
    def dict_lookup(word: str = Query(..., min_length=1)) -> dict:
        return _call(feed.lookup, word)

    @router.get("/api/dict/entries")
    def dict_entries(
        sort: str = "alpha", then: str | None = None, dir: str = "asc", then_dir: str = "asc",
        offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=feed.MAX_LIMIT),
        letter: str | None = None, q: str | None = None,
        domain: str | None = None, pos: str | None = None, band: str | None = None, origin: str | None = None,
        grouped: bool = False,
    ) -> dict:
        return _call(feed.entries, sort=sort, then=then, dir=dir, then_dir=then_dir, offset=offset,
                     limit=limit, letter=letter, q=q, filters=_filters(domain, pos, band, origin),
                     grouped=grouped)

    @router.get("/api/dict/index")
    def dict_index(
        sort: str = "alpha", dir: str = "asc", letter: str | None = None, q: str | None = None,
        domain: str | None = None, pos: str | None = None, band: str | None = None, origin: str | None = None,
    ) -> dict:
        groups = _call(feed.index, sort=sort, dir=dir, q=q, letter=letter,
                       filters=_filters(domain, pos, band, origin))
        return {"sort": sort, "dir": dir, "groups": groups}

    @router.get("/api/dict/position")
    def dict_position(
        word: str = Query(..., min_length=1),
        sort: str = "alpha", then: str | None = None, dir: str = "asc", then_dir: str = "asc",
        letter: str | None = None, q: str | None = None,
        domain: str | None = None, pos: str | None = None, band: str | None = None, origin: str | None = None,
        grouped: bool = False,
    ) -> dict:
        return _call(feed.position, word, sort=sort, then=then, dir=dir, then_dir=then_dir, letter=letter,
                     q=q, filters=_filters(domain, pos, band, origin), grouped=grouped)

    @router.get("/api/dict/entry/{word}")
    def dict_entry(word: str) -> dict:
        e = _call(feed.entry, word)
        if e is None:
            raise HTTPException(404, f"no entry for {word!r}")
        return e

    @router.get("/api/dict/facets")
    def dict_facets() -> dict:
        return _call(feed.facets)

    @router.delete("/api/dict/user/{word}")
    def dict_user_delete(word: str) -> dict:
        r = _call(feed.user_delete, word)
        if not r.get("ok"):
            raise HTTPException(404, r.get("error") or "not in your dictionary")
        return r

    return router
