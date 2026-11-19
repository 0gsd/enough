# Engine: the chat alone

Use this when the harness can show no page at all. The scaffold lives in
the conversation: the plectrum is the layout, and the person writes each
box's words in turn. At the end you hold the whole state as one markdown
file, which any other engine can pick up.

**The rule: you never write into a plecholder's field.** In a chat this is
easy to break by accident. Do not "start them off", do not offer a sample
sentence, do not tidy their words when you write the state. What they send
for a box is that box's text, as they sent it.

## The turns

1. **The plectrum.** As everywhere (`SKILL.md`): their prose in, the
   plectrum out, read back and corrected. Say the count line.
2. **The scaffold, shown.** Show the frames and boxes as a short list: each
   box's id, name, target and plec in brackets. Ask whether to go box by
   box in order, or whether they will name the box they are writing.
3. **The writing.** For each box, show its name, its plec in brackets and
   its target, then wait. Their reply is the box's text. Say the count
   against the target in one line ("142 of 140 characters, 2 over"); never
   suggest what to cut. If they ask to change a box, a plec, a target or the
   order, change the plectrum and say what changed.
4. **Keep the state.** After every few boxes, and whenever they ask, give
   the whole state as one markdown block (`../state.md`), so nothing is
   lost if the conversation ends. When the harness can run Python,
   `scripts/scaffold_state.py write` makes the writer's own form.
5. **The lock.** When they say it is done, set `locked`, run the check
   (`../lock.md`) and show the findings box by box: the quoted words, the
   fix, why. They answer each one; you change the quoted words only for the
   ones they accept, and give the state again.
6. **The finish.** Ask where the work goes next. Without scripts, a
   document's Markdown and a page's HTML can be written straight from the
   state, the person's words exactly as written; say that a PDF comes from
   printing the HTML, and a deck's PPTX needs a harness that runs the
   script, or enough.

## Moving on

The state is the hand-off. Pasted into a harness with a page, it becomes a
page (`export.py fill`); given to enough, it becomes a composure.

## Tried

Not tried (see the index's table).
