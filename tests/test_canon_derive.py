"""The derivation engine (0.4.3, P3): `enough/canon_derive.py` and `dictionary.lookup_many`.

Rules mode against the hand-written fixture text (tests/fixtures/cosm/eml/notes.md) grounded in a tiny FEED built
from `tests/test_dictionary.py`'s fixture lexicon plus a few orchard words; model mode through a fake `complete`
(canned YAML, one deliberate lint error, garbage); atems, pins, the file atem, compile, the prompts. No model, no
network; FEED is built into tmp_path (conftest moved `ENOUGH_DICT_ROOT` there).
"""

from __future__ import annotations

import datetime as dt
import os
import re
import shutil
from pathlib import Path

import pytest

from enough import canon, canon_derive as CD, canon_prompts as P, dictionary as D, macrocosm
from tests.test_dictionary import SCHEMA, W, WORDS, sync_dictionary, write_lexicon

REPO = Path(__file__).resolve().parent.parent
FIX = REPO / "tests" / "fixtures" / "cosm" / "eml"
NOW = dt.datetime(2026, 10, 22, 10, 30, tzinfo=dt.timezone.utc)

# The orchard words FEED holds in these tests, beside the fixture lexicon's apple, run and the rest.
ORCHARD = [
    W("orchard", first_use="Old English", domain="agriculture", frequency_rank=4, hyphenation="or·chard",
      definition="A piece of land planted with fruit trees."),
    W("pollinate", pos="verb", pos_primary="verb", first_use="late 19th century", domain="biology",
      frequency_rank=2, hyphenation="pol·li·nate", definition="To carry pollen to a flower so that it sets seed."),
    W("mulch", pos="noun; verb", first_use="mid 17th century", domain="gardening", frequency_rank=2,
      hyphenation="mulch", definition="A layer of material spread over soil to keep it moist."),
    W("variety", first_use="late 15th century", frequency_rank=5, hyphenation="va·ri·e·ty",
      definition="A kind of plant bred to have distinct features."),
    W("orchards", head=False, form_of="orchard", form_labels=["pl."], status=None),
]


def lint_errors(text: str, tmp: Path, name: str = "twin.md.cosm") -> list[str]:
    path = tmp / name
    path.write_text(text, encoding="utf-8")
    vol = macrocosm.load_volume(path)
    assert vol.refused is None, vol.refused
    return [str(p) for p in macrocosm.lint(vol).errors]


def nodes_of(text: str) -> list[dict]:
    return macrocosm.yaml_load(text)["nodes"]


# Words of the fixture text FEED is made not to hold, so the scaffold has open questions to show.
NOT_IN_FEED = {"strip", "litres", "quirk"}
NAMES_AND_TIMES = {"mara", "okafor", "hollins", "bramley", "march", "july", "october", "september"}


def fixture_words() -> list[dict]:
    """Like the real FEED, the test FEED knows nearly every ordinary word of the fixture text (band 5,
    "Familiar"), so ranking by band means something; a plural whose singular is there is a form of it."""
    text = (FIX / "notes.md").read_text(encoding="utf-8")
    have = {w["word"] for w in WORDS + ORCHARD}
    words = {t.word.lower() for t in CD._tokens(text)
             if len(t.word) >= 4 and t.word.isalpha() and t.word.lower() not in CD.STOP_WORDS}
    words -= have | NOT_IN_FEED | NAMES_AND_TIMES
    plurals = {w for w in words if w.endswith("s") and w[:-1] in words | have}
    return ([W(w, frequency_rank=5, hyphenation=w) for w in sorted(words - plurals)]
            + [W(w, head=False, form_of=w[:-1], form_labels=["pl."], status=None) for w in sorted(plurals)])


@pytest.fixture
def feed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if SCHEMA is None:
        pytest.skip("reflib/dict/schema.sql not synced yet")
    lexicon = write_lexicon(tmp_path / "lexicon", words=WORDS + ORCHARD + fixture_words())
    out = tmp_path / "reflib-dict"
    sync_dictionary.sync(lexicon, out)
    monkeypatch.setenv("ENOUGH_DICT_SOURCE", str(out))
    assert str(D.state_root()).startswith(str(tmp_path))
    st = D.ensure_built()
    assert st["ready"], st


@pytest.fixture
def notes(tmp_path: Path) -> Path:
    d = tmp_path / "proj"
    d.mkdir()
    shutil.copyfile(FIX / "notes.md", d / "notes.md")
    return d / "notes.md"


# ---------------------------------------------------------------------------
# FEED batch grounding
# ---------------------------------------------------------------------------

def test_lookup_many_one_connection_forms_users_and_misses(feed, monkeypatch):
    opened = []
    real = D._connect

    def counting():
        opened.append(1)
        return real()

    monkeypatch.setattr(D, "_connect", counting)
    out = D.lookup_many(["Apples", "apple", "ran", "Orchard's", "zzzz", "", "  "])
    assert len(opened) == 1, "one connection for the whole batch"
    assert set(out) == {"apples", "apple", "ran", "orchard's", "zzzz"}
    assert out["apples"]["word"] == "apple" and out["apple"]["word"] == "apple"   # a form → its headword
    assert out["ran"]["word"] == "run"
    assert out["orchard's"]["word"] == "orchard"                                  # possessive dropped
    assert out["zzzz"] is None
    assert out["apple"]["origin"] == "feed"
    assert D.user_update("apple", {"definition": "Mine."})["ok"]
    assert D.lookup_many(["apple"])["apple"]["definition"] == "Mine."             # the user row wins
    assert D.lookup_many(["apple"])["apple"]["origin"] == "user"
    assert D.lookup_many([]) == {}


def test_lookup_many_without_feed_is_all_none(tmp_path):
    assert not D.feed_path().is_file()
    assert D.lookup_many(["apple", "orchard"]) == {"apple": None, "orchard": None}


# ---------------------------------------------------------------------------
# The lexical pre-pass and chunks
# ---------------------------------------------------------------------------

def test_candidate_terms_rank_fold_and_skip(feed):
    text = (FIX / "notes.md").read_text(encoding="utf-8")
    terms = CD.candidate_terms(text)
    assert terms == CD.candidate_terms(text), "deterministic"
    assert len(terms) == CD.TERMS_MIN                                  # a ~230-word note: 6, not 40
    assert not {"okafor", "bramley", "hollins", "mara", "july", "march"} & set(terms)   # names and months
    assert not {"would", "every", "there", "after"} & set(terms)       # stop words
    assert all(len(t) >= 4 for t in terms)
    # FEED knows some words: the rarer band ranks first (pollinate, mulch: band 2) ahead of orchard (4).
    assert terms.index("pollinate") < terms.index("orchard") and terms.index("mulch") < terms.index("orchard")
    folded = CD.candidate_terms("The apples fell. An apple stayed. Apples rot.")
    assert "apple" in folded and "apples" not in folded               # the form folds into its headword


def test_term_count_scales_with_the_text():
    """40 per 2,000 words, at least 6, at most 60: a short note, a mid-length text, a long one."""
    assert [CD.term_limit(n) for n in (0, 230, 330, 1_000, 2_000, 4_000, 50_000)] == [6, 6, 7, 20, 40, 60, 60]
    vocab = [f"glim{a}{b}" for a in "bcdfghjklm" for b in "bcdfghjklmnpqrstvwxz"]       # 200 distinct words

    def text_of(n: int) -> str:
        words = [vocab[i % len(vocab)] for i in range(n)]
        return "\n".join(" ".join(words[i:i + 10]) + "." for i in range(0, n, 10))

    nolookup = lambda ws: {}  # noqa: E731
    assert len(CD.candidate_terms(text_of(300), lookup=nolookup)) == 6
    assert len(CD.candidate_terms(text_of(1_000), lookup=nolookup)) == 20
    assert len(CD.candidate_terms(text_of(4_000), lookup=nolookup)) == 60
    cosm, _ = CD.derive_eml(text_of(4_000), source_name="long.md", source_stat=None, lookup=nolookup)
    assert sum(1 for n in nodes_of(cosm) if n["id"].startswith("L:")) == 60


def test_candidate_terms_without_feed_rank_by_use():
    text = (FIX / "notes.md").read_text(encoding="utf-8")
    terms = CD.candidate_terms(text, lookup=lambda ws: {})
    assert terms[0] == "orchard"                                       # the most used word
    both = CD.candidate_terms("The apples fell. An apple stayed. Apples rot.", lookup=lambda ws: {})
    assert "apple" in both and "apples" in both                        # no FEED, no folding


def test_names_are_entities_not_terms(tmp_path):
    """FEED holds no proper nouns, so rarity would put names first in the lexicon: a word capitalised mid-sentence
    (or in an entity's name) is an entity candidate only; with FEED there, a word only ever capitalised at
    sentence starts that FEED does not know is a name too."""
    text = ("Thomas Aquinas read the commentaries of Averroes closely. Averroes wrote about the intellect, and\n"
            "Aquinas answered with a treatise. Scholars still compare the treatise with the commentaries.\n"
            "Boethius, translated early, shaped the vocabulary.\n")
    words = {"commentaries": 2, "commentary": 2, "closely": 5, "intellect": 3, "answered": 5, "treatise": 3,
             "scholars": 4, "compare": 5, "translated": 5, "shaped": 5, "vocabulary": 4, "early": 6}

    def fake_feed(ws):
        return {w: ({"word": w, "frequency_rank": words[w]} if w in words else None) for w in ws}

    for lookup in (fake_feed, lambda ws: {}):
        terms = CD.candidate_terms(text, lookup=lookup)
        assert not {"thomas", "aquinas", "averroes"} & set(terms), terms
        assert "treatise" in terms
    assert "boethius" not in CD.candidate_terms(text, lookup=fake_feed)     # sentence-initial only, not in FEED
    assert CD.entity_candidates(text) == ["Thomas Aquinas", "Averroes"]
    cosm, _ = CD.derive_eml(text, source_name="scholars.md", source_stat=None, lookup=fake_feed)
    assert lint_errors(cosm, tmp_path) == []
    ids = {n["id"] for n in nodes_of(cosm)}
    assert {"E:thing/thomas-aquinas", "E:thing/averroes"} <= ids                # names still feed E items
    assert not {"L:term/aquinas", "L:term/averroes", "L:term/thomas"} & ids


def test_entity_candidates_and_kinds():
    text = (FIX / "notes.md").read_text(encoding="utf-8")
    assert CD.entity_candidates(text) == ["Mara Okafor", "Hollins Lane", "Bramley"]      # first appearance
    kinds = {e["name"]: e["kind"] for e in CD._entity_table(text)}
    assert kinds == {"Hollins Lane": "place", "Mara Okafor": "thing", "Bramley": "thing"}
    more = "We met Dr. Ada Lovelace at the Bank of England.\nThe Parish Council met on Monday.\n"
    got = {e["name"]: e["kind"] for e in CD._entity_table(more)}
    assert got == {"Dr. Ada Lovelace": "person", "Bank of England": "thing", "Parish Council": "org"}


def test_chunk_by_headings_windows_and_overlap():
    text = (FIX / "notes.md").read_text(encoding="utf-8")
    [c] = CD.chunk(text)
    assert (c.id, c.start_line, c.end_line) == (1, 1, 25)
    assert c.text_numbered.splitlines()[2] == "3| Mara Okafor, who has kept the Hollins Lane orchard since 2019, says the old"
    para = " ".join(["The orchard keeps a record of every tree it plants."] * 12)     # ~620 chars
    long = "# One\n\n" + "\n\n".join([para] * 8) + "\n\n# Two\n\nA short closing section.\n"
    parts = CD.chunk(long)
    lines = long.split("\n")
    assert len(parts) >= 3 and [p.id for p in parts] == list(range(1, len(parts) + 1))
    for p in parts:
        body = "\n".join(lines[p.start_line - 1:p.end_line])
        assert len(body) <= CD.CHUNK_CHARS
        assert p.text_numbered.splitlines()[0].startswith(f"{p.start_line}| ")
    windows = [p for p in parts if p.start_line < lines.index("# Two") + 1]
    for a, b in zip(windows, windows[1:]):
        assert b.start_line <= a.end_line, "one paragraph of overlap between windows"
    assert parts[-1].text_numbered.splitlines()[0].endswith("# Two"), "a heading starts its own chunk"
    assert CD.chunk("") == [] and CD.chunk("\n\n  \n") == []


def test_item_slug():
    assert CD.item_slug("the Support Lead") == "support-lead"
    assert CD.item_slug("Café “Owner’s” list") == "cafe-owners-list"
    assert CD.item_slug("con").startswith("con-")
    assert len(CD.item_slug("word " * 30)) <= CD.SLUG_MAX
    assert re.fullmatch(r"[0-9a-f]{6}", CD.item_slug("!!!"))


# ---------------------------------------------------------------------------
# Rules mode
# ---------------------------------------------------------------------------

def test_rules_eml_lints_clean_and_is_grounded(feed, notes, tmp_path):
    text, stat = CD.read_source(notes)
    cosm, info = CD.derive_eml(text, source_name="notes.md", source_stat=stat, now=NOW)
    assert cosm.splitlines()[0] == "oes: eml/1"
    assert lint_errors(cosm, tmp_path) == []
    doc = macrocosm.yaml_load(cosm)
    assert list(doc)[:8] == ["oes", "macrocosm", "id", "name", "source", "derived", "atem", "nodes"]
    assert doc["macrocosm"] == "0.0.1" and doc["id"] == "eml/notes-md"
    assert doc["name"] == "The Hollins Lane orchard, autumn notes"
    assert doc["source"] == {"path": "notes.md", **stat}
    assert doc["derived"] == {"at": NOW, "by": "person", "mode": "rules", "completeness": "full", "chunks": 1}
    assert info["mode"] == "rules" and info["dropped"] == 0
    by_id = {n["id"]: n for n in doc["nodes"]}
    assert by_id["L:term/orchard"]["feed"] == {"word": "orchard", "pos": "noun", "origin": "feed"}
    assert by_id["L:term/orchard"]["sense"] == "A piece of land planted with fruit trees."
    assert by_id["L:term/pollinate"]["feed"]["pos"] == "verb"
    assert sum(1 for i in by_id if i.startswith("L:")) == CD.TERMS_MIN    # scaled to a short note
    assert by_id["L:term/strip"]["feed"] == {"pending": "not in FEED"}
    assert "sense" not in by_id["L:term/strip"]
    assert {"E:place/hollins-lane", "E:thing/mara-okafor", "E:thing/bramley"} <= set(by_id)
    assert not [i for i in by_id if i[0] in "KPTX"], "rules invent no concepts, claims, events or atems"
    for n in doc["nodes"]:
        assert n["provenance"] == {"mode": "derived", "sources": [f"notes.md#L{n['span']['lines']}"],
                                   "confidence": 0.3, "state": "pending"}
        assert n["pending"] == "a model has not read this passage"
    # the scaffold atem
    assert doc["atem"]["line"].startswith("Mara Okafor, who has kept the Hollins Lane orchard since 2019")
    assert doc["atem"]["focus"].endswith("so that is hearsay for now.")
    assert doc["atem"]["push"] == doc["atem"]["pull"] == {"pending": "a model has not read this passage"}


def test_rules_spans_point_at_real_lines(notes):
    text, stat = CD.read_source(notes)
    lines = text.split("\n")
    cosm, _ = CD.derive_eml(text, source_name="notes.md", source_stat=stat, lookup=lambda ws: {})
    for n in nodes_of(cosm):
        line = lines[int(n["span"]["lines"]) - 1]
        assert n["name"].lower() in line.lower(), (n["id"], line)


def test_rules_ids_stable_across_runs(feed, notes):
    text, stat = CD.read_source(notes)
    a, _ = CD.derive_eml(text, source_name="notes.md", source_stat=stat, now=NOW)
    b, _ = CD.derive_eml(text, source_name="notes.md", source_stat=stat, now=NOW + dt.timedelta(hours=3))
    assert [n["id"] for n in nodes_of(a)] == [n["id"] for n in nodes_of(b)]
    assert nodes_of(a) == nodes_of(b)


def test_catalog_id_is_the_slugged_path_and_standalone_has_no_source(notes, tmp_path):
    text, _ = CD.read_source(notes)
    cosm, _ = CD.derive_eml(text, source_name="close.md", source_stat=None, rel_path="guides/close.md",
                            lookup=lambda ws: {})
    doc = macrocosm.yaml_load(cosm)
    assert doc["id"] == "eml/guides--close-md" and "source" not in doc
    assert lint_errors(cosm, tmp_path) == []


def test_twin_written_atomically_and_fresh_then_stale(notes, monkeypatch):
    text, stat = CD.read_source(notes)
    cosm, _ = CD.derive_eml(text, source_name="notes.md", source_stat=stat, lookup=lambda ws: {})
    replaced = []
    real = os.replace

    def spy(a, b):
        replaced.append((Path(a).name, Path(b).name))
        return real(a, b)

    monkeypatch.setattr(os, "replace", spy)
    assert CD.twin_state(notes) == "absent"
    twin = CD.twin_path(notes)
    assert twin.name == "notes.md.cosm"
    CD.write_twin(twin, cosm)
    assert twin.read_text(encoding="utf-8") == cosm
    assert len(replaced) == 1 and replaced[0][1] == "notes.md.cosm" and replaced[0][0].startswith(".notes.md.cosm.")
    assert sorted(p.name for p in notes.parent.iterdir()) == ["notes.md", "notes.md.cosm"], "no temp left over"
    assert CD.twin_state(notes) == "fresh"
    assert canon.eml_state(notes, twin) == "fresh"                    # one rule: P2's
    with notes.open("a", encoding="utf-8") as fh:
        fh.write("\nA line added later.\n")
    assert CD.twin_state(notes) == "stale"
    # a .cosm beside the text that is not an EML is not its twin
    twin.write_text("oes: canon/1\nid: canon/x\nname: x\nnodes: []\n", encoding="utf-8")
    assert CD.twin_state(notes) == "absent"


def test_rules_atem_scaffold_and_cut():
    a = CD.derive_atem("Rain that falls after a dry spell runs off. The soil is hard. A third sentence.")
    assert a == {"line": "Rain that falls after a dry spell runs off.",
                 "focus": "Rain that falls after a dry spell runs off. The soil is hard.",
                 "push": {"pending": "a model has not read this passage"},
                 "pull": {"pending": "a model has not read this passage"},
                 "stance_profile": {}, "mode": "rules"}
    long = "# Heading only\n\n" + " ".join(f"w{i}" for i in range(40)) + ".\n"
    line = CD.derive_atem(long)["line"]
    assert line.endswith("…") and len(line.split()) == CD.LINE_MAX_WORDS
    assert CD.derive_atem("# Just a title\n")["line"] == "Just a title"


# ---------------------------------------------------------------------------
# Pins and the file atem
# ---------------------------------------------------------------------------

MODEL_ATEM = {"line": "Mowing the meadow strip in July would starve the pollinators the orchard needs to set its fruit.",
              "focus": "When the parish council mows the meadow strip.",
              "push": "Ask the council to wait until September.",
              "pull": "The orchard depends on wildflowers it does not control."}


def test_pin_creates_a_minimal_twin_then_appends(notes, tmp_path):
    text, stat = CD.read_source(notes)
    first = CD.pin_atem(None, MODEL_ATEM, {"lines": "17-20", "start": "The parish council's grounds team"},
                        source_name="notes.md", source_stat=stat, now=NOW, title="The orchard",
                        of=["P:claim/nowhere"])
    assert lint_errors(first, tmp_path) == []
    doc = macrocosm.yaml_load(first)
    assert doc["derived"]["completeness"] == "atem" and doc["derived"]["mode"] == "model"
    assert doc["source"]["sha256"] == stat["sha256"] and doc["name"] == "The orchard" and "atem" not in doc
    [item] = doc["nodes"]
    assert item["id"] == "X:atem/1" and item["type"] == "atem" and item["name"] == "lines 17-20"
    assert item["span"] == {"lines": "17-20", "start": "The parish council's grounds team"}
    assert item["provenance"] == {"mode": "derived", "sources": ["notes.md#L17-L20"], "confidence": 0.8,
                                  "state": "known"}
    assert item["of"] == [{"pending": "P:claim/nowhere is not an item of this twin"}]
    assert CD.next_atem_id(first) == "X:atem/2"
    scaffold = CD.rules_atem("Mowing in July cuts the flowers. It harms the bees.")
    second = CD.pin_atem(first, scaffold, {"lines": "18"}, source_name="notes.md", source_stat=stat)
    assert lint_errors(second, tmp_path) == []
    ids = [n["id"] for n in nodes_of(second)]
    assert ids == ["X:atem/1", "X:atem/2"]
    pinned = nodes_of(second)[1]
    assert pinned["provenance"]["confidence"] == 0.3 and pinned["pending"] == CD.PENDING_NO_MODEL


def test_pin_into_the_full_fixture_keeps_everything(tmp_path):
    full = (FIX / "notes.md.cosm").read_text(encoding="utf-8")
    out = CD.pin_atem(full, MODEL_ATEM, {"lines": "13-15"}, source_name="notes.md", source_stat=None,
                      of=["P:claim/mulch-raised-the-yield"])
    before, after = nodes_of(full), nodes_of(out)
    assert after[:-1] == before
    assert after[-1]["id"] == "X:atem/2" and after[-1]["of"] == ["P:claim/mulch-raised-the-yield"]
    assert macrocosm.yaml_load(out)["source"] == macrocosm.yaml_load(full)["source"], "a pin never freshens"
    assert lint_errors(out, tmp_path) == []


def test_set_file_atem_keeps_nodes_and_makes_minimal_twins(notes, tmp_path):
    full = (FIX / "notes.md.cosm").read_text(encoding="utf-8")
    out = CD.set_file_atem(full, MODEL_ATEM, source_name="notes.md", source_stat=None)
    a, b = macrocosm.yaml_load(full), macrocosm.yaml_load(out)
    assert b["atem"] == MODEL_ATEM and b["nodes"] == a["nodes"] and b["derived"] == a["derived"]
    assert list(b) == list(a), "the atem replaced in place"
    assert lint_errors(out, tmp_path) == []
    text, stat = CD.read_source(notes)
    minimal = CD.set_file_atem(None, CD.rules_atem(text), source_name="notes.md", source_stat=stat, now=NOW,
                               title="The orchard")
    m = macrocosm.yaml_load(minimal)
    assert m["nodes"] == [] and m["derived"] == {"at": NOW, "by": "person", "mode": "rules",
                                                  "completeness": "atem", "chunks": 1}
    assert lint_errors(minimal, tmp_path) == []
    later = NOW + dt.timedelta(days=1)
    again = CD.set_file_atem(minimal, MODEL_ATEM, source_name="notes.md", source_stat=stat, now=later,
                             model="g40-04")
    g = macrocosm.yaml_load(again)
    assert g["derived"]["at"] == later and g["derived"]["mode"] == "model" and g["derived"]["model"] == "g40-04"
    assert g["atem"] == MODEL_ATEM and g["name"] == "The orchard"
    with pytest.raises(CD.DeriveError):
        CD.set_file_atem("nodes: [oops", MODEL_ATEM, source_name="notes.md", source_stat=None)


# ---------------------------------------------------------------------------
# Compile
# ---------------------------------------------------------------------------

def test_compiled_path_naming_and_collisions(tmp_path):
    when = dt.datetime(2026, 10, 22, 14, 32)
    p = CD.compiled_path(tmp_path / "notes.md.cosm", when)
    assert p.name == "notes-from-eml-2026-10-22-1432.md"
    p.write_text("x")
    assert CD.compiled_path(tmp_path / "notes.md.cosm", when).name == "notes-from-eml-2026-10-22-1432-2.md"
    assert CD.compiled_path(tmp_path / "rain.cosm", when).name == "rain-from-eml-2026-10-22-1432.md"


def test_rules_compile_of_the_fixture(tmp_path):
    before = sorted(tmp_path.iterdir())
    md = CD.compile_text(macrocosm.load_volume(FIX / "notes.md.cosm"), source_name="notes.md.cosm")
    assert sorted(tmp_path.iterdir()) == before, "compile_text writes nothing"
    lines = md.splitlines()
    assert lines[0] == "# The Hollins Lane orchard, autumn notes"
    assert lines[2].startswith("The orchard's juice rose this year")        # the atem line leads
    assert "It is taken as given that every apple tree needs a second apple variety" in md
    assert "It is assumed that the meadow strip exists" in md
    assert "Mara Okafor holds that the leaf mould" in md and "(an opinion)" in md
    assert "(reported)" in md
    # claims in salience order: the critical ones before the low one
    assert md.index("140 litres of juice this year") < md.index("oldest tree on Hollins Lane")
    # events in before/after order
    assert md.index("1. The orchard volunteers spread leaf mould") < md.index("2. The Hollins Lane orchard pressed")
    assert "## Terms" in md and "- **leaf mould** (not in FEED):" in md
    assert "by rules, without a model" in md
    assert CD.compile_text((FIX / "notes.md.cosm").read_text(encoding="utf-8")) .startswith("# The Hollins")
    with pytest.raises(CD.DeriveError):
        CD.compile_text("oes: canon/1\nnodes: []\n")


def test_model_compile_uses_one_completion():
    seen = []

    def fake(messages):
        seen.append(messages)
        return "```markdown\n# The orchard\n\nProse.\n```", {"model": "fake"}

    out = CD.compile_text((FIX / "notes.md.cosm").read_text(encoding="utf-8"), complete=fake)
    assert out == "# The orchard\n\nProse.\n" and len(seen) == 1
    assert seen[0][0]["content"] == P.COMPILE_SYSTEM and "It is assumed that" in seen[0][1]["content"]


# ---------------------------------------------------------------------------
# Model mode, through a fake `complete`
# ---------------------------------------------------------------------------

PASSAGE_YAML = """\
```yaml
nodes:
  - {id: L:term/pollinate, type: term, name: pollinate, summary: To carry pollen so that fruit can set.,
     span: {lines: "7-8"}, provenance: {mode: derived, sources: ['notes.md#L7-L8'], confidence: 0.9, state: known}}
  - id: E:person/mara
    type: person
    name: Mara Okafor
    summary: Mara Okafor keeps the Hollins Lane orchard.
    span: {lines: "3"}
    provenance: {mode: derived, sources: ['notes.md#L3'], confidence: 0.9, state: known}
  - id: K:concept/cross-pollination
    type: concept
    name: cross-pollination
    summary: An apple tree sets fruit only with pollen from a second variety.
    span: {lines: "7-8"}
    provenance: {mode: derived, sources: ['notes.md#L7-L8'], confidence: 0.9, state: known}
  - id: P:claim/apples-need-a-second-variety
    type: claim
    name: apples need a second variety
    summary: Every apple tree needs a second apple variety nearby to set fruit.
    stance: {stance}
    salience: high
    roles: {claim: K:concept/cross-pollination}
    span: {lines: "7"}
    provenance: {mode: derived, sources: ['notes.md#L7'], confidence: 0.9, state: known}
  - id: P:claim/bramley-is-oldest
    type: claim
    name: the Bramley is the oldest tree
    summary: Mara Okafor says the Bramley by the gate is the oldest tree on Hollins Lane.
    stance: hearsay
    salience: low
    roles: {source: E:person/mara, about: the old Bramley}
    links: [{rel: supports, to: P:claim/not-in-this-text}]
    span: {lines: "3-5"}
    provenance: {mode: derived, sources: ['notes.md#L3-L5'], confidence: 0.8, state: known}
  - id: T:event/pressing
    type: event
    name: the pressing
    summary: The orchard pressed 140 litres of juice, counted on 12 October.
    agent: Mara Okafor
    when: 12 October
    span: {lines: "10-11"}
    provenance: {mode: derived, sources: ['notes.md#L10-L11'], confidence: 0.9, state: known}
  - {id: X:atem/1, type: atem, name: the notes, summary: The passage's atem., line: The orchard had a good year.,
     focus: A good year., push: Wait to mow., pull: Mowing dates matter., span: {lines: "1-25"},
     provenance: {mode: derived, sources: ['notes.md#L1-L25'], confidence: 0.8, state: known}}
```
"""

ATEM_YAML = """\
line: The orchard pressed more juice this year, and mowing the meadow strip in July would starve the pollinators it needs.
focus: A small orchard's good year and a mowing date that could undo it.
push: Ask the parish council to wait until September before mowing.
pull: Whether mulch or weather raised the yield is open, and the lease may not let the parish mow.
stance_profile: {axiom: 1, hearsay: 1}
"""


def kind_of(messages: list[dict]) -> str:
    """Which call a model was asked to make, read from the messages the engine sent."""
    if messages[0]["content"].startswith("You write the atem"):
        return "atem"
    last = messages[-1]["content"]
    if "did not pass the checks" in last:
        return "repair"
    if "Your list was cut off" in last:
        return "continue"
    if "had no YAML `nodes:` list" in last:
        return "retry"
    return "passage"


class FakeModel:
    """Answers like a small local model: EML passages from `passages` (one per call, the last repeated), the
    continuation, the repair, the retry, and the atem. An answer may be `(text, finish_reason)`."""

    def __init__(self, passages: list, repairs: list | None = None, atem: str = ATEM_YAML,
                 continuations: list | None = None, retries: list | None = None):
        self.passages, self.repairs, self.atem = list(passages), list(repairs or []), atem
        self.continuations, self.retries = list(continuations or []), list(retries or [])
        self.calls: list[list[dict]] = []
        self.budgets: list = []

    def __call__(self, messages, max_tokens=None):
        self.calls.append(messages)
        self.budgets.append(max_tokens)
        kind = kind_of(messages)
        queue = {"atem": [self.atem], "repair": self.repairs, "continue": self.continuations,
                 "retry": self.retries, "passage": self.passages}[kind]
        answer = (queue.pop(0) if len(queue) > 1 else queue[0]) if queue else "still nothing"
        text, finish = answer if isinstance(answer, tuple) else (answer, "stop")
        return text, {"model": "fake-model", "finish_reason": finish}

    def kinds(self) -> list[str]:
        return [kind_of(m) for m in self.calls]


def good(stance: str = "axiom") -> str:
    return PASSAGE_YAML.replace("{stance}", stance)


def test_model_mode_repairs_one_lint_error(feed, notes, tmp_path):
    fake = FakeModel([good("certain")], repairs=[good("axiom")])
    text, stat = CD.read_source(notes)
    cosm, info = CD.derive_eml(text, source_name="notes.md", source_stat=stat, complete=fake, now=NOW)
    assert fake.kinds() == ["passage", "repair", "atem"]
    assert fake.budgets[:2] == [CD.EML_MAX_TOKENS] * 2, "EML completions carry the output budget"
    repair_msg = fake.calls[1][-1]["content"]
    assert "stance = 'certain'" in repair_msg and "Return only these items, corrected" in repair_msg
    assert repair_msg.count("- id: ") == 1 and "id: P:claim/apples-need-a-second-variety" in repair_msg
    assert "L:term/pollinate" not in repair_msg, "the items that passed are not sent again"
    assert lint_errors(cosm, tmp_path) == []
    doc = macrocosm.yaml_load(cosm)
    assert doc["derived"] == {"at": NOW, "by": "person", "model": "fake-model", "mode": "model",
                              "completeness": "full", "chunks": 1}
    assert info == {**info, "mode": "model", "model": "fake-model", "dropped": 0, "continued": 0}
    by_id = {n["id"]: n for n in doc["nodes"]}
    # ids rebuilt from names; the passage's own reference followed the rename
    assert "E:person/mara-okafor" in by_id and "E:person/mara" not in by_id
    assert by_id["P:claim/bramley-is-the-oldest-tree"]["roles"] == {"source": "E:person/mara-okafor",
                                                           "about": "the old Bramley"}
    # a link to nothing in the twin is an open question, not an error
    assert by_id["P:claim/bramley-is-the-oldest-tree"]["links"] == [
        {"pending": "supports P:claim/not-in-this-text: not an item of this twin"}]
    # a named reference that held a name now holds the id
    assert by_id["T:event/pressing"]["agent"] == "E:person/mara-okafor"
    # terms grounded deterministically in FEED, sense from FEED when the model gave none
    assert by_id["L:term/pollinate"]["feed"] == {"word": "pollinate", "pos": "verb", "origin": "feed"}
    assert by_id["L:term/pollinate"]["sense"].startswith("To carry pollen")
    assert by_id["L:term/pollinate"]["provenance"]["confidence"] == 0.9, "the model's reading of a floor word"
    assert "pending" not in by_id["L:term/pollinate"]
    # the lexicon floor: FEED-grounded terms the model did not discuss are there, saying so
    assert by_id["L:term/orchard"]["feed"]["word"] == "orchard"
    assert by_id["L:term/orchard"]["pending"] == CD.PENDING_FLOOR
    # one passage: its atem is the file's, not an X item
    assert not [i for i in by_id if i.startswith("X:")]
    assert doc["atem"]["line"].startswith("The orchard pressed more juice this year")
    assert [list(n)[:2] for n in doc["nodes"]][0] == ["id", "type"]
    assert [n["id"][0] for n in doc["nodes"]] == sorted((n["id"][0] for n in doc["nodes"]),
                                                       key=CD.MODULE_ORDER.index)


def test_model_mode_drops_what_the_repair_did_not_fix(notes, tmp_path):
    fake = FakeModel([good("certain")], repairs=[good("surely")])
    text, stat = CD.read_source(notes)
    cosm, info = CD.derive_eml(text, source_name="notes.md", source_stat=stat, complete=fake,
                               lookup=lambda ws: {})
    assert lint_errors(cosm, tmp_path) == []
    doc = macrocosm.yaml_load(cosm)
    assert doc["derived"]["dropped"] == 1 and info["dropped"] == 1
    ids = {n["id"] for n in doc["nodes"]}
    assert "P:claim/apples-need-a-second-variety" not in ids and "P:claim/bramley-is-the-oldest-tree" in ids


def test_model_mode_garbage_everywhere_still_lints_clean(tmp_path):
    para = " ".join(["The orchard keeps a record of every tree it plants."] * 12)
    text = "# One\n\n" + "\n\n".join([para] * 8) + "\n"
    n_chunks = len(CD.chunk(text))
    assert n_chunks >= 2
    fake = FakeModel(["I'm sorry, I can't do that."], retries=["Still no YAML here: {"], atem="no atem either")
    cosm, info = CD.derive_eml(text, source_name="long.md", source_stat=None, complete=fake,
                               lookup=lambda ws: {})
    assert lint_errors(cosm, tmp_path) == []
    doc = macrocosm.yaml_load(cosm)
    assert doc["nodes"] and {n["id"][0] for n in doc["nodes"]} == {"L"}, "only the lexicon floor"
    assert all(n["pending"] == CD.PENDING_FLOOR for n in doc["nodes"])
    assert doc["derived"]["dropped"] == n_chunks == info["dropped"]       # one per unreadable passage
    assert doc["derived"]["chunks"] == n_chunks
    assert doc["atem"]["line"] == {"pending": "the model's answer could not be read"}
    assert fake.kinds() == ["passage", "retry"] * n_chunks + ["atem"]


def test_model_mode_merges_across_passages_and_extends_spans(tmp_path):
    para = " ".join(["Ada Lovelace wrote the notes on the engine for the society."] * 40)
    text = "# One\n\n" + para + "\n\n# Two\n\n" + para + "\n"
    parts = CD.chunk(text)
    assert [(c.start_line, c.end_line) for c in parts] == [(1, 3), (5, 7)]
    first = """nodes:
  - {id: E:person/ada, type: person, name: Ada Lovelace, summary: Ada Lovelace wrote the notes.,
     span: {lines: "3"}, provenance: {mode: derived, confidence: 0.9}}
  - {id: K:concept/engine-notes, type: concept, name: the notes, summary: The notes on the engine.,
     span: {lines: "3"}, provenance: {mode: derived, confidence: 0.9}}
  - {id: X:atem/1, type: atem, name: one, summary: s, line: One., focus: f, push: p, pull: q,
     provenance: {mode: derived, confidence: 0.8}}
"""
    # The second passage names Ada again (her own id there), and refers to the notes by the id the FIRST
    # passage gave them, which it never defines: resolved after the merge.
    second = """nodes:
  - {id: E:person/lovelace, type: person, name: Ada Lovelace, summary: Ada Lovelace again.,
     span: {lines: "7"}, provenance: {mode: derived, confidence: 0.8}}
  - id: P:claim/ada-wrote
    type: claim
    name: Ada wrote the notes
    summary: Ada Lovelace wrote the notes on the engine.
    stance: observed
    roles: {actor: E:person/lovelace, object: K:concept/engine-notes}
    span: {lines: "7"}
    provenance: {mode: derived, confidence: 0.9}
  - {id: X:atem/1, type: atem, name: two, summary: s, line: Ada wrote the notes., focus: f, push: p, pull: q,
     provenance: {mode: derived, confidence: 0.8}}
"""

    def fake(messages):
        if messages[0]["content"].startswith("You write the atem"):
            user = messages[1]["content"]
            assert "- lines 1-3: One." in user and "- lines 5-7: Ada wrote the notes." in user
            return ATEM_YAML, {"model": "m"}
        return (first if "lines 1-3:" in messages[1]["content"] else second), {"model": "m"}

    cosm, info = CD.derive_eml(text, source_name="t.md", source_stat=None, complete=fake, lookup=lambda ws: {})
    assert lint_errors(cosm, tmp_path) == []
    by_id = {n["id"]: n for n in nodes_of(cosm)}
    ada = by_id["E:person/ada-lovelace"]
    assert ada["summary"] == "Ada Lovelace wrote the notes."              # the first wins
    assert ada["span"] == {"lines": "3-7"}                                # its span extended
    assert ada["provenance"]["sources"] == ["t.md#L3", "t.md#L7"]         # the sources appended
    assert by_id["P:claim/ada-wrote-the-notes"]["roles"] == {"actor": "E:person/ada-lovelace", "object": "K:concept/notes"}
    assert not [i for i in by_id if i.startswith("X:")], "passage atems feed the file's atem; X items are pins"
    assert info["chunks"] == 2 and info["dropped"] == 0


def test_a_re_derive_keeps_the_pinned_atems(notes, tmp_path):
    text, stat = CD.read_source(notes)
    pinned = CD.pin_atem(None, MODEL_ATEM, {"lines": "17-20"}, source_name="notes.md", source_stat=stat,
                         of=["E:thing/bramley"])
    pinned = CD.pin_atem(pinned, MODEL_ATEM, {"lines": "3"}, source_name="notes.md", source_stat=stat,
                         of=["P:claim/gone"])
    cosm, info = CD.derive_eml(text, source_name="notes.md", source_stat=stat, lookup=lambda ws: {},
                               previous=pinned)
    assert lint_errors(cosm, tmp_path) == []
    xs = [n for n in nodes_of(cosm) if n["id"].startswith("X:")]
    assert [x["id"] for x in xs] == ["X:atem/1", "X:atem/2"] and xs[0]["line"] == MODEL_ATEM["line"]
    # pinned before the twin had items, the first `of` was an open question; the second still names nothing
    assert xs[1]["of"] == [{"pending": "P:claim/gone is not an item of this twin"}]
    assert info["counts"]["X"] == 2
    assert CD.derive_eml(text, source_name="notes.md", source_stat=stat, lookup=lambda ws: {},
                         previous="not: [a twin")[1]["counts"].get("X") is None


def test_model_mode_cancel_between_passages():
    para = " ".join(["The orchard keeps a record of every tree it plants."] * 12)
    text = "# One\n\n" + "\n\n".join([para] * 8) + "\n"
    fake = FakeModel(["nodes: []"])
    with pytest.raises(CD.DeriveCancelled):
        CD.derive_eml(text, source_name="long.md", source_stat=None, complete=fake, lookup=lambda ws: {},
                      should_stop=lambda: len(fake.calls) >= 1)
    assert fake.kinds() == ["passage"], "the passage being read finished; no other began"


def test_model_atem_one_shot_and_long():
    seen = []

    def fake(messages):
        seen.append(messages)
        return ATEM_YAML, {"model": "fake-model"}

    a = CD.derive_atem("A short passage about an orchard.", context="a passage of notes.md", complete=fake)
    assert a["mode"] == "model" and a["model"] == "fake-model" and len(seen) == 1
    assert a["stance_profile"] == {"axiom": 1, "hearsay": 1}
    assert seen[0][1]["content"].startswith("Context: a passage of notes.md")
    seen.clear()
    long = "\n\n".join([" ".join(["The orchard keeps a record of every tree."] * 30)] * 16)
    assert len(long) > CD.ATEM_ONE_SHOT_CHARS
    CD.derive_atem(long, complete=fake)
    assert len(seen) == len(CD.chunk(long)) + 1 and len(seen) > 2
    partial = CD.derive_atem("x", complete=lambda m: ("line: Only a line.", {}))
    assert partial["line"] == "Only a line." and partial["push"] == {"pending": "the model gave no push"}


# ---------------------------------------------------------------------------
# The prompts
# ---------------------------------------------------------------------------

def test_prompts_size_and_required_words():
    assert len(P.EML_SYSTEM) < 2000
    assert len(P.EML_SYSTEM.format(source="a-rather-long-file-name.md")) < 2000
    for prompt in (P.EML_SYSTEM, P.ATEM_SYSTEM, P.COMPILE_SYSTEM):
        for stance in CD.STANCES:
            assert stance in prompt, (stance, prompt[:40])
        assert "pronoun" in prompt
    assert "8 claims, 4 events, 4 concepts, 6 entities, 8 terms" in P.EML_SYSTEM
    shapes = P.EML_SYSTEM
    assert shapes.index("P:claim") < shapes.index("T:event") < shapes.index("K:concept") \
        < shapes.index("E:<person") < shapes.index("L:term") < shapes.index("X:atem"), "claims come first"
    for words in ("return only a yaml `nodes:` list", "never invent", "no pronouns in a claim's summary",
                  "name every participant", '{lines: "a-b"}', "mode: derived", "state: known", "role names"):
        assert words in P.EML_SYSTEM.format(source="x.md").lower(), words
    for kind in ("L:term", "E:<person|org|place|work|thing>", "K:concept", "P:claim", "T:event", "X:atem"):
        assert kind in P.EML_SYSTEM
    # the owner's atem definitions, word for word
    a = P.ATEM_SYSTEM
    assert "15 to 25 words" in a and "Fair: the author would accept it" in a
    assert "Full: nothing the text depends on is missing" in a and "Plain:" in a
    assert "at most two sentences: what is happening, what the author directs attention to" in a
    assert "what the author wants the reader to take away, believe or do" in a
    assert ("what the reader should actually take away, naming hidden assumptions, opinion stated as fact, "
            "dependencies") in a
    assert "stance_profile" in a
    assert "{items}" in P.EML_REPAIR and "{problems}" in P.EML_REPAIR
    assert "Return only these items, corrected" in P.EML_REPAIR and "Do not repeat any other item" in P.EML_REPAIR
    assert "{last}" in P.EML_CONTINUE and "return only the remaining items" in P.EML_CONTINUE
    for words in ("the author holds", "it is assumed", "reportedly", "## Terms", "atem line"):
        assert words in P.COMPILE_SYSTEM


# ---------------------------------------------------------------------------
# Model mode, the real-model findings: truncation, normalization, a narrow repair, the lexicon floor
# ---------------------------------------------------------------------------

def _items_yaml(*items: str) -> str:
    return "nodes:\n" + "".join(items)


CLAIM_A = """  - id: P:claim/apples-need-a-second-variety
    type: claim
    name: apples need a second variety
    summary: Every apple tree needs a second apple variety nearby to set fruit.
    stance: axiom
    salience: high
    span: {lines: "7"}
    provenance: {mode: derived, sources: ['notes.md#L7'], confidence: 0.9, state: known}
"""
CLAIM_B = """  - id: P:claim/july-mowing-harms-the-orchard
    type: claim
    name: July mowing harms the orchard
    summary: Mowing the meadow strip in July would starve the pollinators the orchard depends on.
    stance: deduced
    salience: critical
    span: {lines: "17-20"}
    provenance: {mode: derived, sources: ['notes.md#L17-L20'], confidence: 0.8, state: known}
"""
CLAIM_C_CUT = """  - id: P:claim/the-strip-feeds-pollinators
    type: claim
    name: the strip feeds pollinators
    summary: The meadow strip exists to feed the pollinators the orchard depends on.
    stance: assumed
    salience: hig"""
CLAIM_C = CLAIM_C_CUT + """h
    span: {lines: "18-19"}
    provenance: {mode: derived, sources: ['notes.md#L18-L19'], confidence: 0.7, state: known}
"""
ENTITY = """  - id: E:person/mara-okafor
    type: person
    name: Mara Okafor
    summary: Mara Okafor keeps the orchard.
    span: {lines: "3"}
    provenance: {mode: derived, sources: ['notes.md#L3'], confidence: 0.9, state: known}
"""


@pytest.mark.parametrize("finish", ["length", None])
def test_a_cut_reply_is_salvaged_and_continued(notes, tmp_path, finish):
    """The real run: the reply was cut mid-item (`salience: hig`). Every complete item before the cut is kept, the
    cut one is dropped, and ONE continuation after the last complete id brings the rest. With no finish_reason,
    a tail that does not parse says the same."""
    tail = CLAIM_C_CUT if finish == "length" else CLAIM_C_CUT + 'h\n    span: {lines: "18'
    cut = _items_yaml(CLAIM_A, CLAIM_B, tail)
    fake = FakeModel([(cut, finish)], continuations=[_items_yaml(CLAIM_C, ENTITY)])
    text, stat = CD.read_source(notes)
    cosm, info = CD.derive_eml(text, source_name="notes.md", source_stat=stat, complete=fake,
                               lookup=lambda ws: {})
    assert fake.kinds() == ["passage", "continue", "atem"]
    cont = fake.calls[1][-1]["content"]
    assert "- P:claim/apples-need-a-second-variety\n- P:claim/july-mowing-harms-the-orchard" in cont
    assert "Continue the list after P:claim/july-mowing-harms-the-orchard" in cont
    assert lint_errors(cosm, tmp_path) == []
    by_id = {n["id"]: n for n in nodes_of(cosm)}
    assert {"P:claim/apples-need-a-second-variety", "P:claim/july-mowing-harms-the-orchard",
            "P:claim/strip-feeds-pollinators", "E:person/mara-okafor"} <= set(by_id)
    assert by_id["P:claim/strip-feeds-pollinators"]["salience"] == "high"   # the whole item, not the cut one
    assert info["continued"] == 1 and info["dropped"] == 0


def test_a_cut_continuation_loses_only_its_last_item(notes, tmp_path):
    fake = FakeModel([(_items_yaml(CLAIM_A, CLAIM_C_CUT), "length")],
                     continuations=[(_items_yaml(ENTITY, CLAIM_C_CUT), "length")])
    text, stat = CD.read_source(notes)
    cosm, info = CD.derive_eml(text, source_name="notes.md", source_stat=stat, complete=fake,
                               lookup=lambda ws: {})
    assert fake.kinds() == ["passage", "continue", "atem"], "one continuation, never a second"
    ids = {n["id"] for n in nodes_of(cosm)}
    assert {"P:claim/apples-need-a-second-variety", "E:person/mara-okafor"} <= ids
    assert info["dropped"] == 1 and lint_errors(cosm, tmp_path) == []


def test_a_reply_cut_before_its_first_item_ends_is_asked_again(notes, tmp_path):
    fake = FakeModel([("nodes:\n  - id: P:claim/x\n    type: cla", "length")],
                     continuations=[_items_yaml(CLAIM_A)])
    text, stat = CD.read_source(notes)
    cosm, _info = CD.derive_eml(text, source_name="notes.md", source_stat=stat, complete=fake,
                                lookup=lambda ws: {})
    assert "cut off before its first item ended" in fake.calls[1][-1]["content"]
    assert "P:claim/apples-need-a-second-variety" in {n["id"] for n in nodes_of(cosm)}


MISMATCHES = """```yaml
nodes:
  - id: P:claim/flowers-feed-insects
    type: statement
    name: flowers feed insects
    summary: The wildflowers of the meadow strip feed the insects that set the orchard's fruit.
    stance: Observe
    salience: hig
    roles: {holder: the writer}
    span: {lines: "4, 17"}
    links: [{rel: support, to: P:claim/not-in-this-text}]
    provenance: {mode: inferred, confidence: 90}
  - id: E:concept/pollinator-habitat
    type: concept
    name: pollinator habitat
    summary: Uncut wildflowers that feed the insects an orchard needs.
    span: {lines: "L18"}
    salience: medium
    links: [{rel: depends-on, to: flowers feed insects}]
    provenance: {mode: derived, sources: ['notes.md#L18'], confidence: "0.8", state: known}
  - id: E:organization/parish-council
    type: organization
    name: the parish council
    span: 17
    provenance: {mode: derived, sources: ['notes.md#L17'], confidence: 1.7, state: sure}
  - id: E:org/meadow-strip
    type: place
    name: meadow strip
    summary: The strip of meadow beside the orchard.
    lines: "17-19"
  - id: X:thing/the-bramley
    type: thing
    name: the Bramley by the gate
    summary: The old Bramley tree by the gate.
    span: "4"
    provenance: {mode: derived, sources: ['notes.md#L4'], confidence: 0.9}
  - id: T:action/leaf-mould-spread
    name: leaf mould spread
    summary: The volunteers spread leaf mould under the trees in March.
    agent: the orchard volunteers
    after: the parish council
    when: March
    span: {lines: [13]}
    provenance: {mode: derived, sources: ['notes.md#L13'], confidence: 0.9, state: known}
```"""


def test_every_mismatch_is_normalized_not_dropped(notes, tmp_path):
    fake = FakeModel([MISMATCHES])
    text, stat = CD.read_source(notes)
    cosm, info = CD.derive_eml(text, source_name="notes.md", source_stat=stat, complete=fake,
                               lookup=lambda ws: {})
    assert fake.kinds() == ["passage", "atem"], "nothing needed a repair turn"
    assert lint_errors(cosm, tmp_path) == []
    assert info["dropped"] == 0
    by_id = {n["id"]: n for n in nodes_of(cosm)}
    claim = by_id["P:claim/flowers-feed-insects"]                          # statement → claim
    assert (claim["type"], claim["stance"], claim["salience"]) == ("claim", "observed", "high")
    assert claim["span"] == {"lines": "4-17"}                              # "4, 17" → min-max
    assert claim["links"] == [{"pending": "supports P:claim/not-in-this-text: not an item of this twin"}]
    assert claim["provenance"] == {"mode": "derived", "confidence": 0.9, "sources": ["notes.md#L4-L17"],
                                   "state": "known"}                       # mode, percent, sources
    assert by_id["K:concept/pollinator-habitat"]["span"] == {"lines": "18"}  # moved E → K; "L18" → "18"
    assert by_id["K:concept/pollinator-habitat"]["provenance"]["confidence"] == 0.8
    council = by_id["E:org/parish-council"]                                # organization → org
    assert council["summary"] == "the parish council"                      # missing summary → the name
    assert council["span"] == {"lines": "17"}                              # a bare int → a string
    assert council["provenance"]["confidence"] == 1.0 and council["provenance"]["state"] == "known"
    strip = by_id["E:org/meadow-strip"]                                    # the id's declared kind is trusted
    assert strip["type"] == "org" and strip["span"] == {"lines": "17-19"}  # top-level lines → span
    assert strip["provenance"] == {"mode": "derived", "sources": ["notes.md#L17-L19"], "confidence": 0.7,
                                   "state": "known"}                       # missing provenance
    assert "E:thing/bramley-by-the-gate" in by_id                          # X:thing → E:thing
    event = by_id["T:event/leaf-mould-spread"]
    assert event["type"] == "event"                                        # T:action → event
    assert event["agent"] == {"pending": "agent: the orchard volunteers is not an item of this twin"}
    assert event["after"] == "E:org/parish-council"                        # a name given its id
    assert claim["roles"] == {"holder": "the writer"}                      # a role keeps its words
    habitat = by_id["K:concept/pollinator-habitat"]
    assert habitat["salience"] == "normal"                                 # medium → normal
    assert habitat["links"] == [{"rel": "depends-on", "to": "P:claim/flowers-feed-insects"}]
    assert info["normalized"] >= 18


def test_the_repair_never_asks_for_the_whole_list(notes, tmp_path):
    """A model whose repair answer regenerates everything: only the failing item is sent, and what comes back
    replaces only it."""
    bad = CLAIM_B.replace("stance: deduced", "stance: maybe")
    fake = FakeModel([_items_yaml(CLAIM_A, bad, ENTITY)], repairs=[_items_yaml(CLAIM_A, CLAIM_B, ENTITY)])
    text, stat = CD.read_source(notes)
    cosm, info = CD.derive_eml(text, source_name="notes.md", source_stat=stat, complete=fake,
                               lookup=lambda ws: {})
    assert fake.kinds() == ["passage", "repair", "atem"]
    sent = fake.calls[1][-1]["content"].split("These items did not pass the checks:", 1)[1]
    assert sent.count("- id: ") == 1 and "P:claim/july-mowing-harms-the-orchard" in sent
    assert "apples-need-a-second-variety" not in sent and "mara-okafor" not in sent
    ids = [n["id"] for n in nodes_of(cosm)]
    assert ids.count("P:claim/july-mowing-harms-the-orchard") == 1 and ids.count("E:person/mara-okafor") == 1
    assert {n["id"]: n for n in nodes_of(cosm)}["P:claim/july-mowing-harms-the-orchard"]["stance"] == "deduced"
    assert info["dropped"] == 0 and lint_errors(cosm, tmp_path) == []


def test_model_mode_keeps_the_feed_lexicon_floor(feed, notes, tmp_path):
    """The twin always has the FEED-grounded lexicon. A model term naming a floor word by one of its forms takes
    the floor term's place and id (its sense wins, FEED's grounding stays), and a claim that pointed at the
    model's id follows it; a model term beyond the floor is kept (the floor's count does not cap the model)."""
    orchards = """  - id: L:term/orchards
    type: term
    name: orchards
    summary: Pieces of land planted with fruit trees.
    sense: The community fruit garden on Hollins Lane.
    span: {lines: "3"}
    provenance: {mode: derived, sources: ['notes.md#L3'], confidence: 0.9, state: known}
"""
    mould = """  - id: L:term/leaf-mould
    type: term
    name: leaf mould
    summary: Fallen leaves left to rot into a dark mulch.
    span: {lines: "13"}
    provenance: {mode: derived, sources: ['notes.md#L13'], confidence: 0.8, state: known}
"""
    claim = CLAIM_A.replace("    span: {lines: \"7\"}", "    roles: {object: L:term/orchards}\n    span: {lines: \"7\"}")
    fake = FakeModel([_items_yaml(claim, orchards, mould)])
    text, stat = CD.read_source(notes)
    cosm, _info = CD.derive_eml(text, source_name="notes.md", source_stat=stat, complete=fake)
    assert lint_errors(cosm, tmp_path) == []
    by_id = {n["id"]: n for n in nodes_of(cosm)}
    terms = [i for i in by_id if i.startswith("L:")]
    floor = CD._term_table(text, CD._default_lookup)
    assert len(floor) == CD.TERMS_MIN
    assert len(terms) == len(floor) + 1, "every floor word once, and the model's own term beyond them"
    orchard = by_id["L:term/orchard"]
    assert "L:term/orchards" not in by_id
    assert orchard["sense"] == "The community fruit garden on Hollins Lane."         # the model's sense wins
    assert orchard["feed"] == {"word": "orchard", "pos": "noun", "origin": "feed"}  # FEED's grounding stays
    assert "pending" not in orchard and orchard["provenance"]["confidence"] == 0.9
    assert by_id["P:claim/apples-need-a-second-variety"]["roles"] == {"object": "L:term/orchard"}
    assert by_id["L:term/leaf-mould"]["feed"] == {"pending": "not in FEED"}
    assert by_id["L:term/pollinate"]["pending"] == CD.PENDING_FLOOR
    assert by_id["L:term/pollinate"]["sense"] == "To carry pollen to a flower so that it sets seed."
