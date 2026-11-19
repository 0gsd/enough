"""An authored fabulac entailed as its program (0.8, fabulac-first F3 and F4: pins section 4; MacroCOSM OES 18.4.1
`entailed`, 18.4.7 "Cases as the judge" and "The entailment of an authored fabulac", 18.4.8; Thym 20.7's second
program `entail-authored-python`, 7.3): cases as data for a command and a function, the same notion as a
transconception's outside cases; `tests/test_cases.py` written by rules from them; the folder's rules-written files
byte-stable; `cases-entailed` and `requirement-cased`; the dialectic's answer kinds `given` and `expect`; a tool, a
library and a service entailed (`enough/fabulac_entail.py`), a hand edit refused; and once, the tool's and the
library's tests run in enough's sandbox.

The model is a scripted one: it answers each source with the text given here (the recorded-answer pattern of
tests/test_thym_code.py), the prose case with one method, and the catem with sentences. Fixtures:
tests/fixtures/fabula/authored/ (`words`, a tool; `pairs`, a library; `hello`, a service).
"""
from __future__ import annotations

import datetime as dt
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from enough import dialectic as dl
from enough import fabula
from enough import fabulac_entail as E
from enough import macrocosm as mc
from enough import sandbox as sb
from enough import thym_host as H
from enough import transconception as tc
from enough.thym import Refusal
from enough.thym import declarations as dc
from enough.thym import enumerate as en
from enough.thym import plan as pl
from enough.thym.contracts import AHEAD
from enough.thym.coprocessor import candidate
from enough.thym.folder import Folder
from enough.thym.moves import authored_code as AC
from enough.thym.values import Value
from tests.test_thym_code import engines
from tests.test_thym_shipped import compile_with

NOW = dt.datetime(2026, 11, 20, 12, 0, tzinfo=dt.timezone.utc)
REPO = Path(__file__).resolve().parents[1]
FIX = REPO / "tests" / "fixtures" / "fabula" / "authored"
MAC = sys.platform == "darwin" and os.access("/usr/bin/sandbox-exec", os.X_OK)

WORDS_INIT = '''"""words: count the words of a text."""


def count_words(text: str) -> int:
    """The number of words in text: runs of characters between white space."""
    return len(text.split())
'''

WORDS_MAIN = '''"""The command line of words."""
import argparse
import sys

from words import count_words


def main(argv=None) -> int:
    """words count PATH: print the number of words in the file at PATH."""
    parser = argparse.ArgumentParser(prog="words")
    sub = parser.add_subparsers(dest="command", required=True)
    count = sub.add_parser("count")
    count.add_argument("path")
    args = parser.parse_args(argv)
    try:
        with open(args.path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        print(f"words: {args.path}: no such file", file=sys.stderr)
        return 2
    print(count_words(text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

ONLY_SPACES = '''```python
def test_anything(self):
    folder = Path(tempfile.mkdtemp())
    try:
        (folder / "blank.md").write_text("   \\n  \\n", encoding="utf-8")
        got = subprocess.run(interpreter() + ["-c", BOOT, str(ROOT), ENTRY, "count", "blank.md"],
                             capture_output=True, text=True, cwd=folder)
        self.assertEqual(got.returncode, 0)
        self.assertEqual(got.stdout, "0\\n")
    finally:
        shutil.rmtree(folder, ignore_errors=True)
```'''

PAIRS_INIT = '''"""pairs: read and write key=value lines."""


def split_pair(line: str) -> list:
    """The key and the value of a key=value line, each without the spaces around it."""
    if "=" not in line:
        raise ValueError("no '=' in the line")
    key, value = line.split("=", 1)
    return [key.strip(), value.strip()]
'''

PAIRS_JOIN = '''"""Joining a pair."""


def join_pair(key: str, value: str) -> str:
    """The line key=value."""
    return f"{key}={value}"
'''

HELLO_INIT = '''"""hello: a greeting."""


def greeting(name: str) -> str:
    """The words hello answers with."""
    return f"Hello, {name}."
'''

HELLO_MAIN = '''"""hello's service."""


def main(argv=None) -> int:
    """Serve greetings (served in a later minor)."""
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

CATEMS = {
    "words": """
intro: [{say: words counts the words of a text file from the command line., cites: [N:aim/count-words]}]
sections:
  - heading: Count a file
    sentences: [{say: A person counts the words of one file with the count command., cites: [N:use/count-a-file, C:interface/command-words]}]
""",
    "pairs": """
intro: [{say: pairs reads a line of key=value into its two halves., cites: [N:aim/read-pairs]}]
sections:
  - heading: Split and join
    sentences:
      - {say: split_pair gives the key and the value of a line., cites: [C:interface/split-pair]}
      - {say: join_pair gives the line from a key and a value., cites: [C:interface/join-pair]}
""",
    "hello": """
intro: [{say: hello answers a greeting on a port., cites: [N:aim/greet]}]
sections:
  - heading: Greeting
    sentences: [{say: greeting gives the words hello answers with., cites: [C:interface/greeting]}]
""",
}

SOURCES = {"words/__init__.py": WORDS_INIT, "words/__main__.py": WORDS_MAIN, "pairs/__init__.py": PAIRS_INIT,
           "pairs/joining.py": PAIRS_JOIN, "hello/__init__.py": HELLO_INIT, "hello/__main__.py": HELLO_MAIN}


def _t(inputs: dict, name: str) -> str:
    v = (inputs or {}).get(name)
    v = v[0] if isinstance(v, tuple) else v
    return v.text() if hasattr(v, "text") else str(v or "")


class Model:
    """A scripted model: each source by its path (a list is one answer per attempt), the prose case's one method,
    the catem's sentences; anything else (a question) proposes nothing."""

    def __init__(self, name: str, sources: dict | None = None) -> None:
        self.name = name
        self.sources = {k: (list(v) if isinstance(v, list) else v) for k, v in (sources or SOURCES).items()}
        self.sent: list[tuple[str, str]] = []

    def complete(self, contract, inputs, *, budget, **_kw):
        step = _t(inputs, "fabulac")
        if step == "code":
            p = _t(inputs, "path")
            self.sent.append(("code", p))
            got = self.sources[p]
            if isinstance(got, list):
                got = got.pop(0) if len(got) > 1 else got[0]
            return candidate(f"```python\n{got}```\n", engine="model:scripted-1", tokens=5)
        if step == "test":
            self.sent.append(("test", _t(inputs, "case")))
            return candidate(ONLY_SPACES, engine="model:scripted-1", tokens=5)
        if step == "catem":
            self.sent.append(("catem", _t(inputs, "depth")))
            data = mc.yaml_load(CATEMS[self.name])
            return candidate({**data, "engine": "model:scripted-1"}, engine="model:scripted-1", tokens=5)
        self.sent.append(("other", str(contract.get("move"))))
        return candidate("questions: []", engine="model:scripted-1", tokens=5)


def runtime(cp=None, root: Path | None = None):
    def make(stage, plan, info, mode, scaffolds, program):
        from enough.thym.coprocessor import RefusingCoprocessor
        return {"coprocessor": cp if (mode == "model" and cp is not None) else RefusingCoprocessor(),
                "agent_free": False, "rules": scaffolds, "preflight": None,
                "environment": {"route": "local"} if mode == "model" else {},
                "root": root or H.host_root(), "engines": engines(), "calls": None}
    return make


def doc_of(name: str, folder: Path = FIX) -> tuple[dict, list[dict]]:
    doc = mc.yaml_load((folder / f"{name}.fabulac.cosm").read_text(encoding="utf-8"))
    return {k: v for k, v in doc.items() if k != "nodes"}, doc["nodes"]


@pytest.fixture
def project(tmp_path: Path) -> Path:
    proj = tmp_path / "project"
    proj.mkdir()
    for p in FIX.glob("*.fabulac.cosm"):
        shutil.copyfile(p, proj / p.name)
    return proj


def entail(project: Path, name: str, cp: Model | None = None) -> dict:
    return E.run_entail(project, project / f"{name}.fabulac.cosm", mode="model",
                        runtime=runtime(cp or Model(name)), now=NOW)


# ---------------------------------------------------------------------------
# One notion of a case
# ---------------------------------------------------------------------------

def test_a_case_is_data_for_a_command_or_a_function_and_words_stay_valid():
    cat, items = doc_of("words")
    got = {c["id"]: (s, why) for c, s, why in AC.runnable(cat, items)}
    assert got == {"P:case/count-function": ("function", ""), "P:case/huge-file": (None, "its given is still a question"),
                   "P:case/missing-file": ("command", ""), "P:case/only-spaces": ("prose", ""),
                   "P:case/three-words": ("command", "")}
    # a library has no command to start; a function case calls a function the fabulac holds
    cat, items = doc_of("pairs")
    assert dict((c["id"], s) for c, s, _ in AC.runnable(cat, items))["P:case/as-a-command"] is None
    bad = {"id": "P:case/x", "given": {"calls": "C:interface/nope", "arguments": {}}, "expect": {"value": 1}}
    assert [w for c, s, w in AC.runnable(cat, items + [bad]) if c["id"] == "P:case/x"] == [
        "given.calls names C:interface/nope, which the fabulac does not hold"]
    # data no surface knows is named, with what it lacks
    assert AC.given_surface({"argv": ["x"]})[0] is None
    assert "one {exit, output, error-output} per given step" in AC.expect_problem(
        {"steps": []}, "command", {"steps": [{"arguments": []}]})
    assert AC.expect_problem({"value": 1, "raises": {"error": "E"}}, "function", {})
    assert AC.case_surface({"given": {"steps": [{"arguments": ["a"]}]}, "expect": {"steps": [{"output": "x"}]}}) == (
        None, "expect.steps[0] says its exit status, a whole number")


def test_a_command_case_is_the_same_case_a_transconception_runs_outside():
    """One notion of a case: the authored command case's fields are the ones `case_from_item` (W2-X4) hands the
    outside harness, unchanged in meaning (arguments → argv, output → out, error-output → err, files → written)."""
    _cat, items = doc_of("words")
    case = dict(next(i for i in items if i["id"] == "P:case/three-words"), stands="outside")
    harness = tc.case_from_item(case, {"C:interface/command-words": "command.words"}, {})
    assert harness["files"] == {"notes.md": "one two three\n"} and harness["steps"] == [["count", "notes.md"]]
    assert harness["expect"] == {"steps": [{"exit": 0, "out": "3\n", "err": ""}]}
    assert [tc.case_expect(s) for s in harness["expect"]["steps"]] == case["expect"]["steps"]
    assert AC.case_surface(case) == ("command", "")


def test_a_question_about_a_cases_given_or_expect_takes_words_or_data():
    """The question's kind stays text (the core's closed list); the field decides: a case's given and expect take
    words (a prose case) or data for a surface, and refuse data no surface knows."""
    g = {"kind": "text", "about": "P:case/a#given"}
    e = {"kind": "text", "about": "P:case/a#expect"}
    data = {"steps": [{"arguments": ["count", "notes.md"]}], "files": {"notes.md": "one two\n"}}
    assert dl.check_value(None, g, data) == data
    assert dl.check_value(None, g, "  a file notes.md, counted  ") == "a file notes.md, counted"
    assert dl.check_value(None, g, "{calls: C:interface/count-words, arguments: {text: a b}}") == {
        "calls": "C:interface/count-words", "arguments": {"text": "a b"}}
    assert dl.check_value(None, e, {"value": 2}) == {"value": 2}
    assert dl.check_value(None, e, {"steps": [{"exit": 0, "output": "2\n"}]})
    with pytest.raises(dl.AnswerRefused, match="no surface's given holds argv"):
        dl.check_value(None, g, {"argv": ["count"]})
    with pytest.raises(dl.AnswerRefused, match="raises"):
        dl.check_value(None, e, {"raises": {"message": "no error named"}})
    # an answer by address, with no question, is read the same way; any other field is text as before
    assert dl.check_value(None, {"kind": "text"}, {"value": 1}, qid="P:case/a#expect") == {"value": 1}
    with pytest.raises(dl.AnswerRefused, match="not a structure"):
        dl.check_value(None, {"kind": "text", "about": "P:case/a#of"}, {"value": 1})
    assert dl.case_field("N:requirement/a#given") is None and dl.case_field("P:case/a") is None


def test_an_open_case_is_asked_and_its_answer_lands_as_data(project: Path):
    from enough import fabulac_author_job as A
    fab = project / "words.fabulac.cosm"
    A.raise_next(project, fab, now=NOW)
    L = dl.ledger_of(mc.load_volume(fab))
    qs = {q["about"]: q for q in L.questions() if q.get("state") == "open"}
    assert {"P:case/huge-file#given", "P:case/huge-file#expect"} <= set(qs)
    given = {"files": {"big.md": "one two three four\n"}, "steps": [{"arguments": ["count", "big.md"]}]}
    expect = {"steps": [{"exit": 0, "output": "4\n", "error-output": ""}]}
    at = NOW + dt.timedelta(minutes=1)
    A.answer(project, "words", [{"question": qs["P:case/huge-file#given"]["id"], "value": given, "says": "big.md"},
                                {"question": qs["P:case/huge-file#expect"]["id"], "value": expect, "says": "4"}],
             at=at)
    A.settle_next(project, fab, runtime=runtime(), now=at)
    case = next(i for i in mc.yaml_load(fab.read_text())["nodes"] if i["id"] == "P:case/huge-file")
    assert case["given"] == given and case["expect"] == expect
    assert AC.case_surface(case) == ("command", "")


# ---------------------------------------------------------------------------
# The rules writers
# ---------------------------------------------------------------------------

def test_the_tests_file_is_written_by_rules_one_test_per_runnable_case_byte_stable():
    cat, items = doc_of("words")
    text, held = AC.tests_text(cat, items, "words.fabulac.cosm")
    assert text == AC.tests_text(cat, list(reversed(items)), "words.fabulac.cosm")[0]   # order of items: no matter
    assert held == ["P:case/count-function", "P:case/missing-file", "P:case/three-words"]
    assert text.startswith("# written by rules from words.fabulac.cosm, not by a model")
    compile(text, "test_cases.py", "exec")
    assert "    def test_three_words(self):\n        'P:case/three-words: A file holding three words counts 3.'\n" \
           "        run_command(self, CASES['P:case/three-words'])\n" in text
    assert "        call_function(self, CASES['P:case/count-function'])\n" in text
    assert "'module': 'words',\n        'name': 'count_words',\n        'value': 3," in text
    assert "P:case/only-spaces" not in text and "P:case/huge-file" not in text
    assert "import pytest" not in text and "\nimport unittest\n" in text
    # a library's function cases, a raise among them, and a dotted interface in its own module
    cat, items = doc_of("pairs")
    text, held = AC.tests_text(cat, items, "pairs.fabulac.cosm")
    assert held == ["P:case/join", "P:case/no-equals", "P:case/split"]
    assert "'raises': {\n            'error': 'ValueError',\n            'message': \"no '=' in the line\",\n" in text
    assert "'module': 'pairs.joining',\n        'name': 'join_pair'," in text
    assert [s["path"] for s in AC.plan_sources(cat, items)] == ["pairs/__init__.py", "pairs/joining.py"]


def test_pyproject_and_running_are_written_by_rules_for_each_kind():
    for name, kind, start in (("words", "tool", ["-m", "words"]), ("pairs", "library", []),
                              ("hello", "service", ["-m", "hello"])):
        cat, items = doc_of(name)
        text = AC.pyproject_text(cat, items, f"{name}.fabulac.cosm")
        assert text == AC.pyproject_text(cat, items, f"{name}.fabulac.cosm")
        data = tomllib.loads(text)
        assert data["project"]["name"] == name and data["project"]["requires-python"] == ">=3.10"
        assert data["project"]["version"] == "0.0.0" and data["project"]["dependencies"] == []
        assert data["tool"]["enough"]["kind"] == kind and data["tool"]["enough"]["start"] == start
        if kind == "service":
            assert data["tool"]["enough"]["serve"] == {"port": 0, "reach": []}
        else:
            assert data["tool"]["enough"]["serve"] == {}
        assert ("scripts" in data["project"]) == (kind != "library")
        run = AC.running_text(cat, items, f"{name}.fabulac.cosm")
        assert "python -m unittest discover -s tests -t ." in run
    cat, items = doc_of("words")
    assert tomllib.loads(AC.pyproject_text(cat, items, "w"))["project"]["scripts"] == {"words": "words.__main__:main"}
    assert "serving comes in a later minor" in AC.running_text(*doc_of("hello"), "hello.fabulac.cosm")


def test_a_service_s_running_says_enough_runs_neither_its_tests_nor_it_as_the_sandbox_does():
    """W5-F7's find: a service's RUNNING.md said enough runs its tests, and the sandbox refuses a service's tests."""
    from enough import sandbox as sb
    run = AC.running_text(*doc_of("hello"), "hello.fabulac.cosm")
    said = run.split("## What enough runs here", 1)[1]
    assert "enough runs its tests" not in said
    assert "runs neither its tests nor the service" in said and "its tests included" in said
    prog = sb.program_from_block("hello", {"kind": "service", "start": ["-m", "hello"],
                                           "serve": {"port": 0, "reach": []}})
    with pytest.raises(sb.Refusal) as e:                 # the sandbox: tests and run go through this one refusal
        sb.check_program(prog)
    assert e.value.reason == "service"


def test_a_need_outside_the_standard_library_is_pinned_and_running_says_why_enough_cannot_run_it():
    cat, items = doc_of("words")
    items = items + [{"id": "C:dependency/requests", "type": "dependency", "name": "requests", "package": "requests",
                      "version": "2.32.3", "scope": "run-time", "summary": "HTTP calls.", "stance": "axiom"},
                     {"id": "C:dependency/a-thing", "type": "dependency", "name": "a thing to draw charts with",
                      "scope": "run-time", "summary": "a thing to draw charts with", "stance": "axiom"}]
    data = tomllib.loads(AC.pyproject_text(cat, items, "words.fabulac.cosm"))
    assert data["project"]["dependencies"] == ["requests==2.32.3"]
    run = AC.running_text(cat, items, "words.fabulac.cosm")
    assert "Python 3.10 or later, and `requests==2.32.3`." in run
    assert "enough cannot run it here yet: it needs `requests`, outside the standard library" in run
    assert "Not written into its dependencies: C:dependency/a-thing names no package" in run


# ---------------------------------------------------------------------------
# The entailment, end to end
# ---------------------------------------------------------------------------

def test_a_tool_is_entailed_as_a_folder_beside_its_fabulac(project: Path):
    cp = Model("words")
    out = entail(project, "words", cp)
    folder = project / "words"
    assert out["entailed"] == "words/" and out["recorded"] is True and out["removed"] == []
    have = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())
    assert have == ["ENTAILED.md", "RUNNING.md", "pyproject.toml", "tests/__init__.py", "tests/test_cases.py",
                    "tests/test_prose_cases.py", "words/__init__.py", "words/__main__.py"]
    # the model wrote the sources and the prose case's test, and nothing rules write
    assert sorted(cp.sent) == sorted([("code", "words/__init__.py"), ("code", "words/__main__.py"),
                                      ("test", "P:case/only-spaces"), ("catem", "manual")])
    cat, items = doc_of("words", project)
    assert (folder / "tests/test_cases.py").read_text() == AC.tests_text(cat, items, "words.fabulac.cosm")[0]
    assert (folder / "pyproject.toml").read_text() == AC.pyproject_text(cat, items, "words.fabulac.cosm")
    assert (folder / "RUNNING.md").read_text() == AC.running_text(cat, items, "words.fabulac.cosm")
    assert (folder / "words/__main__.py").read_text() == WORDS_MAIN
    ent = (folder / "ENTAILED.md").read_text()
    lines = ent.splitlines()
    assert lines[0] == "*an entailment of words.fabulac.cosm, in Python, entailed on 2026-11-20 by scripted-1*"
    assert lines[-1] == "Licence of the source: MIT"
    read = AC.read_entailed(ent)
    assert set(read["rows"]) == set(have) - {"ENTAILED.md"}
    assert read["rows"]["tests/test_cases.py"]["from"] == "rules"
    assert read["rows"]["words/__init__.py"]["from"].startswith("C:interface/count-words, P:case/count-function")
    assert read["model"] == ["P:case/only-spaces"]
    assert read["not"] == {"P:case/huge-file": "its given is still a question"}
    prose = (folder / "tests/test_prose_cases.py").read_text()
    assert "# P:case/only-spaces: written by a model from the case's words\n    def test_only_spaces(self):" in prose
    # the fabulac records the entailment, file by file, and the catem
    doc = mc.yaml_load((project / "words.fabulac.cosm").read_text())
    rec = doc["entailed"]
    assert rec["path"] == "words/" and rec["run"] == out["run"]
    assert {f["path"] for f in rec["files"]} == set(have)
    assert all(f["sha256"] == E._sha(folder / f["path"]) for f in rec["files"])
    init = next(f for f in rec["files"] if f["path"] == "words/__init__.py")
    assert init["brief"] == AC.brief_digest(items, init["from"]) == read["rows"]["words/__init__.py"]["brief"]
    assert list(doc).index("entailed") == list(doc).index("nodes") - 1
    assert len(doc["catems"]) == 1 and doc["catems"][0]["depth"] == "manual"
    # every check of the call held, cases-entailed among them
    trace_checks = [c for r in _records(out) if r.get("name") == "entail f as code" for c in r["checks"]]
    assert [c["name"] for c in trace_checks] == ["parses", "interfaces-present", "files-present", "footer",
                                                 "cases-entailed", "provenance"]
    assert all(c["ok"] for c in trace_checks), trace_checks
    # the fabula's own checks: cases-entailed holds on disk; requirement-cased warns of the uncased requirement
    rep = fabula.lint(project / "words.fabulac.cosm")
    assert rep.errors == [], [str(p) for p in rep.errors]
    assert [p.item for p in rep.warnings if p.check == "requirement-cased"] == ["N:requirement/never-writes"]
    assert "cases-entailed" in rep.checks and "requirement-cased" in rep.checks
    assert E.hand_edits(project / "words.fabulac.cosm") == []


def _records(out: dict) -> list[dict]:
    from enough.thym import trace as T
    path = Path(out["trace"])
    hit = sorted(path.glob("*.cosm")) if path.is_dir() else [path]
    data = T.load(hit[0])
    assert not isinstance(data, Refusal), str(data)
    return T.records_of(data)


def test_entailing_again_is_byte_stable_and_a_hand_edit_is_refused(project: Path):
    entail(project, "words")
    folder = project / "words"
    before = {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*") if p.is_file()}
    entail(project, "words")
    after = {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*") if p.is_file()}
    assert after == before
    (folder / "words" / "__init__.py").write_text(WORDS_INIT + "# mine\n")
    (folder / "NOTES.md").write_text("my notes\n")
    fab_text = (project / "words.fabulac.cosm").read_bytes()
    with pytest.raises(E.EntailError, match=r"NOTES\.md, words/__init__\.py"):
        entail(project, "words")
    assert (project / "words.fabulac.cosm").read_bytes() == fab_text
    assert (folder / "NOTES.md").read_text() == "my notes\n"


def test_a_failed_file_is_asked_again_alone(project: Path):
    cp = Model("words", {**SOURCES, "words/__init__.py": ["def count_words(text:\n", WORDS_INIT]})
    entail(project, "words", cp)
    asked = [k for s, k in cp.sent if s == "code"]
    assert asked.count("words/__init__.py") == 2 and asked.count("words/__main__.py") == 1
    assert (project / "words" / "words" / "__init__.py").read_text() == WORDS_INIT


def test_a_missing_interface_fails_the_call(project: Path):
    bad = WORDS_INIT.replace("def count_words(text: str)", "def count(text: str)")
    with pytest.raises(RuntimeError, match="interfaces-present"):
        entail(project, "words", Model("words", {**SOURCES, "words/__init__.py": bad}))
    assert not (project / "words").exists()


def test_a_library_is_entailed_and_a_command_case_of_it_is_named(project: Path):
    out = entail(project, "pairs")
    folder = project / "pairs"
    assert out["files"] == 7
    read = AC.read_entailed((folder / "ENTAILED.md").read_text())
    assert read["not"] == {"P:case/as-a-command": "a library has no command to start: the program's start is not set"}
    assert read["model"] == [] and not (folder / "tests" / "test_prose_cases.py").exists()
    data = tomllib.loads((folder / "pyproject.toml").read_text())
    assert data["tool"]["enough"] == {"kind": "library", "start": [], "serve": {}}
    assert sb.read_program(folder).kind == "library"


def test_a_service_is_entailed_and_refused_at_run(project: Path):
    entail(project, "hello")
    folder = project / "hello"
    data = tomllib.loads((folder / "pyproject.toml").read_text())
    assert data["tool"]["enough"] == {"kind": "service", "start": ["-m", "hello"], "serve": {"port": 0, "reach": []}}
    prog = sb.read_program(folder)
    assert prog.kind == "service"
    with pytest.raises(sb.Refusal) as e:
        sb.check_program(prog)
    assert e.value.reason == "service" and "serving comes in a later minor" in e.value.sentence
    assert "serving comes in a later minor" in (folder / "RUNNING.md").read_text()


def test_a_decompiled_fabulac_is_not_entailed_here(tmp_path: Path):
    proj = tmp_path / "p"
    proj.mkdir()
    shutil.copyfile(REPO / "tests/fixtures/fabula/tally.fabulac.cosm", proj / "tally.fabulac.cosm")
    with pytest.raises(E.EntailError, match="is not authored"):
        E.run_entail(proj, proj / "tally.fabulac.cosm", runtime=runtime(Model("words")), now=NOW)


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------

def _folder(project: Path, name: str) -> tuple[dict, list[dict], dict[str, str]]:
    cat, items = doc_of(name, project)
    root = project / name
    texts = {p.relative_to(root).as_posix(): p.read_text() for p in root.rglob("*") if p.is_file()}
    return cat, items, texts


def test_cases_entailed_names_what_is_missing(project: Path):
    entail(project, "words")
    cat, items, texts = _folder(project, "words")
    fab = "words.fabulac.cosm"
    assert AC.cases_entailed_problem(cat, items, fab, texts.get) is None
    lost = dict(texts, **{AC.TESTS: texts[AC.TESTS].replace("    def test_three_words(self):", "    def x(self):")})
    assert "is not what rules write" in AC.cases_entailed_problem(cat, items, fab, lost.get)
    unmarked = dict(texts, **{AC.PROSE_TESTS: texts[AC.PROSE_TESTS].replace("# P:case/only-spaces: written", "#")})
    assert AC.cases_entailed_problem(cat, items, fab, unmarked.get).startswith("P:case/only-spaces is told in words")
    silent = dict(texts, **{AC.ENTAILED: texts[AC.ENTAILED].replace("- P:case/huge-file: its given is still a "
                                                                     "question.\n", "")})
    assert "P:case/huge-file was not entailed" in AC.cases_entailed_problem(cat, items, fab, silent.get)
    # a case added after the entailment is a case the tests do not hold
    more = items + [{"id": "P:case/two", "type": "case", "name": "two", "summary": "two", "of": [],
                     "given": {"calls": "C:interface/count-words", "arguments": {"text": "a b"}},
                     "expect": {"value": 2}}]
    assert AC.cases_entailed_problem(cat, more, fab, texts.get) == f"{AC.TESTS} has no test for P:case/two"
    # of a cshort, nothing to check
    assert AC.cases_entailed_problem(cat, items, fab, {"CSHORT.md": "x"}.get) is None
    # and the Thym check: a folder that is no entailment holds with nothing to check
    ok, _why = AC._cases_entailed(Value("folder", Folder("x/", (), "0" * 64)), {}, {}, None, None)
    assert ok and "cases-entailed" in AHEAD


def test_requirement_cased_warns_in_an_authored_fabulac_only(project: Path):
    rep = fabula.lint(project / "words.fabulac.cosm")
    assert [(p.check, p.severity, p.item) for p in rep.problems() if p.check == "requirement-cased"] == [
        ("requirement-cased", "warning", "N:requirement/never-writes")]
    assert not [p for p in fabula.lint(REPO / "tests/fixtures/fabula/tally.fabulac.cosm").problems()
                if p.check in ("requirement-cased", "cases-entailed")]


# ---------------------------------------------------------------------------
# The program, as the text has it
# ---------------------------------------------------------------------------

def test_the_program_is_the_texts_block_and_compiles_and_plans():
    path = REPO / "defaults" / "thym" / "entail-authored-python.thym"
    text = path.read_text(encoding="utf-8")
    c = compile_with(text, dc.load(), str(path))
    assert not isinstance(c, Refusal), str(c)
    assert [p.name for p in c.programs()] == ["entail-authored-python"]
    plan = pl.plan(c, [{"name": "f", "type": "fabula", "path": "f.in", "sha256": "0" * 64}],
                   program="entail-authored-python")
    assert not isinstance(plan, Refusal), str(plan)
    assert en.compile_volume(en.enumerate_checked(c)) == text
    d = dc.load()
    assert dc.chosen(d["entail"].view(1), as_word="code")["contract"] == (
        "parses", "interfaces-present", "files-present", "footer", "cases-entailed", "provenance")
    site = Path("/Users/m3u/METMcloud/cosmoes-site")
    shown = subprocess.run(["git", "-C", str(site), "show", "origin/v080-texts:specs/thym.md"], capture_output=True,
                           text=True) if site.is_dir() else None
    if shown is not None and shown.returncode == 0 and "program entail-authored-python" in shown.stdout:
        assert text.split("\n", 2)[2] in shown.stdout


# ---------------------------------------------------------------------------
# Once: the entailed tests, in enough's sandbox
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not MAC, reason="needs macOS with /usr/bin/sandbox-exec")
def test_the_entailed_tests_pass_in_the_sandbox(project: Path, tmp_path: Path):
    entail(project, "words")
    entail(project, "pairs")
    for name, n in (("words", 4), ("pairs", 3)):
        run = sb.prepare(project / name, source_kind="authored", root=tmp_path / "box")
        res = sb.run_tests(run)
        assert res.enforced and res.exit_code == 0, (res.stdout, res.stderr)
        assert f"Ran {n} tests" in res.stderr and "OK" in res.stderr, res.stderr
    # a case the program does not meet fails in the box: the cases are the judge
    bad = WORDS_MAIN.replace("return 2", "return 1")
    shutil.rmtree(project / "words")
    doc = mc.yaml_load((project / "words.fabulac.cosm").read_text())
    doc.pop("entailed")
    (project / "words.fabulac.cosm").write_text(mc.dump(doc))
    entail(project, "words", Model("words", {**SOURCES, "words/__main__.py": bad}))
    res = sb.run_tests(sb.prepare(project / "words", source_kind="authored", root=tmp_path / "box"))
    assert res.exit_code != 0 and "test_missing_file" in res.stderr and "FAILED (failures=1)" in res.stderr
