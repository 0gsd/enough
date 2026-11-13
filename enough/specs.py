"""The specifications kept current from cosmoes.org (0.5.4): the launch check, its report, and the seams.

The four OES specifications enough shows in its docs viewer — MacroCOSM OES, Thym, Ascribe and Comprise OES — are the
canonical editions published at cosmoes.org. enough bundles a copy of each (`docs/*.md`, refreshed at release time by
`scripts/sync_specs.py`, their editions in `docs/specs.json`) as the floor, and at server start asks cosmoes.org once
for the specifications' manifest and fetches only a text that changed, into `docoes.specs_root()` (`~/enough/specs/`).
`docoes.spec_source()` then reads the synced copy in place of the bundled one, and the docs viewer's volume rebuilds on
the next open because its digest follows the file read. Nothing of the user's is sent: one GET of the manifest (with
an ETag), then one GET per changed source, to cosmoes.org only, over HTTPS.

The client is cosmoes-site's `client/cosmoes_client.py`, vendored unchanged as `enough/cosmoes_client.py` (the commit it
was taken from is in docs/specs.json). It never raises for a network or content fault: everything lands in its Report,
kept here for `GET /api/specs-status`.

Rules: never on the request path, never blocking startup (one daemon thread), one request per launch, 3 s timeout per
request, logged at INFO when something updated. Off when the preference `specs_sync` is false (POST /api/ui-config) or
`ENOUGH_SPECS_SYNC=0` (tests and scratch rigs: no test may reach the network); `ENOUGH_COSMOES_BASE` points the client
at a loopback stand-in (the client allows http://127.0.0.1… and http://localhost… bases, nothing else off cosmoes.org).
"""
from __future__ import annotations

import datetime as _dt
import logging
import os
import threading
from pathlib import Path
from typing import Any

from . import __version__
from . import cosmoes_client as _cc
from . import docoes as _docoes

log = logging.getLogger("enough.specs")

#: The documents enough syncs: every registered specification, in the registry's order.
SLUGS: tuple[str, ...] = tuple(slug for slug, d in _docoes.DOCUMENTS.items() if d.spec)
#: The global preference (ui.json, top-level, a bool; absent means on): "keep the specifications current from cosmoes.org".
PREF_KEY = "specs_sync"
DEFAULT_BASE = "https://cosmoes.org"
#: What cosmoes.org sees: the client's protocol version and the app behind it.
USER_AGENT = f"cosmoes-client/{_cc.VERSION} (enough {__version__})"
TIMEOUT = 3.0

_LOCK = threading.Lock()
_THREAD: threading.Thread | None = None
_STATUS: dict[str, Any] = {
    "ran": False,           # whether a check was started this launch
    "running": False,
    "reason": None,         # why it did not run: "ENOUGH_SPECS_SYNC=0" | "preference off"
    "checked": False,       # the manifest was obtained (fetched, or confirmed by a 304)
    "updated": [],          # [slug, kind] written this launch
    "unchanged": [],
    "skipped": [],
    "errors": [],           # [slug, kind, message]
    "elapsed": None,
    "at": None,             # when the check finished, UTC
    "base": None,
}


def cosmoes_base() -> str:
    """Where the client asks: `ENOUGH_COSMOES_BASE`, else https://cosmoes.org."""
    return (os.environ.get("ENOUGH_COSMOES_BASE") or "").strip() or DEFAULT_BASE


def sync_allowed() -> bool:
    """`ENOUGH_SPECS_SYNC=0` turns the launch check off whatever the preference says (tests, scratch rigs)."""
    return os.environ.get("ENOUGH_SPECS_SYNC", "1").strip() != "0"


def preference_on(cfg: dict[str, Any] | None) -> bool:
    """The preference as saved in ui.json: on unless it is exactly false."""
    return (cfg or {}).get(PREF_KEY) is not False


def _set(**fields: Any) -> None:
    with _LOCK:
        _STATUS.update(fields)


def _run(root: Path, base: str, timeout: float) -> None:
    started = _dt.datetime.now(_dt.timezone.utc)
    try:
        client = _cc.CosmoesClient(base=base, timeout=timeout, user_agent=USER_AGENT)
        report = client.sync(root, {slug: ["source"] for slug in SLUGS}, validate=_docoes.validate_spec_source)
    except Exception as e:  # noqa: BLE001 — a bad base or an unexpected fault is a line in the status, never a crash
        log.warning("specs: the launch check could not run: %s: %s", type(e).__name__, e)
        _set(running=False, errors=[["*", "client", f"{type(e).__name__}: {e}"]],
             at=started.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"))
        return
    _set(running=False, checked=report.checked,
         updated=[list(p) for p in report.updated], unchanged=[list(p) for p in report.unchanged],
         skipped=[list(p) for p in report.skipped], errors=[list(e) for e in report.errors],
         elapsed=round(report.elapsed, 3),
         at=_dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"))
    # The client logs under "cosmoes" (INFO per update, WARNING per error); this is the one line per launch.
    if report.updated:
        log.info("specs: %d document(s) updated from %s into %s: %s", len(report.updated), base, root,
                 ", ".join(slug for slug, _kind in report.updated))
    elif report.checked:
        log.debug("specs: checked %s; nothing changed (%d current, %d errors)", base, len(report.unchanged),
                  len(report.errors))
    else:
        log.debug("specs: %s not reached (%s)", base, "; ".join(e[2] for e in report.errors) or "no manifest")


def launch_check(cfg: dict[str, Any] | None = None, *, root: Path | None = None, base: str | None = None,
                 timeout: float = TIMEOUT) -> threading.Thread | None:
    """At server start: one background sync of the four specifications' sources into the specs root, when the
    preference is on and `ENOUGH_SPECS_SYNC` is not 0. Returns the daemon thread, or None when the check does not
    run (the reason is in `status()`). Never blocks the caller; a second call in one process is a no-op."""
    global _THREAD
    with _LOCK:
        if _THREAD is not None:
            return _THREAD
    if not sync_allowed():
        _set(ran=False, reason="ENOUGH_SPECS_SYNC=0")
        return None
    if not preference_on(cfg):
        _set(ran=False, reason="preference off")
        return None
    base = base or cosmoes_base()
    root = Path(root or _docoes.specs_root())
    _set(ran=True, running=True, reason=None, base=base)
    t = threading.Thread(target=_run, args=(root, base, timeout), name="enough-specs-sync", daemon=True)
    with _LOCK:
        _THREAD = t
    t.start()
    return t


def reset_for_tests() -> None:
    """Forget this process's check so a test may run another (the server runs one per launch)."""
    global _THREAD
    with _LOCK:
        _THREAD = None
        _STATUS.update(ran=False, running=False, reason=None, checked=False, updated=[], unchanged=[], skipped=[],
                       errors=[], elapsed=None, at=None, base=None)


def documents(root: Path | None = None) -> dict[str, dict[str, Any]]:
    """Each specification's edition and where enough reads it from: `{slug: {name, edition, revised, source, path,
    home, set_aside}}` with `source` "cosmoes" (the synced copy is shown) or "bundled", and `set_aside` the edition
    of an older synced copy the bundled text was preferred to (0.7: the newer copy wins), else None."""
    out: dict[str, dict[str, Any]] = {}
    for slug in SLUGS:
        info = _docoes.spec_info(slug)
        d = _docoes.DOCUMENTS[slug]
        out[slug] = {"name": d.name, "edition": info["version"], "revised": info["revised"], "source": info["source"],
                     "path": str(info["path"]), "home": info["home"], "set_aside": info["set_aside"]}
    return out


def status(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """`GET /api/specs-status`: the launch check's report (checked, updated, errors, …), whether it is on, where it
    asks and keeps the copies, and every document's edition and source — for the docs viewer's badge and for QA."""
    with _LOCK:
        body = dict(_STATUS)
    body.update({"enabled": preference_on(cfg), "allowed": sync_allowed(), "base": body.get("base") or cosmoes_base(),
                 "root": str(_docoes.specs_root()), "user_agent": USER_AGENT, "documents": documents()})
    return body
