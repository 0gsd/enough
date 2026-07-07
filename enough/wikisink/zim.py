"""ZIM archive access: articles, search, suggestions, metadata.

The archive is read in place — never extracted. One lazily-opened
Archive singleton guarded by a lock (the binding's thread-safety is
undocumented; callers already run off the event loop, so serializing
archive calls costs nothing noticeable).

`libzim` is imported inside functions so enough boots without the wheel;
callers get WikisinkUnavailable with an actionable message instead of an
ImportError at startup.
"""

from __future__ import annotations

import logging
import posixpath
import re
import threading
import urllib.parse
from pathlib import Path
from typing import Any

from . import config as wconfig

log = logging.getLogger("enough.wikisink")

_LOCK = threading.Lock()
_archive: Any = None
_archive_path: Path | None = None

_MAX_REDIRECT_HOPS = 5
_MAX_RANDOM_DRAWS = 32


class WikisinkUnavailable(RuntimeError):
    """Raised when the archive can't be served; message is user-facing."""


def _ensure_archive() -> Any:
    """Open (or reuse) the Archive for the currently installed ZIM.
    Caller must hold _LOCK."""
    try:
        from libzim.reader import Archive
    except ImportError:
        raise WikisinkUnavailable(
            "the libzim package isn't installed — run `uv sync` in the "
            "enough checkout (or `pip install libzim`) and restart."
        )
    global _archive, _archive_path
    path = wconfig.zim_file()
    if path is None:
        # Drop any cached Archive: its file handle is dead if the drive
        # just detached, and a reattach would otherwise reuse it.
        _archive = None
        _archive_path = None
        # Message distinguishes never-installed from a detached drive
        # (and points at reachable alternate installs when they exist).
        raise WikisinkUnavailable(
            wconfig.unavailable_reason()
            or "the wikipedia archive isn't reachable right now."
        )
    if _archive is None or _archive_path != path:
        log.info("opening ZIM archive %s", path)
        _archive = Archive(str(path))
        _archive_path = path
    return _archive


def reset_archive() -> None:
    """Drop the cached Archive (after install/replace, or in tests)."""
    global _archive, _archive_path
    with _LOCK:
        _archive = None
        _archive_path = None


def available() -> bool:
    try:
        with _LOCK:
            _ensure_archive()
        return True
    except WikisinkUnavailable:
        return False


# ---------------------------------------------------------------------------
# Entry lookup
# ---------------------------------------------------------------------------

def _lookup_entry(archive: Any, path: str | None, title: str | None) -> Any:
    """Find an entry by path (with an A/-prefix fallback for older
    Wikipedia ZIM URL layouts) or by title; follow redirects."""
    entry = None
    candidates: list[str] = []
    if path:
        decoded = urllib.parse.unquote(path)
        candidates = [decoded]
        if not decoded.startswith("A/"):
            candidates.append("A/" + decoded)
        candidates.append(decoded.replace(" ", "_"))
    for cand in candidates:
        try:
            entry = archive.get_entry_by_path(cand)
            break
        except KeyError:
            continue
    if entry is None and (title or path):
        try:
            entry = archive.get_entry_by_title(title or (path or "").replace("_", " "))
        except KeyError:
            pass
    if entry is None:
        raise KeyError(path or title or "")
    hops = 0
    while entry.is_redirect and hops < _MAX_REDIRECT_HOPS:
        entry = entry.get_redirect_entry()
        hops += 1
    return entry


def get_article(path: str | None = None, title: str | None = None) -> dict[str, Any]:
    """Fetch one article's raw HTML from the archive.

    Returns {path, title, html, mimetype}; raises KeyError when the
    archive has no such entry, WikisinkUnavailable when there's no
    archive to ask."""
    with _LOCK:
        archive = _ensure_archive()
        entry = _lookup_entry(archive, path, title)
        item = entry.get_item()
        return {
            "path": entry.path,
            "title": entry.title,
            "html": bytes(item.content).decode("utf-8", errors="replace"),
            "mimetype": item.mimetype,
        }


def has_article(path: str | None = None, title: str | None = None) -> bool:
    try:
        with _LOCK:
            archive = _ensure_archive()
            _lookup_entry(archive, path, title)
        return True
    except (KeyError, WikisinkUnavailable):
        return False


def search(q: str, offset: int = 0, limit: int = 20) -> dict[str, Any]:
    """Full-text search via the ZIM's built-in Xapian index."""
    from libzim.search import Query, Searcher  # noqa: import guarded by _ensure_archive

    with _LOCK:
        archive = _ensure_archive()
        if not archive.has_fulltext_index:
            raise WikisinkUnavailable(
                "this archive has no full-text index — title suggestions "
                "still work via the search box."
            )
        srch = Searcher(archive).search(Query().set_query(q))
        estimated = srch.getEstimatedMatches()
        results = []
        for p in srch.getResults(offset, limit):
            try:
                e = archive.get_entry_by_path(p)
                results.append({"path": e.path, "title": e.title})
            except KeyError:
                continue
    return {"estimated_matches": estimated, "results": results}


def suggest(q: str, limit: int = 10) -> list[dict[str, str]]:
    """Title suggestions (prefix-ish matching) for the search box."""
    from libzim.suggestion import SuggestionSearcher

    with _LOCK:
        archive = _ensure_archive()
        sugg = SuggestionSearcher(archive).suggest(q)
        out = []
        for p in sugg.getResults(0, limit):
            try:
                e = archive.get_entry_by_path(p)
                if e.is_redirect:
                    e = e.get_redirect_entry()
                out.append({"path": e.path, "title": e.title})
            except KeyError:
                continue
    # Redirect-following can produce duplicates (Woden -> Odin); dedupe.
    seen: set[str] = set()
    deduped = []
    for r in out:
        if r["path"] not in seen:
            seen.add(r["path"])
            deduped.append(r)
    return deduped


def random_article() -> dict[str, str]:
    """A random text/html non-redirect article."""
    with _LOCK:
        archive = _ensure_archive()
        for _ in range(_MAX_RANDOM_DRAWS):
            entry = archive.get_random_entry()
            if entry.is_redirect:
                continue
            item = entry.get_item()
            if item.mimetype.startswith("text/html"):
                return {"path": entry.path, "title": entry.title}
    raise WikisinkUnavailable("couldn't find a random article — archive may be empty.")


def snapshot_info() -> dict[str, Any]:
    with _LOCK:
        archive = _ensure_archive()
        meta_keys = set(archive.metadata_keys)

        def _meta(name: str) -> str:
            if name not in meta_keys:
                return ""
            try:
                return archive.get_metadata(name).decode("utf-8", errors="replace")
            except (KeyError, RuntimeError):
                return ""

        return {
            "date": _meta("Date"),
            "title": _meta("Title"),
            "article_count": archive.article_count,
            "entry_count": archive.entry_count,
            "filename": Path(str(_archive_path)).name if _archive_path else None,
        }


# ---------------------------------------------------------------------------
# HTML sanitize + link rewrite
# ---------------------------------------------------------------------------

_BODY_RE = re.compile(r"<body[^>]*>(.*)</body>", re.IGNORECASE | re.DOTALL)
_STRIP_BLOCKS_RE = re.compile(
    r"<(script|style|iframe|object|embed|audio|video)\b.*?</\1\s*>",
    re.IGNORECASE | re.DOTALL,
)
_STRIP_VOID_RE = re.compile(r"<(?:link|meta|img|source|track)\b[^>]*>", re.IGNORECASE)
_ON_ATTR_RE = re.compile(r"\s+on[a-z]+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.IGNORECASE)
_STYLE_ATTR_RE = re.compile(r"\s+style\s*=\s*(\"[^\"]*\"|'[^']*')", re.IGNORECASE)
_HREF_RE = re.compile(r"(<a\b[^>]*?)\shref\s*=\s*(\"[^\"]*\"|'[^']*')", re.IGNORECASE)


def _rewrite_href(tag_head: str, quoted: str, base_dir: str) -> str:
    href = quoted[1:-1]
    unescaped = href.replace("&amp;", "&")
    low = unescaped.lower()
    if low.startswith(("http://", "https://", "//")):
        return f'{tag_head} href="{href}" target="_blank" rel="noopener" class="wiki-external"'
    if low.startswith(("mailto:", "javascript:", "data:")):
        return f"{tag_head} href=\"#\""
    if unescaped.startswith("#"):
        return f'{tag_head} href="{href}"'  # in-page anchor
    # Internal article link: resolve relative to the current article's
    # directory and hand navigation to the client-side router.
    target, _, frag = unescaped.partition("#")
    resolved = posixpath.normpath(posixpath.join(base_dir, urllib.parse.unquote(target)))
    resolved = resolved.lstrip("./")
    frag_attr = f' data-wiki-frag="{html_escape(frag)}"' if frag else ""
    return f'{tag_head} href="#" data-wiki-path="{html_escape(resolved)}"{frag_attr}'


def html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def sanitize_and_rewrite(raw_html: str, article_path: str) -> str:
    """Make ZIM/Parsoid article HTML safe and themable for #wiki-body:
    body extraction, script/style/media stripping, inline-style removal
    (our CSS variables do the styling), internal links rewired to
    data-wiki-path for the client-side router."""
    m = _BODY_RE.search(raw_html)
    body = m.group(1) if m else raw_html
    body = _STRIP_BLOCKS_RE.sub("", body)
    body = _STRIP_VOID_RE.sub("", body)
    body = _ON_ATTR_RE.sub("", body)
    body = _STYLE_ATTR_RE.sub("", body)
    base_dir = posixpath.dirname(article_path)
    body = _HREF_RE.sub(lambda mm: _rewrite_href(mm.group(1), mm.group(2), base_dir), body)
    return body.strip()
