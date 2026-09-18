"""P5b — `composure.from_outline` and the `composure_from_outline` tool.

The `scaffold` skill teaches the grammar and this parser implements it, so
the skill's own two worked examples are the fixtures: they are lifted out of
`defaults/skills/scaffold/references/structure.md` at test time rather than
copied here, which means the skill cannot drift away from the parser without
this file going red.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from enough import broker
from enough import composure as C
from enough import composure_tools as CT
from enough import tools as T
from enough.composure import ComposureError

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "defaults" / "skills" / "scaffold"


# ---------------------------------------------------------------------------
# The skill's own worked examples
# ---------------------------------------------------------------------------

def _dedent_block(text: str) -> str:
    """The reference file indents its outlines by four spaces (they are
    markdown code blocks). Strip exactly that."""
    return "\n".join(line[4:] if line.startswith("    ") else line
                     for line in text.splitlines())


def _example(start: str, stop: str) -> str:
    body = (SKILL / "references" / "structure.md").read_text(encoding="utf-8")
    a = body.index(start)
    b = body.index(stop, a)
    return _dedent_block(body[a:b])


@pytest.fixture()
def story() -> str:
    return _example("# The Keeper's Stipend", "Then:")


@pytest.fixture()
def essay() -> str:
    return _example("# Not the Privacy Essay", "Then the same tool call")


@pytest.fixture()
def plan() -> str:
    return _example("# Six Languages by March", "# Reminders")


def test_the_skill_and_the_parser_agree_about_the_grammar():
    """Every rule SKILL.md states, asserted against the parser."""
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "composure_from_outline" in skill
    for form in C.OUTLINE_FORMS:
        assert f"`{form}`" in skill
    for name in ("premise", "logline", "thesis"):
        assert name in skill and name in C.TOP_GROUPS
    for name in ("ending", "endings", "denouement", "resolution"):
        assert name in skill and name in C.BOTTOM_GROUPS
    assert C.GAP_PREFIX in skill


def test_worked_example_a_lands_as_the_skill_describes_it(story: str):
    doc = C.parse_outline(story)
    assert doc.title == "The Keeper's Stipend"
    assert [g.name for g in doc.groups] == [
        "Premise", "Act one — the inventory", "Act two — the stipend",
        "Act three — the keeping", "Threads", "Ending"]
    assert doc.card_count() == 15          # the skill's own count
    gaps = [c for g in doc.groups for c in g.cards if c.is_gap]
    assert len(gaps) == 1
    assert gaps[0].title == "[gap: why does she not sell?]"

    comp = C.from_outline("The Keeper's Stipend", "scaffold", story)
    assert comp.kind == "board"
    assert len(comp.modules) == 15 + 6     # a header card per group
    heads = [m for m in comp.modules if m.bg == "gray"]
    assert [m.title for m in heads] == [g.name for g in doc.groups]

    # Premise spans the top, above everything.
    premise = heads[0]
    assert premise.y == 0.0 and premise.x == 0.0
    assert premise.w > C.CARD_W
    # Three act columns plus a continuity column, left to right, level.
    columns = heads[1:5]
    assert len({m.y for m in columns}) == 1
    assert [m.x for m in columns] == [0.0, 368.0, 736.0, 1104.0]
    assert premise.w == columns[-1].x + C.CARD_W
    # The ending is the bottom row, under every column.
    ending = heads[5]
    assert ending.y > max(m.y + m.h for m in comp.modules if m is not ending
                          and m.y < ending.y)
    assert ending.w == premise.w
    # The gap card is orange, titled "gap", and keeps its question.
    gap = next(m for m in comp.modules if m.bg == C.GAP_BG)
    assert gap.title == C.GAP_TITLE
    assert "why does she not sell?" in C.rich_to_md(gap.pages[0].rich)
    # The user's own phrasing survives.
    threads = C.rich_to_md(
        next(m for m in comp.modules if m.title == "Translation as the life"
             ).pages[0].rich)
    assert "carrying things between languages" in threads


def test_worked_example_b_puts_thesis_on_top_and_close_along_the_bottom(
        essay: str):
    doc = C.parse_outline(essay)
    assert doc.title == "Not the Privacy Essay"
    assert [g.name for g in doc.groups] == [
        "Thesis", "Grounds", "Warrants", "Counter-case", "Unplaced", "Close"]
    assert sum(1 for g in doc.groups for c in g.cards if c.is_gap) == 3
    comp = C.from_outline("", "scaffold", essay)
    assert comp.title == "Not the Privacy Essay"   # the `# ` line is the fallback
    heads = [m for m in comp.modules if m.bg == "gray"]
    top, bottom = heads[0], heads[-1]
    assert top.title == "Thesis" and top.y == 0.0
    assert bottom.title == "Close" and bottom.y == max(m.y for m in heads)
    assert top.w == bottom.w > C.CARD_W
    assert len([m for m in comp.modules if m.bg == C.GAP_BG]) == 3


def test_the_plan_fragment_parses_with_list_and_heading_cards(plan: str):
    doc = C.parse_outline(plan)
    assert [g.name for g in doc.groups] == [
        "Goal", "Phase 1 — extract", "Phase 2 — translate", "Dependencies",
        "Risks"]
    # No premise-like or ending-like group here: every group is a column.
    comp = C.from_outline("Six Languages by March", "scaffold", plan)
    heads = [m for m in comp.modules if m.bg == "gray"]
    assert len({m.y for m in heads}) == 1
    assert [m.x for m in heads] == [0.0, 368.0, 736.0, 1104.0, 1472.0]


# ---------------------------------------------------------------------------
# The grammar, rule by rule
# ---------------------------------------------------------------------------

def test_top_level_list_items_are_cards_and_nested_ones_are_body():
    doc = C.parse_outline(
        "# T\n\n## Options\n\n- keep it\n  it is paid for\n- sell it\n"
        "    - but not to him\n\n## Risks\n\n1. rain\n2) hail\n")
    assert [c.title for c in doc.groups[0].cards] == ["keep it", "sell it"]
    assert doc.groups[0].cards[0].body == "it is paid for"
    assert "but not to him" in doc.groups[0].cards[1].body
    assert [c.title for c in doc.groups[1].cards] == ["rain", "hail"]


def test_deeper_headings_and_tables_are_body_not_structure():
    doc = C.parse_outline(
        "# T\n\n## G\n\n### A card\n\n#### not a group\n\n| a | b |\n"
        "| - | - |\n\nstill the body\n")
    assert len(doc.groups) == 1 and len(doc.groups[0].cards) == 1
    body = doc.groups[0].cards[0].body
    assert "#### not a group" in body and "| a | b |" in body


def test_a_card_before_any_group_opens_an_implicit_one():
    doc = C.parse_outline("# T\n\n### Lonely\n\nbody\n")
    assert [g.name for g in doc.groups] == ["Cards"]
    assert doc.groups[0].cards[0].title == "Lonely"


def test_a_gap_card_is_orange_titled_gap_and_keeps_its_question():
    doc = C.parse_outline(
        "# T\n\n## G\n\n### [gap: who pays?]\n\nNobody says.\n")
    card = doc.groups[0].cards[0]
    assert card.is_gap
    assert card.text().startswith("[gap: who pays?]")
    assert "Nobody says." in card.text()
    comp = C.from_outline("T", "scaffold", "# T\n\n## G\n\n### [gap: who?]\n")
    gap = next(m for m in comp.modules if m.bg == C.GAP_BG)
    assert gap.title == "gap"
    # A card whose BODY opens with [gap counts too.
    doc2 = C.parse_outline("# T\n\n## G\n\n- something\n\n  [gap: really?]\n")
    assert not doc2.groups[0].cards[0].is_gap   # title decides when there is one


def test_the_title_argument_wins_over_the_hash_line():
    comp = C.from_outline("Override", "scaffold", "# In the outline\n\n## G\n\n### C\n")
    assert comp.title == "Override"
    assert C.from_outline("", "scaffold",
                          "# In the outline\n\n## G\n\n### C\n"
                          ).title == "In the outline"
    assert C.from_outline("", "scaffold", "## G\n\n### C\n").title == "Untitled"


# ---------------------------------------------------------------------------
# Forms
# ---------------------------------------------------------------------------

def test_cards_form_makes_a_row_per_group():
    comp = C.from_outline("Set", "cards",
                          "# Set\n\n## A\n\n- one\n- two\n\n## B\n\n- three\n")
    assert comp.kind == "board"
    heads = [m for m in comp.modules if m.bg == "gray"]
    assert [m.title for m in heads] == ["A", "B"]
    assert [m.x for m in heads] == [0.0, 0.0]        # a column of headers
    assert heads[0].y < heads[1].y                   # rows, top to bottom
    row = [m for m in comp.modules if m.bg != "gray" and m.y == heads[0].y]
    assert [m.title for m in row] == ["one", "two"]
    assert row[0].x < row[1].x


def test_blank_form_is_one_fullport_module_with_the_whole_outline():
    src = "# Doc\n\n## A\n\n### B\n\nbody text\n"
    comp = C.from_outline("Doc", "blank", src)
    assert comp.kind == "page" and len(comp.modules) == 1
    m = comp.modules[0]
    assert (m.w, m.h) == C.FULLPORT
    md = C.rich_to_md(m.pages[0].rich)
    assert "## A" in md and "body text" in md


def test_the_form_supplies_the_kind_not_its_placeholder_modules():
    """Every shipped form ships content. A scaffolded composure of somebody's
    actual story must not arrive with "Act one goes here" still on it."""
    for form in C.OUTLINE_FORMS:
        shipped = C.new_composure(form)
        made = C.from_outline("T", form, "# T\n\n## G\n\n### C\n\nbody\n")
        shipped_titles = {m.title for m in shipped.modules if m.title}
        made_titles = {m.title for m in made.modules if m.title}
        assert not (shipped_titles & made_titles) or form == "blank"
        assert all(m.id.startswith("m") for m in made.modules)


# ---------------------------------------------------------------------------
# Determinism, wrapping, caps
# ---------------------------------------------------------------------------

def test_the_layout_is_deterministic():
    src = "# T\n\n## Premise\n\n### L\n\none\n\n## A\n\n### x\n\ntwo\n"
    a = C.dumps(C.from_outline("T", "scaffold", src))
    b = C.dumps(C.from_outline("T", "scaffold", src))
    # Only the timestamps differ, and they are the composure's, not the
    # layout's — strip them and the documents are byte-identical.
    strip = lambda s: re.sub(r'content="20\d\d-[^"]*"', "", s)  # noqa: E731
    assert strip(a) == strip(b)


def test_a_group_over_twelve_cards_wraps_into_a_second_column():
    src = "# T\n\n## Act one\n\n" + "".join(
        f"### Beat {i}\n\nsomething happens, number {i}.\n\n"
        for i in range(1, 16))
    comp = C.from_outline("T", "scaffold", src)
    heads = [m for m in comp.modules if m.bg == "gray"]
    assert [m.title for m in heads] == ["Act one", "Act one (cont.)"]
    assert heads[0].x == 0.0 and heads[1].x == C.CARD_W + C.COL_GAP
    assert heads[0].y == heads[1].y
    first = [m for m in comp.modules if m.x == 0.0 and m.bg != "gray"]
    second = [m for m in comp.modules
              if m.x == heads[1].x and m.bg != "gray"]
    assert len(first) == C.MAX_CARDS_PER_COLUMN and len(second) == 3
    # ...rather than a mile-high stack.
    assert max(m.y + m.h for m in first) < 3000


def test_card_heights_track_the_text_and_stay_inside_the_cap():
    short = C.from_outline("T", "scaffold", "# T\n\n## G\n\n### C\n\nsmall\n")
    long = C.from_outline(
        "T", "scaffold", "# T\n\n## G\n\n### C\n\n" + "word " * 4000)
    sc = next(m for m in short.modules if m.title == "C")
    lc = next(m for m in long.modules if m.title == "C")
    assert lc.h > sc.h
    assert lc.h == C.CARD_H_MAX
    # Cards in a column never overlap.
    comp = C.from_outline("T", "scaffold", "# T\n\n## G\n\n"
                          + "".join(f"### C{i}\n\n{'w ' * (i * 40)}\n\n"
                                    for i in range(1, 7)))
    cards = sorted((m for m in comp.modules if m.bg != "gray"),
                   key=lambda m: m.y)
    for a, b in zip(cards, cards[1:]):
        assert a.y + a.h <= b.y


def test_an_outline_over_the_module_cap_is_refused_with_the_fix():
    src = "# T\n\n" + "".join(
        f"## G{g}\n\n" + "".join(f"### c{g}-{i}\n\nx\n\n" for i in range(12))
        for g in range(20))
    with pytest.raises(ComposureError, match="a composure holds"):
        C.from_outline("T", "scaffold", src)


def test_malformed_outlines_get_a_sentence_not_a_traceback():
    with pytest.raises(ComposureError, match="has no groups"):
        C.from_outline("T", "scaffold", "just prose, no headings")
    with pytest.raises(ComposureError, match="has no groups"):
        C.from_outline("T", "cards", "")
    with pytest.raises(ComposureError, match="unknown outline form"):
        C.outline_ops(C.parse_outline("# a\n## g\n### c"), "storyboard")
    # A group with no cards is allowed — it is a column waiting to be filled.
    comp = C.from_outline("T", "scaffold", "# T\n\n## Empty\n\n## G\n\n### C\n")
    assert [m.title for m in comp.modules if m.bg == "gray"] == ["Empty", "G"]


# ---------------------------------------------------------------------------
# The tool
# ---------------------------------------------------------------------------

@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    (home / "enough" / "config").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(broker, "CONFIG_PATH",
                        home / "enough" / "config" / "broker.json")
    proj = tmp_path / "project"
    (proj / "rness" / "io" / "composure").mkdir(parents=True)
    return proj


def call(**tags) -> T.ToolCall:
    content = tags.pop("content", None)
    return T.ToolCall(name="composure_from_outline", path=tags.pop("path", None),
                      content=content, command=None, url=None, extra=tags,
                      raw="", span=(0, 0))


def test_the_tool_writes_the_file_and_reports_the_ids(project: Path,
                                                      story: str):
    out = CT.run_composure_from_outline(project, call(
        title="The Keeper's Stipend", form="scaffold", content="\n" + story))
    assert out.ok, out.body
    rel = out.key
    assert rel.startswith("rness/io/composure/") and rel.endswith(".comp")
    assert (project / rel).is_file()
    assert "6 group(s), 15 card(s), 21 modules" in out.body
    assert "1 gap card(s)" in out.body
    # The outline it returns carries the ids the model quotes back.
    comp = C.load(project / rel)
    for m in comp.modules:
        assert f"{m.id}  text" in out.body
    # It went through the ops door, so the canvas hears about it.
    assert out.side_effects[C.EVENT]["source"] == "readvisor"
    assert out.side_effects[C.EVENT]["created"] is True


def test_the_tool_is_gated_by_the_broker_toggle(project: Path,
                                                monkeypatch):
    monkeypatch.setattr(broker, "is_enabled", lambda key: key != "composure_enabled")
    out = CT.run_composure_from_outline(project, call(
        title="T", form="scaffold", content="\n# T\n\n## G\n\n### C\n"))
    assert not out.ok
    assert "composure tools are disabled" in out.body
    assert not list((project / "rness" / "io" / "composure").iterdir())


def test_the_tool_is_registered_and_traced():
    CT.register()
    assert "composure_from_outline" in T._DISPATCH
    assert T._TRACE_TOGGLE["composure_from_outline"] == "trace_log_enabled"
    assert "composure_from_outline" in CT.TOOL_NAMES


def test_the_tool_names_the_grammar_when_it_is_handed_nothing(project: Path):
    empty = CT.run_composure_from_outline(project, call(title="T", content="\n"))
    assert not empty.ok and "'## ' per group" in empty.body
    bad = CT.run_composure_from_outline(project, call(
        title="T", form="storyboard", content="\n# T\n## G\n### C\n"))
    assert not bad.ok and "unknown outline form" in bad.body
    untitled = CT.run_composure_from_outline(project, call(
        form="scaffold", content="\n## G\n\n### C\n"))
    assert not untitled.ok and "no title" in untitled.body


def test_the_tool_is_documented_in_the_prompt():
    from enough import prompt
    text = prompt.COMPOSURE_TOOL_INSTRUCTIONS
    assert "`composure_from_outline` `<title>` `<form>` `<content>`" in text
    assert "a WHOLE composure" in text
    # The grammar fits in twelve lines, as the spec asks.
    start = text.index("The outline grammar, entire:")
    block = text[start:text.index("\nRules:", start)]
    assert len([ln for ln in block.splitlines() if ln.strip()]) <= 12
    for word in ("premise", "logline", "thesis", "[gap", "scaffold", "cards",
                 "blank"):
        assert word in block
