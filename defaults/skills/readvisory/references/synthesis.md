# Synthesis — writing the two documents

The interview is over. You have `answers.md` (what the source said) and
`context.md` (what the user said about them). Now you write two files and
show them to the user before anything is installed.

- **`AGENT.md`** — how this readvisor works. It has to stand on its own: a
  session that never opens `MOTIVATION.md` should still get a usable
  readvisor. **Roughly 600–1300 words** — the shipped block-breaker is the bar, not the cap.
- **`MOTIVATION.md`** — what sits underneath. Values, fears, frame, and an
  honest account of where the profile is thin. **Roughly 400–1000 words.**

Drafts go to `rness/io/output/readvisory/<name>/AGENT.draft.md` and
`MOTIVATION.draft.md`. Show them in chat first. Write the files after the
user has seen them, so a reset does not lose the corrected version.

---

## AGENT.md — the exact shape

Use these headings, in this order, with these words. enough and the user both
read these documents; a readvisor with improvised headings reads as a
different kind of object.

    # <Display Name>

    <One short paragraph. Who this readvisor is built from — in terms of
    judgment, not identity — and what it is for. Two to four sentences.
    Address the readvisor as "you".>

    ## Core orientation

    ## Decision-making style

    ## Core moves

    ## Anti-patterns

    ## Communication style

    ## Domains of strength

    ## Hand-offs

    ## Tone notes

    ## How to apply this profile to the user's actual questions

    ## When in doubt

    ---
    enough-tooltip-text: "…"

What goes in each:

**Core orientation** — 2–4 sentences naming the foundational stance: how they
move under uncertainty, what timescale they trust, what they believe makes
things change. Use their own phrasing where it is memorable. This is the
paragraph that decides whether the readvisor sounds like a person.

**Decision-making style** — 3–6 short bullets. How they take a problem apart,
where they put their trust, what they do when it is unclear. Concrete. "Reads
the ending first" beats "values structure".

**Core moves** — 3–5 numbered, each a bolded name and one sentence. These are
the instinctive first things this readvisor does. A move is an action, not a
trait: *"Ask who the piece is for"*, not *"reader-focused"*.

**Anti-patterns** — 2–5 bullets, bolded name plus a sentence. What this
readvisor reliably pushes back against. Anti-patterns are half of what makes
a readvisor useful; keep the source's own, and keep their heat.

**Communication style** — 2–4 sentences. Length, directness, whether they
tell stories, whether they ask questions back, how they behave when told they
are not helping. Quote a phrasing if you have a good one.

**Domains of strength** — a short list of the kinds of question where this
readvisor is worth asking.

**Hand-offs** — where it says *go ask somebody else*. See below.

**Tone notes** — 2–4 sentences on texture: warm, dry, blunt, teasing,
patient. Include what the *user* asked for in `context.md` — this is where
their answer about tone lands.

**How to apply this profile to the user's actual questions** — the
three-tier signal section. See below.

**When in doubt** — 1–3 sentences. What this readvisor does when it does not
know: says so, asks for more, picks the smallest step, slows down. If the
source's default is to admit ignorance, keep it. Do not upgrade it into
confidence.

**The trailing line.** `AGENT.md` ends with a `---` rule and then, as the
last non-empty line:

    enough-tooltip-text: "careful-reader tells you whether a draft is done, and what it is still owed."

One line, one sentence, in enough's house voice: lowercase start, plain
words, addressed to the user, and it names the readvisor by its folder name
or opens with "engage \<name\> to …". `install_readvisor` refuses a document
without it.

No hash comment, no provenance block, no machine-readable header. The
documents are for the user and for enough to read, and nothing else.

---

## MOTIVATION.md — the exact shape

    # Motivational Substrate — <Display Name>

    <One or two sentences: what this file is for. Read it when you need to
    know not just what this readvisor would say, but why — and where it is
    calibrated well and badly.>

    ## What this readvisor cares about

    ## What this readvisor protects against

    ## What this readvisor finds beautiful

    ## Implicit theory of the world

    ## What success looks like in their frame

    ## Reading of the profile

    ## Likely failure modes

    ## Notes for the user

**Cares about / protects against / finds beautiful** — 3–5, 2–4 and 2–4
bullets. Specific, never generic. Not "integrity" but "won't let a deadline
override the one read-through that catches the real problem". The
*beautiful* list comes mostly from the taste questions; do not skip it,
because it is where the readvisor's aesthetic actually lives.

**Implicit theory of the world** — 2–4 sentences, understated. What this
person seems to believe about how things actually work, stated as the
assumption underneath their advice rather than as a manifesto.

**What success looks like in their frame** — 2–4 sentences. The texture of a
good outcome to them. Not "happiness" — something you could recognise.

**Reading of the profile** — your own honest account of what the answers add
up to, with your confidence marked. Name the two or three strongest patterns
— places where several answers pull the same way — and say what each one
means for how the readvisor should be used. This section is interpretation
and must read as interpretation.

**Likely failure modes** — 2–4 bullets. Where this readvisor will go wrong:
the tendency it will over-apply, the question it will answer when it should
not, the thing it will keep doing past the point of use. Every good readvisor
has these. A `MOTIVATION.md` without them is flattering, not useful.

**Notes for the user** — 2–4 sentences, plain. Sharpest on what, weakest on
what, best used how. This is the paragraph the user will actually reread.

`MOTIVATION.md` has no tooltip line. Only `AGENT.md` carries it.

---

## Marking interpretive leaps

You will infer things the answers did not say. That is most of the value —
and all of the risk. **Every inference gets marked in the text**, so the user
can overrule it by reading rather than by cross-examining you.

Use these, inline and in italics:

- *reading this as:* — you are interpreting an answer.
- *inferred hand-off:* — the source never said this; the pattern implies it.
- *the answers cluster as:* — you are naming a pattern across several
  answers.
- *not in the answers:* — you are naming a silence.

For example:

> **Externally graded writing** — *inferred hand-off:* the "the rules are
> invented, so the cure can be invented" frame leans on the work being
> voluntary. When it is not — a committee, an editor with red lines, a house
> style — narrow the help to the part that is still free.

Unmarked, that reads as something the person said. Marked, it reads as what
it is: a reasonable guess the user can delete in ten seconds.

The rule is simple. **If you could not point at the line in `answers.md` or
`context.md` that says it, mark it.**

---

## Honest hand-offs

A hand-off names a kind of question where this readvisor should say *go ask
somebody else* — and says it in the readvisor's own voice, not as a
disclaimer.

Write each one as: **the domain** — what the readvisor does instead.

> **Life-blocks** — grief, burnout, a hard stretch wearing a writing block's
> clothes. You will always listen, and naming it may itself free the writing
> — but you do not pretend to solve it.

Three sources for hand-offs, in order of authority:

1. **The source said so** (LIMIT-3, or anywhere they declined). Keep their
   words. These are not negotiable and not edited for confidence.
2. **The user said so** (the "where should it defer" follow-up). Keep, and
   attribute nothing to the source.
3. **You inferred it** from a silence. Allowed, but marked *inferred
   hand-off:* every time.

A readvisor with no hand-offs is not a readvisor, it is a search engine with
opinions. If the interview produced none, ask the user one more question
before you invent one.

---

## The low-signal posture

The "How to apply this profile to the user's actual questions" section sorts
the user's real questions into three tiers. Write it as three labelled
groups, with the reason attached to each entry:

> **High signal on:**
> - Essay and argument blocks — especially "I don't know what I'm actually
>   saying".
>
> **Useful but indirect on:**
> - Plot-level fiction. You will generate good options, but expect to
>   translate them into your own genre's conventions.
>
> **Low signal on:**
> - Line-level prose craft. Not a strength; say so rather than faking it.

Then close the section with one sentence that tells the readvisor what to do
in the third tier:

> When the question lands in low-signal territory, your instinct is to say so
> plainly. Channel that — do not invent advice.

Two rules for this section:

- **The tiers come from the brief.** The user's actual questions
  (`context.md`, BRIEF-1) are what gets sorted. A tier list about questions
  nobody is going to ask is decoration.
- **The low tier must not be empty.** If everything is high signal, you have
  written a flattering profile rather than an accurate one. Go back to the
  answers and find the edges.

---

## Voice rules

The two documents should read as though written by somebody who paid close
attention to one person. Not by a system that processed them.

**Do:**

- **Quote what was memorable.** A striking phrase, a metaphor, an exact
  framing — keep it, in quotation marks. Quoted phrasing is the whole reason
  the finished readvisor sounds like somebody.
- **Write moves, not attributes.** "Tends toward small bets" is nothing.
  "Asks what the two-week version would look like" is a readvisor.
- **Keep the tension.** If two answers pull against each other, say so and
  say when each applies. Do not iron it flat; the tension is the person.
- **Use active verbs.** *instinctively asks · pushes back when · refuses to ·
  reads first · will hand you*.
- **Stay inside the source's confidence.** If they hedged, the readvisor
  hedges. If they said "I don't know", the readvisor is allowed not to know.

**Do not:**

- **Do not make the readvisor smarter than the person.** Same mind, better
  organised. Adding sophistication they did not show is the most common way
  this goes wrong, and the user will notice immediately.
- **Do not invent detail.** If the answers are silent on a domain, `AGENT.md`
  is silent on it. `MOTIVATION.md` may *name* the silence; it never fills it.
- **Do not politicise.** If the source kept value questions clear of party
  and creed, so do you.
- **Do not write compliance-doc voice** — "aligned", "authentic",
  "leveraging", "stakeholder", "strengths and weaknesses".
- **Do not write horoscope voice** — "you are a person who values growth".
  Every sentence should be one that could be false.
- **Do not bullet everything.** Prose where prose reads better; bullets where
  the material is genuinely a list.

**Short and sharp beats long and complete.** A readvisor that fits on a
screen and says three true things gets used. One that sprawls and hedges does
not.

---

## When the signal is thin

Some sessions produce little: six short answers, everything hedged, one axis
clear and the rest empty. Do not inflate it.

- Write a short `AGENT.md` that says only what the answers support.
- Write an honest `MOTIVATION.md` that names the thinness in "Reading of the
  profile" and lists the empty axes.
- Tell the user plainly: *"This is about half a readvisor. It will be good on
  the two things she actually talked about and vague on everything else. If
  she has another twenty minutes, here are the three questions I'd ask."*
- Offer the top-up. A second short round later is cheap; a confident
  invention is not.

A thin readvisor honestly written is more useful than a thick one that is
guessing, because the user knows which parts to trust.

---

## The correction loop

Show both documents in chat, in full, before writing them out. Then say what
kind of corrections you want — name all three, because people only give the
first kind unless invited:

1. **"That's not quite right."** → Rephrase it and show that section again.
   Do not defend the draft. If you cannot rephrase it without losing the
   point, say which answer it came from and ask what you misread.
2. **"You missed something."** → This usually means an axis you did not
   cover. Ask one or two more questions — of the user, or, if the source is
   reachable and it matters, of the source — then rewrite the affected
   section.
3. **"That's too identifying."** → Abstract it, then check the neighbouring
   sentences for the same detail arriving another way, then show the whole
   section again. See `privacy.md`.

Iterate until the user signs off. Two rounds is normal. If you are on the
fourth, stop rewriting and ask what the readvisor is supposed to do that this
draft would not do — the disagreement is about the brief, not the wording.

When the user signs off, go to step 6 in `SKILL.md` and install.
