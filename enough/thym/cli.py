"""The command line (docs/THYM.md 11.3).

    python -m enough.thym check     <program.thym>                     compile only; prints the refusal or "ok"
    python -m enough.thym plan      <program.thym> <inputs…>           compile and plan; prints the atem and cost
    python -m enough.thym run       <program.thym> <inputs…> [--rules]
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

**Inputs** (THYM.md 11.3). An input is `name=path`, a folder's path included (`repo=tool/`). An argument is
`name=path` when the text before its first `=` is a name the program takes, and a bare path otherwise; a program that
takes exactly one input takes a bare path (`run tighten.thym notes.md`), and a program of several refuses one ("tidy
takes story and voice; give each as name=path"). The rule is the command line's, for both grammars.

**The model** (THYM.md 23). `plan` and `run` take `--model local` (the default: the machine's model), `--model cloud`
(the cloud model the host names) or `--model cloud:<the provider's model id>`, and `--calls N`, a ceiling on the run's
model requests. The route goes to the host, which alone reaches a model; `plan` prints the plan's `models` line under
its atem ("61 model calls, at most 183, on the cloud (openrouter: vendor/large-model)"). Without the host a plan that
asks a model on the cloud is refused, since nothing here can reach one.

**Outputs.** A run lists every output as it landed, one per line, a folder output as a directory with its files
counted.
"""
from __future__ import annotations

import argparse
import importlib
import re
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


_NAME_LIKE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


def said_and(names: list[str]) -> str:
    """`a`, `a and b`, `a, b and c`."""
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def parse_model(spec: str | None) -> tuple[str, str | None] | Refusal:
    """`--model` as `(route, model id or None)`: `local` (the default), `cloud`, or `cloud:<the provider's model id>`
    (THYM.md 11.3, 23.1); a refusal in words for anything else."""
    s = (spec or "local").strip()
    if s == "local":
        return "local", None
    if s == "cloud":
        return "cloud", None
    if s.startswith("cloud:") and s[len("cloud:"):].strip():
        return "cloud", s[len("cloud:"):].strip()
    return Refusal("plan", "model", f"--model is local, cloud or cloud:<model id>, not {spec!r}")


def _takes(program: Path) -> tuple[str, list[tuple[str, str]]]:
    from enough.thym.run import ProgramInfo
    info = ProgramInfo.from_source(program.read_text(encoding="utf-8-sig"))
    return info.name or program.stem, list(info.takes)


def _pairs(items: list[str], program: Path | None = None, names: list[str] | None = None,
           lists: set[str] | None = None) -> dict[str, str | list[str]] | Refusal:
    """The inputs from the command line (THYM.md 11.3): `name=path` when the text before the first `=` is a name the
    program takes, else a bare path, which stands for the program's one input. Without a program (a plan's inputs),
    `names` are the names it takes; with neither, every argument must be `name=path`. An input whose type is a list
    (`lists`, read from the program's `takes` when it is given) is given by its name once per member, in order
    (`xs=a.md xs=b.md`), and is a list of paths here; several bare paths are the members of a program's one input
    when that input is a list. Any other input is given once."""
    prog = None
    if program is not None:
        try:
            prog, takes = _takes(program)
        except (OSError, UnicodeDecodeError, ValueError):
            takes = []
        names = [n for n, _ in takes]
        lists = {n for n, t in takes if _is_list(t)}
    lists = lists or set()
    out: dict[str, str | list[str]] = {}
    bare: list[str] = []
    for it in items:
        k, eq, v = it.partition("=")
        k = k.strip()
        if eq and (names is None or k in names):
            if not v.strip():
                return Refusal("plan", "input", f"{k}= names no path")
            if k in lists:
                out.setdefault(k, [])
                out[k].append(v.strip())        # type: ignore[union-attr]
                continue
            if k in out and out[k] != v.strip():
                return Refusal("plan", "input", f"{k} is given twice ({out[k]} and {v.strip()}); give each input once")
            out[k] = v.strip()
        elif eq and _NAME_LIKE.match(k) and not Path(it).exists():
            who = prog or "the program"
            return Refusal("plan", "input", f"{who} takes no {k}; it takes {said_and(names) if names else 'nothing'}")
        else:
            bare.append(it)
    if bare:
        who = prog or "the program"
        if names is None:
            return Refusal("plan", "input", f"an input is name=path, not {bare[0]!r}")
        if not names:
            return Refusal("plan", "input", f"{who} takes nothing; run it without {bare[0]}")
        if len(names) > 1:
            return Refusal("plan", "input", f"{who} takes {said_and(names)}; give each as name=path")
        if names[0] in lists:
            out[names[0]] = list(out.get(names[0]) or []) + bare
            return out
        if len(bare) > 1 or names[0] in out:
            return Refusal("plan", "input", f"{who} takes one input, {names[0]}; give it once")
        out[names[0]] = bare[0]
    return out


def _is_list(typ: Any) -> bool:
    return isinstance(typ, str) and (typ == "list" or typ.startswith("list of "))


def _inputs(program: Path, pairs: dict[str, str | list[str]]) -> list[dict]:
    """The plan's inputs from `name=path` pairs: each with its type (from the program's `takes`) and its sha256 (a
    folder's tree digest for a folder input); a list input's members each so, in order, under `members`."""
    from enough.thym.values import digest_path, guess_type, list_member_type

    def digest(p: Path, typ: str) -> str:
        return (digest_path(p, typ if typ == "folder" else None) or "") if p.exists() else ""

    takes = dict(_takes(program)[1])
    out = []
    for name, raw in pairs.items():
        if isinstance(raw, list):
            typ = takes.get(name) or "list"
            member = list_member_type(typ)
            members = [{"path": r, "sha256": digest(Path(r), member)} for r in raw]
            out.append({"name": name, "type": typ, "path": raw[0] if raw else "", "members": members})
            continue
        p = Path(raw)
        typ = takes.get(name) or (guess_type(p) if p.exists() else "text")
        row = {"name": name, "type": typ, "path": raw}
        row["sha256"] = digest(p, typ)
        out.append(row)
    return out


def _host() -> Any | None:
    return _module(HOST_MODULE)


def _make_plan(program: Path, pairs: dict[str, str], *, route: str = "local",
               model: str | None = None) -> tuple[dict | Refusal | None, dict | None]:
    """`(plan, info)`: the plan, with the `models` block of the route when the host is here and the plan asks a
    model; `info` is the route as the host read it (None when nothing asks, or without the host)."""
    checked = _checked(program)
    if checked is None or isinstance(checked, Refusal):
        return checked, None
    mods = _compiler("plan")
    if mods is None:
        return None, None
    rows = _inputs(program, pairs)
    host = _host()
    if host is not None and hasattr(host, "plan_for"):
        return host.plan_for(checked, rows, route=route, model=model)
    plan = mods[0].plan(checked, rows)
    return plan, None


def models_line(plan: dict) -> str | None:
    """The plan's `models` block as one line (THYM.md 23.2): "61 model calls, at most 183, on the cloud (openrouter:
    vendor/large-model)", "3 model calls, at most 9, on this machine (g40-04)"; with the steps whose count is open
    named after it. None for a plan that asks no model."""
    m = plan.get("models") if isinstance(plan.get("models"), dict) else None
    if not m:
        return None
    calls, at_most = int(m.get("calls") or 0), int(m.get("at_most") or 0)
    model = m.get("model")
    if m.get("route") == "cloud":
        who = ": ".join(str(x) for x in (m.get("provider"), model) if x)
        where = f"on the cloud ({who})" if who else "on the cloud"
    else:
        where = f"on this machine ({model})" if model else "on this machine"
    line = f"{calls} model call{'s' if calls != 1 else ''}, at most {at_most}, {where}"
    opened = list(m.get("calls_open") or [])
    if opened:
        nodes = {n.get("id"): n for n in plan.get("nodes") or [] if isinstance(n, dict)}
        named = [str((nodes.get(i) or {}).get("name") or i) for i in opened]
        line += f"; and more that cannot be counted before it runs ({said_and(named)})"
    return line


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


def _host_kwargs(rules: bool, *, route: str | None = None, model: str | None = None, calls: int | None = None,
                 info: dict | None = None, program: Any = None) -> dict:
    """What the host gives a run: the coprocessor on the route, the preflight, the environment, the engines, the
    ceiling. Without the host, only the ceiling."""
    host = _host()
    if host is None:
        return {"calls": calls} if calls is not None else {}
    if route is None:
        return host.runtime_kwargs(rules=rules)
    return host.runtime_kwargs(rules=rules, route=route, model=model, calls=calls, info=info, ceiling="--calls",
                               program=program)


def _route_refusal(plan: dict, info: dict | None, route: str, calls: int | None, program: Any) -> Refusal | None:
    """The plan-time refusal of the route (the host's), or, without the host, a cloud plan that asks refused: nothing
    here reaches a model."""
    host = _host()
    if host is not None and hasattr(host, "route_refusal"):
        return host.route_refusal(plan, info, calls=calls, ceiling="--calls", program=program)
    asks = (plan.get("estimate") or {}).get("asks") if isinstance(plan.get("estimate"), dict) else 0
    if route == "cloud" and asks:
        return Refusal("plan", "cloud", "the cloud is not open for this run: no host here reaches a cloud model")
    return None


def _output_lines(t: Any) -> list[str]:
    """Every output of a landed run, one line each, as it landed: a folder output as a directory, its files counted."""
    out = []
    for name, path in t.outputs.items():
        p = Path(path)
        if p.is_dir():
            n = sum(1 for f in p.rglob("*") if f.is_file())
            out.append(f"{name}: {p}/ (a folder of {n} file{'s' if n != 1 else ''})")
        else:
            out.append(f"{name}: {p}")
    return out


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


def _route_args(args: argparse.Namespace) -> tuple[str, str | None, int | None] | Refusal:
    got = parse_model(getattr(args, "model", None))
    if isinstance(got, Refusal):
        return got
    calls = getattr(args, "calls", None)
    if calls is not None and calls < 1:
        return Refusal("plan", "calls", f"--calls is a ceiling of at least 1 model call, not {calls}")
    return got[0], got[1], calls


def cmd_plan(args: argparse.Namespace) -> int:
    route = _route_args(args)
    if isinstance(route, Refusal):
        _say(str(route))
        return 2
    src = Path(args.program)
    pairs = _pairs(args.inputs, src if src.is_file() else None)
    if isinstance(pairs, Refusal):
        _say(str(_in_file(pairs, src)))
        return 2
    plan, info = _make_plan(src, pairs, route=route[0], model=route[1])
    if plan is None:
        return 1
    if isinstance(plan, Refusal):
        _say(str(plan))
        return 2
    _say(_plan_atem(plan))
    line = models_line(plan)
    if line:
        _say(line + (f"; ceiling {route[2]}" if route[2] is not None else ""))
    r = _route_refusal(plan, info, route[0], route[2], src)
    if r is not None:
        _say(str(_in_file(r, src)))
        return 2
    if args.out:
        from enough.thym.trace import write_atomic
        write_atomic(Path(args.out), mc.dump(plan).encode("utf-8"))
        _say(f"wrote {args.out}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    from enough.thym import run as R
    from enough.thym.trace import Trace
    root = _root(args)
    if args.replay:
        kw = _host_kwargs(args.rules)
        kw.pop("root", None)
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
    route = _route_args(args)
    if isinstance(route, Refusal):
        _say(str(route))
        return 2
    src = Path(args.program)
    info: dict | None = None
    if src.name.endswith(".cosm"):
        try:
            plan = mc.yaml_load(mc.read_text(src))
        except Exception as e:  # noqa: BLE001
            _say(str(Refusal("plan", "plan", f"{src} could not be read: {e}")))
            return 2
        if not isinstance(plan, dict) or plan.get("kind") != "plan":
            _say(str(Refusal("plan", "plan", f"{src} is not a plan volume")))
            return 2
        names = [str(r.get("name")) for r in plan.get("inputs") or [] if isinstance(r, dict)]
        lists = {str(r.get("name")) for r in plan.get("inputs") or [] if isinstance(r, dict)
                 and (_is_list(r.get("type")) or isinstance(r.get("members"), list))}
        pairs = _pairs(args.inputs, names=names, lists=lists)
        if isinstance(pairs, Refusal):
            _say(str(_in_file(pairs, src)))
            return 2
        for row in plan.get("inputs") or []:
            if not isinstance(row, dict) or row.get("name") not in pairs:
                continue
            given = pairs[row["name"]]
            if isinstance(given, list):              # a list's members, in order, where the plan recorded them
                ms = row.get("members") if isinstance(row.get("members"), list) else []
                if len(given) != len(ms):
                    _say(str(_in_file(Refusal("plan", "input", f"{row['name']} has {len(ms)} member"
                                              f"{'s' if len(ms) != 1 else ''} in the plan, and {len(given)} "
                                              f"{'was' if len(given) == 1 else 'were'} given; give each, in order, or "
                                              "plan it again"), src)))
                    return 2
                for m, g in zip(ms, given):
                    if isinstance(m, dict):
                        m["path"] = str(Path(g).absolute())
                row["path"] = ms[0]["path"] if ms and isinstance(ms[0], dict) else row.get("path")
            else:
                row["path"] = str(Path(given).absolute())
        program: Any = Path(args.program_items) if args.program_items else None
        inputs_root = Path(args.inputs_root) if args.inputs_root else Path.cwd()
    else:
        pairs = _pairs(args.inputs, src if src.is_file() else None)
        if isinstance(pairs, Refusal):
            _say(str(_in_file(pairs, src)))
            return 2
        plan, info = _make_plan(src, pairs, route=route[0], model=route[1])
        if plan is None:
            return 1
        if isinstance(plan, Refusal):
            _say(str(plan))
            return 2
        program = src
        inputs_root = Path(args.inputs_root) if args.inputs_root else Path.cwd()
    if _host() is None:
        r = _route_refusal(plan, info, route[0], route[2], program)
        if r is not None:
            _say(str(_in_file(r, src)))
            return 2
    kw = _host_kwargs(args.rules, route=route[0], model=route[1], calls=route[2], info=info,
                      program=program if isinstance(program, Path) and program.suffix == ".thym" else None)
    kw.pop("root", None)
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
    for line in _output_lines(t):
        _say(line)
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
    routes = argparse.ArgumentParser(add_help=False)
    routes.add_argument("--model", metavar="ROUTE", default="local",
                        help="local (the default: this machine's model), cloud (the cloud model the host names), or "
                             "cloud:<the provider's model id>")
    routes.add_argument("--calls", metavar="N", type=int, default=None,
                        help="a ceiling on the run's model requests (a cloud plan whose count is open needs one)")
    inputs_help = ("name=path, one per input the program takes (a folder's path too), and once per member for a list "
                   "(xs=a.md xs=b.md); a bare path for a program of one")
    p = sub.add_parser("plan", parents=[common, routes], help="compile and plan; prints the plan's atem and cost")
    p.add_argument("program")
    p.add_argument("inputs", nargs="*", help=inputs_help)
    p.add_argument("--out", help="also write the plan volume here")
    p.set_defaults(fn=cmd_plan)
    p = sub.add_parser("run", parents=[common, routes], help="run a program, a plan, or replay a recorded run")
    p.add_argument("program", nargs="?", help="a .thym program, or a .plan.cosm plan")
    p.add_argument("inputs", nargs="*", help=inputs_help)
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
