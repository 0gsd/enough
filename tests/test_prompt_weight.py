"""What the system prompt costs, and what it is allowed to cost.

Two things are pinned here, because nothing else in the suite was watching
either of them:

1. **Drift.** Every tool in `tools._DISPATCH` is documented in the fully
   enabled assembled prompt. A tool the model is never told about is a tool
   that does not exist, and until now nothing would have said so.
2. **Weight.** A local model re-reads the whole system prompt on every turn of
   every tool loop. The budgets below are deliberately close to what the tree
   costs today: the next round that adds a tool should have to look at this
   file and decide, rather than spending the user's context window quietly.

The scratch-safety rule applies here as everywhere: `HOME` and every
`ENOUGH_*` seam point inside `tmp_path` before anything reads state, and
`broker.CONFIG_PATH` is re-pointed by hand because it is resolved at import
time from `Path.home()`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from enough import broker
from enough import council as K
from enough import prompt
from enough import skeleton
from enough import tools as T

#: The always-on core: what every project pays on every turn — and, since
#: 0.4.1, the core plus the dictionary block, which every install that ships
#: FEED carries. `show_intro` with its one-time offer (~300 chars) and the
#: dictionary block (~580) both fit inside the existing headroom.
CORE_BUDGET = 17_500
#: Core plus every gated block an ordinary turn can carry — the worst case,
#: for a project using composures and forging readvisors. The pal block is
#: deliberately NOT in here: it is carried by the one turn the user opened
#: with `/pal` and by no other, so it is budgeted on its own below rather
#: than inflating the number every turn is measured against.
#: 0.4.1: +900 for the FEED block (~580) and the core's `show_intro` plus its
#: one-time offer (~300) — the tree measured ~21,960 before them, ~22,850
#: after.
FULL_BUDGET = 22_900
#: The `/pal` block, which rides along on a pal turn only. Small on purpose:
#: a turn that is about to spend the user's money on a cloud call is not the
#: turn to also spend a page of their context window.
PAL_BUDGET = 1_200
#: The chief's whole council system message (identity + framing), by the
#: repo's own char-based estimator. See `docs/composure-landed-P5.md`.
COUNCIL_HEAD_TOKENS = 2_500


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    (home / "enough" / "config").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    for var, rel in (("ENOUGH_PROJECTS_STATE", "state/projects.json"),
                     ("ENOUGH_CACHEAWL_ROOT", "cacheawl"),
                     ("ENOUGH_INFOWORLD_ROOT", "no-infoworld"),
                     ("ENOUGH_WIKISINK_CONFIG", "wikisink.json"),
                     ("ENOUGH_READVISORS_ROOT", "readvisors-global"),
                     ("ENOUGH_UI_CONFIG", "ui.json")):
        monkeypatch.setenv(var, str(tmp_path / rel))
    monkeypatch.setattr(broker, "CONFIG_PATH",
                        home / "enough" / "config" / "broker.json")
    # FEED ships, as in a real install: the dictionary block is in. A
    # manifest and a schema are all `dictionary.available()` asks about.
    feed = tmp_path / "feed-source"
    feed.mkdir()
    (feed / "manifest.json").write_text('{"digest": "x"}', encoding="utf-8")
    (feed / "schema.sql").write_text("", encoding="utf-8")
    monkeypatch.setenv("ENOUGH_DICT_SOURCE", str(feed))
    proj = tmp_path / "project"
    proj.mkdir()
    skeleton.ensure_skeleton(proj)
    assert str(Path.home()).startswith(str(tmp_path))
    return proj


def no_feed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ENOUGH_DICT_SOURCE", str(tmp_path / "no-feed-here"))


def set_toggle(key: str, value: bool) -> None:
    cfg = broker.load_config()
    cfg[key] = value
    broker.save_config(cfg)


def enable_skill(project: Path, name: str) -> None:
    """Skills are opt-in via a `.disabled` file; drop the name from it."""
    f = project / "rness" / "skills" / ".disabled"
    if f.is_file():
        keep = [ln for ln in f.read_text().splitlines() if ln.strip() != name]
        f.write_text("\n".join(keep) + ("\n" if keep else ""), encoding="utf-8")


def disable_skill(project: Path, name: str) -> None:
    f = project / "rness" / "skills" / ".disabled"
    names = set(f.read_text().split()) if f.is_file() else set()
    names.add(name)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("\n".join(sorted(names)) + "\n", encoding="utf-8")


def fully_enabled(project: Path) -> str:
    """Everything an ordinary turn can carry — what FULL_BUDGET measures."""
    enable_skill(project, "readvisory")
    set_toggle("composure_enabled", True)
    return prompt.tool_instructions(project)


def every_block(project: Path) -> str:
    """...plus the per-turn ones. Drift is measured against this: a tool is
    documented if the turn that can call it says so, not if every turn does."""
    return fully_enabled(project) + prompt.tool_instructions(project, pal=True)


# ---------------------------------------------------------------------------
# 1. Drift — every tool is documented
# ---------------------------------------------------------------------------

def test_every_dispatchable_tool_is_documented(project: Path):
    """The guard this file exists for. A tool in `_DISPATCH` that no prompt
    mentions can never be called, and nothing else in the suite notices."""
    text = every_block(project)
    missing = [name for name in sorted(T._DISPATCH) if name not in text]
    assert not missing, f"undocumented tools: {', '.join(missing)}"


def test_every_documented_tool_is_dispatchable(project: Path):
    """...and the other direction, which is how a renamed tool is caught:
    every `<tool name="x">` example names something that can actually run,
    and no example is written in a form the parser would not see as a call
    at all (`<tool>x`, `<tool name='x'>`) — a model copies what it is shown."""
    import re
    text = every_block(project)
    named = set(re.findall(r'<tool name="([a-z_]+)">', text))
    assert named, "no tool examples found at all"
    assert not (named - set(T._DISPATCH)), named - set(T._DISPATCH)
    openings = re.findall(r"<tool\b[^>\n]*>", text)
    nameless = [o for o in openings if not re.fullmatch(r'<tool name="[a-z_]+">', o)]
    assert not nameless, f"tool examples without name=\"…\": {nameless}"


def test_every_tool_example_round_trips_through_the_parser(project: Path):
    """What the prompt shows is what the harness parses: every `<tool …>…
    </tool>` example block in the fully-enabled docs comes back from
    `parse_tool_calls` as exactly one call of the same name, and is a
    complete call by `has_complete_tool_call`'s reckoning."""
    import re
    text = every_block(project)
    blocks = re.findall(r"<tool\b[^>\n]*>.*?</tool>", text, re.DOTALL)
    assert blocks, "no tool example blocks found"
    calls = T.parse_tool_calls(text)
    assert len(calls) == len(blocks), (len(calls), len(blocks))
    for block, call in zip(blocks, calls):
        assert call.raw == block, (call.name, block[:60])
        name = re.match(r'<tool name="([a-z_]+)">', block)
        assert name and call.name == name.group(1), block[:60]
        assert T.has_complete_tool_call(block), block[:60]
        assert len(T.parse_tool_calls(block)) == 1, block[:60]


def test_the_assembled_prompt_carries_the_tools_it_documents(project: Path):
    enable_skill(project, "readvisory")
    set_toggle("composure_enabled", True)
    ordinary = prompt.assemble_system_prompt(project)
    pal = prompt.assemble_system_prompt(project, pal=True)
    for name in sorted(T._DISPATCH):
        assert name in pal, name
        if name != "ask_pal":
            assert name in ordinary, name
    # ...and the one that is not in an ordinary turn is not in it by
    # accident: a tool the model cannot call is a tool it must not be told
    # about, or it will spend a turn trying.
    assert "ask_pal" not in ordinary


# ---------------------------------------------------------------------------
# 2. Gating
# ---------------------------------------------------------------------------

def test_the_composure_block_follows_its_broker_toggle(project: Path):
    enable_skill(project, "readvisory")
    set_toggle("composure_enabled", True)
    on = prompt.tool_instructions(project)
    assert "## Composures" in on and "comp_add_module" in on
    set_toggle("composure_enabled", False)
    off = prompt.tool_instructions(project)
    assert "## Composures" not in off and "comp_add_module" not in off
    assert "composure_from_outline" not in off
    # ...and the core is untouched either way.
    assert prompt.TOOL_INSTRUCTIONS in off
    assert len(on) - len(off) == len(prompt.COMPOSURE_TOOL_INSTRUCTIONS) + 1


def test_the_readvisory_block_follows_its_skill(project: Path):
    set_toggle("composure_enabled", True)
    disable_skill(project, "readvisory")
    off = prompt.tool_instructions(project)
    assert "install_readvisor" not in off
    enable_skill(project, "readvisory")
    on = prompt.tool_instructions(project)
    assert "install_readvisor" in on and "## Readvisors" in on


def test_the_dictionary_block_follows_the_dictionary_not_the_skill(
        project: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Zero setup: the FEED tools are documented wherever FEED ships, with
    the `lexicographer` skill on or (as by default) off."""
    set_toggle("composure_enabled", True)
    for skill in (disable_skill, enable_skill):
        skill(project, "lexicographer")
        on = prompt.tool_instructions(project)
        assert "## Dictionary" in on
        for name in ("dict_lookup", "dict_add_entry", "dict_update_entry", "dict_guide"):
            assert name in on, name
    no_feed(monkeypatch, tmp_path)
    off = prompt.tool_instructions(project)
    assert "## Dictionary" not in off and "dict_" not in off
    assert len(on) - len(off) == len(prompt.DICTIONARY_TOOL_INSTRUCTIONS) + 1


def test_show_intro_and_its_offer_are_in_the_always_on_core():
    assert '<tool name="show_intro">' in prompt.TOOL_INSTRUCTIONS
    assert '"want a brief introduction to enough?"' in prompt.TOOL_INSTRUCTIONS
    assert "show_intro" in T._DISPATCH


def test_the_pal_block_follows_the_turn_and_not_the_project(project: Path):
    """The narrowest gate in the file: not a project setting, not a toggle —
    one turn, the one the user opened by typing `/pal`."""
    set_toggle("composure_enabled", True)
    off = prompt.tool_instructions(project)
    on = prompt.tool_instructions(project, pal=True)
    assert "## Pal" not in off and "ask_pal" not in off
    assert "## Pal" in on and "ask_pal" in on
    assert len(on) - len(off) == len(prompt.PAL_TOOL_INSTRUCTIONS) + 1
    # The standing instruction rides with it, and only with it.
    assert prompt.PAL_TURN_INSTRUCTION.strip() not in \
        prompt.assemble_system_prompt(project)
    assert prompt.PAL_TURN_INSTRUCTION.strip() in \
        prompt.assemble_system_prompt(project, pal=True)


def test_a_pal_turn_is_a_chat_turn(project: Path):
    with pytest.raises(ValueError, match="pal turn is a chat turn"):
        prompt.assemble_system_prompt(project, readvisors="none",
                                      profile="council", pal=True)


def test_a_project_using_neither_pays_only_the_core(
        project: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """The whole point of the diet: a plain project is back to what it cost
    before composures and readvisor-forging existed — plus, where FEED
    ships, the dictionary block and nothing else."""
    set_toggle("composure_enabled", False)
    disable_skill(project, "readvisory")
    assert prompt.tool_instructions(project).strip() == (
        prompt.TOOL_INSTRUCTIONS.rstrip() + "\n\n"
        + prompt.DICTIONARY_TOOL_INSTRUCTIONS).strip()
    no_feed(monkeypatch, tmp_path)
    assert prompt.tool_instructions(project).strip() == \
        prompt.TOOL_INSTRUCTIONS.strip()


def test_an_unreadable_broker_config_does_not_hide_the_tools(project: Path,
                                                             monkeypatch):
    """A gate that fails closed would silently take working tools away. This
    one fails open — the tools themselves still refuse if the toggle is
    genuinely off."""
    def boom(_key):
        raise OSError("no broker config")
    monkeypatch.setattr(broker, "is_enabled", boom)
    assert "## Composures" in prompt.tool_instructions(project)


# ---------------------------------------------------------------------------
# 3. Budgets
# ---------------------------------------------------------------------------

def test_the_always_on_core_stays_inside_its_budget():
    size = len(prompt.TOOL_INSTRUCTIONS)
    assert size <= CORE_BUDGET, (
        f"the always-on tool docs are {size} chars, over the {CORE_BUDGET} "
        f"budget. Every char here is paid on every turn of every tool loop by "
        f"every project. Gate the new material behind a toggle (see "
        f"`prompt.tool_instructions`) or compress something first.")


def test_the_core_and_the_dictionary_block_stay_inside_the_core_budget():
    """What every project of an install with FEED pays."""
    size = len(prompt.TOOL_INSTRUCTIONS) + 1 + len(prompt.DICTIONARY_TOOL_INSTRUCTIONS)
    assert size <= CORE_BUDGET, (
        f"core + the dictionary block is {size} chars, over the {CORE_BUDGET} "
        f"budget every project pays. Compress one of them.")


def test_the_fully_enabled_tool_docs_stay_inside_their_budget(project: Path):
    size = len(fully_enabled(project))
    assert size <= FULL_BUDGET, (
        f"core + every gated block is {size} chars, over the {FULL_BUDGET} "
        f"budget. Raising this number is a decision, not a formality: it is "
        f"context window and prefill time on every turn.")


def test_the_pal_block_stays_inside_its_budget():
    size = len(prompt.PAL_TOOL_INSTRUCTIONS)
    assert size <= PAL_BUDGET, (
        f"the pal tool docs are {size} chars, over the {PAL_BUDGET} budget. "
        f"They are paid on a turn that is already about to pay a cloud bill; "
        f"cut something rather than raise this.")


def test_the_councils_chief_head_is_lean(project: Path):
    """P5's finding: the chat profile's assembled prompt is ~20 000 tokens,
    which is larger than a chief's whole share of an ordinary context window.
    The council profile is who the chief is and nothing else."""
    chat = prompt.assemble_system_prompt(project)
    council = prompt.assemble_system_prompt(project, readvisors="none",
                                            profile="council")
    head = K.identity_for(project, {"kind": "chief", "name": "Ed"}, "Ed")
    est = len(head) // 3
    assert est < COUNCIL_HEAD_TOKENS, (
        f"the chief's council system message is ~{est} tokens, over the "
        f"{COUNCIL_HEAD_TOKENS} budget — a council's whole memory is what "
        f"pays for it.")
    assert len(council) < len(chat) // 4


def test_neither_council_identity_carries_tool_machinery(project: Path):
    """A council turn calls no tools and the framing says so. Documentation
    for tools that cannot be called is the most expensive kind of dead
    text."""
    d = project / "rness" / "readvisors" / "close-reader"
    d.mkdir(parents=True, exist_ok=True)
    (d / "AGENT.md").write_text("# Nadia\n\nReads closely.\n", encoding="utf-8")
    (d / "MOTIVATION.md").write_text("The sentence.\n", encoding="utf-8")
    chief = K.identity_for(project, {"kind": "chief", "name": "Ed"}, "Ed")
    rv = K.identity_for(project, {"kind": "readvisor", "name": "Nadia",
                                  "folder": "close-reader"}, "Ed")
    for who, text in (("chief", chief), ("readvisor", rv)):
        assert "<tool name=" not in text, who
        assert "# Tools" not in text, who
        assert "install_readvisor" not in text, who
        assert "## Composures" not in text, who
    # The chat profile, by contrast, carries all of it.
    set_toggle("composure_enabled", True)
    assert "<tool name=" in prompt.assemble_system_prompt(project)


def test_the_council_profile_keeps_identity_and_drops_the_harness(
        project: Path):
    from enough import project_meta
    project_meta.save(project, None, "A novel about lighthouses.")
    (project / "rness" / "AGENT.md").write_text(
        "# Ed\n\nIDENTITY-MARKER\n", encoding="utf-8")
    (project / "rness" / "MOTIVATION.md").write_text(
        "MOTIVATION-MARKER\n", encoding="utf-8")
    (project / "rness" / "INTENTION.md").write_text(
        "INTENTION-MARKER\n", encoding="utf-8")
    text = prompt.assemble_system_prompt(project, readvisors="none",
                                         profile="council")
    for kept in ("chief readvisor", "IDENTITY-MARKER", "MOTIVATION-MARKER",
                 "A novel about lighthouses."):
        assert kept in text, kept
    for dropped in ("# Paradigm", "# Policies", "# Skills", "# Tools",
                    "INTENTION-MARKER", "# Converted documents",
                    "# Context", "# Active Readvisors"):
        assert dropped not in text, dropped


def test_an_unknown_profile_is_refused_by_name(project: Path):
    with pytest.raises(ValueError, match="unknown system-prompt profile"):
        prompt.assemble_system_prompt(project, profile="council-ish")


def test_the_chat_profile_is_unchanged_by_the_council_one(project: Path):
    """`profile` defaults to `chat`, and `chat` is what it always was."""
    set_toggle("composure_enabled", True)
    a = prompt.assemble_system_prompt(project)
    b = prompt.assemble_system_prompt(project, profile="chat")
    assert a == b
    for section in ("# Identity", "# Motivation", "# Paradigm", "# Tools",
                    "# Converted documents", "# Context"):
        assert section in a, section
