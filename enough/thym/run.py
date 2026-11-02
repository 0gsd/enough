"""The runtime: a plan walked in order, deterministic moves run in code, model-backed moves sent to the coprocessor
behind their contracts, every run traced and replayable (docs/THYM.md 12, with 4.5, 8, 9, 11.1, 18 and 19).

`run(plan, ...)` takes a plan volume mapping (the shape of `tests/fixtures/thym/expected/*/plan.cosm`) and:

1. checks it against the environment, at plan time, before anything runs (THYM.md 9, 12.1, 19): agent-free (or
   `--rules`) with nodes that ask a model and have no scaffold is refused with their count and the first one's line;
   every input must be present with the digest the plan recorded; the `preflight` hook may refuse a plan whose largest
   prompt the machine's model cannot hold; every move must be declared and implemented here;
2. walks the nodes in a topological order (sequentially, plan order breaking ties). A node's call is read from its
   `name` (`band t3 as [none, some]`, `emit employees: mark t4 as verified`, `emit offer-line o, for each o in h where
   kind in [product, service, platform]`, `if now.medium is "phone" and now.hurry`, `assert f covers story`): the
   planner writes nested calls as temporaries, so a name is one flat statement. A deterministic node calls the
   registry; a model-backed one builds the contract from the declaration (`checks` = its `contract:` list) and the
   node's budget, sends the move's `Request` to the coprocessor, checks every candidate against the contract, repairs
   and retries within `attempts`, and refuses the whole run on failure. An `if` node evaluates its condition, and the
   nodes of the branch not taken are skipped; a `repeats` node walks its collection (a volume's items in told order, a
   short's lines, a list's members) and runs its call once per member; `emit` collects into the run's output volume
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
from enough.thym import registry as _registry
from enough.thym import trace as _trace
from enough.thym.coprocessor import RecordingCoprocessor, RefusingCoprocessor, ReplayCoprocessor
from enough.thym.coprocessor import ask as _ask
from enough.thym.coprocessor import prose_problem
from enough.thym.engines import CallCounter, EngineRefusal, Recording, Replaying, recorded_names
from enough.thym.registry import Amount, Request, Where, decl_get
from enough.thym.trace import Trace, default_root, digest_row, node_number, write_atomic
from enough.thym.values import NOTHING, Value, canonical, load_input, members, plain, sha256_bytes, stamp, wrap

MODIFIERS = ("as", "by", "with", "to", "against", "of", "in", "where", "marked")
UNITS = ("words", "sentences")
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


class _Reader:
    def __init__(self, text: str, moves: set[str]) -> None:
        self.text = text
        self.toks = _tokenize(text)
        self.i = 0
        self.moves = moves

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
            return Stmt("give", expr=self.expr())
        if self.at("let"):
            self.take()
            nm = self.name()
            self.expect("=")
            return Stmt("let", expr=self.expr(), name=nm)
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
        coll = self.primary()
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
            return Filter(p, cond, self.span(c0, self.i) or self.span(a, self.i))
        return p

    def call(self) -> Call:
        move = self.name()
        operands: list = []
        if not (self.at_end() or self.at_modifier() or self.at(")") or self.at("]") or self.at(",")
                or self.at("then") or self.at("else")):
            operands.append(self.primary())
            while self.at(",") and not self.at_trailer():
                self.take()
                operands.append(self.primary())
        mods: dict = {}
        while self.at_modifier():
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
                mods[w] = self.call() if self.at_move() else self.primary()
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

    def _term(self) -> Any:
        left = self.primary()
        if self.at("is"):
            self.take()
            neg = False
            if self.at("not"):
                self.take()
                neg = True
            return Cmp("is not" if neg else "is", left, self.rhs_word())
        if self.at("in"):
            self.take()
            return Cmp("in", left, self.primary())
        for op in ("<", ">", "="):
            if self.at(op):
                self.take()
                return Cmp(op, left, self.primary())
        if self.at("has"):
            self.take()
            return Has(left, self.name())
        if self.at("covers"):
            self.take()
            return Covers(left, self.primary())
        return Bare(left)

    def rhs_word(self) -> Any:
        t = self.peek()
        if t[0] == "name" and not self.at(".", 1) and t[1] not in ("true", "false", "nothing"):
            self.take()
            return Lit(Value("word", t[1]))
        return self.primary()


def _unquote(s: str) -> str:
    return s[1:-1].replace('\\"', '"').replace("\\\\", "\\")


def _name_of(e: Any) -> str:
    return e.name if isinstance(e, Name) else str(e)


def read_statement(text: str, moves: set[str] | frozenset[str]) -> Stmt:
    """One statement, read with the names of the moves in scope (a name that is a move begins a call). Raises
    `ReadError`."""
    return _Reader(text, set(moves)).statement()


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
        return f"{_expr_text(c.left)} {c.op} {_expr_text(c.right)}"
    if isinstance(c, Has):
        return f"{_expr_text(c.base)} has {c.name}"
    if isinstance(c, Covers):
        return f"{_expr_text(c.left)} covers {_expr_text(c.right)}"
    if isinstance(c, Bare):
        return _expr_text(c.expr)
    return str(c)


def _expr_text(e: Any) -> str:
    if isinstance(e, Name):
        return e.name
    if isinstance(e, Lit):
        v = e.value
        return f'"{v.payload}"' if v.type == "string" else str(v.plain() if v.type != "nothing" else "nothing")
    if isinstance(e, FieldRead):
        return f"{_expr_text(e.base)}.{e.name}"
    if isinstance(e, ListLit):
        return "[" + ", ".join(_expr_text(x) for x in e.items) + "]"
    if isinstance(e, Call):
        return f"{e.move} " + ", ".join(_expr_text(o) for o in e.operands)
    if isinstance(e, Filter):
        return f"{_expr_text(e.base)} where {e.text}"
    return str(e)


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
    `("stmt", line, text)`, `("if", line, text, then, else)` or `("for", line, text, body)`."""
    name: str
    params: list
    gives: str | None
    body: list


_LET = re.compile(r"^let\s+([a-z][a-z0-9-]*)\s*=\s*(.+)$")
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

    @classmethod
    def from_any(cls, program: Any) -> "ProgramInfo":
        """From a program volume mapping (the enumeration, `<name>.thym.cosm`), a `.thym` source text, a path to
        either, or None."""
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
                return cls.from_items(data) if isinstance(data, dict) else cls()
            return cls.from_source(text)
        if isinstance(program, dict):
            return cls.from_items(program)
        if isinstance(program, str):
            return cls.from_source(program)
        return cls()

    @classmethod
    def from_items(cls, vol: dict) -> "ProgramInfo":
        info = cls()
        nodes = [n for n in vol.get("nodes") or [] if isinstance(n, dict)]
        by_id = {n.get("id"): n for n in nodes}
        prog = next((n for n in nodes if n.get("type") == "program"), None)
        if prog is not None:
            info.name = prog.get("name")
            info.takes = [(t.get("name"), t.get("type")) for t in prog.get("takes") or [] if isinstance(t, dict)]
            gv = [g for g in prog.get("gives") or [] if isinstance(g, dict)]
            info.gives = (gv[0].get("name"), gv[0].get("type")) if gv else None
        for st in nodes:
            if st.get("type") != "step":
                continue
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
        return info

    @classmethod
    def from_source(cls, text: str) -> "ProgramInfo":
        """Read from the `.thym` text itself, line by line (a statement is one line, THYM.md 4.8)."""
        info = cls()
        stack: list[dict] = []
        prose = False

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
                    info.name = s.split()[1]
                    stack.append({"kind": "program", "body": []})
                elif first == "move":
                    mt = _MOVE_HEAD.match(s)
                    um = UserMove(mt.group(1), _params(mt.group(2)), mt.group(3).strip(), []) if mt else None
                    stack.append({"kind": "move", "body": [], "move": um})
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
            if prose and first not in ("takes", "gives", "end"):
                continue
            prose = False
            if first == "takes":
                if top["kind"] == "program":
                    info.takes = _params(s[len("takes"):])
                continue
            if first == "gives":
                if top["kind"] == "program":
                    g = _params(s[len("gives"):])
                    info.gives = g[0] if g else None
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
                elif f["kind"] == "if" and stack:
                    current(stack[-1]).append(("if", f["line"], f["text"], f["then"], f["else"]))
                elif f["kind"] == "for" and stack:
                    current(stack[-1]).append(("for", f["line"], f["text"], f["body"]))
                continue
            if s == "else" and top["kind"] == "if":
                top["in_else"] = True
                continue
            if first == "if":
                stack.append({"kind": "if", "line": ln, "text": s, "then": [], "else": [], "in_else": False})
                continue
            if first == "for":
                stack.append({"kind": "for", "line": ln, "text": s, "body": []})
                continue
            current(top).append(("stmt", ln, s))
            mt = _LET.match(s)
            if mt and not any(f["kind"] == "move" for f in stack):      # a move's lets are its own (THYM.md 5.4)
                info.lets.setdefault(mt.group(1), mt.group(2).strip())
            if first == "assert":
                mm = _ELSE_MSG.search(s)
                if mm:
                    info.messages[ln] = _unquote(f'"{mm.group(1)}"')
        return info


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

    def withhold(self, *items: Any) -> None:
        """Mark items withheld from the projection (THYM.md 18): values (items, or a list of them) or ids."""
        for x in items:
            if isinstance(x, (list, tuple)):
                self.withhold(*x)
            elif isinstance(x, Value) and x.type == "list":
                self.withhold(*(x.payload or []))
            elif isinstance(x, Value):
                iid = (x.origin or {}).get("id") or (x.mapping() or {}).get("id")
                if iid:
                    self.withheld[str(iid)] = x
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
    def __init__(self, refusal: Refusal) -> None:
        super().__init__(str(refusal))
        self.refusal = refusal


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
        stuck = [k for k in waiting if k not in {o.get("id") for o in out}]
        return Refusal("plan", "plan-acyclic", f"the plan's nodes wait on each other: {', '.join(map(str, stuck))}")
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
            self.info = ProgramInfo.from_any(self.program)
        except (OSError, ValueError) as e:
            return Refusal("plan", "program", f"the program could not be read: {e}")
        self.move_names = frozenset(set(self.decls) | set(self.info.moves))
        est = self.plan.get("estimate") if isinstance(self.plan.get("estimate"), dict) else {}
        self.largest_prompt = int(self.head.get("largest_prompt") or est.get("largest_prompt") or 0)
        return self._environment()

    def _body_moves(self, name: str, seen: frozenset[str] = frozenset()) -> set[str]:
        """The declared moves a user move calls, through the user moves it calls (THYM.md 8.3)."""
        out: set[str] = set()
        um = self.info.moves.get(name)
        if um is None or name in seen:
            return out

        def walk(body: list) -> None:
            for part in body:
                try:
                    st = read_statement(part[2], self.move_names)
                except ReadError:
                    continue
                for m in calls_in(st):
                    if m in self.info.moves:
                        out.update(self._body_moves(m, seen | {name}))
                    else:
                        out.add(m)
                for sub in part[3:]:
                    if isinstance(sub, list):
                        walk(sub)
        walk(um.body)
        return out

    def _moves_of(self, node: dict) -> list[str]:
        m = node.get("move")
        return sorted(self._body_moves(m)) if m in self.info.moves else [m]

    def _environment(self) -> Refusal | None:
        asks = [n for n in self.nodes if n.get("asks") is True]
        if asks and (self.agent_free or self.rules):
            blocked = asks
            if self.rules:
                def bare(m: Any) -> bool:
                    return not decl_get(self.decls.get(m), "scaffold")

                def unscaffolded(n: dict) -> bool:
                    inner = any(decl_get(self.decls.get(m), "asks") is True and bare(m) for m in self._moves_of(n))
                    return inner or (n.get("move") not in self.info.moves and bare(n.get("move")))
                blocked = [n for n in asks if unscaffolded(n)]
            if blocked:
                k = len(blocked)
                many = f"{k} step{'s' if k != 1 else ''} ask{'' if k != 1 else 's'} a model"
                if self.rules:
                    many += f" and {'have' if k != 1 else 'has'} no scaffold"
                why = "agent-free is on" if self.agent_free else "--rules runs no model"
                return Refusal("plan", "agent-free" if self.agent_free else "rules", f"{many}; {why}",
                               line=blocked[0].get("line"))
        for spec in self.plan.get("inputs") or []:
            if not isinstance(spec, dict):
                continue
            v = load_input(spec, self.inputs_root)
            if isinstance(v, Refusal):
                return v
            name = str(spec.get("name"))
            self.inputs[name] = v
            self.input_paths[name] = str(spec.get("path"))
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
                    hint = ("; a move the program defines needs the program beside the plan (its items or its .thym "
                            "file)" if self.program is None else "")
                    return Refusal("plan", "unknown-move", f"node {node_number(n.get('id'))}: the move {m} is not "
                                   f"declared and the program defines no move of that name{hint}", line=line)
                if decl_get(decl, "asks") is True and self.rules:
                    if self.moves.scaffold(decl) is None:
                        return Refusal("plan", "move", f"the scaffold of {m} ({decl_get(decl, 'scaffold')}) has no "
                                                       "implementation here", line=line)
                elif self.moves.lookup(m) is None:
                    why = next((p.split(": ", 1)[1] for p in self.load_problems if p.startswith(f"{m}: ")), None)
                    return Refusal("plan", "move", f"the move {m} has no implementation here"
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
        self.output_name = self._output_name()
        refusal: Refusal | None = None
        stopped: str | None = None
        total = len(self.order)
        for i, node in enumerate(self.order, 1):
            if self.should_stop is not None and self.should_stop():
                refusal = Refusal("run", "cancelled", f"the run was cancelled before node {node_number(node.get('id'))}; "
                                                      "nothing landed", line=node.get("line"))
                stopped = f"R:record/{node_number(node.get('id'))}"
                break
            self._tell(i, total, node, "running")
            try:
                refusal = self._node(node)
            except _Stop as s:                    # pragma: no cover - _node catches its own
                refusal = s.refusal
            except Exception as e:  # noqa: BLE001 - a runtime fault refuses the run with its words; never half-lands
                refusal = Refusal("run", "runtime", f"node {node_number(node.get('id'))}: {type(e).__name__}: {e}",
                                  line=node.get("line"))
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
        text = str(node.get("name") or "").strip() or " ".join([str(node.get("move"))] + list(node.get("takes") or []))
        try:
            st = read_statement(text, self.move_names)
        except ReadError as e:
            r = Refusal("run", "parse", f"node {node_number(nid)} ({text}): {e}", line=node.get("line"))
            self._record(node, r)
            return r
        scope = _Scope(self.env, True)
        try:
            if st.form == "if":
                self.if_results[nid] = self._cond(st.cond, scope)
            elif st.form == "assert":
                self._assert(st, scope)
            elif st.loop is not None:
                self._repeat(st, scope)
            else:
                self._deliver(st, self._eval(st.expr, scope), node)
        except _Stop as s:
            r = s.refusal
            r = r if r.line else Refusal(r.stage, r.check, r.message, line=node.get("line"), file=r.file)
            self._record(node, r)
            return r
        if st.loop is None:
            self.cur.attempts = max(self.cur.attempts, 1)      # a condition, an assert, a plain emit ran once
        self._record(node)
        return None

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
                            tries=cur.tries)
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
        loop = st.loop
        coll = self._eval(loop.coll, scope)
        rows = members(coll)
        if rows is None:
            raise _Stop(Refusal("run", "type",
                                f"{_expr_text(loop.coll)} is a {coll.type}, which a for each cannot walk"))
        if loop.cond is not None:
            rows = [r for r in rows if self._cond(loop.cond, scope, item=r)]
        outs = []
        for k, r in enumerate(rows, 1):
            v = self._eval(st.expr, scope.child({loop.var: r}))
            self._deliver(st, v, self.cur.node, k)
            outs.append(v)
        g = self.cur.node.get("gives")
        if isinstance(g, str):
            self.env[g] = Value("list", outs)

    def _assert(self, st: Stmt, scope: _Scope) -> None:
        ok = self._cond(st.cond, scope)
        check = "coverage" if _has_covers(st.cond) else "assert"
        line = self.cur.node.get("line") if self._move_stack == [] else None
        msg = st.message or (self.info.messages.get(line) if line else None) or f"{_cond_text(st.cond)} does not hold"
        if check == "coverage":
            for c in self.cur.checks:
                if c.get("name") == "coverage" and not c.get("ok") and c.get("why"):
                    msg = f"{msg} ({c['why']})"
                    break
        else:
            self.cur.checks.append({"name": "assert", "ok": ok, "why": "" if ok else msg})
        if not ok:
            raise _Stop(Refusal("run", check, msg))

    # -- values ---------------------------------------------------------------------------------------------------

    def _lookup(self, name: str, scope: _Scope, item: Value | None) -> Value:
        if name in scope.vars:
            return scope.vars[name]
        if scope.program and name in self.info.lets and name not in self._let_busy:
            try:
                e = read_expression(self.info.lets[name], self.move_names)
            except ReadError as err:
                raise _Stop(Refusal("run", "parse", f"let {name} = {self.info.lets[name]}: {err}")) from None
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
        hint = ("; it is a let the plan folded into this node, so run with the program beside the plan"
                if self.program is None and scope.program else "")
        raise _Stop(Refusal("run", "unbound", f"{name} is not bound{hint}"))

    def _eval(self, e: Any, scope: _Scope, item: Value | None = None) -> Value:
        if isinstance(e, Name):
            return self._lookup(e.name, scope, item)
        if isinstance(e, Lit):
            return e.value
        if isinstance(e, ListLit):
            return Value("list", [self._eval(x, scope, item) for x in e.items])
        if isinstance(e, FieldRead):
            return wrap(self._eval(e.base, scope, item).field(e.name))
        if isinstance(e, Filter):
            base = self._eval(e.base, scope, item)
            rows = members(base)
            if rows is None:
                raise _Stop(Refusal("run", "type", f"{_expr_text(e.base)} is a {base.type}, which where cannot filter"))
            return Value("list", [r for r in rows if self._cond(e.cond, scope, item=r)])
        if isinstance(e, Call):
            return self._call(e, scope, item)
        raise _Stop(Refusal("run", "parse", f"cannot evaluate {e!r}"))

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
            a = self._eval(c.left, scope, item).plain()
            b = self._eval(c.right, scope, item).plain()
            if c.op == "is":
                return _eq(a, b)
            if c.op == "is not":
                return not _eq(a, b)
            if c.op == "in":
                return isinstance(b, list) and any(_eq(a, x) for x in b)
            if c.op == "=":
                return _eq(a, b)
            if isinstance(a, bool) or isinstance(b, bool) or not isinstance(a, int) or not isinstance(b, int):
                return False
            return a < b if c.op == "<" else a > b
        raise _Stop(Refusal("run", "parse", f"cannot evaluate the condition {c!r}"))

    # -- calls ----------------------------------------------------------------------------------------------------

    def _ctx(self) -> MoveContext:
        return MoveContext(run=self.made_run, node=dict(self.cur.node), decls=self.decls, coprocessor=self.coproc,
                           rules=self.rules, now=self.started, emitted=self.emitted, slots=self.slots,
                           withheld=self.withheld, inputs_root=self.inputs_root, root=self.root, stage=self.stage,
                           program=self.info, trace_fn=self._trace_so_far, engines=self.engines,
                           calls=self.cur.calls if self.cur is not None else None)

    def _trace_so_far(self) -> dict:
        self.trace.records = list(self.records)
        return self.trace.to_volume()

    def _made(self, move: str, engine: str) -> dict:
        step = self.cur.node.get("step")
        n = step.get("n") if isinstance(step, dict) else None
        return {"move": move, "run": self.made_run, "step": n, "node": node_number(self.cur.node.get("id")),
                "engine": engine}

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
            fn = self.moves.scaffold(decl)
            if fn is None:
                raise _Stop(Refusal("run", "rules", f"{move} asks a model and has no scaffold; --rules runs no model"))
            r = self._invoke(move, fn, ctx, operands, mods)
            if isinstance(r, Request):
                raise _Stop(Refusal("run", "rules", f"the scaffold of {move} asked the model"))
            v = stamp(self._as_value(r, decl), self._made(move, "rules"), pending=True)
            self.cur.state = "pending"
            self._settle(move, decl, v, inputs, check_node, "rules")
            return v
        fn = self.moves.lookup(move)
        if fn is None:
            raise _Stop(Refusal("run", "move", f"the move {move} has no implementation here"))
        r = self._invoke(move, fn, ctx, operands, mods)
        if isinstance(r, Request):
            if not asks:
                raise _Stop(Refusal("run", "asks", f"{move} is declared deterministic, and it asked the model"))
            return self._ask_model(move, decl, r, inputs, check_node)
        pending = any(isinstance(x, Value) and x.state == "pending" for x in inputs.values())
        # what is made from a scaffold's output is pending too
        v = stamp(self._as_value(r, decl), self._made(move, "code"), pending=pending)
        if pending:
            self.cur.state = "pending"
        self._settle(move, decl, v, inputs, check_node, "code")
        return v

    def _invoke(self, move: str, fn: Callable, ctx: MoveContext, operands: list, mods: dict) -> Any:
        try:
            return fn(ctx, *operands, **mods)
        except _Stop:
            raise
        except EngineRefusal as e:                      # a replayed engine call that does not match its record
            raise _Stop(e.refusal) from None
        except Exception as e:  # noqa: BLE001 - THYM.md 9: a deterministic move that raises refuses the run
            raise _Stop(Refusal("run", "move", f"{move} raised {type(e).__name__}: {e}")) from None

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
            raise _Stop(Refusal("run", bad["name"], f"{move} at node {node_number(node.get('id'))}: "
                                                    f"{bad['why'] or 'the check does not hold'}"))

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
        n = node_number(self.cur.node.get("id"))
        key = self.cur.calls.request_key()
        last: list[dict] = []
        engine = "model:unknown"
        for attempt in range(1, attempts + 1):
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
                value = stamp(value, self._made(move, engine))
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
                        value = stamp(self._as_value(fixed, decl), self._made(move, engine))
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
            contract["repair"] = {"allowed": allowed, "failed": [dict(x) for x in failed]}
        self._merge_checks(last)
        bad = next((x for x in last if not x["ok"]), {"name": "schema", "why": "no answer"})
        tries = f"{attempts} attempt{'s' if attempts != 1 else ''}"
        why = f": {bad['why']}" if bad.get("why") else ""
        raise _Stop(Refusal("run", bad["name"], f"{move} at node {n} still fails {bad['name']} after {tries}{why}"))

    # -- user moves (THYM.md 8.3) ---------------------------------------------------------------------------------

    def _user_move(self, name: str, operands: list) -> Value:
        um: UserMove = self.info.moves[name]
        if len(operands) != len(um.params):
            raise _Stop(Refusal("run", "type",
                                f"{name} takes {len(um.params)} operand(s); it was given {len(operands)}"))
        if name in self._move_stack:
            raise _Stop(Refusal("run", "recursion", f"{name} calls itself"))
        scope = _Scope({p[0]: v for p, v in zip(um.params, operands)}, program=False)
        self._move_stack.append(name)
        try:
            out = self._body(um.body, scope)
        finally:
            self._move_stack.pop()
        if out is None:
            raise _Stop(Refusal("run", "no-give", f"{name} reached its end without a give"))
        return out

    def _body(self, body: list, scope: _Scope) -> Value | None:
        for part in body:
            if part[0] == "if":
                st = self._read_stmt(part[2])
                out = self._body(part[3] if self._cond(st.cond, scope) else part[4], scope.child({}))
                if out is not None:
                    return out
            elif part[0] == "for":
                st = self._read_stmt(part[2])
                coll = self._eval(st.loop.coll, scope)
                rows = members(coll) or []
                if st.loop.cond is not None:
                    rows = [r for r in rows if self._cond(st.loop.cond, scope, item=r)]
                for r in rows:
                    self._body(part[3], scope.child({st.loop.var: r}))
            else:
                st = self._read_stmt(part[2])
                if st.form == "give":
                    return self._eval(st.expr, scope)
                if st.form == "let":
                    scope.vars[st.name] = self._eval(st.expr, scope)
                elif st.form == "assert":
                    self._assert(st, scope)
                elif st.form == "emit":
                    v = self._eval(st.expr, scope)
                    (self.slots.__setitem__(st.slot, v) if st.slot else self.emitted.append(v))
                elif st.expr is not None:
                    self._eval(st.expr, scope)
        return None

    def _read_stmt(self, text: str) -> Stmt:
        try:
            return read_statement(text, self.move_names)
        except ReadError as e:
            raise _Stop(Refusal("run", "parse", f"{text}: {e}")) from None

    # -- landing (THYM.md 12.1: every output or none) -------------------------------------------------------------

    def _land(self) -> Refusal | None:
        name = self.output_name
        landed: dict[str, Path] = {}
        if name:
            v = self.env.get(name)
            if v is None:
                return Refusal("run", "no-give", f"the program gives {name}, and no node gave it")
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
                if row.get("name") == name and name in landed:
                    row["path"] = str(landed[name])
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


def _alternatives(x: Any) -> list[str]:
    """A declaration's type alternatives, whether written `'item | word'` (a manifest) or `('item', 'word')` (the
    compiler's `MoveDecl`)."""
    if x is None:
        return []
    parts = [x] if isinstance(x, str) else [str(p) for p in x] if isinstance(x, (list, tuple)) else [str(x)]
    return [a.strip() for p in parts for a in p.split("|") if a.strip()]


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
        should_stop: Callable[[], bool] | None = None) -> Trace | Refusal:
    """Run a plan (THYM.md 12.1). `inputs_root` is the folder the plan's input paths are relative to; `program` the
    program's items or `.thym` source (needed for let filters and user moves); `coprocessor` answers model-backed
    nodes (default: refusing); `root` is where runs live (default `ENOUGH_THYM_ROOT`, else `~/enough/thym/`);
    `preflight(plan)` may refuse on size; `destination` is a folder the output is also copied into once it lands.
    `record` wraps the coprocessor so every candidate is kept for replay. `made_run` and `now` let a replay stamp
    `made` and show moves the recorded run's id and clock. `engines` is enough's engines by name (`ctx.engines`), which
    the host fills (`enough.thym_host.engines()`) and a test may fake; a recorded run records every engine call and a
    replay answers them from the record (`engines.py`). `progress({node, of, name, move, state})` hears each node start
    (`running`) and end (`done`, `skipped`, `refused`); `should_stop()`, asked before each node, cancels the run
    (check `cancelled`), and nothing lands."""
    return _Run(plan, inputs_root=inputs_root, coprocessor=coprocessor, root=root, rules=rules, agent_free=agent_free,
                preflight=preflight, program=program, decls=decls, moves=moves, checks=checks,
                environment=environment, destination=destination, record=record, run_id=run_id,
                made_run=made_run, now=now, replay_of=replay_of, engines=engines, progress=progress,
                should_stop=should_stop).go()


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
            engines=eng)
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
    t.replay = {"of": rid, "identical": not diffs, "differences": diffs}
    return t
