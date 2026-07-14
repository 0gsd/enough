---
name: girraph-merirmaid
description: "Two sibling visualization jobs in one skill. GIRRAPH — IBIS discipline for mapping contested, fuzzy, or wicked problems as issues (❓), positions (💡), and arguments (➕/➖) in a .girraph file, BEFORE any solving happens; engage when the user wants to map a problem, untangle a decision with no clean answer, see the shape of a disagreement, or says 'girraph this', 'map this out', 'help me think through (not solve) X', 'what are the positions on Y', 'IBIS', 'argument map'. MERIRMAID — generate, display, and edit Mermaid diagrams in .merirmaid files for ANYTHING with structure or flow; engage when the user says 'diagram this', 'flowchart', 'mermaid', 'sequence diagram', 'state diagram', 'visualize this process', 'draw the architecture', 'show how X works', 'chart the steps'. Also engage when a planning conversation keeps circling — competing considerations that won't linearize are a girraph smell; a described-but-unpictured process or structure is a merirmaid smell. Do NOT engage for problems with a known procedure (use a request file), linear plans (use text-planning), or simple either/or questions the user just wants answered."
---

# girraph-merirmaid

Two sibling jobs, one skill, both about turning something the user is
holding in their head into an editable picture on disk:

- **girraph** — *argue*. Map a contested, fuzzy, or wicked problem as an
  IBIS issue/position/argument graph in a `.girraph` file. The product
  is a *confirmed map*, not a solution. This half is unchanged discipline;
  it lives in the first part of this file.
- **merirmaid** — *depict*. Draw a structure, flow, interaction, or
  lifecycle as a Mermaid diagram in a `.merirmaid` file, rendered live
  in the browser. The product is a *diagram the user can read and edit*.
  This half lives in the second part.

## Which one to reach for

| The user wants to… | Use | Why |
|---|---|---|
| Untangle a question with no clean answer; see who believes what and why | **.girraph** | Contested framing, competing positions, arguments — that's IBIS. |
| Picture how something is put together, or how a process/interaction/lifecycle flows | **.merirmaid** | Structure and flow are Mermaid's job; there's a right answer to depict, not a debate to map. |

Rule of thumb: if the honest first move is *asking a question* (what's
really at issue here?), it's a girraph. If the honest first move is
*drawing a box-and-arrow* (here's how the pieces connect), it's a
merirmaid. When both apply — a contested decision *and* a system to
picture — they can coexist: map the argument in a `.girraph`, depict the
mechanism in a `.merirmaid`, and cross-link them (see linking, below).

---

# Part 1 — girraph (IBIS mapping)

IBIS (Issue-Based Information Systems) is a 1970s-vintage discipline for
mapping *wicked problems* — problems where the framing is part of the
fight, every stakeholder sees a different problem, and there is no
stopping rule. This skill teaches you to build that map as a **girraph**
(pronounced "graph"; the *ir* is for iterative/recursive) using the
girraph tools (`read_girraph`, `add_node`, `update_node`, `link_nodes`,
`remove_node`).

The product of this half is a *confirmed map*, not a solution.

---

## Node discipline — what goes where

- **Issue (`?` ❓)** — a genuine open question, phrased as a question.
  Not "the database problem" but "How should we store user data?".
  If you can't phrase it as a question, it isn't an issue yet.
- **Position (`!` 💡)** — one possible answer to exactly one issue.
  A position responds to its parent issue; if it answers a different
  question, you've discovered a new issue — add that first.
- **Argument (`+` ➕ / `-` ➖)** — supports or objects to exactly one
  position. Arguments attach to positions, not to issues. An argument
  that cuts across several positions gets one node plus `link_nodes`
  cross-edges to the others.
- **Note (`.` 📄)** — context that is none of the above: background
  reading (`ref:` a doc), constraints, definitions, data points.
- **Nested girraph (`@` 🦒)** — when a sub-question grows its own
  positions-and-arguments thicket (rule of thumb: ~7+ descendants, or
  the sub-debate has different stakeholders), split it into its own
  `.girraph` file and link it with an `@` node. Recursion is the
  feature; don't let one file become a wall.

## Anti-solution-jumping (the prime directive)

Never propose interventions, resolutions, recommendations, or "so what
we should do is…" while the map is unconfirmed. The temptation is
strongest exactly when it's most damaging — early, when the framing is
still the user's biggest unknown. Record positions *as positions on the
map*, including your own if asked, and keep mapping. If the user asks
you to just solve it, say plainly: *"Happy to — want me to finish the
map first so we're solving the right problem? It's close."* If they
still want the answer, give it; they're the boss. But never drift into
solving on your own initiative.

## The stopping rule

Wicked problems have no natural stopping point — that's what makes them
wicked. The imposed rule: **the map is done when the user says it's
done.** Offer a readiness check when the map stabilizes (no new nodes
in a few exchanges): *"Does this map capture the problem as you see
it? Anything missing or mis-framed?"* The user's confirmation is the
finish line. After confirmation — and only then — solving can begin,
in whatever paradigm fits.

## Mapping etiquette

- **One question per turn.** Mapping is an interview, not a download.
  Ask the single question whose answer would most reshape the map.
- **Challenge vs record.** Default to recording the user's framing in
  their own words (`by:user`). Challenge it when (a) two of their
  claims conflict, (b) a stated issue smuggles in a position ("How do
  we ship the plugin API?" assumes shipping), or (c) the same words
  carry two meanings in different branches. Challenge by asking, not
  asserting — and if they hold, record their framing and move on.
- **Re-read before you write.** The user has an editable panel for the
  same file. Start girraph turns with `read_girraph` on the working
  branch; never assume the map is as you left it.
- **Depth etiquette.** Read the branch you're working, not the world.
  Default depth, expand on demand. After a context reset, the girraph
  IS your checkpoint — one `read_girraph` re-orients you.

## Attribution (`by:`) — cheap now, load-bearing later

Every position and argument gets a `by:`: `user`, `agent`, or a role
slug. This is what keeps "whose claim is this?" answerable months
later, and it's the hook for stakeholder-role workflows — when roles
(or future synthesized stakeholders) weigh in, their nodes carry their
name, and a glance shows which voices have and haven't been heard on
each position. Never relabel someone else's claim as your own; if you
sharpen the user's wording, the node is still `by:user`.

## Starting a map

1. Confirm the root issue with the user, phrased as a question.
2. `add_node` with no parent — file created, label becomes title.
   Default location: `<slug>.girraph` at the project root (or where
   the user says).
3. Map breadth-first: the user's known positions first, then arguments,
   then the issues those arguments expose.

## With text-planning

When the `text-planning` paradigm is active and this skill is enabled,
plan *structure* (the contested shape of the thing — what it's arguing,
what belongs in/out, order-of-battle questions) lives in a girraph at
the project root; the prose plan document stays the home for settled
decisions. Map first, settle into the plan after confirmation.

---

# Part 2 — merirmaid (Mermaid diagrams)

A **merirmaid** (pronounced "mermaid"; the *ir* is the same
iterative/recursive joke as girraph) is enough's flavor of a Mermaid
diagram: plain Mermaid source wrapped in a small frontmatter header,
saved as a `.merirmaid` file and rendered to SVG **live in the browser**
by a vendored Mermaid v11 (`enough/static/mermaid.min.js`, no CDN).
Plain text is the source of truth — a `.merirmaid` is never a stored
image.

Use this whenever the user wants to *see* a structure or flow: an
architecture, a process, an interaction, a lifecycle, a data model, a
schedule, a breakdown. If they described a system in words and would
grasp it faster as boxes and arrows, offer to draw it.

## The file format

UTF-8 text. `key: value` frontmatter between `---` fences (first thing
in the file), then verbatim Mermaid source:

```
---
merirmaid: 1
title: How the broker gates a tool call
modality: wip
node-char-limit: 48
---
flowchart TD
  A[tool call] --> B{broker toggle on?}
  B -- yes --> C[runner executes]
  B -- no --> D[canned denial]
```

Frontmatter keys:

- `merirmaid: 1` — **required**, the format version.
- `title` — **required**, a human-readable name shown in the viewer
  toolbar.
- `modality` — **required**, either `wip` or `mirror` (see below).
- `node-char-limit` — optional soft per-node-label limit the in-viewer
  editor surfaces (defaults to 48). Not a hard cap.
- Unknown keys are preserved, so leave ones you don't recognize alone.

Everything after the closing `---` fence is verbatim Mermaid source of
any diagram type Mermaid v11 supports.

## Modality — `wip` vs `mirror` (know the difference)

- **`wip`** — a working diagram / brainstorming whiteboard. This is what
  you create when the user asks you to diagram something. Node *text* is
  user-editable in the viewer; structure edits come through you via chat.
  Whole-file `write_file` is allowed for these.
- **`mirror`** — a source-of-truth diagram that mirrors some external
  structure. It is **read-only** and owned by whatever backend generates
  it. **Never hand-write or edit a `mirror` file.** The launch example is
  the auto-generated `_cachebox.merirmaid` files that mirror a cachebox's
  contents under `~/enough/cacheawl/`: a backend module owns those and
  regenerates them on every change. If a user asks you to "fix" or "tidy"
  a mirror diagram, don't — explain that it reflects the actual structure
  and the way to change the picture is to change the thing it mirrors
  (e.g. the cachebox contents). `write_file` on a mirror file under
  `~/enough/cacheawl/` is refused by the broker anyway; don't try to
  route around it.

Create `modality: wip` for everything you author. Only ever *read*
`mirror` files.

## Generation rules (match the renderer and leave editing room)

Pick the diagram type from what's being depicted:

- **Structures, decision flows, dependency maps → `flowchart TD`** (top-
  down) — the default. Reach for it unless another type clearly fits
  better; it's the format users read and edit most fluently. Use `LR`
  (left-right) only when the flow is naturally horizontal.
- **Interactions / message-passing between actors over time →
  `sequenceDiagram`.**
- **Lifecycles / state machines / mode transitions → `stateDiagram-v2`.**
- **Data/type models, schemas as objects → `classDiagram`.**
- **Database/domain entities and relationships → `erDiagram`.**
- **Schedules/timelines with dates → `gantt`; simple proportion
  breakdowns → `pie`; loose radiating brainstorms → `mindmap`.**

Full syntax for each type is vendored in `references/` — read the page
for the type you're about to write rather than reconstructing syntax
from memory. `references/README.md` indexes them.

Label rules:

- **Keep node labels ≤ ~32 characters.** The format's soft limit is
  `node-char-limit: 48`, but generate well under it: users edit node
  text in the viewer and need headroom to expand a label without
  immediately tripping the warning. Short labels also render cleaner.
  Put detail in the surrounding structure, not in one giant node.
- **Quote any label containing special characters** — parentheses,
  colons, `#`, quotes, brackets, or a leading `o`/`x`. In flowcharts,
  wrap the text: `A["read_file (gated)"]`. Unquoted punctuation is the
  #1 cause of Mermaid parse errors.
- Avoid the bare word `end` as flowchart node text (capitalize it or
  reword) — lowercase `end` breaks flowchart parsing.

## Linking diagrams as nodes (breadcrumb navigation)

To make one diagram a drill-down from a node in another, use a Mermaid
`click` interaction with a **relative path**:

```
click NODE "subsystem/details.merirmaid"
```

The viewer intercepts these clicks and pushes the target onto a
breadcrumb stack — the same navigation pattern as girraph mode's `@`
refs. Targets may be `.merirmaid`, `.girraph`, or `.md` paths. This is
how you keep any single diagram small: when a node deserves its own
diagram, give it one and `click`-link it rather than cramming everything
into one wall. A `.merirmaid` flowchart node can even link to a
`.girraph` when the sub-topic is contested rather than structural —
that's how the two halves of this skill connect.

## Editing etiquette

`.merirmaid` files are plain text with no special tools:

- **Read** with `read_file`.
- **Rewrite** with `write_file` (whole-file writes are allowed for `wip`
  files — there are no broker-assigned IDs to protect, unlike
  `.girraph`).
- **Re-read before you rewrite.** Users edit node *text* directly in the
  viewer, so the on-disk source may have changed since you last wrote
  it. Always `read_file` at the start of an edit turn and rewrite from
  what's actually there — never from your memory of the last version, or
  you'll clobber the user's label edits.
- If a diagram fails to render, the viewer shows the Mermaid error plus
  the raw source. Read the source, fix the syntax (usually an unquoted
  label — see above), and rewrite.

## Worked example

A `wip` merirmaid depicting how enough routes a chat turn between the
local model and the cloud slot, with one node linking off to a deeper
diagram:

```
---
merirmaid: 1
title: Chat turn routing
modality: wip
node-char-limit: 48
---
flowchart TD
  U[user message] --> A[assemble system prompt]
  A --> R{active model?}
  R -- local --> L[llama-server stream]
  R -- opro-api --> C[cloud stream]
  L --> T{tool call?}
  C --> T
  T -- yes --> X[run tool via broker]
  X --> A
  T -- no --> E[end turn]
  click X "broker-gating.merirmaid"
```

Every node label is short, decision nodes use `{…}`, no label needs
quoting, and the `click` turns "run tool via broker" into a drill-down
to a broker-gating diagram. This parses against the `.merirmaid`
frontmatter rules: `merirmaid: 1`, `title`, and `modality: wip` are all
present and the body is valid Mermaid.

---

*Map the disagreement, confirm the map, only then solve — or draw the
structure so it can finally be seen. Read before you write, either way.*

---
enough-tooltip-text: "use girraph-merirmaid to map hard, fuzzy, or contested problems as an editable issue/position/argument girraph, or to draw structures and processes as editable Mermaid diagrams in .merirmaid files."
