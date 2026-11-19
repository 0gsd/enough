# Engine: an artifact with a store (claude.ai, Claude Code)

Use this when the harness can publish an interactive page that keeps a small
database of its own (an Artifact with the `db` capability). The person
writes on the page; the words are kept in the page's store; you read the
store to see what they wrote. This is how the first plecholder page was made.

**The rule: you never write into a plecholder's field.** Not on the page,
and not in the store: you never write a document in the collection `plecs`,
and you never put words into a box's `text` in `scaffold/state`. Reading
the store is how you see the person's words; writing it is theirs.

## Build it

1. The plectrum first, read back to the person and corrected (`SKILL.md`,
   steps 1 and 2). Say the count line.
2. Make the page: copy `assets/scaffold.html` and replace the content of its
   one JSON block (the script element of type `application/json` with id
   `scaffold`) with the plectrum as JSON. With Python:
   `python3 scripts/export.py fill PLECTRUM.md` writes `<slug>.scaffold.html`.
   Without Python: write the JSON by hand in the shape `../state.md` gives
   "for a program", with every `<` written `<`.
3. Publish that file as an artifact that declares the `db` capability (in
   claude.ai and Claude Code, load the artifact capabilities guidance first
   for the declaration). The page needs nothing else: no fonts, no scripts,
   no network.
4. Give the person the link. Tell them: each dashed box is theirs; the
   bracketed line says what it must get across; it saves as they type;
   "+ scaffold-box" and "+ page" (or "+ slide") add parts; "Lock" closes
   the whole when they are done.

## What the store holds

| collection / doc | written by | holds |
|---|---|---|
| `plecs/<box id>` | the page, as the person types | `{text, name, target, chars, words, state, updated}` |
| `scaffold/state` | the page, on a change of layout, a lock, an unlock, an accepted or declined finding | `{json, base, version, locked, updated}`: `json` is the whole model as JSON, `base` a hash of the JSON block it grew from |
| `scaffold/v<N>` | the page, at unlock | the locked version N as it was, `{json, version, updated}` |

On load the page takes its JSON block; if `scaffold/state` grew from that
same block (`base` matches), it takes the saved layout instead (the
person's added boxes, the lock); then each `plecs` document gives back its
box's words. A page republished with a new JSON block keeps the person's
words box by box, by id.

## Change the layout when the person asks

1. Read the store: `scaffold/state` (its `json`) and every `plecs` document.
2. Make the state from them: the model from `json`, each box's `text` from
   `plecs/<id>`. Write it out (`scaffold_state.py write`) and keep it.
3. Change the plectrum as asked: a box, a plec, a target, the order. Keep
   every id. Never drop a box that holds the person's words; propose it.
4. Fill the page from the new state (`export.py fill`) and republish to the
   same artifact. The person's words come back from the store by id.

## Lock and check

The person presses "Lock". Read the store, make the state, and run the
check as `../lock.md` says. Findings go into the state's `# Findings`;
republish the page with that state, and the page shows each finding beside
its box with "Accept the fix" and "Keep my words". Only the person's click
changes a word.

## Finish

Make the state from the store, ask where the work goes next
(`export.py next`), and make what the person chooses (`../engines/index.md`,
"Exports"). In claude.ai, run the script in the code sandbox when there is
one; otherwise give the HTML (always possible) and say how to print a PDF.

## When the store is not there

If the page says "Kept in this browser only", the store is not reachable:
the words are safe in that browser, and the person's "Copy everything out"
gives you the whole state as markdown. Work from that, as
`single-html.md` says.

## Tried

claude.ai: not tried. Claude Code: not tried (see the index's table).
