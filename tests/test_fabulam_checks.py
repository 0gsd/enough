"""The fabulam's own checks over the volume alone (docs/v090-fabulam-design.md, 2.A; enough/fabulam.py).

The hand-written fixture passes every check with no error. Then, for each check, the fixture is broken in the one way
that check exists to catch, and exactly that check fails.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from enough import fabula
from enough import fabulam as FM
from enough import macrocosm as M

FIXTURE = Path(__file__).parent / "fixtures" / "fabula" / "fabulam" / "hand-primes-congruent-one.fabulam.cosm"
STMT = "C:statement/Nat.infinite_setOfPred_prime_modEq_one"
SPINE = "C:lemma/Nat.exists_prime_gt_modEq_one"
BOOK = "C:lemma/Nat.frequently_atTop_modEq_one"
YIELD = "P:yield/what-the-proof-delivers"
CASE = "P:case/k-three-n-two"
RED = "C:part/what-must-be-found"
MAIN = "C:part/a-number-built-to-have-the-right-factor"
CLOSE = "C:part/from-one-to-many"


def _doc() -> dict:
    return yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))


def _node(doc: dict, iid: str) -> dict:
    return next(n for n in doc["nodes"] if n["id"] == iid)


def _lint(doc: dict, tmp_path: Path) -> M.Report:
    p = tmp_path / "broken.fabulam.cosm"
    p.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return fabula.lint(p)


def _errors(rep: M.Report) -> set[str]:
    return {p.check for p in rep.problems() if p.severity == "error"}


def _warnings(rep: M.Report) -> set[str]:
    return {p.check for p in rep.problems() if p.severity == "warning"}


def test_the_fixture_passes_every_check():
    rep = fabula.lint(FIXTURE)
    assert rep.errors == [], [str(p) for p in rep.errors]
    assert set(FM.CHECKS) <= set(rep.checks) and not set(FM.CHECKS) & set(rep.not_run)
    # the one warning the design expects (4.2): the rule's only candidate was judged bookkeeping
    warns = [p for p in rep.problems() if p.severity == "warning"]
    assert [(p.check, p.item) for p in warns] == [("spine-rule-differs", BOOK)], [str(p) for p in warns]


def test_the_fixture_round_trips_through_yaml_and_still_passes(tmp_path):
    rep = _lint(_doc(), tmp_path)
    assert rep.errors == [], [str(p) for p in rep.errors]


def _drop(doc, iid):
    doc["nodes"] = [n for n in doc["nodes"] if n["id"] != iid]


def _set(iid, **kw):
    def f(doc):
        _node(doc, iid).update(kw)
    return f


def _pop(iid, key):
    def f(doc):
        _node(doc, iid).pop(key)
    return f


def _two_yields(doc):
    y = copy.deepcopy(_node(doc, YIELD))
    y["id"] = "P:yield/a-second"
    doc["nodes"].append(y)


def _wording_without_fit(doc):
    doc["source"]["wording"] = "wording.md"
    doc["nodes"].append({"id": "E:work/wording", "type": "work", "name": "the wording", "summary": "A wording.",
                         "stance": "hearsay", "provenance": {"mode": "manual", "sources": ["wording.md"],
                                                             "confidence": 1}})


def _fit_without_wording(doc):
    if not any(n["id"] == "E:work/wording" for n in doc["nodes"]):
        doc["nodes"].append({"id": "E:work/wording", "type": "work", "name": "a wording", "summary": "A wording.",
                             "stance": "hearsay", "provenance": {"mode": "manual", "sources": ["w"], "confidence": 1}})
    doc["nodes"].append({"id": "P:fit/against-the-wording", "type": "fit", "name": "fit", "summary": "A fit.",
                         "of": STMT, "against": "E:work/wording", "how": "same", "differences": [],
                         "confidence": "high", "stance": "opinion",
                         "provenance": {"mode": "manual", "sources": ["x"], "confidence": 0.5}})


def _spine_out_of_stages(doc):
    _node(doc, MAIN)["steps"] = [s for s in _node(doc, MAIN)["steps"] if s != SPINE]


def _two_reductions(doc):
    _node(doc, CLOSE)["stage"] = "reduction"
    _node(doc, CLOSE)["obvious"] = "none: the file's way is the obvious one"
    doc["telling"] = [RED, CLOSE, MAIN]


def _telling_reversed(doc):
    doc["telling"] = list(reversed(doc["telling"]))


def _row_unnamed_claim(doc):
    doc["audit"][1] = {"lines": "10-15", "kind": "module-note", "on": "", "verdict": "agrees"}


def _claim_partial_bare(doc):
    _node(doc, "P:claim/module-note-infinitely-many")["checked"] = "partial"


def _checking_says_verified(doc):
    _node(doc, "P:claim/checking")["says"] = "The file was verified by Lean."


def _case_without_numbers(doc):
    _node(doc, CASE).update(given="small numbers", expect="a prime of the right kind")


def _up_to(doc):
    _node(doc, YIELD)["says"] = "The proof delivers primes up to a bound it names."


def _plain_symbol(doc):
    _node(doc, CLOSE)["plain"] = "If p > n always holds for some p, there is no last one."


def _judgement(doc):
    _wording_without_fit(doc)
    _fit_without_wording(doc)
    _node(doc, "P:fit/against-the-wording")["differences"] = ["The wording leaves out the obvious case k = 0."]


def _size(doc):
    _node(doc, YIELD)["says"] = "The prime it finds grows with n at a rate set by the point."


def _spine_far_down(doc):
    n = _node(doc, SPINE)
    n.update(depth=3, carries=0)


def _reliance_part_disagrees(doc, tmp_path):
    return doc


BREAKS = [
    # check, how it is broken
    ("declared-once", _set(SPINE, lean="")),
    ("declared-once", _set(BOOK, lean="Nat.exists_prime_gt_modEq_one")),
    ("declared-once", _set("C:constant/the-point", lean="Nat.factorial")),
    ("statement-whole", lambda d: d["source"].update(target=["Nat.some_other_theorem"])),
    ("statement-whole", _set(STMT, quantifiers=[{"kind": "for-some", "what": "k"}])),
    ("yield-stated", _two_yields),
    ("yield-stated", _pop(YIELD, "as-statement")),
    ("yield-stated", _set(YIELD, trivial=[])),
    ("fit-stated", _wording_without_fit),
    ("fit-stated", _fit_without_wording),
    ("spine-told", _pop(SPINE, "why")),
    ("spine-told", _spine_out_of_stages),
    ("spine-told", _set(BOOK, reached="perhaps")),
    ("stages-whole", _set(CLOSE, number=4)),
    ("stages-whole", _two_reductions),
    ("stages-whole", _telling_reversed),
    ("stages-whole", _pop(RED, "obvious")),
    ("grounds-given", _set(YIELD, grounds=[])),
    ("grounds-given", _set("C:step/order-k-divides-p-minus-one",
                           span={"file": "PrimesCongruentOne.lean", "lines": "61-65"})),
    ("audit-whole", _row_unnamed_claim),
    ("audit-whole", _claim_partial_bare),
    ("audit-whole", lambda d: d["audit"][0].update(verdict="fine")),
    ("stance-fits", _set(SPINE, stance="opinion")),
    ("stance-fits", _set("C:constant/the-point", stance="assumed")),
    ("checking-said", _checking_says_verified),
    ("checking-said", lambda d: d["source"]["checking"].update({"built-here": "yes"})),
    ("checking-said", lambda d: _drop(d, "P:claim/checking")),
    ("example-worked", _case_without_numbers),
    ("no-up-to", _up_to),
]


@pytest.mark.parametrize("check,breaker", BREAKS, ids=[f"{c}-{i}" for i, (c, _b) in enumerate(BREAKS)])
def test_each_error_check_catches_its_break(check, breaker, tmp_path):
    doc = _doc()
    breaker(doc)
    errs = _errors(_lint(doc, tmp_path))
    assert errs == {check}, errs


WARN_BREAKS = [
    ("plain-words", _plain_symbol),
    ("no-judgement", _judgement),
    ("regime-named", _size),
    ("spine-rule-differs", _spine_far_down),
]


@pytest.mark.parametrize("check,breaker", WARN_BREAKS, ids=[c for c, _b in WARN_BREAKS])
def test_each_warning_check_catches_its_break(check, breaker, tmp_path):
    doc = _doc()
    breaker(doc)
    rep = _lint(doc, tmp_path)
    assert _errors(rep) == set(), [str(p) for p in rep.errors]
    got = {p.check for p in rep.problems() if p.severity == "warning" and p.check != "spine-rule-differs"
           or (p.check == "spine-rule-differs" and p.item != BOOK)}
    assert got == {check}, got


def test_every_check_is_broken_by_a_test():
    covered = {c for c, _b in BREAKS} | {c for c, _b in WARN_BREAKS} | {"parts-resolve", "statements-agree"}
    assert covered == set(FM.CHECKS)


# ---------------------------------------------------------------- a head and its part

def _write(p: Path, doc: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _head_and_part(tmp_path: Path, *, part_head: str = "oes:fabula/archive", gives: str | None = None):
    part = _doc()
    part["id"] = "fabula/archive--Mathlib-NumberTheory-PrimesCongruentOne"
    part["head"] = part_head
    lem = _node(part, SPINE)
    lem["digest"] = "0123456789abcdef"
    head = {"oes": "fabula/1", "flavour": "fabulam", "id": "fabula/archive", "name": "archive",
            "source": {"path": "src/", "kind": "folder", "language": "lean", "files": 1, "licence": "Apache-2.0",
                       "target": ["Nat.infinite_setOfPred_prime_modEq_one"], "target-by": "rule",
                       "checking": {"sorry": 0, "axioms": 0, "native-decide": 0, "built-here": "no"}},
            "parts": [{"uri": "oes:fabula/archive--Mathlib-NumberTheory-PrimesCongruentOne",
                       "path": "archive.fabulam.parts/PrimesCongruentOne.fabulam.cosm"}],
            "nodes": [
                {"id": "C:component/primes-congruent-one", "type": "component", "name": "PrimesCongruentOne",
                 "summary": "The one part.", "told-in": "oes:fabula/archive--Mathlib-NumberTheory-PrimesCongruentOne",
                 "stance": "deduced", "provenance": {"mode": "derived", "sources": ["parts"], "confidence": 1}},
                {"id": SPINE, "type": "lemma", "name": "the crossing lemma", "summary": "Told in the part.",
                 "lean": "Nat.exists_prime_gt_modEq_one", "says": lem["says"], "digest": "0123456789abcdef",
                 "told-in": "oes:fabula/archive--Mathlib-NumberTheory-PrimesCongruentOne/C/lemma/"
                            "Nat.exists_prime_gt_modEq_one",
                 "stance": "deduced", "provenance": {"mode": "derived", "sources": ["parts"], "confidence": 1}},
                {"id": STMT, "type": "statement", "name": "the target", "summary": "Told in the part.",
                 "lean": "Nat.infinite_setOfPred_prime_modEq_one", "says": _node(part, STMT)["says"],
                 "quantifiers": _node(part, STMT)["quantifiers"],
                 "told-in": "oes:fabula/archive--Mathlib-NumberTheory-PrimesCongruentOne/C/statement/"
                            "Nat.infinite_setOfPred_prime_modEq_one",
                 "stance": "deduced", "provenance": {"mode": "derived", "sources": ["parts"], "confidence": 1}},
                {"id": "P:claim/checking", "type": "claim", "name": "checking", "summary": "What is known.",
                 "says": "Nothing was built or run here.", "stance": "observed",
                 "provenance": {"mode": "derived", "sources": ["source.checking"], "confidence": 1}},
                {"id": "R:licence/apache-2-0", "type": "licence", "name": "Apache-2.0", "summary": "The licence.",
                 "identifier": "Apache-2.0", "stance": "observed",
                 "provenance": {"mode": "manual", "sources": ["x"], "confidence": 1}},
            ]}
    # a reliance in the part on the head's own statement of the crossing lemma (as a neighbour would hold it)
    part["nodes"].append({"id": "C:reliance/the-crossing-lemma", "type": "reliance", "name": "the crossing lemma",
                          "summary": "As the head states it.", "on": "part", "lean": ["Nat.exists_prime_gt_modEq_one"],
                          "stated-in": f"oes:fabula/archive/C/lemma/Nat.exists_prime_gt_modEq_one",
                          "digest": "0123456789abcdef", "gives": gives if gives is not None else lem["says"],
                          "stance": "deduced",
                          "provenance": {"mode": "derived", "sources": ["head"], "confidence": 1}})
    _write(tmp_path / "archive.fabulam.cosm", head)
    _write(tmp_path / "archive.fabulam.parts" / "PrimesCongruentOne.fabulam.cosm", part)
    return tmp_path / "archive.fabulam.cosm", tmp_path / "archive.fabulam.parts" / "PrimesCongruentOne.fabulam.cosm"


def test_a_head_and_its_part_resolve_and_agree(tmp_path):
    head, part = _head_and_part(tmp_path)
    for p in (head, part):
        rep = fabula.lint(p)
        assert rep.errors == [], (p.name, [str(x) for x in rep.errors])


def test_parts_resolve_catches_a_part_that_names_another_head(tmp_path):
    head, part = _head_and_part(tmp_path, part_head="oes:fabula/elsewhere")
    assert _errors(fabula.lint(head)) == {"parts-resolve"}


def test_a_part_that_holds_no_target_needs_no_statement(tmp_path):
    """The conductor's ruling on 2.A against 4.1: a part whose file declares none of the targets holds no statement,
    its atem names one of its own declarations, and the yield, fit and worked example hold of no statement."""
    head, part = _head_and_part(tmp_path)
    doc = yaml.safe_load(part.read_text(encoding="utf-8"))
    doc["source"]["target"] = ["Nat.a_theorem_of_another_part"]
    doc["nodes"] = [n for n in doc["nodes"] if n["id"] not in (STMT, YIELD, CASE)
                    and not n["id"].startswith("C:definition/")]
    for n in doc["nodes"]:
        for f in ("uses", "used-by", "steps"):
            if isinstance(n.get(f), list):
                n[f] = [x for x in n[f] if x != STMT]
        if n["id"] == "P:claim/module-note-infinitely-many":
            n["about"], n["by"] = SPINE, [SPINE]
    doc["atem"]["of"] = SPINE
    _write(part, doc)
    rep = fabula.lint(part)
    assert rep.errors == [], [str(p) for p in rep.errors]
    doc["atem"]["of"] = "C:reliance/exists-infinite-primes"
    _write(part, doc)
    assert _errors(fabula.lint(part)) == {"statement-whole"}


def test_a_part_must_state_a_target_its_own_file_declares(tmp_path):
    head, part = _head_and_part(tmp_path)
    doc = yaml.safe_load(part.read_text(encoding="utf-8"))
    doc["source"]["target"] = ["Nat.infinite_setOfPred_prime_modEq_one", "Nat.exists_prime_gt_modEq_one"]
    _write(part, doc)
    assert _errors(fabula.lint(part)) == {"statement-whole"}


def test_statements_agree_catches_a_neighbour_restated_differently(tmp_path):
    head, part = _head_and_part(tmp_path, gives="Something else than the head states.")
    assert _errors(fabula.lint(part)) == {"statements-agree"}
    assert fabula.lint(head).errors == []
