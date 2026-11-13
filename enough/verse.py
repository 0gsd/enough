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
    """One line of the poem: `number` counted from 1 over the poem, `src` its line in the file, its stanza; `repeats`
    is how many times a repeat mark after it (`(x2)`, `×3`) says it is sung (1 without one), the mark left out of
    `text`."""
    number: int
    src: int
    text: str
    stanza: int
    repeats: int = 1


@dataclass(frozen=True)
class Label:
    """A lyric's label (Thym 20.9): a line that is only a section's name, `verse`, `chorus`, `refrain`, `bridge`,
    `prechorus`, `intro`, `outro`, `hook` or `coda`, with or without a number, in brackets or before a colon.
    `heading` as written (`Verse 2`), `word` folded (`verse`), its `division` (`other` for the last five), and the
    repeats a mark after it says."""
    word: str
    heading: str
    division: str
    src: int
    number: str | None = None
    repeats: int = 1


@dataclass(frozen=True)
class Stanza:
    """A stanza, or a lyric's labelled section. `label` is its label (None for a stanza); `echo` the number of the
    part a label with no lines under it repeats."""
    number: int
    lines: tuple[VLine, ...]
    label: Label | None = None
    echo: int | None = None

    @property
    def start(self) -> int:
        return self.label.src if self.label is not None else self.lines[0].src

    @property
    def end(self) -> int:
        return self.lines[-1].src if self.lines else self.label.src          # type: ignore[union-attr]


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


LABEL_WORDS = ("verse", "chorus", "refrain", "bridge", "prechorus", "intro", "outro", "hook", "coda")
_DIVISION = {"verse": "verse", "chorus": "chorus", "refrain": "refrain", "bridge": "bridge"}
_W = r"verse|chorus|refrain|bridge|pre-?chorus|intro|outro|hook|coda"
_MARK = r"(?:\(\s*[x×]\s*(?P<r1>\d+)\s*\)|[x×]\s*(?P<r2>\d+))"
_LABEL = re.compile(rf"^\s*(?:\[\s*(?P<a>{_W})\.?(?:\s*(?P<an>\d+))?\s*\]|\(\s*(?P<b>{_W})(?:\s*(?P<bn>\d+))?\s*\)"
                    rf"|(?P<c>{_W})(?:\s*(?P<cn>\d+))?\s*:)\s*(?:{_MARK})?\s*$", re.I)
_REPEAT_END = re.compile(r"\s*(?:\(\s*[x×]\s*(\d+)\s*\)|×\s*(\d+)|(?<=\s)[x](\d+))\s*$")


def label_of(raw: str, src: int = 0) -> Label | None:
    """The lyric label a line is, or None (Thym 20.9)."""
    mt = _LABEL.match(raw.strip())
    if not mt:
        return None
    word = (mt.group("a") or mt.group("b") or mt.group("c")).lower().replace("-", "")
    num = mt.group("an") or mt.group("bn") or mt.group("cn")
    heading = word.capitalize() + (f" {num}" if num else "")
    rep_ = mt.group("r1") or mt.group("r2")
    return Label(word, heading, _DIVISION.get(word, "other"), src, num, int(rep_) if rep_ else 1)


def _repeat_mark(text: str) -> tuple[str, int]:
    """A line less the repeat mark after it (`(x2)`, `×3`), and how many times the mark says it is sung."""
    mt = _REPEAT_END.search(text)
    if not mt or not text[:mt.start()].strip():
        return text, 1
    n = int(next(g for g in mt.groups() if g))
    return text[:mt.start()].rstrip(), max(1, n)


def _is_header(block: list[int], rest: list[list[int]], lines: list[str]) -> bool:
    """The first block is a header (a title, a byline) when a line of it is a markdown heading; or it has at most two
    lines and every block after it is longer; or it has at most three lines and one reads as a byline (`by …`, a dash,
    a year). Never when it is the only block, nor when a line of it is a lyric's label."""
    if not rest:
        return False
    said = [lines[n - 1] for n in block]
    if any(label_of(s) for s in said):
        return False
    if any(_HEADING.match(s) for s in said):
        return True
    sizes = [k for k in (sum(1 for n in b if not label_of(lines[n - 1])) for b in rest) if k]   # a label is no line
    if len(block) <= 2 and sizes and all(k > len(block) for k in sizes):
        return True
    return len(block) <= 3 and any(_BYLINE.search(s) for s in said[1:] or said)


def read_poem(text: str) -> Poem:
    """The poem a text holds: its header set apart, then its stanzas and lines (see the module's words). A lyric's
    label opens a part of its own, inside a stanza or at its head; a label with no lines under it repeats the last
    part of its name before it (`echo`); a repeat mark after a line or a label is read off it (Thym 20.9)."""
    lines = _file_lines(text)
    blocks = _blocks(lines)
    title = header = None
    if blocks and _is_header(blocks[0], blocks[1:], lines):
        head = blocks.pop(0)
        header = (head[0], head[-1])
        title = _clean(lines[head[0] - 1]).lstrip("#").strip() or None
    stanzas: list[Stanza] = []
    k = 0
    for b in blocks:
        segs: list[tuple[Label | None, list[int]]] = []
        for n in b:
            lab = label_of(lines[n - 1], n)
            if lab is not None:
                segs.append((lab, []))
                continue
            if not segs:
                segs.append((None, []))
            segs[-1][1].append(n)
        for lab, ns in segs:
            i = len(stanzas) + 1
            vls = []
            for n in ns:
                k += 1
                said, times = _repeat_mark(_clean(lines[n - 1]))
                vls.append(VLine(k, n, said, i, times))
            echo = None
            if lab is not None and not vls:
                same = [s for s in stanzas if s.label is not None and s.lines and s.label.word == lab.word
                        and (lab.number is None or s.label.number == lab.number)]
                echo = same[-1].number if same else None
            stanzas.append(Stanza(i, tuple(vls), lab, echo))
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
        if not s.lines:
            continue
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


def said_words(line: str) -> list[str]:
    """A line's words as written (their case kept), in order: what a cue quotes."""
    return [w.replace("’", "'") for w in _WORD.findall(line.replace("-", " ").replace("—", " "))]


#: A contraction (Thym 20.9: `don't`, `I'm`, `they'd`): read as the words it joins, one syllable where it is spelled as
#: one, and only through FEED's own entry for it (contractions enter FEED by the lexicon's lane). A word FEED lacks is
#: never read without its apostrophe when it is one of these: `we'll` is not `well`.
_CONTRACTION = re.compile(r"^[a-z]+(?:n't|'m|'re|'ve|'ll)$|^(?:i|you|he|she|it|we|they|who|that|there)'d$"
                          r"|^(?:'tis|'twas|o'er|e'er|ne'er)$")


def is_contraction(word: str) -> bool:
    return bool(_CONTRACTION.match(word.lower().replace("’", "'"))) or bool(
        re.match(r"^(?:it|that|there|here|what|where|who|he|she|let)'s$", word.lower().replace("’", "'")))


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
            for cand in dict.fromkeys([w] if _CONTRACTION.match(w) else [w, w.replace("'", "")]):
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


_CLITICS = (("n't", "not"), ("'m", "am"), ("'re", "are"), ("'ve", "have"), ("'d", "would"), ("'ll", "will"),
            ("'s", "is"))
_NEG_STEMS = {"don": "do", "won": "will", "can": "can", "shan": "shall", "ain": "am"}


def joined(word: str) -> list[str] | None:
    """The words a contraction joins (`don't` → do not, `I'm` → I am, `they'd` → they would), or None."""
    w = word.lower().replace("’", "'")
    for tail, full in _CLITICS:
        if w.endswith(tail) and len(w) > len(tail):
            stem = w[:-len(tail)]
            if tail == "n't":
                stem = _NEG_STEMS.get(stem, stem[:-1] if stem.endswith("n") else stem)
            return [stem, full]
    return None


def is_function_word(word: str) -> bool:
    """A function word of the edition's list, or a contraction of function words only (`I'm`, `don't`, `they'd`:
    read as the words it joins, Thym 20.9)."""
    if word in FUNCTION_WORDS:
        return True
    parts = joined(word) if is_contraction(word) else None
    return bool(parts) and all(x in FUNCTION_WORDS for x in parts)


def word_stress(word: str, pron: Pron) -> list[str]:
    """`x`/`/` per syllable: a primary or secondary stress is `/`; an unmarked monosyllable is `/` unless it is a
    function word, or a contraction of function words."""
    out = []
    for m in pron.stresses:
        if m == "?":
            out.append("x" if is_function_word(word) else "/")
        else:
            out.append("/" if m in ("P", "S") else "x")
    return out


@dataclass
class LineScan:
    """What the rules could read of one line's sound: `stresses` (`x`/`/` per syllable) and `syllables`, or None with
    `missing` naming the words FEED does not hold; the end word and its pronunciation, when known; and each word's
    FEED entry and pronunciation (`entries`, `prons`, None where FEED lacks it)."""
    line: VLine
    words: list[str]
    stresses: list[str] | None
    missing: list[str]
    end: str | None
    end_pron: Pron | None
    end_entry: dict | None
    covered: float                     # the share of the line's words FEED held
    place: int = 1                     # the line's place in its stanza, from 1
    entries: list = field(default_factory=list)
    prons: list = field(default_factory=list)

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
        entries: list = []
        prons: list = []
        for w in ws:
            e = found.get(w)
            p = parse_ipa(e.get("ipa")) if isinstance(e, dict) else None
            entries.append(e if isinstance(e, dict) else None)
            prons.append(p)
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
                            end, p_end, e_end if isinstance(e_end, dict) else None, covered, place, entries, prons))
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


def read(text: str, pron: PronFn) -> Reading:
    """The poem, every line scanned through `pron`, the scheme stanza by stanza and the metre: what every `scan`
    reads, before it writes an item."""
    poem = read_poem(text)
    scans = scan(poem, pron)
    scheme = rhyme_scheme(poem, scans)
    lines_all = poem.lines
    rhymed = sum(len(g[1]) for g in scheme.groups) * 2 >= len(lines_all) > 0
    return Reading(poem, scans, scheme, metre(scans, rhymed=rhymed), [])


def part_ids(poem: Poem) -> dict[int, str]:
    """`{stanza number: its C:part id}`: `C:part/stanza-<n>` for a stanza, `C:part/<heading>` for a lyric's labelled
    section (`C:part/verse-2`, `C:part/chorus`; `-2`, `-3` … for one of the same heading again)."""
    out: dict[int, str] = {}
    taken: set[str] = set()
    for st in poem.stanzas:
        base = _slug(st.label.heading) if st.label is not None else f"stanza-{st.number}"
        pid, k = base, 2
        while pid in taken:
            pid, k = f"{base}-{k}", k + 1
        taken.add(pid)
        out[st.number] = f"C:part/{pid}"
    return out


def _and(xs: list) -> str:
    xs = [str(x) for x in xs]
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1] if xs else ""


def _lines_said(nums: list[int]) -> str:
    return f"line {nums[0]}" if len(nums) == 1 else f"lines {_and(nums)}"


def cue_of(words_: list[str], sep: str = " … ") -> str:
    """The words that carry a pattern, at most 60 characters (MacroCOSM OES 18.4.2): whole words, the last dropped
    until it fits."""
    ws = [w for w in words_ if w]
    while ws and len(sep.join(ws)) > 60:
        ws = ws[:-1]
    return sep.join(ws) if ws else (words_[0][:60] if words_ else "")


_PAUSE = re.compile(r"[,;:.?!]|—|–|--|\s-\s")


def pause_after(text: str) -> str | None:
    """The word a line pauses after, inside it (Thym 20.9): a mark of punctuation (a comma, a semicolon, a colon, a
    full stop, a question or exclamation mark, a dash) after its first word and before its last. None when it does
    not pause inside."""
    spans = [m.span() for m in _WORD.finditer(text.replace("’", "'"))]
    if len(spans) < 2:
        return None
    for mt in _PAUSE.finditer(text):
        before = [sp for sp in spans if sp[1] <= mt.start()]
        after = [sp for sp in spans if sp[0] >= mt.end()]
        if before and after:
            a, b = before[-1]
            return text[a:b]
    return None


def _said_part(poem: Poem, number: int) -> str:
    st = poem.stanzas[number - 1]
    name = st.label.heading if st.label is not None else f"stanza {st.number}"
    return f"{name} (lines {st.lines[0].number}-{st.lines[-1].number})" if st.lines else name


def outline_items(r: Reading, *, source: str, copyable: bool = False) -> list[dict]:
    """`scan poem` (Thym 20.9): the fabulap's outline, in module order. Every stanza and every labelled section a
    `C:part` (`refrain` for a stanza that comes back whole, a lyric's division where it is labelled, `is-a` the part
    a label alone repeats); every line a `C:line` (number, part, span, ending, `text` only when `copyable`, its
    stresses and syllables from FEED, else an open question naming the words FEED lacks); the `C:metre`; the lines
    that pause inside, one `C:device` of figure `caesura`. No rhyme letters and no scheme: `scan … as rhyme` adds
    them, and `nothing-lost` keeps what this call wrote."""
    poem, scans, m = r.poem, r.scans, r.metre
    by_num = {s.line.number: s for s in scans}
    items: list[dict] = []
    lines_all = poem.lines
    if not lines_all:
        return items
    pids = part_ids(poem)
    norms = [tuple(norm_line(vl.text) for vl in st.lines) for st in poem.stanzas]
    count = Counter(nm for nm in norms if nm)
    for st, nm in zip(poem.stanzas, norms):
        pid = pids[st.number]
        lab = st.label
        if not st.lines:                                    # a label alone: the part of its name again
            it: dict[str, Any] = {
                "id": pid, "type": "part", "name": f"{lab.heading}, again" if lab else f"Stanza {st.number}",
                "summary": (f"{lab.heading} again: the label alone, at line {st.start} of the file, repeats "
                            + (f"the {_said_part(poem, st.echo)}" if st.echo else "the part of its name")
                            + (f", sung {lab.repeats} times" if lab and lab.repeats > 1 else "") + "."),
                "stance": "observed", "division": lab.division if lab else "stanza", "number": st.number}
            if lab is not None:
                it["heading"] = lab.heading
            if st.echo:
                it["links"] = [{"rel": "is-a", "to": pids[st.echo]}]
            it["span"] = _span(st.start)
            it["provenance"] = _prov(source, st.start, None, 1.0)
            items.append(it)
            continue
        repeats = count[nm] > 1 and len(poem.stanzas) > 1
        others = [pids[s.number] for s, n2 in zip(poem.stanzas, norms) if n2 == nm and s is not st]
        name = lab.heading if lab else f"{'Refrain' if repeats else 'Stanza'} {st.number}"
        lead = (f"{name}, a refrain: its words come back as "
                f"{_and([o.split('/', 1)[1].replace('stanza-', 'stanza ') for o in others])}" if repeats else name)
        sung = f", sung {lab.repeats} times" if lab and lab.repeats > 1 else ""
        at = (f"line {st.lines[0].number}" if len(st.lines) == 1 else
              f"lines {st.lines[0].number}-{st.lines[-1].number}")
        it = {"id": pid, "type": "part", "name": name,
              "summary": f"{lead}; {at} of the poem, {len(st.lines)} line{'s' if len(st.lines) != 1 else ''}{sung}.",
              "stance": "observed",
              "division": lab.division if lab else ("refrain" if repeats else "stanza"), "number": st.number}
        if lab is not None:
            it["heading"] = lab.heading
        it["span"] = _span(st.start, st.end)
        it["provenance"] = _prov(source, st.start, st.end, 1.0)
        items.append(it)
    metre_id = f"C:metre/{_slug(m.name)}" if m else None
    governed = set(m.lines) if m else set()
    last_num = lines_all[-1].number
    for vl in lines_all:
        sc = by_num[vl.number]
        st = poem.stanzas[vl.stanza - 1]
        k = vl.number - st.lines[0].number + 1
        where = st.label.heading.lower() if st.label is not None else f"stanza {st.number}"
        it = {
            "id": f"C:line/{vl.number}", "type": "line",
            "name": vl.text if copyable and vl.text else f"line {vl.number}",
            "summary": f"Line {vl.number} of the poem, the {_ordinal(k)} of {where}"
                       + (f", sung {vl.repeats} times" if vl.repeats > 1 else "") + ".",
            "stance": "observed", "number": vl.number,
        }
        if copyable:
            it["text"] = vl.text
        it["part"] = pids[st.number]
        if metre_id and vl.number in governed:
            it["metre"] = metre_id
        if sc.stresses is not None:
            foot = m.foot if m and m.foot in FEET and vl.number in governed else None
            it["stresses"] = marks(sc.stresses, foot, (m.offsets.get(vl.number, 0) if m else 0))
            it["syllables"] = len(sc.stresses)
        else:
            if sc.missing:
                said = ", ".join(chr(34) + w + chr(34) + (", a contraction" if is_contraction(w) else "")
                                 for w in sc.missing)
                why = f"FEED does not hold {said}"
            else:
                why = "the line has no words"
            q = {"pending": f"how is line {vl.number} scanned? {why}"}
            it["stresses"] = q
            it["syllables"] = dict(q)
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
    paused = [(vl, w) for vl in lines_all if (w := pause_after(vl.text))]
    if paused:
        nums = [vl.number for vl, _w in paused]
        srcs = [vl.src for vl, _w in paused]
        after = _and([f'"{w}"' for _vl, w in paused])
        items.append({
            "id": "C:device/caesura", "type": "device",
            "name": f"Pauses inside {_lines_said(nums)}",
            "summary": f"{_lines_said(nums)[0].upper()}{_lines_said(nums)[1:]} pause{'s' if len(nums) == 1 else ''} "
                       f"inside, after {after}.",
            "stance": "observed", "figure": "caesura", "where": [f"C:line/{n}" for n in nums],
            "span": _span(min(srcs), max(srcs)), "provenance": _prov(source, min(srcs), max(srcs), 1.0),
        })
    return items


# ---------------------------------------------------------------------------
# Rhyme, at the line's end and inside it
# ---------------------------------------------------------------------------

def rhyme_letters(r: Reading) -> dict[int, Any]:
    """`{line number: its rhyme letter}`, or an open question for a line whose last word FEED lacks."""
    out: dict[int, Any] = {}
    for sc in r.scans:
        n = sc.line.number
        letter = r.scheme.letters.get(n)
        if letter:
            out[n] = letter
        elif sc.end:
            out[n] = {"pending": f"what does line {n} rhyme with? FEED does not hold \"{sc.end}\""}
    return out


def _stressed(sc: LineScan, k: int) -> bool:
    p = sc.prons[k] if k < len(sc.prons) else None
    return p is not None and "/" in word_stress(sc.words[k], p)


def inner_rhymes(sc: LineScan) -> list[tuple[list[int], str]]:
    """The inner rhymes of a line (Thym 20.9): stressed words inside it in full rhyme with its last word, or with
    another stressed word of it; `[(word indexes, the sound)]`, one group per sound. The same word twice is not a
    rhyme."""
    n = len(sc.words)
    if n < 2:
        return []
    groups: dict[str, list[int]] = {}
    for k in range(n):
        p = sc.prons[k] if k < len(sc.prons) else None
        if p is None:
            continue
        if k == n - 1 or _stressed(sc, k):
            groups.setdefault(p.rhyme, []).append(k)
    out = []
    for sound, ks in groups.items():
        ws = {sc.words[k] for k in ks}
        inside = [k for k in ks if k != n - 1]
        if len(ws) < 2 or not inside:
            continue
        out.append((ks, sound))
    return out


def rhyme_items(r: Reading, *, source: str) -> list[dict]:
    """`scan … as rhyme` (Thym 20.9): a `C:rhyme` per end-rhyme sound shared by two lines or more of a stanza
    (`full`, `slant`, `eye` or `identical`, `placement: end`), and per inner rhyme (`placement: internal`); the lines'
    letters are `rhyme_letters`."""
    poem, scans, scheme = r.poem, r.scans, r.scheme
    by_num = {s.line.number: s for s in scans}
    items: list[dict] = []
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
    for vl in poem.lines:
        sc = by_num[vl.number]
        for ks, sound in inner_rhymes(sc):
            ws = list(dict.fromkeys(sc.words[k] for k in ks))
            rid = f"C:rhyme/{_slug('-'.join(ws))}-inside-{vl.number}"
            items.append({
                "id": rid, "type": "rhyme", "name": ", ".join(ws),
                "summary": f"Inside line {vl.number}, {_and([chr(34) + w + chr(34) for w in ws])} rhyme, the sound "
                           f"-{sound}.",
                "stance": "deduced", "sound": f"-{sound}", "lines": [f"C:line/{vl.number}"], "quality": "full",
                "placement": "internal", "span": _span(vl.src), "provenance": _prov(source, vl.src, None, 0.7),
            })
    return items


# ---------------------------------------------------------------------------
# Sound: alliteration, assonance, consonance
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Syl:
    """One syllable as FEED pronounces it: its stress (`P`, `S`, `U`, or `?` for an unmarked monosyllable), the
    consonants it opens on, its vowel and the consonants it closes on."""
    stress: str
    onset: str
    vowel: str
    coda: str


_AFFRICATES = ("tʃ", "dʒ")


def _consonants(s: str) -> str:
    return "".join("g" if ch == "ɡ" else ch for ch in s if ch not in "ˈˌʰʲ")


def syllables_of(ipa: Any) -> list[Syl]:
    """FEED's IPA as syllables (the first pronunciation): each nucleus as `parse_ipa` finds it; a consonant run
    between two is split at a stress mark where there is one, else its last consonant (an affricate whole) opens the
    next syllable and the rest close the one before."""
    if not isinstance(ipa, str):
        return []
    s = ipa.strip().split(",")[0].split(";")[0]
    s = "".join(ch for ch in s if ch not in _IGNORE).strip()
    nuclei: list[tuple[int, int, str, int | None]] = []
    mark, mpos, i = "U", None, 0
    while i < len(s):
        ch = s[i]
        if ch in "ˈˌ":
            mark, mpos = ("P" if ch == "ˈ" else "S"), i
            i += 1
            continue
        if ch in _VOWELS:
            j = i + 2 if s[i:i + 2] in _DIPHTHONGS else i + 1
            nuclei.append((i, j, mark, mpos))
            mark, mpos, i = "U", None, j
            continue
        if ch == "̩" and i > 0:
            nuclei.append((i - 1, i + 1, mark, mpos))
            mark, mpos = "U", None
        i += 1
    if not nuclei:
        return []
    onsets: list[str] = []
    codas: list[str] = [""] * len(nuclei)
    prev_end = 0
    for k, (a, _b, _m, mp) in enumerate(nuclei):
        if mp is not None and mp >= prev_end:
            before, onset = s[prev_end:mp], s[mp + 1:a]
        else:
            run = _consonants(s[prev_end:a])
            if k == 0 or len(run) <= 1:
                before, onset = "", run
            elif run.endswith(_AFFRICATES):
                before, onset = run[:-2], run[-2:]
            else:
                before, onset = run[:-1], run[-1:]
        if k > 0:
            codas[k - 1] = _consonants(before)
        onsets.append(_consonants(onset))
        prev_end = nuclei[k][1]
    codas[-1] = _consonants(s[prev_end:])
    stresses = [m for _a, _b, m, _p in nuclei]
    if len(stresses) == 1 and stresses[0] == "U":
        stresses = ["?"]
    return [Syl(st, on, s[a:b].replace("̩", ""), co) for st, on, co, (a, b, _m, _p) in
            zip(stresses, onsets, codas, nuclei)]


def _onset_sound(onset: str) -> str | None:
    if not onset:
        return None
    return onset[:2] if onset.startswith(_AFFRICATES) else onset[0]


#: Sound patterns: three stressed syllables or more (this edition's thresholds, Thym 20.9; the suite pins them).
SOUND_MIN = 3


def _stressed_syllables(sc: LineScan, *, skip_end: bool) -> list[tuple[int, Syl]]:
    """`[(word index, syllable)]` for the stressed syllables of a line, one word's several kept apart; the last word
    left out when `skip_end` (the line's rhyme)."""
    out = []
    n = len(sc.words)
    for k, w in enumerate(sc.words):
        if skip_end and k == n - 1:
            continue
        e = sc.entries[k] if k < len(sc.entries) else None
        syls = syllables_of(e.get("ipa")) if isinstance(e, dict) else []
        for sy in syls:
            stressed = (sy.stress in ("P", "S")) or (sy.stress == "?" and not is_function_word(w))
            if stressed:
                out.append((k, sy))
    return out


def _pattern(rows: list[tuple[int, int, Syl]], key, said: Callable[[int, int], str]) -> dict[str, list[tuple[int, int]]]:
    """`{sound: [(line, word index)]}`: each word counted once per sound, and a word said again not counted again (the
    same word three times is a repetition, not a sound pattern)."""
    out: dict[str, list[tuple[int, int]]] = {}
    seen: dict[str, set[str]] = {}
    for ln, k, sy in rows:
        snd = key(sy)
        if not snd:
            continue
        w = said(ln, k)
        if w in seen.setdefault(snd, set()):
            continue
        seen[snd].add(w)
        out.setdefault(snd, []).append((ln, k))
    return out


_SOUND_SAID = {"alliteration": "open on", "assonance": "share the vowel", "consonance": "close on"}


def sound_items(r: Reading, *, source: str) -> list[dict]:
    """`scan … as sound` (Thym 20.9): alliteration (three stressed syllables or more opening on one consonant sound,
    in a line or across two that follow one another), assonance (three or more in a line sharing their vowel, the
    rhyme apart) and consonance (three or more in a line closing on the same consonants, rhymes apart): a `C:device`
    each, its words in `cue`, `deduced` (read through FEED's pronunciations)."""
    poem, scans = r.poem, r.scans
    by_num = {s.line.number: s for s in scans}
    items: list[dict] = []
    taken: set[str] = set()

    def add(figure: str, nums: list[int], hits: list[tuple[int, int]], sound: str) -> None:
        said = [said_words(by_num[ln].line.text) for ln in nums]
        ws = []
        for ln, k in sorted(hits):
            row = said[nums.index(ln)]
            ws.append(row[k] if k < len(row) else by_num[ln].words[k])
        base = f"{figure}-{'-'.join(map(str, nums))}"
        did = base if base not in taken else f"{base}-{_slug(sound)}"
        k2 = 2
        while did in taken:
            did, k2 = f"{base}-{k2}", k2 + 1
        taken.add(did)
        srcs = [by_num[n].line.src for n in nums]
        items.append({
            "id": f"C:device/{did}", "type": "device",
            "name": f"{figure.capitalize()} in {_lines_said(nums)}",
            "summary": f"In {_lines_said(nums)}, {len(ws)} stressed syllables {_SOUND_SAID[figure]} "
                       f"/{sound}/: {_and([chr(34) + w + chr(34) for w in ws])}.",
            "stance": "deduced", "figure": figure, "where": [f"C:line/{n}" for n in nums], "cue": cue_of(ws),
            "span": _span(min(srcs), max(srcs)), "provenance": _prov(source, min(srcs), max(srcs), 0.7),
        })

    rows_all = {vl.number: [(vl.number, k, sy) for k, sy in _stressed_syllables(by_num[vl.number], skip_end=False)]
                for vl in poem.lines}
    rows_inner = {vl.number: [(vl.number, k, sy) for k, sy in _stressed_syllables(by_num[vl.number], skip_end=True)]
                  for vl in poem.lines}
    onset = lambda sy: _onset_sound(sy.onset)            # noqa: E731
    word_at = lambda ln, k: by_num[ln].words[k]            # noqa: E731
    one: dict[int, set[str]] = {}
    for vl in poem.lines:
        for snd, hits in _pattern(rows_all[vl.number], onset, word_at).items():
            if len(hits) >= SOUND_MIN:
                one.setdefault(vl.number, set()).add(snd)
                add("alliteration", [vl.number], hits, snd)
    for a, b in zip(poem.lines, poem.lines[1:]):
        for snd, hits in _pattern(rows_all[a.number] + rows_all[b.number], onset, word_at).items():
            if snd in one.get(a.number, set()) or snd in one.get(b.number, set()):
                continue
            if len(hits) >= SOUND_MIN and {ln for ln, _k in hits} == {a.number, b.number}:
                add("alliteration", [a.number, b.number], hits, snd)
    for vl in poem.lines:
        # a vowel before an r is another sound (`then` and `there`): its key keeps the r
        for snd, hits in _pattern(rows_inner[vl.number], lambda sy: sy.vowel + ("r" if sy.coda.startswith("r")
                                                                                  else ""), word_at).items():
            if len(hits) >= SOUND_MIN:
                add("assonance", [vl.number], hits, snd)
        for snd, hits in _pattern(rows_inner[vl.number], lambda sy: sy.coda, word_at).items():
            if len(hits) >= SOUND_MIN:
                add("consonance", [vl.number], hits, snd)
    return items


# ---------------------------------------------------------------------------
# Recurrence: refrains, openings and closings, repetitions, the hook
# ---------------------------------------------------------------------------

def _all_function(ws: Iterable[str]) -> bool:
    return all(w in FUNCTION_WORDS for w in ws)


def sung_lines(poem: Poem) -> list[VLine]:
    """Every line as it is said or sung, in order: a line again for each time its repeat mark says, a part again for
    each time its label's mark says, and a label alone's part again."""
    by_number = {st.number: st for st in poem.stanzas}
    out: list[VLine] = []
    for st in poem.stanzas:
        times = st.label.repeats if st.label is not None else 1
        body = st.lines if st.lines else (by_number[st.echo].lines if st.echo else ())
        for _ in range(times):
            for vl in body:
                out += [vl] * vl.repeats
    return out


def recurrence_items(r: Reading, *, source: str) -> list[dict]:
    """`scan … as recurrence` (Thym 20.9), words folded to lowercase and their marks dropped: a line that comes back in
    another stanza (`refrain`, not within a stanza that comes back whole); two lines or more in a row that open, or
    close, on the same one to three words, not all function words (`anaphora`, `epistrophe`); a word, or a phrase of
    two words or more, said three times or more over the poem's distinct lines (`repetition`); and, in a poem with a
    refrain, a chorus or a line said three times, its `hook`: the line, or the phrase, said most often (a chorus's
    first, then the title's words, then the earliest), `deduced`, at a confidence of at most 0.5."""
    poem = r.poem
    lines_all = poem.lines
    items: list[dict] = []
    if not lines_all:
        return items
    norms = [tuple(norm_line(vl.text) for vl in st.lines) for st in poem.stanzas]
    count = Counter(nm for nm in norms if nm)
    repeated_stanzas = {st.number for st, nm in zip(poem.stanzas, norms) if nm and count[nm] > 1}
    by_norm: dict[str, list[VLine]] = {}
    for vl in lines_all:
        nm = norm_line(vl.text)
        if nm and vl.stanza not in repeated_stanzas:
            by_norm.setdefault(nm, []).append(vl)
    k = 0
    refrain_lines: set[int] = set()
    for nm, vls in by_norm.items():
        if len(vls) < 2 or len({vl.stanza for vl in vls}) < 2:
            continue
        k += 1
        nums = [vl.number for vl in vls]
        refrain_lines |= set(nums)
        srcs = [vl.src for vl in vls]
        items.append({
            "id": f"C:device/refrain-{k}", "type": "device", "name": f"A refrain, lines {', '.join(map(str, nums))}",
            "summary": f"The words of line {nums[0]} come back at line{'s' if len(nums) > 2 else ''} "
                       f"{', '.join(map(str, nums[1:]))}: a refrain.",
            "stance": "observed", "figure": "refrain", "where": [f"C:line/{n}" for n in nums],
            "span": _span(min(srcs), max(srcs)), "provenance": _prov(source, min(srcs), max(srcs), 1.0),
        })
    # openings and closings, two lines or more in a row
    ws_of = {vl.number: words(vl.text) for vl in lines_all}
    said_of = {vl.number: said_words(vl.text) for vl in lines_all}
    for figure, end in (("anaphora", False), ("epistrophe", True)):
        i = 0
        while i < len(lines_all):
            hit = None
            for n in (3, 2, 1):
                first = ws_of[lines_all[i].number]
                if len(first) < n:
                    continue
                phrase = first[-n:] if end else first[:n]
                if _all_function(phrase):
                    continue
                run = [lines_all[i]]
                for vl in lines_all[i + 1:]:
                    w = ws_of[vl.number]
                    if len(w) >= n and (w[-n:] if end else w[:n]) == phrase \
                            and norm_line(vl.text) != norm_line(run[-1].text):
                        run.append(vl)
                    else:
                        break
                if len(run) >= 2:
                    hit = (n, run)
                    break
            if hit is None:
                i += 1
                continue
            n, run = hit
            nums = [vl.number for vl in run]
            srcs = [vl.src for vl in run]
            said = [" ".join(said_of[x][-n:] if end else said_of[x][:n]) for x in nums]
            verb = "close" if end else "open"
            items.append({
                "id": f"C:device/{figure}-{nums[0]}", "type": "device",
                "name": f"Lines {_and(nums)} {verb} on \"{said[0]}\"",
                "summary": f"Lines {_and(nums)} {'all ' if len(nums) > 2 else 'both '}{verb} on the "
                           f"word{'s' if n > 1 else ''} \"{said[0]}\".",
                "stance": "observed", "figure": figure, "cue": cue_of(said), "where": [f"C:line/{x}" for x in nums],
                "span": _span(min(srcs), max(srcs)), "provenance": _prov(source, min(srcs), max(srcs), 1.0),
            })
            i += len(run)
    # repetition: over the poem's distinct lines, so a refrain is not counted again
    distinct: dict[str, VLine] = {}
    for vl in lines_all:
        distinct.setdefault(norm_line(vl.text), vl)
    seen: dict[tuple[str, ...], list[int]] = {}
    for nm, vl in distinct.items():
        ws = nm.split()
        for size in (1, 2, 3, 4):
            for a in range(0, len(ws) - size + 1):
                g = tuple(ws[a:a + size])
                if _all_function(g) or (size == 1 and len(g[0]) < 3):
                    continue
                seen.setdefault(g, []).append(vl.number)
    hits = {g: nums for g, nums in seen.items() if len(nums) >= 3}
    keep = []
    for g, nums in sorted(hits.items(), key=lambda kv: (-len(kv[0]), kv[1][0])):
        inside = any(len(h) > len(g) and len(hits[h]) == len(nums) and any(h[a:a + len(g)] == g
                                                                             for a in range(len(h) - len(g) + 1))
                     for h in hits)
        if not inside:
            keep.append((g, nums))
    keep.sort(key=lambda kv: (-len(kv[1]), kv[1][0]))
    for g, nums in keep[:6]:
        phrase = " ".join(g)
        srcs = [x.src for x in lines_all if x.number in nums]
        at = list(dict.fromkeys(nums))
        items.append({
            "id": f"C:device/repetition-{_slug(phrase)}", "type": "device",
            "name": f"\"{phrase}\", said {len(nums)} times",
            "summary": f"The {'word' if len(g) == 1 else 'words'} \"{phrase}\" {'is' if len(g) == 1 else 'are'} said "
                       f"{len(nums)} times, in {_lines_said(at)}.",
            "stance": "observed", "figure": "repetition", "cue": cue_of([phrase]),
            "where": [f"C:line/{x}" for x in at],
            "span": _span(min(srcs), max(srcs)), "provenance": _prov(source, min(srcs), max(srcs), 1.0),
        })
    hook = _hook(r, refrain_lines, repeated_stanzas)
    if hook is not None:
        nums, said, times, phrase = hook
        srcs = [x.src for x in lines_all if x.number in nums]
        name = f"\"{said}\"" if phrase else f"line {nums[0]}"
        items.append({
            "id": "C:device/hook", "type": "device", "name": name,
            "summary": (f"{'The words' if phrase else 'Line ' + str(nums[0])} {chr(34) + said + chr(34) + ' ' if phrase else ''}"
                        f"{'are' if phrase else 'is'} said {times} times, more than any other "
                        f"{'line or phrase' if phrase else 'line'}: the hook, by rule; whether it is one is asked."),
            "stance": "deduced", "figure": "hook", "cue": cue_of([said]), "where": [f"C:line/{x}" for x in nums],
            "span": _span(min(srcs), max(srcs)), "provenance": _prov(source, min(srcs), max(srcs), 0.5),
        })
    return items


def _hook(r: Reading, refrain_lines: set[int], repeated_stanzas: set[int]) -> tuple | None:
    """`(the lines it is said in, its words as written, how many times, a phrase?)`, or None in a poem with no
    refrain, no chorus and no line said three times."""
    poem = r.poem
    sung = sung_lines(poem)
    times = Counter(norm_line(vl.text) for vl in sung if norm_line(vl.text))
    chorus = any(st.label is not None and st.label.division in ("chorus", "refrain") for st in poem.stanzas)
    if not (refrain_lines or repeated_stanzas or chorus or any(c >= 3 for c in times.values())):
        return None
    title = {w for w in words(poem.title or "") if w not in FUNCTION_WORDS}
    in_chorus = {vl.number for st in poem.stanzas if st.label is not None and st.label.division in
                 ("chorus", "refrain") for vl in st.lines} | {vl.number for st in poem.stanzas
                                                              if st.number in repeated_stanzas for vl in st.lines}
    first: dict[str, VLine] = {}
    nums: dict[str, list[int]] = {}
    for vl in poem.lines:
        nm = norm_line(vl.text)
        if nm:
            first.setdefault(nm, vl)
            nums.setdefault(nm, []).append(vl.number)

    def rank(nm: str) -> tuple:
        vl = first[nm]
        return (-times[nm], 0 if vl.number in in_chorus else 1, 0 if title & set(nm.split()) else 1, vl.number)
    best = min(first, key=rank)
    best_n = times[best]
    # a phrase of two words or more said more often than any line
    grams: Counter = Counter()
    where: dict[tuple, list[int]] = {}
    for vl in sung:
        ws = words(vl.text)
        here = set()
        for size in range(2, min(6, len(ws)) + 1):
            for a in range(len(ws) - size + 1):
                here.add(tuple(ws[a:a + size]))
        for g in here:
            if not _all_function(g):
                grams[g] += 1
                where.setdefault(g, [])
                if vl.number not in where[g]:
                    where[g].append(vl.number)
    top = [g for g, c in grams.items() if c > best_n and len(where[g]) > 0]
    if top:
        g = max(top, key=lambda g: (grams[g], len(g), -min(where[g])))
        said_line = said_words(first[norm_line(next(vl.text for vl in poem.lines if vl.number == where[g][0]))].text)
        low = [w.lower() for w in said_line]
        a = next((i for i in range(len(low) - len(g) + 1) if tuple(low[i:i + len(g)]) == g), 0)
        return sorted(where[g]), " ".join(said_line[a:a + len(g)]), grams[g], True
    if best_n < 2:
        return None
    return nums[best], " ".join(said_words(first[best].text)), best_n, False


# ---------------------------------------------------------------------------
# The rules' fabulap, whole
# ---------------------------------------------------------------------------

def with_letters(items: list[dict], letters: dict[int, Any]) -> list[dict]:
    """The items with each `C:line`'s `rhyme` letter (or its open question) in place after its syllables."""
    out = []
    for it in items:
        n = it.get("number") if it.get("type") == "line" else None
        if n in letters and "rhyme" not in it:
            new: dict = {}
            for k, v in it.items():
                if k == "ending":
                    new["rhyme"] = letters[n]
                new[k] = v
            new.setdefault("rhyme", letters[n])
            it = new
        out.append(it)
    return out


def rules_items(text: str, *, source: str, pron: PronFn, copyable: bool = False) -> Reading:
    """The fabulap's rules items (MacroCOSM 18.4.6), in module order: what `scan` writes with every `as` word, run
    inside `derive … as verse` (Thym 20.9): the outline (`outline_items`), the rhymes and each line's letter
    (`rhyme_items`), the sound patterns (`sound_items`), the recurrences (`recurrence_items`) and the form
    (`verse_forms.form_item`, read from the items before it)."""
    from . import verse_forms
    r = read(text, pron)
    if not r.poem.lines:
        return r
    items = outline_items(r, source=source, copyable=copyable)
    items = with_letters(items, rhyme_letters(r)) + rhyme_items(r, source=source)
    items += sound_items(r, source=source) + recurrence_items(r, source=source)
    form = verse_forms.form_item(items, text, pron, source=source)
    if form is not None:
        items.append(form)
    order = {"part": 0, "line": 1, "metre": 2, "rhyme": 3, "form": 4, "device": 5}
    items.sort(key=lambda it: order.get(str(it.get("type")), 9))
    r.items = items
    return r


def line_table(poem: Poem) -> dict[int, int]:
    """`{file line: poem line number}`."""
    return {vl.src: vl.number for vl in poem.lines}


__all__ = ["VLine", "Label", "Stanza", "Poem", "read_poem", "label_of", "stanza_groups", "decap", "words",
           "norm_line", "said_words", "is_contraction", "feed_pronunciations", "FUNCTION_WORDS", "Pron", "parse_ipa",
           "word_stress", "LineScan", "scan", "rhyme_quality", "Scheme", "rhyme_scheme", "stanza_scheme", "FEET",
           "metre", "Metre", "marks", "Reading", "read", "part_ids", "pause_after", "outline_items", "rhyme_letters",
           "inner_rhymes", "rhyme_items", "Syl", "syllables_of", "sound_items", "sung_lines", "recurrence_items",
           "with_letters", "rules_items", "line_table", "cue_of"]
