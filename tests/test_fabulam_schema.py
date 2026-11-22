"""The fabulam in the fabula's manifest (docs/v090-fabulam-design.md, 1 and 5.1), and its names on disk (6, 1.3).

The flavour, the catalog keys and field lists, the reused kinds that gain the flavour, the seven new kinds with their
refs, required and closed lists, the stance rows, the thym-1 calls; and enough/fabula_names.py's names and ids.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from enough import fabula
from enough import fabula_names as N
from enough import fabulam as FM
from enough import macrocosm as M

FIXTURE = Path(__file__).parent / "fixtures" / "fabula" / "fabulam" / "hand-primes-congruent-one.fabulam.cosm"


@pytest.fixture(scope="module")
def m():
    return M.default_registry().get("fabula")


def test_the_flavour_and_the_catalog(m):
    assert m.flavours == ["fabulan", "fabulap", "fabulac", "fabulam"] and m.flavour_absent == "fabulan"
    cat = m.data["catalog"]
    assert {"teaching", "audit"} <= set(cat["keys"])
    assert cat["source-checking-fields"] == ["sorry", "axioms", "native-decide", "said", "said-by", "said-at",
                                             "built-here"]
    assert cat["source-proof-fields"][:5] == ["path", "kind", "language", "toolchain", "module"]
    assert "checking" in cat["source-proof-folder-fields"] and cat["source-target-by"] == ["given", "rule"]
    assert cat["audit-kind"] == ["header", "module-note", "note", "inline"]
    assert cat["audit-verdict"] == ["agrees", "claim", "nothing"]
    assert cat["audit-fields"] == ["lines", "kind", "on", "verdict", "claim"]
    assert cat["shorts-density"] == ["expert", "student", "everyone"] and "density" in cat["shorts-fields"]
    assert cat["shorts-path-fabulam"] == "<name>.pshort-<density>-<YYYY-MM-DD-HHMM>.md"
    assert cat["atem-fields-fabulam"] == ["line", "of", "focus", "push", "pull"]
    assert m.matches_catalog("primes-congruent-one.fabulam.cosm")
    assert "stage" in m.closed_lists()["division"]


REUSED = ["C:file", "C:dependency", "C:reliance", "C:part", "C:component", "P:claim", "P:reading", "P:case",
          "P:assumption", "L:term", "K:concept", "E:work", "E:person", "E:org", "N:aim", "N:decision", "R:maker",
          "R:licence", "R:means", "X:atem"]
NEW = ["C:statement", "C:definition", "C:lemma", "C:constant", "C:step", "P:yield", "P:fit"]


@pytest.mark.parametrize("key", REUSED + NEW)
def test_every_kind_a_fabulam_holds_names_the_flavour(m, key):
    L, k = key.split(":")
    assert "fabulam" in m.kind(L, k)["flavours"], key


def test_the_new_kinds_hold_only_fabulams(m):
    for key in NEW:
        L, k = key.split(":")
        assert m.kind(L, k)["flavours"] == ["fabulam"], key


def test_the_new_kinds_as_the_design_writes_them(m):
    st = m.kind("C", "statement")
    assert st["refs"] == ["uses", "leans-on", "relates.to"]
    assert st["required"][-3:] == ["lean", "says", "quantifiers"]
    lem = m.kind("C", "lemma")
    assert lem["closed"]["role"] == ["spine", "support", "bookkeeping"]
    assert lem["closed"]["reached"] == ["yes", "no", "perhaps"] and lem["open"] == ["scope"]
    assert m.kind("C", "definition")["closed"]["form"][-3:] == ["alias", "notation", "other"]
    assert m.kind("C", "constant")["required"][-2:] == ["says", "where"]
    assert m.kind("C", "step")["required"][-3:] == ["inside", "says", "span"]
    y = m.kind("P", "yield")
    assert y["closed"]["bound"] == ["at-least", "at-most", "exactly", "between", "none"]
    assert y["closed"]["trivial.compares"] == ["above", "equal", "below"]
    assert "chooses.where" in y["refs"]
    f = m.kind("P", "fit")
    assert f["closed"]["how"] == ["same", "stronger", "weaker", "a-particular-reading", "different"]


def test_the_added_words_of_reused_kinds(m):
    assert "part" in m.kind("C", "reliance")["closed"]["on"]
    assert "worked" in m.kind("P", "case")["closed"]["from"]
    assert m.kind("C", "part")["closed"]["stage"] == ["reduction", "main", "tool", "side", "close"]
    assert {"opens", "limits"} <= set(m.kind("C", "file")["checked"])
    assert {"lean", "known-as", "field", "case", "stated-in", "digest"} <= set(m.kind("C", "reliance")["checked"])


def test_the_earlier_flavours_read_their_kinds_as_before(m):
    # a fabulac's reliance still needs no lean; a fabulan's part still needs only its division
    assert "lean" not in m.kind("C", "reliance")["required"]
    assert m.kind("C", "part")["required"] == ["id", "type", "name", "summary", "provenance", "stance", "division"]
    assert m.kind("C", "interface")["flavours"] == ["fabulac"]
    assert m.kind("C", "line")["flavours"] == ["fabulap"]


def test_the_checks_join_checks_own(m):
    own = m.own_checks()
    assert own == list(fabula.OWN_CHECKS)
    assert set(FM.CHECKS) <= set(own)
    sev = m._block("checks")["severity"]
    assert all(sev[c] == "warning" for c in FM.WARNINGS)


def _move(m, name):
    return next(mv for mv in m.data["moves"] if mv["name"] == name)


def test_the_thym1_calls(m):
    sv = _move(m, "survey")
    assert sv["takes"] == ["folder | text"] and sv["modifiers"] == {"with": "fabula"}
    rule = next(r for r in sv["contract-when"] if r.get("takes") == "text")
    assert {"declarations-found", "comments-covered", "reach-agrees", "fabula-checks"} <= set(rule["contract"])
    dv = _move(m, "derive")["thym-1"]
    assert "proof" in dv["modifiers"]["as"]
    rule = next(r for r in dv["contract-when"] if r.get("as") == ["proof"])
    assert "its-own-file" not in rule["contract"] and "lines-resolve" in rule["contract"]
    assert {"as": ["proof"], "scaffold": "none"} in dv["scaffold-when"]
    cs = _move(m, "construe")
    for axis in ("comments", "fit", "yield", "stages"):
        assert axis in cs["modifiers"]["as"]
        assert any(r.get("as") == [axis] for r in cs["contract-when"])
    en = _move(m, "entail")["thym-1"]
    dens = ["expert", "student", "everyone"]
    assert all(d in en["modifiers"]["as"] for d in dens)
    assert {"as": dens, "gives": "short"} in en["gives-when"]
    rule = next(r for r in en["contract-when"] if r.get("as") == dens)
    assert rule["contract"][:4] == ["cites-resolve", "every-sentence-cited", "yield-cited", "teaching-followed"]
    assert {"as": dens, "scaffold": "none"} in en["scaffold-when"]
    assert [mv["name"] for mv in m.data["moves"]].count("survey") == 1      # no new move (design 5.1)


def test_the_fixture_is_hand_written_and_valid():
    head = FIXTURE.read_text(encoding="utf-8").splitlines()[0]
    assert "Hand-written for the fabulam schema's tests" in head
    rep = fabula.lint(FIXTURE)
    assert rep.errors == [] and fabula.flavour(rep.volume) == "fabulam"
    doc = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    kinds = {n["id"].split("/")[0] for n in doc["nodes"]}
    assert {"C:statement", "C:lemma", "C:definition", "C:step", "C:constant", "C:part", "P:yield", "P:case",
            "P:claim", "P:assumption", "C:file", "C:dependency", "C:reliance"} <= kinds


def test_a_lemma_scope_is_not_a_dependency_scope(tmp_path):
    doc = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    next(n for n in doc["nodes"] if n["id"] == "C:lemma/Nat.exists_prime_gt_modEq_one")["scope"] = ["12-14"]
    p = tmp_path / "x.fabulam.cosm"
    p.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    assert fabula.lint(p).errors == []
    next(n for n in doc["nodes"] if n["id"] == "C:dependency/mathlib")["scope"] = "lines"
    p.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    assert {e.check for e in fabula.lint(p).errors} == {"closed-list"}


def test_a_new_kind_in_another_flavour_is_refused(tmp_path):
    doc = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    doc["flavour"] = "fabulac"
    p = tmp_path / "x.fabulac.cosm"
    p.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    assert "flavour-kind" in {e.check for e in fabula.lint(p).errors}


# ---------------------------------------------------------------- names on disk

def test_the_flavour_in_fabula_names():
    assert "fabulam" in N.FLAVOURS and "fabulam" not in N.TEXT_FLAVOURS
    assert N.parse("primes-congruent-one.fabulam.cosm") == ("primes-congruent-one", "fabulam")
    with pytest.raises(N.FlavourError, match="Lean proof"):
        N.check_text_flavour("fabulam")
    assert N.short_stem("primes-congruent-one.fabulam.cosm") == "primes-congruent-one"


def test_a_fabulam_is_never_a_text_twin(tmp_path):
    (tmp_path / "notes.md").write_text("x", encoding="utf-8")
    twin = tmp_path / "notes.md.fabulam.cosm"
    twin.write_text("oes: fabula/1\nflavour: fabulam\n", encoding="utf-8")
    assert N.text_of_twin(twin) is None
    assert N.folder_twins(tmp_path.iterdir()).twins == {}


def test_the_names_of_design_6():
    assert N.fabulam_stem("PrimesCongruentOne.lean") == "primes-congruent-one"
    assert N.fabulam_stem("Mathlib/NumberTheory/LSeries/") == "lseries"
    assert N.fabulam_name("primes-congruent-one") == "primes-congruent-one.fabulam.cosm"
    assert N.fabulam_parts_folder("lseries") == "lseries.fabulam.parts"
    assert N.fabulam_part_name("Mathlib/NumberTheory/LSeries/Nonvanishing.lean") == "Nonvanishing.fabulam.cosm"
    assert N.fabulam_part_id("lseries", "Mathlib.NumberTheory.LSeries.Nonvanishing") == \
        "fabula/lseries--Mathlib-NumberTheory-LSeries-Nonvanishing"
    assert N.pshort_name("primes-congruent-one", "everyone", "2026-11-22-1405") == \
        "primes-congruent-one.pshort-everyone-2026-11-22-1405.md"
    with pytest.raises(ValueError):
        N.pshort_name("x", "child", "2026-11-22-1405")
    with pytest.raises(ValueError):
        N.pshort_name("x", "expert", "2026-11-22")


def test_the_id_slug_rule():
    assert N.declaration_slug("Nat.exists_prime_gt_modEq_one") == "Nat.exists_prime_gt_modEq_one"
    assert N.declaration_slug("quadratic_reciprocity'") == "quadratic_reciprocity-prime"
    assert N.declaration_slug("ZMod.χ₈") == "ZMod.-x3c7-x2088"
    assert N.declaration_slug("χ₈") == "x-x3c7-x2088"
    ids = N.declaration_ids([("lemma", "foo'", 3), ("lemma", "foo-prime", 9), ("definition", "", 12),
                             ("lemma", "", 20), ("statement", "Nat.main", 30)])
    assert ids == ["C:lemma/foo-prime", "C:lemma/foo-prime-2", "C:definition/instance-L12", "C:lemma/example-L20",
                   "C:statement/Nat.main"]
    # every id the rule writes parses under the fabula's grammar
    g = M.default_registry().get("fabula").grammar
    for iid in ids + ["C:lemma/" + N.declaration_slug("ZMod.χ₈"), "C:lemma/" + N.declaration_slug("«weird name».")]:
        assert g.parse(iid) is not None, iid
