"""Thym's `run` (Thym 6.3, 7.3, 20.12): an authored fabulac's entailment run by the host's sandbox, its report, the
checks `only-authored` and `in-sandbox`, the refusals in the text's words, and a replay that runs nothing.

The real runs start under /usr/bin/sandbox-exec on this Mac and skip elsewhere, as tests/test_sandbox.py's do; the
refusals and the replay's second half need no box. Everything lands in pytest's tmp_path (conftest moves the Thym
root and with it the sandbox's run folders).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import os
import shutil
import sys
import textwrap
from pathlib import Path

import pytest

from enough import macrocosm as mc
from enough import sandbox as sb
from enough import thym
from enough import thym_sandbox as TS
from enough.thym import Refusal
from enough.thym import plan as pl
from enough.thym import run as RUN
from enough.thym import trace as T
from enough.thym.contracts import BEHIND_MOVES
from enough.thym.folder import read as read_folder
from enough.thym.moves import run_entailment as RE
from enough.thym.values import Value

NOW = dt.datetime(2026, 11, 19, 12, 0, tzinfo=dt.timezone.utc)
MAC = sys.platform == "darwin" and os.access("/usr/bin/sandbox-exec", os.X_OK)
needs_box = pytest.mark.skipif(not MAC, reason="the sandbox runs here only on macOS with sandbox-exec")

MAIN = '''import sys


def main(argv):
    print(" ".join(argv) or "nothing")
    return 0


raise SystemExit(main(sys.argv[1:]))
'''

TESTS = '''import unittest


class Cases(unittest.TestCase):
    def test_adds(self):
        self.assertEqual(1 + 1, 2)

    def test_is_wrong(self):
        """A case the program does not meet yet."""
        self.assertEqual(1 + 1, 3)

    @unittest.skip("not this one")
    def test_skipped(self):
        pass
'''

PROGRAMS = '''thym 1

program test-the-entailment
  why: an authored fabulac's entailment is judged by its cases: its tests run in the host's sandbox.

  takes code: folder
  gives r: report

  give run code as tests
end

program start-the-tool
  why: the person starts the program they authored, with the arguments they give.

  takes code: folder
  gives r: report

  give run code as tool with ["count", "notes.md"]
end

program serve-it
  why: a service is specified and refused in this edition.

  takes code: folder
  gives r: report

  give run code as service
end
'''


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def project(tmp_path: Path, *, name: str = "tally", kind: str = "tool", source_kind: str = "authored",
            entailed_as: str | None = None, cshort: bool = False, fabulac: bool = True,
            record_missing: bool = False) -> Path:
    """A project holding `<name>/`, an entailment laid out as authored_code writes one, and `<name>.fabulac.cosm`
    beside it recording it (or not, as the arguments say)."""
    d = tmp_path / name
    (d / name).mkdir(parents=True)
    (d / name / "__init__.py").write_text("")
    (d / name / "__main__.py").write_text(MAIN)
    (d / "tests").mkdir()
    (d / "tests" / "__init__.py").write_text("")
    (d / "tests" / "test_cases.py").write_text(TESTS)
    (d / ("CSHORT.md" if cshort else "ENTAILED.md")).write_text("*an entailment*\n")
    (d / "pyproject.toml").write_text(textwrap.dedent(f"""
        [project]
        name = "{name}"
        version = "0.1.0"
        requires-python = ">=3.11"

        [tool.enough]
        kind = "{kind}"
        start = ["-m", "{name}"]
    """))
    if fabulac:
        files = [{"path": p.relative_to(d).as_posix(), "sha256": _sha(p)} for p in sorted(d.rglob("*"))
                 if p.is_file()]
        if record_missing:
            files.append({"path": "tally/gone.py", "sha256": "0" * 64})
        doc = {"oes": "fabula/1", "flavour": "fabulac", "id": f"fabula/{name}", "name": name,
               "source": {"kind": source_kind, "language": "python"},
               "program": {"kind": kind, "start": ["-m", name]},
               "entailed": {"path": entailed_as or f"{name}/", "files": files}}
        (tmp_path / f"{name}.fabulac.cosm").write_text(mc.dump(doc), encoding="utf-8")
    return d


def engines() -> dict:
    return {"sandbox": TS.thym_engine()}


def go(tmp_path: Path, program: str, folder: str = "tally", **kw):
    prog = tmp_path / "run-it.thym"
    prog.write_text(PROGRAMS, encoding="utf-8")
    c = thym.check_file(prog)
    assert not isinstance(c, Refusal), str(c)
    p = pl.plan(c, [{"name": "code", "type": "folder", "path": folder}], program=program, inputs_root=tmp_path)
    assert not isinstance(p, Refusal), str(p)
    kw.setdefault("engines", engines())
    return RUN.run(p, inputs_root=tmp_path, root=tmp_path / "root", program=prog, now=NOW, **kw)


def report(t) -> dict:
    assert isinstance(t, T.Trace) and t.landed, getattr(t, "refusal", t)
    out = sorted((t.dir / "outputs").glob("r.*"))
    assert out, sorted(x.name for x in (t.dir / "outputs").iterdir())
    return mc.yaml_load(out[0].read_text(encoding="utf-8"))


def refused(t) -> Refusal:
    r = t if isinstance(t, Refusal) else getattr(t, "refusal", None)
    assert isinstance(r, Refusal), t
    return r


# ---------------------------------------------------------------------------
# The declaration
# ---------------------------------------------------------------------------

def test_run_is_built_and_no_longer_behind():
    from enough.thym import declarations as dc
    assert "run" not in BEHIND_MOVES
    d = dc.load()["run"]
    assert d.takes == (("folder",),) and d.gives == ("report",) and d.asks is False
    assert d.modifiers == {"as": ("tests", "tool", "service"), "with": ("list of string",)}
    assert d.contract == ("only-authored", "in-sandbox", "provenance")
    assert d.view(0) is None and d.view(1) is not None


# ---------------------------------------------------------------------------
# Real runs, in the box
# ---------------------------------------------------------------------------

@needs_box
def test_run_as_tests_reports_each_verdict_and_lands_though_one_fails(tmp_path):
    project(tmp_path)
    t = go(tmp_path, "test-the-entailment")
    r = report(t)
    assert list(r)[:3] == ["as", "folder", "fabulac"]
    assert (r["as"], r["folder"], r["fabulac"]) == ("tests", "tally/", "tally.fabulac.cosm")
    assert "arguments" not in r
    assert r["exit"] == 1 and r["stopped"] is None and r["cut"] == []
    assert r["tests"] == [{"test": "tests.test_cases.Cases.test_adds", "verdict": "passed"},
                          {"test": "tests.test_cases.Cases.test_is_wrong", "verdict": "failed"},
                          {"test": "tests.test_cases.Cases.test_skipped", "verdict": "skipped"}]
    assert "FAILED" in r["error-output"]
    rows = r["sandbox"]["rows"]
    assert r["sandbox"]["by"] == "sandbox-exec" and list(rows) == list(RE.ROWS)
    assert all(rows[k]["enforced"] for k in RE.ROWS) and all(rows[k]["said"] for k in RE.ROWS)
    assert rows["limits"]["unenforced"] and "memory" in rows["limits"]["unenforced"][0]   # macOS: none promised
    assert isinstance(r["milliseconds"], int)
    checks = {c["name"]: c["ok"] for c in t.records[-1]["checks"]}
    assert checks == {"only-authored": True, "in-sandbox": True, "provenance": True}
    assert not any(sb.default_root().glob("*/work")), "the sandbox's run folder goes once the run is read"


@needs_box
def test_run_as_tool_with_arguments_and_an_empty_input(tmp_path):
    project(tmp_path)
    r = report(go(tmp_path, "start-the-tool"))
    assert (r["as"], r["arguments"], r["exit"]) == ("tool", ["count", "notes.md"], 0)
    assert r["output"] == "count notes.md\n" and "tests" not in r


@needs_box
def test_a_replay_reads_the_record_and_runs_nothing(tmp_path, monkeypatch):
    project(tmp_path)
    t = go(tmp_path, "start-the-tool")
    first = report(t)
    assert sorted(p.name for p in (t.dir / "candidates").glob("*-e*.1.cosm")) == ["1-e1.1.cosm", "1-e2.1.cosm"]

    def never(*a, **k):
        raise AssertionError("a replay ran the sandbox")
    monkeypatch.setattr(sb, "prepare", never)
    monkeypatch.setattr(TS, "run", never)
    shutil.rmtree(tmp_path / "tally")                      # nor does it need the folder or the fabulac
    (tmp_path / "tally.fabulac.cosm").unlink()
    again = RUN.replay(t.dir, inputs_root=tmp_path, root=tmp_path / "root", engines={})
    assert isinstance(again, T.Trace) and again.landed, getattr(again, "refusal", again)
    assert again.replay["identical"], again.replay
    assert report(again) == first


# ---------------------------------------------------------------------------
# Refusals: only-authored, before anything runs
# ---------------------------------------------------------------------------

@pytest.fixture
def no_running(monkeypatch):
    def never(*a, **k):
        raise AssertionError("a refused run reached the sandbox")
    monkeypatch.setattr(sb, "prepare", never)


def test_a_cshort_is_read_never_run(tmp_path, no_running):
    project(tmp_path, cshort=True)
    r = refused(go(tmp_path, "test-the-entailment"))
    assert (r.stage, r.check) == ("run", "only-authored")
    assert "cshort" in r.message and "read, never run" in r.message


def test_the_folder_a_fabulac_was_decompiled_from_is_read_never_run(tmp_path, no_running):
    project(tmp_path, source_kind="folder")
    r = refused(go(tmp_path, "start-the-tool"))
    assert r.check == "only-authored"
    assert "was not authored (its source.kind is folder)" in r.message and "read, never run" in r.message


def test_a_folder_with_no_fabulac_beside_it_is_read_never_run(tmp_path, no_running):
    project(tmp_path, fabulac=False)
    r = refused(go(tmp_path, "test-the-entailment"))
    assert r.check == "only-authored" and "there is no tally.fabulac.cosm beside tally" in r.message


def test_a_folder_not_the_one_entailed_records_is_refused(tmp_path, no_running):
    project(tmp_path, entailed_as="elsewhere/")
    r = refused(go(tmp_path, "test-the-entailment"))
    assert r.check == "only-authored" and "records its entailment as elsewhere/" in r.message
    shutil.rmtree(tmp_path / "tally")
    (tmp_path / "tally.fabulac.cosm").unlink()
    project(tmp_path, record_missing=True)
    r = refused(go(tmp_path, "test-the-entailment"))
    assert r.check == "only-authored" and "lacks tally/gone.py" in r.message


# ---------------------------------------------------------------------------
# Refusals: the host's sandbox
# ---------------------------------------------------------------------------

def test_a_host_with_no_sandbox_refuses_at_run_time(tmp_path, no_running):
    project(tmp_path)
    r = refused(go(tmp_path, "test-the-entailment", engines={}))
    assert r.check == "in-sandbox" and r.message.endswith(RE.NO_SANDBOX)


def test_serving_is_refused_in_this_edition(tmp_path, no_running):
    project(tmp_path, kind="service")
    r = refused(go(tmp_path, "serve-it"))
    assert r.check == "in-sandbox" and "comes in a later one" in r.message


def test_a_system_with_no_box_refuses_in_words(tmp_path, monkeypatch):
    project(tmp_path)
    monkeypatch.setattr(sb, "_platform", lambda: "plan9")
    r = refused(go(tmp_path, "test-the-entailment"))
    assert r.check == "in-sandbox" and "only on macOS and Linux" in r.message
    assert not any(sb.default_root().glob("*")) if sb.default_root().exists() else True


def test_a_need_outside_the_standard_library_is_named(tmp_path):
    d = project(tmp_path)
    (d / "tally" / "__main__.py").write_text("import requests\n")
    r = refused(go(tmp_path, "test-the-entailment"))
    assert r.check == "in-sandbox" and "requests" in r.message


# ---------------------------------------------------------------------------
# The rules alone
# ---------------------------------------------------------------------------

def test_unittest_verdicts_are_read_from_its_verbose_output():
    err = textwrap.dedent("""\
        test_a (tests.test_cases.Cases.test_a) ... ok
        test_b (tests.test_cases.Cases.test_b)
        What b checks. ... FAIL
        test_c (tests.test_cases.Cases) ... ERROR
        test_d (tests.test_cases.Cases.test_d) ... skipped 'later'
        test_e (tests.test_cases.Cases.test_e) ... expected failure

        ======================================================================
        FAIL: test_b (tests.test_cases.Cases.test_b)
        ----------------------------------------------------------------------
        Ran 5 tests in 0.001s
        """)
    assert sb.test_verdicts(err) == [
        {"test": "tests.test_cases.Cases.test_a", "verdict": "passed"},
        {"test": "tests.test_cases.Cases.test_b", "verdict": "failed"},
        {"test": "tests.test_cases.Cases.test_c", "verdict": "error"},
        {"test": "tests.test_cases.Cases.test_d", "verdict": "skipped"},
        {"test": "tests.test_cases.Cases.test_e", "verdict": "expected failure"}]


def test_in_sandbox_holds_every_row_and_a_box_that_held():
    rows = {k: {"enforced": True, "said": "held"} for k in RE.ROWS}
    good = {"sandbox": {"by": "bwrap", "rows": rows}}
    assert RE.in_sandbox_problem(good) is None
    assert "does not name" in RE.in_sandbox_problem({"sandbox": {"rows": rows}})
    short = {"sandbox": {"by": "bwrap", "rows": {k: v for k, v in rows.items() if k != "stop"}}}
    assert "enforced stop" in RE.in_sandbox_problem(short)
    weak = {"sandbox": {"by": "bwrap", "rows": {**rows, "no-network": {"enforced": False, "said": "no namespace"}}}}
    assert RE.in_sandbox_problem(weak) == "the box did not hold this run (no-network): no namespace"
    # a row held in part (memory, on macOS) is said, and holds
    part = {**rows, "limits": {"enforced": True, "said": "120 s", "unenforced": ["memory: not limited"]}}
    assert RE.in_sandbox_problem({"sandbox": {"by": "sandbox-exec", "rows": part}}) is None


def test_only_authored_by_rules(tmp_path):
    d = project(tmp_path)
    f = read_folder(d, path="tally")
    beside = TS.beside(Value("folder", f))
    assert beside["found"] and beside["source"] == {"kind": "authored"} and beside["entailed"]["path"] == "tally/"
    assert RE.only_authored_problem(f, beside) is None
    assert "not authored" in RE.only_authored_problem(f, {**beside, "source": {"kind": "clone"}})
    assert "records no entailment" in RE.only_authored_problem(f, {k: v for k, v in beside.items()
                                                                   if k != "entailed"})
    assert "run takes a folder" in RE.only_authored_problem(None, beside)
