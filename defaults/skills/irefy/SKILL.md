---
name: irefy
description: "I Read Everything For You. Ingests any text — Deep Research reports, blog posts, web pages, books, articles, papers, transcripts — and produces a one-page analytical digest with two scored indices: Conveyance Success (0.0–1.0) and Conveyance Evil (0.0–1.0). Three lenses: Intention, Method, Verdict. Use for 'irefy', 'summarize this report', 'digest this', 'one-pager', 'what is this actually saying', 'tl;dr but smart', 'read this for me', 'break this down', 'how manipulative is this', 'what's the agenda'. Also trigger on long uploaded docs (especially Gemini Deep Research), pasted URLs needing critical reads, or any 'read and tell me what matters' request. Works with .txt, .md, .docx, .pdf, .epub, .html, pasted text, and web pages."
---

# IREFY — I Read Everything For You

Read everything. Trust nothing. Report back in one page.

## Philosophy

IREFY is a *reading machine* — not a summarizer. Summarizers compress; IREFY *interrogates*. Every text has an author with an intention, a method for delivering that intention, and a reader whose beliefs, biases, and credulity are either respected or exploited. IREFY makes the full transaction visible in a single page.

The output is deliberately constrained to one page (at 9pt, you have room — roughly 800–1000 words). This is a feature, not a limitation. If you can't say what a text is doing in one page, you haven't understood it yet.

IREFY works on anything an LLM can ingest: Gemini Deep Research reports, blog posts, academic papers, novels, web pages, transcripts, legal filings, newsletters, manifestos, marketing copy, instruction manuals. The analytical framework is universal because the questions are universal: *What are you trying to tell me? How are you trying to tell me? Did it work? Were you honest about it?*

## The Three Lenses

### Lens I — INTENTION

Who is talking, to whom, and why?

**I-a. Author's Objective.** What is the author trying to convey? Not what they *claim* to be doing (which may differ) but what the text structurally *does*. A Deep Research report may claim to be a neutral survey but structurally argues for a particular conclusion. A blog post may present itself as casual reflection but structurally sells a product. Name the real objective.

**I-b. Identity Dependence.** Does correct interpretation require knowing who wrote this or who is reading it? A medical paper means different things to a clinician and a patient. A policy memo means different things inside and outside the issuing organization. An AI-generated report has different epistemic weight than a human-authored one. Flag whether author identity, reader identity, or both are load-bearing for interpretation. If neither matters (rare), say so.

**I-c. Presumed Biases.** What does the text *assume* the reader already believes, values, or knows? What does the author appear to believe, value, or know? Biases aren't always bad — a physics textbook presumes mathematical literacy — but they shape what the text can and cannot communicate. Name them.

**I-d. Required Belief Adjustments.** What does the reader need to take on faith, suspend disbelief about, or adopt as a new premise to receive the author's full intention? For fiction this is literal (genre conventions, premise). For non-fiction this is often invisible — the unstated axioms that make the argument cohere. For persuasive writing this is the gap between where the reader starts and where the author needs them to be. Map it.

### Lens II — METHOD

How is the intention delivered, and how clean is the delivery?

**II-a. Support Structure.** What methods does the author use to support their conveyance? Citations, data, anecdotes, analogies, appeals to authority, logical argument, emotional narrative, visual formatting, repetition, selective omission? Evaluate the relevance and accuracy of these methods. A 50-page report built on three cherry-picked studies is structurally different from one built on a systematic review, even if both "cite sources."

**II-b. Language Persuasion Profile.** How compelling and/or manipulative is the language? Look for: loaded framing, false dichotomies, strategic ambiguity, weasel words ("some experts say"), emotional amplification, urgency manufacture, tribal signaling, flattery of the reader, minimization of counter-evidence. Also note: clarity, precision, elegance, wit — good writing is also a persuasion mechanism, but an honest one. Distinguish between *compelling because true and well-expressed* and *compelling because rhetorically engineered*.

**II-c. Logical Coherence.** Do the assertions, arguments, and conclusions follow from each other? Look for: non sequiturs, circular reasoning, unstated premises doing heavy lifting, correlation-as-causation, motte-and-bailey shifts, scope creep (arguing X, concluding Y). A text can be factually accurate and logically incoherent.

**II-d. Subjectivity Load.** How much of the text's structural weight rests on subjective conclusions, personal presumptions, unverified claims, or aesthetic judgments presented as analysis? Some subjectivity is inevitable and appropriate — but it should be flagged when it's doing structural work. A Deep Research report that says "this approach is promising" is making a subjective claim. If the whole argument pivots on that claim, the reader should know.

### Lens III — VERDICT

What did the text actually accomplish?

**III-a. Point Summary.** Summarize the point(s) of the text in 2–5 sentences. Not what the text *discusses* — what it *argues, asserts, or conveys*. If the text has no coherent point, say that. If it has multiple competing points, name them and note whether they're reconciled.

**III-b. Three Key Quotes.** Extract exactly three quotes that get to the heart of the piece. Rules:
- Quotes must be *primary material* — the author's own words, not someone they're quoting.
- Each quote should be a sentence or short passage (aim for 1–3 sentences).
- Include a location reference: line number, paragraph number, page number, percentage through the text, section heading — whatever attribution method the input format supports.
- For each quote, write one sentence explaining *why* this quote is a heart-of-the-piece moment.

**III-c. Conveyance Success Index (CSI): 0.0 – 1.0.** How successful is this text at conveying what its author intended to convey to its reader?
- **0.0** = Total failure; the reader cannot determine what the author wanted to say.
- **0.3** = The general topic is clear but the argument/point is muddled or lost.
- **0.5** = The point comes through but with significant noise, confusion, or padding.
- **0.7** = Clearly conveyed with some structural or rhetorical issues.
- **0.9** = Precisely, efficiently, and memorably conveyed.
- **1.0** = Masterclass; the text could not communicate its intention more effectively.

**III-d. Conveyance Evil Index (CEI): 0.0 – 1.0.** How manipulative, deceptive, or rhetorically dishonest are the conveyance mechanisms used?
- **0.0** = Transparent, honest, fair-minded; respects the reader's autonomy.
- **0.3** = Some rhetorical spin or selective emphasis, within normal persuasive writing norms.
- **0.5** = Notably manipulative framing, strategic omissions, or emotional engineering.
- **0.7** = Systematically exploits cognitive biases, buries counter-evidence, or uses dark persuasion patterns.
- **0.9** = Propaganda-grade manipulation disguised as neutral information.
- **1.0** = Hostile epistemic weapon; designed to deceive the reader while appearing to inform them.

Note: High CSI + High CEI = *effectively evil*. High CSI + Low CEI = *genuinely good communication*. Low CSI + High CEI = *incompetent manipulation*. Low CSI + Low CEI = *well-intentioned mess*.

## Workflow

### Step 1: Ingest

Determine the input type and read the full text:

- **Uploaded file** (.txt, .md, .docx, .pdf, .epub): Read from `/mnt/user-data/uploads/`. For large files, use appropriate extraction (pandoc for docx, pdftotext for pdf, etc.). For very large texts (books), read the entire text — IREFY doesn't get to skip parts.
- **Pasted text**: Work directly with the text in the conversation.
- **URL**: Use `web_fetch` to retrieve the page. If the page is long or complex, fetch and read the full content.
- **Multiple inputs**: If the user provides multiple texts, produce one IREFY digest *per text* unless they specifically ask for a comparative digest (in which case, produce a single digest that covers all inputs with internal comparison).

Compute a rough word count and note the format/genre for calibration.

### Step 2: Deep Read

Read the entire text with the three lenses active simultaneously. As you read, track:

- Structural moves (how the text is organized and why)
- Rhetorical moves (how the text persuades)
- Logical moves (how the text argues)
- Emotional moves (how the text manipulates feeling)
- Omission moves (what the text conspicuously *doesn't* say)
- The three candidate key quotes (mark their locations)

For long texts (10,000+ words), this is the expensive step. Do not shortcut it. The value of IREFY is that you actually read everything — the user didn't, or doesn't want to, or wants a second opinion from someone who did.

### Step 3: Compose the One-Pager

Write the digest in the output format below. The discipline is *compression without loss of analytical precision*. Every sentence in the output should do work. No filler, no hedging, no "it should be noted that." The tone is: smart friend who read the thing and is telling you what they found, with receipts.

Target length: 800–1000 words. The output should fit on a single printed page at 9pt font with reasonable margins. If you go to 1100 words for a genuinely complex input, fine — but feel the constraint. Brevity is the skill.

### Step 4: Format and Deliver

Output as a Markdown file: `[source-name]-irefy.md` saved to `/mnt/user-data/outputs/`.

If the input was a URL, derive the filename from the domain or page title. If pasted text, use a slug derived from the point summary. If uploaded file, use the source filename.

## Output Template

```markdown
# IREFY — [Title or Source Identifier]

**Source:** [filename / URL / "pasted text"]
**Length:** [word count] words | **Type:** [genre/format]
**Date of analysis:** [date]

---

## I. INTENTION

**Objective:** [I-a — 2-3 sentences on what the text is really trying to do]

**Identity Dependence:** [I-b — 1-2 sentences on whether author/reader identity matters]

**Presumed Biases:** [I-c — 1-3 sentences on what's assumed about author and reader]

**Required Belief Adjustments:** [I-d — 1-3 sentences on what the reader must accept to receive the full message]

---

## II. METHOD

**Support Structure:** [II-a — 2-3 sentences on how the argument/narrative is built and how solid it is]

**Language Profile:** [II-b — 2-3 sentences on persuasion mechanics]

**Logical Coherence:** [II-c — 1-3 sentences on whether it adds up]

**Subjectivity Load:** [II-d — 1-2 sentences on how much rests on opinion vs. evidence]

---

## III. VERDICT

**The Point:** [III-a — 2-5 sentence summary of what the text actually argues/conveys]

**Key Quotes:**

1. > "[Quote 1]" — [location]
   *[One sentence on why this quote matters]*

2. > "[Quote 2]" — [location]
   *[One sentence on why this quote matters]*

3. > "[Quote 3]" — [location]
   *[One sentence on why this quote matters]*

---

**Conveyance Success Index (CSI):** [X.X] / 1.0
*[One sentence justifying the score]*

**Conveyance Evil Index (CEI):** [X.X] / 1.0
*[One sentence justifying the score]*

---

*IREFY — I Read Everything For You*
```

## Calibration Notes

### On scoring CSI:
- Deep Research reports from Gemini etc. typically land 0.5–0.8. They tend to be thorough but padded, with key insights buried in boilerplate.
- Great essays and opinion pieces can hit 0.9+. The best ones have a single sharp point and every sentence serves it.
- Academic papers vary wildly. Good ones: 0.7–0.9. Bad ones (jargon-dense, circular, inconclusive): 0.2–0.4.
- Fiction is scored on *did the author create the experience they intended?* — not on whether you liked the experience.
- Marketing copy and PR are scored on clarity of the pitch, not on whether the product is good.

### On scoring CEI:
- Most honest writing lands 0.1–0.3. Some rhetorical shaping is normal and fine.
- Journalism should ideally be 0.0–0.3. If it scores higher, something is wrong.
- Opinion/editorial is expected to be 0.2–0.5. Persuasion is the genre.
- Marketing/PR is inherently 0.4–0.7. The reader expects to be sold to.
- Propaganda is 0.7–1.0. If you're scoring something this high, be very specific about *what* makes it propaganda-grade.
- Fiction's CEI measures *rhetorical dishonesty within the text's own frame*, not the fact that it's made up. A novel that stacks the deck to make a political point scores higher than one that presents its world honestly and lets the reader draw conclusions.

### On the three quotes:
- The quotes should triangulate: one that captures the *thesis*, one that captures the *method*, one that captures the *tone* or *blind spot*.
- For long texts, resist the temptation to quote from the introduction and conclusion only. The most revealing quotes are often buried in the middle, where the author is less guarded.
- If the text is so formulaic that no quote stands out, that itself is a finding worth noting.

## Edge Cases

- **Very short text** (<500 words): Still produce the full framework but note that brevity limits the analysis. Short texts often score extreme on CEI (either very clean or very manipulative — there's no room to hide).
- **Multiple languages**: Analyze in the primary language. Note if code-switching or untranslated passages affect accessibility.
- **No clear author** (e.g., Wikipedia, collaborative docs): I-b and I-c may be harder to assess. Note the collective/institutional authorship and adjust.
- **Raw data or code**: IREFY is designed for *prose*. For data dumps, note that the framework doesn't fully apply and provide what analysis you can.
- **Fiction**: Full framework applies. "Author's objective" means the literary/experiential intention. "Method" includes narrative technique, point of view, pacing, etc. "Evil" is about rhetorical dishonesty within the fiction's own terms (propaganda novels score high; complex honest novels score low).
- **The user's own writing**: Be honest but constructive. The user is asking IREFY to read their work with the same critical eye it applies to anything else. Don't soften the scores — but do note strengths as well as weaknesses.

## Integration

IREFY is a standalone reading tool. It does not call other skills and is not called by other skills. Its output is for *the user*, not for a pipeline.

That said, IREFY digests can be useful *inputs* to other work — a user might IREFY a stack of research reports and then use the digests to inform a pomo-hacer treatise, a point-press editorial session, or a lit-fic premise. IREFY doesn't need to know about this; it just does its reading and reports back.

---

*You didn't read it. I did. Here's what it said, what it meant, and how honest it was about the difference.*
