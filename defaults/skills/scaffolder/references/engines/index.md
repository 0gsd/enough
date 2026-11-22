# The engines: where a scaffold can live

Read this first in any harness that is not enough. The five steps are the
same everywhere (`SKILL.md`): the plectrum, the scaffold, the writing, the
lock, the finish. What changes from harness to harness is the **engine**:
what holds the scaffold while the person writes into it.

**The rule holds in every engine: you never write into a plecholder's
field.** Not in a page, not in a store, not in a state file, not in the
chat. The person writes every word of the thing; you write the plectrum,
the plecs and the layout, and you offer wording only as a suggested fix at
lock, which changes nothing until the person accepts it.

There are four engines. Pick the first one the harness can do.

| engine | what holds the scaffold | read it |
|---|---|---|
| enough's composure | a composure on enough's canvas | [enough.md](enough.md) |
| an artifact with a store | a page published in claude.ai or Claude Code, saving to its own store | [claude-artifact.md](claude-artifact.md) |
| one self-contained HTML file | the page as a file, saving in the person's browser | [single-html.md](single-html.md) |
| the chat alone | the plectrum, filled in turns | [chat-only.md](chat-only.md) |

The one thing that moves a scaffold between engines is its **state**: one
markdown file (`../state.md`), so a scaffold begun in one harness is
finished in another. The page's "Copy everything out" button gives it;
`scripts/scaffold_state.py` reads it; `scripts/export.py fill` puts it back
into a page. enough does not read or give a state yet: a scaffold goes into
enough as its plectrum, and the person carries their words by hand
([enough.md](enough.md), "Carrying a scaffold in and out").

## Which harness can do which

"Tried" means one plectrum was taken through that harness, end to end, and
what worked is written here, with who tried it: a person, or a
coding agent standing in for one with stand-in text (which shows the path
works, not that it suits a person). Every row is **not tried** until then; until a row is
tried, say so when you rely on it.

| harness | engine to use | the page | a store | runs `scripts/` | exports it can make itself | tried |
|---|---|---|---|---|---|---|
| enough | composure | enough's own canvas | the project's files | yes | all (HTML, PDF, PPTX, Markdown) | tried 2026-11-22 by an agent with stand-in text: a deck finished here (plectrum in, words pasted by hand, lock, check, findings taken and kept, PPTX and PDF) and a document begun here; no state goes in or out yet |
| Claude Code | artifact with a store; else one HTML file | the published artifact, or the file opened in a browser | the artifact's store (`db`); else the browser | yes, with the person's Python | what `export.py can` reports | one HTML file: tried 2026-11-22 by an agent with stand-in text (a deck begun, a document finished: writing, saving in the browser, lock, copy out, the check filed in the state, fixes taken and kept, Markdown and PDF); the copy went to the panel, not the clipboard, from a file. Artifact with a store: not tried |
| claude.ai | artifact with a store | the published artifact | the artifact's store (`db`); "Save as a file" through `downloads` | yes, in its sandbox when code runs there | what `export.py can` reports there | tried 2026-11-19 (a page): plectrum, scaffold, saving, lock and check worked; "Save as a file" failed until the page used `downloads` |
| a chat harness with an HTML preview and no store | one HTML file | the preview, or the file saved and opened | the browser only | if it runs code | HTML always; the rest if it runs the script | not tried |
| a chat with no page at all | the chat alone | none | the chat itself | no | the plectrum and the state as text; HTML by hand from the state | not tried |

## Exports, wherever you are

`scripts/export.py` makes the thing's own formats with the standard library,
and uses pandoc, typst or python-pptx only when the harness has them. Run
`python3 scripts/export.py can` first and say what it found.

| thing | always | when present | with nothing present |
|---|---|---|---|
| page | HTML (`export.py html`) | PDF through typst | PDF: open the HTML and print it from the browser |
| deck | HTML (to print, landscape) | PPTX through pandoc, else python-pptx; PDF through typst | PDF: print the HTML at landscape. No PPTX |
| document | Markdown (`export.py md`), HTML | PDF through typst | PDF: print the HTML |

Every export writes a new file beside the state and never overwrites one.
A notes box is never exported; an empty box is left out and named.

## Where it goes next

The scaffold is presumed to be a link in a chain. Ask the person where the
work goes next (`export.py next FILE` prints the question and the choices),
and offer what fits, one or several: the thing's own formats; a mermaid
diagram (`export.py mermaid`); a fabulac brief, which is the brief enough's
authoring program takes, or the thing's words as one text that enough makes
a fabulan from (`export.py brief --for fabulac|fabulan`); a prompt for
another creative engine **the person names** (`export.py prompt --engine
NAME`). Never pick the next link for them.
