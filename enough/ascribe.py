"""Ascribe: a person's holograph, checked (`oes: ascribe/1`, defaults/cosm/manifests/ascribe.manifest.cosm).

A holograph is a self described well enough that no name is needed: a folder whose catalog, `holograph.cosm`, is
the self, with ten module folders of nodes beside it (A affinity, B belief, C concern, E experience, I interest,
O opinion, Q quale, S skill, U understanding, Y yearning) and `F/` for the forms, polyforms and relations the nodes
anchor to. The reader, `enough/macrocosm.py`, loads and checks it like any volume; this module runs Ascribe's own
checks beside the generic ones, the way `docoes.lint_doc` does for a doc volume, in one report:

- `form-anchored` (error): every node of the ten kinds names a form or a polyform that exists.
- `relation-declared` (error): every typed link's rel is a starter word or a relation the holograph declares.
- `when-shape` (error): a `when` is a date, a year or an era word.
- `strength-range` (error): a `strength` is a whole number from 1 to 5.
- `no-pii` (warning, never an error: the owner's ruling): what reads like personal data, anywhere in the volume,
  comments included, and capitalised pairs in prose fields that read as personal names.
- `private-marker` (note): what a `.ascribe-private` marker would keep out of ingest and transfer.

It also holds two generic checks to what the reader cannot read from the manifest: `id-module` to the module
folders (a node is written in its own module's folder, or in the catalog's `nodes:`), and `catalog-key` to the hid
and the handle.

It reads only the folder it is given and writes nothing. No server route, viewer or tool calls it in 0.5.0.

    python -m enough.ascribe lint <folder> [--json]

Standalone like the reader: the standard library, PyYAML (through the reader) and `enough.macrocosm`.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
from pathlib import Path
from typing import Any, Iterable, Iterator

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
ASCRIBE_CHECKS = ("form-anchored", "relation-declared", "when-shape", "strength-range", "no-pii", "private-marker")
ASCRIBE_SEVERITY = {"form-anchored": "error", "relation-declared": "error", "when-shape": "error",
                    "strength-range": "error", "no-pii": "warning", "private-marker": "note"}
ADVICE = "people appear by role or by a pseudonym you declare"

HID_RE = re.compile(r"^[a-z2-7]{26}$")                     # Connect's hid: 26 characters of lowercase base32
HANDLE_RE = re.compile(r"^[a-z]+(?:-[a-z]+)*$")            # lowercase words joined by hyphens
YEAR_RE = re.compile(r"^[0-9]{4}$")
ERA_RE = re.compile(r"^(?:[0-9]{3}0s|[a-z]+(?:-[a-z]+)*)$")  # 2010s, childhood, secondary-school


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
    """(the marker's path, what ingest and transfer would leave out beside it) for every marker below `root`,
    paths relative to `root`, folders ending in `/`. Reads the folder; drops nothing."""
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
    """Ascribe's own checks over one loaded holograph, adding to the generic report."""

    def __init__(self, vol: mc.Volume, rep: mc.Report):
        self.v, self.rep, self.m = vol, rep, vol.manifest
        c = self.m._block("checks")
        override = c.get("severity") if isinstance(c.get("severity"), dict) else {}
        self.sev = dict(ASCRIBE_SEVERITY, **{str(k): str(v) for k, v in override.items() if str(k) in ASCRIBE_CHECKS})
        self.sev["no-pii"] = "note" if self.sev.get("no-pii") == "note" else "warning"     # never an error
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
        self.no_pii()
        self.private_marker()

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
        for rel in self.v.files:
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
            self.add("private-marker", None, f"ingest and transfer would leave out {what}{count}", file=mk)


def lint_holograph(path, *, registry: mc.Registry | None = None) -> mc.Report:
    """The generic checks (`macrocosm.lint`) and Ascribe's own, in one report, for a holograph folder (or its
    `holograph.cosm`, or a volume already loaded). A volume that is not `ascribe/1` gets the generic report alone."""
    vol = path if isinstance(path, mc.Volume) else mc.load_volume(path, registry)
    rep = mc.lint(vol)
    if vol.manifest is None or vol.minicosm != "ascribe":
        return rep
    rep.checks = rep.checks + [c for c in ASCRIBE_CHECKS if c not in rep.checks]
    _Own(vol, rep).run()
    return rep


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
