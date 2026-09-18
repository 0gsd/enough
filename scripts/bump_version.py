#!/usr/bin/env python3
"""Bump enough's version across every file that names it — carefully.

    uv run python scripts/bump_version.py --check
    uv run python scripts/bump_version.py --to 0.3.1 --dry-run
    uv run python scripts/bump_version.py --to 0.3.1

Why this exists: `tests/test_content_integrity.py::check_version_lockstep`
already *asserts* that seven files agree on one version string, but an
assertion only ever tells you AFTER a release slips that something drifted.
This script is the other half — the thing a release actually runs to move
the number, so the seven-way (really nineteen-way; see SITES below) hand
edit stops being how that assertion passes.

Two failure modes shaped the design:

  1. A version string typed by hand in nineteen places will eventually be
     typed in eighteen of them. So `--to` is atomic per file (write a temp
     file, `os.replace` over the original) and the tool re-runs `--check`
     on itself after writing, so a partial bump cannot silently ship.
  2. Some files contain a string that LOOKS like our version but ISN'T:
     mermaid's own `v10.3.0` in a skill reference, Adobe Illustrator's own
     `30.3.0` in an SVG comment, a historical "landed in 0.3.0" mention that
     must keep saying 0.3.0 forever, a dependency in Cargo.lock that just
     happens to be at version 0.3.0 this week. NOT_A_VERSION documents every
     one of these so the next person who greps for the version string and
     finds a new lookalike knows it was considered, not missed.

Everything here is stdlib only. `--to` without `--dry-run` is the only mode
that writes; `--check` and `--to ... --dry-run` never touch a file. This
script never shells out to git — release tagging/committing is a human (or
a different tool's) job.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------
# Parameterized (not a bare module constant) so tests can point every check
# at a throwaway fixture tree instead of the real repo.

DEFAULT_REPO = Path(__file__).resolve().parents[1]

_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
_VERSION_GROUP = r"(\d+\.\d+\.\d+)"


# ---------------------------------------------------------------------------
# Sites: every file that names the version, and how to find it there.
# ---------------------------------------------------------------------------
# Each Site's `pattern` has exactly ONE capture group: the version string.
# `re.search` is used (not `re.match`), and each pattern is anchored enough,
# by literal context, that it cannot land on the wrong occurrence in files
# that contain more than one `\d+\.\d+\.\d+`-shaped string (Cargo.lock is
# the sharpest case of this — see its comment below).

@dataclass(frozen=True)
class Site:
    path: str            # relative to repo root
    pattern: re.Pattern[str]
    label: str           # human name for --check's table and diffs


SITES: tuple[Site, ...] = (
    Site("pyproject.toml",
         re.compile(r'^version = "' + _VERSION_GROUP + r'"', re.M),
         "pyproject.toml [project].version"),

    Site("enough/__init__.py",
         re.compile(r'__version__\s*=\s*"' + _VERSION_GROUP + r'"'),
         "enough/__init__.py __version__"),

    Site("desktop/src-tauri/tauri.conf.json",
         re.compile(r'"version":\s*"' + _VERSION_GROUP + r'"'),
         "tauri.conf.json \"version\""),

    Site("desktop/src-tauri/Cargo.toml",
         re.compile(r'^version = "' + _VERSION_GROUP + r'"', re.M),
         "desktop Cargo.toml [package].version"),

    # Cargo.lock has ~200 `version = "x.y.z"` lines, most of them dependency
    # pins (e.g. `dtor 0.3.0`, `urlpattern 0.3.0` — pure coincidence, same
    # string, different package). The only safe way to find OUR crate's
    # entry is to anchor on the `name = "enough-desktop"` line that
    # immediately precedes it in the same [[package]] block, and capture
    # only the version line that directly follows. This is a plain-text
    # anchor (no TOML parser), but the pair is unique in the file, so a
    # capture-group regex isolates it exactly — no dependency pin is ever
    # touched by this pattern.
    Site("desktop/src-tauri/Cargo.lock",
         re.compile(r'name = "enough-desktop"\nversion = "' + _VERSION_GROUP + r'"'),
         "Cargo.lock enough-desktop entry"),

    Site("bootstrap.sh",
         re.compile(r'enough v' + _VERSION_GROUP + r' runs on macOS'),
         "bootstrap.sh prose"),

    Site("docs/AGENT_GUIDE.md",
         re.compile(r'^#\s.*\(v' + _VERSION_GROUP + r'\)', re.M),
         "AGENT_GUIDE.md title line"),

    Site("docs/HELP_CENTER.md",
         re.compile(r'Written against enough \*\*' + _VERSION_GROUP + r'\*\*'),
         "HELP_CENTER.md header"),

    # The five translated manuals say the same sentence in five different
    # languages ("Rédigé pour enough **0.3.0**", "enough **0.3.0** に対して
    # 書かれています", ...) — only the bold "enough **X.Y.Z**" token is
    # constant, so that is what the pattern matches, not the sentence.
    *(
        Site(f"enough/static/i18n/{lang}/help-center.md",
             re.compile(r'enough \*\*' + _VERSION_GROUP + r'\*\*'),
             f"i18n/{lang}/help-center.md header")
        for lang in ("fr", "es", "de", "zh", "ja")
    ),

    # ui.json's `_meta.source` marker: `"index.html @ 0.3.0"` for en (the
    # catalog is transcribed from index.html), `"en @ 0.3.0"` for the five
    # translations (transcribed from the en catalog). One pattern covers
    # both prefixes since only the trailing version matters here.
    *(
        Site(f"enough/static/i18n/{lang}/ui.json",
             re.compile(r'"source":\s*"[^"]*@ ' + _VERSION_GROUP + r'"'),
             f"i18n/{lang}/ui.json _meta.source")
        for lang in ("en", "fr", "es", "de", "zh", "ja")
    ),
)

assert len(SITES) == 19, f"expected 19 sites, wired up {len(SITES)}"
assert len({s.path for s in SITES}) == len(SITES), "duplicate path in SITES"


# ---------------------------------------------------------------------------
# NOT_A_VERSION: every "0.3.0"-shaped string we found and rejected.
# ---------------------------------------------------------------------------
# Kept here (rather than just in a commit message) so the next person who
# greps the tree for the version string and finds one of these again does
# not have to re-derive that it was already considered.

NOT_A_VERSION: tuple[str, ...] = (
    # Dependency / third-party version pins — not ours to bump.
    "defaults/skills/girraph-merirmaid/references/sequence.md — "
    "\"Actor Creation and Destruction (v10.3.0+)\" is mermaid.js's own "
    "release, not enough's.",
    "defaults/skills/girraph-merirmaid/references/gantt.md (x2) — same: "
    "mermaid.js v10.3.0 feature notes.",
    "enough/static/enough-loader_1-2.svg — "
    "\"Generator: Adobe Illustrator 30.3.0\" is Illustrator's own version.",
    "desktop/src-tauri/Cargo.lock — every OTHER `version = \"0.3.0\"` line "
    "(e.g. the `dtor` and `urlpattern` crates) is a dependency pin that "
    "happens to share our number this release; only the entry immediately "
    "following `name = \"enough-desktop\"` is ours (see SITES).",

    # Historical mentions — name the release a feature landed in, and must
    # keep naming it even after later releases bump past it.
    "docs/AGENT_GUIDE.md — the \"## UI languages (i18n, 0.3.0)\" section "
    "heading records when six-language UI shipped; bumping it would make "
    "it say something false about history.",
    "enough/static/index.html — the ui-prefs-row comment \"...and the "
    "ui-language selector's future slot (0.3.0)\" names the round that "
    "slot was reserved in, same reasoning.",

    # Test fixtures / prose that describe the version rather than assert it.
    "tests/test_content_integrity.py — the KNOWN_FINDINGS docstring comment "
    "mentions 0.3.0 while narrating a past AGENT_GUIDE edit; not a value "
    "any check reads.",
    "tests/test_readvisors.py — "
    "\"a project last opened by 0.3.0\" is a docstring for a migration "
    "fixture; the number is illustrative, not asserted against a real site.",

    # Generated, not hand-edited — see COMPOSURE_FORMS below.
    "defaults/composure-forms/*.comp (blank, cards, council, journal, "
    "scaffold) — the `<meta name=\"generator\" content=\"enough X.Y.Z\">` "
    "line is written by enough/composure.py's _generator(), which reads "
    "enough.__version__ at write time. Regenerate with "
    "scripts/gen_composure_forms.py after bumping __init__.py instead of "
    "editing the .comp files; --to does this automatically.",
    "docs/AGENT_GUIDE.md — the same generator meta line appears again "
    "at line ~1007 as a fenced-code EXAMPLE of the composure format inside "
    "prose documentation; it is not read by anything and editing it is "
    "cosmetic, so it is left alone like the .comp files it illustrates.",

    # Confirmed NOT literals — read the version dynamically, so there is
    # nothing to bump.
    "enough/wikisink/update.py — USER_AGENT interpolates "
    "`from . import __version__` at import time; bumping enough/__init__.py "
    "is sufficient.",
    "scripts/smoke_boot.py — grepped for a version literal; none found.",
)


# ---------------------------------------------------------------------------
# Generated artifacts this tool does not edit but DOES verify in --check.
# ---------------------------------------------------------------------------

COMPOSURE_FORMS_DIR = "defaults/composure-forms"
_COMPOSURE_FORM_NAMES = ("blank", "cards", "council", "journal", "scaffold")
_GENERATOR_RE = re.compile(r'<meta name="generator" content="enough ' + _VERSION_GROUP + r'">')


def composure_forms_status(root: Path, canonical: str | None) -> list[tuple[str, str | None]]:
    """[(form filename, version found or None)] for each shipped .comp form.

    Read-only: this never writes. `--to` calls `scripts/gen_composure_forms.py`
    as a subprocess to regenerate the forms from the new `enough.__version__`,
    then this function is used again (via `--check`) to confirm they picked
    it up.

    A repo (or test fixture) that ships no `defaults/composure-forms/`
    directory at all is not a finding — it just has nothing to check —
    so this returns `[]` rather than five MISSING rows in that case.
    """
    forms_dir = root / COMPOSURE_FORMS_DIR
    if not forms_dir.is_dir():
        return []
    out: list[tuple[str, str | None]] = []
    for name in _COMPOSURE_FORM_NAMES:
        p = forms_dir / f"{name}.comp"
        if not p.is_file():
            out.append((f"{name}.comp", None))
            continue
        m = _GENERATOR_RE.search(p.read_text(encoding="utf-8"))
        out.append((f"{name}.comp", m.group(1) if m else None))
    return out


# ---------------------------------------------------------------------------
# --check
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Found:
    site: Site
    version: str | None    # None = pattern did not match (file missing counts as None too)
    error: str | None = None


def read_sites(root: Path) -> list[Found]:
    out: list[Found] = []
    for site in SITES:
        p = root / site.path
        if not p.is_file():
            out.append(Found(site, None, f"{site.path} does not exist"))
            continue
        text = p.read_text(encoding="utf-8")
        m = site.pattern.search(text)
        out.append(Found(site, m.group(1) if m else None))
    return out


def canonical_version(found: list[Found]) -> str | None:
    """pyproject.toml is the source of truth, same as
    test_content_integrity.py's check_version_lockstep."""
    for f in found:
        if f.site.path == "pyproject.toml":
            return f.version
    return None


def print_check_table(found: list[Found], canonical: str | None,
                       forms: list[tuple[str, str | None]]) -> bool:
    """Print the site table; return True iff everything agrees."""
    width = max(len(f.site.label) for f in found)
    ok = True
    print(f"canonical version (pyproject.toml): {canonical or '(not found)'}\n")
    for f in found:
        if f.version is None:
            status = f"MISSING ({f.error or 'pattern did not match'})"
            ok = False
        elif f.version != canonical:
            status = f"MISMATCH ({f.version!r})"
            ok = False
        else:
            status = f"ok ({f.version})"
        print(f"  {f.site.label.ljust(width)}  {status}")

    if forms:
        print(f"\n  {'generated composure forms'.ljust(width)}  "
              f"(scripts/gen_composure_forms.py — not edited directly)")
        for name, version in forms:
            if version is None:
                status = "MISSING generator stamp"
                ok = False
            elif version != canonical:
                status = f"MISMATCH ({version!r}) — run scripts/gen_composure_forms.py"
                ok = False
            else:
                status = f"ok ({version})"
            print(f"    {name.ljust(width - 2)}  {status}")
    return ok


def cmd_check(root: Path) -> int:
    found = read_sites(root)
    canonical = canonical_version(found)
    forms = composure_forms_status(root, canonical)
    ok = print_check_table(found, canonical, forms)
    print(f"\n{'all sites agree' if ok else 'DISAGREEMENT — see above'}")
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# --to
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Change:
    site: Site
    before: str
    after: str
    old_version: str | None
    new_text: str


def plan_changes(root: Path, new_version: str) -> tuple[list[Change], list[str]]:
    """Compute every edit `--to` would make, without writing anything.

    Returns (changes, problems). A problem (missing file, pattern didn't
    match) does not raise — it is reported so `--check`-style output can
    show every issue at once instead of stopping at the first one.
    """
    changes: list[Change] = []
    problems: list[str] = []
    for site in SITES:
        p = root / site.path
        if not p.is_file():
            problems.append(f"{site.path}: file does not exist")
            continue
        before = p.read_text(encoding="utf-8")
        m = site.pattern.search(before)
        if not m:
            problems.append(f"{site.path}: pattern for {site.label!r} did not match")
            continue
        start, end = m.span(1)
        after = before[:start] + new_version + before[end:]
        if after == before:
            continue    # already at the target version — nothing to change
        changes.append(Change(site, before, after, m.group(1), after))
    return changes, problems


def render_diff(site_path: str, before: str, after: str) -> str:
    return "".join(difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=f"a/{site_path}", tofile=f"b/{site_path}"))


def write_atomic(path: Path, text: str) -> None:
    """Write-tmp-then-rename so a crash mid-bump never leaves a half file."""
    tmp = path.with_suffix(path.suffix + ".bumptmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def regenerate_composure_forms(root: Path) -> tuple[bool, str]:
    """Run scripts/gen_composure_forms.py so the shipped .comp forms pick up
    the new enough.__version__. Returns (ran_ok, message)."""
    script = root / "scripts" / "gen_composure_forms.py"
    if not script.is_file():
        return False, f"{script} not found — regenerate the composure forms manually"
    for runner in (("uv", "run", "python", str(script)), (sys.executable, str(script))):
        try:
            proc = subprocess.run(runner, cwd=root, capture_output=True, text=True,
                                   timeout=120)
        except (OSError, subprocess.SubprocessError) as e:
            continue
        if proc.returncode == 0:
            return True, proc.stdout.strip() or "regenerated composure forms"
        return False, (f"scripts/gen_composure_forms.py exited "
                        f"{proc.returncode}:\n{proc.stdout}{proc.stderr}")
    return False, ("could not run scripts/gen_composure_forms.py (no `uv` and no "
                    f"working `{sys.executable}`) — run it by hand: "
                    "uv run python scripts/gen_composure_forms.py")


def cmd_to(root: Path, new_version: str, dry_run: bool, force: bool) -> int:
    if not _SEMVER.match(new_version):
        print(f"error: --to {new_version!r} is not X.Y.Z", file=sys.stderr)
        return 2

    found = read_sites(root)
    canonical = canonical_version(found)
    if canonical is not None and not force:
        old = tuple(int(x) for x in canonical.split("."))
        new = tuple(int(x) for x in new_version.split("."))
        if new < old:
            print(f"error: --to {new_version} goes backwards from {canonical} "
                  f"(pyproject.toml) — pass --force to override", file=sys.stderr)
            return 2

    changes, problems = plan_changes(root, new_version)
    for p in problems:
        print(f"warning: {p}", file=sys.stderr)

    if not changes:
        print("nothing to change — every site already matches "
              f"{new_version!r} (or none exist)")
        return 1 if problems else 0

    for c in changes:
        print(f"--- {c.site.path} ({c.site.label}): "
              f"{c.old_version!r} -> {new_version!r}")
        print(render_diff(c.site.path, c.before, c.after))

    if dry_run:
        print(f"(dry run — {len(changes)} file(s) would change, "
              f"nothing was written)")
        return 1 if problems else 0

    for c in changes:
        write_atomic(root / c.site.path, c.after)
    print(f"wrote {len(changes)} file(s)")

    ok, message = regenerate_composure_forms(root)
    print(f"{'ok' if ok else 'warning'}: {message}")

    print("\nre-running --check:")
    return cmd_check(root)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=DEFAULT_REPO,
                     help="repo root to operate on (default: this checkout; "
                          "tests point this at a fixture tree)")
    ap.add_argument("--check", action="store_true",
                     help="report every version-bearing site and exit 1 on disagreement")
    ap.add_argument("--to", metavar="X.Y.Z",
                     help="the version to bump every site to")
    ap.add_argument("--dry-run", action="store_true",
                     help="with --to: show the diff, write nothing")
    ap.add_argument("--force", action="store_true",
                     help="with --to: allow moving to a lower version")
    args = ap.parse_args(argv)

    if args.to and args.check:
        print("error: --check and --to are mutually exclusive", file=sys.stderr)
        return 2
    if args.dry_run and not args.to:
        print("error: --dry-run only makes sense with --to", file=sys.stderr)
        return 2
    if args.force and not args.to:
        print("error: --force only makes sense with --to", file=sys.stderr)
        return 2

    root = args.root.resolve()
    if args.to:
        return cmd_to(root, args.to, args.dry_run, args.force)
    if args.check:
        return cmd_check(root)

    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
