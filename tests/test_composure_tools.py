"""The readvisor's eight composure tools.

These go through `tools.execute()` rather than calling the runners
directly, because dispatch registration and the broker gate are half of
what is being asserted: a tool that exists but is not in `_DISPATCH` is a
tool the readvisor cannot call.

`broker.CONFIG_PATH` is monkeypatched by attribute — it is resolved from
`Path.home()` at import time, so moving `$HOME` afterwards does not move it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from enough import broker
from enough import composure as C
from enough import tools
from enough.tools import ToolCall

REL = "rness/io/composure/board.comp"


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    (home / "enough" / "config").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(broker, "CONFIG_PATH",
                        home / "enough" / "config" / "broker.json")
    proj = tmp_path / "project"
    (proj / "rness" / "io" / "composure").mkdir(parents=True)
    (proj / "rness" / "knowledge" / "session-logs").mkdir(parents=True)
    return proj


def call(tool: str, path: str | None = None, content: str | None = None,
         **extra) -> ToolCall:
    """A ToolCall as `parse_tool_calls` would build it: `<path>`,
    `<content>`, and every other inner tag in `extra`."""
    return ToolCall(name=tool, path=path, content=content, command=None,
                    url=None, extra={k: str(v) for k, v in extra.items()},
                    raw="", span=(0, 0))


def run(project: Path, tool: str, **kw):
    """Through `tools.execute`, not the runner — dispatch registration and
    the broker gate are half of what is under test."""
    return tools.execute(project, call(tool, **kw))


def seed(project: Path, form: str = "cards", title: str = "Board") -> str:
    result = run(project, "new_composure", form=form, title=title)
    assert result.ok, result.body
    return result.key


# ---------------------------------------------------------------------------
# Registration and the broker gate
# ---------------------------------------------------------------------------

def test_all_eight_tools_are_dispatchable_and_traced():
    from enough import composure_tools

    for name in composure_tools.TOOL_NAMES:
        assert name in tools._DISPATCH, name
        assert tools._TRACE_TOGGLE[name] == "trace_log_enabled", name


def test_the_toggle_exists_and_defaults_on():
    toggle = next(t for t in broker.TOGGLES if t.key == "composure_enabled")
    assert toggle.default is True and toggle.group == "composure"
    assert "composure" in toggle.label


@pytest.mark.parametrize("name", [
    "read_composure", "new_composure", "comp_add_module",
    "comp_update_module", "comp_set_page", "comp_remove_module",
    "comp_arrange", "comp_save_as_form",
])
def test_every_tool_is_gated_by_the_toggle(project: Path, name: str):
    cfg = {t.key: t.default for t in broker.TOGGLES}
    cfg["composure_enabled"] = False
    broker.save_config(cfg)
    result = run(project, name, path=REL)
    assert result.ok is False
    assert result.body == broker.denial_composure_disabled()
    assert "broker pane" in result.body


# ---------------------------------------------------------------------------
# read_composure
# ---------------------------------------------------------------------------

def test_read_composure_returns_the_outline(project: Path):
    rel = seed(project)
    out = run(project, "read_composure", path=rel)
    assert out.ok
    assert out.body.startswith("composure: Board")
    assert "form: cards" in out.body
    assert "16 module(s)" in out.body
    assert out.body.count("\n") < 30          # compact, by construction


def test_read_composure_can_fetch_one_module(project: Path):
    rel = seed(project, form="blank")
    mid = C.load(project / rel).modules[0].id
    run(project, "comp_set_page", path=rel, module=mid,
        content="\n# Title\n\nbody text\n")
    out = run(project, "read_composure", path=rel, module=mid)
    assert out.ok and "# Title" in out.body and "body text" in out.body
    bad = run(project, "read_composure", path=rel, module="mnope")
    assert not bad.ok and "no module" in bad.body


def test_long_module_text_is_cached_not_dumped(project: Path):
    rel = seed(project, form="blank")
    mid = C.load(project / rel).modules[0].id
    run(project, "comp_set_page", path=rel, module=mid,
        content="\n" + ("a long paragraph of prose. " * 400))
    out = run(project, "read_composure", path=rel, module=mid)
    assert out.ok
    assert "full text cached at: rness/io/input/" in out.body
    assert len(out.body) < 3000
    cached = next((project / "rness" / "io" / "input").glob("*-comp-*.md"))
    assert "a long paragraph" in cached.read_text(encoding="utf-8")


def test_read_composure_path_rules(project: Path):
    missing = run(project, "read_composure", path="rness/io/composure/x.comp")
    assert not missing.ok and "no composure at" in missing.body
    wrong = run(project, "read_composure", path="notes/plan.md")
    assert not wrong.ok and "not a composure" in wrong.body
    none = run(project, "read_composure")
    assert not none.ok and "needs a <path>" in none.body
    escape = run(project, "read_composure", path="../../escape.comp")
    assert not escape.ok and "escapes project directory" in escape.body


# ---------------------------------------------------------------------------
# new_composure
# ---------------------------------------------------------------------------

def test_new_composure_writes_immediately_and_reports_the_path(project: Path):
    out = run(project, "new_composure", form="scaffold", title="Chapter map")
    assert out.ok
    assert out.key.startswith("rness/io/composure/chapter-map-")
    assert (project / out.key).is_file()
    assert "from the scaffold form" in out.body
    assert "composure: Chapter map" in out.body
    assert out.side_effects["composure"]["source"] == "readvisor"
    assert out.side_effects["composure"]["created"] is True


def test_new_composure_needs_a_title_and_a_known_form(project: Path):
    assert "needs a <title>" in run(project, "new_composure",
                                    form="blank").body
    bad = run(project, "new_composure", form="nope", title="x")
    assert not bad.ok and "no composure form" in bad.body


# ---------------------------------------------------------------------------
# module ops
# ---------------------------------------------------------------------------

def test_comp_add_module_places_itself(project: Path):
    rel = seed(project, form="blank")
    out = run(project, "comp_add_module", path=rel, type="text",
              title="Act one", bg="yellow",
              content="\n- [ ] move the confession earlier\n")
    assert out.ok and "added text module" in out.body
    comp = C.load(project / rel)
    m = comp.modules[-1]
    assert m.title == "Act one" and m.bg == "yellow"
    assert '<li data-check="0">' in m.pages[0].rich
    assert m.id in out.body                # the readvisor can quote it back
    # It was placed, not stacked.
    assert not C._overlaps((m.x, m.y, m.w, m.h),
                           (comp.modules[0].x, comp.modules[0].y,
                            comp.modules[0].w, comp.modules[0].h))


def test_comp_add_module_reports_a_bad_swatch(project: Path):
    rel = seed(project)
    out = run(project, "comp_add_module", path=rel, type="text", bg="#ff0000")
    assert not out.ok and "named swatches" in out.body
    out = run(project, "comp_add_module", path=rel, type="text", x="over there")
    assert not out.ok and "<x> must be a number" in out.body


def test_comp_update_module(project: Path):
    rel = seed(project)
    mid = C.load(project / rel).modules[0].id
    out = run(project, "comp_update_module", path=rel, module=mid,
              bg="green", title="Resolved")
    assert out.ok
    m = C.load(project / rel).module(mid)
    assert m.bg == "green" and m.title == "Resolved"
    assert "needs a <module>" in run(project, "comp_update_module",
                                     path=rel).body
    assert "at least one field" in run(project, "comp_update_module", path=rel,
                                       module=mid).body


def test_comp_set_page_replaces_and_appends(project: Path):
    rel = seed(project, form="blank")
    mid = C.load(project / rel).modules[0].id
    run(project, "comp_set_page", path=rel, module=mid, content="\nfirst\n")
    run(project, "comp_set_page", path=rel, module=mid, append="true",
        content="\nsecond\n")
    pages = C.load(project / rel).module(mid).pages
    assert len(pages) == 2
    assert "first" in pages[0].rich and "second" in pages[1].rich
    assert "needs <content>" in run(project, "comp_set_page", path=rel,
                                    module=mid).body


def test_comp_remove_module_requires_confirmation(project: Path):
    rel = seed(project)
    mid = C.load(project / rel).modules[0].id
    unconfirmed = run(project, "comp_remove_module", path=rel, module=mid)
    assert not unconfirmed.ok
    assert "explicit confirmation" in unconfirmed.body
    assert "Never pre-fill it" in unconfirmed.body
    assert C.load(project / rel).module(mid) is not None

    confirmed = run(project, "comp_remove_module", path=rel, module=mid,
                    confirmed="yes")
    assert confirmed.ok and C.load(project / rel).module(mid) is None


def test_comp_arrange(project: Path):
    rel = seed(project)
    ids = [m.id for m in C.load(project / rel).modules[:4]]
    out = run(project, "comp_arrange", path=rel, modules=" ".join(ids),
              mode="column")
    assert out.ok and "as a column" in out.body
    comp = C.load(project / rel)
    assert len({comp.module(i).x for i in ids}) == 1
    assert "needs <modules>" in run(project, "comp_arrange", path=rel).body
    assert "no module" in run(project, "comp_arrange", path=rel,
                              modules="mnope").body


def test_comp_save_as_form(project: Path):
    rel = seed(project)
    out = run(project, "comp_save_as_form", path=rel, name="Chapter Map")
    assert out.ok and "chapter-map" in out.body
    assert (project / "rness" / "composure-forms" / "chapter-map.comp").is_file()
    made = run(project, "new_composure", form="chapter-map", title="Reused")
    assert made.ok
    assert "needs a <name>" in run(project, "comp_save_as_form", path=rel).body


# ---------------------------------------------------------------------------
# The rules the tools carry that the UI does not
# ---------------------------------------------------------------------------

def test_tools_cannot_rewrite_a_filed_journal_page(project: Path):
    rel = seed(project, form="journal", title="Journal")
    mid = C.load(project / rel).modules[0].id
    run(project, "comp_set_page", path=rel, module=mid, content="\ntoday\n")
    C.apply_ops(project / rel, None,
                [{"op": "file_page", "module": mid, "n": 1}],
                source="ui", rel_path=rel)
    blocked = run(project, "comp_set_page", path=rel, module=mid,
                  content="\nrewritten\n")
    assert not blocked.ok and "permanently read-only" in blocked.body
    assert "today" in C.load(project / rel).module(mid).pages[0].rich


def test_tools_cannot_rewrite_a_council_statement(project: Path):
    rel = seed(project, form="council", title="Council")
    mid = C.apply_ops(
        project / rel, None,
        [{"op": "add_module", "type": "text", "speaker": "Ed", "turn": "1",
          "markdown": "the statement"}],
        source="council", rel_path=rel).changed[0]
    blocked = run(project, "comp_set_page", path=rel, module=mid,
                  content="\nforged\n")
    assert not blocked.ok and "council engine owns" in blocked.body
    removed = run(project, "comp_remove_module", path=rel, module=mid,
                  confirmed="yes")
    assert not removed.ok and "council engine owns" in removed.body


def test_write_file_refuses_a_comp_and_names_the_tools(project: Path):
    rel = seed(project)
    out = tools.run_write_file(project, call("write_file", path=rel,
                                             content="<html>clobbered"))
    assert not out.ok
    assert "module-by-module" in out.body
    for named in ("comp_add_module", "comp_set_page", "read_composure",
                  "new_composure"):
        assert named in out.body
    assert "clobbered" not in (project / rel).read_text(encoding="utf-8")


def test_write_file_refuses_the_comments_sidecar(project: Path):
    rel = seed(project)
    C.add_comment(project / rel, "x", {"module": "m1"}, rel)
    side = f"rness/io/composure/.{Path(rel).name}.comments.json"
    out = tools.run_write_file(project, call("write_file", path=side,
                                             content="[]"))
    assert not out.ok and "backend-owned" in out.body


def test_every_tool_call_lands_in_the_broker_journal(project: Path):
    rel = seed(project)
    run(project, "comp_add_module", path=rel, type="text", content="\nx\n")
    run(project, "comp_remove_module", path=rel, module="mnope")
    logs = list((project / "rness" / "knowledge" / "session-logs").glob(
        "*-broker.md"))
    assert logs, "no broker journal was written"
    text = logs[0].read_text(encoding="utf-8")
    assert "new_composure" in text and "comp_add_module" in text
    assert "comp_remove_module" in text


def test_prompt_documents_every_tool_in_the_new_vocabulary():
    """The composure docs moved out of the always-on `TOOL_INSTRUCTIONS` and
    behind the `composure_enabled` gate (P5b's tool-docs diet), so this now
    reads the block itself. Same assertion: every tool named, in the round's
    vocabulary."""
    from enough.prompt import COMPOSURE_TOOL_INSTRUCTIONS as section
    from enough import composure_tools

    for name in composure_tools.TOOL_NAMES:
        assert name in section, name
    assert section.lstrip().startswith("## Composures")
    # The round's vocabulary: readvisor, never agent.
    assert "readvisor" in section and "agent" not in section.lower()
    assert "composure" in section and "module" in section
