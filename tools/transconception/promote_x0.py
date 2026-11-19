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
the verdict file's path and sha256. Everything else of the weighing is as A7 wrote it.
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


def weighed_in(nodes: list[dict], target: dict, verdict: dict, verdict_digest: str, verdict_rel: str, *,
               at: str | None) -> dict:
    """A hand weighing written into the nodes in place of the language's placeholder, in the pinned shape: points by
    number, the spike's level from the judge's verdict on it. Returns the item written."""
    from enough import transconception as tc
    t = _strings(target, _fix)
    for w in t.get("weighed") or []:
        n = tc.point_number(w.get("point"))
        if n is None:
            raise ValueError(f"{t['id']}: {w.get('point')!r} is none of the twelve points")
        w["point"] = n
    t["weighed"] = sorted(t.get("weighed") or [], key=lambda w: w["point"])
    t["spike"] = tc.spike_from_verdict(t.get("spike") or {}, verdict, where=verdict_rel, digest=verdict_digest, at=at)
    for i, n in enumerate(nodes):
        if n.get("id") == t["id"]:
            if "verdict" in n:
                raise ValueError(f"{t['id']} is weighed already: a later weighing goes beside it, under its own id")
            nodes[i] = t
            return t
    nodes.append(t)
    return t


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
    a = ap.parse_args(argv)
    doc = mc.yaml_load(a.fabulac.read_text(encoding="utf-8"))
    raw = a.verdict.read_bytes()
    rel = os.path.relpath(a.verdict.resolve(), a.fabulac.resolve().parent)
    new = promote(doc, json.loads(raw), hashlib.sha256(raw).hexdigest(), rel, level=a.level, at=a.at,
                  cshort_path=a.cshort)
    for md, spike_verdict in a.target:
        sraw = spike_verdict.read_bytes()
        srel = os.path.relpath(spike_verdict.resolve(), a.fabulac.resolve().parent)
        stamp = _RESULTS_STAMP.search(srel)
        t = weighed_in(new["nodes"], hand_weighing(md.read_text(encoding="utf-8")), json.loads(sraw),
                       hashlib.sha256(sraw).hexdigest(), srel,
                       at=f"{stamp.group(1)}T{stamp.group(2)}:{stamp.group(3)}" if stamp else None)
        print(t["id"], t["verdict"], "spike level", t["spike"]["level"])
    a.out.write_text(dump(new), encoding="utf-8")
    print(a.out, len(new["nodes"]), "items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
