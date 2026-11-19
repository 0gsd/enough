"""The scaffold's check, as one job (0.8, E5; pins 6 and 11; survey 6.11).

A locked scaffold is read for spelling, grammar and truth, and what is found lands beside it as findings: comments
with a fix attached (`composure.record_check`), each with its box, the quoted span, the kind, the fix and a status.
The check never changes the person's words; the person accepts a fix or declines it (`composure.answer_finding`).

**Two passes.**

- *Rules* (always, agent-free included): FEED (`dictionary.lookup_many`) is asked about every word of every written
  text box. A word FEED does not know is flagged as a spelling finding with no fix: FEED only flags, and no
  suggestion is invented by rule. Text in a language other than English is marked "not checked for spelling" (a
  finding that cannot be checked), once per box; so is a box most of whose words FEED does not know. When FEED is not
  built on this machine, spelling is recorded as not checked rather than every word being flagged.
- *Model* (when a model answers): each written text box is read under a contract (`CONTRACT`). It proposes a fix for
  each word FEED flagged (or says the word is right, which leaves the flag without a fix), flags grammar with a fix
  to the quoted span, and lists every claim of fact with a verdict: `holds`, `wrong` (with a fix when it has one) or
  `cannot be checked`. A claim that cannot be checked is marked so, never passed; an answer that cannot be read
  marks the whole box's truth as not checked, never as passed.

Agent-free (or no model answering) runs the rules pass and says so: the check's record names grammar and truth as
not checked, and no claim is passed. A `cannot be checked` finding is final: the check never changes it.

The job is a CanonJob of kind `scaffold`, keyed by the composure, started from the composure routes
(`composure_api.build_scaffold_router`) like the fabulap's build. Its result: `{path, version, mode, passes,
not_checked, counts, added, findings, message}`.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any, Callable

from . import composure as C
from .canon_derive import DeriveCancelled

JOB_KIND = "scaffold"
#: The languages FEED checks spelling in.
SPELLING_LANGS = ("en",)
#: A box with at least this many words, more than half of them unknown to FEED, is marked "not checked for
#: spelling" (most likely another language) instead of having every word flagged.
FOREIGN_MIN_WORDS = 6
FOREIGN_SHARE = 0.5
#: The most of a box's text one model call reads.
MODEL_CHARS = 6000
MODEL_MAX_TOKENS = 1500

KnownFn = Callable[[set[str]], "set[str] | None"]
CompleteFn = Callable[..., tuple[str, dict[str, Any]]]


class CheckError(Exception):
    """A refusal with the HTTP status the route answers with."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# What is checked
# ---------------------------------------------------------------------------

def target_of(comp_path: Path) -> C.Composure:
    """The composure to check: a scaffold, locked. A check reads finished words, so an open scaffold is refused."""
    if not comp_path.is_file():
        raise CheckError(f"no composure at {comp_path.name}", status=404)
    comp = C.load(comp_path)
    if not C.is_scaffold(comp):
        raise CheckError(f"{comp_path.name} is not a scaffold, so there is nothing to check.")
    if not C.scaffold_locked(comp):
        raise CheckError("the check reads a locked scaffold: lock it first, then check it.", status=409)
    return comp


def written_boxes(comp: C.Composure) -> list[tuple[C.Module, str]]:
    """The text boxes with words in them, in reading order, each with its plain text (`composure.box_text`)."""
    view = C.scaffold_view(comp) or {"boxes": {}, "loose": []}
    out: list[tuple[C.Module, str]] = []
    for bid in [b for ids in view["boxes"].values() for b in ids] + list(view["loose"]):
        m = comp.module(bid)
        if m is None or m.type != C.BOX or (m.kind or "text") != "text":
            continue
        text = C.box_text(m)
        if text.strip():
            out.append((m, text))
    return out


def is_english(lang: str | None) -> bool:
    return (lang or "en").strip().lower().split("-")[0] in SPELLING_LANGS


# ---------------------------------------------------------------------------
# The rules pass: FEED flags the words it does not know
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"[A-Za-zÀ-ɏ](?:[A-Za-zÀ-ɏ'’-]*[A-Za-zÀ-ɏ])?")
_SKIP_RE = re.compile(r"\S*(?:://|www\.|@)\S*")
_CONTRACTIONS = ("n't", "'re", "'ve", "'ll", "'d", "'m", "'s")


def words_of(text: str) -> list[tuple[int, str]]:
    """The words to look up, with where each starts. Left out: anything inside a web address or an email, a word in
    capitals (an acronym), and a capitalised word that does not begin a sentence (most likely a name: FEED does not
    hold names, and flagging every one would bury the real slips)."""
    skip = [(m.start(), m.end()) for m in _SKIP_RE.finditer(text)]
    out: list[tuple[int, str]] = []
    for m in _WORD_RE.finditer(text):
        w, at = m.group(0), m.start()
        if any(a <= at < b for a, b in skip):
            continue
        letters = [c for c in w if c.isalpha()]
        if len(letters) > 1 and all(c.isupper() for c in letters):
            continue
        if w[0].isupper():
            before = text[:at].rstrip()
            if before and before[-1] not in ".!?:\n\"“(":
                continue
        out.append((at, w))
    return out


def feed_known(words: set[str]) -> set[str] | None:
    """The words FEED knows, from one `lookup_many`; None when FEED cannot be read here (not built, or broken), so
    the check says spelling was not checked instead of flagging everything."""
    from . import dictionary as D
    probe = "the"
    try:
        found = D.lookup_many(list(words) + [probe])
    except Exception:  # noqa: BLE001 - lookup_many never raises; belt and braces
        return None
    if found.get(probe) is None:
        return None
    known: set[str] = set()
    for w in words:
        cands = D.normalize(w)
        if cands and found.get(cands[0]) is not None:
            known.add(w)
    return known


def _lookup_forms(word: str) -> list[str]:
    """The forms of a word worth asking about: the word, its parts across a hyphen, the word without a contraction."""
    w = word.replace("’", "'")
    forms = [w]
    low = w.lower()
    for suf in _CONTRACTIONS:
        if low.endswith(suf) and len(w) > len(suf) + 1:
            forms.append(w[: -len(suf)])
    if "-" in w:
        forms += [p for p in w.split("-") if p]
    return forms


def _context(text: str, at: int, quote: str) -> tuple[str, str]:
    """A prefix and suffix that tell this place apart, when the quote stands in more than one."""
    if text.count(quote) <= 1:
        return "", ""
    return text[max(0, at - 20):at], text[at + len(quote):at + len(quote) + 20]


def rules_pass(comp: C.Composure, *, known: KnownFn | None = None,
               lang: str | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Spelling by FEED. Returns the findings and what the pass could not do (`{"not_checked": {...}}`)."""
    version = (C.scaffold_view(comp) or {}).get("version", 1)
    lang = lang or comp.lang or "en"
    boxes = written_boxes(comp)
    findings: list[dict[str, Any]] = []
    notes: dict[str, Any] = {"not_checked": {}, "unknown": 0}
    if not boxes:
        return findings, notes
    if not is_english(lang):
        for m, _text in boxes:
            findings.append({"box": m.id, "kind": "spelling", "quote": "", "fix": None,
                             "why": f"not checked for spelling: the text is in {lang}, and FEED is English",
                             "status": C.CANNOT, "version": version, "pass": "rules"})
        return findings, notes
    per_box = [(m, text, words_of(text)) for m, text in boxes]
    asked: set[str] = set()
    for _m, _t, ws in per_box:
        for _at, w in ws:
            asked.update(_lookup_forms(w))
    knows = (known or feed_known)(asked)
    if knows is None:
        notes["not_checked"]["spelling"] = "FEED is not built on this machine, so no word was looked up"
        return findings, notes
    for m, text, ws in per_box:
        unknown = [(at, w) for at, w in ws if not any(f in knows for f in _lookup_forms(w))]
        if len(ws) >= FOREIGN_MIN_WORDS and len(unknown) > FOREIGN_SHARE * len(ws):
            findings.append({"box": m.id, "kind": "spelling", "quote": "", "fix": None,
                             "why": "not checked for spelling: most of its words are not English words FEED knows",
                             "status": C.CANNOT, "version": version, "pass": "rules"})
            continue
        for at, w in unknown:
            prefix, suffix = _context(text, at, w)
            findings.append({"box": m.id, "kind": "spelling", "quote": w, "prefix": prefix, "suffix": suffix,
                             "fix": None, "why": "FEED does not know this word", "status": "open",
                             "version": version, "pass": "rules"})
            notes["unknown"] += 1
    return findings, notes


# ---------------------------------------------------------------------------
# The model pass, under a contract
# ---------------------------------------------------------------------------

CONTRACT = """\
You check one box of a person's own writing. You never rewrite it. You point at an exact span of the text and, where
you can, give the smallest replacement for that span. Answer with one JSON object and nothing else:

{"spelling": [{"quote": "<a word from the list>", "fix": "<its right spelling>" or null, "why": "<one line>"}],
 "grammar": [{"quote": "<exact span copied from the text>", "fix": "<replacement for that span>", "why": "<one line>"}],
 "claims": [{"quote": "<exact span copied from the text>", "verdict": "holds" or "wrong" or "cannot be checked",
             "fix": "<replacement for that span>" or null, "why": "<one line>"}]}

The rules:
- spelling: only the words in the list the dictionary does not know. Give the right spelling as fix, or fix null when
  the word is right as written (a name, a coinage, a word from another language). Never add a word to the list.
- grammar: only real errors (agreement, tense, a missing or doubled word, punctuation that changes the sense). Not
  style, not taste, not tone. The fix replaces exactly the quoted span.
- claims: every statement of fact in the text: numbers, dates, names, places, events, anything said to be true of the
  world. One entry each. "holds" only when you are sure from what you know; "wrong" when you know it is false (give a
  fix when you know the right fact); "cannot be checked" whenever you cannot confirm or refute it (anything about the
  writer, their plans, their group, local or recent facts). Never guess "holds". Opinions, wishes and requests are not
  claims.
- Every quote is copied exactly, character for character, from the text. Empty lists are fine.
"""


def _prompt(m: C.Module, text: str, unknown: list[str], thing: str) -> list[dict[str, str]]:
    body = text if len(text) <= MODEL_CHARS else text[:MODEL_CHARS]
    lines = [f"This box is part of a {thing}.",
             f"What it must get across: {m.plec or '(not said)'}",
             f"Words the dictionary does not know: {', '.join(unknown) if unknown else '(none)'}",
             "", "The text:", "<<<", body, ">>>"]
    return [{"role": "system", "content": CONTRACT}, {"role": "user", "content": "\n".join(lines)}]


def parse_answer(raw: str) -> dict[str, list[dict[str, Any]]] | None:
    """The model's JSON object, or None when it cannot be read as the contract says."""
    s = (raw or "").strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", s, re.DOTALL)
    if fence:
        s = fence.group(1)
    else:
        a, b = s.find("{"), s.rfind("}")
        if a < 0 or b <= a:
            return None
        s = s[a:b + 1]
    try:
        data = json.loads(s)
    except ValueError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("claims"), list):
        return None
    out: dict[str, list[dict[str, Any]]] = {}
    for key in ("spelling", "grammar", "claims"):
        items = data.get(key) or []
        out[key] = [x for x in items if isinstance(x, dict)] if isinstance(items, list) else []
    return out


def _located(text: str, quote: str) -> tuple[str, str] | None:
    """The prefix and suffix for a quote the model gave (its first place, when it stands in several), or None when
    the quote is not in the text."""
    at = text.find(quote) if quote else -1
    if at < 0:
        return None
    return _context(text, at, quote)


def model_pass(comp: C.Composure, complete: CompleteFn, spelling: list[dict[str, Any]], *,
               progress: Callable[[dict[str, Any]], None] | None = None,
               check: Callable[[], None] | None = None) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Grammar and truth, and a fix for each word FEED flagged. `spelling` (the rules pass's open findings) is
    filled in place with the model's fixes. Returns the new findings and the counts."""
    view = C.scaffold_view(comp) or {}
    version, thing = view.get("version", 1), view.get("thing", "page")
    boxes = written_boxes(comp)
    counts = {"boxes": len(boxes), "claims": 0, "holds": 0, "wrong": 0, "cannot": 0, "grammar": 0,
              "spelling_fixed": 0, "unread": 0}
    found: list[dict[str, Any]] = []
    for i, (m, text) in enumerate(boxes, start=1):
        if check is not None:
            try:
                check()
            except DeriveCancelled:
                raise DeriveCancelled(f"cancelled after box {i - 1} of {len(boxes)}; no finding was written") from None
        if progress is not None:
            progress({"phase": "model", "chunk": i, "chunks": len(boxes),
                      "message": f"reading box {i} of {len(boxes)}{': ' + m.title if m.title else ''}"})
        flagged = [f for f in spelling if f["box"] == m.id and f["status"] == "open" and f["quote"]]
        raw, _meta = complete(_prompt(m, text, sorted({f["quote"] for f in flagged}), thing),
                              max_tokens=MODEL_MAX_TOKENS)
        answer = parse_answer(raw)
        if answer is None:
            counts["unread"] += 1
            found.append({"box": m.id, "kind": "truth", "quote": "", "fix": None, "status": C.CANNOT,
                          "why": "the model's answer could not be read, so the claims in this box were not checked",
                          "version": version, "pass": "model"})
            continue
        fixes = {str(x.get("quote") or ""): x for x in answer["spelling"]}
        for f in flagged:
            said = fixes.get(f["quote"])
            if said is None:
                continue
            fix = said.get("fix")
            if isinstance(fix, str) and fix.strip() and fix != f["quote"]:
                f["fix"], f["pass"] = fix.strip(), "model"
                f["why"] = _why(said) or "FEED does not know this word"
                counts["spelling_fixed"] += 1
            else:
                f["why"] = "FEED does not know this word; the model reads it as right" + (
                    f" ({_why(said)})" if _why(said) else "")
        for g in answer["grammar"]:
            quote, fix = str(g.get("quote") or ""), g.get("fix")
            where = _located(text, quote)
            if where is None or not isinstance(fix, str) or fix == quote:
                continue
            counts["grammar"] += 1
            found.append({"box": m.id, "kind": "grammar", "quote": quote, "prefix": where[0], "suffix": where[1],
                          "fix": fix, "why": _why(g), "status": "open", "version": version, "pass": "model"})
        for c in answer["claims"]:
            quote = str(c.get("quote") or "")
            verdict = str(c.get("verdict") or "").strip().lower()
            counts["claims"] += 1
            if verdict == "holds":
                counts["holds"] += 1
                continue
            located = _located(text, quote)
            where = located or ("", "")
            if located is None:
                quote = ""                    # the model misquoted: the finding is about the whole box
            if verdict == "wrong":
                counts["wrong"] += 1
                fix = c.get("fix") if isinstance(c.get("fix"), str) and quote else None
                found.append({"box": m.id, "kind": "truth", "quote": quote, "prefix": where[0],
                              "suffix": where[1], "fix": fix, "why": _why(c), "status": "open",
                              "version": version, "pass": "model"})
            else:                             # "cannot be checked", or a verdict outside the contract: never passed
                counts["cannot"] += 1
                why = _why(c) if verdict == C.CANNOT else f"the model's verdict was {verdict or 'missing'}"
                found.append({"box": m.id, "kind": "truth", "quote": quote, "prefix": where[0],
                              "suffix": where[1], "fix": None, "why": why, "status": C.CANNOT,
                              "version": version, "pass": "model"})
    return found, counts


def _why(item: dict[str, Any]) -> str | None:
    why = item.get("why")
    return " ".join(str(why).split())[:300] if isinstance(why, str) and why.strip() else None


# ---------------------------------------------------------------------------
# The job
# ---------------------------------------------------------------------------

def run_check(comp_path: Path, rel: str, *, mode: str, why: str = "", complete: CompleteFn | None = None,
              known: KnownFn | None = None, progress: Callable[[dict[str, Any]], None] | None = None,
              check: Callable[[], None] | None = None) -> dict[str, Any]:
    """One run of the check: the rules pass, the model pass when `mode` is `model`, then every finding written at
    once (`composure.record_check`). A cancel before the end writes nothing."""
    from . import agent_free as _agent_free
    comp = target_of(comp_path)
    view = C.scaffold_view(comp) or {}
    version = view.get("version", 1)
    if progress is not None:
        progress({"phase": "rules", "message": "looking the words up in FEED"})
    findings, notes = rules_pass(comp, known=known)
    passes = ["rules"]
    not_checked = dict(notes["not_checked"])
    counts: dict[str, int] = {"boxes": len(written_boxes(comp)), "unknown": notes["unknown"]}
    if mode == "model" and complete is not None:
        more, mcounts = model_pass(comp, complete, findings, progress=progress, check=check)
        findings += more
        counts.update(mcounts)
        passes.append("model")
    else:
        reason = ("agent-free is on" if why == _agent_free.REASON
                  else f"no model is answering ({why})" if why else "the rules pass was asked for")
        not_checked["grammar"] = f"needs a model, and {reason}"
        not_checked["truth"] = f"needs a model, and {reason}; no claim was passed"
    if check is not None:
        check()
    stamp = {"at": _stamp(), "version": version, "mode": "model" if "model" in passes else "rules",
             "reason": _agent_free.REASON if why == _agent_free.REASON else None, "passes": passes,
             "not_checked": not_checked, "counts": counts}
    landed = C.record_check(comp_path, findings, stamp, rel)
    open_n = sum(1 for f in landed["findings"] if f["status"] == "open" and f["version"] == version)
    cannot_n = sum(1 for f in landed["findings"] if f["status"] == C.CANNOT and f["version"] == version)
    said = (f"checked {counts['boxes']} box(es) of version {version}: {open_n} open finding(s), "
            f"{cannot_n} that cannot be checked")
    if "model" not in passes:
        said = (("agent-free: " if why == _agent_free.REASON else "")
                + said + "; spelling by FEED only, grammar and truth not checked")
    if "spelling" in not_checked:
        said += "; spelling not checked (FEED is not built here)"
    return {"path": rel, "version": version, "mode": stamp["mode"], "passes": passes, "not_checked": not_checked,
            "counts": counts, "added": landed["added"], "findings": len(landed["findings"]), "message": said}


__all__ = ["CONTRACT", "CheckError", "JOB_KIND", "feed_known", "model_pass", "parse_answer", "rules_pass",
           "run_check", "target_of", "words_of", "written_boxes"]
