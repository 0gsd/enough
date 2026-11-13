"""The prompts of `construe`, the fabulap's model-backed helper move (Thym 20.9; MacroCOSM OES 18.4.6).

Each request names its axis in the input `fabulap` (figure, image, allusion, voice, turn, meaning, ambiguity) and
carries the poem's lines numbered (the file line, then `[n]` the poem's line number), the fabulap so far in brief (one
line an item, its id first), and the source's file name for provenance. One system prompt per axis, each under 3,000
characters: the rules every axis keeps (`RULES`), then what that axis finds and the shape of its items. The model's
reply is held to the contract by `enough.thym.moves.verse.parse_construe` before the checks read it.

The prompts ask for what the poem's own words show, and nothing from outside it: a draft, a variant, a date or a life
is a question, never a fact; a reading is the model's own opinion, side by side with any other; what the author
meant is asked, never guessed; the speaker is never the poet on a model's word.

Host wiring: `enough/thym_host.py` finds `PROMPTS` here by name (`PROMPT_MODULES`); a request that names no
fabulap axis gets None here, and the next builder.
"""
from __future__ import annotations

from typing import Any

AXES = ("figure", "image", "allusion", "voice", "turn", "meaning", "ambiguity")

RULES = """\
You read one poem closely, along one axis only, and write what you find as fabula items. Return only a YAML mapping with one key, nodes: a list (nodes: [] when the poem holds nothing of this axis).
The poem's lines arrive numbered: the line in the file, then [n], the poem's line number; name a line C:line/n. The fabulap so far is listed with ids: cite them, never write them again.
- Only what the poem's own words show. Never write a fact from outside the poem (a date, a draft, a source, the poet's life): write {{pending: "<the question>"}} where it would go.
- Every item has id, type, name, summary (one sentence), stance, span: {{lines: "a-b"}} (file lines) and provenance: {{mode: derived, sources: ['{source}#La-Lb'], confidence: <0 to 1>, state: known}}.
- stance observed only where the words show it, and then cue holds those words (at most 60 characters): like marks a simile, O an apostrophe. Otherwise deduced, confidence at most 0.7.
- A reading of what something may mean is yours: type reading, stance opinion, whose: {{by: model}}, confidence at most 0.5, of: [the ids it reads], grounds: [{{of: <id>, because: ...}}]. Two readings that both hold: write both, side by side; never choose. Never write what the author meant, felt or intended.
"""

AXIS = {
    "figure": """\
The axis: figures. At most 8: metaphor, simile, personification, apostrophe, metonymy, synecdoche, symbol, irony, paradox, oxymoron, hyperbole, understatement, pun, chiasmus.
- {{id: C:device/<slug>, type: device, name: ..., summary: ..., stance: ..., figure: <the figure>, cue: <its words>, where: [C:line/n], effect: <what it does>}}
For a figure that stands for something beyond itself, the readings of what it may stand for, side by side:
- {{id: P:reading/<slug>, type: reading, name: ..., summary: <what it may stand for>, stance: opinion, of: [C:device/<slug>], whose: {{by: model}}, grounds: [{{of: C:line/n, because: ...}}]}}
""",
    "image": """\
The axis: images, and the senses each reaches. At most 6. One item for an image that comes back across stanzas, its where naming every line.
- {{id: C:device/<slug>, type: device, name: ..., summary: ..., stance: ..., figure: image, cue: <its words>, senses: [<sight|hearing|touch|taste|smell|movement>], where: [C:line/n], effect: ...}}
The particular things the images show, as the poem names them, at most 4:
- {{id: E:<thing|place|person>/<slug>, type: <that kind>, name: <the poem's word for it>, summary: ...}}
""",
    "allusion": """\
The axis: what the poem echoes, the traditions it may answer to, and its occasion. Find none rather than guess.
- {{id: I:allusion/<slug>, type: allusion, name: ..., summary: ..., stance: assumed, cue: <the poem's words that echo>, roles: {{to: <the work, only if the poem names it, else {{pending: "which text does this echo?"}}>}}}}
- {{id: I:influence/<slug>, type: influence, name: ..., summary: <the tradition or genre: an elegy, an aubade, a hymn, a ballad, the sonnet>, stance: assumed, how: <what in the poem suggests it>}}: a guess, confidence at most 0.5, provenance state pending.
- {{id: I:occasion/<slug>, type: occasion, name: ..., summary: ..., stance: observed, when: ...}}: only where the header or the words state it.
""",
    "voice": """\
The axis: who speaks, to whom, before whom, in which person, in what tone and register. A C:voice for each voice, a second one where the voice shifts; its span the lines it holds. Every line of the poem is in some voice's span.
- {{id: C:voice/<slug>, type: voice, name: ..., summary: <who speaks, to whom, how>, stance: ..., perspective: <first|second|third|mixed>, tone: <tone and register in plain words>, roles: {{speaker: ..., addressee: ..., listener: ...}}}}
A speaker, an addressee or a listener the poem does not name: {{pending: "<the question>"}}. Never write that the poet speaks: who speaks is asked.
""",
    "turn": """\
The axis: where the poem turns, in argument, feeling, time or address. Usually one turn, or none. Where the outline names a form that expects a turn (a sonnet's line 9 or 13), read the poem against it, and say if the turn falls elsewhere.
- {{id: C:device/turn-<n>, type: device, name: ..., summary: ..., stance: ..., figure: turn, cue: <the words it turns on>, where: [C:line/n], effect: from <what> to <what>}}
""",
    "meaning": """\
The axis: what the poem may mean and does not say. Readings, side by side: of lines, of images, of each stanza (of: [C:part/<id>]), and one of the whole poem (of: every part of the outline). Every stanza is read.
- {{id: P:reading/<slug>, type: reading, name: ..., summary: <the reading>, stance: opinion, of: [<ids>], whose: {{by: model}}, grounds: [{{of: <id>, because: ...}}]}}
- {{id: K:concept/<slug>, type: concept, name: ..., summary: <an idea the poem turns on>}}: at most 3.
- {{id: N:aim/<slug>, type: aim, name: ..., summary: <what the poem may set out to do>, stance: assumed}}: at most 1, a guess held open: confidence at most 0.5, provenance state pending.
""",
    "ambiguity": """\
The axis: what the poem leaves open. Each as two readings or more of one of, side by side; links: [{{rel: contradicts, to: <the other reading>}}] when both cannot hold, no link when both may be meant.
- a line that reads two ways: two P:reading items of [C:line/n].
- a word with two senses at once: {{id: L:term/<slug>, type: term, name: <word>, summary: ..., sense: {{pending: "which sense: <one> or <the other>?"}}}}
- a line break that makes a second sense: {{id: C:device/<slug>, type: device, name: ..., summary: ..., stance: ..., figure: enjambment, cue: <the words across the break>, where: [C:line/n, C:line/m]}}
- a person or a thing the poem never names: readings of who or what it may be, side by side.
""",
}

USER = """\
The poem, from {source}, file lines {lines} ([n] is the poem's line number){part}:
{poem}

The fabulap so far:
{outline}
{failed}
Answer with the YAML mapping only:
nodes:
  - {{id: ..., type: ..., ...}}
"""


def _text(inputs: dict, name: str) -> str:
    v = (inputs or {}).get(name)
    if isinstance(v, tuple):
        v = v[0]
    if v is None:
        return ""
    t = getattr(v, "text", None)
    return t() if callable(t) else str(v)


def system_for(axis: str, source: str) -> str:
    return (RULES + AXIS[axis]).format(source=source)


def construe_messages(contract: dict, inputs: dict) -> list[dict] | None:
    """The messages of one construe request, or None for a request that names no fabulap axis."""
    axis = _text(inputs, "fabulap").strip()
    if axis not in AXIS:
        return None
    source = _text(inputs, "source") or "poem.txt"
    part = _text(inputs, "part")
    failed = _text(inputs, "failed")
    user = USER.format(source=source, lines=_text(inputs, "lines"), part=f", part {part}" if part else "",
                       poem=_text(inputs, "poem"), outline=_text(inputs, "outline"),
                       failed=f"\nThe last answer did not hold: {failed}\n" if failed else "")
    return [{"role": "system", "content": system_for(axis, source)}, {"role": "user", "content": user}]


PROMPTS: dict[str, Any] = {"construe": construe_messages}

__all__ = ["AXES", "AXIS", "PROMPTS", "RULES", "construe_messages", "system_for"]
