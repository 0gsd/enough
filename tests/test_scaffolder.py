"""The scaffolder in enough: `enough/scaffolder.py`, the tool `scaffold_from_plectrum`, and the
switch carried from the retired skill name `scaffold` to `scaffolder`.

The rule every test here leans on: the readvisor never writes a word into a box. A plectrum
builds and changes the frames and the boxes; the person's text, and a plec the person edited,
survive every update untouched.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from enough import broker
from enough import composure as C
from enough import composure_tools as CT
from enough import retired_names
from enough import scaffolder as SC
from enough import skeleton
from enough import tools as T

S = SC.state_module()
EXAMPLES = Path(__file__).resolve().parent.parent / "defaults" / "skills" / "scaffolder" / \
    "references" / "examples"
PLECTRUMS = ["more-page.md", "ten-slide-deck.md", "document.md"]


def plectrum(name: str):
    return S.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def apply(comp: C.Composure, ops: list[dict], source: str = "readvisor") -> C.Composure:
    draft = copy.deepcopy(comp)
    for op in ops:
        C._apply_one(draft, op, source)
    return draft


def frames_in_order(comp: C.Composure) -> list[str]:
    return C.scaffold_view(comp)["frames"]


# ---------------------------------------------------------------------------
# The adapter
# ---------------------------------------------------------------------------

def test_module_ids_are_stable_and_valid():
    mid = SC.module_id("cover-title")
    assert mid == SC.module_id("cover-title") and mid != SC.module_id("cover-who")
    assert C._MODULE_ID_RE.match(mid)


@pytest.mark.parametrize("name", PLECTRUMS)
def test_a_plectrum_becomes_frames_and_boxes_in_order(name: str):
    model = plectrum(name)
    comp = C.new_composure("scaffold", model.meta["title"])
    built = apply(comp, SC.plectrum_ops(model, comp).ops)
    view = C.scaffold_view(built)
    assert view["frames"] == [SC.module_id(f["id"]) for f in model.frames]
    for f in model.frames:
        held = view["boxes"][SC.module_id(f["id"])]
        assert sorted(held) == sorted(SC.module_id(b["id"]) for b in f["boxes"])
    assert not view["loose"]
    assert len(built.modules) == S.count(model)["parts"]
    boxes = [m for m in built.modules if m.type == C.BOX]
    assert all(not any(p.rich for p in m.pages) for m in boxes)
    # inside its frame, every box
    for m in boxes:
        f = built.module(m.frame)
        assert f.x <= m.x and m.x + m.w <= f.x + f.w + 0.01
        assert f.y <= m.y and m.y + m.h <= f.y + f.h + 0.01
    # and the plectrum comes back out whole, layout included
    back = S.as_plectrum(SC.state_from_composure(built, model))
    assert S.to_dict(back) == S.to_dict(model)
    # the same plectrum again changes nothing
    assert SC.plectrum_ops(model, built).ops == []


def test_a_deck_lays_its_slides_side_by_side_and_a_page_one_under_another():
    deck = plectrum("ten-slide-deck.md")
    comp = C.new_composure("scaffold", "deck")
    built = apply(comp, SC.plectrum_ops(deck, comp).ops)
    slides = [built.module(f) for f in frames_in_order(built)]
    assert all(f.shape == "slide" and f.h == C.SLIDE[1] for f in slides)
    assert all(a.x < b.x and a.y == b.y for a, b in zip(slides, slides[1:]))
    page = plectrum("more-page.md")
    comp = C.new_composure("scaffold", "page")
    built = apply(comp, SC.plectrum_ops(page, comp).ops)
    bands = [built.module(f) for f in frames_in_order(built)]
    assert all(a.y + a.h < b.y for a, b in zip(bands, bands[1:]))


def _edited_deck():
    """The deck's plectrum as the readvisor sends it after the person asked for changes."""
    model = plectrum("ten-slide-deck.md")
    model.box("the-ask-in-one-sentence")["target"] = "120c"
    model.box("plot-headline")["plec"] = "The readvisor's new idea for this plec."
    model.box("cover-who")["plec"] = "Who is asking, by name."
    caption = model.box("caption-to-the-photo")
    model.frame("the-plot-today")["boxes"].remove(caption)
    model.frame("who-we-are")["boxes"].append(caption)
    ask = model.frame("the-ask")
    ask["boxes"] = [b for b in ask["boxes"] if b["id"] != "speaker-notes-the-ask"]
    ask["boxes"].append({**copy.deepcopy(ask["boxes"][0]), "id": "the-ask-why-now",
                         "name": "Why now", "plec": "Why tonight and not next year.",
                         "target": "80c", "row": 2, "col": 1})
    who = model.frame("who-we-are")
    who["boxes"] = [b for b in who["boxes"] if b["id"] != "we-in-a-line"]
    frames = model.frames
    i, j = [f["id"] for f in frames].index("what-happens-next"), \
        [f["id"] for f in frames].index("thank-you")
    frames[i], frames[j] = frames[j], frames[i]
    frames.insert(1, {**copy.deepcopy(frames[0]), "id": "agenda", "name": "Agenda",
                      "boxes": [{**copy.deepcopy(frames[0]["boxes"][0]), "id": "agenda-list",
                                 "name": "The order of the evening",
                                 "plec": "Three things, in the order you will say them."}]})
    return model


def test_an_edited_plectrum_updates_without_touching_the_persons_text():
    model = plectrum("ten-slide-deck.md")
    comp = C.new_composure("scaffold", model.meta["title"])
    built = apply(comp, SC.plectrum_ops(model, comp).ops)
    ask, we, plot = (SC.module_id(i) for i in ("the-ask-in-one-sentence", "we-in-a-line",
                                               "plot-headline"))
    # The person writes into two boxes and rewrites one plec.
    built = apply(built, [
        {"op": "set_page", "module": ask, "n": 1, "markdown": "We ask for the plot."},
        {"op": "set_page", "module": we, "n": 1, "markdown": "Forty neighbours since 2019."},
        {"op": "update_module", "id": plot, "plec": "Say what gets dumped there."},
    ], source="ui")
    before = {m.id: [p.rich for p in m.pages] for m in built.modules}

    edited = _edited_deck()
    plan = SC.plectrum_ops(edited, built)
    for op in plan.ops:
        assert op["op"] not in ("set_page", "add_page", "remove_page")
        assert not {"markdown", "rich", "pages"} & set(op)
    after = apply(built, plan.ops)

    # the person's words, everywhere they were
    for mid in (ask, we):
        assert [p.rich for p in after.module(mid).pages] == before[mid]
    assert "we-in-a-line" not in {b["id"] for b in edited.boxes()}
    assert after.module(we) is not None and plan.kept_words == ["We, in a line"]
    # the person's plec stays theirs; a readvisor's plec is rewritten
    assert after.module(plot).plec == "Say what gets dumped there."
    assert plan.kept_plecs == ["The plot today"]
    assert after.module(SC.module_id("cover-who")).plec == "Who is asking, by name."
    # retargeted, moved, added, removed, reordered
    assert after.module(ask).target == "120c"
    assert after.module(SC.module_id("caption-to-the-photo")).frame == SC.module_id("who-we-are")
    assert after.module(SC.module_id("the-ask-why-now")).frame == SC.module_id("the-ask")
    assert after.module(SC.module_id("speaker-notes-the-ask")) is None
    assert frames_in_order(after) == [SC.module_id(f["id"]) for f in edited.frames]
    # and the state read back holds the text and the edited plectrum's shape
    state = SC.state_from_composure(after, edited)
    assert state.box("the-ask-in-one-sentence")["text"] == "We ask for the plot."
    assert state.box("plot-headline")["plec_by"] == "person"
    assert [f["id"] for f in state.frames] == [f["id"] for f in edited.frames]


def test_the_composure_refuses_a_readvisors_text_in_a_box():
    """The tool never tries; the composure would refuse it anyway."""
    model = plectrum("more-page.md")
    comp = C.new_composure("scaffold", model.meta["title"])
    built = apply(comp, SC.plectrum_ops(model, comp).ops)
    with pytest.raises(C.ComposureError, match="never writes them"):
        apply(built, [{"op": "set_page", "module": SC.module_id("headline"), "n": 1,
                       "markdown": "Words."}])


def test_an_older_composure_is_not_a_scaffold_until_the_person_says():
    comp = C.from_outline("T", "scaffold", "# T\n\n## G\n\n### C\n")
    with pytest.raises(C.ComposureError, match="make this a scaffold"):
        SC.plectrum_ops(plectrum("more-page.md"), comp)


def test_the_state_written_from_a_composure_reads_back():
    model = plectrum("ten-slide-deck.md")
    comp = C.new_composure("scaffold", model.meta["title"])
    built = apply(comp, SC.plectrum_ops(model, comp).ops)
    mid = SC.module_id("cover-title")
    built = apply(built, [{"op": "set_page", "module": mid, "n": 1,
                           "markdown": "# A garden\n\non Mill Lane"},
                          {"op": "update_module", "id": mid, "state": "written"}], source="ui")
    state = SC.state_from_composure(built, model)
    text = S.dumps(state)
    again = S.loads(text)
    assert again.box("cover-title")["text"] == "# A garden\n\non Mill Lane"
    assert again.box("cover-title")["state"] == "written"
    assert "\\# A garden" in text
    assert S.dumps(again) == text


# ---------------------------------------------------------------------------
# The tool
# ---------------------------------------------------------------------------

@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    (home / "enough" / "config").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(broker, "CONFIG_PATH", home / "enough" / "config" / "broker.json")
    proj = tmp_path / "project"
    (proj / "rness" / "io" / "composure").mkdir(parents=True)
    return proj


def call(content: str, path: str | None = None) -> T.ToolCall:
    return T.ToolCall(name="scaffold_from_plectrum", path=path, content=content, command=None,
                      url=None, extra={}, raw="", span=(0, 0))


def test_the_tool_builds_then_updates(project: Path):
    text = (EXAMPLES / "ten-slide-deck.md").read_text(encoding="utf-8")
    out = CT.run_scaffold_from_plectrum(project, call("\n" + text))
    assert out.ok, out.body
    assert out.body.startswith("This is 11 frames and 25 boxes, 36 parts in all.")
    rel = out.key
    comp = C.load(project / rel)
    assert comp.form == "scaffold" and comp.title == "A garden on Mill Lane"
    assert len(comp.modules) == 36
    assert out.side_effects[C.EVENT]["created"] is True
    side = project / rel.replace(".comp", ".plectrum.md")
    assert S.to_dict(S.loads(side.read_text(encoding="utf-8"))) == S.to_dict(S.loads(text))

    C.apply_ops(project / rel, None, [{"op": "set_page", "module": SC.module_id("cover-title"),
                                      "n": 1, "markdown": "A garden on Mill Lane"}], source="ui")
    edited = S.dumps(_edited_deck(), "plectrum")
    again = CT.run_scaffold_from_plectrum(project, call(edited, rel))
    assert again.ok, again.body
    assert "updated" in again.body and "Why now" in again.body
    comp = C.load(project / rel)
    assert C.rich_to_md(comp.module(SC.module_id("cover-title")).pages[0].rich).strip() == \
        "A garden on Mill Lane"
    same = CT.run_scaffold_from_plectrum(project, call(edited, rel))
    assert same.ok and "nothing changed" in same.body


def test_the_tool_refuses_past_the_module_cap_and_builds_nothing(project: Path):
    text = (EXAMPLES / "document.md").read_text(encoding="utf-8").replace(
        "repeat: 24", "repeat: 40")
    out = CT.run_scaffold_from_plectrum(project, call(text))
    assert not out.ok
    assert out.body.startswith("This is 43 frames and 205 boxes, 248 parts in all.")
    assert "holds 200 modules" in out.body and "two scaffolds" in out.body
    assert not list((project / "rness" / "io" / "composure").iterdir())


def test_the_tool_refuses_a_state_an_outline_and_nothing(project: Path):
    state = (EXAMPLES / "ten-slide-deck.state.md").read_text(encoding="utf-8")
    out = CT.run_scaffold_from_plectrum(project, call(state))
    assert not out.ok and "never writes a box's text" in out.body
    outline = CT.run_scaffold_from_plectrum(project, call("# T\n\n## G\n\n### C\n"))
    assert not outline.ok and "Line 1:" in outline.body and "outline" in outline.body
    empty = CT.run_scaffold_from_plectrum(project, call("\n"))
    assert not empty.ok and "plectrum: 1" in empty.body
    assert not list((project / "rness" / "io" / "composure").iterdir())


def test_the_tool_refuses_a_composure_that_is_not_a_scaffold(project: Path):
    rel = "rness/io/composure/notes.comp"
    C.save(project / rel, C.from_outline("Notes", "cards", "# Notes\n\n## G\n\n### C\n"))
    out = CT.run_scaffold_from_plectrum(
        project, call((EXAMPLES / "more-page.md").read_text(encoding="utf-8"), rel))
    assert not out.ok and "not a scaffold" in out.body


def test_the_tool_is_gated_registered_documented_and_named_in_the_broker(project, monkeypatch):
    CT.register()
    assert T._DISPATCH["scaffold_from_plectrum"] is CT.run_scaffold_from_plectrum
    assert T._TRACE_TOGGLE["scaffold_from_plectrum"] == "trace_log_enabled"
    assert "scaffold_from_plectrum" in CT.TOOL_NAMES
    from enough import prompt
    assert "`scaffold_from_plectrum`" in prompt.COMPOSURE_TOOL_INSTRUCTIONS
    assert "`scaffold_from_plectrum`" in prompt.COMPOSURE_LEAN_INSTRUCTIONS
    toggle = next(t for t in broker.TOGGLES if t.key == "composure_enabled")
    assert "scaffold_from_plectrum" in toggle.description
    monkeypatch.setattr(broker, "is_enabled", lambda key: key != "composure_enabled")
    out = CT.run_scaffold_from_plectrum(
        project, call((EXAMPLES / "more-page.md").read_text(encoding="utf-8")))
    assert not out.ok and "composure tools are disabled" in out.body
    assert not list((project / "rness" / "io" / "composure").iterdir())


# ---------------------------------------------------------------------------
# `scaffold` → `scaffolder`: the switch carries over
# ---------------------------------------------------------------------------

def test_the_rename_is_on_the_table():
    assert retired_names.SKILLS == {"scaffold": "scaffolder"}


def _skills(tmp_path: Path, *, link: bool = True, off: bool = False) -> Path:
    skills = tmp_path / "project" / "rness" / "skills"
    skills.mkdir(parents=True)
    if link:
        (skills / "scaffold").symlink_to(tmp_path / "an-old-install" / "skills" / "scaffold")
    (skills / ".disabled").write_text("# off\nanalyzer\n" + ("scaffold\n" if off else ""),
                                      encoding="utf-8")
    return skills


def _off(skills: Path) -> set[str]:
    return {ln.strip() for ln in (skills / ".disabled").read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.startswith("#")}


@pytest.mark.parametrize("off", [False, True])
def test_a_project_keeps_its_switch_under_the_new_name(tmp_path, monkeypatch, off: bool):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    skills = _skills(tmp_path, off=off)
    defaults = skeleton._install_defaults_root()
    skeleton._populate_skill_symlinks(skills.parent.parent, defaults)
    new = skills / "scaffolder"
    assert new.is_symlink() and new.resolve() == (defaults / "skills" / "scaffolder").resolve()
    assert not (skills / "scaffold").exists() and not (skills / "scaffold").is_symlink()
    assert ("scaffolder" in _off(skills)) is off
    assert "scaffold" not in _off(skills) and "analyzer" in _off(skills)


def test_a_materialized_copy_is_left_alone_and_reported(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    skills = _skills(tmp_path, link=False)
    (skills / "scaffold").mkdir()
    (skills / "scaffold" / "SKILL.md").write_text("---\nname: scaffold\n---\nmine\n",
                                                  encoding="utf-8")
    src = skeleton._install_defaults_root() / "skills"
    reports = skeleton.carry_retired_skills(skills, src)
    assert len(reports) == 1 and "left as it is" in reports[0] and "'scaffolder'" in reports[0]
    assert (skills / "scaffold" / "SKILL.md").read_text(encoding="utf-8").endswith("mine\n")
    assert not (skills / "scaffolder").exists()
    skeleton._populate_skill_symlinks(skills.parent.parent, src.parent)
    assert (skills / "scaffold").is_dir() and not (skills / "scaffold").is_symlink()
    assert "scaffolder" in _off(skills)  # it arrives as any new skill does


def test_nothing_to_carry_changes_nothing(tmp_path):
    skills = _skills(tmp_path, link=False)
    before = (skills / ".disabled").read_text(encoding="utf-8")
    assert skeleton.carry_retired_skills(skills, skeleton._install_defaults_root() / "skills") == []
    assert (skills / ".disabled").read_text(encoding="utf-8") == before
    assert not (skills / "scaffolder").exists()
