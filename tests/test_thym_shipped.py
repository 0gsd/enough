"""Every `thym 1` program the round ships, and every `thym 1` block of the specification, compiles against the real
declared moves (design 5, ruling 14; THYM 4.8, 7.5, 8.1, 8.3, 20 to 22).

The text is the synced copy, docs/THYM.md (scripts/sync_specs.py); the draft copy earlier lanes kept under
tests/fixtures/thym/draft-0.6/ is gone. The declarations are the manifests' own (`declarations.load()`), held here to
the text's table of the moves `thym 1` adds or extends (6.3). The shipped programs are defaults/thym/'s, each a block
of the text byte for byte. Nothing here runs a program.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from enough.thym import Refusal
from enough.thym import check as ck
from enough.thym import declarations as dc
from enough.thym import enumerate as en
from enough.thym import parse as ps
from enough.thym import plan as pl

REPO = Path(__file__).resolve().parents[1]
TEXT = REPO / "docs" / "THYM.md"
SHIPPED = REPO / "defaults" / "thym"
#: The programs the round ships (design 5); defaults/thym/ also holds the three thym 0 programs of 0.5.0.
ROUND = ("compile-python", "decompile-prose", "decompile-python", "decompile-verse", "settle", "tighten")


def scratch_decls() -> dc.Declarations:
    """The real declarations (the name is kept from the days the round's moves were declared here in scratch)."""
    return dc.load()


def _table_rows() -> list[tuple[str, ...]]:
    text = TEXT.read_text(encoding="utf-8")
    part = text[text.index("The moves `thym 1` adds or extends."):text.index("`propose` is Ascribe's:")]
    return [m.groups() for m in re.finditer(r"^\| `([a-z-]+)` \| (.*?) \| (.*?) \| (.*?) \| (.*?) \|$", part, re.M)]


def test_the_real_declarations_are_the_texts_table_of_thym_1_moves():
    """Each row of 6.3's second table is a real declaration's `thym 1` view: its contract (where the row names one
    list), whether it asks, its scaffold; the three rows that choose by the call are held to their `-when` rules."""
    d = dc.load()
    rows = _table_rows()
    assert len(rows) == 20
    for name, _sig, asks, contract, scaffold in rows:
        v = d[name].view(1)
        assert v is not None, name
        assert v.asks is asks.startswith("yes"), name
        if "·" not in contract and "as above" not in contract:
            assert list(v.contract) == re.findall(r"`([a-z-]+)`", contract), name
        if "·" not in scaffold:
            want = re.findall(r"`([a-z-]+)`", scaffold)
            assert ([v.scaffold] if v.scaffold else []) == want, name
    derive, tell = d["derive"].view(1), d["tell"].view(1)
    assert dc.chosen(derive, as_word="code")["contract"] == ("code-span", "outline-cited", "coverage",
                                                             "terms-grounded", "stance-closed", "fabula-checks",
                                                             "provenance")
    assert dc.chosen(derive, first_type="folder")["contract"] == ("fold-grounded", "atem-shape", "licence-recorded",
                                                                  "fabula-checks", "provenance")
    assert dc.chosen(tell, as_word="code")["contract"] == ("parses", "interfaces-present", "files-present", "footer",
                                                           "provenance")
    assert dc.chosen(tell, as_word="manual")["contract"] == ("coverage", "no-invention", "uses-told", "footer",
                                                             "provenance")
    assert dc.chosen(tell, as_word="code")["gives"] == ("folder",)
    assert {n for n in d if d[n].since >= 1} == {r[0] for r in rows} - {"derive", "tell", "count", "words"}


def compile_with(text: str, decls: dc.Declarations, path: str | None = None):
    """Parse with the names a program of the text's version sees in `decls` (and its own move blocks), and check."""
    version = 1 if re.search(r"^\s*thym 1\s*$", text, re.M) else 0
    moves = set(decls.view(version)) | set(ps._MOVE_LINE.findall(text))
    m = ps.parse(text, path=path, moves=moves)
    return m if isinstance(m, Refusal) else ck.check(m, decls=decls)


def blocks(text: str) -> list[tuple[int, str]]:
    """Every ```thym block of a markdown text: (its line, its text)."""
    out, lines = [], text.split("\n")
    i = 0
    while i < len(lines):
        if lines[i].strip() == "```thym":
            j = i + 1
            while lines[j].strip() != "```":
                j += 1
            out.append((i + 1, "\n".join(lines[i + 1:j]) + "\n"))
            i = j
        i += 1
    return out


DRAFT_BLOCKS = [(ln, b) for ln, b in blocks(TEXT.read_text(encoding="utf-8")) if b.startswith("thym 1\n")]


def _first_name(text: str) -> str:
    mt = re.search(r"^(program|contract)\s+([a-z][a-z0-9-]*)", text, re.M)
    return mt.group(2) if mt else "?"


@pytest.mark.parametrize("line, text", DRAFT_BLOCKS, ids=[f"L{ln}-{_first_name(b)}" for ln, b in DRAFT_BLOCKS])
def test_every_thym_1_block_of_the_text_compiles(line, text):
    r = compile_with(text, scratch_decls())
    assert not isinstance(r, Refusal), f"the block at line {line} of docs/THYM.md: {r}"


def test_folder_outline_compiles_as_the_text_now_writes_it():
    """The text's folder-outline (8.3), mended by the errata pass (a list of one type): recursion under depth and
    the collect node, as written."""
    text = next(b for _, b in DRAFT_BLOCKS if _first_name(b) == "folder-outline")
    c = compile_with(text, scratch_decls())
    assert not isinstance(c, Refusal), str(c)
    plan = pl.plan(c, [{"name": "d", "type": "folder", "path": "tool", "sha256": "1" * 64, "files": 7, "bytes": 1}])
    node = next(n for n in plan["nodes"] if n["type"] == "node")
    assert node["name"] == "tree-of d" and node["budget"] == {"attempts": 1, "output_words": 0, "depth": 12}
    assert c.module.features[0][1] == "the type folder"
    assert any(f[1] == "a move that calls itself (move tree-of)" for f in c.module.features), c.module.features


def test_the_draft_holds_the_blocks_this_round_names():
    names = sorted(_first_name(b) for _, b in DRAFT_BLOCKS)
    assert names == sorted(["plain-enough", "aims-in-brief", "folder-outline", "python-files", "decompile-verse",
                            "its-own-file", "compile-python", "shorter", "drop-the-todos", "decompile-prose",
                            "settle-the-answers"]), names


SHIPPED_FILES = [SHIPPED / f"{n}.thym" for n in ROUND]


@pytest.mark.parametrize("path", SHIPPED_FILES, ids=[p.stem for p in SHIPPED_FILES])
def test_every_shipped_program_compiles_plans_and_enumerates(path):
    """Design 5: decompile-python (five programs), compile-python, decompile-prose, decompile-verse, settle and tighten,
    as the text has them, each a block of the text byte for byte."""
    text = path.read_text(encoding="utf-8")
    assert text in [b for _, b in DRAFT_BLOCKS], f"{path.name} is not a block of docs/THYM.md as written"
    d = scratch_decls()
    c = compile_with(text, d, str(path))
    assert not isinstance(c, Refusal), str(c)
    for prog in c.programs():
        plan = pl.plan(c, [{"name": p.name, "type": p.type, "path": f"{p.name}.in", "sha256": "0" * 64}
                           for p in prog.takes], program=prog.name)
        assert not isinstance(plan, Refusal), (prog.name, str(plan))
    vol = en.enumerate_checked(c)
    assert en.compile_volume(vol) == text


def test_the_shipped_programs_are_the_six_of_the_design_and_the_three_of_0_5_0():
    assert sorted(p.stem for p in SHIPPED.glob("*.thym")) == sorted(ROUND + ("open-house", "publish-story",
                                                                             "read-my-way"))


def test_the_shipped_programs_plan_as_the_text_says():
    """The plan shapes the text promises (THYM 7.5, 8.1, 11.1): tighten's loop that collects is one node that calls
    the move that keeps shorter; read-every-file's reading is one collect node over the folder, its members counted;
    raise-the-questions' output node carries what the program keeps."""
    d = scratch_decls()
    c = compile_with((SHIPPED / "tighten.thym").read_text(encoding="utf-8"), d)
    plan = pl.plan(c, [{"name": "s", "type": "short", "path": "s.md", "sha256": "0" * 64}])
    nodes = [n for n in plan["nodes"] if n["type"] == "node"]
    loop = nodes[0]
    assert loop["name"] == "let changes = for each l in lines of s where words l > 30"
    assert (loop["move"], loop["gives"], loop["repeats"], loop["asks"]) == ("for", "changes", True, True)
    assert loop["calls"] == ["lines", "words", "replace", "tightened", "reword"]
    assert loop["keeps"] == ["shorter"] and loop["budget"] == {"attempts": 3, "output_words": 0}
    assert nodes[1]["name"] == "edit s with changes" and nodes[1]["takes"] == ["s", "changes"]
    c = compile_with((SHIPPED / "decompile-python.thym").read_text(encoding="utf-8"), d)
    rows = [{"name": "repo", "type": "folder", "path": "tool", "sha256": "1" * 64, "files": 7, "bytes": 640},
            {"name": "f", "type": "fabula", "path": "f.cosm", "sha256": "0" * 64}]
    plan = pl.plan(c, rows, program="read-every-file")
    node = next(n for n in plan["nodes"] if n.get("move") == "for")
    assert node["members"] == {"at_most": 7} and node["takes"] == ["repo", "f"] and node["gives"] == "readings"
    assert node["keeps"] == ["its-own-file"] and node["calls"] == ["read-file", "derive"]
    plan = pl.plan(c, rows[1:], program="raise-the-questions")
    out = [n for n in plan["nodes"] if n.get("gives") == "g"]
    assert out[0]["keeps"] == ["fabula-checks"]
    items = en.enumerate_checked(c)["nodes"]
    check = next(it for it in items if it["id"] == "P:check/its-own-file")
    assert [p["name"] for p in check["params"]] == ["r", "t"] and check["order"] == 1
    assert check["steps"] == ["P:step/its-own-file.1", "P:step/its-own-file.2"]
    mv = next(it for it in items if it["id"] == "P:move/read-every-file.read-file")
    assert mv["keeps"] == ["its-own-file"]


@pytest.mark.parametrize("depth, words", [("code", "only a fabulac is told as code"),
                                          ("manual", "a catem is told from a fabulac")])
def test_a_fabula_known_to_be_a_fabulap_is_never_told_as_a_fabulacs(depth, words):
    """The flavour as a static note (THYM 20.5): `derive … as verse` gives a fabulap, and `tell` of a fabulac's depth
    is refused at compile (`flavour`); a fabula input's flavour is the run's to find."""
    text = ("thym 1\n\nprogram p\n  takes poem: text\n  gives s: short\n\n  let f = derive poem as verse\n"
            f"  give tell f as {depth}\nend\n")
    if depth == "code":
        text = text.replace("gives s: short", "gives s: folder")
    r = compile_with(text, scratch_decls())
    assert isinstance(r, Refusal) and (r.check, r.line) == ("flavour", 8), r
    assert r.message == f"f is a fabulap, a poem's fabula; {words}"
    ok = compile_with(text.replace("takes poem: text", "takes poem: text, g: fabula").replace(
        f"tell f as {depth}", f"tell g as {depth}"), scratch_decls())
    assert not isinstance(ok, Refusal), ok
