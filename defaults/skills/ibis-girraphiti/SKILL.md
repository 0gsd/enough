---
name: ibis-girraphiti
description: "IBIS discipline for girraphs — structured mapping of contested, fuzzy, or wicked problems as issues (❓), positions (💡), and arguments (➕/➖) in a .girraph file, BEFORE any solving happens. Engage when the user wants to map a problem, untangle a decision with no clean answer, see the shape of a disagreement, or says 'girraph this', 'map this out', 'help me think through (not solve) X', 'what are the positions on Y', 'IBIS', 'argument map'. Also engage when a planning conversation keeps circling — competing considerations that won't linearize are a map smell. Do NOT engage for problems with a known procedure (use a request file), linear plans (use text-planning), or simple either/or questions the user just wants answered."
---

# ibis-girraphiti

IBIS (Issue-Based Information Systems) is a 1970s-vintage discipline for
mapping *wicked problems* — problems where the framing is part of the
fight, every stakeholder sees a different problem, and there is no
stopping rule. This skill teaches you to build that map as a **girraph**
(pronounced "graph"; the *ir* is for iterative/recursive) using the
girraph tools (`read_girraph`, `add_node`, `update_node`, `link_nodes`,
`remove_node`).

The product of this skill is a *confirmed map*, not a solution.

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

*Map the disagreement. Confirm the map. Only then solve.*

---
enough-tooltip-text: "use ibis-girraphiti to map hard, fuzzy, or contested problems as an editable issue/position/argument girraph before trying to solve them."
