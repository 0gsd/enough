"""The dialectic in a program (THYM 22; MacroCOSM OES 18.6): the moves `question`, `record` and `settle`, their checks
`addressed`, `no-duplicate` and `only-the-asked`, the scaffolds `bank` and `direct`, the prompts, and the three
shipped programs `decompile-prose`, `decompile-verse` and `settle` (`settle-the-answers`).

The moves reach the dialectic's core only through `ctx.engines["dialectic"]`. The engine is `enough.dialectic.thym_engine()`,
which the host registers: three functions that take and give plain data, so that a run records them and a replay
answers them (docs/fabula-landed-T1-dialectic.md, section 2).

Moves are called directly where the point is the move, and through runs (scripted coprocessors stand in for a model)
where the point is what a person sees; runs land under tmp_path (the conftest's seams).
"""
from __future__ import annotations

import copy
import datetime as dt
import re
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from enough import dialectic as dl
from enough import macrocosm as mc
from enough import thym
from enough import thym_host as H
from enough.thym import Refusal
from enough.thym import checks as C
from enough.thym import registry as R
from enough.thym import run as RUN
from enough.thym import trace as T
from enough.thym.coprocessor import candidate
from enough.thym.moves import MoveError
from enough.thym.moves import dialectic as D
from enough.thym.values import Value, digest_path, read_value

REPO = Path(__file__).resolve().parents[1]
FAB = REPO / "tests" / "fixtures" / "fabula"
ANS = REPO / "tests" / "fixtures" / "dialectic"
SUITE = REPO / "tests" / "fixtures" / "thym"
SHIPPED = REPO / "defaults" / "thym"
CLOSE = FAB / "guides" / "close.md.fabulan.cosm"
ROSE = FAB / "poems" / "the-sick-rose.txt.fabulap.cosm"
TALLY = FAB / "tally.fabulac.cosm"
ANSWERS = {CLOSE: "close.md.fabulan.answers-2026-11-05-1200.cosm",
           ROSE: "the-sick-rose.txt.fabulap.answers-2026-11-05-1200.cosm",
           TALLY: "tally.fabulac.answers-2026-11-05-1200.cosm"}
NOW = dt.datetime(2026, 11, 5, 13, 0, tzinfo=dt.timezone.utc)
FORBIDDEN = re.compile(r"\bt\d+\b|\bnode \d+\b|R:node/|Error\b|Exception\b|operand\d|thym_question|thym_settle")


def thym_engine():
    return dl.thym_engine()


def engines() -> dict:
    """The host's engines, the dialectic's among them (`enough.dialectic.thym_engine`, found by the host)."""
    out = H.engines(feed=None)
    assert "dialectic" in out
    return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ctx_for(tmp_path: Path, *, engines_: dict | None = None, ask=None, rules: bool = False, **kw):
    stage = tmp_path / "stage"
    stage.mkdir(parents=True, exist_ok=True)
    base = dict(run="2026-11-05-1300-test", node={"id": "R:node/1", "step": {"n": 1}}, decls=R.read_declarations(),
                coprocessor=None, rules=rules, now=NOW, emitted=[], slots={}, withheld={}, inputs_root=SUITE,
                root=tmp_path, stage=stage, engines=engines() if engines_ is None else engines_)
    base.update(kw)
    ctx = RUN.MoveContext(**base)
    if ask is not None:
        ctx.ask = ask
    return ctx


class Asker:
    """A stand-in for `ctx.ask`: answers in turn, every request kept."""

    def __init__(self, answers: list) -> None:
        self.answers, self.sent = list(answers), []

    def __call__(self, contract, inputs, *, budget=None):
        self.sent.append({"contract": contract, "inputs": inputs})
        return candidate(self.answers.pop(0), engine="model:scripted", tokens=10)


class Scripted:
    """A coprocessor answering by move, in turn: `{move: [answer, ...]}`."""

    def __init__(self, answers: dict) -> None:
        self.answers = {k: list(v) for k, v in answers.items()}
        self.sent: list[dict] = []

    def complete(self, contract, inputs, *, budget):
        self.sent.append({"move": contract.get("move"), "failed": list((contract.get("repair") or {}).get("failed")
                                                                      or []) if isinstance(contract.get("repair"),
                                                                                           dict) else [],
                          "inputs": {k: (v[0] if isinstance(v, tuple) else v) for k, v in inputs.items()}})
        return candidate(self.answers[contract["move"]].pop(0), engine="model:scripted", tokens=10)


def fabula(path: Path) -> Value:
    return read_value(path, "fabula")


def doc(v: Value) -> dict:
    return mc.yaml_load(v.raw.decode("utf-8")) if v.raw is not None else v.payload


def verdict(name: str, out: Value, inputs: dict) -> tuple[bool, str]:
    return C.verdict(name, out, inputs, {}, None, None)


def answers_value(path: Path) -> Value:
    return read_value(path, "volume")


# ---------------------------------------------------------------------------
# question, by rules (the scaffold `bank`)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("src,flavour,n_bank", [(CLOSE, "fabulan", 16), (ROSE, "fabulap", 20), (TALLY, "fabulac", 15)])
def test_question_by_rules_on_the_three_example_fabulas(tmp_path, src, flavour, n_bank):
    ctx = ctx_for(tmp_path, rules=True)
    got = D.bank(ctx, fabula(src))
    qs = [m.payload for m in got.payload]
    want = dl.raise_questions(dl.open_twin(src), run=ctx.run, at=NOW).questions
    assert qs == want and qs                                        # exactly the core's rules, nothing else
    assert all(q["state"] == "open" and q["raised"]["run"] == ctx.run for q in qs)
    assert all((q["raised"]["by"] in ("bank", "move")) for q in qs)
    banked = [q for q in qs if q["raised"]["by"] == "bank"]
    assert all(q["raised"]["from"].startswith(flavour + "/") for q in banked)
    assert len(banked) >= 1 and len(banked) <= n_bank * 4
    assert got.origin["question"]["model"] == 0
    inputs = {"found": fabula(src)}
    for check in ("addressed", "no-duplicate"):
        assert verdict(check, got, inputs) == (True, ""), check


def test_question_without_a_model_is_the_scaffold_and_the_move_asks_nothing_of_an_empty_volume(tmp_path):
    empty = Value("fabula", {"oes": "fabula/1", "macrocosm": "0.5.4", "flavour": "fabulan", "id": "fabula/empty",
                             "name": "Empty", "nodes": []})
    asker = Asker([])
    got = D.question(ctx_for(tmp_path, ask=asker), empty)
    assert asker.sent == []                                          # nothing read, nothing asked
    banks = [m.payload["raised"]["from"] for m in got.payload]
    # the module entries of the fabulan bank are asked of any volume; kind entries need items of their kind
    assert banks and all(b.startswith("fabulan/") for b in banks)
    assert {b.split("/")[1] for b in banks} <= {"occasion", "influence", "aim", "audience", "exclusion", "decision",
                                                 "parts", "maker", "release", "drafts", "licence", "weight", "refuse"}


def test_a_volume_with_nothing_to_ask(tmp_path):
    """A Canon volume, which has no bank, no pending value and no unsure item: no question, and no request."""
    vol = Value("volume", {"oes": "canon/1", "id": "canon/notes", "name": "notes", "nodes": [
        {"id": "P:claim/one", "type": "claim", "name": "one", "summary": "One.", "stance": "observed",
         "provenance": {"mode": "derived", "sources": ["notes.md#L1"], "confidence": 0.9}}]})
    if mc.default_registry().identify(vol.payload, filename="notes.canon.cosm").__class__ is mc.Refusal:
        pytest.skip("no canon/1 manifest here")
    asker = Asker(["questions: []\n"])
    got = D.question(ctx_for(tmp_path, ask=asker), vol)
    assert got.payload == [] and got.origin["question"]["model"] == 0
    assert len(asker.sent) == 1                                      # one chunk read; it needed no person


# ---------------------------------------------------------------------------
# question, with a model
# ---------------------------------------------------------------------------

GOOD = {"about": "P:claim/close-locks-the-day", "asks": "Can anything in a locked day still be changed by hand?",
        "why": "ambiguous", "kind": "yes-no"}
GOOD2 = {"about": "K:concept/close#summary", "asks": "Does the close also lock a day's notes, or only its entries?",
         "why": "ambiguous", "kind": "choice", "options": ["entries only", "entries and notes"]}
DUPLICATE = {"about": "I:occasion/why-written#roles.event", "asks": "What prompted this guide?", "why": "intent",
             "kind": "text"}
NOWHERE = {"about": "P:claim/nothing-like-this", "asks": "Is this one meant?", "why": "intent", "kind": "yes-no"}
ANSWERED_BY_SOURCE = {"about": "K:concept/close#name", "asks": "What is this concept called?", "why": "unsure",
                      "kind": "text"}
VOICED = {"about": "P:claim/close-locks-the-day", "asks": "I wonder, is the day locked for good?", "why": "intent",
          "kind": "yes-no"}
TWO = {"about": "P:claim/close-locks-the-day", "asks": "Who locks it? And when?", "why": "intent", "kind": "text"}


def ask_yaml(*proposals: dict) -> str:
    return mc.dump({"questions": [dict(p) for p in proposals]})


def test_question_with_a_model_keeps_the_good_and_drops_the_rest(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "CHUNK_ITEMS", 100)                        # one request reads every item
    asker = Asker([ask_yaml(GOOD, GOOD2, DUPLICATE, NOWHERE, ANSWERED_BY_SOURCE, VOICED, TWO)])
    v = fabula(CLOSE)
    got = D.question(ctx_for(tmp_path, ask=asker), v)
    qs = [m.payload for m in got.payload]
    model = [q for q in qs if q["raised"]["by"] == "model"]
    assert [(q["about"], q["asks"]) for q in model] == [(GOOD["about"], GOOD["asks"]), (GOOD2["about"],
                                                                                         GOOD2["asks"])]
    assert all(q["raised"] == {"by": "model", "from": "question", "at": NOW, "run": "2026-11-05-1300-test"}
               for q in model)
    assert model[1]["options"] == GOOD2["options"] and model[0]["to"] == "author"   # the bank's answerer
    rules = dl.raise_questions(dl.open_twin(CLOSE), run="2026-11-05-1300-test", at=NOW).questions
    assert qs[:len(rules)] == rules                                   # the rules first, then the model's
    dropped = {d["asks"]: d["why"] for d in got.origin["question"]["dropped"]}
    assert "already asks" in dropped[DUPLICATE["asks"]]
    assert "no item read here" in dropped[NOWHERE["asks"]]
    assert "already says" in dropped[ANSWERED_BY_SOURCE["asks"]]
    assert "someone's voice" in dropped[VOICED["asks"]]
    assert "more than one thing" in dropped[TWO["asks"]]
    assert len(asker.sent) == 1                                       # something was kept: asked once
    for check in ("addressed", "no-duplicate"):
        assert verdict(check, got, {"found": v}) == (True, ""), check


def test_the_request_is_asked_again_when_nothing_valid_comes_back(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "CHUNK_ITEMS", 100)
    asker = Asker(["this is not yaml: [", ask_yaml(NOWHERE, VOICED), ask_yaml(GOOD)])
    got = D.question(ctx_for(tmp_path, ask=asker), fabula(CLOSE))
    # the first answer did not read: asked again with why; the second kept nothing: that chunk is given up
    assert len(asker.sent) == 2
    failed = asker.sent[1]["contract"]["repair"]["failed"]
    assert failed and failed[0]["name"] == "questions" and "could not be read" in failed[0]["why"]
    assert not [m for m in got.payload if m.payload["raised"]["by"] == "model"]
    asker = Asker([ask_yaml(NOWHERE, VOICED), ask_yaml(GOOD)])
    got = D.question(ctx_for(tmp_path, ask=asker), fabula(CLOSE))
    assert len(asker.sent) == 2
    why = asker.sent[1]["contract"]["repair"]["failed"][0]["why"]
    assert why.startswith("no question could be kept") and "no item read here" in why and "voice" in why
    assert [m.payload["asks"] for m in got.payload if m.payload["raised"]["by"] == "model"] == [GOOD["asks"]]


def test_question_asks_one_request_per_chunk_of_items(tmp_path, monkeypatch):
    v = fabula(TALLY)
    read = D.asked_of(doc(v)["nodes"], "fabulac")
    # of a fabulac, the model reads only what a person can say something about, and whatever is unsure or pending
    assert read and {D._kind(i) for i in read} - set(D.PERSON_KINDS["fabulac"]) <= {"occasion", "dependency"}
    assert all(D._marked(i) for i in read if D._kind(i) not in D.PERSON_KINDS["fabulac"])
    assert not [i for i in read if D._kind(i) in ("file", "change", "release", "case") and not D._marked(i)]
    asker = Asker(["questions: []\n"])
    D.question(ctx_for(tmp_path, ask=asker), v)
    assert len(asker.sent) == 1                                       # fewer, fuller: one request holds them all
    assert len(mc.yaml_load(asker.sent[0]["inputs"]["items"].payload)["items"]) == len(read)
    monkeypatch.setattr(D, "CHUNK_ITEMS", 10)
    chunks = -(-len(read) // 10)
    asker = Asker(["questions: []\n"] * chunks)
    D.question(ctx_for(tmp_path, ask=asker), v)
    assert len(asker.sent) == chunks and chunks >= 2
    first = mc.yaml_load(asker.sent[0]["inputs"]["items"].payload)["items"]
    assert len(first) == 10 and all("made" not in it for it in first)
    assert asker.sent[0]["inputs"]["flavour"].payload == "fabulac"
    monkeypatch.setattr(D, "CHUNK_ITEMS", 100)
    monkeypatch.setattr(D, "CHUNK_CHARS", 1)                          # a lone item larger than the budget goes alone
    assert [len(c) for c in D._chunks(doc(v)["nodes"], "fabulac")] == [1] * len(read)


def test_the_question_prompts_one_per_flavour():
    def inputs(fl):
        return {"flavour": (Value("word", fl), "x"), "volume": (Value("string", "Tally"), "x"),
                "items": (Value("string", "- {id: C:behaviour/show}"), "x"), "asked": (Value("string", "- x"), "x")}
    verse = D.question_messages({}, inputs("fabulap"))
    code = D.question_messages({}, inputs("fabulac"))
    prose = D.question_messages({}, inputs("fabulan"))
    assert "poem" in verse[0]["content"] and "speaks" in verse[0]["content"] and "metre" in verse[0]["content"]
    assert "docstring" in code[0]["content"] and "name the edge" in code[0]["content"] \
        and "nothing a person cannot answer" not in verse[0]["content"]               # what is worth a person's time
    assert "never \"is this behaviour intended?\" in general" in code[0]["content"]
    for msgs in (verse, code, prose):                    # one question per address, and the quoting line, everywhere
        assert "the only one about its item or field" in msgs[0]["content"]
        assert "any value that is not a plain word or number" in msgs[0]["content"]
    assert "claim rests on" in prose[0]["content"] and "assumes" in prose[0]["content"]
    for m in (verse, code, prose):
        s = m[0]["content"]
        assert "one thing" in s and "no one's voice" in s and "already answers" in s and "questions:" in s
        assert "- {id: C:behaviour/show}" in m[1]["content"] and "do not ask these again" in m[1]["content"]
    assert D.PROMPTS["question"] is D.question_messages
    assert R.MOVES.prompt("question")({}, inputs("fabulap")) == verse       # the host's chain reaches it
    assert D.question_messages({}, {}) is None                       # not this module's request
    assert D.settle_messages({}, {}) is None


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("src", [CLOSE, ROSE, TALLY])
def test_record_writes_the_answers_volume_into_the_questions(tmp_path, src):
    f = fabula(src)
    said = answers_value(ANS / ANSWERS[src])
    out = D.record(ctx_for(tmp_path), said, **{"in": f})
    t = dl.open_twin(src)
    dl.record_answers_volume(t, ANS / ANSWERS[src])
    assert out.raw.decode("utf-8") == t.render()                     # exactly the core's, byte for byte
    assert out.type == "fabula"
    for check in ("addressed", "only-the-asked"):
        assert verdict(check, out, {"said": said, "in": f}) == (True, ""), check
    recorded = dict(map(tuple, out.origin["record"]["recorded"]))
    if src == ROSE:   # an answer, "I don't know" and a refusal
        assert recorded["D:question/the-plate"] == "unknown" and recorded["D:question/dark"] == "declined"
        assert recorded["D:question/speaker"] == "answered"
    if src == TALLY:  # a skip stays open
        q = next(n for n in doc(out)["nodes"] if n["id"] == "D:question/shared-ledger")
        assert q["state"] == "open"
        s = next(n for n in doc(out)["nodes"] if n["id"] == "D:session/session-1")
        assert s["skipped"] == ["D:question/shared-ledger"]


def test_record_refuses_in_plain_words(tmp_path):
    f = fabula(CLOSE)
    said = answers_value(ANS / ANSWERS[CLOSE])
    once = D.record(ctx_for(tmp_path), said, **{"in": f})
    with pytest.raises(MoveError) as e:                               # a replay of the same sitting is not doubled
        D.record(ctx_for(tmp_path), said, **{"in": once})
    assert "recorded" in str(e.value) and not FORBIDDEN.search(str(e.value))
    other = answers_value(ANS / ANSWERS[ROSE])
    with pytest.raises(MoveError, match="fabula/poems--the-sick-rose-txt"):
        D.record(ctx_for(tmp_path), other, **{"in": f})
    with pytest.raises(MoveError, match=r"^record needs the volume the answers are for: record said in f$"):
        D.record(ctx_for(tmp_path), said)


# ---------------------------------------------------------------------------
# settle
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("src", [CLOSE, ROSE, TALLY])
def test_settle_writes_exactly_what_the_core_says_and_nothing_else(tmp_path, src):
    f = fabula(src)
    recorded = D.record(ctx_for(tmp_path), answers_value(ANS / ANSWERS[src]), **{"in": f})
    asker = Asker([])
    out = D.settle(ctx_for(tmp_path, ask=asker, program=Path("settle.thym")), recorded)
    assert asker.sent == []                                          # nothing needs reading: nothing asked
    t = dl.twin_from_text(recorded.raw.decode("utf-8"), filename=src.name)
    dl.settle(t, run="2026-11-05-1300-test", program="settle.thym", at=NOW)
    assert out.raw.decode("utf-8") == t.render()
    assert out.origin["settle"]["settled"]
    for check in ("addressed", "only-the-asked", "fabula-checks"):
        assert verdict(check, out, {"answered": recorded}) == (True, ""), check
    assert verdict("only-the-asked", out, {"f": f}) == (True, "")    # the program's keeps, against the input
    assert D.only_the_asked(D._doc(f), D._doc(out)) == []
    assert dl.only_the_asked(dl.open_twin(src), t) == []             # the check agrees with the core's
    runs = doc(out)["derived"]["runs"]
    assert runs[-1] == {"program": "settle.thym", "run": "2026-11-05-1300-test", "at": NOW}


def _whole_item_question(src: Path, about: str) -> tuple[Value, Value]:
    """A fabula with an open question about a whole item, and an answers volume that answers it."""
    t = dl.open_twin(src)
    dl.land(t, [{"id": "D:question/stand-by", "type": "question", "about": about,
                 "asks": "Would you still stand behind this as written?", "why": "unsure", "kind": "text",
                 "to": "author", "raised": {"by": "person", "from": "hand", "at": NOW}, "state": "open"}])
    av = dl.answers_delta(t, [{"question": "stand-by", "says": "Mostly; a locked day can be reopened by support.",
                               "value": "a locked day can be reopened by support, on request", "confidence": 0.8}],
                          session={"with": {"to": "author", "who": "the guide's writer"}}, at=NOW)
    return Value("fabula", mc.yaml_load(t.render()), raw=t.render().encode("utf-8")), \
        Value("volume", mc.yaml_load(dl.write_answers_volume(av)), raw=dl.write_answers_volume(av).encode("utf-8"))


REREAD = {"item": {"id": "P:claim/close-locks-the-day", "type": "claim", "name": "A close locks the day",
                   "summary": "A close locks the day, so no entry in it changes, unless support reopens it on request.",
                   "stance": "axiom", "salience": "critical", "roles": {"subject": "K:concept/close"},
                   "links": [{"rel": "defines", "to": "K:concept/close"}], "span": {"lines": "4"}}}
BAD_REREAD = {"item": {**REREAD["item"], "stance": "certain"}}


def test_settle_reads_again_an_item_an_answer_is_about_and_a_good_rewrite_lands(tmp_path):
    f, said = _whole_item_question(CLOSE, "P:claim/close-locks-the-day")
    answered = D.record(ctx_for(tmp_path), said, **{"in": f})
    asker = Asker([mc.dump(REREAD)])
    out = D.settle(ctx_for(tmp_path, ask=asker, program=Path("settle.thym")), answered)
    assert len(asker.sent) == 1 and asker.sent[0]["inputs"]["says"].payload.startswith("Mostly")
    item = next(n for n in doc(out)["nodes"] if n["id"] == "P:claim/close-locks-the-day")
    assert item["summary"] == REREAD["item"]["summary"]
    assert item["provenance"]["answered"]["summary"]["sources"][0].startswith("D:session/")
    q = next(n for n in doc(out)["nodes"] if n["id"] == "D:question/stand-by")
    assert q["settled"]["wrote"] == ["P:claim/close-locks-the-day#summary"]
    assert doc(out)["derived"]["runs"][-1]["model"] == "scripted"
    for check in ("addressed", "only-the-asked", "fabula-checks"):
        assert verdict(check, out, {"answered": answered}) == (True, ""), check


def test_a_rewrite_that_breaks_a_check_is_refused_and_the_item_left(tmp_path):
    f, said = _whole_item_question(CLOSE, "P:claim/close-locks-the-day")
    answered = D.record(ctx_for(tmp_path), said, **{"in": f})
    asker = Asker([mc.dump(BAD_REREAD), mc.dump(BAD_REREAD)])
    out = D.settle(ctx_for(tmp_path, ask=asker), answered)
    assert len(asker.sent) == 2                                       # asked again once, with the checks' words
    assert asker.sent[1]["contract"]["repair"]["failed"][0]["name"] == "fabula-checks"
    assert "certain" in asker.sent[1]["contract"]["repair"]["failed"][0]["why"]
    before = next(n for n in doc(answered)["nodes"] if n["id"] == "P:claim/close-locks-the-day")
    after = next(n for n in doc(out)["nodes"] if n["id"] == "P:claim/close-locks-the-day")
    assert after == before                                            # the item is left as it was
    q = next(n for n in doc(out)["nodes"] if n["id"] == "D:question/stand-by")
    assert q["state"] == "answered" and "settled" not in q            # unsettled, and no counter question raised
    assert not [n for n in doc(out)["nodes"] if n["id"].endswith("-counter")]
    assert out.origin["settle"]["left"][0]["question"] == "D:question/stand-by"


def test_direct_leaves_what_must_be_read_again_answered_and_unsettled(tmp_path):
    f, said = _whole_item_question(CLOSE, "P:claim/close-locks-the-day")
    answered = D.record(ctx_for(tmp_path), said, **{"in": f})
    out = D.direct(ctx_for(tmp_path, rules=True), answered)
    q = next(n for n in doc(out)["nodes"] if n["id"] == "D:question/stand-by")
    assert q["state"] == "answered" and "settled" not in q
    assert out.origin["settle"]["needs_reading"][0]["question"] == "D:question/stand-by"
    assert verdict("only-the-asked", out, {"answered": answered}) == (True, "")


def test_the_settle_prompt_reads_one_item_in_the_light_of_the_answer():
    inputs = {"item": (Value("string", "id: P:claim/x\n"), "x"), "asks": (Value("string", "Still so?"), "x"),
              "says": (Value("string", "No."), "x"), "value": (Value("string", "no"), "x"),
              "because": (Value("string", "the whole item"), "x")}
    m = D.settle_messages({}, inputs)
    assert "authority" in m[0]["content"] and "Keep the item's id and type" in m[0]["content"]
    assert "id: P:claim/x" in m[1]["content"] and "Still so?" in m[1]["content"] and "No." in m[1]["content"]
    assert D.PROMPTS["settle"] is D.settle_messages


# ---------------------------------------------------------------------------
# The checks, refusing what they catch
# ---------------------------------------------------------------------------

def test_the_checks_catch_their_broken_cases():
    f = fabula(CLOSE)
    bad = Value("list", [Value("item", {"id": "D:question/x", "type": "question", "about": "P:claim/gone",
                                        "asks": "Is it?", "state": "open", "raised": {"from": "question"}})])
    ok, why = verdict("addressed", bad, {"found": f})
    assert not ok and why == "D:question/x: P:claim/gone names nothing in this volume"
    dup = Value("list", [Value("item", {"id": "D:question/again", "about": "I:occasion/why-written#roles.event",
                                        "asks": "What prompted this guide", "state": "open",
                                        "raised": {"from": "hand"}})])
    ok, why = verdict("no-duplicate", dup, {"found": f})
    assert not ok and "already asks" in why
    moved = copy.deepcopy(doc(f))
    next(n for n in moved["nodes"] if n["id"] == "K:concept/close")["summary"] = "Changed by nobody."
    ok, why = verdict("only-the-asked", Value("fabula", moved), {"f": f})
    assert not ok and why == "K:concept/close#summary changed, and no question is about it"
    runs = copy.deepcopy(doc(f))
    runs["derived"]["model"] = "another"
    assert verdict("only-the-asked", Value("fabula", runs), {"f": f}) == (False, "derived changed beyond its runs")
    runs = copy.deepcopy(doc(f))
    runs["derived"]["runs"] = [{"program": "settle.thym", "run": "r", "at": NOW}]
    assert verdict("only-the-asked", Value("fabula", runs), {"f": f}) == (True, "")     # a run joins derived.runs


# ---------------------------------------------------------------------------
# The engine: refused without it, in plain words
# ---------------------------------------------------------------------------

def test_the_moves_refuse_without_the_engine(tmp_path):
    f = fabula(CLOSE)
    ctx = ctx_for(tmp_path, engines_={})
    for fn, args, kw in ((D.question, (f,), {}), (D.bank, (f,), {}), (D.settle, (f,), {}), (D.direct, (f,), {}),
                         (D.record, (answers_value(ANS / ANSWERS[CLOSE]),), {"in": f})):
        with pytest.raises(MoveError) as e:
            fn(ctx, *args, **kw)
        assert "needs the dialectic engine" in str(e.value) and "this host has none" in str(e.value)
        assert not FORBIDDEN.search(str(e.value))
    half = ctx_for(tmp_path, engines_={"dialectic": SimpleNamespace(thym_question=dl.thym_question)})
    with pytest.raises(MoveError, match=r"^the dialectic engine here cannot settle answers, which settle needs$"):
        D.settle(half, f)


def test_a_folder_volume_is_questioned_but_never_written(tmp_path):
    with pytest.raises(MoveError, match="folder volume, which keeps its questions in its own layout"):
        D._volume_arg(Value("volume", mc.Volume(tmp_path, manifest=None), path=tmp_path / "holograph"), "settle",
                      single=True)


# ---------------------------------------------------------------------------
# The shipped programs and the two-run shape, end to end, then replayed
# ---------------------------------------------------------------------------

def test_the_shipped_programs_are_the_texts():
    blocks = _text_blocks()
    for name in ("decompile-prose", "decompile-verse", "settle"):
        assert (SHIPPED / f"{name}.thym").read_text(encoding="utf-8") in blocks, name
    assert (SUITE / "programs" / "settle-the-answers.thym").read_bytes() == (SHIPPED / "settle.thym").read_bytes()


def test_the_dialectic_module_is_vendorable():
    """One module under the vendored folder, importing only what the package may, and naming no host path."""
    text = (REPO / "enough" / "thym" / "moves" / "dialectic.py").read_text(encoding="utf-8")
    body = "\n".join(l for l in text.splitlines() if not l.startswith(("from enough", "import enough")))
    assert not re.search(r"ENOUGH_|~/enough|defaults/cosm|enough\.[a-z_]", body)
    init = (REPO / "enough" / "thym" / "moves" / "__init__.py").read_text(encoding="utf-8")
    assert "dialectic" not in init                                   # never imported eagerly: load_all finds it
    decls = R.read_declarations()
    for move in ("question", "record", "settle"):
        assert decls[move]["code"] == f"enough.thym.moves.dialectic:{move}"
        assert R.resolve(decls[move]["code"]) is getattr(D, move)
    assert R.MOVES.scaffold(decls["question"]) is D.bank and R.MOVES.scaffold(decls["settle"]) is D.direct
    for chk in ("addressed", "no-duplicate", "only-the-asked"):
        assert C.CHECKS.lookup(chk) is not None


def plan(tmp_path: Path, name: str, inputs: dict[str, tuple[str, Path]]):
    rows = [{"name": n, "type": t, "path": str(p), "sha256": digest_path(p)} for n, (t, p) in inputs.items()]
    p = SHIPPED / f"{name}.thym"
    got = thym.plan_file(p, rows)
    assert not isinstance(got, Refusal), got
    return got, p


def run(tmp_path: Path, name: str, inputs: dict, *, cp=None, rules: bool = False, now=NOW):
    pl, p = plan(tmp_path, name, inputs)
    t = RUN.run(pl, inputs_root=tmp_path, root=tmp_path / "root", program=p, coprocessor=cp, rules=rules,
                engines=engines(), now=now)
    return t


@pytest.mark.parametrize("name,kind", [("decompile-prose", "essay"), ("decompile-verse", "poem")])
def test_the_decompile_programs_compile_and_plan(tmp_path, name, kind):
    pl, _p = plan(tmp_path, name, {kind: ("text", FAB / "guides" / "close.md")})
    nodes = [n for n in pl["nodes"] if n.get("type") == "node"]
    assert [n["move"] for n in nodes] == ["derive", "assert", "question", "gather"]
    q = next(n for n in nodes if n["move"] == "question")
    assert q["asks"] is True


def test_settle_compiles_and_plans(tmp_path):
    pl, _p = plan(tmp_path, "settle", {"f": ("fabula", CLOSE), "said": ("volume", ANS / ANSWERS[CLOSE])})
    nodes = [n for n in pl["nodes"] if n.get("type") == "node"]
    assert [n["move"] for n in nodes] == ["record", "settle"]


def two_runs(tmp_path: Path, src: Path, *, cp=None, rules=False):
    """The second run of the two-run shape over a fabula of the three examples: the answers volume beside it."""
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    shutil.copy(src, work / src.name)
    shutil.copy(ANS / ANSWERS[src], work / ANSWERS[src])
    t = run(work, "settle", {"f": ("fabula", work / src.name), "said": ("volume", work / ANSWERS[src])}, cp=cp,
            rules=rules)
    return t, work


@pytest.mark.parametrize("src", [CLOSE, ROSE, TALLY])
def test_settle_the_answers_runs_lands_and_replays(tmp_path, src):
    t, work = two_runs(tmp_path, src, cp=Scripted({}))
    assert isinstance(t, T.Trace) and t.landed, getattr(t, "refusal", t)
    out = t.outputs["g"].read_text(encoding="utf-8")
    exp = dl.open_twin(work / src.name)
    dl.record_answers_volume(exp, work / ANSWERS[src])
    dl.settle(exp, run=t.run_id, program="settle-the-answers", at=NOW)     # the program's name
    assert out == exp.render()                                       # byte for byte the core's two steps
    assert (work / src.name).read_bytes() == src.read_bytes()        # the input is never written
    again = RUN.replay(t.dir, root=tmp_path / "again", inputs_root=work)
    assert isinstance(again, T.Trace) and again.replay["identical"], again
    names = {p.name for p in (t.dir / "candidates").glob("*.cosm")}
    assert any("-e" in n for n in names)                              # the engine's calls, recorded


def test_settle_the_answers_under_rules(tmp_path):
    t, _work = two_runs(tmp_path, TALLY, rules=True)
    assert t.landed, t.refusal


def test_decompile_prose_lands_questions_with_the_fabula_then_settle_closes_one(tmp_path):
    """The two runs as a pair over the suite's orchard notes: decompile with a scripted model (derive and question),
    an answers volume written as the page would, then settle; both runs replay without the model."""
    from tests.test_thym_moves import PASSAGE, WHOLE_ATEM
    work = tmp_path / "work"
    work.mkdir()
    shutil.copy(SUITE / "inputs" / "notes.md", work / "notes.md")
    asked = ask_yaml({"about": "P:claim/mulch-made-difference", "asks": "Was it the leaf mould, or the wet spring?",
                      "why": "conflict", "kind": "choice", "options": ["the leaf mould", "the wet spring", "both"]})
    cp = Scripted({"derive": [PASSAGE, WHOLE_ATEM], "question": [asked, "questions: []\n", "questions: []\n"]})
    t1 = run(work, "decompile-prose", {"essay": ("text", work / "notes.md")}, cp=cp)
    assert isinstance(t1, T.Trace) and t1.landed, getattr(t1, "refusal", t1)
    fab_path = work / "notes.md.fabulan.cosm"
    shutil.copy(t1.outputs["f"], fab_path)
    landed = dl.open_twin(fab_path)
    model_qs = [q for q in landed.ledger.questions() if q["raised"]["by"] == "model"]
    assert [q["asks"] for q in model_qs] == ["Was it the leaf mould, or the wet spring?"]
    assert all(q["state"] == "open" for q in landed.ledger.questions())
    again = RUN.replay(t1.dir, root=tmp_path / "again1", inputs_root=work)
    assert isinstance(again, T.Trace) and again.replay["identical"], again
    # the person answers, in a page: an answers volume beside the fabula
    q = model_qs[0]
    av = dl.answers_delta(landed, [{"question": q["id"], "says": "Both, I think.", "value": "both"}],
                          session={"with": {"to": "author", "who": "the orchard's keeper"}}, at=NOW)
    ans = dl.answers_path(fab_path, at=NOW)
    ans.write_text(dl.write_answers_volume(av), encoding="utf-8")
    # a choice about a whole claim: the claim must be read again in its light, so settle asks for it rewritten
    claim = copy.deepcopy(landed.ledger.item("P:claim/mulch-made-difference"))
    claim = {k: v for k, v in claim.items() if k not in ("provenance", "made")}
    claim["summary"] = "Both the leaf mould and the wet spring raised the yield, the orchard's keeper says."
    cp2 = Scripted({"settle": [mc.dump({"item": claim})]})
    t2 = run(work, "settle", {"f": ("fabula", fab_path), "said": ("volume", ans)}, cp=cp2,
             now=NOW + dt.timedelta(hours=1))
    assert isinstance(t2, T.Trace) and t2.landed, getattr(t2, "refusal", t2)
    g = dl.twin_from_text(t2.outputs["g"].read_text(encoding="utf-8"), filename=fab_path.name)
    assert g.ledger.question(q["id"])["state"] == "answered" and g.ledger.question(q["id"])["settled"]
    assert g.ledger.item("P:claim/mulch-made-difference")["summary"] == claim["summary"]
    assert [x["move"] for x in cp2.sent] == ["settle"]
    assert dl.only_the_asked(landed, g) == []
    again = RUN.replay(t2.dir, root=tmp_path / "again2", inputs_root=work)
    assert isinstance(again, T.Trace) and again.replay["identical"], again


@pytest.mark.parametrize("name,kind,src", [("decompile-prose", "essay", FAB / "guides" / "close.md"),
                                           ("decompile-verse", "poem", FAB / "poems" / "the-sick-rose.txt")])
def test_the_decompile_programs_run_under_rules(tmp_path, name, kind, src):
    work = tmp_path / "work"
    work.mkdir()
    shutil.copy(src, work / src.name)
    t = run(work, name, {kind: ("text", work / src.name)}, rules=True)
    if isinstance(t, T.Trace) and not t.landed:
        # the rules twin holds no claims, so `covers` may not hold of it: the run refuses at the assert, in its words
        assert "does not cover" in t.refusal.message or "in no item" in t.refusal.message, t.refusal
        return
    assert isinstance(t, T.Trace) and t.landed, t
    got = mc.yaml_load(t.outputs["f"].read_text(encoding="utf-8"))
    assert [n for n in got["nodes"] if str(n.get("id", "")).startswith("D:question/")]
    # VERSE FLIP (flipped): `derive … as verse` reaches the engine's verse reading, so a poem lands as a fabulap and
    # is asked the fabulap bank
    want = {"decompile-prose": "fabulan", "decompile-verse": "fabulap"}[name]
    assert got.get("flavour", "fabulan") == want
    banked = {q["raised"]["from"].split("/")[0] for q in got["nodes"]
              if str(q.get("id", "")).startswith("D:question/") and q["raised"]["by"] == "bank"}
    assert banked == {want}


ASK_ONE = """program ask-the-guide
  why: the questions a person should answer about the guide, landed with it.
  takes f: fabula
  gives g: fabula

  let asked = question f
  give gather asked with f
end
"""


def test_the_three_moves_run_through_the_hosts_engines_and_prompts(tmp_path):
    """End to end through the host: `engines()` finds `enough.dialectic.thym_engine`, and the host's model coprocessor
    builds the requests with this module's prompts (its chain); a run lands questions, the person answers, and
    `settle-the-answers` lands the settled fabula, re-reading one item."""
    work = tmp_path / "work"
    work.mkdir()
    fab = work / CLOSE.name
    shutil.copy(CLOSE, fab)
    live = H.engines(feed=None)
    assert hasattr(live["dialectic"], "thym_settle")
    seen: list = []
    proposal = ask_yaml({"about": "P:claim/close-locks-the-day", "asks": "Would you still stand behind this claim?",
                         "why": "unsure", "kind": "text"})

    def complete(messages, **kw):
        seen.append(messages)
        system = messages[0]["content"]
        if "find what only" in system:
            here = "P:claim/close-locks-the-day" in messages[1]["content"].split("Already asked")[0]
            return (proposal if here else "questions: []\n"), {"model": "m1"}
        assert "read one item of a fabula again" in system
        return mc.dump(REREAD), {"model": "m1"}
    cp = H.ModelCoprocessor(complete)
    prog = work / "ask-the-guide.thym"
    prog.write_text("thym 1\n\n" + ASK_ONE, encoding="utf-8")
    pl = thym.plan_file(prog, [{"name": "f", "type": "fabula", "path": str(fab), "sha256": digest_path(fab)}])
    assert not isinstance(pl, Refusal), pl
    t1 = RUN.run(pl, inputs_root=work, root=tmp_path / "root", program=prog, coprocessor=cp, engines=live, now=NOW)
    assert t1.landed, t1.refusal
    assert "poem" not in seen[0][0]["content"] and "claim rests on" in seen[0][0]["content"]   # the prose prompt
    landed = work / "landed.md.fabulan.cosm"
    shutil.copy(t1.outputs["g"], landed)
    tw = dl.open_twin(landed)
    model_qs = [x for x in tw.ledger.questions() if x["raised"]["by"] == "model"]
    assert model_qs, [m[1]["content"][-400:] for m in seen]
    q = model_qs[0]
    av = dl.answers_delta(tw, [{"question": q["id"], "says": "Mostly; support can reopen a locked day.",
                                "value": "a locked day can be reopened by support, on request"}],
                          session={"with": {"to": "author", "who": "the guide's writer"}}, at=NOW)
    ans = dl.answers_path(landed, at=NOW)
    ans.write_text(dl.write_answers_volume(av), encoding="utf-8")
    t2 = run(work, "settle", {"f": ("fabula", landed), "said": ("volume", ans)}, cp=cp,
             now=NOW + dt.timedelta(hours=1))
    assert t2.landed, t2.refusal
    g = dl.twin_from_text(t2.outputs["g"].read_text(encoding="utf-8"), filename=landed.name)
    assert g.ledger.item("P:claim/close-locks-the-day")["summary"] == REREAD["item"]["summary"]
    assert g.ledger.question(q["id"])["settled"]["wrote"] == ["P:claim/close-locks-the-day#summary"]
    assert g.doc["derived"]["runs"][-1]["model"] == "m1"
    for t in (t1, t2):
        again = RUN.replay(t.dir, root=tmp_path / "again", inputs_root=work)
        assert again.replay["identical"], again.replay


def test_a_verse_run_records_what_its_rules_read_and_replays_with_no_dictionary(tmp_path):
    """`derive … as verse` reaches the engine's verse rules with the `pron` engine (pronunciations, `PRON_FIELDS`):
    the poem lands as a fabulap whose lines are scanned and rhymed, and the run replays byte for byte with no
    dictionary and no engine at all, since the engine call that read the pronunciations is recorded whole.
    `the-sick-rose.pron.json` is what FEED answered for the poem's words, cut to `PRON_FIELDS` (3 KB)."""
    import json
    table = json.loads((FAB / "poems" / "the-sick-rose.pron.json").read_text(encoding="utf-8"))
    asked: list = []

    def pron(words):
        asked.append(list(words))
        return {w: table.get(w) for w in words}
    work = tmp_path / "work"
    work.mkdir()
    shutil.copy(FAB / "poems" / "the-sick-rose.txt", work / "the-sick-rose.txt")
    pl, p = plan(work, "decompile-verse", {"poem": ("text", work / "the-sick-rose.txt")})
    eng = {**engines(), "pron": H.pron_fields(pron)}
    t = RUN.run(pl, inputs_root=work, root=tmp_path / "root", program=p, rules=True, engines=eng, now=NOW)
    assert isinstance(t, T.Trace) and t.landed, t
    assert asked, "the verse rules read their pronunciations through the pron engine"
    got = mc.yaml_load(t.outputs["f"].read_text(encoding="utf-8"))
    assert got["flavour"] == "fabulap"
    lines = [n for n in got["nodes"] if str(n["id"]).startswith("C:line/")]
    assert len(lines) == 8 and all(n.get("rhyme") for n in lines)
    assert any(isinstance(n.get("syllables"), int) for n in lines)          # scanned where FEED knew every word
    assert [n["id"] for n in got["nodes"] if str(n["id"]).startswith("C:rhyme/")]
    again = RUN.replay(t.dir, root=tmp_path / "again", inputs_root=work, engines={})
    assert isinstance(again, T.Trace) and again.replay["identical"], again


def test_the_pron_engine_answers_only_what_verse_rules_read():
    full = {"rose": {"word": "rose", "ipa": "/roʊz/", "hyphenation": "rose", "definition": "a flower",
                     "perfect_rhymes": ["goes", "knows", "nose"], "slant_rhymes": ["roads"]}, "o": None}
    cut = H.pron_fields(lambda ws: full)(["rose", "o", "knows"])
    assert cut == {"rose": {"word": "rose", "ipa": "/roʊz/", "perfect_rhymes": ["knows"], "slant_rhymes": []},
                   "o": None}


def _text_blocks() -> list[str]:
    """Every ```thym block of the synced text, docs/THYM.md, as a program file holds it."""
    import re as _re
    text = (Path(__file__).resolve().parents[1] / "docs" / "THYM.md").read_text(encoding="utf-8")
    return [b for b in _re.findall(r"^```thym\n(.*?)^```", text, _re.S | _re.M)]


def test_a_request_keeps_an_interface_with_its_behaviours_shows_no_bookkeeping_and_every_pending(tmp_path,
                                                                                                monkeypatch):
    """docs/fabula-landed-G3.md: an interface and the behaviours that cite it are read in one request; an item is
    shown without the fields no person is asked about; every part lists the volume's pendings under Already asked."""
    rows = [{"id": "C:interface/m.f", "type": "interface", "name": "f", "defined-in": "C:file/m", "exported": True,
             "stance": "observed", "surface": "function", "span": {"file": "m.py", "lines": "1"},
             "provenance": {"confidence": 1, "state": "known"}},
            {"id": "C:interface/m.g", "type": "interface", "name": "g"},
            {"id": "C:behaviour/m.g-does", "type": "behaviour", "of": ["C:interface/m.g"], "does": "x"},
            {"id": "C:behaviour/m.f-does", "type": "behaviour", "of": ["C:interface/m.f"], "does": "y",
             "stance": "deduced", "provenance": {"confidence": 0.7, "state": "known"}}]
    assert [[i["id"] for i in g] for g in D._groups(rows)] == [
        ["C:interface/m.f", "C:behaviour/m.f-does"], ["C:interface/m.g", "C:behaviour/m.g-does"]]
    assert D._compact(rows[0], "fabulac") == {"id": "C:interface/m.f", "name": "f"}
    assert D._compact(rows[3], "fabulac")["provenance"] == {"confidence": 0.7, "state": "known"}
    assert "span" in D._compact(rows[0], "fabulan")                  # prose and verse keep what their lines need
    v = fabula(TALLY)
    pend = [q for q in dl.raise_questions(dl.open_twin(TALLY), at="2026-11-05T12:00:00Z").questions
            if (q.get("raised") or {}).get("by") == "move"]
    assert pend
    monkeypatch.setattr(D, "CHUNK_ITEMS", 10)
    n = len(D._chunks(doc(v)["nodes"], "fabulac"))
    asker = Asker(["questions: []\n"] * n)
    D.question(ctx_for(tmp_path, ask=asker), v)
    for sent in asker.sent:
        for q in pend:
            assert q["asks"] in sent["inputs"]["asked"].payload
