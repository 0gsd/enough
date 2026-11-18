# tools/transconception

The outside tools of a transconception (MacroCOSM 18.4.9; Thym 20.10): the recorder, the runner and the judge, and
two converters. Promoted for 0.8 from the experiment's kit (`docs/v070-x0-sandbox/`, ignored by git), with its file
shapes kept, so that the experiment's own results still read.

**These are the owner's to run, in the owner's sandbox.** enough never imports or starts any of them, and no agent
runs the recorder or the runner: they run other people's programs. enough reads the files they leave
(`entail f as cases` writes the cases file; `gather recorded with f` reads a recording folder; `gather verdict with f`
reads a verdict). The sandbox wrapper stays the owner's: the experiment's `x0.sh` (in the kit) starts these files
under macOS's `sandbox-exec`, with no network and no writing outside a scratch folder the owner names. Each tool is
one file of the standard library, so `python -I <file>` runs it.

## harness.py: the recorder, the runner, the judge

    python -I harness.py record CASES IMPL OUT_FOLDER [--seeds 0,1] [--source DIR] [--commit SHA]
    python -I harness.py run    CASES IMPL OUT.json [--seed N]
    python -I harness.py stable RECORDED_A.json RECORDED_B.json OUT.json
    python -I harness.py judge  CASES RECORDED.json RUN.json RULINGS.json|- VERDICT.json

- **record** (the recorder): runs the original on the cases once per hash seed and keeps the steps both agree on.
  It writes the recording folder enough reads: `cases.json` (the cases file, byte for byte), `recorded-seed<N>.json`,
  and `recorded.json` with `unstable` (the steps the seeds disagree on; each needs a ruling) and `source`: the
  source it was recorded from, `{tree, commit}`, the tree digest by MacroCOSM 18.4.1's rule over `--source`, the
  commit from `--commit` or a `COMMIT` file in that folder. A recording that names no source is never taken as
  fresh by enough. (x0.sh's `record` did the same in three calls, `run`, `run`, `stable`; both forms work.)
- **run** (the runner): drives one implementation at its boundary only, each case in a fresh folder: argv, stdin,
  the environment, the case's files, stdout, stderr, exit status, and the files it leaves (`written`).
- **judge**: compares a cshort's run with the recording, applies the transconceiver's rulings for the cshort's
  target (picked by its label: `go-apart` is go's), and writes the verdict. `RULINGS` may be `-`: the cases file's
  own `rulings`, which `entail f as cases` derives from the fabulac (survey 2.4: derived, never edited).

### The files

- **The cases file** (`<folder>.cases.json`, named in the fabulac's catalog as `cases:`): `{repo, fabulac, source,
  ..., cases: [...], rulings: {targets: {...}}}`. A case: `{id, of, from, files, env, cwd, steps, reliances, note}`
  as x0 wrote it; a step is an argument list or `{argv, stdin}`; a file is text, `{b64}`, `{symlink}` or
  `{dir: true}`; `<CASE>` in an argument or an environment value is the case's folder. Beside them, read by enough
  only: `item` (the fabulac's `P:case`), `expect` (`{steps: [{exit, out, err}], written}`), `recorded` (the source,
  the recording, its digest, the runtime, the seeds), `stale` (why the expectation does not stand on the source
  now). New in 0.8 and optional: a case's `burst` (`{argv, times}`: that many copies of one step at once, first),
  the file's `masks` (`{out|err|written: [{pattern, to}]}`, regular expressions applied after the folder is masked:
  the tally trial masked its ledger's times this way), and `source`.
- **IMPL.json**: `{label, command, env, path, scratch, work, timeout}` (x0.sh writes it).
- **A run, a recording**: `{impl, seed, cases_digest, python, rows: [{id, of, argv, run: {steps, written,
  burst?}}]}`; a recording adds `unstable`, `seeds` and `source`.
- **A verdict**: `{cshort, against, target, recorded_digest, run_digest, rulings_digest, steps: {kept, agree},
  share, passes_95, unruled, passes, findings, source?, stale?}`. A finding's kinds: `interface not ruled`, `ruled
  difference`, `ruled change not seen`, `original unstable, not ruled`, `allowance unknown to the judge`, `UNRULED
  difference`, and (0.8) `recorded against another source`. A verdict from a recording of another source than the
  cases file names says `stale` and does not pass.

## trial_cases.py

    python tools/transconception/trial_cases.py TRIAL_MD TALLY_FABULAC OUT_JSON

The migration trial's 53 scenarios (161 steps, `docs/fabula-survey-migration-trial.md`, ignored by git) as tally's
cases file, `tests/fixtures/fabula/transconception/tally/tally.cases.json`. It reads the document as text and runs
nothing of it; the original's results come from what the trial's report printed (only where a port differed).

## promote_x0.py

The experiment's working fabulacs into 0.8's shapes (lane W1-X1); see its docstring.

## drivers/sloppy_cases_driver.py

The boundary the experiment agreed for sloppy-xml-py, a library with no command line of its own (worksheet item
S-I0): one request on stdin, the result as JSON lines. Copied unchanged from the kit. It imports the library under
test, so it runs only inside the sandbox, with `PYTHONPATH` at the copy being judged.
