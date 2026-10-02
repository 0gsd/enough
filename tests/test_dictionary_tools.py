"""FEED's readvisor tools (0.4.1): `dict_lookup`, `dict_add_entry`,
`dict_update_entry`, and the `lexicographer` skill that documents them.

Runs against test_dictionary's small fixture lexicon (synced through the real
`scripts/sync_dictionary.py`, pointed at by `ENOUGH_DICT_SOURCE`); conftest has
already moved `ENOUGH_DICT_ROOT` and `HOME` into tmp_path.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from enough import broker
from enough import dictionary as D
from enough import dictionary_tools as DT
from enough import prompt
from enough import tools as T
from test_dictionary import SCHEMA, built, lexicon, source  # noqa: F401 — fixtures

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "defaults" / "skills" / "lexicographer" / "SKILL.md"


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    (home / "enough" / "config").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(broker, "CONFIG_PATH", home / "enough" / "config" / "broker.json")
    proj = tmp_path / "project"
    proj.mkdir()
    assert str(Path.home()).startswith(str(tmp_path))
    assert str(D.state_root()).startswith(str(tmp_path))
    return proj


def run(project: Path, text: str) -> T.ToolResult:
    calls = T.parse_tool_calls(text)
    assert len(calls) == 1, text
    return T.execute(project, calls[0])


def test_registered_and_traced():
    for name in DT.TOOL_NAMES:
        assert name in T._DISPATCH
        assert T._TRACE_TOGGLE[name] == "trace_log_enabled"


# ---------------------------------------------------------------------------
# No dictionary: a sentence, never a raise
# ---------------------------------------------------------------------------

def test_no_dictionary_shipped(project: Path):
    # conftest points ENOUGH_DICT_SOURCE at nothing.
    for text in ('<tool name="dict_lookup"><word>apple</word></tool>',
                 '<tool name="dict_add_entry"><word>zork</word><pos>noun</pos></tool>'):
        r = run(project, text)
        assert not r.ok and "no dictionary" in r.body


@pytest.mark.skipif(SCHEMA is None, reason="reflib/dict/schema.sql not synced yet")
def test_dictionary_not_built_yet(project: Path, source: Path):
    r = run(project, '<tool name="dict_lookup"><word>apple</word></tool>')
    assert not r.ok and "still being prepared" in r.body


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------

pytestmark_built = pytest.mark.skipif(SCHEMA is None, reason="reflib/dict/schema.sql not synced yet")


@pytestmark_built
def test_lookup_renders_a_compact_entry(project: Path, built: Path):
    r = run(project, '<tool name="dict_lookup">\n<word>Aardvark</word>\n</tool>')
    assert r.ok
    lines = r.body.splitlines()
    assert lines[0] == "aardvark — feed"
    assert "pronunciation: /aardvark/" in lines
    assert "pos: noun" in lines
    assert "domain: zoology" in lines
    assert "frequency_rank: 2 (rare)" in lines
    assert "hyphenation: aard·vark" in lines
    assert "synonyms: anteater" in lines
    assert "still empty" not in r.body          # only the user's own words
    assert "rhymes" not in r.body and "fr_" not in r.body


@pytestmark_built
def test_lookup_a_form_and_a_miss(project: Path, built: Path):
    r = run(project, '<tool name="dict_lookup"><word>aahed</word></tool>')
    assert r.ok and r.body.startswith("aah — feed") and "(aahed is a form of aah)" in r.body
    r = run(project, '<tool name="dict_lookup"><word>bananna</word></tool>')
    assert r.ok and "is not in feed" in r.body and "banana" in r.body
    r = run(project, '<tool name="dict_lookup"></tool>')
    assert not r.ok and "<word>" in r.body


# ---------------------------------------------------------------------------
# Add and update
# ---------------------------------------------------------------------------

ADD = """<tool name="dict_add_entry">
<word>glimmerwick</word>
<pronunciation>/ˈɡlɪmərˌwɪk/</pronunciation>
<pos>noun</pos>
<definition>The last small flame of a candle burned almost to the bottom.</definition>
<examples>
- We sat up talking until the glimmerwick went out.
- She never blows out a glimmerwick; she waits for it.
</examples>
<related>candle, wick</related>
<frequency_rank>0 (unrecorded)</frequency_rank>
<forms>
glimmerwicks /ˈɡlɪmərˌwɪks/ pl.
</forms>
</tool>"""


@pytestmark_built
def test_add_then_lookup_then_update(project: Path, built: Path, tmp_path: Path):
    r = run(project, ADD)
    assert r.ok, r.body
    assert "added 'glimmerwick'" in r.body
    assert "still empty:" in r.body and "etymology" in r.body and "examples" not in r.body.split(
        "still empty:")[1]
    assert r.side_effects == {DT.SIDE_EFFECT: {"word": "glimmerwick", "action": "add"}}
    e = D.entry("glimmerwick")
    assert e["origin"] == "user"
    assert e["examples"] == ["We sat up talking until the glimmerwick went out.",
                             "She never blows out a glimmerwick; she waits for it."]
    assert e["related"] == ["candle", "wick"]
    assert e["frequency_rank"] == 0
    assert e["forms"] == [{"word": "glimmerwicks", "pronunciation": "/ˈɡlɪmərˌwɪks/",
                           "labels": ["pl."], "synonyms": [], "label_meanings": ["plural"]}]
    # Writes went to the user DB only.
    assert D.user_path().is_file()
    assert str(D.user_path()).startswith(str(tmp_path))

    looked = run(project, '<tool name="dict_lookup"><word>glimmerwick</word></tool>')
    assert looked.body.startswith("glimmerwick — the user's own entry")
    assert "still empty:" in looked.body and "forms: glimmerwicks /ˈɡlɪmərˌwɪks/ (pl.)" in looked.body

    up = run(project, '<tool name="dict_update_entry"><word>glimmerwick</word>'
                      '<etymology>A blend of glimmer and wick.</etymology><related></related></tool>')
    assert up.ok and "updated 'glimmerwick'" in up.body
    assert up.side_effects[DT.SIDE_EFFECT]["action"] == "update"
    e = D.entry("glimmerwick")
    assert e["etymology"] == "A blend of glimmer and wick." and e["related"] is None


@pytestmark_built
def test_add_refuses_a_feed_word_and_update_makes_the_users_version(project: Path, built: Path):
    r = run(project, '<tool name="dict_add_entry"><word>apple</word><pos>noun</pos>'
                     '<pronunciation>/ˈæpəl/</pronunciation><definition>A fruit.</definition></tool>')
    assert not r.ok and "feed already has 'apple'" in r.body
    assert not r.side_effects
    up = run(project, '<tool name="dict_update_entry"><word>apple</word>'
                      '<usage_note>Family usage</usage_note></tool>')
    assert up.ok and "stands in for feed's" in up.body
    looked = run(project, '<tool name="dict_lookup"><word>apple</word></tool>')
    assert looked.body.startswith("apple — the user's own version of a feed word")


@pytestmark_built
def test_write_failures_name_what_is_missing(project: Path, built: Path):
    r = run(project, '<tool name="dict_add_entry"><word>zork</word><pos>noun</pos></tool>')
    assert not r.ok and "needed first: definition, pronunciation" in r.body
    r = run(project, '<tool name="dict_add_entry"><word>zork</word><pos>noun</pos>'
                     '<pronunciation>/zɔrk/</pronunciation><definition>A thing.</definition>'
                     '<colour>red</colour></tool>')
    assert not r.ok and "unknown column 'colour'" in r.body and "columns you can write" in r.body
    r = run(project, '<tool name="dict_add_entry"><word>two words</word></tool>')
    assert not r.ok and "a-z" in r.body
    r = run(project, '<tool name="dict_update_entry"><word>nowhere</word><pos>noun</pos></tool>')
    assert not r.ok and "add it instead" in r.body


def test_parse_form():
    assert DT.parse_form("aahs /ɑz/ pl., 3rd sing.") == {
        "word": "aahs", "pronunciation": "/ɑz/", "labels": ["pl.", "3rd sing."], "synonyms": []}
    assert DT.parse_form("ran") == {"word": "ran", "pronunciation": "", "labels": [], "synonyms": []}
    assert DT.parse_form("runs (3rd sing.)")["labels"] == ["3rd sing."]


# ---------------------------------------------------------------------------
# The skill, and the prompt block it gates
# ---------------------------------------------------------------------------

def test_the_skill_ships_with_the_tool_tags_and_the_prompt_block_fits():
    text = SKILL.read_text(encoding="utf-8")
    for name in DT.TOOL_NAMES:
        assert name in text
    assert len(prompt.DICTIONARY_TOOL_INSTRUCTIONS) <= 750
    # The skill's example entry is a call the harness would run.
    calls = T.parse_tool_calls(text)
    assert [c.name for c in calls] == ["dict_add_entry"]
    assert "```" not in text.split("## An entry, whole", 1)[1]


def test_dict_guide_hands_back_the_shipped_guide(project: Path):
    """The guide reaches a model whose `lexicographer` skill is off (the
    default): the whole skill body, without frontmatter or tooltip."""
    r = run(project, '<tool name="dict_guide">\n</tool>')
    assert r.ok
    assert r.body.startswith("# lexicographer")
    assert "## The columns" in r.body and "**hyphenation**" in r.body
    assert "enough-tooltip-text" not in r.body and "description:" not in r.body
    assert r.body == DT.guide_text()


def test_dict_guide_without_a_shipped_guide(project: Path, monkeypatch):
    from enough import skeleton
    monkeypatch.setattr(skeleton, "_install_defaults_root", lambda: project / "nowhere")
    r = run(project, '<tool name="dict_guide"></tool>')
    assert not r.ok and "no lexicographer guide" in r.body


def test_the_skill_names_every_column_it_teaches():
    text = SKILL.read_text(encoding="utf-8")
    for col in D.REPORTED:
        assert f"**{col}**" in text, col
    for label in DT.FORM_LABELS:
        assert f"`{label}`" in text, label


@pytest.mark.skipif(not (REPO / "reflib" / "dict" / "words").is_dir(),
                    reason="reflib/dict not synced")
def test_the_skill_lists_exactly_feeds_domains_and_parts_of_speech():
    """The skill's vocabularies are FEED's own, read from the shipped text."""
    domains, pos = set(), set()
    for f in sorted((REPO / "reflib" / "dict" / "words").glob("*.jsonl")):
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                if r.get("is_headword") != 1:
                    continue
                if r.get("domain"):
                    domains.add(r["domain"])
                pos.update(p for p in (r.get("pos") or "").split("; ") if p)
    text = " ".join(SKILL.read_text(encoding="utf-8").split())
    dom_para = text.split("**domain** —", 1)[1].split("**first_use**", 1)[0]
    listed = {d.strip(" .") for d in dom_para.split(":", 1)[1].split("When nothing")[0].split(",")}
    assert listed == domains, (listed ^ domains)
    pos_para = text.split("**pos** —", 1)[1].split("**definition**", 1)[0]
    listed_pos = {p.strip(" .") for p in pos_para.split("FEED's list:", 1)[1].split(",")}
    assert listed_pos == pos, (listed_pos ^ pos)
