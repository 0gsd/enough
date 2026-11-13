# The Thym conformance suite

The folder `docs/THYM.md` section 20.3 describes, portable as a folder together with `../cosm/` (MacroCOSM's own
corpus, which holds the public sample Holotype `holotypes/meadow` that `open-house` runs on).

| path | what |
|---|---|
| `programs/<name>.thym` | the programs: the three of the specification first (`publish-story`, `read-my-way`, `open-house`) |
| `inputs/` | what they run on: `notes.md` with its EMF twin; the same text as a package, `orchard-notes.thym/`; a declared morph and a declared context; `little-tool/`, a folder of seven small files (one of them binary, `docs/logo.png`) for the `thym 1` folder programs, whose tree digest is `dfef659d…48ea` (MacroCOSM OES 18.4.1) |
| `expected/<name>/items.cosm` | the enumeration of each program; its `front` and `body` fields compile back to `programs/<name>.thym` byte for byte |
| `expected/<name>/plan.cosm` | the plan; compared without run ids, timestamps and prompt token counts; an input's sha256 is its bytes' for a file and its catalog file's for a volume or a package |
| `expected/<name>/outputs/` | the outputs of deterministic runs, byte for byte (a folder output is a folder here, `outputs/<name>/`, as it lands) (recorded from the first conforming run, then frozen; `conform` runs them with the clock pinned to 2026-11-01T12:00:00Z) |
| `replay/<name>/<run-id>/` | recorded runs of model-backed programs: plan, trace, candidates; re-run to the recorded outputs. Two of `publish-story` on Qwen3.8-27B, both with their engine calls recorded as `candidates/<node>-e<k>.1.cosm`, so each replays with no dictionary and no engine: `2026-11-01-2148-35b5` (checkpoint A's run, re-recorded on 2026-11-05 under its own id: recorded before engine calls were, it replayed with live engines and stopped matching when the grammar version Canon stamps moved; the id is kept because other fixtures and the UI check copy its package) and `2026-11-02-0843-ff92` (wave 2; its FEED answers re-recorded on 2026-11-05 with the engine's six fields, every other record as it was). Re-record, never hand-edit |
| `bad/<slug>.thym` | programs that must be refused; the first line says `-- refused: <stage> <check> line <n>` |

**Passing.** A compiler conforms when every program in `programs/` compiles, enumerates to its `expected/items.cosm`,
compiles back byte for byte, plans to its `expected/plan.cosm`, and every `bad/` program is refused at the stage,
check and line its first line names. A runtime conforms when every deterministic program's outputs match
`expected/outputs/` and every `replay/` run re-runs to its recorded outputs. Every block marked `thym` in
`docs/THYM.md` is also a program of the suite (`tests/test_thym_spec.py` collects them).

**Inputs by program.**

| program | takes |
|---|---|
| `publish-story` | `story`: `inputs/notes.md` |
| `read-my-way` | `p`: `inputs/orchard-notes.thym/`; `mine`: `inputs/plain-letter.morph.cosm`; `now`: `inputs/on-the-train.context.cosm` |
| `open-house` | `h`: `../cosm/holotypes/meadow` |
| `nested-in-loop` | `h`: `../cosm/holotypes/meadow` |
| `keep-the-python` | `repo`: `inputs/little-tool/` (a folder; its plan row also records `files` and `bytes`) |
| `split-a-folder` | `repo`: `inputs/little-tool/` |
| `collect-the-offers` | `h`: `../cosm/holotypes/meadow` (a loop that collects: one node, `move: for`, `gives`, `members`) |
| `loop-as-a-unit` | `h`: `../cosm/holotypes/meadow` (a `thym 1` loop of several statements: one node, its body run member by member) |
| `contract-holds` | `t`: `inputs/notes.md` (a contract block, kept by a move and by the program) |
| `bounded-recursion` | `t`: `inputs/notes.md` (a move that calls itself under `depth: 2`) |
| `drop-the-todos` | `draft`: `inputs/draft.md` (the text's deterministic editor, section 21.5: every line that says TODO dropped by one `edit`) |
| `tighten` | `s`: `inputs/long-lines.md` (the editor program people copy, section 21.5, byte for byte `defaults/thym/tighten.thym`; it asks, so it conforms by replay: `replay/tighten/2026-11-05-1956-ae6e/`, recorded with a scripted coprocessor whose first answer for line 3 runs past thirty words and fails `length`, so the loop node asks again with the failure in `repair.failed`, and whose answers for lines 3 and 6 pass; its words are the input's own, so `nothing-added` needs no FEED and the replay passes with or without one) |
| `settle-the-answers` | `f`: `inputs/close.md.fabulan.cosm` (a copy of the fabula fixture `guides/close.md`'s twin, MacroCOSM OES 18.4.5 and 18.6.9: the questions its question run raised by rules, one answered in a first sitting and settled, the rest open); `said`: `inputs/close.md.fabulan.answers-2026-11-05-1200.cosm` (its answers volume, THYM 22.2: a second sitting answering the bank's audience question, which is about module N, so its answer is written as a new item). Byte for byte `defaults/thym/settle.thym`, the text's second run of the dialectic (22.4). `settle` asks only where an item must be read again, and nothing here must be, so its run asks nothing; but its plan counts `settle` as a node that asks, so it conforms by replay: `replay/settle-the-answers/2026-11-06-0035-c4b5/`, whose engine calls (`dialectic.thym_record`, `dialectic.thym_settle`) are recorded, so it replays with no dialectic engine and no model |
| `join-the-notes` | `notes`: `inputs/notes.md`, then `inputs/draft.md` (a list input, `list of short`, given member by member: its plan row records each member's path and sha256 under `members`, and the list's `sha256` over theirs in order; its loop node has `members: {at_most: 2}`; the run joins them in the order given and counts the words of each) |
| `survey-a-repo` | `repo`: `inputs/tiny-tool/` (a fabulac's outline by rules alone, THYM 20.6: its syntax read through the host's `syntax` engine and its file counts through `repo`, nothing run; its outputs cannot be frozen byte for byte, since the runtime writes the run's id into every item's `made`, so `conform` runs it as its recording, under the recorded run's id and clock, and compares its outputs with `replay/survey-a-repo/2026-11-06-0006-d8f4/outputs/` byte for byte (where the host's engines are there; elsewhere it conforms by its replay alone); that recording holds every engine call, `candidates/1-e<k>.1.cosm`, and replays with no engine and no folder) |

The editor's static refusals are `bad/lines-in-zero.thym` and `bad/words-of-a-string-in-zero.thym` (`compile version`:
a move only `thym 1` declares, and a signature only `thym 1`'s view of `words` has), and `bad/replace-a-short.thym`,
`bad/edit-with-strings.thym`, `bad/join-numbers.thym`, `bad/say-a-fabula.thym`, `bad/gather-a-text.thym`,
`bad/insert-without-place.thym` (`compile type`: `insert` takes exactly one of `before` and `after`). Its run refusals
(a change applied to another text, two changes to one line, a `reword` that fails every attempt) are cases of `tests/test_thym_edit.py`: the suite holds files, not runs that refuse.

A list input's static refusal is `bad/list-as-a-short.thym` (`compile type`: a list of shorts where `cut` takes one
short). Its plan and run refusals (one path for a list, a list for one path, an empty list, a member missing or
changed, named `xs[n]`) are cases of `tests/test_thym_lists.py`.

The dialectic's static refusals (THYM 22) are `bad/question-in-zero.thym` (`compile version`: a move only `thym 1` declares), and `bad/question-a-text.thym`, `bad/record-a-text.thym`, `bad/settle-a-text.thym` and `bad/settle-gives-a-volume.thym` (`compile type`). Its runs (questions by rules and with a model, an answers volume recorded, settling with a re-read, the two runs as a pair and their replays) are cases of `tests/test_thym_dialectic.py`.

`inputs/tiny-tool/` is a small Python program of the suite's own (a package of four modules with a command line, a
test file, a README, a change log, an MIT licence and a `pyproject.toml`), never run: `inputs/conftest.py` keeps pytest
from collecting its test. `tests/test_thym_code.py` builds its whole fabulac with `defaults/thym/decompile-python.thym`
and compiles it back with `compile-python.thym` under a scripted coprocessor, and makes a clone of it in a temporary
folder for the history. The fabulac's static refusals are `bad/entail-a-poem-as-code.thym` (`compile flavour`) and
`bad/cshort-as-a-short.thym` (`compile type`: `entail … as code` gives a folder). The second is written with `tell`,
`entail`'s earlier spelling (THYM 6.3), which the compiler reads as `entail` for good, so the suite holds one program
that still says it.

The orchard text and its twin are copies of `../cosm/emf/notes.md` and `notes.md.cosm`; inside the package the twin's
`source.path` and its spans say `text.md`, as a package's fabula must.
