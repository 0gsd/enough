#!/usr/bin/env python3
"""Copy the lexicon's dictionary into `reflib/dict/`, as the public edition FEED ships.

    uv run python scripts/sync_dictionary.py                # sync from ../../enough-lexicon
    uv run python scripts/sync_dictionary.py --check        # report what would change, write nothing
    uv run python scripts/sync_dictionary.py --lexicon DIR  # another lexicon checkout

The lexicon (`enough-lexicon/dictionary/`) is the committed text form of the dictionary DB: `schema.sql`, one
JSON-lines file per small table, and `words`/`forms`/`synonyms` split by initial letter. This script only ever
READS it. The copy mirrors that layout exactly, with the public-edition filter applied line by line
(docs/feed-041-plan.md, "FEED data pipeline"):

- `words`: `notes`, `source` and `corrected_on` are set to null (pack provenance and sourcing notes never appear
  in the dictionary itself); rows whose `status` is neither null nor `live` are dropped, along with every
  `forms`/`synonyms` row that names them;
- `meta`: only `dictionary_version`, `languages`, `schema_version` and `title` survive.

Key order is preserved and lines are re-serialised the way the lexicon's exporter writes them, so a rerun over an
unchanged lexicon is byte-stable. Only files whose filtered content changed are rewritten; files with no source
are removed. `manifest.json` records every file's sha256 and a digest over them (no timestamps), which is what
`enough/dictionary.py` compares to decide whether an install's `feed.sqlite` needs rebuilding. `NOTICE.md` is
hand-written and never touched here.

Exit status: 0 = synced (or, with --check, nothing to do); 1 = --check found changes; 2 = no lexicon.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEXICON = REPO_ROOT.parent.parent / "enough-lexicon"
DEFAULT_OUT = REPO_ROOT / "reflib" / "dict"

SMALL = ("meta", "labels", "frequency_bands")
SPLIT = ("words", "forms", "synonyms")
META_KEEP = frozenset({"dictionary_version", "languages", "schema_version", "title"})
NULLED = ("notes", "source", "corrected_on")
LIVE = (None, "live")
# Hand-written or generated here; never mirrored from the lexicon, never removed.
OWN = frozenset({"manifest.json", "NOTICE.md"})


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _line(row: dict) -> str:
    # The lexicon exporter's own serialisation (tools/dictionary_text.py).
    return json.dumps(row, ensure_ascii=False) + "\n"


def _rows(path: Path):
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            if raw.strip():
                yield json.loads(raw)


def _sources(src: Path) -> list[str]:
    """Every file the copy mirrors, as relpaths, sorted."""
    rel = []
    if (src / "schema.sql").is_file():
        rel.append("schema.sql")
    rel += [f"{t}.jsonl" for t in SMALL if (src / f"{t}.jsonl").is_file()]
    for t in SPLIT:
        if (src / t).is_dir():
            rel += [f"{t}/{p.name}" for p in sorted((src / t).glob("*.jsonl"))]
    return sorted(rel)


def filtered(src: Path, state: dict):
    """The public edition, one file at a time: yields (relpath, bytes). Fills `state` with the headword and word
    counts and the set of dropped (non-live) words as it goes; words come first because forms and synonyms need
    that set."""
    dropped: set[str] = state.setdefault("dropped", set())
    state.setdefault("headwords", 0)
    state.setdefault("words", 0)
    rels = _sources(src)
    for rel in [r for r in rels if r.startswith("words/")]:
        lines = []
        for row in _rows(src / rel):
            if row.get("status") not in LIVE:
                dropped.add(row["word"])
                continue
            for col in NULLED:
                if col in row:
                    row[col] = None
            state["words"] += 1
            state["headwords"] += 1 if row.get("is_headword") == 1 else 0
            lines.append(_line(row))
        yield rel, "".join(lines).encode("utf-8")
    for rel in rels:
        path = src / rel
        if rel.startswith("words/"):
            continue
        if rel in ("schema.sql", "labels.jsonl", "frequency_bands.jsonl"):
            yield rel, path.read_bytes()
        elif rel == "meta.jsonl":
            yield rel, "".join(_line(r) for r in _rows(path) if r.get("key") in META_KEEP).encode("utf-8")
        elif rel.startswith("forms/"):
            yield rel, "".join(_line(r) for r in _rows(path)
                               if r["headword"] not in dropped and r["form"] not in dropped).encode("utf-8")
        elif rel.startswith("synonyms/"):
            yield rel, "".join(_line(r) for r in _rows(path)
                               if r["word"] not in dropped and r["synonym"] not in dropped).encode("utf-8")


def _meta_value(data: bytes, key: str) -> str | None:
    for raw in data.decode("utf-8").splitlines():
        row = json.loads(raw) if raw.strip() else {}
        if row.get("key") == key:
            return row.get("value")
    return None


def manifest_for(hashes: dict[str, str], meta: bytes, counts: dict[str, int]) -> bytes:
    hashes = dict(sorted(hashes.items()))
    digest = _sha("".join(f"{rel} {h}\n" for rel, h in hashes.items()).encode("utf-8"))
    body = {
        "dictionary_version": _meta_value(meta, "dictionary_version"),
        "schema_version": _meta_value(meta, "schema_version"),
        "headwords": counts["headwords"],
        "words": counts["words"],
        "files": hashes,
        "digest": digest,
    }
    return (json.dumps(body, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _existing(out: Path) -> list[str]:
    """Mirrored files already in the copy (OWN excluded)."""
    if not out.is_dir():
        return []
    rel = [p.name for p in out.iterdir() if p.is_file() and p.name not in OWN and not p.name.startswith(".")]
    for t in SPLIT:
        if (out / t).is_dir():
            rel += [f"{t}/{p.name}" for p in (out / t).iterdir() if p.is_file() and not p.name.startswith(".")]
    return sorted(rel)


def _word_delta(old: bytes, new: bytes) -> tuple[int, int, int]:
    """(added, removed, changed) words between two versions of one words/*.jsonl file."""
    def keyed(data: bytes) -> dict[str, str]:
        rows = {}
        for raw in data.decode("utf-8").splitlines():
            if raw.strip():
                rows[json.loads(raw).get("word", raw)] = raw
        return rows
    a, b = keyed(old), keyed(new)
    return (len(b.keys() - a.keys()), len(a.keys() - b.keys()),
            sum(1 for w in a.keys() & b.keys() if a[w] != b[w]))


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def sync(lexicon: Path, out: Path, *, check: bool = False) -> dict:
    """Bring `out` in line with `lexicon/dictionary`. Returns a report; writes nothing when `check`."""
    src = Path(lexicon) / "dictionary"
    if not (src / "schema.sql").is_file():
        raise FileNotFoundError(f"no dictionary at {src} (expected schema.sql there)")
    out = Path(out)
    state: dict = {}
    hashes: dict[str, str] = {}
    meta = b""
    report = {"added": [], "changed": [], "removed": [], "words_added": 0, "words_removed": 0,
              "words_changed": 0}
    for rel, data in filtered(src, state):
        hashes[rel] = _sha(data)
        if rel == "meta.jsonl":
            meta = data
        target = out / rel
        if not target.is_file():
            report["added"].append(rel)
            if rel.startswith("words/"):
                report["words_added"] += data.count(b"\n")
        else:
            old = target.read_bytes()
            if _sha(old) == hashes[rel]:
                continue
            report["changed"].append(rel)
            if rel.startswith("words/"):
                a, r, c = _word_delta(old, data)
                report["words_added"] += a
                report["words_removed"] += r
                report["words_changed"] += c
        if not check:
            _write(target, data)
    for rel in _existing(out):
        if rel not in hashes:
            report["removed"].append(rel)
            if rel.startswith("words/"):
                report["words_removed"] += (out / rel).read_bytes().count(b"\n")
            if not check:
                (out / rel).unlink()
    counts = {"headwords": state["headwords"], "words": state["words"]}
    report.update(counts, withheld=len(state["dropped"]))
    manifest = manifest_for(hashes, meta, counts)
    mpath = out / "manifest.json"
    if not mpath.is_file() or mpath.read_bytes() != manifest:
        report["changed" if mpath.is_file() else "added"].append("manifest.json")
        if not check:
            _write(mpath, manifest)
    report["digest"] = json.loads(manifest)["digest"]
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--lexicon", type=Path, default=DEFAULT_LEXICON,
                    help=f"lexicon checkout (default {DEFAULT_LEXICON})")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help=argparse.SUPPRESS)
    ap.add_argument("--check", action="store_true", help="list what would change; write nothing")
    args = ap.parse_args(argv)
    try:
        r = sync(args.lexicon, args.out, check=args.check)
    except FileNotFoundError as e:
        print(f"sync_dictionary: {e}", file=sys.stderr)
        return 2
    for kind in ("added", "changed", "removed"):
        for rel in r[kind]:
            print(f"  {kind:8} {rel}")
    touched = len(r["added"]) + len(r["changed"]) + len(r["removed"])
    print(f"{'check' if args.check else 'sync'}: {len(r['added'])} added, {len(r['changed'])} changed, "
          f"{len(r['removed'])} removed files; words +{r['words_added']} -{r['words_removed']} "
          f"~{r['words_changed']}; {r['headwords']} headwords, {r['words']} words, {r['withheld']} withheld; "
          f"digest {r['digest'][:12]}")
    if args.check and touched:
        print(f"check: {touched} file(s) would change — run without --check to sync", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
