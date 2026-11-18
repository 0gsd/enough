# The plectrum

Read this before you write a plectrum, read one, or build a scaffold from one.
It gives the four words, the plectrum's grammar, who may change what, and the
count to say before building. The scaffold's state, which carries the
person's text, is in `state.md` beside this file. Three worked plectrums are
in `examples/`.

---

## The four words

- **Plectrum.** The structured markdown that says what the thing is, who it
  is for, how much of it the person means to write, and every plec it holds.
  It is made from the person's own prose and can be exported and used
  elsewhere.
- **Plec.** One line of the plectrum that says what one part of the thing
  must get across, with a target for its length.
- **Plecholder**, also called a **scaffold-box.** The box made from one plec:
  it shows the plec in brackets and has a free field where the person writes
  their own text.
- **Scaffold.** The thing laid out as plecholders, in its pages or slides,
  ready for the person to write into.

So: a plectrum holds plecs; a scaffold holds plecholders. The person writes
every word that goes into a plecholder. The readvisor never does.

**Thing** is the plain word for what is being made. A thing is one of three
kinds: a **page** (or a small site), a **deck**, or a **document**. Its parts
are **frames**: a frame is one band of a page, one slide of a deck, or one
section of a document.

---

## A small plectrum

````markdown
---
plectrum: 1
title: Spring open day
thing: page
for: neighbours who have never been inside the garden
writes: every word, about 600 characters
next: HTML for the club's site, and a PDF for the noticeboard
---

# Spring open day

## Opening

### headline · Headline

```plec
as: headline
target: 50c
plec: The day, the place and the one reason to come, in one line.
```

- When and where [120c]: The date, the hours and how to find the gate.

## What you can do

- Things to try [250c]: Two or three things a visitor can do with their own hands.
- The picture [graphic 4:3]: The beds in flower, with people in them.

## Not on the page

- Notes to the readvisor [notes]: Anything the page gets wrong.
````

The outer fence above is only for showing the example here. A plectrum file
starts with its `---` line.

---

## The grammar

A plectrum is a UTF-8 markdown file. Lines end with `\n` (a `\r\n` is read as
`\n`). It has three parts, in this order: the front matter, the title line,
and the frames.

### 1. The front matter

The file's first line is exactly `---`. Its second line is exactly
`plectrum: 1`. Then come `key: value` lines, one per line, until the next line
that is exactly `---`.

- A key is lowercase letters and hyphens. It ends at the first `: ` (or at a
  `:` that ends the line, which gives an empty value).
- A value is the rest of the line, with spaces at both ends dropped. It is
  plain text: no quotes are needed and none are removed.
- A key given twice is refused.
- Blank lines and lines starting with `#` inside the front matter are
  ignored.

The keys:

| key | needed | value |
|---|---|---|
| `plectrum` | yes, first | `1`, the grammar's version |
| `title` | yes | the thing's name |
| `thing` | yes | `page`, `deck` or `document` |
| `for` | yes | who it is for, in a phrase |
| `writes` | yes | how much the person means to write, in their own terms ("every word", "the headlines only", "about 3,000 words") |
| `next` | no | where the thing goes next, if the person said: a format, a place, or another tool. Empty means not said |
| `shape` | no | the frame's shape: `page`, `slide` or `letter`. Default: `page` for a page, `slide` for a deck, `letter` for a document |
| `unit` | no | the unit for a target written as a bare number: `c` (characters) or `w` (words). Default: `c` for a page and a deck, `w` for a document |
| `lang` | no | the language the person writes in, as a tag (`en`, `fr`, `de`). Default `en` |
| `aim` | no | `thing`, `map`, `diagram` or `system`: what the scaffold is a step toward. Default `thing`. A harness that knows nothing of aims treats them all as `thing` |

A reader keeps a key it does not know and writes it back unchanged. It does
not refuse it.

### 2. The title line

After the front matter, blank lines, then one line `# ` and the title. It
should match `title:`. If the two differ, the front matter wins and the
reader says so.

The title line is the only `#` line in a plectrum. (A state may have one
more: `# Findings`. See `state.md`.)

### 3. Frames

Each line starting with `## ` begins a frame. Frames come in the order the
thing shows them: top to bottom for a page, first to last for a deck or a
document.

- The heading is `## ` and the frame's name. Its id is the name made into a
  slug (see 6), unless the frame block gives one.
- Right under the heading, after blank lines, a frame may have one fenced
  block whose info string is `frame`:

  ```frame
  id: recipe
  repeat: 24
  shape: letter
  ```

  Keys: `id` (an explicit id), `shape` (this frame's shape, if it differs from
  the front matter's), `repeat` (see 5). A state adds `copy-of` and `copy`.
- A frame holds one or more plecs. A frame with none is refused.

### 4. Plecs

A plec is written in one of two forms. Both may be mixed inside a frame. The
order in the file is the order in the frame.

**The block form**, for a plec with more than a name, a target and a line:

    ### headline · Headline

    ```plec
    as: headline
    target: 60c
    plec: The one promise that holds for every subject alike.
    ```

- The heading is `### `, then the box's id, then ` · ` (a space, U+00B7, a
  space), then its name. For hand typing ` | ` is read the same as ` · `. With
  no separator, the whole heading is the name and the id is its slug.
- Under the heading, after blank lines, comes one fenced block whose info
  string is `plec`. Inside it, `key: value` lines as in the front matter.
- A line inside the block that starts with two spaces continues the value of
  the line before it, joined with one space. A writer never splits a value;
  this is only for people typing by hand.
- In a plectrum a box holds no text. After its block, the next `- ` line is
  the next plec, and other lines are prose (see 7). In a state, the person's
  text follows the block (see `state.md`).

**The line form**, for a plec that needs only a name, a target and its line:

    - Things to try [250c]: Two or three things a visitor can do with their own hands.

- A line starting `- ` at the left margin, directly inside a frame.
- Then the name, then a space, then a bracket `[...]`, then `: `, then the
  plec. The name runs to the first ` [`; the bracket ends at the first `]`,
  which must be followed by `: `.
- The bracket holds one of: a target (`250c`, `300w`, `250`, `0`); the word
  `graphic` and a shape (`graphic 4:3`); or what the box is, and a target (`notes`,
  `call 80c`). The bracket's first word tells which: a number is a target,
  `graphic` is a graphic, anything else says what the box is (its `as`). A bare
  `as` word means that, with no target.
- The id is the name's slug. Everything not said takes its default.

The plec's keys:

| key | needed | value |
|---|---|---|
| `plec` | yes | what this part must get across, in one line. At most 2,000 characters |
| `target` | no | how long the person's text should be: a number and a unit, `140c` or `300w`. A bare number takes the front matter's `unit`. `0`, the default, means no target. Give every text box but a notes box a target. A target is a guide, not a wall |
| `kind` | no | `text` (the default) or `graphic` |
| `shape` | for a graphic | the picture's shape: `16:9`, `4:3`, `1:1`, `3:4`, `9:16`, any `W:H`, or `portrait`, `landscape`, `square`. Default `16:9` |
| `as` | no | what the box is on the finished thing. Known values: `title`, `headline`, `lede`, `body`, `step`, `tile`, `deck`, `call`, `caption`, `quote`, `speaker`, `notes`. Default `body`. A value a harness does not know is shown as `body` |
| `fixed` | no | a fixed part shown with the box that is not the person's to write: a product name, an address, a label (`Comprise`, `10 slides`). Shown in grey, exported as it is |
| `chips` | no | fixed buttons or tags shown with the box, separated by commas (`PDF, PPTX, play`) |
| `row` | no | which row of the frame the box sits in, counting from 1. Boxes with the same `row` sit side by side. A box with no `row` takes the row after the last one used |
| `col` | no | its place in the row, counting from 1. Default: the order in the file |

A graphic has no target. Its plec says what the picture must show. The
person supplies the picture, always.

A box `as: speaker` holds a slide's speaker notes: written by the
person, kept out of the slide itself. A box `as: notes` is never
exported: it is where the person tells the readvisor what the scaffold gets
wrong. Every plectrum ends with a frame that holds one notes box, unless the
person asks for none. A frame that holds only notes boxes is not part of the
thing: it is not a band, a slide or a section, and it is not exported.

### 5. A repeated section

A document often has a long run of same-shaped pieces: twenty-four recipes,
thirty entries, twelve lessons. Write the piece once and say how many:

    ## Recipe {n}

    ```frame
    id: recipe
    repeat: 24
    ```

    - Name of the dish [8w]: What the family calls it.
    - The story [150w]: Who made it first, and when it is made now.

- `repeat: N` (N from 2 to 999) makes N copies of the frame and its plecs.
- `{n}` in the frame's name becomes the copy's number: `Recipe 1`, `Recipe 2`.
- Copies get ids by adding `-` and the number, padded with zeros to the width
  of N: frame `recipe-01`, boxes `name-of-the-dish-01`, `the-story-01`.
- A plec's own name and line may also hold `{n}`.
- A repeated frame cannot hold another repeat.

A state writes every copy out in full (see `state.md`).

### 6. Ids and slugs

- An id is 1 to 40 of `a-z`, `0-9` and `-`, starting with a letter or digit.
- A slug is made from a name by: lowercasing; turning every run of characters
  that are not `a-z` or `0-9` into one `-`; dropping `-` at both ends; cutting
  to 40 characters; dropping a `-` left at the end by the cut. A name that
  gives an empty slug is refused: give the box an id.
- Every frame id and every box id is unique in the file, after repeats are
  made into copies. Frames and boxes share one set of ids.
- An id, once a scaffold is built, does not change. A renamed box keeps its id.

### 7. What else may be in the file

- Blank lines anywhere between the parts.
- Prose lines after the title line that are none of the above. A reader
  ignores them and a writer does not keep them. Use them, if at all, for a
  word to whoever reads the file.
- Nothing else. A `####` heading, a second `#` line, a fenced block with
  another info string at a frame's or box's top, or a `plec` block with no
  `### ` heading above it is refused.

### 8. Refusals

A reader that refuses a plectrum says the line number, what it found and the
fix, in one sentence each: "Line 14: the plec block has no `plec:` line. Add
`plec:` and what this box must get across." It refuses the whole file, never
half of it.

### 9. Telling a plectrum from an outline

The `scaffold` skill's outline (`scaffold/references/structure.md` and its
`SKILL.md`) also uses `#`, `##` and `###`, and stays as it is. The two never
mix:

- An outline starts with a `# ` line and has no front matter.
- A plectrum starts with `---` and then `plectrum: 1`.
- A state starts with `---` and then `scaffold: 1`.

A harness reads the first two lines and knows which it holds. An outline is
not a plectrum with the front matter missing: its cards hold a body, a
plectrum's boxes hold a plec.

---

## Who may change what

The readvisor writes the plectrum from the person's prose. The person reads
it and corrects it before anything is built. After that:

| what | the readvisor | the person |
|---|---|---|
| the front matter (`title`, `thing`, `for`, `writes`, `next`, `shape`, `unit`, `lang`, `aim`) | proposes; changes it when the person asks | changes it |
| frames: add, drop, rename, reorder, repeat | when the person asks | yes |
| boxes: add, drop, rename, move (`row`, `col`, frame) | when the person asks | yes |
| a box's `plec` | writes it, and rewrites it until the person edits it; after that only proposes | yes. Once they edit it, it is theirs |
| `target`, `kind`, `shape`, `as`, `fixed`, `chips` | yes | yes |
| ids | sets them at the start | no; ids do not change |
| the text in a box | **never** | only the person |
| a graphic's picture | **never** | only the person |
| marking a box written | no | only the person |
| lock and unlock | no | only the person |
| accepting or declining a finding | no; it proposes the fix | only the person |

The one place the readvisor offers wording is a suggested fix at lock, and
nothing changes until the person accepts it.

---

## The count before building

Before building a scaffold, count its parts and tell the person: frames plus
boxes, after repeats are made into copies, notes box included. Say it as one
line: "This is 8 frames and 19 boxes, 27 parts in all."

Some harnesses can hold only so many. enough's composure holds 200 modules,
frames and boxes together. A long document can pass that: 40 recipes of five
boxes each is 240 parts before the opening. When the count passes what the
harness holds, say so and offer two ways: fewer boxes per piece, or the thing
split into two scaffolds (for example recipes 1 to 20 and 21 to 40). Do not
build a part of it silently.

Say the targets' sum too, in the plectrum's unit, when it helps the person
see how much they have taken on: "About 2,800 characters in all."
