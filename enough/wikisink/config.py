"""wikisink configuration + storage layout.

One JSON file at ~/enough/config/wikisink.json tracks what's installed,
download progress (so multi-hour downloads survive restarts), the watch
registry (saved / commented articles the update engine refreshes), the
deletion-override registry, and reading state (last viewed article plus
a bounded ring of recently viewed paths used for deletion checks).

Since schema v2 there can be several *installs* — base archives living
in different places (internal disk, external drives) — with one marked
active. An install whose file isn't currently reachable (drive
detached) stays registered; the UI offers switching to another install
or adding one, and everything heals when the drive comes back.

Each install's storage dir holds only the big, replaceable bits:

    <flavor>_<date>.zim         the base archive, read in place
    downloads/<file>.part       resumable partial download

The user's own data lives under `data_dir` (v2 default
~/enough/wikisink — always the local disk for fresh setups, so comments
and preserved articles never vanish with a drive; v1 configs keep their
original storage dir to avoid moving files):

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
        "version": 2,
        "data_dir": str(DEFAULT_STORAGE_DIR),
        "installs": [],           # [{"id", "storage_dir", "flavor", "filename",
                                  #   "snapshot", "url", "size_bytes", "installed_at"}]
        "active_install": None,   # id of the install being served
        "download": {
            "status": "idle",     # idle | downloading | paused | error | done
            "filename": None,
            "url": None,
            "storage_dir": None,  # where this download lands
            "replace_id": None,   # install being upgraded in place, if any
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


def _migrate_v1(cfg: dict[str, Any], on_disk: dict[str, Any]) -> None:
    """Fold a v1 single-install config into the v2 shape, in place.
    The old storage dir becomes data_dir (nothing on disk moves) and the
    old zim block, if an archive was installed, becomes the one active
    install. Next save_config persists the v2 shape."""
    old_storage = on_disk.get("storage_dir") or str(DEFAULT_STORAGE_DIR)
    cfg["data_dir"] = old_storage
    zim = on_disk.get("zim") or {}
    if isinstance(zim, dict) and zim.get("filename"):
        entry = {
            "id": install_id(old_storage, zim["filename"]),
            "storage_dir": old_storage,
            "flavor": zim.get("flavor"),
            "filename": zim["filename"],
            "snapshot": zim.get("snapshot"),
            "url": zim.get("url"),
            "size_bytes": zim.get("size_bytes") or 0,
            "installed_at": zim.get("installed_at"),
        }
        cfg["installs"] = [entry]
        cfg["active_install"] = entry["id"]
    if cfg["download"].get("filename") and not cfg["download"].get("storage_dir"):
        cfg["download"]["storage_dir"] = old_storage


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
                if int(on_disk.get("version") or 1) < 2:
                    _migrate_v1(cfg, on_disk)
        except (OSError, json.JSONDecodeError, ValueError) as e:
            log.warning("wikisink config read failed (%s); using defaults", e)
    cfg["version"] = 2
    return cfg


def save_config(cfg: dict[str, Any]) -> None:
    """Persist recognized keys only, dropping anything stale."""
    base = _defaults()
    safe = {k: cfg.get(k, base[k]) for k in base}
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(safe, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Installs — registered base archives, one active
# ---------------------------------------------------------------------------

def install_id(storage_dir: str, filename: str) -> str:
    """Stable id for an install: where it lives + what file it is."""
    return hashlib.sha256(f"{storage_dir}\n{filename}".encode()).hexdigest()[:10]


def installs(cfg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    cfg = cfg or load_config()
    return [i for i in cfg.get("installs", []) if isinstance(i, dict) and i.get("filename")]


def get_install(install: str, cfg: dict[str, Any] | None = None) -> dict[str, Any] | None:
    return next((i for i in installs(cfg) if i.get("id") == install), None)


def active_install(cfg: dict[str, Any] | None = None) -> dict[str, Any] | None:
    cfg = cfg or load_config()
    return get_install(cfg.get("active_install") or "", cfg)


def install_zim_path(entry: dict[str, Any]) -> Path:
    """Where this install's archive lives (or would live) — existence not
    checked; pair with install_available."""
    return Path(entry.get("storage_dir") or str(DEFAULT_STORAGE_DIR)).expanduser() \
        / entry["filename"]


def install_available(entry: dict[str, Any]) -> bool:
    try:
        return install_zim_path(entry).is_file()
    except OSError:
        return False


def volume_mounted(p: Path) -> bool:
    """False when `p` sits on a macOS external volume that isn't mounted.
    Guards every mkdir under a user-chosen dir: creating
    /Volumes/<name>/... while the drive is away would silently plant a
    real directory on the boot volume and then shadow the next mount."""
    parts = p.expanduser().parts
    if len(parts) >= 3 and parts[0] == "/" and parts[1] == "Volumes":
        return Path("/Volumes", parts[2]).exists()
    return True


def zim_file(cfg: dict[str, Any] | None = None) -> Path | None:
    """Path to the active install's archive, or None when there is no
    active install or its file isn't reachable right now."""
    entry = active_install(cfg)
    if entry is None:
        return None
    p = install_zim_path(entry)
    return p if install_available(entry) else None


def installed(cfg: dict[str, Any] | None = None) -> bool:
    """True when the active archive is actually servable right now."""
    return zim_file(cfg) is not None


def configured(cfg: dict[str, Any] | None = None) -> bool:
    """True when any install is registered, reachable or not."""
    return bool(installs(cfg))


def unavailable_reason(cfg: dict[str, Any] | None = None) -> str | None:
    """User-facing reason the archive can't be served, or None when it
    can. Distinguishes never-installed from drive-not-attached."""
    cfg = cfg or load_config()
    if installed(cfg):
        return None
    entry = active_install(cfg)
    if entry is None:
        return ("no local wikipedia archive is installed yet — click the 🚰 "
                "button in the top bar to set one up.")
    where = entry.get("storage_dir") or str(DEFAULT_STORAGE_DIR)
    others = [i for i in installs(cfg)
              if i.get("id") != entry.get("id") and install_available(i)]
    msg = (f"the active wikipedia archive ({entry.get('filename')}) isn't "
           f"reachable at {where} — if that's an external drive, it may be "
           "detached. reattach it, or click 🚰 to switch installs or add one.")
    if others:
        msg += (f" {len(others)} other install"
                f"{'s are' if len(others) > 1 else ' is'} available right now.")
    return msg


def add_install(entry: dict[str, Any], *, activate: bool = True) -> dict[str, Any]:
    """Register an install (replacing any existing entry with the same
    id) and optionally make it active. Returns the saved config."""
    cfg = load_config()
    cfg["installs"] = [i for i in installs(cfg) if i.get("id") != entry["id"]] + [entry]
    if activate:
        cfg["active_install"] = entry["id"]
    save_config(cfg)
    return cfg


def remove_install(install: str) -> dict[str, Any] | None:
    """Forget an install (registry only — the archive file always stays
    on disk; deleting gigabytes is the user's own act, in the Finder).
    If it was active, fall back to any reachable install. Returns the
    removed entry, or None if the id is unknown."""
    cfg = load_config()
    removed = get_install(install, cfg)
    if removed is None:
        return None
    cfg["installs"] = [i for i in installs(cfg) if i.get("id") != install]
    if cfg.get("active_install") == install:
        fallback = next((i for i in cfg["installs"] if install_available(i)),
                        next(iter(cfg["installs"]), None))
        cfg["active_install"] = fallback["id"] if fallback else None
    save_config(cfg)
    return removed


def set_active_install(install: str) -> dict[str, Any] | None:
    """Switch the served archive. Returns the entry, or None if unknown."""
    cfg = load_config()
    entry = get_install(install, cfg)
    if entry is None:
        return None
    cfg["active_install"] = install
    save_config(cfg)
    return entry


def active_zim_meta(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """The active install's metadata (flavor/snapshot/filename/…), or an
    empty dict — shaped like the old single-install `zim` block for the
    provenance strings sprinkled around the package."""
    return active_install(cfg) or {}


# ---------------------------------------------------------------------------
# Data paths — the user's own wikisink data, independent of any install
# ---------------------------------------------------------------------------

def data_dir(cfg: dict[str, Any] | None = None) -> Path:
    cfg = cfg or load_config()
    raw = cfg.get("data_dir") or str(DEFAULT_STORAGE_DIR)
    return Path(raw).expanduser()


def _subdir(name: str, cfg: dict[str, Any] | None = None) -> Path:
    base = data_dir(cfg)
    if not volume_mounted(base):
        raise OSError(
            f"wikisink data at {base} isn't reachable — the volume isn't mounted")
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def downloads_dir(storage: Path) -> Path:
    """Partial downloads live beside their final destination (same
    volume, so the finishing rename is atomic)."""
    if not volume_mounted(storage):
        raise OSError(
            f"download target {storage} isn't reachable — the volume isn't mounted")
    d = storage / "downloads"
    d.mkdir(parents=True, exist_ok=True)
    return d


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
