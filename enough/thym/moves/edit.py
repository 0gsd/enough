"""The plain moves `thym/1` declares, and `cut` (docs/THYM.md 6.3, 7.3): `cut`, `count`, `words`, `digest`, `lint`,
`trace`, with the check `weight-order`.

All transcode: the same answer every time, in code.

- `cut` shortens a short by whole sentences, the lightest first, until it fits `to N words` or `to N sentences`. A
  sentence weighs what the heaviest item it says weighs (EMF's salience: critical, high, normal, low), read from the
  citations the short carries beside its text (`telling_of`); among sentences of one weight the later goes first, so
  the opening stays. A short read from disk carries no citations, and every sentence weighs the same. Headings are
  structure: one goes only when nothing is left under it. The footer stays.
- `count` counts a volume's items, a fabula's items, a short's lines or a list's members; `words` counts a text's,
  a short's (its body, without front matter or footer) or an atem line's words; `digest` is a value's sha256 over its
  canonical bytes (THYM.md 12.6); `lint` runs the checks a volume's MiniCOSM selects and gives the report; `trace`
  gives the run's trace so far.

Standalone: the standard library, PyYAML and `enough.macrocosm`.
"""
from __future__ import annotations

import re
from typing import Any

from enough import macrocosm as mc
from enough.thym import checks as C
from enough.thym.checks import body, check
from enough.thym.moves import SALIENCE, MoveError, fabula_doc, fold, short_value, telling_of
from enough.thym.registry import Amount, implements
from enough.thym.values import Value, members, plain


# ---------------------------------------------------------------------------
# cut
# ---------------------------------------------------------------------------

def _units(text: str) -> tuple[str, list[list[str]], str]:
    """A short as (front, paragraphs of units, footer): each unit a sentence by the runtime's sentence rule
    (`checks.sentences`), so that `whole-sentences` reads them the same way."""
    raw = text.replace("\r\n", "\n")
    fm = re.match(r"\A---\n.*?\n---\n?", raw, re.S)
    front = fm.group(0) if fm else ""
    whole = body(raw, footer=True)
    core = body(raw)
    footer = whole[len(core):].strip("\n") if whole.startswith(core) else ""
    paras = [C.sentences(p) for p in re.split(r"\n\s*\n", core) if p.strip()]
    return front, [p for p in paras if p], footer


def _weights(short: Value, units: list[str]) -> list[int]:
    """Each unit's weight: the heaviest salience among the items its sentence cites (normal for an item without one);
    every unit weighs `normal` when the short carries no citations."""
    t = telling_of(short)
    if not t or t.get("covers") is None:
        return [SALIENCE["normal"]] * len(units)
    fab = t.get("fabula")
    sal = {it.get("id"): SALIENCE.get(str(it.get("salience") or "normal"), 1) for it in fabula_doc(fab)[1]}
    said = [(fold(s), c) for s, c in zip(t.get("sentences") or [], t.get("covers") or [])]
    out = []
    for u in units:
        fu = fold(u)
        cites = next((c for s, c in said if fu == s or fu in s or s in fu), [])
        out.append(max((sal.get(c, 1) for c in cites), default=SALIENCE["normal"]))
    return out


def _is_heading(u: str) -> bool:
    return bool(re.match(r"^#{1,6}\s", u))


def _cites_of(short: Value, kept: list[str]) -> tuple[list[str], list[list[str]]] | None:
    t = telling_of(short)
    if not t or t.get("covers") is None:
        return None
    said = [(fold(s), c) for s, c in zip(t.get("sentences") or [], t.get("covers") or [])]
    sents, covers = [], []
    for u in kept:
        fu = fold(u)
        hit = next(((s, c) for s, c in said if fu == s or fu in s or s in fu), None)
        if hit is not None and (not sents or sents[-1] != hit[0]):
            sents.append(hit[0])
            covers.append(list(hit[1]))
    return sents, covers


@implements("cut")
def cut(ctx: Any, short: Value, **mods: Any) -> Value:
    """A short shortened by whole sentences, the lightest first (THYM.md 6.3), until it fits `to N words` or `to N
    sentences`."""
    to = mods.get("to")
    if not isinstance(to, Amount) or to.unit not in ("words", "sentences"):
        raise MoveError("cut needs a length: cut <short> to N words, or to N sentences")
    front, paras, footer = _units(short.text())
    flat = [(pi, ui, u) for pi, p in enumerate(paras) for ui, u in enumerate(p)]
    weights = dict(zip(((pi, ui) for pi, ui, _u in flat), _weights(short, [u for _pi, _ui, u in flat])))
    alive = {(pi, ui) for pi, ui, _u in flat}

    def size() -> int:
        kept = [u for pi, ui, u in flat if (pi, ui) in alive]
        return len(kept) if to.unit == "sentences" else sum(C.words(u) for u in kept)

    order = sorted(((pi, ui) for pi, ui, u in flat if not _is_heading(u)),
                   key=lambda k: (weights[k], -k[0], -k[1]))
    for k in order:
        if size() <= to.n or sum(1 for q in order if q in alive) <= 1:
            break                                   # it fits, or one sentence is all that is left
        alive.discard(k)
        # a heading goes when nothing is left under it
        for pi, ui, u in flat:
            if _is_heading(u) and (pi, ui) in alive:
                below = [(qi, vi) for qi, vi, v in flat if (qi, vi) > (pi, ui) and not _is_heading(v)]
                nxt = next(((qi, vi) for qi, vi, v in flat if (qi, vi) > (pi, ui) and _is_heading(v)), None)
                under = [b for b in below if nxt is None or b < nxt]
                if under and not any(b in alive for b in under):
                    alive.discard((pi, ui))
    if size() > to.n:
        raise MoveError(f"cut cannot fit the short to {to.n} {to.unit} by whole sentences")
    kept_paras = [" ".join(u for ui, u in enumerate(p) if (pi, ui) in alive) for pi, p in enumerate(paras)]
    kept_paras = [p for p in kept_paras if p]
    text = front + "\n\n".join(kept_paras) + (f"\n\n{footer}" if footer else "") + "\n"
    if front and not text.startswith(front):
        text = front + text
    kept = [u for pi, ui, u in flat if (pi, ui) in alive]
    t = telling_of(short) or {}
    cites = _cites_of(short, kept)
    extra = {k: v for k, v in t.items() if k not in ("fabula", "sentences", "covers", "order", "morph")}
    extra["cut_from"] = short.sha256
    if cites is None:
        return short_value(text, fabula=t.get("fabula"), order=t.get("order"), morph=t.get("morph"), **extra)
    return short_value(text, fabula=t.get("fabula"), sentences=cites[0], covers=cites[1], order=t.get("order"),
                       morph=t.get("morph"), **extra)


@check("weight-order")
def _weight_order(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """`cut` removed the lightest sentences first (THYM.md 7.3): no sentence it removed weighs more than a sentence
    it kept (a sentence weighs the heaviest salience among the items it cites)."""
    src = next((v for v in inputs.values() if isinstance(v, Value) and v.type in ("short", "text")), None)
    if src is None:
        return False, "no short among the inputs"
    _f, paras, _foot = _units(src.text())
    units = [u for p in paras for u in p]
    weights = _weights(src, units)
    kept_text = {fold(u) for p in _units(output.text())[1] for u in p}
    removed = [w for u, w in zip(units, weights) if fold(u) not in kept_text and not _is_heading(u)]
    kept = [w for u, w in zip(units, weights) if fold(u) in kept_text and not _is_heading(u)]
    if not telling_of(src) or telling_of(src).get("covers") is None:
        return True, "the short carries no citations, so every sentence weighed the same"
    if removed and kept and max(removed) > min(kept):
        names = {v: k for k, v in SALIENCE.items()}
        return False, f"a {names[max(removed)]} sentence was removed while a {names[min(kept)]} one was kept"
    return True, ""


# ---------------------------------------------------------------------------
# count, words, digest, lint, trace
# ---------------------------------------------------------------------------

@implements("count")
def count(ctx: Any, v: Value, **_: Any) -> Value:
    """How many items a volume or a fabula holds, how many lines a short has, how many members a list has."""
    if v.type == "fabula":
        return Value("number", len(fabula_doc(v)[1]))
    rows = members(v)
    if rows is None:
        raise MoveError(f"a {v.type} has nothing to count")
    return Value("number", len(rows))


@implements("words")
def words(ctx: Any, v: Value, **_: Any) -> Value:
    """How many words: a text's, a short's body (front matter and footer left out), an atem's line."""
    if v.type == "atem":
        a = v.mapping() or {}
        line = a.get("line") if isinstance(a.get("line"), str) else (v.payload if isinstance(v.payload, str) else "")
        return Value("number", C.words(line))
    text = v.text()
    return Value("number", C.words(body(text) if v.type == "short" else C.front_matter(text)[1]))


@implements("digest")
def digest(ctx: Any, v: Value, **_: Any) -> Value:
    """A value's sha256, over its canonical bytes (THYM.md 12.6)."""
    return Value("string", v.sha256)


@implements("lint")
def lint(ctx: Any, v: Value, **_: Any) -> Value:
    """The checks a volume's MiniCOSM selects, and their verdicts: `{ok, errors, warnings, notes}`, each a line."""
    vol = v.payload if isinstance(v.payload, mc.Volume) else None
    if vol is None:
        data = v.mapping()
        if data is None:
            raise MoveError(f"a {v.type} is not a volume to lint")
        name = v.path.name if v.path is not None and v.path.suffix == ".cosm" else "volume.cosm"
        vol = mc.load_volume_text(mc.dump(plain(data)), filename=name)
    if vol.refused is not None:
        return Value("report", {"ok": False, "minicosm": vol.oes, "checks": [], "not_run": [],
                                "errors": [str(vol.refused)], "warnings": [], "notes": []})
    rep = mc.lint(vol)
    out = {"ok": rep.ok, "minicosm": vol.oes, "checks": list(rep.checks), "not_run": list(rep.not_run),
           "errors": [str(p) for p in rep.errors], "warnings": [str(p) for p in rep.warnings],
           "notes": [str(p) for p in rep.notes]}
    return Value("report", out)


@implements("trace")
def trace(ctx: Any, **_: Any) -> Value:
    """The run's trace so far (THYM.md 6.3)."""
    return ctx.trace()


__all__ = ["count", "cut", "digest", "lint", "trace", "words"]
