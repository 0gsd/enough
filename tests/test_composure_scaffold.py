"""The scaffold in composure (0.8, lanes E1 and E2): the plecholder
(`scaffold-box`), frames in order, the `composure:scaffold` block, and the
rule that the readvisor never writes a box's text.

What must not move is asserted here too: every composure without a frame
or a box keeps its bytes, an old `form=scaffold` file is never converted on
open, and an outline laid over the scaffold form (the outline tool, the
council's output) gives exactly the plane it gave in 0.7.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from enough import broker
from enough import composure as C
from enough import composure_tools as CT
from enough import council as K
from enough import tools as T
from enough.composure import ComposureError

REPO = Path(__file__).resolve().parent.parent
OLD_SCAFFOLD = REPO / "tests" / "fixtures" / "composure" / "scaffold-form-0.7.comp"
#: The last commit before the scaffold: its composure.py plays "an older
#: enough" in the forward-compatibility test.
BEFORE_SCAFFOLD = "3cf8a60"

sys.path.insert(0, str(REPO / "tests"))
import test_composure_outline as TO  # noqa: E402
import test_council_output as TC  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def scaf(tmp_path: Path) -> Path:
    path = tmp_path / "rness" / "io" / "composure" / "s.comp"
    path.parent.mkdir(parents=True, exist_ok=True)
    C.save(path, C.new_composure("scaffold", "Landing page"))
    return path


def ops(path: Path, *op_list, source: str = "ui") -> C.OpsResult:
    return C.apply_ops(path, None, list(op_list), source=source)


def first_frame(path: Path) -> str:
    return C.scaffold_view(C.load(path))["frames"][0]


def build_scaffold(path: Path) -> dict[str, str]:
    """Two page frames, three boxes (one graphic), the person's words in
    one of them."""
    f1 = first_frame(path)
    r = ops(path,
            {"op": "add_frame", "id": "mf2", "title": "Second"},
            {"op": "add_module", "type": "scaffold-box", "id": "mhead",
             "frame": f1, "title": "Headline",
             "plec": 'The one promise, in "plain" words [no jargon]',
             "target": "60c"},
            {"op": "add_module", "type": "scaffold-box", "id": "mpic",
             "frame": f1, "kind": "graphic", "shape": "16:9",
             "plec": "What the picture must show"},
            {"op": "add_module", "type": "scaffold-box", "id": "mbody",
             "frame": "mf2", "plec": "Why it matters", "target": "300w"},
            source="readvisor")
    assert r.rev == 1
    ops(path, {"op": "set_page", "module": "mbody", "n": 1,
               "markdown": "The person's own **words**."},
        {"op": "update_module", "id": "mbody", "state": "written"})
    return {"f1": f1, "f2": "mf2"}


def shape(comp: C.Composure) -> str:
    """A digest of everything a 0.7 composure was made of (the fields that
    existed before the scaffold). The table below was taken at 3cf8a60."""
    mods = []
    for m in comp.modules:
        mods.append([m.id, m.type, m.x, m.y, m.w, m.h, m.z, m.bg, m.scale,
                     m.title, m.cur, m.href, m.url, m.article, m.install,
                     m.refresh, m.cache, m.speaker, m.speaker_kind, m.turn,
                     sorted(m.extra.items()),
                     [[p.n, p.rich, p.date, p.filed, sorted(p.extra.items())]
                      for p in m.pages]])
    doc = [comp.title, comp.form, comp.kind, comp.version, comp.lang,
           comp.council, sorted(comp.meta_extra.items()), mods,
           [[s.id, s.width, s.color, s.points] for s in comp.strokes]]
    return hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Round trips
# ---------------------------------------------------------------------------

def test_a_scaffold_with_frames_and_boxes_round_trips_byte_stable(scaf: Path):
    build_scaffold(scaf)
    text = scaf.read_text(encoding="utf-8")
    comp = C.loads(text)
    assert comp.warnings == []
    assert C.dumps(comp) == text
    assert C.dumps(C.loads(C.dumps(comp))) == text
    head = comp.module("mhead")
    assert (head.type, head.plec_by, head.target, head.kind, head.state) == (
        C.BOX, "readvisor", "60c", "text", "empty")
    assert comp.module("mpic").shape == "16:9"
    assert C.rich_to_md(comp.module("mbody").pages[0].rich).strip() == \
        "The person's own **words**."
    assert 'data-plec="The one promise, in &quot;plain&quot; words [no jargon]"' in text


def test_every_composure_without_a_scaffold_keeps_its_bytes():
    """The scaffold's style rules are written only into a file that holds a
    frame or a box, so the four untouched forms and a 0.7 scaffold-form
    composure come back byte for byte."""
    for name in ("blank", "cards", "journal", "council"):
        raw = C.form_path(name).read_text(encoding="utf-8")
        assert C.dumps(C.loads(raw)) == raw, name
        assert "scaffold-box" not in raw
    old = OLD_SCAFFOLD.read_text(encoding="utf-8")
    comp = C.loads(old)
    assert comp.warnings == []
    assert C.dumps(comp) == old


def test_the_bare_browser_sees_the_plec_in_brackets_and_a_dashed_border(scaf: Path):
    build_scaffold(scaf)
    text = scaf.read_text(encoding="utf-8")
    assert 'content:"[" attr(data-plec) "]"' in text
    assert "border:1.5px dashed" in text
    assert C._STYLE_SCAFFOLD not in C.dumps(C.new_composure("blank"))


def _older_enough():
    """enough's composure.py as it was before the scaffold, imported beside
    today's. Skipped where the history is not there (a shallow clone)."""
    try:
        src = subprocess.run(
            ["git", "show", f"{BEFORE_SCAFFOLD}:enough/composure.py"],
            cwd=REPO, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip(f"git history to {BEFORE_SCAFFOLD} is not available")
    name = "enough._composure_before_scaffold"
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "enough"
    mod.__file__ = str(REPO / "enough" / "composure.py")
    sys.modules[name] = mod
    exec(compile(src, f"<{BEFORE_SCAFFOLD}:composure.py>", "exec"), mod.__dict__)
    return mod


def test_an_older_enough_still_renders_a_scaffolds_text_and_keeps_it(scaf: Path):
    old = _older_enough()
    build_scaffold(scaf)
    text = scaf.read_text(encoding="utf-8")
    there = old.loads(text)
    body = there.module("mbody")
    # An unknown type is kept and drawn as a text card: the words read.
    assert body.type == "scaffold-box"
    assert any("renders it as a text card" in w for w in there.warnings)
    assert old.model(there)["modules"][0]["known_type"] is False
    assert "words" in body.pages[0].rich
    assert body.extra["data-plec"] == "Why it matters"
    assert json.loads(there.meta_extra["scaffold"])["frames"][0] == first_frame(scaf)
    # ...and what the older enough writes back opens here as the same scaffold.
    back = C.loads(old.dumps(there))
    assert C.dumps(back) == text


# ---------------------------------------------------------------------------
# The rule: the readvisor never writes a box's text
# ---------------------------------------------------------------------------

def test_a_readvisor_write_to_a_boxs_text_is_refused_with_the_reason(scaf: Path):
    build_scaffold(scaf)
    before = scaf.read_text(encoding="utf-8")
    for op in ({"op": "set_page", "module": "mhead", "n": 1, "markdown": "Hi"},
               {"op": "add_page", "module": "mhead", "markdown": "Hi"},
               {"op": "remove_page", "module": "mbody", "n": 1}):
        with pytest.raises(ComposureError, match="the person's own words"):
            ops(scaf, op, source="readvisor")
    with pytest.raises(ComposureError, match="never writes them"):
        ops(scaf, {"op": "add_module", "type": "scaffold-box",
                   "plec": "x", "markdown": "words"}, source="readvisor")
    with pytest.raises(ComposureError, match="never writes them"):
        ops(scaf, {"op": "add_module", "type": "scaffold-box",
                   "pages": [{"markdown": "words"}]}, source="readvisor")
    with pytest.raises(ComposureError, match="delete their words"):
        ops(scaf, {"op": "remove_module", "id": "mbody"}, source="readvisor")
    with pytest.raises(ComposureError, match="into or out of a scaffold-box"):
        ops(scaf, {"op": "update_module", "id": "mbody", "type": "text"},
            source="readvisor")
    with pytest.raises(ComposureError, match="the person's mark"):
        ops(scaf, {"op": "update_module", "id": "mhead", "state": "written"},
            source="readvisor")
    with pytest.raises(ComposureError, match="the person's choice"):
        ops(scaf, {"op": "make_scaffold"}, source="readvisor")
    with pytest.raises(ComposureError, match="belong"):
        ops(scaf, {"op": "set_scaffold", "locked": True}, source="readvisor")
    assert scaf.read_text(encoding="utf-8") == before   # nothing landed


def test_the_readvisor_keeps_the_plec_target_kind_and_place(scaf: Path):
    ids = build_scaffold(scaf)
    r = ops(scaf,
            {"op": "update_module", "id": "mhead", "plec": "Sharper",
             "target": "80c", "x": 100, "y": 120, "w": 500, "h": 140},
            {"op": "update_module", "id": "mpic", "kind": "text", "shape": ""},
            {"op": "move_to_frame", "id": "mpic", "frame": ids["f2"]},
            {"op": "remove_module", "id": "mhead"},       # empty: allowed
            {"op": "set_scaffold", "thing": "document"},
            source="readvisor")
    comp = r.composure
    assert comp.module("mhead") is None
    assert comp.module("mpic").frame == ids["f2"]
    assert comp.module("mpic").kind == "text"
    assert C.scaffold_view(comp)["thing"] == "document"
    # The person's text is untouched by all of it.
    assert "words" in comp.module("mbody").pages[0].rich


def test_who_last_set_the_plec_is_recorded_from_the_source(scaf: Path):
    build_scaffold(scaf)
    ops(scaf, {"op": "update_module", "id": "mhead", "plec": "Mine now"})
    assert C.load(scaf).module("mhead").plec_by == "person"
    ops(scaf, {"op": "update_module", "id": "mhead", "plec": "Back"},
        source="readvisor")
    assert C.load(scaf).module("mhead").plec_by == "readvisor"
    with pytest.raises(ComposureError, match="plec_by is not sent"):
        ops(scaf, {"op": "update_module", "id": "mhead", "plec_by": "person"})
    # The person may write in a box, of course.
    ops(scaf, {"op": "set_page", "module": "mhead", "n": 1, "markdown": "Mine."})


def test_box_and_frame_fields_are_validated(scaf: Path):
    build_scaffold(scaf)
    f1 = first_frame(scaf)
    cases = [
        ({"op": "update_module", "id": "mhead", "target": "140x"}, "140c or 300w"),
        ({"op": "update_module", "id": "mhead", "shape": "16:9"}, "only a graphic box"),
        ({"op": "update_module", "id": "mpic", "shape": "huge"}, "proportion"),
        ({"op": "update_module", "id": "mhead", "kind": "video"}, "unknown box kind"),
        ({"op": "update_module", "id": "mhead", "state": "done"}, "unknown box state"),
        ({"op": "update_module", "id": "mhead", "frame": "mnope"}, "no frame"),
        ({"op": "add_module", "type": "text", "plec": "x"}, "belong"),
        ({"op": "add_module", "type": "frame"}, "add_frame"),
        ({"op": "update_module", "id": f1, "plec": "x"}, "a frame takes a shape"),
        ({"op": "update_module", "id": f1, "shape": "poster"}, "unknown frame shape"),
        ({"op": "update_module", "id": f1, "type": "text"}, "no module becomes a frame"),
        ({"op": "set_page", "module": f1, "n": 1, "markdown": "x"}, "holds no text"),
    ]
    for op, why in cases:
        with pytest.raises(ComposureError, match=why):
            ops(scaf, op)


# ---------------------------------------------------------------------------
# Frames in order
# ---------------------------------------------------------------------------

def test_frames_are_added_in_order_and_placed_by_the_thing(scaf: Path):
    f1 = first_frame(scaf)
    ops(scaf, {"op": "add_frame", "id": "mf2"},
        {"op": "add_frame", "id": "mf0", "at": 1})
    comp = C.load(scaf)
    assert C.scaffold_view(comp)["frames"] == ["mf0", f1, "mf2"]
    first, second = comp.module(f1), comp.module("mf2")
    assert (second.x, second.y) == (first.x, first.y + first.h + C.GUTTER)
    assert (second.w, second.h) == C.FULLPORT and second.shape == "page"
    # A deck's frames are slides, laid to the right.
    ops(scaf, {"op": "set_scaffold", "thing": "deck"},
        {"op": "add_frame", "id": "ms1"})
    comp = C.load(scaf)
    slide, prev = comp.module("ms1"), comp.module("mf2")
    assert (slide.w, slide.h) == C.SLIDE and slide.shape == "slide"
    assert (slide.x, slide.y) == (prev.x + prev.w + C.GUTTER, prev.y)


def test_reordering_needs_every_frame_once(scaf: Path):
    f1 = first_frame(scaf)
    ops(scaf, {"op": "add_frame", "id": "mf2"})
    ops(scaf, {"op": "reorder_frames", "order": ["mf2", f1]})
    assert C.scaffold_view(C.load(scaf))["frames"] == ["mf2", f1]
    for bad in (["mf2"], ["mf2", f1, f1], ["mf2", "mzz"]):
        with pytest.raises(ComposureError, match="every frame exactly once"):
            ops(scaf, {"op": "reorder_frames", "order": bad})


def test_a_frame_holding_boxes_is_not_removed(scaf: Path):
    ids = build_scaffold(scaf)
    with pytest.raises(ComposureError, match="still holds"):
        ops(scaf, {"op": "remove_module", "id": ids["f2"]})
    ops(scaf, {"op": "move_to_frame", "id": "mbody", "frame": ids["f1"]},
        {"op": "remove_module", "id": ids["f2"]})
    view = C.scaffold_view(C.load(scaf))
    assert view["frames"] == [ids["f1"]]
    assert view["boxes"][ids["f1"]] == ["mhead", "mpic", "mbody"]


def test_boxes_stack_inside_their_frame_and_a_page_grows(scaf: Path):
    f1 = first_frame(scaf)
    for i in range(8):
        ops(scaf, {"op": "add_module", "type": "scaffold-box", "id": f"mb{i}",
                   "frame": f1, "h": 160}, source="readvisor")
    comp = C.load(scaf)
    frame = comp.module(f1)
    boxes = [comp.module(f"mb{i}") for i in range(8)]
    assert boxes[0].x == frame.x + C.FRAME_PAD and boxes[0].y == frame.y + C.FRAME_PAD
    assert boxes[0].w == frame.w - 2 * C.FRAME_PAD
    for a, b in zip(boxes, boxes[1:]):
        assert b.y == a.y + a.h + C.GRID
    assert frame.h == boxes[-1].y + boxes[-1].h + C.FRAME_PAD - frame.y > C.FULLPORT[1]
    # A slide keeps its size.
    ops(scaf, {"op": "add_frame", "id": "ms", "shape": "slide"})
    for i in range(6):
        ops(scaf, {"op": "add_module", "type": "scaffold-box", "frame": "ms",
                   "h": 160})
    assert (C.load(scaf).module("ms").w, C.load(scaf).module("ms").h) == C.SLIDE


def test_a_box_goes_on_the_last_frame_unless_told(scaf: Path):
    ops(scaf, {"op": "add_frame", "id": "mf2"},
        {"op": "add_module", "type": "scaffold-box", "id": "mb"})
    assert C.load(scaf).module("mb").frame == "mf2"


def test_frame_ops_need_a_scaffold(tmp_path: Path):
    path = tmp_path / "plain.comp"
    C.save(path, C.new_composure("cards", "Plain"))
    for op in ({"op": "add_frame"}, {"op": "reorder_frames", "order": []},
               {"op": "set_scaffold", "thing": "deck"}):
        with pytest.raises(ComposureError, match="not a scaffold"):
            ops(path, op)


def test_the_meta_block_stores_lock_version_and_parent(scaf: Path):
    ops(scaf, {"op": "set_scaffold", "locked": True, "version": 2,
               "parent": "rness/io/composure/s-v1.comp"})
    view = C.scaffold_view(C.load(scaf))
    assert view["locked"]["by"] == "ui" and view["locked"]["at"]
    assert (view["version"], view["parent"]) == (2, "rness/io/composure/s-v1.comp")
    ops(scaf, {"op": "set_scaffold", "locked": False})
    assert C.scaffold_view(C.load(scaf))["locked"] is None
    with pytest.raises(ComposureError, match="stays a scaffold"):
        ops(scaf, {"op": "set_scaffold", "scaffold": None})


# ---------------------------------------------------------------------------
# Old scaffolds: never converted on open, converted on the person's click
# ---------------------------------------------------------------------------

def test_an_old_scaffold_form_composure_opens_as_it_did(tmp_path: Path):
    path = tmp_path / "old.comp"
    path.write_text(OLD_SCAFFOLD.read_text(encoding="utf-8"), encoding="utf-8")
    comp = C.load(path)
    assert comp.form == "scaffold" and comp.scaffold is None
    assert {m.type for m in comp.modules} == {"text"} and len(comp.modules) == 29
    assert C.model(comp)["scaffold"] is None
    # Working on it leaves it a plain plane, and the readvisor may still
    # write its cards: they are not the person's boxes.
    mid = comp.modules[3].id
    r = ops(path, {"op": "set_page", "module": mid, "n": 1, "markdown": "New"},
            source="readvisor")
    assert r.composure.scaffold is None


def test_make_this_a_scaffold_turns_cards_into_the_persons_boxes(tmp_path: Path):
    path = tmp_path / "old.comp"
    path.write_text(OLD_SCAFFOLD.read_text(encoding="utf-8"), encoding="utf-8")
    old = C.load(path)
    r = ops(path, {"op": "make_scaffold"})
    comp = r.composure
    view = C.scaffold_view(comp)
    assert view["thing"] == "page" and len(view["frames"]) == 1
    frame = comp.module(view["frames"][0])
    assert frame.type == C.FRAME and frame.z < min(m.z for m in old.modules)
    boxes = [m for m in comp.modules if m.type == C.BOX]
    assert len(boxes) == 29 and all(b.frame == frame.id for b in boxes)
    for b in boxes:                       # the frame is drawn around them
        assert frame.x <= b.x and b.x + b.w <= frame.x + frame.w
        assert frame.y <= b.y and b.y + b.h <= frame.y + frame.h
        before = old.module(b.id)
        assert (b.pages[0].rich, b.title) == (before.pages[0].rich, before.title)
    with pytest.raises(ComposureError, match="the person's own words"):
        ops(path, {"op": "set_page", "module": boxes[0].id, "n": 1,
                   "markdown": "x"}, source="readvisor")
    with pytest.raises(ComposureError, match="already a scaffold"):
        ops(path, {"op": "make_scaffold"})


# ---------------------------------------------------------------------------
# The outline tool and the council's output give 0.7's plane
# ---------------------------------------------------------------------------

#: Taken at 3cf8a60, before the scaffold, with `shape` above.
OUTLINE_SHAPES = {
    ("story", "scaffold"): "e69df81bef948f68",
    ("story", "cards"): "ace797432320dd5a",
    ("story", "blank"): "43c956a612c64189",
    ("essay", "scaffold"): "99ce48f24fd8320b",
    ("essay", "cards"): "1c1e492ef9f3482c",
    ("essay", "blank"): "e620a3273093db84",
    ("plan", "scaffold"): "405030b644adbe05",
    ("plan", "cards"): "44c8ff973044b370",
    ("plan", "blank"): "d08548ae45da5976",
}
COUNCIL_SHAPES = {"scaffold": "fad957dc7d1f5bc7", "cards": "c89ebce74f99b4f2"}


def _examples() -> dict[str, str]:
    return {
        "story": TO._example("# The Keeper's Stipend", "Then:"),
        "essay": TO._example("# Not the Privacy Essay", "Then the same tool call"),
        "plan": TO._example("# Six Languages by March", "# Reminders"),
    }


def test_from_outline_gives_the_plane_it_gave_before_the_scaffold():
    for name, src in _examples().items():
        for form in C.OUTLINE_FORMS:
            comp = C.from_outline("T", form, src)
            assert comp.scaffold is None, (name, form)
            assert shape(comp) == OUTLINE_SHAPES[(name, form)], (name, form)


def test_the_councils_output_is_unchanged():
    for form, digest in COUNCIL_SHAPES.items():
        comp = K.outline_composure("Round table", form, TC.OUTLINE)
        assert comp.scaffold is None and comp.form == form
        assert shape(comp) == digest


def test_the_outline_tool_over_the_scaffold_form_writes_a_plain_plane(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    home = tmp_path / "home"
    (home / "enough" / "config").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(broker, "CONFIG_PATH",
                        home / "enough" / "config" / "broker.json")
    project = tmp_path / "project"
    (project / "rness" / "io" / "composure").mkdir(parents=True)
    story = _examples()["story"]
    out = CT.run_composure_from_outline(project, T.ToolCall(
        name="composure_from_outline", path=None, content="\n" + story,
        command=None, url=None, extra={"title": "T", "form": "scaffold"},
        raw="", span=(0, 0)))
    assert out.ok, out.body
    written = C.load(project / out.key)
    assert written.scaffold is None
    assert "composure:scaffold" not in (project / out.key).read_text(encoding="utf-8")
    assert shape(written) == OUTLINE_SHAPES[("story", "scaffold")]


# ---------------------------------------------------------------------------
# Caps, content, the model
# ---------------------------------------------------------------------------

def test_the_module_cap_counts_frames_and_boxes(scaf: Path):
    """MAX_MODULES (200) is one count for every module: a frame and a
    scaffold-box are modules. A 26-slide deck at five boxes a slide is 182."""
    assert C.MAX_MODULES == 200
    comp = C.load(scaf)
    f1 = comp.modules[0].id
    for i in range(C.MAX_MODULES - 1):
        m = C.Module(id=f"mb{i}", type=C.BOX, frame=f1, kind="text",
                     state="empty", y=i * 200.0)
        m.pages = [C.Page(n=1)]
        comp.modules.append(m)
    C.save(scaf, comp)
    assert len(C.load(scaf).modules) == C.MAX_MODULES
    for op in ({"op": "add_module", "type": "scaffold-box"},
               {"op": "add_frame"}):
        with pytest.raises(ComposureError, match="frames and scaffold-boxes count"):
            ops(scaf, op)


def test_a_fresh_scaffold_has_no_content_until_something_is_on_it(scaf: Path):
    assert not C.has_content(C.load(scaf))
    ops(scaf, {"op": "add_module", "type": "scaffold-box"})
    assert not C.has_content(C.load(scaf))
    ops(scaf, {"op": "add_module", "type": "scaffold-box", "plec": "Say why"},
        source="readvisor")
    assert C.has_content(C.load(scaf))


def test_the_model_and_the_outline_carry_the_scaffold(scaf: Path):
    ids = build_scaffold(scaf)
    comp = C.load(scaf)
    model = C.model(comp)
    json.dumps(model)
    assert model["scaffold"] == {
        "v": 1, "thing": "page", "frames": [ids["f1"], ids["f2"]],
        "boxes": {ids["f1"]: ["mhead", "mpic"], ids["f2"]: ["mbody"]},
        "loose": [], "locked": None, "version": 1, "parent": None}
    head = next(m for m in model["modules"] if m["id"] == "mhead")
    assert head["known_type"] is True
    assert {k: head["fields"][k] for k in
            ("frame", "kind", "shape", "plec_by", "target", "state")} == {
        "frame": ids["f1"], "kind": "text", "shape": None,
        "plec_by": "readvisor", "target": "60c", "state": "empty"}
    text = C.outline(comp, "s.comp")
    assert f"scaffold: a page · frames in order: {ids['f1']}, {ids['f2']}" in text
    assert "target 60c" in text and "[What the picture must show]" in text
