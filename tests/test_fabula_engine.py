"""The fabula engine of 0.6 (lane C2b): what a decompile writes beyond the first edition's six modules.

Prose (a fabulan): the rules' structure (sections, what the file states of its making), the whole-text request's
items (I, N, C:device, C:voice, R) with honest stances, a whole-text request that fails landing the twin without its
items and saying so, rules mode. Verse (a fabulap) through a scripted model: devices, voice, two rival readings of one
image side by side, the rules' lines under the model's items. The dialectic carried over on a re-decompile. The
prompts' size caps. No real model: every `complete` here is scripted; FEED is a fixture (tests/fixtures/fabula/verse/
feed.json, entries copied from reflib/dict).
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from enough import canon_derive as CD, canon_prompts as P, dialectic, fabula, macrocosm

REPO = Path(__file__).resolve().parent.parent
FIX = REPO / "tests" / "fixtures" / "fabula"
NOW = dt.datetime(2026, 11, 5, 12, 0, tzinfo=dt.timezone.utc)
FEED = json.loads((FIX / "verse" / "feed.json").read_text(encoding="utf-8"))["words"]


def lookup(words):
    return {w: FEED.get(w.lower()) for w in words}


def pron(words):
    return {w: FEED.get(w) for w in words}


def errors_of(cosm: str, tmp: Path, name: str = "twin.cosm") -> list[str]:
    p = tmp / name
    p.write_text(cosm, encoding="utf-8")
    vol = macrocosm.load_volume(p)
    assert vol.refused is None, vol.refused
    return [f"{e.check} {e.item} {e.message}" for e in fabula.lint(vol).errors]


def doc_of(cosm: str) -> dict:
    return macrocosm.yaml_load(cosm)


def by_id(cosm: str) -> dict:
    return {n["id"]: n for n in doc_of(cosm)["nodes"]}


# ---------------------------------------------------------------------------
# A scripted model
# ---------------------------------------------------------------------------

def call_kind(messages: list[dict]) -> str:
    last = messages[-1]["content"]
    if "did not pass the checks" in last:
        return "repair"
    if messages[0]["content"].startswith("You write the atem"):
        return "whole"
    if messages[0]["content"].startswith("You read one passage of a poem"):
        return "verse"
    return "passage"


class Script:
    """Answers by the kind of request: a passage of prose, a passage of verse, the whole-text request, a repair."""

    def __init__(self, **answers):
        self.answers = {k: list(v) if isinstance(v, list) else [v] for k, v in answers.items()}
        self.calls: list[list[dict]] = []

    def __call__(self, messages, max_tokens=None):
        self.calls.append(messages)
        q = self.answers.get(call_kind(messages)) or ["nodes: []"]
        text = q.pop(0) if len(q) > 1 else q[0]
        return text, {"model": "scripted", "finish_reason": "stop"}

    def kinds(self) -> list[str]:
        return [call_kind(m) for m in self.calls]


ESSAY = (FIX / "essay" / "commons.md").read_text(encoding="utf-8")

ESSAY_PASSAGE = """nodes:
  - id: P:claim/commons-need-rules
    type: claim
    name: a commons lasts while its users agree on rules
    summary: The Hollins Lane meadow lasts only while the volunteers who use the meadow agree on rules.
    stance: deduced
    salience: high
    roles: {holder: E:person/ines-varga, object: K:concept/commons}
    span: {lines: "12"}
    provenance: {mode: derived, sources: ['commons.md#L12'], confidence: 0.8, state: known}
  - id: K:concept/commons
    type: concept
    name: commons
    summary: Land that a group shares and keeps by agreed rules.
    span: {lines: "11-12"}
    provenance: {mode: derived, sources: ['commons.md#L11-L12'], confidence: 0.8, state: known}
  - id: E:person/elinor-ostrom
    type: person
    name: Elinor Ostrom
    summary: Elinor Ostrom, who studied commons.
    span: {lines: "12"}
    provenance: {mode: derived, sources: ['commons.md#L12'], confidence: 0.9, state: known}
"""

ESSAY_ATEM = """line: The volunteers who keep the Hollins Lane meadow decide by consent, because a commons lasts only while its users agree on rules.
focus: How the meadow's volunteers keep it and why they decide by consent.
push: Join the volunteers and take part in decisions by consent.
pull: The essay assumes consent scales; it leaves out the orchard's money.
stance_profile: {deduced: 1}
"""

ESSAY_WHOLE = ESSAY_ATEM + """nodes:
  - id: N:audience/volunteers
    type: audience
    name: The meadow's volunteers
    summary: The essay is written for the meadow's volunteers and for people thinking of joining them.
    stance: observed
    who: the volunteers of the Hollins Lane meadow, and would-be volunteers
    span: {lines: "7"}
    provenance: {mode: derived, sources: ['commons.md#L7'], confidence: 0.95, state: known}
  - id: N:aim/recruit
    type: aim
    name: Bring in new volunteers
    summary: The essay sets out to bring new volunteers to the meadow.
    stance: deduced
    measure: Someone joins after reading it.
    span: {lines: "7"}
    provenance: {mode: derived, sources: ['commons.md#L7'], confidence: 0.9, state: known}
  - id: N:decision/consent
    type: decision
    name: Decide by consent
    summary: The volunteers chose to decide by consent rather than by vote.
    stance: observed
    chose: consent
    because: a vote leaves a losing side, and a small group cannot afford one
    span: {lines: "16-17"}
    provenance: {mode: derived, sources: ['commons.md#L16-L17'], confidence: 0.9, state: known}
  - id: N:exclusion/finances
    type: exclusion
    name: Not the orchard's finances
    summary: The essay leaves out the orchard's finances, which the treasurer reports on.
    stance: observed
    because: the treasurer reports on them
    span: {lines: "19"}
    provenance: {mode: derived, sources: ['commons.md#L19'], confidence: 0.9, state: known}
  - id: I:influence/ostrom
    type: influence
    name: Ostrom's work on the commons
    summary: Elinor Ostrom's study of commons shapes the essay's case for rules.
    stance: observed
    roles: {source: E:person/elinor-ostrom, 'on': P:claim/commons-need-rules}
    how: the idea that a commons lasts only while its users agree on rules
    span: {lines: "12"}
    provenance: {mode: derived, sources: ['commons.md#L12'], confidence: 0.9, state: known}
  - id: C:voice/we
    type: voice
    name: The volunteers, as we
    summary: The essay speaks as the volunteers, in the first person plural.
    stance: observed
    perspective: first
    tone: plain, inviting
    span: {lines: "16"}
    provenance: {mode: derived, sources: ['commons.md#L16'], confidence: 0.8, state: known}
  - id: C:device/appeal
    type: device
    name: An appeal to authority
    summary: The essay leans on Ostrom's name to carry its claim about rules.
    stance: opinion
    figure: appeal to authority
    where: [P:claim/commons-need-rules]
    span: {lines: "12"}
    provenance: {mode: derived, sources: ['commons.md#L12'], confidence: 0.9, state: known}
  - id: E:thing/not-allowed-here
    type: thing
    name: something the whole request may not write
    summary: An entity, which only the passages write.
    span: {lines: "7"}
    provenance: {mode: derived, sources: ['commons.md#L7'], confidence: 0.9, state: known}
"""


def test_prose_rules_structure_parts_and_making():
    items = {it["id"]: it for it in CD.structure_nodes(ESSAY, "commons.md")}
    parts = [it for it in items.values() if it["type"] == "part"]
    assert [p["name"] for p in parts] == ["What the meadow is", "How we decide"], "the title heading is no part"
    meadow = items["C:part/what-the-meadow-is"]
    assert meadow["division"] == "section" and meadow["number"] == 1 and meadow["span"] == {"lines": "9-12"}
    assert items["C:part/how-we-decide"]["number"] == 2 and items["C:part/how-we-decide"]["span"] == {"lines": "14-21"}
    assert meadow["stance"] == "observed" and meadow["provenance"]["confidence"] == 1.0
    assert items["R:maker/ines-varga"]["capacity"] == "author" and items["R:maker/ines-varga"]["span"] == {"lines": "1-4"}
    assert items["R:release/version-2"]["version"] == "2"
    lic = next(it for it in items.values() if it["type"] == "licence")
    assert (lic["identifier"], lic["holder"], lic["year"], lic["span"]) == ("all rights reserved", "Ines Varga",
                                                                            "2026", {"lines": "21"})
    # a text with no section headings and nothing said of its making has no structure items
    assert CD.structure_nodes("# Title\n\nOne paragraph.\n\nAnother.\n", "t.md") == []
    nested = CD.structure_nodes("# T\n\n## A\n\ntext\n\n### A1\n\nmore\n\n## B\n\nend\n", "t.md")
    assert [(p["name"], p.get("of"), p["number"]) for p in nested] == [("A", None, 1), ("A1", "C:part/a", 1),
                                                                       ("B", None, 2)]


def test_prose_model_mode_writes_the_whole_text_items_with_honest_stances(tmp_path):
    fake = Script(passage=ESSAY_PASSAGE, whole=ESSAY_WHOLE)
    cosm, info = CD.derive_emf(ESSAY, source_name="commons.md", source_stat=None, complete=fake, lookup=lambda w: {},
                               now=NOW)
    assert fake.kinds() == ["passage", "whole"], "one passage, then ONE whole-text request; nothing to repair"
    assert errors_of(cosm, tmp_path) == []
    items = by_id(cosm)
    doc = doc_of(cosm)
    assert doc["flavour"] == "fabulan" and "dropped" not in doc["derived"]
    assert doc["atem"]["push"] == "Join the volunteers and take part in decisions by consent."
    # the whole-text items, each with its stance; a model's opinion capped at 0.5, an observed one kept
    assert items["N:audience/meadows-volunteers"]["stance"] == "observed"
    assert items["N:audience/meadows-volunteers"]["provenance"]["confidence"] == 0.95
    assert items["N:aim/bring-in-new-volunteers"]["stance"] == "deduced" and items["N:aim/bring-in-new-volunteers"]["provenance"]["confidence"] == 0.7
    assert items["N:decision/decide-by-consent"]["chose"] == "consent"
    assert items["N:exclusion/not-the-orchards-finances"]["stance"] == "observed"
    assert items["C:device/appeal-to-authority"]["provenance"]["confidence"] == 0.5
    assert items["C:device/appeal-to-authority"]["where"] == ["P:claim/commons-lasts-while-its-users-agree-on-rules"]
    assert items["C:voice/volunteers-as-we"]["perspective"] == "first"
    assert items["I:influence/ostroms-work-on-the-commons"]["roles"]["source"] == "E:person/elinor-ostrom"
    assert "E:thing/something-whole-request-may-not-write" not in items, "the whole request writes no entities"
    assert info["whole"] == {"items": 7, "dropped": 0, "ignored": 1, "repaired": False}
    # the passage's items as before, and the rules' parts and making beside them
    assert items["P:claim/commons-lasts-while-its-users-agree-on-rules"]["stance"] == "deduced"
    assert items["C:part/what-the-meadow-is"]["provenance"]["confidence"] == 1.0
    assert items["R:maker/ines-varga"]["stance"] == "observed"
    # the whole-text request: the atem's own prompt, then the items; the digest names the passages' items by id
    system, user = fake.calls[-1][0]["content"], fake.calls[-1][1]["content"]
    assert system.startswith(P.ATEM_SYSTEM) and "No item is better than a guess" in system
    assert "P:claim/commons-lasts-while-its-users-agree-on-rules (deduced, high)" in user and "C:part/what-the-meadow-is" in user
    # module order: I L E K N C R P T X
    letters = [n["id"][0] for n in doc["nodes"]]
    assert letters == sorted(letters, key=CD.MODULES_ALL.index)


BAD_WHOLE = ESSAY_ATEM + """nodes:
  - id: N:decision/consent
    type: decision
    name: Decide by consent
    summary: The volunteers decide by consent.
    stance: observed
    span: {lines: "16"}
  - id: C:line/1
    type: line
    name: a line, in prose
    summary: Not a kind a fabulan holds.
    stance: observed
    number: 1
  - id: N:audience/volunteers
    type: audience
    name: The volunteers
    summary: The meadow's volunteers.
    stance: observed
    span: {lines: "7"}
"""


def test_a_whole_text_reply_that_fails_lands_the_twin_without_it_and_says_so(tmp_path):
    """The decision lacks its required `chose` and the repair does not fix it; a C:line is not a fabulan's (and not a
    kind the whole request writes): the twin lands with what passed, `derived.dropped` counts the failure."""
    fake = Script(passage=ESSAY_PASSAGE, whole=BAD_WHOLE, repair="nodes:\n  - id: N:decision/consent\n    type: "
                                                                 "decision\n    name: Decide by consent\n")
    cosm, info = CD.derive_emf(ESSAY, source_name="commons.md", source_stat=None, complete=fake,
                               lookup=lambda w: {}, now=NOW)
    assert fake.kinds() == ["passage", "whole", "repair"]
    assert "Decide by consent" in fake.calls[-1][-1]["content"] and "chose" in fake.calls[-1][-1]["content"]
    assert errors_of(cosm, tmp_path) == []
    items = by_id(cosm)
    assert "N:decision/decide-by-consent" not in items and "C:line/1" not in items
    assert items["N:audience/volunteers"]["stance"] == "observed"
    assert info["whole"]["dropped"] == 1 and info["whole"]["ignored"] == 1 and info["whole"]["repaired"]
    assert doc_of(cosm)["derived"]["dropped"] == info["dropped"] == 1
    assert doc_of(cosm)["atem"]["line"].startswith("The volunteers who keep"), "the atem still lands"


def test_an_unreadable_whole_reply_still_gives_its_atem_and_writes_no_guess(tmp_path):
    reply = ESSAY_ATEM + "nodes:\n  - id: N:aim/x\n    type: aim\n    name: [unclosed\n"
    fake = Script(passage=ESSAY_PASSAGE, whole=reply, repair="I cannot.")
    cosm, info = CD.derive_emf(ESSAY, source_name="commons.md", source_stat=None, complete=fake,
                               lookup=lambda w: {}, now=NOW)
    assert errors_of(cosm, tmp_path) == []
    assert not [i for i in by_id(cosm) if i[0] in "IN"]
    assert doc_of(cosm)["atem"]["focus"].startswith("How the meadow's volunteers")
    assert info["whole"]["items"] == 0 and info["whole"]["dropped"] >= 1
    # a whole reply that is only the atem (the first edition's answer) writes nothing and drops nothing
    fake2 = Script(passage=ESSAY_PASSAGE, whole=ESSAY_ATEM)
    cosm2, info2 = CD.derive_emf(ESSAY, source_name="commons.md", source_stat=None, complete=fake2,
                                 lookup=lambda w: {}, now=NOW)
    assert info2["whole"] == {"items": 0, "dropped": 0, "ignored": 0, "repaired": False}
    assert fake2.kinds() == ["passage", "whole"] and "dropped" not in doc_of(cosm2)["derived"]


def test_prose_rules_mode_writes_only_what_rules_read(tmp_path):
    cosm, info = CD.derive_emf(ESSAY, source_name="commons.md", source_stat=None, lookup=lambda w: {}, now=NOW)
    assert errors_of(cosm, tmp_path) == []
    items = by_id(cosm)
    assert info["mode"] == "rules" and info["whole"] is None
    assert not [i for i in items if i[0] in "IKNPT"], "no intent, inspiration, concepts, claims or events by rules"
    assert {"C:part/what-the-meadow-is", "C:part/how-we-decide", "R:maker/ines-varga"} <= set(items)
    for it in items.values():
        if it["id"][0] in "CR":
            assert it["stance"] == "observed" and it["provenance"]["confidence"] == 1.0 and "pending" not in it
        else:
            assert it["provenance"]["confidence"] == 0.3 and it["pending"] == CD.PENDING_NO_MODEL


# ---------------------------------------------------------------------------
# Verse through a scripted model
# ---------------------------------------------------------------------------

ROSE = (FIX / "verse" / "the-sick-rose.txt").read_text(encoding="utf-8")

ROSE_PASSAGE = """nodes:
  - id: C:device/worm-symbol
    type: device
    name: The worm as a symbol
    summary: The worm is given flight, love and a secret, so it stands for something the poem never names.
    stance: deduced
    figure: symbol
    where: [C:line/2, C:line/7]
    effect: The image stays open.
    span: {lines: "5-11"}
    provenance: {mode: derived, sources: ['the-sick-rose.txt#L5-L11'], confidence: 0.8, state: known}
  - id: C:device/run-on
    type: device
    name: Enjambment into the last line
    summary: Line 7 runs on into line 8, so the love arrives before what it does.
    stance: observed
    figure: enjambment
    where: C:line/7
    span: {lines: "11-12"}
    provenance: {mode: derived, sources: ['the-sick-rose.txt#L11-L12'], confidence: 0.9, state: known}
  - id: C:voice/speaker-to-rose
    type: voice
    name: A speaker to the rose
    summary: An unnamed speaker addresses the rose as thou.
    stance: observed
    perspective: second
    tone: grave
    roles: {speaker: {pending: "who speaks: the poet, a witness, a lover?"}, addressee: E:thing/rose}
    span: {lines: "4-12"}
    provenance: {mode: derived, sources: ['the-sick-rose.txt#L4-L12'], confidence: 0.8, state: known}
  - id: P:reading/worm-is-a-canker
    type: reading
    name: The worm is a canker
    summary: Read plainly, the worm is a grub that eats into the rose, and the poem is about blight.
    stance: observed
    of: E:thing/worm
    whose: model
    grounds:
      - {of: C:line/2, because: 'a worm is the plain word for a grub'}
      - just a sentence with no item
    span: {lines: "5-12"}
    provenance: {mode: derived, sources: ['the-sick-rose.txt#L5-L12'], confidence: 0.9, state: known}
  - id: P:reading/worm-is-desire
    type: reading
    name: The worm is a lover's desire
    summary: The worm is a lover whose hidden desire spoils what it loves; the bed of crimson joy is a bed of love.
    stance: opinion
    of: [E:thing/worm, L:term/bed]
    whose: {by: model}
    grounds:
      - {of: C:line/7, because: 'the worm has a love that is dark and secret'}
      - {of: C:line/6, because: 'crimson joy reads as passion'}
    span: {lines: "9-12"}
    provenance: {mode: derived, sources: ['the-sick-rose.txt#L9-L12'], confidence: 0.4, state: known}
  - id: L:term/bed
    type: term
    name: bed
    summary: The place the worm finds.
    sense: A flower bed, and a bed to sleep or love in.
    span: {lines: "9"}
    provenance: {mode: derived, sources: ['the-sick-rose.txt#L9'], confidence: 0.7, state: known}
  - id: E:thing/rose
    type: thing
    name: rose
    summary: The rose the poem addresses and calls sick.
    span: {lines: "4"}
    provenance: {mode: derived, sources: ['the-sick-rose.txt#L4'], confidence: 0.9, state: known}
  - id: E:thing/worm
    type: thing
    name: worm
    summary: The invisible worm that flies in the night.
    span: {lines: "5-6"}
    provenance: {mode: derived, sources: ['the-sick-rose.txt#L5-L6'], confidence: 0.9, state: known}
  - id: C:line/1
    type: line
    name: O Rose thou art sick
    summary: The model's own line item, which the rules own.
    stance: observed
    number: 1
"""

ROSE_WHOLE = """line: An unseen worm finds a rose's bed of crimson joy at night, and its dark secret love destroys the rose's life.
focus: A speaker tells a rose that it is sick, and names the cause.
push: Something loved in secret destroys what it loves.
pull: The poem never says what the rose or the worm stands for.
nodes:
  - id: R:maker/blake
    type: maker
    name: William Blake, as author
    summary: The poem's heading names William Blake as its poet.
    stance: observed
    capacity: author
    span: {lines: "2"}
    provenance: {mode: derived, sources: ['the-sick-rose.txt#L2'], confidence: 0.9, state: known}
  - id: R:release/songs-of-experience
    type: release
    name: Songs of Experience
    summary: The heading says the poem appeared in Songs of Experience, 1794.
    stance: observed
    venue: Songs of Experience
    at: '1794'
    span: {lines: "2"}
    provenance: {mode: derived, sources: ['the-sick-rose.txt#L2'], confidence: 0.9, state: known}
  - id: C:device/not-here
    type: device
    name: A device the whole request may not write for verse
    summary: Devices of a poem come from its stanzas.
    stance: deduced
    figure: metaphor
"""


def test_verse_model_mode_readings_side_by_side_devices_voice_and_the_rules_lines(tmp_path):
    fake = Script(verse=ROSE_PASSAGE, whole=ROSE_WHOLE)
    cosm, info = CD.derive_emf(ROSE, source_name="the-sick-rose.txt", source_stat=None, complete=fake,
                               lookup=lookup, pron=pron, flavour="fabulap", now=NOW)
    assert fake.kinds() == ["verse", "whole"], "one passage (the poem is short), then the whole"
    assert errors_of(cosm, tmp_path) == []
    doc = doc_of(cosm)
    items = by_id(cosm)
    assert doc["flavour"] == "fabulap" and doc["name"] == "The Sick Rose"
    # the passage the model read: whole stanzas, each line with its file line and its poem number
    user = fake.calls[0][1]["content"]
    assert "4| [1] O Rose thou art sick." in user and "12| [8] Does thy life destroy." in user
    assert "1| The Sick Rose" in user, "the header is read with the first stanza"
    # two rival readings of the worm, side by side, both the model's own, guesses: never linked as one winning
    canker, desire = items["P:reading/worm-is-a-canker"], items["P:reading/worm-is-a-lovers-desire"]
    for r in (canker, desire):
        assert r["whose"] == {"by": "model"} and r["stance"] == "opinion"
        assert r["provenance"]["confidence"] <= 0.5 and "links" not in r
    assert canker["of"] == ["E:thing/worm"] and canker["grounds"] == [
        {"of": "C:line/2", "because": "a worm is the plain word for a grub"}], "a ground naming nothing is dropped"
    assert desire["of"] == ["E:thing/worm", "L:term/bed"]
    assert [g["of"] for g in desire["grounds"]] == ["C:line/7", "C:line/6"]
    # devices and voice: a device's where is a list of lines; the speaker stays a question
    assert items["C:device/worm-as-a-symbol"]["where"] == ["C:line/2", "C:line/7"]
    assert items["C:device/enjambment-into-the-last-line"]["where"] == ["C:line/7"]
    voice = items["C:voice/speaker-to-the-rose"]
    assert voice["roles"]["speaker"] == {"pending": "who speaks: the poet, a witness, a lover?"}
    assert voice["roles"]["addressee"] == "E:thing/rose"
    # the lines are the rules', not the model's: no text (not copyable), the rules' summary
    assert items["C:line/1"]["summary"] == "Line 1 of the poem, the first of stanza 1." and "text" not in items["C:line/1"]
    assert sum(1 for i in items if i.startswith("C:line/")) == 8
    assert items["L:term/bed"]["sense"] == "A flower bed, and a bed to sleep or love in."
    # the whole: a named maker and release, observed; a device the verse whole request may not write is ignored
    assert items["R:maker/william-blake-as-author"]["stance"] == "observed"
    assert items["R:release/songs-of-experience"]["venue"] == "Songs of Experience"
    assert info["whole"]["ignored"] == 1 and not [i for i in items if "not-here" in i or "may-not" in i]


def test_verse_prompt_is_the_verse_one_and_carries_the_rules():
    s = P.VERSE_SYSTEM.format(source="x.txt")
    for words in ("never invent", "C:line/n", "whose {by: model}", "write both; never choose", "pending",
                  "confidence at most 0.5", "No pronouns"):
        assert words in s, words
    for stance in CD.STANCES:
        assert stance in s


# ---------------------------------------------------------------------------
# The prompts' sizes (a small local model reads each passage's prompt once per passage)
# ---------------------------------------------------------------------------

def test_prompt_size_caps():
    long_name = "a-rather-long-file-name-for-a-poem.txt"
    assert len(P.EMF_SYSTEM.format(source=long_name)) < 2000, "unchanged"
    assert len(P.VERSE_SYSTEM.format(source=long_name)) < 2000
    for fl in ("fabulan", "fabulap"):
        msgs = CD.whole_messages(ESSAY, source=long_name, flavour=fl, passage_atems=[], items=[])
        assert msgs[0]["content"].startswith(P.ATEM_SYSTEM), "the atem's definitions stay the owner's, first"
        assert len(msgs[0]["content"]) < CD.WHOLE_SYSTEM_MAX
        for stance in ("observed", "deduced", "opinion"):
            assert stance in msgs[0]["content"]
    # the digest is bounded however many items the passages found
    many = [{"id": f"P:claim/c{i}", "type": "claim", "summary": "x " * 200, "stance": "observed",
             "salience": "normal"} for i in range(200)]
    many += [{"id": f"E:thing/t{i}", "type": "thing", "name": f"thing {i}"} for i in range(200)]
    digest = CD._digest(many)
    assert digest.count("P:claim/") == CD.WHOLE_DIGEST_CLAIMS and len(digest) < 4000
    # a verse passage is whole stanzas, about one chunk at most
    stanza = "The rain came down upon the hill,\nAnd all the village lay quite still,\nThe miller slept, " \
             "the mill was dumb,\nAnd no one knew the flood would come.\n"
    lyric = "\n".join([stanza] * 60)
    parts = CD.verse_chunks(lyric)
    assert len(parts) > 1 and all(len(c.text_numbered) <= CD.CHUNK_CHARS for c in parts)
    lines = lyric.split("\n")
    for c in parts:          # every passage starts on a stanza's first line and ends on a stanza's last
        assert lines[c.end_line].strip() == "" and (c.start_line == 1 or lines[c.start_line - 2].strip() == "")


# ---------------------------------------------------------------------------
# The dialectic carried over on a re-decompile
# ---------------------------------------------------------------------------

def test_a_re_decompile_carries_the_dialectic_over(tmp_path):
    cosm, _ = CD.derive_emf(ESSAY, source_name="commons.md", source_stat=None, lookup=lambda w: {}, now=NOW)
    twin = dialectic.twin_from_text(cosm, filename="commons.md.fabulan.cosm")
    led = twin.ledger
    led.add({"id": "D:question/maker", "type": "question", "about": "R:maker/ines-varga#capacity",
             "asks": "In what capacity did Ines Varga make the essay?", "why": "unsure", "kind": "text",
             "to": "author", "raised": {"by": "person", "from": "person", "at": NOW}, "state": "open"})
    led.add({"id": "D:question/gone", "type": "question", "about": "C:part/how-we-decide",
             "asks": "Is this section still how the group decides?", "why": "intent", "kind": "yes-no",
             "to": "author", "raised": {"by": "person", "from": "person", "at": NOW}, "state": "open"})
    led.add({"id": "D:session/session-1", "type": "session", "at": NOW, "with": {"to": "author", "who": "the author"},
             "through": "person", "asked": ["D:question/maker"], "skipped": ["D:question/maker"]})
    previous = twin.render()
    assert errors_of(previous, tmp_path, "previous.cosm") == []
    # the text changes: the "How we decide" section is renamed, so its part is gone
    text2 = ESSAY.replace("## How we decide", "## How we choose")
    cosm2, info = CD.derive_emf(text2, source_name="commons.md", source_stat=None, lookup=lambda w: {}, now=NOW,
                                previous=previous)
    items = by_id(cosm2)
    assert info["dialectic"] == {"carried": 3, "stale": 1, "dropped": 0}
    assert items["D:question/maker"]["state"] == "open"
    assert items["D:question/gone"]["state"] == "stale" and items["D:question/gone"]["ended"]["by"] == "derive"
    assert items["D:session/session-1"]["skipped"] == ["D:question/maker"]
    assert errors_of(cosm2, tmp_path, "new.cosm") == []
    # nothing to carry: no previous twin, a twin without D items, an unreadable one
    assert CD.derive_emf(ESSAY, source_name="commons.md", source_stat=None, lookup=lambda w: {},
                         previous=cosm)[1]["dialectic"] is None
    assert CD.derive_emf(ESSAY, source_name="commons.md", source_stat=None, lookup=lambda w: {},
                         previous="not: [a twin")[1]["dialectic"] is None


def test_policy_leaves_claims_and_first_edition_kinds_alone():
    claim = {"id": "P:claim/x", "type": "claim", "stance": "opinion",
             "provenance": {"mode": "derived", "confidence": 0.9}}
    assert CD._policy(claim) == 0 and claim["provenance"]["confidence"] == 0.9, "a claim's stance is the text's"
    aim = {"id": "N:aim/x", "type": "aim", "stance": "surely", "provenance": {"confidence": 0.95}}
    assert CD._policy(aim) == 2 and aim["stance"] == "deduced" and aim["provenance"]["confidence"] == 0.7


@pytest.mark.parametrize("flavour,kind,ok", [("fabulan", "line", False), ("fabulan", "part", True),
                                             ("fabulap", "line", True), ("fabulap", "file", False)])
def test_lint_items_holds_items_to_the_flavour(tmp_path, flavour, kind, ok):
    extra = {"line": {"number": 1}, "part": {"division": "section"}, "file": {"path": "a.py"}}[kind]
    item = {"id": f"C:{kind}/x", "type": kind, "name": "x", "summary": "x", "stance": "observed", **extra,
            "provenance": {"mode": "derived", "sources": ["t#L1"], "confidence": 1.0, "state": "known"}}
    bad = CD._lint_items([item], tmp_path, "flavour", flavour=flavour)
    assert (f"C:{kind}/x" not in bad) is ok, bad
    if not ok:
        assert any(p.check == "flavour-kind" for p in bad[f"C:{kind}/x"])
