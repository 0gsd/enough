"""Thym's checker: resolve, type-check and contract-check a parsed program (THYM.md 5, 6, 7.1, 8, 9; stages 2 to 4
of section 11.1).

It resolves every name a file uses: a program's `takes`, `let` bindings, loop variables, a move's parameters, the
file's `morph` and `context` blocks, the moves every manifest declares (`declarations.load`), the file's own `move`
blocks, and what its `use` lines bring in (the blocks of a `.thym` file beside it, or the `M:morph` and `C:context`
items of a `thym/1` volume). Scopes are section 5.4's: a name is bound once; an inner block sees what was bound
before it and may not rebind it; a move sees its parameters and the file's blocks, never its caller's bindings.

It types every expression by section 5, matches every call to its declaration (operand count and types, modifier
words, their order and types; `marked` is `mark … as …`; the accessors take their argument through `of`), and
refuses the static failures of section 9 with their check names: `unknown-move` (with the nearest name),
`unknown-uri`, `use-clash`, `unbound`, `rebound`, `type`, `recursion`, `no-give`, `emit-without-project`, and the
static contract `no-counts`. A refusal is a value with the line; nothing here raises for a bad program.

`check` gives a `Checked`: the module with every expression typed and every call bound to its target, the file's
symbols, and the user moves with the contracts, calls and asks they inherit. `own_call`, `step_calls`, `eval_calls`,
`names_used` and `walk` are the views of a statement that enumeration and planning share.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Callable, Iterator, Mapping

from enough import macrocosm as mc

from . import Refusal
from . import contracts as ct
from . import declarations as dc
from . import parse as ps
from . import types as ty

ENVELOPE_KEYS = frozenset(("id", "type", "name", "summary", "status", "visibility", "provenance", "pending", "links",
                           "made", "why", "must", "decided", "lines", "order", "body"))
_OES_THYM = re.compile(r"^oes:thym/([A-Za-z0-9](?:[A-Za-z0-9._@-]*[A-Za-z0-9_@-])?)$")

Volumes = Mapping[str, Any] | Callable[[str], Any] | None


def _escapes(uri: str) -> str | None:
    """Why a `use`d path reaches outside the program's folder (THYM.md 8.4: a file beside this one; the grammar's URI
    is a relative path), or None when it stays inside: an absolute path, a drive, or a `..` step, on either system's
    reading of the text. A link that leads out is caught after it is followed (`_inside`)."""
    if PurePosixPath(uri).is_absolute() or PureWindowsPath(uri).anchor:
        return "is an absolute path"
    if ".." in PurePosixPath(uri).parts or ".." in PureWindowsPath(uri).parts:
        return "steps out with .."
    return None


def _inside(base: Path, p: Path) -> bool:
    """Whether `p`, every link followed, lies inside the folder `base` (itself followed)."""
    try:
        return p.resolve().is_relative_to(base.resolve())
    except (OSError, RuntimeError):
        return False


def _yaml_problem(e: Exception) -> str:
    """What is wrong with a used file's YAML, with its place and never its text: PyYAML's message quotes the line it
    stopped on, and a refusal must not carry a file's content."""
    problem = getattr(e, "problem", None)
    mark = getattr(e, "problem_mark", None)
    if problem and mark is not None:
        return f"{problem} at line {mark.line + 1}, column {mark.column + 1}"
    return problem or type(e).__name__


@dataclass(eq=False)
class Binding:
    """A bound name: its type, what bound it (`takes`, `let`, `loop`, `param`, `morph`, `context`), its line and
    file. A context block's `fields` map each field to its type."""
    name: str
    type: str
    kind: str
    line: int | None
    file: str | None = None
    fields: dict[str, str] | None = None
    source: Any = None


@dataclass(eq=False)
class UserMove:
    """A `move` block as a callable move. `program` names the program it is local to. `calls`, `checks` and
    `asks` are inherited from every move its body uses (THYM.md 8.3), and filled in once recursion is ruled out."""
    name: str
    params: list[tuple[str, str]]
    gives: str
    line: int
    block: ps.Block
    module: ps.Module
    program: str | None = None
    file: str | None = None
    calls: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)
    asks: bool = False
    inherited: bool = False

    @property
    def id(self) -> str:
        return f"P:move/{self.block.qualified}"


@dataclass(eq=False)
class Checked:
    """A program that compiled: the module (every expression typed, every call bound to its `target`), the
    declarations it was checked against, the file-scope names, the user moves, and each block's bindings."""
    module: ps.Module
    decls: dict
    names: dict[str, Binding]
    moves: dict[str, UserMove]
    local: dict[str, dict[str, UserMove]]
    user_moves: list[UserMove]
    symbols: dict[str, dict[str, Binding]]
    used: list[dict]
    warnings: list

    def programs(self) -> list[ps.Block]:
        return self.module.programs()

    def move_of(self, block: ps.Block) -> UserMove | None:
        return next((m for m in self.user_moves if m.block is block), None)


class _Fail(Exception):
    def __init__(self, refusal: Refusal):
        super().__init__(refusal.message)
        self.refusal = refusal


class _Scope:
    def __init__(self, parent: "_Scope | None" = None, sink: dict | None = None):
        self.parent, self.names, self.sink = parent, {}, sink

    def lookup(self, name: str) -> Binding | None:
        s: _Scope | None = self
        while s is not None:
            if name in s.names:
                return s.names[name]
            s = s.parent
        return None

    def add(self, b: Binding) -> None:
        self.names[b.name] = b
        if self.sink is not None:
            self.sink.setdefault(b.name, b)

    def child(self) -> "_Scope":
        return _Scope(self, self.sink)


@dataclass
class _Ctx:
    block: ps.Block
    program: str | None
    in_loop: bool = False


# ---------------------------------------------------------------------------
# Views of a statement, shared with enumeration and planning
# ---------------------------------------------------------------------------

def walk(stmts: list[ps.Stmt]) -> Iterator[ps.Stmt]:
    """Every statement in the order written: an `if` before its branches, a `for each` before its body."""
    for s in stmts:
        yield s
        if isinstance(s, ps.If):
            yield from walk(s.then)
            yield from walk(s.else_ or [])
        elif isinstance(s, ps.For):
            yield from walk(s.body)


def parts(st: ps.Stmt) -> list[Any]:
    """A statement's own expressions and conditions, in source order (not its body's)."""
    if isinstance(st, (ps.Let, ps.Emit, ps.Give, ps.Effect)):
        return [st.expr]
    if isinstance(st, ps.Assert):
        return [st.cond]
    if isinstance(st, ps.If):
        return [st.cond]
    if isinstance(st, ps.For):
        return [st.coll] + ([st.where] if st.where is not None else [])
    if isinstance(st, ps.Withhold):
        return [st.call]
    return []


def strip_paren(e: Any) -> Any:
    while isinstance(e, ps.Paren):
        e = e.inner
    return e


def own_call(st: ps.Stmt) -> Any:
    """The call a statement is about: the call its expression is (inside `marked`, the marked call), or the
    `marked` itself when it marks a plain value; None for `assert`, `if`, `for each` and a call-less expression."""
    if isinstance(st, ps.Withhold):
        return st.call
    if isinstance(st, (ps.Let, ps.Emit, ps.Give, ps.Effect)):
        e = strip_paren(st.expr)
        if isinstance(e, ps.Marked):
            inner = strip_paren(e.inner)
            return inner if isinstance(inner, ps.Call) else e
        if isinstance(e, ps.Call):
            return e
    return None


def children(x: Any) -> list[Any]:
    if isinstance(x, ps.Call):
        return list(x.operands) + [m.arg for m in x.mods]
    if isinstance(x, ps.Marked):
        return [x.inner]
    if isinstance(x, ps.Paren):
        return [x.inner]
    if isinstance(x, ps.Filter):
        return [x.target, x.cond]
    if isinstance(x, ps.FieldRead):
        return [x.target]
    if isinstance(x, ps.ListLit):
        return list(x.items)
    if isinstance(x, ps.Logic):
        return [x.left, x.right]
    if isinstance(x, ps.Not):
        return [x.inner]
    if isinstance(x, (ps.Compare, ps.Covers)):
        return [x.left, x.right]
    if isinstance(x, ps.Has):
        return [x.target]
    if isinstance(x, ps.Truth):
        return [x.expr]
    return []


def eval_calls(x: Any) -> list[Any]:
    """Every call in an expression or condition in evaluation order: what a call takes before the call, the marked
    value before its `marked`."""
    out: list[Any] = []
    for c in children(x):
        out.extend(eval_calls(c))
    if isinstance(x, (ps.Call, ps.Marked)):
        out.append(x)
    return out


def step_calls(st: ps.Stmt) -> list[Any]:
    """A statement's calls in step order: its own call first, then every other in evaluation order (THYM.md 10)."""
    own = own_call(st)
    rest = [c for p in parts(st) for c in eval_calls(p) if c is not own]
    return ([own] if own is not None else []) + rest


def move_name(c: Any) -> str:
    return "mark" if isinstance(c, ps.Marked) else c.move


def call_checks(c: Any) -> list[str]:
    return ct.checks_of(getattr(c, "target", None))


def call_asks(c: Any) -> bool:
    t = getattr(c, "target", None)
    return bool(getattr(t, "asks", False))


def step_call_names(st: ps.Stmt) -> list[str]:
    """Every move a statement's line calls: its own first, then nested calls, each user move followed by the moves
    it calls."""
    out: list[str] = []
    for c in step_calls(st):
        out.append(move_name(c))
        t = getattr(c, "target", None)
        if isinstance(t, UserMove):
            out.extend(t.calls)
    seen: list[str] = []
    for n in out:
        if n not in seen:
            seen.append(n)
    return seen


def step_asks(st: ps.Stmt) -> bool:
    return any(call_asks(c) for c in step_calls(st))


def names_used(st: ps.Stmt) -> list[str]:
    """The bound names a statement's own expressions use, in order of appearance, once each (never the name the
    statement binds, a word, or an item's field)."""
    out: list[str] = []
    own = st.name if isinstance(st, ps.Let) else (st.var if isinstance(st, ps.For) else None)

    def visit(x: Any) -> None:
        if isinstance(x, ps.Name):
            if x.kind == "binding" and x.name != own and x.name not in out:
                out.append(x.name)
            return
        for c in children(x):
            visit(c)

    for p in parts(st):
        visit(p)
    return out


def reaches_give(stmts: list[ps.Stmt]) -> bool:
    """True when every path through these statements reaches a `give` (THYM.md 8.2)."""
    for s in stmts:
        if isinstance(s, ps.Give):
            return True
        if isinstance(s, ps.If) and s.else_ is not None and reaches_give(s.then) and reaches_give(s.else_):
            return True
    return False



# ---------------------------------------------------------------------------
# The checker
# ---------------------------------------------------------------------------

class _Checker:
    def __init__(self, module: ps.Module, decls: dict, volumes: Volumes, seen: frozenset[str]):
        self.m, self.decls, self.volumes, self.seen = module, decls, volumes, seen
        self.file = module.path
        self.reserved = set(ps.KEYWORDS) | set(decls) | set(ty.LITERAL_WORDS)
        self.names: dict[str, Binding] = {}
        self.moves: dict[str, UserMove] = {}
        self.local: dict[str, dict[str, UserMove]] = {}
        self.user_moves: list[UserMove] = []
        self.symbols: dict[str, dict[str, Binding]] = {}
        self.used: list[dict] = []
        self.origin: dict[str, str] = {}          # a file-scope name → the file that declares it
        self.file_scope = _Scope()

    # -- refusals ----------------------------------------------------------

    def fail(self, check: str, message: str, line: int | None, file: str | None = None) -> None:
        raise _Fail(Refusal("compile", check, message, line, file or self.file))

    def what_is(self, name: str) -> str | None:
        if name in ps.KEYWORDS:
            return "keyword"
        if name in self.decls:
            return "standard move"
        if name in ty.DENSITIES:
            return "density"
        if name in ty.ORDERS:
            return "order"
        if name in ty.MARKINGS:
            return "marking"
        if name in ty.STANCES:
            return "stance"
        return None

    def name_ok(self, name: str, line: int, what: str) -> None:
        reason = self.what_is(name)
        if reason:
            a = "an" if reason[0] in "aeiou" else "a"
            self.fail("type", f"`{name}` is {a} {reason} and cannot name {what}; choose another name", line)

    # -- the whole file ----------------------------------------------------

    def run(self) -> Checked:
        m = self.m
        blocks_by_name: dict[str, ps.Block] = {}
        for b in m.blocks:
            self.name_ok(b.name, b.line, f"a {b.kind}")
            if b.name in blocks_by_name:
                first = blocks_by_name[b.name]
                self.fail("rebound", f"`{b.name}` already names the {first.kind} at line {first.line}; a name is "
                          "unique among the blocks of its file", b.line)
            blocks_by_name[b.name] = b
        for b in m.blocks:
            for lm in b.moves:
                self.name_ok(lm.name, lm.line, "a move")
                if lm.name in blocks_by_name or any(o is not lm and o.name == lm.name for o in b.moves):
                    self.fail("rebound", f"`{lm.name}` already names a block of this file", lm.line)
        for u in m.uses:
            self.use(u, blocks_by_name)
        for b in m.blocks:
            self.origin.setdefault(b.name, Path(self.file).name if self.file else "this file")
            if b.kind == "morph":
                self.add_name(Binding(b.name, "morph", "morph", b.line, self.file, source=b))
            elif b.kind == "context":
                fields = {f.field: self.value_type(f.value) for f in b.fields}
                self.add_name(Binding(b.name, "context", "context", b.line, self.file, fields=fields, source=b))
            elif b.kind == "move":
                mv = self.user_move(b, None)
                self.moves[b.name] = mv
        for b in m.blocks:
            if b.kind == "program":
                self.local[b.name] = {lm.name: self.user_move(lm, b.name) for lm in b.moves}
        for b in m.blocks:
            self.check_block(b)
        self.no_recursion()
        for mv in self.user_moves:
            self.inherit(mv, set())
        return Checked(m, self.decls, self.names, self.moves, self.local, self.user_moves, self.symbols, self.used,
                       list(m.warnings))

    def add_name(self, b: Binding) -> None:
        self.names[b.name] = b
        self.file_scope.add(b)

    def user_move(self, b: ps.Block, program: str | None) -> UserMove:
        for p in b.params:
            self.name_ok(p.name, p.line, "a parameter")
        mv = UserMove(b.name, [(p.name, p.type) for p in b.params], b.gives.type if b.gives else ty.NOTHING,
                      b.line, b, self.m, program, self.file)
        self.user_moves.append(mv)
        return mv

    # -- use ---------------------------------------------------------------

    def use(self, u: ps.Use, blocks: dict[str, ps.Block]) -> None:
        brought = self.resolve_use(u)
        names: list[str] = []
        here = Path(self.file).name if self.file else "this file"
        for name, (kind, value, source_file) in brought.items():
            source_file = Path(source_file).name if source_file else u.uri
            if name in blocks:
                self.fail("use-clash", f"`{name}` comes from {source_file} and is also a {blocks[name].kind} of "
                          f"{here} (line {blocks[name].line}); rename one", u.line)
            if name in self.origin:
                self.fail("use-clash", f"`{name}` comes from both {self.origin[name]} and {source_file}; "
                          "rename one, or use only one of them", u.line)
            self.origin[name] = source_file
            names.append(name)
            if kind == "move":
                self.moves[name] = value
            else:
                self.add_name(value)
        self.used.append({"uri": u.uri, "line": u.line, "names": names})

    def lookup_volume(self, uri: str) -> Any:
        v = self.volumes
        if v is None:
            return None
        if callable(v) and not isinstance(v, Mapping):
            return v(uri)
        return v.get(uri)

    def resolve_use(self, u: ps.Use) -> dict[str, tuple[str, Any, str]]:
        uri = u.uri
        base = Path(self.file).parent if self.file else Path.cwd()
        found = self.lookup_volume(uri)
        outside = (f"use names a .thym file or a thym/1 volume inside this program's folder; {uri} "
                   "{why}, and was not read")
        if found is None:
            if uri.startswith("oes:"):
                mt = _OES_THYM.match(uri)
                if not mt:
                    self.fail("unknown-uri", f"use names a whole thym/1 volume (oes:thym/<name>) or a .thym file "
                              f"beside this one; {uri} is neither", u.line)
                slug = mt.group(1)
                for name in (f"{slug}.morph.cosm", f"{slug}.context.cosm", f"{slug}.thym.cosm",
                             f"{slug}.package.cosm", f"{slug}.cosm"):
                    if (base / name).is_file():
                        if not _inside(base, base / name):
                            self.fail("unknown-uri", outside.format(why=f"is {name}, a link that leads out of it"),
                                      u.line)
                        found = base / name
                        break
            else:
                why = _escapes(uri)
                if why:
                    self.fail("unknown-uri", outside.format(why=why), u.line)
                if (base / uri).is_file():
                    if not _inside(base, base / uri):
                        self.fail("unknown-uri", outside.format(why="is a link that leads out of it"), u.line)
                    found = base / uri
        if found is None:
            self.fail("unknown-uri", f"nothing answers to {uri}: no such thym/1 volume or file is known here", u.line)
        if isinstance(found, ps.Module):
            return self.names_of_module(found, uri, u.line)
        if isinstance(found, (str, Path)):
            p = Path(found)
            if p.suffix == ".thym":
                return self.names_of_file(p, uri, u.line)
            try:
                found = mc.yaml_load(mc.read_text(p))
            except Exception as e:                      # noqa: BLE001  (a bad used file is a refusal)
                self.fail("unknown-uri", f"{uri} cannot be read as a thym/1 volume: {_yaml_problem(e)}", u.line)
            label = str(p)
        else:
            label = uri
        if not isinstance(found, dict) or found.get("oes") != "thym/1":
            self.fail("unknown-uri", f"{uri} is not a thym/1 volume or a .thym file", u.line)
        if found.get("kind") == "program" and isinstance(found.get("front"), str):
            from . import enumerate as en
            text = en.compile_volume(found)
            src = found.get("source") or {}
            mod = ps.parse(text, path=str(base / str(src.get("path") or f"{label}.thym")))
            if isinstance(mod, Refusal):
                self.fail("unknown-uri", f"{uri} holds a program that does not parse: {mod.message}", u.line)
            return self.names_of_module(mod, uri, u.line)
        out: dict[str, tuple[str, Any, str]] = {}
        for it in found.get("nodes") or []:
            if not isinstance(it, dict) or not isinstance(it.get("id"), str):
                continue
            mt = re.match(r"^(M:morph|C:context)/(.+)$", it["id"])
            if not mt:
                continue
            slug = mt.group(2)
            if mt.group(1) == "M:morph":
                out[slug] = ("morph", Binding(slug, "morph", "morph", u.line, label, source=it), label)
            else:
                fields = {k: self.python_type(v) for k, v in it.items() if k not in ENVELOPE_KEYS}
                out[slug] = ("context", Binding(slug, "context", "context", u.line, label, fields=fields, source=it),
                             label)
        return out

    def names_of_file(self, p: Path, uri: str, line: int) -> dict[str, tuple[str, Any, str]]:
        key = str(p.resolve())
        if key in self.seen:
            return {}
        try:
            text = p.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError) as e:
            self.fail("unknown-uri", f"{uri} cannot be read: {e}", line)
        mod = ps.parse(text, path=str(p))
        if isinstance(mod, Refusal):
            raise _Fail(mod)
        return self.names_of_module(mod, uri, line, key)

    def names_of_module(self, mod: ps.Module, uri: str, line: int, key: str | None = None) -> dict:
        sub = check(mod, decls=self.decls, volumes=self.volumes,
                    _seen=self.seen | {key or str(mod.path), str(Path(self.file).resolve()) if self.file else ""})
        if isinstance(sub, Refusal):
            raise _Fail(sub)
        label = mod.path or uri
        out: dict[str, tuple[str, Any, str]] = {}
        for b in mod.blocks:
            if b.kind == "move" and b.name in sub.moves:
                out[b.name] = ("move", sub.moves[b.name], label)
            elif b.kind in ("morph", "context") and b.name in sub.names:
                out[b.name] = (b.kind, sub.names[b.name], label)
        return out

    # -- values in data ----------------------------------------------------

    def value_type(self, e: ps.Expr) -> str:
        if isinstance(e, ps.Lit):
            return ty.literal_type(e.kind)
        if isinstance(e, ps.ListLit):
            return ty.list_of(ty.WORD) if all(isinstance(x, ps.Name) for x in e.items) else ty.list_of(ty.ANY)
        if isinstance(e, ps.Name):
            return ty.WORD
        if isinstance(e, ps.Uri):
            return ty.uri_type(e.uri)
        return ty.ANY

    @staticmethod
    def python_type(v: Any) -> str:
        if isinstance(v, bool):
            return "bool"
        if isinstance(v, int):
            return "number"
        if isinstance(v, str):
            return "string"
        return ty.ANY

    # -- blocks ------------------------------------------------------------

    def check_block(self, b: ps.Block) -> None:
        if b.kind == "morph":
            self.morph(b)
        elif b.kind == "context":
            self.context(b)
        elif b.kind == "move":
            self.body(b, None)
        else:
            for lm in b.moves:
                self.body(lm, b.name)
            self.body(b, b.name)

    def morph(self, b: ps.Block) -> None:
        seen: dict[str, int] = {}
        for s in b.scales:
            if s.scale not in ty.SCALES:
                near = difflib.get_close_matches(s.scale, ty.SCALES, n=1)
                self.fail("type", f"`{s.scale}` is not one of the ten scales" +
                          (f"; did you mean `{near[0]}`?" if near else f" ({', '.join(ty.SCALES)})"), s.line)
            if s.scale in seen:
                self.fail("type", f"{s.scale} is already set at line {seen[s.scale]}", s.line)
            seen[s.scale] = s.line
            value = s.value.value if isinstance(s.value, ps.Lit) else None
            if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 5:
                self.fail("type", f"{s.scale} takes an integer from 1 to 5", s.line)
            if s.toward is not None:
                if s.scale != "formality":
                    self.fail("type", f"only formality has a direction; {s.scale} takes a number alone", s.line)
                if s.toward not in ty.TOWARD:
                    self.fail("type", "formality departs toward casual or toward formal", s.line)
            elif s.scale == "formality" and value > 1:
                self.fail("type", f"formality {value} departs from plain: say which way, toward casual or toward "
                          "formal", s.line)

    def context(self, b: ps.Block) -> None:
        seen: dict[str, int] = {}
        for f in b.fields:
            if f.field in ENVELOPE_KEYS:
                self.fail("type", f"a context field may not be named `{f.field}`: the item's envelope uses it",
                          f.line)
            if f.field in seen:
                self.fail("rebound", f"{f.field} is already set at line {seen[f.field]}", f.line)
            seen[f.field] = f.line
            if isinstance(f.value, ps.FieldRead):
                self.fail("type", "a context field holds a literal or a word", f.line)

    def body(self, b: ps.Block, program: str | None) -> None:
        sink: dict[str, Binding] = {}
        self.symbols[b.qualified] = sink
        scope = _Scope(self.file_scope, sink)
        for p in (b.params if b.kind == "move" else b.takes):
            self.name_ok(p.name, p.line, "an input" if b.kind == "program" else "a parameter")
            if scope.lookup(p.name) is not None:
                self.fail("rebound", f"`{p.name}` is already bound; a name is bound once", p.line)
            scope.add(Binding(p.name, p.type, "param" if b.kind == "move" else "takes", p.line, self.file))
        ctx = _Ctx(block=b, program=program)
        self.stmts(b.stmts, scope, ctx)
        if b.gives is not None and not reaches_give(b.stmts):
            self.fail("no-give", f"{b.kind} {b.name} gives {b.gives.name}: {b.gives.type}, and a path through it "
                      "never reaches a give", b.line)
        if b.kind == "program":
            self.emits_and_counts(b, ctx)

    def emits_and_counts(self, b: ps.Block, ctx: _Ctx) -> None:
        emits, targets = self.reach(b.stmts, set())
        if not emits:
            return
        consumers = ct.consumer_checks(targets)
        if not any(getattr(t, "name", None) in ct.EMIT_CONSUMERS for t in targets):
            first = emits[0]
            self.fail("emit-without-project", f"{b.kind} {b.name} emits items and never projects them, so they go "
                      "nowhere: give project … as isotype, or remove the emit", first.line)
        if "no-counts" in consumers:
            for e in emits:
                if e.slot is not None and e.expr.type == "number":
                    self.fail("no-counts", f"a number reaches the projection's {e.slot} field, and project's "
                              f"contract forbids counts: band it first (emit {e.slot}: band (…) as [none, some])",
                              e.line)

    def reach(self, stmts: list[ps.Stmt], seen: set[int]) -> tuple[list[ps.Emit], list[Any]]:
        """Every emit, and every call target, these statements reach, through the user moves they call."""
        emits: list[ps.Emit] = []
        targets: list[Any] = []
        for s in walk(stmts):
            if isinstance(s, ps.Emit):
                emits.append(s)
            for c in step_calls(s):
                t = c.target
                targets.append(t)
                if isinstance(t, UserMove) and id(t) not in seen:
                    seen.add(id(t))
                    e2, t2 = self.reach(t.block.stmts, seen)
                    emits.extend(e2)
                    targets.extend(t2)
        return emits, targets

    # -- statements --------------------------------------------------------

    def stmts(self, stmts: list[ps.Stmt], scope: _Scope, ctx: _Ctx) -> None:
        for s in stmts:
            self.stmt(s, scope, ctx)

    def bind(self, scope: _Scope, name: str, t: str, kind: str, line: int, ctx: _Ctx) -> Binding:
        self.name_ok(name, line, "a binding")
        prev = scope.lookup(name)
        if prev is not None:
            where = f" at line {prev.line}" if prev.line and prev.file == self.file else ""
            self.fail("rebound", f"`{name}` is already bound{where}; a name is bound once", line)
        if name in self.moves or name in self.local.get(ctx.program or "", {}):
            self.fail("type", f"`{name}` is a move of this file and cannot name a binding", line)
        b = Binding(name, t, kind, line, self.file)
        scope.add(b)
        return b

    def stmt(self, s: ps.Stmt, scope: _Scope, ctx: _Ctx) -> None:
        if isinstance(s, ps.Let):
            t = self.expr(s.expr, scope, ctx)
            s.binding = self.bind(scope, s.name, t, "let", s.line, ctx)
        elif isinstance(s, ps.Assert):
            self.cond(s.cond, scope, ctx, items=False)
        elif isinstance(s, ps.If):
            self.cond(s.cond, scope, ctx, items=False)
            self.stmts(s.then, scope.child(), ctx)
            if s.else_ is not None:
                self.stmts(s.else_, scope.child(), ctx)
        elif isinstance(s, ps.For):
            coll = self.expr(s.coll, scope, ctx)
            member = self.member(coll, s.coll)
            inner = scope.child()
            s.binding = self.bind(inner, s.var, member, "loop", s.line, ctx)
            if s.where is not None:
                self.cond(s.where, inner, ctx, items=True)
            was = ctx.in_loop
            ctx.in_loop = True
            self.stmts(s.body, inner, ctx)
            ctx.in_loop = was
        elif isinstance(s, ps.Emit):
            t = self.expr(s.expr, scope, ctx)
            if s.slot is None and not self.emittable(s.expr, t):
                self.fail("type", f"an emit adds an item to the output volume; {ps.render(s.expr)} gives a {t}"
                          + (": mark it first (… marked verified), or emit it into a field (emit <field>: …)"
                             if t == ty.WORD else ""), s.line)
        elif isinstance(s, ps.Give):
            if ctx.in_loop:
                self.fail("type", "a loop body may not give: a block gives once, after its loops", s.line)
            b = ctx.block
            if b.gives is None:
                self.fail("type", f"{b.kind} {b.name} gives nothing, so it cannot give: add a gives head", s.line)
            t = self.expr(s.expr, scope, ctx)
            if not ty.accepts([b.gives.type], t):
                fix = ty.hint(t, [b.gives.type])
                self.fail("type", f"{b.kind} {b.name} gives {b.gives.name}: {b.gives.type}, and "
                          f"{ps.render(s.expr)} is a {t}" + (f": {fix}" if fix else ""), s.line)
        elif isinstance(s, ps.Withhold):
            self.expr(s.call, scope, ctx)
        elif isinstance(s, ps.Effect):
            self.expr(s.expr, scope, ctx)

    @staticmethod
    def emittable(e: ps.Expr, t: str) -> bool:
        if t in ("item", ty.ANY):
            return True
        if t == ty.WORD:
            inner = strip_paren(e)
            return isinstance(inner, ps.Marked) or (isinstance(inner, ps.Call) and inner.move == "mark")
        return False

    def member(self, t: str, e: ps.Expr) -> str:
        if t in ("volume", "fabula"):
            return "item"
        if t == "short":
            return "string"
        if ty.is_list(t):
            return ty.element(t)
        if t == ty.ANY:
            return ty.ANY
        self.fail("type", f"for each goes through a volume, a fabula, a short or a list; {ps.render(e)} is a {t}",
                  e.line)
        return ty.ANY

    # -- expressions -------------------------------------------------------

    def find_move(self, name: str, ctx: _Ctx) -> Any:
        if ctx.program and name in self.local.get(ctx.program, {}):
            return self.local[ctx.program][name]
        if name in self.moves:
            return self.moves[name]
        return self.decls.get(name)

    def visible_moves(self, ctx: _Ctx) -> list[str]:
        return sorted(set(self.decls) | set(self.moves) | set(self.local.get(ctx.program or "", {})))

    def expr(self, e: Any, scope: _Scope, ctx: _Ctx, *, word_ok: bool = False, items: bool = False) -> str:
        t = self._expr(e, scope, ctx, word_ok=word_ok, items=items)
        e.type = t
        return t

    def _expr(self, e: Any, scope: _Scope, ctx: _Ctx, *, word_ok: bool, items: bool) -> str:
        if isinstance(e, ps.Name):
            return self.name(e, scope, ctx, word_ok=word_ok, items=items)
        if isinstance(e, ps.Word):
            return ty.WORD
        if isinstance(e, ps.Lit):
            return ty.literal_type(e.kind)
        if isinstance(e, ps.Uri):
            return ty.uri_type(e.uri)
        if isinstance(e, ps.ListLit):
            types = {self.expr(x, scope, ctx, word_ok=True) for x in e.items}
            types.discard(ty.ANY)
            if len(types) > 1:
                self.fail("type", f"a list holds values of one type; {ps.render(e)} mixes {', '.join(sorted(types))}",
                          e.line)
            return ty.list_of(types.pop() if types else ty.ANY)
        if isinstance(e, ps.FieldRead):
            tt = self.expr(e.target, scope, ctx, items=items)
            if tt in ty.PLAIN or tt == ty.NOTHING:
                self.fail("type", f"a {tt} has no fields; {ps.render(e)} reads one", e.line)
            target = e.target
            if isinstance(target, ps.Name) and isinstance(target.binding, Binding) and target.binding.fields:
                return target.binding.fields.get(e.field, ty.ANY)
            return ty.ANY
        if isinstance(e, ps.Paren):
            return self.expr(e.inner, scope, ctx, word_ok=word_ok, items=items)
        if isinstance(e, ps.Filter):
            tt = self.expr(e.target, scope, ctx, items=items)
            if tt in ("volume", "fabula"):
                member = "item"
            elif ty.is_list(tt):
                member = ty.element(tt)
            elif tt == ty.ANY:
                member = ty.ANY
            else:
                self.fail("type", f"where filters a volume or a list; {ps.render(e.target)} is a {tt}", e.line)
                member = ty.ANY
            self.cond(e.cond, scope, ctx, items=True)
            return ty.list_of(member)
        if isinstance(e, ps.Marked):
            return self.marked(e, scope, ctx)
        if isinstance(e, ps.Call):
            return self.call(e, scope, ctx)
        if isinstance(e, ps.Units):
            return ty.ANY
        return ty.ANY

    def name(self, e: ps.Name, scope: _Scope, ctx: _Ctx, *, word_ok: bool, items: bool) -> str:
        b = scope.lookup(e.name)
        if b is not None:
            e.kind, e.binding = "binding", b
            return b.type
        if e.name in ty.LITERAL_WORDS or (word_ok and ps.NAME.match(e.name)):
            e.kind = "word"
            return ty.WORD
        if items:
            e.kind = "field"
            return ty.ANY
        if self.find_move(e.name, ctx) is not None:
            self.fail("type", f"`{e.name}` is a move: call it with its operands (or in parentheses as an operand)",
                      e.line)
        self.fail("unbound", f"`{e.name}` is not bound: take it with takes, bind it with let, or name a block of "
                  "this file", e.line)
        return ty.ANY

    def marked(self, e: ps.Marked, scope: _Scope, ctx: _Ctx) -> str:
        it = self.expr(e.inner, scope, ctx)
        decl = self.decls.get("mark")
        if decl is None:
            self.fail("unknown-move", "marked is short for mark … as …, and no manifest declares mark", e.line)
        e.target = decl
        if it not in ("item", ty.WORD, ty.ANY):
            self.fail("type", f"marked takes an item or a word; {ps.render(e.inner)} is a {it}", e.line)
        alts = list(decl.modifiers.get("as", ("marking",)))
        if not ty.accepts(alts, ty.WORD, word=e.word):
            self.fail("type", f"marked takes {ty.show(alts)}; `{e.word}` is not one", e.line)
        return it

    def call(self, c: ps.Call, scope: _Scope, ctx: _Ctx) -> str:
        target = self.find_move(c.move, ctx)
        if target is None:
            near = difflib.get_close_matches(c.move, self.visible_moves(ctx), n=1, cutoff=0.4)
            self.fail("unknown-move", f"unknown move `{c.move}`" + (f"; did you mean `{near[0]}`?" if near else
                      "; no manifest declares it and no move block of this file is named so"), c.line)
        c.target = target
        if isinstance(target, UserMove):
            if len(c.operands) != len(target.params):
                self.fail("type", f"{c.move} takes {len(target.params)} operand(s) "
                          f"({', '.join(f'{n}: {t}' for n, t in target.params) or 'none'}); given {len(c.operands)}",
                          c.line)
            for op, (pn, pt) in zip(c.operands, target.params):
                t = self.expr(op, scope, ctx)
                if not ty.accepts([pt], t):
                    fix = ty.hint(t, [pt])
                    self.fail("type", f"{c.move} takes {pn}: {pt}, and {ps.render(op)} is a {t}"
                              + (f": {fix}" if fix else ""), op.line)
            if c.mods:
                self.fail("type", f"{c.move} is a move of this file and takes no modifiers; its parameters are "
                          "operands", c.line)
            return target.gives
        takes = [list(a) for a in target.takes]
        if not takes and c.operands:
            self.fail("type", f"{c.move} takes no operand" + (f"; its argument is its of: {c.move} of …"
                                                              if "of" in target.modifiers else ""), c.line)
        if len(c.operands) != len(takes):
            self.fail("type", f"{c.move} takes {len(takes)} operand(s) ({'; '.join(ty.show(a) for a in takes)}); "
                      f"given {len(c.operands)}", c.line)
        for op, alts in zip(c.operands, takes):
            t = self.expr(op, scope, ctx)
            w = strip_paren(op)
            word = w.name if isinstance(w, ps.Name) and w.kind == "word" else None
            if not ty.accepts(alts, t, word=word):
                fix = ty.hint(t, alts)
                self.fail("type", f"{c.move} takes {ty.show(alts)}, and {ps.render(op)} is a {t}"
                          + (f": {fix}" if fix else ""), op.line)
        declared = list(target.modifiers)
        last = -1
        for m in c.mods:
            if m.word not in target.modifiers:
                self.fail("type", f"{c.move} takes no `{m.word}`" + (f"; it takes {', '.join(declared)}" if declared
                                                                    else ""), m.line)
            pos = declared.index(m.word)
            if pos < last:
                self.fail("type", f"the modifiers of {c.move} come in the order {', '.join(declared)}", m.line)
            last = pos
            self.modifier(c, m, list(target.modifiers[m.word]), scope, ctx)
        if not takes and "of" in target.modifiers and c.mod("of") is None:
            self.fail("type", f"{c.move} takes its argument through of: {c.move} of …", c.line)
        gives = list(target.gives)
        if len(gives) == 1:
            return gives[0]
        if c.operands and c.operands[0].type in gives:
            return c.operands[0].type
        return ty.ANY

    def modifier(self, c: ps.Call, m: ps.Mod, alts: list[str], scope: _Scope, ctx: _Ctx) -> None:
        arg = m.arg
        if alts == [ty.CONDITION]:
            if not isinstance(arg, ps.Cond):
                self.fail("type", f"{c.move} {m.word} takes a condition", m.line)
            self.cond(arg, scope, ctx, items=True)
            return
        if isinstance(arg, ps.Cond):
            self.fail("type", f"{c.move} {m.word} takes {ty.show(alts)}, not a condition", m.line)
        if isinstance(arg, ps.Units):
            arg.type = ty.ANY
            if not any(a in ty.UNITS for a in alts) or arg.unit not in alts:
                self.fail("type", f"{c.move} {m.word} takes {' or '.join(a for a in alts if a in ty.UNITS) or 'no unit'}"
                          f", not {arg.unit}", m.line)
            return
        if isinstance(arg, ps.Word):
            arg.type = ty.WORD
            if not ty.accepts(alts, ty.WORD, word=arg.word):
                self.fail("type", f"{c.move} {m.word} takes {ty.show(alts)}; `{arg.word}` is not one", m.line)
            return
        if isinstance(arg, ps.ListLit) and all(isinstance(x, ps.Word) for x in arg.items):
            for x in arg.items:
                x.type = ty.WORD
            arg.type = ty.list_of(ty.WORD)
            if not ty.accepts(alts, arg.type):
                self.fail("type", f"{c.move} {m.word} takes {ty.show(alts)}, not a list", m.line)
            return
        t = self.expr(arg, scope, ctx)
        if t == ty.NOTHING:
            self.fail("type", f"{c.move} {m.word} takes {ty.show(alts)}; for none, leave `{m.word}` out", m.line)
        if not ty.accepts(alts, t):
            fix = ty.hint(t, alts)
            self.fail("type", f"{c.move} {m.word} takes {ty.show(alts)}, and {ps.render(arg)} is a {t}"
                      + (f": {fix}" if fix else ""), m.line)

    # -- conditions --------------------------------------------------------

    def cond(self, c: Any, scope: _Scope, ctx: _Ctx, *, items: bool) -> None:
        if isinstance(c, ps.Logic):
            self.cond(c.left, scope, ctx, items=items)
            self.cond(c.right, scope, ctx, items=items)
        elif isinstance(c, ps.Not):
            self.cond(c.inner, scope, ctx, items=items)
        elif isinstance(c, ps.Compare):
            lt = self.expr(c.left, scope, ctx, items=items)
            if c.op in ("is", "is not"):
                self.expr(c.right, scope, ctx, word_ok=True, items=items)
            elif c.op == "in":
                rt = self.expr(c.right, scope, ctx, items=items)
                if not (ty.is_list(rt) or rt == ty.ANY):
                    self.fail("type", f"in tests membership in a list; {ps.render(c.right)} is a {rt}", c.line)
            elif c.op in ("<", ">"):
                rt = self.expr(c.right, scope, ctx, items=items)
                for t, side in ((lt, c.left), (rt, c.right)):
                    if t not in ("number", "date", ty.ANY):
                        self.fail("type", f"{c.op} compares numbers or dates; {ps.render(side)} is a {t}", c.line)
            else:
                self.expr(c.right, scope, ctx, items=items)
        elif isinstance(c, ps.Has):
            self.expr(c.target, scope, ctx, items=items)
        elif isinstance(c, ps.Covers):
            lt = self.expr(c.left, scope, ctx, items=items)
            rt = self.expr(c.right, scope, ctx, items=items)
            if lt not in ("fabula", ty.ANY):
                fix = ty.hint(lt, ["fabula"])
                self.fail("type", f"covers takes a fabula on its left; {ps.render(c.left)} is a {lt}"
                          + (f": {fix}" if fix else ""), c.line)
            if rt not in ("text", "short", ty.ANY):
                self.fail("type", f"covers takes a text or a short on its right; {ps.render(c.right)} is a {rt}",
                          c.line)
        elif isinstance(c, ps.Truth):
            t = self.expr(c.expr, scope, ctx, items=items)
            if t not in ("bool", ty.ANY):
                self.fail("type", f"a condition needs a bool; {ps.render(c.expr)} is a {t}", c.line)

    # -- recursion and inheritance ------------------------------------------

    def callees(self, mv: UserMove) -> list[UserMove]:
        out: list[UserMove] = []
        for s in walk(mv.block.stmts):
            for c in step_calls(s):
                t = getattr(c, "target", None)
                if isinstance(t, UserMove) and t.module is self.m and t not in out:
                    out.append(t)
        return out

    def no_recursion(self) -> None:
        mine = [mv for mv in self.user_moves]
        state: dict[int, int] = {}
        on_cycle: list[tuple[UserMove, list[UserMove]]] = []

        def visit(mv: UserMove, path: list[UserMove]) -> None:
            state[id(mv)] = 1
            for nxt in self.callees(mv):
                if state.get(id(nxt)) == 1:
                    cycle = path[path.index(nxt):] + [nxt] if nxt in path else [mv, nxt]
                    on_cycle.append((nxt, cycle))
                elif state.get(id(nxt)) is None:
                    visit(nxt, path + [nxt])
            state[id(mv)] = 2

        for mv in mine:
            if state.get(id(mv)) is None:
                visit(mv, [mv])
        if on_cycle:
            first, cycle = min(on_cycle, key=lambda x: x[0].line)
            chain = " → ".join(m.name for m in cycle)
            how = "calls itself" if len(cycle) <= 2 and cycle[0] is cycle[-1] else f"calls itself through {chain}"
            self.fail("recursion", f"move {first.name} {how}; version 0 has no recursion", first.line)

    def inherit(self, mv: UserMove, busy: set[int]) -> UserMove:
        if mv.inherited or id(mv) in busy:
            return mv
        busy.add(id(mv))
        calls: list[str] = []
        checks: list[str] = []
        asks = False
        for s in walk(mv.block.stmts):
            for c in step_calls(s):
                calls.append(move_name(c))
                t = getattr(c, "target", None)
                if isinstance(t, UserMove):
                    self.inherit(t, busy)
                    calls.extend(t.calls)
                    checks.extend(t.checks)
                    asks = asks or t.asks
                elif t is not None:
                    checks.extend(ct.checks_of(t))
                    asks = asks or bool(getattr(t, "asks", False))
            if isinstance(s, ps.Assert):
                checks.extend(ct.condition_checks(s.cond))
        mv.calls = _once(calls)
        mv.checks = _once(checks)
        mv.asks = asks
        mv.inherited = True
        return mv


def _once(xs: list[str]) -> list[str]:
    out: list[str] = []
    for x in xs:
        if x not in out:
            out.append(x)
    return out


def check(module: ps.Module, *, decls: dict | None = None, volumes: Volumes = None,
          _seen: frozenset[str] = frozenset()) -> Checked | Refusal:
    """Resolve, type-check and contract-check a parsed module. `decls` are the declared moves (the bundled
    registry's by default); `volumes` answers a `use oes:…` (a mapping or a function from the URI to a loaded
    `thym/1` mapping, a path, or a parsed module), before the files beside the program are looked at."""
    if isinstance(module, Refusal):
        return module
    if not isinstance(module, ps.Module):
        return Refusal("compile", "parse", "check takes a parsed module", None, None)
    decls = dc.load() if decls is None else decls
    try:
        return _Checker(module, decls, volumes, _seen).run()
    except _Fail as f:
        return f.refusal
    except RecursionError:
        return Refusal("compile", "parse", "the program nests too deeply", None, module.path)
