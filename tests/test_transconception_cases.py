"""Transconception, phase 4: the cases (docs/v080-pins.md 2; the survey's phase 4).

The moves `entail f as cases`, `gather recorded with f` and `gather verdict with f` (enough/thym/moves/transconceive.py)
over enough's cases functions (enough/transconception.py), on the promoted fixtures; a recording folder in the
experiment's shape read back; a verdict folded into evidence; what goes stale when the source moves, and what carries
over; tally's 161 trial steps as cases data; and the outside harness (tools/transconception/harness.py), whose judge is
pure data and is exercised here on data alone. Nothing here runs a recorder or a runner: those are the owner's.
"""
from __future__ import annotations

import ast
import copy
import datetime as dt
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from enough import macrocosm as mc
from enough import thym
from enough import transconception as tc
from enough.thym import Refusal
from enough.thym import checks as C
from enough.thym import plan as pl
from enough.thym import run as RUN
from enough.thym import trace as T
from enough.thym import folder as FOLDER
from enough.thym.moves import transconceive as TV
from enough.thym.values import Value, digest_path, folder_value

REPO = Path(__file__).resolve().parents[1]
FX = REPO / "tests" / "fixtures" / "fabula"
TFX = FX / "transconception"
TALLY_CASES = TFX / "tally" / "tally.cases.json"
SLOPPY = TFX / "sloppy-xml-py.fabulac.cosm"
VULTURE = TFX / "vulture.fabulac.cosm"
TOOLS = REPO / "tools" / "transconception"
TRIAL = next((r / "docs" / "fabula-survey-migration-trial.md" for r in (REPO, *REPO.parents[1:3])
              if (r / "docs" / "fabula-survey-migration-trial.md").is_file()), REPO / "docs" / "none")  # git ignores it
X0 = Path("/Users/m3u/METMcloud/fabulac-test-repos/_x0")
X0_RESULTS = X0 / "results" / "2026-11-13-1006"
NOW = dt.datetime(2026, 11, 18, 12, 0, tzinfo=dt.timezone.utc)

#: The trial's summary (report.py), steps per group: the same for both ports.
TRIAL_GROUPS = {"A ordinary use": 47, "B command-line edges": 24, "C numbers": 25, "D text": 34,
                "E ledger as found": 30, "F at once": 1}
#: The steps whose original result the trial's report printed (where a port differed), by case.
TRIAL_KNOWN = {"B2": [0], "B7": [0, 1, 2, 3], "C1": [0, 1, 2, 3], "C2": [4, 6], "E3a": [0], "E3b": [0], "E3c": [0],
               "E3d": [0], "E3h": [0], "E6": [0], "E9": [0]}


def _load(path: Path) -> dict:
    return mc.yaml_load(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sloppy() -> dict:
    return _load(SLOPPY)


@pytest.fixture(scope="module")
def vulture() -> dict:
    return _load(VULTURE)


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def harness():
    return _module("tc_harness", TOOLS / "harness.py")


def ctx(**kw):
    return SimpleNamespace(engines={"transconception": tc.thym_engine()}, now=NOW, run="run-1", **kw)


# ---------------------------------------------------------------------------
# tally's 161 trial steps, as cases data
# ---------------------------------------------------------------------------

def test_the_trials_161_steps_are_cases():
    text = TALLY_CASES.read_text(encoding="utf-8")
    doc = json.loads(text)
    assert tc.dump_cases(doc) == text                      # written as the harness writes a file
    assert tc.check_cases_doc(doc) == []
    cases = doc["cases"]
    assert len(cases) == 53 and sum(len(c["steps"]) for c in cases) == 161
    assert doc["groups"] == TRIAL_GROUPS
    for g, n in TRIAL_GROUPS.items():
        assert sum(len(c["steps"]) for c in cases if c["group"] == g) == n
    tally = _load(FX / "tally.fabulac.cosm")
    ifaces = {n["id"] for n in tally["nodes"] if n["id"].startswith("C:interface/")}
    for c in cases:
        assert f"C:interface/{c['of']}" in ifaces, c["id"]
        assert len(c["expect"]["steps"]) == len(c["steps"]) and c["expect-says"].endswith(".")
        assert c["env"]["TALLY_FILE"] in ("<CASE>/t.jsonl", None, "   ", "~/sub/t.jsonl", "<CASE>/a/b/c.jsonl")
    known = {c["id"]: [i for i, e in enumerate(c["expect"]["steps"]) if e] for c in cases}
    assert {k: v for k, v in known.items() if v} == TRIAL_KNOWN
    assert sum(len(v) for v in known.values()) == 18
    by = {c["id"]: c for c in cases}
    # a value the report cut is kept as the beginning it printed, and named
    assert by["B7"]["expect"]["steps"][0]["cut"] == ["out"]
    assert by["B7"]["expect"]["steps"][0]["out"].startswith("usage: tally [-h] [--version] {add,show,undo} ...\n\n"
                                                            "Count things from the command line.")
    assert "cut" not in by["B7"]["expect"]["steps"][2]
    assert by["E6"]["expect"]["steps"][0] == {"exit": 1, "out": "",
                                              "err": "tally: <CASE>/t.jsonl: line 1 is not a tally entry\n"}
    assert by["C1"]["expect"]["written"]["t.jsonl"].startswith('{"at": <float>, "delta": 99999999999999999999999')
    assert sorted(c["id"] for c in cases if "written" in c["expect"]) == ["C1", "C2", "E1"]
    assert "not in the trial's document" in by["A1"]["expect-says"]
    # the scenarios' set-ups: a seed (bytes that are not UTF-8 as base64), a folder in the ledger's place, a burst
    assert by["E7"]["files"] == {"t.jsonl": {"b64": "//4K"}} and by["E8"]["files"] == {"t.jsonl": {"dir": True}}
    assert by["F1"]["burst"] == {"argv": ["add", "x"], "times": 40}
    assert by["A8"]["env"] == {"TALLY_FILE": None}
    # the expectations stand on the source the tally fabulac is about
    assert doc["source"] == {"tree": tally["source"]["tree"]}
    assert tc.stale_report(tally, tally["nodes"], doc) == []
    assert all(tc.freshness(c["recorded"], tally)[0] == "fresh" for c in cases)


@pytest.mark.skipif(not TRIAL.is_file(), reason="the trial's document is ignored by git; it is in the main checkout")
def test_the_tally_cases_are_made_again_from_the_trials_document():
    conv = _module("trial_cases", TOOLS / "trial_cases.py")
    got = conv.build(TRIAL.read_text(encoding="utf-8"), (FX / "tally.fabulac.cosm").read_text(encoding="utf-8"))
    assert tc.dump_cases(got) == TALLY_CASES.read_text(encoding="utf-8")


def test_the_trials_masks_are_the_harness_s(harness):
    masks = json.loads(TALLY_CASES.read_text(encoding="utf-8"))["masks"]["written"]
    line = '{"at": 1731000000.25, "name": "tea", "delta": 1}\n{"at": 2, "name": "tea", "delta": 2}\n'
    assert harness.masked(line, masks) == ('{"at": <float>, "name": "tea", "delta": 1}\n'
                                           '{"at": <int>, "name": "tea", "delta": 2}\n')
    assert harness.masked('{"at": 1e5}', masks) == '{"at": <float>}' and harness.masked("x", None) == "x"


# ---------------------------------------------------------------------------
# entail f as cases
# ---------------------------------------------------------------------------

def test_entail_as_cases_makes_the_harness_s_file_from_the_fabulac(sloppy, vulture):
    for doc, n, targets in ((sloppy, 26, {"python", "rust"}), (vulture, 54, {"python", "go"})):
        cases, report = tc.cases_document(doc, doc["nodes"])
        assert report == {"cases": n, "from-items": n, "from-file": 0, "stale": []}
        assert len(cases["cases"]) == n and tc.check_cases_doc(cases) == []
        assert set(cases["rulings"]["targets"]) == targets
        assert cases["source"] == tc.source_of(doc) and cases["fabulac"] == doc["id"]
        for c in cases["cases"]:
            assert c["item"].startswith("P:case/x0.") and c["recorded"]["source"] == {"commit": doc["source"]["commit"]}
            assert len(c["expect"]["steps"]) == len(c["steps"]) and "stale" not in c
    v, _ = tc.cases_document(vulture, vulture["nodes"])
    c01 = v["cases"][0]
    assert (c01["id"], c01["of"], c01["steps"]) == ("V-C01", "V-I1", [["m.py"], ["."]])
    assert c01["expect"]["steps"][0]["exit"] == 3 and c01["expect"]["steps"][0]["out"].startswith("m.py:1: unused")
    go = v["rulings"]["targets"]["go"]
    assert go["made-for"] == "N:target/go" and go["labels"] == ["go"]
    assert go["cases"]["V-C10"] == [{"is": "alike", "allowing": "lines-in-any-order", "steps": [0],
                                     "about": "step 0, the only step recorded unstable",
                                     "said": "sitting 1, 5b Q-A2: alike, allowing lines-in-any-order; the step "
                                             "stays counted"}]
    assert v["rulings"]["targets"]["python"]["labels"] == ["py", "python"]
    s, _ = tc.cases_document(sloppy, sloppy["nodes"])
    s01 = s["cases"][0]
    assert s01["steps"] == [{"argv": [], "stdin": {"call": "stream_parse", "as": "str", "options": {},
                                                   "input": "<root><child>text</child></root>"}}]
    assert tc.cases_name(sloppy) == "sloppy-xml-py.cases.json"
    assert tc.given_step(tc.harness_step({"arguments": ["a"], "input": "x"})) == {"arguments": ["a"], "input": "x"}
    assert tc.case_expect(tc.harness_expect({"exit": 0, "output": "o", "error-output": ""})) == {
        "exit": 0, "output": "o", "error-output": ""}


@pytest.mark.skipif(not X0_RESULTS.is_dir(), reason="the experiment's results are on the owner's machine only")
def test_entail_as_cases_gives_back_the_experiments_own_cases_file(vulture, sloppy):
    """What the runner reads of each case (`id`, `of`, `files`, `steps`, `env`, `cwd`) is x0's own cases file again."""
    for doc, repo in ((vulture, "vulture"), (sloppy, "sloppy-xml-py")):
        mine = {c["id"]: c for c in tc.cases_document(doc, doc["nodes"])[0]["cases"]}
        x0 = json.loads((X0_RESULTS / repo / "cases.json").read_text(encoding="utf-8"))
        assert sorted(mine) == sorted(c["id"] for c in x0["cases"])
        for c in x0["cases"]:
            for k in ("of", "files", "steps", "env", "cwd"):
                assert mine[c["id"]].get(k) == (c.get(k) or None), (repo, c["id"], k)


def test_the_cases_file_beside_the_fabulac_is_kept_and_recorded_cases_stand(sloppy):
    first, _ = tc.cases_document(sloppy, sloppy["nodes"])
    existing = copy.deepcopy(first)
    existing["boundary"] = "the driver's request and lines"
    existing["cases"].append({"id": "S-C99", "of": "S-I0", "steps": [{"argv": [], "stdin": {"call": "tree_parse"}}],
                              "note": "a case only the file holds"})
    del existing["cases"][0]["expect"]                     # the item's own expectation comes back
    doc, report = tc.cases_document(sloppy, sloppy["nodes"], existing=existing)
    assert report["cases"] == 27 and report["from-file"] == 27 and doc["boundary"] == "the driver's request and lines"
    assert doc["cases"][-1]["id"] == "S-C99" and doc["cases"][0]["expect"] == first["cases"][0]["expect"]


def _program(tmp: Path, body: str) -> Path:
    p = tmp / "p.thym"
    p.write_text("thym 1\n\nprogram p\n" + body + "end\n", encoding="utf-8")
    return p


def _run(tmp: Path, prog: Path, rows: list[dict], **kw):
    for r in rows:
        r.setdefault("sha256", digest_path(tmp / r["path"]))
    c = thym.check_file(prog)
    assert not isinstance(c, Refusal), str(c)
    plan = pl.plan(c, rows, program=None)
    assert not isinstance(plan, Refusal), str(plan)
    return RUN.run(plan, inputs_root=tmp, root=tmp / "root", program=prog, now=NOW,
                   engines={"transconception": tc.thym_engine()}, **kw)


@pytest.mark.parametrize("rules", [False, True])
def test_entail_as_cases_is_a_move_a_thym_1_program_writes(tmp_path, rules):
    (tmp_path / "s.fabulac.cosm").write_bytes(SLOPPY.read_bytes())
    prog = _program(tmp_path, "  takes f: fabula\n  gives c: text\n\n  give entail f as cases\n")
    t = _run(tmp_path, prog, [{"name": "f", "type": "fabula", "path": "s.fabulac.cosm"}], rules=rules)
    assert isinstance(t, T.Trace) and t.landed, getattr(t, "refusal", t)
    out = next((t.dir / "outputs").glob("c.*"))
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert len(doc["cases"]) == 26 and doc["cases"][0]["id"] == "S-C01"
    rec = next(r for r in t.records if r.get("name") == "entail f as cases")
    assert [c["name"] for c in rec["checks"]] == ["cases-whole", "provenance"] and all(c["ok"] for c in rec["checks"])


def test_a_thym_0_program_does_not_see_entail_as_cases(tmp_path):
    p = tmp_path / "p.thym"
    p.write_text("thym 0\n\nprogram p\n  takes f: fabula\n  gives c: short\n\n  give entail f as cases\nend\n")
    assert isinstance(thym.check_file(p), Refusal)


def test_cases_whole_refuses_a_file_that_is_not_whole(sloppy):
    fab = Value("fabula", sloppy)
    good = TV.entail_cases(ctx(), fab)
    c = ctx()
    assert C.verdict("cases-whole", good, {"f": fab}, {}, None, c) == (True, "")
    doc = json.loads(good.text())
    assert C.verdict("cases-whole", Value("text", json.dumps(doc)), {"f": fab}, {}, None, c)[0] is False
    doc["cases"] = doc["cases"][1:]
    ok, why = C.verdict("cases-whole", Value("text", tc.dump_cases(doc)), {"f": fab}, {}, None, c)
    assert not ok and "P:case/x0.S-C01" in why
    doc["cases"][0]["steps"] = []
    ok, why = C.verdict("cases-whole", Value("text", tc.dump_cases(doc)), {}, {}, None, c)
    assert not ok and "has no steps" in why
    with pytest.raises(Exception, match="transconception engine is not here"):
        TV.entail_cases(SimpleNamespace(engines={}), fab)


# ---------------------------------------------------------------------------
# gather recorded with f: a recording folder in the experiment's shape
# ---------------------------------------------------------------------------

def _recording(tmp: Path, cases: dict, rows: list[dict], *, source=None, env_commit=None, unstable=()) -> Path:
    base = tmp / "results"
    folder = base / str(cases["repo"])
    folder.mkdir(parents=True)
    craw = tc.dump_cases(cases).encode("utf-8")
    (folder / "cases.json").write_bytes(craw)
    rec = {"impl": "original", "seed": "0", "cases_digest": hashlib.sha256(craw).hexdigest(),
           "python": "3.13.11 (main)", "rows": rows, "unstable": list(unstable), "seeds": ["0", "1"]}
    if source is not None:
        rec["source"] = source
    (folder / "recorded.json").write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8")
    if env_commit:
        (base / "environment.txt").write_text(f"x0 setup\n{cases['repo']}: {env_commit}\n", encoding="utf-8")
    return folder


def _row(case: dict, steps: list[dict], written=None) -> dict:
    return {"id": case["id"], "of": case["of"], "argv": [tc._as_step(s) for s in case["steps"]],
            "run": {"steps": steps, "written": written or {}}}


def test_a_recording_folder_reads_back_into_the_cases_file(tmp_path, sloppy):
    doc, _ = tc.cases_document(sloppy, sloppy["nodes"])
    first, second = doc["cases"][0], doc["cases"][1]
    extra = {"id": "S-C98", "of": "S-I0", "steps": [{"argv": [], "stdin": {"call": "tree_parse", "input": "<a/>"}}]}
    rcases = {"repo": "sloppy-xml-py", "cases": [first, second, extra]}
    moved = copy.deepcopy(second)
    moved["steps"] = [["changed"]]                          # the file's case changed after it was recorded
    doc["cases"][1] = moved
    rows = [_row(first, [{"exit": 0, "out": "new\n", "err": ""}], written={"x.txt": "1"}),
            _row(second, [{"exit": 1, "out": "", "err": "e\n"}]),
            _row(extra, [{"exit": 0, "out": "{\"end\":\"ok\"}\n", "err": ""}])]
    folder = _recording(tmp_path, rcases, rows, env_commit=sloppy["source"]["commit"],
                        unstable=[{"case": first["id"], "step": 0}])
    rec = tc.read_recording_folder(folder)
    assert rec.source == {"commit": sloppy["source"]["commit"]} and rec.name == "sloppy-xml-py"
    out, report = tc.gather_recorded(doc, rec, now=tc.source_of(sloppy))
    assert report["recorded"] == ["S-C01", "S-C98"] and report["added"] == ["S-C98"] and report["unknown"] == []
    assert [r["case"] for r in report["stale"]] == ["S-C02"]
    by = {c["id"]: c for c in out["cases"]}
    c1 = by["S-C01"]
    assert c1["expect"] == {"steps": [{"exit": 0, "out": "new\n", "err": ""}], "written": {"x.txt": "1"}}
    assert c1["recorded"]["source"] == {"commit": sloppy["source"]["commit"]}
    assert c1["recorded"]["run"] == "sloppy-xml-py/recorded.json" and c1["recorded"]["unstable-steps"] == [0]
    assert c1["recorded"]["seeds"] == ["0", "1"] and "stale" not in c1
    assert "expect" not in by["S-C02"] and "record it again" in by["S-C02"]["stale"]
    assert by["S-C98"]["steps"] == extra["steps"] and len(out["cases"]) == 27
    # the recording's own source, when it names one, wins over the experiment's environment line
    folder2 = _recording(tmp_path / "b", rcases, rows, source={"tree": "f" * 64}, env_commit="0" * 40)
    assert tc.read_recording_folder(folder2).source == {"tree": "f" * 64}
    # a cases.json that is not the one recorded on is refused
    (folder2 / "cases.json").write_text("{}\n")
    with pytest.raises(tc.CasesError, match="not the cases file the recording was made on"):
        tc.read_recording_folder(folder2)


def test_gather_recorded_as_a_move_names_the_source_of_every_case(tmp_path, sloppy):
    doc, _ = tc.cases_document(sloppy, sloppy["nodes"])
    rows = [_row(c, [{"exit": 0, "out": "", "err": ""} for _ in c["steps"]]) for c in doc["cases"]]
    folder = _recording(tmp_path, {**doc, "repo": "sloppy-xml-py"}, rows, source=tc.source_of(sloppy))
    fab = Value("fabula", sloppy, path=SLOPPY)
    rec = folder_value(FOLDER.read(folder), path=folder)
    v = TV.gather_outside(ctx(), rec, **{"with": fab})
    out = json.loads(v.text())
    assert len(out["cases"]) == 26 and all(c["recorded"]["source"] == tc.source_of(sloppy) for c in out["cases"])
    assert all("stale" not in c for c in out["cases"]) and v.origin["cases"]["recorded"][0] == "S-C01"
    inputs = {"recorded": rec, "with": fab}
    assert C.verdict("source-named", v, inputs, {}, None, ctx()) == (True, "")
    assert C.verdict("cases-whole", v, inputs, {}, None, ctx()) == (True, "")
    bad = json.loads(v.text())
    del bad["cases"][3]["recorded"]
    ok, why = C.verdict("source-named", Value("text", tc.dump_cases(bad)), {}, {}, None, ctx())
    assert not ok and "names no source" in why
    bad = json.loads(v.text())
    bad["cases"] = bad["cases"][:-1]
    ok, why = C.verdict("source-named", Value("text", tc.dump_cases(bad)), inputs, {}, None, ctx())
    assert not ok and "S-C" in why


@pytest.mark.skipif(not X0_RESULTS.is_dir(), reason="the experiment's results are on the owner's machine only")
def test_the_experiments_own_recordings_read_back_fresh(vulture, sloppy):
    for doc, repo, n in ((vulture, "vulture", 54), (sloppy, "sloppy-xml-py", 26)):
        rec = tc.read_recording_folder(X0_RESULTS / repo)
        assert rec.source == {"commit": doc["source"]["commit"]}            # from the experiment's environment.txt
        cases, _ = tc.cases_document(doc, doc["nodes"])
        out, report = tc.gather_recorded(cases, rec, now=tc.source_of(doc))
        assert len(report["recorded"]) == n and report["stale"] == [] and report["unknown"] == []
        # what the recording says is what the experiment wrote into the fabulac's own cases (exit and output; a
        # traceback's machine paths were written from the home folder when the fixture was promoted)
        def said(d):
            return [[(s["exit"], s["out"]) for s in c["expect"]["steps"]] for c in d["cases"]]
        assert said(out) == said(cases)


# ---------------------------------------------------------------------------
# gather verdict with f
# ---------------------------------------------------------------------------

def _verdict(passes=True, **kw) -> dict:
    v = {"cshort": "py-roundtrip", "against": "original", "target": "python", "recorded_digest": "ab" * 32,
         "run_digest": "cd" * 32, "rulings_digest": "ef" * 32, "steps": {"kept": 60, "agree": 60 if passes else 57},
         "share": 1.0 if passes else 0.95, "passes_95": True, "unruled": 0 if passes else 2, "passes": passes,
         "findings": [] if passes else [
             {"case": "S-C06", "step": 1, "kind": "ruled difference", "ruling": {"is": "changed", "to": "x"},
              "argv": {"argv": [], "stdin": "{}"}, "original": {"exit": 0, "out": "a", "err": ""},
              "cshort": {"exit": 0, "out": "b", "err": ""}},
             {"case": "S-C07", "step": 0, "kind": "UNRULED difference", "ruling": None,
              "argv": {"argv": [], "stdin": "{}"}, "original": {"exit": 0, "out": "a", "err": ""},
              "cshort": {"exit": 1, "out": "", "err": "boom"}},
             {"case": "S-C08", "kind": "interface not ruled", "of": "S-I9"},
             {"case": "S-C09", "kind": tc.STALE_FINDING, "why": "recorded from commit 0000"}]}
    v.update(kw)
    return v


def test_a_verdict_is_folded_into_its_cshorts_evidence(tmp_path, sloppy):
    cat = {k: v for k, v in sloppy.items() if k != "nodes"}
    raw = json.dumps(_verdict(source=tc.source_of(sloppy))).encode()
    new, report = tc.fold_verdict(cat, json.loads(raw), verdict_bytes=raw, where="v/verdict.json",
                                  at="2026-11-18T12:00", by="the judge")
    ev = new["shorts"][0]["evidence"]
    assert ev == {"level": 3, "steps": {"kept": 60, "agree": 60}, "against": "original",
                  "inputs": "the recorded cases, digest abababababab",
                  "where": {"file": "v/verdict.json", "digest": hashlib.sha256(raw).hexdigest()},
                  "at": "2026-11-18T12:00", "by": "the judge", "source": tc.source_of(sloppy)}
    assert report == {"cshort": "py-roundtrip", "level": 3, "passes": True, "differences": 0, "needs-ruling": 0,
                      "stale": None}
    assert cat["shorts"][0]["evidence"]["level"] == 3 and "source" not in cat["shorts"][0]["evidence"]  # unchanged
    raw = json.dumps(_verdict(passes=False)).encode()
    new, report = tc.fold_verdict(cat, json.loads(raw), verdict_bytes=raw, where="v.json", at="t", by="b")
    assert new["shorts"][0]["evidence"]["level"] == 2 and report["needs-ruling"] == 2 and report["differences"] == 4
    assert report["stale"].startswith("unnamed")
    with pytest.raises(tc.CasesError, match="no cshort 'go-apart'"):
        tc.fold_verdict(cat, _verdict(cshort="go-apart"), verdict_bytes=b"{}", where="v", at="t", by="b")


def test_gather_verdict_as_a_move_raises_nothing_and_states_its_evidence(tmp_path, sloppy):
    (tmp_path / "s.fabulac.cosm").write_bytes(SLOPPY.read_bytes())
    (tmp_path / "told" / "py-roundtrip").mkdir(parents=True)
    vp = tmp_path / "told" / "py-roundtrip" / "verdict.json"
    vp.write_text(json.dumps(_verdict(passes=False)), encoding="utf-8")
    fab = Value("fabula", sloppy, path=tmp_path / "s.fabulac.cosm")
    verdict = Value("text", vp.read_text(encoding="utf-8"), path=vp, raw=vp.read_bytes())
    out = TV.gather_outside(ctx(), verdict, **{"with": fab})
    ev = out.mapping()["shorts"][0]["evidence"]
    assert ev["where"] == {"file": "told/py-roundtrip/verdict.json",
                           "digest": hashlib.sha256(vp.read_bytes()).hexdigest()}
    assert ev["at"] == "2026-11-18T12:00" and "run-1" in ev["by"]
    nodes = out.mapping()["nodes"]
    assert len(nodes) == len(sloppy["nodes"]) and not any(n["id"].startswith("D:") for n in nodes
                                                          if n not in sloppy["nodes"])
    assert C.verdict("evidence-stated", out, {"verdict": verdict, "with": fab}, {}, None, ctx()) == (True, "")
    other = Value("text", json.dumps(_verdict(passes=False, share=0.5)), path=vp)
    ok, why = C.verdict("evidence-stated", out, {"verdict": other, "with": fab}, {}, None, ctx())
    assert not ok and "digest" in why
    with pytest.raises(Exception, match="not a verdict"):
        TV.gather_outside(ctx(), Value("text", "{}"), **{"with": fab})


def test_differences_from_verdict_is_the_shared_signature():
    assert list(inspect.signature(tc.differences_from_verdict).parameters) == ["verdict"]
    d = tc.differences_from_verdict(_verdict(passes=False))
    assert [(x["case"], x["kind"], x["needs-ruling"]) for x in d] == [
        ("S-C06", "ruled difference", False), ("S-C07", "UNRULED difference", True),
        ("S-C08", "interface not ruled", True), ("S-C09", tc.STALE_FINDING, False)]
    assert d[1]["original"] == {"exit": 0, "out": "a", "err": ""} and d[1]["cshort-gave"]["exit"] == 1
    assert d[1]["target"] == "python" and d[1]["cshort"] == "py-roundtrip" and "ruling" not in d[1]
    assert d[2]["of"] == "S-I9" and d[3]["why"] == "recorded from commit 0000"
    assert tc.differences_from_verdict({}) == []


# ---------------------------------------------------------------------------
# When the source moves
# ---------------------------------------------------------------------------

def test_recorded_cases_and_evidence_go_stale_when_the_source_moves(sloppy):
    moved = copy.deepcopy(sloppy)
    moved["source"]["commit"] = "1" * 40
    moved["source"]["tree"] = "2" * 64
    doc, report = tc.cases_document(moved, moved["nodes"])
    assert len(report["stale"]) == 26 and all(r["state"] == "stale" for r in report["stale"])
    assert all(c["stale"].startswith("recorded from commit 74a02907a402") for c in doc["cases"])
    rows = tc.stale_report(moved, moved["nodes"], doc)
    assert {r["where"] for r in rows} == {"item", "cases", "shorts"}
    assert next(r for r in rows if r["where"] == "shorts")["state"] == "unnamed"     # the promoted evidence says none
    # a recording that names the tree: stale when the tree moves, though the commit is the same
    assert tc.freshness({"tree": "a" * 64, "commit": "c" * 40}, {"tree": "b" * 64, "commit": "c" * 40})[0] == "stale"
    assert tc.freshness({"tree": "a" * 64}, {"tree": "a" * 64, "commit": "z"}) == ("fresh", "")
    assert tc.freshness(None, {"tree": "a"})[0] == "unnamed" and tc.freshness("abc", {})[0] == "unnamed"
    assert tc.freshness({"source-commit": "abc"}, {"commit": "abc"}) == ("fresh", "")
    # the same source again: nothing is stale, and a stale mark is cleared
    again, report = tc.cases_document(sloppy, sloppy["nodes"], existing=doc)
    assert report["stale"] == [] and not any("stale" in c for c in again["cases"])


def test_stale_evidence_does_not_count_for_the_round_trip(sloppy):
    vol = mc.load_volume(SLOPPY)
    found = []

    def add(check, it, msg, fld=None, *, severity=None):
        found.append((check, severity or "error", msg))

    tc._Checks(vol, add).round_trip()
    assert found == []
    vol.catalog["shorts"][0]["evidence"]["source"] = {"commit": "0" * 40}
    tc._Checks(vol, add).round_trip()
    assert [(c, s) for c, s, _m in found] == [("round-trip", "note"), ("round-trip", "error")]
    assert "is stale" in found[0][2] and "stands at level 2" in found[1][2]
    vol.catalog["shorts"][0]["evidence"]["source"] = tc.source_of(sloppy)
    found.clear()
    tc._Checks(vol, add).round_trip()
    assert found == []


def test_rulings_and_reliances_carry_over_while_their_item_resolves(sloppy):
    old = sloppy
    new = copy.deepcopy(sloppy)
    by = {n["id"]: n for n in old["nodes"]}
    iface = next(n["id"] for n in new["nodes"] if n["id"].startswith("C:interface/") and "ruling" in n)
    gone = next(n["id"] for n in new["nodes"] if n["id"].startswith("C:behaviour/") and "ruling" in n
                and n["id"] != iface)
    rel = next(n for n in new["nodes"] if n["id"].startswith("C:reliance/") and len(n.get("used-by") or []) > 1)
    lone = next(n for n in new["nodes"] if n["id"].startswith("C:reliance/") and n is not rel)
    for n in new["nodes"]:
        n.pop("ruling", None)
    new["nodes"] = [n for n in new["nodes"] if n["id"] not in (gone, rel["id"], lone["id"])]
    dropped_ref = rel["used-by"][0]
    new["nodes"] = [n for n in new["nodes"] if n["id"] != dropped_ref]
    for ref in (lone.get("used-by") or []) + (lone.get("of") or []):     # nothing the lone reliance names is left
        new["nodes"] = [n for n in new["nodes"] if n["id"] != ref]
    rep = tc.carry_over(old, new, at="2026-11-18", by="decompile")
    now = {n["id"]: n for n in new["nodes"]}
    assert iface in rep["rulings"] and now[iface]["ruling"] == by[iface]["ruling"]
    assert {"id": gone, "what": "ruling", "because": "the item is gone from the new fabulac"} in rep["stale"]
    assert rel["id"] in rep["reliances"] and dropped_ref not in now[rel["id"]]["used-by"]
    assert {"id": rel["id"], "ref": f"used-by: {dropped_ref}"} in rep["refs-dropped"]
    assert now[rel["id"]]["ruling"] == by[rel["id"]]["ruling"]          # carried whole, its ruling with it
    assert lone["id"] not in now and any(s["id"] == lone["id"] and s["what"] == "reliance" for s in rep["stale"])
    kept = copy.deepcopy(new)
    first = next(n for n in kept["nodes"] if n["id"] == iface)
    first["ruling"] = [{"is": "free", "because": "ruled again"}]
    tc.carry_over(old, kept)
    assert first["ruling"] == [{"is": "free", "because": "ruled again"}]   # a ruling the new item has is kept


# ---------------------------------------------------------------------------
# The outside harness: data in, data out
# ---------------------------------------------------------------------------

def test_the_harness_imports_only_the_standard_library_and_enough_imports_none_of_the_tools():
    allowed = {"__future__", "base64", "concurrent", "hashlib", "json", "os", "re", "shutil", "subprocess", "sys",
               "tempfile", "pathlib", "ast"}
    for name in ("harness.py", "trial_cases.py"):
        for n in ast.walk(ast.parse((TOOLS / name).read_text(encoding="utf-8"))):
            if isinstance(n, ast.Import):
                assert {a.name.split(".")[0] for a in n.names} <= allowed, (name, ast.dump(n))
            if isinstance(n, ast.ImportFrom):
                assert n.module.split(".")[0] in allowed, (name, n.module)
    for p in (REPO / "enough").rglob("*.py"):
        assert "tools.transconception" not in p.read_text(encoding="utf-8"), p


def test_the_harness_tree_digest_is_macrocosms(harness):
    tally = FX / "tally"
    pinned = _load(FX / "tally.fabulac.cosm")["source"]["tree"]
    assert harness.tree_digest(tally) == mc.tree_digest(tally)["tree"] == pinned
    assert harness.source_marks(tally, "abc") == {"tree": mc.tree_digest(tally)["tree"], "commit": "abc"}


def _judge(harness, tmp: Path, cases: dict, rec: dict, run: dict, rulings="-") -> dict:
    for name, obj in (("cases.json", cases), ("recorded.json", rec), ("run.json", run)):
        (tmp / name).write_text(json.dumps(obj), encoding="utf-8")
    rp = "-"
    if rulings != "-":
        (tmp / "rulings.json").write_text(json.dumps(rulings), encoding="utf-8")
        rp = tmp / "rulings.json"
    harness.cmd_judge(tmp / "cases.json", tmp / "recorded.json", tmp / "run.json", rp, tmp / "verdict.json")
    return json.loads((tmp / "verdict.json").read_text(encoding="utf-8"))


def test_the_judge_reads_the_rulings_enough_derives_and_the_source(tmp_path, harness, sloppy):
    cases, _ = tc.cases_document(sloppy, sloppy["nodes"])
    rows = [{"id": c["id"], "of": c["of"], "argv": [tc._as_step(s) for s in c["steps"]],
             "run": {"steps": [{"exit": e["exit"], "out": e["out"], "err": e["err"]} for e in c["expect"]["steps"]],
                     "written": c["expect"].get("written", {})}} for c in cases["cases"]]
    rec = {"impl": "original", "rows": rows, "unstable": [], "source": tc.source_of(sloppy)}
    run = {"impl": "py-roundtrip", "rows": copy.deepcopy(rows)}
    v = _judge(harness, tmp_path, cases, rec, run)
    assert v["target"] == "python" and v["passes"] and v["unruled"] == 0 and v["source"] == tc.source_of(sloppy)
    assert v["steps"]["kept"] == v["steps"]["agree"] > 0
    assert all(f["kind"] == "ruled change not seen" for f in v["findings"])
    # a verdict the judge wrote folds into the evidence, and its findings read as differences
    raw = (tmp_path / "verdict.json").read_bytes()
    new, report = tc.fold_verdict({k: x for k, x in sloppy.items() if k != "nodes"}, v, verdict_bytes=raw,
                                  where="verdict.json", at="t", by="b")
    assert report["passes"] and report["stale"] is None and new["shorts"][0]["evidence"]["level"] == 3
    # a recording from another source: the verdict says so and does not pass
    v = _judge(harness, tmp_path, cases, {**rec, "source": {"commit": "0" * 40}}, run)
    assert v["stale"].startswith("recorded from commit 000000000000") and not v["passes"]
    # a case enough marked stale is reported, never judged silently
    marked = copy.deepcopy(cases)
    marked["cases"][0]["stale"] = "recorded from commit 0000"
    v = _judge(harness, tmp_path, marked, rec, run)
    assert v["findings"][0] == {"case": "S-C01", "kind": tc.STALE_FINDING, "why": "recorded from commit 0000"}
    assert not v["passes"]
    # an unruled difference is found, with what each side gave
    bad = copy.deepcopy(run)
    bad["rows"][0]["run"]["steps"][0]["out"] += "x"
    v = _judge(harness, tmp_path, cases, rec, bad)
    assert [f["kind"] for f in v["findings"] if f["case"] == "S-C01"] == ["UNRULED difference"]
    d = tc.differences_from_verdict(v)
    assert next(x for x in d if x["case"] == "S-C01")["needs-ruling"] is True


@pytest.mark.skipif(not X0_RESULTS.is_dir(), reason="the experiment's results are on the owner's machine only")
def test_the_promoted_judge_judges_the_experiments_recording_against_itself(tmp_path, harness, vulture):
    """The experiment's judge self-test (x0 a4/judge_selftest.py, the "self" run): its recording against itself,
    with its own rulings file and with the rulings enough derives, agrees on every step it counts."""
    base = X0_RESULTS / "vulture"
    rec = json.loads((base / "recorded.json").read_text(encoding="utf-8"))
    run = {**copy.deepcopy(rec), "impl": "go-selftest"}
    run.pop("unstable", None)
    x0_rulings = json.loads((X0 / "vulture" / "rulings.json").read_text(encoding="utf-8"))
    v = _judge(harness, tmp_path, json.loads((base / "cases.json").read_text(encoding="utf-8")), rec, run, x0_rulings)
    assert v["unruled"] == 0 and v["steps"]["kept"] == v["steps"]["agree"] and v["passes"]
    derived, _ = tc.cases_document(vulture, vulture["nodes"])
    (tmp_path / "d").mkdir()
    v = _judge(harness, tmp_path / "d", derived, rec, run)
    assert v["unruled"] == 0 and v["steps"]["kept"] == v["steps"]["agree"] and v["passes"]
