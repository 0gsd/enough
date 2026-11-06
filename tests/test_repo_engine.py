"""The engines the fabulac moves reach the outside through (`enough.repo_engine`): `repo` and `syntax`.

A repository is untrusted data. The syntax engine reads Python by its syntax tree and packaging files as text, and
never runs or imports anything. The history is read by one fixed git binary with every configuration-driven way to
execute something closed: a hostile `.git/config` (an fsmonitor hook, a pager, an external diff, a textconv driver, a
signature verifier, hooks) runs nothing, which a canary file proves, while the same config does run its program under
a plain `git` call (so the canary is a real one). Repositories here are made in tmp_path from scripted commits.
"""
from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

from enough import macrocosm as mc
from enough import repo_engine as RE

REPO = Path(__file__).resolve().parents[1]
TINY = REPO / "tests" / "fixtures" / "thym" / "inputs" / "tiny-tool"
TALLY = REPO / "tests" / "fixtures" / "fabula" / "tally"
needs_git = pytest.mark.skipif(RE.git_binary() is None, reason="git is not installed here")


def _env(home: Path, who: str = "Ann Example", when: str = "2026-10-01T10:00:00+00:00") -> dict:
    return {"PATH": "/usr/bin:/bin", "HOME": str(home), "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_AUTHOR_NAME": who, "GIT_AUTHOR_EMAIL": "ann@example.com", "GIT_COMMITTER_NAME": who,
            "GIT_COMMITTER_EMAIL": "ann@example.com", "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when}


def git(repo: Path, *args: str, stdin: bytes | None = None, **kw) -> bytes:
    return subprocess.run([RE.git_binary(), "-C", str(repo), *args], check=True, env=_env(repo.parent, **kw),
                          capture_output=True, input=stdin).stdout


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / "a.py").write_text("x = 1\n")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "Add a <ann@example.com>", "-m", "Why: we needed it, ask bo@example.org.\n\n"
        "Signed-off-by: Ann Example <ann@example.com>\nCo-Authored-By: Bo <bo@example.org>")
    git(repo, "tag", "v1")
    return repo


# ---------------------------------------------------------------------------
# syntax
# ---------------------------------------------------------------------------

def test_the_outline_of_a_python_file_is_read_from_its_syntax_tree():
    ol = RE.outline("tally/cli.py", (TALLY / "tally" / "cli.py").read_text())
    assert ol["ok"] and ol["lines"] == 62 and ol["doc"] == "tally: count things from the command line."
    main = next(d for d in ol["defs"] if d["qual"] == "main")
    assert main["signature"] == "def main(argv: list[str] | None = None) -> int" and (main["line"], main["end"]) == (32, 58)
    assert main["params"] == [{"name": "argv", "kind": "positional", "annotation": "list[str] | None",
                               "default": "None"}]
    assert ol["main"] == 61 and ol["main_calls"] == ["main"]
    imports = {i["module"]: i for i in ol["imports"]}
    assert imports["argparse"]["stdlib"] is True and imports[""]["level"] == 1
    parsers = {p.get("command") or p.get("prog"): p for p in ol["argparse"]}
    assert set(parsers) == {"tally", "add", "show", "undo"}
    assert parsers["add"]["args"][1] == {"names": ["n"], "line": 24, "type": "int", "default": "1", "nargs": "?"}
    assert parsers["show"]["args"][0]["action"] == "store_true"


def test_the_outline_reads_classes_methods_constants_all_and_the_environment():
    text = ('"""m."""\nimport os\n__all__ = ["A", "f"]\nLIMIT = 3\nPAT = object()\n\n@dataclass(frozen=True)\n'
            'class A(Base, metaclass=M):\n    """An A."""\n    at: float\n    name: str = "x"\n\n'
            '    def go(self, n: int, *, fast=False) -> None:\n        return os.getenv("A_MODE", "slow")\n\n'
            'async def f(a, /, b=2, *args, c, **kw):\n    return os.environ["F_KEY"]\n')
    ol = RE.outline("m.py", text)
    defs = {d["qual"]: d for d in ol["defs"]}
    assert defs["A"]["signature"] == "class A(Base, metaclass=M)" and defs["A"]["decorators"] == [
        "dataclass(frozen=True)"]
    assert defs["A"]["fields"] == [{"name": "at", "annotation": "float", "line": 10},
                                   {"name": "name", "annotation": "str", "line": 11, "default": '"x"'}]
    assert defs["A.go"]["signature"] == "def go(self, n: int, *, fast=False) -> None" and defs["A.go"]["kind"] == "method"
    assert defs["f"]["signature"] == "async def f(a, /, b=2, *args, c, **kw)"
    assert ol["all"] == ["A", "f"] and ol["constants"] == [
        {"name": "LIMIT", "value": "3", "line": 4},
        {"name": "PAT", "value": "object()", "line": 5, "literal": False}]       # a value that is no literal, as written
    assert ol["env"] == [{"key": "A_MODE", "line": 14, "default": '"slow"', "in": "A.go"},
                         {"key": "F_KEY", "line": 17, "in": "f"}]


def test_parse_says_where_a_file_breaks_and_runs_nothing(tmp_path):
    canary = tmp_path / "canary"
    text = f"import pathlib\npathlib.Path({str(canary)!r}).write_text('ran')\n"
    assert RE.parse("ok.py", text) == {"ok": True}
    assert RE.outline("ok.py", text)["ok"]
    assert not canary.exists()
    bad = RE.parse("bad.py", "def f(:\n    pass\n")
    assert bad["ok"] is False and bad["line"] == 1 and bad["message"]
    assert RE.parse("x.js", "let x")["ok"] is None and "Python only" in RE.parse("x.js", "")["why"]
    assert RE.outline("x.rs", "fn main(){}")["ok"] is None


def test_packaging_files_are_read_as_text_never_run():
    m = RE.manifest("pyproject.toml", (TINY / "pyproject.toml").read_text())
    assert (m["name"], m["requires_python"], m["licence"]) == ("tiny-tool", ">=3.10", "MIT")
    assert m["dependencies"] == [{"package": "pytest", "version": ">=8", "scope": "test", "group": "test", "line": 10}]
    assert m["scripts"] == [{"name": "tiny", "target": "tiny.cli:main", "line": 13}]
    assert m["build"]["backend"] == "setuptools.build_meta"
    cfg = RE.manifest("setup.cfg", "[metadata]\nname = a\nlicense = BSD\n[options]\npython_requires = >=3.9\n"
                                   "install_requires =\n    requests>=2\n[options.entry_points]\nconsole_scripts =\n"
                                   "    a = a.cli:main\n")
    assert cfg["licence"] == "BSD" and cfg["dependencies"][0]["package"] == "requests"
    assert cfg["scripts"][0]["target"] == "a.cli:main"
    req = RE.manifest("requirements-dev.txt", "# x\npytest==8.0\n-e .\n")
    assert req["dependencies"] == [{"package": "pytest", "version": "==8.0", "scope": "test", "line": 2}]
    assert RE.manifest("setup.py", "import os; os.system('x')")["ok"] is None
    assert RE.manifest("pyproject.toml", "[project\n")["ok"] is False


def test_the_tree_counts_are_macrocosms():
    assert RE.tree(TALLY) == {k: mc.tree_digest(TALLY)[k] for k in ("files", "bytes", "skipped", "tree")}
    assert [f["path"] for f in RE.files(TINY)][:3] == ["CHANGES.md", "LICENSE", "README.md"]


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------

@needs_git
def test_history_answers_only_what_the_moves_read_and_never_an_address(tmp_path):
    repo = make_repo(tmp_path)
    h = RE.history(repo)
    assert h["clone"] is True and h["shallow"] is False and h["truncated"] is False
    (c,) = h["commits"]
    assert set(c) == {"sha", "at", "author", "subject", "body", "paths"}
    assert (c["at"], c["author"], c["subject"], c["body"], c["paths"]) == (
        "2026-10-01T10:00:00Z", "Ann Example", "Add a", "Why: we needed it, ask .", ["a.py"])
    assert h["tags"] == [{"name": "v1", "sha": c["sha"], "at": "2026-10-01T10:00:00Z"}]
    assert "@" not in repr(h)


def test_history_of_what_is_no_clone_says_why(tmp_path, monkeypatch):
    assert RE.history(TINY) == {"clone": False,
                                "why": "the folder is not a git clone (it has no .git folder of its own)"}
    d = tmp_path / "w"
    d.mkdir()
    (d / ".git").write_text("gitdir: /elsewhere\n")
    assert "worktree or a submodule" in RE.history(d)["why"]
    e = tmp_path / "l"
    e.mkdir()
    (e / ".git").symlink_to(tmp_path)
    assert "symbolic link" in RE.history(e)["why"]
    g = tmp_path / "g"
    (g / ".git").mkdir(parents=True)
    monkeypatch.setattr(RE, "GIT_CANDIDATES", ("/nonexistent/git",))
    assert RE.history(g) == {"clone": False, "why": "git is not installed here"}


@needs_git
def test_an_empty_clone_is_refused_by_git_in_plain_words(tmp_path):
    repo = tmp_path / "e"
    repo.mkdir()
    git(repo, "init", "-q")
    h = RE.history(repo)
    assert h["clone"] is False and h["why"].startswith("git refused: ")


def test_git_runs_with_nothing_of_the_callers_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_DIR", "/evil")
    monkeypatch.setenv("GIT_EXTERNAL_DIFF", "/evil/diff")
    monkeypatch.setenv("GIT_SSH_COMMAND", "/evil/ssh")
    monkeypatch.setenv("PAGER", "/evil/pager")
    env = RE.git_env(tmp_path / ".git")
    assert env["GIT_DIR"] == str(tmp_path / ".git") and "GIT_EXTERNAL_DIFF" not in env
    assert "GIT_SSH_COMMAND" not in env and env["PAGER"] == "cat" and env["GIT_CONFIG_GLOBAL"] == "/dev/null"
    for o in ("core.fsmonitor=false", "core.hooksPath=/dev/null", "diff.external=", "core.pager=cat",
              "protocol.allow=never", "log.showSignature=false"):
        assert o in RE.GIT_OVERRIDES


def _canary_program(tmp_path: Path) -> tuple[Path, Path]:
    canary = tmp_path / "CANARY"
    prog = tmp_path / "evil.sh"
    prog.write_text(f"#!/bin/sh\necho ran \"$0\" \"$@\" >> {canary}\nexit 1\n")
    prog.chmod(prog.stat().st_mode | stat.S_IXUSR)
    return prog, canary


def _sign(repo: Path) -> None:
    """Rewrite HEAD as a commit that carries an (unverifiable) OpenPGP signature: `log --show-signature` hands it to
    gpg.program."""
    raw = git(repo, "cat-file", "commit", "HEAD").decode()
    head, _, msg = raw.partition("\n\n")
    sig = ("gpgsig -----BEGIN PGP SIGNATURE-----\n \n iQEzBAABCAAdFiEE\n =abcd\n -----END PGP SIGNATURE-----")
    signed = f"{head}\n{sig}\n\n{msg}"
    sha = git(repo, "hash-object", "-t", "commit", "-w", "--stdin", stdin=signed.encode()).decode().strip()
    git(repo, "update-ref", "refs/heads/main", sha)


@needs_git
def test_a_hostile_git_config_runs_nothing(tmp_path):
    repo = make_repo(tmp_path)
    _sign(repo)
    prog, canary = _canary_program(tmp_path)
    hooks = repo / ".git" / "hooks"
    for h in ("post-checkout", "pre-commit", "reference-transaction", "post-index-change"):
        (hooks / h).write_text(f"#!/bin/sh\n{prog} hook\n")
        (hooks / h).chmod(0o755)
    (repo / ".git" / "info").mkdir(exist_ok=True)
    (repo / ".git" / "info" / "attributes").write_text("* diff=evil\n")
    with open(repo / ".git" / "config", "a") as fh:
        fh.write(f"[core]\n\tfsmonitor = {prog}\n\tpager = {prog}\n\tsshCommand = {prog}\n"
                 f"[diff]\n\texternal = {prog}\n[diff \"evil\"]\n\ttextconv = {prog}\n\tcommand = {prog}\n"
                 f"[log]\n\tshowSignature = true\n[gpg]\n\tprogram = {prog}\n[pager]\n\tlog = {prog}\n"
                 f"[credential]\n\thelper = !{prog}\n[include]\n\tpath = {tmp_path / 'more.cfg'}\n")
    (tmp_path / "more.cfg").write_text(f"[core]\n\tfsmonitor = {prog}\n")
    # the canary is real: a plain git, isolated only from the caller's own config, runs the repository's programs
    plain = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "GIT_CONFIG_NOSYSTEM": "1",
             "GIT_CONFIG_GLOBAL": "/dev/null"}
    subprocess.run([RE.git_binary(), "-C", str(repo), "log", "-1"], env=plain, capture_output=True)
    subprocess.run([RE.git_binary(), "-C", str(repo), "status"], env=plain, capture_output=True)
    assert canary.exists(), "the hostile config should run its program under a plain git"
    canary.unlink()
    h = RE.history(repo)
    assert h["clone"] is True and len(h["commits"]) == 1 and h["tags"][0]["name"] == "v1"
    assert not canary.exists(), canary.read_text()
    assert os.listdir(hooks)                      # the hooks are there, and never ran


@needs_git
def test_a_shallow_clone_says_so(tmp_path):
    repo = make_repo(tmp_path)
    (repo / ".git" / "shallow").write_text(git(repo, "rev-parse", "HEAD").decode())
    assert RE.history(repo)["shallow"] is True


def test_the_outline_reads_data_shapes_and_the_words_a_user_sees():
    text = ('import enum, sys, logging\nfrom dataclasses import dataclass\nfrom typing import NamedTuple, TypedDict\n'
            'log = logging.getLogger(__name__)\n\n@dataclass\nclass P:\n    x: int\n    y: int = 0\n\n'
            'class Pair(NamedTuple):\n    a: str\n\nclass Row(TypedDict):\n    k: str\n\n'
            'class Colour(enum.Enum):\n    RED = "r"\n    BLUE = "b"\n\n'
            'def main(argv=None) -> int:\n    if argv:\n        print(f"bad: {argv!r}", file=sys.stderr)\n'
            '        return 2\n    log.warning("careful %s", argv)\n    print("done")\n    if not argv:\n'
            '        raise ValueError(f"need {len(argv)} things")\n    sys.exit("stopped")\n    return 0\n')
    ol = RE.outline("m.py", text)
    d = {x["qual"]: x for x in ol["defs"]}
    assert (d["P"]["shape"], d["Pair"]["shape"], d["Row"]["shape"], d["Colour"]["shape"]) == (
        "dataclass", "NamedTuple", "TypedDict", "enum")
    assert d["Colour"]["fields"] == [{"name": "RED", "default": '"r"', "line": 18},
                                     {"name": "BLUE", "default": '"b"', "line": 19}]
    words = d["main"]["words"]
    assert words == [
        {"kind": "print", "stream": "stderr", "text": "bad: {argv!r}", "line": 23, "exit": 2},
        {"kind": "log", "level": "warning", "text": "careful %s", "line": 25},
        {"kind": "print", "stream": "stdout", "text": "done", "line": 26},
        {"kind": "raise", "error": "ValueError", "text": "need {len(argv)} things", "line": 28},
        {"kind": "exit", "text": "stopped", "code": 1, "line": 29}]
    assert d["main"]["returns_int"] == [0, 2]
    p = RE.outline("cli.py", 'import argparse\np = argparse.ArgumentParser(prog="x", epilog="See the README.")\n'
                             'p.add_argument("--mode", choices=["a", "b"], metavar="M", help="how")\n')
    assert p["argparse"][0]["epilog"] == "See the README."
    assert p["argparse"][0]["args"][0]["choices"] == '["a", "b"]' and p["argparse"][0]["args"][0]["metavar"] == "M"


def test_the_outline_reads_real_code_shapes():
    """What real repositories hold (lane G1): definitions under `if`/`try`, `__all__` grown by `append`, nested
    classes, a property's setter folded into it, overloads gathered on their function, type aliases and values that
    are no literal, class attributes, and the docstring with its doctest examples (parsed, never run)."""
    text = ('from typing import Union, overload\n'
            'try:\n    import fast\n    HAS_FAST = True\nexcept ImportError:\n    HAS_FAST = False\n'
            '__all__ = ["Box", "go"]\n'
            'Event = Union[int, str]\n'
            'PAT = re.compile("a")  # a pattern\n'
            'class Box:\n    """A box.\n\n    More about it.\n\n    >>> Box().size\n    0\n    """\n'
            '    __marker = object()\n'
            '    class Inner:\n        def go(self): pass\n'
            '    @property\n    def size(self): return 0\n'
            '    @size.setter\n    def size(self, v): pass\n'
            '@overload\ndef go(a: int) -> int: ...\n@overload\ndef go(a: str) -> str: ...\ndef go(a): return a\n'
            'if HAS_FAST:\n    class Fast(Box):\n        pass\n    __all__.append("Fast")\n')
    ol = RE.outline("m.py", text)
    defs = {d["qual"]: d for d in ol["defs"]}
    assert ol["all"] == ["Box", "go", "Fast"]
    assert defs["Fast"]["cond"] == "if HAS_FAST" and defs["Box.Inner"]["nested"] and "Box.Inner.go" in defs
    assert defs["Box.size"]["setter"] is True and [d["qual"] for d in ol["defs"]].count("Box.size") == 1
    assert defs["go"]["overloads"] == ["def go(a: int) -> int", "def go(a: str) -> str"]
    assert defs["Box"]["attrs"] == [{"name": "__marker", "value": "object()", "line": 18}]
    assert defs["Box"]["docstring"].startswith("A box.") and defs["Box"]["examples"] == [
        {"source": "Box().size", "want": "0"}]
    consts = {c["name"]: c for c in ol["constants"]}
    assert consts["Event"]["alias"] and consts["Event"]["literal"] is False
    assert consts["PAT"]["value"] == 're.compile("a")' and "alias" not in consts["PAT"]
    assert consts["HAS_FAST"]["value"] == "True" and consts["HAS_FAST"]["cond"] == "try"
    assert consts["HAS_FAST"]["also"] == [{"value": "False", "cond": "except ImportError", "line": 6}]
