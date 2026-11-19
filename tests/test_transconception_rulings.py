"""Transconception's rulings (0.8, phase 3): the role `transconceiver`, bank selection by purpose, a
transconception's three banks (standing, target, rulings), `batch`, `made-for`, the riskiest first, a skipped
question blocking gate 1's `ruled`, and the judge's differences come back as questions (`why: conflict`).
enough/dialectic.py, enough/thym/moves/dialectic.py, the banks in defaults/cosm/manifests/fabula.manifest.cosm;
MacroCOSM OES 18.4.9 and 18.6.6.

The sitting is simulated on the converted vulture fixture (tests/fixtures/fabula/transconception/), no model: its 506
rulings are taken back to what a reading leaves while unruled (a pending entry with its proposal; an item with only a
bare `kept` has no ruling at all, proposed `kept` by default), the questions are raised, a person's answers are
written as an answers volume (data), recorded, settled, and every ruling comes back as it was, with gate 1's `ruled`
holding. Everything reads tests/fixtures/ or writes under tmp_path.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
from collections import Counter
from pathlib import Path

import pytest

from enough import dialectic as dl
from enough import macrocosm as mc
from enough import transconception as tc

REPO = Path(__file__).resolve().parents[1]
FAB = REPO / "tests" / "fixtures" / "fabula"
VULTURE = FAB / "transconception" / "vulture.fabulac.cosm"
SLOPPY = FAB / "transconception" / "sloppy-xml-py.fabulac.cosm"
CLOSE = FAB / "guides" / "close.md.fabulan.cosm"
ROSE = FAB / "poems" / "the-sick-rose.txt.fabulap.cosm"
TALLY = FAB / "tally.fabulac.cosm"
X0_VERDICT = Path("/Users/m3u/METMcloud/fabulac-test-repos/_x0/results/2026-11-13-1006/vulture/py-roundtrip/verdict.json")
RAISED = "2026-11-18T10:00:00Z"
ANSWERED_AT = "2026-11-18T10:20:00Z"
SETTLED = "2026-11-18T10:30:00Z"
SESSION = {"with": {"to": "transconceiver", "who": "the program's maintainer, by questionnaire"}, "through": "person"}
SCOPE = ("made-for", "about", "steps")
PROPOSAL = ("is", "allowing", "because", "until", "to", "case")
RULINGS_BANK = "transconception-rulings"


def twin(path: Path = VULTURE) -> dl.Twin:
    return dl.open_twin(path)


def ruling_qs(qs) -> list[dict]:
    return [q for q in qs if dl.is_ruling_question(q)]


def unrule(led: dl.Ledger) -> dict[str, list[dict]]:
    """Every ruling taken back to what a reading leaves while unruled: a pending entry of the same scope with the
    ruling as its proposal; an item whose rulings are all a bare `kept` has none at all. Returns the rulings as they
    were, by item."""
    was = {}
    for d in led.items:
        if not isinstance(d, dict) or "ruling" not in d:
            continue
        was[d["id"]] = copy.deepcopy(d["ruling"])
        bare = all(set(x) <= {"is", "by", "on", "said"} and x.get("is") == "kept" for x in d["ruling"])
        if bare and d.get("type") != "case":
            del d["ruling"]
            continue
        d["ruling"] = [{"pending": "not ruled yet", **{k: x[k] for k in SCOPE if k in x},
                        "proposed": {k: x[k] for k in PROPOSAL if k in x}} for x in d["ruling"]]
    return was


def strip_all(led: dl.Ledger) -> int:
    n = 0
    for d in led.items:
        if isinstance(d, dict) and "ruling" in d:
            del d["ruling"]
            n += 1
    return n


def shape(rs) -> list[str]:
    return sorted(json.dumps({k: x.get(k) for k in SCOPE + PROPOSAL}, sort_keys=True) for x in rs)


def answer_all(led: dl.Ledger, qs: list[dict], says: dict | None = None, *, skip: tuple = ()) -> dl.Recorded:
    """The person's answers, as data: an answers volume written and recorded (Thym 22.2), every question answered
    `as proposed` unless `says` gives other words; `skip` lists the questions skipped."""
    said = says or {}
    rows = [{"question": q["id"], **({"skip": True} if q["id"] in skip else {"says": said.get(q["id"], "as proposed")})}
            for q in qs]
    av = dl.answers_delta(led, rows, session=SESSION, at=ANSWERED_AT)
    text = dl.write_answers_volume(av)
    return dl.record_answers_volume(led, text)


def lint_errors(led: dl.Ledger) -> Counter:
    return Counter(p.check for p in dl.default_checker(led.volume()).errors)


# ---------------------------------------------------------------------------
# the role, and bank selection by purpose
# ---------------------------------------------------------------------------

def test_the_transconceiver_is_a_word_of_to():
    assert "transconceiver" in dl.TO_WORDS
    m = mc.default_registry().get("fabula")
    for b in m.banks():
        if b["name"].startswith("transconception-"):
            assert b["to"] == "transconceiver" and all(e["to"] == "transconceiver" for e in b["questions"])


@pytest.mark.parametrize("path,names", [
    (CLOSE, ["fabulan"]), (ROSE, ["fabulap"]), (TALLY, ["fabulac"]),
    (VULTURE, ["fabulac", "transconception-standing", "transconception-target", RULINGS_BANK]),
    (SLOPPY, ["fabulac", "transconception-standing", "transconception-target", RULINGS_BANK])])
def test_banks_are_chosen_by_flavour_and_by_purpose(path, names):
    assert [b["name"] for b in dl.banks_for(twin(path))] == names


def test_a_fabulac_kept_for_its_own_sake_is_asked_none_of_a_transconceptions_banks():
    t = twin()
    del t.ledger.catalog["purpose"]
    assert [b["name"] for b in dl.banks_for(t)] == ["fabulac"]
    assert not any(q["raised"].get("from", "").startswith("transconception-") for q in dl.raise_questions(t).questions)


def test_selection_is_general_a_key_unread_selects_nothing_and_a_new_reading_selects():
    led = twin().ledger
    assert dl.bank_applies(led, {"for": {}}) and dl.bank_applies(led, {"for": {"module": "S"}})
    assert dl.bank_applies(led, {"for": {"flavour": ["fabulap", "fabulac"], "purpose": "transconception"}})
    assert not dl.bank_applies(led, {"for": {"flavour": "fabulac", "purpose": "other"}})
    assert dl.bank_applies(led, {"for": {"source-kind": "authored"}})         # no reading of it yet: selects nothing
    dl.BANK_FOR["source-kind"] = lambda lg: (lg.catalog.get("source") or {}).get("kind")
    try:
        assert not dl.bank_applies(led, {"for": {"source-kind": "authored"}})
        assert dl.bank_applies(led, {"for": {"source-kind": "folder"}})
    finally:
        del dl.BANK_FOR["source-kind"]


# ---------------------------------------------------------------------------
# a whole sitting, in one pass
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sitting():
    t = twin()
    led = t.ledger
    before = lint_errors(led)
    was = unrule(led)
    r = dl.raise_questions(led, at=RAISED)
    dl.land(led, r.questions)
    asked = ruling_qs(r.questions)
    rec = answer_all(led, asked)
    s = dl.settle(led, at=SETTLED)
    return {"twin": t, "led": led, "was": was, "raised": r, "asked": asked, "rec": rec, "settled": s,
            "before": before}


def test_one_sitting_rules_the_whole_fabulac(sitting):
    led, was, asked, s = sitting["led"], sitting["was"], sitting["asked"], sitting["settled"]
    assert len(was) == 286 and sum(len(v) for v in was.values()) == 506
    covered = sum(1 + len(q.get("batch") or []) for q in asked)
    needed = 0
    for iid, v in was.items():                                        # a bare kept: one default question; else each
        bare = all(set(x) <= {"is", "by", "on", "said"} and x["is"] == "kept" for x in v)
        needed += 1 if bare and not iid.startswith("P:case/") else len(v)
    assert covered == needed == 506
    assert len(asked) < covered / 3                                   # batches: far fewer questions than rulings
    assert len(sitting["rec"].recorded) == len(asked) and not sitting["rec"].refused
    assert len(s.settled) == len(asked) and not s.counters and not s.needs_reading and not s.waiting
    for iid, rs in was.items():                                       # every ruling as it was
        assert shape(led.item(iid)["ruling"]) == shape(rs), iid
    g = tc.ready_to_keep(led.volume())
    assert g["checks"]["ruled"] == {"state": "holds", "errors": [], "warnings": [], "notes": []}
    assert lint_errors(led) == sitting["before"]                      # nothing else moved


def test_the_sitting_writes_only_the_asked_with_the_session_as_provenance(sitting):
    led = sitting["led"]
    assert dl.only_the_asked(twin(), led) == []
    assert dl.provenance_written(led) == []
    sid = sitting["rec"].session
    for q in sitting["asked"]:
        q = led.question(q["id"])
        assert q["state"] == "answered" and q["settled"]["wrote"] == dl.ruling_addresses(q)
        for addr in q["settled"]["wrote"]:
            d = led.item(addr.partition("#")[0])
            assert d["provenance"]["answered"]["ruling"]["sources"] == [sid]
            mine = [x for x in d["ruling"] if dl._scope(x) == dl._scope(q["proposed"])]
            assert len(mine) == 1 and mine[0]["by"] == "R:maker/transconceiver" and mine[0]["on"] == "2026-11-18"
            assert mine[0]["said"] == "as proposed"


def test_the_sitting_lands_in_place_and_reads_back(sitting, tmp_path):
    t = sitting["twin"]
    out = tmp_path / "vulture.fabulac.cosm"
    out.write_text(t.render(), encoding="utf-8")
    back = twin(out)
    for iid, rs in sitting["was"].items():
        assert shape(back.ledger.item(iid)["ruling"]) == shape(rs), iid
    assert tc.ready_to_keep(back.ledger.volume())["checks"]["ruled"]["state"] == "holds"


def test_the_riskiest_are_asked_first(sitting):
    asked = sitting["asked"]
    entries = [q["raised"]["from"].split("/", 1)[1] for q in asked]
    order = ["interface", "behaviour", "reliance", "setting", "structure", "case"]
    assert [e for e in order if e in entries] == sorted(set(entries), key=order.index)   # the bank's order
    assert entries == sorted(entries, key=order.index)
    led = sitting["led"]
    cases = dl._case_counts(led)
    for entry in set(entries):
        risks = [dl.ruling_risk(led.item(q["about"].partition("#")[0]), cases) for q in asked
                 if q["raised"]["from"].endswith("/" + entry)]
        assert risks == sorted(risks, reverse=True), entry


def test_a_fresh_fabulac_is_ruled_in_a_handful_of_batches():
    t = twin()
    led = t.ledger
    assert strip_all(led) == 286
    r = dl.raise_questions(led, at=RAISED)
    asked = ruling_qs(r.questions)
    # one question per kind, every item proposed kept; cases carry no ruling, so none is asked of them
    assert [q["raised"]["from"] for q in asked] == [f"{RULINGS_BANK}/{k}" for k in
                                                     ("interface", "behaviour", "reliance", "setting", "structure")]
    assert [1 + len(q["batch"]) for q in asked] == [85, 71, 100, 17, 6]
    first = led.item(asked[0]["about"].partition("#")[0])
    assert first["surface"] in ("command", "format", "stream")       # the riskiest: what a user types or reads
    assert all(q["proposed"] == {"is": "kept"} and q["to"] == "transconceiver" and q["kind"] == "choice"
               and q["options"] == list(dl.RULING_OPTIONS) and q["hint"].startswith("One answer rules all")
               for q in asked)
    assert "Proposed: kept." in asked[0]["asks"]
    dl.land(led, r.questions)
    answer_all(led, asked)
    s = dl.settle(led, at=SETTLED)
    assert len(s.settled) == 5
    assert tc.ready_to_keep(led.volume())["checks"]["ruled"]["state"] == "holds"
    assert all(len(d["ruling"]) == 1 and d["ruling"][0]["is"] == "kept" and "made-for" not in d["ruling"][0]
               for d in led.items if isinstance(d, dict) and "ruling" in d)


def test_a_skipped_question_blocks_gate_one():
    led = twin().ledger
    strip_all(led)
    r = dl.raise_questions(led, at=RAISED)
    dl.land(led, r.questions)
    asked = ruling_qs(r.questions)
    skipped = asked[3]                                               # the settings
    rec = answer_all(led, asked, skip=(skipped["id"],))
    assert rec.skipped == [skipped["id"]]
    dl.settle(led, at=SETTLED)
    g = tc.ready_to_keep(led.volume())
    assert g["checks"]["ruled"]["state"] == "fails" and "ruled" in g["do-not-hold"]
    errs = g["checks"]["ruled"]["errors"]
    blocked = [e for e in errs if skipped["id"] in e]
    assert len(blocked) == 1 + len(skipped["batch"]) == 17 and all("skipped blocks the gate" in e for e in blocked)
    # answered, it holds
    dl.record(led, [{"question": skipped["id"], "says": "kept"}], session=SESSION, at=ANSWERED_AT)
    dl.settle(led, at=SETTLED)
    assert tc.ready_to_keep(led.volume())["checks"]["ruled"]["state"] == "holds"


# ---------------------------------------------------------------------------
# batch: one answer settles many
# ---------------------------------------------------------------------------

def _fresh_settings() -> tuple[dl.Ledger, dict]:
    led = twin().ledger
    strip_all(led)
    r = dl.raise_questions(led, at=RAISED)
    dl.land(led, r.questions)
    q = next(q for q in r.questions if q["raised"]["from"] == f"{RULINGS_BANK}/setting")
    return led, q


@pytest.mark.parametrize("says,want", [
    ("as proposed", {"is": "kept"}),
    ("yes", {"is": "kept"}),
    ("kept", {"is": "kept"}),
    ("alike, the lines in any order: lines-in-any-order", {"is": "alike", "allowing": "lines-in-any-order"}),
    ("free: nobody sets these by hand", {"is": "free", "because": "nobody sets these by hand"}),
    ("kept wrong, because users rely on it", {"is": "kept-wrong", "because": "users rely on it"}),
    ("changed: to a flag read from the environment", {"is": "changed", "to": "a flag read from the environment"}),
])
def test_one_answer_writes_the_same_ruling_into_every_item_of_its_batch(says, want):
    led, q = _fresh_settings()
    members = dl.ruling_addresses(q)
    assert len(members) == 17
    dl.record(led, [{"question": q["id"], "says": says}], session=SESSION, at=ANSWERED_AT)
    s = dl.settle(led, at=SETTLED)
    assert s.settled == [(q["id"], members)] and not s.counters
    for addr in members:
        (r,) = led.item(addr.partition("#")[0])["ruling"]
        assert {k: r[k] for k in r if k not in ("by", "on", "said")} == want and r["said"] == says


def test_a_ruling_missing_what_its_word_needs_is_asked_again_by_a_counter():
    led, q = _fresh_settings()
    dl.record(led, [{"question": q["id"], "says": "alike"}], session=SESSION, at=ANSWERED_AT)
    s = dl.settle(led, at=SETTLED)
    assert s.settled == [] and len(s.counters) == 1
    _qid, cid, errs = s.counters[0]
    c = led.question(cid)
    assert c["why"] == "counter" and c["batch"] == q["batch"] and c["proposed"] == q["proposed"]
    assert c["asks"].startswith("That ruling needs one more thing")                 # the bank's counter words
    assert all("ruling" not in led.item(a.partition("#")[0]) for a in dl.ruling_addresses(q))
    dl.record(led, [{"question": cid, "says": "alike, exit-only"}], session=SESSION, at="2026-11-18T10:40:00Z")
    s = dl.settle(led, at="2026-11-18T10:50:00Z")
    assert (cid, dl.ruling_addresses(q)) in s.settled


def test_i_dont_know_leaves_every_item_of_the_batch_unruled_in_the_persons_words():
    led, q = _fresh_settings()
    dl.record(led, [{"question": q["id"], "says": "I don't know"}], session=SESSION, at=ANSWERED_AT)
    s = dl.settle(led, at=SETTLED)
    assert s.settled and not s.counters
    for addr in dl.ruling_addresses(q):
        assert led.item(addr.partition("#")[0])["ruling"] == [{"pending": "I don't know"}]
    errs = tc.ready_to_keep(led.volume())["checks"]["ruled"]["errors"]
    assert sum("not ruled yet" in e for e in errs) == 17


def test_a_batch_question_is_no_duplicate_of_its_members():
    led, q = _fresh_settings()
    again = dl.raise_questions(led, at=RAISED)
    assert ruling_qs(again.questions) == []                          # every item stands in an open question
    assert not any("ruling" in (q2.get("about") or "") for q2 in again.questions)


# ---------------------------------------------------------------------------
# made-for: a later target asks again only what names another
# ---------------------------------------------------------------------------

def _with_rust(led: dl.Ledger) -> None:
    led.add({"id": "N:target/rust", "type": "target", "name": "rust", "summary": "vulture in rust", "stance":
             "observed", "language": "rust", "provenance": {"mode": "manual", "confidence": 1, "state": "known"}})


def test_a_new_target_raises_again_only_the_rulings_that_name_another():
    t = twin()
    led = t.ledger
    _with_rust(led)
    assert ruling_qs(dl.raise_questions(led, target="go").questions) == []          # ruled for go throughout
    assert ruling_qs(dl.raise_questions(led).questions) == []                       # and for gate 1
    r = dl.raise_questions(led, target="rust", at=RAISED)
    asked = ruling_qs(r.questions)
    want = set()                                                     # by rule, from the data: (item, part, steps)
    for d in led.items:
        parts: dict = {}
        for x in (d.get("ruling") or []) if isinstance(d, dict) else []:
            parts.setdefault((x.get("about"), json.dumps(x.get("steps"))), []).append(x)
        for (about, steps), xs in parts.items():
            if all(x.get("made-for") not in (None, "N:target/rust") for x in xs):
                want.add((d["id"], about, steps))
    got = {(a.partition("#")[0], q["proposed"].get("about"), json.dumps(q["proposed"].get("steps")))
           for q in asked for a in dl.ruling_addresses(q)}
    assert got == want and len(want) > 100
    assert all(q["proposed"]["made-for"] == "N:target/rust" and "(for rust)" in q["asks"] for q in asked)
    untouched = {d["id"] for d in led.items if isinstance(d, dict) and d.get("ruling")} - {w[0] for w in want}
    assert untouched                                                 # items ruled for any target are not asked
    # the target bank is asked of the target named, once
    tb = [q for q in r.questions if q["raised"]["from"].startswith("transconception-target/")]
    assert {(q["about"], q["raised"]["from"]) for q in tb} == {
        ("N:target/rust#version", "transconception-target/version"),
        ("N:target/rust#conditions", "transconception-target/conditions")}
    assert not [q for q in dl.raise_questions(led).questions if q["raised"]["from"].startswith(
        "transconception-target/")]                                  # no target named: none
    before = {d["id"]: copy.deepcopy(d.get("ruling")) for d in led.items if isinstance(d, dict) and d.get("ruling")}
    dl.land(led, r.questions)
    answer_all(led, asked)
    dl.settle(led, at=SETTLED)
    for iid, rs in before.items():                                   # the go and python rulings stand as they were
        now = led.item(iid)["ruling"]
        assert [x for x in now if x.get("made-for") != "N:target/rust"] == rs
    assert ruling_qs(dl.raise_questions(led, target="rust").questions) == []
    g = tc.ready_to_keep(led.volume())
    assert g["checks"]["ruled"]["state"] == "holds"


def test_a_ruling_made_for_no_target_holds_for_a_new_one():
    led = twin().ledger
    _with_rust(led)
    d = next(d for d in led.items if isinstance(d, dict) and d.get("type") == "setting" and d.get("ruling"))
    assert all("made-for" not in x for x in d["ruling"])
    assert dl.unruled_scopes(d, "N:target/rust") == []
    go_only = {"is": "free", "made-for": "N:target/go", "by": "R:maker/transconceiver", "on": "2026-11-13"}
    assert dl.unruled_scopes({"ruling": [go_only]}, "N:target/rust") == [{"is": "free", "made-for": "N:target/rust"}]
    assert dl.unruled_scopes({"ruling": [go_only]}, None) == []
    assert dl.unruled_scopes({}, "N:target/rust") == [{"is": "kept"}]


def test_a_target_the_fabulac_does_not_hold_is_refused():
    with pytest.raises(dl.DialecticError, match="weigh it first"):
        dl.raise_questions(twin(), target="cobol")


# ---------------------------------------------------------------------------
# the judge's differences come back as questions, why: conflict
# ---------------------------------------------------------------------------

def fake_verdict() -> dict:
    """A verdict in the shape the judge writes (x0's `x0_harness.py judge`): one ruled difference (shown, needs
    nothing), one unruled difference, one unstable step, one case the fabulac does not hold."""
    return {
        "cshort": "go-apart", "against": "original", "target": "go", "recorded_digest": "69bc", "run_digest": "9eb0",
        "rulings_digest": "be7c", "steps": {"kept": 92, "agree": 90}, "share": 0.9783, "passes_95": True,
        "unruled": 3, "passes": False,
        "findings": [
            {"case": "V-C07", "step": 0, "kind": "ruled difference", "ruling": {"is": "changed", "steps": [0]},
             "argv": {"argv": ["m.py"], "stdin": None}, "original": {"exit": 3, "out": "a\n", "err": ""},
             "cshort": {"exit": 3, "out": "a\nb\n", "err": ""}},
            {"case": "V-C10", "step": 0, "kind": "UNRULED difference", "ruling": None,
             "argv": {"argv": ["m.py"], "stdin": None},
             "original": {"exit": 3, "out": "m.py:1: unused import 'foo' (90% confidence)\n", "err": ""},
             "cshort": {"exit": 3, "out": "m.py:1: unused import \"foo\" (90% confidence)\n", "err": ""}},
            {"case": "V-C33", "step": 1, "kind": "original unstable, not ruled"},
            {"case": "V-C99", "step": 0, "kind": "UNRULED difference", "original": {"exit": 0, "out": "", "err": ""},
             "cshort": {"exit": 1, "out": "", "err": "x"}},
        ]}


def test_the_conflicts_read_the_verdict_as_the_cases_lane_does(tmp_path):
    """One reading of a verdict for both lanes: `differences_from_verdict`, whose `needs-ruling` says what comes
    back as a question; a file and its mapping raise the same questions, and the file is named in the hint."""
    rows = tc.differences_from_verdict(fake_verdict())
    assert [(f["case"], f["needs-ruling"]) for f in rows] == [
        ("V-C07", False), ("V-C10", True), ("V-C33", True), ("V-C99", True)]
    p = tmp_path / "verdict.json"
    p.write_text(json.dumps(fake_verdict()), encoding="utf-8")
    from_file = dl.conflicts_from_verdict(twin(), p, at=RAISED).questions
    from_map = dl.conflicts_from_verdict(twin(), fake_verdict(), at=RAISED).questions
    assert [q["about"] for q in from_file] == [q["about"] for q in from_map] == [
        "P:case/x0.V-C10#ruling", "P:case/x0.V-C33#ruling"]
    assert str(p) in from_file[0]["hint"] and str(p) not in from_map[0]["hint"]
    stale = {**fake_verdict(), "findings": [{"case": "V-C10", "step": 0, "kind": "recorded against another source"}]}
    assert dl.conflicts_from_verdict(twin(), stale).questions == []          # it needs a recording, not a ruling


@pytest.mark.skipif(not X0_VERDICT.is_file(), reason="the experiment's verdicts are not on this machine")
def test_the_experiments_own_verdict_raises_nothing():
    rows = tc.differences_from_verdict(json.loads(X0_VERDICT.read_text(encoding="utf-8")))
    assert rows and not any(f["needs-ruling"] for f in rows)
    r = dl.conflicts_from_verdict(twin(), X0_VERDICT)
    assert r.questions == [] and r.skipped == []


def test_a_difference_no_ruling_covers_comes_back_as_a_conflict_question():
    led = twin().ledger
    r = dl.conflicts_from_verdict(led, fake_verdict(), run="judge-run", at=RAISED)
    assert r.skipped == [("V-C99", "the fabulac holds no such case")]
    q10, q33 = r.questions
    assert (q10["about"], q10["why"], q10["to"], q10["raised"]["from"], q10["kind"]) == (
        "P:case/x0.V-C10#ruling", "conflict", "transconceiver", "judge", "choice")
    assert q10["proposed"] == {"made-for": "N:target/go", "steps": [0]} and "as proposed" not in q10["options"]
    assert "the original gave exit 3, output" in q10["asks"] and "the go entailment gave exit 3" in q10["asks"]
    assert "unused import 'foo'" in q10["asks"] and 'unused import \\"foo\\"' in q10["asks"]
    assert q33["about"] == "P:case/x0.V-C33#ruling" and "original unstable, not ruled" in q33["asks"]
    dl.land(led, r.questions)
    again = dl.conflicts_from_verdict(led, fake_verdict())
    assert again.questions == [] and len(again.skipped) == 3                       # one standing question per case
    g = tc.ready_to_keep(led.volume())                                             # a conflict blocks gate 1
    assert g["checks"]["ruled"]["state"] == "fails"
    assert sum(q10["id"] in e for e in g["checks"]["ruled"]["errors"]) == 1
    before = copy.deepcopy(led.item("P:case/x0.V-C10")["ruling"])
    dl.record(led, [{"question": q10["id"], "says": "alike, the order of lines is free: lines-in-any-order"},
                    {"question": q33["id"], "says": "free: the walk's order is the file system's"}],
              session=SESSION, at=ANSWERED_AT)
    s = dl.settle(led, at=SETTLED)
    assert len(s.settled) == 2 and not s.counters
    after = led.item("P:case/x0.V-C10")["ruling"]
    new = [x for x in after if x not in before]
    assert len(new) == 1 and {k: new[0][k] for k in ("is", "allowing", "made-for", "steps")} == {
        "is": "alike", "allowing": "lines-in-any-order", "made-for": "N:target/go", "steps": [0]}
    (r33,) = [x for x in led.item("P:case/x0.V-C33")["ruling"]
              if x.get("steps") == [1] and x.get("made-for") == "N:target/go" and "about" not in x]
    assert (r33["is"], r33["because"]) == ("free", "the walk's order is the file system's")
    assert tc.ready_to_keep(led.volume())["checks"]["ruled"]["state"] == "holds"


# ---------------------------------------------------------------------------
# the standing bank
# ---------------------------------------------------------------------------

def test_the_standing_bank_asks_who_rules_the_terms_and_the_statements_only_while_unanswered():
    led = twin().ledger
    r = dl.raise_questions(led)
    assert not [q for q in r.questions if q["raised"]["from"].startswith("transconception-standing/")]
    # nobody rules yet, and the licence's lane is not recorded: who rules, and the lane, are asked
    led.items[:] = [d for d in led.items if not (isinstance(d, dict) and d.get("capacity") == "transconceiver")]
    led.catalog["nodes"] = led.items
    lic = led.item("R:licence/mit")
    del lic["lane"]
    r = dl.raise_questions(led, at=RAISED)
    st = {q["raised"]["from"].split("/")[1]: q for q in r.questions
          if q["raised"]["from"].startswith("transconception-standing/")}
    assert set(st) == {"who-rules", "lane"}
    assert st["lane"]["about"] == "R:licence/mit#lane" and st["lane"]["options"] == ["open", "bound", "closed"]
    assert st["who-rules"]["about"] == "R" and st["who-rules"]["to"] == "transconceiver"
    dl.land(led, r.questions)
    dl.record(led, [{"question": st["who-rules"]["id"], "says": "The maintainer, who wrote most of it"},
                    {"question": st["lane"]["id"], "says": "closed"}], session=SESSION, at=ANSWERED_AT)
    dl.settle(led, at=SETTLED)
    maker = [d for d in led.items if isinstance(d, dict) and d.get("capacity") == "transconceiver"]
    assert len(maker) == 1 and maker[0]["summary"] == "The maintainer, who wrote most of it"
    assert led.item("R:licence/mit")["lane"] == "closed"
    r = dl.raise_questions(led, at="2026-11-18T11:00:00Z")
    st = {q["raised"]["from"].split("/")[1] for q in r.questions
          if q["raised"]["from"].startswith("transconception-standing/")}
    # the closed lane asks for the holder's leave; the new transconceiver's statements are asked; who rules is not
    assert st == {"leave", "licence", "lane-said", "confidential", "programs", "attribution"}


# ---------------------------------------------------------------------------
# the moves: `in <language>`, and the checks read batch and scope
# ---------------------------------------------------------------------------

def test_the_moves_pass_a_target_only_when_one_is_named_and_their_checks_hold(tmp_path):
    from enough.thym.checks import verdict
    from enough.thym.moves import dialectic as D
    from enough.thym.values import Value, read_value

    calls = []

    def thym_question(volume, **kw):
        calls.append(sorted(kw))
        return dl.thym_question(volume, **kw)

    class Ctx:
        run, now = "2026-11-18-1000-test", dt.datetime(2026, 11, 18, 10, tzinfo=dt.timezone.utc)
        engines = {"dialectic": type("E", (), {"thym_question": staticmethod(thym_question)})()}

    t = twin()
    _with_rust(t.ledger)
    p = tmp_path / "vulture.fabulac.cosm"
    p.write_text(t.render(), encoding="utf-8")
    f = read_value(p, "fabula")
    plain = D.bank(Ctx(), f)
    assert calls[-1] == ["at", "run"]                                # as it always was: replays as recorded
    rust = D.bank(Ctx(), f, **{"in": Value("word", "rust")})
    assert calls[-1] == ["at", "run", "target"]
    qs = [m.payload for m in rust.payload]
    assert ruling_qs(qs) and all(q["proposed"]["made-for"] == "N:target/rust" for q in ruling_qs(qs))
    assert len(ruling_qs([m.payload for m in plain.payload])) == 0
    inputs = {"found": f}
    for check in ("addressed", "no-duplicate"):
        assert verdict(check, rust, inputs, {}, None, None) == (True, ""), check
    # a batch that names nothing is caught
    broken = copy.deepcopy(qs)
    next(q for q in broken if q.get("batch"))["batch"].append("C:interface/nothing#ruling")
    bad = Value("list", [Value("item", q) for q in broken])
    ok, why = verdict("addressed", bad, inputs, {}, None, None)
    assert not ok and "batch" in why
