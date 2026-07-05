"""Agent-facing wikisink tools.

Four tools (registered via thin lazy wrappers in tools.py so imports
stay acyclic):

- `wiki_search`       — full-text search over the local archive
- `read_wiki_article` — fetch an article as markdown, cached to
                        rness/io/input/ (fetch_url's contract: the agent
                        sees a preview + cache path, never the full body)
- `wiki_status`       — what's installed, watched, commented, overridden
- `wikisink`          — the update run (wired in update.py's phase)

All gated by the `wikisink_enabled` broker toggle.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .. import broker
from ..tools import ToolCall, ToolResult
from . import config as wconfig
from . import overlay as woverlay
from . import zim as wzim

log = logging.getLogger("enough.wikisink")

PREVIEW_CHARS = 500


def _denied(name: str, key: str = "") -> ToolResult:
    return ToolResult(name, key, False, broker.denial_tool_disabled(
        f"{name} (wikisink tools are disabled in the broker config)"))


def _unavailable(name: str, key: str, e: Exception) -> ToolResult:
    return ToolResult(name, key, False, f"wikisink unavailable: {e}")


def run_wiki_search(project_dir: Path, call: ToolCall) -> ToolResult:
    if not broker.is_enabled("wikisink_enabled"):
        return _denied("wiki_search")
    query = (call.extra.get("query") or "").strip()
    if not query:
        return ToolResult("wiki_search", "", False,
                          "error: missing <query>…</query>")
    try:
        limit = min(int(call.extra.get("limit") or 10), 25)
    except ValueError:
        limit = 10
    try:
        res = wzim.search(query, 0, limit)
    except wzim.WikisinkUnavailable as e:
        return _unavailable("wiki_search", query, e)
    lines = [f"{i + 1}. {r['title']} — {r['path']}"
             for i, r in enumerate(res["results"])]
    body = (f"~{res['estimated_matches']} matches in the local archive "
            f"for {query!r}; top {len(lines)}:\n" + "\n".join(lines)
            if lines else f"no matches in the local archive for {query!r}.")
    body += "\n\nuse read_wiki_article with a path to read one."
    return ToolResult("wiki_search", query, True, body)


def run_read_wiki_article(project_dir: Path, call: ToolCall) -> ToolResult:
    if not broker.is_enabled("wikisink_enabled"):
        return _denied("read_wiki_article")
    path = (call.path or call.extra.get("path") or "").strip()
    title = (call.extra.get("title") or "").strip()
    key = path or title
    if not key:
        return ToolResult("read_wiki_article", "", False,
                          "error: provide <path> or <title>")
    try:
        art = woverlay.resolve_article(path=path or None, title=title or None)
    except KeyError:
        return ToolResult("read_wiki_article", key, False,
                          f"no article for {key!r} in the local archive — "
                          "try wiki_search first.")
    except wzim.WikisinkUnavailable as e:
        return _unavailable("read_wiki_article", key, e)

    from ..tools import _markdownify_via_pandoc

    md, converted = _markdownify_via_pandoc(art["html"])
    text = md if converted else art["html"]
    cache_dir = project_dir / "rness" / "io" / "input"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_name = f"wiki-{wconfig.article_key(art['path'])}.{'md' if converted else 'html'}"
    cache_path = cache_dir / cache_name
    cache_path.write_text(text, encoding="utf-8")

    cfg = wconfig.load_config()
    if art["source"] == "overlay":
        provenance = (f"live Wikipedia overlay (revision "
                      f"{(art['meta'] or {}).get('revid', '?')}, fetched "
                      f"{(art['meta'] or {}).get('fetched_at', '?')})")
    elif art["source"] == "preserved":
        provenance = "preserved local copy (deletion override)"
    else:
        provenance = f"local ZIM snapshot {(cfg.get('zim') or {}).get('snapshot')}"
    preview = text[:PREVIEW_CHARS]
    body = (
        f"“{art['title']}” — {provenance}\n"
        f"cached full text ({len(text)} chars) at rness/io/input/{cache_name} "
        "— read_file it for the rest.\n"
        f"---\n{preview}{'…' if len(text) > PREVIEW_CHARS else ''}"
    )
    return ToolResult("read_wiki_article", art["path"], True, body,
                      side_effects={"cache_path": f"rness/io/input/{cache_name}"})


def run_wikisink(project_dir: Path, call: ToolCall) -> ToolResult:
    if not broker.is_enabled("wikisink_enabled"):
        return _denied("wikisink")
    from . import update as wupdate

    scope = (call.extra.get("scope") or "watched").strip()
    if scope not in ("watched", "report-only"):
        scope = "watched"
    try:
        report = wupdate.run_wikisink(project_dir, scope=scope)
    except wzim.WikisinkUnavailable as e:
        return _unavailable("wikisink", scope, e)
    return ToolResult("wikisink", scope, True, report)


def run_wiki_status(project_dir: Path, call: ToolCall) -> ToolResult:
    if not broker.is_enabled("wikisink_enabled"):
        return _denied("wiki_status")
    cfg = wconfig.load_config()
    installed = wconfig.installed(cfg)
    lines = []
    if installed:
        try:
            info = wzim.snapshot_info()
            lines.append(
                f"archive: {info['filename']} — {info['article_count']} articles, "
                f"snapshot date {info['date']} "
                f"(flavor {(cfg.get('zim') or {}).get('flavor')})")
        except wzim.WikisinkUnavailable as e:
            lines.append(f"archive present but unreadable: {e}")
    else:
        lines.append("no archive installed — the user can set one up via "
                     "the 🚰 button in the top bar.")
    dl = cfg.get("download") or {}
    if dl.get("status") not in (None, "idle", "done"):
        pct = (100 * dl.get("bytes_done", 0) / dl["bytes_total"]) if dl.get("bytes_total") else 0
        lines.append(f"download {dl['status']}: {dl.get('filename')} ({pct:.0f}%)")
    from . import comments as wcomments

    commented = wcomments.commented_articles()
    lines.append(f"watched articles: {len(cfg.get('watched', []))} "
                 f"(saved and/or commented); commented: {len(commented)}; "
                 f"deletion overrides: {len(cfg.get('overrides', []))}")
    if cfg.get("overrides"):
        lines.append("overridden (preserved locally, never refreshed): " +
                     ", ".join(o["title"] for o in cfg["overrides"][:10]))
    lines.append(f"last wikisink run: {cfg.get('last_wikisink_at') or 'never'}")
    lines.append(f"live updates toggle: "
                 f"{'on' if broker.is_enabled('wikisink_live_updates') else 'off'}")
    return ToolResult("wiki_status", "wikisink", True, "\n".join(lines))
