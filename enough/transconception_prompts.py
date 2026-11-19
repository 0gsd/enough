"""The prompts of a transconception's entailing into another language (Thym 20.10; MacroCOSM OES 18.4.9).

Two steps ask a model, each naming itself in the input `fabulac`, as the fabulac's own steps do
(`enough/fabulac_prompts.py`, which chains these in front of its own):

- `layout`: `entail f as layout in <language>`: the files of the program to be, in the order they are written, the
  name each kept interface takes there, the target's own types, what fills each gap (YAML;
  `enough.thym.moves.transconceive.parse_layout` checks it by rules);
- `code-in`: `entail f as code in <language> with layout`: one file, then what the writer chose where the fabulac is
  silent, under `## Notes` (`file_and_notes` reads both; the notes land in the cshort's `NOTES.md`).

What they ask is what made the experiment's four writers succeed (x0 step A8: every cshort built at its first build
and agreed with the original on every counted step at its first judge): the working fabulac and its rulings for that
target, never the source when entailed apart; the weighing's gaps, with what provides each reliance; the cases as the
judge, compared byte for byte at every interface ruled kept; and a guess written down, never silent (their NOTES.md).
Beside the source (the person's own code, or an open lane, and only when the person asked) the source is shown as a
reader's aid, never to be copied.

Each system prompt stays under 2,000 characters, as the fabulac's own do.
"""
from __future__ import annotations

from typing import Any, Callable


def _text(inputs: dict, name: str) -> str:
    """An input's text, as a value or the `(value, sha256)` pair the runtime hands a coprocessor (as
    `enough.fabulac_prompts._text`; kept here so that neither module imports the other first)."""
    v: Any = (inputs or {}).get(name)
    if isinstance(v, tuple):
        v = v[0]
    if v is None:
        return ""
    t = getattr(v, "text", None)
    return t() if callable(t) else str(v)

STEPS = ("layout", "code-in")

LAYOUT_SYSTEM = (
    "You lay out a program to be written in {language}, from its fabulac alone: what the program does as a person "
    "or another program sees it, ruled interface by interface for {language}. You have never seen its code. Plan the "
    "files of the new program as a {language} programmer would, in the order they are written (the files others "
    "lean on first), and say what each holds.\n"
    "- Every interface under map is held by one file, with the name it takes there in {language}: a function, a "
    "type, a method, or the program's entry. An interface ruled changed or free still needs a home.\n"
    "- Each item under types takes {language}'s own type where its ruling allows (own-types): name that type.\n"
    "- Each gap the weighing found is filled: by the standard library's part, a library pinned by name and version, "
    "or code written in a file you name.\n"
    "- Include the file {language}'s tools need to build the program (its module or package file). No tests.\n"
    "Name only the ids given. Reply with one YAML mapping, nothing else:\n"
    "files: [{path, holds: <one sentence>, interfaces: [{id, name}]}]\n"
    "types: [{for: <id>, type: <the type>}]\n"
    "gaps: [{for: <id>, fill: <what fills it>}]")

CODE_IN_SYSTEM = (
    "You write one file of a program in {language}. The program is a transconception: it does what its fabulac says "
    "the original does, written anew. {seen}\n"
    "The cases are the judge. For every case of an interface ruled kept, the program's exit status, standard output "
    "and error output must be the case's, byte for byte. An interface ruled alike may differ only as its allowance "
    "says; one ruled changed does what its ruling says; one ruled free is yours to choose. A reliance is provided as "
    "the weighing says (built in, a library, or written here), and a gap is filled as the layout says.\n"
    "Define every name the layout gives this file, with exactly that name; call the other files by the names the "
    "layout gives them. Use the language's own types where a ruling allows it.\n"
    "Where the fabulac is silent, choose the plainest code and write the guess down: a guess is never silent.\n"
    "Return the whole file in one fenced code block. After it, under a line ## Notes, one bullet for each thing the "
    "fabulac left unsaid and what you chose (none if nothing).")

SEEN = {"apart": "You have never seen the original's code: you have the fabulac and the layout, and nothing else.",
        "beside": "The original's source is shown beside the fabulac, to read and never to copy: no line of it goes "
                  "into the file, and where it and the fabulac's rulings differ, the rulings decide."}


def layout_messages(contract: dict, inputs: dict) -> list[dict]:
    lang = _text(inputs, "language") or "the target language"
    user = (f"The program: {_text(inputs, 'name')}, to be written in {lang} (its files end in "
            f"{_text(inputs, 'suffixes')}).\n\nWhat the fabulac holds of it:\n```yaml\n{_text(inputs, 'program')}```\n\n"
            f"map (every one in a file, under a name):\n{_text(inputs, 'map')}\n\n"
            f"types (own-types):\n{_text(inputs, 'types')}\n\ngaps (the weighing's):\n{_text(inputs, 'gaps')}\n\n"
            f"The weighing's conditions:\n{_text(inputs, 'conditions')}")
    return [{"role": "system", "content": LAYOUT_SYSTEM.replace("{language}", lang)},
            {"role": "user", "content": user}]


def code_in_messages(contract: dict, inputs: dict) -> list[dict]:
    lang = _text(inputs, "language") or "the target language"
    seen = SEEN.get(_text(inputs, "entailed").strip() or "apart", SEEN["apart"])
    user = (f"The program: {_text(inputs, 'name')}, in {lang}. Its layout:\n\n{_text(inputs, 'layout')}\n\n"
            f"Write the file {_text(inputs, 'path')}. What the fabulac says of it:\n```yaml\n{_text(inputs, 'brief')}```")
    src = _text(inputs, "source")
    if src.strip() and (_text(inputs, "entailed").strip() == "beside"):
        user += f"\n\nThe original's source, beside (to read, never to copy):\n```\n{src}\n```"
    return [{"role": "system", "content": CODE_IN_SYSTEM.replace("{language}", lang).replace("{seen}", seen)},
            {"role": "user", "content": user}]


BUILDERS: dict[str, Callable[[dict, dict], list[dict]]] = {"layout": layout_messages, "code-in": code_in_messages}


__all__ = ["BUILDERS", "CODE_IN_SYSTEM", "LAYOUT_SYSTEM", "SEEN", "STEPS", "code_in_messages", "layout_messages"]
