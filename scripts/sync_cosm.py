#!/usr/bin/env python3
"""Copy Comprise's MiniCOSM manifest and its public sample Holotypes into enough.

    uv run python scripts/sync_cosm.py                  # sync from ../../comprise-dev
    uv run python scripts/sync_cosm.py --check          # report what would change, write nothing
    uv run python scripts/sync_cosm.py --comprise DIR   # another comprise checkout

Comprise (comprise-dev) is the reference implementation of the first MiniCOSM. enough reads its volumes through
`enough/macrocosm.py`, driven by Comprise's own manifest, and tests that reader against Comprise's public samples.
This script only ever READS the Comprise checkout. It copies, byte for byte:

- `oes/comprise-oes.manifest.cosm` -> `defaults/cosm/manifests/comprise.manifest.cosm` (never edited in enough);
- for each sample Holotype on the allowlist below, only the model: `holotype.cosm` and `atoms/**/*.cosm`, plus any
  `atoms/**/README*` -> `tests/fixtures/cosm/holotypes/<name>/`. Nothing else in a Holotype folder is copied: no
  local database, no people files, no scans, feeds, bindings, reports, snapshots, vendors or logos;
- the COSM 0.2 example tree (`core/vendor/comprise-oes/examples/meadow/`: `firm.cosm`, `nodes.cosm`, `doc.cosm`,
  `meadow.sketch`, `README.md`) -> `tests/fixtures/cosm/cosm02/meadow/`.

The Holotypes are named by an allowlist, never found by listing Comprise's fixtures: a fixture that is not public
must never reach this repository, so nothing here can copy one by accident. Only changed files are rewritten;
files under the synced folders with no source are removed. `tests/fixtures/cosm/manifest.json` records the source
commit and every copied file's sha256 with a digest over them (no timestamps), so a rerun over an unchanged
checkout is byte-stable. `tests/fixtures/cosm/NOTICE.md` is hand-written and never touched here.

Exit status: 0 = synced (or, with --check, nothing to do); 1 = --check found changes; 2 = no Comprise checkout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COMPRISE = REPO_ROOT.parent.parent / "comprise-dev"

MANIFEST_SOURCE = "oes/comprise-oes.manifest.cosm"
MANIFEST_DEST = "defaults/cosm/manifests/comprise.manifest.cosm"
FIXTURES = "tests/fixtures/cosm"
# The public sample Holotypes, by name. An allowlist: add a name here only for a sample Comprise publishes.
HOLOTYPES = ("meadow", "mozilla", "wikimedia", "khan-academy")
HOLOTYPES_DEST = f"{FIXTURES}/holotypes"
EXAMPLE_SOURCE = "core/vendor/comprise-oes/examples/meadow"
EXAMPLE_FILES = ("firm.cosm", "nodes.cosm", "doc.cosm", "meadow.sketch", "README.md")
EXAMPLE_DEST = f"{FIXTURES}/cosm02/meadow"
# Folders this script owns outright: anything in them with no source is removed.
OWNED = (HOLOTYPES_DEST, f"{FIXTURES}/cosm02")
MANIFEST_JSON = f"{FIXTURES}/manifest.json"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _holotype_files(src: Path) -> list[Path]:
    """The model files of one Holotype folder: the catalog, then every module file and README under atoms/."""
    out = []
    if (src / "holotype.cosm").is_file():
        out.append(src / "holotype.cosm")
    atoms = src / "atoms"
    if atoms.is_dir():
        for p in sorted(atoms.rglob("*"), key=lambda p: p.relative_to(src).as_posix()):
            if not p.is_file() or p.name.startswith(".") or p.name.lower().startswith("people"):
                continue
            if p.suffix == ".cosm" or p.name.upper().startswith("README"):
                out.append(p)
    return out


def plan(comprise: Path) -> dict[str, Path]:
    """Every file the copy holds: {repo-relative destination: source path}, sorted by destination."""
    comprise = Path(comprise)
    files: dict[str, Path] = {MANIFEST_DEST: comprise / MANIFEST_SOURCE}
    for name in HOLOTYPES:
        src = comprise / "fixtures" / name
        for p in _holotype_files(src):
            files[f"{HOLOTYPES_DEST}/{name}/{p.relative_to(src).as_posix()}"] = p
    for fname in EXAMPLE_FILES:
        p = comprise / EXAMPLE_SOURCE / fname
        if p.is_file():
            files[f"{EXAMPLE_DEST}/{fname}"] = p
    return dict(sorted(files.items()))


def source_commit(comprise: Path) -> str | None:
    """The checkout's short commit, with `-dirty` when any copied source differs from it. Read-only git calls."""
    try:
        head = subprocess.run(["git", "-C", str(comprise), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=10)
        if head.returncode != 0:
            return None
        paths = [MANIFEST_SOURCE, EXAMPLE_SOURCE] + [f"fixtures/{n}/holotype.cosm" for n in HOLOTYPES] \
            + [f"fixtures/{n}/atoms" for n in HOLOTYPES]
        status = subprocess.run(["git", "-C", str(comprise), "status", "--porcelain", "--", *paths],
                                capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    commit = head.stdout.strip() or None
    if commit and status.returncode == 0 and status.stdout.strip():
        commit += "-dirty"
    return commit


def manifest_for(hashes: dict[str, str], commit: str | None) -> bytes:
    hashes = dict(sorted(hashes.items()))
    digest = _sha("".join(f"{rel} {h}\n" for rel, h in hashes.items()).encode("utf-8"))
    body = {"source_commit": commit, "files": hashes, "digest": digest}
    return (json.dumps(body, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _existing(root: Path) -> list[str]:
    """Files already in the folders this script owns, repo-relative."""
    out = []
    for owned in OWNED:
        d = root / owned
        if d.is_dir():
            out += [p.relative_to(root).as_posix() for p in d.rglob("*") if p.is_file()]
    return sorted(out)


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _prune(root: Path) -> None:
    """Remove folders left empty under the owned folders (deepest first)."""
    for owned in OWNED:
        d = root / owned
        if not d.is_dir():
            continue
        for p in sorted((p for p in d.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            if not any(p.iterdir()):
                p.rmdir()


def sync(comprise: Path, root: Path = REPO_ROOT, *, check: bool = False) -> dict:
    """Bring the copies under `root` in line with the Comprise checkout. Returns a report; writes nothing when
    `check`."""
    comprise, root = Path(comprise), Path(root)
    if not (comprise / MANIFEST_SOURCE).is_file():
        raise FileNotFoundError(f"no Comprise checkout at {comprise} (expected {MANIFEST_SOURCE} there)")
    report = {"added": [], "changed": [], "removed": []}
    hashes: dict[str, str] = {}
    for rel, src in plan(comprise).items():
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
    for rel in _existing(root):
        if rel not in hashes:
            report["removed"].append(rel)
            if not check:
                (root / rel).unlink()
    if not check:
        _prune(root)
    manifest = manifest_for(hashes, source_commit(comprise))
    mpath = root / MANIFEST_JSON
    if not mpath.is_file() or mpath.read_bytes() != manifest:
        report["changed" if mpath.is_file() else "added"].append(MANIFEST_JSON)
        if not check:
            _write(mpath, manifest)
    body = json.loads(manifest)
    report.update(files=len(hashes), digest=body["digest"], source_commit=body["source_commit"])
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--comprise", type=Path, default=DEFAULT_COMPRISE,
                    help=f"comprise checkout (default {DEFAULT_COMPRISE})")
    ap.add_argument("--root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    ap.add_argument("--check", action="store_true", help="list what would change; write nothing")
    args = ap.parse_args(argv)
    try:
        r = sync(args.comprise, args.root, check=args.check)
    except FileNotFoundError as e:
        print(f"sync_cosm: {e}", file=sys.stderr)
        return 2
    for kind in ("added", "changed", "removed"):
        for rel in r[kind]:
            print(f"  {kind:8} {rel}")
    touched = len(r["added"]) + len(r["changed"]) + len(r["removed"])
    print(f"{'check' if args.check else 'sync'}: {len(r['added'])} added, {len(r['changed'])} changed, "
          f"{len(r['removed'])} removed; {r['files']} files from {r['source_commit'] or 'an unknown commit'}; "
          f"digest {r['digest'][:12]}")
    if args.check and touched:
        print(f"check: {touched} file(s) would change — run without --check to sync", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
