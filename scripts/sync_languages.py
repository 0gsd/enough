#!/usr/bin/env python3
"""Copy the language library's shelf from a cosmoes-site checkout into enough's `reflib/languages/`.

    uv run python scripts/sync_languages.py                    # sync from ../../cosmoes-site
    uv run python scripts/sync_languages.py --check            # report what differs, write nothing
    uv run python scripts/sync_languages.py --from DIR         # another checkout, or a shelf folder itself
    uv run python scripts/sync_languages.py --index FILE       # also build the index into FILE

cosmoes.org keeps the library (`library/` in cosmoes-site, pin 7 of the 0.8 build): `library.json`, the registry,
and for each kept text (`aboard: true`) a version folder `<shelf>/<text>/<version>/` holding `files/` (the
publisher's files as they came), `NOTICE`, `FETCHED` and `SHA256SUMS`. Only the owner's fetch script writes it; this
script only ever READS it and copies, byte for byte:

- `library/library.json` -> `reflib/languages/library.json` (the index's source digest reads it);
- each kept text's version folder, whole (`files/`, `NOTICE`, `FETCHED`, `SHA256SUMS`; nothing else in it), after
  `library_index.verify(folder, entry)` passes on the source AND on the copy; a version folder no longer kept is
  removed. The registry's `README.md`, `NOTICE.md` and the fetch script's `.fetch-*` folders are not copied;
- `client/library_index.py` -> `enough/library_index.py`, THE CANONICAL COPY vendored unchanged (a fix goes to
  cosmoes-site and is taken again). From a bare shelf folder (`--from` naming a folder that holds `library.json`)
  nothing is vendored.

It refuses the whole sync, writing nothing, when the registry has a problem or any kept text's folder does not
verify (a file whose sha256 does not match SHA256SUMS, a file missing or not listed, a link, a marked gap in NOTICE,
the registry's digest or file count): the copy is all or nothing, as the index is. A rerun over an unchanged shelf
writes nothing. `reflib/languages/synced.json` records what was copied (the checkout's commit, `dirty`, the date, the
registry's sha256, the kept texts, the shelf's source digest).

The index is not part of the copy: enough builds it at run time from these files alone (`enough/language_library.py`,
under `ENOUGH_LANGUAGES_ROOT`, `~/enough/languages/library.sqlite`). The sync builds it once into a scratch file to
prove the copy indexes (or into `--index FILE`). Everything under `reflib/languages/` but its README is gitignored.

Exit status: 0 = synced (or, with --check, nothing to do); 1 = refused, or --check found differences; 2 = no shelf.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]


def find_cosmoes(start: Path = REPO_ROOT) -> Path:
    """The sibling cosmoes-site checkout, as sync_specs finds it (two folders above the repository); from a worktree
    (`<repo>/.claude/worktrees/<name>`) the first ancestor that holds a `cosmoes-site` folder is used instead."""
    first = start.parent.parent / "cosmoes-site"
    if first.is_dir():
        return first
    for up in start.parents:
        if (up / "cosmoes-site").is_dir():
            return up / "cosmoes-site"
    return first


DEFAULT_COSMOES = find_cosmoes()

SHELF = "library"                                   # in the checkout
REGISTRY = "library.json"
DEST = "reflib/languages"
INDEX_SOURCE = "client/library_index.py"
INDEX_DEST = "enough/library_index.py"
SYNCED = "synced.json"
OWN = frozenset({"README.md", SYNCED, REGISTRY})    # in DEST: never a version folder, never removed by the copy
META_FILES = ("NOTICE", "FETCHED", "SHA256SUMS")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(cosmoes: Path, *args: str) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(cosmoes), *args], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def locate(source: Path) -> tuple[Path, Path | None]:
    """(the shelf folder, the checkout or None): a cosmoes-site checkout holds `library/library.json`; a shelf
    folder holds `library.json` itself."""
    source = Path(source)
    if (source / SHELF / REGISTRY).is_file():
        return source / SHELF, source
    if (source / REGISTRY).is_file():
        return source, None
    raise FileNotFoundError(f"no language library at {source} (expected {SHELF}/{REGISTRY} or {REGISTRY} there)")


def index_module(checkout: Path | None) -> ModuleType:
    """The index builder to verify with: the checkout's own when there is one (the copy about to be vendored), else
    enough's vendored copy."""
    path = (checkout / INDEX_SOURCE) if checkout is not None and (checkout / INDEX_SOURCE).is_file() \
        else REPO_ROOT / INDEX_DEST
    spec = importlib.util.spec_from_file_location("_sync_library_index", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod                      # dataclasses look their module up while the class is made
    spec.loader.exec_module(mod)
    return mod


def _key(e: dict) -> str:
    return f"{e['shelf']}/{e['text']}/{e['version']}"


def _kept_here(dest: Path) -> set[str]:
    """The version folders in the copy, as keys (any folder three deep that holds a SHA256SUMS)."""
    return {p.parent.relative_to(dest).as_posix() for p in dest.glob("*/*/*/SHA256SUMS")}


def _copy_folder(li: ModuleType, src: Path, dest: Path, entry: dict) -> list[str]:
    """Copy one version folder (files/ and the three files) to `dest` through a staging folder beside it, verify the
    copy, and swap it in. Returns the copy's problems ([] when it went in)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{dest.name}.sync-", dir=dest.parent))
    try:
        shutil.copytree(src / li.FILES, stage / li.FILES, symlinks=True)
        for name in META_FILES:
            shutil.copy2(src / name, stage / name)
        problems = li.verify(stage, entry)
        if problems:
            return problems
        old = None
        if dest.exists():
            old = dest.with_name(f".{dest.name}.old-{os.getpid()}")
            os.replace(dest, old)
        os.replace(stage, dest)
        if old is not None:
            shutil.rmtree(old, ignore_errors=True)
        return []
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)


def _prune(path: Path, stop: Path) -> None:
    """Remove empty folders from `path` up to (not including) `stop`."""
    p = path
    while p != stop and p.is_dir() and not any(p.iterdir()):
        p.rmdir()
        p = p.parent


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def sync(source: Path, root: Path = REPO_ROOT, *, check: bool = False, today: str | None = None,
         index: Path | None = None, prove: bool = True) -> dict:
    """Bring `root`'s `reflib/languages/` (and the vendored index builder) in line with the shelf at `source`.
    Returns a report; writes nothing when `check`, or when anything is refused (`refused` lists why)."""
    shelf, checkout = locate(source)
    root = Path(root)
    dest = root / DEST
    li = index_module(checkout)
    report: dict = {"added": [], "changed": [], "removed": [], "unchanged": [], "refused": {}, "vendored": None,
                    "index": None, "shelf": str(shelf)}
    reg_bytes = (shelf / REGISTRY).read_bytes()
    try:
        reg = json.loads(reg_bytes.decode("utf-8"))
    except ValueError as e:
        report["refused"][REGISTRY] = [f"not JSON: {e}"]
        return report
    problems = li.validate_registry(reg)
    if problems:
        report["refused"][REGISTRY] = problems
    kept = [e for e in reg.get("texts") or [] if e.get("aboard")]
    for e in kept:
        probs = li.verify(li.text_dir(shelf, e), e)
        if probs:
            report["refused"][_key(e)] = probs
    if report["refused"]:
        return report

    # what changes
    plan: list[tuple[str, dict]] = []
    for e in kept:
        k, here = _key(e), li.text_dir(dest, e)
        same = (here / "SHA256SUMS").is_file() and \
            (here / "SHA256SUMS").read_bytes() == (li.text_dir(shelf, e) / "SHA256SUMS").read_bytes() and \
            all((here / n).is_file() and (here / n).read_bytes() == (li.text_dir(shelf, e) / n).read_bytes()
                for n in META_FILES) and not li.verify(here, e)
        if same:
            report["unchanged"].append(k)
        else:
            report["changed" if here.exists() else "added"].append(k)
            plan.append((k, e))
    gone = sorted(_kept_here(dest) - {_key(e) for e in kept}) if dest.is_dir() else []
    report["removed"] += gone
    reg_dest = dest / REGISTRY
    reg_changed = not reg_dest.is_file() or reg_dest.read_bytes() != reg_bytes
    if reg_changed:
        report["changed" if reg_dest.is_file() else "added"].append(f"{DEST}/{REGISTRY}")
    vend_src = (checkout / INDEX_SOURCE) if checkout is not None else None
    if vend_src is not None and vend_src.is_file():
        data = vend_src.read_bytes()
        have = root / INDEX_DEST
        report["vendored"] = {"path": INDEX_DEST, "source": INDEX_SOURCE, "sha256": _sha(data),
                              "commit": _git(checkout, "log", "-1", "--format=%h", "--", INDEX_SOURCE),
                              "changed": not have.is_file() or have.read_bytes() != data}
        if report["vendored"]["changed"]:
            report["changed" if have.is_file() else "added"].append(INDEX_DEST)
    if check:
        return report

    # the copy
    for k, e in plan:
        probs = _copy_folder(li, li.text_dir(shelf, e), li.text_dir(dest, e), e)
        if probs:                                         # the copy itself did not verify: stop, say so
            report["refused"][k] = [f"the copy: {p}" for p in probs]
            return report
    for k in gone:
        shutil.rmtree(dest / k, ignore_errors=True)
        _prune((dest / k).parent, dest)
    if reg_changed:
        _write(reg_dest, reg_bytes)
    if report["vendored"] and report["vendored"]["changed"]:
        _write(root / INDEX_DEST, vend_src.read_bytes())

    # the record
    commit = _git(checkout, "rev-parse", "--short", "HEAD") if checkout is not None else None
    status = _git(checkout, "status", "--porcelain", "--", SHELF, INDEX_SOURCE) if checkout is not None else None
    body = {"source": "cosmoes-site" if checkout is not None else str(shelf), "commit": commit,
            "dirty": bool(status) if status is not None else None, "synced": today or _dt.date.today().isoformat(),
            "registry": _sha(reg_bytes), "kept": sorted(_key(e) for e in kept),
            "shelf-digest": li.source_digest(dest)}
    if report["vendored"]:
        body["index-builder"] = {k: report["vendored"][k] for k in ("path", "source", "sha256", "commit")}
    spath = dest / SYNCED
    try:
        have_body = json.loads(spath.read_text(encoding="utf-8")) if spath.is_file() else None
    except ValueError:
        have_body = None

    def _stable(b: dict | None) -> dict | None:
        return {k: v for k, v in b.items() if k not in ("commit", "dirty", "synced")} if b else None
    if _stable(have_body) != _stable(body):
        _write(spath, (json.dumps(body, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    report["shelf_digest"] = body["shelf-digest"]

    # the index, from the files alone
    if index is not None:
        if not li.is_current(dest, index):
            report["index"] = {"path": str(index), **li.build(dest, index)}
        else:
            report["index"] = {"path": str(index), "current": True}
    elif prove:
        with tempfile.TemporaryDirectory(prefix="sync-languages-") as td:
            report["index"] = {"path": None, **li.build(dest, Path(td) / "library.sqlite")}
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--from", dest="source", type=Path, default=DEFAULT_COSMOES,
                    help=f"a cosmoes-site checkout, or a shelf folder holding library.json (default {DEFAULT_COSMOES})")
    ap.add_argument("--root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    ap.add_argument("--check", action="store_true", help="list what differs; write nothing")
    ap.add_argument("--index", type=Path, default=None, help="also build the index into this file")
    args = ap.parse_args(argv)
    try:
        r = sync(args.source, args.root, check=args.check, index=args.index)
    except FileNotFoundError as e:
        print(f"sync_languages: {e}", file=sys.stderr)
        return 2
    if r["refused"]:
        for what, probs in r["refused"].items():
            for p in probs:
                print(f"  refused  {what}: {p}", file=sys.stderr)
        print(f"sync_languages: refused, nothing written ({len(r['refused'])} folder(s) or files do not verify)",
              file=sys.stderr)
        return 1
    for kind in ("added", "changed", "removed"):
        for rel in r[kind]:
            print(f"  {kind:8} {rel}")
    touched = len(r["added"]) + len(r["changed"]) + len(r["removed"])
    idx = r.get("index") or {}
    print(f"{'check' if args.check else 'sync'}: {len(r['added'])} added, {len(r['changed'])} changed, "
          f"{len(r['removed'])} removed, {len(r['unchanged'])} unchanged"
          + (f"; index: {idx.get('kept', 0)} kept, {idx.get('files', 0)} files, {idx.get('sections', 0)} sections"
             if idx and "sections" in idx else ""))
    if args.check and touched:
        print(f"check: {touched} item(s) differ from the shelf — run without --check to sync", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
