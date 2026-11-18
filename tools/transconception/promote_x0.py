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


yaml.add_representer(str, _str, Dumper=mc._Dumper)

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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("fabulac", type=Path)
    ap.add_argument("verdict", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--level", type=int, default=3)
    ap.add_argument("--at", default="2026-11-13T10:06")
    ap.add_argument("--cshort", default="told/py-roundtrip/", help="the cshort's path as the x0 fabulac sees it")
    a = ap.parse_args(argv)
    doc = mc.yaml_load(a.fabulac.read_text(encoding="utf-8"))
    raw = a.verdict.read_bytes()
    rel = os.path.relpath(a.verdict.resolve(), a.fabulac.resolve().parent)
    new = promote(doc, json.loads(raw), hashlib.sha256(raw).hexdigest(), rel, level=a.level, at=a.at,
                  cshort_path=a.cshort)
    a.out.write_text(mc.dump(new), encoding="utf-8")
    print(a.out, len(new["nodes"]), "items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
