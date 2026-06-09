"""Tests for the girraph parser/serializer/ops (enough/girraph.py).

The malformed-input cases simulate what a flaky 16–32K-ctx local model
actually emits: arrow glyphs instead of ASCII, sloppy spacing, duplicate
ids, lines that aren't in the grammar at all. The invariant under test
throughout: parsing + serializing never destroys content.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from enough import girraph as gr

EXAMPLE = """\
%girraph 0.1
title: Should enough ship a plugin API?
next: a4 g2 n2 p3 q2

q1 ? Should enough ship a plugin API?
p1 ! Ship a minimal one < q1
p2 ! Don't — skills are enough < q1
a1 + Ecosystem growth needs stable hooks < p1 by:graham
a2 - API surface = forever maintenance < p1 by:open-skeptic
a3 + Skills already cover 80% of cases < p2 [-> a2]
n1 . Background reading < q1 ref:infoworld/plugins-survey.md
g1 @ Subproblem: versioning policy < p1 ref:rness/girraphs/versioning.girraph

q1 >
  Longer free-form details for the root issue live in an
  indented block under `id >`. Markdown allowed.
"""


def test_parse_example():
    g = gr.loads(EXAMPLE)
    assert g.title == "Should enough ship a plugin API?"
    assert g.next_marks == {"a": 4, "g": 2, "n": 2, "p": 3, "q": 2}
    assert list(g.nodes) == ["q1", "p1", "p2", "a1", "a2", "a3", "n1", "g1"]
    assert g.root().id == "q1"
    assert g.nodes["p1"].parent == "q1"
    assert g.nodes["a1"].by == "graham"
    assert g.nodes["a3"].cross == ["a2"]
    assert g.nodes["n1"].ref == "infoworld/plugins-survey.md"
    assert g.nodes["g1"].type == "girraph"
    assert "indented block" in g.nodes["q1"].detail
    assert g.warnings == []


def test_round_trip_is_stable():
    """Canonical input survives parse→dump byte-for-byte."""
    g = gr.loads(EXAMPLE)
    assert gr.dumps(g) == EXAMPLE
    # And a second round trip of the dump is a fixed point.
    assert gr.dumps(gr.loads(gr.dumps(g))) == gr.dumps(g)


def test_sloppy_input_normalizes():
    """Arrow glyphs, ragged spacing, detail block before its node."""
    sloppy = (
        "%girraph 0.1\n"
        "title:   Messy   \n"
        "\n"
        "q1 >\n"
        "    early detail\n"
        "q1 ?   What now   [→  a9 ]\n"
        "a9 +  because reasons   <q1\n"
    )
    g = gr.loads(sloppy)
    assert g.nodes["q1"].label == "What now"
    assert g.nodes["q1"].cross == ["a9"]
    assert g.nodes["q1"].detail == "early detail"
    assert g.nodes["a9"].parent == "q1"
    out = gr.dumps(g)
    assert "[-> a9]" in out          # glyph normalized to ASCII
    assert "→" not in out


def test_label_keeps_inline_lookalikes():
    """Modifier-ish text mid-label is label; only trailing tokens strip."""
    text = (
        "%girraph 0.1\n\n"
        "q1 ? Is a < b ever true for refs like x by:graham said so\n"
    )
    g = gr.loads(text)
    # by:graham is mid-label here (followed by more words) — untouched.
    assert g.nodes["q1"].by is None
    assert g.nodes["q1"].label.endswith("said so")


def test_freeform_lines_survive():
    text = (
        "%girraph 0.1\n\n"
        "q1 ? A question\n"
        "TODO revisit this whole branch\n"
        "p1 ! An answer < q1\n"
    )
    g = gr.loads(text)
    assert any("unparsed line" in w for w in g.warnings)
    out = gr.dumps(g)
    # Preserved verbatim, in place (between the two node lines).
    assert out.index("q1 ?") < out.index("TODO revisit") < out.index("p1 !")


def test_duplicate_id_keeps_first_preserves_second():
    text = (
        "%girraph 0.1\n\n"
        "q1 ? First\n"
        "q1 ? Second\n"
    )
    g = gr.loads(text)
    assert g.nodes["q1"].label == "First"
    assert any("duplicate" in w for w in g.warnings)
    assert "q1 ? Second" in gr.dumps(g)


def test_missing_magic_refused():
    with pytest.raises(gr.GirraphError):
        gr.loads("just some text\n")


def test_dangling_parent_and_cycle_warn():
    text = (
        "%girraph 0.1\n\n"
        "p1 ! Orphaned < q9\n"
        "a1 + Chicken < a2\n"
        "a2 - Egg < a1\n"
    )
    g = gr.loads(text)
    assert any("unknown parent" in w for w in g.warnings)
    assert any("cycle" in w for w in g.warnings)
    # Cycle members render as roots without hanging.
    assert "Chicken" in gr.ascii_render(g)


# ---------------------------------------------------------------------------
# Ops
# ---------------------------------------------------------------------------

def test_add_node_assigns_ids_and_creates():
    g = gr.new_girraph("Test map")
    q = gr.add_node(g, type="issue", label="The question?")
    assert q.id == "q1"
    p = gr.add_node(g, type="position", label="An answer", parent=q.id)
    assert p.id == "p1"
    a = gr.add_node(g, type="objection", label="But no", parent=p.id, by="user")
    assert a.id == "a1"
    assert gr.loads(gr.dumps(g)).nodes[a.id].by == "user"


def test_add_node_validates():
    g = gr.new_girraph("t")
    with pytest.raises(gr.GirraphError, match="parent"):
        gr.add_node(g, type="note", label="x", parent="q9")
    with pytest.raises(gr.GirraphError, match="girraph"):
        gr.add_node(g, type="girraph", label="x", ref="not-a-girraph.md")
    with pytest.raises(gr.GirraphError, match="unknown node type"):
        gr.add_node(g, type="opinion", label="x")
    # Sigils are accepted as type names.
    n = gr.add_node(g, type="?", label="sigil works")
    assert n.type == "issue"


def test_ids_never_reused_after_remove():
    g = gr.new_girraph("t")
    q = gr.add_node(g, type="issue", label="root")
    n2 = gr.add_node(g, type="note", label="highest", parent=q.id)
    assert n2.id == "n1"
    # Round-trip through disk format, then remove the max-numbered node.
    g = gr.loads(gr.dumps(g))
    gr.remove_node(g, "n1")
    n_new = gr.add_node(g, type="note", label="fresh", parent=q.id)
    assert n_new.id == "n2"  # n1 is never recycled


def test_update_node_patch_and_clear():
    g = gr.loads(EXAMPLE)
    gr.update_node(g, "a1", label="Sharper claim", by="")
    assert g.nodes["a1"].label == "Sharper claim"
    assert g.nodes["a1"].by is None
    gr.update_node(g, "q1", detail="")
    assert "q1 >" not in gr.dumps(g)
    with pytest.raises(gr.GirraphError):
        gr.update_node(g, "zz9", label="nope")


def test_reparent_rejects_own_subtree():
    g = gr.loads(EXAMPLE)
    with pytest.raises(gr.GirraphError, match="subtree"):
        gr.update_node(g, "q1", parent="a1")
    gr.update_node(g, "a3", parent="p1")
    assert g.nodes["a3"].parent == "p1"


def test_link_and_unlink():
    g = gr.loads(EXAMPLE)
    gr.link_nodes(g, "a1", "a3")
    assert g.nodes["a1"].cross == ["a3"]
    gr.link_nodes(g, "a1", "a3")  # idempotent
    assert g.nodes["a1"].cross == ["a3"]
    with pytest.raises(gr.GirraphError):
        gr.link_nodes(g, "a1", "a1")
    gr.unlink_nodes(g, "a1", "a3")
    assert g.nodes["a1"].cross == []


def test_remove_refuses_orphaning():
    g = gr.loads(EXAMPLE)
    with pytest.raises(gr.GirraphError, match="children"):
        gr.remove_node(g, "p1")
    removed = gr.remove_node(g, "p1", cascade=True)
    assert set(removed) == {"p1", "a1", "a2", "g1"}
    # a3's cross-edge to the removed a2 was cleaned up.
    assert g.nodes["a3"].cross == []
    assert "p1" not in gr.dumps(g)


# ---------------------------------------------------------------------------
# ASCII render
# ---------------------------------------------------------------------------

def test_ascii_render_example():
    g = gr.loads(EXAMPLE)
    art = gr.ascii_render(g)
    assert "🦒 Should enough ship a plugin API?" in art
    assert "q1 ❓ Should enough ship a plugin API?" in art
    assert "(+detail)" in art
    assert "[→ a2]" in art
    assert "├─ " in art and "└─ " in art
    # Refs are one-line stubs, never inlined content.
    assert "ref:rness/girraphs/versioning.girraph" in art


def test_ascii_render_depth_limits():
    g = gr.new_girraph("deep")
    parent = gr.add_node(g, type="issue", label="level 0").id
    for i in range(1, 6):
        parent = gr.add_node(g, type="position", label=f"level {i}", parent=parent).id
    art = gr.ascii_render(g, depth=1)
    assert "level 1" in art
    assert "level 2" not in art
    assert "not shown" in art
    full = gr.ascii_render(g)
    assert "level 5" in full


def test_ascii_render_subtree_and_unknown_node():
    g = gr.loads(EXAMPLE)
    art = gr.ascii_render(g, node="p2", depth=1)
    assert art.splitlines()[-1].endswith("[→ a2]")
    assert "p1" not in art.replace("p2", "")
    with pytest.raises(gr.GirraphError):
        gr.ascii_render(g, node="zz1")


def test_ascii_render_marks_broken_refs(tmp_path: Path):
    g = gr.loads(EXAMPLE)
    art = gr.ascii_render(g, project_dir=tmp_path)
    assert "⚠ broken ref:infoworld/plugins-survey.md" in art
    (tmp_path / "infoworld").mkdir()
    (tmp_path / "infoworld" / "plugins-survey.md").write_text("hi")
    art2 = gr.ascii_render(g, project_dir=tmp_path)
    assert "⚠ broken ref:infoworld/plugins-survey.md" not in art2


def test_save_and_load(tmp_path: Path):
    g = gr.new_girraph("On disk")
    gr.add_node(g, type="issue", label="Persist me?")
    p = tmp_path / "maps" / "test.girraph"
    gr.save(p, g)
    g2 = gr.load(p)
    assert g2.title == "On disk"
    assert g2.nodes["q1"].label == "Persist me?"
    with pytest.raises(gr.GirraphError, match="no girraph"):
        gr.load(tmp_path / "missing.girraph")
