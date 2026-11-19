"""Metaparadigms (0.8, tracker `paradigms-several-active` P2, P2g, P3, P5) and
the faces hook (`transcognition-paradigm` T2).

A metaparadigm is the one text that rides for two or three paradigms on
together: `rness/metaparadigms/<sorted names joined with +>.md`, a project's
own file or a link to the install's `defaults/metaparadigms/`. It counts only
while the fingerprints in its front matter match its members as the project
has them; a combination with no true text is composed by rule.

The four shipped texts (lane W2-PT) are checked for their fingerprints, their
weight and their hints; a fixture proves the shipped check fails, naming the
stale combinations, when a member changes. A test that needs a set with no
text of its own takes the project's link away, or uses a paradigm of the
project's own.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from enough import prompt, skeleton

SHIPPED = skeleton._install_defaults_root()


def _paradigm(folder: Path, name: str, body: str, tooltip: str = "t") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / f"{name}.md"
    p.write_text(f"---\nname: {name}\ndescription: d\n---\n\n{body}\n\n---\n"
                 f'enough-tooltip-text: "{tooltip}"\n', encoding="utf-8")
    return p


def _meta(folder: Path, paradigms: Path, members: list[str], body: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / f"{prompt.metaparadigm_key(members)}.md"
    p.write_text(prompt.metaparadigm_front_matter(paradigms, members) + "\n" + body + "\n",
                 encoding="utf-8")
    return p


# --------------------------------------------------------------------------
# P3: keeping them true
# --------------------------------------------------------------------------

def test_every_shipped_metaparadigm_is_true_to_its_members():
    """Fails when a shipped paradigm changed and the combinations holding it
    were not looked at again. Passes on none shipped."""
    stale = prompt.stale_metaparadigms(SHIPPED / "metaparadigms", SHIPPED / "paradigms")
    assert not stale, (
        "these metaparadigms are stale (their members changed since they were "
        "written; read each again, then refresh its fingerprints with "
        "prompt.metaparadigm_front_matter): "
        + "; ".join(f"{k} ({', '.join(v)})" for k, v in stale.items()))


def test_every_shipped_metaparadigm_has_a_lean_head_no_heavier_than_text_planning():
    folder = SHIPPED / "metaparadigms"
    home = prompt._parse_paradigm_frontmatter(
        (SHIPPED / "paradigms" / "text-planning.md").read_text(encoding="utf-8"))[1]
    home_head = home.strip().split(prompt.LEAN_CUT, 1)[0].rstrip()
    for p in sorted(folder.glob("*.md")) if folder.is_dir() else []:
        whole = p.read_text(encoding="utf-8")
        assert prompt.LEAN_CUT in whole, f"{p.name} has no lean cut"
        body = prompt._parse_paradigm_frontmatter(whole)[1].strip()
        head = body.split(prompt.LEAN_CUT, 1)[0].rstrip()
        assert len(head) <= len(home_head), (p.name, len(head), len(home_head))
        assert len(whole) <= prompt.FULL_PARADIGM_BUDGET + 200, (p.name, len(whole))


def test_the_four_shipped_texts_carry_their_hints():
    """Pins 5 and 6 (E8): each shipped combination says who does what, and
    above its cut what the scaffolder presumes for that set: with
    workflow-design in it, a higher-order-creativity system; text-planning
    with transcognition alone, a map of a mind, a world and a universe."""
    folder = SHIPPED / "metaparadigms"
    keys = {"text-planning+transcognition", "text-planning+workflow-design",
            "transcognition+workflow-design", "text-planning+transcognition+workflow-design"}
    assert {p.stem for p in folder.glob("*.md")} == keys
    for key in keys:
        body = prompt._parse_paradigm_frontmatter((folder / f"{key}.md").read_text(encoding="utf-8"))[1]
        head = " ".join(body.split(prompt.LEAN_CUT, 1)[0].split())
        assert "## Who does what" in body and "switching" in head, key
        for member in key.split("+"):
            assert f"`rness/paradigms/{member}.md`" in head, (key, member)
        if "workflow-design" in key:
            assert "higher-order-creativity system" in head, key
        else:
            assert "map of a mind, a world and a universe" in head, key
        if "transcognition" in key:
            assert "fabula-driven meaning enumeration foundation design" in head, key
            assert "nllb_optin: true" in head, key
        if key.startswith("text-planning+transcognition"):
            assert "kept as a fabulan when the user asks" in head, key


def test_the_check_names_the_stale_combinations(tmp_path: Path):
    """The fixture the shipped check stands on: a written combination is true
    until a member's body changes; a tooltip or description edit does not
    stale it; the stale one is named, with the member that moved."""
    paradigms, metas = tmp_path / "paradigms", tmp_path / "metaparadigms"
    _paradigm(paradigms, "alpha", "# Alpha\n\nRule one.")
    _paradigm(paradigms, "beta", "# Beta\n\nRule two.")
    _paradigm(paradigms, "gamma", "# Gamma\n\nRule three.")
    _meta(metas, paradigms, ["beta", "alpha"], "# Alpha with beta")
    _meta(metas, paradigms, ["alpha", "beta", "gamma"], "# All three")
    assert prompt.stale_metaparadigms(metas, paradigms) == {}
    assert prompt.stale_metaparadigms(tmp_path / "absent", paradigms) == {}

    _paradigm(paradigms, "alpha", "# Alpha\n\nRule one.", tooltip="new words")   # tooltip only
    text = (paradigms / "alpha.md").read_text(encoding="utf-8")
    (paradigms / "alpha.md").write_text(text.replace("description: d", "description: e")
                                        .replace("Rule one.", "Rule one.   \n\n\n"),
                                        encoding="utf-8")                        # whitespace only
    assert prompt.stale_metaparadigms(metas, paradigms) == {}

    _paradigm(paradigms, "gamma", "# Gamma\n\nRule three, changed.")
    assert prompt.stale_metaparadigms(metas, paradigms) == {"alpha+beta+gamma": ["gamma"]}
    (paradigms / "beta.md").unlink()
    assert prompt.stale_metaparadigms(metas, paradigms) == {
        "alpha+beta": ["beta"], "alpha+beta+gamma": ["beta", "gamma"]}


def test_members_must_be_the_file_s_own():
    paradigms = SHIPPED / "paradigms"
    head = prompt.metaparadigm_front_matter(paradigms, ["text-planning", "transcognition"])
    assert head.startswith("---\nmembers: text-planning transcognition\n")
    assert "fingerprint.text-planning: sha256:" in head
    fp = prompt.paradigm_fingerprint((paradigms / "text-planning.md").read_text(encoding="utf-8"))
    assert len(fp) == len("sha256:") + 16
    # a text whose members are not its stem's is stale throughout
    assert prompt.metaparadigm_stale_members(head, "text-planning+workflow-design", paradigms) == \
        ["text-planning", "transcognition", "workflow-design"]


# --------------------------------------------------------------------------
# P2 / P5: the text for each of the seven states
# --------------------------------------------------------------------------

@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("ENOUGH_UI_CONFIG", str(tmp_path / "ui.json"))
    monkeypatch.setenv("ENOUGH_CANON_ROOT", str(tmp_path / "cacheawl"))
    monkeypatch.setenv("ENOUGH_INFOWORLD_ROOT", str(tmp_path / "no-infoworld"))
    monkeypatch.setenv("ENOUGH_PROJECTS_STATE", str(tmp_path / "state" / "projects.json"))
    monkeypatch.setenv("ENOUGH_READVISORS_ROOT", str(tmp_path / "readvisors-global"))
    proj = tmp_path / "project"
    proj.mkdir()
    skeleton.ensure_skeleton(proj)
    return proj


SEVEN = [
    ["text-planning"], ["transcognition"], ["workflow-design"],
    ["text-planning", "transcognition"], ["text-planning", "workflow-design"],
    ["transcognition", "workflow-design"],
    ["text-planning", "transcognition", "workflow-design"],
]


@pytest.mark.parametrize("names", SEVEN, ids=["+".join(s) for s in SEVEN])
def test_each_of_the_seven_states_gets_one_text(project: Path, names: list[str]):
    rness = project / "rness"
    prompt.set_active_paradigms(rness, names)
    choice = prompt.choose_paradigm_text(rness)
    assert list(choice.names) == names
    shipped = SHIPPED / "metaparadigms" / f"{prompt.metaparadigm_key(names)}.md"
    if len(names) == 1:
        assert choice.kind == "paradigm" and choice.path == f"paradigms/{names[0]}.md"
    elif shipped.is_file():
        assert choice.kind == "metaparadigm" and choice.level == "global"
    else:
        assert choice.kind == "composed"
    for profile in ("chat", "lean"):
        system = prompt.assemble_system_prompt(project, profile=profile)
        heading = (f"# Paradigm: {names[0]}" if len(names) == 1
                   else "# Paradigms: " + " + ".join(names))
        assert system.count(heading + "\n") == 1, (profile, heading)


def test_the_composed_fallback_weighs_about_one_lean_head(project: Path):
    rness = project / "rness"
    names = ["text-planning", "transcognition", "workflow-design"]
    # the triple ships: take its link away, so the set has no text of its own
    (rness / "metaparadigms" / f"{prompt.metaparadigm_key(names)}.md").unlink(missing_ok=True)
    prompt.set_active_paradigms(rness, names)
    choice = prompt.choose_paradigm_text(rness)
    assert choice.kind == "composed" and choice.stale == ()
    lean = prompt.load_paradigm_text(rness, choice, lean=True)
    full = prompt.load_paradigm_text(rness, choice, lean=False)
    assert lean.startswith(prompt.COMPOSED_LEAD)
    for n in names:
        assert f"## From `{n}`" in lean and f"## From `{n}`" in full
        assert f"`rness/paradigms/{n}.md`" in lean
    # lean: held to the measure; full: each member's whole lean head
    assert len(lean) <= prompt.LEAN_HEAD_BUDGET + 300, len(lean)
    for n in names:
        head = prompt._paradigm_body(rness, (rness / "paradigms" / f"{n}.md").read_text(encoding="utf-8"))
        assert head.split(prompt.LEAN_CUT, 1)[0].rstrip() in full
    assert prompt.LEAN_CUT not in full and prompt.LEAN_CUT not in lean


def test_a_member_without_a_cut_gets_an_even_share(tmp_path: Path):
    rness = tmp_path / "rness"
    long_body = "\n\n".join(f"Paragraph {i}. " + "x" * 400 for i in range(80))
    _paradigm(rness / "paradigms", "alpha", "# Alpha\n\n" + long_body)
    _paradigm(rness / "paradigms", "beta", "# Beta\n\nShort.")
    choice = prompt.choose_paradigm_text(rness, ["alpha", "beta"])
    full = prompt.load_paradigm_text(rness, choice)
    alpha = full.split("## From `alpha`", 1)[1].split("## From `beta`", 1)[0]
    assert len(alpha) <= prompt.FULL_PARADIGM_BUDGET // 2 + 300
    assert "The rest of `rness/paradigms/alpha.md`" in alpha
    assert "The rest of `rness/paradigms/beta.md`" not in full     # beta rides whole


def test_a_project_s_own_metaparadigm_rides_while_true(project: Path):
    rness = project / "rness"
    names = ["text-planning", "transcognition"]
    # The pair ships, so the project holds a link to it: a project's own
    # file takes the link's place (writing through the link would write
    # into the install's own text).
    (rness / "metaparadigms" / f"{prompt.metaparadigm_key(names)}.md").unlink(missing_ok=True)
    _meta(rness / "metaparadigms", rness / "paradigms", names,
          "# Both\n\nOWN-PAIR-TEXT\n\n<!-- lean-cut -->\n\nLONG-TAIL")
    prompt.set_active_paradigms(rness, names)
    choice = prompt.choose_paradigm_text(rness)
    assert (choice.kind, choice.level, choice.path) == \
        ("metaparadigm", "project", "metaparadigms/text-planning+transcognition.md")
    lean = prompt.assemble_system_prompt(project, profile="lean")
    full = prompt.assemble_system_prompt(project)
    assert "OWN-PAIR-TEXT" in lean and "LONG-TAIL" not in lean
    assert "`rness/metaparadigms/text-planning+transcognition.md`" in lean   # the pointer
    assert "LONG-TAIL" in full and "members:" not in full
    # the person makes transcognition their own and changes it: the pair is
    # stale for this project, set aside (never rewritten), composed instead
    link = rness / "paradigms" / "transcognition.md"
    body = link.read_text(encoding="utf-8")
    link.unlink()
    link.write_text(body.replace("# Transcognition Paradigm", "# My Transcognition"), encoding="utf-8")
    choice = prompt.choose_paradigm_text(rness)
    assert choice.kind == "composed" and choice.stale == ("transcognition",)
    assert "OWN-PAIR-TEXT" not in prompt.assemble_system_prompt(project)
    assert "OWN-PAIR-TEXT" in (rness / "metaparadigms" / "text-planning+transcognition.md").read_text(
        encoding="utf-8")


# --------------------------------------------------------------------------
# P2g: links at the global level
# --------------------------------------------------------------------------

def _install(tmp_path: Path) -> Path:
    root = tmp_path / "install-defaults"
    _paradigm(root / "paradigms", "alpha", "# Alpha")
    _paradigm(root / "paradigms", "beta", "# Beta")
    _paradigm(root / "paradigms", "gamma", "# Gamma")
    _meta(root / "metaparadigms", root / "paradigms", ["alpha", "beta"], "# AB")
    _meta(root / "metaparadigms", root / "paradigms", ["alpha", "gamma"], "# AG")
    return root


def test_global_combinations_link_while_every_member_is_the_global_link(tmp_path: Path):
    root = _install(tmp_path)
    proj = tmp_path / "proj"
    (proj / "rness").mkdir(parents=True)
    skeleton._populate_paradigm_symlinks(proj, root)
    skeleton._populate_metaparadigm_symlinks(proj, root)
    metas = proj / "rness" / "metaparadigms"
    assert sorted(p.name for p in metas.iterdir()) == ["alpha+beta.md", "alpha+gamma.md"]
    assert all(p.is_symlink() for p in metas.iterdir())
    choice = prompt.choose_paradigm_text(proj / "rness", ["beta", "alpha"])
    assert (choice.kind, choice.level) == ("metaparadigm", "global")

    # the person makes gamma their own: alpha+gamma is never wider than its
    # members, so its link goes; alpha+beta stays
    g = proj / "rness" / "paradigms" / "gamma.md"
    g.unlink()
    g.write_text("---\nname: gamma\n---\n# My gamma\n", encoding="utf-8")
    skeleton._populate_metaparadigm_symlinks(proj, root)
    assert sorted(p.name for p in metas.iterdir()) == ["alpha+beta.md"]

    # a project's own real file is never touched
    own = metas / "alpha+gamma.md"
    own.write_text("---\nmembers: alpha gamma\n---\nMINE\n", encoding="utf-8")
    skeleton._populate_metaparadigm_symlinks(proj, root)
    assert own.read_text(encoding="utf-8").endswith("MINE\n") and not own.is_symlink()

    # the global is removed: its dangling link is pruned
    (root / "metaparadigms" / "alpha+beta.md").unlink()
    skeleton._populate_metaparadigm_symlinks(proj, root)
    assert not (metas / "alpha+beta.md").is_symlink()
    # a member removed from the install: nothing links
    (root / "paradigms" / "beta.md").unlink()
    _meta(root / "metaparadigms", root / "paradigms", ["alpha", "beta"], "# AB again")
    skeleton._populate_paradigm_symlinks(proj, root)
    skeleton._populate_metaparadigm_symlinks(proj, root)
    assert not (metas / "alpha+beta.md").exists()


def test_no_folder_is_made_when_nothing_ships(tmp_path: Path):
    root = tmp_path / "bare-defaults"
    _paradigm(root / "paradigms", "alpha", "# Alpha")
    proj = tmp_path / "proj"
    (proj / "rness").mkdir(parents=True)
    skeleton._populate_paradigm_symlinks(proj, root)
    skeleton._populate_metaparadigm_symlinks(proj, root)
    assert not (proj / "rness" / "metaparadigms").exists()


def test_the_folder_is_hidden_from_the_tree():
    from enough.server import HIDDEN_TREE_PATHS
    assert "rness/metaparadigms" in HIDDEN_TREE_PATHS


# --------------------------------------------------------------------------
# Faces: blocks kept or dropped by the skills that are on
# --------------------------------------------------------------------------

FACED = """# Fixture paradigm

Opening.

<!-- face: translator -->
TRANSLATOR-FACE nllb_optin: true
<!-- /face -->

<!-- face: macrocosm-oes -->
FABULA-FACE
<!-- /face -->

Closing.
"""


def _faces(on: set[str], body: str = FACED) -> str:
    return prompt.apply_faces(body, lambda s: s in on)


def test_a_face_rides_only_with_its_skill_on():
    one = _faces({"translator"})
    assert "TRANSLATOR-FACE" in one and "FABULA-FACE" not in one
    assert "Opening." in one and "Closing." in one and "<!-- face" not in one
    other = _faces({"macrocosm-oes"})
    assert "FABULA-FACE" in other and "TRANSLATOR-FACE" not in other


def test_both_on_rides_both_and_asks_once():
    both = _faces({"translator", "macrocosm-oes"})
    assert "TRANSLATOR-FACE" in both and "FABULA-FACE" in both
    assert "ask the person\nonce" in both or "ask the person once" in both.replace("\n", " ")


def test_neither_on_names_the_two_skills():
    neither = _faces(set())
    assert "TRANSLATOR-FACE" not in neither and "FABULA-FACE" not in neither
    assert "`translator`" in neither and "`macrocosm-oes`" in neither
    assert "active skills" in neither


def test_a_text_may_write_its_own_both_and_neither_lines():
    own = FACED + "\n<!-- face: both -->\nOWN-BOTH\n<!-- /face -->\n" \
                  "<!-- face: none -->\nOWN-NONE\n<!-- /face -->\n"
    assert "OWN-NONE" in _faces(set(), own) and "OWN-BOTH" not in _faces(set(), own)
    assert "active skills" not in _faces(set(), own)
    both = _faces({"translator", "macrocosm-oes"}, own)
    assert "OWN-BOTH" in both and "OWN-NONE" not in both and "ask the person" not in both
    assert "OWN-BOTH" not in _faces({"translator"}, own)


def test_a_text_without_faces_is_unchanged():
    body = "# Plain\n\nNo faces here.\n"
    assert prompt.apply_faces(body, lambda s: True) == body


def test_faces_follow_the_project_s_skills_in_both_profiles(project: Path):
    rness = project / "rness"
    (rness / "paradigms" / "faced.md").write_text(
        "---\nname: faced\n---\n" + FACED + "\n<!-- lean-cut -->\n\nTAIL\n", encoding="utf-8")
    prompt.set_active_paradigm(rness, "faced")
    for skill in ("translator", "macrocosm-oes"):
        prompt.set_skill_enabled(rness, skill, False)
    assert "TRANSLATOR-FACE" not in prompt.assemble_system_prompt(project, profile="lean")
    prompt.set_skill_enabled(rness, "translator", True)
    for profile in ("chat", "lean"):
        system = prompt.assemble_system_prompt(project, profile=profile)
        assert "TRANSLATOR-FACE nllb_optin: true" in system, profile
        assert "FABULA-FACE" not in system, profile


# --- W3-PF: stamp on save, writing over a link, the SKILL.md sentence -------

def _write(project: Path, rel: str, content: str):
    from enough import tools
    return tools.run_write_file(project, tools.ToolCall(name="write_file", path=rel, content=content, command=None, url=None, extra={}, raw="", span=(0, 0)))


def _proj(tmp_path: Path) -> Path:
    proj = tmp_path / "proj"
    _paradigm(proj / "rness" / "paradigms", "aa", "alpha body")
    _paradigm(proj / "rness" / "paradigms", "bb", "beta body")
    return proj


def test_write_file_stamps_a_metaparadigm_on_save(tmp_path):
    proj = _proj(tmp_path)
    r = _write(proj, "rness/metaparadigms/aa+bb.md", "---\nmembers: aa bb\n---\n\nthe text\n")
    assert r.ok, r.body
    saved = (proj / "rness/metaparadigms/aa+bb.md").read_text()
    want = prompt.metaparadigm_front_matter(proj / "rness" / "paradigms", ["aa", "bb"])
    assert saved.startswith(want) and "the text" in saved
    # a stale stamp is refreshed
    (proj / "rness/paradigms/aa.md").write_text("---\nname: aa\n---\n\nchanged\n")
    _write(proj, "rness/metaparadigms/aa+bb.md", saved.replace("sha256:", "sha256:0"))
    again = (proj / "rness/metaparadigms/aa+bb.md").read_text()
    assert prompt.metaparadigm_stale_members(again, "aa+bb", proj / "rness/paradigms") == []


def test_stamp_warns_and_keeps_text_when_a_member_is_missing(tmp_path):
    proj = _proj(tmp_path)
    text = "---\nmembers: aa zz\n---\n\nbody\n"
    r = _write(proj, "rness/metaparadigms/aa+zz.md", text)
    assert r.ok and "warning" in r.body and "zz" in r.body
    assert (proj / "rness/metaparadigms/aa+zz.md").read_text() == text


def test_the_page_save_stamps_too(tmp_path):
    proj = _proj(tmp_path)
    t = proj / "rness/metaparadigms/aa+bb.md"
    t.parent.mkdir(parents=True)
    out, warn = prompt.stamp_metaparadigm_on_save(t, "---\nmembers: aa bb\n---\n\nx\n")
    assert warn is None and "fingerprint.aa: sha256:" in out and "fingerprint.bb: sha256:" in out
    other = proj / "rness/notes.md"
    assert prompt.stamp_metaparadigm_on_save(other, "hi") == ("hi", None)


def test_write_over_a_link_in_the_two_folders_only(tmp_path):
    proj = _proj(tmp_path)
    glob = tmp_path / "glob"
    glob.mkdir()
    (glob / "gg.md").write_text("global\n")
    (proj / "rness" / "metaparadigms").mkdir()
    for rel in ("rness/paradigms/gg.md", "rness/metaparadigms/aa+bb.md"):
        (proj / rel).symlink_to(glob / "gg.md")
        r = _write(proj, rel, "mine\n" if "metap" not in rel else "---\nmembers: aa bb\n---\n\nmine\n")
        assert r.ok and "replaced" in r.body, r.body
        assert not (proj / rel).is_symlink() and "mine" in (proj / rel).read_text()
    assert (glob / "gg.md").read_text() == "global\n"
    # elsewhere the refusal stays
    (proj / "rness" / "skills").mkdir()
    (proj / "rness/skills/s.md").symlink_to(glob / "gg.md")
    r = _write(proj, "rness/skills/s.md", "x")
    assert not r.ok and (proj / "rness/skills/s.md").is_symlink()
    assert (glob / "gg.md").read_text() == "global\n"


def test_macrocosm_skill_says_authored_entailment_runs_in_the_sandbox():
    s = (SHIPPED / "skills" / "macrocosm-oes" / "SKILL.md").read_text()
    assert "Nothing read or entailed is ever run" not in s
    assert "sandbox" in s and "did not author is read, never run" in s


# --- W5-MF: transcognition's faces ride in the combinations that hold it ----

HOLDING_TRANSCOGNITION = [
    ["text-planning", "transcognition"],
    ["transcognition", "workflow-design"],
    ["text-planning", "transcognition", "workflow-design"],
]
_HOLDING_IDS = ["+".join(s) for s in HOLDING_TRANSCOGNITION]

# What each skill state presumes, as the combination says it (pins 5).
FACE_STATES = {
    ("translator",): ("`translator` is on:", "MADLAD-400-3B"),
    ("macrocosm-oes",): ("`macrocosm-oes` is on:", "never run"),
    ("macrocosm-oes", "translator"): ("`translator` is on:", "`macrocosm-oes` is on:",  # both faces,
                                      "Both are on", "ask once"),                      # plus ask once
    (): ("Neither is on", "chat model alone"),
}
FACE_MARKERS = ("`translator` is on:", "`macrocosm-oes` is on:", "Both are on", "Neither is on")


def _skills(rness: Path, on: tuple[str, ...]) -> None:
    for skill in ("translator", "macrocosm-oes"):
        prompt.set_skill_enabled(rness, skill, skill in on)


def _paradigm_section(project: Path, names: list[str], profile: str) -> str:
    """The combination's text as the profile carries it (faces applied, cut
    for lean), checked to ride in the assembled prompt under its heading;
    measured alone so the skills' own texts do not count."""
    rness = project / "rness"
    rel = f"metaparadigms/{prompt.metaparadigm_key(names)}.md"
    text = prompt._load_text_at(rness, rel, lean=profile == "lean")
    system = prompt.assemble_system_prompt(project, profile=profile)
    heading = "# Paradigms: " + " + ".join(names) + "\n"
    assert text and heading in system, (names, profile)
    assert text.strip() in system.split(heading, 1)[1], (names, profile)
    return " ".join(text.split())


@pytest.mark.parametrize("names", HOLDING_TRANSCOGNITION, ids=_HOLDING_IDS)
def test_a_combination_holding_transcognition_presumes_by_skill_state(project: Path, names: list[str]):
    """Each shipped combination with transcognition in it carries its faces:
    the presumption per skill state, its own "ask once" and "neither"
    lines (so enough's generated ones stay out), no face markup left, in
    both profiles."""
    rness = project / "rness"
    prompt.set_active_paradigms(rness, names)
    assert prompt.choose_paradigm_text(rness).kind == "metaparadigm"
    for on, wanted in FACE_STATES.items():
        _skills(rness, on)
        for profile in ("chat", "lean"):
            section = _paradigm_section(project, names, profile)
            for marker in wanted:
                assert marker in section, (names, on, profile, marker)
            for marker in FACE_MARKERS:
                if marker not in wanted:
                    assert marker not in section, (names, on, profile, marker)
            assert "<!-- face" not in section and "<!-- /face" not in section, (names, on, profile)
            assert "each face above is presumed" not in section, (names, on, profile)
            assert "None of the skills this paradigm leans on" not in section, (names, on, profile)


@pytest.mark.parametrize("names", HOLDING_TRANSCOGNITION, ids=_HOLDING_IDS)
def test_a_combination_keeps_nllb_optin_visible_with_translator_on(project: Path, names: list[str]):
    """Pin 5: `nllb_optin` is read by the model from the text, so with
    `translator` on it is in the translation face in the lean and full
    profiles; with it off, the face and the line go."""
    rness = project / "rness"
    prompt.set_active_paradigms(rness, names)
    for on in (("translator",), ("macrocosm-oes", "translator")):
        _skills(rness, on)
        for profile in ("chat", "lean"):
            section = _paradigm_section(project, names, profile)
            assert "nllb_optin: true" in section, (names, on, profile)
            assert "`rness/paradigms/transcognition.md`" in section, (names, on, profile)
    for on in ((), ("macrocosm-oes",)):
        _skills(rness, on)
        for profile in ("chat", "lean"):
            assert "nllb_optin" not in _paradigm_section(project, names, profile), (names, on, profile)


@pytest.mark.parametrize("names", HOLDING_TRANSCOGNITION, ids=_HOLDING_IDS)
def test_a_combination_s_lean_head_fits_in_every_skill_state(project: Path, names: list[str]):
    """With faces applied, the lean head of each combination holding
    transcognition is no larger than text-planning's, in every skill state."""
    rness = project / "rness"
    home = len(prompt.paradigm_lean_head(rness, "text-planning"))
    rel = f"metaparadigms/{prompt.metaparadigm_key(names)}.md"
    for on in FACE_STATES:
        _skills(rness, on)
        head = prompt._load_text_at(rness, rel, lean=True)
        assert head and len(head) <= home, (names, on, len(head), home)
