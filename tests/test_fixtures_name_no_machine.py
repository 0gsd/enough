"""A recorded run kept as a fixture names no path on the machine that recorded it.

The runtime writes the folder a run's inputs were read from into its trace (`inputs_root`), which on the recording
machine is an absolute path: a home folder's name, a scratch folder's. The suite's recordings say `.` there (a replay
is given the folder, and reads nothing from this field that it needs), and three of them reached the repository,
and from there another application's copy of the suite, saying where they were made. This holds the convention.
"""

from __future__ import annotations

import re
from pathlib import Path

REPLAY = Path(__file__).resolve().parent / "fixtures" / "thym" / "replay"
MACHINE = re.compile(r"(?m)^\s*inputs_root:\s*(?!\.\s*$)\S.*$|/Users/|/home/|/private/tmp/|/var/folders/|[A-Za-z]:\\\\Users\\\\")


def test_no_recorded_run_names_a_path_on_the_machine_that_made_it():
    found = []
    for p in sorted(REPLAY.rglob("*.cosm")):
        for m in MACHINE.finditer(p.read_text(encoding="utf-8")):
            found.append(f"{p.relative_to(REPLAY)}: {m.group(0).strip()[:90]}")
    assert not found, "a recording names a machine path (write `inputs_root: .`):\n" + "\n".join(found)
