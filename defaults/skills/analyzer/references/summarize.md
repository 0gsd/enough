# analyzer — summarize mode

Produce a single-page even-handed digest of any text — long, short, web page,
book, paper, blog post, transcript, draft, manifesto, marketing copy.

The output is descriptive, not evaluative. You are explaining what the text
is, who it is for, how it sounds, and what it actually says — so that a reader
who has not opened it can decide whether to engage with it themselves.

---

## Three lenses

### Lens I — WHO

1. **Author (perceived).** Who appears to have written this and what does the
   text suggest about their position, expertise, profession, affiliation, or
   stake in the topic? If the author is named, note who they are; if not,
   characterize them from internal evidence (vocabulary, references, tone).
2. **Perceived motivation.** What does the text seem to want — to inform,
   persuade, sell, vent, document, entertain, recruit, argue, comfort,
   provoke? Name the structural goal, not just the claimed one. If those
   diverge, note both.
3. **Apparent biases or commitments.** What does the author seem to take for
   granted, value, be loyal to, or be quietly fighting against? Describe
   neutrally — biases are not automatically a flaw; they are a fact about
   where the text is coming from.
4. **Intended audience.** Who is this for? What does the text assume the
   reader already knows, believes, or cares about? A medical paper means
   different things to a clinician and a patient; a policy memo means
   different things inside and outside the issuing organization. Pin it down.

### Lens II — HOW

1. **Tone and register.** Formal, casual, intimate, distant, urgent, dry,
   warm, polemical, scholarly, conversational, oracular? Describe in plain
   terms; quote a phrase if it crystallizes the tone.
2. **Vocabulary and lexicon.** Is the text plain or jargon-heavy? Are there
   distinctive word choices, recurring metaphors, technical terms, in-group
   shorthand, or unusual phrasings? Note any words or phrases the author
   leans on.
3. **Structural shape.** How is it built? Argument-and-evidence, narrative,
   list, dialogue, accumulation of anecdote, FAQ, manifesto, point-by-point
   rebuttal? One paragraph each — keep it visual.
4. **Persuasion mechanics (if any).** If the text is trying to move the
   reader, briefly note how — appeals to authority, emotional narrative, data,
   shared values, urgency, repetition, humor. This is description, not
   accusation; persuasion is normal and most texts do some of it.

### Lens III — WHAT

1. **The point.** In 2–5 sentences, what does the text actually argue,
   assert, narrate, or convey? Not what it discusses — what it *says*. If it
   has no coherent point, say so. If it has multiple competing points, name
   them.
2. **Three key quotes.** Extract exactly three direct quotations that
   crystallize the text. Rules:
   - The author's own words (or the speaker's, in a transcript). Not someone
     they're quoting unless that quotation is functioning as the author's
     thesis.
   - Each quote: a sentence or short passage (1–3 sentences).
   - Include a location: line number, paragraph number, page number,
     percentage through the text, section heading, or timestamp — whatever
     the source format supports.
   - One sentence after each quote saying why it earns its place. Aim for
     one quote that captures the *thesis*, one the *method*, one the *tone
     or blind spot*.

---

## Workflow

### Step 1 — Ingest

Determine the input and read it through, end to end. Do not skip sections.

- **Uploaded file** (`.txt`, `.md`, `.docx`, `.pdf`, `.epub`, `.html`):
  read from `rness/io/input/` (or wherever the user pointed you). Use the
  appropriate extractor for the format (`pandoc` for docx, `pdftotext` for
  pdf, etc.) if reading the raw bytes would be lossy.
- **Pasted text:** work from the message.
- **URL:** fetch the page. If the page is paginated or has a "read more,"
  follow it.
- **Multiple inputs:** one summary per source, unless the user explicitly
  asks for a comparative digest.

Note word count and format/genre — those calibrate the analysis.

### Step 2 — Read with all three lenses active

As you read, mark:

- structural moves (how the text is organized)
- rhetorical moves (how it persuades)
- distinctive phrasings (for the tone/lexicon note)
- the three candidate key quotes (with their locations)
- whatever the text conspicuously is *not* talking about (often as
  revealing as what it is)

For long texts (10k+ words), this is the slow step. Do it anyway. The whole
value of this mode is that you actually read the thing.

### Step 3 — Compose the one-pager

Target length: **800–1000 words**, fitting one printed page at 9pt. Going to
~1100 for a genuinely complex input is fine; padding past that is not. Every
sentence should do work. No filler, no hedging, no "it is interesting to
note that."

Tone: a thoughtful friend who actually read the thing and is telling you
what they found, with receipts. Not snarky, not deferential.

### Step 4 — Write the file

Save to `rness/io/output/analyzer/<source-slug>-summary.md` (mirroring any
subfolder the user named). Create the directory if it does not exist.

Derive the slug from: the source filename → the page title → a short slug
from the point summary. Keep slugs lowercased and hyphenated.

---

## Output template

```markdown
# Summary — [Title or Source Identifier]

**Source:** [filename / URL / "pasted text"]
**Length:** [word count] words   |   **Type:** [genre/format]
**Date of analysis:** [YYYY-MM-DD]

---

## I. WHO

**Author (perceived):** [1–2 sentences]

**Perceived motivation:** [1–2 sentences — structural goal, plus claimed goal
if it differs]

**Apparent biases / commitments:** [1–3 sentences, neutral]

**Intended audience:** [1–2 sentences — who the text assumes is reading, and
what it assumes they already know]

---

## II. HOW

**Tone and register:** [1–2 sentences; quote a phrase if useful]

**Vocabulary and lexicon:** [1–2 sentences — plainness, jargon, distinctive
recurring words, characteristic phrasings]

**Structural shape:** [1–2 sentences on how the text is built]

**Persuasion mechanics:** [1–2 sentences; omit if the text is purely
informational and not trying to move the reader]

---

## III. WHAT

**The point:** [2–5 sentences — what the text actually argues, asserts, or
conveys]

**Key quotes:**

1. > "[Quote 1]" — [location]
   *[One sentence on why this quote matters]*

2. > "[Quote 2]" — [location]
   *[One sentence on why this quote matters]*

3. > "[Quote 3]" — [location]
   *[One sentence on why this quote matters]*

---

*analyzer — summarize mode*
```

---

## Calibration

- **Be descriptive, not evaluative.** "Argues for X by appealing to Y" is
  description. "Argues unconvincingly for X" is a judgment — only include it
  if the user asked for a critical read, and then make sure your reasoning
  is on the page.
- **Resist the urge to score.** No 0.0–1.0 numbers, no letter grades, no
  star ratings. If the text is muddled, *say* it is muddled and point to
  where; don't reach for a metric.
- **Quote from the middle.** The most revealing key quote is often buried
  deep in the text, where the author is less guarded than in the intro or
  conclusion.
- **Note absences carefully.** "The text never addresses X" is a fair
  observation if X is reasonably expected by the genre. It is not a fair
  observation if you are simply wishing the author wrote a different text.
- **The user's own writing.** If they have asked you to summarize something
  they wrote, do not soften the description. They asked because they want
  an outside read. Be even-handed, not flattering.

---

## Edge cases

- **Very short text (<500 words):** Use the full template; note that brevity
  limits some lenses. Short texts often have unusually sharp tone signatures
  — there is no room to hide.
- **No clear single author** (Wikipedia, collective documents): Lens I.1
  becomes "collective/institutional authorship" — describe the apparent
  editorial voice and any traces of competing hands.
- **Fiction:** Author motivation = literary/experiential intention. Method
  = narrative technique, POV, pacing. The point = what the work is *about*
  (the experience it creates, the question it sits with), not just its plot.
- **Multiple languages:** Analyze in the primary language; note any
  code-switching or untranslated passages and how they affect accessibility.
- **Raw data, code, or non-prose:** This mode is for prose. Tell the user
  the framework only partially applies and offer what you can.

---

*Describe what the text is doing. Trust the user to decide what they think
of it.*
