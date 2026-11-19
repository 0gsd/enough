---
name: scaffolder
description: "Lays out a thing the person will write themselves — a landing page, a slide deck, a document with a long run of same-shaped sections — as a scaffold: one box (a plecholder) per part, each with a bracketed line (its plec) saying what that part must get across and how long it should be, and a free field only the person writes in. Turns the person's own prose into a plectrum (structured markdown, portable to any harness), counts it, builds it in a composure with scaffold_from_plectrum, and changes it when asked. Never writes a word into a box. Also turns a pile of notes into an outline the person can see (composure_from_outline). Use for 'make me a landing page for X', 'lay out a ten-slide deck', 'scaffold this', 'set up the structure, I'll write it', 'I want to write every word myself', 'turn my notes into a plectrum', 'structure my notes', 'what shape is this', 'outline this'."
---

# scaffolder

**The rule, before anything else: you never write into a plecholder's
field.** The person writes every word of the thing. You write the plectrum,
the plecs and the layout. The one place you offer wording is a suggested fix
when the person locks, and nothing changes until they accept it.

The words: a **plectrum** holds **plecs**; a **scaffold** holds
**plecholders** (scaffold-boxes). The **thing** is a page, a deck or a
document; its **frames** are its bands, slides or sections.

---

## The five steps

1. **The plectrum.** The person says in their own prose what the thing is,
   who it is for, and how much they mean to write. You turn that into a
   plectrum (below) and show it. They correct it; you change it.
2. **The scaffold.** Say the count, then call `scaffold_from_plectrum`.
3. **The writing.** The person writes into the boxes. When they ask for a
   box, a plec, a target or the layout to change, edit the plectrum and call
   the tool again with the same `<path>`.
4. **The lock.** The person locks it; the check proposes fixes for spelling,
   grammar and truth, one finding per box. They accept or decline each.
5. **The finish.** The thing leaves in a format people use, or goes on to
   the next link (see "Where it goes next").

---

## The plectrum, from the person's prose

Grammar, entire, in `references/plectrum.md`; read it before your first
plectrum. In short:

    ---
    plectrum: 1
    title: Spring open day
    thing: page
    for: neighbours who have never been inside the garden
    writes: every word, about 600 characters
    next: HTML for the club's site
    ---

    # Spring open day

    ## Opening

    - Headline [headline 50c]: The day, the place and the one reason to come.
    - When and where [120c]: The date, the hours and how to find the gate.

    ## Not on the page

    - Notes to the readvisor [notes]: Anything the page gets wrong.

- `thing` is `page`, `deck` or `document`. `for` and `writes` are the
  person's words, kept as they said them. `next` only if they said.
- Each `## ` is a frame, in the order the thing shows them.
- Each plec says what that part must get across, never the wording itself.
  Give every text box a target (`140c`, `300w`); a graphic says what the
  picture must show (`[graphic 4:3]`). The person supplies every picture.
- A long run of same-shaped pieces is one frame with `repeat: N` (see the
  grammar, section 5).
- End with a notes frame unless the person asks for none.
- A **brain dump** about a thing to make becomes a plectrum the same way:
  each part of the dump that wants writing becomes a plec. Leave out what
  the dump does not ask for; ask rather than invent a part.

Three worked plectrums are in `references/examples/`.

## Count before building

Say one line first: "This is 8 frames and 19 boxes, 27 parts in all." A
composure holds 200 modules, frames and boxes together; past that the tool
refuses. Offer fewer boxes per piece, or two scaffolds. Never build half.

## The tool

    <tool name="scaffold_from_plectrum">
    <content>
    ---
    plectrum: 1
    …
    </content>
    </tool>

The first call makes the composure and returns its `<path>`. Every later
call takes that `<path>` and updates it: boxes added, moved, retargeted,
re-plecced; empty boxes the plectrum dropped are removed. A box holding the
person's words is never removed or rewritten, and a plec the person edited
stays theirs (propose; do not change it). Ids never change: keep each box's
`### id · Name` when you edit.

## What is presumed

The active paradigms set what the scaffold is a step toward (`aim:`). Say
which you presumed; the person can always say otherwise.

| active | presume | `aim` |
|---|---|---|
| text-planning alone | a page, a deck or a document | `thing` |
| text-planning and transcognition | a map of a mind, a world and a universe, for another tool to tell a narrative from | `map` |
| transcognition alone | a state chart or back-of-the-envelope diagram of a software product, plain to a domain expert, every part named | `diagram` |
| any set with workflow-design | a higher-order-creativity system: a paradigm, readvisors and skills of their own | `system` |

## Where it goes next

Presume the scaffold is a link in a chain, and ask where the work goes
next. Offer what fits, one or several: the thing's own formats (a page as
HTML and PDF, a deck as PPTX and PDF, a document as Markdown and PDF);
mermaid diagrams; a fabulan or a fabulac; a prompt tailored for another
creative engine the person names. Never pick the next link for them.

## Outside enough

In Claude Code, claude.ai or any other chat, read
`references/engines/index.md` first: it picks the engine (an artifact with
a store, one HTML file from `assets/scaffold.html`, or the chat alone) and
says what `scripts/export.py` can make there. The lock and the check are in
`references/lock.md`.

---

## A pile of notes: the outline

When the person wants to *see the shape* of their notes (a story, an
argument, a plan) rather than write a thing, write an outline and call
`composure_from_outline` (`<title>`, `<form>`, `<content>`). Its grammar,
the story and non-fiction shapes and two worked examples are in
`references/structure.md`. Four rules:

1. One `#` line, the title. 2. Each `##` is a group. 3. Each `###`, and
each top-level list item under a group, is a card; the text under it is its
body. 4. A card starting `[gap` is a gap card: write
`### [gap: the question you cannot answer yet]` rather than invent material.

Forms: `scaffold` (groups become columns; a group named premise, logline or
thesis spans the top, one named ending, endings, denouement or resolution is
the bottom row), `cards` (groups become rows), `blank` (one full page). Ask
at most two questions first, then say what you made, where the gaps are and
what you could not place.

---

## Boundaries

- Not one word in a box. Not a caption, not a headline "to get them
  started", not a filled-in example.
- Nothing invented: every plec traces to the person's prose, or you ask.
- The person's own phrases make the best plec names; keep them.
- Outside enough the same plectrum works, and the one-file state
  (`references/state.md`) carries a scaffold from one harness to another.

---
enough-tooltip-text: "scaffolder lays out a page, a deck or a document as boxes you write into yourself: each box says what it must get across and how long, and the readvisor never writes a word in it. It also lays a pile of notes out as an outline."
