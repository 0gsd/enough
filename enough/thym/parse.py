"""Thym's parser: a `.thym` file into a tree, by recursive descent over the grammar of THYM.md 4.8, with sections
4.1–4.6 as its prose rules.

The file is read line by line. Its first line that is neither blank nor a comment is the version line, `thym 0`;
after it come `use` lines and the four kinds of block (`program`, `move`, `morph`, `context`), each closed by
`end`, with `move` blocks also standing inside a program before its statements. A comment runs from `--` to the end
of the line, outside strings, and a line holding only a comment counts as blank. A block's prose heads (`why:`,
`must:`, `decided <date>:`) run to a blank line, a line whose first word is a head keyword, or `end`; a prose line
that begins with a statement keyword is kept as prose with a warning on the module, since the writer probably
forgot the blank line. A statement ends at the end of its line, except inside parentheses or a list.

Calls are read with the names of the moves the file can see: the declared moves (`declarations.names()`), the file's
own `move` blocks, and the `move` blocks of the `.thym` files it `use`s. A modifier's argument that begins with a
move name is itself a call that takes every modifier after it (`measure story against null of f`). A name followed
by an operand is read as a call even when no move has that name, so that the checker can refuse it as an unknown
move with the nearest name.

Every node keeps its 1-based `line`; every statement keeps its source `text` verbatim and its `comment`. `parse`
returns a `Module`, or a `Refusal` with the check `parse` or `version` and the line; it never raises for bad input.
`render` and `render_cond` write an expression back in canonical spacing, which the plan uses to name its nodes.
"""
from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from . import Refusal
from . import types as ty

KEYWORDS = frozenset("""
thym use program move morph context end
why must decided takes gives
let assert if then else for each in where emit give withhold
as by with to against of marked
is not and or has covers
true false nothing
""".split())
HEAD_WORDS = ("why", "must", "decided", "takes", "gives")
STATEMENT_WORDS = ("let", "assert", "if", "for", "emit", "give", "withhold")
MODIFIER_WORDS = ("as", "by", "with", "to", "against", "of", "in", "where", "marked")
BLOCK_WORDS = ("program", "move", "morph", "context")
LITERAL_KEYWORDS = ("true", "false", "nothing")

NAME = re.compile(r"^[a-z][a-z0-9-]*$")
FIELD = re.compile(r"^[a-z][a-z0-9_-]*$")
_FIRST_WORD = re.compile(r"^\s*([a-z][a-z0-9_-]*)")
_MOVE_LINE = re.compile(r"^\s*move\s+([a-z][a-z0-9-]*)\s*\(", re.M)
_USE_LINE = re.compile(r"^\s*use\s+(\S+)", re.M)
_TOKEN = re.compile(r"""
    (?P<ws>[ \t]+)
  | (?P<uri>oes:[^\s,()\[\]]+)
  | (?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})(?![0-9A-Za-z_-])
  | (?P<int>[0-9]+)(?![0-9A-Za-z_])
  | (?P<name>[a-z][a-z0-9_-]*)
  | (?P<string>"(?:[^"\\]|\\["\\])*")
  | (?P<punct>[()\[\],.:=<>])
""", re.X)


# ---------------------------------------------------------------------------
# The tree
# ---------------------------------------------------------------------------

@dataclass(eq=False, kw_only=True)
class Node:
    line: int


# Expressions. `type` is filled in by the checker.

@dataclass(eq=False, kw_only=True)
class Expr(Node):
    type: str | None = None


@dataclass(eq=False, kw_only=True)
class Name(Expr):
    """A bare name. The checker decides what it is (`kind`): a binding, a word standing for itself, or the current
    item's field inside a `where` over items."""
    name: str
    kind: str | None = None
    binding: Any = None


@dataclass(eq=False, kw_only=True)
class Word(Expr):
    """A bare word where only a word can stand: after `as`, `by` and `marked`."""
    word: str


@dataclass(eq=False, kw_only=True)
class Lit(Expr):
    """A literal: kind `number`, `string`, `date`, `bool` or `nothing`."""
    kind: str
    value: Any


@dataclass(eq=False, kw_only=True)
class ListLit(Expr):
    items: list[Expr]


@dataclass(eq=False, kw_only=True)
class Uri(Expr):
    uri: str


@dataclass(eq=False, kw_only=True)
class FieldRead(Expr):
    target: Expr
    field: str


@dataclass(eq=False, kw_only=True)
class Paren(Expr):
    inner: Expr


@dataclass(eq=False, kw_only=True)
class Units(Expr):
    """The argument of `to`: a number and a unit, `300 words`."""
    count: int
    unit: str


@dataclass(eq=False, kw_only=True)
class Mod(Node):
    word: str
    arg: Any                     # Expr, Word, ListLit of Word, Units, or a Cond (for `where`)


@dataclass(eq=False, kw_only=True)
class Call(Expr):
    """A move call: the move's name, its operands, its modifiers in the order written. `known` is False when no
    move the parser could see has this name. `target` is filled in by the checker (a declaration or a user move)."""
    move: str
    operands: list[Expr] = field(default_factory=list)
    mods: list[Mod] = field(default_factory=list)
    known: bool = True
    target: Any = None

    def mod(self, word: str) -> Mod | None:
        return next((m for m in self.mods if m.word == word), None)


@dataclass(eq=False, kw_only=True)
class Filter(Expr):
    """`primary where cond`: the items of a volume, or the members of a list, that satisfy cond."""
    target: Expr
    cond: Any


@dataclass(eq=False, kw_only=True)
class Marked(Expr):
    """`expr marked <word>`, short for `mark expr as <word>` (THYM.md 4.5). `target` is the `mark` declaration."""
    inner: Expr
    word: str
    target: Any = None


# Conditions.

@dataclass(eq=False, kw_only=True)
class Cond(Node):
    pass


@dataclass(eq=False, kw_only=True)
class Logic(Cond):
    op: str                      # and, or
    left: Cond
    right: Cond


@dataclass(eq=False, kw_only=True)
class Not(Cond):
    inner: Cond


@dataclass(eq=False, kw_only=True)
class Compare(Cond):
    op: str                      # is, is not, in, <, >, =
    left: Expr
    right: Expr


@dataclass(eq=False, kw_only=True)
class Has(Cond):
    target: Expr
    field: str


@dataclass(eq=False, kw_only=True)
class Covers(Cond):
    left: Expr
    right: Expr


@dataclass(eq=False, kw_only=True)
class Truth(Cond):
    expr: Expr


# Statements. `text` is the statement's source verbatim (its header lines for `if` and `for each`); `end` is its
# last line (the `end` line for `if` and `for each`); `comment` the text of its first comment.

@dataclass(eq=False, kw_only=True)
class Stmt(Node):
    text: str
    end: int
    comment: str | None = None
    header_end: int = 0          # the last line of the statement's own text

    @property
    def form(self) -> str:
        return _FORMS[type(self).__name__]


@dataclass(eq=False, kw_only=True)
class Let(Stmt):
    name: str
    expr: Expr
    binding: Any = None


@dataclass(eq=False, kw_only=True)
class Assert(Stmt):
    cond: Cond
    message: str | None = None


@dataclass(eq=False, kw_only=True)
class If(Stmt):
    cond: Cond
    then: list[Stmt]
    else_: list[Stmt] | None = None
    else_line: int | None = None


@dataclass(eq=False, kw_only=True)
class For(Stmt):
    var: str
    coll: Expr
    where: Cond | None
    body: list[Stmt]
    binding: Any = None


@dataclass(eq=False, kw_only=True)
class Emit(Stmt):
    slot: str | None
    expr: Expr


@dataclass(eq=False, kw_only=True)
class Give(Stmt):
    expr: Expr


@dataclass(eq=False, kw_only=True)
class Withhold(Stmt):
    """`withhold <expr> [where <cond>]`: a call of the move `withhold`, kept as one."""
    call: Call


@dataclass(eq=False, kw_only=True)
class Effect(Stmt):
    expr: Expr


_FORMS = {"Let": "let", "Assert": "assert", "If": "if", "For": "for", "Emit": "emit", "Give": "give",
          "Withhold": "withhold", "Effect": "effect"}


# Blocks.

@dataclass(eq=False, kw_only=True)
class Param(Node):
    name: str
    type: str


@dataclass(eq=False, kw_only=True)
class Prose(Node):
    text: str
    end: int


@dataclass(eq=False, kw_only=True)
class Decided(Node):
    date: _dt.date
    what: str
    end: int


@dataclass(eq=False, kw_only=True)
class ScaleLine(Node):
    scale: str
    value: Expr
    toward: str | None = None


@dataclass(eq=False, kw_only=True)
class FieldLine(Node):
    field: str
    value: Expr


@dataclass(eq=False, kw_only=True)
class Block(Node):
    """One block. `end` is its `end` line. A program's inputs are `takes`, a move's `params`; both may have
    `gives` (a move's is named after the move). `parent` names the program a local move stands in."""
    kind: str
    name: str
    end: int = 0
    why: Prose | None = None
    musts: list[Prose] = field(default_factory=list)
    decideds: list[Decided] = field(default_factory=list)
    takes: list[Param] = field(default_factory=list)
    params: list[Param] = field(default_factory=list)
    gives: Param | None = None
    moves: list["Block"] = field(default_factory=list)
    stmts: list[Stmt] = field(default_factory=list)
    scales: list[ScaleLine] = field(default_factory=list)
    fields: list[FieldLine] = field(default_factory=list)
    parent: str | None = None

    @property
    def qualified(self) -> str:
        """`<program>.<move>` for a local move, else the name: what its ids are built from."""
        return f"{self.parent}.{self.name}" if self.parent else self.name


@dataclass(eq=False, kw_only=True)
class Use(Node):
    uri: str
    text: str


@dataclass(frozen=True)
class ParseWarning:
    line: int
    message: str

    def __str__(self) -> str:
        return f"line {self.line}: {self.message}"


@dataclass(eq=False)
class Module:
    """A parsed file. `raw_lines` are its lines split on LF only, a CR kept, so that bodies are its bytes;
    `lines` are the same without the CR (and the byte-order mark)."""
    path: str | None
    text: str
    raw_lines: list[str]
    lines: list[str]
    version_line: int
    uses: list[Use]
    blocks: list[Block]
    warnings: list[ParseWarning]
    moves_known: frozenset[str]

    @property
    def file_name(self) -> str:
        if self.path:
            return Path(self.path).name
        first = next((b for b in self.blocks if b.kind == "program"), None) or (self.blocks[0] if self.blocks else None)
        return f"{first.name if first else 'program'}.thym"

    def programs(self) -> list[Block]:
        return [b for b in self.blocks if b.kind == "program"]


# ---------------------------------------------------------------------------
# Lines and tokens
# ---------------------------------------------------------------------------

def strip_comment(line: str) -> tuple[str, str | None]:
    """(the line without its comment and trailing space, the comment's text or None). `--` inside a string is not
    a comment."""
    i, n, in_str = 0, len(line), False
    while i < n:
        c = line[i]
        if in_str:
            if c == "\\" and i + 1 < n:
                i += 2
                continue
            if c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "-" and line.startswith("--", i):
            return line[:i].rstrip(), line[i + 2:].strip()
        i += 1
    return line.rstrip(), None


def _prose_text(line: str) -> str:
    """A prose line without its comment: prose holds no strings, so `--` always starts one."""
    return line.split("--", 1)[0].strip()


@dataclass(frozen=True)
class Token:
    kind: str                    # name, int, date, string, uri, punct
    text: str
    value: Any
    line: int


class _Fail(Exception):
    def __init__(self, check: str, message: str, line: int):
        super().__init__(message)
        self.check, self.message, self.line = check, message, line


def _unescape(s: str) -> str:
    return s[1:-1].replace('\\"', '"').replace("\\\\", "\\")


def _tokens(code: str, line: int) -> list[Token]:
    out: list[Token] = []
    pos, n = 0, len(code)
    while pos < n:
        mt = _TOKEN.match(code, pos)
        if not mt or mt.end() == pos:
            ch = code[pos]
            if ch == '"':
                raise _Fail("parse", "a string is never closed: strings take double quotes on one line", line)
            if ch.isupper():
                raise _Fail("parse", f"`{_word_at(code, pos)}`: names are lowercase", line)
            raise _Fail("parse", f"`{ch}` is not part of Thym's grammar", line)
        kind = mt.lastgroup
        text = mt.group(kind)
        pos = mt.end()
        if kind == "ws":
            continue
        value: Any = text
        if kind == "int":
            value = int(text)
        elif kind == "string":
            value = _unescape(text)
        elif kind == "date":
            try:
                value = _dt.date.fromisoformat(text)
            except ValueError:
                raise _Fail("parse", f"{text} is not a date", line) from None
        out.append(Token(kind, text, value, line))
    return out


def _word_at(code: str, pos: int) -> str:
    mt = re.match(r"[A-Za-z0-9_-]+", code[pos:])
    return mt.group(0) if mt else code[pos]


def _depth(tokens: list[Token]) -> int:
    d = 0
    for t in tokens:
        if t.kind == "punct" and t.text in "([":
            d += 1
        elif t.kind == "punct" and t.text in ")]":
            d -= 1
    return d


class _Stream:
    """The tokens of one logical line, read left to right."""

    def __init__(self, tokens: list[Token], line: int):
        self.toks, self.pos, self.line = tokens, 0, line

    def peek(self, k: int = 0) -> Token | None:
        i = self.pos + k
        return self.toks[i] if i < len(self.toks) else None

    def next(self) -> Token:
        t = self.peek()
        if t is None:
            raise _Fail("parse", "the line ends too soon", self.last_line())
        self.pos += 1
        return t

    def last_line(self) -> int:
        return self.toks[-1].line if self.toks else self.line

    def is_word(self, w: str) -> bool:
        t = self.peek()
        return t is not None and t.kind == "name" and t.text == w

    def is_punct(self, p: str) -> bool:
        t = self.peek()
        return t is not None and t.kind == "punct" and t.text == p

    def take_word(self, w: str) -> bool:
        if self.is_word(w):
            self.pos += 1
            return True
        return False

    def expect_word(self, w: str, why: str) -> Token:
        t = self.peek()
        if t is None or t.kind != "name" or t.text != w:
            raise _Fail("parse", why, t.line if t else self.last_line())
        self.pos += 1
        return t

    def expect_punct(self, p: str, why: str) -> Token:
        t = self.peek()
        if t is None or t.kind != "punct" or t.text != p:
            raise _Fail("parse", why, t.line if t else self.last_line())
        self.pos += 1
        return t

    def name(self, why: str, *, field_ok: bool = False) -> Token:
        t = self.peek()
        if t is None or t.kind != "name":
            raise _Fail("parse", why, t.line if t else self.last_line())
        if not (FIELD if field_ok else NAME).match(t.text):
            raise _Fail("parse", f"`{t.text}`: a name is lowercase letters, digits and hyphens", t.line)
        self.pos += 1
        return t

    def end(self) -> None:
        t = self.peek()
        if t is not None:
            raise _Fail("parse", f"unexpected `{t.text}`: a line holds one statement, and this one has ended", t.line)


def _operand_start(t: Token | None) -> bool:
    if t is None:
        return False
    if t.kind in ("int", "date", "string", "uri"):
        return True
    if t.kind == "punct":
        return t.text in ("(", "[")
    return t.text not in KEYWORDS or t.text in LITERAL_KEYWORDS


# ---------------------------------------------------------------------------
# The parser
# ---------------------------------------------------------------------------

class _Parser:
    def __init__(self, text: str, path: str | None, moves: frozenset[str]):
        self.text, self.path, self.moves = text, path, moves
        self.raw = text.split("\n")
        lines = [ln[:-1] if ln.endswith("\r") else ln for ln in self.raw]
        if lines and lines[0].startswith("﻿"):
            lines[0] = lines[0][1:]
        self.lines = lines
        pairs = [strip_comment(ln) for ln in lines]
        self.codes = [p[0] for p in pairs]
        self.comments = [p[1] for p in pairs]
        self.warnings: list[ParseWarning] = []
        self.n = len(lines)

    # -- helpers -----------------------------------------------------------

    def blank(self, i: int) -> bool:
        return not self.codes[i].strip()

    def first_word(self, i: int) -> str | None:
        mt = _FIRST_WORD.match(self.codes[i])
        return mt.group(1) if mt else None

    def logical(self, i: int) -> tuple[list[Token], int]:
        """The tokens of the statement starting on line i (0-based), joining lines while a parenthesis or a list is
        open; and the index of its last line."""
        toks = _tokens(self.codes[i], i + 1)
        j = i
        while _depth(toks) > 0:
            j += 1
            if j >= self.n:
                raise _Fail("parse", "a parenthesis or a list opened here is never closed", i + 1)
            toks += _tokens(self.codes[j], j + 1)
        if _depth(toks) < 0:
            raise _Fail("parse", "a closing parenthesis or bracket with nothing open", i + 1)
        return toks, j

    def first_comment(self, i: int, j: int) -> str | None:
        return next((self.comments[k] for k in range(i, j + 1) if self.comments[k]), None)

    def source(self, i: int, j: int) -> str:
        return "\n".join(self.raw[i:j + 1])

    # -- the file ----------------------------------------------------------

    def run(self) -> Module:
        i = 0
        while i < self.n and self.blank(i):
            i += 1
        if i == self.n:
            raise _Fail("version", "an empty program: a program starts with its version line, thym 0", 1)
        try:
            toks = _tokens(self.codes[i], i + 1)
        except _Fail:
            toks = []
        if not (len(toks) == 2 and toks[0].text == "thym" and toks[1].kind == "int"):
            raise _Fail("version", "the first line must be the version line, `thym 0`", i + 1)
        if toks[1].value != 0:
            raise _Fail("version", f"this compiler reads thym 0, and the file says thym {toks[1].value}", i + 1)
        version_line = i + 1
        i += 1
        uses: list[Use] = []
        blocks: list[Block] = []
        while i < self.n:
            if self.blank(i):
                i += 1
                continue
            fw = self.first_word(i)
            if fw == "use":
                mt = re.match(r"^\s*use\s+(\S+)\s*$", self.codes[i])
                if not mt:
                    raise _Fail("parse", "a use line names one URI or file: use oes:thym/house, use house.thym", i + 1)
                uses.append(Use(line=i + 1, uri=mt.group(1), text=self.raw[i]))
                i += 1
            elif fw in BLOCK_WORDS:
                b, i = self.block(i)
                blocks.append(b)
            else:
                raise _Fail("parse", f"expected a use line or a block (program, move, morph, context), found "
                            f"`{self.codes[i].strip()}`", i + 1)
        return Module(self.path, self.text, self.raw, self.lines, version_line, uses, blocks, self.warnings,
                      self.moves)

    # -- blocks ------------------------------------------------------------

    def block(self, i: int, parent: str | None = None) -> tuple[Block, int]:
        toks, j = self.logical(i)
        ts = _Stream(toks, i + 1)
        kind = ts.next().text
        name = ts.name(f"a {kind} block names itself: {kind} <name>").text
        b = Block(line=i + 1, kind=kind, name=name, parent=parent)
        if kind == "move":
            ts.expect_punct("(", f"a move declares its parameters: move {name}(<name>: <type>, …): <type>")
            if not ts.is_punct(")"):
                b.params.append(self.param(ts))
                while ts.is_punct(","):
                    ts.next()
                    b.params.append(self.param(ts))
            ts.expect_punct(")", "a move's parameters close with )")
            ts.expect_punct(":", f"a move declares what it gives: move {name}(…): <type>")
            b.gives = Param(line=i + 1, name=name, type=self.type_(ts))
        ts.end()
        i = j + 1
        i = self.heads(b, i)
        if kind == "program":
            while True:
                while i < self.n and self.blank(i):
                    i += 1
                if i < self.n and self.first_word(i) == "move":
                    mv, i = self.block(i, parent=name)
                    b.moves.append(mv)
                else:
                    break
            b.stmts, i = self.stmts(i, ("end",), b)
        elif kind == "move":
            b.stmts, i = self.stmts(i, ("end",), b)
        elif kind == "morph":
            i = self.lines_until_end(b, i, self.scale_line)
        else:
            i = self.lines_until_end(b, i, self.field_line)
        b.end = i + 1
        return b, i + 1

    def param(self, ts: _Stream) -> Param:
        t = ts.name("a parameter is <name>: <type>")
        ts.expect_punct(":", f"a parameter is <name>: <type>; `{t.text}` has no type")
        return Param(line=t.line, name=t.text, type=self.type_(ts))

    def type_(self, ts: _Stream) -> str:
        t = ts.peek()
        if t is None or t.kind != "name":
            raise _Fail("parse", "a type is expected here: text, fabula, short, atem, item, volume, …",
                        t.line if t else ts.last_line())
        if t.text == "list":
            ts.next()
            ts.expect_word("of", "a list type reads list of <type>")
            return ty.list_of(self.type_(ts))
        if t.text not in ty.SIMPLE:
            raise _Fail("parse", f"`{t.text}` is not a type; the types are {', '.join(ty.SIMPLE)} and list of <type>",
                        t.line)
        ts.next()
        return t.text

    def heads(self, b: Block, i: int) -> int:
        while i < self.n:
            if self.blank(i):
                i += 1
                continue
            fw = self.first_word(i)
            if fw in ("why", "must"):
                mt = re.match(r"^(why|must)\s*:(.*)$", _prose_text(self.lines[i]))
                if not mt:
                    raise _Fail("parse", f"a {fw} head reads {fw}: <prose>", i + 1)
                prose, i = self.prose(i, mt.group(2).strip(), b.kind)
                if fw == "why":
                    if b.why is not None:
                        raise _Fail("parse", f"{b.kind} {b.name} already has its why, at line {b.why.line}",
                                    prose.line)
                    b.why = prose
                else:
                    b.musts.append(prose)
            elif fw == "decided":
                mt = re.match(r"^decided\s+([0-9]{4}-[0-9]{2}-[0-9]{2})\s*:(.*)$", _prose_text(self.lines[i]))
                if not mt:
                    raise _Fail("parse", "a decided head reads decided <YYYY-MM-DD>: <prose>", i + 1)
                try:
                    date = _dt.date.fromisoformat(mt.group(1))
                except ValueError:
                    raise _Fail("parse", f"{mt.group(1)} is not a date", i + 1) from None
                prose, i = self.prose(i, mt.group(2).strip(), b.kind)
                b.decideds.append(Decided(line=prose.line, date=date, what=prose.text, end=prose.end))
            elif fw in ("takes", "gives"):
                if b.kind != "program":
                    raise _Fail("parse", f"{fw} is a program's head; a move's signature stands on its first line",
                                i + 1)
                toks, j = self.logical(i)
                ts = _Stream(toks, i + 1)
                ts.next()
                params = [self.param(ts)]
                while ts.is_punct(","):
                    ts.next()
                    params.append(self.param(ts))
                ts.end()
                if fw == "takes":
                    if b.takes:
                        raise _Fail("parse", f"program {b.name} has one takes line", i + 1)
                    b.takes = params
                else:
                    if b.gives is not None:
                        raise _Fail("parse", f"program {b.name} has one gives line", i + 1)
                    if len(params) != 1:
                        raise _Fail("parse", "gives names one output: gives <name>: <type>", i + 1)
                    b.gives = params[0]
                i = j + 1
            else:
                break
        return i

    def prose(self, i: int, first: str, kind: str = "program") -> tuple[Prose, int]:
        texts = [first] if first else []
        j = i + 1
        while j < self.n:
            t = _prose_text(self.lines[j])
            if not t:
                break
            mt = _FIRST_WORD.match(t)
            fw = mt.group(1) if mt else None
            if fw in HEAD_WORDS or fw == "end":
                break
            if fw in STATEMENT_WORDS or fw == "move" or (kind == "morph" and fw in ty.SCALES):
                self.warnings.append(ParseWarning(j + 1, f"a prose head holds a line that begins with `{fw}`; "
                                                         "a blank line probably belongs before it"))
            texts.append(t)
            j += 1
        return Prose(line=i + 1, text=" ".join(texts), end=j), j

    def lines_until_end(self, b: Block, i: int, one) -> int:
        while i < self.n:
            if self.blank(i):
                i += 1
                continue
            code = self.codes[i].strip()
            if self.first_word(i) == "end":
                if code != "end":
                    raise _Fail("parse", "`end` stands alone on its line", i + 1)
                return i
            one(b, i)
            i += 1
        raise _Fail("parse", f"{b.kind} {b.name} is never closed by end", b.line)

    def scale_line(self, b: Block, i: int) -> None:
        ts = _Stream(_tokens(self.codes[i], i + 1), i + 1)
        scale = ts.name("a morph line reads <scale> <1-5>").text
        t = ts.peek()
        if t is None or t.kind != "int":
            raise _Fail("parse", f"a morph line reads <scale> <1-5>; `{scale}` has no number", i + 1)
        ts.next()
        value = Lit(line=i + 1, kind="number", value=t.value)
        toward = None
        if ts.take_word("toward"):
            toward = ts.name("toward names a direction: toward casual, toward formal").text
        ts.end()
        b.scales.append(ScaleLine(line=i + 1, scale=scale, value=value, toward=toward))

    def field_line(self, b: Block, i: int) -> None:
        ts = _Stream(_tokens(self.codes[i], i + 1), i + 1)
        name = ts.name("a context line reads <field> <value>", field_ok=True).text
        if ts.peek() is None:
            raise _Fail("parse", f"a context line reads <field> <value>; `{name}` has no value", i + 1)
        value = self.primary(ts)
        ts.end()
        b.fields.append(FieldLine(line=i + 1, field=name, value=value))

    # -- statements --------------------------------------------------------

    def stmts(self, i: int, terminators: tuple[str, ...], b: Block) -> tuple[list[Stmt], int]:
        """Statements from line i up to a line whose first word is one of `terminators`; returns them and the
        index of that line."""
        out: list[Stmt] = []
        while i < self.n:
            if self.blank(i):
                i += 1
                continue
            fw = self.first_word(i)
            code = self.codes[i].strip()
            if fw in terminators:
                if code != fw:
                    raise _Fail("parse", f"`{fw}` stands alone on its line", i + 1)
                return out, i
            if fw in ("else", "end", "then"):
                raise _Fail("parse", f"`{fw}` without the if or for each it would close", i + 1)
            if fw == "move":
                if b.kind == "program":
                    raise _Fail("parse", "a local move stands before the program's statements", i + 1)
                raise _Fail("parse", "a move stands at the top of a file or at the start of a program", i + 1)
            if fw in HEAD_WORDS:
                raise _Fail("parse", f"`{fw}` is a head: heads stand at the top of a block, before its statements",
                            i + 1)
            if fw in ("program", "use"):
                raise _Fail("parse", f"`{fw}` stands at the top level; close {b.kind} {b.name} with end first", i + 1)
            st, i = self.stmt(i, b)
            out.append(st)
        raise _Fail("parse", f"{b.kind} {b.name} is never closed by end", b.line)

    def stmt(self, i: int, b: Block) -> tuple[Stmt, int]:
        toks, j = self.logical(i)
        ts = _Stream(toks, i + 1)
        line, text, comment = i + 1, self.source(i, j), self.first_comment(i, j)
        common = dict(line=line, text=text, comment=comment, end=j + 1, header_end=j + 1)
        first = ts.peek()
        word = first.text if first is not None and first.kind == "name" else None
        if word == "let":
            ts.next()
            name = ts.name("let names what it binds: let <name> = <expression>").text
            ts.expect_punct("=", f"let binds with =: let {name} = <expression>")
            expr = self.expr(ts)
            ts.end()
            return Let(name=name, expr=expr, **common), j + 1
        if word == "assert":
            ts.next()
            cond = self.cond(ts)
            message = None
            if ts.take_word("else"):
                t = ts.peek()
                if t is None or t.kind != "string":
                    raise _Fail("parse", 'assert … else takes a message in double quotes', line)
                ts.next()
                message = t.value
            ts.end()
            return Assert(cond=cond, message=message, **common), j + 1
        if word == "if":
            ts.next()
            cond = self.cond(ts)
            ts.expect_word("then", "an if line ends with then: if <condition> then")
            ts.end()
            then, k = self.stmts(j + 1, ("else", "end"), b)
            else_, else_line = None, None
            if self.first_word(k) == "else":
                else_line = k + 1
                else_, k = self.stmts(k + 1, ("end",), b)
            common["end"] = k + 1
            return If(cond=cond, then=then, else_=else_, else_line=else_line, **common), k + 1
        if word == "for":
            ts.next()
            ts.expect_word("each", "a loop reads for each <name> in <expression>")
            var = ts.name("a loop names its variable: for each <name> in <expression>").text
            ts.expect_word("in", f"a loop reads for each {var} in <expression>")
            coll = self.expr(ts, filter_ok=False)
            where = None
            if ts.take_word("where"):
                where = self.cond(ts)
            ts.end()
            body, k = self.stmts(j + 1, ("end",), b)
            common["end"] = k + 1
            return For(var=var, coll=coll, where=where, body=body, **common), k + 1
        if word == "emit":
            ts.next()
            slot = None
            t0, t1 = ts.peek(), ts.peek(1)
            if t0 is not None and t0.kind == "name" and t1 is not None and t1.kind == "punct" and t1.text == ":":
                slot = ts.name("a labelled emit names a field: emit <field>: <expression>", field_ok=True).text
                ts.next()
            expr = self.expr(ts)
            ts.end()
            return Emit(slot=slot, expr=expr, **common), j + 1
        if word == "give":
            ts.next()
            expr = self.expr(ts)
            ts.end()
            return Give(expr=expr, **common), j + 1
        if word == "withhold":
            head = ts.next()
            target = self.expr(ts, filter_ok=False)
            mods = []
            if isinstance(target, Call) and target.mod("where") is not None:
                where_mod = target.mod("where")
                target.mods.remove(where_mod)
                mods.append(where_mod)
            elif ts.is_word("where"):
                w = ts.next()
                mods.append(Mod(line=w.line, word="where", arg=self.cond(ts)))
            ts.end()
            call = Call(line=head.line, move="withhold", operands=[target], mods=mods)
            return Withhold(call=call, **common), j + 1
        expr = self.expr(ts)
        ts.end()
        return Effect(expr=expr, **common), j + 1

    # -- expressions -------------------------------------------------------

    def expr(self, ts: _Stream, filter_ok: bool = True) -> Expr:
        e = self.application(ts)
        if isinstance(e, (Call, Marked)):
            return e
        if filter_ok and ts.is_word("where"):
            w = ts.next()
            e = Filter(line=w.line, target=e, cond=self.cond(ts))
        if ts.is_word("marked"):
            w = ts.next()
            e = Marked(line=w.line, inner=e, word=self.bare_word(ts, "marked"))
        return e

    def application(self, ts: _Stream) -> Expr:
        t = ts.peek()
        if t is None:
            raise _Fail("parse", "an expression is expected here", ts.last_line())
        if t.kind == "name":
            if t.text in self.moves:
                return self.call(ts)
            if t.text not in KEYWORDS and NAME.match(t.text) and _operand_start(ts.peek(1)):
                return self.call(ts, known=False)
        return self.primary(ts)

    def call(self, ts: _Stream, known: bool = True) -> Expr:
        head = ts.next()
        c = Call(line=head.line, move=head.text, known=known)
        if _operand_start(ts.peek()):
            c.operands.append(self.operand(ts))
            while ts.is_punct(","):
                ts.next()
                c.operands.append(self.operand(ts))
        while True:
            t = ts.peek()
            if t is None or t.kind != "name" or t.text not in MODIFIER_WORDS:
                return c
            ts.next()
            w = t.text
            if w == "marked":
                return Marked(line=t.line, inner=c, word=self.bare_word(ts, "marked"))
            if c.mod(w) is not None:
                raise _Fail("parse", f"`{w}` comes once in a call of {c.move}", t.line)
            if w == "as":
                arg: Any = self.word_list(ts) if ts.is_punct("[") else Word(line=t.line, word=self.bare_word(ts, w))
            elif w == "by":
                arg = Word(line=t.line, word=self.bare_word(ts, w))
            elif w == "to":
                n = ts.peek()
                if n is None or n.kind != "int":
                    raise _Fail("parse", "to takes a number and a unit: to 300 words, to 12 sentences", t.line)
                ts.next()
                u = ts.peek()
                if u is None or u.kind != "name" or u.text not in ty.UNITS:
                    raise _Fail("parse", f"to {n.value} takes a unit: words or sentences", t.line)
                ts.next()
                arg = Units(line=t.line, count=n.value, unit=u.text)
            elif w == "where":
                arg = self.cond(ts)
            else:
                arg = self.mod_arg(ts)
            c.mods.append(Mod(line=t.line, word=w, arg=arg))

    def mod_arg(self, ts: _Stream) -> Expr:
        t = ts.peek()
        if t is not None and t.kind == "name" and t.text in self.moves:
            return self.call(ts)
        return self.primary(ts)

    def operand(self, ts: _Stream) -> Expr:
        t = ts.peek()
        if t is not None and t.kind == "name" and t.text in self.moves:
            raise _Fail("parse", f"a call as an operand goes in parentheses: ({t.text} …)", t.line)
        return self.primary(ts)

    def bare_word(self, ts: _Stream, after: str) -> str:
        t = ts.peek()
        if t is None or t.kind != "name" or not NAME.match(t.text) or t.text in KEYWORDS:
            raise _Fail("parse", f"{after} takes a bare word here", t.line if t else ts.last_line())
        ts.next()
        return t.text

    def word_list(self, ts: _Stream) -> ListLit:
        start = ts.expect_punct("[", "a list opens with [")
        items: list[Expr] = []
        if not ts.is_punct("]"):
            items.append(Word(line=start.line, word=self.bare_word(ts, "a list of words")))
            while ts.is_punct(","):
                ts.next()
                items.append(Word(line=start.line, word=self.bare_word(ts, "a list of words")))
        ts.expect_punct("]", "a list closes with ]")
        return ListLit(line=start.line, items=items)

    def primary(self, ts: _Stream) -> Expr:
        t = ts.peek()
        if t is None:
            raise _Fail("parse", "a value is expected here", ts.last_line())
        ts.next()
        e: Expr
        if t.kind == "name":
            if t.text in ("true", "false"):
                e = Lit(line=t.line, kind="bool", value=t.text == "true")
            elif t.text == "nothing":
                e = Lit(line=t.line, kind="nothing", value=None)
            elif t.text in KEYWORDS:
                raise _Fail("parse", f"`{t.text}` is a keyword, and a value is expected here", t.line)
            else:
                e = Name(line=t.line, name=t.text)
        elif t.kind == "int":
            e = Lit(line=t.line, kind="number", value=t.value)
        elif t.kind == "date":
            e = Lit(line=t.line, kind="date", value=t.value)
        elif t.kind == "string":
            e = Lit(line=t.line, kind="string", value=t.value)
        elif t.kind == "uri":
            e = Uri(line=t.line, uri=t.text)
        elif t.text == "(":
            inner = self.expr(ts)
            ts.expect_punct(")", "a parenthesis opened here is never closed")
            e = Paren(line=t.line, inner=inner)
        elif t.text == "[":
            items: list[Expr] = []
            if not ts.is_punct("]"):
                items.append(self.primary(ts))
                while ts.is_punct(","):
                    ts.next()
                    items.append(self.primary(ts))
            ts.expect_punct("]", "a list opened here is never closed")
            e = ListLit(line=t.line, items=items)
        else:
            raise _Fail("parse", f"a value is expected here, not `{t.text}`", t.line)
        while ts.is_punct("."):
            ts.next()
            f = ts.peek()
            if f is None or f.kind != "name" or not FIELD.match(f.text):
                raise _Fail("parse", "a field is read with a dot and its name: now.medium (version 0 has no floats)",
                            t.line)
            ts.next()
            e = FieldRead(line=f.line, target=e, field=f.text)
        return e

    # -- conditions --------------------------------------------------------

    def cond(self, ts: _Stream) -> Cond:
        left = self.cond_and(ts)
        while ts.is_word("or"):
            t = ts.next()
            left = Logic(line=t.line, op="or", left=left, right=self.cond_and(ts))
        return left

    def cond_and(self, ts: _Stream) -> Cond:
        left = self.term(ts)
        while ts.is_word("and"):
            t = ts.next()
            left = Logic(line=t.line, op="and", left=left, right=self.term(ts))
        return left

    def term(self, ts: _Stream) -> Cond:
        if ts.is_word("not"):
            t = ts.next()
            return Not(line=t.line, inner=self.term(ts))
        a = self.cond_primary(ts)
        t = ts.peek()
        if ts.is_word("is"):
            ts.next()
            op = "is not" if ts.take_word("not") else "is"
            return Compare(line=t.line, op=op, left=a, right=self.cond_primary(ts))
        if ts.is_word("in"):
            ts.next()
            return Compare(line=t.line, op="in", left=a, right=self.cond_primary(ts))
        if t is not None and t.kind == "punct" and t.text in "<>=":
            ts.next()
            return Compare(line=t.line, op=t.text, left=a, right=self.cond_primary(ts))
        if ts.is_word("has"):
            ts.next()
            f = ts.name("has names a field: x has <field>", field_ok=True)
            return Has(line=t.line, target=a, field=f.text)
        if ts.is_word("covers"):
            ts.next()
            return Covers(line=t.line, left=a, right=self.cond_primary(ts))
        return Truth(line=a.line, expr=a)

    def cond_primary(self, ts: _Stream) -> Expr:
        t = ts.peek()
        if t is not None and t.kind == "name" and t.text in self.moves and _operand_start(ts.peek(1)):
            raise _Fail("parse", f"a call inside a condition goes in parentheses: ({t.text} …)", t.line)
        return self.primary(ts)


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def _known_moves(text: str, path: str | None) -> frozenset[str]:
    """The move names a file can see before it is checked: the declared ones, its own `move` blocks, and the `move`
    blocks of the `.thym` files beside it that it `use`s."""
    from . import declarations
    found = set(declarations.names())
    found.update(_MOVE_LINE.findall(text))
    base = Path(path).parent if path else Path.cwd()
    for uri in _USE_LINE.findall(text):
        if uri.startswith("oes:") or not uri.endswith(".thym"):
            continue
        try:
            found.update(_MOVE_LINE.findall((base / uri).read_bytes().decode("utf-8", "replace")))
        except OSError:
            pass
    return frozenset(found)


def parse(text: str, *, path: str | None = None, moves: Iterable[str] | None = None) -> Module | Refusal:
    """A program's text as a `Module`, or the `Refusal` that says where it is not Thym 0. `path` is where the
    text was read from (for `use` of a file beside it, and for refusals); `moves` overrides the move names the
    parser reads calls with (by default every declared move, the file's own and its `use`d files')."""
    if not isinstance(text, str):
        return Refusal("compile", "parse", "a program is text", None, path)
    known = frozenset(moves) if moves is not None else _known_moves(text, path)
    try:
        return _Parser(text, path, known).run()
    except _Fail as f:
        return Refusal("compile", f.check, f.message, f.line, path)
    except RecursionError:
        return Refusal("compile", "parse", "the expression nests too deeply", None, path)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _string(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render(e: Any, subst: dict[int, str] | None = None) -> str:
    """An expression in canonical spacing; `subst` replaces nodes (by id) with names, as the plan's temporaries."""
    if subst and id(e) in subst:
        return subst[id(e)]
    if isinstance(e, Name):
        return e.name
    if isinstance(e, Word):
        return e.word
    if isinstance(e, Lit):
        if e.kind == "string":
            return _string(e.value)
        if e.kind == "bool":
            return "true" if e.value else "false"
        if e.kind == "nothing":
            return "nothing"
        if e.kind == "date":
            return e.value.isoformat()
        return str(e.value)
    if isinstance(e, ListLit):
        return "[" + ", ".join(render(x, subst) for x in e.items) + "]"
    if isinstance(e, Uri):
        return e.uri
    if isinstance(e, FieldRead):
        return f"{render(e.target, subst)}.{e.field}"
    if isinstance(e, Paren):
        if subst and id(e.inner) in subst:
            return subst[id(e.inner)]
        return f"({render(e.inner, subst)})"
    if isinstance(e, Units):
        return f"{e.count} {e.unit}"
    if isinstance(e, Call):
        out = e.move
        if e.operands:
            out += " " + ", ".join(render(o, subst) for o in e.operands)
        for m in e.mods:
            arg = render_cond(m.arg, subst) if isinstance(m.arg, Cond) else render(m.arg, subst)
            out += f" {m.word} {arg}"
        return out
    if isinstance(e, Filter):
        return f"{render(e.target, subst)} where {render_cond(e.cond, subst)}"
    if isinstance(e, Marked):
        return f"{render(e.inner, subst)} marked {e.word}"
    if isinstance(e, Cond):
        return render_cond(e, subst)
    return str(e)


def render_cond(c: Any, subst: dict[int, str] | None = None) -> str:
    if isinstance(c, Logic):
        return f"{render_cond(c.left, subst)} {c.op} {render_cond(c.right, subst)}"
    if isinstance(c, Not):
        return f"not {render_cond(c.inner, subst)}"
    if isinstance(c, Compare):
        return f"{render(c.left, subst)} {c.op} {render(c.right, subst)}"
    if isinstance(c, Has):
        return f"{render(c.target, subst)} has {c.field}"
    if isinstance(c, Covers):
        return f"{render(c.left, subst)} covers {render(c.right, subst)}"
    if isinstance(c, Truth):
        return render(c.expr, subst)
    return render(c, subst)


def statement_name(st: Stmt, lines: list[str]) -> str:
    """A statement as a name: its own lines without indentation and comments, joined by spaces."""
    a, b = st.line, (st.header_end or st.line)
    parts = [strip_comment(lines[k - 1])[0].strip() for k in range(a, b + 1)]
    return " ".join(p for p in parts if p)
