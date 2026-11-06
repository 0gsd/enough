---
name: macrocosm-oes
description: Reads, checks and explains MacroCOSM `.cosm` files — Holotypes, Canon catalogs, product trees, fabulas, holographs — and, only when the user asks, decompiles a text into its fabula, writes its atem (the tightest fair, full, plain reduction of a text), puts a volume's questions to the user and records their answers, builds a fabulac of a folder of Python, or runs a Thym program. Use for "what is this .cosm file", "read this Holotype", "lint this .cosm", "decompile this text", "make an atem of this", "say it in one line", "what is a fabula", "what does this stance mean", "ask me the questions", "build a fabulac", "run publish-story on this", "what is Thym". Not for an ordinary summary in the user's own terms (answer that directly), not for editing a Holotype's content (that is Comprise's work), and not for writing new .cosm volumes by hand.
---

# macrocosm-oes

**MacroCOSM OES** is a shared grammar and its **core**: a domain written as
plain-text `.cosm` files (a restricted YAML subset). A **volume** is a
folder or one file whose **catalog** declares its format (`oes: fabula/1`);
its **items** have a stable `id` (`P:claim/apples-need-a-second-variety`), a
`type`, references by id, and one envelope: name, summary, status,
visibility, provenance. A value nobody has given yet is an **open
question**, `{pending: "the question"}`, never a guess.

## The formats enough reads

| Format | Declaration | A volume is |
|---|---|---|
| `cosm` | `cosm: 0.2` or `0.3` | a standalone product tree |
| `canon` | `oes: canon/1` | a catalog, `canon.cosm`, kept by enough |
| `fabula` | `oes: fabula/1` (old spelling `emf/1`) | a decompiled input: a text's twin, or a fabulac of code |
| `doc` | `oes: doc/1` | a document enumerated (the specs, the manual) |
| `thym` | `oes: thym/1` | a Thym program, morph, context, plan, trace or package |
| `comprise` | `oes: comprise/1` | a Holotype: one company, a folder with `holotype.cosm` |
| `ascribe` | `oes: ascribe/1` | a holograph: a self with no name, a folder with `holograph.cosm` |

The first five are the core's **built-ins**; `comprise` and `ascribe` are
the two **MiniCOSMs**. Any volume may carry module D, the **dialectic**.

## The fabula

To **decompile** is to take an input apart into its **fabula**: everything
found in it or derived from it — I inspiration, L terms (grounded in FEED),
E entities, K concepts, N intent, C construction, R production, P claims
(and readings or cases), T events, X atems. To **compile** is to tell a
fabula back as a **short** (markdown). Its **flavour**: `fabulan` (prose),
`fabulap` (verse), `fabulac` (code: its short is a **cshort**, source
rebuilt; its deep atem a **catem**). A text's **twin** sits beside it:
`notes.md.fabulan.cosm`. An old twin `notes.md.cosm` that says `oes: emf/1`
is still read and is replaced only when the text is decompiled again.
"EMF" is the fabula's retired name.

## The six stances

Every claim says how the text knows it:

- `axiom` — given, or true by definition; the text does not argue for it
- `observed` — seen, measured or done at first hand
- `deduced` — reasoned from the text's other claims
- `opinion` — a judgement or preference of the author's
- `assumed` — relied on without being stated as a premise
- `hearsay` — reported from someone else, who fills the claim's `source`

## The atem

An **atem** is the tightest fair, full, plain-English reduction of a text or
a passage, in four parts:

- **line** — one sentence of 15–25 words that says what the whole says:
  *fair* (the author would accept it), *full* (nothing the text depends on is
  missing), *plain* (everyday words). "The atem" in prose means the line.
- **focus** — what is happening: what the author directs attention to.
- **push** — what the author wants the reader to take away.
- **pull** — what the reader should actually take away, naming hidden
  assumptions and dependencies.

Where push and pull differ is what an atem shows best.

## When to make one

- **Decompile only when asked** ("decompile", "make a twin"), never on your
  own initiative. For the gist or a one-line summary, make an atem instead:
  `<text>` for a pasted passage, `<path>` to write a file's atem.
- `fabula_derive` takes `<flavour>` `fabulan` or `fabulap` (left out:
  enough suggests). Without a model both tools write a **scaffold**: say so,
  never present it as a reading.
- Without `<route>` the decompile or the atem runs on this machine's model,
  never the cloud; say `<route>cloud</route>` only when the person chose the
  cloud for this job.
- In a chat turn a model reads up to about 6,000 characters (longer gets the
  scaffold; the reader's decompile does a full pass); both refuse over about
  24,000. Shorts are compiled in the reader; you have no tool for them.

## Reading a Holotype

A Holotype describes one company: concerns of eight modules.

- **People are never in files.** Employees live only in Comprise's sealed
  database. Never infer or invent the people of a company.
- Report each open question with the item that holds it; never answer one
  with a guess. No twins or atems of a Holotype's files.
- Comprise's own rules show as "not run": that is not a failure.

## The dialectic

Questions a volume asks about what its source means, answered by a person.

- `dialectic` with a `<path>` shows the next one or two open questions.
  **Put one or two at a time**, in your own words, to the person they are
  for.
- Record the person's words **verbatim** with `<question>` and `<says>`, or
  `<state>` unknown (they don't know), declined, or skip. **Never answer for
  them**, never guess, never fill one in from the text.
- Answers wait in a sitting until `<do>settle</do>` folds them in (a job).
  `<do>raise</do>` asks the format's opening questions when there are none.
- A holograph: only its holder answers, and nothing that reads like
  personal data is kept.

## Fabulacs

A **fabulac** is the fabula of a small folder of pure Python (up to 60
files, 6,000 lines): `tool/` → `tool.fabulac.cosm`. Only when asked:

- `fabulac` `<do>build</do>` runs five stages as a job after your turn
  (without a model it stops at the outline). `status` says what landed;
  `cancel` stops it; `build` again resumes it.
- `<do>compile</do>` with `<what>` `code` (a cshort and the manual catem) or
  a catem's depth: `line`, `overview`, `manual`.
- Nothing read or told is ever run: a cshort is text to read.

## Thym programs

A **Thym program** is a `.thym` file: a recipe of moves over documents. It
is checked and planned before anything runs, and every run leaves a trace
that replays. Its first line is `thym 0` or `thym 1`; `thym 1` adds folders,
several outputs, editing moves, loops that collect (`keep`), contract blocks
a move `keeps`, recursion under a `depth:`, and the dialectic's `question`,
`record`, `settle`.

- `thym_check`: "ok" and the plan's line (with which model, how many
  calls), or the refusal with its line. Use it first.
- `thym_run`, only when asked: `<program>`, `<path>` the first input,
  others as `<inputs>` lines (`name=path`). It names the outputs and trace;
  the reader's "run with…" puts them beside the text.
- `thym_moves` lists the moves a program may use (`<version>` 1 or 0,
  `<move>` for one).
- Programs come from the project, then the Canon store, then enough's own
  (`open-house`, `tighten`, `decompile-prose`, `settle`, …).

**Models.** A step that asks a model runs on this machine unless the user
chose the cloud for that job: `<model>cloud` (with `<calls>`, a ceiling,
when the count is open) only then. A shut gate, agent-free mode or no model
refuses the plan; say what was refused and what would make it run.

## The tools, in order

Their tags are in the Tools section. With this skill off, this guide is one
`cosm_guide` call away, and `dialectic`, `fabulac` and the Thym tools do not
run.

1. `cosm_read` — the tree, or one item with `<item>`. Start here.
2. `cosm_lint` — the checks: a fabula's and a holograph's own, else the
   generic ones.
3. `fabula_derive` or `atem` — only on request.
4. `dialectic`, `fabulac` — only on request.
5. `thym_moves`, `thym_check`, then `thym_run` — runs only on request.

`doc_lookup` answers "what is X" from the specs and the manual. Writing into
the Canon store (`canon:` paths) needs the broker's canon tools on.

## More

The specifications, published at cosmoes.org and open in the app's docs
viewer: `docs/MACROCOSM_OES.md` (the fabula §18.4, the dialectic §18.6),
`docs/THYM.md`, `docs/ASCRIBE.md`, `docs/COMPRISE_OES.md`.

MacroCOSM OES © 2026 Graham Smith; see defaults/cosm/NOTICE.md

---
enough-tooltip-text: "use macrocosm-oes to read and check .cosm files — Holotypes, catalogs, fabulas — and, when you ask, to decompile a text, make its atem, answer a volume's questions, build a fabulac of Python, or run a Thym program."
