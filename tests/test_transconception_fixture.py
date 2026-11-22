"""Transconception, phase 9 (0.8): tally's transconception as the conformance fixture
(`tests/fixtures/fabula/transconception/tally/`, made by `tests/make_tally_transconception.py`).

The folder is a Thym conformance suite of its own (THYM 24.3's shape): the text's programs of a transconception, the
stage fabulacs they ran on, and every run recorded, from `ground repo with f` to `entail f as code in rust with drawn`.
These tests hold it: the suite conforms read alone, in a copy with nothing beside it; every replay re-runs byte for
byte with no model and no engine; the stages chain (each run's output is the next run's input); every check of the
lint and both gates say on each stage what the folder recorded they say; what is simulated says so and no evidence
is claimed; tally's own fixture is beside it, untouched; and the maker makes the folder again, the same.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from enough import fabula as FAB
from enough import macrocosm as mc
from enough import transconception as tc
from enough.thym import conform as CF
from enough.thym import run as RUN
from enough.thym.values import digest_path

import make_tally_transconception as MK

FIX = MK.DEST
INPUTS = FIX / "inputs"
LANDED = FIX / "landed"
RUNS = [s for s in MK.PATH if s[0] == "run"]


def _load(p: Path) -> dict:
    return mc.yaml_load(p.read_text(encoding="utf-8"))


def _run_dir(program: str, rid: str) -> Path:
    return FIX / "replay" / program / rid


def _files(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


# ---------------------------------------------------------------------------
# the suite: conforms, read alone
# ---------------------------------------------------------------------------

def test_the_fixture_conforms_read_alone(tmp_path):
    """A copy of the folder with nothing beside it conforms whole: every program compiles, enumerates, compiles back
    and plans as expected; `ground-the-fabulac`, whose plan asks nothing, runs again to its recording's outputs; every
    recorded run replays to its outputs."""
    alone = tmp_path / "alone" / "tally"
    shutil.copytree(FIX, alone)
    rep = CF.conform(alone, root=tmp_path / "runs")
    assert rep.ok, "\n".join(ln for ln in rep.lines if not ln.startswith("pass"))
    assert not [ln for ln in rep.lines if ln.startswith("skip")], rep.lines
    replays = [ln for ln in rep.lines if "re-runs to its recorded outputs" in ln]
    assert len(replays) == len(RUNS) == 10
    # the one program whose plan asks nothing runs again, live, through the host's syntax engine, over inputs/tally
    live = [ln for ln in rep.lines if "run lands replay/" in ln]
    assert len(live) == 1 and live[0].startswith("pass  ground-the-fabulac: run lands"), live
    assert sorted(p.stem for p in (FIX / "programs").glob("*.thym")) == sorted(MK.PROGRAMS)


def test_the_fixture_names_nothing_outside_it():
    """No file names a folder of the machine it was made on, and every plan's input lies inside the folder."""
    # (the ground catalogue's own examples name `/home/ann` and `/tmp`: words of the language's text, not folders)
    machine = re.compile(r"/Users/|/private/|/var/folders|METMcloud|METMroot|enough-dev|worktrees")
    for p in sorted(FIX.rglob("*")):
        if p.is_file() and p.suffix in (".cosm", ".json", ".md", ".jsonl", ".thym", ".txt", ""):
            assert not machine.search(p.read_text(encoding="utf-8", errors="replace")), p.relative_to(FIX)
    for plan in sorted(FIX.glob("replay/*/*/*.plan.cosm")) + sorted(FIX.glob("expected/*/plan.cosm")):
        for row in _load(plan)["inputs"]:
            assert not Path(row["path"]).is_absolute() and ".." not in Path(row["path"]).parts, (plan, row)
            assert (FIX / row["path"]).exists(), (plan, row["path"])
    for tr in sorted(FIX.glob("replay/*/*/*.trace.cosm")):
        assert "inputs_root: .\n" in tr.read_text(encoding="utf-8"), tr


# ---------------------------------------------------------------------------
# the replays: byte-stable, with no model and no engine
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("program, rid", [(s[1], s[2]) for s in RUNS], ids=[s[2] for s in RUNS])
def test_every_replay_is_byte_stable_with_no_model_and_no_engine(tmp_path, program, rid):
    run_dir = _run_dir(program, rid)
    want = _files(run_dir / "outputs")
    assert want
    for k in range(2):
        t = RUN.replay(run_dir, root=tmp_path / f"r{k}", inputs_root=FIX, engines={})
        assert t.replay["identical"], t.replay
        assert _files(t.dir / "outputs") == want


# ---------------------------------------------------------------------------
# the path: each stage is the run before it, the plans hold the stages' digests
# ---------------------------------------------------------------------------

def test_the_stages_chain_from_ground_to_entail():
    for _, program, rid, _now, inputs, _rules, gives in RUNS:
        run_dir = _run_dir(program, rid)
        plan = _load(run_dir / f"{rid}.plan.cosm")
        rows = {r["name"]: r for r in plan["inputs"]}
        for name, (typ, _rel) in inputs.items():
            if typ != "folder":
                assert rows[name]["sha256"] == digest_path(FIX / rows[name]["path"]), (rid, name)
        for give, stage in gives.items():
            assert MK._output(run_dir, give).read_bytes() == (INPUTS / stage).read_bytes(), (rid, stage)
    # the order the stages were made in, each from the one before
    used = [r[4]["f"][1] for r in RUNS]
    assert used == ["inputs/" + s for s in (MK.KEPT, MK.GROUNDED, MK.GROUNDED, MK.ASKED, MK.SETTLED, MK.ASKED_AGAIN,
                                            MK.RULED, MK.WEIGHED_GO, MK.FINAL, MK.FINAL)]
    # the final stage is the weighed one but for the two spikes, set from their verdicts
    w, f = _load(INPUTS / MK.WEIGHED), _load(INPUTS / MK.FINAL)
    assert [n for n in w["nodes"] if not str(n["id"]).startswith("N:target/")] == \
        [n for n in f["nodes"] if not str(n["id"]).startswith("N:target/")]
    # the landed cshorts are the entailing runs' folders, file for file
    for lang, rid in (("go", "2026-11-22-1400-a909"), ("rust", "2026-11-22-1410-a910")):
        got = _files(LANDED / f"tally.cshort-{lang}-{MK.LANDED_STAMP[lang]}")
        assert got == _files(MK._output(_run_dir("entail-in-a-language", rid), "code"))
        assert (LANDED / f"tally.layout-{lang}-{MK.LANDED_STAMP[lang]}.md").read_bytes() == \
            MK._output(_run_dir("entail-in-a-language", rid), "arrangement").read_bytes()


def test_the_path_says_what_it_did():
    g = _load(INPUTS / MK.GROUNDED)
    rel = [n for n in g["nodes"] if n.get("type") == "reliance"]
    assert len(rel) == 56 and all(n.get("entry") for n in rel)
    import test_ground as TG                            # the 43 reliances the 2026-11-05 trial's writers had to know
    raised = {n["entry"] for n in rel} | {n["id"].split("/", 1)[1] for n in g["nodes"]
                                          if str(n["id"]).startswith("P:assumption/")}
    assert set(TG.TALLY_NEEDS) <= raised, sorted(set(TG.TALLY_NEEDS) - raised)
    asked = _load(INPUTS / MK.ASKED)
    banked = [n["id"] for n in asked["nodes"] if str(n["id"]).startswith("D:question/")
              and str((n.get("raised") or {}).get("from", "")).startswith("transconception-")]
    assert "D:question/who-rules" in banked and "D:question/lane-mit" in banked and len(banked) == 7
    ruled = _load(INPUTS / MK.RULED)
    makers = [n for n in ruled["nodes"] if n["id"].startswith("R:maker/") and n.get("capacity") == "transconceiver"]
    assert len(makers) == 1 and set(makers[0]["statements"]) >= set(tc.STATEMENTS)
    assert next(n for n in ruled["nodes"] if n["id"] == "R:licence/mit")["lane"] == "open"
    rulings = [r for n in ruled["nodes"] for r in tc.rulings(n)]
    assert rulings and {r["is"] for r in rulings} == {"kept"}             # every ruling as proposed: kept
    final = _load(INPUTS / MK.FINAL)
    targets = {n["id"]: n for n in final["nodes"] if str(n["id"]).startswith("N:target/")}
    assert sorted(targets) == ["N:target/go", "N:target/rust"]          # no N:target in python: no round trip
    assert {t["verdict"] for t in targets.values()} == {"feasible-with"}
    assert any("argparse-surface" in c for c in targets["N:target/go"]["conditions"])
    assert any("whole-numbers-unbounded" in c for c in targets["N:target/rust"]["conditions"])
    for t in targets.values():
        assert t["spike"]["level"] == 3 and t["spike"]["evidence"]["where"]["file"].startswith("spikes/")
        assert t["made"]["engine"] == "rules+model:scripted"


# ---------------------------------------------------------------------------
# checks and gates, as recorded
# ---------------------------------------------------------------------------

def test_every_check_holds_or_fails_as_recorded_and_the_gates_report_as_recorded():
    checks, gates = MK.reports(FIX)
    assert checks == json.loads((FIX / "recorded" / "checks.json").read_text(encoding="utf-8"))
    assert gates == json.loads((FIX / "recorded" / "gates.json").read_text(encoding="utf-8"))
    assert list(gates) == ([f"inputs/{s}" for s in MK.STAGES] + [f"landed/{MK.FINAL}"]
                           + [f"inputs/{s}" for s in (MK.FIXED, MK.RECORDED, MK.JUDGED)])


def test_the_gates_say_where_the_path_stands():
    gates = json.loads((FIX / "recorded" / "gates.json").read_text(encoding="utf-8"))

    def failing(stage: str, gate: str) -> list[str]:
        return gates[stage][gate]["do-not-hold"]
    assert failing(f"inputs/{MK.KEPT}", "ready-to-keep") == ["standing", "stands-alone", "ruled", "round-trip"]
    assert failing(f"inputs/{MK.GROUNDED}", "ready-to-keep") == ["standing", "ruled", "round-trip"]
    assert failing(f"inputs/{MK.SETTLED}", "ready-to-keep") == ["standing", "round-trip"]   # statements not yet
    assert failing(f"inputs/{MK.RULED}", "ready-to-keep") == ["round-trip"]
    # weighed, each spike at level 0: target-confirmed does not hold; the simulated verdicts set the spikes
    for lang in ("go", "rust"):
        assert failing(f"inputs/{MK.WEIGHED}", f"ready-to-entail {lang}") == ["round-trip", "target-confirmed"]
        assert failing(f"inputs/{MK.FINAL}", f"ready-to-entail {lang}") == ["round-trip"]
        assert failing(f"landed/{MK.FINAL}", f"ready-to-entail {lang}") == ["round-trip"]
    # the round trip is never claimed: tally's Python cshort of 2026-11-05 was never judged
    rt = gates[f"landed/{MK.FINAL}"]["ready-to-keep"]["checks"]["round-trip"]["errors"]
    assert rt == ["round-trip tally.fabulac.cosm: no N:target in the source language (python): the round trip is "
                  "entailed for it"]
    assert gates[f"landed/{MK.FINAL}"]["ready-to-keep"]["says"] == "not ready to keep"


NINE = ("standing", "ground-given", "ground-cited", "stands-alone", "nothing-carried", "case-outside", "cases-cover",
        "ruled", "round-trip")


def test_which_gate_tallys_fixture_holds():
    """Where tally's transconception stands, so it cannot fall back silently (lane T1, 0.9): on the judged stage gate 1
    says "ready to keep", and it says so if and only if all nine of its checks hold, every one measured. Before the
    judged round trip, only `round-trip` fails."""
    gates = json.loads((FIX / "recorded" / "gates.json").read_text(encoding="utf-8"))
    for stage, gate in gates.items():
        keep = gate["ready-to-keep"]
        assert tuple(keep["checks"]) == NINE, stage
        nine_hold = all(keep["checks"][n]["state"] == "holds" for n in NINE) and not keep["not-measured"]
        assert keep["holds"] is nine_hold and (keep["says"] == "ready to keep") is nine_hold, stage
    judged = gates[f"inputs/{MK.JUDGED}"]["ready-to-keep"]
    assert judged["holds"] is True and judged["says"] == "ready to keep"
    assert judged["hold"] == list(NINE) and judged["do-not-hold"] == [] and judged["not-measured"] == []
    for name in NINE:                                     # nothing left over, not even a warning
        c = judged["checks"][name]
        assert c["errors"] == c["warnings"] == [], (name, c)
    for stage in (MK.FIXED, MK.RECORDED):
        assert gates[f"inputs/{stage}"]["ready-to-keep"]["do-not-hold"] == ["round-trip"], stage
    # gate 2 holds on the judged stage too, but its target-confirmed rests on the simulated spikes (see below)
    for lang in ("go", "rust"):
        assert gates[f"inputs/{MK.JUDGED}"][f"ready-to-entail {lang}"]["holds"] is True


def test_the_round_trip_was_recorded_outside_and_judged_blind():
    out = FIX / "outside"
    rec = json.loads((out / "recording" / "recorded.json").read_text(encoding="utf-8"))
    src = _load(INPUTS / MK.FINAL)["source"]
    assert rec["source"] == {"tree": src["tree"]} and rec["seeds"] == ["0", "1"] and rec["unstable"] == []
    assert rec["python"].startswith("3.13.11 ")
    assert len(rec["rows"]) == 53 and sum(len(r["argv"]) for r in rec["rows"]) == 161
    # the recorder ran on the cases file entail f as cases gives the targeted fabulac; the judge on the recorded one's
    assert (out / "recording" / "cases.json").read_text(encoding="utf-8") == MK.handed_out(MK.targeted(
        _load(INPUTS / MK.FIXED)))
    recorded = _load(INPUTS / MK.RECORDED)
    assert (out / MK.ROUNDTRIP / "cases.json").read_text(encoding="utf-8") == MK.judge_cases(recorded)
    data = _load(INPUTS / MK.JUDGED)
    cases = [n for n in data["nodes"] if str(n["id"]).startswith("P:case/trial-")]
    assert len(cases) == 53 and all(n["stands"] == "outside" and n["from"] == "recorded" for n in cases)
    assert all(n["of"][0].startswith("C:interface/command.") for n in cases)
    b7 = next(n for n in cases if n["worksheet-id"] == "B7")
    assert b7["ruling"] == [MK.B7_RULING] and b7["ruling"][0]["said"] == "Free"     # the owner's, 2026-11-22
    # the first round trip (from FINAL) found the slip on E1 and the help words of B7; it is kept, never gathered
    first = json.loads((out / "first-round-trip" / "verdict.json").read_text(encoding="utf-8"))
    assert first["steps"] == {"kept": 189, "agree": 184} and first["passes"] is False
    assert sorted((f["case"], str(f["step"])) for f in first["findings"]) == [
        ("B7", "0"), ("B7", "1"), ("B7", "2"), ("B7", "3"), ("E1", "written")]
    # the second, a fresh blind agent from the fixed fabulac: every counted step agrees, B7's four shown as ruled
    v = json.loads((out / MK.ROUNDTRIP / "verdict.json").read_text(encoding="utf-8"))
    assert v["target"] == "python" and v["steps"] == {"kept": 185, "agree": 185} and v["passes"] is True
    assert sorted((f["case"], f["step"], f["kind"]) for f in v["findings"]) == [
        ("B7", i, "ruled difference") for i in range(4)]
    entry = next(e for e in data["shorts"] if e.get("target") == "N:target/python")
    assert entry["path"] == f"../outside/{MK.ROUNDTRIP}/" and f"from inputs/{MK.FIXED} alone" in entry["by"]
    ev = entry["evidence"]
    assert ev["level"] == 3 and ev["steps"] == {"kept": 185, "agree": 185} and "run by an agent" in ev["by"]
    for d in (out / "first-round-trip", out / MK.ROUNDTRIP):   # tally's own six tests, on the original and the rebuild
        for which in ("control", MK.ROUNDTRIP):
            log = (d / f"own-tests-{which}.log").read_text(encoding="utf-8")
            assert log.strip().splitlines()[-1].startswith("6 passed"), (d.name, which)


def test_the_fix_is_recorded_as_a_fix():
    """The owner's "The fabulac slipped: fix it" (2026-11-22): the words on `undoes` say what the original does, and
    each item corrected says so in `provenance.fixed`; nothing else of FINAL changed, and no ruling was made for it."""
    final, fixed = _load(INPUTS / MK.FINAL), _load(INPUTS / MK.FIXED)
    assert fixed == MK.fixed(final)
    before = {n["id"]: n for n in final["nodes"]}
    changed = [n["id"] for n in fixed["nodes"] if n != before[n["id"]]]
    assert sorted(changed) == sorted(MK.FIX_WORDS)
    for iid in changed:
        n = next(x for x in fixed["nodes"] if x["id"] == iid)
        (fx,) = n["provenance"]["fixed"]
        assert fx["why"].startswith("the owner, 2026-11-22") and n.get("ruling") == before[iid].get("ruling")
    assert {k: v for k, v in fixed.items() if k != "nodes"} == {k: v for k, v in final.items() if k != "nodes"}


def test_the_landed_cshorts_hold_their_own_checks_and_claim_no_evidence():
    data = _load(LANDED / MK.FINAL)
    items = data["nodes"]
    for lang, title in MK.LANGUAGES:
        names = tc.entailed_names(MK.FINAL, lang, MK.LANDED_STAMP[lang])
        entry = next(e for e in data["shorts"] if e["path"] == names["cshort"])
        assert entry == {"path": names["cshort"], "order": "code", "language": lang, "target": f"N:target/{lang}",
                         "layout": names["layout"], "entailed": "apart", "files": 2, "evidence": []}
        folder = LANDED / names["cshort"]
        md = (folder / "CSHORT.md").read_text(encoding="utf-8")
        texts = {p.name: p.read_text(encoding="utf-8") for p in folder.iterdir()}
        assert tc.surface_problems(items, f"N:target/{lang}", md, file_text=texts.get, unruled=True) == []
        lines = (folder / "requests.jsonl").read_text(encoding="utf-8").split("\n")
        assert tc.apart_problems(lines, tc.source_paths(items), None) == []
        assert md.splitlines()[0] == f"*a cshort of {MK.FINAL}, in {title}, compiled on 2026-11-22 by scripted; never run*"
    rep = FAB.lint(LANDED / MK.FINAL)
    per = [str(p) for p in rep.errors if p.check in tc.PER_CSHORT]
    assert per == []


# ---------------------------------------------------------------------------
# simulated, recorded, never claimed
# ---------------------------------------------------------------------------

def test_what_is_simulated_says_so():
    """Since 0.9 the two sittings are the owner's (2026-11-22, "Confirm all"); the spikes and the model stay
    simulated, and say so."""
    for vol in sorted(INPUTS.glob("*.answers-*.cosm")):
        text = vol.read_text(encoding="utf-8")
        assert "simulated" not in text and "the owner, as transconceiver, by questionnaire" in text, vol.name
    ruled = _load(INPUTS / MK.RULED)
    maker = next(n for n in ruled["nodes"] if n["id"].startswith("R:maker/") and n.get("capacity") == "transconceiver")
    assert maker["id"] == MK.OWNER and maker["statements"]["programs"] == "tally, in Go, in Rust and in Python, the round trip"
    assert not any("simulated" in str(v) for v in maker["statements"].values())
    assert {r["by"] for n in ruled["nodes"] for r in tc.rulings(n)} == {MK.OWNER}
    assert _load(INPUTS / MK.KEPT)["source"]["obtained"] == "own"
    for lang, title in MK.LANGUAGES:
        v = json.loads((INPUTS / "spikes" / f"{lang}-spike.verdict.json").read_text(encoding="utf-8"))
        assert v["simulated"].startswith("simulated for the conformance fixture: there is no " + title)
        assert v["findings"] == [] and v["steps"] == {"kept": 0, "agree": 0}
    for p in sorted(FIX.glob("replay/*/*/candidates/*.cosm")):
        rec = _load(p)
        eng = str(rec.get("engine") or "")
        if eng.startswith("model:"):
            assert eng == "model:scripted", p
    asked = [s for s in MK.PATH if s[0] == "run" and not s[5]]
    assert {s[1] for s in asked} == {"weigh-a-target", "entail-in-a-language"}   # only these asked the fake model
    for d in sorted(LANDED.glob("tally.cshort-*")):
        assert "a stub by the recorded fake model of the conformance fixture; never built" in \
            next(p for p in d.iterdir() if p.suffix in (".go", ".rs")).read_text(encoding="utf-8")


def test_tallys_own_fixture_is_beside_it_untouched():
    assert _files(INPUTS / "tally") == {k: v for k, v in _files(MK.TALLY).items() if "__pycache__" not in k
                                        and ".pytest_cache" not in k}
    kept = (INPUTS / MK.KEPT).read_text(encoding="utf-8")
    assert kept == MK.kept_text(MK.TALLY_FABULAC.read_text(encoding="utf-8"))
    assert "purpose: transconception\n" in kept and "licence: MIT, obtained: own}" in kept
    assert (INPUTS / "tally.cases.json").read_bytes() == (FIX / "tally.cases.json").read_bytes()
    src = _load(MK.TALLY_FABULAC)["source"]
    assert mc.tree_digest(INPUTS / "tally")["tree"] == src["tree"]


def test_the_programs_are_the_bundled_texts_six():
    """THYM 24.3: the folder's six `thym 1` programs are the text's own, byte for byte under their version line:
    `ground-the-fabulac`, `hand-out-the-cases`, `weigh-a-target` and `entail-in-a-language` (20.10),
    `raise-the-questions` (20.6) and `settle-the-answers` (22.4)."""
    thym_md = (MK.REPO / "docs" / "THYM.md").read_text(encoding="utf-8")
    assert sorted(MK.PROGRAMS) == ["entail-in-a-language", "ground-the-fabulac", "hand-out-the-cases",
                                   "raise-the-questions", "settle-the-answers", "weigh-a-target"]
    for name, text in MK.PROGRAMS.items():
        assert text.startswith("thym 1\n\n"), name
        body = text.split("\n", 2)[2]                   # without its `thym 1` line
        assert f"program {name}\n" in thym_md and body in thym_md, name


# ---------------------------------------------------------------------------
# made again, the same
# ---------------------------------------------------------------------------

def test_the_maker_makes_the_folder_again_byte_for_byte(tmp_path):
    """Every run id and clock is pinned: a second make gives the same bytes, but for each recorded run's plan and
    trace, which carry the wall clock they were made at (the trace's `ended`, the plan's id)."""
    again = tmp_path / "tally"
    again.mkdir()
    shutil.copyfile(FIX / "tally.cases.json", again / "tally.cases.json")
    shutil.copyfile(FIX / "README.md", again / "README.md")
    MK.make(again)

    def stable(files: dict) -> dict:
        return {k: v for k, v in files.items() if not re.search(r"\.(plan|trace)\.cosm$", k)}
    a, b = stable(_files(FIX)), stable(_files(again))
    assert sorted(a) == sorted(b)
    assert [k for k in a if a[k] != b[k]] == []
