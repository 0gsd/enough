"""The moves `emf/1` declares: `derive`, `entail`, `atem`, `expand` (docs/THYM.md 6.3, 7.3, 19; MacroCOSM 18.3.5, 18.4).
`tell`, `entail`'s earlier spelling, reaches `entail`: the compiler reads it as `entail` (THYM 6.3).

All four transcognize, so each returns a `Request` and the runtime asks the coprocessor under the move's contract;
each has the rules-mode stand-in its declaration names, except `expand`, which has none (THYM.md 19).

- `derive` reads a text into its fabula through `canon_derive`, as Canon does: chunked, every passage read, normalized,
  repaired once, merged, its terms grounded in FEED over the lexicon floor. The passages are read through an
  `EngineAdapter` (one recorded candidate per call, `candidates/<node>-<k>.1.cosm`); the last call, the whole text's
  atem, is the move's own `Request`, so the runtime owns its attempts and the node's engine is the model's. When the
  fabula leaves a claim-bearing sentence uncovered, the narrow repair reads just those lines once more, as one
  passage. The fabula records its sentence-to-item map in `derived.covers` (the same computation `coverage` runs).
  Its scaffold,
  `rules-twin`, is Canon's rules-mode twin (`derived.mode: rules`, completeness `full`, terms and entities only).
- `entail` makes a short of a fabula (or of one item, or of an EMF volume) in an order, `told` or `weight`, and in a
  morph when one is given: the model is shown the fabula's items with their ids and answers sentence by sentence with the ids each
  sentence says; the short ends with MacroCOSM 18.4.4's footer (`short_footer`). Its scaffold, `outline`, is Canon's
  rules-mode short. A morph's scales are asked for; `scales-met` is not in `entail`'s contract.
- `atem` reduces a text, a short, a fabula or an item to its line, focus, push and pull, through Canon's atem prompt;
  of a fabula it also names the items it centres on (`of`). Its scaffold, `first-sentence`, is `rules_atem`.
- `expand` opens an atem out into a short of about `to N words`, entailed by the fabula `with` it.

The checks an entailment carries live here too: `coverage`, `no-invention`, `stance-kept`, `footer`, `span-resolves`,
`stance-closed`, `terms-grounded`, `atem-shape`, `span-inside`.

Standalone: the standard library, PyYAML and `enough.macrocosm`.
"""
from __future__ import annotations

import copy
import re
from typing import Any

from enough import macrocosm as mc
from enough.thym.checks import body, check
from enough.thym.moves import (LADDER, RANK, SENTENCES_SAYS, EngineAdapter, MoveError, answer_mapping, compose,
                               cover_map, engine, fabula_doc, fabula_for, first_input, fold, item_kind,
                               messages_value, model_of, names_and_numbers, plain_text, read_sentences,
                               segment,
                               short_value, source_name, span_lines, entailment_of, entailment_stance, text_blob, utc_day,
                               words_in)
from enough.thym.registry import Amount, Request, implements
from enough.thym.values import Value

#: What an entailing move asks back (THYM.md 12.2): its sentences with the ids each one says. `stamp: engine` asks the
#: host's coprocessor to write the model's id into the answer, so the footer can name it and a replay names it again.
SENTENCES_SCHEMA = {"format": "yaml", "stamp": "engine", "says": SENTENCES_SAYS}
ATEM_SCHEMA = {"format": "yaml", "stamp": "engine",
               "says": "a YAML mapping: line, focus, push, pull, stance_profile, and of (the ids it centres on)"}
DERIVE_SCHEMA = {"format": "text", "says": "the whole text's atem, as Canon's derivation asks for it"}
_KIND_RANK = {"term": 0, **{k: 1 for k in ("person", "org", "place", "work", "thing")}, "concept": 2, "claim": 3,
              "event": 4}


# ---------------------------------------------------------------------------
# Shared by the entailing moves
# ---------------------------------------------------------------------------

def as_fabula(x: Value) -> Value:
    """The fabula a short is entailed from: a fabula as it is; an item as a fabula of one; an EMF volume read as one."""
    if x.type == "fabula":
        return x
    cat, items = fabula_doc(x)
    if not items:
        raise MoveError(f"a {x.type} with no items entails nothing")
    return Value("fabula", cat if isinstance(x.payload, dict) and "nodes" in x.payload else
                 {**cat, "nodes": items}, path=x.path, made=x.made, state=x.state)


def default_order(cat: dict, items: list[dict]) -> str:
    """`told` when the items carry spans (the author's order is known), `weight` otherwise (MacroCOSM 18.4.4)."""
    return "told" if any(span_lines(it) for it in items) else "weight"


def ordered(items: list[dict], order: str) -> list[dict]:
    """The items in an order: `told`, by span (first line, last line, then words, names, ideas, claims, events), the
    unplaced last; `weight`, the claims by salience, then the events, the ideas, the names and the words. The items of
    a volume that is not a fabula (a holotype's offerings) come after, in the volume's order."""
    pos = {id(it): i for i, it in enumerate(items)}
    tellable = [it for it in items if item_kind(it) != "atem"]      # a pinned atem reduces; it is not material
    if order == "told":
        def key(it: dict) -> tuple:
            ab = span_lines(it) or (10 ** 9, 10 ** 9)
            return (ab[0], ab[1], _KIND_RANK.get(item_kind(it), 5), pos[id(it)])
        return sorted(tellable, key=key)
    sal = {"critical": 0, "high": 1, "normal": 2, "low": 3}
    kinds = {"claim": 0, "event": 1, "concept": 2, "term": 4}

    def wkey(it: dict) -> tuple:
        k = item_kind(it)
        return (kinds.get(k, 3), sal.get(str(it.get("salience") or "normal"), 2), pos[id(it)])
    return sorted(tellable, key=wkey)


def cited_outline(cat: dict, items: list[dict], order: str) -> str:
    """The fabula as the model is shown it: its name and atem line, then one line per item in the order, each with
    its id, kind, stance and salience, so that every sentence it writes can cite what it says."""
    out = [f"# {cat.get('name') or 'untitled'}"]
    atem = cat.get("atem") if isinstance(cat.get("atem"), dict) else {}
    if isinstance(atem.get("line"), str) and atem["line"].strip():
        out.append(f"Atem: {fold(atem['line'])}")
    out.append("")
    for it in ordered(items, order):
        k = item_kind(it)
        tags = [k]
        if it.get("stance"):
            tags.append(f"stance {it['stance']}")
        if it.get("salience") and k == "claim":
            tags.append(f"salience {it['salience']}")
        said = fold(it.get("summary") or it.get("sense") or it.get("name") or "")
        name = fold(it.get("name") or "")
        out.append(f"- [{it.get('id')}] ({', '.join(tags)}) {name}: {said}" if name and name.lower() not in
                   said.lower() else f"- [{it.get('id')}] ({', '.join(tags)}) {said}")
    return "\n".join(out) + "\n"


def footer_line(ctx: Any, cat: dict, fab: Value, order: str, model: str | None) -> str:
    """MacroCOSM 18.4.4's footer, by Canon's `short_footer`: what the short is of, its order, the day, the model."""
    src = cat.get("source") if isinstance(cat.get("source"), dict) else None
    standalone = not (src and src.get("path"))
    return engine(ctx, "canon").short_footer(text_name=source_name(cat, fab), standalone=standalone, order=order,
                                             day=utc_day(ctx), model=model, mode="model")


def entailment(ctx: Any, out: Any, fab: Value, *, footer: Any, order: str | None, morph: str | None = None,
               front: dict | None = None, one_paragraph: bool = False, **extra: Any) -> Value:
    """A model's sentences as a short: composed, footed, and carrying its fabula and each sentence's citations.
    `one_paragraph` folds the model's paragraph marks away (the null short, THYM.md 13.1)."""
    paras, covers = read_sentences(out)
    if one_paragraph:
        paras = [[s for p in paras for s in p]]
    model = model_of(answer_mapping(out))
    foot = footer(model) if callable(footer) else footer
    text = compose(paras, foot, front)
    sents = [s for p in paras for s in p]
    return short_value(text, fabula=fab, sentences=sents, covers=covers, order=order, morph=morph, **extra)


def morph_name(m: Value | None) -> str | None:
    if m is None or not isinstance(m, Value) or m.is_nothing:
        return None
    from enough.thym.moves.morph import morph_scales
    return morph_scales(m)[0]


# ---------------------------------------------------------------------------
# derive
# ---------------------------------------------------------------------------

def _text_facts(story: Value) -> tuple[str, str, int]:
    name = story.path.name if story.path is not None else "text.md"
    return name, story.sha256, len(story.bytes())


def _with_covers(cat: dict, story: Value) -> dict:
    fab = Value("fabula", cat)
    cat.setdefault("derived", {})["covers"] = cover_map(fab, story).record()
    return cat


@implements("derive")
def derive(ctx: Any, story: Value, **mods: Any) -> Request:
    """A text decompiled into its fabula (THYM.md 6.3), by Canon's derivation over the coprocessor. A text read `as
    code` and a folder folded are the fabulac's (`code.py`, THYM 20.6)."""
    branch = _code.derive_branch(ctx, story, mods)
    if branch is None:
        branch = _verse.derive_branch(ctx, story, mods)     # derive poem as verse with f (THYM 20.9)
    if branch is not None:
        return branch
    canon = engine(ctx, "canon")
    feed = ctx.engines.get("feed")
    text = story.text()
    name, sha, size = _text_facts(story)
    adapter = EngineAdapter(ctx, "derive")
    verse = _verse_args(ctx, mods)
    got = canon.derive_passages(text, source_name=name, complete=adapter, lookup=feed, **verse)

    def parse(out: Any) -> Value:
        reply = out if isinstance(out, str) else mc.dump(out) if isinstance(out, dict) else str(out or "")
        unread = _atem_unread(canon.read_atem(reply))
        if unread:
            # checkpoint A, lesson 4: with a model on, an atem that cannot be read fails `schema` and is asked again;
            # it never becomes four open questions under green checks
            raise ValueError(f"the whole text's atem could not be read ({unread}); answer with line, focus, push and "
                             "pull, each on its own line")
        model = adapter.model or got.get("model") or model_of(out if isinstance(out, dict) else {})
        cat = canon.derive_finish(text, nodes=copy.deepcopy(got["nodes"]), atem_reply=reply, source_name=name,
                                  sha256=sha, size=size, model=model, chunks=got["chunks"], dropped=got["dropped"],
                                  now=ctx.now, **{k: v for k, v in verse.items() if k == "flavour"})
        return Value("fabula", _with_covers(cat, story))

    def repair(value: Value, failed: list) -> Value | None:
        read = None
        if "coverage" in {f.get("name") for f in failed}:
            read = _read_gaps(ctx, canon, value, story, adapter, name, verse.get("flavour"))
            if read is not None:
                got["nodes"] = list(fabula_doc(read)[1])                # a later attempt keeps what was read
        return _repair_fabula(ctx, read or value, failed, story) or read

    return Request(contract={"schema": DERIVE_SCHEMA, "repair": ["drop-unresolved-spans", "normalise-stance",
                                                                 "ground-terms"]},
                   inputs={"messages": messages_value(got["messages"])}, parse=parse, repair=repair)


def _verse_args(ctx: Any, mods: dict) -> dict:
    """What the engine is told of a `derive … as verse` (THYM 20.5): the flavour `fabulap` and the pronunciations
    its verse rules read (the `pron` engine, recorded like FEED's). `as prose`, or no `as`, is a fabulan, told as
    before (nothing added)."""
    if mods.get("as") != "verse":
        return {}
    return {"flavour": "fabulap", "pron": ctx.engines.get("pron")}


def _atem_unread(atem: Any) -> str | None:
    """Why a model's whole-text atem is unreadable, or None: the answer gave no line (Canon's reader then writes the
    line as an open question), or it could not be read at all."""
    if not isinstance(atem, dict):
        return "the answer is not a mapping"
    line = atem.get("line")
    if isinstance(line, str) and line.strip():
        return None
    if mc.is_pending(line):
        return str(line.get("pending") or "no line")
    return "no line"


def _read_gaps(ctx: Any, canon: Any, value: Value, story: Value, adapter: EngineAdapter, name: str,
               flavour: str | None = None) -> Value | None:
    """`coverage`'s narrow repair: the lines no item covers, read once more as one passage through the coprocessor
    (one more recorded candidate), the items found merged in. None when every sentence is covered already."""
    cm = cover_map(value, story)
    spans = [ln for _s, ln, ids in cm.rows if not ids and ln]
    if not spans:
        return None
    cat, items = fabula_doc(value)
    nodes = canon.derive_gaps(story.text(), nodes=copy.deepcopy(items), spans=spans, source_name=name,
                              complete=adapter, lookup=ctx.engines.get("feed"),
                              **({"flavour": flavour} if flavour else {}))
    return Value("fabula", _with_covers({**copy.deepcopy(cat), "nodes": nodes}, story))


def _repair_fabula(ctx: Any, value: Value, failed: list, story: Value) -> Value | None:
    """The narrow repairs THYM.md 12.2 allows a fabula: drop an item whose span does not resolve (its references
    become open questions), match a stance word to the closed list (a claim whose word matches none is dropped), and
    write `{pending: "not in FEED"}` on a term FEED does not hold. None when nothing failed that these can fix."""
    names = {f.get("name") for f in failed}
    if not names & {"span-resolves", "stance-closed", "terms-grounded"}:
        return None
    cat, items = fabula_doc(value)
    cat = copy.deepcopy(cat)
    items = [it for it in cat.get("nodes") or [] if isinstance(it, dict)]
    drop: set[str] = set()
    if "span-resolves" in names:
        n = len(story.text().replace("\r\n", "\n").split("\n"))
        drop |= {it["id"] for it in items if _span_problem(it, story.text(), n)}
    if "stance-closed" in names:
        for it in items:
            if item_kind(it) == "claim" and it.get("stance") not in LADDER:
                hit = _closest(it.get("stance"))
                if hit:
                    it["stance"] = hit
                else:
                    drop.add(it["id"])
    if "terms-grounded" in names:
        for it in items:
            if item_kind(it) == "term" and _term_problem(ctx, it):
                it["feed"] = {"pending": "not in FEED"}
    if drop:
        items = [it for it in items if it.get("id") not in drop]
        for it in items:
            _unlink(it, drop)
    cat["nodes"] = items
    return Value("fabula", _with_covers(cat, story))


def _closest(word: Any) -> str | None:
    if not isinstance(word, str) or not word.strip():
        return None
    w = word.strip().lower()
    hits = [s for s in LADDER if s.startswith(w[:5]) or w.startswith(s[:5])]
    return hits[0] if len(hits) == 1 else None


def _unlink(it: dict, gone: set[str]) -> None:
    if isinstance(it.get("links"), list):
        it["links"] = [ln for ln in it["links"] if not (isinstance(ln, dict) and ln.get("to") in gone)]
        if not it["links"]:
            it.pop("links")
    for k, v in list(it.items()):
        if isinstance(v, str) and v in gone:
            it[k] = {"pending": f"{k}: {v} was dropped; its span did not resolve"}
        elif isinstance(v, dict) and k != "span":
            for r, x in list(v.items()):
                if isinstance(x, str) and x in gone:
                    v[r] = {"pending": f"{r}: {x} was dropped; its span did not resolve"}


@implements("derive.scaffold")
@implements("rules-twin")
def derive_rules(ctx: Any, story: Value, **mods: Any) -> Value:
    """`rules-twin`: Canon's rules-mode twin, as Canon makes one without a model (MacroCOSM 18.4.3): the words the
    text leans on, grounded in FEED, and the names it uses, each with the line of its first use; no claims. A text
    read `as code` takes `file-outline`, and a folder has no scaffold (`code.py`)."""
    branch = _code.derive_scaffold_branch(ctx, story, mods)
    if branch is None:
        branch = _verse.derive_branch(ctx, story, mods, rules=True)
    if branch is not None:
        return branch
    name, sha, size = _text_facts(story)
    cat = engine(ctx, "canon").derive_rules(story.text(), source_name=name, sha256=sha, size=size,
                                            lookup=ctx.engines.get("feed"), now=ctx.now, **_verse_args(ctx, mods))
    return Value("fabula", cat)


# ---------------------------------------------------------------------------
# entail
# ---------------------------------------------------------------------------

@implements("entail")
def entail(ctx: Any, x: Value, **mods: Any) -> Request:
    """An entailment of a fabula, in an order, in a morph (THYM.md 6.3), cited sentence by sentence. `as code` and a
    catem's depths are the fabulac's (`code.py`, THYM 20.7)."""
    branch = _code.entail_branch(ctx, x, mods)
    if branch is not None:
        return branch
    fab = as_fabula(x)
    cat, items = fabula_doc(fab)
    order = mods.get("as") or mods.get("by") or default_order(cat, items)
    if order not in ("told", "weight"):
        raise MoveError(f"entail takes the order told or weight, not {order}")
    m = mods.get("with")
    inputs: dict = {"fabula": fab, "outline": Value("string", cited_outline(cat, items, order)),
                    "order": Value("word", order)}
    if isinstance(m, Value) and not m.is_nothing:
        from enough.thym.moves.morph import asks_for
        inputs["morph"] = m
        inputs["asks"] = Value("string", asks_for(m))

    def parse(out: Any) -> Value:
        return entailment(ctx, out, fab, footer=lambda model: footer_line(ctx, cat, fab, order, model), order=order,
                          morph=morph_name(m))
    return Request(contract={"schema": SENTENCES_SCHEMA, "repair": []}, inputs=inputs, parse=parse)


@implements("entail.scaffold")
@implements("outline")
def entail_outline(ctx: Any, x: Value, **mods: Any) -> Value:
    """`outline`: Canon's rules-mode short, the ordered outline said in the items' own sentences with the footer that
    says "by rules, without a model". A morph cannot be kept by rules, and is not. A catem's depth takes
    `uses-outline`, and `as code` has no scaffold (`code.py`)."""
    branch = _code.entail_scaffold_branch(ctx, x, mods)
    if branch is not None:
        return branch
    fab = as_fabula(x)
    cat, items = fabula_doc(fab)
    order = mods.get("as") or mods.get("by") or default_order(cat, items)
    md = engine(ctx, "canon").compile_rules({**cat, "nodes": items}, order=order, source_name=source_name(cat, fab),
                                            now=ctx.now)
    return short_value(md, fabula=fab, order=order)


# ---------------------------------------------------------------------------
# atem
# ---------------------------------------------------------------------------

def _atem_source(x: Value) -> tuple[str, Value | None]:
    if x.type in ("fabula", "item"):
        fab = as_fabula(x)
        cat, items = fabula_doc(fab)
        return cited_outline(cat, items, default_order(cat, items)), fab
    t = entailment_of(x)
    text = body(x.text()) if x.type == "short" else x.text()
    return text, (t.get("fabula") if t else None)


@implements("atem")
def atem(ctx: Any, x: Value, **_: Any) -> Request:
    """The atem of a text, a short, a fabula or an item (MacroCOSM 18.3.5): line, focus, push and pull."""
    text, fab = _atem_source(x)
    inputs: dict = {"text": Value("string", text)}
    if fab is not None:
        inputs["fabula"] = fab

    def parse(out: Any) -> Value:
        data = answer_mapping(out)
        a: dict = {}
        for part in ("line", "focus", "push", "pull"):
            v = data.get(part)
            a[part] = fold(v) if isinstance(v, str) and v.strip() else {"pending": f"the model gave no {part}"}
        prof = data.get("stance_profile") or data.get("stances")
        if isinstance(prof, dict):
            a["stance_profile"] = {s: int(prof[s]) for s in LADDER[::-1] if isinstance(prof.get(s), int)
                                   and not isinstance(prof.get(s), bool) and prof[s] >= 0}
        of = data.get("of")
        if fab is not None and of:
            a["of"] = [fold(i) for i in (of if isinstance(of, list) else [of]) if fold(i)]
        a["source"] = {"type": x.type, "sha256": x.sha256}
        return Value("atem", a)

    def repair(value: Value, failed: list) -> Value | None:
        a = dict(value.mapping() or {})
        if fab is None or "span-resolves" not in {f.get("name") for f in failed} or not a.get("of"):
            return None
        ids = {it.get("id") for it in fabula_doc(fab)[1]}
        a["of"] = [i for i in a["of"] if i in ids]
        if not a["of"]:
            a.pop("of")
        return Value("atem", a)

    return Request(contract={"schema": ATEM_SCHEMA, "repair": ["drop-unknown-ids"]}, inputs=inputs, parse=parse,
                   repair=repair)


@implements("atem.scaffold")
@implements("first-sentence")
def atem_first_sentence(ctx: Any, x: Value, **_: Any) -> Value:
    """`first-sentence`: Canon's scaffold atem (`rules_atem`), the first sentence as the line, the first two as the
    focus, push and pull open questions. Of a fabula, the first sentence of its told outline: its own atem line."""
    if x.type in ("fabula", "item"):
        fab = as_fabula(x)
        cat, items = fabula_doc(fab)
        _title, lines = engine(ctx, "canon").outline({**cat, "nodes": items}, order=default_order(cat, items))
        text = "\n".join(ln for ln in lines if not ln.startswith("#"))
    else:
        text = body(x.text()) if x.type == "short" else x.text()
    a = dict(engine(ctx, "canon").rules_atem(text))
    a["source"] = {"type": x.type, "sha256": x.sha256}
    return Value("atem", a)


# ---------------------------------------------------------------------------
# expand
# ---------------------------------------------------------------------------

@implements("expand")
def expand(ctx: Any, a: Value, **mods: Any) -> Request:
    """An atem opened out into a short of about `to N words`, from the fabula `with` it (THYM.md 6.3)."""
    fab = mods.get("with")
    if not isinstance(fab, Value) or fab.type != "fabula":
        raise MoveError("expand needs the fabula the atem reduces: expand <atem> with <fabula> to N words")
    to = mods.get("to")
    n = to.n if isinstance(to, Amount) else 300
    cat, items = fabula_doc(fab)
    inputs = {"atem": a, "fabula": fab, "outline": Value("string", cited_outline(cat, items, "told")),
              "words": Value("number", n)}

    def foot(model: str | None) -> str:
        who = f"by {model or 'a model'}"
        src = cat.get("source") if isinstance(cat.get("source"), dict) else None
        tail = "compiled from its fabula" if src and src.get("path") else "a standalone fabula, compiled"
        return f"*a short of {source_name(cat, fab)}, expanded from its atem to about {n} words, {tail} on " \
               f"{utc_day(ctx)} {who}*"

    def parse(out: Any) -> Value:
        return entailment(ctx, out, fab, footer=foot, order="told", atem=a)
    return Request(contract={"schema": SENTENCES_SCHEMA, "repair": []}, inputs=inputs, parse=parse,
                   budget={"output_words": n})


# ---------------------------------------------------------------------------
# The checks an entailment carries (THYM.md 7.3)
# ---------------------------------------------------------------------------

def _pair(output: Value, inputs: dict) -> tuple[Value | None, Value | None]:
    """(fabula, what it covers) for `coverage`: derive gives a fabula of a text; an entailing move gives a short of a fabula;
    `assert f covers t` asks of `t` with `f` beside it."""
    if output.type == "fabula":
        return output, first_input(inputs, "text", "short")
    return fabula_for(output, inputs), output


@check("coverage")
def _coverage(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every claim-bearing sentence of an entailment traces to one or more items of its fabula (THYM.md 7.2 law 1, 7.3);
    as a condition, `f covers t`. The map (`cover_map`) is the one `derived.covers` records, and on success the
    verdict's why is the map itself, so the trace records it. A scaffold's output promises no coverage: rules cannot
    read claims, and say so."""
    if output.type == "fabula" and _code.flavour_of(fabula_doc(output)[0]) == "fabulac":
        return _code.code_coverage(output, inputs)          # a file read as code (THYM 20.6)
    fab, tel = _pair(output, inputs)
    if fab is None or tel is None:
        return False, "no fabula and text to lay over each other" if fab is None else "no text or short to cover"
    if fab.state == "pending" or tel.state == "pending":
        return True, "a scaffold makes no coverage promise: rules cannot read claims"
    cm = cover_map(fab, tel)
    if cm.unknown:
        s, bad = cm.unknown[0]
        return False, f"a sentence cites {', '.join(bad)}, which the fabula does not hold: {s[:80]}"
    if not cm.rows:
        return True, "the text has no claim-bearing sentence"
    if cm.missing:
        k = len(cm.missing)
        return False, (f"{k} claim-bearing sentence{'s' if k != 1 else ''} trace{'s' if k == 1 else ''} to no item of "
                       f"the fabula; the first: {cm.missing[0][:100]}")
    return True, cm.compact()


@check("no-invention")
def _no_invention(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """The entailment names no entity, claim or event its fabula lacks (THYM.md 7.3): every sentence cites at least one
    item, every cited id is an item of the fabula, and every name and number a sentence uses is one the fabula holds
    (in its items' names, summaries, roles or times)."""
    fab = fabula_for(output, inputs)
    if fab is None:
        return False, "no fabula to look the short up in"
    if output.state == "pending":
        return True, "a scaffold says the items' own sentences"
    t = entailment_of(output)
    if not t or t.get("covers") is None:
        return False, "the short carries no citations, sentence by sentence"
    cat, items = fabula_doc(fab)
    ids = {it.get("id") for it in items}
    blob = text_blob(cat, items)
    for i, (s, cites) in enumerate(zip(t.get("sentences") or [], t.get("covers") or []), 1):
        if not cites:
            return False, f"sentence {i} cites no item: {s[:80]}"
        bad = [c for c in cites if c not in ids]
        if bad:
            return False, f"sentence {i} cites {', '.join(bad)}, which the fabula does not hold"
        names, numbers = names_and_numbers(s)
        for w in names + numbers:
            if not re.search(rf"(?<![\w]){re.escape(w.lower())}(?![\w])", blob):
                what = "the number" if w.isdigit() else "the name"
                return False, f"sentence {i} says {what} {w}, which no item of the fabula holds: {s[:80]}"
    return True, ""


@check("stance-kept")
def _stance_kept(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """No sentence says a claim more strongly than its fabula holds it (THYM.md 7.2 law 3): a sentence is said at the
    weakest stance its words mark ("reportedly", "the author holds that", "it follows that", a hedge), or as
    `observed` when it asserts plainly, and that must sit at or below every cited claim's stance on the ladder
    `hearsay assumed opinion deduced observed axiom`."""
    fab = fabula_for(output, inputs)
    if fab is None:
        return False, "no fabula to read the claims' stances from"
    if output.state == "pending":
        return True, "a scaffold says each claim's stance in Canon's own stance words"
    _cat, items = fabula_doc(fab)
    stance = {it.get("id"): it.get("stance") for it in items if item_kind(it) == "claim"}
    t = entailment_of(output)
    if t and t.get("covers") is not None:
        rows = list(zip(t.get("sentences") or [], t.get("covers") or []))
    else:
        cm = cover_map(fab, output)
        rows = [(s, ids) for s, _ln, ids in cm.rows]
    # A claim said over several sentences is said at the weakest stance any of them marks: "Reportedly the Bramley
    # is the oldest tree; the records do not say when it was planted" keeps the claim at hearsay.
    said_by_claim: dict[str, tuple[int, str, str]] = {}
    for s, cites in rows:
        said = entailment_stance(s)
        for c in cites:
            best = said_by_claim.get(c)
            if best is None or RANK[said] < best[0]:
                said_by_claim[c] = (RANK[said], said, s)
    for c, (rank, said, s) in said_by_claim.items():
        held = stance.get(c)
        if held in RANK and rank > RANK[held]:
            return False, (f"{c} is {held} in the fabula and the short says it as {said}: {s[:80]} "
                           f"(say it with the stance's phrase: reportedly, it is assumed that, the author holds that)")
    return True, ""


# MacroCOSM OES 18.4.4: "compiled from its fabula" / "a standalone fabula"; a footer an earlier edition wrote ("from
# its EMF twin", "a standalone EMF") reads the same, so a short on disk or in a recorded run still holds.
_FOOTER = re.compile(r"^\*a short of .+?, (?:a standalone (?:fabula|EMF), )?(?:told as the author told it|told by weight), "
                     r"compiled (?:from its (?:fabula|EMF twin) )?on \d{4}-\d{2}-\d{2} by .+\*$")


@check("footer")
def _footer(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """A short ends with MacroCOSM 18.4.4's footer line: what it is a short of, in which order, when, and by which
    model or by rules (`*a short of notes.md, told as the author told it, compiled from its fabula on 2026-10-23 by
    g40-04*`; the earlier edition's "from its EMF twin" reads the same). A cshort's and a catem's footers are MacroCOSM 18.4.7's (`code.py`)."""
    if _code.is_code_entailment(output):
        why = _code.footer_problem(output, inputs, ctx)
        return (why is None), (why or "")
    lines = [ln.strip() for ln in output.text().replace("\r\n", "\n").split("\n") if ln.strip()]
    if not lines:
        return False, "the short is empty"
    if not _FOOTER.match(lines[-1]):
        return False, f"the last line is not a short's footer: {lines[-1][:80]}"
    return True, ""


def _span_problem(it: dict, text: str, n_lines: int) -> str | None:
    span = it.get("span")
    if not isinstance(span, dict):
        return None
    if span.get("lines") is not None:
        ab = span_lines(it)
        if ab is None:
            return f"its span's lines {span.get('lines')!r} name no line"
        if ab[0] < 1 or ab[1] > n_lines:
            return f"its span's lines {span.get('lines')} lie outside the text's {n_lines} lines"
    flat = fold(text).lower()
    for key in ("start", "end"):
        q = span.get(key)
        if isinstance(q, str) and q.strip() and fold(q).lower() not in flat:
            if plain_text(q).lower() not in plain_text(text).lower():
                return f"its span's {key} quote is not in the text: {q[:40]}"
    return None


@check("span-resolves")
def _span_resolves(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every span names lines or quotes that exist in the source text (THYM.md 7.2 law 2): a fabula's items in the
    text it was derived from; an atem's span in its text, and the items it centres on (`of`) in its fabula."""
    src = first_input(inputs, "text", "short")
    if output.type == "atem":
        a = output.mapping() or {}
        fab = first_input(inputs, "fabula", "item") or fabula_for(output, inputs)
        if a.get("of"):
            ids = {it.get("id") for it in fabula_doc(fab)[1]} if fab is not None else set()
            bad = [i for i in a["of"] if i not in ids]
            if bad:
                return False, f"the atem centres on {', '.join(map(str, bad))}, which the fabula does not hold"
        if isinstance(a.get("span"), dict) and src is not None:
            text = src.text()
            why = _span_problem(a, text, len(text.replace("\r\n", "\n").split("\n")))
            if why:
                return False, f"the atem: {why}"
        return True, ""
    if src is None:
        return False, "no source text to resolve the spans in"
    text = src.text()
    n = len(text.replace("\r\n", "\n").split("\n"))
    for it in fabula_doc(output)[1]:
        why = _span_problem(it, text, n)
        if why:
            return False, f"{it.get('id')}: {why}"
    return True, ""


@check("stance-closed")
def _stance_closed(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every claim has a stance, from EMF's closed list of six (MacroCOSM 18.4.3)."""
    for it in fabula_doc(output)[1]:
        if item_kind(it) == "claim" and it.get("stance") not in LADDER:
            return False, f"{it.get('id')}: stance {it.get('stance')!r} is not one of {', '.join(LADDER)}"
        if "stance" in it and it.get("stance") not in LADDER:
            return False, f"{it.get('id')}: stance {it.get('stance')!r} is not one of {', '.join(LADDER)}"
    return True, ""


def _term_problem(ctx: Any, it: dict) -> str | None:
    feed = it.get("feed")
    if mc.is_pending(feed):
        return None if "not in feed" in str(feed.get("pending")).lower() else "its open question is not 'not in FEED'"
    name = str(it.get("name") or "")
    word = feed.get("word") if isinstance(feed, dict) and feed.get("word") else name
    if name[:1].isupper() and not name.isupper():
        return None                                      # a named entity, never a FEED word
    lookup = (getattr(ctx, "engines", None) or {}).get("feed")
    if lookup is None:
        return None if isinstance(feed, dict) and feed.get("word") else "it says nothing of FEED"
    try:
        found = lookup([str(word)]) or {}
    except Exception:  # noqa: BLE001 - a FEED that cannot be read grounds nothing, and says so
        return "FEED could not be read"
    key = str(word).lower().strip()
    if isinstance(found.get(key), dict) or any(isinstance(v, dict) for v in found.values()):
        return None
    return f"{word!r} is not in FEED, and the term does not say so"


@check("terms-grounded")
def _terms_grounded(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every `L:term` is in FEED, or carries `{pending: "not in FEED"}`, or is a named entity (THYM.md 7.2 law 2),
    looked up through the host's FEED (`ctx.engines["feed"]`); without FEED a term's own grounding is trusted."""
    note = "" if (getattr(ctx, "engines", None) or {}).get("feed") else "FEED is not here; the terms' own feed blocks"
    for it in fabula_doc(output)[1]:
        if item_kind(it) != "term":
            continue
        why = _term_problem(ctx, it)
        if why:
            return False, f"{it.get('id')}: {why}"
    return True, note and f"{note} were trusted"


@check("atem-shape")
def _atem_shape(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """The line is 15 to 25 words; the focus at most two sentences; push one; pull one (MacroCOSM 18.3.5). A scaffold
    (THYM.md 19) promises less: a line of at most 25 words, the parts it cannot give as open questions."""
    a = output.mapping() if isinstance(output.payload, dict) else {"line": output.text()}
    if output.type == "fabula":
        a = _code.atem_of(output)                          # the fold's fabulac: its catalog's atem (THYM 20.6)
    a = a or {}
    pending = output.state == "pending"
    line = a.get("line")
    if mc.is_pending(line) or not isinstance(line, str):
        return (True, "") if pending and mc.is_pending(line) else (False, "the atem has no line")
    n = len(words_in(line))
    if n > 25 or (n < 15 and not pending):
        return False, f"the line is {n} words, not 15 to 25"
    for part, most in (("focus", 2), ("push", 1), ("pull", 1)):
        v = a.get(part)
        if mc.is_pending(v):
            if pending:
                continue
            return False, f"the {part} is an open question: {v.get('pending')}"
        if not isinstance(v, str) or not v.strip():
            return False, f"the atem has no {part}"
        k = len(segment(v)) or 1
        if k > most:
            return False, f"the {part} is {k} sentences, more than {most}"
    return True, ""


@check("span-inside")
def _span_inside(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """The expanded short says the claims of the atem's span (THYM.md 7.3): every claim the atem centres on (`of`),
    and every claim whose span meets the atem's, is cited by a sentence of the short."""
    a_val = first_input(inputs, "atem")
    fab = fabula_for(output, inputs)
    if a_val is None or fab is None:
        return False, "no atem and fabula to read the span from"
    a = a_val.mapping() or {}
    _cat, items = fabula_doc(fab)
    claims = {it.get("id"): it for it in items if item_kind(it) == "claim"}
    want = [i for i in (a.get("of") or []) if i in claims]
    if isinstance(a.get("span"), dict):
        ab = span_lines(a)
        if ab:
            want += [i for i, it in claims.items() if (sp := span_lines(it)) and sp[0] <= ab[1] and sp[1] >= ab[0]
                     and i not in want]
    if not want:
        return True, "the atem names no claim of the fabula"
    t = entailment_of(output)
    cited = {c for cs in ((t or {}).get("covers") or []) for c in cs}
    lost = [i for i in want if i not in cited]
    if lost:
        return False, f"the short does not say {', '.join(lost)}, which the atem centres on"
    return True, ""


from enough.thym.moves import code as _code  # noqa: E402 - the fabulac's branches of derive and entail
from enough.thym.moves import verse as _verse  # noqa: E402 - the fabulap's helper moves and derive's with branch

__all__ = ["as_fabula", "atem", "cited_outline", "default_order", "derive", "entail", "expand", "ordered"]
