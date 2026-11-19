"""The sandbox: the one place enough starts a program entailed from a fabulac the person authored.

The owner's ruling (2026-11-14, tracker `fabulac-first` F4r): enough may run the entailment of a fabulac the person
AUTHORED (its entailed tests, and the tool itself) inside a box: a folder of its own, an environment of its own,
nothing of the project or the home folder in reach unless the person hands it over, no network, a limit on time and
size, and a stop. A cshort of code the person did not author stays "read, never run" (the 2026-11-05 rule): this
module refuses to prepare anything whose source is not `authored`, and that is the first thing it checks.

This module imports nothing outside Python's standard library and nothing of enough, so that it can be read, tested
and carried on its own. It lives outside `enough/thym/` so that Comprise does not inherit a runner.

The shape
---------

    run = prepare(entailed_folder, source_kind="authored")      # a copy, never the original
    result = run_tests(run)                                      # python -m unittest, inside the box
    result = run_tool(run, ["count", "notes.txt"], stdin=b"", handed_over=["/path/the/person/chose/notes.txt"])
    stop(run.run_id)                                             # from another thread: stops a run in progress

`prepare`, `run_tests` and `run_tool` raise `Refusal` (its `.sentence` is for the person) when enough will not run
the program: not authored, a service, a need outside the standard library, an interpreter older than the program
asks, a platform with no box. A run that starts always returns a `Result`, also when it was stopped.

A run folder is `<root>/<run-id>/` (`root` defaults to `<thym root>/sandbox`, the Thym root being
`ENOUGH_THYM_ROOT` else `~/enough/thym`, so a scratch server's override moves the sandbox too):

    work/     a copy of the entailed folder; the program's working directory; writable
    home/     the program's HOME; writable
    tmp/      the program's TMPDIR; writable
    handed/   copies of what the person handed over, read-only to the program
    box/      the profile, the launcher, stdin; not writable by the program
    out/      stdout, stderr, result.json; not writable by the program (it writes only through its own streams)

The box
-------

The interpreter is enough's own (`sys._base_executable`, resolved, which is the interpreter `sys.executable` runs)
with `-I -S -X utf8 -B`: isolated (no `PYTHON*` variables, no user site, no current folder on `sys.path`) and no
site-packages, so the standard library only. The environment is whole, nothing inherited: `PATH=/usr/bin:/bin`,
`HOME=<run>/home`, `TMPDIR=<run>/tmp`, `LANG=C.UTF-8`, `PYTHONHASHSEED=0`, `PYTHONDONTWRITEBYTECODE=1`, `NO_COLOR=1`,
`COLUMNS=80`; no `ENOUGH_*`, no proxies, no keys. The program starts in a process group of its own; a small launcher
(`box/launch.py`, written from `_LAUNCHER` below) sets the limits inside the child (`RLIMIT_CPU`, `RLIMIT_FSIZE`,
`RLIMIT_NOFILE`, `RLIMIT_CORE`, and `RLIMIT_AS` on Linux only), then runs the program with `runpy`; never
`preexec_fn`, which is unsafe in a threaded server.

The parent keeps a wall clock, caps the output it keeps (the streams go to files in `out/`; a stream that passes the
cap stops the run), measures the run folder against a disk cap while it runs, and stops with `SIGTERM` to the group
then `SIGKILL` after a grace.

macOS: `/usr/bin/sandbox-exec` with a profile written per run (`macos_profile`): the network denied; every write
denied except under `work/`, `home/`, `tmp/` and `/dev/null`; every read denied except the run folder, the system's
own libraries (`/System`, `/usr/lib`, `/usr/share`, `/dev`, the time zone data) and the interpreter's own prefix,
with every `site-packages` inside it denied again; executing anything but the interpreter denied. File metadata
(that a path exists, its size and dates) stays readable, as `stat` needs it on the way to any allowed file; contents
and folder listings outside the allowed places do not.

Linux: bubblewrap (`bwrap`) when it is on the path, with the same promises (`linux_argv`): every namespace unshared
(no network but loopback), the system and the interpreter's prefix read-only, `site-packages` hidden under empty
folders, the run folder writable, `box/`, `out/` and `handed/` read-only over it. Without bubblewrap enough refuses
and says what to install: limits alone do not keep the home folder out of reach.

Any other platform: refused.

What is not guaranteed (and a `Result` says so in `guarantees`): memory on macOS (`RLIMIT_AS` and `RLIMIT_DATA`
are not enforced there; nothing is promised); a count of processes per run (`RLIMIT_NPROC` counts per user); the
disk cap is measured every `POLL` seconds, so a fast writer can pass it by what it writes in between (each file is
held to `fsize` by the kernel); `sandbox-exec` is deprecated by Apple and its profile language undocumented, so a
macOS update could change it; Mach IPC on macOS stays open (`(allow default)`); CPU time is a limit, not fairness;
a program that leaves its process group before it is stopped escapes `killpg` (on Linux bubblewrap's
`--die-with-parent` still takes it down).

The package source
------------------

`PACKAGE_SOURCE` is the default and the one value the page and the readvisor can ask for (`OFFERED_SOURCES`):
`"standard-library"`. The sandbox fetches nothing, and `unmet_needs` names what a program asks for outside Python's
own standard library (`sys.stdlib_module_names`). `PACKAGE_SOURCES` holds every value this module knows:

- `"standard-library"`: the default, above.
- `"enough-venv"` (the owner's ruling at checkpoint C, 2026-11-18): the run also reads the `site-packages` of the
  virtual environment enough itself runs in (`venv_site_packages`), read-only, added to the end of `sys.path` by the
  launcher with no `.pth` file read (so an editable install of enough there is not followed); nothing is fetched or
  installed, and writes there stay denied. It is accepted only when the caller says, with `owners_code=True`, that
  the run's source is the owner's own code (a round trip of enough's or Comprise's own parts, pins section 9). No
  route passes `owners_code`, and a fabulac's own fields cannot set it: a person's authored program stays standard
  library only.

The Thymop Register (`thymop-snake-harness`) will be a third value; the install step it brings runs before the run,
into `<run>/venv`, under a profile that allows the network for that step only, and the run itself has the network
denied again.

Serving (specified; switched on in a later minor, tracker `fabulac-h5`)
-----------------------------------------------------------------------

A program's kind is read from the `program` block of the fabulac's catalog, mirrored in the entailed
`pyproject.toml` as `[tool.enough]`: `kind` (`tool` | `library` | `service`), `start` (`["-m", "<module>"]` or
`["<file>.py"]`, relative to the folder), `serve: {port, reach}`. In 0.8 a `service` is authored and entailed and
refused here with `SERVING_LATER`. When serving is switched on it promises, with no change of format:

- The port is chosen by enough, never by the program: a free port on the loopback interface only
  (`127.0.0.1`), handed to the program as `PORT` in its environment; `serve.port` is a wish, kept when free.
  macOS adds `(allow network-bind (local ip "localhost:<port>"))` and `(allow network-inbound (local ip
  "localhost:<port>"))`; Linux keeps the network namespace and forwards the port from a socket enough opens.
- Outbound network stays denied. `serve.reach` lists what the service may reach (hosts, or `"none"`); every entry
  waits for the person's yes, and a host the box cannot filter by name (macOS filters by address or not at all) is
  refused with the reason rather than widened.
- Stopping is the same `stop(run_id)`: `SIGTERM` to the group, `SIGKILL` after the grace; the app's shutdown stops
  every service it started; a service has no wall-clock limit but keeps its CPU, file, output and disk limits, and
  its output is kept as a rolling tail rather than a cap that stops it.
"""
from __future__ import annotations

import ast
import dataclasses
import json
import os
import re
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import sysconfig
import threading
import time
import tomllib
from pathlib import Path
from typing import Any, Iterable, Sequence

PACKAGE_SOURCE = "standard-library"                     # the default
ENOUGH_VENV = "enough-venv"                             # the owner's own code only (owners_code=True)
PACKAGE_SOURCES = frozenset({PACKAGE_SOURCE, ENOUGH_VENV})
OFFERED_SOURCES = (PACKAGE_SOURCE,)                     # all the page and the readvisor may ask for

SERVING_LATER = ("{name} is a service. enough authors and entails services, but serving comes in a later minor: "
                 "enough cannot serve it here yet. Its source is entailed and can run elsewhere.")
NOT_AUTHORED = ("{name} was not authored in enough, so its code is read, never run (the rule for a cshort of code "
                "you did not author).")
OWNERS_ONLY = ("{name} asks for enough's own packages ({source}); those are lent only to a round trip of the owner's "
               "own code, so enough will not run it with them.")
UNKNOWN_SOURCE = "enough knows no package source called {source!r}; it knows {known}."
POLL = 0.05            # seconds between looks at the clock, the output and the stop flag
DISK_POLL = 0.2        # seconds between measurements of the run folder

_MAC_SYSTEM_READS = ("/System", "/usr/lib", "/usr/share", "/private/var/db/timezone", "/private/var/db/dyld",
                     "/dev", "/Library/Apple")
_MAC_SYSTEM_LITERALS = ("/", "/private/etc/localtime")


class Refusal(Exception):
    """enough will not run this; `sentence` says why, in words for the person."""

    def __init__(self, sentence: str, *, reason: str = "refused"):
        super().__init__(sentence)
        self.sentence = sentence
        self.reason = reason


@dataclasses.dataclass(frozen=True)
class Limits:
    wall: float = 120.0               # seconds, kept by the parent
    cpu: int = 60                     # seconds of CPU, RLIMIT_CPU
    output: int = 1_000_000           # bytes kept of each stream; passing it stops the run
    disk: int = 200_000_000           # bytes the run's writable folders may hold
    fsize: int = 50_000_000           # bytes in any one file, RLIMIT_FSIZE
    nofile: int = 256                 # open files, RLIMIT_NOFILE
    memory: int = 1_073_741_824       # bytes of address space, RLIMIT_AS, Linux only
    grace: float = 3.0                # seconds between SIGTERM and SIGKILL


@dataclasses.dataclass(frozen=True)
class Program:
    name: str
    kind: str = "tool"                # tool | library | service
    start: tuple[str, ...] = ()
    serve: dict = dataclasses.field(default_factory=dict)
    requires_python: str = ""
    dependencies: tuple[str, ...] = ()


@dataclasses.dataclass
class Run:
    run_id: str
    folder: Path
    program: Program
    original: Path
    package_source: str = PACKAGE_SOURCE

    @property
    def work(self) -> Path:
        return self.folder / "work"

    def sub(self, name: str) -> Path:
        return self.folder / name


@dataclasses.dataclass
class Result:
    run_id: str
    what: str                         # "tests" | "tool"
    exit_code: int | None
    stdout: str
    stderr: str
    stdout_truncated: bool
    stderr_truncated: bool
    wall_time: float
    stopped_by: str | None            # None | "time" | "cpu" | "output" | "disk" | "request"
    stopped: str | None               # the sentence for the person, when stopped
    refused: list[str]                # what the box or the limits refused, as sentences
    enforced: bool                    # True only when the box (sandbox-exec or bubblewrap) held the run
    mechanism: str
    guarantees: dict[str, str]
    handed_over: list[str]
    disk_used: int

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


# ---- what the program is ----------------------------------------------------------------------------------------

def program_from_block(name: str, block: dict | None, project: dict | None = None) -> Program:
    """A Program from a catalog `program` block (or `[tool.enough]`), plus `[project]` when there is one."""
    block = dict(block or {})
    project = dict(project or {})
    kind = str(block.get("kind") or "tool")
    if kind not in ("tool", "library", "service"):
        raise Refusal(f"{name} says its kind is {kind!r}; enough knows tool, library and service.", reason="kind")
    start = block.get("start") or ()
    if isinstance(start, str):
        start = start.split()
    serve = block.get("serve") or {}
    return Program(name=name, kind=kind, start=tuple(str(s) for s in start),
                   serve=dict(serve) if isinstance(serve, dict) else {},
                   requires_python=str(project.get("requires-python") or ""),
                   dependencies=tuple(str(d) for d in project.get("dependencies") or ()))


def read_program(folder: str | os.PathLike) -> Program:
    """The program an entailed folder holds, from its `pyproject.toml` (`[tool.enough]` and `[project]`)."""
    folder = Path(folder)
    py = folder / "pyproject.toml"
    if not py.is_file():
        raise Refusal(f"{folder.name} has no pyproject.toml, so it is not an entailed application enough can run.",
                      reason="not-entailed")
    try:
        data = tomllib.loads(py.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise Refusal(f"{folder.name}'s pyproject.toml cannot be read ({exc}).", reason="not-entailed") from exc
    block = (data.get("tool") or {}).get("enough")
    if not isinstance(block, dict):
        raise Refusal(f"{folder.name}'s pyproject.toml has no [tool.enough] table, so it is not an entailed "
                      "application enough can run.", reason="not-entailed")
    project = data.get("project") or {}
    return program_from_block(str(project.get("name") or folder.name), block, project)


def check_program(program: Program, *, source: str = PACKAGE_SOURCE) -> None:
    """Refuse what this minor does not run: a service, a newer Python, a need the package source cannot meet."""
    if program.kind == "service":
        raise Refusal(SERVING_LATER.format(name=program.name), reason="service")
    floor = re.fullmatch(r"\s*>=\s*(\d+)\.(\d+)(?:\.\d+)?\s*", program.requires_python or "")
    if floor and sys.version_info[:2] < (int(floor.group(1)), int(floor.group(2))):
        raise Refusal(f"{program.name} needs Python {floor.group(1)}.{floor.group(2)} or later; enough runs "
                      f"{sys.version_info[0]}.{sys.version_info[1]}, so it cannot run it here.", reason="python")
    if program.dependencies:
        names = [re.split(r"[\s<>=!~;\[(@]", d.strip(), maxsplit=1)[0] for d in program.dependencies]
        if source == ENOUGH_VENV:
            have = venv_distributions()
            names = [n for n in names if _norm(n) not in have]
            if not names:
                return
        raise Refusal(needs_sentence(program.name, names, source=source), reason="needs")


# ---- the package source -----------------------------------------------------------------------------------------

def check_source(source: str, *, owners_code: bool = False, name: str = "This program") -> None:
    """Refuse a package source this module does not know, and `enough-venv` for anything but the owner's own code."""
    if source not in PACKAGE_SOURCES:
        raise Refusal(UNKNOWN_SOURCE.format(source=source, known=", ".join(sorted(PACKAGE_SOURCES))),
                      reason="package-source")
    if source == ENOUGH_VENV and owners_code is not True:
        raise Refusal(OWNERS_ONLY.format(name=name, source=source), reason="package-source")


def venv_site_packages() -> list[str]:
    """The site-packages folders of the virtual environment enough runs in (resolved), or [] outside one."""
    if os.path.realpath(sys.prefix) == os.path.realpath(sys.base_prefix):
        return []
    v = {"base": sys.prefix, "platbase": sys.prefix}
    out: list[str] = []
    for key in ("purelib", "platlib"):
        p = os.path.realpath(sysconfig.get_paths(vars=v)[key])
        if os.path.isdir(p) and p not in out:
            out.append(p)
    return out


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "_", name).lower()


def venv_modules() -> set[str]:
    """The top-level module names enough's own site-packages holds: folders, modules, extension modules, and what
    each distribution's `top_level.txt` names. Read as a listing; nothing is imported."""
    out: set[str] = set()
    for sp in venv_site_packages():
        for e in os.scandir(sp):
            n = e.name
            if n.endswith((".dist-info", ".egg-info")):
                tl = os.path.join(e.path, "top_level.txt")
                if os.path.isfile(tl):
                    with open(tl, encoding="utf-8", errors="replace") as fh:
                        out.update(x.strip().split("/")[0] for x in fh if x.strip())
            elif n.endswith((".py", ".so", ".pyd")):
                out.add(n.split(".")[0])
            elif e.is_dir() and n.isidentifier():
                out.add(n)
    return out


def venv_distributions() -> set[str]:
    """The distribution names (normalised) installed in enough's own site-packages."""
    out: set[str] = set()
    for sp in venv_site_packages():
        for e in os.scandir(sp):
            if e.name.endswith(".dist-info"):
                out.add(_norm(e.name[:-len(".dist-info")].rsplit("-", 1)[0]))
    return out


def unmet_needs(names: Iterable[str], *, local: Iterable[str] = (), source: str = PACKAGE_SOURCE) -> list[str]:
    """The names among `names` (module names; dotted is fine) that the package source cannot provide."""
    if source not in PACKAGE_SOURCES:  # the register's value arrives with thymop-snake-harness
        raise NotImplementedError(f"package source {source!r}")
    own = set(sys.stdlib_module_names) | {"__future__"} | set(local)
    if source == ENOUGH_VENV:
        own |= venv_modules()
    out: list[str] = []
    for n in names:
        top = str(n).split(".")[0].strip()
        if top and top not in own and top not in out:
            out.append(top)
    return sorted(out)


def needs_sentence(name: str, unmet: Sequence[str], *, source: str = PACKAGE_SOURCE) -> str:
    listed = ", ".join(f"`{u}`" for u in unmet)
    which = "which is" if len(unmet) == 1 else "which are"
    where = "the standard library" if source == PACKAGE_SOURCE else "the standard library and enough's own packages"
    return (f"{name} needs {listed}, {which} outside {where}: enough cannot run it here yet. Its source "
            "is entailed and can run elsewhere.")


def check_needs(name: str, names: Iterable[str], *, local: Iterable[str] = (), source: str = PACKAGE_SOURCE) -> None:
    unmet = unmet_needs(names, local=local, source=source)
    if unmet:
        raise Refusal(needs_sentence(name, unmet, source=source), reason="needs")


#: The exceptions an `except` may name for the imports in its `try` to count as optional (the program goes on without
#: them): a missing module raises ImportError (ModuleNotFoundError is one).
OPTIONAL_GUARDS = frozenset({"ImportError", "ModuleNotFoundError", "Exception", "BaseException"})


def _guards_import(handler: ast.ExceptHandler) -> bool:
    t = handler.type
    if t is None:                                       # a bare `except:`
        return True
    names = t.elts if isinstance(t, ast.Tuple) else [t]
    return any((isinstance(n, ast.Name) and n.id in OPTIONAL_GUARDS)
               or (isinstance(n, ast.Attribute) and n.attr in OPTIONAL_GUARDS) for n in names)


def _siblings(d: Path) -> set[str]:
    """The modules a file in folder `d` can import as siblings: its `.py` files and its folders (packages)."""
    out: set[str] = set()
    try:
        for p in d.iterdir():
            if p.is_symlink():
                continue
            if p.suffix == ".py":
                out.add(p.stem)
            elif p.is_dir() and p.name.isidentifier():
                out.add(p.name)
    except OSError:
        pass
    return out


def _hard_imports(tree: ast.AST) -> set[str]:
    """The top-level names a module imports absolutely, but those inside a `try` whose `except` catches ImportError
    (an optional import: the program goes on without it)."""
    found: set[str] = set()

    def visit(node: ast.AST, optional: bool) -> None:
        if isinstance(node, ast.Import):
            if not optional:
                found.update(a.name.split(".")[0] for a in node.names)
            return
        if isinstance(node, ast.ImportFrom):
            if not optional and not node.level and node.module:
                found.add(node.module.split(".")[0])
            return
        if isinstance(node, (ast.Try, getattr(ast, "TryStar", ast.Try))):
            guarded = optional or any(_guards_import(h) for h in node.handlers)
            for child in node.body:
                visit(child, guarded)
            for child in [*node.handlers, *node.orelse, *node.finalbody]:
                visit(child, optional)
            return
        for child in ast.iter_child_nodes(node):
            visit(child, optional)

    visit(tree, False)
    return found


def imports_of(folder: str | os.PathLike) -> tuple[set[str], set[str]]:
    """(top-level names imported absolutely and not optionally, the program's own modules), by syntax only (nothing
    runs). An import inside `try: … except ImportError` is optional and not counted; a module beside the file that
    imports it (a sibling, anywhere in the folder) is the program's own, as are the folder's top-level modules."""
    folder = Path(folder)
    local: set[str] = _siblings(folder)
    for p in folder.glob("tests/*.py"):
        local.add(p.stem)
    found: set[str] = set()
    for p in folder.rglob("*.py"):
        if p.is_symlink():
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        names = _hard_imports(tree)
        if p.parent != folder:
            names -= _siblings(p.parent)
        found |= names
    return found, local


# ---- the run folder ---------------------------------------------------------------------------------------------

def default_root() -> Path:
    thym = os.environ.get("ENOUGH_THYM_ROOT") or os.path.join(os.path.expanduser("~"), "enough", "thym")
    return Path(thym) / "sandbox"


#: Run folders are removed once their result is read and the run is over (`discard`), and those left behind (a crash,
#: a stop of the app) are swept at app start when older than this many seconds (`sweep`).
STALE_AFTER = 24 * 60 * 60
#: Set True (or export ENOUGH_SANDBOX_KEEP=1) to keep every run folder for debugging: nothing is discarded or swept.
KEEP_RUNS = False
_RUN_ID = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{8}$")


def keeping() -> bool:
    """Whether run folders are kept (the seam `KEEP_RUNS`, or ENOUGH_SANDBOX_KEEP set to anything but 0 or empty)."""
    return KEEP_RUNS or os.environ.get("ENOUGH_SANDBOX_KEEP", "").strip() not in ("", "0")


def discard(run: Run) -> bool:
    """Remove a run's folder once its result has been read and the run is over; False (nothing removed) while it
    runs, when folders are kept, or when the folder is not a run folder."""
    if keeping():
        return False
    with _LOCK:
        if run.run_id in _LIVE:
            return False
    folder = Path(run.folder)
    if not _RUN_ID.match(folder.name) or folder.name != run.run_id or not folder.is_dir() or folder.is_symlink():
        return False
    shutil.rmtree(folder, ignore_errors=True)
    return not folder.exists()


def sweep(root: str | os.PathLike | None = None, *, older_than: float = STALE_AFTER,
          now: float | None = None) -> list[str]:
    """Remove the run folders under `root` (default `default_root()`) last changed more than `older_than` seconds
    ago and not running: what a crash or a stopped app left behind. Only folders named as runs are touched. Returns
    the run ids removed (none when folders are kept)."""
    if keeping():
        return []
    root = Path(root) if root is not None else default_root()
    if not root.is_dir():
        return []
    now = time.time() if now is None else now
    with _LOCK:
        live = set(_LIVE)
    gone: list[str] = []
    for e in os.scandir(root):
        if not _RUN_ID.match(e.name) or e.name in live or e.is_symlink() or not e.is_dir(follow_symlinks=False):
            continue
        try:
            age = now - e.stat(follow_symlinks=False).st_mtime
        except OSError:
            continue
        if age > older_than:
            shutil.rmtree(e.path, ignore_errors=True)
            if not os.path.exists(e.path):
                gone.append(e.name)
    return sorted(gone)


def _tree_size(*folders: Path) -> int:
    total = 0
    for f in folders:
        for dirpath, dirnames, filenames in os.walk(f, followlinks=False):
            for n in filenames + dirnames:
                try:
                    total += os.lstat(os.path.join(dirpath, n)).st_size
                except OSError:
                    pass
    return total


def prepare(entailed: str | os.PathLike, *, source_kind: str, root: str | os.PathLike | None = None,
            program: Program | None = None, limits: Limits = Limits(), package_source: str = PACKAGE_SOURCE,
            owners_code: bool = False) -> Run:
    """A run folder holding a copy of the entailed folder. Refuses before copying anything it will not run.

    `owners_code=True` is the caller's word that the source is the owner's own code (a round trip of one of enough's
    or Comprise's parts, rebuilt from its fabulac): such a run need not be authored, and it alone may take the
    package source `enough-venv`. The routes never pass it."""
    entailed = Path(entailed)
    name = program.name if program else entailed.name
    if source_kind != "authored" and owners_code is not True:   # the first check: read, never run
        raise Refusal(NOT_AUTHORED.format(name=name), reason="not-authored")
    check_source(package_source, owners_code=owners_code, name=name)
    if package_source == ENOUGH_VENV and not venv_site_packages():
        raise Refusal("enough is not running in a virtual environment of its own, so it has no packages of its own "
                      "to lend this run.", reason="package-source")
    if not entailed.is_dir():
        raise Refusal(f"There is no folder {entailed} to run.", reason="missing")
    program = program or read_program(entailed)
    check_program(program, source=package_source)
    found, local = imports_of(entailed)
    check_needs(program.name, found, local=local, source=package_source)
    if _tree_size(entailed) > limits.disk:
        raise Refusal(f"{program.name} is larger than the run's disk limit ({limits.disk} bytes).", reason="disk")
    machinery()                                         # refuse now on a platform with no box
    root = Path(root) if root is not None else default_root()
    root.mkdir(parents=True, exist_ok=True)
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(4)
    folder = Path(os.path.realpath(root)) / run_id
    folder.mkdir()
    for sub in ("home", "tmp", "handed", "box", "out"):
        (folder / sub).mkdir()
    # a copy, never a bind; symbolic links stay links (whatever they point at outside stays out of reach)
    shutil.copytree(entailed, folder / "work", symlinks=True, ignore_dangling_symlinks=True,
                    ignore=shutil.ignore_patterns("__pycache__", ".git"))
    (folder / "box" / "launch.py").write_text(_LAUNCHER, encoding="utf-8")
    return Run(run_id=run_id, folder=folder, program=program, original=entailed, package_source=package_source)


# ---- the mechanism ----------------------------------------------------------------------------------------------

def _platform() -> str:
    return sys.platform


def _bwrap() -> str | None:
    for cand in ("/usr/bin/bwrap", "/usr/local/bin/bwrap"):
        if os.access(cand, os.X_OK):
            return cand
    return shutil.which("bwrap")


def machinery() -> tuple[str, str]:
    """(mechanism, its path), or Refusal with the reason."""
    plat = _platform()
    if plat == "darwin":
        if os.access("/usr/bin/sandbox-exec", os.X_OK):
            return "sandbox-exec", "/usr/bin/sandbox-exec"
        raise Refusal("This Mac has no /usr/bin/sandbox-exec, so enough cannot keep a program off the network and "
                      "away from your home folder; it will not run it.", reason="no-box")
    if plat.startswith("linux"):
        b = _bwrap()
        if b:
            return "bwrap", b
        raise Refusal("This machine has no bubblewrap (bwrap), so enough cannot keep a program off the network and "
                      "away from your home folder; it will not run it. Install bubblewrap (the package is usually "
                      "called bubblewrap) and try again.", reason="no-box")
    raise Refusal(f"enough runs programs only on macOS and Linux, where it can box them; not on {plat}.",
                  reason="no-box")


def interpreter() -> dict[str, Any]:
    """The interpreter the box runs, and the folders it reads."""
    exe = os.path.realpath(getattr(sys, "_base_executable", None) or sys.executable)
    prefix = os.path.realpath(sys.base_prefix)
    stdlib = os.path.realpath(sysconfig.get_paths(vars={"base": sys.base_prefix, "platbase": sys.base_prefix,
                                                        "installed_base": sys.base_prefix,
                                                        "installed_platbase": sys.base_prefix})["stdlib"])
    hidden = [os.path.join(stdlib, "site-packages"), os.path.join(stdlib, "dist-packages")]
    hidden += [os.path.join(prefix, n) for n in ("envs", "pkgs", "conda-meta")]   # conda: other envs' packages
    reads = [prefix]
    for p in (exe, stdlib):
        if not (p == prefix or p.startswith(prefix + os.sep)):
            reads.append(p)
    return {"executable": exe, "prefix": prefix, "stdlib": stdlib, "reads": reads,
            "hidden": [h for h in hidden if os.path.exists(h)], "version": "%d.%d.%d" % sys.version_info[:3]}


def _q(p: str | Path) -> str:
    return '"' + str(p).replace("\\", "\\\\").replace('"', '\\"') + '"'


def lent_packages(run: Run) -> list[str]:
    """The site-packages folders this run reads (read-only): none but for `enough-venv`."""
    return venv_site_packages() if run.package_source == ENOUGH_VENV else []


def macos_profile(run: Run, interp: dict[str, Any] | None = None) -> str:
    """The sandbox-exec profile for one run. In SBPL the later rule wins."""
    interp = interp or interpreter()
    f = run.folder
    exe = interp["executable"]
    framework_exe = os.path.join(interp["prefix"], "Resources", "Python.app", "Contents", "MacOS", "Python")
    lines = [
        "(version 1)",
        "(allow default)",
        "(deny network*)",
        "(deny file-write*)",
        f"(allow file-write* (subpath {_q(f / 'work')}) (subpath {_q(f / 'home')}) (subpath {_q(f / 'tmp')})",
        '  (literal "/dev/null") (literal "/dev/dtracehelper"))',
        "(deny file-read*)",
        "(allow file-read-metadata)",
        "(allow file-read* " + " ".join(f"(subpath {_q(p)})" for p in _MAC_SYSTEM_READS),
        "  " + " ".join(f"(literal {_q(p)})" for p in _MAC_SYSTEM_LITERALS) + ")",
        f"(allow file-read* (subpath {_q(f)}) " + " ".join(f"(subpath {_q(p)})" for p in interp["reads"]) + ")",
    ]
    if interp["hidden"]:
        lines.append("(deny file-read* " + " ".join(f"(subpath {_q(p)})" for p in interp["hidden"]) + ")")
    lent = lent_packages(run)
    if lent:                                            # enough-venv: read-only (every write above stays denied)
        lines.append("(allow file-read* " + " ".join(f"(subpath {_q(p)})" for p in lent) + ")")
    lines += [
        "(deny process-exec*)",
        f"(allow process-exec* (literal {_q(exe)}) (literal {_q(framework_exe)}))",
    ]
    return "\n".join(lines) + "\n"


def environment(run: Run) -> dict[str, str]:
    """The whole environment of the program; nothing is inherited. With `enough-venv` the lent folders are also on
    `PYTHONPATH`, so an interpreter the program starts itself (only the interpreter may be started) finds them; the
    program's own interpreter runs with `-I` and takes them from the launcher instead."""
    env = {"PATH": "/usr/bin:/bin", "HOME": str(run.sub("home")), "TMPDIR": str(run.sub("tmp")),
           "LANG": "C.UTF-8", "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1", "NO_COLOR": "1",
           "COLUMNS": "80"}
    lent = lent_packages(run)
    if lent:
        env["PYTHONPATH"] = os.pathsep.join(lent)
    return env


def _python_argv(run: Run, inner: Sequence[str], limits: Limits, interp: dict[str, Any], linux: bool) -> list[str]:
    argv = [interp["executable"], "-I", "-S", "-X", "utf8", "-B", str(run.sub("box") / "launch.py"),
            "--work", str(run.work), "--cpu", str(limits.cpu), "--fsize", str(limits.fsize),
            "--nofile", str(limits.nofile)]
    if linux:
        argv += ["--as", str(limits.memory)]
    lent = lent_packages(run)
    if lent:
        argv += ["--path", os.pathsep.join(lent)]
    return argv + ["--", *inner]


def linux_argv(run: Run, inner: Sequence[str], limits: Limits, bwrap: str,
               interp: dict[str, Any] | None = None) -> list[str]:
    interp = interp or interpreter()
    f = str(run.folder)
    argv = [bwrap, "--unshare-all", "--die-with-parent", "--new-session", "--clearenv",
            "--ro-bind", "/usr", "/usr"]
    for p in ("/lib", "/lib64", "/lib32", "/bin", "/sbin", "/etc/localtime", "/etc/ld.so.cache"):
        argv += ["--ro-bind-try", p, p]
    for p in interp["reads"]:
        argv += ["--ro-bind", p, p]
    for p in interp["hidden"]:
        argv += ["--tmpfs", p]
    for p in lent_packages(run):
        argv += ["--ro-bind", p, p]
    argv += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--bind", f, f]
    for sub in ("box", "out", "handed"):
        argv += ["--ro-bind", str(run.sub(sub)), str(run.sub(sub))]
    argv += ["--chdir", str(run.work)]
    for k, v in environment(run).items():
        argv += ["--setenv", k, v]
    return argv + _python_argv(run, inner, limits, interp, linux=True)


def _packages_words(run: Run) -> str:
    if run.package_source == ENOUGH_VENV:
        return (f"{ENOUGH_VENV}: the standard library and enough's own site-packages, read-only "
                f"({', '.join(lent_packages(run))}); nothing fetched or installed")
    return run.package_source


def build_command(run: Run, inner: Sequence[str], limits: Limits = Limits()) -> tuple[list[str], str, dict]:
    """(argv, mechanism, guarantees) for one run, or Refusal."""
    mech, path = machinery()
    interp = interpreter()
    if mech == "sandbox-exec":
        prof = run.sub("box") / "sandbox.sb"
        prof.write_text(macos_profile(run, interp), encoding="utf-8")
        argv = [path, "-f", str(prof)] + _python_argv(run, inner, limits, interp, linux=False)
        g = {"network": "denied by sandbox-exec",
             "writes": "only in the run's work, home and tmp folders (sandbox-exec)",
             "reads": "only the run folder, the system's libraries and the interpreter's own files (sandbox-exec); "
                      "file metadata elsewhere stays readable",
             "processes": "only the interpreter may be started (sandbox-exec)",
             "memory": "not limited: macOS does not enforce a memory limit, so none is promised",
             "time": f"{limits.wall:g} s wall clock, {limits.cpu} s CPU",
             "output": f"{limits.output} bytes kept of each stream",
             "disk": f"{limits.disk} bytes in the run folder (measured every {DISK_POLL:g} s), "
                     f"{limits.fsize} bytes in any one file",
             "packages": _packages_words(run)}
    else:
        argv = linux_argv(run, inner, limits, path, interp)
        g = {"network": "denied by bubblewrap (a network namespace of its own: loopback only)",
             "writes": "only in the run folder; box, out and handed are read-only (bubblewrap)",
             "reads": "only the run folder, /usr and the system libraries, and the interpreter's own files "
                      "(bubblewrap)",
             "processes": "anything under /usr may be started, inside the same box",
             "memory": f"{limits.memory} bytes of address space (RLIMIT_AS)",
             "time": f"{limits.wall:g} s wall clock, {limits.cpu} s CPU",
             "output": f"{limits.output} bytes kept of each stream",
             "disk": f"{limits.disk} bytes in the run folder (measured every {DISK_POLL:g} s), "
                     f"{limits.fsize} bytes in any one file",
             "packages": _packages_words(run)}
    return argv, mech, g


# ---- running ----------------------------------------------------------------------------------------------------

_LIVE: dict[str, subprocess.Popen] = {}
_STOP_ASKED: set[str] = set()
_LOCK = threading.Lock()


def stop(run_id: str) -> bool:
    """Stop a run in progress (from another thread). False when no such run is going."""
    with _LOCK:
        p = _LIVE.get(run_id)
        if p is None:
            return False
        _STOP_ASKED.add(run_id)
    return True


def running() -> list[str]:
    with _LOCK:
        return sorted(_LIVE)


def stop_all() -> None:
    for rid in running():
        stop(rid)


def _kill(p: subprocess.Popen, grace: float) -> None:
    for sig, wait in ((signal.SIGTERM, grace), (signal.SIGKILL, 5.0)):
        try:
            os.killpg(p.pid, sig)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            p.wait(timeout=wait)
            return
        except subprocess.TimeoutExpired:
            continue


def _hand_over(run: Run, paths: Sequence[str | os.PathLike]) -> dict[str, str]:
    """Copy what the person handed over into handed/, read-only; {original: copy}."""
    out: dict[str, str] = {}
    for p in paths:
        src = Path(p)
        if not src.exists():
            raise Refusal(f"{src} was handed over but does not exist.", reason="handed-over")
        dest = run.sub("handed") / src.name
        n = 1
        while dest.exists():
            n += 1
            dest = run.sub("handed") / f"{src.stem}-{n}{src.suffix}"
        if src.is_dir():
            shutil.copytree(src, dest, symlinks=True)
        else:
            shutil.copy2(src, dest, follow_symlinks=True)
        for dirpath, dirnames, filenames in os.walk(dest):
            for n_ in filenames:
                fp = os.path.join(dirpath, n_)
                if not os.path.islink(fp):
                    os.chmod(fp, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        if dest.is_file():
            os.chmod(dest, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        out[str(p)] = str(dest)
    return out


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _read_capped(path: Path, cap: int) -> tuple[str, bool]:
    try:
        size = path.stat().st_size
        with open(path, "rb") as fh:
            data = fh.read(cap)
    except OSError:
        return "", False
    return data.decode("utf-8", errors="replace"), size > cap


def _execute(run: Run, what: str, inner: Sequence[str], stdin: bytes, limits: Limits,
             handed: list[str]) -> Result:
    argv, mech, guarantees = build_command(run, inner, limits)
    out_dir = run.sub("out")
    (run.sub("box") / "stdin").write_bytes(stdin or b"")
    so_path, se_path = out_dir / "stdout", out_dir / "stderr"
    writable = (run.work, run.sub("home"), run.sub("tmp"))
    stopped_by: str | None = None
    t0 = time.monotonic()
    with open(run.sub("box") / "stdin", "rb") as fin, open(so_path, "wb") as fo, open(se_path, "wb") as fe:
        p = subprocess.Popen(argv, env=environment(run), cwd=str(run.work), stdin=fin, stdout=fo, stderr=fe,
                             start_new_session=True, close_fds=True, shell=False)
        with _LOCK:
            _LIVE[run.run_id] = p
        try:
            next_disk = t0
            while p.poll() is None:
                now = time.monotonic()
                with _LOCK:
                    asked = run.run_id in _STOP_ASKED
                if asked:
                    stopped_by = "request"
                elif now - t0 > limits.wall:
                    stopped_by = "time"
                elif so_path.stat().st_size > limits.output or se_path.stat().st_size > limits.output:
                    stopped_by = "output"
                elif now >= next_disk:
                    next_disk = now + DISK_POLL
                    if _tree_size(*writable) > limits.disk:
                        stopped_by = "disk"
                if stopped_by:
                    _kill(p, limits.grace)
                    break
                time.sleep(POLL)
        finally:
            if p.poll() is None:
                _kill(p, limits.grace)
            with _LOCK:
                _LIVE.pop(run.run_id, None)
                _STOP_ASKED.discard(run.run_id)
    wall = time.monotonic() - t0
    code = p.returncode
    if stopped_by is None and code is not None and code == -getattr(signal, "SIGXCPU", 24):
        stopped_by = "cpu"
    if stopped_by is None and max(_size(so_path), _size(se_path)) > limits.output:
        stopped_by = "output"   # it ended before the next look: a fast flood meets the file-size limit first
    disk_used = _tree_size(*writable)
    if stopped_by is None and disk_used > limits.disk:
        stopped_by = "disk"
    stdout, so_trunc = _read_capped(so_path, limits.output)
    stderr, se_trunc = _read_capped(se_path, limits.output)
    sentences = {
        "time": f"Stopped: it ran past the limit of {limits.wall:g} seconds.",
        "cpu": f"Stopped: it used more than {limits.cpu} seconds of CPU.",
        "output": f"Stopped: its output passed the limit of {limits.output} bytes.",
        "disk": f"Stopped: its folder passed the limit of {limits.disk} bytes.",
        "request": "Stopped, as asked.",
    }
    refused: list[str] = []
    if stopped_by:
        refused.append(sentences[stopped_by])
    enforced = True
    if mech == "bwrap" and code not in (None, 0) and stderr.startswith("bwrap:"):
        enforced = False
        refused.append("bubblewrap could not build the box here (" + stderr.splitlines()[0][6:].strip()
                       + "); nothing of the program ran.")
    if "Operation not permitted" in stderr or "Operation not permitted" in stdout:
        refused.append("The box refused at least one operation (\"Operation not permitted\" is in the output).")
    if "File too large" in stderr:
        refused.append(f"The box refused a file larger than {limits.fsize} bytes.")
    res = Result(run_id=run.run_id, what=what, exit_code=code, stdout=stdout, stderr=stderr,
                 stdout_truncated=so_trunc, stderr_truncated=se_trunc, wall_time=round(wall, 3),
                 stopped_by=stopped_by, stopped=sentences.get(stopped_by) if stopped_by else None,
                 refused=refused, enforced=enforced, mechanism=mech, guarantees=guarantees, handed_over=handed,
                 disk_used=disk_used)
    (out_dir / "result.json").write_text(json.dumps(res.as_dict(), indent=1), encoding="utf-8")
    return res


def run_tests(run: Run, *, limits: Limits = Limits()) -> Result:
    """The entailed tests (`tests/`), with `python -m unittest` inside the box."""
    check_program(run.program, source=run.package_source)
    if not (run.work / "tests").is_dir():
        raise Refusal(f"{run.program.name} has no tests folder to run.", reason="no-tests")
    inner = ["-m", "unittest", "discover", "-s", "tests", "-t", ".", "-v"]
    return _execute(run, "tests", inner, b"", limits, [])


_TEST_HEAD = re.compile(r"^(?P<name>\w+) \((?P<where>[\w.]+)\)")
_TEST_VERDICT = re.compile(r" \.\.\. (?P<v>ok|FAIL|ERROR|skipped(?: .*)?|expected failure|unexpected success)$")
_VERDICT_WORDS = {"ok": "passed", "FAIL": "failed", "ERROR": "error", "expected failure": "expected failure",
                  "unexpected success": "unexpected success"}


def test_verdicts(stderr: str) -> list[dict[str, str]]:
    """Each test `unittest -v` reported, in the order it ran, with its verdict: `[{test, verdict}]`, the test by its
    id (`tests.test_cases.Cases.test_counts`), the verdict `passed`, `failed`, `error`, `skipped`, `expected
    failure` or `unexpected success`. A test with a docstring is reported over two lines; both are read."""
    out: list[dict[str, str]] = []
    pending: str | None = None
    for line in (stderr or "").splitlines():
        head = _TEST_HEAD.match(line)
        if head:
            where, name = head.group("where"), head.group("name")
            pending = where if where.endswith("." + name) else f"{where}.{name}"
        v = _TEST_VERDICT.search(line)
        if v and pending:
            word = v.group("v")
            out.append({"test": pending, "verdict": "skipped" if word.startswith("skipped")
                        else _VERDICT_WORDS[word]})
            pending = None
        elif not head and line.startswith(("=====", "-----", "Ran ")):
            pending = None
    return out


def run_tool(run: Run, argv: Sequence[str] = (), *, stdin: bytes = b"",
             handed_over: Sequence[str | os.PathLike] = (), limits: Limits = Limits()) -> Result:
    """The tool itself: its `start` plus `argv`. What the person hands over is copied into handed/ (read-only), and
    an argument that names a handed-over path exactly is rewritten to the copy's path."""
    prog = run.program
    check_program(prog, source=run.package_source)
    if prog.kind != "tool":
        raise Refusal(f"{prog.name} is a {prog.kind}, not a tool: there is nothing to start; run its tests instead.",
                      reason="kind")
    start = list(prog.start)
    if len(start) >= 2 and start[0] == "-m" and re.fullmatch(r"[A-Za-z_][\w.]*", start[1]):
        pass
    elif len(start) >= 1 and start[0].endswith(".py") and not start[0].startswith("-"):
        target = os.path.realpath(run.work / start[0])
        if not target.startswith(str(run.work) + os.sep):
            raise Refusal(f"{prog.name}'s start names a file outside its folder.", reason="start")
    else:
        raise Refusal(f"{prog.name} does not say how it starts (start = [\"-m\", \"<module>\"] or "
                      "[\"<file>.py\"]).", reason="start")
    copies = _hand_over(run, handed_over)
    args = [copies.get(str(a), str(a)) for a in argv]
    return _execute(run, "tool", start + args, stdin, limits, sorted(copies.values()))


# ---- the launcher, run inside the box (standard library only, no enough) ----------------------------------------

_LAUNCHER = r'''"""enough's sandbox launcher: limits first, then the program. Written by enough/sandbox.py per run."""
import os, resource, runpy, signal, sys

def main(argv):
    opts, i = {}, 0
    while argv[i] != "--":
        opts[argv[i][2:]] = argv[i + 1]
        i += 2
    inner = argv[i + 1:]
    def lim(which, value):
        try:  # the hard limit comes down too, so the program cannot raise it again
            hard = resource.getrlimit(which)[1]
            v = int(value)
            h = v + 1 if which == resource.RLIMIT_CPU else v
            if hard != resource.RLIM_INFINITY:
                v, h = min(v, hard), min(h, hard)
            resource.setrlimit(which, (v, h))
        except (ValueError, OSError):
            pass
    lim(resource.RLIMIT_CPU, opts["cpu"])
    lim(resource.RLIMIT_FSIZE, opts["fsize"])
    lim(resource.RLIMIT_NOFILE, opts["nofile"])
    lim(resource.RLIMIT_CORE, 0)
    if "as" in opts:
        lim(resource.RLIMIT_AS, opts["as"])
    signal.signal(signal.SIGXFSZ, signal.SIG_IGN)   # a file past the limit fails with EFBIG instead of a kill
    work = opts["work"]
    os.chdir(work)
    sys.path.insert(0, work)
    if opts.get("path"):   # enough-venv: lent site-packages, last, with no .pth file read
        sys.path.extend(p for p in opts["path"].split(os.pathsep) if p)
    if inner[0] == "-m":
        sys.argv = ["python -m " + inner[1]] + inner[2:]
        runpy.run_module(inner[1], run_name="__main__", alter_sys=True)
    else:
        sys.argv = list(inner)
        runpy.run_path(inner[0], run_name="__main__")

main(sys.argv[1:])
'''
