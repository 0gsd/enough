#!/usr/bin/env python3
"""Build the scaffolder skill as one bundle for any harness: `scaffolder.skill`
and `scaffolder.zip`, the same bytes under two names (some upload pickers take
only `.zip`).

The bundle is staged from `git archive <ref>` (HEAD by default) of
`defaults/skills/scaffolder/`, so it holds what is committed and nothing a
working tree happens to have. It is a zip whose top folder is `scaffolder/`,
with `SKILL.md` first and every other file after it in path order, every
entry stamped 1980-01-01 00:00:00 with fixed permissions: one commit gives
the same bytes on every build.

The build refuses to write a bundle in which any path, or the text of any
file, names a private sample or a private path (PRIVATE below).

    python3 scripts/build_scaffolder_skill.py              build into dist/
    python3 scripts/build_scaffolder_skill.py --out DIR    build into DIR
    python3 scripts/build_scaffolder_skill.py --ref REF    build from another commit
    python3 scripts/build_scaffolder_skill.py --check      build into a temporary folder and check it:
                                                           nothing staged imports enough, and each
                                                           script answers --help under python3 -I
                                                           from the staged copy alone

Standard library only; git must be on the PATH.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "scaffolder"
SOURCE = f"defaults/skills/{NAME}"
FIRST = "SKILL.md"
STAMP = (1980, 1, 1, 0, 0, 0)
JUNK_PARTS = ("__pycache__", ".pytest_cache", ".DS_Store")
JUNK_SUFFIXES = (".pyc", ".pyo")
#: Never in a bundle, in a path or in a file's text, in any case: comprise-dev's
#: two private samples, and any path into a person's own machine.
PRIVATE = ("longaberger", "katiej", "/users/", "/home/", "/private/tmp/", "c:\\users\\")
IMPORTS_ENOUGH = ("import enough", "from enough")


class BuildError(Exception):
    pass


def stage(dest: Path, ref: str = "HEAD") -> list[str]:
    """`git archive` of the skill at `ref`, unpacked into `dest`; returns the
    staged files' paths relative to `dest`, in bundle order."""
    try:
        tar = subprocess.run(["git", "-C", str(ROOT), "archive", "--format=tar", ref, SOURCE],
                             capture_output=True, check=True).stdout
    except FileNotFoundError:
        raise BuildError("git is not on the PATH; the bundle is built from a commit.") from None
    except subprocess.CalledProcessError as e:
        raise BuildError(f"git archive {ref} {SOURCE} failed: {e.stderr.decode(errors='replace').strip()}") from None
    prefix = SOURCE + "/"
    files = []
    with tarfile.open(fileobj=io.BytesIO(tar)) as tf:
        for m in tf.getmembers():
            if not m.isfile() or not m.name.startswith(prefix):
                continue
            rel = m.name[len(prefix):]
            parts = rel.split("/")
            if any(p in JUNK_PARTS for p in parts) or rel.endswith(JUNK_SUFFIXES) or ".." in parts:
                continue
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            data = tf.extractfile(m).read()  # type: ignore[union-attr]
            out.write_bytes(data)
            if m.mode & 0o111:
                out.chmod(0o755)
            files.append(rel)
    if FIRST not in files:
        raise BuildError(f"{SOURCE}/{FIRST} is not in {ref}: commit the skill first.")
    return [FIRST] + sorted(f for f in files if f != FIRST)


def refuse_private(stage_dir: Path, files: list[str]) -> None:
    named = [f for f in files if any(k in f.lower() for k in PRIVATE)]
    if named:
        raise BuildError(f"refusing to bundle a private name in a path: {', '.join(named[:5])}")
    said = []
    for f in files:
        low = (stage_dir / f).read_bytes().lower()
        if any(k.encode() in low for k in PRIVATE):
            said.append(f)
    if said:
        raise BuildError(f"refusing to bundle files whose text names a private sample or path: {', '.join(said[:5])}")


def zip_bytes(stage_dir: Path, files: list[str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel in files:
            info = zipfile.ZipInfo(f"{NAME}/{rel}", date_time=STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            mode = 0o755 if (stage_dir / rel).stat().st_mode & 0o111 else 0o644
            info.external_attr = (0o100000 | mode) << 16
            z.writestr(info, (stage_dir / rel).read_bytes(), compresslevel=9)
    return buf.getvalue()


def build(out_dir: Path, ref: str = "HEAD") -> tuple[Path, Path, str, int]:
    """Stage, refuse, zip; write both names. Returns (skill, zip, sha256, files)."""
    with tempfile.TemporaryDirectory() as tmp:
        stage_dir = Path(tmp) / NAME
        files = stage(stage_dir, ref)
        refuse_private(stage_dir, files)
        data = zip_bytes(stage_dir, files)
    out_dir.mkdir(parents=True, exist_ok=True)
    skill, zf = out_dir / f"{NAME}.skill", out_dir / f"{NAME}.zip"
    for p in (skill, zf):
        p.write_bytes(data)
    return skill, zf, hashlib.sha256(data).hexdigest(), len(files)


def check(bundle: Path) -> list[str]:
    """Unpack the bundle and check it stands alone: the first entry is
    SKILL.md; no Python file imports enough; every script answers --help
    under `python3 -I` from the staged copy. Returns the problems found."""
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(bundle) as z:
            names = z.namelist()
            if not names or names[0] != f"{NAME}/{FIRST}":
                problems.append(f"the first entry is {names[0] if names else 'nothing'}, not {NAME}/{FIRST}")
            if any(not n.startswith(f"{NAME}/") or ".." in n.split("/") for n in names):
                problems.append("an entry lies outside the top folder")
            z.extractall(tmp)
        top = Path(tmp) / NAME
        for py in sorted(top.rglob("*.py")):
            for i, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
                s = line.strip()
                if any(s.startswith(k + " ") or s.startswith(k + ".") or s == k for k in IMPORTS_ENOUGH):
                    problems.append(f"{py.relative_to(top)}:{i} imports enough: {s}")
        env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
        for script in sorted((top / "scripts").glob("*.py")):
            r = subprocess.run([sys.executable, "-I", str(script), "--help"], cwd=tmp, env=env,
                               capture_output=True, text=True, timeout=60)
            if r.returncode != 0:
                problems.append(f"scripts/{script.name} --help under python3 -I exits {r.returncode}: "
                                f"{(r.stderr or r.stdout).strip()[:300]}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build the scaffolder skill bundle (.skill and .zip, the same bytes).")
    ap.add_argument("--out", help="the folder to write into (default: dist/ in the repo)")
    ap.add_argument("--ref", default="HEAD", help="the commit to build from (default: HEAD)")
    ap.add_argument("--check", action="store_true",
                    help="build into a temporary folder and check the bundle stands alone")
    a = ap.parse_args(argv)
    try:
        if a.check:
            with tempfile.TemporaryDirectory() as tmp:
                skill, _zf, sha, n = build(Path(tmp), a.ref)
                problems = check(skill)
            for p in problems:
                print(p, file=sys.stderr)
            print(f"{'FAILED' if problems else 'OK'}: {NAME}.skill from {a.ref}, {n} files, sha256 {sha}")
            return 1 if problems else 0
        skill, zf, sha, n = build(Path(a.out) if a.out else ROOT / "dist", a.ref)
    except BuildError as e:
        print(str(e), file=sys.stderr)
        return 1
    size = skill.stat().st_size
    print(f"{skill}\n{zf}\n{n} files, {size / 1024:.0f} KB, sha256 {sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
