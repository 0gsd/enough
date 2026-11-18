"""Transconception's moves, the cases (MacroCOSM 18.4.9; Thym 20.10, Transconceiving a fabulac), seen by `thym 1`
programs only.

- `entail f as cases` (fabula -> text; a kind of `entail`, declared in its `thym-1:` view): the cases file the
  fabulac's catalog names (`cases: <folder>.cases.json`), in the outside harness's own shape, from the fabulac's
  outside `P:case` items and the cases already recorded beside it; each case whose recorded expectation stands on
  another source than the fabulac's is marked `stale`, and the judge's rulings for each target are derived from the
  fabulac's. No model: its scaffold is the move itself (`cases-file`), so `--rules` makes the same file.
- `gather recorded with f` (folder -> text): a recording folder (the harness's `record` leaves one: `recorded.json`,
  `cases.json`) read into that cases file; each recorded case says which source it was recorded from.
- `gather verdict with f` (text -> fabula): a verdict file (the harness's `judge` writes one) read into the evidence
  of the cshort it judged. It raises nothing itself: `enough.transconception.differences_from_verdict` gives the
  findings as data, and the rulings turn them into questions.

The two gathers are `gather` called with a folder or a text (`edit.gather` hands them here). `gather`'s declaration
still takes only lists (THYM 6.3's table, which a test holds); until the text and the declaration take a folder and a
text, a program cannot write them, and a host calls `gather_outside` itself.

The recorder, runner and judge live outside enough (`tools/transconception/harness.py`), the owner's to run in their
sandbox: these moves read the files they leave, and start nothing. The cases functions are enough's
(`enough.transconception`), reached as `ctx.engines["transconception"]` like every engine (`enough.thym_host`): this
module imports only Thym and the reader, so a host without them refuses the moves by name.

The checks: `cases-whole` (the cases file is whole data in the harness's shape, written as the harness writes it, with
every outside case of the fabulac in it), `source-named` (every recorded case names the source it was recorded from,
or says why it is stale, and nothing the recording holds is lost), `evidence-stated` (the cshort's evidence carries
its level, its counts and the verdict's digest).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from enough import macrocosm as mc
from enough.thym.checks import check
from enough.thym.moves import MoveError, engine, fabula_doc
from enough.thym.registry import implements
from enough.thym.values import Value

#: The scaffold of `entail f as cases`: the move needs no model, so a `--rules` run makes the same file.
CASES_SCAFFOLD = "cases-file"
ENGINE = "transconception"


def _tc(ctx: Any) -> Any:
    return engine(ctx, ENGINE)


def _fabulac_path(v: Value | None) -> Path | None:
    """Where the fabulac a value holds lives on disk (its `.fabulac.cosm`), when it was read from there."""
    if not isinstance(v, Value):
        return None
    if isinstance(v.payload, mc.Volume):
        p = v.payload.path or v.payload.root
        return Path(p) if p else None
    return Path(v.path) if v.path is not None else None


def _beside(v: Value | None, name: str) -> Path | None:
    p = _fabulac_path(v)
    if p is None:
        return None
    return (p if p.is_dir() else p.parent) / name


def _existing_cases(tc: Any, v: Value, catalog: dict) -> dict | None:
    """The cases file already beside the fabulac, as data; None when there is none."""
    p = _beside(v, tc.cases_name(catalog))
    if p is None or not p.is_file():
        return None
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise MoveError(f"the cases file beside the fabulac, {p.name}, cannot be read: {e}") from None
    return doc if isinstance(doc, dict) else None


def _need_fabula(x: Any, what: str) -> tuple[dict, list[dict]]:
    if not isinstance(x, Value) or x.type not in ("fabula", "volume"):
        raise MoveError(f"{what} needs a fabulac")
    cat, nodes = fabula_doc(x)
    if not nodes:
        raise MoveError(f"{what}: the fabula holds no items")
    return cat, nodes


def _cases_value(text: str, *, name: str, fabula: Value, report: dict) -> Value:
    return Value("text", text, origin={"cases": {"file": name, "fabula": fabula, **report}})


@implements(CASES_SCAFFOLD)
def entail_cases(ctx: Any, x: Value, **mods: Any) -> Value:
    """`entail f as cases`: the fabulac's cases file, as text (the harness's own JSON)."""
    tc = _tc(ctx)
    cat, nodes = _need_fabula(x, "entail … as cases")
    doc, report = tc.cases_document(cat, nodes, existing=_existing_cases(tc, x, cat))
    if not doc["cases"]:
        raise MoveError("entail … as cases: the fabulac holds no outside case (stands: outside) and no cases file "
                        "beside it names one")
    return _cases_value(tc.dump_cases(doc), name=tc.cases_name(cat), fabula=x, report=report)


def _folder_files(v: Value):
    """`get(relative path) -> bytes or None` over a folder value, and the text of the `environment.txt` beside it."""
    f = v.payload
    names = {e.path for e in getattr(f, "entries", ())}

    def get(rel: str) -> bytes | None:
        return f.raw(rel) if rel in names else None

    env = None
    root = getattr(f, "root", None)
    if root is not None and (Path(root).parent / "environment.txt").is_file():
        env = (Path(root).parent / "environment.txt").read_text(encoding="utf-8")
    return get, env


def _folder_name(v: Value) -> str:
    f = v.payload
    root = getattr(f, "root", None)
    return Path(root).name if root is not None else Path(str(getattr(f, "path", "recording"))).name


def _recording(tc: Any, rec: Value) -> Any:
    get, env = _folder_files(rec)
    return tc.read_recording(get, name=_folder_name(rec), environment=env)


def gather_recorded(ctx: Any, rec: Value, w: Value) -> Value:
    """`gather recorded with f`: the fabulac's cases file with a recording folder read into it."""
    tc = _tc(ctx)
    cat, nodes = _need_fabula(w, "gather recorded with f")
    try:
        recording = _recording(tc, rec)
    except tc.CasesError as e:
        raise MoveError(f"gather recorded with f: {e}") from None
    doc, made = tc.cases_document(cat, nodes, existing=_existing_cases(tc, w, cat))
    doc, report = tc.gather_recorded(doc, recording, now=tc.source_of(cat))
    return _cases_value(tc.dump_cases(doc), name=tc.cases_name(cat), fabula=w,
                        report={**report, "recording": recording.name, "source": recording.source,
                                "from-items": made["from-items"], "from-file": made["from-file"]})


def gather_verdict(ctx: Any, verdict: Value, w: Value) -> Value:
    """`gather verdict with f`: the fabulac with the verdict read into its cshort's evidence."""
    tc = _tc(ctx)
    cat, nodes = _need_fabula(w, "gather verdict with f")
    raw = verdict.bytes()
    name = verdict.path.name if verdict.path is not None else "verdict.json"
    try:
        v = tc.read_verdict(raw, name=name)
    except tc.CasesError as e:
        raise MoveError(f"gather verdict with f: {e}") from None
    where = name
    fp = _fabulac_path(w)
    if verdict.path is not None and fp is not None:
        base = fp if fp.is_dir() else fp.parent
        where = Path(os.path.relpath(Path(verdict.path).resolve(), base.resolve())).as_posix()
    now = getattr(ctx, "now", None)
    at = now.strftime("%Y-%m-%dT%H:%M") if now is not None else "1970-01-01T00:00"
    run = getattr(ctx, "run", None)
    by = f"the judge, run by the owner; gathered in run {run}" if run else "the judge, run by the owner"
    try:
        new_cat, report = tc.fold_verdict({k: x for k, x in cat.items() if k != "nodes"}, v, verdict_bytes=raw,
                                          where=where, at=at, by=by)
    except tc.CasesError as e:
        raise MoveError(f"gather verdict with f: {e}") from None
    return Value("fabula", {**new_cat, "nodes": nodes},
                 origin={"verdict": {"report": report, "digest": hashlib.sha256(raw).hexdigest()}})


def gather_outside(ctx: Any, parts: Value, **mods: Any) -> Value:
    """`gather` of what a transconception's outside tools leave: a recording folder, or a verdict file. Called by
    `gather` (`enough/thym/moves/edit.py`) for a `folder` or a `text`; its list forms are untouched."""
    w = mods.get("with")
    if not isinstance(w, Value) or w.type not in ("fabula", "volume"):
        raise MoveError("gather needs the fabulac it gathers into: gather recorded with f, gather verdict with f")
    if parts.type == "folder":
        return gather_recorded(ctx, parts, w)
    if parts.type == "text":
        return gather_verdict(ctx, parts, w)
    raise MoveError(f"gather takes a list of fabulas or of items, a recording folder or a verdict, not {parts.type}")


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------

def _cases_of(output: Value) -> tuple[dict | None, str]:
    if not isinstance(output, Value) or output.type != "text":
        return None, "the output is not a cases file (a text)"
    text = output.text()
    try:
        doc = json.loads(text)
    except ValueError as e:
        return None, f"the cases file is not JSON: {e}"
    return doc, text


@check("cases-whole")
def _cases_whole(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """The cases file is whole data in the harness's shape, written as the harness writes it (one dump, byte for
    byte), and every outside case of the fabulac (bar a ruled one) is in it."""
    tc = _tc(ctx)
    doc, text = _cases_of(output)
    if doc is None:
        return False, text
    if tc.dump_cases(doc) != text:
        return False, "the cases file is not written as the harness writes it (indent 1, UTF-8 kept, a last newline)"
    bad = tc.check_cases_doc(doc)
    if bad:
        return False, "; ".join(bad[:5])
    fab = next((v for v in inputs.values() if isinstance(v, Value) and v.type in ("fabula", "volume")), None)
    if fab is not None:
        _cat, nodes = fabula_doc(fab)
        have = {c.get("item") for c in doc["cases"]} | {c.get("id") for c in doc["cases"]}
        missing = [n["id"] for n in nodes if str(n.get("id", "")).startswith("P:case/")
                   and n.get("stands") == "outside" and n.get("from") != "ruled"
                   and n["id"] not in have and tc.case_key(n, "P:case/") not in have]
        if missing:
            return False, f"{len(missing)} outside cases of the fabulac are not in the file: {', '.join(missing[:5])}"
    return True, ""


@check("source-named")
def _source_named(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every case with a recorded expectation names the source it was recorded from, or is marked stale with why;
    and every case of the recording gathered is in the file (nothing it recorded is lost)."""
    tc = _tc(ctx)
    doc, text = _cases_of(output)
    if doc is None:
        return False, text
    for c in doc.get("cases") or []:
        if not isinstance(c, dict) or "expect" not in c:
            continue
        if not tc.source_marks((c.get("recorded") or {}).get("source")) and not c.get("stale"):
            return False, f"{c.get('id')}: carries a recorded expectation and names no source it was recorded from"
    rec = next((v for v in inputs.values() if isinstance(v, Value) and v.type == "folder"), None)
    if rec is not None:
        try:
            recording = _recording(tc, rec)
        except tc.CasesError as e:
            return False, str(e)
        have = {c.get("id") for c in doc.get("cases") or [] if isinstance(c, dict)}
        rcases = {c.get("id") for c in ((recording.cases or {}).get("cases") or []) if isinstance(c, dict)}
        lost = [str(r.get("id")) for r in recording.recorded["rows"] if r.get("id") not in have
                and r.get("id") in rcases]
        if lost:
            return False, f"recorded cases not in the file: {', '.join(lost[:5])}"
    return True, ""


@check("evidence-stated")
def _evidence_stated(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """The cshort the verdict judged carries evidence: its level (1 to 4), its counts (agree no more than kept),
    and the verdict file's digest, which is the digest of the verdict gathered."""
    tc = _tc(ctx)
    cat = output.mapping() if isinstance(output, Value) else None
    if not isinstance(cat, dict):
        return False, "the output is not a fabula"
    verdict = next((v for v in inputs.values() if isinstance(v, Value) and v.type == "text"), None)
    label = digest = None
    if verdict is not None:
        try:
            label = str(tc.read_verdict(verdict.bytes()).get("cshort"))
        except tc.CasesError as e:
            return False, str(e)
        digest = hashlib.sha256(verdict.bytes()).hexdigest()
    rows = [e for e in cat.get("shorts") or [] if isinstance(e, dict) and isinstance(e.get("evidence"), dict)
            and (label is None or tc.cshort_label(e) == label)]
    if not rows:
        return False, f"no cshort {label} carries evidence" if label else "no cshort carries evidence"
    ev = rows[-1]["evidence"]
    lv, st, wh = ev.get("level"), ev.get("steps"), ev.get("where")
    if not (isinstance(lv, int) and 1 <= lv <= 4):
        return False, "evidence.level is 1 to 4"
    if not (isinstance(st, dict) and isinstance(st.get("kept"), int) and isinstance(st.get("agree"), int)
            and 0 <= st["agree"] <= st["kept"]):
        return False, "evidence.steps is {kept, agree}, agree no more than kept"
    if not (isinstance(wh, dict) and wh.get("file") and wh.get("digest")):
        return False, "evidence.where names the verdict file and its digest"
    if digest is not None and wh["digest"] != digest:
        return False, f"evidence.where.digest is {str(wh['digest'])[:12]}, the verdict's {digest[:12]}"
    return True, ""


__all__ = ["CASES_SCAFFOLD", "ENGINE", "entail_cases", "gather_outside", "gather_recorded", "gather_verdict"]
