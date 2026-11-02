# Ascribe OES 1: a person, described without a name

*Specification of the `ascribe/1` MiniCOSM · written 2026-11-02 for enough 0.5.0*

Ascribe is the MiniCOSM for a person's **holograph**: a description of one self, comprehensive enough that a name is
unnecessary. It holds what a person is drawn to and turns from, believes, worries about, has lived through, wants to
know, thinks, feels, can do, understands and longs for, each item anchored to the thing it is about, under a
pseudonymous handle. It is written in MacroCOSM OES (`docs/MACROCOSM_OES.md`), whose words (item, kind, volume,
catalog, module, check, lens, open question) keep their meaning here, and what leaves a holograph leaves by a Thym
program its holder runs (`docs/THYM.md`). Comprise describes companies; Ascribe describes people, in the same grammar,
with the same envelope, so that one set of moves works on both.

**Status.** Normative for `ascribe/1`. The declaration is the manifest, `defaults/cosm/manifests/ascribe.manifest.cosm`;
the reference reader is `enough/macrocosm.py`, and Ascribe's own checks are `enough/ascribe.py`. Where this text and the
code disagree, the code wins and this text is corrected. What enough builds of Ascribe in 0.5.0 is the manifest and the
reader: a holograph loads, checks and draws in the cosm viewer, and nothing in enough writes one (section 13). A rule the
owner of enough settled is marked *the owner's ruling*; the rulings are dated 2026-11-01 and collected in section 14.

## Contents

1. Provenance and the name
2. The model on one page
3. The design rules
4. The holograph
5. The ten containers and the forms
6. The envelope
7. Links and relations
8. The dialectic
9. Checks
10. The private filter
11. The command line
12. Projections, by reference
13. What is not built
14. Decisions in this version

Colophon

## How to read this

**Must and may.** *Must* is a rule a conforming reader or writer keeps. *May* is a permission. *Should* is advice the
checks do not enforce.

**The family of words.** The suffix says what kind of subject; the prefix says the form. Ascribe is the second row.

| | the whole, private, held by its subject | the verified public duplicate | an outsider's guess, unverified | the owner's encrypted share | the style sheet |
|---|---|---|---|---|---|
| a company (Comprise) | **holotype** | **isotype** | **paratype** | **cryptotype** | — |
| a person (Ascribe) | **holograph** | **isograph** | — (never) | **cryptograph** | **holomorph** (private) · **isomorph** (shared) |

*holo-* the whole; *iso-* an equal, verified; *para-* beside, by another hand; *crypto-* hidden, by the owner. There is
no outsider's graph of a person, ever (the owner's ruling): what one person knows of another is an experience in their
own holograph.

**Blocks.** A block marked `cosm` is one complete file that loads through the reference reader and passes the checks
the manifest selects and Ascribe's own (`python -m enough.ascribe lint`), with every reference resolving inside it. A
block marked `yaml` is a fragment and may point outside itself. A block marked `text` is a picture or a transcript.

---

## 1. Provenance and the name

<!-- atem: where Ascribe comes from, and what the name says -->
The owner's drawings for the 0.5.0 round set two subjects side by side, each with a private whole and public
projections: Comprise for companies, already built, and Ascribe for people. `docs/thym-architecture.md` (local) drew its
first shape, with the modules left to the owner; the owner wrote the list on 2026-11-01, and the manifest landed the
same evening as `ascribe/1`. *Ascribe OES 1* is its name in prose, as *Comprise OES 1* is Comprise's.

To *ascribe* is to set something down as belonging to someone. A holograph ascribes qualities to a self without saying
whose self it is.

---

## 2. The model on one page

<!-- atem: a folder that is the self, ten containers of nodes, and the forms they anchor to -->

```text
<holograph>/
  holograph.cosm                    the self: oes: ascribe/1, id ascribe/<hid>, a handle, pseudonyms, sample
  A/ B/ C/ E/ I/ O/ Q/ S/ U/ Y/     ten containers of the self, one kind of node each
  F/                                the forms the nodes anchor to, the polyforms that combine them, declared relations
  **/.ascribe-private               a marker: what ingest and transfer leave behind (declared, not built)
```

- The **holograph** is the volume: a folder whose catalog, `holograph.cosm`, is the self. It names no one. Its id is a
  base32 handle-id, and its `handle` is a pseudonym.
- A **node** is one item of the self, in one of ten kinds: affinity, belief, concern, experience, interest, opinion,
  quale, skill, understanding, yearning. Each kind lives in its own module, whose letter is the kind's initial.
- A **form** is a thing a self can be about: anything a person can love or hate, know well or want to learn ("is there
  an encyclopedia article for it, or should there be?"). Every node anchors to one form, or to a polyform that combines
  several. Forms are shared roots, grounded in FEED where the form is one word FEED has.
- The author shapes the rest: hierarchies, branches and flat lists by `of` and `parts`; typed links from a starter list
  or from relations they declare; a `when`, a `valence` and a `strength` where they help.
- Nothing about the person that would identify them has a place in the schema. A check warns on what reads like it,
  and a filter keeps private files out of ingest and transfer.
- The holograph stays with its holder. What leaves it, as an isograph or a cryptograph, leaves by a Thym program the
  holder runs (section 12).

---

## 3. The design rules

<!-- atem: seven rules every part of Ascribe answers to -->
1. **No name is needed.** A holograph describes a self well enough that a name adds nothing. The catalog carries a
   pseudonymous handle and no name.
2. **No personal data, three ways** (the owner's ruling). *Schema*: there is no kind and no field for a name, an email
   address, a phone number, a postal address, a birth date, a government id or an employer's legal name. *Lint*: the
   `no-pii` check warns on what reads like any of them, anywhere in the volume, comments included, and never refuses
   (section 9). *Filter*: a `.ascribe-private` marker keeps files out of ingest and transfer (section 10).
3. **Every node is about something.** A node anchors to a form or a polyform that exists (`form-anchored`), so that two
   nodes about the same thing are seen to be.
4. **One grammar for both subjects.** The envelope is Comprise's, plus six fields of Ascribe's own (section 6), so that
   Thym's moves read a holograph as they read a Holotype.
5. **The author shapes it.** Hierarchy, branches, links, dates, valence and strength are optional and the author's.
   The checks hold only what must hold: an anchor, a declared relation, a well-formed `when`, a strength in range.
6. **Nothing of another person.** A reference never points into another person's holograph. People in a life appear by
   role ("a retired harbour pilot") or by a pseudonym the catalog declares.
7. **The holder releases.** Nothing in a holograph is public by default (`visibility` is `internal` when absent), and
   what is released is released by a program the holder runs.

---

## 4. The holograph

<!-- atem: the folder, its catalog, its module files, its ids and paths -->

### 4.1 The volume

A holograph is a folder, laid out as a Holotype's atoms are, minus the part level: one person, one volume, so the module
folders sit directly beside the catalog.

| Place | Holds |
|---|---|
| `holograph.cosm` | the catalog, the self; it may carry a few nodes of any module in its own `nodes:` |
| `<module>/` | `A/` `B/` `C/` `E/` `I/` `O/` `Q/` `S/` `U/` `Y/` for the ten kinds, `F/` for forms, polyforms and relations; a reader reads either case and a writer writes the capital |
| `<module folder>/**/*.cosm` | module files, at any depth, each a mapping with a `nodes:` list |
| `.ascribe-private` | a marker, anywhere below the catalog (section 10) |

A node is written in its own module's folder or in the catalog's `nodes:`; a node elsewhere fails `id-module`, which
`enough/ascribe.py` holds to the folders because the generic reader places module folders only under parts.

### 4.2 The catalog

| Key | Holds |
|---|---|
| `oes` | `ascribe/1`; a `holograph.cosm` without it is refused |
| `macrocosm` | reserved (MacroCOSM 5.6) |
| `id` | `ascribe/<hid>`: the hid is twenty-six characters of lowercase base32 (`a`–`z`, `2`–`7`), the shape of a Comprise Connect `hid` |
| `handle` | a pseudonymous handle: lowercase words joined by hyphens (`salt-and-crumb`), never a name |
| `summary` | one line, optional; people appear in it by role, never by name |
| `sample` | `true` on a fixture or a demonstration, never on a real person's holograph |
| `visibility` | `public`, `internal` or `restricted`; `internal` when absent |
| `pseudonyms` | the stand-in names the author uses for the people in their life ("Wren", "the Captain"), so that the `no-pii` check reads them as declared rather than as personal names |
| `nodes` | items, when the catalog carries any |

A catalog never holds the person's name, an email address, a phone number, a postal address, a birth date, a government
id or an employer's legal name. A catalog `name` key reads as a personal name to the `no-pii` check (a holograph names
no one); an item's `name` is the item's own. The reader titles a holograph by its `handle`.

### 4.3 Ids and paths

An item's id is `<module>:<kind>/<slug>`: `A:affinity/sourdough-baking`, `Q:quale/starter-smell`,
`F:form/celestial-navigation`, `F:polyform/slow-crafts`, `F:relation/learned-in`. Inside its own volume an id is
written bare. A path respells an id through the manifest's levels, `<module>/<kind>/<slug>#<field>`
(`A/affinity/sourdough-baking#strength`), and a URI qualifies it, `oes:ascribe/<hid>/<path>`, the catalog id without
`ascribe/` standing for the database. The slug grammar and the refused path forms are MacroCOSM's (MacroCOSM 11.2),
with the module segment one of `A B C E I O Q S U Y F`.

### 4.4 An example

A holograph small enough to be one file, every node in the catalog: two forms, a declared relation, and two nodes, one
linked to the other by the declared relation.

```cosm
oes: ascribe/1
id: ascribe/aej6l5qrka6c6btarfiy2f7vnj
handle: salt-and-crumb
summary: A baker by a working harbour, slow at most things on purpose.
sample: true
visibility: internal
pseudonyms: [Wren]
nodes:
  - id: F:form/sourdough
    type: form
    name: sourdough
    summary: Bread leavened by a starter of wild yeasts and bacteria instead of commercial yeast.
    feed: {word: sourdough, pos: noun, origin: feed}
    provenance: {mode: dialectic, sources: [session-1], confidence: 1}
  - id: F:form/celestial-navigation
    type: form
    name: celestial navigation
    summary: Finding a position at sea from the sun, the moon and the stars, with a sextant, a clock and tables.
    wiki: Celestial navigation
    provenance: {mode: dialectic, sources: [session-2], confidence: 1}
  - id: F:relation/learned-in
    type: relation
    name: learned in
    summary: A skill or an understanding picked up during the experience the link points to.
    provenance: {mode: manual, sources: [self], confidence: 1}
  - id: E:experience/first-night-crossing
    type: experience
    name: A first night crossing
    summary: A crossing of the bay at night with a retired harbour pilot, steering by the stars.
    form: F:form/celestial-navigation
    when: 2019
    valence: for
    strength: 5
    provenance: {mode: dialectic, sources: [session-2], confidence: 0.9}
  - id: S:skill/taking-a-sight
    type: skill
    name: Taking a sight
    summary: A star brought down to the horizon with a sextant, and the time noted to the second.
    form: F:form/celestial-navigation
    strength: 3
    links:
      - {rel: learned-in, to: E:experience/first-night-crossing}
    provenance: {mode: dialectic, sources: [session-2], confidence: 0.8}
```

The sample holograph that `tests/fixtures/ascribe/sample-self/` holds is the same self at full size, in folders: every
module, twenty-six items, one open question (sea glass, which FEED does not have).

---

## 5. The ten containers and the forms

<!-- atem: ten kinds of node, one per module, and the forms they anchor to -->

### 5.1 The containers

Each container holds one kind, named for the singular of the module, and the letter is the kind's initial (the owner's
ruling).

| Letter | Module | Kind | What it holds |
|---|---|---|---|
| A | Affinities | `affinity` | what you are drawn to, and what you turn from |
| B | Beliefs | `belief` | what you hold to be true |
| C | Concerns | `concern` | what weighs on you |
| E | Experiences | `experience` | what has happened to you, and what you did |
| I | Interests | `interest` | what you want to know more about |
| O | Opinions | `opinion` | what you think, and would say so |
| Q | Qualia | `quale` | how things feel from the inside |
| S | Skills | `skill` | what you can do |
| U | Understandings | `understanding` | what you have come to understand |
| Y | Yearnings | `yearning` | what you long for |

Every kind's reference fields are `form`, `of`, `parts` and `links`, and its checked fields `when`, `valence` and
`strength`. An affinity against something is still an affinity: `valence: against` says which way it points.

### 5.2 The forms

Module F, *Forms*, holds the things a self is about and how they combine. Forms are shared roots, not nodes of the self:
they anchor nothing and need no form of their own.

| Kind | What it is | Its own fields |
|---|---|---|
| `form` | one thing a self can be about | `feed`: `{word, pos, origin}` (`origin` is `feed` or `user`) when the form is one word FEED has, else `{pending: "not in FEED"}`; `wiki`: an encyclopedia article's title or URL; `when` |
| `polyform` | several forms taken together | `forms`: the forms it combines; `links`: `{from, rel, to}` between them; `feed`, `wiki`, `when` |
| `relation` | a relation the author declares beyond the starter list | `name` and `summary`, which give its sense; links name it by its slug (section 7) |

Metadata on a form is global: every node anchored to it shares it. Metadata on a node belongs to that node alone. A form
with a `wiki` names a public subject, and its prose is not read for personal names (section 9).

A module file, as a fragment:

```yaml
# A/affinities.cosm
nodes:
  - id: A:affinity/fast-bread
    type: affinity
    name: Fast bread
    summary: Bread hurried along with commercial yeast tastes of very little.
    form: F:form/sourdough
    valence: against
    strength: 3
    provenance: {mode: dialectic, sources: [session-1], confidence: 0.8}
```

---

## 6. The envelope

<!-- atem: Comprise's envelope plus six fields of Ascribe's own -->
The envelope is Comprise's, so that Thym's moves work on both subjects; confidence and sources live in `provenance`, as
they do in Comprise outside its product tree. Six fields are Ascribe's: `form`, `of`, `parts`, `when`, `valence` and
`strength`.

| Field | Holds |
|---|---|
| `id`, `type` | the item's id and its kind |
| `name` | the item's name, never the person's |
| `summary` | one line about the item |
| `status` | `active`, `dormant`, `planned` or `retired` (once true of the person, no longer: a belief given up) |
| `visibility` | `public`, `internal` or `restricted`; `internal` when absent |
| `provenance` | `mode`, `sources`, `confidence` (a number from 0 to 1: how sure the person is) and `state` (`known`, the default, `pending`, `not-disclosed`, `stale`); `sources` name a dialectic session (`session-3`), a text the author wrote (`notes.md#L3-L7`), or `self` for what they wrote down directly |
| `pending` | open questions on the item |
| `links` | typed links (section 7) |
| `span` | where in a text the node was read: `{lines: "12-18"}`, or `{start, end}` of up to sixty characters each |
| `form` | what the node is about: one `F:form/<slug>` or `F:polyform/<slug>`; every node of the ten kinds carries one |
| `of`, `parts` | the node this one is a child of, and the node's children in order: a hierarchy, a branch or a flat list, as the author likes |
| `when` | a date (`2014-06-03`), a year (`2014`) or an era word (`childhood`, `2010s`, `university`); absent, the node is not on the timeline |
| `valence` | `for`, `against` or `mixed` |
| `strength` | a whole number from 1 to 5 |
| `made` | `{move, run, step, engine}`: the Thym move that made the item, or `{move: none}` for a hand-made one (THYM.md 5.3) |

Required: `id`, `type`, `name`, `summary`, `provenance`. The provenance modes are Comprise's list (`dialectic`,
`net-scan`, `system-scan`, `integration`, `structured-intake`, `manual`, `derived`, `asserted`, `archetype`,
`catalogue`, `directory`, `accounting`). An open question is `{pending: "<the question>"}`, answered by the person;
the sentinels are `none` and `self`; unknown fields are allowed and kept. `valence` and a FEED grounding's `origin` are
closed lists.

---

## 7. Links and relations

<!-- atem: a starter list of relations, and the ones an author declares -->
A typed link is `{rel, to}`, as in MacroCOSM 9.4. Its `rel` is one of the starter relations or a relation the holograph
declares:

```text
is-a  part-of  about  because  before  after  with  against  like  from  toward  see
```

`before` and `after` order nodes in time without dates. A declared relation is an `F:relation/<slug>` with a name and a
one-line summary giving its sense; a link names it as `rel: <slug>`, or by its id. A relation that repeats a starter word
is refused: use the starter word, or give the relation a name of its own.

The manifest keeps the starter list as `links.starter` and leaves the closed `links.rels` out on purpose: a closed list
there would make the generic reader refuse every relation an author declares. Ascribe's own check, `relation-declared`,
closes the list instead, so that a typo never becomes a relation.

References take three forms: a bare id (`F:form/sourdough`), naming an item of the same holograph; a typed link; and an
open question. An unresolved reference is an error. A reference never names another person's holograph.

---

## 8. The dialectic

<!-- atem: the opening questions a guided process asks, four for each module -->
The manifest's `dialectic:` block holds the opening questions a guided process, or an agent, asks to help a person fill
a holograph in (the owner's ruling). They are plain words, in no one's voice. What the person says is written as nodes
with provenance `{mode: dialectic, sources: [session-<n>], confidence: <how sure the person is>}`. In 0.5.0 the questions
are all that is built; the process that asks them is a later round.

- **A Affinities.** What do you go back to, again and again? What can you not stand, even when everyone around you loves it? Which place or kind of work feels most like yours? What did you love as a child that you still love?
- **B Beliefs.** What do you believe that most people around you do not? What did you once believe and no longer do? What would you hold to even if it cost you something? What do you take on trust?
- **C Concerns.** What keeps you awake at night? What do you worry about for the people close to you? Which problem do you wish more people noticed? If you could fix one thing, what would it be?
- **E Experiences.** What happened that changed the direction of your life? Which day would you live again? What have you done that you are proud of? Which stretch of years feels like a chapter of its own?
- **I Interests.** What could you read about for hours? What have you looked up lately just because you wanted to know? What would you study if you had a year to spare? What do you notice that others walk past?
- **O Opinions.** What do you think most people get wrong? What is overrated, and what is underrated? Which argument would you gladly start at dinner? What have you changed your mind about lately?
- **Q Qualia.** Which sensation do you remember most exactly? What does your favourite weather feel like? Which sound, smell or taste takes you straight back somewhere? What does it feel like when your work is going well?
- **S Skills.** What can you do without thinking about it? What do people ask you to help with? What did you learn the hard way? What are you getting better at right now?
- **U Understandings.** What do you understand now that you did not ten years ago? What could you explain to a curious stranger? Which idea changed how you see things once it clicked? What do you know from experience that no book taught you?
- **Y Yearnings.** What do you wish you had time for? What would you try if you knew you could not fail? Where would you go, given the chance? What do you miss?
- **F Forms.** Which words would you put on a list of things you care about? What would you look up first in an encyclopedia? Which subject deserves an article that nobody has written yet? Which things belong together for you, though others keep them apart?

---

## 9. Checks

<!-- atem: MacroCOSM's generic checks, and six of Ascribe's own -->

### 9.1 The generic checks

The manifest selects `load` and the envelope checks `duplicate-id`, `id-grammar`, `id-module`, `type`, `type-prefix`,
`identity-min`, `provenance`, `status`, `visibility`, `ref-grammar`, `ref-unresolved`, `closed-list`, `pending-shape` and
`catalog-key` (MacroCOSM 12.2). `enough/ascribe.py` holds two of them to what the generic reader cannot read from the
manifest: `id-module` to the module folders (section 4.1), and `catalog-key` to the hid, the handle and the shape of
`pseudonyms`.

### 9.2 Ascribe's own

Run by `enough/ascribe.py` (`lint_holograph`) after the generic ones, in one report. A generic reader does not run them.

| Check | Severity | Catches |
|---|---|---|
| `form-anchored` | error | a node of the ten kinds with no `form`, a `form` that names no item, or one that names something other than a form or a polyform; a `form` that is an open question is a note |
| `relation-declared` | error | a link whose `rel` is neither a starter word nor a declared relation; a declared relation that repeats a starter word |
| `when-shape` | error | a `when` that is not a date, a year or an era word |
| `strength-range` | error | a `strength` that is not a whole number from 1 to 5 |
| `no-pii` | warning, never an error | what reads like personal data (section 9.3) |
| `private-marker` | note | what a `.ascribe-private` marker would keep out of ingest and transfer (section 10) |

The manifest's `checks.severity` may move a severity; `no-pii` may be lowered to a note and never raised above a
warning, while the schema and the filter still hold (the owner's ruling).

### 9.3 What reads like personal data

`no-pii` reads every string of the catalog and of every item, every key, and every comment in every file of the volume.
It warns on:

| What | How it is recognised |
|---|---|
| an email address | a local part, an `@` and a dotted domain |
| a birth date | *born*, *birth*, *birthday*, *date of birth* or *dob* within a few words of a day of a month (a year alone is a `when`, not a birth date); and a node dated to the day whose name, summary or form speaks of a birth |
| an id-like run of digits | the three-two-four shape of a social-security number, a card's groups of four, or eight digits or more standing alone |
| a phone number | international with a plus, a bracketed area code, three-three-four groups, or a national number after a trunk zero; seven to fifteen digits in all |
| a street address | a number and a capitalised street name (*17 Quillfeather Lane*), the French, Spanish and Italian order, the German *-straße*, or a post-office box |
| a field for personal data | a key named for one: `email`, `phone`, `address`, `birthday`, `ssn`, `passport`, `employer`, `first-name`, `surname` and their kin; a catalog `name` |
| a personal name | in a prose field (a `summary`, and an experience's `name`), two adjacent capitalised words neither of which is all capitals, a place word, a month or day, a sentence's opening word, or a declared pseudonym |

A stretch one pattern has claimed is not claimed again, so one email address is one warning. A form with a `wiki` names
a public subject, and its prose is not read for names. Every warning ends with the same advice: people appear by role,
or by a pseudonym you declare.

---

## 10. The private filter

<!-- atem: what ingest and transfer leave out of a holograph -->
The manifest declares what ingest and transfer leave out of a holograph, the way Canon leaves a Holotype's private side
behind. The rule is declared and checked; the code that applies it is a later round.

- **Marker:** `.ascribe-private`.
- **Drops:** every file and folder beside a marker, with everything below them; and every node with `visibility:
  restricted`.
- **Keeps:** everything else, unchanged. A reference to a dropped node keeps its id and gains no name.

`private-marker` reports, as a note, what each marker would drop: the files, and how many nodes they hold, or "the whole
holograph" when the catalog itself is beside a marker. It drops nothing.

---

## 11. The command line

<!-- atem: one command that checks a holograph folder -->

```text
python -m enough.ascribe lint <folder | holograph.cosm> [--json]
```

It loads the holograph through the reference reader, runs the generic checks and Ascribe's own, prints each problem as
`<severity> <check> <item> (<file>): <message>`, and ends with one line: `ascribe/1: <n> items, <e> errors, <w> warnings,
<k> notes, <q> open questions`. It exits 0 when there is no error (warnings and notes do not fail it) and 1 otherwise.
It reads only the folder it is given and writes nothing. No server route, viewer or tool calls it in 0.5.0.

On the fixtures in `tests/fixtures/ascribe/`:

```text
sample-self                   ascribe/1: 26 items, 0 errors, 0 warnings, 0 notes, 1 open questions      exit 0
bad/pii                       ascribe/1: 8 items, 0 errors, 7 warnings, 0 notes, 0 open questions       exit 0
bad/unanchored                ascribe/1: 3 items, 1 errors, 0 warnings, 0 notes, 0 open questions       exit 1
bad/undeclared-relation       ascribe/1: 3 items, 1 errors, 0 warnings, 0 notes, 0 open questions       exit 1
```

`bad/pii` carries one of each pattern, invented, and every one is a warning: a phone number, a birth date, a personal
name, an email address, an id-like run of digits, an `employer` field and a street address.

---

## 12. Projections, by reference

<!-- atem: what leaves a holograph, and how; built in Thym, not here -->
- An **isograph** is the holograph projected by a Thym program its holder runs: the dial, for a person (THYM.md 18
  writes the company's). It is discoverable on an index like a profile. *Verified* means only what an Ascribe-Connect
  could check, that one real person holds this key and this graph has one holder; everything else is *stated*.
- A **cryptograph** is the holograph's sealed share for a chosen party: an encrypted Thym package (THYM.md 15.3), with
  the key shown once and stored nowhere, and, on an index, only consented match tokens, hashes of the characteristics
  the holder chose to make matchable.
- A **holomorph** is the morph measured from what the person writes with Ascribe active, and an **isomorph** is one the
  holder chose to share, released from the holograph by a program as an isograph is (THYM.md 13.4).
- There is no paratype of a person: no outsider's graph, ever.

A later round may bridge Comprise and Ascribe: an employer's *seek* for a role shaped like an isograph, answered by a
candidate's isograph, both speaking Thym. Nothing in 0.5.0 builds it; the common envelope makes it possible.

---

## 13. What is not built

<!-- atem: what 0.5.0 leaves for later rounds -->
- **The application module**: the process that asks the dialectic's questions and writes nodes, and any editor for a
  holograph. In 0.5.0 a holograph is written by hand; enough reads it.
- **Ascribe-Connect**: the service that would vouch that one real person holds a holograph.
- **Isographs on an index**, and the projection programs that make them.
- **Consented match tokens**, and an index that serves them.
- **The private filter's code**: the rule is declared (section 10) and nothing applies it.
- **The bridge to Comprise** (section 12).

What is built: the manifest, the reader's support (a holograph loads, checks and draws in the cosm viewer, titled by its
handle, with the lenses `self`, `graph` and the generic `map`; `timeline` is a table the reader keeps and does not
draw), `enough/ascribe.py` and its command, and the fixtures with their tests (`tests/test_ascribe.py`).

---

## 14. Decisions in this version

<!-- atem: the rulings and readings Ascribe OES 1 settled, one line each -->
1. **Ten containers, one kind each** (the owner's ruling): A B C E I O Q S U Y, the kind the singular of the module's
   name and the letter its initial.
2. **Module F for forms, polyforms and declared relations** (the owner's ruling). Every node anchors to a form.
3. **The catalog is the self** (the owner's ruling): `holograph.cosm`, with the module folders beside it; a handle,
   pseudonyms and a sample flag, and no name.
4. **`when`, with `before` and `after`** (the owner's ruling): a date, a year or an era word, optional; order without
   dates by the two starter relations.
5. **`valence` and `strength`** (the owner's ruling): `for`, `against` or `mixed`; a whole number from 1 to 5.
6. **The dialectic's questions live in the manifest** (the owner's ruling); the process that asks them is later.
7. **No personal data by schema, lint and filter; the lint warns and never refuses** (the owner's ruling), while the
   schema and the filter still hold.
8. **Ascribe OES 1 is `ascribe/1`** (the owner's ruling).
9. **Comprise's envelope**, so that one set of Thym moves works on both subjects.
10. **`links.starter`, not a closed `links.rels`**, so that declared relations pass the generic reader and
    `relation-declared` closes the list.
11. **No outsider's graph of a person, ever** (the owner's ruling, `docs/thym-architecture.md`): crypto- means encrypted,
    and there is no paratype of a person.

---

## Colophon

Written 2026-11-02 for enough 0.5.0, version 1 of Ascribe OES. The manifest is
`defaults/cosm/manifests/ascribe.manifest.cosm`; the checks are `enough/ascribe.py`; the grammar is
`docs/MACROCOSM_OES.md`; the projections are `docs/THYM.md`. Like the MacroCOSM specification and its manifests, this
specification is all rights reserved and not covered by enough's Apache License 2.0; see `defaults/cosm/NOTICE.md`.
