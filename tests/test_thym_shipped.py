"""Every `thym 1` program the round ships, and every `thym 1` block of the 0.6 draft of the specification, compiles
(design 5, ruling 14; THYM 4.8, 7.5, 8.1, 8.3, 20 to 22).

The moves those programs call do not exist yet (`survey`, `history`, `gather`, `question`, `record`, `settle`, the
editor's moves, `join`, `say`, `folders`; `derive`, `tell`, `count` and `words` extended): the move lanes write them.
So the programs compile here against scratch declarations of those moves, with the signatures of the design's table
(3.2), read by the compiler's own reader into the declarations every other move has. The draft of the text is a copy
kept under `tests/fixtures/thym/draft-0.6/` (`thym-0.6-draft.md`); its `thym 1` blocks are read from it here, and the
shipped programs, as the text has them, are files beside it. Nothing here runs a program.
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
DRAFT = REPO / "tests" / "fixtures" / "thym" / "draft-0.6"
TEXT = DRAFT / "thym-0.6-draft.md"
SHIPPED = DRAFT / "programs"

#: The design's table (3.2), as declarations: the moves the round adds (each `since: 1`) and the four it extends (their
#: additions under `thym-1:`). Scratch: the move lanes write the real ones in the manifests.
NEW = [
    {"name": "survey", "takes": ["folder"], "gives": "fabula", "since": 1,
     "contract": ["files-found", "code-span", "licence-recorded", "fabula-checks", "provenance"]},
    {"name": "history", "takes": ["folder"], "gives": "fabula", "modifiers": {"with": "fabula"}, "since": 1,
     "contract": ["history-grounded", "fabula-checks", "provenance"]},
    {"name": "gather", "takes": ["list of fabula | list of item"], "gives": "same-as-with",
     "modifiers": {"with": "fabula | volume"}, "since": 1,
     "contract": ["nothing-lost", "ids-unique", "fabula-checks", "provenance"]},
    {"name": "question", "takes": ["fabula | volume"], "gives": "list of item", "asks": True, "scaffold": "bank",
     "since": 1, "contract": ["addressed", "no-duplicate", "provenance"]},
    {"name": "record", "takes": ["volume"], "gives": "same-as-in", "modifiers": {"in": "fabula | volume"},
     "since": 1, "contract": ["addressed", "only-the-asked", "provenance"]},
    {"name": "settle", "takes": ["fabula | volume"], "gives": "fabula | volume", "asks": True, "scaffold": "direct",
     "since": 1, "contract": ["addressed", "only-the-asked", "fabula-checks", "provenance"]},
    {"name": "lines", "takes": [], "gives": "list of line", "modifiers": {"of": "text | short"}, "since": 1},
    {"name": "replace", "takes": ["line"], "gives": "change", "modifiers": {"with": "string | line | short"},
     "since": 1},
    {"name": "drop", "takes": ["line"], "gives": "change", "since": 1},
    {"name": "insert", "takes": ["string | line | short"], "gives": "change",
     "modifiers": {"before": "line", "after": "line"}, "since": 1},
    {"name": "edit", "takes": ["text | short"], "gives": "text | short", "modifiers": {"with": "list of change"},
     "since": 1, "contract": ["only-the-changed", "never-source", "provenance"]},
    {"name": "reword", "takes": ["line | string | short"], "gives": "line | string | short",
     "modifiers": {"to": "words", "with": "morph"}, "asks": True, "since": 1,
     "contract": ["length", "one-line", "nothing-added", "provenance"]},
    {"name": "join", "takes": ["list of string | list of line | list of short"], "gives": "short",
     "modifiers": {"with": "string"}, "since": 1, "contract": ["provenance"]},
    {"name": "say", "takes": ["number | date | word | bool | string"], "gives": "string", "since": 1},
    {"name": "folders", "takes": [], "gives": "list of folder", "modifiers": {"of": "folder"}, "since": 1},
]
CHANGED = {
    "derive": {"thym-1": {"takes": ["text | folder"], "modifiers": {"as": "prose | verse | code", "with": "fabula"},
                          "contract": ["span-resolves", "stance-closed", "terms-grounded", "coverage", "fabula-checks",
                                       "provenance"],
                          "contract-when": [
                              {"as": ["code"], "contract": ["code-span", "outline-cited", "coverage", "terms-grounded",
                                                            "stance-closed", "fabula-checks", "provenance"]},
                              {"takes": "folder", "contract": ["fold-grounded", "atem-shape", "licence-recorded",
                                                               "fabula-checks", "provenance"]}]}},
    "tell": {"thym-1": {"modifiers": {"as": "order | code | line | overview | manual", "by": "order",
                                      "with": "morph"},
                        "gives-when": [{"as": ["code"], "gives": "folder"}]}},
    "count": {"thym-1": {"takes": ["volume | fabula | short | list | folder"]}},
    "words": {"thym-1": {"takes": ["text | short | atem | line | string"]}},
}


def scratch_decls() -> dc.Declarations:
    """The bundled declarations, with the round's moves declared (scratch) by the compiler's own reader."""
    base = dc.load()
    out = base.copy()
    problems: list[str] = []
    for entry in NEW:
        d = dc._decl("thym", dict(entry), "scratch.moves.cosm", problems)
        assert d is not None, problems
        out[entry["name"]] = d
    for name, extra in CHANGED.items():
        old = base[name]
        entry = {"name": name, "takes": [" | ".join(a) for a in old.takes], "gives": " | ".join(old.gives),
                 "modifiers": {k: " | ".join(v) for k, v in old.modifiers.items()}, "asks": old.asks,
                 "contract": list(old.contract), **({"scaffold": old.scaffold} if old.scaffold else {}), **extra}
        d = dc._decl(old.owner, entry, "scratch.moves.cosm", problems)
        assert d is not None, problems
        out[name] = d
    return out


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


#: Blocks of the draft that do not compile, and why: a fault in the text, for the editor (docs/fabula-landed-T1c.md).
#: When the text is mended, its block compiles and this test says so.
TEXT_FAULTS = {
    "folder-outline": ("type", "a list holds values of one type; [d.path, (join below)] mixes short, string"),
}


@pytest.mark.parametrize("line, text", DRAFT_BLOCKS, ids=[f"L{ln}-{_first_name(b)}" for ln, b in DRAFT_BLOCKS])
def test_every_thym_1_block_of_the_draft_compiles(line, text):
    r = compile_with(text, scratch_decls())
    fault = TEXT_FAULTS.get(_first_name(text))
    if fault is not None:
        assert isinstance(r, Refusal) and (r.check, r.message) == fault, f"the block at line {line} now: {r}"
        return
    assert not isinstance(r, Refusal), f"the block at line {line} of the draft: {r}"


def test_folder_outline_compiles_once_its_list_holds_one_type():
    """The fault in the text's folder-outline (8.3) is its list `[d.path, (join below)]`, a string and a short; with
    both shorts the program compiles, recursion, depth and the collect node included."""
    text = next(b for _, b in DRAFT_BLOCKS if _first_name(b) == "folder-outline")
    mended = text.replace("give join [d.path, (join below)]", "give join [(join [d.path]), (join below)]")
    c = compile_with(mended, scratch_decls())
    assert not isinstance(c, Refusal), str(c)
    plan = pl.plan(c, [{"name": "d", "type": "folder", "path": "tool", "sha256": "1" * 64, "files": 7, "bytes": 1}])
    node = next(n for n in plan["nodes"] if n["type"] == "node")
    assert node["name"] == "tree-of d" and node["budget"] == {"attempts": 1, "output_words": 0, "depth": 12}
    assert c.module.features[0][1] == "the type folder"
    assert any(f == (9, "a move that calls itself (move tree-of)") for f in c.module.features), c.module.features


def test_the_draft_holds_the_blocks_this_round_names():
    names = sorted(_first_name(b) for _, b in DRAFT_BLOCKS)
    assert names == sorted(["plain-enough", "aims-in-brief", "folder-outline", "python-files", "decompile-verse",
                            "its-own-file", "compile-python", "shorter", "drop-the-todos", "decompile-prose",
                            "settle-the-answers"]), names


SHIPPED_FILES = sorted(SHIPPED.glob("*.thym"))


@pytest.mark.parametrize("path", SHIPPED_FILES, ids=[p.stem for p in SHIPPED_FILES])
def test_every_shipped_program_compiles_plans_and_enumerates(path):
    """Design 5: decompile-python (five programs), compile-python, decompile-prose, decompile-verse, settle and tighten,
    as the text has them, each a block of the draft byte for byte."""
    text = path.read_text(encoding="utf-8")
    assert text in [b for _, b in DRAFT_BLOCKS], f"{path.name} is not a block of the draft as written"
    d = scratch_decls()
    c = compile_with(text, d, str(path))
    assert not isinstance(c, Refusal), str(c)
    for prog in c.programs():
        plan = pl.plan(c, [{"name": p.name, "type": p.type, "path": f"{p.name}.in", "sha256": "0" * 64}
                           for p in prog.takes], program=prog.name)
        assert not isinstance(plan, Refusal), (prog.name, str(plan))
    vol = en.enumerate_checked(c)
    assert en.compile_volume(vol) == text


def test_the_shipped_programs_are_the_six_of_the_design():
    assert [p.stem for p in SHIPPED_FILES] == ["compile-python", "decompile-prose", "decompile-python",
                                               "decompile-verse", "settle", "tighten"]


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
