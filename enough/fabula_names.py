"""A fabula's names on disk and how they are found (MacroCOSM OES 18.4, its volume; pins P3).

The single source of truth for what a text's twin is called, which file beside a text is its twin, what a short's stem
is, and which flavour enough suggests for a text. Everything that pairs a text with its twin (Canon's listings and
catalogs, the sidebar tree, the project mirror, the derivation routes and tools, Thym's export and readings, the page
through the payloads) asks this module, so the three names are spelled in one place.

- A text's twin is `<the text's whole name>.<flavour>.cosm`: `close.md.fabulan.cosm`, `rose.txt.fabulap.cosm`.
- The first edition's name, `<the text's whole name>.cosm` (`close.md.cosm`), is read forever as the text's fabulan.
  When both `close.md.fabulan.cosm` and `close.md.cosm` declare a fabula, the flavour-named one is the twin and the
  old one is an ordinary file (`superseded`). A text may have one twin per flavour; the one a single slot shows is
  the one derived last (`primary`).
- A fabula is identified by its declaration, never by its file name: a twin is a file of one of those names, beside
  an existing file whose whole name is the rest, that declares `oes: fabula/1` or its old spelling `oes: emf/1` in its
  first lines (a sniff, no YAML). A fabula with no sibling text (`rain.fabulan.cosm`, an old `rain.cosm`) is a
  standalone fabula: an ordinary `.cosm` file in every listing.
- `tool.fabulac.cosm` beside a folder `tool/` is a fabulac (18.4.7); this module names it (`twin_name`, `parse`) but
  pairs only texts: a fabulac is listed as an ordinary `.cosm` file until the lane that builds code pairs folders.

Standalone: the standard library and `enough.macrocosm` (which imports nothing from enough). Never writes.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from . import macrocosm

OES = "fabula/1"
OLD_OES = "emf/1"
DECLARATIONS = (OES, OLD_OES)              # what a fabula's first lines may declare; only OES is written
FLAVOURS = ("fabulan", "fabulap", "fabulac", "fabulam")
TEXT_FLAVOURS = ("fabulan", "fabulap")     # what a text may be decompiled as; a fabulac is a folder's, a fabulam a
                                           # Lean file's (named by the person or the file, never a text's twin)
NOT_TWINS = ("fabulac", "fabulam")         # flavours that never pair with a text beside them
OLD_FLAVOUR = "fabulan"                    # an old-named twin (and every `emf/1` file) is a fabulan
COSM = ".cosm"
SHORT_STEM_SUFFIXES = tuple(f".{f}{COSM}" for f in FLAVOURS) + (COSM,)   # the order a short's stem is looked up in


class FlavourError(ValueError):
    """A flavour a text cannot take: not one of the three, or `fabulac` (a folder's)."""


def suffix(flavour: str) -> str:
    """`fabulan` -> `.fabulan.cosm`."""
    if flavour not in FLAVOURS:
        raise FlavourError(f"flavour must be one of {', '.join(FLAVOURS)}, not {flavour!r}")
    return f".{flavour}{COSM}"


def twin_name(name: str, flavour: str) -> str:
    """`close.md`, `fabulan` -> `close.md.fabulan.cosm`; a folder `tool`, `fabulac` -> `tool.fabulac.cosm`."""
    return f"{name}{suffix(flavour)}"


def twin_path(text: Path | str, flavour: str) -> Path:
    """The twin a text of `flavour` is written as, beside it."""
    text = Path(text)
    return text.parent / twin_name(text.name, flavour)


def old_twin_path(text: Path | str) -> Path:
    """`close.md` -> `close.md.cosm`: the first edition's name, read forever and never written."""
    text = Path(text)
    return text.parent / f"{text.name}{COSM}"


def parse(name: str) -> tuple[str, str | None] | None:
    """`(the input's whole name, flavour)` for a name a fabula may carry: `close.md.fabulan.cosm` -> `("close.md",
    "fabulan")`, `close.md.cosm` -> `("close.md", None)` (the old name: a fabulan when it declares a fabula). None
    for a name that is not `<something>.cosm`."""
    for fl in FLAVOURS:
        sfx = f".{fl}{COSM}"
        if name.endswith(sfx) and len(name) > len(sfx):
            return name[: -len(sfx)], fl
    if name.endswith(COSM) and len(name) > len(COSM):
        return name[: -len(COSM)], None
    return None


def check_text_flavour(flavour: str | None) -> str | None:
    """The flavour a text is decompiled as, checked: None stays None (the caller's default); `fabulan` or `fabulap`
    as given; `fabulac` refused in plain words; anything else refused."""
    if flavour is None:
        return None
    fl = str(flavour).strip().lower()
    if not fl:
        return None
    if fl == "fabulac":
        raise FlavourError("fabulac is the fabula of a folder of code; a text is decompiled as fabulan (prose) "
                           "or fabulap (verse)")
    if fl == "fabulam":
        raise FlavourError("fabulam is the fabula of a Lean proof; a text is decompiled as fabulan (prose) "
                           "or fabulap (verse)")
    if fl not in TEXT_FLAVOURS:
        raise FlavourError(f"flavour must be fabulan (prose) or fabulap (verse), not {flavour!r}")
    return fl


def declares_fabula(path: Path | str) -> bool:
    """True when the file's first lines declare `oes: fabula/1` or `oes: emf/1` (a sniff, no YAML)."""
    return macrocosm.sniff_declaration(path) in DECLARATIONS


def is_old_declaration(said: str | None) -> bool:
    return said == OLD_OES


def _is_file(p: Path) -> bool:
    try:
        return p.is_file()
    except OSError:
        return False


# ---------------------------------------------------------------------------
# One text's twins
# ---------------------------------------------------------------------------

def text_twins(text: Path | str) -> dict[str, Path]:
    """`{flavour: path}` for the twins of one text that exist and declare a fabula. `fabulan` is
    `<text>.fabulan.cosm`, else the old `<text>.cosm`; `fabulap` is `<text>.fabulap.cosm`. Empty when the text is
    not a file or has none."""
    text = Path(text)
    if not _is_file(text):
        return {}
    out: dict[str, Path] = {}
    for fl in TEXT_FLAVOURS:
        p = twin_path(text, fl)
        if _is_file(p) and declares_fabula(p):
            out[fl] = p
    if "fabulan" not in out:
        old = old_twin_path(text)
        if _is_file(old) and declares_fabula(old):
            out["fabulan"] = old
    return {fl: out[fl] for fl in TEXT_FLAVOURS if fl in out}


def is_old_name(twin: Path | str) -> bool:
    """A twin under the first edition's name (`close.md.cosm`)."""
    got = parse(Path(twin).name)
    return got is not None and got[1] is None


def flavour_of_twin(twin: Path | str) -> str:
    """The flavour a twin's name says; an old name is a fabulan."""
    got = parse(Path(twin).name)
    return (got[1] if got and got[1] else OLD_FLAVOUR)


_DERIVED_AT_RE = re.compile(r"""^\s*(?:derived:\s*\{.*?\bat:|at:)\s*["']?([0-9][0-9T:.\-+Z ]*[0-9Z])""")


def derived_at(twin: Path | str, *, max_lines: int = 30) -> str:
    """The twin's `derived.at` as written (a UTC timestamp compares as text), from its first lines; "" when unread."""
    in_derived = False
    try:
        with open(twin, encoding="utf-8-sig", errors="replace") as fh:
            for _ in range(max_lines):
                line = fh.readline()
                if not line or line.startswith("nodes:"):
                    break
                if line.startswith("derived:"):
                    m = _DERIVED_AT_RE.match(line)
                    if m:
                        return m.group(1).strip()
                    in_derived = True
                    continue
                if in_derived:
                    if line[:1] not in (" ", "\t"):
                        in_derived = False
                        continue
                    m = _DERIVED_AT_RE.match(line)
                    if m:
                        return m.group(1).strip()
    except OSError:
        return ""
    return ""


def _mtime(p: Path) -> int:
    try:
        return p.stat().st_mtime_ns
    except OSError:
        return 0


def primary(twins: dict[str, Path]) -> tuple[str, Path] | None:
    """The twin a single slot shows when a text has more than one: the one derived last (`derived.at`, then the
    file's modification time; a tie goes to the fabulan). None when there is none."""
    if not twins:
        return None
    if len(twins) == 1:
        fl, p = next(iter(twins.items()))
        return fl, p
    order = {fl: i for i, fl in enumerate(TEXT_FLAVOURS)}
    best = max(twins.items(), key=lambda kv: (derived_at(kv[1]), _mtime(kv[1]), -order.get(kv[0], 9)))
    return best[0], best[1]


def find_twin(text: Path | str, flavour: str | None = None) -> Path | None:
    """The text's twin: of `flavour` when given, else the one derived last. None when there is none."""
    twins = text_twins(text)
    if flavour is not None:
        return twins.get(flavour)
    got = primary(twins)
    return got[1] if got else None


def text_of_twin(twin: Path | str) -> Path | None:
    """The text a twin is the twin of, when `twin` is one: a file of a text-twin name beside an existing file of the
    rest of the name, declaring a fabula, and, for an old name, with no flavour-named fabulan beside it. None
    otherwise (a standalone fabula, a superseded old twin, a fabulac, any other file)."""
    twin = Path(twin)
    got = parse(twin.name)
    if got is None:
        return None
    base, fl = got
    if fl in NOT_TWINS:
        return None
    text = twin.parent / base
    if not (_is_file(twin) and _is_file(text)) or not declares_fabula(twin):
        return None
    if fl is None:
        new = twin_path(text, "fabulan")
        if _is_file(new) and declares_fabula(new):
            return None                        # superseded: the flavour-named one is the twin
    return text


def is_twin(path: Path | str) -> bool:
    """True iff `path` is a text's twin (`text_of_twin`): what listings hide behind the text."""
    return text_of_twin(path) is not None


def superseded_by(path: Path | str) -> Path | None:
    """For an old-named twin that a flavour-named fabulan beside the same text has superseded, that fabulan; None
    otherwise. Such a file is listed as an ordinary file, with a note."""
    path = Path(path)
    got = parse(path.name)
    if got is None or got[1] is not None:
        return None
    text = path.parent / got[0]
    new = twin_path(text, "fabulan")
    if (_is_file(path) and _is_file(text) and _is_file(new) and declares_fabula(new)
            and declares_fabula(path)):
        return new
    return None


# ---------------------------------------------------------------------------
# One folder's twins (listings)
# ---------------------------------------------------------------------------

@dataclass
class FolderTwins:
    """What one folder's entries hold, by name: `twins` `{text: {flavour: twin path}}`; `primary` `{text: twin
    path}` (the one a single slot shows); `hidden`, the twin names listings hide; `superseded` `{old twin name: (text
    name, the flavour-named twin's name)}`, old-named twins listed as ordinary files with a note."""
    twins: dict[str, dict[str, Path]] = field(default_factory=dict)
    primary: dict[str, Path] = field(default_factory=dict)
    hidden: set[str] = field(default_factory=set)
    superseded: dict[str, tuple[str, str]] = field(default_factory=dict)

    def flavour(self, text: str) -> str | None:
        p = self.primary.get(text)
        if p is None:
            return None
        for fl, q in self.twins.get(text, {}).items():
            if q == p:
                return fl
        return None


def folder_twins(entries: Iterable[Path]) -> FolderTwins:
    """The twins among one folder's entries (a list of paths, as `iterdir` gives them). Sniffs only files whose
    names are twin names beside an existing file of the rest of the name."""
    entries = list(entries)
    files: dict[str, Path] = {}
    for p in entries:
        if _is_file(p):
            files[p.name] = p
    found: dict[str, dict[str, Path]] = {}
    olds: dict[str, Path] = {}
    for n, p in files.items():
        got = parse(n)
        if got is None:
            continue
        base, fl = got
        if fl in NOT_TWINS or base not in files:
            continue
        if not declares_fabula(p):
            continue
        if fl is None:
            olds[base] = p
        else:
            found.setdefault(base, {})[fl] = p
    out = FolderTwins()
    for base, old in olds.items():
        mine = found.setdefault(base, {})
        if "fabulan" in mine:
            out.superseded[old.name] = (base, mine["fabulan"].name)
        else:
            mine["fabulan"] = old
    for base, mine in found.items():
        ordered = {fl: mine[fl] for fl in TEXT_FLAVOURS if fl in mine}
        out.twins[base] = ordered
        got = primary(ordered)
        if got:
            out.primary[base] = got[1]
        out.hidden.update(p.name for p in ordered.values())
    return out


# ---------------------------------------------------------------------------
# Shorts: the stem
# ---------------------------------------------------------------------------

def short_stem(fabula_name: str) -> str:
    """The stem a short of this fabula takes (MacroCOSM OES 18.4.4): the input's whole name less its fabula suffix,
    then less one extension. `close.md.fabulan.cosm` and `close.md.cosm` -> `close`; a standalone
    `rain.fabulan.cosm` or `rain.cosm` -> `rain`; `tool.fabulac.cosm` -> `tool`."""
    got = parse(fabula_name)
    base = got[0] if got else fabula_name
    stem = os.path.splitext(base)[0] if not base.startswith(".") else base
    return stem or base


def standalone_names(stem: str) -> tuple[str, ...]:
    """The names a standalone fabula a short of stem `stem` may have been compiled from, in the order they are
    tried: `rain.fabulan.cosm`, `rain.fabulap.cosm`, `rain.fabulac.cosm`, `rain.cosm`."""
    return tuple(f"{stem}{s}" for s in SHORT_STEM_SUFFIXES)


# ---------------------------------------------------------------------------
# A fabulam's names: the file, its parts, its pshorts, its items' ids (MacroCOSM OES 18.4.10; design 6, 1.3)
# ---------------------------------------------------------------------------

FABULAM_SUFFIX = ".fabulam.cosm"
FABULAM_PARTS_SUFFIX = ".fabulam.parts"
PSHORT_DENSITIES = ("expert", "student", "everyone")
_STAMP_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{4}$")
_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_SLUG_CHAR = re.compile(r"[A-Za-z0-9._@-]")


def fabulam_stem(source_name: str) -> str:
    """The name a fabulam takes by rule from its Lean file's or folder's name, when the person gives none: the
    extension dropped, words split where a small letter or a digit meets a capital, lowercased, and anything outside
    a-z and 0-9 a hyphen. `PrimesCongruentOne.lean` -> `primes-congruent-one`; `LSeries` -> `lseries`."""
    base = source_name.rstrip("/").rsplit("/", 1)[-1]
    if base.endswith(".lean"):
        base = base[: -len(".lean")]
    s = re.sub(r"[^a-z0-9]+", "-", _CAMEL_RE.sub("-", base).lower()).strip("-")
    return s or "fabulam"


def fabulam_name(name: str) -> str:
    """`primes-congruent-one` -> `primes-congruent-one.fabulam.cosm`."""
    return f"{name}{FABULAM_SUFFIX}"


def fabulam_parts_folder(name: str) -> str:
    """The folder a head's parts live in, beside the head: `lseries` -> `lseries.fabulam.parts`."""
    return f"{name}{FABULAM_PARTS_SUFFIX}"


def fabulam_part_name(lean_file: str) -> str:
    """A part's file inside the parts folder: `Nonvanishing.lean` -> `Nonvanishing.fabulam.cosm`."""
    base = lean_file.rsplit("/", 1)[-1]
    return (base[: -len(".lean")] if base.endswith(".lean") else base) + FABULAM_SUFFIX


def fabulam_part_id(head_name: str, module: str) -> str:
    """A part's catalog id: `fabula/<head name>--<module respelled>`, the module's dots as hyphens and every other
    character as `declaration_slug` spells it: `fabula/lseries--Mathlib-NumberTheory-LSeries-Nonvanishing`."""
    return f"fabula/{head_name}--{declaration_slug(module.replace('.', '-'))}"


def pshort_name(name: str, density: str, at: str) -> str:
    """`primes-congruent-one`, `everyone`, `2026-11-22-1405` -> `primes-congruent-one.pshort-everyone-2026-11-22-1405.md`
    (a pshort, beside its fabulam)."""
    if density not in PSHORT_DENSITIES:
        raise ValueError(f"a pshort's density is {', '.join(PSHORT_DENSITIES)}, not {density!r}")
    if not _STAMP_RE.match(at):
        raise ValueError(f"a pshort's time is YYYY-MM-DD-HHMM, not {at!r}")
    return f"{name}.pshort-{density}-{at}.md"


def declaration_slug(name: str) -> str:
    """A Lean declaration's full name respelled for an item id's slug (design 1.3, "Ids"): `'` becomes `-prime`,
    any other character the slug grammar refuses becomes `-x` and its code point in hex; a name that would then
    begin with no letter or digit takes `x` first, and one that would end in a dot spells the dot. `quadratic_reciprocity'`
    -> `quadratic_reciprocity-prime`; `χ₈` -> `x-x3c7-x2088`."""
    out = []
    for ch in name:
        if ch == "'":
            out.append("-prime")
        elif _SLUG_CHAR.match(ch):
            out.append(ch)
        else:
            out.append(f"-x{ord(ch):x}")
    s = "".join(out)
    if s.endswith("."):
        s = s[:-1] + "-x2e"
    if not s or not s[0].isalnum() or not s[0].isascii():
        s = "x" + s
    return s


def declaration_ids(decls: Iterable[tuple[str, str, int]]) -> list[str]:
    """The item ids of a file's declarations, in order: each `(kind, full name, line)` (kind `statement`, `lemma` or
    `definition`) -> `C:<kind>/<declaration_slug(name)>`. An unnamed one is `C:definition/instance-L<line>` or
    `C:lemma/example-L<line>` (its kind's word: `instance` for a definition, `example` for a lemma). A slug two names
    share: the later takes `-2`, then `-3`."""
    seen: set[str] = set()
    out: list[str] = []
    for kind, name, line in decls:
        if name:
            slug = declaration_slug(name)
        else:
            slug = f"{'example' if kind == 'lemma' else 'instance'}-L{line}"
        iid, n = f"C:{kind}/{slug}", 2
        while iid in seen:
            iid, n = f"C:{kind}/{slug}-{n}", n + 1
        seen.add(iid)
        out.append(iid)
    return out


# ---------------------------------------------------------------------------
# The flavour enough suggests for a text
# ---------------------------------------------------------------------------

#: A line of verse is at most this many characters (stripped).
VERSE_LINE_MAX = 60
#: At least this share of the non-blank lines must be that short.
VERSE_SHORT_SHARE = 0.75
#: Verse has at least this many non-blank lines, two stanzas, and on average two lines a stanza.
VERSE_MIN_LINES = 4

_HEADING = re.compile(r"^\s{0,3}(#{1,6}\s|#{1,6}$)")
_SETEXT = re.compile(r"^\s{0,3}(=+|-{2,})\s*$")
_FENCE = re.compile(r"^\s{0,3}(```|~~~)")
_TABLE = re.compile(r"^\s*\|.*\|\s*$")


def suggest_flavour(text: str) -> str:
    """`fabulap` when the text looks like verse, else `fabulan` (MacroCOSM OES 18.4: short lines, stanza breaks, no
    headings). Verse here: at least `VERSE_MIN_LINES` non-blank lines; at least three in four of them at most
    `VERSE_LINE_MAX` characters; at least two stanzas (runs of lines between blank lines) of two lines or more on
    average; and no markdown heading, setext underline, code fence or table row. Pure; reads only `text`."""
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    stanzas: list[int] = []
    run = 0
    body: list[str] = []
    for line in lines:
        if line.strip():
            if _HEADING.match(line) or _FENCE.match(line) or _TABLE.match(line):
                return "fabulan"
            if run and _SETEXT.match(line):
                return "fabulan"
            body.append(line.strip())
            run += 1
        elif run:
            stanzas.append(run)
            run = 0
    if run:
        stanzas.append(run)
    if len(body) < VERSE_MIN_LINES or len(stanzas) < 2:
        return "fabulan"
    if len(body) / len(stanzas) < 2:
        return "fabulan"
    short = sum(1 for ln in body if len(ln) <= VERSE_LINE_MAX)
    return "fabulap" if short / len(body) >= VERSE_SHORT_SHARE else "fabulan"


__all__ = [
    "COSM", "DECLARATIONS", "FABULAM_PARTS_SUFFIX", "FABULAM_SUFFIX", "FLAVOURS", "FlavourError", "FolderTwins",
    "NOT_TWINS", "OES", "OLD_FLAVOUR", "OLD_OES", "PSHORT_DENSITIES",
    "SHORT_STEM_SUFFIXES", "TEXT_FLAVOURS", "VERSE_LINE_MAX", "VERSE_MIN_LINES", "VERSE_SHORT_SHARE",
    "check_text_flavour", "declaration_ids", "declaration_slug", "declares_fabula", "fabulam_name",
    "fabulam_part_id", "fabulam_part_name", "fabulam_parts_folder", "fabulam_stem", "pshort_name", "derived_at", "find_twin", "flavour_of_twin", "folder_twins",
    "is_old_declaration", "is_old_name", "is_twin", "old_twin_path", "parse", "primary", "short_stem",
    "standalone_names", "suffix", "suggest_flavour", "superseded_by", "text_of_twin", "text_twins", "twin_name",
    "twin_path",
]
