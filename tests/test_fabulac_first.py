"""Fabulac-first's helpers (0.8, F6: pins section 4, the three doors): the plain functions
(`enough/fabulac_first.py`), the routes over them (`enough/routes/fabulac.py`), the readvisor's `fabulac` tool's
`<do>` words, the command line (`python -m enough.fabulac`), the client (`enough/enough_client.py`) and the three
starters (`defaults/fabulac-starters/`); running wired to the sandbox (a job thread, Stop, the app's shutdown); a
service refused at run with the later-minor sentence.

The model is a scripted one, as in tests/test_fabulac_entail.py: each source of a starter by its path, the catem
with sentences. The sandbox runs for real on macOS (`sandbox-exec`); elsewhere those tests are skipped.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import os
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from enough import enough_client as EC
from enough import fabula
from enough import fabula_tools as FT
from enough import fabulac_cli as CLI
from enough import fabulac_first as FF
from enough import macrocosm as mc
from enough import models, sandbox as sb, skeleton
from enough import thym_host as H
from enough import tools as T
from enough.routes import fabulac as RF
from enough.server import create_app
from enough.thym.coprocessor import candidate
from enough.thym.moves import author as A
from tests.test_thym_code import engines

NOW = dt.datetime(2026, 11, 20, 12, 0, tzinfo=dt.timezone.utc)
MAC = sys.platform == "darwin" and os.access("/usr/bin/sandbox-exec", os.X_OK)
needs_box = pytest.mark.skipif(not MAC, reason="the sandbox runs here only on macOS with sandbox-exec")

TALLY_INIT = '''"""tally: count the words of a text."""


def count_words(text: str) -> int:
    """The number of words in text: runs of characters between white space."""
    return len(text.split())
'''

TALLY_MAIN = '''"""The command line of tally."""
import argparse
import sys
import time

from tally import count_words


def main(argv=None) -> int:
    """tally count PATH: print the number of words in the file at PATH."""
    parser = argparse.ArgumentParser(prog="tally")
    sub = parser.add_subparsers(dest="command", required=True)
    count = sub.add_parser("count")
    count.add_argument("path")
    args = parser.parse_args(argv)
    if args.path == "forever.md":
        while True:
            time.sleep(0.05)
    try:
        with open(args.path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        print(f"tally: {args.path}: no such file", file=sys.stderr)
        return 2
    print(count_words(text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

KEYVAL_INIT = '''"""keyval: read and write key=value lines."""


def split_pair(line: str) -> list:
    """The key and the value of a key=value line, each without the spaces around it."""
    if "=" not in line:
        raise ValueError("no '=' in the line")
    key, value = line.split("=", 1)
    return [key.strip(), value.strip()]


def join_pair(key: str, value: str) -> str:
    """The line key=value."""
    return f"{key}={value}"
'''

GREET_INIT = '''"""greet: a greeting."""


def greeting(name: str) -> str:
    """The words greet answers with."""
    return f"Hello, {name}."
'''

GREET_MAIN = '''"""greet's service."""


def main(argv=None) -> int:
    """Serve greetings (served in a later minor)."""
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

SOURCES = {"tally/__init__.py": TALLY_INIT, "tally/__main__.py": TALLY_MAIN, "keyval/__init__.py": KEYVAL_INIT,
           "greet/__init__.py": GREET_INIT, "greet/__main__.py": GREET_MAIN}

CATEMS = {
    "tally": """
intro: [{say: tally counts the words of a text file from the command line., cites: [N:aim/count-words]}]
sections:
  - heading: Count a file
    sentences: [{say: A person counts the words of one file with the count command., cites: [N:use/count-a-file, C:interface/command-count]}]
""",
    "keyval": """
intro: [{say: keyval reads a line of key=value into its two halves., cites: [N:aim/read-pairs]}]
sections:
  - heading: Split and join
    sentences:
      - {say: A program reads a settings file of key=value lines with split_pair., cites: [N:use/settings-file, C:interface/split-pair]}
      - {say: join_pair gives the line from a key and a value., cites: [C:interface/join-pair]}
""",
    "greet": """
intro: [{say: greet answers a greeting on a port., cites: [N:aim/greet]}]
sections:
  - heading: Greeting
    sentences: [{say: A page on this machine asks greet for a greeting, and greeting gives the words it answers with., cites: [N:use/a-page-asks, C:interface/greeting]}]
""",
}


def _t(inputs: dict, name: str) -> str:
    v = (inputs or {}).get(name)
    v = v[0] if isinstance(v, tuple) else v
    return v.text() if hasattr(v, "text") else str(v or "")


class Model:
    """A scripted model: each source by its path; the catem's sentences by the program's name (read off the path)."""

    def complete(self, contract, inputs, *, budget, **_kw):
        step = _t(inputs, "fabulac")
        if step == "code":
            return candidate(f"```python\n{SOURCES[_t(inputs, 'path')]}```\n", engine="model:scripted-1", tokens=5)
        if step == "catem":
            name = _t(inputs, "name")
            data = mc.yaml_load(CATEMS[name])
            return candidate({**data, "engine": "model:scripted-1"}, engine="model:scripted-1", tokens=5)
        return candidate("questions: []", engine="model:scripted-1", tokens=5)


def runtime(cp: Model | None = None):
    cp = cp or Model()

    def make(stage, plan, info, mode, scaffolds, program):
        from enough.thym.coprocessor import RefusingCoprocessor
        return {"coprocessor": cp if mode == "model" else RefusingCoprocessor(), "agent_free": False,
                "rules": scaffolds, "preflight": None, "environment": {"route": "local"} if mode == "model" else {},
                "root": H.host_root(), "engines": engines(), "calls": None}
    return make


@pytest.fixture
def scripted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every entailment asks the scripted model, and the routes decide `model` (as with a model running)."""
    monkeypatch.setattr(FF, "RUNTIME", runtime())

    async def decide(canon_mode, body, route):
        return "model", ""
    monkeypatch.setattr(RF, "decide_mode", decide)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    proj = tmp_path / "project"
    proj.mkdir()
    skeleton.ensure_skeleton(proj)
    f = proj / "rness" / "skills" / ".disabled"
    if f.is_file():
        f.write_text("".join(ln + "\n" for ln in f.read_text().splitlines() if ln.strip() != "macrocosm-oes"))
    (proj / "notes.md").write_text("one two three four\n", encoding="utf-8")
    return proj


@pytest.fixture
def client(project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    live = tmp_path / "live-models.json"
    live.write_text(json.dumps({"current": "g40-04"}), encoding="utf-8")
    monkeypatch.setattr(models, "LIVE_STATE", live)
    assert str(H.host_root()).startswith(str(tmp_path))
    assert str(sb.default_root()).startswith(str(tmp_path))
    app = create_app(project, "http://127.0.0.1:9", supervise=False)
    with TestClient(app, headers={"X-Enough-Api": "1"}) as c:
        yield c
    FT.configure()


def enough_over(client: TestClient) -> EC.Enough:
    """The client library, its requests sent into the app in this process."""
    def send(method, url, headers, body):
        r = client.request(method, url.replace("http://enough.test", ""), headers=headers, content=body)
        return r.status_code, r.content
    return EC.Enough("http://enough.test", transport=send, poll=0.05)


def cli(project: Path, *argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = CLI.main(["--project", str(project), *argv])
    return code, out.getvalue(), err.getvalue()


def begun(project: Path, kind: str) -> str:
    name = {"tool": "tally", "library": "keyval", "service": "greet"}[kind]
    FF.begin(project, name, starter=kind, licence="MIT", by="Ada", now=NOW)
    return name


# ---------------------------------------------------------------------------
# The starters
# ---------------------------------------------------------------------------

def test_three_starters_one_per_kind_each_passing_its_checks():
    got = FF.starters()
    assert [(s["kind"], s["name"]) for s in got] == [("tool", "tally"), ("library", "keyval"), ("service", "greet")]
    for s in got:
        p = FF.STARTERS.parent.parent / s["path"]
        doc = mc.yaml_load(p.read_text(encoding="utf-8"))
        rep = fabula.lint(p)
        assert rep.ok, [str(e) for e in rep.errors]
        # the one warning a starter carries: the licence is the person's to give
        assert [str(w).split()[0] for w in rep.warnings] == ["licence-recorded"], [str(w) for w in rep.warnings]
        assert A.is_authored(doc) and not A.source_problems(doc)
        assert not A.uncovered_items(doc["nodes"])
        assert doc["program"]["kind"] == s["kind"] and s["cases"]
        assert all(n["stance"] == "axiom" for n in doc["nodes"])


def test_a_starter_begun_under_another_name_is_the_persons(project: Path):
    out = FF.begin(project, "counter", starter="tool", licence="MIT", by="Ada", now=NOW)
    assert out["fabulac"] == "counter.fabulac.cosm" and "tool starter" in out["message"]
    p = project / "counter.fabulac.cosm"
    doc = mc.yaml_load(p.read_text())
    assert doc["name"] == "counter" and doc["id"] == "fabula/counter"
    assert doc["program"]["start"] == ["-m", "counter"] and doc["source"]["licence"] == "MIT"
    assert doc["source"]["at"] == "2026-11-20"
    items = {n["id"]: n for n in doc["nodes"]}
    assert items["C:interface/command-count"]["signature"] == "counter count PATH"
    assert items["P:case/missing-file"]["expect"]["steps"][0]["error-output"] == "counter: gone.md: no such file\n"
    assert items["R:maker/author"]["name"] == "Ada" and items["R:licence/licence"]["identifier"] == "MIT"
    rep = fabula.lint(p)
    assert rep.ok and not rep.warnings, [str(x) for x in rep.errors + rep.warnings]
    with pytest.raises(FF.FirstError) as e:
        FF.begin(project, "counter", starter="tool")
    assert e.value.status == 409


# ---------------------------------------------------------------------------
# The plain functions
# ---------------------------------------------------------------------------

def test_add_check_status_and_moved_by_rules(project: Path):
    begun(project, "tool")
    out = FF.add(project, "tally", as_="requirement", says="tally never writes to the file it counts.")
    assert out["added"] == "N:requirement/tally-never-writes-to-the-file"
    assert out["item"]["force"] == {"pending": A.ADD_ASKS["force"]}
    assert out["item"]["provenance"]["mode"] == "manual" and out["item"]["stance"] == "axiom"
    case = FF.add(project, "tally.fabulac.cosm", as_="case", says="Two words count 2.",
                  fields={"of": ["C:interface/count-words"],
                          "given": {"calls": "C:interface/count-words", "arguments": {"text": "a b"}},
                          "expect": {"value": 2}})
    assert case["item"]["expect"] == {"value": 2}
    chk = FF.check(project, "tally")
    assert chk["ok"] and chk["uncovered"] == [] and chk["entailment"] is None
    FF.add(project, "tally", as_="requirement", says="It counts a huge file.", fields={"force": "must"})
    assert FF.check(project, "tally")["uncovered"] == ["N:requirement/it-counts-a-huge-file"]
    st = FF.status(project, "tally")
    assert st["program"]["kind"] == "tool" and st["entailment"] is None and st["interview"]["authored"]
    assert FF.moved(project, "tally")["entailed"] is False
    for bad, status in ((dict(as_="wish", says="x"), 400), (dict(as_="case", says="  "), 400)):
        with pytest.raises(FF.FirstError) as e:
            FF.add(project, "tally", **bad)
        assert e.value.status == status


def test_only_an_authored_fabulac_is_taken(project: Path):
    doc = mc.yaml_load((FF.STARTERS / "tool" / "tally.fabulac.cosm").read_text())
    doc["source"] = {"kind": "folder", "path": "folded/"}
    (project / "folded.fabulac.cosm").write_text(mc.dump(json.loads(json.dumps(doc))))
    for fn in (FF.status, FF.check, FF.moved, FF.test):
        with pytest.raises(FF.FirstError) as e:
            fn(project, "folded")
        assert e.value.status == 409 and "read, never run" in str(e.value)
    with pytest.raises(FF.FirstError) as e:
        FF.status(project, "nothing-here")
    assert e.value.status == 404


def test_begin_by_rules_runs_the_authoring_job(project: Path):
    out = FF.begin(project, "fresh", kind="library", licence="MIT", by="Ada", now=NOW)
    assert out["fabulac"] == "fresh.fabulac.cosm" and out["state"]["authored"] and out["state"]["kind"] == "library"
    assert out["waiting"] and out["state"]["next"] == "answer"


def test_begin_into_a_missing_folder_is_refused_with_a_sentence(project: Path, client: TestClient):
    """0.8 (W4-X7; W4-FP found it): by rules or from a starter, a folder that is not there is refused in words (404),
    never a bare FileNotFoundError, and nothing is made."""
    for kw in (dict(kind="tool", mode="rules"), dict(starter="tool")):
        with pytest.raises(FF.FirstError) as e:
            FF.begin(project, "not-yet/linecount", now=NOW, **kw)
        assert e.value.status == 404, kw
        assert str(e.value) == ("there is no folder not-yet/ to begin linecount.fabulac.cosm in: make the folder "
                                "first, or begin it in one that is there")
    assert not (project / "not-yet").exists()
    r = client.post("/api/fabulac/begin", json={"path": "not-yet/linecount", "mode": "rules"})
    assert r.status_code == 404 and "there is no folder not-yet/" in r.json()["detail"], r.text


@needs_box
def test_a_starter_tools_entailed_tests_and_the_tool_run_in_the_sandbox(project: Path, scripted: None):
    begun(project, "tool")
    with pytest.raises(FF.FirstError) as e:
        FF.test(project, "tally")
    assert e.value.status == 409 and "not entailed" in str(e.value)
    ent = FF.entail(project, "tally", now=NOW)
    assert (project / "tally" / "tests" / "test_cases.py").is_file() and ent["fabulac"] == "tally.fabulac.cosm"
    res = FF.test(project, "tally")
    assert res["ok"] and res["ran"] == 3 and res["enforced"], res["stderr"]
    got = FF.run(project, "tally", ["count", "notes.md"], hand_over=["notes.md"])
    assert got["ok"] and got["stdout"] == "4\n" and got["handed_over"], (got["stderr"], got["handed_over"])
    assert FF.status(project, "tally")["last_run"]["what"] == "tool"
    assert FF.moved(project, "tally")["edited"] == []


# ---------------------------------------------------------------------------
# The command line, on a starter
# ---------------------------------------------------------------------------

def test_the_command_line_on_a_starter(project: Path, scripted: None):
    code, out, _ = cli(project, "starters")
    assert code == 0 and "tool: tally" in out and "service: greet" in out
    code, out, _ = cli(project, "begin", "tally", "--starter", "tool", "--licence", "MIT", "--by", "Ada")
    assert code == 0 and "begun from the tool starter" in out
    code, out, _ = cli(project, "check", "tally")
    assert code == 0 and "no errors" in out
    code, out, _ = cli(project, "add", "tally", "requirement", "It counts fast.", "--field", 'force="should"')
    assert code == 0 and "added N:requirement/it-counts-fast" in out
    code, out, _ = cli(project, "--json", "status", "tally")
    assert code == 0 and json.loads(out)["program"]["kind"] == "tool"
    code, _out, err = cli(project, "test", "tally")
    assert code == 2 and "not entailed" in err
    code, _out, err = cli(project, "entail", "tally")
    assert code == 2 and "only a model writes sources" in err
    code, out, _ = cli(project, "moved", "tally")
    assert code == 0 and "not entailed yet" in out
    if MAC:
        FF.entail(project, "tally", now=NOW)
        code, out, _ = cli(project, "test", "tally")
        assert code == 0 and "the tests passed" in out and "Ran 3 tests" in out
        code, out, _ = cli(project, "run", "tally", "--hand", "notes.md", "--", "count", "notes.md")
        assert code == 0 and out.splitlines()[-1] == "4"
        code, out, _ = cli(project, "run", "tally", "--", "count", "gone.md")
        assert code == 1


def test_head_by_a_name_writes_a_maker_reference_that_checks(project: Path, scripted: None):
    """W5-F7's find: `head … --by Ada` wrote `Ada` as a reference, and `check` failed `id-grammar`."""
    for kind in ("tool", "library"):
        begun(project, kind)
    code, out, err = cli(project, "head", "toolbox", "tally", "keyval", "--licence", "MIT", "--by", "Ada")
    assert code == 0, err
    d = mc.yaml_load((project / "toolbox.fabulac.cosm").read_text(encoding="utf-8"))
    assert d["source"]["by"] == ["R:maker/ada"]
    maker = next(n for n in d["nodes"] if n["id"] == "R:maker/ada")
    assert maker["type"] == "maker" and maker["name"] == "Ada" and maker["capacity"] == "author"
    code, out, err = cli(project, "check", "toolbox")
    assert code == 0 and "id-grammar" not in out + err, out + err
    from enough import fabulac_head as FH
    assert FH.maker_ref("R:maker/ada") == ("R:maker/ada", "ada")
    assert FH.maker_ref("Ada Lovelace") == ("R:maker/ada-lovelace", "Ada Lovelace")


def test_python_dash_m_enough_fabulac_is_the_command_line():
    import subprocess
    got = subprocess.run([sys.executable, "-m", "enough.fabulac", "starters"], capture_output=True, text=True,
                         cwd=Path(__file__).resolve().parents[1], timeout=60)
    assert got.returncode == 0 and "library: keyval" in got.stdout, got.stderr


# ---------------------------------------------------------------------------
# The routes and the client
# ---------------------------------------------------------------------------

def test_the_client_drives_a_running_enough(client: TestClient, project: Path, scripted: None):
    e = enough_over(client)
    assert e.check_promise()["version"] == 1
    assert [s["kind"] for s in e.starters()] == ["tool", "library", "service"]
    got = e.begin("tally", starter="tool", licence="MIT", by="Ada")
    assert got["fabulac"] == "tally.fabulac.cosm"
    assert e.add("tally", "requirement", "tally never writes to the file it counts.",
                 fields={"force": "should"})["added"].startswith("N:requirement/")
    assert e.check("tally")["ok"]
    ent = e.entail("tally")
    assert ent["fabulac"] == "tally.fabulac.cosm" and "tally/__main__.py" in json.dumps(ent)
    st = e.status("tally")
    assert st["entailment"]["entailed"] and not st["entailment"]["tell"]
    assert e.moved("tally")["edited"] == []
    if MAC:
        res = e.test("tally")
        assert res["ok"] and res["ran"] == 3, res["stderr"]
        out = e.run("tally", ["count", "notes.md"], hand_over=["notes.md"])
        assert out["stdout"] == "4\n"
        assert e.status("tally")["last_run"]["what"] == "tool"
    with pytest.raises(EC.EnoughError) as err:
        e.stop("tally")
    assert err.value.status == 409 and "nothing of tally" in err.value.detail
    with pytest.raises(EC.EnoughError) as err:
        e.status("nothing-here")
    assert err.value.status == 404


def test_a_service_is_entailed_and_refused_at_run(client: TestClient, project: Path, scripted: None):
    e = enough_over(client)
    e.begin("greet", starter="service", licence="MIT")
    e.entail("greet")
    assert (project / "greet" / "pyproject.toml").is_file()
    for call in (lambda: e.test("greet"), lambda: e.run("greet", [])):
        with pytest.raises(EC.EnoughError) as err:
            call()
        assert err.value.status == 409
        assert err.value.detail == sb.SERVING_LATER.format(name="greet")


def test_a_library_has_tests_and_no_tool_to_start(client: TestClient, project: Path, scripted: None):
    e = enough_over(client)
    e.begin("keyval", starter="library")
    e.entail("keyval")
    with pytest.raises(EC.EnoughError) as err:
        e.run("keyval", [])
    assert err.value.status == 409 and "not a tool" in err.value.detail
    if MAC:
        res = e.test("keyval")
        assert res["ok"] and res["ran"] == 3, res["stderr"]


@needs_box
def test_stop_stops_a_sandbox_run_through_its_job(client: TestClient, project: Path, scripted: None):
    e = enough_over(client)
    e.begin("tally", starter="tool")
    e.entail("tally")
    started = e.run("tally", ["count", "forever.md"], wait=False)
    run_id = started["run"]
    deadline = time.time() + 20
    while run_id not in sb.running() and time.time() < deadline:
        time.sleep(0.05)
    assert run_id in sb.running()
    stopped = e.stop("tally")
    assert stopped["stopped"][0]["run"] == run_id
    snap = started["job"]
    while snap["state"] in ("queued", "running") and time.time() < deadline:
        time.sleep(0.05)
        snap = e.job(snap["id"])
    assert snap["state"] in ("done", "cancelled"), snap
    assert run_id not in sb.running()
    if snap["state"] == "done":
        assert snap["result"]["stopped_by"] == "request"


def test_a_run_s_folder_goes_once_its_result_is_read(project: Path, scripted: None):
    """W5-XF2: sandbox run folders were never swept; a run's folder is removed once its result is read."""
    begun(project, "tool")
    FF.entail(project, "tally", now=NOW)
    fab, run = FF.prepare(project, "tally", what="tests")
    assert run.folder.is_dir()
    try:
        sb.machinery()
        boxed = True
    except sb.Refusal:
        boxed = False
    if MAC:
        out = FF.execute(project, fab, run, what="tests")
        assert out["ok"] and out["run"] == run.run_id
    elif boxed:
        # Linux with bubblewrap (GitHub's runners have it): the box may or may not hold there, but the run is
        # its own either way, and its folder goes once its result is read.
        out = FF.execute(project, fab, run, what="tests")
        assert out["run"] == run.run_id
    else:
        with pytest.raises(FF.FirstError):
            FF.execute(project, fab, run, what="tests")
    assert not run.folder.exists()


def test_the_apps_start_sweeps_stale_sandbox_run_folders(project: Path, tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch):
    root = sb.default_root()
    stale, fresh = root / "20261101-120000-0000000a", root / "20261118-120000-0000000b"
    for d in (stale, fresh):
        (d / "work").mkdir(parents=True)
    os.utime(stale, (time.time() - 2 * sb.STALE_AFTER,) * 2)
    live = tmp_path / "live-models.json"
    live.write_text(json.dumps({"current": "g40-04"}), encoding="utf-8")
    monkeypatch.setattr(models, "LIVE_STATE", live)
    with TestClient(create_app(project, "http://127.0.0.1:9", supervise=False)):
        assert not stale.exists() and fresh.is_dir()
    FT.configure()


def test_the_apps_shutdown_stops_every_sandbox_run(project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    called: list[bool] = []
    monkeypatch.setattr(sb, "stop_all", lambda: called.append(True))
    live = tmp_path / "live-models.json"
    live.write_text(json.dumps({"current": "g40-04"}), encoding="utf-8")
    monkeypatch.setattr(models, "LIVE_STATE", live)
    with TestClient(create_app(project, "http://127.0.0.1:9", supervise=False)):
        assert not called
    FT.configure()
    assert called == [True]


def test_entail_without_a_model_is_refused_before_a_job(client: TestClient, project: Path):
    begun(project, "tool")
    r = client.post("/api/fabulac/entail", json={"path": "tally"})
    assert r.status_code == 409 and "needs a model" in r.json()["detail"]


# ---------------------------------------------------------------------------
# The tool's do-words
# ---------------------------------------------------------------------------

def tool(project: Path, do: str, path: str = "tally", **tags: str):
    inner = "".join(f"<{k}>{v}</{k}>" for k, v in tags.items())
    (call,) = T.parse_tool_calls(f'<tool name="fabulac"><path>{path}</path><do>{do}</do>{inner}</tool>')
    return FT.run_fabulac(project, call)


def test_the_fabulac_tools_do_words(client: TestClient, project: Path, scripted: None):
    got = tool(project, "starters")
    assert got.ok and "tool: tally" in got.body
    got = tool(project, "begin", starter="tool", licence="MIT")
    assert got.ok and "begun from the tool starter" in got.body, got.body
    got = tool(project, "add", **{"as": "requirement", "says": "It counts fast."})
    assert got.ok and "added N:requirement/it-counts-fast" in got.body
    got = tool(project, "check")
    assert got.ok and "no errors" in got.body
    got = tool(project, "status")
    assert got.ok and "authored tool" in got.body and "not entailed yet" in got.body
    got = tool(project, "entail")
    assert got.ok and "job " in got.body, got.body
    deadline = time.time() + 60
    while "entailment tally/" not in tool(project, "status").body and time.time() < deadline:
        time.sleep(0.1)
    assert "entailment tally/: in step" in tool(project, "status").body
    assert "in step" in tool(project, "moved").body
    if MAC:
        got = tool(project, "test")
        assert got.ok and "sandbox" in got.body
        while "last tests" not in tool(project, "status").body and time.time() < deadline:
            time.sleep(0.1)
        assert "last tests: the tests passed" in tool(project, "status").body
    got = tool(project, "keep", file="tally/__main__.py")
    assert not got.ok and "error:" in got.body
    got = tool(project, "wish")
    assert not got.ok and "begin" in got.body


def test_a_hand_edit_is_named_and_kept_through_the_routes(client: TestClient, project: Path, scripted: None):
    e = enough_over(client)
    e.begin("tally", starter="tool")
    e.entail("tally")
    main = project / "tally" / "tally" / "__main__.py"
    main.write_text(main.read_text() + "\n# mine\n")
    assert e.moved("tally")["edited"] == ["tally/__main__.py"]
    with pytest.raises(EC.EnoughError) as err:
        e.entail("tally")
    assert err.value.status == 409 and "tally/__main__.py" in err.value.detail
    kept = e.keep("tally", ["tally/__main__.py"], because="mine")
    assert kept["kept"][0]["path"] == "tally/__main__.py"
    assert e.moved("tally")["kept"] == ["tally/__main__.py"]
    assert e.let_go("tally", ["tally/__main__.py"])["released"] == ["tally/__main__.py"]
