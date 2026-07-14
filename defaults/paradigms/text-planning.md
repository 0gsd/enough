---
name: text-planning
description: Long-horizon planning paradigm for any structured text — novel, novella, short-story collection, non-fiction book, academic paper, long essay, blog post, manifesto. Switch to this whenever the user expresses intent to plan, outline, or structure a piece of writing they intend to author themselves (with or without later agent assistance), and either the `analyzer` or `memoir-dialectic` skill is enabled. Treats the project folder as the heart of a single writing project. Produces a `<project>-text-plan.md` at the project root via patient, iterative collaboration with the user, then optionally generates per-section `<section>-scaffold.md` files on request — purely structural guidance that the user expands into prose themselves.
---

# Text-Planning Paradigm

This paradigm covers the long pre-prose phase of a writing project — the
arc from "I think I want to write something" to "I have a usable plan and
section scaffolds I can sit down and draft from."

Two things happen here:

1. **Plan.** The agent and user build a single plan document together,
   iteratively, across one or many sessions. The plan lives at the
   project root as `<project>-text-plan.md` and is the heart of the
   project folder while planning is active.
2. **Scaffold.** When the plan is in a usable state, the user can ask
   for a *scaffold* of any planned section — a structural guide they
   then expand into prose themselves. Scaffolds are purely structural
   (headers, beats, voice reminders, per-beat word budgets); they
   contain **no generated prose**. The user's voice stays the user's
   voice.

What this paradigm explicitly does *not* do:

- Write prose from the plan or scaffold. (If the user wants the agent to
  draft, they invoke that outside this paradigm — usually by switching to
  `default` and asking directly.)
- Plan memoirs. The `memoir-dialectic` skill is purpose-built for that
  and earns the specialization. See "Memoir handoff" below.

## Activation rule

Switch into this paradigm when **both** conditions hold:

1. The user has expressed planning intent for a long-form structured
   text: "help me plan a novel," "I want to outline a book about X," "let's
   structure my essay collection," "I have an idea for a manifesto," "I'm
   starting work on a non-fiction book," "let's plan out my [text type]."
2. Either the `analyzer` skill or the `memoir-dialectic` skill is enabled
   in the sidebar. (Both serve text-shaped work; either signals the user is
   in a text-project context.)

If condition 1 fires but **no relevant skill is enabled**, stay in
`default` and surface the situation:

> *I'd love to plan this with you — for the best support after the plan
> is built, you'll want to toggle on either `analyzer` (for general
> analytical work on the finished text) or `memoir-dialectic` (if this
> turns out to be a memoir). Once one of those is on, I'll switch into
> the text-planning paradigm.*

Switch by writing `text-planning` to `rness/active-paradigm` with
`write_file`. Effect takes hold next turn. Briefly tell the user you're
switching.

**Switch back to `default`** when planning is paused/done OR when the
user pivots to non-planning work for more than a turn or two.

## Memoir handoff

If during the intake interview the project reveals itself to be a memoir
(autobiography, personal life-writing across more than a single
incident), tell the user:

> *This sounds like memoir territory — `memoir-dialectic` is purpose-built
> for it (sensitive-topic handling, voice capture, multi-session
> resumability, optional draft pipeline). Want me to hand off to that
> skill instead of building a generic text-plan?*

If they say yes, switch back to `default` and let `memoir-dialectic`
take over on their next message. If they say no (e.g. "no, this is a
themed essay collection that happens to draw on my life"), proceed in
text-planning and capture the autobiographical-sources note in the
plan's Voice & Tone section.

Single-incident personal essays, professional memoirs treated as
business books, and other not-quite-memoir cases stay in text-planning
without offering the handoff.

## Three artifacts this paradigm tracks

| Artifact | Path | When created | Owner |
|----------|------|--------------|-------|
| Request file | `rness/requests/develop-plan-for-<slug>_<ts>.md` | Once, at the start | Agent writes, user marks Done |
| Plan document | `<project>-text-plan.md` (project root) | Once, after intake | Co-authored; agent re-reads every turn |
| Scaffold(s) | `<section-slug>-scaffold.md` (project root) | On demand, per section | Agent writes; user expands into prose |

The plan document deliberately lives at the project root, not inside a
subfolder — text-planning treats the project folder as the heart of one
writing project. Multiple plans in one project are allowed (the
`<project>-text-plan.md` prefix disambiguates), but the natural shape is
one plan per project.

## Plan creation — flow

### Step 1 — Confirm name

Ask the user for the working name of the text or project, then derive a
slug:

- "What would you like to call this project? (Working title is fine —
  we can rename later. I'll use it as the prefix for the plan filename.)"
- Slug rule: lowercased, hyphenated, drop articles. "The Quiet Year" →
  `quiet-year`. Plan file: `quiet-year-text-plan.md`.

### Step 2 — Open the request

Create `rness/requests/develop-plan-for-<slug>_<ts>.md` per the
`policies/requests.md` flow. The request stays open until the user marks
it Done. Log Progress Checkpoints each session.

### Step 3 — Intake interview

Conversational, **one or two questions at a time**. Never a flood. Cover
these areas across the first session (or two, if needed):

1. **Overview & seed.** "Tell me what you have in mind — as much detail
   or as much uncertainty as you have. I'll write down everything; we'll
   shape it together."
2. **Intent.** What does this text want to do — entertain, persuade,
   document, console, argue, provoke, instruct, witness?
3. **Audience.** Who is this for? What do they already know? What might
   they resist?
4. **Form.** Novel / novella / story collection / non-fiction book /
   essay / blog post / academic paper / manifesto / something else?
5. **Length target.** Word count or page count, even loose. (Used for
   short-text detection — see below.)
6. **Voice & tone instincts.** Formal / conversational / lyrical /
   spare / playful? Any reference texts they want to feel adjacent to?
7. **Structural instincts.** Chapters, parts, sections, vignettes, no
   structure yet?

Record the answers in the user's own phrasing where you can. Then draft
the initial `<project>-text-plan.md` per the skeleton below. Show it to
the user and ask what to deepen first.

### Step 4 — Short-text detection

If the user's stated target is **under ~5,000 words** (a blog post, a
short essay, a magazine piece), offer the lighter flow:

> *This is short enough that a formal multi-section plan might be more
> overhead than help. Want me to give you a bullet outline straight to
> draft instead, or keep going with the full plan? Either is fine —
> short texts sometimes do benefit from the planning rigor.*

If they want the lighter flow, write a much shorter plan (Overview /
Intent / Audience / Beat-list of 5–10 bullets) and skip the per-section
detail. Otherwise proceed normally.

### Step 5 — Iterative planning loop

Each subsequent turn during planning:

1. **Re-read the plan first.** Always. The user may have edited it
   between turns; their version is authoritative.
2. **Ask focused questions, one or two at a time.** When the user gets
   stuck, offer (don't insist) three or four angles to choose from.
3. **Update the plan in-place,** appending to or refining the relevant
   section. Preserve the user's wording. Never silently remove their
   text.
4. **Note voice and recurring phrases** as the user talks. Append to the
   Voice & Tone section. Scaffolds will pull from here.
5. **Acknowledge user edits naturally.** If you re-read and see the user
   added a chapter or revised a section, mention it: *"I see you added
   chapter 4 on the move to Lisbon — want to flesh that one out next?"*
   Do not pretend not to have seen the change.
6. **Update the request file's Progress Checkpoint** at session end.

### Step 6 — Readiness self-audit (offered, not enforced)

When the plan looks substantially complete, offer the user a quick
readiness audit:

> *Quick check before we call this done: every chapter/section has at
> least a sentence of purpose ✓ / 🔲, word budgets assigned ✓ / 🔲, voice
> & tone captured with a few sample phrases ✓ / 🔲, key beats listed for
> each major section ✓ / 🔲. Want to fill any gaps, or are you ready to
> mark the request Done and start scaffolding?*

The user decides what counts as done.

## Plan document — generic skeleton

Every `<project>-text-plan.md` opens with a self-describing header so a
future agent (or a different conversation, or a collaborator) can read it
cold and know what it is.

```markdown
# <Project Name> — Text Plan

> **About this document.** This is a text plan created in the
> `text-planning` paradigm of an enough workflow. It captures the
> overview, intent, audience, voice, structure, and per-section beats
> for a writing project the user intends to author. When the plan is in
> a usable state, the user may ask the agent to generate per-section
> *scaffolds* — purely structural guides for individual sections — which
> appear next to this file as `<section-slug>-scaffold.md`. The plan
> itself contains no prose to be lifted; it is a blueprint.

> **Request:** `rness/requests/develop-plan-for-<slug>_<ts>.md`
> **Created:** YYYY-MM-DD   **Last touched:** YYYY-MM-DD

## Overview

[2–6 sentences — what the text is, in the user's own words where
possible. The seed.]

## Intent

[What the text wants to do. Why this text, why now.]

## Audience

[Who it's for. What they bring; what they may resist.]

## Form & length

- **Form:** [novel / novella / story collection / non-fiction book /
  essay / blog post / academic paper / manifesto / other]
- **Length target:** [~word count or ~page count]

## Voice & tone

[Adjectives, register, reference texts. Plus a "phrases & rhythms" sub-
section that accumulates distinctive turns of phrase, recurring images,
characteristic vocabulary captured during planning. Scaffolds pull from
here.]

## Structure

[The shape of the whole text. Takes any form the project needs:
  - For a novel: chapters, parts, acts
  - For a story collection: stories with through-line notes
  - For a non-fiction book: parts and chapters
  - For an essay: sections or movements
  - For an academic paper: standard sections (intro, lit review, etc.)
  - For a manifesto: numbered theses
  - For a blog post: hook → arc → payoff (often skipped for short-form)

Use whichever shape the user's instincts and the text's nature call for.
Annotate each top-level structural unit with a one-sentence purpose and
a target word budget.]

## Sections

[One subsection per planned section/chapter/essay/etc. Predictable
header format so scaffolds can target by name:

### Section: <Section Name>

- **Purpose:** [1–2 sentences]
- **Target length:** [~N words]
- **Key beats:**
  - [beat 1]
  - [beat 2]
  - [beat 3]
- **Voice notes:** [section-specific tone, POV, register]
- **Open questions:** [what's still uncertain]

…repeat per section.]

## Open questions & gaps

[Running list of things the user wants to come back to — research
needed, decisions deferred, characters not yet named, sources not yet
read.]
```

Genre suggestions are inline above; don't break them out into separate
template files. The skeleton is the same shape for every text; the
"Structure" and "Sections" parts flex to whatever the text needs.

## With the girraph-merirmaid skill (girraph-backed structure)

When the `girraph-merirmaid` skill is enabled alongside this paradigm,
*contested* plan structure lives in a girraph at the project root
(`<slug>-structure.girraph`), edited via the girraph node tools and the
user's girraph panel. The split: questions still being argued — what
the text is really about, what belongs in or out, competing orderings —
get mapped as issues/positions/arguments in the girraph; the
`<project>-text-plan.md` remains the home for *settled* decisions.
When the user confirms a branch of the map, migrate its conclusion into
the plan document and note the girraph node id next to it. Without the
skill enabled, keep all structure in the plan document as described
above.

## Live document awareness

The plan is a living document the user can edit at any time, including
between turns. The rule is:

- **Re-read the plan at the start of every turn** that happens while
  text-planning is active. Use `read_file`; this is cheap.
- **Treat the user's version as authoritative.** If their edits
  conflict with what you were about to write, integrate around them.
  Never silently overwrite.
- **Acknowledge changes naturally** in your reply. "I see you renamed
  chapter 3 to 'The Bargain' and added a beat about the dog — want to
  develop that beat?"
- **When you write to the plan,** make minimal targeted edits using
  `edit_file` or section-level rewrites. Do not regenerate the whole
  file unless the user asks.

## Scaffold mode

Triggered when the user, while in text-planning, asks for a scaffold:

> "Scaffold chapter 1 for me — I want ~500 words of structural
> guidance for a 4000-word chapter I'll write myself."

### Inputs

- **Which section.** The user names it; match against `### Section:`
  headers in the plan. If ambiguous, ask.
- **Scaffold size and target prose size.** User-stated, or use the
  default ratio of ~1/8 to 1/10 (a 4000-word chapter scaffolds at
  ~400–500 words).
- **Any specific guidance:** beats to emphasize, voice notes to
  surface, things to keep out.

### Output

`<section-slug>-scaffold.md` at the project root. Filename derived
from the section name slug (`chapter-1` for "Chapter 1", `the-bargain`
for "Chapter 3: The Bargain", etc.). If a scaffold for that slug
already exists, suffix with `-v2`, `-v3`, etc.; do not overwrite.

### Format

```markdown
# Scaffold — <Section name>

> **About this scaffold.** Structural guide for expanding into prose.
> Source plan: `<project>-text-plan.md` → `### Section: <name>`.
> Target prose length: ~N words. Scaffold size: ~N words.
> No generated prose; expand the beats below in the user's own voice.

## Section purpose
[Pulled from the plan, in 1–2 sentences.]

## Voice & tone reminders
[Surfaced from the plan's Voice & Tone section. Relevant phrases,
register notes, POV reminders. Keep terse.]

## Beats

### Beat 1 — <short label> (~N words)
[2–4 sentences of structural guidance: what this beat is *about*, what
it needs to accomplish, what to set up, what to pay off. NO prose. NO
sample sentences. The user's voice fills the beat.]

### Beat 2 — <short label> (~N words)
[…]

[…until the beats sum to the scaffold's word budget.]

## Things to NOT do here
[Anti-guidance — what the section should avoid: themes that belong
elsewhere, voice slips to watch for, info-dumps to resist.]

## Open questions for the user
[Anything that came up while scaffolding that the user might want to
resolve before drafting.]
```

### Hard rule: no prose

Scaffolds contain **no sample sentences, no opening lines, no closing
images.** The user's prose stays uncontaminated. If the user explicitly
requests a sample line ("give me a strong first line I can react
against"), they can ask — but the default is zero prose.

### Multi-section scaffolds

If the user asks for several sections at once ("scaffold chapters 1–3"),
produce one file per section, processed sequentially. Pause briefly
between them so the user can interrupt if the first one's not the right
shape.

## Posture

- Collaborator, not order-taker. Patient. One or two questions per
  turn. The plan accumulates over many short exchanges, not one long
  download.
- Capture the user's own phrasing whenever you can. Voice & tone are
  load-bearing — scaffolds depend on them.
- Never moralize about content. Never invent biography, history, or
  references the user hasn't introduced.
- The user marks the request Done. You don't, and you don't pressure
  toward it.
- Plan → scaffold → prose is the rhythm of this paradigm. Mention the
  arc when it's useful ("when the plan is in shape, I can scaffold any
  section for you to expand into prose yourself"). Don't oversell it.

## Request tracking

Per `policies/requests.md`:

1. Open `rness/requests/develop-plan-for-<slug>_<ts>.md` at the start
   of the first session.
2. Log a Progress Checkpoint at the end of every session: which
   sections were touched, what's outstanding, where to resume.
3. The user fills in the End Output section when they mark the request
   Done. Don't preempt them.
4. Scaffold generation does *not* open a new request — it's an action
   the agent takes inside the existing planning request, logged as a
   Progress Checkpoint entry.

## Quick reference

| Trigger | Mode | File written |
|---------|------|--------------|
| "Plan a novel/book/essay/etc." (with skill enabled) | Plan | `<project>-text-plan.md` (created) |
| Subsequent planning turn | Plan | `<project>-text-plan.md` (edited in place) |
| "Scaffold chapter N" / "scaffold the <name> section" | Scaffold | `<section-slug>-scaffold.md` |
| User edited the plan between turns | Plan | Acknowledge, integrate, never overwrite |
| Project turns out to be a memoir | Handoff | Switch to `default`; recommend `memoir-dialectic` |
| Planning paused or done | Switch out | `default` |

---

*The project folder is the project. The plan is the blueprint. The
scaffold is the frame. The prose is yours.*

---
enough-tooltip-text: "use the text-planning paradigm to plan and create tracking documents for you and agents to use across sessions."
