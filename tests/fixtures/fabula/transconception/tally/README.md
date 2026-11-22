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
| 0 | the maker: tally's fabulac with `purpose: transconception` and `source.obtained: own`, nothing else | `tally.0-kept.fabulac.cosm` |
| 1 | `ground-the-fabulac` (`2026-11-22-1200-a901`), rules: 56 reliances and an assumption | `tally.1-grounded.fabulac.cosm` |
| - | `hand-out-the-cases` (`…-a902`), rules: the cases file again, its rulings derived (`outputs/cases.md`) | |
| 2 | `raise-the-questions` (`…-a903`): who rules, the lane, five batched ruling questions over 78 items | `tally.2-asked.fabulac.cosm` |
| - | the first sitting, the owner's (2026-11-22) | `tally.2-asked.fabulac.answers-2026-11-22-1230.cosm` |
| 3 | `settle-the-answers` (`…-a904`) | `tally.3-settled.fabulac.cosm` |
| 4 | `raise-the-questions` (`…-a905`): the transconceiver's five statements | `tally.4-asked-again.fabulac.cosm` |
| - | the second sitting, the owner's (2026-11-22) | `tally.4-asked-again.fabulac.answers-2026-11-22-1250.cosm` |
| 5 | `settle-the-answers` (`…-a906`) | `tally.5-ruled.fabulac.cosm` |
| 6 | `weigh-a-target` in go (`…-a907`): feasible-with, the option reader a gap | `tally.6-weighed-go.fabulac.cosm` |
| 7 | `weigh-a-target` in rust (`…-a908`): feasible-with, whole numbers without limit and the option reader | `tally.7-weighed.fabulac.cosm` |
| 8 | the maker: each spike's level read from its verdict (`tc.spike_from_verdict`) | `tally.fabulac.cosm` |
| - | `entail-in-a-language` in go (`…-a909`) and in rust (`…-a910`): a layout, then the code, apart | |
| - | the maker: `tc.land_in_language` for each | `../landed/` |

## Recorded, simulated, never claimed

- **Recorded as it ran**: every rule (ground, the cases, the questions, settling, landing, the lint, the gates).
- **The sittings are the owner's.** Simulated in 0.8. Ruled by the owner on 2026-11-22, by questionnaire:
  "Confirm all". Every ruling question is answered "as proposed" (`kept`, for an item never ruled). The lane is
  `open` (tally is MIT). Who rules: "the owner, as transconceiver" (`R:maker/the-owner-as-transconceiver`). The five
  statements are read from tally's own files, and the programs are "tally, in Go, in Rust and in Python, the round
  trip". Each answers volume's session names the owner. tally's own open questions of 2026-11-05 are left open.
- **The model is a recorded fake** (`engine: model:scripted`): the weighings (2 on every point a model answers, a row
  `written` for what no ground entry answers), the layouts (one file for every interface) and the cshorts' files
  (empty stubs, each saying it was never built). No model was asked anything.
- **The spikes are simulated.** There is no Go or Rust build of tally and no spike of it. `inputs/spikes/*.json` are
  verdicts written, not judged, each with `simulated` saying so and no finding; they let the path reach
  `target-confirmed`. Stage 7 records the gates before them (level 0: target-confirmed does not hold).
- **No evidence is claimed for Go or Rust.** Each cshort's entry says `evidence: []`: not judged. Nothing was built
  or run in either. Gate 2 holds on the judged stage only because the simulated spikes let `target-confirmed` hold.
  The trial of 2026-11-05 judged a TypeScript and a Swift tally, never Go or Rust.

## The round trip (0.9)

tally was recorded outside enough, and two Python rebuilds of it were judged. All of it was done in the sandbox by an
agent (lane T1, 2026-11-22; `outside/README.md` says how). Each rebuild was written blind by a fresh agent, from
one fabulac file alone. The maker reads `outside/` and writes three more stages after `tally.fabulac.cosm`, never
over it:

| # | made by | stage file (in `inputs/`) |
|---|---|---|
| 9 | the maker: the fabulac's words on `undoes` fixed (the owner: "The fabulac slipped: fix it"), each item saying so in `provenance.fixed` | `tally.9-fixed.fabulac.cosm` |
| 10 | the maker: the round trip's target (`N:target/python`, not weighed), its `shorts` entry, the 53 recorded cases as outside `P:case` items (`trial-a1` …), and the owner's ruling of B7 (the help screens' words: `free`) | `tally.10-recorded.fabulac.cosm` |
| 11 | the maker: the second round trip's verdict read into its evidence (`tc.fold_verdict`) | `tally.11-judged.fabulac.cosm` |

The first rebuild was made from `tally.fabulac.cosm`. It agreed on 184 of 189 steps. It differed on B7's help words
and on E1's `undoes` with blank lines, where the fabulac's words were wrong. It is kept in `outside/first-round-trip/`
and is not gathered. The second rebuild was made from stage 9 and judged with the owner's ruling of B7. It agrees on
185 of 185 counted steps and passes, with B7's four steps shown as ruled differences. Its evidence stands at level 3,
and gate 1 says "ready to keep" on stage 11, with all nine checks holding. `tests/test_transconception_fixture.py`
holds that.

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
