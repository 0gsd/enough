"""The null morph, the ten scales, morphs and readings (docs/THYM.md 13, 14): the moves `null`, `measure`, `morph`,
`read`, and the checks `null-pinned`, `scales-met`, `scale-evidence`.

**The ten scales.** Each is an integer from 1 (the null's value) to 5. Seven are statistics, computed here exactly as
THYM.md 13.3 tabulates them, in integers per hundred or per thousand (12.6: no floats); three are the model's
judgement (`figurative-density`, `humour`, `allusion`): the model names the sentences, by number, and the code counts
them against the same table, so a judgement is a count a person can check. Every word a statistic counts is a FEED
headword (the lists below; a test holds them to FEED), and a form of one (`seems`, `ok`) counts with its headword.
`register` asks FEED's frequency band where FEED has the word (bands 0 to 3, Uncommon and rarer, are rare; 4 to 8 are
the common band), and counts a word of nine letters or more as rare where it has none; names and numbers are not
counted. `analytical-depth` is the fabula's (13.4), read from the reason links between its claims.

For every scale `measure` gives a value, a basis (`statistics` or `judgement`), one to three sentences of the text that
moved it (the first sentence, when nothing did), and a confidence per hundred (0 to 100: a `.cosm` holds no float),
at most 50 for a statistics scale and 40 for a judgement scale under 300 words or three paragraphs (13.3).

**The moves.** `null` tells a fabula as plainly as it can be told (13.1), cited sentence by sentence; its contract
`null-pinned` measures the telling and holds every statistics scale to 1 (the judgement scales are assumed 1, and the
why says so). `measure` gives a text's morph against the null of its fabula: the seven statistics in code, the three
judgements in one request with examples; its scaffold, `statistics`, gives the seven and leaves the three as open
questions. `morph` tells a short again in a morph (the short must carry its fabula: one told in this run). `read`
tells someone else's fabula in the reader's morph, for an occasion, and labels it: `read_through:` in its front
matter and the reading footer of THYM.md 14 at its end; it is never written over a source.

Standalone: the standard library, PyYAML and `enough.macrocosm`.
"""
from __future__ import annotations

import math
import re
from typing import Any, Iterable

from enough import macrocosm as mc
from enough.thym.checks import body, check
from enough.thym.moves import (MoveError, Sentence, answer_mapping, fabula_doc, fabula_for,
                               first_input, fold, item_kind, model_of, segment, source_name, span_lines, telling_of,
                               utc_day, words_in)
from enough.thym.moves.emf import SENTENCES_SCHEMA, cited_outline, footer_line, tell_outline, telling
from enough.thym.registry import implements, Request
from enough.thym.values import Value

SCALES = ("register", "sentence-length", "paragraph-rhythm", "analytical-depth", "figurative-density",
          "stance-style", "person-voice", "formality", "humour", "allusion")
STATISTICS = ("register", "sentence-length", "paragraph-rhythm", "analytical-depth", "stance-style", "person-voice",
              "formality")
JUDGEMENT = ("figurative-density", "humour", "allusion")
#: THYM.md 13.3, version 0's thresholds. `lt`: the value is 1 plus how many bounds the ratio reaches; `le`: plus how
#: many it exceeds; `none`: a count of nothing is 1, and any count is 2 or more, by the bounds.
THRESHOLDS = {
    "register": ("lt", (2, 5, 10, 20)),
    "sentence-length": ("le", (10, 15, 20, 27)),
    "paragraph-rhythm": ("lt", (15, 30, 50, 75)),
    "analytical-depth": ("lt", (10, 30, 60, 100)),
    "stance-style": ("lt", (5, 10, 20, 40)),
    "person-voice": ("lt", (5, 15, 30, 60)),
    "formality": ("lt", (5, 15, 30, 60)),
    "figurative-density": ("none", (5, 15, 30)),
    "humour": ("none", (3, 10, 20)),
    "allusion": ("none", (1, 3, 6)),
}
#: The units each ratio is in, for the asks a prompt carries.
UNITS = {"register": "rare words in every hundred distinct words", "sentence-length": "words per sentence on average",
         "paragraph-rhythm": "spread of sentences per paragraph, per hundred of the mean",
         "analytical-depth": "reason links per hundred claims", "stance-style": "hedge words per thousand words",
         "person-voice": "first and second person words per thousand words",
         "formality": "marked words per thousand words",
         "figurative-density": "figurative sentences per hundred sentences",
         "humour": "joking or ironic sentences per hundred sentences",
         "allusion": "references outside the subject per thousand words"}
ENDS = {"register": ("plain", "ornate"), "sentence-length": ("short", "long"), "paragraph-rhythm": ("even", "varied"),
        "analytical-depth": ("claims only", "every reason"), "figurative-density": ("literal", "figurative"),
        "stance-style": ("flat", "hedged"), "person-voice": ("impersonal", "personal"),
        "formality": ("plain", "marked"), "humour": ("none", "much"), "allusion": ("none", "dense")}

# The word lists of THYM.md 13.3, version 0's seed: every entry a FEED headword. FORMS lists the forms of a headword
# that count with it (FEED files `seems` under `seem` and `ok` under `okay`).
HEDGES = ("maybe", "perhaps", "seem", "might", "could", "arguably", "probably", "likely", "somewhat", "rather")
HEDGE_PHRASES = (("i", "think"), ("i", "suspect"))
PRONOUNS = ("i", "me", "my", "we", "us", "our", "you", "your")
CASUAL = ("gonna", "kinda", "yeah", "okay", "stuff", "gotta", "wanna", "sorta", "dude",
          "oh", "wow", "hey", "um", "uh", "ah", "ugh", "whoa", "yep", "nope", "nah", "huh", "hmm")
LATINATE = ("utilise", "utilize", "commence", "whereby", "herein", "aforementioned", "pursuant", "notwithstanding",
            "endeavour", "facilitate", "ascertain", "thereby")
FORMAL_PHRASES = (("prior", "to"), ("in", "accordance", "with"))
HONORIFICS = ("sir", "madam", "mister")
FORMS = {"seem": ("seems", "seemed", "seeming"), "okay": ("ok",)}
#: Every word the statistics count, for the test that holds them to FEED.
WORD_LISTS = {"hedges": HEDGES + tuple(w for p in HEDGE_PHRASES for w in p), "pronouns": PRONOUNS, "casual": CASUAL,
              "latinate": LATINATE + tuple(w for p in FORMAL_PHRASES for w in p), "honorifics": HONORIFICS}
COMMON_BAND = 4                         # FEED's bands 4 (Occasional) to 8 (Extremely common) are common
RARE_LETTERS = 9                        # where FEED has no band: a word of nine letters or more is rare
REASON_RELS = ("supports", "depends-on", "resolves")
_CONTRACTION = re.compile(r"(?:n['’]t|['’](?:re|ve|ll|d|m))$", re.I)
_PASSIVE = re.compile(r"\b(?:is|are|was|were|be|been|being)\s+(?:\w+ly\s+)?(?:\w+ed|known|made|done|given|taken|seen|"
                      r"written|shown|built|held|kept|told|found|thought|brought|bought|caught|taught|left|lost|paid|"
                      r"put|read|run|said|sent|set|spent|won|cut|mown|sown|grown|spread|chosen|drawn|driven)\b", re.I)


def _expand(words: Iterable[str]) -> set[str]:
    out = set()
    for w in words:
        out.add(w)
        out.update(FORMS.get(w, ()))
    return out


_HEDGE_SET, _PRONOUN_SET = _expand(HEDGES), set(PRONOUNS)
_CASUAL_SET, _LATINATE_SET, _HONORIFIC_SET = _expand(CASUAL), _expand(LATINATE), set(HONORIFICS)


def scale_value(scale: str, ratio: int, count: int | None = None) -> int:
    """A ratio (and, for a judgement scale, its count) as the scale's value, by THYM.md 13.3."""
    kind, bounds = THRESHOLDS[scale]
    if kind == "le":
        return 1 + sum(1 for b in bounds if ratio > b)
    if kind == "none":
        if not count:
            return 1
        return 2 + sum(1 for b in bounds if ratio >= b)
    return 1 + sum(1 for b in bounds if ratio >= b)


# ---------------------------------------------------------------------------
# The statistics, in code
# ---------------------------------------------------------------------------

def _first(sents: list[Sentence]) -> list[str]:
    return [sents[0].text] if sents else []


def _top(sents: list[Sentence], score: list[int], k: int = 3) -> list[str]:
    ranked = sorted((i for i in range(len(sents)) if score[i] > 0), key=lambda i: (-score[i], i))[:k]
    return [sents[i].text for i in sorted(ranked)] or _first(sents)


def _tokens(s: Sentence) -> list[str]:
    return words_in(s.text)


def _is_name(w: str, i: int) -> bool:
    return i > 0 and w[:1].isupper() and not w.isupper()


def _phrase_count(toks: list[str], phrase: tuple[str, ...]) -> int:
    n = len(phrase)
    return sum(1 for i in range(len(toks) - n + 1) if tuple(toks[i:i + n]) == phrase)


def statistics(text: str, *, feed: Any = None, fabula: Value | None = None, exempt: Iterable[str] = (),
               telling: bool = False, sentences: list[Sentence] | None = None) -> dict[str, dict]:
    """The seven statistics scales of a text (THYM.md 13.3): `{scale: {value, basis, evidence, confidence}}`, with
    `toward` on `formality` when it departs from plain. `telling` reads a short (front matter and footer left out);
    `exempt` names words `register` does not count (the null's own names and terms); `fabula` gives
    `analytical-depth`; `feed` is FEED's batch lookup (`ctx.engines["feed"]`), or None for the letter rule."""
    sents = sentences if sentences is not None else [s for s in segment(text, footer=not telling)
                                                     if s.kind != "heading"]
    toks_by = [_tokens(s) for s in sents]
    n_words = sum(len(t) for t in toks_by)
    paras: dict[int, int] = {}
    for s in sents:
        paras[s.para] = paras.get(s.para, 0) + 1
    short = n_words < 300 or len(paras) < 3
    base = 50 if short else 90
    out: dict[str, dict] = {}

    def put(scale: str, value: int, evidence: list[str], confidence: int, **extra: Any) -> None:
        out[scale] = {"value": int(value), "basis": "statistics", "evidence": evidence[:3] or _first(sents),
                      "confidence": int(confidence), **extra}

    # register: distinct words outside FEED's common band, per hundred
    exempt_set = {w.lower() for w in exempt}
    distinct: dict[str, None] = {}
    for toks in toks_by:
        for i, w in enumerate(toks):
            lw = w.lower()
            if w.isdigit() or _is_name(w, i) or "'" in w or "’" in w or lw in exempt_set:
                continue
            distinct.setdefault(lw, None)
    found: dict = {}
    if feed is not None and distinct:
        try:
            found = feed(list(distinct)) or {}
        except Exception:  # noqa: BLE001 - no FEED: the letter rule stands in
            found = {}

    def rare(w: str) -> bool:
        e = found.get(w)
        band = e.get("frequency_rank") if isinstance(e, dict) else None
        if isinstance(band, int) and not isinstance(band, bool):
            return band < COMMON_BAND
        return len(w) >= RARE_LETTERS
    rare_words = {w for w in distinct if rare(w)}
    r = 100 * len(rare_words) // len(distinct) if distinct else 0
    put("register", scale_value("register", r),
        _top(sents, [sum(1 for w in t if w.lower() in rare_words) for t in toks_by]), base,
        words=sorted(rare_words, key=lambda w: (-sum(w in t2 for t2 in (set(x.lower() for x in t) for t in toks_by)), w))[:12])

    # sentence-length: mean words per sentence
    mean = n_words // len(sents) if sents else 0
    v = scale_value("sentence-length", mean)
    lens = [len(t) for t in toks_by]
    put("sentence-length", v, _top(sents, lens) if v > 1 else _first(sents), base)

    # paragraph-rhythm: the spread of sentences per paragraph, standard deviation over mean, per hundred
    counts = list(paras.values())
    if len(counts) < 3:
        put("paragraph-rhythm", 1, _first(sents), 30)
    else:
        p, s_, q = len(counts), sum(counts), sum(c * c for c in counts)
        r = math.isqrt(10000 * max(0, p * q - s_ * s_)) // s_ if s_ else 0
        longest = max(paras, key=lambda k: (paras[k], -k))
        shortest = min(paras, key=lambda k: (paras[k], k))
        ev = [next(x.text for x in sents if x.para == k) for k in sorted({longest, shortest})]
        put("paragraph-rhythm", scale_value("paragraph-rhythm", r), ev, base)

    # analytical-depth: the fabula's reason links per claim, per hundred (carried, 13.4)
    _cat, items = fabula_doc(fabula)
    claims = [it for it in items if item_kind(it) == "claim"]
    links = {}
    for c in claims:
        k = sum(1 for ln in c.get("links") or [] if isinstance(ln, dict) and ln.get("rel") in REASON_RELS)
        links[c.get("id")] = k
    if not claims:
        put("analytical-depth", 1, _first(sents), 20 if fabula is None else min(base, 40))
    else:
        r = 100 * sum(links.values()) // len(claims)
        ev = []
        for c in sorted(claims, key=lambda c: -links[c.get("id")]):
            ab = span_lines(c)
            if links[c.get("id")] and ab:
                ev += [s.text for s in sents if s.first <= ab[1] and s.last >= ab[0] and s.text not in ev]
            if len(ev) >= 3:
                break
        put("analytical-depth", scale_value("analytical-depth", r), ev, base)

    # stance-style: hedge words per thousand
    low = [[w.lower() for w in t] for t in toks_by]
    hedges = [sum(1 for w in t if w in _HEDGE_SET) + sum(_phrase_count(t, ph) for ph in HEDGE_PHRASES) for t in low]
    r = 1000 * sum(hedges) // n_words if n_words else 0
    put("stance-style", scale_value("stance-style", r), _top(sents, hedges), base)

    # person-voice: first and second person per thousand
    pron = [sum(1 for w, o in zip(t, toks_by[i]) if w in _PRONOUN_SET and not (o.isupper() and len(o) > 1))
            for i, t in enumerate(low)]
    r = 1000 * sum(pron) // n_words if n_words else 0
    put("person-voice", scale_value("person-voice", r), _top(sents, pron), base)

    # formality: casual markers and contractions against Latinate markers, honorifics and a mostly passive text
    casual = [sum(1 for w in t if w in _CASUAL_SET) + sum(1 for o in toks_by[i] if _CONTRACTION.search(o))
              for i, t in enumerate(low)]
    passive = [1 if _PASSIVE.search(s.text) else 0 for s in sents]
    formal = [sum(1 for w in t if w in _LATINATE_SET or w in _HONORIFIC_SET)
              + sum(_phrase_count(t, ph) for ph in FORMAL_PHRASES) for t in low]
    if sents and 2 * sum(passive) > len(sents):
        formal = [f + p for f, p in zip(formal, passive)]
    cr = 1000 * sum(casual) // n_words if n_words else 0
    fr = 1000 * sum(formal) // n_words if n_words else 0
    v = scale_value("formality", max(cr, fr))
    extra = {"toward": "formal" if fr > cr else "casual"} if v > 1 else {}
    put("formality", v, _top(sents, formal if fr > cr else casual), base, **extra)
    return out


def judged(data: dict, sents: list[Sentence], n_words: int, *, short: bool) -> dict[str, dict]:
    """The three judgement scales from the model's answer, by count: the sentence numbers it judged figurative and
    joking, and the references it found outside the subject (THYM.md 13.3)."""
    out: dict[str, dict] = {}
    n = len(sents)
    conf = 40 if short else 70

    def numbers(v: Any) -> list[int]:
        rows = v if isinstance(v, list) else ([v] if v is not None else [])
        got = []
        for x in rows:
            if isinstance(x, dict):
                x = x.get("sentence", x.get("n"))
            if isinstance(x, str) and x.strip().isdigit():
                x = int(x.strip())
            if isinstance(x, int) and not isinstance(x, bool) and 1 <= x <= n and x not in got:
                got.append(x)
        return sorted(got)

    for scale, key in (("figurative-density", "figurative"), ("humour", "humour")):
        hits = numbers(data.get(key))
        r = 100 * len(hits) // n if n else 0
        out[scale] = {"value": scale_value(scale, r, len(hits)), "basis": "judgement",
                      "evidence": [sents[i - 1].text for i in hits[:3]] or _first(sents), "confidence": conf}
    refs = data.get("allusion") if isinstance(data.get("allusion"), list) else []
    valid = [x for x in refs if numbers([x])]                 # a reference counts when it names its sentence
    hits = numbers(valid)
    count = len(valid)
    r = 1000 * count // n_words if n_words else 0
    out["allusion"] = {"value": scale_value("allusion", r, count), "basis": "judgement",
                       "evidence": [sents[i - 1].text for i in hits[:3]] or _first(sents), "confidence": conf}
    return out


# ---------------------------------------------------------------------------
# Morphs: reading one, writing one, asking for one
# ---------------------------------------------------------------------------

def morph_items(v: Value | None) -> list[dict]:
    if v is None or not isinstance(v, Value) or v.is_nothing:
        return []
    m = v.mapping() or {}
    if isinstance(m.get("nodes"), list):
        return [n for n in m["nodes"] if isinstance(n, dict) and isinstance(n.get("scales"), dict)]
    return [m] if isinstance(m.get("scales"), dict) else []


def morph_scales(v: Value | None) -> tuple[str, dict, str | None]:
    """A morph's name, its ten scales (an unlisted scale sits at 1, 13.5) and the direction of its formality."""
    rows = morph_items(v)
    if not rows:
        return "null", {s: 1 for s in SCALES}, None
    it = rows[0]
    sc = it.get("scales") or {}
    scales = {s: (sc.get(s) if isinstance(sc.get(s), int) or mc.is_pending(sc.get(s)) else 1) for s in SCALES}
    name = it.get("name") or str(it.get("id") or "").rsplit("/", 1)[-1] or "morph"
    toward = it.get("toward") if it.get("toward") in ("formal", "casual") else None
    return str(name), scales, toward


def _band(scale: str, value: int) -> str:
    kind, b = THRESHOLDS[scale]
    if kind == "le":
        lo = [0, b[0] + 1, b[1] + 1, b[2] + 1, b[3] + 1]
        return (f"at most {b[0]}" if value == 1 else f"more than {b[3]}" if value == 5
                else f"{lo[value - 1]} to {b[value - 1]}")
    if kind == "none":
        if value == 1:
            return "none at all"
        lo = [None, None, 0, b[0], b[1], b[2]][value]
        return (f"some, fewer than {b[0]}" if value == 2 else f"{b[2]} or more" if value == 5
                else f"{lo} to {b[value - 2] - 1}")
    return (f"fewer than {b[0]}" if value == 1 else f"{b[3]} or more" if value == 5
            else f"{b[value - 2]} to {b[value - 1] - 1}")


def asks_for(m: Value | None) -> str:
    """A morph as a model is asked to keep it: one line per scale, its value, what the value means and the number the
    code will measure (THYM.md 13.2, 13.3)."""
    name, scales, toward = morph_scales(m)
    lines = [f"The morph {name}, ten scales from 1 (the plainest telling) to 5:"]
    for s in SCALES:
        v = scales.get(s)
        if not isinstance(v, int):
            continue
        a, b = ENDS[s]
        said = a if v == 1 else b if v == 5 else f"between {a} and {b}"
        if s == "formality" and v > 1 and toward:
            said += f", toward {toward}"
        lines.append(f"- {s} {v}: {said}; {_band(s, v)} {UNITS[s]}")
    return "\n".join(lines)


def _slug(v: Value) -> str:
    stem = v.path.name if v.path is not None else "measured"
    stem = re.sub(r"\.(md|markdown|txt|text)$", "", stem)
    return re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-") or "measured"


def morph_volume(t: Value, scales: dict[str, dict], *, ctx: Any, against: Value | None, by: str) -> dict:
    """A measured morph as a `thym/1` morph volume with one `M:morph` item (THYM.md 13.5, 17.3)."""
    slug = _slug(t)
    name = t.path.name if t.path is not None else slug
    item: dict = {"id": f"M:morph/{slug}", "type": "morph", "name": slug,
                  "summary": f"How {name} departs from the null telling of its fabula, on ten scales.",
                  "scales": {}, "evidence": {}, "basis": {}, "confidence": {}}
    for s in SCALES:
        e = scales.get(s) or {"value": {"pending": "not measured"}, "basis": "judgement"}
        item["scales"][s] = e["value"]
        item["basis"][s] = e.get("basis", "statistics")
        if not mc.is_pending(e["value"]):
            item["evidence"][s] = list(e.get("evidence") or [])
            item["confidence"][s] = int(e.get("confidence", 0))
    fo = scales.get("formality") or {}
    if fo.get("toward"):
        item["toward"] = fo["toward"]
    item["pinned"] = []
    derived = {"from": [f"{name}#sha256:{t.sha256}"]}
    if against is not None and not against.is_nothing:
        derived["against"] = f"sha256:{against.sha256}"
    derived.update(at=ctx.now, by=by)
    item["derived"] = derived
    item["shared"] = False
    item["provenance"] = {"mode": "derived", "sources": [name]}
    return {"oes": "thym/1", "kind": "morph", "id": f"thym/{slug}", "name": slug, "nodes": [item]}


def _candidates(fab: Value | None) -> list[str]:
    out = []
    for it in fabula_doc(fab)[1]:
        if item_kind(it) in ("work", "person") and it.get("name"):
            out.append(f"{it.get('name')} ({item_kind(it)})")
        q = it.get("quote") or it.get("quotation")
        if isinstance(q, str) and q.strip():
            out.append(f"\"{fold(q)}\" (a quotation)")
    return out


MEASURE_SCHEMA = {"format": "yaml", "stamp": "engine",
                  "says": "a YAML mapping: figurative, humour (lists of sentence numbers) and allusion (a list of "
                          "{sentence, to})"}


# ---------------------------------------------------------------------------
# The moves
# ---------------------------------------------------------------------------

@implements("null")
def null(ctx: Any, **mods: Any) -> Request:
    """The null telling of a fabula (THYM.md 13.1): told order, one claim per sentence, the commonest words, every
    stance in a fixed phrase; no figure, humour, allusion or contraction; the third person."""
    fab = mods.get("of")
    if not isinstance(fab, Value) or fab.type != "fabula":
        raise MoveError("null tells a fabula: null of <fabula>")
    cat, items = fabula_doc(fab)
    inputs = {"fabula": fab, "outline": Value("string", cited_outline(cat, items, "told"))}

    def parse(out: Any) -> Value:
        # The null is one paragraph by definition (THYM.md 13.1): paragraph marks the model adds are not a departure
        # it can be asked to undo, they are read as none, so `paragraph-rhythm` is 1 by construction.
        return telling(ctx, out, fab, footer=lambda model: footer_line(ctx, cat, fab, "told", model), order="told",
                       morph="null", one_paragraph=True)
    return Request(contract={"schema": SENTENCES_SCHEMA, "repair": []}, inputs=inputs, parse=parse)


@implements("null.scaffold")
def null_outline(ctx: Any, **mods: Any) -> Value:
    """The null's scaffold, `outline`: the fabula's told outline in the items' own sentences (THYM.md 13.1, 19)."""
    return tell_outline(ctx, mods.get("of"), **{"as": "told"})


def _measure_parts(ctx: Any, t: Value, against: Value | None) -> tuple[list[Sentence], int, bool, dict, Value | None]:
    fab = (telling_of(against) or {}).get("fabula") if isinstance(against, Value) else None
    sents = [s for s in segment(t.text(), footer=True) if s.kind != "heading"]
    n_words = sum(len(words_in(s.text)) for s in sents)
    short = n_words < 300 or len({s.para for s in sents}) < 3
    stats = statistics(t.text(), feed=ctx.engines.get("feed"), fabula=fab, sentences=sents)
    return sents, n_words, short, stats, fab


@implements("measure")
def measure(ctx: Any, t: Value, **mods: Any) -> Request:
    """A text's morph against the null of its fabula (THYM.md 13.3, 13.4): seven statistics in code, three judgements
    asked of the model, every scale with its evidence, basis and confidence."""
    against = mods.get("against")
    sents, n_words, short, stats, fab = _measure_parts(ctx, t, against)
    numbered = "\n".join(f"{i}. {s.text}" for i, s in enumerate(sents, 1))
    inputs = {"text": t, "sentences": Value("string", numbered),
              "candidates": Value("string", "\n".join(_candidates(fab)) or "(none)")}

    def parse(out: Any) -> Value:
        data = answer_mapping(out)
        scales = {**stats, **judged(data, sents, n_words, short=short)}
        by = f"model:{model_of(data)}" if model_of(data) else "model"
        return Value("morph", morph_volume(t, scales, ctx=ctx, against=against, by=by))
    return Request(contract={"schema": MEASURE_SCHEMA, "repair": []}, inputs=inputs, parse=parse)


@implements("measure.scaffold")
@implements("statistics")
def measure_statistics(ctx: Any, t: Value, **mods: Any) -> Value:
    """`statistics`: the seven statistics scales, and the three judgement scales as open questions (THYM.md 19)."""
    against = mods.get("against")
    _s, _n, _short, stats, _fab = _measure_parts(ctx, t, against)
    for s in JUDGEMENT:
        stats[s] = {"value": {"pending": "a model has not judged this"}, "basis": "judgement"}
    return Value("morph", morph_volume(t, stats, ctx=ctx, against=against, by="rules"))


@implements("morph")
def morph(ctx: Any, s: Value, **mods: Any) -> Request:
    """A short told again in a morph (THYM.md 6.3): the same items, the same citations, the morph's scales."""
    m = mods.get("with")
    t = telling_of(s)
    fab = t.get("fabula") if t else None
    if not isinstance(fab, Value):
        raise MoveError("morph tells again a short that carries its fabula, one told in this run; tell it first")
    cat, _items = fabula_doc(fab)
    rows = list(zip(t.get("sentences") or [], t.get("covers") or [])) if t.get("covers") is not None else \
        [(x.text, []) for x in segment(body(s.text()))]
    numbered = "\n".join(f"{i}. [{', '.join(c)}] {x}" for i, (x, c) in enumerate(rows, 1))
    order = t.get("order") or "told"
    inputs = {"short": s, "fabula": fab, "sentences": Value("string", numbered), "morph": m,
              "asks": Value("string", asks_for(m))}
    name = morph_scales(m)[0]

    def parse(out: Any) -> Value:
        return telling(ctx, out, fab, footer=lambda model: footer_line(ctx, cat, fab, order, model), order=order,
                       morph=name)
    return Request(contract={"schema": SENTENCES_SCHEMA, "repair": []}, inputs=inputs, parse=parse)


def occasion(c: Value | None) -> str:
    """An occasional context as the prompt says it (THYM.md 16.2): every field, one line each."""
    if c is None or not isinstance(c, Value) or c.is_nothing:
        return "(no occasion was given)"
    m = c.mapping() or {}
    it = next((n for n in m.get("nodes") or [] if isinstance(n, dict)), m)
    skip = {"id", "type", "name", "summary", "provenance", "made", "status", "visibility", "links", "pending"}
    lines = [f"{k}: {v}" for k, v in it.items() if k not in skip and not isinstance(v, (dict, list))]
    head = it.get("summary") or it.get("name") or ""
    return "\n".join(([f"The occasion: {head}"] if head else []) + lines) or "(no occasion was given)"


def _budget(c: Value | None) -> int | None:
    if c is None or not isinstance(c, Value) or c.is_nothing:
        return None
    w = c.field("words")
    return w if isinstance(w, int) and not isinstance(w, bool) and w > 0 else None


@implements("read")
def read(ctx: Any, f: Value, **mods: Any) -> Request:
    """Someone else's fabula told in the reader's morph, for an occasion, labelled a reading (THYM.md 14)."""
    m = mods.get("with")
    c = mods.get("in")
    if not isinstance(f, Value) or f.type != "fabula":
        raise MoveError("read takes a fabula; a reading is a short, and a reading of a reading is refused")
    cat, items = fabula_doc(f)
    name = morph_scales(m)[0]
    inputs = {"fabula": f, "outline": Value("string", cited_outline(cat, items, "told")), "morph": m,
              "asks": Value("string", asks_for(m)), "occasion": Value("string", occasion(c))}
    words = _budget(c)
    if words:
        inputs["words"] = Value("number", words)

    def foot(model: str | None) -> str:
        return (f"*a reading of {source_name(cat, f)} through {name}, made here on "
                f"{utc_day(ctx)} by {model or 'a model'}; the text stands unchanged*")

    def parse(out: Any) -> Value:
        return telling(ctx, out, f, footer=foot, order="told", morph=name, front={"read_through": name})
    return Request(contract={"schema": SENTENCES_SCHEMA, "repair": []}, inputs=inputs, parse=parse,
                   budget={"output_words": words} if words else None)


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------

def _measured(output: Value, ctx: Any, exempt: Iterable[str] = ()) -> dict[str, dict]:
    feed = (getattr(ctx, "engines", None) or {}).get("feed")
    return statistics(output.text(), feed=feed, exempt=exempt, telling=True)


@check("null-pinned")
def _null_pinned(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every scale of the null telling is 1 (THYM.md 13.1, 13.4): the statistics scales, measured on the telling (the
    fabula's own words, its items' names, summaries and senses, are not counted as rare: the null must say them);
    `analytical-depth` is 1 because
    the null tells claims without their reasons; the judgement scales are assumed 1 and not asked; `person-voice` is
    let be when the fabula's own claims are in the first person."""
    if output.state == "pending":
        return True, "a scaffold is the outline in the items' own sentences; the pin is the model's to keep"
    fab = fabula_for(output, inputs)
    _cat, items = fabula_doc(fab)
    # The null is given its fabula's vocabulary and must repeat it, so every word the items use is exempt from
    # register here; a text's own register (measure) exempts names only, since the author chose the rest.
    exempt = {w.lower() for it in items for f in ("name", "summary", "sense")
              for w in words_in(str(it.get(f) or ""))}
    got = _measured(output, ctx, exempt)
    first_person = any(w.lower() in ("i", "we", "my", "our") for it in items if item_kind(it) == "claim"
                       for w in words_in(str(it.get("summary") or "")))
    off = []
    for s in STATISTICS:
        if s == "analytical-depth" or got[s]["value"] == 1 or (s == "person-voice" and first_person):
            continue
        said = f"{s} {got[s]['value']}"
        if s == "register" and got[s].get("words"):
            # the re-ask can act on words, not on a number: the rare ones, commonest first in the telling
            said += " (rare words: " + ", ".join(got[s]["words"]) + "; say them in commoner words or the items' own)"
        off.append(said)
    if off:
        return False, f"the null telling departs: {'; '.join(off)} (every scale must be 1)"
    return True, "statistics all 1; figurative-density, humour and allusion assumed 1 (judgement, not asked)"


def _signed(v: int, toward: str | None) -> int:
    return -(v - 1) if toward == "casual" else (v - 1)


@check("scales-met")
def _scales_met(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Each statistics scale of the output, measured, is within one step of the morph asked for (THYM.md 7.3);
    `analytical-depth` is the fabula's (13.4), and the judgement scales are skipped with a note: measuring them would
    ask the model again."""
    m = inputs.get("with") if isinstance(inputs.get("with"), Value) else first_input(inputs, "morph")
    if m is None or m.is_nothing:
        return True, "no morph was asked for"
    name, asked, toward = morph_scales(m)
    got = _measured(output, ctx)
    off = []
    for s in STATISTICS:
        if s == "analytical-depth" or not isinstance(asked.get(s), int):
            continue
        g = got[s]["value"]
        if s == "formality":
            if abs(_signed(g, got[s].get("toward")) - _signed(asked[s], toward)) > 1:
                off.append(f"formality {g}{' toward ' + got[s]['toward'] if got[s].get('toward') else ''} against "
                           f"{asked[s]}{' toward ' + toward if toward else ''}")
        elif abs(g - asked[s]) > 1:
            off.append(f"{s} {g} against {asked[s]}")
    if off:
        return False, f"the telling misses {name}: {', '.join(off)}"
    return True, (f"{name}'s statistics met within one step; figurative-density, humour and allusion are judgement "
                  "scales and were not measured; analytical-depth is the fabula's")


@check("scale-evidence")
def _scale_evidence(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every scale cites one to three sentences of the measured text, and gives its basis and its confidence (THYM.md
    7.3, 13.3); an open question (a scaffold's judgement scale) cites nothing yet."""
    src = first_input(inputs, "text", "short")
    if src is None:
        return False, "no measured text among the inputs"
    flat = fold(" ".join(s.text for s in segment(src.text(), footer=True))).lower()
    rows = morph_items(output)
    if not rows:
        return False, "no morph with scales"
    for it in rows:
        for s, v in (it.get("scales") or {}).items():
            if mc.is_pending(v):
                continue
            ev = (it.get("evidence") or {}).get(s)
            if not isinstance(ev, list) or not 1 <= len(ev) <= 3:
                return False, f"{s} cites {len(ev) if isinstance(ev, list) else 'no'} sentences, not one to three"
            for e in ev:
                if not isinstance(e, str) or fold(e).lower() not in flat:
                    return False, f"{s} cites a sentence the text does not hold: {str(e)[:60]}"
            if (it.get("basis") or {}).get(s) not in ("statistics", "judgement"):
                return False, f"{s} gives no basis"
            c = (it.get("confidence") or {}).get(s)
            if not isinstance(c, int) or isinstance(c, bool) or not 0 <= c <= 100:
                return False, f"{s} gives no confidence from 0 to 100"
    return True, ""


__all__ = ["JUDGEMENT", "SCALES", "STATISTICS", "THRESHOLDS", "WORD_LISTS", "asks_for", "measure", "morph",
           "morph_scales", "morph_volume", "null", "read", "scale_value", "statistics"]
