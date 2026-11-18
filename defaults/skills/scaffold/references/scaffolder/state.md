# The scaffold's state

Read this when you save a scaffold, load one, or carry one from one harness to
another. The state is one markdown file. It holds everything a scaffold is:
the plectrum, the layout, the person's text in each box, what is locked, the
version and its parent, and what the check found. A harness that can read
this file can pick up a scaffold another harness began.

The state uses the plectrum's grammar (`plectrum.md`) with a few more keys,
the person's text under each box, and a findings part at the end. A full
example is `examples/ten-slide-deck.state.md`.

---

## The file at a glance

````markdown
---
scaffold: 1
title: A garden on Mill Lane
thing: deck
# the other plectrum keys, written out in full
version: 1
parent:
locked: 2026-11-18T21:40:00Z
checked: 2026-11-18T21:41:12Z
---

# A garden on Mill Lane

## Cover

```frame
id: cover
```

### cover-title · Title

```plec
role: title
kind: text
target: 40c
row: 1
col: 1
plec-by: readvisor
state: written
plec: The garden's name and the place, as the committee will say it afterwards.
```

A garden on Mill Lane

# Findings

```finding
id: f1
box: the-ask-in-one-sentence
kind: spelling
quote: comittee
fix: committee
status: open
version: 1
```
````

---

## How it differs from a plectrum

### 1. The front matter

The second line is `scaffold: 1`, not `plectrum: 1`. Every plectrum key is
kept. Four keys are added:

| key | value |
|---|---|
| `version` | a whole number from 1. Each unlock makes the next |
| `parent` | the version this one was made from. Empty for version 1 |
| `locked` | when the person locked it, as UTC time `YYYY-MM-DDTHH:MM:SSZ`. Empty while open |
| `checked` | when the check last ran, the same way. Empty if it never ran |

A writer writes the keys in this order: `scaffold`, `title`, `thing`, `for`,
`writes`, `next`, `shape`, `unit`, `lang`, `aim`, `version`, `parent`,
`locked`, `checked`, then any key it did not know, in the order it read them.
It writes every known key, with the defaults spelled out and an empty value
as `key:`.

### 2. Frames

Every frame has a `frame` block, with its `id` always written.

A repeated frame of the plectrum is written out copy by copy. Each copy is a
frame of its own, with two more keys:

    ## Recipe 7

    ```frame
    id: recipe-07
    copy-of: recipe
    copy: 7
    ```

`copy-of` is the id the plectrum gave the pattern; `copy` is the copy's
number. This keeps the pattern: a person who adds a twenty-fifth recipe adds a
frame with `copy-of: recipe` and `copy: 25`, and its boxes get the same keys
and plecs as the others.

### 3. Boxes

Every box is in the block form, `### id · Name`, never the line form. Its
`plec` block always holds `role`, `kind`, `row`, `col`, `plec-by` and `plec`,
and `target` for a text box or `shape` for a graphic. The writer's order is:
`role`, `kind`, `target`, `shape`, `row`, `col`, `place`, `fixed`, `chips`,
`plec-by`, `state`, `href`, `plec`, then keys it did not know.

The state's own keys:

| key | value | who sets it |
|---|---|---|
| `row`, `col` | the box's row in its frame and its place in the row, from 1. Written for every box | readvisor or person |
| `place` | for a harness that places boxes freely (a slide, mostly): `left top width height`, four numbers from 0 to 100, in percent of the frame. When present it wins over `row` and `col`; `row` and `col` stay for a harness that lays out by rows | readvisor or person |
| `plec-by` | `readvisor` until the person edits the plec, then `person` | set to `person` by the person's edit |
| `state` | `written` when the person has marked the box written. Absent otherwise. "Empty" and "over the target" are worked out from the text and never stored | person only |
| `href` | a graphic's picture: a path relative to the state file, or a URL | person only |

### 4. The person's text

The person's text for a box is everything after its `plec` block's closing
fence, up to the next line that starts with `# `, `## ` or `### `.

- It is markdown, as the person wrote it.
- Blank lines at its start and end are dropped. Nothing else is changed:
  spaces, line breaks and inner blank lines are kept.
- A text line that starts with `#` would end the box. So a writer puts one
  more backslash in front of every text line that starts with `#` or with
  backslashes followed by `#`, and a reader takes one off. `# Note` is
  written `\# Note`; `\# Note` is written `\\# Note`.
- Inside the text, a line such as `#### a`, `#tag` or `####` is text, not a
  heading: only `# `, `## ` and `### ` end it. A writer escapes those too.
- An empty box has no text: its closing fence is followed by a blank line and
  the next heading.
- For a graphic, the text is the person's caption or description of the
  picture, and may be empty.

The writer puts one blank line after the fence, the text, and one blank line
before the next heading.

### 5. Findings

What the check found comes after the last frame, under the line `# Findings`.
It is the only `#` line after the title. Each finding is one fenced block with
the info string `finding`, in the order they were found. A state with no
findings has no `# Findings` line.

| key | value |
|---|---|
| `id` | `f1`, `f2` …, unique in the file, never reused |
| `box` | the id of the box it is about |
| `kind` | `spelling`, `grammar` or `truth` |
| `quote` | the exact span of the box's text it is about. Empty means the whole box |
| `prefix`, `suffix` | a few characters before and after the span, when the span appears more than once in the box. Optional |
| `fix` | the suggested replacement for the span. Empty when there is none |
| `why` | one line: what is wrong, or why it cannot be checked. Optional for spelling |
| `status` | `open`, `accepted`, `declined`, or `cannot be checked` |
| `version` | the version whose check found it |

In `quote`, `prefix`, `suffix` and `fix`, a line break is written `\n` and a
backslash `\\`. All other values are one line as written.

The outcomes:

- **open**: found, and the person has not answered yet.
- **accepted**: the person took the fix. The fix is already in the box's text
  above; the finding stays as the record of the change.
- **declined**: the person kept their own words.
- **cannot be checked**: a claim the check could not confirm or refute from
  what it can reach, or text it cannot check (for example spelling in a
  language it does not know). It has no fix. It is never counted as passed,
  and the check never changes it to anything else. The person reads it and
  decides what to do with their own words.

### 6. Lock and versions

- While `locked` has a time, the scaffold is read-only. Nothing in it
  changes, for the readvisor or the person, with one exception: the person
  may accept a fix. That changes only the quoted span in that box's text, and
  sets the finding's `status` to `accepted`. Declining changes only
  `status`.
- Unlocking does not change the locked file. It makes a new state with
  `version` one higher, `parent` the old version, `locked` and `checked`
  empty, and every finding carried over as it was (each keeps the `version`
  that found it). The old file is kept.
- Suggested file names, where a harness has files: the plectrum as
  `<slug>.plectrum.md`, the state as `<slug>.scaffold.md`, a version kept at
  unlock as `<slug>.v<N>.scaffold.md`, where `<slug>` is the title's slug.

---

## Without loss

The state moves a scaffold between harnesses, so a reader and a writer must
agree exactly:

1. Reading a file the writer wrote and writing it again gives the same bytes.
2. Writing a state and reading it back gives the same state.
3. A file a person edited by hand is read to the same state as the writer's
   form of it, and the writer then writes its own form. Line-form plecs, a
   ` | ` separator, continued values, missing defaults and stored "empty" or
   "over" states are the only differences a reader smooths over.
4. A key the reader does not know is kept and written back, in the front
   matter, a frame block, a plec block or a finding.
5. Prose lines that are none of the parts are not kept. The writer writes
   none.

A harness that keeps a scaffold in its own form (a page's store, a
composure) must be able to give this file back, and take it in, with nothing
lost.

## The plectrum, back out of a state

To get the plectrum from a state: write `plectrum: 1` for `scaffold: 1`;
drop `version`, `parent`, `locked` and `checked`; drop every box's text,
`state` and `href`; drop the findings; fold copies with the same `copy-of`
back into one frame with `repeat` set to their count. The layout (`row`,
`col`, `place`) stays, as hints.

## For a program

A reader that turns the state into data can use this shape (names as in the
file; lists keep the file's order):

```json
{
  "scaffold": 1,
  "meta": {"title": "…", "thing": "deck", "for": "…", "writes": "…", "next": "…",
           "shape": "slide", "unit": "c", "lang": "en", "aim": "thing",
           "version": 1, "parent": null, "locked": "2026-…Z", "checked": "2026-…Z",
           "extra": {}},
  "frames": [
    {"id": "cover", "name": "Cover", "shape": null, "copy_of": null, "copy": null, "extra": {},
     "boxes": [
       {"id": "cover-title", "name": "Title", "role": "title", "kind": "text",
        "target": "40c", "shape": null, "row": 1, "col": 1, "place": null,
        "fixed": null, "chips": [], "plec_by": "readvisor", "state": "written",
        "href": null, "plec": "…", "text": "A garden on Mill Lane", "extra": {}}
     ]}
  ],
  "findings": [
    {"id": "f1", "box": "the-ask-in-one-sentence", "kind": "spelling", "quote": "comittee",
     "prefix": null, "suffix": null, "fix": "committee", "why": null,
     "status": "open", "version": 1, "extra": {}}
  ]
}
```
