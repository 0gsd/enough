# analyzer — decide mode

Take a question, a decision, a "I've got this far and don't know what comes
next," or any complex multifaceted prompt — and run a transcripted debate
between three archetypes from the persona roster. Output a clear
recommendation alongside the full debate, so the user can both see the
answer and check its work.

This mode is in-process and local: a single model voicing three personas in
turn. It is designed for laptops and quick deliberations; the user does not
need an API key or a multi-agent harness.

(If they want a heavier-weight debate via the Anthropic API, the `wattba`
skill handles that.)

---

## What this mode is good for

- "I have to pick between X and Y, talk me through it."
- "I've done the work in this branch, what's the best next step?"
- "Here's a half-formed plan, what am I missing?"
- "We disagree about how to do this, run the argument for me."
- "Is this idea actually good or am I in love with it?"
- "What are the strongest cases for and against this?"

What it is *not* for:

- Single-answer factual questions ("what year was X built") — answer those
  directly.
- Pure mechanical tasks ("rename this function") — just do them.
- Anything that needs real-time information you don't have access to.

---

## Persona selection

The persona roster lives in `SKILL.md`. There are ten archetypes. For each
invocation, pick the **three** most relevant to the question.

### How to pick

1. Read the question carefully.
2. Ask: what makes this question hard? (Tradeoffs? Missing information?
   Aesthetic stakes? Audience reaction? Long-term vs. short-term? Risk?)
3. Choose three personas whose perspectives most directly bear on what
   makes it hard.
4. Prefer combinations that will actually disagree. A panel that converges
   immediately is a panel that didn't earn its conclusion.

### Combinations that tend to work

(Not prescriptive — these are starting intuitions, not rules.)

| Question shape | Suggested trio |
|----------------|----------------|
| Should I ship / cut / pivot? | Pragmatist, Skeptic, Target Reader |
| Which of two designs / drafts? | Editor, Stylist, Target Reader |
| Is this idea actually novel? | Historian, Synthesizer, Skeptic |
| Will users get this? | Outsider, Target Reader, Editor |
| Is this technically right? | Insider, Skeptic, Pragmatist |
| Should I take this risk? | Pragmatist, Contrarian, Synthesizer |
| Is there a stronger version of the opposite case? | Contrarian, Skeptic, Historian |
| Am I missing something obvious? | Outsider, Insider, Skeptic |

If two questions are nested ("should I do A, and if so, how?"), pick
personas for the *harder* of the two and let them speak to both.

### Tell the user who's on the panel

Open the output by naming the three personas and saying in one sentence why
each was chosen. This is part of the deliverable — the user should be able
to disagree with the casting and ask you to rerun with a different trio.

---

## Debate structure

Run **three rounds** by default. Each round has each persona speak once, in
the order Skeptic-types first, Builder-types last (so the conversation moves
from "what's wrong with this" toward "what should we actually do").

If the question is genuinely simple and consensus is real after round one,
you may end early — but say so explicitly and explain why the panel
converged.

If the question is genuinely hard and round three still has open
disagreement, you may add a fourth round — but no more. Long debates produce
diminishing returns and bloated transcripts.

### Each persona's turn

A turn is **2–5 sentences**. Not a paragraph essay. Personas should:

- Stay in character. The Skeptic does not become reasonable in round two;
  the Contrarian does not give in just to be polite. They *can* update on
  good arguments — but the update has to be earned.
- Reference what previous speakers said by name. "The Editor's point about
  structure is right but doesn't address…" This is what makes it a debate
  and not three monologues.
- Make at least one move per turn — a new argument, a counter, a question,
  a concession. Repeating a previous round's point is not a turn.
- Disagree productively. Manufactured agreement is worse than honest
  disagreement.

### Voice

Each persona has a voice; do not blur them.

- **The Editor** is calm, organized, asks "what is the structure of this?"
- **The Skeptic** is direct, probing, asks "what would have to be true?"
- **The Target Reader** is the audience speaking; reacts the way they
  would, with their assumptions and impatience.
- **The Outsider** asks naive questions that turn out to be load-bearing.
- **The Historian** brings context, precedent, the "this has been tried
  before" view.
- **The Contrarian** argues the opposite case fully, not as a strawman.
- **The Pragmatist** asks "so what does this change Monday morning?"
- **The Stylist** cares about how things land, sound, feel; the
  craft-level perspective.
- **The Synthesizer** sees connections to adjacent fields and broader
  patterns.
- **The Insider** is the domain expert; speaks with the specifics only
  someone in the field would have.

If you find yourself writing the same sentence in two personas' voices,
something is wrong — back up and reread the roster.

---

## Workflow

### Step 1 — Frame the question

Restate the question in your own words at the top of the output. If the
user's question is vague, narrow it before you start; if it's compound
("should I A and B and C?"), break it into the actual sub-decisions.

If you genuinely don't have enough context to debate it, ask **one**
clarifying question to the user before proceeding. Don't ask several.

### Step 2 — Lay out the options (briefly)

A short numbered list of the options on the table, including any options
the user didn't name but that the personas should be free to bring up
(e.g. "do nothing," "do something smaller first").

### Step 3 — Cast the panel

Name the three personas and one sentence of casting rationale each.

### Step 4 — Run the debate

Three rounds, each persona speaking once per round, 2–5 sentences per turn.
Write it like a transcript:

> **The Skeptic:** [their turn]
>
> **The Pragmatist:** [their turn]
>
> **The Editor:** [their turn]

Do not insert your own narration between turns. The debate is the debate.

### Step 5 — Synthesize

After the rounds, write a short **Synthesis** section (under 200 words):

- Where did the panel converge?
- Where did they remain split, and what does each side weigh more heavily?
- Are there any moves the user could make that would change which position
  is right?

### Step 6 — Recommend

Give a **Recommendation** in plain prose, 1–3 sentences. Be direct: name
the best option and why. If the honest recommendation is "the panel did not
converge; here is how you'd decide between the remaining two," say that.
"It depends" is allowed only if you immediately specify *what it depends
on* — otherwise it is non-advice.

If the user explicitly asked for a ranked list rather than a single pick,
provide that instead.

### Step 7 — Write the file

Save to `rness/io/output/analyzer/<question-slug>-decision.md` (mirroring
any subfolder the user named). Create the directory if it does not exist.

Slug from a short version of the question. Keep slugs lowercased and
hyphenated.

---

## Output template

```markdown
# Decision — [Restated question]

**Date:** [YYYY-MM-DD]
**Original prompt:** [user's question, verbatim, blockquoted]

---

## The question (restated)

[1–3 sentences, clarifying any ambiguity in the original prompt]

## Options on the table

1. [Option A]
2. [Option B]
3. [Option C — including any options the user didn't name]
   …

## The panel

- **[Persona 1]** — [one sentence of casting rationale]
- **[Persona 2]** — [one sentence]
- **[Persona 3]** — [one sentence]

---

## Debate

### Round 1

> **[Persona 1]:** [turn]
>
> **[Persona 2]:** [turn]
>
> **[Persona 3]:** [turn]

### Round 2

> **[Persona 1]:** [turn]
>
> **[Persona 2]:** [turn]
>
> **[Persona 3]:** [turn]

### Round 3

> **[Persona 1]:** [turn]
>
> **[Persona 2]:** [turn]
>
> **[Persona 3]:** [turn]

(Optional Round 4 only if still genuinely contested.)

---

## Synthesis

[~150 words on where the panel landed and what remains in tension]

## Recommendation

[1–3 sentences, plain and direct]

---

*analyzer — decide mode*
```

---

## Calibration

- **Three personas, not one.** A debate is the point. If you find
  yourself writing the same argument under three names, the trio was
  miscast — restart the casting step.
- **No artificial neutrality.** When the case for one option is clearly
  stronger, the Recommendation should say so. Hedging that contradicts
  the debate is dishonest.
- **Show the work.** The full transcript is the receipt for the
  recommendation. The user can disagree with the synthesis only if they
  can see what the personas actually said.
- **Don't moralize in the personas' voices.** "The right thing to do is
  obvious" is rarely a turn; it's a non-argument. Even the Pragmatist
  has to *argue*, not just declare.
- **Length budget.** A typical decide output is 800–1500 words.
  Genuinely complex decisions can run longer; one-paragraph
  recommendations are usually wrong.

---

## Edge cases

- **The user just wants three perspectives, no recommendation.** Skip
  the Recommendation section; keep the Synthesis. Note at the top that
  this is a non-prescriptive debate.
- **The user wants more than three personas.** Run with up to five.
  Beyond five, the transcript becomes unreadable.
- **The user names the personas they want.** Use their choices. If
  their picks would all agree, gently flag that the debate may be thin
  and offer one alternative.
- **The question is actually a research question, not a decision.**
  Tell the user; offer to run `summarize` on the source material
  instead, or to defer the debate until they have more facts.
- **The question is emotionally charged or personal.** Personas should
  still argue, not perform empathy. The user is asking for thinking, not
  comfort — but the Recommendation can acknowledge the human stakes.

---

*Three voices. One transcript. A clear answer at the bottom.*
