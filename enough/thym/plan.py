"""A checked program planned into a `thym/1` plan volume: what it will do, before it does it (THYM.md 11.1, 12.5,
17.1, 17.3; stages 5 and 7 of section 11.1).

The nodes come in evaluation order, a nested call before the call that takes its value:

- one node per move call, a `marked` modifier included (a `mark` node of its own), and one per `assert`; a call of
  a user move is one node;
- one node per `if`, for its condition; each node of a branch says which branch it is in and waits on the condition;
- for a `for each` over a list written in the program, a node per member for each call in its body; over anything
  else (known only at run time), one node per call, marked `repeats`, that takes the collection;
- no node for a `let` whose value is not a call: a filter, a name or a field folds into the node that takes it, which
  then takes what the filter reads and spans its line. A call-less `emit` or `give` is a node of its own (`emit`,
  `give`), so that the plan says everything the run does.

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

    # -- names -------------------------------------------------------------

    def names(self, x: Any, env: _Env, sub: dict[int, str], stmt: ps.Stmt) -> tuple[list[str], set[int]]:
        """The names a part of a statement takes, making a node (a temporary) for every call inside it first."""
        if isinstance(x, (ps.Call, ps.Marked)):
            temp = self.expr(x, env, stmt, role="temp")
            sub[id(x)] = temp
            return [temp], set()
        if isinstance(x, ps.Paren):
            names, lines = self.names(x.inner, env, sub, stmt)
            if id(x.inner) in sub:
                sub[id(x)] = sub[id(x.inner)]
            return names, lines
        if isinstance(x, ps.Name):
            if x.kind != "binding":
                return [], set()
            if env.loop is not None and x.name == env.loop.var:
                if env.loop_names is not None:
                    return list(env.loop_names[0]), set(env.loop_names[1])
                return [], set()
            if x.name in env.aliases:
                names, lines = env.aliases[x.name]
                return list(names), set(lines)
            return [x.name], set()
        out: list[str] = []
        lines: set[int] = set()
        for ch in ck.children(x):
            n, ls = self.names(ch, env, sub, stmt)
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
            sub = {}
            names, lines = self.names(s.coll, env, sub, s)
            if s.where is not None:
                inner = env.child(loop=s, loop_names=None)
                more, more_lines = self.names(s.where, inner, sub, s)
                names += more
                lines |= more_lines
            coll = ck.strip_paren(s.coll)
            if isinstance(coll, ps.ListLit) and s.where is None:
                for member in coll.items:
                    self.stmts(s.body, env.child(loop=s, loop_names=None, member=member))
            else:
                self.stmts(s.body, env.child(loop=s, loop_names=(_once(names), lines), member=None))
        elif isinstance(s, ps.Emit):
            if is_call:
                self.expr(top, env, s, role=f"emit:{s.slot or ''}")
            else:
                self.simple("emit", "emit", s, s.expr, env, emits=True, slot=s.slot)
        elif isinstance(s, ps.Give):
            out = self.b.gives.name if self.b.gives else None
            if is_call:
                self.expr(top, env, s, role=f"out:{out}")
            else:
                self.simple("give", "give", s, s.expr, env, gives=out, output=True)
        elif isinstance(s, ps.Withhold):
            self.expr(s.call, env, s, role="withhold")
        elif isinstance(s, ps.Effect):
            if is_call:
                self.expr(top, env, s, role="effect")

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
        if nd.kind in ("assert", "if"):
            text = f"{nd.kind} {ps.render_cond(nd.expr, nd.subst)}"
        elif nd.kind == "mark":
            inner = ck.strip_paren(nd.expr.inner)
            text = f"mark {nd.subst.get(id(inner)) or nd.subst.get(id(nd.expr.inner)) or ps.render(inner)} as " \
                   f"{nd.expr.word}"
        elif nd.kind in ("emit", "give"):
            text = ps.render(nd.expr, nd.subst)
        else:
            text = ps.render(nd.expr, nd.subst)
        if nd.emits:
            text = f"emit {nd.slot + ': ' if nd.slot else ''}{text}"
        elif nd.kind == "give":
            text = f"give {text}"
        if nd.loop is not None:
            if nd.member is not None:
                text += f", for {nd.loop.var} = {ps.render(nd.member)}"
            else:
                text += ", " + ps.statement_name(nd.loop, self.c.module.lines)
        return text

    def node_summary(self, nd: PlanNode) -> str:
        """A node's summary: its line's comment, else its name (THYM.md 10)."""
        return nd.stmt.comment or nd.name


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


def _size(inp: dict) -> int:
    if isinstance(inp.get("size"), int):
        return inp["size"]
    try:
        p = Path(str(inp.get("path") or ""))
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


def plan(checked: ck.Checked, inputs: list[dict], *, program: str | None = None,
         now: _dt.datetime | None = None) -> dict | Refusal:
    """The plan volume of a checked program over its inputs, `[{name, type, path, sha256}]` in the order the
    program takes them (a `size` in bytes may come with each, else the file is measured if it is there)."""
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
    ins = [{"name": str(i.get("name")), "type": str(i.get("type")), "path": posix_path(i.get("path")),
            "sha256": str(i.get("sha256"))} for i in inputs]
    program_sha = en.sha256(m.text.encode("utf-8"))
    rid = run_id(program_sha, ins, now)
    sizes = {str(i.get("name")): _size(i) for i in inputs}
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
        it["after"] = [f"R:node/{k}" for k in nd.after]
        it["budget"] = {"attempts": 3 if nd.asks else 1, "output_words": nd.output_words}
        it["line"] = nd.stmt.line
        it["provenance"] = en.provenance(fname, nd.lines[0], nd.lines[1])
        items.append(it)
    return {
        "oes": MINICOSM, "kind": "plan", "id": f"thym/{rid}", "name": title,
        "program": {"name": block.name, "sha256": program_sha},
        "inputs": ins,
        "estimate": {"steps": len(nodes), "asks": asks, "largest_prompt": largest, "output_words": words},
        "nodes": items,
    }


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
    for key in ("built", "started", "ended", "at"):
        out.pop(key, None)
    if isinstance(out.get("estimate"), dict):
        out["estimate"]["largest_prompt"] = 0
    for it in out.get("nodes") or []:
        if isinstance(it, dict) and it.get("type") == "plan":
            it["largest_prompt"] = 0
    return out
