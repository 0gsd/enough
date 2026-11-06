# Ascribe

*Edition 0.5.4 · revised 2026-11-03 · cosmoes.org home: https://ascribe.cosmoes.org/*

*This edition describes the `ascribe/1` MiniCOSM: the declaration every holograph carries.*

A person, described without a name: Ascribe is the MiniCOSM for a person's **holograph**, a description of one self
comprehensive enough that a name is unnecessary. It holds what a person is drawn to and turns from, believes, worries
about, has lived through, wants to know, thinks, feels, can do, understands and longs for, each item anchored to the
thing it is about, under a pseudonymous handle.

Ascribe is one of the two MiniCOSMs, the domain OESes with a specification of their own; Comprise OES
(https://comprise.cosmoes.org/), for companies, is the other. Both are written in MacroCOSM OES
(https://macro.cosmoes.org/), an OES: the shared grammar and its core, which holds the formats built into every
reader, the densities and the dialectic; its words (item, kind, volume, catalog, module, check, lens, open question, question, session) keep
their meaning here. Thym (https://thym.cosmoes.org/) is the transcognition language that connects OESes: an isograph
leaves a holograph by a Thym program its holder runs. Comprise describes companies and Ascribe describes people, in the
same grammar and with the same envelope, so that one set of moves works on both.

**Status.** Normative for `ascribe/1`. The declaration is the manifest, `ascribe.manifest.cosm`. The reference
implementation is enough (https://github.com/0gsd/enough): its MacroCOSM reader loads a holograph and runs the checks
the manifest selects, its Ascribe module runs Ascribe's own, and its cosm viewer draws the holograph. Where an
implementation and this text disagree, one of them is in error; the Changes appendix (section 17) records which was
corrected.

## Contents

<!-- atem: every section of Ascribe, in order -->
1. Provenance and the name
2. The model on one page
3. The design rules
4. The holograph
5. The ten containers and the forms
6. The envelope
7. Links and relations
8. The dialectic, applied
9. Reading a person's own texts
10. Checks
11. The private filter
12. Lenses
13. Releases
14. Projections: the isograph, the cryptograph, match tokens, morphs
15. The command line
16. Conformance
17. Changes
18. Withdrawn

Colophon

## How to read this

<!-- atem: the rule words, the family of words, the holder, and the blocks -->
**Must and may.** *Must* is a rule a conforming reader or writer keeps. *May* is a permission. *Should* is advice the
checks do not enforce.

**The family of words.** The suffix says what kind of subject; the prefix says the form. Ascribe is the second row.

| | the whole, private, held by its subject | the verified public duplicate | an outsider's guess, unverified | the owner's encrypted share | the style sheet |
|---|---|---|---|---|---|
| a company (Comprise) | **holotype** | **isotype** | **paratype** | **cryptotype** | — |
| a person (Ascribe) | **holograph** | **isograph** | — (never) | **cryptograph** | **holomorph** (private) · **isomorph** (shared) |

*holo-* the whole; *iso-* an equal, verified; *para-* beside, by another hand; *crypto-* hidden, by the owner. There is
no outsider's graph of a person, ever: what one person knows of another is an experience in their own holograph.

<!-- term: holder -->
The **holder** of a holograph is its subject, who keeps it: the one person who answers its questions,
runs its programs and releases what leaves it.

**Blocks.** A block marked `cosm` is one complete file that loads through a conforming reader and passes the checks the
manifest selects and Ascribe's own (section 10), with every reference resolving inside it. A block marked `json` is one
complete document of the format it names. A block marked `yaml` is a fragment and may point outside itself. A block
marked `text` is a picture or a transcript.

---

## 1. Provenance and the name

<!-- atem: where Ascribe comes from, and what the name says -->
Ascribe was drawn beside Comprise: two subjects set side by side, each with a private whole and public projections,
Comprise for companies and Ascribe for people. The architecture drawn for Thym gave Ascribe its first shape, with the
modules left to the owner, who wrote the list of ten; the manifest followed as `ascribe/1` (section 17). *Ascribe* is
its name in prose, as *Comprise OES* is Comprise's; `ascribe/1` is its declaration, as `comprise/1` is Comprise's.

To *ascribe* is to set something down as belonging to someone. A holograph ascribes qualities to a self without saying
whose self it is.

Ascribe is stewarded by Verroes (Graham Smith). Its canonical edition is published at https://ascribe.cosmoes.org/
(see the colophon); each revision is an edition, and the Changes appendix (section 17) records what each edition
changed.

---

## 2. The model on one page

<!-- atem: a folder that is the self: ten containers and their forms -->

```text
<holograph>/
  holograph.cosm                    the self: oes: ascribe/1, id ascribe/<hid>, a handle, pseudonyms, sample,
                                    the releases it has made, its morph volumes
  A/ B/ C/ E/ I/ O/ Q/ S/ U/ Y/     ten containers of the self, one kind of node each
  F/                                the forms the nodes anchor to, the polyforms that combine them, declared relations
  D/                                the dialectic's questions and sessions: the holder's, and never released
  **/.ascribe-private               a marker: what ingest, packages, transfer and projections leave behind (section 11)
<holograph>.morph.cosm              beside the folder: the holder's morphs, a thym/1 volume (section 14.5)
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
- A holograph is filled in by the **dialectic**, the core's way of asking a person and recording what they say
  (section 8), and by reading the holder's own texts, each node so read a candidate until the holder accepts it
  (section 9).
- Nothing about the person that would identify them has a place in the schema. A check warns on what reads like it,
  and a filter keeps private files and restricted nodes out of everything that leaves (section 11).
- The holograph stays with its holder. What leaves it, as an isograph, a cryptograph, match tokens or an isomorph,
  leaves by the holder's act: an isograph by a Thym program the holder runs, the others made by the implementation
  (section 14); each release is recorded in the holograph (section 13).

---

## 3. The design rules

<!-- atem: eight rules every part of Ascribe answers to -->
1. **No name is needed.** A holograph describes a self well enough that a name adds nothing. The catalog carries a
   pseudonymous handle and no name.
2. **No personal data, three ways.** *Schema*: there is no kind and no field for a name, an email address, a phone
   number, a postal address, a birth date, a government id or an employer's legal name. *Lint*: the `no-pii` check
   warns on what reads like any of them, anywhere in the volume, comments included, and never refuses inside the
   holograph (section 10); at a projection it is an error, and a release is refused while it stands (section 14).
   *Filter*: a `.ascribe-private` marker and `visibility: restricted` keep files and nodes out of everything that
   leaves (section 11).
3. **Every node is about something.** A node anchors to a form or a polyform that exists (`form-anchored`), so that two
   nodes about the same thing are seen to be.
4. **One grammar for both subjects.** The envelope is Comprise's, plus six fields of Ascribe's own (section 6), so that
   Thym's moves read a holograph as they read a Holotype.
5. **The author shapes it.** Hierarchy, branches, links, dates, valence and strength are optional and the author's.
   The checks hold only what must hold: an anchor, a declared relation, a well-formed `when`, a strength in range.
6. **Nothing of another person.** A reference never points into another person's holograph. People in a life appear by
   role ("a retired harbour pilot") or by a pseudonym the catalog declares.
7. **The holder releases.** Nothing in a holograph is public by default (`visibility` is `internal` when absent), what
   is released is released by a program the holder runs, and every release is recorded in the holograph.
8. **Nothing without the holder's word.** An answer, a candidate read from a text, a release: each becomes part of the
   holograph, or leaves it, only by the holder's own act.

---

## 4. The holograph

<!-- atem: the folder, its catalog, its module files, its ids and paths -->

### 4.1 The volume

A holograph is a folder, laid out as a Holotype's atoms are, minus the part level: one person, one volume, so the module
folders sit directly beside the catalog.

| Place | Holds |
|---|---|
| `holograph.cosm` | the catalog, the self; it may carry a few nodes of any module in its own `nodes:` |
| `<module>/` | `A/` `B/` `C/` `E/` `I/` `O/` `Q/` `S/` `U/` `Y/` for the ten kinds, `F/` for forms, polyforms and relations, `D/` for the dialectic's questions and sessions; a reader reads either case and a writer writes the capital |
| `<module folder>/**/*.cosm` | module files, at any depth, each a mapping with a `nodes:` list |
| `.ascribe-private` | a marker, anywhere below the catalog (section 11) |

A node is written in its own module's folder or in the catalog's `nodes:`; a node elsewhere fails `id-module`, which an
Ascribe reader holds to the module folders because the generic reader places module folders only under parts
(section 10.1). Every `.cosm` file below the catalog's folder is read as a module file, so a file of another format,
a morph volume included, is kept beside the folder and never inside it.

### 4.2 The catalog

| Key | Holds |
|---|---|
| `oes` | `ascribe/1`; a `holograph.cosm` without it is refused |
| `macrocosm` | reserved ([MacroCOSM OES](https://macro.cosmoes.org/), its section 5.6) |
| `id` | `ascribe/<hid>`: the hid is twenty-six characters of lowercase base32 (`a`–`z`, `2`–`7`), the shape of a Comprise Connect `hid` |
| `handle` | a pseudonymous handle: lowercase words joined by hyphens (`salt-and-crumb`), never a name |
| `summary` | one line, optional; people appear in it by role, never by name |
| `sample` | `true` on a fixture or a demonstration, never on a real person's holograph |
| `visibility` | `public`, `internal` or `restricted`; `internal` when absent |
| `pseudonyms` | the stand-in names the author uses for the people in their life ("Wren", "the Captain"), so that the `no-pii` check reads them as declared rather than as personal names |
| `releases` | optional: the record of every release the holder has made, oldest first (section 13); absent, none has been made |
| `morphs` | optional: the file names of the holder's morph volumes, each kept beside the holograph's folder (section 14.5) |
| `nodes` | items, when the catalog carries any |

A catalog never holds the person's name, an email address, a phone number, a postal address, a birth date, a government
id or an employer's legal name. A catalog `name` key reads as a personal name to the `no-pii` check (a holograph names
no one); an item's `name` is the item's own. The reader titles a holograph by its `handle`. A holograph written before
`releases` and `morphs` were catalog keys reads unchanged, and a reader that does not know the two keeps them as unknown
catalog keys.

### 4.3 Ids and paths

An item's id is `<module>:<kind>/<slug>`: `A:affinity/sourdough-baking`, `Q:quale/starter-smell`,
`F:form/celestial-navigation`, `F:polyform/slow-crafts`, `F:relation/learned-in`, `D:question/ascribe-a1`,
`D:session/session-3`. Inside its own volume an id is written bare. A path respells an id through the manifest's
levels, `<module>/<kind>/<slug>#<field>` (`A/affinity/sourdough-baking#strength`), and a URI qualifies it,
`oes:ascribe/<hid>/<path>`, the catalog id without `ascribe/` standing for the database. The slug grammar and the
refused path forms are MacroCOSM's ([MacroCOSM OES](https://macro.cosmoes.org/), its section 11.2), with the module
segment one of `A B C E I O Q S U Y F D`.

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

enough's sample holograph, `sample-self`, is the same self at full size, in folders: every module of the self,
twenty-six items, one open question (sea glass, which FEED does not have).

---

## 5. The ten containers and the forms

<!-- atem: ten kinds of node, one per module, and their forms -->

### 5.1 The containers

Each container holds one kind, named for the singular of the module, and the letter is the kind's initial.

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

Two more modules sit beside the containers and are not the self: F, the forms (section 5.2), and D, the dialectic's
questions and sessions, which the core declares and every format inherits (section 8). Ascribe's own check
`form-anchored` holds only the ten kinds, never an item of D.

### 5.2 The forms

Module F, *Forms*, holds the things a self is about and how they combine. Forms are shared roots, not nodes of the self:
they anchor nothing and need no form of their own.

| Kind | What it is | Its own fields |
|---|---|---|
| `form` | one thing a self can be about | `feed`: `{word, pos, origin}` (`origin` is `feed` or `user`) when the form is one word FEED has, else `{pending: "not in FEED"}`; `wiki`: an encyclopedia article's title or URL; `when` |
| `polyform` | several forms taken together | `forms`: the forms it combines; `links`: `{from, rel, to}` between them; `feed`, `wiki`, `when` |
| `relation` | a relation the author declares beyond the starter list | `name` and `summary`, which give its sense; links name it by its slug (section 7) |

Metadata on a form is global: every node anchored to it shares it. Metadata on a node belongs to that node alone. A form
with a `wiki` names a public subject, and its prose is not read for personal names (section 10).

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
| `provenance` | `mode`, `sources`, `confidence` (a number from 0 to 1: how sure the person is) and `state` (`known`, the default, `pending`, `not-disclosed`, `stale`); `sources` name a dialectic session (`D:session/session-3`, or the earlier spelling `session-3`), a text the author wrote (`notes.md#L3-L7`, or `notes.md#sha256:<digest>` for a candidate read from it, section 9), or `self` for what they wrote down directly |
| `pending` | open questions on the item |
| `links` | typed links (section 7) |
| `span` | where in a text the node was read: `{lines: "12-18"}`, or `{start, end}` of up to sixty characters each |
| `form` | what the node is about: one `F:form/<slug>` or `F:polyform/<slug>`; every node of the ten kinds carries one |
| `of`, `parts` | the node this one is a child of, and the node's children in order: a hierarchy, a branch or a flat list, as the author likes |
| `when` | a date (`2014-06-03`), a year (`2014`) or an era word (`childhood`, `2010s`, `university`); absent, the node is not on the timeline |
| `valence` | `for`, `against` or `mixed` |
| `strength` | a whole number from 1 to 5 |
| `made` | `{move, run, step, engine}`: the Thym move that made the item, or `{move: none}` for a hand-made one ([Thym](https://thym.cosmoes.org/), its section 5.3) |

Required: `id`, `type`, `name`, `summary`, `provenance`. The provenance modes are Comprise's list (`dialectic`,
`net-scan`, `system-scan`, `integration`, `structured-intake`, `manual`, `derived`, `asserted`, `archetype`,
`catalogue`, `directory`, `accounting`). An open question is `{pending: "<the question>"}`, answered by the person;
the sentinels are `none` and `self`; unknown fields are allowed and kept. `valence` and a FEED grounding's `origin` are
closed lists. Two fields the dialectic writes are kept like any unknown field: `withheld`, the fields the holder
declined to answer (section 8.5), and, inside `provenance`, `answered`, the session and confidence of each field an
answer filled.

---

## 7. Links and relations

<!-- atem: a starter list of relations, and the ones an author declares -->
A typed link is `{rel, to}`, as in [MacroCOSM OES](https://macro.cosmoes.org/), its section 9.4. Its `rel` is one of the
starter relations or a relation the holograph declares:

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

## 8. The dialectic, applied

<!-- atem: the core's questions and sessions, asked of one person about themselves -->
<!-- term: dialectic -->
The **dialectic** is the core's one way of asking a person what something means and recording what they say: questions
and sessions in module D, two atomic runs with a person between them, and the Thym moves `question`, `record` and
`settle` ([MacroCOSM OES](https://macro.cosmoes.org/), its section 18.6; [Thym](https://thym.cosmoes.org/), its section
22). This section says how a holograph uses it. Every rule of the core holds; Ascribe adds what a holograph needs.

### 8.1 The bank

A manifest's `dialectic:` key holds **banks** of opening questions. Ascribe's manifest holds one, read as the bank named
`ascribe`: four questions for each module of the self and four for the forms, forty-four in all, in plain words and in
no one's voice. Each question is an entry about its module, asked of the holograph once (`about: <letter>`), with
`kind: text`, `to: holder` and `why: missing`; entry ids are `A1`, `A2` and on, by position, so a question raised
from the first says `raised.from: ascribe/A1`.

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

Besides the bank, questions are raised by rule, as the core raises them: one for each `{pending: …}` in the holograph,
and one for each node whose `provenance.state` is `pending` or whose confidence is below 0.5 (`why: unsure`).

### 8.2 Choosing and putting a question

Every question in a holograph is `to: holder`: no one else answers for a self. A question is put in one of three ways.

| Way | How | The session records |
|---|---|---|
| a person working alone | the holder picks a module, or takes the next open question, and answers in their own time | `through: person` |
| an agent | a readvisor puts one or two questions at a time in conversation, and records the answers the holder gives | `through: agent`, with the agent's `model` |
| a Thym program | the holder runs a program whose `question` step lands questions; the holder answers; a second run's `settle` step folds the answers in | `through: person` or `agent`, as the answers were given |

Which bank questions come first is the asker's choice: a writer should offer the modules with the fewest nodes first
and never put a question whose entry the holder has declined (section 8.5) unless the holder asks for it. One open
question stands for each bank entry and each item or field at a time (the core's `no-duplicate`). A session's `with`
names the holder by the role word `holder` and describes them by nothing else.

### 8.3 What an answer writes

An answer to a bank question writes a **node** in the container the question belongs to, or, for a question of the
forms, a form. `settle` writes it, from the answer, after `record` has kept the holder's words verbatim on the question:

- `name`: a few words of the holder's own, naming the node; `summary`: the answer, one line, people in it by role or
  by a declared pseudonym;
- `form`: the form the answer is about, found as section 8.4 says;
- `provenance: {mode: dialectic, sources: [D:session/<id>], confidence: <how sure the person is>}`, the confidence
  the holder gave with the answer, and `1` when they gave none and stated it plainly.

An answer to a question about a field (`<node>#when`, `<node>#strength`) fills that field; the node keeps its mode,
`provenance.sources` gains the session, and `provenance.answered` gains the field with its session and confidence. A
write that would add a check error is not made, and a `why: counter` question is raised instead.

The earlier spelling of a session source, `session-<n>` (`sources: [session-1]`), stays valid: it names
`D:session/session-<n>` whether or not the holograph holds that record. A writer writes `D:session/<id>` and a
`D:session` item for every new session, and a new session's number skips every number a source already cites.

A question, its session and an answer, as a fragment:

```yaml
# D/session-3.cosm
nodes:
  - id: D:session/session-3
    type: session
    name: An evening session
    summary: Three questions on what the holder goes back to.
    at: 2026-11-05T19:30:00Z
    with: {to: holder, who: the holder}
    through: agent
    model: g40-04
    asked: [D:question/ascribe-a1]
    answered: [D:question/ascribe-a1]
  - id: D:question/ascribe-a1
    type: question
    name: What do you go back to?
    summary: The first opening question of the affinities.
    about: A
    asks: What do you go back to, again and again?
    why: missing
    kind: text
    to: holder
    raised: {by: bank, from: ascribe/A1, at: 2026-11-05T19:30:00Z, run: 2026-11-05-1930-7e1a}
    state: answered
    answers:
      - {at: 2026-11-05T19:34:00Z, by: holder, says: "Sourdough. I keep a starter going and bake twice a week.", value: "Baking sourdough from a starter kept going for years.", confidence: 1, session: D:session/session-3}
    settled: {at: 2026-11-05T19:40:00Z, run: 2026-11-05-1940-c4d2, wrote: [A:affinity/sourdough-baking]}
```

### 8.4 Form discovery and follow-up questions

A node needs a form. `settle` looks for one in this order: a form or polyform of the holograph the answer is plainly
about; a new form for one word FEED has, `feed: {word, pos, origin: feed}`; and, for anything else, a new form whose
`feed` is `{pending: "not in FEED"}`, named in the holder's words. A word not in FEED is an open question, never an
invented form: no writer grounds it in a sense FEED does not give, and the holder may answer it later with a
definition or an encyclopedia article (`wiki`). The form is found from the holder's own words for what the answer is
about, or from a thing the answer names whole, never from a word guessed out of a sentence. Where the answer names no
thing at all, the node is not written, and a follow-up asks what it is about: a question about the bank question
(`about: D:question/<its id>`, raised from `settle`), whose answer settles both.

After a node is written, a writer may raise **follow-up questions** about its optional fields, each `to: holder`,
`why: missing`, about `<node>#<field>`:

| Field | Asks | `kind` |
|---|---|---|
| `form` | What is this about, in a word or two? | `text` |
| `when` | When was this, roughly: a date, a year, or a time of life? | `date` |
| `valence` | Does this draw you, put you off, or both? | `choice`: `for`, `against`, `mixed` |
| `strength` | How strongly, from 1 to 5? | `number`, range 1 to 5 |

A follow-up is never put twice about one field, and a field the holder left empty stays empty: the author shapes the
holograph (section 3).

### 8.5 Not knowing, and not saying

| The holder says | The question | The holograph |
|---|---|---|
| "I don't know" | `unknown`, the answer `value: null` and their words in `says` | on a field, the field stays `{pending: "<their words>"}`; on a bank question, nothing is written |
| they would rather not say | `declined`, the answer `declined: true` | on a field, the node gains `withheld: [<field>]` and `provenance.state: not-disclosed`; on a bank question, nothing is written, and the bank does not put that entry again unless the holder asks |
| nothing; they skip it | stays `open`; the session lists it as skipped | nothing |

A refusal is never asked again in other words, and nothing a holder declined is inferred from anything else.

### 8.6 The dialectic stays with the holder

Module D holds the holder's own words. A holograph's D items are the holder's and never leave it: every projection,
package and ingest leaves module D out, and only a transfer of the whole holograph into the holder's own keeping (a
backup, a second machine) carries it (section 11).

---

## 9. Reading a person's own texts

<!-- atem: the holder's own writing proposes candidate nodes; the holder decides -->
A holder may have their own writing read for what it says of them: letters, a journal, essays, notes. The text is
decompiled to a **fabulan**, the fabula of narrative and nonfiction prose
([MacroCOSM OES](https://macro.cosmoes.org/), its section 18.4), and from the fabulan a reading proposes **candidate**
nodes of the ten kinds: what the text shows its author drawn to, believing, worried by, living through, wanting to
know, thinking, feeling, able to do, understanding and longing for.

**Only the holder's own texts.** A reading is begun only by the holder, over texts the holder names as their own. A
text about the holder written by anyone else is never read into a holograph: that would be an outsider's graph of a
person.

<!-- term: candidate -->
A **candidate** is an ordinary node of its kind, proposed by a reading and not yet the holder's, written with:

| Field | Holds |
|---|---|
| `provenance` | `{mode: derived, sources: ["<text>#sha256:<the text's digest>"], confidence: <the reading's>, state: pending}` |
| `span` | where in the text it was read: `{lines: "12-18"}`, or `{start, end}` of up to sixty characters each |
| `form` | a form of the holograph, a new form found as section 8.4 says, or `{pending: "<what it seems to be about>"}` |
| `made` | the move, run and engine that proposed it ([Thym](https://thym.cosmoes.org/), its section 5.3) |

Its `name` and `summary` say what the text shows in the reading's words, and name people only by role or by a declared
pseudonym; the text's own names never enter the holograph. A candidate is proposed only from what the text says
(the core's `no-invention`), and each carries the span that shows it.

**The holder decides.** Each candidate gets a question about it, `about: <the candidate's id>`, `why: unsure`,
`to: holder`, `kind: choice`, `options: [yes, no, partly]`, asking whether it is so:

| Answer | `settle` writes |
|---|---|
| `yes` | the candidate becomes a node of the self: `provenance.state` is removed, `sources` gain `D:session/<id>`, `confidence` is the holder's |
| `partly` | as `yes`, then a follow-up `text` question about the candidate's `summary`, so the holder says it their way |
| `no` | the candidate is removed; its question is settled with `wrote: []`, keeps the answer, and is not raised again |
| "I don't know", a refusal, or nothing | the candidate stays a candidate |

A candidate is not part of the self until the holder says so. Every lens draws it as pending, `no-pii` reads it as it
reads any item, and no projection, package or match token ever carries one (section 14). Nothing is written into a
holograph by a reading except its candidates and their questions, and nothing becomes the holder's except by their
answer.

The step that proposes candidates asks the model; it is the move `propose`, declared in Ascribe's manifest:
`propose f with h` takes the text's fabulan and, `with` it, the holograph, and gives the candidates and their questions,
which the program lands with `gather` ([Thym](https://thym.cosmoes.org/), its section 6.3). Its contract is
`no-invention` and `provenance`, the move itself holds every candidate to Ascribe's own checks (section 10), and its run
lands every candidate and question or none.

---

## 10. Checks

<!-- atem: MacroCOSM's generic checks, the dialectic's, and seven of Ascribe's own -->

### 10.1 The generic checks

The manifest selects `load` and the envelope checks `duplicate-id`, `id-grammar`, `id-module`, `type`, `type-prefix`,
`identity-min`, `provenance`, `status`, `visibility`, `ref-grammar`, `ref-unresolved`, `closed-list`, `pending-shape` and
`catalog-key` ([MacroCOSM OES](https://macro.cosmoes.org/), its section 12.2). An Ascribe reader holds two of them to what
the generic reader cannot read from the manifest: `id-module` to the module folders (section 4.1), and `catalog-key` to
the hid, the handle and the shape of `pseudonyms`. A holograph that carries module D also passes the dialectic's
checks ([MacroCOSM OES](https://macro.cosmoes.org/), its section 18.6).

### 10.2 Ascribe's own

An Ascribe reader runs them after the generic ones, in one report. A generic reader does not run them.

| Check | Severity | Catches |
|---|---|---|
| `form-anchored` | error | a node of the ten kinds with no `form`, a `form` that names no item, or one that names something other than a form or a polyform; a `form` that is an open question is a note |
| `relation-declared` | error | a link whose `rel` is neither a starter word nor a declared relation; a declared relation that repeats a starter word |
| `when-shape` | error | a `when` that is not a date, a year or an era word |
| `strength-range` | error | a `strength` that is not a whole number from 1 to 5 |
| `release-shape` | error | a `releases` entry that lacks a field section 13 requires, holds a field section 13 does not name, or whose `as`, `epoch` or digests are not in their shape; a `morphs` entry that is not a bare file name ending `.morph.cosm` |
| `no-pii` | warning, never an error in the holograph | what reads like personal data (section 10.3) |
| `private-marker` | note | what a `.ascribe-private` marker would keep out of everything that leaves (section 11) |

The manifest's `checks.severity` may move a severity; `no-pii` may be lowered to a note and never raised above a
warning in the holograph, while the schema and the filter still hold. At a projection `no-pii` is an error whatever
the manifest says (section 14.1).

### 10.3 What reads like personal data

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

## 11. The private filter

<!-- atem: what every ingest, package, transfer and projection leaves out -->
The manifest declares what leaves a holograph and what stays, the way the home file system leaves a Holotype's private
side behind; this section is the rule, and an implementation applies it.

**Where it applies.** To everything that takes any part of a holograph off the holder's own copy:

| Use | What it is |
|---|---|
| **ingest** | another volume, a library or an index copies the holograph, or part of it, in |
| **package** | a Thym package carries it, sealed or not, a cryptograph included ([Thym](https://thym.cosmoes.org/), its section 15) |
| **transfer** | the holograph, or part of it, is copied off the holder's machine, a backup included |
| **projection** | a program projects it: an isograph, match tokens, an isomorph (section 14) |

**What it withholds.**

- **Marker:** `.ascribe-private`. Every file and folder beside a marker, with everything below them, the marker
  included. A marker beside the catalog withholds the whole holograph: nothing leaves.
- **Restricted:** every node, form, polyform, relation and dialectic item with `visibility: restricted`, wherever it is
  written. A kept file that holds one is written out again without it, as its `nodes:` in the COSM YAML subset, and
  without its comments, since a comment cannot be tied to the node it was beside.
- **Module D**, in every use but a transfer of the whole holograph into the holder's own keeping (section 8.6).
- **Candidates**, in every use: every candidate (section 9) and every question about one, the holder's own keeping
  included, since a candidate is not part of the self until the holder says yes.
- **The catalog's `releases:`**, in every use: it is the holder's own account of what left (section 13).
- **What it cannot read:** a symbolic link, and a `.cosm` file that does not parse, since either may hold what must be
  withheld.

**What it never drops.** Everything else, unchanged and byte for byte when its file holds nothing it withholds. A
reference to a withheld item keeps its id and gains no name; the filter never rewrites a kept item, never adds a
placeholder or a count for what it withheld, and never drops the catalog unless a marker sits beside it.

**A pure function of the folder.** The filter reads the holograph's folder and nothing else (no setting, no history, no
other volume) and gives the files that leave and their bytes; the same folder gives the same answer every time. It runs
before anything else in each use, so that a program, a check or a model never sees what it withholds.

`private-marker` reports, as a note, what each marker would withhold: the files, and how many nodes they hold, or "the
whole holograph" when the catalog itself is beside a marker. It withholds nothing.

---

## 12. Lenses

<!-- atem: self, graph and timeline, with the generic map and text tree -->
A holograph is drawn by the lenses its manifest declares and by MacroCOSM's generic ones
([MacroCOSM OES](https://macro.cosmoes.org/), its section 14). A reader applies visibility before it draws anything;
the private filter does not apply, since a lens draws for the holder on the holder's own copy.

| Lens | Kind | Draws |
|---|---|---|
| `self` | a mindmap | the self at a glance: a branch for each of the ten modules and a leaf for each node |
| `graph` | a flowchart | every typed link between the nodes and the forms, coloured by `valence`; a form `([ ])`, a polyform `{{ }}`, a relation `[/ /]` |
| `timeline` | a table, not a drawing | every node that carries a `when`, one row each (`when`, id, name, valence, strength), dates and years in order and era words after them |
| `map` | a flowchart (the generic lens) | every module, D included, with every reference field, every typed link and every `parts` and `of` |
| `tree` | a flowchart (the generic lens) | the nodes joined by `parts`, when any node carries `parts` |

The text tree ([MacroCOSM OES](https://macro.cosmoes.org/), its section 14.2) lists the holograph module by module
and item by item, as text. In the reader's order a holograph has the lenses `self`, `graph`, `map` and, when its nodes
carry `parts`, `tree`; `timeline` and the text tree are drawn by their own renderers. A candidate (section 9) is drawn
like any node, with its pending state shown.

---

## 13. Releases

<!-- atem: the holograph's own record of everything that has left it -->
<!-- term: release -->
A **release** is one act of the holder's by which something left the holograph: an isograph, a cryptograph, a list of
match tokens or an isomorph (section 14). Every release is recorded in the holograph, in the catalog's `releases:`
list, oldest first. The record is the holder's own and private: the private filter withholds it in every use
(section 11). It is what Thym's `released` check reads:
nothing is in a package's `graph.cosm` without a release recorded in the holograph
([Thym](https://thym.cosmoes.org/), its section 15). It is the shape of a Holotype's isotype release in
[Comprise OES](https://comprise.cosmoes.org/), its section 11.3, kept in a file because a holograph has no database.

| Field | Holds | Required |
|---|---|---|
| `epoch` | the epoch the release carries: a quarter (`2026-Q4`), a month (`2026-11`) or a week (`2026-W45`), never the day of an edit | yes |
| `as` | what left: `isograph`, `cryptograph`, `tokens` or `isomorph` | yes |
| `program` | `{name, sha256}`: the program that made it, and the sha256 of its `.thym` bytes | yes |
| `trace` | `{run, sha256}`: the run's id, and the sha256 of its trace file as the run wrote it, which stays on the holder's machine | yes |
| `at` | when the release was made: a timestamp, kept in the holograph and never in what left | yes |
| `sha256` | the sha256 of the bytes that left: the isograph's canonical JSON, the sealed file, the token list or the morph volume | yes |
| `items` | the ids of the holograph's items that left, sorted, and for an isomorph the morph's id (`M:morph/<slug>`); `all` for a cryptograph of the whole holograph | yes |
| `for` | `{path, sha256}`: the text a package's excerpt was released for | when the release is a package's `graph.cosm` |

A record never holds what was withheld: no id of a withheld item, no count of them and no reason. It never holds a
key, a token's key or the party a cryptograph was handed to. A record is appended and never rewritten; a release
withdrawn later stays recorded, since what left cannot be recalled.

A release, as a fragment of the catalog:

```yaml
releases:
  - epoch: 2026-Q4
    as: isograph
    program: {name: open-self, sha256: '2222222222222222222222222222222222222222222222222222222222222222'}
    trace: {run: 2026-11-05-1415-ab12, sha256: '3333333333333333333333333333333333333333333333333333333333333333'}
    at: 2026-11-05T14:15:00Z
    sha256: '4444444444444444444444444444444444444444444444444444444444444444'
    items: [A:affinity/fast-bread, F:form/sourdough]
```

A holograph with no `releases` has released nothing, and every holograph written under `ascribe/1` reads as such until
its holder releases something.

---

## 14. Projections: the isograph, the cryptograph, match tokens, morphs

<!-- atem: what may leave a holograph, in what shape, and by whose act -->
What leaves a holograph leaves by its holder's act, after the private filter (section 11), and is recorded as a release
(section 13). In this edition an isograph is made by a Thym program the holder runs ([Thym](https://thym.cosmoes.org/),
its section 18); a cryptograph, an isomorph and match tokens are made by the implementation at the holder's act, and
Thym moves for them are reserved for a later edition. Every projection keeps four rules:

1. **Default-deny.** Only what this section names may appear; anything else is refused, never filtered.
2. **Withhold, never falsify.** What does not leave leaves no mark: no placeholder, no gap, no count.
3. **Nothing of the dialectic and nothing pending.** No D item, no candidate (section 9), no node whose
   `provenance.state` is anything but `known`, and nothing below confidence 0.5.
4. **No personal data.** `no-pii` runs over what the filter keeps and over the projection itself, at the severity of
   an error, and a release is refused while any finding stands.

There is no paratype of a person: no outsider's graph, ever.

### 14.1 The isograph

<!-- term: isograph -->
An **isograph** (`ascribe-isograph/0`) is a person's public projection: a separate document with a fixed schema,
computed from the holograph by rules, one rule per field, and narrowed by the holder's program, as a company's
isotype is in [Comprise OES](https://comprise.cosmoes.org/), its section 11.3. It is the dial for a person
([Thym](https://thym.cosmoes.org/), its section 18, writes the company's): `project h as isograph`, under a program
that only chooses, and can keep more back but never add a row, a word or a model's telling. A field added to the model
later never flows into it by itself.

```text
{isograph, hid, handle, epoch, sample, program, run, self}
self[]:  kind, form, valence, strength, when, marking
```

| Field | Derived from |
|---|---|
| `isograph` | `ascribe-isograph/0` |
| `hid` | the catalog's id without `ascribe/` |
| `handle` | the catalog's `handle`: the pseudonym, never a name |
| `epoch` | the release's epoch (section 13) |
| `sample` | `true` when the catalog says so; absent otherwise |
| `program` | as the release records it: `{name, sha256}` |
| `run` | the id of the run that made it; the release record carries its trace's digest (section 13) |
| `self[].kind` | the node's kind, one of the ten |
| `self[].form` | the FEED word of the node's form (its `feed.word`, where `feed.origin` is `feed`); for a polyform, the sorted list of its forms' words, at most eight, every one so grounded |
| `self[].valence` | the node's `valence`, when it has one |
| `self[].strength` | a band of the node's `strength`: `slight` (1 or 2), `moderate` (3), `strong` (4 or 5) |
| `self[].when` | the decade of a date or a year (`2010s`), or an era word already in that shape; any other era word is left out |
| `self[].marking` | `stated` |

**Which nodes may appear.** A node of the ten kinds whose `visibility` is `public`, whose `status` is absent or
`active`, whose provenance is known at confidence 0.5 or more, that the filter keeps, and whose form, or every form of
whose polyform, is grounded in FEED with origin `feed`. Nothing else of a holograph may appear: no node's `name`,
`summary`, `links`, `of`, `parts`, `span` or `provenance`, no id, no form named only by an encyclopedia article or in
the holder's own words, no relation, no pseudonym, and not the catalog's `summary`. Free text never leaves, since free
text can identify.

**Its rules.**

- **Assertions, not measurements.** No number of anything; the only digits are in the epoch, a decade, the hid, the
  run's id and the digests.
- **Bands.** `strength` leaves only as its band, and `when` only as its decade.
- **Sorted.** `self` is sorted by the order of the modules (A B C E I O Q S U Y), then by `form`, `valence`,
  `strength` and `when`, so that file order leaks nothing. Two nodes that give the same entry give it once, and
  nothing counts them. At most twenty entries of each kind; at most 64 kilobytes.
- **One per epoch.** A holder releases at most one isograph in an epoch; one who releases more often chooses a shorter
  epoch.
- **Stated and verified.** Every entry is marked `stated`: the holder's own word. **`verified`** is reserved for what a
  registry can attest of the holder, and of nothing in the self: that one real person holds the key this isograph is
  signed with, and that this holograph has one holder. Ascribe lists nothing as derivable, so Thym's
  `verified-only-where-derived` refuses every `mark … as verified` in a program over a holograph, and an isograph made
  by its holder alone marks everything `stated`. A reader refuses an isograph that carries `verified`.
- **Canonical JSON.** The document is JSON with its keys sorted, no space between tokens and UTF-8 without a
  byte-order mark; the release's `sha256` is over those bytes.

The registry itself, the signing of an isograph and the key it is signed with, an index of isographs, and further
fields a holder may open one at a time (each opt-in and marked `stated` or `verified`) are reserved for a later
edition. An isograph is the holder's to keep or hand on; nothing in this edition publishes one.

The isograph of the holograph of section 4.4, were its node `A:affinity/fast-bread` of section 5.2 added and marked
`visibility: public` (the two other nodes anchor to a form FEED does not have, and stay):

```json
{"epoch":"2026-Q4","handle":"salt-and-crumb","hid":"aej6l5qrka6c6btarfiy2f7vnj","isograph":"ascribe-isograph/0","program":{"name":"open-self","sha256":"2222222222222222222222222222222222222222222222222222222222222222"},"run":"2026-11-05-1415-ab12","sample":true,"self":[{"form":"sourdough","kind":"affinity","marking":"stated","strength":"moderate","valence":"against"}]}
```

A package's `graph.cosm` ([Thym](https://thym.cosmoes.org/), its section 15) is an isograph made for one text: the
same keys, written in the COSM YAML subset, its `self` narrowed to what the program emitted for that text, and recorded
as a release `as: isograph` with `for` naming the text.

### 14.2 The cryptograph

<!-- term: cryptograph -->
A **cryptograph** is the holder's encrypted share: a Thym package in its encrypted form
([Thym](https://thym.cosmoes.org/), its section 15.3) of the holograph or of a projection of it, handed with its key to
one chosen party. It is, for a person, the sealed package of [Comprise OES](https://comprise.cosmoes.org/), its section 11.5.

- **Two kinds.** *The whole holograph*: one `holograph` row per file the filter keeps, at its own path, module D left
  out. *A projection*: `projection` (`projection.json`, an `ascribe-isograph/0` document), `program` (`program.thym`)
  and `trace` (`trace.cosm`, the run's trace as the run wrote it). Nothing else is a cryptograph: no key, no morph's
  evidence, nothing the filter withholds.
- **The seal.** The cipher of Thym's encrypted form under a fresh data key for the package; its catalog's `hid` is a
  random id of its own, never the holograph's, so that a cryptograph cannot be joined to the holder's isograph.
- **The key** is shown once, stored nowhere, and handed by the holder to the party of their choosing. A lost key is a
  lost cryptograph.
- **The notice** says what it is and names no one.

Hosting a cryptograph for others to fetch is reserved for a later edition, with the registry.

### 14.3 Match tokens

<!-- term: match token -->
A **match token** lets a search find a cryptograph without reading it: a consented, salted digest of one chosen form,
`{about, token}`, `token` being the lowercase hex HMAC-SHA256 of `about`, a line feed and the value, under a key made for
one cryptograph and never its package key.

| `about` | The value |
|---|---|
| one of the ten kinds: `affinity`, `belief`, `concern`, `experience`, `interest`, `opinion`, `quale`, `skill`, `understanding`, `yearning` | the slug of the node's form, and, when the node carries a `valence`, a space and the valence word: `sourdough against` |
| `form` | the slug of a form the holder chose, whatever nodes anchor to it |

A token is made only for a form grounded in FEED with origin `feed`, and only for a node the isograph's rules let
appear (section 14.1), so that a value is a public word whose meaning anyone can work out. Making tokens is the holder's
act and is a release (`as: tokens`): the holder chooses each form, and nothing is made a token by default. The list is
`{tokens: ascribe-tokens/0, of: <the cryptograph's hid>, epoch, entries: [{about, token}]}`, its entries sorted by
`token`. A cryptograph handed over directly has none. Serving tokens, and who holds the key a search needs, are
reserved for a later edition, with the registry.

### 14.4 The bridge to Comprise

A bridge between a company's Holotype and a person's holograph, an employer's *seek* for a role shaped like an isograph
and answered by a candidate's isograph, both speaking Thym, is reserved for a later edition; the common envelope makes
it possible.

### 14.5 Morphs

<!-- term: holomorph -->
A **holomorph** is the holder's morph: the ten scales of Thym's morphs measured from the holder's own texts, as a
departure from the null morph, sharpened over a corpus, with any scale the holder pins by hand winning
([Thym](https://thym.cosmoes.org/), its section 13.4). It is an `M:morph` item in a `thym/1` morph volume kept beside
the holograph's folder, never inside it (section 4.1): `<holograph folder>.morph.cosm` for the first, and any name
ending `.morph.cosm` for more, each named in the catalog's `morphs:` list. Its `derived.from` holds the digests of the
holder's own texts only, as section 9 reads them; a text by anyone else is never measured into it.

<!-- term: isomorph -->
An **isomorph** is a holomorph the holder chose to share: the same shape, marked `shared`, released by a program and
recorded as a release `as: isomorph`. It leaves with its `scales`, `toward`, `pinned` and `confidence`, and never with
its `evidence` or `derived.from`, which quote and point to the holder's texts. A holder may keep several, one for
letters and one for work.

---

## 15. The command line

<!-- atem: enough's command that checks a holograph folder -->
enough, the reference implementation, offers one command that checks a holograph. It is given here as the example of how
the checks are run, not as a rule of the format:

```text
python -m enough.ascribe lint <folder | holograph.cosm> [--json]
```

It loads the holograph through enough's MacroCOSM reader, runs the generic checks and Ascribe's own, prints each problem
as `<severity> <check> <item> (<file>): <message>`, and ends with one line: `ascribe/1: <n> items, <e> errors, <w>
warnings, <k> notes, <q> open questions`. It exits 0 when there is no error (warnings and notes do not fail it) and 1
otherwise. It reads only the folder it is given and writes nothing.

On enough's fixtures:

```text
sample-self                   ascribe/1: 26 items, 0 errors, 0 warnings, 0 notes, 1 open questions      exit 0
bad/pii                       ascribe/1: 8 items, 0 errors, 7 warnings, 0 notes, 0 open questions       exit 0
bad/unanchored                ascribe/1: 3 items, 1 errors, 0 warnings, 0 notes, 0 open questions       exit 1
bad/undeclared-relation       ascribe/1: 3 items, 1 errors, 0 warnings, 0 notes, 0 open questions       exit 1
```

`bad/pii` carries one of each pattern, invented, and every one is a warning: a phone number, a birth date, a personal
name, an email address, an id-like run of digits, an `employer` field and a street address.

---

## 16. Conformance

<!-- atem: what a reader and a writer of holographs must do -->

### 16.1 A reader must

1. Read every holograph written under `ascribe/1`, from any edition of this text, and keep every unknown field and
   catalog key, `releases` and `morphs` included where it does not know them.
2. Read a session source in both spellings, `D:session/<id>` and `session-<n>`, as one session.
3. Run the generic checks the manifest selects and Ascribe's own (section 10), in one report, with `no-pii` never above
   a warning inside the holograph.
4. Apply visibility before drawing or showing anything (section 12).
5. Refuse an isograph that carries a field section 14.1 does not name, or the marking `verified`.

### 16.2 A writer must

1. Never write a name, an email address, a phone number, a postal address, a birth date, a government id or an
   employer's legal name, in any field, key or comment; write people by role or by a pseudonym the catalog declares.
2. Write a node only from the holder's own word: an answer, an accepted candidate, or what the holder wrote down
   (section 8, section 9); write an open question, never a guess, and never a form FEED does not have as if it did.
3. Read only the holder's own texts into a holograph, never a text about them by anyone else.
4. Apply the private filter (section 11) to every ingest, package, transfer and projection, before anything else reads
   the holograph.
5. Refuse a projection while `no-pii` finds anything in what the filter keeps or in the projection (section 14).
6. Keep module D, candidates and every node not known at confidence 0.5 or more out of every projection, package and
   ingest.
7. Record every release in the catalog's `releases:` before anything leaves, append records and never rewrite one, and
   never record what was withheld (section 13).
8. Keep a morph volume beside the holograph's folder, never inside it (section 14.5).

### 16.3 Where an implementation and this text disagree

Where an implementation and this text disagree, one of them is in error. The disagreement is settled by correcting the
one that is wrong, and the Changes appendix (section 17) records which was corrected, with the section it touched.

---

## 17. Changes

<!-- atem: what each edition changed, newest first, one line each -->
**Edition 0.6.0 · 2026-11-05.** Ascribe built out: what happens to a holograph after it is written is specified.

1. **The taxonomy.** Ascribe is one of the two MiniCOSMs; MacroCOSM OES is the OES with a core; Thym is the
   transcognition language that connects OESes. The stewardship sentence joins section 1.
2. **The rulings' markers are dropped**, with the sentence that explained them; this appendix records the rulings.
3. **The dialectic, applied** (section 8, was "The dialectic"): the core's questions and sessions in module D, `D/`
   beside the containers; the forty-four opening questions as the bank `ascribe`; how a question is put, what an answer
   writes, form discovery, four follow-up questions, "I don't know" and a refusal; D items never leave. The earlier
   session spelling `session-<n>` stays valid.
4. **Reading a person's own texts** (section 9, new): the holder's own writing, decompiled to a fabulan, proposes
   candidate nodes that become the holder's only by their answer; the move `propose`.
5. **The checks** (section 10): `release-shape` added; `no-pii` is an error at projection.
6. **The private filter applied** (section 11): to every ingest, package, transfer and projection; restricted items,
   module D, candidates and their questions, and the catalog's `releases:` withheld; a pure function of the folder; what
   it never drops.
7. **Lenses** (section 12, new): `self`, `graph` and `timeline`, with the generic `map`, `tree` and text tree.
8. **Releases** (section 13, new): the catalog key `releases`, the record Thym's `released` check reads.
9. **Projections** (section 14, was "Projections, by reference"): the isograph's fixed schema
   (`ascribe-isograph/0`), everything `stated` and `verified` reserved for a registry; the cryptograph; match tokens for
   a person (`ascribe-tokens/0`); morphs beside the holograph, with the catalog key `morphs`. The registry, an index of
   isographs, serving tokens and the bridge to Comprise stay reserved.
10. **Conformance** (section 16, new). The command line moves to section 15, Changes to 17, Withdrawn to 18.

No `ascribe/1` holograph changes meaning, and every one that was valid stays valid.

**Edition 0.5.4 · 2026-11-03.** The canonical edition at cosmoes.org. The name is *Ascribe*, without a number; the
edition is a field of the status line, and the declaration stays `ascribe/1`. The section "What is not built" is
withdrawn: the gaps it listed are stated where they fall, as reserved for a later edition (the process that asks the
dialectic's questions, in "The dialectic"; the filter that applies the private marker, in "The private filter"; the
bridge to Comprise, in "Projections, by reference"); Ascribe-Connect, isographs on an index and consented match tokens
stay named in "Projections, by reference" as what the projections are for. The section "Decisions in this version"
becomes this appendix. The reference implementation is named by its public repository; MacroCOSM OES and Thym are
cited at their cosmoes.org homes; where the text deferred to the code, it is normative. No rule of the format, no
check and no example changed.

**Edition 1 · 2026-11-02** (published as *Ascribe OES 1*; its rules settled 2026-11-01). The first edition, declaring
`ascribe/1`:

1. **Ten containers, one kind each**: A B C E I O Q S U Y, the kind the singular of the module's name and the letter
   its initial.
2. **Module F for forms, polyforms and declared relations.** Every node anchors to a form.
3. **The catalog is the self**: `holograph.cosm`, with the module folders beside it; a handle, pseudonyms and a sample
   flag, and no name.
4. **`when`, with `before` and `after`**: a date, a year or an era word, optional; order without dates by the two
   starter relations.
5. **`valence` and `strength`**: `for`, `against` or `mixed`; a whole number from 1 to 5.
6. **The dialectic's questions live in the manifest**; the process that asks them is reserved for a later edition.
7. **No personal data by schema, lint and filter; the lint warns and never refuses**, while the schema and the filter
   still hold.
8. **The declaration is `ascribe/1`.**
9. **Comprise's envelope**, so that one set of Thym moves works on both subjects.
10. **`links.starter`, not a closed `links.rels`**, so that declared relations pass the generic reader and
    `relation-declared` closes the list.
11. **No outsider's graph of a person, ever**: crypto- means encrypted, and there is no paratype of a person.

---

## 18. Withdrawn

<!-- atem: withdrawn in edition 0.5.4; see the Changes appendix -->
The section "What is not built" was withdrawn in edition 0.5.4; what it listed is specified in this edition or stated
where it falls as reserved for a later edition, and the Changes appendix records each step.

---

## Colophon

<!-- atem: copyright, the canonical edition and its source -->
Ascribe — Copyright © 2026 Graham Smith. All rights reserved. The canonical edition is published at
https://ascribe.cosmoes.org/; its source and history are at https://github.com/0gsd/cosmoes-site.
