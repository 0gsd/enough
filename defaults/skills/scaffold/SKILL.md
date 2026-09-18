---
name: scaffold
description: "Turns a brain dump into a visible structure. Reads a pile of thinking — a story idea, an essay, an argument, a plan, a proposal, a talk, a course — and returns a markdown outline that enough converts deterministically into a composure the user can look at, move around, and fill in. Knows story shapes (arcs, beats, continuity threads, denouements, endings) and non-fiction shapes (claim, grounds, warrant, counter-case, close; goal, phases, dependencies, risks, done-when). Never invents material to fill a hole — it writes a [gap: …] card instead, so the structure shows the writer what they still owe it. Asks at most two clarifying questions before the first pass. Works from text pasted in chat, a file in the project, or an existing composure. Use for 'scaffold this', 'give this a structure', 'structure my notes', 'outline this', 'turn my notes into a composure', 'make me a storyboard', 'map out my essay', 'what shape is this', 'break this plan into phases', 'lay out the acts', 'I have a pile of notes and no structure', 'where are the holes in this', 'I know what happens but not in what order'."
---

# scaffold

A brain dump goes in. An outline comes out. `composure_from_outline` turns
that outline into a composure — one card per beat, section or phase, laid out
on the canvas — and the user can then see the shape of the thing they have
been carrying in their head.

This skill does not write the piece. It writes the structure, and it marks
every place the structure is still missing something.

---

## The pass, in order

1. Get the brain dump (three sources, below).
2. Decide the shape: story, argument, or plan (`references/structure.md`).
3. Ask **at most two** clarifying questions. Often ask none.
4. Write the outline in the grammar below.
5. Call `composure_from_outline`.
6. Tell the user what you could not place, and where the gaps are.

Do the whole pass in one go. Do not ask the user to approve the outline
before creating the composure — the composure *is* how they read it, and
every card is editable once it is on the canvas.

---

## Where the brain dump comes from

| The user… | Do this |
|---|---|
| pastes or types the material in chat | use it as-is |
| names a file (`notes/ideas.md`, a draft, a transcript) | `read_file` that path |
| points at an existing composure | `read_composure` that path, full text |
| says "the thing we were just talking about" | use the conversation, and say which parts you took |

A brain dump is usually messy: repetition, contradictions, three versions of
the same idea, asides. That is normal material. Do not clean it up before
structuring it — structure it, and let the gaps show.

---

## The outline grammar — exact

`composure_from_outline` parses markdown. It accepts only this:

    # The title of the composure

    ## A group

    ### A card

    The text under a card heading is that card's body.
    It can run to several paragraphs.

    ### Another card

    - A top-level list item under a group is also a card.
    - Its body is the indented lines beneath it.

    ## Another group

    ### [gap: what is this card's question?]

Four rules, and nothing else:

1. **One `#` line** — the composure title. Put it first.
2. **Each `##` is a group.** A group is a column (scaffold form) or a row
   (cards form). Give it a short noun name: `Act two`, `The counter-case`,
   `Phase 3 — migration`.
3. **Each `###`, and each top-level list item under a group, is a card.**
   Everything beneath it until the next heading or item is its body.
4. **A card whose text starts with `[gap`** is tinted orange and titled
   "gap". Write it as `[gap: the question you cannot answer yet]`.

Use `###` when a card has a real body. Use list items for a run of short
beats. Do not mix both inside one group unless the group genuinely has both.

Nothing else is parsed. No `####`, no tables, no nested groups, no front
matter. Bold, italics and links inside a card body are fine.

---

## Forms

| Form | Layout | Reach for it when |
|---|---|---|
| `scaffold` | Groups become **columns**, left to right. Each column gets a header card and its cards stacked below. | The thing has an order: acts, sections, phases, chapters. This is the default. |
| `cards` | Groups become **rows** of a grid. | The thing is a set, not a sequence: characters, options, sources, open questions. |
| `blank` | One full-page module holding the whole outline as rich text. | The user wants a document, not a board. Rare from this skill. |

Two names get special treatment in the `scaffold` form, so use them when they
fit:

- A group named **premise**, **logline** or **thesis** spans the top, above
  the columns. Put the one-sentence version of the whole thing there.
- A group named **ending**, **endings**, **denouement** or **resolution**
  forms the bottom row, under the columns.

If neither fits the material, do not force them. A plan has no denouement.

---

## The two questions

Ask at most two, and only when the answer changes the outline. Good ones:

- "Is this a story, an argument, or a plan?" — when the dump could be any.
- "Where does it end?" — when there is no ending anywhere in the material.
- "Is this one piece or a series?" — when the scope keeps doubling.
- "Who reads this?" — when the shape depends on the reader (a talk and a
  memo hold the same argument differently).

Do not ask about anything you can decide yourself. Do not ask the user to
fill a hole — that is what a gap card is for. If you have two questions and
one of them is weaker, ask the strong one alone.

---

## The gap rule

**Never invent material to fill a hole.** If the brain dump does not say how
she gets out of the locked room, the outline does not say either. Write:

    ### [gap: how does she get out of the room?]

    Everything after this beat assumes she is outside. Nothing in the notes
    says how.

A gap card is a service, not a failure. The orange card is the most useful
thing on the canvas — it is the writer's own question, handed back to them in
the one place where they can see what depends on it.

Write a gap card when:

- a transition is asserted but never shown,
- a claim is made with no grounds in the material,
- a phase depends on something nobody has named,
- the material contradicts itself and you cannot tell which version is live,
- an ending is implied but never stated.

Aim for honesty, not coverage. Three real gaps beat eleven nitpicks.

---

## The tool call

One call, at the end:

    <tool name="composure_from_outline">
    <title>The Lighthouse Keeper's Daughter</title>
    <form>scaffold</form>
    <content>
    # The Lighthouse Keeper's Daughter

    ## Premise

    ### Logline

    A girl who has never left an island inherits the one job that keeps her
    on it.

    ## Act one

    ### The storm takes the boat

    Her father's boat goes out in weather he has read wrong for the first
    time in thirty years.
    </content>
    </tool>

`title` is what the composure is called. `form` is `scaffold`, `cards` or
`blank`. `content` is the whole outline, exactly as written above — the same
`#` title line goes inside it.

enough creates the composure and opens it. The cards arrive already placed;
the user moves them.

---

## After the call

Say three things, briefly:

1. **What it made** — "Twelve cards across four columns, plus the premise."
2. **Where the gaps are** — name each gap card in one line.
3. **What you could not place** — material in the dump that did not become a
   card, and why. ("Two paragraphs about her mother didn't attach to any
   beat — they may be a thread rather than a scene. Say the word and I'll
   add a continuity column.")

Then stop. The user reads the canvas and tells you what to move.

---

## When the user comes back

Re-scaffolding is normal. If they want the structure changed, write a new
outline and call `composure_from_outline` again with a new title, or edit the
existing composure's cards with the composure tools when the change is small.
Do not silently overwrite a composure the user has been working in.

---

## The shapes

`references/structure.md` holds the vocabulary: arcs and beats, continuity
threads, denouements and endings, and the non-fiction equivalents (argument
and plan). It also holds two complete worked examples — a story and an
essay — each from brain dump to finished outline.

Read it when the material's shape is not obvious to you, when you are about
to name groups, or when the user asks what a beat or a thread is. You do not
need it for a simple re-run.

---

## Boundaries

- **Structure only.** This skill does not draft prose, dialogue, or argument.
  A card body is a note to the writer, not a paragraph of the finished piece.
- **Nothing invented.** Every card traces to something in the brain dump, or
  it is a gap card.
- **The user's own words.** Where the dump has a good phrase, keep it in the
  card body. Their language is the best label for their own material.
- **One composure per pass.** Do not fan a brain dump out into three
  composures because it has three threads. Make one, with a column per
  thread.
- **Not a council.** If the user wants several readvisors to argue about the
  structure, that is a council composure, not this skill.

---
enough-tooltip-text: "scaffold takes a pile of notes, a brain dump, or a half-finished idea and lays it out as a composure you can see — a card for every beat, section or phase, and an orange card wherever the structure still has a hole."
