"""Transconception, checked: a program carried into another language through its fabulac (the manifest's
`transconception` block in defaults/cosm/manifests/fabula.manifest.cosm; the prose MacroCOSM OES 18.4.9).

A fabulac whose catalog says `purpose: transconception` gets thirteen checks beside the fabula's own, run by
`enough.fabula.lint` in the same report, and two gates, one function each:

- `ready_to_keep(volume)`: standing, ground-given, ground-cited, stands-alone, nothing-carried, case-outside,
  cases-cover, ruled, round-trip. None needs a target; all need the original or the people who know it.
- `ready_to_entail(volume, language)`: the same, and target-confirmed for that language, and every ruled item ruled
  for it with an allowance the judge knows.

A fabulac whose catalog says `ruled-by: none` is kept unruled, and the first gate says so.

The checks, one method each on `_Checks`:

- `standing` (error): the source's licence is an `R:licence` with its `lane` (open, bound, closed), and a closed lane
  carries the holder's `leave`; the transconceiver (`R:maker`, capacity `transconceiver`) has answered its
  statements (licence, lane, confidential, programs, attribution), unless `ruled-by: none`; `source.obtained` says how
  the source came (a warning while absent).
- `ground-given` (error): every run-time or standard dependency says in plain words what it is `needed-for`; every
  reliance carries `gives` and an `example`.
- `ground-cited` (error): every reliance on the language or its runtime carries `stated`, a list of
  `{in, version, at, digest}` and `{nowhere: text}`; a version is a patch of the runtime's minor. Resolving a
  citation against the language library comes with the library: `resolve_citation` is the one place it will go.
- `stands-alone` (error): no `summary` or `means` names the source language, its runtime or a dependency, unless a
  reliance says the same without the name (the item is in its `used-by`). Cases, production (R), dependencies,
  reliances and targets are not read: they record what the source was, or say what they rely on.
- `nothing-carried` (error): outside cases, spans, signatures and items ruled kept everywhere (a kept message is
  carried exactly), no text field holds a run of the source's own text longer than the manifest's length (200 code
  points). It reads the source folder as text, never runs it; with no source at hand it is not measured.
- `case-outside` (error): an outside case is whole data (given steps, expected steps, each with an exit), is of an
  interface, and names no file of the source; a call it makes is one an interface names.
- `cases-cover` (warning): the share of behaviours ruled kept (kept, alike, kept-wrong) that an outside case is of;
  below the manifest's share (0.6) a warning, else a note naming the uncovered.
- `ruled` (error): every interface, behaviour, structure, setting and reliance carries a `ruling`, a list, each entry
  with `is` and what its `is` needs (alike: allowing; free, kept-wrong: because; changed: to); an allowance the judge
  does not know is a warning (it blocks only `ready_to_entail` for that target).
- `round-trip` (error): a cshort in the source language (its `shorts` entry's `target` is the source language's
  `N:target`) stands at the manifest's level (2) or more, by its `evidence`. enough runs nothing: it reads evidence.
- `target-confirmed` (error, for each target that carries a `verdict`; a note for one not weighed): the verdict is
  feasible or feasible-with, every reliance kept for it is provided, and its spike reached level 2.
- `surface-answered` (error): a cshort in another language has a `CSHORT.md` mapping every interface kept for its
  target to a file and a name, and the name is in the file (not measured without the cshort folder).
- `apart` (error): a cshort entailed apart: no request of the entailing carried a span, a path of the source or a run
  of its text (read from `<cshort>/requests.jsonl`, which the entailing keeps; not measured without it).
- `evidence-stated` (error): a `shorts` entry's `evidence` carries its level, its counts and the verdict file's
  digest, and the file, when at hand, has that digest.

The cases (phase 4; the end of this module): the cases file a fabulac's catalog names (`cases: <folder>.cases.json`,
the shape of the experiment's harness, `tools/transconception/harness.py`), made from the fabulac's outside `P:case`
items and the cases already recorded (`cases_document`); a recording folder read back into it, each case saying the
source it was recorded from (`read_recording`, `gather_recorded`); a verdict folded into a cshort's `evidence`
(`fold_verdict`) and its findings as data for the rulings (`differences_from_verdict`); and what holds when the source
moves (`freshness`, `stale_report`, `carry_over`). The recorder, runner and judge are the owner's, outside enough:
enough reads their files and starts none of them.

Standalone like the reader: the standard library and `enough.macrocosm`. It reads the volume, and the source folder
and cshort folders as text when they are at hand; it writes nothing and runs nothing.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable, Mapping

from . import macrocosm as mc

PURPOSE = "transconception"
CAPACITY = "transconceiver"
CHECKS = ("standing", "ground-given", "ground-cited", "stands-alone", "nothing-carried", "case-outside", "cases-cover",
          "ruled", "round-trip", "target-confirmed", "surface-answered", "apart", "evidence-stated")
SEVERITY = {c: "error" for c in CHECKS} | {"cases-cover": "warning"}   # the owner, checkpoint A, 2026-11-18
READY_TO_KEEP = ("standing", "ground-given", "ground-cited", "stands-alone", "nothing-carried", "case-outside",
                 "cases-cover", "ruled", "round-trip")
READY_TO_ENTAIL = READY_TO_KEEP + ("target-confirmed",)
PER_CSHORT = ("surface-answered", "apart", "evidence-stated")

# The manifest's numbers and lists, used when the manifest does not give them (it does: `transconception:`).
DEFAULTS = {
    "allowances": ["exit-only", "exit-and-stdout", "stderr-said-or-not", "lines-in-any-order"],
    "ruled-kinds": ["C:interface", "C:behaviour", "C:structure", "C:setting", "C:reliance"],
    "ruling-needs": {"alike": ["allowing"], "free": ["because|said"], "kept-wrong": ["because|said"], "changed": ["to"]},
    "nothing-carried": 200,
    "cases-cover": 0.6,
    "round-trip-level": 2,
}
KEPT = ("kept", "alike", "kept-wrong")
STATEMENTS = ("licence", "lane", "confidential", "programs", "attribution")
LANES_NEEDING_LEAVE = ("closed",)
SPIKE_LEVEL = 2
SOURCE_SUFFIXES = (".py", ".md", ".toml", ".txt", ".cfg", ".rst", ".yml", ".yaml", ".in", "")

# The names a text uses when it names a source language, its runtime or its standard library, by language. Pin 3 of
# the 0.8 build puts everything the builder does by language behind one registry (enough/languages.py); this table
# moves there when the registry lands. Python's is the experiment's own (x0, a4lib.NAMES).
SOURCE_NAMES: dict[str, re.Pattern] = {
    "python": re.compile(
        r"\b(Python|python3?|CPython|PyPy|argparse|ast\b|ast\.\w+|fnmatch\w*|tomllib|tomli|pathlib|rglob|tokenize|"
        r"pkgutil|sys\.\w+|os\.path\.?\w*|IntEnum|NamedTuple|namedtuple|dataclass\w*|typing|html\.entities|html5|"
        r"xml\.etree|ElementTree|lxml|etree|codecs|collections|functools|logging|re\.\w+|regular expression|"
        r"literal_eval|splitlines|isspace|strip\(\)|str\(\)|int\(\)|chr\(\)|sorted\(\)|any\(\)|generator|yield|"
        r"pytest|traceback|TypeError|ValueError|KeyError|ImportError|UnicodeDecodeError|SyntaxError|OSError|"
        r"dict(?:ionary)?|tuple|bytes|glob)\b"),
}
# Kinds whose words are not read by stands-alone: they record what the source was (R), are data (P:case), or say
# what they rely on or depend on (C:reliance, C:dependency, N:target); D is the dialectic's.
STANDS_ALONE_SKIP_MODULES = ("R", "D")
STANDS_ALONE_SKIP_KINDS = (("P", "case"), ("C", "reliance"), ("C", "dependency"), ("N", "target"))


def is_transconception(volume: mc.Volume) -> bool:
    """Whether a loaded volume is a fabulac kept for transconception (`purpose: transconception`)."""
    return volume.manifest is not None and volume.catalog.get("purpose") == PURPOSE


def kept_unruled(volume: mc.Volume) -> bool:
    """Whether the catalog says nobody could rule it (`ruled-by: none`)."""
    return volume.catalog.get("ruled-by") == "none"


def rulings(item_data: dict) -> list[dict]:
    """An item's rulings as a list of mappings (a single mapping is read as one, though `ruled` asks for a list)."""
    r = item_data.get("ruling")
    if r is None:
        return []
    return [x for x in (r if isinstance(r, list) else [r]) if isinstance(x, dict)]


def applies(ruling: dict, target_ref: str | None) -> bool:
    """A ruling holds for a target when it is made for it, or made for no target in particular."""
    mf = ruling.get("made-for")
    return mf is None or target_ref is None or mf == target_ref


def resolve_citation(entry: dict, library: Any = None) -> tuple[bool | None, str]:
    """Whether a `stated` entry `{in, version, at, digest}` resolves to a section aboard the language library, or to
    a pinned text's digest. Returns (True, '') when it does, (False, why) when it does not, (None, why) when it cannot
    be told. The language library is not aboard in this build (phase 2b brings it, with its index): until then every
    citation is (None, ...), and ground-cited asks only that each reliance carries `stated`."""
    if library is None:
        return None, "the language library is not aboard: the citation is carried, not resolved"
    find = getattr(library, "find", None)
    if not callable(find):
        return None, "the language library given has no index to look in"
    hit = find(entry)
    if hit is None:
        return False, f"{entry.get('in')} {entry.get('version')} has no section at {entry.get('at')}"
    want = entry.get("digest")
    if want and str(getattr(hit, "digest", want)).startswith(str(want)) is False:
        return False, f"{entry.get('at')}: the digest is {getattr(hit, 'digest', '?')}, not {want}"
    return True, ""


def _minor(v: Any) -> str | None:
    mt = re.match(r"^\D*(\d+)\.(\d+)", str(v)) if v is not None else None
    return f"{mt.group(1)}.{mt.group(2)}" if mt else None


def _text_fields(node: Any, path: str = "", keys=("summary", "means")):
    """(field path, text) for every summary and meaning, at any depth (x0's a4lib.text_fields)."""
    if isinstance(node, dict):
        for k, v in node.items():
            p = f"{path}.{k}" if path else str(k)
            if k in keys and isinstance(v, str):
                yield p, v
            elif isinstance(v, (dict, list)):
                yield from _text_fields(v, p, keys)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _text_fields(v, f"{path}[{i}]", keys)


def source_text(root: Path) -> str:
    """The source folder's text files, read as text (never run), joined; the same read set x0 measured."""
    parts = []
    for f in sorted(root.rglob("*")):
        if ".git" in f.parts or not f.is_file() or f.is_symlink() or f.suffix not in SOURCE_SUFFIXES:
            continue
        try:
            parts.append(f.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, OSError):
            pass
    return "\n\u0000\n".join(parts)


def longest_carried(text: str, source: str, length: int) -> int:
    """The longest run of `source`'s text, of at least `length` code points, that `text` holds; 0 when none.
    x0's measure (a4lib.carried_runs): windows of `length` stepped by a quarter, each grown while it is still found."""
    if len(text) < length or not source:
        return 0
    best, step = 0, max(1, length // 4)
    for i in range(0, len(text) - length + 1, step):
        if text[i:i + length] in source:
            j = i + length
            while j < len(text) and text[i:j + 1] in source:
                j += 1
            best = max(best, j - i)
    return best


class _Checks:
    """The thirteen checks over one loaded fabulac. `add(check, item, message, field, severity=None)` reports;
    `unmeasured` collects the checks that could not be measured, with the reason."""

    def __init__(self, vol: mc.Volume, add: Callable[..., None], *, source: Path | None = None,
                 library: Any = None):
        self.v, self._add, self.library = vol, add, library
        self.items = list(vol.items.values())
        self.by_id = {it.id: it for it in self.items}
        blk = vol.manifest._block("transconception") if vol.manifest is not None else {}
        self.cfg = {**DEFAULTS, **{str(k): v for k, v in (blk or {}).items()}}
        src = vol.catalog.get("source")
        self.src = src if isinstance(src, dict) else {}
        self.language = self.src.get("language") if isinstance(self.src.get("language"), str) else None
        self.source_root = source if source is not None else self._source_root()
        self.unmeasured: dict[str, str] = {}
        self._source_text: str | None = None

    # ------------------------------------------------------------------ helpers
    def add(self, check: str, it: mc.Item | None, msg: str, fld: str | None = None, *,
            severity: str | None = None) -> None:
        self._add(check, it, msg, fld, severity=severity)

    def of(self, module: str, kind: str) -> list[mc.Item]:
        return [it for it in self.items if it.module == module and it.kind == kind]

    def _source_root(self) -> Path | None:
        p = self.src.get("path")
        if not isinstance(p, str) or not p.strip() or self.v.root is None:
            return None
        root = (self.v.root / p).resolve()
        return root if root.is_dir() else None

    def source(self) -> str | None:
        if self._source_text is None and self.source_root is not None:
            self._source_text = source_text(self.source_root)
        return self._source_text

    def source_target(self) -> str | None:
        """The `N:target` of the source language (the round trip's), by id."""
        for it in self.of("N", "target"):
            if self.language and it.data.get("language") == self.language:
                return it.id
        return None

    def file_paths(self) -> set[str]:
        return {it.data["path"] for it in self.of("C", "file") if isinstance(it.data.get("path"), str)}

    def scope(self) -> list[mc.Item]:
        kinds = {tuple(str(k).split(":", 1)) for k in self.cfg["ruled-kinds"]}
        return [it for it in self.items if (it.module, it.kind) in kinds]

    def kept_behaviours(self, target: str | None = None) -> list[mc.Item]:
        return [it for it in self.of("C", "behaviour")
                if any(r.get("is") in KEPT and applies(r, target) for r in rulings(it.data) if "pending" not in r)]

    def outside_cases(self) -> list[mc.Item]:
        return [it for it in self.of("P", "case") if it.data.get("stands") == "outside"]

    def shorts(self) -> list[dict]:
        s = self.v.catalog.get("shorts")
        return [x for x in s if isinstance(x, dict)] if isinstance(s, list) else []

    def cshort_folder(self, entry: dict) -> Path | None:
        p = entry.get("path")
        if not isinstance(p, str) or self.v.root is None:
            return None
        d = (self.v.root / p).resolve()
        return d if d.is_dir() else None

    # ------------------------------------------------------------------ the checks
    def run(self, only: tuple[str, ...] | None = None) -> None:
        for name in only or CHECKS:
            getattr(self, name.replace("-", "_"))()

    def standing(self) -> None:
        lic = self.of("R", "licence")
        if not lic:
            self.add("standing", None, "the source's licence is recorded as an R:licence, with its lane")
        for it in lic:
            lane = it.data.get("lane")
            if lane is None or mc.is_pending(lane):
                self.add("standing", it, "the licence's lane (open, bound, closed) is recorded", "lane")
            elif lane in LANES_NEEDING_LEAVE and not it.data.get("leave"):
                self.add("standing", it, "a closed lane carries the holder's leave", "leave")
        ob = self.src.get("obtained")
        if ob is None:
            self.add("standing", None, "how the source came (source.obtained: public, permitted, own) is not recorded",
                     "source.obtained", severity="warning")
        elif mc.is_pending(ob):
            self.add("standing", None, "how the source came is still a question", "source.obtained",
                     severity="warning")
        if kept_unruled(self.v):
            return
        tc = [it for it in self.of("R", "maker") if it.data.get("capacity") == CAPACITY]
        rb = self.v.catalog.get("ruled-by")
        if isinstance(rb, str) and rb != "none" and not any(it.id == rb for it in tc):
            self.add("standing", None, f"ruled-by names {rb}, which is not an R:maker of capacity {CAPACITY}",
                     "ruled-by")
        if not tc:
            self.add("standing", None, f"no R:maker of capacity {CAPACITY}: name who rules, or say ruled-by: none")
        for it in tc:
            st = it.data.get("statements")
            if not isinstance(st, dict):
                self.add("standing", it, f"the {CAPACITY}'s statements ({', '.join(STATEMENTS)}) are answered",
                         "statements")
                continue
            missing = [k for k in STATEMENTS if st.get(k) in (None, "", [], {}) or mc.is_pending(st.get(k))]
            if missing:
                self.add("standing", it, f"statements not answered: {', '.join(missing)}", "statements")

    def ground_given(self) -> None:
        for it in self.of("C", "dependency"):
            if it.data.get("scope") not in ("run-time", "standard"):
                continue
            nf = it.data.get("needed-for")
            if not (isinstance(nf, str) and nf.strip()):
                self.add("ground-given", it, "a run-time dependency says in plain words what it is needed for",
                         "needed-for")
        for it in self.of("C", "reliance"):
            for k in ("gives", "example"):
                v = it.data.get(k)
                if not (isinstance(v, str) and v.strip()):
                    self.add("ground-given", it, f"a reliance carries {k}"
                             + (" (plain words)" if k == "gives" else " (one plain example)"), k)

    def runtime_minor(self) -> str | None:
        for it in self.of("C", "dependency"):
            if self.language and it.data.get("package") == self.language:
                for k in ("resolved", "pinned"):
                    m = _minor(it.data.get(k))
                    if m:
                        return m
        return None

    def ground_cited(self) -> None:
        minor = self.runtime_minor()
        for it in self.of("C", "reliance"):
            if it.data.get("on") not in ("language", "runtime"):
                continue
            st = it.data.get("stated")
            if not isinstance(st, list) or not st:
                self.add("ground-cited", it, "a reliance on the language or its runtime carries stated: a list of "
                                             "{in, version, at, digest} and {nowhere: text}", "stated")
                continue
            for i, e in enumerate(st):
                fld = f"stated[{i}]"
                if isinstance(e, dict) and set(e) == {"nowhere"}:
                    if not (isinstance(e["nowhere"], str) and e["nowhere"].strip()):
                        self.add("ground-cited", it, "nowhere says what no text states", fld)
                    continue
                if not isinstance(e, dict) or any(not e.get(k) for k in ("in", "version", "at", "digest")):
                    self.add("ground-cited", it, "a citation is {in, version, at, digest}, or {nowhere: text}", fld)
                    continue
                if minor and e.get("in") == self.language and _minor(e["version"]) != minor:
                    self.add("ground-cited", it, f"{e['in']} {e['version']} is not a patch of the runtime's "
                                                 f"{minor}", fld)
                ok, why = resolve_citation(e, self.library)
                if ok is False:
                    self.add("ground-cited", it, why, fld)
            cb = it.data.get("contradicted-by")
            if cb is not None and not (isinstance(cb, dict) and cb.get("at") and cb.get("says")):
                self.add("ground-cited", it, "contradicted-by is {at, says, said}", "contradicted-by")

    def stands_alone(self) -> None:
        rx = SOURCE_NAMES.get(self.language or "")
        if rx is None:
            self.unmeasured["stands-alone"] = f"no names are known for the source language {self.language!r}"
            return
        said_by_reliance = set()
        for it in self.of("C", "reliance"):
            for ref in it.data.get("used-by") or []:
                if isinstance(ref, str):
                    said_by_reliance.add(ref)
        for it in self.items:
            if it.module in STANDS_ALONE_SKIP_MODULES or (it.module, it.kind) in STANDS_ALONE_SKIP_KINDS:
                continue
            if it.id in said_by_reliance:
                continue
            for fld, text in _text_fields(it.data):
                names = sorted({m.group(1) for m in rx.finditer(text)})
                if names:
                    self.add("stands-alone", it, f"names {', '.join(names)}: say it without the name, or let a "
                                                 "reliance say it (used-by)", fld)

    def _kept_everywhere(self, it: mc.Item) -> bool:
        rs = rulings(it.data)
        return bool(rs) and all(r.get("is") == "kept" for r in rs)

    def nothing_carried(self) -> None:
        src = self.source()
        if src is None:
            self.unmeasured["nothing-carried"] = "the source folder is not at hand (source.path)"
            return
        n = int(self.cfg["nothing-carried"])
        skip = ("span", "signature", "sha256")

        def walk(v: Any, p: str, it: mc.Item) -> None:
            if isinstance(v, dict):
                for k, x in v.items():
                    if k not in skip:
                        walk(x, f"{p}.{k}" if p else str(k), it)
            elif isinstance(v, list):
                for i, x in enumerate(v):
                    walk(x, f"{p}[{i}]", it)
            elif isinstance(v, str):
                run = longest_carried(v, src, n)
                if run:
                    self.add("nothing-carried", it, f"carries {run} code points of the source's own text (at most "
                                                    f"{n - 1}, unless it is ruled kept)", p)

        for it in self.items:
            if (it.module, it.kind) == ("P", "case") or self._kept_everywhere(it):
                continue
            walk(it.data, "", it)

    def case_outside(self) -> None:
        files = self.file_paths()
        calls = set()
        for it in self.of("C", "interface"):
            for k in ("name", "signature"):
                if isinstance(it.data.get(k), str):
                    calls.update(re.findall(r"[A-Za-z_][A-Za-z0-9_.]*", it.data[k]))
        for it in self.outside_cases():
            d = it.data
            refs = d.get("of") if isinstance(d.get("of"), list) else [d.get("of")]
            if not any(isinstance(r, str) and r.startswith("C:interface/") for r in refs):
                self.add("case-outside", it, "an outside case is of an interface: the boundary it stands at", "of")
            given, expect = d.get("given"), d.get("expect")
            steps = given.get("steps") if isinstance(given, dict) else None
            if not isinstance(steps, list) or not steps or not all(isinstance(s, dict) for s in steps):
                self.add("case-outside", it, "an outside case is whole data: given.steps, a list of steps", "given")
                continue
            exp = expect.get("steps") if isinstance(expect, dict) else None
            if isinstance(exp, dict):               # a ruled case: only the steps its ruling changes
                pairs = [(k, v) for k, v in exp.items()]
                bad = [k for k, _ in pairs if not (isinstance(k, int) and 0 <= k < len(steps))]
                if bad:
                    self.add("case-outside", it, f"expected steps {bad} are not steps of the case", "expect.steps")
            elif isinstance(exp, list) and len(exp) == len(steps):
                pairs = list(enumerate(exp))
            else:
                self.add("case-outside", it, "an outside case expects each step: expect.steps, one per given step",
                         "expect")
                continue
            for k, e in pairs:
                if not (isinstance(e, dict) and "exit" in e):
                    self.add("case-outside", it, "each expected step says its exit status", f"expect.steps[{k}]")
            gf = given.get("files")                 # a file an interface names (a format the program reads, such
            for name in (gf if isinstance(gf, dict) else {}):     # as pyproject.toml) is the boundary, not the source
                if str(name) in files and str(name) not in calls:
                    self.add("case-outside", it, f"given.files names {name}, a file of the source", "given.files")
            for i, s in enumerate(steps):
                for a in s.get("arguments") or []:
                    if isinstance(a, str) and a in files and a not in calls:
                        self.add("case-outside", it, f"step {i} names {a}, a file of the source",
                                 f"given.steps[{i}].arguments")
                inp = s.get("input")
                call = inp.get("call") if isinstance(inp, dict) else None
                if isinstance(call, str) and call not in calls:
                    self.add("case-outside", it, f"step {i} calls {call}, which no interface names",
                             f"given.steps[{i}].input.call")

    def cases_cover(self) -> None:
        kept = self.kept_behaviours()
        if not kept:
            return
        covered = set()
        for c in self.outside_cases():
            covered.update(r for r in (c.data.get("of") or []) if isinstance(r, str))
        uncovered = [it.id for it in kept if it.id not in covered]
        share = (len(kept) - len(uncovered)) / len(kept)
        if not uncovered:
            return
        msg = (f"{len(kept) - len(uncovered)} of {len(kept)} behaviours ruled kept are the subject of an outside case "
               f"({share:.0%}); not: {', '.join(uncovered[:12])}" + (" …" if len(uncovered) > 12 else ""))
        if share < float(self.cfg["cases-cover"]):
            self.add("cases-cover", None, msg)
        else:
            self.add("cases-cover", None, msg, severity="note")

    def ruled(self) -> None:
        if kept_unruled(self.v):
            self.add("ruled", None, "ruled-by: none: nobody could rule this fabulac; it is kept unruled", "ruled-by")
            return
        needs = self.cfg["ruling-needs"] if isinstance(self.cfg["ruling-needs"], dict) else {}
        allowances = set(self.cfg["allowances"])
        for it in self.scope():
            r = it.data.get("ruling")
            if r is None or r == []:
                self.add("ruled", it, "carries no ruling: must the next program do exactly this?", "ruling")
                continue
            if not isinstance(r, list):
                self.add("ruled", it, "ruling is a list, one entry per target (made-for)", "ruling")
                continue
            for i, x in enumerate(r):
                fld = f"ruling[{i}]"
                if not isinstance(x, dict) or "pending" in x or not x.get("is"):
                    self.add("ruled", it, "not ruled yet", fld)
                    continue
                for k in needs.get(x["is"], []):
                    alts = str(k).split("|")            # a|b: either will do
                    if not any(x.get(a) for a in alts):
                        self.add("ruled", it, f"a ruling {x['is']} says {' or '.join(alts)}", f"{fld}.{alts[0]}")
                if x["is"] == "alike" and x.get("allowing") and x["allowing"] not in allowances:
                    self.add("ruled", it, f"the judge knows no allowance {x['allowing']!r} ("
                                          f"{', '.join(sorted(allowances))}); it holds until entailing for "
                                          f"{x.get('made-for', 'any target')}", f"{fld}.allowing", severity="warning")

    def not_ruled_for(self, target_ref: str) -> list[str]:
        """The items in scope with no ruling for the target the judge can read (gate 2)."""
        allowances = set(self.cfg["allowances"])
        out = []
        for it in self.scope():
            ok = [r for r in rulings(it.data) if "pending" not in r and r.get("is") and applies(r, target_ref)]
            if not ok or any(r["is"] == "alike" and r.get("allowing") not in allowances for r in ok):
                out.append(it.id)
        return out

    def round_trip(self) -> None:
        t = self.source_target()
        if t is None:
            self.add("round-trip", None, f"no N:target in the source language ({self.language}): the round trip "
                                         "is entailed for it")
            return
        level = int(self.cfg["round-trip-level"])
        best = None
        for e in self.shorts():
            ev = e.get("evidence")
            if e.get("target") == t and isinstance(ev, dict) and isinstance(ev.get("level"), int):
                state, why = freshness(ev.get("source"), source_of(self.v.catalog))
                if state == "stale":            # evidence stands against the source it was judged on, and no other
                    self.add("round-trip", None, f"the evidence of {e.get('path')} is stale: {why}", "shorts",
                             severity="note")
                    continue
                best = max(best or 0, ev["level"])
        if best is None or best < level:
            self.add("round-trip", None, f"no cshort in {self.language} stands at level {level} or more by its "
                                         f"evidence" + (f" (the best is {best})" if best is not None else ""),
                     "shorts")

    def target_confirmed(self, language: str | None = None) -> None:
        for it in self.of("N", "target"):
            lang = it.data.get("language")
            if lang == self.language or (language is not None and lang != language):
                continue
            if "verdict" not in it.data:
                if language is None:
                    self.add("target-confirmed", it, f"{lang} is not weighed yet", "verdict", severity="note")
                else:
                    self.add("target-confirmed", it, f"{lang} is not weighed: no verdict", "verdict")
                continue
            if it.data.get("verdict") not in ("feasible", "feasible-with"):
                self.add("target-confirmed", it, f"the verdict on {lang} is {it.data.get('verdict')!r}", "verdict")
            provided = {p.get("for") for p in (it.data.get("provides") or []) if isinstance(p, dict)
                        and p.get("by") not in ("cannot", None)}
            for r in self.of("C", "reliance"):
                if any(x.get("is") in KEPT and applies(x, it.id) for x in rulings(r.data)) and r.id not in provided:
                    self.add("target-confirmed", it, f"{lang} provides nothing for {r.id}, which is kept", "provides")
            sp = it.data.get("spike")
            if not (isinstance(sp, dict) and isinstance(sp.get("level"), int) and sp["level"] >= SPIKE_LEVEL):
                self.add("target-confirmed", it, f"the spike in {lang} has not reached level {SPIKE_LEVEL}", "spike")
        if language is not None and not any(it.data.get("language") == language for it in self.of("N", "target")):
            self.add("target-confirmed", None, f"no N:target for {language}")

    def _other_cshorts(self) -> list[dict]:
        src = self.source_target()
        return [e for e in self.shorts() if isinstance(e.get("target"), str) and e["target"] != src]

    def surface_answered(self) -> None:
        for e in self._other_cshorts():
            d = self.cshort_folder(e)
            if d is None or not (d / "CSHORT.md").is_file():
                self.unmeasured["surface-answered"] = f"{e.get('path')}: the cshort's CSHORT.md is not at hand"
                continue
            rows = {}
            for ln in (d / "CSHORT.md").read_text(encoding="utf-8").splitlines():
                cells = [c.strip().strip("`") for c in ln.strip().strip("|").split("|")]
                if len(cells) >= 3 and cells[0].startswith("C:interface/"):
                    rows[cells[0]] = (cells[1], cells[2])
            for it in self.of("C", "interface"):
                if not any(r.get("is") in ("kept", "alike") and applies(r, e["target"]) for r in rulings(it.data)):
                    continue
                row = rows.get(it.id)
                if row is None:
                    self.add("surface-answered", it, f"{e.get('path')}: CSHORT.md maps it to no file and name")
                    continue
                f = d / row[0]
                if not f.is_file() or row[1] not in f.read_text(encoding="utf-8", errors="replace"):
                    self.add("surface-answered", it, f"{e.get('path')}: {row[1]} is not in {row[0]}")

    def apart(self) -> None:
        files, n, src = self.file_paths(), int(self.cfg["nothing-carried"]), None
        for e in self._other_cshorts():
            if e.get("entailed") != "apart":
                continue
            d = self.cshort_folder(e)
            req = d / "requests.jsonl" if d is not None else None
            if req is None or not req.is_file():
                self.unmeasured["apart"] = f"{e.get('path')}: the entailing's requests are not at hand"
                continue
            src = src if src is not None else (self.source() or "")
            for i, ln in enumerate(req.read_text(encoding="utf-8").splitlines()):
                text = ln
                try:
                    text = json.dumps(json.loads(ln), ensure_ascii=False)
                except ValueError:
                    pass
                why = None
                if re.search(r'"span"\s*:', text) or re.search(r'"file"\s*:\s*"[^"]+"\s*,\s*"lines"', text):
                    why = "carried a span"
                elif any(f and f in text for f in files):
                    why = "named a path of the source"
                elif src and longest_carried(text, src, n):
                    why = "carried the source's own text"
                if why:
                    self.add("apart", None, f"{e.get('path')}: request {i + 1} {why}", "shorts")

    def evidence_stated(self) -> None:
        for e in self.shorts():
            ev = e.get("evidence")
            if ev is None:
                continue
            where = f"shorts ({e.get('path')})"
            if not isinstance(ev, dict):
                self.add("evidence-stated", None, f"{where}: evidence is {{level, steps, against, inputs, where, at, by}}",
                         "shorts")
                continue
            lv, st, wh = ev.get("level"), ev.get("steps"), ev.get("where")
            if not (isinstance(lv, int) and 1 <= lv <= 4):
                self.add("evidence-stated", None, f"{where}: evidence.level is 1 to 4", "shorts")
            if not (isinstance(st, dict) and isinstance(st.get("kept"), int) and isinstance(st.get("agree"), int)
                    and 0 <= st["agree"] <= st["kept"]):
                self.add("evidence-stated", None, f"{where}: evidence.steps is {{kept, agree}}, agree no more than kept",
                         "shorts")
            if not (isinstance(wh, dict) and wh.get("file") and wh.get("digest")):
                self.add("evidence-stated", None, f"{where}: evidence.where names the verdict file and its digest",
                         "shorts")
                continue
            f = (self.v.root / str(wh["file"])) if self.v.root is not None else None
            if f is not None and f.is_file():
                got = hashlib.sha256(f.read_bytes()).hexdigest()
                if not got.startswith(str(wh["digest"])):
                    self.add("evidence-stated", None, f"{where}: {wh['file']} has digest {got[:12]}, not "
                                                      f"{wh['digest']}", "shorts")


def run_checks(vol: mc.Volume, add: Callable[..., None], *, source: Path | None = None,
               library: Any = None) -> dict[str, str]:
    """The thirteen checks on a fabulac kept for transconception, through `add`; nothing for any other volume.
    Returns the checks not measured, with the reason."""
    if not is_transconception(vol):
        return {}
    c = _Checks(vol, add, source=source, library=library)
    c.run()
    return c.unmeasured


# ---------------------------------------------------------------------------
# The two gates
# ---------------------------------------------------------------------------

def _gate(vol: mc.Volume, names: tuple[str, ...], *, language: str | None, source: Path | None,
          library: Any) -> dict:
    found: dict[str, list[mc.Problem]] = {n: [] for n in names}

    def add(check, it, msg, fld=None, *, severity=None):
        if check in found:
            found[check].append(mc.Problem(check, severity or SEVERITY.get(check, "error"), it.key if it else "",
                                           it.file if it else vol.catalog_file, msg, fld))

    c = _Checks(vol, add, source=source, library=library)
    for n in names:
        if n == "target-confirmed":
            c.target_confirmed(language)
        else:
            getattr(c, n.replace("-", "_"))()
    if language is not None and "ruled" in names and not kept_unruled(vol):
        t = next((it.id for it in c.of("N", "target") if it.data.get("language") == language), None)
        for iid in c.not_ruled_for(t or f"N:target/{language}"):
            found["ruled"].append(mc.Problem("ruled", "error", iid, "", f"not ruled for {language}, or with an "
                                                                         "allowance the judge does not know"))
    checks = {}
    for n in names:
        errs = [str(p) for p in found[n] if p.severity == "error"]
        warns = [str(p) for p in found[n] if p.severity == "warning"]
        if n in c.unmeasured:
            state = "not measured"
        else:
            state = "holds" if not errs else "fails"
        checks[n] = {"state": state, "errors": errs, "warnings": warns,
                     "notes": [str(p) for p in found[n] if p.severity == "note"],
                     **({"why": c.unmeasured[n]} if n in c.unmeasured else {})}
    holding = [n for n in names if checks[n]["state"] == "holds"]
    return {"holds": len(holding) == len(names) and is_transconception(vol), "purpose": vol.catalog.get("purpose"),
            "kept-unruled": kept_unruled(vol), "hold": holding,
            "do-not-hold": [n for n in names if checks[n]["state"] == "fails"],
            "not-measured": [n for n in names if checks[n]["state"] == "not measured"], "checks": checks}


def ready_to_keep(volume, *, source: Path | None = None, library: Any = None) -> dict:
    """Gate 1, ready to keep: which of its nine checks hold and which do not, on a fabulac (a path or a loaded
    volume). `source` is the source folder when it is not at `source.path` beside the fabulac. A fabulac whose
    catalog says `ruled-by: none` is reported `kept unruled`."""
    vol = volume if isinstance(volume, mc.Volume) else mc.load_volume(volume)
    g = _gate(vol, READY_TO_KEEP, language=None, source=source, library=library)
    if not is_transconception(vol):
        g["says"] = "not kept for transconception (no purpose: transconception)"
    elif g["kept-unruled"]:
        g["says"] = "kept unruled"
    else:
        g["says"] = "ready to keep" if g["holds"] else "not ready to keep"
    return {"gate": "ready-to-keep", **g}


def ready_to_entail(volume, language: str, *, source: Path | None = None, library: Any = None) -> dict:
    """Gate 2, ready to entail into a named language: gate 1's checks, every ruled item ruled for that language with
    an allowance the judge knows, and target-confirmed for it."""
    vol = volume if isinstance(volume, mc.Volume) else mc.load_volume(volume)
    g = _gate(vol, READY_TO_ENTAIL, language=language, source=source, library=library)
    if not is_transconception(vol):
        g["says"] = "not kept for transconception (no purpose: transconception)"
    elif g["kept-unruled"]:
        g["says"] = "kept unruled: nothing is entailed into another language before it is ruled"
        g["holds"] = False
    else:
        g["says"] = f"ready to entail in {language}" if g["holds"] else f"not ready to entail in {language}"
    return {"gate": "ready-to-entail", "language": language, **g}


# ---------------------------------------------------------------------------
# Cases (phase 4): the cases file, recordings, verdicts, and the source they stand against
# ---------------------------------------------------------------------------
#
# The cases file is the harness's own shape (the experiment's x0 kit, promoted to tools/transconception/harness.py):
#
#     {"repo": <the source folder's name>, "fabulac": <the fabulac's id>, "source": {commit, tree},
#      ... any other key the file already had (boundary, drafted, masks) ...,
#      "cases": [{"id", "of", "from", "files", "env", "cwd", "steps", "reliances", "note",
#                 "item", "expect": {"steps": [{exit, out, err}], "written": {...}}, "recorded": {...}, "stale"}],
#      "rulings": {"targets": {<language>: {"made-for", "labels", "interfaces", "cases"}}}}
#
# `id`, `of`, `files`, `env`, `cwd` and `steps` are what the runner reads (a step is an argument list or
# `{argv, stdin}`); `expect` and `recorded` are what a recording said, and from which source; `stale` says why a
# recorded expectation does not stand against the source the fabulac is about now. `rulings` is what the judge reads
# for each target, derived from the fabulac's rulings, never edited by hand.

CASES_SUFFIX = ".cases.json"
#: The judge's finding kinds that need no ruling: a difference a ruling already allows, shown for reading.
SHOWN_FINDINGS = ("ruled difference", "ruled change not seen")
#: The judge's finding for a case enough marked stale: it needs the original recorded again, not a ruling.
STALE_FINDING = "recorded against another source"
#: The labels the judge picks a target by: a cshort's label begins with one (`go-apart` is go's). The experiment
#: labelled its Python round trips `py-…`; every other language is labelled by its name.
JUDGE_LABELS = {"python": ["py", "python"]}
#: The keys of a case ruling the judge reads (x0's write_a4.JUDGE_KEYS).
JUDGE_KEYS = ("is", "allowing", "steps", "to", "about", "said")
#: A case's keys in the order the file writes them (the runner's first, then what a recording added).
CASE_ORDER = ("id", "of", "from", "group", "files", "env", "cwd", "burst", "steps", "reliances", "note", "item",
              "expect", "expect-says", "recorded", "stale")


class CasesError(ValueError):
    """A cases file, a recording or a verdict that cannot be read, or that names what the fabulac does not hold."""


def dump_cases(doc: dict) -> str:
    """The cases file's text: JSON, one-space indent, UTF-8 kept, a final newline (the harness's own dump)."""
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def cases_name(catalog: Mapping) -> str:
    """The cases file a fabulac's catalog names (`cases:`), else `<folder>.cases.json` after its source folder."""
    named = catalog.get("cases")
    if isinstance(named, str) and named.strip():
        return named.strip()
    src = catalog.get("source") if isinstance(catalog.get("source"), dict) else {}
    folder = Path(str(src.get("path") or "")).name if src.get("path") else ""
    return f"{folder or catalog.get('name') or 'fabulac'}{CASES_SUFFIX}"


def source_of(catalog: Mapping) -> dict:
    """The marks of the source a fabulac is about now: `{commit, tree}`, each when the catalog carries it."""
    src = catalog.get("source") if isinstance(catalog.get("source"), dict) else {}
    return {k: str(src[k]) for k in ("commit", "tree") if isinstance(src.get(k), str) and src[k]}


def _source_marks(x: Any) -> dict:
    """`{commit, tree}` from what a recording, a case or an evidence says it was made from: `{commit, tree}`,
    x0's `{source-commit}`, a `{source: {...}}` around either, or a commit as a string."""
    if isinstance(x, str) and x.strip():
        return {"commit": x.strip()}
    if not isinstance(x, dict):
        return {}
    if isinstance(x.get("source"), (dict, str)):
        return _source_marks(x["source"])
    out = {}
    for key, names in (("commit", ("commit", "source-commit")), ("tree", ("tree", "source-tree"))):
        for n in names:
            if isinstance(x.get(n), str) and x[n]:
                out[key] = x[n]
                break
    return out


def freshness(recorded_from: Any, now: Any) -> tuple[str, str]:
    """Whether what was recorded (or judged) from one source stands against the source as it is now:
    `("fresh", "")`, `("stale", why)`, or `("unnamed", why)` when either side names no mark to compare. The tree
    digest is compared first (it is the source's content), then the commit."""
    rf, nw = _source_marks(recorded_from), _source_marks(now)
    if not rf:
        return "unnamed", "it does not say which source it was recorded from"
    if not nw:
        return "unnamed", "the fabulac names no source to stand it against"
    for key in ("tree", "commit"):
        if rf.get(key) and nw.get(key):
            if rf[key] == nw[key]:
                return "fresh", ""
            return "stale", f"recorded from {key} {rf[key][:12]}; the source is now {key} {nw[key][:12]}"
    return "unnamed", "it names its source by a mark the fabulac does not carry"


def _items(nodes: list[dict], prefix: str) -> list[dict]:
    return [n for n in nodes if isinstance(n, dict) and str(n.get("id", "")).startswith(prefix)]


def _key(item: dict, prefix: str) -> str:
    """The id a cases file uses for an item: its worksheet id where the experiment gave one (`V-C01`), else its id
    without the kind (`x0.V-C01`, `command.add`)."""
    wid = item.get("worksheet-id")
    if isinstance(wid, str) and wid.strip():
        return wid.strip()
    iid = str(item.get("id", ""))
    return iid[len(prefix):] if iid.startswith(prefix) else iid


def harness_step(step: Any) -> Any:
    """A case's given step (`{arguments, input}`) as the runner reads it: the argument list, or `{argv, stdin}`."""
    if not isinstance(step, dict):
        return step
    args = [str(a) for a in (step.get("arguments") or [])]
    if step.get("input") is not None:
        return {"argv": args, "stdin": copy.deepcopy(step["input"])}
    return args


def given_step(step: Any) -> dict:
    """The runner's step as a case's given step (x0's a4lib.case_given)."""
    if isinstance(step, list):
        return {"arguments": [str(a) for a in step]}
    out: dict = {}
    if isinstance(step, dict):
        if step.get("argv"):
            out["arguments"] = [str(a) for a in step["argv"]]
        if step.get("stdin") is not None:
            out["input"] = copy.deepcopy(step["stdin"])
    return out


def harness_expect(e: Any) -> Any:
    """A case's expected step (`{exit, output, error-output}`) as the harness writes a step (`{exit, out, err}`)."""
    if not isinstance(e, dict):
        return e
    out = {"exit": e.get("exit")}
    if "output" in e:
        out["out"] = e["output"]
    if "error-output" in e:
        out["err"] = e["error-output"]
    return out


def case_expect(s: Any) -> Any:
    """The harness's step as a case's expected step."""
    if not isinstance(s, dict):
        return s
    return {"exit": s.get("exit"), "output": s.get("out", ""), "error-output": s.get("err", "")}


def _ordered(case: dict) -> dict:
    out = {k: case[k] for k in CASE_ORDER if k in case}
    out.update({k: v for k, v in case.items() if k not in out})
    return out


def case_from_item(item: dict, iface_keys: Mapping[str, str], reliance_keys: Mapping[str, list[str]]) -> dict | None:
    """One outside `P:case` item as a case of the cases file; None for a case the file does not run (an inside one,
    or one ruled: its changed expectation reaches the judge through `rulings`)."""
    if item.get("stands") != "outside" or item.get("from") == "ruled":
        return None
    given = item.get("given") if isinstance(item.get("given"), dict) else {}
    refs = item.get("of") if isinstance(item.get("of"), list) else [item.get("of")]
    iface = next((r for r in refs if isinstance(r, str) and r.startswith("C:interface/")), None)
    case: dict = {"id": _key(item, "P:case/"),
                  "of": iface_keys.get(iface, iface[len("C:interface/"):]) if iface else None,
                  "from": item.get("drafted-from") or item.get("from")}
    for k in ("files", "env", "cwd"):
        if given.get(k) not in (None, {}, ""):
            case[k] = copy.deepcopy(given[k])
    case["steps"] = [harness_step(s) for s in (given.get("steps") or [])]
    rel = reliance_keys.get(str(item.get("id")))
    if rel:
        case["reliances"] = list(rel)
    if isinstance(item.get("note"), str) and item["note"]:
        case["note"] = item["note"]
    case["item"] = item.get("id")
    exp = item.get("expect") if isinstance(item.get("expect"), dict) else {}
    if isinstance(exp.get("steps"), list):
        case["expect"] = {"steps": [harness_expect(e) for e in exp["steps"]]}
        if isinstance(exp.get("files"), dict) and exp["files"]:
            case["expect"]["written"] = copy.deepcopy(exp["files"])
    rec = item.get("recorded")
    if isinstance(rec, dict):
        r = {"source": _source_marks(rec)}
        r.update({k: copy.deepcopy(v) for k, v in rec.items() if k not in ("source", "source-commit", "source-tree")})
        case["recorded"] = r
    return _ordered(case)


def judge_rulings(catalog: Mapping, nodes: list[dict]) -> dict:
    """What the judge reads, for each target the fabulac names (`N:target`): the ruling of each interface (`is`,
    and the allowance of an `alike`), and each case's rulings other than kept with the steps they cover. A ruling
    made for the target wins over one made for any target. Derived, never edited (survey 2.4)."""
    targets: dict = {}
    for t in _items(nodes, "N:target/"):
        lang, tid = str(t.get("language") or t["id"][len("N:target/"):]), t["id"]
        interfaces: dict = {}
        for it in _items(nodes, "C:interface/"):
            rs = [r for r in rulings(it) if applies(r, tid) and "pending" not in r and r.get("is")]
            rs.sort(key=lambda r: r.get("made-for") != tid)
            if rs:
                interfaces[_key(it, "C:interface/")] = {k: rs[0][k] for k in ("is", "allowing") if k in rs[0]}
        cases: dict = {}
        for c in _items(nodes, "P:case/"):
            if c.get("stands") != "outside" or c.get("from") == "ruled":
                continue
            rs = [r for r in rulings(c) if applies(r, tid) and r.get("is") and r["is"] != "kept"]
            if rs:
                cases[_key(c, "P:case/")] = [{k: r[k] for k in JUDGE_KEYS if k in r} for r in rs]
        targets[lang] = {"made-for": tid, "labels": list(JUDGE_LABELS.get(lang, [lang])), "interfaces": interfaces,
                         "cases": cases}
    return {"targets": targets}


def _mark(case: dict, now: Mapping) -> dict | None:
    """Set or clear the case's `stale` by the source its expectation was recorded from; the report row when it is
    not fresh. A case with neither an expectation nor a recording is neither."""
    case.pop("stale", None)
    if "expect" not in case and "recorded" not in case:
        return None
    rec = case.get("recorded")
    state, why = freshness(rec if isinstance(rec, dict) else None, now)
    if state == "fresh":
        return None
    case["stale"] = why
    return {"case": case.get("id"), "item": case.get("item"), "state": state, "why": why}


def cases_document(catalog: Mapping, nodes: list[dict], *, existing: Mapping | None = None) -> tuple[dict, dict]:
    """The cases file of a fabulac, as data, and a report: every case of the file already there (`existing`, read
    from beside the fabulac) and every outside case among the fabulac's own `P:case` items, by id, the item's words
    over the file's for what the item says, the file's recorded expectation kept where the item has none; every case
    marked `stale` whose expectation was recorded from another source (or does not say which); and the judge's
    `rulings` derived again. Report: `{cases, from-items, from-file, stale: [{case, item, state, why}]}`."""
    ex = dict(existing or {})
    now = source_of(catalog)
    iface_keys = {str(it["id"]): _key(it, "C:interface/") for it in _items(nodes, "C:interface/")}
    reliance_keys: dict[str, list[str]] = {}
    for r in _items(nodes, "C:reliance/"):
        for ref in r.get("shown-by") or []:
            if isinstance(ref, str):
                reliance_keys.setdefault(ref, []).append(_key(r, "C:reliance/"))
    by_id: dict[str, dict] = {}
    order: list[str] = []
    for c in ex.get("cases") or []:
        if isinstance(c, dict) and isinstance(c.get("id"), str) and c["id"] not in by_id:
            by_id[c["id"]] = copy.deepcopy(c)
            order.append(c["id"])
    from_file, from_items = len(order), 0
    for it in _items(nodes, "P:case/"):
        case = case_from_item(it, iface_keys, reliance_keys)
        if case is None:
            continue
        from_items += 1
        old = by_id.get(case["id"])
        if old is None:
            by_id[case["id"]] = case
            order.append(case["id"])
            continue
        for k in ("expect", "recorded"):                # the file's newer recording stands where the item has none
            if k not in case and k in old:
                case[k] = old[k]
        old.update(case)
        by_id[case["id"]] = _ordered(old)
    stale = [row for cid in order if (row := _mark(by_id[cid], now))]
    src = catalog.get("source") if isinstance(catalog.get("source"), dict) else {}
    head = {"repo": ex.get("repo") or Path(str(src.get("path") or "")).name or catalog.get("name"),
            "fabulac": catalog.get("id"), "source": now}
    doc = {**head, **{k: v for k, v in ex.items() if k not in head and k not in ("cases", "rulings")},
           "cases": [by_id[cid] for cid in order], "rulings": judge_rulings(catalog, nodes)}
    return doc, {"cases": len(order), "from-items": from_items, "from-file": from_file, "stale": stale}


def check_cases_doc(doc: Any) -> list[str]:
    """What is wrong with a cases file's data as the runner reads it (empty when it is whole): a `cases` list, each
    case with a unique `id`, an `of`, and `steps`, each an argument list or `{argv, stdin}`."""
    if not isinstance(doc, dict) or not isinstance(doc.get("cases"), list):
        return ["a cases file is a mapping with a list of cases"]
    out, seen = [], set()
    for i, c in enumerate(doc["cases"]):
        if not isinstance(c, dict) or not isinstance(c.get("id"), str) or not c["id"]:
            out.append(f"case {i} has no id")
            continue
        if c["id"] in seen:
            out.append(f"{c['id']}: the id is used twice")
        seen.add(c["id"])
        if not isinstance(c.get("of"), str) or not c["of"]:
            out.append(f"{c['id']}: names no interface it is of")
        steps = c.get("steps")
        if not isinstance(steps, list) or not steps:
            out.append(f"{c['id']}: has no steps")
            continue
        for k, s in enumerate(steps):
            argv = s if isinstance(s, list) else (s.get("argv", []) if isinstance(s, dict) else None)
            if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
                out.append(f"{c['id']}: step {k} is neither an argument list nor {{argv, stdin}}")
    return out


# --- recordings ----------------------------------------------------------------------------------------------------

class Recording:
    """A recording folder as the harness leaves it (x0's `out/<repo>/`): `recorded.json` (the original's steps,
    stable across two hash seeds, `unstable` beside them), and `cases.json`, the cases it was recorded on. `source` is
    the source it was recorded from: `recorded.json`'s own `source`, else the `<repo>: <commit>` line of the
    experiment's `environment.txt` one folder up, else nothing (and every case it gives is then unnamed)."""

    def __init__(self, recorded: dict, cases: dict | None, *, name: str, digest: str, source: dict):
        self.recorded, self.cases, self.name, self.digest, self.source = recorded, cases, name, digest, source


def read_recording(get: Callable[[str], bytes | None], *, name: str, environment: str | None = None) -> Recording:
    """A recording folder read through `get(relative path) -> bytes or None` (a folder on disk, or a folder value's
    files). `environment` is the text of the `environment.txt` beside it, when there is one."""
    raw = get("recorded.json")
    if raw is None:
        raise CasesError(f"{name}: no recorded.json: a recording folder holds the original's recorded steps")
    try:
        rec = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise CasesError(f"{name}/recorded.json is not JSON: {e}") from None
    if not isinstance(rec, dict) or not isinstance(rec.get("rows"), list):
        raise CasesError(f"{name}/recorded.json holds no rows: it is not a recording")
    craw = get("cases.json")
    cases = None
    if craw is not None:
        try:
            cases = json.loads(craw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as e:
            raise CasesError(f"{name}/cases.json is not JSON: {e}") from None
        got = hashlib.sha256(craw).hexdigest()
        if rec.get("cases_digest") and got != rec["cases_digest"]:
            raise CasesError(f"{name}: cases.json is not the cases file the recording was made on (digest "
                             f"{got[:12]}, recorded {str(rec['cases_digest'])[:12]})")
    source = _source_marks(rec.get("source"))
    if not source and environment:
        repo = (cases or {}).get("repo") or name.rstrip("/").rsplit("/", 1)[-1]
        m = re.search(rf"^{re.escape(str(repo))}: ([0-9a-f]{{40}})\s*$", environment, re.M)
        if m:
            source = {"commit": m.group(1)}
    return Recording(rec, cases, name=name, digest=hashlib.sha256(raw).hexdigest(), source=source)


def read_recording_folder(folder: Path) -> Recording:
    """A recording folder on disk (the owner's `out/<repo>/`, or a collected `results/<stamp>/<repo>/`)."""
    folder = Path(folder)
    env = folder.parent / "environment.txt"

    def get(rel: str) -> bytes | None:
        p = folder / rel
        return p.read_bytes() if p.is_file() else None

    return read_recording(get, name=folder.name,
                          environment=env.read_text(encoding="utf-8") if env.is_file() else None)


def _as_step(s: Any) -> dict:
    """A step as the runner runs it (x0's as_step): `{argv, stdin}`, stdin as text."""
    if isinstance(s, list):
        return {"argv": [str(a) for a in s], "stdin": None}
    if not isinstance(s, dict):
        return {"argv": [], "stdin": None}
    stdin = s.get("stdin")
    if stdin is not None and not isinstance(stdin, str):
        stdin = json.dumps(stdin, ensure_ascii=True)
    return {"argv": [str(a) for a in s.get("argv", [])], "stdin": stdin}


def gather_recorded(doc: Mapping, rec: Recording, *, now: Mapping | None = None) -> tuple[dict, dict]:
    """The cases file with a recording read into it: each recorded case gets `expect` (the original's steps, and the
    files it left) and `recorded` (the source it was recorded from, the recording's file and digest, the runtime, the
    seeds, the cases digest, the steps that differed between seeds); a case the recording holds and the file does not
    is added from the recording's own cases; a case whose steps changed since it was recorded keeps no expectation
    and is marked `stale`; and each case is marked against the source the fabulac is about now (`now`, else the
    file's own `source`). Nothing of the file is lost. Report: `{recorded, added, stale, unknown}`."""
    out = copy.deepcopy(dict(doc))
    now = dict(now) if now is not None else _source_marks(out.get("source"))
    cases = out.setdefault("cases", [])
    by_id = {c["id"]: c for c in cases if isinstance(c, dict) and isinstance(c.get("id"), str)}
    rcases = {c["id"]: c for c in ((rec.cases or {}).get("cases") or []) if isinstance(c, dict) and "id" in c}
    unstable: dict[str, list] = {}
    for u in rec.recorded.get("unstable") or []:
        if isinstance(u, dict):
            unstable.setdefault(str(u.get("case")), []).append(u.get("step"))
    report: dict = {"recorded": [], "added": [], "stale": [], "unknown": []}
    seeds = rec.recorded.get("seeds") or ([rec.recorded["seed"]] if "seed" in rec.recorded else [])
    for row in rec.recorded["rows"]:
        cid = str(row.get("id"))
        c = by_id.get(cid)
        if c is None:
            src = rcases.get(cid)
            if src is None:
                report["unknown"].append(cid)       # a row with no case anywhere: its inputs are not known whole
                continue
            c = {k: copy.deepcopy(v) for k, v in src.items() if k not in ("expect", "recorded", "stale")}
            cases.append(c)
            by_id[cid] = c
            report["added"].append(cid)
        run = row.get("run") if isinstance(row.get("run"), dict) else {}
        if [_as_step(s) for s in row.get("argv") or []] != [_as_step(s) for s in c.get("steps") or []]:
            c.pop("expect", None)
            c["recorded"] = {"source": dict(rec.source), "run": f"{rec.name}/recorded.json", "digest": rec.digest}
            c["stale"] = "the case's steps changed since it was recorded: record it again"
            report["stale"].append({"case": cid, "item": c.get("item"), "state": "stale", "why": c["stale"]})
            continue
        c["expect"] = {"steps": [{k: s.get(k) for k in ("exit", "out", "err")} for s in run.get("steps") or []]}
        if run.get("written"):
            c["expect"]["written"] = copy.deepcopy(run["written"])
        r = {"source": dict(rec.source), "run": f"{rec.name}/recorded.json", "digest": rec.digest,
             "python": rec.recorded.get("python"), "seeds": list(seeds),
             "cases-digest": rec.recorded.get("cases_digest")}
        if cid in unstable:
            r["unstable-steps"] = unstable[cid]
        c["recorded"] = r
        c.pop("expect-says", None)
        report["recorded"].append(cid)
        row_mark = _mark(c, now)
        if row_mark:
            report["stale"].append(row_mark)
    out["cases"] = [_ordered(c) for c in cases]
    return out, report


# --- verdicts --------------------------------------------------------------------------------------------------------

def read_verdict(raw: bytes, *, name: str = "verdict.json") -> dict:
    """A verdict file as the judge writes it: `{cshort, against, target, steps: {kept, agree}, share, passes,
    findings, ...}`."""
    try:
        v = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise CasesError(f"{name} is not JSON: {e}") from None
    if not isinstance(v, dict) or not isinstance(v.get("steps"), dict) or "cshort" not in v:
        raise CasesError(f"{name} is not a verdict: it holds no cshort and no steps")
    return v


def differences_from_verdict(verdict: Mapping) -> list[dict]:
    """The judge's findings in a verdict, as data for the rulings: one mapping per finding, in the verdict's order,
    `{case, step, kind, needs-ruling, target, cshort, of, argv, original, cshort-gave, ruling, allowing, why}` (a key
    the finding has nothing for is left out, but `case`, `kind` and `needs-ruling` are always there). `needs-ruling` is
    false for what a ruling already allows (a ruled difference, a ruled change not seen) and for a case recorded from
    another source (it needs the original recorded again); everything else waits for the transconceiver: an unruled
    difference, an interface not ruled, an unstable original, an allowance the judge does not know. Nothing is raised
    here: the rulings lane turns these into questions (`why: conflict`)."""
    out = []
    for f in verdict.get("findings") or []:
        if not isinstance(f, dict):
            continue
        row = {"case": f.get("case"), "step": f.get("step"), "kind": f.get("kind"),
               "needs-ruling": f.get("kind") not in SHOWN_FINDINGS + (STALE_FINDING,),
               "target": verdict.get("target"),
               "cshort": verdict.get("cshort"), "of": f.get("of"), "argv": f.get("argv"),
               "original": f.get("original"), "cshort-gave": f.get("cshort"), "ruling": f.get("ruling"),
               "allowing": f.get("allowing"), "why": f.get("why")}
        out.append({k: v for k, v in row.items() if v is not None or k in ("case", "kind", "needs-ruling")})
    return out


def _cshort_label(entry: Mapping) -> str:
    return str(entry.get("path") or "").rstrip("/").rsplit("/", 1)[-1]


def fold_verdict(catalog: Mapping, verdict: Mapping, *, verdict_bytes: bytes, where: str, at: str,
                 by: str) -> tuple[dict, dict]:
    """The catalog with a verdict read into its cshort's `evidence`: the `shorts` entry whose folder is the
    verdict's cshort (`told/py-roundtrip/` for `py-roundtrip`, `<folder>.cshort-<stamp>/` for that whole name),
    its evidence `{level, steps: {kept, agree}, against, inputs, where: {file, digest}, at, by, source}`. A passing
    verdict stands at level 3 (the recorded cases judged and passing); one that does not pass leaves the level the
    entry had, at most 2, or 1 (it built and ran). Returns the new catalog and a report `{cshort, level, passes,
    differences, needs-ruling, stale}`; raises nothing into the fabulac (no question is written here)."""
    label = str(verdict.get("cshort") or "")
    shorts = [dict(e) if isinstance(e, dict) else e for e in (catalog.get("shorts") or [])]
    hits = [i for i, e in enumerate(shorts) if isinstance(e, dict) and _cshort_label(e) == label]
    if not hits:
        names = ", ".join(_cshort_label(e) for e in shorts if isinstance(e, dict)) or "none"
        raise CasesError(f"no cshort {label!r} in the fabulac's shorts (it has: {names}): a verdict is gathered "
                         "into the cshort it judged")
    i = hits[-1]
    entry = shorts[i]
    old = entry.get("evidence") if isinstance(entry.get("evidence"), dict) else {}
    passes = bool(verdict.get("passes"))
    old_level = old.get("level") if isinstance(old.get("level"), int) else None
    level = 3 if passes else (min(old_level, 2) if old_level else 1)
    steps = verdict.get("steps") or {}
    ev = {"level": level, "steps": {"kept": int(steps.get("kept", 0)), "agree": int(steps.get("agree", 0))},
          "against": verdict.get("against", "original"),
          "inputs": f"the recorded cases, digest {str(verdict.get('recorded_digest', ''))[:12]}",
          "where": {"file": where, "digest": hashlib.sha256(verdict_bytes).hexdigest()}, "at": at, "by": by}
    src = _source_marks(verdict.get("source"))
    if src:
        ev["source"] = src
    entry["evidence"] = ev
    shorts[i] = entry
    out = {**dict(catalog), "shorts": shorts}
    diffs = differences_from_verdict(verdict)
    state, why = freshness(src or None, source_of(catalog))
    report = {"cshort": label, "level": level, "passes": passes, "differences": len(diffs),
              "needs-ruling": sum(1 for d in diffs if d["needs-ruling"]),
              "stale": None if state == "fresh" else f"{state}: {why}"}
    return out, report


# --- when the source moves ------------------------------------------------------------------------------------------

def stale_report(catalog: Mapping, nodes: list[dict], cases: Mapping | None = None) -> list[dict]:
    """Everything recorded or judged from a source that is not the one the fabulac is about now, and everything that
    does not say: each outside case item with a recording, each case of the cases file with an expectation, each
    cshort's evidence. Rows `{where, id, state, why}`, state `stale` or `unnamed`; fresh ones are not listed."""
    now = source_of(catalog)
    out = []
    for it in _items(nodes, "P:case/"):
        if isinstance(it.get("recorded"), dict):
            state, why = freshness(it["recorded"], now)
            if state != "fresh":
                out.append({"where": "item", "id": it["id"], "state": state, "why": why})
    for c in (cases or {}).get("cases") or []:
        if isinstance(c, dict) and ("expect" in c or "recorded" in c):
            state, why = freshness(c.get("recorded"), now)
            if state != "fresh":
                out.append({"where": "cases", "id": c.get("id"), "state": state, "why": why})
    for e in catalog.get("shorts") or []:
        if isinstance(e, dict) and isinstance(e.get("evidence"), dict):
            state, why = freshness(e["evidence"].get("source"), now)
            if state != "fresh":
                out.append({"where": "shorts", "id": e.get("path"), "state": state, "why": why})
    return out


def thym_engine() -> Any:
    """What Thym's transconception moves (`enough/thym/moves/transconceive.py`) reach as `ctx.engines
    ["transconception"]` (`enough.thym_host.SIBLING_ENGINES`): the cases functions of this module. A move imports only
    Thym and the reader, so that a host without this module (Comprise's) refuses the moves by name, never on import."""
    from types import SimpleNamespace
    return SimpleNamespace(
        CasesError=CasesError, Recording=Recording, cases_name=cases_name, source_of=source_of, freshness=freshness,
        source_marks=_source_marks, case_key=_key, dump_cases=dump_cases, check_cases_doc=check_cases_doc,
        cases_document=cases_document, read_recording=read_recording, gather_recorded=gather_recorded,
        read_verdict=read_verdict, fold_verdict=fold_verdict, cshort_label=_cshort_label,
        differences_from_verdict=differences_from_verdict, stale_report=stale_report, carry_over=carry_over)


def carry_over(old: Mapping, new: dict, *, at: str | None = None, by: str = "decompile") -> dict:
    """After a fabulac is decompiled again from a source that moved, what the transconceiver ruled and what the
    ground found are carried into the new one while their item resolves, as 0.6 carries questions
    (`enough.dialectic.carry_over`, MacroCOSM 18.6.3): an item's `ruling` list goes to the item of the same id in
    `new` when that item has none (one it has is kept); a `C:reliance` the new fabulac lacks is carried whole while
    something it is `used-by` (or `of`) still resolves, its refs that no longer resolve taken out and named; a ruling
    whose item is gone, or a reliance nothing resolves for, is not carried and is named stale, with why. Recorded
    cases and evidence are not carried: they stand against their own source (`stale_report`). Changes `new` only;
    returns `{rulings, reliances, refs-dropped, stale: [{id, what, because}], at, by}`."""
    o_nodes = [n for n in (old.get("nodes") or []) if isinstance(n, dict)]
    n_nodes = new.setdefault("nodes", [])
    by_id = {str(n.get("id")): n for n in n_nodes if isinstance(n, dict)}
    rep: dict = {"rulings": [], "reliances": [], "refs-dropped": [], "stale": [], "at": at, "by": by}
    for o in o_nodes:
        oid = str(o.get("id"))
        if "ruling" not in o or (oid.startswith("C:reliance/") and oid not in by_id):
            continue                                    # a reliance the new fabulac lacks is carried whole below
        n = by_id.get(oid)
        if n is None:
            rep["stale"].append({"id": oid, "what": "ruling", "because": "the item is gone from the new fabulac"})
        elif "ruling" not in n:
            n["ruling"] = copy.deepcopy(o["ruling"])
            rep["rulings"].append(oid)
    for o in o_nodes:
        oid = str(o.get("id"))
        if not oid.startswith("C:reliance/") or oid in by_id:
            continue
        r = copy.deepcopy(o)
        lost = []
        for fld in ("used-by", "of", "shown-by"):
            refs = r.get(fld)
            if isinstance(refs, list):
                keep = [x for x in refs if isinstance(x, str) and x in by_id]
                lost += [f"{fld}: {x}" for x in refs if x not in keep]
                r[fld] = keep
        if not [x for fld in ("used-by", "of") for x in (r.get(fld) or [])]:
            rep["stale"].append({"id": oid, "what": "reliance",
                                 "because": "nothing it is used by, or a gift of, is in the new fabulac"})
            continue
        for fld in ("used-by", "of", "shown-by"):
            if fld in r and not r[fld]:
                del r[fld]
        n_nodes.append(r)
        by_id[oid] = r
        rep["reliances"].append(oid)
        rep["refs-dropped"] += [{"id": oid, "ref": x} for x in lost]
    return rep
