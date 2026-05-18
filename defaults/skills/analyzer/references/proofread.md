# analyzer — proofread mode

Proofread a document — possibly a full-length book — and produce two
deliverables:

1. **A corrected manuscript copy** with small mechanical fixes applied
   (typos, obvious misspellings, doubled words, missing/extra spaces,
   straightforward punctuation slips).
2. **A separate proof report** documenting every change made, plus
   substantive suggestions the user can choose to apply or ignore, plus
   pattern findings (repeated phrases, recycled metaphors, structural
   issues).

The user keeps full authority. You make only the safe mechanical fixes;
everything else is a suggestion in the report.

---

## The two-deliverable rule

| Deliverable | Contains | Filename |
|-------------|----------|----------|
| Corrected manuscript | Original text with only mechanical fixes applied. Same structure, same chapter breaks, same line breaks where possible. | `<source-slug>-corrected.<ext>` |
| Proof report | Every change made + suggestions + pattern findings. | `<source-slug>-proof-report.md` |

Both files go to `rness/io/output/analyzer/` (mirroring any subfolder the
user named). If the user only wants the report and not a corrected copy,
they will say so; default is both.

---

## What counts as "safe to fix silently"

Apply, but log every change in the report:

- Unambiguous typos and misspellings (`teh` → `the`, `recieve` → `receive`).
- Doubled words (`the the`, `and and`) where the duplication is clearly
  accidental.
- Missing or extra spaces around punctuation.
- Obvious punctuation slips (missing period at end of paragraph, stray
  comma inside a clearly closed phrase).
- Wrong-case proper nouns the document itself uses correctly elsewhere
  (e.g. fixing `paris` to `Paris` if every other instance is capitalized).
- Curly-vs-straight quote inconsistency, but **only** if the document is
  overwhelmingly one style and a few stragglers slipped through. If
  usage is mixed, leave it and note it as a suggestion.

**Do not silently change:**

- Word choice, even if you have a better word.
- Sentence structure or order.
- Author voice or rhythm, including unusual punctuation that appears
  intentional.
- Regional spellings (`colour`/`color`, `theatre`/`theater`) — pick the
  document's apparent dialect and only fix outliers if there is a clear
  majority; otherwise note as a suggestion.
- Style choices: serial commas, em-dash spacing, ellipsis style — match the
  document's prevailing convention; do not impose your own.
- Anything in dialogue, quoted material, or epigraphs. Errors in dialogue
  are often deliberate characterization.
- Anything in code blocks, URLs, filenames, or technical strings.

When in doubt, leave it alone and put it in the suggestion list.

---

## Chunking strategy

The document size determines the strategy. Decide before you start.

### Up to ~5,000 words (an essay, a short story, a long memo)

- Read the whole thing into context.
- Pass 1: mechanical fixes (apply + log).
- Pass 2: substantive suggestions.
- Pass 3: pattern findings on the full text.
- Write both deliverables.

### 5,000 – 30,000 words (a paper, a novella, a long report)

- If the document has natural sections (chapters, parts, numbered sections),
  treat each section as a chunk.
- If it doesn't, split into ~3,000-word chunks at paragraph boundaries — do
  not split inside a paragraph.
- For each chunk, run the three passes locally; after every chunk, update
  the running phrase-frequency table (see below).
- After all chunks, do a **cross-chunk pass** for pattern findings before
  writing the report.

### 30,000+ words (a book)

This is the case to plan carefully for. You will run out of context if you
try to hold the whole book at once.

**Setup:**

1. Read the table of contents (or first ~1000 words if no TOC) to identify
   chapter boundaries.
2. Write a `proofread-tasklist.md` to a scratch location (use
   `rness/io/output/analyzer/<source-slug>-scratch/`). It lists:
   - every chapter and its source location
   - the per-chapter output paths (corrected chunk + per-chapter report
     fragment)
   - a placeholder for the running phrase-frequency table
3. Copy each chapter's text to its own scratch file
   (`scratch/ch01.txt`, `scratch/ch02.txt`, …) so you can read them
   one at a time.

**Per-chapter loop:**

For each chapter:

1. Read just that chapter.
2. Pass 1 — mechanical fixes. Write the corrected chapter text to
   `scratch/ch{N}-corrected.txt`. Append every change to
   `scratch/ch{N}-changes.md` (the per-chapter change log).
3. Pass 2 — substantive suggestions. Append to
   `scratch/ch{N}-suggestions.md`.
4. Pass 3 — repeated-phrase scan within the chapter. Then update the
   global phrase-frequency table in `scratch/phrase-table.md` (see
   below for the schema).
5. Update the tasklist: mark this chapter done.

**Finalization:**

1. Concatenate `scratch/ch*-corrected.txt` into
   `<source-slug>-corrected.<ext>` in the analyzer output directory.
2. Compile the per-chapter change logs + suggestions + cross-chapter pattern
   findings into `<source-slug>-proof-report.md`.
3. Leave `scratch/` in place — the user may want to inspect it. Mention
   the scratch path in the report.

**Resumability:** the tasklist makes the process resumable. If the
conversation runs out of room mid-book, the user can start a fresh
conversation, point analyzer at the same scratch directory, and you can
pick up at the next unchecked chapter.

---

## Pattern detection — repeated phrases

You are watching for the "phrase the author leans on too often" — distinctive
multi-word strings that feel like a fingerprint after the third or fourth
time. This is the net-new capability for this mode.

### What counts as a candidate phrase

- 3–7 word distinctive strings. (Two-word phrases are usually too common
  to flag; longer than seven and you're describing a sentence, not a tic.)
- Not stock connective phrasing (`on the other hand`, `in this case`, `for
  example`). These don't count even if they repeat.
- Not technical terms specific to the subject matter — repetition of those
  is usually appropriate.
- Distinctive metaphors, similes, or comparisons — even at 2–3 occurrences
  these are worth noting, because the author probably didn't realize they
  were reaching for the same image twice.
- Distinctive sentence openers if they repeat across many paragraphs
  (`What's interesting is that…`, `The thing is,…`, `Look,…`).

### The phrase-frequency table

A running tally maintained across chunks. Schema:

```markdown
| Phrase | Count | Locations | Type | First flagged |
|--------|-------|-----------|------|---------------|
| "the sense that something was about to happen" | 4 | ch02 ¶7; ch05 ¶12; ch11 ¶3; ch14 ¶22 | distinctive sentence | ch05 |
| "like a shadow on water" | 3 | ch03 ¶4; ch08 ¶15; ch19 ¶6 | metaphor | ch08 |
```

Flagging thresholds (default; the user can override):

- Distinctive 3–7 word strings: flag at 3+ occurrences in a chunked book,
  4+ in a single-chunk document.
- Distinctive metaphors/similes: flag at 2+.
- Distinctive sentence openers: flag at 5+ in a book, 3+ in a paper.

When you flag, do not silently fix. Put it in the proof report under
"Repeated phrasing" and let the author decide.

---

## Substantive suggestions

These never get applied silently. They go in the proof report. Categories
to consider, from smallest scope to largest:

- **Word-level.** A weak or imprecise word with a stronger alternative.
  Suggest the alternative; explain why in one short clause.
- **Sentence-level.** A sentence that is technically correct but does too
  much, too little, or in the wrong order. Suggest a rewrite or a split.
- **Paragraph-level flow.** A paragraph whose sentences are in an order
  that buries the lead, or where a transition is missing.
- **Section/chapter flow.** A section that drifts off-topic, starts in the
  wrong place, repeats a point the previous section already made, or sets
  up something that never pays off.
- **Document structure.** Larger missing-load-bearing-structure problems:
  a thesis that arrives in chapter 3 instead of chapter 1, two chapters
  that probably want to be one, a conclusion that doesn't answer the
  question the opening posed.

For each suggestion, write:

- the location (chapter, paragraph, or page reference)
- the current text in `> blockquote` form (or a brief excerpt for long
  passages — start and end with ellipses)
- the suggestion in one short paragraph
- *optionally* — only when the user has indicated they want it — a rewrite

You can sometimes draw on the persona roster (SKILL.md) when forming a
suggestion. *"The Editor would say…"* / *"The Target Reader might trip
over…"* / *"The Stylist would flag…"*. Use sparingly; one persona voice
per suggestion at most, and only when it sharpens the note.

---

## Proof report — template

```markdown
# Proof report — [Document title]

**Source:** [path or URL]
**Length:** [word count] words   |   **Date:** [YYYY-MM-DD]
**Chunking strategy:** [single-pass / N sections / N chapters via scratch dir]
**Scratch directory (if any):** `rness/io/output/analyzer/<slug>-scratch/`

---

## Summary

- Mechanical fixes applied: **[N]**
- Substantive suggestions: **[N]**
- Repeated-phrase findings: **[N]**
- Structural notes: **[N]**

The corrected manuscript is at `<filename>`. Diff it against the original to
see exactly which characters changed; the change log below also lists every
fix.

---

## Mechanical fixes (applied)

For each change, one line in the format:
`[location] — "before" → "after" — [reason]`

For example:
- ch02 ¶4 — "recieved" → "received" — spelling
- ch07 ¶12 — "the the river" → "the river" — doubled word
- ch11 ¶3 — "paris" → "Paris" — proper noun capitalization (matches every
  other instance in the document)

[…full list, grouped by chapter or section…]

---

## Suggestions (not applied)

Grouped by scope, smallest to largest.

### Word and phrase

[entries — location, current, suggestion]

### Sentence

[entries]

### Paragraph and section flow

[entries]

### Document structure

[entries]

---

## Repeated phrasing

[the phrase-frequency table from the scratch directory, restricted to
phrases that crossed the flagging threshold]

Brief note on overall pattern: is the author leaning on a particular
metaphor family, a particular sentence shape, a particular hedge?

---

## Structural notes

[longer-form notes that don't fit the suggestion list — e.g. "Chapters 4
and 7 cover overlapping material; consider merging." Keep these grounded
in specific evidence.]

---

*analyzer — proofread mode*
```

---

## Edge cases

- **Drafts in active revision:** ask the user whether to apply mechanical
  fixes or just report. Some writers want zero changes to the file they're
  editing.
- **Documents with intentional non-standard spelling** (dialect, period
  voice, invented language): ask before fixing the first apparent
  "misspelling," confirm intent, and from then on respect that choice
  consistently.
- **Documents that mix dialects deliberately** (a novel set in two
  countries, a paper quoting both British and American sources): note this
  in the report and do not normalize.
- **Code, structured data, or markup-heavy documents:** copy-edit prose
  sections only; leave code blocks, frontmatter, tables, and structured
  fields untouched.
- **Highly stylized voice** (stream of consciousness, e.e. cummings, prose
  poetry): set the bar for "obvious typo" much higher. When in doubt,
  default to suggestion rather than silent fix.
- **The user's first book / first major work:** the suggestions can be
  honest but should be useful — pick the suggestions that will most
  improve the work, not every suggestion you could possibly make.

---

## Boundaries

- You are a copy editor, not a rewriter. The corrected manuscript should
  read like the user's manuscript with errors removed — same voice, same
  rhythm, same choices.
- Never apply a substantive suggestion silently. Even if you are sure it's
  better. The author keeps the pen.
- Never fix in dialogue or quoted material.
- Track every change. The trust model depends on the change log being
  complete.

---

*Small fixes silently. Larger ideas in the report. The author decides.*
