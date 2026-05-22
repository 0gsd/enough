---
name: analyzer
description: "Three-mode analytical toolkit for documents, books, web pages, and decisions. SUMMARIZE produces an even-handed one-page digest of any text (author motivation, intended audience, tone, key quotes). PROOFREAD makes light spelling/typo corrections on full-length documents (including entire books, chapter by chapter), driven by the Harper grammar checker (local, offline, rule-named findings), and produces a separate proof report with suggestions and repeated-phrase findings. DECIDE picks three archetypal personas from a built-in roster and runs a transcripted debate over a question, complex decision, or 'what should I do next' — returning a recommendation plus the full debate. Use for 'analyze this', 'summarize this', 'one-pager', 'tl;dr but smart', 'read this for me', 'proofread this', 'copy-edit this book', 'fix typos in', 'spot repetition', 'help me decide', 'pros and cons', 'what should I do about', 'three perspectives on', 'debate this'. Works with .txt, .md, .docx, .pdf, .epub, .html, pasted text, web pages, and free-form questions."
---

# analyzer

A lightweight, three-mode analytical workbench for text and decisions. Designed
to run comfortably on 16 GB machines — the dispatch lives here, the heavy
guidance lives in `references/` and is loaded only when a mode fires.

---

## Modes

| Mode        | What it does                                                                                                                  | Reference to load                |
|-------------|-------------------------------------------------------------------------------------------------------------------------------|----------------------------------|
| `summarize` | One-page even-handed digest of any text — author motivation, biases, intended audience, tone/lexicon, the point, key quotes.  | `references/summarize.md`        |
| `proofread` | Full-document copy-editing pass (typos/spelling) driven by Harper (`brew install harper`), with a separate proof report covering suggestions and repeated-phrase notes. | `references/proofread.md`        |
| `decide`    | Three archetypes from the roster below debate the user's question; output is a recommendation plus the full debate.           | `references/decide.md`           |

---

## How to dispatch

1. Pick the mode that matches the request:
   - **Text in, "what is this saying / give me a summary / break this down" → `summarize`.**
   - **Text in, "proofread / copy-edit / fix typos / clean this up" → `proofread`.**
   - **Question or dilemma in, "help me decide / debate this / pros and cons / what should I do" → `decide`.**
2. Read the matching `references/*.md` file completely. Do not improvise the
   mode from the SKILL.md alone — the reference contains the workflow, the
   output template, calibration notes, and edge cases.
3. Follow that reference end to end.

If the user request is ambiguous (e.g. they hand you a draft and say "look at
this"), ask one clarifying question: *"Do you want a summary, a proofread, or
a decision/debate on something in the text?"* Don't guess.

---

## Persona roster

These ten archetypes are shared across modes. `decide` picks three of them per
request (whichever three are most relevant to the question). `proofread` and
`summarize` may invoke individual personas when forming suggestions or
characterizing a text's likely reader.

Each persona is described in **one line** here. The reference files quote and
expand them as needed; do not re-describe them inline elsewhere.

1. **The Editor** — pragmatic; cares about clarity, structure, and whether
   each sentence is earning its place.
2. **The Skeptic** — interrogates premises; asks what is being assumed,
   what is missing, and what the text is quietly hoping you won't notice.
3. **The Target Reader** — stands in for the audience the text or decision
   is actually aimed at; reacts the way that reader would, biases and all.
4. **The Outsider** — knows nothing about the topic; tests whether the
   text or argument lands cold, without the usual context to lean on.
5. **The Historian** — knows the genre, the form, the precedents; spots
   clichés, missed conventions, and unacknowledged predecessors.
6. **The Contrarian** — argues the opposite position; takes seriously the
   case the text or decision is choosing not to make.
7. **The Pragmatist** — asks "so what" and "what would actually change";
   strips away anything that doesn't affect a concrete next action.
8. **The Stylist** — focuses on voice, rhythm, sentence music, word
   choice; flags pleasure and friction at the line level.
9. **The Synthesizer** — finds connections to adjacent domains, useful
   analogies, broader patterns the text or decision sits inside.
10. **The Insider** — domain expert; checks for technical accuracy and
    fairness within the field; spots the kind of error only a specialist
    would catch.

When `decide` selects three, prefer combinations that will actually
disagree. *Skeptic + Editor + Stylist* tend to converge; *Skeptic +
Contrarian + Pragmatist* tend to argue productively.

---

## Output

All artifacts from analyzer go to:

    rness/io/output/analyzer/

Mirror any subfolder the user named (e.g. if they asked you to analyze a
manuscript in `rness/io/input/manuscripts/foo/`, output to
`rness/io/output/analyzer/manuscripts/foo/`).

Filename conventions:

- `summarize` → `<source-slug>-summary.md`
- `proofread` → `<source-slug>-proof-report.md` (separate from any corrected
  manuscript copy; see `references/proofread.md` for the corrected-copy
  filename rule)
- `decide`    → `<question-slug>-decision.md`

If `rness/io/output/analyzer/` does not exist, create it.

---

## Boundaries

- **No scoring.** Analyzer does not assign numerical quality, manipulation,
  or "evil" scores. If the user wants a verdict, give them a clear
  recommendation in prose. Numbers pretending to be analysis are not honest.
- **Even-handed by default.** Summaries describe what a text is doing without
  approving or condemning it. Decisions present the strongest version of each
  position before recommending. The user is the judge.
- **Read everything you claim to have read.** For long inputs, take the
  chunking strategy in the relevant reference seriously. Don't fake breadth.
- **One mode per invocation.** If the user wants two modes on the same text
  (e.g. summarize *and* proofread a manuscript), run them sequentially and
  produce two separate output files.

---

*Three lenses. One workbench. The user decides.*

---
enough-tooltip-text: "use analyzer to summarize a document or webpage, proofread any text including full length works, or help you decide between possible options."
