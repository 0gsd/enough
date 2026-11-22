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

The state (`../state.md`) is how a scaffold moves between harnesses. In
enough both doors are the person's: two items under "the state file" in
the scaffold's menu (the export button in the scaffold's group). You never
press them for the person, and no tool of yours takes a state in.

- **Out of enough:** "take the state out (.scaffold.md)" writes the
  scaffold's state beside the composure as a new file
  (`<name>.scaffold.md`, then `<name>-2.scaffold.md` …), never over one.
  It is what `scripts/scaffold_state.py` writes from the same scaffold, byte
  for byte: the layout, the person's words, the `written` marks, the
  version, the lock and the findings. It works on a locked scaffold too.
  Hand that file to the next harness.
- **Into enough:** the person makes a fresh scaffold (or opens one), presses
  "bring a state in…" and picks the state file. enough reads it with the
  same parser and refuses, with a sentence, a file that does not read, a
  plectrum (it has no words), a state for another thing than the scaffold
  makes once that scaffold holds words, and a locked scaffold. It then says
  what it would bring: how many of the state's boxes the scaffold has, how
  many are new, how many of the scaffold's boxes get no words from it. On
  the person's yes, the layout and the words come in as the person's own
  change, one step that undo takes back. Words already in a box are never
  written over unless the person is shown those boxes and says to; "keep my
  words" keeps them. Who wrote each plec comes as the file says. A locked
  state comes in locked, with its findings and when it was checked (nothing
  lost), and is then changed only by unlocking, as any locked scaffold. A
  picture does not travel: its path was the other harness's, so the person
  puts it in again.
- Tell the person which file to bring and that the button is theirs. If
  enough refused the file, say what the refusal said.

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
  files findings only in a state (`../lock.md`); when the person brings that
  state into a scaffold that has no findings of its own, they come with it.
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
through enough's own code). Then, the same day, with the two doors: that
deck's state brought into a fresh scaffold through "bring a state in…"
(the 7 written boxes in their places, undo and redo, "keep my words" on a
box the person had changed), taken out through "take the state out" byte
for byte the file that came in, and its locked final state brought in
locked with its 8 findings.
