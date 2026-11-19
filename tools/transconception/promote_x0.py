"""Promote one of the experiment's working fabulacs (x0, `fabulac-test-repos/_x0/<repo>/<repo>.fabulac.cosm`, written
2026-11-13) into the shapes pinned for 0.8 (docs/v080-pins.md sections 0 and 2), and fold its round trip's verdict in
as evidence. A tool kept outside enough's import path: enough never imports it. It reads the x0 files as text and
writes one file; it runs nothing.

    python tools/transconception/promote_x0.py X0_FABULAC VERDICT_JSON OUT [--level N] [--at STAMP]

What it changes, and nothing else:

- the words: `purpose: transcoding` becomes `purpose: transconception`; the R:maker of capacity `transcoder` becomes
  capacity `transconceiver`, its id `R:maker/transcoder` becomes `R:maker/transconceiver` everywhere it is named, and
  its name and summary say transconceiver (the x0 files keep their 0.7 words: they are the experiment's record);
- the catalog says `ruled-by: R:maker/transconceiver` and `source.obtained: public` (the transconceiver's standing
  statement Q-D4: "public repositories only"), and the grammar version the reader writes;
- `ruling` is always a list (x0 wrote one ruling as a mapping);
- a reliance's `of` means what it is a gift of (the C:dependency of the source language, for a reliance on the
  language or its runtime) and `used-by` lists the items that use it (x0's `of` and x0's `used-by` together);
  `cited` is dropped (it is derivable from `stated`);
- a path on the recording machine inside a recorded message (a traceback's file) is written from the home folder
  (`~/...`): a fixture names no machine;
- the round trip's cshort becomes a `shorts` entry: order code, in the source language, entailed apart (A6 wrote it
  from the fabulac alone), target the source language's N:target, and `evidence` from the verdict
  (`steps: {kept, agree}`, `where: {file, digest}`, the digest the verdict file's sha256). Its level is given
  (default 3: the original's own tests passed bar the failures its rulings expect, and the recorded cases judged and
  passing; the experiment's LEDGER, O7).

With `--target TARGET_MD SPIKE_VERDICT` (given once per weighed language), the hand weighing of step A7
(`_x0/<repo>/target-<language>.md`, its `N:target` in the last YAML block) replaces the fabulac's unweighed placeholder
of that language, in the shape MacroCOSM 18.4.9 pins: each `weighed` point named by its number (A7 wrote the keys
`stewardship` … `can-be-left`, which `enough.transconception.point_number` reads), and the spike's level read from
the judge's verdict on the spike (`enough.transconception.spike_from_verdict`: only the spike's own cases count), with
the verdict file's path and sha256. A `provides` row the shape expects a `gap` on and A7 wrote none gets one: the
rows A7's verdict names in its numbered list of what "must be written or fetched" take that item's words (`named_gaps`),
and any other row provided by a library, a binding or nothing takes `weigh`'s own rule (`<by>: <what>`). Everything
else of the weighing is as A7 wrote it.

With `--ground CLONE` (0.8, pins 25), the fabulac is grounded with 0.8's ground catalogue: the move `ground`'s pure
core (`enough.thym.moves.transconceive.ground_fabula`) over the clone's files read as text, never run, imported or
installed; the clone must be the tree the fabulac was made from. Each reliance it raises that the fabulac did not hold
carries the owner's ruling of 2026-11-19 (`kept`, for every target: `GROUND_RULING`), and the transconceiver says it
ruled them. A7's weighings predate the ground, so each weighed target gains a `provides` row, by `weigh`'s own rules
from the language's target table (`answered: rules`), for each reliance the ground raised (`ground_rows`); no row A7
wrote, no point, verdict or condition changes. Grounding holds every `ENOUGH_*` seam at a scratch value first (`_scratch_seams`): nothing reaches the
network or a person's ~/enough.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from enough import macrocosm as mc  # noqa: E402  (read and dump only)

import yaml  # noqa: E402  (through the reader's own dumper)

_LINEY = ("\x85", " ", " ")


def _str(dumper, data):
    """A string holding a character YAML reads as a line break is written double-quoted, so it loads back exact
    (x0's a4lib did the same)."""
    if any(c in data for c in _LINEY):
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')
    return dumper.represent_str(data)


class _Dumper(mc._Dumper):
    """The reader's dumper, with `_str`: a dumper of the promoter's own, so that importing this file never changes
    how enough dumps (it once added `_str` to `mc._Dumper` itself; every later dump in the process then quoted those
    strings, every engine call's digest moved with it, and a recorded run that followed in the same process refused
    to replay)."""


_Dumper.add_representer(str, _str)


def dump(mapping: dict) -> str:
    """`mc.dump` (the declaration key first, never an anchor, a shared structure refused) through `_Dumper`."""
    mc._refuse_shared(mapping)
    first = next((k for k in mc.DECLARATION_KEYS if k in mapping), None)
    if first is not None and next(iter(mapping)) != first:
        mapping = {first: mapping[first], **{k: v for k, v in mapping.items() if k != first}}
    return yaml.dump(mapping, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=110,
                     default_flow_style=False)

OLD_MAKER, NEW_MAKER = "R:maker/transcoder", "R:maker/transconceiver"
_MACHINE = re.compile(r"/Users/[^/\s\"']+/|/home/[^/\s\"']+/")


def _strings(v, f):
    if isinstance(v, dict):
        return {k: _strings(x, f) for k, x in v.items()}
    if isinstance(v, list):
        return [_strings(x, f) for x in v]
    return f(v) if isinstance(v, str) else v


def _fix(s: str) -> str:
    s = s.replace(OLD_MAKER, NEW_MAKER)
    s = re.sub(r"\btranscoder\b", "transconceiver", s)        # the role's word, ruled 2026-11-18
    s = re.sub(r"\btranscoding\b", "transconception", s)     # the purpose's word, ruled 2026-11-18
    return _MACHINE.sub("~/", s)


def promote(doc: dict, verdict: dict, verdict_digest: str, verdict_rel: str, *, level: int, at: str,
            cshort_path: str) -> dict:
    out: dict = {}
    for k, v in doc.items():
        if k == "nodes":
            continue
        if k == "purpose":
            v = "transconception" if v == "transcoding" else v
        if k == "macrocosm":
            v = mc.MACROCOSM_VERSION
        out[k] = v
        if k == "purpose":
            out["ruled-by"] = NEW_MAKER
    src = out.get("source")
    if isinstance(src, dict):
        src.setdefault("obtained", "public")
    language = src.get("language") if isinstance(src, dict) else None
    nodes = [_strings(n, _fix) for n in doc["nodes"]]
    dep = next((n["id"] for n in nodes if n.get("type") == "dependency" and n.get("package") == language), None)
    target = next((n["id"] for n in nodes if n.get("type") == "target" and n.get("language") == language), None)
    for n in nodes:
        if n["id"] == NEW_MAKER:
            n["capacity"] = "transconceiver"
            for k in ("name", "summary"):
                n[k] = re.sub(r"\btranscoder\b", "transconceiver", n[k])
        r = n.get("ruling")
        if isinstance(r, dict):
            n["ruling"] = [r]
        if n.get("type") == "reliance":
            used = []
            for ref in list(n.get("of") or []) + list(n.get("used-by") or []):
                if ref not in used:
                    used.append(ref)
            rebuilt = {}
            for k, v in n.items():
                if k in ("of", "used-by", "cited"):
                    continue
                rebuilt[k] = v
                if k == "on":
                    if dep and v in ("language", "runtime"):
                        rebuilt["of"] = [dep]
                    rebuilt["used-by"] = used
            n.clear()
            n.update(rebuilt)
    entry = {"path": cshort_path, "at": at, "by": "an agent of the experiment (step A6), from the fabulac alone",
             "mode": "model", "order": "code", "language": language, "entailed": "apart", "target": target,
             "evidence": {"level": level, "steps": {"kept": verdict["steps"]["kept"], "agree": verdict["steps"]["agree"]},
                          "against": verdict.get("against", "original"),
                          "inputs": f"the recorded cases, digest {verdict.get('recorded_digest', '')[:12]}",
                          "where": {"file": verdict_rel, "digest": verdict_digest}, "at": at,
                          "by": "the judge of the experiment, run by the owner (step O7)"}}
    shorts = list(out.get("shorts") or [])
    shorts.append(entry)
    out["shorts"] = shorts
    out["nodes"] = nodes
    return out


_YAML_BLOCK = re.compile(r"```yaml\n(.*?)```", re.S)
_RESULTS_STAMP = re.compile(r"(\d{4}-\d{2}-\d{2})-(\d{2})(\d{2})")


def hand_weighing(md_text: str) -> dict:
    """The `N:target` item of a hand weighing (A7's `target-<language>.md`): its last YAML block that is a list of
    one `N:target`."""
    for block in reversed(_YAML_BLOCK.findall(md_text)):
        data = mc.yaml_load(block)
        if isinstance(data, list) and len(data) == 1 and str(data[0].get("id", "")).startswith("N:target/"):
            return data[0]
    raise ValueError("no N:target item in a YAML block of the weighing")


_NAMED_GAP = re.compile(r"^\d+\. \*\*(.+?)\*\*\s*\(([^)]*)\)", re.M)
_RELIANCE_REF = re.compile(r"\b[A-Z]-R\d+\b")
GAP_BY = ("library", "binding", "cannot")      # the rows `weigh` names a gap on when the reply names none


def named_gaps(md_text: str) -> dict[str, str]:
    """The gaps A7's weighing names in its verdict: each numbered item of the `## Verdict` section (`1. **What** (V-R02,
    V-R27; ...)`), the reliances in its parentheses, its bold words. A verdict with no numbered list names none."""
    section = md_text.split("## Verdict", 1)[1].split("\n## ", 1)[0] if "## Verdict" in md_text else ""
    out: dict[str, str] = {}
    for m in _NAMED_GAP.finditer(section):
        for ref in _RELIANCE_REF.findall(m.group(2)):
            out.setdefault(f"C:reliance/{ref}", m.group(1).strip())
    return out


def gaps_in(t: dict, named: dict[str, str]) -> list[str]:
    """Each `provides` row the shape expects a `gap` on and A7 left without one gets it: A7's own words for a row its
    verdict names (`<words> (<by>)`), `weigh`'s rule (`<by>: <what>`) for a library, binding or `cannot` row. Returns
    the rows given one."""
    given = []
    for row in t.get("provides") or []:
        if not isinstance(row, dict) or row.get("gap"):
            continue
        if row.get("for") in named:
            row["gap"] = f"{named[row['for']]} ({row.get('by')})"
        elif row.get("by") in GAP_BY:
            row["gap"] = f"{row['by']}: {row.get('what')}"
        else:
            continue
        given.append(str(row["for"]))
    unknown = sorted(set(named) - {str(r.get("for")) for r in t.get("provides") or [] if isinstance(r, dict)})
    if unknown:
        raise ValueError(f"{t['id']}: the verdict names gaps no provides row is for: {', '.join(unknown)}")
    return given


def weighed_in(nodes: list[dict], target: dict, verdict: dict, verdict_digest: str, verdict_rel: str, *,
               at: str | None, named: dict[str, str] | None = None) -> dict:
    """A hand weighing written into the nodes in place of the language's placeholder, in the pinned shape: points by
    number, the spike's level from the judge's verdict on it, a gap on each row the shape expects one on
    (`gaps_in`). Returns the item written."""
    from enough import transconception as tc
    t = _strings(target, _fix)
    for w in t.get("weighed") or []:
        n = tc.point_number(w.get("point"))
        if n is None:
            raise ValueError(f"{t['id']}: {w.get('point')!r} is none of the twelve points")
        w["point"] = n
    t["weighed"] = sorted(t.get("weighed") or [], key=lambda w: w["point"])
    gaps_in(t, named or {})
    t["spike"] = tc.spike_from_verdict(t.get("spike") or {}, verdict, where=verdict_rel, digest=verdict_digest, at=at)
    for i, n in enumerate(nodes):
        if n.get("id") == t["id"]:
            if "verdict" in n:
                raise ValueError(f"{t['id']} is weighed already: a later weighing goes beside it, under its own id")
            nodes[i] = t
            return t
    nodes.append(t)
    return t


#: The owner's ruling on the reliances 0.8's ground raises in the experiment's fabulacs (enough-dev docs/v080-pins.md
#: section 25, 2026-11-19, by questionnaire): `kept`, as proposed, for every target.
GROUND_RULED_ON = "2026-11-19"
GROUND_RULED_IN = "enough-dev docs/v080-pins.md section 25 (2026-11-19, by questionnaire)"
GROUND_RULING = {"is": "kept", "by": NEW_MAKER, "on": GROUND_RULED_ON,
                 "said": "pins 25: the reliances 0.8's ground catalogue raised in the experiment's fabulacs are kept, "
                         "as proposed, recorded as the owner's"}


def _scratch_seams() -> None:
    """Every ENOUGH_* seam at a scratch value, every behaviour seam removed, as the test suite and tally's maker do:
    grounding by hand must never reach the network (the language library's fetch) or a person's ~/enough."""
    import tempfile
    from enough import seams
    scratch = Path(tempfile.mkdtemp(prefix="promote-x0-seams-"))
    for name in seams.BEHAVIOUR_SEAMS:
        os.environ.pop(name, None)
    for name, value in seams.scratch_env(scratch, {}).items():
        if name.startswith("ENOUGH_"):
            os.environ[name] = value


def grounded(doc: dict, root: Path, *, at: str) -> tuple[dict, list[str], dict]:
    """The fabulac grounded with 0.8's ground catalogue over `root` read as text (the move `ground`'s pure core, as
    `tests/test_ground.py` calls it), each new reliance ruled as the owner ruled (`GROUND_RULING`). Returns the
    fabulac, the new reliances' ids, and what the ground found."""
    from enough import repo_engine as RE
    from enough.thym import folder as FO
    from enough.thym.moves import transconceive as TR
    cat = {k: v for k, v in doc.items() if k != "nodes"}
    if mc.tree_digest(root)["tree"] != (cat.get("source") or {}).get("tree"):
        raise ValueError(f"{root} is not the tree the fabulac was made from (source.tree)")
    f = FO.read(root)
    uses = {e.path: RE.uses(e.path, f.text(e.path)) for e in f.texts()
            if e.path.endswith((".py", ".pyi")) and not TR.is_tooling(e.path)}
    locks = {e.path: RE.locks(e.path, f.text(e.path)) for e in f.texts() if TR._lock_file(e.path)}
    had = {n["id"] for n in doc["nodes"]}
    cat2, items, found = TR.ground_fabula(cat, doc["nodes"], uses, RE.catalogue(cat["source"]["language"]),
                                          locks=locks, swhid=RE.swhid(root),
                                          run={"program": "ground", "mode": "rules", "at": at,
                                               "by": "tools/transconception/promote_x0.py --ground (0.8's catalogue, "
                                                     f"{found_catalogue()})"})
    new = [it["id"] for it in items if it["id"] not in had]
    for it in items:
        if it["id"] in new and it.get("type") == "reliance" and not it.get("ruling"):
            it["ruling"] = [dict(GROUND_RULING)]
        if it["id"] == NEW_MAKER:
            ri = list(it.get("ruled-in") or [])
            if GROUND_RULED_IN not in ri:
                it["ruled-in"] = ri + [GROUND_RULED_IN]
            line = (" On 2026-11-19 the owner ruled the reliances 0.8's ground catalogue raised kept, as proposed "
                    "(pins 25).")
            if line.strip() not in str(it.get("summary")):
                it["summary"] = str(it.get("summary") or "").rstrip() + line
    return {**cat2, "nodes": items}, new, found


GROUND_ROWS_SOURCE = ("rows for the reliances 0.8's ground raised, by `weigh`'s rules from the target table "
                      "(promote_x0.py --ground, 2026-11-19); every row A7 wrote is as it wrote it")


def ground_rows(doc: dict, raised: list[str]) -> dict[str, list[str]]:
    """A7's hand weighings give a `provides` row for every reliance x0 wrote, and none for those the ground raised
    after them, which `target-confirmed` asks a row for. Each weighed target gains, for each raised reliance with no
    row, the row `weigh`'s rules give it from the language's target table (`answered: rules`); nothing A7 wrote is
    changed, and no point, verdict or condition is weighed again. Returns the rows added, by target."""
    from enough import transconception as tc
    from enough.thym.moves import transconceive as TR
    cat = {k: v for k, v in doc.items() if k != "nodes"}
    added: dict[str, list[str]] = {}
    for t in [n for n in doc["nodes"] if n.get("type") == "target" and n.get("verdict")]:
        language = str(t.get("language") or "")
        answer = tc.target_table(language)
        if not answer.get("ok"):
            continue
        rows = {r["for"]: r for r in TR.weigh_rules(cat, doc["nodes"], language, answer)["target"]["provides"]}
        have = {r.get("for") for r in t.get("provides") or [] if isinstance(r, dict)}
        new = [rows[r] for r in raised if r in rows and r not in have]
        if not new:
            continue
        t["provides"] = list(t.get("provides") or []) + new
        prov = t.setdefault("provenance", {})
        if GROUND_ROWS_SOURCE not in (prov.get("sources") or []):
            prov["sources"] = list(prov.get("sources") or []) + [GROUND_ROWS_SOURCE]
        added[str(t["id"])] = [r["for"] for r in new]
    return added


def found_catalogue() -> str:
    from enough import languages as L
    head = L.catalogue("python")
    return f"python ground catalogue, {len(L.entries('python'))} entries, version {head.get('version')}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("fabulac", type=Path)
    ap.add_argument("verdict", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--level", type=int, default=3)
    ap.add_argument("--at", default="2026-11-13T10:06")
    ap.add_argument("--cshort", default="told/py-roundtrip/", help="the cshort's path as the x0 fabulac sees it")
    ap.add_argument("--target", nargs=2, action="append", type=Path, default=[], metavar=("TARGET_MD", "SPIKE_VERDICT"),
                    help="a hand weighing (A7's target-<language>.md) and the judge's verdict on its spike")
    ap.add_argument("--ground", type=Path, default=None, metavar="CLONE",
                    help="ground with 0.8's catalogue over the clone the fabulac was made from, read as text")
    ap.add_argument("--ground-at", default="2026-11-19T12:00")
    a = ap.parse_args(argv)
    if a.ground is not None:
        _scratch_seams()
    doc = mc.yaml_load(a.fabulac.read_text(encoding="utf-8"))
    raw = a.verdict.read_bytes()
    rel = os.path.relpath(a.verdict.resolve(), a.fabulac.resolve().parent)
    new = promote(doc, json.loads(raw), hashlib.sha256(raw).hexdigest(), rel, level=a.level, at=a.at,
                  cshort_path=a.cshort)
    for md, spike_verdict in a.target:
        sraw = spike_verdict.read_bytes()
        srel = os.path.relpath(spike_verdict.resolve(), a.fabulac.resolve().parent)
        stamp = _RESULTS_STAMP.search(srel)
        md_text = md.read_text(encoding="utf-8")
        t = weighed_in(new["nodes"], hand_weighing(md_text), json.loads(sraw),
                       hashlib.sha256(sraw).hexdigest(), srel,
                       at=f"{stamp.group(1)}T{stamp.group(2)}:{stamp.group(3)}" if stamp else None,
                       named=named_gaps(md_text))
        print(t["id"], t["verdict"], "spike level", t["spike"]["level"],
              "gaps", [r["for"] for r in t.get("provides") or [] if r.get("gap")])
    if a.ground is not None:
        new, raised, found = grounded(new, a.ground, at=a.ground_at)
        print("ground:", len(found["entries"]), "entries shown;", len(raised), "new items:", ", ".join(raised))
        for tid, rows in ground_rows(new, raised).items():
            print(f"{tid}: {len(rows)} rows by weigh's rules for the reliances the ground raised")
    a.out.write_text(dump(new), encoding="utf-8")
    print(a.out, len(new["nodes"]), "items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
