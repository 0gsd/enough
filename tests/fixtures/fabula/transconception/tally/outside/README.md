# outside/: tally recorded and its round trips judged, outside enough

Made on 2026-11-22 by lane T1 of the 0.9 build. tally is the owner's own code, and agents run round trips of the
owner's own code in the sandbox kit (0.8 pins 9 and 21). Everything ran under macOS's `sandbox-exec` with a closed
profile, modelled on the experiment's `x0.sh`: no network, and no writing outside a scratch folder. Only the standard
library was used. Nothing was installed or fetched. enough never ran any of it. The maker
(`tests/make_tally_transconception.py`) reads this folder and never writes it.

| path | what |
|---|---|
| `environment.txt` | the interpreter (Python 3.13.11), the sandbox and the machine's system |
| `recording/` | the recorder's folder (`tools/transconception/harness.py record`, seeds 0 and 1, `--source` a copy of tally's source): `cases.json`, the two seeds' runs and `recorded.json` (53 cases, 161 steps, none unstable, source tree `0f26fb87…`, the fabulac's own). `cases.json` is the cases file `entail f as cases` gives for the fixed stage with the round trip's target, and the maker checks it. |
| `first-round-trip/` | the first blind rebuild, from `inputs/tally.fabulac.cosm`: `tally/`, `tests/`, `LICENSE`, `NOTES.md` (its 18 choices), `run.json`, `verdict.json` (judged with the recording's own rulings) and the own-tests logs. It is kept as the record that found the slip, and it is never gathered. |
| `py-roundtrip/` | the second blind rebuild, by another fresh agent, from `inputs/tally.9-fixed.fabulac.cosm`: `tally/` and `NOTES.md` (19 choices); `cases.json` (the cases file the recorded stage gives, the owner's ruling of B7 among its rulings; the maker checks it), `run.json`, `verdict.json` and the own-tests logs |

Two changes were made after each run, both by rule. First, a path on the recording machine inside a traceback is
written from the home folder (`~/`), as `promote_x0.py` does. This happened in six places, in cases E7 and E8. The
judge compares a crash by its exit status only. Second, each verdict was judged again on the rewritten files, so its
digests are theirs.

## The verdicts

- **First** (184 of 189 counted steps agree). There were five differences with no ruling. B7, steps 0 to 3: the help
  screens' words, which the fabulac does not give. E1, the files it leaves: the original's `undoes` names the cancelled
  entry's place among the entries, while the fabulac said "a line number from 1". The owner ruled B7 `free`
  ("Free"). On E1 the owner said "The fabulac slipped: fix it", so the words were fixed in stage 9 as a fix, not a
  ruling.
- **Second** (185 of 185 counted steps agree, passes). B7's four steps are shown as ruled differences. tally's own six
  tests pass on both rebuilds and on the original.

## Which Python

The recording ran on 3.13.11. The Python texts the reliances cite are 3.13.18. As a check, the same cases were
recorded again on 3.13.15, which was already on the machine. Four steps differ. B2 step 0: from 3.13.15 on, argparse
quotes the choices (`(choose from 'add', 'show', 'undo')`). E7 step 0 and E8 steps 0 and 1 are tracebacks whose
frame lines differ, and the judge reads them by exit status only. So B2 depends on the patch release. A recording
made on 3.13.18 would differ there. 3.13.18 was not run.
