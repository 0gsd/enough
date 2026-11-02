"""The conformance suite runner (docs/THYM.md 20; the folder is `tests/fixtures/thym/`, its README says what passing
means).

For each program under `programs/`: it compiles, enumerates to `expected/<name>/items.cosm`, compiles back byte for
byte, and plans to `expected/<name>/plan.cosm` (compared with the compiler's `plan.normalise`); these parts need the
compiler (`parse`, `check`, `enumerate`, `plan`) and are skipped, with a line saying so, while it is not there. A
deterministic program's run is compared with `expected/<name>/outputs/` byte for byte when that folder holds recorded
outputs, and every recorded run under `replay/<name>/` is replayed to its recorded outputs; these parts need only the
runtime and the moves. Every `bad/` program must be refused at the stage, check and line its first line names.

`conform(suite)` returns a `Report`; `main(suite)` prints it and returns 1 on any failure, 0 otherwise (a skip is not
a failure). Runs land in a temporary root unless one is given, never in the user's.

Standalone: the standard library, PyYAML and `enough.macrocosm`.
"""
from __future__ import annotations

import datetime as _dt
import importlib
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from enough import macrocosm as mc

HOST_MODULE = "enough.thym_host"           # enough's side: the engines a recorded run needs to replay; imported by name only


def _module(name: str) -> Any | None:
    """A module by name, or None when it is not there (the package stays free of host imports)."""
    try:
        return importlib.import_module(name)
    except Exception:  # noqa: BLE001
        return None


# Deterministic programs run with this clock, so recorded outputs that carry an epoch stay comparable (THYM.md 20.3).
FIXTURE_NOW = _dt.datetime(2026, 11, 1, 12, 0, tzinfo=_dt.timezone.utc)
from enough.thym import Refusal
from enough.thym.values import plain

SUITE = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "thym"
_REFUSED = re.compile(r"^-- refused: (compile|plan|run) ([a-z0-9-]+) line (\d+)\s*$")


@dataclass
class Report:
    passed: list = field(default_factory=list)
    failed: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    lines: list = field(default_factory=list)

    def add(self, kind: str, what: str) -> None:
        {"pass": self.passed, "FAIL": self.failed, "skip": self.skipped}[kind].append(what)
        self.lines.append(f"{kind:4}  {what}")

    @property
    def ok(self) -> bool:
        return not self.failed

    def summary(self) -> str:
        return f"conform: {len(self.passed)} passed, {len(self.failed)} failed, {len(self.skipped)} skipped"


def compiler() -> tuple[dict, str | None]:
    """The compiler's modules that import (`parse`, `check`, `enumerate`, `plan`), and why the rest do not."""
    mods, why = {}, []
    for name in ("parse", "check", "enumerate", "plan"):
        try:
            mods[name] = importlib.import_module(f"enough.thym.{name}")
        except Exception as e:  # noqa: BLE001 - absent, or mid-build in the compiler lane
            why.append(f"{name}: {type(e).__name__}: {e}")
    return mods, ("; ".join(why) or None)


def _without(mapping: Any, *keys: str) -> Any:
    if isinstance(mapping, dict):
        return {k: v for k, v in plain(mapping).items() if k not in keys}
    return mapping


def _first_difference(a: Any, b: Any, path: str = "") -> str:
    if isinstance(a, dict) and isinstance(b, dict):
        for k in list(a) + [k for k in b if k not in a]:
            if k not in a or k not in b:
                return f"{path}.{k}" if path else str(k)
            d = _first_difference(a[k], b[k], f"{path}.{k}" if path else str(k))
            if d:
                return d
        return ""
    if isinstance(a, list) and isinstance(b, list):
        for i, (x, y) in enumerate(zip(a, b)):
            label = x.get("id") if isinstance(x, dict) and x.get("id") else i
            d = _first_difference(x, y, f"{path}[{label}]")
            if d:
                return d
        return "" if len(a) == len(b) else f"{path} (length {len(a)} against {len(b)})"
    return "" if a == b else (path or "the value")


def _compile_parts(rep: Report, name: str, src: Path, exp: Path, mods: dict, why: str | None) -> None:
    need = ("parse", "check", "enumerate", "plan")
    if any(m not in mods for m in need):
        rep.add("skip", f"{name}: compile, enumerate, round trip and plan (the compiler is not here yet: {why})")
        return
    parse, check, en, pl = (mods[m] for m in need)
    text = src.read_bytes().decode("utf-8")
    try:
        module = parse.parse(text, path=str(src))
        checked = module if isinstance(module, Refusal) else check.check(module)
    except Exception as e:  # noqa: BLE001 - a compiler that raises fails conformance, it does not stop the suite
        rep.add("FAIL", f"{name}: compile raised {type(e).__name__}: {e}")
        return
    if isinstance(checked, Refusal):
        rep.add("FAIL", f"{name}: refused: {checked}")
        return
    rep.add("pass", f"{name}: compiles")
    try:
        items = en.enumerate_file(src)
    except Exception as e:  # noqa: BLE001
        items = Refusal("compile", "enumerate", f"{type(e).__name__}: {e}")
    if isinstance(items, Refusal):
        rep.add("FAIL", f"{name}: enumerate refused: {items}")
    else:
        want = mc.yaml_load(mc.read_text(exp / "items.cosm")) if (exp / "items.cosm").is_file() else None
        if want is None:
            rep.add("skip", f"{name}: enumerate (no expected/{name}/items.cosm)")
        else:
            d = _first_difference(_without(items, "built"), _without(want, "built"))
            rep.add("FAIL" if d else "pass", f"{name}: enumerates to expected/{name}/items.cosm"
                                              + (f" (first difference at {d})" if d else ""))
        try:
            back = en.compile_volume(items)
        except Exception as e:  # noqa: BLE001
            back = f"\0{type(e).__name__}: {e}"
        same = isinstance(back, str) and back.encode("utf-8") == src.read_bytes()
        rep.add("pass" if same else "FAIL", f"{name}: compiles back to programs/{name}.thym byte for byte")
    plan_file = exp / "plan.cosm"
    if not plan_file.is_file():
        rep.add("skip", f"{name}: plan (no expected/{name}/plan.cosm)")
        return
    want_plan = mc.yaml_load(mc.read_text(plan_file))
    try:
        got = pl.plan(checked, list(want_plan.get("inputs") or []))
        if isinstance(got, Refusal):
            rep.add("FAIL", f"{name}: plan refused: {got}")
            return
        d = _first_difference(pl.normalise(got), pl.normalise(want_plan))
    except Exception as e:  # noqa: BLE001
        rep.add("FAIL", f"{name}: plan raised {type(e).__name__}: {e}")
        return
    rep.add("FAIL" if d else "pass", f"{name}: plans to expected/{name}/plan.cosm"
                                      + (f" (first difference at {d})" if d else ""))


def _run_parts(rep: Report, name: str, suite: Path, exp: Path, root: Path, kw: dict) -> None:
    from enough.thym import run as _run
    plan_file, items_file, outs = exp / "plan.cosm", exp / "items.cosm", exp / "outputs"
    if plan_file.is_file():
        plan = mc.yaml_load(mc.read_text(plan_file))
        asks = (plan.get("estimate") or {}).get("asks") if isinstance(plan.get("estimate"), dict) else None
        recorded = sorted(p for p in outs.rglob("*") if p.is_file()) if outs.is_dir() else []
        if asks:
            pass                                    # a model-backed program conforms by replay, below
        elif not recorded:
            rep.add("skip", f"{name}: run (no recorded outputs under expected/{name}/outputs/ yet)")
        else:
            t = _run.run(plan, inputs_root=suite, root=root, program=items_file if items_file.is_file() else None,
                         record=False, **{**kw, "now": kw.get("now") or FIXTURE_NOW})
            if isinstance(t, Refusal):
                rep.add("FAIL", f"{name}: run refused at plan time: {t}")
            elif not t.landed:
                rep.add("FAIL", f"{name}: run refused: {t.refusal}")
            else:
                landed = t.dir / "outputs"
                bad = [p.relative_to(outs).as_posix() for p in recorded
                       if not (landed / p.relative_to(outs)).is_file()
                       or (landed / p.relative_to(outs)).read_bytes() != p.read_bytes()]
                rep.add("FAIL" if bad else "pass", f"{name}: run lands expected/{name}/outputs/ byte for byte"
                                                    + (f" (differs: {', '.join(bad)})" if bad else ""))
    for run_dir in sorted((suite / "replay" / name).glob("*")) if (suite / "replay" / name).is_dir() else []:
        if not run_dir.is_dir():
            continue
        if not _records_engines(run_dir) and not (kw.get("engines") or {}).get("feed"):
            # a run recorded before engine calls were (THYM.md 12.4) replays with live engines, and its prompts carry
            # FEED's lookups; one that recorded them replays anywhere, with no dictionary and no engine
            rep.add("skip", f"{name}: replay {run_dir.name} (recorded before engine calls were, its prompts carry FEED "
                            "lookups and this host has no FEED engine; set ENOUGH_DICT_SOURCE, or run `python -m "
                            "enough.thym conform`)")
            continue
        t = _run.replay(run_dir, root=root, inputs_root=suite, **kw)
        what = f"{name}: replay {run_dir.name}"
        if isinstance(t, Refusal):
            rep.add("FAIL", f"{what} refused: {t}")
        elif not (t.replay or {}).get("identical"):
            rep.add("FAIL", f"{what}: {'; '.join((t.replay or {}).get('differences') or ['outputs differ'])}")
        else:
            rep.add("pass", f"{what} re-runs to its recorded outputs")


def _records_engines(run_dir: Path) -> bool:
    """Whether a recorded run recorded its engine calls: its trace's root item names `engines` (`engines.py`)."""
    from enough.thym import trace as _trace
    from enough.thym.engines import recorded_names
    found = sorted(run_dir.glob("*.trace.cosm"))
    tv = _trace.load(found[0]) if found else None
    return isinstance(tv, dict) and recorded_names(_trace.root_item(tv)) is not None


def _bad_parts(rep: Report, suite: Path, mods: dict, why: str | None) -> None:
    bad = sorted((suite / "bad").glob("*.thym")) if (suite / "bad").is_dir() else []
    if not bad:
        return
    if "parse" not in mods or "check" not in mods:
        rep.add("skip", f"bad/: {len(bad)} programs to refuse (the compiler is not here yet: {why})")
        return
    for p in bad:
        text = p.read_bytes().decode("utf-8")
        mt = _REFUSED.match(text.split("\n", 1)[0])
        if not mt:
            rep.add("FAIL", f"bad/{p.name}: its first line does not say where it must be refused")
            continue
        stage, chk, line = mt.group(1), mt.group(2), int(mt.group(3))
        try:
            r = mods["parse"].parse(text, path=str(p))
            if not isinstance(r, Refusal):
                r = mods["check"].check(r)
        except Exception as e:  # noqa: BLE001
            rep.add("FAIL", f"bad/{p.name}: the compiler raised {type(e).__name__}: {e}")
            continue
        if not isinstance(r, Refusal):
            rep.add("FAIL", f"bad/{p.name}: compiled; it must be refused at {stage} {chk} line {line}")
        elif (r.stage, r.check, r.line) != (stage, chk, line):
            rep.add("FAIL", f"bad/{p.name}: refused at {r.stage} {r.check} line {r.line}, "
                            f"not {stage} {chk} line {line}")
        else:
            rep.add("pass", f"bad/{p.name}: refused at {stage} {chk} line {line}")


def conform(suite: Path | str | None = None, *, root: Path | str | None = None, **run_kw: Any) -> Report:
    """Run the suite at `suite` (default: the repository's `tests/fixtures/thym/`). `run_kw` reaches `run` and
    `replay` (`moves=`, `checks=`, `decls=`, `coprocessor=` for a test)."""
    suite = Path(suite or SUITE).absolute()
    rep = Report()
    if run_kw.get("engines") is None:                    # the host's engines, so a recorded run can replay here too
        host = _module(HOST_MODULE)
        if host is not None and hasattr(host, "engines"):
            try:
                run_kw["engines"] = host.engines()
            except Exception:  # noqa: BLE001 - no host engines: the replay of a model-backed run then says so
                pass
    if not (suite / "programs").is_dir():
        rep.add("FAIL", f"{suite} holds no programs/ folder")
        return rep
    mods, why = compiler()
    with tempfile.TemporaryDirectory(prefix="thym-conform-") as tmp:
        runs_root = Path(root) if root else Path(tmp)
        for src in sorted((suite / "programs").glob("*.thym")):
            name = src.stem
            exp = suite / "expected" / name
            _compile_parts(rep, name, src, exp, mods, why)
            _run_parts(rep, name, suite, exp, runs_root, run_kw)
        _bad_parts(rep, suite, mods, why)
    return rep


def main(suite: Path | str | None = None, *, root: Path | str | None = None,
         out: Callable[[str], Any] = print) -> int:
    rep = conform(suite, root=root)
    for line in rep.lines:
        out(line)
    out(rep.summary())
    return 0 if rep.ok else 1
