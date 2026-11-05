"""Two grammars, one compiler (THYM 1.3, 4.9, 17.6; design 1, ruling 1 and 6–8).

The version line `thym 0` or `thym 1` switches the tables a file is read by; any other number is refused. A `thym 0`
file that `thym 1` would read is refused with "this needs `thym 1`", naming the first `thym 1` feature and its line
(the second compile only chooses the message). A declaration's `since: 1` hides a move from `thym 0` programs, and
its `thym-1:` mapping is what only `thym 1` programs see. A used file is read by its own version line, and a `thym 0`
program may not use a `thym 1` file. `emf-checks` and `fabula-checks` are one check. Scratch manifests and files go
into tmp_path; nothing here touches ~/enough.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from enough import macrocosm as mc
from enough import thym
from enough.thym import Refusal
from enough.thym import check as ck
from enough.thym import checks as C
from enough.thym import declarations as dc
from enough.thym import enumerate as en
from enough.thym import parse as ps
from enough.thym import plan as pl
from enough.thym.values import Value, guess_type, is_fabula

REPO = Path(__file__).resolve().parents[1]
SUITE = REPO / "tests" / "fixtures" / "thym"


def compile_text(text: str, *, path: str | None = None, decls=None):
    m = ps.parse(text, path=path)
    return m if isinstance(m, Refusal) else ck.check(m, decls=decls)


def ok(text: str, **kw):
    r = compile_text(text, **kw)
    assert not isinstance(r, Refusal), str(r)
    return r


def refused(text: str, **kw) -> Refusal:
    r = compile_text(text, **kw)
    assert isinstance(r, Refusal), "compiled, and it must be refused"
    return r


def prog(version: int, body: str, takes: str = "t: text", gives: str = "n: number", give: str = "give words t") -> str:
    return f"thym {version}\n\nprogram p\n  takes {takes}\n  gives {gives}\n{body}  {give}\nend\n"


# ---------------------------------------------------------------------------
# The version line
# ---------------------------------------------------------------------------

def test_the_version_line_names_one_of_two_grammars():
    assert ok(prog(0, "")).module.version == 0
    assert ok(prog(1, "")).module.version == 1
    r = refused(prog(2, ""))
    assert (r.check, r.line, r.message) == ("version", 1, "this compiler reads thym 0 and thym 1, and the file says "
                                                          "thym 2")
    r = refused("program p\nend\n")
    assert (r.check, r.message) == ("version", "the first line must be the version line, `thym 0` or `thym 1`")
    assert ps.GRAMMARS[0] is ps.THYM0 and ps.grammar(1) is ps.THYM1


def test_the_tables_of_the_two_grammars():
    zero, one = ps.THYM0, ps.THYM1
    assert one.keywords - zero.keywords == {"keep", "keeps", "contract", "depth", "before", "after"}
    assert one.head_words == zero.head_words + ("keeps", "depth")
    assert one.block_words == zero.block_words + ("contract",)
    assert one.modifier_words == zero.modifier_words + ("before", "after")
    assert set(one.types) - set(zero.types) == {"folder", "line", "change"}
    assert not zero.features and one.admits("side-call")


@pytest.mark.parametrize("name", sorted(p.stem for p in SUITE.glob("programs/*.thym")))
def test_a_thym_0_program_relabelled_thym_1_plans_and_enumerates_the_same(name, tmp_path):
    """Every program of the suite is valid `thym 1` too, and compiles the same way under it: the same plan nodes and
    the same items, but for the version line in `front` and the file's digest."""
    src = SUITE / "programs" / f"{name}.thym"
    text = src.read_text(encoding="utf-8")
    assert text.startswith("thym 0\n")
    other = tmp_path / src.name
    other.write_text("thym 1\n" + text[len("thym 0\n"):], encoding="utf-8")
    want = mc.yaml_load(mc.read_text(SUITE / "expected" / name / "plan.cosm"))
    a, b = (pl.plan(thym.check_file(p), want["inputs"]) for p in (src, other))
    assert a["nodes"][1:] == b["nodes"][1:]
    ia, ib = en.enumerate_file(src), en.enumerate_file(other)
    assert ia["nodes"] == ib["nodes"] and ib["front"] == ia["front"].replace("thym 0", "thym 1", 1)


# ---------------------------------------------------------------------------
# "this needs `thym 1`"
# ---------------------------------------------------------------------------

def test_a_call_in_a_condition_without_parentheses_needs_thym_1():
    body = "  assert words t > 0\n"
    r = refused(prog(0, body))
    assert (r.stage, r.check, r.line) == ("compile", "version", 6)
    assert r.message == ("this needs `thym 1`: a call in a condition without parentheses (words t) at line 6; the "
                         "first line says thym 0")
    checked = ok(prog(1, body))
    assert checked.module.features == [(6, "a call in a condition without parentheses (words t)")]
    ok(prog(0, "  assert (words t) > 0\n"))


def test_a_call_on_either_side_and_where_it_ends():
    ok(prog(1, "  assert words t < words t or count [t] is 1\n"))
    ok(prog(1, "  if not words t > 3 then\n    assert words t > 0\n  end\n"))
    # `in` after a move that declares no `in` modifier is membership: parentheses for the call are not needed
    ok(prog(1, "  assert words t in [1, 2]\n"))
    # a field that shares a move's name is still a field: nothing that begins an operand follows it
    ok(prog(1, "  for each o in h where count is 3\n    emit o\n  end\n", takes="h: volume", gives="i: volume",
            give="give project h as isotype"))


def test_a_refusal_thym_1_shares_stands_as_thym_0_said_it():
    """The second compile only chooses the message: a file `thym 1` refuses too keeps its `thym 0` refusal."""
    r = refused(prog(0, "  assert words t > 0\n  let x = nowhere\n"))
    assert (r.check, r.line) == ("parse", 6) and "goes in parentheses" in r.message
    for p in sorted((SUITE / "bad").glob("*.thym")):
        first = p.read_text(encoding="utf-8").split("\n", 1)[0]
        r = compile_text(p.read_text(encoding="utf-8"), path=str(p))
        assert isinstance(r, Refusal) and f"{r.stage} {r.check} line {r.line}" in first, (p.name, str(r))


def test_thym_0_keeps_its_own_words_free():
    """`keeps` begins a prose line in `thym 0` as before, and `keep`, `contract` and `depth` are names there."""
    text = ("thym 0\n\nprogram p\n  why: one line\n       keeps going.\n  takes t: text\n  gives n: number\n"
            "  let keep = words t\n  let contract = keep\n  give contract\nend\n")
    checked = ok(text)
    assert checked.programs()[0].why.text == "one line keeps going."
    assert refused(text.replace("thym 0", "thym 1", 1)).check == "parse"


@pytest.mark.parametrize("body, what", [
    ("  let k = for each x in [t]\n    keep x\n  end\n", "keep"),
    ("  contract c(x: text)\n  end\n", "contract"),
])
def test_thym_1_syntax_not_read_yet_is_refused_saying_so(body, what):
    r = refused(prog(1, body))
    assert r.check == "parse" and "this compiler does not read yet" in r.message, str(r)


def test_a_type_not_read_yet_is_refused_saying_so():
    r = refused("thym 1\n\nprogram p\n  takes repo: folder\n  gives n: number\n  give 0\nend\n")
    assert (r.check, r.line) == ("parse", 4) and r.message.startswith("`folder` begins the type folder")
    r = refused("thym 0\n\nprogram p\n  takes repo: folder\n  gives n: number\n  give 0\nend\n")
    assert (r.check, r.line) == ("parse", 4) and r.message.startswith("`folder` is not a type")


# ---------------------------------------------------------------------------
# since, thym-1 and the views
# ---------------------------------------------------------------------------

SIDECAR = """moves-of: testing/1
moves:
  - {name: survey, takes: [text], gives: fabula, since: 1, contract: [fabula-checks]}
  - {name: derive-two, takes: [text], gives: fabula, contract: [coverage, emf-checks],
     thym-1: {contract: [coverage, fabula-checks]}}
  - {name: tell-two, takes: [fabula], gives: short, modifiers: {as: order},
     thym-1: {modifiers: {as: "order | code"}}}
  - {name: count-two, takes: [volume], gives: number, thym-1: {takes: ["volume | text"]}}
  - {name: broken, takes: [text], gives: number, since: 7}
"""


@pytest.fixture
def scratch_decls(tmp_path):
    d = tmp_path / "manifests"
    d.mkdir()
    for p in mc.DEFAULT_MANIFEST_DIR.glob("*.cosm"):
        shutil.copy(p, d / p.name)
    (d / "testing.moves.cosm").write_text(SIDECAR, encoding="utf-8")
    return dc.load(mc.Registry([d]))


def test_since_and_thym_1_are_read_into_two_views(scratch_decls):
    d = scratch_decls
    assert "broken" not in d and any("since names a grammar version" in p for p in d.problems)
    assert d["survey"].since == 1 and d["survey"].view(0) is None and d["survey"].view(1).name == "survey"
    two = d["derive-two"]
    assert two.contract == ("coverage", "emf-checks")                       # as written: the thym 0 keys
    assert two.view(0).contract == ("coverage", "emf-checks")
    assert two.view(1).contract == ("coverage", "fabula-checks")
    assert two.view(1).frozen_view().contract == ("coverage", "emf-checks")
    assert two.view(1).view(0) == two.view(0)
    zero, one = d.view(0), d.view(1)
    assert "survey" not in zero and "survey" in one and isinstance(zero, dc.Declarations)
    assert dc.view_of({"name": "x", "since": 1}, 0) is None
    assert dc.view_of({"name": "x", "contract": ["a"], "thym-1": {"contract": ["b"]}}, 1)["contract"] == ["b"]
    assert "survey" not in dc.names(version=0) or dc.load()["survey"].since == 0


def test_a_move_only_thym_1_sees_is_free_in_thym_0_and_needs_thym_1_when_called(scratch_decls):
    d = scratch_decls
    ok(prog(0, "  let survey = words t\n"), decls=d)                       # a name, not a reserved move, in thym 0
    r = refused(prog(1, "  let survey = words t\n"), decls=d)
    assert r.check == "type"                                                 # reserved: thym 1 sees the move
    text = prog(0, "  let f = survey t\n", give="give words t")
    r = refused(text, decls=d)
    assert (r.check, r.line) == ("version", 6)
    assert r.message == "this needs `thym 1`: the move survey, which thym 1 declares at line 6; the first line says thym 0"
    ok(text.replace("thym 0", "thym 1", 1), decls=d)


def test_a_word_or_an_operand_only_the_thym_1_view_takes_needs_thym_1(scratch_decls):
    d = scratch_decls
    text = prog(0, "  let f = derive-two t\n  let s = tell-two f as code\n", gives="s2: short", give="give s")
    r = refused(text, decls=d)
    assert (r.check, r.line) == ("version", 7)
    assert "the word code after as of tell-two, which thym 1 adds at line 7" in r.message
    ok(prog(0, "  let f = derive-two t\n  let s = tell-two f as told\n", gives="s2: short", give="give s"), decls=d)
    r = refused(prog(0, "  let n = count-two t\n", give="give n"), decls=d)
    assert r.check == "version" and "count-two t (a text), which thym 1 allows at line 6" in r.message


def test_the_contract_a_step_lists_is_spelled_by_its_view(scratch_decls):
    """Ruling 7: a `thym 0` enumeration keeps `emf-checks` (the frozen view); a `thym 1` one says `fabula-checks`."""
    d = scratch_decls
    for version, word in ((0, "emf-checks"), (1, "fabula-checks")):
        vol = en.enumerate_text(prog(version, "  let f = derive-two t\n", gives="g: fabula", give="give f"), decls=d)
        assert not isinstance(vol, Refusal), vol
        lists = [it.get("checks") for it in vol["nodes"] if str(it.get("id", "")).startswith("P:contract/")]
        assert ["coverage", word] in lists, lists


def test_the_shipped_derive_keeps_emf_checks_in_thym_0():
    items = mc.yaml_load(mc.read_text(SUITE / "expected" / "publish-story" / "items.cosm"))
    assert any("emf-checks" in (it.get("checks") or []) for it in items["nodes"])


# ---------------------------------------------------------------------------
# use across versions
# ---------------------------------------------------------------------------

LIB0 = "thym 0\n\nmove len(x: text): number\n  give words x\nend\n"
LIB1 = "thym 1\n\nmove long(x: text): bool\n  assert words x > 0\n  give true\nend\n"


def test_use_reads_each_file_by_its_own_version_line(tmp_path):
    (tmp_path / "lib0.thym").write_text(LIB0, encoding="utf-8")
    (tmp_path / "lib1.thym").write_text(LIB1, encoding="utf-8")
    main = tmp_path / "main.thym"
    use0 = "use lib0.thym\n\nprogram p\n  takes t: text\n  gives n: number\n  give len t\nend\n"
    use1 = "use lib1.thym\n\nprogram p\n  takes t: text\n  gives n: number\n  assert (long t)\n  give words t\nend\n"
    for version in (0, 1):
        main.write_text(f"thym {version}\n" + use0, encoding="utf-8")
        assert not isinstance(thym.check_file(main), Refusal)
    main.write_text("thym 1\n" + use1, encoding="utf-8")
    checked = thym.check_file(main)
    assert not isinstance(checked, Refusal), checked
    main.write_text("thym 0\n" + use1, encoding="utf-8")
    r = thym.check_file(main)
    assert isinstance(r, Refusal) and (r.check, r.line) == ("version", 2)
    assert r.message == "use lib1.thym brings a thym 1 file into a thym 0 program; this needs `thym 1`"


def test_a_used_thym_0_file_with_thym_1_syntax_is_told_so_in_its_own_name(tmp_path):
    (tmp_path / "lib.thym").write_text(LIB1.replace("thym 1", "thym 0", 1), encoding="utf-8")
    main = tmp_path / "main.thym"
    main.write_text("thym 1\nuse lib.thym\n\nprogram p\n  takes t: text\n  gives n: number\n  give words t\nend\n",
                    encoding="utf-8")
    r = thym.check_file(main)
    assert isinstance(r, Refusal) and r.check == "version" and r.line == 4 and r.file.endswith("lib.thym")


# ---------------------------------------------------------------------------
# fabula-checks and the fabula predicate
# ---------------------------------------------------------------------------

def test_emf_checks_and_fabula_checks_are_one_check():
    assert C.CHECKS.lookup("emf-checks") is C.CHECKS.lookup("fabula-checks") is not None
    nothing = Value("string", "not a volume")
    assert C.verdict("emf-checks", nothing, {}, {}, None) == C.verdict("fabula-checks", nothing, {}, {}, None)


def test_a_fabula_is_fabula_1_or_emf_1(tmp_path):
    assert is_fabula("fabula/1") and is_fabula("emf/1")
    assert not is_fabula("emf/2") and not is_fabula("thym/1") and not is_fabula(None)
    for decl in ("fabula/1", "emf/1"):
        p = tmp_path / f"{decl.replace('/', '-')}.cosm"
        p.write_text(f"oes: {decl}\nid: x\nname: x\nnodes: []\n", encoding="utf-8")
        assert guess_type(p) == "fabula"
