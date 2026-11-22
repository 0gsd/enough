# outside/: tally recorded and its round trip judged, outside enough

Made on 2026-11-22 by lane T1 of the 0.9 build. tally is the owner's own code, and agents run round trips of the
owner's own code in the sandbox kit (0.8 pins 9 and 21). Everything ran under macOS's `sandbox-exec` with a closed
profile, modelled on the experiment's `x0.sh`: no network, and no writing outside a scratch folder. Only the standard
library was used. Nothing was installed or fetched. enough never ran any of it. The maker
(`tests/make_tally_transconception.py`) reads this folder and never writes it.

| path | what |
|---|---|
| `environment.txt` | the interpreter (Python 3.13.11), the sandbox and the machine's system |
| `recording/` | the recorder's folder (`tools/transconception/harness.py record`, seeds 0 and 1, `--source` the copy of tally's source): `cases.json` (the cases file `entail f as cases` gives for the final stage with the round trip's target; the maker checks it), the two seeds' runs and `recorded.json` (53 cases, 161 steps, none unstable, source tree `0f26fb87…`, the fabulac's own) |
| `py-roundtrip/` | the blind Python rebuild: `tally/` (the program), `tests/`, `LICENSE` and `NOTES.md` (its 18 choices), written by a fresh agent from `inputs/tally.fabulac.cosm` alone; `run.json` (the runner on the rebuild), `verdict.json` (the judge, with the cases file's own rulings for python), and `own-tests-*.log` (tally's own six tests on the original and on the rebuild) |

Two changes were made after the run, both by rule. First, a path on the recording machine inside a traceback is
written from the home folder (`~/`), as `promote_x0.py` does. This happened in six places, in cases E7 and E8. The
judge compares a crash by its exit status only. Second, the verdict was judged again on the rewritten files, so
its digests are theirs.

## The verdict

184 of 189 counted steps agree (97.4%). Five differences have no ruling, so the verdict does not pass, and the round
trip's evidence stands at level 1:

- B7, steps 0 to 3 (`--help`, `-h`, `add --help`, `show -h`): the help screens' description and help strings. The
  fabulac gives the help screen's layout (`C:reliance/argparse-help`) but not the words. The rebuild wrote its own.
- E1, the files it leaves: with blank lines in the ledger, the original's `undoes` names the cancelled entry's place
  among the entries (2). The rebuild names its physical line (4). The fabulac says "a line number from 1" and "its
  line", which reads as the rebuild's reading.

Both need the owner's ruling: see the lane's batch. With the two case rulings proposed there, which are not applied
anywhere, the judge passes 184/184 and gate 1 holds.

## Which Python

The recording ran on 3.13.11. The Python texts the reliances cite are 3.13.18. As a check, the same cases were
recorded again on 3.13.15, which was already on the machine. Four steps differ. B2 step 0: from 3.13.15 on, argparse
quotes the choices (`(choose from 'add', 'show', 'undo')`). E7 step 0 and E8 steps 0 and 1 are tracebacks whose
frame lines differ. So B2 depends on the patch release. A recording made on 3.13.18 would differ there, and a
rebuild run on it would differ from this recording. 3.13.18 was not run.
