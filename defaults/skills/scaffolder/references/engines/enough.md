# Engine: enough's composure

In enough the scaffold is a composure, and `SKILL.md` is the whole of what
you need: count the plectrum, call `scaffold_from_plectrum`, change it by
calling the tool again with the same `<path>`. This page is for a harness
that meets a scaffold made in enough, or hands one to it.

**The rule: you never write into a plecholder's field.** In enough the tool
refuses a readvisor's write to a box's text, with the reason.

## What enough keeps

- The composure is the truth for the layout and the person's text. Each
  plecholder is a `scaffold-box` module; each frame is a `frame` module; the
  order of the frames and the lock live in the composure's scaffold meta.
- A box's `as` (headline, caption, speaker …) is on the composure too:
  `scaffold_from_plectrum` sets it from the plectrum, the person can change
  it in the box's inspector, and the export follows the composure.
- The plectrum lives beside it as `<name>.plectrum.md`, rewritten by the
  tool each time.

## Carrying a scaffold in and out

The state (`../state.md`) is how a scaffold moves between harnesses. enough
does not yet read a state or give one back: no button, route or tool of
enough takes a state's words in or hands the state out. Until it does:

- **Into enough:** give enough the plectrum (`scripts/scaffold_state.py
  plectrum FILE` takes it out of a state) and call `scaffold_from_plectrum`;
  it builds the boxes, with their ids, plecs, targets and `as`. The tool
  never writes a box's text, so tell the person that their words travel by
  their own hand: they paste each box's words from the state file (the text
  under each box's `plec` block) into the same box on enough's canvas. Say
  how many boxes hold words, so they know when they are done. Marks
  (`state: written`) and findings do not come in; they mark boxes again.
- **Out of enough:** a person can export the thing in its own formats from
  the scaffold's menu, but not the state. A harness that must finish a
  scaffold begun in enough builds a fresh scaffold from the plectrum beside
  the composure (`<name>.plectrum.md`) and the person pastes their words into
  it, as above. Say plainly that this is the way until enough gives the
  state back.

## Lock, check, export

enough locks, checks and exports from its own page and jobs. The procedure
is the one in `../lock.md`: one lock for the whole; findings by box, each
proposed and accepted or declined by the person; "cannot be checked" is
final; unlocking makes a new version.

- **The check is enough's own job.** The person presses the check after the
  lock. It reads spelling with FEED (enough's dictionary), and grammar and
  truth with the model enough runs, when one answers. With no model (or
  agent-free), it says so: spelling by FEED only, each unknown word flagged
  with no fix, grammar and truth "not checked". A readvisor outside enough
  has no door to file findings into a composure; it checks a scaffold only
  where it holds the state (`../lock.md`).
- Each finding shows in the comments panel with "take the fix" and "keep my
  words"; a claim that cannot be checked shows as final, with neither.
- **Export** is in the scaffold's menu: a page as HTML and PDF, a deck as
  PPTX and PDF, a document as Markdown and PDF, each a new file beside the
  composure. Frame names, plecs, notes boxes and empty boxes never reach the
  thing; the page names what it left out.

## Tried

Tried 2026-11-22 by an agent with stand-in text: a deck begun in one HTML
file and finished here (plectrum in, words pasted by hand, lock, check with
FEED and a model, findings taken and kept one by one, PPTX and PDF); a
document begun here and finished in one HTML file (the state taken out
through enough's own code, which a harness cannot reach).
