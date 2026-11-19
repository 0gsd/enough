"""Keeping an authored fabulac and its entailment in step (0.8, fabulac-first F5: pins section 4; MacroCOSM OES 18.4.1
`entailed` and "Fresh and stale, for an authored fabulac"; Thym 20.11 "Keeping in step"): the fingerprint the
entailment records (per file its sha256 and its brief digest), what moved when the fabulac changes, an entailment done
again that tells only what moved and leaves the rest byte for byte, and a hand edit named file by file and resolved
three ways (written over, kept as a recorded decision, taken back as questions).

The model is the scripted one of tests/test_fabulac_entail.py; the fixture is its `words` tool.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from enough import dialectic as dl
from enough import fabula
from enough import fabulac_entail as E
from enough import macrocosm as mc
from enough.thym.coprocessor import candidate
from enough.thym.moves import authored_code as AC
from tests.test_fabulac_entail import NOW, SOURCES, WORDS_INIT, WORDS_MAIN, Model, _t, entail, project, runtime  # noqa: F401

MISSING_OLD = "words: PATH: no such file` on the error"
MISSING_NEW = "words: PATH: not found` on the error"
WORDS_MAIN_2 = WORDS_MAIN.replace("no such file", "not found")


def _bytes(folder: Path) -> dict[str, bytes]:
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted(folder.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}


def _doc(fab: Path) -> dict:
    return mc.yaml_load(fab.read_text(encoding="utf-8"))


def _edit_fabulac(fab: Path, old: str, new: str) -> None:
    text = fab.read_text(encoding="utf-8")
    assert old in text
    fab.write_text(text.replace(old, new), encoding="utf-8")


# ---------------------------------------------------------------------------
# The fingerprint, and what moved
# ---------------------------------------------------------------------------

def test_the_fingerprint_is_each_files_sha256_and_brief_and_briefs_agree_with_it(project: Path):
    entail(project, "words")
    fab = project / "words.fabulac.cosm"
    doc = _doc(fab)
    rec = {f["path"]: f for f in doc["entailed"]["files"]}
    cat, items = {k: v for k, v in doc.items() if k != "nodes"}, doc["nodes"]
    now = AC.briefs(cat, items)
    assert set(now) == set(rec) - {"ENTAILED.md"}
    for p, b in now.items():
        assert rec[p]["brief"] == b["brief"] and rec[p]["from"] == b["from"], p
        assert rec[p]["sha256"] == E._sha(project / "words" / p)
    st = E.step_state(fab)
    assert st["in-step"] == sorted(rec, key=lambda s: s.encode()) and st["tell"] == [] and st["edited"] == []


def test_a_change_in_the_fabulac_moves_only_the_files_told_from_it(project: Path):
    entail(project, "words")
    fab = project / "words.fabulac.cosm"
    _edit_fabulac(fab, MISSING_OLD, MISSING_NEW)            # C:behaviour/missing-file, of the command line only
    st = E.step_state(fab)
    assert st["moved"] == ["words/__main__.py"] and st["tell"] == ["words/__main__.py"]
    assert "words/__init__.py" in st["in-step"] and "tests/test_cases.py" in st["in-step"]
    # a case's expect is read by the rules that write the tests: those move too, and nothing a model wrote
    _edit_fabulac(fab, "    - exit: 0\n      output: '3\n", "    - exit: 0\n      output: '03\n")
    st = E.step_state(fab)
    assert "tests/test_cases.py" in st["moved"] and "words/__init__.py" in st["in-step"]


def test_entailing_again_tells_only_what_moved_and_leaves_the_rest_byte_for_byte(project: Path):
    entail(project, "words")
    folder, fab = project / "words", project / "words.fabulac.cosm"
    before = _bytes(folder)
    _edit_fabulac(fab, MISSING_OLD, MISSING_NEW)
    cp = Model("words", {**SOURCES, "words/__main__.py": WORDS_MAIN_2})
    out = entail(project, "words", cp)
    assert [k for s, k in cp.sent if s in ("code", "test")] == ["words/__main__.py"]   # one file asked, no other
    assert out["told"] == ["ENTAILED.md", "words/__main__.py"]
    after = _bytes(folder)
    assert after["words/__main__.py"] == WORDS_MAIN_2.encode()
    assert {p for p in after if after[p] != before.get(p)} == {"ENTAILED.md", "words/__main__.py"}
    st = E.step_state(fab)
    assert st["tell"] == [] and st["edited"] == [] and st["moved"] == []
    # ENTAILED.md lists the new digest and keeps the earlier model's name when nothing else was asked
    read = AC.read_entailed(after["ENTAILED.md"].decode())
    assert read["rows"]["words/__main__.py"]["sha256"] == E._sha(folder / "words/__main__.py")
    rep = fabula.lint(fab)
    assert rep.errors == [], [str(p) for p in rep.errors]


def test_a_file_gone_from_the_folder_is_told_again(project: Path):
    entail(project, "words")
    (project / "words" / "words" / "__init__.py").unlink()
    st = E.step_state(project / "words.fabulac.cosm")
    assert st["gone"] == ["words/__init__.py"] and st["tell"] == ["words/__init__.py"]
    cp = Model("words")
    entail(project, "words", cp)
    assert [k for s, k in cp.sent if s == "code"] == ["words/__init__.py"]
    assert (project / "words" / "words" / "__init__.py").read_text() == WORDS_INIT


# ---------------------------------------------------------------------------
# A hand edit, named file by file, and its three choices
# ---------------------------------------------------------------------------

def _hand_edit(project: Path) -> tuple[Path, Path]:
    entail(project, "words")
    folder = project / "words"
    (folder / "words" / "__init__.py").write_text(WORDS_INIT + "\n\ndef count_lines(text: str) -> int:\n"
                                                  "    return len(text.splitlines())\n")
    (folder / "NOTES.md").write_text("my notes\n")
    return folder, project / "words.fabulac.cosm"


def test_a_hand_edit_is_named_file_by_file_and_refuses_the_entailment(project: Path):
    folder, fab = _hand_edit(project)
    st = E.step_state(fab)
    assert st["edited"] == ["NOTES.md", "words/__init__.py"]
    assert {f["path"]: f["state"] for f in st["files"]}["NOTES.md"] == "edited by hand"
    text = fab.read_bytes()
    with pytest.raises(E.EntailError, match=r"NOTES\.md, words/__init__\.py"):
        entail(project, "words")
    assert fab.read_bytes() == text


def test_written_over_with_the_persons_word(project: Path):
    folder, fab = _hand_edit(project)
    with pytest.raises(E.EntailError, match=r"NOTES\.md"):
        E.run_entail(project, fab, runtime=runtime(Model("words")), now=NOW, overwrite=["words/__init__.py"])
    cp = Model("words")
    out = E.run_entail(project, fab, runtime=runtime(cp), now=NOW, overwrite=["words/__init__.py", "NOTES.md"])
    assert [k for s, k in cp.sent if s == "code"] == ["words/__init__.py"]
    assert (folder / "words" / "__init__.py").read_text() == WORDS_INIT
    assert not (folder / "NOTES.md").exists() and out["removed"] == ["NOTES.md"]
    assert E.step_state(fab)["edited"] == [] and E.hand_edits(fab) == []


def test_kept_by_hand_is_a_recorded_decision_left_out_until_let_go(project: Path):
    folder, fab = _hand_edit(project)
    mine = (folder / "words" / "__init__.py").read_bytes()
    with pytest.raises(E.EntailError, match="own account"):
        E.keep(project, fab, ["ENTAILED.md"])
    with pytest.raises(E.EntailError, match="not edited by hand"):
        E.keep(project, fab, ["RUNNING.md"])
    got = E.keep(project, fab, ["words/__init__.py", "NOTES.md"], because="I want count_lines there", at=NOW)
    assert [k["path"] for k in got["kept"]] == ["words/__init__.py", "NOTES.md"]
    doc = _doc(fab)
    assert doc["entailed"]["kept"] == [{"path": "NOTES.md", "decision": "N:decision/kept-by-hand-notes-md"},
                                       {"path": "words/__init__.py",
                                        "decision": "N:decision/kept-by-hand-words-init-py"}]
    dec = next(d for d in doc["nodes"] if d["id"] == "N:decision/kept-by-hand-words-init-py")
    assert dec["chose"] == "keep words/words/__init__.py as changed by hand" and dec["because"].startswith("I want")
    assert fabula.lint(fab).errors == []
    st = E.step_state(fab)
    assert st["kept"] == ["NOTES.md", "words/__init__.py"] and st["edited"] == [] and E.hand_edits(fab) == []
    # entailing again: the kept files are never asked or written, even when what they were told from moves
    _edit_fabulac(fab, "summary: 'count_words(text) gives", "summary: 'count_words(text) returns")
    cp = Model("words")
    entail(project, "words", cp)
    assert ("code", "words/__init__.py") not in cp.sent and ("code", "words/__main__.py") in cp.sent
    assert (folder / "words" / "__init__.py").read_bytes() == mine and (folder / "NOTES.md").exists()
    assert _doc(fab)["entailed"]["kept"] == doc["entailed"]["kept"]
    # let go: the decision is retired, and the next entailment tells it again
    E.let_go(project, fab, ["words/__init__.py"])
    doc = _doc(fab)
    assert [k["path"] for k in doc["entailed"]["kept"]] == ["NOTES.md"]
    assert next(d for d in doc["nodes"] if d["id"] == "N:decision/kept-by-hand-words-init-py")["status"] == "retired"
    assert E.step_state(fab)["tell"] == ["words/__init__.py"]
    cp = Model("words")
    entail(project, "words", cp)
    assert [k for s, k in cp.sent if s == "code"] == ["words/__init__.py"]
    assert (folder / "words" / "__init__.py").read_text() == WORDS_INIT
    with pytest.raises(E.EntailError, match="not kept"):
        E.let_go(project, fab, ["words/__init__.py"])


COUNT_LINES = {"id": "C:interface/count-lines", "type": "interface", "name": "count_lines",
               "summary": "count_lines(text) gives the number of lines in text.", "surface": "function",
               "signature": "count_lines(text: str) -> int", "span": {"file": "words/__init__.py", "lines": "9-10"},
               "stance": "observed", "provenance": {"mode": "derived", "sources": ["words/__init__.py#L9-L10"],
                                                    "confidence": 0.8}}


def test_taken_back_as_questions_and_settled_into_the_fabulac(project: Path):
    folder, fab = _hand_edit(project)
    with pytest.raises(E.EntailError, match="not a Python file"):
        E.take_back(project, fab, "NOTES.md", read=lambda d, p, t: [])
    seen = {}

    def read(doc, path, text):
        seen.update(path=path, text=text)
        changed = next(dict(d) for d in doc["nodes"] if d["id"] == "C:interface/count-words")
        changed["summary"] = "count_words(text) counts the runs of characters between white space."
        same = next(dict(d) for d in doc["nodes"] if d["id"] == "N:aim/count-words")
        return [COUNT_LINES, changed, same]
    out = E.take_back(project, fab, "words/__init__.py", read=read, at=NOW)
    assert seen["path"] == "words/__init__.py" and "count_lines" in seen["text"]
    assert out["questions"] == ["D:question/take-back-count-lines", "D:question/take-back-count-words"]
    led = dl.ledger_of(mc.load_volume(fab))
    q_new, q_changed = (led.question(q) for q in out["questions"])
    assert q_new["about"] == "C:interface" and q_new["kind"] == "choice"
    assert q_new["options"] == [dl.TAKE_IT_BACK, dl.LEAVE_IT_OUT]
    assert q_new["proposed"]["item"]["id"] == "C:interface/count-lines" and "span" not in q_new["proposed"]["item"]
    assert q_changed["about"] == "C:interface/count-words" and "summary" in q_changed["asks"]
    # the file is the entailment's again, and no longer a hand edit; NOTES.md still is
    assert E.step_state(fab)["edited"] == ["NOTES.md"]
    assert fabula.lint(fab).errors == []
    # the person answers: take the new interface back, leave the changed one out
    twin = dl.open_twin(fab)
    at = NOW + dt.timedelta(minutes=1)
    dl.record(twin.ledger, [{"question": q_new["id"], "value": dl.TAKE_IT_BACK},
                            {"question": q_changed["id"], "value": dl.LEAVE_IT_OUT}], at=at)
    res = dl.settle(twin.ledger, at=at)
    twin.save()
    assert [s for s, _w in res.settled] == [q_new["id"], q_changed["id"]]
    nodes = {d["id"]: d for d in _doc(fab)["nodes"]}
    assert nodes["C:interface/count-lines"]["stance"] == "observed" and "span" not in nodes["C:interface/count-lines"]
    assert nodes["C:interface/count-words"]["summary"].startswith("count_words(text) gives")
    assert fabula.lint(fab).errors == []
    # what was taken back moved the file it lives in: the next entailment tells it again from the fabulac
    st = E.step_state(fab)
    assert "words/__init__.py" in st["tell"]


READ_ANSWER = """
behaviours:
  - {slug: count-lines, name: Counting lines, summary: count_lines gives the number of lines of a text.,
     of: [C:interface/count-words], when: count_lines(text), does: 'returns len(text.splitlines())', lines: "9-10"}
"""


class Reader(Model):
    """The scripted model, also reading one file back (the read stage's `read` step)."""

    def complete(self, contract, inputs, *, budget, **kw):
        if _t(inputs, "fabulac") == "read":
            self.sent.append(("read", _t(inputs, "path")))
            return candidate(READ_ANSWER, engine="model:scripted-1", tokens=5)
        return super().complete(contract, inputs, budget=budget, **kw)


def test_taken_back_by_the_read_stage(project: Path):
    folder, fab = _hand_edit(project)
    cp = Reader("words")
    out = E.take_back(project, fab, "words/__init__.py", runtime=runtime(cp), now=NOW, at=NOW)
    assert ("read", "words/__init__.py") in cp.sent
    assert len(out["questions"]) == 1
    q = dl.ledger_of(mc.load_volume(fab)).question(out["questions"][0])
    item = q["proposed"]["item"]
    assert q["about"] == "C:behaviour" and item["type"] == "behaviour" and item["does"].startswith("returns len")
    assert q["proposed"]["file"] == "words/__init__.py" and "span" not in item
