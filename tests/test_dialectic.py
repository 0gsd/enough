"""The dialectic's deterministic core (enough/dialectic.py; MacroCOSM OES 18.6, Thym 22, docs/fabula-pins.md P4).

Every row of the text's tables is a test: each state move (18.6.3), each answer kind good and bad, each of the four
things an answer can be (a value, "I don't know", a refusal, a skip) and what settling it writes (18.6.4). Banks of
both shapes (the fabula's three flavours, Ascribe's 44), no-duplicate, the counter question, only-the-asked, the
answers volume (Thym 22.2), carry_over and staleness, the three appendix examples answered from fixture answers
volumes (tests/fixtures/dialectic/) and settled, an old-spelled `emf/1` twin, a volume with nothing to ask, and that a
volume written back is byte-identical outside what the operation changed. Everything reads tests/fixtures/ or writes
under tmp_path.
"""

from __future__ import annotations

import copy
import datetime as dt
import io
import re
import shutil
from pathlib import Path

import pytest

from enough import dialectic as dl
from enough import fabula as fb
from enough import macrocosm as mc

REPO = Path(__file__).resolve().parent.parent
FAB = REPO / "tests" / "fixtures" / "fabula"
ANS = REPO / "tests" / "fixtures" / "dialectic"
CLOSE = FAB / "guides" / "close.md.fabulan.cosm"
ROSE = FAB / "poems" / "the-sick-rose.txt.fabulap.cosm"
TALLY = FAB / "tally.fabulac.cosm"
EMF = REPO / "tests" / "fixtures" / "cosm" / "emf" / "notes.md.cosm"
RUST = REPO / "tests" / "fixtures" / "cosm" / "canon" / "rust-book" / "canon.cosm"
SELF = REPO / "tests" / "fixtures" / "ascribe" / "sample-self"
AT = "2026-11-05T12:00:00Z"
RUN = "2026-11-05-1300-d1d1"

MINI = """\
oes: fabula/1
macrocosm: 0.5.4
flavour: fabulan
id: fabula/mini-md
name: Mini
# a comment above derived, kept
derived: {at: 2026-11-05T10:00:00Z, by: person, mode: rules, completeness: full, chunks: 1}
nodes:
  # --- N ---
  - id: N:audience/owners
    type: audience
    name: Owners
    summary: The owners read it.
    stance: observed
    who: {pending: "who reads it, besides the owners?"}
    span: {lines: "1"}
    provenance: {mode: derived, sources: ['mini.md#L1'], confidence: 0.9, state: known}
  - id: N:exclusion/old
    type: exclusion
    name: The old file is not read
    summary: The old file is not read.
    stance: observed
    horizon: {pending: "ever again?"}
    because: 'it holds other things'   # quoted on purpose
    provenance: {mode: derived, sources: ['mini.md#L2'], confidence: 0.9, state: known}
  - id: P:claim/one
    type: claim
    name: One claim
    summary: The day is locked.
    stance: observed
    span: {lines: "3"}
    provenance: {mode: derived, sources: ['mini.md#L3'], confidence: 0.3, state: known}
  - id: P:reading/r
    type: reading
    name: A reading
    summary: The lock is a promise.
    stance: opinion
    of: [P:claim/one]
    whose: {by: model}
    grounds:
      - {of: P:claim/one, because: it says locked}
    provenance: {mode: derived, sources: ['mini.md#L3'], confidence: 0.5, state: known}
"""


def mini(text: str = MINI) -> dl.Twin:
    return dl.twin_from_text(text, filename="mini.md.fabulan.cosm")


def question(about, kind="text", qid="q1", **more) -> dict:
    d = {"id": f"D:question/{qid}", "type": "question", "about": about, "asks": "What is it?", "why": "missing",
         "kind": kind, "to": "author", "raised": {"by": "person", "from": "hand", "at": dt.datetime(
             2026, 11, 5, 11, 0, tzinfo=dt.timezone.utc)}, "state": "open"}
    d.update(more)
    return d


def with_question(t: dl.Twin, *qs: dict) -> dl.Twin:
    dl.land(t, qs)
    return dl.twin_from_text(t.render(), filename="mini.md.fabulan.cosm")


def errors(t: dl.Twin) -> list[str]:
    return [str(p) for p in t.lint().errors]


def node_chunks(text: str) -> dict[str, str]:
    """{id: the item's text} for a single-file volume's nodes (each from its `  - id:` line to the next)."""
    out, cur, buf = {}, None, []
    for line in text.splitlines(keepends=True):
        mt = re.match(r"^  - id: (\S+)", line)
        if mt or (cur and re.match(r"^\S", line)):
            if cur:
                out[cur] = "".join(buf)
            cur, buf = (mt.group(1), [line]) if mt else (None, [])
            continue
        if cur:
            buf.append(line)
    if cur:
        out[cur] = "".join(buf)
    return out


def head(text: str) -> str:
    return text.split("\nnodes:\n", 1)[0]


# ---------------------------------------------------------------------------
# A. Reading
# ---------------------------------------------------------------------------

def test_reading_the_close_example():
    t = dl.open_twin(CLOSE)
    assert [q["id"] for q in dl.questions(t)] == ["D:question/audience", "D:question/occasion"]
    assert [q["id"] for q in dl.questions(t, state="open")] == ["D:question/occasion"]
    assert [s["id"] for s in dl.sessions(t)] == ["D:session/session-1"]
    oq = dl.open_questions(t)
    assert [(e["form"], e["about"]) for e in oq] == [
        ("question", "I:occasion/why-written#roles.event"),
        ("pending", "L:term/morning-summary#feed"),
        ("pending", "R:release/handbook#at"),
    ]
    # the pending the open question is about is not listed twice (18.6.5: one open question, two lengths)
    assert "I:occasion/why-written#roles.event" not in [e["about"] for e in oq if e["form"] == "pending"]


@pytest.mark.parametrize("about,form,ok", [
    ("N:audience/owners", "item", True),
    ("N:audience/owners#who", "field", True),               # pending
    ("N:audience/owners#size", "field", True),              # absent: still resolves (9.3)
    ("N:audience/owners#bad..path", "field", False),
    ("N:audience/nobody", "item", False),
    ({"lines": "2-3"}, "span", True),
    ({"start": "The day", "end": "is locked."}, "span", True),
    ({"file": "a.py", "lines": "1-4"}, "span", True),
    ({"lines": "4-2"}, "span", False),
    ({"start": "x" * 61, "end": "y"}, "span", False),
    ("N", "module", True),
    ("N:audience", "kind", True),
    ("N:nothing", "kind", False),
])
def test_resolve_about_every_form(about, form, ok):
    w = dl.resolve_about(mini(), about)
    assert w.form == form and w.resolves is ok


def test_resolve_about_says_present_and_pending():
    t = mini()
    w = dl.resolve_about(t, "N:audience/owners#who")
    assert w.present and w.pending and w.address == "N:audience/owners#who"
    w = dl.resolve_about(t, "N:audience/owners#size")
    assert not w.present and not w.pending


def test_reading_from_items_handed_in():
    """A MiniCOSM lane hands its items in: the same functions read them without knowing its layout."""
    m = mc.default_registry().get("ascribe")
    items = [{"id": "A:affinity/bread", "type": "affinity", "name": "Bread", "summary": "Bakes bread.",
              "when": {"pending": "since when?"}, "provenance": {"mode": "manual", "sources": ["self"],
                                                                 "confidence": 1}},
             question("A:affinity/bread#when", kind="date", qid="when")]
    led = dl.ledger_from_items(m, items, catalog={"oes": "ascribe/1", "id": "ascribe/x"})
    assert [e["id"] for e in dl.open_questions(led)] == ["D:question/when"]
    assert dl.resolve_about(led, "A:affinity/bread#when").pending


def test_a_volume_with_nothing_to_ask():
    """No D items, no pendings, no bank (a Canon volume): nothing is open, nothing is raised, settling writes nothing,
    and the text comes back byte for byte."""
    t = dl.open_twin(RUST)
    assert dl.questions(t) == [] and dl.open_questions(t) == []
    r = dl.raise_questions(t, at=AT)
    assert r.questions == [] and r.refused == []
    res = dl.settle(t, run=RUN, program="settle.thym", at=AT)
    assert res.settled == [] and res.run is None              # not a fabula: no derived.runs
    assert not t.changed and t.render() == RUST.read_text(encoding="utf-8") and t.how == "unchanged"


# ---------------------------------------------------------------------------
# B. Raising
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path,flavour,n", [(CLOSE, "fabulan", 17), (ROSE, "fabulap", 25), (TALLY, "fabulac", 17)])
def test_the_bank_is_chosen_by_flavour(path, flavour, n):
    banks = dl.banks_for(dl.open_twin(path))
    assert [b["name"] for b in banks] == [flavour] and len(banks[0]["questions"]) == n


def test_an_emf_twin_reads_the_fabulan_bank():
    assert [b["name"] for b in dl.banks_for(dl.open_twin(EMF))] == ["fabulan"]


def test_bank_entries_by_module_kind_and_field():
    t = mini()
    r = dl.raise_questions(t, at=AT, run="r1", pending=False, unsure=False)
    by_from = {}
    for q in r.questions:
        by_from.setdefault(q["raised"]["from"], []).append(q)
    # a module entry: once, about the module letter
    assert [q["about"] for q in by_from["fabulan/aim"]] == ["N"]
    assert by_from["fabulan/aim"][0]["id"] == "D:question/aim"
    # a kind entry: each item of the kind, {name} filled from it
    stand = by_from["fabulan/stand-by"]
    assert [q["about"] for q in stand] == ["P:claim/one"]
    assert stand[0]["asks"] == "Would you still stand behind this: One claim?"
    assert stand[0]["id"] == "D:question/stand-by-one"
    # a field entry: each item where the field is absent or pending (no L:term here: nothing)
    assert "fabulan/sense" not in by_from
    q = stand[0]
    assert q["raised"] == {"by": "bank", "from": "fabulan/stand-by", "at": dl.now(AT), "run": "r1"}
    assert q["to"] == "author" and q["state"] == "open" and q["kind"] == "yes-no" and q["why"] == "unsure"
    assert list(q) == ["id", "type", "about", "asks", "why", "kind", "to", "raised", "state"]


def test_a_field_entry_skips_items_that_hold_the_value():
    t = dl.open_twin(ROSE)
    r = dl.raise_questions(t, at=AT, banks=["fabulap"], pending=False, unsure=False)
    words = [q["about"] for q in r.questions if q["raised"]["from"] == "fabulap/word"]
    terms = [d for d in t.ledger.items if d["id"].startswith("L:term/")]
    want = [f"{d['id']}#sense" for d in terms if "sense" not in d or mc.is_pending(d["sense"])]
    want = [w for w in want if w != "L:term/bed#sense"]       # D:question/bed already asks it (fabulap/word)
    assert words == want


def test_a_placeholder_the_item_cannot_fill_is_skipped():
    t = dl.open_twin(ROSE)
    r = dl.raise_questions(t, at=AT, pending=False, unsure=False)
    stresses = [s for s in r.skipped if s[0].startswith("fabulap/stresses")]
    lines = [d for d in t.ledger.items if d["id"].startswith("C:line/") and "number" not in d]
    assert len(stresses) == len([d for d in lines if "stresses" not in d or mc.is_pending(d.get("stresses"))])


def test_who_answers_author_expert_and_override():
    t = mini()
    assert {q["to"] for q in dl.raise_questions(t, at=AT).questions} == {"author"}
    assert {q["to"] for q in dl.raise_questions(t, at=AT, author_unavailable=True).questions} == {"expert"}
    assert {q["to"] for q in dl.raise_questions(t, at=AT, to="anyone").questions} == {"anyone"}
    assert {q["to"] for q in dl.raise_questions(dl.open_twin(TALLY), at=AT, banks=["fabulac"]).questions} == {"maker"}


def test_pending_values_raise_questions_that_ask_their_text():
    r = dl.raise_questions(mini(), at=AT, banks=[], unsure=False)
    got = {q["about"]: q for q in r.questions}
    q = got["N:audience/owners#who"]
    assert q["asks"] == "Who reads it, besides the owners?" and q["why"] == "missing" and q["kind"] == "text"
    assert q["raised"]["by"] == "move" and q["raised"]["from"] == "question"
    assert q["id"] == "D:question/owners-who"
    assert "N:exclusion/old#horizon" in got


def test_a_whole_item_pending_is_asked_about_the_item():
    text = MINI.replace("    stance: opinion\n", "    stance: opinion\n    pending: is this reading anyone's?\n")
    r = dl.raise_questions(mini(text), at=AT, banks=[], unsure=False)
    assert "P:reading/r" in [q["about"] for q in r.questions]


def test_unsure_items_raise_a_question_and_pending_ones_do_not_twice():
    r = dl.raise_questions(mini(), at=AT, banks=[], pending=False)
    assert [(q["about"], q["why"]) for q in r.questions] == [("P:claim/one", "unsure")]
    # appendix B: the occasion is pending and at 0.3, but its pending is already asked: no unsure question
    r = dl.raise_questions(dl.open_twin(CLOSE), at=AT, banks=[])
    assert "I:occasion/why-written" not in [q["about"] for q in r.questions]


def test_ascribes_44_questions_as_the_reader_gives_them():
    led = dl.ledger_from_volume(mc.load_volume(SELF))
    r = dl.raise_questions(led, at=AT, pending=False, unsure=False)
    assert len(r.questions) == 44
    q = r.questions[0]
    assert q["id"] == "D:question/ascribe-a1" and q["about"] == "A" and q["to"] == "holder"
    assert q["raised"]["from"] == "ascribe/A1" and q["asks"] == "What do you go back to, again and again?"
    assert {x["about"] for x in r.questions} == set("ABCEIOQSUYF")


def _from(r, frm: str) -> list[dict]:
    return [q for q in r.questions if q["raised"]["from"] == frm]


def test_words_that_name_no_item_are_asked_once_about_the_module():
    """The conductor's ruling on the question stage: a bank question whose words name no item is asked once of the
    volume, about the module, when the volume holds an item it would be asked of; one that names `{name}` (or any
    `{<field>}`) is still asked of each item."""
    t = dl.open_twin(TALLY)
    r = dl.raise_questions(t, at=AT, pending=False, unsure=False)
    worry = _from(r, "fabulac/worry")
    assert [(q["about"], q["id"], q["kind"]) for q in worry] == [("P", "D:question/worry", "ref")]
    rose = dl.raise_questions(dl.open_twin(ROSE), at=AT, pending=False, unsure=False)
    assert [q["about"] for q in _from(rose, "fabulap/breaks")] == ["C"]          # was one per line
    assert len(_from(rose, "fabulap/stands-for")) == 2                           # names {name}: per device
    # a volume with no item of the kind is not asked; one asked already is not asked again
    no_cases = t.render().replace("P:case/", "P:claim/").replace("type: case", "type: claim")
    assert not _from(dl.raise_questions(dl.twin_from_text(no_cases, filename=t.ledger.filename), at=AT),
                     "fabulac/worry")
    dl.land(t, worry)
    assert not _from(dl.raise_questions(t, at=AT), "fabulac/worry")


def test_a_bank_entry_bounds_itself():
    """`only-with: <field>` (the unexpected-input question only of an interface that takes arguments), `at-most: <n>`
    (why a change was made, of the five newest changes with no `because`), and a field asked only where it is absent
    or pending (the licence only when its identifier is)."""
    t = dl.open_twin(TALLY)
    r = dl.raise_questions(t, at=AT, pending=False, unsure=False)
    interfaces = [d for d in t.ledger.items if d["id"].startswith("C:interface/")]
    taking = [d["id"] for d in interfaces if d.get("takes")]
    assert len(taking) > 5 and len(taking) < len(interfaces)
    assert [q["about"] for q in _from(r, "fabulac/bad-input")] == taking[-5:]     # only-with, then at most five
    for entry in ("why-this", "tried", "intended", "public", "bad-input", "settings", "changed"):
        assert len(_from(r, f"fabulac/{entry}")) <= 5, entry                      # no per-item entry floods a volume
    assert not _from(r, "fabulac/licence")                                       # its identifier was read
    lic = next(d for d in t.ledger.items if d["id"].startswith("R:licence/"))
    text = t.render().replace(f"identifier: {lic['identifier']}",
                              "identifier: {pending: 'which licence is it under'}", 1)
    assert text != t.render()
    pend = dl.raise_questions(dl.twin_from_text(text, filename=t.ledger.filename), at=AT, pending=False,
                              unsure=False)
    assert [q["about"] for q in _from(pend, "fabulac/licence")] == [f"{lic['id']}#identifier"]
    changes = [{"id": f"R:change/c{k}", "type": "change", "name": f"Change {k}", "summary": f"Change {k}.",
                "stance": "observed", "at": f"2026-01-{k:02d}"} for k in (3, 1, 7, 5, 2, 6, 4)]
    kept = [d for d in t.ledger.items if not d["id"].startswith("R:change/")]
    led = dl.ledger_from_items(t.ledger.manifest, kept + changes, catalog=t.ledger.catalog)
    got = [q["about"] for q in _from(dl.raise_questions(led, at=AT, pending=False, unsure=False),
                                     "fabulac/changed")]
    assert got == ["R:change/c3#because", "R:change/c7#because", "R:change/c5#because", "R:change/c6#because",
                   "R:change/c4#because"]                                        # the newest five, in volume order
    assert dl._newest([{"id": "a"}, {"id": "b"}, {"id": "c"}], 2) == [{"id": "b"}, {"id": "c"}]
    assert dl._entry_bound({"at-most": 0}) == "a bank entry's at-most is a whole number above 0"
    assert dl._entry_bound({"only-with": ""}) == "a bank entry's only-with names a field"
    assert dl._entry_bound({"only-with": "takes", "at-most": 5}) == ("takes", 5)


def test_no_duplicate():
    t = mini()
    r1 = dl.raise_questions(t, at=AT)
    dl.land(t, r1.questions)
    r2 = dl.raise_questions(t, at=AT)
    assert r2.questions == []                                  # one open question per (raised.from, about)
    with pytest.raises(dl.DialecticError):
        dl.land(t, r1.questions[:1])                           # all or none: an id already held
    # a declined bank question is a fact: not raised again; a withdrawn one may be
    q = t.ledger.question("stand-by-one")
    dl.record(t, [{"question": q["id"], "declined": True}], at=AT)
    assert dl.raise_questions(t, at=AT).questions == []
    dl.withdraw(t, q["id"], because="asked by mistake", at=AT)
    again = dl.raise_questions(t, at=AT).questions
    assert [x["about"] for x in again] == ["P:claim/one"] and again[0]["id"] == "D:question/stand-by-one-2"


def test_proposed_questions_are_validated_and_merged():
    t = mini()
    proposals = [
        {"about": "P:claim/one#salience", "asks": "How much does this claim matter?", "why": "intent",
         "kind": "choice", "options": ["critical", "major", "minor"], "from": "fold"},
        {"about": "P:claim/nothing", "asks": "Is this so?", "why": "unsure", "kind": "yes-no"},       # nothing there
        {"about": "P:claim/one", "asks": "Is it?", "why": "sometimes", "kind": "yes-no"},             # not a why
        {"about": "P:claim/one", "asks": "Hm?", "why": "unsure", "kind": "choice"},                   # no options
        {"asks": "About what?", "why": "unsure", "kind": "text"},
    ]
    r = dl.raise_questions(t, at=AT, banks=[], pending=False, unsure=False, proposed=proposals)
    assert [q["about"] for q in r.questions] == ["P:claim/one#salience"]
    q = r.questions[0]
    assert q["raised"]["by"] == "model" and q["raised"]["from"] == "fold" and q["options"] == ["critical", "major",
                                                                                                "minor"]
    assert len(r.refused) == 4
    dl.land(t, r.questions)
    # the same proposal again duplicates a standing question
    again = dl.raise_questions(t, at=AT, banks=[], pending=False, unsure=False, proposed=proposals[:1])
    assert again.questions == [] and "already asks" in again.refused[0][1]
    # a callable hook sees the rule questions
    seen = []
    dl.raise_questions(t, at=AT, banks=[], proposed=lambda led, qs: seen.append(len(qs)) or [])
    assert seen == [3]          # two pendings and one unsure item


def test_raised_questions_load_clean():
    for p in (CLOSE, ROSE, TALLY, EMF):
        t = dl.open_twin(p)
        dl.ask_by_bank(t, at=AT, run="r1")
        t2 = dl.twin_from_text(t.render(), filename=t.ledger.filename)
        assert errors(t2) == []
        assert dl.only_the_asked(dl.open_twin(p), t2) == []


# ---------------------------------------------------------------------------
# C. Recording
# ---------------------------------------------------------------------------

def _rec_twin() -> dl.Twin:
    t = mini()
    return with_question(t, question("N:exclusion/old#horizon", kind="choice", qid="h", options=["never", "later"]),
                         question("N:audience/owners#who", qid="w"), question("P:claim/one", kind="text", qid="c"),
                         question("N:audience/owners#size", kind="number", qid="n", range=[1, 10]))


def test_record_a_value_moves_open_to_answered():
    t = _rec_twin()
    rec = dl.record(t, [dl.Answer("h", says="Never, I think.", value="never", confidence=0.8)],
                    session={"with": {"to": "author", "who": "the guide's writer"}}, at=AT)
    q = t.ledger.question("h")
    assert q["state"] == "answered"
    assert q["answers"] == [{"at": dl.now(AT), "by": "author", "says": "Never, I think.", "value": "never",
                             "confidence": 0.8, "session": "D:session/session-1"}]
    s = t.ledger.session("session-1")
    assert s["asked"] == s["answered"] == ["D:question/h"] and s["skipped"] == [] and s["through"] == "person"
    assert rec.recorded[0][1] == "answered"
    # the item it is about is not touched yet
    assert mc.is_pending(t.ledger.item("N:exclusion/old")["horizon"])
    assert errors(dl.twin_from_text(t.render())) == []


@pytest.mark.parametrize("answer", [dict(says="I don't know"), dict(says="no idea, ask the owners"),
                                    dict(says="nobody has said", dont_know=True)])
def test_record_i_dont_know_moves_open_to_unknown(answer):
    t = _rec_twin()
    dl.record(t, [dict(question="w", **answer)], at=AT)
    q = t.ledger.question("w")
    assert q["state"] == "unknown"
    assert q["answers"][-1]["value"] is None and q["answers"][-1]["says"] == answer["says"]
    assert "declined" not in q["answers"][-1]


@pytest.mark.parametrize("answer", [dict(says="I'd rather not say"), dict(says="no comment"),
                                    dict(says="", declined=True)])
def test_record_a_refusal_moves_open_to_declined(answer):
    t = _rec_twin()
    dl.record(t, [dict(question="w", **answer)], at=AT)
    q = t.ledger.question("w")
    assert q["state"] == "declined" and q["answers"][-1]["declined"] is True and q["answers"][-1]["value"] is None


def test_record_a_skip_leaves_it_open_and_lists_it():
    t = _rec_twin()
    rec = dl.record(t, [{"question": "w", "skip": True}, {"question": "h", "says": "later"}], at=AT)
    assert t.ledger.question("w")["state"] == "open" and "answers" not in t.ledger.question("w")
    s = t.ledger.session(rec.session)
    assert s["asked"] == ["D:question/w", "D:question/h"] and s["skipped"] == ["D:question/w"]
    assert s["answered"] == ["D:question/h"]


def test_record_refuses_and_leaves_the_question_open():
    t = _rec_twin()
    rec = dl.record(t, [{"question": "h", "says": "sometimes"}, {"question": "nope", "says": "x"},
                        {"question": "n", "value": 11}], at=AT)
    assert [r[0] for r in rec.refused] == ["D:question/h", "nope", "D:question/n"]
    assert "not one of: never, later" in rec.refused[0][1] and "not from 1 to 10" in rec.refused[2][1]
    assert t.ledger.question("h")["state"] == "open" and "answers" not in t.ledger.question("h")
    # a question that is not open: ask it again first
    dl.record(t, [{"question": "h", "says": "never"}], at=AT)
    rec = dl.record(t, [{"question": "h", "says": "later"}], at=AT)
    assert "not open" in rec.refused[0][1]
    with pytest.raises(dl.DialecticError):
        dl.record(t, [{"question": "w", "says": "x"}, {"question": "h", "says": "later"}], at=AT, strict=True)
    assert t.ledger.question("w")["state"] == "open"            # strict: nothing recorded


def test_reask_keeps_the_answers_and_appends():
    t = _rec_twin()
    dl.record(t, [{"question": "h", "says": "later"}], at=AT)
    dl.settle(t, at=AT)
    first = t.ledger.question("h")["settled"]
    assert first
    dl.reask(t, "h")
    q = t.ledger.question("h")
    # The conductor's ruling 2: the earlier `settled` stays as the record of the earlier write (18.6.3), and an open
    # question that holds an answer may carry it.
    assert q["state"] == "open" and len(q["answers"]) == 1 and q["settled"] == first
    assert errors(dl.twin_from_text(t.render())) == []
    dl.record(t, [{"question": "h", "says": "never", "by": "expert"}], session={"with": {"to": "expert",
                                                                                         "who": "an expert"}},
              at="2026-11-05T13:00:00Z")
    assert [a["value"] for a in q["answers"]] == ["later", "never"] and q["state"] == "answered"
    assert [a["session"] for a in q["answers"]] == ["D:session/session-1", "D:session/session-2"]
    assert errors(dl.twin_from_text(t.render())) == []
    # The answer given since the earlier settling is settled anew; settling again changes nothing more.
    res = dl.settle(t, at="2026-11-05T14:00:00Z")
    assert [x[0] for x in res.settled] == ["D:question/h"]
    q = t.ledger.question("h")                      # looked up afresh: a fold replaces the items it wrote
    assert q["settled"]["at"] == dl.now("2026-11-05T14:00:00Z") and q["settled"]["wrote"] == first["wrote"]
    assert dl.settle(t, at="2026-11-05T15:00:00Z").settled == []


def test_reask_can_still_drop_settled():
    t = _rec_twin()
    dl.record(t, [{"question": "h", "says": "later"}], at=AT)
    dl.settle(t, at=AT)
    assert "settled" not in dl.reask(t, "h", keep_settled=False)


def test_record_continues_an_existing_session():
    t = _rec_twin()
    rec = dl.record(t, [{"question": "h", "says": "later"}], at=AT)
    dl.record(t, [{"question": "w", "skip": True}], session={"id": rec.session}, at=AT)
    assert len(t.ledger.sessions()) == 1
    assert t.ledger.session(rec.session)["asked"] == ["D:question/h", "D:question/w"]


def test_record_by_address_lists_the_address_and_writes_nothing_else():
    """A format that asks a field directly (Comprise OES 8): the session lists `<item>#<field>`."""
    t = mini()
    before = copy.deepcopy(t.doc)
    rec = dl.record(t, [{"question": "N:exclusion/old#horizon", "says": "never",
                         "spec": {"kind": "choice", "options": ["never", "later"]}}],
                    session={"id": "elicit-2026-11-05-a3f9", "with": {"to": "owner", "who": "the owner"}}, at=AT)
    assert rec.recorded[0][0] == "N:exclusion/old#horizon" and rec.recorded[0][2]["value"] == "never"
    s = t.ledger.session("elicit-2026-11-05-a3f9")
    assert s["asked"] == ["N:exclusion/old#horizon"] and s["answered"] == ["N:exclusion/old#horizon"]
    assert [d for d in t.ledger.items if not dl.is_d_item(d)] == before["nodes"]
    f = dl.fold(t, "N:exclusion/old#horizon", rec.recorded[0][2], spec={"kind": "choice"})
    assert f.ok and f.wrote == ["N:exclusion/old#horizon"]
    out = dl.twin_from_text(t.render())
    assert errors(out) == [] and out.ledger.item("N:exclusion/old")["horizon"] == "never"
    assert out.ledger.item("N:exclusion/old")["provenance"]["sources"][-1] == "D:session/elicit-2026-11-05-a3f9"


# ----------------------------------------------------------------- each answer kind, good and bad

GOOD = [
    ({"kind": "text"}, "  For owners.  ", "For owners."),
    ({"kind": "text", "many": True}, "owners; support staff", ["owners", "support staff"]),
    ({"kind": "choice", "options": ["never", "later"]}, "Never", "never"),
    ({"kind": "choice", "options": ["never", "later"], "options-open": True}, "sometime", "sometime"),
    ({"kind": "choice", "options": ["a", "b", "c"], "many": True}, ["a", "C"], ["a", "c"]),
    ({"kind": "yes-no"}, "Yes, on purpose.", True),
    ({"kind": "yes-no"}, "no", False),
    ({"kind": "yes-no"}, False, False),
    ({"kind": "number"}, "3", 3),
    ({"kind": "number", "range": [1, 5]}, 4.5, 4.5),
    ({"kind": "date"}, "2014-06-03", dt.date(2014, 6, 3)),
    ({"kind": "date"}, "2014-06", "2014-06"),
    ({"kind": "date"}, 2014, "2014"),
    ({"kind": "ref"}, "P:claim/one", "P:claim/one"),
    ({"kind": "ref", "options": ["P:"], "many": True}, ["P:claim/one", "P:reading/r"], ["P:claim/one", "P:reading/r"]),
    ({"kind": "span"}, "12-18", {"lines": "12-18"}),
    ({"kind": "span"}, {"start": "The day", "end": "locked."}, {"start": "The day", "end": "locked."}),
    ({"kind": "span"}, {"file": "tally/cli.py", "lines": "40-47"}, {"file": "tally/cli.py", "lines": "40-47"}),
]
BAD = [
    ({"kind": "text"}, "   ", "empty"),
    ({"kind": "text"}, {"a": 1}, "words"),
    ({"kind": "choice", "options": ["never", "later"]}, "sometime", "not one of"),
    ({"kind": "choice", "options": ["never", "later"], "options-open": True}, "two words", "not one of"),
    ({"kind": "yes-no"}, "perhaps", "not yes or no"),
    ({"kind": "number"}, "three", "not a number"),
    ({"kind": "number"}, True, "not yes or no"),
    ({"kind": "number", "range": [1, 5]}, 6, "not from 1 to 5"),
    ({"kind": "date"}, "2014-13", "not a date"),
    ({"kind": "date"}, "June 2014", "not a date"),
    ({"kind": "date"}, "2014-02-30", "not a date"),
    ({"kind": "ref"}, "P:claim/none", "names nothing"),
    ({"kind": "ref", "options": ["N:"]}, "P:claim/one", "does not start with"),
    ({"kind": "span"}, "line twelve", "not a span"),
    ({"kind": "span"}, {"lines": "9-2"}, "n or n-m"),
    ({"kind": "span"}, {"start": "x" * 61, "end": "y"}, "60 characters"),
    ({"kind": "colour"}, "red", "not an answer kind"),
]


@pytest.mark.parametrize("spec,value,want", GOOD)
def test_each_answer_kind_good(spec, value, want):
    got = dl.check_value(mini(), spec, value)
    assert dl._same(got, want)


@pytest.mark.parametrize("spec,value,words", BAD)
def test_each_answer_kind_bad(spec, value, words):
    with pytest.raises(dl.AnswerRefused) as e:
        dl.check_value(mini(), spec, value)
    assert words in str(e.value)


# ---------------------------------------------------------------------------
# The answers volume (Thym 22.2)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", sorted(p.name for p in ANS.glob("*.answers-*.cosm")))
def test_the_fixture_answers_volumes_round_trip(name):
    av = dl.read_answers_volume(ANS / name)
    again = dl.read_answers_volume(dl.write_answers_volume(av))
    assert dl._same(av.to_doc(), again.to_doc())
    assert av.oes == "fabula/1" and av.session["id"].startswith("D:session/")


def test_an_answers_volume_is_written_beside_and_leaves_the_volume_alone(tmp_path):
    shutil.copy(CLOSE, tmp_path / CLOSE.name)
    t = dl.open_twin(tmp_path / CLOSE.name)
    av = dl.answers_delta(t, [{"question": "occasion", "says": "A support call."}],
                          session={"with": {"to": "author", "who": "the head of support"}}, at=AT)
    assert not t.changed
    assert [e["id"] for e in av.entries] == ["D:question/occasion"] and av.entries[0]["state"] == "answered"
    assert set(av.entries[0]) == {"id", "state", "answers"}
    assert av.volume_id == "fabula/guides--close-md" and av.session["id"] == "D:session/session-2"
    p = dl.answers_path(tmp_path / CLOSE.name, at=AT)
    assert p.name == "close.md.fabulan.answers-2026-11-05-1200.cosm" and dl.is_answers_of(tmp_path / CLOSE.name, p)
    p.write_text(dl.write_answers_volume(av), encoding="utf-8")
    assert dl.answers_path(tmp_path / CLOSE.name, at=AT).name.endswith("1200-2.cosm")
    rec = dl.record_answers_volume(t, p)
    assert rec.recorded[0][:2] == ("D:question/occasion", "answered")
    with pytest.raises(dl.DialecticError, match="recorded"):
        dl.record_answers_volume(t, p)                            # a replay of the same record: refused


@pytest.mark.parametrize("edit,words", [
    (lambda s: s.replace("id: fabula/guides--close-md", "id: fabula/other"), "answers fabula/other"),
    (lambda s: s.replace("oes: fabula/1", "oes: canon/1"), "answers a canon/1"),
    (lambda s: s.replace("state: answered", "state: settled"), "not answered, unknown or declined"),
    (lambda s: s.replace("state: answered", "state: declined"), "disagrees"),
    (lambda s: s.replace("session: D:session/session-2}", "session: D:session/session-9}"), "names session"),
    (lambda s: s.replace("  - id: D:session/session-2\n", "  - id: D:session/session-3\n    type: session\n"
                                                          "  - id: D:session/session-2\n"), "exactly one"),
    (lambda s: s.replace("D:question/occasion\n    state", "D:question/nothing\n    state"), "not a question"),
    (lambda s: s.replace("value: \"an owner's call to support about a late morning summary\"", "value: {a: 1}"),
     "words"),
])
def test_a_bad_answers_volume_is_refused(edit, words):
    text = edit((ANS / "close.md.fabulan.answers-2026-11-05-1200.cosm").read_text(encoding="utf-8"))
    t = dl.open_twin(CLOSE)
    with pytest.raises(dl.DialecticError, match=re.escape(words)):
        dl.record_answers_volume(t, text)
    assert not t.changed


# ---------------------------------------------------------------------------
# D. Settling: 18.6.4's tables
# ---------------------------------------------------------------------------

def settled(t: dl.Twin, *answers, **kw) -> tuple[dl.Twin, dl.Settled]:
    dl.record(t, answers, session={"with": {"to": "author", "who": "the writer"}}, at=AT)
    res = dl.settle(t, at="2026-11-05T13:00:00Z", **kw)
    return dl.twin_from_text(t.render(), filename="mini.md.fabulan.cosm"), res


@pytest.mark.parametrize("about,kind,extra,value,field,want", [
    ("N:audience/owners#who", "text", {}, "owners and support", "who", "owners and support"),
    ("N:exclusion/old#horizon", "choice", {"options": ["never", "later"]}, "later", "horizon", "later"),
    ("N:audience/owners#print", "yes-no", {}, "no", "print", False),
    ("N:audience/owners#size", "number", {"range": [1, 100]}, "12", "size", 12),
    ("N:audience/owners#since", "date", {}, "2019-04", "since", "2019-04"),
    ("N:audience/owners#first", "date", {}, "2019-04-02", "first", dt.date(2019, 4, 2)),
    ("N:audience/owners#see", "ref", {"options": ["P:"]}, "P:claim/one", "see", "P:claim/one"),
    ("N:audience/owners#readers", "ref", {"many": True}, ["P:claim/one", "N:exclusion/old"], "readers",
     ["P:claim/one", "N:exclusion/old"]),
    ("P:claim/one#span", "span", {}, "3-4", "span", {"lines": "3-4"}),
])
def test_a_value_is_written_into_the_field(about, kind, extra, value, field, want):
    t = with_question(mini(), question(about, kind=kind, **extra))
    out, res = settled(t, {"question": "q1", "value": value, "says": str(value), "confidence": 0.9})
    item = out.ledger.item(about.split("#")[0])
    assert dl._same(item[field], want)
    prov = item["provenance"]
    assert prov["mode"] == "derived"                                   # the item keeps its mode
    assert prov["sources"][-1] == "D:session/session-1"
    assert prov["answered"][field] == {"sources": ["D:session/session-1"], "confidence": 0.9}
    q = out.ledger.question("q1")
    assert q["settled"] == {"at": dl.now("2026-11-05T13:00:00Z"), "wrote": [about]}
    assert errors(out) == [] and res.settled == [("D:question/q1", [about])]


def test_a_span_into_grounds_is_appended():
    t = with_question(mini(), question("P:reading/r#grounds", kind="span"))
    out, _ = settled(t, {"question": "q1", "says": "line 3", "value": "3"})
    g = out.ledger.item("P:reading/r")["grounds"]
    assert g == [{"of": "P:claim/one", "because": "it says locked"}, {"lines": "3"}]


@pytest.mark.parametrize("about,kind,new_kind", [("N", "text", "aim"), ("N:audience", "text", "audience"),
                                                  ("N:exclusion", "choice", "exclusion")])
def test_a_module_or_kind_answer_writes_a_new_item(about, kind, new_kind):
    extra = {"options": ["Old drafts are never kept", "x"]} if kind == "choice" else {}
    t = with_question(mini(), question(about, kind=kind, **extra))
    out, res = settled(t, {"question": "q1", "says": "Old drafts are never kept", "confidence": 0.6})
    new = [d for d in out.ledger.items if d["id"] not in {x["id"] for x in mini().ledger.items} and
           not dl.is_d_item(d)]
    assert len(new) == 1
    d = new[0]
    assert d["id"] == f"N:{new_kind}/old-drafts-are-never-kept" and d["type"] == new_kind
    assert d["name"] == "Old drafts are never kept" and d["summary"] == "Old drafts are never kept"
    assert d["stance"] == "hearsay"
    assert d["provenance"] == {"mode": "dialectic", "sources": ["D:session/session-1"], "confidence": 0.6}
    assert out.ledger.question("q1")["settled"]["wrote"] == [d["id"]] and errors(out) == []


def test_a_module_entry_named_after_a_kind_writes_that_kind():
    """The fabulan bank's `audience` entry is about N; its answer writes an N:audience (not the module's first kind)."""
    t = mini()
    q = question("N", qid="audience", raised={"by": "bank", "from": "fabulan/audience", "at": dl.now(AT)})
    t = with_question(t, q)
    out, _ = settled(t, {"question": "audience", "says": "Owners and their bookkeepers"})
    assert out.ledger.item("N:audience/owners-and-their-bookkeepers") is not None


@pytest.mark.parametrize("entry,writes,want", [
    ("audience", "exclusion", "N:exclusion/owners-and-their-bookkeepers"),        # the entry's writes wins
    ("audience", "D:question", None),                                              # a kind no module of N: refused
    ("refuse", "reading", "P:reading/owners-and-their-bookkeepers"),               # required of, whose: pending
    ("parts", "N:decision", "N:decision/owners-and-their-bookkeepers"),            # another module's kind
])
def test_a_bank_entry_about_a_module_says_which_kind_its_answer_writes(entry, writes, want, monkeypatch):
    """The conductor's ruling 3: a bank entry about a module may say `writes: <kind>` (or `<M>:<kind>`); absent, the
    kind named like the entry where the module has one, else the module's first kind."""
    about = {"parts": "C", "refuse": "P"}.get(entry, "N")
    e = {"id": entry, "about": about, "asks": "x?", "kind": "text", "why": "intent", "writes": writes, "to": "author"}
    real = mc.Manifest.banks

    def banks(self):
        out = [dict(b) for b in real(self)]
        for b in out:
            if b["name"] == "fabulan":
                b["questions"] = [q for q in b["questions"] if q["id"] != entry] + [e]
        return out
    monkeypatch.setattr(mc.Manifest, "banks", banks)
    q = question(about, qid=entry, raised={"by": "bank", "from": f"fabulan/{entry}", "at": dl.now(AT)})
    out, res = settled(with_question(mini(), q), {"question": entry, "says": "Owners and their bookkeepers"})
    if want is None:
        assert res.settled == [] and "declares no kind to write" in res.counters[0][2][0][3]
    else:
        assert out.ledger.item(want) is not None, [d["id"] for d in out.ledger.items]
        assert res.settled == [(f"D:question/{entry}", [want])] and errors(out) == []
        kind = want.split("/")[0].split(":")[1]
        for f in out.ledger.manifest.required_fields(want.split(":")[0], kind):
            assert f in out.ledger.item(want), f       # what the answer cannot fill stays an open question


def test_the_fabula_banks_say_what_each_module_entry_writes():
    """Every fabula bank entry about a module whose answer can make an item (text or choice) names a kind the format
    declares (ruling 3); an entry of another kind writes no item and names none."""
    led = mini().ledger
    m = led.manifest
    seen = 0
    for b in m.banks():
        for e in b["questions"]:
            if ":" in e["about"] or "#" in e["about"]:
                assert "writes" not in e, (b["name"], e["id"])
                continue
            if e.get("kind") not in ("text", "choice"):
                assert "writes" not in e, (b["name"], e["id"])
                continue
            mod, _, k = str(e["writes"]).partition(":")
            mod, k = (mod, k) if k else (e["about"], mod)
            assert k in m.kinds(mod), (b["name"], e["id"], e["writes"])
            seen += 1
    assert seen >= 30


@pytest.mark.parametrize("kind", ["yes-no", "number", "date", "ref", "span"])
def test_a_module_answer_of_another_kind_is_not_written(kind):
    t = with_question(mini(), question("N", kind=kind))
    value = {"yes-no": "yes", "number": 3, "date": "2014", "ref": "P:claim/one", "span": "3"}[kind]
    out, res = settled(t, {"question": "q1", "value": value, "says": str(value)})
    assert res.settled == [] and out.ledger.question("q1").get("settled") is None
    assert res.counters and "always about a field" in res.counters[0][2][0][3]


def test_i_dont_know_leaves_the_field_pending_in_their_words():
    t = with_question(mini(), question("N:audience/owners#who", qid="q1"), question("N#x", qid="q2"))
    t = with_question(mini(), question("N:audience/owners#who", qid="q1"), question("N", qid="q2"))
    out, res = settled(t, {"question": "q1", "says": "I don't know who else reads it"},
                       {"question": "q2", "says": "no idea"})
    assert out.ledger.item("N:audience/owners")["who"] == {"pending": "I don't know who else reads it"}
    assert "answered" not in out.ledger.item("N:audience/owners")["provenance"]
    assert out.ledger.question("q1")["state"] == "unknown"
    assert out.ledger.question("q1")["settled"]["wrote"] == ["N:audience/owners#who"]
    assert out.ledger.question("q2")["settled"]["wrote"] == []          # a bank question: nothing is written
    assert errors(out) == []


def test_i_dont_know_about_a_whole_item_writes_its_pending():
    t = with_question(mini(), question("P:claim/one"))
    out, _ = settled(t, {"question": "q1", "says": "I don't know whether it still holds"})
    assert out.ledger.item("P:claim/one")["pending"] == "I don't know whether it still holds"


def test_a_refusal_writes_withheld_and_not_disclosed_and_removes_the_pending():
    t = with_question(mini(), question("N:audience/owners#who"))
    out, _ = settled(t, {"question": "q1", "says": "I would rather not say", "declined": True})
    d = out.ledger.item("N:audience/owners")
    assert d["withheld"] == ["who"] and d["provenance"]["state"] == "not-disclosed" and "who" not in d
    assert out.ledger.question("q1")["state"] == "declined" and errors(out) == []


def test_a_skip_writes_nothing():
    t = with_question(mini(), question("N:audience/owners#who"))
    before = t.render()
    out, res = settled(t, {"question": "q1", "skip": True})
    assert res.settled == [] and out.ledger.question("q1")["state"] == "open"
    assert node_chunks(out.render())["N:audience/owners"] == node_chunks(before)["N:audience/owners"]


def test_an_answer_about_a_whole_item_or_a_span_waits_for_a_reading():
    t = with_question(mini(), question("P:claim/one", qid="q1"), question({"lines": "3"}, qid="q2"))
    out, res = settled(t, {"question": "q1", "says": "It was never true."}, {"question": "q2", "says": "Meant."})
    assert [r[0] for r in res.needs_reading] == ["D:question/q1", "D:question/q2"]
    assert out.ledger.question("q1")["state"] == "answered" and "settled" not in out.ledger.question("q1")
    # the hook the model lane fills: fields to write, each with provenance.answered
    t2 = dl.twin_from_text(t.render(), filename="mini.md.fabulan.cosm")
    res = dl.settle(t2, at=AT, reread=lambda item, q, a: {"summary": "The day was never locked."} if item else None)
    assert res.settled == [("D:question/q1", ["P:claim/one#summary"])]
    assert t2.ledger.item("P:claim/one")["provenance"]["answered"]["summary"]["sources"] == ["D:session/session-1"]
    assert [r[0] for r in res.needs_reading] == ["D:question/q2"]


def test_a_yes_no_into_a_structure_waits_for_a_reading():
    t = with_question(mini(), question("P:reading/r#grounds[0]", kind="yes-no"))
    _, res = settled(t, {"question": "q1", "says": "yes"})
    assert res.needs_reading and res.settled == []


def test_a_write_that_adds_a_check_error_is_refused_and_a_counter_is_raised():
    t = with_question(mini(), question("N:exclusion/old#horizon", kind="text"))
    before = t.render()
    dl.record(t, [{"question": "q1", "says": "in a year or two"}], at=AT)
    recorded = t.render()
    res = dl.settle(t, at="2026-11-05T13:00:00Z", run=RUN)
    assert res.settled == [] and len(res.counters) == 1
    qid, cid, errs = res.counters[0]
    assert errs[0][0] == "closed-list"
    out = t.render()
    # the item is byte-identical; the question stays as it was; only the counter question is appended
    assert out[:len(recorded)] == recorded and out[len(recorded):].startswith("  - id: D:question/q1-counter\n")
    assert node_chunks(out)["N:exclusion/old"] == node_chunks(before)["N:exclusion/old"]
    c = t.ledger.question(cid)
    assert c["why"] == "counter" and c["about"] == "N:exclusion/old#horizon" and c["state"] == "open"
    assert c["raised"]["from"] == "settle" and "in a year or two" in c["asks"]
    assert t.ledger.question("q1")["state"] == "answered" and "settled" not in t.ledger.question("q1")
    assert errors(dl.twin_from_text(out)) == []
    # a second settle waits on the counter rather than raising another
    res2 = dl.settle(t, at=AT)
    assert res2.counters == [] and res2.waiting == [("D:question/q1", "its counter question stands")]


def test_a_banks_counter_gives_the_counter_questions_words():
    m = mc.default_registry().get("fabula")
    data = copy.deepcopy(m.data)
    data["dialectic"]["banks"]["fabulan"]["counters"] = {"closed-list": "Never or later, for {value}?"}
    m2 = mc.Manifest(m.name, m.title, m.version, m.path, data, m.inherited, m.inherited_from)
    t = with_question(mini(), question("N:exclusion/old#horizon", raised={"by": "bank", "from": "fabulan/exclusion",
                                                                          "at": dl.now(AT)}))
    t.ledger.manifest = m2
    dl.record(t, [{"question": "q1", "says": "soon"}], at=AT)
    res = dl.settle(t, at=AT)
    assert t.ledger.question(res.counters[0][1])["asks"] == "Never or later, for soon?"


def test_settle_joins_derived_runs_and_keeps_the_single_keys():
    t = with_question(mini(), question("N:exclusion/old#horizon", kind="choice", options=["never", "later"]))
    single = {k: v for k, v in t.doc["derived"].items()}
    dl.record(t, [{"question": "q1", "says": "never"}], at=AT)
    res = dl.settle(t, at="2026-11-05T13:00:00Z", run=RUN, program="settle.thym", model="g40-04", route="local")
    d = dl.twin_from_text(t.render()).doc["derived"]
    assert d["runs"] == [{"program": "settle.thym", "run": RUN, "at": dl.now("2026-11-05T13:00:00Z"),
                          "model": "g40-04", "route": "local"}]
    assert {k: v for k, v in d.items() if k != "runs"} == single and res.run == d["runs"][0]
    assert t.ledger.question("q1")["settled"]["run"] == RUN
    # without a program, no run is recorded
    t = with_question(mini(), question("N:exclusion/old#horizon", kind="choice", options=["never", "later"]))
    dl.record(t, [{"question": "q1", "says": "never"}], at=AT)
    dl.settle(t, at=AT, run=RUN)
    assert "runs" not in t.doc["derived"]


def test_make_item_hook_changes_or_withholds_a_new_item():
    t = with_question(mini(), question("N:audience", qid="q1"))
    dl.record(t, [{"question": "q1", "says": "Bookkeepers"}], at=AT)
    dl.settle(t, at=AT, make_item=lambda q, a, item: None)
    assert t.ledger.question("q1").get("settled") == {"at": dl.now(AT), "wrote": []}


# ---------------------------------------------------------------------------
# only-the-asked
# ---------------------------------------------------------------------------

def test_only_the_asked_holds_after_record_and_settle_and_catches_more():
    t = with_question(mini(), question("N:audience/owners#who"))
    base = dl.twin_from_text(t.render(), filename="mini.md.fabulan.cosm")
    dl.record(t, [{"question": "q1", "says": "support staff"}], at=AT)
    assert dl.only_the_asked(base, t) == []
    dl.settle(t, at=AT, run=RUN, program="settle.thym")
    assert dl.only_the_asked(base, t) == []
    t.ledger.item("N:audience/owners")["summary"] = "Changed behind the question's back."
    t.ledger.item("P:claim/one")["stance"] = "axiom"
    t.doc["name"] = "Renamed"
    got = dl.only_the_asked(base, t)
    assert "N:audience/owners#summary changed, and no answered question is about it" in got
    assert "P:claim/one#stance changed, and no answered question is about it" in got
    assert "the catalog's name changed" in got
    t.ledger.items.append({"id": "P:claim/two", "type": "claim"})
    assert "P:claim/two was added, and no answered question wrote it" in dl.only_the_asked(base, t)


# ---------------------------------------------------------------------------
# E. Staleness and carrying over
# ---------------------------------------------------------------------------

def test_stale_when_the_item_is_gone_or_a_spans_words_are_not_found():
    t = with_question(mini(), question("N:audience/owners#who", qid="q1"),
                      question({"start": "The day", "end": "is locked."}, qid="q2"),
                      question({"lines": "3"}, qid="q3"), question("P:claim/one", qid="q4"))
    t.ledger.items[:] = [d for d in t.ledger.items if d["id"] != "N:audience/owners"]
    got = dict(dl.stale_reasons(t, source_text="One line.\nThe night is long.\n"))
    assert set(got) == {"D:question/q1", "D:question/q2", "D:question/q3"}
    ids = dl.mark_stale(t, by="question", at=AT, source_text="One line.\nThe night is long.\n")
    q = t.ledger.question("q1")
    assert q["state"] == "stale" and q["ended"]["by"] == "question" and "names nothing" in q["ended"]["because"]
    assert len(ids) == 3 and t.ledger.question("q4")["state"] == "open"
    assert "N:audience/owners" not in [d["id"] for d in t.ledger.items]


def test_withdraw():
    t = with_question(mini(), question("N:audience/owners#who"))
    q = dl.withdraw(t, "q1", by="question", because="duplicates D:question/x", at=AT)
    assert q["state"] == "withdrawn" and q["ended"] == {"at": dl.now(AT), "by": "question",
                                                         "because": "duplicates D:question/x"}
    assert errors(dl.twin_from_text(t.render())) == []


def test_carry_over_after_a_decompile_done_again():
    old = with_question(mini(), question("N:audience/owners#who", qid="kept"),
                        question("N:exclusion/old#horizon", qid="dropped-field"),
                        question("P:claim/one", qid="gone"),
                        question("P:reading/r#intended", qid="settled", state="answered", answers=[
                            {"at": dl.now(AT), "by": "author", "says": "yes", "value": True, "confidence": 1,
                             "session": "D:session/session-0"}],
                            settled={"at": dl.now(AT), "wrote": ["P:reading/r#intended"]}))
    dl.land(old, [{"id": "D:session/session-0", "type": "session", "at": dl.now(AT),
                   "with": {"to": "author", "who": "the writer"}, "through": "person",
                   "asked": ["D:question/settled"], "answered": ["D:question/settled"], "skipped": []}])
    dl.record(old, [{"question": "kept", "says": "support staff"}], at=AT)
    old.ledger.item("N:exclusion/old")["horizon"] = "later"           # the old fabula held the value
    # the new decompile: the claim is gone, the horizon field dropped; it raised its own open question anew
    text = MINI.replace("    horizon: {pending: \"ever again?\"}\n", "")
    new = dl.twin_from_text(text, filename="mini.md.fabulan.cosm")
    new.ledger.items[:] = [d for d in new.ledger.items if d["id"] not in ("P:claim/one", "P:reading/r")]
    dl.land(new, [question("N:audience/owners#who", qid="anew", raised={"by": "move", "from": "hand",
                                                                       "at": dl.now(AT)})])
    res = dl.carry_over(old, new, at=AT)
    ids = [d["id"] for d in new.ledger.items if dl.is_d_item(d)]
    assert set(res.carried) == {"D:question/kept", "D:question/dropped-field", "D:question/gone",
                                "D:question/settled", "D:session/session-0", "D:session/session-1"}
    assert res.dropped == ["D:question/anew"] and "D:question/anew" not in ids
    assert set(res.stale) == {"D:question/dropped-field", "D:question/gone"}
    assert new.ledger.question("kept")["state"] == "answered" and new.ledger.question("kept")["answers"]
    assert new.ledger.question("gone")["ended"]["by"] == "derive"
    assert "dropped" in new.ledger.question("dropped-field")["ended"]["because"]
    out = dl.twin_from_text(new.render(), filename="mini.md.fabulan.cosm")
    # The conductor's ruling 1: question-about (18.6.8) skips a question that has ended, so a stale one whose item
    # is gone is not an error (its item being gone is why it went stale).
    assert errors(out) == []


# ---------------------------------------------------------------------------
# The three appendix examples, answered from fixture answers volumes and settled
# ---------------------------------------------------------------------------

EXAMPLES = {
    "close": (CLOSE, "close.md.fabulan.answers-2026-11-05-1200.cosm",
              {"I:occasion/why-written": {"roles", "provenance"}}),
    "rose": (ROSE, "the-sick-rose.txt.fabulap.answers-2026-11-05-1200.cosm",
             {"C:voice/speaker-to-rose": {"roles", "provenance"}, "P:reading/worm-as-desire": {"intended", "provenance"},
              "L:term/bed": {"sense", "provenance"}, "P:reading/worm-is-a-canker": {"pending"},
              "C:metre/two-beat": {"withheld", "provenance"}}),
    "tally": (TALLY, "tally.fabulac.answers-2026-11-05-1200.cosm",
              {"C:behaviour/show": {"intended", "provenance"}, "N:exclusion/old-ledger": {"horizon", "provenance"}}),
}


@pytest.mark.parametrize("name", list(EXAMPLES))
def test_the_appendix_examples_answered_and_settled(name, tmp_path):
    src, answers, expected = EXAMPLES[name]
    vol = tmp_path / src.name
    shutil.copy(src, vol)
    shutil.copy(ANS / answers, tmp_path / answers)
    original = vol.read_text(encoding="utf-8")
    t = dl.open_twin(vol)
    before = copy.deepcopy(t.doc)
    rec = dl.record_answers_volume(t, tmp_path / answers)
    t.save()
    after_record = dl.open_twin(vol)
    assert dl.only_the_asked(dl.twin_from_text(original, filename=vol.name), after_record) == []
    res = dl.settle(after_record, run=RUN, program="settle.thym", at="2026-11-05T13:00:00Z")
    after_record.save()
    text = vol.read_text(encoding="utf-8")
    # loads clean through the reader and enough/fabula.py
    rep = fb.lint(vol)
    assert rep.errors == [] and rep.warnings == []
    assert mc.lint(mc.load_volume(vol)).errors == []
    # exactly the expected fields changed, in exactly the expected items
    out = dl.open_twin(vol)
    b = {d["id"]: d for d in before["nodes"]}
    changed = {}
    for d in out.ledger.items:
        if dl.is_d_item(d) or d["id"] not in b or dl._same(d, b[d["id"]]):
            continue
        changed[d["id"]] = {k for k in set(d) | set(b[d["id"]]) if not dl._same(d.get(k), b[d["id"]].get(k))}
    assert changed == expected
    assert dl.only_the_asked(dl.twin_from_text(original, filename=vol.name), out) == []
    assert dl.provenance_written(out) == []
    # every question answered is settled; a skipped one stays open
    for e in dl.read_answers_volume(tmp_path / answers).entries:
        assert out.ledger.question(e["id"])["settled"]["run"] == RUN
    assert {k: v for k, v in out.doc["derived"].items() if k != "runs"} == before["derived"]
    assert out.doc["derived"]["runs"][-1]["program"] == "settle.thym"
    # byte for byte outside what changed: the declaration and source lines, and every untouched item
    assert original.splitlines()[:6] == text.splitlines()[:6]
    oc, nc = node_chunks(original), node_chunks(text)
    for iid, chunk in oc.items():
        if iid not in expected and iid not in {e["id"] for e in dl.read_answers_volume(tmp_path / answers).entries}:
            assert nc[iid] == chunk, iid
    assert rec.session in [s["id"] for s in out.ledger.sessions()]
    assert res.counters == [] and res.needs_reading == []


def test_the_tally_skip_stays_open():
    t = dl.open_twin(TALLY)
    dl.record_answers_volume(t, ANS / "tally.fabulac.answers-2026-11-05-1200.cosm")
    dl.settle(t, at=AT)
    assert t.ledger.question("shared-ledger")["state"] == "open"
    assert t.ledger.session("session-1")["skipped"] == ["D:question/shared-ledger"]
    assert [e["id"] for e in dl.open_questions(t) if e["form"] == "question"] == ["D:question/shared-ledger"]


# ---------------------------------------------------------------------------
# An old-spelled emf/1 twin
# ---------------------------------------------------------------------------

def test_an_emf_twin_takes_questions_and_keeps_its_declaration(tmp_path):
    vol = tmp_path / "notes.md.cosm"
    shutil.copy(EMF, vol)
    original = vol.read_text(encoding="utf-8")
    t = dl.open_twin(vol)
    assert t.ledger.is_fabula and t.ledger.flavour == "fabulan"
    r = dl.ask_by_bank(t, at=AT, run="r1")
    t.save()
    text = vol.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "oes: emf/1" and text.startswith(original.rsplit("\nnodes:\n", 1)[0])
    t = dl.open_twin(vol)
    qid = next(q["id"] for q in r.questions if q["raised"]["from"] == "fabulan/audience")
    dl.record(t, [{"question": qid, "says": "The parish council, first"}], at=AT)
    dl.settle(t, at=AT, run=RUN, program="settle.thym")
    t.save()
    text = vol.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "oes: emf/1"
    v = mc.load_volume(vol)
    assert v.declaration.how == "old" and fb.lint(v).errors == []
    assert v.item("N:audience/the-parish-council-first") is not None


# ---------------------------------------------------------------------------
# Writing back: byte for byte outside what changed
# ---------------------------------------------------------------------------

def test_a_write_keeps_every_untouched_byte_comments_and_quoting_included():
    t = with_question(mini(), question("N:audience/owners#who"))
    base = t.render()
    dl.record(t, [{"question": "q1", "says": "support staff"}], at=AT)
    dl.settle(t, at=AT)
    out = t.render()
    assert t.how == "in place"
    assert "# a comment above derived, kept\n" in out and "    because: 'it holds other things'   # quoted on purpose\n" \
        in out and "  # --- N ---\n" in out
    oc, nc = node_chunks(base), node_chunks(out)
    for iid in ("N:exclusion/old", "P:claim/one", "P:reading/r"):
        assert nc[iid] == oc[iid]
    assert head(out) == head(base)
    # inside the changed item, the untouched keys keep their lines
    for line in ("    name: Owners\n", "    summary: The owners read it.\n", '    span: {lines: "1"}\n'):
        assert line in nc["N:audience/owners"]


def test_crlf_and_no_final_newline_are_kept():
    text = MINI.replace("\n", "\r\n").rstrip("\r\n")
    t = dl.twin_from_text(text, filename="mini.md.fabulan.cosm")
    dl.land(t, [question("N:audience/owners#who")])
    out = t.render()
    assert out.startswith(text[:200]) and "\r\n" in out and "\n" not in out.replace("\r\n", "")
    assert dl._same(dl.twin_from_text(out).doc, t.doc)


def test_a_flow_nodes_list_is_re_emitted_and_the_head_kept():
    text = MINI.split("nodes:\n")[0] + "nodes: [{id: P:claim/x, type: claim, name: X, summary: X., stance: axiom, " \
                                       "provenance: {mode: derived, sources: [m], confidence: 0.4}}]\n"
    t = dl.twin_from_text(text, filename="mini.md.fabulan.cosm")
    dl.land(t, [question("P:claim/x")])
    out = t.render()
    assert t.how in ("in place", "by top-level keys")
    assert out.split("nodes:", 1)[0] == text.split("nodes:", 1)[0]
    assert dl._same(dl.twin_from_text(out).doc, t.doc)


def test_write_back_refuses_rather_than_write_something_else():
    with pytest.raises(dl.DialecticError):
        dl.write_back("a: 1\n", {"a": 1}, {"a": object()})


def test_save_writes_only_its_own_volume(tmp_path):
    vol = tmp_path / CLOSE.name
    shutil.copy(CLOSE, vol)
    t = dl.open_twin(vol)
    with pytest.raises(dl.DialecticError):
        t.save(tmp_path / "elsewhere.cosm")
    assert not (tmp_path / "elsewhere.cosm").exists()
    with pytest.raises(dl.DialecticError):
        dl.twin_from_text(CLOSE.read_text(encoding="utf-8")).save()


def test_a_folder_volume_is_not_opened_for_writing():
    with pytest.raises(dl.DialecticError, match="folder volume"):
        dl.open_twin(SELF / "holograph.cosm")


# ---------------------------------------------------------------------------
# F. The command line
# ---------------------------------------------------------------------------

def test_cli_list_raise_answer_settle(tmp_path):
    vol = tmp_path / CLOSE.name
    shutil.copy(CLOSE, vol)
    out = io.StringIO()
    assert dl.main(["list", str(vol)], out=out) == 0
    assert "D:question/occasion" in out.getvalue() and "1 sessions, 3 open" in out.getvalue()
    out = io.StringIO()
    assert dl.main(["raise", str(vol), "--rules", "--run", "r1"], out=out) == 0
    assert "questions raised" in out.getvalue()
    n_open = len(dl.questions(dl.open_twin(vol), state="open"))
    # interactive: a value, "I don't know", a skip, a refusal, then stop; written as an answers volume beside it
    replies = iter(["A support call.", "?", "nobody knows", "-", "x", "q"])
    out = io.StringIO()
    assert dl.main(["answer", str(vol), "--who", "the head of support"], ask=lambda _p: next(replies), out=out) == 0
    written = list(tmp_path.glob("*.answers-*.cosm"))
    assert len(written) == 1 and dl.is_answers_of(vol, written[0])
    av = dl.read_answers_volume(written[0])
    assert [e["state"] for e in av.entries] == ["answered", "unknown", "declined"]
    assert len(av.session["skipped"]) == 1
    assert len(dl.questions(dl.open_twin(vol), state="open")) == n_open        # the volume is not touched
    out = io.StringIO()
    assert dl.main(["settle", str(vol), "--answers", str(written[0]), "--run", RUN, "--program", "settle.thym"],
                   out=out) == 0
    assert "settled" in out.getvalue()
    assert fb.lint(vol).errors == []


def test_cli_answer_reprompts_a_bad_value_and_records_into(tmp_path):
    vol = tmp_path / TALLY.name
    shutil.copy(TALLY, vol)
    replies = iter(["maybe", "yes", "q"])
    out = io.StringIO()
    assert dl.main(["answer", str(vol), "--into"], ask=lambda _p: next(replies), out=out) == 0
    assert "not yes or no" in out.getvalue()
    assert dl.open_twin(vol).ledger.question("hide-zero")["state"] == "answered"


def test_cli_answer_from_a_file_beside_it(tmp_path):
    vol = tmp_path / ROSE.name
    shutil.copy(ROSE, vol)
    name = "the-sick-rose.txt.fabulap.answers-2026-11-05-1200.cosm"
    shutil.copy(ANS / name, tmp_path / name)
    assert dl.main(["answer", str(vol), "--from", str(tmp_path / name)], out=io.StringIO()) == 0
    assert dl.open_twin(vol).ledger.question("bed")["state"] == "answered"


def test_cli_refuses_an_answers_file_that_is_not_beside_it(tmp_path, capsys):
    vol = tmp_path / ROSE.name
    shutil.copy(ROSE, vol)
    before = vol.read_bytes()
    name = "the-sick-rose.txt.fabulap.answers-2026-11-05-1200.cosm"
    assert dl.main(["answer", str(vol), "--from", str(ANS / name)], out=io.StringIO()) == 2
    assert dl.main(["settle", str(vol), "--answers", str(ANS / name)], out=io.StringIO()) == 2
    assert "not an answers volume beside" in capsys.readouterr().err
    assert vol.read_bytes() == before


def test_cli_lists_a_folder_volume_and_refuses_to_write_it(tmp_path, capsys):
    out = io.StringIO()
    assert dl.main(["list", str(SELF)], out=out) == 0 and "1 open" in out.getvalue()
    assert dl.main(["raise", str(SELF / "holograph.cosm")], out=io.StringIO()) == 2
    assert "folder volume" in capsys.readouterr().err


def test_python_m_runs():
    import subprocess
    import sys
    r = subprocess.run([sys.executable, "-m", "enough.dialectic", "list", str(CLOSE)], capture_output=True,
                       text=True, cwd=REPO, timeout=60)
    assert r.returncode == 0 and "D:question/occasion" in r.stdout


def test_the_provenance_contract_catches_a_write_without_its_session():
    t = with_question(mini(), question("N:audience/owners#who"))
    dl.record(t, [{"question": "q1", "says": "support staff"}], at=AT)
    dl.settle(t, at=AT)
    assert dl.provenance_written(t) == []
    del t.ledger.item("N:audience/owners")["provenance"]["answered"]
    assert dl.provenance_written(t) == ["N:audience/owners#who was written by D:question/q1 without "
                                        "provenance.answered naming D:session/session-1"]
