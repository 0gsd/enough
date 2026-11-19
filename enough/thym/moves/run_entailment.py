"""Running an authored fabulac's entailment (Thym 6.3's `run` row, 7.3, 20.12; MacroCOSM OES 18.4.7, the run rule),
seen by `thym 1` programs only.

`run code as tests` runs the entailment's tests (`tests/`, with the standard library's `unittest`); `run code as tool
with ["count", "notes.md"]` starts a `tool` by its `program.start` with those arguments and an empty standard input;
`run code as service` is specified and refused in this edition, in the host's words (serving comes in a later one).
Each gives a **report** (`REPORT_KEYS`, in this order):

| key | holds |
|---|---|
| `as` | `tests` or `tool` |
| `folder` | the folder run, as the program names it |
| `fabulac` | the authored fabulac beside it whose entailment it is (`tally.fabulac.cosm`) |
| `arguments` | the tool's arguments (as tool only) |
| `exit` | the exit status, or nothing when the run was stopped before it gave one |
| `output`, `error-output` | each stream, cut at the host's limit |
| `cut` | the streams the host cut at its limit (`output`, `error-output`), or none |
| `tests` | as tests: each test and its verdict (`passed`, `failed`, `error`, `skipped`, `expected failure`, `unexpected success`) |
| `stopped` | nothing, or `{by, said}`: what stopped it (`time`, `cpu`, `output`, `disk`, `request`) and the host's sentence |
| `refused` | what the box refused while it ran, as sentences |
| `sandbox` | `{by, rows}`: the host's box, and each row of 20.12's table (`ROWS`) with `enforced` and `said`, and `unenforced` where a row holds only in part (memory, on macOS) |
| `milliseconds` | how long it ran |

A test that fails is in the report, and the run still lands: the report is what the cases judged.

**Thym runs nothing itself.** The move asks the host through the engine `sandbox` (`enough/thym_sandbox.py`
registers it), two calls, each recorded as every engine call is (Thym 12.4; `enough/thym/engines.py`):
`sandbox.beside(code)`, what the fabulac beside the folder says (its `source.kind`, `program`, `entailed`), and
`sandbox.run(code, as, arguments)`, the host's answer: `{report: …}`, or `{refused: <sentence>, reason}` when the host
will not run it (no box on this system, a package outside the standard library, a service). A replay answers both from
the record and runs nothing; a runtime with no sandbox replays a recorded run all the same. A host with no `sandbox`
engine refuses at run time, as for an absent engine.

**The checks.** `only-authored` is held before anything runs (the move refuses with that check's name, never asking the
host to run it) and again of the report: the folder is an entailment (`ENTAILED.md`, no `CSHORT.md`), the fabulac of
the same name beside it says `source: {kind: authored, …}`, its `entailed.path` is this folder, and every file it
records is in the folder. A cshort, a decompiled fabulac's folder and any other code are read, never run.
`in-sandbox` holds of the report: the host named its box, the box held (`own-place`, `no-network` and `packages`
enforced), and every row of the table is there with whether it was enforced and the host's words.

This module imports only Thym: the runner is the host's, so that a runtime that vendors Thym inherits no runner.
"""
from __future__ import annotations

from typing import Any

from enough.thym.checks import check
from enough.thym.folder import Folder
from enough.thym.moves import MoveError
from enough.thym.registry import implements
from enough.thym.values import Value, plain

AS_WORDS = ("tests", "tool", "service")
ENGINE = "sandbox"
AUTHORED = "authored"
FABULAC_SUFFIX = ".fabulac.cosm"
ENTAILED = "ENTAILED.md"
CSHORT = "CSHORT.md"
#: The rows of Thym 20.12's table (MacroCOSM OES 18.4.7's sandbox), as the report names them.
ROWS = ("own-place", "no-network", "limits", "stop", "packages", "serving")
#: The rows a run cannot do without: when the box did not hold these, nothing was kept apart.
HELD_ROWS = ("own-place", "no-network", "packages")
REPORT_KEYS = ("as", "folder", "fabulac", "arguments", "exit", "output", "error-output", "cut", "tests", "stopped",
               "refused", "sandbox", "milliseconds")
VERDICTS = ("passed", "failed", "error", "skipped", "expected failure", "unexpected success")
NO_SANDBOX = ("this host has no sandbox, so it runs nothing: run asks the host's sandbox, and Thym runs nothing "
              "itself (Thym 20.12)")
READ_NEVER_RUN = "it is read, never run (MacroCOSM OES 18.4.7)"


class Refused(MoveError):
    """`run` refused by one of its checks' names (`only-authored`, `in-sandbox`): the runtime refuses the run with that
    check (`enough.thym.run`, a MoveError's `check`)."""

    def __init__(self, check_name: str, message: str) -> None:
        super().__init__(message)
        self.check = check_name


# ---------------------------------------------------------------------------
# only-authored, by rules over what the fabulac beside the folder says
# ---------------------------------------------------------------------------

def _folder_name(f: Folder) -> str:
    return f.name.rstrip("/")


def only_authored_problem(f: Folder | None, beside: Any) -> str | None:
    """Why the folder is not the entailment of an authored fabulac (Thym 7.3 `only-authored`), or None when it is.
    `beside` is the host's answer to `sandbox.beside`: `{found, fabulac, why, source: {kind}, entailed: {path,
    files: [{path, sha256}]}}`."""
    if not isinstance(f, Folder):
        return "run takes a folder: an authored fabulac's entailment"
    name = _folder_name(f)
    if f.entry(CSHORT) is not None:
        return f"{name} is a cshort, the code of a fabulac decompiled from a folder: {READ_NEVER_RUN}"
    b = beside if isinstance(beside, dict) else {}
    fab = str(b.get("fabulac") or f"{name}{FABULAC_SUFFIX}")
    if not b.get("found"):
        why = f" ({b['why']})" if b.get("why") else ""
        return (f"there is no {fab} beside {name}{why}: only the entailment of a fabulac its person authored is run, "
                f"and any other code {READ_NEVER_RUN}")
    src = b.get("source") if isinstance(b.get("source"), dict) else {}
    if src.get("kind") != AUTHORED:
        kind = src.get("kind") or "none"
        return (f"{fab} was not authored (its source.kind is {kind}): {name} is the folder a fabulac was decompiled "
                f"from, and {READ_NEVER_RUN}")
    ent = b.get("entailed") if isinstance(b.get("entailed"), dict) else {}
    if not ent:
        return f"{fab} records no entailment: entail it first, and run the folder its entailed names"
    want = str(ent.get("path") or "").rstrip("/")
    if want != name:
        return f"{fab} records its entailment as {want}/, not {name}/: only the folder its entailed names is run"
    if f.entry(ENTAILED) is None:
        return f"{name} holds no {ENTAILED}: it is not the entailment {fab} records"
    missing = [str(r.get("path")) for r in ent.get("files") or [] if isinstance(r, dict)
               and f.entry(str(r.get("path"))) is None]
    if missing:
        return f"{name} lacks {', '.join(missing[:5])}, which {fab}'s entailed records: entail it again"
    return None


# ---------------------------------------------------------------------------
# The move
# ---------------------------------------------------------------------------

def _as_word(x: Any) -> str | None:
    if isinstance(x, (list, tuple)):
        x = x[0] if len(x) == 1 else None
    return x if isinstance(x, str) else None


def _arguments(x: Any) -> list[str]:
    if x is None:
        return []
    got = plain(x)
    if isinstance(got, str):
        got = [got]
    if not isinstance(got, list) or not all(isinstance(a, (str, int)) and not isinstance(a, bool) for a in got):
        raise MoveError("run … with gives the tool's arguments: a list of strings")
    return [str(a) for a in got]


def _sandbox(ctx: Any) -> Any:
    engines = getattr(ctx, "engines", None) or {}
    try:
        got = engines[ENGINE] if ENGINE in engines else None
    except KeyError:
        got = None
    if got is None:
        raise Refused("in-sandbox", NO_SANDBOX)
    return got


@implements("run")
def run(ctx: Any, code: Value, **mods: Any) -> Value:
    """`run code as tests | tool | service [with arguments]`: the host's report of a run of an authored fabulac's
    entailment in its sandbox (Thym 20.12)."""
    word = _as_word(mods.get("as"))
    if word not in AS_WORDS:
        raise MoveError("run says how it runs the entailment: as tests, as tool or as service")
    args = _arguments(mods.get("with"))
    if word != "tool" and args:
        raise MoveError(f"run … as {word} takes no arguments: with gives a tool's arguments")
    f = code.payload if isinstance(code, Value) else None
    if not isinstance(f, Folder):
        raise Refused("only-authored", "run takes a folder: an authored fabulac's entailment")
    sb = _sandbox(ctx)
    beside = sb.beside(code)
    why = only_authored_problem(f, beside)
    if why:
        raise Refused("only-authored", f"run refused: {why}")
    answer = sb.run(code, word, args)
    if not isinstance(answer, dict):
        raise Refused("in-sandbox", "the host's sandbox gave no report")
    if answer.get("refused"):
        raise Refused("in-sandbox", f"the host will not run {_folder_name(f)}: {answer['refused']}")
    got = answer.get("report")
    if not isinstance(got, dict):
        raise Refused("in-sandbox", "the host's sandbox gave no report")
    fab = str((beside or {}).get("fabulac") or f"{_folder_name(f)}{FABULAC_SUFFIX}")
    head = {"as": word, "folder": f"{_folder_name(f)}/", "fabulac": fab}
    if word == "tool":
        head["arguments"] = args
    report = {**head, **{k: plain(got[k]) for k in REPORT_KEYS if k in got and k not in head}}
    return Value("report", report, origin={"run": {"beside": plain(beside)}})


# ---------------------------------------------------------------------------
# The checks (Thym 7.3)
# ---------------------------------------------------------------------------

def _folder_input(inputs: dict) -> Folder | None:
    for v in (inputs or {}).values():
        p = v.payload if isinstance(v, Value) else None
        if isinstance(p, Folder):
            return p
    return None


@check("only-authored")
def _only_authored(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """The folder run is the entailment of an authored fabulac, as the fabulac beside it records (the move refuses
    before anything runs; this holds the report it gave to the same rule)."""
    beside = ((output.origin or {}).get("run") or {}).get("beside") if isinstance(output, Value) else None
    if beside is None:
        return False, "the report does not say which fabulac's entailment was run"
    why = only_authored_problem(_folder_input(inputs), beside)
    return (False, why) if why else (True, "")


def in_sandbox_problem(report: Any) -> str | None:
    """Why a report does not show a run in a sandbox that holds to 20.12's table, or None."""
    if not isinstance(report, dict):
        return "the run gave no report"
    sb = report.get("sandbox")
    if not isinstance(sb, dict) or not sb.get("by"):
        return "the report does not name the host's sandbox"
    rows = sb.get("rows")
    if not isinstance(rows, dict):
        return "the report does not say which rows of the sandbox the host enforced"
    for r in ROWS:
        row = rows.get(r)
        if not isinstance(row, dict) or not isinstance(row.get("enforced"), bool) or not str(row.get("said") or ""):
            return f"the report does not say whether the host enforced {r}, in its words"
    weak = [r for r in HELD_ROWS if rows[r]["enforced"] is not True]
    if weak:
        return f"the box did not hold this run ({', '.join(weak)}): {rows[weak[0]]['said']}"
    return None


@check("in-sandbox")
def _in_sandbox(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """The host ran the folder in a sandbox that holds to every row of MacroCOSM OES 18.4.7, and the report says which
    rows it enforced and which it could not (memory, on some systems)."""
    why = in_sandbox_problem(output.payload if isinstance(output, Value) else None)
    return (False, why) if why else (True, "")


__all__ = ["AS_WORDS", "ENGINE", "HELD_ROWS", "REPORT_KEYS", "ROWS", "Refused", "VERDICTS", "in_sandbox_problem",
           "only_authored_problem", "run"]
