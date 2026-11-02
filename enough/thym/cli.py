"""The command line (docs/THYM.md 11.3).

    python -m enough.thym check     <program.thym>                     compile only; prints the refusal or "ok"
    python -m enough.thym plan      <program.thym> <name=path…>        compile and plan; prints the atem and cost
    python -m enough.thym run       <program.thym> <name=path…> [--rules]
                                                                       run; prints the trace's atem; writes outputs
    python -m enough.thym run       <plan.cosm> [<name=path…>] --program <items.cosm|program.thym> [--inputs-root DIR]
                                                                       run a plan already made
    python -m enough.thym run       --replay <run-id>                  re-run a recorded run (THYM.md 12.4)
    python -m enough.thym trace     <run-id>                           show a trace
    python -m enough.thym enumerate <program.thym>                     write <name>.thym.cosm beside it
    python -m enough.thym compile   <name.thym.cosm>                   the file again, byte for byte
    python -m enough.thym conform   [<suite folder>]                   run the conformance suite

Every command reads `--root`, else `ENOUGH_THYM_ROOT`, else `~/enough/thym/`, for where runs live, and writes nowhere
else unless it is given the path. A refusal is printed as one line and exits 2; a conformance failure or a replay
that differs exits 1. The compiler's parts (`check`, `plan`, `enumerate`, `compile`) and enough's host (the model
coprocessor, the preflight, the agent-free switch: `enough.thym_host`) are found when they are there; the runtime
works without either, with no model.
"""
from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path
from typing import Any

from enough import macrocosm as mc
from enough.thym import Refusal

#: The module that plugs enough's engines in; absent when the package is vendored.
HOST_MODULE = "enough.thym_host"


def _say(msg: str) -> None:
    print(msg)


def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


def _module(name: str) -> Any | None:
    try:
        return importlib.import_module(name)
    except Exception:  # noqa: BLE001 - absent (vendored, or the compiler lane mid-build)
        return None


def _compiler(*names: str) -> list[Any] | None:
    mods = [_module(f"enough.thym.{n}") for n in names]
    if any(m is None for m in mods):
        _err(f"the compiler is not here: enough.thym.{', enough.thym.'.join(names)} must import")
        return None
    return mods


def _root(args: argparse.Namespace) -> Path:
    from enough.thym.trace import default_root
    return Path(args.root).expanduser() if args.root else default_root()


def _checked(path: Path) -> Any:
    mods = _compiler("parse", "check")
    if mods is None:
        return None
    parse, check = mods
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return Refusal("compile", "parse", f"{path} cannot be read: {e}", file=str(path))
    module = parse.parse(text, path=str(path))
    return module if isinstance(module, Refusal) else check.check(module)


def _pairs(items: list[str]) -> dict[str, str] | Refusal:
    out: dict[str, str] = {}
    for it in items:
        if "=" not in it:
            return Refusal("plan", "input", f"an input is name=path, not {it!r}")
        k, _, v = it.partition("=")
        out[k.strip()] = v.strip()
    return out


def _inputs(program: Path, pairs: dict[str, str]) -> list[dict]:
    """The plan's inputs from `name=path` pairs: each with its type (from the program's `takes`) and its sha256."""
    from enough.thym.run import ProgramInfo
    from enough.thym.values import digest_path, guess_type
    takes = dict(ProgramInfo.from_source(program.read_text(encoding="utf-8-sig")).takes)
    out = []
    for name, raw in pairs.items():
        p = Path(raw)
        row = {"name": name, "type": takes.get(name) or (guess_type(p) if p.exists() else "text"), "path": raw}
        row["sha256"] = (digest_path(p) or "") if p.exists() else ""
        out.append(row)
    return out


def _make_plan(program: Path, pairs: dict[str, str]) -> dict | Refusal | None:
    checked = _checked(program)
    if checked is None or isinstance(checked, Refusal):
        return checked
    mods = _compiler("plan")
    if mods is None:
        return None
    return mods[0].plan(checked, _inputs(program, pairs))


def plan_atem(plan: dict) -> str:
    """A plan's one line, its cost, as `plan` prints it: "<program>: 7 nodes, 3 ask a model; largest prompt 307
    tokens, output budget 300 words" (the routes and the readvisor show the same line)."""
    est = plan.get("estimate") if isinstance(plan.get("estimate"), dict) else {}
    prog = (plan.get("program") or {}).get("name") or "the program"
    n = est.get("steps", len([x for x in plan.get("nodes") or [] if isinstance(x, dict) and x.get("type") == "node"]))
    return (f"{prog}: {n} nodes, {est.get('asks', 0)} ask a model; largest prompt {est.get('largest_prompt', 0)} "
            f"tokens, output budget {est.get('output_words', 0)} words")


_plan_atem = plan_atem


def _in_file(r: Refusal | None, src: Path) -> Refusal | None:
    """A runtime refusal named after the file it is about: the program, or the plan."""
    if r is None or r.file:
        return r
    return Refusal(r.stage, r.check, r.message, line=r.line, file=str(src))


def _host_kwargs(rules: bool) -> dict:
    host = _module(HOST_MODULE)
    if host is None:
        return {}
    kw = host.runtime_kwargs(rules=rules)
    return kw


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_check(args: argparse.Namespace) -> int:
    r = _checked(Path(args.program))
    if r is None:
        return 1
    if isinstance(r, Refusal):
        _say(str(r))
        return 2
    _say("ok")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    pairs = _pairs(args.inputs)
    if isinstance(pairs, Refusal):
        _say(str(pairs))
        return 2
    plan = _make_plan(Path(args.program), pairs)
    if plan is None:
        return 1
    if isinstance(plan, Refusal):
        _say(str(plan))
        return 2
    _say(_plan_atem(plan))
    if args.out:
        from enough.thym.trace import write_atomic
        write_atomic(Path(args.out), mc.dump(plan).encode("utf-8"))
        _say(f"wrote {args.out}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    from enough.thym import run as R
    from enough.thym.trace import Trace
    root = _root(args)
    kw = _host_kwargs(args.rules)
    kw.pop("root", None)
    if args.replay:
        run_dir = root / "runs" / args.replay
        if not run_dir.is_dir():
            _say(str(Refusal("run", "replay", f"no run {args.replay} under {root / 'runs'}")))
            return 2
        t = R.replay(run_dir, root=root, inputs_root=args.inputs_root, environment=kw.get("environment"),
                     engines=kw.get("engines"))
        if isinstance(t, Refusal):
            _say(str(t))
            return 2
        _say(t.atem())
        rep = t.replay or {}
        if rep.get("identical"):
            _say(f"replayed {args.replay}: the outputs are byte-identical")
            return 0
        for d in rep.get("differences") or []:
            _err(f"differs: {d}")
        return 1
    if not args.program:
        _err("run needs a program (or a plan) and its inputs, or --replay <run-id>")
        return 2
    pairs = _pairs(args.inputs)
    if isinstance(pairs, Refusal):
        _say(str(pairs))
        return 2
    src = Path(args.program)
    if src.name.endswith(".cosm"):
        try:
            plan = mc.yaml_load(mc.read_text(src))
        except Exception as e:  # noqa: BLE001
            _say(str(Refusal("plan", "plan", f"{src} could not be read: {e}")))
            return 2
        if not isinstance(plan, dict) or plan.get("kind") != "plan":
            _say(str(Refusal("plan", "plan", f"{src} is not a plan volume")))
            return 2
        for row in plan.get("inputs") or []:
            if isinstance(row, dict) and row.get("name") in pairs:
                row["path"] = str(Path(pairs[row["name"]]).absolute())
        program: Any = Path(args.program_items) if args.program_items else None
        inputs_root = Path(args.inputs_root) if args.inputs_root else Path.cwd()
    else:
        plan = _make_plan(src, pairs)
        if plan is None:
            return 1
        if isinstance(plan, Refusal):
            _say(str(plan))
            return 2
        program = src
        inputs_root = Path(args.inputs_root) if args.inputs_root else Path.cwd()
    t = R.run(plan, inputs_root=inputs_root, root=root, rules=args.rules, program=program,
              destination=Path(args.destination) if args.destination else None, **kw)
    if isinstance(t, Refusal):
        _say(str(_in_file(t, src)))
        return 2
    assert isinstance(t, Trace)
    _say(t.atem())
    if not t.landed:
        _say(str(_in_file(t.refusal, src)))
        _say(f"trace: {t.path}")
        return 2
    for name, path in t.outputs.items():
        _say(f"{name}: {path}")
    _say(f"trace: {t.path}")
    return 0


def cmd_trace(args: argparse.Namespace) -> int:
    from enough.thym import trace as T
    vol = T.read(args.run_id, root=_root(args))
    if isinstance(vol, Refusal):
        _say(str(vol))
        return 2
    _say(T.show(vol))
    return 0


def cmd_enumerate(args: argparse.Namespace) -> int:
    mods = _compiler("enumerate")
    if mods is None:
        return 1
    en = mods[0]
    src = Path(args.program)
    vol = en.enumerate_file(src)
    if isinstance(vol, Refusal):
        _say(str(vol))
        return 2
    out = src.with_name(f"{src.stem}.thym.cosm")
    from enough.thym.trace import write_atomic
    write_atomic(out, en.dump(vol).encode("utf-8"))
    _say(f"wrote {out}")
    return 0


def cmd_compile(args: argparse.Namespace) -> int:
    mods = _compiler("enumerate")
    if mods is None:
        return 1
    try:
        data = mc.yaml_load(mc.read_text(args.volume))
    except Exception as e:  # noqa: BLE001
        _say(str(Refusal("compile", "parse", f"{args.volume} could not be read: {e}")))
        return 2
    if not isinstance(data, dict):
        _say(str(Refusal("compile", "parse", f"{args.volume} is not a program volume")))
        return 2
    sys.stdout.flush()
    sys.stdout.buffer.write(mods[0].compile_volume(data).encode("utf-8"))
    sys.stdout.flush()
    return 0


def cmd_conform(args: argparse.Namespace) -> int:
    from enough.thym import conform
    host = _module(HOST_MODULE)
    engines = host.engines() if host is not None and hasattr(host, "engines") else None
    if not engines:
        return conform.main(args.suite, root=args.root)
    rep = conform.conform(args.suite, root=args.root, engines=engines)     # the host's engines reach every replay
    for line in rep.lines:
        _say(line)
    _say(rep.summary())
    return 0 if rep.ok else 1


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", help="where runs live (default ENOUGH_THYM_ROOT, else ~/enough/thym)")
    ap = argparse.ArgumentParser(prog="python -m enough.thym",
                                 description="Thym, the MacroCOSM language: check, plan, run, trace and conform "
                                             "(docs/THYM.md 11.3).")
    sub = ap.add_subparsers(dest="command", required=True, metavar="command")
    p = sub.add_parser("check", parents=[common], help="compile only; prints the refusal or ok")
    p.add_argument("program")
    p.set_defaults(fn=cmd_check)
    p = sub.add_parser("plan", parents=[common], help="compile and plan; prints the plan's atem and cost")
    p.add_argument("program")
    p.add_argument("inputs", nargs="*", help="name=path, one per input the program takes")
    p.add_argument("--out", help="also write the plan volume here")
    p.set_defaults(fn=cmd_plan)
    p = sub.add_parser("run", parents=[common], help="run a program, a plan, or replay a recorded run")
    p.add_argument("program", nargs="?", help="a .thym program, or a .plan.cosm plan")
    p.add_argument("inputs", nargs="*", help="name=path, one per input the program takes")
    p.add_argument("--rules", action="store_true", help="run the declared scaffolds instead of the model")
    p.add_argument("--replay", metavar="RUN_ID", help="re-run a recorded run with its recorded candidates")
    p.add_argument("--program", dest="program_items", metavar="PATH",
                   help="with a plan: the program's items (.thym.cosm) or its .thym file")
    p.add_argument("--inputs-root", metavar="DIR", help="the folder input paths are relative to (default: here)")
    p.add_argument("--destination", metavar="DIR", help="also copy the output into this folder once it lands")
    p.set_defaults(fn=cmd_run)
    p = sub.add_parser("trace", parents=[common], help="show a trace")
    p.add_argument("run_id")
    p.set_defaults(fn=cmd_trace)
    p = sub.add_parser("enumerate", parents=[common], help="write <name>.thym.cosm beside the program")
    p.add_argument("program")
    p.set_defaults(fn=cmd_enumerate)
    p = sub.add_parser("compile", parents=[common], help="a program volume compiled back to its file")
    p.add_argument("volume")
    p.set_defaults(fn=cmd_compile)
    p = sub.add_parser("conform", parents=[common], help="run the conformance suite")
    p.add_argument("suite", nargs="?", help="the suite folder (default tests/fixtures/thym)")
    p.set_defaults(fn=cmd_conform)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.fn(args))
