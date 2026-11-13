"""Thym's in-page runtime (`enough/static/thym/`) held to the conformance suite under node (the 0.7 build, tracker
`thym-js-runtime`; THYM 12.6: a JavaScript runtime that passes the suite is a conforming runtime).

Every program of `tests/fixtures/thym/` runs under the page's runtime and under Python's (`run.run`, agent-free, the
same run id and clock), from what the page would be handed (`enough.thym.bundle.page_bundle`). A deterministic
program must land the same files byte for byte (and its `expected/<name>/outputs/`) with the same trace; a program
that asks a model must be refused at plan time with Python's words. Runs that refuse (an assert, a move that cannot
go on, a recursion past its depth, a changed input) must give the same refusal and the same trace. Skipped, with the
reason, where node is not on PATH.
"""
from __future__ import annotations

import base64
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from enough import macrocosm as mc
from enough.thym import Refusal, bundle, plan_file
from enough.thym import run as R
from enough.thym.conform import FIXTURE_NOW
from enough.thym.values import digest_path

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not on PATH: the page's runtime is held to the suite under node")

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "tests" / "fixtures" / "thym"
HARNESS = ROOT / "tests" / "thym_js_harness.js"
RID = "2026-11-01-1200-js00"


def _node(req: dict) -> dict:
    p = subprocess.run([NODE, str(HARNESS)], input=json.dumps(req), capture_output=True, text=True, timeout=120)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


def _plan(name: str) -> dict:
    return mc.yaml_load(mc.read_text(SUITE / "expected" / name / "plan.cosm"))


def _normal(trace: dict | None) -> dict | None:
    """A trace without what the wall clock writes: `ended`, and the seconds in the root item's one line."""
    if trace is None:
        return None
    t = json.loads(json.dumps(trace, default=str))
    t.pop("ended", None)
    for n in t.get("nodes") or []:
        if n.get("type") == "trace" and isinstance(n.get("summary"), str):
            n["summary"] = re.sub(r" (in|after) \d+ s", r" \1 N s", n["summary"])
    return t


def _both(plan: dict, inputs_root: Path, program, tmp: Path) -> tuple[dict, dict]:
    """The page's run and Python's of one plan, as `{outcome, refusal, trace, files}` each."""
    b = bundle.page_bundle(plan, inputs_root=inputs_root, program=program)
    js = _node({"bundle": b, "runId": RID, "now": FIXTURE_NOW.isoformat(), "inputsRoot": str(inputs_root)})
    js_out = {"outcome": js["outcome"], "refusal": js["refusal"],
              "trace": _normal(mc.yaml_load(js["traceText"])) if js["traceText"] else None,
              "files": {k: base64.b64decode(v) for k, v in js["files"].items()}}
    t = R.run(plan, inputs_root=inputs_root, root=tmp, program=program, record=False, now=FIXTURE_NOW, run_id=RID,
              agent_free=True)
    if isinstance(t, Refusal):
        py = {"outcome": "refused", "refusal": {"stage": t.stage, "check": t.check, "message": t.message,
                                                "line": t.line}, "trace": None, "files": {}}
    else:
        out = t.dir / "outputs"
        files = {"outputs/" + q.relative_to(out).as_posix(): q.read_bytes()
                 for q in sorted(out.rglob("*")) if q.is_file()} if out.is_dir() else {}
        r = t.refusal
        py = {"outcome": t.outcome, "files": files, "trace": _normal(mc.yaml_load(t.path.read_text(encoding="utf-8"))),
              "refusal": {"stage": r.stage, "check": r.check, "message": r.message, "line": r.line} if r else None}
    return js_out, py


def _programs() -> list[str]:
    return sorted(p.stem for p in (SUITE / "programs").glob("*.thym"))


def _asks(name: str) -> int:
    est = _plan(name).get("estimate") or {}
    return int(est.get("asks") or 0)


#: the deterministic programs the page cannot run, and why (THYM 20.6: `survey` reads syntax through an engine)
NEEDS_SERVER = {"survey-a-repo": "survey"}


@pytest.mark.parametrize("form", ["source", "volume"])
@pytest.mark.parametrize("name", _programs())
def test_the_suite_runs_the_same_in_the_page(name: str, form: str, tmp_path: Path) -> None:
    program = SUITE / "programs" / f"{name}.thym" if form == "source" else SUITE / "expected" / name / "items.cosm"
    js, py = _both(_plan(name), SUITE, program, tmp_path)
    if name in NEEDS_SERVER:
        assert js["refusal"]["stage"] == "plan" and js["refusal"]["check"] == "move"
        assert f"the move {NEEDS_SERVER[name]} has no implementation here" in js["refusal"]["message"]
        assert "run it on the server" in js["refusal"]["message"]
        return
    if _asks(name):
        # a model-backed program is never run in the page: the refusal agent-free gives, word for word
        assert js["refusal"] == py["refusal"] and js["refusal"]["check"] == "agent-free"
        assert js["trace"] is None and not js["files"]
        return
    assert js["outcome"] == py["outcome"] == "landed", (js["refusal"], py["refusal"])
    assert js["files"] == py["files"]
    want = SUITE / "expected" / name / "outputs"
    expected = {"outputs/" + q.relative_to(want).as_posix(): q.read_bytes() for q in want.rglob("*") if q.is_file()}
    assert expected and all(js["files"].get(k) == v for k, v in expected.items())
    assert js["trace"] == py["trace"]


@pytest.mark.parametrize("name", _programs())
def test_the_page_says_before_reading_inputs_whether_it_can_run_a_plan(name: str) -> None:
    """`ThymJS.planCheck`, what the page asks to offer "run here": the plan-time refusal the run would give for a step
    that asks or a move the page lacks, in the same words, and null for a plan the page runs."""
    src = (SUITE / "programs" / f"{name}.thym").read_text(encoding="utf-8")
    got = _node({"planCheck": {"plan": bundle.jsonable(_plan(name)), "program": src}})["refusal"]
    if name in NEEDS_SERVER:
        assert got["check"] == "move" and f"the move {NEEDS_SERVER[name]} has no implementation here" in got["message"]
    elif _asks(name):
        b = bundle.page_bundle(_plan(name), inputs_root=SUITE, program=SUITE / "programs" / f"{name}.thym")
        assert got == _node({"bundle": b, "runId": RID})["refusal"] and got["check"] == "agent-free"
    else:
        assert got is None


REFUSING = {
    "too-short": ("""thym 1

program too-short
  why: a text the program takes must be long.

  takes t: text
  gives n: number

  let k = words t
  assert k > 1000 else "the text is too short"
  give k
end
""", "assert"),
    "every-line-short": ("""thym 1

program every-line-short
  why: no line of the text runs past ten words.

  takes t: text
  gives n: number

  for each l in lines of t
    assert words l < 10
  end
  give count (lines of t)
end
""", "assert"),
    "dropped-twice": ("""thym 1

program dropped-twice
  why: every TODO line dropped, twice over.

  takes t: text
  gives clean: text

  let changes = for each l in lines of t where "TODO" in l
    keep drop l
    keep drop l
  end
  give edit t with changes
end
""", "move"),
    "too-deep": ("""thym 1

program too-deep
  why: a move that calls itself past the depth it says.

  takes t: text
  gives n: number

  move again(x: text, more: bool): number
    depth: 2
    if more then
      give again x, false
    else
      give again x, true
    end
  end

  give again t, true
end
""", "recursion"),
    "another-text": ("""thym 1

program another-text
  why: changes read from one text, applied to another.

  takes t: text
  gives s: short

  let changes = for each l in lines of t where "TODO" in l
    keep drop l
  end
  give edit (join (lines of t) with " ") with changes
end
""", "move"),
}


@pytest.mark.parametrize("name", sorted(REFUSING))
def test_a_run_that_refuses_refuses_the_same_in_the_page(name: str, tmp_path: Path) -> None:
    text, check = REFUSING[name]
    src = tmp_path / f"{name}.thym"
    src.write_text(text, encoding="utf-8")
    inputs = [{"name": "t", "type": "text", "path": "inputs/draft.md",
               "sha256": digest_path(SUITE / "inputs" / "draft.md")}]
    plan = plan_file(src, inputs)
    assert not isinstance(plan, Refusal), plan
    js, py = _both(plan, SUITE, src, tmp_path / "runs")
    assert py["outcome"] == "refused" and py["refusal"]["check"] == check, py["refusal"]
    assert js["refusal"] == py["refusal"]
    assert js["trace"] == py["trace"]
    assert not js["files"]


LANDING = {
    "editor-moves": ("""thym 1

program editor-moves
  why: every TODO line said again, a line put under the title, and the text's digest.

  takes t: text
  gives clean: text, sum: string

  let changes = for each l in lines of t
    if "TODO" in l then
      keep replace l with "done"
    end
    if l.number = 1 then
      keep insert "below the title" after l
    end
  end
  give clean: edit t with changes
  give sum: digest t
end
""", "t", "text", "inputs/draft.md"),
    "folder-moves": ("""thym 1

program folder-moves
  why: the folders directly below a folder, counted, and the words of its prose.

  takes repo: folder
  gives n: number, said: short

  let subs = folders of repo
  let sizes = for each d in repo where suffix is md
    keep say (words d)
  end
  give n: count subs
  give said: join sizes with " "
end
""", "repo", "folder", "inputs/little-tool"),
}


@pytest.mark.parametrize("name", sorted(LANDING))
def test_the_editor_moves_land_the_same_in_the_page(name: str, tmp_path: Path) -> None:
    text, iname, itype, ipath = LANDING[name]
    src = tmp_path / f"{name}.thym"
    src.write_text(text, encoding="utf-8")
    plan = plan_file(src, [{"name": iname, "type": itype, "path": ipath,
                            "sha256": digest_path(SUITE / ipath, itype)}])
    assert not isinstance(plan, Refusal), plan
    js, py = _both(plan, SUITE, src, tmp_path / "runs")
    assert py["outcome"] == "landed", py["refusal"]
    assert js["outcome"] == "landed", js["refusal"]
    assert js["files"] == py["files"]
    assert js["trace"] == py["trace"]


def test_a_changed_input_is_refused_at_plan_time_in_the_page(tmp_path: Path) -> None:
    plan = _plan("drop-the-todos")
    plan["inputs"][0]["sha256"] = "0" * 64
    js, py = _both(plan, SUITE, SUITE / "programs" / "drop-the-todos.thym", tmp_path)
    assert js["refusal"] == py["refusal"] and js["refusal"]["check"] == "input"


def test_the_page_dumps_as_macrocosm_does() -> None:
    """The canonical dump every digest is over (THYM 12.6), on the scalars PyYAML quotes, folds or escapes."""
    import datetime as dt
    long = "word " * 40 + "end"
    data = {"name": "x", "oes": "thym/1", "plain": "a plain string", "yes": "yes", "on": "on", "null": "null",
            "empty": "", "num": "123", "float": "1.5", "date": "2026-11-01", "colon": "a: b", "hash": "a #b",
            "lead": " lead", "trail": "trail ", "quote": "it's", "dq": '"quoted"', "tab": "a\tb", "nl": "line\nnext",
            "nl2": "end\n", "uni": "café —   ﻿", "long": long, "long_q": "'" + long,
            "long_nl": long + "\n" + long, "dash": "- item", "star": "*x", "bool": True, "none": None, "int": -7,
            "flt": 0.25, "when": dt.date(2019, 3, 1), "at": dt.datetime(2026, 11, 1, 12, 0, tzinfo=dt.timezone.utc),
            "list": [], "map": {}, "nested": {"a": [1, {"b": [], "c": [long]}], "7": "index-like key"},
            "rows": [{"k": "v", "w": ["x", "y"]}, ["deep", ["deeper"]]]}
    got = _node({"dump": bundle.jsonable(data)})["text"]
    assert got == mc.dump(data)


@pytest.mark.parametrize("program, check, words", [
    ("scan-the-poem", "move", "the move scan has no implementation here"),
    ("hear-the-poem", "move", "the move scan has no implementation here"),
    ("read-closely", "agent-free", "ask a model"),
])
def test_the_poems_programs_are_refused_in_the_page_with_the_reason(program: str, check: str, words: str,
                                                                    tmp_path: Path) -> None:
    """0.7: `scan` reads FEED's pronunciations, which only the server holds, so the page refuses it with that reason;
    `construe` asks a model, and planCheck refuses it as every step that asks is refused (agent-free's words)."""
    from enough.thym import check_file
    from enough.thym import plan as P
    src = ROOT / "defaults" / "thym" / "decompile-verse.thym"
    poem = ROOT / "tests" / "fixtures" / "fabula" / "verse" / "nobody.txt"
    work = tmp_path / "f.cosm"
    work.write_text("oes: fabula/1\nflavour: fabulap\nnodes: []\n", encoding="utf-8")
    rows = [{"name": "poem", "type": "text", "path": str(poem), "sha256": digest_path(poem)}]
    if program != "scan-the-poem":
        rows.append({"name": "f", "type": "fabula", "path": str(work), "sha256": digest_path(work)})
    plan = P.plan(check_file(src), rows, program=program)
    assert not isinstance(plan, Refusal), plan
    got = _node({"planCheck": {"plan": bundle.jsonable(plan), "program": src.read_text(encoding="utf-8")}})["refusal"]
    assert got["stage"] == "plan" and got["check"] == check and words in got["message"], got
    if check == "move":
        assert "FEED's pronunciations, which the server holds" in got["message"]
