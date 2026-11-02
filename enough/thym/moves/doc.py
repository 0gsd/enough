"""The moves `doc/1` declares: `enumerate` and `compile` (docs/THYM.md 6.3, 10; MacroCOSM 18.5).

Both transcode, byte for byte (THYM.md 7.2, law 4).

- `enumerate` reads a text into a volume: a Thym program (a `.thym` file, or a text whose first line that is not blank
  or a comment is `thym 0`) through the compiler's own enumerator, into a `thym/1` program volume (THYM.md 10); any
  other markdown through DocOES (`ctx.engines["docoes"]`), into a `doc/1` volume. The move compiles the volume back
  before it gives it and refuses when the bytes differ. A doc volume records its markdown in `document:`; the move
  the `byte-exact` check reads the volume's `document` block (a doc/1 volume names its text there).
- `compile` gives a volume's text again: a program volume's file (`front`, then each block's body in order), or a doc
  volume's markdown, as told.

Standalone: the standard library, PyYAML and `enough.macrocosm` (and, in-package, the compiler).
"""
from __future__ import annotations

import re
from typing import Any

from enough import macrocosm as mc
from enough.thym import Refusal
from enough.thym.moves import MoveError, engine
from enough.thym.registry import implements
from enough.thym.values import Value, sha256_bytes

_VERSION = re.compile(r"^\s*thym\s+\d+\s*(?:--.*)?$")


def is_program(text: str, path: Any = None) -> bool:
    """A Thym program: a `.thym` file, or a text whose first line that is neither blank nor a comment is `thym 0`."""
    if path is not None and str(path).endswith(".thym"):
        return True
    for line in text.lstrip("﻿").replace("\r\n", "\n").split("\n"):
        s = line.strip()
        if not s or s.startswith("--"):
            continue
        return bool(_VERSION.match(s))
    return False


@implements("enumerate")
def enumerate_(ctx: Any, t: Value, **_: Any) -> Value:
    """A text enumerated into a volume: a program into `thym/1`, any other markdown into `doc/1` (THYM.md 6.3)."""
    raw = t.bytes()
    text = raw.decode("utf-8")
    name = t.path.name if t.path is not None else "text.md"
    if is_program(text, t.path):
        from enough.thym import check as ck
        from enough.thym import enumerate as en
        from enough.thym import parse as ps
        module = ps.parse(text, path=name)
        checked = module if isinstance(module, Refusal) else ck.check(module)
        if isinstance(checked, Refusal):
            raise MoveError(f"the program does not compile: {checked}")
        vol = en.enumerate_checked(checked, built_at=ctx.now)
        if en.compile_volume(vol).encode("utf-8") != raw:
            raise MoveError("the program's items do not compile back to its text byte for byte")
        return Value("volume", vol)
    docoes = engine(ctx, "docoes")
    vol = docoes.enumerate(text, path=name)
    if docoes.compile(vol).encode("utf-8") != raw:
        raise MoveError("the doc volume does not compile back to its markdown byte for byte")
    return Value("volume", vol)


@implements("compile")
def compile_(ctx: Any, v: Value, **_: Any) -> Value:
    """A volume's text again, byte for byte: a program volume's `.thym` file, or a doc volume's markdown."""
    data = v.mapping()
    if data is None:
        raise MoveError(f"a {v.type} is not a volume to compile")
    if data.get("oes") == "thym/1" and data.get("kind") == "program":
        from enough.thym import enumerate as en
        return Value("text", en.compile_volume(data))
    if str(data.get("oes") or (v.payload.oes if isinstance(v.payload, mc.Volume) else "")).startswith("doc/"):
        return Value("text", engine(ctx, "docoes").compile(v.payload))
    raise MoveError(f"compile gives back a program volume or a doc volume, not {data.get('oes') or v.type}")


#: The names the manifest's `code:` keys give (`enough.thym.moves.doc:enumerate`, `…:compile`).
enumerate = enumerate_  # noqa: A001 - the declared name; the builtin is not used in this module
compile = compile_  # noqa: A001

__all__ = ["compile", "compile_", "enumerate", "enumerate_", "is_program"]
