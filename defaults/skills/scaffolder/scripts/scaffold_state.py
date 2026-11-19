#!/usr/bin/env python3
"""Read and write a plectrum and a scaffold's state: one model for both.

The grammar is `references/plectrum.md`; the state is `references/state.md`.
Standard library only, and nothing of any harness: every engine and every
export reads a scaffold through this one file.

    loads(text)          -> Scaffold      (raises StateError: line, problem, fix)
    dumps(model, kind)   -> str           (kind "scaffold" or "plectrum"; default the model's own)
    validate(model)      -> list[str]     (problems, each naming the fix; empty when sound)
    to_json(model)       -> str           (the shape `state.md` gives "for a program")
    from_json(text)      -> Scaffold
    count(model)         -> dict          (frames, boxes, parts, targets by unit)
    count_line(model)    -> str           ("This is 8 frames and 19 boxes, 27 parts in all.")
    as_plectrum(model)   -> Scaffold      (the plectrum back out of a state)

A file this writer wrote reads back and writes again to the same bytes. A
file a person typed reads to the same model as the writer's form of it.

From a shell:

    python3 scaffold_state.py check FILE      the count line, or the refusal
    python3 scaffold_state.py json FILE       the model as JSON
    python3 scaffold_state.py write FILE      the writer's form of FILE
    python3 scaffold_state.py plectrum FILE   the plectrum back out of a state
"""

from __future__ import annotations

import copy
import json
import re
import sys
from dataclasses import dataclass, field
from typing import Any

GRAMMAR = 1
THINGS = ("page", "deck", "document")
SHAPES = ("page", "slide", "letter")
UNITS = ("c", "w")
AIMS = ("thing", "map", "diagram", "system")
KINDS = ("text", "graphic")
AS_KNOWN = ("title", "headline", "lede", "body", "step", "tile", "deck", "call",
            "caption", "quote", "speaker", "notes")
GRAPHIC_WORDS = ("portrait", "landscape", "square")
PLEC_BY = ("readvisor", "person")
FINDING_KINDS = ("spelling", "grammar", "truth")
FINDING_STATUSES = ("open", "accepted", "declined", "cannot be checked")
MAX_PLEC = 2000
MAX_ID = 40

#: The writer's key orders (`state.md` 1, 2, 3 and 5).
FRONT_KEYS = ("title", "thing", "for", "writes", "next", "shape", "unit", "lang", "aim")
STATE_FRONT_KEYS = ("version", "parent", "locked", "checked")
FRAME_KEYS = ("id", "shape", "repeat", "copy-of", "copy")
BOX_KEYS = ("as", "kind", "target", "shape", "row", "col", "place", "fixed", "chips",
            "plec-by", "state", "href", "plec")
FINDING_KEYS = ("id", "box", "kind", "quote", "prefix", "suffix", "fix", "why", "status",
                "version")
_ESCAPED = ("quote", "prefix", "suffix", "fix")

_ID_RE = r"^[a-z0-9][a-z0-9-]{0,39}$"
_KEY_RE = r"^([a-z][a-z-]*):(?: (.*)|)$"
_TARGET_RE = r"^(0|[1-9][0-9]{0,5})([cw]?)$"
_RATIO_RE = r"^[1-9][0-9]{0,2}:[1-9][0-9]{0,2}$"
_LINE_PLEC_RE = r"^- (.+?) \[([^\]]*)\]: (.+)$"
_STAMP_RE = r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$"
_TEXT_ESCAPE_RE = r"^\\*#"
_TEXT_UNESCAPE_RE = r"^\\+#"


def _match(pattern: str, value: str) -> re.Match[str] | None:
    """`re.match`; the patterns stay strings, which `re` caches."""
    return re.match(pattern, value)


def is_stamp(value: str) -> bool:
    """A UTC time as the state writes it, `YYYY-MM-DDTHH:MM:SSZ`."""
    return bool(_match(_STAMP_RE, value))


class StateError(ValueError):
    """A refusal: the line it was found on (0 when there is none), what was
    found, and the fix, in one sentence each."""

    def __init__(self, message: str, line: int = 0):
        super().__init__(f"Line {line}: {message}" if line else message)
        self.line = line


@dataclass
class Scaffold:
    """A plectrum or a scaffold's state. `kind` says which the file was.

    `meta` holds the front matter under the file's own key names (`for`,
    not `for_`) plus `extra`; frames and findings are plain dicts in the
    shape `state.md` gives for a program, so `to_json` is the model as is."""
    kind: str = "plectrum"
    meta: dict[str, Any] = field(default_factory=dict)
    frames: list[dict[str, Any]] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def boxes(self) -> list[dict[str, Any]]:
        return [b for f in self.frames for b in f["boxes"]]

    def box(self, box_id: str) -> dict[str, Any] | None:
        return next((b for b in self.boxes() if b["id"] == box_id), None)

    def frame(self, frame_id: str) -> dict[str, Any] | None:
        return next((f for f in self.frames if f["id"] == frame_id), None)


# ---------------------------------------------------------------------------
# Small rules
# ---------------------------------------------------------------------------

def slug(name: str) -> str:
    """`plectrum.md` 6: lowercase, runs of anything but a-z0-9 to one '-',
    no '-' at either end, cut to 40, no '-' left at the end by the cut."""
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s[:MAX_ID].rstrip("-")


def default_shape(thing: str) -> str:
    return {"deck": "slide", "document": "letter"}.get(thing, "page")


def default_unit(thing: str) -> str:
    return "w" if thing == "document" else "c"


def _target(raw: str, unit: str) -> str | None:
    """`140c`, `300w`, a bare number in the front matter's unit, `0` for none."""
    m = _match(_TARGET_RE, raw.strip().lower().replace(" ", ""))
    if not m:
        return None
    if m.group(1) == "0":
        return "0"
    return m.group(1) + (m.group(2) or unit)


def _graphic_shape_ok(shape: str) -> bool:
    return bool(_match(_RATIO_RE, shape)) or shape in GRAPHIC_WORDS


def _place_ok(place: str) -> bool:
    parts = place.split()
    if len(parts) != 4:
        return False
    try:
        return all(0 <= float(p) <= 100 for p in parts)
    except ValueError:
        return False


def _int_or_text(value: str) -> int | str | None:
    if value == "":
        return None
    return int(value) if value.isdigit() else value


def _plain(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n")


def _unescape(value: str) -> str:
    out, i = [], 0
    while i < len(value):
        ch = value[i]
        if ch == "\\" and i + 1 < len(value) and value[i + 1] in "\\n":
            out.append("\n" if value[i + 1] == "n" else "\\")
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

class _Lines:
    def __init__(self, text: str):
        text = text.replace("\r\n", "\n")
        self.lines = text.split("\n")
        if self.lines and self.lines[-1] == "":
            self.lines.pop()
        self.i = 0

    def more(self) -> bool:
        return self.i < len(self.lines)

    def peek(self) -> str:
        return self.lines[self.i]

    def take(self) -> str:
        line = self.lines[self.i]
        self.i += 1
        return line

    @property
    def n(self) -> int:
        """The 1-based number of the line `peek` would give."""
        return self.i + 1

    def skip_blank(self) -> None:
        while self.more() and not self.peek().strip():
            self.i += 1


def _keyvals(lines: _Lines, what: str, start: int, *, fence: bool) -> tuple[dict[str, str], dict[str, int]]:
    """`key: value` lines up to a closing ``` (a block) or `---` (the front
    matter). A line starting with two spaces continues the last value."""
    out: dict[str, str] = {}
    where: dict[str, int] = {}
    last: str | None = None
    closer = "```" if fence else "---"
    while True:
        if not lines.more():
            raise StateError(f"the {what} opened on line {start} is never closed. "
                             f"End it with a line `{closer}`.", start)
        n, line = lines.n, lines.take()
        if line == closer:
            return out, where
        if fence and line.startswith("```"):
            raise StateError(f"a fence `{line}` inside the {what}. Close the {what} "
                             f"with a line `{closer}` first.", n)
        if not line.strip() or (not fence and line.startswith("#")):
            continue
        if line.startswith("  ") and last is not None:
            out[last] = (out[last] + " " + line.strip()).strip()
            continue
        m = _match(_KEY_RE, line.rstrip())
        if not m:
            raise StateError(f"`{line.strip()[:60]}` in the {what} is not a `key: value` line. "
                             f"Write it as a lowercase key, `: ` and the value.", n)
        key, value = m.group(1), (m.group(2) or "").strip()
        if key in out:
            raise StateError(f"the key `{key}` is given twice in the {what}. Keep one.", n)
        out[key] = value
        where[key] = n
        last = key


def loads(text: str) -> Scaffold:
    """Read a plectrum or a state. Refuses the whole file on the first
    problem, never half of it."""
    lines = _Lines(text)
    if not lines.more() or lines.peek() != "---":
        if lines.more() and lines.peek().startswith("# "):
            raise StateError("this is an outline (it starts with a `# ` line), not a plectrum. "
                             "A plectrum starts with `---` and then `plectrum: 1`.", 1)
        raise StateError("a plectrum starts with a line `---`. Put `---` and then "
                         "`plectrum: 1` (or `scaffold: 1` for a state) at the top.", 1)
    lines.take()
    head_n = lines.n
    head = lines.take() if lines.more() else ""
    m = re.match(r"^(plectrum|scaffold):\s*(\S*)\s*$", head)
    if not m:
        raise StateError("the second line says what the file is. Make it `plectrum: 1` "
                         "or `scaffold: 1`.", head_n)
    kind, version = m.group(1), m.group(2)
    if version != str(GRAMMAR):
        raise StateError(f"`{kind}: {version}` is a grammar this reader does not know. "
                         f"This reader reads `{kind}: {GRAMMAR}`.", head_n)
    front, where = _keyvals(lines, "front matter", 1, fence=False)
    model = Scaffold(kind=kind)
    model.meta = _read_front(front, where, kind)

    lines.skip_blank()
    if not lines.more() or not lines.peek().startswith("# "):
        raise StateError("after the front matter comes the title line. Add `# ` and the "
                         "thing's title.", lines.n if lines.more() else len(lines.lines))
    title_n, title_line = lines.n, lines.take()[2:].strip()
    if title_line != model.meta["title"]:
        model.warnings.append(f"Line {title_n}: the title line says {title_line!r} and the "
                              f"front matter {model.meta['title']!r}; the front matter wins.")
    _read_body(lines, model)
    _expand_repeats(model)
    _settle_rows(model)
    problems = validate(model)
    if problems:
        raise StateError(problems[0])
    return model


def _read_front(front: dict[str, str], where: dict[str, int], kind: str) -> dict[str, Any]:
    def need(key: str) -> str:
        if not front.get(key):
            raise StateError(f"the front matter has no `{key}:`. Add `{key}:` and "
                             + {"title": "the thing's name.",
                                "thing": "page, deck or document.",
                                "for": "who it is for, in a phrase.",
                                "writes": "how much the person means to write, in their words."}[key],
                             where.get(key, 2))
        return front[key]

    title, thing = need("title"), need("thing")
    if thing not in THINGS:
        raise StateError(f"`thing: {thing}` is not a kind of thing. Write page, deck or "
                         f"document.", where["thing"])
    meta: dict[str, Any] = {"title": title, "thing": thing, "for": need("for"),
                            "writes": need("writes"), "next": front.get("next") or None}
    shape = front.get("shape") or default_shape(thing)
    if shape not in SHAPES:
        raise StateError(f"`shape: {shape}` is not a frame shape. Write page, slide or "
                         f"letter.", where["shape"])
    unit = front.get("unit") or default_unit(thing)
    if unit not in UNITS:
        raise StateError(f"`unit: {unit}` is not a unit. Write c (characters) or w (words).",
                         where["unit"])
    aim = front.get("aim") or "thing"
    if aim not in AIMS:
        raise StateError(f"`aim: {aim}` is not an aim. Write thing, map, diagram or system.",
                         where["aim"])
    meta.update(shape=shape, unit=unit, lang=front.get("lang") or "en", aim=aim)
    if kind == "scaffold":
        version = front.get("version") or "1"
        if not version.isdigit() or int(version) < 1:
            raise StateError(f"`version: {version}` is not a version. Write a whole number "
                             f"from 1.", where.get("version", 2))
        meta["version"] = int(version)
        meta["parent"] = _int_or_text(front.get("parent", ""))
        for key in ("locked", "checked"):
            value = front.get(key) or None
            if value is not None and not _match(_STAMP_RE, value):
                raise StateError(f"`{key}: {value}` is not a UTC time. Write it as "
                                 f"YYYY-MM-DDTHH:MM:SSZ, or leave it empty.", where[key])
            meta[key] = value
    else:
        meta.update(version=None, parent=None, locked=None, checked=None)
        for key in STATE_FRONT_KEYS:
            if key in front:
                raise StateError(f"`{key}:` belongs to a scaffold's state, not to a plectrum. "
                                 f"Drop it, or make the second line `scaffold: 1`.", where[key])
    known = set(FRONT_KEYS) | set(STATE_FRONT_KEYS)
    meta["extra"] = {k: v for k, v in front.items() if k not in known}
    return meta


def _new_frame(name: str, n: int) -> dict[str, Any]:
    return {"id": None, "name": name, "shape": None, "copy_of": None, "copy": None,
            "extra": {}, "boxes": [], "_repeat": None, "_line": n}


def _new_box(box_id: str | None, name: str, n: int) -> dict[str, Any]:
    return {"id": box_id, "name": name, "as": "body", "kind": "text", "target": None,
            "shape": None, "row": None, "col": None, "place": None, "fixed": None,
            "chips": [], "plec_by": "readvisor", "state": None, "href": None, "plec": "",
            "text": "", "extra": {}, "_line": n}


def _fence_info(line: str) -> str | None:
    return line[3:].strip() if line.startswith("```") else None


def _read_body(lines: _Lines, model: Scaffold) -> None:
    unit = model.meta["unit"]
    frame: dict[str, Any] | None = None
    findings = False
    while lines.more():
        n, line = lines.n, lines.peek()
        if line.startswith("# "):
            lines.take()
            if model.kind == "scaffold" and line.rstrip() == "# Findings" and not findings:
                if frame is None:
                    raise StateError("`# Findings` comes before any frame. Findings follow the "
                                     "last frame.", n)
                findings = True
                frame = None
                continue
            raise StateError(f"a second `#` line, `{line[:60]}`. A plectrum has one title line"
                             f"{'' if model.kind == 'plectrum' else ' and a state one more, # Findings'}"
                             f"; make it a `## ` frame or drop it.", n)
        if findings:
            lines.take()
            info = _fence_info(line)
            if info == "finding":
                model.findings.append(_read_finding(lines, n))
            elif line.startswith("##"):
                raise StateError("a heading after `# Findings`. Frames come before the findings; "
                                 "move it up.", n)
            elif info is not None:
                raise StateError(f"a `{info}` block among the findings. Only `finding` blocks go "
                                 f"there.", n)
            continue
        if line.startswith("####"):
            raise StateError(f"`{line[:40]}` is a heading the grammar does not have. Use `## ` for "
                             f"a frame and `### ` for a box; anything else is prose.", n)
        if line.startswith("## "):
            lines.take()
            if frame is not None and not frame["boxes"]:
                raise StateError(f"the frame `{frame['name']}` holds no plec. Give it one, or "
                                 f"drop the frame.", frame["_line"])
            frame = _new_frame(line[3:].strip(), n)
            if not frame["name"]:
                raise StateError("a `## ` line with no name. Name the frame.", n)
            model.frames.append(frame)
            lines.skip_blank()
            if lines.more() and _fence_info(lines.peek()) is not None:
                fn, info = lines.n, _fence_info(lines.take())
                if info != "frame":
                    raise StateError(f"a `{info or '(no info string)'}` block at the top of a frame. "
                                     f"Only a `frame` block goes there.", fn)
                _apply_frame_block(frame, *_keyvals(lines, "frame block", fn, fence=True), fn)
            continue
        if line.startswith("### "):
            lines.take()
            if frame is None:
                raise StateError("a box (`### `) before any frame. Put a `## ` frame line above it.", n)
            frame["boxes"].append(_read_block_box(lines, model, line[4:].strip(), n, unit))
            continue
        info = _fence_info(line)
        if info is not None:
            lines.take()
            if info in ("plec", "frame", "finding"):
                where = {"plec": "`### ` box heading", "frame": "`## ` frame heading",
                         "finding": "`# Findings` line"}[info]
                raise StateError(f"a `{info}` block with no {where} above it. Put it under one, "
                                 f"or drop it.", n)
            while lines.more() and lines.take() != "```":  # prose in a fence: not kept
                pass
            continue
        lines.take()
        if line.startswith("- ") and frame is not None:
            frame["boxes"].append(_read_line_box(line, n, unit))
        # anything else is prose: read past, never kept
    if frame is not None and not frame["boxes"]:
        raise StateError(f"the frame `{frame['name']}` holds no plec. Give it one, or drop the "
                         f"frame.", frame["_line"])
    if not model.frames:
        raise StateError("the file has no frame. Add a `## ` line for each band, slide or "
                         "section, each with its plecs.")


def _apply_frame_block(frame: dict[str, Any], vals: dict[str, str], where: dict[str, int],
                       start: int) -> None:
    if "id" in vals:
        frame["id"] = vals["id"]
    if vals.get("shape"):
        if vals["shape"] not in SHAPES:
            raise StateError(f"`shape: {vals['shape']}` is not a frame shape. Write page, slide "
                             f"or letter.", where["shape"])
        frame["shape"] = vals["shape"]
    if "repeat" in vals:
        r = vals["repeat"]
        if not r.isdigit() or not 2 <= int(r) <= 999:
            raise StateError(f"`repeat: {r}` is not a count. Write a whole number from 2 to 999.",
                             where["repeat"])
        frame["_repeat"] = int(r)
    if "copy-of" in vals:
        frame["copy_of"] = vals["copy-of"] or None
    if "copy" in vals:
        c = vals["copy"]
        if c and not c.isdigit():
            raise StateError(f"`copy: {c}` is not a copy's number. Write a whole number.",
                             where["copy"])
        frame["copy"] = int(c) if c else None
    frame["extra"] = {k: v for k, v in vals.items() if k not in FRAME_KEYS}


def _read_block_box(lines: _Lines, model: Scaffold, heading: str, n: int,
                    unit: str) -> dict[str, Any]:
    for sep in (" · ", " | "):
        if sep in heading:
            box_id, name = heading.split(sep, 1)
            box_id, name = box_id.strip(), name.strip()
            break
    else:
        box_id, name = None, heading
    box = _new_box(box_id, name, n)
    lines.skip_blank()
    if not lines.more() or _fence_info(lines.peek()) != "plec":
        raise StateError(f"the box `{heading[:60]}` has no plec block. Put a ```plec block under "
                         f"its heading, with at least `plec:`.", n)
    fn = lines.n
    lines.take()
    vals, where = _keyvals(lines, "plec block", fn, fence=True)
    if "plec" not in vals:
        raise StateError("the plec block has no `plec:` line. Add `plec:` and what this box must "
                         "get across.", fn)
    _apply_box_vals(box, vals, where, unit, model.kind)
    if model.kind == "scaffold":
        box["text"] = _read_text(lines)
    return box


def _read_text(lines: _Lines) -> str:
    """The person's text: from the plec block's fence to the next `# `,
    `## ` or `### ` line, blank lines at both ends dropped, one escape
    backslash taken off."""
    body: list[str] = []
    while lines.more():
        line = lines.peek()
        if line.startswith(("# ", "## ", "### ")):
            break
        lines.take()
        body.append(line[1:] if _match(_TEXT_UNESCAPE_RE, line) else line)
    while body and not body[0].strip():
        body.pop(0)
    while body and not body[-1].strip():
        body.pop()
    return "\n".join(body)


def _apply_box_vals(box: dict[str, Any], vals: dict[str, str], where: dict[str, int],
                    unit: str, kind: str) -> None:
    def at(key: str) -> int:
        return where.get(key, box["_line"])

    if vals.get("as"):
        box["as"] = vals["as"]
    if vals.get("kind"):
        if vals["kind"] not in KINDS:
            raise StateError(f"`kind: {vals['kind']}` is not a box kind. Write text or graphic.",
                             at("kind"))
        box["kind"] = vals["kind"]
    if "target" in vals and vals["target"] != "":
        t = _target(vals["target"], unit)
        if t is None:
            raise StateError(f"`target: {vals['target']}` is not a target. Write a whole number "
                             f"and its unit, like 140c or 300w, or 0 for none.", at("target"))
        box["target"] = t
    if vals.get("shape"):
        box["shape"] = vals["shape"]
    for key in ("row", "col"):
        if vals.get(key):
            if not vals[key].isdigit() or int(vals[key]) < 1:
                raise StateError(f"`{key}: {vals[key]}` is not a place. Write a whole number "
                                 f"from 1.", at(key))
            box[key] = int(vals[key])
    if vals.get("place"):
        if not _place_ok(vals["place"]):
            raise StateError(f"`place: {vals['place']}` is not a place. Write four numbers from "
                             f"0 to 100: left top width height.", at("place"))
        box["place"] = vals["place"]
    for key in ("fixed", "href"):
        if vals.get(key):
            box[key] = vals[key]
    if vals.get("chips"):
        box["chips"] = [c.strip() for c in vals["chips"].split(",") if c.strip()]
    if vals.get("plec-by"):
        if vals["plec-by"] not in PLEC_BY:
            raise StateError(f"`plec-by: {vals['plec-by']}` is not who set the plec. Write "
                             f"readvisor or person.", at("plec-by"))
        box["plec_by"] = vals["plec-by"]
    if vals.get("state"):
        state = vals["state"]
        if state in ("empty", "over"):
            state = None  # worked out from the text, never stored
        elif state != "written":
            raise StateError(f"`state: {state}` is not a box's state. Write written, or leave it "
                             f"out.", at("state"))
        box["state"] = state
    box["plec"] = vals.get("plec", "")
    box["extra"] = {k: v for k, v in vals.items() if k not in BOX_KEYS}


def _read_line_box(line: str, n: int, unit: str) -> dict[str, Any]:
    m = _match(_LINE_PLEC_RE, line.rstrip())
    if not m:
        raise StateError(f"`{line[:60]}` reads as a plec but is not one. Write "
                         f"`- Name [140c]: what it must get across`.", n)
    name, bracket, plec = m.group(1).strip(), m.group(2).split(), m.group(3).strip()
    box = _new_box(None, name, n)
    box["plec"] = plec
    if not bracket:
        raise StateError(f"the plec `{name}` has an empty bracket. Put a target (140c), "
                         f"`graphic` and a shape, or what the box is.", n)
    first, rest = bracket[0].lower(), bracket[1:]
    if _target(first, unit) is not None:
        box["target"] = _target(first, unit)
        if rest:
            raise StateError(f"the bracket of `{name}` holds more than a target. Write "
                             f"`[140c]`, `[graphic 4:3]` or `[headline 60c]`.", n)
    elif first == "graphic":
        box["kind"] = "graphic"
        if len(rest) > 1:
            raise StateError(f"the bracket of `{name}` holds more than a graphic's shape. "
                             f"Write `[graphic 4:3]`.", n)
        if rest:
            box["shape"] = rest[0]
    else:
        box["as"] = first
        if len(rest) > 1 or (rest and _target(rest[0], unit) is None):
            raise StateError(f"the bracket of `{name}` says what the box is but no target "
                             f"after it. Write `[{first} 80c]` or `[{first}]`.", n)
        if rest:
            box["target"] = _target(rest[0], unit)
    return box


def _read_finding(lines: _Lines, start: int) -> dict[str, Any]:
    vals, where = _keyvals(lines, "finding block", start, fence=True)
    f: dict[str, Any] = {k.replace("-", "_"): None for k in FINDING_KEYS}
    f["extra"] = {}
    for key, value in vals.items():
        if key in _ESCAPED:
            f[key] = _unescape(value)
        elif key == "version":
            if value and not value.isdigit():
                raise StateError(f"`version: {value}` is not a version. Write a whole number.",
                                 where[key])
            f[key] = int(value) if value else None
        elif key in FINDING_KEYS:
            f[key] = value
        else:
            f["extra"][key] = value
    for key in ("id", "box", "kind", "status"):
        if not f[key]:
            raise StateError(f"the finding has no `{key}:`. Add it.", start)
    if f["quote"] is None:
        f["quote"] = ""
    f["_line"] = start
    return f


def _expand_repeats(model: Scaffold) -> None:
    """`repeat: N` makes N copies; `{n}` numbers names and plecs; ids get
    `-NN`, padded to the width of N."""
    out: list[dict[str, Any]] = []
    for frame in model.frames:
        if frame["id"] is None:
            frame["id"] = slug(frame["name"])
            if not frame["id"]:
                raise StateError(f"the frame `{frame['name']}` makes an empty id. Give it one in a "
                                 f"```frame block (`id: …`).", frame["_line"])
        for box in frame["boxes"]:
            if box["id"] is None:
                box["id"] = slug(box["name"])
                if not box["id"]:
                    raise StateError(f"the box `{box['name']}` makes an empty id. Give it one: "
                                     f"`### id · {box['name']}`.", box["_line"])
        count = frame.pop("_repeat")
        if not count:
            out.append(frame)
            continue
        width = len(str(count))
        for k in range(1, count + 1):
            suffix = f"-{k:0{width}d}"
            twin = copy.deepcopy(frame)
            twin.update(id=frame["id"] + suffix, name=frame["name"].replace("{n}", str(k)),
                        copy_of=frame["id"], copy=k)
            for box in twin["boxes"]:
                box["id"] += suffix
                box["name"] = box["name"].replace("{n}", str(k))
                box["plec"] = box["plec"].replace("{n}", str(k))
            out.append(twin)
    model.frames = out


def _settle_rows(model: Scaffold) -> None:
    """Defaults spelled out: a text box's target, a graphic's shape, and
    rows and columns (a box with no row takes the row after the last one
    used; a column is the box's place in its row, in file order)."""
    for frame in model.frames:
        used = 0
        per_row: dict[int, int] = {}
        for box in frame["boxes"]:
            if box["kind"] == "text" and box["target"] is None:
                box["target"] = "0"
            if box["kind"] == "graphic" and box["shape"] is None:
                box["shape"] = "16:9"
            if box["row"] is None:
                box["row"] = used + 1
            used = max(used, box["row"])
            per_row[box["row"]] = per_row.get(box["row"], 0) + 1
            if box["col"] is None:
                box["col"] = per_row[box["row"]]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _where(item: dict[str, Any], what: str) -> str:
    line = item.get("_line")
    return f"Line {line}: " if line else f"{what} `{item.get('id')}`: "


def validate(model: Scaffold) -> list[str]:
    """Every problem in a model, each a sentence that names the fix. A
    model read by `loads` or `from_json` is checked here too."""
    out: list[str] = []
    meta = model.meta
    for key in ("title", "thing", "for", "writes"):
        if not meta.get(key):
            out.append(f"the front matter has no `{key}:`. Add it.")
    if meta.get("thing") and meta["thing"] not in THINGS:
        out.append(f"`thing: {meta['thing']}` is not a kind of thing. Write page, deck or document.")
    if model.kind not in ("plectrum", "scaffold"):
        out.append(f"a model is a plectrum or a scaffold, not {model.kind!r}.")
    if not model.frames:
        out.append("the file has no frame. Add a `## ` line for each band, slide or section.")
    seen: set[str] = set()
    for frame in model.frames:
        fw = _where(frame, "frame")
        out += _id_problems(frame["id"], fw, seen)
        if not frame["boxes"]:
            out.append(f"{fw}the frame `{frame['name']}` holds no plec. Give it one, or drop it.")
        if frame.get("shape") and frame["shape"] not in SHAPES:
            out.append(f"{fw}`shape: {frame['shape']}` is not a frame shape. Write page, slide or letter.")
        for box in frame["boxes"]:
            bw = _where(box, "box")
            out += _id_problems(box["id"], bw, seen)
            if box["kind"] not in KINDS:
                out.append(f"{bw}`kind: {box['kind']}` is not a box kind. Write text or graphic.")
            if model.kind == "plectrum" and not box["plec"].strip():
                out.append(f"{bw}the plec of `{box['name']}` is empty. Say what this box must get across.")
            if len(box["plec"]) > MAX_PLEC:
                out.append(f"{bw}the plec of `{box['name']}` runs past {MAX_PLEC:,} characters. "
                           f"Say it in one line.")
            if box["kind"] == "graphic" and box["shape"] and not _graphic_shape_ok(box["shape"]):
                out.append(f"{bw}`shape: {box['shape']}` is not a picture's shape. Write a "
                           f"proportion like 16:9, or portrait, landscape or square.")
            if box["target"] is not None and _target(box["target"], "c") != box["target"]:
                out.append(f"{bw}`target: {box['target']}` is not a target. Write 140c, 300w, or 0.")
            if model.kind == "plectrum" and (box["text"] or box["state"] or box["href"]):
                out.append(f"{bw}a plectrum's box holds no text, state or picture. Those belong "
                           f"to the scaffold's state.")
    boxes = {b["id"] for b in model.boxes()}
    fids: set[str] = set()
    for f in model.findings:
        fw = _where(f, "finding")
        if f["id"] in fids:
            out.append(f"{fw}the finding id `{f['id']}` is used twice. Number findings f1, f2, … "
                       f"and never reuse one.")
        fids.add(f["id"])
        if f["box"] not in boxes:
            out.append(f"{fw}the finding `{f['id']}` is about box `{f['box']}`, which is not in "
                       f"the file. Name a box that is.")
        if f["kind"] not in FINDING_KINDS:
            out.append(f"{fw}`kind: {f['kind']}` is not a finding's kind. Write spelling, "
                       f"grammar or truth.")
        if f["status"] not in FINDING_STATUSES:
            out.append(f"{fw}`status: {f['status']}` is not an outcome. Write open, accepted, "
                       f"declined or cannot be checked.")
    if model.findings and model.kind != "scaffold":
        out.append("a plectrum holds no findings. They belong to the scaffold's state.")
    return out


def _id_problems(item_id: Any, where: str, seen: set[str]) -> list[str]:
    if not isinstance(item_id, str) or not _match(_ID_RE, item_id) or len(item_id) > MAX_ID:
        return [f"{where}`{item_id}` is not an id. An id is 1 to 40 of a-z, 0-9 and `-`, "
                f"starting with a letter or a digit; shorten or respell it."]
    if item_id in seen:
        return [f"{where}the id `{item_id}` is used twice. Frames and boxes share one set of "
                f"ids; give one of them another."]
    seen.add(item_id)
    return []


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def dumps(model: Scaffold, kind: str | None = None) -> str:
    """The writer's form. `kind` "plectrum" writes the plectrum back out of
    a state (`state.md`, "The plectrum, back out of a state")."""
    kind = kind or model.kind
    if kind not in ("plectrum", "scaffold"):
        raise StateError(f"a file is a plectrum or a scaffold, not {kind!r}.")
    problems = validate(model if kind == model.kind else _for_kind(model, kind))
    if problems:
        raise StateError(problems[0])
    meta = model.meta
    out = ["---", f"{kind}: {GRAMMAR}"]
    for key in FRONT_KEYS + (STATE_FRONT_KEYS if kind == "scaffold" else ()):
        value = meta.get(key)
        if key == "version" and value is None:
            value = 1
        out.append(f"{key}: {_plain(value)}".rstrip() if _plain(value) else f"{key}:")
    for key, value in meta.get("extra", {}).items():
        out.append(f"{key}: {value}" if value else f"{key}:")
    out += ["---", "", f"# {meta['title']}", ""]
    groups = _fold(model.frames) if kind == "plectrum" else [(f, None) for f in model.frames]
    for frame, repeat in groups:
        out += [f"## {frame['name']}", "", "```frame", f"id: {frame['id']}"]
        if frame.get("shape"):
            out.append(f"shape: {frame['shape']}")
        if repeat:
            out.append(f"repeat: {repeat}")
        if frame.get("copy_of") and not repeat:
            out.append(f"copy-of: {frame['copy_of']}")
        if frame.get("copy") is not None and not repeat:
            out.append(f"copy: {frame['copy']}")
        out += [f"{k}: {v}" if v else f"{k}:" for k, v in frame.get("extra", {}).items()]
        out += ["```", ""]
        for box in frame["boxes"]:
            out += _box_lines(box, kind)
    if kind == "scaffold" and model.findings:
        out += ["# Findings", ""]
        for f in model.findings:
            out.append("```finding")
            for key in FINDING_KEYS:
                value = f.get(key.replace("-", "_"))
                if value is None and key not in ("id", "box", "kind", "quote", "status", "version"):
                    continue
                value = _escape(value) if key in _ESCAPED and value is not None else _plain(value)
                out.append(f"{key}: {value}" if value else f"{key}:")
            out += [f"{k}: {v}" if v else f"{k}:" for k, v in f.get("extra", {}).items()]
            out += ["```", ""]
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


def _box_lines(box: dict[str, Any], kind: str) -> list[str]:
    out = [f"### {box['id']} · {box['name']}", "", "```plec"]
    values = {
        "as": box["as"], "kind": box["kind"],
        "target": box["target"] if box["kind"] == "text" or box["target"] is not None else None,
        "shape": box["shape"],
        "row": box["row"], "col": box["col"], "place": box["place"], "fixed": box["fixed"],
        "chips": ", ".join(box["chips"]) if box["chips"] else None,
        "plec-by": box["plec_by"] or "readvisor",
        "state": box["state"] if kind == "scaffold" else None,
        "href": box["href"] if kind == "scaffold" else None,
        "plec": box["plec"],
    }
    for key in BOX_KEYS:
        value = values[key]
        if value is None:
            continue
        out.append(f"{key}: {value}" if _plain(value) else f"{key}:")
    out += [f"{k}: {v}" if v else f"{k}:" for k, v in box.get("extra", {}).items()]
    out += ["```", ""]
    if kind == "scaffold" and box["text"]:
        out += ["\\" + ln if _match(_TEXT_ESCAPE_RE, ln) else ln for ln in box["text"].split("\n")]
        out.append("")
    return out


def _for_kind(model: Scaffold, kind: str) -> Scaffold:
    return as_plectrum(model) if kind == "plectrum" else model


def as_plectrum(model: Scaffold) -> Scaffold:
    """The plectrum back out of a state: no version, lock or check, no
    text, state or picture, no findings. Layout stays, as hints."""
    out = copy.deepcopy(model)
    out.kind = "plectrum"
    out.meta.update(version=None, parent=None, locked=None, checked=None)
    for box in out.boxes():
        box.update(text="", state=None, href=None)
    out.findings = []
    out.warnings = []
    return out


_FOLD_SAME = ("as", "kind", "target", "shape", "row", "col", "place", "fixed", "chips",
              "plec_by", "extra")


def _fold(frames: list[dict[str, Any]]) -> list[tuple[dict[str, Any], int | None]]:
    """Copies with the same `copy-of`, numbered 1..N in a run, folded back
    into one frame with `repeat: N`. A run whose copies differ by more than
    their number is written out copy by copy, with its `copy-of` kept."""
    out: list[tuple[dict[str, Any], int | None]] = []
    i = 0
    while i < len(frames):
        f = frames[i]
        if not f.get("copy_of"):
            out.append((f, None))
            i += 1
            continue
        j = i
        while j < len(frames) and frames[j].get("copy_of") == f["copy_of"]:
            j += 1
        run = frames[i:j]
        folded = _fold_run(run)
        out += [(folded, len(run))] if folded else [(x, None) for x in run]
        i = j
    return out


def _fold_run(run: list[dict[str, Any]]) -> dict[str, Any] | None:
    count = len(run)
    width = len(str(count))
    nums = [f.get("copy") for f in run]
    if count < 2 or nums != list(range(1, count + 1)):
        return None
    base = run[0]["copy_of"]
    if any(f["id"] != f"{base}-{k:0{width}d}" for k, f in zip(nums, run)):
        return None
    if any(f.get("shape") != run[0].get("shape") or f.get("extra") != run[0].get("extra")
           for f in run):
        return None
    name = _pattern([f["name"] for f in run], nums)
    if name is None or len({len(f["boxes"]) for f in run}) != 1:
        return None
    boxes = []
    for parts in zip(*(f["boxes"] for f in run)):
        first = parts[0]
        suffix = f"-{1:0{width}d}"
        if not first["id"].endswith(suffix):
            return None
        box_base = first["id"][: -len(suffix)]
        if any(b["id"] != f"{box_base}-{k:0{width}d}" for k, b in zip(nums, parts)):
            return None
        if any(b[key] != first[key] for b in parts for key in _FOLD_SAME):
            return None
        bname = _pattern([b["name"] for b in parts], nums)
        plec = _pattern([b["plec"] for b in parts], nums)
        if bname is None or plec is None:
            return None
        boxes.append({**first, "id": box_base, "name": bname, "plec": plec, "text": "",
                      "state": None, "href": None})
    return {**run[0], "id": base, "name": name, "copy_of": None, "copy": None, "boxes": boxes}


def _pattern(values: list[str], nums: list[int]) -> str | None:
    """The `{n}` pattern every copy's string comes from, or None."""
    first = values[0]
    if "{n}" in first:
        return None
    spans = [m.span() for m in re.finditer(rf"(?<!\d){nums[0]}(?!\d)", first)]
    for chosen in [spans] + [[s] for s in spans] + [[]]:
        pattern, last = [], 0
        for a, b in chosen:
            pattern += [first[last:a], "{n}"]
            last = b
        pattern.append(first[last:])
        p = "".join(pattern)
        if all(p.replace("{n}", str(k)) == v for k, v in zip(nums, values)):
            return p
    return None


# ---------------------------------------------------------------------------
# JSON, counts
# ---------------------------------------------------------------------------

def _clean(item: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in item.items() if not k.startswith("_")}


def to_dict(model: Scaffold) -> dict[str, Any]:
    return {
        model.kind: GRAMMAR,
        "meta": dict(model.meta),
        "frames": [{**_clean(f), "boxes": [_clean(b) for b in f["boxes"]]}
                   for f in model.frames],
        "findings": [_clean(f) for f in model.findings],
    }


def to_json(model: Scaffold, indent: int | None = 2) -> str:
    return json.dumps(to_dict(model), ensure_ascii=False, indent=indent)


def from_dict(data: dict[str, Any]) -> Scaffold:
    kind = "scaffold" if "scaffold" in data else "plectrum" if "plectrum" in data else ""
    if not kind or data.get(kind) != GRAMMAR:
        raise StateError(f"the JSON names no grammar this reader knows. Give it "
                         f"`\"scaffold\": {GRAMMAR}` or `\"plectrum\": {GRAMMAR}`.")
    model = Scaffold(kind=kind)
    meta = {k: None for k in FRONT_KEYS + STATE_FRONT_KEYS}
    meta.update(data.get("meta") or {})
    meta.setdefault("extra", {})
    meta["extra"] = dict(meta.get("extra") or {})
    model.meta = meta
    for raw in data.get("frames") or []:
        frame = {**_new_frame(raw.get("name", ""), 0), **raw}
        frame.pop("_repeat", None)
        frame.pop("_line", None)
        frame["boxes"] = []
        for b in raw.get("boxes") or []:
            box = {**_new_box(None, "", 0), **b}
            box.pop("_line", None)
            box["chips"] = list(box.get("chips") or [])
            box["extra"] = dict(box.get("extra") or {})
            frame["boxes"].append(box)
        model.frames.append(frame)
    for raw in data.get("findings") or []:
        f = {k.replace("-", "_"): None for k in FINDING_KEYS}
        f["extra"] = {}
        f.update(raw)
        f["extra"] = dict(f.get("extra") or {})
        if f["quote"] is None:
            f["quote"] = ""
        model.findings.append(f)
    _settle_rows(model)
    problems = validate(model)
    if problems:
        raise StateError(problems[0])
    return model


def from_json(text: str) -> Scaffold:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise StateError(f"the JSON does not read ({e.msg}, line {e.lineno}). Mend it.") from None
    if not isinstance(data, dict):
        raise StateError("the JSON is not an object. Give the shape `state.md` gives.")
    return from_dict(data)


def count(model: Scaffold) -> dict[str, Any]:
    """Frames plus boxes after repeats, notes box included; the targets'
    sum per unit, notes boxes left out."""
    targets: dict[str, int] = {}
    for box in model.boxes():
        t = box["target"]
        if box["kind"] == "text" and t and t != "0" and box["as"] != "notes":
            targets[t[-1]] = targets.get(t[-1], 0) + int(t[:-1])
    frames, boxes = len(model.frames), len(model.boxes())
    return {"frames": frames, "boxes": boxes, "parts": frames + boxes, "targets": targets}


def count_line(model: Scaffold) -> str:
    c = count(model)
    line = (f"This is {c['frames']} frame{'s' if c['frames'] != 1 else ''} and {c['boxes']} "
            f"box{'es' if c['boxes'] != 1 else ''}, {c['parts']} parts in all.")
    words = {"c": "characters", "w": "words"}
    sums = [f"{n:,} {words[u]}" for u, n in sorted(c["targets"].items())]
    if sums:
        line += f" About {' and '.join(sums)} in all."
    return line


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    usage = "usage: scaffold_state.py check|json|write|plectrum FILE"
    if argv in (["-h"], ["--help"]):
        print(usage)
        print(__doc__)
        return 0
    if len(argv) != 2 or argv[0] not in ("check", "json", "write", "plectrum"):
        print(usage, file=sys.stderr)
        return 2
    command, path = argv
    try:
        with open(path, encoding="utf-8") as fh:
            model = loads(fh.read())
    except OSError as e:
        print(f"cannot read {path}: {e.strerror}", file=sys.stderr)
        return 1
    except StateError as e:
        print(str(e), file=sys.stderr)
        return 1
    for warning in model.warnings:
        print(warning, file=sys.stderr)
    if command == "check":
        print(count_line(model))
    elif command == "json":
        print(to_json(model))
    elif command == "write":
        sys.stdout.write(dumps(model))
    else:
        sys.stdout.write(dumps(model, "plectrum"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
