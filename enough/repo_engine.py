"""The engines the fabulac moves reach the outside through: `repo` (a folder's files and a clone's history) and
`syntax` (a language's syntax, for Python from `ast`) (THYM 20, 20.8; MacroCOSM OES 18.4.7).

A Thym move never reads the disk or runs a parser itself: it asks `ctx.engines["repo"]` and `ctx.engines["syntax"]`,
and every call it makes is recorded by the runtime (`enough.thym.engines.Recording`), so a replay answers from the
record and needs neither the repository, nor git, nor a parser. Each function answers only the fields the moves read,
in plain data (strings, integers, booleans, lists, mappings; never a float), so that the records stay small and
portable (THYM 12.6).

**A repository is untrusted data.** Nothing in it is executed, imported, installed or sourced:

- `syntax` reads Python with `ast.parse` on the text. Parsing is not running: nothing is imported, nothing is compiled
  to a file, no code object is executed. Packaging files are read as text (`tomllib` for `pyproject.toml`,
  `configparser` with interpolation off for `setup.cfg`, lines for `requirements*.txt`); `setup.py` is never run and
  is read, like any Python file, by its syntax tree only.
- `repo.history` runs one fixed, absolute `git` binary, never through a shell, with a scrubbed environment, a
  timeout, an output cap and command-line overrides that neutralise every configuration-driven way the repository's
  own `.git/config` could make git execute something (see `GIT_OVERRIDES`, `git_env` and docs/fabula-landed-T1-code.md
  for the reason behind each). It runs only `log` and `for-each-ref` (read-only; neither touches the index, the work
  tree or the network). Where git is absent, the folder is not a clone of its own, or git refuses, the answer says
  `clone: false` with the reason in plain words, and the move records the history as a question, never a guess.

Host wiring (enough/thym_host.py): `engines()` here gives `{"repo": ..., "syntax": ...}` to merge into the host's.
"""
from __future__ import annotations

import ast
import configparser
import datetime as dt
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from enough import macrocosm as mc
from enough.thym import folder as _folder

# ---------------------------------------------------------------------------
# repo: files, text, tree, history
# ---------------------------------------------------------------------------

#: The git binaries tried, in order: absolute paths only, never a PATH lookup (a PATH entry could be anything).
GIT_CANDIDATES = ("/usr/bin/git", "/opt/homebrew/bin/git", "/usr/local/bin/git", "/bin/git")
#: Seconds one git command may take; output beyond `GIT_MAX_BYTES` is refused, not read.
GIT_TIMEOUT = 20
GIT_MAX_BYTES = 8 * 1024 * 1024
#: At most this many commits are read (newest first); a repository of the band holds far fewer.
MAX_COMMITS = 400
MAX_BODY = 600
MAX_PATHS = 60

#: `-c` overrides given on every git command line. Command-line configuration outranks every file, the repository's
#: own `.git/config` (and anything it `include`s) among them. Each closes one way a hostile config could run a program.
GIT_OVERRIDES = (
    "core.fsmonitor=false",          # a hook program git runs to learn which files changed (index-reading commands)
    "core.hooksPath=/dev/null",      # no hook is ever found
    "core.pager=cat",                # the pager is a shell command; also GIT_PAGER/PAGER and --no-pager
    "pager.log=false",
    "core.editor=true",              # never invoked by log; set so a mistake cannot open an editor program
    "core.askPass=",                 # no credential helper program
    "credential.helper=",
    "core.sshCommand=false",         # transports are forbidden below; belt and braces
    "protocol.allow=never",          # no transport at all: no fetch of a partial clone's missing objects
    "diff.external=",                # an external diff program (also --no-ext-diff)
    "log.showSignature=false",       # verifying a signed commit runs gpg.program (also --no-show-signature)
    "gpg.program=false",
    "gpg.ssh.program=false",
    "gpg.x509.program=false",
    "core.attributesFile=/dev/null",  # attributes name diff drivers and filters; none is read from outside the clone
    "log.mailmap=false",
    "core.untrackedCache=false",
    "core.splitIndex=false",
    "index.skipHash=false",
    "color.ui=false",
    "log.decorate=false",
    "i18n.logOutputEncoding=UTF-8",
    "core.quotePath=false",
)


def git_binary() -> str | None:
    """The first of `GIT_CANDIDATES` that is an executable regular file, or None."""
    for p in GIT_CANDIDATES:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def git_env(git_dir: Path) -> dict:
    """The whole environment a git command runs with: nothing inherited (no GIT_* of the caller's, no PAGER, no
    EDITOR, no SSH command), system and global configuration off, no optional locks, no prompt, no lazy fetch, no
    replace objects, discovery stopped at the clone's parent."""
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": "/nonexistent",
        "LC_ALL": "C",
        "GIT_DIR": str(git_dir),
        "GIT_CEILING_DIRECTORIES": str(git_dir.parent.parent),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_PAGER": "cat",
        "PAGER": "cat",
        "GIT_ASKPASS": "/usr/bin/false",
        "SSH_ASKPASS": "/usr/bin/false",
    }


def run_git(git_dir: Path, args: list[str], *, timeout: int = GIT_TIMEOUT) -> tuple[bool, bytes, str]:
    """One read-only git command against `git_dir`: `(ok, stdout, why)`. Never a shell, never a tty, stdin closed,
    the working directory the clone's own `.git` (never the caller's), the overrides and environment above."""
    git = git_binary()
    if git is None:
        return False, b"", "git is not installed here"
    cmd = [git, "--no-pager", "--no-replace-objects", "--literal-pathspecs", f"--git-dir={git_dir}"]
    for o in GIT_OVERRIDES:
        cmd += ["-c", o]
    cmd += list(args)
    try:
        proc = subprocess.run(cmd, cwd=str(git_dir), env=git_env(git_dir), stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, shell=False,
                              close_fds=True, check=False)
    except subprocess.TimeoutExpired:
        return False, b"", f"git took longer than {timeout} seconds"
    except OSError as e:
        return False, b"", f"git could not be started ({e.strerror or 'the system refused'})"
    if len(proc.stdout) > GIT_MAX_BYTES:
        return False, b"", "git's answer is larger than this build reads"
    if proc.returncode != 0:
        first = proc.stderr.decode("utf-8", "replace").strip().splitlines()[:1]
        return False, b"", "git refused: " + _scrub(first[0] if first else f"exit status {proc.returncode}")
    return True, proc.stdout, ""


_EMAIL = re.compile(r"<?[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}>?")
_TRAILER = re.compile(r"^[A-Za-z][A-Za-z-]*-by:\s.*$", re.M | re.I)


def _scrub(s: str) -> str:
    """Text with every e-mail address and every `*-by:` trailer taken out: no address ever leaves the engine."""
    s = _TRAILER.sub("", s)
    s = _EMAIL.sub("", s)
    s = re.sub(r"[ \t]+\n", "\n", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def _utc(stamp: str) -> str | None:
    try:
        t = dt.datetime.fromisoformat(stamp.strip())
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _root(folder: Any) -> Path | None:
    """The folder on disk: a Thym folder value, a `Folder`, or a path."""
    p = getattr(folder, "payload", folder)
    if isinstance(p, _folder.Folder):
        return p.root
    if isinstance(p, (str, Path)):
        return Path(p)
    return None


def _clone_dir(root: Path | None) -> tuple[Path | None, str]:
    if root is None:
        return None, "the folder was read from a snapshot, and a snapshot holds no history"
    g = root / ".git"
    if g.is_symlink():
        return None, "its .git is a symbolic link, which is never followed"
    if g.is_file():
        return None, "its .git is a file (a worktree or a submodule), which this build does not follow"
    if not g.is_dir():
        return None, "the folder is not a git clone (it has no .git folder of its own)"
    return g, ""


def history(folder: Any, *, limit: int = MAX_COMMITS) -> dict:
    """A clone's history, read by `git log` and `git for-each-ref` only: `{clone: true, shallow, truncated,
    commits: [{sha, at, author, subject, body, paths}], tags: [{name, sha, at}]}`, newest commit first; `at` in UTC
    (`YYYY-MM-DDTHH:MM:SSZ`); an author's name only, never an address; bodies without trailers or addresses. Or
    `{clone: false, why}`."""
    g, why = _clone_dir(_root(folder))
    if g is None:
        return {"clone": False, "why": why}
    fmt = "--format=%x1e%H%x1f%aI%x1f%an%x1f%s%x1f%b%x1f"
    ok, out, why = run_git(g, ["log", "--no-color", "--no-decorate", "--no-renames", "--no-ext-diff",
                               "--no-textconv", "--no-show-signature", "-z", "--name-only", f"--max-count={limit + 1}",
                               fmt, "HEAD", "--"])
    if not ok:
        return {"clone": False, "why": why}
    commits = []
    for rec in out.decode("utf-8", "replace").split("\x1e")[1:]:
        parts = rec.split("\x1f")
        if len(parts) < 6:
            continue
        sha, at, author, subject, body, tail = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
        paths = [p for p in tail.replace("\n", "\0").split("\0") if p.strip()]
        name = _scrub(author).strip() or "unknown"
        commits.append({"sha": sha.strip(), "at": _utc(at) or at.strip(), "author": name,
                        "subject": _scrub(subject)[:200], "body": _scrub(body)[:MAX_BODY],
                        "paths": sorted(set(paths))[:MAX_PATHS]})
    truncated = len(commits) > limit
    commits = commits[:limit]
    ok, out, why = run_git(g, ["for-each-ref", "--format=%(refname:strip=2)%1f%(objectname)%1f%(*objectname)%1f"
                                               "%(creatordate:iso-strict)", "refs/tags"])
    tags = []
    if ok:
        for line in out.decode("utf-8", "replace").splitlines():
            f = line.split("\x1f")
            if len(f) == 4 and f[0]:
                tags.append({"name": f[0], "sha": (f[2] or f[1]).strip(), "at": _utc(f[3]) or f[3].strip()})
    return {"clone": True, "shallow": (g / "shallow").is_file(), "truncated": truncated, "commits": commits,
            "tags": sorted(tags, key=lambda t: (t["at"], t["name"]))}


def tree(folder: Any) -> dict:
    """MacroCOSM's counts of the files read (OES 18.4.1): `{files, bytes, skipped, tree}`."""
    root = _root(folder)
    if root is None:
        raise ValueError("the folder is not on disk")
    got = mc.tree_digest(root)
    return {k: got[k] for k in ("files", "bytes", "skipped", "tree")}


def files(folder: Any) -> list[dict]:
    """The files Thym's folder rule keeps (THYM 20.1): `[{path, sha256, size, binary}]` in path order."""
    root = _root(folder)
    f = _folder.read(root) if root is not None else getattr(folder, "payload", None)
    return [{"path": e.path, "sha256": e.sha256, "size": e.size, "binary": e.binary} for e in f.entries]


def text(folder: Any, path: str) -> str:
    """One text file's text, under the folder rule (a link or a binary file is refused)."""
    root = _root(folder)
    return _folder.read(root).text(path)


REPO = SimpleNamespace(history=history, tree=tree, files=files, text=text)


# ---------------------------------------------------------------------------
# syntax: Python's outline, parse, and the packaging files
# ---------------------------------------------------------------------------

LANGUAGES = {"py": "python", "pyi": "python", "md": "markdown", "rst": "restructuredtext", "txt": "text",
             "toml": "toml", "cfg": "ini", "ini": "ini", "json": "json", "yaml": "yaml", "yml": "yaml", "js": "javascript",
             "ts": "typescript", "c": "c", "h": "c", "rs": "rust", "go": "go", "sh": "shell", "html": "html",
             "css": "css", "in": "text"}


def language(path: str) -> str:
    name = path.rsplit("/", 1)[-1]
    if "." not in name:
        return "text"
    return LANGUAGES.get(name.rsplit(".", 1)[1].lower(), "other")


def parse(path: str, text: str) -> dict:
    """`{ok: true}` or `{ok: false, line, message}` for a file in a language this edition parses (Python), by
    `ast.parse` on the text; `{ok: null, why}` for any other language. Nothing is imported or executed."""
    if language(path) != "python":
        return {"ok": None, "why": f"{path} is not Python, and this edition parses Python only"}
    try:
        ast.parse(text, filename=path)
    except SyntaxError as e:
        return {"ok": False, "line": int(e.lineno or 0), "message": str(e.msg or "invalid syntax")}
    except ValueError as e:                        # a NUL byte
        return {"ok": False, "line": 0, "message": str(e)}
    return {"ok": True}


def _seg(text: str, node: ast.AST | None) -> str | None:
    if node is None:
        return None
    s = ast.get_source_segment(text, node)
    return " ".join(s.split()) if s is not None else ast.unparse(node)


def _doc1(node: ast.AST) -> str | None:
    d = ast.get_docstring(node, clean=True) if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                                                 ast.AsyncFunctionDef)) else None
    if not d:
        return None
    first = d.strip().split("\n\n", 1)[0]
    return " ".join(first.split())[:300]


def _params(text: str, a: ast.arguments) -> list[dict]:
    out: list[dict] = []
    pos = list(a.posonlyargs) + list(a.args)
    defaults = [None] * (len(pos) - len(a.defaults)) + list(a.defaults)
    for i, (arg, d) in enumerate(zip(pos, defaults)):
        kind = "positional-only" if i < len(a.posonlyargs) else "positional"
        out.append(_param(text, arg, d, kind))
    if a.vararg:
        out.append(_param(text, a.vararg, None, "var-positional"))
    for arg, d in zip(a.kwonlyargs, a.kw_defaults):
        out.append(_param(text, arg, d, "keyword-only"))
    if a.kwarg:
        out.append(_param(text, a.kwarg, None, "var-keyword"))
    return out


def _param(text: str, arg: ast.arg, default: ast.AST | None, kind: str) -> dict:
    p: dict = {"name": arg.arg, "kind": kind}
    if arg.annotation is not None:
        p["annotation"] = _seg(text, arg.annotation)
    if default is not None:
        p["default"] = _seg(text, default)
    return p


def _signature(text: str, node: ast.AST) -> str:
    """The `def` or `class` line as written: name, parameters with annotations and defaults, the return annotation,
    or the bases and keywords; whitespace folded to one line."""
    if isinstance(node, ast.ClassDef):
        bases = [_seg(text, b) for b in node.bases] + [f"{k.arg}={_seg(text, k.value)}" if k.arg else
                                                       f"**{_seg(text, k.value)}" for k in node.keywords]
        return f"class {node.name}({', '.join(bases)})" if bases else f"class {node.name}"
    a = node.args                                       # type: ignore[attr-defined]
    parts: list[str] = []
    pos = list(a.posonlyargs) + list(a.args)
    defaults = [None] * (len(pos) - len(a.defaults)) + list(a.defaults)

    def one(arg: ast.arg, d: ast.AST | None, star: str = "") -> str:
        s = star + arg.arg
        if arg.annotation is not None:
            s += f": {_seg(text, arg.annotation)}"
            if d is not None:
                s += f" = {_seg(text, d)}"
        elif d is not None:
            s += f"={_seg(text, d)}"
        return s
    for i, (arg, d) in enumerate(zip(pos, defaults)):
        parts.append(one(arg, d))
        if a.posonlyargs and i == len(a.posonlyargs) - 1:
            parts.append("/")
    if a.vararg:
        parts.append(one(a.vararg, None, "*"))
    elif a.kwonlyargs:
        parts.append("*")
    for arg, d in zip(a.kwonlyargs, a.kw_defaults):
        parts.append(one(arg, d))
    if a.kwarg:
        parts.append(one(a.kwarg, None, "**"))
    head = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    ret = f" -> {_seg(text, node.returns)}" if node.returns is not None else ""    # type: ignore[attr-defined]
    return f"{head} {node.name}({', '.join(parts)}){ret}"                              # type: ignore[attr-defined]


def _literal(text: str, node: ast.AST) -> str | None:
    """A module-level value as written, when it is a literal (a number, a string, a tuple or list of them, a
    negative number, an f-string-free constant); None otherwise. At most 200 characters."""
    try:
        ast.literal_eval(node)
    except Exception:  # noqa: BLE001 - not a literal: not a constant the outline names
        return None
    s = _seg(text, node) or ""
    return s if len(s) <= 200 else s[:199] + "…"


def _str_arg(node: ast.AST | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _env_reads(text: str, tree: ast.AST, owners: dict[int, str]) -> list[dict]:
    """Every literal environment variable read: `os.environ["K"]`, `os.environ.get("K", d)`, `os.getenv("K", d)`,
    `environ.get(...)`, `env.get("K")` on a parameter called env; with its default as written and the function it
    is read in."""
    out: list[dict] = []

    def is_environ(n: ast.AST) -> bool:
        return (isinstance(n, ast.Attribute) and n.attr == "environ") or (isinstance(n, ast.Name) and
                                                                          n.id in ("environ", "env"))
    for n in ast.walk(tree):
        key = default = None
        if isinstance(n, ast.Subscript) and is_environ(n.value):
            key = _str_arg(n.slice)
        elif isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute) and f.attr in ("get", "setdefault", "pop") and is_environ(f.value) \
                    or isinstance(f, ast.Attribute) and f.attr == "getenv" \
                    or isinstance(f, ast.Name) and f.id == "getenv":
                key = _str_arg(n.args[0]) if n.args else None
                if len(n.args) > 1:
                    default = _seg(text, n.args[1])
        if key and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            row = {"key": key, "line": int(getattr(n, "lineno", 0))}
            if default is not None:
                row["default"] = default
            owner = owners.get(row["line"])
            if owner:
                row["in"] = owner
            out.append(row)
    seen: set = set()
    rows = []
    for r in sorted(out, key=lambda r: (r["line"], r["key"])):
        if (r["key"], r.get("in")) not in seen:
            seen.add((r["key"], r.get("in")))
            rows.append(r)
    return rows


def _kw(call: ast.Call, name: str) -> ast.AST | None:
    return next((k.value for k in call.keywords if k.arg == name), None)


def _argparse(text: str, tree: ast.AST) -> list[dict]:
    """The command lines argparse builds, read from the calls as written (never run): each parser (`ArgumentParser`
    or a sub-command's `add_parser`) with its `prog` or sub-command name, description or help, and its arguments in
    order: `{names, dest, action, type, default, nargs, choices, required, help, line}`, every value as written."""
    parsers: dict[str, dict] = {}
    subs: dict[str, str] = {}                 # subparsers variable -> parent parser variable
    order: list[str] = []

    def target(n: ast.AST) -> str | None:
        return n.id if isinstance(n, ast.Name) else (f"self.{n.attr}" if isinstance(n, ast.Attribute) and
                                                     isinstance(n.value, ast.Name) else None)

    for n in ast.walk(tree):
        if not isinstance(n, ast.Assign) or len(n.targets) != 1 or not isinstance(n.value, ast.Call):
            continue
        var, call = target(n.targets[0]), n.value
        f = call.func
        fname = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
        if var is None:
            continue
        if fname == "ArgumentParser":
            parsers[var] = {"var": var, "prog": _str_arg(_kw(call, "prog")), "parent": None, "command": None,
                            "help": _str_arg(_kw(call, "description")), "epilog": _str_arg(_kw(call, "epilog")),
                            "line": n.lineno, "args": []}
            order.append(var)
        elif fname == "add_subparsers" and isinstance(f, ast.Attribute):
            parent = target(f.value)
            if parent:
                subs[var] = parent
                if parent in parsers:
                    parsers[parent]["subcommands"] = {"dest": _str_arg(_kw(call, "dest")),
                                                      "required": _seg(text, _kw(call, "required"))}
        elif fname == "add_parser" and isinstance(f, ast.Attribute):
            sv = target(f.value)
            parsers[var] = {"var": var, "prog": None, "parent": subs.get(sv or ""), "command": _str_arg(
                call.args[0]) if call.args else None, "help": _str_arg(_kw(call, "help")) or _str_arg(
                _kw(call, "description")), "line": n.lineno, "args": []}
            order.append(var)
    # bare `sub.add_parser("undo")` statements, with no variable
    for n in ast.walk(tree):
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call):
            call = n.value
            f = call.func
            if isinstance(f, ast.Attribute) and f.attr == "add_parser":
                sv = target(f.value)
                name = _str_arg(call.args[0]) if call.args else None
                key = f"<{name}@{n.lineno}>"
                parsers[key] = {"var": key, "prog": None, "parent": subs.get(sv or ""), "command": name,
                                "help": _str_arg(_kw(call, "help")), "line": n.lineno, "args": []}
                order.append(key)
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "add_argument":
            var = target(n.func.value)
            if var not in parsers:
                continue
            names = [s for s in (_str_arg(a) for a in n.args) if s]
            row: dict = {"names": names, "line": n.lineno}
            for k in ("dest", "action", "type", "default", "nargs", "choices", "required", "help", "metavar"):
                v = _kw(n, k)
                if v is not None:
                    row[k] = _str_arg(v) if k in ("help", "dest", "metavar", "action", "nargs") and \
                        _str_arg(v) is not None else _seg(text, v)
            parsers[var]["args"].append(row)
    out = []
    for var in sorted(order, key=lambda v: parsers[v]["line"]):
        p = parsers[var]
        p["args"].sort(key=lambda r: r["line"])
        out.append({k: v for k, v in p.items() if v is not None})
    return out


def _class_shape(node: ast.ClassDef, decs: list) -> str | None:
    """What kind of data shape a class is, read from its decorators and bases as written: `frozen dataclass`,
    `dataclass`, `NamedTuple`, `TypedDict`, `enum`, `class` (a plain class with annotated attributes), or None."""
    for dsrc in decs or []:
        if re.search(r"(^|\.)dataclass\b", str(dsrc)):
            return "frozen dataclass" if re.search(r"frozen\s*=\s*True", str(dsrc)) else "dataclass"
    names = [b.attr if isinstance(b, ast.Attribute) else getattr(b, "id", "") for b in node.bases]
    if "NamedTuple" in names:
        return "NamedTuple"
    if "TypedDict" in names:
        return "TypedDict"
    if any(n in ("Enum", "IntEnum", "StrEnum", "Flag", "IntFlag") for n in names):
        return "enum"
    if any(isinstance(b, ast.AnnAssign) and isinstance(b.target, ast.Name) for b in node.body):
        return "class"
    return None


def _own_nodes(fn: ast.AST):
    """The nodes of a function's own body: nested functions and classes are theirs, not its."""
    todo = list(ast.iter_child_nodes(fn))
    while todo:
        n = todo.pop()
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        yield n
        todo.extend(ast.iter_child_nodes(n))


def template(text: str, node: ast.AST | None) -> str | None:
    """A string literal as written, or an f-string as its template (`not a date: {text!r}`); None otherwise."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        out = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                out.append(str(v.value))
            elif isinstance(v, ast.FormattedValue):
                conv = {115: "!s", 114: "!r", 97: "!a"}.get(v.conversion, "")
                spec = "" if v.format_spec is None else ":" + (template(text, v.format_spec) or "")
                out.append("{" + (_seg(text, v.value) or "") + conv + spec + "}")
        return "".join(out)
    return None


_LOG_LEVELS = ("debug", "info", "warning", "warn", "error", "critical", "exception", "fatal")


def _word_of(text: str, call: ast.Call) -> dict | None:
    f = call.func
    name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "")
    owner = getattr(getattr(f, "value", None), "id", None) if isinstance(f, ast.Attribute) else None
    first = call.args[0] if call.args else None
    if name == "print":
        t = template(text, first)
        if t is None:
            return None
        file = next((k.value for k in call.keywords if k.arg == "file"), None)
        stream = "stderr" if file is not None and "stderr" in (_seg(text, file) or "") else "stdout"
        return {"kind": "print", "stream": stream, "text": t, "line": call.lineno}
    if name == "exit" and (owner in ("sys", None)):
        if isinstance(first, ast.Constant) and type(first.value) is int:
            return {"kind": "exit", "code": first.value, "line": call.lineno}
        t = template(text, first)
        return {"kind": "exit", "text": t, "code": 1, "line": call.lineno} if t is not None else None
    if name in _LOG_LEVELS and owner is not None and re.search(r"(?i)log", owner or ""):
        t = template(text, first)
        return {"kind": "log", "level": name, "text": t, "line": call.lineno} if t is not None else None
    return None


def _words(text: str, fn: ast.AST) -> list[dict]:
    """The words a function shows a user, by its syntax: each `raise X("…")` with the error and its message, each
    `print`, `sys.exit` and logging call with a literal or an f-string (its template), in line order; a word followed
    at once by `return <int>` or `sys.exit(<int>)` carries that exit status."""
    out: list[dict] = []
    for n in _own_nodes(fn):
        if isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call):
            f = n.exc.func
            err = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)
            t = template(text, n.exc.args[0]) if n.exc.args else None
            if err and t is not None:
                out.append({"kind": "raise", "error": err, "text": t, "line": n.lineno})
        elif isinstance(n, ast.Call):
            w = _word_of(text, n)
            if w:
                out.append(w)
    # exit statuses that follow a word in the same block
    for n in _own_nodes(fn):
        for body in (getattr(n, "body", None), getattr(n, "orelse", None), getattr(n, "handlers", None),
                     getattr(n, "finalbody", None)):
            if not isinstance(body, list):
                continue
            for a, b in zip(body, body[1:]):
                if not (isinstance(a, ast.Expr) and isinstance(a.value, ast.Call)):
                    continue
                code = None
                if isinstance(b, ast.Return) and isinstance(b.value, ast.Constant) and type(b.value.value) is int:
                    code = b.value.value
                elif isinstance(b, ast.Expr) and isinstance(b.value, ast.Call) and (_word_of(text, b.value) or {}).get(
                        "kind") == "exit" and "text" not in (_word_of(text, b.value) or {}):
                    code = _word_of(text, b.value)["code"]
                if code is not None:
                    for w in out:
                        if w["line"] == a.lineno and w["kind"] in ("print", "log"):
                            w["exit"] = code
    if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and fn.body and isinstance(fn.body[0], ast.Expr):
        pass
    out.sort(key=lambda w: (w["line"], w["kind"]))
    return out


def outline(path: str, text: str) -> dict:
    """A Python file's outline from its syntax tree (never run): `{ok, language, lines, doc, all, imports, defs,
    constants, env, main, argparse}`, every line number an integer, every value as written. `defs` are the
    module's functions and classes and the classes' methods (`qual` `Class.method`), each with `kind`, `line`,
    `end`, `signature`, `params`, `returns`, `decorators`, `bases`, `doc` (first paragraph, one line); nested
    functions are left out. A file that does not parse gives `{ok: false, line, message}`; a file in another
    language `{ok: null, language, why}`."""
    lang = language(path)
    if lang != "python":
        return {"ok": None, "language": lang, "why": f"no outline of {lang} in this edition, which reads Python"}
    try:
        tree = ast.parse(text, filename=path)
    except (SyntaxError, ValueError) as e:
        return {"ok": False, "language": lang, "line": int(getattr(e, "lineno", 0) or 0),
                "message": str(getattr(e, "msg", None) or e)}
    out: dict = {"ok": True, "language": lang, "lines": _folder.lines_in(text)}
    doc = _doc1(tree)
    if doc:
        out["doc"] = doc
    imports = []
    for n in tree.body:
        if isinstance(n, ast.Import):
            for a in n.names:
                imports.append({"module": a.name, "line": n.lineno})
        elif isinstance(n, ast.ImportFrom):
            imports.append({"module": n.module or "", "level": n.level, "names": [a.name for a in n.names],
                            "line": n.lineno})
    # imports inside functions and guarded blocks count too, as dependencies
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)) and n not in tree.body:
            if isinstance(n, ast.Import):
                imports += [{"module": a.name, "line": n.lineno, "nested": True} for a in n.names]
            else:
                imports.append({"module": n.module or "", "level": n.level, "names": [a.name for a in n.names],
                                "line": n.lineno, "nested": True})
    for r in imports:
        top = str(r.get("module") or "").split(".", 1)[0]
        if not r.get("level") and top:
            r["stdlib"] = top in sys.stdlib_module_names
    out["imports"] = sorted(imports, key=lambda r: r["line"])
    defs: list[dict] = []
    owners: dict[int, str] = {}

    def add_def(node: ast.AST, qual: str, kind: str) -> None:
        d: dict = {"name": node.name, "qual": qual, "kind": kind, "line": node.lineno,      # type: ignore
                   "end": int(getattr(node, "end_lineno", node.lineno) or node.lineno),       # type: ignore
                   "signature": _signature(text, node)}
        if not isinstance(node, ast.ClassDef):
            d["params"] = _params(text, node.args)                                            # type: ignore
            if node.returns is not None:                                                      # type: ignore
                d["returns"] = _seg(text, node.returns)                                       # type: ignore
        else:
            d["bases"] = [_seg(text, b) for b in node.bases]
        decs = [_seg(text, x) for x in node.decorator_list]                                  # type: ignore
        if decs:
            d["decorators"] = decs
        doc1 = _doc1(node)
        if doc1:
            d["doc"] = doc1
        if isinstance(node, ast.ClassDef):
            fields = []
            shape = _class_shape(node, decs)
            for b in node.body:
                if isinstance(b, ast.AnnAssign) and isinstance(b.target, ast.Name):
                    row = {"name": b.target.id, "annotation": _seg(text, b.annotation), "line": b.lineno}
                    if b.value is not None:
                        row["default"] = _seg(text, b.value)
                    fields.append(row)
                elif shape == "enum" and isinstance(b, ast.Assign) and len(b.targets) == 1 and \
                        isinstance(b.targets[0], ast.Name) and not b.targets[0].id.startswith("_"):
                    fields.append({"name": b.targets[0].id, "default": _seg(text, b.value), "line": b.lineno})
            if fields:
                d["fields"] = fields
            if shape:
                d["shape"] = shape
        else:
            said = _words(text, node)
            if said:
                d["words"] = said
            rets = sorted({r.value.value for r in _own_nodes(node) if isinstance(r, ast.Return)
                           and isinstance(r.value, ast.Constant) and type(r.value.value) is int})
            if rets:
                d["returns_int"] = rets
        defs.append(d)
        for ln in range(d["line"], d["end"] + 1):
            owners.setdefault(ln, qual) if kind == "class" else owners.__setitem__(ln, qual)

    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            add_def(n, n.name, "function")
        elif isinstance(n, ast.ClassDef):
            add_def(n, n.name, "class")
            for b in n.body:
                if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    add_def(b, f"{n.name}.{b.name}", "method")
    out["defs"] = defs
    consts, names_all = [], None
    for n in tree.body:
        tgt, val = None, None
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            tgt, val = n.targets[0].id, n.value
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.value is not None:
            tgt, val = n.target.id, n.value
        if tgt == "__all__" and isinstance(val, (ast.List, ast.Tuple)):
            names_all = [e.value for e in val.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        elif tgt and val is not None:
            lit = _literal(text, val)
            if lit is not None:
                consts.append({"name": tgt, "value": lit, "line": n.lineno})
    if names_all is not None:
        out["all"] = names_all
    out["constants"] = consts
    out["env"] = _env_reads(text, tree, owners)
    for n in tree.body:
        if isinstance(n, ast.If) and isinstance(n.test, ast.Compare) and isinstance(n.test.left, ast.Name) \
                and n.test.left.id == "__name__" and any(isinstance(c, ast.Constant) and c.value == "__main__"
                                                         for c in n.test.comparators):
            out["main"] = n.lineno
            calls = [c for c in ast.walk(n) if isinstance(c, ast.Call)]
            names = [c.func.id for c in calls if isinstance(c.func, ast.Name) and c.func.id not in ("exit",)]
            if names:
                out["main_calls"] = names[:4]
    ap = _argparse(text, tree)
    if ap:
        out["argparse"] = ap
    return out


def _req(spec: str) -> dict | None:
    """One requirement line (`name[extra] >=1.2; marker`) as `{package, version}`."""
    s = spec.split("#", 1)[0].strip()
    if not s or s.startswith(("-", "git+", "http")):
        return None
    m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*(.*)$", s)
    if not m:
        return None
    ver = m.group(3).split(";", 1)[0].strip()
    row = {"package": m.group(1)}
    if ver:
        row["version"] = ver
    return row


def _key_line(text: str, key: str) -> int:
    """The line a TOML or INI key is set on (`tiny = "…"`), else the first that names it."""
    rx = re.compile(rf"^\s*[\"']?{re.escape(key)}[\"']?\s*[=:]")
    for i, ln in enumerate(text.splitlines(), 1):
        if rx.match(ln):
            return i
    return _line_of(text, key)


def _line_of(text: str, needle: str) -> int:
    for i, ln in enumerate(text.splitlines(), 1):
        if needle in ln:
            return i
    return 1


def manifest(path: str, text: str) -> dict:
    """A packaging file read as text, never run: `pyproject.toml`, `setup.cfg`, `requirements*.txt`. Gives `{ok,
    kind, name, version, requires_python, licence, dependencies: [{package, version, scope, line}], scripts:
    [{name, target, line}], build: {backend, requires}}`; `{ok: null, why}` for any other file, `setup.py`
    included (its outline is Python's)."""
    name = path.rsplit("/", 1)[-1]
    out: dict = {"ok": True}
    deps: list[dict] = []
    scripts: list[dict] = []
    try:
        if name == "pyproject.toml":
            data = tomllib.loads(text)
            out["kind"] = "pyproject"
            proj = data.get("project") if isinstance(data.get("project"), dict) else {}
            poetry = ((data.get("tool") or {}).get("poetry") or {}) if isinstance(data.get("tool"), dict) else {}
            for k_out, k in (("name", "name"), ("version", "version"), ("requires_python", "requires-python")):
                v = proj.get(k) if isinstance(proj, dict) else None
                if isinstance(v, str):
                    out[k_out] = v
            lic = proj.get("license") if isinstance(proj, dict) else None
            if isinstance(lic, str):
                out["licence"] = lic
            elif isinstance(lic, dict) and isinstance(lic.get("text"), str):
                out["licence"] = lic["text"].strip().splitlines()[0] if lic["text"].strip() else None
            elif isinstance(lic, dict) and isinstance(lic.get("file"), str):
                out["licence_file"] = lic["file"]
            for c in proj.get("classifiers") or []:
                if isinstance(c, str) and c.startswith("License ::"):
                    out.setdefault("licence_classifier", c)
            for spec in proj.get("dependencies") or []:
                if isinstance(spec, str) and (r := _req(spec)):
                    deps.append({**r, "scope": "run-time", "line": _line_of(text, spec)})
            for extra, specs in (proj.get("optional-dependencies") or {}).items():
                for spec in specs or []:
                    if isinstance(spec, str) and (r := _req(spec)):
                        scope = "test" if extra in ("test", "tests", "testing") else (
                            "build" if extra in ("dev", "docs", "lint") else "optional")
                        deps.append({**r, "scope": scope, "line": _line_of(text, spec)})
            for group, specs in (data.get("dependency-groups") or {}).items():
                for spec in specs or []:
                    if isinstance(spec, str) and (r := _req(spec)):
                        deps.append({**r, "scope": "test" if "test" in group else "build",
                                     "line": _line_of(text, spec)})
            for sname, tgt in (proj.get("scripts") or {}).items():
                if isinstance(tgt, str):
                    scripts.append({"name": sname, "target": tgt, "line": _key_line(text, sname)})
            if isinstance(poetry, dict):
                for sname, tgt in (poetry.get("scripts") or {}).items():
                    if isinstance(tgt, str):
                        scripts.append({"name": sname, "target": tgt, "line": _key_line(text, sname)})
                for pk, ver in (poetry.get("dependencies") or {}).items():
                    if pk.lower() == "python":
                        out.setdefault("requires_python", ver if isinstance(ver, str) else None)
                    else:
                        deps.append({"package": pk, "version": ver if isinstance(ver, str) else "",
                                     "scope": "run-time", "line": _line_of(text, pk)})
            b = data.get("build-system") if isinstance(data.get("build-system"), dict) else {}
            if b:
                out["build"] = {"backend": b.get("build-backend") if isinstance(b.get("build-backend"), str) else
                                None, "requires": [r for r in b.get("requires") or [] if isinstance(r, str)]}
        elif name == "setup.cfg":
            cp = configparser.ConfigParser(interpolation=None, strict=False)
            cp.read_string(text)
            out["kind"] = "setup.cfg"
            if cp.has_section("metadata"):
                for k_out, k in (("name", "name"), ("version", "version"), ("licence", "license")):
                    if cp.has_option("metadata", k):
                        out[k_out] = cp.get("metadata", k).strip()
            if cp.has_section("options"):
                if cp.has_option("options", "python_requires"):
                    out["requires_python"] = cp.get("options", "python_requires").strip()
                for spec in cp.get("options", "install_requires", fallback="").splitlines():
                    if (r := _req(spec)):
                        deps.append({**r, "scope": "run-time", "line": _line_of(text, spec.strip())})
            if cp.has_section("options.entry_points"):
                for spec in cp.get("options.entry_points", "console_scripts", fallback="").splitlines():
                    if "=" in spec:
                        sname, tgt = (x.strip() for x in spec.split("=", 1))
                        scripts.append({"name": sname, "target": tgt, "line": _line_of(text, spec.strip())})
        elif re.fullmatch(r"requirements[\w.-]*\.txt", name):
            out["kind"] = "requirements"
            scope = "test" if re.search(r"test|dev", name) else "run-time"
            for i, line in enumerate(text.splitlines(), 1):
                if (r := _req(line)):
                    deps.append({**r, "scope": scope, "line": i})
        else:
            return {"ok": None, "why": f"{path} is no packaging file this edition reads"}
    except (tomllib.TOMLDecodeError, configparser.Error) as e:
        return {"ok": False, "why": f"{path} could not be read: {' '.join(str(e).split())[:200]}"}
    out["dependencies"] = deps
    out["scripts"] = scripts
    return {k: v for k, v in out.items() if v is not None}


PACKAGING = ("pyproject.toml", "setup.cfg")


def is_packaging(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return "/" not in path and (name in PACKAGING or re.fullmatch(r"requirements[\w.-]*\.txt", name) is not None)


SYNTAX = SimpleNamespace(outline=outline, parse=parse, manifest=manifest, language=language)


def repo_engine() -> Any:
    """The `repo` engine, as the host makes it by name (enough/thym_host.py, `SIBLING_ENGINES`)."""
    return REPO


def syntax_engine() -> Any:
    """The `syntax` engine, as the host makes it by name."""
    return SYNTAX


def engines() -> dict:
    """The two engines, as the host merges them into `ctx.engines`: `{"repo": REPO, "syntax": SYNTAX}`."""
    return {"repo": REPO, "syntax": SYNTAX}


__all__ = ["GIT_OVERRIDES", "REPO", "SYNTAX", "engines", "repo_engine", "syntax_engine", "template", "files", "git_binary", "git_env", "history", "is_packaging",
           "language", "manifest", "outline", "parse", "run_git", "text", "tree"]
