"""Tests for the girraph broker tools (tools.py runners): every op, the
confirmation/cascade gates, the write_file denial, and the round-trip
acceptance case (agent creates → "user" edits → agent patches → file
stays clean)."""

from __future__ import annotations

from pathlib import Path

from enough import girraph as gr
from enough import tools


def call(name: str, path: str | None = None, **extra: str) -> tools.ToolCall:
    return tools.ToolCall(
        name=name, path=path, content=None, command=None, url=None,
        extra=extra, raw="", span=(0, 0),
    )


def make_map(project: Path) -> str:
    """Agent-style creation: root via parentless add_node, then children."""
    rel = "plans/test.girraph"
    r = tools.run_girraph_add_node(
        project, call("add_node", rel, type="issue", label="Ship it?"))
    assert r.ok, r.body
    assert "file created" in r.body and "q1" in r.body
    r = tools.run_girraph_add_node(
        project, call("add_node", rel, type="position", label="Yes", parent="q1"))
    assert r.ok and "p1" in r.body
    r = tools.run_girraph_add_node(
        project, call("add_node", rel, type="objection", label="Too risky",
                      parent="p1", by="user"))
    assert r.ok and "a1" in r.body
    return rel


def test_round_trip_agent_user_agent(tmp_path: Path):
    rel = make_map(tmp_path)
    target = tmp_path / rel
    # "User edits a label in the panel" — same node ops the UI uses.
    with gr.path_lock(target):
        g = gr.load(target)
        gr.update_node(g, "p1", label="Yes — minimal surface")
        gr.save(target, g)
    # Agent patches another node.
    r = tools.run_girraph_update_node(
        tmp_path, call("update_node", rel, id="a1", label="Maintenance burden"))
    assert r.ok, r.body
    # File is clean, parseable, both edits landed, no warnings.
    g = gr.load(target)
    assert g.warnings == []
    assert g.nodes["p1"].label == "Yes — minimal surface"
    assert g.nodes["a1"].label == "Maintenance burden"
    text = target.read_text(encoding="utf-8")
    assert text.startswith("%girraph 0.1\n")
    assert "→" not in text  # ASCII-canonical on disk


def test_read_girraph_depth_stubs(tmp_path: Path):
    rel = make_map(tmp_path)
    tools.run_girraph_add_node(
        tmp_path, call("add_node", rel, type="girraph", label="Subproblem",
                       parent="a1", ref="plans/sub.girraph"))
    r = tools.run_read_girraph(tmp_path, call("read_girraph", rel))
    assert r.ok
    assert "q1" in r.body and "p1" in r.body
    assert "a1 ➖" not in r.body      # depth 1 truncates the grandchild…
    assert "not shown" in r.body     # …to a stub marker
    r2 = tools.run_read_girraph(tmp_path, call("read_girraph", rel, depth="3"))
    assert "g1" in r2.body
    assert "⚠ broken ref:plans/sub.girraph" in r2.body  # target doesn't exist
    r3 = tools.run_read_girraph(
        tmp_path, call("read_girraph", rel, node="p1", depth="1"))
    assert "a1" in r3.body and "q1 ❓" not in r3.body


def test_add_node_errors(tmp_path: Path):
    rel = "plans/missing.girraph"
    r = tools.run_girraph_add_node(
        tmp_path, call("add_node", rel, type="note", label="x", parent="q1"))
    assert not r.ok and "does not exist" in r.body
    r = tools.run_girraph_add_node(
        tmp_path, call("add_node", "plans/notes.md", type="note", label="x"))
    assert not r.ok and ".girraph" in r.body
    rel = make_map(tmp_path)
    r = tools.run_girraph_add_node(
        tmp_path, call("add_node", rel, type="bogus", label="x", parent="q1"))
    assert not r.ok and "unknown node type" in r.body


def test_update_clear_and_absent_fields(tmp_path: Path):
    rel = make_map(tmp_path)
    r = tools.run_girraph_update_node(
        tmp_path, call("update_node", rel, id="a1", by=""))
    assert r.ok
    g = gr.load(tmp_path / rel)
    assert g.nodes["a1"].by is None          # empty tag cleared it
    assert g.nodes["a1"].label == "Too risky"  # absent tag untouched
    r = tools.run_girraph_update_node(tmp_path, call("update_node", rel, id="a1"))
    assert not r.ok and "nothing to update" in r.body


def test_link_and_unlink(tmp_path: Path):
    rel = make_map(tmp_path)
    r = tools.run_girraph_link_nodes(
        tmp_path, call("link_nodes", rel, **{"from": "a1", "to": "q1"}))
    assert r.ok
    assert "[-> q1]" in (tmp_path / rel).read_text()
    r = tools.run_girraph_link_nodes(
        tmp_path, call("link_nodes", rel, remove="true", **{"from": "a1", "to": "q1"}))
    assert r.ok
    assert "[-> q1]" not in (tmp_path / rel).read_text()


def test_remove_requires_confirmation_and_cascade(tmp_path: Path):
    rel = make_map(tmp_path)
    r = tools.run_girraph_remove_node(
        tmp_path, call("remove_node", rel, id="a1"))
    assert not r.ok and "confirmation" in r.body
    r = tools.run_girraph_remove_node(
        tmp_path, call("remove_node", rel, id="p1", confirmed="yes"))
    assert not r.ok and "children" in r.body  # no orphaning
    r = tools.run_girraph_remove_node(
        tmp_path, call("remove_node", rel, id="p1", confirmed="yes", cascade="true"))
    assert r.ok and "p1" in r.body and "a1" in r.body
    g = gr.load(tmp_path / rel)
    assert list(g.nodes) == ["q1"]


def test_write_file_denied_for_girraph(tmp_path: Path):
    rel = make_map(tmp_path)
    wcall = tools.ToolCall(
        name="write_file", path=rel, content="%girraph 0.1\n\nq1 ? clobbered\n",
        command=None, url=None, extra={}, raw="", span=(0, 0),
    )
    r = tools.run_write_file(tmp_path, wcall)
    assert not r.ok and "node-by-node" in r.body
    # Original content untouched.
    assert gr.load(tmp_path / rel).nodes["q1"].label == "Ship it?"


def test_dispatch_routes_girraph_tools(tmp_path: Path):
    parsed = tools.parse_tool_calls(
        '<tool name="add_node">\n'
        "<path>plans/d.girraph</path>\n"
        "<type>issue</type>\n"
        "<label>Dispatched?</label>\n"
        "</tool>"
    )
    assert len(parsed) == 1
    r = tools.execute(tmp_path, parsed[0])
    assert r.ok and "q1" in r.body
    r2 = tools.execute(
        tmp_path,
        tools.parse_tool_calls(
            '<tool name="read_girraph"><path>plans/d.girraph</path></tool>'
        )[0],
    )
    assert r2.ok and "Dispatched?" in r2.body
