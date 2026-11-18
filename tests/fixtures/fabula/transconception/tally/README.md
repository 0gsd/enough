# tally's cases: the migration trial's 161 steps

`tally.cases.json` holds the 53 scenarios (161 steps) of the migration trial of 2026-11-05, which judged a TypeScript
and a Swift tally written from `tests/fixtures/fabula/tally.fabulac.cosm` against the original
(`tests/fixtures/fabula/tally/`), as cases in the outside harness's shape (`tools/transconception/harness.py`). It
sits beside tally's pinned fixture, never over it: neither `tally.fabulac.cosm` nor `tally/` is touched.

The scenarios are the trial's own (`harness/diff.py`): groups A (ordinary use, 47 steps), B (command-line edges, 24),
C (numbers, 25), D (text, 34), E (the ledger as found, 30), F (at once, 1). Each case is `of` the command it drives
(`command.add`, `command.show`, `command.undo`, or `command.tally` when it drives several), sets `TALLY_FILE` to its
own folder as the trial did, and carries the trial's seed ledger, folder or burst. The file's `masks` are the trial's:
a ledger line's time is compared as `<int>` or `<float>`.

**Expected results.** Nobody has recorded tally with the recorder yet: that runs the original, and is the owner's.
The trial's document prints the original's result only where a port differed, so 18 of the 161 steps carry it
(B2, B7, C1, C2, E3a to E3d, E3h, E6, E9), and the files left behind for C1, C2 and E1; a value the report cut short
is the beginning it printed, named in `cut`. Every case's `expect-says` says which of its steps the document has and
which it does not. Each case's `recorded` names the source as the tally fabulac does (its tree digest): the trial ran
that folder, with Python 3.13.11.

Made by `python tools/transconception/trial_cases.py docs/fabula-survey-migration-trial.md
tests/fixtures/fabula/tally.fabulac.cosm tests/fixtures/fabula/transconception/tally/tally.cases.json`.
tally is MIT, as `tests/fixtures/fabula/tally/` says.
