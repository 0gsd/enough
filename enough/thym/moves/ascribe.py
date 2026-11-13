"""Ascribe's moves for Thym (Ascribe, https://ascribe.cosmoes.org/, sections 9 and 14; THYM 6.2, 6.3, 18): `propose`,
declared in Ascribe's own manifest for `thym 1`, and `project`, the body of `project h as isograph` and `project h as
allograph`.

**The engine.** These moves never read or write a holograph themselves: they reach Ascribe's module only through
`ctx.engines["ascribe"]`, which the host supplies (this folder is vendored into a product that brings its own), and
every engine call is recorded and replayed with the run, so every argument and every answer is plain data (paths,
text, lists, strings, whole numbers). The engine answers these functions:

- `thym_forms(holograph) -> {text, whole}`: what a reading may see of the holograph after its private filter (its
  forms and polyforms, by id, name and FEED word, and its pseudonyms), as YAML text; `whole` is true when a marker
  beside the catalog withholds everything.
- `thym_propose(holograph, proposals, *, text, sha256, run=None, at=None, made=None) -> {items, nodes, refused}`:
  the model's proposals (YAML text) as candidate nodes and their questions, each candidate stamped with `made`,
  checked against the holograph and writing nothing:
  `items` the YAML text `{nodes: [...]}` (a form a reading made, the candidate, its question, in that order),
  `nodes` `[[proposal index, candidate id], ...]`, `refused` `[{index, why}]`.
- `thym_isograph(holograph, *, epoch, program, trace, keep=None) -> {json, items}`: the holograph's isograph
  (`ascribe-isograph/0`) after the filter, as canonical JSON text, and the ids of the items in it. It records no
  release: the host records it when the run lands, before anything leaves.
- `thym_allograph(holograph, *, epoch, program, trace, keep=None) -> {json, items, holograph}`: the holograph's
  allograph (`ascribe-allograph/0`) the same way, and the holograph's state as the run took it; no release either.
- `thym_isograph_problems(text)`, `thym_allograph_problems(text) -> [words]`: why a reader would refuse the
  projection, for the checks of `project` of each kind.

A `holograph` argument is `{path}`, the holograph's folder. With no such engine, or one that lacks a function, the
move refuses in plain words.

**propose f with h** (THYM 6.3): the fabula of the holder's own prose (a fabulan, whose `source` names the text and
its sha256), with the holograph, gives the candidates a reading proposes and the question about each (`why: unsure`,
`to: holder`, `kind: choice`, `options: [yes, no, partly]`), which a program lands with `gather`. It asks the model
once; a proposal that names a person, invents a form, or would add a check error is refused by the engine, and an
answer from which nothing could be kept is a failed reading, asked again. The list it gives carries, beside it, the
sentence-to-item map `no-invention` reads: each candidate's summary and the fabula's items it was read from.
Nothing it proposes is the holder's until they answer yes.

**project** is what `project h as isograph` and `project h as allograph` do for a holograph (Ascribe's one entry
that `extends` Comprise's `project`, THYM 17.6): the program's emitted nodes (default-deny: an item neither emitted
nor withheld is left out), less what it withheld, projected by the engine as the kind the call names. The engine's
`thym_allograph` answers as `thym_isograph` does, with `holograph` beside: the holograph's state after the filter,
which the host keeps with the listing so that it can say when the holograph has changed since (Ascribe 14.6). No move
sends anything to a registry.

The standard library, PyYAML and the MacroCOSM reader.
"""
from __future__ import annotations

from typing import Any

from enough import macrocosm as mc
from enough.thym.moves import MoveError, fabula_doc, strip_fences
from enough.thym.checks import check
from enough.thym.registry import Request, implements, prompt_for
from enough.thym.trace import write_atomic
from enough.thym.values import Value, is_withheld, plain

ENGINE = "ascribe"
FUNCTIONS = ("thym_forms", "thym_propose", "thym_isograph", "thym_allograph")
HOLOGRAPH_OES = "ascribe/1"
_DOES = {"thym_forms": "read a holograph's forms", "thym_propose": "turn a reading into candidates",
         "thym_isograph": "project a holograph as an isograph",
         "thym_isograph_problems": "read an isograph as a reader would",
         "thym_allograph": "project a holograph as an allograph",
         "thym_allograph_problems": "read an allograph as a reader would"}
#: The kinds Ascribe adds to `project` (THYM 6.2), each its engine function and the file it stages.
KINDS = {"isograph": ("thym_isograph", "isograph.json"), "allograph": ("thym_allograph", "allograph.json")}


def _engine(ctx: Any, move: str, fn: str) -> Any:
    """`ctx.engines["ascribe"].<fn>`, or a refusal in plain words."""
    engines = getattr(ctx, "engines", None) or {}
    try:
        eng = engines.get(ENGINE) if hasattr(engines, "get") else None
    except Exception:  # noqa: BLE001 - an engine table that cannot answer is no engine
        eng = None
    if eng is None:
        raise MoveError(f"{move} needs the ascribe engine, which keeps a person's holograph, and this host has none")
    got = getattr(eng, fn, None)
    if got is None or not callable(got):
        raise MoveError(f"the ascribe engine here cannot {_DOES[fn]}, which {move} needs")
    return got


def _holograph(v: Any, move: str) -> dict:
    """A holograph value as the engine takes it, `{path}`; refused when it is not a holograph folder."""
    if not isinstance(v, Value) or v.type != "volume" or v.path is None:
        raise MoveError(f"{move} reads a holograph, a folder volume: {move} … with h")
    p = v.payload
    oes = p.oes if isinstance(p, mc.Volume) else (v.mapping() or {}).get("oes")
    if oes != HOLOGRAPH_OES:
        raise MoveError(f"{move} reads a holograph (oes: {HOLOGRAPH_OES}), and this volume is {oes or 'no holograph'}")
    return {"path": str(v.path)}


PROPOSE_SYSTEM = """You read the fabula of a text its author wrote about their own life and thoughts, and you \
propose what the text shows of its author: what they are drawn to or turn from (affinity), hold to be true (belief), \
worry about (concern), have lived through (experience), want to know more about (interest), think and would say \
(opinion), feel from the inside (quale), can do (skill), have come to understand (understanding) and long for \
(yearning). Each proposal is a candidate the author will be asked about; nothing is theirs until they say yes.

Propose only what the text says, never a guess about the person. Name people only by role ("a neighbour", "an old \
teacher") or by a pseudonym the holograph declares, never by name, and write no address, date of birth or number \
that could identify anyone. Say what each candidate is about in a word or two, using a form the holograph already \
has when one fits.

Answer in YAML and nothing else:
candidates:
  - kind: <one of the ten kinds>
    name: <a few words>
    summary: <one line, in plain words>
    form: <what it is about, in a word or two>
    span: {lines: "<first>-<last>"}
    confidence: <from 0 to 1: how plainly the text shows it>
    cites: [<the ids of the fabula's items it was read from>]"""


def _get(inputs: dict, name: str) -> str:
    pair = (inputs or {}).get(name)
    v = pair[0] if isinstance(pair, (tuple, list)) else pair
    return v.text() if isinstance(v, Value) else str(v if v is not None else "")


def propose_messages(contract: dict, inputs: dict) -> list[dict] | None:
    """The request `propose` makes of the model: the fabula of the holder's own text, and the holograph's forms."""
    if not (inputs or {}).get("fabula"):
        return None
    user = (f"The fabula of the author's text:\n{_get(inputs, 'fabula')}\n\nThe forms and the pseudonyms their "
            f"holograph already has:\n{_get(inputs, 'forms')}\n\nPropose the candidates.")
    return [{"role": "system", "content": PROPOSE_SYSTEM}, {"role": "user", "content": user}]


prompt_for("propose")(propose_messages)

#: The prompt builders this module carries, by move: the host reads them and puts them in front of its own.
PROMPTS = {"propose": propose_messages}


@implements("propose")
def propose(ctx: Any, f: Value, **mods: Any) -> Request:
    """Candidate nodes the holder's own text suggests, each with the question that asks whether it is so (Ascribe,
    section 9; THYM 6.3)."""
    if not isinstance(f, Value) or f.type != "fabula":
        raise MoveError("propose reads the fabula of the holder's own text: propose f with h")
    hol = _holograph(mods.get("with"), "propose")
    cat, items = fabula_doc(f)
    flavour = cat.get("flavour") or "fabulan"
    if flavour != "fabulan":
        raise MoveError(f"propose reads a fabulan, the fabula of the holder's own prose, and this is a {flavour}")
    src = cat.get("source") if isinstance(cat.get("source"), dict) else {}
    text, sha = src.get("path"), src.get("sha256")
    if not (isinstance(text, str) and text.strip() and isinstance(sha, str) and sha.strip()):
        raise MoveError("the fabula names no source text with its sha256; propose reads the holder's own text, "
                        "decompiled, and cites it by its digest")
    forms = _engine(ctx, "propose", "thym_forms")(hol)
    if (forms or {}).get("whole"):
        raise MoveError("a private marker sits beside the holograph's catalog: nothing of it is read, and nothing "
                        "is proposed")
    turn = _engine(ctx, "propose", "thym_propose")
    ids = {it.get("id") for it in items if isinstance(it, dict)}

    def parse(output: Any) -> Value:
        data = mc.yaml_load(strip_fences(str(output or "")))
        if isinstance(data, dict):
            data = data.get("candidates")
        if not isinstance(data, list) or not data or not all(isinstance(p, dict) for p in data):
            raise ValueError("the answer is not a list of candidates")
        props, cites = [], []
        for p in data:
            c = p.get("cites")
            cites.append([x for x in c if x in ids] if isinstance(c, list) else [])
            props.append({k: v for k, v in p.items() if k != "cites"})
        made = {"move": "propose", "run": getattr(ctx, "run", None)}
        node = getattr(ctx, "node", None)
        if isinstance(node, dict) and node.get("id"):
            made["step"] = str(node["id"])
        res = turn(hol, mc.dump({"candidates": plain(props)}), text=text, sha256=sha,
                   run=getattr(ctx, "run", None), at=getattr(ctx, "now", None),
                   made={k: v for k, v in made.items() if v is not None})
        if not res.get("nodes"):
            why = "; ".join(str(r.get("why")) for r in (res.get("refused") or [])[:3]) or "nothing was proposed"
            raise ValueError(f"no candidate could be kept: {why}")
        got = mc.yaml_load(res["items"]) or {}
        nodes = [d for d in got.get("nodes") or [] if isinstance(d, dict)]
        index = {n: i for i, n in res["nodes"]}
        sentences = [d["summary"] for d in nodes if d.get("id") in index]
        covers = [cites[index[d["id"]]] for d in nodes if d.get("id") in index]
        members = [Value("item", d, origin={"id": d.get("id"), "kind": d.get("type"), "oes": HOLOGRAPH_OES})
                   for d in nodes]
        return Value("list", members, origin={"entailment": {"fabula": f, "sentences": sentences, "covers": covers,
                                                          "order": None, "morph": "null"}})

    return Request(contract={"schema": {"format": "yaml", "shape": "candidates: [{kind, name, summary, form, span, "
                                                                     "confidence, cites}]"},
                             "repair": []},
                   inputs={"fabula": f, "forms": Value("string", str((forms or {}).get("text") or ""))},
                   parse=parse)


def _emitted_ids(ctx: Any) -> list[str]:
    withheld = getattr(ctx, "withheld", None) or {}
    out = []
    for v in getattr(ctx, "emitted", None) or []:
        if not isinstance(v, Value) or is_withheld(withheld, v):
            continue
        iid = (v.origin or {}).get("id") or (v.mapping() or {}).get("id")
        if isinstance(iid, str):
            out.append(iid)
    return out


def _projection(ctx: Any, h: Value, kind: str) -> Value:
    """`project h as <kind>` for a holograph, an isograph or an allograph: the nodes the program emitted and did not
    withhold, projected by the rules of the kind's schema; the epoch the run falls in, by quarter; the program's name
    and digest; the run's id. Written into the run's stage as `<kind>.json`, its canonical form, so that it lands with
    the run or not at all."""
    fn, staged = KINDS[kind]
    hol = _holograph(h, "project")
    try:
        prog = (ctx.trace().mapping() or {}).get("program") or {}
    except Exception:  # noqa: BLE001 - a trace that cannot be read names no program
        prog = {}
    now, run = getattr(ctx, "now", None), getattr(ctx, "run", None)
    if now is None or not prog.get("name") or not prog.get("sha256") or not run:
        raise MoveError(f"an {kind} names its epoch, its program and its run, and this run gives none of them")
    epoch = f"{now.year}-Q{(now.month - 1) // 3 + 1}"
    # the projection names the run by its id; the trace's digest goes into the release record, once the run has landed
    res = _engine(ctx, "project", fn)(hol, epoch=epoch, program={"name": prog["name"], "sha256": prog["sha256"]},
                                      trace={"run": str(run)}, keep=_emitted_ids(ctx))
    doc = mc.yaml_load(res["json"])
    stage = getattr(ctx, "stage", None)
    if stage is not None:
        write_atomic(stage / staged, res["json"].encode("utf-8"))
    # the ids that left ride in the value's origin, for the release the host records once the run has landed; an
    # allograph's also carries the holograph's state as the run took it (Ascribe 14.6: made again, never edited)
    origin: dict = {"items": list(res.get("items") or [])}
    if res.get("holograph"):
        origin["holograph"] = str(res["holograph"])
    return Value("volume", doc, origin=origin)


def isograph(ctx: Any, h: Value, **mods: Any) -> Value:
    """`project h as isograph` for a holograph (Ascribe 14.1)."""
    return _projection(ctx, h, "isograph")


def allograph(ctx: Any, h: Value, **mods: Any) -> Value:
    """`project h as allograph` for a holograph (Ascribe 14.6): only E, S and U, offered, public and known; no hid, no
    handle. Nothing is sent anywhere: listing is the implementation's act after the run, at the holder's word."""
    return _projection(ctx, h, "allograph")


def project(ctx: Any, h: Value, **mods: Any) -> Value:
    """The code of Ascribe's one `extends` entry of `project` (THYM 17.6): the call's `as` word chooses the kind."""
    kind = mods.get("as")
    if kind not in KINDS:
        raise MoveError(f"Ascribe projects a holograph as an isograph or an allograph, not as {kind!r}")
    return _projection(ctx, h, kind)


# ---------------------------------------------------------------------------
# `project … as isograph`: the kind Ascribe adds to `project` (its manifest's `extends: true` entry), held to the
# isograph's own schema (`ascribe-isograph/0`, Ascribe 14.1) under the check names THYM 6.3 gives `project`;
# Comprise's kinds keep Comprise's implementations of the same names.
# ---------------------------------------------------------------------------

def _isograph_problems(output: Value, ctx: Any) -> list[str]:
    import json
    data = output.mapping()
    if not isinstance(data, dict):
        return ["the projection is not an ascribe-isograph/0 document"]
    text = json.dumps(plain(data), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return list(_engine(ctx, "project", "thym_isograph_problems")(text))


def _verdict(problems: list[str]) -> tuple[bool, str]:
    return (not problems), "; ".join(problems)


@check("default-deny", kind="isograph")
def _isograph_default_deny(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """The isograph holds only the fields ascribe-isograph/0 names, each in its shape, every entry `stated`."""
    return _verdict([p for p in _isograph_problems(output, ctx) if "holds a number" not in p
                     and not p.startswith("epoch ")])


@check("no-counts", kind="isograph")
def _isograph_no_counts(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Assertions, not measurements: no number of anything (Ascribe 14.1)."""
    return _verdict([p for p in _isograph_problems(output, ctx) if "holds a number" in p])


@check("epoch", kind="isograph")
def _isograph_epoch(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """The isograph names its epoch: a quarter, a month or a week."""
    return _verdict([p for p in _isograph_problems(output, ctx) if p.startswith("epoch ") or p == "no epoch"])


# `project … as allograph`, held to `ascribe-allograph/0` (Ascribe 14.6) under the same check names.

def _allograph_problems(output: Value, ctx: Any) -> list[str]:
    import json
    data = output.mapping()
    if not isinstance(data, dict):
        return ["the projection is not an ascribe-allograph/0 document"]
    text = json.dumps(plain(data), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return list(_engine(ctx, "project", "thym_allograph_problems")(text))


@check("default-deny", kind="allograph")
def _allograph_default_deny(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """The allograph holds only the fields ascribe-allograph/0 names, each in its shape, one entry per kind and form,
    in order, every entry `stated`."""
    return _verdict([p for p in _allograph_problems(output, ctx) if "holds a number" not in p
                     and not p.startswith("epoch ")])


@check("no-counts", kind="allograph")
def _allograph_no_counts(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Assertions, not measurements: no number of anything (Ascribe 14.6)."""
    return _verdict([p for p in _allograph_problems(output, ctx) if "holds a number" in p])


@check("epoch", kind="allograph")
def _allograph_epoch(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """The allograph names its epoch: a quarter, a month or a week."""
    return _verdict([p for p in _allograph_problems(output, ctx) if p.startswith("epoch ") or p == "no epoch"])


__all__ = ["FUNCTIONS", "KINDS", "PROMPTS", "allograph", "isograph", "project", "propose", "propose_messages"]
