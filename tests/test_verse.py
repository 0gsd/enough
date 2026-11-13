"""Verse by rules (enough/verse.py) and the fabulap a rules-mode decompile writes (lane C2b).

Four public-domain poems (tests/fixtures/fabula/verse/): Blake's *The Sick Rose* (1794, a clear abcb scheme),
Dickinson's *"Hope" is the thing with feathers* (1891, slant rhyme in common metre), Whitman's *A Noiseless Patient
Spider* (1891, unrhymed; three words FEED lacks), and the traditional ballad *Scarborough Fair* (a refrain line).
FEED is a fixture: the entries reflib/dict holds for every word of them (feed.json; a word FEED lacks is absent).
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from enough import canon_derive as CD, fabula, macrocosm, verse as V

REPO = Path(__file__).resolve().parent.parent
FIX = REPO / "tests" / "fixtures" / "fabula" / "verse"
NOW = dt.datetime(2026, 11, 5, 12, 0, tzinfo=dt.timezone.utc)
FEED = json.loads((FIX / "feed.json").read_text(encoding="utf-8"))["words"]
POEMS = ("the-sick-rose.txt", "hope.txt", "spider.txt", "scarborough-fair.txt")


def pron(words):
    return {w: FEED.get(w) for w in words}


def lookup(words):
    return {w: FEED.get(w.lower()) for w in words}


def text_of(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def rules_twin(name: str, **kw) -> tuple[str, dict]:
    kw.setdefault("source_stat", None)
    return CD.derive_emf(text_of(name), source_name=name, lookup=lookup, pron=pron, flavour="fabulap", now=NOW, **kw)


def items_of(cosm: str) -> dict:
    return {n["id"]: n for n in macrocosm.yaml_load(cosm)["nodes"]}


def lint(cosm: str, tmp: Path, name: str) -> list[str]:
    p = tmp / f"{name}.fabulap.cosm"
    p.write_text(cosm, encoding="utf-8")
    vol = macrocosm.load_volume(p)
    assert vol.refused is None, vol.refused
    return [f"{e.check} {e.item} {e.message}" for e in fabula.lint(vol).errors]


# ---------------------------------------------------------------------------
# The splitter
# ---------------------------------------------------------------------------

def test_read_poem_sets_the_header_apart_and_counts_lines_over_the_poem():
    rose = V.read_poem(text_of("the-sick-rose.txt"))
    assert rose.title == "The Sick Rose" and rose.header == (1, 2)
    assert [len(s.lines) for s in rose.stanzas] == [4, 4]
    assert [(vl.number, vl.src, vl.stanza) for vl in rose.lines][4] == (5, 9, 2)
    assert rose.lines[4].text == "Has found out thy bed"
    # no header: a poem that starts with its first stanza; a markdown heading is always one
    bare = V.read_poem("Roses are red,\nViolets are blue.\n\nSugar is sweet,\nAnd so are you.\n")
    assert bare.title is None and bare.header is None and len(bare.lines) == 4
    headed = V.read_poem("# Rain\n\nIt rains.\nIt pours.\n")
    assert headed.title == "Rain" and [vl.number for vl in headed.lines] == [1, 2]
    # a one-stanza poem keeps its stanza
    assert len(V.read_poem("One line,\nand another.\n").stanzas) == 1


def test_parse_ipa_syllables_stress_and_rhyme_sound():
    inv = V.parse_ipa("/ɪnˈvɪzəbəl/")
    assert inv.stresses == ("U", "P", "U", "U") and V.word_stress("invisible", inv) == ["x", "/", "x", "x"]
    assert V.parse_ipa("/dɪˈstrɔɪ/").rhyme == V.parse_ipa("/dʒɔɪ/").rhyme == "ɔɪ"
    assert V.word_stress("the", V.parse_ipa("/ðə/")) == ["x"] and V.word_stress("rose", V.parse_ipa("/roʊz/")) == ["/"]
    work = V.parse_ipa("/ˈnidəlˌwɜrk/")
    assert work.rhyme == "ɜrk" and work.tail == 1, "a compound rhymes on its last stress"
    assert V.parse_ipa("") is None and V.parse_ipa(None) is None


def test_decap_keeps_names_and_drops_line_initial_capitals():
    text = text_of("the-sick-rose.txt")
    assert "O Rose" not in V.decap(text) and "o Rose thou" in V.decap(text)
    assert V.decap(text).splitlines()[:2] == text.splitlines()[:2], "the header is left as it is"
    names = CD.entity_candidates(V.decap(text))
    assert "Sick Rose" in names and not {"Has", "That", "The", "In", "Does", "And", "Of"} & set(names)


# ---------------------------------------------------------------------------
# The rules' fabulap, poem by poem
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", POEMS)
def test_every_rules_fabulap_passes_the_reader_and_the_fabula_lint(name, tmp_path):
    cosm, info = rules_twin(name)
    assert lint(cosm, tmp_path, name) == []
    doc = macrocosm.yaml_load(cosm)
    assert doc["flavour"] == "fabulap" and doc["derived"]["mode"] == "rules" and info["mode"] == "rules"
    items = items_of(cosm)
    poem = V.read_poem(text_of(name))
    assert sum(1 for i in items if i.startswith("C:line/")) == len(poem.lines)
    assert sum(1 for i in items if i.startswith("C:part/")) == len(poem.stanzas)
    for vl in poem.lines:
        line = items[f"C:line/{vl.number}"]
        assert line["span"] == {"lines": str(vl.src)} and line["part"] == f"C:part/stanza-{vl.stanza}"
        assert line["stance"] == "observed" and "text" not in line, "no words unless the poem may be copied"
        assert line["name"] == f"line {vl.number}"
    # no model: no readings, devices of meaning, voice, claims or events
    assert not [i for i in items if i.startswith(("P:", "T:", "K:", "C:voice", "I:", "N:"))]
    assert doc["atem"]["push"] == {"pending": CD.PENDING_NO_MODEL}


def test_the_sick_rose_scheme_metre_and_a_question_for_the_word_feed_lacks():
    cosm, _ = rules_twin("the-sick-rose.txt")
    items = items_of(cosm)
    # the scheme is the rhymes' and the form's, never a part's summary (scan … as rhyme adds it; Thym 20.9)
    assert items["C:part/stanza-1"]["summary"] == "Stanza 1; lines 1-4 of the poem, 4 lines."
    assert items["C:form/shape"]["form"] == "two quatrains, rhymed abcb"
    joy = items["C:rhyme/joy-destroy"]
    assert (joy["scheme"], joy["quality"], joy["lines"], joy["stance"]) == ("e", "full", ["C:line/6", "C:line/8"],
                                                                            "deduced")
    assert items["C:rhyme/worm-storm"]["quality"] == "slant"
    assert [items[f"C:line/{n}"]["rhyme"] for n in range(1, 9)] == list("abcbdefe")
    # "O" is not in FEED: line 1's scansion is a question, never a guess, and the metre leaves it out
    one = items["C:line/1"]
    assert one["stresses"] == {"pending": 'how is line 1 scanned? FEED does not hold "o"'}
    assert one["syllables"] == one["stresses"] and "metre" not in one
    assert one["provenance"]["confidence"] == 1.0
    two = items["C:line/2"]
    assert two["syllables"] == 6 and two["stresses"].replace(" | ", " ") == "x x / x x /"
    assert two["provenance"]["confidence"] == 0.7 and two["ending"] == "stopped"
    assert items["C:line/5"]["ending"] == "run-on" and items["C:line/8"]["ending"] == "stopped"
    metre = next(v for k, v in items.items() if k.startswith("C:metre/"))
    assert metre["stance"] == "deduced" and "C:line/1" not in metre["lines"] and len(metre["lines"]) == 7
    assert metre["provenance"]["confidence"] < 0.8, "seven of eight lines scanned: confidence says so"


def test_hope_slant_rhymes_and_common_metre():
    items = items_of(rules_twin("hope.txt")[0])
    soul = items["C:rhyme/soul-all"]
    assert soul["quality"] == "slant" and soul["sound"] == "-oʊl"
    assert items["C:rhyme/heard-bird"]["quality"] == "full" and items["C:rhyme/storm-warm"]["quality"] == "full"
    metre = items["C:metre/iambic-tetrameter-and-trimeter-alternating"]
    assert (metre["foot"], metre["feet"], metre["basis"]) == ("iamb", "3-4", "accentual-syllabic")
    assert [d["line"] for d in metre.get("departures", [])] == ["C:line/1"]
    assert items["C:line/2"]["stresses"].count("|") == 2, "three feet, two bars"


def test_an_unrhymed_poem_is_free_verse_and_each_missing_word_is_named():
    items = items_of(rules_twin("spider.txt")[0])
    metre = items["C:metre/free-verse"]
    assert (metre["foot"], metre["basis"]) == ("none", "free") and "feet" not in metre
    for n, word in ((2, "mark'd"), (3, "mark'd"), (4, "launch'd"), (6, "o"), (9, "form'd")):
        assert items[f"C:line/{n}"]["stresses"]["pending"].endswith(f'FEED does not hold "{word}"'), n
    assert isinstance(items["C:line/5"]["syllables"], int)


def test_scarborough_fair_a_refrain_line_and_a_rhyme_sound_again():
    items = items_of(rules_twin("scarborough-fair.txt")[0])
    refrain = items["C:device/refrain-1"]
    assert (refrain["figure"], refrain["where"], refrain["stance"]) == ("refrain", ["C:line/2", "C:line/6"],
                                                                        "observed")
    assert items["C:rhyme/fair-there"]["quality"] == "full"
    assert items["C:rhyme/thyme-mine"]["quality"] == "slant" and items["C:rhyme/thyme-mine-d"]["scheme"] == "d"
    assert items["C:rhyme/shirt-needlework"]["quality"] == "slant"
    # "Scarborough" is not in FEED: line 1 is not scanned, but its end word is, so it still rhymes
    assert "pending" in items["C:line/1"]["stresses"] and items["C:line/1"]["rhyme"] == "a"
    metre = next(v for k, v in items.items() if k.startswith("C:metre/"))
    assert metre["basis"] == "accentual" and metre["foot"] == "mixed", "a rhymed poem with no clear foot is not free"


def test_a_repeated_whole_stanza_is_a_refrain(tmp_path):
    text = "Sing\n\nThe wind is high,\nThe boat is low.\n\nO row, row on,\nRow as we go.\n\n" \
           "The night is near,\nThe tide runs slow.\n\nO row, row on,\nRow as we go.\n"
    cosm, _ = CD.derive_emf(text, source_name="row.txt", source_stat=None, lookup=lookup, pron=pron,
                            flavour="fabulap")
    assert lint(cosm, tmp_path, "row") == []
    items = items_of(cosm)
    assert items["C:part/stanza-2"]["division"] == items["C:part/stanza-4"]["division"] == "refrain"
    assert items["C:part/stanza-1"]["division"] == "stanza"
    assert "come back as stanza 4" in items["C:part/stanza-2"]["summary"]
    assert not [i for i in items if i.startswith("C:device/refrain")], "a whole repeated stanza is a part, not a device"


def test_a_lines_text_only_when_the_poem_may_be_copied(tmp_path):
    cosm, info = rules_twin("the-sick-rose.txt", copyable=True)
    items = items_of(cosm)
    assert items["C:line/5"]["text"] == items["C:line/5"]["name"] == "Has found out thy bed"
    assert items["C:line/6"]["text"] == "Of crimson joy:" and info["copyable"] is True
    assert lint(cosm, tmp_path, "copy") == []
    assert "Has found out thy bed" not in rules_twin("the-sick-rose.txt")[0]


def test_no_feed_makes_every_lines_scansion_a_question(tmp_path):
    cosm, _ = CD.derive_emf(text_of("hope.txt"), source_name="hope.txt", source_stat=None, lookup=lambda w: {},
                            flavour="fabulap")
    assert lint(cosm, tmp_path, "nofeed") == []
    items = items_of(cosm)
    assert all("pending" in items[f"C:line/{n}"]["stresses"] for n in range(1, 9))
    assert all("pending" in items[f"C:line/{n}"]["rhyme"] for n in range(1, 9))
    metre = items["C:metre/unscanned"]
    assert "pending" in metre["foot"] and metre["provenance"]["state"] == "pending"
    assert not [i for i in items if i.startswith("C:rhyme/")]


def test_the_sick_rose_example_of_the_specification_still_reads():
    vol = macrocosm.load_volume(REPO / "tests" / "fixtures" / "fabula" / "poems" / "the-sick-rose.txt.fabulap.cosm")
    assert vol.refused is None and fabula.lint(vol).errors == []


# ---------------------------------------------------------------------------
# A fabulap told as a short
# ---------------------------------------------------------------------------

def test_a_fabulap_is_told_stanza_by_stanza():
    stat = {"sha256": "0" * 64, "size": 232, "mtime_ns": 1}
    cosm, _ = rules_twin("the-sick-rose.txt", copyable=True, source_stat=stat)
    md, info = CD.compile_short(cosm, order="told", source_text=text_of("the-sick-rose.txt"), now=NOW)
    assert info["mode"] == "rules"
    body = md.split("\n---\n")[0]
    assert body.index("## How it is built") < body.index("## Stanza 1") < body.index("## Stanza 2")
    assert "- Line 5 (x / | / x /, rhyme d): Has found out thy bed" in body
    assert "Has found out thy bed" in body and "Anapaestic dimeter" in body
    assert md.rstrip().endswith("*a short of the-sick-rose.txt, told as the author told it, compiled from its "
                                "fabula on 2026-11-05 by rules, without a model*")
    # without the words, a line is told by its number, stresses and rhyme
    bare, _ = CD.compile_short(rules_twin("the-sick-rose.txt")[0], order="told", now=NOW)
    assert "Has found out thy bed" not in bare and "- Line 6 (" in bare


def test_readings_are_told_as_whose_they_are():
    doc = {"oes": "fabula/1", "flavour": "fabulap", "id": "fabula/x", "name": "X", "nodes": [
        {"id": "P:reading/a", "type": "reading", "name": "a", "summary": "The worm is a canker.",
         "stance": "opinion", "of": ["E:thing/worm"], "whose": {"by": "model"}},
        {"id": "E:thing/worm", "type": "thing", "name": "worm", "summary": "A worm."}]}
    md, _ = CD.compile_short(doc, order="weight", now=NOW)
    assert "## How it can be read" in md and "One reading, the model's own guess: The worm is a canker." in md
