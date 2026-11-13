"""The forms a fabulap names by rule (MacroCOSM OES 18.4.6's table; Thym 20.9, `scan … as form`).

A form is named only when the poem keeps its defining rules (its number of lines and its stanzas' shape), the first of
the table that it keeps: common metre before ballad stanza. Every rule of the form, defining or not, is listed with
whether the poem keeps it, and each line or part that breaks one is a departure. A rule over lines or stanzas holds
when three of four of them keep it (`TOLERANCE`); a count of lines holds exactly. The form's confidence is the share of
its rules held, at most 0.8. A poem that keeps no form of the table is named by its shape (`two quatrains, rhymed
aabc defe`); one with neither a metre nor a rhyme scheme is `free verse`, the table's last row.

What a form is read from is the fabula's own: each line's syllables and stresses (`C:line`), its parts (`C:part`, a
line's `part`), the metre (`C:metre`), a turn a model found (`C:device` of figure `turn`); and, from the poem and
FEED, each line's words (for a line that comes back) and whether two lines' last words rhyme, across stanzas too (a
villanelle's `aba` and terza rima's chain run from stanza to stanza). The move (`scan … as form`) and its check
(`form-grounded`) read it the same way, through the same function, `facts`.

Pure functions; the pronunciations come in as `verse.feed_pronunciations`' shape.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from . import verse as V

#: Three of four lines (or stanzas) keep a rule over lines (or stanzas) for it to hold (the design's ¾ tolerance).
TOLERANCE = 0.75
#: A form named by rule is a guess about a whole poem's shape: at most this sure.
FORM_CAP = 0.8
SHAPE_CONFIDENCE = 0.6
_NUM = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
        11: "eleven", 12: "twelve"}
_SIZE = {1: "single line", 2: "couplet", 3: "tercet", 4: "quatrain", 5: "quintain", 6: "sestet", 7: "septet",
         8: "octave"}


@dataclass
class Facts:
    """What a form is read from (the module's words). Lines by their number in the poem."""
    n: int
    parts: list[tuple[str, list[int]]]                 # (C:part id, its lines), parts that hold lines, in order
    syllables: dict[int, int | None]
    beats: dict[int, int | None]
    norm: dict[int, str]
    end: dict[int, str | None]
    rhymes: Callable[[int, int], bool | None]
    metre: dict | None                                 # the C:metre item, or None
    turns: set[int] | None                             # the lines a C:device of figure turn names; None when none
    src: dict[int, int] = field(default_factory=dict)

    def letters(self) -> dict[int, str]:
        """Each line's rhyme letter over the whole poem (a line takes the letter of the first earlier line it rhymes
        with, else the next): `?` where FEED lacks its last word."""
        out: dict[int, str] = {}
        k = 0
        for a in range(1, self.n + 1):
            hit = None
            for b in range(1, a):
                if out.get(b, "?") != "?" and self.rhymes(b, a):
                    hit = out[b]
                    break
            if hit is None and self.end.get(a) and self.rhymes(a, a) is not None:
                hit = V._letter(k)
                k += 1
            out[a] = hit or "?"
        return out

    def scheme(self) -> str:
        let = self.letters()
        return " ".join("".join(let[n] for n in ns) for _p, ns in self.parts)


def facts(items: list[dict], text: str, pron: V.PronFn) -> Facts:
    """The facts of a fabulap's items and its poem (the module's words)."""
    poem = V.read_poem(text)
    lines = {it.get("number"): it for it in items if it.get("type") == "line" and isinstance(it.get("number"), int)}
    parts: list[tuple[str, list[int]]] = []
    for it in items:
        if it.get("type") == "part":
            ns = sorted(n for n, ln in lines.items() if ln.get("part") == it.get("id"))
            if ns:
                parts.append((str(it["id"]), ns))
    parts.sort(key=lambda p: p[1][0])
    syl: dict[int, int | None] = {}
    beats: dict[int, int | None] = {}
    for n, ln in lines.items():
        s = ln.get("syllables")
        syl[n] = s if isinstance(s, int) and not isinstance(s, bool) else None
        st = ln.get("stresses")
        beats[n] = st.count("/") if isinstance(st, str) else None
    vls = {vl.number: vl for vl in poem.lines}
    ends = {vl.number: (V.words(vl.text) or [None])[-1] for vl in poem.lines}
    want = sorted({w for w in ends.values() if w})
    try:
        found = pron(want) or {} if want else {}
    except Exception:  # noqa: BLE001 - no FEED: no rhyme is known
        found = {}
    prons = {w: V.parse_ipa(e.get("ipa")) if isinstance(e, dict) else None for w, e in found.items()}
    entries = {w: e for w, e in found.items() if isinstance(e, dict)}

    def as_scan(n: int) -> V.LineScan:
        w = ends.get(n)
        return V.LineScan(vls[n], [w] if w else [], None, [], w, prons.get(w) if w else None,
                          entries.get(w) if w else None, 1.0)

    scans = {n: as_scan(n) for n in vls}

    def rhymes(a: int, b: int) -> bool | None:
        sa, sb = scans.get(a), scans.get(b)
        if sa is None or sb is None or sa.end_pron is None or sb.end_pron is None:
            return None
        if a == b:
            return True
        return V.rhyme_quality(sa, sb) is not None

    metre = next((it for it in items if it.get("type") == "metre"), None)
    turn_lines: set[int] = set()
    any_turn = False
    for it in items:
        if it.get("type") == "device" and str(it.get("figure") or "").strip().lower() == "turn":
            any_turn = True
            for ref in it.get("where") or []:
                mt = re.match(r"^C:line/(\d+)$", str(ref))
                if mt:
                    turn_lines.add(int(mt.group(1)))
    return Facts(len(poem.lines), parts, syl, beats, {n: V.norm_line(vl.text) for n, vl in vls.items()}, ends,
                 rhymes, metre, turn_lines if any_turn else None, {n: vl.src for n, vl in vls.items()})


# ---------------------------------------------------------------------------
# The rules, each `(held: bool | None, departures: [(at, what)])`; None is a rule the rules cannot read (a turn)
# ---------------------------------------------------------------------------

Result = tuple[Any, list[tuple[str, str]]]


def _line(n: int) -> str:
    return f"C:line/{n}"


def _said_syl(k: int | None) -> str:
    return _NUM.get(k, str(k)) if isinstance(k, int) else "?"


def _count(k: int) -> Callable[[Facts], Result]:
    def rule(f: Facts) -> Result:
        return f.n == k, []
    return rule


def _sizes(f: Facts) -> list[int]:
    return [len(ns) for _p, ns in f.parts]


def _all_parts(size: int, *, at_least: int = 1) -> Callable[[Facts], Result]:
    def rule(f: Facts) -> Result:
        sizes = _sizes(f)
        ok = [s == size for s in sizes]
        held = len(sizes) >= at_least and sum(ok) / len(sizes) >= TOLERANCE if sizes else False
        deps = [(p, f"{_said_syl(len(ns))} lines where the form's stanzas have {_said_syl(size)}")
                for (p, ns), good in zip(f.parts, ok) if not good]
        return held, deps
    return rule


def _shape(sizes: list[int]) -> Callable[[Facts], Result]:
    def rule(f: Facts) -> Result:
        got = _sizes(f)
        if len(got) != len(sizes):
            return False, []
        ok = [a == b for a, b in zip(got, sizes)]
        deps = [(p, f"{_said_syl(len(ns))} lines where the form has {_said_syl(want)}")
                for (p, ns), want, good in zip(f.parts, sizes, ok) if not good]
        return sum(ok) / len(ok) >= TOLERANCE, deps
    return rule


def _per_line(values: list[int], what: str, *, beats: bool = False) -> Callable[[Facts], Result]:
    """Each stanza's lines carry `values` syllables (or beats) in turn: held in three of four lines."""
    def rule(f: Facts) -> Result:
        got = f.beats if beats else f.syllables
        hits, deps, total = 0, [], 0
        for _p, ns in f.parts:
            for i, n in enumerate(ns):
                total += 1
                want = values[i % len(values)] if len(ns) == len(values) else None
                k = got.get(n)
                if want is not None and k == want:
                    hits += 1
                elif want is None:
                    deps.append((_line(n), f"a line of a stanza of {_said_syl(len(ns))} lines"))
                elif k is None:
                    deps.append((_line(n), f"a line FEED could not scan, where the pattern has {_said_syl(want)} "
                                           f"{what}"))
                else:
                    deps.append((_line(n), f"{_said_syl(k)} {what if k != 1 else what[:-1]} where the pattern has "
                                           f"{_said_syl(want)}"))
        return (total > 0 and hits / total >= TOLERANCE), deps
    return rule


def _pattern_lines(f: Facts, ns: list[int], pattern: str) -> tuple[int, list[tuple[str, str]]]:
    """How many of `ns` rhyme where `pattern` (one letter a line) says they do; the departures of the rest."""
    ok, deps = 0, []
    for i, a in enumerate(ns):
        mates = [b for j, b in enumerate(ns) if j != i and pattern[j] == pattern[i]]
        good = all(f.rhymes(a, b) is True for b in mates)
        if good:
            ok += 1
        else:
            deps.append((_line(a), f"its end does not rhyme where the scheme {pattern} has it"))
    return ok, deps


def _scheme_whole(pattern: str) -> Callable[[Facts], Result]:
    """The whole poem, line by line, rhymes as `pattern` says (spaces ignored)."""
    pat = pattern.replace(" ", "")

    def rule(f: Facts) -> Result:
        ns = list(range(1, f.n + 1))
        if len(ns) != len(pat):
            return False, []
        ok, deps = _pattern_lines(f, ns, pat)
        return ok / len(ns) >= TOLERANCE, deps
    return rule


def _scheme_first(pattern: str) -> Callable[[Facts], Result]:
    def rule(f: Facts) -> Result:
        ns = list(range(1, len(pattern) + 1))
        if f.n < len(pattern):
            return False, []
        ok, deps = _pattern_lines(f, ns, pattern)
        return ok / len(ns) >= TOLERANCE, deps
    return rule


def _scheme_each(*patterns: str) -> Callable[[Facts], Result]:
    """Every stanza rhymes as one of `patterns` (by its own lines): held in three of four lines."""
    def rule(f: Facts) -> Result:
        ok_n, total, deps = 0, 0, []
        for _p, ns in f.parts:
            best = None
            for pat in patterns:
                if len(pat) != len(ns):
                    continue
                ok, d = _pattern_lines(f, ns, pat)
                if best is None or ok > best[0]:
                    best = (ok, d)
            total += len(ns)
            if best is None:
                deps += [(_line(n), "a line of a stanza the scheme does not fit") for n in ns]
            else:
                ok_n += best[0]
                deps += best[1]
        return (total > 0 and ok_n / total >= TOLERANCE), deps
    return rule


def _even_lines_rhyme(f: Facts) -> Result:
    good, deps, quads = 0, [], [(p, ns) for p, ns in f.parts if len(ns) == 4]
    for p, ns in quads:
        if f.rhymes(ns[1], ns[3]) is True:
            good += 1
        else:
            deps.append((p, f"its second and fourth lines do not rhyme (\"{f.end.get(ns[1])}\", "
                            f"\"{f.end.get(ns[3])}\")"))
    return (bool(quads) and good / len(quads) >= TOLERANCE), deps


def _foot(foot: str, feet: int | None = None) -> Callable[[Facts], Result]:
    def rule(f: Facts) -> Result:
        m = f.metre or {}
        held = m.get("foot") == foot and m.get("basis") == "accentual-syllabic" and (feet is None or m.get("feet") == feet)
        return held, []
    return rule


def _pentameter(f: Facts) -> Result:
    hits, deps = 0, []
    for n in range(1, f.n + 1):
        b, s = f.beats.get(n), f.syllables.get(n)
        if b == 5 or (isinstance(s, int) and 9 <= s <= 11):
            hits += 1
        else:
            deps.append((_line(n), "not a line of five beats" if b is not None else "a line FEED could not scan"))
    return (f.n > 0 and hits / f.n >= TOLERANCE), deps


def _rhymed(f: Facts) -> Result:
    let = f.letters()
    seen = [x for x in let.values() if x != "?"]
    return len(seen) > len(set(seen)), []


def _no_rhyme(f: Facts) -> Result:
    let = f.letters()
    seen = [x for x in let.values() if x != "?"]
    shared = sum(1 for x in seen if seen.count(x) > 1)
    return shared * 4 < max(1, f.n), []


def _turn(at: int | None) -> Callable[[Facts], Result]:
    def rule(f: Facts) -> Result:
        if f.turns is None:
            return None, []
        return (bool(f.turns) if at is None else at in f.turns), []
    return rule


def _again(pairs: list[tuple[int, int]]) -> Callable[[Facts], Result]:
    """Line a comes back at line b, for each pair (its words, folded): held in three of four."""
    def rule(f: Facts) -> Result:
        good, deps = 0, []
        for a, b in pairs:
            if f.norm.get(a) and f.norm.get(a) == f.norm.get(b):
                good += 1
            elif b <= f.n:
                deps.append((_line(b), f"not line {a} again"))
        return (good / len(pairs) >= TOLERANCE), deps
    return rule


def _two_rhymes(f: Facts) -> Result:
    let = [x for x in f.letters().values() if x != "?"]
    return (len(let) >= 6 and len(set(let)) <= 2), []


def _sestet_sounds(f: Facts) -> Result:
    let = f.letters()
    octave = {let[n] for n in range(1, 9) if let.get(n, "?") != "?"}
    sest = [let.get(n, "?") for n in range(9, 15)]
    known = [x for x in sest if x != "?"]
    return (len(known) >= 5 and len(set(known)) in (2, 3) and not set(known) & octave), []


def _terza_tercets(f: Facts) -> Result:
    sizes = _sizes(f)
    body = sizes[:-1] if sizes and sizes[-1] in (1, 2) else sizes
    good = sum(1 for s in body if s == 3)
    return (good >= 2 and good / len(body) >= TOLERANCE if body else False), []


def _terza_chain(f: Facts) -> Result:
    tercets = [ns for _p, ns in f.parts if len(ns) == 3]
    links = list(zip(tercets, tercets[1:]))
    if not links:
        return False, []
    good, deps = 0, []
    for a, b in links:
        if f.rhymes(a[1], b[0]) is True and f.rhymes(a[1], b[2]) is True:
            good += 1
        else:
            deps.append((_line(a[1]), "its middle line does not rhyme with the outer lines of the next tercet"))
    return good / len(links) >= TOLERANCE, deps


def _closing(f: Facts) -> Result:
    sizes = _sizes(f)
    return (bool(sizes) and sizes[-1] in (1, 2)), []


def _sestina_turns(f: Facts) -> Result:
    st = [ns for _p, ns in f.parts if len(ns) == 6][:6]
    if len(st) < 2:
        return False, []
    order = [5, 0, 4, 1, 3, 2]
    good, deps = 0, []
    for a, b in zip(st, st[1:]):
        want = [f.end.get(a[i]) for i in order]
        got = [f.end.get(n) for n in b]
        if want == got:
            good += 1
        else:
            deps.append((_line(b[0]), "the stanza's end words are not the last stanza's in the order 6 1 5 2 4 3"))
    return good / (len(st) - 1) >= TOLERANCE, deps


def _sestina_envoi(f: Facts) -> Result:
    st = [ns for _p, ns in f.parts if len(ns) == 6]
    env = [ns for _p, ns in f.parts if len(ns) == 3]
    if not st or not env:
        return False, []
    six = {f.end.get(n) for n in st[0]}
    said = " ".join(f.norm.get(n, "") for n in env[-1]).split()
    return six <= set(said), []


def _pantoum_links(f: Facts) -> Result:
    quads = [ns for _p, ns in f.parts if len(ns) == 4]
    links = list(zip(quads, quads[1:]))
    if not links:
        return False, []
    good, deps = 0, []
    for a, b in links:
        if f.norm[a[1]] == f.norm[b[0]] and f.norm[a[3]] == f.norm[b[2]]:
            good += 1
        else:
            deps.append((_line(b[0]), "lines 2 and 4 of the stanza before do not come back as lines 1 and 3"))
    return good / len(links) >= TOLERANCE, deps


def _pantoum_close(f: Facts) -> Result:
    return (f.n > 1 and f.norm.get(f.n) == f.norm.get(1)), []


def _ghazal_couplets(f: Facts) -> Result:
    sizes = _sizes(f)
    good = sum(1 for s in sizes if s == 2)
    return (good >= 5 and good / len(sizes) >= TOLERANCE), []


def _ghazal_radif(f: Facts) -> Result:
    cps = [ns for _p, ns in f.parts if len(ns) == 2]
    if not cps:
        return False, []
    word = f.end.get(cps[0][0])
    ok = word and f.end.get(cps[0][1]) == word
    good = sum(1 for ns in cps[1:] if f.end.get(ns[1]) == word)
    return bool(ok) and good / max(1, len(cps) - 1) >= TOLERANCE, []


def _couplets_rhymed(f: Facts) -> Result:
    if f.n < 4:
        return False, []
    pat = "".join(V._letter(i // 2) for i in range(f.n))
    ok, deps = _pattern_lines(f, list(range(1, f.n + 1)), pat)
    return ok / f.n >= TOLERANCE, deps


def _spenser_lines(f: Facts) -> Result:
    hits, total, deps = 0, 0, []
    for _p, ns in f.parts:
        for i, n in enumerate(ns):
            total += 1
            want = 6 if i == 8 else 5
            if f.beats.get(n) == want:
                hits += 1
            else:
                deps.append((_line(n), f"not a line of {_said_syl(want)} beats"))
    return (total > 0 and hits / total >= TOLERANCE), deps


def _syllables_exact(values: list[int]) -> Callable[[Facts], Result]:
    def rule(f: Facts) -> Result:
        good = sum(1 for i, v in enumerate(values, 1) if f.syllables.get(i) == v)
        return (f.n == len(values) and good == len(values)), []
    return rule


def _free(f: Facts) -> Result:
    return ((f.metre or {}).get("basis") == "free"), []


def _ten_iambic(f: Facts) -> Result:
    return (f.n >= 10 and _foot("iamb", 5)(f)[0]), []


FORMS: list[tuple[str, list[tuple[str, Callable]], list[tuple[str, Callable]]]] = [
    ("Shakespearean sonnet", [("fourteen lines", _count(14)),
                              ("three quatrains and a couplet, as the rhymes run (abab cdcd efef gg)",
                               _scheme_whole("abab cdcd efef gg"))],
     [("iambic pentameter", _foot("iamb", 5)), ("a turn at line 13", _turn(13))]),
    ("Petrarchan sonnet", [("fourteen lines", _count(14)), ("an octave rhymed abbaabba", _scheme_first("abbaabba"))],
     [("a sestet on two or three sounds (cdecde, cdcdcd)", _sestet_sounds), ("iambic pentameter", _foot("iamb", 5)),
      ("a turn at line 9", _turn(9))]),
    ("sonnet", [("fourteen lines", _count(14)), ("of pentameter", _pentameter), ("rhymed", _rhymed)],
     [("a turn", _turn(None))]),
    ("villanelle", [("nineteen lines", _count(19)), ("five tercets and a quatrain", _shape([3, 3, 3, 3, 3, 4]))],
     [("aba throughout and abaa last", _scheme_whole("aba aba aba aba aba abaa")),
      ("line 1 again at lines 6, 12 and 18, and line 3 at 9, 15 and 19",
       _again([(1, 6), (1, 12), (1, 18), (3, 9), (3, 15), (3, 19)]))]),
    ("sestina", [("thirty-nine lines", _count(39)), ("six sestets and a tercet", _shape([6, 6, 6, 6, 6, 6, 3]))],
     [("the first stanza's six end words end every stanza's lines, each stanza taking them in the order 6 1 5 2 4 3 "
       "of the one before", _sestina_turns), ("all six in the tercet", _sestina_envoi)]),
    ("terza rima", [("tercets", _terza_tercets),
                    ("each one's middle line rhyming with the outer lines of the next (aba bcb cdc)", _terza_chain)],
     [("iambic pentameter", _foot("iamb", 5)), ("a closing line or couplet", _closing)]),
    ("rhyme royal", [("stanzas of seven lines", _all_parts(7)), ("rhymed ababbcc", _scheme_each("ababbcc"))],
     [("iambic pentameter", _foot("iamb", 5))]),
    ("ottava rima", [("stanzas of eight lines", _all_parts(8)), ("rhymed abababcc", _scheme_each("abababcc"))],
     [("iambic pentameter", _foot("iamb", 5))]),
    ("Spenserian stanza", [("stanzas of nine lines", _all_parts(9)), ("rhymed ababbcbcc", _scheme_each("ababbcbcc"))],
     [("eight lines of iambic pentameter, then one of six feet", _spenser_lines)]),
    ("common metre", [("quatrains of 8, 6, 8 and 6 syllables", _per_line([8, 6, 8, 6], "syllables"))],
     [("iambic", _foot("iamb")), ("the second and fourth lines rhyme", _even_lines_rhyme)]),
    ("long metre", [("quatrains of 8 syllables a line", _per_line([8, 8, 8, 8], "syllables"))],
     [("iambic tetrameter", _foot("iamb", 4)), ("abab or aabb", _scheme_each("abab", "aabb"))]),
    ("short metre", [("quatrains of 6, 6, 8 and 6 syllables", _per_line([6, 6, 8, 6], "syllables"))],
     [("iambic", _foot("iamb")), ("the second and fourth lines rhyme", _even_lines_rhyme)]),
    ("ballad stanza", [("quatrains of four beats and three, alternating", _per_line([4, 3, 4, 3], "beats",
                                                                                     beats=True))],
     [("the second and fourth lines rhyme", _even_lines_rhyme)]),
    ("limerick", [("five lines", _count(5)), ("rhymed aabba", _scheme_whole("aabba"))],
     [("three beats in lines 1, 2 and 5, two in lines 3 and 4", _per_line([3, 3, 2, 2, 3], "beats", beats=True)),
      ("feet of anapaests", _foot("anapaest"))]),
    ("triolet", [("eight lines", _count(8)), ("on two rhymes", _two_rhymes)],
     [("line 1 again at lines 4 and 7, and line 2 at 8", _again([(1, 4), (1, 7), (2, 8)]))]),
    ("pantoum", [("quatrains", _all_parts(4, at_least=2)),
                 ("lines 2 and 4 of each coming back as lines 1 and 3 of the next", _pantoum_links)],
     [("the last stanza ends on the poem's first line", _pantoum_close)]),
    ("ghazal", [("five couplets or more", _ghazal_couplets)],
     [("every couplet's second line ends on the same word or words, as both lines of the first do", _ghazal_radif)]),
    ("heroic couplets", [("rhymed couplets of pentameter (aabbcc …)", lambda f: (
        _couplets_rhymed(f)[0] and _pentameter(f)[0], _couplets_rhymed(f)[1]))],
     [("iambic", _foot("iamb"))]),
    ("haiku", [("three lines", _count(3))],
     [("5, 7 and 5 syllables", _syllables_exact([5, 7, 5])), ("no rhyme", _no_rhyme)]),
    ("blank verse", [("ten lines or more of iambic pentameter", _ten_iambic)], [("no rhyme scheme", _no_rhyme)]),
    ("free verse", [("no metre", _free), ("no rhyme scheme", _no_rhyme)], []),
]


def _shape_name(f: Facts) -> str:
    """A poem's shape in plain words: `two quatrains, rhymed aabc defe`, `four quatrains, rhymed abcb`."""
    sizes = _sizes(f)
    if not sizes:
        return "no lines"
    if len(set(sizes)) == 1:
        size = sizes[0]
        noun = _SIZE.get(size, f"stanza of {size} lines")
        if len(sizes) == 1:
            said = f"one {noun}" if size in _SIZE else f"one stanza of {size} lines"
        else:
            plural = f"{noun}s" if size in _SIZE else f"stanzas of {size} lines"
            said = f"{_NUM.get(len(sizes), str(len(sizes)))} {plural}"
    else:
        said = f"{_NUM.get(len(sizes), str(len(sizes)))} stanzas of {', '.join(map(str, sizes[:-1]))} and {sizes[-1]} lines"
    rhymed, _d = _rhymed(f)
    if not rhymed:
        return f"{said}, unrhymed"
    let = f.letters()
    pats = []
    for _p, ns in f.parts:
        seen: dict[str, str] = {}
        pats.append("".join("?" if let[n] == "?" else seen.setdefault(let[n], V._letter(len(seen))) for n in ns))
    if len(set(pats)) == 1 and len(pats) > 1:
        return f"{said}, rhymed {pats[0]}"
    return f"{said}, rhymed {f.scheme()}"


def form_of(f: Facts) -> dict | None:
    """The form the facts keep: `{form, rules: [{rule, held}], departures: [(at, what)], confidence, named}` (named
    False for a poem named by its shape), or None for a poem with no line."""
    if f.n == 0 or not f.parts:
        return None
    for name, defining, other in FORMS:
        got = [(text, *fn(f)) for text, fn in defining]
        if not all(held is True for _t, held, _d in got):
            continue
        got += [(text, *fn(f)) for text, fn in other]
        rules = []
        deps: list[tuple[str, str]] = []
        for text, held, d in got:
            if held is None:
                rules.append({"rule": text, "held": {"pending": f"does the poem keep {text}? a model's reading of "
                                                                f"its turn, or the author, says"}})
            else:
                rules.append({"rule": text, "held": bool(held)})
            for at, what in d:
                if (at, what) not in deps:
                    deps.append((at, what))
        decided = [r["held"] for r in rules if isinstance(r["held"], bool)]
        conf = min(FORM_CAP, sum(decided) / len(decided)) if decided else FORM_CAP
        return {"form": name, "rules": rules, "departures": deps, "confidence": round(conf, 2), "named": True}
    return {"form": _shape_name(f), "rules": [], "departures": [], "confidence": SHAPE_CONFIDENCE, "named": False}


def form_item(items: list[dict], text: str, pron: V.PronFn, *, source: str) -> dict | None:
    """`scan … as form` (Thym 20.9): the `C:form` of a fabulap's items and its poem, `deduced`, or None for a poem
    with no line."""
    f = facts([it for it in items if it.get("type") != "form"], text, pron)
    got = form_of(f)
    if got is None:
        return None
    name = got["form"]
    lines = sorted(f.src)
    a, b = f.src[lines[0]], f.src[lines[-1]]
    shape = _shape_name(f).split(",")[0]
    held = [r for r in got["rules"] if r["held"] is True]
    decided = [r for r in got["rules"] if isinstance(r["held"], bool)]
    if got["named"]:
        summary = (f"{name[0].upper()}{name[1:]} by its defining rules ({shape}); {len(held)} of its {len(decided)} "
                   f"rules read by rule held" + (", and a turn is left to a reader" if len(decided) < len(got["rules"])
                                                  else "") + ".")
    else:
        summary = f"No form of the table: {name}."
    it: dict[str, Any] = {"id": f"C:form/{V._slug(name) if got['named'] else 'shape'}", "type": "form",
                          "name": name[0].upper() + name[1:], "summary": summary, "stance": "deduced", "form": name,
                          "parts": [p for p, _ns in f.parts]}
    if f.metre is not None and isinstance(f.metre.get("id"), str):
        it["metre"] = f.metre["id"]
    it["scheme"] = f.scheme()
    if got["rules"]:
        it["rules"] = got["rules"]
    if got["departures"]:
        it["departures"] = [{"at": at, "what": what} for at, what in got["departures"]]
    it["span"] = V._span(a, b)
    it["provenance"] = V._prov(source, a, b, got["confidence"])
    return it


__all__ = ["FORMS", "Facts", "facts", "form_of", "form_item", "TOLERANCE"]
