"""Thym's standard moves and the checks they carry (docs/THYM.md 6.3, 7.3, 13 to 16, 18, 19): `enough/thym/moves/`.

Every deterministic move runs on the conformance fixtures. Every model-backed move runs against a `FakeCoprocessor`
(the runtime's own test fake, `tests/test_thym_run.py`) whose candidates are written here by hand: Canon's passage
answer and whole-text atem for the orchard text, a cited null telling, a judgement of three scales, an atem, an
expansion, a reading, a morph's telling. For each contract check one candidate passes and one fails, and the run is
refused with the check's name; where a move's own narrow repair makes a failure unreachable through the run (a
span outside the text, a stance word), the check is held to it directly. `open-house` over the sample Holotype lands
exactly `expected/open-house/outputs/`; `publish-story` and `read-my-way` run end to end; `--rules` runs the
scaffolds; a recorded run replays byte for byte. Runs land in a tmp root (conftest's seam); no model is started.
"""
from __future__ import annotations

import ast
import datetime as dt
import hashlib
import shutil
from pathlib import Path

import pytest

from enough import macrocosm as mc
from enough import thym_host as H
from enough.thym import Refusal, conform
from enough.thym import checks as C
from enough.thym import plan_file
from enough.thym import registry as R
from enough.thym import run as RUN
from enough.thym import trace as T
from enough.thym import moves as M
from enough.thym.moves import edit, emf, morph, pack, project
from enough.thym.registry import Amount, Request
from enough.thym import values as V
from enough.thym.values import NOTHING, Value, digest_path, read_value
from tests.test_thym_run import FakeCoprocessor, hand_plan, lint_errors, node

REPO = Path(__file__).resolve().parents[1]
SUITE = REPO / "tests" / "fixtures" / "thym"
NOTES = SUITE / "inputs" / "notes.md"
TWIN = SUITE / "inputs" / "notes.md.cosm"
PACKAGE = SUITE / "inputs" / "orchard-notes.thym"
MORPH = SUITE / "inputs" / "plain-letter.morph.cosm"
OUTPUTS = SUITE / "expected" / "open-house" / "outputs"
NOW = dt.datetime(2026, 11, 1, 12, 0, tzinfo=dt.timezone.utc)
sha = digest_path


def load(rel: str) -> dict:
    return mc.yaml_load((SUITE / rel).read_text(encoding="utf-8"))


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "thym-root"


@pytest.fixture(scope="module")
def engines() -> dict:
    return H.engines(feed=None)


def ctx_for(tmp_path: Path, engines: dict | None = None, **kw):
    """A move context outside a run, for calling a move or a check directly."""
    stage = tmp_path / "stage"
    stage.mkdir(parents=True, exist_ok=True)
    base = dict(run="2026-11-01-1200-test", node={"id": "R:node/1", "step": {"n": 1}}, decls=R.read_declarations(),
                coprocessor=None, rules=False, now=NOW, emitted=[], slots={}, withheld={}, inputs_root=SUITE,
                root=tmp_path, stage=stage, engines=engines or {})
    base.update(kw)
    return RUN.MoveContext(**base)


def verdict(name: str, out: Value, inputs: dict | None = None, node_: dict | None = None, ctx=None):
    return C.verdict(name, out, inputs or {}, node_ or {}, None, ctx)


# ---------------------------------------------------------------------------
# Hand-written candidates for the orchard text
# ---------------------------------------------------------------------------

PASSAGE = """nodes:
  - id: P:claim/bramley-oldest
    type: claim
    name: Bramley oldest
    summary: "Mara Okafor says the old Bramley by the gate is the oldest tree on Hollins Lane; the parish records do not confirm it."
    stance: hearsay
    salience: low
    roles: {source: E:person/mara-okafor}
    span: {lines: "3-5"}
  - id: P:claim/apples-need-second-variety
    type: claim
    name: apples need second variety
    summary: "Every apple tree needs a second variety nearby to set fruit, as the nursery leaflet says."
    stance: axiom
    salience: high
    span: {lines: "7-8"}
  - id: P:claim/juice-rose
    type: claim
    name: juice rose
    summary: "The Hollins Lane orchard pressed 140 litres of juice this year, up from 90 litres last year."
    stance: observed
    salience: critical
    span: {lines: "10-11"}
  - id: P:claim/mulch-made-difference
    type: claim
    name: mulch made difference
    summary: "Mara Okafor holds that the leaf mould made the difference to the yield."
    stance: opinion
    salience: high
    roles: {holder: E:person/mara-okafor}
    span: {lines: "13-14"}
  - id: P:claim/spring-explains-rise
    type: claim
    name: spring explains rise
    summary: "A warm, wet spring would explain most of the rise, because every orchard in the valley did well."
    stance: deduced
    salience: high
    span: {lines: "14-15"}
    links: [{rel: contradicts, to: P:claim/mulch-made-difference}]
  - id: P:claim/july-mowing-harms-orchard
    type: claim
    name: July mowing harms orchard
    summary: "Mowing the meadow strip in July would cut the wildflowers before they seed and starve the pollinators the orchard depends on."
    stance: deduced
    salience: critical
    span: {lines: "17-20"}
    links: [{rel: depends-on, to: P:claim/apples-need-second-variety}]
  - id: T:event/leaf-mould-spread
    type: event
    name: leaf mould spread
    summary: "The volunteers spread leaf mould under the trees in March."
    when: March
    span: {lines: "13"}
  - id: T:event/council-asked-to-wait
    type: event
    name: council asked to wait
    summary: "The orchard agreed to ask the parish council to wait until September; Mara Okafor will write the letter."
    when: September
    span: {lines: "22-23"}
  - id: E:person/mara-okafor
    type: person
    name: Mara Okafor
    summary: "Mara Okafor has kept the Hollins Lane orchard since 2019."
    span: {lines: "3"}
  - id: E:org/parish-council
    type: org
    name: parish council
    summary: "The parish council, whose grounds team wants to mow the meadow strip."
    span: {lines: "17"}
  - id: X:atem/1
    type: atem
    name: passage atem
    summary: "The orchard's year and the mowing date."
    line: "The orchard pressed more juice this year, and mowing the strip in July would starve its pollinators."
    focus: "A good year and a mowing date."
    push: "Ask the council to wait until September."
    pull: "The cause of the rise is unsettled."
    span: {lines: "3-23"}
"""



def _without(text: str, *ids: str) -> str:
    blocks = text.split("\n  - id: ")
    return "\n  - id: ".join(b for b in blocks if not any(b.startswith(i) for i in ids))


# The mowing claim and the letter are in no item: lines 18 to 23 are uncovered.
PASSAGE_SHORT = _without(PASSAGE, "P:claim/july-mowing-harms-orchard", "T:event/council-asked-to-wait")

WHOLE_ATEM = """line: "The orchard pressed more juice this year for reasons still argued over, and mowing the meadow strip in July would starve its pollinators."
focus: "A good year for a small orchard, and a mowing date that could undo it."
push: "Ask the parish council to wait until September before mowing the meadow strip."
pull: "Whether the leaf mould or a wet spring raised the yield is unsettled, and the mowing claim leans on cross-pollination."
stance_profile: {axiom: 1, observed: 1, deduced: 2, opinion: 1, assumed: 0, hearsay: 1}
"""


def null_answer(*extra: dict) -> dict:
    rows = [
        {"say": "Mara Okafor says the old Bramley is the oldest tree.",
         "cites": ["P:claim/bramley-oldest", "E:person/mara-okafor"]},
        {"say": "Every apple tree needs a second variety to set fruit.",
         "cites": ["P:claim/apples-need-second-variety"]},
        {"say": "The orchard pressed 140 litres of juice this year.", "cites": ["P:claim/juice-rose"]},
        {"say": "Last year it pressed 90 litres.", "cites": ["P:claim/juice-rose"]},
        {"say": "The leaf mould was spread in March.", "cites": ["T:event/leaf-mould-spread"]},
        {"say": "Mara Okafor holds that the leaf mould made the difference.",
         "cites": ["P:claim/mulch-made-difference"]},
        {"say": "It follows that a wet spring would explain most of the rise.",
         "cites": ["P:claim/spring-explains-rise"]},
        {"say": "It follows that mowing the strip in July would harm the orchard.",
         "cites": ["P:claim/july-mowing-harms-orchard"]},
        {"say": "The orchard will ask the parish council to wait until September.",
         "cites": ["T:event/council-asked-to-wait", "E:org/parish-council"]},
    ]
    return {"sentences": rows + list(extra)}


JUDGED = {"figurative": [], "humour": [], "allusion": []}


def run_publish(root: Path, engines: dict, answers: dict, **kw):
    cp = FakeCoprocessor(answers)
    kw.setdefault("now", NOW)
    t = RUN.run(load("expected/publish-story/plan.cosm"), inputs_root=SUITE, root=root, coprocessor=cp,
                program=SUITE / "programs" / "publish-story.thym", engines=engines, **kw)
    return t, cp


# ---------------------------------------------------------------------------
# The registry: every declared move, scaffold and check is here, and the package imports only what it may
# ---------------------------------------------------------------------------

def test_every_declared_move_scaffold_and_check_is_implemented():
    decls = R.read_declarations()
    assert len(decls) >= 26
    for name, d in decls.items():
        assert R.MOVES.lookup(name) is not None, name
        if d.get("scaffold"):
            assert R.MOVES.scaffold(d) is not None, name
        for chk in d.get("contract") or []:
            assert C.CHECKS.lookup(chk) is not None, (name, chk)
        assert R.resolve(d["code"]) is not None, d["code"]
    assert {"derive", "tell", "null", "expand", "atem", "measure", "morph", "read"} <= {
        n[:-len(".prompt")] for n in R.MOVES.names() if n.endswith(".prompt")}


def test_the_moves_import_only_what_the_package_may():
    allowed = ("enough.thym", "enough.macrocosm")
    for p in sorted((REPO / "enough" / "thym" / "moves").glob("*.py")):
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("enough"):
                assert n.module.startswith(allowed) or (n.module == "enough" and all(
                    a.name == "macrocosm" for a in n.names)), (p.name, n.module)
            if isinstance(n, ast.Import):
                assert not any(a.name.startswith("enough") and not a.name.startswith(allowed) for a in n.names)


def _feed_rows(word: str) -> bool:
    """A FEED headword, read from the shipped text form (reflib/dict), which needs no built dictionary."""
    src = REPO / "reflib" / "dict" / "words" / f"{word[0]}.jsonl"
    data = src.read_bytes()
    at = data.find(f'{{"word": "{word}", '.encode())
    if at < 0:
        return False
    end = data.find(b"\n", at)
    return b'"is_headword": 1' in data[at:end]


def test_every_word_a_statistic_counts_is_a_feed_headword():
    words = {w for ws in morph.WORD_LISTS.values() for w in ws}
    assert {"maybe", "seem", "okay", "utilise", "commence", "accordance"} <= words
    missing = sorted(w for w in words if not _feed_rows(w))
    assert missing == [], missing
    forms = REPO / "reflib" / "dict" / "forms"
    for head, fs in morph.FORMS.items():
        text = (forms / f"{head[0]}.jsonl").read_text(encoding="utf-8")
        for f in fs:
            assert f'"headword": "{head}", "form": "{f}"' in text, (head, f)


# ---------------------------------------------------------------------------
# Sentences, coverage and the stance ladder
# ---------------------------------------------------------------------------

def test_the_sentence_rule_and_claim_bearing_sentences():
    sents = M.segment(NOTES.read_text(encoding="utf-8"), footer=True)
    assert sents[0].kind == "heading" and sents[0].first == 1
    bearing = [s for s in sents if M.claim_bearing(s)]
    assert len(bearing) == 14
    assert bearing[0].first == 3 and bearing[0].last == 4
    assert bearing[-1].text.startswith("Mara will write the letter")
    assert (bearing[-1].first, bearing[-1].last) == (22, 23)
    assert not any(s.text.startswith("Open question") for s in bearing)
    assert M.segment("Dr. Okafor came. She left.\n") == [M.Sentence("Dr. Okafor came.", 1, 1, 0),
                                                         M.Sentence("She left.", 1, 1, 0)]
    md = "---\nread_through: x\n---\n\nOne two three.\n\n*read through x*\n*a reading of y*\n"
    assert [s.text for s in M.segment(md)] == ["One two three."] and M.segment(md)[0].first == 5


def test_coverage_is_one_computation_for_the_check_and_the_assert(tmp_path):
    story, twin = read_value(NOTES, "text"), read_value(TWIN, "fabula")
    ok, why = verdict("coverage", story, {"f": twin})          # as `assert f covers story` asks it
    assert not ok and "We agreed to ask the council" in why    # the hand twin has no item for the agreement
    data = mc.yaml_load(TWIN.read_text(encoding="utf-8"))
    data["nodes"].append({"id": "T:event/letter-agreed", "type": "event", "name": "the letter agreed",
                          "summary": "The orchard agreed to ask the council to wait until September.",
                          "span": {"lines": "22-23"}, "provenance": {"mode": "manual", "sources": ["notes.md#L22"]}})
    fab = Value("fabula", data)
    ok, why = verdict("coverage", story, {"f": fab})
    assert ok and why.startswith("14 claim-bearing sentences, each traced (spans)") and "T:event/letter-agreed" in why
    cm = M.cover_map(fab, story)
    assert cm.how == "spans" and cm.record()[0] == {"sentence": 1, "lines": "3-4", "items": [
        "E:person/mara-okafor", "E:place/hollins-lane-orchard", "E:thing/bramley-by-the-gate",
        "P:claim/bramley-is-oldest"]}


def test_telling_stance_reads_the_weakest_marker():
    assert M.telling_stance("The orchard pressed 140 litres.") == "observed"
    assert M.telling_stance("Reportedly, the Bramley is the oldest tree.") == "hearsay"
    assert M.telling_stance("Mara thinks the mulch helped, because the spring was wet.") == "opinion"
    assert M.telling_stance("It follows that mowing would harm the orchard.") == "deduced"
    assert M.telling_stance("It is taken as given that apples need a second variety.") == "axiom"
    assert M.telling_stance("Perhaps the strip feeds the bees.") == "hearsay"


# ---------------------------------------------------------------------------
# The plain moves
# ---------------------------------------------------------------------------

def test_count_words_digest_lint_and_trace(tmp_path, engines):
    ctx = ctx_for(tmp_path, engines)
    twin, story = read_value(TWIN, "fabula"), read_value(NOTES, "text")
    meadow = read_value(SUITE.parent / "cosm" / "holotypes" / "meadow", "volume")
    assert edit.count(ctx, twin).payload == 21
    assert edit.count(ctx, meadow).payload == 36
    assert edit.count(ctx, Value("list", [Value("number", 1), Value("number", 2)])).payload == 2
    assert edit.words(ctx, story).payload == C.words(NOTES.read_text(encoding="utf-8"))
    assert edit.words(ctx, Value("short", "One two three.\n\n*a short of x*\n")).payload == 3
    assert edit.words(ctx, Value("atem", {"line": "four words are here"})).payload == 4
    assert edit.digest(ctx, story).payload == hashlib.sha256(NOTES.read_bytes()).hexdigest()
    rep = edit.lint(ctx, twin).payload
    assert rep["ok"] is True and rep["minicosm"] == "emf/1" and rep["errors"] == []
    bad = edit.lint(ctx, Value("volume", {"oes": "emf/1", "id": "emf/x", "name": "x",
                                          "nodes": [{"id": "P:claim/x", "type": "claim"}]})).payload
    assert bad["ok"] is False and bad["errors"]
    ctx.trace_fn = lambda: {"oes": "thym/1", "kind": "trace"}
    assert edit.trace(ctx).type == "trace"


def _cited_short(fab: Value) -> Value:
    sents = ["The Bramley by the gate is reportedly the oldest tree on Hollins Lane.",
             "The orchard pressed 140 litres of juice this year.",
             "Mara Okafor holds that the leaf mould raised the yield.",
             "Mowing the meadow strip in July would starve the pollinators."]
    covers = [["P:claim/bramley-is-oldest"], ["P:claim/juice-rose-to-140-litres"],
              ["P:claim/mulch-raised-the-yield"], ["P:claim/july-mowing-harms-the-orchard"]]
    text = " ".join(sents[:2]) + "\n\n" + " ".join(sents[2:]) + "\n\n*a short of notes.md, told as the author told " \
        "it, compiled from its EMF twin on 2026-11-01 by a model*\n"
    return M.short_value(text, fabula=fab, sentences=sents, covers=covers, order="told")


def test_cut_removes_the_lightest_sentences_first(tmp_path):
    ctx = ctx_for(tmp_path)
    fab = read_value(TWIN, "fabula")
    s = _cited_short(fab)
    out = edit.cut(ctx, s, to=Amount(2, "sentences"))
    body = C.body(out.text())
    assert body == ("The orchard pressed 140 litres of juice this year.\n\n"
                    "Mowing the meadow strip in July would starve the pollinators.")
    assert out.text().rstrip().endswith("by a model*")              # the footer stays
    assert M.telling_of(out)["covers"] == [["P:claim/juice-rose-to-140-litres"],
                                           ["P:claim/july-mowing-harms-the-orchard"]]
    inputs = {"s": s}
    for name in ("whole-sentences", "weight-order", "coverage"):
        assert verdict(name, out, inputs)[0], name
    worse = M.short_value(C.sentences(C.body(s.text()))[0] + "\n", fabula=fab,
                          sentences=[M.telling_of(s)["sentences"][0]], covers=[["P:claim/bramley-is-oldest"]])
    ok, why = verdict("weight-order", worse, inputs)
    assert not ok and "critical sentence was removed while a low one was kept" in why
    words = edit.cut(ctx, s, to=Amount(25, "words"))
    assert C.words(C.body(words.text())) <= 25
    with pytest.raises(M.MoveError):
        edit.cut(ctx, s, to=Amount(1, "words"))


# ---------------------------------------------------------------------------
# Projection: band, mark, withhold, project and Comprise's rules
# ---------------------------------------------------------------------------

def test_band_mark_and_withhold(tmp_path):
    ctx = ctx_for(tmp_path)
    assert project.band(ctx, Value("number", 0), **{"as": ["none", "some"]}).payload == "none"
    assert project.band(ctx, Value("number", 3), **{"as": ["none", "some"]}).payload == "some"
    assert [project.band(ctx, Value("number", n), **{"as": ["few", "several", "many"]}).payload
            for n in (0, 9, 10, 19, 20, 500)] == ["few", "few", "several", "several", "many", "many"]
    w = project.band(ctx, Value("number", 0), **{"as": ["none", "some"]})
    assert verdict("banded", w, node_={"modifiers": {"as": ["none", "some"]}})[0]
    assert not verdict("banded", Value("word", "lots"), node_={"modifiers": {"as": ["none", "some"]}})[0]
    marked = project.mark(ctx, w, **{"as": "verified"})
    assert marked.payload == "none" and project.marking_of(marked) == "verified"
    assert verdict("verified-only-where-derived", marked, node_={"slot": "employees",
                                                                  "modifiers": {"as": "verified"}})[0]
    assert not verdict("verified-only-where-derived", project.mark(ctx, Value("word", "x"), **{"as": "verified"}),
                       node_={"modifiers": {"as": "verified"}})[0]
    meadow = read_value(SUITE.parent / "cosm" / "holotypes" / "meadow", "volume")
    rows = {r.origin["id"]: r for r in RUN.members(meadow)}
    offer = project.mark(ctx, rows["P:service/reconcile"], **{"as": "verified"})
    assert offer.payload["marking"] == "verified"
    assert verdict("verified-only-where-derived", offer, node_={"modifiers": {"as": "verified"}})[0]
    vendor = project.mark(ctx, rows["S:vendor/stripe"], **{"as": "verified"})
    ok, why = verdict("verified-only-where-derived", vendor, node_={"modifiers": {"as": "verified"}})
    assert not ok and "does not derive a vendor" in why
    claim = project.mark(ctx, Value("item", {"id": "P:claim/x", "type": "claim"}, origin={"oes": "emf/1"}),
                         **{"as": "verified"})
    assert not verdict("verified-only-where-derived", claim, node_={"modifiers": {"as": "verified"}})[0]
    where = R.Where("visibility is internal", lambda r: r.field("visibility") == "internal")
    assert project.withhold(ctx, meadow, where=where) is None
    assert "atom/meadow//C:entity/meadow-software-inc" in ctx.withheld          # held by its key, not its bare id
    assert "atom/meadow//P:service/reconcile" not in ctx.withheld
    assert "C:entity/meadow-software-inc" not in ctx.withheld


def _twins() -> tuple[Value, Value]:
    """Two concerns' items that share an id, as Wikimedia's Foundation and Endowment each hold `M:audience/donors`."""
    def row(atom: str, name: str, vis: str) -> Value:
        iid = "M:audience/donors"
        return Value("item", {"id": iid, "type": "audience", "name": name, "visibility": vis, "status": "active"},
                     origin={"item": True, "id": iid, "key": f"atom/{atom}//{iid}", "kind": "audience",
                             "oes": "comprise/1"})
    return row("wmf", "Donors", "public"), row("endowment", "Donors to the Endowment", "internal")


def test_withholding_one_twin_keeps_the_other(tmp_path):
    """Withholding one item of an id leaves another item that shares the id in another part (THYM.md 18)."""
    foundation, endowment = _twins()
    ctx = ctx_for(tmp_path)
    project.withhold(ctx, endowment)
    assert list(ctx.withheld) == ["atom/endowment//M:audience/donors"]
    assert V.is_withheld(ctx.withheld, endowment) and not V.is_withheld(ctx.withheld, foundation)
    both = Value("list", [foundation, endowment])
    ctx2 = ctx_for(tmp_path)
    project.withhold(ctx2, both, where=R.Where("visibility is internal",
                                               lambda r: r.field("visibility") == "internal"))
    assert list(ctx2.withheld) == ["atom/endowment//M:audience/donors"]
    # an id given as a word names no part, and takes every item of that id
    ctx3 = ctx_for(tmp_path)
    ctx3.withhold("M:audience/donors")
    assert V.is_withheld(ctx3.withheld, foundation) and V.is_withheld(ctx3.withheld, endowment)
    # an item with no key is held by its id, as before
    bare = Value("item", {"id": "P:claim/x", "type": "claim"}, origin={"id": "P:claim/x"})
    ctx4 = ctx_for(tmp_path)
    ctx4.withhold(bare)
    assert list(ctx4.withheld) == ["P:claim/x"] and V.is_withheld(ctx4.withheld, bare)


def test_verified_derived_counts_a_twin_of_a_withheld_item(tmp_path):
    """`project`'s rules compare by key too: the kept twin is still an emitted, marked item."""
    foundation, endowment = _twins()
    ctx = ctx_for(tmp_path)
    ctx.emitted.append(project.mark(ctx, foundation, **{"as": "verified"}))
    ctx.emitted.append(project.mark(ctx, endowment, **{"as": "stated"}))      # stated on an audience: refused, unless withheld
    ok, why = verdict("verified-derived", Value("volume", {}), ctx=ctx)
    assert not ok and "is marked stated" in why
    project.withhold(ctx, endowment)
    ok, why = verdict("verified-derived", Value("volume", {}), ctx=ctx)
    assert ok and "verified on 1 item" in why, why


def test_no_mark_finds_a_withheld_item_by_key_or_by_id(tmp_path):
    _foundation, endowment = _twins()
    ctx = ctx_for(tmp_path)
    project.withhold(ctx, endowment)
    assert verdict("no-mark", Value("volume", {"offers": [{"name": "Donors"}]}), ctx=ctx)[0]
    for said in ("M:audience/donors", "atom/endowment//M:audience/donors"):
        ok, why = verdict("no-mark", Value("volume", {"offers": [{"name": said}]}), ctx=ctx)
        assert not ok and "is named in the output" in why


def test_projection_rules_hold_and_fail(tmp_path):
    ctx = ctx_for(tmp_path)
    good = {"isotype": "comprise-isotype/0", "hid": None, "epoch": "2026-Q4", "cadence": "quarterly", "sample": True,
            "identity": {"name": "M", "founded": 2019}, "shape": {"employees": "some"},
            "offers": [{"name": "A", "summary": "", "kind": "product"},
                       {"name": "B", "summary": "", "kind": "service"}],
            "seeks": [], "open_to": [], "program": {"name": "p", "sha256": "0" * 64}}
    v = Value("volume", good)
    for name in ("epoch", "standing-gate", "banded", "default-deny", "no-counts"):
        assert verdict(name, v, ctx=ctx)[0], name
    assert not verdict("epoch", Value("volume", {**good, "epoch": "2026-Q3"}), ctx=ctx)[0]
    assert not verdict("epoch", Value("volume", {**good, "offers": good["offers"][::-1]}), ctx=ctx)[0]
    ok, why = verdict("epoch", Value("volume", {**good, "identity": {"name": "edited 2026-10-30"}}), ctx=ctx)
    assert not ok and "only date" in why
    ok, why = verdict("standing-gate", Value("volume", {**good, "sample": False}), ctx=ctx)
    assert not ok and "first-party" in why
    first = ctx_for(tmp_path, {"standing": lambda h: "first-party"})
    assert verdict("standing-gate", Value("volume", {**good, "sample": False}), ctx=first)[0]
    assert not verdict("banded", Value("volume", {**good, "shape": {"employees": "7"}}), ctx=ctx)[0]
    ctx.slots["employees"] = Value("word", "none", origin={"band": ["none", "some"]})          # never marked
    ok, why = verdict("verified-derived", v, ctx=ctx)
    assert not ok and "employees is derived" in why


def test_open_house_lands_the_recorded_outputs_byte_for_byte(root, engines):
    t = RUN.run(load("expected/open-house/plan.cosm"), inputs_root=SUITE, root=root,
                program=SUITE / "expected" / "open-house" / "items.cosm", engines=engines, now=NOW)
    assert isinstance(t, T.Trace) and t.landed, getattr(t, "refusal", t)
    landed = t.dir / "outputs"
    recorded = sorted(p.name for p in OUTPUTS.iterdir())
    assert recorded == ["i.cosm", "isotype.cosm", "isotype.json"]
    for name in recorded:
        assert (landed / name).read_bytes() == (OUTPUTS / name).read_bytes(), name
    iso = mc.yaml_load((landed / "i.cosm").read_text(encoding="utf-8"))
    assert set(iso) == set(C.ISOTYPE_KEYS) - {"trace"}
    assert iso["shape"] == {"employees": "none"} and iso["sample"] is True and iso["epoch"] == "2026-Q4"
    assert [o["name"] for o in iso["offers"]] == ["CSV importer", "Bank sync", "Reconcile", "Tip-out"]
    assert iso["identity"] == {"name": "Meadow Software", "domains": ["meadow.example"], "founded": 2019,
                               "kind": "company"}
    rec = next(r for r in t.records if r["id"] == "R:record/7")
    assert all(c["ok"] for c in rec["checks"])
    vd = next(c for c in rec["checks"] if c["name"] == "verified-derived")
    assert "19 items neither emitted nor withheld were left out by default-deny" in vd["why"]
    assert lint_errors(t.path) == []


def test_conform_has_no_failure_and_no_skip_for_open_house(tmp_path, engines):
    rep = conform.conform(SUITE, root=tmp_path / "conform-root", engines=engines)
    assert rep.ok, "\n".join(rep.failed)
    assert not [s for s in rep.skipped if s.startswith("open-house")]
    assert "open-house: run lands expected/open-house/outputs/ byte for byte" in rep.passed


# ---------------------------------------------------------------------------
# publish-story: derive, assert covers, null, measure, context, graph, package
# ---------------------------------------------------------------------------

def test_publish_story_runs_end_to_end_with_the_fake_coprocessor(root, engines):
    t, cp = run_publish(root, engines, {"derive": [PASSAGE, WHOLE_ATEM], "null": null_answer(), "measure": JUDGED})
    assert isinstance(t, T.Trace) and t.landed, getattr(t, "refusal", t)
    assert [m for m, _ in cp.calls] == ["derive", "derive", "null", "measure"]
    names = sorted(p.name for p in (t.dir / "candidates").iterdir())
    assert [n for n in names if "-e" not in n] == ["1-1.1.cosm", "1.1.cosm", "3.1.cosm", "4.1.cosm"]
    # the engine calls are recorded beside the model's answers (THYM.md 12.4), so a replay needs no engine
    assert [n for n in names if "-e" in n] == ["1-e1.1.cosm", "1-e2.1.cosm", "1-e3.1.cosm", "3-e1.1.cosm"]
    passages = mc.yaml_load((t.dir / "candidates" / "1-e1.1.cosm").read_text(encoding="utf-8"))
    assert passages["engine"] == "canon.derive_passages" and passages["keys"] == ["1-1"]
    assert passages["tokens"] == 10, "the passage's model call cost what the coprocessor reported"
    engines_by = {r["id"]: r["engine"] for r in t.records}
    assert engines_by["R:record/1"] == "model:fake-1" and engines_by["R:record/7"] == "code"
    covers = next(c for r in t.records if r["id"] == "R:record/2" for c in r["checks"] if c["name"] == "coverage")
    assert covers["ok"] and covers["why"].startswith("14 claim-bearing sentences, each traced (spans)")
    pkg = mc.yaml_load(t.outputs["out"].read_text(encoding="utf-8"))
    assert t.outputs["out"].name == "out.package.cosm"
    assert [r["role"] for r in pkg["contents"]] == ["text", "fabula", "morph"]
    assert pkg["contents"][0]["text"].encode("utf-8") == NOTES.read_bytes()
    assert pkg["made"]["program"]["name"] == "publish-story" and pkg["made"]["trace"]["run"] == t.run_id
    assert verdict("digests", Value("package", pkg)) == (True, "")
    folder = t.dir / "outputs" / "notes.thym"
    assert sorted(p.name for p in folder.iterdir()) == ["fabula.cosm", "morph.cosm", "package.cosm", "text.md"]
    assert verdict("digests", read_value(folder, "package")) == (True, "")
    fab = mc.yaml_load((folder / "fabula.cosm").read_text(encoding="utf-8"))
    assert fab["source"] == {"path": "text.md", "sha256": sha(NOTES), "size": NOTES.stat().st_size}
    assert fab["derived"]["mode"] == "model" and fab["derived"]["model"] == "fake-1"
    assert len(fab["derived"]["covers"]) == 14 and fab["atem"]["push"].startswith("Ask the parish council")
    assert all(s.startswith("text.md#") for it in fab["nodes"] for s in it["provenance"]["sources"])
    m = mc.yaml_load((folder / "morph.cosm").read_text(encoding="utf-8"))["nodes"][0]
    assert list(m["scales"]) == list(morph.SCALES) and all(isinstance(v, int) for v in m["scales"].values())
    assert set(m["basis"].values()) == {"statistics", "judgement"} and all(1 <= len(e) <= 3
                                                                           for e in m["evidence"].values())
    assert lint_errors(t.path) == []


def test_publish_story_replays_byte_identical(root, engines):
    # a replay keeps the recorded run's clock, which the trace records as the run's own start: no `now=` here
    t, _cp = run_publish(root, engines, {"derive": [PASSAGE, WHOLE_ATEM], "null": null_answer(), "measure": JUDGED},
                         now=None)
    assert t.landed, t.refusal
    again = RUN.replay(t.dir, root=root, engines=engines)
    assert isinstance(again, T.Trace) and again.landed, getattr(again, "refusal", again)
    assert again.replay == {"of": t.run_id, "identical": True, "differences": []}
    assert again.outputs["out"].read_bytes() == t.outputs["out"].read_bytes()


def test_publish_story_under_rules_runs_the_scaffolds(root, engines):
    cp = FakeCoprocessor({})
    t = RUN.run(load("expected/publish-story/plan.cosm"), inputs_root=SUITE, root=root, coprocessor=cp, rules=True,
                program=SUITE / "programs" / "publish-story.thym", engines=engines, now=NOW)
    assert t.landed, t.refusal
    assert cp.calls == []
    engines_by = {r["id"]: r["engine"] for r in t.records}
    assert engines_by["R:record/1"] == engines_by["R:record/3"] == engines_by["R:record/4"] == "rules"
    pkg = mc.yaml_load(t.outputs["out"].read_text(encoding="utf-8"))
    fab = mc.yaml_load(pkg["contents"][1]["text"])
    assert fab["derived"]["mode"] == "rules" and all(it["provenance"]["state"] == "pending" for it in fab["nodes"])
    m = mc.yaml_load(pkg["contents"][2]["text"])["nodes"][0]
    assert m["scales"]["humour"] == {"pending": "a model has not judged this"} and m["basis"]["humour"] == "judgement"
    assert isinstance(m["scales"]["register"], int)


GAPS = """nodes:
  - id: P:claim/july-mowing-harms-orchard
    type: claim
    name: July mowing harms orchard
    summary: "Mowing the meadow strip in July would cut the wildflowers before they seed and starve the pollinators the orchard depends on."
    stance: deduced
    salience: critical
    span: {lines: "17-20"}
  - id: T:event/council-asked-to-wait
    type: event
    name: council asked to wait
    summary: "The orchard agreed to ask the parish council to wait until September; Mara Okafor will write the letter."
    when: September
    span: {lines: "22-23"}
"""


def test_derive_reads_the_lines_its_fabula_left_uncovered(root, engines):
    t, cp = run_publish(root, engines, {"derive": [PASSAGE_SHORT, WHOLE_ATEM, GAPS], "null": null_answer(),
                                        "measure": JUDGED})
    assert t.landed, t.refusal
    assert [m for m, _ in cp.calls][:3] == ["derive"] * 3
    model = [p.name for p in sorted((t.dir / "candidates").iterdir()) if "-e" not in p.name]
    assert model[:3] == ["1-1.1.cosm", "1-2.1.cosm", "1.1.cosm"]
    gap = cp.calls[2]                                       # the repair asked only for lines 18 to 23
    assert gap[1]["schema"] == {"format": "text", "engine": "passage"}
    rec = next(r for r in t.records if r["id"] == "R:record/1")
    assert rec["attempts"] == 1 and all(c["ok"] for c in rec["checks"])
    fab = mc.yaml_load(mc.yaml_load(t.outputs["out"].read_text(encoding="utf-8"))["contents"][1]["text"])
    mowing = next(it for it in fab["nodes"] if it["id"] == "P:claim/july-mowing-harms-orchard")
    assert mowing["span"] == {"lines": "18-20"}                # read inside the gap, lines 18 to 23


def test_derive_is_refused_when_its_fabula_does_not_cover_the_text(root, engines):
    empty = "nodes: []\n"
    t, cp = run_publish(root, engines, {"derive": [PASSAGE_SHORT] + [WHOLE_ATEM, empty] * 3})
    assert t.outcome == "refused" and (t.refusal.check, t.refusal.line) == ("coverage", 12)
    assert "trace to no item of the fabula" in t.refusal.message and "after 3 attempts" in t.refusal.message
    assert [m for m, _ in cp.calls] == ["derive"] * 7


def test_the_null_is_one_paragraph_whatever_marks_the_model_adds(root, engines):
    """THYM.md 13.1: a paragraph mark on the null telling is read as none, so paragraph-rhythm is 1 by construction
    and the run lands; the telling is one paragraph and the footer."""
    marked = null_answer()
    for i in (2, 5, 7):
        marked["sentences"][i] = {**marked["sentences"][i], "paragraph": True}
    t, _cp = run_publish(root, engines, {"derive": [PASSAGE, WHOLE_ATEM], "null": marked, "measure": JUDGED})
    assert t.landed, t.refusal
    rec = next(r for r in t.records if r["id"] == "R:record/3")
    assert rec["attempts"] == 1 and all(c["ok"] for c in rec["checks"]) and "tries" not in rec
    out = mc.yaml_load(t.outputs["out"].read_text(encoding="utf-8"))
    morph = next(c for c in out["contents"] if c["path"] == "morph.cosm")
    assert "paragraph-rhythm" in morph["text"]


def test_null_pinned_refuses_a_hedged_or_long_null(root, engines):
    hedged = null_answer({"say": "Perhaps the orchard will press more juice.", "cites": ["P:claim/juice-rose"]})
    t, _cp = run_publish(root, engines, {"derive": [PASSAGE, WHOLE_ATEM], "null": [hedged] * 3})
    assert t.outcome == "refused" and t.refusal.check == "null-pinned" and "stance-style" in t.refusal.message


def test_the_derive_checks_hold_and_fail(tmp_path, engines):
    story = read_value(NOTES, "text")
    twin = read_value(TWIN, "fabula")
    for name in ("span-resolves", "stance-closed", "terms-grounded", "emf-checks"):
        assert verdict(name, twin, {"story": story}, ctx=ctx_for(tmp_path, engines)) [0], name
    data = mc.yaml_load(TWIN.read_text(encoding="utf-8"))
    data["nodes"][0]["span"] = {"lines": "40-41"}
    ok, why = verdict("span-resolves", Value("fabula", data), {"story": story})
    assert not ok and "outside the text's 26 lines" in why
    data = mc.yaml_load(TWIN.read_text(encoding="utf-8"))
    data["nodes"][4]["span"] = {"start": "words nobody wrote"}
    assert not verdict("span-resolves", Value("fabula", data), {"story": story})[0]
    data = mc.yaml_load(TWIN.read_text(encoding="utf-8"))
    next(n for n in data["nodes"] if n["id"] == "P:claim/juice-rose-to-140-litres")["stance"] = "certain"
    assert not verdict("stance-closed", Value("fabula", data))[0]
    feed = {"pollinate": {"word": "pollinate"}, "variety": {"word": "variety"}, "mulch": {"word": "mulch"}}
    fctx = ctx_for(tmp_path, {"feed": lambda ws: {w: feed.get(w.lower()) for w in ws}})
    assert verdict("terms-grounded", twin, ctx=fctx)[0]
    data = mc.yaml_load(TWIN.read_text(encoding="utf-8"))
    data["nodes"][1]["feed"] = {"word": "varietal"}
    ok, why = verdict("terms-grounded", Value("fabula", data), ctx=fctx)
    assert not ok and "'varietal' is not in FEED" in why
    data["nodes"][1]["feed"] = {"pending": "not in FEED"}
    assert verdict("terms-grounded", Value("fabula", data), ctx=fctx)[0]
    assert not verdict("emf-checks", Value("fabula", {"oes": "emf/1", "id": "emf/x", "name": "x",
                                                      "nodes": [{"id": "P:claim/x", "type": "claim"}]}))[0]


# ---------------------------------------------------------------------------
# tell, atem, expand: hand-made plans over the orchard twin
# ---------------------------------------------------------------------------

def twin_plan(*nodes: dict, extra: list | None = None) -> dict:
    inputs = [{"name": "f", "type": "fabula", "path": "inputs/notes.md.cosm", "sha256": sha(TWIN)}] + (extra or [])
    return hand_plan(*nodes, inputs=inputs)


def tell_answer(*rows: tuple) -> dict:
    return {"sentences": [{"say": s, "cites": list(c)} for s, c in rows]}


GOOD_TELL = tell_answer(
    ("Mara Okafor says the Bramley by the gate is the oldest tree on Hollins Lane.", ["P:claim/bramley-is-oldest"]),
    ("Every apple tree needs a second variety nearby to set fruit.", ["P:claim/apples-need-a-second-variety"]),
    ("The orchard pressed 140 litres of juice this year, up from 90.", ["P:claim/juice-rose-to-140-litres"]),
    ("Mara Okafor holds that the leaf mould raised the yield.", ["P:claim/mulch-raised-the-yield"]),
    ("It follows that mowing the meadow strip in July would starve the pollinators.",
     ["P:claim/july-mowing-harms-the-orchard"]))


@pytest.mark.parametrize("answer, check, words", [
    (tell_answer(("The orchard pressed 140 litres of juice.", ["P:claim/nonesuch"])), "coverage", "nonesuch"),
    (tell_answer(("The orchard pressed 500 litres of juice.", ["P:claim/juice-rose-to-140-litres"])),
     "no-invention", "the number 500"),
    (tell_answer(("Mara Okafor and Bob Jones run the orchard.", ["E:person/mara-okafor"])), "no-invention",
     "the name Bob"),
    (tell_answer(("The Bramley by the gate is the oldest tree on Hollins Lane.", ["P:claim/bramley-is-oldest"])),
     "stance-kept", "hearsay in the fabula and the telling says it as observed"),
])
def test_tell_contract_checks_refuse_the_run(root, engines, answer, check, words):
    plan = twin_plan(node(1, "tell f as told", "tell", asks=True, takes=["f"], gives="s", line=4))
    t = RUN.run(plan, inputs_root=SUITE, root=root, coprocessor=FakeCoprocessor({"tell": [answer] * 3}),
                engines=engines, now=NOW)
    assert t.outcome == "refused" and t.refusal.check == check, t.refusal
    assert words in t.refusal.message


def test_tell_lands_a_cited_short_with_its_footer(root, engines):
    plan = twin_plan(node(1, "tell f by weight", "tell", asks=True, takes=["f"], gives="s", line=4))
    stamped = {**GOOD_TELL, "engine": "model:g40-04"}
    cp = FakeCoprocessor({"tell": stamped})
    t = RUN.run(plan, inputs_root=SUITE, root=root, coprocessor=cp, engines=engines, now=NOW)
    assert t.landed, t.refusal
    text = t.outputs["s"].read_text(encoding="utf-8")
    assert text.rstrip().endswith("*a short of notes.md, told by weight, compiled from its EMF twin on 2026-11-01 "
                                  "by g40-04*")
    contract = cp.calls[0][1]
    assert contract["schema"]["stamp"] == "engine" and "footer" in contract["checks"]
    assert verdict("footer", Value("short", "Text.\n"))[0] is False
    assert verdict("footer", Value("short", text))[0] is True


def test_tell_under_rules_gives_the_outline(root, engines):
    plan = twin_plan(node(1, "tell f as told", "tell", asks=True, takes=["f"], gives="s", line=4))
    t = RUN.run(plan, inputs_root=SUITE, root=root, rules=True, engines=engines, now=NOW)
    assert t.landed, t.refusal
    text = t.outputs["s"].read_text(encoding="utf-8")
    assert text.startswith("# The Hollins Lane orchard, autumn notes")
    assert text.rstrip().endswith("compiled from its EMF twin on 2026-11-01 by rules, without a model*")
    assert t.records[0]["engine"] == "rules" and t.records[0]["state"] == "pending"


GOOD_ATEM = {"line": "The orchard pressed more juice this year, and mowing the meadow strip in July would starve the "
                     "pollinators its fruit depends on.",
             "focus": "A small orchard's good year, and a mowing date that could undo it.",
             "push": "Ask the parish council to wait until September before mowing.",
             "pull": "The cause of the rise is argued, and the mowing claim leans on cross-pollination.",
             "of": ["P:claim/july-mowing-harms-the-orchard", "P:claim/juice-rose-to-140-litres"]}


def test_atem_shape_refuses_and_unknown_ids_are_repaired(root, engines):
    plan = twin_plan(node(1, "atem f", "atem", asks=True, takes=["f"], gives="a", line=4))
    short_line = {**GOOD_ATEM, "line": "The orchard did well."}
    t = RUN.run(plan, inputs_root=SUITE, root=root, coprocessor=FakeCoprocessor({"atem": [short_line] * 3}),
                engines=engines, now=NOW)
    assert t.outcome == "refused" and t.refusal.check == "atem-shape" and "4 words" in t.refusal.message
    stray = {**GOOD_ATEM, "of": GOOD_ATEM["of"] + ["P:claim/nonesuch"]}
    t = RUN.run(plan, inputs_root=SUITE, root=root, coprocessor=FakeCoprocessor({"atem": stray}), engines=engines,
                now=NOW)
    assert t.landed, t.refusal
    a = mc.yaml_load(t.outputs["a"].read_text(encoding="utf-8"))
    assert a["of"] == GOOD_ATEM["of"] and a["source"]["type"] == "fabula"
    assert not verdict("span-resolves", Value("atem", {"line": "x", "of": ["P:claim/nonesuch"]}),
                       {"f": read_value(TWIN, "fabula")})[0]


def _expansion(n_words: int, *, cite_mowing: bool = True) -> dict:
    rows = [
        ("The Hollins Lane orchard pressed 140 litres of juice this year, up from 90 litres last year.",
         ["P:claim/juice-rose-to-140-litres"]),
        ("The writer counted the bottles on 12 October, after the pressing.", ["T:event/pressing"]),
        ("Mara Okafor, who has kept the orchard since 2019, holds that the leaf mould raised the yield.",
         ["P:claim/mulch-raised-the-yield", "E:person/mara-okafor"]),
        ("The orchard volunteers spread the leaf mould under the trees in March.", ["T:event/leaf-mould-spread"]),
        ("A warm, wet spring would explain most of the rise, because every orchard in the valley did well.",
         ["P:claim/spring-explains-the-yield"]),
        ("Every apple tree needs a second variety nearby to set fruit.", ["P:claim/apples-need-a-second-variety"]),
        ("It is assumed that the meadow strip exists to feed the pollinators the orchard depends on.",
         ["P:claim/strip-feeds-pollinators"]),
    ]
    if cite_mowing:
        rows.append(("If the parish council mows the meadow strip in July, it would cut the wildflowers before they "
                     "seed and starve the pollinators the orchard depends on.",
                     ["P:claim/july-mowing-harms-the-orchard", "E:org/parish-council"]))
    filler = ("Mara Okafor says the Bramley by the gate is the oldest tree on Hollins Lane, though the parish records "
              "do not confirm it.", ["P:claim/bramley-is-oldest"])
    out = list(rows)
    while sum(len(M.words_in(s)) for s, _c in out) < n_words - 20:
        out.append(filler)
    return tell_answer(*out)


def test_read_my_way_runs_end_to_end_the_short_way_in(root, engines):
    cp = FakeCoprocessor({"atem": GOOD_ATEM, "expand": _expansion(280)})
    t = RUN.run(load("expected/read-my-way/plan.cosm"), inputs_root=SUITE, root=root, coprocessor=cp,
                program=SUITE / "programs" / "read-my-way.thym", engines=engines)
    assert t.landed, t.refusal
    assert [m for m, _ in cp.calls] == ["atem", "expand"]
    text = t.outputs["r"].read_text(encoding="utf-8")
    assert 240 <= C.words(C.body(text)) <= 300
    assert "expanded from its atem to about 300 words" in text.splitlines()[-1]
    assert {r["id"]: r["engine"] for r in t.records}["R:record/5"] == "skipped"
    again = RUN.replay(t.dir, root=root, engines=engines, program=SUITE / "programs" / "read-my-way.thym")
    assert again.replay["identical"], again.replay


@pytest.mark.parametrize("answer, check", [
    (_expansion(120), "length"),
    (_expansion(280, cite_mowing=False), "span-inside"),
])
def test_expand_contract_checks_refuse_the_run(root, engines, answer, check):
    cp = FakeCoprocessor({"atem": GOOD_ATEM, "expand": [answer] * 3})
    t = RUN.run(load("expected/read-my-way/plan.cosm"), inputs_root=SUITE, root=root, coprocessor=cp,
                program=SUITE / "programs" / "read-my-way.thym", engines=engines, now=NOW)
    assert t.outcome == "refused" and t.refusal.check == check, t.refusal


# ---------------------------------------------------------------------------
# measure, read, morph: the scales
# ---------------------------------------------------------------------------

def test_measure_gives_ten_scales_with_evidence_and_basis(tmp_path, engines):
    ctx = ctx_for(tmp_path, engines)
    story = read_value(NOTES, "text")
    null = M.short_value("x\n", fabula=read_value(TWIN, "fabula"))
    req = morph.measure(ctx, story, against=null)
    assert set(req.inputs) == {"text", "sentences", "candidates"}
    assert req.inputs["sentences"].payload.startswith("1. Mara Okafor, who has kept")
    out = req.parse({"figurative": [], "humour": [12], "allusion": [{"sentence": 5, "to": "a saying"}],
                     "engine": "model:g40-04"})
    it = out.mapping()["nodes"][0]
    assert list(it["scales"]) == list(morph.SCALES)
    assert {s: it["basis"][s] for s in morph.JUDGEMENT} == dict.fromkeys(morph.JUDGEMENT, "judgement")
    n_words = sum(len(M.words_in(x.text)) for x in M.segment(NOTES.read_text(encoding="utf-8"), footer=True)
                  if x.kind != "heading")
    assert it["scales"]["humour"] == 3                       # one sentence in fifteen: 6 per hundred
    assert it["scales"]["allusion"] == morph.scale_value("allusion", 1000 // n_words, 1) == 4
    assert it["scales"]["figurative-density"] == 1
    assert it["scales"]["person-voice"] >= 2                 # "I counted the bottles myself"
    assert it["scales"]["analytical-depth"] == 2             # 2 reason links over 7 claims: 28 per hundred
    assert all(c <= 50 for s, c in it["confidence"].items() if it["basis"][s] == "statistics")
    assert it["confidence"]["humour"] == 40 and it["derived"]["by"] == "model:g40-04"
    assert it["derived"]["against"] == f"sha256:{null.sha256}"
    stamped = RUN.stamp(out, {"move": "measure", "run": "r", "step": 1})
    for name in ("scale-range", "scale-evidence", "provenance"):
        assert verdict(name, stamped, {"story": story})[0], name
    bad = mc.yaml_load(mc.dump(out.mapping()))
    bad["nodes"][0]["evidence"]["register"] = ["A sentence the text never held."]
    ok, why = verdict("scale-evidence", Value("morph", bad), {"story": story})
    assert not ok and "register cites a sentence the text does not hold" in why
    bad["nodes"][0]["scales"]["register"] = 6
    assert not verdict("scale-range", Value("morph", bad))[0]


def test_statistics_follow_the_thresholds_of_13_3():
    assert [morph.scale_value("sentence-length", r) for r in (10, 11, 15, 16, 27, 28)] == [1, 2, 2, 3, 4, 5]
    assert [morph.scale_value("register", r) for r in (1, 2, 4, 5, 19, 20)] == [1, 2, 2, 3, 4, 5]
    assert [morph.scale_value("humour", r, c) for r, c in ((0, 0), (0, 1), (2, 2), (3, 3), (25, 9))] == [1, 2, 2, 3, 5]
    plain_ = "The orchard pressed juice. The council will mow. The bees fed. The trees grew.\n"
    st = morph.statistics(plain_, telling=True)
    assert {s: st[s]["value"] for s in morph.STATISTICS} == dict.fromkeys(morph.STATISTICS, 1)
    chatty = ("I think we're gonna be okay, you know. Maybe it's fine. Perhaps you'd agree, and I suspect we might. "
              "Yeah, we probably could.\n")
    st = morph.statistics(chatty, telling=True)
    assert st["person-voice"]["value"] == 5 and st["stance-style"]["value"] == 5
    assert st["formality"]["value"] == 5 and st["formality"]["toward"] == "casual"
    assert "toward" not in morph.statistics(plain_, telling=True)["formality"]
    assert "person-voice 4: between impersonal and personal; 30 to 59" in morph.asks_for(read_value(MORPH, "morph"))


def desk_plan(tmp_path: Path) -> tuple[dict, Path]:
    """read-my-way over the orchard package with an occasion that is not a hurry, so the else branch reads."""
    desk = tmp_path / "at-the-desk.context.cosm"
    desk.write_text("oes: thym/1\nkind: context\nid: thym/at-the-desk\nname: at-the-desk\nnodes:\n"
                    "  - id: C:context/at-the-desk\n    type: context\n    name: at-the-desk\n"
                    "    summary: An evening at the desk, unhurried.\n    medium: desk\n    hurry: false\n"
                    "    words: 120\n"
                    "    provenance: {mode: manual, sources: [at-the-desk.context.cosm], confidence: 1}\n",
                    encoding="utf-8")
    inputs = [{"name": "p", "type": "package", "path": str(PACKAGE), "sha256": sha(PACKAGE)},
              {"name": "mine", "type": "morph", "path": str(MORPH), "sha256": sha(MORPH)},
              {"name": "now", "type": "context", "path": str(desk), "sha256": sha(desk)}]
    plan = plan_file(SUITE / "programs" / "read-my-way.thym", inputs)
    assert isinstance(plan, dict), plan
    return plan, desk


GOOD_READING = tell_answer(
    ("I'll tell you what I found at the orchard this year.", ["E:place/hollins-lane-orchard"]),
    ("It pressed 140 litres of juice, up from 90 last year.", ["P:claim/juice-rose-to-140-litres"]),
    ("Mara Okafor thinks the leaf mould did it.", ["P:claim/mulch-raised-the-yield"]),
    ("Maybe a wet spring did most of it, since every orchard nearby did well.",
     ["P:claim/spring-explains-the-yield"]),
    ("You should know the council wants to mow the strip in July.", ["E:org/parish-council"]),
    ("If they do, it would cut the wildflowers and starve the bees we need.",
     ["P:claim/july-mowing-harms-the-orchard"]),
    ("We think September would be kinder.", ["P:claim/july-mowing-harms-the-orchard"]))


def test_read_labels_a_reading_through_my_morph(tmp_path, root, engines):
    plan, _desk = desk_plan(tmp_path)
    cp = FakeCoprocessor({"read": {**GOOD_READING, "engine": "model:g40-04"}})
    t = RUN.run(plan, inputs_root=SUITE, root=root, coprocessor=cp, program=SUITE / "programs" / "read-my-way.thym",
                engines=engines, now=NOW)
    assert t.landed, t.refusal
    text = t.outputs["r"].read_text(encoding="utf-8")
    assert text.startswith("---\nread_through: plain-letter\n---\n")
    assert text.rstrip().endswith("*a reading of orchard-notes.thym through "
                                  "plain-letter, made here on 2026-11-01 by g40-04; the text stands unchanged*")
    rec = next(r for r in t.records if r["id"] == "R:record/5")
    assert {c["name"]: c["ok"] for c in rec["checks"]} == dict.fromkeys(
        ["coverage", "no-invention", "stance-kept", "scales-met", "labelled", "never-source", "provenance"], True)
    assert "occasion" in cp.calls[0][1]["schema"]["says"] or cp.calls[0][1]["move"] == "read"


def test_read_is_refused_when_it_misses_the_morph(tmp_path, root, engines):
    plan, _desk = desk_plan(tmp_path)
    flat = tell_answer(("The orchard pressed 140 litres of juice this year.", ["P:claim/juice-rose-to-140-litres"]),
                       ("Mara Okafor holds that the leaf mould raised the yield.", ["P:claim/mulch-raised-the-yield"]))
    t = RUN.run(plan, inputs_root=SUITE, root=root, coprocessor=FakeCoprocessor({"read": [flat] * 3}),
                program=SUITE / "programs" / "read-my-way.thym", engines=engines, now=NOW)
    assert t.outcome == "refused" and t.refusal.check == "scales-met"
    assert "person-voice 1 against 4" in t.refusal.message


def test_morph_tells_a_short_again_and_keeps_the_scales(root, engines, tmp_path):
    plan = twin_plan(node(1, "tell f as told", "tell", asks=True, takes=["f"], gives="s", line=4),
                     node(2, "morph s with mine", "morph", asks=True, takes=["s", "mine"], gives="r",
                          after=["R:node/1"], line=5),
                     extra=[{"name": "mine", "type": "morph", "path": "inputs/plain-letter.morph.cosm",
                             "sha256": sha(MORPH)}])
    t = RUN.run(plan, inputs_root=SUITE, root=root, engines=engines, now=NOW,
                coprocessor=FakeCoprocessor({"tell": GOOD_TELL, "morph": GOOD_READING}))
    assert t.landed, t.refusal
    assert t.outputs["r"].read_text(encoding="utf-8").rstrip().endswith("by a model*")
    t = RUN.run(plan, inputs_root=SUITE, root=root, engines=engines, now=NOW,
                coprocessor=FakeCoprocessor({"tell": GOOD_TELL, "morph": [GOOD_TELL] * 3}))
    assert t.outcome == "refused" and t.refusal.check == "scales-met"


# ---------------------------------------------------------------------------
# doc and pack
# ---------------------------------------------------------------------------

def test_enumerate_and_compile_round_trip(tmp_path, engines):
    ctx = ctx_for(tmp_path, engines)
    prog = read_value(SUITE / "programs" / "open-house.thym", "text")
    vol = M.doc.enumerate_(ctx, prog)
    assert vol.mapping()["kind"] == "program" and vol.mapping()["built"]["at"] == NOW
    assert verdict("byte-exact", vol, {"t": prog}) == (True, "")
    back = M.doc.compile_(ctx, vol)
    assert back.payload.encode("utf-8") == prog.bytes()
    assert verdict("byte-exact", back, {"v": vol}) == (True, "")
    md = tmp_path / "guide.md"
    md.write_text("# A guide\n\nIntro text.\n\n## 1. First\n\nThe first part.\n", encoding="utf-8")
    doc = M.doc.enumerate_(ctx, read_value(md, "text"))
    assert doc.mapping()["oes"] == "doc/1" and doc.mapping()["document"]["sha256"] == sha(md)
    assert M.doc.compile_(ctx, doc).payload == md.read_text(encoding="utf-8")


def test_package_accessors_read_both_forms(tmp_path, engines):
    ctx = ctx_for(tmp_path, engines)
    folder = read_value(PACKAGE, "package")
    f = pack.fabula_of(ctx, of=folder)
    assert f.type == "fabula" and f.sha256 == sha(PACKAGE / "fabula.cosm")
    assert pack.unpack(ctx, folder).bytes() == (PACKAGE / "text.md").read_bytes()
    assert pack.isomorph_of(ctx, of=folder).is_nothing and pack.graph_of(ctx, of=folder).is_nothing
    assert pack.context_of(ctx, of=folder).is_nothing
    story = read_value(NOTES, "text")
    assert pack.context_of(ctx, of=story).is_nothing                       # no catalog engine: nothing
    cctx = ctx_for(tmp_path, {"catalog": lambda p: {"name": "orchard notes", "neighbours": ["notes.md"]}})
    c = pack.context_of(cctx, of=story)
    assert c.type == "context" and c.mapping()["nodes"][0]["surrounding"]["name"] == "orchard notes"
    out = pack.package(ctx, story, f, read_value(MORPH, "morph"), NOTHING, NOTHING)
    assert [r["role"] for r in out.mapping()["contents"]] == ["text", "fabula", "morph"]
    assert verdict("digests", out) == (True, "") and verdict("released", out)[0]
    assert pack.unpack(ctx, out).bytes() == NOTES.read_bytes()
    assert pack.isomorph_of(ctx, of=out).sha256 == sha(MORPH)
    assert (ctx.stage / "notes.thym" / "package.cosm").is_file()
    graph = Value("graph", {"oes": "ascribe/1", "nodes": []})
    ok, why = verdict("released", graph)
    assert not ok and "no release recorded" in why
    assert verdict("released", Value("graph", {"release": {"at": "2026-11-01"}, "nodes": []}))[0]


# ---------------------------------------------------------------------------
# The host: prompt builders and the model's id stamped into an answer
# ---------------------------------------------------------------------------

def test_the_prompt_builders_write_every_model_backed_moves_messages(tmp_path, engines):
    ctx = ctx_for(tmp_path, engines)
    fab, story = read_value(TWIN, "fabula"), read_value(NOTES, "text")
    mine, desk = read_value(MORPH, "morph"), Value("context", {"oes": "thym/1", "kind": "context", "nodes": [
        {"id": "C:context/desk", "type": "context", "name": "desk", "summary": "At the desk.", "words": 120}]})
    seen: list = []

    def complete(messages, max_tokens=None):
        seen.append(messages)
        return "```yaml\nsentences:\n  - {say: The orchard did well., cites: [P:claim/juice-rose-to-140-litres]}\n```", \
            {"model": "g40-04"}

    mcp = H.ModelCoprocessor(complete)
    short = _cited_short(fab)
    requests = {"tell": emf.tell(ctx, fab, **{"as": "told", "with": mine}), "null": morph.null(ctx, of=fab),
                "expand": emf.expand(ctx, Value("atem", GOOD_ATEM), **{"with": fab, "to": Amount(300, "words")}),
                "atem": emf.atem(ctx, fab), "measure": morph.measure(ctx, story),
                "morph": morph.morph(ctx, short, **{"with": mine}),
                "read": morph.read(ctx, fab, **{"with": mine, "in": desk})}
    for move, req in requests.items():
        contract = {"move": move, "schema": req.contract["schema"], "checks": [], "repair": {"allowed": [],
                                                                                             "failed": []}}
        ins = {k: (v, v.sha256) for k, v in req.inputs.items()}
        cand = mcp.complete(contract, ins, budget={"attempts": 1, "output_words": 0, "prompt_tokens_max": 0,
                                                   "seconds": 1})
        assert cand["engine"] == "model:g40-04", move
        if req.contract["schema"].get("stamp") == "engine":
            assert cand["output"]["engine"] == "model:g40-04", move      # the footer can name the model
        system, user = seen[-1][0]["content"], seen[-1][-1]["content"]
        assert system and user, move
        if move in ("tell", "null", "expand", "read", "atem"):
            assert "[P:claim/juice-rose-to-140-litres]" in user, move
        if move in ("tell", "read", "morph"):
            assert "person-voice 4" in system, move
    assert "About 120 words." in seen[-1][0]["content"] and "words: 120" in seen[-1][0]["content"]
    assert "1. Mara Okafor, who has kept" in requests["measure"].inputs["sentences"].payload
    passthrough = [{"role": "system", "content": "S"}, {"role": "user", "content": "U"}]
    msgs = mcp.messages({"move": "derive", "repair": {}}, {"messages": (M.messages_value(passthrough), "x")})
    assert msgs == passthrough


# ---------------------------------------------------------------------------
# Wave 2 (0.5.0, P1): engine calls recorded, call keys that never collide, tokens, prose, replay refusals
# ---------------------------------------------------------------------------

def _fake_feed(words: list) -> dict:
    """A FEED that knows every word: the derive prompt then carries lookups no test seam's host can answer."""
    return {str(w).lower(): {"word": str(w).lower(), "band": 6} for w in words}


def test_a_run_records_its_engine_calls_and_replays_with_no_engine(root):
    from enough.thym.engines import recorded_names
    live = H.engines(feed=_fake_feed)
    t, _cp = run_publish(root, live, {"derive": [PASSAGE, WHOLE_ATEM], "null": null_answer(), "measure": JUDGED},
                         now=None)
    assert t.landed, t.refusal
    vol = T.load(t.path)
    assert recorded_names(T.root_item(vol)) == ["canon", "docoes", "feed"]
    rec = mc.yaml_load((t.dir / "candidates" / "1-e1.1.cosm").read_text(encoding="utf-8"))
    assert rec["engine"] == "canon.derive_passages" and len(rec["inputs"]["call"]) == 64
    assert lint_errors(t.path) == []

    class Refuses(dict):
        def get(self, name, default=None):
            raise AssertionError(f"a replay that recorded its engine calls reaches no engine ({name})")

    # the host of a replay has no FEED and no engine at all: the record is the whole of what they said
    again = RUN.replay(t.dir, root=root, engines=Refuses())
    assert isinstance(again, T.Trace) and again.landed, getattr(again, "refusal", again)
    assert again.replay == {"of": t.run_id, "identical": True, "differences": []}
    assert conform._records_engines(t.dir) is True
    older = _as_recorded_before_engine_calls(t.dir, root.parent / "older")
    assert conform._records_engines(older) is False, "a trace that names no engines was recorded before they were"


def _as_recorded_before_engine_calls(run_dir: Path, to: Path) -> Path:
    """A copy of a recorded run whose trace names no `engines`, as every run recorded before 0.5.0's wave 2 was
    (THYM.md 12.4: it replays with the host's live engines). The suite's own replays all record their engine calls
    since the checkpoint-A fixture was re-recorded (a grammar bump had changed what the live Canon engine writes)."""
    dst = to / run_dir.name
    shutil.copytree(run_dir, dst)
    trace = next(dst.glob("*.trace.cosm"))
    vol = mc.yaml_load(trace.read_text(encoding="utf-8"))
    for it in vol.get("nodes") or []:
        it.pop("engines", None)
    trace.write_text(mc.dump(vol), encoding="utf-8")
    return dst


def test_a_replay_recorded_before_engine_calls_skips_with_its_reason_where_there_is_no_feed(tmp_path):
    suite = tmp_path / "suite"
    shutil.copytree(SUITE, suite)
    shutil.copytree(SUITE.parent / "cosm", tmp_path / "cosm")          # the plan of open-house names ../cosm
    runs = sorted((suite / "replay" / "publish-story").iterdir())
    assert all(conform._records_engines(r) for r in runs), "every replay of the suite records its engine calls"
    shutil.rmtree(runs[0])
    _as_recorded_before_engine_calls(runs[1], tmp_path / "older")
    shutil.rmtree(runs[1])
    shutil.copytree(tmp_path / "older" / runs[1].name, runs[1])
    rep = conform.conform(suite, root=tmp_path / "conform-root", engines=H.engines(feed=None))
    assert rep.ok, "\n".join(rep.failed)
    assert len(rep.skipped) == 1 and runs[1].name in rep.skipped[0], rep.skipped
    assert "recorded before engine calls were" in rep.skipped[0] and "no FEED engine" in rep.skipped[0]


def test_every_replay_of_the_suite_replays_with_no_feed_and_no_engine(tmp_path):
    rep = conform.conform(SUITE, root=tmp_path / "conform-root", engines=H.engines(feed=None))
    assert rep.ok and not rep.skipped, "\n".join(rep.failed + rep.skipped)


TWICE = """thym 0

program twice
  why: a text derived, then told twice, in one step.

  takes story: text
  gives s: short

  move told-twice(t: text): short
    let f = derive t
    let a = tell f as told
    give tell f as told
  end

  give told-twice story
end
"""


def test_engine_calls_and_two_requests_in_one_node_never_collide(root):
    """Two passages read through the engine, then three requests, all in node 1 (THYM.md 12.4): every key its own."""
    mv = R.Moves()
    for name in ("tell",):
        mv.add(name, lambda ctx, *ops, **m: Request(contract={"schema": {"format": "markdown"}},
                                                    inputs={f"in{k}": v for k, v in enumerate(ops)}))

    @mv.implements("derive")
    def derive(ctx, story):
        adapter = M.EngineAdapter(ctx, "derive")
        adapter([{"role": "user", "content": "passage one"}])
        adapter([{"role": "user", "content": "passage two"}])
        return Request(contract={"schema": {"format": "yaml"}}, inputs={"story": story})

    from tests.test_thym_run import fake_checks, telling
    plan = hand_plan(node(1, "told-twice story", "told-twice", asks=True, takes=["story"], gives="s", line=15),
                     name="twice")
    cp = FakeCoprocessor({"derive": ["nodes: []\n", "nodes: []\n", TWIN.read_text(encoding="utf-8")],
                          "tell": [telling(), telling()]})
    t = RUN.run(plan, inputs_root=SUITE, root=root, coprocessor=cp, program=TWICE, moves=mv, checks=fake_checks())
    assert t.landed, t.refusal
    names = sorted(p.name for p in (t.dir / "candidates").iterdir())
    assert names == ["1-1.1.cosm", "1-2.1.cosm", "1-3.1.cosm", "1-4.1.cosm", "1.1.cosm"]
    moves = [mc.yaml_load((t.dir / "candidates" / n).read_text(encoding="utf-8"))["contract"]["move"] for n in names]
    assert moves == ["derive", "derive", "tell", "tell", "derive"]
    rec = next(r for r in t.records if r["id"] == "R:record/1")
    assert rec["tokens"] == 50, "two passages and three requests at 10 tokens each: the engine's calls count too"
    again = RUN.replay(t.dir, root=root, moves=mv, checks=fake_checks())
    assert again.replay["identical"], again.replay


def test_the_model_coprocessor_reports_the_tokens_the_engine_reports():
    assert H.reported_tokens({"usage": {"total_tokens": 77}}) == 77
    assert H.reported_tokens({"usage": {"prompt_tokens": 60, "completion_tokens": 17}}) == 77
    assert H.reported_tokens({"model": "x"}) is None
    mc_ = H.ModelCoprocessor(lambda messages, max_tokens=None: ("text", {"model": "m", "usage": {"total_tokens": 77}}))
    cand = mc_.complete({"move": "tell", "schema": {"format": "markdown"}, "checks": []}, {}, budget={})
    assert cand["tokens"] == 77


def test_the_environment_names_the_models_window_when_a_model_runs(monkeypatch, root, engines):
    reads: list = []
    monkeypatch.setattr(H, "agent_free", lambda: False)
    monkeypatch.setattr(H, "_read_n_ctx", lambda url: reads.append(url) or 16384)
    kw = H.runtime_kwargs(complete=lambda messages, max_tokens=None: ("", {}))
    assert reads == [], "the window is read only when a plan asks a model"
    kw.update(coprocessor=FakeCoprocessor({"derive": [PASSAGE, WHOLE_ATEM], "null": null_answer(),
                                           "measure": JUDGED}), engines=engines, root=root)
    t = RUN.run(load("expected/publish-story/plan.cosm"), inputs_root=SUITE,
                program=SUITE / "programs" / "publish-story.thym", now=NOW, **kw)
    assert t.landed, t.refusal
    assert T.load(t.path)["environment"]["context"] == 16384 and len(reads) == 1, "one reading, shared"

    def no_read(url):
        raise AssertionError("a run that asks no model never asks a model's size")
    monkeypatch.setattr(H, "_read_n_ctx", no_read)
    kw = H.runtime_kwargs(rules=True)
    assert kw["environment"]["context"] == 0
    kw = H.runtime_kwargs()
    kw.update(root=root, engines=engines)
    t = RUN.run(load("expected/open-house/plan.cosm"), inputs_root=SUITE,
                program=SUITE / "expected" / "open-house" / "items.cosm", now=NOW, **kw)
    assert t.landed and T.load(t.path)["environment"]["context"] == 0


def _narrating(answers: list):
    calls: list = []

    def complete(messages, max_tokens=None):
        calls.append(messages)
        return answers[min(len(calls), len(answers)) - 1], {"model": "g40-04"}
    return complete, calls


def test_prose_around_the_yaml_fails_schema_at_once_and_is_asked_again(root, engines):
    clean = mc.dump(GOOD_TELL)
    narrated = "Thinking Process: the user wants a telling, so I will list the claims.\n\n```yaml\n" + clean + "```\n"
    complete, calls = _narrating([narrated, clean])
    plan = twin_plan(node(1, "tell f by weight", "tell", asks=True, takes=["f"], gives="s", line=4))
    t = RUN.run(plan, inputs_root=SUITE, root=root, coprocessor=H.ModelCoprocessor(complete), engines=engines,
                now=NOW)
    assert t.landed, t.refusal
    assert len(calls) == 2 and calls[1][-1]["content"].endswith(H.ONLY_THE_YAML)
    assert "schema: prose around the YAML" in calls[1][-1]["content"]
    rec = next(r for r in t.records if r["id"] == "R:record/1")
    assert rec["attempts"] == 2
    first = mc.yaml_load((t.dir / "candidates" / "1.1.cosm").read_text(encoding="utf-8"))
    assert first["output"].startswith("Thinking Process:"), "the narration is recorded as the model wrote it"
    again = RUN.replay(t.dir, root=root)
    assert again.replay["identical"], again.replay


def test_a_model_that_only_narrates_is_refused_on_schema_never_on_coverage(root, engines):
    complete, calls = _narrating(["Here is the YAML you asked for:\n" + mc.dump(GOOD_TELL)])
    plan = twin_plan(node(1, "tell f by weight", "tell", asks=True, takes=["f"], gives="s", line=4))
    t = RUN.run(plan, inputs_root=SUITE, root=root, coprocessor=H.ModelCoprocessor(complete), engines=engines,
                now=NOW)
    assert t.outcome == "refused" and t.refusal.check == "schema" and len(calls) == 3
    assert "starts with prose" in t.refusal.message and "after 3 attempts" in t.refusal.message


def test_an_unreadable_atem_fails_schema_and_is_asked_again(root, engines):
    t, cp = run_publish(root, engines, {"derive": [PASSAGE, "I am sorry, I cannot do that.", WHOLE_ATEM],
                                        "null": null_answer(), "measure": JUDGED})
    assert t.landed, t.refusal
    assert [m for m, _ in cp.calls][:3] == ["derive"] * 3
    rec = next(r for r in t.records if r["id"] == "R:record/1")
    assert rec["attempts"] == 2
    assert "could not be read" in cp.calls[2][1]["repair"]["failed"][0]["why"]
    fab = mc.yaml_load(mc.yaml_load(t.outputs["out"].read_text(encoding="utf-8"))["contents"][1]["text"])
    assert isinstance(fab["atem"]["line"], str), "the atem that landed was read, never four open questions"
    t2, _cp = run_publish(root, engines, {"derive": [PASSAGE] + ["Sorry."] * 3})
    assert t2.outcome == "refused" and t2.refusal.check == "schema"


def test_a_replay_that_cannot_match_refuses_at_once(root, tmp_path):
    import time as _time
    live = H.engines(feed=None)
    t, _cp = run_publish(root, live, {"derive": [PASSAGE, WHOLE_ATEM], "null": null_answer(), "measure": JUDGED},
                         now=None)
    assert t.landed, t.refusal

    def tampered(name: str, field: str) -> Path:
        copy = tmp_path / f"{name}-{field}" / t.run_id
        shutil.copytree(t.dir, copy)
        path = copy / "candidates" / name
        rec = mc.yaml_load(path.read_text(encoding="utf-8"))
        key = next(iter(rec["inputs"]))
        rec["inputs"][key] = "0" * 64
        path.write_text(mc.dump(rec), encoding="utf-8")
        return copy

    for name in ("1-e1.1.cosm", "1.1.cosm", "4.1.cosm"):
        t0 = _time.monotonic()
        r = RUN.replay(tampered(name, "inputs"), root=root)
        took = _time.monotonic() - t0
        assert isinstance(r, T.Trace) and r.outcome == "refused", r
        assert r.refusal.check in ("replay", "move") and "replay" in str(r.refusal), r.refusal
        assert took < 2, f"{name}: a replay that cannot match refused after {took:.1f} s"
    moved = tmp_path / "moved-input"
    shutil.copytree(SUITE / "inputs", moved / "inputs")
    plan = load("expected/publish-story/plan.cosm")
    t3 = RUN.run(plan, inputs_root=moved, root=root, coprocessor=FakeCoprocessor(
        {"derive": [PASSAGE, WHOLE_ATEM], "null": null_answer(), "measure": JUDGED}),
        program=SUITE / "programs" / "publish-story.thym", engines=live)
    assert t3.landed, t3.refusal
    (moved / "inputs" / "notes.md").write_text("A changed text.\n", encoding="utf-8")
    t0 = _time.monotonic()
    r = RUN.replay(t3.dir, root=root)
    assert isinstance(r, Refusal) and (r.stage, r.check) == ("plan", "input") and _time.monotonic() - t0 < 2


# ---------------------------------------------------------------------------
# Paths in plans and traces are POSIX on every system
# ---------------------------------------------------------------------------

def test_a_trace_writes_posix_paths_whatever_system_made_them(monkeypatch):
    """A run recorded on Windows must replay elsewhere: `outputs/out.package.cosm`, never `outputs\\out.package.cosm`.
    Tested without Windows: a PureWindowsPath goes through the same helper `_land`, `digest_row` and the plan use."""
    from pathlib import PurePosixPath, PureWindowsPath
    from types import SimpleNamespace
    assert V.posix_path(PureWindowsPath("outputs") / "out.package.cosm") == "outputs/out.package.cosm"
    assert V.posix_path(PureWindowsPath("outputs\\notes.thym")) == "outputs/notes.thym"
    assert V.posix_path(PurePosixPath("outputs") / "out.package.cosm") == "outputs/out.package.cosm"
    assert V.posix_path("inputs/notes.md") == "inputs/notes.md"
    assert V.posix_path("odd\\name.md") == "odd\\name.md"                 # on POSIX a backslash is a letter of a name
    monkeypatch.setattr(V, "os", SimpleNamespace(sep="\\"))                 # as Windows reads a text it was given
    assert V.posix_path("inputs\\notes.md") == "inputs/notes.md"
    monkeypatch.undo()
    v = Value("text", "x", path=PureWindowsPath("C:\\runs\\outputs\\out.md"))
    assert T.digest_row("out", v)["path"] == "C:/runs/outputs/out.md"
    assert T.digest_row("out", v, path=PureWindowsPath("outputs") / "out.md")["path"] == "outputs/out.md"
    assert "str(landed[name])" not in Path(RUN.__file__).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# A call nested inside another call in a `for each` (wording only; the language is unchanged)
# ---------------------------------------------------------------------------

def _loop_program(tmp_path: Path, body: str):
    from enough import thym
    meadow = SUITE.parent / "cosm" / "holotypes" / "meadow"
    tmp_path.mkdir(parents=True, exist_ok=True)
    prog = tmp_path / "p.thym"
    prog.write_text("thym 0\n\nprogram p\n  takes h: volume\n  gives i: volume\n\n" + body
                    + "  give project h as isotype\nend\n", encoding="utf-8")
    pl = thym.plan_file(prog, [{"name": "h", "type": "volume", "path": str(meadow), "sha256": sha(meadow)}])
    assert not isinstance(pl, Refusal), pl
    return RUN.run(pl, inputs_root=SUITE, root=tmp_path / "root", program=prog, engines=H.engines(feed=None), now=NOW)


def test_a_nested_call_in_a_loop_is_folded_into_its_statement_and_lands(tmp_path):
    """T0's probe (survey 2.3.1): the nested `mark` is part of its statement's node and runs with each member, so the
    run lands (THYM 11.1); before the fold it was planned as a node of its own and handed every pass's list."""
    t = _loop_program(tmp_path, "  for each o in h where kind is service\n"
                                "    emit mark (mark o as stated) as verified\n  end\n")
    assert isinstance(t, T.Trace) and t.landed, getattr(t, "refusal", t)
    ok = _loop_program(tmp_path / "ok", "  move both(o: item): item\n    give mark (mark o as stated) as verified\n"
                                        "  end\n\n  for each o in h where kind is service\n    emit both o\n  end\n")
    assert isinstance(ok, T.Trace) and ok.landed, getattr(ok, "refusal", ok)
    def offers(tr):
        return mc.yaml_load((tr.dir / "outputs" / "i.cosm").read_text(encoding="utf-8")).get("offers")
    assert offers(t) == offers(ok) and offers(t)            # the same isotype, but for the program that made it


# ---------------------------------------------------------------------------
# The feed engine answers only the fields a run reads
# ---------------------------------------------------------------------------

def test_the_feed_engine_answers_only_the_fields_the_moves_read():
    whole = {"word": "orchard", "frequency_rank": 7, "definition": "A planting of fruit trees.", "pos": "noun",
             "pos_primary": "noun", "origin": "feed", "perfect_rhymes": ["x"] * 50, "zh_definition": "果园",
             "forms": [{"word": "orchards"}]}
    feed = H.feed_fields(lambda words: {w: (dict(whole) if w == "orchard" else None) for w in words})
    got = feed(["orchard", "zzxq"])
    assert got == {"orchard": {k: whole[k] for k in H.FEED_FIELDS}, "zzxq": None}
    # what the readers make of it is what they made of the whole entry
    text = "The orchard stands. The orchard grows old."
    full = morph.statistics(text, feed=lambda ws: {w: (whole if w == "orchard" else None) for w in ws})
    cut = morph.statistics(text, feed=feed)
    assert full == cut
    import enough.canon_derive as CD
    lookup_full = lambda ws: {w: (whole if w == "orchard" else None) for w in ws}       # noqa: E731
    assert CD._term_table(text, lookup_full) == [
        {**r, "entry": whole if r["entry"] else None} for r in CD._term_table(text, feed)]
    assert CD._feed_block(whole) == CD._feed_block(feed(["orchard"])["orchard"])


def test_a_packaged_fabula_says_text_md_in_every_locator():
    """`notes.md#L3, notes.md#L14` in one source becomes `text.md#L3, text.md#L14` (THYM.md 15: every span resolves
    into text.md); a name that merely ends the same way is left alone."""
    doc = {"oes": "emf/1", "id": "emf/notes-md", "name": "n", "source": {"path": "notes.md"},
           "nodes": [{"id": "E:person/a", "type": "person", "name": "A",
                      "provenance": {"mode": "derived", "sources": ["notes.md#L3, notes.md#L14,notes.md#L22",
                                                                    "other-notes.md#L2", "notes.md"]}}]}
    out = mc.yaml_load(pack._packaged_fabula(Value("fabula", doc)).decode("utf-8"))
    assert out["source"]["path"] == "text.md"
    assert out["nodes"][0]["provenance"]["sources"] == ["text.md#L3, text.md#L14,text.md#L22", "other-notes.md#L2",
                                                        "text.md"]
