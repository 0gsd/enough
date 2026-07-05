"""wikisink configuration + storage layout.

One JSON file at ~/enough/config/wikisink.json tracks what's installed,
download progress (so multi-hour downloads survive restarts), the watch
registry (saved / commented articles the update engine refreshes), the
deletion-override registry, and reading state (last viewed article plus
a bounded ring of recently viewed paths used for deletion checks).

Storage layout under `storage_dir` (default ~/enough/wikisink, user may
point it anywhere, external drives included):

    <flavor>_<date>.zim         the base archive, read in place
    downloads/<file>.part       resumable partial download
    overlay/<key>.html + .meta.json    live-refreshed watched articles
    preserved/<key>.html + .meta.json  deletion-overridden articles
    comments/<key>.json         per-article comment threads
    rankings/<date>-daily.json  AQS top-1000 pageview snapshots
    state/run-<ts>/             wikisink update-run scratch + reports

None of this ever appears in the file-manager tree (server-side filter);
only articles explicitly saved to a project's wiki/ or infoworld/wiki/
are user-visible files.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import os
import re

from pathlib import Path
from typing import Any

log = logging.getLogger("enough.wikisink")

# ENOUGH_WIKISINK_CONFIG overrides the config location — a test/dev hook
# so suites and smoke runs never touch the real ~/enough state.
CONFIG_PATH = Path(
    os.environ.get("ENOUGH_WIKISINK_CONFIG")
    or (Path.home() / "enough" / "config" / "wikisink.json")
).expanduser()
DEFAULT_STORAGE_DIR = Path.home() / "enough" / "wikisink"

VIEWED_RING_MAX = 200


def _defaults() -> dict[str, Any]:
    return {
        "version": 1,
        "storage_dir": str(DEFAULT_STORAGE_DIR),
        "zim": {
            "flavor": None,       # e.g. "wikipedia_en_top1m_nopic"
            "filename": None,     # e.g. "wikipedia_en_top1m_nopic_2026-04.zim"
            "snapshot": None,     # e.g. "2026-04"
            "url": None,
            "size_bytes": 0,
            "installed_at": None,
        },
        "download": {
            "status": "idle",     # idle | downloading | paused | error | done
            "filename": None,
            "url": None,
            "bytes_done": 0,
            "bytes_total": 0,
            "error": None,
        },
        "last_viewed": None,      # {"path": ..., "title": ...}
        "viewed_ring": [],        # [{"path", "title"}] capped at VIEWED_RING_MAX
        "last_wikisink_at": None, # ISO timestamp of last completed update run
        "watched": [],            # [{"path", "title", "saved_to": [...], "commented", "saved_at"}]
        "overrides": [],          # [{"path", "title", "preserved_file", "reason",
                                  #   "deletion_log_excerpt", "detected_at", "overridden_at"}]
    }


def load_config() -> dict[str, Any]:
    """Merged config: defaults overlaid with whatever's on disk. Missing
    file, unknown keys, or wrong types all fall through to defaults —
    callers never handle KeyError. (Same contract as broker.load_config.)"""
    cfg = _defaults()
    if CONFIG_PATH.is_file():
        try:
            on_disk = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(on_disk, dict):
                for key, value in on_disk.items():
                    if key not in cfg:
                        continue
                    if isinstance(cfg[key], dict) and isinstance(value, dict):
                        for k2, v2 in value.items():
                            if k2 in cfg[key]:
                                cfg[key][k2] = v2
                    elif type(value) is type(cfg[key]) or cfg[key] is None or value is None:
                        cfg[key] = value
        except (OSError, json.JSONDecodeError) as e:
            log.warning("wikisink config read failed (%s); using defaults", e)
    return cfg


def save_config(cfg: dict[str, Any]) -> None:
    """Persist recognized keys only, dropping anything stale."""
    base = _defaults()
    safe = {k: cfg.get(k, base[k]) for k in base}
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(safe, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Storage paths
# ---------------------------------------------------------------------------

def storage_dir(cfg: dict[str, Any] | None = None) -> Path:
    cfg = cfg or load_config()
    raw = cfg.get("storage_dir") or str(DEFAULT_STORAGE_DIR)
    return Path(raw).expanduser()


def _subdir(name: str, cfg: dict[str, Any] | None = None) -> Path:
    d = storage_dir(cfg) / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def downloads_dir(cfg: dict[str, Any] | None = None) -> Path:
    return _subdir("downloads", cfg)


def overlay_dir(cfg: dict[str, Any] | None = None) -> Path:
    return _subdir("overlay", cfg)


def preserved_dir(cfg: dict[str, Any] | None = None) -> Path:
    return _subdir("preserved", cfg)


def comments_dir(cfg: dict[str, Any] | None = None) -> Path:
    return _subdir("comments", cfg)


def rankings_dir(cfg: dict[str, Any] | None = None) -> Path:
    return _subdir("rankings", cfg)


def state_dir(cfg: dict[str, Any] | None = None) -> Path:
    return _subdir("state", cfg)


def zim_file(cfg: dict[str, Any] | None = None) -> Path | None:
    """Path to the installed base archive, or None if not installed."""
    cfg = cfg or load_config()
    name = (cfg.get("zim") or {}).get("filename")
    if not name:
        return None
    p = storage_dir(cfg) / name
    return p if p.is_file() else None


def installed(cfg: dict[str, Any] | None = None) -> bool:
    return zim_file(cfg) is not None


# ---------------------------------------------------------------------------
# Article keys — filenames for overlay/preserved/comments stores
# ---------------------------------------------------------------------------

def article_key(path_or_title: str) -> str:
    """Stable filesystem key for an article: readable slug + short hash
    of the exact ZIM path/title (mirrors tools._slugify/_short_hash;
    local copies keep this module import-light and cycle-free)."""
    s = re.sub(r"[^a-zA-Z0-9]+", "-", path_or_title).strip("-").lower()
    slug = (s[:60].strip("-")) or "untitled"
    digest = hashlib.sha256(path_or_title.encode("utf-8", errors="ignore")).hexdigest()[:8]
    return f"{slug}-{digest}"


# ---------------------------------------------------------------------------
# Reading state + registries (all load-modify-save on the tiny JSON file)
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record_viewed(path: str, title: str) -> None:
    """Note the article just opened: becomes last_viewed and joins the
    bounded viewed ring (dedup by path, most recent last)."""
    cfg = load_config()
    entry = {"path": path, "title": title}
    cfg["last_viewed"] = entry
    ring = [e for e in cfg.get("viewed_ring", []) if e.get("path") != path]
    ring.append(entry)
    cfg["viewed_ring"] = ring[-VIEWED_RING_MAX:]
    save_config(cfg)


def upsert_watched(path: str, title: str, *, saved_to: str | None = None,
                   commented: bool | None = None) -> None:
    """Add or update a watch-registry entry. `saved_to` is a destination
    tag ("project:<abs-dir>" or "infoworld") appended if new; `commented`
    flips the commented flag."""
    cfg = load_config()
    watched = cfg.get("watched", [])
    entry = next((w for w in watched if w.get("path") == path), None)
    if entry is None:
        entry = {"path": path, "title": title, "saved_to": [],
                 "commented": False, "saved_at": None}
        watched.append(entry)
    entry["title"] = title or entry.get("title")
    if saved_to and saved_to not in entry["saved_to"]:
        entry["saved_to"].append(saved_to)
        entry["saved_at"] = _now_iso()
    if commented is not None:
        entry["commented"] = bool(commented)
    cfg["watched"] = watched
    save_config(cfg)


def is_overridden(path: str, cfg: dict[str, Any] | None = None) -> bool:
    cfg = cfg or load_config()
    return any(o.get("path") == path for o in cfg.get("overrides", []))


def add_override(path: str, title: str, *, preserved_file: str, reason: str = "",
                 deletion_log_excerpt: str = "", detected_at: str | None = None) -> None:
    cfg = load_config()
    if is_overridden(path, cfg):
        return
    cfg["overrides"].append({
        "path": path,
        "title": title,
        "preserved_file": preserved_file,
        "reason": reason,
        "deletion_log_excerpt": deletion_log_excerpt,
        "detected_at": detected_at,
        "overridden_at": _now_iso(),
    })
    save_config(cfg)


def remove_override(path: str) -> dict[str, Any] | None:
    """Drop an override from the registry; returns the removed entry so
    the caller can decide what to do with the preserved file (we never
    delete it here — deletions are user-confirmed)."""
    cfg = load_config()
    removed = next((o for o in cfg["overrides"] if o.get("path") == path), None)
    if removed is not None:
        cfg["overrides"] = [o for o in cfg["overrides"] if o.get("path") != path]
        save_config(cfg)
    return removed
