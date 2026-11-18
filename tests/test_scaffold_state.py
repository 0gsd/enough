"""The scaffolder's one reader and writer: `defaults/skills/scaffolder/scripts/scaffold_state.py`.

It travels in the skill to harnesses that have no enough, so it is loaded here the way enough
loads it (`scaffolder.state_module`), and it is also run alone under `python -I` to show it
needs nothing of enough. The four worked examples under `references/examples/` are the fixtures.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from enough import scaffolder as SC

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "defaults" / "skills" / "scaffolder"
EXAMPLES = SKILL / "references" / "examples"
SCRIPT = SKILL / "scripts" / "scaffold_state.py"
S = SC.state_module()

PLECTRUMS = ["more-page.md", "ten-slide-deck.md", "document.md"]


def read(name: str) -> str:
    return (EXAMPLES / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Round trips on the four examples
# ---------------------------------------------------------------------------

def test_the_state_example_round_trips_byte_for_byte():
    text = read("ten-slide-deck.state.md")
    model = S.loads(text)
    assert model.kind == "scaffold"
    assert S.dumps(model) == text
    assert S.to_dict(S.loads(S.dumps(model))) == S.to_dict(model)


@pytest.mark.parametrize("name", PLECTRUMS)
def test_a_typed_plectrum_reads_to_the_model_of_its_writer_form(name: str):
    model = S.loads(read(name))
    assert model.kind == "plectrum" and not model.warnings
    written = S.dumps(model)
    again = S.loads(written)
    assert S.to_dict(again) == S.to_dict(model)
    assert S.dumps(again) == written  # the writer's form is a fixed point


@pytest.mark.parametrize("name", PLECTRUMS + ["ten-slide-deck.state.md"])
def test_json_round_trips(name: str):
    model = S.loads(read(name))
    back = S.from_json(S.to_json(model))
    assert S.to_dict(back) == S.to_dict(model)
    assert S.dumps(back) == S.dumps(model)


@pytest.mark.parametrize("name, frames, boxes, sums", [
    ("more-page.md", 8, 19, {"c": 2800}),
    ("ten-slide-deck.md", 11, 25, {"c": 3020}),
    ("document.md", 27, 125, {"w": 11012}),
])
def test_the_count_matches_what_each_example_says(name, frames, boxes, sums):
    model = S.loads(read(name))
    c = S.count(model)
    assert (c["frames"], c["boxes"], c["targets"]) == (frames, boxes, sums)
    assert S.count_line(model).startswith(
        f"This is {frames} frames and {boxes} boxes, {frames + boxes} parts in all.")


def test_the_plectrum_lays_out_as_its_state_does():
    """The deck's plectrum and its state agree on every box's id, what it is, its target, shape,
    row and column: the defaults the reader spells out are the ones the state was written with."""
    plectrum = S.loads(read("ten-slide-deck.md"))
    state = S.loads(read("ten-slide-deck.state.md"))
    keys = ("id", "as", "kind", "target", "shape", "row", "col", "fixed", "chips")
    assert [[b[k] for k in keys] for b in plectrum.boxes()] == \
        [[b[k] for k in keys] for b in state.boxes()]
    assert [f["id"] for f in plectrum.frames] == [f["id"] for f in state.frames]


def test_the_plectrum_back_out_of_a_state():
    state = S.loads(read("ten-slide-deck.state.md"))
    text = S.dumps(state, "plectrum")
    plectrum = S.loads(text)
    assert plectrum.kind == "plectrum" and not plectrum.findings
    assert all(not b["text"] and b["state"] is None for b in plectrum.boxes())
    assert "version:" not in text and "locked:" not in text
    # the person's edited plec stays theirs
    assert plectrum.box("plot-headline")["plec_by"] == "person"


def test_a_repeated_section_expands_and_folds_back():
    model = S.loads(read("document.md"))
    recipes = [f for f in model.frames if f["copy_of"] == "recipe"]
    assert len(recipes) == 24
    assert recipes[6]["id"] == "recipe-07" and recipes[6]["name"] == "Recipe 7"
    dish = recipes[6]["boxes"][0]
    assert dish["id"] == "dish-07" and "dish 7," in dish["plec"]
    written = S.dumps(model)
    assert written.count("repeat: 24") == 1 and "{n}" in written
    # as a state, every copy is written out with copy-of and copy
    state = S.Scaffold(kind="scaffold", meta={**model.meta, "version": 1},
                       frames=model.frames)
    as_state = S.dumps(state)
    assert as_state.count("copy-of: recipe") == 24 and "repeat:" not in as_state
    assert S.to_dict(S.as_plectrum(S.loads(as_state))) == S.to_dict(model)


# ---------------------------------------------------------------------------
# The person's text, findings, hand-typed forms
# ---------------------------------------------------------------------------

STATE_HEAD = """---
scaffold: 1
title: T
thing: page
for: me
writes: all of it
---

# T

## Band

### b1 · One

```plec
plec: Say the thing.
```
"""


def test_text_lines_that_look_like_headings_are_escaped_and_restored():
    text = "# Not a title\n\\# kept\n#### four\n#tag\n\nlast line"
    model = S.loads(STATE_HEAD)
    model.box("b1")["text"] = text
    written = S.dumps(model)
    assert "\\# Not a title\n\\\\# kept\n\\#### four\n\\#tag" in written
    assert S.loads(written).box("b1")["text"] == text
    assert S.dumps(S.loads(written)) == written


def test_findings_escape_line_breaks_and_backslashes():
    model = S.loads(STATE_HEAD)
    model.box("b1")["text"] = "a\\b\nc"
    model.findings.append({"id": "f1", "box": "b1", "kind": "grammar", "quote": "a\\b\nc",
                           "prefix": None, "suffix": None, "fix": "ab c", "why": "two lines",
                           "status": "open", "version": 1, "extra": {}})
    written = S.dumps(model)
    assert "quote: a\\\\b\\nc" in written
    back = S.loads(written)
    assert back.findings[0]["quote"] == "a\\b\nc"
    assert S.dumps(back) == written


def test_hand_typed_forms_read_as_the_writer_form():
    typed = STATE_HEAD.replace("### b1 · One", "### b1 | One").replace(
        "plec: Say the thing.", "state: over\nunknown-key: kept\nplec: Say\n  the thing.")
    model = S.loads(typed)
    box = model.box("b1")
    assert box["plec"] == "Say the thing." and box["state"] is None
    assert box["extra"] == {"unknown-key": "kept"}
    assert (box["target"], box["row"], box["col"], box["as"]) == ("0", 1, 1, "body")
    assert "unknown-key: kept" in S.dumps(model)


def test_the_title_line_disagreeing_is_said_and_the_front_matter_wins():
    model = S.loads(STATE_HEAD.replace("\n# T\n", "\n# Another\n"))
    assert model.meta["title"] == "T" and "front matter wins" in model.warnings[0]


# ---------------------------------------------------------------------------
# Refusals name the line and the fix
# ---------------------------------------------------------------------------

PLEC = """---
plectrum: 1
title: T
thing: deck
for: them
writes: all
---

# T

## One

- A box [140c]: What it says.
"""


@pytest.mark.parametrize("text, line, words", [
    ("# T\n\n## G\n\n### C\n", 1, "outline"),
    ("hello\n", 1, "starts with a line `---`"),
    (PLEC.replace("plectrum: 1", "plectrum: 2"), 2, "grammar this reader does not know"),
    (PLEC.replace("thing: deck", "thing: poster"), 4, "page, deck or document"),
    (PLEC.replace("for: them\n", ""), 0, "Add `for:`"),
    (PLEC + "\n## Two\n", 15, "holds no plec"),
    (PLEC + "\n#### deep\n", 15, "heading the grammar does not have"),
    (PLEC + "\n```plec\nplec: x\n```\n", 15, "no `### ` box heading above it"),
    (PLEC + "\n### b · B\n\n```plec\nas: body\n```\n", 17, "Add `plec:`"),
    (PLEC + "\n- Bad [7 apples]: x\n", 15, "bracket"),
    (PLEC.replace("[140c]", "[graphic 4:3 big]"), 13, "bracket"),
    (PLEC + "\n- A box [10c]: twice\n", 0, "used twice"),
    (PLEC + "\n# Second\n", 15, "second `#` line"),
    (PLEC.replace("title: T\n", "title: T\ntitle: U\n"), 4, "given twice"),
    (PLEC.replace("## One", "## One\n\n```frame\nrepeat: 1\n```"), 14, "from 2 to 999"),
])
def test_refusals(text: str, line: int, words: str):
    with pytest.raises(S.StateError) as e:
        S.loads(text)
    assert words in str(e.value)
    if line:
        assert str(e.value).startswith(f"Line {line}:"), str(e.value)
    # every refusal ends with what to do
    assert str(e.value).rstrip().endswith(".")


def test_validate_names_every_problem_in_a_built_model():
    model = S.loads(PLEC)
    model.box("a-box")["text"] = "words in a plectrum"
    model.frames[0]["boxes"].append({**model.box("a-box"), "id": "Bad Id", "_line": None})
    problems = S.validate(model)
    assert any("holds no text" in p for p in problems)
    assert any("is not an id" in p for p in problems)


# ---------------------------------------------------------------------------
# It needs nothing of enough
# ---------------------------------------------------------------------------

def test_the_script_imports_nothing_of_enough():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "import enough" not in source and "from enough" not in source
    for name in ("check", "plectrum"):
        run = subprocess.run([sys.executable, "-I", str(SCRIPT), name,
                              str(EXAMPLES / "ten-slide-deck.state.md")],
                             capture_output=True, text=True, cwd=str(SCRIPT.parent.parent))
        assert run.returncode == 0, run.stderr
    assert "11 frames and 25 boxes" in subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "check", str(EXAMPLES / "ten-slide-deck.md")],
        capture_output=True, text=True).stdout


def test_the_command_line_refuses_with_the_line():
    run = subprocess.run([sys.executable, "-I", str(SCRIPT), "check", str(SKILL / "SKILL.md")],
                         capture_output=True, text=True)
    assert run.returncode == 1 and run.stderr.startswith("Line 2:")
