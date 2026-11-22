"""The fabulam's shipped fixture, and what the first real runs found (0.9, lane M6; the design
`docs/v090-fabulam-design.md`, section 8).

`tests/fixtures/fabula/fabulam/primes-congruent-one.fabulam.cosm` and the three pshorts beside it were made by the
pipeline from Mathlib's `PrimesCongruentOne.lean` (shipped whole, `NOTICE.md`): blind agents stood in as the model,
one fresh agent for each request, and their answers are kept as they were given, the refused tries too, under
`recorded/primes-congruent-one-run/`. Here the fixture is rebuilt from those answers with no model and is the same
byte for byte, and it passes every check of the design's section 2. No mathematician has read it, and nothing of
Lean was built or run.

The rest are the faults the runs on two archives of Mathlib showed in the engine, each held by a test on a small
Lean text of our own.
"""
from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from enough import fabula as FAB
from enough import fabulam as FM
from enough import fabulam_head as HD
from enough import fabulam_job as J
from enough import macrocosm as mc
from enough import repo_engine as RE
from enough import thym_host as H
from enough.thym import checks as C
from enough.thym import run as RUN
from enough.thym.moves import proof as P
from enough.thym.moves import short_value
from enough.thym.values import Value, read_value

FIX = Path(__file__).resolve().parent / "fixtures" / "fabula" / "fabulam"
LEAN = FIX / "PrimesCongruentOne.lean"
FAB_NAME = "primes-congruent-one.fabulam.cosm"
RECORDED = FIX / "recorded" / "primes-congruent-one-run"
NOW = dt.datetime(2026, 11, 22, 12, 0, tzinfo=dt.timezone.utc)
DENSITIES = ("expert", "student", "everyone")
B_CHECKS = ("declarations-found", "lines-resolve", "nothing-invented", "reach-agrees", "comments-covered",
            "nothing-carried")
C_CHECKS = ("cites-resolve", "every-sentence-cited", "yield-cited", "teaching-followed", "no-up-to",
            "example-worked", "nothing-added", "checking-told", "confidence-told", "symbols-worded", "apart",
            "length", "footer")
TEXT_ONLY = "-- Read as text only: enough wrote this file for its tests, and Lean never built it."


def pshort_name(density: str) -> str:
    return f"primes-congruent-one.pshort-{density}-2026-11-22-1200.md"


@pytest.fixture
def counted_runs(tmp_path: Path, monkeypatch):
    """A run's id holds the wall clock and a random tail. For a rebuild that is the same byte for byte the ids
    count up, in a runs folder of the test's own."""
    monkeypatch.setenv("ENOUGH_THYM_ROOT", str(tmp_path / "thym"))
    n = iter(range(1, 10 ** 4))
    monkeypatch.setattr(RUN, "new_run_id", lambda now=None: f"2026-11-22-1200-{next(n):04x}")


def test_the_fixture_rebuilds_byte_for_byte_from_its_recorded_answers_with_no_model(tmp_path: Path, counted_runs):
    proj = tmp_path / "project"
    proj.mkdir()
    lean = proj / LEAN.name
    shutil.copy(LEAN, lean)
    answers = tmp_path / "answers"
    shutil.copytree(RECORDED, answers)
    out = J.run_file_build(proj, lean, mode="model", now=NOW, obtained="public",
                           runtime=J.agent_runtime(proj, answers / "answers-decompiler", who="blind-decompiler"))
    assert out["complete"], out
    got = J.run_entail(proj, proj / FAB_NAME, mode="model", now=NOW,
                       runtime=J.agent_runtime(proj, answers / "answers-entailer", who="blind-entailer"))
    assert [p["path"] for p in got["pshorts"]] == [pshort_name(d) for d in DENSITIES]
    assert not list(answers.rglob("*.request.md"))             # every answer was there: nothing was asked
    for name in [FAB_NAME] + [pshort_name(d) for d in DENSITIES]:
        assert (proj / name).read_bytes() == (FIX / name).read_bytes(), name


def test_the_fixture_passes_every_check_and_says_nothing_of_a_machine_check():
    rep = FAB.lint(FIX / FAB_NAME)
    assert rep.errors == [], [str(e) for e in rep.errors]
    assert [w.check for w in rep.warnings] == ["spine-rule-differs"]   # the lemma that only rephrases: bookkeeping
    doc = mc.yaml_load((FIX / FAB_NAME).read_text(encoding="utf-8"))
    src = doc["source"]
    assert src["target"] == ["Nat.infinite_setOfPred_prime_modEq_one"] and src["target-by"] == "rule"
    assert src["checking"] == {"sorry": 0, "axioms": 0, "native-decide": 0, "built-here": "no"}   # no `said` entry
    assert doc["derived"]["completeness"] == "full"
    assert {r.get("model") for r in doc["derived"]["runs"][1:]} == {"blind-decompiler"}
    ctx = SimpleNamespace(engines={**H.engines(feed=None), **RE.engines()}, now=NOW, coprocessor=None)
    for name in B_CHECKS:
        ok, why = C.verdict(name, Value("fabula", doc), {"t": read_value(LEAN, "text")}, {"modifiers": {}},
                            {"name": "survey"}, ctx)
        assert ok, f"{name}: {why}"
    fab = read_value(FIX / FAB_NAME, "fabula")
    cat, items = P._fabulam(fab, "a fabulam")
    assert [s["density"] for s in doc["shorts"]] == list(DENSITIES)
    for s in doc["shorts"]:
        assert (s["path"], s["entailed"], s["by"]) == (pshort_name(s["density"]), "apart", "blind-entailer")
        text = (FIX / s["path"]).read_text(encoding="utf-8")
        low = text.lower()
        assert "it is not a proof" in low and "whether lean accepts it is not known here" in low
        for word in P.CHECK_WORDS:
            assert word not in low, (s["path"], word)
        v = short_value(text, fabula=fab, order="told", density=s["density"],
                        requests=[{"items": P.pshort_view(cat, items)[0], "density": s["density"]}])
        for name in C_CHECKS:
            ok, why = C.verdict(name, v, {"f": fab}, {"modifiers": {"as": s["density"]}}, {"name": "entail"}, ctx)
            assert ok, f"{s['path']}: {name}: {why}"


def test_the_recorded_answers_are_the_agents_own_and_name_no_source_but_the_request():
    files = sorted(RECORDED.rglob("*.cosm"))
    assert len(files) == 14
    for p in files:
        data = mc.yaml_load(p.read_text(encoding="utf-8"))
        who = "blind-decompiler" if "answers-decompiler" in p.parts else "blind-entailer"
        assert data["engine"] == f"model:{who}" and isinstance(data["output"], str) and data["output"].strip(), p


# ---------------------------------------------------------------------------
# What the runs on two archives found in the engine
# ---------------------------------------------------------------------------

def _archive(tmp_path: Path) -> Path:
    """Three Lean files of our own. `A` writes the bare name `map_one` and imports nothing; `B` declares
    `Thing.map_one`; `C` imports both and uses both."""
    proj = tmp_path / "project"
    lib = proj / "Lib"
    lib.mkdir(parents=True)
    (lib / "A.lean").write_text(f"{TEXT_ONLY}\n\ntheorem a_fact : True := by\n  simpa using map_one\n",
                                encoding="utf-8")
    (lib / "B.lean").write_text(f"{TEXT_ONLY}\n\nnamespace Thing\n\ntheorem map_one : True := trivial\n\n"
                                "end Thing\n", encoding="utf-8")
    (lib / "C.lean").write_text(f"{TEXT_ONLY}\nimport Lib.A\nimport Lib.B\n\ntheorem top : True := by\n"
                                "  have h := Thing.map_one\n  exact a_fact\n", encoding="utf-8")
    return proj


def _rules(stage, plan, info, mode, scaffolds, program):
    from enough.thym.coprocessor import RefusingCoprocessor
    return {"coprocessor": RefusingCoprocessor(), "agent_free": False, "rules": scaffolds, "preflight": None,
            "environment": {}, "root": H.host_root(), "engines": {**H.engines(feed=None), **RE.engines()},
            "calls": None}


def test_a_part_leans_on_another_part_only_where_the_readers_graph_found_the_use(tmp_path: Path):
    """A bare `map_one` in a file that imports nothing is no use of another file's `Thing.map_one`: a last name
    alone makes no link. The head says which crossing declarations each part uses, from the reader's graph."""
    proj = _archive(tmp_path)
    J.run_archive_build(proj, proj / "Lib", mode="rules", why="no model", runtime=_rules, now=NOW, target=["top"])
    head = J.fabulam_path(proj / "Lib")
    hdoc = HD.load(head)
    comps = {c["name"]: c for c in hdoc["nodes"] if c.get("type") == "component"}
    assert "uses" not in comps["Lib.A"] and "uses" not in comps["Lib.B"]
    assert sorted(comps["Lib.C"]["uses"]) == ["C:lemma/Thing.map_one", "C:lemma/a_fact"]

    def relied(file: str) -> list[str]:
        doc = HD.load(HD.part_path(head, file))
        return sorted(n["id"] for n in doc["nodes"] if n.get("type") == "reliance" and n.get("stated-in"))
    assert relied("A.lean") == [] and relied("B.lean") == []
    assert relied("C.lean") == ["C:reliance/Thing.map_one", "C:reliance/a_fact"]
    for part in sorted(head.with_name("lib.fabulam.parts").rglob("*.fabulam.cosm")):
        assert FAB.lint(part).errors == [], part.name


def test_up_to_is_refused_of_a_bound_and_not_of_a_total_or_a_sign():
    assert P.UP_TO_AFTER == FM.UP_TO_AFTER
    for text, bounds in (("a bound of up to n primes", True), ("the values add up to nothing", False),
                         ("the pieces sum up to a finite total", False), ("unique up to isomorphism", False),
                         ("its square is the size, up to a sign", False), ("Up to k of them", True)):
        assert P.holds_up_to(text) is bounds, text
        assert bool(FM._UP_TO_RE.search(text)) is bounds, text


def _lemma(k: int, role: str, reached: str = "yes") -> dict:
    return {"id": f"C:lemma/l{k}", "type": "lemma", "name": f"l{k}", "lean": f"l{k}", "reached": reached,
            "role": role, "says": "For every natural number n the thing holds, " + "and so on, " * 30,
            "method": "It unfolds the definition and counts, " + "step after step, " * 20,
            "uses": [f"C:lemma/l{j}" for j in range(max(0, k - 6), k)], "summary": f"The lemma l{k}.",
            "span": {"file": "X.lean", "lines": f"{k}-{k}"}}


def test_a_file_or_a_head_of_many_items_is_shown_less_by_rule_and_never_past_one_request():
    items = [_lemma(k, ("spine", "support", "bookkeeping")[k % 3]) for k in range(150)]
    sizes = [len(P._yaml(P.fold_rows(items, cut))) for cut in range(len(P.FOLD_CUTS) + 1)]
    assert sizes == sorted(sizes, reverse=True) and sizes[-1] < sizes[0] / 2
    sizes = [len(P._yaml(P.yield_rows(items, cut))) for cut in range(len(P.YIELD_CUTS) + 1)]
    assert sizes == sorted(sizes, reverse=True) and sizes[-1] < sizes[0] / 2
    small, left = P.pshort_view({"name": "x"}, items[:6])
    assert left == [] and "method:" in small                # a small fabulam is carried whole
    text, left = P.pshort_view({"name": "x"}, items)
    assert len(text) <= min(P.PSHORT_CHARS, P.REQUEST_CHARS - P.PSHORT_ROOM)
    assert left[:2] == ["the bookkeeping lemmas", "the support lemmas' method"] and len(left) > 2
    assert "what an item says twice" in left
    assert P.pshort_footer({"name": "x"}, None, "expert", "2026-11-22", "m", left).count("left out for length") == 1


def test_one_claim_whose_verdict_cannot_be_taken_is_kept_as_not_checkable_and_a_claim_may_name_two_declarations():
    data = {"audit": [{"lines": "3-4", "verdict": "claim",
                       "claim": {"name": "a note", "says": "It says so.", "checked": "partial",
                                 "false-as-written": {"pending": "cannot tell"}}},
                      {"lines": "9", "verdict": "agrees"}]}
    assert P._claim_unsettled(data, 'lines 3-4: false-as-written is "yes" or "no", never pending') is True
    assert data["audit"][0]["claim"]["checked"] == "not-checkable"
    assert P._claim_unsettled(data, "lines 3-4: again") is False       # once: it is the weakest word already
    assert P._claim_unsettled(data, "lines 9: verdict is agrees") is False
    assert P._claim_unsettled(data, "the answer holds no audit: list") is False
    items = [{"id": "C:lemma/a", "type": "lemma", "lean": "a", "span": {"file": "X.lean", "lines": "1-2"}},
             {"id": "C:lemma/b", "type": "lemma", "lean": "b", "span": {"file": "X.lean", "lines": "3-4"}}]
    rows = [{"lines": "6", "kind": "note", "on": ""}]
    answer = {"audit": [{"lines": "6", "verdict": "claim",
                         "claim": {"name": "both", "says": "Both hold.", "checked": "yes", "by": "a, b, nothing"}}]}
    done, new = P.parse_comments(answer, fname="X.lean", cat={}, items=items, rows=rows, taken=set())
    assert new[0]["by"] == ["C:lemma/a", "C:lemma/b"] and done[0]["claim"] == new[0]["id"]


def test_a_final_theorem_under_a_variable_is_surveyed_and_only_a_lemma_carries_scope(tmp_path: Path):
    """The manifest opens `scope` (the lines of the variables that hold) on a lemma. A final theorem under a
    `variable` once carried it too, and the shared closed list of a dependency's scope refused the survey."""
    proj = tmp_path / "project"
    proj.mkdir()
    lean = proj / "Scoped.lean"
    lean.write_text(f"{TEXT_ONLY}\n\nvariable {{n : Nat}}\n\ntheorem helper : n = n := rfl\n\n"
                    "theorem final : n + 0 = n := by\n  have h := helper (n := n)\n  simp\n", encoding="utf-8")
    out = J.run_file_build(proj, lean, mode="rules", why="no model", runtime=_rules, now=NOW)
    assert [r["stage"] for r in out["ran"]] == ["survey"], out
    doc = mc.yaml_load((proj / "scoped.fabulam.cosm").read_text(encoding="utf-8"))
    its = {n["id"]: n for n in doc["nodes"]}
    assert "scope" in its["C:lemma/helper"] and "scope" not in its["C:statement/final"]
    assert FAB.lint(proj / "scoped.fabulam.cosm").errors == []


def test_the_folds_request_shows_no_lemma_the_targets_do_not_reach_and_says_which_step_is_none():
    items = [_lemma(1, "spine"), {**_lemma(2, "support", reached="no"), "role": None},
             {"id": "C:reliance/r", "type": "reliance", "name": "r", "lean": ["r"], "gives": "It gives."}]
    assert [r["id"] for r in P.fold_rows([i for i in items if i.get("reached") != "no"])] == [
        "C:lemma/l1", "C:reliance/r"]
    stage = {"slug": "s", "name": "S", "number": 1, "stage": "reduction", "says": "It says.", "plain": "It does.",
             "plain-if": "none", "obvious": "none: the file's way is the obvious one"}
    kinds = ("lemma", "statement", "step", "definition")
    with pytest.raises(ValueError) as e:
        P.parse_stages({"stages": [{**stage, "steps": ["C:lemma/nowhere"]}]}, items=items, taken=set(),
                       sources=["X.lean"], step_kinds=kinds, atem_of=None)
    assert "'C:lemma/nowhere' is no item shown" in str(e.value)
    with pytest.raises(ValueError) as e:
        P.parse_stages({"stages": [{**stage, "steps": ["C:reliance/r"]}]}, items=items, taken=set(),
                       sources=["X.lean"], step_kinds=kinds, atem_of=None)
    assert "C:reliance/r is a reliance" in str(e.value)


def test_the_atems_line_is_counted_where_the_model_is_asked_again():
    from enough import fabulam_prompts as FP
    assert "every run of letters or of digits is one word" in FP.ATEM_COUNT
    msgs = FP.stages_messages({}, {"name": Value("string", "x"), "items": Value("string", "[]")})
    assert FP.ATEM_COUNT in msgs[-1]["content"]
