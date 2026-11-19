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
- The plectrum lives beside it as `<name>.plectrum.md`, rewritten by the
  tool each time.
- The state (`../state.md`) is what enough gives when the scaffold leaves,
  and what it takes when one arrives.

## Carrying a scaffold in and out

- **Out of enough:** a composure gives back its state (`../state.md`), the
  person's words included. Any engine on the index page takes it from there
  (`scripts/export.py fill` puts it into a page).
- **Into enough:** give enough the plectrum (`scripts/scaffold_state.py
  plectrum FILE` takes it out of a state) and call `scaffold_from_plectrum`;
  it builds the boxes. The person's words travel in the state file, and the
  tool never writes them into a box: the words come in by the person's own
  hand, or by a step of enough's own page that the person takes. Never by
  the readvisor.

## Lock, check, export

enough locks, checks and exports from its own page and jobs. The procedure
is the one in `../lock.md`: one lock for the whole; findings by box, each
proposed and accepted or declined by the person; "cannot be checked" is
final; unlocking makes a new version. enough's exports are the same
formats `scripts/export.py` makes, from enough's own tools.

## Tried

Not tried as the cross-harness route yet (see the index's table).
