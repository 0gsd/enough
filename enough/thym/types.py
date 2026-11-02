"""Thym's types: the densities, the meaning types, the plain types, and what fits where (THYM.md 4.6, 4.8, 5.1, 5.2).

A type is a plain string: one of the simple types of the grammar (`text`, `fabula`, `short`, `atem`, `item`,
`volume`, `morph`, `context`, `graph`, `package`, `plan`, `trace`, `report`, `number`, `string`, `bool`, `date`,
`word`), or `list of T`. Two more stand only inside the compiler: `nothing`, the absent value an accessor may give,
and `any`, the type of a value the compiler cannot know before the run (a field read off a context or an item).

A declaration in a manifest's `moves:` block writes a type as a string of alternatives, `'fabula | item | volume'`,
and may name a class of words instead of a type (`order`, `marking`), the words themselves (`'isotype | paratype'`),
a unit (`words`, `sentences`) or `condition`. `alternatives` reads those strings and `accepts` says whether a value
fits one.

A value of one density is never read as another (section 5.2): `accepts` has no coercions between `text`, `fabula`,
`short` and `atem`, and `hint` gives the fix when a program tries ("derive it first").
"""
from __future__ import annotations

DENSITIES = ("text", "fabula", "short", "atem")
MEANING = ("text", "fabula", "short", "atem", "item", "volume", "morph", "graph", "package")
SIMPLE = ("text", "fabula", "short", "atem", "item", "volume", "morph", "context", "graph", "package", "plan", "trace",
          "report", "number", "string", "bool", "date", "word")
PLAIN = ("number", "string", "bool", "date", "word")

ORDERS = ("told", "weight")
MARKINGS = ("verified", "stated")
STANCES = ("axiom", "observed", "deduced", "opinion", "assumed", "hearsay")
LADDER = ("hearsay", "assumed", "opinion", "deduced", "observed", "axiom")        # weakest first (section 7.2)
SCALES = ("register", "sentence-length", "paragraph-rhythm", "analytical-depth", "figurative-density",
          "stance-style", "person-voice", "formality", "humour", "allusion")        # section 13.2, in its order
TOWARD = ("casual", "formal")
UNITS = ("words", "sentences")

# The classes of words a declaration may name for a modifier, and the words in each (section 4.6).
WORD_CLASSES = {"order": ORDERS, "marking": MARKINGS, "density": DENSITIES, "stance": STANCES}
# Words that are literals wherever they stand as values, and so are reserved (section 4.7).
LITERAL_WORDS = frozenset(DENSITIES + ORDERS + MARKINGS + STANCES)
# The operand types that accept `nothing`: the last three parts of a package (section 6.3).
OPTIONAL = ("morph", "context", "graph")

ANY = "any"
NOTHING = "nothing"
WORD = "word"
CONDITION = "condition"


def list_of(t: str) -> str:
    return f"list of {t}"


def is_list(t: str | None) -> bool:
    return bool(t) and (t == "list" or t.startswith("list of "))


def element(t: str) -> str:
    """The member type of a list type (`any` for the bare `list` a declaration may name)."""
    return t[len("list of "):] if t.startswith("list of ") else ANY


def parse_type(words: str) -> str | None:
    """A type as the grammar writes it (`fabula`, `list of word`), in canonical spacing; None when it is not one."""
    parts = words.split()
    if len(parts) == 1 and parts[0] in SIMPLE:
        return parts[0]
    if len(parts) >= 3 and parts[0] == "list" and parts[1] == "of":
        inner = parse_type(" ".join(parts[2:]))
        return list_of(inner) if inner else None
    return None


def alternatives(spec) -> list[str]:
    """A declaration's type string as its alternatives: `'fabula | item | volume'` → [fabula, item, volume]."""
    if spec is None:
        return []
    if isinstance(spec, (list, tuple)):
        out: list[str] = []
        for s in spec:
            out.extend(alternatives(s))
        return out
    return [" ".join(a.split()) for a in str(spec).split("|") if a.strip()]


def is_word_choice(alts: list[str]) -> bool:
    """True when a declaration names words rather than types (`'isotype | paratype'`, `order`, `marking`)."""
    return bool(alts) and all(a not in SIMPLE and not is_list(a) and a not in (ANY, NOTHING, CONDITION)
                              and a not in UNITS for a in alts)


def accepts(alts: list[str], actual: str | None, *, word: str | None = None) -> bool:
    """Whether a value of type `actual` fits one of the declared alternatives. `word` is the bare word itself
    when the value is one, so that `as told` fits an `order` and `as isotype` fits `'isotype | paratype'`."""
    if actual is None:
        return False
    if actual == ANY:
        return True
    for a in alts:
        if a == actual:
            return True
        if a == "list" and is_list(actual):
            return True
        if is_list(a) and is_list(actual):
            inner = element(actual)
            if inner == ANY or accepts([element(a)], inner):
                return True
        if actual == WORD and word is not None:
            if a in WORD_CLASSES and word in WORD_CLASSES[a]:
                return True
            if a == word and a not in SIMPLE:
                return True
        if actual == NOTHING and a in OPTIONAL:
            return True
    return False


def show(alts: list[str]) -> str:
    """Alternatives as a reader says them: `a fabula, an item or a volume`."""
    words = [_article(a) for a in alts]
    if not words:
        return "nothing"
    if len(words) == 1:
        return words[0]
    return ", ".join(words[:-1]) + " or " + words[-1]


def _article(t: str) -> str:
    if t in WORD_CLASSES:
        return f"an {t} ({', '.join(WORD_CLASSES[t])})" if t[0] in "aeiou" else f"a {t} ({', '.join(WORD_CLASSES[t])})"
    if t not in SIMPLE and not is_list(t) and t not in (ANY, NOTHING, CONDITION):
        return f"`{t}`"
    return f"{'an' if t[0] in 'aeiou' else 'a'} {t}"


_HINTS = {
    ("text", "fabula"): "derive it first",
    ("text", "short"): "derive it, then tell it",
    ("text", "atem"): "derive it, then atem it",
    ("fabula", "short"): "tell it first",
    ("fabula", "atem"): "atem it first",
    ("short", "atem"): "atem it first",
    ("atem", "short"): "expand it first",
    ("short", "fabula"): "a short is a telling, not a fabula: derive its text instead",
    ("number", "word"): "band it first",
}


def hint(actual: str | None, alts: list[str]) -> str | None:
    """The fix for a value of the wrong density, when one is known: a text where a fabula is wanted is derived."""
    for a in alts:
        h = _HINTS.get((actual or "", a))
        if h:
            return h
    return None


def literal_type(kind: str) -> str:
    """The type of a literal of the parser's kind."""
    return {"number": "number", "string": "string", "date": "date", "bool": "bool", "nothing": NOTHING}[kind]


def uri_type(uri: str) -> str:
    """An `oes:` URI names a volume, or an item inside one; a morph or a context item has its own type."""
    rest = uri[len("oes:"):] if uri.startswith("oes:") else uri
    parts = rest.split("/")
    if len(parts) <= 2:
        return "volume"
    path = "/".join(parts[2:])
    if path.startswith("M/morph/"):
        return "morph"
    if path.startswith("C/context/"):
        return "context"
    return "item"


def noun(t: str | None) -> str:
    """The noun a summary uses for a value of this type: `fabula`, `text`, `items`."""
    if not t or t == ANY:
        return "value"
    if is_list(t):
        inner = element(t)
        return "items" if inner in ("item", ANY) else f"list of {inner}s"
    return t


def gives_same(gives: list[str], takes: list[list[str]]) -> bool:
    """True when a declaration gives "the same" as it takes (`mark`: item | word → item | word)."""
    return len(gives) > 1 and bool(takes) and sorted(gives) == sorted(takes[0])
