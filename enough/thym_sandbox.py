"""The host's sandbox engine for Thym's `run` (Thym 20.12; `enough/thym/moves/run_entailment.py`): the one door from a
Thym run to `enough.sandbox`, registered in `thym_host.SIBLING_ENGINES` as `sandbox`.

Thym runs nothing itself: its `run` move asks this engine, and the runtime records each answer as an engine call
(Thym 12.4), so a replay reads the record and runs nothing. Two functions, both taking the folder value the program
named (its digest is its tree, so a replay matches the record without the disk):

- `beside(code)`: what the fabulac of the same name beside the folder says: `{found, fabulac, source: {kind},
  program: {kind, start}, entailed: {path, files: [{path, sha256}]}}`, or `{found: false, fabulac, why}`. The move
  holds `only-authored` against it before it asks for a run.
- `run(code, as_word, arguments)`: the run, in the sandbox alone (`enough.sandbox`: `prepare`, `run_tests` or
  `run_tool`, then `discard`), answered as `{report: …}` (the report's host part; the move adds what it knows) or
  `{refused: <sentence>, reason}` when enough will not run it: not authored (the sandbox's own first check), a
  service (serving comes in a later edition), a need outside the standard library, an interpreter too old, a system
  with no box. A refusal is an answer, not a raise, so that a replay refuses in the same words.

The tool gets an empty standard input and hands over no file (20.12: "with those arguments and an empty standard
input"); the page's and the command line's fabulac-first doors (`enough/fabulac_first.py`) keep handing files over.
A run started here is stopped as any sandbox run is (`sandbox.stop`, `sandbox.stop_all` at the app's shutdown).
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from . import macrocosm as _mc
from . import sandbox as _sb

FABULAC_SUFFIX = ".fabulac.cosm"
SERVING_LATER = ("{name} is a service. Serving is specified in this edition and comes in a later one: enough authors "
                 "and entails services, and does not serve them yet.")
STOP_SAID = ("the person can stop a run at any moment (the page's Stop, the app's shutdown); a stopped run leaves "
             "nothing running, and its report says it was stopped")
SERVING_SAID = "a service is refused: serving comes in a later edition, so nothing is served or listens on a port"


def _root(code: Any) -> Path | None:
    p = getattr(code, "payload", code)
    root = getattr(p, "root", None)
    if isinstance(root, Path):
        return root
    if isinstance(p, (str, Path)):
        return Path(p)
    return None


def _fabulac(root: Path) -> Path:
    r = root.resolve()
    return r.parent / f"{r.name}{FABULAC_SUFFIX}"


def _doc(fab: Path) -> dict:
    d = _mc.yaml_load(fab.read_text(encoding="utf-8"))
    return d if isinstance(d, dict) else {}


def beside(code: Any) -> dict:
    """What the fabulac beside the folder says, for `only-authored` (Thym 7.3)."""
    root = _root(code)
    if root is None or not root.is_dir():
        return {"found": False, "fabulac": None, "why": "the folder is not on this disk"}
    fab = _fabulac(root)
    if not fab.is_file():
        return {"found": False, "fabulac": fab.name, "why": "no such file"}
    try:
        doc = _doc(fab)
    except Exception as e:  # noqa: BLE001 - a fabulac that cannot be read is not one to run from
        return {"found": False, "fabulac": fab.name, "why": f"it cannot be read: {e}"}
    src = doc.get("source") if isinstance(doc.get("source"), dict) else {}
    prog = doc.get("program") if isinstance(doc.get("program"), dict) else {}
    ent = doc.get("entailed") if isinstance(doc.get("entailed"), dict) else None
    out: dict = {"found": True, "fabulac": fab.name, "source": {"kind": src.get("kind")},
                 "program": {"kind": prog.get("kind"), "start": list(prog.get("start") or [])}}
    if ent is not None:
        out["entailed"] = {"path": ent.get("path"),
                           "files": [{"path": r.get("path"), "sha256": r.get("sha256")}
                                     for r in ent.get("files") or [] if isinstance(r, dict)]}
    return _mc.jsonable(out)


def _rows(res: _sb.Result) -> dict:
    g = res.guarantees or {}
    boxed = bool(res.enforced)
    mac = res.mechanism == "sandbox-exec"
    limits = {"enforced": True,
              "said": "; ".join(str(g[k]) for k in ("time", "output", "disk") if g.get(k))}
    memory = str(g.get("memory") or "")
    if mac or memory.startswith("not limited"):
        limits["unenforced"] = [f"memory: {memory}" if memory else "memory: not limited on this system"]
    else:
        limits["said"] += f"; memory: {memory}"
    return {
        "own-place": {"enforced": boxed, "said": "; ".join(str(g[k]) for k in ("reads", "writes", "processes")
                                                           if g.get(k)) or "a copy of the folder, made for the run"},
        "no-network": {"enforced": boxed, "said": str(g.get("network") or "denied")},
        "limits": limits,
        "stop": {"enforced": True, "said": STOP_SAID},
        "packages": {"enforced": boxed, "said": str(g.get("packages") or _sb.PACKAGE_SOURCE)
                     + ": nothing fetched or installed"},
        "serving": {"enforced": True, "said": SERVING_SAID},
    }


def report_of(res: _sb.Result) -> dict:
    """The host's part of `run`'s report (Thym 20.12), from a sandbox result: no floats (Thym 12.6)."""
    out: dict = {"exit": res.exit_code, "output": res.stdout, "error-output": res.stderr,
                 "cut": [n for n, cut in (("output", res.stdout_truncated), ("error-output", res.stderr_truncated))
                         if cut]}
    if res.what == "tests":
        out["tests"] = _sb.test_verdicts(res.stderr)
    out["stopped"] = {"by": res.stopped_by, "said": res.stopped} if res.stopped_by else None
    out["refused"] = list(res.refused or [])
    out["sandbox"] = {"by": res.mechanism, "rows": _rows(res)}
    out["milliseconds"] = int(round(float(res.wall_time or 0) * 1000))
    return out


def run(code: Any, as_word: str, arguments: Any = ()) -> dict:
    """One run of an authored fabulac's entailment in the sandbox: `{report}` or `{refused, reason}`."""
    root = _root(code)
    if root is None or not root.is_dir():
        return {"refused": "the folder is not on this disk, so there is nothing to run", "reason": "missing"}
    fab = _fabulac(root)
    doc = _doc(fab) if fab.is_file() else {}
    name = str(doc.get("name") or root.resolve().name)
    prog = doc.get("program") if isinstance(doc.get("program"), dict) else {}
    if as_word == "service" or (prog.get("kind") == "service" and as_word == "tool"):
        return {"refused": SERVING_LATER.format(name=name), "reason": "serving"}
    src = doc.get("source") if isinstance(doc.get("source"), dict) else {}
    try:
        r = _sb.prepare(root, source_kind=str(src.get("kind") or ""))
    except _sb.Refusal as e:
        return {"refused": e.sentence, "reason": e.reason}
    try:
        if as_word == "tests":
            res = _sb.run_tests(r)
        else:
            res = _sb.run_tool(r, [str(a) for a in arguments or ()], stdin=b"")
    except _sb.Refusal as e:
        return {"refused": e.sentence, "reason": e.reason}
    finally:
        _sb.discard(r)
    return {"report": report_of(res)}


def thym_engine() -> SimpleNamespace:
    """The engine `sandbox` a Thym run reaches as `ctx.engines["sandbox"]` (`thym_host.SIBLING_ENGINES`)."""
    return SimpleNamespace(beside=beside, run=run)


__all__ = ["SERVING_LATER", "beside", "report_of", "run", "thym_engine"]
