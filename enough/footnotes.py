"""Footnote surgery on markdown source (docs/paginate-plan.md §2.1).

Footnotes in enough are plain markdown: `[^1]` refs in the prose and a block
of `[^1]: text` definitions at the END of the file. That block is the user's
own file — pandoc reads it, another editor reads it, the twin round-trips
through it — so it has to come back out byte for byte apart from the labels
we deliberately move. Hence regex surgery over the source and never a full
markdown parse: everything this module does not recognise is text it must
not touch.

Four rules do most of the work, and each one exists because the alternative
loses something the writer wrote:

- **Code is not prose.** A `[^1]` inside a fenced block or an inline code
  span is an *example* of a footnote. Renumbering it would rewrite the
  documentation of the syntax while somebody was reading it.
- **Only digits are managed.** `[^intro-note]` is recognised (`parse`
  reports it with `numeric: False`) and then left exactly where it is: a
  named label is how a writer pins a footnote that must not move.
- **An orphan definition is left alone.** A `[^7]: …` with no `[^7]` in the
  prose is a note in progress or a mistake; either way it is not ours to
  renumber, so it keeps its bytes and stays out of the mapping.
- **A ref inside a definition body is not a ref.** Renumbering goes by order
  of appearance and the definitions live at the end of the file, so honouring
  those refs would sort the tail of the document first.

`tests/test_footnotes.py` is the reference spec for this module *and* for the
JS mirror in index.html (`fnParse` / `fnRenumber` / `fnNextNumber` /
`fnInsertAt`). That is why the rules above are stated as flat conditions on
lines and offsets rather than as a grammar: both implementations have to
agree byte for byte, and only simple rules survive being written twice.

Offsets index the string handed in. A ref's `start`/`end` bracket its
`[^label]` token; a definition's bracket the whole entry — the `[^label]:`
line plus its continuation lines — up to but not including the newline that
ends it, so `text[start:end]` is a definition and `text[end - len(body):end]`
is its body.

No I/O, no imports beyond the standard library: wave B's worker, the server
and the test suite all call straight in.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# A label carries no whitespace and no `]`. That is also what keeps `[^]` out
# of both patterns — the sentinel the edit face types before it expands has
# an empty label, so a half-typed footnote is never mistaken for a real one.
REF_RE = re.compile(r"\[\^([^\]\s]+)\]")

# A definition is a line that *starts* with its label, indented by at most
# three spaces (four would make it an indented code block, and four is also
# the continuation indent, so the limit is load-bearing in both directions).
# The match covers the lead only: `m.end()` is where the body starts.
DEF_RE = re.compile(r"^ {0,3}\[\^([^\]\s]+)\]:[ \t]*", re.MULTILINE)

# `str.isdigit()` says yes to '²' and to Arabic-Indic digits, and `int()`
# would then renumber a label into something the user cannot type back.
_NUM_RE = re.compile(r"[0-9]+")

_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_BACKTICKS_RE = re.compile(r"`+")
_BLANK_LINE_RE = re.compile(r"\n[ \t]*\n")


def _is_numeric(label: str) -> bool:
    return _NUM_RE.fullmatch(label) is not None


# ---------------------------------------------------------------------------
# Code regions — the one thing that is never a footnote
# ---------------------------------------------------------------------------

def _fence_ranges(text: str) -> list[tuple[int, int]]:
    """Half-open spans of every fenced code block, fence lines included.

    An unclosed fence runs to the end of the document: that is what a
    renderer does with it, and a footnote inside a block somebody is still
    typing is still an example.
    """
    ranges: list[tuple[int, int]] = []
    opened: int | None = None
    marker = ""
    pos = 0
    for line in text.splitlines(keepends=True):
        m = _FENCE_RE.match(line.rstrip("\r\n"))
        if opened is None:
            # A backtick fence's info string may not contain a backtick
            # (CommonMark); a tilde fence has no such restriction.
            if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
                opened, marker = pos, m.group(1)
        elif (m and m.group(1)[0] == marker[0]
              and len(m.group(1)) >= len(marker) and not m.group(2).strip()):
            ranges.append((opened, pos + len(line)))
            opened = None
        pos += len(line)
    if opened is not None:
        ranges.append((opened, len(text)))
    return ranges


def _span_ranges(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Inline code spans within `text[start:end]`, as absolute offsets.

    CommonMark's rule: a run of N backticks opens and the next run of exactly
    N closes. A span cannot cross a blank line — the paragraph ends there —
    and that bound is what stops one stray backtick from swallowing the rest
    of the file.
    """
    out: list[tuple[int, int]] = []
    at = start
    while True:
        opener = _BACKTICKS_RE.search(text, at, end)
        if opener is None:
            return out
        blank = _BLANK_LINE_RE.search(text, opener.end(), end)
        limit = blank.start() if blank else end
        closer = None
        probe = opener.end()
        while True:
            cand = _BACKTICKS_RE.search(text, probe, limit)
            if cand is None:
                break
            if len(cand.group(0)) == len(opener.group(0)):
                closer = cand
                break
            probe = cand.end()
        if closer is None:
            at = opener.end()          # an unmatched run is just backticks
            continue
        out.append((opener.start(), closer.end()))
        at = closer.end()


def _mask_code(text: str) -> str:
    """`text` with every code region blanked to NULs, newlines preserved.

    Masking rather than filtering, because offsets have to survive: a match
    found in the mask indexes straight back into the original, and the
    `^`-anchored definition pattern still sees the same lines it would have
    seen in the source.
    """
    if "`" not in text and "~" not in text:
        return text
    fences = _fence_ranges(text)
    spans: list[tuple[int, int]] = list(fences)
    cursor = 0
    for fence_start, fence_end in fences:
        spans.extend(_span_ranges(text, cursor, fence_start))
        cursor = fence_end
    spans.extend(_span_ranges(text, cursor, len(text)))
    chars = list(text)
    for s, e in spans:
        for i in range(s, e):
            if chars[i] != "\n":
                chars[i] = "\x00"
    return "".join(chars)


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def _line_end(text: str, pos: int) -> int:
    nl = text.find("\n", pos)
    return len(text) if nl < 0 else nl


def _is_continuation(line: str) -> bool:
    """A definition body continues onto lines indented four spaces or a tab.

    A blank line ends the definition — and therefore ends the terminal block
    — which is also what keeps `definitions_span` from swallowing whatever
    indented thing happens to follow the notes.
    """
    return (line.startswith("\t") or line.startswith("    ")) and bool(line.strip())


def _definition_end(text: str, body_start: int) -> int:
    end = _line_end(text, body_start)
    while end < len(text):
        nxt = _line_end(text, end + 1)
        if not _is_continuation(text[end + 1:nxt]):
            break
        end = nxt
    return end


def parse(text: str) -> dict[str, list[dict[str, Any]]]:
    """Every footnote ref and definition in `text`, each in document order.

        {"refs": [{"label": "1", "numeric": True, "start": int, "end": int}],
         "defs": [{"label": "1", "numeric": True, "start": int, "end": int,
                   "body": str}]}

    `body` is a raw slice ending at `end`, so continuation lines keep their
    indentation and `end - len(body)` is where the body begins — which is the
    span a margin card writes back into.

    Refs and defs found inside code are not reported at all, and neither is
    the `[^1]` that opens a definition or any ref sitting inside a definition
    body (see the module docstring for why).
    """
    masked = _mask_code(text)
    defs: list[dict[str, Any]] = []
    for m in DEF_RE.finditer(masked):
        end = _definition_end(text, m.end())
        label = m.group(1)
        defs.append({"label": label, "numeric": _is_numeric(label),
                     "start": m.start(), "end": end,
                     "body": text[m.end():end]})
    refs: list[dict[str, Any]] = []
    for m in REF_RE.finditer(masked):
        if any(d["start"] <= m.start() < d["end"] for d in defs):
            continue
        label = m.group(1)
        refs.append({"label": label, "numeric": _is_numeric(label),
                     "start": m.start(), "end": m.end()})
    return {"refs": refs, "defs": defs}


def definitions_span(text: str) -> tuple[int, int] | None:
    """The terminal definitions block as `(start, end)`, or None.

    The block is the last run of *consecutive* definitions — one entry's last
    line and the next entry's first line with no blank line between them —
    and it only counts as terminal when nothing but whitespace follows it.
    A document whose definitions sit in the middle with prose after them has
    no terminal block, and `insert_at` starts one at the end rather than file
    a new note under a heading it cannot see.
    """
    defs = parse(text)["defs"]
    if not defs:
        return None
    if text[defs[-1]["end"]:].strip():
        return None
    first = len(defs) - 1
    while first > 0 and text[defs[first - 1]["end"]:defs[first]["start"]] == "\n":
        first -= 1
    return defs[first]["start"], defs[-1]["end"]


def next_number(text: str, offset: int) -> int:
    """The number a footnote inserted at `offset` should carry: one more than
    the managed refs before it. In a renumbered document that is exactly the
    number a reader expects to see next."""
    refs = parse(text)["refs"]
    return 1 + sum(1 for r in refs if r["numeric"] and r["start"] < offset)


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def _apply_edits(text: str, edits: list[tuple[int, int, str]]) -> str:
    """Apply non-overlapping `(start, end, replacement)` edits in one pass.

    Sorted by `(start, end)`, so a zero-length insertion lands *before* a
    replacement starting at the same offset — which is what puts a new ref in
    front of the ref it displaces.
    """
    if not edits:
        return text
    out: list[str] = []
    at = 0
    for start, end, repl in sorted(edits, key=lambda ed: (ed[0], ed[1])):
        out.append(text[at:start])
        out.append(repl)
        at = end
    out.append(text[at:])
    return "".join(out)


def _relabel_edits(text: str, doc: dict[str, list[dict[str, Any]]],
                   mapping: dict[str, str]) -> list[tuple[int, int, str]]:
    """Edits rewriting every `[^label]` token — ref or definition lead — whose
    label the mapping moves. A label that maps to itself produces no edit, so
    an already-ordered document comes back byte-identical."""
    edits: list[tuple[int, int, str]] = []
    for ref in doc["refs"]:
        new = mapping.get(ref["label"]) if ref["numeric"] else None
        if new is not None and new != ref["label"]:
            edits.append((ref["start"], ref["end"], f"[^{new}]"))
    for entry in doc["defs"]:
        new = mapping.get(entry["label"]) if entry["numeric"] else None
        if new is None or new == entry["label"]:
            continue
        # The lead may be indented; the token itself starts at the bracket.
        start = text.index("[", entry["start"])
        edits.append((start, start + len(entry["label"]) + 3, f"[^{new}]"))
    return edits


def _block_items(text: str, doc: dict[str, list[dict[str, Any]]],
                 span: tuple[int, int]) -> list[dict[str, Any]]:
    start, end = span
    return [d for d in doc["defs"] if start <= d["start"] < end]


def _ref_rank(doc: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    """Managed labels in order of first appearance — the order the
    definitions block is supposed to read in."""
    rank: dict[str, int] = {}
    for ref in doc["refs"]:
        if ref["numeric"] and ref["label"] not in rank:
            rank[ref["label"]] = len(rank)
    return rank


def _reorder_definitions(text: str, managed: set[str]) -> str:
    """Permute the managed definitions inside the terminal block into label
    order, leaving every other line of the block where it was.

    The managed entries move only among themselves: a named definition or an
    orphan keeps its slot, so a writer who parked `[^intro]` at the top of
    the block still finds it there.
    """
    span = definitions_span(text)
    if span is None:
        return text
    items = _block_items(text, parse(text), span)
    slots = [i for i, d in enumerate(items)
             if d["numeric"] and d["label"] in managed]
    if len(slots) < 2:
        return text
    chunks = [text[d["start"]:d["end"]] for d in items]
    ordered = sorted((items[i] for i in slots), key=lambda d: int(d["label"]))
    for slot, entry in zip(slots, ordered):
        chunks[slot] = text[entry["start"]:entry["end"]]
    start, end = span
    return text[:start] + "\n".join(chunks) + text[end:]


def renumber(text: str) -> tuple[str, dict[str, str]]:
    """Renumber the managed footnotes 1..N in order of first appearance.

    Numeric refs take the new numbers, their definitions are relabelled to
    match and reordered inside the terminal block so it reads in ref order.
    Named labels, orphan definitions and every byte that is not a label come
    through untouched. Returns `(new_text, {old: new})` including the labels
    that happened not to move — the map is the managed set, not a diff.

    A label used twice is one footnote, not two: it takes its number at first
    appearance and keeps it everywhere, which is also the only reading a
    `{old: new}` dict can express.
    """
    doc = parse(text)
    mapping: dict[str, str] = {}
    for ref in doc["refs"]:
        if ref["numeric"] and ref["label"] not in mapping:
            mapping[ref["label"]] = str(len(mapping) + 1)
    if not mapping:
        return text, {}
    out = _apply_edits(text, _relabel_edits(text, doc, mapping))
    return _reorder_definitions(out, set(mapping.values())), mapping


def _def_line(label: str, body: str) -> str:
    """`[^label]: body`, with any further lines indented to the continuation
    depth so the entry stays a single definition. Blank lines inside a body
    are dropped for the same reason: one would end the definition, and
    silently splitting a note in half is worse than closing the gap."""
    lines = [ln for ln in (body or "").split("\n")]
    head = f"[^{label}]:" + (f" {lines[0].strip()}" if lines[0].strip() else "")
    rest = [f"    {ln.strip()}" for ln in lines[1:] if ln.strip()]
    return "\n".join([head] + rest)


def _place_definition(text: str, label: str, body: str) -> str:
    """File `[^label]: body` into the terminal definitions block in ref order,
    starting the block one blank line below the prose when there isn't one."""
    line = _def_line(label, body)
    span = definitions_span(text)
    if span is None:
        prose = text.rstrip()
        return f"{prose}\n\n{line}\n" if prose else f"{line}\n"
    doc = parse(text)
    items = _block_items(text, doc, span)
    rank = _ref_rank(doc)
    mine = rank.get(label, len(rank))
    # Before the first managed entry that belongs after us; failing that, at
    # the end of the block.
    at = len(items)
    for i, entry in enumerate(items):
        if entry["numeric"] and rank.get(entry["label"], -1) > mine:
            at = i
            break
    chunks = [text[d["start"]:d["end"]] for d in items]
    chunks.insert(at, line)
    start, end = span
    return text[:start] + "\n".join(chunks) + text[end:]


def insert_at(text: str, offset: int, body: str = "") -> tuple[str, int]:
    """Insert a footnote at `offset`; return `(new_text, number)`.

    The new ref takes `next_number(text, offset)`; every managed ref from that
    number up that sits at or after the insertion point shifts by one, each
    definition follows its label, and `[^k]: body` is filed into the terminal
    definitions block in ref order.

    Only refs at or after the insertion point move: a document whose numbers
    already run out of order is the job of `renumber`, not something to
    quietly rewrite around a caret.
    """
    offset = max(0, min(len(text), offset))
    doc = parse(text)
    k = 1 + sum(1 for r in doc["refs"] if r["numeric"] and r["start"] < offset)
    moving = {r["label"] for r in doc["refs"]
              if r["numeric"] and r["start"] >= offset and int(r["label"]) >= k}
    edits = _relabel_edits(text, doc, {lab: str(int(lab) + 1) for lab in moving})
    edits.append((offset, offset, f"[^{k}]"))
    return _place_definition(_apply_edits(text, edits), str(k), body), k
