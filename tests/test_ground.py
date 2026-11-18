"""The ground (0.8, transconception phase 2; MacroCOSM OES 18.4.9, Thym 20.10): the language registry
(`enough/languages.py`), Python's ground catalogue (`defaults/cosm/ground/python.ground.cosm`), the survey's new rules
in `enough/repo_engine.py` (`uses`, `locks`, `swhid`, `catalogue`) and the move `ground repo with f`
(`enough/thym/moves/transconceive.py`).

The source trees are read as text and never run: tally's fixture here, and the experiment's two clones in
fabulac-test-repos when they are on this machine (the tests that need them skip otherwise). Nothing in them is
imported, executed or installed.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from enough import fabula as FAB
from enough import fabulac_job as FJ
from enough import languages as L
from enough import macrocosm as mc
from enough import repo_engine as RE
from enough import thym
from enough import thym_host as H
from enough import transconception as tc
from enough.thym import Refusal
from enough.thym import contracts as ct
from enough.thym import declarations as dc
from enough.thym import folder as FO
from enough.thym import plan as pl
from enough.thym import run as RUN
from enough.thym.moves import transconceive as TR
from enough.thym.values import digest_path

REPO = Path(__file__).resolve().parents[1]
FIX = REPO / "tests" / "fixtures" / "fabula"
TALLY = FIX / "tally"
TALLY_FABULAC = FIX / "tally.fabulac.cosm"
PROMOTED = FIX / "transconception"
CLONES = Path("/Users/m3u/METMcloud/fabulac-test-repos")
DOCS = CLONES / "_x0" / "library" / "python" / "3.13"
LIBRARY_JSON = REPO / "tests" / "fixtures" / "languages" / "library.json"
DECOMPILE = REPO / "defaults" / "thym" / "decompile-python.thym"
NOW = dt.datetime(2026, 11, 18, 12, 0, tzinfo=dt.timezone.utc)

needs_clones = pytest.mark.skipif(not (CLONES / "vulture" / "vulture").is_dir()
                                  or not (CLONES / "sloppy-xml-py" / "sloppy_xml.py").is_file(),
                                  reason="the experiment's clones are not on this machine")


def entries() -> dict[str, dict]:
    return {e["id"]: e for e in L.entries("python")}


def uses_of(root: Path) -> dict[str, dict]:
    """Every Python file's uses, tooling left out, as the move asks for them (read as text, never run)."""
    f = FO.read(root)
    return {e.path: RE.uses(e.path, f.text(e.path)) for e in f.texts()
            if e.path.endswith((".py", ".pyi")) and not TR.is_tooling(e.path)}


def ground(fabulac: Path, root: Path) -> tuple[dict, list[dict], dict]:
    data = mc.yaml_load(fabulac.read_text(encoding="utf-8"))
    cat = {k: v for k, v in data.items() if k != "nodes"}
    f = FO.read(root)
    locks = {e.path: RE.locks(e.path, f.text(e.path)) for e in f.texts() if TR._lock_file(e.path)}
    return TR.ground_fabula(cat, data["nodes"], uses_of(root), RE.catalogue(cat["source"]["language"]), locks=locks,
                            swhid=RE.swhid(root))


def volume(cat: dict, items: list[dict], name: str = "x.fabulac.cosm") -> mc.Volume:
    return mc.load_volume_text(mc.dump({**cat, "nodes": items}), filename=name)


def stands_alone(cat: dict, items: list[dict]) -> list[tuple]:
    found: list[tuple] = []
    tc._Checks(volume(cat, items), lambda c, it, m, f=None, severity=None: found.append(
        (getattr(it, "id", None), f, m))).stands_alone()
    return found


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------

def test_python_reads_runs_parses_and_has_its_ground_and_programs():
    py = L.require("python")
    assert (py.reads, py.parses, py.runs, py.target) == (True, True, True, True)
    assert py.ground_path is not None and py.ground_path.is_file()
    assert (REPO / "defaults" / "thym" / py.decompile).is_file() and (REPO / "defaults" / "thym" / py.compile).is_file()
    assert L.program("python", "decompile") == "decompile-python.thym" == FJ.PROGRAM_FILE
    assert L.program("Python", "compile") == "compile-python.thym" == FJ.COMPILE_FILE
    assert L.DEFAULT == "python" and L.reading() == ["python"] and py.owns("a/b.py") and py.owns("x.pyi")


def test_go_and_rust_are_weighed_and_entailed_into_and_read_nothing():
    for name, suffix in (("go", "go"), ("rust", "rs")):
        lang = L.require(name)
        assert lang.target and not (lang.reads or lang.parses or lang.runs)
        assert lang.ground is None and lang.decompile is None and lang.compile is None and lang.names is None
        assert L.of_path(f"cmd/main.{suffix}") is lang and RE.language(f"x.{suffix}") == name
        assert RE.parse(f"x.{suffix}", "package main")["ok"] is None
        assert RE.outline(f"x.{suffix}", "fn main() {}")["ok"] is None
        assert RE.uses(f"x.{suffix}", "fn main() {}")["ok"] is None
        assert RE.catalogue(name)["ok"] is None
        with pytest.raises(KeyError, match="no program decompiles"):
            L.program(name, "decompile")
        with pytest.raises(KeyError, match="no ground catalogue"):
            L.catalogue(name)
    assert set(L.targets()) == {"python", "go", "rust"}
    with pytest.raises(KeyError, match="no language this build knows"):
        L.require("cobol")
    assert L.get("cobol") is None and not L.reads("cobol")


def test_the_names_stands_alone_reads_and_the_kinds_it_skips_are_the_registrys():
    assert tc.SOURCE_NAMES["python"] is L.source_names("python") and set(tc.SOURCE_NAMES) == {"python"}
    assert TR._SKIP_MODULES == tc.STANDS_ALONE_SKIP_MODULES and TR._SKIP_KINDS == tc.STANDS_ALONE_SKIP_KINDS


def test_the_suffix_tables_are_the_registrys_where_they_were_a_pure_move():
    assert {s: n for s, n in RE.LANGUAGES.items() if n in L.LANGUAGES} == L.suffixes()
    assert RE.language("a.py") == "python" and RE.language("a.toml") == "toml" and RE.language("Makefile") == "text"


# ---------------------------------------------------------------------------
# The catalogue
# ---------------------------------------------------------------------------

PAPER = ("whole-numbers-unbounded", "halves-round-to-even", "number-from-text", "text-length-in-code-points",
         "text-order-by-code-point", "what-is-a-space", "lines-end-at", "json-written", "json-read", "number-as-text",
         "argparse-surface", "uncaught-error", "home-and-tilde", "append-is-whole")
X0 = [f"V-R{i:02d}" for i in range(1, 34)] + [f"S-R{i:02d}" for i in (1, 2, 3, 4, 6, 7, 9, 10, 11, 12, 13, 15, 17,
                                                                     18, 19, 20, 21, 22)]


def test_the_catalogue_lints_and_every_entry_is_stated():
    doc = L.catalogue("python")
    assert L.lint_catalogue(doc) == []
    es = list(entries().values())
    assert 60 <= len(es) <= 100
    for e in es:
        assert e["stated"] and all(set(s) in ({"nowhere"}, {"in", "version", "at", "digest"}) for s in e["stated"])
        assert e["gives"].strip() and e["example"].strip() and e["shows-as"], e["id"]
    assert set(PAPER) <= set(entries())
    assert entries()["append-is-whole"]["kind"] == "assumption"


def test_every_reliance_the_experiment_wrote_is_an_entry_of_the_catalogue():
    froms = {f for e in entries().values() for f in e.get("from") or []}
    assert set(X0) <= froms, sorted(set(X0) - froms)
    assert "paper" in froms


def test_a_lint_finds_what_is_wrong_with_an_entry():
    doc = json.loads(json.dumps(L.catalogue("python")))
    e = doc["entries"][0]
    e["stated"] = [{"in": "python", "version": "3.12.1", "at": "library/x.html#y", "digest": "abc"}]
    e["shows-as"] = [{"calls": "int"}]
    doc["entries"].append(dict(doc["entries"][1]))
    probs = L.lint_catalogue(doc)
    assert any("a text the head does not carry" in p for p in probs)
    assert any("twelve hex digits" in p for p in probs)
    assert any("names no condition calls" in p for p in probs)
    assert any("the id is given twice" in p for p in probs)


def test_the_catalogues_head_agrees_with_the_library():
    lib = json.loads(LIBRARY_JSON.read_text(encoding="utf-8"))
    doc = L.catalogue("python")
    assert L.catalogue_agrees(doc, lib) == []
    # the docs are not aboard yet (the owner's fetch adds them): the head says so
    assert [t["aboard"] for t in doc["texts"]] == [False]
    bad = json.loads(json.dumps(doc))
    bad["pins"][0]["name"] = "PyPy"
    bad["texts"][0]["aboard"] = True
    probs = L.catalogue_agrees(bad, lib)
    assert any("says name 'PyPy'" in p for p in probs) and any("aboard: false" in p for p in probs)


@pytest.mark.skipif(not DOCS.is_dir(), reason="the owner's 0.7 fetch of the 3.13 documentation is not here")
def test_every_citation_names_a_page_and_an_anchor_of_the_kept_text_with_its_digest():
    text = DOCS / "text" / "python-3.13-docs-text"
    html = DOCS / "html" / "python-3.13-docs-html"
    assert "Notable changes in 3.13.18" in (text / "contents.txt").read_text(encoding="utf-8")
    pages: dict[str, tuple[str, str]] = {}
    for e in entries().values():
        for s in e["stated"]:
            if "at" not in s:
                continue
            page, anchor = s["at"].split("#", 1)
            if page not in pages:
                pages[page] = (hashlib.sha256((text / (page[:-5] + ".txt")).read_bytes()).hexdigest()[:12],
                               (html / page).read_text(encoding="utf-8", errors="replace"))
            digest, body = pages[page]
            assert (s["in"], s["version"], s["digest"]) == ("python", "3.13.18", digest), (e["id"], s["at"])
            assert f'id="{anchor}"' in body, (e["id"], s["at"])


# ---------------------------------------------------------------------------
# The survey's new rules: uses, locks, swhid
# ---------------------------------------------------------------------------

def test_uses_reads_calls_forms_and_names_from_the_syntax():
    p = "tally/ledger.py"
    u = RE.uses(p, (TALLY / p).read_text(encoding="utf-8"))
    assert u["ok"] is True
    calls = {(c.get("name"), c.get("method")): c for c in u["calls"]}
    dumps = calls[("json.dumps", "dumps")]
    assert dumps["kw"] == ["sort_keys"] and dumps["in"] == "_append"
    assert calls[("path.open", "open")]["mode"] == "a"
    assert calls[("pathlib.Path.home", "home")]["in"] == "ledger_path"
    assert calls[("dataclasses.dataclass", None)]["kwv"] == {"frozen": "True"}
    forms = {f["form"] for f in u["forms"]}
    assert {"map", "set", "truth-test", "compare-in", "raise-from", "handler", "path-join"} <= forms
    assert "true-division" not in forms                        # `Path.home() / NAME` joins a path, it divides nothing
    assert {"name": "os.environ", "line": 31, "in": "ledger_path"} in u["attrs"]
    assert {h["name"] for h in u["handlers"]} == {"ValueError", "KeyError", "TypeError"}
    r = RE.uses("tally/render.py", (TALLY / "tally/render.py").read_text(encoding="utf-8"))
    assert {"true-division", "text-repeat", "f-string"} <= {f["form"] for f in r["forms"]}
    assert RE.uses("x.py", "def f(:\n")["ok"] is False


def test_uses_runs_nothing(tmp_path):
    canary = tmp_path / "ran"
    src = (f"import pathlib\npathlib.Path({str(canary)!r}).write_text('x')\n"
           f"if __name__ == '__main__':\n    open({str(canary)!r}, 'w')\n")
    u = RE.uses("m.py", src)
    assert u["ok"] and u["entry"] == 3 and not canary.exists()
    assert any(c.get("method") == "write_text" for c in u["calls"])


def test_locks_pin_versions_and_digests_without_running_anything():
    uv = ('version = 1\nrequires-python = ">=3.10"\n\n[[package]]\nname = "tally"\nversion = "0.2.0"\n'
          'source = { editable = "." }\n\n[[package]]\nname = "Click"\nversion = "8.1.7"\n'
          'source = { registry = "https://pypi.org/simple" }\n'
          'sdist = { url = "https://x/click.tar.gz", hash = "sha256:' + "a" * 64 + '" }\n')
    got = RE.locks("uv.lock", uv)
    assert got["ok"] and [p["package"] for p in got["packages"]] == ["Click"]
    assert got["packages"][0] == {"package": "Click", "version": "8.1.7", "line": 10, "digest": "sha256:" + "a" * 64,
                                  "address": "https://pypi.org/project/click/"}
    req = RE.locks("requirements.txt", "attrs==23.1.0 \\\n    --hash=sha256:" + "b" * 64 + "\nrich>=13\n")
    assert [(p["package"], p["version"], p["digest"][-4:]) for p in req["packages"]] == [("attrs", "23.1.0", "bbbb")]
    assert RE.locks(".python-version", "3.13.11\n")["runtime"] == "3.13.11"
    assert RE.locks("setup.py", "")["ok"] is None and RE.locks("uv.lock", "[[")["ok"] is False


@pytest.mark.skipif(RE.git_binary() is None, reason="git is not installed here")
def test_swhid_is_the_tree_git_makes_of_the_same_files(tmp_path):
    root = tmp_path / "t"
    shutil.copytree(TALLY, root)
    (root / "tally" / "run.sh").write_text("#!/bin/sh\necho\n")
    (root / "tally" / "run.sh").chmod(0o755)
    (root / "link").symlink_to("README.md")
    git = RE.git_binary()
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t",
           "GIT_AUTHOR_EMAIL": "t@t.t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t.t"}
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "x"]):
        subprocess.run([git, *args], cwd=root, env=env, check=True, capture_output=True)
    want = subprocess.run([git, "rev-parse", "HEAD^{tree}"], cwd=root, env=env, check=True, capture_output=True,
                          text=True).stdout.strip()
    got = RE.swhid(root)
    assert got["ok"] and got["dir"] == f"swh:1:dir:{want}"
    assert RE.swhid(root / "nope")["ok"] is False


def test_the_syntax_engine_hands_a_move_the_catalogue_whole():
    got = RE.catalogue("python")
    assert got["ok"] and got["language"] == {"name": "python", "title": "Python", "runtime": "python",
                                             "suffixes": ["py", "pyi"]}
    assert got["catalogue"] == json.loads(json.dumps(L.catalogue("python")))


# ---------------------------------------------------------------------------
# Ground on tally: every reliance the 2026-11-05 trial's writers had to know
# ---------------------------------------------------------------------------

#: What the trial's two writers (docs/fabula-survey-migration-trial.md, "The writers' notes") had to know, as the
#: catalogue entry that says it: section 3 ("Assumed knowledge") of each, item by item.
TALLY_NEEDS = {
    "argparse-surface": ["TS 3.1", "TS 3.2", "TS 3.3", "TS 3.4", "TS 3.5", "TS 3.6", "TS 3.9", "SW 3.1", "SW 3.2",
                         "SW 3.7", "SW 3.8", "SW 3.11"],
    "argparse-negative-numbers": ["TS 3.7", "SW 3.6"],
    "argparse-abbreviation": ["TS 3.8", "SW 3.10"],
    "argparse-optional-positional": ["TS 3.10", "SW 3.9"],
    "argparse-help": ["TS 3.11", "TS 3.13", "SW 3.3", "SW 3.4"],
    "argparse-version": ["TS 3.12", "SW 3.4"],
    "argparse-subcommands": ["SW 3.5", "SW 3.12"],
    "number-from-text": ["TS 3.14", "SW 3.13"],
    "printed-form": ["TS 3.5", "SW 3.14"],
    "json-written": ["TS 3.15", "SW 3.15"],
    "json-keys-sorted": ["TS 3.15", "SW 3.15"],
    "number-as-text": ["TS 3.16", "SW 3.17"],
    "halves-round-to-even": ["TS 3.17", "SW 3.19"],
    "division-gives-fraction": ["SW 3.19"],
    "what-is-a-space": ["TS 3.18", "SW 3.20"],
    "text-length-in-code-points": ["TS 3.19", "SW 3.22"],
    "text-order-by-code-point": ["TS 3.20", "SW 3.22"],
    "home-and-tilde": ["TS 3.21", "SW 3.23"],
    "path-written": ["TS 3.22", "SW 3.23"],
    "clock-seconds": ["TS 3.23", "SW 3.18"],
    "newlines-translated": ["TS 3.24", "SW 3.21"],
    "lines-end-at": ["SW 3.21"],
    "json-read": ["TS 3.25", "SW 3.16"],
    "uncaught-error": ["TS 3.26", "SW 3.25"],
    "make-folders": ["TS 3.27", "SW 3.24"],
    "file-created-mode": ["SW 3.24"],
    "format-spec": ["TS 3.28"],
    "print-line-end": ["TS 3.29", "SW 3.27"],
    "output-encoding": ["TS 3.29", "SW 3.27"],
    "exit-status-from-return": ["SW 3.26"],
    "run-as-module": ["SW 3.26"],
    "program-arguments": ["SW 3.28"],
    "append-is-whole": ["SW 3.29"],
    # what their sections 1 and 2 (silent, Python-shaped) left them to guess, and that the source shows
    "whole-numbers-unbounded": ["TS 1.11", "SW 1.10", "SW 1.34"],
    "fractions-are-doubles": ["SW 1.29"],
    "conversions": ["TS 1.22", "SW 1.17"],
    "text-decoding-strict": ["TS 1.26", "SW 1.21", "SW 1.22"],
    "path-kinds": ["SW 1.23"],
    "map-keeps-order": ["TS 2.10", "SW 2.14"],
    "records-compare-by-fields": ["TS 2.5", "SW 2.8"],
    "environment-read": ["TS 2.6", "SW 2.11"],
    "error-text": ["TS 2.4", "SW 2.6"],
    "runtime-version": ["TS 2.19", "SW 2.1"],
}


def test_every_assumed_knowledge_of_the_trial_has_an_entry_that_says_where_it_came_from():
    notes = {f"{w} 3.{i}" for w in ("TS", "SW") for i in range(1, 30)}
    said = {n for ns in TALLY_NEEDS.values() for n in ns}
    assert notes <= said, sorted(notes - said)
    es = entries()
    for eid, ns in TALLY_NEEDS.items():
        assert eid in es, eid
        assert set(ns) <= set(es[eid].get("from") or []), (eid, sorted(set(ns) - set(es[eid].get("from") or [])))


def test_rules_raise_on_tally_every_reliance_the_trials_writers_had_to_know():
    cat, items, grounds = ground(TALLY_FABULAC, TALLY)
    raised = set(grounds["entries"])
    assert set(TALLY_NEEDS) <= raised, sorted(set(TALLY_NEEDS) - raised)
    by = {it["id"]: it for it in items}
    r = by["C:reliance/argparse-surface"]
    es = entries()
    assert {k: r[k] for k in TR.COPIED} == {k: es["argparse-surface"][k] for k in TR.COPIED}
    assert r["entry"] == "argparse-surface" and r["span"] == {"file": "tally/cli.py", "lines": "19"}
    assert "C:interface/command.tally" in r["used-by"] and "C:interface/tally.cli.main" in r["used-by"]
    a = by["P:assumption/append-is-whole"]
    assert a["checked"] == "no" and a["carries"] == "must" and "C:interface/tally.ledger.add" not in a.get(
        "relied-by", []) and a["relied-by"]
    # the trial's tally has no clone of its own and no lock: its runtime's address is pinned, nothing is resolved
    rt = by["C:dependency/python-standard-library"]
    assert rt["address"] == "https://github.com/python/cpython" and "resolved" not in rt
    assert cat["source"]["swhid"]["dir"].startswith("swh:1:dir:") and "rev" not in cat["source"]["swhid"]
    assert TR.cited_problems(cat, items) == []
    assert stands_alone(cat, items) == []
    # what the fixture held is all there, as it was (nothing lost), and a second grounding adds nothing
    old = mc.yaml_load(TALLY_FABULAC.read_text(encoding="utf-8"))["nodes"]
    from enough.thym.moves.edit import _within
    assert all(_within(o, by[o["id"]]) for o in old)
    cat2, items2, _ = TR.ground_fabula(cat, items, uses_of(TALLY), RE.catalogue("python"))
    assert len(items2) == len(items) and items2 == items
    assert FAB.lint(volume(cat, items)).ok


def test_a_reliance_nobody_cites_is_found_by_ground_cited_in_both_readings():
    cat, items, _ = ground(TALLY_FABULAC, TALLY)
    items = copy.deepcopy(items)
    r = next(it for it in items if it["id"] == "C:reliance/json-read")
    r["stated"] = []
    q = next(it for it in items if it["id"] == "C:reliance/json-written")
    del q["example"]
    probs = TR.cited_problems(cat, items)
    assert any("json-read.stated" in p for p in probs) and any("json-written: copied from" in p for p in probs)
    found: list = []
    tc._Checks(volume(cat, items), lambda c, it, m, f=None, severity=None: found.append(
        (getattr(it, "id", None), f))).ground_cited()
    assert ("C:reliance/json-read", "stated") in found


# ---------------------------------------------------------------------------
# Ground on the experiment's two repositories (their promoted fixtures, their clones read as text)
# ---------------------------------------------------------------------------

#: x0's reliances (V-R01..V-R33, S-R..), each as the catalogue entries that say it.
VULTURE_NEEDS = {
    "V-R01": ["path-written"], "V-R02": ["source-parsed"],
    "V-R03": ["argparse-surface", "program-arguments", "argparse-abbreviation", "argparse-help", "argparse-version"],
    "V-R04": ["number-from-text"], "V-R05": ["glob-case-per-platform"], "V-R06": ["glob-patterns"],
    "V-R07": ["glob-case-sensitive"], "V-R08": ["toml-read"], "V-R09": ["value-kinds"],
    "V-R10": ["literal-truth", "truth-of-values"], "V-R11": ["any-all-stop-early"], "V-R12": ["program-tree-nodes"],
    "V-R13": ["set-members"], "V-R14": ["text-order-by-code-point", "sort-is-stable", "text-case-mapping",
                                        "set-order-varies"],
    "V-R15": ["folder-walk", "path-resolved"], "V-R16": ["pattern-syntax", "pattern-flags"],
    "V-R17": ["what-is-a-space"], "V-R18": ["lines-end-at"], "V-R19": ["identifiers-normalised"],
    "V-R20": ["pattern-unicode-classes"], "V-R21": ["format-string-fields"], "V-R22": ["uncaught-error"],
    "V-R23": ["exit-with-message"], "V-R24": ["source-encodings"], "V-R25": ["error-text"],
    "V-R26": ["parser-messages"], "V-R27": ["type-comments"], "V-R28": ["package-data"], "V-R29": ["path-kinds"],
    "V-R30": ["tree-dump"], "V-R31": ["path-relative"], "V-R32": ["output-encoding"],
    "V-R33": ["exit-status-whole-number"],
}
SLOPPY_NEEDS = {
    "S-R01": ["pattern-syntax", "pattern-flags"], "S-R02": ["pattern-unicode-classes"], "S-R03": ["what-is-a-space"],
    "S-R04": ["text-indexed-by-code-point", "text-length-in-code-points"], "S-R06": ["pattern-syntax"],
    "S-R07": ["html5-entities"], "S-R09": ["whole-numbers-unbounded", "code-points-by-number"],
    "S-R10": ["code-points-by-number"], "S-R11": ["map-keeps-order", "text-replace"], "S-R12": ["map-keeps-order"],
    "S-R13": ["text-replace"], "S-R15": ["tree-text-and-tail"], "S-R17": ["bytes-decoded"],
    "S-R18": ["printed-form"], "S-R19": ["membership-identity-then-equality"],
    "S-R20": ["optional-library", "missing-key-error"], "S-R21": ["generators-lazy"],
    "S-R22": ["records-compare-by-fields"],
}
#: What W1-X1 found failing `stands-alone` in the promoted fixtures (docs/v080-landed-W1-X1.md, "For the ground
#: lane"), and the entry whose reliance now says it without the name.
STANDS_ALONE_FIXED = {
    "vulture": {"C:interface/vulture.config._parse_toml": "map-keeps-order",
                "C:interface/vulture.config._parse_args": "program-arguments",
                "C:interface/vulture.config.make_config": "program-arguments",
                "C:setting/vulture.core.PYTEST_FUNCTION_NAMES": "pytest-conventions",
                "C:setting/vulture.core.PYTEST_METHOD_NAMES": "pytest-conventions",
                "N:requirement/python-version": "runtime-version",
                "I:influence/pytest-conventions": "pytest-conventions"},
    "sloppy-xml-py": {"C:interface/x0.S-I3": "bytes-decoded"},
}


def test_the_needs_name_every_reliance_the_experiment_wrote():
    assert set(VULTURE_NEEDS) | set(SLOPPY_NEEDS) == set(X0)
    es = entries()
    for rid, eids in {**VULTURE_NEEDS, **SLOPPY_NEEDS}.items():
        assert any(rid in (es[e].get("from") or []) for e in eids), rid


@needs_clones
@pytest.mark.parametrize("name,needs", [("vulture", VULTURE_NEEDS), ("sloppy-xml-py", SLOPPY_NEEDS)])
def test_the_survey_raises_on_the_experiments_clones_what_its_writers_needed(name, needs):
    fab, root = PROMOTED / f"{name}.fabulac.cosm", CLONES / name
    data = mc.yaml_load(fab.read_text(encoding="utf-8"))
    assert mc.tree_digest(root)["tree"] == data["source"]["tree"]          # the clone the fixture was made from
    before = stands_alone({k: v for k, v in data.items() if k != "nodes"}, data["nodes"])
    assert {i for i, _f, _m in before} == set(STANDS_ALONE_FIXED[name])    # W1-X1's findings, held here too
    cat, items, grounds = ground(fab, root)
    want = {e for eids in needs.values() for e in eids}
    assert want <= set(grounds["entries"]), sorted(want - set(grounds["entries"]))
    # with ground applied, the items W1-X1 listed no longer fail stands-alone: each is used by the reliance that says it
    assert stands_alone(cat, items) == []
    by = {it["id"]: it for it in items}
    for iid, eid in STANDS_ALONE_FIXED[name].items():
        assert iid in by[f"C:reliance/{eid}"]["used-by"], (iid, eid)
    assert cat["source"]["swhid"]["rev"] == f"swh:1:rev:{data['source']['commit']}"
    assert TR.cited_problems(cat, items) == []
    # x0's own reliances and every other item stay as they were
    from enough.thym.moves.edit import _within
    assert all(_within(o, by[o["id"]]) for o in data["nodes"])
    # the gate: stands-alone holds now; what still stops ready-to-keep is that the new reliances are not yet ruled
    vol = volume(cat, items, f"{name}.fabulac.cosm")
    gate = tc.ready_to_keep(vol, source=root)
    assert gate["checks"]["stands-alone"]["state"] == "holds", gate["checks"]["stands-alone"]
    assert gate["checks"]["ground-cited"]["state"] == "holds", gate["checks"]["ground-cited"]
    assert not gate["holds"] and gate["checks"]["ruled"]["state"] != "holds"


# ---------------------------------------------------------------------------
# The move: declared since thym 1, run by Thym on a copy of tally, replayed without the folder
# ---------------------------------------------------------------------------

GROUND_PROGRAM = """thym 1

program ground-the-fabulac
  why: what the program leans on in its language is found by rule.
  must: nothing in the repository is run, imported or installed.

  takes repo: folder, f: fabula
  gives g: fabula

  give ground repo with f
end
"""


def test_ground_is_declared_since_thym_1_with_the_texts_contract():
    d = dc.load()
    g = d["ground"]
    assert g.since == 1 and d.view(0).get("ground") is None and g.owner == "fabula"
    assert list(g.contract) == ["ground-cited", "code-span", "nothing-lost", "fabula-checks", "provenance"]
    assert "ground-cited" in ct.AHEAD and "ground" in ct.AHEAD_MOVES


def _run(tmp_path: Path, prog: Path, program: str, rows: list[dict]):
    for r in rows:
        if r["type"] == "fabula":
            r["sha256"] = digest_path(tmp_path / r["path"])
    c = thym.check_file(prog)
    assert not isinstance(c, Refusal), str(c)
    p = pl.plan(c, rows, program=program)
    assert not isinstance(p, Refusal), str(p)
    return RUN.run(p, inputs_root=tmp_path, root=tmp_path / "root", program=prog, engines={
        **H.engines(feed=None), **RE.engines()}, now=NOW)


def test_the_move_grounds_a_survey_and_replays_without_the_folder(tmp_path):
    repo = tmp_path / "tally"
    shutil.copytree(TALLY, repo)
    t = _run(tmp_path, DECOMPILE, "survey-the-repo", [{"name": "repo", "type": "folder", "path": "tally"}])
    assert t.landed, getattr(t, "refusal", t)
    f = sorted((t.dir / "outputs").glob("f.*"))[0]
    prog = tmp_path / "ground.thym"
    prog.write_text(GROUND_PROGRAM, encoding="utf-8")
    g_run = _run(tmp_path, prog, "ground-the-fabulac", [{"name": "repo", "type": "folder", "path": "tally"},
                                                        {"name": "f", "type": "fabula",
                                                         "path": str(f.relative_to(tmp_path))}])
    assert g_run.landed, getattr(g_run, "refusal", g_run)
    checks = g_run.records[-1]["checks"]
    assert all(c["ok"] for c in checks), checks
    assert {c["name"] for c in checks} >= {"ground-cited", "code-span", "nothing-lost", "fabula-checks", "provenance"}
    g = sorted((g_run.dir / "outputs").glob("g.*"))[0]
    data = mc.yaml_load(g.read_text(encoding="utf-8"))
    rel = {it["entry"]: it for it in data["nodes"] if it.get("type") == "reliance"}
    # the survey alone knows no release of the runtime (tally names none in a packaging file): runtime-version waits
    # for the fold, which reads it from the README; the assumption is a P:assumption, not a reliance
    survey_needs = set(TALLY_NEEDS) - {"append-is-whole", "runtime-version"}
    assert survey_needs <= set(rel), sorted(survey_needs - set(rel))
    assert rel["json-written"]["of"] == "C:dependency/python" and rel["whole-numbers-unbounded"]["of"] == "R:means/python"
    assert data["source"]["swhid"]["dir"] == RE.swhid(repo)["dir"]
    assert re.fullmatch(r"swh:1:dir:[0-9a-f]{40}", data["source"]["swhid"]["dir"])
    assert FAB.lint(g).ok
    shutil.rmtree(repo)
    again = RUN.replay(g_run.dir, inputs_root=tmp_path, root=tmp_path / "root", engines={
        **H.engines(feed=None), **RE.engines()})
    assert again.replay["identical"], again.replay


def test_ground_refuses_a_folder_that_is_not_the_one_surveyed(tmp_path):
    repo = tmp_path / "tally"
    shutil.copytree(TALLY, repo)
    t = _run(tmp_path, DECOMPILE, "survey-the-repo", [{"name": "repo", "type": "folder", "path": "tally"}])
    f = sorted((t.dir / "outputs").glob("f.*"))[0]
    (repo / "tally" / "extra.py").write_text("X = 1\n", encoding="utf-8")
    prog = tmp_path / "ground.thym"
    prog.write_text(GROUND_PROGRAM, encoding="utf-8")
    g_run = _run(tmp_path, prog, "ground-the-fabulac", [{"name": "repo", "type": "folder", "path": "tally"},
                                                        {"name": "f", "type": "fabula",
                                                         "path": str(f.relative_to(tmp_path))}])
    assert not g_run.landed
    assert "is not the folder f was surveyed from" in json.dumps(g_run.records, ensure_ascii=False)
