"""The language library fetched on demand from cosmoes.org and cached (0.8; ruled by the owner 2026-11-19).

An installed enough carries no texts of the library (nothing is added to the DMG). When a citation or the docs viewer
asks for a text that is not aboard here, enough fetches it from the library's published home, the way the spec texts
are kept current (`enough/specs.py`), verifies every file before keeping anything, caches it under the state root and
builds the index from the cache. Offline, or with the fetch turned off, the citation reads `not-aboard`: a warning,
never an error.

What is fetched, all GETs over HTTPS to cosmoes.org only (`ENOUGH_LIBRARY_URL`, default https://cosmoes.org/library;
a loopback http://127.0.0.1… or http://localhost… stand-in for tests and scratch rigs, nothing else):

    <url>/library.json                                  the registry, byte for byte (kept as `library.remote.json`)
    <url>/<shelf>/<text>/<version>/SHA256SUMS           its sha256 must be the registry entry's `digest`
    <url>/<shelf>/<text>/<version>/NOTICE, FETCHED      the licence and notice, the fetch's record
    <url>/<shelf>/<text>/<version>/raw/<path>           every file SHA256SUMS lists (`files/<path>`), each checked

A text is staged in a scratch folder in the cache, checked file by file against SHA256SUMS and then whole by
`library_index.verify(folder, entry)` (sums, digest, file count, no link, no marked gap), and only then moved into
place. A text whose checksums fail is refused and nothing of it is kept. Nothing fetched is run, imported or installed:
the texts are read as text.

The cache (`<ENOUGH_LANGUAGES_ROOT>/shelf/`, default `~/enough/languages/shelf/`) is itself a shelf the index reads:

    library.remote.json                 the site's registry as fetched
    library.json                        ours: the site's registry with `aboard` true only for the texts kept here
    fetched.json                        {key: {at, url, files, bytes}} for each text kept here
    <shelf>/<text>/<version>/...        a fetched text, as the site keeps it

The registry is fetched once per launch at the library's first use (as the spec check runs once per launch), so a
text republished on the site with another digest is dropped from the cache and fetched again on its next citation.

When it runs: only when the spec texts' sync may run, the same switch: off with `ENOUGH_SPECS_SYNC=0` (every test
and scratch rig) or the preference `specs_sync: false` ("keep the specifications current from cosmoes.org"). Like
the spec sync, agent-free mode does not stop it: agent-free means no model, and this is no model. Never on the
request path: a fetch runs in a daemon thread; the asker gets `fetching` and asks again (or waits a little).
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from . import __version__
from . import library_index as li

log = logging.getLogger("enough.library")

DEFAULT_URL = "https://cosmoes.org/library"
DOMAIN = "cosmoes.org"
LOOPBACK = ("127.0.0.1", "localhost")
CACHE_DIR = "shelf"
REMOTE_REGISTRY = "library.remote.json"
FETCHED_RECORD = "fetched.json"
REGISTRY_KEY = "library.json"
USER_AGENT = f"enough/{__version__} (language library)"
TIMEOUT = 10.0
WORKERS = 8
#: After a failed fetch, the same text (or the registry) is not asked for again for this long: the viewer polls.
RETRY_AFTER = 60.0
MAX_FILE = 64 * 1024 * 1024
MAX_TEXT = 1024 * 1024 * 1024
MAX_REGISTRY = 5 * 1024 * 1024
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class FetchRefused(RuntimeError):
    """A fetch that could not be done or whose result was refused (network, HTTP, a digest that does not agree)."""


# ---------------------------------------------------------------------------
# where, and whether
# ---------------------------------------------------------------------------

def library_url() -> str:
    """Where the library is asked: `ENOUGH_LIBRARY_URL`, else https://cosmoes.org/library (no trailing slash)."""
    return ((os.environ.get("ENOUGH_LIBRARY_URL") or "").strip() or DEFAULT_URL).rstrip("/")


def check_url(url: str) -> str:
    """The url when it is https on cosmoes.org (or a .cosmoes.org host, no port) or http on a loopback host; else
    ValueError. Never a query or a fragment."""
    parts = urllib.parse.urlsplit(str(url).strip())
    host = (parts.hostname or "").lower()
    try:
        port = parts.port
    except ValueError:
        port = -1
    if parts.query or parts.fragment or parts.username or parts.password:
        raise ValueError(f"the library's address carries more than a path: {url!r}")
    if parts.scheme == "https" and (host == DOMAIN or host.endswith("." + DOMAIN)) and port is None:
        return str(url).strip().rstrip("/")
    if parts.scheme == "http" and host in LOOPBACK:
        return str(url).strip().rstrip("/")
    raise ValueError(f"the library's address must be https://{DOMAIN}/… or a loopback http://127.0.0.1…; "
                     f"not {url!r}")


def _ui_config() -> dict:
    try:
        from . import agent_free
        return json.loads(agent_free.ui_config_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, ImportError):
        return {}


def allowed(cfg: dict | None = None) -> tuple[bool, str]:
    """Whether a fetch may run, and why not: the spec sync's own switch (`ENOUGH_SPECS_SYNC=0`, the preference
    `specs_sync: false`), and an address that is not cosmoes.org's or a loopback stand-in's."""
    if os.environ.get("ENOUGH_SPECS_SYNC", "1").strip() == "0":
        return False, "ENOUGH_SPECS_SYNC=0"
    if (cfg if cfg is not None else _ui_config()).get("specs_sync") is False:
        return False, "the preference to keep the specifications current from cosmoes.org is off"
    try:
        check_url(library_url())
    except ValueError as e:
        return False, str(e)
    return True, ""


def key_of(entry: dict) -> str:
    return f"{entry['shelf']}/{entry['text']}/{entry['version']}"


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_rel(rel: str) -> bool:
    """A path SHA256SUMS may list: `files/<segments>`, relative, no `..`, no empty or dot segment, no backslash."""
    if not rel.startswith(li.FILES + "/") or "\\" in rel or "\x00" in rel:
        return False
    segs = rel.split("/")[1:]
    return bool(segs) and all(s and s not in (".", "..") for s in segs)


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    """The library's files are served where they are asked for: a redirect is refused."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise FetchRefused(f"{req.full_url}: redirected ({code}), refused")


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".part-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------------------
# the fetcher
# ---------------------------------------------------------------------------

class Fetcher:
    """Fetches the registry and kept texts from `base` into the cache shelf `cache`. One per (cache, base) in a
    process (`shared()`). `opener` is anything with `.open(request, timeout=…)` (urllib's by default); `clock` is
    `time.monotonic`."""

    def __init__(self, cache: Path, base: str, *, timeout: float = TIMEOUT, workers: int = WORKERS,
                 retry_after: float = RETRY_AFTER, opener: Any = None, clock: Callable[[], float] | None = None):
        self.cache = Path(cache)
        self.base = check_url(base)
        self.timeout, self.workers, self.retry_after = float(timeout), int(workers), float(retry_after)
        self.opener = opener if opener is not None else urllib.request.build_opener(_NoRedirects())
        self.clock = clock or time.monotonic
        self._lock = threading.RLock()
        self._done = threading.Condition(self._lock)
        self._write = threading.Lock()
        self._jobs: dict[str, dict] = {}          # key -> {state: fetching|done|failed, why, at, t}
        self._threads: dict[str, threading.Thread] = {}
        self.refreshed = False                    # the registry was fetched this launch

    # ------------------------------------------------------------------ the network
    def url(self, *parts: str) -> str:
        return self.base + "/" + "/".join(urllib.parse.quote(p, safe="/-._~") for p in parts)

    def get(self, url: str, cap: int = MAX_FILE) -> bytes:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
        try:
            with self.opener.open(req, timeout=self.timeout) as resp:
                declared = (resp.headers.get("Content-Length") or "").strip()
                if declared.isdigit() and int(declared) > cap:
                    raise FetchRefused(f"{url}: {declared} bytes, over the cap of {cap}")
                data = resp.read(cap + 1)
                if len(data) > cap:
                    raise FetchRefused(f"{url}: over the cap of {cap} bytes")
                return data
        except FetchRefused:
            raise
        except urllib.error.HTTPError as e:
            raise FetchRefused(f"{url}: HTTP {e.code}") from None
        except urllib.error.URLError as e:
            raise FetchRefused(f"{url}: {e.reason}") from None
        except (OSError, ValueError) as e:                       # timeouts, resets, incomplete reads
            raise FetchRefused(f"{url}: {type(e).__name__}: {e}") from None

    # ------------------------------------------------------------------ the cache
    def remote_registry(self) -> dict | None:
        try:
            return json.loads((self.cache / REMOTE_REGISTRY).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def remote_entry(self, shelf: str, text: str, version: str) -> dict | None:
        for e in (self.remote_registry() or {}).get("texts") or []:
            if (e.get("shelf"), e.get("text"), e.get("version")) == (shelf, text, version):
                return e
        return None

    def record(self) -> dict:
        try:
            return json.loads((self.cache / FETCHED_RECORD).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _here(self, entry: dict) -> bool:
        return key_of(entry) in self.record() and li.text_dir(self.cache, entry).is_dir()

    def _write_registry(self, remote: dict, record: dict) -> None:
        """Ours: the site's registry with `aboard` true only for the texts in `record` whose digest agrees."""
        texts = []
        for e in remote.get("texts") or []:
            e = dict(e)
            if e.get("aboard") and not (key_of(e) in record and record[key_of(e)].get("digest") == e.get("digest")):
                e["aboard"] = False
            texts.append(e)
        ours = dict(remote, texts=texts)
        _write_atomic(self.cache / li.REGISTRY, (json.dumps(ours, indent=2, ensure_ascii=False) + "\n").encode())
        _write_atomic(self.cache / FETCHED_RECORD, (json.dumps(record, indent=2, sort_keys=True) + "\n").encode())

    # ------------------------------------------------------------------ fetching, done here and now
    def fetch_registry(self) -> dict:
        """library.json from the site, validated, kept as `library.remote.json`; texts the site no longer keeps
        with the digest they were fetched with are dropped from the cache. Returns the registry."""
        url = self.url(li.REGISTRY)
        data = self.get(url, MAX_REGISTRY)
        try:
            reg = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as e:
            raise FetchRefused(f"{url}: not JSON ({e})") from None
        problems = li.validate_registry(reg) if isinstance(reg, dict) else ["not an object"]
        if problems:
            raise FetchRefused(f"{url}: the registry does not validate: {'; '.join(problems)}")
        with self._write:
            self.cache.mkdir(parents=True, exist_ok=True)
            _write_atomic(self.cache / REMOTE_REGISTRY, data)
            record = self.record()
            current = {key_of(e): e for e in reg.get("texts") or [] if e.get("aboard")}
            stale = [k for k, r in record.items() if k not in current or current[k].get("digest") != r.get("digest")]
            for k in stale:
                record.pop(k)
            self._write_registry(reg, record)        # first say they are not aboard, then remove them
            for k in stale:
                shelf, text, version = k.split("/", 2)
                shutil.rmtree(self.cache / shelf / text / version, ignore_errors=True)
                for empty in (self.cache / shelf / text, self.cache / shelf):
                    try:
                        empty.rmdir()
                    except OSError:
                        break
                log.info("library: %s changed on the site; dropped from the cache", k)
        with self._lock:
            self.refreshed = True
        return reg

    def fetch_text(self, entry: dict) -> dict:
        """One kept text, whole, verified, into the cache. FetchRefused, with nothing kept, for anything that does not
        agree. Returns its record `{at, url, files, bytes, digest}`."""
        key = key_of(entry)
        if not entry.get("aboard") or not entry.get("digest"):
            raise FetchRefused(f"{key} is not kept on the site's shelf")
        sums_url = self.url(entry["shelf"], entry["text"], entry["version"], "SHA256SUMS")
        sums = self.get(sums_url)
        if "sha256:" + _sha(sums) != entry["digest"]:
            raise FetchRefused(f"{key}: SHA256SUMS is not the one the registry names (its digest differs)")
        listed: dict[str, str] = {}
        for line in sums.decode("utf-8", "replace").splitlines():
            if not line.strip():
                continue
            digest, sep, rel = line.partition("  ")
            if not sep or not _HEX64.match(digest) or not _safe_rel(rel) or rel in listed:
                raise FetchRefused(f"{key}: SHA256SUMS holds a line that is not `<sha256>  files/<path>`: {line!r}")
            listed[rel] = digest
        if entry.get("files") != len(listed):
            raise FetchRefused(f"{key}: the registry says {entry.get('files')} files, SHA256SUMS lists {len(listed)}")
        self.cache.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=f".fetch-{entry['shelf']}-{entry['text']}-", dir=self.cache))
        try:
            total = 0
            for name in ("NOTICE", "FETCHED"):
                body = self.get(self.url(entry["shelf"], entry["text"], entry["version"], name))
                (stage / name).write_bytes(body)
            (stage / "SHA256SUMS").write_bytes(sums)

            def one(item: tuple[str, str]) -> int:
                rel, digest = item
                body = self.get(self.url(entry["shelf"], entry["text"], entry["version"], "raw",
                                         rel[len(li.FILES) + 1:]))
                if _sha(body) != digest:
                    raise FetchRefused(f"{key}: {rel} does not match its sha256 in SHA256SUMS; the text is refused")
                p = stage / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(body)
                return len(body)

            with ThreadPoolExecutor(max_workers=max(1, self.workers)) as pool:
                for n in pool.map(one, sorted(listed.items())):
                    total += n
                    if total > MAX_TEXT:
                        raise FetchRefused(f"{key}: over the cap of {MAX_TEXT} bytes")
            problems = li.verify(stage, entry)
            if problems:
                raise FetchRefused(f"{key} does not verify: {'; '.join(problems)}")
            rec = {"at": _now(), "url": self.url(entry["shelf"], entry["text"], entry["version"]) + "/",
                   "files": len(listed), "bytes": total, "digest": entry["digest"]}
            with self._write:
                dest = li.text_dir(self.cache, entry)
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    aside = Path(tempfile.mkdtemp(prefix=".old-", dir=self.cache))
                    os.replace(dest, aside / "v")
                    shutil.rmtree(aside, ignore_errors=True)
                os.replace(stage, dest)
                record = self.record()
                record[key] = rec
                remote = self.remote_registry() or {"format": li.FORMAT, "shelves": [], "texts": [entry]}
                self._write_registry(remote, record)
            log.info("library: %s fetched from %s (%d files, %d bytes)", key, self.base, len(listed), total)
            return rec
        finally:
            shutil.rmtree(stage, ignore_errors=True)

    # ------------------------------------------------------------------ on demand, in the background
    def _job(self, key: str) -> dict | None:
        with self._lock:
            return self._jobs.get(key)

    def _start(self, key: str, work: Callable[[], Any], then: Callable[[], Any] | None = None) -> tuple[str, str]:
        """('fetching', why) when `key` is (now) being fetched; ('not-aboard', why) when it failed a moment ago."""
        with self._lock:
            job = self._jobs.get(key)
            if job and job["state"] == "fetching":
                return "fetching", job["why"]
            if job and job["state"] == "failed" and self.clock() - job["t"] < self.retry_after:
                return "not-aboard", job["why"]
            what = "the library's registry" if key == REGISTRY_KEY else key
            why = f"fetching {what} from {self.base}; ask again in a moment"
            self._jobs[key] = {"state": "fetching", "why": why, "at": _now(), "t": self.clock()}

            def run() -> None:
                try:
                    work()
                    state, msg = "done", ""
                except Exception as e:                            # noqa: BLE001 - a fault is a line in the status
                    state = "failed"
                    msg = (f"{what} could not be fetched from {self.base}: {e}" if not isinstance(e, FetchRefused)
                           else f"{what} could not be fetched: {e}")
                    log.warning("library: %s", msg)
                if state == "done" and then is not None:          # before this job ends, so a waiter sees the next
                    try:
                        then()
                    except Exception:                             # noqa: BLE001
                        log.exception("library: after %s", key)
                with self._lock:
                    self._jobs[key] = {"state": state, "why": msg, "at": _now(), "t": self.clock()}
                    self._threads.pop(key, None)
                    self._done.notify_all()

            t = threading.Thread(target=run, name=f"enough-library-fetch {key}", daemon=True)
            self._threads[key] = t
        t.start()
        return "fetching", why

    def refresh_once(self) -> None:
        """At the library's first use in a launch: fetch the registry again in the background (texts the site now
        keeps with another digest are dropped, and fetched again when next cited)."""
        with self._lock:
            if self.refreshed or REGISTRY_KEY in self._jobs:
                return
        self._start(REGISTRY_KEY, self.fetch_registry)

    def demand(self, shelf: str, text: str, version: str,
               then: Callable[[], Any] | None = None) -> tuple[str, str] | None:
        """A kept text asked for that is not here: start its fetch. ('fetching', why), ('not-aboard', why) when a
        fetch failed a moment ago (offline, refused), or None when the site's shelf does not keep it either (after
        the registry was fetched this launch)."""
        remote = self.remote_entry(shelf, text, version)
        if remote is not None and remote.get("aboard"):
            if self._here(remote):
                return None
            return self._start(key_of(remote), lambda: self.fetch_text(remote), then=then)
        with self._lock:
            refreshed = self.refreshed
        if refreshed:
            return None
        return self._start(REGISTRY_KEY, self.fetch_registry, then=then)

    def demand_registry(self, then: Callable[[], Any] | None = None) -> tuple[str, str] | None:
        """No registry here, or a name the registry here does not know: fetch it, once a launch."""
        with self._lock:
            if self.refreshed:
                return None
        return self._start(REGISTRY_KEY, self.fetch_registry, then=then)

    def busy(self) -> bool:
        with self._lock:
            return any(j["state"] == "fetching" for j in self._jobs.values())

    def wait(self, timeout: float | None = None) -> bool:
        """Wait until no fetch runs (or `timeout` seconds). True when none runs."""
        deadline = None if timeout is None else self.clock() + timeout
        with self._lock:
            while self.busy():
                left = None if deadline is None else deadline - self.clock()
                if left is not None and left <= 0:
                    return False
                self._done.wait(left if left is not None else 1.0)
        return True

    def status(self) -> dict:
        rec = self.record()
        with self._lock:
            jobs = {k: {x: v for x, v in j.items() if x != "t"} for k, j in self._jobs.items()}
            refreshed = self.refreshed
        return {"url": self.base, "cache": str(self.cache), "registry": (self.cache / REMOTE_REGISTRY).is_file(),
                "refreshed": refreshed, "cached": [dict(key=k, **v) for k, v in sorted(rec.items())], "jobs": jobs}


# ---------------------------------------------------------------------------
# one per process
# ---------------------------------------------------------------------------

_SHARED: dict[tuple[str, str], Fetcher] = {}
_SHARED_GUARD = threading.Lock()


def shared(cache: Path) -> Fetcher | None:
    """The process's fetcher for `cache` and the library's address, or None when a fetch may not run."""
    ok, _why = allowed()
    if not ok:
        return None
    base = check_url(library_url())
    key = (str(cache), base)
    with _SHARED_GUARD:
        f = _SHARED.get(key)
        if f is None:
            f = _SHARED[key] = Fetcher(cache, base)
    return f


def reset_for_tests() -> None:
    with _SHARED_GUARD:
        _SHARED.clear()


def status(cache: Path) -> dict:
    """The fetch at a glance, for `GET /api/library/status`: whether it may run (and why not), where it asks, and
    what is cached."""
    ok, why = allowed()
    f = shared(cache) if ok else None
    if f is not None:
        return {"allowed": True, "reason": None, **f.status()}
    try:
        rec = json.loads((Path(cache) / FETCHED_RECORD).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        rec = {}
    return {"allowed": False, "reason": why, "url": library_url(), "cache": str(cache),
            "registry": (Path(cache) / REMOTE_REGISTRY).is_file(), "refreshed": False,
            "cached": [dict(key=k, **v) for k, v in sorted(rec.items())], "jobs": {}}
