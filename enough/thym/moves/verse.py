"""The fabulap's helper moves (Thym 20.9; MacroCOSM OES 18.4.6): `scan` by rule, `construe` by a model.

- `scan poem` (rules, no model): the fabulap's outline, `completeness: outline`: the header set apart; each stanza and
  each labelled section of a lyric a `C:part`; each line a `C:line` with its stresses and syllables from FEED's
  pronunciations (the `pron` engine, recorded like FEED's); the `C:metre`; the lines that pause inside, one `C:device`
  of figure `caesura` (`enough.verse.outline_items`).
- `scan poem as rhyme | sound | recurrence | form with f` (rules): adds to the fabulap it is given, never changing
  what is there: the rhymes and each line's letter; alliteration, assonance, consonance; refrains, openings and
  closings, repetitions, the hook; the `C:form` (`enough.verse`, `enough.verse_forms`).
- `construe poem as figure | image | allusion | voice | turn | meaning | ambiguity with f` (asks): one axis of the
  poem read by a model under contract, one request (by stanzas when the poem is longer than one), its prompts in
  `enough.fabulap_prompts`. What it writes keeps the stance the poem gives it: a reading is the model's `opinion`, at
  most 0.5, with no `intended`; an aim, an occasion or an influence the poem does not state is `assumed`, at most
  0.5, pending; the speaker is never the poet on a model's word. `parse_construe` holds a reply to that before the
  checks read it; what cannot be held is dropped, never guessed.
- `derive poem as verse with f` (asks; reached through `emf.derive`): what the poem says, against the fabulap so far:
  terms, names, ideas, claims, events, each stanza's atem and the poem's, and what the header states of its maker,
  occasion and appearance. Figure, image, voice and meaning are construe's.

The checks registered here: `lines-found`, `scansion-grounded`, `sound-grounded`, `form-grounded` (Thym 7.3), and the
readings of `coverage`, `no-invention` and `stance-kept` for verse, one per `construe` axis (Thym 20.9's table).
`nothing-lost` is gather's (`edit.py`), read against the `with` the call was given.

The rules themselves are enough's (`enough.verse`, `enough.verse_forms`), reached through the host's `verse` engine
(`enough.thym_host.verse_engine`), plain data in and out: a run records each call and a replay needs neither the rules
nor FEED, and this package imports nothing of enough's beyond the runtime and the MacroCOSM reader.

Nothing here reads anything but the poem, the fabulap and FEED's pronunciations, or sends a person's text anywhere but
through the declared, contracted model calls.
"""
from __future__ import annotations

import copy
import re
from typing import Any

from enough import macrocosm as mc
from enough.thym.checks import check
from enough.thym.moves import (EngineAdapter, MoveError, answer_mapping, engine, fabula_doc, first_input, fold,
                               item_kind, messages_value, model_of, span_lines)
from enough.thym.registry import Request, implements
from enough.thym.values import Value, plain

SCAN_AS = ("rhyme", "sound", "recurrence", "form")
CONSTRUE_AS = ("figure", "image", "allusion", "voice", "turn", "meaning", "ambiguity")
#: The kinds and figures `scan` writes: no other call changes them (`nothing-lost`), and a model's item of the same id
#: is dropped, never merged in.
RULE_KINDS = frozenset(("part", "line", "metre", "rhyme", "form"))
SCAN_FIGURES = frozenset(("caesura", "alliteration", "assonance", "consonance", "refrain", "anaphora", "epistrophe",
                          "repetition", "hook"))
#: What each construe axis may write, as `module:kind`; anything else in a reply is left out.
AXIS_KINDS = {
    "figure": {"C:device", "P:reading"},
    "image": {"C:device", "E:person", "E:org", "E:place", "E:work", "E:thing"},
    "allusion": {"I:allusion", "I:influence", "I:occasion"},
    "voice": {"C:voice"},
    "turn": {"C:device"},
    "meaning": {"P:reading", "K:concept", "N:aim"},
    "ambiguity": {"P:reading", "L:term", "C:device"},
}
#: What `derive poem as verse with f` may write (MacroCOSM OES 18.4.6's table, sense and reference).
SENSE_KINDS = {"L:term", "E:person", "E:org", "E:place", "E:work", "E:thing", "K:concept", "P:claim", "T:event",
               "X:atem", "R:maker", "R:release", "I:occasion"}
#: Intent and inspiration a poem does not state: a model's guess, held open (Thym 20.9, `stance-kept`).
INTENT_KINDS = frozenset(("N:aim", "N:audience", "N:decision", "N:exclusion", "I:influence"))
SENSES = ("sight", "hearing", "touch", "taste", "smell", "movement")
OPINION_CAP = 0.5
DEDUCED_CAP = 0.7
#: A poem longer than this is read by stanzas, one request each (Thym 20.9).
CONSTRUE_CHARS = 6000
CUE_MAX = 60
MODULE_ORDER = "ILEKNCRPTXD"
SPEAKER_ASKS = "who speaks the poem: the poet, or a figure the poem makes?"
CONSTRUE_SAYS = "a YAML mapping, nodes: a list of fabula items, along the one axis the request names"
_ID = re.compile(r"^([A-Z]):([a-z][a-z0-9-]*)/([A-Za-z0-9](?:[A-Za-z0-9._@-]*[A-Za-z0-9_@-])?)$")
_QUOTED = re.compile(r"[\"“]([^\"”]{2,80})[\"”]")


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

def _pron(ctx: Any):
    p = (getattr(ctx, "engines", None) or {}).get("pron")
    return p if callable(p) else None


def _verse(ctx: Any) -> Any:
    return engine(ctx, "verse")


_WORD = re.compile(r"[A-Za-zÀ-ɏ]+(?:['’][A-Za-zÀ-ɏ]+)*")


def words(line: str) -> list[str]:
    """A line's words as the verse rules fold them: lowercased, a hyphenated word its parts, apostrophes straight."""
    return [w.lower().replace("’", "'") for w in _WORD.findall(str(line).replace("-", " ").replace("—", " "))]


def layout(ctx: Any, text: str) -> dict:
    """The poem's lines, parts, header, labels and request groups (`verse_engine().layout`)."""
    return _verse(ctx).layout(text, chars=CONSTRUE_CHARS)


def _line_src(lay: dict) -> dict[int, int]:
    return {int(n): int(src) for n, src, _p in lay.get("lines") or []}


def _poem_text(poem: Value, move: str) -> str:
    if not isinstance(poem, Value) or poem.type not in ("text", "short"):
        raise MoveError(f"{move} reads a poem: a text")
    return poem.text()


def _name_of(poem: Value) -> str:
    return poem.path.name if poem.path is not None else "poem.txt"


def _stamp(ctx: Any) -> str:
    now = getattr(ctx, "now", None)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ") if now is not None else "1970-01-01T00:00:00Z"


def _program(ctx: Any) -> str | None:
    p = getattr(ctx, "program", None)
    if p is None:
        return None
    return getattr(p, "name", None) or str(p).replace("\\", "/").rsplit("/", 1)[-1]


def _run_entry(ctx: Any, model: str | None = None) -> dict:
    run = {"program": _program(ctx), "run": getattr(ctx, "run", None), "at": _stamp(ctx), "model": model}
    return {k: v for k, v in run.items() if v}


def _fabulap(w: Any, said: str) -> tuple[dict, list[dict]]:
    """The fabulap a call adds to, as plain mappings; a MoveError in the program's words otherwise."""
    if not isinstance(w, Value) or w.type != "fabula":
        raise MoveError(said)
    cat, items = fabula_doc(w)
    fl = cat.get("flavour") if isinstance(cat.get("flavour"), str) else "fabulan"
    if fl != "fabulap":
        what = {"fabulan": "the fabula of a text", "fabulac": "a folder's fabula"}.get(fl, fl)
        raise MoveError(f"the fabula given is a {fl}, {what}; only a fabulap, a poem's fabula, is taken here")
    return {k: plain(x) for k, x in cat.items() if k != "nodes"}, [plain(it) for it in items]


def _same_poem(cat: dict, poem: Value) -> None:
    src = cat.get("source") if isinstance(cat.get("source"), dict) else {}
    sha = src.get("sha256")
    if isinstance(sha, str) and sha and sha != poem.sha256:
        raise MoveError(f"the fabulap given is of another text ({src.get('path') or 'its source'}), not of this poem")


def _ordered(items: list[dict]) -> list[dict]:
    """Items in MacroCOSM's module order, each module's in the order they came."""
    rank = {m: i for i, m in enumerate(MODULE_ORDER)}
    return sorted(items, key=lambda it: rank.get(str(it.get("id", "?"))[:1], 99))


def _prov_last(it: dict) -> dict:
    if "provenance" in it:
        it = {**{k: v for k, v in it.items() if k != "provenance"}, "provenance": it["provenance"]}
    return it


def _is_rule_item(it: dict) -> bool:
    return item_kind(it) in RULE_KINDS or (item_kind(it) == "device"
                                           and str(it.get("figure") or "").lower() in SCAN_FIGURES)


def _added(output: Value, inputs: dict) -> tuple[list[dict], list[dict]]:
    """(the items the output adds to its `with`, the `with`'s items)."""
    w = inputs.get("with")
    base = fabula_doc(w)[1] if isinstance(w, Value) else []
    have = {it.get("id") for it in base}
    return [it for it in fabula_doc(output)[1] if it.get("id") not in have], base


# ---------------------------------------------------------------------------
# scan
# ---------------------------------------------------------------------------

def outline_value(ctx: Any, poem: Value) -> Value:
    text = _poem_text(poem, "scan")
    name = _name_of(poem)
    got = _verse(ctx).outline(text, source=name, pron=_pron(ctx))
    if not got.get("lines"):
        raise MoveError(f"{name} holds no line of verse to scan")
    items = [plain(it) for it in got["items"]]
    at = _stamp(ctx)
    run = _run_entry(ctx)
    title = got.get("title") or name
    cat = {"oes": "fabula/1", "macrocosm": mc.MACROCOSM_VERSION, "flavour": "fabulap",
           "id": f"fabula/{_slug(name)}", "name": title,
           "source": {"path": name, "sha256": poem.sha256, "size": len(poem.bytes())},
           "derived": {"at": at, "by": "person", **({"program": run["program"]} if run.get("program") else {}),
                       **({"run": run["run"]} if run.get("run") else {}), "mode": "rules", "completeness": "outline",
                       "chunks": 0, "runs": [run]},
           "atem": {k: {"pending": f"a model has not read this poem: what is its {k}?"}
                    for k in ("line", "focus", "push", "pull")},
           "nodes": [_prov_last(it) for it in items]}
    return Value("fabula", cat)


def _slug(s: str) -> str:
    out = re.sub(r"[^a-z0-9-]", "-", s.replace("/", "--").replace(".", "-").lower()).strip("-")
    return re.sub(r"-{3,}", "--", out) or "poem"


@implements("scan")
def scan(ctx: Any, poem: Value, **mods: Any) -> Value:
    """A poem read by rule (Thym 20.9): with no `as`, its outline; with an `as`, the fabulap given with that axis
    added, nothing of it changed."""
    word, w = mods.get("as"), mods.get("with")
    if isinstance(word, list):
        raise MoveError("scan takes one as word: rhyme, sound, recurrence or form")
    if word is None:
        if w is not None:
            raise MoveError("scan poem reads the poem from the start and takes no with; scan poem as rhyme with f adds "
                            "to the fabulap it is given")
        return outline_value(ctx, poem)
    if word not in SCAN_AS:
        raise MoveError(f"scan reads a poem as {', '.join(SCAN_AS[:-1])} or {SCAN_AS[-1]}, not as {word}")
    if w is None:
        raise MoveError(f"scan … as {word} adds to what scan found: scan poem as {word} with f")
    cat, items = _fabulap(w, f"scan … as {word} adds to a fabulap: scan poem as {word} with f")
    _same_poem(cat, poem)
    text = _poem_text(poem, "scan")
    name = _name_of(poem)
    new = added_by_scan(ctx, word, text, items, source=name)
    out = _merge_rules(items, new)
    cat = copy.deepcopy(cat)
    cat.setdefault("derived", {}).setdefault("runs", []).append(_run_entry(ctx))
    return Value("fabula", {**cat, "nodes": out})


def added_by_scan(ctx: Any, word: str, text: str, items: list[dict], *, source: str) -> dict:
    """What `scan … as <word>` adds: `{letters: {line: letter}, items: [...]}` (the letters only for `rhyme`). The
    form is read from the fabulap's own items (`verse_forms.facts`, through the verse engine)."""
    got = _verse(ctx).added(word, text, items, source=source, pron=_pron(ctx))
    letters = {int(n): plain(x) for n, x in got.get("letters") or []}
    return {"letters": letters, "items": [plain(it) for it in got.get("items") or []]}


def with_letters(items: list[dict], letters: dict[int, Any]) -> list[dict]:
    """The items with each `C:line`'s `rhyme` letter (or its open question) in place before its ending."""
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


def _merge_rules(items: list[dict], new: dict) -> list[dict]:
    have = {it.get("id") for it in items}
    out = with_letters(copy.deepcopy(items), new["letters"]) if new["letters"] else copy.deepcopy(items)
    out += [_prov_last(it) for it in new["items"] if it.get("id") not in have]
    return _ordered(out)


# ---------------------------------------------------------------------------
# construe
# ---------------------------------------------------------------------------

def numbered_poem(text: str, lay: dict, a: int | None = None, b: int | None = None) -> str:
    """The poem's file lines `a` to `b`, numbered as a model reads them: the file line, then `[n]` the poem's line
    number, a header line `(header)` and a lyric's label `(label)`."""
    lines = text.replace("\r\n", "\n").split("\n")
    num = {src: n for n, src in _line_src(lay).items()}
    hd = lay.get("header")
    head = set(range(hd[0], hd[1] + 1)) if hd else set()
    labels = set(lay.get("labels") or [])
    a = a or 1
    b = b or len(lines)
    out = []
    for i in range(a, b + 1):
        raw = lines[i - 1] if i - 1 < len(lines) else ""
        if i in num:
            out.append(f"{i}| [{num[i]}] {raw.strip()}")
        elif i in head:
            out.append(f"{i}| (header) {raw.strip()}")
        elif i in labels:
            out.append(f"{i}| (label) {raw.strip()}")
        elif raw.strip():
            out.append(f"{i}| {raw.strip()}")
        else:
            out.append(f"{i}|")
    return "\n".join(out)


def brief(items: list[dict], *, most: int = 90) -> str:
    """The fabulap so far as a model is shown it: one line an item, its id first, the lines (`C:line`) left out but
    for the ones FEED could not scan."""
    rows = []
    for it in items:
        k = item_kind(it)
        iid = it.get("id")
        if k == "line":
            continue
        said = fold(it.get("summary") or it.get("name") or "")
        if len(said) > 140:
            said = said[:137].rstrip() + "…"
        extra = ""
        if k == "device" and it.get("figure"):
            extra = f" ({it['figure']})"
        elif k == "form":
            extra = f" (scheme {it.get('scheme')})" if it.get("scheme") else ""
            turns = [r.get("rule") for r in it.get("rules") or [] if "turn" in str(r.get("rule"))]
            if turns:
                extra += f"; the form expects {turns[0]}"
        rows.append(f"- [{iid}] {k}{extra}: {said}")
        if len(rows) >= most:
            rows.append("- …")
            break
    return "\n".join(rows) or "- (nothing yet)"


def _groups(text: str, lay: dict) -> list[tuple[int, int]]:
    return [(int(a), int(b)) for a, b in lay.get("groups") or []] or [(1, len(text.split("\n")))]


def _fix_cue(v: Any) -> Any:
    if not isinstance(v, str):
        return v
    v = fold(v)
    if len(v) <= CUE_MAX:
        return v
    cut = v[:CUE_MAX].rsplit(" ", 1)[0]
    return cut or v[:CUE_MAX]


def _span_of(it: dict, line_src: dict[int, int]) -> dict | None:
    """A span for an item that gives none: the file lines of the `C:line`s it names (`where`, `of`)."""
    nums = []
    for key in ("where", "of"):
        for ref in (it.get(key) if isinstance(it.get(key), list) else [it.get(key)]):
            mt = re.match(r"^C:line/(\d+)$", str(ref or ""))
            if mt and int(mt.group(1)) in line_src:
                nums.append(line_src[int(mt.group(1))])
    if not nums:
        return None
    a, b = min(nums), max(nums)
    return {"lines": str(a) if a == b else f"{a}-{b}"}


def _cap(it: dict, most: float) -> None:
    prov = it.get("provenance")
    if not isinstance(prov, dict):
        return
    c = prov.get("confidence")
    if not isinstance(c, (int, float)) or isinstance(c, bool) or c > most:
        prov["confidence"] = most


def _poets(items: list[dict], text: str, lay: dict) -> set[str]:
    """The names the poem's maker goes by, as far as the fabulap and the header say: never the speaker on a model's
    word."""
    out = {"poet", "the poet", "author", "the author", "poetess", "the poetess"}
    for it in items:
        if item_kind(it) == "maker" and isinstance(it.get("name"), str):
            out.add(it["name"].strip().lower())
    hd = lay.get("header")
    if hd:
        lines = text.replace("\r\n", "\n").split("\n")
        for n in range(hd[0] + 1, hd[1] + 1):
            head = re.split(r"[,(]", lines[n - 1])[0].strip().lower()
            if head:
                out.add(head)
    return out


def _speaker_is_poet(v: Any, poets: set[str]) -> bool:
    if not isinstance(v, str):
        return False
    s = v.strip().lower()
    return s in poets or any(p and len(p) > 3 and p in s for p in poets) or bool(re.search(r"\bthe poet\b", s))


def hold(it: dict, *, axis: str, text: str, line_src: dict[int, int], source: str, poets: set[str]) -> dict | None:
    """One item of a model's reply held to the contract's stances (Thym 20.9, `stance-kept`), or None when it is not
    an item this axis writes. The narrow, deterministic part of the contract; the checks read the rest."""
    if not isinstance(it, dict) or not isinstance(it.get("id"), str):
        return None
    it = {str(k): plain(v) for k, v in it.items()}
    mt = _ID.match(it["id"].strip())
    if not mt:
        return None
    it["id"] = it["id"].strip()
    module, kind = mt.group(1), mt.group(2)
    allowed = AXIS_KINDS.get(axis, SENSE_KINDS)
    if f"{module}:{kind}" not in allowed:
        return None
    it["type"] = kind
    if not isinstance(it.get("name"), str) or not it["name"].strip():
        it["name"] = mt.group(3).replace("-", " ")
    if not isinstance(it.get("summary"), str) or not it["summary"].strip():
        it["summary"] = it["name"]
    for f in ("cue",):
        if f in it:
            it[f] = _fix_cue(it[f])
    if not isinstance(it.get("span"), dict) or span_lines(it) is None:
        sp = _span_of(it, line_src)
        if sp is None:
            return None
        it["span"] = sp
    ab = span_lines(it)
    prov = it.get("provenance") if isinstance(it.get("provenance"), dict) else {}
    loc = f"{source}#L{ab[0]}" if ab[0] == ab[1] else f"{source}#L{ab[0]}-L{ab[1]}"
    prov = {"mode": "derived", "sources": [loc], "confidence": prov.get("confidence", 0.5),
            "state": prov.get("state") or "known"}
    if not isinstance(prov["confidence"], (int, float)) or isinstance(prov["confidence"], bool):
        prov["confidence"] = 0.5
    it["provenance"] = prov
    key = f"{module}:{kind}"
    if key == "P:reading":
        it["stance"] = "opinion"
        it["whose"] = {"by": "model"}
        it.pop("intended", None)
        _cap(it, OPINION_CAP)
        if not it.get("of"):
            return None
    elif key in INTENT_KINDS or (key == "I:occasion" and it.get("stance") != "observed"):
        it["stance"] = "assumed"
        _cap(it, OPINION_CAP)
        prov["state"] = "pending"
    elif key == "I:allusion":
        roles = it.get("roles") if isinstance(it.get("roles"), dict) else {}
        to = roles.get("to", it.pop("to", None))
        if to is None or (isinstance(to, str) and not to.strip()):
            to = {"pending": "which text does this echo, if any?"}
        it["roles"] = {**roles, "to": to}
        if it.get("stance") != "observed":
            it["stance"] = "assumed"
            _cap(it, OPINION_CAP)
            prov["state"] = "pending"
    elif module == "C":
        it.pop("intended", None)                     # only the author says a device was meant
        st = it.get("stance")
        if st not in ("observed", "deduced"):
            it["stance"] = "deduced"
        if it["stance"] == "observed" and not _cue_in(it.get("cue"), text):
            it["stance"] = "deduced"
        if it["stance"] == "deduced":
            _cap(it, DEDUCED_CAP)
        if kind == "device":
            if not isinstance(it.get("figure"), str) or not it["figure"].strip():
                it["figure"] = {"turn": "turn", "image": "image"}.get(axis) or "figure"
            if axis == "turn":
                it["figure"] = "turn"
            if axis == "image" and it.get("figure") == "image" and isinstance(it.get("senses"), list):
                it["senses"] = [s for s in (str(x).strip().lower() for x in it["senses"]) if s in SENSES]
                if not it["senses"]:
                    it.pop("senses")
            elif "senses" in it and not isinstance(it.get("senses"), list):
                it.pop("senses")
        if kind == "voice":
            roles = it.get("roles") if isinstance(it.get("roles"), dict) else {}
            sp = roles.get("speaker")
            if sp is None or _speaker_is_poet(sp, poets):
                roles["speaker"] = {"pending": SPEAKER_ASKS}
            if "addressee" in roles and isinstance(roles["addressee"], str) and not roles["addressee"].strip():
                roles["addressee"] = {"pending": "whom does the poem address?"}
            it["roles"] = roles
    else:
        if it.get("stance") not in ("observed", "deduced", "opinion", "assumed", "hearsay", "axiom"):
            it["stance"] = "deduced"
    return _prov_last(it)


def _cue_in(cue: Any, text: str) -> bool:
    if not isinstance(cue, str) or not cue.strip():
        return False
    flat = " ".join(words(text))
    for part in re.split(r"\s*…\s*|\.\.\.", cue):
        ws = " ".join(words(part))
        if ws and ws not in flat:
            return False
    return True


def parse_construe(out: Any, *, axis: str, text: str, items: list[dict], source: str, lay: dict) -> list[dict]:
    """A model's reply to one construe request as the items it adds (`hold` each), or a ValueError the runtime asks
    again with."""
    data = answer_mapping(out) if not isinstance(out, str) else None
    if data is None:
        try:
            data = mc.yaml_load(out)
        except Exception as e:  # noqa: BLE001
            raise ValueError(f"the answer is not YAML: {str(e).splitlines()[0][:120]}") from None
    if isinstance(data, list):
        data = {"nodes": data}
    if not isinstance(data, dict) or not isinstance(data.get("nodes", []), list):
        raise ValueError("answer with a YAML mapping whose one key, nodes, is a list of items (nodes: [] for none)")
    line_src = _line_src(lay)
    poets = _poets(items, text, lay)
    out_items = []
    for raw in data.get("nodes") or []:
        it = hold(raw, axis=axis, text=text, line_src=line_src, source=source, poets=poets)
        if it is not None:
            out_items.append(it)
    return out_items


def merge_reading(items: list[dict], new: list[dict]) -> list[dict]:
    """The fabulap with a reading's items added: a new id appended; an id it holds already gains only the fields it
    lacks (never one it says otherwise), unless it is an item `scan` wrote, which no reading changes."""
    out = copy.deepcopy(items)
    by_id = {it.get("id"): it for it in out}
    for it in new:
        old = by_id.get(it["id"])
        if old is None:
            out.append(it)
            by_id[it["id"]] = it
            continue
        if _is_rule_item(old):
            continue
        for k, v in it.items():
            if k not in old:
                old[k] = v
    return _ordered([_prov_last(x) for x in out])


def ground_terms(ctx: Any, new: list[dict]) -> None:
    """Every new `L:term` says where its word stands in FEED (`terms-grounded`), through the host's `feed` engine:
    `feed: {word, pos, origin}`, else `{pending: "not in FEED"}`; without FEED a term is left as the model wrote it."""
    terms = [it for it in new if item_kind(it) == "term" and "feed" not in it]
    lookup = (getattr(ctx, "engines", None) or {}).get("feed")
    if not terms or not callable(lookup):
        return
    try:
        found = lookup([str(it.get("name") or "") for it in terms]) or {}
    except Exception:  # noqa: BLE001 - a FEED that cannot be read grounds nothing
        return
    for it in terms:
        name = str(it.get("name") or "")
        e = found.get(name) or found.get(name.lower().strip())
        if isinstance(e, dict):
            pos = e.get("pos_primary") or str(e.get("pos") or "").split(";")[0].strip()
            it["feed"] = {"word": str(e.get("word") or name.lower()), **({"pos": str(pos)} if pos else {}),
                          "origin": "user" if e.get("origin") == "user" else "feed"}
        else:
            it["feed"] = {"pending": "not in FEED"}


@implements("construe")
def construe(ctx: Any, poem: Value, **mods: Any) -> Request | Value:
    """One axis of a poem read by a model, under contract (Thym 20.9)."""
    axis, w = mods.get("as"), mods.get("with")
    if isinstance(axis, list) or axis is None:
        raise MoveError("construe names one axis: construe poem as figure with f")
    if axis not in CONSTRUE_AS:
        raise MoveError(f"construe reads a poem as {', '.join(CONSTRUE_AS[:-1])} or {CONSTRUE_AS[-1]}, not as {axis}")
    cat, items = _fabulap(w, f"construe takes the fabulap so far: construe poem as {axis} with f")
    _same_poem(cat, poem)
    text = _poem_text(poem, "construe")
    name = _name_of(poem)
    lay = layout(ctx, text)
    groups = _groups(text, lay)
    outline = brief(items)

    def inputs(a: int, b: int) -> dict:
        ins = {"fabulap": Value("string", axis), "source": Value("string", name),
               "lines": Value("string", f"{a}-{b}"), "poem": Value("string", numbered_poem(text, lay, a, b)),
               "outline": Value("string", outline)}
        if len(groups) > 1:
            ins["part"] = Value("string", f"{groups.index((a, b)) + 1} of {len(groups)}")
        return ins

    schema = {"format": "yaml", "stamp": "engine", "says": CONSTRUE_SAYS}

    def value(new: list[dict], model: str | None) -> Value:
        ground_terms(ctx, new)
        c = copy.deepcopy(cat)
        c.setdefault("derived", {}).setdefault("runs", []).append(_run_entry(ctx, model))
        return Value("fabula", {**c, "nodes": merge_reading(items, new)})

    if len(groups) == 1:
        a, b = groups[0]

        def parse(out: Any) -> Value:
            new = parse_construe(out, axis=axis, text=text, items=items, source=name, lay=lay)
            return value(new, model_of(answer_mapping(out)) if not isinstance(out, str) else None)
        return Request(contract={"schema": schema, "repair": []}, inputs=inputs(a, b), parse=parse)
    # a long poem: one request per group of stanzas, through ctx.ask (keyed <node>, <node>-1, … replayed in order)
    new: list[dict] = []
    model = None
    for a, b in groups:
        last_err = None
        for _try in range(2):
            ins = inputs(a, b)
            if last_err:
                ins["failed"] = Value("string", last_err)
            cand = ctx.ask({"schema": schema, "repair": []}, ins)
            try:
                got = parse_construe(cand.get("output"), axis=axis, text=text, items=items + new, source=name,
                                     lay=lay)
                model = model or model_of(answer_mapping(cand.get("output")))
                have = {x["id"] for x in new}
                new += [x for x in got if x["id"] not in have]
                break
            except ValueError as e:
                last_err = str(e)
        else:
            raise MoveError(f"{name}, lines {a} to {b}: the reading could not be read: {last_err}")
    return value(new, model)


# ---------------------------------------------------------------------------
# derive poem as verse with f: what the poem says, against the outline
# ---------------------------------------------------------------------------

def derive_with(ctx: Any, story: Value, w: Value) -> Request:
    """`derive poem as verse with f` (Thym 20.9): the sense reading, passage by passage through Canon's verse path
    with the sense prompt (no devices, voice or readings: those are construe's), then the whole poem's atem; the
    items added to the fabulap, nothing of it changed."""
    cat, items = _fabulap(w, "derive … as verse with f reads a poem against its fabulap")
    _same_poem(cat, story)
    canon = engine(ctx, "canon")
    text = story.text()
    name = _name_of(story)
    adapter = EngineAdapter(ctx, "derive")
    got = canon.derive_passages(text, source_name=name, complete=adapter, lookup=ctx.engines.get("feed"),
                                flavour="fabulap", pron=ctx.engines.get("pron"), sense=True)

    def parse(out: Any) -> Value:
        reply = out if isinstance(out, str) else mc.dump(out) if isinstance(out, dict) else str(out or "")
        atem = canon.read_atem(reply)
        line = atem.get("line") if isinstance(atem, dict) else None
        if not (isinstance(line, str) and line.strip()):
            raise ValueError("the whole poem's atem could not be read; answer with line, focus, push and pull, each "
                             "on its own line")
        model = adapter.model or got.get("model") or model_of(out if isinstance(out, dict) else {})
        new = [plain(it) for it in got["nodes"]
               if f"{str(it.get('id', ''))[:1]}:{it.get('type')}" in SENSE_KINDS]
        c = copy.deepcopy(cat)
        c["atem"] = {k: atem.get(k) for k in ("line", "focus", "push", "pull") if atem.get(k) is not None}
        d = c.setdefault("derived", {})
        d.update({"at": _stamp(ctx), "mode": "model", "completeness": "full"})
        if model:
            d["model"] = model
        d.setdefault("runs", []).append(_run_entry(ctx, model))
        return Value("fabula", {**c, "nodes": merge_reading(items, new)})

    return Request(contract={"schema": {"format": "text", "says": "the whole poem's atem"}, "repair": []},
                   inputs={"messages": messages_value(got["messages"])}, parse=parse)


def derive_with_rules(ctx: Any, story: Value, w: Value) -> Value:
    """The rules scaffold of `derive poem as verse with f`: the fabulap with the rules twin's words and names added
    (grounded in FEED, each at its first use), nothing of it changed; its atem stays open."""
    cat, items = _fabulap(w, "derive … as verse with f reads a poem against its fabulap")
    _same_poem(cat, story)
    twin = engine(ctx, "canon").derive_rules(story.text(), source_name=_name_of(story), sha256=story.sha256,
                                             size=len(story.bytes()), lookup=ctx.engines.get("feed"), now=ctx.now,
                                             flavour="fabulap", pron=ctx.engines.get("pron"))
    new = [it for it in fabula_doc(Value("fabula", twin))[1] if str(it.get("id", ""))[:2] in ("L:", "E:")]
    c = copy.deepcopy(cat)
    c.setdefault("derived", {}).setdefault("runs", []).append(_run_entry(ctx))
    return Value("fabula", {**c, "nodes": merge_reading(items, [plain(x) for x in new])}, state="pending")


def derive_branch(ctx: Any, story: Value, mods: dict, *, rules: bool = False) -> Any:
    """The `with` branch of `derive … as verse`, or None for any other call."""
    w = mods.get("with")
    if mods.get("as") != "verse" or not isinstance(w, Value):
        return None
    return derive_with_rules(ctx, story, w) if rules else derive_with(ctx, story, w)


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------

def _poem_of(inputs: dict) -> Value | None:
    return first_input(inputs, "text", "short")


@check("lines-found")
def _lines_found(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every line of the poem that is not blank, after its header and less a lyric's labels, is one `C:line`,
    numbered from 1 in the poem's order, its span its own line, its part its stanza's; every stanza and every
    labelled section is a `C:part`; no `C:line` names a line the poem lacks (Thym 7.3)."""
    src = _poem_of(inputs)
    if src is None:
        return False, "no poem to find the lines in"
    lay = layout(ctx, src.text())
    items = fabula_doc(output)[1]
    lines = {it.get("number"): it for it in items if item_kind(it) == "line"}
    parts = {it.get("id") for it in items if item_kind(it) == "part"}
    for pid in lay.get("parts") or []:
        if pid not in parts:
            return False, f"the poem's part {pid} has no C:part"
    rows = lay.get("lines") or []
    for n, src_line, pid in rows:
        it = lines.get(n)
        if it is None:
            return False, f"line {n} of the poem (line {src_line} of the file) has no C:line"
        if it.get("id") != f"C:line/{n}":
            return False, f"line {n} is written {it.get('id')}"
        if span_lines(it) != (src_line, src_line):
            return False, f"C:line/{n}'s span is not line {src_line} of the file"
        if it.get("part") != pid:
            return False, f"C:line/{n} is in {pid}, not {it.get('part')}"
    extra = sorted(n for n in lines if not isinstance(n, int) or n < 1 or n > len(rows))
    if extra:
        return False, f"C:line/{extra[0]} names a line the poem lacks"
    return True, f"{len(rows)} lines in {len(lay.get('parts') or [])} parts"


@check("scansion-grounded")
def _scansion_grounded(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every line's stresses and syllables are FEED's, read by the rule of Thym 20.9 (a contraction as the words it
    joins), or an open question naming the words FEED lacks; the `C:metre` and its departures are the rule's."""
    src = _poem_of(inputs)
    if src is None:
        return False, "no poem to scan"
    got_ = _verse(ctx).outline(src.text(), source=_name_of(src), pron=_pron(ctx))
    want = {it["id"]: plain(it) for it in got_.get("items") or []}
    got = {it.get("id"): it for it in fabula_doc(output)[1]}
    for iid, it in want.items():
        if item_kind(it) == "line":
            g = got.get(iid) or {}
            for f in ("stresses", "syllables"):
                a, b = g.get(f), it.get(f)
                if mc.is_pending(b):
                    if not mc.is_pending(a):
                        return False, f"{iid}: FEED does not hold every word of it, and its {f} are not a question"
                elif a != b:
                    return False, f"{iid}: its {f} are {a!r}, and FEED gives {b!r}"
        elif item_kind(it) == "metre":
            g = got.get(iid)
            if g is None:
                return False, f"the metre the rule reads is {it.get('name')}, and the fabulap has no {iid}"
            for f in ("foot", "feet", "basis", "lines", "departures"):
                if not mc.is_pending(it.get(f)) and g.get(f) != it.get(f):
                    return False, f"{iid}: its {f} is not the rule's ({it.get(f)!r})"
    return True, ""


def _key_fields(it: dict) -> tuple:
    return (it.get("id"), item_kind(it), it.get("figure"), tuple(it.get("where") or it.get("lines") or []),
            it.get("quality"), it.get("placement"), it.get("scheme"), it.get("cue"))


@check("sound-grounded")
def _sound_grounded(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every rhyme, sound pattern and recurrence a call writes names lines of the poem, and their words share what it
    says they share, by FEED and the edition's thresholds; each line's `rhyme` letter is its rhyme's scheme (Thym
    7.3): what the call added is what the rule finds, no more and no other."""
    src = _poem_of(inputs)
    mods = (node or {}).get("modifiers")
    word = mods.get("as") if isinstance(mods, dict) else None
    if src is None or word not in ("rhyme", "sound", "recurrence"):
        return False, "no poem, or no axis, to ground the sounds in"
    added, base = _added(output, inputs)
    want = added_by_scan(ctx, word, src.text(), base, source=_name_of(src))
    have = {it.get("id") for it in base}
    expect = {_key_fields(it) for it in want["items"] if it.get("id") not in have}
    got = {_key_fields(it) for it in added}
    if got - expect:
        extra = sorted(got - expect, key=str)[0]
        return False, f"{extra[0]} is not what the rule finds in the poem"
    if expect - got:
        miss = sorted(expect - got, key=str)[0]
        return False, f"the rule finds {miss[0]}, and the call did not write it"
    if want["letters"]:
        lines = {it.get("number"): it for it in fabula_doc(output)[1] if item_kind(it) == "line"}
        for n, letter in want["letters"].items():
            g = (lines.get(n) or {}).get("rhyme")
            if mc.is_pending(letter) != mc.is_pending(g) or (not mc.is_pending(letter) and g != letter):
                return False, f"C:line/{n}'s rhyme letter is {g!r}, and its rhyme's scheme is {letter!r}"
    return True, ""


@check("form-grounded")
def _form_grounded(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """A `C:form` names a form of the table only when the poem keeps its defining rules, read from the fabula's own
    lines, parts, metre, rhymes and recurrences; every other rule is in `rules`, held as the fabula shows it; every
    departure names a line or a part (Thym 7.3)."""
    src = _poem_of(inputs)
    if src is None:
        return False, "no poem to read the form from"
    items = fabula_doc(output)[1]
    forms = [it for it in items if item_kind(it) == "form"]
    if len(forms) > 1:
        return False, f"{len(forms)} C:form items; a poem keeps one form"
    if not forms:
        return True, "no form"
    got = forms[0]
    rest = [it for it in items if item_kind(it) != "form"]
    added = added_by_scan(ctx, "form", src.text(), rest, source=_name_of(src))["items"]
    want = added[0] if added else None
    if want is None:
        return False, "the poem holds no line, and the fabulap names a form"
    if got.get("form") != want.get("form"):
        return False, f"the fabulap names {got.get('form')!r}, and the rule reads {want.get('form')!r}"
    if (got.get("rules") or []) != (want.get("rules") or []):
        return False, f"{got.get('id')}: its rules are not held as the fabulap shows them"
    ids = {it.get("id") for it in items}
    for d in got.get("departures") or []:
        at = d.get("at") if isinstance(d, dict) else None
        if at not in ids or not str(at).startswith(("C:line/", "C:part/")):
            return False, f"{got.get('id')}: a departure names {at!r}, not a line or a part of the poem"
    return True, ""


def _verse_coverage(axis: str):
    def fn(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
        """`coverage` read for verse (Thym 20.9)."""
        src = _poem_of(inputs)
        if src is None:
            return False, "no poem to cover"
        text = src.text()
        lay = layout(ctx, text)
        n_file = len(text.replace("\r\n", "\n").split("\n"))
        added, _base = _added(output, inputs)
        items = fabula_doc(output)[1]
        ids = {it.get("id") for it in items}
        for it in added:
            ab = span_lines(it)
            if ab is None or ab[0] < 1 or ab[1] > n_file:
                return False, f"{it.get('id')}: its span is not inside the poem or its header"
            for g in it.get("grounds") or []:
                of = g.get("of") if isinstance(g, dict) else None
                refs = of if isinstance(of, list) else [of]
                if any(isinstance(r, str) and r not in ids for r in refs) or not of:
                    return False, f"{it.get('id')}: its grounds name {of!r}, which the fabulap does not hold"
        if axis == "voice":
            voices = [span_lines(it) for it in items if item_kind(it) == "voice" and span_lines(it)]
            for n, src_line, _pid in lay.get("lines") or []:
                if not any(a <= src_line <= b for a, b in voices):
                    return False, f"line {n} is in no C:voice"
        if axis == "meaning":
            parts = [it for it in items if item_kind(it) == "part" and isinstance(it.get("id"), str)]
            part_lines = {p["id"]: {f"C:line/{ln.get('number')}" for ln in items
                                    if item_kind(ln) == "line" and ln.get("part") == p["id"]} for p in parts}
            readings = [it for it in items if item_kind(it) == "reading"]

            def of_set(r: dict) -> set:
                of = r.get("of")
                return set(of if isinstance(of, list) else [of])
            for p in parts:
                if not part_lines[p["id"]]:
                    continue
                if not any(p["id"] in of_set(r) or of_set(r) & part_lines[p["id"]] for r in readings):
                    return False, f"{p['id']} is read by no reading"
            whole = {p["id"] for p in parts if part_lines[p["id"]]}
            if whole and not any(whole <= of_set(r) for r in readings):
                return False, "no reading reads the whole poem: none names every part in its of"
        return True, f"{len(added)} item{'s' if len(added) != 1 else ''} added"
    return fn


def _words_of(text: str) -> set[str]:
    return set(words(text))


def _verse_no_invention(axis: str):
    def fn(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
        """`no-invention` read for verse (Thym 20.9): every name, cue and quoted word an added item carries is in the
        poem or its header; a work, a person or a tradition outside the poem only as an allusion's `to` or an
        influence's `source`."""
        src = _poem_of(inputs)
        if src is None:
            return False, "no poem to look the words up in"
        text = src.text()
        flat = " ".join(words(text))
        have = _words_of(text)
        added, _base = _added(output, inputs)
        for it in added:
            cue = it.get("cue")
            if isinstance(cue, str) and cue.strip() and not _cue_in(cue, text):
                return False, f"{it.get('id')}: its cue \"{cue}\" is not in the poem"
            if isinstance(cue, str) and len(cue) > CUE_MAX:
                return False, f"{it.get('id')}: its cue is longer than {CUE_MAX} characters"
            if str(it.get("id", ""))[:2] == "E:":
                ws = [w for w in words(str(it.get("name") or "")) if len(w) > 3]
                if ws and not all(w in have for w in ws):
                    return False, f"{it.get('id')}: the poem does not name {it.get('name')!r}"
            for field_ in ("name", "summary"):
                for q in _QUOTED.findall(str(it.get(field_) or "")):
                    ws = " ".join(words(q))
                    if ws and ws not in flat:
                        return False, f"{it.get('id')}: it quotes \"{q}\", which the poem does not say"
        return True, ""
    return fn


def _verse_stance_kept(axis: str):
    def fn(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
        """`stance-kept` read for verse (Thym 20.9)."""
        src = _poem_of(inputs)
        if src is None:
            return False, "no poem to read the stances against"
        text = src.text()
        added, base = _added(output, inputs)
        poets = _poets(fabula_doc(output)[1], text, layout(ctx, text))
        for it in added:
            iid = str(it.get("id"))
            key = iid.split("/", 1)[0]
            prov = it.get("provenance") if isinstance(it.get("provenance"), dict) else {}
            conf = prov.get("confidence")
            if key == "P:reading":
                if it.get("stance") != "opinion" or (it.get("whose") or {}).get("by") != "model":
                    return False, f"{iid}: a model's reading is its opinion, whose: {{by: model}}"
                if not isinstance(conf, (int, float)) or conf > OPINION_CAP:
                    return False, f"{iid}: a model's reading is at most {OPINION_CAP} sure"
                if "intended" in it:
                    return False, f"{iid}: only the author says whether a reading was meant"
            elif key in INTENT_KINDS or (key in ("I:occasion", "I:allusion") and it.get("stance") != "observed"):
                if it.get("stance") != "assumed" or prov.get("state") != "pending" or \
                        not isinstance(conf, (int, float)) or conf > OPINION_CAP:
                    return False, f"{iid}: intent or inspiration the poem does not state is assumed, at most " \
                                  f"{OPINION_CAP}, and pending"
            elif key in ("C:device", "C:voice"):
                if "intended" in it:
                    return False, f"{iid}: only the author says whether it was meant"
                if it.get("stance") == "observed" and not _cue_in(it.get("cue"), text) and key == "C:device":
                    return False, f"{iid}: observed, and its cue does not show it in the poem's words"
                if it.get("stance") not in ("observed", "deduced"):
                    return False, f"{iid}: a figure, an image, a voice or a turn is observed or deduced"
                if it.get("stance") == "deduced" and (not isinstance(conf, (int, float)) or conf > DEDUCED_CAP):
                    return False, f"{iid}: deduced, at most {DEDUCED_CAP} sure"
                if key == "C:voice":
                    sp = (it.get("roles") or {}).get("speaker") if isinstance(it.get("roles"), dict) else None
                    if sp is None or _speaker_is_poet(sp, poets):
                        return False, f"{iid}: the speaker is never the poet on a model's word"
        return True, ""
    return fn


for _axis in CONSTRUE_AS:
    check("coverage", kind=_axis)(_verse_coverage(_axis))
    check("no-invention", kind=_axis)(_verse_no_invention(_axis))
    check("stance-kept", kind=_axis)(_verse_stance_kept(_axis))


__all__ = ["AXIS_KINDS", "CONSTRUE_AS", "SCAN_AS", "added_by_scan", "brief", "construe", "derive_branch",
           "derive_with", "derive_with_rules", "hold", "merge_reading", "numbered_poem", "outline_value",
           "parse_construe", "scan"]
