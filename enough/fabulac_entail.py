"""An authored fabulac entailed as its program, landed beside it (0.8, fabulac-first F3 and F4: pins section 4;
MacroCOSM OES 18.4.1 `entailed`, 18.4.7; Thym 20.7's second program).

`run_entail(project, fab)` runs `defaults/thym/entail-authored-python.thym` (Thym 20.7's block, byte for byte): `give
code: entail f as code` (the move `thym.moves.authored_code.entail_authored`: the sources a model writes file by
file, and by rules the tests from the cases, `pyproject.toml`, `RUNNING.md`, `ENTAILED.md`) and `give manual: entail f
as manual` (the catem). What it gives lands all at once: the folder at its stable path, `<name>/` beside
`<name>.fabulac.cosm` (not a `.cshort-<stamp>/`), the catem as a compile's, and the fabulac records the entailment in
its catalog's `entailed` key, file by file (`{path, sha256, from, brief}`), and the catem in `catems:`.

**Keeping in step** (MacroCOSM OES 18.4.1; Thym 20.11). The `entailed` key is the fingerprint: per file the sha256
of the bytes written and the `brief` digest of what it was told from. `step_state` reads the folder against it, file
by file (in step, moved, edited by hand, gone, kept, new); an entailment done again tells only the moved, gone and new
files (the move gets the rest from the host's `entailment` engine and they land byte for byte).

**Nothing a person edited is written over without their word.** A file edited by hand (bytes not as recorded, or not
recorded at all) refuses the entailment, named file by file, and nothing is written, until the person chooses: write
over it (`run_entail(overwrite=[…])`), keep it (`keep`: an `N:decision` "kept by hand" and an entry under
`entailed.kept`, left out of every entailment until `let_go`), or take it back (`take_back`: the file read against
the fabulac by the read stage, `read_by_model`, and what it adds put to the person as take-back questions). A file the
new entailment no longer writes, and the last one did, is removed.

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
from typing import Any, Callable, Iterable

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


def _on_disk(folder: Path) -> dict[str, str]:
    """The entailment's folder as it is: relative path -> sha256 (a symbolic link is never read: it reads as one
    that differs from any record). `__pycache__` is the interpreter's, not the entailment's."""
    out: dict[str, str] = {}
    if not folder.is_dir():
        return out
    for p in sorted(x for x in folder.rglob("*") if x.is_file() or x.is_symlink()):
        rel = p.relative_to(folder).as_posix()
        if "__pycache__" in rel.split("/"):
            continue
        out[rel] = "a symbolic link" if p.is_symlink() else _sha(p)
    return out


def _entailed_of(doc: dict) -> dict:
    return doc.get("entailed") if isinstance(doc.get("entailed"), dict) else {}


def _kept_of(ent: dict) -> dict[str, str]:
    """`kept` as {path: the N:decision that records it}."""
    return {str(k.get("path")): str(k.get("decision") or "") for k in ent.get("kept") or []
            if isinstance(k, dict) and k.get("path")}


def hand_edits(fab: Path, doc: dict | None = None) -> list[str]:
    """The files of the entailment's folder the fabulac did not write as they are now, and nobody chose to keep: a
    file whose bytes differ from the recorded sha256, or a file it did not record (sorted, relative to the folder).
    Empty when the folder is absent or in step with its record."""
    folder = entailed_path(fab)
    if not folder.is_dir():
        return []
    doc = doc if doc is not None else _fj._load(fab)
    ent = _entailed_of(doc)
    rec = {str(f.get("path")): str(f.get("sha256")) for f in ent.get("files") or [] if isinstance(f, dict)}
    kept = _kept_of(ent)
    return [rel for rel, sha in _on_disk(folder).items() if rec.get(rel) != sha and rel not in kept]


# ---------------------------------------------------------------------------
# Keeping in step (MacroCOSM OES 18.4.1, "Fresh and stale, for an authored fabulac"; Thym 20.11)
# ---------------------------------------------------------------------------

#: The states a file of the entailment is read in, file by file, against the fabulac's `entailed` key; `new` is a
#: file the fabulac would have told that no entailment wrote yet.
STATES = ("in step", "moved", "edited by hand", "gone", "kept", "new")


def step_state(fab: Path, doc: dict | None = None) -> dict:
    """The entailment read against its record, file by file (18.4.1's four states, with `kept` and `new`):
    `{folder, entailed, files: [{path, state}], in-step, moved, edited, gone, kept, new, tell}`, each list sorted.

    - in step: bytes as recorded, and the brief computed again from the fabulac is the recorded one;
    - moved: bytes as recorded, the brief not (an item it was told from changed; or the fabulac no longer tells it);
    - edited (by hand): bytes not as recorded, or a file the entailment did not record;
    - gone: recorded, and not in the folder;
    - kept: changed by hand and kept, under `kept` with its `N:decision`;
    - new: told by the fabulac now, never written.

    `tell` is what an entailment done again asks for: the moved, gone and new files the fabulac tells now.
    `ENTAILED.md` is written again whenever anything is; it is in step while its bytes are as recorded. A file taken
    back (recorded with `from: []`) that the fabulac does not tell is in step while its bytes are."""
    from enough.fabulac_head import which_moved
    doc = doc if doc is not None else _fj._load(fab)
    cat = {k: v for k, v in doc.items() if k != "nodes"}
    items = [x for x in doc.get("nodes") or [] if isinstance(x, dict)]
    ent = _entailed_of(doc)
    folder = entailed_path(fab)
    recs = {str(f.get("path")): f for f in ent.get("files") or [] if isinstance(f, dict) and f.get("path")}
    kept = _kept_of(ent)
    disk = _on_disk(folder)
    now = {p: v["brief"] for p, v in _ac.briefs(cat, items).items()}
    by_bytes = which_moved({p: str(r.get("sha256")) for p, r in recs.items()}, disk)
    same = [p for p in by_bytes["in-step"]]
    rec_brief = {}
    for p in same:
        r = recs[p]
        if p == _ac.ENTAILED or (r.get("from") == [] and p not in now):
            continue
        rec_brief[p] = r.get("brief") if isinstance(r.get("brief"), str) else None
    by_brief = which_moved(rec_brief, {p: now.get(p) for p in rec_brief})
    state: dict[str, str] = {}
    for p in same:
        state[p] = "in step"
    for p in by_brief["moved"] + by_brief["gone"] + by_brief["unread"]:
        state[p] = "moved"
    for p in by_bytes["moved"] + by_bytes["new"]:
        state[p] = "edited by hand"
    for p in by_bytes["gone"]:
        state[p] = "gone"
    for p in now:
        if p not in state:
            state[p] = "new"
    for p in kept:
        if p in state or p in recs:
            state[p] = "kept"
    order = sorted(state, key=lambda s: s.encode("utf-8"))
    pick = {s: [p for p in order if state[p] == s] for s in STATES}
    tell = [p for p in order if p in now and state[p] in ("moved", "gone", "new")]
    return {"folder": f"{folder.name}/", "entailed": bool(recs), "files": [{"path": p, "state": state[p]} for p in order],
            "in-step": pick["in step"], "moved": pick["moved"], "edited": pick["edited by hand"],
            "gone": pick["gone"], "kept": pick["kept"], "new": pick["new"], "tell": tell}


def _held(fab: Path, state: dict) -> Callable[[], dict]:
    """The host's `entailment` engine for one entailment done again (`authored_code.HELD_ENGINE`): the texts of the
    files it leaves as they are, in step or kept by hand, and the kept paths, which it never asks again."""
    folder = entailed_path(fab)
    texts: dict[str, str] = {}
    for p in state["in-step"] + state["kept"]:
        f = folder / p
        if not f.is_file() or f.is_symlink():          # ENTAILED.md too: its footer's who, when nothing is asked
            continue
        try:
            texts[p] = f.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
    answer = {"texts": texts, "kept": list(state["kept"])}

    def held() -> dict:
        return answer
    return held


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
               now: dt.datetime | None = None, overwrite: Iterable[str] = ()) -> dict:
    """The entailment's work (blocking). Returns `{fabulac, entailed, files, catems, run, trace, mode, route, model,
    removed, recorded, told, message}`; raises EntailError before anything runs (not authored, a hand edit, no
    model) and RuntimeError in the refusal's words when the run does not land.

    Done again, it tells only what moved (`step_state`'s `tell`): the files in step and the files kept by hand are
    handed to the move as they are (the host's `entailment` engine) and land byte for byte; `told` lists the files
    whose bytes changed. A file edited by hand refuses the entailment, named, unless it is in `overwrite` (the
    person's word to write over it: told again, or removed when the entailment does not write it), kept (`keep`) or
    taken back (`take_back`)."""
    from .thym import plan as _plan
    from .thym import run as _run
    from .thym.values import digest_path
    project_dir = Path(project_dir)
    doc = _authored(fab)
    over = {str(p) for p in overwrite}
    state = step_state(fab, doc)
    edited = [p for p in state["edited"] if p not in over]
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
    kw["engines"] = {**dict(kw.get("engines") or {}), _ac.HELD_ENGINE: _held(fab, state)}
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
    return land(project_dir, fab, t, route=route, overwrite=over)


def land(project_dir: Path, fab: Path, t: Any, *, route: str = "local", overwrite: Iterable[str] = ()) -> dict:
    """What a landed run gives, put in place: the folder written into `<name>/` (files the last entailment wrote
    and this one does not, removed), the manual catem beside the fabulac, and both recorded in the fabulac. A file
    kept by hand is never written or removed; a file taken back that the entailment does not write stays, recorded as
    it is; an unrecorded file the person said to write over is removed when the entailment does not write it."""
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
    kept = _kept_of(old)
    before = _on_disk(dst)
    removed = []
    for f in old.get("files") or []:
        rel = str(f.get("path")) if isinstance(f, dict) else ""
        if not rel or rel in files or rel in kept:
            continue
        if f.get("from") == [] and before.get(rel) == f.get("sha256"):
            rec_files.append(dict(f))                  # taken back, and not told by the fabulac: it stays as it is
            continue
        if (dst / rel).is_file():
            (dst / rel).unlink()
            removed.append(rel)
    for rel in sorted(set(overwrite) - set(files) - set(kept)):
        if rel in before and (dst / rel).is_file() and not any(r["path"] == rel for r in rec_files):
            (dst / rel).unlink()                       # the person's word: written over by nothing
            removed.append(rel)
    rec_files.sort(key=lambda r: _ac.path_key(r["path"]))
    told = []
    for rel, p in files.items():
        if rel in kept:
            continue                                   # kept by hand: never written over
        target = dst / rel
        if before.get(rel) != _sha(p):
            told.append(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f".{target.name}.entailing")
        shutil.copyfile(p, tmp)
        tmp.replace(target)
    stamp = when.strftime("%Y-%m-%d-%H%M")
    name = _fj.compiled_name(fab)
    out: dict = {"fabulac": _fj.rel_of(project_dir, fab), "entailed": _fj.rel_of(project_dir, dst) + "/",
                 "files": len(files), "run": t.run_id, "trace": str(t.path), "mode": "model" if models else "rules",
                 "route": run_route, "model": by if models else None, "catems": [], "removed": removed,
                 "told": sorted(told, key=lambda s: s.encode("utf-8"))}
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


# ---------------------------------------------------------------------------
# A hand edit, resolved: written over (`run_entail(overwrite=…)`), kept, or taken back
# ---------------------------------------------------------------------------

KEPT_PREFIX = _ac.KEPT_DECISION                         # N:decision/kept-by-hand-<file>: told from by no source


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower() or "file"


def _edited_only(fab: Path, doc: dict, paths: Iterable[str], what: str) -> tuple[dict, list[str]]:
    state = step_state(fab, doc)
    paths = [str(p) for p in paths]
    if not paths:
        raise EntailError(f"name the files to {what}", 409)
    wrong = [p for p in paths if p not in state["edited"]]
    if wrong:
        raise EntailError(f"{', '.join(wrong)} {'is' if len(wrong) == 1 else 'are'} not edited by hand in "
                          f"{state['folder']}: nothing to {what}", 409)
    return state, paths


def _save(fab: Path, twin: Any, entailed: dict) -> None:
    text = record_entailed(twin.render(), entailed)
    _fj.write_atomic(fab, text)


def keep(project_dir: Path, fab: Path, paths: Iterable[str], *, because: str | None = None,
         by: str = "the person", at: Any = None) -> dict:
    """Keep files edited by hand (MacroCOSM OES 18.4.1): each gets an `N:decision` "kept by hand" in the fabulac and
    an entry `{path, decision}` under `entailed.kept`, and is left out of every later entailment (never asked again,
    never written over) until the person lets it go (`let_go`). `ENTAILED.md` cannot be kept: it is the
    entailment's own account. Returns `{kept: [{path, decision}], message}`."""
    from . import dialectic as _dl
    doc = _authored(fab)
    paths = [str(p) for p in paths]
    if _ac.ENTAILED in paths:
        raise EntailError(f"{_ac.ENTAILED} is the entailment's own account of what it wrote: write over it, or "
                          "entail again", 409)
    _state, paths = _edited_only(fab, doc, paths, "keep")
    twin = _dl.open_twin(fab)
    led = twin.ledger
    taken = led.ids()
    ent = dict(_entailed_of(twin.doc))
    kept = [dict(k) for k in ent.get("kept") or [] if isinstance(k, dict)]
    day = _dl.now(at).date().isoformat()
    folder = entailed_path(fab).name
    made = []
    for p in paths:
        base, n = KEPT_PREFIX + _slug(p), 2
        did = base
        while did in taken:
            did, n = f"{base}-{n}", n + 1
        taken.add(did)
        item = {"id": did, "type": "decision", "name": f"Kept by hand: {p}",
                "summary": f"{folder}/{p} was changed by hand on {day}, and kept as it is: it is left out of entailing "
                           "until it is let go.",
                "chose": f"keep {folder}/{p} as changed by hand", "over": "entailing it again from the fabulac",
                "stance": "axiom",
                "provenance": {"mode": "manual", "sources": [f"{by}, keeping a hand edit"], "confidence": 1}}
        if because:
            item["because"] = because
        led.add(item)
        kept = [k for k in kept if k.get("path") != p] + [{"path": p, "decision": did}]
        made.append({"path": p, "decision": did})
    ent["kept"] = sorted(kept, key=lambda k: _ac.path_key(str(k["path"])))
    _save(fab, twin, ent)
    return {"kept": made, "message": f"kept {', '.join(paths)} as changed by hand"}


def let_go(project_dir: Path, fab: Path, paths: Iterable[str]) -> dict:
    """Let kept files go: each leaves `entailed.kept`, its `N:decision` is retired (it stays as the record of the
    choice), and its brief is forgotten, so the next entailment tells it again (a file whose bytes are not the ones
    recorded is a hand edit again, and asks the person's word first). Returns `{released, message}`."""
    from . import dialectic as _dl
    _authored(fab)
    twin = _dl.open_twin(fab)
    ent = dict(_entailed_of(twin.doc))
    kept = _kept_of(ent)
    paths = [str(p) for p in paths]
    wrong = [p for p in paths if p not in kept]
    if not paths or wrong:
        raise EntailError(f"{', '.join(wrong) or 'nothing'} is not kept by hand: nothing to let go", 409)
    for d in twin.ledger.items:
        if d.get("id") in {kept[p] for p in paths}:
            d["status"] = "retired"
    ent["kept"] = [k for k in ent.get("kept") or [] if isinstance(k, dict) and k.get("path") not in paths]
    if not ent["kept"]:
        del ent["kept"]
    files = []
    for f in ent.get("files") or []:
        f = dict(f)
        if f.get("path") in paths:
            f["brief"] = None
        files.append(f)
    ent["files"] = files
    _save(fab, twin, ent)
    return {"released": paths, "message": f"let go of {', '.join(paths)}: the next entailment tells "
                                          f"{'it' if len(paths) == 1 else 'them'} again"}


#: A reader of one edited file against the fabulac: `read(doc, path, text) -> [items]`, the items the read stage
#: (Thym 20.6) finds in it. The app's is `read_by_model`; a test passes its own.
Reader = Callable[[dict, str, str], list]

#: The kinds a reading proposes back, in the order their questions are asked (an interface before what is about it).
TAKE_BACK_ORDER = ("interface", "structure", "setting", "behaviour", "case", "term", "concept", "claim", "event")
_NOT_COMPARED = ("provenance", "span", "stance", "lines", "made")


def _comparable(d: dict) -> dict:
    return {k: v for k, v in d.items() if k not in _NOT_COMPARED}


def proposals(doc: dict, reading: list, path: str) -> list[dict]:
    """What a reading of an edited file adds to the fabulac or changes in it, as take-back questions (unlanded):
    one choice question per item that is new (about its kind) or differs (about the item), `proposed: {item, file}`,
    the item without its span (the file is not part of the fabulac); an item the fabulac holds as read is left out,
    and so are the reading's files and anything of module D."""
    from . import dialectic as _dl
    by = {d.get("id"): d for d in doc.get("nodes") or [] if isinstance(d, dict)}
    rank = {k: i for i, k in enumerate(TAKE_BACK_ORDER)}
    out = []
    for r in sorted((x for x in reading if isinstance(x, dict) and isinstance(x.get("id"), str)),
                    key=lambda x: rank.get(str(x.get("type")), len(rank))):
        mod, _sep, rest = r["id"].partition(":")
        kind = rest.split("/", 1)[0]
        if mod == "D" or (mod == "C" and kind == "file"):
            continue
        item = {k: v for k, v in r.items() if k != "span"}
        have = by.get(r["id"])
        if have is not None and _comparable(have) == _comparable(item):
            continue
        name = str(r.get("name") or r["id"])
        if have is None:
            about = f"{mod}:{kind}"
            asks = (f"{path} was changed by hand, and it now holds {r['id']}, {name}: {r.get('summary') or ''} "
                    "Take it back into the fabulac?").replace("  ", " ")
            why = "missing"
        else:
            fields = sorted({k for k in set(_comparable(have)) | set(_comparable(item))
                             if _comparable(have).get(k) != _comparable(item).get(k)})
            about = r["id"]
            asks = (f"{path} was changed by hand, and {r['id']}, {name}, now reads otherwise in its "
                    f"{', '.join(fields)}. Take the code's reading back into the fabulac?")
            why = "conflict"
        out.append({"id": f"take-back-{_slug(r['id'].split('/', 1)[-1])}", "about": about, "asks": asks, "why": why,
                    "kind": "choice", "options": [_dl.TAKE_IT_BACK, _dl.LEAVE_IT_OUT], "from": _dl.TAKE_BACK,
                    "proposed": {"item": item, "file": path}})
    return out


def take_back(project_dir: Path, fab: Path, path: str, *, read: Reader | None = None, at: Any = None,
              **read_kw: Any) -> dict:
    """Take a hand edit back (MacroCOSM OES 18.4.1; Thym 20.11): the edited Python file is read against the fabulac
    as the read stage reads one (Thym 20.6; `read`, by default `read_by_model`), and what the reading adds or changes
    is put to the person as questions in the fabulac (`proposals`: answer `take it back` or `leave it out`; settling
    writes the item with `stance: observed`). The file's bytes are recorded as the entailment's, so it is no longer
    a hand edit: once the answers are settled the items it was told from have moved, and the next entailment tells
    it again from the fabulac; a file the fabulac does not tell stays as it is. Returns `{path, questions, refused,
    message}`."""
    from . import dialectic as _dl
    doc = _authored(fab)
    _state, (path,) = _edited_only(fab, doc, [path], "take back")
    if not path.endswith(".py"):
        raise EntailError(f"{path} is not a Python file, and this edition reads only Python as code: keep it, or "
                          "write over it", 409)
    f = entailed_path(fab) / path
    text = f.read_bytes().decode("utf-8")
    reading = (read or (lambda d, p, t: read_by_model(project_dir, fab, p, t, **read_kw)))(doc, path, text)
    props = proposals(doc, reading, path)
    twin = _dl.open_twin(fab)
    led = twin.ledger
    taken = led.ids()
    to = _dl.default_to(led)
    when = _dl.now(at)
    qs = []
    for p in props:
        slug = _dl._unique_slug(p["id"], taken, led)
        qs.append(_dl._question_item(_dl.Q_PREFIX + slug, p["about"], p["asks"], p["why"],
                                     {"kind": p["kind"], "options": p["options"]}, to,
                                     {"by": "move", "from": _dl.TAKE_BACK, "at": when}, proposed=p["proposed"]))
    refused = []
    if qs:
        cand = led.copy()
        cand.items.extend(qs)
        if cand.manifest.single_file:
            cand.catalog[_dl._items_key(cand.manifest)] = cand.items
        bad = {_dl._bare(e.item) for e in _dl.default_checker(cand.volume()).errors}
        refused = [q["id"] for q in qs if q["id"] in bad]
        qs = [q for q in qs if q["id"] not in bad]
    _dl.land(led, qs)
    ent = dict(_entailed_of(twin.doc))
    sha = _sha(f)
    files, seen = [], False
    for r in ent.get("files") or []:
        r = dict(r)
        if r.get("path") == path:
            r["sha256"], seen = sha, True
        files.append(r)
    if not seen:
        files.append({"path": path, "sha256": sha, "from": [], "brief": _ac.brief_digest([], [])})
    ent["files"] = sorted(files, key=lambda r: _ac.path_key(str(r["path"])))
    _save(fab, twin, ent)
    return {"path": path, "questions": [q["id"] for q in qs], "refused": refused,
            "message": f"read {path} back: {len(qs)} question{'s' if len(qs) != 1 else ''} for the person"}


def read_by_model(project_dir: Path, fab: Path, path: str, text: str, *, route: str = "local",
                  model: str | None = None, calls: int | None = None, llm_url: str | None = None, why: str = "",
                  runtime: Callable | None = None, complete: Callable | None = None,
                  now: dt.datetime | None = None) -> list[dict]:
    """The read stage over one edited file (Thym 20.6; `decompile-python.thym`'s `read-every-file`), in a scratch
    folder holding that file alone, against a copy of the fabulac given a `C:file` for it: the items the reading
    gives (the scratch file's own item left out)."""
    import tempfile
    from .thym import run as _run
    import copy
    doc = _fj._load(fab)
    nodes = [copy.deepcopy(d) for d in doc.get("nodes") or [] if isinstance(d, dict)]
    fid, cid = f"C:file/{_slug(path)}", f"C:component/{_slug(path)}-as-edited"
    cat = {k: v for k, v in doc.items() if k != "nodes"}
    mine = next((s["interfaces"] for s in _ac.plan_sources(cat, nodes) if s["path"] == path), [])
    for d in nodes:                           # the outline the read stage reads against: this file's interfaces
        if d.get("id") in mine:
            d["defined-in"] = fid
    def prov() -> dict:
        return {"mode": "derived", "sources": [path], "confidence": 1}
    scratch = {**doc, "nodes": nodes + [
        {"id": fid, "type": "file", "name": path, "summary": f"{path}, changed by hand, read to take it back.",
         "path": path, "language": "python", "length": {"lines": len(text.splitlines()) or 1},
         "component": cid, "stance": "observed", "provenance": prov()},
        {"id": cid, "type": "component", "name": path, "summary": f"{path}, as it was changed by hand.",
         "does": f"what {path} does now", "files": [fid], "exposes": list(mine), "stance": "observed", "provenance": prov()}]}
    gone = {fid, cid}

    def unscratch(d: dict) -> dict:
        out = {}
        for k, v in d.items():
            if k == "made" or (isinstance(v, str) and v in gone):     # the run's stamp, or the scratch outline
                continue
            if isinstance(v, list) and any(isinstance(x, str) and x in gone for x in v):
                v = [x for x in v if not (isinstance(x, str) and x in gone)]
                if not v:
                    continue
            out[k] = v
        return out
    with tempfile.TemporaryDirectory(prefix="take-back-") as tmp:
        root = Path(tmp)
        name = _fj.compiled_name(fab)
        folder = root / name
        (folder / path).parent.mkdir(parents=True, exist_ok=True)
        (folder / path).write_text(text, encoding="utf-8")
        sfab = root / fab.name
        sfab.write_text(_macrocosm.dump(scratch), encoding="utf-8")
        stage = "read-every-file"
        prog = _fj.program_path()
        checked = _fj._checked(prog)
        rows = _fj.stage_rows(folder, sfab, stage)
        plan, info = _host.plan_for(checked, rows, route=route, model=model, llm_url=llm_url, program=stage,
                                    inputs_root=root)
        if isinstance(plan, Refusal):
            raise RuntimeError(f"the reading was refused ({plan.check}): {plan.message}")
        make = runtime or _fj.app_runtime(Path(project_dir), why=why, route=route, model=model, calls=calls,
                                          complete=complete)
        kw = make(stage, plan, info, "model", False, prog)
        t = _run.run(plan, inputs_root=root, program=prog, **({"now": now} if now is not None else {}), **kw)
        if isinstance(t, Refusal):
            raise RuntimeError(f"the reading was refused ({t.check}): {t.message}")
        if not t.landed:
            r = t.refusal
            raise RuntimeError(f"the reading was refused ({r.check}): {r.message}" if r else "the reading was refused")
        got = _macrocosm.yaml_load(Path(t.outputs["g"]).read_text(encoding="utf-8"))
    have = {d.get("id"): d for d in scratch["nodes"]}
    read = [d for d in (got or {}).get("nodes") or [] if isinstance(d, dict) and d.get("id") not in gone]
    return [unscratch(d) for d in read if d.get("id") not in have
            or _comparable(unscratch(have[d["id"]])) != _comparable(unscratch(d))]


__all__ = ["EntailError", "JOB_KIND", "KEPT_PREFIX", "PROGRAM", "PROGRAM_FILE", "STATES", "TAKE_BACK_ORDER",
           "entailed_path", "hand_edits", "keep", "land", "let_go", "proposals", "read_by_model", "record_entailed",
           "run_entail", "step_state", "take_back"]
