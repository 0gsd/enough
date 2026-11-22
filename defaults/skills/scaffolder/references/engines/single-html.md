# Engine: one self-contained HTML file

Use this when the harness can show or save an HTML page but the page has no
store of its own: a preview pane, a file the person opens in their browser.
The page saves in the person's browser and has a button that copies
everything out, as one markdown file, for you to read.

**The rule: you never write into a plecholder's field.** You never put the
person's words into the JSON block either: the words in it are only ever
the ones the person copied out to you, carried back unchanged.

## Build it

1. The plectrum first, read back and corrected; say the count line.
2. `python3 scripts/export.py fill PLECTRUM.md` writes `<slug>.scaffold.html`
   beside it (a new file; it never overwrites). Without Python, copy
   `assets/scaffold.html` and replace its JSON block's content as below.
3. Give the person the file, or show it in the harness's preview. It loads
   nothing from any network and uses the system's own fonts.

## The data contract

The page reads one block, and only one:

```html
<script type="application/json" id="scaffold">{ … }</script>
```

- Its content is a scaffold's state, or a plectrum, as JSON in the shape
  `../state.md` gives "for a program" (`scaffold_state.py json FILE`):
  `{"scaffold": 1, "meta": {…}, "frames": [{…, "boxes": [{…}]}], "findings": […]}`.
  A plectrum (`"plectrum": 1`) opens as version 1 of a new scaffold.
- Every `<` inside the block is written `<`, so nothing in the
  person's words can close the block early. `export.py fill` does this.
- `null` (the template's own content) shows "No scaffold in this page yet".
- Nothing else in the file changes. A harness that edits anything else is
  no longer using this template.

## What the page keeps, and where

| key in `localStorage` | holds |
|---|---|
| `scaffold:<title slug>:plec:<box id>` | the person's words in that box, as they type |
| `scaffold:<title slug>:state` | the whole model with its layout changes and lock, and the hash of the block it grew from |
| `scaffold:<title slug>:v<N>` | version N as it was locked, kept at unlock |

The page takes its block first. A saved layout is used only if it grew from
the same block; a block you rewrote (a new plectrum) wins, and the person's
words come back box by box by id. Every read and write is guarded: in a
private window, or with storage blocked, the page still works and says that
nothing is kept.

## What the page does

- Frames as the thing shows them: a page's bands, a deck's slides at 16:9
  (speaker notes under each), a document's sections, with "+ another like
  this" on a repeated section.
- Each plecholder: its name, its plec in brackets, the target with a live
  count (characters or words), and its state: empty, draft, written (the
  person marked it), over the target, or locked. Fixed parts in grey; chips.
- A graphic box: the picture's shape and "the person supplies it", a place
  for where the picture is, and a caption field.
- A notes box, which is never part of the thing.
- "+ scaffold-box" in every frame and "+ page" (or "+ slide"): the person
  adds parts; a plec they write or change is theirs (`plec-by: person`).
- "Read it as the page / deck / document": the reading view.
- "Lock": one lock for the whole (`../lock.md`). Locked, it is read-only,
  except that the person may accept or decline each finding. "Unlock" makes
  the next version and keeps the locked one.
- "Copy everything out": the whole state as one markdown file, to the
  clipboard when the browser allows, and always shown selected, with
  "Save as a file".

## Change it, check it, finish it

Ask the person to copy everything out and paste it to you. That text is the
state: read it with `scaffold_state.py`, change the plectrum as asked, run
the check at lock (`../lock.md`), and write the new state. Fill a new page
from it (`export.py fill`) and give it to the person; their words are in
the state and in their browser.

The lock and the check, in turns:

1. The person presses "Lock", then "Lock now". The page names the empty
   boxes first. Then they copy everything out and paste it to you. Its
   `locked:` has a time; if it has none, they have not locked it.
2. You run the check (`../lock.md`) on that text and write `checked:` and
   the findings under `# Findings`, each `status: open` or `cannot be
   checked`. Change nothing else in it.
3. `export.py fill` that state. It writes a new file beside the old one
   (`-2`, `-3` …). Tell the person to open the new file: it shows each
   finding beside its box with "Accept the fix" and "Keep my words".
4. They answer each one, then copy everything out again and paste it to
   you. That text is what you export from (`export.py md`, `pdf` …).

From a page opened as a file, the browser may refuse the clipboard: the page
then shows the whole text selected in a box below the scaffold, and the
person copies it with the keyboard or presses "Save as a file".

## Tried

Tried 2026-11-22 by an agent with stand-in text, in Chrome from a file: a
deck begun here and carried into enough; a document carried in from enough,
finished, locked, checked in turns as above, fixes taken and kept, and
exported as Markdown and PDF.
