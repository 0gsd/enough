# Girraphs

It's pronounced **"graph."** The *ir* is silent — it stands for
*iterative* and *recursive*, and yes, this is the GIF wars all over
again. We are at peace with the consequences. The animal is a 🦒 and
the animal is also silent.

## What is a girraph?

A girraph is a map of a hard question. Not a to-do list, not an
outline — a map of a *disagreement*, including the productive ones you
have with yourself.

Some problems don't behave like tasks. "Should we homeschool?" "What is
this book actually about?" "Do we take the funding?" Every answer
sprouts objections, every objection hides another question, and writing
it as a list just buries the fight. A girraph keeps the fight visible
and organized:

- ❓ **issues** — open questions, always phrased as questions
- 💡 **positions** — possible answers to an issue
- ➕ ➖ **arguments** — reasons for or against a position
- 📄 **notes** — background, constraints, reading
- 🦒 **nested girraphs** — when a sub-question gets big enough to
  deserve its own map (recursive, remember?)

This way of working has a lineage — it's called IBIS, invented in the
1970s for so-called *wicked problems*, the kind with no clean answer
and no obvious place to stop. The girraph is enough's plain-text take
on it.

## Where does it live?

In a regular text file ending in `.girraph`, right in your project.
Open one in any text editor — in 2026 or 2056 — and it reads like this:

```
%girraph 0.1
title: Should enough ship a plugin API?

q1 ? Should enough ship a plugin API?
p1 ! Ship a minimal one < q1
a1 + Ecosystem growth needs stable hooks < p1 by:graham
a2 - API surface = forever maintenance < p1 by:open-skeptic
```

One line per thought. `< q1` means "this answers q1." `by:graham`
remembers whose claim it is. No database, nothing hidden: the file is
the map.

## How do you use it?

**In the app:** click any `.girraph` file and hit the **🦒 girraph
panel** button. You get a collapsible tree you can edit directly —
click a label to rewrite it, hover a row for add/link/remove buttons,
click a 🦒 chip to descend into a nested map (breadcrumbs bring you
back), click a 📄 chip to read a referenced doc right there.

**In chat:** ask the agent to "map this out" or "girraph this." The
agent edits the same file through the same node-by-node operations you
do, so you can both work the map at once without stepping on each
other. Removing nodes always requires your confirmation.

**The discipline (optional but recommended):** enable the
`girraph-merirmaid` skill in the sidebar and the agent becomes a proper
mapping partner — one question per turn, no jumping to solutions until
*you* say the map is done. Wicked problems have no stopping rule, so
your confirmation is the stopping rule.

## Three habits that make girraphs work

1. **Phrase issues as questions.** "The money problem" is a worry;
   "How do we fund year two?" is mappable.
2. **Let arguments attach to positions, not issues.** Reasons are
   always reasons *for or against an answer*.
3. **Split before it sprawls.** When one branch grows a beard, move it
   to its own `.girraph` and link it with a 🦒 node.

That's it. It's pronounced "graph." Tell your friends, gently.
