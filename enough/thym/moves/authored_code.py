"""An authored fabulac entailed as the program its person can start (MacroCOSM OES 18.4.1 `entailed`, 18.4.7,
18.4.8; Thym 20.7's second program `entail-authored-python`, 7.3), seen by `thym 1` programs only.

`entail f as code` of a fabulac whose `source.kind` is `authored` lands here (`code.entail_branch`'s one dispatch
line); a cshort of code the person did not author is `code.entail_code`'s, unchanged. What it gives is the
entailment, the folder of the fabulac's name beside it (`tally/` beside `tally.fabulac.cosm`):

| file | written by | holds |
|---|---|---|
| the sources | a model, file by file (the `code` step, as a cshort's) | the program, from the fabulac alone |
| `tests/test_cases.py` | rules (`tests_text`) | one `unittest` test per runnable case |
| `tests/test_prose_cases.py` | a model (the `test` step), only when a case is prose | a test per prose case, marked |
| `tests/__init__.py` | rules | the tests' package mark, so `unittest discover -s tests -t .` finds them |
| `pyproject.toml` | rules (`pyproject_text`) | name, version, Python floor, scripts, pinned needs, `[tool.enough]` |
| `RUNNING.md` | rules (`running_text`) | how to test, how to start, what it needs, what enough will and will not run |
| `ENTAILED.md` | rules (`entailed_text`) | the footer; path, from, sha256, brief per file; what was not; licence |

**One notion of a case** (MacroCOSM OES 18.4.7, "Cases as the judge"; the same fields transconception's outside cases
use, `enough/transconception.py` `case_from_item`): a `P:case` is runnable when its `given` and `expect` are data for
one of two surfaces. A command: `given: {files, env, cwd, steps: [{arguments, input}]}`, `expect: {steps: [{exit,
output, error-output}], files}`; `<CASE>` in an argument or a variable is the case's own folder, as the harness has
it. A function: `given: {calls: <C:interface id>, arguments: {<parameter>: <value>}}`, `expect: {value}` or `expect:
{raises: {error, message}}`. A case in words stays valid: it is prose, and a model step writes its test, marked so. A
case whose `given` or `expect` is still a question, or is data no surface knows, is named in `ENTAILED.md` with why.

**Tests by rules, never by the model that writes the code.** `tests/test_cases.py` is written from the cases alone:
a command case runs the entailed program's `start` through `subprocess`, with this interpreter and the flags it runs
under (the sandbox's `-I -S -X utf8 -B`), in a temporary folder of its own; a function case imports the module and
calls the interface by keyword. The file holds the cases as data; its bytes follow from the fabulac alone.

**The checks.** `cases-entailed` (here: every runnable case is a test in `tests/test_cases.py` exactly as rules write
it; every prose case a test marked as a model's or named with its reason; of a cshort, nothing to check), and the
entailment's readings of `files-present`, `interfaces-present` and `footer` against `ENTAILED.md` (here, reached from
`code.py`'s checks by one dispatch line each). `requirement-cased` is the fabula's own (`enough/fabula.py`), by
`author.uncovered_items`.

**The brief digest** (MacroCOSM OES 18.4.1 `entailed.files[].brief`): the sha256 of the items a file was entailed
from, each dumped as Thym dumps a value for its digest (Thym 12.6, `values.canonical`) with its `provenance` left out,
joined in the order `from` gives; for a file rules wrote, of the inputs the rules read. `brief_digest` is the one
function; keeping in step (W3-F5) reads it again.

This module imports only Thym and the reader.
"""
from __future__ import annotations

import ast
import hashlib
import re
import textwrap
from typing import Any

from enough import macrocosm as mc
from enough.thym.checks import check
from enough.thym.folder import Folder, path_key
from enough.thym.moves import MoveError, engine, fold, item_kind, utc_day
from enough.thym.moves import code as _code
from enough.thym.values import Value, canonical, plain

AUTHORED = "authored"
SURFACES = ("command", "function")
#: The fields of each surface's `given` and `expect` (MacroCOSM OES 18.4.7's table; `cwd` as the harness reads it).
COMMAND_GIVEN = ("files", "env", "cwd", "steps")
COMMAND_STEP = ("arguments", "input")
COMMAND_EXPECT = ("steps", "files")
COMMAND_EXPECT_STEP = ("exit", "output", "error-output")
FUNCTION_GIVEN = ("calls", "arguments")
FUNCTION_EXPECT = ("value", "raises")
RAISES = ("error", "message")
#: The harness's word for a case's own folder (tools/transconception/harness.py `CASE_TOKEN`).
CASE_TOKEN = "<CASE>"
TESTS = "tests/test_cases.py"
PROSE_TESTS = "tests/test_prose_cases.py"
TESTS_INIT = "tests/__init__.py"
PYPROJECT = "pyproject.toml"
RUNNING = "RUNNING.md"
ENTAILED = "ENTAILED.md"
RULES_FILES = (RUNNING, PYPROJECT, TESTS_INIT, TESTS)
#: The version an entailment says when the fabulac records no `R:release` with one.
NO_VERSION = "0.0.0"
#: A step's limit in the tests rules write: a case that hangs fails, it does not wait for the box's clock.
STEP_SECONDS = 60
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PACKAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_ENTAILED_FOOT = re.compile(r"^\*an entailment of (?P<f>\S.*?), in (?P<lang>[A-Za-z][\w+ #-]*), entailed on "
                            r"(?P<day>\d{4}-\d{2}-\d{2}) by (?P<who>.+)\*$")
_ROW = re.compile(r"^\| (?P<path>[^|]+?) \| (?P<from>[^|]+?) \| (?P<sha>[0-9a-f]{64}) \| (?P<brief>[0-9a-f]{64}) \|$")
SERVING_LATER = ("{name} is a service. enough authors and entails services, but serving comes in a later minor: "
                 "enough cannot serve it here yet.")


# ---------------------------------------------------------------------------
# What an authored fabulac is, and its program
# ---------------------------------------------------------------------------

def is_authored(cat: Any) -> bool:
    src = cat.get("source") if isinstance(cat, dict) else None
    return isinstance(src, dict) and src.get("kind") == AUTHORED


def is_authored_fabula(v: Any) -> bool:
    """Whether a value is an authored fabulac (what `entail … as code` hands this module)."""
    if not isinstance(v, Value) or v.type != "fabula":
        return False
    try:
        cat, _ = _code._fabula(v, "")
    except MoveError:
        return False
    return is_authored(cat)


def is_entailment(f: Any) -> bool:
    """Whether a folder value is an authored fabulac's entailment: it holds `ENTAILED.md`, not `CSHORT.md`."""
    return isinstance(f, Folder) and f.entry(ENTAILED) is not None and f.entry("CSHORT.md") is None


def program_of(cat: dict) -> dict:
    p = cat.get("program") if isinstance(cat.get("program"), dict) else {}
    return {k: plain(v) for k, v in p.items()}


def folder_name(cat: dict, fab: Value | None) -> str:
    """The entailment's folder, the fabulac's file name without `.fabulac.cosm` (`tally` for `tally.fabulac.cosm`)."""
    return _code.fabulac_file(cat, fab).rsplit(".fabulac.cosm", 1)[0] if fab is not None else str(cat.get("name"))


def main_module(cat: dict) -> str:
    """The program's top module: `start`'s `-m <module>` (its first part), else the name respelled as a module."""
    start = program_of(cat).get("start")
    if isinstance(start, list) and len(start) >= 2 and start[0] == "-m" and isinstance(start[1], str):
        return start[1].split(".")[0]
    s = re.sub(r"[^a-z0-9_]+", "_", str(cat.get("name") or "program").lower()).strip("_") or "program"
    return f"_{s}" if s[0].isdigit() else s


def _items_of(items: list[dict], kind: str) -> list[dict]:
    return [x for x in items if item_kind(x) == kind]


# ---------------------------------------------------------------------------
# One notion of a case
# ---------------------------------------------------------------------------

def _is_plain(v: Any) -> bool:
    """Data a test can hold as a literal: text, numbers, yes or no, nothing, lists and mappings keyed by text."""
    if v is None or isinstance(v, (str, bool, int, float)):
        return True
    if isinstance(v, list):
        return all(_is_plain(x) for x in v)
    if isinstance(v, dict):
        return all(isinstance(k, str) and _is_plain(x) for k, x in v.items())
    return False


def _strings(v: Any, nullable: bool = False) -> bool:
    return isinstance(v, dict) and all(isinstance(k, str) and (isinstance(x, str) or (nullable and x is None))
                                       for k, x in v.items())


def given_surface(given: Any) -> tuple[str | None, str]:
    """`(surface, why)` of a case's `given`: `command` or `function` for data in that shape, `prose` for words, None
    with why for anything else (a question still open, data no surface knows)."""
    if mc.is_pending(given):
        return None, "its given is still a question"
    if isinstance(given, str):
        return ("prose", "") if given.strip() else (None, "its given is empty")
    if not isinstance(given, dict) or not given:
        return None, "its given is neither words nor data"
    if "calls" in given:
        extra = sorted(set(given) - set(FUNCTION_GIVEN))
        if extra:
            return None, f"a function's given holds calls and arguments, not {', '.join(extra)}"
        if not (isinstance(given["calls"], str) and given["calls"].startswith("C:interface/")):
            return None, "given.calls names the interface it calls, by its id (C:interface/…)"
        args = given.get("arguments", {})
        if not (isinstance(args, dict) and all(isinstance(k, str) and _IDENT.match(k) for k in args)):
            return None, "given.arguments maps each parameter's name to its value"
        if not _is_plain(args):
            return None, "given.arguments holds only text, numbers, yes or no, nothing, lists and mappings"
        return "function", ""
    extra = sorted(set(given) - set(COMMAND_GIVEN))
    if extra:
        return None, f"no surface's given holds {', '.join(extra)} (a command's: {', '.join(COMMAND_GIVEN)})"
    steps = given.get("steps")
    if not (isinstance(steps, list) and steps and all(isinstance(s, dict) for s in steps)):
        return None, "a command's given.steps is a list of steps, each {arguments, input}"
    for i, s in enumerate(steps):
        if set(s) - set(COMMAND_STEP):
            return None, f"given.steps[{i}] holds {', '.join(sorted(set(s) - set(COMMAND_STEP)))}"
        a = s.get("arguments", [])
        if not (isinstance(a, list) and all(isinstance(x, str) for x in a)):
            return None, f"given.steps[{i}].arguments is a list of words"
        if s.get("input") is not None and not isinstance(s.get("input"), str):
            return None, f"given.steps[{i}].input is text"
    if "files" in given and not _strings(given["files"]):
        return None, "given.files maps each path to the text it starts with"
    if "env" in given and not _strings(given["env"], nullable=True):
        return None, "given.env maps each variable to its value (or nothing, to unset it)"
    if "cwd" in given and not (isinstance(given["cwd"], str) and not given["cwd"].startswith("/")
                               and ".." not in given["cwd"].split("/")):
        return None, "given.cwd is a folder inside the case's own"
    for p in (given.get("files") or {}):
        if p.startswith("/") or ".." in p.split("/"):
            return None, f"given.files names {p}, outside the case's own folder"
    return "command", ""


def expect_problem(expect: Any, surface: str, given: dict) -> str:
    """Why a case's `expect` is not data for its surface; empty when it is."""
    if mc.is_pending(expect):
        return "its expect is still a question"
    if not isinstance(expect, dict) or not expect:
        return f"a {surface} case's expect is data"
    if surface == "function":
        extra = sorted(set(expect) - set(FUNCTION_EXPECT))
        if extra or ("value" in expect) == ("raises" in expect):
            return "a function's expect is {value} or {raises: {error, message}}"
        if "value" in expect and not _is_plain(expect["value"]):
            return "expect.value holds only text, numbers, yes or no, nothing, lists and mappings"
        r = expect.get("raises")
        if "raises" in expect and not (isinstance(r, dict) and isinstance(r.get("error"), str) and _IDENT.match(
                r["error"]) and not set(r) - set(RAISES) and isinstance(r.get("message", ""), str)):
            return "expect.raises is {error, message}: the error's class name, and the message it carries"
        return ""
    extra = sorted(set(expect) - set(COMMAND_EXPECT))
    if extra:
        return f"a command's expect holds steps and files, not {', '.join(extra)}"
    steps = expect.get("steps")
    if not (isinstance(steps, list) and len(steps) == len(given.get("steps") or [])):
        return "a command's expect.steps has one {exit, output, error-output} per given step"
    for i, s in enumerate(steps):
        if not (isinstance(s, dict) and "exit" in s and isinstance(s["exit"], int) and not isinstance(s["exit"], bool)):
            return f"expect.steps[{i}] says its exit status, a whole number"
        if set(s) - set(COMMAND_EXPECT_STEP):
            return f"expect.steps[{i}] holds {', '.join(sorted(set(s) - set(COMMAND_EXPECT_STEP)))}"
        if any(k in s and not isinstance(s[k], str) for k in ("output", "error-output")):
            return f"expect.steps[{i}]'s output and error-output are text"
    if "files" in expect and not _strings(expect["files"], nullable=True):
        return "expect.files maps each path to the text it holds after (or nothing: it is not there)"
    return ""


def case_surface(item: dict) -> tuple[str | None, str]:
    """`(surface, why)` of a `P:case`: `command` or `function` when runnable, `prose` when a model writes its test,
    None with why when it cannot be entailed (MacroCOSM OES 18.4.7)."""
    given, expect = item.get("given"), item.get("expect")
    if mc.is_pending(given) or mc.is_pending(expect):
        return None, ("its given is still a question" if mc.is_pending(given) else "its expect is still a question")
    surface, why = given_surface(given)
    if surface is None:
        return None, why
    if surface == "prose" or isinstance(expect, str):
        if isinstance(expect, str) and not expect.strip():
            return None, "its expect is empty"
        return "prose", ""
    why = expect_problem(expect, surface, given)
    return (None, why) if why else (surface, "")


def answer_shape(part: str, value: Any) -> str:
    """Why an answer to a case's `given` or `expect` is not one, empty when it is: words (a prose case) or data for a
    surface. The dialectic's answer kinds `given` and `expect` read it (MacroCOSM OES 18.6.4)."""
    if isinstance(value, str):
        return "" if value.strip() else "an empty answer"
    if part == "given":
        surface, why = given_surface(value)
        return "" if surface else why
    if not isinstance(value, dict) or not value:
        return "what is expected is words, or data: {steps, files} for a command, {value} or {raises} for a function"
    if set(value) <= set(FUNCTION_EXPECT):
        return expect_problem(value, "function", {})
    if set(value) <= set(COMMAND_EXPECT):
        steps = value.get("steps")
        return expect_problem(value, "command", {"steps": list(steps) if isinstance(steps, list) else []})
    return "what is expected is {steps, files} for a command, {value} or {raises} for a function"


# ---------------------------------------------------------------------------
# Where each interface lives: the sources rules plan, and a model writes
# ---------------------------------------------------------------------------

def _signature_params(sig: Any, attr: str) -> list[str] | None:
    """The parameter names a `signature` says (`count(path, words=False) -> int`), by syntax; None when unread."""
    if not isinstance(sig, str) or "(" not in sig:
        return None
    s = sig.strip().rstrip(":")
    head = s.split("(", 1)[0].strip().split(".")[-1].split()[-1:] or [attr]
    try:
        tree = ast.parse(f"def {head[0] if _IDENT.match(head[0]) else attr}({s.split('(', 1)[1]}: pass")
    except SyntaxError:
        return None
    fn = tree.body[0]
    a = fn.args
    names = [x.arg for x in a.posonlyargs + a.args]
    if a.vararg:
        names.append(a.vararg.arg)
    names += [x.arg for x in a.kwonlyargs]
    if a.kwarg:
        names.append(a.kwarg.arg)
    return names


def interface_place(it: dict, items: list[dict], main: str) -> tuple[str, str] | None:
    """`(module, attribute)` of a function interface: the file it is `defined-in`, else its dotted name under the
    program's package (`tally.count` → `tally`, `count`; `counting.count` → `tally.counting`), else the package."""
    raw = str(it.get("name") or "").split("(", 1)[0].strip()
    by = _code._by_id(items)
    fi = by.get(str(it.get("defined-in"))) if it.get("defined-in") else None
    if fi and isinstance(fi.get("path"), str) and fi["path"].endswith(".py"):
        p = fi["path"][:-3]
        mod = ".".join(x for x in p.split("/") if x and x != "__init__")
        attr = raw.split(".")[-1]
        return (mod, attr) if _IDENT.match(attr) and mod else None
    parts = raw.split(".")
    if not parts or not all(_IDENT.match(x) for x in parts):
        return None
    if len(parts) == 1:
        return main, parts[0]
    mod = ".".join(parts[:-1])
    if parts[0] != main:
        mod = f"{main}.{mod}"
    return mod, parts[-1]


def module_path(mod: str, main: str) -> str:
    return f"{main}/__init__.py" if mod == main else mod.replace(".", "/") + ".py"


def command_path(cat: dict) -> str | None:
    """The file a tool's or a service's command line lives in: `<module>/__main__.py` for `-m <module>`, the file
    `start` names, or None (a library)."""
    prog = program_of(cat)
    start = prog.get("start")
    if prog.get("kind") not in ("tool", "service") or not isinstance(start, list) or not start:
        return None
    if start[0] == "-m" and len(start) >= 2:
        return start[1].replace(".", "/") + "/__main__.py"
    return str(start[0]) if str(start[0]).endswith(".py") else None


def plan_sources(cat: dict, items: list[dict]) -> list[dict]:
    """The sources a model writes, by rules: `[{path, module, role, interfaces}]`. The fabulac's own Python `C:file`s
    when it names any; else the program's package (`<module>/__init__.py`), a module per dotted function interface,
    and for a tool or a service the command line, `<module>/__main__.py`."""
    main = main_module(cat)
    files = [x for x in _items_of(items, "file") if str(x.get("path", "")).endswith(".py")
             and not _code.is_test(str(x.get("path")))]
    plan: dict[str, dict] = {}

    def add(path: str, module: str, role: str) -> dict:
        return plan.setdefault(path, {"path": path, "module": module, "role": role, "interfaces": []})

    for x in files:
        p = str(x["path"])
        add(p, ".".join(y for y in p[:-3].split("/") if y and y != "__init__"), "a module the fabulac names")
    add(module_path(main, main), main, "the program's package")
    cmd = command_path(cat)
    if cmd is not None:
        add(cmd, cmd[:-3].replace("/", "."), "the command line")
    for it in _items_of(items, "interface"):
        surface = it.get("surface")
        if surface == "command" and cmd is not None:
            plan[cmd]["interfaces"].append(it["id"])
            continue
        if surface in ("function", "class", "method"):
            place = interface_place(it, items, main)
            if place is None:
                continue
            path = module_path(place[0], main)
            add(path, place[0], "a module of the package")["interfaces"].append(it["id"])
    for p in list(plan):                       # every package a module sits in holds its __init__.py
        parts = p.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            init = "/".join(parts[:i]) + "/__init__.py"
            add(init, ".".join(parts[:i]), "a package")
    return [plan[p] for p in sorted(plan, key=path_key)]


#: What every source's request carries of the program (its aims, uses, requirements…), whichever file it is.
PROGRAM_KINDS = ("aim", "audience", "use", "requirement", "exclusion", "decision", "setting", "dependency")
#: A decision to keep a file changed by hand (`enough/fabulac_entail.py` `keep`) is about the entailment, not the
#: program: no source is told from it, so keeping or letting go of one file moves no other.
KEPT_DECISION = "N:decision/kept-by-hand-"


def source_brief(cat: dict, items: list[dict], src: dict, plan: list[dict]) -> tuple[dict, list[str]]:
    """What one source's request carries, and the ids it carries in order (its `from`): the file and its role, its
    interfaces with the behaviours and cases about them, the program's own items, and the interfaces of the other
    files with the file each lives in. The command line's file is told it defines `main(argv=None) -> int`."""
    by = _code._by_id(items)
    mine = [by[i] for i in src["interfaces"] if i in by]
    ids = {x["id"] for x in mine}
    about = [x for x in items if item_kind(x) in ("behaviour", "structure", "case")
             and (set(_code._refs(x)) & ids or (isinstance(x.get("given"), dict) and x["given"].get("calls") in ids))]
    if src["role"] == "the command line":
        about += [x for x in _items_of(items, "case") if x not in about and case_surface(x)[0] == "command"]
    program = [x for x in items if item_kind(x) in PROGRAM_KINDS and not str(x.get("id")).startswith(KEPT_DECISION)]
    elsewhere = []
    for other in plan:
        if other["path"] == src["path"]:
            continue
        for i in other["interfaces"]:
            if i in by:
                elsewhere.append({"id": i, "signature": by[i].get("signature"), "in": other["path"],
                                  "module": other["module"]})
    role = src["role"]
    if role == "the command line":
        role = (f"the command line, started as python -m {src['module'].rsplit('.', 1)[0]}: it defines main(argv=None) "
                "-> int, which reads its arguments with argparse, and ends with `if __name__ == \"__main__\": raise "
                "SystemExit(main())`")
    brief = {"file": {"path": src["path"], "module": src["module"], "role": role},
             "items": [_code._compact(x) for x in mine + about],
             "program": [_code._compact(x) for x in program], "elsewhere": elsewhere}
    seen: set = set()
    order = [x["id"] for x in mine + about + program if not (x["id"] in seen or seen.add(x["id"]))]
    order += [e["id"] for e in elsewhere if not (e["id"] in seen or seen.add(e["id"]))]
    return brief, order


# ---------------------------------------------------------------------------
# The brief digest (MacroCOSM OES 18.4.1, `entailed.files[].brief`)
# ---------------------------------------------------------------------------

def _without_provenance(d: Any) -> Any:
    return {k: plain(v) for k, v in d.items() if k != "provenance"} if isinstance(d, dict) else plain(d)


def brief_digest(items: list[dict], ids: list[str]) -> str:
    """The sha256 of the items `ids` names, each dumped canonically (Thym 12.6) without its provenance, joined in
    the order given. An id the fabulac lacks is dumped as nothing (so a gone item moves the file)."""
    by = _code._by_id(items)
    h = hashlib.sha256()
    for i in ids:
        h.update(canonical(_without_provenance(by[i])) if i in by else b"")
    return h.hexdigest()


def rules_digest(inputs: list[Any]) -> str:
    """A file rules wrote: the sha256 of the inputs the rules read, each dumped canonically, joined in order."""
    h = hashlib.sha256()
    for x in inputs:
        h.update(canonical({"input": _without_provenance(x)}))
    return h.hexdigest()


def briefs(cat: dict, items: list[dict]) -> dict[str, dict]:
    """What each file an entailment writes would be told from now, by rules (keeping in step, MacroCOSM OES 18.4.1):
    `{path: {from, brief}}` for every planned source, the prose cases' tests when there are any, and the files rules
    write; `ENTAILED.md` is left out (it is written again whenever anything is). The same `from` and `brief`
    `entail_authored` records."""
    plan = plan_sources(cat, items)
    out: dict[str, dict] = {}
    for src in plan:
        _brief, frm = source_brief(cat, items, src, plan)
        out[src["path"]] = {"from": frm, "brief": brief_digest(items, frm)}
    prose = [c for c, s, _ in runnable(cat, items) if s == "prose"]
    if prose:
        frm = [str(c["id"]) for c in prose] + sorted({r for c in prose for r in _code._refs(c)
                                                     if r in _code._by_id(items)})
        out[PROSE_TESTS] = {"from": frm, "brief": brief_digest(items, frm)}
    out[TESTS] = {"from": "rules", "brief": rules_digest(tests_inputs(cat, items))}
    out[TESTS_INIT] = {"from": "rules", "brief": rules_digest([])}
    out[PYPROJECT] = {"from": "rules", "brief": rules_digest(pyproject_inputs(cat, items))}
    out[RUNNING] = {"from": "rules", "brief": rules_digest(running_inputs(cat, items))}
    return out


#: The host's engine that hands an entailment done again the files it leaves as they are (keeping in step):
#: `held() -> {texts: {path: text}, kept: [path]}`; `enough/fabulac_entail.py` registers it for its own runs.
HELD_ENGINE = "entailment"


def held_by_host(ctx: Any) -> tuple[dict[str, str], set[str]]:
    """The texts the host holds back from telling again (files in step, and files kept by hand), and the paths kept
    by hand, which are never asked again; nothing when the host registered no such engine."""
    eng = (getattr(ctx, "engines", None) or {}).get(HELD_ENGINE)
    got = eng() if callable(eng) else None
    if not isinstance(got, dict):
        return {}, set()
    texts = got.get("texts") if isinstance(got.get("texts"), dict) else {}
    return {str(k): str(v) for k, v in texts.items()}, {str(p) for p in got.get("kept") or []}


def _catalog_part(cat: dict) -> dict:
    """What the rules read of the catalog: the name, the source's licence and language, and the program."""
    src = cat.get("source") if isinstance(cat.get("source"), dict) else {}
    return {"name": cat.get("name"), "language": src.get("language"), "licence": plain(src.get("licence")),
            "program": program_of(cat)}


# ---------------------------------------------------------------------------
# tests/test_cases.py, by rules
# ---------------------------------------------------------------------------

def _lit(v: Any, indent: int = 0) -> str:
    """A Python literal of plain data, the same bytes for the same data on every run: mappings with their keys
    sorted, one entry per line."""
    pad = " " * indent
    if isinstance(v, dict):
        if not v:
            return "{}"
        inner = ",\n".join(f"{pad}    {k!r}: {_lit(v[k], indent + 4)}" for k in sorted(v))
        return "{\n" + inner + f",\n{pad}}}"
    if isinstance(v, list):
        if not v:
            return "[]"
        if all(isinstance(x, str) for x in v) and len(repr(v)) <= 80:
            return repr(v)
        inner = ",\n".join(f"{pad}    {_lit(x, indent + 4)}" for x in v)
        return "[\n" + inner + f",\n{pad}]"
    if isinstance(v, float) and v != v:
        return "float('nan')"
    return repr(v)


def _method(cid: str, taken: set[str]) -> str:
    base = "test_" + (re.sub(r"[^0-9a-zA-Z]+", "_", cid.split("/", 1)[-1]).strip("_").lower() or "case")
    name, n = base, 2
    while name in taken:
        name, n = f"{base}_{n}", n + 1
    taken.add(name)
    return name


def runnable(cat: dict, items: list[dict]) -> list[tuple[dict, str | None, str]]:
    """Every `P:case` in id order, with its surface (`command`, `function`, `prose`, or None) and why not, the
    surface's preconditions on the program and the interfaces included."""
    by = _code._by_id(items)
    main = main_module(cat)
    prog = program_of(cat)
    out = []
    for c in sorted(_items_of(items, "case"), key=lambda x: str(x["id"])):
        surface, why = case_surface(c)
        if surface == "command":
            start = prog.get("start")
            if prog.get("kind") not in ("tool", "service") or not (isinstance(start, list) and start):
                surface, why = None, (f"a {prog.get('kind') or 'program'} has no command to start: the program's "
                                      "start is not set")
        elif surface == "function":
            iface = by.get(str(c["given"]["calls"]))
            if iface is None or item_kind(iface) != "interface":
                surface, why = None, f"given.calls names {c['given']['calls']}, which the fabulac does not hold"
            elif iface.get("surface") != "function":
                surface, why = None, f"{iface['id']} is a {iface.get('surface')}, and a function case calls a function"
            elif interface_place(iface, items, main) is None:
                surface, why = None, f"{iface['id']}'s name is not a Python name a test can call"
        out.append((c, surface, why))
    return out


def _case_data(c: dict, surface: str, items: list[dict], main: str) -> dict:
    if surface == "command":
        g, e = c["given"], c["expect"]
        d: dict = {"steps": [{"arguments": list(s.get("arguments") or []), **(
            {"input": s["input"]} if s.get("input") is not None else {})} for s in g["steps"]],
            "expect": [{k: s[k] for k in COMMAND_EXPECT_STEP if k in s} for s in e["steps"]]}
        for k in ("files", "env", "cwd"):
            if k in g:
                d[k] = plain(g[k])
        if "files" in e:
            d["files-after"] = plain(e["files"])
        return d
    iface = _code._by_id(items)[c["given"]["calls"]]
    mod, attr = interface_place(iface, items, main)
    d = {"module": mod, "name": attr, "arguments": plain(c["given"].get("arguments") or {})}
    if "value" in c["expect"]:
        d["value"] = plain(c["expect"]["value"])
    else:
        d["raises"] = plain(c["expect"]["raises"])
    return d


_TESTS_HEAD = '''"""The cases of {name}, as tests: one test per case of {fab} whose given and expect are data.

Written by rules from the cases alone, never by the model that wrote the program (MacroCOSM OES 18.4.7). Change a
case in the fabulac and entail again; an edit here is a hand edit.
"""
import importlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
START = {start}
CASE = "<CASE>"
STEP_SECONDS = {seconds}
ENTRY = START[1] if START[:1] == ["-m"] else (START[0] if START else "")
BOOT = ("import os, runpy, sys; root = sys.argv.pop(1); entry = sys.argv.pop(1); sys.path.insert(0, root); "
        "runpy.run_path(os.path.join(root, entry), run_name='__main__') if entry.endswith('.py') else "
        "runpy.run_module(entry, run_name='__main__', alter_sys=True)")


def interpreter():
    """This interpreter, with the flags this run was started with (in enough's sandbox: -I -S -X utf8 -B)."""
    flags = []
    if sys.flags.isolated:
        flags.append("-I")
    elif sys.flags.ignore_environment:
        flags.append("-E")
    if sys.flags.no_site:
        flags.append("-S")
    if sys.flags.dont_write_bytecode:
        flags.append("-B")
    if sys.flags.utf8_mode:
        flags += ["-X", "utf8"]
    return [os.path.realpath(sys.executable)] + flags


def plain(value):
    """A value as the case writes it: a tuple read as a list, throughout."""
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, dict):
        return {{k: plain(v) for k, v in value.items()}}
    return value


def run_command(test, case):
    """A command case: each step runs the program's start in a folder of the case's own, in order."""
    folder = Path(tempfile.mkdtemp(prefix="case-"))
    try:
        for rel, text in (case.get("files") or {{}}).items():
            p = folder / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        env = dict(os.environ)
        env["HOME"] = str(folder)
        for k, v in (case.get("env") or {{}}).items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v.replace(CASE, str(folder))
        cwd = folder / case.get("cwd", ".")
        cwd.mkdir(parents=True, exist_ok=True)
        spellings = sorted({{str(folder), os.path.realpath(folder)}}, key=len, reverse=True)

        def said(text):
            for s in spellings:
                text = text.replace(s, CASE)
            return text

        for i, (step, want) in enumerate(zip(case["steps"], case["expect"])):
            argv = [a.replace(CASE, str(folder)) for a in step["arguments"]]
            got = subprocess.run(interpreter() + ["-c", BOOT, str(ROOT), ENTRY] + argv,
                                 input=step.get("input", ""), capture_output=True, text=True, encoding="utf-8",
                                 errors="surrogateescape", env=env, cwd=cwd, timeout=STEP_SECONDS)
            if "exit" in want:
                test.assertEqual(got.returncode, want["exit"], f"step {{i}}: the exit status ({{got.stderr[-500:]}})")
            if "output" in want:
                test.assertEqual(said(got.stdout), want["output"], f"step {{i}}: the output")
            if "error-output" in want:
                test.assertEqual(said(got.stderr), want["error-output"], f"step {{i}}: the error output")
        for rel, text in (case.get("files-after") or {{}}).items():
            p = folder / rel
            if text is None:
                test.assertFalse(p.exists(), f"{{rel}} is not there after")
            else:
                test.assertTrue(p.is_file(), f"{{rel}} is there after")
                test.assertEqual(said(p.read_text(encoding="utf-8")), text, f"what {{rel}} holds after")
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def call_function(test, case):
    """A function case: the module imported, the interface called with its arguments by name."""
    fn = importlib.import_module(case["module"])
    for part in case["name"].split("."):
        fn = getattr(fn, part)
    if "raises" in case:
        with test.assertRaises(BaseException) as caught:
            fn(**case["arguments"])
        names = [c.__name__ for c in type(caught.exception).__mro__]
        test.assertIn(case["raises"]["error"], names)
        if "message" in case["raises"]:
            test.assertEqual(str(caught.exception), case["raises"]["message"])
    else:
        test.assertEqual(plain(fn(**case["arguments"])), plain(case["value"]))


CASES = {cases}


class Cases(unittest.TestCase):
    maxDiff = None
'''


def tests_text(cat: dict, items: list[dict], fab_file: str) -> tuple[str, list[str]]:
    """`tests/test_cases.py` by rules, and the cases it holds, in order. Every runnable case is one method, named
    after its id, with its id and summary as its docstring; the cases are data in `CASES`."""
    main = main_module(cat)
    rows = [(c, s) for c, s, _ in runnable(cat, items) if s in SURFACES]
    data = {c["id"]: _case_data(c, s, items, main) for c, s in rows}
    prog = program_of(cat)
    start = prog.get("start") if isinstance(prog.get("start"), list) else []
    head = (f"# written by rules from {fab_file}, not by a model: one test per runnable case "
            "(MacroCOSM OES 18.4.7)\n")
    out = head + _TESTS_HEAD.format(name=cat.get("name"), fab=fab_file, start=repr([str(s) for s in start]),
                                    seconds=STEP_SECONDS, cases=_lit(data))
    taken: set[str] = set()
    for c, s in rows:
        m = _method(str(c["id"]), taken)
        doc = fold(f"{c['id']}: {c.get('summary') or c.get('name') or ''}")[:200]
        call = "run_command" if s == "command" else "call_function"
        out += f"\n    def {m}(self):\n        {doc!r}\n        {call}(self, CASES[{str(c['id'])!r}])\n"
    if not rows:
        out += ("\n    def test_no_runnable_case(self):\n        'The fabulac holds no case whose given and expect "
                "are data.'\n        self.skipTest('no runnable case')\n")
    out += "\n\nif __name__ == \"__main__\":\n    unittest.main()\n"
    return out, [str(c["id"]) for c, _ in rows]


def tests_inputs(cat: dict, items: list[dict]) -> list[Any]:
    """What `tests_text` reads: the program, and every case with the interfaces the function cases call."""
    by = _code._by_id(items)
    cases = sorted(_items_of(items, "case"), key=lambda x: str(x["id"]))
    called = sorted({str(c["given"]["calls"]) for c in cases if isinstance(c.get("given"), dict)
                     and isinstance(c["given"].get("calls"), str)})
    return [_catalog_part(cat)] + cases + [by[i] for i in called if i in by]


# ---------------------------------------------------------------------------
# pyproject.toml and RUNNING.md, by rules
# ---------------------------------------------------------------------------

def _toml(s: Any) -> str:
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def python_floor(items: list[dict]) -> str | None:
    """`>=3.10` from `C:dependency/python`'s `version` (`3.10`, `>=3.10`, `3.10 or later`); None when unsaid."""
    py = next((x for x in items if x.get("id") == "C:dependency/python"), {})
    v = py.get("version")
    if not isinstance(v, str):
        return None
    m = re.search(r"(\d+)\.(\d+)", v)
    return f">={m.group(1)}.{m.group(2)}" if m else None


def version_of(items: list[dict]) -> str:
    rel = [x for x in _items_of(items, "release") if isinstance(x.get("version"), str) and x["version"].strip()]
    return str(rel[-1]["version"]).strip() if rel else NO_VERSION


def dependencies(items: list[dict]) -> tuple[list[str], list[str], list[str]]:
    """`(pinned, outside, why-not)`: each run-time dependency besides Python as `name==version` (or the name alone
    when no version is recorded); the names outside the standard library; and the dependencies that name no package,
    with why."""
    pinned, outside, why = [], [], []
    for x in _items_of(items, "dependency"):
        if x.get("id") == "C:dependency/python" or x.get("scope") not in ("run-time", None):
            continue
        name = x.get("package") if isinstance(x.get("package"), str) else x.get("name")
        name = str(name or "").strip()
        if not _PACKAGE.match(name):
            why.append(f"{x['id']} names no package (its words: {fold(str(x.get('summary') or ''))[:80]})")
            continue
        ver = x.get("version") if isinstance(x.get("version"), str) else ""
        ver = ver.strip().lstrip("=")
        pinned.append(f"{name}=={ver}" if re.fullmatch(r"\d+(\.\d+)*\S*", ver) else name)
        outside.append(name)
    return sorted(pinned, key=str.lower), sorted(outside, key=str.lower), why


def script_name(cat: dict, items: list[dict]) -> str:
    """The command a person types once the program is installed: the first word of its command interface's name,
    else the program's module."""
    for it in _items_of(items, "interface"):
        if it.get("surface") == "command":
            w = str(it.get("name") or "").split()
            if w and re.fullmatch(r"[a-z][a-z0-9_-]*", w[0]):
                return w[0]
    return main_module(cat).replace("_", "-")


def project_name(cat: dict) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", str(cat.get("name") or "program")).strip("-._")
    return s or main_module(cat)


def pyproject_text(cat: dict, items: list[dict], fab_file: str) -> str:
    """`pyproject.toml` by rules: the project's name and version, the Python floor, its entry point, its
    dependencies pinned exactly, and `[tool.enough]` repeating the catalog's `program`."""
    prog = program_of(cat)
    kind = prog.get("kind") or "tool"
    start = prog.get("start") if isinstance(prog.get("start"), list) else []
    pinned, _outside, _why = dependencies(items)
    floor = python_floor(items)
    out = [f"# written by rules from {fab_file}, not by a model: the project's name, version, Python, entry point "
           "and dependencies, and [tool.enough], from its catalog's program and its items",
           "[build-system]", 'requires = ["setuptools>=61"]', 'build-backend = "setuptools.build_meta"', "",
           "[project]", f"name = {_toml(project_name(cat))}", f"version = {_toml(version_of(items))}"]
    if floor:
        out.append(f"requires-python = {_toml(floor)}")
    out.append("dependencies = [" + ", ".join(_toml(p) for p in pinned) + "]")
    cmd = command_path(cat)
    if cmd is not None and cmd.endswith("/__main__.py"):
        out += ["", "[project.scripts]", f"{script_name(cat, items)} = {_toml(cmd[:-3].replace('/', '.') + ':main')}"]
    out += ["", "[tool.setuptools.packages.find]", f"include = [{_toml(main_module(cat))}, "
            f"{_toml(main_module(cat) + '.*')}]", "", "[tool.enough]", f"kind = {_toml(kind)}",
            "start = [" + ", ".join(_toml(s) for s in start) + "]"]
    serve = prog.get("serve") if isinstance(prog.get("serve"), dict) else {}
    if kind == "service":
        port = serve.get("port") if isinstance(serve.get("port"), int) else 0
        reach = serve.get("reach") if isinstance(serve.get("reach"), list) else []
        out.append(f"serve = {{port = {port}, reach = [" + ", ".join(_toml(r) for r in reach) + "]}")
    else:
        out.append("serve = {}")
    return "\n".join(out) + "\n"


def pyproject_inputs(cat: dict, items: list[dict]) -> list[Any]:
    return [_catalog_part(cat)] + [x for x in items if item_kind(x) in ("dependency", "release")
                                   or (item_kind(x) == "interface" and x.get("surface") == "command")]


def running_text(cat: dict, items: list[dict], fab_file: str) -> str:
    """`RUNNING.md` by rules: how to run its tests, how to start it, what it needs, and what enough will and will not
    run of it here."""
    name = str(cat.get("name") or main_module(cat))
    prog = program_of(cat)
    kind = prog.get("kind") or "tool"
    main = main_module(cat)
    start = prog.get("start") if isinstance(prog.get("start"), list) else []
    pinned, outside, why = dependencies(items)
    floor = python_floor(items)
    cases = runnable(cat, items)
    n_rules = sum(1 for _, s, _ in cases if s in SURFACES)
    n_prose = sum(1 for _, s, _ in cases if s == "prose")
    out = [f"*written by rules from {fab_file}, not by a model*", "", f"# Running {name}", "",
           "## Its tests", "",
           "From this folder:", "", "    python -m unittest discover -s tests -t .", "",
           f"`tests/test_cases.py` holds {n_rules} test{'s' if n_rules != 1 else ''}, written by rules from the "
           "fabulac's cases." + (f" `tests/test_prose_cases.py` holds {n_prose}, written by a model from cases told "
                                 "in words." if n_prose else ""), "", "## Starting it", ""]
    if kind == "library":
        out += [f"{name} is a library: another program imports it.", "", f"    import {main}", ""]
    elif start:
        line = " ".join(str(s) for s in start)
        out += [f"{name} is a {kind}. From this folder:", "", f"    python {line} …", ""]
        if command_path(cat) and str(command_path(cat)).endswith("/__main__.py"):
            out += [f"Installed (`pip install .`), it is the command `{script_name(cat, items)}`.", ""]
        if kind == "service":
            serve = prog.get("serve") if isinstance(prog.get("serve"), dict) else {}
            port = serve.get("port") if isinstance(serve.get("port"), int) else 0
            reach = serve.get("reach") if isinstance(serve.get("reach"), list) else []
            out += [f"It serves on port {port if port else 'one the host chooses'}, and may reach "
                    + (", ".join(f"`{r}`" for r in reach) if reach else "nothing outside it") + ".", ""]
    else:
        out += [f"{name} is a {kind}, and its fabulac does not say how it starts (`program.start`).", ""]
    out += ["## What it needs", ""]
    out.append(f"Python {floor[2:]} or later" if floor else "Python (the fabulac names no version)")
    if pinned:
        out[-1] += ", and " + ", ".join(f"`{p}`" for p in pinned) + "."
    else:
        out[-1] += ", and its standard library alone."
    for w in why:
        out += ["", f"Not written into its dependencies: {w}."]
    out += ["", "## What enough runs here", ""]
    can = []
    if outside:
        can.append(f"enough cannot run it here yet: it needs {', '.join(f'`{o}`' for o in outside)}, outside the "
                   "standard library, and enough's sandbox has the standard library only and installs nothing. Its "
                   "source is entailed and can run elsewhere.")
    elif kind == "service":
        can.append(f"enough runs its tests in its sandbox. {SERVING_LATER.format(name=name)}")
    elif kind == "library":
        can.append("enough runs its tests in its sandbox; a library has nothing to start.")
    else:
        can.append("enough runs its tests, and starts it with the arguments you give, in its sandbox.")
    can.append("The sandbox is a copy of this folder with a home and a temporary folder of its own: no network, "
               "nothing of the project or your home folder unless you hand a file over (as a copy it cannot write), "
               "Python's standard library only, limits on time, processor time, output, disk and file size, and a "
               "stop. Where memory cannot be limited, enough says so and promises nothing for it.")
    can.append("enough never runs a cshort, a folder a fabulac was decompiled from, or any code you did not author.")
    out += [" ".join(can[:1]), "", can[1], "", can[2]]
    return "\n".join(out) + "\n"


def running_inputs(cat: dict, items: list[dict]) -> list[Any]:
    return pyproject_inputs(cat, items) + sorted(_items_of(items, "case"), key=lambda x: str(x["id"]))


TESTS_INIT_TEXT = "# written by rules: the tests' package mark, so that unittest discover finds them\n"


# ---------------------------------------------------------------------------
# ENTAILED.md, by rules
# ---------------------------------------------------------------------------

def entailed_footer(fab_file: str, day: str, who: str) -> str:
    return f"*an entailment of {fab_file}, in Python, entailed on {day} by {who}*"


def entailed_text(cat: dict, footer: str, rows: list[dict], *, model_cases: list[str],
                  not_entailed: list[tuple[str, str]]) -> str:
    """`ENTAILED.md` (MacroCOSM OES 18.4.7): the footer line first; a table of the files written, each with what it
    came from, its sha256 and its brief digest; the tests a model wrote; what was not entailed and why; last, the
    source's licence line."""
    out = [footer, "", "| path | from | sha256 | brief |", "|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: path_key(r["path"])):
        frm = r["from"] if isinstance(r["from"], str) else ", ".join(r["from"]) or "nothing"
        out.append(f"| {r['path']} | {frm} | {r['sha256']} | {r['brief']} |")
    out.append("")
    if model_cases:
        out += [f"Written by a model, from cases told in words ({PROSE_TESTS}): " + ", ".join(model_cases) + ".", ""]
    if not_entailed:
        out += ["Not entailed:", ""] + [f"- {cid}: {why}." for cid, why in not_entailed] + [""]
    out.append(_code.licence_line(cat))
    return "\n".join(out) + "\n"


def read_entailed(text: str) -> dict:
    """`ENTAILED.md` read back: `{footer, rows: {path: {from, sha256, brief}}, model: [ids], not: {id: why},
    licence}`."""
    lines = text.replace("\r\n", "\n").split("\n")
    full = [ln for ln in lines if ln.strip()]
    rows = {}
    for ln in lines:
        m = _ROW.match(ln)
        if m:
            rows[m.group("path")] = {"from": m.group("from"), "sha256": m.group("sha"), "brief": m.group("brief")}
    model: list[str] = []
    for ln in lines:
        if ln.startswith("Written by a model, from cases told in words"):
            model = [x.strip() for x in ln.split(":", 1)[1].rstrip(".").split(",") if x.strip()]
    nots = {}
    for ln in lines:
        m = re.match(r"^- (P:case/\S+): (.+)\.$", ln)
        if m:
            nots[m.group(1)] = m.group(2)
    return {"footer": full[0] if full else "", "rows": rows, "model": model, "not": nots,
            "licence": full[-1] if full else ""}


# ---------------------------------------------------------------------------
# The prose cases' tests: a model step of their own (`test`)
# ---------------------------------------------------------------------------

TEST_SYSTEM = (
    "You write one test, a method of a Python unittest.TestCase, for one case of a program, from the case alone. The "
    "case is told in words: what is given and what is expected. The program's folder is ROOT; its start is START "
    "(run it with subprocess.run(interpreter() + ['-c', BOOT, str(ROOT), ENTRY] + arguments, ...)); a "
    "function is reached with importlib.import_module. These names are already defined: os, sys, subprocess, "
    "tempfile, shutil, importlib, unittest, Path, ROOT, START, ENTRY, BOOT, interpreter(). Use the standard library "
    "only, "
    "write in a temporary folder of the test's own, and assert exactly what the case expects, nothing more. Return "
    "only the method, `def {method}(self):` and its body, in one fenced code block.")


def test_messages(contract: dict, inputs: dict) -> list[dict] | None:
    """The request of the `test` step; None for a request that is not its own."""
    def get(name: str) -> str:
        pair = (inputs or {}).get(name)
        v = pair[0] if isinstance(pair, tuple) else pair
        return v.text() if hasattr(v, "text") else str(v or "")
    if get("fabulac") != "test":
        return None
    user = (f"The program: {get('name')}. Its start: {get('start')}.\nThe case, and the interfaces it is of:\n"
            f"```yaml\n{get('brief')}```\nWrite the method {get('method')}.")
    return [{"role": "system", "content": TEST_SYSTEM.replace("{method}", get("method"))},
            {"role": "user", "content": user}]


PROMPTS = {"entail": test_messages}

_PROSE_HEAD = '''"""Tests a model wrote from the cases of {name} told in words: not written by rules
(MacroCOSM OES 18.4.7). Each test names its case; ENTAILED.md lists them as written by a model."""
import importlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_cases import BOOT, ENTRY, ROOT, START, interpreter  # noqa: F401


class ProseCases(unittest.TestCase):
    maxDiff = None
'''


def _method_text(out: Any, method: str) -> str:
    """The model's method, renamed by rule to the case's method and indented into the class."""
    s = _code._file_text(out)
    s = textwrap.dedent(s).strip("\n")
    s = re.sub(r"^(\s*)def\s+\w+\s*\(", rf"\1def {method}(", s, count=1, flags=re.M)
    if not re.search(rf"^def {method}\(", s, re.M):
        s = f"def {method}(self):\n" + textwrap.indent(s or "self.fail('no test was written')", "    ")
    return textwrap.indent(s, "    ")


# ---------------------------------------------------------------------------
# entail f as code, for an authored fabulac
# ---------------------------------------------------------------------------

def entail_authored(ctx: Any, fab: Value, **mods: Any) -> Value:
    """`entail f as code` of an authored fabulac (Thym 20.7, `entail-authored-python`): the sources asked of a
    model file by file (the `code` step, as a cshort's), the prose cases' tests asked one by one (the `test` step),
    and by rules `tests/test_cases.py`, `tests/__init__.py`, `pyproject.toml`, `RUNNING.md` and `ENTAILED.md`.
    Called again with what failed, it asks again only for the files the failures name."""
    cat, items = _code._fabula(fab, "entail … as code takes a fabulac")
    _code._need_fabulac(cat, "f", "only a fabulac entails code")
    if not is_authored(cat):
        raise MoveError("only an authored fabulac is entailed as its program; this one is compiled to a cshort")
    if program_of(cat).get("kind") not in ("tool", "library", "service"):
        raise MoveError("the fabulac's program names no kind (tool, library or service): entail needs it")
    fab_file = _code.fabulac_file(cat, fab)
    name = folder_name(cat, fab)
    plan = plan_sources(cat, items)
    cases = runnable(cat, items)
    prose = [c for c, s, _ in cases if s == "prose"]
    paths = [s["path"] for s in plan] + ([PROSE_TESTS] if prose else [])
    prev = getattr(ctx, "previous", None)
    texts: dict[str, str] = {}
    meta: dict = {}
    methods: dict[str, str] = {}
    if isinstance(prev, Value) and isinstance(prev.payload, Folder):
        texts = {p: prev.payload.text(p) for p in paths if prev.payload.entry(p) is not None}
        meta = dict((prev.origin or {}).get("cshort") or {})
        methods = dict(((prev.origin or {}).get("entailed") or {}).get("methods") or {})
    redo = _code._failed_paths(getattr(ctx, "failed", None) or [], paths) if texts else set(paths)
    if texts and not redo:
        redo = set(paths)
    held, kept = held_by_host(ctx)                 # keeping in step: what is in step or kept by hand is not told again
    if held and not texts:
        texts, redo = {p: held[p] for p in paths if p in held}, set()
    for p in kept:
        if p in held and p in paths:
            texts[p] = held[p]
        redo.discard(p)
    atem = _code._yaml(plain(cat.get("atem") or {}))
    rows: list[dict] = []

    def note(cand: Any) -> None:
        eng = str(cand.get("engine") or "") if isinstance(cand, dict) else ""
        if eng.startswith("model:") and eng[6:] not in ("", "unknown"):
            meta.setdefault("model", eng[6:])
        for k in ("route", "provider"):
            if isinstance(cand, dict) and cand.get(k):
                meta.setdefault(k, cand[k])

    for src in plan:
        p = src["path"]
        brief, frm = source_brief(cat, items, src, plan)
        if p in redo or p not in texts:
            inputs = {"fabulac": Value("string", "code"), "path": Value("string", p),
                      "name": Value("string", str(cat.get("name") or name)),
                      "brief": Value("string", _code._yaml(plain(brief))), "atem": Value("string", atem)}
            cand = ctx.ask({"schema": {"format": "markdown", "says": f"the whole of {p}, nothing else"}}, inputs)
            texts[p] = _code._file_text(cand.get("output") if isinstance(cand, dict) else None)
            note(cand)
        rows.append({"path": p, "from": frm, "brief": brief_digest(items, frm)})
    model_cases = [str(c["id"]) for c in prose]
    if prose:
        start = program_of(cat).get("start") or []
        if PROSE_TESTS in redo or PROSE_TESTS not in texts:
            taken: set[str] = set()
            methods = {}
            for c in prose:
                m = _method(str(c["id"]), taken)
                about = [x for x in items if x["id"] in set(_code._refs(c))]
                inputs = {"fabulac": Value("string", "test"), "path": Value("string", PROSE_TESTS),
                          "case": Value("string", str(c["id"])), "method": Value("string", m),
                          "name": Value("string", str(cat.get("name") or name)),
                          "start": Value("string", " ".join(str(s) for s in start) or "none: a library"),
                          "brief": Value("string", _code._yaml(plain([_code._compact(c)] + [
                              _code._compact(x) for x in about])))}
                cand = ctx.ask({"schema": {"format": "markdown", "says": f"one unittest method, {m}"}}, inputs)
                methods[str(c["id"])] = _method_text(cand.get("output") if isinstance(cand, dict) else None, m)
                note(cand)
            texts[PROSE_TESTS] = (_PROSE_HEAD.format(name=cat.get("name")) + "".join(
                f"\n    # {cid}: written by a model from the case's words\n{methods[cid]}\n" for cid in model_cases)
                + "\n\nif __name__ == \"__main__\":\n    unittest.main()\n")
        frm = model_cases + sorted({r for c in prose for r in _code._refs(c) if r in _code._by_id(items)})
        rows.append({"path": PROSE_TESTS, "from": frm, "brief": brief_digest(items, frm)})
    texts[TESTS], _held = tests_text(cat, items, fab_file)
    texts[TESTS_INIT] = TESTS_INIT_TEXT
    texts[PYPROJECT] = pyproject_text(cat, items, fab_file)
    texts[RUNNING] = running_text(cat, items, fab_file)
    rows += [{"path": TESTS, "from": "rules", "brief": rules_digest(tests_inputs(cat, items))},
             {"path": TESTS_INIT, "from": "rules", "brief": rules_digest([])},
             {"path": PYPROJECT, "from": "rules", "brief": rules_digest(pyproject_inputs(cat, items))},
             {"path": RUNNING, "from": "rules", "brief": rules_digest(running_inputs(cat, items))}]
    for r in rows:
        r["sha256"] = hashlib.sha256(texts[r["path"]].encode("utf-8")).hexdigest()
    syn = engine(ctx, "syntax")
    syntax = {}
    for p in sorted(texts):
        if p.endswith(".py"):
            syntax[p] = {"sha256": hashlib.sha256(texts[p].encode("utf-8")).hexdigest(),
                         "outline": syn.outline(p, texts[p])}
    not_entailed = [(str(c["id"]), why) for c, s, why in cases if s is None]
    last = _ENTAILED_FOOT.match(read_entailed(held[ENTAILED])["footer"]) if ENTAILED in held else None
    who = last.group("who") if last and not meta.get("model") else _code._who(meta)   # nothing asked again: as before
    footer = entailed_footer(fab_file, utc_day(ctx), who)
    texts[ENTAILED] = entailed_text(cat, footer, rows, model_cases=model_cases, not_entailed=not_entailed)
    folder = _code.folder_of_texts(f"{name}/", texts)
    files = [{"path": r["path"], "sha256": r["sha256"], "from": r["from"], "brief": r["brief"]}
             for r in sorted(rows, key=lambda r: path_key(r["path"]))]
    return Value("folder", folder, origin={"cshort": {**meta, "syntax": syntax, "day": utc_day(ctx)},
                                           "entailed": {"path": f"{name}/", "files": files, "methods": methods}})


# ---------------------------------------------------------------------------
# The entailment's readings of the cshort's checks (code.py dispatches here) and cases-entailed
# ---------------------------------------------------------------------------

def files_present(f: Folder, cat: dict, items: list[dict], fab: Value | None) -> tuple[bool, str]:
    """`files-present` of an entailment: every source the plan names, the files rules write exactly as they write
    them, `ENTAILED.md`, and the digests it lists are the files' (Thym 7.3)."""
    if f.entry(ENTAILED) is None:
        return False, "ENTAILED.md is missing"
    fab_file = _code.fabulac_file(cat, fab) if fab is not None else f"{cat.get('name')}.fabulac.cosm"
    want = [s["path"] for s in plan_sources(cat, items)] + list(RULES_FILES)
    if any(s == "prose" for _c, s, _w in runnable(cat, items)):
        want.append(PROSE_TESTS)
    missing = [p for p in want if f.entry(p) is None]
    if missing:
        return False, f"{', '.join(missing)} {'is' if len(missing) == 1 else 'are'} missing"
    exact = {TESTS: tests_text(cat, items, fab_file)[0], TESTS_INIT: TESTS_INIT_TEXT,
             PYPROJECT: pyproject_text(cat, items, fab_file), RUNNING: running_text(cat, items, fab_file)}
    for p, text in exact.items():
        if f.text(p) != text:
            return False, f"{p} is not the file rules write from the fabulac"
    listed = read_entailed(f.text(ENTAILED))["rows"]
    for p, row in listed.items():
        e = f.entry(p)
        if e is None:
            return False, f"ENTAILED.md lists {p}, which is not there"
        if e.sha256 != row["sha256"]:
            return False, f"ENTAILED.md lists {p} with another sha256 than the file's"
    have = {e.path for e in f.entries if e.path != ENTAILED}
    if set(listed) != have:
        return False, "ENTAILED.md does not list exactly the files entailed"
    return True, ""


def interfaces_present(f: Folder, cat: dict, items: list[dict], output: Value, ctx: Any) -> tuple[bool, str]:
    """`interfaces-present` of an entailment: every function interface is defined in the file the plan puts it in,
    with the parameters its `takes` (or its signature) names; every command interface's file defines `main`."""
    plan = plan_sources(cat, items)
    where = {i: s["path"] for s in plan for i in s["interfaces"]}
    problems = []
    for it in _items_of(items, "interface"):
        path = where.get(it["id"])
        if path is None:
            continue
        if f.entry(path) is None:
            problems.append(f"{path}: the file is missing, so {it['id']} is not there")
            continue
        ol = _code._syntax_of(output, ctx, path, f.text(path))
        if not ol.get("ok"):
            problems.append(f"{path}: it does not parse, so {it['id']} cannot be found")
            continue
        if it.get("surface") == "command":
            if not any(d.get("qual") == "main" and d.get("kind") == "function" for d in ol.get("defs") or []):
                problems.append(f"{path}: main, the command line {it['id']} starts, is not defined")
            elif it.get("takes"):
                why = _code._command_present(it, ol)
                if why:
                    problems.append(f"{path}: {why}")
            continue
        place = interface_place(it, items, main_module(cat))
        attr = place[1] if place else str(it.get("name"))
        d = next((x for x in ol.get("defs") or [] if x.get("qual") == attr), None)
        if d is None:
            problems.append(f"{path}: {attr} ({it['id']}) is not defined")
            continue
        surface = it.get("surface")
        if d.get("kind") != surface:
            problems.append(f"{path}: {attr} is a {d.get('kind')}, and the fabulac says {surface}")
            continue
        if surface == "class":
            continue
        need = _code._sig_names(it.get("takes")) if it.get("takes") else _signature_params(it.get("signature"), attr)
        if need is None:
            continue
        have = [str(p.get("name")) for i, p in enumerate(d.get("params") or [])
                if not (surface == "method" and i == 0 and p.get("name") in ("self", "cls"))]
        if have != [n.lstrip("*") for n in need]:
            problems.append(f"{path}: {attr} takes ({', '.join(have)}), and the fabulac says ({', '.join(need)})")
    if problems:
        return False, "; ".join(problems[:6]) + (f" (and {len(problems) - 6} more)" if len(problems) > 6 else "")
    return True, ""


def footer_problem(f: Folder, cat: dict, fab: Value | None, ctx: Any) -> str | None:
    """`footer` of an entailment: `ENTAILED.md`'s first line names the fabulac's file, the language, the run's day in
    UTC and the model; its last line is the licence line, agreeing with `source.licence`."""
    if f.entry(ENTAILED) is None:
        return "ENTAILED.md is missing"
    lines = [ln for ln in f.text(ENTAILED).split("\n") if ln.strip()]
    m = _ENTAILED_FOOT.match(lines[0]) if lines else None
    if not m:
        return f"ENTAILED.md's first line is not an entailment's footer: {lines[0][:80] if lines else ''}"
    if fab is not None and m.group("f") != _code.fabulac_file(cat, fab):
        return f"the footer names {m.group('f')}, not {_code.fabulac_file(cat, fab)}"
    if m.group("day") != utc_day(ctx):
        return f"the footer's day is {m.group('day')}, the run's {utc_day(ctx)}"
    if lines[-1] != _code.licence_line(cat):
        return f"ENTAILED.md's last line is not the licence line: {lines[-1][:80]}"
    return None


def cases_entailed_problem(cat: dict, items: list[dict], fab_file: str, text_of: Any) -> str | None:
    """`cases-entailed` (MacroCOSM OES 18.4.8) over an entailment's files (`text_of(path) -> text or None`): every
    runnable case is a test in `tests/test_cases.py`, which is exactly what rules write; every prose case is a test
    in `tests/test_prose_cases.py` named in `ENTAILED.md` as a model's, or named there as not entailed; every other
    case is named there with its reason. None when it holds."""
    ent = text_of(ENTAILED)
    if ent is None:
        return None                                     # a cshort: nothing to check
    tests = text_of(TESTS)
    want, held = tests_text(cat, items, fab_file)
    if tests is None:
        return f"{TESTS} is missing"
    if tests != want:
        got = set(re.findall(r"^    (P:case/\S+?)': ", tests, re.M)) | set(re.findall(r"CASES\['(P:case/[^']+)'\]",
                                                                                         tests))
        lost = [c for c in held if c not in got]
        return (f"{TESTS} has no test for {', '.join(lost[:5])}" if lost
                else f"{TESTS} is not what rules write from the fabulac's cases")
    read = read_entailed(ent)
    prose_text = text_of(PROSE_TESTS) or ""
    for c, s, why in runnable(cat, items):
        cid = str(c["id"])
        if s in SURFACES:
            continue
        if s == "prose":
            if cid in read["model"] and f"# {cid}: written by a model" in prose_text:
                continue
            if cid in read["not"]:
                continue
            return f"{cid} is told in words, and is neither a test marked as a model's nor named as not entailed"
        if cid not in read["not"]:
            return f"{cid} was not entailed ({why}), and ENTAILED.md does not say so"
    return None


@check("cases-entailed")
def _cases_entailed(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """After an authored fabulac is entailed, every runnable case is a test in `tests/test_cases.py`, and every other
    case is a test marked as written by a model or named in `ENTAILED.md` with its reason; of a cshort it holds with
    nothing to check (Thym 7.3, MacroCOSM OES 18.4.8)."""
    f, cat, items, fab = _code._cshort_parts(output, inputs)
    if f is None or not is_entailment(f):
        return True, ""
    why = cases_entailed_problem(cat, items, _code.fabulac_file(cat, fab) if fab is not None else "",
                                 lambda p: f.text(p) if f.entry(p) is not None else None)
    return (False, why) if why else (True, "")


__all__ = ["AUTHORED", "CASE_TOKEN", "ENTAILED", "PROMPTS", "PROSE_TESTS", "PYPROJECT", "RUNNING", "SURFACES", "TESTS",
           "TESTS_INIT", "answer_shape", "brief_digest", "case_surface", "cases_entailed_problem", "entail_authored",
           "entailed_footer", "entailed_text", "expect_problem", "files_present", "folder_name", "footer_problem",
           "given_surface", "interface_place", "interfaces_present", "is_authored", "is_authored_fabula",
           "is_entailment", "main_module", "plan_sources", "pyproject_text", "read_entailed", "rules_digest",
           "running_text", "runnable", "source_brief", "tests_text"]
