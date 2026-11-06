"""The fabulac moves (THYM 6.3, 7.3, 20; MacroCOSM OES 18.4.7): `survey`, `history`, `derive t as code with f`,
`derive repo with f`, `tell f as code` and the catems, and the two shipped programs, `decompile-python.thym` and
`compile-python.thym`, end to end on `tests/fixtures/thym/inputs/tiny-tool/`.

A scripted coprocessor stands in for the model: it answers each request by the step it names (`read`, `fold`, `code`,
`readme`, `catem`) and the file it is about. The engines are enough's own (`enough.repo_engine`), so every engine
call is recorded, and every run here replays with the folder deleted. Nothing in tiny-tool, and nothing a scripted
answer holds, is ever run or imported: a canary proves it. Runs land under tmp_path (the conftest's seams).
"""
from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from enough import fabula as FAB
from enough import fabulac_prompts as FP
from enough import macrocosm as mc
from enough import repo_engine as RE
from enough import thym
from enough import thym_host as H
from enough.thym import Refusal
from enough.thym import checks as C
from enough.thym import declarations as dc
from enough.thym import plan as pl
from enough.thym import registry as R
from enough.thym import run as RUN
from enough.thym import trace as T
from enough.thym.coprocessor import candidate
from enough.thym.moves import code as CODE
from enough.thym.values import Value, digest_path

REPO = Path(__file__).resolve().parents[1]
SUITE = REPO / "tests" / "fixtures" / "thym"
TINY = SUITE / "inputs" / "tiny-tool"
DECOMPILE = REPO / "defaults" / "thym" / "decompile-python.thym"
COMPILE = REPO / "defaults" / "thym" / "compile-python.thym"
NOW = dt.datetime(2026, 11, 5, 12, 0, tzinfo=dt.timezone.utc)
STAGES = ["survey-the-repo", "read-the-history", "read-every-file", "fold-the-whole", "raise-the-questions"]


def engines() -> dict:
    return {**H.engines(feed=None), **RE.engines()}


def _t(inputs: dict, name: str) -> str:
    v = (inputs or {}).get(name)
    v = v[0] if isinstance(v, tuple) else v
    return v.text() if hasattr(v, "text") else str(v or "")


class Scripted:
    """A model that answers by the step a request names and the file it is about: `answers[(step, key)]` is a list
    (one per attempt; the last is kept for later attempts) or a function of the inputs."""

    def __init__(self, answers: dict) -> None:
        self.answers = {k: (list(v) if isinstance(v, list) else v) for k, v in answers.items()}
        self.sent: list[tuple[str, str, dict]] = []

    def complete(self, contract, inputs, *, budget):
        step = _t(inputs, "fabulac")
        key = _t(inputs, "path") or _t(inputs, "depth") or step
        self.sent.append((step, key, contract))
        got = self.answers.get((step, key), self.answers.get((step, "*")))
        if got is None:
            raise AssertionError(f"no scripted answer for {step} {key}")
        if isinstance(got, list):
            got = got.pop(0) if len(got) > 1 else got[0]
        if callable(got):
            got = got(inputs)
        sch = contract.get("schema") or {}
        if sch.get("format") == "yaml" and sch.get("stamp") == "engine":
            data = mc.yaml_load(got)                      # as the host's coprocessor does: the model's id stamped in
            if isinstance(data, dict):
                got = {**data, "engine": "model:scripted-1"}
        return candidate(got, engine="model:scripted-1", tokens=5)

    def asked(self, step: str, key: str | None = None) -> list[dict]:
        return [c for s, k, c in self.sent if s == step and (key is None or k == key)]


# ---------------------------------------------------------------------------
# The scripted readings of tiny-tool's five Python files, its fold, and its catems
# ---------------------------------------------------------------------------

READ = {
    "tiny/__init__.py": """
behaviours:
  - {slug: version, name: The version, summary: Importing tiny gives its version string., of: [C:component/tiny],
     when: tiny is imported, does: 'tiny.__version__ is the string "0.2.0".', lines: "1-2"}
""",
    "tiny/__main__.py": """
behaviours:
  - {slug: run-as-module, name: python -m tiny, summary: Running the package runs the command line and exits with its
     status., of: [C:component/tiny.__main__], when: python -m tiny ARGS, does: Calls tiny.cli.main and exits with what
     it returns., lines: "1-5"}
""",
    "tiny/cli.py": """
behaviours:
  - slug: parse
    name: The command line
    summary: build_parser builds the tiny command line, with the sub-commands count and top.
    of: [C:interface/tiny.cli.build_parser, C:interface/command.tiny, C:interface/command.tiny.count,
         C:interface/command.tiny.top, C:component/tiny.cli]
    when: tiny is run
    does: 'tiny --version prints "tiny 0.2.0". A sub-command is required: count FILE [--lines] or top FILE [-n N].'
    errors: [{when: no sub-command, message: argparse's usage and error, exit: 2}]
    lines: "11-21"
  - slug: run
    name: Running one command
    summary: main reads the file, counts its words or lines, or lists its commonest words, and prints one line.
    of: [C:interface/tiny.cli.main]
    when: main(argv)
    does: 'count prints the number of words, or of lines with --lines; top prints "word: count" pairs joined by ", ".'
    edges: [{given: 'tiny top notes.txt -n 2', then: 'the: 5, and: 3'}]
    errors: [{when: the file cannot be read, message: 'tiny: cannot read FILE: OSError', exit: 1}]
    lines: "24-35"
events:
  - {slug: parse-args, name: The arguments are parsed, summary: main parses the command line., agent: C:component/tiny.cli,
     lines: "25"}
  - {slug: print-result, name: The answer is printed, summary: main prints one line., agent: C:component/tiny.cli,
     after: T:event/tiny.cli.parse-args, lines: "28-31"}
""",
    "tiny/counting.py": """
enrich:
  - id: C:interface/tiny.counting.top_words
    takes: [{name: text, means: the text whose words are ranked}, {name: n, means: how many words to give}]
    gives: {means: '(word, count) pairs, commonest first'}
    raises: [{error: CountError, message: n must be 1 or more, when: n is less than 1}]
    lines: "46-51"
  - {id: C:structure/tiny.counting.Summary, fields: [{name: words, means: how many words}], lines: "18-24"}
  - {id: C:component/tiny.counting, does: Counts the words of a text and ranks them.}
behaviours:
  - slug: read
    name: Reading a file
    summary: read_text reads a file in the encoding TINY_ENCODING names, UTF-8 when unset.
    of: [C:interface/tiny.counting.read_text, C:interface/tiny.counting.CountError, C:component/tiny.counting]
    when: read_text(path, env)
    does: Reads the whole file as text; an empty TINY_ENCODING means UTF-8.
    errors: [{when: 'the file cannot be read or decoded, or the encoding is unknown', message: 'cannot read PATH: ERRORCLASS'}]
    lines: "26-33"
  - slug: count
    name: Counting words
    summary: words and count_words read a text's words, runs of the letters A-Z and a-z, lowercased.
    of: [C:interface/tiny.counting.words, C:interface/tiny.counting.count_words, C:interface/tiny.counting.summarise]
    does: A word is a run of letters; "It's" is two words; digits are not words. summarise counts words and lines.
    edges: [{given: '"It''s a dog-day, 2 dogs."', then: '6'}]
    lines: "36-56"
  - slug: top
    name: The commonest words
    summary: top_words gives the n commonest words with their counts, ties in alphabetical order.
    of: [C:interface/tiny.counting.top_words]
    does: Counts the words, sorts by count, highest first, then by the word, and keeps the first n.
    errors: [{when: n is less than 1, message: n must be 1 or more}]
    lines: "46-51"
terms:
  - {slug: word, name: word, word: word, pos: noun, summary: The unit tiny counts., sense: 'A run of letters, compared
     without case.', lines: "10"}
""",
    "tests/test_counting.py": """
cases:
  - slug: runs-of-letters
    name: Words are runs of letters
    summary: count_words counts six words in "It's a dog-day, 2 dogs."
    of: [C:interface/tiny.counting.count_words]
    given: {calls: ['count_words("It''s a dog-day, 2 dogs.")']}
    expect: {value: '6'}
    lines: "6-7"
  - slug: ties
    name: Ties break by letter
    summary: top_words breaks ties alphabetically.
    of: [C:interface/tiny.counting.top_words]
    given: {calls: ['top_words("b a b a c", 2)']}
    expect: {value: '[("a", 2), ("b", 2)]'}
    lines: "10-11"
  - slug: one-or-more
    name: n must be 1 or more
    summary: top_words refuses an n of 0.
    of: [C:interface/tiny.counting.top_words]
    given: {calls: ['top_words("a", 0)']}
    expect: {raises: 'CountError matching "n must be 1 or more"'}
    lines: "14-16"
""",
}

FOLD = """
atem:
  line: tiny counts the words or lines of a text file, or lists its commonest words, from one short command.
  focus: A two-command tool over one text file.
  push: Answer how long a text is in one line.
  pull: Only runs of plain letters count as words.
  cites: [N:use/count-words, N:use/top-words]
audiences:
  - {slug: terminal-users, name: People at a terminal, summary: People who want a word count without an editor.,
     stance: deduced, confidence: 0.7, who: a person at a terminal, needs: a quick count, sources: [README.md#L1-L3]}
aims:
  - {slug: quick-counts, name: A count in one line, summary: tiny sets out to count a file's words in one command.,
     stance: observed, confidence: 0.9, measure: Every README example prints the line shown., roles: {for:
     N:audience/terminal-users}, sources: [README.md#L1-L7]}
uses:
  - {slug: count-words, name: Count the words of a file, summary: A person counts the words or lines of a file.,
     stance: observed, confidence: 0.9, for: N:audience/terminal-users, via: [C:interface/command.tiny.count],
     steps: ['tiny count notes.txt', 'tiny count notes.txt --lines'], gets: one number, sources: [README.md#L5-L6]}
  - {slug: top-words, name: List the commonest words, summary: A person lists the commonest words of a file.,
     stance: observed, confidence: 0.9, for: N:audience/terminal-users, via: [C:interface/command.tiny.top],
     steps: ['tiny top notes.txt -n 2'], gets: '"word: count" pairs', sources: [README.md#L7]}
requirements:
  - {slug: standard-library, name: Standard library only, summary: tiny runs on Python 3.10 or later alone.,
     stance: observed, confidence: 0.9, force: must, met-by: [C:dependency/python], sources: [README.md#L12]}
decisions:
  - {slug: letters-only, name: Words are letters only, summary: A word is a run of letters; digits are not words.,
     stance: deduced, confidence: 0.6, chose: runs of A-Z and a-z, over: [{option: words with digits, because:
     {pending: "why are digits not words?"}}], sources: [C:behaviour/tiny.counting.count]}
exclusions:
  - {slug: no-stemming, name: No stemming, summary: tiny does not fold dogs into dog., stance: deduced,
     confidence: 0.5, horizon: {pending: "will words ever be stemmed?"}, sources: [C:behaviour/tiny.counting.count]}
"""

CATEM = {
    "overview": """
intro: [{say: tiny counts the words of a text file from the command line., cites: [N:aim/quick-counts]}]
sections:
  - heading: Count the words of a file
    sentences: [{say: '`tiny count notes.txt` prints how many words the file holds.', cites: [N:use/count-words]}]
  - heading: List the commonest words
    sentences: [{say: '`tiny top notes.txt -n 2` lists the commonest words with their counts.', cites: [N:use/top-words]}]
""",
}
CATEM["manual"] = CATEM["overview"] + """  - heading: The tiny command line
    sentences:
      - {say: '`tiny` takes the sub-command count or top, and `--version` prints the version.', cites: [C:interface/command.tiny]}
      - {say: '`tiny count FILE --lines` counts lines instead of words.', cites: [C:interface/command.tiny.count]}
      - {say: '`tiny top FILE -n N` lists N words, 3 when left out.', cites: [C:interface/command.tiny.top]}
"""


def code_answer(inputs) -> str:
    """The scripted cshort: tiny-tool's own text for the file asked, as a model would fence it."""
    p = _t(inputs, "path")
    return f"```\n{(TINY / p).read_text(encoding='utf-8')}```\n"


def answers(over: dict | None = None) -> dict:
    out = {("read", p): [a] for p, a in READ.items()}
    out[("fold", "fold")] = [FOLD]
    out[("code", "*")] = code_answer
    out[("readme", "*")] = code_answer
    out.update({("catem", d): [a] for d, a in CATEM.items()})
    out.update(over or {})
    return out


# ---------------------------------------------------------------------------
# Running the stages
# ---------------------------------------------------------------------------

def plan_stage(prog: Path, program: str | None, rows: list[dict]):
    c = thym.check_file(prog)
    assert not isinstance(c, Refusal), str(c)
    return pl.plan(c, rows, program=program)


def run_stage(tmp_path: Path, prog: Path, program: str | None, rows: list[dict], cp=None, **kw):
    rows = [dict(r) for r in rows]
    for r in rows:
        if r["type"] == "fabula" and "sha256" not in r:
            r["sha256"] = digest_path(tmp_path / r["path"])
    p = plan_stage(prog, program, rows)
    assert not isinstance(p, Refusal), str(p)
    return RUN.run(p, inputs_root=tmp_path, root=tmp_path / "root", program=prog, coprocessor=cp,
                   engines=engines(), now=NOW, **kw)


def landed(t, name: str = "g") -> Path:
    assert isinstance(t, T.Trace) and t.landed, getattr(t, "refusal", t)
    out = t.dir / "outputs"
    hit = sorted(out.glob(f"{name}.*")) or sorted(out.glob(f"{name}"))
    assert hit, sorted(x.name for x in out.iterdir())
    return hit[0]


def copy_tiny(tmp_path: Path, name: str = "tiny-tool") -> Path:
    dest = tmp_path / name
    shutil.copytree(TINY, dest)
    return dest


def build(tmp_path: Path, repo: Path, cp: Scripted | None = None, upto: int = 4) -> tuple[Path, list]:
    """Run the stages of decompile-python.thym over `repo`, each with the fabula the stage before landed."""
    runs = []
    t = run_stage(tmp_path, DECOMPILE, "survey-the-repo", [{"name": "repo", "type": "folder", "path": repo.name}])
    f = landed(t, "f")
    runs.append(t)
    for program in STAGES[1:upto]:
        rows = [{"name": "repo", "type": "folder", "path": repo.name},
                {"name": "f", "type": "fabula", "path": str(f.relative_to(tmp_path))}]
        t = run_stage(tmp_path, DECOMPILE, program, rows, cp)
        f = landed(t, "g")
        runs.append(t)
    return f, runs


def fabula_of(path: Path) -> tuple[dict, dict]:
    data = mc.yaml_load(path.read_text(encoding="utf-8"))
    return data, {it["id"]: it for it in data["nodes"]}


# ---------------------------------------------------------------------------
# survey
# ---------------------------------------------------------------------------

def test_survey_finds_files_parts_interfaces_and_the_licence_by_rules_alone(tmp_path):
    repo = copy_tiny(tmp_path)
    t = run_stage(tmp_path, DECOMPILE, "survey-the-repo", [{"name": "repo", "type": "folder", "path": "tiny-tool"}])
    f = landed(t, "f")
    data, items = fabula_of(f)
    assert data["flavour"] == "fabulac" and data["derived"]["completeness"] == "outline"
    assert data["derived"]["mode"] == "rules" and data["source"]["licence"] == "MIT"
    src = data["source"]
    assert (src["path"], src["files"], src["skipped"]) == ("tiny-tool/", 9, 0)
    assert src["tree"] == mc.tree_digest(repo)["tree"]
    # every file, with its digest
    files = {it["path"]: it for it in items.values() if it["type"] == "file"}
    assert set(files) == {"CHANGES.md", "LICENSE", "README.md", "pyproject.toml", "tests/test_counting.py",
                          "tiny/__init__.py", "tiny/__main__.py", "tiny/cli.py", "tiny/counting.py"}
    assert files["tiny/cli.py"]["entry"] is True and files["tiny/counting.py"]["component"] == \
        "C:component/tiny.counting"
    # interfaces with their exact signatures, from the syntax tree
    top = items["C:interface/tiny.counting.top_words"]
    assert top["signature"] == "def top_words(text: str, n: int = DEFAULT_TOP) -> list[tuple[str, int]]"
    assert top["takes"] == [{"name": "text", "type": "str", "required": True},
                            {"name": "n", "type": "int", "default": "DEFAULT_TOP", "required": False}]
    assert items["C:interface/tiny.counting.CountError"]["signature"] == "class CountError(Exception)"
    assert items["C:interface/command.tiny.top"]["signature"] == "tiny top [-h] [-n N] file"
    assert items["C:interface/command.tiny"]["signature"] == "tiny [-h] [--version] {count,top} ..."
    # settings: an environment variable and the reader that reads it, an option, a constant
    env = items["C:setting/env.TINY_ENCODING"]
    assert (env["set-in"], env["default"], env["read-by"]) == ("environment", '"utf-8"',
                                                               ["C:interface/tiny.counting.read_text"])
    assert items["C:setting/option.tiny-count.lines"]["read-by"] == ["C:interface/command.tiny.count"]
    assert items["C:setting/tiny.counting.DEFAULT_TOP"]["default"] == "3"
    # dependencies, the licence and the means
    assert items["C:dependency/python"]["version"] == ">=3.10"
    assert (items["C:dependency/pytest"]["scope"], items["C:dependency/pytest"]["version"]) == ("test", ">=8")
    lic = items["R:licence/mit"]
    assert (lic["identifier"], lic["holder"], lic["year"]) == ("MIT", "Orchard Tools", "2026")
    assert {"R:means/python", "R:means/setuptools", "R:means/pytest"} <= set(items)
    # nothing observed by rules is a guess: every item observed, components' responsibilities left as questions
    assert all(it.get("stance") == "observed" for it in items.values())
    assert all("span" in it for it in items.values() if it["type"] in ("interface", "structure", "setting")
               or (it["type"] == "file" and it["language"] != "binary"))
    assert mc.is_pending(items["C:component/tiny.cli"]["does"])
    # spans on everything read from the code; data shapes, raised messages, printed words and exits by rules
    for iid in ("C:file/tiny--cli-py", "C:component/tiny.cli", "C:interface/tiny.counting.top_words",
                "C:dependency/python", "C:setting/env.TINY_ENCODING", "C:structure/tiny.counting.Summary"):
        assert items[iid]["span"]["file"].endswith(".py"), iid
    assert items["C:interface/tiny.counting.top_words"]["span"] == {"file": "tiny/counting.py", "lines": "46-51"}
    st = items["C:structure/tiny.counting.Summary"]
    assert st["shape"] == "a dataclass whose instances cannot change" and st["fields"] == [
        {"name": "words", "type": "int", "required": True}, {"name": "lines", "type": "int", "required": True},
        {"name": "encoding", "type": "str", "default": '"utf-8"', "required": False}]
    assert items["C:interface/tiny.counting.top_words"]["raises"] == [{"error": "CountError",
                                                                      "message": "n must be 1 or more"}]
    assert items["C:interface/tiny.counting.read_text"]["raises"] == [
        {"error": "CountError", "message": "cannot read {path}: {e.__class__.__name__}"}]
    words = items["C:behaviour/tiny.cli.main.words"]
    assert words["errors"] == [{"when": "main, line 33", "message": "tiny: {e}", "exit": 1}]
    assert items["C:interface/command.tiny"]["gives"] == {"exit": "0, 1 (what main returns or exits with)"}
    assert items["C:setting/tiny.counting.DEFAULT_TOP"]["span"] == {"file": "tiny/counting.py", "lines": "11"}
    rep = FAB.lint(f)
    assert not rep.errors, [str(p) for p in rep.errors]
    rec = t.records[-1]
    assert {c["name"]: c["ok"] for c in rec["checks"]} == {
        "files-found": True, "code-span": True, "licence-recorded": True, "fabula-checks": True, "provenance": True}


def test_survey_reads_nothing_it_runs_and_calls_only_its_engines(tmp_path):
    copy_tiny(tmp_path)
    t = run_stage(tmp_path, DECOMPILE, "survey-the-repo", [{"name": "repo", "type": "folder", "path": "tiny-tool"}])
    landed(t, "f")
    recs = [mc.yaml_load(p.read_text()) for p in sorted((t.dir / "candidates").glob("*-e*.1.cosm"))]
    called = sorted({r["engine"] for r in recs})
    assert called == ["repo.tree", "syntax.manifest", "syntax.outline"]
    assert sum(r["engine"] == "syntax.outline" for r in recs) == 5


@pytest.mark.parametrize("make, words", [
    (lambda d: [(d / f"m{i}.py").write_text("x = 1\n") for i in range(61)], "more than sixty Python files"),
    (lambda d: (d / "big.py").write_text("x = 1\n" * 6001), "more than six thousand lines of Python"),
    (lambda d: (d / "notes.md").write_text("# notes\n"), "there is no Python file here"),
])
def test_the_band_is_refused_in_the_programs_words(tmp_path, make, words):
    d = tmp_path / "big"
    d.mkdir()
    make(d)
    t = run_stage(tmp_path, DECOMPILE, "survey-the-repo", [{"name": "repo", "type": "folder", "path": "big"}])
    assert isinstance(t, T.Trace) and not t.landed and words in t.refusal.message


def test_the_move_refuses_the_band_itself():
    from enough.thym import folder as FO
    f = FO.Folder("x/", (FO.Entry("README.md", "0" * 64, 3),), "1" * 64, _texts={"README.md": "hi\n"})
    with pytest.raises(CODE.MoveError, match="there is no Python file here"):
        CODE.survey(None, Value("folder", f))


def test_a_folder_with_no_licence_records_the_question(tmp_path):
    repo = copy_tiny(tmp_path)
    (repo / "LICENSE").unlink()
    py = repo / "pyproject.toml"
    py.write_text(py.read_text().replace('license = "MIT"\n', ""))
    t = run_stage(tmp_path, DECOMPILE, "survey-the-repo", [{"name": "repo", "type": "folder", "path": "tiny-tool"}])
    f = landed(t, "f")
    data, items = fabula_of(f)
    assert mc.is_pending(data["source"]["licence"]) and "licence" in data["source"]["licence"]["pending"]
    assert mc.is_pending(items["R:licence/unknown"]["identifier"])
    verdict = next(c for c in t.records[-1]["checks"] if c["name"] == "licence-recorded")
    assert verdict["ok"] and "question" in verdict["why"]
    rep = FAB.lint(f)
    assert any(p.check == "licence-recorded" for p in rep.warnings), [str(p) for p in rep.warnings]
    assert not any(p.check == "licence-recorded" for p in rep.errors)


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------

def git(repo: Path, *args: str, when: str = "2026-10-01T10:00:00+00:00", who: str = "Ann Example") -> None:
    env = {"PATH": "/usr/bin:/bin", "HOME": str(repo.parent), "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_AUTHOR_NAME": who, "GIT_AUTHOR_EMAIL": "a@example.com",
           "GIT_COMMITTER_NAME": who, "GIT_COMMITTER_EMAIL": "a@example.com", "GIT_AUTHOR_DATE": when,
           "GIT_COMMITTER_DATE": when}
    subprocess.run([RE.git_binary(), "-C", str(repo), *args], check=True, env=env, capture_output=True)


def make_clone(tmp_path: Path) -> Path:
    """tiny-tool as a clone of three commits over five weeks and two tags, by two people."""
    repo = copy_tiny(tmp_path)
    keep = {p: p.read_bytes() for p in repo.rglob("*") if p.is_file()}
    for p in keep:
        if p.name not in ("counting.py", "LICENSE", "README.md", "__init__.py"):
            p.unlink()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "Add word counting", "-m", "Because we needed a count.\n\nSigned-off-by: "
        "Ann Example <ann@example.com>", when="2026-09-01T10:00:00+00:00")
    git(repo, "tag", "v0.1.0", when="2026-09-01T10:00:00+00:00")
    for p, b in keep.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "Add the command line", when="2026-09-03T10:00:00+00:00", who="Orchard Tools")
    git(repo, "commit", "-q", "--allow-empty", "-m", "fix: top breaks ties by letter",
        when="2026-10-10T09:00:00+00:00", who="Bo Example")
    git(repo, "tag", "-a", "v0.2.0", "-m", "0.2.0", when="2026-10-10T09:00:00+00:00", who="Bo Example")
    return repo


@pytest.mark.skipif(RE.git_binary() is None, reason="git is not installed here")
def test_history_reads_a_real_clone_through_the_engine_and_replays_without_it(tmp_path):
    repo = make_clone(tmp_path)
    t = run_stage(tmp_path, DECOMPILE, "survey-the-repo", [{"name": "repo", "type": "folder", "path": "tiny-tool"}])
    f = landed(t, "f")
    rows = [{"name": "repo", "type": "folder", "path": "tiny-tool"},
            {"name": "f", "type": "fabula", "path": str(f.relative_to(tmp_path))}]
    h = run_stage(tmp_path, DECOMPILE, "read-the-history", rows)
    g = landed(h, "g")
    data, items = fabula_of(g)
    changes = [it for it in items.values() if it["type"] == "change"]
    assert [c["name"] for c in changes] == ["Add word counting", "Add the command line",
                                            "fix: top breaks ties by letter"]
    first = changes[0]
    assert (first["at"], first["nature"], first["because"]) == ("2026-09-01", "feature", "Because we needed a count.")
    assert changes[2]["nature"] == "fix" and changes[1]["touches"]
    rel = {it["tag"]: it for it in items.values() if it["type"] == "release"}
    assert set(rel) == {"v0.1.0", "v0.2.0"} and rel["v0.2.0"]["version"] == "0.2.0"
    assert first["release"] == "R:release/v0-1-0" and changes[2]["release"] == "R:release/v0-2-0"
    phases = sorted(it["id"] for it in items.values() if it["type"] == "phase")
    assert phases == ["R:phase/episode-1", "R:phase/episode-2", "R:phase/episode-3"]  # a tag, then a 37-day gap
    makers = {it["id"]: it for it in items.values() if it["type"] == "maker"}
    # a name only where the repository states it (the licence's holder); the others are roles with counts
    assert set(makers) == {"R:maker/contributor-1", "R:maker/orchard-tools", "R:maker/contributor-2"}
    text = g.read_text()
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text) and "Ann Example" not in text and "Bo Example" not in text
    assert all(c["ok"] for c in h.records[-1]["checks"]), h.records[-1]["checks"]
    assert FAB.lint(g).ok
    # the replay needs no clone and no git
    shutil.rmtree(repo)
    again = RUN.replay(h.dir, root=tmp_path / "root", engines=engines())
    assert again.replay["identical"], again.replay


def test_history_of_a_folder_that_is_no_clone_is_a_question(tmp_path):
    f, _runs = build(tmp_path, copy_tiny(tmp_path), upto=2)
    _data, items = fabula_of(f)
    q = items["D:question/history"]
    assert q["about"] == "R" and "not a git clone" in q["asks"] and q["state"] == "open"
    assert not any(it["type"] in ("change", "release", "maker") for it in items.values())
    rep = FAB.lint(f)
    assert not rep.errors, [str(p) for p in rep.errors]


# ---------------------------------------------------------------------------
# derive t as code with f: one file against the outline
# ---------------------------------------------------------------------------

def test_every_file_is_read_against_the_outline_and_gathered(tmp_path):
    cp = Scripted(answers())
    f, runs = build(tmp_path, copy_tiny(tmp_path), cp, upto=3)
    assert sorted(k for s, k, _c in cp.sent) == sorted(READ)
    _data, items = fabula_of(f)
    b = items["C:behaviour/tiny.cli.run"]
    assert b["span"] == {"file": "tiny/cli.py", "lines": "24-35"} and b["stance"] == "observed"
    assert b["errors"][0]["message"] == "tiny: cannot read FILE: OSError"
    case = items["P:case/tests.test_counting.ties"]
    assert case["of"] == ["C:interface/tiny.counting.top_words"]
    assert items["L:term/tiny.counting.word"]["feed"] == {"word": "word", "pos": "noun", "origin": "feed"}
    assert FAB.lint(f).ok, [str(p) for p in FAB.lint(f).errors]
    node = next(r for r in runs[-1].records if r.get("move") == "for")
    assert node["passes"] == 5


def test_a_reading_adds_only_what_it_reads_and_enriches_the_outlines_own_items(tmp_path):
    """A reading holds only its additions for its file (its references resolve in the fabula it was read with, and
    its fabula-checks run on the two together); an outline item of its own file comes back with the fields the code
    shows, and gather lays them in without changing what rules read."""
    cp = Scripted(answers())
    f, runs = build(tmp_path, copy_tiny(tmp_path), cp, upto=3)
    _data, items = fabula_of(f)
    top = items["C:interface/tiny.counting.top_words"]
    assert top["signature"] == "def top_words(text: str, n: int = DEFAULT_TOP) -> list[tuple[str, int]]"
    assert top["takes"][1] == {"name": "n", "type": "int", "default": "DEFAULT_TOP", "required": False,
                               "means": "how many words to give"}
    assert top["raises"] == [{"error": "CountError", "message": "n must be 1 or more", "when": "n is less than 1"}]
    assert top["gives"] == {"type": "list[tuple[str, int]]", "means": "(word, count) pairs, commonest first"}
    assert items["C:structure/tiny.counting.Summary"]["fields"][0]["means"] == "how many words"
    assert items["C:component/tiny.counting"]["does"] == "Counts the words of a text and ranks them."
    assert top["provenance"]["sources"] == ["tiny/counting.py#L46-L51"]          # the same lines, once
    # a reading's own value: its additions only (read again against the gathered fabula, the component's does is
    # said already, so it is not said twice)
    from enough.thym.moves import code as code_mod
    base = [it for it in items.values()]
    got = code_mod.parse_reading(READ["tiny/counting.py"], path="tiny/counting.py", module="tiny.counting",
                                 n_lines=56, taken={i for i in items}, base=base)
    assert {it["id"] for it in got if "type" not in it} == {"C:interface/tiny.counting.top_words",
                                                            "C:structure/tiny.counting.Summary"}
    assert not any(it.get("type") == "file" for it in got)
    with pytest.raises(ValueError, match="not an item of the outline for tiny/counting.py"):
        code_mod.parse_reading("enrich: [{id: C:interface/tiny.cli.main, gives: {means: x}}]", path="tiny/counting.py",
                               module="m", n_lines=56, taken=set(), base=base)
    with pytest.raises(ValueError, match="a interface takes takes, gives, raises here, not signature"):
        code_mod.parse_reading("enrich: [{id: C:interface/tiny.counting.top_words, signature: def x()}]",
                               path="tiny/counting.py", module="m", n_lines=56, taken=set(), base=base)


def test_a_reading_with_a_span_outside_its_file_is_refused_and_asked_again(tmp_path):
    bad = READ["tiny/__init__.py"].replace('lines: "1-2"', 'lines: "1-40"')
    cp = Scripted(answers({("read", "tiny/__init__.py"): [bad, READ["tiny/__init__.py"]]}))
    build(tmp_path, copy_tiny(tmp_path), cp, upto=3)
    asked = cp.asked("read", "tiny/__init__.py")
    assert len(asked) == 2
    failed = asked[1]["repair"]["failed"]
    assert [x["name"] for x in failed] == ["code-span"] and "outside tiny/__init__.py" in failed[0]["why"]


def test_a_reading_that_names_an_interface_the_outline_lacks_is_refused(tmp_path):
    bad = READ["tiny/__main__.py"].replace("C:component/tiny.__main__", "C:interface/tiny.__main__.go")
    cp = Scripted(answers({("read", "tiny/__main__.py"): [bad]}))
    copy_tiny(tmp_path)
    t = run_stage(tmp_path, DECOMPILE, "survey-the-repo", [{"name": "repo", "type": "folder", "path": "tiny-tool"}])
    f = landed(t, "f")
    rows = [{"name": "repo", "type": "folder", "path": "tiny-tool"},
            {"name": "f", "type": "fabula", "path": str(f.relative_to(tmp_path))}]
    r = run_stage(tmp_path, DECOMPILE, "read-every-file", rows, cp)
    assert isinstance(r, T.Trace) and not r.landed
    assert len(cp.asked("read", "tiny/__main__.py")) == 3
    assert "outline-cited" in r.refusal.message or "fabula-checks" in r.refusal.message, r.refusal.message
    assert "tiny.__main__.go" in r.refusal.message


def test_a_reading_that_leaves_an_interface_unsaid_fails_coverage(tmp_path):
    thin = READ["tiny/counting.py"].split("  - slug: top")[0]
    cp = Scripted(answers({("read", "tiny/counting.py"): [thin, READ["tiny/counting.py"]]}))
    build(tmp_path, copy_tiny(tmp_path), cp, upto=3)
    failed = cp.asked("read", "tiny/counting.py")[1]["repair"]["failed"]
    assert [x["name"] for x in failed] == ["coverage"] and "tiny.counting.top_words" in failed[0]["why"]


def test_an_answer_that_is_not_the_shape_is_asked_again():
    with pytest.raises(ValueError, match="sections this reading does not take: functions"):
        CODE.parse_reading("functions: []", path="a.py", module="a", n_lines=3, taken=set())
    with pytest.raises(ValueError, match="cases entry 1 .* has no given"):
        CODE.parse_reading("cases: [{name: x, summary: y, of: [z], expect: {value: 1}}]", path="a.py", module="a",
                           n_lines=3, taken=set())


def test_a_long_file_is_read_in_chunks_cut_at_a_definition():
    text = "".join(f"def f{i}():\n    return {i}\n\n" for i in range(400))
    parts = CODE.chunks_of(text, 600)
    assert parts[0][0] == 1 and parts[-1][1] == 1200 and all(b - a < 600 for a, b in parts)
    assert all(parts[k][0] == parts[k - 1][1] + 1 for k in range(1, len(parts)))
    assert all(text.split("\n")[a - 1].startswith("def ") for a, _b in parts)


# ---------------------------------------------------------------------------
# derive repo with f: the fold
# ---------------------------------------------------------------------------

def test_the_fold_is_grounded_and_says_what_it_inferred(tmp_path):
    cp = Scripted(answers())
    f, runs = build(tmp_path, copy_tiny(tmp_path), cp, upto=4)
    data, items = fabula_of(f)
    assert data["atem"]["line"].startswith("tiny counts the words")
    assert data["derived"]["mode"] == "model" and data["derived"]["completeness"] == "full"
    # survey, history and the fold record their runs; the reading's run is gather's to record (not this lane's)
    assert data["derived"]["model"] == "scripted-1" and [r["program"] for r in data["derived"]["runs"]] == [
        "survey-the-repo", "read-the-history", "fold-the-whole"]
    use = items["N:use/count-words"]
    assert use["stance"] == "observed" and use["span"] == {"file": "README.md", "lines": "5-6"}
    dec = items["N:decision/letters-only"]
    assert dec["stance"] == "deduced" and dec["provenance"]["confidence"] <= 0.7
    assert mc.is_pending(dec["over"][0]["because"])
    assert all(c["ok"] for c in runs[-1].records[-1]["checks"])
    assert FAB.lint(f).ok


def test_an_observed_claim_without_a_documents_lines_is_said_as_deduced():
    data = mc.yaml_load(FOLD)
    data["aims"][0]["sources"] = ["C:interface/command.tiny"]
    data["aims"][0]["confidence"] = 1.0
    items, _atem, _cites = CODE.parse_fold(data, taken={"C:interface/command.tiny"}, paths={"README.md"})
    aim = next(it for it in items if it["type"] == "aim")
    assert aim["stance"] == "deduced" and aim["provenance"]["confidence"] == 0.7 and "span" not in aim


def test_a_fold_item_that_rests_on_nothing_is_refused_and_asked_again(tmp_path):
    loose = FOLD.replace("sources: [README.md#L1-L3]}\naims", "sources: []}\naims")
    cp = Scripted(answers({("fold", "fold"): [loose, FOLD]}))
    build(tmp_path, copy_tiny(tmp_path), cp, upto=4)
    asked = cp.asked("fold")
    assert len(asked) == 2 and asked[1]["repair"]["failed"][0]["name"] == "fold-grounded"
    assert "N:audience/terminal-users cites nothing" in asked[1]["repair"]["failed"][0]["why"]


def test_derive_of_a_folder_without_with_is_refused(tmp_path):
    p = tmp_path / "p.thym"
    p.write_text("thym 1\n\nprogram p\n  takes repo: folder\n  gives g: fabula\n\n  give derive repo\nend\n")
    copy_tiny(tmp_path)
    t = run_stage(tmp_path, p, None, [{"name": "repo", "type": "folder", "path": "tiny-tool"}], Scripted({}))
    assert not t.landed and "derive of a folder folds what the stages found: derive repo with f" in t.refusal.message


# ---------------------------------------------------------------------------
# tell f as code, and the catems
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def built(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("built")
    f, runs = build(tmp, copy_tiny(tmp), Scripted(answers()), upto=4)
    return tmp, f, runs


def compile_run(tmp: Path, f: Path, cp: Scripted, **kw):
    return run_stage(tmp, COMPILE, None, [{"name": "f", "type": "fabula", "path": str(f.relative_to(tmp))}], cp, **kw)


def test_tell_as_code_writes_the_cshort_file_by_file(built, tmp_path):
    tmp, f, _runs = built
    cp = Scripted(answers())
    t = compile_run(tmp, f, cp)
    assert isinstance(t, T.Trace) and t.landed, t.refusal
    out = t.dir / "outputs" / "code"
    assert sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()) == [
        "CSHORT.md", "README.md", "pyproject.toml", "tiny/__init__.py", "tiny/__main__.py", "tiny/cli.py",
        "tiny/counting.py"]
    lines = (out / "CSHORT.md").read_text().strip().split("\n")
    assert lines[0] == "*a cshort of g.cosm, in Python, compiled on 2026-11-05 by scripted-1; never run*"
    assert lines[-1] == "Licence of the source: MIT"
    assert "Not rebuilt: CHANGES.md, LICENSE, tests/test_counting.py." in lines
    # the packaging file is written by rules from what the survey recorded, never asked of the model
    assert any(ln.startswith("| pyproject.toml | rules, from C:file/pyproject-toml | ") for ln in lines)
    pack = (out / "pyproject.toml").read_text()
    assert pack.startswith("# written by rules from g.cosm, not by a model")
    assert 'name = "tiny-tool"' in pack and 'version = "0.2.0"' in pack and 'requires-python = ">=3.10"' in pack
    assert '"test" = ["pytest>=8"]' in pack and 'packages = ["tiny"]' in pack
    assert not [k for s, k, _c in cp.sent if k == "pyproject.toml"]
    assert [s for s, _k, _c in cp.sent].count("code") == 4 and [s for s, _k, _c in cp.sent].count("readme") == 1
    rec = next(r for r in t.records if r.get("name") == "tell f as code")
    assert [c["name"] for c in rec["checks"]] == ["parses", "interfaces-present", "files-present", "footer",
                                                  "provenance"] and all(c["ok"] for c in rec["checks"])
    manual = (t.dir / "outputs" / "manual.md").read_text()
    assert manual.rstrip().endswith("at depth manual, compiled on 2026-11-05 by scripted-1*")


def test_a_file_that_does_not_parse_is_asked_again_alone_and_nothing_told_is_run(built, tmp_path):
    tmp, f, _runs = built
    canary = tmp_path / "canary"
    broken = f"import pathlib\npathlib.Path({str(canary)!r}).write_text('ran')\ndef main(:\n"
    cp = Scripted(answers({("code", "tiny/cli.py"): [broken, code_answer]}))
    t = compile_run(tmp, f, cp)
    assert isinstance(t, T.Trace) and t.landed, t.refusal
    assert len(cp.asked("code", "tiny/cli.py")) == 2 and len(cp.asked("code", "tiny/counting.py")) == 1
    failed = cp.asked("code", "tiny/cli.py")[1]["repair"]["failed"]
    assert failed[0]["name"] == "parses" and failed[0]["why"].startswith("tiny/cli.py: line 3")
    assert not canary.exists()


def test_a_cshort_missing_an_interface_is_refused_and_nothing_imported_runs(built, tmp_path):
    tmp, f, _runs = built
    canary = tmp_path / "canary"
    loud = (f"import pathlib\npathlib.Path({str(canary)!r}).write_text('imported')\n"
            + (TINY / "tiny/counting.py").read_text().replace("def top_words(", "def top(")
            + "\nif __name__ == '__main__':\n    pathlib.Path('x').write_text('ran')\n")
    cp = Scripted(answers({("code", "tiny/counting.py"): [loud]}))
    t = compile_run(tmp, f, cp)
    assert isinstance(t, T.Trace) and not t.landed
    assert t.refusal.check == "interfaces-present" or "interfaces-present" in t.refusal.message
    assert "top_words" in t.refusal.message and len(cp.asked("code", "tiny/counting.py")) == 3
    assert not canary.exists() and not (tmp / "x").exists()


def test_a_catem_at_each_depth(built, tmp_path):
    tmp, f, _runs = built
    for depth in ("line", "overview", "manual"):
        p = tmp_path / f"{depth}.thym"
        p.write_text(f"thym 1\n\nprogram p\n  takes f: fabula\n  gives c: short\n\n  give tell f as {depth}\nend\n")
        cp = Scripted(answers())
        t = run_stage(tmp, p, None, [{"name": "f", "type": "fabula", "path": str(f.relative_to(tmp))}], cp)
        out = landed(t, "c").read_text()
        foot = out.rstrip().split("\n")[-1]
        assert f"at depth {depth}, compiled on 2026-11-05" in foot, out
        assert all(c["ok"] for c in t.records[-1]["checks"]), t.records[-1]["checks"]
        if depth == "line":
            assert out.startswith("tiny counts the words") and cp.sent == []
        else:
            assert "## Count the words of a file" in out and len(cp.sent) == 1
        if depth == "manual":
            assert "## The tiny command line" in out


def test_a_catem_at_depth_line_is_the_atems_line_and_asks_no_model(built):
    """`tell f as line` (THYM 20.7) asks no model. `line` is also a type of `thym 1`; in a declaration's list of
    words it is a word (`types.accepts`), while a type's name that the list does not hold is still refused."""
    tmp = built[0]
    p = tmp / "text.thym"
    p.write_text("thym 1\n\nprogram p\n  takes f: fabula\n  gives c: short\n\n  give tell f as text\nend\n")
    r = thym.check_file(p)
    assert isinstance(r, Refusal) and r.check == "type" and "`text` is not one" in r.message
    _tmp, f, _runs = built
    fab = Value("fabula", mc.yaml_load(f.read_text()), path=f)
    v = CODE.tell_catem(type("Ctx", (), {"now": NOW})(), fab, "line")
    lines = v.text().strip().split("\n")
    assert lines[0].startswith("tiny counts the words") and lines[-1].startswith("*a catem of g.cosm, at depth line")
    assert C.verdict("uses-told", v, {}, {}, None) == (True, "") and C.verdict("footer", v, {}, {}, None)[0]


def test_a_catem_that_leaves_a_use_untold_is_asked_again(built, tmp_path):
    tmp, f, _runs = built
    short = CATEM["overview"].split("  - heading: List")[0]
    cp = Scripted(answers({("catem", "overview"): [short, CATEM["overview"]]}))
    p = tmp_path / "o.thym"
    p.write_text("thym 1\n\nprogram p\n  takes f: fabula\n  gives c: short\n\n  give tell f as overview\nend\n")
    t = run_stage(tmp, p, None, [{"name": "f", "type": "fabula", "path": str(f.relative_to(tmp))}], cp)
    landed(t, "c")
    failed = cp.asked("catem")[1]["repair"]["failed"]
    assert [x["name"] for x in failed] == ["uses-told"] and "N:use/top-words" in failed[0]["why"]


def test_a_catem_of_a_poem_is_refused_for_its_flavour(tmp_path):
    p = tmp_path / "v.thym"
    p.write_text("thym 1\n\nprogram p\n  takes poem: text\n  gives c: short\n\n  let f = derive poem as verse\n"
                 "  give tell f as manual\nend\n")
    r = thym.check_file(p)
    assert isinstance(r, Refusal) and r.check == "flavour" and "a catem is told from a fabulac" in r.message


def test_rules_mode_refuses_code_and_tells_a_catem_by_its_outline(built, tmp_path):
    tmp, f, _runs = built
    t = compile_run(tmp, f, Scripted({}), rules=True)
    assert isinstance(t, (Refusal, T.Trace))
    refusal = t if isinstance(t, Refusal) else t.refusal
    assert refusal is not None and "rules" in (refusal.check + refusal.message)
    v = CODE.uses_outline(type("Ctx", (), {"now": NOW})(), Value("fabula", mc.yaml_load(f.read_text())),
                          **{"as": "manual"})
    assert v.state == "pending" and "## Count the words of a file" in v.text() and "## tiny top" in v.text()


def test_rules_refuses_a_folder_derive_and_tell_as_code_at_plan_time(built, tmp_path):
    """`scaffold-when` may say `none` (the conductor's ruling L6): `derive` of a folder and `tell … as code` have no
    rules scaffold, so `--rules` refuses them at plan time, in the words a move without a scaffold gets, and asks
    and writes nothing; `tell f as manual` keeps its scaffold, `uses-outline`."""
    tmp, f, _runs = built
    t = compile_run(tmp, f, Scripted({}), rules=True)
    assert isinstance(t, Refusal) and (t.stage, t.check, t.line) == ("plan", "rules", 12), t
    assert t.message == ("1 step asks a model and has no scaffold: give code: tell f as code (line 12); --rules runs "
                         "no model")
    rows = [{"name": "repo", "type": "folder", "path": "tiny-tool"},
            {"name": "f", "type": "fabula", "path": str(f.relative_to(tmp)), "sha256": digest_path(f)}]
    p = plan_stage(DECOMPILE, "fold-the-whole", rows)
    r = RUN.run(p, inputs_root=tmp, root=tmp / "root", program=DECOMPILE, rules=True, engines=engines(), now=NOW)
    assert isinstance(r, Refusal) and (r.stage, r.check) == ("plan", "rules"), r
    assert r.message.startswith("1 step asks a model and has no scaffold: give derive repo with f (line ")
    decl = R.declarations()["tell"]
    assert dc.chosen(decl.view(1), as_word="code")["scaffold"] is None
    assert dc.chosen(decl.view(1), as_word="manual")["scaffold"] == "uses-outline"
    assert dc.chosen(R.declarations()["derive"].view(1), first_type="folder")["scaffold"] is None
    assert dc.chosen(R.declarations()["derive"].view(1), as_word="code", first_type="text")["scaffold"] == \
        "file-outline"
    assert R.declarations()["derive"].view(0).scaffold_when == ()          # a thym 0 program sees nothing new


# ---------------------------------------------------------------------------
# The whole build, then the compile, replayed with the folder gone
# ---------------------------------------------------------------------------

def test_decompile_then_compile_end_to_end_and_every_run_replays_without_the_folder(tmp_path):
    repo = copy_tiny(tmp_path)
    cp = Scripted(answers())
    f, runs = build(tmp_path, repo, cp, upto=4)
    if R.MOVES.lookup("question") is not None:
        t = run_stage(tmp_path, DECOMPILE, "raise-the-questions",
                      [{"name": "f", "type": "fabula", "path": str(f.relative_to(tmp_path))}],
                      Scripted({("question", "*"): ["questions: []"]}))
        if isinstance(t, T.Trace) and t.landed:
            runs.append(t)
    c = compile_run(tmp_path, f, Scripted(answers()))
    assert isinstance(c, T.Trace) and c.landed, c.refusal
    runs.append(c)
    shutil.rmtree(repo)
    for t in runs:
        again = RUN.replay(t.dir, root=tmp_path / "root", engines=engines())
        assert isinstance(again, T.Trace) and again.replay["identical"], (t.dir.name, getattr(again, "replay", again))


# ---------------------------------------------------------------------------
# Prompts, declarations, the static rules
# ---------------------------------------------------------------------------

def test_the_prompts_are_built_for_each_step_and_stay_lean():
    for system in (FP.READ_SYSTEM, FP.FOLD_SYSTEM, FP.CODE_SYSTEM, FP.README_SYSTEM, FP.CATEM_SYSTEM):
        assert len(system) < 2000
    v = lambda s: (Value("string", s), "0" * 64)  # noqa: E731
    msgs = FP.messages({}, {"fabulac": v("read"), "path": v("a.py"), "code": v("1| x = 1"), "outline": v("[]"),
                            "lines": v("1-1 of 1"), "terms": v("[]"), "elsewhere": v("[]"), "test": v("no")})
    assert msgs[0]["content"] == FP.READ_SYSTEM and "1| x = 1" in msgs[1]["content"]
    assert "enrich:" in msgs[1]["content"] and "raises: [{error" in msgs[1]["content"]
    assert FP.messages({}, {"text": v("x")}) is None
    assert FP.PROMPTS == {"derive": FP.messages, "tell": FP.messages}


def test_the_host_finds_the_engines_and_the_prompts_by_name():
    """enough/thym_host.py looks the code lane's modules up by name (`SIBLING_ENGINES`, `PROMPT_MODULES`): the
    engines join every run's, and the fabulac's builders stand in front of the host's own for derive and tell."""
    eng = H.engines(feed=None)
    assert eng["repo"] is RE.REPO and eng["syntax"] is RE.SYNTAX
    assert {"derive", "tell"} <= set(H.register_prompts())
    seen = []
    cp = H.ModelCoprocessor(lambda msgs, **kw: (seen.append(msgs) or "```python\nx = 1\n```", {"model": "m"}))
    cand = cp.complete({"move": "tell", "schema": {"format": "markdown"}},
                       {"fabulac": (Value("string", "code"), ""), "path": (Value("string", "a.py"), ""),
                        "name": (Value("string", "t"), ""), "brief": (Value("string", "{}"), ""),
                        "atem": (Value("string", "{}"), "")}, budget={})
    assert seen[0][0]["content"] == FP.CODE_SYSTEM and cand["output"] == "x = 1\n"
    assert cp.messages({"move": "tell", "schema": {"format": "yaml"}},
                       {"outline": (Value("string", "- [P:claim/a] a"), ""), "order": (Value("string", "told"), "")}
                       )[0]["content"] != FP.CODE_SYSTEM


def test_the_declarations_keep_thym_0s_view_and_add_thym_1s():
    from enough.thym import declarations as D
    decls = D.load()
    assert decls["survey"].view(0) is None and decls["history"].view(0) is None
    assert decls["derive"].view(0).contract[-2] == "emf-checks" and decls["derive"].view(0).takes == (("text",),)
    d1, t1 = decls["derive"].view(1), decls["tell"].view(1)
    assert D.chosen(d1, as_word="code")["contract"] == ("code-span", "outline-cited", "coverage", "terms-grounded",
                                                         "stance-closed", "fabula-checks", "provenance")
    assert D.chosen(d1, first_type="folder")["contract"][0] == "fold-grounded"
    assert D.chosen(t1, as_word="code")["gives"] == ("folder",)
    assert D.chosen(t1, as_word="manual")["scaffold"] == "uses-outline"
    for name in ("files-found", "code-span", "licence-recorded", "outline-cited", "fold-grounded", "history-grounded",
                 "parses", "interfaces-present", "files-present", "uses-told", "flavour"):
        assert C.CHECKS.lookup(name) is not None, name


def test_the_shipped_programs_are_the_texts_and_compile_and_plan(tmp_path):
    blocks = _text_blocks()
    assert DECOMPILE.read_text(encoding="utf-8") in blocks and COMPILE.read_text(encoding="utf-8") in blocks
    copy_tiny(tmp_path)
    for program in STAGES:
        rows = [{"name": "repo", "type": "folder", "path": str(TINY)},
                {"name": "f", "type": "fabula", "path": str(SUITE / "inputs" / "notes.md.cosm"), "sha256": "0" * 64}]
        c = thym.check_file(DECOMPILE)
        p = pl.plan(c, [r for r in rows if r["name"] in ("repo", "f")][: 1 if program == STAGES[0] else 2]
                    if program != STAGES[-1] else rows[1:], program=program)
        assert not isinstance(p, Refusal), (program, p)
    assert not isinstance(thym.check_file(COMPILE), Refusal)
    assert os.path.getsize(DECOMPILE) > 0


def _text_blocks() -> list[str]:
    """Every ```thym block of the synced text, docs/THYM.md, as a program file holds it."""
    import re as _re
    text = (Path(__file__).resolve().parents[1] / "docs" / "THYM.md").read_text(encoding="utf-8")
    return [b for b in _re.findall(r"^```thym\n(.*?)^```", text, _re.S | _re.M)]


# ---------------------------------------------------------------------------
# Real code (lane G1): what three real repositories taught survey and history
# ---------------------------------------------------------------------------

def _pkg(tmp_path: Path) -> Path:
    repo = tmp_path / "pkg-tool"
    (repo / "src" / "pkg").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "docs").mkdir()
    (repo / "src" / "pkg" / "__init__.py").write_text(
        '"""A package."""\n__all__ = ("Cache", "make")\nfrom typing import Literal\n'
        'Kind = Literal["a", "b"]\n'
        'class _Base:\n    @property\n    def timer(self):\n        return 1\n'
        'class Cache(_Base):\n    def get(self, key):\n        return key\n'
        'def make(kind: Kind = "a"):\n    """Make one.\n\n    >>> make()\n    \'a\'\n    """\n    return kind\n')
    (repo / "src" / "pkg" / "_impl.py").write_text("def _helper(x):\n    return x\n\ndef _other():\n    pass\n")
    (repo / "tests" / "test_pkg.py").write_text("from pkg._impl import _helper\n\ndef test_h():\n    assert _helper(1)\n")
    (repo / "docs" / "conf.py").write_text('project = "pkg"\n')
    (repo / "LICENSE").write_text("MIT License\n\nCopyright (c) 2024 Ann Example (ann@example.com)\n\n"
                                  "Permission is hereby granted, free of charge, to any person\n")
    return repo


def test_survey_reads_what_a_caller_reaches_and_leaves_the_tooling_out(tmp_path):
    _pkg(tmp_path)
    t = run_stage(tmp_path, DECOMPILE, "survey-the-repo", [{"name": "repo", "type": "folder", "path": "pkg-tool"}])
    f = landed(t, "f")
    _data, items = fabula_of(f)
    # a private base whose methods a public class inherits, and a private name the tests import
    assert items["C:interface/pkg._Base"]["exported"] is False and "C:interface/pkg._Base.timer" in items
    assert items["C:interface/pkg._Base.timer"]["signature"] == "@property def timer(self)"
    assert "C:interface/pkg._impl._helper" in items and "C:interface/pkg._impl._other" not in items
    # a type alias a public signature names, the docstring and its doctest example, by rules
    assert items["C:structure/pkg.Kind"]["shape"] == 'a type alias: Literal["a", "b"]'
    assert items["C:behaviour/pkg.make.doc"]["does"].startswith("Make one.")
    assert items["P:case/pkg.make.example-1"]["given"] == {"calls": ["make()"]}
    assert items["P:case/pkg.make.example-1"]["expect"] == {"value": "'a'"}
    # the repository's own tooling is no part of the program; an address never reaches the licence's holder
    assert "C:component/docs.conf" not in items and not any(i.startswith("C:setting/docs") for i in items)
    assert items["R:licence/mit"]["holder"] == "Ann Example"
    assert not FAB.lint(f).errors


def test_a_value_split_at_an_unquoted_comma_is_refused():
    with pytest.raises(ValueError, match="a key with no value"):
        CODE.parse_fold(mc.yaml_load("atem: {line: a, focus: b, push: c, pull: d, cites: []}\n"
                                     "aims: [{slug: x, name: X, summary: Standard, HTML and more.}]\n"),
                        taken=set(), paths=set())


@pytest.mark.skipif(RE.git_binary() is None, reason="git is not installed here")
def test_history_places_a_tag_outside_the_log_by_its_release_commit_and_stays_small(tmp_path):
    repo = make_clone(tmp_path)
    git(repo, "checkout", "-q", "-b", "side")
    git(repo, "commit", "-q", "--allow-empty", "-m", "Release v0.3.0.", when="2026-10-20T09:00:00+00:00")
    git(repo, "tag", "v0.3.0", when="2026-10-20T09:00:00+00:00")
    git(repo, "checkout", "-q", "main")
    git(repo, "commit", "-q", "--allow-empty", "-m", "Release v0.3.0.", when="2026-10-21T09:00:00+00:00")
    t = run_stage(tmp_path, DECOMPILE, "survey-the-repo", [{"name": "repo", "type": "folder", "path": "tiny-tool"}])
    f = landed(t, "f")
    h = run_stage(tmp_path, DECOMPILE, "read-the-history", [{"name": "repo", "type": "folder", "path": "tiny-tool"},
                  {"name": "f", "type": "fabula", "path": str(f.relative_to(tmp_path))}])
    _data, items = fabula_of(landed(h))
    rel = items["R:release/v0-3-0"]
    assert "outside the history read" in rel["summary"] and rel.get("changes")
    change = items[rel["changes"][-1]]
    assert change["name"] == "Release v0.3.0." and change["nature"] == "build"
    assert all(it["began"] <= it["ended"] for it in items.values() if it["type"] == "phase")


# ---------------------------------------------------------------------------
# What seven readers met on real code (docs/fabula-landed-G3.md)
# ---------------------------------------------------------------------------

def _sib(tmp_path: Path) -> Path:
    """A package whose module imports siblings by their package's name, whose plug-ins import a helper beside them
    bare, typed in a stub, with its own [tool.<name>] table and an f-string help filled from a name."""
    repo = tmp_path / "sib-tool"
    (repo / "sib" / "plugins").mkdir(parents=True)
    (repo / "sib" / "__init__.py").write_text("")
    (repo / "sib" / "lines.py").write_text("def first(node):\n    return 1\n")
    (repo / "sib" / "noqa.py").write_text("def parse(code):\n    return {}\n")
    (repo / "sib" / "core.py").write_text(
        "import argparse\nfrom sib import lines, noqa\n\ndef keyed(a, b=2):\n    return a\n\n"
        "def main():\n    glob_help = 'Patterns may hold *.'\n    p = argparse.ArgumentParser(prog='sib')\n"
        "    p.add_argument('--exclude', help=f'Paths to skip. {glob_help}')\n"
        "    p.add_argument('--width', help=f'At most {WIDTH} wide.')\n    return lines.first(noqa.parse(p))\n")
    (repo / "sib" / "core.pyi").write_text("def keyed(a: int, b: int = ...) -> str: ...\n")
    (repo / "sib" / "plugins" / "__init__.py").write_text("")
    (repo / "sib" / "plugins" / "helper.py").write_text("class Helper:\n    pass\n")
    (repo / "sib" / "plugins" / "one.py").write_text("from helper import Helper\n\nHelper()\n")
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "sib-tool"\nversion = "1.2"\nrequires-python = ">=3.10"\ndependencies = ["toml>=0.10"]\n'
        '[project.optional-dependencies]\npint = ["pint"]\n\n[tool.sib-tool]\nexclude = ["build"]\n'
        'min_confidence = 70\n\n[build-system]\nrequires = ["setuptools"]\nbuild-backend = "setuptools.build_meta"\n')
    (repo / "LICENSE").write_text("MIT License\n\nCopyright (c) 2024 Ann Example\n")
    return repo


def test_survey_reads_siblings_stub_types_the_tools_table_and_a_filled_help(tmp_path):
    _sib(tmp_path)
    t = run_stage(tmp_path, DECOMPILE, "survey-the-repo", [{"name": "repo", "type": "folder", "path": "sib-tool"}])
    _data, items = fabula_of(landed(t, "f"))
    # `from sib import lines, noqa` is those two modules; a bare import of a module beside it is that module
    assert {"C:component/sib.lines", "C:component/sib.noqa"} <= set(items["C:component/sib.core"]["uses"])
    assert "C:component/sib" not in items["C:component/sib.core"]["uses"]
    assert items["C:component/sib.plugins.one"]["uses"] == ["C:component/sib.plugins.helper"]
    assert not any(i.startswith("C:dependency/helper") for i in items)
    # the stub's types reach the interface
    keyed = items["C:interface/sib.core.keyed"]
    assert [x.get("type") for x in keyed["takes"]] == ["int", "int"] and keyed["gives"] == {"type": "str"}
    assert "Typed in sib/core.pyi" in keyed["summary"]
    # the program's own [tool.<name>] table, as settings; the packaging file names its project
    tool = items["C:setting/pyproject.tool.sib-tool.min-confidence"]
    assert (tool["set-in"], tool["key"], tool["default"]) == ("file", "min_confidence", "70")
    assert items["C:file/pyproject-toml"]["holds"] == "packaging metadata of the project sib-tool, version 1.2, Python >=3.10"
    assert "declared in the optional group `pint`" in items["C:dependency/pint"]["summary"]
    # an f-string help filled from a name the file binds once; one no rule can fill says it is a template
    assert items["C:setting/option.sib.exclude"]["means"] == "Paths to skip. Patterns may hold *."
    assert items["C:setting/option.sib.width"]["means"].endswith("(an f-string: its {…} parts are filled in when "
                                                                 "the program runs)")
    assert not FAB.lint(landed(t, "f")).errors


def test_a_test_file_takes_cases_and_structures_and_a_bare_file_a_structure():
    with pytest.raises(ValueError, match="a test file takes cases, and structures .* also gives behaviours"):
        CODE.parse_reading("behaviours: [{name: x, summary: y, does: z, of: [C:component/a]}]", path="tests/t.py",
                           module="tests.t", n_lines=3, taken=set(), role="test")
    got = CODE.parse_reading("structures: [{slug: lock, name: A lock, summary: It counts., shape: a class}]",
                             path="tests/t.py", module="tests.t", n_lines=3, taken=set(), role="test")
    assert [i["id"] for i in got] == ["C:structure/tests.t.lock"]
    with pytest.raises(ValueError, match="no interface or component of its own"):
        CODE.parse_reading("behaviours: [{name: x, summary: y, does: z, of: [C:file/dev]}]", path="dev/r.py",
                           module="dev.r", n_lines=3, taken=set(), role="bare")
    assert CODE.read_role("tests/test_a.py", []) == "test" and CODE.read_role("dev/r.py", [{"id": "C:file/x"}]) == "bare"
    v = lambda s: (Value("string", s), "0" * 64)  # noqa: E731
    msgs = FP.messages({}, {"fabulac": v("read"), "path": v("tests/t.py"), "code": v("1| x = 1"), "role": v("test"),
                            "outline": v("[]"), "lines": v("1-1 of 1"), "elsewhere": v("[]"), "test": v("yes")})
    assert "write only cases" in msgs[1]["content"] and "behaviours:" not in msgs[1]["content"]
    assert "Terms the specification already has" not in msgs[1]["content"]       # no terms yet: no line
    assert "any value that is not a plain word or number" in msgs[1]["content"]


def test_a_component_is_covered_by_its_does_and_an_event_shows_ids():
    local = [{"id": "C:component/a", "type": "component", "does": {"pending": "what?"}},
             {"id": "C:interface/a.f", "type": "interface", "span": {"file": "a.py", "lines": "3-4"}}]
    assert CODE.uncovered(local, []) == ["C:component/a", "C:interface/a.f"]
    told = [{"id": "C:component/a", "does": "It counts."}]
    assert CODE.uncovered(local, told) == ["C:interface/a.f"]                     # enrich covers a component only
    assert CODE.uncovered(local, told + [{"id": "C:behaviour/a.f", "type": "behaviour", "of": ["C:interface/a.f"]}]) == []
    assert "agent: C:interface/pkg.mod.main" in FP.READ_SHAPE and "after: T:event/pkg.mod.read-file" in FP.READ_SHAPE
    assert "a component does; a setting means" in FP.READ_SYSTEM
    # a long file's parts: each covers the interfaces whose first line it holds; the component in the first only
    assert CODE.to_cover(local, "a.py", 1, 2, True) == ["C:component/a"]
    assert CODE.to_cover(local, "a.py", 3, 9, False) == ["C:interface/a.f"]


def _long_module(tmp_path: Path) -> Path:
    repo = copy_tiny(tmp_path)
    body = "".join(f"def f{i}(x):\n    return x + {i}\n\n" for i in range(4))
    (repo / "tiny" / "counting.py").write_text((repo / "tiny" / "counting.py").read_text() + "\n" + body)
    return repo


def test_a_coverage_fault_is_asked_again_only_of_the_part_that_holds_it(tmp_path, monkeypatch):
    """A long file is read in parts; the part whose lines hold an uncovered interface is asked again, with the
    current verdict, and the other part's answer is kept."""
    repo = _long_module(tmp_path)
    n = len((repo / "tiny" / "counting.py").read_text().splitlines())
    monkeypatch.setattr(CODE, "chunks_of", lambda text, size=600: [(1, 56), (57, n)])
    tail = ("behaviours:\n" + "".join(f"  - {{slug: f{i}, name: f{i}, summary: f{i} adds {i}., of: "
                                        f"[C:interface/tiny.counting.f{i}], does: Adds {i}., lines: \"{58 + 3 * i}\"}}\n"
                                        for i in range(4)))
    first = READ["tiny/counting.py"]
    calls = {"n": 0}
    told: list[str] = []

    def answer(inputs):
        if _t(inputs, "lines").startswith("1-"):
            calls["n"] += 1
            return first
        told.append(_t(inputs, "failed"))
        return tail if _t(inputs, "failed") else tail.split("  - {slug: f3")[0]
    cp = Scripted(answers({("read", "tiny/counting.py"): answer}))
    build(tmp_path, repo, cp, upto=3)
    asked = cp.asked("read", "tiny/counting.py")
    assert len(asked) == 3 and calls["n"] == 1                       # part 1 once; part 2 twice
    again = [c for s, k, c in cp.sent if k == "tiny/counting.py"][2]
    # the part asked again hears its own verdict, in its `failed` input, and not the whole list the runtime holds
    # (lane S3: `replaces`); the first asks of both parts are as they were
    assert "tiny.counting.f3" in told[-1] and again["repair"] == {"allowed": [], "failed": []}
    assert [c["repair"] for c in asked[:2]] == [{"allowed": [], "failed": []}] * 2


def test_what_a_file_reaches_elsewhere_is_what_it_imports():
    items = [{"id": "C:file/a", "type": "file", "path": "p/a.py"}, {"id": "C:file/b", "type": "file", "path": "p/b.py"},
             {"id": "C:file/c", "type": "file", "path": "p/c.py"},
             {"id": "C:component/p.a", "type": "component", "name": "p.a", "files": ["C:file/a"]},
             {"id": "C:component/p.b", "type": "component", "name": "p.b", "files": ["C:file/b"]},
             {"id": "C:component/p.c", "type": "component", "name": "p.c", "files": ["C:file/c"]},
             {"id": "C:interface/p.b.go", "type": "interface", "name": "go", "defined-in": "C:file/b", "signature": "def go()"},
             {"id": "C:interface/p.b.stop", "type": "interface", "name": "stop", "defined-in": "C:file/b"},
             {"id": "C:interface/p.c.run", "type": "interface", "name": "run", "defined-in": "C:file/c"},
             {"id": "C:setting/p.b.LIMIT", "type": "setting", "key": "LIMIT", "name": "LIMIT", "default": "3",
              "span": {"file": "p/b.py", "lines": "1"}}]
    ol = {"ok": True, "imports": [{"module": "p.b", "names": ["go", "LIMIT"], "line": 1}]}
    got = CODE.elsewhere_of(items, "p/a.py", ol, test=False)
    assert [r["id"] for r in got] == ["C:interface/p.b.go", "C:setting/p.b.LIMIT"]
    whole = {"ok": True, "imports": [{"module": "p", "names": ["c"], "line": 1}]}
    items.append({"id": "C:component/p", "type": "component", "name": "p", "files": []})
    assert [r["id"] for r in CODE.elsewhere_of(items, "p/a.py", whole, test=False)] == ["C:interface/p.c.run"]


def test_the_fold_cuts_documents_at_a_line_reference_before_the_change_log(tmp_path, monkeypatch):
    repo = tmp_path / "docs-tool"
    (repo / "docs").mkdir(parents=True)
    (repo / "README.md").write_text("# t\n\nA tool.\n")
    (repo / "CHANGELOG.md").write_text("".join(f"- change {i}\n" for i in range(400)))
    (repo / "docs" / "api.md").write_text("".join(f"The reference, line {i}.\n" for i in range(50)))
    from enough.thym import folder as FO
    monkeypatch.setattr(CODE, "DOC_BUDGET", 2000)
    text = CODE._documents(FO.read(repo), [])
    assert text.index("=== docs/api.md") < text.index("=== CHANGELOG.md")
    assert re.search(r"\(… \d+ more lines of CHANGELOG.md not shown\)", text)
    assert all(ln.startswith(("===", "(", "")) or re.match(r"\s*\d+\| ", ln) for ln in text.split("\n"))


def test_the_fold_keeps_one_term_per_word():
    items = [{"id": "L:term/a.whitelist", "type": "term", "name": "whitelist", "sense": "A file of names.",
              "provenance": {"sources": ["a.py#L1"]}},
             {"id": "L:term/b.whitelist", "type": "term", "name": "Whitelist", "sense": "A module of uses.",
              "provenance": {"sources": ["b.py#L2"]}},
             {"id": "K:concept/x", "type": "concept", "defined-by": ["L:term/b.whitelist"]}]
    got = CODE.merge_terms(items)
    assert [i["id"] for i in got] == ["L:term/a.whitelist", "K:concept/x"]
    assert got[0]["sense"] == "A file of names. Also: A module of uses." and got[1]["defined-by"] == ["L:term/a.whitelist"]
    assert got[0]["provenance"]["sources"] == ["a.py#L1", "b.py#L2"]


def test_a_file_brief_carries_the_cases_of_the_work_it_does_and_what_it_calls():
    items = [{"id": "C:file/i", "type": "file", "path": "p/__init__.py"}, {"id": "C:file/w", "type": "file", "path": "p/_w.py"},
             {"id": "C:component/p", "type": "component", "name": "p", "files": ["C:file/i"]},
             {"id": "C:component/p._w", "type": "component", "name": "p._w", "files": ["C:file/w"]},
             {"id": "C:interface/p.cached", "type": "interface", "name": "cached", "defined-in": "C:file/i",
              "signature": "def cached(cache)"},
             {"id": "C:interface/p._w._wrapper", "type": "interface", "name": "_wrapper", "defined-in": "C:file/w",
              "signature": "def _wrapper(func)"},
             {"id": "C:behaviour/p.cached-deco", "type": "behaviour", "of": ["C:interface/p.cached"],
              "does": "Returns a decorator built by _wrapper from p._w."},
             {"id": "C:behaviour/p._w.locked", "type": "behaviour", "of": ["C:interface/p._w._wrapper"],
              "does": "Enters the lock twice on a miss; see `cached(`."},
             {"id": "P:case/t.lock-count", "type": "case", "of": ["C:interface/p.cached"], "given": {}, "expect": {}},
             {"id": "D:question/q1", "type": "question", "about": "C:behaviour/p._w.locked", "asks": "Why twice?",
              "state": "open"}]
    b = CODE.file_brief(items, items[1])
    ids = [x["id"] for x in b["items"]]
    assert "P:case/t.lock-count" in ids and len(ids) == len(set(ids))
    assert b["open questions"] == [{"about": "C:behaviour/p._w.locked", "asks": "Why twice?"}]
    assert [e["id"] for e in b["elsewhere"]] == ["C:interface/p.cached"] and b["elsewhere"][0]["does"]
    # the README's request follows its format, and asks for typed commands only of a program that has some
    v = lambda s: (Value("string", s), "0" * 64)  # noqa: E731
    rst = FP.messages({}, {"fabulac": v("readme"), "path": v("README.rst"), "name": v("p"), "brief": v("{}"),
                           "atem": v("{}"), "commands": v("no")})
    assert "reStructuredText" in rst[0]["content"] and "commands a user types" not in rst[0]["content"]


def test_a_catem_request_lists_every_item_it_may_cite():
    items = [{"id": "K:concept/budget", "type": "concept", "name": "budget"}, {"id": "N:use/u", "type": "use"},
             {"id": "C:structure/s", "type": "structure"}, {"id": "C:file/f", "type": "file"}]
    got = mc.yaml_load(CODE._catem_outline(items, "manual"))
    assert [i["id"] for i in got] == ["K:concept/budget", "N:use/u", "C:structure/s"]
