"""Scaffolds built the way the readvisor's tool builds them (a plectrum from the skill's examples, laid out by
`scaffolder.plectrum_ops`), then written in as the person writes (`source="ui"`). Shared by the lock, check and
export tests (0.8, lane W3-E5). Not a test module."""
from __future__ import annotations

from pathlib import Path

from enough import composure as C
from enough import scaffolder as SC

REPO = Path(__file__).resolve().parent.parent
EXAMPLES = REPO / "defaults" / "skills" / "scaffolder" / "references" / "examples"

#: The ten-slide deck, written in (box id in the plectrum → the person's words). The two speaker boxes and the
#: notes box are left as the example leaves them, except one speaker note, so a PPTX carries notes.
DECK_WORDS = {
    "cover-title": "A garden on Mill Lane",
    "cover-who": "Mill Lane Growers, for the planning committee",
    "the-ask-in-one-sentence": "We ask the comittee to lease the Mill Lane plot to us for five years.",
    "speaker-notes-the-ask": "Pause here. Let them read the ask before saying anything else.",
    "plot-headline": "Empty since 2019",
    "caption-to-the-photo": "The plot from the lane, October 2026.",
    "we-in-a-line": "Forty neighbours who already grow things",
    "what-we-have-done-already": "We have run the school garden for three years and raised the money for its shed.",
    "plan-body": "Twelve raised beds, a tool store and a path wide enough for a wheelchair.",
    "the-total": "Four thousand pounds",
    "where-the-money-comes-from": "Half from the parish fund, half from our own members.",
    "gets-headline": "What the town gets",
    "gets-1": "Fresh food for the food bank every week.",
    "gets-2": "A place for the school to learn outside.",
    "gets-3": "A tidy plot instead of a fenced-off one.",
    "the-questions-and-our-answers": "Who pays for water? We do. Who locks up? Two members each evening.",
    "the-first-step": "Sign the lease in January",
    "the-first-year": "Beds built by March, the first harvest in July.",
    "close-call": "Thank you",
    "close-contact": "growers@example.org",
}

PAGE_WORDS_FIRST = 6     # how many of the page's boxes get words
DOC_WORDS_FIRST = 8      # how many of the document's boxes get words


def build(project: Path, example: str, title: str, words: dict[str, str] | None = None,
          first: int | None = None) -> Path:
    """A scaffold at `rness/io/composure/<slug>.comp` from `EXAMPLES/<example>`, its plectrum beside it, and the
    person's words in the boxes `words` names (by plectrum id), or in the first `first` text boxes."""
    rel = f"rness/io/composure/{C.slugify(title)}.comp"
    path = project / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    plectrum_text = (EXAMPLES / example).read_text(encoding="utf-8")
    model = SC.loads(plectrum_text)
    comp = C.new_composure("scaffold", title)
    plan = SC.plectrum_ops(model, comp)
    C.save(path, comp)
    C.apply_ops(path, None, plan.ops, source="readvisor")
    SC.plectrum_path(path).write_text(SC.state_module().dumps(model, "plectrum"), encoding="utf-8")
    fill: dict[str, str] = {}
    if words:
        fill = {SC.module_id(k): v for k, v in words.items()}
    elif first:
        n = 0
        for b in model.boxes():
            if b["kind"] == "text" and b["as"] not in ("notes", "speaker") and n < first:
                fill[SC.module_id(b["id"])] = f"The words of {b['name'].lower()}, written by the person."
                n += 1
    ops = []
    for mid, text in fill.items():
        ops += [{"op": "set_page", "module": mid, "n": 1, "markdown": text},
                {"op": "update_module", "id": mid, "state": "written"}]
    if ops:
        C.apply_ops(path, None, ops, source="ui")
    return path


def deck(project: Path) -> Path:
    return build(project, "ten-slide-deck.md", "A garden on Mill Lane", DECK_WORDS)


def page(project: Path) -> Path:
    return build(project, "more-page.md", "More page", first=PAGE_WORDS_FIRST)


def document(project: Path) -> Path:
    return build(project, "document.md", "Recipe book", first=DOC_WORDS_FIRST)
