"""Highlight metadata storage for review-mode highlights.

Per-document JSON sidecar living next to the highlighted file:
`<dirname>/.<filename>.highlights.json`. Hidden so it doesn't clutter
file managers; per-doc so that deleting / moving the document loses
exactly its own highlights and nothing else.

Every CRUD operation also writes a journal entry through the existing
broker trace so highlight activity shows up alongside tool calls in the
session-logs/<date>-broker.md file. (The user explicitly drew the
parallel: highlights are "broker-managed metadata" in the same family
as tool-call traces.)

Storage shape (one JSON file per highlighted doc):

    {
      "version": 1,
      "doc_path": "rness/io/output/foo.md",
      "highlights": [
        {
          "id": "h_<8-char-hex>",
          "color": "yellow" | "green" | "blue" | "pink",
          "snippet": "the text the user actually selected (rendered, not source)",
          "before_anchor": "up to 60 rendered chars immediately before",
          "after_anchor":  "up to 60 rendered chars immediately after",
          "src_start": 1234,    # source-position hint; may be invalidated by external edits
          "src_end":   1289,
          "created_at": "2026-05-14T16:23:00Z",
          "stale": false        # set true by Phase 5 when re-anchoring fails
        },
        ...
      ]
    }

Phase 3 stores src_start/src_end as hints; rendering uses snippet +
anchors (more robust against minor edits). Phase 5 will add fuzzy
re-anchoring that flips `stale: true` when even the snippet+anchor
search fails.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import secrets
from pathlib import Path
from typing import Any

from . import broker

log = logging.getLogger("enough.highlights")

SCHEMA_VERSION = 1
ALLOWED_COLORS = ("yellow", "green", "blue", "pink")


# ---------------------------------------------------------------------------
# Sidecar location
# ---------------------------------------------------------------------------

def _sidecar_path(project_dir: Path, doc_rel: str) -> Path:
    """Return the absolute path of the per-doc highlights sidecar.

    `doc_rel` is the doc's path relative to the project directory (the
    same form the rest of the harness uses). The sidecar lives in the
    SAME directory as the doc with a `.<filename>.highlights.json`
    name — hidden + co-located so deleting the doc lets the user
    delete one obvious sibling to clean up."""
    doc = (project_dir / doc_rel).resolve()
    return doc.parent / f".{doc.name}.highlights.json"


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

def load_highlights(project_dir: Path, doc_rel: str) -> list[dict[str, Any]]:
    """Read the sidecar and return the highlights list. Empty list when
    no sidecar exists or the file is malformed (we'd rather render
    silently than throw on a corrupted JSON)."""
    sidecar = _sidecar_path(project_dir, doc_rel)
    if not sidecar.is_file():
        return []
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        log.warning("highlights sidecar unreadable (%s); returning empty", e)
        return []
    if not isinstance(data, dict):
        return []
    items = data.get("highlights")
    if not isinstance(items, list):
        return []
    # Drop any malformed entries silently; an entry with the wrong
    # shape is more confusing than no entry at all.
    out: list[dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        if it.get("color") not in ALLOWED_COLORS:
            continue
        if not isinstance(it.get("snippet"), str) or not it["snippet"]:
            continue
        out.append(it)
    return out


def _save_all(project_dir: Path, doc_rel: str, highlights: list[dict[str, Any]]) -> None:
    """Write the full sidecar. When `highlights` is empty we delete the
    sidecar instead of leaving a `{"highlights": []}` carcass behind —
    a user who clears every highlight on a file should see the dotfile
    disappear too."""
    sidecar = _sidecar_path(project_dir, doc_rel)
    if not highlights:
        if sidecar.exists():
            try:
                sidecar.unlink()
            except OSError as e:
                log.warning("failed to remove empty sidecar %s (%s)", sidecar, e)
        return
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": SCHEMA_VERSION,
        "doc_path": doc_rel,
        "highlights": highlights,
    }
    sidecar.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def _new_id() -> str:
    """Short random hex id, prefixed `h_` so it's grep-able. 8 hex chars
    gives ~4 billion possibilities — collision-safe for any plausible
    per-doc highlight count without the visual heaviness of a UUID."""
    return "h_" + secrets.token_hex(4)


def add_highlight(
    project_dir: Path,
    doc_rel: str,
    *,
    color: str,
    snippet: str,
    before_anchor: str = "",
    after_anchor: str = "",
    src_start: int | None = None,
    src_end: int | None = None,
) -> dict[str, Any]:
    """Create a new highlight entry, persist it, and journal the action.

    Returns the created dict (including the assigned id and timestamp)
    so the caller can echo it back to the UI without reloading."""
    if color not in ALLOWED_COLORS:
        raise ValueError(f"unknown highlight color {color!r}; allowed: {ALLOWED_COLORS}")
    if not snippet:
        raise ValueError("highlight snippet cannot be empty")
    items = load_highlights(project_dir, doc_rel)
    entry = {
        "id": _new_id(),
        "color": color,
        "snippet": snippet,
        "before_anchor": before_anchor or "",
        "after_anchor": after_anchor or "",
        "src_start": int(src_start) if src_start is not None else None,
        "src_end": int(src_end) if src_end is not None else None,
        "created_at": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stale": False,
    }
    items.append(entry)
    _save_all(project_dir, doc_rel, items)
    broker.trace(
        project_dir,
        tool="highlight",
        decision=f"add ({color})",
        args={"path": doc_rel, "id": entry["id"], "snippet": _short(snippet)},
        result_ok=True,
        result_summary=f"applied {color} highlight",
    )
    return entry


def delete_highlight(project_dir: Path, doc_rel: str, hl_id: str) -> bool:
    """Remove the highlight by id. Returns True if removed, False if no
    such id existed (caller can decide whether that's a 404)."""
    items = load_highlights(project_dir, doc_rel)
    new_items = [h for h in items if h.get("id") != hl_id]
    if len(new_items) == len(items):
        return False
    _save_all(project_dir, doc_rel, new_items)
    broker.trace(
        project_dir,
        tool="highlight",
        decision="delete",
        args={"path": doc_rel, "id": hl_id},
        result_ok=True,
        result_summary="removed highlight",
    )
    return True


def update_highlight(
    project_dir: Path,
    doc_rel: str,
    hl_id: str,
    **changes: Any,
) -> dict[str, Any] | None:
    """Update fields of an existing highlight. Used by Phase 5 to flip
    `stale` when re-anchoring fails. Returns the updated entry, or
    None when the id doesn't exist."""
    items = load_highlights(project_dir, doc_rel)
    target = None
    for h in items:
        if h.get("id") == hl_id:
            target = h
            break
    if target is None:
        return None
    # Only allow safe fields to be updated; never let the caller change
    # the id or the created_at stamp.
    safe_keys = {"color", "snippet", "before_anchor", "after_anchor",
                 "src_start", "src_end", "stale"}
    for k, v in changes.items():
        if k in safe_keys:
            target[k] = v
    _save_all(project_dir, doc_rel, items)
    broker.trace(
        project_dir,
        tool="highlight",
        decision="update",
        args={"path": doc_rel, "id": hl_id, "fields": ",".join(sorted(changes))},
        result_ok=True,
        result_summary="updated highlight",
    )
    return target


# ---------------------------------------------------------------------------
# Agent-facing query helpers
# ---------------------------------------------------------------------------

def highlights_by_color(
    project_dir: Path,
    doc_rel: str,
    color: str,
) -> list[dict[str, Any]]:
    """Subset of highlights for a single color. Used by the agent's
    `read_highlights` tool (Phase 4) when the user says e.g. 'edit the
    green sections one by one' — agent gets a clean list to iterate."""
    if color not in ALLOWED_COLORS:
        return []
    return [h for h in load_highlights(project_dir, doc_rel) if h.get("color") == color]


def highlight_summary(project_dir: Path, doc_rel: str) -> dict[str, int]:
    """Count of highlights per color. Used in the system prompt
    surface (Phase 4) so the agent knows at a glance what's on the
    active doc."""
    counts = {c: 0 for c in ALLOWED_COLORS}
    for h in load_highlights(project_dir, doc_rel):
        c = h.get("color")
        if c in counts:
            counts[c] += 1
    return counts


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _short(s: str, n: int = 60) -> str:
    """Truncate for journal entries — keeps the broker log scannable."""
    s = s.replace("\n", " ")
    return s if len(s) <= n else s[:n] + "…"
