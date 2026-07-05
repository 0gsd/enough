"""Google-Docs-style comments on wiki articles.

Central store: one JSON file per article at
`{storage_dir}/comments/<key>.json` — comments attach to the article's
identity, not to any saved file, so they persist whether the article was
saved, merely browsed, updated by a wikisink run, or even deleted from
live Wikipedia.

Anchor model (three-tier degrade, mirroring highlights.py's spirit):

- `quote` anchors carry the selected text plus ≤60 chars of prefix and
  suffix. Rendering tries an exact quote match (prefix/suffix break
  ties); if the text has changed, it falls back to the recorded
  heading-path + paragraph index; if that's gone too, the comment
  survives as "orphaned" — listed in the panel, no in-text mark.
- `paragraph` anchors (the "add comment here" button) skip the quote
  and pin straight to heading-path + paragraph index.

`state` records how the comment last rendered (anchored | paragraph |
orphaned) so the panel can label degraded comments. Comments are never
deleted automatically.
"""

from __future__ import annotations

import json
import logging
import secrets
from pathlib import Path
from typing import Any

from . import config as wconfig

log = logging.getLogger("enough.wikisink")

VALID_STATES = ("anchored", "paragraph", "orphaned")


def _doc_path(article_path: str) -> Path:
    return wconfig.comments_dir() / f"{wconfig.article_key(article_path)}.json"


def load_comments(article_path: str) -> dict[str, Any]:
    p = _doc_path(article_path)
    if p.is_file():
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(doc, dict) and isinstance(doc.get("comments"), list):
                return doc
        except (OSError, json.JSONDecodeError) as e:
            log.warning("wikisink comments read failed for %s (%s)", p, e)
    return {"version": 1, "article_path": article_path,
            "article_title": article_path, "comments": []}


def _save(doc: dict[str, Any]) -> None:
    p = _doc_path(doc["article_path"])
    if not doc["comments"]:
        p.unlink(missing_ok=True)
        return
    p.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def _normalize_anchor(anchor: dict[str, Any] | None) -> dict[str, Any]:
    anchor = anchor or {}
    a_type = anchor.get("type") if anchor.get("type") in ("quote", "paragraph") else "paragraph"
    return {
        "type": a_type,
        "quote": str(anchor.get("quote") or "")[:2000],
        "prefix": str(anchor.get("prefix") or "")[-60:],
        "suffix": str(anchor.get("suffix") or "")[:60],
        "heading_path": [str(h)[:200] for h in (anchor.get("heading_path") or [])][:4],
        "para_index": anchor.get("para_index") if isinstance(anchor.get("para_index"), int) else None,
        "source": anchor.get("source") or {},
    }


def add_comment(article_path: str, article_title: str, body: str,
                anchor: dict[str, Any] | None) -> dict[str, Any]:
    doc = load_comments(article_path)
    doc["article_title"] = article_title or doc.get("article_title") or article_path
    anchor = _normalize_anchor(anchor)
    entry = {
        "id": f"c_{secrets.token_hex(4)}",
        "body": body,
        "created_at": wconfig._now_iso(),
        "updated_at": None,
        "resolved": False,
        "replies": [],
        "anchor": anchor,
        "state": "anchored" if (anchor["type"] == "quote" and anchor["quote"]) else "paragraph",
    }
    doc["comments"].append(entry)
    _save(doc)
    # Commented articles join the watch registry (refreshed by wikisink runs).
    wconfig.upsert_watched(article_path, doc["article_title"], commented=True)
    return entry


def update_comment(article_path: str, comment_id: str, *, body: str | None = None,
                   resolved: bool | None = None, state: str | None = None) -> dict[str, Any]:
    doc = load_comments(article_path)
    entry = next((c for c in doc["comments"] if c.get("id") == comment_id), None)
    if entry is None:
        raise KeyError(comment_id)
    if body is not None:
        entry["body"] = body
        entry["updated_at"] = wconfig._now_iso()
    if resolved is not None:
        entry["resolved"] = bool(resolved)
    if state is not None and state in VALID_STATES:
        entry["state"] = state
    _save(doc)
    return entry


def add_reply(article_path: str, comment_id: str, body: str) -> dict[str, Any]:
    doc = load_comments(article_path)
    entry = next((c for c in doc["comments"] if c.get("id") == comment_id), None)
    if entry is None:
        raise KeyError(comment_id)
    reply = {"id": f"r_{secrets.token_hex(4)}", "body": body,
             "created_at": wconfig._now_iso()}
    entry.setdefault("replies", []).append(reply)
    _save(doc)
    return reply


def delete_comment(article_path: str, comment_id: str) -> None:
    doc = load_comments(article_path)
    before = len(doc["comments"])
    doc["comments"] = [c for c in doc["comments"] if c.get("id") != comment_id]
    if len(doc["comments"]) == before:
        raise KeyError(comment_id)
    _save(doc)
    if not doc["comments"]:
        wconfig.upsert_watched(article_path, doc.get("article_title") or article_path,
                               commented=False)


def commented_articles() -> list[dict[str, str]]:
    """[{path, title, count}] for every article with live comments —
    input to the update engine's watched set."""
    out = []
    for p in sorted(wconfig.comments_dir().glob("*.json")):
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(doc, dict) and doc.get("comments"):
            out.append({"path": doc.get("article_path", ""),
                        "title": doc.get("article_title", ""),
                        "count": len(doc["comments"])})
    return out
