"""The standard moves of Thym 0 and the checks their contracts name (docs/THYM.md 6.3, 7.3, 12, 13 to 16, 18, 19).

A manifest declares a move (its `moves:` block) and names its code (`code: enough.thym.moves.emf:derive`); this package
holds that code, one module per subject, as THYM.md 11.2 lays it out:

- `emf`: `derive`, `tell`, `atem`, `expand`, and the checks a telling carries (`coverage`, `no-invention`,
  `stance-kept`, `footer`, `span-resolves`, `stance-closed`, `terms-grounded`, `atem-shape`, `span-inside`);
- `edit`: `cut`, `count`, `words`, `digest`, `lint`, `trace`, and `weight-order`;
- `morph`: `null`, `measure`, `morph`, `read`, the ten scales with their word lists, and `null-pinned`,
  `scales-met`, `scale-evidence`;
- `project`: `project`, `band`, `mark`, `withhold`, and Comprise's rules as checks (`banded`, `verified-derived`,
  `verified-only-where-derived`, `standing-gate`, `epoch`);
- `doc`: `enumerate`, `compile`;
- `pack`: `package`, `unpack` and the accessors `fabula`, `context`, `graph`, `isomorph`, and `released`.

Importing any of them imports them all, so every move and every check is registered once (`registry.MOVES`,
`checks.CHECKS`). The deterministic moves transcode in code and never touch the coprocessor. A move that transcognizes
returns a `Request`; the model is reached only through `ctx.coprocessor`. Where an engine itself calls the model
(`canon_derive`'s reading of a text, passage by passage), its `complete` is an `EngineAdapter` over the coprocessor, so
that every call is one recorded candidate, `candidates/<node>-<k>.1.cosm`, and a replay gives the same answers back.

The engines live outside the package. A move reaches them through `ctx.engines` (`canon`, `docoes`, `feed`, and,
when the host has them, `standing` and `catalog`), which `enough/thym_host.py` fills; a test may pass fakes.

This module holds what the moves share: the sentence rule (where a text's sentences are, line by line), the
sentence-to-item map that `coverage` and `assert f covers t` both compute (`cover_map`), the stance ladder and the
words that say a stance, what a telling carries beside its text, and the reading of a model's sentences.

Standalone: the standard library, PyYAML and `enough.macrocosm`.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from enough import macrocosm as mc
from enough.thym import Refusal
from enough.thym.checks import body
from enough.thym.coprocessor import ask
from enough.thym.registry import decl_get
from enough.thym.trace import node_number
from enough.thym.values import Value, plain, wrap

#: The stance ladder of THYM.md 7.2, weakest first: a telling may say a claim more weakly than its fabula, never more
#: strongly.
LADDER = ("hearsay", "assumed", "opinion", "deduced", "observed", "axiom")
RANK = {s: i for i, s in enumerate(LADDER)}
#: EMF's salience, as `cut` weighs a sentence by the items it says (THYM.md 7.3, `weight-order`).
SALIENCE = {"low": 0, "normal": 1, "high": 2, "critical": 3}
ENTITY_KINDS = ("person", "org", "place", "work", "thing")
ORDERS = ("told", "weight")


class MoveError(RuntimeError):
    """A move that cannot go on; the runtime refuses the run with its words (THYM.md 9)."""


def engine(ctx: Any, name: str) -> Any:
    """One of enough's engines from `ctx.engines`, or a MoveError that says which is missing."""
    got = (getattr(ctx, "engines", None) or {}).get(name)
    if got is None:
        raise MoveError(f"the {name} engine is not here; enough's host registers it (enough.thym_host.engines)")
    return got


def utc_day(ctx: Any) -> str:
    """The run's day, in UTC, as a footer writes it: a replay, which keeps the recorded run's clock, writes it again."""
    now = getattr(ctx, "now", None)
    return now.date().isoformat() if now is not None else "1970-01-01"


# ---------------------------------------------------------------------------
# Words and sentences
# ---------------------------------------------------------------------------

_WORD = re.compile(r"[A-Za-zÀ-ɏ0-9]+(?:['’][A-Za-z]+)?")
_FENCE = re.compile(r"^\s{0,3}(```|~~~)")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+\S")
_LIST = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_RULE = re.compile(r"^\s*[-=*_]{3,}\s*$")
_SPLIT = re.compile(r"(?<=[.!?])[\"'”’)\]]*\s+(?=[\"'“‘(\[]?[A-Z0-9])")
_ABBR = frozenset("mr mrs ms dr prof st vs etc eg ie jr sr no fig".split())
_INLINE = [
    (re.compile(r"!\[([^\]]*)\]\([^)]*\)"), r"\1"),
    (re.compile(r"\[([^\]]+)\]\([^)]*\)"), r"\1"),
    (re.compile(r"`([^`]*)`"), r"\1"),
    (re.compile(r"(\*\*|__)(.+?)\1"), r"\2"),
    (re.compile(r"(?<![\w*])[*_]([^*_]+)[*_](?![\w*])"), r"\1"),
    (re.compile(r"<[^>]+>"), ""),
]


def fold(s: Any) -> str:
    """Whitespace folded to single spaces."""
    return " ".join(str(s).split())


def plain_text(s: str) -> str:
    """A line's words without markdown's inline marks (links, emphasis, code, tags), whitespace folded."""
    for rx, rep in _INLINE:
        s = rx.sub(rep, s)
    return fold(s)


def words_in(s: str) -> list[str]:
    return _WORD.findall(s)


@dataclass(frozen=True)
class Sentence:
    """One sentence of a text: its words (markdown marks stripped), the lines it sits on (1-based, in the text as
    written), its paragraph, and its kind: `prose`, `list` (a list item), or `heading`."""
    text: str
    first: int
    last: int
    para: int
    kind: str = "prose"


def _front_lines(lines: list[str]) -> int:
    """How many lines a YAML front matter block takes at the top (0 when there is none)."""
    if lines and lines[0].strip() == "---":
        for i in range(1, min(len(lines), 400)):
            if lines[i].strip() in ("---", "..."):
                return i + 1
    return 0


def _is_footer(line: str) -> bool:
    s = line.strip()
    return len(s) > 2 and s.startswith("*") and s.endswith("*") and not s.startswith("**")


def segment(text: str, *, footer: bool = False) -> list[Sentence]:
    """The sentences of a markdown text, by rule (THYM.md 7.3): front matter, fenced code, tables and rules are not
    text; a heading is a sentence of its own; a list item starts a sentence; inside a paragraph a sentence ends at
    `.`, `!` or `?` followed by space and a capital or a digit (an abbreviation such as `Dr.` does not end one). The
    closing footer paragraph (a last paragraph in italics, MacroCOSM 18.4.4 and THYM.md 14) is left out unless
    `footer`. Line numbers count the text as written, front matter included, so that a span's lines can be laid
    over them."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    start = _front_lines(lines)
    # the closing footer: the last paragraph, when it is italic throughout
    stop = len(lines)
    if not footer:
        j = len(lines) - 1
        while j >= start and not lines[j].strip():
            j -= 1
        k = j
        while k >= start and lines[k].strip():
            k -= 1
        para = [ln.strip() for ln in lines[k + 1:j + 1]]
        if para and _is_footer(" ".join(para)):
            stop = k + 1
    out: list[Sentence] = []
    buf: list[tuple[int, str]] = []
    kind = "prose"
    p = 0

    def flush() -> None:
        nonlocal buf, p
        if not buf:
            return
        joined, owners = "", []
        for ln, s in buf:
            if joined:
                joined += " "
                owners.append(ln)
            joined += s
            owners.extend([ln] * len(s))
        pos = 0
        pieces = [x for x in _SPLIT.split(joined)]
        merged: list[str] = []
        for x in pieces:
            last = merged[-1].split()[-1].lower().rstrip(".") if merged and merged[-1].split() else ""
            if merged and last in _ABBR:
                merged[-1] = f"{merged[-1]} {x}"
            else:
                merged.append(x)
        for x in merged:
            at = joined.find(x, pos)
            at = pos if at < 0 else at
            end = max(at, at + len(x) - 1)
            pos = at + len(x)
            words = plain_text(x)
            if words:
                out.append(Sentence(words, owners[min(at, len(owners) - 1)], owners[min(end, len(owners) - 1)], p,
                                    kind))
        buf = []
        p += 1

    fenced = False
    for i in range(start, stop):
        raw = lines[i]
        ln = i + 1
        if _FENCE.match(raw):
            flush()
            fenced = not fenced
            continue
        if fenced:
            continue
        s = raw.strip()
        if not s or s.startswith("|") or _RULE.match(s):
            flush()
            kind = "prose"
            continue
        if _HEADING.match(raw):
            flush()
            words = plain_text(s.lstrip("#").strip())
            if words:
                out.append(Sentence(words, ln, ln, p, "heading"))
                p += 1
            kind = "prose"
            continue
        s = re.sub(r"^(?:>\s*)+", "", s)
        if _LIST.match(s):
            if kind != "list":
                flush()
            elif buf:                               # one list, one paragraph; each item its own sentence(s)
                saved_p = p
                flush()
                p = saved_p
            kind = "list"
            s = _LIST.sub("", s)
        buf.append((ln, s))
    flush()
    return out


def claim_bearing(s: Sentence | str) -> bool:
    """A sentence that bears a claim, by rule: prose or a list item (never a heading), of three words or more, that
    does not end with a question mark. A question asserts nothing, a heading names, and a fragment of one or two words
    labels; every other sentence says something an item of the fabula must hold."""
    if isinstance(s, Sentence):
        if s.kind == "heading":
            return False
        t = s.text
    else:
        t = fold(s)
    return len(words_in(t)) >= 3 and not t.rstrip(" *_\"'”’)").endswith("?")


# ---------------------------------------------------------------------------
# A fabula, whatever form it comes in
# ---------------------------------------------------------------------------

def fabula_doc(v: Value | None) -> tuple[dict, list[dict]]:
    """A fabula's catalog and items, from a value holding an `emf/1` mapping, a loaded volume, or one item (an
    item is told as a fabula of one). `({}, [])` for anything else."""
    if v is None or not isinstance(v, Value) or v.is_nothing:
        return {}, []
    p = v.payload
    if isinstance(p, mc.Volume):
        return dict(p.catalog), [dict(it.data) for it in p.items.values()]
    if isinstance(p, dict):
        if isinstance(p.get("nodes"), list):
            return p, [n for n in p["nodes"] if isinstance(n, dict)]
        if "id" in p:
            return {"oes": (v.origin or {}).get("oes") or "emf/1", "id": "emf/item", "name": p.get("name") or p["id"],
                    "nodes": [p]}, [p]
    if isinstance(p, str):
        try:
            data = mc.yaml_load(p)
        except Exception:  # noqa: BLE001 - a text that is not YAML is no fabula
            data = None
        if isinstance(data, dict) and isinstance(data.get("nodes"), list):
            return data, [n for n in data["nodes"] if isinstance(n, dict)]
    return {}, []


def item_kind(it: dict) -> str:
    t = it.get("type")
    if isinstance(t, str) and t:
        return t
    mt = re.match(r"^[A-Z]:([a-z][a-z0-9-]*)/", str(it.get("id") or ""))
    return mt.group(1) if mt else ""


def span_lines(it: dict) -> tuple[int, int] | None:
    """An item's span as `(first line, last line)`, read however it is written (`"3"`, `"12-18"`, `"L12-L18"`)."""
    span = it.get("span")
    if not isinstance(span, dict):
        return None
    nums = [int(n) for n in re.findall(r"\d+", str(span.get("lines") or ""))]
    nums = [n for n in nums if n > 0]
    return (min(nums), max(nums)) if nums else None


def source_name(cat: dict, v: Value | None = None) -> str:
    """The text a fabula is of, as a footer names it: its `source.path`'s file name; a package's folder name when the
    fabula sits in one (its text is always `text.md`); else the fabula's name."""
    if v is not None and v.path is not None and v.path.parent.name.endswith(".thym"):
        return v.path.parent.name
    src = cat.get("source")
    p = src.get("path") if isinstance(src, dict) else None
    if isinstance(p, str) and p.strip():
        return p.replace("\\", "/").rsplit("/", 1)[-1]
    return str(cat.get("name") or "the fabula")


def text_blob(cat: dict, items: list[dict]) -> str:
    """Every word a fabula holds (its items' strings, its name and its atem), lowercased: what `no-invention` looks a
    telling's names and numbers up in."""
    out: list[str] = [str(cat.get("name") or "")]
    def walk(x: Any) -> None:
        if isinstance(x, str):
            out.append(x)
        elif isinstance(x, dict):
            for y in x.values():
                walk(y)
        elif isinstance(x, list):
            for y in x:
                walk(y)
    walk(cat.get("atem"))
    for it in items:
        walk({k: v for k, v in it.items() if k not in ("provenance", "made")})
    return " ".join(out).lower()


# ---------------------------------------------------------------------------
# What a telling carries beside its text (THYM.md 5.1: a short carries its fabula, its order and its morph)
# ---------------------------------------------------------------------------

def telling_of(v: Value | None) -> dict | None:
    """What a short made in this run carries beside its text: `{fabula, sentences, covers, order, morph}`; None for a
    short read from disk. A value's `made` is the runtime's, so this rides in `origin`, which the runtime keeps."""
    if not isinstance(v, Value):
        return None
    t = (v.origin or {}).get("telling")
    return t if isinstance(t, dict) else None


def short_value(text: str, *, fabula: Value | None, sentences: list[str] | None = None,
                covers: list[list[str]] | None = None, order: str | None = None, morph: str | None = None,
                **extra: Any) -> Value:
    """A short as a value: its markdown, and beside it what it was told from and which items each sentence says."""
    tell: dict = {"fabula": fabula, "order": order, "morph": morph or "null"}
    if sentences is not None:
        tell["sentences"] = list(sentences)
        tell["covers"] = [list(c) for c in (covers or [[] for _ in sentences])]
    tell.update(extra)
    return Value("short", text, origin={"telling": tell})


def fabula_for(output: Value, inputs: dict) -> Value | None:
    """The fabula a check reads a telling against: one among the inputs (an operand or a `with`/`of` value), else
    the one the output or an input short carries."""
    for v in inputs.values():
        if isinstance(v, Value) and v.type == "fabula":
            return v
    for v in [output, *inputs.values()]:
        t = telling_of(v)
        if t and isinstance(t.get("fabula"), Value):
            return t["fabula"]
    return None


# ---------------------------------------------------------------------------
# The sentence-to-item map (THYM.md 7.3: `coverage`, and `assert f covers t`)
# ---------------------------------------------------------------------------

_STOP = frozenset("""
about above after again against also among and another any are because been before being below between both but
came come could did does doing done down during each either even every from further gave gets give given gives had
has have having here hers into its itself just made make many more most much must near never next none nor not now
off once only onto other ought our ours out over own same said says should since some such than that their theirs
them then there these they this those though through thus till too under until upon very was were what when where
whether which while who whom whose why will with within without would year years your yours the for one two
""".split())


def _content(s: str) -> set[str]:
    out = set()
    for w in words_in(s):
        lw = w.lower().replace("’", "'")
        if lw.endswith("'s"):
            lw = lw[:-2]
        if len(lw) < 4 or lw in _STOP:
            if lw.isdigit():
                out.add(lw)
            continue
        for suf in ("ings", "ing", "ies", "es", "ed", "s"):
            if lw.endswith(suf) and len(lw) - len(suf) >= 4:
                lw = lw[: -len(suf)]
                break
        out.add(lw)
    return out


@dataclass
class CoverMap:
    """Which items of a fabula each claim-bearing sentence of a telling says. `how` is `citations` (the model cited
    them, sentence by sentence), `spans` (the author's text: an item covers the sentences its span's lines touch) or
    `words` (a short with no citations: the items whose names and content words it shares). `unknown` holds the cited
    ids no item has."""
    rows: list = field(default_factory=list)          # [(sentence text, first line or None, [ids])]
    how: str = "spans"
    unknown: list = field(default_factory=list)       # [(sentence text, [ids])]

    @property
    def missing(self) -> list[str]:
        return [s for s, _ln, ids in self.rows if not ids]

    def compact(self, limit: int = 2000) -> str:
        """The map in one line, as a trace records it: `s1→P:claim/a,E:person/b; s2→…`."""
        parts = [f"s{i}→{','.join(ids) or '-'}" for i, (_s, _ln, ids) in enumerate(self.rows, 1)]
        out = f"{len(self.rows)} claim-bearing sentences, each traced ({self.how}): " + "; ".join(parts)
        return out if len(out) <= limit else out[: limit - 1] + "…"

    def record(self) -> list[dict]:
        """The map as a fabula records it in `derived.covers`: `[{sentence, lines, items}]`."""
        out = []
        for i, (_s, span, ids) in enumerate(self.rows, 1):
            row: dict = {"sentence": i}
            if span:
                row["lines"] = f"{span[0]}" if span[0] == span[1] else f"{span[0]}-{span[1]}"
            row["items"] = list(ids)
            out.append(row)
        return out


def cover_map(fabula: Value, telling: Value) -> CoverMap:
    """The sentence-to-item map of a telling against its fabula, one computation for `coverage` and for `assert f
    covers t`. A short that carries its citations is read by them; the author's text (a `text`, or a short whose
    sha256 is the fabula's `source.sha256`) by spans; any other short by the words it shares with the items. Only
    claim-bearing sentences are mapped (`claim_bearing`), and pinned atems never cover anything: they reduce the
    text, they are not its material."""
    cat, items = fabula_doc(fabula)
    items = [it for it in items if item_kind(it) != "atem" and isinstance(it.get("id"), str)]
    ids = {it["id"] for it in items}
    t = telling_of(telling)
    cm = CoverMap()
    if t and t.get("covers") is not None:
        cm.how = "citations"
        for s, cites in zip(t.get("sentences") or [], t.get("covers") or []):
            if not claim_bearing(s):
                continue
            good = [c for c in cites if c in ids]
            bad = [c for c in cites if c not in ids]
            if bad:
                cm.unknown.append((s, bad))
            cm.rows.append((s, None, good))
        return cm
    src = cat.get("source") if isinstance(cat.get("source"), dict) else {}
    text = telling.text()
    if telling.type == "text" or (src.get("sha256") and src.get("sha256") == telling.sha256):
        cm.how = "spans"
        placed = [(span_lines(it), it) for it in items]
        quotes = []
        for it in items:
            sp = it.get("span") if isinstance(it.get("span"), dict) else {}
            q = sp.get("start")
            if isinstance(q, str) and q.strip():
                quotes.append((plain_text(q).lower(), it["id"]))
        for s in segment(text, footer=True):
            if not claim_bearing(s):
                continue
            hit = [it["id"] for ab, it in placed if ab and ab[0] <= s.last and ab[1] >= s.first]
            low = s.text.lower()
            hit += [i for q, i in quotes if q and q in low and i not in hit]
            cm.rows.append((s.text, (s.first, s.last), hit))
        return cm
    cm.how = "words"
    sigs = []
    for it in items:
        words = _content(f"{it.get('name') or ''} {it.get('summary') or ''}")
        names = {w.lower() for w in words_in(str(it.get("name") or "")) if w[:1].isupper() or w.isdigit()}
        sigs.append((it["id"], words, names))
    for s in segment(body(text)):
        if not claim_bearing(s):
            continue
        mine = _content(s.text)
        caps = {w.lower() for w in words_in(s.text)[1:] if w[:1].isupper() or w.isdigit()}
        hit = [i for i, ws, ns in sigs if len(mine & ws) >= 2 or (caps & ns)]
        cm.rows.append((s.text, (s.first, s.last), hit))
    return cm


# ---------------------------------------------------------------------------
# Stance: the words a telling says it in (THYM.md 7.2, law 3)
# ---------------------------------------------------------------------------

#: The words that say a stance, weakest first. A sentence is said at the weakest stance its words mark; a sentence
#: with none of them asserts plainly, which is `observed`. A hedge weakens as far as the ladder goes.
STANCE_MARKERS: tuple[tuple[str, re.Pattern], ...] = (
    ("hearsay", re.compile(r"\breportedly\b|\bsays?\b|\bsaid\b|\baccording to\b|\bclaims?\b|\bclaimed\b|"
                           r"\bsupposedly\b|\ballegedly\b|\brumou?red\b|\bis reported\b|\(reported\)", re.I)),
    ("hearsay", re.compile(r"\bmaybe\b|\bperhaps\b|\bseems?\b|\bseemed\b|\bmight\b|\bcould\b|\barguably\b|"
                           r"\bprobably\b|\blikely\b|\bpossibly\b|\bmay\b|\bnot sure\b|\bless sure\b", re.I)),
    ("assumed", re.compile(r"\bit is assumed\b|\bassum(?:e|es|ed|ing)\b|\bpresumably\b|\bpresum(?:e|es|ed)\b|"
                           r"\bsuppos(?:e|es|ed|ing)\b|\btaken for granted\b|\(assumed\)", re.I)),
    ("opinion", re.compile(r"\bholds? that\b|\bthinks?\b|\bthought\b|\bbelieves?\b|\bfeels?\b|\bin (?:\w+['’]s|her|"
                           r"his|their|my|our) view\b|\bopinion\b|\bjudges?\b|\bsuspects?\b|\bdoubts?\b|"
                           r"\(an opinion\)", re.I)),
    ("deduced", re.compile(r"\bit follows\b|\bfollows that\b|\btherefore\b|\bthus\b|\bhence\b|\bwould\b|"
                           r"\bbecause\b|\bif\b|\bso\b|\bimplies\b|\bmust\b|\bexplains?\b|\(reasoned\)", re.I)),
    ("observed", re.compile(r"\bobserved\b|\bsaw\b|\bcounted\b|\bmeasured\b|\bwitnessed\b|\(observed\)", re.I)),
    ("axiom", re.compile(r"\bit is given\b|\btaken as given\b|\bby definition\b|\(taken as given\)", re.I)),
)


def telling_stance(sentence: str) -> str:
    """The stance a sentence says its claim at: the weakest its words mark, else `observed` (a plain assertion)."""
    found = [st for st, rx in STANCE_MARKERS if rx.search(sentence)]
    if not found:
        return "observed"
    return min(found, key=lambda s: RANK[s])


# ---------------------------------------------------------------------------
# Reading a model's sentences, and composing a short from them
# ---------------------------------------------------------------------------

SENTENCES_SAYS = ("a YAML mapping: sentences, a list in the order told, each {say: one sentence, cites: [the ids of "
                  "the items it says]}, with paragraph: true on a sentence that starts a new paragraph")


def strip_fences(text: str) -> str:
    mt = re.search(r"```[A-Za-z0-9_-]*\s*\n(.*?)(?:\n```|$)", text, re.S)
    return mt.group(1) if mt else text


def answer_mapping(out: Any) -> dict:
    """A model's YAML answer as a mapping (fences stripped); ValueError when it is not one."""
    if isinstance(out, dict):
        return out
    data = mc.yaml_load(strip_fences(str(out or "")))
    if not isinstance(data, dict):
        raise ValueError("the answer is not a YAML mapping")
    return data


def model_of(data: dict) -> str | None:
    """The model's id, as the host's coprocessor stamps it into a YAML answer (`engine: model:<id>`)."""
    e = data.get("engine") if isinstance(data, dict) else None
    if isinstance(e, str) and e.startswith("model:") and e[6:].strip() not in ("", "unknown"):
        return e[6:].strip()
    return None


def read_sentences(out: Any) -> tuple[list[list[str]], list[list[str]]]:
    """A model's told sentences: `(paragraphs, covers)`, the paragraphs a list of lists of sentences and the covers
    one list of cited ids per sentence, in order. ValueError when the answer holds no sentence."""
    data = answer_mapping(out)
    rows = data.get("sentences")
    if not isinstance(rows, list):
        raise ValueError("the answer holds no sentences: list")
    paras: list[list[str]] = [[]]
    covers: list[list[str]] = []
    for row in rows:
        if isinstance(row, str):
            say, cites, new = row, [], False
        elif isinstance(row, dict):
            say = row.get("say") or row.get("text") or row.get("sentence") or ""
            cites = row.get("cites") if "cites" in row else row.get("cite", [])
            new = row.get("paragraph") is True
        else:
            continue
        say = fold(say)
        if not say:
            continue
        if say[-1] not in ".!?…\"”'’)":
            say += "."
        if isinstance(cites, str):
            cites = [c for c in re.split(r"[,\s]+", cites) if c]
        cites = [fold(c) for c in (cites if isinstance(cites, list) else []) if fold(c)]
        if new and paras[-1]:
            paras.append([])
        paras[-1].append(say)
        covers.append(cites)
    if not covers:
        raise ValueError("the answer holds no sentences")
    return [p for p in paras if p], covers


def compose(paragraphs: list[list[str]], footer: str | None = None, front: dict | None = None) -> str:
    """A short's markdown: front matter (a reading's), paragraphs of sentences, and the closing footer."""
    out = ""
    if front:
        out += "---\n" + mc.dump(plain(front)) + "---\n\n"
    out += "\n\n".join(" ".join(p) for p in paragraphs)
    if footer:
        out += "\n\n" + footer
    return out + "\n"


# ---------------------------------------------------------------------------
# Inputs, names and numbers
# ---------------------------------------------------------------------------

def first_input(inputs: dict, *types: str) -> Value | None:
    for v in inputs.values():
        if isinstance(v, Value) and v.type in types:
            return v
    return None


def modifiers(node: dict) -> dict:
    m = (node or {}).get("modifiers")
    return m if isinstance(m, dict) else {}


_NAMEISH = frozenset("i a an the it this that these those he she they we you".split())


def names_and_numbers(sentence: str) -> tuple[list[str], list[str]]:
    """The names a sentence uses (capitalised words past its first) and its numbers, as `no-invention` reads them."""
    ws = words_in(sentence)
    names = [w for w in ws[1:] if w[:1].isupper() and w.lower() not in _NAMEISH and not w.isupper()]
    numbers = [w for w in ws if w.isdigit()]
    return names, numbers


# ---------------------------------------------------------------------------
# Engines that call the model: every call one recorded candidate
# ---------------------------------------------------------------------------

class EngineAdapter:
    """An engine's `complete(messages, max_tokens=None) -> (text, meta)`, answered by the run's coprocessor. Each call
    is one candidate, recorded as `candidates/<node>-<k>.1.cosm`, its key the next of the node's call counter
    (`ctx.calls`, `enough.thym.engines.CallCounter`), which the node's later requests share so that no key collides;
    its input is the messages themselves, so a replay hands every answer back in order. The tokens the coprocessor
    reports are the node's (THYM.md 12.3). A refusal stops the move."""

    def __init__(self, ctx: Any, move: str) -> None:
        self.ctx = ctx
        self.move = move
        self.model: str | None = None
        self.calls = 0
        decl = ctx.decl(move) if hasattr(ctx, "decl") else None
        self.checks = [str(c) for c in (decl_get(decl, "contract") or [])]
        self._local = 0                                 # a context with no counter (a move called outside a run)

    def _key(self) -> str:
        counter = getattr(self.ctx, "calls", None)
        if counter is not None:
            return counter.model_key()
        self._local += 1
        return f"{node_number((self.ctx.node or {}).get('id'))}-{self._local}"

    def __call__(self, messages: list, max_tokens: int | None = None) -> tuple[str, dict]:
        ctx = self.ctx
        key = self._key()
        self.calls += 1
        msgs = Value("string", json.dumps(plain(messages), ensure_ascii=False, sort_keys=True))
        contract = {"move": self.move, "schema": {"format": "text", "engine": "passage"}, "checks": self.checks,
                    "repair": {"allowed": [], "failed": []}}
        budget = {"attempts": 1, "output_words": int(max_tokens or 0) // 3, "prompt_tokens_max": 0, "seconds": 600}
        cand = ask(ctx.coprocessor, contract, {"messages": (msgs, msgs.sha256)}, budget=budget, at=(key, 1))
        if isinstance(cand, Refusal):
            raise MoveError(f"the model could not be asked ({cand.check}): {cand.message}")
        counter = getattr(ctx, "calls", None)
        if counter is not None:
            counter.spend(cand.get("tokens"))
        eng = str(cand.get("engine") or "")
        if eng.startswith("model:") and eng[6:] not in ("", "unknown"):
            self.model = self.model or eng[6:]
        out = cand.get("output")
        if isinstance(out, dict):
            out = mc.dump(plain(out))
        return (out if isinstance(out, str) else str(out or "")), ({"model": self.model} if self.model else {})


def messages_value(messages: list) -> Value:
    """An engine's messages as a value: the input a passthrough prompt builder hands the model unchanged."""
    return Value("string", json.dumps(plain(messages), ensure_ascii=False, sort_keys=True))


def as_list(v: Any) -> list:
    if isinstance(v, Value):
        v = v.plain() if v.type == "list" else [v]
    if v is None:
        return []
    return list(v) if isinstance(v, (list, tuple)) else [v]


# Every module registers its moves and checks when imported; importing one imports them all. `project` stays out: it
# implements moves a MiniCOSM declares with `code:`, so `load_all` imports it from the sidecar and a host's `code:` wins.
from enough.thym.moves import doc, edit, emf, morph, pack  # noqa: E402,F401

__all__ = ["LADDER", "RANK", "SALIENCE", "CoverMap", "EngineAdapter", "MoveError", "Sentence", "claim_bearing",
           "compose", "cover_map", "engine", "fabula_doc", "fabula_for", "first_input", "fold", "item_kind",
           "names_and_numbers", "read_sentences", "segment", "short_value", "span_lines", "telling_of",
           "telling_stance", "utc_day", "wrap"]
