"""The languages the builder knows, one entry each: the one seam for everything it does by language (0.8 pin 3).

A fabulac's builder reads a source language by its syntax, surveys it by rules, grounds it in its language's ground
catalogue, decompiles and compiles it by the programs named here, and may run its entailment in the sandbox. Another
language can be weighed and entailed into without any of that: the outside runner builds and judges it, and enough
reads none of it (MacroCOSM OES 18.4.9; Thym 20.10). Each of those choices is a field of one `Language` below, and
nothing else in enough asks `if language == …`: a language added later (the waiting entry `fabulac-h5`) is an entry
here, not a branch elsewhere.

| field | means |
|---|---|
| `reads` | the syntax engine (`enough.repo_engine`) reads its files: an outline, a parse, the survey's rules |
| `parses` | the `parses` check holds for it (a cshort in it is parsed by the syntax engine) |
| `runs` | enough may run an authored entailment in it, in the sandbox only (Thym 20.12) |
| `target` | it may be weighed (`weigh f in <language>`) and entailed into (`entail f as code in <language>`) |
| `ground` | its ground catalogue, relative to the repository (`defaults/cosm/ground/<language>.ground.cosm`) |
| `decompile`, `compile` | the shipped programs (`defaults/thym/`) that build a fabulac of it and entail one into it |
| `shelf` | its shelf in the language library (cosmoes-site `library/<shelf>/`, `library.json`) |
| `runtime` | the package name its runtime's `C:dependency` carries (`C:dependency/<runtime>`) |
| `names` | the words a text uses when it names the language, its runtime or its standard library (`stands-alone`) |

Standalone: the standard library, and `enough.macrocosm` only to read a ground catalogue.
"""
from __future__ import annotations

import functools
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: The language the builder reads today, the only one with `reads`: what a survey of a folder is taken to be.
DEFAULT = "python"

ROOT = Path(__file__).resolve().parent.parent
GROUND_FORMAT = "ground/1"

# The names a text uses when it names Python, its runtime or its standard library: the experiment's own list (x0,
# a4lib.NAMES), moved here from enough/transconception.py, which reads it through `source_names`.
_PYTHON_NAMES = re.compile(
    r"\b(Python|python3?|CPython|PyPy|argparse|ast\b|ast\.\w+|fnmatch\w*|tomllib|tomli|pathlib|rglob|tokenize|"
    r"pkgutil|sys\.\w+|os\.path\.?\w*|IntEnum|NamedTuple|namedtuple|dataclass\w*|typing|html\.entities|html5|"
    r"xml\.etree|ElementTree|lxml|etree|codecs|collections|functools|logging|re\.\w+|regular expression|"
    r"literal_eval|splitlines|isspace|strip\(\)|str\(\)|int\(\)|chr\(\)|sorted\(\)|any\(\)|generator|yield|"
    r"pytest|traceback|TypeError|ValueError|KeyError|ImportError|UnicodeDecodeError|SyntaxError|OSError|"
    r"dict(?:ionary)?|tuple|bytes|glob)\b")


@dataclass(frozen=True)
class Language:
    """One language the builder knows (see the module's table)."""
    name: str
    title: str
    suffixes: tuple[str, ...]
    reads: bool = False
    parses: bool = False
    runs: bool = False
    target: bool = True
    ground: str | None = None
    decompile: str | None = None
    compile: str | None = None
    shelf: str | None = None
    runtime: str | None = None
    names: re.Pattern | None = field(default=None, compare=False)

    def owns(self, path: str) -> bool:
        """Whether a file of this name is written in this language, by its suffix."""
        base = str(path).rsplit("/", 1)[-1]
        return "." in base and base.rsplit(".", 1)[1].lower() in self.suffixes

    @property
    def ground_path(self) -> Path | None:
        return ROOT / self.ground if self.ground else None


LANGUAGES: dict[str, Language] = {
    "python": Language(
        name="python", title="Python", suffixes=("py", "pyi"), reads=True, parses=True, runs=True, target=True,
        ground="defaults/cosm/ground/python.ground.cosm", decompile="decompile-python.thym",
        compile="compile-python.thym", shelf="python", runtime="python", names=_PYTHON_NAMES),
    "go": Language(name="go", title="Go", suffixes=("go",), target=True, shelf="go", runtime="go"),
    "rust": Language(name="rust", title="Rust", suffixes=("rs",), target=True, shelf="rust", runtime="rust"),
}


def get(name: Any) -> Language | None:
    """The entry for a language name (any case), or None for a language the builder does not know."""
    return LANGUAGES.get(str(name or "").strip().lower())


def require(name: Any) -> Language:
    """The entry for a language name; a KeyError in plain words for one the builder does not know."""
    lang = get(name)
    if lang is None:
        raise KeyError(f"{name!r} is no language this build knows ({', '.join(sorted(LANGUAGES))})")
    return lang


def of_path(path: str) -> Language | None:
    """The language a file is written in, by its suffix, among the registry's; None for any other file."""
    return next((lang for lang in LANGUAGES.values() if lang.owns(path)), None)


def suffixes() -> dict[str, str]:
    """`{suffix: language}` for every suffix of every entry (`py` → `python`, `rs` → `rust`)."""
    return {s: lang.name for lang in LANGUAGES.values() for s in lang.suffixes}


def reads(name: Any) -> bool:
    """Whether the syntax engine reads the language (Python only in this build)."""
    lang = get(name)
    return bool(lang and lang.reads)


def parses(name: Any) -> bool:
    lang = get(name)
    return bool(lang and lang.parses)


def runs(name: Any) -> bool:
    lang = get(name)
    return bool(lang and lang.runs)


def reading() -> list[str]:
    """The languages the syntax engine reads, in the registry's order."""
    return [n for n, lang in LANGUAGES.items() if lang.reads]


def targets() -> list[str]:
    """The languages that may be weighed and entailed into."""
    return [n for n, lang in LANGUAGES.items() if lang.target]


def source_names(name: Any) -> re.Pattern | None:
    """The words that name a source language, its runtime or its standard library (`stands-alone`), or None."""
    lang = get(name)
    return lang.names if lang else None


def program(name: Any, which: str) -> str:
    """The shipped program that decompiles (`which="decompile"`) or compiles (`"compile"`) a language; a KeyError
    in plain words for a language that has none."""
    lang = require(name)
    got = getattr(lang, which, None) if which in ("decompile", "compile") else None
    if not got:
        raise KeyError(f"no program {which}s {lang.title} in this build")
    return got


# ---------------------------------------------------------------------------
# The ground catalogue (MacroCOSM OES 18.4.9, "The ground")
# ---------------------------------------------------------------------------

ENTRY_KEYS = ("id", "kind", "on", "of", "name", "gives", "example", "names", "shows-as", "usual", "stated",
              "about", "if-false", "carries", "note", "from")
ENTRY_REQUIRED = ("id", "on", "name", "gives", "example", "shows-as", "stated")
ON = ("language", "runtime", "platform", "dependency")
KINDS = ("reliance", "assumption")
USUAL = ("kept", "alike", "free", "kept-wrong", "changed")
#: The conditions a `shows-as` alternative may name (see `enough.thym.moves.transconceive`, `shown`).
CONDITIONS = ("call", "method", "kw", "without", "arg0", "mode", "attr", "annotation", "form", "decorator", "base",
              "import", "handler", "string", "entry-point", "declared")
TEXT_KEYS = ("shelf", "text", "version", "name", "publisher", "what", "form", "lane", "aboard", "licence", "from",
             "cited-as", "cited-version")
PIN_KEYS = ("shelf", "text", "version", "name", "publisher", "what", "lane", "aboard", "licence", "from", "release",
            "swhid", "digest")
_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_AT = re.compile(r"^[a-z0-9_./-]+\.html#[A-Za-z0-9_.:-]+$")


@functools.lru_cache(maxsize=8)
def _load(path: str) -> dict:
    from enough import macrocosm as mc
    data = mc.yaml_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a ground catalogue")
    return data


def catalogue(name: Any, *, path: Path | None = None) -> dict:
    """A language's ground catalogue, read once per process: `{ground, language, version, texts, pins, entries}`.
    A KeyError in plain words for a language that has none."""
    lang = require(name)
    p = path or lang.ground_path
    if p is None:
        raise KeyError(f"{lang.title} has no ground catalogue in this build: it can be entailed into, not grounded")
    return _load(str(p))


def entries(name: Any) -> list[dict]:
    """The catalogue's entries, in its order."""
    return [e for e in catalogue(name).get("entries") or [] if isinstance(e, dict)]


def lint_catalogue(doc: dict) -> list[str]:
    """What is wrong with a ground catalogue, one line each; an empty list when nothing is. Each entry carries what
    `ground-given` and `ground-cited` ask of the reliance copied from it (`gives`, `example`, `stated`), a rule the
    survey can apply (`shows-as`, each condition a known one), and `stated` in the shape the fabulac stores."""
    out: list[str] = []
    if doc.get("ground") != GROUND_FORMAT:
        out.append(f"the head says ground: {doc.get('ground')!r}, not {GROUND_FORMAT}")
    if not get(doc.get("language")):
        out.append(f"the head names {doc.get('language')!r}, no language of the registry")
    for k, keys in (("texts", TEXT_KEYS), ("pins", PIN_KEYS)):
        rows = doc.get(k)
        if not isinstance(rows, list) or not rows:
            out.append(f"the head carries no {k}")
            continue
        for i, r in enumerate(rows):
            extra = [x for x in (r or {}) if x not in keys] if isinstance(r, dict) else ["(not a mapping)"]
            if extra:
                out.append(f"{k}[{i}]: fields the head does not name: {', '.join(map(str, extra))}")
    cited = {(t.get("cited-as"), str(t.get("cited-version"))) for t in doc.get("texts") or [] if isinstance(t, dict)}
    seen: set[str] = set()
    for i, e in enumerate(doc.get("entries") or []):
        where = f"entries[{i}]"
        if not isinstance(e, dict):
            out.append(f"{where}: not a mapping")
            continue
        eid = str(e.get("id") or "")
        where = f"entry {eid or i}"
        if not _ID.match(eid):
            out.append(f"{where}: an id is lowercase words joined by hyphens")
        if eid in seen:
            out.append(f"{where}: the id is given twice")
        seen.add(eid)
        for k in ENTRY_REQUIRED:
            if e.get(k) in (None, "", [], {}):
                out.append(f"{where}: carries no {k}")
        extra = [k for k in e if k not in ENTRY_KEYS]
        if extra:
            out.append(f"{where}: fields an entry does not name: {', '.join(extra)}")
        if e.get("on") not in ON:
            out.append(f"{where}: on is one of {', '.join(ON)}")
        if e.get("kind", "reliance") not in KINDS:
            out.append(f"{where}: kind is one of {', '.join(KINDS)}")
        if e.get("usual") is not None and e.get("usual") not in USUAL:
            out.append(f"{where}: usual is one of {', '.join(USUAL)}")
        if e.get("kind") == "assumption" and not e.get("about"):
            out.append(f"{where}: an assumption says what it is about")
        for alt in e.get("shows-as") or []:
            if not isinstance(alt, dict) or not alt:
                out.append(f"{where}: each shows-as is a mapping of conditions")
                continue
            bad = [k for k in alt if k not in CONDITIONS]
            if bad:
                out.append(f"{where}: shows-as names no condition {', '.join(bad)}")
        for j, rx in enumerate(e.get("names") or []):
            try:
                re.compile(str(rx))
            except re.error as err:
                out.append(f"{where}: names[{j}] is no pattern ({err})")
        st = e.get("stated")
        if not isinstance(st, list) or not st:
            out.append(f"{where}: stated is a list of {{in, version, at, digest}} and {{nowhere: text}}")
            continue
        for j, s in enumerate(st):
            if isinstance(s, dict) and set(s) == {"nowhere"}:
                if not (isinstance(s["nowhere"], str) and s["nowhere"].strip()):
                    out.append(f"{where}: stated[{j}] says what no text states")
                continue
            if not isinstance(s, dict) or set(s) != {"in", "version", "at", "digest"}:
                out.append(f"{where}: stated[{j}] is {{in, version, at, digest}} or {{nowhere: text}}")
                continue
            if not _AT.match(str(s["at"])):
                out.append(f"{where}: stated[{j}].at is a page and an anchor (library/json.html#json.dumps)")
            if not re.fullmatch(r"[0-9a-f]{12}", str(s["digest"])):
                out.append(f"{where}: stated[{j}].digest is the first twelve hex digits of the page's sha256")
            if (s["in"], str(s["version"])) not in cited:
                out.append(f"{where}: stated[{j}] cites {s['in']} {s['version']}, a text the head does not carry")
    return out


def catalogue_agrees(doc: dict, library: dict) -> list[str]:
    """Where a catalogue's head disagrees with the language library's registry (cosmoes-site `library/library.json`),
    one line each. A text or pin the registry holds must say what the registry says, field by field; a text the
    registry does not hold yet (fetched by the owner later) must say `aboard: false`, and a pin the registry does not
    hold is a disagreement."""
    out: list[str] = []
    rows = {(str(r.get("shelf")), str(r.get("text")), str(r.get("version"))): r
            for r in (library.get("texts") or []) if isinstance(r, dict)}
    for k, keys in (("texts", TEXT_KEYS), ("pins", PIN_KEYS)):
        for r in doc.get(k) or []:
            key = (str(r.get("shelf")), str(r.get("text")), str(r.get("version")))
            lib = rows.get(key)
            if lib is None:
                if k == "pins":
                    out.append(f"pins: {'/'.join(key)} is not pinned in library.json")
                elif r.get("aboard") is not False:
                    out.append(f"texts: {'/'.join(key)} is not in library.json yet, so it is aboard: false")
                continue
            for f in keys:
                if f in ("cited-as", "cited-version"):
                    continue
                if f in lib and f in r and lib[f] != r[f]:
                    out.append(f"{k}: {'/'.join(key)} says {f} {r[f]!r}, library.json {lib[f]!r}")
                elif f in lib and f not in r and lib[f] is not None:
                    out.append(f"{k}: {'/'.join(key)} carries no {f} (library.json: {lib[f]!r})")
    return out


__all__ = ["DEFAULT", "LANGUAGES", "Language", "catalogue", "catalogue_agrees", "entries", "get", "lint_catalogue",
           "of_path", "parses", "program", "reading", "reads", "require", "runs", "source_names", "suffixes",
           "targets"]
