"""The plain moves `thym/1` declares, `cut`, and the editor (docs/THYM.md 6.3, 7.3, 20, 21): `cut`, `count`,
`words`, `digest`, `lint`, `trace`, with the check `weight-order`; for `thym 1`, the editing moves `lines`, `replace`,
`drop`, `insert`, `edit` and `reword`, the helpers `join`, `say`, `folders` and `gather`, and the checks
`only-the-changed`, `one-line`, `nothing-added`, `nothing-lost` and `ids-unique`.

All transcode, the same answer every time, in code, except `reword`, which asks the model for the wording of one
line (its prompt builder is registered here, `reword.prompt`).

- `lines of s` gives every line of a text or a short, blank ones included, front matter and footer included, each a
  `line` numbered from 1 that carries the sha256 of its source and of itself. `replace`, `drop` and `insert` make
  `change` values from lines; `edit s with changes` applies them all at once and gives a new value of s's type,
  never an edit in place. Every line no change names comes through byte for byte, its own line ending kept; a new
  line takes the ending the source uses most.
- `gather parts with f` gives the `with` fabula or volume with every item of every part in it (a part is a fabula, a
  volume or one item): the `with` volume's items first, then each part's in order; an item already there byte for
  byte (`made` aside: it says which run wrote the item) is there once, and two different items under one id are both
  kept, so that `ids-unique` refuses them.

- `cut` shortens a short by whole sentences, the lightest first, until it fits `to N words` or `to N sentences`. A
  sentence weighs what the heaviest item it says weighs (EMF's salience: critical, high, normal, low), read from the
  citations the short carries beside its text (`entailment_of`); among sentences of one weight the later goes first, so
  the opening stays. A short read from disk carries no citations, and every sentence weighs the same. Headings are
  structure: one goes only when nothing is left under it. The footer stays.
- `count` counts a volume's items, a fabula's items, a short's lines or a list's members; `words` counts a text's,
  a short's (its body, without front matter or footer) or an atem line's words; `digest` is a value's sha256 over its
  canonical bytes (THYM.md 12.6); `lint` runs the checks a volume's MiniCOSM selects and gives the report; `trace`
  gives the run's trace so far.

Standalone: the standard library, PyYAML and `enough.macrocosm`.
"""
from __future__ import annotations

import datetime as _dt
import difflib
import re
from typing import Any

from enough import macrocosm as mc
from enough.thym import checks as C
from enough.thym.checks import body, check
from enough.thym.moves import SALIENCE, MoveError, fabula_doc, fold, short_value, entailment_of
from enough.thym.registry import Amount, Request, implements, prompt_for
from enough.thym.values import (
    CHANGE_DOES,
    Value,
    canonical,
    folder_value,
    make_change,
    make_line,
    members,
    plain,
    sha256_bytes,
)


# ---------------------------------------------------------------------------
# cut
# ---------------------------------------------------------------------------

def _units(text: str) -> tuple[str, list[list[str]], str]:
    """A short as (front, paragraphs of units, footer): each unit a sentence by the runtime's sentence rule
    (`checks.sentences`), so that `whole-sentences` reads them the same way."""
    raw = text.replace("\r\n", "\n")
    fm = re.match(r"\A---\n.*?\n---\n?", raw, re.S)
    front = fm.group(0) if fm else ""
    whole = body(raw, footer=True)
    core = body(raw)
    footer = whole[len(core):].strip("\n") if whole.startswith(core) else ""
    paras = [C.sentences(p) for p in re.split(r"\n\s*\n", core) if p.strip()]
    return front, [p for p in paras if p], footer


def _weights(short: Value, units: list[str]) -> list[int]:
    """Each unit's weight: the heaviest salience among the items its sentence cites (normal for an item without one);
    every unit weighs `normal` when the short carries no citations."""
    t = entailment_of(short)
    if not t or t.get("covers") is None:
        return [SALIENCE["normal"]] * len(units)
    fab = t.get("fabula")
    sal = {it.get("id"): SALIENCE.get(str(it.get("salience") or "normal"), 1) for it in fabula_doc(fab)[1]}
    said = [(fold(s), c) for s, c in zip(t.get("sentences") or [], t.get("covers") or [])]
    out = []
    for u in units:
        fu = fold(u)
        cites = next((c for s, c in said if fu == s or fu in s or s in fu), [])
        out.append(max((sal.get(c, 1) for c in cites), default=SALIENCE["normal"]))
    return out


def _is_heading(u: str) -> bool:
    return bool(re.match(r"^#{1,6}\s", u))


def _cites_of(short: Value, kept: list[str]) -> tuple[list[str], list[list[str]]] | None:
    t = entailment_of(short)
    if not t or t.get("covers") is None:
        return None
    said = [(fold(s), c) for s, c in zip(t.get("sentences") or [], t.get("covers") or [])]
    sents, covers = [], []
    for u in kept:
        fu = fold(u)
        hit = next(((s, c) for s, c in said if fu == s or fu in s or s in fu), None)
        if hit is not None and (not sents or sents[-1] != hit[0]):
            sents.append(hit[0])
            covers.append(list(hit[1]))
    return sents, covers


@implements("cut")
def cut(ctx: Any, short: Value, **mods: Any) -> Value:
    """A short shortened by whole sentences, the lightest first (THYM.md 6.3), until it fits `to N words` or `to N
    sentences`."""
    to = mods.get("to")
    if not isinstance(to, Amount) or to.unit not in ("words", "sentences"):
        raise MoveError("cut needs a length: cut <short> to N words, or to N sentences")
    front, paras, footer = _units(short.text())
    flat = [(pi, ui, u) for pi, p in enumerate(paras) for ui, u in enumerate(p)]
    weights = dict(zip(((pi, ui) for pi, ui, _u in flat), _weights(short, [u for _pi, _ui, u in flat])))
    alive = {(pi, ui) for pi, ui, _u in flat}

    def size() -> int:
        kept = [u for pi, ui, u in flat if (pi, ui) in alive]
        return len(kept) if to.unit == "sentences" else sum(C.words(u) for u in kept)

    order = sorted(((pi, ui) for pi, ui, u in flat if not _is_heading(u)),
                   key=lambda k: (weights[k], -k[0], -k[1]))
    for k in order:
        if size() <= to.n or sum(1 for q in order if q in alive) <= 1:
            break                                   # it fits, or one sentence is all that is left
        alive.discard(k)
        # a heading goes when nothing is left under it
        for pi, ui, u in flat:
            if _is_heading(u) and (pi, ui) in alive:
                below = [(qi, vi) for qi, vi, v in flat if (qi, vi) > (pi, ui) and not _is_heading(v)]
                nxt = next(((qi, vi) for qi, vi, v in flat if (qi, vi) > (pi, ui) and _is_heading(v)), None)
                under = [b for b in below if nxt is None or b < nxt]
                if under and not any(b in alive for b in under):
                    alive.discard((pi, ui))
    if size() > to.n:
        raise MoveError(f"cut cannot fit the short to {to.n} {to.unit} by whole sentences")
    kept_paras = [" ".join(u for ui, u in enumerate(p) if (pi, ui) in alive) for pi, p in enumerate(paras)]
    kept_paras = [p for p in kept_paras if p]
    text = front + "\n\n".join(kept_paras) + (f"\n\n{footer}" if footer else "") + "\n"
    if front and not text.startswith(front):
        text = front + text
    kept = [u for pi, ui, u in flat if (pi, ui) in alive]
    t = entailment_of(short) or {}
    cites = _cites_of(short, kept)
    extra = {k: v for k, v in t.items() if k not in ("fabula", "sentences", "covers", "order", "morph")}
    extra["cut_from"] = short.sha256
    if cites is None:
        return short_value(text, fabula=t.get("fabula"), order=t.get("order"), morph=t.get("morph"), **extra)
    return short_value(text, fabula=t.get("fabula"), sentences=cites[0], covers=cites[1], order=t.get("order"),
                       morph=t.get("morph"), **extra)


@check("weight-order")
def _weight_order(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """`cut` removed the lightest sentences first (THYM.md 7.3): no sentence it removed weighs more than a sentence
    it kept (a sentence weighs the heaviest salience among the items it cites)."""
    src = next((v for v in inputs.values() if isinstance(v, Value) and v.type in ("short", "text")), None)
    if src is None:
        return False, "no short among the inputs"
    _f, paras, _foot = _units(src.text())
    units = [u for p in paras for u in p]
    weights = _weights(src, units)
    kept_text = {fold(u) for p in _units(output.text())[1] for u in p}
    removed = [w for u, w in zip(units, weights) if fold(u) not in kept_text and not _is_heading(u)]
    kept = [w for u, w in zip(units, weights) if fold(u) in kept_text and not _is_heading(u)]
    if not entailment_of(src) or entailment_of(src).get("covers") is None:
        return True, "the short carries no citations, so every sentence weighed the same"
    if removed and kept and max(removed) > min(kept):
        names = {v: k for k, v in SALIENCE.items()}
        return False, f"a {names[max(removed)]} sentence was removed while a {names[min(kept)]} one was kept"
    return True, ""


# ---------------------------------------------------------------------------
# count, words, digest, lint, trace
# ---------------------------------------------------------------------------

@implements("count")
def count(ctx: Any, v: Value, **_: Any) -> Value:
    """How many items a volume or a fabula holds, how many lines a short has, how many members a list has, how many
    text files a folder holds (THYM 20.2: its binary files are counted in `files`, never here)."""
    if v.type == "fabula":
        return Value("number", len(fabula_doc(v)[1]))
    if v.type == "folder" and hasattr(v.payload, "texts"):
        return Value("number", len(v.payload.texts()))
    rows = members(v)
    if rows is None:
        raise MoveError(f"a {v.type} has nothing to count")
    return Value("number", len(rows))


@implements("words")
def words(ctx: Any, v: Value, **_: Any) -> Value:
    """How many words: a text's, a short's body (front matter and footer left out), an atem's line, a line's or a
    string's."""
    if v.type in ("line", "string", "word"):
        return Value("number", C.words(str(v.payload or "")))
    if v.type == "atem":
        a = v.mapping() or {}
        line = a.get("line") if isinstance(a.get("line"), str) else (v.payload if isinstance(v.payload, str) else "")
        return Value("number", C.words(line))
    text = v.text()
    return Value("number", C.words(body(text) if v.type == "short" else C.front_matter(text)[1]))


@implements("digest")
def digest(ctx: Any, v: Value, **_: Any) -> Value:
    """A value's sha256, over its canonical bytes (THYM.md 12.6)."""
    return Value("string", v.sha256)


@implements("lint")
def lint(ctx: Any, v: Value, **_: Any) -> Value:
    """The checks a volume's MiniCOSM selects, and their verdicts: `{ok, errors, warnings, notes}`, each a line."""
    vol = v.payload if isinstance(v.payload, mc.Volume) else None
    if vol is None:
        data = v.mapping()
        if data is None:
            raise MoveError(f"a {v.type} is not a volume to lint")
        name = v.path.name if v.path is not None and v.path.suffix == ".cosm" else "volume.cosm"
        vol = mc.load_volume_text(mc.dump(plain(data)), filename=name)
    if vol.refused is not None:
        return Value("report", {"ok": False, "minicosm": vol.oes, "checks": [], "not_run": [],
                                "errors": [str(vol.refused)], "warnings": [], "notes": []})
    rep = mc.lint(vol)
    out = {"ok": rep.ok, "minicosm": vol.oes, "checks": list(rep.checks), "not_run": list(rep.not_run),
           "errors": [str(p) for p in rep.errors], "warnings": [str(p) for p in rep.warnings],
           "notes": [str(p) for p in rep.notes]}
    return Value("report", out)


@implements("trace")
def trace(ctx: Any, **_: Any) -> Value:
    """The run's trace so far (THYM.md 6.3)."""
    return ctx.trace()


# ---------------------------------------------------------------------------
# The editor (THYM 21): lines, changes, edit, reword
# ---------------------------------------------------------------------------

def split_lines(text: str) -> list[tuple[str, str]]:
    """A text's lines as `(line, ending)`: the line without its break, and the break itself (`\\n`, `\\r\\n`, or
    `""` for a last line without one). A text that ends with a break has no empty line after it."""
    if not text:
        return []
    out = []
    parts = text.split("\n")
    last = parts.pop()
    for p in parts:
        out.append((p[:-1], "\r\n") if p.endswith("\r") else (p, "\n"))
    if last:
        out.append((last, ""))
    return out


def _ending(rows: list[tuple[str, str]]) -> str:
    """The line break a new line takes: the one the source uses most (`\\n` when it uses none or as many of each)."""
    crlf = sum(1 for _t, e in rows if e == "\r\n")
    lf = sum(1 for _t, e in rows if e == "\n")
    return "\r\n" if crlf > lf else "\n"


def _source(v: Value, move: str) -> tuple[str, list[tuple[str, str]]]:
    if not isinstance(v, Value) or v.type not in ("text", "short"):
        kind = v.type if isinstance(v, Value) else "nothing"
        raise MoveError(f"{move} reads a text or a short, and was given a {kind}")
    return v.sha256, split_lines(v.text())


@implements("lines")
def lines(ctx: Any, **mods: Any) -> Value:
    """`lines of s`: every line of a text or a short, blank ones included, numbered from 1 (THYM 21.1)."""
    src = mods.get("of")
    of, rows = _source(src, "lines")
    return Value("list", [make_line(t, n, of) for n, (t, _e) in enumerate(rows, 1)])


def _line_of(v: Any, move: str) -> dict:
    """The place a line value carries (`number`, `source`, `sha256`), or a MoveError in the program's words."""
    place = (v.origin or {}).get("line") if isinstance(v, Value) else None
    if not isinstance(place, dict) or not isinstance(place.get("number"), int) or not place.get("source"):
        raise MoveError(f"{move} names a line read with lines of a text or a short; this value is no such line")
    return place


def _new_lines(v: Any, move: str) -> list[str]:
    """The lines a value gives a change: a string's or a line's (split where it holds line breaks), a short's."""
    if not isinstance(v, Value) or v.is_nothing:
        raise MoveError(f"{move} needs the new words, and was given nothing")
    if v.type not in ("string", "line", "short", "word", "text"):
        raise MoveError(f"{move} puts in a string, a line or a short, not a {v.type}")
    text = v.text()
    return [t for t, _e in split_lines(text)] if text else [""]


@implements("replace")
def replace(ctx: Any, l: Value, **mods: Any) -> Value:
    """`replace l with v`: a change that puts v's lines in place of l's (THYM 21.2)."""
    place = _line_of(l, "replace")
    if mods.get("with") is None:
        raise MoveError("replace needs what goes in the line's place: replace l with <a string, a line or a short>")
    new = _new_lines(mods["with"], "replace")
    return make_change(place["number"], place["sha256"], place["source"], "replace", new)


@implements("drop")
def drop(ctx: Any, l: Value, **_: Any) -> Value:
    """`drop l`: a change that takes l's line out (THYM 21.2)."""
    place = _line_of(l, "drop")
    return make_change(place["number"], place["sha256"], place["source"], "drop", [])


@implements("insert")
def insert(ctx: Any, v: Value, **mods: Any) -> Value:
    """`insert v before l`, `insert v after l`: a change that puts v's lines before or after l's; exactly one of
    `before` and `after` (THYM 21.2)."""
    places = [w for w in ("before", "after") if mods.get(w) is not None]
    if len(places) != 1:
        raise MoveError("insert takes before <line> or after <line>, exactly one of the two")
    place = _line_of(mods[places[0]], "insert")
    return make_change(place["number"], place["sha256"], place["source"], f"insert-{places[0]}",
                       _new_lines(v, "insert"))


def _changes(v: Any) -> list[dict]:
    if not isinstance(v, Value) or v.type != "list":
        raise MoveError("edit needs its changes as a list: edit s with changes")
    out = []
    for m in v.payload or []:
        d = m.payload if isinstance(m, Value) else None
        if not isinstance(m, Value) or m.type != "change" or not isinstance(d, dict) or d.get("do") not in CHANGE_DOES:
            raise MoveError("edit takes changes made by replace, drop and insert, and only those")
        out.append(d)
    return out


def change_problems(of: str, rows: list[tuple[str, str]], changes: list[dict]) -> list[str]:
    """What is wrong with a list of changes for the value whose digest is `of` and whose lines are `rows` (THYM
    21.3, the first three conditions of `only-the-changed`), in the program's words; empty when nothing is."""
    out: list[str] = []
    for c in changes:
        at = c.get("at")
        if c.get("of") != of:
            out.append(f"a change names line {at} of another text")
        elif not isinstance(at, int) or not 1 <= at <= len(rows):
            out.append(f"a change names line {at}, and the text has {len(rows)} lines")
        elif c.get("was") != sha256_bytes(rows[at - 1][0].encode("utf-8")):
            out.append(f"line {at} changed since it was read")
    taken: dict[int, str] = {}
    for c in changes:
        if c.get("do") not in ("replace", "drop") or not isinstance(c.get("at"), int):
            continue
        at, do = c["at"], c["do"]
        if at in taken:
            # one line changed twice the same way: "line 7 is replaced twice" (the conductor's ruling L7); two
            # different lines are never met here, since a change names one line
            if taken[at] == do == "replace":
                out.append(f"line {at} is replaced twice")
            elif taken[at] == do:
                out.append(f"line {at} is dropped twice")
            else:
                out.append(f"line {at} is both replaced and dropped")
        taken.setdefault(at, do)
    return out


def apply_changes(rows: list[tuple[str, str]], changes: list[dict]) -> list[tuple[str, str, str]]:
    """The lines after the changes, each `(line, ending, from)`: `from` is `keep:<n>` for an input line that comes
    through and `change:<n>` for a line a change gave. Inserts at one place keep their written order: before a line,
    then the line (or its replacement), then after it."""
    eol = _ending(rows)
    by: dict[int, dict[str, list]] = {}
    for c in changes:
        by.setdefault(c["at"], {}).setdefault(c["do"], []).append(c)
    out: list[tuple[str, str, str]] = []
    for n, (text, end) in enumerate(rows, 1):
        mine = by.get(n, {})
        for c in mine.get("insert-before", []):
            out += [(x, eol, f"change:{n}") for x in c["lines"]]
        if "replace" in mine:
            out += [(x, eol, f"change:{n}") for x in mine["replace"][0]["lines"]]
        elif "drop" not in mine:
            out.append((text, end, f"keep:{n}"))
        for c in mine.get("insert-after", []):
            out += [(x, eol, f"change:{n}") for x in c["lines"]]
    if rows and rows[-1][1] == "" and out:            # a source without a last line break gives an output without one
        out = [(t, e or eol, f) for t, e, f in out[:-1]] + [(out[-1][0], "", out[-1][2])]
    return out


@implements("edit")
def edit(ctx: Any, s: Value, **mods: Any) -> Value:
    """`edit s with changes`: s with every change applied at once, a new value of s's type; nothing is edited in place
    (THYM 21.2, 21.3)."""
    of, rows = _source(s, "edit")
    changes = _changes(mods.get("with"))
    bad = change_problems(of, rows, changes)
    if bad:
        raise MoveError("; ".join(dict.fromkeys(bad)))
    text = "".join(t + e for t, e, _f in apply_changes(rows, changes))
    return Value(s.type, text)


def _edited(inputs: dict) -> tuple[str | None, Value | None, Value | None]:
    src = next(((k, v) for k, v in inputs.items() if k != "with" and isinstance(v, Value)
                and v.type in ("text", "short")), (None, None))
    return src[0], src[1], inputs.get("with")


@check("only-the-changed")
def _only_the_changed(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """`edit`'s contract (THYM 21.3): every change names the value edited and a line it holds with that digest; no
    line is replaced or dropped twice; and the output is the input with exactly those changes: every line no change
    names comes through byte for byte and in order, and no line comes that neither the input nor a change gave."""
    name, src, with_ = _edited(inputs)
    if src is None:
        return False, "no text or short among the inputs"
    try:
        changes = _changes(with_)
    except MoveError as e:
        return False, str(e)
    rows = split_lines(src.text())
    bad = change_problems(src.sha256, rows, changes)
    if bad:
        return False, "; ".join(dict.fromkeys(bad))
    want = apply_changes(rows, changes)
    got = split_lines(output.text())
    sm = difflib.SequenceMatcher(None, [t for t, _e, _f in want], [t for t, _e in got], autojunk=False)
    for op, a1, a2, b1, b2 in sm.get_opcodes():
        if op == "equal":
            continue
        for t, _e, frm in want[a1:a2]:
            kind, n = frm.split(":")
            if kind == "change":
                return False, f"line {n} is not what its change says"
            what = "is missing from the output" if op == "delete" else "differs in the output"
            return False, f"line {n} of {name}, which no change names, {what}"
        line = got[b1][0]
        return False, f"the output holds a line that neither {name} nor a change gave: {line[:60]}"
    if "".join(t + e for t, e, _f in want) != output.text():
        return False, f"the output's line breaks are not {name}'s"
    return True, ""


def _morph_note(m: Any) -> str:
    if not isinstance(m, Value) or m.is_nothing:
        return ""
    from enough.thym.moves.morph import asks_for          # here, so that importing this module imports no other
    return asks_for(m)


def _reworded(v: Value, text: str) -> Value:
    """The model's words as a value of the type reworded: a line keeps the number and the source of the line it
    rewords; a string is a string; a short ends with a line break."""
    if v.type == "line":
        place = (v.origin or {}).get("line") or {}
        return make_line(text, int(place.get("number") or 0), str(place.get("source") or ""))
    if v.type == "short":
        return Value("short", text.rstrip("\n") + "\n")
    return Value(v.type if v.type in ("string", "word") else "string", text)


@implements("reword")
def reword(ctx: Any, v: Value, **mods: Any) -> Request:
    """`reword l to N words`: asks the model to say l again in at most N words, adding nothing; the same type as l
    (THYM 21.4). An answer of several lines for a line is repaired by joining them with a space (`one-line`)."""
    to = mods.get("to")
    if not isinstance(to, Amount) or to.unit != "words":
        raise MoveError("reword needs a length: reword l to N words")
    if not isinstance(v, Value) or v.type not in ("line", "string", "word", "short"):
        raise MoveError("reword says again a line, a string or a short")
    inputs = {"line": v, "words": Value("number", to.n), "kind": Value("word", v.type)}
    note = _morph_note(mods.get("with"))
    if note:
        inputs["morph"] = Value("string", note)

    def parse(out: Any) -> Value:
        text = str(out if out is not None else "")
        text = text.strip() if v.type != "short" else text.strip("\n")
        if not text:
            raise ValueError("the answer is empty")
        return _reworded(v, text)

    def repair(value: Any, failed: list) -> Any:
        names = {f.get("name") for f in failed or [] if isinstance(f, dict)}
        if "one-line" in names and isinstance(value, Value) and "\n" in value.text().strip("\n"):
            joined = " ".join(x.strip() for x in value.text().splitlines() if x.strip())
            return _reworded(v, joined).copy(made=value.made, state=value.state)
        return None

    return Request(contract={"schema": {"format": "markdown", "says": "the words alone, nothing before or after"},
                             "repair": ["one-line"]},
                   inputs=inputs, parse=parse, repair=repair, budget={"output_words": to.n})


@prompt_for("reword")
def reword_messages(contract: dict, inputs: dict) -> list[dict]:
    """The request `reword` makes of the model: the line, its length, the morph when one is given (THYM 21.4)."""
    def get(name: str) -> str:
        pair = (inputs or {}).get(name)
        v = pair[0] if isinstance(pair, (tuple, list)) else pair
        return v.text() if isinstance(v, Value) else str(v if v is not None else "")

    n = int(get("words") or 30)
    kind = get("kind") or "line"
    what = "text" if kind == "short" else "line"
    system = (f"You say a {what} again in fewer words: at most {n} words, and no fewer than {n * 4 // 5}. Keep what it "
              f"says and add nothing: use only the names, numbers and words it uses, or plain common words. "
              + ("Answer with the new line alone, on one line, with nothing before or after it."
                 if what == "line" else "Answer with the new text alone, with nothing before or after it."))
    morph = get("morph")
    if morph:
        system += f"\nSay it in this morph, keeping each scale near its number:\n{morph}"
    return [{"role": "system", "content": system}, {"role": "user", "content": f"The {what}:\n{get('line')}"}]


#: The prompt builders this module carries, by move: the host reads them (its `PROMPT_MODULES`) and puts them in
#: front of its own; `prompt_for` above registers the same builder when no host is there.
PROMPTS = {"reword": reword_messages}


@check("one-line")
def _one_line(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """A reworded line is one line (THYM 7.3); an answer of several lines is repaired by joining them with a space."""
    if output.type != "line":
        return True, ""
    n = len([x for x in output.text().strip("\n").split("\n")])
    return (True, "") if n == 1 else (False, f"the reworded line is {n} lines, not one")


_NUMBERISH = re.compile(r"\d")


@check("nothing-added")
def _nothing_added(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every name, number and word outside FEED in the output is in the input (THYM 7.3, 21.4): a narrow
    `no-invention` that needs no fabula. A word that is not in the input is looked up in FEED (`ctx.engines["feed"]`);
    without FEED only names and numbers are held to the input."""
    said = " ".join(v.text() for k, v in inputs.items()
                    if k != "with" and isinstance(v, Value) and v.type in ("line", "string", "word", "short", "text"))
    have = {w.lower() for w in C._WORDS.findall(said)}
    lookup = (getattr(ctx, "engines", None) or {}).get("feed")
    text = output.text()
    unknown: list[str] = []
    for m in C._WORDS.finditer(text):
        w = m.group(0)
        if w.lower() in have:
            continue
        if _NUMBERISH.search(w):
            return False, f"the number {w} is not in what was reworded"
        before = text[:m.start()].rstrip()
        starts = not before or before[-1] in ".!?:\n\"“"
        if w[:1].isupper() and not starts:
            return False, f"the name {w} is not in what was reworded"
        unknown.append(w)
    if not unknown:
        return True, ""
    if lookup is None:
        return True, "FEED is not here; only names and numbers were held to what was reworded"
    for w in dict.fromkeys(unknown):
        try:
            found = lookup([w]) or {}
        except Exception:  # noqa: BLE001 - a FEED that cannot be read grounds nothing, and says so
            return False, "FEED could not be read"
        if not any(isinstance(x, dict) for x in found.values()):
            return False, f"the word {w} is in neither FEED nor what was reworded"
    return True, ""


# ---------------------------------------------------------------------------
# join, say, folders (THYM 20.2, 21.2)
# ---------------------------------------------------------------------------

@implements("join")
def join(ctx: Any, xs: Value, **mods: Any) -> Value:
    """`join xs`: a short of the members, one per line; `join xs with "…"`: the members joined by the string."""
    if not isinstance(xs, Value) or xs.type != "list":
        raise MoveError("join takes a list of strings, lines or shorts")
    sep = mods.get("with")
    by = "\n" if sep is None else (sep.text() if isinstance(sep, Value) else str(sep))
    parts = [("" if not isinstance(m, Value) or m.is_nothing else m.text().rstrip("\r\n")) for m in xs.payload or []]
    text = by.join(parts)
    return Value("short", text + "\n" if text else "")


@implements("say")
def say(ctx: Any, v: Value, **_: Any) -> Value:
    """`say n`: a number, a date, a word or a bool as a string (`true`, `false`; a date as YYYY-MM-DD)."""
    p = v.payload if isinstance(v, Value) else v
    if isinstance(p, bool):
        return Value("string", "true" if p else "false")
    if isinstance(p, (_dt.date, _dt.datetime)):
        return Value("string", p.isoformat())
    if isinstance(p, (int, str)):
        return Value("string", str(p))
    raise MoveError(f"say gives a number, a date, a word or a bool as a string, not a {getattr(v, 'type', v)}")


@implements("folders")
def folders(ctx: Any, **mods: Any) -> Value:
    """`folders of d`: the folders directly below d that the folder rule keeps, in path order (THYM 20.2)."""
    d = mods.get("of")
    if not isinstance(d, Value) or not hasattr(d.payload, "folders"):
        raise MoveError("folders lists the folders of a folder: folders of d")
    return Value("list", [folder_value(f) for f in d.payload.folders()])


# ---------------------------------------------------------------------------
# gather (THYM 20.6, 22.1): parts into the `with` volume
# ---------------------------------------------------------------------------

def _volume_doc(v: Value) -> tuple[dict, list[dict]]:
    """A fabula's or a volume's catalog (without its items) and its items, as plain mappings."""
    p = v.payload
    if isinstance(p, mc.Volume):
        cat, items = dict(p.catalog), [dict(it.data) for it in p.items.values()]
    else:
        cat, items = fabula_doc(v)
    return ({k: plain(x) for k, x in cat.items() if k != "nodes"}, [plain(it) for it in items])


def _part_items(v: Any) -> list[dict]:
    if not isinstance(v, Value) or v.is_nothing:
        return []
    if v.type in ("fabula", "volume"):
        return _volume_doc(v)[1]
    m = v.mapping()
    if isinstance(m, dict) and isinstance(m.get("nodes"), list):
        return [plain(n) for n in m["nodes"] if isinstance(n, dict)]
    if isinstance(m, dict) and "id" in m:
        return [plain(m)]
    raise MoveError(f"gather gathers fabulas, volumes and items, not a {v.type}")


#: The fields of an item a rules pass reads exactly (its place, its name, its signature, its digest): a reading that
#: carries one must carry it unchanged, never with anything added inside it (THYM 20.6; docs/fabula-landed-T1-code.md).
RULES_FIELDS = frozenset(("id", "type", "name", "summary", "stance", "span", "signature", "path", "sha256", "length",
                          "defined-in", "surface", "language", "exported", "key", "set-in", "default", "entry"))


class MergeConflict(MoveError):
    """Two items of one id that say different things in one field."""


def _pending(v: Any) -> bool:
    return isinstance(v, dict) and set(v) == {"pending"}


def merge_value(base: Any, add: Any, where: str) -> Any:
    """`add` laid over `base`, adding only: a mapping gains the keys it lacks (and each key both hold is merged in
    turn); a list keeps the base's entries in order, each merged with the entry at its place, and gains the entries
    after them; anything else must be equal. An open question (`{pending: …}`) in the base is answered by a value. A
    `MergeConflict` names the field where they differ."""
    if _pending(base) and not _pending(add):
        return add
    if isinstance(base, dict) and isinstance(add, dict):
        out = dict(base)
        for k, v in add.items():
            out[k] = merge_value(base[k], v, f"{where}.{k}") if k in base else v
        return out
    if isinstance(base, list) and isinstance(add, list):
        if len(add) < len(base):
            raise MergeConflict(f"{where} holds {len(base)} entries, and the other gives {len(add)}")
        return [merge_value(b, a, f"{where}[{i}]") for i, (b, a) in enumerate(zip(base, add))] + add[len(base):]
    if base != add:
        raise MergeConflict(f"{where} differs: {str(base)[:60]!r} against {str(add)[:60]!r}")
    return base


def merge_item(base: dict, add: dict) -> dict:
    """Two items of one id as one (THYM 20.6, a reading enriching the outline): `add` may give the fields `base`
    lacks, and add inside a field (a parameter's `means`, an error's `when`); a field a rules pass reads
    (`RULES_FIELDS`) is never changed, not even by an addition; `made` is the runtime's and is left as the base has it;
    `provenance.sources` is the union of both. A `MergeConflict` names the item and the field."""
    iid = str(base.get("id"))
    out = dict(base)
    for k, v in add.items():
        if k == "made":
            continue
        if k not in base:
            out[k] = v
        elif k in RULES_FIELDS:
            if base[k] != v:
                raise MergeConflict(f"{iid}: its {k} is read by rules, and the other item changes it")
        elif k == "provenance" and isinstance(v, dict) and isinstance(base[k], dict):
            p = dict(base[k])
            for pk, pv in v.items():
                if pk == "sources":
                    p["sources"] = list(p.get("sources") or []) + [x for x in pv or [] if x not in (p.get("sources")
                                                                                                    or [])]
                elif pk not in p:
                    p[pk] = pv
                elif p[pk] != pv and pk != "state":
                    raise MergeConflict(f"{iid}: provenance.{pk} differs")
            out[k] = p
        else:
            try:
                out[k] = merge_value(base[k], v, k)
            except MergeConflict as e:
                raise MergeConflict(f"{iid}: {e}") from None
    return out


def merge_nodes(nodes: list[dict], parts: list[list[dict]]) -> list[dict]:
    """`nodes` with every item of every part in it: a new id appended, a known id merged (`merge_item`)."""
    out = [dict(n) for n in nodes]
    at = {str(n.get("id")): i for i, n in enumerate(out)}
    for items in parts:
        for it in items:
            key = str(it.get("id"))
            if key in at:
                out[at[key]] = merge_item(out[at[key]], it)
            else:
                at[key] = len(out)
                out.append(dict(it))
    return out


@implements("gather")
def gather(ctx: Any, parts: Value, **mods: Any) -> Value:
    """`gather parts with f`: f with every item of every part in it, nothing lost (THYM 20.6, 22.1). An item whose id
    the volume already has is the same item, and may add what it says (a reading enriching the outline): the fields
    the volume's lacks, never a field it has said otherwise; such a clash is refused, naming the item and the field."""
    w = mods.get("with")
    if not isinstance(w, Value) or w.type not in ("fabula", "volume"):
        raise MoveError("gather needs the volume it gathers into: gather parts with f")
    if not isinstance(parts, Value) or parts.type != "list":
        raise MoveError("gather takes a list of fabulas or of items")
    cat, nodes = _volume_doc(w)
    try:
        nodes = merge_nodes(nodes, [_part_items(p) for p in parts.payload or []])
    except MergeConflict as e:
        raise MoveError(f"gather cannot join what two parts say of one item: {e}") from None
    return Value(w.type, {**cat, "nodes": nodes})


def _bytes(item: dict) -> bytes:
    """An item's canonical bytes with its `made` aside: `made` says which run wrote the item, and the runtime writes
    it into every item of a value that carries none (THYM 5.3), so an item gathered from a value a run gave and the same
    item read from disk are one item."""
    return canonical({k: x for k, x in item.items() if k != "made"})


def _within(part: Any, whole: Any) -> bool:
    """Everything `part` says is in `whole`: each key, with what it holds; a list's entries at their places (the whole
    may hold more after them); a source list as a set; an open question answered counts as kept."""
    if _pending(part) and not _pending(whole):
        return True
    if isinstance(part, dict) and isinstance(whole, dict):
        for k, v in part.items():
            if k == "made":
                continue
            if k not in whole:
                return False
            if k == "sources" and isinstance(v, list) and isinstance(whole[k], list):
                if not set(map(str, v)) <= set(map(str, whole[k])):
                    return False
            elif k == "state":
                continue
            elif not _within(v, whole[k]):
                return False
        return True
    if isinstance(part, list) and isinstance(whole, list):
        return len(part) <= len(whole) and all(_within(a, b) for a, b in zip(part, whole))
    return part == whole


def _same(want: dict, got: dict) -> bool:
    """An item is in the output with everything it says (`_within`; `made` aside)."""
    return _within(want, got)


@check("nothing-lost")
def _nothing_lost(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every item of every part gathered, and of the `with` volume, is in the output with every field it carries,
    as it carries it: the output's item may say more (a reading's added fields), never less or otherwise (THYM 7.3)."""
    out = {}
    for it in _part_items(output):
        out.setdefault(str(it.get("id")), []).append(it)
    for name, v in inputs.items():
        rows = v.payload if isinstance(v, Value) and v.type == "list" else [v]
        for part in rows:
            if not isinstance(part, Value) or part.is_nothing:
                continue
            try:
                items = _part_items(part)
            except MoveError:
                continue
            for it in items:
                iid = str(it.get("id"))
                whose = "the volume gathered into" if name == "with" else name
                if not out.get(iid):
                    return False, f"{iid}, of {whose}, is not in the output"
                if not any(_same(it, o) for o in out[iid]):
                    return False, f"{iid}, of {whose}, is in the output changed"
    return True, ""


@check("ids-unique")
def _ids_unique(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """No two different items of the output share an id; two byte-equal ones are one, and two that say the same item
    are merged into one by `gather` before they land (THYM 7.3)."""
    seen: dict[str, bytes] = {}
    for it in _part_items(output):
        iid, b = str(it.get("id")), _bytes(it)
        if iid in seen and seen[iid] != b:
            return False, f"two different items share the id {iid}"
        seen.setdefault(iid, b)
    return True, ""


__all__ = ["PROMPTS", "RULES_FIELDS", "MergeConflict", "merge_item", "merge_nodes", "merge_value", "apply_changes", "change_problems", "count", "cut", "digest", "drop", "edit", "folders", "gather",
           "insert", "join", "lines", "lint", "replace", "reword", "reword_messages", "say", "split_lines", "trace",
           "words"]
