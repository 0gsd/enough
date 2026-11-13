"""The derivation engine's prompts (0.4.3, plan §7.4): plain strings, filled with `.format` and nothing else.

`EMF_SYSTEM` is read by small local models once per passage, so it is kept under 2,000 characters (a test holds
it there); the grounded term table and the numbered passage travel in the user message (`EMF_USER`), never in
the system prompt. The atem's four parts use the owner's definitions word for word (docs/MACROCOSM_OES.md
§18.3.5). Every system prompt names the six stances and rules out a pronoun standing in for a participant.
Literal braces are doubled because every string here goes through `.format`.
"""

from __future__ import annotations

# One passage → EMF items. `{source}` is the text's file name, as provenance locators spell it. The items come
# most valuable first (claims, events, concepts, entities, terms) with a cap per kind, so a reply cut off by the
# budget loses terms, not claims, and stays short enough for a small model's window.
EMF_SYSTEM = """\
You decompile one passage of a text into EMF items. Return only a YAML `nodes:` list.
Only what this passage says; never invent. The passage has numbered lines.
Write the items in this order, at most: 8 claims, 4 events, 4 concepts, 6 entities, 8 terms, then one atem. Most important first.
- {{id: P:claim/<slug>, type: claim, name: ..., summary: <one sentence>, stance: ..., salience: <critical|high|normal|low>, roles: {{actor: E:..., object: K:...}}, links: [{{rel: supports, to: P:claim/...}}]}}
- {{id: T:event/<slug>, type: event, name: ..., summary: ..., agent: E:..., patient: ..., after: T:event/..., when: <time words>}}
- {{id: K:concept/<slug>, type: concept, name: ..., summary: ...}}
- {{id: E:<person|org|place|work|thing>/<slug>, type: <that kind>, name: ..., summary: ...}}
- {{id: L:term/<slug>, type: term, name: <word>, summary: <what it means here>, sense: <its sense in this text>}}
- {{id: X:atem/1, type: atem, name: ..., summary: ..., line: <15-25 words>, focus: ..., push: ..., pull: ...}}
Every item also has span and provenance. Rules:
- <slug>: the name in lowercase words joined by hyphens.
- stance, one of: axiom (given), observed (first hand), deduced (reasoned from other claims), opinion (the author's judgement), assumed (relied on, unstated), hearsay (reported; the reporter fills roles.source).
- No pronouns in a claim's summary: name every participant.
- roles: free role names (actor, object, cause, effect, holder, source, condition); an item's id where the participant is an item, plain words otherwise.
- links rel, one of: is-a, part-of, depends-on, supports, contradicts, resolves, exemplifies, defines, mentions.
- span: {{lines: "a-b"}} from the line numbers.
- provenance: {{mode: derived, sources: ['{source}#La-Lb'], confidence: <0 to 1>, state: known}}
"""

# The user message beside EMF_SYSTEM: the FEED words this passage uses, then the passage. The follow-ups below are
# appended to it (one user message, so any chat template takes it).
EMF_USER = """\
Words of this passage that FEED, enough's dictionary, holds (word, part of speech: definition):
{terms}

The passage, from {source}, lines {start}-{end}:
{passage}
"""

# A reply cut off by the budget: continue after the last complete item, never from the top.
EMF_CONTINUE = """\

Your list was cut off. You already returned these items:
{ids}
Continue the list after {last}: return only the remaining items, as a YAML `nodes:` list.
"""

# A reply cut off before its first item ended.
EMF_RESTART = """\

Your list was cut off before its first item ended. Return the list again, shorter: the most important items only.
"""

# A reply with no list in it at all.
EMF_RETRY = """\

Your reply had no YAML `nodes:` list. Return only the list, in the item shapes above.
"""

# The one repair turn: only the items that failed the checks, with their problems; never the whole list again.
EMF_REPAIR = """\

These items did not pass the checks:
{items}

The problems:
{problems}

Return only these items, corrected, as a YAML `nodes:` list. Do not repeat any other item.
"""

# A text or a passage → its atem. The four parts are the owner's definitions.
ATEM_SYSTEM = """\
You write the atem of a text or a passage: its tightest fair, full, plain-English reduction.
Return only a YAML mapping with these keys:
line: one sentence of 15 to 25 words that says what the whole says. Fair: the author would accept it. Full: nothing the text depends on is missing. Plain: everyday words.
focus: at most two sentences: what is happening, what the author directs attention to.
push: one sentence: what the author wants the reader to take away, believe or do.
pull: one sentence: what the reader should actually take away, naming hidden assumptions, opinion stated as fact, dependencies.
stance_profile: how many of its claims the text holds as each stance: {axiom: n, observed: n, deduced: n, opinion: n, assumed: n, hearsay: n}
Name who does what: no pronoun whose noun the atem has not named. Use only what the text says; never invent.
"""

ATEM_USER = """\
{context}{text}
"""

# The whole-text atem of a decompiled text, from its passages' atems and its opening and closing.
ATEM_WHOLE_USER = """\
The text: {name}

The atems of its passages, in order:
{atems}

{body}
"""

# ---------------------------------------------------------------------------------------------------------------
# The whole-text request (0.6, the fabula round): the atem of a decompiled text AND the items only the whole shows,
# in one completion after the passages are read. Its system prompt is ATEM_SYSTEM word for word (the atem's four
# definitions stay the owner's), followed by WHOLE_ITEMS for the flavour; its user message is ATEM_WHOLE_USER (the
# passages' atems and the text's opening and close) followed by WHOLE_DIGEST (what the passages found). The reply is
# one YAML mapping: the atem's keys, then `nodes:`. A reply whose nodes cannot be read still gives its atem.
# ---------------------------------------------------------------------------------------------------------------

# Prose (a fabulan): intent, inspiration, how it is built and voiced, and who made it, where the text shows them.
WHOLE_ITEMS_PROSE = """\
nodes: then a YAML list of at most 8 items about the whole text, in these shapes only, and only where the text itself shows them. No item is better than a guess.
- {{id: N:aim/<slug>, type: aim, name: ..., summary: <what the text sets out to do>, stance: ..., measure: <how one would know it worked>}}
- {{id: N:audience/<slug>, type: audience, name: ..., summary: ..., stance: ..., who: ..., needs: <what they come with, and for>}}
- {{id: N:decision/<slug>, type: decision, name: ..., summary: ..., stance: ..., chose: <what was chosen>, because: ...}}
- {{id: N:exclusion/<slug>, type: exclusion, name: ..., summary: <what it says it leaves out>, stance: ..., because: ...}}
- {{id: I:<influence|allusion|occasion>/<slug>, type: <that kind>, name: ..., summary: ..., stance: ..., how: <for an influence>, cue: <for an allusion: its words, at most 60 characters>, when: <for an occasion>}}
- {{id: C:device/<slug>, type: device, name: ..., summary: ..., stance: ..., figure: <metaphor, irony, appeal to authority ...>, effect: ...}}
- {{id: C:voice/<slug>, type: voice, name: ..., summary: <who speaks, to whom, how>, stance: ..., perspective: <first|second|third|mixed>, tone: ..., roles: {{speaker: ..., addressee: ...}}}}
- {{id: R:<maker|release>/<slug>, type: <that kind>, name: ..., summary: ..., stance: ..., capacity: <author|editor|...>, venue: ...}}: only when the text names its maker or where it appeared.
"""

# Verse (a fabulap): the passages' reading already wrote its devices, voice and readings; the whole gives these.
WHOLE_ITEMS_VERSE = """\
nodes: then a YAML list of at most 6 items about the whole poem, in these shapes only, and only where the poem or its heading shows them. No item is better than a guess.
- {{id: I:<allusion|influence|occasion>/<slug>, type: <that kind>, name: ..., summary: ..., stance: ..., cue: <for an allusion: its words, at most 60 characters>, how: ..., when: ...}}
- {{id: N:aim/<slug>, type: aim, name: ..., summary: <what the poem sets out to do>, stance: ...}}
- {{id: R:maker/<slug>, type: maker, name: ..., summary: ..., stance: observed, capacity: author}}: only when the poem's heading names its poet.
- {{id: R:release/<slug>, type: release, name: ..., summary: ..., stance: observed, venue: <the book or album>, at: <the year>}}: only when the heading names it.
"""

# Both flavours: what every item carries, and how its stance is chosen.
WHOLE_RULES = """\
Each item has span: {{lines: "a-b"}} and provenance: {{mode: derived, sources: ['{source}#La-Lb'], confidence: <0 to 1>, state: known}}.
Its stance says how you know it: observed when the text states it outright (its span points at those words); deduced when you reason it from what the text says (confidence at most 0.7); opinion for your own judgement (confidence at most 0.5). Never write as said what the text does not say: who it is for, why it was made, who made it are left out when the text is silent.
"""

# Beside ATEM_WHOLE_USER: what the passages found, so the whole-text items can name them by id.
WHOLE_DIGEST = """
What the reading of its passages found:
{digest}
"""

# One passage of a poem or a song (a fabulap) → its items. `{source}` as for EMF_SYSTEM. Lines arrive numbered with
# their line in the file, then `[n]`, the poem's own line number: the model names a line `C:line/n`. The lines,
# stanzas, metre and rhymes are the rules' (enough/verse.py): the model is not asked for them.
VERSE_SYSTEM = """\
You read one passage of a poem or a song into fabula items. Return only a YAML `nodes:` list.
Only what these lines hold; never invent. Each line shows its line in the file, then [n]: name that line C:line/n.
In this order, at most: 4 devices, 1 voice, 3 readings, 6 terms, 4 entities, 2 concepts, 2 claims, 2 events, then one atem.
- {{id: C:device/<slug>, type: device, name: ..., summary: ..., stance: observed, figure: <image|metaphor|symbol|pun|enjambment|personification|apostrophe|...>, where: [C:line/n], effect: ...}}
- {{id: C:voice/<slug>, type: voice, name: ..., summary: <who speaks, to whom>, stance: ..., perspective: <first|second|third|mixed>, tone: ..., roles: {{speaker: ..., addressee: ...}}}}
- {{id: P:reading/<slug>, type: reading, name: ..., summary: <what a line or an image may mean, which the poem does not say>, stance: opinion, of: [C:line/n], whose: {{by: model}}, grounds: [{{of: C:line/n, because: ...}}]}}
- {{id: L:term/<slug>, type: term, name: <word>, summary: ..., sense: <the sense it has in this poem>}}
- {{id: E:<person|org|place|work|thing>/<slug>, type: <that kind>, name: ..., summary: ...}}
- K:concept; P:claim only for what the poem states outright (stance, salience, roles); T:event only for what it narrates.
- {{id: X:atem/1, type: atem, name: ..., summary: ..., line: <15-25 words>, focus: ..., push: ..., pull: ...}}
Every item also has span and provenance. Rules:
- A reading is a guess: stance opinion, whose {{by: model}}, confidence at most 0.5, grounds from the lines. Two plausible readings of one image: write both; never choose.
- Who speaks or who is addressed, when the poem does not say: {{pending: "<the question>"}} in that role.
- stance, one of: axiom, observed, deduced, opinion, assumed, hearsay. No pronouns in a claim's summary: name every participant.
- span: {{lines: "a-b"}} file lines. provenance: {{mode: derived, sources: ['{source}#La-Lb'], confidence: <0 to 1>, state: known}}
"""

# `derive poem as verse with f` (Thym 20.9): what a passage of a poem SAYS, read against the outline the rules
# wrote. Figures, images, the voice and readings are construe's, one axis a call: not asked here.
VERSE_SENSE_SYSTEM = """\
You read one passage of a poem or a song for what it says, and write it as fabula items. Return only a YAML `nodes:` list.
Only what these lines hold; never invent. Each line shows its line in the file, then [n]: name that line C:line/n.
In this order, at most: 6 terms, 4 entities, 2 concepts, 2 claims, 2 events, then one atem.
- {{id: L:term/<slug>, type: term, name: <word>, summary: ..., sense: <the sense it has in this poem>}}
- {{id: E:<person|org|place|work|thing>/<slug>, type: <that kind>, name: <as the poem names it>, summary: ...}}
- {{id: K:concept/<slug>, type: concept, name: ..., summary: <the idea the lines use>}}
- {{id: P:claim/<slug>, type: claim, name: ..., summary: ..., stance: observed, salience: normal}}: only what the poem states outright.
- {{id: T:event/<slug>, type: event, name: ..., summary: ...}}: only what it narrates.
- {{id: X:atem/<n>, type: atem, name: ..., summary: ..., line: <15-25 words>, focus: ..., push: ..., pull: ...}}
- From the header only, where it names them: {{id: R:maker/<slug>, type: maker, name: ..., summary: ..., stance: observed, capacity: author}}; {{id: R:release/<slug>, type: release, name: ..., summary: ..., stance: observed, venue: ..., at: <the year>}}.
No devices, no voice, no readings: other readings find them. A word whose sense is open: sense: {{pending: "<the question>"}}.
Every item also has span: {{lines: "a-b"}} (file lines) and provenance: {{mode: derived, sources: ['{source}#La-Lb'], confidence: <0 to 1>, state: known}}.
stance, one of: axiom, observed, deduced, opinion, assumed, hearsay. No pronouns in a claim's summary: name every participant.
"""

VERSE_USER = """\
Words of this passage that FEED, enough's dictionary, holds (word, part of speech: definition):
{terms}

The passage, from {source}, file lines {start}-{end} ([n] is the poem's line number):
{passage}
"""

# An ordered outline of a fabula → a SHORT in gfm markdown (plan §7.3 B, §15). `{order}` is one of
# COMPILE_ORDER: the order the outline is in, said so the model keeps it. The engine adds the footer line itself.
COMPILE_SYSTEM = """\
You write a text back from its fabula's outline as a short: gfm markdown in plain English, saying nothing the outline does not hold.
Open with the atem line as the lead paragraph. {order}
Say each claim's stance naturally: axiom "it is given that", observed "the author saw", deduced "it follows that", opinion "the author holds", assumed "it is assumed", hearsay "reportedly" (naming the source).
Name every participant the first time; no pronoun without its noun. Return only the markdown, with no closing note.
"""

COMPILE_ORDER = {
    "told": ("The outline is in the author's own order, as the text told it: keep that order and each ## heading, "
             "and tell the items under each heading as prose. Items under \"## Also in the fabula\" come last, "
             "briefly. A reading said to be a guess stays a guess."),
    "weight": ("Then the claims, grouped under ## headings by the concept they lean on, in the order given (most "
               "salient first). Then the events, in the order given. Close with a \"## Terms\" list: each term "
               "and its sense."),
}

COMPILE_USER = """\
The outline of {name}, {said}:

{outline}
"""
