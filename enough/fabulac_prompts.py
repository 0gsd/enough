"""The prompts of the fabulac's model-backed steps (THYM 20.6, 20.7; MacroCOSM OES 18.4.7).

Four steps ask a model, and each request names its step in the input `fabulac`:

- `read`: one Python file read against the outline (`derive t as code with f`): behaviours, structures, cases,
  terms, concepts, claims, events, in a strict YAML shape (`enough.thym.moves.code.parse_reading` checks it);
- `fold`: the whole program read from the fabulac so far and its own documents (`derive repo with f`): aims,
  audiences, uses, requirements, decisions, exclusions, influences, occasions, and the atem (`parse_fold`);
- `code` and `readme`: one file of the cshort written from the fabulac alone (`entail f as code`);
- `catem`: what a user can do, at depth `overview` or `manual` (`entail f as overview|manual`).

The detail they ask for is MacroCOSM OES 18.4.7's "how much detail is enough": everything a user or a caller can
observe, exactly (signatures, parameters with their types and defaults, what is returned, every error with the words a
user sees, exact output formats, the edges); nothing that is a choice inside a function (no bodies, no line-by-line
paraphrase). A model that does not know says so in a summary, and never fills a value in by guessing.

Each system prompt stays under 2,000 characters (the limit `tests/test_canon_derive.py` holds Canon's own to), so that a
local model's window is spent on the code and the outline, not on instructions; the shape of the answer is shown once,
as a template, in the user message.

Host wiring: `enough/thym_host.py` finds `PROMPTS` here by name (`PROMPT_MODULES`) and chains it in front of its own
builders for `derive` and `entail`; a request that names no fabulac step gets None here, and the host's builder.
"""
from __future__ import annotations

from typing import Any, Callable

STEPS = ("read", "fold", "code", "readme", "catem")


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
    s = _text(inputs, "fabulac").strip()
    return s if s in STEPS else None


# ---------------------------------------------------------------------------
# read: one file, against the outline
# ---------------------------------------------------------------------------

READ_SYSTEM = (
    "You read one Python file of a program and write, as YAML, what it does, for a specification from which another "
    "programmer will write the program again without seeing this code. The outline lists the file's interfaces "
    "(ids, exact signatures, parameters) and components, found from its syntax.\n"
    "Write:\n"
    "- behaviours: what happens for which input. when: the trigger. does: in plain words and in order, what is read, "
    "decided, written, printed; exact output formats and the exact words of every message a user sees. edges: "
    "[{given, then}]. errors: [{when, message, exit}] (exit: a program's exit status). of: [outline ids].\n"
    "- enrich: an outline item's id and only what the code shows that the outline lacks. An interface takes takes "
    "[{name, means}], gives {means}, raises [{error, message, when}]; a structure fields [{name, means}], "
    "invariants; a component does; a setting means.\n"
    "- structures the outline lacks (a file format, a record kept in a dict): shape, fields, invariants.\n"
    "- cases: from tests and docstring examples, exactly as pinned: of [ids], given {calls | arguments | input | "
    "env | file}, expect {value | output | error-output | exit | raises}.\n"
    "- terms (word, pos, sense), concepts, claims (what comments and docstrings assert: stance, salience), events "
    "(the steps of one use, in order: agent an interface or component id; after the id of the event before).\n"
    "Cover every id under cover: an interface by a behaviour whose of names it, or a structure of its name; a "
    "component by its does (enrich) or a behaviour. Enrich alone covers no interface. Cite only ids of the outline; "
    "a test file's cases cite ids under elsewhere. Each new entry has slug, name, summary (one sentence) and lines "
    "(\"12-40\"). No function bodies, no line-by-line paraphrase. Where the code does not say, write the question; "
    "never guess a value. Return only the YAML mapping.")

READ_SHAPE = """behaviours:
  - slug: count-words
    name: Counting words
    summary: 'count_words counts the words of a text.'
    of: [C:interface/pkg.mod.count_words]
    when: 'count_words(text) is called'
    does: 'A word is a run of the letters A-Z or a-z; case is ignored. Returns how many there are.'
    edges: [{given: '""', then: '0'}]
    errors: [{when: 'the file cannot be read', message: 'tool: cannot read FILE: OSError', exit: 1}]
    lines: "20-24"
enrich:
  - id: C:interface/pkg.mod.count_words
    takes: [{name: text, means: 'the text whose words are counted'}]
    gives: {means: 'how many words the text holds'}
    raises: [{error: ValueError, message: 'not a text: {text!r}', when: 'text is not a string'}]
    lines: "20-24"
  - {id: C:structure/pkg.mod.Entry, fields: [{name: at, means: 'seconds since the epoch'}], invariants: ['delta is never 0']}
  - {id: C:component/pkg.mod, does: 'Counts the words of a text and ranks them.'}
structures:
  - {slug: ledger-line, name: 'A ledger line', summary: 'One JSON object per line.', shape: 'a JSON object per line',
     fields: [{name: at, type: float}], lines: "40-44"}
cases:
  - slug: ties
    name: Ties break by letter
    summary: 'top_words breaks ties alphabetically.'
    of: [C:interface/pkg.mod.top_words]
    given: {calls: ['top_words("b a b a c", 2)']}
    expect: {value: '[("a", 2), ("b", 2)]'}
    lines: "9-10"
terms: [{slug: word, name: word, word: word, pos: noun, summary: 'The unit counted.', sense: 'A run of letters.', lines: "8"}]
concepts: []
claims: []
events:
  - {slug: read-file, name: 'The file is read', summary: 'main reads the file.', agent: C:interface/pkg.mod.main, lines: "25"}
  - {slug: print-count, name: 'The count is printed', summary: 'main prints one line.', agent: C:interface/pkg.mod.main,
     after: T:event/pkg.mod.read-file, lines: "28"}"""

#: The shape of a test file's reading: cases, and structures for the helpers other tests use.
TEST_SHAPE = """cases:
  - slug: ties
    name: Ties break by letter
    summary: 'top_words breaks ties alphabetically.'
    of: [C:interface/pkg.mod.top_words]
    given: {calls: ['top_words("b a b a c", 2)']}
    expect: {value: '[("a", 2), ("b", 2)]'}
    lines: "9-10"
structures:
  - {slug: counting-lock, name: 'A lock that counts', summary: 'CountedLock counts how often it is entered.',
     shape: 'a context manager', fields: [{name: count, means: 'how many times it was entered'}], lines: "5-14"}"""

#: The shape of a reading of a file with no interface or component of its own (tooling, a helper).
BARE_SHAPE = """structures:
  - {slug: release-notes, name: 'The release-notes script', summary: 'Prints the change log of one version as notes.',
     shape: 'a script run by hand', fields: [{name: version, means: 'the version whose notes it prints'}],
     invariants: ['it reads CHANGELOG.md and writes to standard output'], lines: "1-40"}
claims: []"""

ROLES = {
    "test": ("This is a test file: write only cases (each test's given and expected, exactly as pinned) and structures "
             "for the helpers and fixtures other tests use. There is nothing to cover.", TEST_SHAPE),
    "bare": ("The outline gives this file no interface or component of its own (the repository's tooling, or a "
             "helper): write a structure that says what it is for and what it does, and the claims its comments "
             "make; no behaviour. There is nothing to cover.", BARE_SHAPE),
}


#: The one rule of YAML a model breaks most: a value that is not a plain word or number ends early, or does not read.
QUOTING = ("Put in single quotes any value that is not a plain word or number: a sentence, a signature, anything "
           "holding , : # ? [ ] { }, or starting with * & ! | > % @, a quote or a backtick (write a quote inside one "
           "as two: 'it''s').")


def read_messages(contract: dict, inputs: dict) -> list[dict]:
    role = _text(inputs, "role") or ("test" if _text(inputs, "test") == "yes" else "code")
    say, shape = ROLES.get(role, ("", READ_SHAPE))
    part = _text(inputs, "part")
    head = f"File: {_text(inputs, 'path')} (lines {_text(inputs, 'lines')}). Test file: {_text(inputs, 'test')}.\n"
    if say:
        head += say + "\n"
    if part:
        head += (f"This is part {part} of the file; the other parts are read apart. Cover only the ids under cover; "
                 "cite any id of the outline." + ("" if part.startswith("1 ") else " The component is told by part "
                                                  "1: give no does for it.") + "\n")
    if role not in ROLES:
        head += f"Cover: {_text(inputs, 'cover') or '[]'}\n"
    terms = _text(inputs, "terms")
    user = (head + f"\nThe outline for this file:\n```yaml\n{_text(inputs, 'outline')}```\n\n"
            + (f"Terms the specification already has (reuse their words): {terms}\n\n"
               if terms and terms.strip() not in ("", "[]") else "")
            + f"What this file imports from the other files (elsewhere):\n```yaml\n{_text(inputs, 'elsewhere')}\n```\n\n"
            + (f"Every definition of the file, private ones too (lines, name, signature). Tell a private helper "
               f"inside the behaviour of the interface that uses it, by its name and signature:\n```\n"
               f"{_text(inputs, 'definitions')}\n```\n\n" if _text(inputs, "definitions") else "")
            + f"The code, its lines numbered:\n```\n{_text(inputs, 'code')}\n```\n\n"
            f"Answer in this shape (the values are examples):\n```yaml\n{shape}\n```\n"
            f"{QUOTING}")
    msgs = [{"role": "system", "content": READ_SYSTEM}, {"role": "user", "content": user}]
    if _text(inputs, "failed"):
        msgs.append({"role": "user", "content": "Your last answer for these lines could not be taken: "
                                                f"{_text(inputs, 'failed')}. Answer again, whole, so that it can."})
    return msgs


# ---------------------------------------------------------------------------
# fold: the whole program
# ---------------------------------------------------------------------------

FOLD_SYSTEM = (
    "You read a whole program from its specification so far (files, interfaces, behaviours, cases, settings, "
    "history, each with its id) and from its own documents (their lines numbered), and write, as YAML, what it is "
    "for. Write:\n"
    "- aims (measure: how one would know it is met), audiences (who, needs), uses (one thing a user does, end to "
    "end: for an audience id, via [interface ids], steps [what is typed], gets), requirements (force: must, should "
    "or may; met-by [behaviour or interface ids]; checked-by [case ids]), decisions (chose, over [{option, "
    "because}], because, changed-in [change ids]), exclusions (what it deliberately does not do: horizon never or "
    "later, because), influences (roles {source, on}, how), occasions (roles {event}, when).\n"
    "- atem: line (15 to 25 words: what the program does), focus (at most two sentences), push (one), pull (one: "
    "its limit), cites [the use ids the line rests on].\n"
    "Every entry has slug, name, summary, stance, confidence (0 to 1) and sources: the ids it rests on and the "
    "document lines it reads (README.md#L3-L8). Stance observed only where a document says it, with those lines in "
    "sources; what you reason to is deduced; your own judgement is opinion (confidence at most 0.5). Where neither "
    "the specification nor the documents settle a why or a whether, write {pending: \"<the question>\"} in that "
    "field: a person answers it later. Never invent a reason, a user or a history. Return only the YAML mapping.")

FOLD_SHAPE = """atem: {line: …, focus: …, push: …, pull: …, cites: [N:use/count-words]}
aims: [{slug: quick-counts, name: …, summary: …, stance: observed, confidence: 0.9, measure: …, roles: {for: N:audience/terminal-users}, sources: [README.md#L1-L3]}]
audiences: [{slug: terminal-users, name: …, summary: …, stance: deduced, confidence: 0.7, who: …, needs: …, sources: [README.md#L1-L3]}]
uses: [{slug: count-words, name: …, summary: …, stance: observed, confidence: 0.9, for: N:audience/terminal-users, via: [C:interface/command.tool.count], steps: ['tool count notes.txt'], gets: 'the number of words, one line', sources: [README.md#L5-L6, C:interface/command.tool.count]}]
requirements: [{slug: stdlib-only, name: …, summary: …, stance: observed, confidence: 0.9, force: must, met-by: [C:dependency/python], sources: [README.md#L10]}]
decisions: [{slug: letters-only, name: …, summary: …, stance: deduced, confidence: 0.6, chose: …, over: [{option: …, because: {pending: "why not …?"}}], sources: [C:behaviour/pkg.mod.count-words]}]
exclusions: []
influences: []
occasions: []"""


def fold_messages(contract: dict, inputs: dict) -> list[dict]:
    user = (f"The program: {_text(inputs, 'name')}.\n\nThe specification so far:\n```yaml\n{_text(inputs, 'outline')}"
            f"```\n\nIts documents:\n```\n{_text(inputs, 'documents')}\n```\n\n"
            f"Answer in this shape (the values are examples):\n```yaml\n{FOLD_SHAPE}\n```\n{QUOTING}")
    return [{"role": "system", "content": FOLD_SYSTEM}, {"role": "user", "content": user}]


# ---------------------------------------------------------------------------
# code and readme: one file of the cshort
# ---------------------------------------------------------------------------

CODE_SYSTEM = (
    "You write one file of a Python program from its specification alone; you have never seen its code. The "
    "specification lists the file, its components, its interfaces (exact signatures and parameters), the "
    "structures defined in it, the behaviours and cases about them, the settings and dependencies it touches, the "
    "program's words, the interfaces of the other files it reaches (with the file each lives in and what it does), "
    "and the questions still open about its items (where one is open, do what the items say).\n"
    "Write the whole file:\n"
    "- every interface listed, with exactly its name, its kind (function, class or method) and its signature: the "
    "same parameters in the same order, with their annotations and defaults;\n"
    "- every behaviour, edge and error as specified: the exact output formats and the exact words of every message;\n"
    "- every command line as its usage line and options say, built with the library the specification implies;\n"
    "- imports of the other files by the module paths their files give; the standard library, and only the "
    "dependencies listed;\n"
    "- docstrings that say what each interface is for.\n"
    "Where the specification is silent, choose the plainest code a competent programmer would write, and add "
    "nothing it does not ask for. No tests. Return only the file, in one fenced code block.")

README_SYSTEM = (
    "You write the README of a program from its specification alone: what it is for, the Python and packages it "
    "needs, {uses}, the settings a user can change, and what happens when something goes wrong. Plain words, short "
    "paragraphs, examples in indented blocks. Say nothing the specification does not hold. Write it in {format}, as "
    "the file's name says, and return only that, in one fenced block.")

#: How a README's uses are asked for: with the commands a user types only when the program has a command line.
README_USES = {"yes": "every use with the commands a user types and what they get (use the cases' exact outputs)",
               "no": "every use with the calls a program makes and what they give (use the cases' exact values)"}
README_FORMATS = {"rst": "reStructuredText", "md": "Markdown", "txt": "plain text", "": "Markdown"}


def readme_system(inputs: dict) -> str:
    """The README's system prompt for this file: its format from its name, its uses as commands only when the
    program has a command line."""
    path = _text(inputs, "path")
    ext = path.rsplit(".", 1)[-1].lower() if "." in path.rsplit("/", 1)[-1] else ""
    return (README_SYSTEM.replace("{format}", README_FORMATS.get(ext, "Markdown"))
            .replace("{uses}", README_USES.get(_text(inputs, "commands") or "yes", README_USES["yes"])))


def code_messages(contract: dict, inputs: dict) -> list[dict]:
    readme = step(inputs) == "readme"
    user = (f"The program: {_text(inputs, 'name')}. Its atem:\n```yaml\n{_text(inputs, 'atem')}```\n\n"
            f"Write the file {_text(inputs, 'path')}. Its specification:\n```yaml\n{_text(inputs, 'brief')}```")
    return [{"role": "system", "content": readme_system(inputs) if readme else CODE_SYSTEM},
            {"role": "user", "content": user}]


# ---------------------------------------------------------------------------
# catem: what a user can do
# ---------------------------------------------------------------------------

CATEM_SYSTEM = (
    "You write a catem: what a user can do with a program, from its specification alone (each item with its id). "
    "At depth overview, one section per use, each saying what a user types and what they get. At depth manual, "
    "every use and also every command and public interface a person reaches, with what each does, its options and "
    "its errors. Begin with an intro of one or two sentences. Use the cases' exact commands and outputs in backticks. "
    "Every sentence cites the ids of the items it says, only ids listed under the items; cite every id listed under "
    "must. Say nothing the items do "
    "not hold: no name, number or option they lack. Return only a YAML mapping:\n"
    "intro: [{say: <sentence>, cites: [<ids>]}]\n"
    "sections:\n  - heading: <a use's name, or an interface's>\n    sentences: [{say: <sentence>, cites: [<ids>]}]")


def catem_messages(contract: dict, inputs: dict) -> list[dict]:
    user = (f"The program: {_text(inputs, 'name')}. Depth: {_text(inputs, 'depth')}.\nIts atem:\n```yaml\n"
            f"{_text(inputs, 'atem')}```\nMust be told (cite each): {_text(inputs, 'must')}\n\n"
            f"The items:\n```yaml\n{_text(inputs, 'outline')}```")
    return [{"role": "system", "content": CATEM_SYSTEM}, {"role": "user", "content": user}]


BUILDERS: dict[str, Callable[[dict, dict], list[dict]]] = {
    "read": read_messages, "fold": fold_messages, "code": code_messages, "readme": code_messages,
    "catem": catem_messages}


def messages(contract: dict, inputs: dict) -> list[dict] | None:
    """The messages of a fabulac step's request, or None when the request names no step (another builder's)."""
    s = step(inputs)
    return BUILDERS[s](contract, inputs) if s else None


#: The host's table (enough/thym_host.py, `PROMPT_MODULES`): move → builder, None for a request that is not a
#: fabulac step, so that the host asks the next builder.
PROMPTS: dict[str, Callable[[dict, dict], list[dict] | None]] = {"derive": messages, "entail": messages}


__all__ = ["BUILDERS", "CATEM_SYSTEM", "CODE_SYSTEM", "FOLD_SYSTEM", "PROMPTS", "READ_SYSTEM", "README_SYSTEM",
           "STEPS", "messages", "step"]
