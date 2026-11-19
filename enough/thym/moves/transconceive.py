"""The moves of a transconception (Thym 20.10; MacroCOSM OES 18.4.9), each `since: 1`: the ground (lane W2-X2)
and the cases (lane W2-X4) of the 0.8 build, joined by the conductor. The two parts follow in that order, each with
its own account below; the target (`weigh f in <language>`, lane W3-X5) follows them, its account in its comments,
and then entailing into a language (`entail f as layout in <language>`, `entail f as code in <language> with layout`,
lane W3-X6), its account in its comments.


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

`ground` reads no file and imports nothing outside `enough.thym` and `enough.macrocosm` (the package Comprise
vendors). Two moves of the cases below are the exceptions, and read beside their values on disk: `entail f as cases`
the cases file already beside the fabulac (`_existing_cases`, so that what was recorded is kept), and `gather
recorded` the recorder's `environment.txt` beside its folder (`_folder_files`). `ground` reaches the files and the catalogue through the host's engines (`enough.repo_engine`,
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
    """The cshort the verdict judged carries evidence: its level (0 to 6), its counts (agree no more than kept),
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
            and (label is None or tc.cshort_label(e) == label)]       # `evidence: []` is not written yet
    if not rows:
        return False, f"no cshort {label} carries evidence" if label else "no cshort carries evidence"
    ev = rows[-1]["evidence"]
    lv, st, wh = ev.get("level"), ev.get("steps"), ev.get("where")
    if not (isinstance(lv, int) and 0 <= lv <= 6):                 # MacroCOSM 18.4.9's seven levels
        return False, "evidence.level is 0 to 6"
    if not (isinstance(st, dict) and isinstance(st.get("kept"), int) and isinstance(st.get("agree"), int)
            and 0 <= st["agree"] <= st["kept"]):
        return False, "evidence.steps is {kept, agree}, agree no more than kept"
    if not (isinstance(wh, dict) and wh.get("file") and wh.get("digest")):
        return False, "evidence.where names the verdict file and its digest"
    if digest is not None and wh["digest"] != digest:
        return False, f"evidence.where.digest is {str(wh['digest'])[:12]}, the verdict's {digest[:12]}"
    return True, ""


__all__ += ["CASES_SCAFFOLD", "ENGINE", "entail_cases", "gather_outside", "gather_recorded", "gather_verdict"]


# ---- the target (lane W3-X5) ----

from enough.thym.moves import answer_mapping, model_of  # noqa: E402  (the target part's own, beside the cases part)
from enough.thym.registry import Request  # noqa: E402
#
# **`weigh f in <language>`** (Thym 6.3, 20.10; MacroCOSM OES 18.4.9, "Weighing a target"), fabula -> fabula, asks:
# the fabulac with one `N:target` for the language named, dated, beside any earlier weighing of it (a later weighing
# adds its own and rewrites none; an unweighed placeholder of the language, an `N:target` with no verdict, is the one
# it fills). Rules first, from the language's target table (`defaults/cosm/ground/targets/<language>.cosm`, reached
# through the transconception engine's `target_table`, recorded with the run): the points that are facts of the
# language alone (1, 2, 3, 7, 8), one `provides` row for every reliance (by its `entry`, or by the ground entries made
# from the experiment's reliance of that id), the gaps those rows name, and point 4 from the rows once every row is
# there. Then a model, under contract, for what rules cannot answer: the program's points (5, 6, 9, 10, 11, 12), a
# row for each reliance no entry answers, the spike (the riskiest use, entailed small and judged outside), the
# conditions it sees. Every interface and behaviour kept gets a row of its own (the new program writes it). Each
# score and each row says who answered it (`answered: rules | model`), and the target bank asks the transconceiver
# to rule each point (`weighed[n].ruled`). The verdict is the rules': `not` when a gate (1, 4, 5) scores 0 or the
# model finds it so, `feasible-with` when a gap or a condition is named, else `feasible`. The spike starts at level 0;
# its level comes from the judge's verdict on it (`enough.transconception.spike_from_verdict`), never from a model.
#
# The checks: `target-weighed` (Thym 7.3: language and version named, the twelve points each scored 0 to 3 with its
# evidence, a row for every reliance, interface and behaviour kept, the verdict `not` when a gate fails), and
# weigh's own reading of `no-invention` (the fabulac comes back as it went in but for the one target, and every id
# the target names is an item of it).

#: The twelve points (number, key, words, gate, the evidence that counts), MacroCOSM OES 18.4.9's table in its order;
#: `enough.transconception.POINTS` holds the same first four columns (a test holds them equal).
TARGET_POINTS = (
    (1, "stewardship", "Stewardship that outlives one company", True,
     "a foundation or a standards body, a published way of deciding, ten years of releases"),
    (2, "specification", "A written specification, and more than one implementation", False,
     "the text, and a second program that follows it"),
    (3, "old-programs-build", "A promise that old programs keep building", False,
     "the published promise, and programs five to ten years old that still build"),
    (4, "provided", "Everything the program leans on is provided", True,
     "for each dependency and each kept reliance: built in, a maintained library, a binding, or an estimate to "
     "write it, as the target's provides says"),
    (5, "runs-and-ships", "It runs where it must and ships as it must", True,
     "support for every system required, in the form required"),
    (6, "fits-shapes", "It fits the program's shapes", False,
     "how it holds memory and does many things at once, set against the program's structures"),
    (7, "safe-by-default", "Safe by default", False,
     "memory safety with no way around it, checked against the rules then in force"),
    (8, "tools-check", "Its tools can check what the fabulac states", False,
     "how much of the stated intent a type checker or another tool verifies"),
    (9, "agent-skill", "The writing agent's skill in it", False,
     "a pass rate measured at the time, on tasks the agent has not seen"),
    (10, "budgets", "It meets the budgets", False, "time, memory and start-up measured in a spike, with room to spare"),
    (11, "readable", "People can read it", False, "the transconceiver and the later maintainers can review it"),
    (12, "can-be-left", "It can be left", False, "how hard it would be to leave it for another language"),
)
WEIGH_GATES = tuple(p[0] for p in TARGET_POINTS if p[3])
#: The points a target table answers (facts of the language alone); point 4 is read from the rows.
TABLE_POINTS = (1, 2, 3, 7, 8)
MODEL_POINTS = tuple(p[0] for p in TARGET_POINTS if p[0] not in TABLE_POINTS + (4,))
PROVIDED_BY = ("built-in", "library", "binding", "written", "cannot", "dropped")
WEIGH_VERDICTS = ("feasible", "feasible-with", "not")
_KEPT_RULINGS = ("kept", "alike", "kept-wrong")
#: How hard a provider is, to pick the one row that answers a reliance several entries were made from.
_HARDER = {"built-in": 0, "dropped": 0, "written": 1, "binding": 2, "library": 2, "cannot": 3}
_POINT_KEY = {p[1]: p[0] for p in TARGET_POINTS}
_IDS = re.compile(r"\b[A-Z]:[a-z][a-z0-9-]*/[A-Za-z0-9_.:-]*[A-Za-z0-9_]")

WEIGH_SAYS = (
    "Weigh one language as the target of a transconception: the program the fabulac states, written again in "
    "{language}. The rules have answered what they can (answered); answer the rest. Reply with one YAML mapping:\n"
    "weighed: one entry for each point in points, {point: <its number>, score: 0 to 3, evidence: <what you know that "
    "bears on it, in plain words>}. A score of 0 on a gate means the language cannot be the target.\n"
    "provides: one entry for each item in open, {for: <its id>, by: built-in | library | binding | written | cannot "
    "| dropped, what: <what gives it in {language}>, note: <optional>, gap: <what must be fetched, bound or written "
    "at length first; optional>}.\n"
    "spike: {use: <the riskiest use, in a sentence: what the program leans on that {language} gives least easily>, "
    "cases: [<ids of the P:case items that exercise it, from cases>]}.\n"
    "conditions: [<anything the new program must do or avoid in {language} to keep what is kept, one sentence each>].\n"
    "verdict: feasible | feasible-with | not.\n"
    "Name only items the fabulac holds. Do not answer a point the rules answered.")


def point_of(p: Any) -> int | None:
    """A weighed point's number, from its number or the experiment's key (`stewardship` is 1)."""
    if isinstance(p, bool):
        return None
    if isinstance(p, int):
        return p if 1 <= p <= 12 else None
    if isinstance(p, str):
        t = p.strip().lower()
        return int(t) if t.isdigit() and 1 <= int(t) <= 12 else _POINT_KEY.get(t)
    return None


def _word(v: Any) -> str | None:
    if isinstance(v, Value):
        v = plain(v)
    return v.strip().lower() if isinstance(v, str) and v.strip() else None


def _rulings_of(d: dict) -> list[dict]:
    r = d.get("ruling")
    rs = r if isinstance(r, list) else ([r] if isinstance(r, dict) else [])
    return [x for x in rs if isinstance(x, dict) and "pending" not in x and x.get("is")]


def ruled_state(d: dict, target_ref: str | None) -> str:
    """How an item stands for a target: `kept` (a kept, alike or kept-wrong ruling holds for it), `changed`, `free`,
    or `unruled` (no ruling holds for it yet: proposed kept, so weighed as kept)."""
    hold = [x for x in _rulings_of(d) if x.get("made-for") in (None, target_ref)]
    if not hold:
        return "unruled"
    if any(x["is"] in _KEPT_RULINGS for x in hold):
        return "kept"
    return "changed" if any(x["is"] == "changed" for x in hold) else "free"


def _first_target(items: list[dict], language: str) -> dict | None:
    return next((it for it in items if item_kind(it) == "target" and str(it.get("language") or "").lower() == language),
                None)


def _target_id(items: list[dict], language: str) -> tuple[str, dict | None]:
    """The id the weighing takes, and the unweighed placeholder it fills (None when it adds a new item)."""
    ws = [it for it in items if item_kind(it) == "target" and str(it.get("language") or "").lower() == language]
    blank = next((it for it in ws if "verdict" not in it), None)
    if blank is not None:
        return str(blank["id"]), blank
    taken = {str(it.get("id")) for it in items}
    base = f"N:target/{language}"
    if base not in taken:
        return base, None
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}", None


def _table_rows(answer: dict) -> tuple[dict[str, dict], dict[str, list[str]]]:
    table = answer.get("table") or {}
    rows = {str(r.get("entry")): r for r in table.get("provides") or [] if isinstance(r, dict) and r.get("entry")}
    frm = {str(k): [str(x) for x in v] for k, v in (answer.get("from") or {}).items() if isinstance(v, list)}
    return rows, frm


def _row_for_reliance(d: dict, rows: dict[str, dict], frm: dict[str, list[str]]) -> tuple[dict | None, list[str]]:
    """The table's row that answers a reliance: its entry's, else the hardest of the entries made from the
    experiment's reliance of its id; and the entries read."""
    entry = d.get("entry")
    if isinstance(entry, str) and entry in rows:
        return rows[entry], [entry]
    bare = str(d.get("id", "")).split("/", 1)[-1]
    names = frm.get(bare) or frm.get(bare.rsplit(".", 1)[-1]) or []
    hits = [rows[e] for e in names if e in rows]
    if not hits:
        return None, []
    best = max(hits, key=lambda r: _HARDER.get(str(r.get("by")), 1))
    return best, [e for e in names if e in rows]


def _point4(rows: list[dict], items_by: dict[str, dict], target_ref: str | None) -> dict:
    """Point 4 by rules, from the rows: 0 when anything kept is `cannot`, 2 when a gap is named, else 3."""
    kept_rows = [r for r in rows if ruled_state(items_by.get(r["for"], {}), target_ref) != "free"]
    rel = [r for r in kept_rows if str(r["for"]).startswith("C:reliance/")]
    counts = {b: sum(1 for r in rel if r.get("by") == b) for b in PROVIDED_BY}
    cannot = [r["for"] for r in kept_rows if r.get("by") == "cannot"]
    gaps = [r["for"] for r in kept_rows if r.get("gap")]
    said = ", ".join(f"{n} {b}" for b, n in counts.items() if n) or "nothing"
    if cannot:
        return {"point": 4, "score": 0, "evidence": f"nothing provides {', '.join(cannot[:5])}, which is kept "
                                                   f"(reliances: {said})", "answered": "rules"}
    ev = f"every reliance kept is provided: {said}; none cannot"
    if gaps:
        return {"point": 4, "score": 2, "evidence": f"{ev}; gaps: {', '.join(gaps[:8])}", "answered": "rules"}
    return {"point": 4, "score": 3, "evidence": ev, "answered": "rules"}


def weigh_rules(cat: dict, items: list[dict], language: str, answer: dict) -> dict:
    """The pure part of `weigh` before the model: `{target, open-points, open-rows, gaps}`. `target` is the `N:target`
    so far (its id, the table's version, the points the table answers, a row for every reliance an entry answers and
    for every interface and behaviour kept); `open-points` and `open-rows` are what the model is asked; `gaps` the
    rows that name one (for a reliance not ruled free)."""
    if not isinstance(answer, dict) or not answer.get("ok"):
        why = answer.get("why") if isinstance(answer, dict) else None
        raise MoveError(why or f"nothing says what {language} provides: no target table came back")
    table = answer.get("table") or {}
    title = (answer.get("language") or {}).get("title") or language
    tid, blank = _target_id(items, language)
    first = _first_target(items, language)
    rref = str(first["id"]) if first else tid                      # rulings are made for the language's first target
    rows, frm = _table_rows(answer)
    out_rows: list[dict] = []
    open_rows: list[str] = []
    for d in items:
        k, iid = item_kind(d), str(d.get("id"))
        if k == "reliance":
            row, read = _row_for_reliance(d, rows, frm)
            if row is None:
                open_rows.append(iid)
                continue
            r = {"for": iid, "by": row.get("by"), "what": row.get("what")}
            state = ruled_state(d, rref)
            note = row.get("note")
            if state == "free":
                note = f"free for {title}" + (f"; {note}" if note else "")
            if note:
                r["note"] = note
            if row.get("gap") and state != "free":
                r["gap"] = row["gap"]
            if read and read != [d.get("entry")]:
                r["entry"] = read[0] if len(read) == 1 else read
            r["answered"] = "rules"
            out_rows.append(r)
        elif k in ("interface", "behaviour") and ruled_state(d, rref) in ("kept", "unruled"):
            what = "the new program's own " + (str(d.get("surface")) if k == "interface" and d.get("surface")
                                               else ("interface" if k == "interface" else "behaviour"))
            out_rows.append({"for": iid, "by": "written", "what": what, "answered": "rules"})
    weighed = []
    for p in table.get("points") or []:
        n = point_of(p.get("point")) if isinstance(p, dict) else None
        if n in TABLE_POINTS:
            weighed.append({"point": n, "score": p.get("score"), "evidence": p.get("evidence"), "answered": "rules"})
    have = {w["point"] for w in weighed}
    open_points = [n for n, *_ in TARGET_POINTS if n not in have and n != 4]
    target: dict = {"id": tid, "type": "target", "name": language}
    if blank is not None:
        target.update({k: v for k, v in blank.items() if k not in ("id", "type", "weighed", "summary", "provenance")})
    target.update({"language": language, "version": str(table.get("version") or "")})
    target["weighed"] = weighed
    target["provides"] = out_rows
    items_by = {str(it.get("id")): it for it in items}
    gaps = [r for r in out_rows if r.get("gap")]
    return {"target": target, "open-points": open_points, "open-rows": open_rows, "gaps": gaps, "rulings-for": rref,
            "title": title, "items": items_by}


def _program_brief(cat: dict, items: list[dict], gaps: list[dict]) -> str:
    """What the fabulac holds that a weighing needs (MacroCOSM 18.4.9): the kind of program, its ways in, its
    dependencies and requirements, the gaps the rules found, and the cases there are to aim a spike at."""
    lines: list[str] = []
    atem = cat.get("atem") if isinstance(cat.get("atem"), dict) else {}
    for k in ("line", "focus"):
        if isinstance(atem.get(k), str):
            lines.append(f"{k}: {atem[k]}")
    by = {str(it.get("id")): it for it in items}
    for kind, label in (("interface", "ways in"), ("dependency", "dependencies"), ("requirement", "requirements")):
        got = [it for it in items if item_kind(it) == kind]
        if kind == "interface":
            got = [it for it in got if it.get("surface") in ("command", "format", "stream")] or got[:20]
        if got:
            lines.append(f"{label}:")
            lines += [f"  - {it.get('id')}: {it.get('name')} ({it.get('surface') or it.get('scope') or it.get('force') or ''})"
                      for it in got[:40]]
    if gaps:
        lines.append("gaps the rules found:")
        lines += [f"  - {g['for']}: {by.get(g['for'], {}).get('name', '')}: {g['gap']}" for g in gaps]
    cases = [it for it in items if item_kind(it) == "case"]
    if cases:
        lines.append("cases:")
        lines += [f"  - {it.get('id')}: {it.get('name')}" for it in cases[:60]]
    return "\n".join(lines)


def weigh_request_inputs(cat: dict, items: list[dict], language: str, partial: dict) -> dict:
    """The model's inputs for what the rules left open (plain strings)."""
    t = partial["target"]
    by = partial["items"]
    pts = [f"{n}. {w}{' (a gate)' if g else ''}: the evidence that counts is {e}" for n, _k, w, g, e in TARGET_POINTS
           if n in partial["open-points"]]
    answered = mc.dump({"weighed": [{k: w[k] for k in ("point", "score", "evidence")} for w in t["weighed"]],
                        "provides": [{k: r[k] for k in ("for", "by", "what") if k in r} for r in t["provides"]
                                     if str(r["for"]).startswith("C:reliance/")]})
    open_ = "\n".join(f"- {iid}: {by.get(iid, {}).get('name', '')}: {by.get(iid, {}).get('gives') or by.get(iid, {}).get('summary') or ''}"
                      for iid in partial["open-rows"]) or "(none)"
    return {"fabulac": str(cat.get("name") or cat.get("id") or "the fabulac"), "language": language,
            "version": str(t.get("version") or ""), "points": "\n".join(pts), "answered": answered, "open": open_,
            "program": _program_brief(cat, items, partial["gaps"])}


def parse_weigh(out: Any, partial: dict) -> dict:
    """A model's reply read into the target: the open points and rows, the spike, the conditions and its verdict.
    A ValueError (asked again) for a reply that misses an open point or row, scores out of 0 to 3, names an item the
    fabulac lacks, or gives a provider outside the list."""
    data = answer_mapping(out)
    by = partial["items"]
    want_p, want_r = set(partial["open-points"]), set(partial["open-rows"])
    got_p: dict[int, dict] = {}
    for w in data.get("weighed") or []:
        n = point_of(w.get("point")) if isinstance(w, dict) else None
        if n is None or n not in want_p:
            continue                                     # a point the rules answered is the rules'
        sc = w.get("score")
        if isinstance(sc, bool) or sc not in (0, 1, 2, 3):
            raise ValueError(f"point {n}: a score is a whole number from 0 to 3, not {sc!r}")
        ev = w.get("evidence")
        if not (isinstance(ev, str) and ev.strip()):
            raise ValueError(f"point {n}: a score carries its evidence")
        got_p[n] = {"point": n, "score": sc, "evidence": ev.strip(), "answered": "model"}
    if want_p - set(got_p):
        raise ValueError(f"the reply scores no point {', '.join(map(str, sorted(want_p - set(got_p))))}")
    got_r: dict[str, dict] = {}
    for r in data.get("provides") or []:
        if not isinstance(r, dict) or r.get("for") not in want_r:
            if isinstance(r, dict) and r.get("for") not in by:
                raise ValueError(f"provides names {r.get('for')!r}, which the fabulac does not hold")
            continue
        if r.get("by") not in PROVIDED_BY:
            raise ValueError(f"{r['for']}: by is one of {', '.join(PROVIDED_BY)}, not {r.get('by')!r}")
        if not (isinstance(r.get("what"), str) and r["what"].strip()):
            raise ValueError(f"{r['for']}: a row says what provides it")
        row = {"for": r["for"], "by": r["by"], "what": r["what"].strip()}
        for k in ("note", "gap"):
            if isinstance(r.get(k), str) and r[k].strip():
                row[k] = r[k].strip()
        if r["by"] in ("library", "binding", "cannot") and "gap" not in row:
            row["gap"] = f"{r['by']}: {row['what']}"
        row["answered"] = "model"
        got_r[r["for"]] = row
    if want_r - set(got_r):
        raise ValueError(f"the reply has no row for {', '.join(sorted(want_r - set(got_r))[:5])}")
    sp = data.get("spike") if isinstance(data.get("spike"), dict) else {}
    cases = [str(c) for c in sp.get("cases") or [] if isinstance(c, str)]
    bad = [c for c in cases if c not in by]
    if bad:
        raise ValueError(f"the spike names {', '.join(bad[:3])}, which the fabulac does not hold")
    conds = [str(c).strip() for c in data.get("conditions") or [] if isinstance(c, str) and c.strip()]
    verdict = data.get("verdict")
    if verdict is not None and verdict not in WEIGH_VERDICTS:
        raise ValueError(f"the verdict is one of {', '.join(WEIGH_VERDICTS)}, not {verdict!r}")
    return {"points": got_p, "rows": got_r, "spike": {"use": str(sp.get("use") or "").strip(), "cases": cases},
            "conditions": conds, "verdict": verdict}


def weigh_finish(partial: dict, reply: dict, *, at: str, made: dict, sources: list[str]) -> dict:
    """The `N:target` whole: the rules' answers and the model's, point 4 and the verdict by rule."""
    t = copy.deepcopy(partial["target"])
    by = partial["items"]
    rows = list(t["provides"])
    order = {str(it_id): i for i, it_id in enumerate(by)}
    rows += list(reply["rows"].values())
    rows.sort(key=lambda r: order.get(r["for"], len(order)))
    weighed = {w["point"]: w for w in t["weighed"]}
    weighed.update(reply["points"])
    weighed[4] = _point4(rows, by, partial["rulings-for"])
    t["weighed"] = [weighed[n] for n, *_ in TARGET_POINTS if n in weighed]
    t["provides"] = rows
    gaps = [r for r in rows if r.get("gap") and ruled_state(by.get(r["for"], {}), partial["rulings-for"]) != "free"]
    conds = [f"{r['for']} ({by.get(r['for'], {}).get('name', '')}): {r['gap']}" for r in gaps] + reply["conditions"]
    gate_fail = [w["point"] for w in t["weighed"] if w["point"] in WEIGH_GATES and w.get("score") == 0]
    if gate_fail or reply.get("verdict") == "not":
        verdict = "not"
    elif gaps or reply["conditions"] or reply.get("verdict") == "feasible-with":
        verdict = "feasible-with"
    else:
        verdict = "feasible"
    sp = reply["spike"]
    use = sp["use"] or (f"the riskiest gap, {gaps[0]['for']}" if gaps else "the program's riskiest use")
    spike = {"use": use, "level": 0, "where": None}
    if sp["cases"]:
        spike["cases"] = sp["cases"]
    title = partial["title"]
    words = {"feasible": "feasible", "feasible-with": f"feasible with {len(gaps) or len(conds)} named "
                                                     f"gap{'s' if (len(gaps) or len(conds)) != 1 else ''}",
             "not": "not feasible" + (f" (gate {', '.join(map(str, gate_fail))} scored 0)" if gate_fail else "")}
    t["summary"] = f"Weighed for a transconception into {title}: {words[verdict]}."
    t["stance"] = "deduced"
    t["spike"] = spike
    t["verdict"] = verdict
    if conds:
        t["conditions"] = conds
    else:
        t.pop("conditions", None)
    t["at"] = at
    t["made"] = made
    t["provenance"] = {"mode": "derived", "sources": sources, "confidence": 0.7, "state": "known"}
    return t


def _with_target(cat: dict, items: list[dict], target: dict, run: dict | None) -> Value:
    c = copy.deepcopy(cat)
    if run:
        c.setdefault("derived", {}).setdefault("runs", []).append({k: v for k, v in run.items() if v})
    out = [copy.deepcopy(it) for it in items]
    for i, it in enumerate(out):
        if it.get("id") == target["id"]:
            out[i] = target
            break
    else:
        last = max((i for i, it in enumerate(out) if item_kind(it) == "target"), default=None)
        out.insert(last + 1 if last is not None else len(out), target)
    return Value("fabula", {**c, "nodes": out}, origin={"weighed": {"target": target["id"]}})


@implements("weigh")
def weigh(ctx: Any, f: Value, **mods: Any) -> Request | Value:
    """`weigh f in <language>` (Thym 20.10): one dated `N:target` for the language, rules first, then a model for
    the points and rows the rules cannot answer, every answer marked for the transconceiver's ruling."""
    language = _word(mods.get("in"))
    if language is None:
        raise MoveError("weigh names the language it weighs: weigh f in go")
    cat, items = _fabula(f, "weigh weighs a fabulac: weigh f in go")
    _need_fabulac(cat, "f", "weigh weighs a fabulac kept for transconception")
    if cat.get("purpose") != "transconception":
        raise MoveError("f is not kept for transconception (its catalog says no purpose: transconception): a "
                        "language is weighed for a transconception")
    src = cat.get("source") if isinstance(cat.get("source"), dict) else {}
    source_language = str(src.get("language") or "").lower() or None
    if language == source_language:
        raise MoveError(f"{language} is f's own language: the round trip entails into it, unweighed")
    answer = _tc(ctx).target_table(language, source=source_language)
    partial = weigh_rules(cat, items, language, answer)
    now = getattr(ctx, "now", None)
    at = now.date().isoformat() if now is not None else "1970-01-01"
    run_id = getattr(ctx, "run", None)
    table_src = f"defaults/cosm/ground/targets/{language}.cosm"

    def finish(reply: dict, model: str | None) -> Value:
        engine_word = "rules" + (f"+model:{model}" if model else "+model")
        made = {k: v for k, v in {"move": "weigh", "in": language, "run": run_id, "engine": engine_word}.items() if v}
        t = weigh_finish(partial, reply, at=at, made=made, sources=[table_src, "MacroCOSM OES 18.4.9"])
        run = {"program": _program(ctx), "run": run_id, "at": stamp_at(ctx), "model": model}
        return _with_target(cat, items, t, run)

    inputs = {k: Value("string", v) for k, v in weigh_request_inputs(cat, items, language, partial).items()}
    schema = {"format": "yaml", "stamp": "engine", "says": WEIGH_SAYS.replace("{language}", partial["title"])}

    def parse(out: Any) -> Value:
        reply = parse_weigh(out, partial)
        return finish(reply, model_of(answer_mapping(out)))
    return Request(contract={"schema": schema, "repair": []}, inputs=inputs, parse=parse)


def weighed_problems(target: dict, items: list[dict]) -> list[str]:
    """`target-weighed` over one `N:target` and the fabula's items: one line per problem, none when it holds."""
    out: list[str] = []
    tid = target.get("id")
    for k in ("language", "version"):
        if not (isinstance(target.get(k), str) and target[k].strip()):
            out.append(f"{tid}: names no {k}")
    seen: dict[int, dict] = {}
    for i, w in enumerate(target.get("weighed") or [] if isinstance(target.get("weighed"), list) else []):
        n = point_of(w.get("point")) if isinstance(w, dict) else None
        if n is None:
            out.append(f"{tid}.weighed[{i}]: a point is one of the twelve, by its number")
            continue
        if n in seen:
            out.append(f"{tid}.weighed[{i}]: point {n} is scored twice")
        seen[n] = w
        sc = w.get("score")
        if isinstance(sc, bool) or sc not in (0, 1, 2, 3):
            out.append(f"{tid}: point {n}'s score is a whole number from 0 to 3")
        if not (isinstance(w.get("evidence"), str) and w["evidence"].strip()):
            out.append(f"{tid}: point {n} carries no evidence")
    missing = [n for n, *_ in TARGET_POINTS if n not in seen]
    if missing:
        out.append(f"{tid}: weighs no point {', '.join(map(str, missing))} of the twelve")
    language = str(target.get("language") or "").lower()
    first = _first_target(items, language) if language else None
    rref = str(first["id"]) if first else tid
    rows = {r.get("for") for r in target.get("provides") or [] if isinstance(r, dict) and r.get("by") in PROVIDED_BY}
    for d in items:
        k = item_kind(d)
        if k not in ("reliance", "interface", "behaviour"):
            continue
        if ruled_state(d, rref) == "kept" and d.get("id") not in rows:
            out.append(f"{tid}: provides says nothing of {d.get('id')}, which is kept")
    gate_fail = [n for n in WEIGH_GATES if n in seen and seen[n].get("score") == 0]
    v = target.get("verdict")
    if v not in WEIGH_VERDICTS:
        out.append(f"{tid}: its verdict is one of {', '.join(WEIGH_VERDICTS)}")
    elif gate_fail and v != "not":
        out.append(f"{tid}: gate point {', '.join(map(str, gate_fail))} scored 0, so the verdict is not, not {v}")
    if v == "feasible-with" and not target.get("conditions"):
        out.append(f"{tid}: feasible-with names its conditions")
    return out


def _weighed_target(output: Value, inputs: dict) -> tuple[dict | None, list[dict], str]:
    """The `N:target` a weighing wrote (the one in the output that the input fabula did not hold as it is)."""
    _cat, items = fabula_doc(output)
    items = [plain(it) for it in items]
    before = next((v for v in inputs.values() if isinstance(v, Value) and v.type == "fabula"), None)
    old = {str(it.get("id")): plain(it) for it in fabula_doc(before)[1]} if before is not None else {}
    new = [it for it in items if item_kind(it) == "target" and _same(old.get(str(it.get("id")))) != _same(it)]
    if len(new) != 1:
        return None, items, f"a weighing writes one N:target, and {len(new)} came back new"
    return new[0], items, ""


@check("target-weighed")
def _target_weighed(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """The `N:target` a weighing writes names its language and the version weighed; `weighed` holds one entry for each
    of the twelve points, each scored 0 to 3 with its evidence; `provides` says how the language gives every reliance,
    interface and behaviour ruled kept; its verdict is `not` when a gate point fails (Thym 7.3; MacroCOSM 18.4.9)."""
    t, items, why = _weighed_target(output, inputs)
    if t is None:
        return False, why
    probs = weighed_problems(t, items)
    if probs:
        return False, "; ".join(probs[:3]) + (f" (and {len(probs) - 3} more)" if len(probs) > 3 else "")
    return True, ""


def _same(x: Any) -> Any:
    """An item (or a field) as plain data, so that a fabula read from a file and the same fabula handed on in a run
    compare alike; an item's `made` is the runtime's stamp (the law of provenance), never the move's change."""
    if isinstance(x, dict) and "id" in x:
        x = {k: v for k, v in x.items() if k != "made"}
    return json.loads(json.dumps(x, sort_keys=True, default=str)) if x is not None else None


@check("no-invention", kind="move:weigh")
def _weigh_no_invention(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """`no-invention` as a weighing holds it: the fabulac comes back as it went in, but for the one `N:target` it
    writes; and every id that target names (`provides.for`, the spike's cases, an id in its words) is an item of the
    fabulac. What a language provides is knowledge of the language, not of the program: the program's own items are
    what a weighing may not invent."""
    t, items, why = _weighed_target(output, inputs)
    if t is None:
        return False, why
    before = next((v for v in inputs.values() if isinstance(v, Value) and v.type == "fabula"), None)
    if before is not None:
        old = [plain(it) for it in fabula_doc(before)[1]]
        now = {str(it.get("id")): it for it in items}
        changed = [o for o in old if o.get("id") != t["id"] and _same(now.get(str(o.get("id")))) != _same(o)]
        if changed:
            o = changed[0]
            n = now.get(str(o.get("id"))) or {}
            fld = next((k for k in list(o) + list(n) if _same(o.get(k)) != _same(n.get(k))), None)
            return False, (f"the weighing changed {', '.join(str(c.get('id')) for c in changed[:3])} (the first at "
                           f"{fld}): it writes its N:target and nothing else")
        if len(items) - len(old) not in (0, 1):
            return False, "the weighing added items beside its N:target"
    ids = {str(it.get("id")) for it in items}
    named = [r.get("for") for r in t.get("provides") or [] if isinstance(r, dict)]
    sp = t.get("spike") if isinstance(t.get("spike"), dict) else {}
    named += list(sp.get("cases") or [])
    named += _IDS.findall(mc.dump({k: t.get(k) for k in ("weighed", "spike", "conditions") if k in t}))
    bad = sorted({str(x) for x in named if str(x) not in ids})
    if bad:
        return False, f"the weighing names {', '.join(bad[:3])}, which the fabulac does not hold"
    return True, ""


__all__ += ["TARGET_POINTS", "parse_weigh", "weigh", "weigh_finish", "weigh_rules", "weighed_problems"]


# ---- entailing into a language (lane W3-X6) ----

from enough.thym.folder import Folder  # noqa: E402  (the entailing part's own, beside the target part)
from enough.thym.moves import entailment_of, short_value, utc_day  # noqa: E402
from enough.thym.moves.code import _yaml, fabulac_file, folder_of_texts, licence_line  # noqa: E402
#
# **`entail f as layout in <language>`** (Thym 6.3, 20.10; MacroCOSM OES 18.4.9), fabula -> short, asks once: the
# files of the program to be, in the order they are written, what each holds, the name each kept interface takes
# there, the target's own type for each item ruled `alike` with `own-types`, and what fills each gap the standing
# weighing names. A model proposes it as YAML; rules check it against the fabulac's kept interfaces (every one in a
# file, under a name; only items the fabulac holds) and write the short, which the host saves beside the fabulac as
# `<name>.layout-<language>-<stamp>.md`. Its footer is its last line: `*a layout of F, in Go, compiled on DAY by WHO*`.
#
# **`entail f as code in <language> with layout`**, fabula and short -> folder, asks once per file the layout names:
# the cshort, `<name>.cshort-<language>-<stamp>/` once the host lands it. Apart by default: each request carries the
# fabulac (spans, source paths, provenance and the R, D and H modules left out) and the layout, and nothing of the
# source; every request is kept in `requests.jsonl`, so that `apart` can be measured. Beside only where MacroCOSM OES
# permits it (the person's own code, or a source in the open lane) and only when the person asked, which a host says
# by giving the engine the source (`enough.transconception.thym_engine(beside=…)`): a program cannot ask for it, and a
# closed or bound lane is refused. Rules write `CSHORT.md` (the footer first, as every cshort's; the files with their
# sha256; the interface table `surface-answered` reads; the licence line last), `NOTES.md` (what the fabulac left
# unsaid: each file's guesses, as its writer wrote them down), `NOTICE` (the licence notice and credit of the source)
# and `requests.jsonl`. The cshort's entry for `shorts` rides on the value (`origin.entry`): `target`, `layout`,
# `entailed`, and `evidence: []`, since a cshort's evidence is read from the judge's verdict (`gather verdict with
# f`), never claimed. `parses` is not in the contract: the host reads no other language; whether the cshort builds is
# the outside runner's first level.
#
# Both open with `target-confirmed` for the language (gate 2's last check): refused, before a model is asked, until the
# language is weighed, feasible, and its spike has stood.

IN_STEPS = ("layout", "code-in")
#: The files rules write into a cshort in another language: never asked of a model, never named by a layout.
RULE_FILES = ("CSHORT.md", "NOTES.md", "NOTICE", "requests.jsonl")
#: What an item carries that names the source rather than the program: left out of a request entailed apart.
APART_DROP = ("span", "spans", "provenance", "defined-in", "files", "path", "file", "lines", "made", "stated",
              "contradicted-by", "first-line", "set-in", "worksheet-id", "digest", "sha256")
#: The modules a request entailed apart leaves out: who made the source, its dialectic, its history.
APART_SKIP = ("R", "D", "H")
_APART_KINDS_SKIP = ("file", "component", "change", "release", "phase", "event", "question")
_LAYOUT_FOOT = re.compile(r"^\*a layout of (?P<f>\S.*?), in (?P<lang>[^,]+), compiled on (?P<day>\d{4}-\d{2}-\d{2}) "
                          r"by (?P<who>.+)\*$")
_ORIGINAL = "a file of the original"


def _in_language(mods: dict, what: str) -> str:
    language = _word(mods.get("in"))
    if language is None:
        raise MoveError(f"{what} names the language: entail f as layout in go, entail f as code in go with layout")
    return language


def _transconception(f: Any, what: str) -> tuple[dict, list[dict]]:
    cat, items = _fabula(f, f"{what} entails a fabulac kept for transconception")
    _need_fabulac(cat, "f", f"{what} entails a fabulac")
    if cat.get("purpose") != "transconception":
        raise MoveError(f"f is not kept for transconception (its catalog says no purpose: transconception): {what} "
                        "entails a transconception")
    return cat, items


def _confirmed(ctx: Any, cat: dict, items: list[dict], language: str, what: str) -> tuple[Any, dict, dict, str]:
    """The engine, the language, the standing weighing and the id rulings are made for; a MoveError when the
    language is the source's own (the round trip is `entail f as code`), unknown, or not confirmed."""
    tc = _tc(ctx)
    src = cat.get("source") if isinstance(cat.get("source"), dict) else {}
    if language == str(src.get("language") or "").lower():
        raise MoveError(f"{language} is f's own language: its round trip is entail f as code, with no layout")
    info = tc.language_info(language)
    if not info.get("ok"):
        raise MoveError(info.get("why") or f"{language} is no language this build knows")
    if not info.get("target"):
        raise MoveError(f"{info['title']} is not a language a program is entailed into in this build")
    probs = tc.target_confirmed_problems(cat, items, language)
    if probs:
        raise MoveError(f"{what} in {language} waits for gate 2's target-confirmed: {probs[0]}"
                        + (f" (and {len(probs) - 1} more)" if len(probs) > 1 else ""))
    latest, rref = tc.standing_weighing(items, language)
    return tc, info, latest or {}, str(rref)


def _for_target(d: dict, rref: str) -> list[dict]:
    """An item's rulings that hold for the target, as a writer reads them."""
    keep = ("is", "allowing", "because", "to", "about", "steps", "said")
    return [{k: x[k] for k in keep if k in x} for x in _rulings_of(d) if x.get("made-for") in (None, rref)]


def _scrub(v: Any, paths: set[str]) -> Any:
    if isinstance(v, str):
        for p in sorted(paths, key=len, reverse=True):
            if p:
                v = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(p)}(?![A-Za-z0-9_])", _ORIGINAL, v)
        return v
    if isinstance(v, dict):
        return {k: _scrub(x, paths) for k, x in v.items()}
    if isinstance(v, list):
        return [_scrub(x, paths) for x in v]
    return v


def apart_view(d: dict, rref: str, paths: set[str]) -> dict:
    """An item as a request entailed apart carries it: without what names the source (spans, paths, provenance,
    citations), its rulings only those for the target, and any path of the source in its words said as "a file of the
    original"."""
    out = {k: v for k, v in d.items() if k not in APART_DROP and k != "ruling"}
    r = _for_target(d, rref)
    if r:
        out["ruling"] = r
    return _scrub(out, paths)


def _skipped(d: dict) -> bool:
    iid = str(d.get("id") or "")
    return iid[:1] in APART_SKIP or item_kind(d) in _APART_KINDS_SKIP


def _must_map(tc: Any, items: list[dict], rref: str) -> list[dict]:
    """The interfaces a layout and a cshort answer: kept or alike for the target, or not ruled for it yet (proposed
    kept, as the weighing read them)."""
    return [d for d in items if item_kind(d) == "interface" and tc.surface_kept(d, rref, unruled=True)]


def _own_types(items: list[dict], rref: str) -> list[dict]:
    return [d for d in items if any(x.get("is") == "alike" and x.get("allowing") == "own-types"
                                    for x in _for_target(d, rref))]


def _gaps(latest: dict, by: dict[str, dict], rref: str) -> list[dict]:
    """The standing weighing's gaps, for what is not ruled free: `{for, name, by, what, gap}`."""
    out = []
    for r in latest.get("provides") or []:
        if isinstance(r, dict) and r.get("gap") and ruled_state(by.get(str(r.get("for")), {}), rref) != "free":
            out.append({"for": r.get("for"), "name": by.get(str(r.get("for")), {}).get("name"), "by": r.get("by"),
                        "what": r.get("what"), "gap": r.get("gap")})
    return out


def _brief_item(d: dict, rref: str, paths: set[str]) -> dict:
    keep = ("id", "name", "summary", "surface", "signature", "takes", "gives", "raises", "fails", "plain", "means",
            "does", "when", "edges", "errors", "of", "key", "default", "kind", "fields")
    v = apart_view(d, rref, paths)
    return {k: v[k] for k in list(keep) + ["ruling"] if k in v}


def layout_inputs(cat: dict, items: list[dict], *, language: dict, latest: dict, rref: str, paths: set[str],
                  must: list[dict]) -> dict:
    """The layout request's inputs, as plain strings: the program (its atem and what it holds, apart), the interfaces
    to map, the items that take the target's own types, the gaps and the weighing's conditions."""
    by = {str(d.get("id")): d for d in items}
    program = {"atem": _scrub(cat.get("atem") or {}, paths),
               "interfaces": [_brief_item(d, rref, paths) for d in must],
               "structures": [_brief_item(d, rref, paths) for d in items if item_kind(d) == "structure"
                              and not _skipped(d)],
               "settings": [_brief_item(d, rref, paths) for d in items if item_kind(d) == "setting"][:60],
               "dependencies": [{k: d.get(k) for k in ("id", "name", "needed-for", "scope") if d.get(k)}
                                for d in items if item_kind(d) == "dependency"]}
    types = [{"for": d["id"], "name": d.get("name"), "ruling": _for_target(d, rref)} for d in _own_types(items, rref)]
    gaps = _gaps(latest, by, rref)
    return {"fabulac": "layout", "name": str(cat.get("name") or "the program"), "language": language["title"],
            "suffixes": ", ".join("." + s for s in language.get("suffixes") or []),
            "program": _yaml(_scrub(program, paths)),
            "map": "\n".join(f"- {d['id']}: {d.get('name') or ''}" for d in must),
            "types": _yaml(types) if types else "(none)", "gaps": _yaml(gaps) if gaps else "(none)",
            "conditions": _yaml(list(latest.get("conditions") or [])) if latest.get("conditions") else "(none)"}


def _rel_ok(p: Any) -> bool:
    return (isinstance(p, str) and bool(p) and p.strip() == p and not p.startswith(("/", "\\"))
            and ".." not in p.split("/") and "\\" not in p and p not in RULE_FILES and not p.endswith("/"))


def parse_layout(out: Any, *, must: list[str], types: list[str], gaps: list[str], ids: set[str],
                 suffixes: list[str]) -> dict:
    """A model's layout read and checked by rules: `{files: [{path, holds, interfaces: [{id, name}]}], types: [{for,
    type}], gaps: [{for, fill}]}`. A ValueError (asked again) for a file named twice or outside the cshort, a file the
    rules write, no file in the language, an interface to map that no file holds, an id the fabulac lacks, an own type
    or a gap left unanswered."""
    data = answer_mapping(out)
    files_in = data.get("files")
    if not isinstance(files_in, list) or not files_in:
        raise ValueError("files: the files of the program to be, in the order they are written")
    files: list[dict] = []
    seen: set[str] = set()
    where: dict[str, list[str]] = {}
    for i, f in enumerate(files_in):
        if not isinstance(f, dict) or not _rel_ok(f.get("path")):
            raise ValueError(f"files[{i}]: a path inside the program, not one of {', '.join(RULE_FILES)}")
        p = f["path"]
        if p in seen:
            raise ValueError(f"{p} is named twice")
        seen.add(p)
        ifs = []
        for x in f.get("interfaces") or []:
            if not (isinstance(x, dict) and isinstance(x.get("id"), str) and isinstance(x.get("name"), str)
                    and x["name"].strip()):
                raise ValueError(f"{p}: each interface it holds is {{id, name}}")
            if x["id"] not in ids:
                raise ValueError(f"{p} holds {x['id']}, which the fabulac does not hold")
            ifs.append({"id": x["id"], "name": x["name"].strip()})
            where.setdefault(x["id"], []).append(p)
        holds = f.get("holds")
        files.append({"path": p, "holds": holds.strip() if isinstance(holds, str) and holds.strip() else "",
                      "interfaces": ifs})
    if suffixes and not any(p.rsplit(".", 1)[-1] in suffixes for p in seen if "." in p):
        raise ValueError(f"no file is in the language: none ends in .{', .'.join(suffixes)}")
    missing = [m for m in must if m not in where]
    if missing:
        raise ValueError(f"no file holds {', '.join(missing[:5])}" + (f" (and {len(missing) - 5} more)"
                                                                      if len(missing) > 5 else ""))

    def pairs(key: str, val: str, want: list[str]) -> list[dict]:
        got: dict[str, str] = {}
        for x in data.get(key) or []:
            if not isinstance(x, dict):
                continue
            if x.get("for") not in ids:
                raise ValueError(f"{key} names {x.get('for')!r}, which the fabulac does not hold")
            if isinstance(x.get(val), str) and x[val].strip():
                got[str(x["for"])] = x[val].strip()
        left = [w for w in want if w not in got]
        if left:
            raise ValueError(f"{key}: no {val} for {', '.join(left[:5])}")
        return [{"for": k, val: v} for k, v in got.items()]
    return {"files": files, "types": pairs("types", "type", types), "gaps": pairs("gaps", "fill", gaps)}


def _cell(s: Any) -> str:
    return str(s or "").replace("\n", " ").replace("|", "\\|").strip()


def layout_text(layout: dict, *, name: str, fabulac: str, language: str, day: str, who: str) -> str:
    """The layout short (Thym 20.10): its files in the order they are written, its interface table (the plain form
    `surface-answered` reads), the own types, the gaps, and its footer last."""
    out = [f"# {name} in {language}: the layout", "",
           f"A layout of {fabulac} for its transconception into {language}: the files of the program to be, in the "
           "order they are written, what each holds, and the name each kept interface takes there. Written from the "
           "fabulac alone.", "", "## Files, in the order they are written", "", "| # | file | holds |",
           "|---|---|---|"]
    out += [f"| {i} | {_cell(f['path'])} | {_cell(f['holds'])} |" for i, f in enumerate(layout["files"], 1)]
    out += ["", "## Interfaces", "", "| interface | file | name |", "|---|---|---|"]
    out += [f"| {x['id']} | {_cell(f['path'])} | {_cell(x['name'])} |" for f in layout["files"]
            for x in f["interfaces"]]
    if layout.get("types"):
        out += ["", "## The target's own types", "", "| item | type |", "|---|---|"]
        out += [f"| {t['for']} | {_cell(t['type'])} |" for t in layout["types"]]
    if layout.get("gaps"):
        out += ["", "## Gaps, and what fills each", "", "| gap | fill |", "|---|---|"]
        out += [f"| {g['for']} | {_cell(g['fill'])} |" for g in layout["gaps"]]
    out += ["", f"*a layout of {fabulac}, in {language}, compiled on {day} by {who}*"]
    return "\n".join(out) + "\n"


def _table_cells(line: str) -> list[str] | None:
    s = line.strip()
    if not (s.startswith("|") and s.endswith("|") and len(s) > 1):
        return None
    parts = re.split(r"(?<!\\)\|", s[1:-1])
    return [p.replace("\\|", "|").strip() for p in parts]


def read_layout(text: str) -> dict:
    """A layout short read back (from this run or from its file): `{files, types, gaps, fabulac, language, day,
    who}`; a MoveError for a text that is no layout."""
    lines = text.replace("\r\n", "\n").split("\n")
    section, files, where, types, gaps = "", [], {}, [], []
    for ln in lines:
        if ln.startswith("## "):
            section = ln[3:].strip().lower()
            continue
        cells = _table_cells(ln)
        if cells is None or all(re.fullmatch(r":?-{3,}:?", c) for c in cells) \
                or cells[0] in ("#", "interface", "item", "gap"):
            continue
        if section.startswith("files") and len(cells) >= 3:
            files.append({"path": cells[1], "holds": cells[2], "interfaces": []})
        elif section == "interfaces" and len(cells) >= 3:
            where.setdefault(cells[1], []).append({"id": cells[0], "name": cells[2]})
        elif section.startswith("the target") and len(cells) >= 2:
            types.append({"for": cells[0], "type": cells[1]})
        elif section.startswith("gaps") and len(cells) >= 2:
            gaps.append({"for": cells[0], "fill": cells[1]})
    for f in files:
        f["interfaces"] = where.get(f["path"], [])
    foot = next((ln.strip() for ln in reversed(lines) if ln.strip()), "")
    m = _LAYOUT_FOOT.match(foot)
    if not files or m is None:
        raise MoveError("the layout is no layout: it names no file, or its last line is not a layout's footer")
    return {"files": files, "types": types, "gaps": gaps, "fabulac": m.group("f"), "language": m.group("lang"),
            "day": m.group("day"), "who": m.group("who")}


def entail_layout(ctx: Any, f: Value, **mods: Any) -> Request:
    """`entail f as layout in <language>`: the layout short, a model's proposal checked by rules."""
    language = _in_language(mods, "entail … as layout")
    cat, items = _transconception(f, "entail … as layout")
    tc, info, latest, rref = _confirmed(ctx, cat, items, language, "entail … as layout")
    paths = set(tc.source_paths(items))
    must = _must_map(tc, items, rref)
    inputs = layout_inputs(cat, items, language=info, latest=latest, rref=rref, paths=paths, must=must)
    by = {str(d.get("id")): d for d in items}
    want = {"must": [d["id"] for d in must], "types": [d["id"] for d in _own_types(items, rref)],
            "gaps": [str(g["for"]) for g in _gaps(latest, by, rref)], "ids": set(by), "suffixes": info["suffixes"]}
    fab_name = fabulac_file(cat, f)

    def parse(out: Any) -> Value:
        layout = parse_layout(out, **want)
        who = model_of(answer_mapping(out)) or "a model"
        text = layout_text(layout, name=str(cat.get("name") or "the program"), fabulac=fab_name,
                           language=info["title"], day=utc_day(ctx), who=who)
        return short_value(text, fabula=f, order="layout",
                           layout={"language": language, "rulings-for": rref, "weighing": latest.get("id"),
                                   "request": inputs, **layout})
    says = (f"the layout of the program in {info['title']}, as one YAML mapping: files (each {{path, holds, "
            "interfaces: [{id, name}]}, in the order they are written), types ([{for, type}]), gaps ([{for, fill}])")
    return Request(contract={"schema": {"format": "yaml", "stamp": "engine", "says": says}, "repair": []},
                   inputs={k: Value("string", v) for k, v in inputs.items()}, parse=parse)


def _layout_of(w: Any) -> dict:
    if not isinstance(w, Value) or w.type not in ("short", "text", "string"):
        raise MoveError("entail … as code in a language takes its layout with it: entail f as code in go with "
                        "layout, the short entail f as layout in go gave")
    return read_layout(w.text())


def _refs_of(d: dict) -> list[str]:
    out: list[str] = []
    for k in ("of", "used-by", "relied-by", "about", "shown-by"):
        v = d.get(k)
        for x in (v if isinstance(v, list) else [v]):
            if isinstance(x, str):
                out.append(x.split("#", 1)[0])
    return out


def file_brief(items: list[dict], layout: dict, path: str, *, rref: str, paths: set[str], latest: dict) -> dict:
    """What one file's request carries, apart (what made the experiment's writers succeed, x0 step A8): the
    interfaces the layout puts in it, with their rulings for the target; the behaviours, structures and settings about
    them; the reliances they lean on with what the standing weighing says provides each; the cases about them, which
    are the judge; the own types and gaps the layout gives; and the names the layout gives in the other files."""
    by = {str(d.get("id")): d for d in items}
    mine = next((f for f in layout["files"] if f["path"] == path), {"interfaces": []})
    ids = [x["id"] for x in mine["interfaces"]]
    near = set(ids)
    about = [d for d in items if item_kind(d) in ("behaviour", "structure", "setting", "requirement")
             and not _skipped(d) and set(_refs_of(d)) & near]
    near |= {str(d.get("id")) for d in about}
    leaned = [d for d in items if item_kind(d) in ("reliance", "assumption") and set(_refs_of(d)) & near]
    rows = {str(r.get("for")): r for r in latest.get("provides") or [] if isinstance(r, dict)}
    cases = [d for d in items if item_kind(d) == "case" and set(_refs_of(d)) & set(ids)]
    lean = []
    for d in leaned:
        row = {k: v for k, v in apart_view(d, rref, paths).items() if k in ("id", "name", "gives", "example", "ruling")}
        if d["id"] in rows:
            row["provided"] = {k: rows[d["id"]][k] for k in ("by", "what", "note", "gap") if k in rows[d["id"]]}
        lean.append(row)
    leaned_ids = {str(d.get("id")) for d in leaned}
    out: dict = {
        "file": {"path": path, "holds": mine.get("holds") or ""},
        "interfaces": [{**_brief_item(by[x["id"]], rref, paths), "takes the name": x["name"]}
                       for x in mine["interfaces"] if x["id"] in by],
        "about them": [_brief_item(d, rref, paths) for d in about],
        "they lean on": lean,
        "the cases, which are the judge": [_scrub({k: v for k, v in d.items() if k in ("id", "name", "of", "given",
                                                                                       "expect", "allowing", "stands")},
                                                  paths) for d in cases],
        "own types": [t for t in layout.get("types") or [] if t["for"] in near],
        "gaps": [g for g in layout.get("gaps") or [] if g["for"] in near or g["for"] in leaned_ids],
        "elsewhere": [{"file": f["path"], "names": [x["name"] for x in f["interfaces"]]}
                      for f in layout["files"] if f["path"] != path]}
    return {k: v for k, v in out.items() if v not in ([], "", None)}


_NOTES_HEAD = re.compile(r"^#{1,3}\s*notes\b.*$", re.I | re.M)


def file_and_notes(out: Any) -> tuple[str, list[str]]:
    """A writer's reply read: the file (its one fenced block, or the whole reply) and its notes (the bullets under a
    `## Notes` line after the block): what the fabulac left unsaid and what the writer chose."""
    s = out if isinstance(out, str) else (_yaml(out) if isinstance(out, dict) else str(out or ""))
    s = s.replace("\r\n", "\n")
    m = re.search(r"```[A-Za-z0-9_+.-]*\n(.*?)\n?```", s, re.S)
    body, rest = (m.group(1), s[m.end():]) if m else (s, "")
    if not m:
        h = _NOTES_HEAD.search(s)
        if h:
            body, rest = s[:h.start()], s[h.start():]
    notes: list[str] = []
    h = _NOTES_HEAD.search(rest)
    if h:
        for ln in rest[h.end():].split("\n"):
            t = ln.strip()
            if t.startswith(("- ", "* ")):
                notes.append(t[2:].strip())
            elif t and notes and not t.startswith("#"):
                notes[-1] += " " + t
    return body.rstrip("\n") + "\n", notes


def notice_text(cat: dict, items: list[dict], *, name: str, language: str, entailed: str, day: str) -> str:
    """`NOTICE`: the credit and the licence notice of the source, as MacroCOSM OES 18.4.9 asks a transconception to
    carry them: what it is a transconception of, under which terms, by whom, and what was read."""
    src = cat.get("source") if isinstance(cat.get("source"), dict) else {}
    lic = [d for d in items if item_kind(d) == "licence"]
    holders = [str(d.get("holder")) for d in lic if d.get("holder")]
    ident = ", ".join(str(d.get("identifier") or d.get("name")) for d in lic) or str(src.get("licence") or "")
    who = ", ".join(dict.fromkeys(holders)) or "its makers"
    of = str(src.get("name") or cat.get("name") or name)
    out = [f"{name}, in {language}, is a transconception of {of}" + (f" ({src['commit']})" if src.get("commit") else "")
           + f", by {who}, carried through its fabulac.", "",
           f"The source is under the {ident} licence." if ident else "The source's licence is not recorded.",
           ("It was written from the fabulac and its layout alone: no line of the source was read."
            if entailed == "apart" else "It was written from the fabulac and its layout, the source read beside them; "
            "no line of the source is copied.")]
    for d in lic:
        if d.get("year") or d.get("holder"):
            out += ["", " ".join(x for x in ("Copyright (c)", str(d.get("year") or ""), str(d.get("holder") or ""))
                                 if x)]
        notice = d.get("notice")
        if isinstance(notice, str) and notice.strip():
            out += ["", notice.strip()]
    out += ["", f"Entailed on {day}."]
    return "\n".join(out) + "\n"


def cshort_in_md(*, fabulac: str, language: str, day: str, who: str, name: str, entailed: str, layout_name: str,
                 files: list[tuple[str, str, str]], rows: list[tuple[str, str, str]], licence: str) -> str:
    """`CSHORT.md` of a cshort in another language: the footer first (MacroCOSM OES 18.4.7), what it is, the files
    with their sha256, the interface table (`surface-answered`), and the licence line last."""
    how = "from the fabulac and its layout alone" if entailed == "apart" else "the source read beside the fabulac"
    out = [f"*a cshort of {fabulac}, in {language}, compiled on {day} by {who}; never run*", "",
           f"{name} in {language}: a transconception, entailed {entailed} ({how}), laid out by {layout_name}. Never "
           "built or run here: building and judging it is the outside runner's. What the fabulac left unsaid, and "
           "what was chosen, is in NOTES.md; the source's licence notice and credit in NOTICE.", "",
           "| file | holds | sha256 |", "|---|---|---|"]
    out += [f"| {p} | {_cell(h)} | {sha} |" for p, h, sha in files]
    out += ["", "## Every kept interface, mapped", "", "| interface | file | name |", "|---|---|---|"]
    out += [f"| {i} | {_cell(p)} | {_cell(n)} |" for i, p, n in rows]
    out += ["", licence]
    return "\n".join(out) + "\n"


def entail_code_in(ctx: Any, f: Value, **mods: Any) -> Value:
    """`entail f as code in <language> with layout`: the cshort, one request per file the layout names, apart unless
    the host gives the source beside (the person asked, and MacroCOSM OES permits it)."""
    language = _in_language(mods, "entail … as code")
    cat, items = _transconception(f, "entail … as code in a language")
    tc, info, latest, rref = _confirmed(ctx, cat, items, language, "entail … as code")
    w = mods.get("with")
    layout = _layout_of(w)
    fab_name = fabulac_file(cat, f)
    if layout["fabulac"] != fab_name:
        raise MoveError(f"the layout is of {layout['fabulac']}, not {fab_name}")
    if layout["language"] != info["title"]:
        raise MoveError(f"the layout is in {layout['language']}, not {info['title']}")
    beside = getattr(tc, "beside", None)
    beside_files = beside() if callable(beside) else None
    entailed = "apart"
    if beside_files is not None:
        ok, why = tc.beside_allowed(cat, items)
        if not ok:
            raise MoveError(f"entailing beside the source is refused: {why}")
        entailed = "beside"
    paths = set(tc.source_paths(items))
    name = str(cat.get("name") or "the program")
    order = [x["path"] for x in layout["files"]]
    prev = getattr(ctx, "previous", None)
    texts: dict[str, str] = {}
    notes: dict[str, list[str]] = {}
    requests: list[str] = []
    meta: dict = {}
    if isinstance(prev, Value) and isinstance(prev.payload, Folder):
        texts = {p: prev.payload.text(p) for p in order if prev.payload.entry(p) is not None}
        meta = dict((prev.origin or {}).get("cshort") or {})
        notes = {k: list(v) for k, v in (meta.pop("notes", None) or {}).items()}
        if prev.payload.entry("requests.jsonl") is not None:
            requests = [ln for ln in prev.payload.text("requests.jsonl").split("\n") if ln.strip()]
    failed = getattr(ctx, "failed", None) or []
    redo = {p for p in order if any(p in str(x.get("why") or "") for x in failed if isinstance(x, dict))} \
        if texts else set(order)
    if texts and not redo:
        redo = set(order)
    layout_md = _scrub(w.text(), paths)
    for p in order:
        if p not in redo and p in texts:
            continue
        brief = file_brief(items, layout, p, rref=rref, paths=paths, latest=latest)
        inputs = {"fabulac": "code-in", "name": name, "language": info["title"], "path": p, "layout": layout_md,
                  "brief": _yaml(brief), "entailed": entailed}
        if entailed == "beside":
            inputs["source"] = "\n\n".join(f"--- {k} ---\n{v}" for k, v in sorted(beside_files.items()))
        line = json.dumps({"request": len(requests) + 1, "writes": p, "entailed": entailed, "inputs": inputs},
                          sort_keys=True)            # ASCII: one request is one line, whatever its text holds
        if entailed == "apart":
            bad = tc.apart_problems([line], paths, None)    # the length is the engine's own: a replay answers calls
            if bad:                      # never sent: a request entailed apart carries nothing of the source
                raise MoveError(f"the request for {p} would not be apart: {bad[0]}")
        requests.append(line)
        cand = ctx.ask({"schema": {"format": "markdown", "says": f"the whole of {p} in one fenced block, then what "
                                                                 "you chose where the fabulac is silent, under ## Notes"}},
                       {k: Value("string", v) for k, v in inputs.items()})
        texts[p], notes[p] = file_and_notes(cand.get("output") if isinstance(cand, dict) else None)
        eng = str(cand.get("engine") or "") if isinstance(cand, dict) else ""
        if eng.startswith("model:") and eng[6:] not in ("", "unknown"):
            meta.setdefault("model", eng[6:])
    who = str(meta.get("model") or "a model")
    day = utc_day(ctx)
    wp = getattr(w, "path", None)
    layout_name = Path(wp).name if wp is not None else f"its layout of {layout['day']}"
    rows = [(x["id"], fl["path"], x["name"]) for fl in layout["files"] for x in fl["interfaces"]]
    out = {p: texts[p] for p in order}
    out["NOTICE"] = notice_text(cat, items, name=name, language=info["title"], entailed=entailed, day=day)
    nb = [f"# What the fabulac left unsaid: {name} in {info['title']}", "",
          "Each file's writer wrote down here what the fabulac and its layout did not say, and what it chose: a guess "
          "is never silent.", ""]
    for p in order:
        nb += [f"## {p}", ""] + ([f"- {n}" for n in notes.get(p) or []] or ["- nothing left unsaid, by its writer"])
        nb += [""]
    if layout.get("gaps"):
        nb += ["## The weighing's gaps, as the layout fills them", ""]
        nb += [f"- {g['for']}: {g['fill']}" for g in layout["gaps"]] + [""]
    out["NOTES.md"] = "\n".join(nb).rstrip("\n") + "\n"
    out["requests.jsonl"] = "\n".join(requests) + "\n"
    holds = {fl["path"]: fl["holds"] for fl in layout["files"]}
    shas = [(p, holds.get(p, {"NOTICE": "the source's licence notice and credit",
                              "NOTES.md": "what the fabulac left unsaid"}.get(p, "")),
             hashlib.sha256(out[p].encode("utf-8")).hexdigest()) for p in order + ["NOTICE", "NOTES.md"]]
    out["CSHORT.md"] = cshort_in_md(fabulac=fab_name, language=info["title"], day=day, who=who, name=name,
                                    entailed=entailed, layout_name=layout_name, files=shas, rows=rows,
                                    licence=licence_line(cat))
    stem = fab_name[: -len(".fabulac.cosm")] if fab_name.endswith(".fabulac.cosm") else fab_name
    folder = folder_of_texts(f"{stem}.cshort-{language}/", out)
    entry = {"path": f"{stem}.cshort-{language}/", "order": "code", "language": language, "target": rref,
             "layout": layout_name, "entailed": entailed, "evidence": [], "files": len(order)}
    return Value("folder", folder, origin={"cshort": {**meta, "language": language, "in": info["title"],
                                                      "entailed": entailed, "day": day, "rulings-for": rref,
                                                      "notes": notes},
                                           "entry": entry})


def is_in_language(mods: dict) -> bool:
    """Whether an `entail` call is a transconception's into another language: `as layout`, or `as code` with `in`."""
    v = mods.get("in")
    named = v is not None and not (isinstance(v, Value) and v.is_nothing)
    return mods.get("as") == "layout" or (mods.get("as") == "code" and named)


def refuse_stray(mods: dict) -> None:
    """`in` a language belongs to `as layout` and `as code`, and a layout (a short) goes `with` `as code in` only:
    anywhere else they are refused, never ignored."""
    v = mods.get("in")
    if v is not None and not (isinstance(v, Value) and v.is_nothing):
        raise MoveError("entail … in a language takes as layout or as code")
    w = mods.get("with")
    if isinstance(w, Value) and w.type == "short":
        raise MoveError("entail … with a short takes it as the layout of entail f as code in a language")


def entail_in(ctx: Any, x: Value, **mods: Any) -> Any:
    """`entail f as layout in <language>` and `entail f as code in <language> with layout` (`emf.entail` hands them
    here)."""
    if mods.get("as") == "layout":
        return entail_layout(ctx, x, **mods)
    return entail_code_in(ctx, x, **mods)


def entail_in_scaffold(ctx: Any, x: Value, **mods: Any) -> Any:
    raise MoveError("entail … in a language has no scaffold: only a model lays out and writes a program in another "
                    "language, so a run with --rules cannot entail it")


# ---- their checks ----

def _out_language(output: Value, node: dict) -> str | None:
    o = (output.origin or {}) if isinstance(output, Value) else {}
    lang = ((o.get("cshort") or {}).get("language") or ((o.get("entailment") or {}).get("layout") or {}).get("language"))
    if isinstance(lang, str):
        return lang
    m = (node or {}).get("modifiers") if isinstance(node, dict) else None
    return _word(m.get("in")) if isinstance(m, dict) else None


def _in_fabula(output: Value, inputs: dict) -> Value | None:
    for v in inputs.values():
        if isinstance(v, Value) and v.type == "fabula":
            return v
    t = entailment_of(output)
    return t.get("fabula") if t and isinstance(t.get("fabula"), Value) else None


def is_cshort_in_language(output: Value) -> bool:
    """A folder this module's `entail … as code in` gave, or one whose `CSHORT.md` footer names another language
    than Python (what `files-present` and `footer` hand here)."""
    if not isinstance(output, Value) or not isinstance(output.payload, Folder):
        return False
    if ((output.origin or {}).get("cshort") or {}).get("in"):
        return True
    f = output.payload
    if f.entry("CSHORT.md") is None:
        return False
    first = next((ln for ln in f.text("CSHORT.md").split("\n") if ln.strip()), "")
    m = re.match(r"^\*a cshort of .+?, in ([^,]+), compiled on ", first)
    return bool(m) and m.group(1).strip().lower() != "python"


def files_present_in(f: Folder) -> tuple[bool, str]:
    """`files-present` of a cshort in another language (Thym 7.3): every file its layout names, with `CSHORT.md`,
    and the digests `CSHORT.md` lists are the files'."""
    if f.entry("CSHORT.md") is None:
        return False, "CSHORT.md is missing"
    md = f.text("CSHORT.md")
    listed = re.findall(r"^\| (.+?) \| .*? \| ([0-9a-f]{64}) \|$", md, re.M)
    if not listed:
        return False, "CSHORT.md lists no file"
    for p, sha in listed:
        e = f.entry(p)
        if e is None:
            return False, f"CSHORT.md lists {p}, which is not there"
        if e.sha256 != sha:
            return False, f"CSHORT.md lists {p} with another sha256 than the file's"
    named = {r[1] for r in re.findall(r"^\| (C:interface/\S+) \| (.+?) \| .+? \|$", md, re.M)}
    missing = sorted(p for p in named if f.entry(p) is None)
    if missing:
        return False, f"{', '.join(missing[:3])} {'is' if len(missing) == 1 else 'are'} missing"
    return True, ""


@check("target-confirmed")
def _target_confirmed(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Gate 2's last check, the first of an entailment into a language (Thym 20.10; MacroCOSM OES 18.4.9): the
    language's standing weighing is feasible, no gate point scored 0, every reliance kept is provided, and its spike
    stood at level 2."""
    fab = _in_fabula(output, inputs)
    lang = _out_language(output, node)
    if fab is None or not lang:
        return False, "no fabulac and language to confirm the target of"
    cat, items = fabula_doc(fab)
    probs = _tc(ctx).target_confirmed_problems({k: plain(v) for k, v in cat.items() if k != "nodes"},
                                               [plain(it) for it in items], lang)
    return (not probs), ("; ".join(probs[:3]) if probs else "")


@check("surface-answered")
def _surface_answered(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Of a cshort in another language, in place of `interfaces-present`: `CSHORT.md` maps every interface ruled kept
    or alike (or not yet ruled for the target) to a file and a name, and the name is in that file. Of a layout: the
    layout maps each such interface to one of its own files and a name (MacroCOSM OES 18.4.9; Thym 7.3)."""
    tc = _tc(ctx)
    fab = _in_fabula(output, inputs)
    if fab is None:
        return False, "no fabulac to read the kept interfaces of"
    items = [plain(it) for it in fabula_doc(fab)[1]]
    lang = _out_language(output, node)
    rref = tc.standing_weighing(items, lang)[1] if lang else None
    if isinstance(output.payload, Folder):
        f = output.payload
        if f.entry("CSHORT.md") is None:
            return False, "CSHORT.md is missing"
        probs = tc.surface_problems(items, rref, f.text("CSHORT.md"), unruled=True,
                                    file_text=lambda p: f.text(p) if f.entry(p) is not None else None)
    else:
        lay = read_layout(output.text())
        probs = tc.surface_problems(items, rref, output.text(), unruled=True, files={x["path"] for x in lay["files"]})
    if probs:
        return False, "; ".join(f"{i}: {w}" for i, w in probs[:3]) + (f" (and {len(probs) - 3} more)"
                                                                      if len(probs) > 3 else "")
    return True, ""


@check("apart")
def _apart(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Of a cshort entailed apart: no request of the entailment carried a span, a source path or the source's text
    (`requests.jsonl`, kept in the cshort). A cshort entailed beside holds it with nothing to check."""
    tc = _tc(ctx)
    if not isinstance(output, Value) or not isinstance(output.payload, Folder):
        return False, "the output is not a cshort"
    f = output.payload
    if ((output.origin or {}).get("cshort") or {}).get("entailed") == "beside":
        return True, ""                         # entailed beside the source, as the person asked: nothing to check
    if f.entry("requests.jsonl") is None:
        return False, "requests.jsonl is missing: the requests of an entailment apart are kept with it"
    fab = _in_fabula(output, inputs)
    items = [plain(it) for it in fabula_doc(fab)[1]] if fab is not None else []
    probs = tc.apart_problems(f.text("requests.jsonl").split("\n"), set(tc.source_paths(items)), None)
    return (not probs), ("; ".join(probs[:3]) if probs else "")


@check("footer", kind="layout")
def _layout_footer(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """A layout ends with its footer: `*a layout of F, in Go, compiled on DAY by WHO*`, F the fabulac's file, DAY
    the run's day in UTC."""
    lines = [ln.strip() for ln in output.text().replace("\r\n", "\n").split("\n") if ln.strip()]
    m = _LAYOUT_FOOT.match(lines[-1]) if lines else None
    if not m:
        return False, f"the last line is not a layout's footer: {lines[-1][:80] if lines else ''}"
    fab = _in_fabula(output, inputs)
    if fab is not None:
        cat, _items = fabula_doc(fab)
        want = fabulac_file({k: plain(v) for k, v in cat.items() if k != "nodes"}, fab)
        if m.group("f") != want:
            return False, f"the footer names {m.group('f')}, not {want}"
    if m.group("day") != utc_day(ctx):
        return False, f"the footer's day is {m.group('day')}, the run's {utc_day(ctx)}"
    return True, ""


@check("no-invention", kind="layout")
def _layout_no_invention(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """`no-invention` as a layout holds it: every id it names is an item of the fabulac. Its file names and the names
    it gives are the new program's to choose; the program's own items are what it may not invent."""
    fab = _in_fabula(output, inputs)
    if fab is None:
        return False, "no fabula to look the layout up in"
    ids = {str(plain(it).get("id")) for it in fabula_doc(fab)[1]}
    bad = sorted({x for x in _IDS.findall(output.text()) if x not in ids})
    if bad:
        return False, f"the layout names {', '.join(bad[:3])}, which the fabulac does not hold"
    return True, ""


__all__ += ["IN_STEPS", "RULE_FILES", "apart_view", "entail_code_in", "entail_in", "entail_in_scaffold", "refuse_stray",
            "entail_layout", "file_and_notes", "file_brief", "files_present_in", "is_cshort_in_language",
            "is_in_language", "layout_text", "parse_layout", "read_layout"]
