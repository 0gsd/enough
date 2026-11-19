"""`python -m enough.fabulac`: an authored fabulac from the command line, with no server running (0.8, fabulac-first
F6: pins section 4, the second of three doors).

Every command calls the plain function the route of the same name calls (`enough/fabulac_first.py`), in this process,
on the project folder given (`--project`, else the folder you are in). Output is a few lines for a person, or the
whole answer as JSON (`--json`) for a script. Exit status: 0 done (tests passed, the tool exited 0, no check
failed); 1 done, and it failed (a test, a check, the tool's own non-zero status); 2 refused, nothing written.

Only `begin` with `--model` and `entail` and `take-back` ask a model (`--model local`, this machine's llama-server at
`--llm-url`; or `cloud`, through enough's gate); everything else runs by rules. `test` and `run` run in enough's
sandbox only; Ctrl-C stops the run.

    python -m enough.fabulac starters
    python -m enough.fabulac begin tally --starter tool --licence MIT
    python -m enough.fabulac check tally
    python -m enough.fabulac entail tally --model local
    python -m enough.fabulac test tally
    python -m enough.fabulac run tally -- count notes.md --hand notes.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from . import fabulac_first as FF


def _model_kw(args: argparse.Namespace, project: Path) -> dict:
    """`{mode, complete, route, model, calls, llm_url}` for a command that may ask a model."""
    from . import thym_host as H
    route = (args.model or "").strip().lower()
    if not route:
        return {"mode": "rules"}
    model = None
    if route.startswith("cloud:"):
        route, model = "cloud", route[len("cloud:"):] or None
    if route not in H.ROUTES:
        raise FF.FirstError(f"--model is local or cloud (or cloud:<model id>), not {args.model!r}")
    llm_url = args.llm_url or os.environ.get("ENOUGH_LLM_URL") or None
    return {"mode": "model", "route": route, "model": model, "calls": args.calls, "llm_url": llm_url,
            "complete": H.route_complete(route, model=model, llm_url=llm_url, project_dir=project)}


def _answers(args: argparse.Namespace) -> list[dict]:
    a: dict[str, Any] = {"question": args.question, "says": args.says or ""}
    for flag, key in (("unknown", "dont_know"), ("declined", "declined"), ("skip", "skip")):
        if getattr(args, flag):
            a[key] = True
    return [a]


def _fields(pairs: list[str]) -> dict:
    out: dict[str, Any] = {}
    for p in pairs or ():
        k, sep, v = p.partition("=")
        if not sep or not k.strip():
            raise FF.FirstError(f"--field is name=value (the value as JSON, or as words), not {p!r}")
        try:
            out[k.strip()] = json.loads(v)
        except ValueError:
            out[k.strip()] = v
    return out


def _lines(cmd: str, out: dict) -> list[str]:
    """A few lines for a person."""
    if cmd == "starters":
        return [f"{s['kind']}: {s['name']}: {s['line']}" for s in out["starters"]]
    if cmd == "status":
        iv = out["interview"]
        lines = [f"{out['fabulac']}: an authored {out['program'].get('kind')}; interview "
                 + ("complete" if iv["complete"] else f"next {iv['next']}" + (f", stage {iv['stage']}" if iv["stage"]
                                                                               else ""))]
        lines += [f"  {q['id']}: {q['asks']}" for q in iv["shown"]]
        ent = out.get("entailment")
        lines.append("not entailed yet" if not ent else f"entailment {ent['folder']}: "
                     + ("in step" if not (ent["tell"] or ent["edited"]) else
                        "; ".join(f"{k}: {', '.join(ent[k])}" for k in ("tell", "edited", "kept") if ent[k])))
        return lines
    if cmd == "check":
        lines = [f"{out['fabulac']}: {'no errors' if out['ok'] else str(len(out['errors'])) + ' error(s)'}, "
                 f"{len(out['warnings'])} warning(s)"]
        lines += [f"  {e}" for e in out["errors"] + out["warnings"]]
        if out["uncovered"]:
            lines.append("  requirements no case shows: " + ", ".join(out["uncovered"]))
        return lines
    if cmd == "moved":
        if not out["entailed"]:
            return [f"{out['folder']} is not entailed yet"]
        return [f"{f['path']}: {f['state']}" for f in out["files"]]
    if cmd in ("test", "run"):
        lines = [out["message"] + f" (run {out['run']}, {out['wall_time']:.1f}s)"]
        if cmd == "run" and out.get("stdout"):
            lines.append(out["stdout"].rstrip("\n"))
        if out.get("stderr") and (cmd == "test" or not out["ok"]):
            lines.append(out["stderr"].rstrip("\n"))
        return lines
    if cmd == "parts-moved":
        return ["moved: " + ", ".join(out["moved"]) if out["moved"] else "no part moved"]
    if cmd == "head":
        return [f"made {out['head']} over {', '.join(out['parts'])}"]
    if cmd == "begin" and out.get("waiting"):
        return [out.get("message") or ""] + [f"  {q['id']}: {q['asks']}" for q in out["waiting"]]
    return [str(out.get("message") or json.dumps(out, ensure_ascii=False))]


def _failed(cmd: str, out: dict) -> bool:
    if cmd in ("test", "run"):
        return not out.get("ok")
    if cmd == "check":
        return not out.get("ok")
    return False


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m enough.fabulac",
                                description="An authored fabulac from the command line, with no server running.")
    p.add_argument("--project", default=".", help="the project folder (default: here)")
    p.add_argument("--json", action="store_true", help="print the whole answer as JSON")
    sub = p.add_subparsers(dest="cmd", required=True)

    def model_opts(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--model", metavar="ROUTE", help="ask a model: local, cloud, or cloud:<model id>")
        sp.add_argument("--llm-url", help="the local model's address (default ENOUGH_LLM_URL, else enough's own)")
        sp.add_argument("--calls", type=int, help="a ceiling on model calls")

    sub.add_parser("starters", help="list the starters: a tool, a library, a service")
    sp = sub.add_parser("begin", help="begin an authored fabulac, or take its interview up again")
    sp.add_argument("path")
    sp.add_argument("--kind", default="tool", choices=FF.KINDS)
    sp.add_argument("--licence")
    sp.add_argument("--brief", help="a markdown brief in the project")
    sp.add_argument("--by", help="who is authoring it")
    sp.add_argument("--starter", choices=FF.KINDS, help="begin from a starter of this kind")
    model_opts(sp)
    sp = sub.add_parser("answer", help="record the person's answer to one question")
    sp.add_argument("path")
    sp.add_argument("question")
    sp.add_argument("says", nargs="?", default="")
    for f in ("unknown", "declined", "skip"):
        sp.add_argument(f"--{f}", action="store_true")
    for name, what in (("status", "where it stands"), ("check", "its checks"), ("moved", "what moved, file by file"),
                       ("test", "run its entailed tests in the sandbox"), ("parts-moved", "which parts of a head moved")):
        sub.add_parser(name, help=what).add_argument("path")
    sp = sub.add_parser("add", help="add a requirement, decision, case or interface in your words")
    sp.add_argument("path")
    sp.add_argument("as_", metavar="as", choices=FF.ADD_AS)
    sp.add_argument("says")
    sp.add_argument("--field", action="append", default=[], metavar="NAME=VALUE")
    sp = sub.add_parser("entail", help="entail it as its program (a model writes the sources)")
    sp.add_argument("path")
    sp.add_argument("--overwrite", action="append", default=[], metavar="FILE")
    model_opts(sp)
    sp = sub.add_parser("run", help="run the tool in the sandbox: arguments after --")
    sp.add_argument("path")
    sp.add_argument("args", nargs="*")
    sp.add_argument("--stdin-file", help="a file in the project whose text is the tool's input")
    sp.add_argument("--hand", action="append", default=[], metavar="FILE", help="hand a project file over, read-only")
    for name in ("keep", "let-go"):
        sp = sub.add_parser(name, help=f"{name} files changed by hand")
        sp.add_argument("path")
        sp.add_argument("files", nargs="+")
        if name == "keep":
            sp.add_argument("--because")
    sp = sub.add_parser("take-back", help="take a hand edit back into the fabulac as questions (a model reads it)")
    sp.add_argument("path")
    sp.add_argument("file")
    model_opts(sp)
    sp = sub.add_parser("head", help="make a head fabulac over parts")
    sp.add_argument("path")
    sp.add_argument("parts", nargs="+")
    sp.add_argument("--name")
    sp.add_argument("--licence")
    sp.add_argument("--by")
    return p


def dispatch(args: argparse.Namespace) -> dict:
    project = Path(args.project).resolve()
    cmd = args.cmd
    if cmd == "starters":
        return {"starters": FF.starters()}
    if cmd == "begin":
        kw = {k: getattr(args, k) for k in ("licence", "brief", "by") if getattr(args, k)}
        if args.starter:
            return FF.begin(project, args.path, starter=args.starter, **kw)
        return FF.begin(project, args.path, kind=args.kind, **kw, **_model_kw(args, project))
    if cmd == "answer":
        return FF.answer(project, args.path, _answers(args))
    if cmd == "status":
        return FF.status(project, args.path)
    if cmd == "add":
        return FF.add(project, args.path, as_=args.as_, says=args.says, fields=_fields(args.field) or None)
    if cmd == "check":
        return FF.check(project, args.path)
    if cmd == "entail":
        kw = _model_kw(args, project)
        if kw["mode"] != "model":
            raise FF.FirstError("only a model writes sources: entail with --model local (or cloud)", 409)
        return FF.entail(project, args.path, overwrite=args.overwrite, **kw)
    if cmd == "moved":
        return FF.moved(project, args.path)
    if cmd == "test":
        return FF.test(project, args.path)
    if cmd == "run":
        stdin = ""
        if args.stdin_file:
            from . import fabulac_job as _fj
            stdin = _fj.project_path(project, args.stdin_file, what="input file").read_text(encoding="utf-8")
        return FF.run(project, args.path, args.args, stdin=stdin, hand_over=args.hand)
    if cmd == "keep":
        return FF.keep(project, args.path, args.files, because=args.because)
    if cmd == "let-go":
        return FF.let_go(project, args.path, args.files)
    if cmd == "take-back":
        kw = _model_kw(args, project)
        if kw.pop("mode") != "model":
            raise FF.FirstError("taking a file back reads it with a model: --model local (or cloud)", 409)
        return FF.take_back(project, args.path, args.file, **kw)
    if cmd == "head":
        kw = {k: getattr(args, k) for k in ("name", "licence", "by") if getattr(args, k)}
        return FF.head(project, args.path, args.parts, **kw)
    if cmd == "parts-moved":
        return FF.parts_moved(project, args.path)
    raise FF.FirstError(f"no command {cmd!r}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        out = dispatch(args)
    except KeyboardInterrupt:
        FF.stop_all()
        print("stopped", file=sys.stderr)
        return 130
    except FF.FirstError as e:
        if args.json:
            print(json.dumps({"refused": str(e), "status": e.status}, ensure_ascii=False))
        else:
            print(f"refused: {e}", file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001 - a run refused in its own words (RuntimeError from a Thym run)
        if args.json:
            print(json.dumps({"refused": str(e)}, ensure_ascii=False))
        else:
            print(f"refused: {e}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print("\n".join(_lines(args.cmd, out)))
    if args.cmd == "run" and out.get("exit_code") not in (None, 0) and not out.get("stopped_by"):
        return 1
    return 1 if _failed(args.cmd, out) else 0


__all__ = ["build_parser", "dispatch", "main"]
