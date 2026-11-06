"""Ascribe: a person's holograph (`oes: ascribe/1`, defaults/cosm/manifests/ascribe.manifest.cosm; the text is
Ascribe, https://ascribe.cosmoes.org/, edition 0.6.0).

A holograph is a self described well enough that no name is needed: a folder whose catalog, `holograph.cosm`, is
the self, with ten module folders of nodes beside it (A affinity, B belief, C concern, E experience, I interest,
O opinion, Q quale, S skill, U understanding, Y yearning), `F/` for the forms, polyforms and relations the nodes
anchor to, and `D/` for the dialectic's questions and sessions (the holder's own words, which never leave).

**Checks** (section 10). The reader, `enough/macrocosm.py`, loads and checks it like any volume (and
`enough/fabula.py` adds the dialectic's checks when it holds module D); `lint_holograph` runs Ascribe's own checks
beside them, in one report:

- `form-anchored` (error): every node of the ten kinds names a form or a polyform that exists (never an item of D).
- `relation-declared` (error): every typed link's rel is a starter word or a relation the holograph declares.
- `when-shape` (error): a `when` is a date, a year or an era word.
- `strength-range` (error): a `strength` is a whole number from 1 to 5.
- `release-shape` (error): every `releases:` entry has what section 13 requires, in its shape; every `morphs:`
  entry is a bare file name ending `.morph.cosm`.
- `no-pii` (warning inside the holograph, never an error there; an error at a projection): what reads like personal
  data, anywhere in the volume, comments included, and capitalised pairs in prose fields that read as names.
- `private-marker` (note): what a `.ascribe-private` marker would keep out of everything that leaves.

It also holds two generic checks to what the reader cannot read from the manifest: `id-module` to the module
folders (a node is written in its own module's folder, or in the catalog's `nodes:`), and `catalog-key` to the hid
and the handle.

**The dialectic, applied** (section 8): `raise_bank`, `queue`, `record_answers`, `settle_holograph`, `answer`,
`follow_ups` ask the holder the bank's questions through `enough/dialectic.py`, keep their words in `D/`, and settle
an answer into a node anchored to a form; nothing that reads as personal data is ever written. **Reading the holder's
own texts** (section 9): `candidates` and `land_candidates` (the engine side of Thym's move `propose`). **The
private filter** (section 11): `private_filter`, a pure function of the folder. **Releases** (section 13):
`releases`, `append_release`, `released`. **Projections** (section 14): `project_isograph` (`ascribe-isograph/0`),
`isograph_problems` (the reader's refusal), `cryptograph`, `make_tokens` (`ascribe-tokens/0`), `isomorph`.
`thym_engine()` is what Thym's moves reach as `ctx.engines["ascribe"]`.

Only the dialectic's writers, `land_candidates` and the release writers write, and only into the holograph folder
they are given (atomically, every byte outside the change kept). `lint_holograph` reads only the folder.

    python -m enough.ascribe lint <folder> [--json]

The standard library, PyYAML (through the reader), `enough.macrocosm`, `enough.fabula`, `enough.dialectic`, and
(for a cryptograph only) `enough.thym.vault`.
"""

from __future__ import annotations

import argparse
import copy
import datetime as _dt
import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

from . import dialectic as dl
from . import fabula as fb
from . import macrocosm as mc

OES = "ascribe/1"
CATALOG = "holograph.cosm"
FORM_MODULE = "F"
ANCHOR_KINDS = ("form", "polyform")          # what a node's `form` may name
RELATION_KIND = "relation"
# The fallbacks for what the manifest gives (`links.starter`, `filter.marker`); the manifest wins when it says.
STARTER_RELS = ("is-a", "part-of", "about", "because", "before", "after", "with", "against", "like", "from", "toward",
                "see")
PRIVATE_MARKER = ".ascribe-private"

# Ascribe's own checks, run by `lint_holograph` after the generic ones (a generic reader does not run them).
ASCRIBE_CHECKS = ("form-anchored", "relation-declared", "when-shape", "strength-range", "release-shape", "no-pii",
                  "private-marker")
ASCRIBE_SEVERITY = {"form-anchored": "error", "relation-declared": "error", "when-shape": "error",
                    "strength-range": "error", "release-shape": "error", "no-pii": "warning",
                    "private-marker": "note"}
ADVICE = "people appear by role or by a pseudonym you declare"

HID_RE = re.compile(r"^[a-z2-7]{26}$")                     # Connect's hid: 26 characters of lowercase base32
HANDLE_RE = re.compile(r"^[a-z]+(?:-[a-z]+)*$")            # lowercase words joined by hyphens
YEAR_RE = re.compile(r"^[0-9]{4}$")
ERA_RE = re.compile(r"^(?:[0-9]{3}0s|[a-z]+(?:-[a-z]+)*)$")  # 2010s, childhood, secondary-school
DECADE_RE = re.compile(r"^[0-9]{3}0s$")

# The ten containers, in the order of the modules (A B C E I O Q S U Y), and their one kind each (section 5.1).
KINDS = {"A": "affinity", "B": "belief", "C": "concern", "E": "experience", "I": "interest", "O": "opinion",
         "Q": "quale", "S": "skill", "U": "understanding", "Y": "yearning"}
CONTAINERS = tuple(KINDS)
DIALECTIC_MODULE = mc.DIALECTIC_MODULE             # D: the holder's questions and sessions, never released
MODULE_FILES = {"A": "affinities", "B": "beliefs", "C": "concerns", "E": "experiences", "I": "interests",
                "O": "opinions", "Q": "qualia", "S": "skills", "U": "understandings", "Y": "yearnings", "F": "forms",
                "D": "questions"}
BANK = "ascribe"                                   # the bank the older `dialectic.questions` shape is read as
HOLDER = "holder"

# Releases (section 13).
RELEASE_AS = ("isograph", "cryptograph", "tokens", "isomorph")
RELEASE_REQUIRED = ("epoch", "as", "program", "trace", "at", "sha256", "items")
RELEASE_FIELDS = RELEASE_REQUIRED + ("for",)
EPOCH_RE = re.compile(r"^[0-9]{4}-(?:Q[1-4]|0[1-9]|1[0-2]|W(?:0[1-9]|[1-4][0-9]|5[0-3]))$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
MORPH_FILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.morph\.cosm$")
MORPH_ID_RE = re.compile(r"^M:morph/[A-Za-z0-9][A-Za-z0-9._@-]*$")

# Projections (section 14).
ISOGRAPH = "ascribe-isograph/0"
# Ruling (2026-11-06): an isograph names the run that made it by its id, not its trace's digest (the trace is not
# finished when the isograph is written); the release record, written after the run lands, carries the digest.
ISOGRAPH_KEYS = ("isograph", "hid", "handle", "epoch", "sample", "program", "run", "self")
#: A run's id as a Thym runtime writes it (`2026-11-05-2046-2166`): its minute, then four hex digits.
RUN_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{4}-[0-9a-f]{4}$")
ISOGRAPH_SELF_KEYS = ("kind", "form", "valence", "strength", "when", "marking")
TOKENS = "ascribe-tokens/0"
STATED = "stated"
BANDS = {1: "slight", 2: "slight", 3: "moderate", 4: "strong", 5: "strong"}
PER_KIND = 20
MAX_ISOGRAPH_BYTES = 64 * 1024
MAX_POLYFORM_WORDS = 8
KNOWN_AT = 0.5                                     # a node below this confidence never leaves (section 14, rule 3)
CANDIDATE_OPTIONS = ["yes", "no", "partly"]
FILTER_USES = ("ingest", "package", "transfer", "projection")

# The four follow-up questions about a node's optional fields (section 8.4), as the manifest's `follow-ups:` gives
# them; these are the fallback.
FOLLOW_UPS = {
    "form": {"asks": "What is this about, in a word or two?", "kind": "text"},
    "when": {"asks": "When was this, roughly: a date, a year, or a time of life?", "kind": "date"},
    "valence": {"asks": "Does this draw you, put you off, or both?", "kind": "choice",
                "options": ["for", "against", "mixed"]},
    "strength": {"asks": "How strongly, from 1 to 5?", "kind": "number", "range": [1, 5]},
}
#: The words an answer that reads like personal data is refused in (Ascribe 3, design rule 6: people appear by what they
#: are to the holder, or by a declared pseudonym). Said in the page's own voice ("describe people by what they are to
#: you"), never with the app's retired word for a readvisor.
REFUSED_PII = ("this answer reads like personal data ({what}), which a holograph never holds: describe people by what "
               "they are to you (\"my oldest friend\", \"a retired harbour pilot who taught me\"), or by a pseudonym "
               "you declare; nothing was written and the question stays open")


class AscribeError(Exception):
    """A refusal in plain words: nothing was written, and nothing left."""


# ---------------------------------------------------------------------------
# What reads like personal data
# ---------------------------------------------------------------------------

_MONTH = (r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sep(?:t(?:ember)?)?"
          r"|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)")
# A day of a month, with or without its year: 1990-03-03, 3/3/1990, 3 March 1990, 3rd of March, March 3, 1990.
_DAY = (r"(?:[0-9]{4}-[0-9]{2}-[0-9]{2}"
        r"|[0-9]{1,2}[/.][0-9]{1,2}[/.][0-9]{2,4}"
        rf"|[0-9]{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?{_MONTH}\b\.?(?:,?\s+[0-9]{{4}})?"
        rf"|{_MONTH}\b\.?\s+[0-9]{{1,2}}(?:st|nd|rd|th)?\b(?:,?\s+[0-9]{{4}})?)")
_STREET = (r"(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Drive|Dr|Boulevard|Blvd|Court|Ct|Close|Crescent|Place|Pl"
           r"|Square|Sq|Terrace|Way|Row|Mews|Gardens|Grove|Parkway|Pkwy|Highway|Hwy)")

# The patterns, compiled once, in the order they claim a stretch of text: a stretch one of them matched is not
# matched again by a later one, so one email address is one warning (and a card's groups of four are an id, not a
# phone number). Each maps to (regex, what it reads as).
PII_PATTERNS: dict[str, tuple[re.Pattern, str]] = {
    # An email address: a local part, an @, and a dotted domain.
    "email": (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"),
              "an email address"),
    # A date that reads as a birth: born, birth, birthday, date of birth or dob within a few words of a day of a
    # month (a year alone is a when, not a birth date).
    "birth-date": (re.compile(rf"(?i:\b(?:born|birth(?:day|date)?|date\s+of\s+birth|dob|d\.o\.b\.?)(?!\w)\W+"
                              rf"(?:\w+\W+){{0,4}}?{_DAY}"
                              rf"|{_DAY}\W+(?:\w+\W+){{0,5}}?(?:birthday|birth|born)\b)"),
                   "a birth date"),
    # An id-like run of digits: the three-two-four shape of a social-security number, a card's groups of four, or
    # eight or more digits standing alone (a passport, an account, a national id).
    "id-number": (re.compile(r"(?<![\w-])(?:[0-9]{3}-[0-9]{2}-[0-9]{4}|[0-9]{4}(?:[ -][0-9]{4}){2,3}|[0-9]{8,})"
                             r"(?![\w-])"),
                  "an id-like run of digits"),
    # A phone number: international with a plus, a bracketed area code, three-three-four groups, or a national
    # number after a trunk zero (020 7946 0958, 07700 900123); seven to fifteen digits in all.
    "phone": (re.compile(r"(?<![\w+])(?:\+[0-9]{1,3}(?:[\s.-]?\(?[0-9]{1,4}\)?){2,5}"
                         r"|\([0-9]{2,5}\)\s?[0-9]{3,4}[\s.-]?[0-9]{3,4}"
                         r"|[0-9]{3}[\s.-][0-9]{3}[\s.-][0-9]{4}"
                         r"|0[0-9]{2,4}[\s-][0-9]{3,4}[\s-]?[0-9]{3,4})(?![\w])"),
              "a phone number"),
    # A street address: a number and a capitalised street name (17 Quillfeather Lane), the French, Spanish and
    # Italian order (12 rue des Lilas), the German (Lindenstraße 5), or a post-office box.
    "street-address": (re.compile(
        rf"\b[0-9]{{1,5}}[A-Za-z]?,?\s+(?:[A-Z][\w'’-]*\s+){{1,3}}{_STREET}\b"
        r"|\b[0-9]{1,5}(?:\s?(?:bis|ter))?,?\s+(?i:rue|avenue|boulevard|chemin|allée|impasse|via|viale|calle|avenida"
        r"|rua)(?:\s+(?i:de|des|du|del|della|di|da|la|le|les))*\s+[\w'’-]+(?:\s+[A-ZÀ-Ý][\w'’-]*)*"
        r"|\b[A-ZÄÖÜ][a-zäöüß]+(?:straße|strasse|weg|gasse|platz|allee)\s+[0-9]{1,4}[a-z]?\b"
        r"|(?i:\bP\.?\s?O\.?\s?Box\s+[0-9]+)"),
        "a street address"),
}

# Field names that would hold personal data, wherever they appear: the schema has no place for them. A catalog's
# `name` is one too (a holograph names no one); an item's `name` is the item's.
IDENTIFYING_FIELDS = {
    "email": "an email address", "e-mail": "an email address", "phone": "a phone number",
    "telephone": "a phone number", "mobile": "a phone number", "address": "a postal address",
    "street": "a postal address", "postcode": "a postal address", "zip": "a postal address",
    "birthday": "a birth date", "birthdate": "a birth date", "birth-date": "a birth date",
    "date-of-birth": "a birth date", "dob": "a birth date", "born": "a birth date", "ssn": "a government id",
    "passport": "a government id", "national-id": "a government id", "tax-id": "a government id",
    "employer": "an employer's legal name", "full-name": "a personal name", "first-name": "a personal name",
    "last-name": "a personal name", "surname": "a personal name", "given-name": "a personal name",
    "family-name": "a personal name",
}
PII_WHAT = {**{k: what for k, (_, what) in PII_PATTERNS.items()}, "personal-name": "a personal name",
            "identifying-field": "a field for personal data"}

# Words that make a capitalised pair something other than a person: the words a sentence opens with, months and
# days, and the words of places, institutions, languages and occasions. Compared lowercased.
_NOT_A_NAME = frozenset("""
a an the this that these those my our your his her their its i we you he she they it me us them and or but so yet nor
for if when while after before since until because though although as at by in on of to from with without into onto
over under about above below between through during every each all some any no not one two three first last next
once then now here there what which who whom whose where why how also only just still even more most less least very
much many few both either neither other another such same own mostly always never often sometimes usually later early
again too well yes
january february march april may june july august september october november december jan feb mar apr jun jul aug
sep sept oct nov dec monday tuesday wednesday thursday friday saturday sunday
north south east west northern southern eastern western new old great little upper lower saint st mount mt lake river
sea ocean bay island isle islands cape coast valley hill hills mountains forest park city town county state states
united kingdom republic empire university college school academy institute museum gallery library hospital church
cathedral abbey temple club society company corporation inc ltd group street road lane avenue drive way square bridge
station airport harbour harbor district national royal central international world war cup league festival day eve
christmas easter house hall
english french spanish german italian latin greek dutch portuguese russian chinese japanese korean arabic hindi
irish scottish welsh british american european african asian
""".split())
_WORD_RE = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")
_BIRTH_WORD = re.compile(r"(?i)\b(?:born|birth(?:s|day|date)?)\b")


def pii_findings(text: str) -> list[tuple[str, str]]:
    """(pattern, matched text) for every stretch of `text` that reads as personal data, in the order of the text;
    a stretch one pattern claimed is not claimed again. Personal names are `name_bigrams`'."""
    return [(kind, text[a:b]) for kind, a, b in _pii_spans(text)]


def _pii_spans(text: str) -> list[tuple[str, int, int]]:
    taken: list[tuple[str, int, int]] = []
    for kind, (rx, _) in PII_PATTERNS.items():
        for mt in rx.finditer(text):
            a, b = mt.span()
            if any(a < y and x < b for _, x, y in taken):
                continue
            if kind == "phone" and not 7 <= sum(c.isdigit() for c in mt.group(0)) <= 15:
                continue
            taken.append((kind, a, b))
    return sorted(taken, key=lambda t: t[1])


def name_bigrams(text: str, pseudonyms: Iterable[str] = (), *, masked: Iterable[tuple[int, int]] = ()) -> list[str]:
    """The capitalised pairs in `text` that read as a personal name: two adjacent words, each capitalised and
    neither all capitals, neither a word that makes the pair a place, a month or a sentence's opening, and neither
    a declared pseudonym. `masked` are stretches another pattern already claimed (an address's street name)."""
    chars = list(text)
    for a, b in masked:
        chars[a:b] = "\0" * (b - a)
    for p in pseudonyms:
        if isinstance(p, str) and p.strip():
            for mt in re.finditer(r"(?<!\w)" + re.escape(p.strip()) + r"(?!\w)", text):
                chars[mt.start():mt.end()] = "\0" * (mt.end() - mt.start())
    clean = "".join(chars)
    words = list(_WORD_RE.finditer(clean))
    out: list[str] = []
    for w1, w2 in zip(words, words[1:]):
        gap = clean[w1.end():w2.start()]
        if not gap or not gap.isspace() or "\n" in gap:
            continue
        a, b = w1.group(0), w2.group(0)
        if all(_capitalised(x) and x.casefold() not in _NOT_A_NAME for x in (a, b)):
            out.append(f"{a} {b}")
    return out


def _capitalised(w: str) -> bool:
    return w[0].isupper() and len(w) > 1 and any(c.islower() for c in w[1:])


def _strings(o: Any, fpath: str = "") -> Iterator[tuple[str, str]]:
    """(field path, text) for every string value in an item, at any depth."""
    if isinstance(o, str):
        yield fpath, o
    elif isinstance(o, dict):
        for k, v in o.items():
            yield from _strings(v, f"{fpath}.{k}" if fpath else str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _strings(v, f"{fpath}[{i}]")


def _keys(o: Any, fpath: str = "") -> Iterator[tuple[str, str]]:
    """(field path, key) for every key of every mapping in an item, at any depth."""
    if isinstance(o, dict):
        for k, v in o.items():
            here = f"{fpath}.{k}" if fpath else str(k)
            yield here, str(k)
            yield from _keys(v, here)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _keys(v, f"{fpath}[{i}]")


def _comments(text: str) -> Iterator[tuple[int, str]]:
    """(line number, comment text) for every YAML comment in a file: a `#` that starts a line or follows a space,
    outside a quoted scalar. A block scalar's `#` reads as a comment too; for a warning that errs the safe way."""
    for n, line in enumerate(text.splitlines(), 1):
        quote = None
        for i, ch in enumerate(line):
            if quote:
                if ch == quote:
                    quote = None
            elif ch in "'\"":
                before = line[:i].rstrip()
                if not before or before[-1] in ":[{,-?":
                    quote = ch
            elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
                yield n, line[i + 1:]
                break


def _quote(s: str, limit: int = 40) -> str:
    s = " ".join(s.split())
    return repr(s if len(s) <= limit else s[:limit - 1] + "…")


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------

def _is_date(v: Any) -> bool:
    if isinstance(v, _dt.datetime):
        return False
    if isinstance(v, _dt.date):
        return True
    if isinstance(v, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", v):
        try:
            _dt.date.fromisoformat(v)
            return True
        except ValueError:
            return False
    return False


def when_ok(v: Any) -> bool:
    """A `when` is a date (2014-06-03), a year (2014) or an era word (childhood, 2010s, university)."""
    if _is_date(v):
        return True
    if isinstance(v, int) and not isinstance(v, bool):
        return 1000 <= v <= 9999
    return isinstance(v, str) and bool(YEAR_RE.match(v) or ERA_RE.match(v))


def strength_ok(v: Any) -> bool:
    """A `strength` is a whole number from 1 to 5."""
    return isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 5


def private_drops(root: Path, marker: str = PRIVATE_MARKER) -> list[tuple[str, list[str]]]:
    """(the marker's path, what everything that leaves would leave out beside it) for every marker below `root`,
    paths relative to `root`, folders ending in `/`. Reads the folder; drops nothing (`private_filter` applies it)."""
    out = []
    for mk in sorted(root.rglob(marker), key=lambda p: p.relative_to(root).as_posix()):
        folder = mk.parent
        dropped = []
        for p in sorted(folder.iterdir(), key=lambda p: p.name):
            if p.name == marker:
                continue
            rel = p.relative_to(root).as_posix()
            dropped.append(rel + "/" if p.is_dir() else rel)
        out.append((mk.relative_to(root).as_posix(), dropped))
    return out


class _Own:
    """Ascribe's own checks over one loaded holograph, adding to the generic report. `files=False` for a volume built
    in memory (the dialectic's candidate ledgers): no file is read, so comments and markers are not looked at.
    `pii_error=True` reports `no-pii` as an error: at a projection, and when a write must add no finding."""

    def __init__(self, vol: mc.Volume, rep: mc.Report, *, files: bool = True, pii_error: bool = False):
        self.v, self.rep, self.m = vol, rep, vol.manifest
        self.files = files
        c = self.m._block("checks")
        override = c.get("severity") if isinstance(c.get("severity"), dict) else {}
        self.sev = dict(ASCRIBE_SEVERITY, **{str(k): str(v) for k, v in override.items() if str(k) in ASCRIBE_CHECKS})
        self.sev["no-pii"] = "note" if self.sev.get("no-pii") == "note" else "warning"     # never an error in it
        if pii_error:
            self.sev["no-pii"] = "error"                                                     # at a projection
        self.generic_sev = dict(mc.SEVERITY, **{str(k): str(v) for k, v in override.items()})
        self.selected = set(self.m.checks())
        mods = self.m.modules()
        # The ten containers: not F, and not the core's dialectic module D, which every format inherits (its
        # questions and sessions anchor to nothing).
        self.node_modules = [L for L in mods if L != FORM_MODULE and L not in self.m.inherited
                             and L != mc.DIALECTIC_MODULE]
        links = self.m._block("links")
        self.starter = tuple(mc._strs(links.get("starter"))) or STARTER_RELS
        filt = self.m._block("filter")
        self.marker = str(filt.get("marker") or self.m.volume.get("private-marker") or PRIVATE_MARKER)
        self.items = list(vol.items.values())
        self.relations = {it.id.split("/", 1)[1]: it for it in self.items
                          if it.module == FORM_MODULE and it.kind == RELATION_KIND and "/" in it.id}
        pseu = vol.catalog.get("pseudonyms")
        self.pseudonyms = [p for p in pseu if isinstance(p, str)] if isinstance(pseu, list) else []

    def add(self, check: str, item: mc.Item | None, msg: str, fld: str | None = None, *, file: str | None = None,
            severity: str | None = None) -> None:
        sev = severity or (self.sev.get(check) if check in ASCRIBE_CHECKS else self.generic_sev.get(check, "error"))
        self.rep.add(mc.Problem(check, sev, item.key if item else "",
                                file if file is not None else (item.file if item else self.v.catalog_file), msg, fld))

    def run(self) -> None:
        for it in self.items:
            if it.module in self.node_modules and it.kind in self.m.kinds(it.module):
                self.form_anchored(it)
            self.relation_declared(it)
            self.when_shape(it)
            self.strength_range(it)
            self.module_folder(it)
        for slug, it in self.relations.items():
            if slug in self.starter:
                self.add("relation-declared", it, f"F:relation/{slug} repeats the starter relation {slug}: use the "
                                                  "starter word, or give the relation a name of its own", "id")
        self.catalog()
        self.release_shape()
        self.no_pii()
        if self.files:
            self.private_marker()

    # release-shape
    def release_shape(self) -> None:
        cat, f = self.v.catalog, self.v.catalog_file
        if "releases" in cat:
            rel = cat["releases"]
            if not isinstance(rel, list):
                self.add("release-shape", None, "releases is a list of the releases the holder has made, oldest "
                                                "first", "releases", file=f)
            else:
                for i, entry in enumerate(rel):
                    for fld, msg in release_problems(entry):
                        path = f"releases[{i}]" + (f".{fld}" if fld else "")
                        self.add("release-shape", None, f"{path}: {msg}", path, file=f)
        if "morphs" in cat:
            mo = cat["morphs"]
            if not isinstance(mo, list):
                self.add("release-shape", None, "morphs is a list of the file names of the holder's morph volumes",
                         "morphs", file=f)
            else:
                for i, name in enumerate(mo):
                    if not (isinstance(name, str) and MORPH_FILE_RE.match(name)):
                        self.add("release-shape", None, f"morphs[{i}] {_quote(str(name))} is not a bare file name "
                                                        "ending .morph.cosm, kept beside the holograph's folder",
                                 f"morphs[{i}]", file=f)

    # form-anchored
    def form_anchored(self, it: mc.Item) -> None:
        f = it.data.get("form")
        if "form" not in it.data or f is None:
            self.add("form-anchored", it, f"no form: every node anchors to a form or a polyform (form: "
                                          f"{FORM_MODULE}:form/<slug>)", "form")
            return
        if mc.is_pending(f):
            self.add("form-anchored", it, "form is an open question: unverifiable until it is answered", "form",
                     severity="note")
            return
        if not isinstance(f, str):
            self.add("form-anchored", it, f"form names one form or one polyform by its id, not {_quote(str(f))}; a "
                                          "node about several forms anchors to a polyform of them", "form")
            return
        target = mc.resolve_ref(self.v, it, f)
        if target is None:
            self.add("form-anchored", it, f"form {f} does not exist: declare it in {FORM_MODULE}/, or anchor to a "
                                          "form that does", "form")
        elif target.module != FORM_MODULE or target.kind not in ANCHOR_KINDS:
            self.add("form-anchored", it, f"form {f} is a {target.kind}, not a form or a polyform", "form")

    # relation-declared
    def relation_declared(self, it: mc.Item) -> None:
        links = it.data.get("links")
        if not isinstance(links, list):
            return
        for i, ln in enumerate(links):
            if not isinstance(ln, dict) or "rel" not in ln:
                continue                            # a bare id: a link with no relation named
            rel, fld = ln["rel"], f"links[{i}].rel"
            if mc.is_pending(rel):
                continue
            if not isinstance(rel, str) or not rel.strip():
                self.add("relation-declared", it, f"{fld} must be a word: a starter relation or a declared one", fld)
            elif rel in self.starter or rel in self.relations:
                continue
            elif rel.startswith(f"{FORM_MODULE}:{RELATION_KIND}/") and rel.split("/", 1)[1] in self.relations:
                continue
            else:
                self.add("relation-declared", it, f"{fld} {rel!r} is neither a starter relation "
                                                  f"({', '.join(self.starter)}) nor a declared "
                                                  f"{FORM_MODULE}:{RELATION_KIND}/<slug>: declare it, or use a "
                                                  "starter word", fld)

    # when-shape
    def when_shape(self, it: mc.Item) -> None:
        if "when" not in it.data:
            return
        v = it.data["when"]
        if mc.is_pending(v) or when_ok(v):
            return
        self.add("when-shape", it, f"when {_quote(str(v))} must be a date (2014-06-03), a year (2014) or an era "
                                   "word (childhood, 2010s, university)", "when")

    # strength-range
    def strength_range(self, it: mc.Item) -> None:
        if "strength" not in it.data:
            return
        v = it.data["strength"]
        if mc.is_pending(v) or strength_ok(v):
            return
        self.add("strength-range", it, f"strength {v!r} must be a whole number from 1 to 5", "strength")

    # id-module, held to the module folders: the reader places module folders only under parts.
    def module_folder(self, it: mc.Item) -> None:
        if "id-module" not in self.selected or it.file == self.v.catalog_file or it.module not in self.m.modules():
            return
        top, sep, _ = it.file.partition("/")
        if not sep:
            self.add("id-module", it, f"written at the holograph's root in {it.file}: a node lives in its module's "
                                      f"folder ({it.module}/) or in the catalog's nodes")
        elif top.upper() != it.module:
            self.add("id-module", it, f"id says {it.module} but the file is under {top}/")

    # catalog-key, held to the hid and the handle
    def catalog(self) -> None:
        if "catalog-key" not in self.selected:
            return
        cat, f = self.v.catalog, self.v.catalog_file
        cid = cat.get("id")
        if isinstance(cid, str) and cid.startswith("ascribe/") and "/" not in cid[len("ascribe/"):] \
                and cid[len("ascribe/"):].strip() and not HID_RE.match(cid[len("ascribe/"):]):
            self.add("catalog-key", None, f"id {cid!r}: the hid is 26 characters of lowercase base32 (a-z and 2-7), "
                                          "as Connect's", "id", file=f)
        h = cat.get("handle")
        if h is None:
            self.add("catalog-key", None, "no handle: a holograph carries a pseudonymous handle (lowercase words "
                                          "joined by hyphens)", "handle", file=f)
        elif not mc.is_pending(h) and not (isinstance(h, str) and HANDLE_RE.match(h)):
            self.add("catalog-key", None, f"handle {_quote(str(h))} must be lowercase words joined by hyphens: a "
                                          "pseudonym, never a name", "handle", file=f)
        p = cat.get("pseudonyms")
        if p is not None and not (isinstance(p, list) and all(isinstance(x, str) and x.strip() for x in p)):
            self.add("catalog-key", None, "pseudonyms is a list of the stand-in names the author uses", "pseudonyms",
                     file=f)

    # no-pii
    def no_pii(self) -> None:
        cat = self.v.catalog
        if "name" in cat:
            self.add("no-pii", None, f"name: reads as {PII_WHAT['identifying-field']} (a personal name): a "
                                     f"holograph names no one; {ADVICE}", "name")
        for fpath, key in _keys({k: v for k, v in cat.items() if k != "nodes"}):
            self._field(None, fpath, key)
        for fpath, s in _strings({k: v for k, v in cat.items() if k != "nodes"}):
            if fpath.startswith("releases[") and fpath.endswith("sha256") and SHA_RE.match(s):
                continue                            # a release's digest, never a person's number
            self._text(None, fpath, s, prose=fpath == "summary")
        for it in self.items:
            for fpath, key in _keys(it.data):
                self._field(it, fpath, key)
            wiki_form = it.module == FORM_MODULE and "wiki" in it.data      # a public subject, named as such
            for fpath, s in _strings(it.data):
                prose = not wiki_form and (fpath == "summary" or (fpath == "name" and it.kind == "experience"))
                self._text(it, fpath, s, prose=prose)
            self._born_when(it)
        root = self.v.root
        for rel in (self.v.files if self.files and root is not None else []):
            try:
                text = mc.read_text(root / rel)
            except (OSError, UnicodeDecodeError):
                continue                            # the load check has it
            for n, comment in _comments(text):
                for kind, found in pii_findings(comment):
                    self.add("no-pii", None, f"line {n}, a comment: {_quote(found)} reads as {PII_WHAT[kind]}; "
                                             f"{ADVICE}", file=rel)

    def _field(self, it: mc.Item | None, fpath: str, key: str) -> None:
        what = IDENTIFYING_FIELDS.get(key.casefold().replace("_", "-"))
        if what:
            self.add("no-pii", it, f"{fpath}: reads as {PII_WHAT['identifying-field']} ({what}), which a "
                                   f"holograph has no place for; {ADVICE}", fpath)

    def _text(self, it: mc.Item | None, fpath: str, s: str, *, prose: bool) -> None:
        spans = _pii_spans(s)
        for kind, a, b in spans:
            self.add("no-pii", it, f"{fpath}: {_quote(s[a:b])} reads as {PII_WHAT[kind]}; {ADVICE}", fpath)
        if prose:
            for pair in name_bigrams(s, self.pseudonyms, masked=[(a, b) for _, a, b in spans]):
                self.add("no-pii", it, f"{fpath}: {_quote(pair)} reads as {PII_WHAT['personal-name']}; {ADVICE}",
                         fpath)

    def _born_when(self, it: mc.Item) -> None:
        """A node dated to the day whose own words, or whose form, speak of a birth."""
        v = it.data.get("when")
        if not _is_date(v):
            return
        words = [it.data.get(k) for k in ("name", "summary", "form")]
        if any(isinstance(w, str) and (_BIRTH_WORD.search(w) or _BIRTH_WORD.search(w.replace("-", " ")))
               for w in words):
            self.add("no-pii", it, f"when {v} reads as {PII_WHAT['birth-date']}; {ADVICE}", "when")

    # private-marker
    def private_marker(self) -> None:
        root = self.v.root
        if root is None:
            return
        for mk, dropped in private_drops(root, self.marker):
            nodes = sum(1 for it in self.items if any(it.file == d or (d.endswith("/") and it.file.startswith(d))
                                                      for d in dropped))
            if self.v.catalog_file in dropped:
                what = f"the whole holograph, {self.v.catalog_file} included"
            else:
                what = ", ".join(dropped) or "nothing yet (the folder holds only the marker)"
            count = f" ({nodes} node{'s' if nodes != 1 else ''})" if dropped else ""
            self.add("private-marker", None, f"everything that leaves would leave out {what}{count}", file=mk)


def lint_holograph(path, *, registry: mc.Registry | None = None) -> mc.Report:
    """The generic checks (`macrocosm.lint`), the dialectic's when the holograph holds module D (`fabula.lint`), and
    Ascribe's own, in one report, for a holograph folder (or its `holograph.cosm`, or a volume already loaded): the
    one call the viewer makes for an `oes: ascribe/1` volume. A volume that is not `ascribe/1` gets the reader's
    report alone (and the dialectic's, when it holds D items)."""
    vol = path if isinstance(path, mc.Volume) else mc.load_volume(path, registry)
    rep = fb.lint(vol)
    if vol.manifest is None or vol.minicosm != "ascribe":
        return rep
    rep.checks = rep.checks + [c for c in ASCRIBE_CHECKS if c not in rep.checks]
    _Own(vol, rep).run()
    return rep


def advice_of(p: mc.Problem) -> str | None:
    """The advice line a `no-pii` finding carries (section 10.3: every warning ends with it), else None."""
    return ADVICE if p.check == "no-pii" else None


def report_dict(rep: mc.Report) -> dict:
    """`rep.to_dict()` with each problem's `advice` (the no-pii advice line, else null) beside its message: what the
    viewer shows for a holograph."""
    out = rep.to_dict()
    for sev in ("errors", "warnings", "notes"):
        for d, p in zip(out.get(sev) or [], getattr(rep, sev)):
            d["advice"] = advice_of(p)
    return out


def _checker(*, pii_error: bool = True) -> Callable[[mc.Volume], mc.Report]:
    """The check gate for a write into a holograph held in memory (a ledger's volume): the generic checks, the
    dialectic's, and Ascribe's own, with `no-pii` an error so that a write that would add a finding is refused (no
    file is read: comments and markers are the folder's, and the folder is not changed by a write's checks)."""
    def check(vol: mc.Volume) -> mc.Report:
        rep = fb.lint(vol)
        if vol.manifest is not None and vol.minicosm == "ascribe":
            _Own(vol, rep, files=False, pii_error=pii_error).run()
        return rep
    return check


# ---------------------------------------------------------------------------
# Releases (section 13): the record, its shape, its reader
# ---------------------------------------------------------------------------

def _sha_ok(v: Any) -> bool:
    """A sha256 in hex. A digest written unquoted that happens to be all digits reads back from YAML as a number
    (the text's own example's 2222…); one of 64 digits is read as the digest it spells."""
    if isinstance(v, bool):
        return False
    if isinstance(v, int):
        return len(str(v)) == 64
    return isinstance(v, str) and bool(SHA_RE.match(v))


def _timestamp_ok(v: Any) -> bool:
    if isinstance(v, _dt.datetime):
        return True
    if isinstance(v, str):
        try:
            _dt.datetime.fromisoformat(v.replace("Z", "+00:00"))
            return "T" in v
        except ValueError:
            return False
    return False


def release_problems(entry: Any) -> list[tuple[str, str]]:
    """(field, message) for each way a `releases:` entry falls short of section 13 (`release-shape`): a required
    field missing; `epoch` not a quarter, a month or a week; `as` not one of isograph, cryptograph, tokens, isomorph;
    `program` not `{name, sha256}`; `trace` not `{run, sha256}`; `at` not a timestamp; `sha256` not a digest;
    `items` not a sorted list of ids (an isomorph's `M:morph/<slug>` among them), or `all` for a cryptograph; `for`
    not `{path, sha256}`; and any field section 13 does not name (a record never holds what was withheld, a key or a
    party)."""
    if not isinstance(entry, dict):
        return [("", "a release is a mapping {epoch, as, program, trace, at, sha256, items}")]
    out: list[tuple[str, str]] = []
    for f in RELEASE_REQUIRED:
        if f not in entry:
            out.append((f, f"no {f}: a release records its epoch, as, program, trace, at, sha256 and items"))
    for k in entry:
        if k not in RELEASE_FIELDS:
            out.append((str(k), f"{k} is not a field of a release; a release never records what was withheld, a key "
                                "or the party a cryptograph was handed to"))
    if "epoch" in entry and not (isinstance(entry["epoch"], str) and EPOCH_RE.match(entry["epoch"])):
        out.append(("epoch", f"epoch {_quote(str(entry['epoch']))} is a quarter (2026-Q4), a month (2026-11) or a "
                             "week (2026-W45), never the day of an edit"))
    if "as" in entry and entry["as"] not in RELEASE_AS:
        out.append(("as", f"as {_quote(str(entry['as']))} is one of {', '.join(RELEASE_AS)}"))
    prog = entry.get("program")
    if "program" in entry and not (isinstance(prog, dict) and set(prog) == {"name", "sha256"}
                                   and isinstance(prog.get("name"), str) and prog["name"].strip()
                                   and _sha_ok(prog.get("sha256"))):
        out.append(("program", "program is {name, sha256}: the program's name and the sha256 of its .thym bytes"))
    tr = entry.get("trace")
    if "trace" in entry and not (isinstance(tr, dict) and set(tr) == {"run", "sha256"}
                                 and isinstance(tr.get("run"), str) and tr["run"].strip() and _sha_ok(tr.get("sha256"))):
        out.append(("trace", "trace is {run, sha256}: the run's id and the sha256 of its cleaned trace"))
    if "at" in entry and not _timestamp_ok(entry["at"]):
        out.append(("at", f"at {_quote(str(entry['at']))} is a timestamp (2026-11-05T14:15:00Z)"))
    if "sha256" in entry and not _sha_ok(entry["sha256"]):
        out.append(("sha256", "sha256 is the sha256 of the bytes that left, 64 hex characters"))
    if "items" in entry:
        items = entry["items"]
        if items == "all":
            if entry.get("as") != "cryptograph":
                out.append(("items", "items: all is only for a cryptograph of the whole holograph"))
        elif not (isinstance(items, list) and items and all(isinstance(x, str) and x.strip() for x in items)):
            out.append(("items", "items is the sorted list of the ids that left (all for a whole cryptograph)"))
        elif items != sorted(items) or len(set(items)) != len(items):
            out.append(("items", "items is sorted, each id once"))
    if "for" in entry:
        fr = entry["for"]
        if not (isinstance(fr, dict) and set(fr) == {"path", "sha256"} and isinstance(fr.get("path"), str)
                and fr["path"].strip() and _sha_ok(fr.get("sha256"))):
            out.append(("for", "for is {path, sha256}: the text a package's excerpt was released for"))
    return out


# ---------------------------------------------------------------------------
# The private filter (section 11): a pure function of the folder
# ---------------------------------------------------------------------------

@dataclass
class Filtered:
    """What may leave a holograph in one use. `files` maps each path that leaves (relative to the holograph's
    folder, `/`-separated, in path order) to its bytes; `whole` is True when a marker beside the catalog withholds
    the whole holograph, and then nothing leaves. `rewritten` names the kept files written out again without what
    they held that is withheld (never what that was)."""
    root: Path
    use: str
    files: dict = field(default_factory=dict)
    whole: bool = False
    rewritten: list = field(default_factory=list)


def _root_of(folder: Any) -> Path:
    p = Path(folder)
    return p.parent if p.name == CATALOG and p.is_file() else p


def _is_d_item(d: Any) -> bool:
    return isinstance(d, dict) and isinstance(d.get("id"), str) and d["id"].startswith(f"{DIALECTIC_MODULE}:")


def _restricted(d: Any) -> bool:
    return isinstance(d, dict) and d.get("visibility") == "restricted"


_UNREAD = object()


def private_filter(folder: Any, *, use: str = "projection", own_keeping: bool = False) -> Filtered:
    """The files that may leave a holograph folder in one use (`ingest`, `package`, `transfer` or `projection`), and
    their bytes: a pure function of the folder (it reads nothing else: no setting, no history, no other volume, and
    the same folder gives the same answer every time). It withholds:

    - every file and folder beside a `.ascribe-private` marker, with everything below them, the marker included; a
      marker beside the catalog withholds the whole holograph (`whole`, and nothing leaves);
    - every item (node, form, polyform, relation, question, session) with `visibility: restricted`, wherever it is
      written: a kept file that holds one is written out again without it, as its `nodes:` in the COSM YAML subset
      (the catalog as its mapping), without its comments;
    - module D (its folder, and any D item in the catalog), in every use but a `transfer` of the whole holograph
      into the holder's own keeping (`own_keeping=True`);
    - every candidate (a node a reading proposed, `provenance: {mode: derived, state: pending}`) and every question
      about one, in every use: a candidate is not part of the self until the holder says yes (ruling, 2026-11-06);
    - the catalog's `releases:`, in every use: the record of what left is the holder's own (ruling, 2026-11-06).

    Everything else leaves unchanged, byte for byte: a reference to a withheld item keeps its id, nothing is added
    in place of what was withheld, and the catalog stays unless a marker sits beside it. Two things are left behind
    because what they hold cannot be known without following them: a symbolic link, and a `.cosm` file that does not
    parse (it may hold a restricted item)."""
    if use not in FILTER_USES:
        raise ValueError(f"the filter applies to {', '.join(FILTER_USES)}, not {use!r}")
    root = _root_of(folder)
    if not (root / CATALOG).is_file():
        raise AscribeError(f"{root} holds no {CATALOG}: it is not a holograph")
    out = Filtered(root.resolve(), use)
    if (root / PRIVATE_MARKER).exists():
        out.whole = True
        return out
    keep_d = use == "transfer" and own_keeping
    found: dict[str, bytes] = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        here = Path(dirpath)
        rel_dir = here.relative_to(root)
        if PRIVATE_MARKER in filenames:
            dirnames[:] = []
            continue
        if not keep_d and rel_dir.parts and rel_dir.parts[0].upper() == DIALECTIC_MODULE and len(rel_dir.parts[0]) == 1:
            dirnames[:] = []
            continue
        dirnames[:] = sorted(n for n in dirnames if not (here / n).is_symlink())
        for n in sorted(filenames):
            p = here / n
            if p.is_symlink() or not p.is_file():
                continue
            found[(rel_dir / n).as_posix()] = p.read_bytes()
    parsed: dict[str, Any] = {}
    for rel in sorted(found):
        if rel.endswith(".cosm"):
            try:
                parsed[rel] = mc.yaml_load(found[rel].decode("utf-8-sig"))
            except Exception:  # noqa: BLE001 - a file that does not parse may hold anything: it stays behind
                parsed[rel] = _UNREAD
    # rulings of 2026-11-06: a candidate is not part of the self until the holder says yes, so it and the questions
    # about it never leave; and the catalog's `releases:` record is the holder's own account, which never leaves
    candidates = {str(x.get("id")) for d in parsed.values() if isinstance(d, dict)
                  for x in (d.get("nodes") if isinstance(d.get("nodes"), list) else []) if _is_candidate(x)}

    def about_candidate(x: Any) -> bool:
        about = x.get("about") if isinstance(x, dict) and _is_d_item(x) else None
        return isinstance(about, str) and about.split("#", 1)[0] in candidates

    for rel in sorted(found):
        raw = found[rel]
        if not rel.endswith(".cosm"):
            out.files[rel] = raw
            continue
        data = parsed[rel]
        if data is _UNREAD:
            continue
        nodes = data.get("nodes") if isinstance(data, dict) else None
        releases_here = rel == CATALOG and isinstance(data, dict) and "releases" in data
        if not isinstance(nodes, list) and not releases_here:
            out.files[rel] = raw
            continue
        nodes = nodes if isinstance(nodes, list) else None
        kept = None if nodes is None else [
            x for x in nodes if not (_restricted(x) or (not keep_d and _is_d_item(x)) or _is_candidate(x)
                                     or about_candidate(x))]
        if not releases_here and len(kept) == len(nodes):
            out.files[rel] = raw
            continue
        if rel == CATALOG:
            new = {k: v for k, v in data.items() if k != "releases"}
            if kept is not None:
                new["nodes"] = kept
        else:
            new = {"nodes": kept}
        out.files[rel] = mc.dump(new).encode("utf-8")
        out.rewritten.append(rel)
    return out


class _Materialized:
    """A filtered holograph written into a temporary folder and loaded, so that the reader and the checks read only
    what the filter keeps (`with _Materialized(filt) as vol:`)."""

    def __init__(self, filt: Filtered):
        self.filt = filt
        self._tmp: tempfile.TemporaryDirectory | None = None

    def __enter__(self) -> mc.Volume:
        self._tmp = tempfile.TemporaryDirectory(prefix="ascribe-filtered-")
        root = Path(self._tmp.name) / "holograph"
        for rel, data in self.filt.files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        return mc.load_volume(root)

    def __exit__(self, *exc: Any) -> None:
        if self._tmp is not None:
            self._tmp.cleanup()


def _pii_errors(vol: mc.Volume) -> list[mc.Problem]:
    """Every `no-pii` finding in a loaded holograph, at the severity of an error (a projection's rule 4)."""
    rep = mc.Report(volume=vol)
    _Own(vol, rep, pii_error=True).no_pii()
    return list(rep.errors)


# ---------------------------------------------------------------------------
# A holograph folder, opened for writing: its ledger, and its files written back byte for byte outside the change
# ---------------------------------------------------------------------------

class Holograph:
    """A holograph folder opened for the dialectic and the readings: the loaded volume, a ledger over every item
    (`enough.dialectic.Ledger`, D items included), and `save`, which writes each changed file back with every byte
    outside the change kept (`dialectic.write_back`) and each new item into its module's folder: a node into the
    first module file of its container (or `<M>/<module>.cosm`), a question into `D/questions.cosm`, a session into
    `D/<session>.cosm` (section 8.3's layout)."""

    def __init__(self, folder: Any, registry: mc.Registry | None = None):
        self.root = _root_of(folder)
        vol = mc.load_volume(self.root, registry)
        if vol.manifest is None or vol.refused is not None:
            raise AscribeError(f"the holograph was refused: {vol.refused}")
        if vol.minicosm != "ascribe":
            raise AscribeError(f"{self.root} is {vol.oes}, not a holograph (oes: {OES})")
        if vol.root is None or vol.catalog_file != CATALOG:
            raise AscribeError("a holograph is a folder whose catalog is holograph.cosm")
        self.vol = vol
        self.led = dl.ledger_from_volume(vol)
        self._ids0 = {d.get("id") for d in self.led.items if isinstance(d, dict)}
        self._origin0 = list(self.led.origin)
        self._files0 = {f for _part, f in self._origin0}

    @property
    def pseudonyms(self) -> list[str]:
        p = self.led.catalog.get("pseudonyms")
        return [x for x in p if isinstance(x, str)] if isinstance(p, list) else []

    def _new_file(self, d: dict) -> str:
        iid = str(d.get("id") or "")
        mod = iid.split(":", 1)[0] if ":" in iid else ""
        if mod == DIALECTIC_MODULE:
            if d.get("type") == dl.SESSION:
                return f"{DIALECTIC_MODULE}/{dl._slug(iid.split('/', 1)[-1], 60) or 'session'}.cosm"
            return f"{DIALECTIC_MODULE}/{MODULE_FILES[DIALECTIC_MODULE]}.cosm"
        have = sorted(f for f in self._files0 if f.split("/", 1)[0].upper() == mod and "/" in f)
        if not have and (self.root / mod).is_dir():
            have = sorted(p.relative_to(self.root).as_posix() for p in (self.root / mod).rglob("*.cosm"))
        return have[0] if have else f"{mod}/{MODULE_FILES.get(mod, 'nodes')}.cosm"

    def save(self) -> list[str]:
        """Write every changed or new file of the holograph; the files written, in order. Atomic per file."""
        by_file: dict[str, list] = {}
        for i, d in enumerate(self.led.items):
            iid = d.get("id") if isinstance(d, dict) else None
            f = self.led.file_of(i) if iid in self._ids0 else self._new_file(d)
            by_file.setdefault(f, []).append(d)
        written = []
        for f in sorted(set(by_file) | self._files0 | {CATALOG}):
            path = self.root / f
            nodes = by_file.get(f, [])
            text = mc.read_text(path) if path.is_file() else None
            old = mc.yaml_load(text) if text is not None else None
            old = old if isinstance(old, dict) else ({} if text is not None else None)
            if f == CATALOG:
                new = {k: v for k, v in (old or {}).items()}
                for k, v in self.led.catalog.items():
                    if k != "nodes":
                        new[k] = v
                if nodes or "nodes" in new:
                    new["nodes"] = nodes
            else:
                new = dict(old or {})
                new["nodes"] = nodes
            if old is not None and dl._same(old, new):
                continue
            if text is None:
                out = dl.dump_text(new)
            else:
                out, _how = dl.write_back(text, old, new)
            path.parent.mkdir(parents=True, exist_ok=True)
            dl.write_atomic(path, out)
            written.append(f)
        self._ids0 = {d.get("id") for d in self.led.items if isinstance(d, dict)}
        self._files0 = self._files0 | set(by_file)
        return written


def open_holograph(folder: Any, registry: mc.Registry | None = None) -> Holograph:
    """A holograph folder opened for writing (refused in plain words when it is not one)."""
    return Holograph(folder, registry)


# ---------------------------------------------------------------------------
# The dialectic, applied (section 8)
# ---------------------------------------------------------------------------

def pii_in(text: Any, pseudonyms: Iterable[str] = ()) -> list[str]:
    """What a piece of the holder's words reads as, where it reads like personal data (an email address, a phone
    number, an id-like run of digits, a street address, a birth date, a personal name), each once; [] when nothing.
    Read as prose: a capitalised pair that is not a declared pseudonym reads as a name."""
    if not isinstance(text, str) or not text.strip():
        return []
    spans = _pii_spans(text)
    found = [PII_WHAT[k] for k, _, _ in spans]
    if name_bigrams(text, pseudonyms, masked=[(a, b) for _, a, b in spans]):
        found.append(PII_WHAT["personal-name"])
    return list(dict.fromkeys(found))


def _module_of(led: dl.Ledger, about: Any, depth: int = 0) -> str | None:
    if not isinstance(about, str) or depth > 4:
        return None
    if about in KINDS or about == FORM_MODULE:
        return about
    head = about.split("#", 1)[0]
    d = led.item(head)
    if d is None:
        return head.split(":", 1)[0] if ":" in head else None
    if _is_d_item(d):
        return _module_of(led, d.get("about"), depth + 1)
    return head.split(":", 1)[0] if ":" in head else None


def _is_candidate(d: Any) -> bool:
    prov = d.get("provenance") if isinstance(d, dict) else None
    return isinstance(prov, dict) and prov.get("state") == "pending" and prov.get("mode") == "derived"


def raise_bank(folder: Any, *, at: Any = None, run: str | None = None, dry: bool = False) -> list[dict]:
    """The bank's questions, and those the core raises by rule (one per `{pending: …}`, one per node pending or
    below confidence 0.5), raised for a holograph and landed in `D/questions.cosm`, every one `to: holder`. A bank
    entry is asked once of the holograph: never again while a question from it stands, a declined one included (the
    holder may ask for it again: `ask_again`). Returns the questions landed; `dry`: the questions it would land,
    nothing written."""
    h = Holograph(folder)
    r = dl.raise_questions(h.led, to=HOLDER, run=run, at=at, checker=_checker(pii_error=False))
    if dry:
        return [copy.deepcopy(q) for q in r.questions]
    if r.questions:
        dl.land(h.led, r.questions)
        h.save()
    return [copy.deepcopy(q) for q in r.questions]


def queue(folder: Any) -> list[dict]:
    """Every open question of a holograph, thinnest container first: ordered by how many nodes the container it
    belongs to holds (the ten and F; a candidate is not counted), then by the order of the modules, then as written.
    One or two at a time is the asker's business."""
    h = Holograph(folder)
    counts = {L: 0 for L in CONTAINERS + (FORM_MODULE,)}
    for it in h.vol.items.values():
        if it.module in counts and not _is_candidate(it.data) and (it.module != FORM_MODULE or it.kind == "form"):
            counts[it.module] += 1
    order = {L: i for i, L in enumerate(CONTAINERS + (FORM_MODULE,))}
    rows = []
    for n, q in enumerate(h.led.questions()):
        if q.get("state") != "open":
            continue
        m = _module_of(h.led, q.get("about"))
        rows.append(((counts.get(m, 10 ** 6), order.get(m, 99), n), q))
    return [copy.deepcopy(q) for _k, q in sorted(rows, key=lambda r: r[0])]


def ask_again(folder: Any, question: str) -> dict:
    """A question the holder asks to be put again (a declined bank entry included): back to open, its answers kept."""
    h = Holograph(folder)
    q = dl.reask(h.led, question)
    h.save()
    return copy.deepcopy(q)


_SESSION_N = re.compile(r"^(?:D:session/)?session-([0-9]+)$")


def _next_session(led: dl.Ledger) -> str:
    """The next `session-<n>`, past every session the holograph holds and every one its items' sources cite: the
    earlier spelling `session-<n>` names `D:session/session-<n>` whether or not the record is there (section 8.3),
    so a new session never takes a number an earlier one was cited by."""
    n = 0
    for d in led.items:
        if not isinstance(d, dict):
            continue
        refs = [d.get("id")] if dl.is_session(d) else []
        prov = d.get("provenance")
        if isinstance(prov, dict) and isinstance(prov.get("sources"), list):
            refs += prov["sources"]
        for r in refs:
            mt = _SESSION_N.match(str(r)) if isinstance(r, str) else None
            if mt:
                n = max(n, int(mt.group(1)))
    return f"session-{n + 1}"


def record_answers(folder: Any, answers: Iterable[Any], *, session: dict | None = None, at: Any = None) -> dl.Recorded:
    """The holder's answers recorded on their questions, their words verbatim (the move `record`, through
    `enough.dialectic.record`), in a session whose `with` is `{to: holder, who: the holder}` and nothing else. An
    answer whose words read like personal data is refused in plain words (`Recorded.refused`), nothing of it is
    written, and the question stays open. `answers` are mappings `{question, says, value, confidence, dont_know,
    declined, skip}` (or `dialectic.Answer`); `session` may give `id`, `through` (person or agent) and `model`."""
    h = Holograph(folder)
    kept, refused = [], []
    for raw in answers:
        a = dl.Answer.of(raw)
        texts = [a.says]
        if a.value is not None:
            texts += [x for x in (a.value if isinstance(a.value, list) else [a.value]) if isinstance(x, str)]
        found = list(dict.fromkeys(w for t in texts for w in pii_in(t, h.pseudonyms)))
        if found:
            q = h.led.question(a.question)
            refused.append((q["id"] if q else a.question, REFUSED_PII.format(what=", ".join(found))))
            continue
        kept.append(a)
    sess = {k: v for k, v in dict(session or {}).items() if k in ("id", "at", "through", "model")}
    sess["with"] = {"to": HOLDER, "who": "the holder"}
    if not sess.get("id"):
        sess["id"] = dl.S_PREFIX + _next_session(h.led)
    rec = dl.record(h.led, kept, session=sess, at=at)
    rec.refused = refused + rec.refused
    if rec.recorded or rec.skipped:
        h.save()
    return rec


def _fold_words(s: Any) -> str:
    return " ".join(str(s).split())


def _form_index(led: dl.Ledger) -> list[tuple[str, str, list[str]]]:
    """(id, kind, the phrases that name it: its name, its slug in words, its FEED word) for every form and polyform."""
    out = []
    for d in led.items:
        if not isinstance(d, dict) or not isinstance(d.get("id"), str) or not d["id"].startswith(f"{FORM_MODULE}:"):
            continue
        kind = d.get("type")
        if kind not in ANCHOR_KINDS:
            continue
        names = set()
        if isinstance(d.get("name"), str):
            names.add(_fold_words(d["name"]).casefold())
        names.add(d["id"].split("/", 1)[-1].replace("-", " ").casefold())
        feed = d.get("feed")
        if isinstance(feed, dict) and isinstance(feed.get("word"), str):
            names.add(feed["word"].casefold())
        out.append((d["id"], kind, sorted(n for n in names if n)))
    return out


def find_form(led: dl.Ledger, words: str) -> str | None:
    """The form or polyform of the holograph that `words` name (its name, its slug, or its FEED word, case aside)."""
    w = _fold_words(words).strip(" .").casefold()
    hits = {fid for fid, _k, names in _form_index(led) if w in names or dl._slug(w) == fid.split("/", 1)[-1]}
    return next(iter(hits)) if len(hits) == 1 else None


def discover_form(led: dl.Ledger, text: str) -> str | None:
    """The form or polyform an answer is plainly about: the one whose name or FEED word the answer says as a whole
    phrase, the longest when several overlap; None when it names none, or two that are not one inside the other."""
    t = _fold_words(text).casefold()
    hits = []
    for fid, _k, names in _form_index(led):
        best = max((len(n) for n in names if re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", t)), default=0)
        if best:
            hits.append((best, fid))
    if not hits:
        return None
    top = max(b for b, _ in hits)
    ids = {fid for b, fid in hits if b == top}
    return next(iter(ids)) if len(ids) == 1 else None


def _lookup(feed: Any, word: str) -> dict | None:
    if feed is None:
        return None
    try:
        got = feed([word]) if callable(feed) else feed
    except Exception:  # noqa: BLE001 - a dictionary that cannot answer grounds nothing
        return None
    if not isinstance(got, dict):
        return None
    e = got.get(word, got.get(word.lower()))
    if e is None:
        e = next((v for v in got.values() if isinstance(v, dict)), None)
    return e if isinstance(e, dict) and isinstance(e.get("word"), str) else None


def new_form(led: dl.Ledger, words: str, *, feed: Any, provenance: dict) -> dict:
    """A new form for what an answer, or a reading, is about (section 8.4), named in the holder's words: grounded in
    FEED (`feed: {word, pos, origin}`, its summary FEED's definition) when it is one word FEED has; else
    `feed: {pending: "not in FEED"}` and a summary the holder still owes, as open questions; never a sense FEED does
    not give. `feed` is FEED's batch lookup (`words -> {word: entry | None}`), or None when there is no dictionary
    here (then a one-word form's grounding is an open question too)."""
    w = _fold_words(words).strip(" .,;:")
    taken = led.ids()
    base = dl._slug(w, 48) or "form"
    slug, n = base, 2
    while f"{FORM_MODULE}:form/{slug}" in taken:
        slug, n = f"{base}-{n}", n + 1
    item: dict = {"id": f"{FORM_MODULE}:form/{slug}", "type": "form", "name": w}
    entry = None
    if len(w.split()) == 1:
        entry = _lookup(feed, w) or (_lookup(feed, w.lower()) if w.lower() != w else None)
    if entry is not None:
        item["name"] = entry["word"]
        grounding = {"word": entry["word"]}
        pos = entry.get("pos_primary") or entry.get("pos")
        if isinstance(pos, str) and pos.strip():
            grounding["pos"] = pos.strip()
        grounding["origin"] = entry.get("origin") if entry.get("origin") in ("feed", "user") else "feed"
        definition = entry.get("definition")
        item["summary"] = (_fold_words(definition) if isinstance(definition, str) and definition.strip()
                           else {"pending": f"What is {w}, in one line?"})
        item["feed"] = grounding
    else:
        item["summary"] = {"pending": f"What is {w}, in one line?"}
        item["feed"] = {"pending": "not in FEED" if (feed is not None or len(w.split()) > 1)
                        else "not looked up in FEED"}
    item["provenance"] = copy.deepcopy(provenance)
    return item


@dataclass
class HoloSettled:
    """What `settle_holograph` did: `settled` [(question id, wrote)]; `follow_ups` [(question id, the follow-up's
    id)] for an answer that names no thing yet (no node is written until the holder says what it is about);
    `counters` [(question id, counter id, errors)] for a write the checks refused; `removed` the candidates a no
    removed; `needs_reading` [(question id, about, because)]; `waiting` [(question id, why)]; `stale` [ids]."""
    settled: list = field(default_factory=list)
    follow_ups: list = field(default_factory=list)
    counters: list = field(default_factory=list)
    removed: list = field(default_factory=list)
    needs_reading: list = field(default_factory=list)
    waiting: list = field(default_factory=list)
    stale: list = field(default_factory=list)


def _settle_mark(led: dl.Ledger, qid: str, wrote: list, when: Any, run: str | None) -> None:
    q = led.question(qid)
    q["settled"] = {"at": when, **({"run": run} if run else {}), "wrote": list(wrote)}


def _counter(led: dl.Ledger, q: dict, refused: list, last: dict, when: Any, run: str | None, out: HoloSettled) -> None:
    taken = led.ids()
    slug = dl._unique_slug(q["id"][len(dl.Q_PREFIX):] + "-counter", taken, led)
    cq = dl._question_item(dl.Q_PREFIX + slug, copy.deepcopy(q.get("about")),
                           dl._counter_text(led, q, refused, last.get("value")), "counter", q, HOLDER,
                           {"by": "move", "from": "settle", "at": when, "run": run})
    led.add(cq)
    out.counters.append((q["id"], cq["id"], refused))


def _about_follow_up(led: dl.Ledger, q: dict) -> dict | None:
    """The follow-up that asks what a bank answer is about (`about: <the question's id>`, raised by settle)."""
    for o in led.questions():
        if o is not q and o.get("about") == q["id"] and (o.get("raised") or {}).get("from") == "settle" \
                and o.get("why") == "missing" and o.get("state") not in dl.ENDED:
            return o
    return None


def _follows_a_question(led: dl.Ledger, q: dict) -> bool:
    about = q.get("about")
    return isinstance(about, str) and about.startswith(dl.Q_PREFIX) and led.question(about) is not None


def _confidence_of(last: dict) -> Any:
    c = last.get("confidence")
    return 1 if c is None else c


def _settle_bank(h: Holograph, q: dict, last: dict, forms: dict, feed: Any, when: Any, run: str | None,
                 checker: Callable, out: HoloSettled) -> None:
    led = h.led
    qid, letter = q["id"], q["about"]
    if q.get("state") != "answered":                       # "I don't know" or a refusal: nothing is written
        _settle_mark(led, qid, [], when, run)
        out.settled.append((qid, []))
        return
    text = _fold_words(dl._scalar_text(last.get("value")))
    sid = dl._sid(str(last.get("session") or ""))
    prov = {"mode": "dialectic", "sources": [sid], "confidence": _confidence_of(last)}
    fu = _about_follow_up(led, q)
    words = forms.get(qid) or forms.get(qid[len(dl.Q_PREFIX):])
    if words is None and fu is not None:
        if fu.get("state") == "answered":
            words = dl._scalar_text((dl._last_answer(fu) or {}).get("value"))
        elif fu.get("state") in ("unknown", "declined"):
            _settle_mark(led, qid, [], when, run)
            _settle_mark(led, fu["id"], [], when, run)
            out.settled += [(qid, []), (fu["id"], [])]
            return
        else:
            out.waiting.append((qid, f"{fu['id']} asks what it is about"))
            return
    cand = led.copy()
    wrote: list[str] = []
    if letter == FORM_MODULE:
        parts = [re.sub(r"^(?:and|or)\s+", "", p.strip(" .")) for p in re.split(r"[\n;,]+", str(words or text))]
        for part in [p for p in parts if p]:
            if find_form(cand, part) is not None:
                continue
            item = new_form(cand, part, feed=feed, provenance=prov)
            cand.add(item)
            wrote.append(item["id"])
    else:
        target = (find_form(led, words) if words else discover_form(led, text))
        made_form = None
        if target is None and words:
            made_form = new_form(led, words, feed=feed, provenance=prov)
            target = made_form["id"]
        if target is None:                                  # names no thing yet: no node, a follow-up asks
            taken = led.ids()
            slug = dl._unique_slug(qid[len(dl.Q_PREFIX):] + "-about", taken, led)
            spec = FOLLOW_UPS["form"]
            fq = dl._question_item(dl.Q_PREFIX + slug, qid, spec["asks"], "missing", spec, HOLDER,
                                   {"by": "move", "from": "settle", "at": when, "run": run})
            led.add(fq)
            out.follow_ups.append((qid, fq["id"]))
            return
        kind = KINDS[letter]
        base = dl._slug(dl._first_words(text), 40) or kind
        slug, n = base, 2
        taken = led.ids()
        while f"{letter}:{kind}/{slug}" in taken:
            slug, n = f"{base}-{n}", n + 1
        node = {"id": f"{letter}:{kind}/{slug}", "type": kind, "name": dl._first_words(text), "summary": text,
                "form": target, "provenance": prov}
        if made_form is not None:
            cand.add(made_form)
            wrote.append(made_form["id"])
        cand.add(node)
        wrote.insert(0, node["id"])
    res = dl._commit(led, cand, wrote, checker)
    if res.refused:
        _counter(led, led.question(qid), res.refused, last, when, run, out)
        return
    _settle_mark(led, qid, wrote, when, run)
    out.settled.append((qid, list(wrote)))
    if fu is not None:
        _settle_mark(led, fu["id"], wrote, when, run)
        out.settled.append((fu["id"], list(wrote)))


def _is_candidate_question(led: dl.Ledger, q: dict) -> bool:
    d = led.item(q.get("about")) if isinstance(q.get("about"), str) else None
    return (d is not None and _is_candidate(d) and q.get("kind") == "choice"
            and set(map(str, q.get("options") or [])) == set(CANDIDATE_OPTIONS))


def _orphan_forms(led: dl.Ledger, sources: list) -> list[str]:
    """Forms a reading made from one text (the same sources) that nothing references any more."""
    refs = set()
    for d in led.items:
        if isinstance(d, dict):
            for fpath, v in _strings(d):
                if fpath != "id":
                    refs.add(v)
    out = []
    for d in led.items:
        if isinstance(d, dict) and str(d.get("id", "")).startswith(f"{FORM_MODULE}:form/") and d["id"] not in refs:
            prov = d.get("provenance")
            if isinstance(prov, dict) and prov.get("mode") == "derived" and prov.get("sources") == sources:
                out.append(d["id"])
    return out


def _settle_candidate(h: Holograph, q: dict, last: dict, when: Any, run: str | None, checker: Callable,
                      out: HoloSettled) -> None:
    led = h.led
    qid, cid = q["id"], q["about"]
    if q.get("state") != "answered":                       # "I don't know" or a refusal: it stays a candidate
        _settle_mark(led, qid, [], when, run)
        out.settled.append((qid, []))
        return
    word = str(last.get("value") or "").strip().lower()
    sid = dl._sid(str(last.get("session") or ""))
    cand = led.copy()
    i = cand.index(cid)
    d = cand.items[i]
    if word == "no":
        sources = copy.deepcopy((d.get("provenance") or {}).get("sources"))
        cand.question(qid)["settled"] = {"at": when, **({"run": run} if run else {}), "wrote": []}
        del cand.items[i]
        if i < len(cand.origin):
            del cand.origin[i]
        for fid in _orphan_forms(cand, sources):
            j = cand.index(fid)
            del cand.items[j]
            if j < len(cand.origin):
                del cand.origin[j]
        res = dl._commit(led, cand, [], checker)
        if res.refused:
            _counter(led, led.question(qid), res.refused, last, when, run, out)
            return
        _settle_mark(led, qid, [], when, run)
        out.settled.append((qid, []))
        out.removed.append(cid)
        return
    prov = d.setdefault("provenance", {})
    prov.pop("state", None)
    srcs = prov.get("sources") if isinstance(prov.get("sources"), list) else []
    if sid not in srcs:
        srcs.append(sid)
    prov["sources"] = srcs
    prov["confidence"] = _confidence_of(last)
    res = dl._commit(led, cand, [cid], checker)
    if res.refused:
        _counter(led, led.question(qid), res.refused, last, when, run, out)
        return
    _settle_mark(led, qid, [cid], when, run)
    out.settled.append((qid, [cid]))
    if word == "partly":
        taken = led.ids()
        slug = dl._unique_slug(qid[len(dl.Q_PREFIX):] + "-summary", taken, led)
        fq = dl._question_item(dl.Q_PREFIX + slug, f"{cid}#summary", "How would you say this, in your own words?",
                               "missing", {"kind": "text"}, HOLDER,
                               {"by": "move", "from": "settle", "at": when, "run": run})
        led.add(fq)
        out.follow_ups.append((qid, fq["id"]))


def settle_holograph(folder: Any, *, forms: dict | None = None, feed: Any = None, at: Any = None,
                     run: str | None = None) -> HoloSettled:
    """Every answered, unknown or declined question of a holograph, not yet settled, folded in as section 8 says
    (the move `settle`, for a holograph), and the holograph written back:

    - a bank question (`about: <letter>`): a value writes a node in that container (`name` the holder's first words,
      `summary` the answer, `form` found as section 8.4 says, `provenance: {mode: dialectic, sources:
      [D:session/<id>], confidence}`); for F, one form for each thing the answer lists. `forms` maps a question's id
      to what the holder said it is about (the follow-up "What is this about, in a word or two?"); without it the
      form is one of the holograph the answer plainly names, and an answer that names none writes nothing yet and
      raises that follow-up (`about: <the question>`), whose answer settles both. "I don't know" and a refusal write
      nothing.
    - a candidate's question (section 9): yes makes it the holder's (`provenance.state` removed, the session among
      its sources, the holder's confidence); partly, the same and a follow-up about its `summary`; no removes it
      (and a form the same reading made that nothing else names) and settles the question with `wrote: []`.
    - anything else (a follow-up about a field, an open question `{pending}`): the core's `fold`, field by field.

    Every write passes the checks or is not made (a counter question is raised); a write that would add a no-pii
    finding is refused the same way. `feed` is FEED's batch lookup for grounding a new form."""
    h = Holograph(folder)
    led = h.led
    when = dl.now(at)
    out = HoloSettled()
    checker = _checker()
    out.stale = dl.mark_stale(led, by="settle", at=when)
    forms = dict(forms or {})
    for qid in [q["id"] for q in led.questions()]:
        q = led.question(qid)
        if q is None or q.get("state") not in dl.ANSWERED or dl._settled_current(q):
            continue
        last = dl._last_answer(q)
        if last is None:
            out.waiting.append((qid, "no answer to fold"))
            continue
        if dl._has_counter(led, q):
            out.waiting.append((qid, "its counter question stands"))
            continue
        about = q.get("about")
        if _follows_a_question(led, q):
            parent = led.question(about)
            if parent is not None and isinstance(parent.get("about"), str) \
                    and (parent["about"] in KINDS or parent["about"] == FORM_MODULE):
                continue                                      # settled with the question it follows
        if isinstance(about, str) and (about in KINDS or about == FORM_MODULE):
            _settle_bank(h, q, last, forms, feed, when, run, checker, out)
            continue
        if _is_candidate_question(led, q):
            _settle_candidate(h, q, last, when, run, checker, out)
            continue
        res = dl.fold(led, about, last, question=q, checker=checker)
        if res.needs_reading:
            out.needs_reading.append((qid, dl._about_key(about), res.needs_reading))
            continue
        if res.refused:
            _counter(led, led.question(qid), res.refused, last, when, run, out)
            continue
        _settle_mark(led, qid, res.wrote, when, run)
        out.settled.append((qid, list(res.wrote)))
    # A follow-up answered after its bank question was settled some other way is settled with nothing to write.
    for q in led.questions():
        if _follows_a_question(led, q) and q.get("state") in dl.ANSWERED and not q.get("settled"):
            parent = led.question(q["about"])
            if parent is not None and parent.get("settled"):
                _settle_mark(led, q["id"], parent["settled"].get("wrote", []), when, run)
                out.settled.append((q["id"], list(parent["settled"].get("wrote", []))))
    h.save()
    return out


@dataclass
class Answered:
    """What `answer` did: the record (`refused` when the answer was refused, and then nothing was written) and the
    settling that followed."""
    recorded: dl.Recorded
    settled: HoloSettled | None = None

    @property
    def refused(self) -> str | None:
        return self.recorded.refused[0][1] if self.recorded.refused else None


def answer(folder: Any, question: str, says: str = "", *, value: Any = None, confidence: float | None = None,
           dont_know: bool = False, declined: bool = False, skip: bool = False, about: str | None = None,
           session: dict | None = None, feed: Any = None, at: Any = None, run: str | None = None) -> Answered:
    """One answer of the holder's, recorded and settled in one step (what a page or an agent does after putting a
    question): `about` is what the holder said the answer is about, when they said it. Refused, nothing is written
    and the question stays open (`Answered.refused` holds the words to show)."""
    rec = record_answers(folder, [{"question": question, "says": says, "value": value, "confidence": confidence,
                                   "dont_know": dont_know, "declined": declined, "skip": skip}],
                         session=session, at=at)
    if rec.refused or skip:
        return Answered(rec)
    qid = rec.recorded[0][0] if rec.recorded else question
    st = settle_holograph(folder, forms={qid: about} if about else None, feed=feed, at=at, run=run)
    return Answered(rec, st)


def follow_ups(folder: Any, node: str, *, fields: Iterable[str] | None = None, at: Any = None,
               run: str | None = None) -> list[dict]:
    """The follow-up questions about a node's optional fields (section 8.4: form, when, valence, strength), each
    `to: holder`, `why: missing`, about `<node>#<field>`, for a field the node does not hold (or holds as an open
    question), and never a second time about one field (a field the holder left empty stays empty). Landed in
    `D/questions.cosm`; returns them."""
    h = Holograph(folder)
    led = h.led
    d = led.item(node)
    if d is None or _is_d_item(d) or _is_candidate(d) or str(d.get("id", "")).split(":", 1)[0] not in KINDS:
        raise AscribeError(f"{node} is not a node of the self: follow-ups ask about the ten kinds' nodes")
    when = dl.now(at)
    m_spec = {str(e.get("about", "")).lstrip("#"): e for e in (h.vol.manifest._block("dialectic").get("follow-ups")
                                                               or []) if isinstance(e, dict)}
    asked = {dl._about_key(q.get("about")) for q in led.questions()}
    new = []
    taken = led.ids()
    for f in fields or FOLLOW_UPS:
        if f not in FOLLOW_UPS:
            raise AscribeError(f"a follow-up asks about form, when, valence or strength, not {f}")
        found, v = dl.get_field(d, f)
        if found and not mc.is_pending(v):
            continue
        addr = f"{d['id']}#{f}"
        if dl._about_key(addr) in asked:
            continue
        spec = {**FOLLOW_UPS[f], **{k: v for k, v in m_spec.get(f, {}).items() if k != "about"}}
        slug = dl._unique_slug(f"{d['id'].split('/', 1)[-1]}-{f}", taken, led)
        taken.add(dl.Q_PREFIX + slug)
        new.append(dl._question_item(dl.Q_PREFIX + slug, addr, spec["asks"], "missing", spec, HOLDER,
                                     {"by": "move", "from": "follow-up", "at": when, "run": run}))
    if new:
        dl.land(led, new)
        h.save()
    return copy.deepcopy(new)


# ---------------------------------------------------------------------------
# Reading the holder's own texts (section 9): candidates and their questions
# ---------------------------------------------------------------------------

def _kind_letter(k: Any) -> str | None:
    if isinstance(k, str):
        if k in KINDS:
            return k
        for L, kind in KINDS.items():
            if k.strip().lower() == kind:
                return L
    return None


def proposal_problem(p: Any, pseudonyms: Iterable[str] = ()) -> str | None:
    """Why a reading's proposal cannot become a candidate, in plain words; None when it can. A proposal is
    `{kind, name, summary, span, confidence, form (what it is about, in words, or a form's id), cites (the fabula's
    items it was read from)}`."""
    if not isinstance(p, dict):
        return "a proposal is a mapping {kind, name, summary, span, confidence, form}"
    if _kind_letter(p.get("kind")) is None:
        return f"kind {p.get('kind')!r} is not one of the ten: {', '.join(KINDS.values())}"
    for f in ("name", "summary"):
        v = p.get(f)
        if not isinstance(v, str) or not v.strip() or "\n" in v.strip():
            return f"{f} is one line of words"
    found = pii_in(p["name"], pseudonyms) + pii_in(p["summary"], pseudonyms)
    if found:
        return (f"it reads like personal data ({', '.join(dict.fromkeys(found))}): a candidate names people only by "
                "role or by a declared pseudonym")
    span = p.get("span")
    if span is None:
        return "a candidate carries the span of the text that shows it"
    why = dl._span_shape_why(span)
    if why:
        return why
    c = p.get("confidence")
    if isinstance(c, bool) or not isinstance(c, (int, float)) or not 0 <= c <= 1:
        return "confidence is the reading's, a number from 0 to 1"
    form = p.get("form")
    if form is not None and not (isinstance(form, str) and form.strip()):
        return "form is what the candidate is about, in a word or two, or a form's id"
    if form is None and not (isinstance(p.get("about"), str) and p["about"].strip()):
        return "a candidate says what it is about (form), or what it seems to be about (about)"
    return None


def candidates(folder: Any, proposals: Iterable[Any], *, text: str, sha256: str, made: dict | None = None,
               feed: Any = None, at: Any = None, run: str | None = None) -> tuple[list[dict], list[tuple[int, str]]]:
    """A reading's proposals, read from the holder's own text `text` (whose sha256 is `sha256`), as candidate nodes
    and their questions (section 9), checked and ready to land, and the proposals refused `[(index, why)]`. Writes
    nothing (`land_candidates` does). Each candidate is an ordinary node of its kind with `provenance: {mode:
    derived, sources: ["<text>#sha256:<digest>"], confidence, state: pending}`, its `span`, its `form` (a form of the
    holograph, a new one found as section 8.4 says, or `{pending: "<what it seems to be about>"}`) and `made` when
    given; its question is `about` it, `why: unsure`, `to: holder`, `kind: choice`, `options: [yes, no, partly]`. A
    proposal that reads like personal data, or that would add a check error, is refused; the others stand."""
    if not (isinstance(sha256, str) and SHA_RE.match(sha256)):
        raise AscribeError("a reading names its text's sha256")
    h = Holograph(folder)
    source = f"{Path(str(text)).name}#sha256:{sha256}"
    when = dl.now(at)
    checker = _checker()
    led = h.led.copy()
    before = dl._errors(led, checker)
    out: list[dict] = []
    refused: list[tuple[int, str]] = []
    for i, p in enumerate(proposals):
        why = proposal_problem(p, h.pseudonyms)
        if why:
            refused.append((i, why))
            continue
        letter = _kind_letter(p["kind"])
        kind = KINDS[letter]
        conf = p["confidence"]
        prov = {"mode": "derived", "sources": [source], "confidence": conf}
        trial = led.copy()
        made_form = None
        form: Any
        if isinstance(p.get("form"), str):
            words = p["form"].strip()
            form = words if trial.item(words) is not None and words.startswith(f"{FORM_MODULE}:") \
                else find_form(trial, words)
            if form is None:
                made_form = new_form(trial, words, feed=feed, provenance=prov)
                form = made_form["id"]
                trial.add(made_form)
        else:
            form = {"pending": _fold_words(p["about"])}
        name = _fold_words(p["name"])
        base = dl._slug(name, 40) or kind
        slug, n = base, 2
        taken = trial.ids()
        while f"{letter}:{kind}/{slug}" in taken:
            slug, n = f"{base}-{n}", n + 1
        node: dict = {"id": f"{letter}:{kind}/{slug}", "type": kind, "name": name, "summary": _fold_words(p["summary"]),
                      "form": form, "span": copy.deepcopy(p["span"]),
                      "provenance": {**prov, "state": "pending"}}
        if made:
            node["made"] = copy.deepcopy(made)
        trial.add(node)
        qslug = dl._unique_slug(f"{slug}-candidate", trial.ids(), trial)
        q = dl._question_item(dl.Q_PREFIX + qslug, node["id"], f"Is this so? \"{node['summary']}\"", "unsure",
                              {"kind": "choice", "options": list(CANDIDATE_OPTIONS)}, HOLDER,
                              {"by": "model", "from": "propose", "at": when, "run": run})
        trial.add(q)
        new = dl._new_errors(before, dl._errors(trial, checker))
        if new:
            refused.append((i, "; ".join(str(e[3]) for e in new[:3])))
            continue
        led = trial
        before = dl._errors(led, checker)
        out += ([made_form] if made_form else []) + [node, q]
    return out, refused


def land_candidates(folder: Any, items: Iterable[dict]) -> list[str]:
    """Candidates and their questions (as `candidates` gives them) written into the holograph, every one or none:
    refused when an id is already there, when an item is not a candidate, its question or a form a reading made, or
    when they would add a check error (no-pii included). Returns the ids written."""
    h = Holograph(folder)
    items = [copy.deepcopy(d) for d in items]
    ids = h.led.ids()
    clash = [d.get("id") for d in items if d.get("id") in ids]
    if clash:
        raise AscribeError(f"the holograph already holds {', '.join(map(str, clash))}; nothing was written")
    for d in items:
        iid = str(d.get("id", ""))
        ok = (_is_candidate(d) or (iid.startswith(dl.Q_PREFIX) and d.get("state") == "open")
              or (iid.startswith(f"{FORM_MODULE}:form/") and (d.get("provenance") or {}).get("mode") == "derived"))
        if not ok:
            raise AscribeError(f"{iid} is not a candidate, its question, or a form a reading made: a reading writes "
                               "nothing else; nothing was written")
    checker = _checker()
    cand = h.led.copy()
    for d in items:
        cand.add(d)
    new = dl._new_errors(dl._errors(h.led, checker), dl._errors(cand, checker))
    if new:
        raise AscribeError("the candidates would not pass the holograph's checks: "
                           + "; ".join(str(e[3]) for e in new[:3]) + "; nothing was written")
    for d in items:
        h.led.add(d)
    h.save()
    return [d["id"] for d in items]


# ---------------------------------------------------------------------------
# Releases (section 13): written and read
# ---------------------------------------------------------------------------

def releases(folder: Any) -> list[dict]:
    """The holograph's releases, oldest first ([] when it has made none)."""
    vol = mc.load_volume(_root_of(folder))
    rel = vol.catalog.get("releases") if vol.manifest is not None else None
    return copy.deepcopy(rel) if isinstance(rel, list) else []


def release_record(*, epoch: str, as_: str, program: dict, trace: dict, sha256: str, items: Any,
                   at: Any = None, for_: dict | None = None) -> dict:
    """A release as section 13 writes it (refused in plain words when it is not in its shape)."""
    rec: dict = {"epoch": epoch, "as": as_, "program": {"name": program.get("name"), "sha256": program.get("sha256")},
                 "trace": {"run": trace.get("run"), "sha256": trace.get("sha256")}, "at": dl.now(at),
                 "sha256": sha256, "items": items if items == "all" else sorted(dict.fromkeys(items))}
    if for_ is not None:
        rec["for"] = {"path": for_.get("path"), "sha256": for_.get("sha256")}
    probs = release_problems(rec)
    if probs:
        raise AscribeError("the release is not in its shape: " + "; ".join(f"{f}: {m}" if f else m for f, m in probs))
    return rec


def append_release(folder: Any, record: dict) -> dict:
    """A release appended to the catalog's `releases:` (never rewriting one), before anything leaves. Refused when
    the record is not in its shape, or when it is a second isograph in one epoch (a holder who releases more often
    chooses a shorter epoch)."""
    probs = release_problems(record)
    if probs:
        raise AscribeError("the release is not in its shape: " + "; ".join(f"{f}: {m}" if f else m for f, m in probs))
    h = Holograph(folder)
    rel = h.led.catalog.get("releases", [])
    if not isinstance(rel, list):
        raise AscribeError("the catalog's releases is not a list; fix it by hand before releasing anything")
    if record["as"] == "isograph" and "for" not in record and any(
            isinstance(r, dict) and r.get("as") == "isograph" and "for" not in r and r.get("epoch") == record["epoch"]
            for r in rel):
        raise AscribeError(f"an isograph was released in {record['epoch']} already: one isograph per epoch (a "
                           "holder who releases more often chooses a shorter epoch)")
    h.led.catalog["releases"] = list(rel) + [copy.deepcopy(record)]
    h.save()
    return record


def released(folder: Any, *, sha256: str | None = None, path: str | None = None) -> dict | None:
    """The release recorded for what left, by the sha256 of its bytes, or for a text (`for: {path, sha256}`, a
    package's `graph.cosm`): what Thym's `released` check reads. None when nothing so released is recorded."""
    for r in reversed(releases(folder)):
        if not isinstance(r, dict):
            continue
        fr = r.get("for") if isinstance(r.get("for"), dict) else {}
        if sha256 is not None and str(sha256) in (str(r.get("sha256")), str(fr.get("sha256"))):
            return r
        if path is not None and fr.get("path") == path:
            return r
    return None


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Projections (section 14): the isograph, match tokens, the cryptograph, the isomorph
# ---------------------------------------------------------------------------

def canonical_json(doc: Any) -> bytes:
    """Keys sorted, no space between tokens, UTF-8 without a byte-order mark: the bytes a release's sha256 is over."""
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _decade(v: Any) -> str | None:
    if isinstance(v, _dt.datetime):
        return None
    if isinstance(v, _dt.date):
        return f"{v.year // 10 * 10}s"
    if isinstance(v, int) and not isinstance(v, bool) and 1000 <= v <= 9999:
        return f"{v // 10 * 10}s"
    if isinstance(v, str):
        if _is_date(v) or YEAR_RE.match(v):
            return f"{int(v[:4]) // 10 * 10}s"
        if DECADE_RE.match(v):
            return v
    return None


@dataclass
class _Eligible:
    id: str
    letter: str
    form: Any                      # a FEED word, or the sorted words of a polyform's forms
    form_ids: list
    data: dict


def _eligible(vol: mc.Volume) -> list[_Eligible]:
    """The nodes the isograph's rules let appear (section 14.1), in module order: of the ten kinds, `visibility:
    public`, `status` absent or active, provenance known at confidence 0.5 or more, and anchored to a form grounded
    in FEED with origin feed, or to a polyform of at most eight forms every one so grounded. `vol` is what the filter
    kept, so whatever it withheld is not here."""
    forms = {it.id: it for it in vol.items.values() if it.module == FORM_MODULE}

    def grounded(fid: Any) -> str | None:
        f = forms.get(fid) if isinstance(fid, str) else None
        feed = f.data.get("feed") if f is not None and f.kind == "form" else None
        if isinstance(feed, dict) and feed.get("origin") == "feed" and isinstance(feed.get("word"), str) \
                and feed["word"].strip():
            return feed["word"].strip()
        return None

    out = []
    for letter in CONTAINERS:
        for it in vol.items.values():
            if it.module != letter or it.kind != KINDS[letter]:
                continue
            d = it.data
            if d.get("visibility") != "public" or d.get("status") not in (None, "active"):
                continue
            prov = d.get("provenance")
            conf = prov.get("confidence") if isinstance(prov, dict) else None
            if not isinstance(prov, dict) or prov.get("state") not in (None, "known") or isinstance(conf, bool) \
                    or not isinstance(conf, (int, float)) or conf < KNOWN_AT:
                continue
            fid = d.get("form")
            if not isinstance(fid, str) or fid not in forms:
                continue
            target = forms[fid]
            if target.kind == "form":
                w = grounded(fid)
                if w:
                    out.append(_Eligible(it.id, letter, w, [fid], d))
            elif target.kind == "polyform":
                parts = target.data.get("forms")
                if isinstance(parts, list) and 0 < len(parts) <= MAX_POLYFORM_WORDS:
                    words = [grounded(x) for x in parts]
                    if all(words):
                        out.append(_Eligible(it.id, letter, sorted(set(words)), [fid] + [str(x) for x in parts], d))
    return out


def _entry(e: _Eligible) -> dict:
    d = e.data
    out: dict = {"kind": KINDS[e.letter], "form": e.form}
    if d.get("valence") in ("for", "against", "mixed"):
        out["valence"] = d["valence"]
    if strength_ok(d.get("strength")):
        out["strength"] = BANDS[d["strength"]]
    dec = _decade(d.get("when"))
    if dec:
        out["when"] = dec
    out["marking"] = STATED
    return out


def _entry_key(x: dict) -> tuple:
    f = x.get("form")
    return (CONTAINERS.index(next(L for L, k in KINDS.items() if k == x["kind"])),
            " ".join(f) if isinstance(f, list) else str(f), x.get("valence", ""), x.get("strength", ""),
            x.get("when", ""))


def _filtered_for_projection(folder: Any) -> Filtered:
    filt = private_filter(folder, use="projection")
    if filt.whole:
        raise AscribeError("a .ascribe-private marker sits beside the catalog: the whole holograph is withheld, and "
                           "nothing leaves")
    return filt


def _refuse_pii(vol: mc.Volume) -> None:
    errs = _pii_errors(vol)
    if errs:
        raise AscribeError(f"no-pii finds {len(errs)} thing{'s' if len(errs) != 1 else ''} that read like personal "
                           f"data in what would leave, and a release is refused while any stands; the first: "
                           f"{errs[0]}")


def isograph_doc(folder: Any, *, epoch: str, program: dict, trace: dict,
                 keep: Iterable[str] | None = None) -> tuple[dict, list[str]]:
    # `trace` is the run as the release will record it, `{run, sha256?}`: the isograph names only its `run`
    """The isograph of a holograph (`ascribe-isograph/0`, section 14.1) and the ids of the items that leave in it,
    computed by rules after the private filter: only the fields the schema names, a band for `strength`, a decade
    for `when`, a FEED word (or a polyform's words) for `form`, every entry `stated`, sorted by the module order then
    form, valence, strength and when, identical entries once, at most twenty of each kind. `keep` is the program's
    choice of nodes (it may keep more back, never add one). Refused while no-pii finds anything the filter keeps.
    Writes nothing."""
    if not (isinstance(epoch, str) and EPOCH_RE.match(epoch)):
        raise AscribeError(f"epoch {epoch!r} is a quarter (2026-Q4), a month (2026-11) or a week (2026-W45)")
    if not (isinstance(program, dict) and isinstance(program.get("name"), str) and _sha_ok(program.get("sha256"))):
        raise AscribeError("an isograph names the program that made it: {name, sha256}")
    if not (isinstance(trace, dict) and isinstance(trace.get("run"), str) and RUN_ID_RE.match(trace["run"])):
        raise AscribeError("an isograph names the run that made it by its id (2026-11-05-2046-2166)")
    filt = _filtered_for_projection(folder)
    with _Materialized(filt) as vol:
        if vol.refused is not None or vol.manifest is None or vol.minicosm != "ascribe":
            raise AscribeError(f"the holograph was refused: {vol.refused}")
        _refuse_pii(vol)
        cat = vol.catalog
        chosen = None if keep is None else set(keep)
        rows = [e for e in _eligible(vol) if chosen is None or e.id in chosen]
        hid = str(cat.get("id", ""))[len("ascribe/"):]
        handle = cat.get("handle")
    if not HID_RE.match(hid):
        raise AscribeError("the catalog's id is not ascribe/<hid> with a 26-character base32 hid")
    if not (isinstance(handle, str) and HANDLE_RE.match(handle)):
        raise AscribeError("the catalog's handle is not a pseudonymous handle (lowercase words joined by hyphens)")
    entries: list[dict] = []
    seen: set = set()
    items: set = set()
    per_kind: Counter = Counter()
    for e in sorted(rows, key=lambda e: _entry_key(_entry(e))):
        x = _entry(e)
        key = canonical_json(x)
        if per_kind[x["kind"]] >= PER_KIND and key not in seen:
            continue
        items.add(e.id)
        items.update(e.form_ids)
        if key in seen:
            continue
        seen.add(key)
        per_kind[x["kind"]] += 1
        entries.append(x)
    doc: dict = {"isograph": ISOGRAPH, "hid": hid, "handle": handle, "epoch": epoch,
                 "program": {"name": program["name"], "sha256": str(program["sha256"])},
                 "run": trace["run"], "self": entries}
    if cat.get("sample") is True:
        doc["sample"] = True
    if len(canonical_json(doc)) > MAX_ISOGRAPH_BYTES:
        raise AscribeError("the isograph would be larger than 64 kilobytes; keep more back")
    return doc, sorted(items)


def isograph_problems(doc: Any) -> list[str]:
    """Why a reader refuses an isograph (section 16.1.5), in plain words; [] when it reads it: a field section 14.1
    does not name, at the top or in an entry; the marking `verified` (or anything but `stated`); a field out of its
    shape; a number anywhere."""
    if not isinstance(doc, dict):
        return ["an isograph is one JSON object"]
    out = []
    extra = [k for k in doc if k not in ISOGRAPH_KEYS]
    if extra:
        out.append(f"fields ascribe-isograph/0 does not name: {', '.join(map(str, extra))}")
    for k in ("isograph", "hid", "handle", "epoch", "program", "run", "self"):
        if k not in doc:
            out.append(f"no {k}")
    if doc.get("isograph") != ISOGRAPH:
        out.append(f"isograph is {ISOGRAPH}")
    if "hid" in doc and not (isinstance(doc["hid"], str) and HID_RE.match(doc["hid"])):
        out.append("hid is 26 characters of lowercase base32")
    if "handle" in doc and not (isinstance(doc["handle"], str) and HANDLE_RE.match(doc["handle"])):
        out.append("handle is a pseudonymous handle, never a name")
    if "epoch" in doc and not (isinstance(doc["epoch"], str) and EPOCH_RE.match(doc["epoch"])):
        out.append("epoch is a quarter, a month or a week")
    if "sample" in doc and doc["sample"] is not True:
        out.append("sample is true, or absent")
    p = doc.get("program")
    if "program" in doc and not (isinstance(p, dict) and set(p) == {"name", "sha256"} and _sha_ok(p.get("sha256"))):
        out.append("program is {name, sha256}")
    if "run" in doc and not (isinstance(doc["run"], str) and RUN_ID_RE.match(doc["run"])):
        out.append("run is the id of the run that made it")
    rows = doc.get("self")
    if "self" in doc and not isinstance(rows, list):
        out.append("self is a list")
        rows = []
    for i, x in enumerate(rows or []):
        if not isinstance(x, dict):
            out.append(f"self[{i}] is an object")
            continue
        bad = [k for k in x if k not in ISOGRAPH_SELF_KEYS]
        if bad:
            out.append(f"self[{i}]: fields ascribe-isograph/0 does not name: {', '.join(map(str, bad))}")
        if x.get("marking") == "verified":
            out.append(f"self[{i}] is marked verified: verified is reserved for what a registry attests, and an "
                       "isograph made by its holder marks everything stated")
        elif x.get("marking") != STATED:
            out.append(f"self[{i}]: marking is stated")
        if x.get("kind") not in KINDS.values():
            out.append(f"self[{i}]: kind is one of the ten")
        f = x.get("form")
        if not (isinstance(f, str) and f.strip()) and not (isinstance(f, list) and 0 < len(f) <= MAX_POLYFORM_WORDS
                                                          and all(isinstance(w, str) and w for w in f)
                                                          and f == sorted(f)):
            out.append(f"self[{i}]: form is a FEED word, or the sorted words of a polyform's forms (at most eight)")
        if "valence" in x and x["valence"] not in ("for", "against", "mixed"):
            out.append(f"self[{i}]: valence is for, against or mixed")
        if "strength" in x and x["strength"] not in ("slight", "moderate", "strong"):
            out.append(f"self[{i}]: strength leaves only as its band")
        if "when" in x and not (isinstance(x["when"], str) and DECADE_RE.match(x["when"])):
            out.append(f"self[{i}]: when leaves only as its decade")
    for path, v in _leaves(doc):
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out.append(f"{path} holds a number; an isograph says no number of anything")
    return out


def _leaves(o: Any, path: str = "") -> Iterator[tuple[str, Any]]:
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _leaves(v, f"{path}.{k}" if path else str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _leaves(v, f"{path}[{i}]")
    else:
        yield path, o


def _refuse_pii_text(text: str, what: str) -> None:
    found = pii_findings(text)
    if found:
        kind, s = found[0]
        raise AscribeError(f"{what} reads like personal data ({_quote(s)}, {PII_WHAT[kind]}); a release is refused "
                           "while it stands")


def _refuse_pii_doc(doc: Any, what: str) -> None:
    """no-pii over a projection itself, at the severity of an error: every string and key of it but its digests."""
    for path, v in _leaves(doc):
        if path.rsplit(".", 1)[-1] == "sha256":
            continue
        if isinstance(v, str):
            _refuse_pii_text(v, f"{what}'s {path}")
    for _p, k in _keys(doc):
        if IDENTIFYING_FIELDS.get(k.casefold().replace("_", "-")):
            raise AscribeError(f"{what} has a field for personal data ({k}); a release is refused while it stands")


def project_isograph(folder: Any, *, epoch: str, program: dict, trace: dict, keep: Iterable[str] | None = None,
                     at: Any = None) -> tuple[bytes, dict]:
    """`project h as isograph`, its engine side (section 14.1): the filter first, no-pii an error over what it keeps
    and over the isograph itself, the isograph by rules, refused if a reader would refuse it, and the release
    (`as: isograph`, its sha256 over the canonical bytes) recorded in the holograph before the bytes are given.
    `trace` is `{run, sha256}`. Returns (the canonical JSON bytes, the release)."""
    doc, items = isograph_doc(folder, epoch=epoch, program=program, trace=trace, keep=keep)
    probs = isograph_problems(doc)
    if probs:
        raise AscribeError("the isograph would not read: " + "; ".join(probs))
    data = canonical_json(doc)
    _refuse_pii_doc(doc, "the isograph")
    if not items:
        raise AscribeError("no node of this holograph may appear in an isograph (public, known at 0.5 or more, "
                           "anchored to a FEED word): nothing to release")
    record = release_record(epoch=epoch, as_="isograph", program=program, trace=trace, sha256=sha256_hex(data),
                            items=items, at=at)
    append_release(folder, record)
    return data, record


def token_key() -> bytes:
    """A key made for one cryptograph's match tokens, never its package key; the holder keeps it, nothing records it."""
    return secrets.token_bytes(32)


def match_token(key: bytes, about: str, value: str) -> str:
    """One match token: the lowercase hex HMAC-SHA256 of `about`, a line feed and the value (section 14.3)."""
    return hmac.new(key, f"{about}\n{value}".encode("utf-8"), hashlib.sha256).hexdigest()


def make_tokens(folder: Any, chosen: Iterable[dict], *, of: str, epoch: str, program: dict, trace: dict,
                key: bytes | None = None, at: Any = None) -> tuple[bytes, bytes, dict]:
    """The holder's consented match tokens (`ascribe-tokens/0`, section 14.3) for the forms they choose, and the
    release (`as: tokens`) recorded before the list is given. `chosen` is `[{about, form}]`: `about` one of the ten
    kinds (a token per node of that kind anchored to the form, its value the form's slug and, when the node carries
    a valence, a space and the valence word) or `form` (the form's slug); `form` a form's slug or id. A token is made
    only for a form grounded in FEED with origin feed and a node the isograph's rules let appear; nothing is a token
    by default. `of` is the cryptograph's hid. Returns (the list's canonical JSON, the key, the release); serving
    tokens is reserved for a later edition."""
    if not (isinstance(of, str) and HID_RE.match(of)):
        raise AscribeError("tokens name the cryptograph they are of, by its 26-character hid")
    if not (isinstance(epoch, str) and EPOCH_RE.match(epoch)):
        raise AscribeError(f"epoch {epoch!r} is a quarter, a month or a week")
    key = key or token_key()
    filt = _filtered_for_projection(folder)
    with _Materialized(filt) as vol:
        _refuse_pii(vol)
        rows = _eligible(vol)
    entries: dict[str, dict] = {}
    items: set = set()
    for c in chosen:
        about = c.get("about") if isinstance(c, dict) else None
        form = str(c.get("form") or "") if isinstance(c, dict) else ""
        fid = form if form.startswith(f"{FORM_MODULE}:form/") else f"{FORM_MODULE}:form/{form}"
        slug = fid.split("/", 1)[1]
        if about not in KINDS.values() and about != "form":
            raise AscribeError(f"a token is about one of the ten kinds or a form, not {about!r}")
        hits = [e for e in rows if e.form_ids == [fid] and (about == "form" or KINDS[e.letter] == about)]
        if not hits:
            raise AscribeError(f"no token for {about} {slug}: a token is made only for a form grounded in FEED and a "
                               "node an isograph may show")
        for e in hits:
            value = slug if about == "form" else (slug + (f" {e.data['valence']}" if e.data.get("valence")
                                                          in ("for", "against", "mixed") else ""))
            tok = match_token(key, about, value)
            entries[tok] = {"about": about, "token": tok}
            items.add(e.id)
            items.add(fid)
    if not entries:
        raise AscribeError("the holder chose no form: nothing is made a token by default")
    doc = {"tokens": TOKENS, "of": of, "epoch": epoch, "entries": [entries[t] for t in sorted(entries)]}
    data = canonical_json(doc)
    record = release_record(epoch=epoch, as_="tokens", program=program, trace=trace, sha256=sha256_hex(data),
                            items=sorted(items), at=at)
    append_release(folder, record)
    return data, key, record


def _known_only(files: dict) -> dict:
    """Kept files without candidates and nodes not known at confidence 0.5 or more (section 16.2.6: never in a
    projection, a package or an ingest); a file that held one is written out again without it."""
    out = {}
    for rel, raw in files.items():
        if not rel.endswith(".cosm"):
            out[rel] = raw
            continue
        data = mc.yaml_load(raw.decode("utf-8-sig"))
        nodes = data.get("nodes") if isinstance(data, dict) else None
        if not isinstance(nodes, list):
            out[rel] = raw
            continue

        def known(d: Any) -> bool:
            iid = str(d.get("id", "")) if isinstance(d, dict) else ""
            if iid.split(":", 1)[0] not in KINDS:
                return True
            prov = d.get("provenance")
            conf = prov.get("confidence") if isinstance(prov, dict) else None
            return isinstance(prov, dict) and prov.get("state") in (None, "known") and not isinstance(conf, bool) \
                and isinstance(conf, (int, float)) and conf >= KNOWN_AT
        kept = [d for d in nodes if known(d)]
        out[rel] = raw if len(kept) == len(nodes) else mc.dump(
            {**data, "nodes": kept} if rel == CATALOG else {"nodes": kept}).encode("utf-8")
    return out


CRYPTOGRAPH_NOTICE = "A cryptograph: a person's encrypted share, opened only with the key its holder handed on."


def cryptograph(folder: Any, *, epoch: str, program: dict, trace: dict, projection: bytes | None = None,
                program_text: str | None = None, trace_text: str | None = None, items: Iterable[str] | None = None,
                at: Any = None, aead: str | None = None) -> tuple[bytes, str, dict]:
    """A cryptograph (section 14.2): a Thym package in its encrypted form (`enough.thym.vault.seal`, Comprise's
    `comprise-bundle/0`, a fresh data key, a random hid that is never the holograph's), of the whole holograph (one
    `holograph` row per file the filter keeps, module D left out, and no candidate or node not known at 0.5) or of a
    projection (`projection.json`, an `ascribe-isograph/0` document, `program.thym`, `trace.cosm`; `items` the ids it
    released). The release (`as: cryptograph`, its sha256 over the sealed file; `items: all` for the whole
    holograph) is recorded before it is given. Returns (the sealed file's bytes, the key, shown once and stored
    nowhere, the release)."""
    from .thym import vault
    if projection is None:
        filt = private_filter(folder, use="package")
        if filt.whole:
            raise AscribeError("a .ascribe-private marker sits beside the catalog: nothing leaves")
        with _Materialized(filt) as vol:
            _refuse_pii(vol)
        files = _known_only(filt.files)
        rows = []
        for rel, raw in files.items():
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                raise AscribeError(f"{rel} is not text; a cryptograph carries the holograph's text files") from None
            rows.append({"path": rel, "sha256": sha256_hex(raw), "role": "holograph", "text": text})
        released_items: Any = "all"
    else:
        try:
            doc = json.loads(projection.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise AscribeError("the projection is not an ascribe-isograph/0 document") from None
        probs = isograph_problems(doc)
        if probs:
            raise AscribeError("the projection would not read: " + "; ".join(probs))
        if not (isinstance(program_text, str) and isinstance(trace_text, str)):
            raise AscribeError("a projection's cryptograph carries its program and its cleaned trace")
        released_items = sorted(items or [])
        if not released_items:
            raise AscribeError("a projection's cryptograph names the items its isograph released")
        rows = [{"path": p, "sha256": sha256_hex(t.encode("utf-8")), "role": r, "text": t}
                for p, r, t in (("projection.json", "projection", projection.decode("utf-8")),
                                ("program.thym", "program", program_text), ("trace.cosm", "trace", trace_text))]
    catalog = {"oes": "thym/1", "kind": "package", "id": "thym/cryptograph", "name": "a cryptograph",
               "contents": rows,
               "made": {"program": {"name": program.get("name"), "sha256": program.get("sha256")},
                        "trace": {"run": trace.get("run")}, "by": "thym 0"},
               "notice": CRYPTOGRAPH_NOTICE, "nodes": []}
    single = mc.dump(catalog).encode("utf-8")
    sealed, key = vault.seal(single, path="cryptograph.package.cosm", slug="cryptograph", aead=aead)
    record = release_record(epoch=epoch, as_="cryptograph", program=program, trace=trace, sha256=sha256_hex(sealed),
                            items=released_items, at=at)
    append_release(folder, record)
    return sealed, key, record


def isomorph(folder: Any, morph_file: str, morph_id: str, *, epoch: str, program: dict, trace: dict,
             at: Any = None) -> tuple[bytes, dict]:
    """An isomorph (section 14.5): the holder's morph `morph_id` from a morph volume the catalog's `morphs:` names,
    kept beside the holograph's folder, marked `shared`, without its `evidence` and `derived.from` (which quote and
    point to the holder's texts), as a `thym/1` volume of that one morph; the release (`as: isomorph`, `items:
    [M:morph/<slug>]`) recorded before it is given. Returns (the volume's bytes, the release)."""
    root = _root_of(folder)
    vol = mc.load_volume(root)
    named = vol.catalog.get("morphs") if isinstance(vol.catalog.get("morphs"), list) else []
    if not (isinstance(morph_file, str) and MORPH_FILE_RE.match(morph_file)) or morph_file not in named:
        raise AscribeError(f"{morph_file!r} is not a morph volume the catalog's morphs names")
    if not MORPH_ID_RE.match(str(morph_id)):
        raise AscribeError(f"{morph_id!r} is not a morph's id (M:morph/<slug>)")
    path = root.parent / morph_file
    if not path.is_file():
        raise AscribeError(f"{morph_file} is not beside the holograph's folder")
    data = mc.yaml_load(mc.read_text(path))
    nodes = data.get("nodes") if isinstance(data, dict) else None
    item = next((copy.deepcopy(n) for n in nodes or [] if isinstance(n, dict) and n.get("id") == morph_id), None)
    if item is None:
        raise AscribeError(f"{morph_file} holds no {morph_id}")
    item.pop("evidence", None)
    if isinstance(item.get("derived"), dict):
        item["derived"].pop("from", None)
        if not item["derived"]:
            item.pop("derived")
    item["shared"] = True
    out = {k: copy.deepcopy(v) for k, v in data.items() if k != "nodes"}
    out["nodes"] = [item]
    text = mc.dump(out)
    _refuse_pii_text(text, "the isomorph")
    raw = text.encode("utf-8")
    record = release_record(epoch=epoch, as_="isomorph", program=program, trace=trace, sha256=sha256_hex(raw),
                            items=[morph_id], at=at)
    append_release(folder, record)
    return raw, record


# ---------------------------------------------------------------------------
# The engine Thym's moves reach as ctx.engines["ascribe"] (enough/thym/moves/ascribe.py)
# ---------------------------------------------------------------------------

def thym_forms(holograph: dict) -> dict:
    """What a reading may see of the holograph it proposes for, after the filter (as an ingest: no marker's files,
    no restricted item, no D): its forms and polyforms (id, name, FEED word) and its pseudonyms, as YAML text."""
    filt = private_filter(holograph["path"], use="ingest")
    if filt.whole:
        return {"text": "forms: []\n", "whole": True}
    with _Materialized(filt) as vol:
        rows = [{"id": it.id, "name": it.data.get("name"),
                 **({"word": it.data["feed"]["word"]} if isinstance(it.data.get("feed"), dict)
                    and isinstance(it.data["feed"].get("word"), str) else {})}
                for it in vol.items.values() if it.module == FORM_MODULE and it.kind in ANCHOR_KINDS]
        pseu = vol.catalog.get("pseudonyms") if isinstance(vol.catalog.get("pseudonyms"), list) else []
    return {"text": mc.dump({"forms": rows, "pseudonyms": [p for p in pseu if isinstance(p, str)]}), "whole": False}


def thym_propose(holograph: dict, proposals: str, *, text: str, sha256: str, run: str | None = None,
                 at: Any = None, made: dict | None = None) -> dict:
    """The move `propose`'s engine call: the model's proposals (YAML text: a list, or `{candidates: [...]}`) as
    candidates and their questions, checked, writing nothing; `made` is stamped on each candidate. `{items: <YAML
    text, nodes: [...]>, nodes: [[index, candidate id], ...], refused: [{index, why}]}`."""
    data = mc.yaml_load(proposals) if isinstance(proposals, str) else proposals
    if isinstance(data, dict):
        data = data.get("candidates")
    if not isinstance(data, list):
        raise AscribeError("the proposals are a list of candidates")
    items, refused = candidates(holograph["path"], data, text=text, sha256=sha256, run=run, at=at, made=made)
    kept = [i for i in range(len(data)) if i not in {j for j, _ in refused}]
    nodes = [d["id"] for d in items if _is_candidate(d)]
    return {"items": dl.dump_text({"nodes": items}), "nodes": [[i, n] for i, n in zip(kept, nodes)],
            "refused": [{"index": i, "why": w} for i, w in refused]}


def thym_isograph(holograph: dict, *, epoch: str, program: dict, trace: dict, keep: list | None = None) -> dict:
    """The isograph of a holograph, for the `as isograph` arm of `project`: `{json: <canonical JSON text>, items:
    [...]}`. Writes nothing: the host records the release when the run lands (`append_release`)."""
    doc, items = isograph_doc(holograph["path"], epoch=epoch, program=program, trace=trace, keep=keep)
    probs = isograph_problems(doc)
    if probs:
        raise AscribeError("the isograph would not read: " + "; ".join(probs))
    data = canonical_json(doc)
    _refuse_pii_doc(doc, "the isograph")
    return {"json": data.decode("utf-8"), "items": items}


def thym_isograph_problems(isograph_json: str) -> list[str]:
    """Why a reader would refuse this isograph (`isograph_problems`), for the checks of `project … as isograph`: the
    isograph as its canonical JSON text in, plain words out ([] when it reads)."""
    try:
        doc = json.loads(isograph_json)
    except ValueError:
        return ["an isograph is one JSON object"]
    return isograph_problems(doc)


THYM_FUNCTIONS = ("thym_forms", "thym_propose", "thym_isograph", "thym_isograph_problems")


def thym_engine() -> Any:
    """The `ascribe` engine Thym's moves reach (`ctx.engines["ascribe"]`): `thym_forms`, `thym_propose` and
    `thym_isograph`, every argument and answer plain data (paths, text, lists, strings)."""
    from types import SimpleNamespace
    return SimpleNamespace(**{n: globals()[n] for n in THYM_FUNCTIONS})


# ---------------------------------------------------------------------------
# CLI: python -m enough.ascribe lint <folder>
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m enough.ascribe",
                                 description="Ascribe: check a person's holograph (oes: ascribe/1).")
    ap.add_argument("command", choices=["lint"])
    ap.add_argument("path", help="a holograph folder, or its holograph.cosm")
    ap.add_argument("--json", action="store_true", help="JSON output")
    args = ap.parse_args(argv)
    rep = lint_holograph(args.path)
    vol = rep.volume
    if args.json:
        print(json.dumps(rep.to_dict(), ensure_ascii=False, indent=2))
    else:
        for p in rep.problems():
            print(f"{p.severity:7} {p}")
        print(f"{vol.oes or 'refused'}: {len(vol.items)} items, {len(rep.errors)} errors, {len(rep.warnings)} "
              f"warnings, {len(rep.notes)} notes, {len(rep.pending)} open questions")
    return 0 if rep.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
