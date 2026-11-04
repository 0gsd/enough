"""What the system prompt costs, and what it is allowed to cost.

Three things are pinned here, because nothing else in the suite was watching
any of them:

1. **Drift.** Every tool in `tools._DISPATCH` is documented in the fully
   enabled assembled prompt. A tool the model is never told about is a tool
   that does not exist, and until now nothing would have said so.
2. **Weight.** A local model re-reads the whole system prompt on every turn of
   every tool loop. The budgets below are deliberately close to what the tree
   costs today: the next round that adds a tool should have to look at this
   file and decide, rather than spending the user's context window quietly.
3. **Fit** (0.4.3, docs/ctx-16gb-plan.md §8.5). Every context window
   `defaults/models.json` ships holds a fresh project's whole prompt plus a
   2,048-token reserve, except an explicit `KNOWN_TOO_SMALL` list that can
   only shrink.

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
#: 0.5.1: the core lost the girraph, review, wiki, cloud and canon-store
#: sections (now blocks of their own, two of them gated) and the cloud
#: example — it measured 13,0xx chars before, ~3.3k after. The budget
#: follows it down so the next section added to the always-on text is a
#: decision again.
CORE_BUDGET = 4_000
#: Core plus every gated block an ordinary turn can carry — the worst case,
#: for a project using composures and forging readvisors. The pal block is
#: deliberately NOT in here: it is carried by the one turn the user opened
#: with `/pal` and by no other, so it is budgeted on its own below rather
#: than inflating the number every turn is measured against.
#: 0.4.1: +900 for the FEED block (~580) and the core's `show_intro` plus its
#: one-time offer (~300) — the tree measured ~21,960 before them, ~22,850
#: after.
#: 0.4.3: +809, exactly `len(prompt.CANON_TOOL_INSTRUCTIONS)`, the MacroCOSM
#: block (owner decision 12: on by default, at most 1,000 chars) — the tree
#: measured 22,746 before it, 23,556 after.
#: 0.4.4: +156, exactly the `doc_lookup` lines added to that block (its
#: example and one sentence; the block went 809 -> 965 chars, still under
#: the owner's 1,000) — the tree measured 23,556 before them, 23,712 after.
#: 0.5.0: +29, exactly the block's growth for `thym_check` and `thym_run` (their
#: two examples and one sentence, paid for by shorter prose elsewhere in the
#: block; it went 965 -> 994 chars, still under the owner's 1,000) — the tree
#: measured 23,712 before them, 23,741 after.
#: 0.5.1: FULL now means every gate open — the cloud block (2.4k) and the
#: wiki block (2.2k) included, which an ordinary default install never
#: carries (no key, no archive) — minus the duplicated paradigm and AGENT.md
#: text the diet removed. The fully enabled tree measured 23,741 before the
#: round; the budget stays, as the ceiling it was.
FULL_BUDGET = 24_500
#: The lean profile's whole prompt for a fresh project, in chars: what an
#: 8,192-token window must hold with the 2,048 reserve at 3.7 chars/token,
#: less the project-path allowance — (8192 - 2048) * 3.7 ≈ 22.7k. Measured
#: 22,387 chars (5,977 gemma tokens, exact) when it landed; the fit test
#: below is the real guard, this number the early warning.
LEAN_BUDGET = 22_500
#: The owner's cap on the MacroCOSM tools' docs (docs/canon-043-plan.md §13).
CANON_BLOCK_MAX = 1_000
#: A fresh project's whole assembled system prompt at HEAD (0.4.2, d865818),
#: the project path written `<project>`: measured 2026-10-22 on this file's
#: fixture against HEAD's tree exported with `git archive` (P6). This round's
#: tree measured 74,166 before the MacroCOSM block and 74,976 after.
HEAD_DEFAULT_PROMPT = 74_307
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
                     ("ENOUGH_CANON_ROOT", "cacheawl"),
                     ("ENOUGH_INFOWORLD_ROOT", "no-infoworld"),
                     ("ENOUGH_WIKISINK_CONFIG", "wikisink.json"),
                     ("ENOUGH_READVISORS_ROOT", "readvisors-global"),
                     ("ENOUGH_UI_CONFIG", "ui.json")):
        monkeypatch.setenv(var, str(tmp_path / rel))
    monkeypatch.setattr(broker, "CONFIG_PATH",
                        home / "enough" / "config" / "broker.json")
    # The wiki gate (0.5.1) reads `wikisink.config.CONFIG_PATH`, which is
    # resolved from the env at import time like broker's — an earlier module
    # that imported it with an archive in its own tmp dir would otherwise
    # leave this fixture seeing an installed archive.
    from enough.wikisink import config as _wcfg
    monkeypatch.setattr(_wcfg, "CONFIG_PATH", tmp_path / "wikisink.json")
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


def open_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    """The two 0.5.1 gates that depend on the machine, not the project: the
    cloud gate (a key, a health check) and a Wikipedia archive. Opened by
    hand so a test sees the blocks they guard."""
    monkeypatch.setattr(prompt, "_cloud_usable", lambda: True)
    monkeypatch.setattr(prompt, "_wiki_installed", lambda: True)


def fully_enabled(project: Path, monkeypatch: pytest.MonkeyPatch | None = None) -> str:
    """Everything an ordinary turn can carry — what FULL_BUDGET measures."""
    enable_skill(project, "readvisory")
    set_toggle("composure_enabled", True)
    if monkeypatch is not None:
        open_gates(monkeypatch)
    return prompt.tool_instructions(project)


def every_block(project: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """...plus the per-turn ones. Drift is measured against this: a tool is
    documented if the turn that can call it says so, not if every turn does."""
    return fully_enabled(project, monkeypatch) + prompt.tool_instructions(project, pal=True)


# ---------------------------------------------------------------------------
# 1. Drift — every tool is documented
# ---------------------------------------------------------------------------

def test_every_dispatchable_tool_is_documented(project: Path, monkeypatch: pytest.MonkeyPatch):
    """The guard this file exists for. A tool in `_DISPATCH` that no prompt
    mentions can never be called, and nothing else in the suite notices."""
    text = every_block(project, monkeypatch)
    missing = [name for name in sorted(T._DISPATCH) if name not in text]
    assert not missing, f"undocumented tools: {', '.join(missing)}"


def test_every_documented_tool_is_dispatchable(project: Path, monkeypatch: pytest.MonkeyPatch):
    """...and the other direction, which is how a renamed tool is caught:
    every `<tool name="x">` example names something that can actually run,
    and no example is written in a form the parser would not see as a call
    at all (`<tool>x`, `<tool name='x'>`) — a model copies what it is shown."""
    import re
    text = every_block(project, monkeypatch)
    named = set(re.findall(r'<tool name="([a-z_]+)">', text))
    assert named, "no tool examples found at all"
    assert not (named - set(T._DISPATCH)), named - set(T._DISPATCH)
    openings = re.findall(r"<tool\b[^>\n]*>", text)
    nameless = [o for o in openings if not re.fullmatch(r'<tool name="[a-z_]+">', o)]
    assert not nameless, f"tool examples without name=\"…\": {nameless}"


def test_every_tool_example_round_trips_through_the_parser(project: Path, monkeypatch: pytest.MonkeyPatch):
    """What the prompt shows is what the harness parses: every `<tool …>…
    </tool>` example block in the fully-enabled docs comes back from
    `parse_tool_calls` as exactly one call of the same name, and is a
    complete call by `has_complete_tool_call`'s reckoning."""
    import re
    text = every_block(project, monkeypatch)
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


def test_the_assembled_prompt_carries_the_tools_it_documents(project: Path, monkeypatch: pytest.MonkeyPatch):
    enable_skill(project, "readvisory")
    set_toggle("composure_enabled", True)
    open_gates(monkeypatch)
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


def test_the_canon_block_rides_on_the_install_not_the_skill(
        project: Path, monkeypatch: pytest.MonkeyPatch):
    """The FEED pattern (owner decision 12): the MacroCOSM tools are on by
    default, so their docs are in every project where the reader's manifests
    ship; the `macrocosm-oes` skill ships OFF like every other shipped skill,
    and `cosm_guide` hands its body over on demand."""
    set_toggle("composure_enabled", True)
    assert ("macrocosm-oes", False) in [(n, on) for n, on, _t in prompt.list_skills(project / "rness")]
    off_skill = prompt.tool_instructions(project)
    assert "## MacroCOSM" in off_skill
    for name in ("cosm_read", "cosm_lint", "emf_derive", "atem", "cosm_guide", "doc_lookup", "thym_check",
                 "thym_run"):
        assert f'<tool name="{name}">' in off_skill, name
    enable_skill(project, "macrocosm-oes")
    assert prompt.tool_instructions(project) == off_skill
    monkeypatch.setattr(prompt, "_macrocosm_available", lambda: False)
    gone = prompt.tool_instructions(project)
    assert "## MacroCOSM" not in gone and "cosm_read" not in gone and "cosm_guide" not in gone
    assert "doc_lookup" not in gone and "thym_check" not in gone and "thym_run" not in gone
    assert len(off_skill) - len(gone) == len(prompt.CANON_TOOL_INSTRUCTIONS) + 1


def test_the_default_prompt_grows_by_at_most_the_canon_block(project: Path):
    """What a fresh project pays every turn (every shipped skill off, as shipped)
    against HEAD (0.4.2, d865818), measured on the same fixture with HEAD's
    tree exported read-only: the round may add the MacroCOSM block and nothing
    more — in particular never the skill's body."""
    text = prompt.assemble_system_prompt(project)
    for p in {str(project.resolve()), str(project)}:
        text = text.replace(p, "<project>")
    assert "## macrocosm-oes" not in text and "## The six stances" not in text     # the skill's section
    size = len(text)
    assert size <= HEAD_DEFAULT_PROMPT + len(prompt.CANON_TOOL_INSTRUCTIONS) + 1, (
        f"a fresh project's system prompt is {size} chars; HEAD's was {HEAD_DEFAULT_PROMPT}, and this round "
        f"may add only the {len(prompt.CANON_TOOL_INSTRUCTIONS)}-char MacroCOSM block.")


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
    ships, the dictionary block, and the MacroCOSM block every install
    carries (0.4.3), and nothing else."""
    set_toggle("composure_enabled", False)
    disable_skill(project, "readvisory")
    monkeypatch.setattr(prompt, "_cloud_usable", lambda: False)
    monkeypatch.setattr(prompt, "_wiki_installed", lambda: False)
    # 0.5.1: the always-on text is the core plus the sections that were in it
    # until the round carved them out (girraphs, review, the canon store,
    # keep going) and the note that no archive is installed.
    plain = "\n\n".join(b.rstrip() for b in (
        prompt.TOOL_INSTRUCTIONS, prompt.GIRRAPH_TOOL_INSTRUCTIONS, prompt.REVIEW_TOOL_INSTRUCTIONS,
        prompt.WIKI_ABSENT_INSTRUCTIONS, prompt.CANON_STORE_INSTRUCTIONS, prompt.KEEP_GOING_INSTRUCTIONS))
    assert prompt.tool_instructions(project).strip() == (
        plain + "\n\n"
        + prompt.DICTIONARY_TOOL_INSTRUCTIONS.rstrip() + "\n\n"
        + prompt.CANON_TOOL_INSTRUCTIONS).strip()
    no_feed(monkeypatch, tmp_path)
    assert prompt.tool_instructions(project).strip() == (
        plain + "\n\n" + prompt.CANON_TOOL_INSTRUCTIONS).strip()
    monkeypatch.setattr(prompt, "_macrocosm_available", lambda: False)
    assert prompt.tool_instructions(project).strip() == plain.strip()


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


def test_the_fully_enabled_tool_docs_stay_inside_their_budget(project: Path, monkeypatch: pytest.MonkeyPatch):
    size = len(fully_enabled(project, monkeypatch))
    assert size <= FULL_BUDGET, (
        f"core + every gated block is {size} chars, over the {FULL_BUDGET} "
        f"budget. Raising this number is a decision, not a formality: it is "
        f"context window and prefill time on every turn.")


def test_the_canon_block_stays_inside_the_owners_cap():
    size = len(prompt.CANON_TOOL_INSTRUCTIONS)
    assert size <= CANON_BLOCK_MAX, (
        f"the MacroCOSM tool docs are {size} chars, over the owner's "
        f"{CANON_BLOCK_MAX}. The guide is the macrocosm-oes skill; the block "
        f"is only the tags.")


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


# ---------------------------------------------------------------------------
# 3b. The lean profile (0.5.1, docs/ctx-16gb-plan.md §4b–4c)
# ---------------------------------------------------------------------------

def _lean(project: Path, **kw) -> str:
    return prompt.assemble_system_prompt(project, profile="lean", **kw)


def test_the_lean_prompt_stays_inside_its_budget(project: Path):
    text = _lean(project)
    for p in {str(project.resolve()), str(project)}:
        text = text.replace(p, "<project>")
    assert len(text) <= LEAN_BUDGET, (
        f"a fresh project's lean prompt is {len(text)} chars, over the {LEAN_BUDGET} budget "
        f"— an 8,192-token window stops holding it with the reserve (see the fit test).")
    assert len(text) < len(prompt.assemble_system_prompt(project)) // 2


def test_the_lean_prompt_names_every_tool_a_turn_can_call(project: Path, monkeypatch: pytest.MonkeyPatch):
    """Lean summarises; it never hides a tool. Every dispatchable tool is
    named in the lean prompt (the pal one on a pal turn), and every section
    marked *(guide: X)* is a topic `harness_guide` answers."""
    import re
    enable_skill(project, "readvisory")
    enable_skill(project, "girraph-merirmaid")
    set_toggle("composure_enabled", True)
    open_gates(monkeypatch)
    text = _lean(project, pal=True)
    missing = [name for name in sorted(T._DISPATCH) if name not in text]
    assert not missing, f"the lean prompt never names: {', '.join(missing)}"
    guides = prompt.harness_guides()
    marked = set(re.findall(r"\(guide: ([a-z]+)\)", text))
    assert marked and marked <= set(guides), marked - set(guides)
    assert "harness_guide" in text and '<tool name="harness_guide">' in text
    for topic, body in guides.items():
        assert body.strip(), topic


def test_harness_guide_hands_back_the_full_text(project: Path):
    for topic, body in prompt.harness_guides().items():
        call = T.parse_tool_calls(f'<tool name="harness_guide">\n<topic>{topic}</topic>\n</tool>')[0]
        r = T.execute(project, call)
        assert r.ok and r.body == body.rstrip(), topic
    bad = T.execute(project, T.parse_tool_calls('<tool name="harness_guide">\n<topic>x</topic>\n</tool>')[0])
    assert not bad.ok and "composures" in bad.body


def test_the_lean_policies_are_an_index_with_the_hard_rules(project: Path):
    text = _lean(project)
    full = prompt.assemble_system_prompt(project)
    assert "# Policies" in text
    for stem in ("allowlists", "context-management", "profile-maintenance", "requests"):
        assert f"`rness/policies/{stem}.md`" in text, stem
        assert f"## {stem}" in full and f"## {stem}" not in text
    assert "to `/reset`" in text and "`rness/policies/allowlists.md` names" in text
    assert "`rness/knowledge/project-profile.md`" in text
    # a user's own policy is indexed by its first paragraph
    (project / "rness" / "policies" / "house-style.md").write_text(
        "# Policy: House style\n\nLowercase prose in every UI string.\n\nMore.\n", encoding="utf-8")
    assert "**house-style** (`rness/policies/house-style.md`) — Lowercase prose in every UI string." in _lean(project)


def test_the_lean_paradigm_is_cut_at_its_marker(project: Path):
    text = _lean(project)
    full = prompt.assemble_system_prompt(project)
    assert prompt.LEAN_CUT in (project / "rness" / "paradigms" / "text-planning.md").read_text(encoding="utf-8")
    assert "## Planning, in brief" in text and "## Plan creation — flow" in full
    assert "## Plan creation — flow" not in text and "## Scaffold mode" not in text
    assert "read with\n`read_file` the moment it applies" in text
    # a paradigm without the marker rides whole
    (project / "rness" / "paradigms" / "plain.md").write_text("# Plain\n\nAll of it.\n", encoding="utf-8")
    prompt.set_active_paradigm(project / "rness", "plain")
    assert "All of it." in _lean(project)


def test_the_lean_tool_docs_summarise_the_long_sections(project: Path, monkeypatch: pytest.MonkeyPatch):
    set_toggle("composure_enabled", True)
    open_gates(monkeypatch)
    full = prompt.tool_instructions(project)
    lean = prompt.tool_instructions(project, lean=True)
    assert prompt.LEAN_TOOLS_NOTE.strip() in lean and prompt.LEAN_TOOLS_NOTE.strip() not in full
    for long, short in ((prompt.COMPOSURE_TOOL_INSTRUCTIONS, prompt.COMPOSURE_LEAN_INSTRUCTIONS),
                        (prompt.REVIEW_TOOL_INSTRUCTIONS, prompt.REVIEW_LEAN_INSTRUCTIONS),
                        (prompt.WIKI_TOOL_INSTRUCTIONS, prompt.WIKI_LEAN_INSTRUCTIONS),
                        (prompt.CLOUD_TOOL_INSTRUCTIONS, prompt.CLOUD_LEAN_INSTRUCTIONS),
                        (prompt.CANON_STORE_INSTRUCTIONS, prompt.CANON_STORE_LEAN_INSTRUCTIONS),
                        (prompt.KEEP_GOING_INSTRUCTIONS, prompt.KEEP_GOING_LEAN_INSTRUCTIONS)):
        assert long.strip() in full and short.strip() in lean
        assert short.strip() not in full and long.strip() not in lean
        assert len(short) < len(long)
    # the girraph summary rides only with a map in the project or the skill on
    assert prompt.GIRRAPH_TOOL_INSTRUCTIONS.strip() in full
    assert "read_girraph" not in lean and prompt.GIRRAPH_ABSENT_LEAN_INSTRUCTIONS.strip() in lean
    assert prompt.GIRRAPH_LEAN_INSTRUCTIONS.strip() not in lean
    (project / "plans").mkdir()
    (project / "plans" / "map.girraph").write_text("# A map\n", encoding="utf-8")
    with_map = prompt.tool_instructions(project, lean=True)
    assert prompt.GIRRAPH_LEAN_INSTRUCTIONS.strip() in with_map
    assert prompt.GIRRAPH_ABSENT_LEAN_INSTRUCTIONS.strip() not in with_map


def test_the_cloud_and_wiki_blocks_follow_their_gates(project: Path, monkeypatch: pytest.MonkeyPatch):
    """Tier 1 of the diet: dead text in a default install leaves. The cloud
    block rides only through an open cloud gate; the wiki block only with
    an archive, a short note naming the wiki tools otherwise."""
    monkeypatch.setattr(prompt, "_cloud_usable", lambda: False)
    monkeypatch.setattr(prompt, "_wiki_installed", lambda: False)
    shut = prompt.tool_instructions(project)
    assert '<tool name="cloud_pipeline">' not in shut and "## Cloud pipeline" not in shut
    assert prompt.WIKI_ABSENT_INSTRUCTIONS.strip() in shut and '<tool name="wiki_search">' not in shut
    for name in ("wiki_status", "wiki_search", "read_wiki_article", "wikisink"):
        assert name in shut, name                       # named, so never a phantom
    open_gates(monkeypatch)
    opened = prompt.tool_instructions(project)
    assert '<tool name="cloud_pipeline">' in opened and "summarize_each" in opened
    assert '<tool name="wiki_search">' in opened and prompt.WIKI_ABSENT_INSTRUCTIONS.strip() not in opened
    # each block joins as its stripped text plus two newlines
    assert len(opened) - len(shut) == (len(prompt.CLOUD_TOOL_INSTRUCTIONS.rstrip()) + 2
                                       + len(prompt.WIKI_TOOL_INSTRUCTIONS.rstrip())
                                       - len(prompt.WIKI_ABSENT_INSTRUCTIONS.rstrip()))


def test_choose_profile_follows_the_half_window_rule(project: Path):
    full = prompt.assemble_system_prompt(project)
    est = prompt.estimate_tokens(full)
    assert prompt.choose_profile(full, None) == "chat"            # an unknown window: the full prompt
    assert prompt.choose_profile(full, est * 2 + 1) == "chat"
    assert prompt.choose_profile(full, est * 2 - 1) == "lean"
    assert prompt.choose_profile(full, 8192) == "lean" and prompt.choose_profile(full, 65536) == "chat"
    text, profile = prompt.assemble_for_window(project, 8192)
    assert profile == "lean" and text == prompt.assemble_system_prompt(project, profile="lean")
    text, profile = prompt.assemble_for_window(project, 131072)
    assert profile == "chat" and text == full
    assert prompt.lean_wanted(10_000, 16_384) and not prompt.lean_wanted(10_000, 32_768)


def test_lean_keeps_what_the_council_profile_keeps(project: Path):
    """Lean trims the harness, never the person: identity, motivation and the
    project description ride whole, as in every profile."""
    from enough import project_meta
    project_meta.save(project, None, "A novel about lighthouses.")
    (project / "rness" / "AGENT.md").write_text("# Ed\n\nIDENTITY-MARKER\n", encoding="utf-8")
    text = _lean(project)
    for kept in ("chief readvisor", "IDENTITY-MARKER", "A novel about lighthouses.", "# Paradigm", "# Policies",
                 "# Tools", "# Converted documents", "# Context", "*(guide: twins)*"):
        assert kept in text, kept


# ---------------------------------------------------------------------------
# 4. The prompt against the windows we ship (docs/ctx-16gb-plan.md §8.5)
# ---------------------------------------------------------------------------
#
# The guard the 16 GB bug lacked: `HEAD_DEFAULT_PROMPT` pinned the prompt's
# size against HEAD, but nothing tied it to the context windows
# `defaults/models.json` ships — so a 20k-token prompt went out to machines
# whose default window was 16k (or 8k) and the first message answered with
# llama-server's 400.

#: Tokens kept free beside the prompt: a first message and a thinking reply.
#: The same reserve the runtime preflight keeps (`enough.preflight.RESERVE`).
CTX_RESERVE = 2_048
#: chars per token — gemma-4's, the lower (more tokens) of the two shipped
#: tokenizer families (plan §1a: 3.76 gemma, 3.88 qwen).
CHARS_PER_TOKEN = 3.7
#: The fixture's project path is written `<project>`; a real one is longer.
#: 130 chars is the path the plan measured with (§1).
PROJECT_PATH_CHARS = 130
#: Each tier's RAM range in GB, [low, high).
TIERS = {"gte_64gb": (64, 10_000), "gte_32gb": (32, 64),
         "gte_16gb": (16, 32), "lt_16gb": (0, 16)}
#: Pairs whose shipped window cannot hold the full default prompt, each with
#: why it is allowed to stay that way for now. The lean profile (the plan's
#: next round) is what fixes them — and when a pair starts fitting, the test
#: below fails until its entry is deleted, so this list can only shrink.
#: 0.5.1: the lean profile (~5.8k tokens) fits every 8,192 window with the
#: reserve, so five of the six pairs left this list: G40-26, Q36-27 and
#: Q38-04 on 16-31 GB, G40-04 and Q35-09 under 16 GB.
KNOWN_TOO_SMALL = {
    ("g40-12", "lt_16gb"): "12-15 GB: 4,096 cannot hold even the lean prompt with "
                           "the reserve; raising it on a 12 GB machine is an owner "
                           "call (plan §3d)",
}


def _default_prompt_tokens(project: Path, profile: str = "chat") -> int:
    text = prompt.assemble_system_prompt(project, profile=profile)
    for p in {str(project.resolve()), str(project)}:
        text = text.replace(p, "<project>")
    chars = len(text) - len("<project>") * text.count("<project>") \
        + PROJECT_PATH_CHARS * text.count("<project>")
    return int(chars / CHARS_PER_TOKEN + 0.999)


def _feasible_pairs() -> dict[tuple[str, str], int]:
    """(model, tier) -> the tier's shipped window, for every pair whose model
    runs somewhere in the tier (its RAM minimum below the tier's top). §8.5's
    allowlist names pairs like G40-26 on 20-31 GB, so feasibility is judged
    at the lowest machine in the tier the model runs on."""
    import json as _json
    reg = _json.loads((Path(__file__).resolve().parent.parent / "defaults"
                       / "models.json").read_text(encoding="utf-8"))
    out: dict[tuple[str, str], int] = {}
    for cute, entry in reg["models"].items():
        need = int(entry.get("ram_gb_recommended_min") or 0)
        for tier, (_low, high) in TIERS.items():
            if need < high:
                out[(cute, tier)] = int(entry["ctx_defaults"][tier])
    return out


def test_every_shipped_window_holds_the_default_prompt(project: Path):
    """Every model x RAM tier the model can run in ships a context window
    that holds a fresh project's whole system prompt plus the reserve —
    the prompt a turn would send there, which since 0.5.1 is the lean
    profile wherever the full one would take more than half the window
    (`prompt.lean_wanted`) — except the `KNOWN_TOO_SMALL` pairs, each with
    its reason."""
    full = _default_prompt_tokens(project)
    lean = _default_prompt_tokens(project, "lean")
    pairs = _feasible_pairs()
    sent = {p: (lean if prompt.lean_wanted(full, ctx) else full) for p, ctx in pairs.items()}
    too_small = {p: ctx for p, ctx in pairs.items() if sent[p] + CTX_RESERVE > ctx}
    new = sorted(set(too_small) - set(KNOWN_TOO_SMALL))
    assert not new, (
        f"a fresh project's prompt is ~{full:,} tokens (lean: ~{lean:,}; +{CTX_RESERVE:,} "
        f"reserve) and these shipped windows cannot hold the profile they would get: "
        + ", ".join(f"{c} {t} ({pairs[(c, t)]:,})" for c, t in new)
        + ". Raise the window in defaults/models.json (if the machine affords "
          "it), shrink the prompt, or add an entry with its reason.")
    fixed = sorted(set(KNOWN_TOO_SMALL) - set(too_small))
    assert not fixed, (
        f"these KNOWN_TOO_SMALL pairs hold the prompt now — delete their "
        f"entries: {fixed}")


def test_the_known_too_small_pairs_are_real_pairs():
    """An entry for a pair the model cannot even run in would never fail."""
    pairs = _feasible_pairs()
    assert set(KNOWN_TOO_SMALL) <= set(pairs), set(KNOWN_TOO_SMALL) - set(pairs)
    assert all(reason.strip() for reason in KNOWN_TOO_SMALL.values())


def test_the_reserve_is_the_preflights():
    from enough import preflight
    assert CTX_RESERVE == preflight.RESERVE
