"""A checked program planned into a `thym/1` plan volume: what it will do, before it does it (THYM.md 11.1, 12.5,
17.1, 17.3; stages 5 and 7 of section 11.1).

The nodes come in evaluation order, a nested call before the call that takes its value:

- outside a loop's body, one node per move call, a `marked` modifier included (a `mark` node of its own), and one
  per `assert`; a call of a user move is one node;
- one node per `if`, for its condition; each node of a branch says which branch it is in and waits on the condition;
- for a `for each`, one node per statement of its body (THYM 11.1): for each member when the collection is a list
  written in the program (the node binds the loop variable to that member, `, for x = <member>`), otherwise once,
  marked `repeats`, taking the collection (`, for each …`). A call nested inside a statement of a loop's body,
  `marked` included, is part of that statement's node (it is *folded*, `_Planner.fold`) and is evaluated with each
  member; it is never a node of its own and makes no temporary. A statement of a loop's body that holds one call and
  nothing nested in it is planned exactly as it always was, so the plans of such loops are unchanged;
- no node for a `let` whose value is not a call: a filter, a name or a field folds into the node that takes it, which
  then takes what the filter reads and spans its line. A call-less `emit` or `give` is a node of its own (`emit`,
  `give`), so that the plan says everything the run does.

A `give` gives the output it names (`give code: …`) or the block's one output; a program of several outputs has a node
giving each (THYM 8.2). A folder input's row is `{name, type: folder, path, sha256: <tree digest>, files, bytes}`
(THYM 20.3). In `thym 1`, a loop whose collection is a call names its nodes with the call's temporary in the trailer
(`, for each l in t2 where …`), so the runtime walks what that node gave and asks for nothing again.

Both grammar versions plan by these rules, and `thym 1` adds three (THYM 11.1, 12.5, 17.3):

- **the loop node**: a `for each` over a collection known only at run time whose body is more than one plain statement
  (a `let`, `assert`, `emit`, `withhold` or a move run for its effect) is one node, named by the loop's own line, move
  `for`, `repeats`, taking the names its collection, its `where` and its body read from outside the loop, with
  `calls` (every move its header and its body call, in written order, once each); its body runs member by member as a
  unit at run time. A loop of one plain statement gives exactly the `thym 0` node. A `for each` nested inside a loop
  over a written list (which is still unrolled, one node per statement per member) is a loop node too, named with the
  outer member's trailer (`, for x = <member>`), so that it sees that member;
- **the collect node**: a loop that collects (`let xs = for each …`) is one node in every case, move `for`, `gives`
  the loop's name, `repeats`, `calls`; both loop nodes carry `members: {at_most: n}` when the collection's size is known
  from the plan itself (a written list; a folder input, or a filter of one, by its row's `files`, counted before any
  `where`). A volume's or a fabula's count of items is in no input row, and reading it would make a plan depend on
  where it was made from, so it is left out (the count is then open);
- **keeps and depth**: a node that calls a user move that keeps contracts carries `keeps` (their names), and one that
  calls a move that may call itself carries the move's `depth` in its budget; the node that gives a program's output
  carries what the program keeps of that output.

**The count of model calls** (THYM 23.2). Given `models` (the route the host chose: `route`, `provider`, `model`,
`window`), a plan whose nodes ask carries the catalog key `models`: those keys with `calls` (the requests the plan
makes when every check passes the first time: a node's asking call sites, times its members when it repeats),
`at_most` (each node's calls times its attempts) and `calls_open` (the nodes whose count nobody can know before the
run: a loop over a collection of unknown size, a move that calls itself, a loop inside a move). `normalise` drops it:
the route is the run's, not the program's.

A node takes names (inputs, bindings, or a temporary `t<n>` made by the nested call at node n) and gives at most
one: its binding, the block's `gives` name, or a temporary. It runs after the nodes whose outputs it takes; the node
that gives the program's output also runs after every `assert`, `emit` and `withhold` before it on its path, and
`after` leaves out any node another in the list already runs after. A node's budget is 3 attempts when it asks the
model, else 1, and the call's `to N words`, else 0. A node's name is its call as written, nested calls replaced by
their temporaries; its summary is its line's comment, else its name; the root's summary counts the nodes and those
that ask (section 10). The estimate counts the nodes, those that ask, the largest
`to N words`, and the largest prompt: the characters of the inputs that reach the largest model-backed node,
divided by four.

The run id is `<YYYY-MM-DD-HHMM>-<four hex>`, local time and the first four hex digits of the sha256 of the program's
sha256 followed by every input's. `normalise` gives what conformance compares: run ids as `fixture`, the catalog id
`thym/plan.<program>`, `largest_prompt` 0, and no timestamps.
"""
from __future__ import annotations

import copy
import datetime as _dt
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import MINICOSM, Refusal
from . import check as ck
from . import enumerate as en
from . import folder as fd
from . import parse as ps
from .values import posix_path

_NUMBERS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
            "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty")


@dataclass(eq=False)
class PlanNode:
    """One node of a plan, with the tree it came from: `stmt` (the statement), `expr` (the call, `marked`, `assert`
    condition or `if` condition it runs), `step` (the statement's number in its block), `subst` (the temporaries
    that stand for the nested calls it takes)."""
    n: int
    kind: str                      # call, mark, assert, if, emit, give
    move: str
    stmt: ps.Stmt
    expr: Any
    step: int
    takes: list[str]
    gives: str | None = None
    asks: bool = False
    deps: list[int] = field(default_factory=list)          # nodes whose outputs it takes
    after: list[int] = field(default_factory=list)
    branch: str | None = None
    path: tuple = ()
    repeats: bool = False
    loop: ps.For | None = None
    member: Any = None
    slot: str | None = None
    emits: bool = False
    gives_output: bool = False
    own: bool = False
    output_words: int = 0
    lines: tuple[int, int] = (0, 0)
    subst: dict[int, str] = field(default_factory=dict)
    name: str = ""
    summary: str = ""
    inputs: set[str] = field(default_factory=set)
    folded: bool = False           # a statement of a loop's body with its nested calls folded in (THYM 11.1)
    calls: list[str] | None = None  # a loop node's moves, in written order (`thym 1`)
    over: Any = None               # a loop node's collection, for `members` (`thym 1`)
    keeps: list[str] = field(default_factory=list)
    depth: int | None = None


@dataclass
class _Env:
    givers: dict[str, int]
    aliases: dict[str, tuple[list[str], set[int]]]
    branch: str | None = None
    path: tuple = ()
    cond: int | None = None
    loop: ps.For | None = None
    loop_names: tuple[list[str], set[int]] | None = None
    member: Any = None

    def child(self, **kw) -> "_Env":
        env = _Env(dict(self.givers), dict(self.aliases), self.branch, self.path, self.cond, self.loop,
                   self.loop_names, self.member)
        for k, v in kw.items():
            setattr(env, k, v)
        return env


def _once(xs: list[str]) -> list[str]:
    out: list[str] = []
    for x in xs:
        if x not in out:
            out.append(x)
    return out


class _Planner:
    def __init__(self, checked: ck.Checked, block: ps.Block):
        self.c, self.b = checked, block
        self.nodes: list[PlanNode] = []
        self.checkpoints: list[int] = []
        self.temps: dict[str, int] = {}
        order = list(ck.walk(block.stmts))
        self.num = {id(s): k + 1 for k, s in enumerate(order)}
        self.inputs = {p.name for p in block.takes}
        self.loop_sub: dict[int, dict[int, str]] = {}      # a thym 1 loop over a call: the call's temporary

    # -- names -------------------------------------------------------------

    def names(self, x: Any, env: _Env, sub: dict[int, str], stmt: ps.Stmt,
              fold: bool = False) -> tuple[list[str], set[int]]:
        """The names a part of a statement takes, making a node (a temporary) for every call inside it first; with
        `fold`, a call inside it makes no node, and the names its operands and modifiers take are taken instead."""
        if isinstance(x, (ps.Call, ps.Marked)) and not fold:
            temp = self.expr(x, env, stmt, role="temp")
            sub[id(x)] = temp
            return [temp], set()
        if isinstance(x, ps.Paren):
            names, lines = self.names(x.inner, env, sub, stmt, fold)
            if id(x.inner) in sub:
                sub[id(x)] = sub[id(x.inner)]
            return names, lines
        if isinstance(x, ps.Name):
            if x.kind != "binding":
                return [], set()
            if env.loop is not None and x.name == env.loop.var:
                if env.loop_names is not None:
                    return list(env.loop_names[0]), set(env.loop_names[1])
                if env.member is not None:                  # a written list's member: what it names, if a binding
                    return self.names(env.member, env.child(loop=None, member=None), sub, stmt, True)
                return [], set()
            if x.name in env.aliases:
                names, lines = env.aliases[x.name]
                return list(names), set(lines)
            return [x.name], set()
        out: list[str] = []
        lines: set[int] = set()
        for ch in ck.children(x):
            n, ls = self.names(ch, env, sub, stmt, fold)
            out.extend(n)
            lines |= ls
        return out, lines

    # -- nodes -------------------------------------------------------------

    def add(self, node: PlanNode, env: _Env, extra_lines: set[int]) -> PlanNode:
        node.n = len(self.nodes) + 1
        node.branch, node.path = env.branch, env.path
        node.loop, node.member = env.loop, env.member
        node.repeats = env.loop is not None and env.member is None
        node.takes = _once(node.takes)
        deps: list[int] = []
        for name in node.takes:
            if name in self.temps:
                deps.append(self.temps[name])
            elif name in env.givers:
                deps.append(env.givers[name])
        node.deps = sorted(set(deps))
        after = set(node.deps)
        if env.cond is not None:
            after.add(env.cond)
        if node.gives_output:
            for k in self.checkpoints:
                kp = self.nodes[k - 1].path
                if node.path[:len(kp)] == kp:
                    after.add(k)
        node.after = sorted(after)
        st = node.stmt
        lo, hi = st.line, st.header_end or st.line
        lines = set(extra_lines)
        if node.repeats and env.loop is not None:
            lines |= {env.loop.line, env.loop.end}
        if env.loop_names is not None and node.repeats:
            lines |= env.loop_names[1]
        node.lines = (min([lo] + list(lines)), max([hi] + list(lines)))
        node.step = self.num[id(st)]
        node.inputs = {t for t in node.takes if t in self.inputs}
        for d in node.deps:
            node.inputs |= self.nodes[d - 1].inputs
        if node.gives:
            if node.gives.startswith("t") and node.gives[1:].isdigit() and node.gives == f"t{node.n}":
                self.temps[node.gives] = node.n
            else:
                env.givers[node.gives] = node.n
        self.nodes.append(node)
        if node.emits or node.kind == "assert" or node.move == "withhold":
            self.checkpoints.append(node.n)
        return node

    def kept(self, node: PlanNode, calls: list[Any]) -> None:
        """What a node's calls of user moves keep, and the depth of the first that may call itself (`thym 1`)."""
        for c in calls:
            t = getattr(c, "target", None)
            if isinstance(t, ck.UserMove):
                node.keeps = _once(node.keeps + t.keeps)
                if node.depth is None and t.depth is not None:
                    node.depth = t.depth

    def expr(self, e: Any, env: _Env, stmt: ps.Stmt, role: str) -> str:
        """Nodes for a call or a `marked` (its nested calls first); returns what the outermost gives."""
        e = ck.strip_paren(e)
        sub: dict[int, str] = {}
        takes: list[str] = []
        lines: set[int] = set()
        if isinstance(e, ps.Marked):
            n, ls = self.names(e.inner, env, sub, stmt)
            kind, move, target = "mark", "mark", e.target
        else:
            for part in list(e.operands) + [m.arg for m in e.mods]:
                n, ls = self.names(part, env, sub, stmt)
                takes.extend(n)
                lines |= ls
            n, ls = [], set()
            kind, move, target = "call", e.move, e.target
        takes.extend(n)
        lines |= ls
        node = PlanNode(0, kind, move, stmt, e, 0, takes, subst=sub)
        self.kept(node, [e])
        node.asks = bool(getattr(target, "asks", False))
        node.own = e is ck.own_call(stmt)
        if isinstance(e, ps.Call):
            to = e.mod("to")
            if to is not None and isinstance(to.arg, ps.Units) and to.arg.unit == "words":
                node.output_words = to.arg.count
        size = len(self.nodes) + 1
        if role == "temp":
            node.gives = f"t{size}"
        elif role.startswith("bind:"):
            node.gives = role[5:]
        elif role.startswith("out:"):
            node.gives = role[4:]
            node.gives_output = True
        elif role.startswith("emit"):
            node.emits = True
            node.slot = role[5:] or None
        self.add(node, env, lines)
        return node.gives or ""

    def simple(self, kind: str, move: str, stmt: ps.Stmt, expr: Any, env: _Env, *, gives: str | None = None,
               output: bool = False, emits: bool = False, slot: str | None = None) -> PlanNode:
        sub: dict[int, str] = {}
        takes, lines = self.names(expr, env, sub, stmt)
        node = PlanNode(0, kind, move, stmt, expr, 0, takes, gives=gives, gives_output=output, emits=emits,
                        slot=slot, subst=sub)
        return self.add(node, env, lines)

    # -- statements --------------------------------------------------------

    def stmts(self, stmts: list[ps.Stmt], env: _Env) -> None:
        for s in stmts:
            self.stmt(s, env)

    def stmt(self, s: ps.Stmt, env: _Env) -> None:
        if env.loop is not None and _nests(s):
            self.fold(s, env)
            return
        top = ck.strip_paren(getattr(s, "expr", None))
        is_call = isinstance(top, (ps.Call, ps.Marked))
        if isinstance(s, ps.Let):
            if is_call:
                self.expr(top, env, s, role=f"bind:{s.name}")
            else:
                sub: dict[int, str] = {}
                names, lines = self.names(s.expr, env, sub, s)
                env.aliases[s.name] = (_once(names), lines | {s.line})
        elif isinstance(s, ps.Assert):
            self.simple("assert", "assert", s, s.cond, env)
        elif isinstance(s, ps.If):
            node = self.simple("if", "if", s, s.cond, env)
            self.stmts(s.then, env.child(branch="then", path=env.path + ((node.n, "then"),), cond=node.n))
            if s.else_ is not None:
                self.stmts(s.else_, env.child(branch="else", path=env.path + ((node.n, "else"),), cond=node.n))
        elif isinstance(s, ps.For):
            self.loop(s, env)
        elif isinstance(s, ps.Emit):
            if is_call:
                self.expr(top, env, s, role=f"emit:{s.slot or ''}")
            else:
                self.simple("emit", "emit", s, s.expr, env, emits=True, slot=s.slot)
        elif isinstance(s, ps.Give):
            out = s.label or (self.b.gives.name if self.b.gives else None)
            if is_call:
                self.expr(top, env, s, role=f"out:{out}")
            else:
                self.simple("give", "give", s, s.expr, env, gives=out, output=True)
            first = self.b.outputs[0].name if self.b.outputs else out
            mine = [k.name for k in self.b.keeps if (k.of or first) == out]
            if mine:                                    # what the program keeps of this output (THYM 7.5)
                self.nodes[-1].keeps = _once(self.nodes[-1].keeps + mine)
        elif isinstance(s, ps.Withhold):
            self.expr(s.call, env, s, role="withhold")
        elif isinstance(s, ps.Effect):
            if is_call:
                self.expr(top, env, s, role="effect")

    def loop(self, s: ps.For, env: _Env) -> None:
        """A `for each`: its body's statements once per member of a list written in the program, else once, each
        node marked `repeats` and taking what the collection and the `where` read (THYM 11.1). In `thym 1`, a loop
        that collects, a loop over a collection known only at run time whose body is more than one plain statement,
        and a loop nested in an unrolled one are one node each (`loop_node`)."""
        coll0 = ck.strip_paren(s.coll)
        written = isinstance(coll0, ps.ListLit) and s.where is None
        if self.c.module.version >= 1 and (s.collect is not None or env.member is not None
                                           or (not written and not _plain_body(s))):
            self.loop_node(s, env)
            return
        sub: dict[int, str] = {}
        names, lines = self.names(s.coll, env, sub, s)
        if s.where is not None:
            inner = env.child(loop=s, loop_names=None)
            more, more_lines = self.names(s.where, inner, sub, s)
            names += more
            lines |= more_lines
        coll = ck.strip_paren(s.coll)
        if self.c.module.version >= 1 and isinstance(coll, (ps.Call, ps.Marked)):
            self.loop_sub[id(s)] = sub
        if isinstance(coll, ps.ListLit) and s.where is None:
            for member in coll.items:
                self.stmts(s.body, env.child(loop=s, loop_names=None, member=member))
        else:
            self.stmts(s.body, env.child(loop=s, loop_names=(_once(names), lines), member=None))

    def loop_node(self, s: ps.For, env: _Env) -> None:
        """One node for a whole loop (`thym 1`, THYM 11.1): move `for`, named by the loop's own line, taking what its
        header and its body read from outside it (nested calls fold in: no temporaries), `calls` every move they call
        in written order, asking when any of them asks; `gives` the loop's name when it collects."""
        inner = list(ck.walk(s.body))
        inside = {s.var} | {st.name for st in inner if isinstance(st, ps.Let)} | {
            n for st in inner if isinstance(st, ps.For) for n in (st.var, st.collect) if n}
        sub: dict[int, str] = {}
        takes: list[str] = []
        lines: set[int] = {s.line, s.end}
        for st in [s] + inner:
            for part in ck.parts(st):
                n, ls = self.names(part, env, sub, st, fold=True)
                takes.extend(x for x in n if x not in inside)
                lines |= ls
        calls = [c for st in [s] + inner for part in ck.parts(st) for c in ck.eval_calls(part)]
        node = PlanNode(0, "for", "for", s, s.coll, 0, takes, folded=True)
        node.calls = _once([n for st in [s] + inner for n in ck.step_call_names(st)])
        node.asks = any(ck.call_asks(c) for c in calls) or any(ck.step_asks(st) for st in [s] + inner)
        node.own = True
        node.output_words = max((c.mod("to").arg.count for c in calls if isinstance(c, ps.Call) and c.mod("to")
                                 and isinstance(c.mod("to").arg, ps.Units) and c.mod("to").arg.unit == "words"),
                                default=0)
        node.gives = s.collect
        node.over = s.coll
        self.kept(node, calls)
        self.add(node, env, lines)
        node.repeats = True
        self.checkpoints.append(node.n)           # it may emit, assert and refuse: the output waits on it

    def fold(self, s: ps.Stmt, env: _Env) -> None:
        """A statement of a loop's body that nests a call inside another (or a call inside an `assert` or an `if`):
        one node, its nested calls folded in and evaluated with each member (THYM 11.1). Its move is the statement's
        outermost call (`mark` for a `marked` at the top; `assert`, `if`, `emit` when there is none), it asks when any
        of its calls asks, and it takes every name the statement and the loop's `where` read."""
        sub: dict[int, str] = {}
        takes: list[str] = []
        lines: set[int] = set()
        for part in ck.parts(s):
            n, ls = self.names(part, env, sub, s, fold=True)
            takes.extend(n)
            lines |= ls
        calls = [c for part in ck.parts(s) for c in ck.eval_calls(part)]
        top = ck.strip_paren(getattr(s, "expr", None))
        if isinstance(s, ps.Withhold):
            top = s.call
        if isinstance(s, (ps.Assert, ps.If)):
            kind = move = "assert" if isinstance(s, ps.Assert) else "if"
            expr: Any = s.cond
        elif isinstance(top, ps.Marked):
            kind, move, expr = "mark", "mark", top
        elif isinstance(top, ps.Call):
            kind, move, expr = "call", top.move, top
        else:
            kind, move, expr = "emit", "emit", s.expr
        node = PlanNode(0, kind, move, s, expr, 0, takes, folded=True)
        self.kept(node, calls)
        node.asks = any(ck.call_asks(c) for c in calls)
        node.own = True
        node.output_words = max((c.mod("to").arg.count for c in calls if isinstance(c, ps.Call) and c.mod("to")
                                 and isinstance(c.mod("to").arg, ps.Units) and c.mod("to").arg.unit == "words"),
                                default=0)
        if isinstance(s, ps.Let):
            node.gives = s.name
        elif isinstance(s, ps.Emit):
            node.emits, node.slot = True, s.slot
        self.add(node, env, lines)
        if isinstance(s, ps.If):
            self.stmts(s.then, env.child(branch="then", path=env.path + ((node.n, "then"),), cond=node.n))
            if s.else_ is not None:
                self.stmts(s.else_, env.child(branch="else", path=env.path + ((node.n, "else"),), cond=node.n))

    def run(self) -> list[PlanNode]:
        self.stmts(self.b.stmts, _Env({}, {}))
        anc: dict[int, set[int]] = {}
        for nd in self.nodes:
            a: set[int] = set()
            for d in nd.after:
                a |= {d} | anc[d]
            anc[nd.n] = a
            nd.after = [d for d in nd.after if not any(d in anc[e] for e in nd.after if e != d)]
        for nd in self.nodes:
            nd.name = self.node_name(nd)
            nd.summary = self.node_summary(nd)
        return self.nodes

    # -- words -------------------------------------------------------------

    def node_name(self, nd: PlanNode) -> str:
        if nd.kind == "for":
            text = ps.statement_name(nd.stmt, self.c.module.lines)
        elif nd.folded:
            text = _statement_text(nd.stmt)
        elif nd.kind in ("assert", "if"):
            text = f"{nd.kind} {ps.render_cond(nd.expr, nd.subst)}"
        elif nd.kind == "mark":
            inner = ck.strip_paren(nd.expr.inner)
            text = f"mark {nd.subst.get(id(inner)) or nd.subst.get(id(nd.expr.inner)) or ps.render(inner)} as " \
                   f"{nd.expr.word}"
        elif nd.kind in ("emit", "give"):
            text = ps.render(nd.expr, nd.subst)
        else:
            text = ps.render(nd.expr, nd.subst)
        if nd.folded:
            pass
        elif nd.emits:
            text = f"emit {nd.slot + ': ' if nd.slot else ''}{text}"
        elif nd.kind == "give":
            text = f"give {text}"
        if nd.loop is not None:
            if nd.member is not None:
                text += f", for {nd.loop.var} = {ps.render(nd.member)}"
            elif id(nd.loop) in self.loop_sub:
                lp, sub = nd.loop, self.loop_sub[id(nd.loop)]
                text += f", for each {lp.var} in {ps.render(lp.coll, sub)}" + (
                    f" where {ps.render_cond(lp.where, sub)}" if lp.where is not None else "")
            else:
                text += ", " + ps.statement_name(nd.loop, self.c.module.lines)
        return text

    def node_summary(self, nd: PlanNode) -> str:
        """A node's summary: its line's comment, else its name (THYM.md 10)."""
        return nd.stmt.comment or nd.name


def _plain_body(s: ps.For) -> bool:
    """Whether a loop's body is one plain statement, which `thym 1` plans exactly as `thym 0` does (THYM 11.1)."""
    return len(s.body) == 1 and isinstance(s.body[0], (ps.Let, ps.Assert, ps.Emit, ps.Withhold, ps.Effect))


def _members(over: Any, rows: dict, counts: dict) -> int | None:
    """How many members a loop node's collection has at most, when the plan knows it (THYM 11.1): a written list's;
    a folder input's files (its row's `files`); for a filter of an input, the input's (counted before the `where`).
    `counts` may give a volume's or fabula's count of items; `plan` gives none (see the module's docstring)."""
    e = ck.strip_paren(over)
    if isinstance(e, ps.ListLit):
        return len(e.items)
    if isinstance(e, ps.Filter):
        e = ck.strip_paren(e.target)
    if isinstance(e, ps.Name) and e.kind == "binding" and e.name in rows:
        b = e.binding
        if getattr(b, "kind", None) != "takes":
            return None
        row = rows[e.name]
        if row.get("type") == "folder" and isinstance(row.get("files"), int):
            return row["files"]
        return counts.get(e.name)
    return None


def _nests(s: ps.Stmt) -> bool:
    """Whether a statement holds a call nested inside another, or a call inside an `assert` or an `if` condition: in
    a loop's body such a statement is folded into one node (THYM 11.1). A statement of one call, or none, is not."""
    if isinstance(s, (ps.For, ps.Give)):
        return False
    calls = [c for part in ck.parts(s) for c in ck.eval_calls(part)]
    if isinstance(s, (ps.Assert, ps.If)):
        return bool(calls)
    own = ck.own_call(s)
    return any(c is not own for c in calls)


def _statement_text(s: ps.Stmt) -> str:
    """A folded statement as a node names it: the statement in canonical spacing, nested calls as written (a
    temporary never stands in for one), so that the runtime reads it whole."""
    if isinstance(s, ps.Assert):
        return f"assert {ps.render_cond(s.cond)}"
    if isinstance(s, ps.If):
        return f"if {ps.render_cond(s.cond)}"
    if isinstance(s, ps.Withhold):
        return ps.render(s.call)
    text = ps.render(ck.strip_paren(s.expr))
    if isinstance(s, ps.Emit):
        return f"emit {s.slot + ': ' if s.slot else ''}{text}"
    return text


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def build(checked: ck.Checked, *, program: str | None = None) -> list[PlanNode] | Refusal:
    """The plan's nodes for a checked module's program (the first, unless one is named), with their tree."""
    progs = checked.programs()
    block = next((b for b in progs if b.name == program), None) if program else (progs[0] if progs else None)
    if block is None:
        what = f"no program named {program}" if program else "no program block"
        return Refusal("plan", "no-program", f"there is nothing to plan: the file has {what}", None,
                       checked.module.path)
    return _Planner(checked, block).run()


def _folder_row(i: dict) -> dict:
    """A folder input's plan row (THYM 20.3): `{name, type: folder, path, sha256: <tree digest>, files, bytes}`,
    the digest and the counts read from the folder when the caller did not give them."""
    row = {"name": str(i.get("name")), "type": "folder", "path": posix_path(i.get("path")),
           "sha256": str(i.get("sha256") or "")}
    files, size = i.get("files"), i.get("bytes")
    if not row["sha256"] or not isinstance(files, int) or not isinstance(size, int):
        try:
            f = fd.read(Path(str(i.get("path") or "")), path=row["path"])
        except fd.FolderError:
            f = None
        if f is not None:
            row["sha256"] = row["sha256"] or f.tree
            files = files if isinstance(files, int) else f.files
            size = size if isinstance(size, int) else f.bytes
    row["files"] = files if isinstance(files, int) else 0
    row["bytes"] = size if isinstance(size, int) else 0
    return row


def _here(inp: dict, root: Path | None) -> Path:
    """Where an input's path points: as given, or under `root` when it is relative and a root was given."""
    p = Path(str(inp.get("path") or ""))
    return p if p.is_absolute() or root is None else Path(root) / p


def _size(inp: dict, root: Path | None = None) -> int:
    if isinstance(inp.get("size"), int):
        return inp["size"]
    if inp.get("type") == "folder":                # what a prompt could hold of it: its text files
        try:
            f = fd.read(_here(inp, root))
            return sum(e.size for e in f.texts())
        except fd.FolderError:
            return 0
    try:
        p = _here(inp, root)
        if p.is_file():
            return p.stat().st_size
        if p.is_dir():
            return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    except OSError:
        pass
    return 0


def run_id(program_sha: str, inputs: list[dict], now: _dt.datetime | None = None) -> str:
    """`<YYYY-MM-DD-HHMM>-<first four hex of sha256(program sha256 + every input's sha256)>`, local time."""
    now = now or _dt.datetime.now()
    joined = program_sha + "".join(str(i.get("sha256") or "") for i in inputs)
    return f"{now:%Y-%m-%d-%H%M}-{hashlib.sha256(joined.encode('utf-8')).hexdigest()[:4]}"


def _count(n: int) -> str:
    return _NUMBERS[n] if 0 <= n < len(_NUMBERS) else str(n)


def root_summary(nodes: int, asks: int) -> str:
    """A plan's root summary: its nodes and the ones that ask, in number words to twenty ("Seven nodes, three of
    which ask the model."; "Seven nodes, none of which asks the model.")."""
    head = f"{en.cap(_count(nodes))} node{'' if nodes == 1 else 's'}"
    if asks == 0:
        return f"{head}, none of which asks the model."
    if asks == 1:
        return f"{head}, one of which asks the model."
    return f"{head}, {_count(asks)} of which ask the model."


def _sites(stmts: list[ps.Stmt], seen: frozenset[int] = frozenset(), deep: bool = True) -> tuple[int, bool]:
    """The asking call sites of some statements, through the user moves they call: `(how many, whether the count is
    open)`. A site inside a `for each` of a written list counts once per member; any other loop, and a move that
    calls itself, opens the count. Not `deep`: the statements' own expressions only, not their branches or bodies."""
    n, open_ = 0, False
    for st in stmts:
        for c in [c for part in ck.parts(st) for c in ck.eval_calls(part)]:
            t = getattr(c, "target", None)
            if isinstance(t, ck.UserMove):
                if not t.asks:
                    continue
                if id(t) in seen or t.depth is not None:
                    open_ = True
                    continue
                k, o = _sites(t.block.stmts, seen | {id(t)})
                n, open_ = n + k, open_ or o
            elif ck.call_asks(c):
                n += 1
        if not deep:
            continue
        if isinstance(st, ps.If):
            k1, o1 = _sites(st.then, seen)
            k2, o2 = _sites(st.else_ or [], seen)
            n, open_ = n + max(k1, k2), open_ or o1 or o2
        elif isinstance(st, ps.For):
            k, o = _sites(st.body, seen)
            coll = ck.strip_paren(st.coll)
            if k and isinstance(coll, ps.ListLit):
                k *= len(coll.items)
            elif k:
                o = True
            n, open_ = n + k, open_ or o
    return n, open_


def calls_estimate(nodes: list[PlanNode], rows: dict, counts: dict) -> dict:
    """`{calls, at_most, calls_open}` for a plan's nodes (THYM 23.2)."""
    calls = at_most = 0
    opened: list[str] = []
    for nd in nodes:
        if not nd.asks:
            continue
        if nd.kind == "for":                       # a loop node: its body's sites, once per member
            k, o = _sites(nd.stmt.body, frozenset())
            head = [c for part in ck.parts(nd.stmt) for c in ck.eval_calls(part) if ck.call_asks(c)]
            m = _members(nd.over, rows, counts)
            if m is None:
                o = o or k > 0
                m = 1
            k = k * m + len(head)
        elif nd.folded:
            k, o = _sites([nd.stmt], frozenset(), deep=False)
            k = max(k, 1)
        else:
            t = getattr(nd.expr, "target", None)
            k, o = (_sites(t.block.stmts, frozenset({id(t)})) if isinstance(t, ck.UserMove) else (1, False))
            if isinstance(t, ck.UserMove) and t.depth is not None:
                o = True
        if nd.repeats and nd.kind != "for":        # a thym 0 repeating node: once per member
            m = _members(nd.loop.coll, rows, counts) if nd.loop is not None else None
            if m is None:
                o = True
            else:
                k *= m
        calls += k
        at_most += k * 3
        if o:
            opened.append(f"R:node/{nd.n}")
    return {"calls": calls, "at_most": at_most, "calls_open": opened}


def plan(checked: ck.Checked, inputs: list[dict], *, program: str | None = None,
         now: _dt.datetime | None = None, inputs_root: Path | str | None = None,
         models: dict | None = None) -> dict | Refusal:
    """The plan volume of a checked program over its inputs, `[{name, type, path, sha256}]` in the order the
    program takes them (a `size` in bytes may come with each, else the file is measured if it is there).
    `inputs_root` is the folder a relative input path is read under when it is measured or counted (else the
    working folder). `models` (`{route, provider, model, window}`, the host's choice of route) adds the catalog key
    `models` with the count of model calls, when a node asks (THYM 23.2)."""
    root = Path(inputs_root) if inputs_root is not None else None
    if isinstance(checked, Refusal):
        return checked
    nodes = build(checked, program=program)
    if isinstance(nodes, Refusal):
        return nodes
    progs = checked.programs()
    block = next(b for b in progs if b.name == program) if program else progs[0]
    m = checked.module
    fname = m.file_name
    given = {str(i.get("name")): i for i in inputs if isinstance(i, dict)}
    for p in block.takes:
        if p.name not in given:
            return Refusal("plan", "input", f"program {block.name} takes {p.name}: {p.type}, and no input was given "
                           "for it", p.line, m.path)
        if str(given[p.name].get("type") or p.type) != p.type:
            return Refusal("plan", "input", f"{p.name} is a {p.type}; the input given for it is a "
                           f"{given[p.name].get('type')}", p.line, m.path)
    unknown = [n for n in given if n not in {p.name for p in block.takes}]
    if unknown:
        return Refusal("plan", "input", f"program {block.name} takes no {unknown[0]}", None, m.path)
    ins = [_folder_row(i) if i.get("type") == "folder" else
           {"name": str(i.get("name")), "type": str(i.get("type")), "path": posix_path(i.get("path")),
            "sha256": str(i.get("sha256"))} for i in inputs]
    program_sha = en.sha256(m.text.encode("utf-8"))
    rid = run_id(program_sha, ins, now)
    sizes = {str(i.get("name")): _size(i, root) for i in inputs}
    rows = {str(i.get("name")): r for i, r in zip(inputs, ins)}
    counts: dict[str, int | None] = {}
    largest = max((sum(sizes.get(n, 0) for n in nd.inputs) // 4 for nd in nodes if nd.asks), default=0)
    asks = sum(1 for nd in nodes if nd.asks)
    words = max((nd.output_words for nd in nodes), default=0)
    title = f"{block.name} on {Path(ins[0]['path']).name}" if ins else block.name
    summary = root_summary(len(nodes), asks)
    items: list[dict] = [{
        "id": f"R:plan/{rid}", "type": "plan", "name": title, "summary": summary,
        "nodes": [f"R:node/{nd.n}" for nd in nodes], "asks": asks, "largest_prompt": largest,
        "provenance": en.provenance(fname),
    }]
    for nd in nodes:
        it: dict[str, Any] = {"id": f"R:node/{nd.n}", "type": "node", "name": nd.name, "summary": nd.summary}
        if nd.slot:
            it["slot"] = nd.slot
        it["step"] = {"program": block.name, "n": nd.step}
        if nd.branch:
            it["branch"] = nd.branch
        it.update({"move": nd.move, "asks": nd.asks, "takes": list(nd.takes)})
        if nd.repeats:
            it["repeats"] = True
        if nd.gives:
            it["gives"] = nd.gives
        if nd.calls is not None:
            it["calls"] = list(nd.calls)
        if nd.over is not None:
            at_most = _members(nd.over, rows, counts)
            if at_most is not None:
                it["members"] = {"at_most": at_most}
        if nd.keeps:
            it["keeps"] = list(nd.keeps)
        it["after"] = [f"R:node/{k}" for k in nd.after]
        it["budget"] = {"attempts": 3 if nd.asks else 1, "output_words": nd.output_words}
        if nd.depth is not None:
            it["budget"]["depth"] = nd.depth
        it["line"] = nd.stmt.line
        it["provenance"] = en.provenance(fname, nd.lines[0], nd.lines[1])
        items.append(it)
    out = {
        "oes": MINICOSM, "kind": "plan", "id": f"thym/{rid}", "name": title,
        "program": {"name": block.name, "sha256": program_sha},
        "inputs": ins,
        "estimate": {"steps": len(nodes), "asks": asks, "largest_prompt": largest, "output_words": words},
    }
    if models is not None and asks:
        est = calls_estimate(nodes, rows, counts)
        out["models"] = {**{k: models[k] for k in ("route", "provider", "model") if k in models}, **est,
                         **({"window": models["window"]} if "window" in models else {})}
    out["nodes"] = items
    return out


def normalise(mapping: dict) -> dict:
    """What conformance compares of a plan: run ids as `fixture`, the catalog id `thym/plan.<program>`,
    `largest_prompt` 0 and no timestamps."""
    out = copy.deepcopy(mapping)
    root = next((it for it in out.get("nodes") or [] if isinstance(it, dict) and it.get("type") == "plan"), None)
    rid = str(root["id"]).split("/", 1)[1] if root and "/" in str(root.get("id")) else None

    def swap(v: Any) -> Any:
        if isinstance(v, str) and rid and rid != "fixture" and rid in v:
            return v.replace(rid, "fixture")
        if isinstance(v, list):
            return [swap(x) for x in v]
        if isinstance(v, dict):
            return {k: swap(x) for k, x in v.items()}
        return v

    out = swap(out)
    prog = (out.get("program") or {}).get("name")
    if prog:
        out["id"] = f"thym/plan.{prog}"
    for key in ("built", "started", "ended", "at", "models"):
        out.pop(key, None)
    if isinstance(out.get("estimate"), dict):
        out["estimate"]["largest_prompt"] = 0
    for it in out.get("nodes") or []:
        if isinstance(it, dict) and it.get("type") == "plan":
            it["largest_prompt"] = 0
    return out
