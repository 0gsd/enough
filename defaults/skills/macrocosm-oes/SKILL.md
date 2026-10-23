---
name: macrocosm-oes
description: Reads, checks and explains MacroCOSM `.cosm` files — Comprise Holotypes, Canon catalogs, standalone COSM product trees and EMF twins — and, only when the user asks, decompiles a text into its EMF twin or writes its atem, the tightest fair, full, plain reduction of a text. Use for "what is this .cosm file", "read this Holotype", "explain this Holotype", "what does the Holotype say about X", "lint this .cosm", "check this .cosm", "decompile this text", "enumerate this document", "make an EMF twin", "make an atem of this", "summarize this tightly", "say it in one line", "what is MacroCOSM", "what is EMF", "what is an atem", "what does this stance mean". Not for an ordinary summary in the user's own terms (answer that directly), not for editing a Holotype's content (that is Comprise's work), and not for writing new .cosm volumes by hand.
---

# macrocosm-oes

**MacroCOSM OES** is the shared grammar every MiniCOSM is written in. A domain
is enumerated as plain-text `.cosm` files (a restricted YAML subset) that are
at once a file system and a relational database, made to be rendered. A
**volume** is a folder or one file whose **catalog** declares the MiniCOSM it
speaks (`oes: emf/1`), and its **items** are rows with a stable `id`
(`P:claim/apples-need-a-second-variety`) and a `type`. Items point at each
other by id, as fields and typed links `{rel, to}`, and every item carries the
same envelope: name, summary, status, visibility, provenance. A value nobody
has given yet is an **open question**, `{pending: "the question"}`, never a
guess.

## The four MiniCOSMs enough ships

| MiniCOSM | Declaration | A volume is | Modules |
|---|---|---|---|
| `comprise` | `oes: comprise/1` | a Holotype: one company, a folder with `holotype.cosm` | C O M P R I S E |
| `cosm` | `cosm: 0.2` or `0.3` | a standalone product tree: brand, suites, offerings | P |
| `canon` | `oes: canon/1` | a Canon volume's or a project's catalog, `canon.cosm`, kept by enough | V |
| `emf` | `oes: emf/1` | a text's EMF twin, `notes.md.cosm` beside `notes.md` | L E K P T X |

**EMF** (*enumerated meaning fabula*; "the fabula") takes a text apart: L terms
grounded in FEED, E entities, K concepts, P claims, T events in order, X atems.

## The six stances

Every EMF claim says how the text knows it:

- `axiom` — given, or true by definition; the text does not argue for it
- `observed` — seen, measured or done at first hand
- `deduced` — reasoned from the text's other claims
- `opinion` — a judgement or preference of the author's
- `assumed` — relied on without being stated as a premise
- `hearsay` — reported from someone else, who fills the claim's `source`

## The atem

An **atem** is the tightest fair, full, plain-English reduction of a text or a
passage. It has four parts:

- **line** — one sentence of 15–25 words that says what the whole says:
  *fair* (the author would accept it), *full* (nothing the text depends on is
  missing), *plain* (everyday words). "The atem" in prose means the line.
- **focus** — what is happening: what the author directs attention to.
- **push** — what the author wants the reader to take away.
- **pull** — what the reader should actually take away, naming hidden
  assumptions and dependencies.

Push is the author's side and pull the reader's. Where they differ is the most
useful thing an atem shows.

## When to make one

- **Decompile only when asked.** An EMF twin is made when the user asks for
  one ("decompile", "enumerate", "make a twin"), never on your own initiative
  and never as a side step of another task.
- **An atem is often enough.** For the gist, the point, a one-line summary, or
  "what is this really saying", make an atem, not a twin: `<text>` for a
  passage the user pasted, `<path>` to write a file's atem into its twin.
- **Without a model** both tools write a labelled **scaffold**: terms and
  names, the first sentence as the line, push and pull left open. Say it is a
  scaffold; never present it as a reading.
- **Long texts.** In a chat turn `emf_derive` gives a model texts of up to
  about 6,000 characters; a longer one gets the scaffold, because a full model
  pass belongs in the reader's decompile, which runs in the background. Say
  so. Both tools refuse texts over about 24,000 characters.
- **Shorts.** "compile a short" in the reader turns an EMF twin (the fabula)
  back into prose, a new `<text>.short-<date>.md` beside the text: *told*
  follows the author's order by span, *by weight* puts the weightiest claims
  first; you have no tool for it, so point the user at that button.

## Reading a Holotype

A Holotype describes one company at a moment: a folder of concerns, each with
eight modules (Corporation, Organizations, Markets, Products,
Representations, Inventories, Stacks, Employees).

- **People are never in files.** Employees live only in Comprise's sealed
  local database; the E module holds a README or a `none` note instead. Never
  infer or invent the people of a company.
- **Open questions are pending.** Report each as a question, with the item
  that holds it. Never answer one with a guess.
- **Browsed, not decompiled.** No EMF twins or atems of a Holotype's files.
- enough runs the generic checks only. Comprise's own rules show as "not run":
  that is not a failure.
- Quote ids and paths as the tools give them; an item's `provenance` says
  where each fact came from.

## The tools, in order

Their tags are in the Tools section. With this skill switched off, this guide
is one `cosm_guide` call away.

1. `cosm_read` — the volume's tree, cut to fit with "(N more)" markers, or one
   item's fields with `<item>`. Start here.
2. `cosm_lint` — the checks: errors, warnings, notes, open questions.
3. `emf_derive` (a text → its EMF twin) or `atem` (the four parts, written
   into the twin; an inline `<text>` writes nothing) — only on request.

Then `cosm_read` the twin to talk about what it holds. Writing into the Canon
store (`canon:` paths) needs the broker's canon tools switched on.

## More

The full specification is `docs/MACROCOSM_OES.md` in enough, which the user
can open in the app as the MacroCOSM spec viewer. `references/README.md` says
where the spec and the four manifests live.

MacroCOSM OES © 2026 Graham Smith; see defaults/cosm/NOTICE.md

---
enough-tooltip-text: "use macrocosm-oes to read and check .cosm files — Holotypes, Canon catalogs, EMF twins — and, when you ask, to decompile a text into its EMF twin or make its atem."
