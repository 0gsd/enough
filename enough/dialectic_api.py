"""The dialectic's routes (0.6, the fabula round: pins P4.7; MacroCOSM OES 18.6; THYM 22; Ascribe 8): any volume's
questions listed, a value checked before it is sent, a sitting recorded, the answers settled, a format's bank raised on
a volume that has none yet, and a question asked again, under `/api/dialectic/`.

**One family of routes, by the volume's format.** The card on the page and the agent's tool are one card and one
tool, whatever volume they ask about; what differs is underneath, so the routes dispatch on the volume:

- **A single-file volume** (a text's fabula, a fabulac, a Canon volume, a document): the answers are written as an
  answers volume beside it, `<its name without .cosm>.answers-<YYYY-MM-DD-HHMM>.cosm` (THYM 22.2), and the volume itself
  is never written by the card. A fabula is settled by the Thym run `settle.thym` (`program settle-the-answers`: `f` the
  volume, `said` the answers volume), on the route chosen for it, one run per sitting, oldest first; its output
  replaces the volume all at once. Under rules (no model answering, agent-free on, or `mode: rules` asked) the run
  takes `settle`'s scaffold `direct`: what needs a model to read an item again waits, and the reply names it. Any
  other single-file volume has no `settle.thym` to run (it takes a fabula), so it is settled by the same moves' rules
  directly (`dialectic.record_answers_volume`, then `dialectic.settle`), and what needs a reading waits in the same way.
  Sittings recorded beside a volume and not yet settled are read in before anything is listed or checked, so a
  question answered in one is not put again and cannot be answered twice.
- **A holograph** (`oes: ascribe/1`, a folder whose catalog is `holograph.cosm`): Ascribe's own functions
  (`ascribe.queue`, `record_answers`, `settle_holograph`, `raise_bank`, `ask_again`), because Ascribe adds rules of its
  own: the holder alone answers (every session is `with: {to: holder, who: the holder}`), an answer that reads like
  personal data is refused in plain words and nothing of it is written, and the dialectic stays with the holder, so
  the answers are recorded into the holograph's own module D rather than beside it.

The plain functions are what the routes translate, and what the agent's tool calls (`enough/fabula_tools.py`).
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, HTTPException, Query, Request

from . import canon_tools as _canon_tools
from . import fabula_names as _fabula_names
from . import macrocosm as _macrocosm
from . import thym_api as _thym_api
from . import thym_host as _host
from .canon_derive import DeriveCancelled
from .thym import Refusal

log = logging.getLogger("enough.dialectic_api")

SETTLE_FILE = "settle.thym"
JOB_KIND = "dialectic"
#: The fields of a question a card shows, beside its words.
CARD_FIELDS = ("hint", "options", "options-open", "many", "range")
#: A question's states that stand (MacroCOSM OES 18.6.3).
ANSWERED = ("answered", "unknown", "declined")
#: The closed questions a listing carries (the newest; `closed_total` says how many there are).
CLOSED_SHOWN = 50
#: The server-sent event a recorded sitting or a landed settle sends (beside the jobs' `canon`).
EVENT = "dialectic"


class DialecticRouteError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _dl():
    from . import dialectic
    return dialectic


def _ascribe():
    from . import ascribe
    return ascribe


def _now(at: Any = None) -> dt.datetime:
    return _dl().now(at)


# ---------------------------------------------------------------------------
# The volume a request names
# ---------------------------------------------------------------------------

@dataclass
class Target:
    """The volume a request names. `kind` is `holograph` or `volume`; `path` the holograph's folder or the volume's
    file; `rel` how the app names it; `key` the claim a derivation, a build or another settle of it holds."""
    kind: str
    path: Path
    rel: str
    key: str
    is_fabula: bool = False

    @property
    def holograph(self) -> bool:
        return self.kind == "holograph"


def _rel(project_dir: Path, p: Path) -> str:
    return _thym_api.rel_of(project_dir, p) or p.name


def _is_holograph_folder(p: Path) -> bool:
    cat = p / "holograph.cosm"
    return p.is_dir() and not p.is_symlink() and cat.is_file() and \
        str(_host._head_of(cat).get("oes") or "").startswith("ascribe/")


def target(project_dir: Path, rel: str) -> Target:
    """The volume `rel` names: a holograph (its folder or its `holograph.cosm`); a single-file volume (`.cosm`); a
    folder's fabulac (the folder, or `<folder>.fabulac.cosm`); a text's fabula (the text: its twin, the one derived
    last). Refused in words: no path (400), nothing there (404), a text with no fabula yet (404), an answers volume
    (400: it is a sitting, not a volume to answer), a folder that is none of these (400)."""
    project_dir = Path(project_dir)
    raw = _canon_tools.tidy_rel(str(rel or ""))
    if not raw or raw in _canon_tools.STORE_PREFIXES:
        raise DialecticRouteError("missing path: name the volume whose questions to show")
    try:
        p = _canon_tools.resolve(project_dir, raw)
    except _canon_tools.TextTargetError as e:
        raise DialecticRouteError(str(e), getattr(e, "status", 400)) from None
    if p.is_symlink():
        raise DialecticRouteError(f"{raw} is a link; nothing is read through a link")
    if not p.exists():
        raise DialecticRouteError(f"no such file: {raw}", 404)
    if p.is_dir():
        if _is_holograph_folder(p):
            return Target("holograph", p, _rel(project_dir, p), str(p.resolve()))
        fab = _fabula_names.twin_path(p, "fabulac")
        if fab.is_file():
            return Target("volume", fab, _rel(project_dir, fab), str(p.resolve()), True)
        raise DialecticRouteError(f"{raw} is a folder with no volume to answer: a holograph, or a folder with its "
                                  "fabulac beside it")
    if p.name == "holograph.cosm" and _is_holograph_folder(p.parent):
        return Target("holograph", p.parent, _rel(project_dir, p.parent), str(p.parent.resolve()))
    if p.name.endswith(".cosm"):
        if _dl()._ANSWERS_NAME.match(p.name):
            raise DialecticRouteError(f"{p.name} is a sitting's answers, not a volume to answer: name the volume "
                                      "beside it")
        oes = str(_host._head_of(p).get("oes") or "")
        if not oes:
            raise DialecticRouteError(f"{p.name} declares no format, so it is not a volume the dialectic can answer")
        fab = oes.split("/")[0] in ("fabula", "emf")
        of_text = _fabula_names.text_of_twin(p) if fab else None
        folder = None
        if p.name.endswith(_fabula_names.suffix("fabulac")):
            folder = p.with_name(p.name[: -len(_fabula_names.suffix("fabulac"))])
        key = str((of_text or folder or p).resolve())
        return Target("volume", p, _rel(project_dir, p), key, fab)
    twin = _fabula_names.find_twin(p)
    if twin is None:
        raise DialecticRouteError(f"{raw} has no fabula yet: decompile it first, and its questions land with it", 404)
    return Target("volume", twin, _rel(project_dir, twin), str(p.resolve()), True)


# ---------------------------------------------------------------------------
# Sittings beside a volume, not yet settled
# ---------------------------------------------------------------------------

def sittings(t: Target) -> list[Path]:
    """The answers volumes beside a volume (its own name, the stamp), oldest first by name."""
    if t.holograph:
        return []
    dl = _dl()
    stem = t.path.name[: -len(".cosm")]
    found = [p for p in t.path.parent.glob(f"{stem}.answers-*.cosm")
             if p.is_file() and not p.is_symlink() and dl.is_answers_of(t.path, p)]
    return sorted(found, key=lambda p: p.name)


def _session_ids(led: Any) -> set[str]:
    return {str(s.get("id")) for s in led.sessions()}


def unsettled(t: Target, led: Any) -> list[tuple[Path, Any]]:
    """The sittings beside the volume whose session the volume does not hold yet, read as deltas, oldest first. A file
    that does not read is skipped and logged (it is not this page's to repair)."""
    dl = _dl()
    have = _session_ids(led)
    out = []
    for p in sittings(t):
        try:
            av = dl.read_answers_volume(p)
        except dl.DialecticError as e:
            log.warning("dialectic: %s is not read (%s)", p.name, e)
            continue
        if str(av.session.get("id")) in have:
            continue
        out.append((p, av))
    return out


def ledger(t: Target) -> tuple[Any, list[tuple[Path, Any]]]:
    """The volume's ledger with every unsettled sitting beside it read in (on a copy: nothing is written), and those
    sittings. For a holograph, Ascribe's ledger as it stands."""
    dl = _dl()
    if t.holograph:
        return _ascribe().Holograph(t.path).led, []
    try:
        base = dl.open_twin(t.path).ledger
    except dl.DialecticError as e:
        raise DialecticRouteError(str(e)) from None
    led = base.copy()
    waiting = unsettled(t, led)
    for p, av in list(waiting):
        try:
            dl.record_answers_volume(led, av)
        except dl.DialecticError as e:
            log.warning("dialectic: %s does not apply (%s)", p.name, e)
            waiting.remove((p, av))
    return led, waiting


# ---------------------------------------------------------------------------
# Listing: the cards
# ---------------------------------------------------------------------------

def _item_brief(led: Any, iid: str | None) -> dict | None:
    if not iid:
        return None
    it = led.item(iid)
    if not isinstance(it, dict):
        return None
    out = {"id": it.get("id")}
    for k in ("name", "summary"):
        v = it.get(k)
        if isinstance(v, str):
            out[k] = v
    return out


def card(led: Any, entry: dict, *, waiting_in: str | None = None) -> dict:
    """A question as the card shows it: `{id, form, about, asks, why, kind, to, state, raised, hint, options,
    options_open, many, range, item: {id, name, summary}, field, answers, last}`. `form` is `question` (a D:question
    item) or `pending` (a bare `{pending: …}` field no question is about yet: answered by its address)."""
    dl = _dl()
    q = led.question(entry["id"]) if entry.get("id") else None
    where = dl.resolve_about(led, entry.get("about"))
    out: dict[str, Any] = {
        "id": entry.get("id"), "form": entry.get("form") or ("question" if q else "pending"),
        "about": entry.get("about"), "asks": entry.get("asks"), "why": entry.get("why"),
        "kind": entry.get("kind") or "text", "to": entry.get("to"),
        "state": (q or {}).get("state", "open"), "raised": _macrocosm.jsonable((q or {}).get("raised")),
        "item": _item_brief(led, where.item_id), "field": where.field,
    }
    for k in CARD_FIELDS:
        v = (q or {}).get(k)
        out[k.replace("-", "_")] = _macrocosm.jsonable(v) if v is not None else None
    answers = (q or {}).get("answers") if isinstance((q or {}).get("answers"), list) else []
    out["answers"] = len(answers)
    if answers:
        last = answers[-1]
        out["last"] = {k: _macrocosm.jsonable(last.get(k)) for k in ("at", "says", "value", "declined") if k in last}
    out["candidate"] = candidate_of(led.item(where.item_id) if where.item_id else None)
    if waiting_in:
        out["waiting_in"] = waiting_in
    return out


def candidate_of(it: Any) -> dict | None:
    """Where a candidate came from, as far as the holograph records it: `{text, sha256, span, confidence, made}`, the
    text it was read from by name and digest (its `provenance.sources` entry `<name>#sha256:<digest>`), the span, the
    reading's confidence and the run that proposed it; a field the node does not hold is null. None for anything that
    is not a candidate (a node a reading proposed, `provenance: {mode: derived, state: pending}`). The words of the
    span are not recorded in a holograph, so they are not given."""
    if not isinstance(it, dict):
        return None
    prov = it.get("provenance")
    if not (isinstance(prov, dict) and prov.get("state") == "pending" and prov.get("mode") == "derived"):
        return None
    text = sha = None
    srcs = prov.get("sources") if isinstance(prov.get("sources"), list) else []
    src = next((s for s in srcs if isinstance(s, str) and s.strip()), None)
    if src is not None:
        name, sep, digest = src.partition("#sha256:")
        text, sha = (name or None), (digest or None) if sep else None
    conf = prov.get("confidence")
    return {"text": text, "sha256": sha, "span": _macrocosm.jsonable(it.get("span")),
            "confidence": conf if isinstance(conf, (int, float)) and not isinstance(conf, bool) else None,
            "made": _macrocosm.jsonable(it.get("made")) if isinstance(it.get("made"), dict) else None}


def _last_at(q: dict) -> str:
    answers = q.get("answers") if isinstance(q.get("answers"), list) else []
    last = answers[-1] if answers and isinstance(answers[-1], dict) else {}
    at = last.get("at")
    return str(_macrocosm.jsonable(at)) if at is not None else ""


def closed_questions(led: Any) -> list[dict]:
    """The questions "ask again" is for: settled ones (answered, unknown or declined, then settled) and every
    declined one, newest first by their last answer's `at` (written order breaks ties, the later first)."""
    rows = [(n, q) for n, q in enumerate(led.questions())
            if q.get("state") in ANSWERED and (q.get("settled") or q.get("state") == "declined")]
    rows.sort(key=lambda r: (_last_at(r[1]), r[0]), reverse=True)
    return [q for _n, q in rows]


def listing(project_dir: Path, rel: str) -> dict:
    """`GET /api/dialectic/questions`: `{path, format, holograph, flavour, open: [card], waiting: [card], settled,
    counters, counts, sittings: [{path, session, answered}], to}`. `open` is the queue, in order: a holograph's thinnest
    container first (Ascribe 8.2); any other volume's open questions as written, then its bare pendings (18.6.5).
    `waiting` holds the questions answered in a sitting not yet settled, and those answered and waiting for a model to
    read their item again."""
    dl = _dl()
    t = target(project_dir, rel)
    led, waiting = ledger(t)
    if t.holograph:
        rows = _ascribe().queue(t.path)
        opened = [card(led, {"form": "question", "id": q["id"], "about": q.get("about"), "asks": q.get("asks"),
                             "why": q.get("why"), "kind": q.get("kind"), "to": q.get("to")}) for q in rows]
    else:
        opened = [card(led, e) for e in dl.open_questions(led)]
    in_sitting: dict[str, str] = {}
    for p, av in waiting:
        for e in av.entries:
            if e.get("id"):
                in_sitting[str(e["id"])] = p.name
    after = []
    counts = {s: 0 for s in dl.STATES}
    settled = 0
    for q in led.questions():
        counts[q.get("state")] = counts.get(q.get("state"), 0) + 1
        if q.get("state") in ANSWERED:
            if q.get("settled"):
                settled += 1
            else:
                after.append(card(led, {"form": "question", "id": q["id"], "about": q.get("about"),
                                        "asks": q.get("asks"), "why": q.get("why"), "kind": q.get("kind"),
                                        "to": q.get("to")}, waiting_in=in_sitting.get(q["id"])))
    counters = [card(led, {"form": "question", "id": q["id"], "about": q.get("about"), "asks": q.get("asks"),
                           "why": q.get("why"), "kind": q.get("kind"), "to": q.get("to")})
                for q in led.questions() if q.get("why") == "counter" and q.get("state") == "open"]
    shut = closed_questions(led)
    closed = [card(led, {"form": "question", "id": q["id"], "about": q.get("about"), "asks": q.get("asks"),
                         "why": q.get("why"), "kind": q.get("kind"), "to": q.get("to")},
                   waiting_in=in_sitting.get(q["id"])) for q in shut[:CLOSED_SHOWN]]
    return {"path": t.rel, "format": f"{led.minicosm}/{led.major}" if led.minicosm else led.catalog.get("oes"),
            "holograph": t.holograph, "flavour": led.catalog.get("flavour") if t.is_fabula else None,
            "fabula": t.is_fabula, "open": opened, "waiting": after, "counters": counters,
            "closed": closed, "closed_total": len(shut),
            "counts": {**counts, "settled": settled, "open_pendings": sum(1 for c in opened if c["form"] == "pending")},
            "sittings": [{"path": _rel(project_dir, p), "session": av.session.get("id"),
                          "answered": [e.get("id") or e.get("about") for e in av.entries]} for p, av in waiting],
            "to": "holder" if t.holograph else dl.default_to(led),
            "sessions": len(led.sessions())}


# ---------------------------------------------------------------------------
# Checking a value, recording a sitting
# ---------------------------------------------------------------------------

def _spec_of(led: Any, question: str) -> tuple[dict, str | None]:
    """A question's shape (kind, options, options-open, many, range) and its id; an address (`<item>#<field>`) asked
    without a question item is text."""
    q = led.question(question)
    if q is None:
        if not str(question).startswith(_dl().Q_PREFIX) and ("#" in str(question) or ":" in str(question)):
            return {"kind": "text"}, None
        raise DialecticRouteError(f"{question} is not a question of this volume", 404)
    return {k: q[k] for k in ("kind", "options", "options-open", "many", "range") if k in q}, q["id"]


def check(project_dir: Path, rel: str, question: str, value: Any) -> dict:
    """`POST /api/dialectic/check`: `{ok, value, refusal}`: the value as it will be written, or the refusal's words
    (the shape's, or, for a holograph, Ascribe's personal-data refusal). Nothing is written."""
    dl = _dl()
    t = target(project_dir, rel)
    led, _ = ledger(t)
    spec, qid = _spec_of(led, str(question or ""))
    if t.holograph:
        a = _ascribe()
        h = a.Holograph(t.path)
        found = a.pii_in(value if isinstance(value, str) else str(value or ""), h.pseudonyms)
        if found:
            return {"ok": False, "value": None, "refusal": a.REFUSED_PII.format(what=", ".join(found))}
    try:
        v = dl.check_value(led, spec, value, qid=qid)
    except dl.AnswerRefused as e:
        return {"ok": False, "value": None, "refusal": str(e)}
    return {"ok": True, "value": _macrocosm.jsonable(v), "refusal": None}


def _answers(raw: Any) -> list[dict]:
    """A sitting's answers as the request gives them: `[{question, value?, says?, dont_know?, declined?, skip?,
    confidence?}]`. 400 in words otherwise."""
    if not isinstance(raw, list) or not raw:
        raise DialecticRouteError("answers is a list of {question, value or says, dont_know, declined, skip}")
    out = []
    for a in raw:
        if not isinstance(a, dict) or not isinstance(a.get("question"), str) or not a["question"].strip():
            raise DialecticRouteError("each answer names its question")
        keep = {k: a[k] for k in ("question", "says", "value", "confidence", "dont_know", "declined", "skip")
                if k in a and a[k] is not None}
        if "says" in keep and not isinstance(keep["says"], str):
            keep["says"] = str(keep["says"])
        out.append(keep)
    return out


def record(project_dir: Path, rel: str, answers: Any, *, through: str = "person", who: str | None = None,
           to: str | None = None, model: str | None = None, at: Any = None) -> dict:
    """`POST /api/dialectic/answers`: a sitting recorded. `{path, session, written, recorded: [{question, state}],
    skipped, refused: [{question, why}]}`. A single-file volume: an answers volume beside it (`written`), the volume
    untouched; a holograph: into the holograph's module D (`written` is the holograph). An answer that cannot be
    recorded is listed in `refused` with the words to show, and the rest are kept; a sitting with nothing recorded and
    nothing skipped writes nothing (422 with the refusals' words)."""
    dl = _dl()
    if through not in dl.THROUGH:
        raise DialecticRouteError(f"through is {' or '.join(dl.THROUGH)}, not {through!r}")
    items = _answers(answers)
    t = target(project_dir, rel)
    session: dict[str, Any] = {"through": through}
    if model and through == "agent":
        session["model"] = str(model)
    if t.holograph:
        rec = _ascribe().record_answers(t.path, items, session=session, at=at)
        out = _recorded(project_dir, rec, written=t.rel if (rec.recorded or rec.skipped) else None)
        out["path"] = t.rel
        if not rec.recorded and not rec.skipped:
            raise DialecticRouteError("nothing was recorded: " + "; ".join(f"{q}: {w}" for q, w in rec.refused), 422)
        return out
    led, _waiting = ledger(t)
    with_ = {"to": to or _first_to(led, items) or dl.default_to(led)}
    if who:
        with_["who"] = str(who)
    session["with"] = with_
    when = _now(at)
    try:
        av = dl.answers_delta(led, items, session=session, at=when, strict=False)
    except dl.DialecticError as e:
        raise DialecticRouteError(str(e)) from None
    rec = _recorded_of_delta(led, items, av, session, when)
    if not av.entries and not av.session.get("skipped"):
        raise DialecticRouteError("nothing was recorded: " + ("; ".join(f"{r['question']}: {r['why']}"
                                                                         for r in rec["refused"]) or "no answer"), 422)
    path = dl.answers_path(t.path, when)
    dl.write_atomic(path, dl.write_answers_volume(av))
    rec.update(path=t.rel, written=_rel(project_dir, path))
    return rec


def _first_to(led: Any, items: list[dict]) -> str | None:
    for a in items:
        q = led.question(a["question"])
        if q is not None and isinstance(q.get("to"), str):
            return q["to"]
    return None


def _recorded(project_dir: Path, rec: Any, *, written: str | None) -> dict:
    return {"session": rec.session, "written": written,
            "recorded": [{"question": ref, "state": state} for ref, state, _entry in rec.recorded],
            "skipped": list(rec.skipped), "refused": [{"question": q, "why": w} for q, w in rec.refused]}


def _state_of_entry(e: dict) -> str:
    """What an address entry of a sitting (`{about, answers}`, which carries no `state`) recorded, read from its last
    answer as `record` wrote it: `declined` (the answer says so), `unknown` (no value: "I don't know"), else
    `answered`."""
    answers = e.get("answers") if isinstance(e.get("answers"), list) else []
    last = answers[-1] if answers and isinstance(answers[-1], dict) else {}
    if last.get("declined"):
        return "declined"
    if "value" in last and last.get("value") is None:
        return "unknown"
    return "answered"


def _recorded_of_delta(led: Any, items: list[dict], av: Any, session: dict, when: Any) -> dict:
    """What a sitting written as an answers volume recorded, refused and skipped: the delta's entries and session,
    and the refusals `record` gives on a copy (strict off, so the rest are kept)."""
    dl = _dl()
    probe = dl.record(led.copy(), items, session={**session, "id": av.session.get("id")}, at=when)
    return {"session": av.session.get("id"),
            "recorded": [{"question": e.get("id") or e.get("about"), "state": e.get("state") or _state_of_entry(e)}
                         for e in av.entries],
            "skipped": list(av.session.get("skipped") or []),
            "refused": [{"question": q, "why": w} for q, w in probe.refused]}


# ---------------------------------------------------------------------------
# Raising a bank, asking again
# ---------------------------------------------------------------------------

def _by_source(questions: list[dict]) -> dict[str, int]:
    """How many questions each bank entry (`raised.from`) or rule (`missing`, one per open field; `unsure`, one per
    unsure item) raised."""
    out: dict[str, int] = {}
    for q in questions:
        raised = q.get("raised") if isinstance(q.get("raised"), dict) else {}
        key = str(raised.get("from")) if raised.get("by") == "bank" and raised.get("from") else \
            str(q.get("why") or raised.get("from") or "rule")
        out[key] = out.get(key, 0) + 1
    return out


def raise_bank(project_dir: Path, rel: str, *, at: Any = None, dry: bool = False) -> dict:
    """`POST /api/dialectic/raise`: the format's bank (and the core's rule questions: one per pending field, one per
    unsure item) raised on a volume that has no questions yet, by rules, and landed in it. 409 when it has some.
    `dry`: raised the same way and landed nowhere, nothing written: `{path, count, by: {<bank entry or rule>: n},
    dry: true}`, so a card can say how many it would ask."""
    dl = _dl()
    t = target(project_dir, rel)
    if t.holograph:
        if _ascribe().Holograph(t.path).led.questions():
            raise DialecticRouteError("this holograph has its questions already; ask one again, or settle the "
                                      "answers", 409)
        raised = _ascribe().raise_bank(t.path, at=at, dry=dry)
        if dry:
            return {"path": t.rel, "count": len(raised), "by": _by_source(raised), "dry": True}
        return {"path": t.rel, "raised": [q.get("id") for q in raised], "count": len(raised)}
    twin = dl.open_twin(t.path)
    if twin.ledger.questions():
        raise DialecticRouteError(f"{t.path.name} has its questions already; ask one again, or settle the answers",
                                  409)
    if dry:
        r = dl.raise_questions(twin.ledger.copy(), rules=True, at=at)
        return {"path": t.rel, "count": len(r.questions), "by": _by_source(r.questions), "dry": True}
    r = dl.ask_by_bank(twin, rules=True, at=at)
    if r.questions:
        twin.save()
    return {"path": t.rel, "raised": [q.get("id") for q in r.questions], "count": len(r.questions),
            "skipped": [{"source": str(s), "why": w} for s, w in r.skipped]}


def ask_again(project_dir: Path, rel: str, question: str) -> dict:
    """`POST /api/dialectic/ask-again`: a question back to open, its answers kept (MacroCOSM OES 18.6.3, "any →
    open"); for a holograph a declined bank entry too (Ascribe 8.5: only when the holder asks). A question answered in
    a sitting not yet settled is refused (409): settle that sitting first."""
    dl = _dl()
    t = target(project_dir, rel)
    if t.holograph:
        try:
            q = _ascribe().ask_again(t.path, question)
        except (dl.DialecticError, _ascribe().AscribeError) as e:
            raise DialecticRouteError(str(e), 404 if "not a question" in str(e) else 400) from None
        return {"path": t.rel, "question": q.get("id"), "state": q.get("state")}
    led, waiting = ledger(t)
    for p, av in waiting:
        if any(e.get("id") == question or str(e.get("id", "")).endswith(f"/{question}") for e in av.entries):
            raise DialecticRouteError(f"{question} is answered in {p.name}, which is not settled yet; settle it "
                                      "first", 409)
    twin = dl.open_twin(t.path)
    try:
        q = dl.reask(twin.ledger, question)
    except dl.DialecticError as e:
        raise DialecticRouteError(str(e), 404) from None
    twin.save()
    return {"path": t.rel, "question": q.get("id"), "state": q.get("state")}


# ---------------------------------------------------------------------------
# Settling
# ---------------------------------------------------------------------------

def _after(led: Any, before_counters: set[str]) -> dict:
    """What a settle leaves to show: the counters it raised (to put on the card), and the answers still unsettled,
    waiting for a model to read their item again."""
    counters = [q["id"] for q in led.questions()
                if q.get("why") == "counter" and q.get("state") == "open" and q["id"] not in before_counters]
    waiting = [{"question": q["id"], "about": q.get("about")} for q in led.questions()
               if q.get("state") in ANSWERED and not q.get("settled")]
    settled = sum(1 for q in led.questions() if q.get("settled"))
    return {"counters": counters, "waiting": waiting, "settled_total": settled}


def settle_rules(project_dir: Path, t: Target, *, at: Any = None) -> dict:
    """A single-file volume that is not a fabula, or a holograph, settled by rules, at once (no model reads an item
    again: what needs it waits, and the reply says which)."""
    dl = _dl()
    if t.holograph:
        a = _ascribe()
        led0 = a.Holograph(t.path).led
        before = {q["id"] for q in led0.questions() if q.get("why") == "counter"}
        feed = None
        try:
            feed = _host._feed()
        except Exception:  # noqa: BLE001 - FEED is a nicety for form discovery
            feed = None
        hs = a.settle_holograph(t.path, feed=feed, at=at)
        led = a.Holograph(t.path).led
        out = _after(led, before)
        out.update(path=t.rel, settled=[q for q, _w in hs.settled], follow_ups=[f for _q, f in hs.follow_ups],
                   needs_reading=[{"question": q, "about": ab, "because": b} for q, ab, b in hs.needs_reading],
                   sittings=[], runs=[], mode="rules")
        return out
    twin = dl.open_twin(t.path)
    before = {q["id"] for q in twin.ledger.questions() if q.get("why") == "counter"}
    used = []
    for p, av in unsettled(t, twin.ledger):
        dl.record_answers_volume(twin.ledger, av)
        used.append(_rel(project_dir, p))
    s = dl.settle(twin.ledger, at=at)
    twin.save()
    out = _after(twin.ledger, before)
    out.update(path=t.rel, settled=[q for q, _w in s.settled],
               needs_reading=[{"question": q, "about": ab, "because": b} for q, ab, b in s.needs_reading],
               sittings=used, runs=[], mode="rules")
    return out


def settle_fabula(project_dir: Path, t: Target, *, mode: str, why: str = "", route: str = "local",
                  model: str | None = None, calls: int | None = None, llm_url: str | None = None,
                  scaffolds: bool = False, complete: Callable | None = None,
                  runtime: Callable[..., dict] | None = None, should_stop: Callable[[], bool] | None = None,
                  progress: Callable[[dict], Any] | None = None, now: dt.datetime | None = None) -> dict:
    """A fabula's sittings settled by `settle.thym`, one run per sitting, oldest first, each landing the settled
    fabula over the volume all at once (blocking: the job's work). In rules the run takes `settle`'s scaffold
    (`direct`), and what needs a model waits. Returns `{path, runs, sittings, settled, counters, waiting, mode}`;
    RuntimeError in the refusal's words when a run does not land (the sittings before it stay settled)."""
    from .thym import run as _run
    from .thym.values import digest_path
    dl = _dl()
    prog = _host.SHIPPED_PROGRAMS / SETTLE_FILE
    checked = _thym_api._checked(prog)
    if isinstance(checked, Refusal):
        raise RuntimeError(f"settle.thym does not compile: {checked}")
    base = dl.open_twin(t.path).ledger
    before = {q["id"] for q in base.questions() if q.get("why") == "counter"}
    todo = unsettled(t, base)
    use_model = mode == "model" and not scaffolds
    runs: list[dict] = []
    used: list[str] = []
    for n, (p, _av) in enumerate(todo, 1):
        if should_stop is not None and should_stop():
            raise DeriveCancelled(f"cancelled; {len(runs)} of {len(todo)} sittings settled")
        rows = [{"name": "f", "type": "fabula", "path": str(t.path), "sha256": digest_path(t.path)},
                {"name": "said", "type": "volume", "path": str(p), "sha256": digest_path(p)}]
        info = None
        if use_model:
            plan, info = _host.plan_for(checked, rows, route=route, model=model, llm_url=llm_url,
                                        inputs_root=project_dir)
        else:
            from .thym import plan as _plan
            plan = _plan.plan(checked, rows, inputs_root=project_dir)
        if isinstance(plan, Refusal):
            raise RuntimeError(f"{p.name} was not settled ({plan.check}): {plan.message}")
        if use_model:
            r = _host.route_refusal(plan, info, calls=calls, ceiling="calls", program=prog)
            if r is not None:
                raise RuntimeError(f"{p.name} was not settled ({r.check}): {r.message}")
        if progress is not None:
            progress({"phase": "settling", "chunk": n, "chunks": len(todo), "message": f"settling {p.name}"})
        if runtime is not None:
            kw = runtime("settle", plan, info, "model" if use_model else "rules", not use_model, prog)
        else:
            kw = _thym_api.runtime(project_dir, mode="model" if use_model else "rules", why=why,
                                   scaffolds=not use_model, complete=complete, n_ctx=(info or {}).get("window"),
                                   route=route, model=model, calls=calls, info=info, program=prog)
        tr = _run.run(plan, inputs_root=project_dir, program=prog, should_stop=should_stop,
                      **({"now": now} if now is not None else {}), **kw)
        if isinstance(tr, Refusal):
            raise RuntimeError(f"{p.name} was not settled ({tr.check}): {tr.message}")
        if not tr.landed:
            r = tr.refusal
            if r is not None and r.check == "cancelled":
                raise DeriveCancelled(f"cancelled; {len(runs)} of {len(todo)} sittings settled")
            raise RuntimeError(f"{p.name} was not settled ({r.check}): {r.message}" if r else
                               f"{p.name} was not settled")
        out = Path(tr.outputs["g"])
        dl.write_atomic(t.path, out.read_bytes().decode("utf-8"))
        runs.append({"run": tr.run_id, "trace": str(tr.path), "sitting": _rel(project_dir, p)})
        used.append(_rel(project_dir, p))
    led = dl.open_twin(t.path).ledger
    res = _after(led, before)
    res.update(path=t.rel, runs=runs, sittings=used, mode="model" if use_model else "rules",
               settled=[q["id"] for q in led.questions() if q.get("settled")])
    return res


# ---------------------------------------------------------------------------
# A holograph's isograph: the holder's program, run through Thym (`project h as isograph`), then the release
# ---------------------------------------------------------------------------

def isograph(project_dir: Path, rel: str, program: str, *, now: dt.datetime | None = None) -> dict:
    """`POST /api/ascribe/isograph`: the holder's program (its one input a volume, its output `project h as
    isograph`) run on the holograph by rules (THYM 6.3; Ascribe 14.1: an isograph is computed by rules), the release
    recorded in the holograph's `releases:` (Ascribe 13: before anything leaves; `trace: {run, sha256}` of the run's
    trace), then the isograph written beside the holograph as `<holograph>.isograph-<epoch>.json`. Returns `{path,
    isograph, release, run, trace}`. Refused in words: not a holograph, no such program, a program that asks a model
    or takes anything but the holograph, a run that does not land (its refusal), a second isograph in one epoch."""
    import hashlib
    from .thym import plan as _plan
    from .thym import run as _run
    from .thym.values import digest_path
    a = _ascribe()
    t = target(project_dir, rel)
    if not t.holograph:
        raise DialecticRouteError(f"{t.rel} is not a holograph; an isograph is a holograph's public projection")
    prog = _host.find_program(str(program or "").strip(), project_dir) if str(program or "").strip() else None
    if prog is None:
        raise DialecticRouteError(f"no program {program!r}: name the holder's program, a .thym file whose output is "
                                  "project h as isograph", 404)
    checked = _thym_api._checked(prog)
    if isinstance(checked, Refusal):
        raise DialecticRouteError(f"{prog.name} does not compile: {checked.message}"
                                  + (f" (line {checked.line})" if checked.line else ""))
    block = _thym_api._block(checked)
    takes = list(block.takes) if block is not None else []
    if len(takes) != 1 or takes[0].type != "volume":
        raise DialecticRouteError(f"{prog.name} takes {', '.join(f'{p.name}: {p.type}' for p in takes) or 'nothing'};"
                                  " an isograph's program takes the holograph alone, as a volume")
    rows = [{"name": takes[0].name, "type": "volume", "path": str(t.path), "sha256": digest_path(t.path)}]
    plan = _plan.plan(checked, rows, inputs_root=project_dir)
    if isinstance(plan, Refusal):
        raise DialecticRouteError(f"{prog.name} does not plan: {plan.message}")
    said = _host.asks_said(plan, route="local", program=prog)
    if said is not None:
        raise DialecticRouteError(f"{said[0]}; an isograph is computed by rules, and no model reads a holograph for "
                                  "it", 409)
    kw = _thym_api.runtime(project_dir, mode="rules", why="", scaffolds=False, complete=None, n_ctx=None)
    tr = _run.run(plan, inputs_root=project_dir, program=prog, **({"now": now} if now is not None else {}), **kw)
    if isinstance(tr, Refusal):
        raise DialecticRouteError(tr.message, 409)
    if not tr.landed:
        r = tr.refusal
        raise DialecticRouteError(f"the isograph was not made ({r.check}): {r.message}" if r else
                                  "the isograph was not made", 409)
    staged = tr.dir / "outputs" / "isograph.json"
    if not staged.is_file():
        raise DialecticRouteError(f"{prog.name} landed no isograph: its output is not project h as isograph", 409)
    data = staged.read_bytes()
    doc = json.loads(data)
    value = next((v for v in tr.values.values() if isinstance(getattr(v, "origin", None), dict)
                  and "items" in v.origin), None)
    items = sorted(value.origin["items"]) if value is not None else []
    trace_sha = hashlib.sha256(tr.path.read_bytes()).hexdigest()
    try:
        record = a.release_record(epoch=doc["epoch"], as_="isograph", program=doc["program"],
                                  trace={"run": tr.run_id, "sha256": trace_sha},
                                  sha256=hashlib.sha256(data).hexdigest(), items=items, at=now)
        a.append_release(t.path, record)
    except a.AscribeError as e:
        raise DialecticRouteError(str(e), 409) from None
    dst = t.path.parent / f"{t.path.name}.isograph-{doc['epoch']}.json"
    dl = _dl()
    dl.write_atomic(dst, data.decode("utf-8"))
    return {"path": t.rel, "isograph": _rel(project_dir, dst), "release": _macrocosm.jsonable(record),
            "run": tr.run_id, "trace": str(tr.path)}


# ---------------------------------------------------------------------------
# The router
# ---------------------------------------------------------------------------

def notify(emit: Callable[[str, dict], None] | None, path: str, session: Any, what: str) -> None:
    """The `dialectic` event (beside the jobs' `canon`, on the same stream): `{path, session, what: recorded |
    settled}`, so a card open in another tab reads the volume again. Never fails what it reports."""
    if emit is None:
        return
    try:
        emit(EVENT, {"path": path, "session": session, "what": what})
    except Exception:  # noqa: BLE001 - an event is a nicety; the write has landed
        log.exception("dialectic event failed")


def _http(e: DialecticRouteError) -> HTTPException:
    return HTTPException(e.status, str(e))


def build_router(*, project_dir: Path, llm_url: str | None, jobs: Any,
                 canon_mode: Callable[..., Awaitable[tuple[str, str]]], start_job: Callable[..., dict],
                 model_complete: Callable[..., Any], catalog_after: Callable[[str], None],
                 emit: Callable[[str, dict], None] | None = None) -> APIRouter:
    router = APIRouter()
    project_dir = Path(project_dir)

    def said(path: str, session: Any, what: str) -> None:
        notify(emit, path, session, what)

    async def body_of(request: Request) -> dict:
        try:
            body = await request.json()
        except ValueError:
            body = None
        return body if isinstance(body, dict) else {}

    def held(t: Target, fn: Callable[[], Any]) -> Any:
        """A write to a volume, under its claim: 409 while a derivation, a build or a settle of it runs."""
        try:
            with jobs.holding(t.key, t.rel):
                return fn()
        except DialecticRouteError:
            raise
        except Exception as e:  # noqa: BLE001 - CanonJobError (409), DialecticError, AscribeError: said in words
            status = getattr(e, "status", None)
            if status:
                raise DialecticRouteError(str(e), status) from None
            from . import dialectic as dl
            from . import ascribe as a
            if isinstance(e, (dl.DialecticError, a.AscribeError)):
                raise DialecticRouteError(str(e)) from None
            raise

    async def run(fn: Callable[[], Any]) -> Any:
        try:
            return await asyncio.to_thread(fn)
        except DialecticRouteError as e:
            raise _http(e) from None

    @router.get("/api/dialectic/questions")
    async def dialectic_questions(path: str = Query(...)) -> dict:
        return await run(lambda: listing(project_dir, path))

    @router.post("/api/dialectic/check")
    async def dialectic_check(request: Request) -> dict:
        body = await body_of(request)
        return await run(lambda: check(project_dir, str(body.get("path") or ""), str(body.get("question") or ""),
                                       body.get("value")))

    @router.post("/api/dialectic/answers")
    async def dialectic_answers(request: Request) -> dict:
        body = await body_of(request)

        def go() -> dict:
            t = target(project_dir, str(body.get("path") or ""))
            out = held(t, lambda: record(project_dir, str(body.get("path") or ""), body.get("answers"),
                                         through=str(body.get("through") or "person"), who=body.get("who"),
                                         to=body.get("to"), model=body.get("model")))
            if out.get("recorded") or out.get("skipped"):
                said(out.get("path") or t.rel, out.get("session"), "recorded")
            return out
        return await run(go)

    @router.post("/api/dialectic/raise")
    async def dialectic_raise(request: Request) -> dict:
        body = await body_of(request)

        dry = body.get("dry")
        if dry is not None and not isinstance(dry, bool):
            raise HTTPException(400, f"dry is true or false, not {dry!r}")

        def go() -> dict:
            t = target(project_dir, str(body.get("path") or ""))
            if dry:
                return raise_bank(project_dir, str(body.get("path") or ""), dry=True)
            out = held(t, lambda: raise_bank(project_dir, str(body.get("path") or "")))
            catalog_after(t.rel)
            return out
        return await run(go)

    @router.post("/api/dialectic/ask-again")
    async def dialectic_ask_again(request: Request) -> dict:
        body = await body_of(request)
        q = str(body.get("question") or "").strip()
        if not q:
            raise HTTPException(400, "name the question to ask again")

        def go() -> dict:
            t = target(project_dir, str(body.get("path") or ""))
            return held(t, lambda: ask_again(project_dir, str(body.get("path") or ""), q))
        return await run(go)

    @router.post("/api/dialectic/settle")
    async def dialectic_settle(request: Request) -> dict:
        """The answers settled into the volume, as a job (`{job}`); its result `{path, settled, counters, waiting,
        needs_reading?, runs, sittings, mode}`. A fabula: `settle.thym` on the chosen route; anything else: by rules
        at once (a finished job)."""
        return await start_settle(await body_of(request))

    async def start_settle(body: dict) -> dict:
        try:
            t = await asyncio.to_thread(target, project_dir, str(body.get("path") or ""))
        except DialecticRouteError as e:
            raise _http(e) from None
        if not t.is_fabula or t.holograph:
            def at_once() -> dict:
                return held(t, lambda: settle_rules(project_dir, t))
            result = await run(at_once)
            catalog_after(t.rel)
            said(t.rel, None, "settled")
            n = len(result.get("settled") or [])
            msg = f"settled {n} answer{'s' if n != 1 else ''} into {t.path.name}"
            if result.get("waiting"):
                msg += f"; {len(result['waiting'])} wait for a model to read their item again"
            result["message"] = msg
            return {"job": jobs.record(kind=JOB_KIND, path=t.rel, mode="rules", result=result, message=msg)}
        raw = str(body.get("route") or "local").strip().lower()
        model = None
        if raw.startswith("cloud:"):
            raw, model = "cloud", raw[len("cloud:"):] or None
        if raw not in _host.ROUTES:
            raise HTTPException(400, f"route is local or cloud (or cloud:<model id>), not {raw!r}")
        route = raw
        model = model or (str(body.get("model")).strip() or None if body.get("model") else None)
        calls = body.get("calls")
        if calls is not None and (isinstance(calls, bool) or not isinstance(calls, int) or calls < 1):
            raise HTTPException(400, f"calls is a ceiling of at least 1 model call, not {calls!r}")
        want = str(body.get("mode") or "auto").strip().lower()
        if want not in ("auto", "model", "rules"):
            raise HTTPException(400, "mode is model, rules, or left out")
        led, waiting = await run(lambda: ledger(t))
        if not waiting:
            raise HTTPException(409, f"nothing to settle: no sitting beside {t.path.name} waits (answer a question "
                                     "first)")
        if want == "rules":
            mode, why, scaffolds = "rules", "asked", True
        else:
            try:
                mode, why = await canon_mode(route)
            except TypeError:
                mode, why = await canon_mode()
            scaffolds = mode != "model"
            if want == "model" and mode != "model":
                raise HTTPException(409, f"no model is running ({why})")
        complete = None
        if mode == "model" and not scaffolds:
            from . import llm as _llm
            complete = (model_complete if route == "local" and _llm._current_slot() != "opro-api"
                        else _host.route_complete(route, model=model, llm_url=llm_url, project_dir=project_dir))

        def work(ctx: Any) -> dict:
            out = settle_fabula(project_dir, t, mode=mode, why=why, route=route, model=model, calls=calls,
                                llm_url=llm_url, scaffolds=scaffolds, complete=complete,
                                should_stop=ctx.should_stop, progress=lambda f: ctx.progress(f))
            catalog_after(t.rel)
            if out.get("runs"):
                said(t.rel, None, "settled")
            n = len(out["runs"])
            msg = f"settled {n} sitting{'s' if n != 1 else ''} into {t.path.name}"
            if out.get("waiting"):
                msg += (f"; {len(out['waiting'])} answer{'s' if len(out['waiting']) != 1 else ''} wait for a model "
                        "to read their item again")
            out["message"] = msg
            return out

        kw = {"route": route if mode == "model" else None} if _host._accepts(start_job, {"route": route}) else {}
        return start_job(kind=JOB_KIND, path=t.rel, mode=mode, why=why if why != "asked" else "",
                         work=work, key=t.key, doing=f"settling the answers into {t.path.name}"
                         + (" on the cloud" if mode == "model" and route == "cloud" else ""), **kw)

    @router.post("/api/ascribe/isograph")
    async def ascribe_isograph(request: Request) -> dict:
        """A holograph's isograph, by the holder's program: `{path, program}` → `{path, isograph, release, run,
        trace}` (synchronous: a rules run)."""
        body = await body_of(request)

        def go() -> dict:
            t = target(project_dir, str(body.get("path") or ""))
            out = held(t, lambda: isograph(project_dir, str(body.get("path") or ""), str(body.get("program") or "")))
            catalog_after(t.rel)
            return out
        return await run(go)

    router.start_settle = start_settle          # type: ignore[attr-defined]  (the agent's tool settles through it)
    return router


__all__ = ["DialecticRouteError", "Target", "ask_again", "build_router", "candidate_of", "card", "check",
           "closed_questions", "isograph", "ledger", "listing", "notify", "raise_bank", "record", "settle_fabula",
           "settle_rules", "sittings", "target", "unsettled"]
