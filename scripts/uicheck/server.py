"""Scratch enough servers for the browser harness — one project, one home.

Both are started through the real `python -m enough` entry point, in a
subprocess, exactly the way `scripts/smoke_boot.py` does it and for the same
reason: `ensure_skeleton()`, the registry write, the boot templating of
`BOOT_UI_STATE` and the `data-mode` gate all happen on the way up, and a
harness that mocked any of that would be checking a UI nobody ships.

Isolation is `smoke_boot.build_env()` itself — imported, not re-implemented.
Every `ENOUGH_*` seam **and** `$HOME` land inside the scratch dir, and
`--llm-url` gets a port nothing is listening on so the run can never adopt
or kill the developer's real llama-server. The UI language lives in
`$HOME/enough/config/ui.json`, which is inside that scratch dir too, so the
harness can flip languages through `POST /api/ui-config` without touching
the developer's setting.

The fixture project is deliberately a bit lumpy — nested folders, a long
file name, a document with headings and footnotes, a `.girraph`, a
`.merirmaid` — because the layout probes are looking for clipping and
overlap, and an empty project has nothing to clip. Since 0.4.3 it also holds
the Canon round's volumes (copied from tests/fixtures/cosm/): a text with its
EMF twin, a Comprise Holotype, and — in the scratch Canon store, never the
real one — a volume holding a text, its twin and a copy of the Holotype.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]

# smoke_boot.py is a script, not a package module, so it is loaded by path.
# Importing it (rather than copying build_env) is the point: the two halves
# of "never touch the developer's real state" stay one implementation.
_spec = importlib.util.spec_from_file_location(
    "enough_smoke_boot", REPO / "scripts" / "smoke_boot.py")
smoke_boot = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(smoke_boot)

build_env = smoke_boot.build_env
free_port = smoke_boot.free_port

BOOT_TIMEOUT_S = 90.0


# ---------------------------------------------------------------------------
# Fixture content
# ---------------------------------------------------------------------------

FIXTURE_DOC = """# The long document

A first paragraph with a footnote.[^one] It runs on for a while so that the
read mode has something to wrap, and so the paragraph counter in the top bar
has something to count.

## A second-level heading

- a bullet
- another bullet, this one long enough that a narrow viewport has to decide
  what to do about it
- a third

### A third-level heading

Some `inline code`, a [link](https://example.invalid/), and **bold** text.

```
a fenced block
that is wider than most sidebars would like to be, on purpose
```

| column | another column | a third |
|---|---|---|
| a | b | c |
| a much longer cell value | b | c |

[^one]: The footnote body, which the footnote rail renders in its own card.
"""

# A real girraph document. The format is enough's own line-based text
# format (see enough/girraph.py and tests/test_girraph.py), NOT JSON — a
# fixture in the wrong format does not merely fail to load, it takes the
# page's layout pass with it.
FIXTURE_GIRRAPH = """%girraph 0.1
title: What should the pre-commit suite cover?
next: a3 g1 n2 p3 q2

q1 ? What should the pre-commit suite cover?
p1 ! Every screen, at every viewport, in every language < q1
p2 ! Only the screens that changed < q1
a1 + Layout bugs hide in the combinations, not the screens < p1
a2 - Six languages times eight viewports is a lot of runs < p1 [-> a1]
n1 . The matrix lives in scripts/uicheck/screens.py < q1

q1 >
  The free-form block under a node id, which the panel renders as
  markdown — here so the fixture exercises that path too.
"""

# A hand-written merirmaid: the front-matter block is what marks the file
# as one (see gr.mirror_path / the `merirmaid: 1` sniff), and `modality`
# decides whether the panel opens it editable.
FIXTURE_MERIRMAID = """---
merirmaid: 1
title: a fixture diagram
modality: wip
---
flowchart TD
  A[a fixture diagram] --> B[with a couple of nodes]
  B --> C[and an edge or two]
"""

LONG_NAME = ("a-file-with-a-deliberately-very-long-name-that-the-sidebar-"
             "has-to-decide-how-to-truncate.md")

# The Canon round's fixtures (0.4.3), copied — never written — from
# tests/fixtures/cosm/. The EMF pair lives in its own folder because
# `notes.md` at the project root is FIXTURE_DOC, which half the screens read.
COSM_FIXTURES = REPO / "tests" / "fixtures" / "cosm"
EMF_DIR = "orchard"            # orchard/notes.md + orchard/notes.md.cosm (a fresh twin)
# A text with no twin (checkpoint B): the atem-pin scenario pins a passage's
# atem into it, which writes its minimal twin — so the hand-made twin beside
# it, which the cosm-viewer screens draw, never changes under them.
LEDGER = "ledger.md"           # orchard/ledger.md
FIXTURE_LEDGER = """# The pressing ledger

We pressed apples on three Saturdays this autumn. The first press gave forty
litres, the second sixty, and the third forty again, because the late Bramleys
were small.

Next year we want a second press, so that two teams can work at once and the
juice spends less time waiting in the sun.
"""
# SHORT (0.4.3, plan §15): a second text with its twin, for the compile-short
# scenario, which writes a short beside it and records it in that twin — so
# the notes.md pair the cosm-viewer and EMF-face screens draw never changes.
PRESS = "press.md"             # orchard/press.md + orchard/press.md.cosm
HOLOTYPE_DIR = "meadow"        # a Comprise Holotype: holotype.cosm + atoms/
CANON_VOLUME = "field-notes"   # in the scratch store: notes.md (+ twin), meadow/


def _seed_cosm(dest: Path, emf_dir: str) -> None:
    """A text with its EMF twin (in `dest/emf_dir`), and the meadow Holotype,
    under `dest`. A byte copy keeps the twin fresh: its recorded size still
    matches, and its sha256 is what decides once the copy's mtime differs."""
    emf = dest / emf_dir
    emf.mkdir(parents=True, exist_ok=True)
    for name in ("notes.md", "notes.md.cosm"):
        shutil.copyfile(COSM_FIXTURES / "emf" / name, emf / name)
    (emf / LEDGER).write_text(FIXTURE_LEDGER, encoding="utf-8")
    shutil.copytree(COSM_FIXTURES / "holotypes" / "meadow", dest / HOLOTYPE_DIR,
                    dirs_exist_ok=True)


def seed_project(project: Path) -> None:
    """Write the fixture tree. Called before the server boots so the first
    `/api/tree` already has something in it."""
    project.mkdir(parents=True, exist_ok=True)
    (project / "notes.md").write_text(FIXTURE_DOC, encoding="utf-8")
    (project / LONG_NAME).write_text("# short body\n\nOne line.\n", encoding="utf-8")
    (project / "map.girraph").write_text(FIXTURE_GIRRAPH, encoding="utf-8")
    (project / "diagram.merirmaid").write_text(FIXTURE_MERIRMAID, encoding="utf-8")
    nested = project / "drafts" / "chapter-one"
    nested.mkdir(parents=True, exist_ok=True)
    (nested / "draft.md").write_text("# Draft\n\nA nested file.\n", encoding="utf-8")
    _seed_cosm(project, EMF_DIR)
    # The same text and twin again under another name (the twin's source and
    # id say so; a byte copy of the text keeps it fresh by its sha256).
    emf = project / EMF_DIR
    shutil.copyfile(COSM_FIXTURES / "emf" / "notes.md", emf / PRESS)
    twin = (COSM_FIXTURES / "emf" / "notes.md.cosm").read_text(encoding="utf-8")
    twin = twin.replace("id: emf/notes-md\n", "id: emf/orchard--press-md\n", 1)
    twin = twin.replace("source: {path: notes.md,", f"source: {{path: {PRESS},", 1)
    (emf / f"{PRESS}.cosm").write_text(twin, encoding="utf-8")


def seed_canon(scratch: Path) -> None:
    """One Canon volume in the SCRATCH store, before the server boots: a
    text with its EMF twin and a copy of the meadow Holotype. The store is
    whatever `build_env(scratch)` points ENOUGH_CANON_ROOT at, and this
    refuses to write anywhere that is not under `scratch` — a harness that
    seeded the real ~/enough/canon would be writing into the owner's library."""
    root = Path(build_env(scratch)["ENOUGH_CANON_ROOT"]).resolve()
    if not root.is_relative_to(scratch.resolve()):
        raise RuntimeError(f"refusing to seed a Canon store outside the scratch dir: {root}")
    _seed_cosm(root / CANON_VOLUME, ".")


# ---------------------------------------------------------------------------
# The servers
# ---------------------------------------------------------------------------

class ScratchServer:
    """One `python -m enough` subprocess, with a hard guarantee of teardown."""

    def __init__(self, scratch: Path, *, home: bool = False) -> None:
        self.scratch = scratch
        self.home_mode = home
        self.port = free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.project = scratch / "project"
        self._proc: subprocess.Popen[bytes] | None = None
        self._log = scratch / ("home-server.log" if home else "server.log")

    def start(self) -> None:
        env = build_env(self.scratch)
        cmd = [sys.executable, "-m", "enough", "--port", str(self.port),
               "--llm-url", f"http://127.0.0.1:{free_port()}", "--no-browser"]
        cmd += ["--home"] if self.home_mode else ["--dir", str(self.project)]
        with open(self._log, "wb") as log:
            self._proc = subprocess.Popen(
                cmd, cwd=str(REPO), env=env, stdout=log,
                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                start_new_session=True)
        probe = "/api/home/projects" if self.home_mode else "/api/project"
        deadline = time.monotonic() + BOOT_TIMEOUT_S
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                raise RuntimeError(
                    f"scratch server exited {self._proc.returncode} during boot\n"
                    + self._log.read_text(encoding="utf-8", errors="replace")[-4000:])
            try:
                with urllib.request.urlopen(self.base + probe, timeout=5) as r:
                    if r.status == 200:
                        return
            except (urllib.error.URLError, OSError, TimeoutError):
                pass
            time.sleep(0.15)
        raise RuntimeError(f"scratch server never answered {probe} in "
                           f"{BOOT_TIMEOUT_S:.0f}s")

    def post_json(self, path: str, payload: dict[str, Any]) -> Any:
        req = urllib.request.Request(
            self.base + path, method="POST",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read().decode("utf-8", "replace")
        return json.loads(body) if body.strip() else None

    def stop(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None or proc.poll() is not None:
            return
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                proc.kill()
            proc.wait(timeout=5)

    def log_tail(self, n: int = 3000) -> str:
        if not self._log.is_file():
            return ""
        return self._log.read_text(encoding="utf-8", errors="replace")[-n:]


class ScratchWorld:
    """Both servers plus the seeded fixtures, as one context manager.

    A second project is registered on the home screen (by booting a throwaway
    server against it) so the home list view has more than one row to lay
    out — one row is not a list, and a single-row list never clips.
    """

    def __init__(self, scratch: Path) -> None:
        self.scratch = scratch
        self.project_server = ScratchServer(scratch)
        self.home_server = ScratchServer(scratch, home=True)

    def __enter__(self) -> ScratchWorld:
        seed_project(self.project_server.project)
        seed_canon(self.scratch)
        second = self.scratch / "second-project"
        second.mkdir(parents=True, exist_ok=True)
        (second / "readme.md").write_text("# Second\n", encoding="utf-8")
        try:
            self.project_server.start()
            self._pin_blank_launch()
            self._register(second)
            self.home_server.start()
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def _pin_blank_launch(self) -> None:
        """Every page load opens a new blank composure, as the recipes assume.

        Since 0.4.2 a project opens on its own composure (`auto`): the only
        one with anything in it, else the last one used. Here that would be
        whatever the previous screen or scenario left behind — a council, a
        cards board — so a reload would land the next recipe on someone
        else's document. `new` is the user-facing "a new blank page" choice,
        set through the same endpoint the project window uses."""
        req = urllib.request.Request(
            self.project_server.base + "/api/project/composure",
            data=json.dumps({"launch": "new"}).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read()

    def _register(self, project: Path) -> None:
        """Put a second project on the home screen.

        `/api/home/*` only exists on a home-mode server, and the home server
        is not up yet — but boot *registers* whatever project it opened, so a
        throwaway project server against the second folder is the cheapest
        way in, and it exercises the real registration path rather than
        hand-writing projects.json.
        """
        extra = ScratchServer(self.scratch)
        extra.project = project
        extra.port = free_port()
        extra.base = f"http://127.0.0.1:{extra.port}"
        try:
            extra.start()
        finally:
            extra.stop()

    def __exit__(self, *_exc: object) -> None:
        self.home_server.stop()
        self.project_server.stop()


def cleanup(scratch: Path) -> None:
    shutil.rmtree(scratch, ignore_errors=True)
