"""The runtime: a plan walked in order, deterministic moves run in code, model-backed moves sent to the coprocessor
behind their contracts, every run traced and replayable (docs/THYM.md 12, with 4.5, 8, 9, 11.1, 18 and 19).

`run(plan, ...)` takes a plan volume mapping (the shape of `tests/fixtures/thym/expected/*/plan.cosm`) and:

1. checks it against the environment, at plan time, before anything runs (THYM.md 9, 12.1, 19): agent-free (or
   `--rules`) with nodes that ask a model and have no scaffold is refused with their count and the first one's line;
   every input must be present with the digest the plan recorded; the `preflight` hook may refuse a plan whose largest
   prompt the machine's model cannot hold; every move must be declared and implemented here;
2. walks the nodes in a topological order (sequentially, plan order breaking ties). A node's call is read from its
   `name` (`band t3 as [none, some]`, `emit employees: mark t4 as verified`, `emit offer-line o, for each o in h where
   kind in [product, service, platform]`, `if now.medium is "phone" and now.hurry`, `assert f covers story`): outside
   a loop's body the planner writes nested calls as temporaries, so a name is one flat statement; inside one, a
   statement's nested calls are folded into its node (THYM 11.1), and the name holds them as written (`emit mark (mark
   o as stated) as verified, for each o in h …`, `assert words x > 0, for x = t`), evaluated whole for each member
   through `_eval`, which runs every nested call with its contract. A deterministic node calls the
   registry; a model-backed one builds the contract from the declaration (`checks` = its `contract:` list) and the
   node's budget, sends the move's `Request` to the coprocessor, checks every candidate against the contract, repairs
   and retries within `attempts`, and refuses the whole run on failure. An `if` node evaluates its condition, and the
   nodes of the branch not taken are skipped; a `repeats` node walks its collection (a volume's items in told order, a
   short's lines, a list's members) and runs its statement once per member (an `assert` too); a node of a loop over a
   written list (`, for x = <member>`) runs once, with the loop variable bound to its member; `emit` collects into
   the run's output volume
   (`ctx.emitted`, or a labelled field, `ctx.slots`) for `project`; a `let` filter (`let staff = h where module is
   employees`), which has no node of its own, and a user move's body are read from the program (its items, or its
   `.thym` source);
3. lands every output or none: the program's output is written under `<root>/runs/<run-id>/stage/` and moved to
   `outputs/<gives-name>.<ext>` only when every node has succeeded, with the trace (`<run-id>.trace.cosm`) and the plan
   (`<run-id>.plan.cosm`) beside it; every candidate the coprocessor gave is recorded under `candidates/`, and every
   call a move made to one of enough's engines beside them (`engines.py`), so that `replay(run_dir)` re-runs the run
   with the replay coprocessor, and no engine, to byte-identical outputs (THYM.md 12.4).

A plan-time refusal is returned as a `Refusal` (nothing ran, nothing was written). A run that starts returns its
`Trace`, whose `outcome` is `landed` or `refused` and whose `refusal` says why (THYM.md 9: a refusal is a value).

**Refusals in the person's words** (THYM 9). A refusal at plan or run time names the statement as the person wrote
it (from the program beside the plan, by its line; without the program, the node's name with every temporary put
back as the expression it stands for), cut to 60 characters, then its line and, inside a loop, the pass:
`<statement> (line N[, for <var> = <member>]): <what failed>[: the fix]` (`_worded`). It never shows a temporary, a
node's number or id, an implementation's exception or a value as Python prints it; a fault of the runtime itself says
so, and its record keeps the detail under `fault`.

**Folders and several outputs** (`thym 1`, THYM 12.1, 20.3, 20.4). A folder input is read under the folder rule and
held to its tree digest; the run snapshots it as `inputs/<name>.folder.cosm` before any node runs, and a replay reads it
from that snapshot and never from the disk (`replay` passes `snapshots`). A `for each` walks a folder's text files
(a pass is named by the file's path, `for t = little/cli.py`), a `where` over a folder gives a folder, and `in` finds
a string in a text. A program of several outputs lands them all in one step or none; a folder output lands as the
directory `outputs/<name>/`, its row in the trace `{name, sha256: <tree digest>, path: outputs/<name>/}`. A move whose
declaration chooses its `gives`, contract or scaffold by the call (`gives-when`, …) is held to the chosen one.

Three `thym 0` loops still run wrong, and are refused at run with the fix, write `thym 1` (THYM 8.1): an `if` inside a
loop over a collection known only at run time (its condition is evaluated once, before the loop), a `let` inside
such a loop read later in the same loop (it holds every pass's value at once), and a `for each` nested inside such a
loop (the plan lost the outer loop), check `loop`.

**What `thym 1` adds to a run** (THYM 7.5, 8.1, 8.3, 12.3). A node of move `for` is a whole loop (`_loop_node`): its
header and body are read from the program by the loop's line, and the body runs member by member as a unit, as a user
move's body runs (`_body`): a name it binds, an `if` inside it and a nested call take this pass's values; a `keep`
adds to the list of the nearest loop that collects, bound when the last pass ends; the record says how many `passes`
it made and holds a row `<name>.<k>` per value kept, and a refusal inside it names the statement of the body and the
pass. A user move's kept contracts run on the value it gives (a contract block's lines, or a named check); a failed
one runs the body again when the move asks, within the node's attempts, every model request of the re-run carrying
the failed verdicts in `repair.failed`, and refuses with the contract's name after the last; a move that does not ask
is refused at once. A program's kept contracts are checked before anything lands. A move that may call itself is
counted on the call stack against its `depth`.

Standalone: the standard library, PyYAML and `enough.macrocosm`.
"""
from __future__ import annotations

import datetime as _dt
import heapq
import re
import secrets
import shutil
import time
from collections import ChainMap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from enough import macrocosm as mc
from enough.thym import Refusal
from enough.thym import checks as _checks
from enough.thym import folder as _folder
from enough.thym import registry as _registry
from enough.thym import trace as _trace
from enough.thym.coprocessor import RecordingCoprocessor, RefusingCoprocessor, ReplayCoprocessor
from enough.thym.coprocessor import ask as _ask
from enough.thym.coprocessor import prose_problem
from enough.thym.coprocessor import where as _coproc_where
from enough.thym.engines import CallCounter, EngineRefusal, Recording, Replaying, recorded_names
from enough.thym.registry import Amount, Request, Where, decl_get
from enough.thym.trace import Trace, default_root, digest_row, node_number, write_atomic
from enough.thym.values import (NOTHING, Value, canonical, filter_folder, item_id, item_key, load_input, members,
                                 plain, posix_path, sha256_bytes, stamp, wrap, write_snapshot)

MODIFIERS = ("as", "by", "with", "to", "against", "of", "in", "where", "marked", "before", "after")
UNITS = ("words", "sentences")
#: The words a condition's terms are joined and compared with; a call on a side of a comparison ends at one (THYM 4.5)
_COND_WORDS = ("is", "in", "has", "covers", "and", "or", "not", "then", "else", "where", "marked")
_KEYWORDS = frozenset(("thym", "use", "program", "move", "morph", "context", "end", "why", "must", "decided", "takes",
                       "gives", "let", "assert", "if", "then", "else", "for", "each", "in", "where", "emit", "give",
                       "withhold", "as", "by", "with", "to", "against", "of", "marked", "is", "not", "and", "or", "has",
                       "covers", "keep", "keeps", "contract", "depth", "before", "after"))
_ENGINE_RANK = {"skipped": 0, "code": 1, "rules": 2}


# ---------------------------------------------------------------------------
# The reader: one statement of THYM.md 4.4 and 4.5, as a node's name or a step's text holds it
# ---------------------------------------------------------------------------

class ReadError(ValueError):
    """A statement the runtime's reader cannot read."""


_TOKEN = re.compile(r"""
    (?P<ws>\s+)
  | (?P<string>"(?:[^"\\]|\\.)*")
  | (?P<uri>oes:[^\s,\])]+)
  | (?P<date>\d{4}-\d{2}-\d{2}(?![\w-]))
  | (?P<int>\d+)
  | (?P<name>[A-Za-z_][A-Za-z0-9_-]*)
  | (?P<punct>[()\[\],.:=<>])
""", re.X)


def strip_comment(line: str) -> str:
    """A line without its comment (`--` to the end of the line, outside a string)."""
    in_str = False
    i = 0
    while i < len(line):
        c = line[i]
        if c == "\\" and in_str:
            i += 2
            continue
        if c == '"':
            in_str = not in_str
        elif not in_str and line.startswith("--", i):
            return line[:i]
        i += 1
    return line


def _tokenize(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    pos = 0
    text = strip_comment(text)
    while pos < len(text):
        mt = _TOKEN.match(text, pos)
        if not mt:
            raise ReadError(f"cannot read {text[pos:pos + 12]!r}")
        kind = mt.lastgroup or ""
        if kind != "ws":
            out.append((kind, mt.group(0)))
        pos = mt.end()
    out.append(("end", ""))
    return out


@dataclass
class Name:
    name: str


@dataclass
class Lit:
    value: Value


@dataclass
class ListLit:
    items: list


@dataclass
class FieldRead:
    base: Any
    name: str


@dataclass
class Call:
    move: str
    operands: list
    mods: dict


@dataclass
class Filter:
    base: Any
    cond: Any
    text: str


@dataclass
class Cmp:
    op: str
    left: Any
    right: Any


@dataclass
class Has:
    base: Any
    name: str


@dataclass
class Covers:
    left: Any
    right: Any


@dataclass
class Bare:
    expr: Any


@dataclass
class BoolOp:
    op: str
    items: list


@dataclass
class Not:
    item: Any


@dataclass
class Loop:
    var: str
    coll: Any
    cond: Any = None


@dataclass
class Stmt:
    """One statement: `form` is `let`, `assert`, `if`, `for`, `emit`, `give` or `effect` (a call run for its value or
    its effect; `withhold` is a call of the move `withhold`)."""
    form: str
    expr: Any = None
    cond: Any = None
    name: str | None = None
    slot: str | None = None
    message: str | None = None
    loop: Loop | None = None
    text: str = ""
    #: a node of a loop over a written list: `(var, member)`, read from its `, for x = <member>` trailer
    member: tuple | None = None


class _Reader:
    def __init__(self, text: str, moves: set[str], in_moves: frozenset[str] = frozenset(),
                 where_moves: frozenset[str] = frozenset()) -> None:
        self.text = text
        self.toks = _tokenize(text)
        self.i = 0
        self.moves = moves
        self.in_moves = in_moves
        self.where_moves = where_moves

    # -- tokens --
    def peek(self, k: int = 0) -> tuple[str, str]:
        return self.toks[min(self.i + k, len(self.toks) - 1)]

    def take(self) -> tuple[str, str]:
        t = self.toks[self.i]
        if t[0] != "end":
            self.i += 1
        return t

    def at(self, text: str, k: int = 0) -> bool:
        t = self.peek(k)
        return t[0] in ("name", "punct") and t[1] == text

    def expect(self, text: str) -> None:
        if not self.at(text):
            raise ReadError(f"expected {text!r}, found {self.peek()[1] or 'the end'!r}")
        self.take()

    def name(self) -> str:
        t = self.take()
        if t[0] != "name":
            raise ReadError(f"expected a name, found {t[1] or 'the end'!r}")
        return t[1]

    def at_end(self) -> bool:
        return self.peek()[0] == "end"

    def at_trailer(self) -> bool:
        return self.at(",") and self.at("for", 1) and self.at("each", 2)

    def at_member_trailer(self) -> bool:
        """`, for x = <member>`: the node of a loop over a written list, for one member (THYM 11.1)."""
        return self.at(",") and self.at("for", 1) and self.peek(2)[0] == "name" and self.at("=", 3)

    def at_side_call(self) -> bool:
        """A call on a side of a comparison (`thym 1`, THYM 4.5): a move's name followed by an operand, or by a
        modifier word other than `in`, `where` and `marked`. A field that happens to share a move's name (`where
        count is 3`) is not one: nothing that begins an operand follows it."""
        if not self.at_move():
            return False
        kind, text = self.peek(1)
        if kind in ("string", "int", "date", "uri"):
            return True
        if kind == "punct":
            return text in ("(", "[")
        if kind != "name":
            return False
        if text in MODIFIERS:
            return text not in ("in", "where", "marked")
        return text not in _KEYWORDS or text in ("true", "false", "nothing")

    def at_modifier(self) -> bool:
        t = self.peek()
        return t[0] == "name" and t[1] in MODIFIERS

    def at_move(self) -> bool:
        t = self.peek()
        return t[0] == "name" and t[1] in self.moves and not self.at(".", 1)

    def span(self, a: int, b: int) -> str:
        return " ".join(t[1] for t in self.toks[a:b] if t[0] != "end")

    # -- statements --
    def statement(self) -> Stmt:
        st = self._statement()
        if self.at_trailer():
            self.take()
            st.loop = self.for_header()
        elif self.at_member_trailer():
            self.take()
            self.take()
            var = self.name()
            self.expect("=")
            st.member = (var, self.list_member_or_primary())
        if not self.at_end():
            raise ReadError(f"unexpected {self.peek()[1]!r}")
        st.text = self.text
        return st

    def _statement(self) -> Stmt:
        if self.at("emit"):
            self.take()
            slot = None
            if self.peek()[0] == "name" and self.at(":", 1):
                slot = self.name()
                self.take()
            return Stmt("emit", expr=self.expr(), slot=slot)
        if self.at("give"):
            self.take()
            label = None
            if self.peek()[0] == "name" and self.at(":", 1):      # a labelled give (THYM 8.2)
                label = self.name()
                self.take()
            return Stmt("give", expr=self.expr(), slot=label)
        if self.at("let"):
            self.take()
            nm = self.name()
            self.expect("=")
            if self.at("for") and self.at("each", 1):      # a loop that collects (thym 1, THYM 8.1)
                return Stmt("for", loop=self.for_header(), name=nm)
            return Stmt("let", expr=self.expr(), name=nm)
        if self.at("keep") and not self.at_move():
            self.take()
            return Stmt("keep", expr=self.expr())
        if self.at("assert"):
            self.take()
            cond = self.cond()
            msg = None
            if self.at("else"):
                self.take()
                t = self.take()
                if t[0] != "string":
                    raise ReadError("assert ... else takes a string")
                msg = _unquote(t[1])
            return Stmt("assert", cond=cond, message=msg)
        if self.at("if"):
            self.take()
            cond = self.cond()
            if self.at("then"):
                self.take()
            return Stmt("if", cond=cond)
        if self.at("for") and self.at("each", 1):
            return Stmt("for", loop=self.for_header())
        return Stmt("effect", expr=self.expr())

    def for_header(self) -> Loop:
        self.expect("for")
        self.expect("each")
        var = self.name()
        self.expect("in")
        coll = self.call(loop=True) if self.at_move() else self.primary()
        cond = None
        if self.at("where"):
            self.take()
            cond = self.cond()
        return Loop(var, coll, cond)

    # -- expressions --
    def expr(self) -> Any:
        if self.at_move():
            return self.call()
        a = self.i
        p = self.primary()
        if self.at("where"):
            self.take()
            c0 = self.i
            cond = self.cond()
            p = Filter(p, cond, self.span(c0, self.i) or self.span(a, self.i))
        if self.at("marked"):                       # `x marked verified`, short for `mark x as verified` (THYM 4.5)
            self.take()
            p = Call("mark", [p], {"as": self.name()})
        return p

    def call(self, side: bool = False, loop: bool = False) -> Call:
        """A call. On a side of a comparison (`side`) `in` ends it unless the move declares `in`; as a `for each`'s
        collection (`loop`) `where` ends it unless the move declares `where` (THYM 4.5)."""
        move = self.name()
        operands: list = []
        if not (self.at_end() or self.at_modifier() or self.at(")") or self.at("]") or self.at(",")
                or self.at("then") or self.at("else") or (side and self.peek()[1] in _COND_WORDS + ("<", ">", "="))):
            operands.append(self.primary())
            while self.at(",") and not self.at_trailer() and not self.at_member_trailer():
                self.take()
                operands.append(self.primary())
        mods: dict = {}
        while self.at_modifier():
            if side and self.at("in") and move not in self.in_moves:
                break                               # membership, not the modifier (THYM 4.5)
            if loop and self.at("where") and move not in self.where_moves:
                break                               # the loop's where, not the call's (THYM 4.5)
            w = self.take()[1]
            if w == "as":
                mods["as"] = self.word_or_list()
            elif w in ("by", "marked"):
                mods[w] = self.name()
            elif w == "to":
                t = self.take()
                if t[0] != "int":
                    raise ReadError("to takes a number and a unit: to 300 words")
                unit = self.name()
                if unit not in UNITS:
                    raise ReadError(f"to takes words or sentences, not {unit}")
                mods["to"] = Amount(int(t[1]), unit)
            elif w == "where":
                c0 = self.i
                cond = self.cond()
                mods["where"] = (cond, self.span(c0, self.i))
            else:
                mods[w] = self.call(loop=loop) if self.at_move() else self.primary()
        return Call(move, operands, mods)

    def word_or_list(self) -> Any:
        if self.at("["):
            lst = self.primary(in_list=True)
            return [m.value.payload if isinstance(m, Lit) else _name_of(m) for m in lst.items]
        t = self.take()
        if t[0] == "string":
            return _unquote(t[1])
        if t[0] != "name":
            raise ReadError(f"as takes a word or a list of words, not {t[1]!r}")
        return t[1]

    def primary(self, in_list: bool = False) -> Any:
        t = self.take()
        kind, text = t
        if kind == "punct" and text == "(":
            e = self.expr()
            self.expect(")")
            p: Any = e
        elif kind == "punct" and text == "[":
            items = []
            while not self.at("]"):
                if self.at_end():
                    raise ReadError("a list is not closed")
                items.append(self.list_member())
                if self.at(","):
                    self.take()
            self.take()
            p = ListLit(items)
        elif kind == "string":
            p = Lit(Value("string", _unquote(text)))
        elif kind == "int":
            p = Lit(Value("number", int(text)))
        elif kind == "date":
            p = Lit(Value("date", _dt.date.fromisoformat(text)))
        elif kind == "uri":
            p = Lit(Value("string", text))
        elif kind == "name":
            if text in ("true", "false"):
                p = Lit(Value("bool", text == "true"))
            elif text == "nothing":
                p = Lit(NOTHING)
            else:
                p = Name(text)
        else:
            raise ReadError(f"expected a value, found {text or 'the end'!r}")
        while self.at(".") and self.peek(1)[0] == "name":
            self.take()
            p = FieldRead(p, self.name())
        return p

    def list_member(self) -> Any:
        if self.peek()[0] == "name" and not self.at(".", 1) and self.peek()[1] not in ("true", "false", "nothing"):
            return Lit(Value("word", self.take()[1]))
        return self.primary()

    def list_member_or_primary(self) -> Any:
        """A written list's member, as a node's `, for x = <member>` trailer holds it: a bare name is kept as a name,
        and means its binding when one is bound, else the word (THYM 4.5: the binding wins)."""
        return self.primary()

    # -- conditions --
    def cond(self) -> Any:
        items = [self._and()]
        while self.at("or"):
            self.take()
            items.append(self._and())
        return items[0] if len(items) == 1 else BoolOp("or", items)

    def _and(self) -> Any:
        items = [self._not()]
        while self.at("and"):
            self.take()
            items.append(self._not())
        return items[0] if len(items) == 1 else BoolOp("and", items)

    def _not(self) -> Any:
        if self.at("not"):
            self.take()
            return Not(self._not())
        return self._term()

    def side(self) -> Any:
        """One side of a term: a call without parentheses (`thym 1`), or a primary."""
        return self.call(side=True) if self.at_side_call() else self.primary()

    def _term(self) -> Any:
        left = self.side()
        if self.at("is"):
            self.take()
            neg = False
            if self.at("not"):
                self.take()
                neg = True
            return Cmp("is not" if neg else "is", left, self.rhs_word())
        if self.at("in"):
            self.take()
            return Cmp("in", left, self.side())
        for op in ("<", ">", "="):
            if self.at(op):
                self.take()
                return Cmp(op, left, self.side())
        if self.at("has"):
            self.take()
            return Has(left, self.name())
        if self.at("covers"):
            self.take()
            return Covers(left, self.side())
        return Bare(left)

    def rhs_word(self) -> Any:
        if self.at_side_call():
            return self.call(side=True)
        t = self.peek()
        if t[0] == "name" and not self.at(".", 1) and t[1] not in ("true", "false", "nothing"):
            self.take()
            return Lit(Value("word", t[1]))
        return self.primary()


def _unquote(s: str) -> str:
    return s[1:-1].replace('\\"', '"').replace("\\\\", "\\")


def _name_of(e: Any) -> str:
    return e.name if isinstance(e, Name) else str(e)


def read_statement(text: str, moves: set[str] | frozenset[str], in_moves: frozenset[str] = frozenset(),
                   where_moves: frozenset[str] = frozenset()) -> Stmt:
    """One statement, read with the names of the moves in scope (a name that is a move begins a call), of those
    that take an `in` modifier (in a condition, `in` after one of them is the modifier), and of those that take a
    `where` (in a `for each` header, a `where` after a call of one of them is the call's). Raises `ReadError`."""
    return _Reader(text, set(moves), frozenset(in_moves), frozenset(where_moves)).statement()


def read_expression(text: str, moves: set[str] | frozenset[str]) -> Any:
    r = _Reader(text, set(moves))
    e = r.expr()
    if not r.at_end():
        raise ReadError(f"unexpected {r.peek()[1]!r}")
    return e


def _cond_text(c: Any) -> str:
    if isinstance(c, BoolOp):
        return f" {c.op} ".join(_cond_text(x) for x in c.items)
    if isinstance(c, Not):
        return f"not {_cond_text(c.item)}"
    if isinstance(c, Cmp):
        return f"{_expr_text(c.left, True)} {c.op} {_expr_text(c.right, True)}"
    if isinstance(c, Has):
        return f"{_expr_text(c.base, True)} has {c.name}"
    if isinstance(c, Covers):
        return f"{_expr_text(c.left, True)} covers {_expr_text(c.right, True)}"
    if isinstance(c, Bare):
        return _expr_text(c.expr)
    return str(c)


def _expr_text(e: Any, nested: bool = False) -> str:
    """An expression of the reader's as the person would write it; a call inside another, or on a side of a
    comparison (`nested`), in parentheses. Never a Python repr."""
    if isinstance(e, Name):
        return e.name
    if isinstance(e, Lit):
        v = e.value
        if v.type == "string":
            return f'"{v.payload}"'
        if v.type == "bool":
            return "true" if v.payload else "false"
        if v.type == "date" and isinstance(v.payload, _dt.date):
            return v.payload.isoformat()
        return "nothing" if v.is_nothing else str(v.payload)
    if isinstance(e, FieldRead):
        return f"{_expr_text(e.base, True)}.{e.name}"
    if isinstance(e, ListLit):
        return "[" + ", ".join(_expr_text(x) for x in e.items) + "]"
    if isinstance(e, Call):
        out = e.move + ("" if not e.operands else " " + ", ".join(_expr_text(o, True) for o in e.operands))
        for w, a in e.mods.items():
            if w == "where":
                out += f" where {a[1]}"
            elif isinstance(a, list):
                out += f" {w} [" + ", ".join(map(str, a)) + "]"
            elif isinstance(a, Amount):
                out += f" {w} {a.n} {a.unit}"
            elif isinstance(a, str):
                out += f" {w} {a}"
            else:
                out += f" {w} {_expr_text(a, True)}"
        return f"({out})" if nested else out
    if isinstance(e, Filter):
        out = f"{_expr_text(e.base, True)} where {e.text}"
        return f"({out})" if nested else out
    return "the value"


def calls_in(x: Any) -> list[str]:
    """Every move a statement, an expression or a condition calls, nested calls and `marked` included."""
    out: list[str] = []
    if isinstance(x, Stmt):
        for part in (x.expr, x.cond, x.loop):
            out += calls_in(part)
    elif isinstance(x, Loop):
        out += calls_in(x.coll) + calls_in(x.cond)
    elif isinstance(x, Call):
        out.append(x.move)
        for o in x.operands:
            out += calls_in(o)
        for w, a in x.mods.items():
            if w == "marked":
                out.append("mark")
            elif w == "where":
                out += calls_in(a[0])
            elif not isinstance(a, (str, list, Amount)):
                out += calls_in(a)
    elif isinstance(x, (Filter, Cmp, Covers, BoolOp, Not, Bare, Has, FieldRead, ListLit)):
        for v in vars(x).values():
            out += calls_in(v) if not isinstance(v, list) else [m for i in v for m in calls_in(i)]
    return out


def _call_objects(x: Any) -> list[Call]:
    """Every call a statement, an expression or a condition makes, outermost first, as `calls_in` finds them (a
    `marked` modifier's `mark` is not a call written here, and is left out)."""
    out: list[Call] = []
    if isinstance(x, Stmt):
        for part in (x.expr, x.cond, x.loop):
            out += _call_objects(part)
    elif isinstance(x, Loop):
        out += _call_objects(x.coll) + _call_objects(x.cond)
    elif isinstance(x, Call):
        out.append(x)
        for o in x.operands:
            out += _call_objects(o)
        for w, a in x.mods.items():
            if w == "where":
                out += _call_objects(a[0])
            elif w != "marked" and not isinstance(a, (str, list, Amount)):
                out += _call_objects(a)
    elif isinstance(x, (Filter, Cmp, Covers, BoolOp, Not, Bare, Has, FieldRead, ListLit)):
        for v in vars(x).values():
            out += _call_objects(v) if not isinstance(v, list) else [c for i in v for c in _call_objects(i)]
    return out


def _has_covers(c: Any) -> bool:
    if isinstance(c, Covers):
        return True
    if isinstance(c, BoolOp):
        return any(_has_covers(x) for x in c.items)
    if isinstance(c, Not):
        return _has_covers(c.item)
    return False


# ---------------------------------------------------------------------------
# What the plan does not carry: let filters, user moves, the output's name, assert messages
# ---------------------------------------------------------------------------

@dataclass
class UserMove:
    """A `move` block (THYM.md 8.3): its parameters, the type it gives and its body, a list of statements, each
    `("stmt", line, text)`, `("if", line, text, then, else)` or `("for", line, text, body)` (a loop that collects is
    a `for` whose text begins `let <name> =`). In `thym 1`: what it keeps, `(name, against, of)` each, and its
    `depth`."""
    name: str
    params: list
    gives: str | None
    body: list
    keeps: list = field(default_factory=list)
    depth: int | None = None


@dataclass
class ContractBlock:
    """A `contract` block (`thym 1`, THYM 7.5): its parameters and its body of `let`, `assert` and `for each` lines,
    in `UserMove`'s shape."""
    name: str
    params: list
    body: list


_LET = re.compile(r"^let\s+([a-z][a-z0-9-]*)\s*=\s*(.+)$")
_COLLECT = re.compile(r"^let\s+[a-z][a-z0-9-]*\s*=\s*for\s+each\b")
_CONTRACT_HEAD = re.compile(r"^contract\s+([a-z][a-z0-9-]*)\s*\((.*)\)\s*$")
_KEEPS = re.compile(r"^keeps\s+([a-z][a-z0-9-]*)(?:\s+of\s+([a-z][a-z0-9-]*))?(?:\s+against\s+(.+))?$")
_DEPTH = re.compile(r"^depth\s*:\s*(\d+)$")
_WRITTEN = re.compile(r"^(?:let\s+[a-z][a-z0-9-]*\s*=\s*)?for\s+each\s+[a-z][a-z0-9-]*\s+in\s+\[[^\]]*\]$")
_ELSE_MSG = re.compile(r'\belse\s+"((?:[^"\\]|\\.)*)"\s*$')
_HEAD = re.compile(r"^(?:(?:why|must)\s*:|decided\b)")
_MOVE_HEAD = re.compile(r"^move\s+([a-z][a-z0-9-]*)\s*\((.*)\)\s*:\s*(.+)$")


def _params(text: str) -> list[tuple[str, str]]:
    out = []
    for part in text.split(","):
        if ":" in part:
            n, t = part.split(":", 1)
            out.append((n.strip(), t.strip()))
    return out


@dataclass
class ProgramInfo:
    """What the runtime needs of a program beyond its plan: the program's name, `takes` and `gives`; the `let` lines
    whose value is not a call (a filter folds into the node that takes it, THYM.md 11.1, so the plan does not hold
    it); the user moves, with their bodies; and the message of each `assert`, by line."""
    name: str | None = None
    takes: list = field(default_factory=list)
    gives: tuple | None = None
    lets: dict = field(default_factory=dict)
    moves: dict = field(default_factory=dict)
    messages: dict = field(default_factory=dict)
    #: every statement as the person wrote it, by its first line, without indentation or comment (THYM 9)
    statements: dict = field(default_factory=dict)
    #: the grammar version its version line names (`thym 0` or `thym 1`), None when it was not read
    version: int | None = None
    #: every output the program gives, `(name, type)`, in the order its gives line names them (THYM 8.2)
    outputs: list = field(default_factory=list)
    #: every `for each` of the program's body, by its line, as `UserMove.body` holds one (`thym 1`'s loop node)
    loops: dict = field(default_factory=dict)
    #: every `for each` of the program's body: `(line, end, runtime)`, runtime when it walks a collection known only
    #: at run time (a `thym 0` loop nested in one is refused)
    spans: list = field(default_factory=list)
    #: the contract blocks, by name (`thym 1`)
    contracts: dict = field(default_factory=dict)
    #: what the program keeps, `(name, against, of)` each (`thym 1`)
    keeps: list = field(default_factory=list)

    @classmethod
    def from_any(cls, program: Any, name: str | None = None) -> "ProgramInfo":
        """From a program volume mapping (the enumeration, `<name>.thym.cosm`), a `.thym` source text, a path to
        either, or None. `name` chooses the program of a file of several (the first, when None)."""
        if program is None:
            return cls()
        if isinstance(program, ProgramInfo):
            return program
        if isinstance(program, Path) or (isinstance(program, str) and "\n" not in program
                                         and program.endswith((".thym", ".cosm"))):
            p = Path(program)
            text = p.read_text(encoding="utf-8-sig")
            if p.suffix == ".cosm":
                data = mc.yaml_load(text)
                return cls.from_items(data, name) if isinstance(data, dict) else cls()
            return cls.from_source(text, name)
        if isinstance(program, dict):
            return cls.from_items(program, name)
        if isinstance(program, str):
            return cls.from_source(program, name)
        return cls()

    @classmethod
    def from_items(cls, vol: dict, name: str | None = None) -> "ProgramInfo":
        info = cls()
        info.version = _version_of(str(vol.get("front") or ""))
        nodes = [n for n in vol.get("nodes") or [] if isinstance(n, dict)]
        by_id = {n.get("id"): n for n in nodes}
        progs = [n for n in nodes if n.get("type") == "program"]
        prog = next((n for n in progs if n.get("name") == name), None) if name else None
        prog = prog or (progs[0] if progs else None)
        if prog is not None:
            info.name = prog.get("name")
            info.takes = [(t.get("name"), t.get("type")) for t in prog.get("takes") or [] if isinstance(t, dict)]
            gv = [g for g in prog.get("gives") or [] if isinstance(g, dict)]
            info.gives = (gv[0].get("name"), gv[0].get("type")) if gv else None
            info.outputs = [(g.get("name"), g.get("type")) for g in gv]
        for st in nodes:
            if st.get("type") != "step":
                continue
            if isinstance(st.get("line"), int):
                said = st.get("name") or " ".join(strip_comment(x).strip()
                                                  for x in str(st.get("text") or "").split("\n"))
                info.statements.setdefault(st["line"], str(said).strip())
            text = strip_comment(str(st.get("text") or "")).strip()
            if st.get("form") == "let" and not st.get("calls") and not str(st.get("of") or "").startswith("P:move/"):
                mt = _LET.match(text)
                if mt:
                    info.lets.setdefault(mt.group(1), mt.group(2).strip())
            if st.get("form") == "assert":
                mt = _ELSE_MSG.search(text)
                if mt and isinstance(st.get("line"), int):
                    info.messages[st["line"]] = _unquote(f'"{mt.group(1)}"')

        def tree(refs: Any) -> list:
            out = []
            for ref in refs or []:
                st = by_id.get(ref)
                if not isinstance(st, dict):
                    continue
                text = strip_comment(str(st.get("text") or "")).strip()
                form = st.get("form")
                if form == "if":
                    br = st.get("branches") or {}
                    out.append(("if", st.get("line"), text, tree(br.get("then")), tree(br.get("else"))))
                elif form == "for":
                    out.append(("for", st.get("line"), text, tree(st.get("steps"))))
                else:
                    out.append(("stmt", st.get("line"), text))
            return out

        for mv in nodes:
            if mv.get("type") != "move" or not mv.get("name"):
                continue
            params = [(p.get("name"), p.get("type")) for p in mv.get("params") or [] if isinstance(p, dict)]
            gv = [g for g in mv.get("gives") or [] if isinstance(g, dict)]
            info.moves[mv["name"]] = UserMove(mv["name"], params, gv[0].get("type") if gv else None,
                                              tree(mv.get("steps")))
        if isinstance(vol.get("front"), str):
            # the program's loops (and, in thym 1, its contracts, keeps and depths) are read from the file the volume
            # compiles back to
            tops = sorted((n for n in nodes if isinstance(n.get("order"), int) and isinstance(n.get("body"), str)),
                          key=lambda n: n["order"])
            src = cls.from_source(str(vol["front"]) + "".join(n["body"] for n in tops), info.name)
            info.loops, info.spans, info.contracts, info.keeps = src.loops, src.spans, src.contracts, src.keeps
            for name, um in info.moves.items():
                if name in src.moves:
                    um.keeps, um.depth = src.moves[name].keeps, src.moves[name].depth
        return info

    @classmethod
    def from_source(cls, text: str, name: str | None = None) -> "ProgramInfo":
        """Read from the `.thym` text itself, line by line (a statement is one line, THYM.md 4.8); `name` chooses the
        program of a file of several (the first, when None)."""
        info = cls()
        info.version = _version_of(text)
        thym1 = (info.version or 0) >= 1
        stack: list[dict] = []
        prose = False

        def contract_frame(s: str) -> dict:
            mt = _CONTRACT_HEAD.match(s)
            cb = ContractBlock(mt.group(1), _params(mt.group(2)), []) if mt else None
            return {"kind": "contract", "body": [], "contract": cb}

        def owner() -> dict | None:
            """The block a head belongs to: the innermost program, move or contract frame."""
            return next((f for f in reversed(stack) if f["kind"] in ("program", "move", "contract")), None)

        def in_program() -> bool:
            """Whether the statement being read stands in a program's own body (not a move's or a contract's)."""
            return bool(stack) and stack[0]["kind"] == "program" and \
                not any(f["kind"] in ("move", "contract") for f in stack)

        def chosen() -> bool:
            """Whether it stands in the program this reading is for."""
            return bool(stack) and stack[0]["kind"] == "program" and stack[0].get("named", True)

        def current(frame: dict) -> list:
            if frame["kind"] == "if":
                return frame["else"] if frame["in_else"] else frame["then"]
            return frame["body"]

        for ln, raw in enumerate(text.replace("\r\n", "\n").split("\n"), 1):
            s = strip_comment(raw).strip()
            if not s:
                prose = False
                continue
            first = s.split()[0]
            if not stack:
                if first == "program" and len(s.split()) > 1:
                    mine = info.name is None and (name is None or s.split()[1] == name)
                    if mine:
                        info.name = s.split()[1]
                    stack.append({"kind": "program", "body": [], "named": mine})
                elif first == "move":
                    mt = _MOVE_HEAD.match(s)
                    um = UserMove(mt.group(1), _params(mt.group(2)), mt.group(3).strip(), []) if mt else None
                    stack.append({"kind": "move", "body": [], "move": um})
                elif first == "contract" and thym1:
                    stack.append(contract_frame(s))
                elif first in ("morph", "context"):
                    stack.append({"kind": "skip"})
                prose = False
                continue
            top = stack[-1]
            if top["kind"] == "skip":
                if s == "end":
                    stack.pop()
                continue
            if _HEAD.match(s):
                prose = True
                continue
            if prose and first not in ("takes", "gives", "end") and not (thym1 and first in ("keeps", "depth")):
                continue
            prose = False
            if thym1 and first == "keeps" and _KEEPS.match(s):
                mt = _KEEPS.match(s)
                kept = (mt.group(1), [a.strip() for a in (mt.group(3) or "").split(",") if a.strip()], mt.group(2))
                f = owner()
                if f is not None and f["kind"] == "program" and f.get("named", True):
                    info.keeps.append(kept)
                elif f is not None and f["kind"] == "move" and f.get("move") is not None:
                    f["move"].keeps.append(kept)
                continue
            if thym1 and _DEPTH.match(s):
                f = owner()
                if f is not None and f["kind"] == "move" and f.get("move") is not None:
                    f["move"].depth = int(_DEPTH.match(s).group(1))
                continue
            if thym1 and first == "contract" and _CONTRACT_HEAD.match(s):
                stack.append(contract_frame(s))
                continue
            if first == "takes":
                if top["kind"] == "program" and chosen():
                    info.takes = _params(s[len("takes"):])
                continue
            if first == "gives":
                if top["kind"] == "program" and chosen():
                    g = _params(s[len("gives"):])
                    info.gives = g[0] if g else None
                    info.outputs = list(g)
                continue
            if first == "move":
                mt = _MOVE_HEAD.match(s)
                um = UserMove(mt.group(1), _params(mt.group(2)), mt.group(3).strip(), []) if mt else None
                stack.append({"kind": "move", "body": [], "move": um})
                continue
            if s == "end":
                f = stack.pop()
                if f["kind"] == "move" and f.get("move") is not None:
                    f["move"].body = f["body"]
                    info.moves[f["move"].name] = f["move"]
                elif f["kind"] == "contract" and f.get("contract") is not None:
                    f["contract"].body = f["body"]
                    info.contracts[f["contract"].name] = f["contract"]
                elif f["kind"] == "if" and stack:
                    current(stack[-1]).append(("if", f["line"], f["text"], f["then"], f["else"]))
                elif f["kind"] == "for" and stack:
                    part = ("for", f["line"], f["text"], f["body"])
                    current(stack[-1]).append(part)
                    if f.get("program"):
                        info.loops[f["line"]] = part
                        info.spans.append((f["line"], ln, not _WRITTEN.match(f["text"])))
                continue
            if s == "else" and top["kind"] == "if":
                top["in_else"] = True
                continue
            info.statements.setdefault(ln, s)
            if first == "if":
                stack.append({"kind": "if", "line": ln, "text": s, "then": [], "else": [], "in_else": False})
                continue
            if first == "for" or (thym1 and _COLLECT.match(s)):
                stack.append({"kind": "for", "line": ln, "text": s, "body": [], "program": in_program()})
                continue
            current(top).append(("stmt", ln, s))
            mt = _LET.match(s)
            if mt and in_program() and chosen():      # a move's lets are its own (THYM 5.4), and a program's
                info.lets.setdefault(mt.group(1), mt.group(2).strip())
            if first == "assert":
                mm = _ELSE_MSG.search(s)
                if mm:
                    info.messages[ln] = _unquote(f'"{mm.group(1)}"')
        return info


def _version_of(text: str) -> int | None:
    """The number a program's version line names (its first line that is neither blank nor a comment)."""
    for raw in text.replace("\r\n", "\n").split("\n"):
        s = strip_comment(raw).strip().lstrip("\ufeff")
        if not s:
            continue
        mt = re.fullmatch(r"thym\s+(\d+)", s)
        return int(mt.group(1)) if mt else None
    return None


# ---------------------------------------------------------------------------
# The person's words (THYM 9)
# ---------------------------------------------------------------------------

_TRAILER = re.compile(r", for (?:each [a-z][a-z0-9-]* in .*|[a-z][a-z0-9-]* = .*)$")
_TEMP = re.compile(r"\bt(\d+)\b")
_ORDINALS = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth",
             "eleventh", "twelfth", "thirteenth", "fourteenth", "fifteenth", "sixteenth", "seventeenth",
             "eighteenth", "nineteenth", "twentieth")
_RUNTIME_FAULT = "a fault of the runtime, not of the program"


def _cut(text: str, n: int = 60) -> str:
    """A statement as a refusal quotes it: one line, at most `n` characters, cut with "…"."""
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[:n - 1].rstrip() + "…"


def _ordinal(k: int) -> str:
    return f"the {_ORDINALS[k - 1]} member" if 1 <= k <= len(_ORDINALS) else f"member {k}"


def describe(v: Any) -> str:
    """A value as a refusal names it, in the program's terms: a number, a word or a date as itself, a string quoted,
    an item by its id, anything else by its type. Never as Python prints it."""
    if not isinstance(v, Value):
        return "a value"
    if v.is_nothing:
        return "nothing"
    if v.type == "bool":
        return "true" if v.payload else "false"
    if v.type in ("number", "word"):
        return str(v.payload)
    if v.type == "date" and isinstance(v.payload, _dt.date):
        return v.payload.isoformat()
    if v.type == "string" and isinstance(v.payload, str):
        return '"' + _cut(v.payload, 40) + '"'
    if v.type == "list":
        n = len(v.payload or [])
        return f"a list of {n}" if n != 1 else "a list of one"
    if v.type == "item":
        return item_id(v) or "an item"
    a = "an" if v.type[:1] in "aeiou" else "a"
    return f"{a} {v.type}"


# ---------------------------------------------------------------------------
# The context a move sees
# ---------------------------------------------------------------------------

@dataclass
class MoveContext:
    """What a move implementation is given beside its operands (the calling convention is in `registry`)."""
    run: str
    node: dict
    decls: dict
    coprocessor: Any
    rules: bool
    now: _dt.datetime
    emitted: list
    slots: dict
    withheld: dict
    inputs_root: Path
    root: Path
    stage: Path
    program: ProgramInfo | None = None
    trace_fn: Callable[[], dict] | None = field(default=None, repr=False)
    #: enough's engines, by name, as the host registers them (`enough.thym_host.engines()`); the package imports none.
    #: In a recorded run each engine call is recorded, and in a replay answered from its record (`engines.py`).
    engines: Any = field(default_factory=dict, repr=False)
    #: the node's call counter (`engines.CallCounter`): the keys of its requests, its engines' model calls and its
    #: engine calls, so that none collide (THYM.md 12.4); `EngineAdapter` takes its keys here
    calls: Any = field(default=None, repr=False)
    #: a model-backed move that asks more than once (a request per file, `tell f as code`) asks through `ask`; when
    #: what it gives then fails its contract, the runtime calls it again, within the node's attempts, with the failed
    #: verdicts in `failed`, what it gave last in `previous` and the attempt's number in `attempt` (1 the first time),
    #: so that it may ask again for only the parts the failures name
    ask_fn: Callable[..., dict] | None = field(default=None, repr=False)
    failed: list = field(default_factory=list)
    previous: Any = None
    attempt: int = 1

    def ask(self, contract: dict, inputs: dict, *, budget: dict | None = None) -> dict:
        """One model request the move makes itself (THYM 12.2, 12.4): `contract` holds `schema` and `repair` as a
        `Request`'s does, `inputs` the values the model reads, by name. `repair` is the list of narrow repairs the
        move allows, or the coprocessor's mapping `{allowed: [...], failed: [...]}`, whose `failed` names what the
        move itself could not take in its last answer (`{name, why}` each, or the reason as a string), so that a
        re-ask says why and is never the same request again. The request is keyed on the node's counter, recorded
        and replayed as every request is, carries every failed verdict the model should hear of in
        `repair.failed` (a kept contract's, the runtime's verdicts on this move's last output, then the move's
        own), and counts toward the run's ceiling of calls. Returns the candidate (`output`, `engine`, `tokens`,
        …); a refusal (a model the run may not ask, the ceiling reached, a replay that does not match) stops the
        move."""
        if self.ask_fn is None:
            raise _Stop(Refusal("run", "asks", "this move asked a model, and the run has none to ask"))
        return self.ask_fn(contract, inputs, budget)

    def withhold(self, *items: Any) -> None:
        """Mark items withheld from the projection (THYM.md 18): values (items, or a list of them) or ids. An item is
        held by its own key (`values.item_key`: its id qualified with its part), so withholding one item never takes
        a twin that shares its id in another part; an id given as a word is held as that word (`values.is_withheld`)."""
        for x in items:
            if isinstance(x, (list, tuple)):
                self.withhold(*x)
            elif isinstance(x, Value) and x.type == "list":
                self.withhold(*(x.payload or []))
            elif isinstance(x, Value):
                key = item_key(x)
                if key:
                    self.withheld[key] = x
            elif isinstance(x, str) and x:
                self.withheld[x] = NOTHING

    def decl(self, name: str) -> Any:
        return self.decls.get(name)

    def trace(self) -> Value:
        """The run's trace so far (the move `trace`, THYM.md 6.3)."""
        return Value("trace", self.trace_fn() if self.trace_fn else {})


# ---------------------------------------------------------------------------
# The walk
# ---------------------------------------------------------------------------

class _Stop(Exception):
    """A refusal on its way out of a node. `worded` when its message already names its statement (THYM 9), so that
    the node does not name it again; `fault` the detail of a fault of the runtime, which the record keeps."""

    def __init__(self, refusal: Refusal, *, worded: bool = False, fault: str | None = None) -> None:
        super().__init__(str(refusal))
        self.refusal = refusal
        self.worded = worded
        self.fault = fault


@dataclass
class _Scope:
    vars: Any
    program: bool = True

    def child(self, names: dict) -> "_Scope":
        return _Scope(ChainMap(dict(names), self.vars), self.program)


@dataclass
class _NodeState:
    node: dict
    engine: str = "code"
    attempts: int = 0
    tokens: int = 0
    checks: list = field(default_factory=list)
    outputs: list = field(default_factory=list)
    calls: CallCounter | None = None
    state: str | None = None
    tries: list = field(default_factory=list)      # each attempt that failed: {attempt, failed: [{name, why}]}
    passing: str | None = None                     # the pass a loop is on, in the person's terms: `for o = M:aim/x`
    fault: str | None = None                       # a fault of the runtime: its detail, for the record only
    passes: int | None = None                      # a loop run as one node: how many passes it made (thym 1)

    def __post_init__(self) -> None:
        if self.calls is None:
            self.calls = CallCounter(node_number(self.node.get("id")))


def new_run_id(now: _dt.datetime | None = None) -> str:
    """A run id in local time, as file names take it: `2026-11-01-1042-7f3a`."""
    t = (now or _dt.datetime.now()).astimezone()
    return f"{t:%Y-%m-%d-%H%M}-{secrets.token_hex(2)}"


def plan_parts(plan: dict) -> tuple[dict, list[dict]]:
    """A plan volume's `R:plan` item and its `R:node` items, in plan order."""
    rows = [n for n in plan.get("nodes") or [] if isinstance(n, dict)]
    head = next((n for n in rows if n.get("type") == "plan"), {})
    return head, [n for n in rows if n.get("type") == "node"]


def topo_order(nodes: list[dict]) -> list[dict] | Refusal:
    """The nodes in a topological order of `after` and of the names they take from each other; plan order breaks
    ties, so a plan already in evaluation order runs as written."""
    idx = {n.get("id"): i for i, n in enumerate(nodes)}
    givers: dict[str, list] = {}
    for n in nodes:
        g = n.get("gives")
        if isinstance(g, str):
            givers.setdefault(g, []).append(n.get("id"))
    deps: dict[Any, set] = {}
    for n in nodes:
        d = {a for a in n.get("after") or [] if a in idx}
        for t in n.get("takes") or []:
            d |= {g for g in givers.get(t, []) if g != n.get("id")}
        deps[n.get("id")] = d
    waiting = {k: set(v) for k, v in deps.items()}
    ready = [idx[k] for k, v in waiting.items() if not v]
    heapq.heapify(ready)
    out: list[dict] = []
    while ready:
        i = heapq.heappop(ready)
        nid = nodes[i].get("id")
        out.append(nodes[i])
        for k, v in waiting.items():
            if nid in v:
                v.discard(nid)
                if not v:
                    heapq.heappush(ready, idx[k])
    if len(out) != len(nodes):
        done = {o.get("id") for o in out}
        lines = sorted({n.get("line") for n in nodes if n.get("id") not in done and isinstance(n.get("line"), int)})
        where = f" (the statements at lines {', '.join(map(str, lines))})" if lines else ""
        return Refusal("plan", "plan-acyclic", f"the plan's steps wait on each other{where}, so none of them can run "
                                               "first: plan the program again")
    return out


def _eq(a: Any, b: Any) -> bool:
    if isinstance(a, Value) or isinstance(b, Value):
        return isinstance(a, Value) and isinstance(b, Value) and a.sha256 == b.sha256
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    return a == b


def _plain_mods(mods: dict) -> dict:
    out: dict = {}
    for k, v in mods.items():
        if isinstance(v, Amount):
            out[k] = v.to_dict()
        elif isinstance(v, Where):
            out[k] = v.text
        else:
            out[k] = v
    return out


class _Run:
    def __init__(self, plan: dict, **kw: Any) -> None:
        self.plan = plan
        self.inputs_root = Path(kw["inputs_root"]).absolute()
        self.root = Path(kw["root"] or default_root()).absolute()
        self.coproc = kw["coprocessor"] if kw["coprocessor"] is not None else RefusingCoprocessor()
        self.rules = bool(kw["rules"])
        self.agent_free = bool(kw["agent_free"])
        self.preflight = kw["preflight"]
        self.program = kw["program"]
        self.moves = kw["moves"] if kw["moves"] is not None else _registry.MOVES
        self.checks = kw["checks"] if kw["checks"] is not None else _checks.CHECKS
        self.decls = kw["decls"]
        self.environment = kw["environment"] or {}
        self.destination = Path(kw["destination"]) if kw["destination"] else None
        self.record = bool(kw["record"])
        self.run_id = kw["run_id"]
        self.made_run = kw["made_run"]
        self.now = kw["now"]
        self.replay_of = kw["replay_of"]
        self.progress = kw.get("progress")
        self.should_stop = kw.get("should_stop")
        self.engines_given = kw.get("engines")
        self.engines: Any = {}
        self.env: dict[str, Value] = {}
        self.inputs: dict[str, Value] = {}
        self.input_paths: dict[str, str] = {}
        self.emitted: list[Value] = []
        self.slots: dict[str, Value] = {}
        self.withheld: dict[str, Value] = {}
        self.if_results: dict[Any, bool] = {}
        self.skipped: set = set()
        self.records: list[dict] = []
        self.cur: _NodeState | None = None
        self._let_busy: set[str] = set()
        self._move_stack: list[str] = []
        self._sides: list[tuple[str, Value]] = []      # the sides the last comparison compared, for an assert's words
        self.in_moves: frozenset[str] = frozenset()
        self.where_moves: frozenset[str] = frozenset()
        #: a replay's snapshots of the folders the recorded run took (its `inputs/`), read in place of the disk
        self.snapshots = Path(kw["snapshots"]) if kw.get("snapshots") else None
        self.folders: dict[str, Value] = {}
        self._keeping: list[list[Value]] = []          # the lists the loops that collect are making, innermost last
        self._passes: list[str] = []                   # the passes of a loop node's loops, innermost last
        self._repairs: list[list[dict]] = []           # failed kept contracts every model request now carries
        self._emit_k = 0
        self.ceiling: int | None = kw.get("calls")    # the run's ceiling on its model requests (`--calls`)
        self.requests = 0
        self._asking: list[dict] = []                  # the moves asking through `ctx.ask`, innermost last

    # -- plan time ------------------------------------------------------------------------------------------------

    def _prepare(self) -> Refusal | None:
        self.head, nodes = plan_parts(self.plan)
        if not nodes:
            return Refusal("plan", "plan", "not a plan: it holds no R:node items")
        order = topo_order(nodes)
        if isinstance(order, Refusal):
            return order
        self.nodes, self.order = nodes, order
        self.by_id = {n.get("id"): n for n in nodes}
        if self.decls is None:
            self.decls = _registry.declarations()
        self.load_problems = _registry.load_all(self.decls)
        try:
            want = (self.plan.get("program") or {}).get("name") if isinstance(self.plan.get("program"), dict) else None
            self.info = ProgramInfo.from_any(self.program, want)
        except OSError as e:
            why = e.strerror or "the system would not open it"
            return Refusal("plan", "program", f"the program could not be read: {why}")
        except ValueError:
            return Refusal("plan", "program", "the program could not be read: it is neither a .thym file nor a program "
                                              "volume")
        # the moves a program of its version sees (THYM 4.9); a plan run without its program sees every move whole
        self.decls = _views(self.decls, self.info.version if self.info.version is not None else 1)
        self.in_moves = frozenset(n for n, d in self.decls.items() if "in" in (decl_get(d, "modifiers") or {}))
        self.where_moves = frozenset(n for n, d in self.decls.items() if "where" in (decl_get(d, "modifiers") or {}))
        self.move_names = frozenset(set(self.decls) | set(self.info.moves))
        est = self.plan.get("estimate") if isinstance(self.plan.get("estimate"), dict) else {}
        self.largest_prompt = int(self.head.get("largest_prompt") or est.get("largest_prompt") or 0)
        return self._environment()

    def _body_moves(self, name: str, seen: frozenset[str] = frozenset()) -> set[str]:
        """The declared moves a user move calls, through the user moves it calls (THYM.md 8.3)."""
        um = self.info.moves.get(name)
        if um is None or name in seen:
            return set()
        return self._part_moves(um.body, seen | {name})

    def _part_moves(self, body: list, seen: frozenset[str] = frozenset()) -> set[str]:
        """The declared moves a body's statements call, through the user moves they call."""
        out: set[str] = set()
        for part in body:
            try:
                st = read_statement(part[2], self.move_names, self.in_moves, self.where_moves)
            except ReadError:
                continue
            for m in calls_in(st):
                if m in self.info.moves:
                    out.update(self._body_moves(m, seen))
                else:
                    out.add(m)
            for sub in part[3:]:
                if isinstance(sub, list):
                    out.update(self._part_moves(sub, seen))
        return out

    def _moves_of(self, node: dict) -> list[str]:
        m = node.get("move")
        if m == "for":                                 # a loop node: every move its header and its body call
            part = self.info.loops.get(node.get("line"))
            return sorted(self._part_moves([part])) if part is not None else []
        return sorted(self._body_moves(m)) if m in self.info.moves else [m]

    def _move_asks(self, name: str) -> bool:
        """Whether a user move asks: any declared move its body calls, through the user moves it calls, asks."""
        return any(decl_get(self.decls.get(m), "asks") is True for m in self._body_moves(name))

    def _route(self) -> str:
        """The route a model would be asked on, as the host named it in the environment (THYM 23.1); `local` when
        it named none (the runtime's own CLI, agent-free)."""
        r = self.environment.get("route")
        return r if isinstance(r, str) and r in ("local", "cloud") else "local"

    def _unscaffolded(self, n: dict) -> bool:
        """Whether a node that asks makes a call that asks and has no rules scaffold (THYM 19), each call's scaffold
        chosen by the call where the plan can tell it (`scaffold-when`, THYM 17.6): a rule that says `none` leaves
        the call with none, and `--rules` refuses it here, at plan time, not when it runs."""
        return any(decl_get(self.decls.get(m), "asks") is True and not self._call_scaffold(m, c, params)
                   for m, c, params in self._calls_of(n))

    def _calls_of(self, n: dict) -> list[tuple[str, Any, dict]]:
        """The declared moves a node calls, each `(move, call, types)`: the call as read (None when it cannot be
        read) and the types of the names it is called with that the program states (a user move's parameters)."""
        m = n.get("move")
        if m == "for":
            part = self.info.loops.get(n.get("line"))
            return self._part_calls([part], {}) if part is not None else []
        if m in self.info.moves:
            return self._move_calls(m, frozenset())
        try:
            st = read_statement(_TRAILER.sub("", str(n.get("name") or "")), self.move_names, self.in_moves,
                                self.where_moves)
        except ReadError:
            return [(m, None, {})]
        own = next((c for c in _call_objects(st) if c.move == m), None)
        return [(m, own, {})]

    def _move_calls(self, name: str, seen: frozenset[str]) -> list[tuple[str, Any, dict]]:
        um = self.info.moves.get(name)
        if um is None or name in seen:
            return []
        return self._part_calls(um.body, dict(um.params), seen | {name})

    def _part_calls(self, body: list, types: dict, seen: frozenset[str] = frozenset()) -> list[tuple[str, Any, dict]]:
        out: list[tuple[str, Any, dict]] = []
        for part in body:
            try:
                st = read_statement(part[2], self.move_names, self.in_moves, self.where_moves)
            except ReadError:
                continue
            for c in _call_objects(st):
                if c.move in self.info.moves:
                    out += self._move_calls(c.move, seen)
                else:
                    out.append((c.move, c, types))
            for sub in part[3:]:
                if isinstance(sub, list):
                    out += self._part_calls(sub, types, seen)
        return out

    def _call_scaffold(self, m: str, c: Any, types: dict) -> Any:
        """The scaffold a call of the declared move `m` runs under `--rules`: its declaration's, or the one its
        `scaffold-when` chooses from the call's `as` word or its first operand's type, where the plan can tell
        that type; None when it has none."""
        decl = self.decls.get(m)
        if c is None or not any(decl_get(decl, k) for k in ("scaffold-when", "scaffold_when")):
            return decl_get(decl, "scaffold")
        try:
            from enough.thym import declarations as _decls     # the compiler's reader of the rules
        except ImportError:
            return decl_get(decl, "scaffold")
        w = c.mods.get("as")
        first = self._static_type(c.operands[0], types) if c.operands else None
        return _decls.chosen(decl, as_word=w if isinstance(w, (str, list)) else None, first_type=first)["scaffold"]

    def _static_type(self, e: Any, types: dict) -> str | None:
        """The type of an operand where the plan says it without running: a name the program types (an input, a
        user move's parameter), a name a node gives whose move gives one type, a literal, a filter of one of
        these; None otherwise."""
        if isinstance(e, Lit):
            return e.value.type
        if isinstance(e, Filter):
            return self._static_type(e.base, types)
        if not isinstance(e, Name):
            return None
        if isinstance(types.get(e.name), str):
            return types[e.name]
        for spec in self.plan.get("inputs") or []:
            if isinstance(spec, dict) and spec.get("name") == e.name and isinstance(spec.get("type"), str):
                return spec["type"]
        giver = next((n for n in self.nodes if n.get("gives") == e.name), None)
        if giver is None or giver.get("move") in self.info.moves or giver.get("move") == "for":
            return None
        gives = _alternatives(decl_get(self.decls.get(giver.get("move")), "gives"))
        return gives[0] if len(gives) == 1 and not gives[0].startswith("same-as-") else None

    def _environment(self) -> Refusal | None:
        asks = [n for n in self.nodes if n.get("asks") is True]
        if asks and (self.agent_free or self.rules):
            blocked = asks
            if self.rules:
                blocked = [n for n in asks if self._unscaffolded(n)]
            if blocked:
                k = len(blocked)
                many = f"{k} step{'s' if k != 1 else ''} ask{'' if k != 1 else 's'} a model"
                if self.agent_free:
                    # the host's words (THYM 19; the conductor's ruling L11): the route, then "the first" and the
                    # statement as written, in backticks when the program is to hand
                    many += f" on the {self._route()} route"
                    if self.rules:
                        many += f" and {'have' if k != 1 else 'has'} no scaffold"
                    line = blocked[0].get("line")
                    stmt = self.info.statements.get(line) if isinstance(line, int) else None
                    named = f"`{_cut(stmt)}`" if stmt else self._said(blocked[0])
                    where = f" (line {line})" if isinstance(line, int) else ""
                    return Refusal("plan", "agent-free", f"{many}, the first {named}{where}; agent-free is on",
                                   line=line)
                many += f" and {'have' if k != 1 else 'has'} no scaffold"
                first = f", the first {self._at(blocked[0])}" if k > 1 else f": {self._at(blocked[0])}"
                return Refusal("plan", "rules", f"{many}{first}; --rules runs no model", line=blocked[0].get("line"))
        for spec in self.plan.get("inputs") or []:
            if not isinstance(spec, dict):
                continue
            name = str(spec.get("name"))
            snap = None
            if spec.get("type") == "folder" and self.snapshots is not None:
                snap = self.snapshots / f"{name}.folder.cosm"
                if not snap.is_file():
                    return Refusal("plan", "input", f"input {name}: the recorded run kept no snapshot of "
                                                    f"{spec.get('path') or name}, so it cannot be replayed")
            v = load_input(spec, self.inputs_root, snapshot=snap)
            if isinstance(v, Refusal):
                return v
            self.inputs[name] = v
            if v.type == "folder":
                self.folders[name] = v
            self.input_paths[name] = posix_path(spec.get("path"))
        if (self.preflight is not None and asks and not self.rules
                and not isinstance(self.coproc, (RefusingCoprocessor, ReplayCoprocessor))):
            try:
                r = self.preflight(self.plan)
            except Exception:  # noqa: BLE001 - a preflight that cannot measure leaves the size unknown, as chat's does
                r = None
            if isinstance(r, Refusal):
                return r
        for n in self.nodes:
            if n.get("move") in ("if", "assert", "emit", "give", "let"):
                continue
            line = n.get("line")
            for m in self._moves_of(n):
                decl = self.decls.get(m)
                if decl is None:
                    if self.program is None:
                        prog = f"{(self.plan.get('program') or {}).get('name') or self.info.name or 'its program'}.thym"
                        return Refusal("plan", "unknown-move", f"{self._at(n)}: {m} is no declared move, so it is a "
                                       f"move of {prog}, and this run has only the plan; run it with the program "
                                       f"beside the plan (--program {prog})", line=line)
                    return Refusal("plan", "unknown-move", f"{self._at(n)}: the move {m} is not declared, and the "
                                   "program defines no move of that name", line=line)
                if decl_get(decl, "asks") is True and self.rules:
                    if self.moves.scaffold(decl) is None:
                        return Refusal("plan", "move", f"{self._at(n)}: the scaffold of {m} "
                                                       f"({decl_get(decl, 'scaffold')}) has no implementation here",
                                       line=line)
                elif self.moves.lookup(m) is None:
                    why = next((p.split(": ", 1)[1] for p in self.load_problems if p.startswith(f"{m}: ")), None)
                    return Refusal("plan", "move", f"{self._at(n)}: the move {m} has no implementation here"
                                                   + (f" ({why})" if why else ""), line=line)
        return None

    # -- the run --------------------------------------------------------------------------------------------------

    def go(self) -> Trace | Refusal:
        r = self._prepare()
        if r is not None:
            return r
        runs = _trace.runs_dir(self.root)
        runs.mkdir(parents=True, exist_ok=True)
        start = _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0)
        self.started = self.now or start          # the clock moves see; a replay's is the recorded run's
        rid = self.run_id or new_run_id()
        while (runs / rid).exists():
            if self.run_id:
                return Refusal("run", "run", f"a run {rid} is already under {runs}")
            rid = new_run_id()
        self.run_id = rid
        self.made_run = self.made_run or rid
        self.dir = runs / rid
        self.stage = self.dir / "stage"
        self.stage.mkdir(parents=True)
        plan_bytes = canonical(self.plan)
        write_atomic(self.dir / f"{rid}.plan.cosm", plan_bytes)
        self._keep_program()
        for name, v in self.folders.items():          # a run snapshots every folder it takes (THYM 20.3)
            write_snapshot(v, self.dir / "inputs" / f"{name}.folder.cosm", id=f"thym/{rid}.{name}")
        if self.record and not isinstance(self.coproc, (ReplayCoprocessor, RefusingCoprocessor, RecordingCoprocessor)):
            self.coproc = RecordingCoprocessor(self.coproc, self.dir)
        recorded_engines = self._engines()
        env = {"enough": "unknown", "model": "none", "context": 0, "agent_free": self.agent_free,
               "memory_band": "unknown"}
        model_runs = (any(n.get("asks") is True for n in self.nodes) and not self.rules and not self.agent_free
                      and not isinstance(self.coproc, (RefusingCoprocessor, ReplayCoprocessor)))
        for k, v in self.environment.items():
            if callable(v):                       # read only when a model runs (the host's window: THYM.md 12.3)
                try:
                    v = v() if model_runs else None
                except Exception:  # noqa: BLE001 - a value that cannot be read is unknown, as a size is
                    v = None
            if v is not None:
                env[k] = v
        prog = self.plan.get("program") if isinstance(self.plan.get("program"), dict) else {}
        self.trace = Trace(run_id=rid, dir=self.dir, program={"name": prog.get("name") or self.info.name,
                                                               "sha256": prog.get("sha256")},
                           plan_sha256=sha256_bytes(plan_bytes), environment=env, started=self.started,
                           nodes=[n for n in self.nodes],
                           inputs=[{"name": k, "path": p} for k, p in self.input_paths.items()],
                           extra={"inputs_root": str(self.inputs_root), "rules": self.rules,
                                  "replay_of": self.replay_of,
                                  "made_run": self.made_run if self.made_run != rid else None,
                                  "engines": recorded_engines})
        self.env.update(self.inputs)
        self.output_names = self._output_names()
        refusal: Refusal | None = None
        stopped: str | None = None
        total = len(self.order)
        for i, node in enumerate(self.order, 1):
            if self.should_stop is not None and self.should_stop():
                refusal = Refusal("run", "cancelled", f"the run was cancelled before {self._at(node)}; nothing landed",
                                  line=node.get("line"))
                stopped = f"R:record/{node_number(node.get('id'))}"
                break
            self._tell(i, total, node, "running")
            try:
                refusal = self._node(node)
            except _Stop as s:                    # pragma: no cover - _node catches its own
                refusal = s.refusal
            except Exception as e:  # noqa: BLE001 - a runtime fault refuses the run with its words; never half-lands
                refusal = Refusal("run", "runtime", f"{self._at(node)}: the runtime failed while running this "
                                                    f"statement, {_RUNTIME_FAULT}; nothing landed",
                                  line=node.get("line"))
                if self.cur is not None:
                    self.cur.fault = f"{type(e).__name__}: {e}"           # the record keeps it, for the maintainer
                self._record(node, refusal)
            self._tell(i, total, node, "refused" if refusal is not None else
                       ("skipped" if node.get("id") in self.skipped else "done"))
            if refusal is not None:
                stopped = f"R:record/{node_number(node.get('id'))}"
                break
        if refusal is None:
            refusal = self._land()
            if refusal is not None:
                stopped = self.records[-1]["id"] if self.records else None
        self.trace.records = self.records
        self.trace.ended = _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0)
        if refusal is None:
            self.trace.outcome = "landed"
        else:
            self.trace.outcome, self.trace.refusal, self.trace.stopped_at = "refused", refusal, stopped
            shutil.rmtree(self.stage, ignore_errors=True)
        _trace.write(self.trace)
        return self.trace

    def _tell(self, i: int, total: int, node: dict, state: str) -> None:
        """Report a node's progress to the caller's `progress` hook: `{node, of, name, move, state}`."""
        if self.progress is None:
            return
        try:
            self.progress({"node": i, "of": total, "name": str(node.get("name") or node.get("move") or ""),
                           "move": str(node.get("move") or ""), "state": state})
        except Exception:  # noqa: BLE001 - a progress hook never stops a run
            pass

    def _engines(self) -> list[str] | None:
        """`ctx.engines` for this run: a replay of a run that recorded its engine calls answers them from the record
        and runs no engine; a recorded run records every engine call; any other run uses the engines as given. The
        names the trace records (its root item's `engines`), or None when the calls are not recorded."""
        given = self.engines_given

        def counter() -> CallCounter | None:
            return self.cur.calls if self.cur is not None else None
        if isinstance(given, Replaying):
            self.engines = given.bind(counter, self.inputs_root)
            return given.names()
        given = dict(given or {})
        if self.record and not isinstance(self.coproc, ReplayCoprocessor):
            self.engines = Recording(given, self.dir, counter, inputs_root=self.inputs_root)
            return sorted(given)
        self.engines = given
        return None

    def _keep_program(self) -> None:
        p = self.program
        name = self.info.name or "program"
        if isinstance(p, dict):
            write_atomic(self.dir / f"{name}.thym.cosm", canonical(p))
        elif isinstance(p, Path) or (isinstance(p, str) and "\n" not in p and p.endswith((".thym", ".cosm"))):
            src = Path(p)
            if src.is_file():
                write_atomic(self.dir / (f"{name}.thym.cosm" if src.suffix == ".cosm" else f"{name}.thym"),
                             src.read_bytes())
        elif isinstance(p, str):
            write_atomic(self.dir / f"{name}.thym", p.encode("utf-8"))

    def _output_names(self) -> list[str]:
        """Every output the program gives (THYM 8.2), from the program; without it, the plan's one output."""
        names = [str(o[0]) for o in self.info.outputs if o and o[0]]
        if names:
            return names
        one = self._output_name()
        return [one] if one else []

    def _output_name(self) -> str | None:
        if self.info.gives and self.info.gives[0]:
            return str(self.info.gives[0])
        taken = {t for n in self.nodes for t in n.get("takes") or []}
        given = [n.get("gives") for n in self.nodes if isinstance(n.get("gives"), str)]
        cands = [g for g in given if not re.fullmatch(r"t\d+", g) and g not in taken]
        return cands[-1] if cands else None

    # -- one node -------------------------------------------------------------------------------------------------

    def _governing_if(self, node: dict) -> Any:
        seen, queue = set(), list(node.get("after") or [])
        while queue:
            nid = queue.pop(0)
            if nid in seen or nid not in self.by_id:
                continue
            seen.add(nid)
            n = self.by_id[nid]
            if n.get("move") == "if":
                return nid
            queue.extend(n.get("after") or [])
        return None

    def _branch_taken(self, node: dict) -> bool:
        g = self._governing_if(node)
        if g is None:
            return True
        if g in self.skipped or g not in self.if_results:
            return False
        return (node.get("branch") == "then") == self.if_results[g]

    def _node(self, node: dict) -> Refusal | None:
        nid = node.get("id")
        self.cur = _NodeState(node)
        self._t0 = time.monotonic()
        if node.get("branch") in ("then", "else") and not self._branch_taken(node):
            self.skipped.add(nid)
            self.cur.engine = "skipped"
            self._record(node)
            return None
        nested = self._nested_in_runtime(node)
        if nested is not None:
            inner, outer = nested
            r = Refusal("run", "loop", f"{self._at(node)}: this statement stands in the for each at line {inner}, "
                                       f"inside the for each at line {outer}, and {self._loop_reason()}, so the inner "
                                       f"loop does not run once for each pass of the outer one; {self._loop_fix()}",
                        line=node.get("line"))
            self._record(node, r)
            return r
        if node.get("move") == "for":
            return self._loop_node(node)
        text = str(node.get("name") or "").strip() or " ".join([str(node.get("move"))] + list(node.get("takes") or []))
        try:
            st = read_statement(text, self.move_names, self.in_moves, self.where_moves)
        except ReadError as e:
            self.cur.fault = f"{text}: {e}"
            r = Refusal("run", "parse", f"{self._at(node)}: the runtime could not read this statement; that is "
                                        f"{_RUNTIME_FAULT}", line=node.get("line"))
            self._record(node, r)
            return r
        scope = _Scope(self.env, True)
        try:
            if st.member is not None:                     # a node of a loop over a written list: one member
                var, member = st.member
                self.cur.passing = f"for {var} = {self._member_label(node)}"
                scope = scope.child({var: self._member(member, scope)})
            if st.form == "if":
                self.if_results[nid] = self._if(st, scope, node)
            elif st.loop is not None:
                self._repeat(st, scope)
            elif st.form == "assert":
                self._assert(st, scope)
            else:
                self._deliver(st, self._eval(st.expr, scope), node)
        except _Stop as s:
            r = s.refusal if s.worded else self._worded(s.refusal, node, self.cur.passing)
            r = r if r.line else Refusal(r.stage, r.check, r.message, line=node.get("line"), file=r.file)
            if s.fault:
                self.cur.fault = s.fault
            self._record(node, r)
            return r
        if st.loop is None:
            self.cur.attempts = max(self.cur.attempts, 1)      # a condition, an assert, a plain emit ran once
        self._record(node)
        return None

    def _nested_in_runtime(self, node: dict) -> tuple[int, int] | None:
        """`thym 0`'s third loop that runs wrong (THYM 8.1): a node of a `for each` nested inside a loop over a
        collection known only at run time, whose plan lost the outer loop. `(inner loop's line, outer loop's line)`."""
        line = node.get("line")
        if self._version() >= 1 or not isinstance(line, int):
            return None
        around = sorted((sp for sp in self.info.spans if sp[0] < line <= sp[1]), key=lambda sp: sp[0])
        outer = next((sp for sp in around[:-1] if sp[2]), None)
        return (around[-1][0], outer[0]) if outer is not None else None

    def _loop_node(self, node: dict) -> Refusal | None:
        """A whole loop as one node (`thym 1`, THYM 8.1, 11.1): its header and body read from the program by its
        line, the body run member by member as a unit; a loop that collects binds its list when the last pass ends."""
        line = node.get("line")
        part = self.info.loops.get(line) if isinstance(line, int) else None
        try:
            if part is None:
                raise _Stop(Refusal("run", "program", f"{self._at(node)}: this loop's body is read from the program, "
                                    "and this run has only the plan: run it with the program beside the plan "
                                    "(--program)"), worded=True)
            scope = _Scope(self.env, True)
            st = self._read_stmt(str(node.get("name") or part[2]))
            if st.member is not None:                     # a loop inside a loop over a written list: one member
                var, member = st.member
                self.cur.passing = f"for {var} = {self._member_label(node)}"
                scope = scope.child({var: self._member(member, scope)})
            header = self._read_stmt(part[2])
            self._emit_k = 0
            kept, passes = self._loop(header, part[3], scope, worded=True)
            self.cur.passes = passes
            if header.name:
                v = Value("list", kept)
                self.env[header.name] = v
                self.cur.outputs.append(digest_row(header.name, v, path=""))
                for k, x in enumerate(kept, 1):
                    self.cur.outputs.append(digest_row(f"{header.name}.{k}", x, path=""))
        except _Stop as s:
            r = s.refusal if s.worded else self._worded(s.refusal, node, self.cur.passing)
            r = r if r.line else Refusal(r.stage, r.check, r.message, line=line, file=r.file)
            if s.fault:
                self.cur.fault = s.fault
            self._record(node, r)
            return r
        self.cur.attempts = max(self.cur.attempts, 1)
        self._record(node)
        return None

    def _loop(self, header: Stmt, body: list, scope: _Scope, *, worded: bool) -> tuple[list, int]:
        """One `for each` (or loop that collects) of a body: its collection walked, the `where` applied, the body run
        once per member in a scope of its own; `(what its keep lines kept, how many passes)`. With `worded`, the
        passes are named in the person's terms for a refusal inside them."""
        loop = header.loop
        coll = self._eval(loop.coll, scope)
        rows = members(coll)
        if rows is None:
            raise _Stop(Refusal("run", "type", f"a for each goes through a volume, a fabula, a folder, a short or a "
                                               f"list, and {self._words(_expr_text(loop.coll))} is a {coll.type}"))
        if loop.cond is not None:
            rows = [r for r in rows if self._cond(loop.cond, scope.child({loop.var: r}), item=r)]
        if header.name:
            self._keeping.append([])
        try:
            for k, r in enumerate(rows, 1):
                if worded:
                    self._passes.append(self._pass(loop.var, r, k, coll))
                try:
                    self._body(body, scope.child({loop.var: r}), worded=worded)
                finally:
                    if worded:
                        self._passes.pop()
        finally:
            kept = self._keeping.pop() if header.name else []
        return kept, len(rows)

    def _record(self, node: dict, refusal: Refusal | None = None) -> None:
        cur = self.cur or _NodeState(node)
        ins = []
        for t in node.get("takes") or []:
            v = self.env.get(t) if isinstance(self.env.get(t), Value) else None
            if v is not None:
                ins.append(digest_row(t, v, path=self.input_paths.get(t, "")))
        seconds = int(time.monotonic() - getattr(self, "_t0", time.monotonic()))
        tokens = cur.tokens + (cur.calls.tokens if cur.calls is not None else 0)
        rec = _trace.record(node, run_id=self.run_id, move=str(node.get("move") or ""), engine=cur.engine,
                            inputs=ins, outputs=cur.outputs, attempts=cur.attempts if cur.engine != "skipped" else 0,
                            tokens=tokens, seconds=seconds, checks=cur.checks, state=cur.state, refusal=refusal,
                            tries=cur.tries, passes=cur.passes)
        if cur.fault:
            rec["fault"] = cur.fault          # a fault of the runtime: the detail, for whoever maintains it (THYM 9)
        self.records = [r for r in self.records if r["id"] != rec["id"]] + [rec]

    def _deliver(self, st: Stmt, v: Value, node: dict, k: int | None = None) -> None:
        suffix = f".{k}" if k is not None else ""
        if st.form == "emit":
            if st.slot:
                self.slots[st.slot] = v
                self.cur.outputs.append(digest_row(f"{st.slot}{suffix}", v, path=""))
            else:
                self.emitted.append(v)
                self.cur.outputs.append(digest_row(f"emit{suffix}", v, path=""))
            return
        target = node.get("gives") if k is None else None
        if st.form == "let" and st.name and k is None:
            target = target or st.name
        if isinstance(target, str):
            self.env[target] = v
            self.cur.outputs.append(digest_row(target, v, path=""))
        elif not v.is_nothing:
            self.cur.outputs.append(digest_row(f"value{suffix}", v, path=""))

    def _repeat(self, st: Stmt, scope: _Scope) -> None:
        """A `repeats` node: its statement once per member of the collection, the members the `where` keeps, each
        pass with the loop variable bound to its member (THYM 8.1, 11.1). The statement's nested calls are folded
        into it and run with each member. This is the seam for `thym 1`'s loop node, whose body of several statements
        runs member by member as a unit (`_body` already runs a body so)."""
        loop = st.loop
        node = self.cur.node
        found = self._same_loop_let(node)
        if found is not None:
            name, giver = found
            raise _Stop(Refusal("run", "loop", f"{self._at(node)}: {name} is bound by {self._at(giver)} inside this "
                                               f"for each, and {self._loop_reason()}, so here {name} would hold "
                                               f"every pass's value at once; {self._loop_fix()}"), worded=True)
        coll = self._eval(loop.coll, scope)
        rows = members(coll)
        if rows is None:
            head, at = self._loop_statement(node)
            raise _Stop(Refusal("run", "type", f"{head} (line {at}): a for each goes through a volume, a fabula, a "
                                               f"short or a list, and {_expr_text(loop.coll)} is a {coll.type}"),
                        worded=True)
        if loop.cond is not None:                     # the where sees the loop's variable bound to the member
            rows = [r for r in rows if self._cond(loop.cond, scope.child({loop.var: r}), item=r)]
        outs = []
        for k, r in enumerate(rows, 1):
            self.cur.passing = self._pass(loop.var, r, k, coll)
            inner = scope.child({loop.var: r})
            if st.form == "assert":
                self._assert(st, inner)
                continue
            v = self._eval(st.expr, inner)
            self._deliver(st, v, self.cur.node, k)
            outs.append(v)
        self.cur.passing = None
        g = self.cur.node.get("gives")
        if isinstance(g, str):
            self.env[g] = Value("list", outs)

    def _if(self, st: Stmt, scope: _Scope, node: dict) -> bool:
        """An `if` node's condition. In a loop over a collection known only at run time, `thym 0` evaluates it once,
        before the loop and without the loop's variable (THYM 8.1): a condition that needs the variable is refused
        with the fix."""
        if st.loop is None:
            return self._cond(st.cond, scope)
        try:
            return self._cond(st.cond, scope)
        except _Stop as s:
            raise _Stop(Refusal("run", s.refusal.check, f"{self._at(node)}: {s.refusal.message}: in thym "
                                f"{self._version()} an if inside a for each over a collection known only at run time "
                                f"is evaluated once, before the loop, and not for each member; {self._loop_fix()}"),
                        worded=True) from None

    def _version(self) -> int:
        return self.info.version if self.info.version is not None else 0

    def _loop_reason(self) -> str:
        return (f"in thym {self._version()} each statement of a for each over a collection known only at run time "
                "runs over every member before the next statement starts")

    def _loop_fix(self) -> str:
        return "inside a for each, write thym 1, where a loop's body runs member by member"

    def _same_loop_let(self, node: dict) -> tuple[str, dict] | None:
        """A name this repeating node takes that a `let` of the same loop binds (a node of the same loop gives it):
        in `thym 0` it holds every pass's value at once (THYM 8.1)."""
        mine = _TRAILER.search(str(node.get("name") or ""))
        if mine is None:
            return None
        for t in node.get("takes") or []:
            for g in self.nodes:
                if g is node or g.get("gives") != t or not g.get("repeats"):
                    continue
                theirs = _TRAILER.search(str(g.get("name") or ""))
                if theirs is not None and theirs.group(0) == mine.group(0) \
                        and g.get("provenance") == node.get("provenance"):
                    return str(t), g
        return None

    def _loop_statement(self, node: dict) -> tuple[str, Any]:
        """The `for each` line a repeating node's loop was written on, and its line (the nearest such line before
        the node's statement), from the program when it is beside the plan."""
        mt = _TRAILER.search(str(node.get("name") or ""))
        head = mt.group(0)[2:] if mt else "for each"
        line = node.get("line")
        found = [ln for ln, text in self.info.statements.items()
                 if text == head and isinstance(line, int) and ln <= line]
        return _cut(head), (max(found) if found else line)

    def _pass(self, var: str, row: Any, k: int, coll: Value) -> str:
        """A pass of a loop in the person's terms (THYM 9): an item by its id, a line of a short by its number, a
        member of a list by its place."""
        if isinstance(row, Value) and isinstance((row.origin or {}).get("member"), dict):
            label = str(row.origin["member"].get("path") or _ordinal(k))        # a folder's file, by its path
        elif isinstance(row, Value) and row.type == "line" and isinstance(row.field("number"), int):
            label = f"line {row.field('number')}"                              # a line, by its number (THYM 9)
        elif isinstance(row, Value) and row.type == "item":
            label = item_id(row) or _ordinal(k)
        elif coll.type in ("short", "text"):
            label = f"line {k}"
        else:
            label = _ordinal(k)
        return f"for {var} = {label}"

    def _member(self, e: Any, scope: _Scope) -> Value:
        """A written list's member, as a node binds its loop variable to it: a bare name means its binding when one is
        bound, else the word (THYM 4.5); anything else is evaluated."""
        if isinstance(e, Name):
            if e.name in scope.vars or (scope.program and e.name in self.info.lets):
                return self._lookup(e.name, scope, None)
            return Value("word", e.name)
        return self._eval(e, scope)

    def _member_label(self, node: dict) -> str:
        """Which member of its written list a node is for: its place among the nodes of the same statement."""
        same = [n for n in self.nodes if n.get("step") == node.get("step") and n.get("line") == node.get("line")]
        k = next((i for i, n in enumerate(same, 1) if n is node), 1)
        return _ordinal(k)

    # -- the person's words (THYM 9) ------------------------------------------------------------------------------

    def _words(self, text: str, depth: int = 0) -> str:
        """Text from the plan with every temporary put back as the expression it stands for, in parentheses."""
        def back(mt: re.Match) -> str:
            giver = self.by_id.get(f"R:node/{mt.group(1)}")
            if not isinstance(giver, dict) or giver.get("gives") != mt.group(0) or depth > 32:
                return mt.group(0)
            return "(" + self._words(_TRAILER.sub("", str(giver.get("name") or "")), depth + 1) + ")"
        return _TEMP.sub(back, text)

    def _said(self, node: dict) -> str:
        """The statement a node runs, as the person wrote it: from the program by its line, else the node's name
        with its temporaries put back; cut to 60 characters."""
        line = node.get("line")
        text = self.info.statements.get(line) if isinstance(line, int) else None
        if not text:
            text = self._words(_TRAILER.sub("", str(node.get("name") or node.get("move") or "")))
        return _cut(text)

    def _at(self, node: dict, passing: str | None = None) -> str:
        """`<statement> (line N[, for <var> = <member>])`, the head of a refusal (THYM 9)."""
        line = node.get("line")
        where = f"line {line}" if isinstance(line, int) else "a line the plan does not give"
        return f"{self._said(node)} ({where}{', ' + passing if passing else ''})"

    def _worded(self, r: Refusal, node: dict, passing: str | None = None) -> Refusal:
        """A refusal raised while a node ran, headed by the node's statement, its line and the pass."""
        return Refusal(r.stage, r.check, f"{self._at(node, passing)}: {r.message}", line=r.line or node.get("line"),
                       file=r.file)

    def _assert(self, st: Stmt, scope: _Scope) -> None:
        self._sides = []
        ok = self._cond(st.cond, scope)
        check = "coverage" if _has_covers(st.cond) else "assert"
        line = self.cur.node.get("line") if self._move_stack == [] else None
        msg = st.message or (self.info.messages.get(line) if line else None)
        if msg is None and not ok:
            msg = f"{self._condition_said(st, line)} does not hold" + "".join(
                f"; {text} is {describe(v)}" for text, v in self._sides)
        msg = msg or ""
        if check == "coverage":
            for c in self.cur.checks:
                if c.get("name") == "coverage" and not c.get("ok") and c.get("why"):
                    msg = f"{msg} ({c['why']})"
                    break
        else:
            self.cur.checks.append({"name": "assert", "ok": ok, "why": "" if ok else msg})
        if not ok:
            raise _Stop(Refusal("run", check, msg))

    def _condition_said(self, st: Stmt, line: Any) -> str:
        """An `assert`'s condition as the person wrote it: from the program's statement, else read back from the
        plan with its temporaries put back."""
        said = self.info.statements.get(line) if isinstance(line, int) else None
        if said and said.startswith("assert "):
            return _cut(_ELSE_MSG.sub("", said[len("assert "):]).strip())
        return _cut(self._words(_cond_text(st.cond)))

    # -- values ---------------------------------------------------------------------------------------------------

    def _lookup(self, name: str, scope: _Scope, item: Value | None) -> Value:
        if name in scope.vars:
            return scope.vars[name]
        if scope.program and name in self.info.lets and name not in self._let_busy:
            try:
                e = read_expression(self.info.lets[name], self.move_names)
            except ReadError as err:
                raise _Stop(Refusal("run", "parse", f"the runtime could not read let {name} = "
                                                    f"{_cut(self.info.lets[name], 40)}; that is {_RUNTIME_FAULT}"),
                            fault=f"let {name} = {self.info.lets[name]}: {err}") from None
            if not isinstance(e, Call):
                self._let_busy.add(name)
                try:
                    v = self._eval(e, _Scope(self.env, True))
                finally:
                    self._let_busy.discard(name)
                self.env[name] = v
                return v
        if item is not None:
            return wrap(item.field(name))
        hint = ("; it is bound by a let whose value the plan does not hold (a filter folds into the node that reads "
                "it), and this run has only the plan: run it with the program beside the plan (--program)"
                if self.program is None and scope.program else "")
        raise _Stop(Refusal("run", "unbound", f"{name} is not bound{hint}"))

    def _eval(self, e: Any, scope: _Scope, item: Value | None = None) -> Value:
        if isinstance(e, Name):
            return self._lookup(e.name, scope, item)
        if isinstance(e, Lit):
            return e.value
        if isinstance(e, ListLit):
            return Value("list", [self._member(Name(x.value.payload), scope)
                                  if isinstance(x, Lit) and x.value.type == "word" else self._eval(x, scope, item)
                                  for x in e.items])
        if isinstance(e, FieldRead):
            return wrap(self._eval(e.base, scope, item).field(e.name))
        if isinstance(e, Filter):
            base = self._eval(e.base, scope, item)
            if base.type == "folder":                  # a folder filtered is a folder (THYM 20.2)
                return filter_folder(base, lambda it: self._cond(e.cond, scope, item=it))
            rows = members(base)
            if rows is None:
                raise _Stop(Refusal("run", "type", f"where filters a volume, a fabula, a short or a list, and "
                                                   f"{self._words(_expr_text(e.base))} is a {base.type}"))
            return Value("list", [r for r in rows if self._cond(e.cond, scope, item=r)])
        if isinstance(e, Call):
            return self._call(e, scope, item)
        raise _Stop(Refusal("run", "runtime", f"the runtime cannot evaluate a part of this statement; that is "
                                              f"{_RUNTIME_FAULT}"), fault=f"cannot evaluate {e!r}")

    def _cond(self, c: Any, scope: _Scope, item: Value | None = None) -> bool:
        if isinstance(c, BoolOp):
            if c.op == "and":
                return all(self._cond(x, scope, item) for x in c.items)
            return any(self._cond(x, scope, item) for x in c.items)
        if isinstance(c, Not):
            return not self._cond(c.item, scope, item)
        if isinstance(c, Bare):
            return self._eval(c.expr, scope, item).plain() is True
        if isinstance(c, Has):
            return self._eval(c.base, scope, item).field(c.name) is not None
        if isinstance(c, Covers):
            f = self._eval(c.left, scope, item)
            t = self._eval(c.right, scope, item)
            fname = c.left.name if isinstance(c.left, Name) else "fabula"
            node = dict(self.cur.node, modifiers={})
            r = _checks.verdict("coverage", t, {fname: f}, node, None, self._ctx(), registry=self.checks)
            if isinstance(r, Refusal):
                raise _Stop(r)
            self.cur.checks.append({"name": "coverage", "ok": r[0], "why": r[1]})
            return r[0]
        if isinstance(c, Cmp):
            av = self._eval(c.left, scope, item)
            bv = self._eval(c.right, scope, item)
            if item is None and c.op != "in":             # what an assert that fails says it compared (THYM 9)
                self._sides = [(self._words(_expr_text(x, True)), v) for x, v in ((c.left, av), (c.right, bv))
                               if not isinstance(x, Lit)]
            a, b = av.plain(), bv.plain()
            if c.op == "is":
                return _eq(a, b)
            if c.op == "is not":
                return not _eq(a, b)
            if c.op == "in":
                if isinstance(b, list):
                    return any(_eq(a, x) for x in b)
                if bv.type in ("text", "short", "string", "line"):      # thym 1: a string inside a text (THYM 4.5)
                    needle = a if isinstance(a, str) else av.text()
                    return needle in bv.text()
                return False
            if c.op == "=":
                return _eq(a, b)
            if isinstance(a, bool) or isinstance(b, bool) or not isinstance(a, int) or not isinstance(b, int):
                return False
            return a < b if c.op == "<" else a > b
        raise _Stop(Refusal("run", "runtime", f"the runtime cannot evaluate a condition of this statement; that is "
                                              f"{_RUNTIME_FAULT}"), fault=f"cannot evaluate the condition {c!r}")

    # -- calls ----------------------------------------------------------------------------------------------------

    def _ctx(self) -> MoveContext:
        return MoveContext(run=self.made_run, node=dict(self.cur.node), decls=self.decls, coprocessor=self.coproc,
                           rules=self.rules, now=self.started, emitted=self.emitted, slots=self.slots,
                           withheld=self.withheld, inputs_root=self.inputs_root, root=self.root, stage=self.stage,
                           program=self.info, trace_fn=self._trace_so_far, engines=self.engines,
                           calls=self.cur.calls if self.cur is not None else None, ask_fn=self._move_ask)

    def _count_request(self) -> None:
        """One more model request; past the run's ceiling (`--calls N`), the run is refused (THYM 12.5, 23.4)."""
        if self.ceiling is not None and self.requests >= self.ceiling:
            raise _Stop(Refusal("run", "calls", f"this run reached its ceiling of {self.ceiling} model call"
                                                f"{'s' if self.ceiling != 1 else ''}; nothing landed"))
        self.requests += 1

    def _move_ask(self, contract: dict, inputs: dict, budget: dict | None) -> dict:
        """`ctx.ask`: one request a move makes itself, keyed, recorded, replayed and counted like any other."""
        if not self._asking:
            raise _Stop(Refusal("run", "asks", "a move asked the model outside a call the runtime made"))
        frame = self._asking[-1]
        if self.rules or self.agent_free:
            raise _Stop(Refusal("run", "rules" if self.rules else "agent-free",
                                f"{frame['move']} asks a model; " + ("--rules runs no model" if self.rules
                                                                     else "agent-free is on")))
        self._count_request()
        nb = self.cur.node.get("budget") if isinstance(self.cur.node.get("budget"), dict) else {}
        rb = budget or {}
        allowed, own = _move_repair(contract.get("repair"))
        failed = [dict(x) for level in self._repairs for x in level] + [dict(x) for x in frame["failed"]] + own
        c = {"move": frame["move"], "schema": plain(contract.get("schema")),
             "checks": [str(x) for x in decl_get(frame["decl"], "contract") or []],
             "repair": {"allowed": allowed, "failed": failed}}
        ins = {}
        for k, v in (inputs or {}).items():
            v = v if isinstance(v, Value) else wrap(v)
            ins[str(k)] = (v, v.sha256)
        b = {"attempts": 1, "output_words": int(rb.get("output_words") or nb.get("output_words") or 0),
             "prompt_tokens_max": self.largest_prompt, "seconds": int(rb.get("seconds") or 600)}
        cand = _ask(self.coproc, c, ins, budget=b, at=(self.cur.calls.request_key(), 1))
        if isinstance(cand, Refusal):
            raise _Stop(cand)
        frame["asked"] += 1
        frame["engine"] = str(cand.get("engine") or frame["engine"])
        frame["cand"] = cand
        self.cur.tokens += int(cand.get("tokens") or 0)
        return cand

    def _trace_so_far(self) -> dict:
        self.trace.records = list(self.records)
        return self.trace.to_volume()

    def _made(self, move: str, engine: str, cand: Any = None) -> dict:
        step = self.cur.node.get("step")
        n = step.get("n") if isinstance(step, dict) else None
        # the candidate's route and provider stand beside the engine when it carried them (THYM 23.1)
        return {"move": move, "run": self.made_run, "step": n, "node": node_number(self.cur.node.get("id")),
                "engine": engine, **_coproc_where(cand)}

    def _engine(self, engine: str) -> None:
        """The node's engine is the strongest of its calls': a model over a scaffold over code."""
        def rank(e: str) -> int:
            return 3 if e.startswith(("model:", "replay")) else _ENGINE_RANK.get(e, 1)
        if rank(engine) >= rank(self.cur.engine):
            self.cur.engine = engine

    def _merge_checks(self, verdicts: list[dict]) -> None:
        for v in verdicts:
            old = next((c for c in self.cur.checks if c.get("name") == v.get("name")), None)
            if old is None:
                self.cur.checks.append(dict(v))
            elif old.get("ok") and not v.get("ok"):
                old.update(v)

    def _call(self, e: Call, scope: _Scope, item: Value | None) -> Value:
        operands = [self._eval(o, scope, item) for o in e.operands]
        names = [o.name if isinstance(o, Name) else f"operand{k + 1}" for k, o in enumerate(e.operands)]
        mods: dict = {}
        for w, a in e.mods.items():
            if w in ("as", "by", "to"):
                mods[w] = a
            elif w == "where":
                cond, text = a
                mods["where"] = Where(text, lambda r, c=cond: self._cond(c, scope, item=r))
            elif w != "marked":
                mods[w] = self._eval(a, scope, item)
        v = self._apply(e.move, operands, mods, names)
        if "marked" in e.mods:
            v = self._apply("mark", [v], {"as": e.mods["marked"]}, ["marked"])
        return v

    def _apply(self, move: str, operands: list, mods: dict, names: list) -> Value:
        if move in self.info.moves:
            return self._user_move(move, operands)
        decl = self.decls.get(move)
        if decl is None:
            raise _Stop(Refusal("run", "unknown-move", f"the move {move} is not declared"))
        decl = _chosen_decl(decl, operands, mods)
        declared = decl_get(decl, "modifiers") or {}
        if "where" in mods and "where" not in declared and operands:
            w = mods.pop("where")
            operands = [Value("list", w.select(operands[0])), *operands[1:]]
        inputs = {names[k] if k < len(names) else f"operand{k + 1}": v for k, v in enumerate(operands)}
        inputs.update({w: v for w, v in mods.items() if isinstance(v, Value)})
        check_node = dict(self.cur.node, modifiers=_plain_mods(mods))
        asks = decl_get(decl, "asks") is True
        ctx = self._ctx()
        if asks and self.rules:
            # a call whose scaffold-when says `none` has no scaffold, whatever `<move>.scaffold` the registry holds
            fn = self.moves.scaffold(decl) if decl_get(decl, "scaffold") else None
            if fn is None:
                raise _Stop(Refusal("run", "rules", f"{move} asks a model and has no scaffold; --rules runs no model"))
            r = self._invoke(move, fn, ctx, operands, mods)
            if isinstance(r, Request):
                raise _Stop(Refusal("run", "rules", f"the scaffold of {move} asked the model"))
            v = stamp(self._as_value(r, decl), self._made(move, "rules"), pending=True)
            self.cur.state = "pending"
            self._settle(move, decl, v, inputs, check_node, "rules")
            return v
        fn = _kind_code(decl, mods) or self.moves.lookup(move)
        if fn is None:
            raise _Stop(Refusal("run", "move", f"the move {move} has no implementation here"))
        frame = {"move": move, "decl": decl, "failed": [], "asked": 0, "engine": "model:unknown"}
        self._asking.append(frame)
        try:
            r = self._invoke(move, fn, ctx, operands, mods)
            if isinstance(r, Request):
                if not asks:
                    raise _Stop(Refusal("run", "asks", f"{move} is declared deterministic, and it asked the model"))
                return self._ask_model(move, decl, r, inputs, check_node)
            if frame["asked"]:
                if not asks:
                    raise _Stop(Refusal("run", "asks", f"{move} is declared deterministic, and it asked the model"))
                return self._asked_itself(move, decl, fn, frame, r, operands, mods, inputs, check_node)
        finally:
            self._asking.pop()
        pending = any(isinstance(x, Value) and x.state == "pending" for x in inputs.values())
        # what is made from a scaffold's output is pending too
        v = stamp(self._as_value(r, decl), self._made(move, "code"), pending=pending)
        if pending:
            self.cur.state = "pending"
        self._settle(move, decl, v, inputs, check_node, "code")
        return v

    def _asked_itself(self, move: str, decl: Any, fn: Callable, frame: dict, r: Any, operands: list, mods: dict,
                      inputs: dict, node: dict) -> Value:
        """A move that asked through `ctx.ask` gave a value: it is held to its contract, and called again with the
        failed verdicts (`ctx.failed`, `ctx.previous`, `ctx.attempt`) within the node's attempts (THYM 12.2)."""
        nb = self.cur.node.get("budget") if isinstance(self.cur.node.get("budget"), dict) else {}
        attempts = max(1, int(nb.get("attempts") or 3))
        attempt = 1
        while True:
            if isinstance(r, Request):
                raise _Stop(Refusal("run", "asks", f"{move} asked through ctx.ask and then gave a request; a move "
                                                   "asks one way"))
            self._engine(frame["engine"])
            self.cur.attempts += 1
            value = stamp(self._as_value(r, decl), self._made(move, frame["engine"], frame.get("cand")))
            verdicts = self._verdicts(decl, value, inputs, node)
            failed = [x for x in verdicts if not x["ok"]]
            if not failed:
                self._merge_checks(verdicts)
                return value
            self.cur.tries.append({"attempt": attempt, "failed": [{"name": str(x.get("name")),
                                                                  "why": str(x.get("why") or "")[:400]}
                                                                 for x in failed]})
            if attempt >= attempts:
                self._merge_checks(verdicts)
                bad = failed[0]
                why = f": {bad['why']}" if bad.get("why") else ""
                raise _Stop(Refusal("run", bad["name"], f"{move} still fails {bad['name']} after {attempt} "
                                                        f"attempt{'s' if attempt != 1 else ''}{why}"))
            attempt += 1
            frame["failed"] = [dict(x) for x in failed]
            ctx = self._ctx()
            ctx.failed, ctx.previous, ctx.attempt = [dict(x) for x in failed], value, attempt
            r = self._invoke(move, fn, ctx, operands, mods)

    def _invoke(self, move: str, fn: Callable, ctx: MoveContext, operands: list, mods: dict) -> Any:
        try:
            return fn(ctx, *operands, **mods)
        except _Stop:
            raise
        except EngineRefusal as e:                      # a replayed engine call that does not match its record
            raise _Stop(e.refusal) from None
        except Exception as e:  # noqa: BLE001 - THYM.md 9: a deterministic move that raises refuses the run
            if any(k.__name__ == "MoveError" for k in type(e).__mro__):
                # a move that cannot go on says why in the program's terms (moves.MoveError)
                raise _Stop(Refusal("run", "move", str(e) or f"{move} cannot go on with what it was given")) from None
            raise _Stop(Refusal("run", "move", f"{move} failed inside its implementation; that is {_RUNTIME_FAULT}"),
                        fault=f"{move}: {type(e).__name__}: {e}") from None

    def _as_value(self, r: Any, decl: Any) -> Value:
        if isinstance(r, Value):
            return r
        if r is None:
            return NOTHING
        alts = _alternatives(decl_get(decl, "gives"))
        if len(alts) > 1:
            if isinstance(r, str) and "word" in alts:
                return Value("word", r)
            if isinstance(r, dict) and "item" in alts:
                return Value("item", r)
        if alts and alts[0] != "nothing":
            return Value(alts[0], r)
        return wrap(r)

    def _verdicts(self, decl: Any, v: Value, inputs: dict, node: dict) -> list[dict]:
        out = []
        for name in decl_get(decl, "contract") or []:
            try:
                r = _checks.verdict(str(name), v, inputs, node, decl, self._ctx(), registry=self.checks)
            except EngineRefusal as e:
                self._merge_checks(out)
                raise _Stop(e.refusal) from None
            if isinstance(r, Refusal):
                self._merge_checks(out)
                raise _Stop(r)
            out.append({"name": str(name), "ok": r[0], "why": r[1]})
        return out

    def _settle(self, move: str, decl: Any, v: Value, inputs: dict, node: dict, engine: str) -> None:
        """Check a value a move gave in code (or a scaffold gave) against the move's contract; refuse on a failure."""
        verdicts = self._verdicts(decl, v, inputs, node)
        self._engine(engine)
        self.cur.attempts += 1
        self._merge_checks(verdicts)
        bad = next((x for x in verdicts if not x["ok"]), None)
        if bad is not None:
            raise _Stop(Refusal("run", bad["name"], bad["why"] or f"{move}'s check {bad['name']} does not hold"))

    def _read(self, req: Request, decl: Any, cand: dict) -> tuple[Value | None, list[dict]]:
        out = cand.get("output")
        schema = req.contract.get("schema") if isinstance(req.contract, dict) else None
        fmt = schema.get("format") if isinstance(schema, dict) else (schema if isinstance(schema, str) else None)
        if fmt == "yaml" and isinstance(out, str):
            # THYM.md 12.2: prose around or instead of the YAML fails `schema` at once and is asked again, never
            # reaching the contract's other checks (a model that narrates fails coverage slowly otherwise)
            why = prose_problem(out)
            if why:
                return None, [{"name": "schema", "ok": False, "why": why}]
        try:
            if req.parse is not None:
                r = req.parse(out)
            elif fmt == "yaml":
                r = out if isinstance(out, dict) else mc.yaml_load(_strip_fences(str(out or "")))
                if not isinstance(r, dict):
                    raise ValueError("the answer is not a YAML mapping")
            else:
                r = out if isinstance(out, (str, dict)) else str(out)
        except EngineRefusal as e:
            raise _Stop(e.refusal) from None
        except Exception as e:  # noqa: BLE001 - an unreadable answer fails like a check, and is asked again
            return None, [{"name": "schema", "ok": False, "why": f"the answer could not be read: {e}"}]
        if r is None:
            return None, [{"name": "schema", "ok": False, "why": "the answer could not be read"}]
        return self._as_value(r, decl), []

    def _ask_model(self, move: str, decl: Any, req: Request, inputs: dict, node: dict) -> Value:
        nb = self.cur.node.get("budget") if isinstance(self.cur.node.get("budget"), dict) else {}
        rb = req.budget or {}
        attempts = max(1, int(rb.get("attempts") or nb.get("attempts") or 3))
        allowed = list(req.contract.get("repair") or []) if isinstance(req.contract, dict) else []
        schema = plain(req.contract.get("schema")) if isinstance(req.contract, dict) else None
        contract = {"move": move, "schema": schema,
                    "checks": [str(c) for c in decl_get(decl, "contract") or []],
                    "repair": {"allowed": allowed, "failed": []}}
        ins = {}
        for k, v in (req.inputs or {}).items():
            v = v if isinstance(v, Value) else wrap(v)
            ins[str(k)] = (v, v.sha256)
        budget = {"attempts": attempts, "output_words": int(rb.get("output_words") or nb.get("output_words") or 0),
                  "prompt_tokens_max": self.largest_prompt, "seconds": int(rb.get("seconds") or 600)}
        key = self.cur.calls.request_key()
        last: list[dict] = []
        engine = "model:unknown"
        # a re-run of a move whose kept contract failed: every request carries those verdicts too (THYM 7.5, 12.2)
        kept_failed = [dict(x) for level in self._repairs for x in level]
        contract["repair"] = {"allowed": allowed, "failed": [dict(x) for x in kept_failed]}
        for attempt in range(1, attempts + 1):
            self._count_request()
            cand = _ask(self.coproc, contract, ins, budget=budget, at=(key, attempt))
            self.cur.attempts += 1
            if isinstance(cand, Refusal):
                self._merge_checks(last)
                raise _Stop(cand)
            engine = str(cand.get("engine") or engine)
            self._engine(engine)
            self.cur.tokens += int(cand.get("tokens") or 0)
            value, failed = self._read(req, decl, cand)
            if value is not None:
                value = stamp(value, self._made(move, engine, cand))
                verdicts = self._verdicts(decl, value, inputs, node)
                failed = [x for x in verdicts if not x["ok"]]
                if failed and req.repair is not None:
                    try:
                        fixed = req.repair(value, [dict(x) for x in failed])
                    except EngineRefusal as e:
                        raise _Stop(e.refusal) from None
                    except Exception:  # noqa: BLE001 - a repair that breaks is no repair; ask again
                        fixed = None
                    if fixed is not None:
                        value = stamp(self._as_value(fixed, decl), self._made(move, engine, cand))
                        verdicts = self._verdicts(decl, value, inputs, node)
                        failed = [x for x in verdicts if not x["ok"]]
                if not failed:
                    self._merge_checks(verdicts)
                    return value
                last = verdicts
            else:
                last = failed
            # the record keeps every attempt's failures, so a refused node explains all its tries, not only the last
            self.cur.tries.append({"attempt": attempt, "failed": [{"name": str(x.get("name") or "schema"),
                                                                  "why": str(x.get("why") or "")[:400]} for x in failed]})
            contract["repair"] = {"allowed": allowed, "failed": [dict(x) for x in kept_failed + failed]}
        self._merge_checks(last)
        bad = next((x for x in last if not x["ok"]), {"name": "schema", "why": "no answer"})
        tries = f"{attempts} attempt{'s' if attempts != 1 else ''}"
        why = f": {bad['why']}" if bad.get("why") else ""
        raise _Stop(Refusal("run", bad["name"], f"{move} still fails {bad['name']} after {tries}{why}"))

    # -- user moves (THYM.md 8.3) ---------------------------------------------------------------------------------

    def _user_move(self, name: str, operands: list) -> Value:
        """A user move's call (THYM 8.3): its body run with its parameters bound; a move that may call itself counted
        against its depth; what it keeps checked on the value it gives, its body run again within the node's attempts
        when a kept contract fails and the move asks (THYM 7.5)."""
        um: UserMove = self.info.moves[name]
        if len(operands) != len(um.params):
            raise _Stop(Refusal("run", "type",
                                f"{name} takes {len(um.params)} operand(s); it was given {len(operands)}"))
        deep = self._move_stack.count(name)
        if deep and um.depth is None:
            raise _Stop(Refusal("run", "recursion", f"{name} calls itself"))
        if deep and deep >= um.depth:
            raise _Stop(Refusal("run", "recursion", f"{name} went {deep + 1} deep; its depth is {um.depth}"))
        args = {p[0]: v for p, v in zip(um.params, operands)}
        asks = bool(um.keeps) and self._move_asks(name)
        nb = self.cur.node.get("budget") if isinstance(self.cur.node.get("budget"), dict) else {}
        budget = max(1, int(nb.get("attempts") or (3 if asks else 1))) if asks else 1
        repair: list[dict] = []
        attempt = 0
        while True:
            attempt += 1
            self._move_stack.append(name)
            self._repairs.append(repair)
            try:
                out = self._body(um.body, _Scope(dict(args), program=False))
            finally:
                self._repairs.pop()
                self._move_stack.pop()
            if out is None:
                raise _Stop(Refusal("run", "no-give", f"{name} reached its end without a give"))
            if not um.keeps:
                return out
            verdicts = [self._kept(k, out, args) for k in um.keeps]
            bad = [v for v in verdicts if not v["ok"]]
            if not bad:
                self._merge_checks(verdicts)
                return out
            self.cur.tries.append({"attempt": attempt, "failed": [{"name": v["name"], "why": str(v["why"])[:400]}
                                                                  for v in bad]})
            why = f": {bad[0]['why']}" if bad[0].get("why") else ""
            if not asks:
                self._merge_checks(verdicts)
                raise _Stop(Refusal("run", bad[0]["name"], f"{name} fails {bad[0]['name']}{why}"))
            if attempt >= budget:
                self._merge_checks(verdicts)
                raise _Stop(Refusal("run", bad[0]["name"], f"{name} still fails {bad[0]['name']} after {attempt} "
                                                          f"attempt{'s' if attempt != 1 else ''}{why}"))
            repair = [dict(v) for v in bad]

    def _kept(self, kept: tuple, value: Value, given: dict) -> dict:
        """A kept contract's verdict on a value (THYM 7.5), `{name, ok, why}`: a contract block's lines run with its
        parameters bound to the value and the `against` values, the first false assert giving the why; a named check
        asked with the `against` values as its inputs, by name."""
        cname, against = kept[0], list(kept[1] or [])
        values = [(a, given[a]) for a in against if a in given]
        cb = self.info.contracts.get(cname)
        if cb is not None:
            why = self._holds(cb, [value] + [v for _, v in values])
            return {"name": cname, "ok": why is None, "why": why or ""}
        node = dict(self.cur.node, modifiers={})
        r = _checks.verdict(cname, value, dict(values), node, None, self._ctx(), registry=self.checks)
        if isinstance(r, Refusal):
            raise _Stop(r)
        return {"name": cname, "ok": r[0], "why": r[1]}

    def _holds(self, cb: ContractBlock, values: list) -> str | None:
        """A contract block's lines run in order over its parameters (THYM 7.5): None when every assert holds, else
        the first false assert's message (or its condition, as written, and what it compared). It asks nothing, and
        leaves the node's record as it found it."""
        cur = self.cur
        saved = (cur.attempts, [dict(c) for c in cur.checks], cur.state, cur.engine, list(self._sides))

        def run(body: list, scope: _Scope) -> str | None:
            for part in body:
                st = self._read_stmt(part[2])
                if part[0] == "for":
                    coll = self._eval(st.loop.coll, scope)
                    rows = members(coll) or []
                    if st.loop.cond is not None:
                        rows = [r for r in rows if self._cond(st.loop.cond, scope.child({st.loop.var: r}), item=r)]
                    for r in rows:
                        why = run(part[3], scope.child({st.loop.var: r}))
                        if why is not None:
                            return why
                elif st.form == "let":
                    scope.vars[st.name] = self._eval(st.expr, scope)
                elif st.form == "assert":
                    self._sides = []
                    if not self._cond(st.cond, scope):
                        return st.message or (f"{_cut(self._words(_cond_text(st.cond)))} does not hold" + "".join(
                            f"; {text} is {describe(v)}" for text, v in self._sides))
            return None

        try:
            return run(cb.body, _Scope({p[0]: v for p, v in zip(cb.params, values)}, program=False))
        finally:
            cur.attempts, cur.checks, cur.state, cur.engine, self._sides = saved

    def _body(self, body: list, scope: _Scope, *, worded: bool = False) -> Value | None:
        """A body's statements in order (a user move's, or, `worded`, a loop node's): `if` and `for each` (and a loop
        that collects) with scopes of their own, `keep` into the nearest loop that collects. With `worded`, a refusal
        inside names the statement of the body it came from, its line and the pass."""
        for part in body:
            try:
                out = self._part(part, scope, worded)
            except _Stop as s:
                if not worded or s.worded:
                    raise
                said = self.info.statements.get(part[1]) or strip_comment(part[2]).strip()
                where = f"line {part[1]}" + (f", {self._passes[-1]}" if self._passes else "")
                r = s.refusal
                raise _Stop(Refusal(r.stage, r.check, f"{_cut(said)} ({where}): {r.message}", line=part[1],
                                    file=r.file), worded=True, fault=s.fault) from None
            if out is not None:
                return out
        return None

    def _part(self, part: tuple, scope: _Scope, worded: bool) -> Value | None:
        if part[0] == "if":
            st = self._read_stmt(part[2])
            return self._body(part[3] if self._cond(st.cond, scope) else part[4], scope.child({}), worded=worded)
        if part[0] == "for":
            st = self._read_stmt(part[2])
            if st.loop is None:
                raise _Stop(Refusal("run", "parse", f"the runtime could not read {_cut(part[2])} as a for each; "
                                                    f"that is {_RUNTIME_FAULT}"))
            kept, _ = self._loop(st, part[3], scope, worded=worded)
            if st.name:                                   # a loop that collects binds its list after its end
                scope.vars[st.name] = Value("list", kept)
            return None
        st = self._read_stmt(part[2])
        if st.form == "give":
            return self._eval(st.expr, scope)
        if st.form == "let":
            scope.vars[st.name] = self._eval(st.expr, scope)
        elif st.form == "keep":
            if not self._keeping:
                raise _Stop(Refusal("run", "runtime", f"a keep stands in no loop that collects; that is "
                                                      f"{_RUNTIME_FAULT}"))
            self._keeping[-1].append(self._eval(st.expr, scope))
        elif st.form == "assert":
            self._assert(st, scope)
        elif st.form == "emit":
            v = self._eval(st.expr, scope)
            (self.slots.__setitem__(st.slot, v) if st.slot else self.emitted.append(v))
            if worded:                                    # a loop node's record holds a row per emitted value
                self._emit_k += 1
                self.cur.outputs.append(digest_row(f"{st.slot or 'emit'}.{self._emit_k}", v, path=""))
        elif st.expr is not None:
            self._eval(st.expr, scope)
        return None

    def _read_stmt(self, text: str) -> Stmt:
        try:
            return read_statement(text, self.move_names, self.in_moves, self.where_moves)
        except ReadError as e:
            raise _Stop(Refusal("run", "parse", f"the runtime could not read {_cut(text)}; that is {_RUNTIME_FAULT}"),
                        fault=f"{text}: {e}") from None

    # -- landing (THYM.md 12.1: every output or none) -------------------------------------------------------------

    def _land(self) -> Refusal | None:
        """Every output into the stage, then the stage renamed into `outputs/` in one step: all or none (THYM
        12.1). A folder lands as a directory holding exactly its files (THYM 20.4)."""
        landed: dict[str, Path] = {}
        prog = self.info.name or (self.plan.get("program") or {}).get("name") or "the program"
        r = self._program_keeps(prog)
        if r is not None:
            return r
        for name in self.output_names:
            v = self.env.get(name)
            if v is None:
                missed = [n for n in self.nodes if n.get("gives") == name and n.get("id") in self.skipped]
                why = (f": the give at line {missed[0].get('line')} is on the branch not taken" if missed else "")
                return Refusal("run", "no-give", f"program {prog} gives {name}, and no give reached it{why}; "
                                                 "nothing landed")
            if isinstance(v.payload, _folder.Folder):
                try:
                    _folder.write_tree(v.payload, self.stage / name)
                except _folder.FolderError as e:
                    return Refusal("run", "output", f"program {prog} gives {name}, a folder, and it could not be "
                                                    f"written: {e}; nothing landed")
                landed[name] = Path("outputs") / name
            else:
                fname = f"{name}.{v.ext}"
                target = self.stage / fname
                if isinstance(v.payload, mc.Volume) and v.path is not None and Path(v.path).is_dir():
                    shutil.copytree(v.path, target)
                else:
                    write_atomic(target, v.write_bytes())
                landed[name] = Path("outputs") / fname
            self.trace.values[name] = v
        out_dir = self.dir / "outputs"
        self.stage.replace(out_dir)
        for rec in self.records:
            for row in rec.get("outputs") or []:
                name = row.get("name")
                if name in landed:
                    folder = isinstance(self.trace.values[name].payload, _folder.Folder)
                    # the same on every system (values.posix_path); a folder's path ends with a slash
                    row["path"] = posix_path(landed[name]) + ("/" if folder else "")
        for n, rel in landed.items():
            self.trace.outputs[n] = self.dir / rel
            if self.destination is not None:
                src = self.dir / rel
                dst = self.destination / src.name
                if src.is_dir():
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    write_atomic(dst, src.read_bytes())
        return None


    def _program_keeps(self, prog: str) -> Refusal | None:
        """What a program keeps, checked on its outputs before anything lands (THYM 7.5): a failure refuses the run
        with the contract's name, and there is no re-ask (a program is not one node)."""
        for kept in self.info.keeps:
            out = kept[2] or (self.output_names[0] if self.output_names else None)
            v = self.env.get(out) if out else None
            if v is None:
                continue                                  # no give reached it: _land says so
            giver = next((n for n in reversed(self.nodes) if n.get("gives") == out), None) or self.nodes[-1]
            self.cur = _NodeState(giver)
            try:
                verdict = self._kept(kept, v, dict(self.inputs))
            except _Stop as s:
                return Refusal("run", s.refusal.check, f"program {prog} gives {out}: {s.refusal.message}; nothing "
                                                       "landed")
            rec = next((r for r in self.records if r.get("node") == giver.get("id")), None)
            if rec is not None:
                rec["checks"] = [c for c in rec.get("checks") or [] if c.get("name") != verdict["name"]] + [verdict]
            if not verdict["ok"]:
                why = f": {verdict['why']}" if verdict.get("why") else ""
                return Refusal("run", verdict["name"], f"program {prog} gives {out}, and it fails "
                                                       f"{verdict['name']}{why}; nothing landed")
        return None


def _views(decls: Any, version: int) -> Any:
    """The declarations a program of grammar `version` sees (THYM 4.9): the compiler's `declarations.views` when it
    is there, else each mapping's own `since` and `thym-1` keys read here."""
    try:
        from enough.thym import declarations as _decls     # the compiler's module
        return _decls.views(decls, version)
    except ImportError:
        pass
    out: dict = {}
    for name, d in (decls or {}).items():
        if isinstance(d, dict):
            since = d.get("since")
            if isinstance(since, int) and not isinstance(since, bool) and since > version:
                continue
            over = d.get("thym-1") if isinstance(d.get("thym-1"), dict) and version >= 1 else {}
            d = {**{k: v for k, v in d.items() if k != "thym-1"}, **over}
        out[name] = d
    return out


def _kind_code(decl: Any, mods: dict) -> Callable | None:
    """The code another owner gave a kind of this move (`extends: true`, THYM 6.2), when the call's `as` word is one
    of its kinds: `project h as isograph` runs Ascribe's projection, `as isotype` Comprise's. None otherwise."""
    word = mods.get("as")
    for words, code, _owner in decl_get(decl, "code_when") or ():
        if isinstance(word, str) and word in words:
            fn = _registry.resolve(code)
            if fn is None:
                raise _Stop(Refusal("run", "move", f"the {word} kind of {decl_get(decl, 'name')} ({code}) has no "
                                                   "implementation here"))
            return fn
    return None


def _move_repair(rep: Any) -> tuple[list, list[dict]]:
    """A move's own `repair` as `ctx.ask` takes it: `(allowed, failed)`. A list (or nothing) is the narrow repairs
    allowed and no failure; a mapping `{allowed, failed}` gives both, each failure a `{name, ok: false, why}` (a
    string is the reason the move could not take its last answer, named `answer`)."""
    if isinstance(rep, dict):
        allowed = [str(x) for x in rep.get("allowed") or []]
        out: list[dict] = []
        for f in rep.get("failed") or []:
            if isinstance(f, dict):
                out.append({"name": str(f.get("name") or "answer"), "ok": False, "why": str(f.get("why") or "")})
            elif isinstance(f, str) and f.strip():
                out.append({"name": "answer", "ok": False, "why": f.strip()})
        return allowed, out
    return list(rep or []), []


def _chosen_decl(decl: Any, operands: list, mods: dict) -> Any:
    """The declaration as this call is held to it: its `gives`, contract and scaffold chosen by the call's `as` word
    or first operand's type (`gives-when`, `contract-when`, `scaffold-when`, `same-as-with`, THYM 17.6). A
    declaration with no such key is returned as it is."""
    keys = ("gives-when", "contract-when", "scaffold-when", "gives_when", "contract_when", "scaffold_when")
    gives = _alternatives(decl_get(decl, "gives"))
    if not any(decl_get(decl, k) for k in keys) and not (len(gives) == 1 and gives[0].startswith("same-as-")):
        return decl
    try:
        from enough.thym import declarations as _decls     # the compiler's reader of the rules
    except ImportError:
        return decl
    w, i = mods.get("with"), mods.get("in")
    ch = _decls.chosen(decl, as_word=mods.get("as"), first_type=operands[0].type if operands else None,
                       with_type=w.type if isinstance(w, Value) else None,
                       in_type=i.type if isinstance(i, Value) else None)
    if isinstance(decl, dict):
        return {**decl, "gives": " | ".join(ch["gives"]), "contract": list(ch["contract"]), "scaffold": ch["scaffold"]}
    import dataclasses
    return dataclasses.replace(decl, gives=tuple(ch["gives"]), contract=tuple(ch["contract"]),
                               scaffold=ch["scaffold"])


def _alternatives(x: Any) -> list[str]:
    """A declaration's type alternatives, whether written `'item | word'` (a manifest) or `('item', 'word')` (the
    compiler's `MoveDecl`)."""
    if x is None:
        return []
    parts = [x] if isinstance(x, str) else [str(p) for p in x] if isinstance(x, (list, tuple)) else [str(x)]
    return [a.strip() for p in parts for a in p.split("|") if a.strip()]


def _tree_files(d: Path) -> dict:
    """Every file under a landed folder output, by its path, with its bytes (a replay compares them)."""
    return {p.relative_to(d).as_posix(): p.read_bytes() for p in sorted(d.rglob("*")) if p.is_file()}


def _strip_fences(text: str) -> str:
    mt = re.search(r"```[A-Za-z0-9_-]*\s*\n(.*?)(?:\n```|$)", text, re.S)
    return mt.group(1) if mt else text


def run(plan: dict, *, inputs_root: Path | str, coprocessor: Any = None, root: Path | str | None = None,
        rules: bool = False, agent_free: bool = False, preflight: Callable[[dict], Refusal | None] | None = None,
        program: Any = None, decls: dict | None = None, moves: _registry.Moves | None = None,
        checks: _checks.Checks | None = None, environment: dict | None = None, destination: Path | None = None,
        record: bool = True, run_id: str | None = None, made_run: str | None = None,
        now: _dt.datetime | None = None, replay_of: str | None = None, engines: Any = None,
        progress: Callable[[dict], Any] | None = None,
        should_stop: Callable[[], bool] | None = None, snapshots: Path | str | None = None,
        calls: int | None = None) -> Trace | Refusal:
    """Run a plan (THYM.md 12.1). `inputs_root` is the folder the plan's input paths are relative to; `program` the
    program's items or `.thym` source (needed for let filters and user moves); `coprocessor` answers model-backed
    nodes (default: refusing); `root` is where runs live (default `ENOUGH_THYM_ROOT`, else `~/enough/thym/`);
    `preflight(plan)` may refuse on size; `destination` is a folder the output is also copied into once it lands.
    `record` wraps the coprocessor so every candidate is kept for replay. `made_run` and `now` let a replay stamp
    `made` and show moves the recorded run's id and clock. `engines` is enough's engines by name (`ctx.engines`), which
    the host fills (`enough.thym_host.engines()`) and a test may fake; a recorded run records every engine call and a
    replay answers them from the record (`engines.py`). `progress({node, of, name, move, state})` hears each node start
    (`running`) and end (`done`, `skipped`, `refused`); `should_stop()`, asked before each node, cancels the run
    (check `cancelled`), and nothing lands. `snapshots` is a recorded run's `inputs/` folder: its folder inputs are
    read from their snapshots there, never from the disk (a replay's, THYM 20.3). `calls` is a ceiling on the run's
    model requests (`--calls N`, THYM 12.5, 23.4): every request counts, re-asks included, and the one past it
    refuses the run, check `calls`."""
    return _Run(plan, inputs_root=inputs_root, coprocessor=coprocessor, root=root, rules=rules, agent_free=agent_free,
                preflight=preflight, program=program, decls=decls, moves=moves, checks=checks,
                environment=environment, destination=destination, record=record, run_id=run_id,
                made_run=made_run, now=now, replay_of=replay_of, engines=engines, progress=progress,
                should_stop=should_stop, snapshots=snapshots, calls=calls).go()


def replay(run_dir: Path | str, *, root: Path | str | None = None, inputs_root: Path | str | None = None,
           program: Any = None, decls: dict | None = None, moves: _registry.Moves | None = None,
           checks: _checks.Checks | None = None, environment: dict | None = None,
           engines: dict | None = None) -> Trace | Refusal:
    """Re-run a recorded run with the replay coprocessor (THYM.md 12.4) and compare its outputs with the recorded
    ones, byte for byte. The new run lands under `root` like any other; its values' `made` names the recorded run,
    and `trace.replay` says `{of, identical, differences}`. A difference is a conformance failure of the runtime.

    A run that recorded its engine calls (its trace's root item names `engines`) replays without any engine: every
    engine call is answered from its record (`engines.py`), and `engines` is not used. A run recorded before that
    replays with the `engines` given, the host's live ones. A replay that cannot match refuses at once (lesson 5 of
    checkpoint A): every input is held to the plan's digest at plan time, before any node runs, and a recorded call
    whose digest differs refuses at the call, before an engine or a model is asked anything."""
    run_dir = Path(run_dir)
    rid = run_dir.name
    plan_file = run_dir / f"{rid}.plan.cosm"
    if not plan_file.is_file():
        found = sorted(run_dir.glob("*.plan.cosm"))
        if not found:
            return Refusal("run", "replay", f"no plan in {run_dir}")
        plan_file = found[0]
        rid = plan_file.name[: -len(".plan.cosm")]
    trace_file = run_dir / f"{rid}.trace.cosm"
    tv = _trace.load(trace_file) if trace_file.is_file() else Refusal("run", "replay", f"no trace in {run_dir}")
    if isinstance(tv, Refusal):
        return tv
    # The plan file is not held to the trace's plan digest: a recorded run's input paths may be made relative to a
    # suite after the run (the frozen fixture's are), and the inputs' own digests are what the plan checks.
    plan = mc.yaml_load(mc.read_text(plan_file))
    head = _trace.root_item(tv)
    if program is None:
        kept = sorted(run_dir.glob("*.thym.cosm")) or sorted(run_dir.glob("*.thym"))
        program = kept[0] if kept else None
    names = recorded_names(head)
    eng: Any = Replaying(run_dir, names) if names is not None else engines
    t = run(plan, inputs_root=inputs_root or head.get("inputs_root") or run_dir,
            coprocessor=ReplayCoprocessor(run_dir), root=root, rules=bool(head.get("rules")), program=program,
            decls=decls, moves=moves, checks=checks, environment=environment, record=False,
            made_run=str(head.get("made_run") or rid), now=_trace.parse_utc(tv.get("started")), replay_of=rid,
            engines=eng, snapshots=run_dir / "inputs")
    if isinstance(t, Refusal):
        return t
    diffs: list[str] = []
    if t.outcome != tv.get("outcome"):
        diffs.append(f"the recorded run {tv.get('outcome')}, the replay {t.outcome}")
    recorded = {}
    for rec in _trace.records_of(tv):
        for row in rec.get("outputs") or []:
            if row.get("path"):
                recorded[row["name"]] = (row.get("sha256"), row["path"])
    for name, (sha, rel) in recorded.items():
        got = t.values.get(name)
        if got is None:
            diffs.append(f"{name}: the replay gave nothing")
            continue
        if got.sha256 != sha:
            diffs.append(f"{name}: sha256 {got.sha256[:12]}, recorded {str(sha)[:12]}")
        old = run_dir / rel
        new = t.outputs.get(name)
        if old.is_file() and new is not None and Path(new).is_file() and old.read_bytes() != Path(new).read_bytes():
            diffs.append(f"{name}: {rel} differs byte for byte from the recorded file")
        if old.is_dir() and new is not None and Path(new).is_dir() and _tree_files(old) != _tree_files(Path(new)):
            diffs.append(f"{name}: {rel} differs from the recorded folder")
    t.replay = {"of": rid, "identical": not diffs, "differences": diffs}
    return t
