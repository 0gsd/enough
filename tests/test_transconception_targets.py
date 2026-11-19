"""Transconception, phase 5 (0.8): targets. `N:target` as MacroCOSM 18.4.9 and the experiment's hand weighing (x0
step A7) have it; the target tables (`defaults/cosm/ground/targets/go.cosm`, `rust.cosm`); the move `weigh f in
<language>` (rules first, then a model under contract, here a scripted one); the checks `target-weighed` and weigh's
own `no-invention`; the gates (points 1, 4 and 5) refusing a target that fails one; `target-confirmed` from a spike's
recorded verdict; the twelve points as the target bank; and the promoted fixtures, which carry A7's weighings with
each spike's level read from O9's verdict on it, reaching gate 2 for their own language but for gate 1's
`stands-alone`.

Held for tally (grounded by rules, kept for transconception): weighed in Go it is `feasible-with` one gap (the option
reader, written); in Rust `feasible-with` two (whole numbers without limit, from a pinned crate or i128 as ruled; the
option reader, written). Rules answer every reliance's row and points 1, 2, 3, 7 and 8 from the table, and point 4 from
the rows; the model answers the program's points 5, 6, 9, 10, 11 and 12.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json

from pathlib import Path

import pytest

from enough import dialectic as dl
from enough import fabula as FAB
from enough import languages as L
from enough import macrocosm as mc
from enough import thym
from enough import thym_host as H
from enough import transconception as tc
from enough.thym import Refusal
from enough.thym import checks as C
from enough.thym import contracts as ct
from enough.thym import declarations as dc
from enough.thym import plan as pl
from enough.thym import registry as R
from enough.thym import run as RUN
from enough.thym.coprocessor import candidate
from enough.thym.moves import MoveError
from enough.thym.moves import transconceive as TR
from enough.thym.values import Value, digest_path

import test_ground as TG

REPO = Path(__file__).resolve().parents[1]
FIX = REPO / "tests" / "fixtures" / "fabula"
PROMOTED = FIX / "transconception"
VULTURE = PROMOTED / "vulture.fabulac.cosm"
SLOPPY = PROMOTED / "sloppy-xml-py.fabulac.cosm"
X0 = Path("/Users/m3u/METMcloud/fabulac-test-repos/_x0")
NOW = dt.datetime(2026, 11, 18, 12, 0, tzinfo=dt.timezone.utc)
PROMOTER = REPO / "tools" / "transconception" / "promote_x0.py"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def tally() -> tuple[dict, list[dict]]:
    """tally's fabulac grounded by rules (phase 2) and kept for transconception: what a weighing reads."""
    cat, items, _ = TG.ground(TG.TALLY_FABULAC, TG.TALLY)
    cat = {**cat, "purpose": "transconception"}
    return cat, items


def fabula_value(cat: dict, items: list[dict]) -> Value:
    return Value("fabula", {**copy.deepcopy(cat), "nodes": copy.deepcopy(items)})


def ctx_for(tmp_path: Path) -> RUN.MoveContext:
    stage = tmp_path / "stage"
    stage.mkdir(parents=True, exist_ok=True)
    return RUN.MoveContext(run="2026-11-18-1200-test", node={"id": "R:node/1", "step": {"n": 1}},
                           decls=R.read_declarations(), coprocessor=None, rules=False, now=NOW, emitted=[], slots={},
                           withheld={}, inputs_root=tmp_path, root=tmp_path, stage=stage,
                           engines={"transconception": tc.thym_engine()})


def reply(inputs: dict, *, scores: dict | None = None, rows: dict | None = None, spike_cases=(), conditions=(),
          verdict: str | None = None) -> str:
    """A scripted model's answer to a weighing's request: every point it is asked scored (2 unless `scores` says),
    a row for every open item (written unless `rows` says), a spike and the conditions given."""
    text = lambda k: inputs[k].text() if isinstance(inputs[k], Value) else str(inputs[k])  # noqa: E731
    asked = [int(ln.split(".", 1)[0]) for ln in text("points").splitlines() if ln.strip()]
    sc = scores or {}
    open_ids = [ln[2:].split(":", 2)[0] + ":" + ln[2:].split(":", 2)[1] for ln in text("open").splitlines()
                if ln.startswith("- ")]
    data = {"weighed": [{"point": n, "score": sc.get(n, 2), "evidence": f"the scripted model's reading of point {n}"}
                        for n in asked],
            "provides": [{"for": i, "by": (rows or {}).get(i, "written"), "what": "written by hand"} for i in open_ids],
            "spike": {"use": "the option reader (C:reliance/argparse-surface), small", "cases": list(spike_cases)},
            "conditions": list(conditions)}
    if verdict:
        data["verdict"] = verdict
    return mc.dump(data)


def weigh(tmp_path: Path, cat: dict, items: list[dict], language: str, **kw) -> Value:
    """`weigh f in <language>` with a scripted model: the request the move makes, answered."""
    req = TR.weigh(ctx_for(tmp_path), fabula_value(cat, items), **{"in": Value("string", language)})
    assert isinstance(req, R.Request)
    return req.parse(reply(req.inputs, **kw))


def target_of(v: Value, tid: str) -> dict:
    return next(n for n in v.payload["nodes"] if n["id"] == tid)


def nodes_of(v: Value) -> list[dict]:
    return v.payload["nodes"]


def check(name: str, out: Value, f: Value) -> tuple[bool, str]:
    r = C.verdict(name, out, {"f": f}, {"modifiers": {"in": "go"}}, {"name": "weigh"}, None)
    assert not isinstance(r, Refusal), r
    return r


def vol(cat: dict, items: list[dict]) -> mc.Volume:
    return mc.load_volume_text(mc.dump({**cat, "nodes": items}), filename="tally.fabulac.cosm")


# ---------------------------------------------------------------------------
# the twelve points, the tables
# ---------------------------------------------------------------------------

def test_the_twelve_points_are_the_texts_and_the_move_keeps_the_same_table():
    assert [p[:4] for p in TR.TARGET_POINTS] == list(tc.POINTS)
    assert tc.GATE_POINTS == TR.WEIGH_GATES == (1, 4, 5)
    assert TR.TABLE_POINTS == L.TABLE_POINTS and TR.PROVIDED_BY == L.PROVIDED_BY
    assert tc.VERDICTS == TR.WEIGH_VERDICTS == ("feasible", "feasible-with", "not")
    m = mc.default_registry().get("fabula")
    closed = m.data["modules"]["N"]["kinds"]["target"]["closed"]
    assert closed["verdict"] == list(tc.VERDICTS) and closed["provides.by"] == list(L.PROVIDED_BY)
    # A7's keys read as the text's numbers
    keys = ["stewardship", "specification", "old-programs-build", "provided", "runs-and-ships", "fits-shapes",
            "safe-by-default", "tools-check", "agent-skill", "budgets", "readable", "can-be-left"]
    assert [tc.point_number(k) for k in keys] == list(range(1, 13)) == [TR.point_of(k) for k in keys]
    assert tc.point_number(0) is None and tc.point_number(13) is None and tc.point_number(True) is None


@pytest.mark.parametrize("language", ["go", "rust"])
def test_each_target_table_lints_and_answers_every_ground_entry(language):
    t = L.provides_table(language)
    assert L.lint_provides(t, L.catalogue("python")) == []
    assert t["language"] == language and t["for"] == "python"
    assert len(t["provides"]) == len(L.entries("python")) == 96
    assert L.require(language).provides_path.is_file()


def test_a_lint_finds_what_is_wrong_with_a_table():
    t = copy.deepcopy(L.provides_table("go"))
    t["provides"][0]["by"] = "imported"
    t["provides"][1].pop("what")
    t["provides"].append(dict(t["provides"][2]))
    t["provides"][3] = {"entry": "division-floors", "by": "library", "what": "a module"}
    t["points"].pop()
    got = L.lint_provides(t, L.catalogue("python"))
    assert any("by is one of" in x for x in got) and any("says what provides it" in x for x in got)
    assert any("two rows" in x for x in got) and any("a library is a gap" in x for x in got)
    assert any("every one" in x for x in got)
    assert any(x.startswith("the head names 'cobol'") for x in L.lint_provides({**t, "language": "cobol"}))
    assert tc.target_table("python")["ok"] is False and tc.target_table("cobol")["ok"] is False
    assert "no target table" in tc.target_table("python")["why"]


def test_the_tables_start_from_a7s_hand_answers():
    """Where an entry was made from one of the experiment's reliances alone, the table's provider is the one A7 gave
    it (go for vulture, rust for sloppy-xml-py), but where the table speaks of every program and A7 of one."""
    a7 = {"go": {"V-R01": "built-in", "V-R02": "written", "V-R06": "written", "V-R08": "library",
                 "V-R19": "library", "V-R21": "written", "V-R22": "written", "V-R24": "written", "V-R28": "built-in",
                 "V-R29": "built-in", "V-R31": "built-in", "V-R33": "built-in"},
          "rust": {"S-R01": "written", "S-R02": "written", "S-R07": "written", "S-R10": "built-in",
                   "S-R12": "written", "S-R15": "written", "S-R21": "built-in"}}
    for language, want in a7.items():
        ans = tc.target_table(language, source="python")
        rows = {r["entry"]: r for r in ans["table"]["provides"]}
        for rid, by in want.items():
            entries = ans["from"][rid]
            assert any(rows[e]["by"] == by for e in entries), (language, rid, [(e, rows[e]["by"]) for e in entries])


# ---------------------------------------------------------------------------
# weigh: rules first, then the model
# ---------------------------------------------------------------------------

def test_rules_answer_every_reliance_of_tally_and_the_languages_points(tally):
    cat, items = tally
    rel = [it for it in items if it.get("type") == "reliance"]
    for language in ("go", "rust"):
        p = TR.weigh_rules(cat, items, language, tc.target_table(language, source="python"))
        t = p["target"]
        assert p["open-rows"] == [] and p["open-points"] == list(TR.MODEL_POINTS) == [5, 6, 9, 10, 11, 12]
        assert [w["point"] for w in t["weighed"]] == [1, 2, 3, 7, 8]
        assert all(w["answered"] == "rules" for w in t["weighed"])
        rows = {r["for"]: r for r in t["provides"]}
        assert {it["id"] for it in rel} <= set(rows)
        assert all(rows[it["id"]]["answered"] == "rules" for it in rel)
        assert rows["C:interface/command.add"] == {"for": "C:interface/command.add", "by": "written",
                                                   "what": "the new program's own command", "answered": "rules"}
        assert t["id"] == f"N:target/{language}" and t["version"] == L.provides_table(language)["version"]


@pytest.mark.parametrize("language, gaps", [
    ("go", ["C:reliance/argparse-surface"]),
    ("rust", ["C:reliance/whole-numbers-unbounded", "C:reliance/argparse-surface"])])
def test_tally_weighed_in_go_and_rust_with_its_gaps_named(tmp_path, tally, language, gaps):
    cat, items = tally
    f = fabula_value(cat, items)
    out = weigh(tmp_path, cat, items, language, spike_cases=["P:case/cli-json-and-error"],
                conditions=["uncaught errors exit 1"])
    t = target_of(out, f"N:target/{language}")
    assert t["verdict"] == "feasible-with" and t["language"] == language and t["at"] == "2026-11-18"
    assert [w["point"] for w in t["weighed"]] == list(range(1, 13))
    assert {w["point"]: w["answered"] for w in t["weighed"]} == {
        **{n: "rules" for n in (1, 2, 3, 4, 7, 8)}, **{n: "model" for n in (5, 6, 9, 10, 11, 12)}}
    p4 = t["weighed"][3]
    assert p4["score"] == 2 and all(g in p4["evidence"] for g in gaps)
    assert [r["for"] for r in t["provides"] if r.get("gap")] == gaps
    assert [c.split(" ", 1)[0] for c in t["conditions"][:len(gaps)]] == gaps
    assert t["conditions"][-1] == "uncaught errors exit 1"
    assert t["spike"] == {"use": "the option reader (C:reliance/argparse-surface), small", "level": 0, "where": None,
                          "cases": ["P:case/cli-json-and-error"]}
    assert t["made"]["move"] == "weigh" and t["made"]["in"] == language and t["made"]["engine"].startswith("rules+model")
    assert "transconception" in str(t["summary"]).lower() and "feasible with" in t["summary"]
    assert check("target-weighed", out, f) == (True, "")
    assert check("no-invention", out, f) == (True, "")
    # the fabulac reads well: the target's fields are the manifest's, its closed lists hold; and it is not confirmed
    # until its spike has stood (the lint says so too, as target-confirmed's one error)
    rep = FAB.lint(vol(out.payload, nodes_of(out)))
    assert [(p.check, p.field) for p in rep.problems() if p.item == t["id"] and p.severity == "error"] == [
        ("target-confirmed", "spike")], [str(p) for p in rep.problems() if p.item == t["id"]]
    g = tc.ready_to_entail(vol(out.payload, nodes_of(out)), language)
    assert [e for e in g["checks"]["target-confirmed"]["errors"]] == [
        f"target-confirmed N:target/{language} (tally.fabulac.cosm): the spike in {language} has not reached level 2"]


def test_a_gate_scored_0_makes_the_target_not_feasible_and_the_gates_refuse_it(tmp_path, tally):
    cat, items = tally
    f = fabula_value(cat, items)
    out = weigh(tmp_path, cat, items, "go", scores={5: 0}, verdict="feasible")
    t = target_of(out, "N:target/go")
    assert t["verdict"] == "not" and "gate 5 scored 0" in t["summary"]
    assert check("target-weighed", out, f) == (True, "")
    t["spike"]["level"] = 3                                          # a spike that stood does not save it
    g = tc.ready_to_entail(vol(out.payload, nodes_of(out)), "go")
    errs = g["checks"]["target-confirmed"]["errors"]
    assert any("the verdict on go is 'not'" in e for e in errs) and any("point 5, a gate, scored 0" in e for e in errs)
    # a target written feasible by hand over a failed gate: target-weighed refuses it, and so does the gate
    t["verdict"] = "feasible"
    ok, why = check("target-weighed", out, f)
    assert not ok and "gate point 5 scored 0, so the verdict is not" in why
    g = tc.ready_to_entail(vol(out.payload, nodes_of(out)), "go")
    assert [e for e in g["checks"]["target-confirmed"]["errors"] if "point 5, a gate" in e]


@pytest.mark.parametrize("point", [1, 4])
def test_the_other_two_gates_refuse_too(tmp_path, tally, point):
    cat, items = tally
    if point == 1:                                                    # the language's own point, from its table
        table = copy.deepcopy(L.provides_table("go"))
        table["points"][0]["score"] = 0
        ans = {**tc.target_table("go", source="python"), "table": table}
    else:                                                             # point 4: something kept cannot be provided
        items = copy.deepcopy(items)
        for it in items:
            if it["id"] == "C:reliance/argparse-surface":
                it["ruling"] = [{"is": "kept", "by": "R:maker/meadow", "on": "2026-11-18", "said": "kept"}]
        ans = copy.deepcopy(tc.target_table("go", source="python"))
        for r in ans["table"]["provides"]:
            if r["entry"] == "argparse-surface":
                r.update(by="cannot", gap="nothing gives it")
    p = TR.weigh_rules(cat, items, "go", ans)
    req_inputs = {k: Value("string", v) for k, v in TR.weigh_request_inputs(cat, items, "go", p).items()}
    t = TR.weigh_finish(p, TR.parse_weigh(reply(req_inputs), p), at="2026-11-18", made={"move": "weigh"}, sources=[])
    assert t["verdict"] == "not" and t["weighed"][point - 1]["score"] == 0
    probs = TR.weighed_problems({**t, "verdict": "feasible-with"}, items)
    assert [x for x in probs if f"gate point {point} scored 0" in x]
    if point == 4:
        out = [n for n in items if n["id"] != "N:target/go"] + [{**t, "spike": {"level": 3}}]
        errs = tc.ready_to_entail(vol(cat, out), "go")["checks"]["target-confirmed"]["errors"]
        assert any("provides nothing for C:reliance/argparse-surface, which is kept (it says it cannot)" in e
                   for e in errs)


def test_a_reply_that_misses_or_invents_is_read_again(tmp_path, tally):
    cat, items = tally
    req = TR.weigh(ctx_for(tmp_path), fabula_value(cat, items), **{"in": Value("string", "rust")})
    good = mc.yaml_load(reply(req.inputs))
    for bad, says in (({**good, "weighed": good["weighed"][1:]}, "scores no point 5"),
                      ({**good, "weighed": [{**good["weighed"][0], "score": 4}] + good["weighed"][1:]}, "0 to 3"),
                      ({**good, "weighed": [{**good["weighed"][0], "evidence": ""}] + good["weighed"][1:]},
                       "carries its evidence"),
                      ({**good, "spike": {"use": "x", "cases": ["P:case/not-there"]}}, "does not hold"),
                      ({**good, "provides": [{"for": "C:reliance/nowhere", "by": "written", "what": "x"}]},
                       "does not hold"),
                      ({**good, "verdict": "maybe"}, "the verdict is one of")):
        with pytest.raises(ValueError, match=says):
            req.parse(mc.dump(bad))
    # a point the rules answered stays the rules', whatever the model says of it
    out = req.parse(mc.dump({**good, "weighed": good["weighed"] + [{"point": 1, "score": 0, "evidence": "no"}]}))
    assert target_of(out, "N:target/rust")["weighed"][0]["answered"] == "rules"


def test_a_reliance_no_entry_answers_is_the_models_row(tmp_path, tally):
    cat, items = tally
    items = copy.deepcopy(items) + [{
        "id": "C:reliance/local-oddity", "type": "reliance", "name": "a local oddity", "summary": "something odd",
        "stance": "observed", "on": "platform", "gives": "an odd thing", "example": "odd",
        "provenance": {"mode": "manual", "sources": [], "confidence": 1, "state": "known"}}]
    req = TR.weigh(ctx_for(tmp_path), fabula_value(cat, items), **{"in": Value("string", "go")})
    assert "C:reliance/local-oddity" in req.inputs["open"].text()
    out = req.parse(reply(req.inputs, rows={"C:reliance/local-oddity": "library"}))
    row = next(r for r in target_of(out, "N:target/go")["provides"] if r["for"] == "C:reliance/local-oddity")
    assert row["answered"] == "model" and row["by"] == "library" and row["gap"].startswith("library")


def test_the_move_refuses_what_is_not_a_weighing(tmp_path, tally):
    cat, items = tally
    ctx = ctx_for(tmp_path)
    with pytest.raises(MoveError, match="names the language"):
        TR.weigh(ctx, fabula_value(cat, items))
    with pytest.raises(MoveError, match="own language"):
        TR.weigh(ctx, fabula_value(cat, items), **{"in": Value("string", "python")})
    with pytest.raises(MoveError, match="no language this build knows"):
        TR.weigh(ctx, fabula_value(cat, items), **{"in": Value("string", "cobol")})
    with pytest.raises(MoveError, match="not kept for transconception"):
        TR.weigh(ctx, fabula_value({k: v for k, v in cat.items() if k != "purpose"}, items),
                 **{"in": Value("string", "go")})


def test_a_later_weighing_goes_beside_and_is_the_one_read(tmp_path, tally):
    cat, items = tally
    first = weigh(tmp_path, cat, items, "go")
    t1 = copy.deepcopy(target_of(first, "N:target/go"))
    t1_at = {**t1, "at": "2026-11-01"}
    nodes = [t1_at if n["id"] == "N:target/go" else n for n in nodes_of(first)]
    second = weigh(tmp_path, first.payload, nodes, "go", scores={5: 0})
    t2 = target_of(second, "N:target/go-2")
    assert target_of(second, "N:target/go") == t1_at and t2["verdict"] == "not"
    f = fabula_value(first.payload, nodes)
    assert check("target-weighed", second, f) == (True, "") and check("no-invention", second, f) == (True, "")
    # the gate reads the latest weighing: the second, not feasible
    for n in nodes_of(second):
        if n.get("type") == "target":
            n["spike"]["level"] = 3
    errs = tc.ready_to_entail(vol(second.payload, nodes_of(second)), "go")["checks"]["target-confirmed"]["errors"]
    assert errs and all("N:target/go-2" in e or "go-2" in e or "point 5" in e or "'not'" in e for e in errs)


def test_no_invention_holds_a_weighing_to_its_one_target(tmp_path, tally):
    cat, items = tally
    f = fabula_value(cat, items)
    out = weigh(tmp_path, cat, items, "go")
    nodes = copy.deepcopy(nodes_of(out))
    t = next(n for n in nodes if n["id"] == "N:target/go")
    t["provides"].append({"for": "C:reliance/made-up", "by": "written", "what": "x"})
    ok, why = check("no-invention", Value("fabula", {**out.payload, "nodes": nodes}), f)
    assert not ok and "C:reliance/made-up" in why
    nodes = copy.deepcopy(nodes_of(out))
    next(n for n in nodes if n["id"] == "C:interface/command.add")["summary"] = "changed by a weighing"
    ok, why = check("no-invention", Value("fabula", {**out.payload, "nodes": nodes}), f)
    assert not ok and "changed C:interface/command.add" in why
    ok, why = check("target-weighed", f, f)
    assert not ok and "0 came back new" in why


# ---------------------------------------------------------------------------
# the spike's level, from its verdict
# ---------------------------------------------------------------------------

def _verdict(findings: list[dict]) -> dict:
    return {"cshort": "go-spike", "against": "original", "target": "go", "steps": {"kept": 10, "agree": 5},
            "findings": findings, "passes": False}


def test_target_confirmed_from_a_recorded_spike_verdict(tmp_path, tally):
    cat, items = tally
    out = weigh(tmp_path, cat, items, "go", spike_cases=["P:case/cli-json-and-error"])
    t = target_of(out, "N:target/go")
    unruled = {"case": "cli-json-and-error", "step": 1, "kind": "UNRULED difference"}
    ruled = {"case": "cli-json-and-error", "step": 2, "kind": "ruled difference", "ruling": {"is": "changed"}}
    elsewhere = {"case": "rows", "step": 0, "kind": "UNRULED difference"}
    raw = json.dumps(_verdict([unruled, ruled, elsewhere])).encode()
    sp = tc.spike_from_verdict(t["spike"], json.loads(raw), where="results/go-spike/verdict.json",
                               digest=hashlib.sha256(raw).hexdigest(), at="2026-11-18T18:19")
    assert sp["level"] == 1 and sp["evidence"]["differ"] == {"ruled": 1, "unruled": 1}
    assert sp["evidence"]["first"] == "cli-json-and-error step 1: UNRULED difference"
    t["spike"] = sp
    g = tc.ready_to_entail(vol(out.payload, nodes_of(out)), "go")
    assert any("has not reached level 2" in e for e in g["checks"]["target-confirmed"]["errors"])
    # only the spike's own cases count: a difference elsewhere is not the spike's
    t["spike"] = tc.spike_from_verdict(t["spike"], _verdict([ruled, elsewhere]), where="v.json", digest="ab")
    assert t["spike"]["level"] == 3 and t["spike"]["evidence"]["where"] == {"file": "v.json", "digest": "ab"}
    g = tc.ready_to_entail(vol(out.payload, nodes_of(out)), "go")
    assert g["checks"]["target-confirmed"] == {"state": "holds", "errors": [], "warnings": [], "notes": []}
    with pytest.raises(tc.CasesError, match="names no case"):
        tc.spike_from_verdict({"use": "nothing named"}, _verdict([]))


# ---------------------------------------------------------------------------
# the target bank: the twelve points put to the transconceiver
# ---------------------------------------------------------------------------

def test_the_twelve_points_are_asked_of_the_target_named_and_the_answer_kept(tmp_path, tally):
    cat, items = tally
    out = weigh(tmp_path, cat, items, "rust")
    p = tmp_path / "tally.fabulac.cosm"
    p.write_text(mc.dump({**out.payload, "nodes": nodes_of(out)}), encoding="utf-8")
    led = dl.open_twin(p).ledger
    banks = {b["name"]: b for b in mc.default_registry().get("fabula").banks()}
    assert [e["id"] for e in banks["transconception-target"]["questions"]][:2] == ["version", "conditions"]
    r = dl.raise_questions(led, target="rust", at="2026-11-18T10:00:00Z")
    tb = [q for q in r.questions if q["raised"]["from"].startswith("transconception-target/")]
    assert [q["about"] for q in tb] == [f"N:target/rust#weighed[{i}].ruled" for i in range(12)]
    first = tb[0]["asks"]
    assert first.startswith("Point 1, a gate: does rust have stewardship") and "scored it 3 of 3" in first
    assert "Point 4, a gate" in tb[3]["asks"] and "gaps: C:reliance/whole-numbers-unbounded" in tb[3]["asks"]
    assert not [q for q in dl.raise_questions(led).questions
                if q["raised"]["from"].startswith("transconception-target/")]          # no target named: none
    dl.land(led, tb)
    rows = [{"question": tb[0]["id"], "says": "yes"}, {"question": tb[4]["id"], "says": "2: it ships as one program"}]
    av = dl.answers_delta(led, rows, session={"with": {"to": "transconceiver", "who": "the maintainer"},
                                              "through": "person"}, at="2026-11-18T10:20:00Z")
    dl.record_answers_volume(led, dl.write_answers_volume(av))
    dl.settle(led, at="2026-11-18T10:30:00Z")
    t = next(d for d in led.items if isinstance(d, dict) and d.get("id") == "N:target/rust")
    assert t["weighed"][0]["ruled"] and t["weighed"][4]["ruled"]
    asked_again = [q["about"] for q in dl.raise_questions(led, target="rust").questions
                   if q["raised"]["from"].startswith("transconception-target/") and q.get("state") not in dl.ENDED]
    assert "N:target/rust#weighed[0].ruled" not in asked_again


# ---------------------------------------------------------------------------
# the declaration, and a program that weighs
# ---------------------------------------------------------------------------

def test_weigh_is_declared_since_thym_1_with_the_texts_contract():
    d = dc.load()
    w = d["weigh"]
    assert w.since == 1 and d.view(0).get("weigh") is None and w.owner == "fabula" and w.asks is True
    assert w.takes == (("fabula",),) and w.gives == ("fabula",) and w.modifiers == {"in": ("string",)}
    assert list(w.contract) == ["target-weighed", "no-invention", "fabula-checks", "provenance"]
    assert "target-weighed" in ct.CHECKS                                # a row of the synced 7.3
    assert C.CHECKS.lookup("no-invention", "move:weigh") is TR._weigh_no_invention
    assert C.CHECKS.lookup("no-invention") is not TR._weigh_no_invention          # every other move keeps its own


WEIGH_PROGRAM = """thym 1

program weigh-a-target
  why: a language is weighed on the twelve points before anything is entailed into it.

  takes f: fabula, language: string
  gives g: fabula

  give weigh f in language
end
"""


class Scripted:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def complete(self, contract, inputs, *, budget):
        ins = {k: (v[0] if isinstance(v, tuple) else v) for k, v in inputs.items()}
        self.sent.append({"move": contract.get("move"), "inputs": ins})
        text = reply({k: Value("string", str(v)) if not isinstance(v, Value) else v for k, v in ins.items()},
                     spike_cases=["P:case/cli-json-and-error"])
        # the host's coprocessor stamps the engine into a YAML answer whose schema asks it (thym_host); this one does too
        assert contract["schema"]["stamp"] == "engine"
        return candidate(text + "engine: model:scripted\n", engine="model:scripted", tokens=10)


def test_a_program_weighs_tally_in_go_under_contract(tmp_path, tally):
    cat, items = tally
    (tmp_path / "f.fabulac.cosm").write_text(mc.dump({**cat, "nodes": items}), encoding="utf-8")
    (tmp_path / "language.txt").write_text("go", encoding="utf-8")
    prog = tmp_path / "weigh.thym"
    prog.write_text(WEIGH_PROGRAM, encoding="utf-8")
    c = thym.check_file(prog)
    assert not isinstance(c, Refusal), str(c)
    rows = [{"name": "f", "type": "fabula", "path": "f.fabulac.cosm", "sha256": digest_path(tmp_path / "f.fabulac.cosm")},
            {"name": "language", "type": "string", "path": "language.txt",
             "sha256": digest_path(tmp_path / "language.txt")}]
    p = pl.plan(c, rows, program="weigh-a-target")
    assert not isinstance(p, Refusal), str(p)
    cp = Scripted()
    t = RUN.run(p, inputs_root=tmp_path, root=tmp_path / "root", program=prog, coprocessor=cp,
                engines=H.engines(feed=None), now=NOW)
    assert t.landed, getattr(t, "refusal", t)
    checks = t.records[-1]["checks"]
    assert {c["name"] for c in checks} >= {"target-weighed", "no-invention", "fabula-checks", "provenance"}
    assert all(c["ok"] for c in checks), checks
    assert [s["move"] for s in cp.sent] == ["weigh"]
    g = mc.yaml_load(sorted((t.dir / "outputs").glob("g.*"))[0].read_text(encoding="utf-8"))
    tg = next(n for n in g["nodes"] if n["id"] == "N:target/go")
    assert tg["verdict"] == "feasible-with" and tg["made"]["engine"] == "rules+model:scripted"


# ---------------------------------------------------------------------------
# the promoted fixtures: A7's weighings, gate 2
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fix, language, verdict, spike_cases", [
    (VULTURE, "go", "feasible-with", ["P:case/x0.V-C32", "P:case/x0.V-C33"]),
    (SLOPPY, "rust", "feasible", ["P:case/x0.S-C05", "P:case/x0.S-C06"])])
def test_the_promoted_fixtures_carry_a7s_weighing_and_reach_gate_2(fix, language, verdict, spike_cases):
    v = mc.load_volume(fix)
    t = v.items[f"N:target/{language}"].data
    assert t["verdict"] == verdict and t["by"] == "R:maker/agent-w1-xp" and t["made"]["by-hand"] is True
    assert [w["point"] for w in t["weighed"]] == list(range(1, 13))
    assert all(w["score"] in (0, 1, 2, 3) and w["evidence"] for w in t["weighed"])
    assert not [w for w in t["weighed"] if w["point"] in tc.GATE_POINTS and w["score"] == 0]
    sp = t["spike"]
    assert sp["level"] == 3 and tc.spike_cases(sp) == spike_cases
    assert sp["evidence"]["differ"]["unruled"] == 0
    assert sp["evidence"]["where"]["file"].startswith(f"../results/2026-11-18-1819/{fix.name.split('.')[0]}/")
    g = tc.ready_to_entail(v, language)
    assert g["checks"]["target-confirmed"]["state"] == "holds"
    assert g["checks"]["ruled"]["state"] == "holds"
    assert g["do-not-hold"] == []                  # since the ground (pins 25): stands-alone holds; rows by rules
    assert g["not-measured"] == ["nothing-carried"]            # no source given here
    rep = FAB.lint(v)
    assert not [p for p in rep.problems() if p.item == f"N:target/{language}" and p.severity == "error"]
    # A7 wrote a row per reliance only; target-weighed asks one for every interface and behaviour kept as well, so a
    # hand weighing is read by the gate, never offered as a weigh call's output
    probs = TR.weighed_problems(t, [it.data for it in v.items.values()])
    assert probs and all("provides says nothing of C:interface/" in x or "provides says nothing of C:behaviour/" in x
                         for x in probs)


@pytest.mark.skipif(not (X0 / "vulture" / "target-go.md").is_file(), reason="the experiment's files are not here")
@pytest.mark.skipif(not (TG.CLONES / "vulture" / "vulture").is_dir(), reason="the experiment's clones are not here")
def test_the_promoter_writes_the_fixtures_from_the_experiments_files(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("promote_x0", PROMOTER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "_scratch_seams", lambda: None)       # the suite holds every seam at scratch already
    for name, language in (("vulture", "go"), ("sloppy-xml-py", "rust")):
        out = tmp_path / f"{name}.fabulac.cosm"
        src = X0 / name / f"{name}.fabulac.cosm"         # the verdicts' paths are written from the x0 fabulac's folder
        mod.main([str(src), str(X0 / "results/2026-11-13-1006" / name / "py-roundtrip/verdict.json"), str(out),
                  "--target", str(X0 / name / f"target-{language}.md"),
                  str(X0 / "results/2026-11-18-1819" / name / f"{language}-spike/verdict.json"),
                  "--ground", str(TG.CLONES / name)])
        assert out.read_text(encoding="utf-8") == (PROMOTED / f"{name}.fabulac.cosm").read_text(encoding="utf-8")
