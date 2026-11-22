"""The prompts of the fabulam's model-backed jobs (Thym 20.13; MacroCOSM OES 18.4.10).

Six jobs take a proof apart, and each request names its job in the input `fabulam`:

- `read`: one Lean file, its comments blanked, read against its outline (`derive t as proof with f`): what each
  reached declaration says, each lemma's role, method and why, the steps, the reliances, the terms;
- `comments`: the comment table (`construe t as comments with f`): the one job that sees the comments;
- `fit`: each statement set against the public wording (`construe w as fit with f`): no Lean;
- `yield`: what a statement's proof delivers, set against what it says (`construe t as yield with f`);
- `stages`: the stages, the teaching order, the readings and the atem, from the items alone (`construe t as stages
  with f`): no Lean;
- `head`: the same over an archive's parts (`derive repo with h`): no Lean.

A seventh, `pshort`, entails: one brief for each density, `expert`, `student`, `everyone` (`entail f as …`). The
entailer sees the fabulam's items and nothing else: the move strips every span, every `lines` and the source's path
before the request is made (`enough.thym.moves.proof.pshort_view`), and the check `apart` holds it.

Each system prompt stays under 2,000 characters, so that a local model's window is spent on the Lean and the
items; the shape of the answer is shown once, in the user message. Common to all: write in your own words; never
copy Lean but a declaration's name; say `{pending: "…"}` where you do not know, never a guess; every `yes` and `no`
in quotes. No prompt says a proof is machine-checked, verified or certified, and the entailer is told never to.

The reader of the proof never sees a comment: `blank_comments` (by rule, every line kept at its number) is
`enough.thym.moves.proof`'s, since the move must blank the Lean before the request exists; it is named here too.

Host wiring: `enough/thym_host.py` finds `PROMPTS` here by name (`PROMPT_MODULES`); a request that names no fabulam
job gets None here, and the next builder.
"""
from __future__ import annotations

from typing import Any, Callable

from enough.thym.moves.proof import DENSITIES, SHAPE_CHARS, blank_comments

JOBS = ("read", "comments", "fit", "yield", "stages", "head")
STEPS = JOBS + ("pshort",)

COMMON = ("Write in your own words; never copy Lean but a declaration's name. Where you do not know, write "
          "{pending: \"<the question>\"}, never a guess. Put every yes and no in quotes. Return only the YAML "
          "mapping.")
QUOTING = ("Quote any value that holds a colon, a hash, a brace or a bracket ('…'), and write \"yes\" and \"no\" in "
           "double quotes.")


def _text(inputs: dict, name: str) -> str:
    """An input's text, whether it comes as a value or as the `(value, sha256)` pair the runtime hands a
    coprocessor."""
    v = (inputs or {}).get(name)
    if isinstance(v, tuple):
        v = v[0]
    if v is None:
        return ""
    t = getattr(v, "text", None)
    return t() if callable(t) else str(v)


def step(inputs: dict) -> str | None:
    s = _text(inputs, "fabulam").strip()
    return s if s in STEPS else None


# ---------------------------------------------------------------------------
# read: one Lean file, comments blanked, against its outline
# ---------------------------------------------------------------------------

READ_SYSTEM = (
    "You read one Lean 4 file, its comments blanked, and write as YAML what it says, for a map of the proof that a "
    "mathematician will check. The outline lists its declarations by their Lean names (lean), found by rule, with "
    "their lines, depth (steps from the final theorem) and carries (how much of the proof passes through each).\n"
    "Write:\n"
    "- declarations: one entry for every name under cover. says: its statement in full, in words and ordinary "
    "notation, every quantifier, hypothesis and constant in the order the Lean gives them, nothing left out, "
    "nothing added. A final theorem (C:statement) also takes quantifiers: [{kind: for-all | exists | "
    "infinitely-many | eventually, what}]. A lemma reached \"yes\" takes role and method (one sentence on how it is "
    "proved). role, by the blackboard rule: spine, if a mathematician telling the proof at a blackboard would state "
    "it, so that without it the argument has a hole (a step that changes what must be proved is spine, however "
    "short its proof); support, a real step the telling would only mention; bookkeeping, needed by Lean and not by "
    "a reader (casts, rearrangements). A spine lemma takes why: what the argument would lack without it and what "
    "it makes easier next; never that no other way exists.\n"
    "- steps: a step with no declaration of its own that the blackboard telling would state: inside (the lean of "
    "a lemma or final theorem, never of a definition or instance), says, lines inside it, confidence.\n"
    "- reliances: a library result that carries real weight, never a declaration of this file: lean (the name as "
    "this file writes it), known-as, field, case (which case or form is used), gives (what it says).\n"
    "- terms, concepts: what a reader must know.\n"
    "Tell this file's own argument, not one you remember. " + COMMON)

READ_SHAPE = """declarations:
  - lean: "Parity.even_add_even"
    says: 'For all natural numbers m and n, if m is even and n is even then m + n is even.'
    quantifiers: [{kind: for-all, what: 'natural numbers m and n, both even'}]
    method: 'It adds the two halves and uses the lemma on doubling.'
  - {lean: "Parity.two_mul_add", says: 'For all a and b, 2a + 2b = 2(a + b).', role: bookkeeping, method: 'One rewrite.'}
  - lean: "Parity.half_exists"
    says: 'For every even n there is a k with n = 2k.'
    role: spine
    method: 'It unfolds the definition.'
    why: 'Without it nothing names the half. It turns "even" into an equation the sum can use.'
steps:
  - {slug: the-witness, name: 'The witness', inside: "Parity.even_add_even", says: 'The half of the sum is the sum of the halves.', lines: "21-22", confidence: high}
reliances:
  - {slug: distributes, name: 'multiplication distributes', lean: [Nat.mul_add], known-as: 'the distributive law', field: arithmetic, case: 'for natural numbers', gives: 'a(b + c) = ab + ac for all natural numbers.'}
terms: [{name: even, summary: 'A whole number that is twice a whole number.'}]
concepts: []"""

WINDOW_SHAPE = """notes:
  - 'Lines 120-180 bound the middle sum by splitting it at the square root.'
steps: []
reliances: []"""


def read_messages(contract: dict, inputs: dict) -> list[dict]:
    path, name = _text(inputs, "path"), _text(inputs, "name")
    part, window = _text(inputs, "part"), _text(inputs, "window")
    code, notes = _text(inputs, "code"), _text(inputs, "notes")
    head = f"The file: {path}, of {name}; lines {_text(inputs, 'lines')}" + (f"; part {part}" if part else "") + ".\n"
    near = _text(inputs, "neighbours")
    user = head + f"\nThe outline (found by rule):\n```yaml\n{_text(inputs, 'outline')}```\n"
    if near:
        user += f"\nWhat other parts state, by name (lean on these; do not prove them again):\n{near}\n"
    if window:
        user += (f"\nThis is window {window} of one long declaration. Its statement:\n{_text(inputs, 'statement')}\n"
                 "Give no declarations here: write notes (sentences on what these lines do), and any steps and "
                 "reliances you see.\n")
        shape = WINDOW_SHAPE
    else:
        user += f"Cover: {_text(inputs, 'cover') or '[]'}\n"
        shape = READ_SHAPE
    if notes:
        user += (f"\nThe declaration was read in windows. Its statement:\n{_text(inputs, 'statement')}\nThe notes "
                 f"from its windows:\n```yaml\n{notes}```\nWrite its entry under declarations from these notes.\n")
    if code:
        user += f"\nThe Lean, comments blanked, lines numbered:\n```\n{code}\n```\n"
    user += f"\nAnswer in this shape (the values are examples):\n```yaml\n{shape}\n```\n{QUOTING}"
    return _with_failed([{"role": "system", "content": READ_SYSTEM}, {"role": "user", "content": user}], inputs)


def _with_failed(msgs: list[dict], inputs: dict) -> list[dict]:
    failed = _text(inputs, "failed")
    if failed:
        msgs.append({"role": "user", "content": f"Your last answer could not be taken: {failed}. Answer again, "
                                                "whole, so that it can."})
    return msgs


# ---------------------------------------------------------------------------
# comments: the audit
# ---------------------------------------------------------------------------

COMMENTS_SYSTEM = (
    "You audit the comments of one Lean 4 file. Lean does not check a comment: each is something a person said. "
    "You see the file with its comments, its declarations (found by rule, with what each says in words), and the "
    "comments listed by their lines.\n"
    "Write audit: one entry for every comment listed, none skipped, its lines exactly as listed, and a verdict:\n"
    "- agrees: the Lean under it bears it out.\n"
    "- nothing: it says nothing about the mathematics (a heading, a licence line, a note on layout).\n"
    "- claim: every mismatch, and every remark Lean cannot bear out that a reader would want kept (a credit, a "
    "piece of history, a judgement). Then add claim: {slug, name, says (what the comment says), about (the lean of "
    "the declaration it is about, or a few words), checked}. checked is \"yes\" (a Lean statement of the file bears "
    "it out in full; add by, that declaration's lean), \"partial\" (in part; add by, short-of, mismatch, "
    "false-as-written \"yes\" or \"no\"), \"contradicted\" (the Lean shows otherwise; add by, mismatch) or "
    "\"not-checkable\" (Lean could bear it out neither way). mismatch is formula, hypothesis, name, numbering or "
    "inference; numbering is a comment that points at a step or a lemma by a number the file does not have.\n"
    "Set each comment against the Lean it stands over, not against what you expect. Do not soften: a comment whose "
    "conclusion does not follow is contradicted, or false-as-written \"yes\".\n"
    "Also list works, people and aims that a comment names, each {slug, name, summary, lines}; an aim is what the "
    "work sets out to prove, as the comment says it.\n" + COMMON)

COMMENTS_SHAPE = """audit:
  - {lines: "1-5", verdict: nothing}
  - {lines: "12-13", verdict: agrees}
  - lines: "30-31"
    verdict: claim
    claim: {slug: holds-for-all-n, name: 'The note says it holds for all n', says: 'The note says the bound holds for every n.', about: "Parity.bound", checked: "partial", by: "Parity.bound", short-of: 'The Lean asks n ≥ 2.', mismatch: hypothesis, false-as-written: "yes"}
works: []
people: []
aims: [{slug: sums-of-even-numbers, name: 'Sums of even numbers', summary: 'The module note says the file proves that even numbers are closed under addition.', lines: "7-10"}]"""


def comments_messages(contract: dict, inputs: dict) -> list[dict]:
    user = (f"The file: {_text(inputs, 'path')}, of {_text(inputs, 'name')}; lines {_text(inputs, 'lines')}.\n\n"
            f"Its declarations:\n```yaml\n{_text(inputs, 'outline')}```\n\n"
            f"The comments to audit, by their lines:\n```yaml\n{_text(inputs, 'comments')}```\n\n"
            f"The Lean with its comments, lines numbered:\n```\n{_text(inputs, 'code')}\n```\n\n"
            f"Answer in this shape (the values are examples):\n```yaml\n{COMMENTS_SHAPE}\n```\n{QUOTING}")
    return _with_failed([{"role": "system", "content": COMMENTS_SYSTEM}, {"role": "user", "content": user}], inputs)


# ---------------------------------------------------------------------------
# fit: the statement against the public wording (no Lean)
# ---------------------------------------------------------------------------

FIT_SYSTEM = (
    "You set a formal statement against a public wording of the same result. You see the wording, its lines "
    "numbered, and each final theorem as the fabulam says it in words, with its quantifiers. You do not see Lean.\n"
    "Write fits: one for every statement, {of (its id), how, form-differences, differences, confidence}.\n"
    "- how: same (the two say one thing), stronger (the statement gives more), weaker (it gives less), "
    "a-particular-reading (the wording can be read in more than one way and the statement fixes one), or "
    "different.\n"
    "- form-differences: differences of form only: notation, quantifiers that may change places, a set against a "
    "property.\n"
    "- differences: differences of mathematical content, one plain sentence each: a range, a hypothesis, a "
    "constant, a case left out. [] when there is none. No word of judgement: not trivial, easy, intended, obvious "
    "or famous.\n"
    "- confidence: high, medium or low.\n"
    "What the wording says about a version, a history or a status is no difference: write it under claims, {slug, "
    "name, says, about}, as something the wording says about that version.\n"
    "Say only what the two texts show. " + COMMON)

FIT_SHAPE = """fits:
  - of: C:statement/Parity.even_add_even
    how: weaker
    form-differences: ['The wording speaks of integers as a set; the statement of a property of numbers.']
    differences: ['The wording covers every integer; the statement covers the natural numbers.']
    confidence: high
claims: []"""


def fit_messages(contract: dict, inputs: dict) -> list[dict]:
    user = (f"The proof: {_text(inputs, 'name')}.\n\nIts final theorems, as the fabulam says them:\n```yaml\n"
            f"{_text(inputs, 'statements')}```\n\nThe public wording, {_text(inputs, 'source')}, lines numbered:\n"
            f"```\n{_text(inputs, 'wording')}\n```\n\n"
            f"Answer in this shape (the values are examples):\n```yaml\n{FIT_SHAPE}\n```\n{QUOTING}")
    return _with_failed([{"role": "system", "content": FIT_SYSTEM}, {"role": "user", "content": user}], inputs)


# ---------------------------------------------------------------------------
# yield: stated against shown
# ---------------------------------------------------------------------------

YIELD_SYSTEM = (
    "You read the proof of one final theorem of a Lean 4 file, comments blanked, and write what the proof delivers, "
    "set against what the statement says. Stated is not shown.\n"
    "How: read the proof of the statement and of the lemmas it rests on. Where the statement says there exists, "
    "look at how the witness is made. Where it fixes a range or a constant, ask whether the proof uses it or would "
    "run for more. Vary each thing the proof chooses and write what comes out as a function of it. Then try the "
    "cases anyone can settle without the proof.\n"
    "Write:\n"
    "- yield: beyond (\"yes\" if the construction delivers more than the statement says, else \"no\"); says (what "
    "it delivers, in full; with \"no\", why you are sure); as-statement (only with \"yes\": the delivered result as "
    "one theorem); needs (steps to as-statement the file does not take; [] if none); bound (at-least, at-most, "
    "exactly, between or none); chooses ([{what, where, value, gives, best, confidence}]: gives is the result as a "
    "function of the choice, best the choice that makes it best, or the file's choice; [] if the proof picks "
    "nothing); trivial ([{case, known, delivered, compares: above | equal | below}]) or no-trivial (one sentence "
    "on why none exists); grounds ([{of, lines}]); confidence (high, medium, low).\n"
    "- case: one worked example in small numbers, checkable by hand: {slug, name, given, expect}.\n"
    "- constants: [{slug, name, says, value, where, why}], what the proof fixes.\n"
    "- slack: [{on, hypothesis, would-suffice, lines, confidence}], where lines show a weaker hypothesis would do.\n"
    "Say at least, at most or exactly; never \"up to\". Where the result falls below what is plainly true, say "
    "below. " + COMMON)

YIELD_SHAPE = """yield:
  name: What the proof delivers
  beyond: "yes"
  says: 'The proof names the half of the sum: it is the sum of the two halves.'
  as-statement: 'For all natural numbers a and b, 2a + 2b = 2(a + b).'
  needs: []
  bound: none
  chooses:
    - {what: 'the half of the sum', where: "Parity.even_add_even", value: 'a + b', gives: 'm + n = 2(a + b)', best: "the file's choice", confidence: high}
  trivial:
    - {case: 'n = 0', known: 'm + 0 = m is even', delivered: 'the half of m, with nothing added', compares: equal}
  grounds: [{of: "Parity.even_add_even", lines: "20-23"}]
  confidence: high
case: {slug: six-and-ten, name: '6 + 10', given: '6 = 2 · 3 and 10 = 2 · 5.', expect: '16 = 2 · 8, and 8 = 3 + 5.'}
constants: []
slack: []"""


def yield_messages(contract: dict, inputs: dict) -> list[dict]:
    user = (f"The file: {_text(inputs, 'path')}, of {_text(inputs, 'name')}; lines {_text(inputs, 'lines')}.\n\n"
            f"The final theorem, as the fabulam says it:\n```yaml\n{_text(inputs, 'statement')}```\n\n"
            f"What the fabulam holds so far of the lemmas, steps and reliances (cite these by lean or id):\n```yaml\n"
            f"{_text(inputs, 'outline')}```\n\nThe proofs, comments blanked, lines numbered:\n```\n"
            f"{_text(inputs, 'code')}\n```\n\n"
            f"Answer in this shape (the values are examples):\n```yaml\n{YIELD_SHAPE}\n```\n{QUOTING}")
    return _with_failed([{"role": "system", "content": YIELD_SYSTEM}, {"role": "user", "content": user}], inputs)


# ---------------------------------------------------------------------------
# stages, and head: the argument folded (no Lean)
# ---------------------------------------------------------------------------

_STAGES_BODY = (
    "- stages, in the order of the logic. Each: slug, name, number (1, 2, 3, no gap), stage, says (what it achieves "
    "and why the next needs it), plain, plain-if, steps (ids of lemmas, statements, steps, definitions, never reliances, in the argument's order), confidence. "
    "stage is reduction, main, tool, side or close. Exactly one is the reduction: what has to be shown or made "
    "large, and why; it also takes obvious: the obvious way to the result and why it fails, or \"none: the file's "
    "way is the obvious one\". Every spine lemma is in some stage's steps.\n"
    "- plain: one or two sentences a reader with no mathematics could follow, on what happens in the stage: the "
    "mechanism, not only the goal. No symbol, no one-letter name, no term to look up; name each thing by what it "
    "is before using it; say nothing the stage's items do not hold. plain-if: the condition the mechanism needs to "
    "be true, in plain words; \"none\" only when plain is true with no condition.\n"
    "- teaching: the stages' slugs in the order a teacher would tell them, the reduction first, then main, tool, "
    "side, close.\n"
    "- readings: three to six key ideas, why the proof works: {slug, name, summary, of (a stage's slug or an id), "
    "grounds: [{of, lines}], confidence}; high only for one you could defend line by line.\n"
    "- atem: line (15 to 25 words: the statement with its own ranges, nothing the proof adds), focus, push, pull "
    "(a sentence each).\n")

STAGES_SYSTEM = (
    "You fold a proof into stages from its items alone: the statements, the lemmas with their roles, the steps, "
    "the reliances, the yield. You do not see Lean.\nWrite:\n" + _STAGES_BODY +
    "- decisions: [{slug, name, summary, chose, because}], a choice visible in the formal text.\n"
    "An item that speaks of size or rate takes regime: {as, uniform-in, fixed, worst-over}. Never \"up to\". "
    + COMMON)

HEAD_SYSTEM = (
    "You fold an archive of Lean files into one argument, from its parts' summaries and the declarations that "
    "cross between parts (what each says, its depth, its role in its part). You do not see Lean.\nWrite:\n"
    + _STAGES_BODY +
    "- roles: [{of, role, why}] for a crossing lemma whose role in the whole differs from its role in its part; a "
    "spine lemma says why.\n"
    "A stage's steps are ids of crossing declarations. Never \"up to\". " + COMMON)

STAGES_SHAPE = """stages:
  - slug: what-must-be-found
    name: What must be found
    number: 1
    stage: reduction
    says: 'To show the sum is even it is enough to name its half.'
    plain: 'To show a number can be shared equally between two people, it is enough to say how much each one gets.'
    plain-if: none
    obvious: "none: the file's way is the obvious one"
    steps: [C:statement/Parity.even_add_even]
    confidence: high
  - {slug: adding-the-halves, name: 'Adding the halves', number: 2, stage: main, says: '…', plain: '…', plain-if: '…', steps: [C:lemma/Parity.half_exists, C:step/the-witness], confidence: medium}
teaching: [what-must-be-found, adding-the-halves]
readings:
  - {slug: the-half-is-named, name: 'The half is named', summary: 'The proof works because it names the half outright.', of: [adding-the-halves], grounds: [{of: C:step/the-witness, lines: "21-22"}], confidence: high}
decisions: []
atem: {line: '…', focus: '…', push: '…', pull: '…'}"""


#: How the atem's line is counted, said in the request: a model cannot count the words of a formula by eye.
ATEM_COUNT = ("The atem's line is counted by rule: every run of letters or of digits is one word, so (p/q) is two "
              "words and 1/2 is two. Write the line in words, with few symbols, and aim at 18 to 22.")


def stages_messages(contract: dict, inputs: dict) -> list[dict]:
    user = (f"The proof: {_text(inputs, 'name')}.\n\nIts items:\n```yaml\n{_text(inputs, 'items')}```\n\n"
            f"Answer in this shape (the values are examples):\n```yaml\n{STAGES_SHAPE}\n```\n{QUOTING}\n{ATEM_COUNT}")
    return _with_failed([{"role": "system", "content": STAGES_SYSTEM}, {"role": "user", "content": user}], inputs)


ROUND_SYSTEM = (
    "You read the summaries of some of the parts of an archive of Lean files, and the declarations that cross "
    "between parts. You do not see Lean. Write notes: a list of sentences, each saying what one part does for the "
    "argument and which crossing declarations carry it, by id. Say nothing the summaries do not hold. " + COMMON)


def head_messages(contract: dict, inputs: dict) -> list[dict]:
    name, rnd = _text(inputs, "name"), _text(inputs, "round")
    comps, notes, yields = _text(inputs, "components"), _text(inputs, "notes"), _text(inputs, "yields")
    user = f"The archive: {name}.\n"
    if comps:
        user += f"\nIts parts{f', round {rnd}' if rnd else ''}:\n```yaml\n{comps}```\n"
    if notes:
        user += f"\nNotes on its parts, from the rounds before:\n```yaml\n{notes}```\n"
    user += f"\nThe declarations that cross between parts:\n```yaml\n{_text(inputs, 'crossing')}```\n"
    if yields:
        user += f"\nWhat the final theorems' proofs deliver:\n```yaml\n{yields}```\n"
    if rnd:
        user += "\nAnswer with the YAML mapping only:\nnotes:\n  - '…'\n"
        return _with_failed([{"role": "system", "content": ROUND_SYSTEM}, {"role": "user", "content": user}], inputs)
    user += (f"\nAnswer in this shape (the values are examples), with roles: [] where you judge no lemma "
             f"differently:\n```yaml\n{STAGES_SHAPE}\nroles: []\n```\n{QUOTING}\n{ATEM_COUNT}")
    return _with_failed([{"role": "system", "content": HEAD_SYSTEM}, {"role": "user", "content": user}], inputs)


# ---------------------------------------------------------------------------
# pshort: the entailer's three briefs
# ---------------------------------------------------------------------------

PSHORT_COMMON = (
    "You write a pshort: a guide to a formal proof, from a fabulam's items alone (each with its id). You have not "
    "seen the Lean and do not need it. A pshort is not a proof: never call your text one, and never say the proof "
    "is checked by a machine, verified or certified. A fixed line above your text says what is known about that.\n"
    "- Say nothing the items do not hold: no name, number, history or result they lack.\n"
    "- Close each run of sentences with the ids it rests on, in square brackets, like this: … so the sum is "
    "even. [C:lemma/a, C:step/b] Every sentence is covered, so every paragraph ends in such a group. Cite only "
    "ids of the items.\n"
    "- Give the statement with its own ranges, as its says gives it.\n"
    "- Tell the yield as what the proof delivers, in the words of its bound: at least, at most, exactly, between. "
    "Never \"up to\".\n"
    "- Hedge what is of low confidence (may, perhaps, seems, we read). Tell an open question as open.\n"
    "- Cite every id listed under must.\n"
    "Write the body alone, as markdown in paragraphs. No title and no footer: rules write those.\n")

PSHORT_BRIEFS = {
    "expert": (
        "The reader is a mathematician in the field. Order: the logic, the stages by number. It must hold: the "
        "statement in full; the fit with the public wording, where there is one; the yield with its as-statement, "
        "needs, chooses and slack; every spine lemma by its Lean name with its why; each reliance by its known "
        "name and the case used; any comment the Lean contradicts; the open questions. 500 to 900 words."),
    "student": (
        "The reader has had a first course in the subject. Order: the logic, the stages by number. Define each "
        "term at first use, from the terms and concepts. For each stage give its says and its key lemma, and one "
        "reading where there is one. Give the worked example. 500 to 800 words."),
    "everyone": (
        "The reader has no mathematics. Order: the teaching order, the reduction first. For each stage tell its "
        "plain together with its plain-if, in your own flow. Give exactly one worked example, the worked case, "
        "with its numbers and no others. Tie every symbol to its words at first use (\"call it k\"), or use no "
        "symbols. Say why it matters only from the aim, work and concept items. Say what is open last. 350 to 600 "
        "words."),
}


def pshort_system(density: str) -> str:
    return PSHORT_COMMON + PSHORT_BRIEFS[density]


def pshort_messages(contract: dict, inputs: dict) -> list[dict] | None:
    density = _text(inputs, "density").strip()
    if density not in DENSITIES:
        return None
    user = (f"The fabulam: {_text(inputs, 'name')}. Density: {density}. Words: {_text(inputs, 'words')}.\n"
            f"Must be cited: {_text(inputs, 'must')}\n\nThe items:\n```yaml\n{_text(inputs, 'items')}```\n\n"
            "Answer with a YAML mapping of one key, the markdown as a block under it, each line two spaces in:\n"
            "```yaml\nbody: |\n  The first paragraph. [C:statement/x]\n\n  The next paragraph. [C:lemma/y, "
            "C:step/z]\n```")
    return _with_failed([{"role": "system", "content": pshort_system(density)}, {"role": "user", "content": user}],
                        inputs)


BUILDERS: dict[str, Callable[[dict, dict], list[dict] | None]] = {
    "read": read_messages, "comments": comments_messages, "fit": fit_messages, "yield": yield_messages,
    "stages": stages_messages, "head": head_messages, "pshort": pshort_messages}

SYSTEMS: dict[str, str] = {"read": READ_SYSTEM, "comments": COMMENTS_SYSTEM, "fit": FIT_SYSTEM,
                           "yield": YIELD_SYSTEM, "stages": STAGES_SYSTEM, "head": HEAD_SYSTEM,
                           **{f"pshort-{d}": pshort_system(d) for d in DENSITIES}}


def messages(contract: dict, inputs: dict) -> list[dict] | None:
    """The messages of a fabulam job's request, or None when the request names no job (another builder's)."""
    s = step(inputs)
    return BUILDERS[s](contract, inputs) if s else None


def user_chars(inputs: dict) -> int:
    """How long the user message of a request is: what `proof.REQUEST_CHARS` bounds before a request is sent (the
    inputs' own texts and at most `SHAPE_CHARS` beside them)."""
    msgs = messages({}, inputs) or []
    return sum(len(m["content"]) for m in msgs if m["role"] == "user")


#: The host's table (enough/thym_host.py, `PROMPT_MODULES`): move -> builder, None for a request that is not a
#: fabulam job, so that the host asks the next builder.
PROMPTS: dict[str, Any] = {"derive": messages, "construe": messages, "entail": messages}

__all__ = ["BUILDERS", "COMMENTS_SYSTEM", "FIT_SYSTEM", "HEAD_SYSTEM", "JOBS", "PROMPTS", "PSHORT_BRIEFS",
           "PSHORT_COMMON", "READ_SYSTEM", "SHAPE_CHARS", "STAGES_SYSTEM", "STEPS", "SYSTEMS", "YIELD_SYSTEM",
           "blank_comments", "messages", "pshort_system", "step", "user_chars"]
