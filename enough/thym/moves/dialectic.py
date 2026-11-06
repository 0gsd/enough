"""The dialectic's three moves of `thym 1` (THYM 22; MacroCOSM OES 18.6): `question`, `record` and `settle`, the checks
`addressed`, `no-duplicate` and `only-the-asked`, the scaffolds `bank` and `direct`, and the prompt builders of the
two moves that ask a model.

The dialectic is two whole runs with a person between them. The first run lands questions with the volume (`question
v`, landed with `gather asked with v`); the person answers them in a page or through an agent, which writes an answers
volume beside the volume; the second run records the answers (`record said in f`) and settles them into the items they
are about (`settle f`). No run waits on a person.

**The engine.** These moves never read or write a volume's questions themselves: they reach the dialectic's
deterministic core only through `ctx.engines["dialectic"]`, which the host supplies (this folder is vendored into a
product that brings its own). Every engine call is recorded and replayed with the run, so every argument and every
answer is plain data (text, mappings, lists, strings, whole numbers and timestamps; never a float). The engine answers
exactly these three functions:

- `thym_question(volume, *, proposed=None, run=None, at=None) -> {questions, refused, skipped}`: the volume's new
  open questions by rules (its banks, every `{pending}` value, every item below confidence 0.5 or pending), then the
  `proposed` ones (mappings `{about, asks, why, kind, options?, options-open?, many?, hint?, from?, id?}`), each
  validated by the core's hook (it resolves, it is no duplicate, it passes the volume's checks). `questions` are the
  D:question items, in order; `refused` is `[{index, about, asks, why}]`, `index` the proposal's position in
  `proposed`; `skipped` is `[{source, why}]`. It writes nothing.
- `thym_record(volume, answers) -> {text, recorded} | {refused}`: the answers volume (`answers` is `{text}`) recorded
  into the volume, all or none; `text` is the volume's new text, every byte outside the change kept; `recorded` is
  `[[question id, state]]`. A refusal is `{refused: <plain words>}` and nothing is recorded.
- `thym_settle(volume, *, rereads=None, run=None, program=None, at=None, model=None, route=None, provider=None,
  dry=False) -> {text, settled, counters, needs_reading, refused_rereads, stale, waiting}`: every answered, unknown
  or declined question folded by rules. `rereads` is `{question id: <the item's new fields, as YAML text>}`, the
  model's re-reading of an item an answer means must be read again; a re-read that would add a check error is not
  written (listed in `refused_rereads` as `{question, errors}`) and its question stays unsettled, with no counter
  question. `needs_reading` is `[{question, about, because, item, asks, says, value}]` (`item` the item as YAML text,
  or null for a passage). With `dry`, the same answer, and nothing is meant to land: the caller keeps its volume.

A `volume` argument is `{text, filename}` (a single-file volume) or `{path}` (a folder volume, which `question` reads
and `record` and `settle` refuse: a folder volume keeps its questions in its own layout). With no such engine, or one
that lacks a function, the move refuses in plain words.

**The model.** `question` asks, one keyed request per chunk of the volume's items (twelve at a time), for the
questions only a person can answer, with one prompt per flavour (prose, verse, code); a proposal in the wrong shape,
about nothing read in that chunk, asking two things, in someone's voice, leading, or asking what the fabula already
says surely, is dropped and counted, and so is one the core's hook refuses. A request whose answer gave nothing that
could be kept (it did not read, or every proposal was dropped) is asked again once, with why. `settle` asks only for
an item that must be read again, one keyed request per item, for the item rewritten; a rewrite the volume's checks
refuse is asked again once with their words, and then left. Under `--rules` the scaffolds run: `bank` (the rules'
questions alone) and `direct` (the rules alone; what must be read again stays answered and unsettled).

**The checks** read the values alone and ask no engine, so that a replay and a program's `keeps` hold them the same
way: `addressed`, `no-duplicate`, `only-the-asked` (THYM 7.3).

Standalone: the standard library, PyYAML and the MacroCOSM reader.
"""
from __future__ import annotations

import copy
import re
from typing import Any

from enough import macrocosm as mc
from enough.thym.checks import check
from enough.thym.moves import MoveError, fabula_doc, strip_fences
from enough.thym.registry import implements, prompt_for
from enough.thym.values import Value, plain

ENGINE = "dialectic"
FUNCTIONS = ("thym_question", "thym_record", "thym_settle")
CHUNK_ITEMS = 12                     # items per request of `question`
ASKS_PER_REQUEST = 2                 # a request is asked again once when nothing could be kept
MODEL_WHYS = ("unsure", "ambiguous", "conflict", "intent")
ANSWER_KINDS = ("text", "choice", "yes-no", "number", "date", "ref", "span")
PROPOSAL_KEYS = ("about", "asks", "why", "kind", "options", "options-open", "many", "hint", "id")
ANSWERED = ("answered", "unknown", "declined")
ENDED = ("stale", "withdrawn")
ALWAYS_WRITABLE = ("provenance", "withheld", "pending")      # what settling may change on any item it writes
_VOICE = re.compile(r"(?:^|[\s\"'(])(?:i|i'm|i'd|i've|me|my|mine|we|we're|our|ours|us)(?=$|[\s,.;:!?\"')])", re.I)
_LEADING = re.compile(r"^\s*(?:isn't|aren't|wasn't|don't|doesn't|didn't|wouldn't|surely|of course)\b", re.I)
_PUNCT = re.compile(r"[^\w\s]")
_FIELD = re.compile(r"^[A-Za-z0-9_-]+(?:\[[0-9]+\])?(?:\.[A-Za-z0-9_-]+(?:\[[0-9]+\])?)*$")
_LINES = re.compile(r"^\s*([0-9]+)(?:\s*-\s*([0-9]+))?\s*$")


# ---------------------------------------------------------------------------
# The engine, and the volume as the engine takes it
# ---------------------------------------------------------------------------

def _engine(ctx: Any, move: str, fn: str) -> Any:
    """`ctx.engines["dialectic"].<fn>`, or a refusal in plain words."""
    engines = getattr(ctx, "engines", None) or {}
    try:
        eng = engines.get(ENGINE) if hasattr(engines, "get") else None
    except Exception:  # noqa: BLE001 - an engine table that cannot answer is no engine
        eng = None
    if eng is None:
        raise MoveError(f"{move} needs the dialectic engine, which keeps a volume's questions and answers, and this "
                        "host has none")
    got = getattr(eng, fn, None)
    if got is None or not callable(got):
        raise MoveError(f"the dialectic engine here cannot {_DOES[fn]}, which {move} needs")
    return got


_DOES = {"thym_question": "raise questions", "thym_record": "record answers", "thym_settle": "settle answers"}


def _filename(v: Value, fallback: str) -> str:
    if v.path is not None:
        return v.path.name
    cat = v.mapping() or {}
    fl = cat.get("flavour")
    return f"{fallback}.{fl}.cosm" if isinstance(fl, str) else f"{fallback}.cosm"


def _volume_arg(v: Value, move: str, *, single: bool) -> dict:
    """A fabula or a volume as the engine takes it: `{text, filename}`, or `{path}` for a folder volume."""
    if not isinstance(v, Value) or v.type not in ("fabula", "volume"):
        raise MoveError(f"{move} takes a fabula or a volume, and was given a {getattr(v, 'type', 'nothing')}")
    p = v.payload
    if isinstance(p, mc.Volume):
        if single:
            raise MoveError(f"{move} writes into a volume of one file, and {v.path.name if v.path else 'this'} is a "
                            "folder volume, which keeps its questions in its own layout")
        return {"path": str(v.path or p.path)}
    if v.raw is not None:
        return {"text": v.raw.decode("utf-8"), "filename": _filename(v, "volume")}
    if isinstance(p, dict):
        return {"text": mc.dump(plain(p)), "filename": _filename(v, "volume")}
    raise MoveError(f"{move} takes a fabula or a volume, and this {v.type} holds neither")


def _volume_value(v: Value, text: str) -> Value:
    """The engine's new text as a value of v's type: its bytes are the text, so every byte the engine kept is kept."""
    data = mc.yaml_load(text)
    if not isinstance(data, dict):
        raise MoveError("the dialectic engine gave back something that is not a volume")
    return Value(v.type, data, raw=text.encode("utf-8"))


def _doc(v: Any) -> tuple[dict, list[dict]]:
    """A value's catalog and items as plain mappings (`{}`, `[]` for anything else)."""
    if not isinstance(v, Value) or v.is_nothing:
        return {}, []
    if v.raw is not None and not isinstance(v.payload, mc.Volume):
        try:
            data = mc.yaml_load(v.raw.decode("utf-8-sig"))
        except Exception:  # noqa: BLE001
            data = None
        if isinstance(data, dict):
            return data, [n for n in data.get("nodes") or [] if isinstance(n, dict)]
    cat, items = fabula_doc(v)
    return cat, items


def _flavour(cat: dict) -> str:
    fl = cat.get("flavour")
    if isinstance(fl, str) and fl:
        return fl
    oes = str(cat.get("oes") or "")
    return "fabulan" if oes.startswith(("emf/", "fabula/")) else (oes.split("/")[0] or "volume")


def _is_d(item: dict) -> bool:
    return isinstance(item.get("id"), str) and item["id"].split("//")[-1].startswith("D:")


def _is_question(item: dict) -> bool:
    return isinstance(item.get("id"), str) and item["id"].split("//")[-1].startswith("D:question/")


def _bare(ref: str) -> str:
    return ref.rpartition("//")[2] if "//" in ref else ref


def _about_key(about: Any) -> str:
    if isinstance(about, str):
        return about
    return mc.dump(plain(about)).strip() if isinstance(about, dict) else str(about)


def _norm(text: Any) -> str:
    return " ".join(_PUNCT.sub(" ", str(text or "").lower()).split())


def _model_of(cand: dict) -> tuple[str | None, str | None, str | None]:
    """(model, route, provider) of a candidate, as the host stamps them."""
    e = cand.get("engine") if isinstance(cand, dict) else None
    model = e[6:].strip() if isinstance(e, str) and e.startswith("model:") and e[6:].strip() not in ("", "unknown") \
        else None
    route = cand.get("route") if isinstance(cand.get("route"), str) else None
    provider = cand.get("provider") if isinstance(cand.get("provider"), str) else None
    return model, route, provider


def _program(ctx: Any) -> str | None:
    p = getattr(ctx, "program", None)
    if p is None:
        return None
    return getattr(p, "name", None) or str(p).replace("\\", "/").rsplit("/", 1)[-1]


# ---------------------------------------------------------------------------
# question
# ---------------------------------------------------------------------------

def _compact(item: dict) -> dict:
    """An item as the model reads it: everything but `made`; of its provenance, how sure it is and its state."""
    out = {k: plain(v) for k, v in item.items() if k not in ("made", "provenance")}
    prov = item.get("provenance")
    if isinstance(prov, dict):
        keep = {k: prov[k] for k in ("confidence", "state") if k in prov}
        if keep:
            out["provenance"] = plain(keep)
    return out


def _passage(v: Value, items: list[dict]) -> str:
    """The source's lines the items' spans name, numbered, when the value carries its source text; else ''."""
    src = (v.origin or {}).get("source_text") if isinstance(v.origin, dict) else None
    if not isinstance(src, str) or not src:
        return ""
    lines = src.replace("\r\n", "\n").split("\n")
    want: set[int] = set()
    for it in items:
        span = it.get("span")
        if isinstance(span, dict) and isinstance(span.get("lines"), str):
            m = _LINES.match(span["lines"])
            if m:
                a, b = int(m.group(1)), int(m.group(2) or m.group(1))
                want.update(range(a, min(b, len(lines)) + 1))
    return "\n".join(f"{n:>4}  {lines[n - 1]}" for n in sorted(want) if 1 <= n <= len(lines))


def _chunks(items: list[dict]) -> list[list[dict]]:
    rows = [it for it in items if isinstance(it.get("id"), str) and not _is_d(it)]
    return [rows[i:i + CHUNK_ITEMS] for i in range(0, len(rows), CHUNK_ITEMS)]


def _read_proposals(out: Any) -> list:
    """The model's answer as a list of proposals: `questions: [...]` (or a bare list). ValueError otherwise."""
    data = out
    if not isinstance(data, (dict, list)):
        try:
            data = mc.yaml_load(strip_fences(str(out or "")))
        except Exception as e:  # noqa: BLE001 - YAML that does not parse is an answer that does not read
            raise ValueError(f"it is not YAML ({str(e).splitlines()[0]})") from None
    if isinstance(data, dict):
        if "questions" not in data:
            raise ValueError("the answer holds no questions: list")
        data = data["questions"]
    if data is None:
        return []
    if not isinstance(data, list):
        raise ValueError("questions is not a list")
    return data


def _field_value(item: dict, fpath: str) -> tuple[bool, Any]:
    cur: Any = item
    for part in re.findall(r"[^.\[\]]+|\[[0-9]+\]", fpath):
        if part.startswith("["):
            i = int(part[1:-1])
            if not isinstance(cur, list) or i >= len(cur):
                return False, None
            cur = cur[i]
        else:
            if not isinstance(cur, dict) or part not in cur:
                return False, None
            cur = cur[part]
    return True, cur


def _confidence(item: dict) -> Any:
    prov = item.get("provenance")
    c = prov.get("confidence") if isinstance(prov, dict) else None
    return c if c is not None else item.get("confidence")


def proposal_problem(p: Any, chunk: dict[str, dict]) -> str | None:
    """Why a proposed question cannot be kept, by its shape and what it asks; None when it may go to the core's hook.
    `chunk` holds the items of the request, by bare id."""
    if not isinstance(p, dict):
        return "a proposal is a mapping of about, asks, why and kind"
    extra = [k for k in p if k not in PROPOSAL_KEYS and k != "to"]
    if extra:
        return f"it carries {extra[0]}, which a proposal does not"
    asks = p.get("asks")
    if not isinstance(asks, str) or not asks.strip():
        return "it asks nothing"
    asks = asks.strip()
    if "\n" in asks or len(asks) > 240:
        return "it is more than one plain sentence"
    if not asks.endswith("?"):
        return "it does not end with a question mark"
    if asks.count("?") > 1:
        return "it asks more than one thing"
    if _VOICE.search(asks):
        return "it speaks in someone's voice (I, me, we, our)"
    if _LEADING.match(asks):
        return "it leads the person to an answer"
    if p.get("why") not in MODEL_WHYS:
        return f"why is {p.get('why')!r}; a model asks where the fabula is unsure, ambiguous, in conflict or silent " \
               "on intent"
    kind = p.get("kind")
    if kind not in ANSWER_KINDS:
        return f"kind is {kind!r}, not one of {', '.join(ANSWER_KINDS)}"
    if kind == "choice":
        opts = p.get("options")
        if not (isinstance(opts, list) and 2 <= len(opts) <= 8 and all(isinstance(o, str) and o.strip()
                                                                        for o in opts)):
            return "a choice lists two to eight options"
    about = p.get("about")
    if isinstance(about, dict):
        return None if ("lines" in about or ("start" in about and "end" in about)) else \
            "it is about a passage that names no lines"
    if not isinstance(about, str) or not about.strip():
        return "it is about nothing"
    base, sep, fpath = about.strip().partition("#")
    item = chunk.get(_bare(base))
    if item is None:
        return f"it is about {about}, which is no item read here"
    if sep and not _FIELD.match(fpath):
        return f"{fpath!r} is not a field path"
    if sep and p["why"] == "unsure":
        found, val = _field_value(item, fpath)
        conf = _confidence(item)
        sure = isinstance(conf, (int, float)) and not isinstance(conf, bool) and conf >= 0.5
        if found and not mc.is_pending(val) and val not in (None, "", [], {}) and sure:
            return f"the fabula already says {about}, and is sure of it"
    return None


def _proposal(p: dict) -> dict:
    """A kept proposal as the core's hook takes it: the stage is `question`, the answerer the bank's."""
    out = {k: copy.deepcopy(p[k]) for k in PROPOSAL_KEYS if k in p}
    out["asks"] = out["asks"].strip()
    if isinstance(out.get("about"), str):
        out["about"] = out["about"].strip()
    out["from"] = "question"
    return out


def _ask_chunk(ctx: Any, v: Value, vol: dict, chunk: list[dict], asked: list[dict], flavour: str, name: str,
               qfn: Any) -> tuple[list[dict], list[dict]]:
    """One chunk's request (asked again once when nothing could be kept): (kept proposals, dropped
    `{about, asks, why}`)."""
    by_id = {_bare(it["id"]): it for it in chunk}
    about_here = [q for q in asked if _bare(str(q.get("about", "")).partition("#")[0]) in by_id
                  or not isinstance(q.get("about"), str)]
    inputs = {"flavour": Value("word", flavour), "volume": Value("string", name),
              "items": Value("string", mc.dump({"items": [_compact(it) for it in chunk]})),
              "asked": Value("string", "\n".join(f"- {_about_key(q.get('about'))}: {q.get('asks')}"
                                                 for q in about_here) or "(nothing yet)")}
    passage = _passage(v, chunk)
    if passage:
        inputs["passage"] = Value("string", passage)
    dropped: list[dict] = []
    failed: list[dict] = []
    for _try in range(ASKS_PER_REQUEST):
        contract = {"schema": {"format": "yaml", "stamp": "engine", "says": QUESTION_SAYS},
                    "repair": {"allowed": [], "failed": failed}}
        cand = ctx.ask(contract, inputs)
        out = cand.get("output") if isinstance(cand, dict) else cand
        try:
            props = _read_proposals(out)
        except ValueError as e:
            dropped.append({"about": None, "asks": None, "why": f"the answer could not be read: {e}"})
            failed = [{"name": "questions", "ok": False, "why": f"the answer could not be read: {e}"}]
            continue
        if not props:
            return [], dropped                      # nothing here needs a person: a fine answer
        kept, reasons = [], []
        for p in props:
            why = proposal_problem(p, by_id)
            if why:
                reasons.append(why)
                dropped.append({"about": _about_key(p.get("about")) if isinstance(p, dict) else None,
                                "asks": p.get("asks") if isinstance(p, dict) else None, "why": why})
            else:
                kept.append(_proposal(p))
        if kept:
            res = qfn(vol, proposed=kept, run=getattr(ctx, "run", None), at=getattr(ctx, "now", None))
            refused = {int(r["index"]): str(r.get("why")) for r in res.get("refused") or []
                       if isinstance(r, dict) and isinstance(r.get("index"), int)}
            for i, why in sorted(refused.items()):
                reasons.append(why)
                dropped.append({"about": _about_key(kept[i].get("about")), "asks": kept[i].get("asks"), "why": why})
            kept = [p for i, p in enumerate(kept) if i not in refused]
        if kept:
            return kept, dropped
        failed = [{"name": "questions", "ok": False, "why": "no question could be kept: " + "; ".join(reasons[:6])}]
    return [], dropped


def _questions_value(res: dict, *, rules: int | None = None, dropped: list | None = None,
                     asked_model: bool = False) -> Value:
    qs = [q for q in res.get("questions") or [] if isinstance(q, dict)]
    by_model = sum(1 for q in qs if (q.get("raised") or {}).get("by") == "model")
    members = [Value("item", q, origin={"item": True, "id": q.get("id")}) for q in qs]
    return Value("list", members, origin={"question": {
        "rules": len(qs) - by_model if rules is None else rules, "model": by_model, "asked_model": asked_model,
        "dropped": list(dropped or []), "skipped": len(res.get("skipped") or [])}})


@implements("question")
def question(ctx: Any, v: Value, **_: Any) -> Value:
    """`question v`: the questions to put to a person about v (THYM 22.1): the rules' (its banks, every pending value,
    every unsure item), and those a model raises where v is unsure, ambiguous, in conflict or silent on intent. A
    list of D:question items, each `open`, landed with `gather asked with v`."""
    vol = _volume_arg(v, "question", single=False)
    qfn = _engine(ctx, "question", "thym_question")
    run, at = getattr(ctx, "run", None), getattr(ctx, "now", None)
    rules = qfn(vol, run=run, at=at)
    cat, items = _doc(v)
    chunks = _chunks(items)
    if not chunks:
        return _questions_value(rules)
    standing = [q for q in items if _is_question(q) and q.get("state") not in ENDED]
    asked = standing + [q for q in rules.get("questions") or [] if isinstance(q, dict)]
    flavour = _flavour(cat)
    name = str(cat.get("name") or cat.get("id") or "the volume")
    proposals: list[dict] = []
    dropped: list[dict] = []
    for chunk in chunks:
        kept, lost = _ask_chunk(ctx, v, vol, chunk, asked, flavour, name, qfn)
        proposals += kept
        dropped += lost
    if not proposals:
        return _questions_value(rules, dropped=dropped, asked_model=True)
    final = qfn(vol, proposed=proposals, run=run, at=at)
    for r in final.get("refused") or []:                # across chunks: one asks what another already asked
        if isinstance(r, dict):
            dropped.append({"about": r.get("about"), "asks": r.get("asks"), "why": r.get("why")})
    return _questions_value(final, dropped=dropped, asked_model=True)


@implements("question.scaffold")
@implements("bank")
def bank(ctx: Any, v: Value, **_: Any) -> Value:
    """The scaffold `bank`: `question` by rules alone (its banks, every pending value, every unsure item)."""
    vol = _volume_arg(v, "question", single=False)
    qfn = _engine(ctx, "question", "thym_question")
    return _questions_value(qfn(vol, run=getattr(ctx, "run", None), at=getattr(ctx, "now", None)))


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------

@implements("record")
def record(ctx: Any, said: Value, **mods: Any) -> Value:
    """`record said in f`: the answers volume's answers appended to f's questions, each question's state moved, the
    session added (THYM 22.2). Code: no model. All or none."""
    f = mods.get("in")
    if not isinstance(f, Value) or f.type not in ("fabula", "volume"):
        raise MoveError("record needs the volume the answers are for: record said in f")
    if not isinstance(said, Value) or said.type != "volume" or (said.raw is None and not isinstance(said.payload,
                                                                                                    dict)):
        raise MoveError("record reads an answers volume, the file a page or an agent writes beside the volume")
    vol = _volume_arg(f, "record", single=True)
    text = said.raw.decode("utf-8") if said.raw is not None else mc.dump(plain(said.payload))
    res = _engine(ctx, "record", "thym_record")(vol, {"text": text})
    if res.get("refused"):
        raise MoveError(str(res["refused"]))
    out = _volume_value(f, str(res["text"]))
    out.origin = {"record": {"recorded": [list(x) for x in res.get("recorded") or []]}}
    return out


# ---------------------------------------------------------------------------
# settle
# ---------------------------------------------------------------------------

def _reread_fields(old: dict, out: Any) -> dict:
    """The model's rewritten item as the fields that changed: `{field: value}`. ValueError when it is not the item."""
    data = out
    if not isinstance(data, dict):
        try:
            data = mc.yaml_load(strip_fences(str(out or "")))
        except Exception as e:  # noqa: BLE001
            raise ValueError(f"it is not YAML ({str(e).splitlines()[0]})") from None
    if isinstance(data, dict) and isinstance(data.get("item"), dict):
        data = data["item"]
    if not isinstance(data, dict):
        raise ValueError("the answer is not the item as a YAML mapping")
    if data.get("id") != old.get("id") or data.get("type", old.get("type")) != old.get("type"):
        raise ValueError(f"the answer is not {old.get('id')}: keep its id and its type")
    fields = {str(k): plain(v) for k, v in data.items()
              if k not in ("id", "type", "provenance", "made") and plain(v) != plain(old.get(k))}
    if not fields:
        raise ValueError("the item came back unchanged")
    return fields


def _reread(ctx: Any, row: dict, flavour: str, sfn: Any, vol: dict) -> tuple[str | None, list[dict], dict]:
    """One item read again: (its new fields as YAML text, or None when no rewrite could be kept; why each try failed;
    the last candidate)."""
    item_text = row.get("item")
    old = mc.yaml_load(item_text) if isinstance(item_text, str) else None
    if not isinstance(old, dict):
        return None, [{"why": "the answer is about a passage, with no item to write into"}], {}
    inputs = {"flavour": Value("word", flavour), "item": Value("string", item_text),
              "asks": Value("string", str(row.get("asks") or "")), "says": Value("string", str(row.get("says") or "")),
              "value": Value("string", str(row.get("value") or "")),
              "because": Value("string", str(row.get("because") or ""))}
    failed: list[dict] = []
    tries: list[dict] = []
    cand: dict = {}
    for _try in range(ASKS_PER_REQUEST):
        contract = {"schema": {"format": "yaml", "stamp": "engine", "says": SETTLE_SAYS},
                    "repair": {"allowed": [], "failed": failed}}
        cand = ctx.ask(contract, inputs)
        try:
            fields = _reread_fields(old, cand.get("output") if isinstance(cand, dict) else cand)
        except ValueError as e:
            tries.append({"why": str(e)})
            failed = [{"name": "item", "ok": False, "why": str(e)}]
            continue
        text = mc.dump(fields)
        test = sfn(vol, rereads={row["question"]: text}, run=getattr(ctx, "run", None),
                   at=getattr(ctx, "now", None), dry=True)
        bad = [r for r in test.get("refused_rereads") or [] if isinstance(r, dict)
               and r.get("question") == row["question"]]
        if not bad:
            return text, tries, cand
        why = "; ".join(str(e) for e in bad[0].get("errors") or []) or "it breaks the volume's checks"
        tries.append({"why": why})
        failed = [{"name": "fabula-checks", "ok": False, "why": why}]
    return None, tries, cand


def _settled_value(v: Value, res: dict, **origin: Any) -> Value:
    out = _volume_value(v, str(res["text"]))
    out.origin = {"settle": {"settled": [list(x) for x in res.get("settled") or []],
                             "counters": [list(x[:2]) for x in res.get("counters") or []],
                             "needs_reading": [{k: r.get(k) for k in ("question", "about", "because")}
                                               for r in res.get("needs_reading") or [] if isinstance(r, dict)],
                             **origin}}
    return out


@implements("settle")
def settle(ctx: Any, f: Value, **_: Any) -> Value:
    """`settle f`: every answered question folded into what it is about, by rules (THYM 22.3; MacroCOSM 18.6.4); the
    model is asked only to read again an item an answer means must be read again, one request per item."""
    vol = _volume_arg(f, "settle", single=True)
    sfn = _engine(ctx, "settle", "thym_settle")
    run, at, program = getattr(ctx, "run", None), getattr(ctx, "now", None), _program(ctx)
    first = sfn(vol, run=run, program=program, at=at, dry=True)
    rows = [r for r in first.get("needs_reading") or [] if isinstance(r, dict) and r.get("question")]
    if not rows:
        res = sfn(vol, run=run, program=program, at=at)
        return _settled_value(f, res, reread=[])
    flavour = _flavour(_doc(f)[0])
    rereads: dict[str, str] = {}
    left: list[dict] = []
    who: tuple = (None, None, None)
    for row in rows:
        text, tries, cand = _reread(ctx, row, flavour, sfn, vol)
        if cand:
            who = _model_of(cand) if any(_model_of(cand)) else who
        if text is None:
            left.append({"question": row["question"], "tries": tries})
        else:
            rereads[row["question"]] = text
    model, route, provider = who
    res = sfn(vol, rereads=rereads, run=run, program=program, at=at, model=model, route=route, provider=provider)
    return _settled_value(f, res, reread=sorted(rereads), left=left)


@implements("settle.scaffold")
@implements("direct")
def direct(ctx: Any, f: Value, **_: Any) -> Value:
    """The scaffold `direct`: `settle` by rules alone. An answer that means an item must be read again is not
    written: its question stays answered and unsettled (the core lists it), to be settled by a run with a model."""
    vol = _volume_arg(f, "settle", single=True)
    res = _engine(ctx, "settle", "thym_settle")(vol, run=getattr(ctx, "run", None), program=_program(ctx),
                                                at=getattr(ctx, "now", None))
    return _settled_value(f, res, reread=[])


# ---------------------------------------------------------------------------
# The prompts: one per flavour for `question`, one for `settle`'s re-reading
# ---------------------------------------------------------------------------

QUESTION_SAYS = ("questions: a list of {about, asks, why, kind, options?, hint?}; about an item id from the items, "
                 "or <id>#<field>; why unsure, ambiguous, conflict or intent")
SETTLE_SAYS = "the item rewritten, as YAML: every field it keeps, its id and type unchanged"

QUESTION_SYSTEM = """You read a fabula: a careful reading of a source, item by item. Your work is to find what only \
the person who made the source, or someone who knows that work well, can say, and to write it down as questions for \
them. They will be asked later, one at a time; you are not talking to them now.

Each question:
- asks one thing, in one plain sentence that ends with a question mark;
- is about one item below, named by its id, or one field of it, written <id>#<field>;
- is in no one's voice: never "I", "we" or "our", never praise, never a guess dressed as a question, never leading \
("Isn't it true that ..."); it may say "you" to the person asked;
- is asked only where the fabula is unsure (a reading is a guess), ambiguous (two readings stand, and either might be \
meant), in conflict (two items disagree), or silent on intent (why something was done, whether it was meant);
- is never one the source or the fabula already answers, and never one in the list of what is already asked.

Be exhaustive and quick: every place here that needs a person, and nothing else. No questions at all is a good answer \
when nothing here needs one.

{flavour}

Answer in YAML and nothing else:
questions:
  - about: <an id from the items, or <id>#<field>>
    asks: <the question>
    why: <unsure | ambiguous | conflict | intent>
    kind: <text | choice | yes-no | number | date | ref | span>
    options: [<two to six short choices>]   # only when kind is choice
    hint: <one short line to show under it>  # optional

kind is the shape of the answer: yes-no for a question answered yes or no, choice when the possible answers can be \
listed, span when the answer is a place in the source, ref when it is one of the items, text otherwise."""

FLAVOURS = {
    "fabulap": """This is a poem's fabula. Ask about:
- who speaks the poem, and whom it addresses, where the fabula guesses; whether the one addressed is listening;
- the occasion: what set the poem going, or whom it was written for, when nothing in it says;
- each image and device: whether it stands for something beyond itself, and what;
- each ambiguity: whether both readings are meant, or one should win;
- the form's choices: where the metre breaks, whether on purpose; why the lines break where they do; why this stanza \
shape, this rhyme or its absence;
- a word that may be used in an old, regional or private sense.""",
    "fabulac": """This is a program's fabula. Ask about:
- why a decision was made, and what else was tried and dropped;
- whether a behaviour is intended, or an accident that users now rely on;
- whom it is for, and what they already know;
- what it must never do, whatever a user asks;
- what an interface should do with input it does not expect;
- whether a setting is meant to be changed by the people who use it.""",
    "fabulan": """This is a prose text's fabula. Ask about:
- what a claim rests on, when the text does not say;
- who is meant by a group, a "you" or a "they";
- what the text assumes and does not state;
- a term used in a sense of the author's own;
- what prompted the text, and for whom it was written, when nothing in it says;
- a claim stated more weakly or more strongly than its author may stand behind.""",
}

SETTLE_SYSTEM = """You read one item of a fabula again, in the light of what the person who made the source said \
about it. Their answer is the authority: change the item so that it agrees with the answer, and change nothing the \
answer does not touch. Keep the item's id and type. Add no name, claim or reason that is not in the answer or already \
in the item. When the answer says a reading was not meant, or a behaviour is not intended, the item says so, plainly.

Answer in YAML and nothing else: the item rewritten, every field it keeps, as
item:
  id: <its id>
  type: <its type>
  ..."""


def _get(inputs: dict, name: str) -> str:
    pair = (inputs or {}).get(name)
    v = pair[0] if isinstance(pair, (tuple, list)) else pair
    return v.text() if isinstance(v, Value) else str(v if v is not None else "")


def _question_messages(flavour_key: str):
    def build(contract: dict, inputs: dict) -> list[dict] | None:
        if not (inputs or {}).get("items"):
            return None
        system = QUESTION_SYSTEM.replace("{flavour}", FLAVOURS[flavour_key])
        user = f"The fabula: {_get(inputs, 'volume')} ({_get(inputs, 'flavour')}).\n\nThe items:\n{_get(inputs, 'items')}"
        passage = _get(inputs, "passage")
        if passage:
            user += f"\n\nThe source's lines they read:\n{passage}"
        user += f"\n\nAlready asked; do not ask these again:\n{_get(inputs, 'asked')}\n\nWrite the questions."
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]
    build.__name__ = f"question_{flavour_key}_messages"
    return build


question_prose_messages = _question_messages("fabulan")
question_verse_messages = _question_messages("fabulap")
question_code_messages = _question_messages("fabulac")


def question_messages(contract: dict, inputs: dict) -> list[dict] | None:
    """The request `question` makes of the model, one prompt per flavour: verse, code, and prose for every other."""
    fl = _get(inputs, "flavour")
    build = {"fabulap": question_verse_messages, "fabulac": question_code_messages}.get(fl, question_prose_messages)
    return build(contract, inputs)


def settle_messages(contract: dict, inputs: dict) -> list[dict] | None:
    """The request `settle` makes of the model: one item, read again in the light of an answer."""
    if not (inputs or {}).get("item"):
        return None
    user = (f"The item:\n{_get(inputs, 'item')}\n\nThe question put to the person: {_get(inputs, 'asks')}\n"
            f"What they said, in their words: {_get(inputs, 'says')}\n")
    value = _get(inputs, "value")
    if value and value != _get(inputs, "says"):
        user += f"The answer as written down: {value}\n"
    user += f"Why the item must be read again: {_get(inputs, 'because')}\n\nRewrite the item."
    return [{"role": "system", "content": SETTLE_SYSTEM}, {"role": "user", "content": user}]


prompt_for("question")(question_messages)
prompt_for("settle")(settle_messages)

#: The prompt builders this module carries, by move: the host reads them and puts them in front of its own.
PROMPTS = {"question": question_messages, "settle": settle_messages}


# ---------------------------------------------------------------------------
# The checks: addressed, no-duplicate, only-the-asked (THYM 7.3)
# ---------------------------------------------------------------------------

def _volume_of(inputs: dict, *, prefer: tuple = ("in",)) -> Value | None:
    """The volume a check compares with: the `in` modifier, else the first fabula or volume input that is not an
    answers volume."""
    for k in prefer:
        v = inputs.get(k)
        if isinstance(v, Value) and v.type in ("fabula", "volume"):
            return v
    for _k, v in inputs.items():
        if isinstance(v, Value) and v.type in ("fabula", "volume") and not _is_answers(v):
            return v
    return None


def _is_answers(v: Value) -> bool:
    """An answers volume: its question entries carry no `type` (THYM 22.2)."""
    _cat, items = _doc(v)
    entries = [it for it in items if not str(it.get("id", "")).startswith("D:session/")]
    return bool(entries) and all("type" not in it and "answers" in it for it in entries)


def _manifest(v: Value) -> Any:
    p = v.payload
    if isinstance(p, mc.Volume):
        return p.manifest
    cat, _items = _doc(v)
    try:
        vol = mc.load_volume_text(mc.dump(plain({**cat, "nodes": []})), filename=_filename(v, "volume"))
    except Exception:  # noqa: BLE001 - a volume the reader refuses has no manifest to read addresses with
        return None
    return vol.manifest if vol.refused is None else None


def _span_why(span: dict) -> str | None:
    if "lines" in span:
        m = _LINES.match(str(span["lines"]))
        if not m or int(m.group(1)) < 1 or int(m.group(2) or m.group(1)) < int(m.group(1)):
            return f"lines {span['lines']!r} is not a line or a range of lines"
        return None
    if "start" in span and "end" in span:
        return None if all(isinstance(span[k], str) and span[k].strip() for k in ("start", "end")) else \
            "a quoted span gives its start and end words"
    return "a span names lines, or its start and end words"


def about_why(about: Any, ids: set[str], manifest: Any) -> str | None:
    """Why a question's `about` names nothing in the volume; None when it resolves (an item, `<item>#<field>`, a span
    of the source, a module or a kind the format declares)."""
    if isinstance(about, dict):
        return _span_why(about)
    if not isinstance(about, str) or not about.strip():
        return "it is about nothing"
    base, sep, fpath = about.partition("#")
    if sep and not _FIELD.match(fpath):
        return f"{fpath!r} is not a field path"
    if ":" not in base or "/" not in base:
        if manifest is None:
            return None
        mod, _, kind = base.partition(":")
        if mod not in manifest.modules():
            return f"{about} is not a module this format declares"
        if kind and kind not in manifest.kinds(mod):
            return f"{about} is not a kind this format declares"
        return None
    return None if _bare(base) in ids else f"{about} names nothing in this volume"


def _ids(items: list[dict]) -> set[str]:
    return {_bare(it["id"]) for it in items if isinstance(it.get("id"), str)}


def _question_rows(output: Value) -> list[dict]:
    if output.type == "list":
        return [m.mapping() for m in output.payload or [] if isinstance(m, Value) and isinstance(m.mapping(), dict)]
    return [it for it in _doc(output)[1] if _is_question(it)]


@check("addressed")
def _addressed(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every question's `about` resolves, and every answer names a session of the volume, on a question that was open
    or answered before it, in the shape its state says (THYM 7.3)."""
    vol = output if output.type in ("fabula", "volume") else _volume_of(inputs)
    if vol is None:
        return False, "there is no volume the questions are about"
    _cat, items = _doc(vol)
    ids, manifest = _ids(items), _manifest(vol)
    for q in _question_rows(output):
        if q.get("settled") or q.get("state") in ENDED:
            continue
        why = about_why(q.get("about"), ids, manifest)
        if why:
            return False, f"{q.get('id')}: {why}"
    if output.type == "list":
        return True, ""
    sessions = {_bare(it["id"]) for it in items if str(it.get("id", "")).startswith("D:session/")}
    before = _volume_of(inputs)
    was = {q.get("id"): q for q in (_doc(before)[1] if before is not None and before is not output else [])
           if _is_question(q)}
    for q in _question_rows(output):
        answers = q.get("answers") or []
        for a in answers:
            s = a.get("session") if isinstance(a, dict) else None
            if isinstance(s, str) and s.startswith("D:session/") and _bare(s) not in sessions:
                return False, f"{q.get('id')}: its answer names {s}, which is no session of this volume"
        old = was.get(q.get("id"))
        if old is not None and len(answers) > len(old.get("answers") or []) and old.get("state") in ENDED:
            return False, f"{q.get('id')} was {old.get('state')}, and an answer was recorded on it"
        state = q.get("state")
        if state in ANSWERED and answers:
            last = answers[-1] if isinstance(answers[-1], dict) else {}
            if state == "answered" and (last.get("declined") is True or last.get("value") is None):
                return False, f"{q.get('id')} is answered, and its last answer gives no value"
            if state == "unknown" and (last.get("declined") is True or last.get("value") is not None):
                return False, f"{q.get('id')} is unknown, and its last answer is not the person's \"I don't know\""
            if state == "declined" and last.get("declined") is not True:
                return False, f"{q.get('id')} is declined, and its last answer is not a refusal"
        elif state in ANSWERED:
            return False, f"{q.get('id')} is {state}, with no answer to show for it"
    return True, ""


@check("no-duplicate")
def _no_duplicate(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """No two open questions about one address ask the same thing, and no new one repeats a question already in the
    volume (THYM 7.3)."""
    rows = _question_rows(output)
    before = _volume_of(inputs) if output.type == "list" else None
    old = [q for q in (_doc(before)[1] if before is not None else []) if _is_question(q)
           and q.get("state") not in ENDED]
    seen: dict[tuple, str] = {}
    froms: dict[tuple, str] = {}
    for q in old:
        seen.setdefault((_about_key(q.get("about")), _norm(q.get("asks"))), str(q.get("id")))
        froms.setdefault(((q.get("raised") or {}).get("from"), _about_key(q.get("about"))), str(q.get("id")))
    for q in rows:
        if q.get("state", "open") != "open" and output.type != "list":
            continue
        key = (_about_key(q.get("about")), _norm(q.get("asks")))
        if key in seen and seen[key] != q.get("id"):
            return False, f"{q.get('id')} asks of {key[0]} what {seen[key]} already asks"
        seen[key] = str(q.get("id"))
        if output.type == "list":
            fk = ((q.get("raised") or {}).get("from"), key[0])
            if fk in froms and froms[fk] != q.get("id"):
                return False, f"{q.get('id')} repeats {froms[fk]}: the same {fk[0]} about {fk[1]}"
            froms[fk] = str(q.get("id"))
    return True, ""


def _paths(a: Any, b: Any, path: str = "") -> list[str]:
    """The field paths where two values differ (a mapping key by `.`, a list position by `[n]`)."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in list(a) + [k for k in b if k not in a]:
            sub = f"{path}.{k}" if path else str(k)
            if k not in a or k not in b:
                out.append(sub)
            else:
                out += _paths(a[k], b[k], sub)
        return out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += _paths(x, y, f"{path}[{i}]")
        return out
    return [] if plain(a) == plain(b) else [path]


def _under(path: str, allowed: str) -> bool:
    return path == allowed or path.startswith(allowed + ".") or path.startswith(allowed + "[") or \
        allowed.startswith(path + ".") or allowed.startswith(path + "[")


def only_the_asked(before: tuple[dict, list[dict]], after: tuple[dict, list[dict]]) -> list[str]:
    """What differs from `before` that no answered question of `after` accounts for (THYM 7.3, `only-the-asked`): an
    item of D may change; an item an answered, unknown or declined question is about may change at its `about` field,
    at a field the question's `settled.wrote` names, and in its `provenance`, `withheld` and `pending`; an item is new
    or gone only where a `settled.wrote` names it; the catalog changes only in `derived.runs`, which only grows. `made`
    is aside (the runtime writes it). Empty when the contract holds."""
    bcat, bitems = before
    acat, aitems = after
    out: list[str] = []
    for k in [k for k in bcat if k != "nodes"] + [k for k in acat if k not in bcat and k != "nodes"]:
        if k == "derived" and isinstance(bcat.get(k), dict) and isinstance(acat.get(k), dict):
            b, a = dict(bcat[k]), dict(acat[k])
            br, ar = b.pop("runs", []) or [], a.pop("runs", []) or []
            if plain(a) != plain(b):
                out.append("derived changed beyond its runs")
            elif not (isinstance(ar, list) and plain(ar[:len(br)]) == plain(br)):
                out.append("derived.runs lost or changed a run it had")
        elif plain(bcat.get(k)) != plain(acat.get(k)):
            out.append(f"the catalog's {k} changed")
    allowed: dict[str, list[str]] = {}
    whole: set[str] = set()
    for q in aitems:
        if not _is_question(q) or q.get("state") not in ANSWERED:
            continue
        about = q.get("about")
        if isinstance(about, str):
            base, sep, fpath = about.partition("#")
            allowed.setdefault(_bare(base), []).extend([fpath] if sep else [])
        st = q.get("settled") if isinstance(q.get("settled"), dict) else {}
        for addr in st.get("wrote") or []:
            if not isinstance(addr, str):
                continue
            base, sep, fpath = addr.partition("#")
            allowed.setdefault(_bare(base), []).extend([fpath] if sep else [])
            if not sep:
                whole.add(_bare(base))

    def strip(it: dict) -> dict:
        return {k: v for k, v in it.items() if k != "made"}

    b = {_bare(it["id"]): strip(it) for it in bitems if isinstance(it.get("id"), str)}
    a = {_bare(it["id"]): strip(it) for it in aitems if isinstance(it.get("id"), str)}
    for iid in list(b) + [i for i in a if i not in b]:
        if iid.startswith("D:"):
            continue
        if iid not in a or iid not in b:
            if iid not in whole:
                out.append(f"{iid} is {'gone' if iid not in a else 'new'}, and no answer wrote it")
            continue
        for p in _paths(b[iid], a[iid]):
            root = re.split(r"[.\[]", p, maxsplit=1)[0]
            if iid in allowed and (root in ALWAYS_WRITABLE or iid in whole
                                   or any(_under(p, f) for f in allowed[iid] if f)):
                continue
            out.append(f"{iid}#{p} changed, and no question is about it")
    return out


@check("only-the-asked")
def _only_the_asked(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Only the questions' answers, states and `settled`, the new session, and the fields answered questions are
    about (with their provenance) differ from the input (THYM 7.3)."""
    before = _volume_of(inputs)
    if before is None:
        return False, "there is no volume to compare with"
    problems = only_the_asked(_doc(before), _doc(output))
    if problems:
        more = f" (and {len(problems) - 2} more)" if len(problems) > 2 else ""
        return False, "; ".join(problems[:2]) + more
    return True, ""


__all__ = ["FLAVOURS", "FUNCTIONS", "PROMPTS", "about_why", "bank", "direct", "only_the_asked", "proposal_problem",
           "question", "question_code_messages", "question_messages", "question_prose_messages",
           "question_verse_messages", "record", "settle", "settle_messages"]
