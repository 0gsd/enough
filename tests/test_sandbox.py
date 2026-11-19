"""enough/sandbox.py: the box an authored fabulac's entailment runs in (tracker `fabulac-first` F4r).

The real-run tests start programs under /usr/bin/sandbox-exec on this Mac and skip where it is absent; the Linux and
other-platform paths are tested with the mechanism faked. Everything happens inside pytest's tmp_path: a folder in it
stands in for the home folder, and nothing touches ~/enough or the real home.
"""
from __future__ import annotations

import hashlib
import os
import socket
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

from enough import sandbox as sb

MAC = sys.platform == "darwin" and os.access("/usr/bin/sandbox-exec", os.X_OK)
needs_mac = pytest.mark.skipif(not MAC, reason="needs macOS with /usr/bin/sandbox-exec")


def entailed(tmp_path: Path, main: str, *, name: str = "tally", kind: str = "tool", tests: str | None = None,
             extra_toml: str = "", project: str = "") -> Path:
    """An entailed application folder, as fabulac-first lays it out (survey 3.4)."""
    d = tmp_path / "project" / name
    (d / name).mkdir(parents=True)
    (d / name / "__init__.py").write_text("")
    (d / name / "__main__.py").write_text(textwrap.dedent(main))
    (d / "tests").mkdir()
    (d / "tests" / "__init__.py").write_text("")
    (d / "tests" / "test_cases.py").write_text(textwrap.dedent(tests or """
        import unittest
        class Cases(unittest.TestCase):
            def test_one(self):
                self.assertEqual(1 + 1, 2)
    """))
    (d / "ENTAILED.md").write_text("entailed\n")
    (d / "pyproject.toml").write_text(textwrap.dedent(f"""
        [project]
        name = "{name}"
        version = "0.1.0"
        requires-python = ">=3.11"
        {project}
        [tool.enough]
        kind = "{kind}"
        start = ["-m", "{name}"]
        {extra_toml}
    """))
    return d


def digest(folder: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(folder.rglob("*")):
        h.update(str(p.relative_to(folder)).encode())
        if p.is_file():
            h.update(p.read_bytes())
    return h.hexdigest()


def go(tmp_path: Path, main: str, argv=(), limits: sb.Limits | None = None, **kw) -> sb.Result:
    run = sb.prepare(entailed(tmp_path, main), source_kind="authored", root=tmp_path / "runs")
    return sb.run_tool(run, list(argv), limits=limits or sb.Limits(wall=30, grace=1), **kw)


# ---- refusals, on every platform ------------------------------------------------------------------------------

def test_package_source_is_named_once():
    assert sb.PACKAGE_SOURCE == "standard-library"
    assert sb.unmet_needs(["json", "os.path", "unittest", "requests", "numpy.linalg", "mine"], local=["mine"]) \
        == ["numpy", "requests"]


def test_the_module_imports_only_the_standard_library():
    import ast
    tree = ast.parse(Path(sb.__file__).read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            names.add(node.module.split(".")[0])
    assert names and names <= set(sys.stdlib_module_names) | {"__future__"}
    launcher = ast.parse(sb._LAUNCHER)
    assert {a.name for n in ast.walk(launcher) if isinstance(n, ast.Import) for a in n.names} \
        <= set(sys.stdlib_module_names)


def test_not_authored_is_read_never_run(tmp_path):
    d = entailed(tmp_path, "print('hi')\n")
    with pytest.raises(sb.Refusal) as e:
        sb.prepare(d, source_kind="decompiled", root=tmp_path / "runs")
    assert e.value.reason == "not-authored" and "read, never run" in e.value.sentence
    assert not (tmp_path / "runs").exists()


def test_service_is_refused_with_the_later_minor(tmp_path):
    d = entailed(tmp_path, "print('hi')\n", kind="service", extra_toml="serve = {port = 0, reach = []}")
    with pytest.raises(sb.Refusal) as e:
        sb.prepare(d, source_kind="authored", root=tmp_path / "runs")
    assert e.value.reason == "service"
    assert "serving comes in a later minor" in e.value.sentence


def test_program_block_from_the_catalog():
    p = sb.program_from_block("tally", {"kind": "service", "start": ["-m", "tally"],
                                        "serve": {"port": 8080, "reach": []}})
    assert p.kind == "service" and p.serve == {"port": 8080, "reach": []}
    with pytest.raises(sb.Refusal) as e:
        sb.check_program(p)
    assert e.value.sentence.startswith("tally is a service.")
    with pytest.raises(sb.Refusal):
        sb.program_from_block("tally", {"kind": "daemon"})


def test_an_import_outside_the_standard_library_is_refused(tmp_path):
    d = entailed(tmp_path, "import json\nimport requests\nfrom . import helper\n")
    with pytest.raises(sb.Refusal) as e:
        sb.prepare(d, source_kind="authored", root=tmp_path / "runs")
    assert e.value.reason == "needs"
    assert e.value.sentence == ("tally needs `requests`, which is outside the standard library: enough cannot run "
                                "it here yet. Its source is entailed and can run elsewhere.")


def test_a_declared_dependency_is_refused(tmp_path):
    d = entailed(tmp_path, "print(1)\n", project='dependencies = ["attrs==23.1.0", "rich>=13"]')
    with pytest.raises(sb.Refusal) as e:
        sb.prepare(d, source_kind="authored", root=tmp_path / "runs")
    assert "`attrs`, `rich`, which are outside the standard library" in e.value.sentence


def test_a_newer_python_is_refused():
    p = sb.Program(name="tally", requires_python=">=9.1")
    with pytest.raises(sb.Refusal) as e:
        sb.check_program(p)
    assert e.value.reason == "python" and "Python 9.1 or later" in e.value.sentence


def test_a_folder_without_tool_enough_is_not_run(tmp_path):
    d = tmp_path / "plain"
    d.mkdir()
    (d / "pyproject.toml").write_text('[project]\nname = "plain"\n')
    with pytest.raises(sb.Refusal) as e:
        sb.prepare(d, source_kind="authored", root=tmp_path / "runs")
    assert e.value.reason == "not-entailed"


# ---- Linux and other platforms, with the mechanism faked ------------------------------------------------------

def test_linux_without_bubblewrap_refuses(tmp_path, monkeypatch):
    monkeypatch.setattr(sb, "_platform", lambda: "linux")
    monkeypatch.setattr(sb, "_bwrap", lambda: None)
    with pytest.raises(sb.Refusal) as e:
        sb.prepare(entailed(tmp_path, "print(1)\n"), source_kind="authored", root=tmp_path / "runs")
    assert e.value.reason == "no-box" and "bubblewrap" in e.value.sentence
    assert "home folder" in e.value.sentence


def test_linux_with_bubblewrap_builds_the_same_promises(tmp_path, monkeypatch):
    monkeypatch.setattr(sb, "_platform", lambda: "linux")
    monkeypatch.setattr(sb, "_bwrap", lambda: "/usr/bin/bwrap")
    run = sb.prepare(entailed(tmp_path, "print(1)\n"), source_kind="authored", root=tmp_path / "runs")
    argv, mech, g = sb.build_command(run, ["-m", "tally"], sb.Limits())
    assert mech == "bwrap" and argv[0] == "/usr/bin/bwrap"
    for flag in ("--unshare-all", "--die-with-parent", "--new-session", "--clearenv"):
        assert flag in argv
    assert "--share-net" not in argv
    pairs = list(zip(argv, argv[1:], argv[2:]))
    f = str(run.folder)
    assert ("--bind", f, f) in pairs
    for sub in ("box", "out", "handed"):  # read-only over the writable run folder, after it
        p = str(run.folder / sub)
        assert ("--ro-bind", p, p) in pairs
        assert argv.index(p) > argv.index("--bind")
    interp = sb.interpreter()
    for h in interp["hidden"]:
        assert ("--tmpfs", h) in list(zip(argv, argv[1:]))
    env = {argv[i + 1]: argv[i + 2] for i, a in enumerate(argv) if a == "--setenv"}
    assert env["HOME"] == str(run.folder / "home") and env["TMPDIR"] == str(run.folder / "tmp")
    assert not any(k.startswith("ENOUGH_") or "proxy" in k.lower() for k in env)
    tail = argv[argv.index(interp["executable"]):]
    assert tail[1:6] == ["-I", "-S", "-X", "utf8", "-B"] and "--as" in tail
    assert "loopback only" in g["network"] and "RLIMIT_AS" in g["memory"]
    # the program's own copy is not the project
    assert str(run.original) not in argv


def test_other_platforms_refuse(tmp_path, monkeypatch):
    monkeypatch.setattr(sb, "_platform", lambda: "win32")
    with pytest.raises(sb.Refusal) as e:
        sb.machinery()
    assert e.value.reason == "no-box" and "win32" in e.value.sentence


def test_macos_profile_text(tmp_path, monkeypatch):
    monkeypatch.setattr(sb, "_platform", lambda: "darwin")
    run = sb.Run(run_id="r", folder=tmp_path / "r", program=sb.Program(name="t"), original=tmp_path)
    prof = sb.macos_profile(run)
    lines = prof.splitlines()
    assert lines[:4] == ["(version 1)", "(allow default)", "(deny network*)", "(deny file-write*)"]
    assert "(deny file-read*)" in lines and "(deny process-exec*)" in lines
    assert f'(subpath "{tmp_path / "r" / "work"}")' in prof
    assert f'(subpath "{tmp_path / "r" / "box"}")' not in prof          # box/ and out/ are not writable
    assert "site-packages" in prof


# ---- real runs on this Mac -------------------------------------------------------------------------------------

@needs_mac
def test_entailed_tests_run_in_the_box(tmp_path):
    run = sb.prepare(entailed(tmp_path, "print(1)\n"), source_kind="authored", root=tmp_path / "runs")
    r = sb.run_tests(run, limits=sb.Limits(wall=60))
    assert r.exit_code == 0, r.stderr
    assert r.enforced and r.mechanism == "sandbox-exec"
    assert "Ran 1 test" in r.stderr and "OK" in r.stderr
    assert "not limited" in r.guarantees["memory"]
    assert (run.folder / "out" / "result.json").is_file()


@needs_mac
def test_the_network_is_denied(tmp_path):
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(0.5)
    port = srv.getsockname()[1]
    r = go(tmp_path, f"""
        import socket
        try:
            socket.create_connection(("127.0.0.1", {port}), timeout=3)
            print("CONNECTED")
        except OSError as e:
            print("DENIED", e)
        try:
            s = socket.socket(); s.bind(("127.0.0.1", 0)); s.listen(1); print("BOUND")
        except OSError as e:
            print("NO-BIND", e)
    """)
    try:
        with pytest.raises(socket.timeout):
            srv.accept()
    finally:
        srv.close()
    assert "DENIED" in r.stdout and "CONNECTED" not in r.stdout
    assert "NO-BIND" in r.stdout
    assert r.enforced and r.exit_code == 0


@needs_mac
def test_a_write_outside_its_folder_is_refused(tmp_path):
    outside = tmp_path / "outside.txt"
    r = go(tmp_path, f"""
        import os
        open("canary.txt", "w").write("inside")
        open(os.path.join(os.environ["HOME"], "h.txt"), "w").write("home of its own")
        try:
            open({str(outside)!r}, "w").write("escaped")
            print("WROTE")
        except OSError as e:
            print("REFUSED", e)
        try:
            open("../box/launch.py", "a").write("#")
            print("WROTE-BOX")
        except OSError as e:
            print("REFUSED-BOX")
    """)
    assert "REFUSED" in r.stdout and "WROTE" not in r.stdout and "REFUSED-BOX" in r.stdout
    assert not outside.exists()
    run_folder = next((tmp_path / "runs").iterdir())
    assert (run_folder / "work" / "canary.txt").read_text() == "inside"   # the canary, turned around
    assert (run_folder / "home" / "h.txt").exists()
    assert any("Operation not permitted" in s for s in r.refused)


@needs_mac
def test_a_read_of_the_home_folder_is_refused(tmp_path):
    home = tmp_path / "fakehome"
    (home / ".ssh").mkdir(parents=True)
    secret = home / ".ssh" / "id_test"
    secret.write_text("SECRET-KEY-MATERIAL")
    r = go(tmp_path, f"""
        import os
        for what, f in (("read", lambda: open({str(secret)!r}).read()),
                        ("list", lambda: os.listdir({str(home)!r})),
                        ("link", lambda: (os.link({str(secret)!r}, "stolen"), open("stolen").read())[1]),
                        ("sitepkg", lambda: __import__("pytest"))):
            try:
                print(what, "GOT", f())
            except Exception as e:
                print(what, "REFUSED", type(e).__name__)
        print("HOME", os.environ["HOME"])
    """)
    assert "SECRET-KEY-MATERIAL" not in r.stdout + r.stderr
    for what in ("read", "list", "link", "sitepkg"):
        assert f"{what} REFUSED" in r.stdout, r.stdout
    assert f"/{r.run_id}/home\n" in r.stdout


@needs_mac
def test_only_the_interpreter_may_be_started(tmp_path):
    r = go(tmp_path, """
        import subprocess, sys
        try:
            subprocess.run(["/bin/sh", "-c", "echo shell"], check=True)
            print("SHELL-RAN")
        except OSError as e:
            print("NO-SHELL", type(e).__name__)
    """)
    assert "NO-SHELL" in r.stdout and "SHELL-RAN" not in r.stdout


@needs_mac
def test_the_environment_is_its_own(tmp_path, monkeypatch):
    monkeypatch.setenv("ENOUGH_HOME_SECRET", "x")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:1")
    r = go(tmp_path, """
        import json, os, sys
        print(json.dumps({"env": dict(os.environ), "path": sys.path, "flags": [sys.flags.isolated, sys.flags.no_site]}))
    """)
    import json
    data = json.loads(r.stdout)
    env = data["env"]
    assert not any(k.startswith("ENOUGH_") or "PROXY" in k.upper() for k in env)
    assert env["HOME"].endswith("/home") and env["TMPDIR"].endswith("/tmp")
    assert str(Path.home()) not in env["HOME"] or str(tmp_path) in env["HOME"]
    assert data["flags"] == [1, 1]
    assert not any("site-packages" in p for p in data["path"])


@needs_mac
def test_an_endless_loop_is_stopped_by_the_clock(tmp_path):
    r = go(tmp_path, "while True:\n    pass\n", limits=sb.Limits(wall=1.5, grace=1))
    assert r.stopped_by == "time" and "1.5 seconds" in r.stopped
    assert r.wall_time < 8
    assert r.exit_code is not None and r.exit_code < 0


@needs_mac
def test_cpu_time_is_limited(tmp_path):
    r = go(tmp_path, "while True:\n    pass\n", limits=sb.Limits(wall=30, cpu=1, grace=1))
    assert r.stopped_by == "cpu", (r.exit_code, r.stderr)
    assert r.wall_time < 15


@needs_mac
def test_a_flood_of_output_is_stopped(tmp_path):
    r = go(tmp_path, """
        import sys
        while True:
            sys.stdout.write("x" * 65536)
    """, limits=sb.Limits(wall=30, output=100_000, grace=1))
    assert r.stopped_by == "output"
    assert r.stdout_truncated and len(r.stdout) == 100_000


@needs_mac
def test_filling_the_disk_is_stopped(tmp_path):
    r = go(tmp_path, """
        import time
        i = 0
        while True:
            open(f"f{i}", "wb").write(b"0" * 65536)
            i += 1
            time.sleep(0.005)
    """, limits=sb.Limits(wall=30, disk=2_000_000, grace=1))
    assert r.stopped_by == "disk"
    assert r.disk_used < 30_000_000


@needs_mac
def test_one_file_past_the_size_limit_is_refused(tmp_path):
    r = go(tmp_path, """
        try:
            open("big", "wb").write(b"0" * 300_000)
            print("WROTE")
        except OSError as e:
            print("EFBIG", e.errno)
    """, limits=sb.Limits(wall=30, fsize=100_000))
    assert "EFBIG" in r.stdout and "WROTE" not in r.stdout


@needs_mac
def test_stop_from_another_thread(tmp_path):
    run = sb.prepare(entailed(tmp_path, "import time\nwhile True:\n    time.sleep(0.1)\n"), source_kind="authored",
                     root=tmp_path / "runs")
    box: dict = {}
    t = threading.Thread(target=lambda: box.setdefault("r", sb.run_tool(run, limits=sb.Limits(wall=60, grace=1))))
    t.start()
    for _ in range(100):
        if run.run_id in sb.running():
            break
        time.sleep(0.05)
    assert sb.stop(run.run_id)
    t.join(20)
    assert box["r"].stopped_by == "request" and box["r"].stopped == "Stopped, as asked."
    assert not sb.stop(run.run_id)


@needs_mac
def test_the_original_folder_is_never_modified(tmp_path):
    d = entailed(tmp_path, """
        import os, pathlib, shutil
        for p in pathlib.Path(".").rglob("*.py"):
            p.write_text("# overwritten\\n")
        shutil.rmtree("tests")
        open("ENTAILED.md", "a").write("changed")
        print("DONE")
    """)
    before = digest(d)
    run = sb.prepare(d, source_kind="authored", root=tmp_path / "runs")
    r = sb.run_tool(run, limits=sb.Limits(wall=30))
    assert "DONE" in r.stdout
    assert digest(d) == before
    assert not (run.work / "tests").exists()          # it changed its copy, only


@needs_mac
def test_what_is_handed_over_is_read_only(tmp_path):
    home = tmp_path / "fakehome"
    home.mkdir()
    notes = home / "notes.txt"
    notes.write_text("one two three")
    r = go(tmp_path, """
        import sys
        path = sys.argv[1]
        print("READ", open(path).read(), "AT", path)
        try:
            open(path, "a").write("more")
            print("WROTE")
        except OSError:
            print("READ-ONLY")
    """, argv=[str(notes)], handed_over=[notes])
    assert "READ one two three" in r.stdout and "READ-ONLY" in r.stdout
    assert "/handed/notes.txt" in r.stdout and str(home) not in r.stdout
    assert notes.read_text() == "one two three"
    assert r.handed_over and r.handed_over[0].endswith("/handed/notes.txt")


# ---- the second package source: enough's own .venv, for the owner's own code only (checkpoint C) ---------------

def fake_venv(tmp_path: Path, monkeypatch) -> Path:
    """A stand-in for enough's site-packages: one package, one module, one distribution."""
    sp = tmp_path / "venv" / "site-packages"
    (sp / "requests").mkdir(parents=True)
    (sp / "requests" / "__init__.py").write_text("")
    (sp / "six.py").write_text("")
    (sp / "attrs-23.1.0.dist-info").mkdir()
    (sp / "attrs-23.1.0.dist-info" / "top_level.txt").write_text("attr\nattrs\n")
    monkeypatch.setattr(sb, "venv_site_packages", lambda: [str(sp)])
    return sp


def test_the_sources_known_and_the_one_offered():
    assert sb.PACKAGE_SOURCE == "standard-library"
    assert sb.PACKAGE_SOURCES == {"standard-library", "enough-venv"}
    assert sb.OFFERED_SOURCES == ("standard-library",)
    # the default of every door is still the standard library
    import inspect
    assert inspect.signature(sb.prepare).parameters["package_source"].default == "standard-library"
    assert inspect.signature(sb.prepare).parameters["owners_code"].default is False


def test_enough_venv_is_refused_by_default(tmp_path, monkeypatch):
    fake_venv(tmp_path, monkeypatch)
    d = entailed(tmp_path, "print(1)\n")
    for kw in ({}, {"owners_code": False}, {"owners_code": "yes"}, {"owners_code": 1}):
        with pytest.raises(sb.Refusal) as e:
            sb.prepare(d, source_kind="authored", root=tmp_path / "runs", package_source="enough-venv", **kw)
        assert e.value.reason == "package-source"
        assert "only to a round trip of the owner's own code" in e.value.sentence
    assert not (tmp_path / "runs").exists()


def test_an_unknown_source_is_refused(tmp_path):
    with pytest.raises(sb.Refusal) as e:
        sb.prepare(entailed(tmp_path, "print(1)\n"), source_kind="authored", root=tmp_path / "runs",
                   package_source="thymop-register", owners_code=True)
    assert e.value.reason == "package-source" and "enough-venv, standard-library" in e.value.sentence


def test_owners_code_still_refuses_what_its_source_cannot_meet(tmp_path, monkeypatch):
    fake_venv(tmp_path, monkeypatch)
    # the owner's code need not be authored; with the default source it is still the standard library only
    d = entailed(tmp_path, "import requests\n")
    with pytest.raises(sb.Refusal) as e:
        sb.prepare(d, source_kind="decompiled", root=tmp_path / "runs", owners_code=True)
    assert e.value.reason == "needs" and "outside the standard library:" in e.value.sentence
    # with enough's packages lent, what they hold is met (by module and by top_level.txt); the rest is not
    sb.prepare(d, source_kind="decompiled", root=tmp_path / "runs", owners_code=True, package_source="enough-venv")
    assert sb.unmet_needs(["requests", "six", "attr", "numpy", "json"], source="enough-venv") == ["numpy"]
    d2 = entailed(tmp_path / "two", "import numpy\n")
    with pytest.raises(sb.Refusal) as e:
        sb.prepare(d2, source_kind="decompiled", root=tmp_path / "runs", owners_code=True,
                   package_source="enough-venv")
    assert "outside the standard library and enough's own packages" in e.value.sentence
    # declared dependencies: met by an installed distribution, refused otherwise
    p = sb.Program(name="t", dependencies=("attrs>=23", "Requests-Extra==1"))
    with pytest.raises(sb.Refusal) as e:
        sb.check_program(p, source="enough-venv")
    assert "`Requests-Extra`" in e.value.sentence and "attrs" not in e.value.sentence
    sb.check_program(sb.Program(name="t", dependencies=("attrs>=23",)), source="enough-venv")


def test_without_a_venv_enough_venv_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(sb, "venv_site_packages", lambda: [])
    with pytest.raises(sb.Refusal) as e:
        sb.prepare(entailed(tmp_path, "print(1)\n"), source_kind="authored", root=tmp_path / "runs",
                   owners_code=True, package_source="enough-venv")
    assert e.value.reason == "package-source" and "virtual environment" in e.value.sentence


def test_the_lent_folders_are_read_only_in_both_boxes(tmp_path, monkeypatch):
    sp = str(fake_venv(tmp_path, monkeypatch))
    own = sb.Run(run_id="r", folder=tmp_path / "r", program=sb.Program(name="t"), original=tmp_path,
                 package_source="enough-venv")
    plain = sb.Run(run_id="p", folder=tmp_path / "p", program=sb.Program(name="t"), original=tmp_path)
    prof = sb.macos_profile(own).splitlines()
    allow = f'(allow file-read* (subpath "{sp}"))'
    assert allow in prof
    assert prof.index(allow) > max(i for i, ln in enumerate(prof) if ln.startswith("(deny file-read*"))
    assert not any(sp in ln for ln in prof if "file-write" in ln)
    assert sp not in sb.macos_profile(plain)
    interp = sb.interpreter()
    a = sb._python_argv(own, ["-m", "t"], sb.Limits(), interp, linux=False)
    assert a[a.index("--path") + 1] == sp and a.index("--path") < a.index("--")
    assert "--path" not in sb._python_argv(plain, ["-m", "t"], sb.Limits(), interp, linux=False)
    la = sb.linux_argv(own, ["-m", "t"], sb.Limits(), "/usr/bin/bwrap", interp)
    assert ("--ro-bind", sp, sp) in list(zip(la, la[1:], la[2:]))
    assert ("--bind", sp, sp) not in list(zip(la, la[1:], la[2:]))
    assert sp not in sb.linux_argv(plain, ["-m", "t"], sb.Limits(), "/usr/bin/bwrap", interp)
    # an interpreter the program starts itself finds the lent folders; a plain run's environment is unchanged
    assert sb.environment(own)["PYTHONPATH"] == sp
    assert "PYTHONPATH" not in sb.environment(plain)


def test_no_door_passes_owners_code_or_the_venv():
    """The routes, the tools and the readvisor never reach the second source: only this module names it."""
    root = Path(sb.__file__).parent
    for p in root.rglob("*.py"):
        if p.name == "sandbox.py":
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        assert "owners_code" not in text and "enough-venv" not in text and "ENOUGH_VENV" not in text, p
    static = root / "static"
    if static.is_dir():
        for p in static.rglob("*"):
            if p.is_file() and p.suffix in (".html", ".js"):
                assert "enough-venv" not in p.read_text(encoding="utf-8", errors="replace"), p


@needs_mac
@pytest.mark.skipif(not sb.venv_site_packages(), reason="needs enough's own virtual environment")
def test_an_owners_code_run_reads_the_venv_and_nothing_more(tmp_path):
    home = tmp_path / "fakehome"
    home.mkdir()
    (home / "secret.txt").write_text("SECRET-KEY-MATERIAL")
    site = sb.venv_site_packages()[0]
    d = entailed(tmp_path, f"""
        import importlib, os, socket, subprocess, sys
        yaml = importlib.import_module("yaml")
        print("YAML", yaml.safe_dump({{"a": 1}}).strip(), "FROM", os.path.dirname(yaml.__file__))
        child = subprocess.run([sys.executable, "-c", "import yaml; print('CHILD-YAML')"], capture_output=True,
                               text=True)
        print(child.stdout.strip())
        for what, f in (("write-venv", lambda: open(os.path.join({site!r}, "planted.py"), "w").write("x")),
                        ("read-home", lambda: open({str(home / "secret.txt")!r}).read()),
                        ("net", lambda: socket.create_connection(("127.0.0.1", 9), timeout=2)),
                        ("enough-by-pth", lambda: importlib.import_module("enough"))):
            try:
                print(what, "GOT", f())
            except Exception as e:
                print(what, "REFUSED", type(e).__name__)
    """)
    run = sb.prepare(d, source_kind="rebuilt", root=tmp_path / "runs", owners_code=True,
                     package_source="enough-venv")
    r = sb.run_tool(run, limits=sb.Limits(wall=60, grace=1))
    assert r.exit_code == 0, r.stderr
    assert "YAML a: 1 FROM " + site in r.stdout and "CHILD-YAML" in r.stdout
    for what in ("write-venv", "read-home", "net", "enough-by-pth"):
        assert f"{what} REFUSED" in r.stdout, r.stdout
    assert not os.path.exists(os.path.join(site, "planted.py"))
    assert "SECRET-KEY-MATERIAL" not in r.stdout + r.stderr
    assert r.guarantees["packages"].startswith("enough-venv: ") and "nothing fetched" in r.guarantees["packages"]
    # the same program with the default source: the box does not lend the packages
    run2 = sb.prepare(d, source_kind="rebuilt", root=tmp_path / "runs", owners_code=True)
    r2 = sb.run_tool(run2, limits=sb.Limits(wall=60, grace=1))
    assert "ModuleNotFoundError" in r2.stderr and "YAML" not in r2.stdout
    assert r2.guarantees["packages"] == "standard-library"
