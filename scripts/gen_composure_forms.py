#!/usr/bin/env python3
"""Regenerate the shipped composure forms in `defaults/composure-forms/`.

    uv run python scripts/gen_composure_forms.py            # write
    uv run python scripts/gen_composure_forms.py --check    # verify only

The five shipped forms are real `.comp` files, and they are produced
THROUGH `composure.dumps` rather than hand-written, for the same reason the
convert suite builds its `.docx` fixture at test time: a template that was
typed by hand drifts away from the serializer that has to read it back. Run
this after any change to the format or the style block, and commit both the
script and its output.

Deterministic: the timestamps are pinned, so a regeneration that changes
nothing produces no diff.

Geometry, in world units (1 unit = 1 CSS px at zoom 1):

- `blank`    — one fullport (816×1056) text module, one empty page.
- `cards`    — a 4×4 grid of 360×240 text cards, 48-unit gutters, three
               pre-tinted yellow so the swatches are discoverable.
- `scaffold` — a premise card across the top, five act columns (header card,
               three beat cards, one continuity card each), and an
               endings/denouement row underneath. Every card carries prompt
               text saying what belongs there — deliberately generic, because
               a scaffold is for any text that needs a visualized structure,
               not only for fiction.
- `journal`  — one fullport module, `kind=page`. The format guarantees at
               least one page per module, so "no pages yet" is expressed as a
               single empty page; the UI stamps and files it.
- `council`  — the brief module skeleton plus a `composure:council` block in
               `status: setup`. P5 fills in the behavior.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from enough import composure as C  # noqa: E402

# Pinned so regeneration is a no-op when nothing changed.
STAMP = "2026-09-17T00:00:00Z"

CARD_W, CARD_H = 360.0, 240.0
GUT = C.GUTTER
COL = CARD_W + GUT          # 408


def _module(mid: str, mtype: str, x: float, y: float, w: float, h: float,
            *, bg: str = "paper", title: str = "", markdown: str = "",
            z: int = 1) -> C.Module:
    m = C.Module(id=mid, type=mtype, x=x, y=y, w=w, h=h, z=z, bg=bg,
                 title=title, scale=1.0, cur=1)
    m.pages = [C.Page(n=1, rich=C.md_to_rich(markdown) if markdown else "")]
    return m


def _comp(title: str, form: str, kind: str, modules: list[C.Module],
          council: dict | None = None) -> C.Composure:
    c = C.Composure(title=title, form=form, kind=kind, rev=0,
                    created=STAMP, modified=STAMP, council=council)
    c.modules = modules
    return c


# ---------------------------------------------------------------------------
# blank
# ---------------------------------------------------------------------------

def form_blank() -> C.Composure:
    w, h = C.FULLPORT
    return _comp("Untitled", "blank", "page",
                 [_module("m1", "text", 0, 0, w, h)])


# ---------------------------------------------------------------------------
# cards
# ---------------------------------------------------------------------------

_CARD_PROMPTS = [
    "One idea per card. Drag them around until the order is the argument.",
    "A card can hold a scene, a section, a claim, a task, a question.",
    "Tint a card to mark it — the swatches mean whatever you decide they mean.",
]
# Cards 1, 6 and 11 arrive tinted, so the colour affordance is visible
# before anybody opens the inspector.
_TINTED = {1, 6, 11}


def form_cards() -> C.Composure:
    modules: list[C.Module] = []
    n = 0
    for row in range(4):
        for col in range(4):
            n += 1
            text = _CARD_PROMPTS[n // 6] if n in _TINTED else ""
            modules.append(_module(
                f"m{n}", "text",
                col * COL, row * (CARD_H + GUT),
                CARD_W, CARD_H,
                bg="yellow" if n in _TINTED else "paper",
                markdown=text,
            ))
    return _comp("Cards", "cards", "board", modules)


# ---------------------------------------------------------------------------
# scaffold
# ---------------------------------------------------------------------------

PREMISE_MD = (
    "**Premise.** In a sentence or two: what is this piece, and what is "
    "different by the end of it?\n\n"
    "A scaffold suits anything that needs a visible structure — a story, an "
    "argument, a proposal, a course, a report. The five columns are five "
    "movements; rename them to whatever your material actually does."
)

ACT_TITLES = ("Act one", "Act two", "Act three", "Act four", "Act five")
ACT_MD = (
    "**{name}.** What this movement is *for*: the job it does that no other "
    "part of the piece can do. One line. If you cannot write it, the "
    "movement is not earning its place yet."
)
BEAT_MD = (
    "**Beat {i}.** One step. What happens here, what it costs, and what it "
    "makes possible next."
)
CONTINUITY_MD = (
    "**Continuity.** What has to stay true across this movement — facts, "
    "names, numbers, promises already made to the reader. Check this card "
    "before you revise the beats above it."
)
ENDING_MD = (
    ("**Climax.** Where the pressure built above is finally released. "
     "Name the moment, not the feeling."),
    ("**Denouement.** What settles afterwards: consequences, loose ends, the "
     "new normal."),
    ("**Last impression.** The final paragraph, slide or line — and what you "
     "want the reader left holding."),
)

ACT_HEADER_H = 120.0
BEAT_H = 160.0
CONTINUITY_H = 140.0
PREMISE_H = 180.0


def form_scaffold() -> C.Composure:
    modules: list[C.Module] = []
    total_w = 5 * CARD_W + 4 * GUT
    modules.append(_module("m1", "text", 0, 0, total_w, PREMISE_H,
                           bg="lilac", title="Premise", markdown=PREMISE_MD))
    top = PREMISE_H + GUT
    next_id = 2
    for col, name in enumerate(ACT_TITLES):
        x = col * COL
        y = top
        modules.append(_module(f"m{next_id}", "text", x, y, CARD_W,
                               ACT_HEADER_H, bg="blue", title=name,
                               markdown=ACT_MD.format(name=name)))
        next_id += 1
        y += ACT_HEADER_H + GUT
        for i in range(1, 4):
            modules.append(_module(f"m{next_id}", "text", x, y, CARD_W, BEAT_H,
                                   markdown=BEAT_MD.format(i=i)))
            next_id += 1
            y += BEAT_H + GUT
        modules.append(_module(f"m{next_id}", "text", x, y, CARD_W,
                               CONTINUITY_H, bg="gray", title="Continuity",
                               markdown=CONTINUITY_MD))
        next_id += 1
    bottom = top + ACT_HEADER_H + GUT + 3 * (BEAT_H + GUT) + CONTINUITY_H + GUT
    for i, md in enumerate(ENDING_MD):
        modules.append(_module(f"m{next_id}", "text", i * COL, bottom,
                               CARD_W, BEAT_H, bg="orange",
                               title=("Climax", "Denouement",
                                      "Last impression")[i],
                               markdown=md))
        next_id += 1
    return _comp("Scaffold", "scaffold", "board", modules)


# ---------------------------------------------------------------------------
# journal
# ---------------------------------------------------------------------------

def form_journal() -> C.Composure:
    w, h = C.FULLPORT
    return _comp("Journal", "journal", "page",
                 [_module("m1", "text", 0, 0, w, h)])


# ---------------------------------------------------------------------------
# council
# ---------------------------------------------------------------------------

COUNCIL_BRIEF_MD = (
    "**Input.** What the council is working from — the text, the question, "
    "the decision on the table.\n\n"
    "**Parameters.** How it should work: how many rounds, who speaks, what "
    "depth of answer you want.\n\n"
    "**Constraints.** What it must not do — length limits, tone, facts that "
    "are settled, things already tried.\n\n"
    "**Desired output.** What you want at the end: a decided answer, or a "
    "document written to a path in this project."
)

COUNCIL_META = {
    "input": "",
    "parameters": "",
    "constraints": "",
    "output": {"kind": "answer"},
    "participants": [],
    "order": "round-robin",
    "max_rounds": 3,
    "status": "setup",
    "round": 0,
    "next": None,
}


def form_council() -> C.Composure:
    return _comp(
        "Council", "council", "page",
        [_module("m1", "text", 0, 0, 816.0, 420.0, bg="paper",
                 title="Brief", markdown=COUNCIL_BRIEF_MD)],
        council=dict(COUNCIL_META),
    )


FORMS = {
    "blank": form_blank,
    "cards": form_cards,
    "council": form_council,
    "journal": form_journal,
    "scaffold": form_scaffold,
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="fail instead of writing when a form would change")
    args = ap.parse_args(argv)

    dest = C.shipped_forms_dir()
    dest.mkdir(parents=True, exist_ok=True)
    drift = 0
    for name, build in sorted(FORMS.items()):
        comp = build()
        text = C.dumps(comp)
        # Every shipped form must survive the parser it will be opened with.
        assert C.dumps(C.loads(text)) == text, f"{name} does not round-trip"
        path = dest / f"{name}{C.SUFFIX}"
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current == text:
            print(f"  ok      {path.name} ({len(comp.modules)} modules)")
            continue
        drift += 1
        if args.check:
            print(f"  DRIFT   {path.name} — run without --check to rewrite")
            continue
        path.write_text(text, encoding="utf-8")
        print(f"  wrote   {path.name} ({len(comp.modules)} modules)")
    if args.check and drift:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
