"""Tests for scripts/bump_version.py.

Every test that exercises `--check` / `--to` builds its own throwaway
fixture tree under `tmp_path` — never the real checkout — because the
whole point of this tool is that it writes files, and a test that pointed
it at the real repo could bump the real repo's version. `build_fixture`
below hand-writes a small, realistic slice of each of the 19 sites (plus
one deliberately excluded lookalike per exclusion class) so the tests
exercise the actual regexes, not a tautology generated from them.

The one test that DOES touch the real repo (`test_real_repo_is_clean`)
only ever runs `--check`, which is read-only by construction.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import bump_version  # noqa: E402

LANGS_ALL = ("en", "fr", "es", "de", "zh", "ja")
LANGS_TRANSLATED = ("fr", "es", "de", "zh", "ja")

# Per-language "Written against enough **X**" sentence, one per translated
# manual, matching the real files closely enough to exercise the pattern
# without copying their prose verbatim.
_HELP_CENTER_SENTENCE = {
    "fr": "Rédigé pour enough **{v}**, le reste du texte.",
    "es": "Escrito para enough **{v}**, el resto del texto.",
    "de": "Geschrieben für enough **{v}**, der Rest des Textes.",
    "zh": "本文对应 enough **{v}**，其余文本。",
    "ja": "enough **{v}** に対して書かれています。",
}


def build_fixture(root: Path, version: str, *, historical: str = "0.3.0") -> None:
    """A minimal tree covering every Site in bump_version.SITES, plus the
    NOT_A_VERSION lookalikes that must survive a bump untouched.

    `historical` is a DIFFERENT number than `version` on purpose in most
    tests, so a bump that accidentally touched an excluded string is
    caught instead of silently agreeing with the real edit.
    """
    (root / "pyproject.toml").write_text(
        '[project]\n'
        'name = "enough"\n'
        f'version = "{version}"\n'
        'description = "fixture"\n', encoding="utf-8")

    (root / "enough").mkdir(parents=True, exist_ok=True)
    (root / "enough" / "__init__.py").write_text(
        '"""enough fixture."""\n\n'
        f'__version__ = "{version}"\n', encoding="utf-8")

    tauri_dir = root / "desktop" / "src-tauri"
    tauri_dir.mkdir(parents=True, exist_ok=True)
    (tauri_dir / "tauri.conf.json").write_text(json.dumps({
        "$schema": "https://schema.tauri.app/config/2",
        "productName": "enough",
        "version": version,
        "identifier": "com.enough.desktop",
    }, indent=2) + "\n", encoding="utf-8")

    (tauri_dir / "Cargo.toml").write_text(
        '[package]\n'
        'name = "enough-desktop"\n'
        f'version = "{version}"\n'
        'description = "fixture"\n', encoding="utf-8")

    # A decoy package sharing the historical number, exactly like the real
    # Cargo.lock's `dtor`/`urlpattern` dependency pins — must NOT be bumped.
    (tauri_dir / "Cargo.lock").write_text(
        '[[package]]\n'
        'name = "some-dependency"\n'
        f'version = "{historical}"\n'
        'source = "registry+https://example"\n'
        '\n'
        '[[package]]\n'
        'name = "enough-desktop"\n'
        f'version = "{version}"\n'
        'dependencies = [\n'
        ' "libc",\n'
        ']\n', encoding="utf-8")

    (root / "bootstrap.sh").write_text(
        '#!/bin/sh\n'
        f'note "enough v{version} runs on macOS (fixture) and Linux."\n',
        encoding="utf-8")

    docs = root / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "AGENT_GUIDE.md").write_text(
        f'# enough — Agent Guide (v{version})\n\n'
        'body text.\n\n'
        # Generated-artifact lookalike (docs/AGENT_GUIDE.md:~1007 in the
        # real repo) — a doc example, must not be touched.
        f'<meta name="generator" content="enough {historical}">\n\n'
        # Historical section heading — names the release a feature landed
        # in, must not be touched even though it looks like a version.
        f'## UI languages (i18n, {historical})\n\n'
        'more body text.\n', encoding="utf-8")
    (docs / "HELP_CENTER.md").write_text(
        f'# HELP CENTER\n\n'
        f'> Written against enough **{version}**, and the rest of the intro.\n',
        encoding="utf-8")

    i18n = root / "enough" / "static" / "i18n"
    for lang in LANGS_ALL:
        d = i18n / lang
        d.mkdir(parents=True, exist_ok=True)
        source = f"index.html @ {version}" if lang == "en" else f"en @ {version}"
        (d / "ui.json").write_text(json.dumps({
            "_meta": {"language": lang, "source": source},
            "strings": {},
        }, indent=2) + "\n", encoding="utf-8")
    for lang in LANGS_TRANSLATED:
        sentence = _HELP_CENTER_SENTENCE[lang].format(v=version)
        (i18n / lang / "help-center.md").write_text(
            f"> {sentence}\n", encoding="utf-8")


def run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO / "scripts" / "bump_version.py"),
         "--root", str(root), *args],
        capture_output=True, text=True)


# ---------------------------------------------------------------------------
# --check
# ---------------------------------------------------------------------------

def test_check_agrees(tmp_path: Path) -> None:
    build_fixture(tmp_path, "1.2.3")
    proc = run(tmp_path, "--check")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "all sites agree" in proc.stdout
    assert "MISMATCH" not in proc.stdout
    assert "MISSING" not in proc.stdout


def test_check_disagrees(tmp_path: Path) -> None:
    build_fixture(tmp_path, "1.2.3")
    # Hand-drift one site away from the rest, the way a half-finished
    # manual edit would.
    init = tmp_path / "enough" / "__init__.py"
    init.write_text(init.read_text(encoding="utf-8").replace("1.2.3", "1.2.2"),
                     encoding="utf-8")
    proc = run(tmp_path, "--check")
    assert proc.returncode == 1
    assert "DISAGREEMENT" in proc.stdout
    assert "MISMATCH ('1.2.2')" in proc.stdout


def test_check_reports_missing_site(tmp_path: Path) -> None:
    build_fixture(tmp_path, "1.2.3")
    (tmp_path / "bootstrap.sh").unlink()
    proc = run(tmp_path, "--check")
    assert proc.returncode == 1
    assert "MISSING" in proc.stdout


# ---------------------------------------------------------------------------
# --to --dry-run
# ---------------------------------------------------------------------------

def test_dry_run_makes_no_change(tmp_path: Path) -> None:
    build_fixture(tmp_path, "1.2.3")
    before = {p: p.read_text(encoding="utf-8")
              for p in tmp_path.rglob("*") if p.is_file()}

    proc = run(tmp_path, "--to", "1.3.0", "--dry-run")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "dry run" in proc.stdout
    assert "1.2.3" in proc.stdout and "1.3.0" in proc.stdout
    assert "-version = \"1.2.3\"" in proc.stdout   # unified diff, minus side
    assert "+version = \"1.3.0\"" in proc.stdout   # unified diff, plus side

    after = {p: p.read_text(encoding="utf-8")
             for p in tmp_path.rglob("*") if p.is_file()}
    assert before == after, "dry-run must not write anything"


# ---------------------------------------------------------------------------
# --to (real bump)
# ---------------------------------------------------------------------------

def test_bump_changes_every_site(tmp_path: Path) -> None:
    build_fixture(tmp_path, "1.2.3")
    proc = run(tmp_path, "--to", "1.3.0")
    assert proc.returncode == 0, proc.stdout + proc.stderr

    check = bump_version.read_sites(tmp_path)
    assert all(f.version == "1.3.0" for f in check), [
        (f.site.path, f.version) for f in check]

    # cmd_to re-runs --check internally and prints its own verdict too.
    assert "all sites agree" in proc.stdout


def test_bump_leaves_exclusions_untouched(tmp_path: Path) -> None:
    build_fixture(tmp_path, "1.2.3", historical="0.3.0")
    run(tmp_path, "--to", "1.3.0")

    guide = (tmp_path / "docs" / "AGENT_GUIDE.md").read_text(encoding="utf-8")
    assert "## UI languages (i18n, 0.3.0)" in guide, \
        "historical section heading must not be bumped"
    assert '<meta name="generator" content="enough 0.3.0">' in guide, \
        "doc-example generator line must not be bumped"

    lock = (tmp_path / "desktop" / "src-tauri" / "Cargo.lock").read_text(encoding="utf-8")
    assert 'name = "some-dependency"\nversion = "0.3.0"' in lock, \
        "a dependency pin that coincidentally matches must not be bumped"
    assert 'name = "enough-desktop"\nversion = "1.3.0"' in lock


def test_bump_refuses_to_go_backwards(tmp_path: Path) -> None:
    build_fixture(tmp_path, "1.2.3")
    proc = run(tmp_path, "--to", "1.0.0")
    assert proc.returncode != 0
    assert "backwards" in proc.stderr

    check = bump_version.read_sites(tmp_path)
    assert all(f.version == "1.2.3" for f in check), "refused bump must not write"


def test_bump_backwards_allowed_with_force(tmp_path: Path) -> None:
    build_fixture(tmp_path, "1.2.3")
    proc = run(tmp_path, "--to", "1.0.0", "--force")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    check = bump_version.read_sites(tmp_path)
    assert all(f.version == "1.0.0" for f in check)


def test_bump_rejects_malformed_version(tmp_path: Path) -> None:
    build_fixture(tmp_path, "1.2.3")
    proc = run(tmp_path, "--to", "1.2")
    assert proc.returncode == 2
    check = bump_version.read_sites(tmp_path)
    assert all(f.version == "1.2.3" for f in check)


# ---------------------------------------------------------------------------
# The real repo
# ---------------------------------------------------------------------------

def test_real_repo_is_clean() -> None:
    """Every version site in THIS checkout agrees today. `--check` is
    read-only, so this is safe to run against the real tree.

    If this fails, the failure message names exactly which site disagrees
    (via bump_version's own table) rather than this assertion being
    weakened to tolerate drift.
    """
    found = bump_version.read_sites(REPO)
    canonical = bump_version.canonical_version(found)
    assert canonical is not None, "pyproject.toml's own version did not parse"

    disagreements = [(f.site.path, f.site.label, f.version, f.error)
                      for f in found if f.version != canonical]
    assert not disagreements, (
        f"expected every version site to say {canonical!r}, but:\n  " +
        "\n  ".join(f"{path} ({label}): got {version!r} ({error})"
                     for path, label, version, error in disagreements))

    forms = bump_version.composure_forms_status(REPO, canonical)
    stale_forms = [(name, v) for name, v in forms if v != canonical]
    assert not stale_forms, (
        f"composure forms out of lockstep with {canonical!r} — run "
        f"`uv run python scripts/gen_composure_forms.py`: {stale_forms}")
