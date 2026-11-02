"""The moves Comprise's sidecar declares (`comprise.moves.cosm`): `project`, `band`, `mark`, `withhold`, and the
target schema's rules as named checks (docs/THYM.md 18; docs/thym-comprise-spec.md 1; comprise-isotype/0).

All four transcode: a projection never asks a model. The program says what is emitted (an item, marked `verified` or
`stated`), what fills a field the schema names (a labelled `emit`, such as `employees:`), and what is withheld;
`project` assembles the target from that and from nothing else, by the rules of `comprise-isotype/0`:

- **default-deny**: the keys `isotype hid epoch cadence sample identity shape offers seeks open_to`, plus `program`
  (the name and sha256 of the program that projected it, THYM.md 18). The trace's digest is not known until the run
  lands, so the release, not the projection, adds `trace`. An item neither emitted nor withheld is left out, as if
  withheld, and only counted, in the trace (`verified-derived`'s why);
- **assertions, not measurements**: no number but the founded year; an offer's summary that holds a digit is not
  published, and an aim or a market that holds one is left out (Comprise's `scrub`);
- **withhold, never falsify**: what `withhold` named leaves no mark, count or gap; lists are sorted, so their order
  tells nothing;
- **verified and stated**: offers (suites, offerings, functions, products, services, platforms) and markets
  (audiences, markets, geographies) only when marked `verified`; seeks and open-to only from aims marked `stated`,
  by their `stance` (`seeking`, `open`); a labelled field of `shape` only when marked `verified`;
- **identity** only where the holotype states it publicly (an item marked `visibility: public`; the brand of the
  product tree is public unless it says otherwise, as COSM shows it): the name and kind from the brand, the founded
  year from a public anchor entity, else the brand; the jurisdiction from a public anchor entity; the domains from the
  company's own public website and a public anchor entity;
- **epochs**: the epoch is the one `ctx.now` falls in, at the holotype's cadence (quarterly unless it says monthly or
  weekly); no other date is shown.

`project` gives the projection as a volume (a mapping with exactly those keys), and writes it into the run's stage as
`isotype.cosm` beside `isotype.json`, its canonical form (keys sorted, no spaces, UTF-8: what Comprise signs), so
both land with the run or not at all. A paratype is the same projection at third-party standing (the thym-Comprise
spec 2.1): `paratype` in place of `isotype`, with `standing`, `submitter` and `of`.

`band` says a number as a word from a list: `[none, some]` is 0 for none and anything more for some; any other list
of k words is cut at equal thresholds of ten (the first word below 10, the next below 20, the last from 10·(k-1)).
`mark` sets `marking: verified | stated` on an item, or on a word. `withhold` records items in `ctx.withheld`.

Standalone: the standard library, PyYAML and `enough.macrocosm`.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import urllib.parse
from typing import Any

from enough import macrocosm as mc
from enough.thym.checks import check
from enough.thym.moves import MoveError, as_list, fold, modifiers
from enough.thym.registry import implements
from enough.thym.trace import write_atomic
from enough.thym.values import Value, members, plain

ISOTYPE = "comprise-isotype/0"
PARATYPE = "comprise-paratype/0"
CADENCES = ("quarterly", "monthly", "weekly")
OFFER_KINDS = ("suite", "offering", "function", "product", "service", "platform")
MARKET_KINDS = ("audience", "market", "geography")
IDENTITY_KINDS = ("brand", "entity", "surface")
SHAPE_KINDS = ("position",)
AIM_KINDS = ("customers", "partners", "suppliers", "distribution", "technology", "talent", "capital", "other")
#: The kinds each MiniCOSM derives, so that `mark ... as verified` holds only on them (THYM.md 7.3).
DERIVABLE = {"comprise": OFFER_KINDS + MARKET_KINDS + IDENTITY_KINDS + SHAPE_KINDS}
#: The fields of the schema a labelled `emit` may fill, and the words a banded one may hold (None: any list of names).
SHAPE_SLOTS = {"employees": ("none", "some"), "structure": ("single", "group"), "markets": None}
IDENTITY_SLOTS = ("name", "domains", "jurisdiction", "founded", "kind")
LIVE = (None, "active")
AIM_LIVE = (None, "active", "planned")
MAX_OFFERS, MAX_MARKETS = 50, 12
EPOCH_RE = {"quarterly": re.compile(r"^\d{4}-Q[1-4]$"), "monthly": re.compile(r"^\d{4}-(0[1-9]|1[0-2])$"),
            "weekly": re.compile(r"^\d{4}-W(0[1-9]|[1-4]\d|5[0-3])$")}
HID_RE = re.compile(r"^[a-z2-7]{26}$")
_DIGIT = re.compile(r"\d")
_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def epoch_for(cadence: str, when: Any) -> str:
    """The epoch a moment falls in (Comprise's `epoch_for`): `2026-Q4`, `2026-11`, `2026-W44`."""
    d = when.date() if isinstance(when, _dt.datetime) else when
    if cadence == "monthly":
        return f"{d.year}-{d.month:02d}"
    if cadence == "weekly":
        y, w, _ = d.isocalendar()
        return f"{y}-W{w:02d}"
    return f"{d.year}-Q{(d.month - 1) // 3 + 1}"


def _plain(v: Any) -> str | None:
    return fold(v) if isinstance(v, str) and v.strip() else None


def _year(v: Any) -> int | None:
    if isinstance(v, (_dt.date, _dt.datetime)):
        return v.year
    if isinstance(v, int) and not isinstance(v, bool) and 1000 <= v <= 2999:
        return v
    mt = re.match(r"^\s*([12]\d{3})(?:\b|-)", v) if isinstance(v, str) else None
    return int(mt.group(1)) if mt else None


def _id(v: Value) -> str | None:
    iid = (v.origin or {}).get("id") or (v.mapping() or {}).get("id")
    return str(iid) if iid else None


def _kind(v: Value) -> str:
    k = (v.origin or {}).get("kind")
    if isinstance(k, str) and k:
        return k
    mt = re.match(r"^[A-Z]:([a-z][a-z0-9-]*)/", _id(v) or "")
    return mt.group(1) if mt else ""


def _minicosm(v: Value) -> str:
    oes = (v.origin or {}).get("oes")
    if isinstance(oes, str) and "/" in oes:
        return oes.split("/", 1)[0]
    vol = (v.origin or {}).get("volume")
    if isinstance(vol, Value) and isinstance(vol.payload, mc.Volume) and vol.payload.oes:
        return str(vol.payload.oes).split("/", 1)[0]
    return ""


def marking_of(v: Value) -> str | None:
    """An item's or a word's marking (`mark`), or None when the program never marked it."""
    m = (v.origin or {}).get("marking")
    if m is None and isinstance(v.payload, dict):
        m = v.payload.get("marking")
    return m if m in ("verified", "stated") else None


def _letter(v: Value) -> str:
    return (_id(v) or " ")[0]


def _public(v: Value) -> bool:
    vis = (v.mapping() or {}).get("visibility")
    return vis == "public" or (vis is None and _letter(v) == "P")


def _domain(url: str) -> str | None:
    host = urllib.parse.urlsplit(url if "://" in url else "https://" + url).hostname
    if not host:
        return None
    host = host.lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def identity(rows: list[Value], withheld: set[str]) -> dict:
    """Identity, each field only where the holotype states it publicly (Comprise's `identity`)."""
    rows = [r for r in rows if _id(r) not in withheld]
    brand = next((r for r in rows if _kind(r) == "brand" and _public(r)), None)
    entity = next((r for r in rows if _kind(r) == "entity" and (r.mapping() or {}).get("anchor") is True
                   and (r.mapping() or {}).get("visibility") == "public"), None)
    b, e = (brand.mapping() if brand else {}) or {}, (entity.mapping() if entity else {}) or {}
    out: dict = {}
    name = _plain(b.get("name")) or _plain(e.get("name"))
    if name:
        out["name"] = name
    domains = set()
    for r in rows:
        d = r.mapping() or {}
        own = d.get("kind") == "website" and d.get("counterparty") in (None, "none", "self")
        if _kind(r) == "surface" and d.get("visibility") == "public" and own and _plain(d.get("url")):
            dom = _domain(d["url"])
            if dom:
                domains.add(dom)
    if e:
        listed = e.get("domains") if isinstance(e.get("domains"), list) else [e.get("domain")]
        gid = e.get("global-id") if isinstance(e.get("global-id"), dict) else {}
        for x in [*listed, gid.get("domain")]:
            if _plain(x):
                dom = _domain(x)
                if dom:
                    domains.add(dom)
    if domains:
        out["domains"] = sorted(domains)
    if _plain(e.get("jurisdiction")):
        out["jurisdiction"] = _plain(e["jurisdiction"])
    founded = _year(e.get("since")) or _year(b.get("since"))
    if founded:
        out["founded"] = founded
    if _plain(b.get("kind")):
        out["kind"] = _plain(b["kind"])
    return out


def _program_ref(ctx: Any) -> dict:
    try:
        prog = (ctx.trace().mapping() or {}).get("program") or {}
    except Exception:  # noqa: BLE001 - a trace that cannot be read names no program
        prog = {}
    name = prog.get("name") or getattr(getattr(ctx, "program", None), "name", None)
    return {"name": name, "sha256": prog.get("sha256")}


def canonical_json(doc: dict) -> bytes:
    """Keys sorted, no spaces, UTF-8: the form Comprise signs and Connect verifies (`core/isotype.py` `canonical`)."""
    return json.dumps(plain(doc), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@implements("project")
def project(ctx: Any, h: Value, **mods: Any) -> Value:
    """A holotype projected as an isotype (or a paratype) from what the program emitted, labelled and withheld."""
    kind = mods.get("as") or "isotype"
    if kind not in ("isotype", "paratype"):
        raise MoveError(f"project gives an isotype or a paratype, not {kind}")
    cat = h.mapping() or {}
    rows = members(h) or []
    withheld = set(ctx.withheld)
    cadence = cat.get("cadence") if cat.get("cadence") in CADENCES else "quarterly"
    offers: dict = {}
    markets: set[str] = set()
    seeks: dict = {}
    open_to: dict = {}
    for v in ctx.emitted:
        if not isinstance(v, Value) or _id(v) in withheld or not isinstance(v.payload, dict):
            continue
        d, k, m = v.payload, _kind(v), marking_of(v)
        if m == "verified" and k in OFFER_KINDS and d.get("status") in LIVE and _plain(d.get("name")):
            name = _plain(d["name"])
            summary = _plain(d.get("summary")) or ""
            offers.setdefault((k, name), {"name": name, "summary": "" if _DIGIT.search(summary) else summary,
                                          "kind": k})
        elif m == "verified" and k in MARKET_KINDS and d.get("status") in LIVE and _plain(d.get("name")):
            if not _DIGIT.search(d["name"]):
                markets.add(_plain(d["name"]))
        elif m == "stated" and k == "aim" and d.get("status") in AIM_LIVE and d.get("kind") in AIM_KINDS:
            summary = _plain(d.get("summary"))
            target = seeks if d.get("stance") == "seeking" else open_to if d.get("stance") == "open" else None
            if summary and target is not None and not _DIGIT.search(summary):
                target.setdefault((d["kind"], summary), {"kind": d["kind"], "summary": summary})
    shape: dict = {}
    ident = identity(rows, withheld)
    for slot, v in ctx.slots.items():
        if not isinstance(v, Value) or marking_of(v) != "verified":
            continue
        word = v.plain()
        if slot in SHAPE_SLOTS and SHAPE_SLOTS[slot] and word in SHAPE_SLOTS[slot]:
            shape[slot] = word
        elif slot == "markets":
            markets |= {fold(x) for x in as_list(word) if isinstance(x, str) and not _DIGIT.search(x)}
        elif slot in IDENTITY_SLOTS and slot not in ident and isinstance(word, str) and slot != "founded":
            ident[slot] = word
    if markets:
        shape["markets"] = sorted(markets, key=lambda s: (s.lower(), s))[:MAX_MARKETS]
    order = {k: i for i, k in enumerate(OFFER_KINDS)}
    aim_order = {k: i for i, k in enumerate(AIM_KINDS)}
    doc: dict = {kind: ISOTYPE if kind == "isotype" else PARATYPE}
    hid = cat.get("hid")
    doc.update(hid=hid if isinstance(hid, str) and HID_RE.match(hid) else None, epoch=epoch_for(cadence, ctx.now),
               cadence=cadence, sample=cat.get("sample") is True and kind == "isotype", identity=ident, shape=shape,
               offers=[offers[k] for k in sorted(offers, key=lambda k: (order[k[0]], k[1].lower(), k[1]))][:MAX_OFFERS],
               seeks=[seeks[k] for k in sorted(seeks, key=lambda k: (aim_order[k[0]], k[1].lower(), k[1]))],
               open_to=[open_to[k] for k in sorted(open_to, key=lambda k: (aim_order[k[0]], k[1].lower(), k[1]))],
               program=_program_ref(ctx))
    if kind == "paratype":
        doc.update(standing="third-party", submitter=None, of=(ident.get("domains") or [None])[0])
    stage = getattr(ctx, "stage", None)
    if stage is not None:
        write_atomic(stage / f"{kind}.cosm", mc.dump(plain(doc)).encode("utf-8"))
        write_atomic(stage / f"{kind}.json", canonical_json(doc))
    return Value("volume", doc)


@implements("band")
def band(ctx: Any, n: Value, **mods: Any) -> Value:
    """A number said as a word from a list, never the number (Comprise's bands; THYM.md 6.3)."""
    words = [str(w) for w in as_list(mods.get("as"))]
    if not words:
        raise MoveError("band needs its words: band <number> as [none, some]")
    value = n.plain()
    if not isinstance(value, int) or isinstance(value, bool):
        raise MoveError(f"band takes a number, not a {n.type}")
    if words == ["none", "some"]:
        w = "none" if value <= 0 else "some"
    else:
        w = words[min(max(value, 0) // 10, len(words) - 1)]
    return Value("word", w, origin={"band": words})


@implements("mark")
def mark(ctx: Any, x: Value, **mods: Any) -> Value:
    """An item, or a banded word, marked `verified` or `stated` (THYM.md 18)."""
    m = mods.get("as")
    if m not in ("verified", "stated"):
        raise MoveError(f"a marking is verified or stated, not {m}")
    if x.type == "word" or not isinstance(x.payload, dict):
        return Value(x.type, x.payload, origin={**(x.origin or {}), "marking": m})
    return Value("item", {**x.payload, "marking": m}, origin=x.origin)


@implements("withhold")
def withhold(ctx: Any, v: Value, **mods: Any) -> None:
    """Items left out of the projection without a trace (THYM.md 18): those of a volume that the `where` names, or
    the item given."""
    w = mods.get("where")
    if w is not None:
        rows = w.select(v)
    elif v.type in ("volume", "list", "fabula"):
        rows = members(v) or []
    else:
        rows = [v]
    ctx.withhold(rows)
    return None


# ---------------------------------------------------------------------------
# The target schema's rules as checks (THYM.md 7.3)
# ---------------------------------------------------------------------------

_NINETY = "no earlier release is known, so the band shown stands; the 90-day rule binds from the second release"


@check("banded")
def _banded(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """A number leaves only as a word from its declared list, and a band moves only after the value has stayed past the
    boundary for 90 days (Comprise's `band`). This round knows no earlier release, so the second half holds by
    default, and the why says so."""
    if output.type == "word":
        words = [str(w) for w in as_list(modifiers(node).get("as"))] or (output.origin or {}).get("band") or []
        if output.payload not in words:
            return False, f"{output.payload!r} is not a word of the band {words}"
        return True, _NINETY
    data = output.mapping() or {}
    shape = data.get("shape") if isinstance(data.get("shape"), dict) else {}
    for slot, allowed in SHAPE_SLOTS.items():
        if allowed and slot in shape and shape[slot] not in allowed:
            return False, f"shape.{slot} is {shape[slot]!r}, not a word of {', '.join(allowed)}"
    for slot, v in (getattr(ctx, "slots", None) or {}).items():
        words = (v.origin or {}).get("band") if isinstance(v, Value) else None
        if words and v.plain() not in words:
            return False, f"{slot}: {v.plain()!r} is not a word of its band {words}"
    return True, _NINETY


def _neither(inputs: dict, ctx: Any) -> int:
    h = next((v for v in inputs.values() if isinstance(v, Value) and v.type == "volume"), None)
    ids = {_id(r) for r in (members(h) or [])} if h is not None else set()
    emitted = {_id(v) for v in (getattr(ctx, "emitted", None) or []) if isinstance(v, Value)}
    return len(ids - emitted - set(getattr(ctx, "withheld", None) or {}))


@check("verified-derived")
def _verified_derived(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """`verified` only on what the schema derives (identity, shape, offers, markets); `stated` only on the subject's
    own words, its aims (comprise-isotype/0). On success the why counts what the program never mentioned: the items
    it neither emitted nor withheld, which default-deny left out."""
    nv = ns = 0
    derivable = DERIVABLE["comprise"]
    withheld = set(getattr(ctx, "withheld", None) or {})
    for v in getattr(ctx, "emitted", None) or []:
        if not isinstance(v, Value) or _id(v) in withheld:
            continue
        m, k = marking_of(v), _kind(v)
        if m == "verified" and k not in derivable:
            return False, f"{_id(v)} is marked verified, and the schema derives no {k}"
        if m == "stated" and k != "aim":
            return False, f"{_id(v)} is marked stated; stated is the subject's own words, its aims"
        nv += m == "verified"
        ns += m == "stated"
    slots = 0
    for slot, v in (getattr(ctx, "slots", None) or {}).items():
        if slot in SHAPE_SLOTS or slot in IDENTITY_SLOTS:
            if not isinstance(v, Value) or marking_of(v) != "verified":
                return False, f"{slot} is derived, and is not marked verified"
            slots += 1
    left = _neither(inputs, ctx)
    return True, (f"verified on {nv} item{'s' if nv != 1 else ''} and {slots} field{'s' if slots != 1 else ''}, "
                  f"stated on {ns} aim{'s' if ns != 1 else ''}; {left} item{'s' if left != 1 else ''} neither emitted "
                  "nor withheld were left out by default-deny")


@check("verified-only-where-derived")
def _verified_only(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """`mark ... as verified` only on an item whose MiniCOSM derives its kind (Comprise: the offer and market kinds,
    identity and shape), or on a word that fills a derived field (`emit employees: … marked verified`) or that a
    `band` made from the holotype."""
    m = modifiers(node).get("as") or marking_of(output)
    if m == "stated":
        return True, ""
    if m != "verified":
        return False, f"a marking is verified or stated, not {m}"
    if output.type == "word" or not isinstance(output.payload, dict):
        slot = (node or {}).get("slot")
        if slot in SHAPE_SLOTS or slot in IDENTITY_SLOTS or (output.origin or {}).get("band"):
            return True, ""
        return False, "a word is verified only where it fills a derived field, or where a band made it"
    mini, k = _minicosm(output), _kind(output)
    if k in DERIVABLE.get(mini, ()):
        return True, ""
    return False, f"{_id(output)}: {mini or 'its MiniCOSM'} does not derive a {k or 'kind'}, so it cannot be verified"


@check("standing-gate")
def _standing_gate(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """A release as the subject needs first-party standing, or `sample: true` (Comprise's `standing.py`); a paratype is
    the third-party kind, and passes by being one."""
    data = output.mapping() or {}
    if data.get("paratype"):
        return True, "a paratype speaks at third-party standing, never as the company"
    if data.get("sample") is True:
        return True, "a sample: its isotype says sample: true"
    standing = (getattr(ctx, "engines", None) or {}).get("standing")
    h = next((v for v in inputs.values() if isinstance(v, Value) and v.type == "volume"), None)
    if standing is not None:
        try:
            got = standing(h)
        except Exception as e:  # noqa: BLE001 - a standing that cannot be read is no standing
            return False, f"the standing could not be read: {e}"
        if got == "first-party":
            return True, ""
        return False, f"a release as the company needs first-party standing; the holotype stands {got}"
    return False, "a release as the company needs first-party standing; this holotype is not a sample, and no " \
                  "standing says first-party"


def _sorted_by(rows: list, key: Any) -> bool:
    return rows == sorted(rows, key=key)


@check("epoch")
def _epoch(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """The date shown is the epoch, never the day of an edit, and lists are sorted, so their order tells nothing
    (comprise-isotype/0)."""
    data = output.mapping() or {}
    cad = data.get("cadence")
    if cad not in CADENCES:
        return False, f"the cadence {cad!r} is not one of {', '.join(CADENCES)}"
    ep = data.get("epoch")
    if not isinstance(ep, str) or not EPOCH_RE[cad].match(ep):
        return False, f"the epoch {ep!r} is not a {cad} epoch"
    now = getattr(ctx, "now", None)
    if now is not None and ep != epoch_for(cad, now):
        return False, f"the epoch {ep} is not the one this run falls in ({epoch_for(cad, now)})"
    for k, v in data.items():
        if k == "epoch":
            continue
        for leaf in _leaves(v):
            if isinstance(leaf, (_dt.date, _dt.datetime)) or (isinstance(leaf, str) and _DATE.search(leaf)):
                return False, f"{k} shows a date ({leaf}); the epoch is the only date a projection shows"
    order = {x: i for i, x in enumerate(OFFER_KINDS)}
    aim = {x: i for i, x in enumerate(AIM_KINDS)}
    offers = [o for o in data.get("offers") or [] if isinstance(o, dict)]
    if not _sorted_by(offers, lambda o: (order.get(o.get("kind"), 99), str(o.get("name")).lower(), str(o.get("name")))):
        return False, "the offers are not sorted"
    for sec in ("seeks", "open_to"):
        rows = [a for a in data.get(sec) or [] if isinstance(a, dict)]
        if not _sorted_by(rows, lambda a: (aim.get(a.get("kind"), 99), str(a.get("summary")).lower(),
                                           str(a.get("summary")))):
            return False, f"{sec} is not sorted"
    ident = data.get("identity") if isinstance(data.get("identity"), dict) else {}
    if isinstance(ident.get("domains"), list) and ident["domains"] != sorted(ident["domains"]):
        return False, "identity.domains is not sorted"
    shape = data.get("shape") if isinstance(data.get("shape"), dict) else {}
    if isinstance(shape.get("markets"), list) and not _sorted_by(shape["markets"], lambda s: (str(s).lower(), str(s))):
        return False, "shape.markets is not sorted"
    return True, ""


def _leaves(v: Any):
    if isinstance(v, dict):
        for x in v.values():
            yield from _leaves(x)
    elif isinstance(v, list):
        for x in v:
            yield from _leaves(x)
    else:
        yield v


__all__ = ["band", "canonical_json", "epoch_for", "identity", "mark", "project", "withhold"]
