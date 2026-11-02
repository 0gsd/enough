"""Traces: what a run did, one record per node, written as a `thym/1` volume of kind `trace` (docs/THYM.md 12.3,
17.1, 17.3, 17.4).

A trace's catalog names the run, the program (name and sha256), the plan's sha256, the environment (enough's version,
the model's id and window, agent-free or not, the machine's memory band), when the run started and ended (UTC), and its
outcome. Its root item `R:trace/<run-id>` lists the records, the outcome and, for a refused run, `stopped_at`; each
`R:record/<n>` is node `n`'s: the node, the move, the digests of its inputs and outputs (`{name, sha256, path}`), the
engine (`code` for a deterministic move, `rules` for a scaffold, `model:<id>` for the model, `skipped` for a node of the
branch not taken), attempts, tokens, seconds, and every check with its verdict. A record's `node` is a reference, so the
trace carries its plan's `R:node` items too, and every reference resolves inside the one file: the trace lints clean on
its own.

Written as `<root>/runs/<run-id>/<run-id>.trace.cosm`, atomically, with the plan beside it as `<run-id>.plan.cosm`.
`read(run_id)` reads one back; `Trace.atem()` is the one line a listing shows ("ran open-house on meadow in 0 s on code:
7 steps, all checks green").

Standalone: the standard library, PyYAML and `enough.macrocosm`.
"""
from __future__ import annotations

import datetime as _dt
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from enough import macrocosm as mc
from enough.thym import MINICOSM, Refusal
from enough.thym.values import Value, plain


def utc(t: _dt.datetime | None) -> str | None:
    """A time as a trace writes it: UTC, to the second, `2026-11-01T10:42:00Z`."""
    if t is None:
        return None
    if t.tzinfo is None:
        t = t.astimezone()
    return t.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(s: Any) -> _dt.datetime | None:
    if isinstance(s, _dt.datetime):
        return s if s.tzinfo else s.replace(tzinfo=_dt.timezone.utc)
    if not isinstance(s, str) or not s:
        return None
    try:
        return _dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc)
    except ValueError:
        return None


def write_atomic(path: Path, data: bytes) -> None:
    """Write through a dotfile beside the target and `os.replace`, so a reader never sees half a file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


def runs_dir(root: Path) -> Path:
    return Path(root) / "runs"


def node_number(node_id: Any) -> str:
    """`R:node/7` -> `7`."""
    s = str(node_id or "")
    return s.rsplit("/", 1)[-1] if "/" in s else s


def record(node: dict, *, run_id: str, move: str, engine: str, inputs: list | None = None,
           outputs: list | None = None, attempts: int = 0, tokens: int = 0, seconds: int = 0,
           checks: list | None = None, state: str | None = None, refusal: Refusal | None = None,
           tries: list | None = None) -> dict:
    """One `R:record/<n>` item for node `n` of the plan (THYM.md 17.3); `refusal` when the run stopped here; `tries`
    each attempt that failed its checks, kept so that a refused node explains all its tries (12.3)."""
    n = node_number(node.get("id"))
    checks = list(checks or [])
    failed = [c for c in checks if not c.get("ok")]
    if engine == "skipped":
        summary = "Not run: the other branch was taken."
    elif refusal is not None:
        summary = f"Refused: {refusal.check}, {refusal.message}".rstrip(".") + "."
    elif failed:
        summary = f"Refused: {failed[0]['name']} does not hold ({failed[0].get('why') or 'no reason given'})."
    else:
        summary = (f"{engine}, {attempts} attempt{'s' if attempts != 1 else ''}, "
                   f"{len(checks)} check{'s' if len(checks) != 1 else ''} green.")
    rec = {"id": f"R:record/{n}", "type": "record", "name": str(node.get("name") or node.get("move") or n),
           "summary": summary, "node": str(node.get("id")), "move": str(move or node.get("move") or ""),
           "inputs": list(inputs or []), "outputs": list(outputs or []), "engine": engine,
           "attempts": int(attempts), "tokens": int(tokens), "seconds": int(seconds), "checks": checks}
    if state:
        rec["state"] = state
    if tries:
        rec["tries"] = [dict(x) for x in tries]
    rec["provenance"] = {"mode": "derived", "sources": [f"{run_id}.plan.cosm#{node.get('id')}"], "confidence": 1}
    return rec


def digest_row(name: str, value: Value, path: str | None = None) -> dict:
    row = {"name": str(name), "sha256": value.sha256}
    p = path if path is not None else (str(value.path) if value.path is not None else None)
    if p:
        row["path"] = p
    return row


@dataclass
class Trace:
    """What a run did. `outcome` is `landed` or `refused`; `refusal` says why a refused run stopped and `stopped_at`
    which record. `outputs` are the landed files by name, `values` the given values (with `made`). `extra` holds what
    a replay needs (`inputs_root`, `rules`, `replay_of`, and `engines`, the engines whose calls the run recorded, so a
    replay answers them from the record: `engines.py`); `replay` a replay's comparison with the recorded run. A
    record's `tokens` are its requests' and the model calls its engines made (THYM.md 12.3)."""
    run_id: str
    dir: Path
    program: dict
    plan_sha256: str
    environment: dict
    started: _dt.datetime
    ended: _dt.datetime | None = None
    outcome: str = "refused"
    records: list = field(default_factory=list)
    nodes: list = field(default_factory=list)
    inputs: list = field(default_factory=list)
    stopped_at: str | None = None
    refusal: Refusal | None = None
    outputs: dict = field(default_factory=dict)
    values: dict = field(default_factory=dict)
    extra: dict = field(default_factory=dict)
    replay: dict | None = None

    @property
    def path(self) -> Path:
        return Path(self.dir) / f"{self.run_id}.trace.cosm"

    @property
    def landed(self) -> bool:
        return self.outcome == "landed"

    def seconds(self) -> int:
        if self.ended is None:
            return 0
        return max(0, int((self.ended - self.started).total_seconds()))

    def engine(self) -> str:
        models = sorted({str(r.get("engine"))[len("model:"):] for r in self.records
                         if str(r.get("engine", "")).startswith("model:")})
        if models:
            return ", ".join(models)
        if any(r.get("engine") == "rules" for r in self.records):
            return "rules"
        return "code"

    def atem(self) -> str:
        """The trace's one line (THYM.md 12.3)."""
        prog = self.program.get("name") or "the program"
        names = [Path(str(i.get("path") or i.get("name"))).name for i in self.inputs] or ["nothing"]
        ran = [r for r in self.records if r.get("engine") != "skipped"]
        head = f"ran {prog} on {', '.join(names)}"
        if self.outcome == "landed":
            return (f"{head} in {self.seconds()} s on {self.engine()}: {len(ran)} step{'s' if len(ran) != 1 else ''}, "
                    "all checks green")
        r = self.refusal
        where = f"; refused at node {node_number(self.stopped_at)}" if self.stopped_at else "; refused"
        why = f": {r.check}, {r.message}" if r is not None else ""
        return f"{head}{where} after {self.seconds()} s{why}"

    def to_volume(self) -> dict:
        """The trace as a `thym/1` volume of kind `trace` (THYM.md 17.1, 17.3)."""
        rid = self.run_id
        prog = self.program.get("name") or "program"
        root: dict[str, Any] = {
            "id": f"R:trace/{rid}", "type": "trace", "name": f"{prog} run {rid}", "summary": self.atem(),
            "records": [r["id"] for r in self.records], "outcome": self.outcome}
        if self.stopped_at:
            root["stopped_at"] = self.stopped_at
        if self.refusal is not None:
            r = self.refusal
            root["refusal"] = {"stage": r.stage, "check": r.check, "message": r.message,
                               **({"line": r.line} if r.line else {})}
        for k in ("replay_of", "inputs_root", "rules", "made_run", "engines"):
            if self.extra.get(k) not in (None, False, ""):
                root[k] = self.extra[k]
        root["provenance"] = {"mode": "derived", "sources": [f"{rid}.plan.cosm"], "confidence": 1}
        return {
            "oes": MINICOSM, "kind": "trace", "id": f"thym/{rid}", "name": f"{prog} run {rid}",
            "program": {"name": self.program.get("name"), "sha256": self.program.get("sha256")},
            "plan": {"sha256": self.plan_sha256},
            "environment": dict(self.environment),
            "started": utc(self.started), "ended": utc(self.ended), "outcome": self.outcome,
            "nodes": [root, *plain(self.records), *plain(self.nodes)],
        }


def write(trace: Trace) -> Path:
    """Write the trace volume beside the run's plan, atomically."""
    path = trace.path
    write_atomic(path, mc.dump(trace.to_volume()).encode("utf-8"))
    return path


def default_root() -> Path:
    """Where runs live: `ENOUGH_THYM_ROOT`, else `~/enough/thym/` (THYM.md 11.3)."""
    env = os.environ.get("ENOUGH_THYM_ROOT")
    return Path(env).expanduser() if env and env.strip() else Path.home() / "enough" / "thym"


def find(run_id: str, *, root: Path | None = None) -> Path | None:
    """The trace file of a run under the root, or None."""
    p = runs_dir(root or default_root()) / run_id / f"{run_id}.trace.cosm"
    return p if p.is_file() else None


def read(run_id: str, *, root: Path | None = None) -> dict | Refusal:
    """A run's trace volume as a mapping, or a refusal when there is none."""
    path = find(run_id, root=root)
    if path is None:
        return Refusal("run", "trace", f"no trace of run {run_id} under {runs_dir(root or default_root())}")
    return load(path)


def load(path: Path) -> dict | Refusal:
    try:
        data = mc.yaml_load(mc.read_text(path))
    except Exception as e:  # noqa: BLE001 - an unreadable trace is a refusal
        return Refusal("run", "trace", f"{path} could not be read: {e}")
    if not isinstance(data, dict) or data.get("kind") != "trace":
        return Refusal("run", "trace", f"{path} is not a trace volume")
    return data


def root_item(volume: dict) -> dict:
    """A trace volume's `R:trace` item."""
    return next((n for n in volume.get("nodes") or [] if isinstance(n, dict) and n.get("type") == "trace"), {})


def records_of(volume: dict) -> list[dict]:
    return [n for n in volume.get("nodes") or [] if isinstance(n, dict) and n.get("type") == "record"]


def show(volume: dict) -> str:
    """A trace as text: its atem, then one row per record (id, move, engine, attempts, seconds), as the `trace`
    renderer's table lists them (THYM.md 17.5)."""
    lines = [str(root_item(volume).get("summary") or volume.get("name") or "a trace")]
    for r in records_of(volume):
        bad = [c.get("name") for c in r.get("checks") or [] if not c.get("ok")]
        lines.append(f"  {r.get('id'):<14} {str(r.get('move')):<10} {str(r.get('engine')):<16} "
                     f"{r.get('attempts', 0)} attempt(s) {r.get('seconds', 0)} s"
                     + (f"  failed: {', '.join(map(str, bad))}" if bad else ""))
    return "\n".join(lines)
