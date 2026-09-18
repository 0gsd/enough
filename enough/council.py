"""The council engine — several readvisors and the user, thinking in turn.

A **council** is a `.comp` with `form=council`: a brief module on top and one
locked text module per statement, tinted per speaker, stacked in a single
column. The file is the **single source of truth**. Nothing about a council
lives in memory that is not derivable from the document on disk — kill the
server mid-council, restart it, and the next turn picks up exactly where the
last one left off, because the engine rebuilds every participant's message
list from the transcript each time.

The shape of this module:

- **Pure logic** (top): schema validation, participants, the rotation,
  per-participant message lists, the even budget and the mechanical fold,
  the framing texts, the tint assignment, the transcript export. No IO, no
  FastAPI, no LLM — all of it is exercisable from a plain unit test.
- **One seam** (middle): `run_council_turn(messages, on_token)`. Exactly one
  streamed completion, through the same local/cloud routing `/api/chat`
  uses. Tests replace this module attribute and never touch a network.
- **The engine** (bottom): `Council`, which loads the file, asks the pure
  half what to do, runs one turn through the seam, and commits the statement
  through `composure.apply_ops` with `source="council"`.

Two exclusions the rest of the app depends on:

- a council turn holds `session.generation_lock`, so `/api/chat` and a
  council turn can never stream at once; and
- `turn_in_flight()` lets `/api/chat` refuse *politely* instead of queueing
  behind the lock, and `/api/council/*` returns 409 when the lock is already
  held by an ordinary chat turn.

The auto-reset / context-pressure machinery never sees council traffic:
council turns do not touch `session.history` or `session.last_usage`, which
is where all of it reads from.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import inspect
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from . import composure as comp_core
from .composure import ComposureError

log = logging.getLogger("enough.council")

EVENT = "council"

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

STATUSES: tuple[str, ...] = ("setup", "ready", "running", "paused", "concluded")
#: `pal` got its meaning in P9 (0.4.0): a pal statement is committed by
#: `ask_pal_turn` when the user asks for one. It is still never in the
#: rotation — nobody's turn is ever the pal's — and it never counts toward the
#: budget's even split, because it speaks only when asked.
PARTICIPANT_KINDS: tuple[str, ...] = ("chief", "readvisor", "user", "pal")
#: Kinds that validate but can never speak. Empty since 0.4.0 — `pal` was the
#: only member and P9 gave it a voice. Kept (rather than deleted) because the
#: brief roster, the export and `state()["reserved"]` all read it, and the
#: next reserved kind should cost one line, not five call sites.
RESERVED_KINDS: frozenset[str] = frozenset()
OUTPUT_KINDS: tuple[str, ...] = ("answer", "document", "composure")
#: Output kinds this release can actually conclude with. All three, since
#: 0.4.0. Kept as its own name because `api_council_conclude` reads it and a
#: future kind will land the same way `composure` did.
OUTPUT_KINDS_LANDED: frozenset[str] = frozenset(OUTPUT_KINDS)
#: The two outline layouts a `composure` output may be built with. `blank` is
#: an outline form too (`comp_core.OUTLINE_FORMS`) but it makes one full page
#: of the raw text, which is what the `answer` output already is.
COMPOSURE_OUTPUT_FORMS: tuple[str, ...] = ("scaffold", "cards")
ORDERS: tuple[str, ...] = ("round-robin",)

MAX_ROUNDS_CAP = 20
MAX_PARTICIPANTS = 12
MAX_BRIEF_FIELD_CHARS = 8_000
#: A charge is one line of accountability, not a second brief.
MAX_CHARGE_CHARS = 200
#: How much of a `document`/`composure` output a reconvened council carries
#: into its brief. Enough to argue with, not so much that the new council
#: starts three quarters full.
RECONVENE_EXCERPT_CHARS = 2_000

#: The tint ladder. Chief speaks on paper (it is the house voice), the user
#: on blue (it is the one voice that is not a model), and the readvisors
#: cycle the remaining named swatches in participant order. Assigned once, at
#: setup, and stored on the participant — so a readvisor keeps its colour for
#: the life of the council even if another is added later.
CHIEF_TINT = "paper"
USER_TINT = "blue"
PAL_TINT = "gray"
READVISOR_TINTS: tuple[str, ...] = ("yellow", "green", "pink", "lilac", "orange")
CONCLUSION_TINT = "ink"

#: Statement modules are fullport-wide, so a council reads as a page of
#: minutes rather than a board of cards.
STATEMENT_W = comp_core.FULLPORT[0]
COLUMN_GUTTER = 48.0

# ---------------------------------------------------------------------------
# The budget
# ---------------------------------------------------------------------------

#: When neither the supervisor nor `/props` will say, assume the smallest
#: window enough ever launches a local model with.
CTX_FALLBACK = 8192
#: The cloud slot has no `/props` and OpenRouter's models range from 8K to a
#: million. 32 768 is the conservative choice: it is at or under every model
#: the slot ships a preset for, so a council that fits here fits everywhere,
#: and being wrong costs a fold that was not strictly needed rather than a
#: hard context overflow mid-turn.
CTX_CLOUD = 32768
#: A share smaller than this is not a share, it is a haiku. Below it the
#: council still runs — it just folds aggressively.
MIN_SHARE = 512
#: Fold when the history reaches this much of the share. The remaining fifth
#: is the room the reply itself needs.
FOLD_AT = 0.80
#: The floor under the fold. A participant's system prompt is fixed and
#: unfoldable — a readvisor's is ~600 tokens and the chief's, in the lean
#: council profile, ~2 400 — so on a small enough window the head alone can
#: still exceed the share. Folding the transcript to nothing would not save a
#: single token of it; it would only take away the thing the council is made
#: of. So once the transcript is down to this much, the fold stops and the
#: turn goes to the model as it is. If that overflows, the honest answer is a
#: bigger `n_ctx`, not a council with amnesia.
#:
#: (Before the lean profile landed the chief's head was ~21 000 tokens and
#: this floor was load-bearing on every council. It is now an edge case: at
#: n_ctx 32768 with two speakers there is room for roughly twenty full
#: statements before anything folds at all.)
MIN_TRANSCRIPT_TOKENS = 1024
#: Roughly what a 350-word statement costs, plus slack. Passed as `max_tokens`
#: so a model that ignores the word limit still cannot eat the window.
MAX_TOKENS = 700
#: `server._estimate_total_tokens`'s ratio, deliberately the same one: a
#: council and the chat gauge should not disagree about how big a thing is.
CHARS_PER_TOKEN = 3
#: How long a `/props` answer is trusted. A model switch relaunches
#: llama-server with a new window, and a minute is short enough that a
#: council started right after a switch re-probes.
_PROPS_TTL = 60.0
_PROPS_CACHE: dict[str, tuple[float, int]] = {}

STATEMENT_WORD_CAP = 350


class CouncilError(ValueError):
    """A refusal a human (or a readvisor) can act on. The API turns it into
    a 400 and the frontend can show the sentence verbatim."""


# ---------------------------------------------------------------------------
# The framing — what a participant is told about being in a council
# ---------------------------------------------------------------------------

_CHIEF_FRAMING = """\
## This is a council

You are {chief}, the chief readvisor, and this is a council: you, the other \
readvisors, and the user, thinking about one thing in turn, in writing, on a \
canvas the user is watching. Each of you speaks under your own name. The \
statements below are the council so far — yours are yours, everyone else's \
carries the name of whoever said it.

How you speak here:

- Speak as yourself. You are the chief readvisor, not the chair of a panel \
and not a narrator: you have your own reading of the brief and this is where \
you give it.
- Answer the brief first. Address the others by name when you are answering \
them — "Nadia's continuity point holds, but the cost lands in act three" is a \
council; "some would argue" is a memo.
- Stay inside your own judgment. When something in the brief belongs to \
someone else in this room, write "I'd defer to <name> on that" and spend your \
words on what is yours. Never answer for another participant, never summarise \
what you think they would say, and never write their statement for them — \
they are about to write it themselves.
- Be brief. {cap} words is the ceiling and the good statements are half of \
it. Do not restate the brief, do not recap the discussion, do not thank \
anyone, do not sign off.
- Add something. If the council has converged, say so in one sentence and \
name what is still unsettled — that is worth more than agreeing at length.
- Plain prose, in the user's language. A short list is fine when the content \
is a list. No headings. Do not write your own name at the start; enough puts \
it on the card.
- You have no tools in a council and no way to read a file. Do not write a \
tool call. Work from what is in front of you, and when something is genuinely \
missing, say what it is and who could get it."""

_READVISOR_FRAMING = """\
## This is a council

You are {name}, and this is a council: the chief readvisor {chief}, the other \
readvisors, and the user, thinking about one thing in turn, in writing, on a \
canvas the user is watching. Everything above is who you are. The statements \
below are the council so far — yours are yours, everyone else's carries the \
name of whoever said it.

How you speak here:

- Speak as yourself, with the judgment those pages describe. You are not a \
general-purpose assistant in this room: you are one particular reader with \
one particular set of concerns, and the council only works if you keep them.
- Answer the brief first, and the others by name when you are answering them.
- Stay in your lane. Your worth here is the part of this that only you would \
notice. When a question belongs to someone else in the room, write "I'd defer \
to <name> on that" and move on. Never role-play another participant and never \
write a statement on their behalf.
- Disagree plainly when you disagree, including with {chief}. A council that \
agrees with everything is a council that was not needed.
- Be brief. {cap} words is the ceiling and the good statements are half of \
it. No preamble, no recap of the brief, no thanks, no sign-off.
- Plain prose, in the user's language. A short list is fine when the content \
is a list. No headings. Do not write your own name at the start; enough puts \
it on the card.
- You have no tools in a council and no way to read a file. Do not write a \
tool call. Work from what is in front of you, and when something is genuinely \
missing, say what it is and who could get it."""

_CONCLUSION_FRAMING = """\
## Conclude the council

The council is over and you are writing what it produced. This is not another \
statement — nobody speaks after you.

- Decide. The council's job was to get to {want}, and a conclusion that lists \
what everyone thought without saying where it lands has not done it.
- Use what was actually said. Credit a participant by name where their point \
carried the decision, and name the real disagreement where one stands — do not \
smooth it over, and do not invent agreement nobody reached.
- Say what is still open, in one or two lines at the end, when something is.
- Write the thing itself, not a description of it. No preamble, no "in \
conclusion", no sign-off, no headings unless the output is a document long \
enough to need them.
{shape}"""

_CONCLUSION_SHAPE = {
    "answer": (
        "- The output is an **answer**: prose the user reads on the canvas. "
        "Aim for under 400 words."
    ),
    "document": (
        "- The output is a **document**, which enough will write to "
        "`{path}`. Write the whole file, in markdown, starting with a `# ` "
        "title. Nothing but the document — no covering note."
    ),
    "composure": (
        "- The output is a **composure**: a board of cards enough will lay "
        "out from an outline. Write the outline and nothing else — no "
        "covering note, no code fence, no explanation before or after it.\n"
        "- The grammar is exactly four rules:\n"
        "  - one `# ` line, the title of the board;\n"
        "  - each `## ` line is a group (a column in the scaffold form, a "
        "row in the cards form);\n"
        "  - each `### ` line is a card, and its heading is the card's "
        "title;\n"
        "  - every line under a `### ` until the next heading is that "
        "card's body.\n"
        "- Nothing else is structure. `#### ` and deeper, tables and nested "
        "lists stay in the body as the text they are, and anything written "
        "before the first card is dropped.\n"
        "- A card whose title starts with `[gap:` is an open question — "
        "`### [gap: who owns the migration?]` — and enough tints it. Use "
        "them for what the council did not settle instead of leaving it "
        "out.\n"
        "- Two to six groups, two to eight cards in each, a body of a "
        "sentence or three per card. The whole board is what the council "
        "decided, arranged so it can be read at a glance."
    ),
}

#: The one retry. Sent as a final user message when the first concluding turn
#: did not parse — the same framing, plus a demonstration, because a model
#: that ignored the grammar in prose usually follows it from an example.
OUTLINE_RETRY = """\
That did not parse as an outline, so nothing was made. Write it again, as \
the outline and nothing else — no preamble, no code fence, no closing note. \
This is the whole grammar:

# The title of the board

## The first group

### The first card

Its body, a sentence or three.

### [gap: what the council did not settle]

Why it is still open.

## The second group

### Another card

Its body.

Start your reply with the `# ` line."""

#: What the chief is asked to do with the user's `/pal` question. One
#: completion; the answer IS the prompt that leaves the machine, so it has to
#: stand on its own — the pal has never seen this council.
PAL_DISTILL = """\
## Distil one question for the pal

The user has asked this council to put a question to the **pal** — a cloud \
model outside this machine, which has not seen this council, this project or \
any of these documents. You are writing the prompt that will be sent to it. \
Your reply is the prompt itself: it leaves exactly as you write it.

The user's ask:

{ask}

Write ONE self-contained prompt that:

- carries the little of the brief and the council the pal actually needs to \
answer, in your own words, and nothing more;
- names no file path, no project name, no participant's real name and no \
private detail that the question does not require;
- asks one thing, plainly, and says what shape of answer is wanted;
- is under 300 words.

Reply with the prompt and nothing else — no preamble, no quotation marks \
around it, no note about what you left out."""

#: The pal's statement, above the fold: the exact text that left the machine.
PAL_PROMPT_LEAD = "→ pal"


def chief_framing(chief: str) -> str:
    """The council framing appended to the chief's assembled prompt."""
    return _CHIEF_FRAMING.format(chief=chief, cap=STATEMENT_WORD_CAP)


def readvisor_framing(name: str, chief: str) -> str:
    """The council framing appended to a readvisor's identity."""
    return _READVISOR_FRAMING.format(name=name, chief=chief,
                                     cap=STATEMENT_WORD_CAP)


def conclusion_framing(output: dict[str, Any]) -> str:
    """What the chief is told for the one concluding turn."""
    kind = str((output or {}).get("kind") or "answer")
    want = {"answer": "a decided answer",
            "document": "a written document",
            "composure": "a new composure"}.get(kind, "a decided answer")
    shape = _CONCLUSION_SHAPE.get(kind, _CONCLUSION_SHAPE["answer"])
    return _CONCLUSION_FRAMING.format(
        want=want, shape=shape.format(path=(output or {}).get("path") or ""))


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def _text(value: object, limit: int = MAX_BRIEF_FIELD_CHARS) -> str:
    if value is None:
        return ""
    out = str(value).replace("\r\n", "\n").replace("\r", "\n").strip()
    return out[:limit]


def _slug_name(value: object) -> str:
    return _text(value, 80)


def validate_output(raw: object) -> dict[str, Any]:
    """`{kind, path?, form?, overwrite?}`.

    A `composure` output takes no path from the user — the file is made next
    to the council when it concludes, and its path is written back here — but
    it does take a `form`, which is the layout the outline is laid out in and
    must be one of `COMPOSURE_OUTPUT_FORMS`."""
    data = raw if isinstance(raw, dict) else {}
    kind = _text(data.get("kind") or "answer", 32).lower()
    if kind not in OUTPUT_KINDS:
        raise CouncilError(
            f"unknown council output kind {kind!r}. kinds: "
            f"{', '.join(OUTPUT_KINDS)}.")
    out: dict[str, Any] = {"kind": kind}
    path = _text(data.get("path"), 512)
    form = _text(data.get("form"), 64).lower()
    if kind == "document":
        if not path:
            raise CouncilError(
                "a document output needs a path — where in the project the "
                "council's document should be written, e.g. "
                "notes/the-decision.md.")
        if path.endswith(comp_core.SUFFIX):
            raise CouncilError(
                "a document output writes markdown, not a composure. Use the "
                "'composure' output kind for that, or give a .md path.")
    if kind == "composure":
        form = form or COMPOSURE_OUTPUT_FORMS[0]
        if form not in COMPOSURE_OUTPUT_FORMS:
            raise CouncilError(
                f"unknown composure form {form!r}. forms: "
                f"{', '.join(COMPOSURE_OUTPUT_FORMS)} — scaffold puts each "
                f"group in a column, cards puts each group in a row.")
    out["path"] = path or None
    out["form"] = form or None
    out["overwrite"] = bool(data.get("overwrite"))
    return out


def _charge(value: object) -> str:
    """One line of accountability, or nothing. Newlines are collapsed rather
    than refused (a textarea that wrapped is not a user error), and anything
    over the cap is refused rather than truncated — a charge silently cut in
    half would change what a participant was told to do."""
    raw = " ".join(_text(value, MAX_CHARGE_CHARS * 4).split())
    if len(raw) > MAX_CHARGE_CHARS:
        raise CouncilError(
            f"a charge is one line — at most {MAX_CHARGE_CHARS} characters "
            f"(that one is {len(raw)}). It says what a participant is "
            f"accountable for here, not what they should think.")
    return raw


def validate_participants(raw: object) -> list[dict[str, Any]]:
    """`[{id, kind, name, charge?}]`. Tints are assigned here, once, in list
    order, and stored — so a readvisor keeps its colour for the life of the
    council. `charge` is the per-participant accountability line ("owns
    continuity", "argues the reader's side"), injected into that
    participant's council framing by `identity_for`."""
    rows = raw if isinstance(raw, list) else []
    if not rows:
        raise CouncilError(
            "a council needs participants — the chief readvisor, any "
            "readvisors you want in the room, and usually you.")
    if len(rows) > MAX_PARTICIPANTS:
        raise CouncilError(
            f"a council seats at most {MAX_PARTICIPANTS} participants "
            f"(got {len(rows)}). More than that and nobody gets a share of "
            f"the context window worth having.")
    out: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    tint = 0
    chiefs = 0
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise CouncilError("each participant must be a json object with "
                               "an id, a kind and a name.")
        kind = _text(row.get("kind"), 32).lower()
        if kind not in PARTICIPANT_KINDS:
            raise CouncilError(
                f"unknown participant kind {kind!r}. kinds: "
                f"{', '.join(PARTICIPANT_KINDS)}.")
        name = _slug_name(row.get("name"))
        if not name:
            raise CouncilError(
                f"participant {i + 1} has no name — a council statement is "
                f"signed, so every participant needs one.")
        pid = _slug_name(row.get("id")) or f"{kind}:{name}"
        if pid in seen_ids:
            raise CouncilError(f"two participants share the id {pid!r}.")
        low = name.casefold()
        if low in seen_names:
            raise CouncilError(
                f"two participants are both called {name!r} — statements are "
                f"attributed by name, so rename one of them (the chief "
                f"readvisor's name is in the broker pane).")
        seen_ids.add(pid)
        seen_names.add(low)
        if kind == "chief":
            chiefs += 1
        entry = {"id": pid, "kind": kind, "name": name,
                 "charge": _charge(row.get("charge")),
                 # The on-disk readvisor directory. Kept because a readvisor
                 # whose AGENT.md has a prettier `# H1` than its folder name
                 # would otherwise be looked up by its display name and find
                 # nothing.
                 "folder": _slug_name(row.get("folder"))}
        if kind == "chief":
            entry["tint"] = CHIEF_TINT
        elif kind == "user":
            entry["tint"] = USER_TINT
        elif kind == "pal":
            entry["tint"] = PAL_TINT
        else:
            entry["tint"] = READVISOR_TINTS[tint % len(READVISOR_TINTS)]
            tint += 1
        out.append(entry)
    if chiefs > 1:
        raise CouncilError("a council has one chief readvisor, not several.")
    if not any(p["kind"] in ("chief", "readvisor") for p in out):
        raise CouncilError(
            "a council needs at least one readvisor to speak — with only the "
            "user in the room nothing would ever be said.")
    return out


def validate_meta(raw: object) -> dict[str, Any]:
    """The whole `composure:council` object, normalized. Unknown keys are
    dropped rather than carried: this meta IS the state machine, and a key
    nobody validates is a key that will one day contradict one that is."""
    data = raw if isinstance(raw, dict) else {}
    status = _text(data.get("status") or "setup", 32).lower()
    if status not in STATUSES:
        raise CouncilError(
            f"unknown council status {status!r}. statuses: "
            f"{', '.join(STATUSES)}.")
    order = _text(data.get("order") or "round-robin", 32).lower()
    if order not in ORDERS:
        raise CouncilError(
            f"unknown council order {order!r}. orders: {', '.join(ORDERS)}.")
    try:
        max_rounds = int(data.get("max_rounds") or 3)
    except (TypeError, ValueError):
        raise CouncilError("max_rounds must be a whole number.") from None
    if not 1 <= max_rounds <= MAX_ROUNDS_CAP:
        raise CouncilError(
            f"max_rounds must be between 1 and {MAX_ROUNDS_CAP} "
            f"(got {max_rounds}).")
    participants = (validate_participants(data.get("participants"))
                    if data.get("participants") else [])
    queue = [
        {"text": _text(q.get("text") if isinstance(q, dict) else q)}
        for q in (data.get("queue") or [])
    ]
    queue = [q for q in queue if q["text"]]
    return {
        "input": _text(data.get("input")),
        "parameters": _text(data.get("parameters")),
        "constraints": _text(data.get("constraints")),
        "output": validate_output(data.get("output")),
        "participants": participants,
        "order": order,
        "max_rounds": max_rounds,
        "status": status,
        "round": max(0, int(data.get("round") or 0)),
        "turn": max(0, int(data.get("turn") or 0)),
        "cursor": max(0, int(data.get("cursor") or 0)),
        "next": _slug_name(data.get("next")) or None,
        "queue": queue,
        "brief_module": _slug_name(data.get("brief_module")) or None,
        #: Where the transcript was exported on conclude, project-relative.
        "transcript": _text(data.get("transcript"), 512) or None,
        # True on a council made by `/api/council/reconvene`. It is a fact
        # about where this council came from, not a control: the UI uses it
        # to label the lineage, and `reconvened_from` carries the path.
        "reconvene": bool(data.get("reconvene")),
        "reconvened_from": _text(data.get("reconvened_from"), 512) or None,
        "reconvened_to": _text(data.get("reconvened_to"), 512) or None,
        # Set when a `composure` output's outline would not parse twice and
        # the conclusion was kept as prose instead: `"answer"`, or None.
        "output_fallback": _text(data.get("output_fallback"), 32) or None,
    }


def speakers(meta: dict[str, Any]) -> list[dict[str, Any]]:
    """The participants that actually generate in the rotation: chief and
    readvisors, in list order. `user` writes its own statements and `pal`
    answers only when it is asked, so neither is in the rotation and neither
    takes a share of the window."""
    return [p for p in meta.get("participants") or []
            if p.get("kind") in ("chief", "readvisor")]


def participant_by_id(meta: dict[str, Any], pid: str) -> dict[str, Any] | None:
    return next((p for p in meta.get("participants") or []
                 if p.get("id") == pid), None)


def participant_by_name(meta: dict[str, Any], name: str) -> dict[str, Any] | None:
    low = (name or "").casefold()
    return next((p for p in meta.get("participants") or []
                 if str(p.get("name", "")).casefold() == low), None)


def user_participant(meta: dict[str, Any]) -> dict[str, Any] | None:
    return next((p for p in meta.get("participants") or []
                 if p.get("kind") == "user"), None)


def next_speaker(meta: dict[str, Any]) -> dict[str, Any] | None:
    """Whose turn it is.

    Round-robin over the speaking participants — except that **a queued user
    statement takes the next slot**. The queue jumps ahead of the rotation
    without consuming it, so after the user speaks the model whose turn it
    was still speaks next, which is what makes "say something at any time"
    an interjection rather than a reshuffle."""
    if meta.get("queue"):
        user = user_participant(meta)
        if user is not None:
            return user
    order = speakers(meta)
    if not order:
        return None
    return order[int(meta.get("cursor") or 0) % len(order)]


def advance(meta: dict[str, Any], spoke: dict[str, Any]) -> None:
    """Move the state on after `spoke` has been committed. A user statement
    does not move the cursor (see `next_speaker`); a speaking participant
    does, and wrapping past the last one closes a round."""
    meta["turn"] = int(meta.get("turn") or 0) + 1
    if spoke.get("kind") in ("chief", "readvisor"):
        order = speakers(meta)
        cursor = (int(meta.get("cursor") or 0) + 1) % max(1, len(order))
        meta["cursor"] = cursor
        if cursor == 0:
            meta["round"] = int(meta.get("round") or 0) + 1
    nxt = next_speaker(meta)
    meta["next"] = nxt["id"] if nxt else None


# ---------------------------------------------------------------------------
# The transcript, read back out of the file
# ---------------------------------------------------------------------------

@dataclass
class Statement:
    module: str
    speaker: str
    speaker_kind: str
    turn: int
    text: str


def read_statements(comp: comp_core.Composure) -> list[Statement]:
    """Every committed statement, in turn order. This is the whole of the
    council's memory: restart the process, reopen the file, and the next
    turn's message lists are identical to the ones it would have had."""
    out: list[Statement] = []
    for i, m in enumerate(comp.modules):
        if not m.speaker:
            continue
        try:
            turn = int(m.turn or 0)
        except (TypeError, ValueError):
            turn = 0
        text = comp_core.rich_to_md(m.pages[0].rich if m.pages else "").strip()
        out.append(Statement(module=m.id, speaker=m.speaker,
                             speaker_kind=m.speaker_kind or "readvisor",
                             turn=turn or (i + 1), text=text))
    out.sort(key=lambda s: s.turn)
    return out


def brief_text(meta: dict[str, Any]) -> str:
    """The brief, as every participant sees it. Always the first user message
    and never folded away — it is the only thing in the window that says what
    the council is for."""
    lines = ["# The brief"]
    for label, key in (("Input", "input"), ("Parameters", "parameters"),
                       ("Constraints", "constraints")):
        body = (meta.get(key) or "").strip()
        if body:
            lines.append(f"\n**{label}.** {body}")
    lines.append(f"\n**Desired output.** {output_sentence(meta)}.")
    roster = ", ".join(
        f"{p['name']} ({p['kind']})"
        for p in meta.get("participants") or []
        if p.get("kind") not in RESERVED_KINDS)
    if roster:
        lines.append(f"\n**In the room.** {roster}.")
    return "\n".join(lines).strip()


def output_sentence(meta: dict[str, Any]) -> str:
    """What the council is for, in one clause. Shared by the brief every
    participant reads and the brief module on the canvas, so the two can
    never drift."""
    out = meta.get("output") or {}
    kind = out.get("kind") or "answer"
    form = out.get("form") or COMPOSURE_OUTPUT_FORMS[0]
    return {
        "answer": "a decided answer, written on the canvas at the end",
        "document": f"a document, written to {out.get('path') or '(a path)'}",
        "composure": (f"a new composure — a board of cards in the {form} "
                      f"layout, written beside this council"),
    }.get(kind, "a decided answer")


def brief_markdown(meta: dict[str, Any]) -> str:
    """The brief MODULE's page: the four setup fields, in the shape the
    shipped form's placeholder has. Written by `api_council_setup` in its own
    batch so a council set up through the API alone — by a tool, by a script,
    by anything that is not the setup card — still shows its real brief
    instead of the form's "What the council is working from…" prompt."""
    rows = [("Input", (meta.get("input") or "").strip()),
            ("Parameters", (meta.get("parameters") or "").strip()),
            ("Constraints", (meta.get("constraints") or "").strip()),
            ("Desired output", output_sentence(meta) + ".")]
    return "\n\n".join(f"**{label}.** {body}" for label, body in rows if body)


# ---------------------------------------------------------------------------
# The budget and the fold
# ---------------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    return len(text or "") // CHARS_PER_TOKEN


def messages_tokens(messages: list[dict[str, str]]) -> int:
    return sum(estimate_tokens(m.get("content") or "") for m in messages)


def share_for(n_ctx: int, n_speakers: int) -> int:
    """`floor(n_ctx / N)`, where N is the number of participants that
    actually generate. One llama-server slot, no relaunch: every participant
    is a separate conversation sharing one window, so an even split is the
    only division that does not quietly starve whoever speaks last."""
    n = max(1, int(n_speakers))
    return max(MIN_SHARE, int(max(0, int(n_ctx)) // n))


def first_sentence(text: str, limit: int = 220) -> str:
    """The mechanical summary: the first sentence of a statement. No second
    LLM call — a council that spends a completion summarizing itself is a
    council paying twice for the same window."""
    body = " ".join((text or "").split())
    if not body:
        return ""
    m = re.search(r"(?<=[.!?])\s", body)
    out = body[:m.start() + 1] if m else body
    return out[:limit].rstrip()


def fold_summary(statements: list[Statement]) -> str:
    lines = ["Earlier in this council:"]
    for s in statements:
        head = first_sentence(s.text) or "(said nothing)"
        lines.append(f"- {s.speaker} (turn {s.turn}): {head}")
    return "\n".join(lines)


def build_messages(meta: dict[str, Any], statements: list[Statement],
                   identity: str, me: str, *, share: int,
                   stats: dict[str, int] | None = None,
                   ) -> list[dict[str, str]]:
    """One participant's whole message list, from the transcript.

    The perspective flip is the point: **my** statements are `assistant`
    turns, everyone else's are `user` turns prefixed with their name. A model
    reading this sees a conversation it has been part of, not a transcript it
    is being asked to comment on.

    Folding is mechanical and deterministic: while the estimate is over
    `FOLD_AT` of the share, one more of the oldest statements moves into a
    single "Earlier in this council" note (first sentence each). The brief is
    pinned and the most recent statement is never folded — a participant that
    cannot see the thing it is answering has nothing to say."""
    head = [{"role": "system", "content": identity},
            {"role": "user", "content": brief_text(meta)}]

    def render(folded: int) -> list[dict[str, str]]:
        out = list(head)
        if folded:
            out.append({"role": "user",
                        "content": fold_summary(statements[:folded])})
        for s in statements[folded:]:
            if s.speaker.casefold() == (me or "").casefold():
                out.append({"role": "assistant", "content": s.text})
            else:
                out.append({"role": "user",
                            "content": f"{s.speaker}: {s.text}"})
        return out

    budget = int(share * FOLD_AT)
    head_tokens = messages_tokens(head)
    folded = 0
    messages = render(folded)
    while (messages_tokens(messages) > budget
           and folded < max(0, len(statements) - 1)):
        if messages_tokens(messages) - head_tokens <= MIN_TRANSCRIPT_TOKENS:
            break                       # see MIN_TRANSCRIPT_TOKENS
        folded += 1
        messages = render(folded)
    if stats is not None:
        stats["folded"] = folded
        stats["head"] = head_tokens
        stats["total"] = messages_tokens(messages)
        stats["budget"] = budget
    return messages


# ---------------------------------------------------------------------------
# Identities
# ---------------------------------------------------------------------------

def identity_for(project_dir: Path, participant: dict[str, Any], chief: str,
                 *, conclude: dict[str, Any] | None = None) -> str:
    """The system prompt for one participant.

    - **chief** — the project's assembled prompt in the **council profile**:
      the identity preface, Identity, Motivation, the project description and
      the project profile, and nothing else. No readvisors (every other
      readvisor is a separate participant with its own prompt; folding them
      into the chief as well would put each of them in the room twice), and no
      paradigm, policies, skills or tool documentation — a council turn calls
      no tools, so all of that is instruction for something that cannot happen,
      paid for on every turn inside a share of the window it is already too
      big for. Then the council framing.
    - **readvisor** — its `AGENT.md` + `MOTIVATION.md` via
      `prompt.readvisor_identity`, the project's description, plus the
      council framing.
    """
    from . import prompt as prompt_mod
    parts: list[str] = []
    kind = participant.get("kind")
    if kind == "chief":
        parts.append(prompt_mod.assemble_system_prompt(
            project_dir, readvisors="none", profile="council"))
        parts.append(chief_framing(chief))
    else:
        name = str(participant.get("name") or "")
        ident = prompt_mod.readvisor_identity(
            project_dir, str(participant.get("folder") or name))
        if ident:
            parts.append(ident)
        else:
            parts.append(f"# {name}\n\nYou are {name}, a readvisor in this "
                         f"project. No profile was found for you on disk, so "
                         f"speak plainly and from general judgment, and say "
                         f"so if that becomes a problem.")
        description = _project_description(project_dir)
        if description:
            parts.append("## The project\n\n" + description)
        parts.append(readvisor_framing(name, chief))
    charge = (participant.get("charge") or "").strip()
    if charge:
        # One line, last, after the framing: it is the most specific thing
        # this participant was told, and the thing a long identity is most
        # likely to bury.
        parts.append(f"## Your charge in this council\n\n"
                     f"Your charge in this council: {charge}")
    if conclude is not None:
        parts.append(conclusion_framing(conclude))
    return "\n\n".join(p.strip() for p in parts if p and p.strip()) + "\n"


def _project_description(project_dir: Path) -> str:
    try:
        from . import project_meta
        return str(project_meta.load(project_dir).get("description") or "").strip()
    except Exception:  # noqa: BLE001 — a description is context, not a gate
        return ""


# ---------------------------------------------------------------------------
# Cleaning what a model emits
# ---------------------------------------------------------------------------

_TOOL_BLOCK = re.compile(r"<tool\b[^>]*>.*?</tool>", re.IGNORECASE | re.DOTALL)
_TOOL_DANGLING = re.compile(r"<tool\b[^>]*>.*\Z", re.IGNORECASE | re.DOTALL)
_SELF_LABEL = re.compile(r"\A\s*([^\n:]{1,40}):\s+")


def strip_tool_calls(text: str, speaker: str = "") -> tuple[str, int]:
    """Remove any tool call a participant emitted anyway.

    There are no tools in a council this round, and the framing says so — but
    a model that has been told about tools in ten thousand tokens of system
    prompt will occasionally reach for one regardless. Stripping is the right
    answer rather than refusing the turn: the statement around the call is
    usually fine, and a council that dies because one participant typed XML
    is worse than a council with one thin statement. Returns the cleaned text
    and how many blocks were removed, so the caller can log it."""
    out, n = _TOOL_BLOCK.subn("", text or "")
    out2, n2 = _TOOL_DANGLING.subn("", out)
    if n + n2:
        log.warning("council: stripped %d tool call(s) from %s's statement",
                    n + n2, speaker or "a participant")
    return out2, n + n2


def clean_statement(text: str, speaker: str = "") -> str:
    """What actually lands on the card: tool calls stripped, and the speaker's
    own name removed from the front if the model signed its statement anyway
    (the card already carries the name; "Ed: Ed: …" reads as a bug)."""
    body, _n = strip_tool_calls(text, speaker)
    body = body.strip()
    m = _SELF_LABEL.match(body)
    if m and speaker and m.group(1).strip().casefold() == speaker.casefold():
        body = body[m.end():].lstrip()
    return body.strip()


# ---------------------------------------------------------------------------
# n_ctx
# ---------------------------------------------------------------------------

def probe_n_ctx(llm_url: str) -> int | None:
    """llama-server's `/props` → `default_generation_settings.n_ctx`. The
    same probe `skillaudit._completion_budget` uses, cached briefly so a
    council's first round does not make one HTTP call per participant."""
    base = (llm_url or "").rstrip("/")
    if not base:
        return None
    now = time.monotonic()
    hit = _PROPS_CACHE.get(base)
    if hit and now - hit[0] < _PROPS_TTL:
        return hit[1]
    try:
        import httpx
        r = httpx.get(f"{base}/props", timeout=5.0)
        if r.status_code != 200:
            return None
        n = (r.json().get("default_generation_settings") or {}).get("n_ctx")
        ctx = int(n) if n else None
    except Exception:  # noqa: BLE001 — a missing /props is not an error
        return None
    if ctx:
        _PROPS_CACHE[base] = (now, ctx)
    return ctx


def resolve_n_ctx(*, supervisor: Any = None, llm_url: str = "",
                  active_model: str | None = None) -> int:
    """The window a council is dividing up: the supervisor's live ctx, else
    the `/props` probe, else `CTX_FALLBACK`. When the cloud slot is the
    active model there is nothing to probe, so the documented constant
    `CTX_CLOUD` stands in."""
    if active_model == "opro-api":
        return CTX_CLOUD
    ctx = getattr(supervisor, "current_ctx", None) if supervisor else None
    try:
        if ctx and int(ctx) > 0:
            return int(ctx)
    except (TypeError, ValueError):
        pass
    probed = probe_n_ctx(llm_url)
    return int(probed) if probed else CTX_FALLBACK


# ---------------------------------------------------------------------------
# The seam — one streamed completion
# ---------------------------------------------------------------------------

TokenSink = Callable[[str], Awaitable[None]]


async def run_council_turn(messages: list[dict[str, str]],
                           on_token: TokenSink | None = None, *,
                           llm_url: str = "",
                           client: Any = None,
                           max_tokens: int = MAX_TOKENS,
                           usage_sink: dict[str, int] | None = None) -> str:
    """One streamed completion, through the same routing `/api/chat` uses.

    **This function is the test seam.** Tests replace
    `council.run_council_turn` with a coroutine that yields canned tokens,
    and every other line in this module runs unchanged. Nothing else in the
    council path talks to a model."""
    import httpx

    from . import cloud as _cloud
    from . import models as _models
    from .llm import stream_chat

    try:
        active = _models.load_state().get("current")
    except Exception:  # noqa: BLE001
        active = None

    owned: httpx.AsyncClient | None = None
    if client is None:
        owned = httpx.AsyncClient()
        client = owned
    buffer: list[str] = []
    try:
        if active == "opro-api":
            agen = _cloud.stream_chat_completion(
                messages, client=client, max_tokens=max_tokens,
                usage_sink=usage_sink)
        else:
            agen = stream_chat(llm_url, messages, client=client,
                               max_tokens=max_tokens, usage_sink=usage_sink)
        try:
            async for chunk in agen:
                buffer.append(chunk)
                if on_token is not None:
                    await on_token(chunk)
        finally:
            await agen.aclose()
    finally:
        if owned is not None:
            await owned.aclose()
    return "".join(buffer)


# ---------------------------------------------------------------------------
# The pal seam — one call out of the machine
# ---------------------------------------------------------------------------

def _pal_not_wired(prompt: str) -> tuple[str, str]:
    raise NotImplementedError("pal lane")


#: `PAL_CALL(prompt) -> (model_id, reply_text)`.
#:
#: The council does not know how to reach a pal and must not learn: the gate,
#: the cache, the broker trace, the exfiltration patterns and the one-call
#: limit all live with `/pal` in `pal_tools.py`. This module attribute is the
#: whole of the contract between them — `ask_pal_turn` distils the prompt,
#: calls this, and commits what comes back. It may be a plain function or a
#: coroutine function; the return is awaited when it is awaitable.
#:
#: Unwired (as here) it raises `NotImplementedError("pal lane")`. Whoever
#: routes the council composer's `/pal` sets it, and turns that exception
#: into whatever the closed-gate answer should be.
PAL_CALL: Callable[[str], Any] = _pal_not_wired

#: A prompt longer than this is not a distillation, and the pal's own caller
#: caps it anyway. Cut here too so the record and the wire agree.
PAL_PROMPT_CHARS = 6_000


# ---------------------------------------------------------------------------
# Runtime registry — what the rest of the server needs to know
# ---------------------------------------------------------------------------

_IN_FLIGHT: set[str] = set()
_RUNS: dict[str, "asyncio.Task[Any]"] = {}
_LOCKS: dict[str, asyncio.Lock] = {}


def turn_in_flight() -> bool:
    """True while any council turn is streaming. `/api/chat` reads this so it
    can refuse politely instead of queueing behind `generation_lock` and
    surprising the user with an answer ten minutes later."""
    return bool(_IN_FLIGHT)


def busy_paths() -> list[str]:
    return sorted(_IN_FLIGHT)


def _turn_lock(key: str) -> asyncio.Lock:
    return _LOCKS.setdefault(key, asyncio.Lock())


def reset_runtime() -> None:
    """Drop every runtime handle. For tests; the file is the state, so this
    can never lose anything that matters."""
    _IN_FLIGHT.clear()
    _RUNS.clear()
    _LOCKS.clear()
    _PROPS_CACHE.clear()


# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------

Emit = Callable[[str, dict[str, Any]], Awaitable[None]]


@dataclass
class TurnResult:
    speaker: str
    speaker_kind: str
    turn: int
    module: str
    rev: int
    text: str
    stripped: int = 0
    folded: int = 0


class Council:
    """One council, bound to one `.comp`.

    Holds no state of its own: every method loads the file, reasons about
    what it finds, and writes back through `composure.apply_ops`. Two
    instances over the same path behave identically, which is exactly what
    "a restart mid-council loses nothing" means."""

    def __init__(self, path: Path, *, project_dir: Path, rel_path: str,
                 emit: Emit | None = None, llm_url: str = "",
                 session: Any = None) -> None:
        self.path = path
        self.project_dir = project_dir
        self.rel = rel_path
        self.emit = emit
        self.llm_url = llm_url
        self.session = session
        self.key = str(path.resolve())

    # -- reading ----------------------------------------------------------

    def load(self) -> tuple[comp_core.Composure, dict[str, Any]]:
        comp = comp_core.load(self.path)
        if comp.council is None:
            raise CouncilError(
                f"{self.rel} is not a council — set one up first "
                f"(POST /api/council/setup), or open it as an ordinary "
                f"composure.")
        return comp, validate_meta(comp.council)

    def n_ctx(self) -> int:
        try:
            from . import models as _models
            active = _models.load_state().get("current")
        except Exception:  # noqa: BLE001
            active = None
        return resolve_n_ctx(supervisor=getattr(self.session, "supervisor", None),
                             llm_url=self.llm_url, active_model=active)

    def state(self) -> dict[str, Any]:
        """Everything the setup card and the controls need, in one read."""
        comp, meta = self.load()
        statements = read_statements(comp)
        n_ctx = self.n_ctx()
        order = speakers(meta)
        nxt = next_speaker(meta)
        return {
            "path": self.rel,
            "rev": comp.rev,
            "title": comp.title,
            "council": meta,
            "next": nxt["id"] if nxt else None,
            "next_name": nxt["name"] if nxt else None,
            "statements": [
                {"module": s.module, "speaker": s.speaker,
                 "speaker_kind": s.speaker_kind, "turn": s.turn}
                for s in statements
            ],
            "budget": {
                "n_ctx": n_ctx,
                "speakers": len(order),
                "share": share_for(n_ctx, len(order)),
                "fold_at": FOLD_AT,
            },
            "running": self.key in _RUNS and not _RUNS[self.key].done(),
            "streaming": self.key in _IN_FLIGHT,
            "reserved": [p["id"] for p in meta["participants"]
                         if p["kind"] in RESERVED_KINDS],
        }

    # -- writing ----------------------------------------------------------

    def _commit(self, ops: list[dict[str, Any]], meta: dict[str, Any] | None = None,
                ) -> comp_core.OpsResult:
        batch = list(ops)
        if meta is not None:
            batch.append({"op": "set_council", "council": meta})
        return comp_core.apply_ops(
            self.path, None, batch, source="council",
            project_dir=self.project_dir, rel_path=self.rel)

    async def _announce(self, payload: dict[str, Any]) -> None:
        if self.emit is None:
            return
        await self.emit(EVENT, {"path": self.rel, **payload})

    async def _announce_composure(self, result: comp_core.OpsResult) -> None:
        if self.emit is None:
            return
        await self.emit(comp_core.EVENT, {
            "path": self.rel, "rev": result.rev, "changed": result.changed,
            "source": "council", "created": result.created,
        })

    def brief_module_id(self, comp: comp_core.Composure,
                        meta: dict[str, Any]) -> str | None:
        stated = meta.get("brief_module")
        if stated and comp.module(stated) is not None:
            return stated
        for m in comp.modules:
            if not m.speaker:
                return m.id
        return None

    def _statement_ops(self, comp: comp_core.Composure, meta: dict[str, Any],
                       *, speaker: dict[str, Any], turn: int, text: str,
                       bg: str | None = None, title: str | None = None,
                       ) -> list[dict[str, Any]]:
        """One statement: a locked, tinted, fullport-wide text module, then a
        packed single-column re-arrange of the brief plus every statement, so
        the transcript reads top to bottom however the user has been dragging
        things around."""
        mid = comp_core._new_module_id()
        height = comp_core.estimate_height(text, STATEMENT_W, title=True)
        ops: list[dict[str, Any]] = [{
            "op": "add_module", "type": "text", "id": mid,
            "w": STATEMENT_W, "h": height,
            "bg": bg or speaker.get("tint") or CHIEF_TINT,
            "title": title or f"{speaker['name']} · turn {turn}",
            "speaker": speaker["name"],
            "speaker_kind": speaker["kind"],
            "turn": str(turn),
            "markdown": text or "(said nothing)",
        }]
        column = [i for i in
                  [self.brief_module_id(comp, meta)]
                  + [s.module for s in read_statements(comp)]
                  + [mid] if i]
        brief = comp.module(column[0]) if column else None
        ops.append({"op": "arrange", "ids": column, "mode": "column",
                    "pack": True, "gutter": COLUMN_GUTTER,
                    "x": brief.x if brief else 0.0,
                    "y": brief.y if brief else 0.0})
        return ops

    def commit_statement(self, speaker: dict[str, Any], text: str, *,
                         bg: str | None = None, title: str | None = None,
                         ) -> TurnResult:
        comp, meta = self.load()
        turn = int(meta.get("turn") or 0) + 1
        ops = self._statement_ops(comp, meta, speaker=speaker, turn=turn,
                                  text=text, bg=bg, title=title)
        advance(meta, speaker)
        result = self._commit(ops, meta)
        return TurnResult(speaker=speaker["name"], speaker_kind=speaker["kind"],
                          turn=turn, module=str(ops[0]["id"]), rev=result.rev,
                          text=text)

    # -- one turn ---------------------------------------------------------

    def messages_for(self, participant: dict[str, Any], *,
                     conclude: dict[str, Any] | None = None,
                     stats: dict[str, int] | None = None,
                     ) -> list[dict[str, str]]:
        comp, meta = self.load()
        statements = read_statements(comp)
        chief = next((p["name"] for p in meta["participants"]
                      if p["kind"] == "chief"), _chief_name())
        identity = identity_for(self.project_dir, participant, chief,
                                conclude=conclude)
        share = share_for(self.n_ctx(), len(speakers(meta)))
        return build_messages(meta, statements, identity,
                              participant["name"], share=share, stats=stats)

    def _chief(self, meta: dict[str, Any]) -> dict[str, Any]:
        speaker = next((p for p in meta["participants"]
                        if p["kind"] == "chief"), None)
        if speaker is None:
            raise CouncilError(
                "a council concludes in the chief readvisor's voice, and "
                "this one has no chief participant.")
        return speaker

    async def _stream_one(self, speaker: dict[str, Any], *, turn: int,
                          conclude: dict[str, Any] | None = None,
                          append: str = "", quiet: bool = False,
                          stats: dict[str, int] | None = None,
                          announce_as: tuple[str, str] | None = None,
                          ) -> str:
        """One streamed completion for one participant, announced on the
        `council` channel and committed by nobody. Holds
        `session.generation_lock` for the whole stream, so an ordinary chat
        turn cannot overlap it.

        `append` is an extra final user message — the outline retry and the
        pal distillation are both "the same participant, one more
        instruction", and neither is worth a second prompt assembly.
        `quiet` suppresses the token phase for a completion the user is not
        meant to read as a statement (the pal distillation: what matters is
        the prompt that left, and it lands in the module). `announce_as` is
        the `(name, kind)` the phases carry when that is not who is running:
        the pal's pending card should say `pal` from the first frame, even
        though the chief is the one writing the prompt."""
        stats = {} if stats is None else stats
        as_name, as_kind = announce_as or (speaker["name"], speaker["kind"])
        # Assembling a prompt reads a dozen files and may probe `/props`;
        # neither belongs on the event loop while an SSE stream is open.
        messages = await asyncio.to_thread(self.messages_for, speaker,
                                           conclude=conclude, stats=stats)
        if append:
            messages.append({"role": "user", "content": append})

        async def on_token(chunk: str) -> None:
            await self._announce({"phase": "token", "turn": str(turn),
                                  "speaker": as_name, "speaker_kind": as_kind,
                                  "text": chunk})

        await self._announce({"phase": "start", "turn": str(turn),
                              "speaker": as_name, "speaker_kind": as_kind})
        _IN_FLIGHT.add(self.key)
        lock = getattr(self.session, "generation_lock", None)
        try:
            if lock is not None:
                async with lock:
                    raw = await run_council_turn(
                        messages, None if quiet else on_token,
                        llm_url=self.llm_url,
                        client=getattr(self.session, "client", None))
            else:
                raw = await run_council_turn(messages,
                                             None if quiet else on_token,
                                             llm_url=self.llm_url)
        except Exception as e:  # noqa: BLE001 — every failure is one shape here
            _IN_FLIGHT.discard(self.key)
            await self._announce({"phase": "error", "turn": str(turn),
                                  "speaker": as_name, "speaker_kind": as_kind,
                                  "text": str(e)})
            raise
        finally:
            _IN_FLIGHT.discard(self.key)
        return raw

    async def take_turn(self, *, conclude: dict[str, Any] | None = None,
                        ) -> TurnResult:
        """One participant speaks, and the statement is committed."""
        comp, meta = self.load()
        if conclude is None:
            speaker = next_speaker(meta)
            if speaker is None:
                raise CouncilError("this council has nobody left to speak.")
            if speaker.get("kind") == "user":
                return await self._drain_user_statement()
        else:
            speaker = self._chief(meta)
        stats: dict[str, int] = {}
        turn = int(meta.get("turn") or 0) + 1
        raw = await self._stream_one(speaker, turn=turn, conclude=conclude,
                                     stats=stats)
        text = clean_statement(raw, speaker["name"])
        stripped = 1 if text != (raw or "").strip() else 0
        return await self._land(
            comp, speaker, text, stats=stats, stripped=stripped,
            bg=CONCLUSION_TINT if conclude is not None else None,
            title=(f"{speaker['name']} · conclusion" if conclude is not None
                   else None))

    async def _land(self, comp: comp_core.Composure, speaker: dict[str, Any],
                    text: str, *, stats: dict[str, int] | None = None,
                    stripped: int = 0, bg: str | None = None,
                    title: str | None = None) -> TurnResult:
        """Commit a statement and tell everybody. The tail of every turn —
        an ordinary one, a conclusion, and a pal's answer."""
        stats = stats or {}
        out = await asyncio.to_thread(self.commit_statement, speaker, text,
                                      bg=bg, title=title)
        out.stripped = stripped
        out.folded = int(stats.get("folded") or 0)
        await self._announce({"phase": "end", "turn": str(out.turn),
                              "speaker": out.speaker,
                              "speaker_kind": out.speaker_kind,
                              "module": out.module, "rev": out.rev,
                              "text": out.text,
                              # How many statements this participant had to
                              # read as a summary rather than in full, and
                              # what its request cost. The setup card can say
                              # "raise ctx" the moment folding starts.
                              "folded": out.folded,
                              "tokens": int(stats.get("total") or 0),
                              "head": int(stats.get("head") or 0),
                              "budget": int(stats.get("budget") or 0)})
        await self._announce_status()
        # The canvas listens to `composure`, not `council`, so it refreshes
        # the new module the same way it refreshes any other op batch.
        await self._announce_composure(comp_core.OpsResult(
            path=self.rel, rev=out.rev, changed=[out.module], stale=False,
            stale_changed=[], created=False, composure=comp))
        return out

    # -- the composure output ---------------------------------------------

    async def conclude_composure(self, out_spec: dict[str, Any],
                                 ) -> dict[str, Any]:
        """The concluding chief turn for a `composure` output.

        One completion asked for an OUTLINE. If it does not parse, **one**
        retry with `OUTLINE_RETRY` appended. If that does not parse either,
        the text is committed as an ordinary `answer` conclusion and the
        result says `fallback: "answer"` — a council that got to a decision
        should not lose it because a small model would not write headings.

        The new composure is built entirely in memory first (`from_outline`),
        so nothing is written unless the whole outline survives the parser,
        the grammar and the module cap."""
        comp, meta = self.load()
        speaker = self._chief(meta)
        form = str(out_spec.get("form") or COMPOSURE_OUTPUT_FORMS[0])
        stats: dict[str, int] = {}
        turn = int(meta.get("turn") or 0) + 1
        raw = await self._stream_one(speaker, turn=turn, conclude=out_spec,
                                     stats=stats)
        text = clean_statement(raw, speaker["name"])
        built = outline_composure(comp.title, form, text)
        retried = False
        if built is None:
            retried = True
            log.info("council: %s's outline did not parse — retrying once",
                     self.rel)
            raw2 = await self._stream_one(speaker, turn=turn,
                                          conclude=out_spec,
                                          append=OUTLINE_RETRY, stats=stats)
            text2 = clean_statement(raw2, speaker["name"])
            built2 = outline_composure(comp.title, form, text2)
            if built2 is not None:
                text, built = text2, built2
            elif text2:
                text = text2
        out = await self._land(comp, speaker, text, stats=stats,
                               bg=CONCLUSION_TINT,
                               title=f"{speaker['name']} · conclusion")
        if built is None:
            log.warning("council: %s fell back to an answer output", self.rel)
            return {"turn": out, "path": None, "fallback": "answer",
                    "retried": retried, "form": form}
        rel = output_composure_path(self.project_dir, self.rel)
        await asyncio.to_thread(_write_composure, self.project_dir, rel, built)
        link = await asyncio.to_thread(self.link_doc, rel, (
            f"The council's composure, written to `{rel}`."))
        await self._announce_composure(link)
        return {"turn": out, "path": rel, "fallback": None,
                "retried": retried, "form": form,
                "modules": len(built.modules)}

    def link_doc(self, rel: str, blurb: str) -> comp_core.OpsResult:
        """A `doc` link-in module under whatever is on the canvas now, so the
        thing the council produced is one click from the council that
        produced it. Used for the output document, the output composure and
        both ends of a reconvene."""
        _comp, meta = self.load()
        return self._commit([{
            "op": "add_module", "type": "doc", "href": rel,
            "title": rel.rsplit("/", 1)[-1], "bg": "paper",
            "markdown": blurb}], meta)

    # -- the pal -----------------------------------------------------------

    async def ask_pal_turn(self, user_ask: str) -> TurnResult:
        """The user's `/pal` question, answered in this council.

        Two halves, and the seam between them is the point:

        1. **the chief distils** — one completion through `run_council_turn`,
           with the whole brief and transcript in front of it, whose answer
           IS the prompt that will leave the machine; and
        2. **`PAL_CALL(prompt)`** — the pal lane's business, not ours.

        What lands on the canvas is one statement tinted `PAL_TINT`, spoken
        by `pal · <model id>` with `speaker_kind="pal"`, whose first block is
        the exact outgoing prompt as a blockquote (the UI collapses it) and
        whose body is the reply. Nothing leaves this machine without being
        written down where the user can read it.

        A pal statement is an interjection, like the user's: it takes a turn
        number but not a slot in the rotation, so whoever was about to speak
        still speaks next."""
        ask = " ".join((user_ask or "").split())
        if not ask:
            raise CouncilError(
                "a pal turn needs a question — what should the council ask?")
        comp, meta = self.load()
        speaker = self._chief(meta)
        turn = int(meta.get("turn") or 0) + 1
        raw = await self._stream_one(
            speaker, turn=turn, append=PAL_DISTILL.format(ask=ask),
            quiet=True, announce_as=("pal", "pal"))
        prompt = clean_statement(raw, speaker["name"])[:PAL_PROMPT_CHARS]
        if not prompt:
            raise CouncilError(
                f"{speaker['name']} did not manage to write a prompt for the "
                f"pal. Try asking again, or more specifically.")
        try:
            answer = PAL_CALL(prompt)
            if inspect.isawaitable(answer):
                answer = await answer
            model_id, reply = answer
        except NotImplementedError:
            raise
        except CouncilError:
            raise
        except Exception as e:  # noqa: BLE001 — one shape for every failure
            await self._announce({"phase": "error", "turn": str(turn),
                                  "speaker": "pal", "speaker_kind": "pal",
                                  "text": str(e)})
            raise CouncilError(f"the pal could not answer: {e}") from None
        pal = pal_participant(str(model_id or "pal"))
        return await self._land(comp, pal,
                                pal_statement(prompt, str(reply or "")))

    def _commit_user_statement(self) -> tuple[TurnResult, comp_core.OpsResult]:
        comp, meta = self.load()
        queue = list(meta.get("queue") or [])
        if not queue:
            raise CouncilError("nothing queued from the user.")
        user = user_participant(meta)
        if user is None:
            raise CouncilError("this council has no user participant.")
        text = queue.pop(0)["text"]
        turn = int(meta.get("turn") or 0) + 1
        ops = self._statement_ops(comp, meta, speaker=user, turn=turn,
                                  text=text)
        meta["queue"] = queue
        advance(meta, user)
        result = self._commit(ops, meta)
        return (TurnResult(speaker=user["name"], speaker_kind="user",
                           turn=turn, module=str(ops[0]["id"]),
                           rev=result.rev, text=text), result)

    async def _drain_user_statement(self) -> TurnResult:
        """Commit the oldest queued user statement. Not a completion — the
        user already wrote it."""
        out, result = await asyncio.to_thread(self._commit_user_statement)
        await self._announce({"phase": "end", "turn": str(out.turn),
                              "speaker": out.speaker, "speaker_kind": "user",
                              "module": out.module, "rev": out.rev,
                              "text": out.text})
        await self._announce_status()
        await self._announce_composure(result)
        return out

    async def _announce_status(self) -> None:
        try:
            state = await asyncio.to_thread(self.state)
        except (CouncilError, ComposureError):
            return
        meta = state["council"]
        await self._announce({"phase": "status", "status": meta["status"],
                              "round": meta["round"], "turn": meta["turn"],
                              "next": state["next"],
                              "next_name": state["next_name"],
                              "rev": state["rev"]})

    # -- the transcript export -------------------------------------------

    def export_transcript(self, *, output_path: str = "",
                          fallback: str = "") -> str:
        """`rness/knowledge/councils/<YYYY-MM-DD>-<slug>.md`, with a header
        block (brief, participants and their charges, output path) so a later
        conversation can cite it the way it cites any other note."""
        comp, meta = self.load()
        stamp = dt.date.today().isoformat()
        slug = comp_core.slugify(comp.title or "council", 48)
        folder = self.project_dir / "rness" / "knowledge" / "councils"
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / f"{stamp}-{slug}.md"
        n = 2
        while dest.exists():
            dest = folder / f"{stamp}-{slug}-{n}.md"
            n += 1
        lines = [f"# {comp.title}", "",
                 f"A council held on {stamp}, exported from `{self.rel}`.", ""]
        lines += ["## The brief", ""]
        for label, key in (("Input", "input"), ("Parameters", "parameters"),
                           ("Constraints", "constraints")):
            body = (meta.get(key) or "").strip()
            lines.append(f"**{label}.** {body or '—'}")
            lines.append("")
        out = meta.get("output") or {}
        target = output_path or out.get("path") or ""
        form = f" ({out.get('form')})" if out.get("kind") == "composure" \
            and out.get("form") else ""
        # The export is written before the meta is sealed, so the fallback
        # comes in as an argument as well as off the meta (a re-export of an
        # already-concluded council reads it from the file).
        fell = fallback or meta.get("output_fallback")
        lines.append(f"**Output.** {out.get('kind') or 'answer'}{form}"
                     + (f" → `{target}`" if target else "")
                     + (f" *(the outline would not parse; kept as "
                        f"{fell})*" if fell else ""))
        if meta.get("reconvened_from"):
            lines.append("")
            lines.append(f"**Reconvened from.** `{meta['reconvened_from']}`")
        lines += ["", "## Participants", ""]
        for p in meta.get("participants") or []:
            charge = (p.get("charge") or "").strip()
            note = f" — {charge}" if charge else ""
            reserved = " *(reserved, did not speak)*" \
                if p["kind"] in RESERVED_KINDS else ""
            lines.append(f"- **{p['name']}** ({p['kind']}){note}{reserved}")
        lines += ["", f"Rounds: {meta.get('round', 0)} of "
                      f"{meta.get('max_rounds', 0)} · "
                      f"{meta.get('turn', 0)} statements", "", "---", ""]
        for s in read_statements(comp):
            lines.append(f"## {s.speaker} · turn {s.turn}")
            lines.append("")
            lines.append(s.text or "(said nothing)")
            lines.append("")
        dest.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return str(dest.relative_to(self.project_dir)).replace("\\", "/")


def _chief_name() -> str:
    from . import prompt as prompt_mod
    return prompt_mod.chief_name()


# ---------------------------------------------------------------------------
# The composure output
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"\A\s*```[a-zA-Z0-9_-]*\s*\n(.*?)\n?\s*```\s*\Z",
                       re.DOTALL)


def strip_code_fence(text: str) -> str:
    """Unwrap a whole reply that is one code fence. Models fence markdown
    they were asked for far more often than they write markdown that IS a
    fence, and an outline nobody can parse because of three backticks is the
    most annoying possible way to lose a council."""
    m = _FENCE_RE.match(text or "")
    return m.group(1) if m else (text or "")


def outline_composure(title: str, form: str,
                      markdown: str) -> comp_core.Composure | None:
    """The chief's concluding text, laid out — or `None` when it is not an
    outline at all.

    Built in memory and never written here: the caller decides. `None` is the
    single "did not parse" answer, whether the text had no groups, no cards,
    or so many that it blew the module cap — all three mean the same thing to
    the retry, which is "ask once more, then keep the prose"."""
    body = strip_code_fence(markdown).strip()
    if not body:
        return None
    try:
        doc = comp_core.parse_outline(body)
    except Exception:  # noqa: BLE001 — a parser that throws is a non-outline
        return None
    if not doc.groups or not doc.card_count():
        return None
    # The model's own `# ` line wins; the council's title is the fallback for
    # an outline that opened straight into `## `.
    fallback = "" if doc.title else (title or "Council output")
    try:
        return comp_core.from_outline(fallback, form, body)
    except ComposureError:
        return None


def output_composure_path(project_dir: Path, council_rel: str,
                          when: str = "") -> str:
    """`rness/io/composure/<council-slug>-output-<date>.comp`, never
    overwriting: a council concluded twice (it cannot be, today) or two
    councils with the same name get `-2`."""
    stem = council_rel.rsplit("/", 1)[-1]
    if stem.endswith(comp_core.SUFFIX):
        stem = stem[:-len(comp_core.SUFFIX)]
    slug = comp_core.slugify(stem or "council", 48)
    stamp = when or dt.date.today().isoformat()
    folder = project_dir / comp_core.COMPOSURE_DIR_REL
    base = f"{slug}-output-{stamp}"
    candidate = folder / f"{base}{comp_core.SUFFIX}"
    n = 2
    while candidate.exists():
        candidate = folder / f"{base}-{n}{comp_core.SUFFIX}"
        n += 1
        if n > 999:  # pragma: no cover
            raise CouncilError("too many council outputs with that name.")
    return f"{comp_core.COMPOSURE_DIR_REL}/{candidate.name}"


def _write_composure(project_dir: Path, rel: str,
                     comp: comp_core.Composure) -> None:
    """Write a composure that was built whole in memory. `apply_ops` is the
    door for *changing* a file; this one has no previous version to be stale
    against, no base rev and no other writer, and `from_outline` has already
    validated every op it is made of."""
    comp.rev = 1
    comp_core.save(project_dir / rel, comp)


# ---------------------------------------------------------------------------
# The pal
# ---------------------------------------------------------------------------

def pal_participant(model_id: str) -> dict[str, Any]:
    """The speaker a pal answer is committed under. Not a member of the
    council — it is never in `meta["participants"]`, never in the rotation,
    and never in the budget — but it is shaped like one so
    `commit_statement` does not need to know it exists."""
    name = f"pal · {model_id}" if model_id else "pal"
    return {"id": "pal", "kind": "pal", "name": _slug_name(name),
            "tint": PAL_TINT, "charge": "", "folder": ""}


def pal_statement(prompt: str, reply: str) -> str:
    """The pal module's page: what left, then what came back.

    The prompt is a blockquote led by `→ pal`, which is what the UI collapses
    — the record has to show what was sent, and a reader scrolling the
    transcript should not have to wade through it every time."""
    quoted = "\n".join(f"> {line}" if line else ">"
                       for line in (prompt or "").strip().splitlines())
    head = f"> **{PAL_PROMPT_LEAD}** — the prompt this council sent:\n>\n{quoted}"
    body = (reply or "").strip() or "(the pal said nothing)"
    return f"{head}\n\n{body}"


async def ask_pal_turn(path: "Path | str | Council", user_ask: str, *,
                       project_dir: Path | None = None, rel_path: str = "",
                       llm_url: str = "", session: Any = None,
                       emit: Emit | None = None) -> TurnResult:
    """`council.ask_pal_turn(path, user_ask)` — the whole seam the `/pal`
    lane calls.

    `path` is a council `.comp` (with `project_dir`, and `rel_path` when the
    project-relative path is not derivable) or an already-built `Council`,
    for a caller that has one. Everything else is
    `Council.ask_pal_turn`'s docstring; the one thing to know from outside is
    that `PAL_CALL` is the only line of this that talks to a pal, and it is
    yours to set."""
    if isinstance(path, Council):
        return await path.ask_pal_turn(user_ask)
    target = Path(path)
    root = Path(project_dir) if project_dir else target.parent
    rel = rel_path
    if not rel:
        try:
            rel = str(target.resolve().relative_to(root.resolve())
                      ).replace("\\", "/")
        except ValueError:
            rel = target.name
    council = Council(target, project_dir=root, rel_path=rel, emit=emit,
                      llm_url=llm_url, session=session)
    return await council.ask_pal_turn(user_ask)


# ---------------------------------------------------------------------------
# Reconvening
# ---------------------------------------------------------------------------

def reconvene_input(meta: dict[str, Any], prior_rel: str, *,
                    answer: str = "", excerpt: str = "") -> str:
    """The new council's `input`: the old brief's input, then what the old
    council actually produced.

    The prior output is carried as INPUT rather than as a statement because
    that is what it is to the new council — the thing on the table, not
    something one of them said. For an `answer` output that is the
    conclusion's text; for a `document` or a `composure` it is a reference
    line plus the first `RECONVENE_EXCERPT_CHARS` of the file, because the
    whole of a document would leave no window for the argument about it."""
    out = meta.get("output") or {}
    kind = out.get("kind") or "answer"
    lines = [(meta.get("input") or "").strip()]
    lines.append(f"\n---\n\nThe council in `{prior_rel}` has already sat on "
                 f"this. What it produced is the starting point now.")
    if kind == "answer":
        body = (answer or "").strip()
        lines.append(f"\nIts answer:\n\n{body}" if body
                     else "\nIt reached no answer worth carrying.")
    else:
        where = out.get("path") or "(unrecorded)"
        noun = "document" if kind == "document" else "composure"
        lines.append(f"\nIts {noun}: `{where}`.")
        body = (excerpt or "").strip()
        if body:
            cut = body[:RECONVENE_EXCERPT_CHARS]
            more = " …(truncated)" if len(body) > RECONVENE_EXCERPT_CHARS \
                else ""
            lines.append(f"\nThe first of it:\n\n{cut}{more}")
    return "\n".join(line for line in lines if line is not None).strip()


def reconvene_meta(prior: dict[str, Any], prior_rel: str, *,
                   answer: str = "", excerpt: str = "") -> dict[str, Any]:
    """The meta a reconvened council starts from: the same participants with
    the same charges and tints, the same parameters, constraints, output and
    round cap, a brief that carries the prior output forward, and a state
    machine wound back to `ready`."""
    meta = validate_meta({
        "input": reconvene_input(prior, prior_rel, answer=answer,
                                 excerpt=excerpt),
        "parameters": prior.get("parameters"),
        "constraints": prior.get("constraints"),
        # The output spec rides over whole, path included. A `document`
        # output pointed at a path that now exists is not silently
        # overwritten — `_check_output_path` asks, exactly as it did the
        # first time.
        "output": dict(prior.get("output") or {}),
        "participants": [dict(p) for p in prior.get("participants") or []],
        "order": prior.get("order"),
        "max_rounds": prior.get("max_rounds"),
        "status": "ready",
        "reconvene": True,
    })
    nxt = next_speaker(meta)
    meta["next"] = nxt["id"] if nxt else None
    return meta


# ---------------------------------------------------------------------------
# Setting one up
# ---------------------------------------------------------------------------

def default_participants(project_dir: Path) -> list[dict[str, Any]]:
    """The chief, every ENABLED readvisor, and the user — the setup card's
    starting checklist. `folder` carries the on-disk name so a readvisor
    renamed in its AGENT.md still resolves to its own two documents."""
    from . import prompt as prompt_mod
    rows: list[dict[str, Any]] = [
        {"id": "chief", "kind": "chief", "name": prompt_mod.chief_name()},
    ]
    rness = project_dir / "rness"
    for folder, enabled, _tip in prompt_mod.list_roles(rness):
        if not enabled:
            continue
        display = _readvisor_display(project_dir, folder)
        rows.append({"id": f"rv:{folder}", "kind": "readvisor",
                     "name": display, "folder": folder})
    rows.append({"id": "user", "kind": "user", "name": "you"})
    return rows


def _readvisor_display(project_dir: Path, folder: str) -> str:
    from . import prompt as prompt_mod
    rness = project_dir / "rness"
    path = prompt_mod._readvisors_dir(rness) / folder / "AGENT.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return folder
    return prompt_mod._display_name(text, folder)


def setup_meta(existing: dict[str, Any] | None, body: dict[str, Any],
               project_dir: Path) -> dict[str, Any]:
    """Validate a setup payload into a council meta. `setup` → `ready`."""
    base = dict(existing or {})
    for key in ("input", "parameters", "constraints"):
        if key in body:
            base[key] = _text(body.get(key))
    if "output" in body:
        base["output"] = body.get("output")
    if "max_rounds" in body:
        base["max_rounds"] = body.get("max_rounds")
    rows = body.get("participants")
    if rows is None and not base.get("participants"):
        rows = default_participants(project_dir)
    if rows is not None:
        base["participants"] = _carry_folders(rows, base.get("participants"))
    base["order"] = "round-robin"
    meta = validate_meta(base)
    if meta["status"] in ("setup", "ready"):
        meta["status"] = "ready"
    nxt = next_speaker(meta)
    meta["next"] = nxt["id"] if nxt else None
    return meta


def _carry_folders(rows: object, previous: object) -> list[dict[str, Any]]:
    """Keep each participant's `folder` (its on-disk readvisor directory)
    across a setup POST that only sends ids, kinds and names. Losing it would
    make `identity_for` fall back to the display name, which is not the
    folder name for any readvisor whose AGENT.md has a prettier H1."""
    prior = {str(p.get("id")): p for p in (previous or []) if isinstance(p, dict)}
    out: list[dict[str, Any]] = []
    for row in (rows if isinstance(rows, list) else []):
        if not isinstance(row, dict):
            out.append(row)
            continue
        entry = dict(row)
        if not entry.get("folder"):
            was = prior.get(str(entry.get("id"))) or {}
            folder = was.get("folder")
            if not folder and str(entry.get("id", "")).startswith("rv:"):
                folder = str(entry["id"])[3:]
            if folder:
                entry["folder"] = folder
        out.append(entry)
    return out


__all__ = [
    "EVENT", "CouncilError", "Council", "STATUSES", "PARTICIPANT_KINDS",
    "OUTPUT_KINDS", "OUTPUT_KINDS_LANDED", "COMPOSURE_OUTPUT_FORMS",
    "MAX_ROUNDS_CAP", "MAX_CHARGE_CHARS", "RECONVENE_EXCERPT_CHARS",
    "CTX_FALLBACK", "CTX_CLOUD", "FOLD_AT", "MIN_SHARE", "MAX_TOKENS",
    "READVISOR_TINTS", "CHIEF_TINT", "USER_TINT", "CONCLUSION_TINT",
    "PAL_TINT", "PAL_CALL", "PAL_DISTILL", "PAL_PROMPT_CHARS",
    "OUTLINE_RETRY",
    "build_messages", "share_for", "fold_summary", "first_sentence",
    "read_statements", "brief_text", "brief_markdown", "output_sentence",
    "next_speaker", "advance", "speakers",
    "validate_meta", "validate_output", "validate_participants",
    "setup_meta", "default_participants", "identity_for",
    "chief_framing", "readvisor_framing", "conclusion_framing",
    "strip_tool_calls", "clean_statement", "estimate_tokens",
    "resolve_n_ctx", "probe_n_ctx", "run_council_turn", "turn_in_flight",
    "busy_paths", "reset_runtime", "Statement", "TurnResult",
    "outline_composure", "output_composure_path", "strip_code_fence",
    "pal_participant", "pal_statement", "ask_pal_turn",
    "reconvene_meta", "reconvene_input",
]
