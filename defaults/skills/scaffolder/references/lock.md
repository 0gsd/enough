# The lock and the check

Read this when the person locks a scaffold, in any harness. The lock closes
the whole thing; the check reads it for spelling, grammar and truth, box by
box; the person answers each finding. The format of a finding is the
state's (`state.md`, sections 5 and 6); this page is the procedure.

Where the check runs: outside enough, you run it on the state (the person
copies everything out, or you read the page's store), and you file the
findings in that state's `# Findings`; the page shows them once you fill it
from that state. In enough the check is enough's own job, started from its
page, and you file nothing (`engines/enough.md`).

**The rule holds here too.** The check is the one place you offer wording:
a suggested fix for a quoted span. Nothing changes until the person accepts
it, and then only that span changes.

## 1. Locking

- One lock for the whole scaffold. The person locks it; you never do.
- Before they lock, name the boxes that are still empty (notes boxes
  aside). They may lock with empty boxes once you have named them; the
  check names them again as gaps, it does not fill them.
- Locked, the state has `locked: <UTC time>`. From then on the scaffold is
  **read-only for everyone**: no box's text, no plec, no target, no layout
  changes, from you or from the person. The one exception is the person
  accepting a fix (section 4).

## 2. The check

Read every box that is part of the thing (not the notes box), in the order
the thing shows them. For each, look for three kinds of finding:

| kind | what it is | what a finding gives |
|---|---|---|
| `spelling` | a word misspelt for the scaffold's `lang` | the word as `quote`, the spelling as `fix` |
| `grammar` | a sentence that does not hold together: agreement, a missing word, a broken clause | the smallest span as `quote`, the mended span as `fix`, `why` in one line |
| `truth` | a claim of fact: a number, a date, a name, a "first", a "only", something the thing says is so | see below |

- **Quote the smallest span** that carries the problem, exactly as it is in
  the box. If the span appears more than once in that box, add `prefix`
  and `suffix` (a few characters on each side) so it can be found once.
- **One finding per problem**, in the order found, numbered `f1`, `f2`, …
  and never reused: a finding from an earlier version keeps its id.
- **Spelling in a language you cannot check** (or a box in another language
  than `lang`) is one finding, kind `spelling`, status `cannot be checked`,
  `why: not checked for spelling: <language>`.
- **Style is not a finding.** Not tone, not length, not word choice, not
  "this could be stronger". A box over its target is not a finding; the
  page already shows it.
- **Truth.** Check a claim against what you can reach: the person's own
  files and notes in the harness, the plectrum, other boxes of the same
  scaffold, and sources the harness can read. When a claim is wrong, the
  finding quotes it, says what you found in `why` (and where), and offers a
  `fix` only when the right words are plain from the source. When you
  cannot confirm or refute it, the finding is `status: cannot be checked`,
  with `why` saying what you could not reach. It has no fix.

Write `checked: <UTC time>` and the findings under `# Findings` in the
state. Every new finding has `status: open` (or `cannot be checked`) and
`version:` the current version.

## 3. Showing the findings

Show them beside their boxes, one at a time or all at once, each with the
quoted words, the fix and the reason. In a page, the person answers with
"Accept the fix" or "Keep my words"; in a chat, they answer in turn. Say
how many wait. Never present a finding as decided.

## 4. The person's answers

- **Accepted:** the quoted span in that box's text becomes the fix, and
  only that span; the finding's `status` becomes `accepted`. If the span is
  no longer in the box exactly once, nothing changes: say so and look again.
- **Declined:** only `status` changes, to `declined`. The person's words
  stay as they are.
- **Cannot be checked:** final. It is never counted as passed, never
  turned into `accepted` or `declined`, never removed. The person reads it
  and decides what to do with their own words; if they change them, that is
  a new version.
- A finding with no `fix` (a gap, a claim found wrong with no plain
  wording) can only be kept or met by the person's own change, in a new
  version.

## 5. Unlocking makes a new version

- The locked file is never changed by unlocking. Keep it
  (`<slug>.v<N>.scaffold.md` where a harness has files; `scaffold/v<N>`
  in a page's store).
- The new state has `version` one higher, `parent` the old version, and
  `locked` and `checked` empty. Every finding is carried over as it was,
  each keeping the `version` that found it.
- The person may now change anything that is theirs to change, and lock
  again; the next check adds findings with the new version's number.

## 6. When the check is done

Say in one line what the check found: how many findings of each kind, how
many cannot be checked, which boxes were empty. Then the finish: ask where
the work goes next (`engines/index.md`).
