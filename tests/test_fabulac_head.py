"""The head fabulac and its parts (0.8: pins section 4, the head; MacroCOSM OES 18.4.1 `head` and `parts`, 18.4.7 "A
head fabulac and its parts", 18.4.8 `parts-resolve` and `interfaces-agree`; enough-fabulac step 6 and 7, comprise-fabulac
steps 2, 8 and 9), and which parts moved.

Fixtures, tests/fixtures/fabula/head/: `counter`, a head over two small parts (`counter-core` offers `count_lines`,
`counter-cli` calls it; each read from its folder beside it, with its tree digest); `thym/`, a head over Thym's seven
parts as the parts map declares them (docs/v080-parts-enough.md: values, compiler, runtime, command line, base, prose
and code moves) and six interfaces between them, the parts declared by name only (no Thym fabulac exists yet).
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from enough import fabula
from enough import fabulac_head as H
from enough import macrocosm as mc
from tests.test_fabulac_entail import entail, project  # noqa: F401

FIX = Path(__file__).resolve().parent / "fixtures" / "fabula" / "head"
THYM = ["thym-values", "thym-compiler", "thym-runtime", "thym-cli", "thym-base-moves", "thym-prose-moves",
        "thym-code-moves"]


@pytest.fixture
def counter(tmp_path: Path) -> Path:
    dst = tmp_path / "counter"
    shutil.copytree(FIX, dst, ignore=shutil.ignore_patterns("thym"))
    return dst


def _lint(p: Path) -> tuple[list[str], list[str]]:
    rep = fabula.lint(p)
    own = [x for x in rep.problems() if x.check in H.CHECKS]
    return ([f"{x.check}: {x.message}" for x in own if x.severity == "error"],
            [f"{x.check}: {x.message}" for x in own if x.severity == "note"])


def _set(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, old
    path.write_text(text.replace(old, new), encoding="utf-8")


# ---------------------------------------------------------------------------
# The checks hold
# ---------------------------------------------------------------------------

def test_a_head_and_its_parts_hold_both_checks():
    for name in ("counter", "counter-core", "counter-cli"):
        rep = fabula.lint(FIX / f"{name}.fabulac.cosm")
        assert rep.errors == [], (name, [str(p) for p in rep.errors])
        assert set(H.CHECKS) <= set(rep.checks)
    doc = mc.yaml_load((FIX / "counter.fabulac.cosm").read_text())
    assert [p["uri"] for p in doc["parts"]] == ["oes:fabula/counter-core", "oes:fabula/counter-cli"]
    assert list(doc).index("parts") == list(doc).index("atem") - 1
    assert {c["told-in"] for c in doc["nodes"] if c["type"] == "component"} == {p["uri"] for p in doc["parts"]}
    part = mc.yaml_load((FIX / "counter-cli.fabulac.cosm").read_text())
    assert part["head"] == "oes:fabula/counter"
    assert part["nodes"][-1]["stated-in"] == "oes:fabula/counter/C/interface/count-lines"


def test_thyms_seven_parts_under_one_head_hold_both_checks():
    head = FIX / "thym" / "thym.fabulac.cosm"
    doc = mc.yaml_load(head.read_text())
    assert [p["uri"] for p in doc["parts"]] == [f"oes:fabula/{p}" for p in THYM]
    stated = sorted(n["id"] for n in doc["nodes"] if n["type"] == "interface")
    assert stated == ["C:interface/canonical", "C:interface/check", "C:interface/command-thym",
                      "C:interface/implements", "C:interface/move-error", "C:interface/value"]
    for p in [head] + [FIX / "thym" / f"{x}.fabulac.cosm" for x in THYM]:
        errors, notes = _lint(p)
        assert errors == [] and notes == [], (p.name, errors, notes)
        assert fabula.lint(p).errors == []
    # every interface between parts is stated once, in the head, and cited from the parts that keep or call it
    cited = {}
    for x in THYM:
        for n in mc.yaml_load((FIX / "thym" / f"{x}.fabulac.cosm").read_text())["nodes"]:
            if n["type"] == "interface":
                cited.setdefault(n["stated-in"].rsplit("/", 1)[-1], []).append(x)
    assert cited["move-error"] == ["thym-base-moves", "thym-prose-moves", "thym-code-moves"]
    assert set(cited) == {s.split("/", 1)[1] for s in stated}
    # declared by name only: no part has been read, so none can be said to have moved
    moved = H.parts_moved(head)
    assert moved["moved"] == [] and moved["sources"]["unread"] == sorted(f"oes:fabula/{p}" for p in THYM)
    assert moved["fabulacs"]["in-step"] == sorted(f"oes:fabula/{p}" for p in THYM)


# ---------------------------------------------------------------------------
# The checks fail
# ---------------------------------------------------------------------------

def test_parts_resolve_fails_on_a_part_that_is_not_there_or_names_another_head(counter: Path):
    head = counter / "counter.fabulac.cosm"
    _set(counter / "counter-cli.fabulac.cosm", "head: oes:fabula/counter", "head: oes:fabula/elsewhere")
    errors, _ = _lint(head)
    assert any("counter-cli.fabulac.cosm names oes:fabula/elsewhere as its head" in e for e in errors), errors
    errors, _ = _lint(counter / "counter-cli.fabulac.cosm")
    assert any("its head is not known: no fabulac the reader knows is oes:fabula/elsewhere" in e for e in errors)
    (counter / "counter-core.fabulac.cosm").unlink()
    errors, _ = _lint(head)
    assert any("counter-core.fabulac.cosm is not a fabulac the reader knows" in e for e in errors), errors


def test_parts_resolve_fails_on_a_component_told_in_nothing_and_a_part_told_in_none(counter: Path):
    head = counter / "counter.fabulac.cosm"
    _set(head, "told-in: oes:fabula/counter-cli", "told-in: oes:fabula/counter-gui")
    errors, _ = _lint(head)
    assert any("told-in 'oes:fabula/counter-gui' is not one of the head's parts" in e for e in errors), errors
    assert any("oes:fabula/counter-cli is told in 0 C:components" in e for e in errors), errors


def test_parts_resolve_fails_on_a_stated_in_that_names_nothing(counter: Path):
    part = counter / "counter-cli.fabulac.cosm"
    _set(part, "stated-in: oes:fabula/counter/C/interface/count-lines",
         "stated-in: oes:fabula/counter/C/interface/count-words")
    errors, _ = _lint(part)
    assert errors == ["parts-resolve: stated-in: oes:fabula/counter/C/interface/count-words: oes:fabula/counter holds "
                      "no C:interface/count-words"]
    _set(part, "stated-in: oes:fabula/counter/C/interface/count-words",
         "stated-in: oes:fabula/counter-core/C/interface/count-lines")
    errors, _ = _lint(part)
    assert errors == ["parts-resolve: stated-in names oes:fabula/counter-core, not its head oes:fabula/counter"]


def test_interfaces_agree_fails_when_a_part_says_another_signature(counter: Path):
    part = counter / "counter-core.fabulac.cosm"
    _set(part, 'signature: "def count_lines(text: str) -> int"', 'signature: "def count_lines(text: bytes) -> int"')
    errors, _ = _lint(part)
    assert errors == ["interfaces-agree: C:interface/count-lines does not agree with "
                      "oes:fabula/counter/C/interface/count-lines in its signature"]
    # and a part that moved since the head checked it is a note on the head, not an error
    errors, notes = _lint(counter / "counter.fabulac.cosm")
    assert errors == [] and len(notes) == 1 and "counter-core.fabulac.cosm moved since the head" in notes[0]
    H.stamp_parts(counter / "counter.fabulac.cosm")
    assert _lint(counter / "counter.fabulac.cosm") == ([], [])


def test_one_interface_between_two_programs_is_stated_once_and_cited_by_both_heads(counter: Path):
    """comprise-fabulac's rule: the program that offers it states it; the other program's head cites it."""
    other = counter / "report"
    other.mkdir()
    part = other / "report-core.fabulac.cosm"
    shutil.copyfile(counter / "counter-cli.fabulac.cosm", part)
    _set(part, "id: fabula/counter-cli", "id: fabula/report-core")
    _set(part, "head: oes:fabula/counter", "head: oes:fabula/report")
    _set(part, "summary: The command line calls count_lines", "summary: The report calls count_lines")
    text = part.read_text()
    H.make_head(other / "report.fabulac.cosm", [part], licence="MIT", at="2026-11-18")
    head = other / "report.fabulac.cosm"
    iface = {"id": "C:interface/count-lines", "type": "interface", "name": "count_lines",
             "summary": "counter offers it; report calls it.", "surface": "function",
             "signature": "def count_lines(text: str) -> int",
             "takes": [{"name": "text", "type": "str", "required": True}],
             "stated-in": "oes:fabula/counter/C/interface/count-lines", "stance": "axiom",
             "provenance": {"mode": "manual", "sources": ["the test"], "confidence": 1}}
    from enough import dialectic as dl
    twin = dl.open_twin(head)
    twin.ledger.add(iface)
    twin.save()
    # the part cites its own head; its head cites the other program's head
    _set(part, "stated-in: oes:fabula/counter/C/interface/count-lines",
         "stated-in: oes:fabula/report/C/interface/count-lines")
    assert text != part.read_text()
    H.stamp_parts(head)
    for p in (head, part):
        errors, _ = _lint(p)
        assert errors == [], (p.name, errors)
    _set(counter / "counter.fabulac.cosm", 'signature: "def count_lines(text: str) -> int"',
         'signature: "def count_lines(text: str, *, blank: bool = True) -> int"')
    errors, _ = _lint(head)
    assert errors == ["interfaces-agree: C:interface/count-lines does not agree with "
                      "oes:fabula/counter/C/interface/count-lines in its signature"]


# ---------------------------------------------------------------------------
# Making a head, and which parts moved
# ---------------------------------------------------------------------------

def test_a_head_is_made_from_a_set_of_part_fabulacs(tmp_path: Path):
    for name in ("counter-core", "counter-cli"):
        shutil.copytree(FIX / name, tmp_path / name)
        text = (FIX / f"{name}.fabulac.cosm").read_text().replace("head: oes:fabula/counter\n", "")
        text = text.replace("    stated-in: oes:fabula/counter/C/interface/count-lines\n", "")
        (tmp_path / f"{name}.fabulac.cosm").write_text(text)
    parts = [tmp_path / "counter-core.fabulac.cosm", tmp_path / "counter-cli.fabulac.cosm"]
    out = H.make_head(tmp_path / "tool.fabulac.cosm", parts, name="tool", licence="MIT", by="R:maker/ada",
                      at="2026-11-18", does={"counter-core": "The counting."})
    assert out["uri"] == "oes:fabula/tool"
    doc = mc.yaml_load((tmp_path / "tool.fabulac.cosm").read_text())
    assert doc["parts"] == [{"uri": "oes:fabula/counter-core", "path": "counter-core.fabulac.cosm",
                             "sha256": H._sha(parts[0])},
                            {"uri": "oes:fabula/counter-cli", "path": "counter-cli.fabulac.cosm",
                             "sha256": H._sha(parts[1])}]
    comps = [n for n in doc["nodes"] if n["type"] == "component"]
    assert [c["told-in"] for c in comps] == ["oes:fabula/counter-core", "oes:fabula/counter-cli"]
    assert comps[0]["summary"] == "The counting."
    for p in parts:
        assert mc.yaml_load(p.read_text())["head"] == "oes:fabula/tool"
        assert list(mc.yaml_load(p.read_text())).index("head") == list(mc.yaml_load(p.read_text())).index("atem") - 1
    for p in [tmp_path / "tool.fabulac.cosm"] + parts:
        assert fabula.lint(p).errors == [], (p.name, [str(x) for x in fabula.lint(p).errors])
    with pytest.raises(FileExistsError):
        H.make_head(tmp_path / "tool.fabulac.cosm", parts)
    with pytest.raises(ValueError, match="two parts"):
        H.make_head(tmp_path / "again.fabulac.cosm", parts + parts)


def test_which_moved_sorts_names_by_their_digests():
    got = H.which_moved({"a": "1", "b": "2", "c": "3", "d": None}, {"a": "1", "b": "9", "d": "4", "e": "5"})
    assert got == {"in-step": ["a"], "moved": ["b"], "gone": ["c"], "new": ["e"], "unread": ["d"]}


def test_which_parts_moved_reads_each_parts_folder_against_its_source_tree(counter: Path):
    head = counter / "counter.fabulac.cosm"
    got = H.parts_moved(head)
    assert got["moved"] == [] and [r["source"] for r in got["parts"]] == ["in-step", "in-step"]
    (counter / "counter-core" / "counter_core.py").write_text("def count_lines(text):\n    return 0\n")
    (counter / "counter-cli" / "extra.py").write_text("X = 1\n")
    got = H.parts_moved(head)
    assert got["moved"] == ["oes:fabula/counter-core", "oes:fabula/counter-cli"]
    assert got["sources"]["moved"] == ["oes:fabula/counter-cli", "oes:fabula/counter-core"]
    assert got["fabulacs"]["in-step"] == ["oes:fabula/counter-cli", "oes:fabula/counter-core"]
    shutil.rmtree(counter / "counter-cli")
    got = H.parts_moved(head, folders={"oes:fabula/counter-core": FIX / "counter-core"})
    assert got["sources"] == {"in-step": ["oes:fabula/counter-core"], "moved": [], "gone": ["oes:fabula/counter-cli"],
                              "new": [], "unread": []}


def test_an_authored_part_moves_when_its_entailment_has_files_to_tell(project: Path):
    entail(project, "words")
    fab = project / "words.fabulac.cosm"
    H.make_head(project / "suite.fabulac.cosm", [fab], licence="MIT", at="2026-11-18")
    assert fabula.lint(project / "suite.fabulac.cosm").errors == []
    got = H.parts_moved(project / "suite.fabulac.cosm")
    assert got["moved"] == [] and got["parts"][0]["files"] == []
    _set(fab, "words: PATH: no such file` on the error", "words: PATH: not found` on the error")
    got = H.parts_moved(project / "suite.fabulac.cosm")
    assert got["moved"] == ["oes:fabula/words"] and got["parts"][0]["files"] == ["words/__main__.py"]
    assert got["fabulacs"]["moved"] == ["oes:fabula/words"]
