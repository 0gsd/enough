"""Thym: the MacroCOSM language, its compiler and its runtime (docs/THYM.md, version 0).

The package imports the standard library, PyYAML and `enough.macrocosm`, and nothing else of enough, so it is
vendorable as the reader is (THYM.md 11.2). enough's engines (`llm`, `preflight`, `canon_derive`, `docoes`) plug in
from outside, through `enough/thym_host.py`: the model coprocessor, the preflight hook and the state root.

Layout, by lane of the 0.5.0 round:

- the compiler (T1): `parse.py` (the grammar of THYM.md 4.8 by recursive descent; every node keeps its line and its
  source text), `declarations.py` (the moves every manifest's `moves:` block and every `*.moves.cosm` sidecar declare),
  `types.py`, `check.py` (resolve, types, the static contracts), `enumerate.py` (a `.thym` file into a `thym/1` program
  volume, and the file back byte for byte), `plan.py` (the plan volume), `contracts.py` (the static side of 7.3);
- the runtime (T2): `values.py`, `registry.py` (move implementations by name), `checks.py` (the dynamic checks of 7.3),
  `coprocessor.py` (the protocol; the refusing and replay coprocessors), `run.py`, `trace.py`, `conform.py`, `cli.py`,
  `__main__.py`;
- the moves (M1): `moves/` by owning MiniCOSM, as the manifests' `code:` keys name them;
- wave 2 (P1): `engines.py` (the call counter, and engine calls recorded and replayed, so a replay needs no engine)
  and `vault.py` (the encrypted package: Comprise's `comprise-bundle/0`, vendored).

A refusal is a value, never an exception (THYM.md 9): `Refusal` below is what every stage returns when it says no.
`check_file` compiles a `.thym` file through stages 1 to 4 of section 11.1 and `plan_file` plans it; the stages one
by one are `parse.parse`, `check.check`, `enumerate.enumerate_file` and `plan.plan`.
"""
from __future__ import annotations

from dataclasses import dataclass

FORMAT = "thym 0"                      # the version line every program starts with (THYM.md 4.1)
MINICOSM = "thym/1"                    # the MiniCOSM programs, morphs, contexts, plans, traces and packages are written in


@dataclass(frozen=True)
class Refusal:
    """A plain no, as a value: the stage (`compile`, `plan` or `run`), the check that failed (the names of THYM.md
    9 and 7.3), the message, and, when one is known, the line and the file."""
    stage: str
    check: str
    message: str
    line: int | None = None
    file: str | None = None

    def __str__(self) -> str:
        where = f"{self.file or '<program>'}:{self.line}" if self.line else (self.file or "<program>")
        return f"{where}: refused at {self.stage} ({self.check}): {self.message}"


def _read(path) -> "tuple[str | None, Refusal | None]":
    from pathlib import Path
    p = Path(path)
    try:
        return p.read_bytes().decode("utf-8"), None
    except OSError as e:
        return None, Refusal("compile", "unknown-uri", f"{p.name} cannot be read: {e.strerror or e}", None, str(p))
    except UnicodeDecodeError:
        return None, Refusal("compile", "parse", f"{p.name} is not UTF-8", None, str(p))


def check_file(path, *, decls: dict | None = None, volumes=None):
    """Compile a `.thym` file through parse, resolve, types and the static contracts: a `check.Checked`, or the
    `Refusal` that names the line (THYM.md 11.1, stages 1 to 4). `volumes` answers a `use oes:…`."""
    from . import check, parse
    text, refused = _read(path)
    if refused is not None:
        return refused
    module = parse.parse(text, path=str(path))
    if isinstance(module, Refusal):
        return module
    return check.check(module, decls=decls, volumes=volumes)


def plan_file(path, inputs: list[dict], *, decls: dict | None = None, volumes=None):
    """Compile a `.thym` file and plan it over its inputs, `[{name, type, path, sha256}]`: the plan volume mapping,
    or the `Refusal` (THYM.md 11.1, stage 7)."""
    from . import plan
    checked = check_file(path, decls=decls, volumes=volumes)
    if isinstance(checked, Refusal):
        return checked
    return plan.plan(checked, inputs)


__all__ = ["FORMAT", "MINICOSM", "Refusal", "check_file", "plan_file"]
