"""The fabulam's jobs (0.9; `enough/fabulam_job.py`, `enough/fabulam_head.py`; Thym 20.13; the design
`docs/v090-fabulam-design.md`, sections 4.1 to 4.3, 5.2 and 6).

The file job: the six programs of `decompile-lean.thym` run in order over Mathlib's `PrimesCongruentOne.lean` (the
shipped fixture), each landing the fabulam with its run in `derived.runs`; a stopped build taken up again from disk;
the states a card shows. The archive job: a head over three small Lean files of our own
(`tests/fixtures/fabula/fabulam/own/Parity/`, never built, each saying so in its first line): its parts, the
declarations that cross, `statements-agree`, summaries upward, and the fold.

Every model answer is HAND-RECORDED (`tests/fixtures/fabula/fabulam/recorded/`; a person wrote each, and each file
says so). No model runs, nothing of Lean is run, and every run replays with no reader.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from enough import fabula as FAB
from enough import fabulam_head as HD
from enough import fabulam_job as J
from enough import macrocosm as mc
from enough import thym_host as H
from enough.canon_derive import DeriveCancelled
from enough.thym import Refusal
from enough.thym import check as ck
from enough.thym import parse as ps
from enough.thym import plan as pl
from enough.thym import run as RUN
from enough.thym import trace as T
from tests.test_fabulam_moves import (DEFAULT_CHECKING, LEAN, MIDDLE, NOW, OWN, REC, SPINE, TARGET, Recorded, build,
                                      engines, fab_path, fabulam, items_of, project, runtime)  # noqa: F401

PRIMES = REC / "primes-congruent-one"
CLONE = Path("/Users/m3u/METMcloud/fabulac-test-repos/mathlib4")


# ---------------------------------------------------------------------------
# The programs
# ---------------------------------------------------------------------------

def _compiled(name: str):
    text = (H.SHIPPED_PROGRAMS / name).read_text(encoding="utf-8")
    c = ck.check(ps.parse(text, path=name))
    assert not isinstance(c, Refusal), str(c)
    return c


def test_the_three_programs_compile_and_plan_and_only_the_survey_asks_nothing():
    assert J.STAGES == ("survey-the-proof", "read-the-proof", "audit-the-comments", "fit-the-wording",
                        "fold-the-argument", "raise-the-questions")
    assert J.program_path().name == "decompile-lean.thym" and J.program_path().parent == H.SHIPPED_PROGRAMS
    c = _compiled("decompile-lean.thym")
    assert [p.name for p in c.programs()] == list(J.STAGES)
    asks = {}
    for prog in c.programs():
        rows = [{"name": p.name, "type": p.type, "path": f"{p.name}.in", "sha256": "0" * 64} for p in prog.takes]
        plan = pl.plan(c, rows, program=prog.name)
        assert not isinstance(plan, Refusal), (prog.name, str(plan))
        asks[prog.name] = any(n.get("asks") for n in plan["nodes"] if n["type"] == "node")
    assert asks == {"survey-the-proof": False, "read-the-proof": True, "audit-the-comments": True,
                    "fit-the-wording": True, "fold-the-argument": True, "raise-the-questions": True}
    plan = pl.plan(c, [{"name": "t", "type": "text", "path": "t.lean", "sha256": "0" * 64},
                       {"name": "f", "type": "fabula", "path": "f.cosm", "sha256": "0" * 64}], program="read-the-proof")
    kept = [n for n in plan["nodes"] if n.get("keeps") == ["its-own-file"]]
    assert len(kept) == 1 and "derive" in str(kept[0])      # the reading keeps the contract block of the file
    a = _compiled("decompile-lean-archive.thym")
    assert [p.name for p in a.programs()] == list(J.HEAD_STAGES)
    e = _compiled("entail-pshort.thym")
    assert [p.name for p in e.programs()] == ["entail-the-pshorts"]
    assert "gives expert: short, student: short, everyone: short" in (H.SHIPPED_PROGRAMS / "entail-pshort.thym"
                                                                      ).read_text(encoding="utf-8")
    assert "the Lean is never read here; nothing is built or run" in (H.SHIPPED_PROGRAMS / "entail-pshort.thym"
                                                                       ).read_text(encoding="utf-8")


def test_under_rules_every_call_but_the_survey_is_refused_at_plan_time(project: Path):  # noqa: F811
    out = build(project, mode="rules", scaffolds=True)
    assert [r["stage"] for r in out["ran"]] == ["survey"] and not out["complete"]
    r = out["refusal"]
    assert (r["check"], r["program"]) == ("rules", "read-the-proof") and "outline only" in r["message"]
    from enough.thym import declarations as dc
    d = dc.load()
    assert dc.chosen(d["derive"].view(1), as_word="proof")["scaffold"] is None
    for axis in ("comments", "fit", "yield", "stages"):
        assert dc.chosen(d["construe"].view(1), as_word=axis)["scaffold"] is None


# ---------------------------------------------------------------------------
# The file job
# ---------------------------------------------------------------------------

def test_with_no_model_the_survey_lands_the_outline_and_the_read_waits(project: Path):  # noqa: F811
    lean = project / LEAN.name
    st = J.file_state(project, lean)
    assert (st["state"], st["exists"], st["landed"], st["of"], st["next"]) == ("none", False, 0, 5,
                                                                              "survey-the-proof")
    assert st["line"] == "no fabulam yet: building it writes primes-congruent-one.fabulam.cosm"
    assert st["targets"] == [TARGET] and st["checking"] is None
    out = build(project, mode="rules", why="the model is not running")
    assert [r["stage"] for r in out["ran"]] == ["survey"] and not out["complete"]
    r = out["refusal"]
    assert r["check"] == "no-model" and r["program"] == "read-the-proof" and r["message"].endswith(
        "; no model is running")
    assert "read-the-proof waits" in out["message"]
    st = out["state"]
    assert (st["state"], st["landed"], st["next"]) == ("outline", 1, "read-the-proof")
    assert st["line"] == "an outline: the survey landed by rules; reading waits for a model"
    assert st["checking"] == DEFAULT_CHECKING              # the card shows the sentence of P:claim/checking, in full
    assert fabulam(project)["derived"]["completeness"] == "outline"


def test_the_six_stage_job_lands_a_whole_fabulam_that_passes_its_own_checks(project: Path):  # noqa: F811
    cp = Recorded(PRIMES)
    out = build(project, cp)
    assert out["complete"] and "refusal" not in out, out
    assert [r["stage"] for r in out["ran"]] == ["survey", "read", "audit", "fold", "question"]   # no wording: no fit
    assert out["message"] == "primes-congruent-one.fabulam.cosm: every stage landed"
    doc = fabulam(project)
    assert [r["program"] for r in doc["derived"]["runs"]] == [
        "survey-the-proof", "read-the-proof", "audit-the-comments", "fold-the-argument", "raise-the-questions"]
    assert doc["derived"]["completeness"] == "full"
    st = out["state"]
    assert (st["state"], st["line"], st["landed"], st["of"], st["next"]) == (
        "complete", "built: every stage landed", 5, 5, None)
    assert [s["stage"] for s in st["stages"] if s["landed"]] == ["survey", "read", "audit", "fold", "question"]
    # every check of 2.A: no error; the one warning is the rule's candidate the reading called bookkeeping
    rep = FAB.lint(fab_path(project))
    assert rep.errors == [], [str(e) for e in rep.errors]
    assert [(w.check, w.item) for w in rep.warnings] == [("spine-rule-differs", f"C:lemma/{MIDDLE}")]
    it = items_of(doc)
    spine, mid = it[f"C:lemma/{SPINE}"], it[f"C:lemma/{MIDDLE}"]
    assert (spine["role"], mid["role"]) == ("spine", "bookkeeping") and spine["why"].startswith("Without it")
    assert spine["leans-on"] == [f"C:reliance/{s}" for s in (
        "infinitely-many-primes", "a-cyclotomic-value-is-large", "a-root-is-prime-to-p", "a-root-has-order-k",
        "the-order-divides-p-minus-one")]
    assert it["C:reliance/a-root-has-order-k"]["lean"] == ["isRoot_cyclotomic_iff.mp"]     # as the file writes it
    assert it["C:reliance/infinitely-many-primes"]["stance"] == "assumed"
    y = it["P:yield/what-the-proof-delivers"]
    assert (y["beyond"], y["of"], y["bound"], y["confidence"]) == ("yes", f"C:statement/{TARGET}", "none", "medium")
    assert y["provenance"]["confidence"] == 0.35 and y["grounds"] == [{"of": f"C:lemma/{SPINE}", "lines": "33-59"}]
    case = it["P:case/k-three-n-two"]
    assert (case["from"], case["stands"], case["of"]) == ("worked", "inside", "P:yield/what-the-proof-delivers")
    assert doc["teaching"] == ["C:part/what-must-be-found", "C:part/a-number-built-to-have-the-right-factor",
                               "C:part/from-one-to-many"]
    assert doc["atem"]["of"] == f"C:statement/{TARGET}" and doc["atem"]["line"].startswith("For every whole number k")
    assert [(r["lines"], r["verdict"]) for r in doc["audit"]] == [("1-5", "nothing"), ("10-15", "agrees"),
                                                                 ("26-27", "agrees"), ("67", "agrees")]
    assert it["N:aim/primes-congruent-to-one"]["stance"] == "hearsay"
    # completeness is written by the job, once, after the last program: the stages' move leaves it alone
    assert it["P:claim/checking"]["says"] == DEFAULT_CHECKING
    with pytest.raises(J.BuildError) as e:
        build(project, cp)
    assert e.value.status == 409 and "already built" in str(e.value)


def test_full_is_written_only_when_the_last_program_has_landed(project: Path):  # noqa: F811
    seen: list[str] = []

    def stop() -> bool:
        st = J.file_state(project, project / LEAN.name)
        if st["exists"]:
            seen.append(fabulam(project)["derived"]["completeness"])
        return st["landed"] >= 4                           # stop before the questions
    with pytest.raises(DeriveCancelled):
        build(project, should_stop=stop)
    assert set(seen) == {"outline"}
    st = J.file_state(project, project / LEAN.name)
    assert (st["state"], st["landed"], st["next"]) == ("partway", 4, "raise-the-questions")
    assert st["line"] == "4 of 5 stages landed; the build can take up again from question"
    assert FAB.lint(fab_path(project)).errors == []         # what has landed passes the checks as it stands
    out = build(project, resume_only=True)
    assert [r["stage"] for r in out["ran"]] == ["question"] and out["complete"]
    assert fabulam(project)["derived"]["completeness"] == "full"


def test_a_stopped_build_takes_up_again_from_disk_after_the_last_program_that_landed(project: Path):  # noqa: F811
    def stop() -> bool:
        return J.file_state(project, project / LEAN.name)["landed"] >= 2
    with pytest.raises(DeriveCancelled) as e:
        build(project, should_stop=stop)
    assert "nothing of it was written" in str(e.value)
    st = J.file_state(project, project / LEAN.name)
    assert (st["state"], st["landed"], st["next"]) == ("partway", 2, "audit-the-comments")
    cp = Recorded(PRIMES)
    out = build(project, cp, resume_only=True)
    assert [r["stage"] for r in out["ran"]] == ["audit", "fold", "question"] and out["complete"]
    assert not cp.asked("read")                             # the reading was not asked again


def test_a_file_that_changed_is_built_again_from_the_survey_and_one_that_is_gone_keeps_its_fabulam(project: Path):  # noqa: F811
    build(project, mode="rules", why="no model")
    lean = project / LEAN.name
    lean.write_text(lean.read_text(encoding="utf-8") + "\n-- a line added later\n", encoding="utf-8")
    st = J.file_state(project, lean)
    assert (st["state"], st["moved"], st["landed"], st["next"]) == ("moved", True, 0, "survey-the-proof")
    assert st["line"].startswith("the Lean file has changed since its fabulam was surveyed")
    with pytest.raises(J.BuildError) as e:
        build(project, mode="rules", why="no model", resume_only=True)
    assert e.value.status == 409 and "nothing to take up again" in str(e.value)
    out = build(project, mode="rules", why="no model")
    assert [r["stage"] for r in out["ran"]] == ["survey"] and out["state"]["state"] == "outline"
    assert fabulam(project)["source"]["lines"] == 77
    lean.unlink()
    st = J.file_state(project, lean)
    assert (st["state"], st["line"]) == ("gone", "the Lean file is not there any more; its fabulam stays as it is")
    with pytest.raises(J.BuildError) as e:
        build(project, mode="rules", why="no model")
    assert e.value.status == 404


def test_a_file_that_ends_in_more_than_three_results_waits_for_the_person_to_pick(tmp_path: Path):
    proj = tmp_path / "project"
    proj.mkdir()
    shutil.copy(OWN / "Many.lean", proj / "Many.lean")
    lean = proj / "Many.lean"
    assert J.targets_by_rule(lean) == ["Many.one_le_two", "Many.two_le_three", "Many.three_le_four",
                                       "Many.four_le_five"]
    st = J.file_state(proj, lean)
    assert (st["state"], st["line"]) == ("pick", "this file ends in 4 results: choose the one to tell")
    out = J.run_file_build(proj, lean, mode="rules", why="no model", runtime=runtime(), now=NOW)
    assert out["ran"] == [] and out["refusal"]["check"] == "pick" and not (proj / "many.fabulam.cosm").exists()
    out = J.run_file_build(proj, lean, mode="rules", why="no model", runtime=runtime(), now=NOW,
                           target=["Many.two_le_three"])
    assert [r["stage"] for r in out["ran"]] == ["survey"]
    doc = mc.yaml_load((proj / "many.fabulam.cosm").read_text(encoding="utf-8"))
    assert doc["source"]["target"] == ["Many.two_le_three"] and doc["source"]["target-by"] == "given"
    assert [n["id"] for n in doc["nodes"] if n["type"] == "statement"] == ["C:statement/Many.two_le_three"]
    # the person's choice is kept by the next build, which leaves it out
    again = J.run_file_build(proj, lean, mode="rules", why="no model", runtime=runtime(), now=NOW, restart=True)
    assert again["state"]["targets"] == ["Many.two_le_three"] and again["state"]["target_by"] == "given"


def test_with_a_public_wording_the_fit_runs_before_the_fold_and_without_lean(project: Path):  # noqa: F811
    shutil.copy(OWN / "wording.md", project / "wording.md")
    cp = Recorded(PRIMES)
    out = build(project, cp, wording="wording.md")
    assert out["complete"], out
    assert [r["stage"] for r in out["ran"]] == ["survey", "read", "audit", "fit", "fold", "question"]
    sent = cp.asked("fit")[0]
    assert "code" not in sent and "minFac" not in "".join(sent.values()) and "leave remainder 1" in sent["wording"]
    doc = fabulam(project)
    it = items_of(doc)
    assert doc["source"]["wording"] == "wording.md" and it["E:work/wording"]["stance"] == "hearsay"
    fit = it[f"P:fit/{TARGET}"]
    assert (fit["of"], fit["against"], fit["how"], fit["differences"]) == (f"C:statement/{TARGET}",
                                                                            "E:work/wording", "same", [])
    assert FAB.lint(fab_path(project)).errors == []
    assert out["state"]["wording"] == "wording.md" and out["state"]["of"] == 6


def test_a_run_replays_from_its_record_with_no_reader_and_no_model(project: Path, tmp_path: Path):  # noqa: F811
    """A recorded engine answer (the reader's outline, graph and reach) and a recorded model answer are replayed:
    the survey's run and the reading's run give their outputs again with no engine and no coprocessor. A run's
    inputs must be as they were, so the outline is put back before the reading's run is replayed (the job lands
    over it)."""
    root = tmp_path / "root"
    lean, fab = project / LEAN.name, fab_path(project)
    first = J.run_file_build(project, lean, mode="rules", why="no model", runtime=runtime(None, root), now=NOW)
    outline = fab.read_bytes()

    def stop() -> bool:
        return J.file_state(project, lean)["landed"] >= 2
    with pytest.raises(DeriveCancelled):
        J.run_file_build(project, lean, mode="model", runtime=runtime(Recorded(PRIMES), root), now=NOW,
                         should_stop=stop)
    read_run = next(r for r in fabulam(project)["derived"]["runs"] if r["program"] == "read-the-proof")["run"]
    survey_dir = Path(first["ran"][0]["trace"]).parent
    read_dir = T.find(read_run, root=root).parent
    assert sorted(p.name for p in (survey_dir / "candidates").glob("*-e*.cosm"))      # the reader's answers, recorded
    assert sorted(p.name for p in (read_dir / "candidates").glob("*.cosm"))
    fab.write_bytes(outline)
    for run_dir in (survey_dir, read_dir):
        again = RUN.replay(run_dir, inputs_root=project, root=tmp_path / "replays", engines={})
        assert isinstance(again, T.Trace) and again.replay["identical"], (run_dir.name, getattr(again, "replay", again))


def test_the_fixture_is_mathlibs_file_byte_for_byte():
    assert LEAN.read_text(encoding="utf-8").startswith("/-\nCopyright (c) 2020 Riccardo Brasca. All rights reserved.")
    notice = (LEAN.parent / "NOTICE.md").read_text(encoding="utf-8")
    assert "6ebcce37335bcb6bca64596e5d57bb3035648030" in notice and "Apache License, Version 2.0" in notice
    assert "Copyright (c) 2020 Riccardo Brasca. All rights reserved." in notice
    theirs = CLONE / "Mathlib" / "NumberTheory" / "PrimesCongruentOne.lean"
    if not theirs.is_file():
        pytest.skip("the Mathlib clone is not on this machine")
    assert theirs.read_bytes() == LEAN.read_bytes()


# ---------------------------------------------------------------------------
# The archive job: a head over three small Lean files of our own
# ---------------------------------------------------------------------------

@pytest.fixture
def archive(tmp_path: Path) -> Path:
    proj = tmp_path / "project"
    proj.mkdir()
    shutil.copytree(OWN / "Parity", proj / "Parity")
    return proj


def load(p: Path) -> dict:
    return mc.yaml_load(p.read_text(encoding="utf-8"))


def test_the_three_files_say_in_their_first_line_that_they_are_read_as_text_only():
    for p in sorted((OWN / "Parity").glob("*.lean")) + [OWN / "Many.lean"]:
        assert p.read_text(encoding="utf-8").split("\n")[0] == (
            "-- Read as text only: enough wrote this file for its tests, and Lean never built it."), p.name


def test_a_head_over_three_files_is_built_part_by_part_and_folded(archive: Path):
    cp = Recorded(REC / "parity")
    out = J.run_archive_build(archive, archive / "Parity", mode="model", runtime=runtime(cp), now=NOW,
                              target=["Parity.isEven_add"])
    assert out["complete"] and "refusal" not in out, out
    assert out["message"] == ("parity.fabulam.cosm: every stage landed; 3 of 3 files read; 0 not reached and left as "
                              "outlines")
    head_path = archive / "parity.fabulam.cosm"
    parts = {n: archive / "parity.fabulam.parts" / f"{n}.fabulam.cosm" for n in ("Basic", "Double", "Sum")}
    # every volume passes its own checks, parts-resolve and statements-agree among them
    for p in [head_path, *parts.values()]:
        rep = FAB.lint(p)
        assert rep.errors == [], (p.name, [str(e) for e in rep.errors])
    head = load(head_path)
    # the files were read in the order of the imports, and each part is named in that order
    assert [p["file"] for p in out["parts"]] == ["Basic.lean", "Double.lean", "Sum.lean"]
    assert [(p["uri"], p["path"]) for p in head["parts"]] == [
        (f"oes:fabula/parity--Parity-{n}", f"parity.fabulam.parts/{n}.fabulam.cosm") for n in ("Basic", "Double",
                                                                                              "Sum")]
    for p in head["parts"]:
        assert p["sha256"] == HD._sha(archive / p["path"])
    it = items_of(head)
    # the declarations that cross, stated in the head with what the part says, and where each is told
    st, iseven, dbl = (it["C:statement/Parity.isEven_add"], it["C:definition/Parity.IsEven"],
                       it["C:lemma/Parity.double_add"])
    assert (st["depth"], iseven["depth"], dbl["depth"]) == (0, 1, 1)
    assert st["uses"] == ["C:definition/Parity.IsEven", "C:lemma/Parity.double_add"]
    assert st["told-in"] == "oes:fabula/parity--Parity-Sum/C/statement/Parity.isEven_add"
    assert dbl["told-in"] == "oes:fabula/parity--Parity-Double/C/lemma/Parity.double_add"
    double, summ, basic = load(parts["Double"]), load(parts["Sum"]), load(parts["Basic"])
    theirs = items_of(double)["C:lemma/Parity.double_add"]
    assert (dbl["says"], dbl["digest"]) == (theirs["says"], theirs["digest"])
    assert dbl["says"] == "For all natural numbers a and b, 2 · a + 2 · b = 2 · (a + b)."
    assert iseven["says"] == items_of(basic)["C:definition/Parity.IsEven"]["says"]
    # the fold judged the crossing lemma for the whole argument, beside its role in its own part
    assert (theirs["role"], dbl["role-there"], dbl["role"]) == ("support", "support", "spine")
    assert dbl["why"].startswith("Without it the two halves could not be gathered into one.")
    # a part that uses a crossing declaration relies on the head's statement of it, and the two agree
    rel = items_of(summ)["C:reliance/Parity.double_add"]
    assert (rel["on"], rel["stance"], rel["lean"], rel["digest"]) == ("part", "deduced", ["Parity.double_add"],
                                                                      dbl["digest"])
    assert rel["stated-in"] == "oes:fabula/parity/C/lemma/Parity.double_add" and rel["gives"] == dbl["says"]
    assert items_of(summ)["C:statement/Parity.isEven_add"]["leans-on"] == ["C:reliance/Parity.IsEven",
                                                                         "C:reliance/Parity.double_add"]
    assert summ["head"] == basic["head"] == "oes:fabula/parity"
    assert summ["source"]["path"] == "../Parity/Sum.lean" and summ["source"]["module"] == "Parity.Sum"
    # in a part: reached and depth are the archive's, carries counts within the part's own file
    b = items_of(basic)
    assert (b["C:definition/Parity.IsEven"]["reached"], b["C:definition/Parity.IsEven"]["depth"],
            b["C:definition/Parity.IsEven"]["carries"]) == ("yes", 1, 0)
    assert b["C:lemma/Parity.isEven_double"]["reached"] == "no" and "role" not in b["C:lemma/Parity.isEven_double"]
    assert "says" not in b["C:lemma/Parity.isEven_double"]              # what the targets do not reach is not read
    assert basic["atem"]["of"] == "C:definition/Parity.IsEven"          # a part with no final theorem
    assert not [n for n in basic["nodes"] if n["type"] in ("statement", "yield")]
    # summaries upward: each component, and the target's yield with its worked example
    comp = it["C:component/Parity.Sum"]
    assert comp["does"] == summ["atem"]["line"] and comp["stages"] == ["What must be shown", "Adding the halves"]
    assert comp["counts"] == {"declarations": 1, "reached": 1, "spine": 0} and comp["completeness"] == "full"
    assert comp["told-in"] == "oes:fabula/parity--Parity-Sum" and comp["offers"] == ["C:statement/Parity.isEven_add"]
    y = it["P:yield/what-the-proof-delivers"]
    assert y["told-in"] == "oes:fabula/parity--Parity-Sum/P/yield/what-the-proof-delivers"
    assert y["says"] == items_of(summ)["P:yield/what-the-proof-delivers"]["says"]
    assert y["grounds"] == [{"of": "C:statement/Parity.isEven_add", "lines": "14-17"}]
    assert it["P:case/six-and-ten"]["of"] == "P:yield/what-the-proof-delivers"
    # the fold: the head's own stages, teaching order, reading and atem, from the summaries, with no Lean
    assert head["teaching"] == ["C:part/what-must-be-shown", "C:part/the-doubles-add"]
    assert it["C:part/the-doubles-add"]["steps"] == ["C:lemma/Parity.double_add"]
    assert head["atem"]["line"].startswith("For all natural numbers m and n") and head["derived"]["completeness"] == \
        "full"
    sent = cp.asked("head")[0]
    assert set(sent) == {"fabulam", "name", "components", "crossing", "yields"}
    assert "rw [" not in "".join(sent.values()) and "obtain" not in "".join(sent.values())
    assert "Parity.double_add" in sent["crossing"] and "role-there: support" in sent["crossing"]
    # no request held more than one file: each reading named its own file and saw its neighbours by statement only
    read_sum = cp.asked("read.Sum")[0]
    assert read_sum["path"] == "Sum.lean" and "Parity.double_add: For all natural numbers a and b" in \
        read_sum["neighbours"]
    assert "Nat.mul_add" not in read_sum["code"]
    st = J.archive_state(archive, archive / "Parity")
    assert (st["state"], st["files"], st["read"], st["unreached"]) == ("complete", 3, 3, 0)
    assert st["head_line"] == "3 of 3 files read; 0 not reached and left as outlines"
    assert [(p["file"], p["state"], p["tied"]) for p in st["parts"]] == [("Basic.lean", "complete", True),
                                                                        ("Double.lean", "complete", True),
                                                                        ("Sum.lean", "complete", True)]


def test_a_head_of_more_parts_than_one_request_carries_folds_in_rounds(archive: Path, monkeypatch):
    """The design's 4.4: a head with more than `HEAD_PARTS` parts folds in rounds, then once over the rounds' notes."""
    from enough.thym.moves import proof as P
    from tests.test_fabulam_moves import recorded
    monkeypatch.setattr(P, "HEAD_PARTS", 2)
    notes = ["notes:\n  - 'Parity.Basic says what even means, and Parity.Double adds two doubles.'\n",
             "notes:\n  - 'Parity.Sum shows the sum of two even numbers is even.'\n"]
    cp = Recorded(REC / "parity", {"head": [*notes, recorded(REC / "parity", "head")]})
    out = J.run_archive_build(archive, archive / "Parity", mode="model", runtime=runtime(cp), now=NOW,
                              target=["Parity.isEven_add"])
    assert out["complete"], out
    asked = cp.asked("head")
    assert [a.get("round") for a in asked] == ["1 of 2", "2 of 2", None]
    assert "components" not in asked[2] and "Parity.Sum shows the sum" in asked[2]["notes"]
    assert asked[0]["components"].count("- id: C:component/") == 2
    assert FAB.lint(archive / "parity.fabulam.cosm").errors == []


def test_a_file_the_target_does_not_reach_is_outlined_by_rule_and_never_read(archive: Path):
    shutil.copy(OWN / "Many.lean", archive / "Parity" / "Many.lean")      # a fourth file, of no use to the target
    cp = Recorded(REC / "parity")
    out = J.run_archive_build(archive, archive / "Parity", mode="model", runtime=runtime(cp), now=NOW,
                              target=["Parity.isEven_add"])
    assert out["complete"], out
    assert out["state"]["head_line"] == "3 of 4 files read; 1 not reached and left as outlines"
    assert not [k for k, _ in cp.sent if k.endswith(".Many")]              # no model read the unreached file
    head = load(archive / "parity.fabulam.cosm")
    comp = items_of(head)["C:component/Parity.Many"]
    assert comp["does"].startswith("No declaration of it is reached from the targets")
    assert comp["counts"] == {"declarations": 4, "reached": 0, "spine": 0} and comp["completeness"] == "outline"
    assert comp["told-in"] == "oes:fabula/parity--Parity-Many"
    path = archive / "parity.fabulam.parts" / "Many.fabulam.cosm"
    part = load(path)
    assert part["derived"]["completeness"] == "outline"
    assert [r["program"] for r in part["derived"]["runs"]] == ["survey-the-proof"]
    assert {x["reached"] for x in part["nodes"] if x["type"] in ("lemma", "statement", "definition")} == {"no"}
    assert not [x for x in part["nodes"] if x["type"] == "statement"] and part["source"]["target"] == [
        "Parity.isEven_add"]                                               # a part repeats the head's target
    assert FAB.lint(path).errors == [] and FAB.lint(archive / "parity.fabulam.cosm").errors == []
    assert "parity.fabulam.parts/Many.fabulam.cosm" in [p["path"] for p in head["parts"]]


def test_with_no_model_the_head_and_every_part_are_outlined_and_the_job_takes_up_again(archive: Path):
    out = J.run_archive_build(archive, archive / "Parity", mode="rules", why="the model is not running",
                              runtime=runtime(), now=NOW, target=["Parity.isEven_add"])
    assert not out["complete"] and out["refusal"]["check"] == "no-model"
    st = out["state"]
    assert st["state"] == "partway" and [(p["file"], p["state"], p["tied"]) for p in st["parts"]] == [
        ("Basic.lean", "outline", True), ("Double.lean", "outline", True), ("Sum.lean", "outline", True)]
    for p in [archive / "parity.fabulam.cosm", *(archive / "parity.fabulam.parts").glob("*.cosm")]:
        assert FAB.lint(p).errors == [], p.name
    cp = Recorded(REC / "parity")
    again = J.run_archive_build(archive, archive / "Parity", mode="model", runtime=runtime(cp), now=NOW)
    assert again["complete"], again
    assert [r["stage"] for r in again["ran"] if r.get("file") == "Basic.lean"] == ["read", "audit", "fold",
                                                                                   "question"]
    assert again["state"]["targets"] == ["Parity.isEven_add"]             # the person's target was kept


def test_survey_refuses_past_the_band_in_the_python_bands_words(tmp_path: Path):
    proj = tmp_path / "project"
    (proj / "Big").mkdir(parents=True)
    for k in range(61):
        (proj / "Big" / f"F{k}.lean").write_text(f"theorem t{k} : True := trivial\n", encoding="utf-8")
    with pytest.raises(RuntimeError) as e:
        J.run_archive_build(proj, proj / "Big", mode="rules", why="no model", runtime=runtime(), now=NOW,
                            target=["t0"])
    assert "more than sixty Lean files: past what this build reads" in str(e.value)
    shutil.rmtree(proj / "Big")
    (proj / "Long").mkdir()
    (proj / "Long" / "L.lean").write_text("theorem t : True := trivial\n" + "-- a line\n" * 12001, encoding="utf-8")
    with pytest.raises(RuntimeError) as e:
        J.run_archive_build(proj, proj / "Long", mode="rules", why="no model", runtime=runtime(), now=NOW)
    assert "more than twelve thousand lines of Lean: past what this build reads" in str(e.value)


def test_where_a_fabulam_lives_and_what_the_host_knows_before_the_survey(tmp_path: Path):
    clone = tmp_path / "work" / "lib4"
    (clone / "Lib" / "Num").mkdir(parents=True)
    (clone / "lean-toolchain").write_text("leanprover/lean4:v4.37.0-rc1\n", encoding="utf-8")
    (clone / "LICENSE").write_text("Apache License\nVersion 2.0, January 2004\n", encoding="utf-8")
    lean = clone / "Lib" / "Num" / "PrimesCongruentOne.lean"
    shutil.copy(LEAN, lean)
    root, where = HD.home(lean)
    assert (root, where) == (clone, tmp_path / "work")       # beside the folder that holds lean-toolchain
    fab = J.fabulam_path(lean)
    assert fab == tmp_path / "work" / "primes-congruent-one.fabulam.cosm"
    doc = HD.catalog_alone(lean, target=None, said="It builds.", said_by="A maintainer")
    src = doc["source"]
    assert (src["path"], src["toolchain"], src["module"]) == ("lib4/Lib/Num/PrimesCongruentOne.lean",
                                                             "leanprover/lean4:v4.37.0-rc1",
                                                             "Lib.Num.PrimesCongruentOne")
    assert src["checking"] == {"said": "It builds.", "said-by": "A maintainer"} and doc["nodes"] == []
    assert "target" not in src                               # the rule finds it at the survey
    head = J.fabulam_path(clone / "Lib" / "Num")
    assert head == tmp_path / "work" / "num.fabulam.cosm"
    assert HD.part_path(head, "Sub/File.lean") == tmp_path / "work" / "num.fabulam.parts" / "Sub" / "File.fabulam.cosm"
    out = J.run_file_build(tmp_path / "work", lean, mode="rules", why="no model", runtime=runtime(), now=NOW)
    got = mc.yaml_load(fab.read_text(encoding="utf-8"))
    assert got["source"]["toolchain"] == "leanprover/lean4:v4.37.0-rc1" and out["state"]["state"] == "outline"
    assert got["source"]["module"] == "Lib.Num.PrimesCongruentOne"
    means = next(n for n in got["nodes"] if n["id"] == "R:means/lean")
    assert means["version"] == "leanprover/lean4:v4.37.0-rc1"
