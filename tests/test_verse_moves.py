"""The fabulap's helper moves (Thym 20.9; MacroCOSM OES 18.4.6): `scan` by rule and its four `as` words, the forms
table, the checks `lines-found`, `scansion-grounded`, `sound-grounded`, `form-grounded`; `construe` by a model under
contract (a scripted coprocessor stands in for the model; nothing is recorded against a real one); `derive poem as
verse with f`; and the five-program file `defaults/thym/decompile-verse.thym`, run under rules and replayed.

The worked example is the design's (docs/v070-v1-fabulap-moves.md section 8): Dickinson's "I'm Nobody! Who are you?"
(1891, public domain). The other poems are public domain or written for these fixtures (tests/fixtures/fabula/verse/).
FEED is a fixture, `feed-forms.json` and `feed.json`: reflib/dict's own rows for every word of them. FEED holds no
contraction yet (the lexicon's lane adds them): a line with one is not scanned and says so, and `WITH_CONTRACTIONS`
stands in for the entries that lane adds, so the suite pins what `scan` reads once they arrive.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import shutil
from pathlib import Path

import pytest

from enough import macrocosm as mc
from enough import thym
from enough import thym_host as H
from enough import verse as V
from enough import verse_forms as VF
from enough.thym import Refusal
from enough.thym import checks as C
from enough.thym import plan as PL
from enough.thym import registry as R
from enough.thym import run as RUN
from enough.thym import trace as T
from enough.thym.coprocessor import candidate
from enough.thym.moves import MoveError
from enough.thym.moves import verse as MV
from enough.thym.values import Value, digest_path, read_value

REPO = Path(__file__).resolve().parents[1]
FIX = REPO / "tests" / "fixtures" / "fabula" / "verse"
SHIPPED = REPO / "defaults" / "thym"
NOW = dt.datetime(2026, 11, 12, 12, 0, tzinfo=dt.timezone.utc)
FEED = {**json.loads((FIX / "feed.json").read_text(encoding="utf-8"))["words"],
        **json.loads((FIX / "feed-forms.json").read_text(encoding="utf-8"))["words"]}
#: The entries the lexicon's lane adds for contractions (their IPA as FEED writes a monosyllable).
WITH_CONTRACTIONS = {"i'm": {"word": "i'm", "ipa": "/aɪm/"}, "don't": {"word": "don't", "ipa": "/doʊnt/"},
                     "they'd": {"word": "they'd", "ipa": "/ðeɪd/"}, "i'd": {"word": "i'd", "ipa": "/aɪd/"}}


def pron(words):
    return {w: FEED.get(w) for w in words}


def pron_c(words):
    return {w: WITH_CONTRACTIONS.get(w) or FEED.get(w) for w in words}


def text_of(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def poem_value(name: str) -> Value:
    return read_value(FIX / name, "text")


def ctx_for(tmp_path: Path, *, p=pron, **kw) -> RUN.MoveContext:
    stage = tmp_path / "stage"
    stage.mkdir(parents=True, exist_ok=True)
    base = dict(run="2026-11-12-1200-test", node={"id": "R:node/1", "step": {"n": 1}}, decls=R.read_declarations(),
                coprocessor=None, rules=False, now=NOW, emitted=[], slots={}, withheld={}, inputs_root=FIX,
                root=tmp_path, stage=stage, engines={"pron": H.pron_fields(p), "canon": H.canon_engine(),
                                                     "verse": H.verse_engine()})
    base.update(kw)
    return RUN.MoveContext(**base)


def items(v: Value) -> dict:
    return {it["id"]: it for it in mc.yaml_load(mc.dump(v.payload))["nodes"]} if isinstance(v.payload, dict) else {}


def verdict(name: str, out: Value, inputs: dict, ctx, word: str | None = None) -> tuple[bool, str]:
    node = {"modifiers": {"as": word} if word else {}}
    r = C.verdict(name, out, inputs, node, None, ctx)
    assert not isinstance(r, Refusal), r
    return r


def heard(tmp_path: Path, name: str, *, p=pron) -> tuple[RUN.MoveContext, Value, dict[str, Value]]:
    """The poem scanned with every `as` word, in the order hear-the-poem runs them; each call's value kept."""
    ctx = ctx_for(tmp_path, p=p)
    poem = poem_value(name)
    got = {"outline": MV.scan(ctx, poem)}
    prev = got["outline"]
    for word in ("rhyme", "sound", "recurrence", "form"):
        prev = got[word] = MV.scan(ctx, poem, **{"as": word, "with": prev})
    return ctx, poem, got


# ---------------------------------------------------------------------------
# The worked example: Dickinson, "I'm Nobody! Who are you?"
# ---------------------------------------------------------------------------

def test_the_outline_of_the_worked_example_as_feed_is_today(tmp_path):
    """Design 8.1: FEED holds none of I'm, don't, they'd, so three of eight lines go unscanned, each saying which
    contraction FEED lacks; the metre is read from the other five; the pauses are one device."""
    ctx = ctx_for(tmp_path)
    poem = poem_value("nobody.txt")
    out = MV.scan(ctx, poem)
    cat = out.payload
    assert (cat["flavour"], cat["derived"]["mode"], cat["derived"]["completeness"]) == ("fabulap", "rules", "outline")
    assert cat["name"] == "I'm Nobody! Who are you?" and cat["source"]["sha256"] == poem.sha256
    it = items(out)
    assert [i for i in it if i.startswith("C:part/")] == ["C:part/stanza-1", "C:part/stanza-2"]
    assert it["C:part/stanza-1"]["summary"] == "Stanza 1; lines 1-4 of the poem, 4 lines."
    for n, word in ((1, "i'm"), (3, "don't"), (4, "they'd")):
        assert it[f"C:line/{n}"]["stresses"] == {
            "pending": f'how is line {n} scanned? FEED does not hold "{word}", a contraction'}
    assert [it[f"C:line/{n}"].get("syllables") for n in (2, 5, 6, 7, 8)] == [6, 8, 6, 8, 7]
    assert not any("rhyme" in it[f"C:line/{n}"] for n in range(1, 9))         # as rhyme adds the letters
    metre = it["C:metre/mixed-metre-2-to-4-beats-a-line"]
    assert metre["lines"] == ["C:line/2", "C:line/5", "C:line/6", "C:line/7", "C:line/8"]
    assert metre["provenance"]["confidence"] == 0.39 and metre["basis"] == "accentual"
    caesura = it["C:device/caesura"]
    assert caesura["name"] == "Pauses inside lines 1, 2, 3, 4 and 6"
    assert caesura["summary"] == ('Lines 1, 2, 3, 4 and 6 pause inside, after "nobody", "nobody", "us", "us" and '
                                  '"public".')
    assert (caesura["stance"], caesura["span"], caesura["provenance"]["sources"]) == (
        "observed", {"lines": "4-10"}, ["nobody.txt#L4-L10"])
    ins = {"poem": poem}
    for name in ("lines-found", "scansion-grounded", "span-resolves", "fabula-checks"):   # provenance: the run's
        assert verdict(name, out, ins, ctx)[0], name


def test_the_worked_example_heard_by_rule_with_feed_as_it_is_and_with_contractions(tmp_path):
    """Design 8.2: as rhyme adds the letters and two rhymes, no inner rhyme; as sound finds nothing above the
    thresholds; as recurrence the anaphora of lines 5 and 6; as form common metre once FEED holds the contractions
    (six of eight lines keep 8.6.8.6), its shape until then."""
    _ctx, _poem, got = heard(tmp_path / "a", "nobody.txt")
    it = items(got["form"])
    assert [it[f"C:line/{n}"]["rhyme"] for n in range(1, 9)] == list("aabcdefe")
    assert {i for i in it if i.startswith("C:rhyme/")} == {"C:rhyme/you-too", "C:rhyme/frog-bog"}
    assert not [i for i in it if i.startswith(("C:device/alliteration", "C:device/assonance",
                                               "C:device/consonance"))]
    ana = it["C:device/anaphora-5"]
    assert (ana["name"], ana["cue"], ana["where"], ana["span"]) == (
        'Lines 5 and 6 open on "How"', "How … How", ["C:line/5", "C:line/6"], {"lines": "9-10"})
    assert ana["summary"] == 'Lines 5 and 6 both open on the word "How".' and ana["stance"] == "observed"
    assert not [i for i in it if i.startswith(("C:device/hook", "C:device/repetition", "C:device/refrain"))]
    assert it["C:form/shape"]["form"] == "two quatrains, rhymed aabc defe"
    # once FEED holds the contractions
    ctx, poem, got = heard(tmp_path / "b", "nobody.txt", p=pron_c)
    it = items(got["form"])
    assert [it[f"C:line/{n}"]["syllables"] for n in range(1, 9)] == [7, 6, 8, 6, 8, 6, 8, 7]
    assert it["C:line/1"]["stresses"] == "x / x x x x x"          # I'm is I am: function words, unstressed
    form = it["C:form/common-metre"]
    assert (form["name"], form["form"], form["stance"], form["scheme"]) == ("Common metre", "common metre",
                                                                           "deduced", "aabc defe")
    assert form["parts"] == ["C:part/stanza-1", "C:part/stanza-2"]
    assert form["metre"] == it["C:line/2"]["metre"]
    assert form["rules"] == [{"rule": "quatrains of 8, 6, 8 and 6 syllables", "held": True},
                             {"rule": "iambic", "held": False},
                             {"rule": "the second and fourth lines rhyme", "held": False}]
    assert form["departures"] == [
        {"at": "C:line/1", "what": "seven syllables where the pattern has eight"},
        {"at": "C:line/8", "what": "seven syllables where the pattern has six"},
        {"at": "C:part/stanza-1", "what": 'its second and fourth lines do not rhyme ("too", "know")'}]
    assert form["provenance"]["confidence"] == 0.33 and form["span"] == {"lines": "4-12"}
    # every call keeps its contract
    base = got["outline"]
    for word, prev in (("rhyme", base), ("sound", got["rhyme"]), ("recurrence", got["sound"]),
                       ("form", got["recurrence"])):
        ins = {"poem": poem, "with": prev}
        grounded = "form-grounded" if word == "form" else "sound-grounded"
        for name in (grounded, "nothing-lost", "fabula-checks"):
            assert verdict(name, got[word], ins, ctx, word)[0], (word, name, verdict(name, got[word], ins, ctx, word))


def test_a_fabulap_heard_by_rule_passes_the_reader_and_the_fabula_lint(tmp_path):
    from enough import fabula
    _ctx, _poem, got = heard(tmp_path, "nobody.txt", p=pron_c)
    p = tmp_path / "nobody.txt.fabulap.cosm"
    p.write_text(mc.dump(got["form"].payload), encoding="utf-8")
    vol = mc.load_volume(p)
    assert vol.refused is None and [str(e) for e in fabula.lint(vol).errors] == []


# ---------------------------------------------------------------------------
# The forms table
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name, form, held", [
    ("sonnet-116.txt", "Shakespearean sonnet", [True, True, False, None]),
    ("the-world.txt", "Petrarchan sonnet", [True, True, True, False, None]),
    ("the-house-on-the-hill.txt", "villanelle", [True, True, True, True]),
    ("old-man-with-a-beard.txt", "limerick", [True, True, False, True]),
    ("kettle.txt", "haiku", [True, True, True]),
    ("hope.txt", "common metre", None),
])
def test_the_first_form_of_the_table_that_fits_is_named(tmp_path, name, form, held):
    _ctx, _poem, got = heard(tmp_path, name)
    forms = [it for it in items(got["form"]).values() if it["type"] == "form"]
    assert len(forms) == 1 and forms[0]["form"] == form, forms
    if held is not None:
        assert [r["held"] if isinstance(r["held"], bool) else None for r in forms[0]["rules"]] == held
    assert forms[0]["provenance"]["confidence"] <= VF.FORM_CAP


def test_a_turn_the_rules_cannot_read_is_a_question_and_a_villanelle_scheme_runs_across_stanzas(tmp_path):
    _ctx, _poem, got = heard(tmp_path, "sonnet-116.txt")
    form = items(got["form"])["C:form/shakespearean-sonnet"]
    turn = form["rules"][-1]
    assert turn["rule"] == "a turn at line 13" and mc.is_pending(turn["held"])
    assert form["provenance"]["confidence"] == 0.67                # two of the three rules read by rule
    _ctx, _poem, got = heard(tmp_path / "v", "the-house-on-the-hill.txt")
    it = items(got["form"])
    assert it["C:form/villanelle"]["scheme"] == "aba aba aba aba aba abaa"
    assert [it[f"C:line/{n}"]["rhyme"] for n in (1, 2, 3, 4)] == ["a", "b", "a", "c"]   # a stanza's own letters
    assert it["C:device/refrain-1"]["where"] == ["C:line/1", "C:line/6", "C:line/12", "C:line/18"]


def test_free_verse_and_a_poem_named_by_its_shape(tmp_path):
    f = VF.Facts(n=4, parts=[("C:part/stanza-1", [1, 2, 3, 4])], syllables=dict.fromkeys(range(1, 5), 9),
                 beats=dict.fromkeys(range(1, 5), 4), norm={n: f"line {n}" for n in range(1, 5)},
                 end={n: f"w{n}" for n in range(1, 5)}, rhymes=lambda a, b: a == b, metre={"basis": "free"},
                 turns=None)
    assert VF.form_of(f)["form"] == "free verse"
    f.metre = {"basis": "accentual", "foot": "mixed"}
    assert VF.form_of(f) == {"form": "one quatrain, unrhymed", "rules": [], "departures": [],
                             "confidence": VF.SHAPE_CONFIDENCE, "named": False}
    _ctx, _poem, got = heard(tmp_path, "the-sick-rose.txt")
    assert items(got["form"])["C:form/shape"]["form"] == "two quatrains, rhymed abcb"


# ---------------------------------------------------------------------------
# A lyric: labels, repeat marks, the hook
# ---------------------------------------------------------------------------

def test_a_lyrics_labels_parts_repeats_and_hook(tmp_path):
    ctx, poem, got = heard(tmp_path, "lantern-song.txt")
    it = items(got["form"])
    assert [i for i in it if i.startswith("C:part/")] == ["C:part/verse-1", "C:part/chorus", "C:part/verse-2",
                                                          "C:part/chorus-2", "C:part/outro"]
    assert (it["C:part/chorus"]["division"], it["C:part/chorus"]["heading"]) == ("chorus", "Chorus")
    assert (it["C:part/outro"]["division"], it["C:part/outro"]["heading"]) == ("other", "Outro")
    again = it["C:part/chorus-2"]
    assert again["links"] == [{"rel": "is-a", "to": "C:part/chorus"}] and again["span"] == {"lines": "17"}
    assert "repeats the Chorus (lines 3-5)" in again["summary"]
    assert it["C:line/2"]["summary"] == "Line 2 of the poem, the second of verse 1, sung 2 times."
    assert len([i for i in it if i.startswith("C:line/")]) == 8              # labels are not lines
    hook = it["C:device/hook"]
    assert (hook["figure"], hook["stance"], hook["cue"], hook["provenance"]["confidence"]) == (
        "hook", "deduced", "Carry the light", 0.5)
    assert hook["where"] == ["C:line/3", "C:line/5", "C:line/8"]
    assert verdict("lines-found", got["outline"], {"poem": poem}, ctx)[0]
    # the bank asks the hook, and only of the hook
    from enough import dialectic as dl
    led = dl.ledger_from_items(mc.default_registry().get("fabula"), list(it.values()),
                               catalog={k: v for k, v in got["form"].payload.items() if k != "nodes"})
    hooks = [q for q in dl.raise_questions(led, pending=False, unsure=False).questions
             if q["raised"]["from"] == "fabulap/hook"]
    assert [q["about"] for q in hooks] == ["C:device/hook#intended"]
    assert hooks[0]["asks"] == 'Is "Carry the light" the hook, the line you want a listener to keep?'


def test_label_lines_and_repeat_marks():
    assert V.label_of("[Chorus]").division == "chorus" and V.label_of("Verse 2:").heading == "Verse 2"
    assert V.label_of("(Bridge)").division == "bridge" and V.label_of("[Pre-chorus] x2").repeats == 2
    assert V.label_of("[Outro]").division == "other" and V.label_of("Chorus") is None     # bare: a line of words
    assert V._repeat_mark("Row, row, row (x3)") == ("Row, row, row", 3)
    assert V._repeat_mark("x2") == ("x2", 1)


# ---------------------------------------------------------------------------
# scan's refusals and its checks catching what a scan must never write
# ---------------------------------------------------------------------------

def test_scan_refuses_what_it_cannot_do(tmp_path):
    ctx = ctx_for(tmp_path)
    poem = poem_value("nobody.txt")
    with pytest.raises(MoveError, match="scan … as rhyme adds to what scan found: scan poem as rhyme with f"):
        MV.scan(ctx, poem, **{"as": "rhyme"})
    f = MV.scan(ctx, poem)
    with pytest.raises(MoveError, match="takes no with"):
        MV.scan(ctx, poem, **{"with": f})
    prose = Value("fabula", {**f.payload, "flavour": "fabulan"})
    with pytest.raises(MoveError, match="only a fabulap"):
        MV.scan(ctx, poem, **{"as": "rhyme", "with": prose})
    with pytest.raises(MoveError, match="of another text"):
        MV.scan(ctx, poem_value("hope.txt"), **{"as": "rhyme", "with": f})


def _tamper(v: Value, iid: str, **fields) -> Value:
    doc = copy.deepcopy(v.payload)
    for it in doc["nodes"]:
        if it["id"] == iid:
            it.update(fields)
    return Value("fabula", doc)


def test_the_rules_checks_catch_what_the_rule_did_not_find(tmp_path):
    ctx, poem, got = heard(tmp_path, "nobody.txt", p=pron_c)
    ins = {"poem": poem}
    out = got["outline"]
    bad = _tamper(out, "C:line/2", stresses="x / x / x /")
    assert verdict("scansion-grounded", bad, ins, ctx)[0] is False
    gone = Value("fabula", {**out.payload, "nodes": [i for i in out.payload["nodes"] if i["id"] != "C:line/3"]})
    ok, why = verdict("lines-found", gone, ins, ctx)
    assert not ok and why == "line 3 of the poem (line 6 of the file) has no C:line"
    extra = copy.deepcopy(got["sound"].payload)
    extra["nodes"].append({"id": "C:device/alliteration-7", "type": "device", "name": "x", "summary": "x.",
                           "stance": "deduced", "figure": "alliteration", "where": ["C:line/7"], "cue": "tell",
                           "span": {"lines": "11"}, "provenance": {"mode": "derived", "sources": ["nobody.txt#L11"],
                                                                   "confidence": 0.7}})
    ok, why = verdict("sound-grounded", Value("fabula", extra), {**ins, "with": got["rhyme"]}, ctx, "sound")
    assert not ok and "is not what the rule finds" in why
    renamed = _tamper(got["form"], "C:form/common-metre", form="ballad stanza")
    ok, why = verdict("form-grounded", renamed, {**ins, "with": got["recurrence"]}, ctx, "form")
    assert not ok and "the rule reads 'common metre'" in why
    changed = _tamper(got["rhyme"], "C:line/1", ending="run-on")
    assert verdict("nothing-lost", changed, {**ins, "with": got["outline"]}, ctx)[0] is False


# ---------------------------------------------------------------------------
# construe, under contract, with a scripted model
# ---------------------------------------------------------------------------

class Scripted:
    """A coprocessor answering by move, in turn: `{move: [answer, ...]}`, every request kept."""

    def __init__(self, answers: dict) -> None:
        self.answers = {k: (v if callable(v) else list(v)) for k, v in answers.items()}
        self.sent: list[dict] = []

    def complete(self, contract, inputs, *, budget):
        self.sent.append({"move": contract.get("move"), "inputs": {k: (v[0] if isinstance(v, tuple) else v)
                                                                  for k, v in inputs.items()}})
        answer = self.answers[contract["move"]]
        if callable(answer):
            return candidate(answer(self.sent[-1]["inputs"]), engine="model:scripted", tokens=10)
        return candidate(answer.pop(0), engine="model:scripted", tokens=10)


FIGURE = """nodes:
  - {id: C:device/simile-frog, type: device, name: A somebody like a frog, summary: Being somebody is likened to a frog telling its name., stance: observed, figure: simile, cue: like a frog, where: [C:line/6], effect: a somebody croaking its own name, intended: true, span: {lines: "10"}, provenance: {mode: derived, sources: ['nobody.txt#L10'], confidence: 0.9, state: known}}
  - {id: C:device/admiring-bog, type: device, name: The admiring bog, summary: The bog admires, as a crowd would., stance: observed, figure: personification, cue: an admiring bog, where: [C:line/8], effect: the public as a bog, span: {lines: "12"}, provenance: {mode: derived, sources: ['nobody.txt#L12'], confidence: 0.9, state: known}}
  - {id: P:reading/fame-as-croaking, type: reading, name: Fame is croaking, summary: Fame is a frog croaking its own name to a bog., stance: observed, of: [C:device/simile-frog], whose: {by: author}, intended: true, grounds: [{of: C:line/6, because: like a frog}], span: {lines: "10-12"}, provenance: {mode: derived, sources: ['nobody.txt#L10-L12'], confidence: 0.9, state: known}}
  - {id: C:line/6, type: line, name: a line, summary: not the model's to write}
"""

VOICE = """nodes:
  - {id: C:voice/nobody-to-you, type: voice, name: Nobody to you, summary: A nobody speaks to a reader as to a fellow nobody., stance: deduced, perspective: mixed, tone: playful, conspiratorial, roles: {speaker: Emily Dickinson, addressee: the reader}, span: {lines: "4-7"}, provenance: {mode: derived, sources: ['nobody.txt#L4-L7'], confidence: 0.6, state: known}}
  - {id: C:voice/against-somebodies, type: voice, name: Against the somebodies, summary: The voice turns to scorn for the public somebody., stance: deduced, perspective: third, tone: exclamatory, scornful, roles: {speaker: {pending: "who speaks?"}}, span: {lines: "9-12"}, provenance: {mode: derived, sources: ['nobody.txt#L9-L12'], confidence: 0.6, state: known}}
"""

MEANING = """nodes:
  - {id: P:reading/obscurity-as-freedom, type: reading, name: Obscurity is freedom, summary: To be nobody is to be free of the public., stance: opinion, of: [C:part/stanza-1], whose: {by: model}, grounds: [{of: C:line/1, because: the boast}], span: {lines: "4-7"}, provenance: {mode: derived, sources: ['nobody.txt#L4-L7'], confidence: 0.5, state: known}}
  - {id: P:reading/fame-is-noise, type: reading, name: Fame is noise, summary: Fame is a frog's noise before a bog., stance: opinion, of: [C:part/stanza-2], whose: {by: model}, span: {lines: "9-12"}, provenance: {mode: derived, sources: ['nobody.txt#L9-L12'], confidence: 0.5, state: known}}
  - {id: P:reading/whole-poem, type: reading, name: The poem prefers being nobody, summary: The poem praises obscurity over fame., stance: opinion, of: [C:part/stanza-1, C:part/stanza-2], whose: {by: model}, span: {lines: "4-12"}, provenance: {mode: derived, sources: ['nobody.txt#L4-L12'], confidence: 0.5, state: known}}
  - {id: N:aim/praise-of-obscurity, type: aim, name: Praise of obscurity, summary: The poem may set out to praise obscurity., stance: observed, span: {lines: "4-12"}, provenance: {mode: derived, sources: ['nobody.txt#L4-L12'], confidence: 0.8, state: known}}
"""

ALLUSION = """nodes:
  - {id: I:influence/hymn-metre, type: influence, name: Hymn metre, summary: The poem may answer to the hymn's common metre., stance: observed, how: eight and six syllables, span: {lines: "4-12"}, provenance: {mode: derived, sources: ['nobody.txt#L4-L12'], confidence: 0.9, state: known}}
  - {id: I:allusion/croaking, type: allusion, name: An echo, summary: The frog may echo a fable., stance: deduced, cue: like a frog, to: Aesop, span: {lines: "10"}, provenance: {mode: derived, sources: ['nobody.txt#L10'], confidence: 0.7, state: known}}
"""


def _construe(ctx, poem, axis: str, f: Value, answer: str) -> Value:
    req = MV.construe(ctx, poem, **{"as": axis, "with": f})
    assert req.inputs["fabulap"].text() == axis and "[1] I'm nobody! Who are you?" in req.inputs["poem"].text()
    return req.parse(answer)


def test_construe_holds_a_models_reading_to_the_contract(tmp_path):
    """Thym 20.9's three laws read for verse: a reading is the model's opinion, at most 0.5, never intended; a device
    the words show is observed, cue and all, and only the author says it was meant; the speaker is never the poet on
    a model's word; an aim, an influence, an allusion's `to` the poem does not state is assumed, pending, asked; a
    model never writes an item `scan` wrote."""
    ctx, poem, got = heard(tmp_path, "nobody.txt", p=pron_c)
    f = got["form"]
    a = _construe(ctx, poem, "figure", f, FIGURE)
    it = items(a)
    sim = it["C:device/simile-frog"]
    assert (sim["stance"], sim["cue"], "intended" in sim) == ("observed", "like a frog", False)
    assert it["C:device/admiring-bog"]["stance"] == "observed"
    r = it["P:reading/fame-as-croaking"]
    assert (r["stance"], r["whose"], r["provenance"]["confidence"], "intended" in r) == (
        "opinion", {"by": "model"}, 0.5, False)
    assert it["C:line/6"] == items(f)["C:line/6"]                         # scan's line, untouched
    b = _construe(ctx, poem, "voice", a, VOICE)
    v = items(b)["C:voice/nobody-to-you"]
    assert v["roles"]["speaker"] == {"pending": "who speaks the poem: the poet, or a figure the poem makes?"}
    c = _construe(ctx, poem, "allusion", b, ALLUSION)
    inf = items(c)["I:influence/hymn-metre"]
    assert (inf["stance"], inf["provenance"]["state"], inf["provenance"]["confidence"]) == ("assumed", "pending", 0.5)
    allu = items(c)["I:allusion/croaking"]
    assert allu["roles"]["to"] == "Aesop" and allu["stance"] == "assumed"
    m = _construe(ctx, poem, "meaning", c, MEANING)
    aim = items(m)["N:aim/praise-of-obscurity"]
    assert (aim["stance"], aim["provenance"]["state"]) == ("assumed", "pending")
    for axis, before, after in (("figure", f, a), ("voice", a, b), ("allusion", b, c), ("meaning", c, m)):
        ins = {"poem": poem, "with": before}
        for name in ("span-resolves", "no-invention", "stance-kept", "coverage", "nothing-lost", "fabula-checks"):
            assert verdict(name, after, ins, ctx, axis)[0], (axis, name, verdict(name, after, ins, ctx, axis))


def test_the_verse_readings_of_the_checks_catch_what_a_model_must_never_write(tmp_path):
    ctx, poem, got = heard(tmp_path, "nobody.txt", p=pron_c)
    f = got["form"]
    a = _construe(ctx, poem, "figure", f, FIGURE)
    ins = {"poem": poem, "with": f}
    meant = _tamper(a, "P:reading/fame-as-croaking", intended=True)
    assert verdict("stance-kept", meant, ins, ctx, "figure") == (
        False, "P:reading/fame-as-croaking: only the author says whether a reading was meant")
    poet = _construe(ctx, poem, "voice", a, VOICE)
    said = _tamper(poet, "C:voice/nobody-to-you", roles={"speaker": "the poet"})
    assert verdict("stance-kept", said, {"poem": poem, "with": a}, ctx, "voice")[0] is False
    elsewhere = _tamper(a, "C:device/simile-frog", cue="like a toad")
    ok, why = verdict("no-invention", elsewhere, ins, ctx, "figure")
    assert not ok and "like a toad" in why
    # as voice gives every line to a voice; as meaning reads every stanza and the whole
    half = Value("fabula", {**poet.payload, "nodes": [i for i in poet.payload["nodes"]
                                                      if i["id"] != "C:voice/against-somebodies"]})
    assert verdict("coverage", half, {"poem": poem, "with": a}, ctx, "voice") == (False, "line 5 is in no C:voice")
    one = MEANING.split("  - ")[1]
    m = _construe(ctx, poem, "meaning", a, "nodes:\n  - " + one)
    assert verdict("coverage", m, {"poem": poem, "with": a}, ctx, "meaning") == (
        False, "C:part/stanza-2 is read by no reading")


def test_a_reply_that_is_not_yaml_is_asked_again(tmp_path):
    ctx, poem, got = heard(tmp_path, "nobody.txt")
    req = MV.construe(ctx, poem, **{"as": "turn", "with": got["form"]})
    with pytest.raises(ValueError, match="nodes"):
        req.parse("just prose about the poem")
    assert items(req.parse("nodes: []")) == items(got["form"])          # a poem need hold no turn


def test_construe_refuses_without_its_axis_or_its_fabulap(tmp_path):
    ctx = ctx_for(tmp_path)
    poem = poem_value("nobody.txt")
    f = MV.scan(ctx, poem)
    with pytest.raises(MoveError, match="construe names one axis"):
        MV.construe(ctx, poem, **{"with": f})
    with pytest.raises(MoveError, match="construe takes the fabulap so far"):
        MV.construe(ctx, poem, **{"as": "figure"})


AMBIGUITY = """nodes:
  - {id: L:term/banish, type: term, name: banish, summary: To send away., sense: {pending: "which sense: to exile, or to shun?"}, span: {lines: "7"}, provenance: {mode: derived, sources: ['nobody.txt#L7'], confidence: 0.6, state: known}}
  - {id: P:reading/they-are-everyone, type: reading, name: They are everyone, summary: They are everyone., stance: opinion, of: [C:line/4], whose: {by: model}, span: {lines: "7"}, provenance: {mode: derived, sources: ['nobody.txt#L7'], confidence: 0.4, state: known}}
"""


def test_a_long_poem_is_construed_by_stanzas_and_its_words_are_grounded_in_feed(tmp_path, monkeypatch):
    """Thym 20.9: a poem longer than one request is read by stanzas, one request each, keyed in turn; a word a
    reading names is grounded in FEED (`terms-grounded`)."""
    monkeypatch.setattr(MV, "CONSTRUE_CHARS", 120)
    ctx, poem, got = heard(tmp_path, "nobody.txt", p=pron_c)
    ctx.engines["feed"] = lambda ws: {w: FEED.get(w.lower()) for w in ws}
    sent = []

    def ask(contract, inputs, *, budget=None):
        sent.append({k: v.text() for k, v in inputs.items()})
        return candidate(AMBIGUITY if len(sent) == 1 else "nodes: []", engine="model:scripted", tokens=5)
    ctx.ask = ask
    out = MV.construe(ctx, poem, **{"as": "ambiguity", "with": got["form"]})
    assert isinstance(out, Value) and [s["part"] for s in sent] == ["1 of 2", "2 of 2"]
    assert "[5] How dreary to be somebody!" in sent[1]["poem"] and "[5]" not in sent[0]["poem"]
    term = items(out)["L:term/banish"]
    assert term["feed"] == {"word": "banish", "pos": "verb", "origin": "feed"} and mc.is_pending(term["sense"])
    assert verdict("terms-grounded", out, {"poem": poem, "with": got["form"]}, ctx, "ambiguity")[0]


def test_the_prompts_are_the_axis_and_stay_small():
    from enough import fabulap_prompts as FP
    for axis in FP.AXES:
        sys_ = FP.system_for(axis, "nobody.txt")
        assert len(sys_) < 3000 and "nobody.txt#La-Lb" in sys_ and "never" in sys_.lower()
    msgs = FP.construe_messages({}, {"fabulap": (Value("string", "voice"), ""), "poem": (Value("string", "1| x"), ""),
                                    "lines": (Value("string", "1-1"), ""), "outline": (Value("string", "- x"), ""),
                                    "source": (Value("string", "p.txt"), "")})
    assert "Never write that the poet speaks" in msgs[0]["content"] and "1| x" in msgs[1]["content"]
    assert FP.construe_messages({}, {"fabulac": (Value("string", "read"), "")}) is None


# ---------------------------------------------------------------------------
# The five-program file, run under rules and with a scripted model, and replayed
# ---------------------------------------------------------------------------

def _plan(tmp_path: Path, program: str, rows: dict[str, tuple[str, Path]]):
    checked = thym.check_file(SHIPPED / "decompile-verse.thym")
    assert not isinstance(checked, Refusal), checked
    ins = [{"name": n, "type": t, "path": str(p), "sha256": digest_path(p)} for n, (t, p) in rows.items()]
    got = PL.plan(checked, ins, program=program)
    assert not isinstance(got, Refusal), got
    return got


def _engines(p=pron) -> dict:
    return {**H.engines(feed=None), "pron": H.pron_fields(p)}


def test_the_five_programs_scan_and_hear_a_poem_under_rules_and_replay(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    shutil.copy(FIX / "nobody.txt", work / "nobody.txt")
    pl = _plan(work, "scan-the-poem", {"poem": ("text", work / "nobody.txt")})
    t = RUN.run(pl, inputs_root=work, root=tmp_path / "root", program=SHIPPED / "decompile-verse.thym", rules=True,
                engines=_engines(pron_c), now=NOW)
    assert isinstance(t, T.Trace) and t.landed, getattr(t, "refusal", t)
    f = work / "nobody.fabulap.cosm"
    shutil.copy(t.outputs["f"], f)
    pl2 = _plan(work, "hear-the-poem", {"poem": ("text", work / "nobody.txt"), "f": ("fabula", f)})
    t2 = RUN.run(pl2, inputs_root=work, root=tmp_path / "root2", program=SHIPPED / "decompile-verse.thym",
                 rules=True, engines=_engines(pron_c), now=NOW)
    assert isinstance(t2, T.Trace) and t2.landed, t2
    got = mc.yaml_load(t2.outputs["g"].read_text(encoding="utf-8"))
    ids = [n["id"] for n in got["nodes"]]
    assert "C:form/common-metre" in ids and "C:device/anaphora-5" in ids
    assert [r["program"] for r in got["derived"]["runs"]] == ["scan-the-poem"] + ["hear-the-poem"] * 4
    again = RUN.replay(t2.dir, root=tmp_path / "again", inputs_root=work)
    assert isinstance(again, T.Trace) and again.replay["identical"], again


def test_rules_runs_no_model_and_refuses_read_closely_at_plan_time(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    shutil.copy(FIX / "nobody.txt", work / "nobody.txt")
    pl = _plan(work, "scan-the-poem", {"poem": ("text", work / "nobody.txt")})
    t = RUN.run(pl, inputs_root=work, root=tmp_path / "root", program=SHIPPED / "decompile-verse.thym", rules=True,
                engines=_engines(), now=NOW)
    shutil.copy(t.outputs["f"], work / "f.cosm")
    pl2 = _plan(work, "read-closely", {"poem": ("text", work / "nobody.txt"), "f": ("fabula", work / "f.cosm")})
    t2 = RUN.run(pl2, inputs_root=work, root=tmp_path / "root2", program=SHIPPED / "decompile-verse.thym", rules=True,
                 engines=_engines(), now=NOW)
    assert isinstance(t2, Refusal) and t2.check == "rules" and "--rules runs no model" in t2.message, t2


def test_read_closely_with_a_scripted_model(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    shutil.copy(FIX / "nobody.txt", work / "nobody.txt")
    _ctx, _poem, got = heard(tmp_path, "nobody.txt", p=pron_c)
    (work / "f.cosm").write_text(mc.dump(got["form"].payload), encoding="utf-8")
    turn = ('nodes:\n  - {id: C:device/turn-5, type: device, name: The turn at line 5, summary: The poem turns from '
            'the pact to scorn., stance: deduced, figure: turn, cue: How dreary, where: [C:line/5], effect: from a '
            'whispered pact to scorn, span: {lines: "8"}, provenance: {mode: derived, sources: [\'nobody.txt#L8\'], '
            'confidence: 0.6, state: known}}\n')
    ambiguity = ('nodes:\n  - {id: P:reading/they-are-the-somebodies, type: reading, name: They are the somebodies, '
                 'summary: They who would banish are the somebodies., stance: opinion, of: [C:line/4], whose: {by: '
                 'model}, span: {lines: "7"}, provenance: {mode: derived, sources: [\'nobody.txt#L7\'], confidence: '
                 '0.4, state: known}}\n  - {id: P:reading/they-are-everyone, type: reading, name: They are everyone, '
                 'summary: They are everyone., stance: opinion, of: [C:line/4], whose: {by: model}, span: {lines: '
                 '"7"}, provenance: {mode: derived, sources: [\'nobody.txt#L7\'], confidence: 0.4, state: known}}\n')
    cp = Scripted({"construe": [FIGURE, "nodes: []", ALLUSION, VOICE, turn, MEANING, ambiguity]})
    pl = _plan(work, "read-closely", {"poem": ("text", work / "nobody.txt"), "f": ("fabula", work / "f.cosm")})
    t = RUN.run(pl, inputs_root=work, root=tmp_path / "root", program=SHIPPED / "decompile-verse.thym",
                coprocessor=cp, engines=_engines(pron_c), now=NOW)
    assert isinstance(t, T.Trace) and t.landed, getattr(t, "refusal", t)
    assert [s["inputs"]["fabulap"].text() for s in cp.sent] == list(MV.CONSTRUE_AS)
    out = {n["id"]: n for n in mc.yaml_load(t.outputs["g"].read_text(encoding="utf-8"))["nodes"]}
    assert out["C:device/turn-5"]["figure"] == "turn" and "P:reading/they-are-everyone" in out
    again = RUN.replay(t.dir, root=tmp_path / "again", inputs_root=work)
    assert isinstance(again, T.Trace) and again.replay["identical"], again


SENSE = """nodes:
  - {id: L:term/livelong, type: term, name: livelong, summary: Whole, from end to end., sense: the whole of the day, span: {lines: "11"}, provenance: {mode: derived, sources: ['nobody.txt#L11'], confidence: 0.8, state: known}}
  - {id: E:thing/frog, type: thing, name: frog, summary: A frog., span: {lines: "10"}, provenance: {mode: derived, sources: ['nobody.txt#L10'], confidence: 0.9, state: known}}
  - {id: C:device/should-not-be-here, type: device, name: x, summary: x., stance: observed, figure: simile, span: {lines: "10"}, provenance: {mode: derived, sources: ['nobody.txt#L10'], confidence: 0.9, state: known}}
  - {id: X:atem/1, type: atem, name: The poem, summary: A nobody boasts., line: A nobody invites another to share being nobody and scorns the public somebody croaking its name to a bog, focus: Obscurity against fame., push: The pact., pull: The bog., span: {lines: "4-12"}, provenance: {mode: derived, sources: ['nobody.txt#L4-L12'], confidence: 0.6, state: known}}
  - {id: R:maker/emily-dickinson, type: maker, name: Emily Dickinson, summary: The header names Emily Dickinson as the poet., stance: observed, capacity: author, span: {lines: "1-2"}, provenance: {mode: derived, sources: ['nobody.txt#L1-L2'], confidence: 0.9, state: known}}
  - {id: R:release/poems-second-series, type: release, name: Poems, Second Series, summary: The header names Poems, Second Series, 1891., stance: observed, venue: Poems, Second Series, at: '1891', span: {lines: "2"}, provenance: {mode: derived, sources: ['nobody.txt#L2'], confidence: 0.9, state: known}}
"""
ATEM = ("line: A nobody invites another nobody into a secret pact and scorns the public somebody who croaks its "
        "name all day\nfocus: Obscurity praised against fame.\npush: The pact.\npull: The bog.\n")


def test_derive_as_verse_with_a_fabulap_reads_only_what_the_poem_says(tmp_path):
    """Thym 20.9: with `with f`, derive reads the sense (terms, names, ideas, claims, events, atems) against the
    outline, and leaves figures to construe; nothing of the fabulap changes; under rules, its scaffold adds the
    rules twin's words and names."""
    work = tmp_path / "work"
    work.mkdir()
    shutil.copy(FIX / "nobody.txt", work / "nobody.txt")
    _ctx, _poem, got = heard(tmp_path, "nobody.txt", p=pron_c)
    (work / "f.cosm").write_text(mc.dump(got["form"].payload), encoding="utf-8")
    def by_ask(ins: dict) -> str:                   # a passage (or its repair), then the whole poem's atem
        return ATEM if "You write the atem" in ins["messages"].text() else SENSE
    cp = Scripted({"derive": by_ask})
    pl = _plan(work, "read-the-poem", {"poem": ("text", work / "nobody.txt"), "f": ("fabula", work / "f.cosm")})
    t = RUN.run(pl, inputs_root=work, root=tmp_path / "root", program=SHIPPED / "decompile-verse.thym",
                coprocessor=cp, engines=_engines(pron_c), now=NOW)
    assert isinstance(t, T.Trace) and t.landed, getattr(t, "refusal", t)
    doc = mc.yaml_load(t.outputs["g"].read_text(encoding="utf-8"))
    ids = {n["id"] for n in doc["nodes"]}
    assert {"L:term/livelong", "E:thing/frog", "R:maker/emily-dickinson", "C:form/common-metre"} <= ids
    assert "C:device/should-not-be-here" not in ids
    assert doc["derived"]["completeness"] == "full" and doc["atem"]["line"].startswith("A nobody invites")
    system = cp.sent[0]["inputs"]["messages"].text()
    assert "for what it says" in system and "No devices, no voice, no readings" in system
    # rules: the scaffold
    t2 = RUN.run(pl, inputs_root=work, root=tmp_path / "root2", program=SHIPPED / "decompile-verse.thym",
                 rules=True, engines=_engines(pron_c), now=NOW)
    assert isinstance(t2, T.Trace) and t2.landed, getattr(t2, "refusal", t2)
    ruled = {n["id"] for n in mc.yaml_load(t2.outputs["g"].read_text(encoding="utf-8"))["nodes"]}
    assert "C:form/common-metre" in ruled and any(i.startswith("L:term/") for i in ruled)


# ---------------------------------------------------------------------------
# The compiler: the two moves reserved and declared in thym 1, and what it refuses before a run
# ---------------------------------------------------------------------------

def _compile(body: str, takes: str = "poem: text", gives: str = "g: fabula"):
    from enough.thym import check as ck
    from enough.thym import declarations as dc
    from enough.thym import parse as ps
    text = f"thym 1\n\nprogram p\n  takes {takes}\n  gives {gives}\n\n{body}end\n"
    decls = dc.load()
    m = ps.parse(text, moves=set(decls.view(1)))
    return m if isinstance(m, Refusal) else ck.check(m, decls=decls)


@pytest.mark.parametrize("body, check, words", [
    ("  give scan poem as rhyme\n", "type", "scan … as rhyme adds to what scan found: scan poem as rhyme with f"),
    ("  let f = scan poem\n  give scan poem with f\n", "type", "takes no with"),
    ("  let f = scan poem\n  give construe poem with f\n", "type", "construe names its axis"),
    ("  let f = derive poem as prose\n  give construe poem as figure with f\n", "flavour",
     "f is a fabulan, the fabula of a text; only a fabulap, a poem's fabula, is taken by construe … with"),
    ("  let f = derive poem as prose\n  give scan poem as form with f\n", "flavour", "only a fabulap"),
    ("  let f = derive poem\n  give derive poem as verse with f\n", "flavour", "only a fabulap"),
    ("  give scan poem as metre with poem\n", "type", None),
])
def test_the_compiler_refuses_a_helper_call_it_can_see_is_wrong(body, check, words):
    r = _compile(body)
    assert isinstance(r, Refusal) and r.check == check, r
    if words:
        assert words in r.message, r.message


def test_scan_and_construe_are_thym_1_moves_and_reserved_there():
    from enough.thym import declarations as dc
    d = dc.load()
    assert d["scan"].since == 1 and d["construe"].since == 1 and d["construe"].view(1).asks is True
    assert d["scan"].view(0) is None and d["scan"].view(1).scaffold is None and not d["scan"].view(1).asks
    assert dc.chosen(d["scan"].view(1), as_word="form")["contract"] == ("form-grounded", "nothing-lost",
                                                                         "fabula-checks", "provenance")
    assert dc.chosen(d["derive"].view(1), as_word="verse", with_type="fabula")["contract"][-1] == "nothing-lost"
    assert "nothing-lost" not in dc.chosen(d["derive"].view(1), as_word="verse")["contract"]
    ok = _compile("  let f = scan poem\n  let g2 = scan poem as rhyme with f\n"
                  "  give construe poem as ambiguity with g2\n")
    assert not isinstance(ok, Refusal), ok
    clash = _compile("  let scan = 1\n  give derive poem as verse\n")
    assert isinstance(clash, Refusal), "scan is a move's name in thym 1, never a binding"
