"""Tests for girraph → merirmaid: the ``to_mermaid`` converter (shapes,
labels, edges, classDefs, clicks, determinism), the mirror-link sniff +
``refresh_mirror`` semantics, the ``POST /api/girraph/merirmaid`` endpoint
(create / idempotent-regen / 409), and that a girraph mutation through ANY
door (the four panel endpoints + a tool runner) regenerates the mirror.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from enough import girraph as gr
from enough import tools
from enough.server import create_app


# --------------------------------------------------------------------------
# to_mermaid — pure converter
# --------------------------------------------------------------------------

def _sample() -> gr.Girraph:
    """One node of each type, a cross-edge, and two refs (a note→.md doc and
    an @→.girraph nested map)."""
    g = gr.new_girraph("Ship a plugin API?")
    gr.add_node(g, type="issue", label="Should enough ship a plugin API?")        # q1
    gr.add_node(g, type="position", label="Ship a minimal one", parent="q1")      # p1
    gr.add_node(g, type="support", label="Ecosystem growth needs hooks",
                parent="p1")                                                       # a1
    gr.add_node(g, type="objection", label="Skills already cover 80%",
                parent="p1")                                                       # a2
    gr.add_node(g, type="note", label="Background", parent="q1",
                ref="plans/notes/survey.md")                                       # n1
    gr.add_node(g, type="girraph", label="Subproblem: versioning", parent="p1",
                ref="plans/sub.girraph")                                           # g1
    gr.link_nodes(g, "a2", "a1")                                                   # cross
    return g


def _body(text: str) -> str:
    """The flowchart body (everything after the closing frontmatter fence)."""
    return text.split("---\n")[-1]


def test_frontmatter_shape():
    text = gr.to_mermaid(_sample(), source_rel="plans/deep.girraph")
    head = text.split("---\n")[1]
    assert "merirmaid: 1" in head
    assert "modality: mirror" in head
    assert "kind: girraph-mirror" in head
    assert "source: plans/deep.girraph" in head
    assert "node-char-limit: 48" in head
    assert "title: Ship a plugin API?" in head
    assert "\ngenerated: " in "\n" + head


def test_node_shapes_by_type():
    body = _body(gr.to_mermaid(_sample(), source_rel="plans/deep.girraph"))
    assert 'q1{{"❓ Should enough ship a plugin API?"}}' in body   # issue → hexagon
    assert 'p1(["💡 Ship a minimal one"])' in body                # position → stadium
    assert 'a1["➕ Ecosystem growth needs hooks"]' in body        # support → rect
    assert 'a2["➖ Skills already cover 80%"]' in body            # objection → rect
    assert 'n1("📄 Background")' in body                          # note → rounded
    assert 'g1[["🦒 Subproblem: versioning"]]' in body           # girraph → subroutine


def test_tree_and_cross_edges():
    body = _body(gr.to_mermaid(_sample(), source_rel="plans/deep.girraph"))
    for edge in ("q1 --> p1", "p1 --> a1", "p1 --> a2", "q1 --> n1", "p1 --> g1"):
        assert f"  {edge}" in body
    assert "  a2 -.-> a1" in body                                 # cross uses dotted


def test_classdefs_stroke_only():
    body = _body(gr.to_mermaid(_sample(), source_rel="plans/deep.girraph"))
    assert "classDef support stroke:#3fa34d;" in body
    assert "classDef objection stroke:#c0392b;" in body
    assert "class a1 support;" in body
    assert "class a2 objection;" in body
    # Stroke only — no fill directives leak in.
    assert "fill:" not in body


def test_click_lines_rebased_to_mirror_dir():
    body = _body(gr.to_mermaid(_sample(), source_rel="plans/deep.girraph"))
    # Mirror lives in plans/; a project-relative ref is rebased against it.
    assert 'click n1 "notes/survey.md"' in body
    assert 'click g1 "sub.girraph"' in body


def test_click_rebasing_escapes_parent_dir():
    g = gr.new_girraph("root")
    gr.add_node(g, type="note", label="ref out", ref="rness/io/notes.md")   # n1
    body = _body(gr.to_mermaid(g, source_rel="plans/deep.girraph"))
    assert 'click n1 "../rness/io/notes.md"' in body


def test_label_truncation():
    g = gr.new_girraph("t")
    long = "x" * 80
    gr.add_node(g, type="support", label=long)                              # a1
    body = _body(gr.to_mermaid(g, source_rel="a.girraph", char_limit=20))
    # emoji + space + text, capped at char_limit with an ellipsis marker.
    import re
    m = re.search(r'a1\["([^"]*)"\]', body)
    assert m and m.group(1).endswith("…")
    assert len(m.group(1)) <= 20


def test_label_escaping_quotes():
    g = gr.new_girraph("t")
    gr.add_node(g, type="support", label='say "hi" now')                    # a1
    body = _body(gr.to_mermaid(g, source_rel="a.girraph"))
    assert 'a1["➕ say #quot;hi#quot; now"]' in body
    assert '"hi"' not in body.replace('a1["', "")                           # no raw quotes


def test_deterministic_output():
    g = _sample()
    a = _body(gr.to_mermaid(g, source_rel="plans/deep.girraph"))
    b = _body(gr.to_mermaid(g, source_rel="plans/deep.girraph"))
    assert a == b


# --------------------------------------------------------------------------
# mirror_path / has_mirror / refresh_mirror — the sniff + regen semantics
# --------------------------------------------------------------------------

def _write_girraph(target: Path, g: gr.Girraph) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(gr.dumps(g), encoding="utf-8")


def test_mirror_path():
    assert gr.mirror_path(Path("a/b/x.girraph")) == Path("a/b/x.merirmaid")


def test_refresh_noop_without_sibling(tmp_path: Path):
    target = tmp_path / "plans" / "x.girraph"
    _write_girraph(target, _sample())
    assert gr.refresh_mirror(target) is None
    assert not gr.mirror_path(target).exists()


def test_refresh_noop_for_non_mirror_sibling(tmp_path: Path):
    target = tmp_path / "plans" / "x.girraph"
    _write_girraph(target, _sample())
    # A hand-authored wip diagram that happens to share the name — no kind.
    hand = "---\nmerirmaid: 1\ntitle: mine\nmodality: wip\n---\nflowchart TD\n  A\n"
    gr.mirror_path(target).write_text(hand, encoding="utf-8")
    assert gr.has_mirror(target) is False
    assert gr.refresh_mirror(target) is None
    assert gr.mirror_path(target).read_text(encoding="utf-8") == hand       # untouched


def test_refresh_regenerates_when_sniff_passes(tmp_path: Path):
    target = tmp_path / "plans" / "x.girraph"
    _write_girraph(target, _sample())
    gr.create_mirror(target, "plans/x.girraph")
    assert gr.has_mirror(target) is True

    # Mutate the girraph and save — save() calls refresh_mirror.
    with gr.path_lock(target):
        g = gr.load(target)
        gr.add_node(g, type="support", label="a fresh new argument", parent="p1")
        gr.save(target, g)
    mirror = gr.mirror_path(target).read_text(encoding="utf-8")
    assert "a fresh new argument" in mirror
    # source: preserved from the original create, not recomputed.
    assert "source: plans/x.girraph" in mirror


# --------------------------------------------------------------------------
# Endpoint + regeneration-through-every-door
# --------------------------------------------------------------------------

@pytest.fixture()
def client(tmp_path: Path):
    app = create_app(tmp_path, "http://127.0.0.1:1/v1", supervise=False)
    with TestClient(app) as c:
        yield c


REL = "plans/api.girraph"


def _seed(client: TestClient) -> None:
    r = client.post("/api/girraph/node",
                    data={"path": REL, "type": "issue", "label": "Root?"})
    assert r.status_code == 200, r.text
    client.post("/api/girraph/node",
                data={"path": REL, "type": "position", "label": "Yes", "parent": "q1"})


def test_endpoint_create_and_get_field(client: TestClient, tmp_path: Path):
    _seed(client)
    # No mirror yet.
    assert client.get("/api/girraph", params={"path": REL}).json()["merirmaid"] is None

    r = client.post("/api/girraph/merirmaid", json={"path": REL})
    assert r.status_code == 200, r.text
    assert r.json() == {"merirmaid": "plans/api.merirmaid"}
    mp = tmp_path / "plans" / "api.merirmaid"
    assert mp.is_file()
    assert "kind: girraph-mirror" in mp.read_text(encoding="utf-8")

    # GET now advertises the link.
    assert client.get("/api/girraph",
                      params={"path": REL}).json()["merirmaid"] == "plans/api.merirmaid"


def test_endpoint_idempotent_regen(client: TestClient, tmp_path: Path):
    _seed(client)
    client.post("/api/girraph/merirmaid", json={"path": REL})
    r = client.post("/api/girraph/merirmaid", json={"path": REL})   # second call
    assert r.status_code == 200
    assert r.json() == {"merirmaid": "plans/api.merirmaid"}


def test_endpoint_409_on_foreign_sibling(client: TestClient, tmp_path: Path):
    _seed(client)
    # A non-mirror .merirmaid already claims the sibling name.
    sib = tmp_path / "plans" / "api.merirmaid"
    sib.write_text("---\nmerirmaid: 1\ntitle: mine\nmodality: wip\n---\nflowchart TD\n  A\n",
                   encoding="utf-8")
    r = client.post("/api/girraph/merirmaid", json={"path": REL})
    assert r.status_code == 409


def test_endpoint_404_missing_girraph(client: TestClient):
    r = client.post("/api/girraph/merirmaid", json={"path": "plans/nope.girraph"})
    assert r.status_code == 404


def _mirror_text(tmp_path: Path) -> str:
    return (tmp_path / "plans" / "api.merirmaid").read_text(encoding="utf-8")


def test_regen_fires_on_add_endpoint(client: TestClient, tmp_path: Path):
    _seed(client)
    client.post("/api/girraph/merirmaid", json={"path": REL})
    client.post("/api/girraph/node",
                data={"path": REL, "type": "support", "label": "added via POST",
                      "parent": "p1"})
    assert "added via POST" in _mirror_text(tmp_path)


def test_regen_fires_on_patch_endpoint(client: TestClient, tmp_path: Path):
    _seed(client)
    client.post("/api/girraph/merirmaid", json={"path": REL})
    client.patch("/api/girraph/node",
                 data={"path": REL, "id": "p1", "label": "patched label"})
    assert "patched label" in _mirror_text(tmp_path)


def test_regen_fires_on_link_endpoint(client: TestClient, tmp_path: Path):
    _seed(client)
    client.post("/api/girraph/merirmaid", json={"path": REL})
    client.post("/api/girraph/link", data={"path": REL, "from": "p1", "to": "q1"})
    assert "p1 -.-> q1" in _mirror_text(tmp_path)


def test_regen_fires_on_delete_endpoint(client: TestClient, tmp_path: Path):
    _seed(client)
    client.post("/api/girraph/node",
                data={"path": REL, "type": "note", "label": "doomed note", "parent": "q1"})
    client.post("/api/girraph/merirmaid", json={"path": REL})
    assert "doomed note" in _mirror_text(tmp_path)
    client.delete("/api/girraph/node", params={"path": REL, "id": "n1"})
    assert "doomed note" not in _mirror_text(tmp_path)


def test_regen_fires_on_tool_runner(client: TestClient, tmp_path: Path):
    _seed(client)
    client.post("/api/girraph/merirmaid", json={"path": REL})

    def _call(**extra):
        return tools.ToolCall(name="add_node", path=REL, content=None,
                              command=None, url=None, extra=extra, raw="", span=(0, 0))

    r = tools.run_girraph_add_node(
        tmp_path, _call(type="support", label="added via tool", parent="p1"))
    assert r.ok, r.body
    assert "added via tool" in _mirror_text(tmp_path)
