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

The orchard text and its twin are copies of `../cosm/emf/notes.md` and `notes.md.cosm`; inside the package the twin's
`source.path` and its spans say `text.md`, as a package's fabula must.
