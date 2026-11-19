"""The owner's three rulings on Thym's behaviour of 2026-11-19 (docs/v080-pins.md section 22, lane W5-TQ):

- A. A closing quotation mark (or bracket) after a sentence's stop stays with its sentence, and the moves' `segment`
  and the checks' `sentences` split by one rule, held in one place (`checks.split_sentences`).
- B. A words-mode coverage map counts lines in the file as written, front matter included, like every other mode.
- C. `for each` over a short binds a `string` at run time, as the compiler (`types.member`) says, in both runtimes.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from enough.thym import checks as C
from enough.thym import moves as M
from enough.thym import types as TY
from enough.thym.values import Value, members

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


# ---------------------------------------------------------------------------
# A. One sentence rule; a closing mark stays with its sentence
# ---------------------------------------------------------------------------

KEPT = [
    ('He said "Go." Then he left.', ['He said "Go."', "Then he left."]),
    ("He said “Go.” Then he left.", ["He said “Go.”", "Then he left."]),
    ("She said ‘Stop.’ Then she sat.", ["She said ‘Stop.’", "Then she sat."]),
    ("She said 'Stop.' Then she sat.", ["She said 'Stop.'", "Then she sat."]),
    ("It rained (all day.) The well filled.", ["It rained (all day.)", "The well filled."]),
    ("See the list [twice.] Then stop.", ["See the list [twice.]", "Then stop."]),
    ('Was it "over?" "Yes," she said.', ['Was it "over?"', '"Yes," she said.']),
    ("Dr. Okafor came. She left.", ["Dr. Okafor came.", "She left."]),
    ("Plain. Two words. 3 apples fell.", ["Plain.", "Two words.", "3 apples fell."]),
]


@pytest.mark.parametrize("text,want", KEPT)
def test_the_moves_keep_a_closing_mark_with_its_sentence(text, want):
    assert [s.text for s in M.segment(text + "\n")] == want


@pytest.mark.parametrize("text,want", KEPT)
def test_the_checks_keep_a_closing_mark_with_its_sentence(text, want):
    assert C.sentences(text + "\n") == want


@pytest.mark.parametrize("text,want", KEPT)
def test_the_rule_is_one_function_both_read(text, want):
    assert [" ".join(x.split()) for x in C.split_sentences(text)] == want
    assert not hasattr(M, "_SPLIT")     # the moves hold no splitter of their own


def test_a_closing_mark_at_a_line_end_keeps_the_sentence_on_its_line():
    s = M.segment('He said "Go."\nThen he left.\n')
    assert [(x.text, x.first, x.last) for x in s] == [('He said "Go."', 1, 1), ("Then he left.", 2, 2)]


# ---------------------------------------------------------------------------
# B. A words-mode cover map counts the file as written
# ---------------------------------------------------------------------------

def test_a_words_mode_cover_map_counts_lines_in_the_file_as_written():
    fab = Value("fabula", {"oes": "emf/1", "id": "emf/x", "name": "x", "nodes": [
        {"id": "E:place/hollins-lane-orchard", "type": "place", "name": "Hollins Lane Orchard",
         "summary": "The orchard on Hollins Lane where the Bramley stands."}]})
    text = "---\ntitle: a short\nby: someone\n---\n\nThe orchard on Hollins Lane keeps the Bramley.\n"
    cm = M.cover_map(fab, Value("short", text))
    assert cm.how == "words"
    assert cm.rows == [("The orchard on Hollins Lane keeps the Bramley.", (6, 6), ["E:place/hollins-lane-orchard"])]
    assert cm.record() == [{"sentence": 1, "lines": "6", "items": ["E:place/hollins-lane-orchard"]}]


# ---------------------------------------------------------------------------
# C. `for each` over a short binds a string
# ---------------------------------------------------------------------------

def test_the_compiler_says_a_shorts_member_is_a_string():
    assert TY.member("short") == "string"


def test_the_python_runtime_binds_a_shorts_lines_as_strings():
    got = members(Value("short", "one\n\nTwo lines here.\nthree\n"))
    assert [(m.type, m.payload) for m in got] == [("string", "one"), ("string", "Two lines here."),
                                                   ("string", "three")]


@pytest.mark.skipif(NODE is None, reason="node is not on PATH: the page's runtime is held to the suite under node")
def test_the_page_runtime_binds_a_shorts_lines_as_strings():
    core = ROOT / "enough" / "static" / "thym" / "core.js"
    script = (f"const T = require({json.dumps(str(core))});"
              "const v = new T.Value('short', 'one\\n\\nTwo lines here.\\nthree\\n');"
              "process.stdout.write(JSON.stringify(T.members(v).map((m) => [m.type, m.payload])));")
    p = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout) == [["string", "one"], ["string", "Two lines here."], ["string", "three"]]
