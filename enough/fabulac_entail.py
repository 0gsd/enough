"""An authored fabulac entailed as its program, landed beside it (0.8, fabulac-first F3 and F4: pins section 4;
MacroCOSM OES 18.4.1 `entailed`, 18.4.7; Thym 20.7's second program).

`run_entail(project, fab)` runs `defaults/thym/entail-authored-python.thym` (Thym 20.7's block, byte for byte): `give
code: entail f as code` (the move `thym.moves.authored_code.entail_authored`: the sources a model writes file by
file, and by rules the tests from the cases, `pyproject.toml`, `RUNNING.md`, `ENTAILED.md`) and `give manual: entail f
as manual` (the catem). What it gives lands all at once: the folder at its stable path, `<name>/` beside
`<name>.fabulac.cosm` (not a `.cshort-<stamp>/`), the catem as a compile's, and the fabulac records the entailment in
its catalog's `entailed` key, file by file (`{path, sha256, from, brief}`), and the catem in `catems:`.

**Nothing a person edited is written over.** When the folder is there already, every file in it must be one the
fabulac's `entailed` key recorded, with the bytes recorded; otherwise the entailment is refused, naming the files, and
nothing is written (keeping in step, which chooses between write over, keep and take back, is the next lane's,
W3-F5). A file the new entailment no longer writes, and the last one did, is removed.

Nothing here runs the entailment: `enough/sandbox.py` does, and the routes lane (W4-F6) wires it. A decompiled
fabulac is refused here: its code is compiled to a cshort (`fabulac_job.run_compile`), read and never run.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import logging
import re
import shutil
from pathlib import Path
from typing import Any, Callable

from . import fabulac_job as _fj
from . import macrocosm as _macrocosm
from . import thym_api as _thym_api
from . import thym_host as _host
from .canon_derive import DeriveCancelled
from .thym import Refusal
from .thym.moves import authored_code as _ac

log = logging.getLogger("enough.fabulac_entail")

PROGRAM_FILE = "entail-authored-python.thym"
PROGRAM = "entail-authored-python"
JOB_KIND = "fabulac-entail"
_TOP_KEY = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):(.*)$")


class EntailError(_fj.BuildError):
    """A refusal before anything is written, with the HTTP status a route answers it with."""


def entailed_path(fab: Path) -> Path:
    """The entailment's folder: `tally/` beside `tally.fabulac.cosm`."""
    return fab.parent / _fj.compiled_name(fab)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def hand_edits(fab: Path, doc: dict | None = None) -> list[str]:
    """The files of the entailment's folder the fabulac did not write as they are now: a file whose bytes differ from
    the recorded sha256, or a file it did not record (sorted, relative to the folder). Empty when the folder is
    absent or in step with its record."""
    folder = entailed_path(fab)
    if not folder.is_dir():
        return []
    doc = doc if doc is not None else _fj._load(fab)
    ent = doc.get("entailed") if isinstance(doc.get("entailed"), dict) else {}
    rec = {str(f.get("path")): str(f.get("sha256")) for f in ent.get("files") or [] if isinstance(f, dict)}
    out = []
    for p in sorted(x for x in folder.rglob("*") if x.is_file() or x.is_symlink()):
        rel = p.relative_to(folder).as_posix()
        if "__pycache__" in rel.split("/"):
            continue
        if p.is_symlink() or rec.get(rel) != _sha(p):
            out.append(rel)
    return out


def record_entailed(text: str, entailed: dict) -> str:
    """The fabulac's text with its catalog's `entailed` key set (replaced when there; made just before `nodes:` when
    absent, 18.4.1's order); every other byte kept. Raises EntailError when the result would not read back as the same
    volume with that key."""
    before = _macrocosm.yaml_load(text)
    if not isinstance(before, dict):
        raise EntailError("the fabulac does not read as a volume; nothing was recorded", 409)
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith(("\n", "\r")):
        lines[-1] += nl
    tops = [(i, m.group(1)) for i, line in enumerate(lines) if (m := _TOP_KEY.match(line.lstrip("﻿")))]
    block = _macrocosm.dump({"entailed": entailed}).replace("\n", nl)
    here = next((i for i, k in tops if k == "entailed"), None)
    if here is not None:
        j = here + 1
        while j < len(lines) and (lines[j][:1] in (" ", "\t", "-") or not lines[j].strip()):
            j += 1
        lines[here:j] = [block]
    else:
        at = next((i for i, k in tops if k == "nodes"), len(lines))
        while at > 0 and lines[at - 1].lstrip().startswith("#"):
            at -= 1
        lines[at:at] = [block]
    out = "".join(lines)
    after = _macrocosm.yaml_load(out)
    if (not isinstance(after, dict) or _plain(after.get("entailed")) != _plain(entailed)
            or {k: v for k, v in after.items() if k != "entailed"}
            != {k: v for k, v in before.items() if k != "entailed"}):
        raise EntailError("the entailment could not be recorded in the fabulac's entailed key without changing it; "
                          "it was left as it was", 409)
    return out


def _plain(v: Any) -> Any:
    return _macrocosm.yaml_load(_macrocosm.dump({"v": v}))["v"] if v is not None else None


def _authored(fab: Path) -> dict:
    doc = _fj._load(fab)
    src = doc.get("source") if isinstance(doc.get("source"), dict) else {}
    if src.get("kind") != _ac.AUTHORED:
        raise EntailError(f"{fab.name} is not authored: its code is compiled to a cshort, read and never run", 409)
    return doc


def run_entail(project_dir: Path, fab: Path, *, mode: str = "model", why: str = "", route: str = "local",
               model: str | None = None, calls: int | None = None, llm_url: str | None = None,
               runtime: Callable | None = None, complete: Callable | None = None,
               progress: Callable[[dict], Any] | None = None, should_stop: Callable[[], bool] | None = None,
               now: dt.datetime | None = None) -> dict:
    """The entailment's work (blocking). Returns `{fabulac, entailed, files, catems, run, trace, mode, route, model,
    removed, recorded, message}`; raises EntailError before anything runs (not authored, a hand edit, no model) and
    RuntimeError in the refusal's words when the run does not land."""
    from .thym import plan as _plan
    from .thym import run as _run
    from .thym.values import digest_path
    project_dir = Path(project_dir)
    doc = _authored(fab)
    edited = hand_edits(fab, doc)
    if edited:
        raise EntailError(f"{entailed_path(fab).name}/ holds files the fabulac did not write as they are: "
                          + ", ".join(edited[:8]) + ("…" if len(edited) > 8 else "")
                          + ". Nothing was written: keep them, write over them, or take them back first", 409)
    prog = _fj.program_path(PROGRAM_FILE)
    checked = _fj._checked(prog)
    rows = [{"name": "f", "type": "fabula", "path": str(fab), "sha256": digest_path(fab)}]
    use_model = mode == "model"
    if use_model:
        plan, info = _host.plan_for(checked, rows, route=route, model=model, llm_url=llm_url, inputs_root=project_dir)
    else:
        plan, info = _plan.plan(checked, rows, inputs_root=project_dir), None
    if isinstance(plan, Refusal):
        raise RuntimeError(f"the entailment was refused ({plan.check}): {plan.message}")
    if not use_model:
        r = _thym_api.scaffold_refusal(plan)
        no = _thym_api.asks_refusal(plan, why, route=route, program=prog)
        msg = "; ".join(x.message for x in (no, r) if x is not None) or "only a model writes code"
        raise EntailError(f"the entailment needs a model: {msg}", 409)
    r = _host.route_refusal(plan, info, calls=calls, ceiling="calls", program=prog)
    if r is not None:
        raise RuntimeError(r.message)
    make = runtime or _fj.app_runtime(project_dir, why=why, route=route, model=model, calls=calls, complete=complete)
    kw = make("entail", plan, info, "model", False, prog)
    if progress is not None:
        progress({"phase": "entailing", "message": f"entailing {fab.name} as its program"})
    t = _run.run(plan, inputs_root=project_dir, program=prog, should_stop=should_stop,
                 **({"now": now} if now is not None else {}), **kw)
    if isinstance(t, Refusal):
        raise RuntimeError(f"the entailment was refused ({t.check}): {t.message}")
    if not t.landed:
        r = t.refusal
        if r is not None and r.check == "cancelled":
            raise DeriveCancelled("cancelled; nothing was written")
        raise RuntimeError(f"the entailment was refused ({r.check}): {r.message}" if r else
                           "the entailment was refused")
    return land(project_dir, fab, t, route=route)


def land(project_dir: Path, fab: Path, t: Any, *, route: str = "local") -> dict:
    """What a landed run gives, put in place: the folder written into `<name>/` (files the last entailment wrote
    and this one does not, removed), the manual catem beside the fabulac, and both recorded in the fabulac."""
    code = Path(t.outputs["code"])
    dst = entailed_path(fab)
    when = t.started if isinstance(t.started, dt.datetime) else dt.datetime.now(dt.timezone.utc)
    when = when.astimezone(dt.timezone.utc)
    at = when.replace(microsecond=0)
    models = sorted({str(r.get("engine"))[len("model:"):] for r in t.records
                     if str(r.get("engine", "")).startswith("model:")})
    by = ", ".join(models) if models else "rules"
    env = t.environment if isinstance(t.environment, dict) else {}
    run_route = (env.get("route") or route) if models else None
    doc = _fj._load(fab)
    old = doc.get("entailed") if isinstance(doc.get("entailed"), dict) else {}
    files = {p.relative_to(code).as_posix(): p for p in sorted(code.rglob("*")) if p.is_file()}
    rows = []
    for rel, p in sorted(files.items()):
        if rel == _ac.ENTAILED:
            continue
        rows.append({"path": rel, "sha256": _sha(p)})
    listed = _ac.read_entailed(files[_ac.ENTAILED].read_text(encoding="utf-8"))["rows"]
    rec_files = []
    for row in rows:
        m = listed.get(row["path"], {})
        frm = str(m.get("from") or "rules")
        rec_files.append({"path": row["path"], "sha256": row["sha256"],
                          "from": frm if frm == "rules" else [x.strip() for x in frm.split(",") if x.strip()],
                          "brief": m.get("brief")})
    rec_files.append({"path": _ac.ENTAILED, "sha256": _sha(files[_ac.ENTAILED]), "from": "rules",
                      "brief": _ac.rules_digest([r["sha256"] for r in rows])})
    removed = []
    for f in old.get("files") or []:
        rel = str(f.get("path")) if isinstance(f, dict) else ""
        if rel and rel not in files and (dst / rel).is_file():
            (dst / rel).unlink()
            removed.append(rel)
    for rel, p in files.items():
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f".{target.name}.entailing")
        shutil.copyfile(p, tmp)
        tmp.replace(target)
    stamp = when.strftime("%Y-%m-%d-%H%M")
    name = _fj.compiled_name(fab)
    out: dict = {"fabulac": _fj.rel_of(project_dir, fab), "entailed": _fj.rel_of(project_dir, dst) + "/",
                 "files": len(files), "run": t.run_id, "trace": str(t.path), "mode": "model" if models else "rules",
                 "route": run_route, "model": by if models else None, "catems": [], "removed": removed}
    entailed: dict = {"path": f"{dst.name}/", "at": at, "run": t.run_id, "files": rec_files}
    if isinstance(old.get("kept"), list) and old["kept"]:
        entailed["kept"] = old["kept"]
    pairs = []
    if "manual" in t.outputs:
        cdst = _fj.free_path(fab.parent, f"{name}{_fj.CATEM_MARK}{stamp}", ".md")
        pairs.append((Path(t.outputs["manual"]), cdst))
        out["catems"].append({"path": _fj.rel_of(project_dir, cdst), "depth": "manual"})
    _thym_api.copy_all(pairs)
    recorded = True
    try:
        text = fab.read_bytes().decode("utf-8")
        for _s, cdst in pairs:
            text = _fj.record_entry(text, "catems", _fj._catem_entry(cdst, at, by, out["mode"], run_route, "manual"))
        text = record_entailed(text, entailed)
        _fj.write_atomic(fab, text)
    except (OSError, UnicodeDecodeError, _fj.BuildError) as e:
        recorded = False
        log.warning("fabulac: wrote the entailment beside %s but could not record it (%s)", fab.name, e)
    out["recorded"] = recorded
    out["message"] = (f"wrote {dst.name}/ ({len(files)} files)" + (", " + ", ".join(Path(d).name for _s, d in pairs)
                                                                    if pairs else "")
                      + ("" if recorded else f"; {fab.name} could not record it"))
    return out


__all__ = ["EntailError", "JOB_KIND", "PROGRAM", "PROGRAM_FILE", "entailed_path", "hand_edits", "land",
           "record_entailed", "run_entail"]
