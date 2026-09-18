"""The composure core: format round trips, the sanitizer, the ops, and the
sidecar.

The sanitizer tests are the load-bearing ones. `loads()` sanitizes on READ,
so a hostile `.comp` — synced in, mailed over, written by a confused model —
can never reach the frontend with anything executable in it. Every case in
`HOSTILE` is asserted twice: once through `sanitize_rich` directly, and once
through a whole file, because those are the two doors.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from enough import composure as C
from enough.composure import ComposureError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build(**kw) -> C.Composure:
    comp = C.Composure(title=kw.pop("title", "Test"),
                       form=kw.pop("form", "blank"),
                       kind=kw.pop("kind", "board"))
    comp.created = comp.modified = "2026-09-17T00:00:00Z"
    return comp


def card(mid: str, x: float = 0, y: float = 0, rich: str = "",
         **kw) -> C.Module:
    m = C.Module(id=mid, type=kw.pop("type", "text"), x=x, y=y,
                 w=kw.pop("w", 360.0), h=kw.pop("h", 240.0), **kw)
    m.pages = [C.Page(n=1, rich=rich)]
    return m


def wrap_page(rich: str) -> str:
    """A whole minimal `.comp` document with `rich` inside one page."""
    comp = build()
    comp.modules = [card("m1")]
    text = C.dumps(comp)
    return text.replace('data-n="1"></div>', f'data-n="1">{rich}</div>')


# ---------------------------------------------------------------------------
# Round trips
# ---------------------------------------------------------------------------

def test_dumps_loads_round_trip_is_byte_stable():
    comp = build(title="Hello & <world>")
    comp.modules = [
        card("m1", 0, 0, rich="<p>plain</p>", bg="yellow", title="A card"),
        card("m2", 408, 0, type="doc", href="notes/plan.md", bg="clear"),
    ]
    comp.strokes = [C.Stroke(id="s1", width=2.5, color="red",
                             points=[(10.0, 10.0), (14.25, 12.0)])]
    text = C.dumps(comp)
    assert C.dumps(C.loads(text)) == text
    # ...and a second pass changes nothing either.
    assert C.dumps(C.loads(C.dumps(C.loads(text)))) == text


def test_round_trip_preserves_unknown_meta_and_data_attributes():
    """A file written by a newer enough must survive being opened by an
    older one — that is what the preserve-unknown rule buys."""
    comp = build()
    comp.meta_extra = {"flavour": "vanilla"}
    m = card("m1")
    m.extra = {"data-from-the-future": "keep me"}
    m.pages[0].extra = {"data-mood": "calm"}
    comp.modules = [m]
    text = C.dumps(comp)
    back = C.loads(text)
    assert back.meta_extra == {"flavour": "vanilla"}
    assert back.modules[0].extra == {"data-from-the-future": "keep me"}
    assert back.modules[0].pages[0].extra == {"data-mood": "calm"}
    assert C.dumps(back) == text
    # Non-`data-*` attributes are regenerated, never preserved.
    assert "onclick" not in C.dumps(back)


def test_loads_refuses_a_document_that_is_not_a_composure():
    with pytest.raises(ComposureError, match="not a composure"):
        C.loads("<!doctype html><html><body>hi</body></html>")


def test_loads_repairs_rather_than_refuses_broken_content():
    """A composure the user can see in their tree must always open."""
    broken = wrap_page("<p>text").replace('data-id="m1"', 'data-id="NOPE!"')
    comp = C.loads(broken)
    assert len(comp.modules) == 1
    assert C._MODULE_ID_RE.match(comp.modules[0].id)
    assert any("reassigned" in w for w in comp.warnings)


def test_a_div_inside_a_page_cannot_truncate_the_module():
    text = wrap_page("<div><p>one</p></div><p>two</p>")
    comp = C.loads(text)
    assert comp.modules[0].pages[0].rich == "<p>one</p><p>two</p>"


def test_every_shipped_form_loads_sanitizes_clean_and_round_trips():
    forms = C.list_forms()
    assert {f["name"] for f in forms} >= set(C.SHIPPED_FORMS)
    for entry in forms:
        raw = Path(entry["path"]).read_text(encoding="utf-8")
        comp = C.loads(raw)
        assert comp.warnings == [], f"{entry['name']}: {comp.warnings}"
        assert C.dumps(comp) == raw, f"{entry['name']} does not round-trip"
        for m in comp.modules:
            for p in m.pages:
                assert C.sanitize_rich(p.rich) == p.rich
        # And the model is JSON-serializable, which is the frontend's ask.
        json.dumps(C.model(comp))


def test_shipped_form_shapes():
    assert len(C.new_composure("cards").modules) == 16
    assert len(C.new_composure("scaffold").modules) == 29
    blank = C.new_composure("blank")
    assert blank.kind == "page"
    assert (blank.modules[0].w, blank.modules[0].h) == C.FULLPORT
    council = C.new_composure("council")
    assert council.council and council.council["status"] == "setup"
    assert C.new_composure("journal").kind == "page"


def test_new_composure_refuses_an_unknown_form():
    with pytest.raises(ComposureError, match="no composure form"):
        C.new_composure("../../etc/passwd")
    with pytest.raises(ComposureError, match="no composure form"):
        C.new_composure("nope")


# ---------------------------------------------------------------------------
# The sanitizer
# ---------------------------------------------------------------------------

HOSTILE: list[tuple[str, str, str]] = [
    # (label, input, expected output)
    ("script tag", "<p>a</p><script>alert(1)</script>", "<p>a</p>"),
    ("script in svg", "<svg><script>alert(1)</script></svg>x", "x"),
    ("style content", "<style>body{x:1}</style>keep", "keep"),
    ("template", "<template><p>hidden</p></template>", ""),
    ("noscript", "<noscript>nope</noscript>", ""),
    ("iframe", '<iframe src="https://e.com">t</iframe>', ""),
    ("object", "<object data='x'>t</object>", ""),
    ("embed", "<embed src='x'>", ""),
    ("math", "<math><mtext>m</mtext></math>", ""),
    ("form + input", "<form><input value=x></form>", ""),
    ("event handler", '<p onclick="steal()">a</p>', "<p>a</p>"),
    ("onerror on allowed tag", '<span onerror=x data-hl="yellow">a</span>',
     '<span data-hl="yellow">a</span>'),
    ("javascript href", '<a href="javascript:alert(1)">x</a>', "x"),
    ("JavaScript href, mixed case", '<a href="JaVaScRiPt:alert(1)">x</a>', "x"),
    ("entity-encoded scheme", '<a href="&#106;avascript:alert(1)">x</a>', "x"),
    ("double-encoded scheme", '<a href="&amp;#106;avascript:alert(1)">x</a>', "x"),
    ("whitespace-split scheme", '<a href="java\tscript:alert(1)">x</a>', "x"),
    ("newline-split scheme", '<a href="java\nscript:alert(1)">x</a>', "x"),
    ("data url", '<a href="data:text/html,<script>">x</a>', "x"),
    ("vbscript url", '<a href="vbscript:msgbox">x</a>', "x"),
    ("file url", '<a href="file:///etc/passwd">x</a>', "x"),
    ("protocol-relative", '<a href="//evil.example/x">x</a>', "x"),
    ("absolute path", '<a href="/etc/passwd">x</a>', "x"),
    ("traversal path", '<a href="../../secret.md">x</a>', "x"),
    ("http kept", '<a href="https://ok.example/a">x</a>',
     '<a href="https://ok.example/a">x</a>'),
    ("mailto kept", '<a href="mailto:a@b.c">x</a>',
     '<a href="mailto:a@b.c">x</a>'),
    ("project path kept", '<a href="notes/plan.md">x</a>',
     '<a href="notes/plan.md">x</a>'),
    ("unknown tag keeps text", "<div><p>a</p></div>", "<p>a</p>"),
    ("unknown attribute dropped", '<p class="x" id="y">a</p>', "<p>a</p>"),
    ("crossed nesting repaired", "<b><i>x</b></i>", "<b><i>x</i></b>"),
    ("stray close ignored", "</b>text", "text"),
    ("comment dropped", "<!-- <script>x</script> -->a", "a"),
    ("processing instruction dropped", "<?php echo 1 ?>a", "a"),
    ("bad highlight color dropped", '<span data-hl="url(evil)">a</span>',
     "<span>a</span>"),
    ("good highlight kept", '<span data-hl="pink">a</span>',
     '<span data-hl="pink">a</span>'),
    ("checklist normalized", '<li data-check="true">a</li>',
     '<li data-check="1">a</li>'),
    ("checklist junk is unchecked", '<li data-check="evil">a</li>',
     '<li data-check="0">a</li>'),
    ("text escaped", "a < b & c > d", "a &lt; b &amp; c &gt; d"),
]


@pytest.mark.parametrize("label,raw,expected",
                         HOSTILE, ids=[c[0] for c in HOSTILE])
def test_sanitizer_corpus(label: str, raw: str, expected: str):
    assert C.sanitize_rich(raw) == expected


@pytest.mark.parametrize("label,raw,expected",
                         HOSTILE, ids=[c[0] for c in HOSTILE])
def test_sanitizer_is_idempotent(label: str, raw: str, expected: str):
    once = C.sanitize_rich(raw)
    assert C.sanitize_rich(once) == once


@pytest.mark.parametrize("label,raw,expected",
                         HOSTILE, ids=[c[0] for c in HOSTILE])
def test_loading_a_hostile_file_sanitizes_it(label: str, raw: str, expected: str):
    """The same corpus, but arriving as a file somebody hand-edited."""
    comp = C.loads(wrap_page(raw))
    assert comp.modules[0].pages[0].rich == expected


def test_a_hostile_file_never_yields_executable_markup():
    nasty = "".join(raw for _label, raw, _exp in HOSTILE)
    out = C.loads(wrap_page(nasty)).modules[0].pages[0].rich
    lowered = out.lower()
    for forbidden in ("<script", "javascript:", "data:text/html", "onclick",
                      "onerror", "<iframe", "<svg", "<object", "<embed",
                      "vbscript:", "<form"):
        assert forbidden not in lowered, forbidden


def test_nesting_bomb_is_capped_not_fatal():
    bomb = "<b>" * 500 + "deep" + "</b>" * 500
    out = C.sanitize_rich(bomb)
    assert "deep" in out
    assert out.count("<b>") <= C.MAX_DEPTH


def test_oversize_input_is_refused_with_a_clear_message():
    with pytest.raises(ComposureError, match="parse limit"):
        C.sanitize_rich("x" * (C.MAX_RICH_INPUT_CHARS + 1))
    with pytest.raises(ComposureError, match="over the 400000 cap"):
        C.sanitize_rich("<p>" + "x" * (C.MAX_PAGE_CHARS + 10) + "</p>")


def test_oversize_file_is_refused_before_parsing():
    with pytest.raises(ComposureError, match="MB"):
        C.loads("x" * (C.MAX_FILE_BYTES + 1))


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

def test_markdown_it_py_is_reachable_from_a_base_dependency():
    """Base-reachable via huggingface-hub → typer → rich. If this ever
    breaks, `md_to_rich` silently degrades to paragraphs — so pin it."""
    assert C._markdown_renderer() is not False


def test_md_to_rich_covers_the_allowlist():
    out = C.md_to_rich(
        "# H1\n\n## H2\n\ntext with **bold**, *em*, `code` and "
        "[a link](https://e.com/x).\n\n"
        "- one\n- two\n  - nested\n\n"
        "1. first\n2. second\n\n"
        "- [ ] todo\n- [x] done\n\n"
        "> quoted\n\n```\nfenced\n```\n\n---\n"
    )
    for fragment in ("<h1>H1</h1>", "<h2>H2</h2>", "<strong>bold</strong>",
                     "<em>em</em>", "<code>code</code>",
                     '<a href="https://e.com/x">a link</a>',
                     "<ul>", "<ol>", '<li data-check="0">',
                     '<li data-check="1">', "<blockquote>", "<pre>", "<hr>"):
        assert fragment in out, fragment
    assert C.sanitize_rich(out) == out


def test_md_to_rich_degrades_unrepresentable_markdown_to_text():
    out = C.md_to_rich("![alt text](x.png)\n\n<div onclick=x>raw</div>\n")
    assert "<img" not in out and "<div" not in out
    assert "alt text" in out            # the picture goes, its words stay
    assert "&lt;div onclick=x&gt;raw" in out   # raw HTML arrives as text


def test_rich_to_md_is_readable():
    md = C.rich_to_md(C.md_to_rich("# T\n\n- [ ] a\n- [x] b\n\n**bold**\n"))
    assert "# T" in md and "- [ ] a" in md and "- [x] b" in md
    assert "**bold**" in md
    assert "\n\n\n" not in md


def test_rich_text_and_first_line():
    rich = C.md_to_rich("# Heading\n\nbody text here\n")
    assert C.rich_text(rich).startswith("Heading")
    assert C.first_line(rich) == "Heading"


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------

def test_place_module_never_overlaps_and_keeps_the_gutter():
    comp = build()
    for i in range(30):
        w, h = 360.0, 240.0
        x, y = C.place_module(comp, w, h)
        for other in comp.modules:
            assert not C._overlaps(
                (x, y, w, h), (other.x, other.y, other.w, other.h)), i
            gap_x = max(other.x - (x + w), x - (other.x + other.w))
            gap_y = max(other.y - (y + h), y - (other.y + other.h))
            assert max(gap_x, gap_y) >= C.GUTTER - 1e-6
        comp.modules.append(card(f"m{i}", x, y))


def test_place_module_is_deterministic_and_starts_at_the_origin_when_empty():
    comp = build()
    assert C.place_module(comp, 360, 240) == (0.0, 0.0)
    comp.modules = [card("m1", 0, 0)]
    assert C.place_module(comp, 360, 240) == C.place_module(comp, 360, 240)


def test_place_module_near_puts_it_to_the_right():
    comp = build()
    comp.modules = [card("m1", 0, 0), card("m2", 0, 288)]
    x, y = C.place_module(comp, 360, 240, near="m1")
    assert x >= 360 + C.GUTTER and y == 0


def test_default_size_and_scale_follow_the_neighbours():
    comp = build()
    assert C.default_scale(comp) == 1.0
    assert C.default_size(comp, "text", 1.0) == (360.0, 240.0)
    assert C.default_size(comp, "webframe", 1.0) == (480.0, 600.0)
    comp.modules = [card("m1", w=500, h=300), card("m2", w=500, h=300)]
    assert C.default_size(comp, "text", 1.0) == (500.0, 300.0)


def test_snap_scale_stays_on_the_ladder():
    assert C.snap_scale(1.0) == 1.0
    assert C.snap_scale(99) == pytest.approx(C.SCALE_MAX, rel=0.2)
    assert C.snap_scale(0.01) == C.SCALE_MIN
    assert C.snap_scale("nonsense") == 1.0


# ---------------------------------------------------------------------------
# Ops
# ---------------------------------------------------------------------------

@pytest.fixture()
def comp_path(tmp_path: Path) -> Path:
    path = tmp_path / "rness" / "io" / "composure" / "board.comp"
    path.parent.mkdir(parents=True, exist_ok=True)
    C.save(path, C.new_composure("blank", "Board"))
    return path


def ops(path: Path, *op_list, base_rev=None, **kw) -> C.OpsResult:
    return C.apply_ops(path, base_rev, list(op_list), **kw)


def test_apply_ops_bumps_rev_once_per_batch(comp_path: Path):
    r = ops(comp_path,
            {"op": "add_module", "type": "text", "markdown": "one"},
            {"op": "add_module", "type": "text", "markdown": "two"})
    assert r.rev == 1
    assert len(r.changed) == 2
    assert len(C.load(comp_path).modules) == 3  # the form's module + two


def test_apply_ops_is_atomic(comp_path: Path):
    before = comp_path.read_text(encoding="utf-8")
    with pytest.raises(ComposureError, match="whole batch was discarded"):
        ops(comp_path,
            {"op": "add_module", "type": "text", "markdown": "kept?"},
            {"op": "add_module", "type": "nonsense"})
    assert comp_path.read_text(encoding="utf-8") == before


def test_apply_ops_refuses_an_empty_batch_and_an_unknown_source(comp_path: Path):
    with pytest.raises(ComposureError, match="nothing to apply"):
        ops(comp_path)
    with pytest.raises(ComposureError, match="unknown op source"):
        ops(comp_path, {"op": "set_meta", "title": "x"}, source="hacker")


def test_lazy_create(tmp_path: Path):
    path = tmp_path / "rness" / "io" / "composure" / "new.comp"
    with pytest.raises(ComposureError, match="send create:true"):
        ops(path, {"op": "set_meta", "title": "x"})
    assert not path.exists()
    r = ops(path, {"op": "set_meta", "title": "Made"},
            create=True, form="cards", title="Made", project_dir=tmp_path)
    assert r.created and path.is_file()
    assert C.load(path).form == "cards"


def test_add_module_places_sizes_and_assigns_an_id(comp_path: Path):
    r = ops(comp_path, {"op": "add_module", "type": "text",
                        "markdown": "# hi", "bg": "yellow"})
    comp = C.load(comp_path)
    m = comp.module(r.changed[0])
    assert m and m.bg == "yellow" and m.pages[0].rich == "<h1>hi</h1>"
    assert C._MODULE_ID_RE.match(m.id)
    assert (m.w, m.h) == C.FULLPORT      # median of the blank form's fullport


def test_client_supplied_ids_are_honored_once(comp_path: Path):
    ops(comp_path, {"op": "add_module", "type": "text", "id": "mabc123"})
    assert C.load(comp_path).module("mabc123") is not None
    with pytest.raises(ComposureError, match="already taken"):
        ops(comp_path, {"op": "add_module", "type": "text", "id": "mabc123"})
    with pytest.raises(ComposureError, match="not usable"):
        ops(comp_path, {"op": "add_module", "type": "text", "id": "M-BAD!"})


def test_update_module_is_a_patch(comp_path: Path):
    mid = ops(comp_path, {"op": "add_module", "type": "text",
                          "title": "keep me"}).changed[0]
    ops(comp_path, {"op": "update_module", "id": mid, "x": 99.456, "bg": "blue"})
    m = C.load(comp_path).module(mid)
    assert m.title == "keep me" and m.bg == "blue"
    assert m.x == 99.46                  # rounded to 2 decimals on write


def test_update_module_refuses_unknown_values(comp_path: Path):
    mid = C.load(comp_path).modules[0].id
    with pytest.raises(ComposureError, match="named swatches"):
        ops(comp_path, {"op": "update_module", "id": mid, "bg": "#ff0000"})
    with pytest.raises(ComposureError, match="unknown module type"):
        ops(comp_path, {"op": "update_module", "id": mid, "type": "applet"})
    with pytest.raises(ComposureError, match="no module"):
        ops(comp_path, {"op": "update_module", "id": "mzzz", "x": 1})


def test_link_module_fields_are_validated(comp_path: Path):
    with pytest.raises(ComposureError, match="project-relative path"):
        ops(comp_path, {"op": "add_module", "type": "doc",
                        "href": "https://evil.example/x"})
    with pytest.raises(ComposureError, match="must be http"):
        ops(comp_path, {"op": "add_module", "type": "webframe",
                        "url": "javascript:alert(1)"})
    r = ops(comp_path, {"op": "add_module", "type": "webframe",
                        "url": "https://ok.example/feed"})
    assert C.load(comp_path).module(r.changed[0]).refresh == "manual"


def test_pages(comp_path: Path):
    mid = C.load(comp_path).modules[0].id
    ops(comp_path, {"op": "set_page", "module": mid, "n": 1,
                    "markdown": "page one"})
    ops(comp_path, {"op": "add_page", "module": mid, "markdown": "page two"})
    m = C.load(comp_path).module(mid)
    assert [p.n for p in m.pages] == [1, 2]
    assert "page two" in m.pages[1].rich
    ops(comp_path, {"op": "remove_page", "module": mid, "n": 1})
    m = C.load(comp_path).module(mid)
    assert len(m.pages) == 1 and "page two" in m.pages[0].rich
    with pytest.raises(ComposureError, match="remove the module instead"):
        ops(comp_path, {"op": "remove_page", "module": mid, "n": 1})


def test_set_page_refuses_rich_and_markdown_together(comp_path: Path):
    mid = C.load(comp_path).modules[0].id
    with pytest.raises(ComposureError, match="not both"):
        ops(comp_path, {"op": "set_page", "module": mid, "n": 1,
                        "rich": "<p>a</p>", "markdown": "a"})


def test_set_page_sanitizes_rich_input(comp_path: Path):
    mid = C.load(comp_path).modules[0].id
    ops(comp_path, {"op": "set_page", "module": mid, "n": 1,
                    "rich": '<p onclick="x">a</p><script>b</script>'})
    assert C.load(comp_path).module(mid).pages[0].rich == "<p>a</p>"


def test_filing_a_journal_page_makes_it_permanently_read_only(tmp_path: Path):
    path = tmp_path / "journal.comp"
    C.save(path, C.new_composure("journal", "Journal"))
    mid = C.load(path).modules[0].id
    ops(path, {"op": "set_page", "module": mid, "n": 1, "markdown": "today"})
    ops(path, {"op": "file_page", "module": mid, "n": 1, "date": "2026-09-17"})
    page = C.load(path).module(mid).pages[0]
    assert page.filed and page.date == "2026-09-17"
    for op in ({"op": "set_page", "module": mid, "n": 1, "markdown": "x"},
               {"op": "remove_page", "module": mid, "n": 1}):
        with pytest.raises(ComposureError, match="permanently read-only"):
            ops(path, op)
    with pytest.raises(ComposureError, match="already filed"):
        ops(path, {"op": "file_page", "module": mid, "n": 1})
    # A new page beside it is still writable — filing locks a page, not a
    # module.
    ops(path, {"op": "add_page", "module": mid, "markdown": "tomorrow"})
    assert len(C.load(path).module(mid).pages) == 2


def test_council_statements_are_engine_owned(comp_path: Path):
    mid = ops(comp_path, {"op": "add_module", "type": "text",
                          "speaker": "Ed", "turn": "1"}).changed[0]
    with pytest.raises(ComposureError, match="council engine owns"):
        ops(comp_path, {"op": "set_page", "module": mid, "n": 1,
                        "markdown": "forged"})
    with pytest.raises(ComposureError, match="council engine owns"):
        ops(comp_path, {"op": "remove_module", "id": mid})
    # The engine itself may write, and anybody may move it.
    ops(comp_path, {"op": "set_page", "module": mid, "n": 1,
                    "markdown": "real"}, source="council")
    ops(comp_path, {"op": "update_module", "id": mid, "x": 10})
    assert C.load(comp_path).module(mid).locked is True


def test_strokes(comp_path: Path):
    ops(comp_path, {"op": "add_strokes", "strokes": [
        {"id": "s1", "color": "red", "width": 3,
         "points": [[0, 0], [10, 10], [20, 5]]},
        {"color": "ink", "points": [[1, 1], [2, 2]]},
    ]})
    comp = C.load(comp_path)
    assert len(comp.strokes) == 2 and comp.strokes[0].color == "red"
    # The eraser's split: remove one, add two, atomically.
    ops(comp_path, {"op": "replace_strokes", "remove": ["s1"], "add": [
        {"points": [[0, 0], [4, 4]]}, {"points": [[16, 7], [20, 5]]}]})
    comp = C.load(comp_path)
    assert "s1" not in comp.stroke_ids() and len(comp.strokes) == 3
    ops(comp_path, {"op": "remove_strokes", "ids": list(comp.stroke_ids())})
    assert C.load(comp_path).strokes == []


def test_stroke_validation(comp_path: Path):
    with pytest.raises(ComposureError, match="at least 2 points"):
        ops(comp_path, {"op": "add_strokes", "strokes": [{"points": [[0, 0]]}]})
    with pytest.raises(ComposureError, match="unknown ink color"):
        ops(comp_path, {"op": "add_strokes", "strokes": [
            {"color": "puce", "points": [[0, 0], [1, 1]]}]})


def test_set_meta_and_arrange(comp_path: Path):
    ids = [ops(comp_path, {"op": "add_module", "type": "text"}).changed[0]
           for _ in range(4)]
    ops(comp_path, {"op": "set_meta", "title": "Renamed", "kind": "board",
                    "view": {"x": 5, "y": 6, "zoom": 2}})
    comp = C.load(comp_path)
    assert comp.title == "Renamed" and comp.kind == "board"
    assert comp.view == {"x": 5, "y": 6, "zoom": 2}
    ops(comp_path, {"op": "arrange", "ids": ids, "mode": "column",
                    "x": 0, "y": 0})
    comp = C.load(comp_path)
    ys = [comp.module(i).y for i in ids]
    assert ys == sorted(ys) and len(set(ys)) == 4
    assert all(comp.module(i).x == 0 for i in ids)
    with pytest.raises(ComposureError, match="no module"):
        ops(comp_path, {"op": "arrange", "ids": ["mnope"]})


def test_unknown_op_names_itself(comp_path: Path):
    with pytest.raises(ComposureError, match="unknown op"):
        ops(comp_path, {"op": "drop_database"})


def test_module_cap(comp_path: Path):
    comp = C.load(comp_path)
    comp.modules = [card(f"m{i}", i * 400, 0) for i in range(C.MAX_MODULES)]
    C.save(comp_path, comp)
    with pytest.raises(ComposureError, match=f"{C.MAX_MODULES} modules"):
        ops(comp_path, {"op": "add_module", "type": "text"})


def test_stale_base_rev_is_a_merge_not_an_error(comp_path: Path):
    first = ops(comp_path, {"op": "add_module", "type": "text"})
    second = ops(comp_path, {"op": "add_module", "type": "text"},
                 base_rev=first.rev)
    assert second.stale is False
    third = ops(comp_path, {"op": "add_module", "type": "text"},
                base_rev=first.rev)
    assert third.stale is True
    assert third.stale_changed == second.changed
    assert len(C.load(comp_path).modules) == 4   # every batch still landed


def test_changed_since_reports_unknown_history_as_none(tmp_path: Path):
    path = tmp_path / "x.comp"
    assert C.changed_since(path, 0, 0) == []
    assert C.changed_since(path, 3, 9) is None


# ---------------------------------------------------------------------------
# Write door, paths, forms, listing
# ---------------------------------------------------------------------------

def test_write_denial_covers_comp_files_and_their_sidecar(tmp_path: Path):
    assert "module-by-module" in (C.write_denial(tmp_path / "a.comp") or "")
    assert "backend-owned" in (
        C.write_denial(tmp_path / ".a.comp.comments.json") or "")
    assert C.write_denial(tmp_path / "a.md") is None


def test_new_path_never_collides(tmp_path: Path):
    (tmp_path / C.COMPOSURE_DIR_REL).mkdir(parents=True)
    first = C.new_path(tmp_path, "My Café Notes")
    assert first.startswith("rness/io/composure/my-cafe-notes-")
    (tmp_path / first).write_text("x", encoding="utf-8")
    assert C.new_path(tmp_path, "My Café Notes") != first


def test_save_as_form_and_project_override(tmp_path: Path):
    comp = C.new_composure("cards", "My Board")
    dest = C.save_as_form(tmp_path, comp, "My Board!")
    assert dest.name == "my-board.comp"
    names = {f["name"]: f for f in C.list_forms(tmp_path)}
    assert names["my-board"]["origin"] == "project"
    # A project form shadows a shipped one of the same name.
    C.save_as_form(tmp_path, comp, "blank")
    assert {f["name"]: f for f in C.list_forms(tmp_path)}["blank"]["origin"] \
        == "project"
    assert C.new_composure("my-board", "x", tmp_path).form == "my-board"


def test_list_composures_hides_dotfiles_and_sorts_newest_first(tmp_path: Path):
    (tmp_path / "a").mkdir()
    C.save(tmp_path / "a" / "one.comp", C.new_composure("blank", "One"))
    older = C.new_composure("blank", "Two")
    older.modified = "2000-01-01T00:00:00Z"
    C.save(tmp_path / "two.comp", older)
    (tmp_path / ".hidden").mkdir()
    C.save(tmp_path / ".hidden" / "x.comp", C.new_composure("blank", "Hidden"))
    rows = C.list_composures(tmp_path)
    assert [r["title"] for r in rows] == ["One", "Two"]
    assert rows[0]["path"] == "a/one.comp"


def test_save_is_atomic_and_leaves_no_temp_file(tmp_path: Path):
    path = tmp_path / "x.comp"
    C.save(path, C.new_composure("blank", "X"))
    assert not [p.name for p in tmp_path.iterdir() if ".tmp-" in p.name]
    assert C.load(path).title == "X"


# ---------------------------------------------------------------------------
# Comments sidecar
# ---------------------------------------------------------------------------

def test_comments_crud(tmp_path: Path):
    path = tmp_path / "board.comp"
    C.save(path, C.new_composure("blank", "Board"))
    side = C.comments_path(path)
    assert side.name == ".board.comp.comments.json"
    assert not side.exists()

    entry = C.add_comment(path, "first thought",
                          {"type": "quote", "module": "m1", "page": 1,
                           "quote": "hello"}, "board.comp")
    assert entry["state"] == "anchored" and entry["id"].startswith("c_")
    assert side.is_file()
    C.add_reply(path, entry["id"], "a reply")
    C.update_comment(path, entry["id"], resolved=True, state="orphaned")
    doc = C.load_comments(path, "board.comp")
    assert len(doc["comments"][0]["replies"]) == 1
    assert doc["comments"][0]["resolved"] is True
    assert doc["comments"][0]["state"] == "orphaned"

    with pytest.raises(KeyError):
        C.update_comment(path, "c_nope", body="x")
    C.delete_comment(path, entry["id"])
    assert not side.exists()            # empty sidecars are removed, not kept


def test_module_anchor_is_the_default(tmp_path: Path):
    path = tmp_path / "b.comp"
    C.save(path, C.new_composure("blank", "B"))
    entry = C.add_comment(path, "on the box itself", {"module": "m1"})
    assert entry["anchor"]["type"] == "module" and entry["state"] == "module"


def test_move_sidecars_follows_a_rename(tmp_path: Path):
    src, dest = tmp_path / "a.comp", tmp_path / "b.comp"
    C.save(src, C.new_composure("blank", "A"))
    C.add_comment(src, "keep me", {"module": "m1"})
    src.rename(dest)
    C.move_sidecars(src, dest)
    assert C.comments_path(dest).is_file()
    assert not C.comments_path(src).exists()
    assert C.load_comments(dest)["comments"][0]["body"] == "keep me"


# ---------------------------------------------------------------------------
# The JSON model and the outline
# ---------------------------------------------------------------------------

def test_model_shape_is_the_frontend_contract(comp_path: Path):
    mid = ops(comp_path, {"op": "add_module", "type": "doc",
                          "href": "notes/plan.md", "title": "Plan"}).changed[0]
    ops(comp_path, {"op": "add_strokes",
                    "strokes": [{"points": [[0, 0], [1, 1]]}]})
    m = C.model(C.load(comp_path))
    assert set(m) == {"version", "title", "form", "kind", "rev", "created",
                      "modified", "view", "council", "bounds", "modules",
                      "strokes", "meta", "warnings", "caps"}
    mod = next(x for x in m["modules"] if x["id"] == mid)
    assert set(mod) == {"id", "type", "known_type", "x", "y", "w", "h", "z",
                        "bg", "known_bg", "scale", "title", "cur", "fields",
                        "speaker", "speaker_kind", "turn", "locked",
                        "page_count", "pages", "data"}
    assert mod["fields"]["href"] == "notes/plan.md"
    assert set(mod["pages"][0]) == {"n", "rich", "first_line", "chars",
                                    "date", "filed", "locked", "data"}
    assert set(m["strokes"][0]) == {"id", "color", "width", "points"}
    assert m["caps"]["modules"] == C.MAX_MODULES
    json.dumps(m)


def test_outline_is_compact_and_quotes_module_ids(comp_path: Path):
    mid = ops(comp_path, {"op": "add_module", "type": "text",
                          "title": "Act one",
                          "markdown": "The hero wants something."}).changed[0]
    text = C.outline(C.load(comp_path), "board.comp")
    assert "composure: Board" in text and "path: board.comp" in text
    assert mid in text and "Act one" in text
    assert "The hero wants something." in text
    assert len(text.splitlines()) == 6          # 3 header, blank, 2 modules
    assert "<" not in text                      # never raw markup


def test_page_markdown_round_trips_through_the_model(comp_path: Path):
    mid = C.load(comp_path).modules[0].id
    ops(comp_path, {"op": "set_page", "module": mid, "n": 1,
                    "markdown": "# Title\n\nbody\n"})
    md = C.page_markdown(C.load(comp_path), mid)
    assert "# Title" in md and "body" in md
    with pytest.raises(ComposureError, match="no page 9"):
        C.page_markdown(C.load(comp_path), mid, 9)
    with pytest.raises(ComposureError, match="no module"):
        C.page_markdown(C.load(comp_path), "mnope")
