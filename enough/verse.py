"""Verse: the rules a fabulap is read by (MacroCOSM OES 18.4.6), with no model.

A poem is split by stanza and line, not by heading and paragraph (`read_poem`): a header (a title, a byline) is set
apart, every non-blank line after it is a line of the poem, counted from 1 over the whole poem, and a blank line ends a
stanza. From that alone the rules write every `C:line` (its number, its stanza, its span, its ending, and its `text`
only when the person said the poem may be copied) and every `C:part` (a stanza; a stanza that repeats another is a
`refrain`); a line whose words come back in another stanza is a `C:device` of figure `refrain`.

Where FEED, enough's dictionary, holds a line's words, the rules also scan it: each word's syllables and stresses
from its IPA (`ˈ` primary, `ˌ` secondary; a monosyllable is stressed unless it is a function word), so the line's
`stresses` and `syllables`; its end word's rhyme sound, from the last stressed vowel to the end, so the stanza's rhyme
scheme (`C:rhyme`, full or slant, eye and identical told apart); and the commonest foot over the lines it could scan
(`C:metre`, with the lines that depart from it). Every such item is `stance: deduced`, its confidence scaled by how much
of the poem the dictionary covered. A word FEED does not hold makes that line's scansion an open question, never a
guess. Nothing here fetches anything, reads anything but the text and FEED, or calls a model.

Pure functions; `feed_pronunciations` is the only one that reads FEED (one connection, never raising).
"""

from __future__ import annotations

import re
import string
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

PronFn = Callable[[list], dict]

# ---------------------------------------------------------------------------
# The poem: header, stanzas, lines
# ---------------------------------------------------------------------------

_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+\S")
_BYLINE = re.compile(r"^\s*(?:by\s+\S|[—–-]\s*\S)|\(\s*\d{3,4}\s*\)|\b1[0-9]{3}\b|\b20[0-9]{2}\b", re.I)
_HARD_BREAK = re.compile(r"(?:\s{2,}|\\)$")


@dataclass(frozen=True)
class VLine:
    """One line of the poem: `number` counted from 1 over the poem, `src` its line in the file, its stanza."""
    number: int
    src: int
    text: str
    stanza: int


@dataclass(frozen=True)
class Stanza:
    number: int
    lines: tuple[VLine, ...]

    @property
    def start(self) -> int:
        return self.lines[0].src

    @property
    def end(self) -> int:
        return self.lines[-1].src


@dataclass(frozen=True)
class Poem:
    """`title` the header's first line (None without a header); `header` its file lines `(a, b)`."""
    title: str | None
    header: tuple[int, int] | None
    stanzas: tuple[Stanza, ...]

    @property
    def lines(self) -> list[VLine]:
        return [ln for s in self.stanzas for ln in s.lines]


def _file_lines(text: str) -> list[str]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if len(lines) > 1 and lines[-1] == "":
        lines.pop()
    return lines


def _blocks(lines: list[str]) -> list[list[int]]:
    """Runs of non-blank lines, as lists of 1-based file line numbers."""
    out: list[list[int]] = []
    run: list[int] = []
    for n, raw in enumerate(lines, 1):
        if raw.strip():
            run.append(n)
        elif run:
            out.append(run)
            run = []
    if run:
        out.append(run)
    return out


def _clean(raw: str) -> str:
    """A line as written, less a markdown hard break and the indentation; inner spacing kept."""
    return _HARD_BREAK.sub("", raw.rstrip()).strip()


def _is_header(block: list[int], rest: list[list[int]], lines: list[str]) -> bool:
    """The first block is a header (a title, a byline) when a line of it is a markdown heading; or it has at most two
    lines and every block after it is longer; or it has at most three lines and one reads as a byline (`by …`, a dash,
    a year). Never when it is the only block."""
    if not rest:
        return False
    said = [lines[n - 1] for n in block]
    if any(_HEADING.match(s) for s in said):
        return True
    if len(block) <= 2 and all(len(b) > len(block) for b in rest):
        return True
    return len(block) <= 3 and any(_BYLINE.search(s) for s in said[1:] or said)


def read_poem(text: str) -> Poem:
    """The poem a text holds: its header set apart, then its stanzas and lines (see the module's words)."""
    lines = _file_lines(text)
    blocks = _blocks(lines)
    title = header = None
    if blocks and _is_header(blocks[0], blocks[1:], lines):
        head = blocks.pop(0)
        header = (head[0], head[-1])
        title = _clean(lines[head[0] - 1]).lstrip("#").strip() or None
    stanzas: list[Stanza] = []
    k = 0
    for i, b in enumerate(blocks, 1):
        vls = []
        for n in b:
            k += 1
            vls.append(VLine(k, n, _clean(lines[n - 1]), i))
        stanzas.append(Stanza(i, tuple(vls)))
    return Poem(title, header, tuple(stanzas))


def stanza_groups(poem: Poem, max_chars: int, text: str, per_line: int = 0) -> list[tuple[int, int]]:
    """File line ranges a model reads, whole stanzas packed together up to `max_chars` (each line counted with
    `per_line` more, for the numbering it is shown with); the first one starts at the header, so the title and
    byline are read with it. A stanza longer than `max_chars` is a group of its own."""
    lines = _file_lines(text)
    out: list[tuple[int, int]] = []
    cur: tuple[int, int] | None = None
    first = poem.header[0] if poem.header else None

    def size(a: int, b: int) -> int:
        return sum(len(lines[n - 1]) + 1 + per_line for n in range(a, b + 1))

    for s in poem.stanzas:
        a = first if (first is not None and not out and cur is None) else s.start
        if cur and size(cur[0], s.end) <= max_chars:
            cur = (cur[0], s.end)
        else:
            if cur:
                out.append(cur)
            cur = (a, s.end)
    if cur:
        out.append(cur)
    return out


def decap(text: str, poem: Poem | None = None) -> str:
    """The text with each poem line's first letter lowercased (a capital that only starts a line of verse does not
    make a name), the header left as it is; for finding terms and names in a poem. Line numbers do not move."""
    poem = poem or read_poem(text)
    lines = _file_lines(text)
    for vl in poem.lines:
        raw = lines[vl.src - 1]
        m = re.search(r"[A-Za-zÀ-ɏ]", raw)
        if not m:
            continue
        word = re.match(r"[A-Za-zÀ-ɏ'’]+", raw[m.start():])
        w = word.group(0) if word else ""
        if len(w) > 1 and w.isupper():
            continue
        lines[vl.src - 1] = raw[:m.start()] + raw[m.start()].lower() + raw[m.start() + 1:]
    return "\n".join(lines) + ("\n" if text.endswith(("\n", "\r")) else "")


# ---------------------------------------------------------------------------
# Words and FEED's pronunciations
# ---------------------------------------------------------------------------

_WORD = re.compile(r"[A-Za-zÀ-ɏ]+(?:['’][A-Za-zÀ-ɏ]+)*")


def words(line: str) -> list[str]:
    """A line's words, lowercased, in order; a hyphenated word is its parts; a curly apostrophe is a straight one."""
    return [w.lower().replace("’", "'") for w in _WORD.findall(line.replace("-", " ").replace("—", " "))]


def norm_line(line: str) -> str:
    """A line folded for comparing (refrains): lowercased, its words only."""
    return " ".join(words(line))


def feed_pronunciations(ws: Iterable[str]) -> dict[str, dict | None]:
    """`{word: {word, ipa, hyphenation, perfect_rhymes, slant_rhymes} | None}` for many words on one FEED
    connection. The word's OWN row (a form such as `has` keeps its own /hæz/, not its headword's), else its row in
    FEED's forms table (pronunciation only); a user's own entry wins over FEED's. Every word None when FEED is not
    built or cannot be read: never raises."""
    want = sorted({w for w in ws if isinstance(w, str) and w})
    out: dict[str, dict | None] = dict.fromkeys(want)
    if not want:
        return out
    try:
        from . import dictionary as D
        con, has_user = D._connect()
    except Exception:  # noqa: BLE001 - no FEED: every word unknown
        return out
    try:
        for w in want:
            for cand in dict.fromkeys([w, w.replace("'", "")]):
                row, _origin = D._row(con, has_user, cand)
                if row is not None:
                    e = dict(row)
                    out[w] = {"word": cand, "ipa": e.get("ipa") or e.get("pronunciation"),
                              "hyphenation": e.get("hyphenation"),
                              "perfect_rhymes": D._parse("perfect_rhymes", e.get("perfect_rhymes")) or [],
                              "slant_rhymes": D._parse("slant_rhymes", e.get("slant_rhymes")) or []}
                    break
                r = con.execute("SELECT pronunciation FROM main.forms WHERE form = ? LIMIT 1", (cand,)).fetchone()
                if r is not None and r[0]:
                    out[w] = {"word": cand, "ipa": r[0], "hyphenation": None, "perfect_rhymes": [],
                              "slant_rhymes": []}
                    break
    except Exception:  # noqa: BLE001
        pass
    finally:
        try:
            con.close()
        except Exception:  # noqa: BLE001
            pass
    return out


# Monosyllables a line carries without a beat: articles, prepositions, conjunctions, pronouns, auxiliaries (the
# usual scansion convention; a polysyllable's stress always comes from FEED).
FUNCTION_WORDS = frozenset("""
a an the and but or nor for so yet if as than that this these those which who whom whose what when where while
of in on at by to from with into onto upon through o'er till though
i me my mine we us our you your ye thou thee thy thine he him his she her it its they them their
is am are was were be been has have had do does did doth dost hath shall should will would can could may might must art
not 'tis 'twas
""".split())

_VOWELS = set("aeiouyæɑɒɔəɛɜɪʊʌɐɘɵʉɨøœɤɯɚɝ")
_DIPHTHONGS = ("aɪ", "aʊ", "ɔɪ", "eɪ", "oʊ", "əʊ", "ɪə", "ɛə", "ʊə", "ɑɪ", "ɑʊ", "oɪ", "eə")
_IGNORE = set("/[]ː.ˑ‿()")


@dataclass(frozen=True)
class Pron:
    """One word as FEED pronounces it: a stress per syllable (`P` primary, `S` secondary, `U` none, `?` a
    monosyllable with no mark), its rhyme sound (from the last stressed vowel to the end), that vowel, and the
    consonants it ends on."""
    stresses: tuple[str, ...]
    rhyme: str
    vowel: str
    coda: str
    ipa: str
    tail: int = 1                      # syllables in the rhyme sound: 1 masculine, 2 feminine …


def parse_ipa(ipa: str) -> Pron | None:
    """FEED's IPA (`/ɪnˈvɪzəbəl/`) as syllable stresses and a rhyme sound; the first of several pronunciations.
    None when it holds no vowel."""
    if not isinstance(ipa, str):
        return None
    s = ipa.strip().split(",")[0].split(";")[0]
    s = "".join(ch for ch in s if ch not in _IGNORE).strip()
    nuclei: list[tuple[int, int, str]] = []        # (start, end, stress) in s
    mark = "U"
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "ˈ":
            mark = "P"
            i += 1
            continue
        if ch == "ˌ":
            mark = "S"
            i += 1
            continue
        if ch in _VOWELS:
            two = s[i:i + 2]
            j = i + 2 if two in _DIPHTHONGS else i + 1
            nuclei.append((i, j, mark))
            mark = "U"
            i = j
            continue
        if ch == "̩" and i > 0:          # a syllabic consonant (n̩)
            nuclei.append((i - 1, i + 1, mark))
            mark = "U"
        i += 1
    if not nuclei:
        return None
    stresses = [m for _a, _b, m in nuclei]
    if len(stresses) == 1 and stresses[0] == "U":
        stresses = ["?"]
    # the rhyme: from the last stressed nucleus, primary or secondary (`needlework` rhymes on -work), else the
    # only or the last one, to the end
    idx = max((k for k, m in enumerate(stresses) if m in ("P", "S", "?")), default=len(stresses) - 1)
    a, b, _m = nuclei[idx]
    tail = s[a:].replace("ˈ", "").replace("ˌ", "")
    vowel = s[a:b]
    coda = s[nuclei[-1][1]:].replace("ˈ", "").replace("ˌ", "")
    return Pron(tuple(stresses), tail, vowel, coda, s, len(nuclei) - idx)


def word_stress(word: str, pron: Pron) -> list[str]:
    """`x`/`/` per syllable: a primary or secondary stress is `/`; an unmarked monosyllable is `/` unless it is a
    function word."""
    out = []
    for m in pron.stresses:
        if m == "?":
            out.append("x" if word in FUNCTION_WORDS else "/")
        else:
            out.append("/" if m in ("P", "S") else "x")
    return out


@dataclass
class LineScan:
    """What the rules could read of one line's sound: `stresses` (`x`/`/` per syllable) and `syllables`, or None with
    `missing` naming the words FEED does not hold; the end word and its pronunciation, when known."""
    line: VLine
    words: list[str]
    stresses: list[str] | None
    missing: list[str]
    end: str | None
    end_pron: Pron | None
    end_entry: dict | None
    covered: float                     # the share of the line's words FEED held
    place: int = 1                     # the line's place in its stanza, from 1

    @property
    def syllables(self) -> int | None:
        return len(self.stresses) if self.stresses is not None else None


def scan(poem: Poem, pron: PronFn) -> list[LineScan]:
    """Every line scanned against FEED (`pron` is `feed_pronunciations`' shape)."""
    all_words = sorted({w for vl in poem.lines for w in words(vl.text)})
    try:
        found = pron(all_words) or {}
    except Exception:  # noqa: BLE001 - no FEED is a question per line, never a failure
        found = {}
    out = []
    for vl in poem.lines:
        ws = words(vl.text)
        stresses: list[str] = []
        missing: list[str] = []
        for w in ws:
            e = found.get(w)
            p = parse_ipa(e.get("ipa")) if isinstance(e, dict) else None
            if p is None:
                missing.append(w)
                continue
            stresses += word_stress(w, p)
        end = ws[-1] if ws else None
        e_end = found.get(end) if end else None
        p_end = parse_ipa(e_end.get("ipa")) if isinstance(e_end, dict) else None
        covered = (len(ws) - len(missing)) / len(ws) if ws else 0.0
        place = vl.number - poem.stanzas[vl.stanza - 1].lines[0].number + 1
        out.append(LineScan(vl, ws, None if missing or not ws else stresses, sorted(set(missing), key=ws.index),
                            end, p_end, e_end if isinstance(e_end, dict) else None, covered, place))
    return out


# ---------------------------------------------------------------------------
# Rhyme
# ---------------------------------------------------------------------------

# Consonants a half-rhyme hears as one: the nasals, and each voiced/voiceless pair.
_CLASS = {"m": "N", "n": "N", "ŋ": "N", "p": "P", "b": "P", "t": "T", "d": "T", "k": "K", "g": "K", "ɡ": "K",
          "f": "F", "v": "F", "s": "S", "z": "S", "θ": "H", "ð": "H", "ʃ": "J", "ʒ": "J"}


def _classes(coda: str) -> str:
    return "".join(_CLASS.get(ch, ch) for ch in coda if ch not in "ʰʲ")


def _slant(a: Pron, b: Pron) -> bool:
    """A half-rhyme, on one syllable each: the closing consonants agree (consonance, `soul`/`all`), or the vowel agrees
    and the closings are near (both open, one the other's start, or the same first consonant by class: `thyme`/`mine`,
    `soul`/`hold`, `shirt`/`work`). Longer rhyme sounds slant only through FEED's own lists."""
    if a.tail != 1 or b.tail != 1:
        return False
    ca, cb = _classes(a.coda), _classes(b.coda)
    if ca and ca == cb:
        return True
    if a.vowel != b.vowel:
        return False
    return (not ca and not cb) or ca.startswith(cb) or cb.startswith(ca) or (bool(ca) and bool(cb) and ca[0] == cb[0])


def rhyme_quality(a: LineScan, b: LineScan) -> str | None:
    """How two lines' end words rhyme: `identical` (the same word), `full` (the same sound from the last stressed
    vowel on, or FEED lists them as perfect rhymes), `slant` (FEED lists them as slant rhymes, or `_slant`), `eye`
    (spelled alike at the end, sounded apart, and no half-rhyme either: `cough`/`bough`), or None. Both end words must
    be in FEED."""
    if not (a.end and b.end and a.end_pron and b.end_pron):
        return None
    if a.end == b.end:
        return "identical"
    ea, eb = a.end_entry or {}, b.end_entry or {}
    if a.end_pron.rhyme == b.end_pron.rhyme or b.end in (ea.get("perfect_rhymes") or []) \
            or a.end in (eb.get("perfect_rhymes") or []):
        return "full"
    if b.end in (ea.get("slant_rhymes") or []) or a.end in (eb.get("slant_rhymes") or []) \
            or _slant(a.end_pron, b.end_pron):
        return "slant"
    tail = 3 if min(len(a.end), len(b.end)) > 3 else 2
    if a.end[-tail:] == b.end[-tail:]:
        return "eye"
    return None


_RANK = {"identical": 0, "full": 1, "eye": 2, "slant": 3}


@dataclass
class Scheme:
    """The rhyme letters: `letters[line number]` (absent for a line whose end word FEED lacks), and the rhyme groups
    `[(letter, [line numbers], quality)]` of two lines or more."""
    letters: dict[int, str] = field(default_factory=dict)
    groups: list[tuple[str, list[int], str]] = field(default_factory=list)


def _letter(n: int) -> str:
    alphabet = string.ascii_lowercase
    return alphabet[n % 26] + ("" if n < 26 else str(n // 26 + 1))


def rhyme_scheme(poem: Poem, scans: list[LineScan]) -> Scheme:
    """The scheme by stanza: each line's end compared with the earlier lines of its own stanza; a line that rhymes
    with one takes its letter, one that rhymes with none takes the next letter, counted on over the whole poem (the
    sick rose's second stanza is `defe`). A line whose end word FEED lacks takes no letter."""
    by_num = {s.line.number: s for s in scans}
    out = Scheme()
    group_of: dict[str, list[int]] = {}
    quality: dict[str, str] = {}
    n = 0
    for st in poem.stanzas:
        seen: list[LineScan] = []
        for vl in st.lines:
            sc = by_num[vl.number]
            if sc.end_pron is None:
                continue
            hit = None
            for prev in seen:
                q = rhyme_quality(prev, sc)
                if q and (hit is None or _RANK[q] < _RANK[hit[1]]):
                    hit = (prev, q)
            if hit:
                letter = out.letters[hit[0].line.number]
                group_of[letter].append(vl.number)
                old = quality.get(letter)
                quality[letter] = hit[1] if old is None or _RANK[hit[1]] > _RANK[old] else old
            else:
                letter = _letter(n)
                n += 1
                group_of[letter] = [vl.number]
            out.letters[vl.number] = letter
            seen.append(sc)
    out.groups = [(k, v, quality[k]) for k, v in group_of.items() if len(v) > 1]
    return out


def stanza_scheme(st: Stanza, scheme: Scheme) -> str:
    """A stanza's scheme in letters (`abcb`), `?` for a line with none."""
    return "".join(scheme.letters.get(vl.number, "?") for vl in st.lines)


# ---------------------------------------------------------------------------
# Metre
# ---------------------------------------------------------------------------

FEET = {"iamb": "x/", "trochee": "/x", "anapaest": "xx/", "dactyl": "/xx", "amphibrach": "x/x"}
FEET_ORDER = ("iamb", "trochee", "anapaest", "dactyl", "amphibrach")
ADJECTIVE = {"iamb": "Iambic", "trochee": "Trochaic", "anapaest": "Anapaestic", "dactyl": "Dactylic",
             "amphibrach": "Amphibrachic"}
LENGTH_NAME = {1: "monometer", 2: "dimeter", 3: "trimeter", 4: "tetrameter", 5: "pentameter", 6: "hexameter",
               7: "heptameter", 8: "octameter"}
FOOT_MATCH = 0.8          # a foot governs the poem when its lines match it this well on average
LINE_MATCH = 0.75         # a line below this departs from it


def _fit(stresses: list[str], foot: str) -> tuple[float, int, int]:
    """`(share of syllables that fit, feet, offset)`: the line laid on the foot repeated, from its start or with the
    first syllable missing (a headless line); the better of the two. Feet are the template's beats it reaches."""
    pat = FEET[foot]
    best = (-1.0, 0, 0)
    n = len(stresses)
    # feet: a rising foot's extra closing unstressed syllable (a feminine ending) makes no foot of its own; else a
    # part foot at either end counts as one (a catalectic or headless line keeps its foot)
    body = n - 1 if pat.endswith("/") and n > len(pat) and stresses[-1] == "x" and n % len(pat) == 1 else n
    feet = max(1, -(-body // len(pat)))
    for off in (0, 1):
        tmpl = (pat * (n // len(pat) + 3))[off:off + n]
        if not tmpl:
            continue
        share = sum(1 for s, t in zip(stresses, tmpl) if s == t) / n
        if share > best[0] + 1e-9:
            best = (share, feet, off)
    return best


def _alternating(done: list[LineScan], feet_each: list[int]) -> tuple[int, int] | None:
    """`(a, b)` when the lines alternate between two lengths stanza by stanza (odd lines `a` feet, even lines `b`),
    in at least three lines of four: common metre's four and three."""
    vals = sorted(set(feet_each))
    if len(vals) < 2:
        return None
    top = Counter(feet_each).most_common(2)
    if len(top) < 2:
        return None
    best = None
    for a, b in ((top[0][0], top[1][0]), (top[1][0], top[0][0])):
        hits = sum(1 for s, f in zip(done, feet_each) if f == (a if s.place % 2 == 1 else b))
        if hits / len(done) >= 0.75 and (best is None or hits > best[0]):
            best = (hits, a, b)
    return (best[1], best[2]) if best else None


def marks(stresses: list[str], foot: str | None, offset: int = 0) -> str:
    """The `stresses` field: `x` and `/` spaced, `|` between feet when a foot governs (`x / | x x /`)."""
    if not foot:
        return " ".join(stresses)
    size = len(FEET[foot])
    groups: list[list[str]] = []
    first = (size - offset) % size or size
    groups.append(stresses[:first])
    rest = stresses[first:]
    while rest:
        groups.append(rest[:size])
        rest = rest[size:]
    return " | ".join(" ".join(g) for g in groups if g)


@dataclass
class Metre:
    foot: str                      # one of FEET, mixed or none
    feet: int | str | None
    basis: str
    name: str
    lines: list[int]               # the scanned lines it governs
    departures: list[tuple[int, str]]
    confidence: float
    offsets: dict[int, int] = field(default_factory=dict)


def metre(scans: list[LineScan], *, rhymed: bool = False) -> Metre | None:
    """The commonest foot over the lines FEED let the rules scan: a foot whose lines match it at least 0.8 on
    average is accentual-syllabic (`Iambic tetrameter`; lines that alternate four and three feet, `Iambic tetrameter
    and trimeter, alternating`, feet `3-4`); else lines with the same number of beats (one off allowed in a quarter
    of them) are accentual (`Two beats a line`); else the same number of syllables is syllabic; else a rhymed poem
    is mixed (`Mixed metre, 3 to 5 beats a line`) and an unrhymed one free. None when no line could be scanned."""
    done = [s for s in scans if s.stresses]
    if not done:
        return None
    coverage = len(done) / len(scans)
    fits = {f: [_fit(s.stresses, f) for s in done] for f in FEET_ORDER}
    mean = {f: sum(x[0] for x in v) / len(v) for f, v in fits.items()}
    best = max(FEET_ORDER, key=lambda f: (round(mean[f], 2), -FEET_ORDER.index(f)))
    nums = [s.line.number for s in done]
    if mean[best] >= FOOT_MATCH:
        feet_each = [x[1] for x in fits[best]]
        mode, _c = Counter(feet_each).most_common(1)[0]
        alt = _alternating(done, feet_each)
        deps = []
        for s, (share, feet, _off) in zip(done, fits[best]):
            want = (alt[0] if s.place % 2 == 1 else alt[1]) if alt else mode
            if share < LINE_MATCH:
                deps.append((s.line.number, f"the stresses ({' '.join(s.stresses)}) leave the "
                                            f"{ADJECTIVE[best].lower()} pattern"))
            elif feet != want:
                deps.append((s.line.number, f"{feet} feet where the pattern has {want}"))
        if alt:
            lo, hi = sorted(alt)
            feet_said: int | str = f"{lo}-{hi}"
            name = (f"{ADJECTIVE[best]} {LENGTH_NAME.get(alt[0], f'{alt[0]}-foot')} and "
                    f"{LENGTH_NAME.get(alt[1], f'{alt[1]}-foot')}, alternating")
        else:
            feet_said = mode
            name = f"{ADJECTIVE[best]} {LENGTH_NAME.get(mode, f'{mode}-foot line')}"
        conf = min(0.8, 0.3 + 0.5 * coverage * mean[best])
        return Metre(best, feet_said, "accentual-syllabic", name, nums, deps, round(conf, 2),
                     {s.line.number: x[2] for s, x in zip(done, fits[best])})
    beats = [s.stresses.count("/") for s in done]
    mode, count = Counter(beats).most_common(1)[0]
    if count / len(beats) >= 0.75 and max(beats) - min(beats) <= 2 and all(abs(b - mode) <= 1 for b in beats) \
            and len(done) > 1:
        deps = [(s.line.number, f"{b} beats where the others have {mode}") for s, b in zip(done, beats) if b != mode]
        words_n = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six"}.get(mode, str(mode))
        conf = min(0.7, 0.3 + 0.4 * coverage * count / len(beats))
        return Metre("mixed", mode, "accentual", f"{words_n} beat{'s' if mode != 1 else ''} a line", nums, deps,
                     round(conf, 2))
    sylls = [len(s.stresses) for s in done]
    smode, scount = Counter(sylls).most_common(1)[0]
    if scount / len(sylls) >= 0.75 and len(done) > 1:
        deps = [(s.line.number, f"{n} syllables where the others have {smode}") for s, n in zip(done, sylls)
                if n != smode]
        return Metre("none", None, "syllabic", f"{smode} syllables a line", nums, deps,
                     round(min(0.6, 0.3 + 0.3 * coverage), 2))
    if rhymed:
        lo, hi = min(beats), max(beats)
        return Metre("mixed", f"{lo}-{hi}" if lo != hi else lo, "accentual",
                     f"Mixed metre, {lo} to {hi} beats a line", nums, [], round(min(0.5, 0.2 + 0.3 * coverage), 2))
    return Metre("none", None, "free", "Free verse", nums, [], round(min(0.6, 0.3 + 0.3 * coverage), 2))


# ---------------------------------------------------------------------------
# The rules' items
# ---------------------------------------------------------------------------

def _span(a: int, b: int | None = None) -> dict:
    return {"lines": f"{a}" if b is None or b == a else f"{a}-{b}"}


def _loc(source: str, a: int, b: int | None = None) -> str:
    return f"{source}#L{a}" if b is None or b == a else f"{source}#L{a}-L{b}"


def _prov(source: str, a: int, b: int | None, confidence: float, state: str = "known") -> dict:
    return {"mode": "derived", "sources": [_loc(source, a, b)], "confidence": round(confidence, 2), "state": state}


def _slug(s: str) -> str:
    out = "-".join(re.findall(r"[a-z0-9]+", s.lower()))
    return out[:48].rstrip("-") or "x"


def _ending(vl: VLine, last: bool) -> str:
    return "stopped" if last or re.search(r"[.,;:!?…—–)\]\"'”’]$", vl.text) else "run-on"


def _ordinal(n: int) -> str:
    return {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh",
            8: "eighth", 9: "ninth", 10: "tenth"}.get(n, f"{n}th")


@dataclass
class Reading:
    """What the rules read of a poem: the poem, its scans, scheme and metre, and the items."""
    poem: Poem
    scans: list[LineScan]
    scheme: Scheme
    metre: Metre | None
    items: list[dict]


def rules_items(text: str, *, source: str, pron: PronFn, copyable: bool = False) -> Reading:
    """The fabulap's rules items, in module order (C first among themselves: parts, lines, metre, rhymes, devices):

    - `C:part/stanza-<n>`: every stanza (`refrain` when its words repeat another stanza's), `observed`, confidence 1;
    - `C:line/<n>`: every line, `observed`: number, part, span, ending; `text` only when `copyable`; with FEED's
      help `stresses`, `syllables`, `rhyme` and `metre`, else an open question naming the words FEED lacks
      (confidence 0.7 when scanned, 1 when only its place is written);
    - `C:metre/<slug>`: the commonest foot over the scanned lines, `deduced`, its departures; an open question when
      no line could be scanned;
    - `C:rhyme/<slug>`: one per rhyme sound shared by two lines or more, `deduced`, `full`, `slant`, `eye` or
      `identical`, `placement: end`;
    - `C:device/refrain-<n>`: a line whose words come back in another stanza, `observed`.
    """
    poem = read_poem(text)
    scans = scan(poem, pron)
    scheme = rhyme_scheme(poem, scans)
    lines_all = poem.lines
    rhymed = sum(len(g[1]) for g in scheme.groups) * 2 >= len(lines_all) > 0
    m = metre(scans, rhymed=rhymed)
    by_num = {s.line.number: s for s in scans}
    items: list[dict] = []
    if not lines_all:
        return Reading(poem, scans, scheme, m, items)
    # stanzas, and whole stanzas that repeat
    norms = [tuple(norm_line(vl.text) for vl in st.lines) for st in poem.stanzas]
    count = Counter(norms)
    first_of = {}
    for st, nm in zip(poem.stanzas, norms):
        first_of.setdefault(nm, st.number)
    for st, nm in zip(poem.stanzas, norms):
        repeats = count[nm] > 1 and any(nm) and len(poem.stanzas) > 1
        sch = stanza_scheme(st, scheme)
        lead = (f"Stanza {st.number}, a refrain: its words come back as stanza "
                f"{', '.join(str(s.number) for s, n2 in zip(poem.stanzas, norms) if n2 == nm and s is not st)}"
                if repeats else f"Stanza {st.number}")
        rhymed = f", rhymed {sch}" if sch.strip("?") else ""
        items.append({
            "id": f"C:part/stanza-{st.number}", "type": "part",
            "name": f"{'Refrain' if repeats else 'Stanza'} {st.number}",
            "summary": f"{lead}; lines {st.lines[0].number}-{st.lines[-1].number} of the poem, "
                       f"{len(st.lines)} line{'s' if len(st.lines) != 1 else ''}{rhymed}.",
            "stance": "observed", "division": "refrain" if repeats else "stanza", "number": st.number,
            "span": _span(st.start, st.end), "provenance": _prov(source, st.start, st.end, 1.0),
        })
    metre_id = f"C:metre/{_slug(m.name)}" if m else None
    governed = set(m.lines) if m else set()
    last_num = lines_all[-1].number
    for vl in lines_all:
        sc = by_num[vl.number]
        st = poem.stanzas[vl.stanza - 1]
        k = vl.number - st.lines[0].number + 1
        it: dict[str, Any] = {
            "id": f"C:line/{vl.number}", "type": "line",
            "name": vl.text if copyable and vl.text else f"line {vl.number}",
            "summary": f"Line {vl.number} of the poem, the {_ordinal(k)} of stanza {st.number}.",
            "stance": "observed", "number": vl.number,
        }
        if copyable:
            it["text"] = vl.text
        it["part"] = f"C:part/stanza-{st.number}"
        if metre_id and vl.number in governed:
            it["metre"] = metre_id
        if sc.stresses is not None:
            foot = m.foot if m and m.foot in FEET and vl.number in governed else None
            it["stresses"] = marks(sc.stresses, foot, (m.offsets.get(vl.number, 0) if m else 0))
            it["syllables"] = len(sc.stresses)
        else:
            why = (f"FEED does not hold {', '.join(chr(34) + w + chr(34) for w in sc.missing)}"
                   if sc.missing else "the line has no words")
            q = {"pending": f"how is line {vl.number} scanned? {why}"}
            it["stresses"] = q
            it["syllables"] = dict(q)
        letter = scheme.letters.get(vl.number)
        if letter:
            it["rhyme"] = letter
        elif sc.end:
            it["rhyme"] = {"pending": f"what does line {vl.number} rhyme with? FEED does not hold \"{sc.end}\""}
        it["ending"] = _ending(vl, vl.number == last_num)
        it["span"] = _span(vl.src)
        it["provenance"] = _prov(source, vl.src, None, 0.7 if sc.stresses is not None else 1.0)
        items.append(it)
    first_src, last_src = lines_all[0].src, lines_all[-1].src
    if m:
        scanned = len(m.lines)
        it = {
            "id": metre_id, "type": "metre", "name": m.name,
            "summary": (f"{m.name}, read from FEED's stresses over the {scanned} of {len(lines_all)} lines it could "
                        f"scan; a best guess, not the poet's word."),
            "stance": "deduced", "foot": m.foot,
        }
        if m.feet is not None:
            it["feet"] = m.feet
        it["basis"] = m.basis
        it["lines"] = [f"C:line/{n}" for n in m.lines]
        if m.departures:
            it["departures"] = [{"line": f"C:line/{n}", "what": what} for n, what in m.departures]
        it["span"] = _span(first_src, last_src)
        it["provenance"] = _prov(source, first_src, last_src, m.confidence)
        items.append(it)
    else:
        items.append({
            "id": "C:metre/unscanned", "type": "metre", "name": "The metre, not scanned",
            "summary": "No line could be scanned: FEED does not hold enough of the poem's words.",
            "stance": "assumed",
            "foot": {"pending": "what metre governs the poem? FEED holds too few of its words to scan a line"},
            "span": _span(first_src, last_src),
            "provenance": _prov(source, first_src, last_src, 0.3, "pending"),
        })
    for letter, nums, quality in scheme.groups:
        ends = [by_num[n].end for n in nums]
        sound = by_num[nums[0]].end_pron.rhyme if by_num[nums[0]].end_pron else ""
        uniq = list(dict.fromkeys(e for e in ends if e))
        name = ", ".join(uniq)
        exact = all((by_num[n].end_entry or {}).get("word") == by_num[n].end for n in nums)
        conf = {"identical": 0.9, "full": 0.9, "eye": 0.5, "slant": 0.6}[quality] * (1.0 if exact else 0.8)
        srcs = [by_num[n].line.src for n in nums]
        said = {"full": "rhyme", "identical": "end on the same word", "eye": "rhyme to the eye, not the ear",
                "slant": "half-rhyme"}[quality]
        rid = f"C:rhyme/{_slug('-'.join(uniq)) or letter}"
        if any(x["id"] == rid for x in items):          # the same sound again, in a later stanza
            rid = f"{rid}-{letter}"
        items.append({
            "id": rid, "type": "rhyme", "name": name,
            "summary": f"Lines {', '.join(str(n) for n in nums)} {said}: {name}, the sound -{sound}.",
            "stance": "deduced", "scheme": letter, "sound": f"-{sound}",
            "lines": [f"C:line/{n}" for n in nums], "quality": quality, "placement": "end",
            "span": _span(min(srcs), max(srcs)),
            "provenance": _prov(source, min(srcs), max(srcs), conf),
        })
    # a line whose words come back in another stanza (not within a repeated whole stanza)
    repeated_stanzas = {st.number for st, nm in zip(poem.stanzas, norms) if count[nm] > 1}
    by_norm: dict[str, list[VLine]] = {}
    for vl in lines_all:
        nm = norm_line(vl.text)
        if nm and vl.stanza not in repeated_stanzas:
            by_norm.setdefault(nm, []).append(vl)
    k = 0
    for nm, vls in by_norm.items():
        stanzas = {vl.stanza for vl in vls}
        if len(vls) < 2 or len(stanzas) < 2:
            continue
        k += 1
        nums = [vl.number for vl in vls]
        srcs = [vl.src for vl in vls]
        items.append({
            "id": f"C:device/refrain-{k}", "type": "device", "name": f"A refrain, lines {', '.join(map(str, nums))}",
            "summary": f"The words of line {nums[0]} come back at line{'s' if len(nums) > 2 else ''} "
                       f"{', '.join(map(str, nums[1:]))}: a refrain.",
            "stance": "observed", "figure": "refrain", "where": [f"C:line/{n}" for n in nums],
            "span": _span(min(srcs), max(srcs)), "provenance": _prov(source, min(srcs), max(srcs), 1.0),
        })
    return Reading(poem, scans, scheme, m, items)


def line_table(poem: Poem) -> dict[int, int]:
    """`{file line: poem line number}`."""
    return {vl.src: vl.number for vl in poem.lines}


__all__ = ["VLine", "Stanza", "Poem", "read_poem", "stanza_groups", "decap", "words", "norm_line",
           "feed_pronunciations", "FUNCTION_WORDS", "Pron", "parse_ipa", "word_stress", "LineScan", "scan",
           "rhyme_quality", "Scheme", "rhyme_scheme", "stanza_scheme", "FEET", "metre", "Metre", "marks",
           "Reading", "rules_items", "line_table"]
