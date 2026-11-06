"""The dialectic: the core's one primitive for asking a person what a source means and recording what they say
(MacroCOSM OES 18.6, 10, 8.5, 13; Thym 22; Ascribe 8; Comprise OES 8; docs/fabula-pins.md P4).

Module D, which every format inherits from the core, holds two kinds: `D:question/<slug>` (one question about one
place in a volume) and `D:session/<slug>` (one sitting in which a person was asked). The dialectic is two whole runs
with a person between them, and this module is their deterministic core, with no model, no network and no server:

- **reading**: the questions and sessions a volume carries, what a question is `about` resolved to its item and field
  (or span, module or kind), and the volume's open questions (open D questions, and bare `{pending: "…"}` values no
  question is about yet);
- **raising** (the Thym move `question`, its rules part, the scaffold `bank`): from the manifest's banks, from every
  `{pending}` value and from every item below confidence 0.5 or pending; never a duplicate; a hook merges questions a
  model proposed, validated, address-checked and de-duplicated;
- **recording** (the move `record`, code): answers appended, never rewritten; the state moved (`answered`, `unknown`,
  `declined`; a skip leaves it `open`); the session written; each value parsed and checked against the question's
  `kind`; the **answers volume** of Thym 22.2 read and written;
- **settling** (the move `settle`, its rules part, the scaffold `direct`): every answered, unknown or declined question
  folded into what it is about, exactly as 18.6.4's tables say; a write that would add a check error is not made and a
  `why: counter` question is raised instead; answers that need an item read again are handed to a hook (the model is
  the Thym lane's) or listed; `only_the_asked` verifies the contract of the same name;
- **staleness and carrying over**: `stale`, `withdraw`, `reask`, and `carry_over(old, new)` after a decompile done
  again.

A single-file volume (a fabula, a Canon volume, a document) is opened as a `Twin`: its text, its data and a `Ledger`
over the items in its `nodes:`. Every write goes back **in place**: the new text is the old text with only the regions
that changed re-emitted (an item's changed keys, an appended list entry, an appended item), checked by parsing the
result and comparing it with the intended data, so everything the operation did not change stays byte for byte. A
folder volume (Ascribe's holograph, Comprise's Holotype) keeps its D items where its own specification says; this
module never writes one: build a `Ledger` from the loaded volume or from a list of items handed in, call the same
functions, and write the items back in your layout.

    python -m enough.dialectic list <volume> [--json]
    python -m enough.dialectic raise <volume> [--rules] [--to WORD] [--author-unavailable] [--run ID]
    python -m enough.dialectic answer <volume> [--from ANSWERS] [--into] [--who TEXT] [--to WORD]
    python -m enough.dialectic settle <volume> [--answers ANSWERS] [--run ID] [--program NAME]

Standalone like the reader: the standard library, PyYAML (through the reader), `enough.macrocosm` and `enough.fabula`.
The contract (every public function, what it reads, writes and refuses) is docs/fabula-landed-D1.md.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
import re
import sys
import threading
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Iterable

from . import fabula as fb
from . import macrocosm as mc

# ---------------------------------------------------------------------------
# The words (MacroCOSM OES 18.6.2)
# ---------------------------------------------------------------------------

MODULE = mc.DIALECTIC_MODULE                 # D
QUESTION = "question"
SESSION = "session"
Q_PREFIX = f"{MODULE}:{QUESTION}/"
S_PREFIX = f"{MODULE}:{SESSION}/"

WHYS = ("missing", "unsure", "ambiguous", "intent", "conflict", "counter")
ANSWER_KINDS = ("text", "choice", "yes-no", "number", "date", "ref", "span")
STATES = ("open", "answered", "unknown", "declined", "stale", "withdrawn")
THROUGH = ("person", "agent")
RAISED_BY = ("bank", "move", "model", "person")
TO_WORDS = ("author", "expert", "maker", "holder", "owner", "anyone")
ANSWERED = ("answered", "unknown", "declined")      # the states an answer moves a question into
ENDED = ("stale", "withdrawn")
UNSURE_BELOW = 0.5                                   # an item below this confidence is unsure (18.6.3)
ITEM_KINDS_ONLY = ("text", "choice")                 # the kinds an answer about a module or a kind may have (18.6.4)
ENTRY_COPIED = ("kind", "options", "options-open", "many", "range", "hint")
QUESTION_ORDER = ("id", "type", "about", "asks", "why", "kind", "options", "options-open", "many", "range", "hint",
                  "to", "raised", "state", "answers", "settled", "ended")
NOT_DISCLOSED = "not-disclosed"
WHOLE_ITEM = mc.WHOLE_ITEM                           # the field path of a pending on the whole item: `node`

# "I don't know", recognised as Comprise's core/elicit.py DONT_KNOW does, without its `skip` (a skip is its own act
# here: the question stays open and the session lists it as skipped).
DONT_KNOW = re.compile(
    r"^\s*(?:(?:i\s+)?(?:don'?t|do\s+not|dont)\s+know|not\s+sure|no\s+idea|unknown|unsure|pending|"
    r"(?:honestly,?\s+)?(?:i\s*)?(?:'d|would|will|need|have)\s+(?:need\s+)?to\s+(?:check|ask|look|find out)|"
    r"(?:i\s+)?can(?:'t|not)\s+say|ask\s+(?:the|our|someone))\b", re.I)
# A refusal to say, recognised in the person's words (an explicit flag always works).
DECLINE = re.compile(
    r"^\s*(?:i'?d\s+rather\s+not|i\s+would\s+rather\s+not|rather\s+not|(?:i\s+)?decline|"
    r"(?:i\s+)?prefer\s+not\s+to\s+(?:say|answer)|no\s+comment|not\s+telling|i\s+won'?t\s+say)\b", re.I)
_YES = re.compile(r"^\s*(?:yes|y|yeah|yep|true|it\s+is|i\s+did|i\s+do|correct)\b", re.I)
_NO = re.compile(r"^\s*(?:no|n|nope|false|it\s+is\s+not|i\s+did\s+not|i\s+didn'?t|not\s+at\s+all)\b", re.I)
_DATE_RE = re.compile(r"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$")
_INT_RE = re.compile(r"^[+-]?\d+$")
_NUM_RE = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$")
_LINES_RE = re.compile(r"^\s*([0-9]+)(?:\s*-\s*([0-9]+))?\s*$")
_PLACEHOLDER = re.compile(r"\{([A-Za-z0-9_][A-Za-z0-9_.\[\]-]*)\}")
_BARE_SESSION = re.compile(r"^(?:session-[0-9]+|elicit-\S+)$")
_ANSWERS_NAME = re.compile(r"^(?P<stem>.+)\.answers-\d{4}-\d{2}-\d{2}-\d{4}(?:-\d+)?\.cosm$")
SPAN_TEXT_MAX = 60


class DialecticError(Exception):
    """A plain "no": what was asked of the dialectic cannot be done, and nothing was written. `str()` says why."""


class AnswerRefused(DialecticError):
    """An answer whose value does not fit its question's kind; the question is left as it was."""

    def __init__(self, message: str, question: str | None = None):
        super().__init__(message)
        self.question = question


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def now(at: Any = None) -> dt.datetime:
    """A timestamp as the dialectic writes it: timezone-aware UTC, whole seconds. Takes a datetime (naive is read
    as UTC), an ISO string (`2026-11-05T10:20:40Z`) or None (the present moment)."""
    if at is None:
        return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    if isinstance(at, str):
        s = at.strip()
        at = dt.datetime.fromisoformat(s[:-1] + "+00:00" if s.endswith(("Z", "z")) else s)
    if isinstance(at, dt.datetime):
        if at.tzinfo is None:
            at = at.replace(tzinfo=dt.timezone.utc)
        return at.astimezone(dt.timezone.utc).replace(microsecond=0)
    if isinstance(at, dt.date):
        return dt.datetime(at.year, at.month, at.day, tzinfo=dt.timezone.utc)
    raise DialecticError(f"{at!r} is not a time")


def _same(a: Any, b: Any) -> bool:
    """Strict equality of loaded values: a bool is never a number, a string never a date; mapping order ignored."""
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, dict):
        return isinstance(b, dict) and a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return isinstance(b, list) and len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if isinstance(a, dt.datetime) or isinstance(b, dt.datetime):
        if not (isinstance(a, dt.datetime) and isinstance(b, dt.datetime)):
            return False
        if (a.tzinfo is None) != (b.tzinfo is None):
            return False
        return a == b
    if isinstance(a, dt.date) or isinstance(b, dt.date):
        return type(a) is type(b) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    return type(a) is type(b) and a == b


def _slug(text: Any, n: int = 48) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    if len(s) > n:
        s = s[:n].rstrip("-")
    return s or "q"


def _bare(ref: str) -> str:
    """`atom/x//N:aim/y` -> `N:aim/y`."""
    return ref.split("//", 1)[-1]


def _qid(ref: str) -> str:
    """A question's id from its id or its bare slug."""
    return ref if ref.startswith(Q_PREFIX) else Q_PREFIX + ref


def _sid(ref: str) -> str:
    """A session's id from its id, its slug, or an older bare spelling (`session-1`, `elicit-…`)."""
    return ref if ref.startswith(S_PREFIX) else S_PREFIX + ref


def _about_key(about: Any) -> str:
    return json.dumps(about, sort_keys=True, default=str) if isinstance(about, (dict, list)) else str(about)


def _module_of(item_id: str) -> str | None:
    head = _bare(item_id).split(":", 1)
    return head[0] if len(head) == 2 else None


def is_question(d: Any) -> bool:
    return isinstance(d, dict) and isinstance(d.get("id"), str) and _bare(d["id"]).startswith(Q_PREFIX)


def is_session(d: Any) -> bool:
    return isinstance(d, dict) and isinstance(d.get("id"), str) and _bare(d["id"]).startswith(S_PREFIX)


def is_d_item(d: Any) -> bool:
    return isinstance(d, dict) and isinstance(d.get("id"), str) and _module_of(d["id"]) == MODULE


# Field paths (MacroCOSM OES 6.6): keys joined by ".", list positions [n] from zero.
def _steps(fpath: str) -> list:
    out: list = []
    for mt in mc._FIELD_STEP.finditer(fpath):
        out.append(mt.group(1) if mt.group(1) is not None else int(mt.group(2)))
    return out


def get_field(data: Any, fpath: str) -> tuple[bool, Any]:
    """(found, value) at a field path of an item's data (the reader's `field_value`)."""
    return mc.field_value(data, fpath)


def set_field(data: dict, fpath: str, value: Any) -> None:
    """Write `value` at a field path, making the mappings on the way; a list position must exist. Raises
    DialecticError for a path that crosses a value that is not a mapping or a list."""
    steps = _steps(fpath)
    if not steps:
        raise DialecticError(f"{fpath!r} is not a field path")
    cur: Any = data
    for i, st in enumerate(steps):
        last = i == len(steps) - 1
        if isinstance(st, int):
            if not isinstance(cur, list) or st >= len(cur):
                raise DialecticError(f"{fpath}: there is no position [{st}] to write into")
            if last:
                cur[st] = value
                return
            cur = cur[st]
            continue
        if not isinstance(cur, dict):
            raise DialecticError(f"{fpath}: {st} is under a value that is not a mapping")
        if last:
            cur[st] = value
            return
        nxt = cur.get(st)
        if nxt is None or mc.is_pending(nxt):
            nxt = {} if not isinstance(steps[i + 1], int) else None
            if nxt is None:
                raise DialecticError(f"{fpath}: there is no list at {st} to write into")
            cur[st] = nxt
        cur = nxt


def del_field(data: dict, fpath: str) -> bool:
    """Remove the value at a field path; True when something was removed. A mapping left empty on the way stays."""
    steps = _steps(fpath)
    cur: Any = data
    for st in steps[:-1]:
        if isinstance(st, int):
            if not isinstance(cur, list) or st >= len(cur):
                return False
            cur = cur[st]
        else:
            if not isinstance(cur, dict) or st not in cur:
                return False
            cur = cur[st]
    st = steps[-1] if steps else None
    if isinstance(st, str) and isinstance(cur, dict) and st in cur:
        del cur[st]
        return True
    if isinstance(st, int) and isinstance(cur, list) and st < len(cur):
        del cur[st]
        return True
    return False


# ---------------------------------------------------------------------------
# The ledger: a volume's items, as the dialectic reads and changes them
# ---------------------------------------------------------------------------

@dataclass
class Ledger:
    """What the dialectic works on: a format's manifest, the catalog mapping, and every item's data in order. For a
    single-file volume (a `Twin`) `items` IS the catalog's `nodes:` list, so a change shows in the document. For a
    folder volume it is a copy of the items a caller handed in: the caller writes them back in its own layout.
    `origin` is parallel to `items` where it is known: (part id or None, file) for each item."""
    manifest: mc.Manifest
    catalog: dict
    items: list
    registry: mc.Registry | None = None
    filename: str = "volume.cosm"
    minicosm: str | None = None
    major: int | None = None
    origin: list = field(default_factory=list)

    # --------------------------------------------------------------- lookups
    @property
    def flavour(self) -> str | None:
        """The catalog's flavour as the manifest reads it (`fabulan` for an `emf/1` twin); None without flavours."""
        if not self.manifest.flavours:
            return None
        v = self.manifest.flavour_of(self.catalog)
        return v if isinstance(v, str) else None

    @property
    def is_fabula(self) -> bool:
        return self.minicosm == fb.FORMAT

    def index(self, ref: str) -> int | None:
        """The position of the item a reference names: its id, its bare id, or a qualified id `part//id`."""
        if not isinstance(ref, str):
            return None
        part, _, bare = ref.rpartition("//") if "//" in ref else ("", "", ref)
        hits = []
        for i, d in enumerate(self.items):
            if not isinstance(d, dict) or not isinstance(d.get("id"), str):
                continue
            if d["id"] == ref:
                return i
            if _bare(d["id"]) == bare:
                if part and self.part_of(i) not in (None, part):
                    continue
                hits.append(i)
        return hits[0] if len(hits) == 1 else None

    def item(self, ref: str) -> dict | None:
        i = self.index(ref)
        return self.items[i] if i is not None else None

    def part_of(self, i: int) -> str | None:
        return self.origin[i][0] if i < len(self.origin) else None

    def file_of(self, i: int) -> str:
        return self.origin[i][1] if i < len(self.origin) else self.filename

    def ids(self) -> set[str]:
        return {d["id"] for d in self.items if isinstance(d, dict) and isinstance(d.get("id"), str)}

    def questions(self) -> list[dict]:
        return [d for d in self.items if is_question(d)]

    def sessions(self) -> list[dict]:
        return [d for d in self.items if is_session(d)]

    def question(self, ref: str) -> dict | None:
        d = self.item(_qid(ref))
        return d if is_question(d) else None

    def session(self, ref: str) -> dict | None:
        d = self.item(_sid(ref))
        return d if is_session(d) else None

    def kind_of(self, d: dict) -> tuple[str | None, str | None]:
        """(module, kind) of an item's data, as the reader reads them."""
        g = self.manifest.grammar
        p = g.parse(d.get("id"))
        mod = (p.module if p else None) or g.default_module
        t = d.get("type")
        return mod, (t if isinstance(t, str) else ((p.form or p.kind) if p else None))

    def add(self, data: dict, part: str | None = None, file: str | None = None) -> None:
        if self.origin or part is not None or file is not None:
            while len(self.origin) < len(self.items):
                self.origin.append((None, self.filename))
            self.origin.append((part, file or self.filename))
        self.items.append(data)

    # --------------------------------------------------------------- the reader's view
    def volume(self) -> mc.Volume:
        """The ledger as a volume the reader's checks run on (built in memory: nothing is read or written)."""
        m = self.manifest
        vol = mc.Volume(Path(self.filename), minicosm=self.minicosm, major=self.major, manifest=m,
                        catalog=self.catalog, root=Path("."), catalog_file=self.filename, files=[self.filename])
        for i, d in enumerate(self.items):
            if not isinstance(d, dict) or not isinstance(d.get("id"), str):
                continue
            mod, kind = self.kind_of(d)
            it = mc.Item(d["id"], mod, kind, self.part_of(i), self.file_of(i), d)
            if it.key in vol.items:
                vol.problems.append(mc.Problem("duplicate-id", "error", it.key, it.file,
                                               f"duplicate id {d['id']} (first in {vol.items[it.key].file}); the "
                                               "first is kept"))
                continue
            vol.items[it.key] = it
        return vol

    def copy(self) -> "Ledger":
        return Ledger(self.manifest, copy.deepcopy(self.catalog), copy.deepcopy(self.items), self.registry,
                      self.filename, self.minicosm, self.major, list(self.origin))


def ledger_from_volume(volume: mc.Volume) -> Ledger:
    """A ledger over a loaded volume (any format, single-file or folder): its items' data, deep-copied, with each
    item's part and file kept. Writing them back is the caller's (a folder volume's layout is its own)."""
    if volume.manifest is None:
        raise DialecticError(f"the volume was refused: {volume.refused}")
    items = [copy.deepcopy(it.data) for it in volume.items.values()]
    origin = [(it.part, it.file) for it in volume.items.values()]
    cat = copy.deepcopy(volume.catalog)
    if volume.manifest.single_file:
        key = _items_key(volume.manifest)
        cat[key] = items
    return Ledger(volume.manifest, cat, items, None, volume.catalog_file or "volume.cosm", volume.minicosm,
                  volume.major, origin)


def ledger_from_items(manifest: mc.Manifest, items: Iterable[dict], *, catalog: dict | None = None,
                      origin: list | None = None, filename: str = "volume.cosm") -> Ledger:
    """A ledger over items handed in (a MiniCOSM's lane that keeps its D items in its own place): `manifest` the
    format's, `items` every item's data (D items and the items they are about), `catalog` the catalog mapping (for the
    checks and the flavour), `origin` [(part, file)] parallel to `items` where the format has parts."""
    cat = dict(catalog or {})
    return Ledger(manifest, cat, [copy.deepcopy(d) for d in items], None, filename, manifest.name,
                  manifest.version, list(origin or []))


def _items_key(m: mc.Manifest) -> str:
    for key, _kind, one in m.item_sources(None):
        if not one:
            return key
    return "nodes"


def ledger_of(src: Any, registry: mc.Registry | None = None) -> Ledger:
    """A ledger from what a caller has: a Ledger, a Twin, a loaded Volume, or a path (a single-file volume opens as a
    Twin; a folder volume loads read-only)."""
    if isinstance(src, Ledger):
        return src
    if isinstance(src, Twin):
        return src.ledger
    if isinstance(src, mc.Volume):
        return ledger_from_volume(src)
    if isinstance(src, (str, Path)):
        p = Path(src)
        if p.is_file():
            try:
                return open_twin(p, registry).ledger
            except DialecticError:
                pass
        return ledger_from_volume(mc.load_volume(p, registry))
    raise DialecticError(f"not a volume: {src!r}")


# ---------------------------------------------------------------------------
# A question's address (18.6.2 `about`; 9.3)
# ---------------------------------------------------------------------------

@dataclass
class Where:
    """What a question's `about` names. `form` is `item`, `field`, `span`, `module` or `kind`; `index` the item's
    position in the ledger (item and field); `field` the field path; `present` whether the field holds a value and
    `value` that value (a pending counts as present, and `pending` says so); `why` is set when it names nothing."""
    about: Any
    form: str
    index: int | None = None
    item_id: str | None = None
    field: str | None = None
    module: str | None = None
    kind: str | None = None
    span: dict | None = None
    present: bool = False
    value: Any = None
    pending: bool = False
    why: str | None = None

    @property
    def resolves(self) -> bool:
        return self.why is None

    @property
    def address(self) -> str:
        if self.form == "field":
            return f"{self.item_id}#{self.field}"
        if self.form == "item":
            return str(self.item_id)
        return _about_key(self.about)


def _span_shape_why(span: Any) -> str | None:
    if not isinstance(span, dict):
        return "a span is {lines}, {start, end}, or {file, lines} in code"
    keys = set(span)
    if keys == {"lines"} or keys == {"file", "lines"}:
        if keys == {"file", "lines"} and not (isinstance(span["file"], str) and span["file"].strip()):
            return "a code span names its file"
        lines = span["lines"]
        if fb._lines(lines) is None:
            return f"lines {lines!r} must be n or n-m, n no greater than m"
        return None
    if keys == {"start", "end"}:
        ok = all(isinstance(span[k], str) and 0 < len(span[k].strip()) <= SPAN_TEXT_MAX for k in ("start", "end"))
        return None if ok else f"a span {{start, end}} is two runs of the source's words, {SPAN_TEXT_MAX} characters " \
                               "at most"
    return "a span is {lines}, {start, end}, or {file, lines} in code"


def resolve_about(src: Any, about: Any) -> Where:
    """What `about` names in a volume: an item, an item's field (absent, pending or present), a span of the source, a
    module or a kind the format declares. Never raises; a `Where` with `why` set names nothing."""
    led = ledger_of(src)
    m = led.manifest
    if isinstance(about, dict) and not mc.is_pending(about):
        why = _span_shape_why(about)
        return Where(about, "span", span=about, why=why)
    if not isinstance(about, str) or not about.strip():
        return Where(about, "item", why="about names an item, an item's field, a span, or a module or a kind")
    if about in m.modules():
        return Where(about, "module", module=about)
    mt = re.fullmatch(r"([A-Z][A-Za-z0-9]*):([a-z][a-z0-9-]*)", about)
    if mt:
        ok = mt.group(1) in m.modules() and mt.group(2) in m.kinds(mt.group(1))
        return Where(about, "kind", module=mt.group(1), kind=mt.group(2),
                     why=None if ok else f"{about} is not a kind this format declares")
    base, sep, fpath = about.partition("#")
    i = led.index(base)
    if i is None:
        return Where(about, "field" if sep else "item", item_id=base, field=fpath or None,
                     why=f"{base} names nothing in this volume")
    d = led.items[i]
    mod, kind = led.kind_of(d)
    if not sep:
        return Where(about, "item", index=i, item_id=d["id"], module=mod, kind=kind, present=True, value=d,
                     pending=isinstance(d.get("pending"), str))
    if not m.grammar.seg["field"].fullmatch(fpath):
        return Where(about, "field", index=i, item_id=d["id"], field=fpath, module=mod, kind=kind,
                     why=f"{fpath!r} is not a field path (keys joined by \".\", list positions as [n])")
    found, v = get_field(d, fpath)
    return Where(about, "field", index=i, item_id=d["id"], field=fpath, module=mod, kind=kind, present=found,
                 value=v if found else None, pending=found and mc.is_pending(v))


# ---------------------------------------------------------------------------
# Reading (A)
# ---------------------------------------------------------------------------

def questions(src: Any, *, state: str | Iterable[str] | None = None) -> list[dict]:
    """The volume's `D:question` items, in volume order; with `state`, only those in that state (or states)."""
    led = ledger_of(src)
    states = (state,) if isinstance(state, str) else (tuple(state) if state is not None else None)
    return [q for q in led.questions() if states is None or q.get("state") in states]


def sessions(src: Any) -> list[dict]:
    """The volume's `D:session` items, in volume order."""
    return ledger_of(src).sessions()


def open_questions(src: Any) -> list[dict]:
    """Every open question of a volume, both lengths of 18.6.5: each `D:question` in state `open`, and each bare
    `{pending: "…"}` value (or `pending:` on a whole item) that no question still standing (not stale or withdrawn)
    is about. Each entry: {form: question|pending, id (a question's) or None, about, asks, why, kind, to, item,
    field}. D items' own fields are never read as pendings."""
    led = ledger_of(src)
    out: list[dict] = []
    covered = {_about_key(q.get("about")) for q in led.questions() if q.get("state") not in ENDED}
    for d in led.items:
        if is_question(d) and d.get("state") == "open":
            w = resolve_about(led, d.get("about"))
            out.append({"form": "question", "id": d["id"], "about": d.get("about"), "asks": d.get("asks"),
                        "why": d.get("why"), "kind": d.get("kind"), "to": d.get("to"),
                        "item": w.item_id, "field": w.field})
    for d in led.items:
        if not isinstance(d, dict) or not isinstance(d.get("id"), str) or is_d_item(d):
            continue
        for fpath, q in mc.walk_pending(d):
            about = d["id"] if fpath == WHOLE_ITEM else f"{d['id']}#{fpath}"
            if about in covered:
                continue
            out.append({"form": "pending", "id": None, "about": about, "asks": q, "why": "missing", "kind": "text",
                        "to": None, "item": d["id"], "field": None if fpath == WHOLE_ITEM else fpath})
    return out


# ---------------------------------------------------------------------------
# The single-file volume, opened for writing, and written back in place
# ---------------------------------------------------------------------------

@dataclass
class Twin:
    """A single-file volume opened by the dialectic. `text` is the file as read (the base every write is spliced
    into), `original` its data as read, `doc` its data as it now stands (operations change it through `ledger`, whose
    `items` is `doc`'s items list). `render()` is the new text; `save()` writes it to `path` and nowhere else."""
    path: Path | None
    text: str
    original: dict
    doc: dict
    ledger: Ledger
    bom: bool = False
    how: str = ""                    # how the last render wrote: `unchanged`, `in place`, or `by top-level keys`

    @property
    def changed(self) -> bool:
        return not _same(self.original, self.doc)

    def render(self) -> str:
        """The volume's new text: the text as read, with only what changed re-emitted (see `write_back`)."""
        text, how = write_back(self.text, self.original, self.doc)
        self.how = how
        return ("﻿" + text) if self.bom and not text.startswith("﻿") else text

    def save(self, path: Path | str | None = None) -> Path:
        """Write the new text to the volume's own file (atomically: a dotfile beside it, then a rename). Refuses any
        other path, and a twin read from text with no path. Returns the path."""
        if self.path is None:
            raise DialecticError("this volume was read from text, with no file to write back to")
        if path is not None and Path(path).resolve() != self.path.resolve():
            raise DialecticError(f"the dialectic writes only the volume it was given ({self.path.name}), not {path}")
        text = self.render()
        if self.changed:
            write_atomic(self.path, text)
        return self.path

    def lint(self) -> mc.Report:
        return fb.lint(self.ledger.volume())


def write_atomic(path: Path, text: str) -> None:
    """Write through a dotfile beside the file and `os.replace`, so no reader sees half a volume."""
    path = Path(path)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


def twin_from_text(text: str, *, filename: str = "volume.cosm", registry: mc.Registry | None = None,
                   path: Path | None = None) -> Twin:
    """Open a single-file volume from its text. Refuses (DialecticError) text that does not parse, holds anchors,
    aliases or tags, declares nothing this reader reads, or declares a folder format."""
    bom = text.startswith("﻿")
    body = text[1:] if bom else text
    data, forbidden, error = mc._parse(body)
    if error or forbidden:
        raise DialecticError(f"{filename}: " + (error or forbidden[0]))
    if not isinstance(data, dict):
        raise DialecticError(f"{filename}: top level must be a mapping")
    reg = registry if registry is not None else mc.default_registry()
    decl = reg.identify(data, filename=Path(filename).name)
    if isinstance(decl, mc.Refusal):
        raise DialecticError(f"{filename}: {decl.message}")
    m = decl.manifest
    if not m.single_file:
        raise DialecticError(f"{filename} is the catalog of a folder volume ({m.title}): the dialectic writes its D "
                             "items only through a ledger of items handed in (ledger_from_volume, ledger_from_items)")
    doc = copy.deepcopy(data)
    key = _items_key(m)
    if doc.get(key) is None:
        doc[key] = []
    if not isinstance(doc[key], list):
        raise DialecticError(f"{filename}: {key} must be a list")
    led = Ledger(m, doc, doc[key], reg, Path(filename).name, decl.minicosm, decl.major)
    return Twin(path, body, data, doc, led, bom)


def open_twin(path: Path | str, registry: mc.Registry | None = None) -> Twin:
    """Open a single-file volume's file (a fabula, an `emf/1` twin, a Canon volume, a document) for the dialectic."""
    p = Path(path)
    try:
        raw = p.read_bytes()
    except OSError as e:
        raise DialecticError(f"{p}: cannot read: {e}") from e
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        raise DialecticError(f"{p.name}: not UTF-8") from e
    return twin_from_text(text, filename=p.name, registry=registry, path=p.absolute())


# ----------------------------------------------------------------- emitting COSM text in the house style

_WIDTH = 110
_ALWAYS_FLOW = frozenset({"span", "raised", "settled", "ended", "with", "covers", "roles", "feed", "source", "whose"})
_PLAIN_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")


@lru_cache(maxsize=8192)
def _plain_ok(s: str, flow: bool) -> bool:
    if not s or s != s.strip() or any(c in s for c in "\n\r\t\x85  ") or s[0] in "'\"":
        return False
    try:
        if flow:
            return mc.yaml_load("k: [" + s + "]") == {"k": [s]} and mc.yaml_load("k: {a: " + s + "}") == {"k": {"a": s}}
        return mc.yaml_load("k: " + s) == {"k": s}
    except Exception:  # noqa: BLE001 - not plain, then
        return False


def _stamp(v: dt.datetime) -> str:
    if v.tzinfo is not None and v.utcoffset() == dt.timedelta(0):
        base = v.replace(tzinfo=None).isoformat()
        return base + "Z"
    return v.isoformat()


def _scalar(v: Any, flow: bool) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, dt.datetime):
        return _stamp(v)
    if isinstance(v, dt.date):
        return v.isoformat()
    s = str(v)
    if _plain_ok(s, flow):
        return s
    return json.dumps(s, ensure_ascii=False)


def _key(k: Any) -> str:
    if isinstance(k, str) and _PLAIN_KEY.match(k) and _plain_ok(k, False):
        return k
    if isinstance(k, (int, float)) and not isinstance(k, bool):
        return str(k)
    return json.dumps(str(k), ensure_ascii=False)


def _flow(v: Any) -> str:
    if isinstance(v, dict):
        return "{" + ", ".join(f"{_key(k)}: {_flow(x)}" for k, x in v.items()) + "}"
    if isinstance(v, list):
        return "[" + ", ".join(_flow(x) for x in v) + "]"
    return _scalar(v, True)


def _has_dict_list(v: Any) -> bool:
    if isinstance(v, dict):
        return any(_has_dict_list(x) for x in v.values())
    if isinstance(v, list):
        return any(isinstance(x, dict) or _has_dict_list(x) for x in v)
    return False


def _emit_kv(key: Any, value: Any, col: int) -> list[str]:
    """The lines (no line ends) of `key: value` at column `col`, in the house style of the spec's examples: small
    mappings and lists of scalars on one line, items and long mappings in block style."""
    pad, k = " " * col, _key(key)
    if isinstance(value, dict):
        if not value:
            return [f"{pad}{k}: {{}}"]
        line = f"{pad}{k}: {_flow(value)}"
        if not _has_dict_list(value) and (key in _ALWAYS_FLOW or len(line) <= _WIDTH):
            return [line]
        return [f"{pad}{k}:"] + _emit_map(value, col + 2)
    if isinstance(value, list):
        if not value:
            return [f"{pad}{k}: []"]
        if not any(isinstance(x, (dict, list)) for x in value):
            return [f"{pad}{k}: {_flow(value)}"]
        return [f"{pad}{k}:"] + _emit_list(value, col + 2, block=key == "nodes")
    return [f"{pad}{k}: {_scalar(value, False)}"]


def _emit_map(d: dict, col: int) -> list[str]:
    out: list[str] = []
    for k, v in d.items():
        out += _emit_kv(k, v, col)
    return out


def _emit_element(v: Any, col: int, *, block: bool) -> list[str]:
    pad = " " * col
    if isinstance(v, dict) and v and (block or _has_dict_list(v)):
        lines = _emit_map(v, col + 2)
        lines[0] = pad + "- " + lines[0][col + 2:]
        return lines
    if isinstance(v, (dict, list)):
        return [f"{pad}- {_flow(v)}"]
    return [f"{pad}- {_scalar(v, False)}"]


def _emit_list(lst: list, col: int, *, block: bool) -> list[str]:
    out: list[str] = []
    for v in lst:
        out += _emit_element(v, col, block=block)
    return out


def dump_text(doc: dict) -> str:
    """A whole document in the house style (used for a new file, such as an answers volume)."""
    return "".join(line + "\n" for line in _emit_map(doc, 0))


# ----------------------------------------------------------------- splicing changes into the text as read

class _NoSplice(Exception):
    pass


_KEY_AT = re.compile(r"""^(?:"(?:[^"\\]|\\.)*"|'(?:[^']|'')*'"""            # a quoted key
                     r"""|[^\s#'"\-?:,\[\]{}][^\s:#]*(?:[ \t]+[^\s:#]+)*)"""     # or a plain one
                     r"""[ \t]*:(?=[ \t]|$|\r|\n)""")


def _skip(line: str) -> bool:
    s = line.strip()
    return not s or s.startswith("#")


def _ind(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _is_dash(content: str) -> bool:
    return content.startswith("- ") or content.rstrip("\r\n") == "-"


def _parse_key(text: str) -> Any:
    try:
        d = mc.yaml_load(text + " 0")
    except Exception as e:  # noqa: BLE001
        raise _NoSplice from e
    if not isinstance(d, dict) or len(d) != 1:
        raise _NoSplice
    return next(iter(d))


def _map_keys(lines: list[str], s: int, e: int, col: int, dash: bool) -> list[tuple[Any, int]]:
    """[(key, line index)] of the block mapping in lines[s:e] whose keys sit at column `col` (the first on a `- `
    line when `dash`). Raises _NoSplice when the region is not that."""
    out: list[tuple[Any, int]] = []
    for i in range(s, e):
        line = lines[i]
        if dash and i == s:
            if line[:col - 2].strip() or line[col - 2:col] != "- ":
                raise _NoSplice
            content = line[col:]
        else:
            if _skip(line):
                continue
            ind = _ind(line)
            if ind < col:
                raise _NoSplice
            if ind > col:
                if not out:
                    raise _NoSplice
                continue
            content = line[col:]
            if _is_dash(content):                   # an indentless sequence under the previous key
                if not out:
                    raise _NoSplice
                continue
        mt = _KEY_AT.match(content)
        if not mt:
            raise _NoSplice
        out.append((_parse_key(mt.group(0)), i))
    return out


def _core_end(lines: list[str], start: int, end: int) -> int:
    """The end of a region without its trailing blank and comment lines (which stay where they are)."""
    k = end
    while k > start + 1 and _skip(lines[k - 1]):
        k -= 1
    return k


def _child_col(lines: list[str], s: int, e: int) -> int | None:
    for i in range(s, e):
        if not _skip(lines[i]):
            return _ind(lines[i])
    return None


def _nl(lines: list[str], nl: str) -> list[str]:
    return [x + nl for x in lines]


def _splice_map(lines, s, e, col, dash, old: dict, new: dict, nl: str, fine: bool) -> list[str]:
    keys = _map_keys(lines, s, e, col, dash)
    if not keys or [k for k, _ in keys] != list(old.keys()):
        raise _NoSplice
    out = list(lines[s:keys[0][1]])
    added = [k for k in new if k not in old]
    for idx, (k, i) in enumerate(keys):
        end = keys[idx + 1][1] if idx + 1 < len(keys) else e
        core = _core_end(lines, i, end)
        first = dash and idx == 0
        last = idx == len(keys) - 1
        if k not in new:
            if first:
                raise _NoSplice
            body: list[str] = []
        elif _same(old[k], new[k]):
            body = lines[i:core]
        else:
            body = _splice_value(lines, i, core, col, first, k, old[k], new[k], nl, fine)
        out += body
        if last:
            for ak in added:
                out += _nl(_emit_kv(ak, new[ak], col), nl)
        out += lines[core:end]
    return out


def _splice_value(lines, i, core, col, first, key, ov, nv, nl, fine) -> list[str]:
    line = lines[i]
    content = line[col:]
    mt = _KEY_AT.match(content)
    rest = content[mt.end():] if mt else ""
    block = not rest.strip() or rest.strip().startswith("#")
    if fine and block and ov and isinstance(ov, dict) and isinstance(nv, dict):
        cc = _child_col(lines, i + 1, core)
        if cc is not None and cc > col:
            try:
                return [line] + _splice_map(lines, i + 1, core, cc, False, ov, nv, nl, fine)
            except _NoSplice:
                pass
    if block and ov and isinstance(ov, list) and isinstance(nv, list) and (fine or key == "nodes"):
        try:
            return [line] + _splice_list(lines, i + 1, core, col, key, ov, nv, nl, fine)
        except _NoSplice:
            pass
    em = _emit_kv(key, nv, col)
    if first:
        em[0] = em[0][:col - 2] + "- " + em[0][col:]
    return _nl(em, nl)


def _splice_list(lines, s, e, keycol, key, ov: list, nv: list, nl: str, fine: bool) -> list[str]:
    dcol = _child_col(lines, s, e)
    if dcol is None or dcol < keycol or len(nv) < len(ov):
        raise _NoSplice
    starts = []
    for i in range(s, e):
        if _skip(lines[i]):
            continue
        ind = _ind(lines[i])
        if ind < dcol:
            raise _NoSplice
        if ind == dcol:
            if not _is_dash(lines[i][dcol:]):
                raise _NoSplice
            starts.append(i)
    if len(starts) != len(ov):
        raise _NoSplice
    block = key == "nodes"
    out = list(lines[s:starts[0]])
    for j, st in enumerate(starts):
        end = starts[j + 1] if j + 1 < len(starts) else e
        core = _core_end(lines, st, end)
        if _same(ov[j], nv[j]):
            body = lines[st:core]
        else:
            body = None
            o, n = ov[j], nv[j]
            if isinstance(o, dict) and isinstance(n, dict) and o and _KEY_AT.match(lines[st][dcol + 2:]):
                try:
                    body = _splice_map(lines, st, core, dcol + 2, True, o, n, nl, fine)
                except _NoSplice:
                    body = None
            if body is None:
                body = _nl(_emit_element(n, dcol, block=block), nl)
        out += body
        if j == len(starts) - 1:
            for extra in nv[len(ov):]:
                out += _nl(_emit_element(extra, dcol, block=block), nl)
        out += lines[core:end]
    return out


def write_back(text: str, old: dict, new: dict) -> tuple[str, str]:
    """`text` (whose data is `old`) with `new` written into it, and how: `unchanged` (the same text), `in place`
    (only the changed keys of the changed items, appended list entries and appended items are re-emitted; every other
    byte is the text's own, comments, quoting and order included), or `by top-level keys` (the fallback for a layout
    the in-place splice cannot follow: each changed top-level key is re-emitted whole, every other one kept byte for
    byte). Every result is parsed back and must equal `new` exactly (types included), else DialecticError: nothing
    is written that would not read as what was meant."""
    if _same(old, new):
        return text, "unchanged"
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith(("\n", "\r")):
        lines[-1] += nl
    for fine, how in ((True, "in place"), (False, "by top-level keys")):
        try:
            out = "".join(_splice_map(lines, 0, len(lines), 0, False, old, new, nl, fine))
        except _NoSplice:
            continue
        data, forbidden, error = mc._parse(out)
        if not error and not forbidden and _same(data, new):
            return out, how
    raise DialecticError("the volume could not be written back without changing what the operation did not touch; "
                         "it was left as it was")


# ---------------------------------------------------------------------------
# The checks, before and after (a write that would add a check error is not made)
# ---------------------------------------------------------------------------

Checker = Callable[[mc.Volume], mc.Report]


def default_checker(volume: mc.Volume) -> mc.Report:
    """The volume's checks: the reader's generic ones and `enough/fabula.py`'s (the fabula's own on a fabula, the
    dialectic's three on any volume holding an item of D)."""
    return fb.lint(volume)


def _errors(led: Ledger, checker: Checker | None) -> Counter:
    rep = (checker or default_checker)(led.volume())
    return Counter((p.check, p.item, p.field, p.message) for p in rep.errors)


def _new_errors(before: Counter, after: Counter) -> list[tuple]:
    return list((after - before).elements())


# ---------------------------------------------------------------------------
# Raising (B): the move `question`, its rules part, and the scaffold `bank`
# ---------------------------------------------------------------------------

@dataclass
class Raised:
    """What `raise_questions` found: `questions` (new D:question items, open, ready to land), `refused` [(proposal,
    why)] for proposed questions that did not pass, `skipped` [(source, why)] for bank entries or items not asked
    (a placeholder the item cannot fill, a duplicate)."""
    questions: list = field(default_factory=list)
    refused: list = field(default_factory=list)
    skipped: list = field(default_factory=list)


def banks_for(src: Any, *, names: Iterable[str] | None = None) -> list[dict]:
    """The manifest's banks that apply to this volume (18.6.6), as the reader gives them (`Manifest.banks()`, both
    shapes): a bank `for: {flavour: X}` applies to a volume of that flavour only; `for: {module: S}` and an empty
    `for` apply to every volume of the format. `names` keeps only the banks named."""
    led = ledger_of(src)
    keep = set(names) if names is not None else None
    out = []
    for b in led.manifest.banks():
        if keep is not None and b["name"] not in keep:
            continue
        want = (b.get("for") or {}).get("flavour")
        if want is not None and want != led.flavour:
            continue
        out.append(b)
    return out


def _fill(text: str, item: dict | None, led: Ledger) -> str | None:
    """`{name}` and `{<field>}` filled from the item (the volume's name for a question asked of the volume); None
    when a placeholder has nothing to fill it."""
    def one(mt: re.Match) -> str:
        key = mt.group(1)
        if key == "name":
            if item is None:
                n = led.catalog.get("name") or led.catalog.get("handle")
                if isinstance(n, str) and n.strip():
                    return n.strip()
                raise KeyError(key)
            n = item.get("name")
            return n.strip() if isinstance(n, str) and n.strip() else str(item.get("id"))
        if item is None:
            raise KeyError(key)
        found, v = get_field(item, key)
        if not found or v is None or isinstance(v, (dict, list)):
            raise KeyError(key)
        return str(v)
    try:
        return _PLACEHOLDER.sub(one, text)
    except KeyError:
        return None


def _unique_slug(base: str, taken: set[str], led: Ledger) -> str:
    g = led.manifest.grammar
    slug = _slug(base)
    if not g.seg["slug"].fullmatch(slug):
        slug = "q-" + slug
    cand, n = slug, 2
    while Q_PREFIX + cand in taken:
        cand, n = f"{slug}-{n}", n + 1
    taken.add(Q_PREFIX + cand)
    return cand


def _question_item(qid: str, about: Any, asks: str, why: str, spec: dict, to: str, raised: dict) -> dict:
    d: dict = {"id": qid, "type": QUESTION, "about": about, "asks": asks, "why": why,
               "kind": spec.get("kind") or "text"}
    for k in ("options", "options-open", "many", "range", "hint"):
        if spec.get(k) is not None:
            d[k] = copy.deepcopy(spec[k])
    d["to"] = to
    d["raised"] = {k: raised[k] for k in ("by", "from", "at", "run") if raised.get(k) is not None}
    d["state"] = "open"
    return d


def _items_of_kind(led: Ledger, module: str, kind: str | None) -> list[dict]:
    out = []
    for d in led.items:
        if not isinstance(d, dict) or not isinstance(d.get("id"), str) or is_d_item(d):
            continue
        mod, k = led.kind_of(d)
        if mod == module and (kind is None or k == kind):
            out.append(d)
    return out


def _unsure(d: dict) -> bool:
    prov = d.get("provenance")
    conf = prov.get("confidence") if isinstance(prov, dict) else d.get("confidence")
    state = prov.get("state") if isinstance(prov, dict) else None
    low = isinstance(conf, (int, float)) and not isinstance(conf, bool) and conf < UNSURE_BELOW
    return low or state == "pending"


def default_to(src: Any) -> str:
    """Who answers a question raised by rule when nothing else says: the `to` of the first bank that applies (the
    fabula's author for prose and verse, maker for code; Ascribe's holder), else `anyone`."""
    for b in banks_for(src):
        if isinstance(b.get("to"), str):
            return b["to"]
    return "anyone"


def raise_questions(src: Any, *, rules: bool = True, banks: Iterable[str] | None = None, pending: bool = True,
                    unsure: bool = True, to: str | None = None, author_unavailable: bool = False,
                    run: str | None = None, at: Any = None, proposed: Any = None,
                    checker: Checker | None = None) -> Raised:
    """The move `question` without a model (Thym 22.1; MacroCOSM 18.6.3, 18.6.5, 18.6.6). Reads the volume and gives
    the new open questions; writes nothing (`land` adds them). In order:

    1. from the banks that apply (`banks_for`): an entry about a module is asked once of the volume (`about: I`; not
       again while any question raised from that entry stands, whatever it is about: appendix B's `fabulan/audience`
       question is about `N:audience/owners`); about a kind, of each item of it; about a kind's field, of each item
       where the field is absent or pending. A kind entry with no item of its kind raises nothing. `{name}`
       and `{<field>}` are filled from the item; an item that cannot fill a placeholder is skipped. `raised: {by:
       bank, from: <bank>/<entry>}`. Ids: the entry's id (a module entry; `<bank>-<entry>` for a bank in the older
       shape, Ascribe's `ascribe-a1`), else `<entry>-<item slug>`.
    2. (`pending`) from every `{pending: "…"}` value of an item that is not of D, and every `pending:` on a whole item:
       `about: <item>#<field>` (or the item), `why: missing`, `asks` the pending's own text (its first letter
       capitalised), `kind: text`. `raised: {by: move, from: question}`. Id `<item slug>-<field>`.
    3. (`unsure`) from every item below confidence 0.5 or with `provenance.state: pending` that holds no pending of its
       own (its pendings already ask what is unsure): `about: <item>`, `why: unsure`, `kind: text`. Id
       `<item slug>-unsure`.
    4. `proposed`: questions a model raised (a list of mappings, or a callable given (ledger, the rule questions) that
       returns one): each needs `about`, `asks`, `why`, `kind` and may give `options`, `options-open`, `many`,
       `range`, `hint`, `to`, `from` (the stage, default `read`), `id`. `raised: {by: model}`. Each is validated by
       the volume's checks (closed lists, `question-about`, `question-shape`) and refused with the checks' words
       when it fails.

    Never a duplicate: nothing is raised for a (`raised.from`, `about`) that a question not stale or withdrawn
    already has (an answered, unknown or declined one included: "a refusal is a fact"); a rule question (2, 3) is not
    raised for an address any standing question is about; a proposed question that asks exactly what a standing
    question asks of the same address is a duplicate. `to`: the entry's or its bank's, else `default_to`; `to=` gives
    every question that word; `author_unavailable=True` sends what would go `to: author` to `expert` (18.4.6).
    `raised.at` is `at` (default now) and `raised.run` is `run` when given. Atomic in the sense of 18.6.1: the result is
    whole; `land` adds all of it or raises."""
    led = ledger_of(src)
    when = now(at)
    out = Raised()
    taken = led.ids()
    standing = [q for q in led.questions() if q.get("state") not in ENDED]
    by_from = {((q.get("raised") or {}).get("from"), _about_key(q.get("about"))) for q in standing}
    by_about = {_about_key(q.get("about")) for q in standing}
    from_any = {(q.get("raised") or {}).get("from") for q in standing}   # a module entry is asked once of the volume
    asked_texts = {(_about_key(q.get("about")), str(q.get("asks", "")).strip().lower()) for q in standing}
    fallback_to = to or default_to(led)

    def who(word: Any) -> str:
        w = to or (word if isinstance(word, str) else fallback_to)
        return "expert" if author_unavailable and w == "author" else w

    def add(q: dict, origin: str) -> None:
        key = ((q.get("raised") or {}).get("from"), _about_key(q["about"]))
        if key in by_from:
            out.skipped.append((origin, f"a question from {key[0]} about {key[1]} already stands"))
            taken.discard(q["id"])
            return
        by_from.add(key)
        by_about.add(_about_key(q["about"]))
        asked_texts.add((_about_key(q["about"]), str(q["asks"]).strip().lower()))
        out.questions.append(q)

    raised_base = {"at": when, "run": run}
    if rules:
        for b in banks_for(led, names=banks):
            older = b["name"] == led.manifest.name and not (led.manifest._block("dialectic").get("banks") or {}) \
                .get(b["name"])
            for e in b["questions"]:
                eid, about = str(e.get("id", "")), e.get("about")
                if not eid or not isinstance(about, str) or not isinstance(e.get("asks"), str):
                    out.skipped.append((f"{b['name']}/{eid}", "a bank entry needs id, about and asks"))
                    continue
                frm = f"{b['name']}/{eid}"
                raised = dict(raised_base, by="bank", **{"from": frm})
                why = e.get("why") if e.get("why") in WHYS else "missing"
                head, sep, fpath = about.partition("#")
                if ":" not in head and not sep:                       # a module: asked once of the volume
                    if frm in from_any:
                        out.skipped.append((frm, f"{frm} was asked of this volume already"))
                        continue
                    asks = _fill(e["asks"], None, led)
                    if asks is None:
                        out.skipped.append((frm, "a placeholder the volume cannot fill"))
                        continue
                    slug = _unique_slug(f"{b['name']}-{eid}" if older else eid, taken, led)
                    add(_question_item(Q_PREFIX + slug, head, asks, why, e, who(e.get("to")), {**raised}), frm)
                    continue
                module, _, kind = head.partition(":")
                for d in _items_of_kind(led, module, kind or None):
                    if sep:
                        found, v = get_field(d, fpath)
                        if found and not mc.is_pending(v):
                            continue
                        q_about = f"{d['id']}#{fpath}"
                    else:
                        q_about = d["id"]
                    asks = _fill(e["asks"], d, led)
                    if asks is None:
                        out.skipped.append((f"{frm} {d['id']}", "a placeholder the item cannot fill"))
                        continue
                    slug = _unique_slug(f"{eid}-{_bare(d['id']).split('/', 1)[-1]}", taken, led)
                    add(_question_item(Q_PREFIX + slug, q_about, asks, why, e, who(e.get("to")), {**raised}), frm)
    if rules and pending:
        for d in led.items:
            if not isinstance(d, dict) or not isinstance(d.get("id"), str) or is_d_item(d):
                continue
            for fpath, text in mc.walk_pending(d):
                if not (isinstance(text, str) and text.strip()):
                    continue
                q_about = d["id"] if fpath == WHOLE_ITEM else f"{d['id']}#{fpath}"
                if _about_key(q_about) in by_about:
                    continue
                t = text.strip()
                asks = t[:1].upper() + t[1:]
                slug = _unique_slug(f"{_bare(d['id']).split('/', 1)[-1]}-{fpath}", taken, led)
                add(_question_item(Q_PREFIX + slug, q_about, asks, "missing", {"kind": "text"}, who(None),
                                   dict(raised_base, by="move", **{"from": "question"})), f"pending {q_about}")
    if rules and unsure:
        for d in led.items:
            if not isinstance(d, dict) or not isinstance(d.get("id"), str) or is_d_item(d) or not _unsure(d):
                continue
            if any(True for _ in mc.walk_pending(d)) or _about_key(d["id"]) in by_about:
                continue
            said = d.get("summary") if isinstance(d.get("summary"), str) else d.get("name")
            asks = f"Is this right, and if not, what is? \"{str(said or d['id']).strip()}\""
            slug = _unique_slug(f"{_bare(d['id']).split('/', 1)[-1]}-unsure", taken, led)
            add(_question_item(Q_PREFIX + slug, d["id"], asks, "unsure", {"kind": "text"}, who(None),
                               dict(raised_base, by="move", **{"from": "question"})), f"unsure {d['id']}")
    props = proposed(led, list(out.questions)) if callable(proposed) else (proposed or [])
    first_model = len(out.questions)
    for p in props:
        if not isinstance(p, dict) or not isinstance(p.get("asks"), str) or not p["asks"].strip() \
                or "about" not in p:
            out.refused.append((p, "a proposed question gives about and asks"))
            continue
        key = (_about_key(p["about"]), p["asks"].strip().lower())
        if key in asked_texts:
            out.refused.append((p, "a standing question already asks this of the same address"))
            continue
        frm = p.get("from") if isinstance(p.get("from"), str) else "read"
        slug = _unique_slug(p.get("id") or (_about_key(p["about"]).split("/")[-1] + "-" + p["asks"][:24]),
                            taken, led)
        q = _question_item(Q_PREFIX + slug, copy.deepcopy(p["about"]), p["asks"].strip(), p.get("why"),
                           p, who(p.get("to")), dict(raised_base, by="model", **{"from": frm}))
        if p.get("why") is None:
            q["why"] = None
        n = len(out.questions)
        add(q, f"proposed {q['id']}")
        if len(out.questions) == n:
            out.refused.append((p, "a standing question from the same stage is about the same address"))
    # Every question raised passes the volume's checks, or is refused with their words.
    if out.questions:
        cand = led.copy()
        cand.items.extend(copy.deepcopy(out.questions))
        if cand.manifest.single_file:
            cand.catalog[_items_key(cand.manifest)] = cand.items
        rep = (checker or default_checker)(cand.volume())
        bad: dict[str, list[str]] = {}
        new_ids = {q["id"] for q in out.questions}
        for p in rep.errors:
            if _bare(p.item) in new_ids:
                bad.setdefault(_bare(p.item), []).append(str(p.message))
        if bad:
            keep = []
            for i, q in enumerate(out.questions):
                if q["id"] in bad:
                    why = "; ".join(bad[q["id"]])
                    if i >= first_model:
                        out.refused.append((q, why))
                    else:
                        out.skipped.append((q["id"], why))
                else:
                    keep.append(q)
            out.questions = keep
    return out


def land(src: Any, new_questions: Iterable[dict]) -> list[str]:
    """Add raised questions to the volume's items (a Twin's `nodes:` end), all or none: refuses a question whose id
    the volume already holds. Returns their ids."""
    led = ledger_of(src)
    qs = list(new_questions)
    ids = led.ids()
    clash = [q["id"] for q in qs if q.get("id") in ids]
    if clash:
        raise DialecticError(f"the volume already holds {', '.join(clash)}; nothing was landed")
    for q in qs:
        led.add(copy.deepcopy(q))
    return [q["id"] for q in qs]


def ask_by_bank(src: Any, **kwargs) -> Raised:
    """`raise_questions` and `land` in one step (the scaffold `bank` as a program uses it)."""
    r = raise_questions(src, **kwargs)
    land(src, r.questions)
    return r


# ---------------------------------------------------------------------------
# Recording (C): the move `record`, and the answers volume
# ---------------------------------------------------------------------------

@dataclass
class Answer:
    """One thing a person did with one question: a value, "I don't know" (`dont_know`), a refusal (`declined`) or a
    skip (`skip`). `question` is a D:question id (or its slug), or an address `<item id>#<field>` where the format asks
    from a bank without writing question items (then `spec` gives the shape: kind, options, many, range). `says` is the
    person's words, verbatim; `value` what is written, parsed from `says` when not given. `confidence` how sure the
    person is (default 1 for a value: "stated plainly"). `by` defaults to the session's `with.to`."""
    question: str
    says: str = ""
    value: Any = None
    confidence: float | None = None
    dont_know: bool = False
    declined: bool = False
    skip: bool = False
    by: str | None = None
    at: Any = None
    spec: dict | None = None

    @classmethod
    def of(cls, a: Any) -> "Answer":
        if isinstance(a, Answer):
            return a
        if not isinstance(a, dict):
            raise DialecticError(f"an answer is a mapping, not {a!r}")
        q = a.get("question") or a.get("id") or a.get("about")
        if not isinstance(q, str):
            raise DialecticError("an answer names its question")
        return cls(q, str(a.get("says") or ""), a.get("value"), a.get("confidence"),
                   bool(a.get("dont_know") or a.get("unknown")), bool(a.get("declined")), bool(a.get("skip")),
                   a.get("by"), a.get("at"), a.get("spec"))


@dataclass
class Recorded:
    """What `record` did: the session's id and item, `recorded` [(question id or address, state, the answer as
    written)], `skipped` [ids or addresses], `refused` [(question id or address, why)] (each left as it was)."""
    session: str
    session_item: dict
    recorded: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    refused: list = field(default_factory=list)


def _confidence(c: Any, default: float | None) -> float | None:
    if c is None:
        return default
    if isinstance(c, bool) or not isinstance(c, (int, float)) or not 0 <= c <= 1:
        raise AnswerRefused(f"confidence {c!r} is a number from 0 to 1")
    return c


def check_value(src: Any, spec: dict, value: Any, *, qid: str | None = None) -> Any:
    """`value` parsed and checked against a question's shape (`spec`: its kind, options, options-open, many, range),
    as it will be written (18.6.4): text, a string; choice, one of `options` (matched without regard to case), or with
    `options-open` one word outside them; yes-no, true or false (yes/no words read); number, inside `range`; date, an
    ISO date (written as a date), a year-month or a year (written as text); ref, an id that resolves in the volume and
    starts with one of `options` when they are given; span, `{lines}`, `{start, end}` or `{file, lines}` (a string
    `12` or `12-18` reads as `{lines}`). `many: true` takes a list (a string splits at new lines and semicolons).
    Raises AnswerRefused with plain words."""
    kind = spec.get("kind") or "text"
    if kind not in ANSWER_KINDS:
        raise AnswerRefused(f"{kind!r} is not an answer kind ({', '.join(ANSWER_KINDS)})", qid)
    if spec.get("many") is True:
        vals = value if isinstance(value, list) else (
            [p.strip() for p in re.split(r"[\n;]+", value) if p.strip()] if isinstance(value, str) else [value])
        if not vals:
            raise AnswerRefused("one or more, as a list", qid)
        return [_check_one(src, spec, kind, v, qid) for v in vals]
    return _check_one(src, spec, kind, value, qid)


def _check_one(src: Any, spec: dict, kind: str, v: Any, qid: str | None) -> Any:
    if v is None:
        raise AnswerRefused("an answer gives a value", qid)
    if kind == "text":
        if isinstance(v, (dict, list)):
            raise AnswerRefused("a text answer is words, not a structure", qid)
        s = _scalar_text(v)
        if not s:
            raise AnswerRefused("an empty answer", qid)
        return s
    if kind == "choice":
        opts = [str(o) for o in (spec.get("options") or [])]
        s = _scalar_text(v)
        hits = [o for o in opts if o.lower() == s.lower().rstrip(".")]
        if hits:
            return hits[0]
        if spec.get("options-open") is True and s and len(s.split()) == 1:
            return s
        raise AnswerRefused(f"{s!r} is not one of: {', '.join(opts)}"
                            + (" (or one word of your own)" if spec.get("options-open") else ""), qid)
    if kind == "yes-no":
        if isinstance(v, bool):
            return v
        s = _scalar_text(v)
        if _YES.match(s) and not _NO.match(s):
            return True
        if _NO.match(s):
            return False
        raise AnswerRefused(f"{s!r} is not yes or no", qid)
    if kind == "number":
        if isinstance(v, bool):
            raise AnswerRefused("a number, not yes or no", qid)
        if isinstance(v, str):
            s = v.strip()
            if _INT_RE.match(s):
                v = int(s)
            elif _NUM_RE.match(s):
                v = float(s)
            else:
                raise AnswerRefused(f"{s!r} is not a number", qid)
        if not isinstance(v, (int, float)):
            raise AnswerRefused(f"{v!r} is not a number", qid)
        rng = spec.get("range")
        if isinstance(rng, list) and len(rng) == 2 and all(isinstance(x, (int, float)) for x in rng):
            if not rng[0] <= v <= rng[1]:
                raise AnswerRefused(f"{v} is not from {rng[0]} to {rng[1]}", qid)
        return v
    if kind == "date":
        if isinstance(v, dt.datetime):
            raise AnswerRefused("a date, not a time: 2014-06-03, 2014-06 or 2014", qid)
        if isinstance(v, dt.date):
            return v
        s = str(v).strip()
        mt = _DATE_RE.match(s)
        if mt:
            y, mo, da = mt.group(1), mt.group(2), mt.group(3)
            try:
                if da:
                    return dt.date(int(y), int(mo), int(da))
                if mo:
                    dt.date(int(y), int(mo), 1)
                    return f"{y}-{mo}"
                return y
            except ValueError:
                pass
        raise AnswerRefused(f"{s!r} is not a date: 2014-06-03, 2014-06 or 2014", qid)
    if kind == "ref":
        s = _scalar_text(v)
        led = ledger_of(src)
        opts = [str(o) for o in (spec.get("options") or [])]
        if opts and not any(s.startswith(o) for o in opts):
            raise AnswerRefused(f"{s} does not start with {' or '.join(opts)}", qid)
        if led.index(s) is None:
            raise AnswerRefused(f"{s} names nothing in this volume", qid)
        return s
    if kind == "span":
        span = v
        if isinstance(v, (str, int)) and not isinstance(v, bool):
            mt = _LINES_RE.match(str(v))
            if not mt:
                raise AnswerRefused(f"{v!r} is not a span: lines n or n-m", qid)
            span = {"lines": mt.group(1) if not mt.group(2) else f"{mt.group(1)}-{mt.group(2)}"}
        why = _span_shape_why(span)
        if why:
            raise AnswerRefused(why, qid)
        return dict(span)
    raise AnswerRefused(f"{kind!r} is not an answer kind", qid)


def _scalar_text(v: Any) -> str:
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v).strip()


def _next_session_slug(led: Ledger) -> str:
    n = 0
    for s in led.sessions():
        mt = re.fullmatch(r"session-([0-9]+)", _bare(s["id"])[len(S_PREFIX):])
        if mt:
            n = max(n, int(mt.group(1)))
    return f"session-{n + 1}"


def _session_item(led: Ledger, session: dict | None, when: dt.datetime) -> tuple[dict, bool]:
    """(the session's item, whether it is new). An existing session is continued (its lists extended)."""
    session = dict(session or {})
    sid = session.get("id")
    if sid:
        sid = _sid(str(sid))
        have = led.session(sid)
        if have is not None:
            return have, False
    else:
        sid = S_PREFIX + _next_session_slug(led)
    through = session.get("through", "person")
    if through not in THROUGH:
        raise DialecticError(f"through is person or agent, not {through!r}")
    with_ = session.get("with") or {}
    if not isinstance(with_, dict):
        raise DialecticError("a session's with is {to, who}")
    item: dict = {"id": sid, "type": SESSION, "at": now(session.get("at") or when),
                  "with": {"to": with_.get("to") or "anyone", "who": with_.get("who") or "a person answering"},
                  "through": through}
    if session.get("model"):
        item["model"] = session["model"]
    if session.get("covers"):
        item["covers"] = session["covers"]
    item.update({"asked": [], "answered": [], "skipped": []})
    return item, True


def _classify(a: Answer, value_given: bool) -> str:
    if a.skip:
        return "skip"
    if a.declined:
        return "declined"
    if a.dont_know:
        return "unknown"
    if not value_given and a.says and DECLINE.match(a.says):
        return "declined"
    if not value_given and a.says and DONT_KNOW.match(a.says):
        return "unknown"
    return "answered"


def record(src: Any, answers: Iterable[Any], *, session: dict | None = None, at: Any = None,
           strict: bool = False) -> Recorded:
    """The move `record` (Thym 22.2; MacroCOSM 18.6.3): a person's answers into the volume's questions, by code. For
    each answer, in order: a skip leaves the question open and lists it in the session's `skipped`; "I don't know"
    (the flag, or the person's words read as Comprise's DONT_KNOW reads them) appends `{at, by, says, value: null,
    session}` and moves the question to `unknown`; a refusal (the flag, or words such as "I'd rather not say") appends
    `{…, value: null, session, declined: true}` and moves it to `declined`; a value is checked against the question's
    kind (`check_value`), appended as `{at, by, says, value, confidence, session}` and moves it to `answered`. Answers
    are appended, never rewritten; the items the questions are about are not touched. Refuses (lists in `refused`,
    the question left as it was) an answer to a question that is not open ("ask it again first": `reask`), to a
    question the volume does not hold, or with a value that does not fit. With `strict`, any refusal refuses the
    whole call and nothing is written.

    An answer may name an address `<item id>#<field>` instead of a question (a format that asks from a bank without
    writing question items): nothing is written but the session, whose lists name the address, and the parsed value
    is in `recorded` for the caller to `fold`.

    The session (`D:session/<id>`; `session=` gives `id`, `at`, `with: {to, who}`, `through`, `model`, `covers`)
    gains `asked` (every question put, in order), `answered` (those answered, unknown or declined) and `skipped`; a new
    session is added after the questions, an existing one (same id) is continued. Its id defaults to the next
    `session-<n>`."""
    led = ledger_of(src)
    when = now(at)
    sess, new_session = _session_item(led, session, when)
    sid = sess["id"]
    out = Recorded(sid, sess)
    plan: list[tuple[dict | None, str, dict | None, str, Any]] = []      # (question, kind of act, entry, ref, value)
    for raw in answers:
        a = Answer.of(raw)
        ref = a.question
        q = None
        is_addr = "#" in ref and not ref.startswith(Q_PREFIX)
        if not is_addr:
            q = led.question(ref)
            if q is None:
                out.refused.append((ref, f"{_qid(ref)} is not a question of this volume"))
                continue
            ref = q["id"]
            if q.get("state") != "open":
                out.refused.append((ref, f"{ref} is {q.get('state')}, not open: ask it again first"))
                continue
        else:
            w = resolve_about(led, ref)
            if not w.resolves or w.form != "field":
                out.refused.append((ref, w.why or f"{ref} is not an item's field"))
                continue
        value_given = a.value is not None
        act = _classify(a, value_given)
        if act == "skip":
            plan.append((q, "skip", None, ref, None))
            continue
        by = a.by or (sess.get("with") or {}).get("to") or (q or {}).get("to") or "anyone"
        entry: dict = {"at": now(a.at or when), "by": by}
        try:
            if act == "answered":
                spec = q if q is not None else (a.spec or {"kind": "text"})
                raw_value = a.value if value_given else a.says
                value = check_value(led, spec, raw_value, qid=ref)
                says = a.says or _scalar_text(value if not isinstance(value, list) else "; ".join(map(str, value)))
                entry.update({"says": says, "value": value, "confidence": _confidence(a.confidence, 1)})
            elif act == "unknown":
                entry.update({"says": a.says or "I don't know", "value": None})
                c = _confidence(a.confidence, None)
                if c is not None:
                    entry["confidence"] = c
            else:
                entry.update({"says": a.says or "I would rather not say", "value": None})
        except AnswerRefused as e:
            out.refused.append((ref, str(e)))
            continue
        entry["session"] = sid
        if act == "declined":
            entry["declined"] = True
        plan.append((q, act, entry, ref, entry.get("value")))
    if strict and out.refused:
        raise DialecticError("; ".join(f"{r}: {w}" for r, w in out.refused) + " (nothing was recorded)")
    for ref, _why in out.refused:
        if led.question(ref) is not None or "#" in ref:
            sess["asked"].append(ref)
    for q, act, entry, ref, _v in plan:
        sess["asked"].append(ref)
        if act == "skip":
            sess["skipped"].append(ref)
            out.skipped.append(ref)
            continue
        sess["answered"].append(ref)
        if q is not None:
            q.setdefault("answers", [])
            if not isinstance(q["answers"], list):
                raise DialecticError(f"{ref}: answers is not a list; fix it by hand")
            q["answers"].append(entry)
            q["state"] = act
        out.recorded.append((ref, act, entry))
    if new_session and (sess["asked"] or plan):
        led.add(sess)
    return out


def reask(src: Any, question: str, *, keep_settled: bool = True) -> dict:
    """A question asked again (18.6.3, "any → open"): another person, an expert after the author, a later session.
    Its answers are kept (the next is appended); `ended` goes. `settled` stays as the record of the earlier write, as
    the text's table says (the conductor's ruling 2: `question-shape` accepts `settled` on an open question that holds
    an answer); `keep_settled=False` removes it. When the question is answered again, `settle` folds the new answer and
    its `settled` then records that write."""
    led = ledger_of(src)
    q = led.question(question)
    if q is None:
        raise DialecticError(f"{_qid(question)} is not a question of this volume")
    q["state"] = "open"
    q.pop("ended", None)
    if not keep_settled:
        q.pop("settled", None)
    return q


def withdraw(src: Any, question: str, *, by: str = "person", because: str = "withdrawn by whoever raised it",
             at: Any = None) -> dict:
    """A question withdrawn (18.6.3, "any → withdrawn"), by whoever raised it or a move that finds it duplicates
    another: state `withdrawn`, `ended: {at, by, because}`. Answers and `settled` stay as the record."""
    led = ledger_of(src)
    q = led.question(question)
    if q is None:
        raise DialecticError(f"{_qid(question)} is not a question of this volume")
    q["state"] = "withdrawn"
    q["ended"] = {"at": now(at), "by": by, "because": because}
    return q


# ----------------------------------------------------------------- the answers volume (Thym 22.2)

@dataclass
class AnswersVolume:
    """An answers volume: a delta beside the volume it answers. `oes` the format's declaration (as this writer writes
    it, `fabula/1` for an `emf/1` twin too), `volume_id` that volume's `id`, `session` the D:session item, `entries`
    one mapping per question answered: `{id, state, answers}` (only the new answers), or, for an address asked from a
    bank without a question item, `{about, answers}`."""
    oes: str
    volume_id: str
    session: dict
    entries: list
    macrocosm: str | None = None

    def to_doc(self) -> dict:
        doc: dict = {"oes": self.oes}
        if self.macrocosm:
            doc["macrocosm"] = self.macrocosm
        doc["id"] = self.volume_id
        doc["nodes"] = [self.session] + list(self.entries)
        return doc


def answers_path(volume_path: Path | str, at: Any = None) -> Path:
    """Where an answers volume is written: beside the volume, `<its name without .cosm>.answers-<YYYY-MM-DD-HHMM>.cosm`
    (the stamp in UTC), `-2`, `-3` … on a collision. `close.md.fabulan.cosm` → `close.md.fabulan.answers-…cosm`."""
    p = Path(volume_path)
    name = p.name[:-len(".cosm")] if p.name.endswith(".cosm") else p.name
    stamp = now(at).strftime("%Y-%m-%d-%H%M")
    cand, n = p.with_name(f"{name}.answers-{stamp}.cosm"), 2
    while cand.exists():
        cand, n = p.with_name(f"{name}.answers-{stamp}-{n}.cosm"), n + 1
    return cand


def is_answers_of(volume_path: Path | str, answers: Path | str) -> bool:
    """Whether `answers` is an answers volume's name beside `volume_path` (same folder, its stem, the stamp)."""
    v, a = Path(volume_path).absolute(), Path(answers).absolute()
    mt = _ANSWERS_NAME.match(a.name)
    stem = v.name[:-len(".cosm")] if v.name.endswith(".cosm") else v.name
    return a.parent == v.parent and mt is not None and mt.group("stem") == stem


def answers_delta(src: Any, answers: Iterable[Any], *, session: dict | None = None, at: Any = None,
                  strict: bool = True) -> AnswersVolume:
    """The answers volume a page or an agent writes beside a volume instead of recording into it: `record` run on a
    copy (so the same checks and refusals apply; with `strict` any refusal raises), and the delta taken from the copy.
    The volume itself is not touched."""
    led = ledger_of(src).copy()
    rec = record(led, answers, session=session, at=at, strict=strict)
    entries: list[dict] = []
    for ref, act, entry in rec.recorded:
        if ref.startswith(Q_PREFIX):
            hit = next((e for e in entries if e.get("id") == ref), None)
            if hit is None:
                entries.append({"id": ref, "state": act, "answers": [entry]})
            else:
                hit["state"] = act
                hit["answers"].append(entry)
        else:
            entries.append({"about": ref, "answers": [entry]})
    oes = f"{led.minicosm}/{led.major}" if led.minicosm else str(led.catalog.get("oes"))
    mac = led.catalog.get("macrocosm")
    return AnswersVolume(oes, str(led.catalog.get("id") or ""), rec.session_item, entries,
                         mc.MACROCOSM_VERSION if mac is not None else None)


def write_answers_volume(av: AnswersVolume) -> str:
    """An answers volume's text, in the house style."""
    return dump_text(av.to_doc())


def read_answers_volume(text_or_path: Any, *, registry: mc.Registry | None = None) -> AnswersVolume:
    """Read an answers volume (a path or its text) as the delta Thym 22.2 says it is, never checked as a volume of its
    format. Refuses (DialecticError): text that does not parse; a declaration this reader does not read; a catalog
    without `id`; `nodes:` without exactly one D:session item; an entry that is not `{id: D:question/…, state,
    answers}` or `{about, answers}`; a state outside answered, unknown, declined; an answer that is not a mapping or
    names another session."""
    if isinstance(text_or_path, Path) or (isinstance(text_or_path, str) and "\n" not in text_or_path
                                          and text_or_path.endswith(".cosm")):
        try:
            text = Path(text_or_path).read_text(encoding="utf-8-sig")
        except OSError as e:
            raise DialecticError(f"{text_or_path}: cannot read: {e}") from e
    else:
        text = str(text_or_path)
    data, forbidden, error = mc._parse(text)
    if error or forbidden:
        raise DialecticError("the answers volume: " + (error or forbidden[0]))
    if not isinstance(data, dict):
        raise DialecticError("the answers volume: top level must be a mapping")
    reg = registry if registry is not None else mc.default_registry()
    decl = reg.identify(data)
    if isinstance(decl, mc.Refusal):
        raise DialecticError(f"the answers volume: {decl.message}")
    vid = data.get("id")
    if not isinstance(vid, str) or not vid.strip():
        raise DialecticError("the answers volume carries the id of the volume it answers")
    nodes = data.get("nodes")
    if not isinstance(nodes, list):
        raise DialecticError("the answers volume holds its session and answers under nodes:")
    sess = [n for n in nodes if is_session(n)]
    if len(sess) != 1:
        raise DialecticError("the answers volume holds exactly one D:session item")
    sid = sess[0]["id"]
    entries = []
    for n in nodes:
        if n is sess[0]:
            continue
        if not isinstance(n, dict):
            raise DialecticError(f"an answers entry is a mapping, not {n!r}")
        if "id" in n:
            if not is_question(n):
                raise DialecticError(f"{n.get('id')}: an answers entry names a D:question")
            if n.get("state") not in ANSWERED:
                raise DialecticError(f"{n['id']}: state {n.get('state')!r} is not answered, unknown or declined")
        elif not isinstance(n.get("about"), str):
            raise DialecticError("an answers entry gives a question's id, or the address asked")
        ans = n.get("answers")
        if not isinstance(ans, list) or not ans or not all(isinstance(a, dict) for a in ans):
            raise DialecticError(f"{n.get('id') or n.get('about')}: answers is a list of mappings")
        for a in ans:
            if _sid(str(a.get("session", ""))) != sid:
                raise DialecticError(f"{n.get('id') or n.get('about')}: an answer names session "
                                     f"{a.get('session')!r}, not {sid}")
        entries.append(n)
    mac = data.get("macrocosm")
    return AnswersVolume(decl.value, vid.strip(), sess[0], entries, str(mac) if mac is not None else None)


def record_answers_volume(src: Any, av: Any, *, registry: mc.Registry | None = None) -> Recorded:
    """The move `record said in f` (Thym 22.4): an answers volume applied to the volume it answers. Refuses
    (DialecticError, nothing written) one whose format or id is not this volume's, whose session the volume already
    holds (recorded already), whose entry names a question the volume does not hold or one that is not open, whose
    state disagrees with its last answer, or whose value does not fit the question's kind. Otherwise appends the
    answers, sets each question's state, and adds the session item as written."""
    led = ledger_of(src)
    if not isinstance(av, AnswersVolume):
        av = read_answers_volume(av, registry=registry)
    reg = registry if registry is not None else (led.registry or mc.default_registry())
    m = reg.by_declaration(av.oes)
    if m is None or m.name != led.manifest.name:
        raise DialecticError(f"the answers volume answers a {av.oes} volume, not a {led.minicosm} one")
    if av.volume_id != str(led.catalog.get("id") or ""):
        raise DialecticError(f"the answers volume answers {av.volume_id}, not {led.catalog.get('id')}")
    sid = av.session["id"]
    if led.session(sid) is not None:
        raise DialecticError(f"{sid} is in the volume already: these answers were recorded")
    staged: list[tuple[dict, str, list]] = []
    for n in av.entries:
        if "id" not in n:
            continue
        q = led.question(n["id"])
        if q is None:
            raise DialecticError(f"{n['id']} is not a question of this volume")
        if q.get("state") != "open":
            raise DialecticError(f"{n['id']} is {q.get('state')}, not open")
        last = n["answers"][-1]
        st = n["state"]
        if st == "declined" and last.get("declined") is not True or \
                st == "unknown" and (last.get("declined") or last.get("value") is not None) or \
                st == "answered" and (last.get("declined") or last.get("value") is None):
            raise DialecticError(f"{n['id']}: state {st} disagrees with its last answer")
        new_answers = []
        for a in n["answers"]:
            a = dict(a)
            a["session"] = sid
            if a.get("value") is not None and not a.get("declined"):
                try:
                    a["value"] = check_value(led, q, a["value"], qid=q["id"])
                except AnswerRefused as e:
                    raise DialecticError(f"{q['id']}: {e}") from e
            new_answers.append(a)
        staged.append((q, st, new_answers))
    for q, st, new_answers in staged:
        if not isinstance(q.get("answers"), list):
            q["answers"] = []
        q["answers"].extend(new_answers)
        q["state"] = st
    sess = copy.deepcopy(av.session)
    led.add(sess)
    out = Recorded(sid, sess)
    for q, st, new_answers in staged:
        out.recorded.append((q["id"], st, new_answers[-1]))
    out.skipped = list(sess.get("skipped") or [])
    return out


# ---------------------------------------------------------------------------
# Settling (D): the move `settle`, its rules part, and the scaffold `direct`
# ---------------------------------------------------------------------------

@dataclass
class Folded:
    """What one `fold` did: `wrote` the addresses written (empty when nothing was), `refused` the new check errors
    that stopped the write (nothing was written), `needs_reading` why the item must be read again (nothing written)."""
    wrote: list = field(default_factory=list)
    refused: list = field(default_factory=list)
    needs_reading: str | None = None

    @property
    def ok(self) -> bool:
        return not self.refused and self.needs_reading is None


def _last_answer(q: dict) -> dict | None:
    a = q.get("answers")
    return a[-1] if isinstance(a, list) and a and isinstance(a[-1], dict) else None


def _session_source(sid: str) -> str:
    return _sid(sid)


def _provenance_answered(d: dict, fpath: str, sid: str, confidence: Any) -> None:
    prov = d.get("provenance")
    if not isinstance(prov, dict):
        prov = {"mode": "dialectic", "sources": [sid], "confidence": confidence if confidence is not None else 1}
        d["provenance"] = prov
    srcs = prov.get("sources")
    if not isinstance(srcs, list):
        srcs = [] if srcs is None else [srcs]
        prov["sources"] = srcs
    if sid not in srcs:
        srcs.append(sid)
    ans = prov.get("answered")
    if not isinstance(ans, dict):
        ans = {}
        prov["answered"] = ans
    entry = {"sources": [sid]}
    if confidence is not None:
        entry["confidence"] = confidence
    ans[fpath] = entry


def _new_item_kind(led: Ledger, w: Where, frm: str | None) -> tuple[str | None, str | None]:
    """(module, kind) of the new item an answer about a module or a kind writes (18.6.4). About `<M>:<kind>`: that
    kind. About a module: the bank entry's `writes:` when it gives one (`<kind>` of the module, or `<M>:<kind>`
    naming another module's kind; the conductor's ruling 3 on docs/fabula-landed-D1.md), else the kind named like the
    entry's id where the module declares one, else the module's first kind."""
    m = led.manifest
    kinds = list(m.kinds(w.module))
    if w.form == "kind":
        return w.module, w.kind
    _bank, e = _bank_entry(led, frm)
    writes = (e or {}).get("writes")
    if isinstance(writes, str) and writes.strip():
        mod, sep, k = writes.strip().partition(":")
        mod, k = (mod, k) if sep else (w.module, mod)
        ok = mod != MODULE and mod in m.modules() and k in m.kinds(mod)       # never a question or a session
        return (mod, k) if ok else (None, None)
    entry = frm.split("/", 1)[1] if isinstance(frm, str) and "/" in frm else None
    if entry in kinds:
        return w.module, entry
    return (w.module, kinds[0]) if kinds else (None, None)


def _first_words(s: str, n: int = 6) -> str:
    words = re.sub(r"\s+", " ", s).strip().split(" ")
    out = " ".join(words[:n]).rstrip(".,;:!?")
    return out or s.strip()


def fold(src: Any, about: Any, answer: dict, *, question: dict | None = None, spec: dict | None = None,
         session: str | None = None, checker: Checker | None = None,
         make_item: Callable[[dict, dict, dict], dict | None] | None = None,
         reread: Callable[[dict, dict, dict], dict | None] | None = None) -> Folded:
    """Fold one answer into what it is about, exactly as MacroCOSM 18.6.4 says; the deterministic part of `settle`,
    and the "commit" of ask, check, commit for a format that asks a field directly (Comprise OES 8: no question item;
    pass `spec` for the shape and `session` for the session id).

    The answer (`{value, says, confidence, session, declined}` as `record` wrote it) is read as a value, "I don't
    know" (`value: null`) or a refusal (`declined: true`), and written:

    - **a field** (`<item>#<field>`): a value replaces what is there (a pending included); a `span` answer about a
      field named `grounds` is appended to it. The item keeps its mode; the session joins `provenance.sources` and
      `provenance.answered` gains `{<field>: {sources: [D:session/<id>], confidence}}`. "I don't know" writes
      `{pending: "<their words>"}` there. A refusal adds the field to `withheld`, sets `provenance.state:
      not-disclosed`, and removes a pending there.
    - **a module or a kind** (a bank question asked of the volume): a value (text or choice only) writes a new item of
      the kind (`<M>:<kind>`'s; for a module, the kind its bank entry is named after when the module has one, else the
      module's first kind) with `name` its first words, `summary` the answer, `stance: hearsay` where the kind requires
      a stance, and `provenance: {mode: dialectic, sources: [D:session/<id>], confidence}`; `make_item(question,
      answer, item)` may change or replace it (Ascribe's form discovery), or return None (nothing written). "I don't
      know" and a refusal write nothing.
    - **a whole item**: "I don't know" writes `pending: "<their words>"` on the item; a refusal sets
      `provenance.state: not-disclosed` and removes the item's own `pending`; a value means the item must be read
      again (`reread(item, question, answer)` returns `{<field path>: value}` to write, each with
      `provenance.answered`, or None).
    - **a span of the source**: the passage must be read again (`reread`, as above, given no item).

    A value into a field that holds a mapping or a list it would replace (a structure, not a value), or a yes-no
    answer into a field holding something other than true or false, means the item must be read again too.

    Before and after, the volume's checks run (`checker`, default `default_checker`); a write that would add an error
    is not made, and `refused` lists the errors (the caller raises the counter question). Changes the ledger only on
    success."""
    led = ledger_of(src)
    spec = spec or question or {"kind": "text"}
    kind = spec.get("kind") or "text"
    w = resolve_about(led, about)
    if not w.resolves:
        return Folded(needs_reading=None, refused=[("question-about", "", "about", w.why)])
    sid = _session_source(str(answer.get("session") or session or ""))
    declined = answer.get("declined") is True
    value = answer.get("value")
    unknown = not declined and value is None
    words = str(answer.get("says") or "").strip()
    conf = answer.get("confidence")
    cand = led.copy()
    wrote: list[str] = []

    if w.form == "span":
        if unknown or declined:
            return Folded()
        if reread is None:
            return Folded(needs_reading="the answer is about a passage of the source, which must be read again")
        return _apply_reread(led, cand, None, question or {}, answer, reread, sid, conf, checker)

    if w.form in ("module", "kind"):
        if unknown or declined:
            return Folded()
        if kind not in ITEM_KINDS_ONLY:
            return Folded(refused=[("question-about", "", "about",
                                    f"a {kind} answer cannot make a new item: it is always about a field")])
        mod, k = _new_item_kind(led, w, ((question or {}).get("raised") or {}).get("from"))
        if k is None:
            return Folded(refused=[("question-about", "", "about", f"{w.about} declares no kind to write")])
        text = _scalar_text(value)
        taken = led.ids()
        g = led.manifest.grammar
        base = _slug(_first_words(text), 40)
        slug, n = base, 2
        while g.item_id(mod, k, slug) in taken:
            slug, n = f"{base}-{n}", n + 1
        item: dict = {"id": g.item_id(mod, k, slug), "type": k, "name": _first_words(text), "summary": text}
        required = led.manifest.required_fields(mod, k)
        if "stance" in required:
            item["stance"] = "hearsay"
        for f in required:                          # a field the answer cannot fill stays an open question (ruling 3)
            if f not in item and f not in ("id", "type", "provenance"):
                item[f] = {"pending": f"what is the {f} of this {k}?"}
        item["provenance"] = {"mode": "dialectic", "sources": [sid], "confidence": conf if conf is not None else 1}
        if make_item is not None:
            item = make_item(question or {}, answer, item)
            if item is None:
                return Folded()
        cand.add(item)
        wrote.append(item["id"])
        return _commit(led, cand, wrote, checker)

    d = cand.items[w.index]
    if w.form == "item":
        if unknown:
            d["pending"] = words or "I don't know"
            wrote.append(d["id"])
        elif declined:
            prov = d.get("provenance")
            if isinstance(prov, dict):
                prov["state"] = NOT_DISCLOSED
            else:
                d["provenance"] = {"mode": "dialectic", "sources": [sid], "confidence": 1, "state": NOT_DISCLOSED}
            d.pop("pending", None)
            wrote.append(d["id"])
        else:
            if reread is None:
                return Folded(needs_reading="the answer is about the whole item, which must be read again in its "
                                            "light")
            return _apply_reread(led, cand, w.index, question or {}, answer, reread, sid, conf, checker)
        return _commit(led, cand, wrote, checker)

    # A field.
    fpath = w.field
    addr = f"{d['id']}#{fpath}"
    if unknown:
        set_field(d, fpath, {"pending": words or "I don't know"})
        wrote.append(addr)
        return _commit(led, cand, wrote, checker)
    if declined:
        wh = d.get("withheld")
        if not isinstance(wh, list):
            wh = []
            d["withheld"] = wh
        if fpath not in wh:
            wh.append(fpath)
        prov = d.get("provenance")
        if isinstance(prov, dict):
            prov["state"] = NOT_DISCLOSED
        else:
            d["provenance"] = {"mode": "dialectic", "sources": [sid], "confidence": 1, "state": NOT_DISCLOSED}
        if w.pending:
            del_field(d, fpath)
        wrote.append(addr)
        return _commit(led, cand, wrote, checker)
    cur_present, cur = w.present and not w.pending, w.value
    last_step = _steps(fpath)[-1] if _steps(fpath) else None
    if kind == "span" and last_step == "grounds":
        if cur_present and not isinstance(cur, list):
            return Folded(needs_reading=f"{addr} holds something other than a list of grounds")
        lst = list(cur) if cur_present else []
        lst.extend(value if isinstance(value, list) else [value])
        set_field(d, fpath, lst)
    else:
        if cur_present and isinstance(cur, (dict, list)) and not (spec.get("many") and isinstance(cur, list)) \
                and not (kind == "span" and isinstance(cur, dict)):
            if reread is None:
                return Folded(needs_reading=f"{addr} holds a structure the answer does not replace; the item must be "
                                            "read again")
            return _apply_reread(led, cand, w.index, question or {}, answer, reread, sid, conf, checker)
        if kind == "yes-no" and cur_present and not isinstance(cur, bool):
            if reread is None:
                return Folded(needs_reading=f"{addr} holds {cur!r}, not true or false; the item must be read again")
            return _apply_reread(led, cand, w.index, question or {}, answer, reread, sid, conf, checker)
        set_field(d, fpath, copy.deepcopy(value))
    _provenance_answered(d, fpath, sid, conf)
    wrote.append(addr)
    return _commit(led, cand, wrote, checker)


def _apply_reread(led, cand, index, question, answer, reread, sid, conf, checker) -> Folded:
    item = cand.items[index] if index is not None else None
    fields = reread(copy.deepcopy(item) if item is not None else None, copy.deepcopy(question), copy.deepcopy(answer))
    if not fields:
        return Folded(needs_reading="read again, and nothing was written")
    if item is None:
        return Folded(needs_reading="a passage read again gives no item to write into")
    wrote = []
    for fpath, v in fields.items():
        set_field(item, fpath, v)
        _provenance_answered(item, fpath, sid, conf)
        wrote.append(f"{item['id']}#{fpath}")
    return _commit(led, cand, wrote, checker)


def _commit(led: Ledger, cand: Ledger, wrote: list[str], checker: Checker | None) -> Folded:
    before = _errors(led, checker)
    if cand.manifest.single_file:
        cand.catalog[_items_key(cand.manifest)] = cand.items
    after = _errors(cand, checker)
    new = _new_errors(before, after)
    if new:
        return Folded(refused=new)
    led.items[:] = cand.items
    if cand.manifest.single_file:
        led.catalog[_items_key(led.manifest)] = led.items
    led.origin[:] = cand.origin
    return Folded(wrote=wrote)


@dataclass
class Settled:
    """What `settle` did: `settled` [(question id, wrote)], `counters` [(question id, its counter's id, the errors)]
    for refused writes, `needs_reading` [(question id, item or about, because)] for answers that need an item read
    again (left answered, unsettled), `stale` [question ids], `waiting` [(question id, why)] for questions not settled
    this run, and `run` the `derived.runs` entry when one was added."""
    settled: list = field(default_factory=list)
    counters: list = field(default_factory=list)
    needs_reading: list = field(default_factory=list)
    stale: list = field(default_factory=list)
    waiting: list = field(default_factory=list)
    run: dict | None = None


def _bank_entry(led: Ledger, frm: Any) -> tuple[dict | None, dict | None]:
    if not isinstance(frm, str) or "/" not in frm:
        return None, None
    bname, eid = frm.split("/", 1)
    for b in led.manifest.banks():
        if b["name"] == bname:
            return b, next((e for e in b["questions"] if str(e.get("id")) == eid), None)
    return None, None


def _counter_text(led: Ledger, q: dict, errors: list, value: Any) -> str:
    bank, _entry = _bank_entry(led, (q.get("raised") or {}).get("from"))
    shown = value if isinstance(value, str) else json.dumps(value, default=str)
    for check, _item, _field, _msg in errors:
        text = ((bank or {}).get("counters") or {}).get(check)
        if isinstance(text, str):
            return text.replace("{value}", str(shown)).replace("{name}", str(shown))
    msg = errors[0][3] if errors else "it did not fit"
    return f"The answer \"{shown}\" could not be written there ({msg}). What should it be instead?"


def _settled_current(q: dict) -> bool:
    """Has the question's last answer been folded in? It has `settled`, and no answer came after that settling (a
    question asked again keeps its earlier `settled`, ruling 2: an answer given since is settled anew)."""
    st = q.get("settled")
    if not st:
        return False
    last = _last_answer(q)
    try:
        if last is None or not isinstance(st, dict) or last.get("at") is None or st.get("at") is None:
            return True
        return now(last.get("at")) <= now(st.get("at"))
    except Exception:  # noqa: BLE001 - a time that does not read: the question counts as settled, as before
        return True


def _has_counter(led: Ledger, q: dict) -> bool:
    key = _about_key(q.get("about"))
    return any(o is not q and o.get("why") == "counter" and o.get("state") not in ENDED
               and (o.get("raised") or {}).get("from") == "settle" and _about_key(o.get("about")) == key
               for o in led.questions())


def settle(src: Any, *, run: str | None = None, program: str | None = None, at: Any = None,
           model: str | None = None, route: str | None = None, provider: str | None = None,
           checker: Checker | None = None, make_item: Callable | None = None, reread: Callable | None = None,
           source_text: str | None = None) -> Settled:
    """The move `settle`, by rules (Thym 22.3; MacroCOSM 18.6.4): every answered, unknown or declined question with
    no `settled` is folded (`fold`) into what it is about, in volume order, and gains `settled: {at, run, wrote}`.

    First, open and answered questions whose `about` no longer holds go `stale` (`mark_stale`, with `source_text`
    when given). A question whose write would add a check error keeps its state and stays unsettled, and a sibling
    question about the same address is raised (`why: counter`, `raised: {by: move, from: settle}`; its words from the
    bank's `counters` for the failing check, else a plain sentence naming the refusal) unless one already stands; a
    question with a standing counter waits. An answer that needs an item read again is handed to `reread` (the model
    is the caller's) or, without it, listed in `needs_reading` and left unsettled (the scaffold `direct`).

    In a fabula, when `run` and `program` are given, `derived.runs` gains `{program, run, at, model, route,
    provider}` (the keys given) and none of `derived`'s single keys change."""
    led = ledger_of(src)
    when = now(at)
    out = Settled()
    out.stale = mark_stale(led, by="settle", at=when, source_text=source_text)
    for qid in [x["id"] for x in led.questions()]:
        q = led.question(qid)                       # looked up afresh: a fold replaces the items it wrote
        if q.get("state") not in ANSWERED or _settled_current(q):
            continue
        last = _last_answer(q)
        if last is None:
            out.waiting.append((q["id"], "no answer to fold"))
            continue
        if _has_counter(led, q):
            out.waiting.append((q["id"], "its counter question stands"))
            continue
        res = fold(led, q.get("about"), last, question=q, checker=checker, make_item=make_item, reread=reread)
        if res.needs_reading:
            out.needs_reading.append((q["id"], _about_key(q.get("about")), res.needs_reading))
            continue
        if res.refused:
            taken = led.ids()
            slug = _unique_slug(q["id"][len(Q_PREFIX):] + "-counter", taken, led)
            cq = _question_item(Q_PREFIX + slug, copy.deepcopy(q.get("about")),
                                _counter_text(led, q, res.refused, last.get("value")), "counter", q,
                                q.get("to") or "anyone", {"by": "move", "from": "settle", "at": when, "run": run})
            led.add(cq)
            out.counters.append((q["id"], cq["id"], res.refused))
            continue
        q = led.question(qid)
        q["settled"] = {"at": when, **({"run": run} if run else {}), "wrote": list(res.wrote)}
        out.settled.append((q["id"], list(res.wrote)))
    if led.is_fabula and run and program:
        derived = led.catalog.get("derived")
        if isinstance(derived, dict):
            entry = {"program": program, "run": run, "at": when}
            for k, v in (("model", model), ("route", route), ("provider", provider)):
                if v:
                    entry[k] = v
            runs = derived.get("runs")
            if not isinstance(runs, list):
                runs = []
                derived["runs"] = runs
            runs.append(entry)
            out.run = entry
    return out


# ---------------------------------------------------------------------------
# The contract `only-the-asked`
# ---------------------------------------------------------------------------

def _diff_paths(a: Any, b: Any, path: str = "") -> list[str]:
    if _same(a, b):
        return []
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in list(a.keys()) + [k for k in b if k not in a]:
            sub = f"{path}.{k}" if path else str(k)
            if k not in a or k not in b:
                out.append(sub)
            else:
                out += _diff_paths(a[k], b[k], sub)
        return out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += _diff_paths(x, y, f"{path}[{i}]")
        return out
    return [path or "(the whole value)"]


def _under(path: str, allowed: str) -> bool:
    return path == allowed or path.startswith(allowed + ".") or path.startswith(allowed + "[") \
        or allowed.startswith(path + ".") or allowed.startswith(path + "[")


def only_the_asked(before: Any, after: Any) -> list[str]:
    """The contract `only-the-asked` (Thym 22.2, 22.3; MacroCOSM 18.6.7), checked: every difference between two states
    of a volume is in a D item, or in an item an answered (unknown, declined) question of `after` is about, at the
    field it is about or a field its `settled.wrote` names, with that item's `provenance`, `withheld` and whole-item
    `pending`; a new item is allowed when a question's `settled.wrote` names it; the catalog may change only in
    `derived.runs`. Returns the violations, in plain words; empty when the contract holds."""
    b, a = ledger_of(before), ledger_of(after)
    allowed: dict[str, set[str]] = {}
    new_ok: set[str] = set()
    for q in a.questions():
        if q.get("state") not in ANSWERED and not q.get("settled"):
            continue
        about = q.get("about")
        if isinstance(about, str) and ":" in about.partition("#")[0] and "/" in about:
            base, sep, fpath = about.partition("#")
            s = allowed.setdefault(_bare(base), set())
            if sep:
                s.add(fpath)
        for addr in ((q.get("settled") or {}).get("wrote") or []):
            if not isinstance(addr, str):
                continue
            base, sep, fpath = addr.partition("#")
            if sep:
                allowed.setdefault(_bare(base), set()).add(fpath)
            else:
                new_ok.add(_bare(base))
                allowed.setdefault(_bare(base), set())
    out: list[str] = []
    bi = {_bare(d["id"]): d for d in b.items if isinstance(d, dict) and isinstance(d.get("id"), str)}
    ai = {_bare(d["id"]): d for d in a.items if isinstance(d, dict) and isinstance(d.get("id"), str)}
    for iid, d in bi.items():
        if _module_of(iid) == MODULE:
            continue
        if iid not in ai:
            if iid not in new_ok:
                out.append(f"{iid} was removed, and no answered question wrote it")
            continue
        fields = allowed.get(iid)
        for p in _diff_paths(d, ai[iid]):
            top = re.split(r"[.\[]", p, maxsplit=1)[0]
            if fields is not None and (top in ("provenance", "withheld") or p == "pending"
                                       or any(_under(p, f) for f in fields)):
                continue
            out.append(f"{iid}#{p} changed, and no answered question is about it")
    for iid in ai:
        if iid not in bi and _module_of(iid) != MODULE and iid not in new_ok:
            out.append(f"{iid} was added, and no answered question wrote it")
    key = _items_key(b.manifest)
    cb = {k: v for k, v in b.catalog.items() if k != key}
    ca = {k: v for k, v in a.catalog.items() if k != key}
    for p in _diff_paths(cb, ca):
        if p == "derived.runs" or p.startswith("derived.runs[") or p.startswith("derived.runs."):
            continue
        out.append(f"the catalog's {p} changed")
    return out


def provenance_written(src: Any) -> list[str]:
    """The contract `provenance` (MacroCOSM 18.6.7; Thym 22.3), checked on a settled volume: every address a question's
    `settled.wrote` names carries the session its answer was given in: a new item, `provenance: {mode: dialectic,
    sources: [.., D:session/<id>, ..]}`; a field of an item, `provenance.answered.<field>.sources` naming the session
    (or, for "I don't know" and a refusal, which answer nothing, the item's pending or `withheld`). Returns the
    violations, in plain words; empty when the contract holds."""
    led = ledger_of(src)
    out: list[str] = []
    for q in led.questions():
        st = q.get("settled")
        last = _last_answer(q)
        if not isinstance(st, dict) or last is None:
            continue
        sid = _sid(str(last.get("session") or ""))
        for addr in st.get("wrote") or []:
            if not isinstance(addr, str):
                continue
            base, sep, fpath = addr.partition("#")
            d = led.item(base)
            if d is None:
                continue                            # its own answer removed it (18.6.3): the record stands
            prov = d.get("provenance") if isinstance(d.get("provenance"), dict) else {}
            if not sep:
                if last.get("value") is None:
                    continue
                srcs = prov.get("sources") if isinstance(prov.get("sources"), list) else []
                if prov.get("mode") != "dialectic" and sid not in srcs:
                    out.append(f"{base} was written by {q['id']} without {sid} as its source")
                continue
            if last.get("declined") is True or last.get("value") is None:
                continue
            ans = (prov.get("answered") or {}).get(fpath) if isinstance(prov.get("answered"), dict) else None
            if not (isinstance(ans, dict) and sid in (ans.get("sources") or [])):
                out.append(f"{addr} was written by {q['id']} without provenance.answered naming {sid}")
    return out


# ---------------------------------------------------------------------------
# Staleness and carrying over (E)
# ---------------------------------------------------------------------------

def stale_reasons(src: Any, *, source_text: str | None = None, previous: Any = None) -> list[tuple[str, str]]:
    """[(question id, because)] for every open or answered question (not settled) whose `about` no longer holds
    (18.6.3): its item is gone; its field was dropped (needs `previous`, the volume before a decompile done again:
    the field held a value there and is absent here); or, given the source's text, a span's words are not found
    (`{start, end}`) or its lines run past the end (`{lines}`). A module or kind the format no longer declares, and an
    address that no longer parses, are gone too."""
    led = ledger_of(src)
    prev = ledger_of(previous) if previous is not None else None
    out = []
    n_lines = len(source_text.splitlines()) if isinstance(source_text, str) else None
    for q in led.questions():
        if q.get("state") not in ("open", "answered") or q.get("settled"):
            continue
        about = q.get("about")
        w = resolve_about(led, about)
        if not w.resolves:
            if w.form == "span":
                continue                            # a malformed span is question-about's to report, not stale
            out.append((q["id"], f"{w.why}: what it was about is gone"))
            continue
        if w.form == "field" and prev is not None and not w.present:
            pd = prev.item(w.item_id)
            if pd is not None:
                found, v = get_field(pd, w.field)
                if found and not mc.is_pending(v):
                    out.append((q["id"], f"{w.item_id}#{w.field} was dropped when the source was read again"))
                    continue
        if w.form == "span" and isinstance(source_text, str):
            sp = w.span or {}
            if "start" in sp and "end" in sp:
                flat = re.sub(r"\s+", " ", source_text)
                if re.sub(r"\s+", " ", sp["start"].strip()) not in flat or \
                        re.sub(r"\s+", " ", sp["end"].strip()) not in flat:
                    out.append((q["id"], "the source changed and the span's words are not found"))
            elif "lines" in sp and "file" not in sp and n_lines is not None:
                rng = fb._lines(sp["lines"])
                if rng and rng[1] > n_lines:
                    out.append((q["id"], f"the source has {n_lines} lines; the span's lines {sp['lines']} are gone"))
    return out


def mark_stale(src: Any, *, by: str = "question", at: Any = None, source_text: str | None = None,
               previous: Any = None) -> list[str]:
    """Every question `stale_reasons` names goes `stale`, with `ended: {at, by: <the move>, because}`; nothing is
    written into items. Returns their ids."""
    led = ledger_of(src)
    when = now(at)
    ids = []
    for qid, because in stale_reasons(led, source_text=source_text, previous=previous):
        q = led.question(qid)
        q["state"] = "stale"
        q["ended"] = {"at": when, "by": by, "because": because}
        ids.append(qid)
    return ids


@dataclass
class Carried:
    """What `carry_over` did: `carried` the D items brought over, `stale` the questions that went stale on the way,
    `replaced` new D items an old one of the same id replaced, `dropped` new open questions an old standing one
    already asks (same `raised.from` and `about`)."""
    carried: list = field(default_factory=list)
    stale: list = field(default_factory=list)
    replaced: list = field(default_factory=list)
    dropped: list = field(default_factory=list)


def carry_over(old: Any, new: Any, *, at: Any = None, by: str = "derive", source_text: str | None = None) -> Carried:
    """After a text is decompiled again (18.6.3, "A decompile done again"): every D item of the old volume is carried
    into the new one, with its answers, state and sessions. A question whose `about` still resolves in the new
    volume keeps its state; one that is not settled and whose `about` no longer resolves (its item gone, its field
    dropped, a span's words gone given `source_text`) goes `stale` with `ended: {at, by, because}`. Settled answers
    are not written again. An old item replaces a new D item of the same id; a new open, unanswered question that a
    carried standing question already asks (same `raised.from`, same `about`) is dropped. Changes `new` only."""
    o, n = ledger_of(old), ledger_of(new)
    when = now(at)
    out = Carried()
    carried_keys = set()
    for d in o.items:
        if not is_d_item(d):
            continue
        dd = copy.deepcopy(d)
        i = n.index(dd["id"])
        if i is not None:
            n.items[i] = dd
            out.replaced.append(dd["id"])
        else:
            n.add(dd)
        out.carried.append(dd["id"])
        if is_question(dd) and dd.get("state") not in ENDED:
            carried_keys.add(((dd.get("raised") or {}).get("from"), _about_key(dd.get("about"))))
    for d in list(n.items):
        if is_question(d) and d["id"] not in out.carried and d.get("state") == "open" and not d.get("answers"):
            key = ((d.get("raised") or {}).get("from"), _about_key(d.get("about")))
            if key in carried_keys:
                n.items.remove(d)
                out.dropped.append(d["id"])
    carried = set(out.carried)
    for qid, because in stale_reasons(n, source_text=source_text, previous=o):
        if qid not in carried:
            continue
        q = n.question(qid)
        q["state"] = "stale"
        q["ended"] = {"at": when, "by": by, "because": because}
        out.stale.append(qid)
    # A carried question not settled whose about is gone, in a state the table does not name (unknown, declined).
    for q in n.questions():
        if q["id"] in carried and q.get("state") in ("unknown", "declined") and not q.get("settled"):
            w = resolve_about(n, q.get("about"))
            if not w.resolves and w.form != "span":
                q["state"] = "stale"
                q["ended"] = {"at": when, "by": by, "because": f"{w.why}: what it was about is gone"}
                out.stale.append(q["id"])
    return out


# ---------------------------------------------------------------------------
# The command line (F)
# ---------------------------------------------------------------------------

def _print_open(led: Ledger, out) -> None:
    oq = open_questions(led)
    for e in oq:
        if e["form"] == "question":
            print(f"  {e['id']}  ({e['why']}, {e['kind']}, to {e['to']})  about {_about_key(e['about'])}", file=out)
            print(f"      {e['asks']}", file=out)
        else:
            print(f"  (pending)  about {e['about']}", file=out)
            print(f"      {e['asks']}", file=out)
    counts = Counter(q.get("state") for q in led.questions())
    print(f"{len(led.questions())} questions ({', '.join(f'{v} {k}' for k, v in counts.items()) or 'none'}), "
          f"{len(led.sessions())} sessions, {len(oq)} open", file=out)


def _prompt(q: dict, ask: Callable[[str], str], out) -> Answer | None:
    """One question put to a person at the terminal; None to stop."""
    print("", file=out)
    print(q.get("asks"), file=out)
    if q.get("hint"):
        print(f"  ({q['hint']})", file=out)
    shape = q.get("kind") or "text"
    if shape == "choice":
        print(f"  one of: {', '.join(map(str, q.get('options') or []))}"
              + (" (or a word of your own)" if q.get("options-open") else ""), file=out)
    elif shape == "number" and q.get("range"):
        print(f"  a number from {q['range'][0]} to {q['range'][1]}", file=out)
    elif shape != "text":
        print(f"  ({shape}{', several, separated by ;' if q.get('many') else ''})", file=out)
    while True:
        try:
            said = ask("  answer (? I don't know, - skip, x decline, q stop): ")
        except EOFError:
            return None
        s = said.strip()
        if s.lower() in ("q", "quit"):
            return None
        if s in ("", "-"):
            return Answer(q["id"], skip=True)
        if s == "?":
            more = ask("  in your own words, what is not known? (enter to leave it): ").strip()
            return Answer(q["id"], says=more, dont_know=True)
        if s.lower() == "x":
            return Answer(q["id"], says="", declined=True)
        return Answer(q["id"], says=s)


def main(argv: list[str] | None = None, *, ask: Callable[[str], str] = input, out=None) -> int:
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="python -m enough.dialectic",
                                 description="The dialectic: ask a person what a volume's source means, record what "
                                             "they say, and settle it into the volume. Writes only the volume given "
                                             "and its sibling answers file.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list", help="the volume's questions, sessions and open questions")
    p.add_argument("volume")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("raise", help="land the opening and open questions, by rules")
    p.add_argument("volume")
    p.add_argument("--rules", action="store_true", help="the rules part only (always so here: no model is asked)")
    p.add_argument("--to", help="who answers every question raised")
    p.add_argument("--author-unavailable", action="store_true", help="questions for the author go to an expert")
    p.add_argument("--run", help="the run's id, written in raised.run")
    p.add_argument("--dry-run", action="store_true", help="say what would be raised; write nothing")
    p = sub.add_parser("answer", help="answer the open questions, one at a time, or record an answers volume")
    p.add_argument("volume")
    p.add_argument("--from", dest="source", help="record this answers volume (beside the volume) instead of asking")
    p.add_argument("--into", action="store_true", help="record into the volume at once (default: write an answers "
                                                       "volume beside it)")
    p.add_argument("--who", default="a person answering at the terminal", help="a plain description, never a name")
    p.add_argument("--to", help="the answerer's word (author, expert, maker, holder, owner, anyone)")
    p.add_argument("--through", choices=THROUGH, default="person")
    p.add_argument("--model", help="the agent's model, with --through agent")
    p = sub.add_parser("settle", help="fold the answered questions into the volume, by rules")
    p.add_argument("volume")
    p.add_argument("--answers", help="record this answers volume (beside the volume) first")
    p.add_argument("--run", help="the run's id (settled.run, and derived.runs with --program)")
    p.add_argument("--program", help="the program's name, for derived.runs")
    args = ap.parse_args(argv)
    vpath = Path(args.volume)
    try:
        if args.cmd == "list":
            led = ledger_of(vpath)
            if args.json:
                print(json.dumps({"questions": mc.jsonable(led.questions()), "sessions": mc.jsonable(led.sessions()),
                                  "open": mc.jsonable(open_questions(led))}, ensure_ascii=False, indent=2), file=out)
            else:
                _print_open(led, out)
            return 0
        twin = open_twin(vpath)
        if args.cmd == "raise":
            r = raise_questions(twin, to=args.to, author_unavailable=args.author_unavailable, run=args.run)
            for q in r.questions:
                print(f"  {q['id']}  about {_about_key(q['about'])}: {q['asks']}", file=out)
            for s, why in r.skipped:
                print(f"  skipped {s}: {why}", file=out)
            print(f"{len(r.questions)} questions raised" + (" (dry run: nothing written)" if args.dry_run else ""),
                  file=out)
            if not args.dry_run and r.questions:
                land(twin, r.questions)
                twin.save()
            return 0
        if args.cmd == "answer":
            if args.source:
                if not is_answers_of(vpath, args.source):
                    raise DialecticError(f"{args.source} is not an answers volume beside {vpath.name} "
                                         f"({vpath.name[:-5] if vpath.name.endswith('.cosm') else vpath.name}"
                                         ".answers-<YYYY-MM-DD-HHMM>.cosm)")
                rec = record_answers_volume(twin, Path(args.source))
                twin.save()
                print(f"recorded {len(rec.recorded)} answers in {rec.session}", file=out)
                return 0
            opened = [q for q in twin.ledger.questions() if q.get("state") == "open"]
            if not opened:
                print("no open questions (raise them first)", file=out)
                return 0
            to = args.to or (opened[0].get("to") if isinstance(opened[0].get("to"), str) else "anyone")
            session = {"with": {"to": to, "who": args.who}, "through": args.through, "model": args.model}
            given: list[Answer] = []
            for q in opened:
                while True:
                    a = _prompt(q, ask, out)
                    if a is None:
                        break
                    if not (a.skip or a.dont_know or a.declined) and not DONT_KNOW.match(a.says) \
                            and not DECLINE.match(a.says):
                        try:
                            check_value(twin.ledger, q, a.says, qid=q["id"])
                        except AnswerRefused as e:
                            print(f"  {e}", file=out)
                            continue
                    given.append(a)
                    break
                if a is None:
                    break
            if not given:
                print("nothing answered; nothing written", file=out)
                return 0
            if args.into:
                rec = record(twin, given, session=session, strict=True)
                twin.save()
                print(f"recorded {len(rec.recorded)} answers in {rec.session}", file=out)
            else:
                av = answers_delta(twin, given, session=session)
                dest = answers_path(vpath)
                write_atomic(dest, write_answers_volume(av))
                print(f"wrote {dest.name}: {len(av.entries)} answers in {av.session['id']}; settle with "
                      f"`settle {vpath.name} --answers {dest.name}`", file=out)
            return 0
        if args.cmd == "settle":
            if args.answers:
                if not is_answers_of(vpath, args.answers):
                    raise DialecticError(f"{args.answers} is not an answers volume beside {vpath.name}")
                record_answers_volume(twin, Path(args.answers))
            res = settle(twin, run=args.run, program=args.program)
            for qid, wrote in res.settled:
                print(f"  settled {qid}: {', '.join(wrote) or 'nothing written'}", file=out)
            for qid, cid, errs in res.counters:
                print(f"  refused {qid}: {errs[0][3]} (asked again as {cid})", file=out)
            for qid, about, because in res.needs_reading:
                print(f"  waits {qid}: {because}", file=out)
            twin.save()
            print(f"{len(res.settled)} settled, {len(res.counters)} refused, {len(res.needs_reading)} to read again, "
                  f"{len(res.stale)} stale", file=out)
            return 0
    except DialecticError as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    return 1


# ---------------------------------------------------------------------------
# The engine Thym's moves call (`ctx.engines["dialectic"]`; docs/fabula-landed-T1-dialectic.md, section 2)
# ---------------------------------------------------------------------------
#
# A run records every engine call and a replay answers it from the record, so these take and give plain data only:
# text, mappings, lists, strings, whole numbers and timestamps (a confidence travels inside YAML text). A `volume` is
# `{text, filename}` (a single-file volume) or `{path}` (a folder volume: questioned, never written). A refusal is
# returned as `{refused: <plain words>}`, never raised, so that a replay gives the same words.

def _thym_twin(volume: dict) -> Twin:
    return twin_from_text(volume["text"], filename=volume.get("filename") or "volume.cosm")


def _thym_ledger(volume: dict) -> Ledger:
    return ledger_of(volume["path"]) if "path" in volume else _thym_twin(volume).ledger


def thym_question(volume: dict, *, proposed: list | None = None, run: str | None = None, at: Any = None) -> dict:
    """The volume's new open questions: the rules', then the `proposed` ones that pass the hook (`raise_questions`).
    `{questions, refused: [{index, about, asks, why}], skipped: [{source, why}]}`; nothing is written."""
    led = _thym_ledger(volume)
    props = [dict(p) for p in proposed or []]
    r = raise_questions(led, run=run, at=at, proposed=props)
    refused = []
    for obj, why in r.refused:
        idx = next((i for i, p in enumerate(props) if obj is p or (
            isinstance(obj, dict) and str(p.get("asks", "")).strip() == obj.get("asks")
            and p.get("about") == obj.get("about"))), None)
        refused.append({"index": idx, "about": _about_key(obj.get("about")) if isinstance(obj, dict) else None,
                        "asks": obj.get("asks") if isinstance(obj, dict) else None, "why": str(why)})
    return {"questions": [copy.deepcopy(q) for q in r.questions], "refused": refused,
            "skipped": [{"source": str(s), "why": str(w)} for s, w in r.skipped]}


def thym_record(volume: dict, answers: dict) -> dict:
    """An answers volume (`answers = {text}`) recorded into the volume, all or none: `{text, recorded: [[id, state]]}`
    or `{refused}`."""
    if "path" in volume:
        return {"refused": "answers are recorded into a volume of one file"}
    try:
        t = _thym_twin(volume)
        rec = record_answers_volume(t, answers["text"])
        return {"text": t.render(), "recorded": [[str(i), str(s)] for i, s, _a in rec.recorded]}
    except DialecticError as e:
        return {"refused": str(e)}


def _thym_value_text(v: Any) -> str:
    return v if isinstance(v, str) else ("" if v is None else mc.dump({"v": v})[3:].strip())


def thym_settle(volume: dict, *, rereads: dict | None = None, run: str | None = None, program: str | None = None,
                at: Any = None, model: str | None = None, route: str | None = None, provider: str | None = None,
                dry: bool = False) -> dict:
    """Every answered question folded by rules (`settle`); `rereads` (`{question id: <fields as YAML text>}`) written
    where they pass the checks, else listed in `refused_rereads` and left unsettled, with no counter question. `dry`
    changes nothing in the answer: the caller does not land it."""
    if "path" in volume:
        return {"refused": "answers are settled into a volume of one file"}
    try:
        t = _thym_twin(volume)
    except DialecticError as e:
        return {"refused": str(e)}
    good: dict = {}
    refused: list = []
    for qid, text in (rereads or {}).items():
        fields = mc.yaml_load(text) if isinstance(text, str) else None
        probe = t.ledger.copy()
        q = probe.question(qid)
        last = _last_answer(q) if q else None
        if q is None or last is None or not isinstance(fields, dict):
            refused.append({"question": qid, "errors": ["no such answered question, or no fields"]})
            continue
        res = fold(probe, q.get("about"), last, question=q, reread=lambda _i, _q, _a, f=fields: f)
        if res.refused:
            refused.append({"question": qid, "errors": [str(m) for _c, _it, _f, m in res.refused]})
        elif res.ok:
            good[qid] = fields
    before = t.ledger.copy()
    s = settle(t, run=run, program=program, at=at, model=model, route=route, provider=provider,
               reread=(lambda _i, q, _a: good.get(q.get("id"))) if good else None)
    rows = []
    for qid, about, because in s.needs_reading:
        q = before.question(qid) or {}
        last = _last_answer(q) or {}
        w = resolve_about(before, q.get("about"))
        item = before.items[w.index] if w.index is not None else None
        rows.append({"question": qid, "about": about, "because": because,
                     "item": mc.dump(item) if item is not None else None, "asks": q.get("asks"),
                     "says": last.get("says"), "value": _thym_value_text(last.get("value"))})
    return {"text": t.render(), "settled": [[i, list(w)] for i, w in s.settled],
            "counters": [[i, c, [str(e[3]) for e in errs]] for i, c, errs in s.counters],
            "needs_reading": rows, "refused_rereads": refused, "stale": list(s.stale),
            "waiting": [[i, str(w)] for i, w in s.waiting]}


def thym_engine() -> Any:
    """The engine Thym's dialectic moves reach as `ctx.engines["dialectic"]`: `thym_question`, `thym_record`,
    `thym_settle` (the host registers it under that name)."""
    from types import SimpleNamespace
    return SimpleNamespace(thym_question=thym_question, thym_record=thym_record, thym_settle=thym_settle)


__all__ = [
    "ANSWERED", "ANSWER_KINDS", "Answer", "AnswerRefused", "AnswersVolume", "Carried", "DECLINE", "DONT_KNOW",
    "DialecticError", "ENDED", "Folded", "Ledger", "MODULE", "Q_PREFIX", "Raised", "Recorded", "STATES", "S_PREFIX",
    "Settled", "THROUGH", "Twin", "UNSURE_BELOW", "WHYS", "Where", "answers_delta", "answers_path", "ask_by_bank",
    "banks_for", "carry_over", "check_value", "default_checker", "default_to", "del_field", "dump_text", "fold",
    "get_field", "is_answers_of", "is_d_item", "is_question", "is_session", "land", "ledger_from_items",
    "ledger_from_volume", "ledger_of", "main", "mark_stale", "now", "only_the_asked", "open_questions", "open_twin",
    "provenance_written", "questions", "raise_questions", "read_answers_volume", "reask", "record",
    "record_answers_volume", "resolve_about", "sessions", "set_field", "settle", "stale_reasons", "thym_engine", "thym_question", "thym_record", "thym_settle",
    "twin_from_text", "withdraw",
    "write_answers_volume", "write_atomic", "write_back",
]


if __name__ == "__main__":
    raise SystemExit(main())
