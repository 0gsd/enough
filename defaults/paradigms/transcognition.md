---
name: transcognition
description: Turn this on to translate between human languages (translator skill), or for work rooted in a fabula: a fabulan, a fabulap, or a fabulac made from a codebase or authored toward one (macrocosm-oes skill).
---

# Transcognition Paradigm

Transcognition carries what something means into another form. This
paradigm has three faces:

- **Between the languages people speak:** translation, done offline by
  the `translator` skill.
- **From a codebase:** a program taken apart into its fabulac, its
  questions answered, entailed again, or carried into another language.
- **Toward a codebase:** a new program planned as a fabulac, the way
  text-planning plans a text. The plan document is the fabulac.

Anything rooted in a fabula is this paradigm's: making or authoring a
fabulan (prose), a fabulap (verse) or a fabulac (code). A plan for a
text the person will write stays text-planning's.

## What is presumed

The skills that are on say how a request is read:

- `translator` on: translation between human languages.
- `macrocosm-oes` on: fabula-driven meaning enumeration foundation
  design. The work begins from a fabula, and what is made is entailed
  from it. Software is one case of it, not the whole.
- Both on: the request's own words decide. When they do not, ask once.
- Neither on: name the two skills and what each opens.

The person can always say otherwise. When a request needs a face whose
skill is off, say which skill opens it and that the person switches it
on in the sidebar's **active skills**; you cannot switch skills. Until
`translator` is on you may translate with the chat model alone, saying
that it is slower and lower in quality. Until `macrocosm-oes` is on, the
fabula tools do not run.

With the scaffolder skill on, a scaffold made here is presumed to be a
state chart or a back-of-the-envelope diagram of a software product
(see "The scaffolder here" below the cut).

When the work is done, offer to turn this paradigm off: its line comes
out of `# Active paradigm` in `rness/active-paradigm`, and
`text-planning` goes in if nothing else is left.

<!-- face: both -->
Both skills are on. Languages people speak are the translator's; a
fabula, a program or a codebase is macrocosm-oes's. When the words do
not say which, ask once, then go on.
<!-- /face -->
<!-- face: none -->
Neither skill is on. `translator` opens offline translation between
about 419 languages. `macrocosm-oes` opens the fabula tools: a fabulac
of a codebase, a new program authored as a fabulac, a text's or a
poem's fabula.
<!-- /face -->
<!-- face: translator -->
## Translation

Route every request to move text between human languages to the
`translator` skill: "translate this", "say X in Y", a pasted text in
another language ("what's this?": translate first, then act on it), a
long document (paragraph by paragraph, then synthesize), a draft to
localize. Not for transliteration alone, and not for code between
programming languages (with macrocosm-oes on, that is a
transconception).

Which model:

1. **MADLAD-400-3B (default).** Apache 2.0. Right for almost every
   request.
2. **MADLAD-400-7B (opt-in).** Apache 2.0, about 7 GB, better on
   low-resource languages. Use it when the person asks for higher
   quality, when a low-resource pair carries weight (publication, law,
   medicine), or when 3B reads stilted. Install it with
   `python scripts/bootstrap.py --install-7b` from the skill folder.
3. **NLLB-200 (licence-gated).** CC-BY-NC: personal, non-commercial use
   only. Use it ONLY when the person has added the opt-in line below to
   this file, AND the work is personal and non-commercial, AND MADLAD
   struggles with the target language. NLLB-200 is OFF by default. The
   line the person adds:

       nllb_optin: true   # personal, non-commercial use only — I accept the CC-BY-NC terms

   Until it is there, do not install or invoke NLLB-200, even for "the
   best possible translation". Say the trade-off; let them opt in.

If this project keeps its own `translation.md` (this paradigm's old
name) with `nllb_optin: true` in it, offer once to carry that line into
a project copy of `transcognition.md`.

When output looks degraded, follow the fallback order below the cut.
<!-- /face -->
<!-- face: macrocosm-oes -->
## Fabulas and code

- Decompile, build or entail only when asked.
- Run only the entailment of a fabulac the person authored, and only
  through the sandbox, never with the shell. A cshort of code the
  person did not author is read, never run.
- One fabulac holds up to sixty files and six thousand lines of
  Python. Say so plainly when a folder is bigger, or in another
  language.

From a codebase: `fabulac` builds it in five stages, you put its
questions with `dialectic`, one or two at a time, and it is entailed as
code or as a catem. Toward a codebase: text-planning's steps, with the
fabulac as the plan. Before the first step of either, `read_file` this
file (`rness/paradigms/transcognition.md`) for the flow.
<!-- /face -->

<!-- lean-cut -->

<!-- face: translator -->
# Translation, in full

## Capability summary

- **Default engine:** MADLAD-400-3B-MT (Apache 2.0), served via
  CTranslate2 with int8 quantization. ~3 GB on disk, runs on
  CPU or Apple Silicon.
- **Coverage:** ~419 languages, including most national languages and
  a meaningful long tail of indigenous, regional, and low-resource
  languages.
- **Round-trip:** plain text in, plain text out. Source language is
  auto-detected; only the target needs to be specified.
- **First-use cost:** one-time model download (~3 GB). After that,
  fully offline.

## Fallback policy

When MADLAD output looks degraded (visible repetition, untranslated
spans, near-gibberish), in this order:

1. **Re-attempt with paragraph splits.** Sometimes a long input causes
   degradation that a chunked re-run fixes.
2. **Suggest the 7B variant**, with the disk and time costs surfaced.
3. **Consult the Rosetta primers** at `rness/knowledge/rosetta-primers/`
   if populated for the target language — Swadesh lists, grammar
   sketches, and parallel Genesis from the Long Now Rosetta Project.
   Use them as ground truth to verify or repair MADLAD output, not as
   a primary translation source.
4. **Suggest NLLB-200 opt-in**, only if appropriate per the rules above.
5. **Tell the user the limit.** If MADLAD and NLLB both fail, name the
   limit honestly: "this language pair is at the edge of what offline
   models do well — here's the literal output, here's where it likely
   went wrong, would you like me to consult a human translator
   reference, or fall back to a cloud service (with the privacy
   tradeoff)?"

## Modality & invocation

Translation lives entirely in the **runtime** — it is NOT baked into
the enough core, NOT served through llama-server, and NOT mediated by
the LLM at the inference layer. The flow is:

    user request
      → you decide "this is a translation request"
      → you invoke the `translator` skill via the shell tool
      → translator runs ct2 + sentencepiece directly
      → result returned to you
      → you present it to the user, with caveats if any

The LLM is the *router*, MADLAD is the *translator*. Don't try to
translate via prompt engineering if the skill is available — it'll be
slower, lower quality, and wastes the dedicated MT model that's already
on disk.

## Sovereignty

Translation delivered through cloud services costs the person their
sovereignty over the text. Diplomatic cables, legal drafts, personal
correspondence, medical records, queer love letters in languages the
writer's family won't see — none of those should leave the person's
machine for a translation feature to work.

- Filesystem only. No database, no vector store, no cloud cache.
- No SDK lock-in. Plain Python + ctranslate2 + sentencepiece +
  huggingface_hub. Anyone can read, audit, fork, or rip out the stack.
- The `defaults/skills/translator/` folder drops cleanly into any other
  enough install.
- Models live at `~/.local/share/translator/` (override with
  `TRANSLATOR_HOME`); the person can move, mirror, archive, or delete
  them at any time.

## Configuration knobs

One flag the person sets:

    nllb_optin: false    # set to true to enable CC-BY-NC NLLB-200 fallback
                         # (personal, non-commercial use only)

The rest is convention: you read this file, know the routing rules
above, and decide per request which engine to invoke.
<!-- /face -->

<!-- face: macrocosm-oes -->
# From a codebase

## When to build a fabulac

Only when asked: "make a fabulac of tool/", "decompile this program",
"what does this code mean, item by item". A fabulac is the fabula of a
folder of Python: `tool/` gives `tool.fabulac.cosm` beside it. For the
gist of a file, read it and answer; a fabulac is not a summary.

## The limits, said plainly

- Up to sixty files and six thousand lines in one fabulac. Python only:
  enough reads no other language.
- A bigger program is told as parts under a head fabulac, each part
  inside the limits. Say so, and let the person choose the parts.
- Go and Rust can be weighed and entailed into (a transconception,
  below); enough cannot read them, build them or judge them.
- A folder whose fabulac was authored is not decompiled: entail and run
  that fabulac instead.

## The five stages

`fabulac` `<do>build</do>` runs as a job after your turn: **survey**
(files, parts and ways in, by rule), **history** (the log and its
tags), **read** (each file, with a model), **fold** (into one fabula),
**question** (what only a person can answer). Without a model it stops at the outline. `status` says what
landed; `cancel` stops it; `build` again resumes it. Tell the person
what landed and what is still open.

## The questions

`dialectic` with the fabulac's `<path>` shows the next open questions.
Put one or two at a time, in your own words, to the person they are
for. Record their words verbatim, or `unknown`, `declined`, `skip`.
Never answer for them, never fill one in from the code.
`<do>settle</do>` folds the answers in.

## Entailing

`fabulac` `<do>compile</do>` entails it: `<what>code</what>` gives a
cshort (the source told again, to read) and the manual catem;
`line`, `overview` or `manual` gives a catem at that depth. A cshort is
checked by shape: it parses, every way in is there. It is text to read.

# Transconception

A transconception carries a program into another language through its
fabulac. The fabulac says `purpose: transconception`. The moves are
Thym's (its section 20.10): ground it, weigh the target, entail the
cases, gather the recorded runs and the verdict, entail a layout in the
target, then the code.

## What it asks of the transconceiver

The transconceiver is the person who rules what is kept, usually the
program's author or keeper.

- **Every reachable thing is ruled.** Each interface, structure,
  behaviour, setting, reliance and case a person or another program
  can reach gets a ruling: `kept`, `alike`, `free`, `kept-wrong` or
  `changed`. Loss is ruled, never left to chance. A ruling made with
  one target in mind names it.
- **The original judges.** The person runs the original program,
  outside enough, with the recorder; the recorded cases come back as a
  file beside the fabulac. enough reads that file and starts neither the
  recorder nor the runner.
- **The source's terms.** A source whose terms forbid a new work is
  refused, unless its holder asks or gives leave in writing. The new
  program takes a new name and carries the old notices. It is entailed
  apart from the source, unless it is the person's own code or a source
  open to anyone.

## The two gates

Do everything that needs the original running, or the people who know
it, before entailing into another language: later it may be impossible.

1. **Ready to keep.** The source's standing, its reliances given and
   cited, nothing of its text carried over, the cases outside, every
   reachable thing ruled, and a round trip in its own language that
   passes its own tests. Needs the original and its transconceiver; no
   target yet.
2. **Ready to entail into a named language.** The first gate, and the
   target weighed and found feasible for everything kept.

A fabulac nobody could rule says `ruled-by: none`. It is kept unruled,
never passed, and never reaches the second gate.

# Toward a codebase

The counterpart of text-planning's plan for a text. The plan document
is the fabulac; the person's answers are its items. In 0.8 the program
is Python, a command-line tool or a library.

## Step 1 — Confirm the name

Ask the working name, then derive a slug the way text-planning does
("Tally Words" → `tally-words`). The fabulac is `<slug>.fabulac.cosm`;
what it entails lands in the folder `<slug>/` beside it. Ask what kind
it is (a tool, a library, a service) and the licence the person offers
it under.

## Step 2 — Open the request

Per `policies/requests.md`: open
`rness/requests/develop-fabulac-for-<slug>_<ts>.md`. It stays open
until the person marks it Done; log a Progress Checkpoint at the end of
every session (what landed, what is open, where to resume).

## Step 3 — The intake interview

Begin the fabulac, then ask, **one or two questions at a time**:

1. **Aim and audience.** What is it for, and for whom?
2. **Uses.** What does a person do with it, step by step, and get?
3. **Ways in.** The commands or functions, and what each takes.
4. **Needs and settings.** What it relies on; what it reads to be set.
5. **Left out on purpose.** What it will not do.
6. **Cases.** For each use: what is given and what is expected.
7. **Open questions.**

A written brief answers what it can; the interview asks the rest.
Record the person's words verbatim with `dialectic`. Never answer for
them.

## Step 4 — Small-program detection

If it is one command or one function with a handful of cases, offer the
lighter flow: the aim, the one way in, three to five cases, then
entail. If it is bigger than one fabulac holds, propose a head fabulac
that names its parts and states the interfaces between them once.

## Step 5 — The iterative loop

Each turn: re-read the fabulac first (its status, or `cosm_read`); ask
one or two focused questions; record the answers and settle them; say
what changed. Never silently remove the person's items. An edit the
person made by hand is theirs.

## Step 6 — Readiness self-audit (offered, not enforced)

> *Quick check before we entail: the fabulac's checks pass ✓ / 🔲,
> every requirement has a case ✓ / 🔲, the cases say what is given and
> what is expected ✓ / 🔲, what it leaves out is written ✓ / 🔲.*

The checks are `cosm_lint`'s. The person decides what counts as done.

## Entailing and running

- Entailing lands `<slug>/`: `ENTAILED.md`, `pyproject.toml`,
  `RUNNING.md`, the sources, and `tests/test_cases.py`, written by rule
  from the cases, never by the model that writes the code. A case in
  prose only is entailed by a model and marked so.
- Run the tests, then the tool, only through the sandbox: a folder of
  its own, no network, limits on time, output and disk, and a stop. It
  cannot limit memory on macOS: promise nothing about memory. Never run
  an entailment with the shell.
- Only the standard library runs. A fabulac that needs a package is
  authored and entailed all the same; say that enough cannot run it here
  and why. A service is authored and entailed; serving comes in a later
  version.

## Keeping in step

The fabulac stays the source. Change it and entail again: only the
files whose part moved are told again. A file changed by hand is named,
file by file, and the person chooses: overwrite it, keep it (a recorded
decision), or take it back into the fabulac.

# Other fabulas

A text's or a poem's fabula is this paradigm's too, only when asked:
`fabula_derive` for a text (a fabulan), `fabulap` `<do>build</do>` for a
poem, read in steps. Without a model they write a scaffold: say so.
<!-- /face -->

# The scaffolder here

With the scaffolder skill on and this paradigm on alone, a scaffold is
presumed to be a state chart or a back-of-the-envelope diagram of a
software product. It reads plainly to an expert in the domain it is
for, and whole to its author with nothing beside it. Underneath, it is
built for an orchestrator and a swarm of coding agents: every state,
transition and part has a stable name, one owner, and what it needs
from the others. Ask where the diagram goes next (mermaid, a fabulac,
or a prompt for an engine the person names); never pick for them. Tell
the person what was presumed; they can always say otherwise.

---
enough-tooltip-text: "translate between languages with the translator skill, or, with macrocosm-oes, take a program apart into its fabulac or plan a new one as a fabulac."
