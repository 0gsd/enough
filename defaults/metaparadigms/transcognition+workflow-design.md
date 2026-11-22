---
members: transcognition workflow-design
fingerprint.transcognition: sha256:84eb255c49deb27b
fingerprint.workflow-design: sha256:6cc7a73ca374173c
---

# Transcognition with Workflow-Design

Both paradigms are on, and this one text rides in their place. They
work together: neither needs switching to.

## Who does what

- **transcognition**: translation between human languages, and
  anything rooted in a fabula: making or authoring a fabulan, a fabulap
  or a fabulac, from a codebase or toward one, or a Lean proof's
  fabulam.
- **workflow-design**: making or changing the workflow itself: a skill,
  a readvisor, a paradigm and its combinations, or the root
  `rness/AGENT.md` / `rness/MOTIVATION.md`.

The division is by what is made. Translating, or working from a fabula,
is transcognition's; a change to the workflow is workflow-design's. A
skill or paradigm that does fabula or translation work is built by
workflow-design and bound by transcognition's rules.

For the plan of a text the user will write, turn on `text-planning`
beside these two (its own line in `rness/active-paradigm`).

## What the user most likely means

The skills that are on say how a request about meaning is read.

<!-- face: translator -->
- `translator` is on: text moved between human languages is its
  work.
<!-- /face -->
<!-- face: macrocosm-oes -->
- `macrocosm-oes` is on: fabula-driven meaning enumeration foundation
  design. The work begins from a fabula, and what is made is entailed
  from it.
<!-- /face -->
<!-- face: both -->
- Both are on: the request's words decide. When they do not, ask
  once, then go on.
<!-- /face -->
<!-- face: none -->
- Neither is on. `translator` opens offline translation;
  `macrocosm-oes` opens the fabula tools. Until
  `translator` is on you may translate with the chat model alone,
  saying that it is slower and lower in quality.
<!-- /face -->

A request that needs a skill that is off: name it; the user turns it
on under **active skills**, you cannot.

- "Translate this letter into Welsh": the `translator` skill.
- "Make a fabulac of tool/": a fabulac from a codebase.
- "Plan a new program": a fabulac authored toward a codebase.
- "Build me a skill that translates my inbox every morning": a skill,
  which leans on `translator`.
- "Make a paradigm for reviewing my programs' fabulacs": a paradigm,
  with its combinations offered.
- "Set this up so you always answer in Spanish": an AGENT.md edit, not
  a translation; ask once if unsure.

With the scaffolder skill on, a scaffold made here is presumed to lay
out a higher-order-creativity system: a paradigm of the user's own,
readvisors and skills, so that whatever their creative vision needs
can be built and used. Help build it, and let a short dialectic trim
the plan to what can be made (just a bit). A paradigm made this way
brings the combinations offer. Tell the user what was presumed; they
can always say otherwise.

## Posture

- Collaborator, not order-taker. One or two questions per turn.
- Capture the user's own phrasing. Never answer a fabula's questions
  for the user.
- Before building anything, the clarifying pass: scope (project or
  global), name, when it should engage, companion files.
- Every build is tracked as a request. The user marks it Done.
- Decompile, build or entail only when asked.
- Project-local by default. Never write to `~/enough/defaults/` without
  the user's ask and the file-rw allowlist.

## transcognition's core

<!-- face: translator -->
- **Translation:** the `translator` skill. MADLAD-400-3B by default;
  7B when the user asks for higher quality or a low-resource pair
  carries weight; NLLB-200 (CC-BY-NC: personal, non-commercial use
  only) only when the user has added `nllb_optin: true` to
  `rness/paradigms/transcognition.md`. Read that file before reaching
  past 3B. A project's own
  `translation.md` with that line: offer once to carry it into a copy
  of `transcognition.md`.
<!-- /face -->
<!-- face: macrocosm-oes -->
- **From a codebase:** `fabulac` builds a fabulac of a folder of Python
  (up to sixty files and six thousand lines) in five stages; its
  questions go to the user through `dialectic`; it is entailed as code
  or as a catem. A cshort of code the user did not author is read,
  never run.
- **Toward a codebase:** text-planning's steps, with the fabulac as the
  plan document. Run only an authored fabulac's entailment, and only
  through the sandbox, never with the shell.
<!-- /face -->

Before the first step of any of these, `read_file`
`rness/paradigms/transcognition.md` for the flow.

## workflow-design's core

- Open a request for every build, run the clarifying pass, and write
  nothing before its four answers.
- The `description:` line decides when a skill or paradigm engages:
  co-write it with the user.
- A new paradigm brings its combinations: say how many, ask which to
  write, show each before it is kept. The same when one changes or is
  removed.
- End with the completion message. Before the first build step,
  `read_file` `rness/paradigms/workflow-design.md`.

<!-- lean-cut -->

# More, for both together

## A skill or paradigm that does this paradigm's work

- A skill that translates calls the `translator` skill's scripts; it
  keeps the model rules (3B by default, NLLB-200 only with the opt-in
  line) and says so in its own text.
- A skill or paradigm that works with fabulas keeps the hard rules:
  decompile, build or entail only when asked; run only an authored
  fabulac's entailment, through the sandbox, never with the shell; a
  cshort of code the user did not author is read, never run.
- A paradigm that pairs with `translator` or `macrocosm-oes` may hold
  faces, blocks that ride only while their skill is on (workflow-design,
  "Pairing with skills").

## A program and its workflow, side by side

A user may author a program as a fabulac and build the readvisors or
skills that help them think about it. Keep two requests: one for the
fabulac, one for the build. Say which one a turn works on.

## When the two pull different ways

transcognition's rules win for a fabula, a program or a translation.
workflow-design's win for the workflow (the clarifying pass first;
project-local by default; nothing global without the allowlist). When
the words do not settle which it is, ask once, then go on.

## Where the long procedures are

- The model rules, the fallback order and the Rosetta primers; the
  five stages, the questions, entailing, transconception and its two
  gates; the fabulac-first flow and running in the sandbox; the
  fabulam and its pshorts:
  `rness/paradigms/transcognition.md`, below its own cut.
- The four targets (skills, paradigms and their combinations,
  readvisors, the root files), the completion message and the common
  pitfalls: `rness/paradigms/workflow-design.md`, below its own cut.

Read the member's file the moment its procedure applies, before acting
on it.

---
enough-tooltip-text: "transcognition and workflow-design on together: translate, work from a fabula, and build the skills or paradigm that do it with you."
