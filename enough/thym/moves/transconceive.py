"""The moves of a transconception (Thym 20.10; MacroCOSM OES 18.4.9), each `since: 1`: the ground (lane W2-X2)
and the cases (lane W2-X4) of the 0.8 build, joined by the conductor. The two parts follow in that order, each with
its own account below.


This module holds `ground` (lane W2-X2 of the 0.8 build); the cases moves (`entail f as cases`, `gather recorded`,
`gather verdict`) arrive beside it from their own lane.

**`ground repo with f`**, rules only, nothing in the repository run, imported or installed: the fabula so far with one
`C:reliance` (or `P:assumption`) for each entry of its language's ground catalogue (`enough.languages`,
`defaults/cosm/ground/<language>.ground.cosm`) whose `shows-as` the program's syntax shows. Each is copied from its
entry whole, with `entry` naming it, so the fabulac reads alone without the catalogue or the library: `on`, `gives`,
`example`, `stated`, and `of` (the `R:means` of the language, the `C:dependency` of its runtime, or of the package).
`used-by` lists what leans on it: the interface or setting whose lines hold a call site (else the file's component),
and every item whose words name the gift as the runtime names it (`names`), which is what `stands-alone` asks of a
reliance that says the same without the name. The same move pins what can be pinned without running anything: each
`C:dependency`'s `address`, `resolved` and `digest` from a lock or version file (`.python-version`, `uv.lock`,
`poetry.lock`, `Pipfile.lock`, `requirements*.txt` with `==`), and `source.swhid` (the folder's tree as Software
Heritage names it, and the commit's revision). A fabulac grounded again gains only what is new: an item it holds
keeps every field, its `used-by` growing at the end.

Like every move it reads no file and imports nothing outside `enough.thym` and `enough.macrocosm` (the package
Comprise vendors): it reaches the files and the catalogue through the host's engines (`enough.repo_engine`,
recorded, so a replay needs neither the folder nor the catalogue): `syntax.catalogue` once (the language's entry of
the registry, `enough/languages.py`, and its catalogue whole), `syntax.uses` per file of the language (tooling left
out; a test file shows only what the tests lean on of a dependency), `syntax.locks` per lock file, `repo.swhid` once.

The check `ground-cited` (MacroCOSM OES 18.4.9; Thym 7.3): every reliance on the language or its runtime carries
`stated`, a list of `{in, version, at, digest}` and `{nowhere: text}`, a version a patch of the runtime's release where
the fabula pins it, as `enough.transconception` reads it on a fabulac kept for transconception; and a reliance copied
from a ground catalogue is stored whole (it carries `on`, `gives`, `example` and `stated` itself, `entry` naming the
entry). Resolving a citation against the language library is `enough.transconception.resolve_citation`'s.

---

Transconception's moves, the cases (MacroCOSM 18.4.9; Thym 20.10, Transconceiving a fabulac), seen by `thym 1`
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

import copy
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from enough import macrocosm as mc
from enough.thym.checks import check
from enough.thym.moves import MoveError, engine, fabula_doc, item_kind
from enough.thym.moves.code import (_fabula, _file_items, _folder_of, _need_fabulac, _program, is_test, is_tooling,
                                    loc, prov, span, stamp_at)
from enough.thym.registry import implements
from enough.thym.values import Value, plain

#: The fields of a catalogue entry copied whole into the reliance (and checked as stored whole by `ground-cited`).
COPIED = ("on", "gives", "example", "stated")
#: The kinds whose words `names` are not read in: what `stands-alone` does not read (enough/transconception.py,
#: `STANDS_ALONE_SKIP_*`; a test holds the two the same).
_SKIP_MODULES = ("R", "D")
_SKIP_KINDS = (("P", "case"), ("C", "reliance"), ("C", "dependency"), ("N", "target"))
#: The fields whose words `names` are read in.
_NAMED_FIELDS = ("summary", "means", "gives")
#: The conditions that hold of one call (the rest hold of the file the call is in).
CALL_CONDITIONS = ("call", "method", "kw", "without", "arg0", "mode")


def _lock_file(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return "/" not in path and (name in (".python-version", "uv.lock", "poetry.lock", "Pipfile.lock")
                                or re.fullmatch(r"requirements[\w.-]*\.txt", name) is not None)


# ---------------------------------------------------------------------------
# Matching a catalogue entry against a file's uses
# ---------------------------------------------------------------------------

def _names_match(want: str, got: Any, written: Any = None) -> bool:
    """A dotted name as a rule writes it against one a file reaches (or writes): equal, or its last parts."""
    for g in (got, written):
        if isinstance(g, str) and (g == want or g.endswith("." + want)):
            return True
    return False


def _call_holds(cond: dict, c: dict) -> bool:
    if "call" in cond and c.get("name") != cond["call"]:
        return False
    if "method" in cond and c.get("method") != cond["method"]:
        return False
    kw = cond.get("kw")
    if isinstance(kw, list) and not set(map(str, kw)) <= set(c.get("kw") or []):
        return False
    if isinstance(kw, dict):
        got = c.get("kwv") or {}
        if any(str(got.get(k)) != str(v) for k, v in kw.items()):
            return False
    if any(k in (c.get("kw") or []) for k in cond.get("without") or []):
        return False
    a0 = cond.get("arg0")
    if a0 is not None:
        if a0 in ("str", "int", "float", "bytes", "bool"):
            if c.get("kind0") != a0:
                return False
        elif str(a0) not in str(c.get("arg0") or ""):
            return False
    mode = cond.get("mode")
    if mode is not None and not any(m in str(c.get("mode") or "") for m in mode):
        return False
    return True


def _file_sites(cond_key: str, cond: Any, u: dict) -> list[dict]:
    """The sites of a file one non-call condition holds at (`[]`: it does not hold there)."""
    if cond_key == "attr":
        return [r for r in u.get("attrs") or [] if r.get("name") == cond]
    if cond_key == "annotation":
        return [r for r in u.get("annotations") or [] if r.get("name") == cond]
    if cond_key == "form":
        return [r for r in u.get("forms") or [] if r.get("form") == cond]
    if cond_key in ("decorator", "base"):
        return [r for r in u.get(cond_key + "s") or [] if _names_match(str(cond), r.get("name"), r.get("as"))]
    if cond_key == "handler":
        return [r for r in u.get("handlers") or [] if r.get("name") == cond]
    if cond_key == "import":
        return [r for r in u.get("imports") or [] if r.get("module") == cond or
                str(r.get("module") or "").startswith(str(cond) + ".")]
    if cond_key == "string":
        want = set(cond if isinstance(cond, list) else [cond])
        return [{"line": 1}] if want & set(u.get("strings") or []) else []
    if cond_key == "entry-point":
        return [{"line": int(u["entry"])}] if cond and u.get("entry") else []
    return []


def shown(entry: dict, uses: dict[str, dict], *, declared: dict | None = None) -> list[dict]:
    """Where a program's syntax shows a catalogue entry: `[{path, line, in}]`, one per site, the files' order; `[]`
    when it does not. An alternative of `shows-as` holds in a file when its call conditions hold of one call there
    and each other condition at some site of the same file; its sites are the calls (else the first condition's).
    `declared` answers the conditions about the fabula itself (`declared: runtime-version`), as `{name: item id}`."""
    out: list[dict] = []
    seen: set = set()
    for alt in entry.get("shows-as") or []:
        if not isinstance(alt, dict):
            continue
        if "declared" in alt:
            iid = (declared or {}).get(str(alt["declared"]))
            if iid and ("item", iid) not in seen:
                seen.add(("item", iid))
                out.append({"item": iid})
            continue
        call_part = {k: v for k, v in alt.items() if k in CALL_CONDITIONS}
        rest = [(k, v) for k, v in alt.items() if k not in CALL_CONDITIONS]
        for path in sorted(uses):
            u = uses[path]
            if not isinstance(u, dict) or not u.get("ok"):
                continue
            found = [_file_sites(k, v, u) for k, v in rest]
            if any(not f for f in found):
                continue
            if call_part:
                sites = [c for c in u.get("calls") or [] if _call_holds(call_part, c)]
                if set(call_part) == {"call"}:      # a function passed by its name is used as surely as one called
                    sites += [r for r in u.get("attrs") or [] if r.get("name") == call_part["call"]]
            else:
                sites = found[0] if found else []
            for s in sites:
                key = (path, int(s.get("line") or 1), s.get("in"))
                if key not in seen:
                    seen.add(key)
                    out.append({"path": path, "line": key[1], **({"in": key[2]} if key[2] else {})})
    return out


# ---------------------------------------------------------------------------
# Writing the reliances
# ---------------------------------------------------------------------------

def _lines(it: dict) -> tuple[str, int, int] | None:
    sp = it.get("span")
    if not isinstance(sp, dict) or not isinstance(sp.get("file"), str):
        return None
    m = re.match(r"^(\d+)(?:-(\d+))?$", str(sp.get("lines") or ""))
    if not m:
        return None
    a = int(m.group(1))
    return sp["file"], a, int(m.group(2) or a)


def _site_owner(site: dict, items: list[dict], files: dict[str, dict]) -> str | None:
    """The item a call site is in: the narrowest interface whose lines hold it, else the narrowest setting, else the
    component of its file."""
    best: tuple[int, int, str] | None = None
    for it in items:
        k = item_kind(it)
        if k not in ("interface", "setting"):
            continue
        got = _lines(it)
        if got is None or got[0] != site["path"] or not (got[1] <= site["line"] <= got[2]):
            continue
        rank = (0 if k == "interface" else 1, got[2] - got[1], str(it["id"]))
        if best is None or rank < best:
            best = rank
    if best is not None:
        return best[2]
    fid = (files.get(site["path"]) or {}).get("id")
    for it in items:
        if item_kind(it) == "component" and fid in (it.get("files") or []):
            return str(it["id"])
    return None


def _texts(node: Any):
    """Every summary, meaning and gift an item says, at any depth."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k in _NAMED_FIELDS and isinstance(v, str):
                yield v
            elif isinstance(v, (dict, list)):
                yield from _texts(v)
    elif isinstance(node, list):
        for v in node:
            yield from _texts(v)


def _text_named(it: dict, patterns: list[re.Pattern]) -> bool:
    return any(p.search(text) for text in _texts(it) for p in patterns)


def _norm(pkg: Any) -> str:
    return re.sub(r"[-_.]+", "-", str(pkg or "")).lower()


def _holders(items: list[dict], lang: dict) -> tuple[dict | None, dict | None]:
    """The fabula's own items for the language (its `R:means`, by id or by what it names) and for its runtime (the
    `C:dependency` whose package is the runtime's)."""
    name, runtime = str(lang.get("name")), str(lang.get("runtime"))
    means = next((it for it in items if it.get("id") == f"R:means/{name}"), None) or next(
        (it for it in items if item_kind(it) == "means" and str(it.get("what") or "").lower() == name), None)
    rt = next((it for it in items if it.get("id") == f"C:dependency/{runtime}"), None) or next(
        (it for it in items if item_kind(it) == "dependency" and _norm(it.get("package")) == runtime), None)
    return means, rt


def _of(entry: dict, items: list[dict], lang: dict) -> str | None:
    """Whose gift an entry is, as an item of the fabula: the language's `R:means`, its runtime's `C:dependency`, or
    the package's `C:dependency`; None when the fabula holds no such item."""
    of = str(entry.get("of") or "")
    means, rt = _holders(items, lang)
    if of == "means":
        return str(means["id"]) if means else None
    if of == "runtime":
        return str(rt["id"]) if rt else None
    dep = next((it for it in items if item_kind(it) == "dependency" and _norm(it.get("package")) == _norm(of)), None)
    return str(dep["id"]) if dep else None


def _first_sentence(text: str) -> str:
    """The first sentence of an entry's `gives`, as the reliance's summary."""
    t = " ".join(str(text).split())
    m = re.match(r"^(.+?\.)(\s+[A-Z(\"'])", t)
    return m.group(1) if m else t


def _pin(dep: dict, lang: dict, catalogue: dict, lockinfo: dict) -> dict:
    """What can be pinned of one `C:dependency` without running anything; only fields it does not carry yet."""
    pkg = str(dep.get("package") or "")
    add: dict = {}
    if _norm(pkg) == lang.get("runtime"):
        pin = next((p for p in catalogue.get("pins") or [] if p.get("what") == "implementation"), None)
        if pin and pin.get("from"):
            add["address"] = pin["from"]
        if lockinfo.get("runtime"):
            add["resolved"] = lockinfo["runtime"]
    elif pkg:
        norm = _norm(pkg)
        row = lockinfo.get("packages", {}).get(norm)
        add["address"] = (row or {}).get("address") or f"https://pypi.org/project/{norm}/"
        if row and row.get("version"):
            add["resolved"] = row["version"]
        if row and row.get("digest"):
            add["digest"] = row["digest"]
    return {k: v for k, v in add.items() if k not in dep or mc.is_pending(dep.get(k))}


def _ground_of(answer: Any) -> tuple[dict, dict]:
    """(the language's entry, the catalogue) from `syntax.catalogue`'s answer; a MoveError in plain words else."""
    if not isinstance(answer, dict) or not answer.get("ok"):
        why = answer.get("why") if isinstance(answer, dict) else None
        raise MoveError(why or "no ground catalogue came back for the fabulac's language")
    return dict(answer.get("language") or {}), dict(answer.get("catalogue") or {})


def ground_fabula(cat: dict, items: list[dict], uses: dict[str, dict], ground: dict, *,
                  locks: dict[str, dict] | None = None, swhid: dict | None = None,
                  run: dict | None = None) -> tuple[dict, list[dict], dict]:
    """The pure part of `ground`: (the catalog, the items, what was found) for a fabulac's catalog and items, the
    `syntax.uses` of its language's files by path, `syntax.catalogue`'s answer for its language, the `syntax.locks` of
    its lock files and `repo.swhid`'s answer."""
    lang, catalogue = _ground_of(ground)
    cat = copy.deepcopy(cat)
    items = [copy.deepcopy(it) for it in items]
    by_id = {str(it.get("id")): it for it in items}
    files = _file_items(items)
    # what the fabula itself declares (`declared:` conditions)
    declared: dict[str, str] = {}
    means, rt = _holders(items, lang)
    for holder in (rt, means):
        if holder and any(isinstance(holder.get(k), str) and holder.get(k) for k in ("version", "pinned", "resolved")):
            declared["runtime-version"] = str(holder["id"])
            break
    # the program's files; a test file shows only what the tests lean on of a dependency (its runner's conventions)
    program = {p: u for p, u in uses.items() if not is_test(p)}
    found: dict[str, list[dict]] = {}
    new: list[dict] = []
    for e in catalogue.get("entries") or []:
        sites = shown(e, uses if e.get("on") == "dependency" else program, declared=declared)
        if not sites:
            continue
        eid = str(e["id"])
        found[eid] = sites
        users: list[str] = []
        for s in sites:                          # a declared condition's item is whose gift it is, not a user
            o = None if "item" in s else _site_owner(s, items, files)
            if o and o not in users:
                users.append(o)
        pats = [re.compile(str(p)) for p in e.get("names") or []]
        if pats:
            for it in items:
                mod, _, kind = str(it.get("id", "")).partition(":")
                if mod in _SKIP_MODULES or (mod, item_kind(it)) in _SKIP_KINDS:
                    continue
                if it["id"] not in users and _text_named(it, pats):
                    users.append(str(it["id"]))
        code_sites = [s for s in sites if "path" in s]
        sources = [loc(s["path"], s["line"]) for s in code_sites[:12]] or [f"C:dependency/{lang.get('runtime')}"]
        assumption = e.get("kind") == "assumption"
        iid = f"{'P:assumption' if assumption else 'C:reliance'}/{eid}"
        if assumption:
            it = {"id": iid, "type": "assumption", "name": e["name"], "summary": _first_sentence(e["gives"]),
                  "stance": "observed", "about": e.get("about") or e["name"], "checked": "no"}
            if e.get("if-false"):
                it["if-false"] = e["if-false"]
            if e.get("carries"):
                it["carries"] = e["carries"]
            if users:
                it["relied-by"] = users
        else:
            it = {"id": iid, "type": "reliance", "name": e["name"], "summary": _first_sentence(e["gives"]),
                  "stance": "observed", **{k: copy.deepcopy(e[k]) for k in COPIED}, "entry": eid}
            of = _of(e, items, lang)
            if of:
                it["of"] = of
            if users:
                it["used-by"] = users
        if code_sites:
            it["span"] = span(code_sites[0]["path"], code_sites[0]["line"])
        it["provenance"] = prov(sources)
        old = by_id.get(iid)
        if old is not None:                      # grounded before: what it holds stays, used-by grows at the end
            ref = "relied-by" if assumption else "used-by"
            more = [u for u in it.get(ref) or [] if u not in (old.get(ref) or [])]
            if more:
                old[ref] = list(old.get(ref) or []) + more
            continue
        new.append(it)
    # pins: each dependency's address, resolved and digest, as far as a lock or version file states them
    lockinfo: dict = {"packages": {}}
    for _p, lk in sorted((locks or {}).items()):
        if not isinstance(lk, dict) or not lk.get("ok"):
            continue
        if lk.get("runtime"):
            lockinfo["runtime"] = lk["runtime"]
        for row in lk.get("packages") or []:
            lockinfo["packages"].setdefault(re.sub(r"[-_.]+", "-", str(row.get("package"))).lower(), row)
    pinned: list[str] = []
    for it in items:
        if item_kind(it) != "dependency":
            continue
        add = _pin(it, lang, catalogue, lockinfo)
        if add:
            it.update(add)
            pinned.append(str(it["id"]))
    # the identifiers of the source
    if isinstance(cat.get("source"), dict) and "swhid" not in cat["source"]:
        sw: dict = {}
        if isinstance(swhid, dict) and swhid.get("ok") and swhid.get("dir"):
            sw["dir"] = swhid["dir"]
        if isinstance(cat["source"].get("commit"), str) and re.fullmatch(r"[0-9a-f]{40}", cat["source"]["commit"]):
            sw["rev"] = f"swh:1:rev:{cat['source']['commit']}"
        if sw:
            cat["source"]["swhid"] = sw
    if run is not None:
        d = cat.setdefault("derived", {})
        d.setdefault("runs", []).append({k: v for k, v in run.items() if v})
    grounds = {"entries": {k: [s.get("item") or loc(s["path"], s["line"]) for s in v][:12] for k, v in found.items()},
               "pinned": pinned, "catalogue": f"{lang.get('name')} {catalogue.get('version')}"}
    return cat, items + new, grounds


@implements("ground")
def ground(ctx: Any, repo: Value, **mods: Any) -> Value:
    """The fabula so far, grounded (Thym 20.10): one reliance per ground entry the syntax shows, stored whole, each
    citing where its gift is written; the dependencies pinned and the source's identifiers computed. Rules only."""
    f = _folder_of(repo, "ground")
    cat, items = _fabula(mods.get("with"), "ground needs the fabulac it grounds: ground repo with f")
    _need_fabulac(cat, "f", "ground adds reliances to a fabulac")
    src = cat.get("source") if isinstance(cat.get("source"), dict) else {}
    if not isinstance(src.get("language"), str) or not src["language"]:
        raise MoveError("f names no language in its source: survey the folder first")
    if isinstance(src.get("tree"), str) and src["tree"] != f.tree:
        raise MoveError(f"{f.path} is not the folder f was surveyed from: its tree is {str(f.tree)[:12]}…, f's "
                        f"{src['tree'][:12]}…")
    syn, rp = engine(ctx, "syntax"), engine(ctx, "repo")
    answer = syn.catalogue(src["language"])
    lang, _catalogue = _ground_of(answer)
    suffixes = tuple("." + str(s) for s in lang.get("suffixes") or [])
    uses = {e.path: syn.uses(e.path, f.text(e.path)) for e in f.texts()
            if e.path.lower().endswith(suffixes) and not is_tooling(e.path)}
    locks = {e.path: syn.locks(e.path, f.text(e.path)) for e in f.texts() if _lock_file(e.path)}
    sw = rp.swhid(repo)
    run = {"program": _program(ctx), "run": getattr(ctx, "run", None), "at": stamp_at(ctx)}
    cat, nodes, grounds = ground_fabula(cat, items, uses, answer, locks=locks, swhid=sw, run=run)
    return Value("fabula", {**cat, "nodes": nodes}, origin={"ground": grounds})


# ---------------------------------------------------------------------------
# The check
# ---------------------------------------------------------------------------

def _minor(v: Any) -> str | None:
    m = re.match(r"^\D*(\d+)\.(\d+)", str(v)) if isinstance(v, (str, int)) else None
    return f"{m.group(1)}.{m.group(2)}" if m else None


def cited_problems(cat: dict, items: list[dict]) -> list[str]:
    """`ground-cited` over a fabula's catalog and items: one line per problem, none when it holds. The same reading as
    `enough.transconception`'s check of that name (a test holds the two to the same verdicts), here for any fabulac a
    move grounds, kept for transconception or not; and a reliance copied from a catalogue carries what it copied."""
    src = cat.get("source") if isinstance(cat.get("source"), dict) else {}
    language = src.get("language") if isinstance(src.get("language"), str) else None
    minor = None
    for it in items:
        if item_kind(it) == "dependency" and language and it.get("package") == language:
            minor = next((m for k in ("resolved", "pinned") if (m := _minor(it.get(k)))), None)
            if minor:
                break
    out: list[str] = []
    for it in items:
        if item_kind(it) != "reliance":
            continue
        iid = it.get("id")
        if it.get("entry") and any(it.get(k) in (None, "", [], {}) for k in COPIED):
            out.append(f"{iid}: copied from {it['entry']}, it is stored whole: {', '.join(COPIED)}")
        if it.get("on") not in ("language", "runtime"):
            continue
        st = it.get("stated")
        if not isinstance(st, list) or not st:
            out.append(f"{iid}.stated: a reliance on the language or its runtime carries stated: a list of "
                       "{in, version, at, digest} and {nowhere: text}")
            continue
        for i, e in enumerate(st):
            if isinstance(e, dict) and set(e) == {"nowhere"}:
                if not (isinstance(e["nowhere"], str) and e["nowhere"].strip()):
                    out.append(f"{iid}.stated[{i}]: nowhere says what no text states")
                continue
            if not isinstance(e, dict) or any(not e.get(k) for k in ("in", "version", "at", "digest")):
                out.append(f"{iid}.stated[{i}]: a citation is {{in, version, at, digest}}, or {{nowhere: text}}")
                continue
            if minor and e.get("in") == language and _minor(e["version"]) != minor:
                out.append(f"{iid}.stated[{i}]: {e['in']} {e['version']} is not a patch of the runtime's {minor}")
        cb = it.get("contradicted-by")
        if cb is not None and not (isinstance(cb, dict) and cb.get("at") and cb.get("says")):
            out.append(f"{iid}.contradicted-by: contradicted-by is {{at, says, said}}")
    return out


@check("ground-cited")
def _ground_cited(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every reliance on the language or its runtime carries `stated`, and a reliance copied from a ground catalogue
    is stored whole with `entry` naming its entry (MacroCOSM OES 18.4.9; Thym 7.3). The citations resolve against
    the language library once it is aboard (`enough.transconception.resolve_citation`)."""
    cat, items = fabula_doc(output)
    cat = {k: plain(v) for k, v in cat.items() if k != "nodes"}
    probs = cited_problems(cat, [plain(it) for it in items])
    if probs:
        return False, "; ".join(probs[:3]) + (f" (and {len(probs) - 3} more)" if len(probs) > 3 else "")
    return True, ""


__all__ = ["COPIED", "cited_problems", "ground", "ground_fabula", "shown"]


# ---- the cases (lane W2-X4) ----

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
