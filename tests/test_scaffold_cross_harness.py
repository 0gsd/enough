"""The scaffolder's cross-harness half: the scaffold page (assets/scaffold.html),
the exports and hand-offs (scripts/export.py), and the bundle
(scripts/build_scaffolder_skill.py).

Nothing here imports enough: the skill must stand alone, so these tests load
its scripts by path, the way a harness would. Tools a harness may lack
(node, typst, pandoc, python-pptx) are skipped with their name when absent.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "defaults" / "skills" / "scaffolder"
EXAMPLES = SKILL / "references" / "examples"
TEMPLATE = SKILL / "assets" / "scaffold.html"
FOUR = ("more-page.md", "ten-slide-deck.md", "document.md", "ten-slide-deck.state.md")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ss = _load("scaffold_state", SKILL / "scripts" / "scaffold_state.py")
export = _load("scaffolder_export", SKILL / "scripts" / "export.py")
builder = _load("build_scaffolder_skill", REPO / "scripts" / "build_scaffolder_skill.py")


def example(name: str):
    return ss.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def as_state(model):
    """A plectrum opened as version 1 of a scaffold, as the page opens one."""
    m = copy.deepcopy(model)
    m.kind = "scaffold"
    if m.meta.get("version") is None:
        m.meta["version"] = 1
    return m


def written(name: str):
    """An example with every text box written (stand-in words, with the
    characters that must survive: < > & " and a line starting with #),
    locked."""
    m = as_state(example(name))
    for i, b in enumerate(m.boxes()):
        if b["kind"] == "text" and not b["text"]:
            b["text"] = f"Words for {b['name']} <{i}> & \"so\"\n# not a heading\n\nA second paragraph."
    m.meta["locked"] = "2026-11-18T22:00:00Z"
    return m


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------

def test_template_has_one_json_block_and_nothing_from_a_network():
    page = TEMPLATE.read_text(encoding="utf-8")
    assert page.count(export.BLOCK_OPEN) == 1
    assert export.block_of(page).strip() == "null"
    low = page.lower()
    for bad in ("http://", "https://", "<link", "@import", "@font-face", "fonts.googleapis"):
        assert bad not in low, bad
    # the one place a plecholder's field is set (the person's own words, or a fix they accepted)
    assert page.count("x.ta.value = ") == 1
    # saving is guarded: the store only when the page has one, the browser inside try/catch
    assert "window.claude && window.claude.use" in page
    assert "try {\n    if (value === undefined) return localStorage.getItem" in page


@pytest.mark.parametrize("name", FOUR)
def test_the_page_fills_from_each_example_and_its_json_round_trips(name):
    model = example(name)
    page = export.fill(model)
    block = export.block_of(page)
    assert "<" not in block                      # nothing in the block can close it early
    back = ss.from_json(block)
    assert ss.to_dict(back) == ss.to_dict(model)
    assert page.replace(block, "null") == TEMPLATE.read_text(encoding="utf-8")


def _writer_js() -> str:
    page = TEMPLATE.read_text(encoding="utf-8")
    a, b = page.index("/* ---- writer:start ----"), page.index("/* ---- writer:end ---- */")
    return page[a:b]


def _node_dump(models: list) -> list[str]:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed: the page's markdown writer is not run here")
    script = _writer_js() + "\nconst fs = require('fs');\n" \
        "const models = JSON.parse(fs.readFileSync(0, 'utf8'));\n" \
        "process.stdout.write(JSON.stringify(models.map(dumpState)));\n"
    data = json.dumps([ss.to_dict(m) for m in models])
    r = subprocess.run([node, "-e", script], input=data, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _tricky_state():
    m = written("ten-slide-deck.state.md")
    box = m.boxes()[3]
    box["text"] = "# a\n\\# b\n\\\\# c\n#### d\n#tag\n\n\n  indented\nlast"
    m.boxes()[4]["text"] = ""
    m.findings.append({"id": "f2", "box": box["id"], "kind": "grammar", "quote": "a\nb\\c", "prefix": None,
                       "suffix": "x", "fix": "", "why": "two lines", "status": "cannot be checked",
                       "version": 1, "extra": {"later-key": "kept"}})
    m.meta["extra"] = {"own-key": "its value"}
    return m


def test_the_pages_copy_out_writes_what_the_parser_writes():
    """'Copy everything out' (the page's JS writer) gives the same bytes as
    scaffold_state.dumps, for the four examples opened as states and for a
    state with every escape in it; and the parser reads them back."""
    models = [as_state(example(n)) for n in FOUR] + [_tricky_state()]
    for model, md in zip(models, _node_dump(models)):
        assert md == ss.dumps(model, "scaffold")
        assert ss.to_dict(ss.loads(md)) == ss.to_dict(model)


# ---------------------------------------------------------------------------
# Export and hand-off
# ---------------------------------------------------------------------------

def _state_file(tmp_path: Path, name: str) -> Path:
    m = written(name)
    p = tmp_path / (name.replace(".md", "") + ".scaffold.md")
    p.write_text(ss.dumps(m), encoding="utf-8")
    return p


def run_export(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-I", str(SKILL / "scripts" / "export.py"), *args],
                          capture_output=True, text=True, timeout=120)


@pytest.mark.parametrize("name", ("more-page.md", "ten-slide-deck.md", "document.md"))
def test_html_always_and_never_over_a_file(tmp_path, name):
    src = _state_file(tmp_path, name)
    r1 = run_export("html", str(src))
    assert r1.returncode == 0, r1.stderr
    first = Path(r1.stdout.strip())
    before = first.read_bytes()
    r2 = run_export("html", str(src))
    second = Path(r2.stdout.strip())
    assert second != first and second.name.endswith("-2.html") and first.read_bytes() == before
    text = first.read_text(encoding="utf-8")
    assert "&amp; &quot;so&quot;" in text and "# not a heading" in text
    assert "<script" not in text and "http" not in text.split("</style>")[1]
    m = ss.loads(src.read_text(encoding="utf-8"))
    notes = [b for b in m.boxes() if b["as"] == "notes"]
    assert notes and all(html_escape(b["text"].splitlines()[0]) not in text for b in notes)


def html_escape(s: str) -> str:
    import html
    return html.escape(s)


def test_markdown_for_a_document_and_refusals(tmp_path):
    src = _state_file(tmp_path, "document.md")
    r = run_export("md", str(src))
    assert r.returncode == 0, r.stderr
    md = Path(r.stdout.strip()).read_text(encoding="utf-8")
    assert md.startswith("# What we cook on Sundays\n")
    assert md.count("\n## ") == 26                 # 1 + 24 recipes + 1; the notes frame left out
    assert "Notes to the readvisor" not in md
    assert "Photo of the dish" not in md           # an empty graphic box is left out, and named on stderr
    assert "Photo of the dish (24 boxes)" in r.stderr
    page = _state_file(tmp_path, "more-page.md")
    r = run_export("md", str(page))
    assert r.returncode == 1 and "a page leaves as html and pdf" in r.stderr
    r = run_export("html", str(EXAMPLES / "more-page.md"))
    assert r.returncode == 1 and "this is a plectrum" in r.stderr


def test_pdf_through_typst_or_says_print(tmp_path):
    src = _state_file(tmp_path, "ten-slide-deck.md")
    tool = export.find_typst()
    if not tool:
        r = run_export("pdf", str(src))
        assert r.returncode == 3 and "print it to PDF" in r.stdout
        pytest.skip("typst is not installed (no command, no wheel): only the 'print the HTML' answer was tried")
    for name in ("more-page.md", "ten-slide-deck.md", "document.md"):
        m = written(name)
        out = tmp_path / f"{name}.pdf"
        export.to_pdf(m, tmp_path, out, tool)
        assert out.read_bytes()[:5] == b"%PDF-"


def _slides(pptx: Path) -> int:
    with zipfile.ZipFile(pptx) as z:
        return len([n for n in z.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")])


def test_pptx_through_pandoc(tmp_path):
    exe = export.find_pandoc()
    if not exe:
        pytest.skip("pandoc is not installed")
    m = written("ten-slide-deck.md")
    out = tmp_path / "deck.pptx"
    export.pptx_by_pandoc(m, tmp_path, out, exe)
    assert _slides(out) == len(export.on_thing(m)) == 10


def test_pptx_through_python_pptx(tmp_path):
    if not export.find_pptx():
        pytest.skip("python-pptx is not installed")
    m = written("ten-slide-deck.md")
    out = tmp_path / "deck.pptx"
    export.pptx_by_python(m, tmp_path, out)
    assert _slides(out) == 10
    with zipfile.ZipFile(out) as z:
        notes = [n for n in z.namelist() if n.startswith("ppt/notesSlides/")]
    assert notes                                   # the speaker boxes went to the notes


def test_a_deck_without_pptx_tools_says_so(tmp_path, monkeypatch):
    monkeypatch.setattr(export, "find_pandoc", lambda: None)
    monkeypatch.setattr(export, "find_pptx", lambda: False)
    src = _state_file(tmp_path, "ten-slide-deck.md")
    args = export.parser().parse_args(["pptx", str(src)])
    assert export.run(args) == 3
    assert not list(tmp_path.glob("*.pptx"))


def test_hand_offs(tmp_path, capsys):
    deck = _state_file(tmp_path, "ten-slide-deck.state.md")
    m = ss.loads(deck.read_text(encoding="utf-8"))
    mm = export.to_mermaid(m)
    assert mm.startswith("flowchart TB\n") and "f_cover --> f_the_ask" in mm
    assert "not_in_the_deck" not in mm                                      # notes are not part of it
    assert "#lt;" in mm and "<0>" not in mm
    brief, placed, unplaced = export.to_brief(m)
    assert brief.startswith("# A garden on Mill Lane\n") and "## Who it is for" in brief
    assert all(b["plec"] not in brief for b in m.boxes() if b["plec"])     # the person's words only
    assert unplaced and not placed
    prompt = export.to_prompt(m, "Some Engine")
    assert prompt.startswith("# For Some Engine: A garden on Mill Lane")
    r = run_export("prompt", str(deck))
    assert r.returncode == 2 and "--engine" in r.stderr                    # never picks the engine
    r = run_export("next", str(deck))
    assert r.returncode == 0 and "nothing is chosen for you" in r.stdout
    for cmd in (["mermaid", str(deck)], ["brief", str(deck)], ["brief", "--for", "fabulan", str(deck)],
                ["prompt", "--engine", "Some Engine", str(deck)], ["fill", str(deck)]):
        r = run_export(*cmd)
        assert r.returncode == 0, (cmd, r.stderr)
        assert Path(r.stdout.strip()).is_file()


def test_brief_places_frames_named_as_the_authoring_bank_names_them():
    m = as_state(example("more-page.md"))
    m.frames[0]["name"] = "What it is for"
    m.frames[1]["name"] = "Requirements"
    for b in m.boxes():
        b["text"] = "said by the person"
    _brief, placed, unplaced = export.to_brief(m)
    assert placed == ["What it is for", "Requirements"]
    assert "Opening" not in unplaced and "Four subjects" in unplaced


# ---------------------------------------------------------------------------
# Standing alone, and the bundle
# ---------------------------------------------------------------------------

def test_nothing_under_the_skill_imports_enough():
    for py in SKILL.rglob("*.py"):
        for line in py.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            assert not (s.startswith("import enough") or s.startswith("from enough")), f"{py}: {s}"


def test_every_script_answers_help_alone(tmp_path):
    copy_of = tmp_path / "scaffolder"
    shutil.copytree(SKILL, copy_of, ignore=shutil.ignore_patterns("__pycache__"))
    for script in sorted((copy_of / "scripts").glob("*.py")):
        r = subprocess.run([sys.executable, "-I", str(script), "--help"], cwd=tmp_path,
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, (script.name, r.stderr)


def _committed() -> bool:
    if not shutil.which("git"):
        return False
    r = subprocess.run(["git", "-C", str(REPO), "cat-file", "-e", "HEAD:defaults/skills/scaffolder/assets/scaffold.html"],
                       capture_output=True)
    return r.returncode == 0


def test_the_bundle_is_the_same_bytes_twice_and_stands_alone(tmp_path):
    if not _committed():
        pytest.skip("the skill's page is not in HEAD (or git is absent): the bundle builds from a commit")
    a = builder.build(tmp_path / "a")
    b = builder.build(tmp_path / "b")
    assert a[2] == b[2]
    assert a[0].read_bytes() == a[1].read_bytes() == b[0].read_bytes()
    with zipfile.ZipFile(a[0]) as z:
        names = z.namelist()
        assert names[0] == "scaffolder/SKILL.md"
        assert "scaffolder/assets/scaffold.html" in names and "scaffolder/scripts/export.py" in names
        assert {i.date_time for i in z.infolist()} == {(1980, 1, 1, 0, 0, 0)}
    assert builder.check(a[0]) == []
    assert builder.main(["--check"]) == 0


def test_the_bundle_refuses_private_names(tmp_path):
    stage = tmp_path / "scaffolder"
    (stage / "references").mkdir(parents=True)
    (stage / "SKILL.md").write_text("fine\n")
    (stage / "references" / "x.md").write_text("see /Users/someone/notes\n")
    with pytest.raises(builder.BuildError):
        builder.refuse_private(stage, ["SKILL.md", "references/x.md"])
    (stage / "references" / "x.md").write_text("fine\n")
    builder.refuse_private(stage, ["SKILL.md", "references/x.md"])


def test_the_page_shows_a_box_with_an_empty_plec_as_a_plec_to_write():
    """A state may hold a box with no plec (a plectrum may not); the page takes it and says what is missing."""
    page = TEMPLATE.read_text(encoding="utf-8")
    assert '"[" + (b.plec || "plec to write") + "]"' in page
    assert "no plec yet" not in page
