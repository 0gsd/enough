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

# The names before EMF (plan §16), kept one release.
EML_SYSTEM = EMF_SYSTEM
EML_USER = EMF_USER
EML_CONTINUE = EMF_CONTINUE
EML_RESTART = EMF_RESTART
EML_RETRY = EMF_RETRY
EML_REPAIR = EMF_REPAIR

# A text or a passage → its atem. The four parts are the owner's definitions.
ATEM_SYSTEM = """\
You write the atem of a text or a passage: its tightest fair, full, plain-English reduction.
Return only a YAML mapping with these keys:
line: one sentence of 15 to 25 words that says what the whole says. Fair: the author would accept it. Full: nothing the text depends on is missing. Plain: everyday words.
focus: at most two sentences: what is happening, what the author directs attention to.
push: one sentence: what the author wants the reader to take away, believe or do.
pull: one sentence: what the reader should actually take away, naming hidden assumptions, opinion stated as fact, dependencies.
stance_profile: how many of its claims the text holds as each stance: {{axiom: n, observed: n, deduced: n, opinion: n, assumed: n, hearsay: n}}
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

# An ordered outline of an EMF twin → a SHORT in gfm markdown (plan §7.3 B, §15). `{order}` is one of
# COMPILE_ORDER: the order the outline is in, said so the model keeps it. The engine adds the footer line itself.
COMPILE_SYSTEM = """\
You write a text back from its EMF outline as a short: gfm markdown in plain English, saying nothing the outline does not hold.
Open with the atem line as the lead paragraph. {order}
Say each claim's stance naturally: axiom "it is given that", observed "the author saw", deduced "it follows that", opinion "the author holds", assumed "it is assumed", hearsay "reportedly" (naming the source).
Name every participant the first time; no pronoun without its noun. Return only the markdown, with no closing note.
"""

COMPILE_ORDER = {
    "told": ("The outline is in the author's own order, as the text told it: keep that order and each ## heading, "
             "and tell the items under each heading as prose. Items under \"## Also in the fabula\" come last, "
             "briefly."),
    "weight": ("Then the claims, grouped under ## headings by the concept they lean on, in the order given (most "
               "salient first). Then the events, in the order given. Close with a \"## Terms\" list: each term "
               "and its sense."),
}

COMPILE_USER = """\
The outline of {name}, {said}:

{outline}
"""
