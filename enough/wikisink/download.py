"""Kiwix flavor discovery + resumable base-archive downloads.

Flavors are the curated English-Wikipedia ZIM builds we offer in the
setup wizard. The live listing at download.kiwix.org is an Apache-style
index; we parse it for the latest dated file per flavor and fall back to
a hardcoded table when offline (sizes then marked stale).

Downloads are streamed to `downloads/<file>.part` with HTTP Range resume
(Kiwix serves Accept-Ranges), progress persisted to wikisink.json every
few seconds so a multi-hour download survives quits and crashes, and
progress events fanned out over SSE for the setup modal.
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx

from . import config as wconfig
from . import zim as wzim

log = logging.getLogger("enough.wikisink")

LISTING_URL = "https://download.kiwix.org/zim/wikipedia/"

# Free-space safety margin over the (approximate) archive size.
DISK_MARGIN = 1.05

CHUNK_SIZE = 1024 * 1024          # 1 MiB
EMIT_INTERVAL = 0.5               # seconds between SSE progress events
PERSIST_INTERVAL = 5.0            # seconds between config progress writes


@dataclass(frozen=True)
class Flavor:
    key: str          # e.g. "top1m_nopic" (suffix of the ZIM basename)
    label: str
    blurb: str
    default: bool = False
    # Fallbacks when the live listing is unreachable (approximate).
    fallback_date: str = ""
    fallback_size: int = 0


_G = 1024 ** 3
_M = 1024 ** 2

FLAVORS: tuple[Flavor, ...] = (
    Flavor("top1m_nopic", "Top 1M articles, no images",
           "the million most-read articles — covers virtually everything "
           "anyone looks up", default=True,
           fallback_date="2026-04", fallback_size=16 * _G),
    Flavor("all_nopic", "Every article, no images",
           "the complete English Wikipedia text",
           fallback_date="2026-06", fallback_size=49 * _G),
    Flavor("top_nopic", "Top ~50k articles, no images",
           "a curated best-of slice; small and fast",
           fallback_date="2026-06", fallback_size=int(2.1 * _G)),
    Flavor("top_mini", "Top ~50k, intro-only",
           "just the lead section of each top article",
           fallback_date="2026-06", fallback_size=316 * _M),
    Flavor("simple_all_nopic", "Simple English, complete",
           "the full Simple English Wikipedia — plain language, tiny",
           fallback_date="2026-05", fallback_size=937 * _M),
)

_FLAVOR_KEYS = "|".join(f.key for f in FLAVORS)
_LISTING_RE = re.compile(
    r'<a href="(wikipedia_en_(' + _FLAVOR_KEYS + r')_(\d{4}-\d{2})\.zim)">'
    r"[^<]*</a>\s+[\d-]+ [\d:]+\s+([\d.]+[KMG]?)"
)


def _human_to_bytes(s: str) -> int:
    m = re.fullmatch(r"([\d.]+)([KMG]?)", s)
    if not m:
        return 0
    n = float(m.group(1))
    mult = {"": 1, "K": 1024, "M": _M, "G": _G}[m.group(2)]
    return int(n * mult)


def bytes_to_human(n: int) -> str:
    for suffix, size in (("GB", _G), ("MB", _M), ("KB", 1024)):
        if n >= size:
            return f"{n / size:.1f} {suffix}".replace(".0 ", " ")
    return f"{n} B"


def parse_listing(html: str) -> dict[str, dict[str, Any]]:
    """Latest dated file per flavor key from the Apache index HTML."""
    latest: dict[str, dict[str, Any]] = {}
    for filename, key, date, size in _LISTING_RE.findall(html):
        cur = latest.get(key)
        if cur is None or date > cur["date"]:
            latest[key] = {
                "filename": filename,
                "date": date,
                "size_bytes": _human_to_bytes(size),
                "url": LISTING_URL + filename,
            }
    return latest


_listing_cache: tuple[float, dict[str, dict[str, Any]]] | None = None
_LISTING_TTL = 3600.0


def fetch_listing(force: bool = False) -> tuple[dict[str, dict[str, Any]], bool]:
    """(latest-per-flavor, live) — live=False means fallback data."""
    global _listing_cache
    if not force and _listing_cache and time.monotonic() - _listing_cache[0] < _LISTING_TTL:
        return _listing_cache[1], True
    try:
        resp = httpx.get(LISTING_URL, timeout=60, follow_redirects=True)
        resp.raise_for_status()
        parsed = parse_listing(resp.text)
        if parsed:
            _listing_cache = (time.monotonic(), parsed)
            return parsed, True
    except (httpx.HTTPError, OSError) as e:
        log.warning("kiwix listing fetch failed (%s); using fallback table", e)
    fallback = {
        f.key: {
            "filename": f"wikipedia_en_{f.key}_{f.fallback_date}.zim",
            "date": f.fallback_date,
            "size_bytes": f.fallback_size,
            "url": f"{LISTING_URL}wikipedia_en_{f.key}_{f.fallback_date}.zim",
        }
        for f in FLAVORS
    }
    return fallback, False


def list_flavors(force: bool = False) -> dict[str, Any]:
    """Wizard-ready flavor list, default first."""
    listing, live = fetch_listing(force)
    out = []
    for f in FLAVORS:
        entry = listing.get(f.key)
        if not entry:
            continue
        out.append({
            "flavor": f.key,
            "label": f.label,
            "blurb": f.blurb,
            "is_default": f.default,
            "filename": entry["filename"],
            "url": entry["url"],
            "date": entry["date"],
            "size_bytes": entry["size_bytes"],
            "size_human": bytes_to_human(entry["size_bytes"]),
        })
    return {"live": live, "flavors": out}


def listing_is_cached() -> bool:
    return (_listing_cache is not None
            and time.monotonic() - _listing_cache[0] < _LISTING_TTL)


def newer_snapshot_available(cfg: dict[str, Any] | None = None,
                             *, cached_only: bool = False) -> dict[str, Any] | None:
    """Newer listing entry for the installed flavor, if any. With
    cached_only, never touches the network (status endpoint stays fast;
    the setup modal's flavors fetch warms the cache)."""
    if cached_only and not listing_is_cached():
        return None
    cfg = cfg or wconfig.load_config()
    zim = wconfig.active_zim_meta(cfg)
    flavor, snapshot = zim.get("flavor"), zim.get("snapshot")
    if not flavor or not snapshot:
        return None
    listing, live = fetch_listing()
    entry = listing.get(flavor)
    if live and entry and entry["date"] > snapshot:
        return {**entry, "flavor": flavor,
                "size_human": bytes_to_human(entry["size_bytes"])}
    return None


# ---------------------------------------------------------------------------
# Download manager — one per server process
# ---------------------------------------------------------------------------

EmitFn = Callable[[str, dict[str, Any]], Awaitable[None]]


class DownloadError(RuntimeError):
    """User-facing download failure."""


class DownloadManager:
    def __init__(self, emit: EmitFn | None = None):
        self._emit = emit
        self._task: asyncio.Task | None = None
        self._pause = False
        self._cancel = False

    @property
    def active(self) -> bool:
        return self._task is not None and not self._task.done()

    async def _fire(self, data: dict[str, Any]) -> None:
        if self._emit is not None:
            try:
                await self._emit("wiki_download", data)
            except Exception:  # noqa: BLE001 — progress must never kill the download
                log.exception("wiki_download emit failed")

    def _persist(self, **updates: Any) -> dict[str, Any]:
        cfg = wconfig.load_config()
        cfg["download"] = {**cfg["download"], **updates}
        wconfig.save_config(cfg)
        return cfg["download"]

    def preflight(self, size_bytes: int, storage: Path) -> None:
        if not wconfig.volume_mounted(storage):
            raise DownloadError(
                f"storage dir {storage} isn't reachable — is the drive attached?")
        storage.mkdir(parents=True, exist_ok=True)
        if not (storage / ".").exists():
            raise DownloadError(f"storage dir {storage} isn't reachable")
        free = shutil.disk_usage(storage).free
        needed = int(size_bytes * DISK_MARGIN)
        if free < needed:
            raise DownloadError(
                f"not enough free space at {storage}: need about "
                f"{bytes_to_human(needed)}, have {bytes_to_human(free)}."
            )

    def start(self, *, flavor: str, filename: str, url: str, size_bytes: int,
              snapshot: str, storage_dir: str | None = None,
              replace_id: str | None = None) -> None:
        """Kick off (or resume) a download as a background task on the
        running event loop. The finished archive is registered as a new
        install (activated on completion); `replace_id` instead upgrades
        that install in place — its old file is deleted when the new one
        lands. Raises DownloadError on preflight failure."""
        if self.active:
            raise DownloadError("a download is already running")
        if replace_id and wconfig.get_install(replace_id) is None:
            raise DownloadError(f"no install {replace_id!r} to replace")
        storage = Path(storage_dir or str(wconfig.DEFAULT_STORAGE_DIR)).expanduser()
        self.preflight(size_bytes, storage)
        self._pause = False
        self._cancel = False
        self._persist(status="downloading", filename=filename, url=url,
                      storage_dir=str(storage), replace_id=replace_id,
                      bytes_total=size_bytes, error=None)
        self._task = asyncio.get_running_loop().create_task(
            self._run(flavor=flavor, filename=filename, url=url,
                      snapshot=snapshot, storage=storage, replace_id=replace_id)
        )

    def resume(self) -> None:
        """Resume a paused/errored download recorded in config."""
        cfg = wconfig.load_config()
        dl = cfg["download"]
        if dl.get("status") not in ("paused", "error", "downloading") or not dl.get("url"):
            raise DownloadError("nothing to resume")
        # Flavor/snapshot ride along in the filename: wikipedia_en_<flavor>_<date>.zim
        m = re.fullmatch(r"wikipedia_en_(.+)_(\d{4}-\d{2})\.zim", dl["filename"] or "")
        flavor = m.group(1) if m else "unknown"
        snapshot = m.group(2) if m else ""
        self.start(flavor=flavor, filename=dl["filename"], url=dl["url"],
                   size_bytes=dl.get("bytes_total") or 0, snapshot=snapshot,
                   storage_dir=dl.get("storage_dir"),
                   replace_id=dl.get("replace_id"))

    def pause(self) -> None:
        self._pause = True

    def cancel(self) -> None:
        self._cancel = True
        if not self.active:
            # Nothing running (e.g. paused across a restart): clean up now.
            cfg = wconfig.load_config()
            dl = cfg["download"]
            storage = Path(dl.get("storage_dir")
                           or str(wconfig.DEFAULT_STORAGE_DIR)).expanduser()
            if wconfig.volume_mounted(storage):
                part = storage / "downloads" / f"{dl.get('filename')}.part"
                part.unlink(missing_ok=True)
            self._persist(status="idle", filename=None, url=None,
                          storage_dir=None, replace_id=None,
                          bytes_done=0, bytes_total=0, error=None)

    async def _run(self, *, flavor: str, filename: str, url: str,
                   snapshot: str, storage: Path, replace_id: str | None = None) -> None:
        part = wconfig.downloads_dir(storage) / f"{filename}.part"
        try:
            await self._download(url, part)
            if self._cancel:
                part.unlink(missing_ok=True)
                self._persist(status="idle", filename=None, url=None,
                              storage_dir=None, replace_id=None,
                              bytes_done=0, bytes_total=0, error=None)
                await self._fire({"status": "idle"})
                return
            if self._pause:
                done = part.stat().st_size if part.exists() else 0
                self._persist(status="paused", bytes_done=done)
                await self._fire({"status": "paused", "bytes_done": done})
                return
            # Complete: move into place and register + activate the
            # install. Other installs are untouched; only an explicit
            # replace (snapshot upgrade, confirmed at start) deletes its
            # predecessor's file.
            final = storage / filename
            part.rename(final)
            replaced = wconfig.get_install(replace_id) if replace_id else None
            entry = {
                "id": wconfig.install_id(str(storage), filename),
                "storage_dir": str(storage),
                "flavor": flavor, "filename": filename, "snapshot": snapshot,
                "url": url, "size_bytes": final.stat().st_size,
                "installed_at": wconfig._now_iso(),
            }
            wconfig.add_install(entry)
            if replaced is not None and replaced["id"] != entry["id"]:
                wconfig.remove_install(replaced["id"])
                wconfig.set_active_install(entry["id"])
                old = wconfig.install_zim_path(replaced)
                if wconfig.volume_mounted(old) and old != final:
                    old.unlink(missing_ok=True)
            self._persist(status="done", bytes_done=final.stat().st_size,
                          error=None)
            wzim.reset_archive()
            await self._fire({"status": "done", "filename": filename})
            log.info("wikisink archive installed: %s", final)
        except Exception as e:  # noqa: BLE001 — surfaced to the UI, not raised into the loop
            log.exception("wikisink download failed")
            self._persist(status="error", error=str(e))
            await self._fire({"status": "error", "error": str(e)})

    async def _download(self, url: str, part: Path) -> None:
        done = part.stat().st_size if part.exists() else 0
        headers = {"Range": f"bytes={done}-"} if done else {}
        mode = "ab" if done else "wb"
        last_emit = 0.0
        last_persist = 0.0
        rate_anchor = (time.monotonic(), done)
        async with httpx.AsyncClient(timeout=httpx.Timeout(60, read=120),
                                     follow_redirects=True) as client:
            async with client.stream("GET", url, headers=headers) as resp:
                if done and resp.status_code == 200:
                    # Server ignored the Range header — start over.
                    done = 0
                    mode = "wb"
                elif done and resp.status_code != 206:
                    resp.raise_for_status()
                resp.raise_for_status()
                length = resp.headers.get("Content-Length")
                total = done + int(length) if length else 0
                if total:
                    self._persist(bytes_total=total)
                with part.open(mode) as fh:
                    async for chunk in resp.aiter_bytes(CHUNK_SIZE):
                        if self._pause or self._cancel:
                            return
                        fh.write(chunk)
                        done += len(chunk)
                        now = time.monotonic()
                        if now - last_emit >= EMIT_INTERVAL:
                            last_emit = now
                            span = now - rate_anchor[0]
                            rate = (done - rate_anchor[1]) / span if span > 0 else 0
                            if span > 30:
                                rate_anchor = (now, done)
                            await self._fire({
                                "status": "downloading",
                                "bytes_done": done,
                                "bytes_total": total,
                                "pct": round(100 * done / total, 1) if total else None,
                                "rate_bps": int(rate),
                                "eta_s": int((total - done) / rate) if rate > 0 and total else None,
                            })
                        if now - last_persist >= PERSIST_INTERVAL:
                            last_persist = now
                            self._persist(bytes_done=done)
        self._persist(bytes_done=done)
