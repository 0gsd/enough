"""The Lean reader (`enough.lean_reader`): Lean 4 read as text, by rule, never built (design
docs/v090-fabulam-design.md, section 3; MacroCOSM OES 18.4.10).

The syntax cases are in a Lean file of our own (`tests/fixtures/fabula/fabulam/reader_cases.lean`), read as text and
never built. The reach is checked on a hand-made graph whose dominator tree is stated below. The tests against
Mathlib read the clone at `fabulac-test-repos/mathlib4` as text and skip when it is absent; nothing of it is copied.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from enough import languages as L
from enough import lean_reader as LR
from enough import macrocosm as mc
from enough import repo_engine as RE
from enough.thym import engines as EN

REPO = Path(__file__).resolve().parents[1]
CASES = REPO / "tests" / "fixtures" / "fabula" / "fabulam" / "reader_cases.lean"
CASES_PATH = "reader_cases.lean"
MATHLIB = Path("/Users/m3u/METMcloud/fabulac-test-repos/mathlib4")
needs_mathlib = pytest.mark.skipif(not (MATHLIB / "Mathlib").is_dir(), reason="no Mathlib clone beside this repository")


@pytest.fixture(scope="module")
def cases() -> dict:
    out = LR.outline(CASES_PATH, CASES.read_text(encoding="utf-8"))
    assert out["ok"] is True
    return out


def _def(ol: dict, qual: str) -> dict:
    got = [d for d in ol["defs"] if d["qual"] == qual]
    assert len(got) == 1, qual
    return got[0]


def _ref(d: dict, name: str) -> dict:
    got = [r for r in d["refs"] if r["name"] == name]
    assert len(got) == 1, (d["qual"], name, d["refs"])
    return got[0]


def _plain(x):
    """No float anywhere, and every key a string: the record stays small and portable."""
    if isinstance(x, dict):
        assert all(isinstance(k, str) for k in x)
        for v in x.values():
            _plain(v)
    elif isinstance(x, list):
        for v in x:
            _plain(v)
    else:
        assert x is None or isinstance(x, (str, int, bool)), x


# ---------------------------------------------------------------------------
# The file of our own
# ---------------------------------------------------------------------------

def test_the_fixture_says_it_is_read_as_text_only():
    first = CASES.read_text(encoding="utf-8").splitlines()[0]
    assert first.startswith("--") and "read as text only" in first and "never built" in first


def test_the_header_the_module_system_imports_and_doc(cases):
    assert cases["language"] == "lean" and cases["lines"] == 144 and cases["module-system"] is True
    assert cases["doc"] == "Cases for the Lean reader"
    assert cases["imports"] == [
        {"module": "Mathlib.Data.Nat.Basic", "line": 8, "public": True, "meta": False, "all": False},
        {"module": "Mathlib.Logic.Basic", "line": 9, "public": False, "meta": False, "all": True}]
    kinds = [(c["kind"], c["line"], c["end"]) for c in cases["comments"]]
    assert kinds[:3] == [("inline", 1, 1), ("header", 2, 5), ("module-note", 11, 15)]   # the nested /- -/ inside
    _plain(cases)


def test_comments_strings_and_character_literals(cases):
    lines = {c["line"] for c in cases["comments"]}
    assert 27 not in lines                                  # `--` and `/-` inside a string are not comments
    g = _def(cases, "Reader.Cases.greeting")
    assert (g["line"], g["end"], g["proof"]) == (26, 27, "term") and g["refs"] == []
    assert g["note"] == {"line": 25, "end": 25}
    p = _def(cases, "Reader.Cases.letter'")                   # a prime in a name, '\'' a character
    assert p["name"] == "letter'" and p["refs"] == []
    run = [c for c in cases["comments"] if c["line"] == 133][0]
    assert (run["kind"], run["end"]) == ("inline", 134)       # two `--` lines with nothing between: one comment
    inside = [c for c in cases["comments"] if c["line"] == 136][0]
    assert inside["on"] == "Reader.Cases.term_proof"
    notes = {c["on"] for c in cases["comments"] if c["kind"] == "note"}
    assert "Reader.Cases.uses_strict" in notes


def test_names_unicode_guillemets_root_and_namespaces(cases):
    assert _def(cases, "Reader.Cases.«odd name»")["refs"] == []           # χ₈ is a binder
    assert _def(cases, "Reader.Cases.hp₁_le")["signature"] == "hp₁_le {a b : ℕ} (hp₁ : a ≤ b) : a ≤ b + 1"
    assert _def(cases, "top_level")["name"] == "_root_.top_level"
    assert _def(cases, "Reader.Cases.Inner.Deep.deep_fact")["kind"] == "theorem"   # namespace A.B
    assert _def(cases, "Reader.Cases.greeting")["qual"] == "Reader.Cases.greeting"  # a section adds nothing
    assert [n["name"] for n in cases["namespaces"]][:2] == ["Reader.Cases", "Reader.Cases.Inner.Deep"]
    d = _def(cases, "Reader.Cases.hp₁_le")
    assert d["digest"] == __import__("hashlib").sha256(d["signature"].encode()).hexdigest()[:16]


def test_strict_binders_mutual_axiom_sorry_and_native_decide(cases):
    assert _ref(_def(cases, "Reader.Cases.uses_strict"), "hp₁_le")["to"] == "Reader.Cases.hp₁_le"
    ev, od = _def(cases, "Reader.Cases.evenish"), _def(cases, "Reader.Cases.oddish")     # inside mutual … end
    assert _ref(ev, "oddish")["to"] == "Reader.Cases.oddish" and _ref(od, "evenish")["to"] == "Reader.Cases.evenish"
    assert cases["axioms"] == ["Reader.Cases.an_axiom"] and _def(cases, "Reader.Cases.an_axiom")["proof"] == "none"
    assert cases["sorry"] == 1 and _def(cases, "Reader.Cases.not_yet")["sorry"] == 1
    assert cases["native-decide"] == 1
    assert _def(cases, "Reader.Cases.tactic_proof")["proof"] == "tactic"
    assert _def(cases, "Reader.Cases.term_proof")["proof"] == "term"
    assert _def(cases, "Reader.Cases.helper")["automation"] == ["simp"]


def test_attributes_modifiers_and_scope(cases):
    h = _def(cases, "Reader.Cases.helper")
    assert h["attributes"] == ["simp"] and h["modifiers"] == ["private"] and h["line"] == 97   # @[simp] above
    assert h["scope"] == [{"line": 91, "end": 91}, {"line": 96, "end": 96}]                     # variable; omit … in
    assert _def(cases, "Reader.Cases.pos_succ")["scope"] == [{"line": 91, "end": 91}, {"line": 93, "end": 93}]
    assert _def(cases, "Reader.Cases.uses_helper")["scope"] == [{"line": 91, "end": 91}]
    assert _def(cases, "Reader.Cases.with_option")["line"] == 114                                 # after set_option … in
    old = _def(cases, "Reader.Cases.old_name")
    assert (old["kind"], old["attributes"]) == ("alias", ["deprecated"])


def test_the_names_declarations_make(cases):
    assert _def(cases, "Reader.Cases.Point")["generates"] == [
        "Reader.Cases.Point.x", "Reader.Cases.Point.y", "Reader.Cases.Point.mk'"]
    assert _def(cases, "Reader.Cases.Colour")["generates"] == ["Reader.Cases.Colour.red", "Reader.Cases.Colour.green"]
    both = [d for d in cases["defs"] if d["kind"] == "alias" and d["name"] == ""][0]
    assert both["generates"] == ["Reader.Cases.forward", "Reader.Cases.backward"]
    assert _def(cases, "Reader.Cases.mul_twice")["generates"] == ["Reader.Cases.add_twice"]
    once = _def(cases, "Reader.Cases.mul_once")
    assert once["generates"] == [] and once["generates-unknown"] is True
    assert any("mul_once" in x for x in cases["limits"])
    assert _def(cases, "Reader.Cases.term_proof")["generates"] == ["Reader.Cases.term_proof.same"]


def test_each_how_of_placing_a_name(cases):
    assert _ref(_def(cases, "Reader.Cases.uses_top"), "top_level") == {
        "name": "top_level", "line": 45, "to": "top_level", "how": "exact"}
    assert _ref(_def(cases, "Reader.Cases.uses_deep"), "Inner.Deep.deep_fact")["how"] == "namespace"
    o = _ref(_def(cases, "Reader.Cases.uses_other"), "other_fact")
    assert (o["how"], o["to"]) == ("open", "Reader.Cases.Other.other_fact")
    x = _ref(_def(cases, "Reader.Cases.point_x"), "x")
    assert (x["how"], x["to"], x["dot"]) == ("last-name", "Reader.Cases.Point", True)
    assert _ref(_def(cases, "Reader.Cases.hp₁_le"), "Nat.le_succ_of_le") == {
        "name": "Nat.le_succ_of_le", "line": 38, "to": None, "how": "outside"}
    t = _ref(_def(cases, "Reader.Cases.uses_twin"), "twin")
    assert (t["how"], t["to"], t["candidates"]) == ("ambiguous", None,
                                                    ["Reader.Cases.Left.twin", "Reader.Cases.Right.twin"])
    assert _ref(_def(cases, "Reader.Cases.red_ne"), "Colour.red")["to"] == "Reader.Cases.Colour"   # a made name


def test_opens_hold_until_their_end(cases):
    rows = [(o["names"], o["line"], o["until"], o["hiding"]) for o in cases["opens"]]
    assert rows == [(["Nat"], 21, 144, ["add_comm"]), (["Other"], 61, 62, []), (["Left", "Right"], 72, 73, [])]


def test_an_unclosed_comment_or_string_is_not_read():
    assert LR.outline("x.lean", "theorem t : True := trivial\n/- open\nmore\n") == {
        "ok": False, "language": "lean", "line": 2, "message": "a block comment opened here is never closed"}
    bad = LR.outline("x.lean", 'def s : String :=\n  "never closed\n')
    assert bad["ok"] is False and bad["line"] == 2
    assert LR.outline("x.lean", "/- a /- nested -/ still open\n")["ok"] is False


def test_the_targets_by_rule():
    text = ("namespace T\n\ntheorem step : True := trivial\n\ntheorem main : True := step\n\n"
            "private theorem hidden : True := trivial\n\n@[deprecated (since := \"2026-01-01\")]\n"
            "theorem old : True := trivial\n\nalias main' := main\n\nend T\n")
    assert LR.default_targets(LR.outline("t.lean", text)) == ["T.main"]


# ---------------------------------------------------------------------------
# The reach, on a graph whose dominator tree is known
# ---------------------------------------------------------------------------

def _graph() -> dict:
    # T uses A and B; both use C; C, D, E, F are a chain. With a root above T, T dominates everything; A and B
    # dominate nothing; C dominates D, E, F (every chain to them meets C); D dominates E, F; E dominates F.
    kinds = {"T": "theorem", "A": "theorem", "B": "def", "C": "lemma", "D": "theorem", "E": "lemma", "F": "lemma",
             "I": "instance", "S": "lemma", "N": "lemma"}
    uses = {"T": ["A", "B"], "A": ["C"], "B": ["C"], "C": ["D"], "D": ["E"], "E": ["F"]}
    decls = {k: {"file": "f.lean", "line": i + 1, "kind": v, "attributes": ["simp"] if k == "S" else [],
                 "modifiers": []} for i, (k, v) in enumerate(kinds.items())}
    return {"ok": True, "language": "lean", "decls": decls, "uses": {k: uses.get(k, []) for k in decls},
            "used-by": {}, "outside": {}, "order": ["f.lean"],
            "files": {"f.lean": {"module": "f", "imports": [], "declarations": len(decls)}},
            "targets-by-rule": {"f.lean": ["T", "S", "N"]}}


def test_reach_depth_and_carries_are_the_dominator_tree():
    r = LR.reach(_graph(), ["T"])
    got = {k: (v["reached"], v["depth"], v["carries"]) for k, v in r["decls"].items()}
    assert got == {"T": ("yes", 0, 6), "A": ("yes", 1, 0), "B": ("yes", 1, 0), "C": ("yes", 2, 3),
                   "D": ("yes", 3, 2), "E": ("yes", 4, 1), "F": ("yes", 5, 0), "I": ("perhaps", None, 0),
                   "S": ("perhaps", None, 0), "N": ("no", None, 0)}
    assert (r["reached"], r["target-by"], r["targets"]) == (7, "given", ["T"])
    # the candidates: the target; theorems and lemmas at depth 1 (B is a def); carries >= 3 and >= 2 in a hundred
    assert [(c["name"], c["carries"], c["why"]) for c in r["candidates"]] == [
        ("T", 6, ["target", "carries"]), ("C", 3, ["carries"]), ("A", 0, ["depth-1"])]
    _plain(r)


def test_two_targets_have_a_root_above_both():
    g = _graph()
    g["decls"]["U"] = {"file": "f.lean", "line": 20, "kind": "theorem", "attributes": [], "modifiers": []}
    g["uses"]["U"] = ["C"]
    r = LR.reach(g, ["T", "U"])
    assert r["decls"]["T"]["carries"] == 2 and r["decls"]["U"]["carries"] == 0 and r["decls"]["C"]["carries"] == 3
    assert LR.reach(g, ["T", "nowhere"])["unknown"] == ["nowhere"]


def test_reach_without_targets_takes_the_rule():
    r = LR.reach(_graph())
    assert r["target-by"] == "rule" and r["targets"] == ["T", "S", "N"]


# ---------------------------------------------------------------------------
# The registry and the syntax engine
# ---------------------------------------------------------------------------

def test_the_lean_entry_of_the_registry():
    lean = L.require("lean")
    assert (lean.reads, lean.parses, lean.runs, lean.target) == (True, False, False, False)
    assert (lean.reader, lean.flavour, lean.decompile, lean.compile) == (
        "enough.lean_reader", "fabulam", "decompile-lean.thym", "entail-pshort.thym")
    assert (lean.ground, lean.provides, lean.shelf, lean.names, lean.runtime) == (None, None, None, None, "lean")
    py = L.require("python")
    assert (py.reader, py.flavour) == ("enough.repo_engine", "fabulac")
    assert L.of_path("Mathlib/X.lean") is lean and "lean" not in L.targets()
    assert L.reader("lean") == "enough.lean_reader" and L.flavour("lean") == "fabulam" and L.reader("go") is None


def test_the_syntax_engine_hands_lean_on_to_its_reader():
    text = CASES.read_text(encoding="utf-8")
    assert RE.language("a/b.lean") == "lean"
    assert RE.SYNTAX.outline(CASES_PATH, text) == LR.outline(CASES_PATH, text)
    assert RE.parse("x.lean", text)["ok"] is None                   # Lean is read, never parsed
    assert RE.uses("x.lean", text)["ok"] is None                    # and not grounded
    assert RE.catalogue("lean")["ok"] is None
    assert RE.outline("x.py", "def f():\n    return 1\n")["ok"] is True       # Python still its own reader
    assert RE.SYNTAX.graph({"x.py": RE.outline("x.py", "x = 1\n")})["ok"] is None
    g = RE.SYNTAX.graph({CASES_PATH: RE.outline(CASES_PATH, text)})
    assert g["ok"] is True and g["language"] == "lean"
    r = RE.SYNTAX.reach(g, ["Reader.Cases.uses_strict"])
    assert r["decls"]["Reader.Cases.hp₁_le"] == {"reached": "yes", "depth": 1, "carries": 0}


def test_answers_survive_the_record_a_replay_reads():
    text = CASES.read_text(encoding="utf-8")
    ol = RE.SYNTAX.outline(CASES_PATH, text)
    g = RE.SYNTAX.graph({CASES_PATH: ol})
    r = RE.SYNTAX.reach(g, None)
    for answer in (ol, g, r):
        back = mc.yaml_load(mc.dump({"output": EN._encode(answer)}))["output"]
        assert back == answer
    assert EN.call_digest("syntax.graph", ({CASES_PATH: ol},), {}) == EN.call_digest(
        "syntax.graph", ({CASES_PATH: mc.yaml_load(mc.dump({"o": ol}))["o"]},), {})


def test_outline_graph_and_reach_are_recorded_and_replayed_with_no_reader(tmp_path):
    text = CASES.read_text(encoding="utf-8")
    live = EN.Recording({"syntax": RE.SYNTAX}, tmp_path, lambda: counter)
    counter = EN.CallCounter("n1")
    syn = live["syntax"]
    ol = syn.outline(CASES_PATH, text)
    g = syn.graph({CASES_PATH: ol})
    r = syn.reach(g, ["Reader.Cases.uses_strict"])
    assert sorted(p.name for p in (tmp_path / "candidates").iterdir()) == [
        "n1-e1.1.cosm", "n1-e2.1.cosm", "n1-e3.1.cosm"]
    counter = EN.CallCounter("n1")
    rep = EN.Replaying(tmp_path, ["syntax"], lambda: counter)["syntax"]
    ol2 = rep.outline(CASES_PATH, text)
    g2 = rep.graph({CASES_PATH: ol2})
    assert (ol2, g2, rep.reach(g2, ["Reader.Cases.uses_strict"])) == (ol, g, r)


def test_cross_file_names_are_placed_through_imports():
    a = "namespace P\n\ntheorem base : True := trivial\n\nend P\n"
    b = "import Pkg.A\n\nnamespace P\n\ntheorem top : True := base\n\nend P\n"
    c = "theorem stray : True := P.base\n"                  # imports nothing of the set: base stays outside
    g = LR.graph({"Pkg/A.lean": LR.outline("Pkg/A.lean", a), "Pkg/B.lean": LR.outline("Pkg/B.lean", b),
                  "Pkg/C.lean": LR.outline("Pkg/C.lean", c)})
    assert g["uses"]["P.top"] == ["P.base"] and g["used-by"]["P.base"] == ["P.top"]
    assert g["uses"]["stray"] == [] and g["outside"]["stray"] == ["P.base"]
    assert g["order"].index("Pkg/A.lean") < g["order"].index("Pkg/B.lean")
    r = LR.reach(g)
    assert set(r["targets"]) == {"P.top", "stray"} and r["decls"]["P.base"]["depth"] == 1


# ---------------------------------------------------------------------------
# Mathlib, read as text
# ---------------------------------------------------------------------------

@needs_mathlib
def test_the_shipped_fixture_file_of_mathlib():
    p = "Mathlib/NumberTheory/PrimesCongruentOne.lean"
    ol = RE.SYNTAX.outline(p, (MATHLIB / p).read_text(encoding="utf-8"))
    assert ol["ok"] is True and ol["module-system"] is True and ol["lines"] == 75
    assert [i["module"] for i in ol["imports"]] == ["Mathlib.RingTheory.Polynomial.Cyclotomic.Eval"]
    assert [d["kind"] for d in ol["defs"]] == ["theorem", "theorem", "theorem", "alias"]
    assert ol["defs"][3]["attributes"] == ["deprecated"]
    assert LR.default_targets(ol) == ["Nat.infinite_setOfPred_prime_modEq_one"]
    r = RE.SYNTAX.reach(RE.SYNTAX.graph({p: ol}))
    assert r["targets"] == ["Nat.infinite_setOfPred_prime_modEq_one"] and r["target-by"] == "rule"
    assert [(c["name"], c["depth"]) for c in r["candidates"]] == [
        ("Nat.infinite_setOfPred_prime_modEq_one", 0), ("Nat.frequently_atTop_modEq_one", 1)]
    assert ol["sorry"] == 0 and ol["axioms"] == [] and ol["native-decide"] == 0


@needs_mathlib
def test_the_calibration_slice_reaches_down_to_the_gauss_sums():
    start, inside = "Mathlib/NumberTheory/LegendreSymbol/QuadraticReciprocity.lean", "Mathlib/NumberTheory/"
    outs: dict = {}
    todo = [start]
    while todo:
        p = todo.pop()
        if p in outs:
            continue
        outs[p] = RE.SYNTAX.outline(p, (MATHLIB / p).read_text(encoding="utf-8"))
        todo += [q for q in (i["module"].replace(".", "/") + ".lean" for i in outs[p]["imports"])
                 if q.startswith(inside) and (MATHLIB / q).is_file()]
    assert len(outs) == 11
    r = RE.SYNTAX.reach(RE.SYNTAX.graph(outs), ["legendreSym.quadratic_reciprocity"])
    top = [c["name"] for c in r["candidates"][:3]]
    assert top == ["legendreSym.quadratic_reciprocity", "quadraticChar_odd_prime", "quadraticChar_card_card"]
