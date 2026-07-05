"""Overlay + preserved stores, and article-serving precedence.

Three layers, most-specific first:

1. `preserved/` — deletion-overridden articles the user chose to keep
   forever; never touched by update runs.
2. `overlay/` — watched articles refreshed live from Wikipedia between
   base-archive snapshots (the hybrid update model).
3. the base ZIM archive.

Each stored article is `<key>.html` plus `<key>.meta.json` capturing
where the HTML came from ({source_url, revid, fetched_at, title, path}).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from . import config as wconfig
from . import zim as wzim

log = logging.getLogger("enough.wikisink")


def _read_store(directory: Path, key: str) -> tuple[str, dict[str, Any]] | None:
    html_path = directory / f"{key}.html"
    if not html_path.is_file():
        return None
    try:
        html = html_path.read_text(encoding="utf-8")
    except OSError as e:
        log.warning("wikisink store read failed for %s (%s)", html_path, e)
        return None
    meta: dict[str, Any] = {}
    meta_path = directory / f"{key}.meta.json"
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = {}
    return html, meta


def _write_store(directory: Path, key: str, html: str, meta: dict[str, Any]) -> Path:
    html_path = directory / f"{key}.html"
    html_path.write_text(html, encoding="utf-8")
    (directory / f"{key}.meta.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    return html_path


def resolve_article(path: str | None = None, title: str | None = None) -> dict[str, Any]:
    """Best available copy of an article, with provenance.

    Returns {path, title, html, source: preserved|overlay|zim, meta}.
    Raises KeyError (nowhere has it) or zim.WikisinkUnavailable."""
    cfg = wconfig.load_config()
    ident = path or title or ""
    key = wconfig.article_key(ident)

    if wconfig.is_overridden(ident, cfg):
        found = _read_store(wconfig.preserved_dir(cfg), key)
        if found:
            html, meta = found
            return {"path": ident, "title": meta.get("title") or title or ident,
                    "html": html, "source": "preserved", "meta": meta}

    found = _read_store(wconfig.overlay_dir(cfg), key)
    if found:
        html, meta = found
        return {"path": ident, "title": meta.get("title") or title or ident,
                "html": html, "source": "overlay", "meta": meta}

    art = wzim.get_article(path=path, title=title)
    # The ZIM lookup may have normalized the path (A/ prefix, redirects);
    # check the stores once more under the canonical key so overlay copies
    # written post-lookup still win next time.
    canon_key = wconfig.article_key(art["path"])
    if canon_key != key:
        found = _read_store(wconfig.overlay_dir(cfg), canon_key)
        if found:
            html, meta = found
            return {"path": art["path"], "title": art["title"], "html": html,
                    "source": "overlay", "meta": meta}
    return {"path": art["path"], "title": art["title"], "html": art["html"],
            "source": "zim", "meta": {"snapshot": (cfg.get("zim") or {}).get("snapshot")}}


def put_overlay(path: str, title: str, html: str, meta: dict[str, Any]) -> Path:
    """Store a live-refreshed copy of a watched article."""
    meta = {"path": path, "title": title, **meta}
    return _write_store(wconfig.overlay_dir(), wconfig.article_key(path), html, meta)


def preserve(path: str, title: str | None = None, *, reason: str = "",
             deletion_log_excerpt: str = "", detected_at: str | None = None) -> dict[str, Any]:
    """Deletion override: copy the best available HTML into preserved/
    and register it so update runs skip it forever (until un-overridden).
    Returns the override registry entry."""
    art = resolve_article(path=path, title=title)
    key = wconfig.article_key(path)
    meta = {**art["meta"], "path": path, "title": art["title"],
            "preserved_from": art["source"]}
    preserved_path = _write_store(wconfig.preserved_dir(), key, art["html"], meta)
    wconfig.add_override(path, art["title"], preserved_file=preserved_path.name,
                         reason=reason, deletion_log_excerpt=deletion_log_excerpt,
                         detected_at=detected_at)
    return {"path": path, "title": art["title"], "preserved_file": preserved_path.name}
