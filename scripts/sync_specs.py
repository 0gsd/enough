#!/usr/bin/env python3
"""Pull the OES specifications and their sync client from a cosmoes-site checkout into enough.

    uv run python scripts/sync_specs.py                    # sync from ../../cosmoes-site
    uv run python scripts/sync_specs.py --check            # report what differs, write nothing
    uv run python scripts/sync_specs.py --cosmoes DIR      # another cosmoes-site checkout

cosmoes.org (github.com/0gsd/cosmoes-site) is the one place the OES specifications are edited: MacroCOSM OES, Thym,
Ascribe and Comprise OES, each at its own home, with `specs/specs.json` as the registry (slug, name, edition,
describes, host, revised). enough bundles a copy of each text as the floor its docs viewer and `/api/*-spec` routes
read when no synced copy is in use, and refreshes the copies at run time with the client the site publishes. This
script only ever READS the checkout and copies, byte for byte:

- `specs/macrocosm-oes.md` -> `docs/MACROCOSM_OES.md`, `specs/thym.md` -> `docs/THYM.md`, `specs/ascribe.md` ->
  `docs/ASCRIBE.md`, `specs/comprise-oes.md` -> `docs/COMPRISE_OES.md` (the four documents the viewer shows; the apex
  text `oes` is not bundled);
- `client/cosmoes_client.py` -> `enough/cosmoes_client.py`, THE CANONICAL COPY vendored unchanged (a fix goes to
  cosmoes-site and is taken again);

and writes `docs/specs.json`: the registry's entry for each of the four plus the bundled path, the source path and
the file's sha256, the client's path, source, sha256 and the commit that last touched it, the checkout's commit (with
`dirty` when a copied source differs from it) and the sync date. `enough/docoes.py` reads it for the bundled editions
(name, edition, revised, home); `tests/test_sync_specs.py` runs this against a fake checkout. Nothing is written when
nothing changed: a rerun over an unchanged checkout is byte-stable (the commit and the date move only with a change).

Exit status: 0 = synced (or, with --check, nothing to do); 1 = --check found differences; 2 = no cosmoes-site checkout.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COSMOES = REPO_ROOT.parent.parent / "cosmoes-site"

REGISTRY = "specs/specs.json"
SPECS_DIR = "specs"
# The documents enough bundles, by slug: where each lands in this repository. The apex text (`oes`) is not bundled.
BUNDLED = {
    "macrocosm-oes": "docs/MACROCOSM_OES.md",
    "thym": "docs/THYM.md",
    "ascribe": "docs/ASCRIBE.md",
    "comprise-oes": "docs/COMPRISE_OES.md",
}
CLIENT_SOURCE = "client/cosmoes_client.py"
CLIENT_DEST = "enough/cosmoes_client.py"
SPECS_JSON = "docs/specs.json"
# The registry keys copied into docs/specs.json as cosmoes-site wrote them.
REGISTRY_KEYS = ("slug", "file", "name", "edition", "describes", "host", "revised", "reference")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(cosmoes: Path, *args: str) -> str | None:
    """One read-only git call in the checkout; None when git or the checkout is not there."""
    try:
        r = subprocess.run(["git", "-C", str(cosmoes), *args], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def registry(cosmoes: Path) -> list[dict]:
    """cosmoes-site's `specs/specs.json`, as a list of entries (its own order)."""
    body = json.loads((Path(cosmoes) / REGISTRY).read_text(encoding="utf-8"))
    if not isinstance(body, list):
        raise ValueError(f"{REGISTRY} is not a list")
    return [e for e in body if isinstance(e, dict)]


def plan(cosmoes: Path) -> dict[str, Path]:
    """Every file the copy holds: {repo-relative destination: source path}, in a stable order. A document the
    registry lists but whose text is missing from the checkout is left out (and reported by `sync`)."""
    cosmoes = Path(cosmoes)
    files: dict[str, Path] = {}
    for entry in registry(cosmoes):
        dest = BUNDLED.get(str(entry.get("slug")))
        src = cosmoes / SPECS_DIR / str(entry.get("file") or "")
        if dest and entry.get("file") and src.is_file():
            files[dest] = src
    client = cosmoes / CLIENT_SOURCE
    if client.is_file():
        files[CLIENT_DEST] = client
    return files


def source_commit(cosmoes: Path) -> tuple[str | None, bool | None]:
    """(the checkout's short commit, whether a copied source differs from it); (None, None) without git."""
    head = _git(cosmoes, "rev-parse", "--short", "HEAD")
    if not head:
        return None, None
    status = _git(cosmoes, "status", "--porcelain", "--", SPECS_DIR, CLIENT_SOURCE)
    return head, bool(status) if status is not None else None


def client_commit(cosmoes: Path) -> str | None:
    """The commit that last touched the client (W3a's recipe: `git log -1 --format=%h -- client/cosmoes_client.py`)."""
    return _git(cosmoes, "log", "-1", "--format=%h", "--", CLIENT_SOURCE) or None


def specs_json(entries: list[dict], hashes: dict[str, str], *, commit: str | None, dirty: bool | None,
               client: str | None, synced: str) -> dict:
    """The body of docs/specs.json for these copies."""
    documents = []
    for entry in entries:
        slug = str(entry.get("slug"))
        dest = BUNDLED.get(slug)
        if not dest or dest not in hashes:
            continue
        doc = {k: entry[k] for k in REGISTRY_KEYS if k in entry}
        doc.update({"path": dest, "source": f"{SPECS_DIR}/{entry.get('file')}", "sha256": hashes[dest]})
        documents.append(doc)
    body: dict = {"source": "cosmoes-site", "commit": commit, "dirty": dirty, "synced": synced}
    if CLIENT_DEST in hashes:
        body["client"] = {"path": CLIENT_DEST, "source": CLIENT_SOURCE, "commit": client, "sha256": hashes[CLIENT_DEST]}
    body["documents"] = documents
    return body


def _stable(body: dict) -> dict:
    """What a rerun compares: everything but the commit, the dirty flag and the date, which move only with a change."""
    return {k: v for k, v in body.items() if k not in ("commit", "dirty", "synced")}


def _dump(body: dict) -> bytes:
    return (json.dumps(body, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def sync(cosmoes: Path, root: Path = REPO_ROOT, *, check: bool = False, today: str | None = None) -> dict:
    """Bring the copies under `root` in line with the cosmoes-site checkout. Returns a report; writes nothing when
    `check`. `today` fixes the sync date (tests)."""
    cosmoes, root = Path(cosmoes), Path(root)
    if not (cosmoes / REGISTRY).is_file():
        raise FileNotFoundError(f"no cosmoes-site checkout at {cosmoes} (expected {REGISTRY} there)")
    entries = registry(cosmoes)
    report: dict = {"added": [], "changed": [], "removed": [], "missing": []}
    for entry in entries:
        slug = str(entry.get("slug"))
        if slug in BUNDLED and not (cosmoes / SPECS_DIR / str(entry.get("file") or "")).is_file():
            report["missing"].append(f"{SPECS_DIR}/{entry.get('file')}")
    for slug in BUNDLED:
        if slug not in {str(e.get("slug")) for e in entries}:
            report["missing"].append(f"{REGISTRY}: no entry for {slug}")
    if not (cosmoes / CLIENT_SOURCE).is_file():
        report["missing"].append(CLIENT_SOURCE)
    hashes: dict[str, str] = {}
    for rel, src in plan(cosmoes).items():
        data = src.read_bytes()
        hashes[rel] = _sha(data)
        target = root / rel
        if target.is_file():
            if _sha(target.read_bytes()) == hashes[rel]:
                continue
            report["changed"].append(rel)
        else:
            report["added"].append(rel)
        if not check:
            _write(target, data)
    commit, dirty = source_commit(cosmoes)
    body = specs_json(entries, hashes, commit=commit, dirty=dirty, client=client_commit(cosmoes),
                      synced=today or _dt.date.today().isoformat())
    spath = root / SPECS_JSON
    have: dict | None = None
    if spath.is_file():
        try:
            have = json.loads(spath.read_text(encoding="utf-8"))
        except ValueError:
            have = None
    if have is None or _stable(have) != _stable(body):
        report["changed" if spath.is_file() else "added"].append(SPECS_JSON)
        if not check:
            _write(spath, _dump(body))
    else:
        body = have
    report.update(files=len(hashes), source_commit=body.get("commit"), dirty=body.get("dirty"),
                  client_commit=(body.get("client") or {}).get("commit"), synced=body.get("synced"),
                  documents=[d["slug"] for d in body.get("documents") or []])
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cosmoes", type=Path, default=DEFAULT_COSMOES,
                    help=f"cosmoes-site checkout (default {DEFAULT_COSMOES})")
    ap.add_argument("--root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    ap.add_argument("--check", action="store_true", help="list what differs; write nothing")
    args = ap.parse_args(argv)
    try:
        r = sync(args.cosmoes, args.root, check=args.check)
    except FileNotFoundError as e:
        print(f"sync_specs: {e}", file=sys.stderr)
        return 2
    for kind in ("added", "changed", "removed"):
        for rel in r[kind]:
            print(f"  {kind:8} {rel}")
    for rel in r["missing"]:
        print(f"  missing  {rel} (not in the checkout)", file=sys.stderr)
    touched = len(r["added"]) + len(r["changed"]) + len(r["removed"])
    print(f"{'check' if args.check else 'sync'}: {len(r['added'])} added, {len(r['changed'])} changed, "
          f"{len(r['removed'])} removed; {r['files']} files from cosmoes-site {r['source_commit'] or 'an unknown commit'}"
          f"{' (dirty)' if r['dirty'] else ''}; client {r['client_commit'] or 'unknown'}; synced {r['synced']}")
    if args.check and touched:
        print(f"check: {touched} file(s) differ from the checkout — run without --check to sync", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
