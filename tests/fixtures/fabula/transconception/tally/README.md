# tally's transconception: the conformance fixture

tally's whole transconception, from `ground repo with f` to a layout and a cshort in Go and in Rust, as a Thym
conformance suite a second implementation can be held to (THYM 24.3's folder shape; `python -m enough.thym conform
<this folder>` reads it as it reads `tests/fixtures/thym/`). It sits beside tally's own pinned fixture
(`tests/fixtures/fabula/tally/` and `tally.fabulac.cosm`), never over it: those are copied in, never written. The
folder reads alone: everything its runs take is inside it, and no plan, trace or record names a path outside it.

Made by `python tests/make_tally_transconception.py` (every run id and clock pinned). Re-make it, never hand-edit it.

| path | what |
|---|---|
| `tally.cases.json` | the migration trial's 53 scenarios (161 steps) as cases (below); made by W2-X4, kept as it is |
| `programs/<name>.thym` | the six programs, each the text's own under a `thym 1` line, byte for byte: `ground-the-fabulac`, `weigh-a-target`, `hand-out-the-cases` and `entail-in-a-language` (Thym 20.10), `raise-the-questions` (20.6), `settle-the-answers` (22.4) |
| `expected/<name>/` | each program's enumeration (`items.cosm`) and plan (`plan.cosm`, its latest run's) |
| `inputs/` | what the runs take: `tally/` (a copy of tally's source; its tree digest is the fabulac's `source.tree`), `tally.cases.json` (a copy of the one above), the stage fabulacs, the two answers volumes, `go.txt`, `rust.txt`, and `spikes/` |
| `replay/<name>/<run-id>/` | the ten recorded runs, each with its engine calls: they replay with no model and no engine |
| `landed/` | the host's landing (`tc.land_in_language`) beside a copy of the final fabulac: two layouts, two cshorts, each entry in `shorts` |
| `recorded/checks.json` | what the fabula's lint says of each stage (errors and warnings) |
| `recorded/gates.json` | what gate 1 (`ready_to_keep`) and gate 2 (`ready_to_entail`, in Go and in Rust) report on each stage |

## The path

| # | made by | stage file (in `inputs/`) |
|---|---|---|
| 0 | the maker: tally's fabulac with `purpose: transconception`, nothing else | `tally.0-kept.fabulac.cosm` |
| 1 | `ground-the-fabulac` (`2026-11-18-1200-a901`), rules: 56 reliances and an assumption | `tally.1-grounded.fabulac.cosm` |
| - | `hand-out-the-cases` (`…-a902`), rules: the cases file again, its rulings derived (`outputs/cases.md`) | |
| 2 | `raise-the-questions` (`…-a903`): who rules, the lane, five batched ruling questions over 78 items | `tally.2-asked.fabulac.cosm` |
| - | the first sitting, simulated | `tally.2-asked.fabulac.answers-2026-11-18-1230.cosm` |
| 3 | `settle-the-answers` (`…-a904`) | `tally.3-settled.fabulac.cosm` |
| 4 | `raise-the-questions` (`…-a905`): the transconceiver's five statements | `tally.4-asked-again.fabulac.cosm` |
| - | the second sitting, simulated | `tally.4-asked-again.fabulac.answers-2026-11-18-1250.cosm` |
| 5 | `settle-the-answers` (`…-a906`) | `tally.5-ruled.fabulac.cosm` |
| 6 | `weigh-a-target` in go (`…-a907`): feasible-with, the option reader a gap | `tally.6-weighed-go.fabulac.cosm` |
| 7 | `weigh-a-target` in rust (`…-a908`): feasible-with, whole numbers without limit and the option reader | `tally.7-weighed.fabulac.cosm` |
| 8 | the maker: each spike's level read from its verdict (`tc.spike_from_verdict`) | `tally.fabulac.cosm` |
| - | `entail-in-a-language` in go (`…-a909`) and in rust (`…-a910`): a layout, then the code, apart | |
| - | the maker: `tc.land_in_language` for each | `../landed/` |

## Recorded, simulated, never claimed

- **Recorded as it ran**: every rule (ground, the cases, the questions, settling, landing, the lint, the gates).
- **The sittings are simulated.** Nobody sat. Every ruling question is answered "as proposed" (`kept`, for an item
  never ruled); the lane `open` (tally is MIT); who rules "nobody: a transconceiver simulated for the conformance
  fixture of 0.8"; the five statements from tally's own files, each saying "(simulated)". Each answers volume's
  session says it is simulated. tally's own open questions of 2026-11-05 are left open.
- **The model is a recorded fake** (`engine: model:scripted`): the weighings (2 on every point a model answers, a row
  `written` for what no ground entry answers), the layouts (one file for every interface) and the cshorts' files
  (empty stubs, each saying it was never built). No model was asked anything.
- **The spikes are simulated.** There is no Go or Rust build of tally and no spike of it. `inputs/spikes/*.json` are
  verdicts written, not judged, each with `simulated` saying so and no finding; they let the path reach
  `target-confirmed`. Stage 7 records the gates before them (level 0: target-confirmed does not hold).
- **No evidence is claimed.** Each cshort's entry says `evidence: []`: not judged. Nothing was built or run. The round
  trip is not claimed either: there is no N:target in Python and tally's Python cshort of 2026-11-05 was never
  judged, so `round-trip` fails on every stage and neither gate holds, as `recorded/gates.json` says. The trial of
  2026-11-05 judged a TypeScript and a Swift tally, never Go or Rust; its 18 recorded steps are in the cases file and
  judge nothing here. `keep-the-record` and `keep-the-verdict` (Thym 20.10) are not in the suite: there is no
  recording of tally and no verdict on a cshort of it to gather.

## Passing

A compiler and a runtime conform on this folder as on `tests/fixtures/thym/` (THYM 24.3): every program compiles,
enumerates, compiles back and plans as expected; `ground-the-fabulac`, whose plan asks nothing, runs again (under its
recorded run's id and clock, through the host's syntax engine, over `inputs/tally/`) to its recording's outputs byte
for byte; every run under `replay/` re-runs to its recorded outputs. `tests/test_transconception_fixture.py` also holds
the stages to the runs that made them, the checks and gates to what `recorded/` says, and the landed cshorts to their
own checks (`surface-answered`, `apart`, `evidence-stated`).

## The cases file

`tally.cases.json` holds the 53 scenarios (161 steps) of the migration trial of 2026-11-05, which judged a TypeScript
and a Swift tally written from `tests/fixtures/fabula/tally.fabulac.cosm` against the original
(`tests/fixtures/fabula/tally/`), as cases in the outside harness's shape (`tools/transconception/harness.py`).

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
