"""Authoring a fabulac (MacroCOSM OES 18.4.1, 18.4.7; Thym 6.3, 7.3, 20.11), seen by `thym 1` programs only.

An authored fabulac is written before its program, by the person who means to make it, and is the program's source.
Its catalog says `source: {kind: authored, language: python, licence, by, at, brief}`, the licence `{pending: …}`
until the person gives one, and `program: {kind, start, serve}`, the kind being the call's `as` word.

- `author brief as tool` (text → fabula; `as` tool | library | service): the catalog, the items the person stated in
  beginning it (who authored it, the licence, the language), and the items the brief answers. The brief is read by
  rules first (`read_brief`): each list item, or each paragraph, under a heading the authoring bank names for one of
  its entries (`brief:` in the manifest) is one item of the kind that entry writes, in the person's own words; the
  paragraphs before the first such heading answer what the program is for. Only what the rules could not place is put
  to a model, which answers which entry each passage answers, and nothing else: the item it makes still says the
  person's words alone, `confidence` below one half, so the interview asks whether it is right. Every item is
  `stance: axiom`, `provenance.mode: structured-intake`, citing the brief's lines.
- `author as tool` (no operand: an interview): the catalog and the person's own items, by rules. Its scaffold
  `catalog-alone` is the move itself, so `--rules` runs it.
- `add said as requirement with f` (and `as decision`, `as case`, `as interface`): the person's sentence as a new
  item of that kind, `provenance.mode: manual`; what the kind needs and the sentence does not give is `{pending: …}`.
  `add` takes only an authored fabulac.
- `compare f with g`: a report of what differs, item by item by id.
- `uncovered f`: the requirements of `force: must` that name no case in `checked-by`.

What the person said in beginning it (the program's name, the licence, who they are, the brief's path) reaches the
move through the engine `authoring`, a callable the host registers that returns that mapping (recorded and replayed as
every engine call is); without it the name is the brief's title, the licence a question and the author "the author".

The check `authored-source` (Thym 7.3, Thym's own) holds every output of `author` and `add`. The interview itself is
the dialectic's (`question`, then `settle`), stage by stage, by the bank `fabulac-authored`; the host's job is
`enough/fabulac_author_job.py`. This module imports only Thym and the reader.
"""
from __future__ import annotations

import copy
import re
from typing import Any

from enough import macrocosm as mc
from enough.thym.checks import check
from enough.thym.moves import MoveError, answer_mapping, fabula_doc, fold
from enough.thym.registry import implements
from enough.thym.values import Value

KINDS = ("tool", "library", "service")
LANGUAGE = "python"
AUTHORED = "authored"
BANK = "fabulac-authored"
#: The scaffold of `author` with no brief: the move itself, by rules.
SCAFFOLD = "catalog-alone"
ENGINE = "authoring"
#: The modes an item a move of authoring writes may carry (Thym 7.3, `authored-source`).
MODES = ("structured-intake", "manual", "dialectic")
#: What `add` writes for each `as` word.
ADD_KINDS = {"requirement": ("N", "requirement"), "decision": ("N", "decision"), "case": ("P", "case"),
             "interface": ("C", "interface")}
#: What a field `add` cannot fill from one sentence asks, by field.
ADD_ASKS = {"force": "must, should or may: how strictly must the program meet it?",
            "chose": "what was chosen, in a word or two?",
            "of": "which way in, or which use, is this case of? Name it by its id.",
            "given": "what is given: the command and its arguments, or the call, and any file it starts with?",
            "expect": "what is expected back: the output, the exit, or the value?",
            "surface": "is it a command (a person types it) or a function (a program calls it)?"}
#: Below this a reading is unsure (MacroCOSM OES 18.6.3): what a model placed is asked again.
PLACED_CONFIDENCE = 0.4
NOT_SET = frozenset(("id", "type", "name", "summary", "provenance", "stance", "pending", "withheld", "links"))
_SLUG_BAD = re.compile(r"[^a-z0-9-]+")
_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
_ITEM = re.compile(r"^\s{0,3}(?:[-*+]|\d+[.)])\s+(.*)$")
_FENCE = re.compile(r"^\s{0,3}(```|~~~)")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def slug(text: str, n: int = 40) -> str:
    """A slug by the Canon rule (MacroCOSM OES 18.3.3), cut at a word near `n` characters."""
    s = _SLUG_BAD.sub("-", str(text).replace("/", "--").replace(".", "-").lower()).strip("-")
    if len(s) > n:
        s = s[:n].rsplit("-", 1)[0] or s[:n]
    return s.strip("-") or "item"


def first_words(s: str, n: int = 6) -> str:
    words = fold(s).split(" ")
    return " ".join(words[:n]).rstrip(".,;:!?") or fold(s)


def module_name(name: str) -> str:
    """The Python module a program of this name is started as: lowercase, a letter first, `_` for the rest."""
    s = re.sub(r"[^a-z0-9_]+", "_", str(name).lower()).strip("_")
    return s if s and s[0].isalpha() else f"p_{s}" if s else "program"


def _as_word(x: Any) -> str | None:
    if isinstance(x, (list, tuple)):
        x = x[0] if x else None
    if isinstance(x, Value):
        x = x.payload
    return str(x) if isinstance(x, str) and x else None


def _text(v: Any) -> str:
    if isinstance(v, Value):
        if v.is_nothing:
            return ""
        try:
            return v.text()
        except Exception:  # noqa: BLE001 - a string value
            return str(v.payload)
    return "" if v is None else str(v)


def is_authored(catalog: Any) -> bool:
    src = catalog.get("source") if isinstance(catalog, dict) else None
    return isinstance(src, dict) and src.get("kind") == AUTHORED


def bank_entries(registry: mc.Registry | None = None) -> list[dict]:
    """The authoring bank's entries, in the manifest's order (MacroCOSM OES 18.6.6)."""
    m = (registry or mc.default_registry()).get("fabula")
    for b in (m.banks() if m is not None else []):
        if b["name"] == BANK:
            return [e for e in b["questions"] if isinstance(e, dict)]
    return []


def stages(registry: mc.Registry | None = None) -> list[str]:
    """The interview's stages in order: the `stage` of the bank's entries, as they first appear."""
    out: list[str] = []
    for e in bank_entries(registry):
        s = e.get("stage")
        if isinstance(s, str) and s and s not in out:
            out.append(s)
    return out


def _writes(e: dict) -> tuple[str, str] | None:
    """(module, kind) an entry about a module writes: `writes: aim` of `about: N` is `N:aim`."""
    w = e.get("writes")
    if not (isinstance(w, str) and w.strip()) or not isinstance(e.get("about"), str):
        return None
    mod, sep, k = w.strip().partition(":")
    return (mod, k) if sep else (e["about"].split(":", 1)[0].split("#", 1)[0], mod)


def _unique_id(mod: str, kind: str, base: str, taken: set[str]) -> str:
    s, n = slug(base), 2
    cand = f"{mod}:{kind}/{s}"
    while cand in taken:
        cand, n = f"{mod}:{kind}/{s}-{n}", n + 1
    taken.add(cand)
    return cand


def make_item(mod: str, kind: str, said: str, *, taken: set[str], provenance: dict, sets: dict | None = None,
              asks: dict | None = None, registry: mc.Registry | None = None) -> dict:
    """One item in the person's words: `name` its first words, `summary` the words whole, `stance: axiom`, the fields
    `sets` gives, and every field the kind requires that nothing gave as `{pending: …}`."""
    m = (registry or mc.default_registry()).get("fabula")
    item: dict = {"id": _unique_id(mod, kind, first_words(said), taken), "type": kind, "name": first_words(said),
                  "summary": fold(said), "stance": "axiom"}
    for f, v in (sets or {}).items():
        if isinstance(f, str) and f not in NOT_SET:
            item[f] = copy.deepcopy(v)
    for f in (m.required_fields(mod, kind) if m is not None else ()):
        if f not in item and f not in ("id", "type", "provenance"):
            item[f] = {"pending": (asks or {}).get(f) or f"what is the {f} of this {kind}?"}
    item["provenance"] = provenance
    return item


# ---------------------------------------------------------------------------
# The catalog an authored fabulac begins with
# ---------------------------------------------------------------------------

def program_block(kind: str, name: str) -> dict:
    """`program: {kind, start, serve}` (MacroCOSM OES 18.4.7): a tool and a service start as `-m <module>`; a service
    serves on a port the host chooses (0) and may reach nothing until the person says what."""
    if kind not in KINDS:
        raise MoveError(f"a program is a tool, a library or a service, not {kind!r}")
    out: dict = {"kind": kind}
    if kind in ("tool", "service"):
        out["start"] = ["-m", module_name(name)]
    if kind == "service":
        out["serve"] = {"port": 0, "reach": []}
    return out


def begin(name: str, *, kind: str = "tool", licence: Any = None, by: str | None = None, at: str,
          brief: str | None = None, program: str | None = None, run: str | None = None, mode: str = "rules",
          registry: mc.Registry | None = None) -> dict:
    """The catalog of an authored fabulac with the items its person stated in beginning it, by rules: who authored it
    (`R:maker`, capacity `author`), the licence (`R:licence`, its identifier when given, else asked by the interview),
    and the language (`C:dependency/python`, with no `version`: MacroCOSM's `version` is optional, and no stage of the
    interview asks it). `at` is a timestamp in UTC; the source's `at` is its day."""
    name = fold(name or "")
    if not name:
        raise MoveError("an authored fabulac needs a name: the program's")
    taken: set[str] = set()
    who = fold(by or "") or "the author"
    prov = {"mode": "manual", "sources": ["the author, in beginning it"], "confidence": 1}
    maker = {"id": _unique_id("R", "maker", "author" if who == "the author" else who, taken), "type": "maker",
             "name": who, "summary": f"{who[:1].upper()}{who[1:]} authored {name}.", "capacity": "author",
             "stance": "axiom", "provenance": dict(prov)}
    lic: dict = {"id": "R:licence/licence", "type": "licence", "name": "licence",
                 "summary": f"The terms {who} offers {name} on.", "stance": "axiom", "provenance": dict(prov)}
    taken.add(lic["id"])
    has_licence = isinstance(licence, str) and licence.strip()
    if has_licence:
        lic["identifier"] = licence.strip()
    py = {"id": "C:dependency/python", "type": "dependency", "name": "python",
          "summary": "Python, the language its entailments are written in, with its standard library.",
          "package": "python", "scope": "run-time", "stance": "axiom", "provenance": dict(prov)}
    taken.add(py["id"])
    src: dict = {"kind": AUTHORED, "language": LANGUAGE,
                 "licence": licence.strip() if has_licence else {"pending": "Under which licence will you offer it?"},
                 "by": [maker["id"]], "at": str(at)[:10]}
    if brief:
        src["brief"] = str(brief)
    entry = {"program": program, "run": run, "at": at}
    return {"oes": "fabula/1", "macrocosm": mc.MACROCOSM_VERSION, "flavour": "fabulac", "id": f"fabula/{slug(name, 80)}",
            "name": name, "source": src,
            "derived": {"at": at, "by": "person", **({"program": program} if program else {}),
                        **({"run": run} if run else {}), "mode": mode, "completeness": "outline", "chunks": 0,
                        **({"runs": [{k: v for k, v in entry.items() if v}]} if program else {})},
            "program": program_block(kind, name),
            "atem": {k: {"pending": f"not yet said: what is its {k}?"} for k in ("line", "focus", "push", "pull")},
            "nodes": [maker, lic, py]}


# ---------------------------------------------------------------------------
# A brief, read by rules
# ---------------------------------------------------------------------------

def _heading_key(s: str) -> str:
    s = re.sub(r"^[\d.)\s]+", "", s.lower())
    return fold(re.sub(r"[^a-z0-9 ]+", " ", s))


def entry_for_heading(heading: str, entries: list[dict]) -> dict | None:
    """The bank entry a brief's heading answers: one whose `brief` words are the heading, else the first whose words
    stand whole in it."""
    key = _heading_key(heading)
    if not key:
        return None
    named = [(e, [_heading_key(w) for w in e.get("brief") or [] if isinstance(w, str)]) for e in entries]
    for e, words in named:
        if key in words:
            return e
    for e, words in named:
        if any(w and re.search(rf"\b{re.escape(w)}\b", key) for w in words):
            return e
    return None


def title_of(text: str) -> str | None:
    """A brief's title: its first level-one heading."""
    for line in (text or "").splitlines():
        m = _HEADING.match(line)
        if m and len(m.group(1)) == 1 and m.group(2).strip():
            return fold(m.group(2))
    return None


def passages(text: str) -> list[dict]:
    """The brief cut into passages, by rule: `{heading, level, text, first, last}`, one per list item (its following
    indented lines joined to it) or per paragraph; a fenced block joins the passage before it. Lines count from 1."""
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[dict] = []
    heading, level = None, 0
    cur: dict | None = None
    fenced = False

    def close() -> None:
        nonlocal cur
        if cur is not None and fold(cur["text"]):
            out.append(cur)
        cur = None

    for i, raw in enumerate(lines, 1):
        if _FENCE.match(raw):
            fenced = not fenced
            if cur is None:
                cur = {"heading": heading, "level": level, "text": "", "first": i, "last": i}
            cur["text"] += "\n" + raw
            cur["last"] = i
            continue
        if fenced:
            if cur is not None:
                cur["text"] += "\n" + raw
                cur["last"] = i
            continue
        h = _HEADING.match(raw)
        if h:
            close()
            heading, level = h.group(2).strip(), len(h.group(1))
            continue
        if not raw.strip():
            close()
            continue
        it = _ITEM.match(raw)
        if it:
            close()
            cur = {"heading": heading, "level": level, "text": it.group(1), "first": i, "last": i, "item": True}
            continue
        if cur is None:
            cur = {"heading": heading, "level": level, "text": raw.strip(), "first": i, "last": i}
        else:
            cur["text"] += " " + raw.strip()
            cur["last"] = i
    close()
    for p in out:
        p.pop("item", None)
    return out


def read_brief(text: str, entries: list[dict] | None = None) -> tuple[list[tuple[dict, dict]], list[dict]]:
    """A brief read by rules: `(placed, unplaced)`. `placed` pairs a bank entry with each passage it answers: those
    under a heading the entry names; the passages before any section heading (under none, or under the title alone)
    answer `aim`. `unplaced` are the passages under a heading no entry names."""
    entries = [e for e in (entries if entries is not None else bank_entries()) if _writes(e) and e.get("brief")]
    aim = next((e for e in entries if e.get("id") == "aim"), None)
    placed: list[tuple[dict, dict]] = []
    unplaced: list[dict] = []
    for p in passages(text):
        if p["heading"] is None or p["level"] == 1:
            e = aim
        else:
            e = entry_for_heading(p["heading"], entries)
        if e is None:
            unplaced.append(p)
        else:
            placed.append((e, p))
    return placed, unplaced


def brief_items(placed: list[tuple[dict, dict]], nodes: list[dict], brief: str, *, confidence: float = 1,
                registry: mc.Registry | None = None) -> list[dict]:
    """The items the placed passages write, each in the person's words, citing its lines of the brief."""
    taken = {str(n.get("id")) for n in nodes if isinstance(n, dict)}
    out = []
    for e, p in placed:
        mk = _writes(e)
        if mk is None:
            continue
        lines = f"L{p['first']}" if p["first"] == p["last"] else f"L{p['first']}-L{p['last']}"
        prov = {"mode": "structured-intake", "sources": [f"{brief}#{lines}"], "confidence": confidence}
        out.append(make_item(mk[0], mk[1], p["text"], taken=taken, provenance=prov, sets=e.get("sets"),
                             registry=registry))
    return out


# ---------------------------------------------------------------------------
# The moves
# ---------------------------------------------------------------------------

def _request(ctx: Any) -> dict:
    """What the person said in beginning it, from the host's `authoring` engine (a callable), or nothing."""
    try:
        fn = (getattr(ctx, "engines", None) or {})[ENGINE]
    except (KeyError, TypeError):
        return {}
    got = fn()
    return dict(got) if isinstance(got, dict) else {}


def _stamp(ctx: Any) -> str:
    now = getattr(ctx, "now", None)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ") if now is not None else "1970-01-01T00:00:00Z"


def _program_name(ctx: Any) -> str | None:
    p = getattr(ctx, "program", None)
    if p is None:
        return None
    return getattr(p, "name", None) or str(p).replace("\\", "/").rsplit("/", 1)[-1]


def _place_by_model(ctx: Any, unplaced: list[dict], entries: list[dict]) -> list[tuple[dict, dict]]:
    """Ask the model which entry each passage the rules could not place answers. It answers only that: an entry's id
    per passage number, or nothing for one it cannot place; anything else it says is dropped."""
    usable = [e for e in entries if _writes(e)]
    numbered = "\n".join(f"{n}. {fold(p['text'])}" for n, p in enumerate(unplaced, 1))
    menu = "\n".join(f"- {e['id']}: {fold(e.get('asks', ''))}" for e in usable)
    cand = ctx.ask({"schema": {"format": "yaml", "says": "placed: a list of {passage: <number>, entry: <id>}"}},
                   {"step": Value("string", "author"), "passages": Value("string", numbered),
                    "entries": Value("string", menu)})
    try:
        data = answer_mapping(cand.get("output") if isinstance(cand, dict) else None)
    except ValueError:
        return []
    by_id = {e["id"]: e for e in usable}
    out, seen = [], set()
    for row in data.get("placed") or []:
        if not isinstance(row, dict):
            continue
        n, eid = row.get("passage"), row.get("entry")
        if isinstance(n, int) and 1 <= n <= len(unplaced) and n not in seen and eid in by_id:
            seen.add(n)
            out.append((by_id[eid], unplaced[n - 1]))
    return out


def author(ctx: Any, brief: Value | None = None, **mods: Any) -> Value:
    """`author brief as tool`, or `author as tool` (an interview): an authored fabulac begun (THYM 20.11)."""
    kind = _as_word(mods.get("as")) or "tool"
    req = _request(ctx)
    text = _text(brief) if isinstance(brief, Value) and not brief.is_nothing else None
    name = req.get("name") or (title_of(text) if text else None)
    if not name:
        raise MoveError("author: the program needs a name: give the brief a title (a first heading), or name it "
                        "when it is begun")
    brief_name = req.get("brief")
    if text is not None and not brief_name:
        p = getattr(brief, "path", None)
        brief_name = p.name if p is not None else "brief.md"
    at = _stamp(ctx)
    entries = bank_entries()
    placed, unplaced = read_brief(text, entries) if text is not None else ([], [])
    by_model: list[tuple[dict, dict]] = []
    if unplaced and not getattr(ctx, "rules", False) and req.get("model", True) is not False:
        by_model = _place_by_model(ctx, unplaced, entries)
    cat = begin(name, kind=kind, licence=req.get("licence"), by=req.get("by"), at=at,
                brief=brief_name or None, program=_program_name(ctx),
                run=getattr(ctx, "run", None), mode="model" if by_model else "rules")
    nodes = cat["nodes"]
    if text is not None:
        nodes.extend(brief_items(placed, nodes, brief_name))
        nodes.extend(brief_items(by_model, nodes, brief_name, confidence=PLACED_CONFIDENCE))
    left = [p for p in unplaced if all(p is not q for _e, q in by_model)]
    return Value("fabula", cat, origin={"author": {
        "brief": brief_name, "placed": len(placed), "placed-by-model": len(by_model),
        "unplaced": [{"lines": [p["first"], p["last"]], "heading": p["heading"], "text": fold(p["text"])[:200]}
                     for p in left]}})


@implements(SCAFFOLD)
def catalog_alone(ctx: Any, *operands: Any, **mods: Any) -> Value:
    """The scaffold of `author` with no brief: the move itself, by rules (a brief has none: `--rules` refuses it)."""
    if operands and isinstance(operands[0], Value) and not operands[0].is_nothing:
        raise MoveError("author with a brief asks a model for what its headings do not place; --rules runs no model")
    return author(ctx, **mods)


def add(ctx: Any, said: Value, **mods: Any) -> Value:
    """`add said as requirement with f` (as decision, case, interface): the person's sentence as a new item."""
    word = _as_word(mods.get("as"))
    if word not in ADD_KINDS:
        raise MoveError("add writes a requirement, a decision, a case or an interface: add said as requirement with f")
    w = mods.get("with")
    if not isinstance(w, Value) or w.type not in ("fabula", "volume"):
        raise MoveError("add needs the fabulac it adds to: add said as requirement with f")
    cat, nodes = fabula_doc(w)
    if not is_authored(cat):
        raise MoveError("add takes only an authored fabulac (its source says kind: authored); a decompiled one is "
                        "changed through its questions")
    text = fold(_text(said))
    if not text:
        raise MoveError("add needs the sentence to write")
    mod, kind = ADD_KINDS[word]
    taken = {str(n.get("id")) for n in nodes}
    item = make_item(mod, kind, text, taken=taken, asks=ADD_ASKS,
                     provenance={"mode": "manual", "sources": ["the author, in their own words"], "confidence": 1})
    out = {**{k: v for k, v in cat.items() if k != "nodes"}, "nodes": [*nodes, item]}
    return Value("fabula", out, origin={"added": item["id"]})


def _items(v: Value) -> dict[str, dict]:
    _cat, nodes = fabula_doc(v)
    return {str(n["id"]): n for n in nodes if isinstance(n, dict) and isinstance(n.get("id"), str)}


def compare_docs(a: dict, b: dict, items_a: dict[str, dict], items_b: dict[str, dict]) -> dict:
    """What differs between two fabulacs: the catalog keys, and item by item by id, each field that differs."""
    changed = []
    for iid in sorted(set(items_a) & set(items_b)):
        x, y = items_a[iid], items_b[iid]
        fields = sorted(k for k in set(x) | set(y) if x.get(k) != y.get(k))
        if fields:
            changed.append({"id": iid, "fields": fields})
    cat = sorted(str(k) for k in set(a) | set(b) if k != "nodes" and a.get(k) != b.get(k))
    return {"catalog": cat, "only-in-first": sorted(set(items_a) - set(items_b)),
            "only-in-second": sorted(set(items_b) - set(items_a)), "changed": changed,
            "same": len(set(items_a) & set(items_b)) - len(changed)}


def compare(ctx: Any, f: Value, **mods: Any) -> Value:
    """`compare f with g`: the report of what differs, item by item."""
    g = mods.get("with")
    if not isinstance(g, Value) or g.type not in ("fabula", "volume"):
        raise MoveError("compare needs a second fabulac: compare f with g")
    a, _ = fabula_doc(f)
    b, _ = fabula_doc(g)
    return Value("report", compare_docs(a, b, _items(f), _items(g)))


def _cases_named(d: dict) -> list[str]:
    cb = d.get("checked-by")
    if mc.is_pending(cb) or cb is None:
        return []
    return [str(x) for x in (cb if isinstance(cb, list) else [cb]) if isinstance(x, str) and x.strip()]


def uncovered_items(nodes: list[dict]) -> list[dict]:
    """The requirements of `force: must` that name no case in `checked-by` (what `requirement-cased` warns of)."""
    return [d for d in nodes if isinstance(d, dict) and str(d.get("id", "")).startswith("N:requirement/")
            and d.get("force") == "must" and not _cases_named(d)]


def uncovered(ctx: Any, f: Value, **mods: Any) -> Value:
    """`uncovered f`: the requirements a program must meet that no case shows, as items."""
    _cat, nodes = fabula_doc(f)
    return Value("list", [Value("item", d, origin={"item": True, "id": d.get("id")}) for d in uncovered_items(nodes)])


# ---------------------------------------------------------------------------
# The model's request (a passage of a brief the rules could not place)
# ---------------------------------------------------------------------------

AUTHOR_SYSTEM = ("A person wrote a brief for a program they mean to make. Some passages of it sit under headings the "
                 "rules do not know. For each passage, say which question of the interview it answers, by the "
                 "question's id, or leave it out when it answers none. Answer in YAML only: placed: a list of "
                 "{passage: <number>, entry: <id>}. Never rewrite a passage, never add one.")


def author_messages(contract: dict, inputs: dict) -> list[dict] | None:
    """The request `author` makes of the model; None for a request that is not its own."""
    def get(name: str) -> str:
        pair = (inputs or {}).get(name)
        v = pair[0] if isinstance(pair, tuple) else pair
        return _text(v)
    if get("step") != "author":
        return None
    user = (f"The questions of the interview, by id:\n{get('entries')}\n\nThe passages, numbered:\n"
            f"{get('passages')}\n\nWhich question does each passage answer?")
    return [{"role": "system", "content": AUTHOR_SYSTEM}, {"role": "user", "content": user}]


PROMPTS = {"author": author_messages}


# ---------------------------------------------------------------------------
# The check
# ---------------------------------------------------------------------------

def source_problems(cat: dict) -> list[str]:
    """What the authored form of `source` and the `program` block lack (MacroCOSM OES 18.4.1, 18.4.7)."""
    src = cat.get("source") if isinstance(cat.get("source"), dict) else None
    if src is None or src.get("kind") != AUTHORED:
        return ["the fabulac's source is not the authored form (source: {kind: authored, …})"]
    out = []
    if not (isinstance(src.get("language"), str) and src["language"].strip()):
        out.append("source.language names the language its entailments are written in")
    lic = src.get("licence")
    if not ((isinstance(lic, str) and lic.strip()) or mc.is_pending(lic)):
        out.append("source.licence is the licence, or {pending: …} until the person gives one")
    by = src.get("by")
    if not (isinstance(by, list) and by and all(isinstance(x, str) and x.startswith("R:maker/") for x in by)):
        out.append("source.by names who authored it: a list of R:maker items")
    if not src.get("at"):
        out.append("source.at is the day it was begun")
    prog = cat.get("program") if isinstance(cat.get("program"), dict) else {}
    if prog.get("kind") not in KINDS:
        out.append("the catalog's program names a kind: tool, library or service")
    return out


@check("authored-source")
def _authored_source(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """The source is the authored form and `program` names a kind; every item the move wrote is an axiom, written
    from a brief (`structured-intake`), by `add` (`manual`) or from an answer (`dialectic`); an item read from a brief
    says only what the brief says (Thym 7.3)."""
    cat, nodes = fabula_doc(output)
    bad = source_problems(cat)
    if bad:
        return False, "; ".join(bad)
    before: set[str] = set()
    brief = None
    for v in inputs.values():
        if isinstance(v, Value) and v.type in ("fabula", "volume"):
            before |= set(_items(v))
        elif isinstance(v, Value) and v.type == "text":
            brief = fold(_text(v))
    have = {str(n.get("id")) for n in nodes}
    for iid in sorted(before - have):
        return False, f"{iid} was in the fabulac and is not now"
    for n in nodes:
        iid = str(n.get("id", ""))
        if iid in before or iid.startswith("D:"):
            continue
        if n.get("stance") != "axiom":
            return False, f"{iid} is not an axiom: an authored item is so because its author says so"
        mode = (n.get("provenance") or {}).get("mode") if isinstance(n.get("provenance"), dict) else None
        if mode not in MODES:
            return False, f"{iid}: provenance.mode is {mode!r}, not {', '.join(MODES)}"
        if mode == "structured-intake":
            if brief is None:
                return False, f"{iid} says a brief gave it, and no brief was given"
            if fold(str(n.get("summary") or "")) not in brief:
                return False, f"{iid} says what the brief does not: its summary is not the brief's own words"
    return True, ""


__all__ = ["ADD_KINDS", "AUTHORED", "BANK", "ENGINE", "KINDS", "MODES", "PROMPTS", "SCAFFOLD", "add", "author",
           "author_messages", "bank_entries", "begin", "brief_items", "catalog_alone", "compare", "compare_docs",
           "entry_for_heading", "is_authored", "make_item", "passages", "program_block", "read_brief",
           "source_problems", "stages", "title_of", "uncovered", "uncovered_items"]
