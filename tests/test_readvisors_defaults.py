"""Shape tests for the shipped readvisors (`defaults/readvisors/`).

Pure repo inspection, in the manner of `test_skills_defaults.py`. The
contract they pin is P2d's: "all readvisors work in roughly the same way,
despite their unique personalities and quirks."

The interesting property of `prompt.readvisor_shape` is that it does NOT
hard-code the shape — it reads its headings from the `readvisory` skill's
two templates at call time. So this file mostly asserts that the shipped
readvisors satisfy whatever those templates currently say, which means a
deliberate change to the shape is a one-file change and an accidental
divergence is a test failure.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from enough import prompt

REPO_ROOT = Path(__file__).resolve().parents[1]
READVISORS_DIR = REPO_ROOT / "defaults" / "readvisors"

READVISOR_DIRS = sorted(
    p for p in READVISORS_DIR.iterdir()
    if p.is_dir() and not p.name.startswith(".")
) if READVISORS_DIR.is_dir() else []

READVISOR_NAMES = [p.name for p in READVISOR_DIRS]

#: The old pipeline's bookkeeping, and the old vocabulary. Neither belongs
#: in a document that is read verbatim into a system prompt.
_BANNED = (
    "<!-- proxy-hash",
    "<!-- augmented-by",
)

#: Old-vocabulary words, as whole words. "agent" survives only as part of
#: the filename `AGENT.md`, which these documents have no reason to mention.
_OLD_VOCAB_RE = re.compile(r"\b(agents?|roles?)\b", re.IGNORECASE)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_the_folder_exists_and_is_not_empty():
    """The 0.3.5 rename moved `defaults/roles/` here. A repo with neither
    folder would make every test below vacuously pass."""
    assert READVISORS_DIR.is_dir(), f"{READVISORS_DIR} is missing"
    assert READVISOR_NAMES, "no shipped readvisors found"
    assert not (REPO_ROOT / "defaults" / "roles").exists(), (
        "defaults/roles/ is back — the rename is the one in P2, not a copy")


@pytest.mark.parametrize("d", READVISOR_DIRS, ids=READVISOR_NAMES)
def test_folder_name_is_kebab_case(d: Path):
    assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", d.name), (
        f"{d.name!r} is not kebab-case; it is a folder name on the user's "
        f"disk and the name `install_readvisor` would refuse")


@pytest.mark.parametrize("d", READVISOR_DIRS, ids=READVISOR_NAMES)
def test_both_documents_exist_and_are_substantial(d: Path):
    for fname in ("AGENT.md", "MOTIVATION.md"):
        f = d / fname
        assert f.is_file(), f"{d.name}/{fname} is missing"
        body = _read(f)
        assert len(body) > 600, (
            f"{d.name}/{fname} is {len(body)} chars — a readvisor this thin "
            f"cannot carry a point of view")


@pytest.mark.parametrize("d", READVISOR_DIRS, ids=READVISOR_NAMES)
def test_conforms_to_the_readvisor_shape(d: Path):
    """The whole of P2d, in one assertion."""
    problems = prompt.readvisor_shape(_read(d / "AGENT.md"),
                                      _read(d / "MOTIVATION.md"))
    assert not problems, f"{d.name}:\n" + "\n".join(f"  - {p}" for p in problems)


@pytest.mark.parametrize("d", READVISOR_DIRS, ids=READVISOR_NAMES)
def test_tooltip_is_the_last_non_empty_line_of_agent_md(d: Path):
    """The sidebar shows it on hover, and `_extract_enough_tooltip` finds it
    by regex anywhere in the file — so "it parses" is not enough. It has to
    be the last line, or an edit that appends a section quietly buries it in
    the middle of a document and nobody notices."""
    lines = [ln for ln in _read(d / "AGENT.md").splitlines() if ln.strip()]
    assert lines, f"{d.name}/AGENT.md is empty"
    assert lines[-1].startswith("enough-tooltip-text:"), (
        f"{d.name}/AGENT.md ends with {lines[-1]!r}, not the tooltip line")
    tooltip = prompt._extract_enough_tooltip(_read(d / "AGENT.md"))
    assert tooltip and "\n" not in tooltip, (
        f"{d.name}/AGENT.md's tooltip must be a single non-empty line")


@pytest.mark.parametrize("d", READVISOR_DIRS, ids=READVISOR_NAMES)
def test_motivation_has_no_tooltip(d: Path):
    """Exactly one tooltip per readvisor, and it belongs to AGENT.md. Two
    would mean the sidebar's hover text depends on which file was read."""
    assert not prompt._extract_enough_tooltip(_read(d / "MOTIVATION.md")), (
        f"{d.name}/MOTIVATION.md carries a tooltip line; AGENT.md owns it")


@pytest.mark.parametrize("d", READVISOR_DIRS, ids=READVISOR_NAMES)
def test_no_old_pipeline_comments(d: Path):
    for fname in ("AGENT.md", "MOTIVATION.md"):
        body = _read(d / fname)
        for marker in _BANNED:
            assert marker not in body, (
                f"{d.name}/{fname} still carries {marker!r} from the "
                f"advice-proxy pipeline")


@pytest.mark.parametrize("d", READVISOR_DIRS, ids=READVISOR_NAMES)
def test_no_old_vocabulary(d: Path):
    """These documents go into the system prompt verbatim, so they are the
    place where "agent" and "role" would most effectively undo the rename."""
    for fname in ("AGENT.md", "MOTIVATION.md"):
        hits = sorted({m.group(0) for m in _OLD_VOCAB_RE.finditer(_read(d / fname))})
        assert not hits, (
            f"{d.name}/{fname} uses the old vocabulary: {', '.join(hits)}")


@pytest.mark.parametrize("d", READVISOR_DIRS, ids=READVISOR_NAMES)
def test_display_name_is_readable(d: Path):
    """`_display_name` is the only source of the pretty name, so an AGENT.md
    whose H1 is still a placeholder would ship one."""
    name = prompt._display_name(_read(d / "AGENT.md"), d.name)
    assert name and name != d.name, (
        f"{d.name}/AGENT.md has no `# <Display Name>` heading of its own")
    assert "[" not in name and "]" not in name, (
        f"{d.name}'s display name {name!r} still looks like the template's "
        f"[DISPLAY_NAME] placeholder")


def test_templates_are_present_and_define_a_shape():
    """`readvisor_shape` degrades to "no shape to enforce" when the
    templates are missing, which is right at runtime and wrong here: a repo
    that lost them would make every shape test above pass silently."""
    for which in ("agent", "motivation"):
        headings = prompt._template_headings(which)
        assert len(headings) >= 5, (
            f"the {which} template defines only {len(headings)} sections — "
            f"the readvisory skill's assets/ are the source of truth for the "
            f"shape and look broken")
