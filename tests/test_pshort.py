"""The pshort: a fabulam entailed at three densities, and the checks of a pshort (0.9; `enough/thym/moves/proof.py`,
`enough/fabulam_job.py`; Thym 20.13; the design `docs/v090-fabulam-design.md`, sections 2.C and 5.4).

`entail-the-pshorts` lands three pshorts of the fixture's fabulam from HAND-RECORDED answers (a person wrote them;
each file says so), and each passes every check of 2.C. Then each check is broken in the one way it exists to
catch. Rules write a pshort's three fixed lines and its footer; the body is the answer's. The entailer never sees
the Lean: what it was sent holds no span, no lines and no path.
"""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from enough import fabulam_job as J
from enough import macrocosm as mc
from enough.thym import checks as C
from enough.thym import declarations as dc
from enough.thym.moves import proof as P
from enough.thym.moves import short_value
from enough.thym.values import read_value
from tests.test_fabulam_moves import (DEFAULT_CHECKING, LEAN, NOW, REC, TARGET, Recorded, build, fab_path, fabulam,
                                      project, recorded, runtime)  # noqa: F401 - project is a fixture

CTX = SimpleNamespace(engines={}, now=NOW, coprocessor=None)
PSHORT_CHECKS = ("cites-resolve", "every-sentence-cited", "yield-cited", "teaching-followed", "no-up-to",
                 "example-worked", "nothing-added", "checking-told", "confidence-told", "symbols-worded", "apart",
                 "length", "footer")
YIELD = "P:yield/what-the-proof-delivers"
CASE = "P:case/k-three-n-two"
STAGES = ["C:part/what-must-be-found", "C:part/a-number-built-to-have-the-right-factor", "C:part/from-one-to-many"]


@pytest.fixture
def built(project: Path):  # noqa: F811
    cp = Recorded(REC / "primes-congruent-one")
    assert build(project, cp)["complete"]
    return SimpleNamespace(project=project, cp=cp, path=fab_path(project))


def entail(built, **kw):
    return J.run_entail(built.project, built.path, mode="model", runtime=runtime(built.cp), now=NOW, **kw)


def a_pshort(built, density: str, body: str | None = None, *, requests: list | None = None, text: str | None = None):
    """A pshort as the move gives it: the fixed lines and the footer by rule around `body` (the recorded one unless
    another is given), carrying its fabulam, its density and what was sent."""
    fab = read_value(built.path, "fabula")
    cat, items = P._fabulam(fab, "a fabulam")
    body = body if body is not None else body_of(density)
    full = text or P.pshort_text(P.pshort_fixed(cat, items, fab, density), body,
                                 P.pshort_footer(cat, fab, density, "2026-11-22", "hand-recorded"))
    sent = requests if requests is not None else [{"items": P.pshort_view(cat, items)[0], "density": density}]
    return short_value(full, fabula=fab, order="told", density=density, requests=sent), fab


def verdict(name: str, built, density: str, body: str | None = None, **kw):
    v, fab = a_pshort(built, density, body, **kw)
    return C.verdict(name, v, {"f": fab}, {"modifiers": {"as": density}}, {"name": "entail"}, CTX)


def body_of(density: str) -> str:
    return mc.yaml_load(recorded(REC / "primes-congruent-one", f"pshort-{density}"))["body"].strip()


# ---------------------------------------------------------------------------
# The three pshorts land, and pass every check
# ---------------------------------------------------------------------------

def test_entail_the_pshorts_lands_three_pshorts_that_pass_every_check(built):
    out = entail(built)
    assert [p["density"] for p in out["pshorts"]] == ["expert", "student", "everyone"] and out["recorded"]
    doc = fabulam(built.project)
    shorts = doc["shorts"]
    assert [s["density"] for s in shorts] == ["expert", "student", "everyone"]
    for s, p in zip(shorts, out["pshorts"]):
        assert set(s) == {"path", "at", "by", "mode", "route", "entailed", "density"}       # no order (the text)
        assert (s["entailed"], s["mode"], s["by"]) == ("apart", "model", "hand-recorded")
        assert s["path"] == f"primes-congruent-one.pshort-{s['density']}-2026-11-22-1200.md" and p["path"] == s["path"]
        text = (built.project / s["path"]).read_text(encoding="utf-8")
        lines = text.split("\n")
        who = {"expert": "experts", "student": "students", "everyone": "everyone"}[s["density"]]
        assert lines[0] == f"# primes-congruent-one, for {who}"
        assert lines[2] == (f"*A pshort of primes-congruent-one.fabulam.cosm at {s['density']}. It is a guide to a "
                            "formal proof. It is not a proof.*")
        assert lines[4] == f"*{DEFAULT_CHECKING}* [P:claim/checking]"
        assert text.rstrip().split("\n")[-1] == (f"*a pshort of primes-congruent-one.fabulam.cosm, at {s['density']}, "
                                                 "entailed apart on 2026-11-22 by hand-recorded*")
        assert not any(w in text.lower() for w in P.CHECK_WORDS)
    # the same pshorts, held to each check of 2.C one by one
    for density in P.DENSITIES:
        for name in PSHORT_CHECKS:
            ok, why = verdict(name, built, density)
            assert ok, (density, name, why)
            if name in ("confidence-told", "symbols-worded", "teaching-followed", "example-worked"):
                assert "warning" not in why and "a note" not in why, (density, name, why)
    state = J.file_state(built.project, built.project / LEAN.name)
    assert [(p["density"], p["exists"], p["stale"]) for p in state["pshorts"]] == [
        ("expert", True, False), ("student", True, False), ("everyone", True, False)]


def test_the_contract_of_a_pshort_is_the_table_of_2c_and_one_density_runs_alone(built):
    entail_decl = dc.load()["entail"].view(1)
    for density in P.DENSITIES:
        assert dc.chosen(entail_decl, as_word=density)["contract"] == PSHORT_CHECKS + ("provenance",)
        assert dc.chosen(entail_decl, as_word=density)["scaffold"] is None
    out = entail(built, density="everyone")
    assert [p["density"] for p in out["pshorts"]] == ["everyone"]
    assert out["pshorts"][0]["path"] == "primes-congruent-one.pshort-everyone-2026-11-22-1200.md"
    again = entail(built, density="everyone")              # a second in one minute takes -2
    assert again["pshorts"][0]["path"] == "primes-congruent-one.pshort-everyone-2026-11-22-1200-2.md"
    with pytest.raises(J.BuildError) as e:
        J.pshort_program("child")
    assert "expert, student or everyone" in str(e.value)


def test_the_entailer_is_sent_the_items_alone(built):
    entail(built, density="expert")
    sent = built.cp.asked("pshort-expert")[0]
    assert set(sent) == {"fabulam", "density", "name", "items", "must", "words"}
    items = sent["items"]
    assert "span:" not in items and "lines:" not in items and "PrimesCongruentOne.lean" not in items
    assert "minFac" not in items and ":= by" not in items and "sha256" not in items
    assert "Nat.exists_prime_gt_modEq_one" in items and "what-the-proof-delivers" in items
    assert sent["words"] == "500 to 900" and "P:claim/checking" in sent["must"]
    fab = read_value(built.path, "fabula")
    cat, its = P._fabulam(fab, "a fabulam")
    assert P.must_cite(cat, its, "everyone") == [YIELD, "P:claim/checking", *STAGES]
    assert P.must_cite(cat, its, "expert") == [YIELD, "P:claim/checking"]


def test_a_pshort_is_not_entailed_from_an_outline_or_without_a_model(project: Path):  # noqa: F811
    build(project, mode="rules", why="no model")
    with pytest.raises(J.BuildError) as e:
        J.run_entail(project, fab_path(project), mode="model", runtime=runtime(None), now=NOW)
    assert e.value.status == 409 and "is an outline" in str(e.value)
    assert build(project, Recorded(REC / "primes-congruent-one"), restart=True)["complete"]
    with pytest.raises(RuntimeError) as e2:
        J.run_entail(project, fab_path(project), mode="rules", why="the model is not running", now=NOW)
    assert "a pshort has no scaffold" in str(e2.value)


def test_past_the_budget_the_bookkeeping_lemmas_are_left_out_and_the_footer_says_so(built, monkeypatch):
    fab = read_value(built.path, "fabula")
    cat, items = P._fabulam(fab, "a fabulam")
    whole, left = P.pshort_view(cat, items)
    assert left == [] and "Nat.frequently_atTop_modEq_one" in whole
    monkeypatch.setattr(P, "PSHORT_CHARS", len(whole) - 10)
    less, left = P.pshort_view(cat, items)
    assert left == ["the bookkeeping lemmas"] and "role: bookkeeping" not in less
    foot = P.pshort_footer(cat, fab, "expert", "2026-11-22", "m", left)
    assert foot.endswith("by m; left out for length: the bookkeeping lemmas*") and P._FOOT.match(foot)


# ---------------------------------------------------------------------------
# Each check of 2.C, broken in the one way it exists to catch
# ---------------------------------------------------------------------------

def test_cites_resolve_catches_an_id_the_fabulam_does_not_hold(built):
    body = body_of("expert").replace("[C:step/p-exceeds-n]", "[C:step/a-step-nobody-wrote]")
    ok, why = verdict("cites-resolve", built, "expert", body)
    assert not ok and "C:step/a-step-nobody-wrote" in why


def test_every_sentence_cited_catches_a_paragraph_that_ends_with_no_citation(built):
    body = body_of("student") + "\n\nThis last remark rests on nothing at all."
    ok, why = verdict("every-sentence-cited", built, "student", body)
    assert not ok and "no citation covers: This last remark rests on nothing at all." in why
    # a group covers the sentences before it, back to the group before
    rows, rest = P.covered("One thing. Another thing. [C:lemma/a, C:step/b] A third. [P:yield/c] A fourth.")
    assert rows == [("One thing.", ["C:lemma/a", "C:step/b"]), ("Another thing.", ["C:lemma/a", "C:step/b"]),
                    ("A third.", ["P:yield/c"])] and rest == "A fourth."


def test_yield_cited_catches_a_pshort_that_never_cites_the_yield(built):
    body = body_of("expert").replace(f"[{YIELD}]", "[C:lemma/Nat.exists_prime_gt_modEq_one]")
    ok, why = verdict("yield-cited", built, "expert", body)
    assert not ok and YIELD in why


def test_teaching_followed_holds_the_teaching_order_at_everyone_and_notes_it_elsewhere(built):
    body = body_of("everyone")
    paras = body.split("\n\n")
    swapped = "\n\n".join([paras[0], paras[2], paras[1], *paras[3:]])       # the main stage before the reduction
    ok, why = verdict("teaching-followed", built, "everyone", swapped)
    assert not ok and "not told in the teaching order" in why
    dropped = body.replace(f"[{STAGES[2]}]", "[C:lemma/Nat.frequently_atTop_modEq_one]")
    ok, why = verdict("teaching-followed", built, "everyone", dropped)
    assert not ok and f"the stage {STAGES[2]} is not cited" in why
    ok, why = verdict("teaching-followed", built, "student", dropped)       # at another density: a note
    assert ok and why.startswith("a note: ")


def test_no_up_to_catches_the_phrase_in_a_sentence_that_tells_the_yield(built):
    body = body_of("student").replace("it is the least prime factor of the value",
                                      "it is, up to the choice of the point, the least prime factor of the value")
    ok, why = verdict("no-up-to", built, "student", body)
    assert not ok and 'says "up to"' in why
    # elsewhere it bounds nothing: allowed after it are isomorphism, order, sign, symmetry, relabelling
    assert not P.holds_up_to("unique up to isomorphism") and P.holds_up_to("primes up to n")


def test_example_worked_holds_the_worked_case_at_everyone(built):
    body = body_of("everyone").replace(f"[{CASE}]", f"[{YIELD}]")
    ok, why = verdict("example-worked", built, "everyone", body)
    assert not ok and "cites no worked example" in why
    ok, why = verdict("example-worked", built, "expert", body_of("expert").replace(f"[{CASE}]", f"[{YIELD}]"))
    assert ok


def test_nothing_added_catches_a_number_and_a_name_the_fabulam_does_not_hold(built):
    body = body_of("student").replace("At 6 it gives 43.", "At 6 it gives 43, and at 7 it gives 57.")
    ok, why = verdict("nothing-added", built, "student", body)
    assert not ok and "the number 7 is not in the fabulam" in why
    body = body_of("student").replace("The module note of the file says the same.",
                                      "The module note of the file says the same, as Dirichlet proved.")
    ok, why = verdict("nothing-added", built, "student", body)
    assert not ok and "the name Dirichlet is not in the fabulam" in why


def test_checking_told_catches_a_claim_of_checking_and_a_changed_fixed_line(built):
    body = body_of("expert").replace("The argument has three stages.",
                                     "The argument has three stages, and Lean has verified each of them.")
    ok, why = verdict("checking-told", built, "expert", body)
    assert not ok and '"verified" is said in a sentence P:claim/checking does not cover' in why
    v, _fab = a_pshort(built, "expert")
    changed = v.text().replace("It is a guide to a formal proof. It is not a proof.", "It is a proof.")
    ok, why = verdict("checking-told", built, "expert", text=changed)
    assert not ok and "first two lines are not the fixed lines" in why
    softened = v.text().replace("so whether Lean accepts it is not known here", "and Lean accepts it")
    ok, why = verdict("checking-told", built, "expert", text=softened)
    assert not ok and "third line is not the sentence of P:claim/checking" in why


def test_confidence_told_and_symbols_worded_warn_and_refuse_nothing(built):
    fab = read_value(built.path, "fabula")
    doc = mc.yaml_load(built.path.read_text(encoding="utf-8"))
    for n in doc["nodes"]:
        if n["id"] == YIELD:
            n["confidence"] = "low"
    built.path.write_text(mc.dump(doc), encoding="utf-8")
    ok, why = verdict("confidence-told", built, "student")
    assert ok and why.startswith("a warning: a sentence that rests only on low confidence holds no hedge")
    del fab
    body = body_of("everyone").replace("Pick any whole number that is not zero and call it k.",
                                       "Pick any whole number k that is not zero.")
    ok, why = verdict("symbols-worded", built, "everyone", body)
    assert ok and why.startswith("a warning: k is used before it is said what it is")


def test_apart_catches_a_request_that_carried_a_span_the_path_or_the_lean(built):
    for bad, words in (([{"items": "- id: C:lemma/x\n  span: {file: F.lean, lines: \"1-2\"}\n"}], "a span or lines"),
                       ([{"items": "source: {path: PrimesCongruentOne.lean}"}], "the source's path"),
                       ([{"items": "- id: C:lemma/x\n", "code": "theorem x : True := trivial"}], "never reads the Lean"),
                       ([], "no record of what was sent")):
        ok, why = verdict("apart", built, "expert", requests=bad)
        assert not ok and words in why, (bad, why)


def test_length_holds_the_body_to_its_densitys_words(built):
    short = "\n\n".join(body_of("expert").split("\n\n")[:2])
    ok, why = verdict("length", built, "expert", short)
    assert not ok and re.search(r"the body is \d+ words; a pshort at expert is 500 to 900", why)
    assert P.WORDS == {"expert": (500, 900), "student": (500, 800), "everyone": (350, 600)}


def test_footer_catches_another_days_footer_and_another_fabulams(built):
    v, _fab = a_pshort(built, "student")
    ok, why = verdict("footer", built, "student", text=v.text().replace("on 2026-11-22 by", "on 2026-11-21 by"))
    assert not ok and "the footer's day is 2026-11-21, the run's 2026-11-22" in why
    ok, why = verdict("footer", built, "student",
                      text=v.text().replace("*a pshort of primes-congruent-one.fabulam.cosm, at",
                                            "*a pshort of another.fabulam.cosm, at"))
    assert not ok and "the footer names another.fabulam.cosm" in why
    ok, why = verdict("footer", built, "student", text=v.text().rsplit("\n\n", 1)[0] + "\n")
    assert not ok and "not a pshort's footer" in why
    assert TARGET in v.text()
