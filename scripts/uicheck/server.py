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
Since 0.5.0 it holds the Thym round's too (copied from tests/fixtures/thym/):
a program with its enumeration, a plan, a trace, a package in both forms, a
hand-made reading, and a small deterministic program a run can land without
a model; and, for the package and unpack cards (U2), the measured morph
beside the notes and a sealed copy of the package in a folder of its own,
sealed at seed time, whose key lives only in this process.
Since 0.7 it holds a holograph that offers work (`talks/work-self/`, Ascribe
14.6's example) and the holder's program that makes its allograph, and the
project server talks to a stand-in Connect on a loopback port
(`connect.StandInConnect`, the client tests' `FakeRegistry` behind HTTP),
named by `ENOUGH_CONNECT_URL` and `ENOUGH_ALLOGRAPH_URL`: the allograph panel's sign-in, listing and
look-ups reach nothing but that.
"""

from __future__ import annotations

import hashlib
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

if str(REPO) not in sys.path:                    # tests.* (the stand-in Connect, the allograph fixture) import by name
    sys.path.insert(0, str(REPO))
from .connect import StandInConnect  # noqa: E402

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
# Thym (0.5.0), all in orchard/ beside the notes they were made from. The
# replay fixture is checkpoint A's real run of publish-story on notes.md, so
# its package (both forms) and its measured holomorph are the real thing; the
# reading is hand-made (no model here) with the §14 front matter and footer.
THYM_FIXTURES = REPO / "tests" / "fixtures" / "thym"
THYM_REPLAY = THYM_FIXTURES / "replay" / "publish-story" / "2026-11-01-2148-35b5"
THYM_PROGRAM = "publish-story.thym"            # + publish-story.thym.cosm, its enumeration
THYM_PLAN = "publish-story.plan.cosm"
THYM_TRACE = "2026-11-01-2148-35b5.trace.cosm"
THYM_PACKAGE = "notes.thym"                    # the folder form; notes.package.cosm the single file
THYM_READING = "notes.read-null-2026-11-01-1200.md"
FIXTURE_READING = """---
read_through: 'null'
---

Mara Okafor has kept the Hollins Lane orchard since 2019. Mara Okafor says that the old Bramley by the gate is the
oldest tree on the lane. It is reportedly the oldest tree. The parish records do not say when it was planted.

Every apple tree needs a second variety nearby to set fruit. This is how apples pollinate. The nursery leaflet says
the same.

The orchard pressed 140 litres of juice this year. It pressed 90 litres last year. The author counted the bottles on
12 October.

*a reading of notes.md through null, made here on 2026-11-01 by a model; the text stands unchanged*
"""
# A program with no step that asks a model, so a run lands with none
# running (thym-run-roundtrip), on a text no other recipe reads.
THYM_RULES_PROGRAM = "count-words.thym"
FIXTURE_RULES_PROGRAM = """thym 0

program count-words
  why: how long a text is, counted in words, and no model is asked.

  takes story: text
  gives n: number

  give words story                           -- every word of the text, counted by rule
end
"""
HARVEST = "harvest.md"
# Writing and running Thym (0.6, U1c), beside the orchard notes: a program
# refused at a known line (an unknown move on line 9, the compiler's words
# name it), a `thym 1` program that takes a folder and a short and gives two
# outputs (asks no model, so a scratch server runs it by rules), the folder
# it reads, and a short whose long line `tighten` (shipped; it asks a model)
# would reword, so its plan shows a model step refused at its statement.
THYM_BROKEN = "broken.thym"
THYM_BROKEN_LINE = 9
FIXTURE_BROKEN = """thym 1

program broken
  why: a program the compiler refuses at line 9, by name.

  takes story: text
  gives n: number

  let x = frobnicate story
  give words story
end
"""
THYM_TRIES_RUN = "2026-11-05-1956-ae6e"
THYM_TWO = "two-outs.thym"
FIXTURE_TWO = """thym 1

program two-outs
  why: a folder's Python files listed one to a line, and how many files a short has beside it.

  takes repo: folder, s: short
  gives n: number, listing: short

  let rows = for each p in repo where suffix is py
    keep join [p.path, (say p.lines)] with " · "
  end
  give n: count repo
  give listing: join rows
end
"""
THYM_REPO = "little-repo"
# A list as an input (0.6, U1d): the suite's join-the-notes (`takes notes: list of short`), copied beside the
# orchard notes; and a project program named as a shipped one is (`open-house.thym` at the project's top, a
# program of its own that takes a short), so a run card lists both and `where` tells them apart.
THYM_LIST = "join-the-notes.thym"
THYM_SAME = "open-house.thym"
FIXTURE_SAME = """thym 0

program open-house
  why: the project's own open-house, named as the shipped one is: the words of a short, counted by rule.

  takes s: short
  gives n: number

  give words s
end
"""
FIXTURE_REPO = {"tool.py": "def tool():\n    return 1\n", "lib/util.py": "X = 2\n", "README.md": "# little repo\n"}
THYM_LONG = "long-lines.md"
FIXTURE_LONG = ("A short line.\n\nThis line runs on for far longer than thirty words, so that the shipped tighten "
                "program has a line to reword, and its plan has a step that asks a model, which a scratch server cannot "
                "answer, so the plan says so at the statement.\n")
# The package and unpack cards (0.5.0, U2). The author's morph beside the
# notes (a copy of the package's measured one), so "package…" packs a morph
# as well — and a re-packed notes.thym/ keeps the scales the EMF face draws.
# A sealed copy of checkpoint A's package (THYM.md 15.3), alone in a folder of
# its own as if it had come from someone: sealed at seed time with enough's own
# vault, so its key exists only in this process (THYM_SEALED_KEY), never in the
# scratch project, for the round trip to unpack it with. THYM_ORCHARD is where
# it was seeded, so the round trip can compare the unpacked bytes on disk.
THYM_MORPH = "notes.morph.cosm"
THYM_RECEIVED = "received"                     # orchard/received/notes.thym.enc
THYM_SEALED = "notes.thym.enc"
THYM_SEALED_KEY = ""
THYM_ORCHARD: Path | None = None
FIXTURE_HARVEST = """# The harvest list

Bramleys from the gate tree, Discovery from the north row, and a basket of
windfalls for the juice. Next year we will weigh them as well as count them.
"""
CANON_VOLUME = "field-notes"   # in the scratch store: notes.md (+ twin), meadow/

# The fabula round (0.6, U1a), seeded by _seed_fabula() into `works/`:
# `tally/`, a small Python tool with its finished fabulac beside it (from
# tests/fixtures/fabula/, with the five stages' runs written into its
# `derived` so the build reads as complete), the cshort and the catem it
# compiled into (the cshort's rebuilt files are the tool's own, as stand-ins:
# the fixture ships only its CSHORT.md); `tiny-tool/`, a folder of Python with
# no fabulac, which a build lands as the outline (no model in the scratch
# environment); a poem with no twin, which the decompile card suggests
# reading as verse; and a letter whose new-named twin sits beside its
# old-named one, the old one listed as an ordinary file with its note.
FABULA_FIXTURES = REPO / "tests" / "fixtures" / "fabula"
FABULA_DIR = "works"
FABULA_TOOL = "tally"
FABULA_CSHORT = "tally.cshort-2026-11-05-1412"
FABULA_CATEM = "tally.catem-2026-11-05-1415.md"
FABULA_TINY = "tiny-tool"
FABULA_POEM = "rain.md"
FIXTURE_POEM = """Rain on the slates at four,
the gutters full of it,
a blackbird at the door
who will not quit.

The kettle starts to sing,
the window runs with grey;
I hold the warm cup's ring
and let the day.
"""
FABULA_LETTER = "letter.md"
FABULA_RUNS = ("survey-the-repo", "read-the-history", "read-every-file", "fold-the-whole", "raise-the-questions")

# The dialectic in the page (0.6, U1b), seeded by _seed_dialectic() into
# `talks/`, each in a folder of its own so a scenario that writes a sitting or
# settles one never changes what a screen draws:
# - `kinds/`: the morning-close guide and its fabulan (tests/fixtures/fabula/
#   guides/), whose one open question is joined by six more, one of each other
#   kind an answer takes (choice with "other", yes-no, number in a range, date,
#   ref, span) — for the card's screens;
# - `answer-<lang>/`: the same pair again, one for each language the matrix
#   runs (scenarios run once per language, and a sitting sent and settled
#   stays sent), for the scenario that answers one of each kind by keyboard,
#   sends the sitting and settles it by rules; an eighth question, about the
#   whole of an item, is answered there so that something waits for a model;
# - `sitting/`: the same pair with the sitting of tests/fixtures/dialectic/
#   beside it, written and not yet settled (its question shows as waiting);
# - `self/`: the sample holograph with Ascribe's bank raised and the journal's
#   two good candidates landed (each asked yes / partly / no), one affinity
#   public, and the holder's program `talks/open-self.thym` (for the isograph);
# - `self-ask-<lang>/`: a copy with its bank raised for each language, for the
#   scenario that sees a personal-data refusal and proves no cloud is offered;
# - `self-pii/`: tests/fixtures/ascribe/bad/pii, whose checks warn with advice;
# - `bare/`: the guide and its fabulan with module D cut away: a volume with
#   no questions yet (raise the questions).
DIALECTIC_DIR = "talks"
DIALECTIC_FIXTURES = REPO / "tests" / "fixtures" / "dialectic"
# The check's own guide, twin and sitting (0.6, U1c): copies of the suite's as they stood at 43f70be (the twin with
# its nine questions, the sitting answering the summary and who). The suite's fixtures follow the specification's
# example and change with it; the screens and scenarios count questions, so they read these, which nothing else moves.
DIALECTIC_OWN = Path(__file__).resolve().parent / "fixtures" / "dialectic"
ASCRIBE_FIXTURES = REPO / "tests" / "fixtures" / "ascribe"
DIALECTIC_KINDS = """  - id: D:question/tone
    type: question
    about: C:voice/meadow-we#tone
    asks: How would you name the guide's tone?
    why: ambiguous
    kind: choice
    options: [plain, warm, formal]
    options-open: true
    hint: Pick one, or say it in a word of your own.
    to: author
    raised: {by: person, from: person, at: 2026-11-05T10:05:00Z}
    state: open
  - id: D:question/meant-to-reassure
    type: question
    about: P:claim/daily-summary-keeps-owners#intended
    asks: Did you mean the last sentence to reassure the owners?
    why: intent
    kind: yes-no
    to: author
    raised: {by: person, from: person, at: 2026-11-05T10:05:00Z}
    state: open
  - id: D:question/retry-hour
    type: question
    about: T:event/close-runs#retry-hour
    asks: At what hour is a failed close tried again?
    why: missing
    kind: number
    range: [0, 23]
    hint: An hour of the day, from 0 to 23.
    to: author
    raised: {by: person, from: person, at: 2026-11-05T10:05:00Z}
    state: open
  - id: D:question/published
    type: question
    about: R:release/handbook#at
    asks: When was the guide first published?
    why: missing
    kind: date
    hint: A date, a year-month or a year.
    to: author
    raised: {by: person, from: person, at: 2026-11-05T10:05:00Z}
    state: open
  - id: D:question/feed-source
    type: question
    about: P:claim/every-customer-has-a-feed#source
    asks: Who says that every customer has a bank feed?
    why: missing
    kind: ref
    options: ['E:']
    to: author
    raised: {by: person, from: person, at: 2026-11-05T10:05:00Z}
    state: open
  - id: D:question/retry-lines
    type: question
    about: P:claim/late-feed-delays-summary#grounds
    asks: Which lines say what happens when the close waits?
    why: missing
    kind: span
    to: author
    raised: {by: person, from: person, at: 2026-11-05T10:05:00Z}
    state: open
  - id: D:question/close-runs-right
    type: question
    about: T:event/close-runs
    asks: Is this right, and if not, what is? "Meadow runs the close for every customer once the bank feeds have arrived."
    why: unsure
    kind: text
    to: author
    raised: {by: person, from: person, at: 2026-11-05T10:05:00Z}
    state: open
"""
DIALECTIC_LANGS = ("en", "de", "fr", "es", "ja", "zh")
# 0.7 (P4): the holograph whose allograph the panel makes and lists (`talks/work-self/`), and its holder's program.
ALLOGRAPH_HOLO = "work-self"
ALLOGRAPH_PROGRAM = "open-for-work.thym"
OPEN_SELF = """thym 1

program open-self
  why: what a person says they like, as they say it, and nothing more.
  takes h: volume
  gives i: volume

  for each a in h where kind is affinity
    emit a
  end
  give project h as isograph
end
"""
JOURNAL_PROPOSALS = """candidates:
  - kind: skill
    name: Splicing an eye by hand
    summary: Splices a new eye into a mooring line by hand, as a retired harbour pilot once showed.
    form: knots
    span: {lines: "3"}
    confidence: 0.8
    cites: [P:claim/spliced-an-eye]
  - kind: yearning
    name: Reading the weather
    summary: Wants to learn to read the weather from the clouds.
    about: the weather
    span: {lines: "5"}
    confidence: 0.7
    cites: [P:claim/learn-the-weather]
"""


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
    _seed_thym(emf)
    _seed_fabula(project / FABULA_DIR)
    _seed_dialectic(project / DIALECTIC_DIR)


def _seed_dialectic(talks: Path) -> None:
    """The dialectic's volumes (see DIALECTIC_* above), all copies."""
    import datetime as _dt
    from enough import ascribe as _a
    from enough import macrocosm as _mc
    guides = DIALECTIC_OWN
    twin = (DIALECTIC_OWN / "close.md.fabulan.cosm").read_text(encoding="utf-8")
    for name in ("kinds", "sitting", "bare") + tuple(f"answer-{lang}" for lang in DIALECTIC_LANGS):
        d = talks / name
        d.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(guides / "close.md", d / "close.md")
        text = twin
        if name == "kinds" or name.startswith("answer-"):
            # the six questions go after the open one, before the session item
            text = text.replace("  - id: D:session/session-1\n", DIALECTIC_KINDS + "  - id: D:session/session-1\n", 1)
        elif name == "bare":
            # module D cut away, and what cited its session with it
            text = text[:text.index("  # --- D: the dialectic")]
            text = text.replace(", D:session/session-1]", "]").replace(
                "\n      answered: {summary: {sources: [D:session/session-1], confidence: 1}, who: {sources: "
                "[D:session/session-1], confidence: 1}}", "")
        (d / "close.md.fabulan.cosm").write_text(text, encoding="utf-8")
    shutil.copyfile(DIALECTIC_OWN / "close.md.fabulan.answers-2026-11-05-1200.cosm",
                    talks / "sitting" / "close.md.fabulan.answers-2026-11-05-1200.cosm")
    shutil.copytree(ASCRIBE_FIXTURES / "bad" / "pii", talks / "self-pii", dirs_exist_ok=True)
    at = _dt.datetime(2026, 11, 5, 19, 30, tzinfo=_dt.timezone.utc)
    for name in ("self",) + tuple(f"self-ask-{lang}" for lang in DIALECTIC_LANGS):
        holo = talks / name
        shutil.copytree(ASCRIBE_FIXTURES / "sample-self", holo, dirs_exist_ok=True)
        if name == "self":
            journal = (ASCRIBE_FIXTURES / "journal" / "journal.md").read_bytes()
            props = _mc.yaml_load(JOURNAL_PROPOSALS)["candidates"]
            got, _refused = _a.candidates(holo, props, text="journal.md", sha256=hashlib.sha256(journal).hexdigest(),
                                          feed=None, at=at, made={"move": "propose", "run": "seed"})
            _a.land_candidates(holo, got)
            aff = holo / "A" / "affinities.cosm"
            src = aff.read_text(encoding="utf-8")
            if "visibility: public" not in src:
                src = src.replace("    type: affinity\n", "    type: affinity\n    visibility: public\n", 1)
                aff.write_text(src, encoding="utf-8")
        _a.raise_bank(holo, at=at)
    (talks / "open-self.thym").write_text(OPEN_SELF, encoding="utf-8")
    # 0.7 (P4): a holograph that offers work, Ascribe 14.6's example (a form `bakery` grounded in FEED, an experience
    # of it and a skill, both public), and the holder's program that makes its allograph.
    from tests.test_ascribe_module import OPEN_FOR_WORK, _for_work
    work = talks / ALLOGRAPH_HOLO
    shutil.copytree(ASCRIBE_FIXTURES / "sample-self", work, dirs_exist_ok=True)
    _for_work(work)
    (talks / ALLOGRAPH_PROGRAM).write_text(OPEN_FOR_WORK, encoding="utf-8")


def _seed_fabula(works: Path) -> None:
    """The fabula round's things (see FABULA_* above), all copies."""
    works.mkdir(parents=True, exist_ok=True)
    shutil.copytree(FABULA_FIXTURES / FABULA_TOOL, works / FABULA_TOOL, dirs_exist_ok=True)
    fab = (FABULA_FIXTURES / f"{FABULA_TOOL}.fabulac.cosm").read_text(encoding="utf-8")
    # The fixture names its build `program: build-fabulac.thym`; the build's
    # state reads a stage as landed from `derived.runs`, so the five runs go in.
    runs = ", ".join(f"{{program: {p}, run: 2026-11-05-13{50 + i}-e4f{i}, at: 2026-11-05T13:{50 + i}:00Z, "
                     f"model: anthropic/claude-opus-5.5, route: cloud, provider: openrouter}}"
                     for i, p in enumerate(FABULA_RUNS))
    fab = fab.replace("stages: [survey, history, read, fold, question]}",
                      f"stages: [survey, history, read, fold, question], runs: [{runs}]}}", 1)
    (works / f"{FABULA_TOOL}.fabulac.cosm").write_text(fab, encoding="utf-8")
    cshort = works / FABULA_CSHORT
    cshort.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FABULA_FIXTURES / FABULA_CSHORT / "CSHORT.md", cshort / "CSHORT.md")
    shutil.copyfile(FABULA_FIXTURES / FABULA_TOOL / "README.md", cshort / "README.md")
    (cshort / FABULA_TOOL).mkdir(exist_ok=True)
    for f in sorted((FABULA_FIXTURES / FABULA_TOOL / FABULA_TOOL).glob("*.py")):
        shutil.copyfile(f, cshort / FABULA_TOOL / f.name)
    shutil.copyfile(FABULA_FIXTURES / FABULA_CATEM, works / FABULA_CATEM)
    shutil.copytree(THYM_FIXTURES / "inputs" / FABULA_TINY, works / FABULA_TINY, dirs_exist_ok=True)
    (works / FABULA_POEM).write_text(FIXTURE_POEM, encoding="utf-8")
    # A letter with its twin under the new name, and the old-named twin still
    # beside it (the orchard notes' twin, declared fabula/1 under the new name).
    shutil.copyfile(COSM_FIXTURES / "emf" / "notes.md", works / FABULA_LETTER)
    old = (COSM_FIXTURES / "emf" / "notes.md.cosm").read_text(encoding="utf-8")
    old = old.replace("id: emf/notes-md\n", "id: emf/works--letter-md\n", 1)
    old = old.replace("source: {path: notes.md,", f"source: {{path: {FABULA_LETTER},", 1)
    (works / f"{FABULA_LETTER}.cosm").write_text(old, encoding="utf-8")
    new = old.replace("oes: emf/1\n", "oes: fabula/1\n", 1)
    new = new.replace("id: emf/works--letter-md\n", "flavour: fabulan\nid: fabula/works--letter-md\n", 1)
    (works / f"{FABULA_LETTER}.fabulan.cosm").write_text(new, encoding="utf-8")


def _seed_thym(orchard: Path) -> None:
    """The Thym round's volumes beside the orchard notes (see THYM_* above):
    copies, never the fixtures themselves, so a run that writes beside them
    touches only the scratch project."""
    shutil.copyfile(THYM_FIXTURES / "programs" / THYM_PROGRAM, orchard / THYM_PROGRAM)
    # `python -m enough.thym enumerate` names a program's items <stem>.thym.cosm.
    shutil.copyfile(THYM_FIXTURES / "expected" / "publish-story" / "items.cosm",
                    orchard / THYM_PROGRAM.replace(".thym", ".thym.cosm"))
    shutil.copyfile(THYM_FIXTURES / "expected" / "publish-story" / "plan.cosm", orchard / THYM_PLAN)
    shutil.copyfile(THYM_REPLAY / THYM_TRACE, orchard / THYM_TRACE)
    shutil.copytree(THYM_REPLAY / "outputs" / "notes.thym", orchard / THYM_PACKAGE, dirs_exist_ok=True)
    shutil.copyfile(THYM_REPLAY / "outputs" / "out.package.cosm", orchard / "notes.package.cosm")
    (orchard / THYM_READING).write_text(FIXTURE_READING, encoding="utf-8")
    (orchard / THYM_RULES_PROGRAM).write_text(FIXTURE_RULES_PROGRAM, encoding="utf-8")
    (orchard / HARVEST).write_text(FIXTURE_HARVEST, encoding="utf-8")
    (orchard / THYM_BROKEN).write_text(FIXTURE_BROKEN, encoding="utf-8")
    # A tighten run whose first reword failed `length` and was asked again (its record keeps the try).
    shutil.copyfile(THYM_FIXTURES / "replay" / "tighten" / THYM_TRIES_RUN / f"{THYM_TRIES_RUN}.trace.cosm",
                    orchard / f"{THYM_TRIES_RUN}.trace.cosm")
    (orchard / THYM_TWO).write_text(FIXTURE_TWO, encoding="utf-8")
    shutil.copyfile(THYM_FIXTURES / "programs" / THYM_LIST, orchard / THYM_LIST)
    (orchard.parent / THYM_SAME).write_text(FIXTURE_SAME, encoding="utf-8")
    (orchard / THYM_LONG).write_text(FIXTURE_LONG, encoding="utf-8")
    for rel, text in FIXTURE_REPO.items():
        f = orchard / THYM_REPO / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    shutil.copyfile(THYM_REPLAY / "outputs" / "notes.thym" / "morph.cosm", orchard / THYM_MORPH)
    _seed_sealed(orchard)


def _seed_sealed(orchard: Path) -> None:
    """orchard/received/notes.thym.enc: the seeded package's single file,
    sealed with `enough.thym.vault.seal` (pure: no state, no network, no
    seam to cross), the key kept in THYM_SEALED_KEY and nowhere on disk."""
    global THYM_SEALED_KEY, THYM_ORCHARD
    from enough.thym import vault
    single = orchard / "notes.package.cosm"
    sealed, key = vault.seal(single.read_bytes(), path=single.name, slug="notes")
    received = orchard / THYM_RECEIVED
    received.mkdir(parents=True, exist_ok=True)
    (received / THYM_SEALED).write_bytes(sealed)
    THYM_SEALED_KEY, THYM_ORCHARD = key, orchard


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
        # Seams set after build_env(): only ever an address inside this run (the stand-in Connect's).
        self.extra_env: dict[str, str] = {}
        self.port = free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.project = scratch / "project"
        self._proc: subprocess.Popen[bytes] | None = None
        self._log = scratch / ("home-server.log" if home else "server.log")

    def start(self) -> None:
        env = build_env(self.scratch)
        env.update(self.extra_env)
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
        self.connect: StandInConnect | None = None

    def __enter__(self) -> ScratchWorld:
        seed_project(self.project_server.project)
        seed_canon(self.scratch)
        second = self.scratch / "second-project"
        second.mkdir(parents=True, exist_ok=True)
        (second / "readme.md").write_text("# Second\n", encoding="utf-8")
        try:
            # 0.7 (P4): the Allograph Registry the project server talks to, on a loopback port of this run.
            self.connect = StandInConnect()
            self.connect.start()
            self.project_server.extra_env["ENOUGH_CONNECT_URL"] = self.connect.url
            self.project_server.extra_env["ENOUGH_ALLOGRAPH_URL"] = self.connect.url
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
        cards plane — so a reload would land the next recipe on someone
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
        if self.connect is not None:
            self.connect.stop()
            self.connect = None


def cleanup(scratch: Path) -> None:
    shutil.rmtree(scratch, ignore_errors=True)
