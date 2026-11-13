# Thym

*Edition 0.6.0 · revised 2026-11-06 · cosmoes.org home: https://thym.cosmoes.org/*

*This edition describes the `thym/1` built-in and defines the language in two grammars; a program's version line, `thym 0` or `thym 1`, names the grammar it is written in.*

Thym is the transcognition language that connects OESes, with its compiler and its runtime: programs compose named
moves over values typed by density, carrying meaning from one volume to another, whether the volume is a text's fabula,
a folder of code, a document, a company's Holotype or a person's holograph. A compiler checks and plans a whole program
before anything runs, and a runtime walks the plan, asks a model only behind a contract, and traces every run so that it
replays. Thym's own volumes, `thym/1`, are a built-in of the core of MacroCOSM OES (https://macro.cosmoes.org/),
specified here, and MacroCOSM's words (item, kind, volume, catalog, module, check, lens, atem) keep their meaning here.

enough (https://github.com/0gsd/enough) is the reference implementation of the language, its compiler and its runtime.
Where an implementation and this text disagree, one of them is in error; the Changes appendix (section 25) records which
was corrected.

## Contents

<!-- atem: every section of this specification, in order -->
1. Provenance and the name
2. The model on one page
3. The design rules
4. Programs: the language
5. Values and types
6. Moves
7. Contracts and the six laws
8. Control flow, bindings, user moves, `use`
9. Errors: compile, plan, run
10. Programs as documents
11. The compiler
12. The runtime
13. The null morph, the ten scales, morphs
14. Readings
15. Packages
16. Context
17. The `thym/1` volumes and the `moves:` block
18. Projections: the dial as a program
19. Agent-free
20. Folders and code
21. Editing
22. The dialectic in a program
23. Models in a run
24. Conformance
25. Changes
26. Withdrawn

Colophon

## How to read this

<!-- atem: the rule words, the family of words, and what a block promises -->
**Must and may.** *Must* is a rule a conforming compiler or runtime keeps. *May* is a permission. *Should* is advice
the checks do not enforce.

**The family of words.** The suffix says what kind of subject; the prefix says the form.

| | the whole, private, held by its subject | the verified public duplicate | an outsider's guess, unverified | the owner's encrypted share | the style sheet |
|---|---|---|---|---|---|
| a company (Comprise) | **holotype** | **isotype** | **paratype** | **cryptotype** | — |
| a person (Ascribe) | **holograph** | **isograph** | — (never) | **cryptograph** | **holomorph** (private) · **isomorph** (shared) |

*holo-* the whole; *iso-* an equal, verified; *para-* beside, by another hand; *crypto-* hidden, by the owner. Crypto-
means encrypted everywhere, and there is no outsider's graph of a person.

**The words of a text.** A text's meaning has MacroCOSM's three densities: the **fabula** (the text's twin: order-free
material with stances and spans), the **short** (an entailment of the fabula) and the **atem** (one line, with
focus, push and pull). The author's text arranges the same material too, and is never called a short: the text entails
its fabula, and the fabula entails a short. Thym counts the text as a density as well, so a text has four (section
5.2). To decompile is to make a fabula from an input, and to compile is to make a short of a fabula: those are the
plain words, and in a program the moves are `derive` and `entail` (DocOES's byte-exact `enumerate` and `compile` keep
their names). Each of these steps is an entailment, the step that expands meaning by reducing data: the whole entails
what is made from it (MacroCOSM OES, its section 18.1). A fabula has a flavour, the value of its catalog's `flavour`: `fabulan` for prose,
`fabulap` for verse, `fabulac` for code (MacroCOSM OES, its section 18.4). A fabulac's short is a `cshort`, source code
rebuilt from it and never run, and its atem at depth is a `catem`, a text saying what a person can do with the program
(section 20). Thym adds three nouns and three verbs:

- a **reading** is an entailment of someone else's fabula in your morph, local and labelled (section 14);
- the **null morph** is the plainest entailment that conforms, Thym's reference (section 13);
- a **package** is the self-contained export of a text with its fabula, morph, context and released graph (section 15);
- to **transcode** is to move a value mechanically: a deterministic move, the same answer every time (`enumerate`,
  `compile`, `cut`, `project`, `band`);
- to **transcognize** is to re-represent a value by choices a mind makes: a move that asks the model, behind a
  contract (`derive`, `entail`, `atem`, `expand`, `null`, `morph`, `read`); the heavy lifting of re-cognition;
- to **transconceptualize** is to transcognize with a change of frame: another morph, language, audience or occasion.

Transcoding and transcognizing meet in entailment, and the line between them stays where it is. A projection
(`project`, section 18) is an entailment made by rule, and holds by construction. `entail` makes an entailment by a
model under contract, and what it makes holds only because its checks hold it: `coverage`, `no-invention` and
`stance-kept` (section 7.3).

Move, program, plan, trace and coprocessor are the words of the model itself; section 2 says what each one is. The
second grammar, `thym 1`, adds a few more: a `folder` (a directory tree read under one fixed rule, section 20), a
`line` and a `change` (section 21), a contract block (a check a program defines, section 7.5), and the dialectic's
questions and answers (section 22).

**Words on screen.** As in the MacroCOSM specification, the word a person reads comes first, and the word the files use
follows in parentheses where they differ. Thym's words are mostly the files' own: a statement of a program is a *step*
(`P:step`), a part of a plan is a *node* (`R:node`), and an entry of a trace is a *record* (`R:record`). A plan's node
is an item of kind `node`; it is not MacroCOSM's file word for an item.

**Blocks.** A block marked `thym` is one complete program file: it starts with its version line (`thym 0` or `thym 1`),
it compiles under a conforming compiler with the standard moves, and its plan is well formed. A block marked `cosm` is one complete `.cosm`
file that loads and lints clean. A block marked `yaml` is a fragment and may point outside itself. A block marked
`python` sketches an interface. A block marked `text` is grammar, a transcript or a picture.

---

## 1. Provenance and the name

<!-- atem: where Thym comes from, how it is said, and who keeps it -->

### 1.1 Lineage

MacroCOSM OES (https://macro.cosmoes.org/) gives one grammar for volumes of items: Comprise's Holotypes, the home file
system's catalogs (Canon), fabulas, documents. Everything a reader does with them (load, check, draw) is generic. Before
Thym, everything that *moves* meaning between them was not: deriving a twin, compiling a short, writing an atem and
projecting an isotype were each a function or a model prompt standing outside the format. Thym makes those moves
first-class (section 2), and so connects one OES to another: a program reads a company's Holotype and writes its
isotype, or reads a folder of code and writes its fabula.

Three precedents shaped it.

- **DocOES** (MacroCOSM OES, its section 18.5, https://macro.cosmoes.org/). A document is enumerated into items and compiled back byte for byte, so the
  written file stays the source of truth. A Thym program is enumerated the same way.
- **Lossy codecs.** A codec specifies the stream and the reference decoder, and leaves the encoder free. Thym specifies
  what a move must preserve (its contract) and leaves the model free.
- **The Ideal State Artifact** (Daniel Miessler, 2026). A thing is described by its ideal state in prose, its
  constraints and its decisions, with criteria that can be checked. A program's `why`, `must` and `decided` heads are
  that, and its contracts are the criteria.

### 1.2 The name

**Thym** is said *THIGH-m*: *thigh* with an m on the end, after Fukuyama's *thymos*, the part of the soul that wants to
be recognised. *Time* passes, if the speaker aspirates the T. The word is not an acronym and has no expansion. It
names re-cognition: a text re-known at another density, a company re-known in public, a person re-known without a
name.

### 1.3 Stewardship

Thym is stewarded by Verroes (Graham Smith). The text is licensed under CC BY 4.0, the author makes the OWFa 1.0
promise, and the names are not licensed (see the colophon). The specification is revised at its home, https://thym.cosmoes.org/; each
revision is an edition, and the Changes appendix (section 25) records what each edition changed. A program's version
line pins the grammar it is written in, `thym 0` or `thym 1` (section 4.9): a program written under a grammar version
must compile under every later conforming compiler, and compile the same way. The language grows by moves, which the
core's built-ins and the MiniCOSMs declare (section 17.6), and never by syntax within a grammar version. `thym 1` is the
next grammar version, and every `thym 0` program compiles under every later compiler exactly as it did.

---

## 2. The model on one page

<!-- atem: moves over typed values; a compiler plans; a runtime runs and traces -->

```text
   author's side                   the three densities                  interpreter's side
   context · graph · morph        fabula · short · atem                 context · graph · morph
        │                               ▲      │                              │
        └── derive ── entail ── atem ───┘      └── read ── expand ── cut ─────┘
                 (moves, each with a signature and a contract)

   a folder of code ── derive ──▶ fabula (a fabulac) ── entail ──▶ cshort (code, never run) · catem (what it does)
   a fabula ── question ──▶ open questions ⇢ a person answers ⇢ record · settle ──▶ the fabula, settled
                 (two runs with a person between them; no run waits)

   program.thym ──compile──▶ items (thym/1) + plan (R:plan) ──run──▶ outputs + trace (R:trace)
                              ▲ inspectable before anything runs      ▲ replayable from its records
                                     a model-backed step ──▶ coprocessor (behind the contract)
```

- A **value** is a document that knows its type and its provenance: which move made it, from what, in which run. A
  text's type is its density (section 5).
- A **move** is one named step. It has a signature (what it takes and gives), a flag saying whether it **asks** the
  model, and a **contract**: the named checks that must hold on its output. The manifests that own the standard moves
  declare them, the core's built-ins and the MiniCOSMs alike; a program may define its own moves, and its own checks.
- A **program** composes moves with bindings, choices and loops, and carries its reason in prose heads.
- The **compiler** parses, resolves, type-checks, contract-checks, estimates, enumerates the program into items, and
  plans it. It refuses whole: a program compiles entirely or not at all, and the refusal names the line.
- A **plan** is what a program will do, before it does it: a graph of nodes a person can read.
- The **runtime** checks the plan against the machine (a model present and large enough; agent-free or not; the inputs
  present), walks it in order, runs deterministic moves in code, and sends model-backed moves to the **coprocessor**:
  the model, behind the move's contract. The model is chosen for the run: a local one, or a cloud model through a
  broker (section 23). A run lands all of its outputs or none.
- A **trace** is what a run did, one record per node. With the answers it recorded, it replays.
- Six **laws** bind every implementation (section 7.2).

---

## 3. The design rules

<!-- atem: seven rules every choice in this document answers to -->

1. **It reads.** Every keyword and every standard move is a FEED headword, or an inflected form of one (`takes`,
   `gives`, `has`, `covers`, `keeps`, `lines`). A program can be read aloud to someone who
   has never seen one, and they follow it. People learn Thym for years the way they learn a craft: more moves, more
   morph scales, more contexts, never more syntax.
2. **Typed by density.** Every meaning value knows its density and its provenance. A move declares what it takes and
   gives, so an atem of a morph is a compile-time error.
3. **Moves are the primitives, and the built-ins and the MiniCOSMs declare them.** `thym/1` declares the language's own
   moves; the built-ins `fabula/1` and `doc/1` and the MiniCOSMs `comprise/1` and `ascribe/1` declare
   theirs (section 6.2). The language
   grows by moves, never by syntax within a grammar version.
4. **Transcode by default; transcognize when marked.** A move that transcodes is mechanical and deterministic. A move
   that transcognizes asks a mind to choose how to re-represent; it is marked `asks` in its declaration, carries a
   contract, and is the only place a run can vary. Everything a model produces is checked against the contract before
   it becomes a value.
5. **Programs are documents.** A program carries its ideal state (`why`), its constraints (`must`) and its dated
   decisions (`decided`). The `.thym` file is the source of truth; its items, plans and traces are derived from it
   (section 10).
6. **Nothing partial.** A program compiles whole or not at all. A run lands every output or none, and its trace says
   where it stopped and why.
7. **Portable by design.** The grammar, the types, the contracts and the conformance suite are language neutral:
   `.cosm` in, `.cosm` out. The Python reference implementation uses nothing a JavaScript runtime could not mirror (section 12.6).

---

## 4. Programs: the language

<!-- atem: the file, its blocks, heads and statements, and the grammar in full -->

### 4.1 The file

A program file has the extension `.thym`. It is UTF-8 (a byte-order mark is tolerated), with LF or CRLF newlines. Its
first line that is neither blank nor a comment is the **version line**, `thym 0` or `thym 1`. The compiler reads the
version line first and then reads the whole file by that version's grammar; nothing else in the file chooses the
version (section 4.9). After it come `use` lines and blocks, in any order. A comment runs from `--` to the end of the line. Blank lines are free. Indentation is free too: the
examples indent for the eye, and a compiler must read the same file with none.

A complete program, which packages a story with its fabula and its author's morph (section 15):

```thym
thym 0

program publish-story
  why: a story leaves the house with its fabula and its author's morph, so that others
       may read it their way and the author's way stays the author's.
  must: nothing in the package names the author.
  decided 2026-11-01: readings are local and labelled; the text is never replaced.

  takes story: text
  gives out: package

  let f = derive story                       -- text to fabula; asks the coprocessor under emf/1
  assert f covers story else "the fabula does not cover the text"
  let m = measure story against null of f    -- the holomorph: the departure from the null morph
  let c = context of story                   -- the surrounding volume's catalog, read-only
  let g = graph of story                     -- what the holograph released for this text, or nothing
  give package story, f, m, c, g
end
```

### 4.2 Blocks

A file holds four kinds of top-level block, each closed by `end`:

| block | opens with | holds |
|---|---|---|
| program | `program <name>` | heads, then statements: the unit a person runs |
| move | `move <name>(<params>): <type>` | heads, then statements: a named program with parameters, called like a move (section 8.3) |
| morph | `morph <name>` | heads, then one line per scale, `<scale> <1-5>`; the `formality` line also gives its direction (section 13.5) |
| context | `context <name>` | heads, then one line per field, `<field> <value>` (section 16.2) |
| contract | `contract <name>(<params>)` | `thym 1`: prose heads, then `let`, `assert` and `for each` lines: a check the program defines (section 7.5) |

A `move` block, and in `thym 1` a `contract` block, may also stand inside a `program` block, before the program's
statements; it is then local to that program. Names are lowercase, `[a-z][a-z0-9-]*`. A name is unique among the blocks of its file, and differs from every
keyword and every move the file can see.

### 4.3 Heads

A head is a line at the start of a block, before any statement. The prose heads carry the block's reason; the
signature heads carry its types.

| head | form | what it is |
|---|---|---|
| `why:` | `why: <prose>` | the ideal state the block serves; one per block; its first sentence is the block's atem |
| `must:` | `must: <prose>` | a constraint the program keeps; stated, not checked (a checked constraint is an `assert`) |
| `decided` | `decided <YYYY-MM-DD>: <prose>` | a decision and its date; any number, in date order |
| `takes` | `takes <name>: <type>, <name>: <type> …` | the inputs; one line, or none for a program that takes nothing |
| `gives` | `gives <name>: <type>` | the output's name and type; one line; every path must then reach a `give`. In `thym 1` a program may give several outputs, `gives code: folder, manual: short`, and every path gives each of them once, by name (section 8.2) |
| `keeps` | `keeps <name> [of <output>] [against <name>, …]` | `thym 1`: the block's output passes the contract block or named check `<name>`; `of` names the output in a program of several (section 7.5) |
| `depth:` | `depth: <1-64>` | `thym 1`: how deep a move that calls itself may go (section 8.3) |

**Prose.** A prose head begins after its colon and runs to the end of its paragraph. It continues on the following
lines until a blank line, a line whose first word is a head keyword (`why` `must` `decided` `takes` `gives`, and in
`thym 1` also `keeps` and `depth`), or `end`.
Inside the paragraph any word may begin a line. A blank line, or a `takes` or `gives` line, separates the last prose
head from the first statement. A compiler warns when a prose paragraph holds a line that begins with a statement
keyword, since the writer probably forgot the blank line.

### 4.4 Statements

| statement | form | meaning |
|---|---|---|
| `let` | `let <name> = <expr>` | binds a name once (section 5.4) |
| `assert` | `assert <cond> [else "<message>"]` | a check the program adds; false refuses the run with the message (section 7.4) |
| `if` | `if <cond> then <stmts> [else <stmts>] end` | a choice |
| `for each` | `for each <name> in <expr> [where <cond>] <stmts> end` | a loop (section 8.1) |
| `emit` | `emit [<slot>:] <expr>` | adds an item to the program's output volume, or, with a slot (`emit employees: …`), puts a value into that field of the projection; `project` consumes both (sections 8.2, 18) |
| `give` | `give <expr>` | gives the block's output, once on each path; a path ends when its last output is given, and nothing after that runs. In `thym 1`, `give <output>: <expr>` names which output it gives (section 8.2) |
| collecting `let` | `let <name> = for each <name> in <expr> [where <cond>] <stmts> end` | `thym 1`: a loop that collects; binds the list of what its `keep` lines kept (section 8.1) |
| `keep` | `keep <expr>` | `thym 1`: adds a value to the list the nearest enclosing loop that collects is making |
| `withhold` | `withhold <expr> [where <cond>]` | calls the move `withhold`: the items leave the output volume without a trace (section 18) |
| effect | `<expr>` | a move run for its effect (`lint v`, `trace`); its value is dropped |

### 4.5 Expressions and modifiers

An expression is a move call, a name, a literal, a field read, or an expression in parentheses. A **move call** is the
move's name, then its operands separated by commas, then its modifiers in the order its signature declares them:

```text
derive story
entail f as told
entail f by weight with rosa
expand (atem f) with f to 300 words
measure story against null of f
read f with mine in now
band (count staff) as [none, some] marked verified
project h as isotype
```

| modifier | after it | used by |
|---|---|---|
| `as` | a word or a list of words: an order (`told`, `weight`), a kind (`isotype`, `paratype`, `isograph`), a marking (`verified`, `stated`), the words of a band | `entail`, `project`, `mark`, `band` |
| `by` | an order | `entail` |
| `with` | a value: a morph, or a fabula | `entail`, `morph`, `read` (a morph); `expand` (a fabula) |
| `to` | a number and a unit: `300 words`, `12 sentences` | `cut` (words or sentences); `expand` (words) |
| `against` | a short: the null (`null of f`) | `measure` |
| `of` | a value | `null` and the accessors `fabula`, `context`, `graph`, `isomorph`, which take no operand: `of` is their argument |
| `in` | a context | `read` |
| `where` | a condition over items | `withhold`; and a filter on a volume or a list (`h where module is employees`) |
| `marked` | a marking: `verified`, `stated` | any expression that gives an item or a word; short for `mark … as …` |
| `before`, `after` | a line | `thym 1`: `insert` (exactly one of the two, section 21) |

In `thym 1`, `as` also takes a flavour's word: `derive t as prose`, `derive t as verse`, `derive t as code`; and `entail`
takes `as code` and the catem's depths `as line`, `as overview`, `as manual` (section 20). The flavour names themselves
are never keywords or moves.

A modifier's argument that begins with a move name is itself a call, and takes every modifier after it: `measure story
against null of f` is `measure(story, against: null(of: f))`. Parentheses group where the eye would otherwise misread.
A field is read with a dot: `now.medium`, `o.kind`.

**Conditions** join terms with `and`, `or` and `not`. A term compares two values with `is`, `is not`, `in` (membership
in a list), `<`, `>` or `=`; tests a field with `has` (the field is present); tests coverage with `covers` (section
7.3); or is a bare value of type `bool`. In `thym 0` a call inside a condition goes in parentheses:
`assert (words x) > 0`.

In `thym 1`, three things change in conditions and loops:

- **A call on either side of a comparison needs no parentheses**: `assert words new < words old`, `where count parts is
  0`. A call in a condition ends at `is`, `<`, `>`, `=`, `has`, `covers`, `and`, `or`, `then`, `else`, a closing
  parenthesis or the end of the line. `in` ends it too, unless the move declares an `in` modifier, in which case `in` is
  the modifier (`read f with m in now`); write membership in parentheses then: `(read f with m) in xs`. Parentheses
  still work everywhere. A move's name on a side begins a call only when an operand, or a modifier other than `in`,
  `where` or `marked`, follows it; otherwise it is a field or a word, so `where count is 3` reads the field `count`.
- **`in` with a text on its right**: `"TODO" in l` holds when the line, string, short or text on the right contains the
  characters on the left exactly. Membership in a list is unchanged.
- **A `where` after a call in a `for each` header belongs to the loop**, unless the move declares a `where` modifier:
  in `for each l in lines of s where words l > 30`, the `where` filters the lines.

**Bare words.** A bare word stands for itself, without quotes, wherever only a word can stand: inside a list literal,
after `as`, `by` and `marked`, and on the right of `is` and `is not`. In a `where` clause over items, a bare field name
is the current item's field: `h where visibility is internal`; `kind` and `module` there are the item's kind and
module letter, read from its id, never a field of that name (a Comprise aim has a `kind` field of its own). Where a
word may stand, a bound name of the same
spelling means its value, and the binding wins. Everywhere else a bare name must be bound. An unbound name is a
compile error, so a typo never becomes a word.

### 4.6 Literals

| literal | form | examples |
|---|---|---|
| number | an integer; the language has no floats (section 12.6) | `300`, `0` |
| string | double quotes; `\"` and `\\` are the only escapes | `"phone"` |
| date | `YYYY-MM-DD` | `2026-11-01` |
| word | a bare word where only a word can stand (section 4.5) | `told`, `verified`, `aim` |
| list | `[` values `]` | `[none, some]`, `[product, service, platform]` |
| density | `text` `fabula` `short` `atem` | |
| order | `told` `weight` | |
| marking | `verified` `stated` | |
| stance | `axiom` `observed` `deduced` `opinion` `assumed` `hearsay` | the fabula's closed list |
| bool, nothing | `true` `false` `nothing` | `nothing` is the absent value an accessor may give |
| URI | `oes:<format>/<database>[/<path>]`, as MacroCOSM OES writes it in its grammar of URIs (https://macro.cosmoes.org/), or a relative file path; `oes:emf/…`, the old spelling, names the same thing as `oes:fabula/…` | `oes:fabula/notes-md`, `oes:thym/house/M/morph/rosa`, `notes.md` |

### 4.7 Keywords

Every keyword is a FEED headword or a form of one (`takes`, `gives`, `has`, `covers` and `keeps` are forms of `take`,
`give`, `have`, `cover` and `keep`). The keywords of `thym 0` are:

```text
thym use program move morph context end
why must decided takes gives
let assert if then else for each in where emit give withhold
as by with to against of marked
is not and or has covers
true false nothing
```

`thym 1` keeps every one of them and adds six:

```text
keep keeps contract depth before after
```

`contract` opens a block, `keeps` and `depth` are heads, `keep` is a statement, and `before` and `after` are
modifiers. `depth` is the head only where a `:` follows it; anywhere else it is a value, the field of a folder's file
(section 20.1), so `repo where depth is 0` holds the files at the folder's top. The standard moves a program sees (section 6.3), the densities, the orders, the markings and the stances
are reserved too: no block, binding or user move may take one of these names. `entail` is a standard move from 0.7,
and so reserved: a program that used `entail` as a name before 0.7 must rename it. That is the only
incompatibility the move's new spelling brings, and none is known. `tell`, its earlier spelling (section 6.3), stays
reserved. A few words are both a keyword or a type and a move (`morph`,
`context`, `package`, `graph`, `fabula`, `trace`); where the word stands decides which it is.

### 4.8 The grammar in full

The grammar of `thym 0`:

```text
file      := blank* "thym" INT NEWLINE { use | block }
use       := "use" URI NEWLINE
block     := program | move | morph | context
program   := "program" NAME NEWLINE { head } { move } { stmt } "end"
move      := "move" NAME "(" [ param { "," param } ] ")" ":" type NEWLINE { head } { stmt } "end"
param     := NAME ":" type
morph     := "morph" NAME NEWLINE { head } { SCALE INT [ "toward" WORD ] NEWLINE } "end"
context   := "context" NAME NEWLINE { head } { FIELD value NEWLINE } "end"

head      := "why:" prose | "must:" prose | "decided" DATE ":" prose
           | "takes" param { "," param } NEWLINE | "gives" param NEWLINE
prose     := TEXT { NEWLINE TEXT }                  -- to a blank line, a head keyword or "end"

type      := "text" | "fabula" | "short" | "atem" | "item" | "volume" | "morph" | "context" | "graph"
           | "package" | "plan" | "trace" | "report"
           | "number" | "string" | "bool" | "date" | "word" | "list" "of" type

stmt      := "let" NAME "=" expr
           | "assert" cond [ "else" STRING ]
           | "if" cond "then" { stmt } [ "else" { stmt } ] "end"
           | "for" "each" NAME "in" expr [ "where" cond ] { stmt } "end"
           | "emit" [ FIELD ":" ] expr | "give" expr | "withhold" expr [ "where" cond ]
           | expr

expr      := call | filter | primary
filter    := primary "where" cond                  -- the items of a volume, or the members of a list, that satisfy cond
call      := MOVENAME [ operand { "," operand } ] { modifier }   -- no operand when the move takes none: fabula of p
operand   := primary
primary   := NAME | literal | URI | primary "." FIELD | "(" expr ")"
modifier  := "as" ( WORD | list ) | "by" WORD | "with" primary | "to" INT UNIT | "against" primary
           | "of" primary | "in" primary | "where" cond | "marked" WORD
             -- a primary after a modifier word that begins with a MOVENAME is a call, to the end of the line

cond      := term { ( "and" | "or" ) term }
term      := [ "not" ] ( primary cmp primary | primary "has" FIELD | primary "covers" primary | primary )
cmp       := "is" | "is" "not" | "in" | "<" | ">" | "="

literal   := INT | STRING | DATE | list | WORD | "true" | "false" | "nothing"
list      := "[" [ primary { "," primary } ] "]"
value     := literal | NAME

NAME      := [a-z][a-z0-9-]*          SCALE := one of the ten scale names (section 13.2)
FIELD     := [a-z][a-z0-9_-]*         UNIT  := "words" | "sentences"
INT       := [0-9]+                   DATE  := [0-9]{4}-[0-9]{2}-[0-9]{2}
STRING    := '"' ( [^"\\] | '\"' | '\\' )* '"'
URI       := "oes:" … | a relative path with no spaces
```

`MOVENAME` is a name that a manifest or a `move` block declares, `WORD` is a bare word (section 4.5), and `TEXT` is the
rest of a line. Comments count as blank. A statement ends at the end of its line: a line may not hold two statements,
and a statement may not span lines except inside parentheses or a list. There are no semicolons, no braces and no
indentation rules.

The grammar of `thym 1` is the grammar above with these productions added. `+=` adds alternatives to a rule, and `:=`
on a rule the grammar above already has replaces it, for `thym 1` only:

```text
block     += contract
program   := "program" NAME NEWLINE { head } { move | contract } { stmt } "end"
contract  := "contract" NAME "(" param { "," param } ")" NEWLINE { prosehead } { cstmt } "end"
cstmt     := "let" NAME "=" expr | "assert" cond [ "else" STRING ]
           | "for" "each" NAME "in" coll [ "where" cond ] NEWLINE { cstmt } "end"
head      += "keeps" NAME [ "of" NAME ] [ "against" NAME { "," NAME } ] NEWLINE   -- "of": which output
           | "depth:" INT NEWLINE
           | "gives" param { "," param } NEWLINE                 -- several outputs
prosehead := "why:" prose | "must:" prose | "decided" DATE ":" prose
type      += "folder" | "line" | "change"
stmt      += "let" NAME "=" "for" "each" NAME "in" coll [ "where" cond ] NEWLINE { stmt } "end"
           | "keep" expr
           | "give" NAME ":" expr                                -- a labelled give
           | "for" "each" NAME "in" coll [ "where" cond ] NEWLINE { stmt } "end"
coll      := expr                -- a "where" after a call belongs to the loop unless the move declares where
modifier  += "before" primary | "after" primary
term      := [ "not" ] ( side cmp side | side "has" FIELD | side "covers" side | side )
side      := call | primary      -- a call needs no parentheses here
```

### 4.9 Two grammars

A conforming compiler reads both versions. The version line switches the tables the whole file is read by:

| what the version line switches | `thym 0` | `thym 1` |
|---|---|---|
| keywords (section 4.7) | as `thym 0` lists them | adds `keep` `keeps` `contract` `depth` `before` `after` |
| head words, at which a prose head stops (section 4.3) | `why must decided takes gives` | adds `keeps` and `depth` |
| blocks (section 4.2) | `program move morph context` | adds `contract` |
| types (section 5.1) | as `thym 0` lists them | adds `folder`, `line`, `change` |
| modifiers (section 4.5) | `as by with to against of in where marked` | adds `before`, `after` |
| grammar | section 4.8, the first block | section 4.8, with the `thym 1` productions |
| the moves a program sees | each declaration's `thym 0` view | each declaration whole |
| how a `for each` over a collection known only at run time plans | one node per statement (section 11.1) | one node for the loop (section 11.1) |

A `thym 0` file is read by the `thym 0` tables exactly, so a `thym 0` paragraph whose second line begins with "keeps"
stays prose, and every `thym 0` program compiles to the same items and the same plan under every later compiler.

**This needs `thym 1`.** When a `thym 0` file is refused, the compiler compiles the same text again as `thym 1`. If
that second compile succeeds, the refusal becomes a `version` refusal at the first line of the file that holds a
`thym 1` feature: "this needs `thym 1`: a loop that collects (let readings = for each …) at line 14; the first line
says thym 0". Otherwise the `thym 0` refusal stands unchanged. The second compile never changes what a `thym 0` program
means: it runs only on a file the first refused, and it only chooses the message.

**What a `thym 0` program sees.** A move declaration may say `since: 1`, and then only `thym 1` programs see the move;
and it may carry a `thym-1:` mapping of what a `thym 1` program sees in addition to, or in place of, its own keys
(section 17.6). A `thym 0` program sees each declaration without its `thym-1:` mapping and no declaration that says
`since: 1`: its view is frozen. So a `thym 0` program that binds a name such as `record` or `lines` still compiles,
and a `thym 0` program that calls a move only `thym 1` sees is told it needs `thym 1`. The language still grows by
moves: a later edition or a manifest may add a move to `thym 0` by declaring it without `since`.

**`use` across versions.** A used file is read by its own version line, and its blocks mean what they meant there. A
`thym 1` program may `use` a `thym 0` file, a `thym 1` file, a program volume of either version, and any morph or
context volume. A `thym 0` program may `use` a `thym 0` file and any morph or context volume; a used `.thym` file or
program volume whose version line (in a volume, the first line of its `front` that is neither blank nor a
comment) says `thym 1` is refused at the `use` line, check `version`.

**Enumeration and round trip** hold in both versions: `compile` on a program volume gives the `.thym` file back byte
for byte (section 10). A `thym 0` file enumerates to exactly the items edition 0.5.4 gave it; new fields appear only on
the new constructs of `thym 1`.

**Relabelling has one cost.** Changing a `thym 0` program's version line to `thym 1` can change the order of the items
that a loop of several statements emits when it goes over a collection known only at run time. Under `thym 0` each
statement of such a loop is a node of its own and runs over every member before the next statement starts, so the
items come in statement order. Under `thym 1` the loop is one node whose body runs member by member, so they come in
pass order. The items are the same; their order in the output volume may differ.

---

## 5. Values and types

<!-- atem: documents typed by density, each carrying what it was made from -->

### 5.1 The types

| type | what it is | carries |
|---|---|---|
| `text` | a markdown text | path or bytes, sha256 |
| `fabula` | a `fabula/1` volume of one flavour; an `emf/1` volume, the old spelling, is read as a fabulan | its source's sha256 (spans resolve against it); for a fabulac, the folder's tree digest |
| `short` | an entailment of a fabula | its fabula's sha256, its order, its morph (the null's when none was given) |
| `atem` | line + focus + push + pull | its source's sha256 and span |
| `item`, `volume` | any OES item or volume | URI, format, kind |
| `morph` | a `thym/1` morph: the ten scales | derived-from (text digests) or declared (a `morph` block) |
| `context` | surrounding (a catalog excerpt) or occasional (a `thym/1` context item) | |
| `graph` | an isograph made for one text (Ascribe, https://ascribe.cosmoes.org/, its section 14.1) | the release it came from |
| `package` | section 15 | contents and digests |
| `plan`, `trace`, `report` | sections 11 and 12; a `lint` report | |
| `number`, `string`, `bool`, `date`, `word`, `list of T` | plain values | |
| `folder` | `thym 1`: a directory tree read under one fixed rule (section 20.1) | its path and its tree digest; each file walked from it carries `source: {folder, path}` |
| `line` | `thym 1`: one line of a text or a short, with its place (section 21.1) | its number, and the sha256 of its source and of itself |
| `change` | `thym 1`: one edit to a line (section 21.1) | the line's number and digest, and its source's digest |

The nine **meaning types** are `text fabula short atem item volume morph graph package`; a `context` is a meaning value
too when it is an occasional context item. Every meaning value carries **provenance** (section 5.3). The plain types
carry none. A `folder` is not a density: it is an input a move reads, and its provenance is its tree digest. A `line`
fits wherever a `string` is taken: it is a string with a place.

**Flavour is a property, not a type.** A fabula's flavour (`fabulan`, `fabulap` or `fabulac`) is a property of the
value, read as `f.flavour`. The compiler carries it as a note on the `fabula` type where it knows it: a fabula from
`derive … as verse` is a fabulap, one from `derive <folder>` or `survey` a fabulac, and a `fabula` input's flavour is
unknown until run time. It refuses at compile time what it can prove wrong ("f is a fabulan, the fabula of a text; only
a fabulac entails code"), and the runtime refuses the rest with the check `flavour`.

### 5.2 Densities and what fits where

The four densities, `text`, `fabula`, `short` and `atem`, are types, and each move's signature says which it takes
(section 6.3). A value of one density is never silently read as another: `entail story`, where `story` is a `text`, is a
type error, and the message gives the fix ("derive it first").

### 5.3 Provenance

Every meaning value a move makes carries the move, its inputs' digests, the run (its trace's id), the step and the
node. Written
into a `.cosm`, this becomes the item's envelope provenance plus one field, `made`, which `thym/1` lists in its envelope
and every other format keeps as an unknown field:

```yaml
provenance: {mode: derived, sources: ["notes.md#sha256:54055e8…", "oes:thym/2026-11-01-1042-7f3a/R/record/3"], confidence: 0.9}
made: {move: entail, run: 2026-11-01-1042-7f3a, step: 3, node: R:node/4, engine: "model:g40-04", route: local}
```

`engine` is `model:<id>` for a model-backed value, where the id is the model's own: the name a local model is known by,
or the provider's resolved id for a cloud model. A model-backed value also says its `route`, `local` or `cloud`, and a
cloud one its `provider` (section 23). A value made before this edition has neither key, and a replay of it writes
none.

`made` is the law of provenance (section 7.2) in one field: the home file system (Canon) never holds an entailment that
does not say what it is an entailment of. A value a person wrote by hand has `made: {move: none}`, and a value read from disk without `made` is
treated as hand-made.

### 5.4 Bindings

`let` binds a name once, in the block where it appears. An inner block (the body of an `if` or a `for each`) sees the
names bound before it and may not rebind them. A loop variable is bound for the loop's body. A program's `takes` names
are bound for the whole program. A move's parameters are bound for its body, and a move sees no binding of the program
that calls it: it is called with values, never with the caller's scope.

---

## 6. Moves

<!-- atem: the primitives: a signature, an asks flag, a contract, and an owner -->

### 6.1 What a move is

A move is one step, a transcoding or a transcognition, with four parts: a **signature** (its operands and modifiers with their types, and the
type it gives); an **asks** flag (true when the move needs the model); a **contract** (the named checks that must hold
on its output, section 7); and an **owner**, the built-in or the MiniCOSM whose manifest declares it (section 17.6). A move
transcodes unless its declaration says `asks: true`, in which case it transcognizes. A model-backed move may have a **scaffold**: a deterministic
stand-in with a weaker output, which a run with `--rules` uses instead (section 19).

### 6.2 Who declares what

| owner | what it is | moves |
|---|---|---|
| `thym/1` | a built-in of the core | `cut`, `count`, `words`, `digest`, `null`, `measure`, `morph`, `read`, `package`, `unpack`, `lint`, `trace`, and the accessors `fabula`, `context`, `graph`, `isomorph`; for `thym 1`, the dialectic's `question`, `record` and `settle`, the editing moves `lines`, `replace`, `drop`, `insert`, `edit`, `reword`, and `gather`, `join`, `say`, `folders` |
| `fabula/1` | a built-in of the core | `derive`, `entail`, `atem`, `expand`; for `thym 1`, `survey` and `history` |
| `doc/1` | a built-in of the core | `enumerate`, `compile` |
| `comprise/1` | a MiniCOSM | `project`, `band`, `mark`, `withhold`, in a sidecar (section 17.6), since `comprise/1`'s manifest belongs to Comprise OES |
| `ascribe/1` | a MiniCOSM | for `thym 1`, `propose`, and the kinds `isograph` and `allograph` of `project`, by an entry that `extends` it, in its own manifest (Ascribe, https://ascribe.cosmoes.org/) |

`fabula/1`'s manifest declares the four moves that `emf/1`'s declared under the old name, unchanged in their `thym 0`
view; the one that `emf/1` named `tell` is spelled `entail` (section 6.3). The dialectic's moves sit with `thym/1`'s because any volume may carry the dialectic's questions, so no single
format owns them. Section 17.6 gives the `moves:` block that declares them all.
`project` takes as its kind what each MiniCOSM declares that it projects: `isotype` and `paratype` are Comprise OES's,
and `isograph` and `allograph` are Ascribe's (section 18).

### 6.3 The standard moves

Each contract below is the `contract:` list of the move's declaration; section 7.3 says what each check holds. The
first table is every program's: it is what a `thym 0` program sees, and a `thym 1` program sees it too, with the
additions of the second table.

| move | signature | asks | contract |
|---|---|---|---|
| `derive` | text → fabula | yes | `span-resolves` `stance-closed` `terms-grounded` `coverage` `fabula-checks` `provenance` (in the `thym 0` view the fifth check keeps its old name, `emf-checks`; it is the same check) |
| `entail` | fabula \| item \| volume → short; `as` order or `by` order; `with` morph | yes | `coverage` `no-invention` `stance-kept` `scales-met` (with a morph) `footer` `provenance` |
| `atem` | text \| fabula \| short \| item → atem | yes | `atem-shape` `span-resolves` `provenance` |
| `expand` | atem → short; `with` fabula; `to` N words | yes | `coverage` `no-invention` `stance-kept` `length` `span-inside` `provenance` |
| `cut` | short → short; `to` N words or N sentences | no | `whole-sentences` `weight-order` `coverage` `provenance` |
| `null` | → short; `of` fabula | yes | `coverage` `no-invention` `stance-kept` `null-pinned` `provenance` |
| `measure` | text → morph; `against` short (the null) | yes | `scale-range` `scale-evidence` `provenance` |
| `morph` | short → short; `with` morph | yes | `coverage` `no-invention` `stance-kept` `scales-met` `provenance` |
| `read` | fabula → short; `with` morph; `in` context | yes | `coverage` `no-invention` `stance-kept` `scales-met` `labelled` `never-source` `provenance` |
| `project` | volume → volume; `as` kind (`isotype` or `paratype`, Comprise OES's; `isograph` or `allograph`, Ascribe's) | no | the target schema's rules: for `isotype` and `paratype`, `default-deny` `no-counts` `banded` `no-mark` `verified-derived` `standing-gate` `epoch` `provenance`; for `isograph` and `allograph`, `default-deny` `no-counts` `no-mark` `epoch` `provenance`. A check holds by the rules of the kind the call names: for an isograph, those of `ascribe-isograph/0`; for an allograph, those of `ascribe-allograph/0`. For an isograph or an allograph, the ids of the items that leave are handed to the host with the value, as the release's `items` (Ascribe, its sections 14.1 and 14.6) |
| `band` | number → word; `as` a list of words (`[none, some]`: 0 is `none`; any other list: equal steps of ten) | no | `banded` |
| `mark` | item \| word → the same; `as` marking | no | `verified-only-where-derived` |
| `withhold` | item \| volume → nothing; `where` condition | no | `no-mark` |
| `enumerate` | text → volume (`doc/1`) | no | `byte-exact` `provenance` |
| `compile` | volume → text | no | `byte-exact` |
| `package` | text, fabula, morph, context, graph → package; the last three may be `nothing` | no | `digests` `released` `provenance` |
| `unpack` | package → text (the rest by accessor) | no | `digests` |
| `lint` | volume → report | no | none; the report holds the checks of the volume's format |
| `trace` | → trace | no | none; it gives the current run's trace so far |
| `fabula` | → fabula; `of` package | no | none |
| `context` | → context; `of` text \| package | no | none |
| `graph` | → graph; `of` text \| package | no | `released` |
| `isomorph` | → morph; `of` package | no | none |
| `count` | volume \| fabula \| short \| list → number | no | none |
| `words` | text \| short \| atem → number | no | none |
| `digest` | any meaning value → string | no | none |

The accessors are read-only and may give `nothing`. `context of` a text gives the surrounding volume's catalog around it
(section 16.1), and of a package the context the package carries; `isomorph of` a package gives the author's shared
morph. `measure` asks the model only for its three judgement scales; the other seven are statistics, computed in code
(section 13.2), and its scaffold gives those seven with the three pending. `compile` given a fabula is refused with the
fix: "to compile a fabula into a short, use entail". `tell` is `entail`'s earlier spelling: the compiler reads it as
`entail` and never writes it.

**`entail`, once `tell`.** The move that makes a short of a fabula was first spelled `tell`. `tell`, the earlier
spelling, names the same move as `entail`, under `thym 0` and `thym 1` alike and for good: `tell f as told` compiles to
the same items, the same plan and the same contract as `entail f as told`. The compiler reads `tell` and never writes
it. A step's `move` and `calls`, a plan's nodes, a record and a value's `made` say `entail`, and a trace or a value
recorded with `move: tell` reads as `entail`. A program's own text keeps its words, so `compile` still gives its file
back byte for byte (section 10). No version line marks the change, since moves are declarations and not syntax
(section 4.9). What `entail` makes is an entailment made by a model under contract, and it holds only because its
checks hold it; what `project` makes is an entailment made by rule, and it holds by construction (section 18).

The moves `thym 1` adds or extends. Every move in this table carries `since: 1` except `derive`, `entail`, `count` and
`words`, which carry their additions under `thym-1:` (section 17.6):

| move | signature | asks | contract | scaffold |
|---|---|---|---|---|
| `derive` | text \| folder → fabula; `as` prose \| verse \| code; `with` fabula | yes | a text as prose or verse: as above, with `fabula-checks` · a text as code: `code-span` `outline-cited` `coverage` `terms-grounded` `stance-closed` `fabula-checks` `provenance` · a folder: `fold-grounded` `atem-shape` `licence-recorded` `fabula-checks` `provenance` | a text: the rules twin · as code: `file-outline` · a folder: none |
| `entail` | fabula \| item \| volume → short; `as` an order, `code`, `line`, `overview` or `manual`; `by` order; `with` morph; `as code` gives a folder | yes | as an order: as above · as code: `parses` `interfaces-present` `files-present` `footer` `provenance` · as line, overview or manual: `coverage` `no-invention` `uses-told` `footer` `provenance` | an order: the outline · code: none · a catem: `uses-outline` |
| `survey` | folder → fabula (a fabulac outline) | no | `files-found` `code-span` `licence-recorded` `fabula-checks` `provenance` | — |
| `history` | folder → fabula; `with` fabula | no | `history-grounded` `fabula-checks` `provenance` | — |
| `gather` | list of fabula \| list of item → the type of `with`; `with` fabula \| volume | no | `nothing-lost` `ids-unique` `fabula-checks` `provenance` | — |
| `question` | fabula \| volume → list of item (questions) | yes | `addressed` `no-duplicate` `provenance` | `bank` |
| `record` | volume → the type of `in`; `in` fabula \| volume | no | `addressed` `only-the-asked` `provenance` | — |
| `settle` | fabula \| volume → the same | yes, only where an item must be read again | `addressed` `only-the-asked` `fabula-checks` `provenance` | `direct` |
| `lines` | → list of line; `of` text \| short | no | none | — |
| `replace` | line → change; `with` string \| line \| short | no | none | — |
| `drop` | line → change | no | none | — |
| `insert` | string \| line \| short → change; `before` line or `after` line, exactly one | no | none | — |
| `edit` | text \| short → the same; `with` list of change | no | `only-the-changed` `never-source` `provenance` | — |
| `reword` | line \| string \| short → the same; `to` N words; `with` morph | yes | `length` `one-line` `nothing-added` `provenance` | — |
| `join` | list of string \| list of line \| list of short → short; `with` string | no | `provenance` | — |
| `say` | number \| date \| word \| bool \| string → string | no | none | — |
| `propose` | fabula → list of item (candidate nodes and their questions); `with` volume (the holograph) | yes | `no-invention` `provenance`; the move itself holds every candidate to Ascribe's own checks (Ascribe, its section 10) | — |
| `folders` | → list of folder; `of` folder | no | none | — |
| `count` | adds folder (its text files) | no | none | — |
| `words` | adds line \| string | no | none | — |

`propose` is Ascribe's: it reads the holder's own text, decompiled to a fabulan, and gives candidate nodes of the
holograph, each with the question that asks the holder whether it is so; a program lands them with `gather`. `atem`,
`expand`, `null`, `measure`, `morph`, `read`, `cut`, `package` and the rest are the same in both versions. `atem f` of a
fabulac is the catem at depth `line`, under the same contract. The compiler picks the `gives`, the contract and the
scaffold of a call from the call as written (its `as` word, or its first operand's type), and the plan's `P:contract`
item lists the chosen contract, so a plan says exactly which checks a node keeps. A call whose scaffold is `none` has no
scaffold, and `--rules` refuses it at plan time (section 19). Sections 20, 21 and 22 say what these moves do.

### 6.4 Signatures in the manifest

A move's declaration is one mapping in a `moves:` list (section 17.6). `entail`'s `thym 0` view, from `fabula/1`'s
manifest:

```yaml
moves:
  - name: entail
    takes: ['fabula | item | volume']
    gives: short
    modifiers: {as: order, by: order, with: morph}
    asks: true
    contract: [coverage, no-invention, stance-kept, footer, provenance]
    scaffold: outline                      # the rules-mode stand-in, or absent
    code: enough.thym.moves.emf:entail
    says: an entailment of the fabula, in an order, in a morph
```

The compiler reads every manifest's moves when it resolves names. A program that names a move no manifest declares is
refused with the nearest name: "unknown move `summarise`; did you mean `entail`?" (check `unknown-move`).

A declaration may also say `since: 1` (only `thym 1` programs see the move) and carry a `thym-1:` mapping of the keys a
`thym 1` program sees in addition to its own; inside it, `gives-when`, `contract-when` and `scaffold-when` choose a
call's type, contract and scaffold by its `as` word or its first operand's type. Section 17.6 lists the keys, and
section 4.9 says what each version sees. A word a declaration lists among a modifier's words is that word even when it
is also a type's name: `entail f as line` names the catem's depth, since `entail`'s `as` lists `line` among its words.

---

## 7. Contracts and the six laws

<!-- atem: named checks on a move's output, six of which every implementation keeps -->

### 7.1 What a contract is

A contract is a list of named checks that must hold on a move's output before the output becomes a value. The
compiler checks the **static** part: it refuses a composition that cannot satisfy a contract, such as an `entail` whose
input is a `text`, or a `project … as isotype` that emits a bare count. The runtime checks the **dynamic** part on every
output. A model-backed output that fails is repaired narrowly, retried within its budget, and then refuses the run
(section 9). Most checks exist as code in enough and Comprise; Thym names them and attaches them to moves. In `thym 1`
a program may also define a check of its own, as a contract block, and promise that a move's output keeps it (section
7.5).

### 7.2 The six laws

1. **Coverage.** An entailment says nothing its fabula does not hold.
2. **Grounding.** Every span exists in its text; every term is in FEED or is a named entity.
3. **Monotone stance.** No move strengthens a claim's stance. The ladder, weakest first, is `hearsay` `assumed`
   `opinion` `deduced` `observed` `axiom`. An entailment may say a claim more weakly than its fabula does, never more
   strongly.
4. **Round trip.** A package gives back its text (section 15.4), `compile` gives back a doc volume's markdown, and
   `compile` on a program's items gives back the `.thym` file: each byte for byte.
5. **Withhold, never falsify.** A projection leaves what it hides without a trace: no placeholder, no count of withheld
   things, no gap in an order that reveals them.
6. **Provenance.** Every meaning value says what it came from and which run made it (section 5.3).

### 7.3 The named checks

| check | holds when | where it comes from |
|---|---|---|
| `span-resolves` | every `span` names lines or quotes that exist in the source text | enough (Canon's derivation) |
| `stance-closed` | every claim's stance is in the fabula's closed list | MacroCOSM's generic `closed-list` check |
| `terms-grounded` | every `L:term` is in FEED, or carries `{pending: "not in FEED"}`, or is a named entity | enough (the lexicon floor) |
| `coverage` | every sentence of an entailment traces to one or more items of its fabula. As a condition it is written `f covers t`, for a fabula `f` and a text or short `t`: the fabula's items cover every claim-bearing sentence of `t` (prose or a list item of three or more words that does not end in a question mark; headings never count); the map `[{sentence, lines, items}]` lives in a derived fabula's `derived.covers` and in the check's verdict | Thym's own; the trace records the sentence → item map |
| `no-invention` | the entailment names no entity, claim or event the fabula lacks; for `propose`, no candidate or question says what its fabula lacks | Thym's own |
| `stance-kept` | each claim's stance in the entailment is at or below its fabula stance on the ladder; a sentence counts at the weakest stance its wording marks (a hedge reads as `hearsay`, a plain sentence as `observed`), and a claim said over several sentences is said at the weakest any of them marks | Thym's own |
| `footer` | a short ends with the footer line of MacroCOSM OES, its section 18.4.4 | enough (the short footer) |
| `byte-exact` | the compiled bytes equal the source bytes | DocOES (MacroCOSM OES, its section 18.5) |
| `atem-shape` | the line is 15 to 25 words; focus is at most two sentences; push is one; pull is one | the rule of MacroCOSM OES, its section 18.3.5 |
| `length` | `to N words`: at most N words and at least 80 per hundred of N; `to N sentences`: N sentences or fewer | Thym's own |
| `span-inside` | the expanded short contains the claims of the atem's span | Thym's own |
| `whole-sentences` | `cut` removed whole sentences only | Thym's own |
| `weight-order` | `cut` removed the lowest-salience sentences first (by their items' salience) | Thym's own |
| `scale-range` | every scale is an integer from 1 to 5 | Thym's own |
| `scale-evidence` | every scale cites one to three sentences of the measured text, and gives its basis and confidence | Thym's own |
| `null-pinned` | every scale of the null short is 1 (section 13.4 says why `analytical-depth` is) | Thym's own; the null morph's contract |
| `scales-met` | each scale of the output, measured, is within one step of the morph asked for; `analytical-depth` excepted, since the fabula sets it (section 13.4) | Thym's own |
| `labelled` | a reading carries `read_through: <morph name>` and the reading footer (section 14) | Thym's own |
| `never-source` | a reading's output path is not the path of any input, and no input file changed | Thym's own |
| `default-deny` | the projected volume holds only the fields its target schema names | Comprise (the isotype) |
| `no-counts` | no number of anything internal reaches the projection; the only number allowed is one the schema names (a founded year) | Comprise |
| `banded` | a number leaves only as a word from the declared list, and a band changes only after the value has stayed past the boundary for 90 days | Comprise (bands) |
| `no-mark` | a withheld item leaves no placeholder, count or gap | Comprise |
| `verified-derived` | `verified` only on fields the target schema derives (identity, shape, offers); `stated` on the subject's own words (aims) | Comprise |
| `verified-only-where-derived` | `mark … as verified` only on an item whose format lists it as derivable | Thym's own |
| `standing-gate` | a release as the subject needs first-party standing, or `sample: true` | Comprise (the standing gate) |
| `epoch` | the date shown is the epoch, never the edit day; lists keep a fixed order that file order cannot change | Comprise |
| `digests` | every file in a package's catalog has the sha256 the catalog says | Thym's own |
| `released` | nothing is in `graph.cosm` without a release recorded in the holograph | Thym's own; the release is Ascribe's (https://ascribe.cosmoes.org/) |
| `provenance` | every output carries `made` | Thym's own |
| `fabula-checks` | the volume passes its own manifest's checks: for a fabula, the generic ones and `fabula/1`'s own (`flavour`, `flavour-kind`, `code-span`, `licence-recorded`; MacroCOSM OES, its section 18.4.8). A file's reading (section 20.6) passes them together with the fabula it was read with. `emf-checks` is its old name: it is read wherever a manifest, a program or a trace writes it, a `thym 0` program's enumeration keeps it, and a verdict keeps the name it was asked by | the MacroCOSM reader's lint |

The checks the moves of `thym 1` add:

| check | holds when | where it comes from |
|---|---|---|
| `flavour` | the fabula's flavour is one the move takes: only a fabulac takes `entail … as code` or a catem's depth | MacroCOSM OES, its section 18.4.8 |
| `files-found` | every file the folder rule keeps (section 20.1) has a `C:file` item whose sha256 is the file's, and no `C:file` names a file the tree lacks | Thym's own |
| `code-span` | every code span `{file, lines}` names a file of the tree and lines inside it | MacroCOSM OES, its section 18.4.8 |
| `licence-recorded` | the fabulac's `source.licence` is the licence's standard short identifier, the licence file's first line, or `{pending: …}`, and never absent | MacroCOSM OES, its section 18.4.8 |
| `outline-cited` | every behaviour, structure and case a file's reading gives names the interfaces or components of the outline it is about, and they belong to that file, or, for a test file, to the files it tests | Thym's own |
| `fold-grounded` | every intent and inspiration item the fold gives (aim, audience, use, requirement, decision, exclusion; influence, allusion, occasion) cites at least one item of the fabula so far, and the atem's line cites at least one use | Thym's own |
| `history-grounded` | every change cites commits the clone's log answered, every release a tag it answered, and every maker rests on commits it answered and carries no address | Thym's own |
| `parses` | every file of a cshort in a language the fabulac names is read by that language's parser without a syntax error; parsing is not running, and nothing is imported or executed | Thym's own; the host's syntax engine |
| `interfaces-present` | every interface of the fabulac is defined in the cshort's file it is `defined-in`, with the same name, kind and parameter names in the same order | Thym's own; the host's syntax engine |
| `files-present` | the cshort holds every file it is required to rebuild, at its path (every `C:file` in a programming language that is not a test, a type stub or the repository's own tooling, and the README; MacroCOSM OES, its section 18.4.7), and the packaging file rules write whenever the fabulac records enough for one, exactly as they write it, with `CSHORT.md`, and the digests `CSHORT.md` lists are the files' | Thym's own |
| `uses-told` | a catem says everything its depth asks for: at `overview` every use, at `manual` every use and every interface a person reaches | Thym's own |
| `nothing-lost` | every item of every part gathered, and of the `with` volume, is in the output with every field it carries, as it carries it (`made` aside); the output's item may say more | Thym's own |
| `ids-unique` | no two different items of the output share an id (two byte-equal ones, `made` aside, are one; `gather` merges two that say the same item before they land, section 20.6) | Thym's own |
| `addressed` | every question's `about` resolves (an item, an `<item>#<field>`, a span of the source, or a module or kind the format declares), and every answer names a question that is `open` and fits the question's `kind` | Thym's own; the dialectic is MacroCOSM OES's, its section 18.6 |
| `no-duplicate` | no two open questions about the same address ask the same thing, nor does a new one repeat a question already in the volume | Thym's own |
| `only-the-asked` | only the questions' answers, states and `settled` fields, the new session, and the fields that answered questions are about (with their provenance) differ from the input | Thym's own |
| `only-the-changed` | every change names the value being edited and a line it holds with that digest; no line is replaced or dropped twice; and the output is the input with exactly those changes (section 21.3) | Thym's own |
| `one-line` | a reworded `line` is one line; an answer of several lines is repaired by joining them with a space, then checked again | Thym's own |
| `nothing-added` | every name, number and word outside FEED in the output is in the input | Thym's own |

### 7.4 `assert`

An `assert` line adds a check of the program's own. Its condition is evaluated at run time with the values at hand, and
false refuses the run with the message. `assert f covers story` is the usual one; its step's contract names the check
the condition uses (`covers` is `coverage`). A user move's `assert` lines become contracts of the move (section 8.3).
An `assert` refuses at once: use it where asking again cannot help, as with an input outside the band a program
reads or a coverage law. Where a model's answer can be better on the next try, use `keeps` (section 7.5).

### 7.5 Contract blocks and `keeps`

In `thym 1` a program may define a check of its own. A **contract block** is a named, reusable set of conditions over
a value: `contract <name>(<value>: T, <other>: U, …)`, its prose heads, then `let`, `assert` and `for each` lines,
then `end`. It stands at the top level, or inside a program before the program's statements, as a move does. In the
terms of section 7.1, it defines one named check.

```text
contract shorter(new: line, old: line)
  why: a reworded line says less in fewer words, never more.

  assert words new < words old else "the reworded line is not shorter than the line it replaces"
end
```

The head **`keeps <name> [of <output>] [against <name>, …]`** stands in a `move` or a `program` that gives, and promises that the
block's output passes the check. The kept value is the block's output and fills the contract's first parameter; the
names after `against` are the block's own parameters (in a move) or its `takes` names (in a program), and they fill
the second and later parameters, in order. `<name>` is a contract block the file can see (its own, a program's local
one, or one a `use`d file declares) or a named check of section 7.3; for a named check, the `against` names are its
inputs. A program of several outputs says which one it keeps: `keeps tidy of manual`.

**The static rules.**

- A contract's body asks no model, directly or through a move it calls: a contract checks, and never asks.
- Its body holds `let`, `assert` and `for each` lines only.
- Its name is unique among the file's blocks, and differs from every keyword, every move the file sees and every
  check of section 7.3.
- `keeps` names a contract or a check that exists; otherwise check `unknown-check`, with the nearest name.
- The kept value's type fits the contract's first parameter, and each `against` name the next one, in count and in
  type.
- `keeps` stands only in a block that gives.

**How it is checked.** When a user move's body gives its value, each contract it keeps runs: its parameters are bound,
its lines run in order, and the first false `assert` gives the verdict `{name, ok: false, why: <the assert's
message>}`. If the move asks (section 8.3: a move asks when any move it calls asks), a failed kept contract runs the
move's body again, within the node's attempts (3, counting the first). On every re-run, each model request the body
makes carries the failed contract's verdicts among its repairs, so the model is told which checks its last answer
failed and why; nothing else reaches the model. After the attempts, the run is refused with the contract's name as its
check. A move that does not ask is refused at once, since running a deterministic body again gives the same answer. A
program that keeps a contract has its output checked before anything lands, and a failure refuses the run, without a
re-ask: a program is not one node.

A manifest's `contract:` list names checks the registry implements, and a contract block is a check a program
implements. Both kinds of name stand in the same places: a plan node's contract item, a record's `checks`, a refusal's
`check`. A manifest cannot name a contract block, because a manifest's checks are code.

```thym
thym 1

contract plain-enough(s: short)
  why: a help page stays short and never shouts.

  assert words s < 301 else "over three hundred words"
  for each l in lines of s
    assert not "!" in l else "an exclamation mark"
  end
end

program help-page
  why: a guide said plainly for the help pages, asked again until it is plain enough.

  takes guide: text
  gives page: short

  move told-plainly(f: fabula): short
    keeps plain-enough
    keeps no-invention against f
    give entail f as told
  end

  give told-plainly (derive guide)
end
```

---

## 8. Control flow, bindings, user moves, `use`

<!-- atem: one choice, one loop, one output; moves calling moves; files lending moves -->

Bindings are section 5.4.

### 8.1 Choice and loop

`if … then … else … end` chooses. `for each … in … where … end` goes through the items of a volume or a fabula (in
`told` order: by span, then by id), the lines of a short, or the members of a list. `where` filters before the body
runs. The loop variable is bound for the body. The body may `emit`, `assert`, `let` new names and run moves for their
effect. It may not `give`: a program gives once, after its loops (refused as `type`, section 9). In `thym 1` a loop
also goes through the text files of a folder, in path order (section 20.2), and `lines of s` gives the lines of a text
or a short as `line` values (section 21).

**How a loop runs.** A loop over a list written in the program runs its statements once per member, as written. Over a
collection known only at run time, `thym 0` runs each statement of the body over every member before the next statement
starts, and `thym 1` runs the body member by member, as a unit, as a user move's body runs: a name the body binds, an
`if` inside it and a nested call all take this pass's values (section 11.1 says how each plans). In `thym 0`, three
such loops are refused at run with the fix, write `thym 1`, where a loop's body runs member by member: one holding an
`if` whose condition reads the loop's variable or a name the body binds (the condition is read once, before the loop,
and the refusal keeps the check that failed); one holding a `let` read later in the same loop (check `loop`); and one
holding a `for each` nested inside it (check `loop`).

**A loop that collects** (`thym 1`) is a `for each` that is the value of a `let`:

```text
let readings = for each t in repo where suffix is py
  keep read-file t, f
end
```

It reads aloud: let readings be, for each Python file of the repository, its reading kept. `keep <expr>` belongs to
the nearest enclosing loop that collects. It may stand inside an `if` or a plain `for each` within that loop's body (an
inner loop then keeps several per pass), and never in a user move's body unless that body holds the loop. Every `keep`
of one loop keeps one type T, and the loop binds `list of T`; a loop that collects has at least one `keep`. The body may
`let`, `assert`, `emit`, `withhold`, run moves for effect, and nest `if` and `for each`, and it may not `give`. The
names the body binds are bound for one pass, and the loop's own name is bound after its `end`, never inside it. The
list is bound when the last pass ends, and a refusal in any pass refuses the run.

```thym
thym 1

program aims-in-brief
  why: every aim of a house, told in one line, in the order the holotype keeps them.

  takes h: volume
  gives brief: short

  let lines-of-aims = for each a in h where kind is aim
    let s = atem a
    keep s.line
  end
  give join lines-of-aims
end
```

### 8.2 Three ways out

`give` gives the block's value, and every path of a block that `gives` must reach one. `emit` adds an item to the
program's output volume, or, with a slot (`emit employees: band …`), sets a field the target schema names; only
`project` consumes them, so a program that emits and never projects is refused, because the emitted items go nowhere. `withhold` marks items of a volume as withheld, and `project` leaves them out without a
mark.

**Several outputs** (`thym 1`). A program may give several outputs, `gives code: folder, manual: short`, and gives each
with a labelled `give`, shaped like the labelled `emit`: `give code: entail f as code`. Every path gives each output
exactly once, by name; a path that misses one is refused (`no-give`), and a second `give` of the same output on one
path, or a `give` naming no output of the program, is refused (`type`). A block with one output may label its `give` or not. A user move gives one value, since its signature
says one type. All of a program's outputs land at once, or none do.

### 8.3 User moves

A `move` block is a named program with parameters. It is called like a standard move, with its operands in parameter
order. It has a declared signature and inherits the contracts of the moves it uses, and its `assert` lines become
contracts of its own. A move may call other moves. A move sees only its parameters.

**Recursion.** In `thym 0`, a move that calls itself, directly or through another, is refused (`recursion`, section 9).
In `thym 1` a move may call itself when it says how deep it may go: the head `depth: <N>`, with N from 1 to 64,
under its `why`. Every move on a cycle of calls says `depth:`, and a move that says it and never calls itself is
refused, as is a depth outside 1 to 64 (`type`). A program cannot call itself, since programs are not called, and cannot
say `depth:`. A depth is one number that a person can read, a plan can show and every runtime keeps the same way; a
rule of "a strictly smaller input" would need a measure the compiler can prove falls, which Thym's values do not have.
A recursive move's contract and `asks` are those of every move on its cycle.

A call of a recursive move is one node, as any call of a user move is (section 11.1): its body is never expanded into
the plan, so the plan is as finite as the program text. The node's budget holds the move's `depth`. At run, the
runtime counts the move's calls on its stack, and a call that would nest the move one deeper than its depth refuses the run,
check `recursion`, naming the pass in the person's terms: "`give tree-of d` (line 17): tree-of went 13 deep; its
depth is 12". A depth bounds how deep a move goes, not how many calls it makes, so a plan with a recursive move that
asks has an open count of model calls (section 23).

```thym
thym 1

program folder-outline
  why: a tree of folders, one line per folder, every folder under its parent.

  takes d: folder
  gives outline: short

  move tree-of(d: folder): short
    depth: 12
    let below = for each sub in folders of d
      keep tree-of sub
    end
    give join [(join [d.path]), (join below)]
  end

  give tree-of d
end
```

```thym
thym 0

program story-in-brief
  why: a story, put plainly and then cut to a paragraph, for a listing.

  takes story: text
  gives brief: short

  move plain-paragraph(f: fabula): short
    let plain = entail f as told
    assert f covers plain else "the short lost part of the fabula"
    give cut plain to 120 words
  end

  let f = derive story
  give plain-paragraph f
end
```

### 8.4 `use`

A `use` line stands outside every block, usually just after the version line. It brings another file's moves, morphs
and contexts into scope: `use oes:thym/house` names everything the install's `thym/1` volume `house` declares (its
morphs and contexts, `rosa` among them), and `use house.thym` names everything a file beside this one declares. Two names that clash are a compile error, and the
refusal names both files. A `use`d path is relative to the program's folder and stays inside it: an absolute path, a
`..` step, or a link that leads out of the folder is an unknown URI, and the file is not read. A used file is read by
its own version line, and a `thym 0` program may not use a `thym 1` file (section 4.9).

```thym
thym 0
use oes:thym/house

program like-rosa
  why: a text said again in the house voice, for the help pages.

  takes t: text
  gives s: short

  let f = derive t
  give entail f as told with rosa
end
```

---

## 9. Errors: compile, plan, run

<!-- atem: three kinds at three times, each refusing whole, each with the line -->

| time | what is refused | with |
|---|---|---|
| **compile** | a parse error (`parse`); a version line that names a grammar the compiler does not know, `thym 1` syntax or a move only `thym 1` sees under a `thym 0` line ("this needs `thym 1`", section 4.9), or a `thym 0` program that uses a `thym 1` file (`version`); an unknown move (`unknown-move`); an unknown URI or `use`d file (`unknown-uri`); two `use`d names that clash (`use-clash`); an unbound name (`unbound`); a type error (`type`); an `insert` with neither `before` nor `after`, or with both (`type`); a name bound twice (`rebound`); recursion in `thym 0`, or in `thym 1` a move on a cycle without `depth:` (`recursion`); a `give` inside a loop (`type`); a `keep` outside a loop that collects, a loop that collects nothing or keeps two types, a contract that asks, a `depth:` out of range or on a move that never calls itself (`type`); a `keeps` naming no contract and no check (`unknown-check`); a block that `gives`, with a path that never reaches a `give` of each output, refused at the block's first line (`no-give`); emitted items with no `project` (`emit-without-project`); a static contract that cannot hold (the contract's check, such as `no-counts`), a fabula known to be of a flavour the move does not take among them (`flavour`) | the file and line, the check, and the fix where one is known |
| **plan** | a model-backed node while agent-free (`agent-free`, section 19); a prompt the machine's model cannot hold (`preflight`, the 16 GB rule, section 12.5); a missing or changed input (`input`: its digest, or a folder's tree digest, differs from the plan's); a plan whose program cannot be read (`no-program`); a move with no implementation here (`move`), or none under `--rules` (`rules`); a cloud route whose gate is closed (`cloud`); a cloud plan whose count of model calls is open and that was given no ceiling (`calls`, section 23) | the node, the count or the size, and what would make it run |
| **run** | a model-backed output that still fails its contract after narrow repair and its budget of attempts (the check's name, a kept contract's included), or that never fits the contract's schema (`schema`); a check the runtime lacks (the check's name, "not implemented"); a failed `assert`; a deterministic move that raises; a move that went deeper than its depth (`recursion`); a `thym 0` loop that section 8.1 refuses at run (`loop`); a fabula of a flavour the move does not take (`flavour`); a run that reached its ceiling of model calls (`calls`) | the trace, which says the node, the check and the attempts; nothing is written |

A refusal is a value, not an exception: the CLI prints it and exits non-zero, the server returns it as the response,
and the viewer shows it in place of the plan or the outputs. It carries `stage` (`compile`, `plan` or `run`), `line`,
`check` and `message`, and like MacroCOSM's refusal it reads as a plain no.

**A refusal speaks in the person's words**, at every stage and in both versions. It names the statement as the person
wrote it: the line without indentation or comment, cut to 60 characters with "…". It names that statement's line,
and, inside a loop, the pass in the person's terms: `for o = M:offer/seed-boxes` (the item's id),
`for t = tool/cli.py` (the file's path), `for l = line 7` (the line's number), `for x = the second member` (a member
of a written list, by its place; the plan's node names the same pass by the member as written, section 11.1). It names a value by the expression the person wrote, such as `(count staff)`. It never shows a
temporary (`t3`), a node's number, a node's id, an implementation's exception or the inside of a value as the
implementation prints it. The shape is:

```text
<statement> (line N[, for <var> = <member>]): <what failed, in the program's names>[: the fix]
```

For example: "`let f = derive story` (line 11): derive still fails coverage after 3 attempts: sentence 4 is not
covered". The one exception is a fault of the runtime itself: that refusal says so, as a fault of the runtime and not
of the program, and its record keeps the detail for whoever maintains the runtime. A plan keeps its temporaries in its
nodes' names, since plans are for reading the graph; a refusal never quotes a node's name, and quotes the statement,
which the runtime has because it runs with the program beside the plan (section 12.1).

---

## 10. Programs as documents

<!-- atem: a program enumerated into items and compiled back byte for byte -->

The enumerator reads a `.thym` file into a `thym/1` volume of kind `program` (section 17). Ids name their block: the
program's name, or `<program>.<move>` for a move local to a program.

- **One item per block.** A top-level block gives `P:program/<name>`, `P:move/<name>`, `M:morph/<name>` or
  `C:context/<name>`, with its heads as fields, its text verbatim in `body`, its `lines`, and its `order` among the
  blocks. A body runs from the block's first line to the next block, blank lines and comments included. A move inside
  a program gives `P:move/<program>.<name>`, with a body and lines but no order, since the program's body already
  holds it.
- **One item per statement.** A `P:step` holds the statement verbatim, its line, which statement it is, the move it
  calls and every move its line calls, what it binds, what it uses, and whether it asks. Steps are numbered from 1 in
  the order they are written, within each block: `P:step/<block>.<n>`. An `if` or a `for each` is one step that lists
  the steps inside it; `else` and `end` are structure, not steps. A block lists only its top-level steps.
- **Names and summaries, by rule.** A step's `name` is its statement without indentation or comment; its `summary`
  is the comment's text when the line has one, else the name. A block's summary is the first sentence of its `why`,
  capitalised. A contract's summary says what its move must leave true of what it gives; an `assert`'s names the
  condition. A plan's root summary counts its nodes and the ones that ask ("Seven nodes, three of which ask the
  model.", with number words up to twenty and "node" or "one of which asks" in the singular); a node's summary
  is its line's comment, else its name; a block with no `why` takes its first line; an `assert` inside a move
  says "The move's own check". Nothing is looked up by program.
- **One item per contracted call.** A `P:contract` names a call's move and the checks it carries:
  `P:contract/<block>.<n>` for the step's own move, and `<block>.<n>.<m>` for each contracted call nested inside it,
  `marked` included. An `assert` step's contract names the check its condition uses. A call of a user move carries the
  contracts the move inherits, and, in `thym 1`, the contracts the move keeps, after the inherited ones.
- **What `thym 1` adds.** A contract block gives `P:check/<name>`, or `P:check/<program>.<name>` for one local to a
  program, with `why`, `params`, `body`, `lines`, `order` and `steps` (its lines as steps, `P:step/<name>.<n>`). A
  `keep` is a step of form `keep`; a loop that collects is a step of form `for` whose `binds` is the loop's name. A labelled
  `give` holds its output's name in `slot`. A block that keeps a contract lists it in `keeps`, a move that may call
  itself holds its `depth`, and a program of several outputs lists each in `gives`. A `thym 0` file enumerates exactly
  as before: no field is new on any of its items.

`compile` on the items gives the file back byte for byte: the catalog's `front` (everything before the first block),
then each top-level item's `body` in `order`, is the file. enough's docs viewer shows a program at three densities like any
volume: its atem (the first sentence of the `why`), its short (the program as written, term-linked), and its fabula
(steps, moves and contracts as cards, with "mentioned in" across programs).

A program is also a text for every other move: `derive` on a `.thym` file gives a fabula of what it says, and an atem
of a program is the one line a listing shows.

---

## 11. The compiler

<!-- atem: seven stages, each refusing whole, ending in items and an inspectable plan -->

### 11.1 The stages

1. **Parse** the file into a tree, by recursive descent over the grammar of section 4.8 for the version its line
   names. The tree keeps each statement's line and source text.
2. **Resolve** names, URIs, `use`d files, and the moves every manifest in the registry declares (section 17.6).
3. **Type-check** by density. Every expression gets a type, every call is matched to a signature, and the provenance
   of each value (what it will be made from, by which move) is worked out.
4. **Contract-check** the static part (section 7.1).
5. **Estimate**: count the model-backed nodes, the sizes of their inputs and the output budgets; work out the largest
   prompt the plan will build; and ask `preflight` whether the machine's model holds it.
6. **Enumerate** into `thym/1` items (section 10), written as `<name>.thym.cosm` beside the program when asked.
7. **Plan** into a directed acyclic graph of nodes, written as a `thym/1` volume of kind `plan` (section 17.3).

The nodes of a plan come in evaluation order, a nested call before the call that takes its value:

- outside a loop's body, one node per move call, a `marked` modifier included (it is a `mark` node of its own), and one
  per `assert`; a call of a user move is one node;
- one node per `if`, for its condition; each node of a branch says which branch it is in (`then` or `else`) and waits
  on the condition;
- for a `for each`, one node per statement of its body: for each member when the collection is a list written in the
  program, otherwise once, marked `repeats`, taking the collection. A call nested inside a statement of a loop's body,
  `marked` included, is part of that statement's node and is evaluated with each member; it is never a node of its
  own. Under `thym 1`, a loop over a collection known only at run time is one node, and its body runs member by member
  as a unit; a loop that collects is one node too;
- no node for a `let` whose value is not a call; a filter (`h where …`) folds into the node that takes it.

A statement's node in a loop is named by its statement, with `, for each …` or `, for x = <member>` after it; it asks
when any of its calls asks, and it takes every name the statement and the loop's `where` read. Under `thym 1`, a loop
over a run-time collection whose body is one plain statement (neither an `if` nor a `for each`) gives exactly the
`thym 0` node; any other gives a node named by the loop's own line, with move `for`, `repeats: true`, `members` where
known, and `calls`, the moves its header and its body call, in written order, once each. A loop that collects gives
such a node, which also `gives` the loop's name. `members: {at_most: n}` is given only where the plan alone knows the
collection's size: a list written in the program, a folder input (its files, counted before the `where`), or a list
input (its members); a count
is never read from a volume or fabula input, so a plan does not depend on where it was planned. A call of a user move that keeps contracts carries `keeps`, and one that may call itself
carries `depth` in its budget.

A node takes names (inputs, bindings, or a temporary `t<n>` made by the nested call at node `n`) and gives at most one:
its binding, the block's `gives` name, or a temporary. A node runs after the nodes whose outputs it takes. The node that
gives a block's output also runs after every `assert`, `emit` and `withhold` before it, so nothing lands until every
check has passed. Its `after` list leaves out any node that another in the list already runs after.

A plan is inspectable before anything runs: the docs viewer draws it with the graph lens, the cosm viewer lists its
nodes with their `asks` flags and budgets, and agent-free mode refuses it on sight when it asks.

### 11.2 The package

In the reference implementation, enough (https://github.com/0gsd/enough), the compiler and the runtime are one Python
package, with the moves implemented by subject (`emf`, `doc`, `project`, `edit`, `morph`, `pack`) as the manifests'
`code` keys name them. The package depends on the standard library, PyYAML and the MacroCOSM reader, and on nothing else
of enough. The engines (Canon's derivation, DocOES, the model client, preflight) plug in from outside, through the
coprocessor and the moves' registration, so another program can carry a copy of the compiler and run it, as it can
the reader.

### 11.3 The command line

enough's command line, as an example of the operations a compiler and a runtime offer:

```text
python -m enough.thym check     <program.thym>                     compile only; prints the refusal or "ok"
python -m enough.thym plan      <program.thym> <inputs…>           compile and plan; prints the plan's atem and cost
python -m enough.thym run       <program.thym> <inputs…> [--rules] run; prints the trace's atem; writes outputs
python -m enough.thym run       --replay <run-id>                  re-run a recorded run (section 12.4)
python -m enough.thym trace     <run-id>                           show a trace
python -m enough.thym enumerate <program.thym>                     write <name>.thym.cosm
python -m enough.thym compile   <name.thym.cosm>                   the file again, byte for byte
python -m enough.thym conform   [<suite folder>]                   run the conformance suite
```

`plan` and `run` also take `--model local` (the default: the local model), `--model cloud` (the cloud model the host
names) or `--model cloud:<the provider's model id>`, and `--calls <N>`, a ceiling on the run's model requests (section
23). An input is given as `name=path`, a folder's path included (`repo=tool/`), and a list input by its name once per
member, in order (`xs=a.md xs=b.md`); when the program takes exactly one input, a bare path will do (`python -m
enough.thym run tidy.thym notes.md`), and for a list, one bare path per member. An argument is `name=path` when the text
before its first `=` is a name the program takes, and a bare path otherwise; a program of several inputs refuses a bare
path ("tidy takes story and voice; give each as name=path"). The bare path is the command line's rule, not the
grammar's, so it holds for both versions, and the plan it makes is the plan `name=path` makes.

Every enough command reads `ENOUGH_THYM_ROOT` (default `~/enough/thym/`) for where runs live, and writes nowhere else
unless it is told the path.

---

## 12. The runtime

<!-- atem: the plan walked in order; the model behind a contract; runs replayable -->

The runtime is non-traditional in four ways and ordinary in every other. Its values are documents. One of its
instructions is "ask a mind", behind a contract. Every run leaves a readable account of itself. And programs, plans and
traces are read in the same viewer as everything else.

### 12.1 Execution

`run` takes a plan and the program it was made from (the `.thym` file or its program volume; the plan's `program.sha256`
must match), since a filter's condition, a local move's body and an `assert`'s message are read from the program, and
checks the plan against the environment: the model present and large enough, agent-free or not, and
every input present with the digest the plan recorded. It then walks the nodes in a topological order. Independent
nodes may run in parallel or in sequence. A deterministic node calls its move's implementation. A model-backed node
builds the coprocessor call from the move's contract and the node's inputs. A failing node refuses the run: outputs
already made are discarded, nothing is written to the target paths, and the trace records how far the run got. Outputs
are written only when every node has succeeded, all at once, with the trace beside them.

A list input (`takes xs: list of T`, in either version) is given member by member, in order; an empty list is not
an input given. The plan records it as `{name, type, path, sha256, members: [{path, sha256}]}`: `path` is the first
member's, `sha256` is over the members' digests in order, a folder member also has `files` and `bytes`, and the list's
size is the sum of its members'. The run reads each member as it reads a single input of type T, held to its own
digest, names it `xs[2]` in a refusal (counted from 1), and gives the program the list in the order given. The record
of a node that takes the list names each member beside it, as `xs[n]`, with its digest and path.

A run snapshots every folder it takes (section 20.3), a list's folder members each as `inputs/<name>.<n>.folder.cosm`,
so that its replay needs no repository. A program of several
outputs lands them all in the same step, or none. A folder output lands as a directory, `outputs/<name>/`, holding
exactly the folder's files, and is renamed into place with every other output in that one step (section 20.4).

### 12.2 The coprocessor

One interface; three implementations in enough; any number elsewhere.

```python
class Coprocessor(Protocol):
    def complete(self, contract: Contract, inputs: Inputs, *, budget: Budget) -> Candidate: ...

Contract  = {move, schema, checks, repair}                         # what the move needs back and what must hold
Inputs    = {name: (value, digest)}                                # the node's operands, by name
Budget    = {attempts, output_words, prompt_tokens_max, seconds}   # the node's budget and the machine's limits
Candidate = {output, engine, route, provider, attempts, tokens, seconds, checks: [{name, ok, why}]}
```

A candidate's `route` and `provider` say where its model ran (section 23); a candidate recorded before this edition
has neither. A kept contract that failed (section 7.5) reaches the next request under `repair`, as the move's own failed
checks do. A move that asks more than once may name under `repair.failed` what it could not take in its last answer;
that reaches the next request too, after the runtime's own verdicts, so that a request asked again says why.

- **`ModelCoprocessor`** is enough's: its model client with the machinery of Canon's derivation, generalised, on the
  run's route, a local model or a cloud model through a broker. It asks for
  schema'd output; makes the narrow repairs the contract allows (drop an item whose span does not resolve, normalise a
  stance word, re-ask once with the failed checks listed); keeps within its attempts; and applies the lexicon floor and
  the span checks. An answer that is to be YAML and has prose before, after or instead of it (a narration, a heading,
  a second block, a block left open) fails `schema` on that attempt, before any other check, and is asked again for
  only the YAML; the runtime reads it so too, so a replay fails it again. An answer an engine reads for a move (the
  whole text's atem under `derive`) that the engine cannot read fails `schema` likewise, and never becomes open
  questions under green checks.
- **`RefusingCoprocessor`** is agent-free's. A plan with model-backed nodes is refused at plan time with their count
  (section 19), so it never reaches `complete`.
- **`ReplayCoprocessor`** is the conformance suite's. It answers each call with the candidate recorded for that node
  and attempt, and refuses when the contract or the input digests differ from the record's. So a trace plus its
  recorded candidates re-runs to the same outputs on any conforming runtime. That is Thym's answer to non-determinism:
  contained by contracts, reproduced by replay.

### 12.3 Traces

A run writes one `thym/1` volume of kind `trace`. Its catalog names the run; the program (name and sha256); the plan's
sha256; the environment (the implementation and its version, the id of the model that ran and its context size, the
route and the provider, agent-free or not, the machine's memory band); when the run started and ended; and its outcome.
A record of a loop that runs as one node says how many `passes` it made, and holds a row `<name>.<k>` per value a loop
that collects kept. One `R:record` item per node holds the node, the move, the
digests of the inputs and outputs, and the candidate's fields: the engine (`code` for a deterministic node, `rules`
for a scaffold, `model:<id>`, or `skipped` for a node on the branch not taken), attempts, tokens, seconds, and every
check with its verdict and, for a failed check, why; a node asked more than once also keeps `tries`, each failed
attempt's checks with their reasons, so a refused node explains all its tries. A record's tokens are its requests' and those of the model calls
its engines made, as the engine reports them where it does, else estimated; the environment's context size is the
model's window, read when a model runs and 0 when none does; and the trace's root item names the engines whose calls
the run recorded (`engines`, section 12.4). The trace also carries a copy of its plan's nodes, so that its
records' `node` references resolve inside the volume and the trace lints clean on its own. In enough, traces live under `ENOUGH_THYM_ROOT/runs/` as
`<run-id>.trace.cosm`, with a copy beside the outputs when they land in a volume. A value's `made` names its run, and so
its trace. The docs viewer shows a trace at the fabula density as cards; its atem is one line: "derived 17 items from
close.md in 11 s on g40-04, all checks green".

### 12.4 Replay

`run --replay <run-id>` runs that run's plan with the `ReplayCoprocessor`, over the candidates recorded under the run as
`candidates/<node>[-<k>].<attempt>.cosm` (a node that asks more than once records each answer). The outputs must be
byte-identical to the recorded run's: they carry the recorded run's id in `made`, and the replay's own trace takes a
new id with `replay_of` naming the recorded run. A difference is a conformance failure of the runtime, not of the
program.

One counter per node keys every call the node makes, so that no two collide: its first request is `<node>`; every
later request, and every model call one of the host's engines makes for it (Canon reads each passage through the
coprocessor), is `<node>-<k>`, k counted from 1 across both; and every call it makes to an engine (FEED's lookup,
Canon's derivation, DocOES, the surrounding catalog) is `<node>-e<k>`, recorded once, at attempt 1, as `{engine,
inputs: {call}, keys, tokens, seconds, output}`: the engine and the function called, the sha256 of the call's
arguments in canonical form, the keys of the model calls the engine made while it ran, what they cost, and what the
engine answered (`raised`, in place of `output`, for a call that raised). Only a node's own engine calls are recorded;
an engine that calls another records the outer call, whose answer holds the inner. A replay answers every engine call
from its record and runs no engine, so it needs no dictionary and no engine; it refuses at the first input, call or
prompt whose digest differs from the record's, before any engine or model work. A run whose trace names no `engines`
was recorded before engine calls were, and replays with the host's live engines.

A replay reads a folder input from the run's snapshot of it (section 20.3), never from the disk, so it needs no
repository. A candidate recorded without a route replays without one: the outputs it gives carry no `route` in `made`,
as they did when they were recorded. Model calls inside a loop or a recursion are keyed on the node's one counter in
the order they were made (pass order, depth first), so a replay meets them in the same order.

### 12.5 Budgets and the 16 GB rule

A plan carries the largest prompt it will build. At plan time the runtime asks `preflight` whether the machine's model
holds it; on a small machine a program may be refused with the number and the fix, as enough refuses a chat the machine cannot
hold. Every node has an
`attempts` budget (3 for a model-backed node, 1 otherwise) and an output budget in words (the call's `to N words`, or
else the machine's). The trace records what each node cost. The rule reads the window of the run's model: a local
model's, or a cloud model's context length. A recursive move's node carries its `depth`, and a run may be given a
ceiling on its model requests, `--calls N`, which a cloud plan with an open count of calls must be given (section 23).

### 12.6 Portability

No Python-only semantics. No reliance on mapping order beyond what the COSM YAML subset fixes. No floats in contracts:
bands and scales are integers, and the ratios of section 13.3 are integers per hundred or per thousand. Digests are
sha256: a text's over its bytes, a volume's over its catalog file, a file's always over its bytes, a folder's over its
files as the tree digest (section 20.1), and a mapping's over the reader's canonical dump (keys in file order, LF
newlines, UTF-8). The folder rule is the same in every language and uses no ignore-file semantics; the compiler's own
`dump` writes program volumes for people, with block scalars, and is never a digest's form. File paths are URIs. Time is UTC in traces and local only in file names. A JavaScript
runtime that passes the conformance suite is a conforming runtime, and the docs viewer could then make readings in the
page.

---

## 13. The null morph, the ten scales, morphs

<!-- atem: the plainest entailment is the reference; a morph is a measured departure -->

### 13.1 The null morph

The **null morph** is Thym's reference entailment of a fabula. It goes in `told` order, one claim per sentence, in the
commonest FEED words that still say it. It says every stance in a fixed phrase ("the author holds that", "it is assumed
that", "reportedly"). It has no figure, no humour, no allusion and no contraction, and it is in the third person unless
the fabula's claims are in the first. It is one paragraph: a paragraph mark the model adds is read as none,
never as a departure. It is model-backed, with the tightest contract in the language, `null-pinned`:
every scale is 1. Its scaffold is the ordered outline said in the items' own sentences, which `--rules` gives (section
19). The null morph exists so that morphs are *differences*: a morph is what a text does that the null short of its
fabula does not.

### 13.2 The ten scales

Each scale is an integer from 1 to 5. 1 is the null's value on every scale, and 5 the farthest departure. Seven scales
are statistics, six over the text and `analytical-depth` over its fabula; three are the model's judgement, with
examples. Every word a measurement counts is a FEED headword (section 13.3).

| scale | 1 | 5 | basis |
|---|---|---|---|
| `register` | plain | ornate | statistics: rare words |
| `sentence-length` | short | long | statistics: words per sentence |
| `paragraph-rhythm` | even | varied | statistics: sentences per paragraph |
| `analytical-depth` | claims only | every reason | statistics on the fabula: reasons per claim (carried, section 13.4) |
| `figurative-density` | literal | figurative | judgement |
| `stance-style` | flat | hedged | statistics: hedge words |
| `person-voice` | impersonal | personal | statistics: first and second person |
| `formality` | plain | marked, `toward: formal` or `toward: casual` | statistics: contractions, Latinate and casual markers |
| `humour` | none | much | judgement |
| `allusion` | none | dense | judgement, with the fabula's entities as candidates |

`formality` is the one scale with two directions away from plain, so a morph that departs on it says which: `toward:
formal` or `toward: casual`.

### 13.3 Measurement

Ratios are per hundred or per thousand words, compared as integers. The thresholds are this edition's. The conformance
suite pins them, and a later edition may move them only with an entry in the Changes appendix (section 25).

| scale | measure | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| `register` | the share of distinct words outside FEED's common band (FEED's bands 4 and up are common; a word with no band is rare when it has nine letters or more and common when it has eight or fewer, the nine-letter rule; names never count; the null short's register also exempts every word its fabula's items use, since it must say them), per hundred | < 2 | < 5 | < 10 | < 20 | ≥ 20 |
| `sentence-length` | mean words per sentence | ≤ 10 | ≤ 15 | ≤ 20 | ≤ 27 | > 27 |
| `paragraph-rhythm` | the spread of sentences per paragraph: standard deviation over mean, per hundred; needs three paragraphs, else 1 with confidence 30 | < 15 | < 30 | < 50 | < 75 | ≥ 75 |
| `analytical-depth` | the fabula's reason links (`supports`, `depends-on`, `resolves`) per claim, per hundred | < 10 | < 30 | < 60 | < 100 | ≥ 100 |
| `figurative-density` | sentences the model judges figurative (metaphor, simile, personification), per hundred sentences | 0 | < 5 | < 15 | < 30 | ≥ 30 |
| `stance-style` | hedge words (`maybe`, `perhaps`, `seems`, `might`, `could`, `arguably`, `probably`, `likely`, `somewhat`, `rather`, `I think`, `I suspect`) per thousand words | < 5 | < 10 | < 20 | < 40 | ≥ 40 |
| `person-voice` | first and second person pronouns and address (`I`, `me`, `my`, `we`, `us`, `our`, `you`, `your`) per thousand words | < 5 | < 15 | < 30 | < 60 | ≥ 60 |
| `formality` | toward casual: contractions and casual markers (`gonna`, `kinda`, `yeah`, `ok`, `stuff`, interjections) per thousand words; toward formal: Latinate markers (`utilise`, `commence`, `prior to`, `in accordance with`, the passive in more than half of sentences, honorifics) per thousand words; the larger decides `toward` | < 5 | < 15 | < 30 | < 60 | ≥ 60 |
| `humour` | sentences the model judges to be making a joke or an ironic turn, per hundred sentences | 0 | < 3 | < 10 | < 20 | ≥ 20 |
| `allusion` | references to works, sayings and figures outside the text's subject, judged by the model with the fabula's `E:work`, `E:person` and quotations as candidates, per thousand words | 0 | < 1 | < 3 | < 6 | ≥ 6 |

For every scale, `measure` gives a `value`; a `basis` (`statistics` or `judgement`); `evidence`, one to three sentences
of the text that moved it; and a `confidence` as an integer per hundred (no floats reach a `.cosm`). Below 300 words
or three paragraphs, a statistics scale reports a confidence of at most 50, and a judgement scale at most 40. The word lists above are this edition's seed; the
reference implementation keeps them beside its measures. The statistics read English: the lists, the honorifics, the
stance phrases, FEED's bands and the nine-letter rule are English's, so a text in another language is measured
as if it were English (its judgement scales still hold, since the model reads the language); lists per language are
reserved for a later edition.

### 13.4 Holomorph and isomorph

A **holomorph** is `measure t against null of f`, for a person's text `t` with fabula `f`: each scale's value as a
departure from the null, with its evidence. It is derived from any text the person writes with Ascribe active, and it
sharpens over a corpus: a corpus's morph is the scale-wise median of its texts' morphs, and each scale's confidence
rises with the number of texts. A person may **pin** a scale by hand; the pin wins, and the scale is listed as pinned.

`analytical-depth` is carried from the fabula rather than measured on the text or the short: a text's depth is its fabula's.
An entailment may say fewer of the fabula's reasons than the fabula holds, never more, so the fabula's depth is a ceiling. The
null says the claims without the reasons that link them, and so sits at 1. In a `read`, the morph's value is the ask,
up to that ceiling.

An **isomorph** is a holomorph the owner chose to share: the same shape, marked shared, released from the holograph by a
program, as an isograph is. A publication may ship one in its package so that readers can read it the author's way. A
person may keep several, one for letters and one for work.

### 13.5 Morph blocks and morph items

A morph may be declared by hand in a program file, one scale per line; the unlisted scales sit at 1.

```thym
thym 0

morph plain-letter
  why: a letter home: personal, a little hedged, never ornate.

  person-voice 4
  stance-style 3
  formality 2 toward casual
end

program letter-home
  why: a note told the way I write letters.

  takes t: text
  gives s: short

  let f = derive t
  give entail f as told with plain-letter
end
```

As an item, a morph is `M:morph/<slug>` in a `thym/1` volume (section 17.3). It holds `scales` (scale → value, all ten);
`toward`, the direction of `formality`; `evidence`, `basis` and `confidence`, scale by scale, when it was measured;
`pinned` (a list of scale names); `derived` (`from`: text digests; `at`; `by`) or `declared: true`; and `shared`.

---

## 14. Readings

<!-- atem: a short of someone else's fabula in your morph: local, labelled, never the source -->

A **reading** is `read f with m in c`: an entailment of a fabula in the reader's morph (their holomorph, or an isomorph they
chose), shaped by the reader's occasional context and made on the reader's machine. Its contract is `morph`'s with two
more checks. It is **labelled**: `read_through: <morph name>` in the file's front matter, and the reading footer at its
end. And it **never touches the source** (`never-source`): its path is never an input's path, and no input file changes.
A reading is saved beside the package or the text as `<text-stem>.read-<morph>-<YYYY-MM-DD-HHMM>.md`, in local time,
taking `-2`, then `-3`, on a collision, as shorts do.

The footer:

```text
*a reading of notes.md through plain-letter, made here on 2026-11-01 by g40-04; the text stands unchanged*
```

The day is the UTC day, so a replay reproduces the line.

On screen a reading is always shown as "read through *name*", and the label is never hidden. A website that serves
packages may offer readings in its own isomorph and let a visitor override it with theirs. Nothing a reader does changes
what the author published. A reading of a reading is refused: `read` takes a fabula, and a reading is a short.

---

## 15. Packages

<!-- atem: the self-contained export of a text: a folder, one file, or encrypted -->

### 15.1 Folder form

`<name>.thym/` (a folder; a program is a file of the same suffix, `<name>.thym`, and a library tells the two apart by
the one being a folder with a `package.cosm` inside):

```text
text.md            the author's text, exactly as published
<twin's name>      the text's fabula, fabula/1, under the name its twin had (notes.md.fabulan.cosm); every span
                   resolves into text.md. A package made before this edition holds it as fabula.cosm, emf/1 read as a fabulan
morph.cosm         thym/1, kind morph (optional: the author's isomorph for this text)
context.cosm       thym/1, kind context (optional: the occasional context, and the surrounding volume's catalog excerpt)
graph.cosm         an isograph made for this text (optional; only what the holograph released for this text)
package.cosm       the catalog: contents with digests, the program and the trace that made it, the notice
```

A package has three forms, each saved beside the text it was made from and named by that text's stem, `<name>`: the
folder form `<name>.thym/`, the single-file form `<name>.package.cosm` and the encrypted form `<name>.thym.enc`
(`notes.md` gives `notes.thym/`, `notes.package.cosm` and `notes.thym.enc`). Section 15.3 is the rule for which of
them `package` lands. A reader of a library lists each form as one thing (the home file system's `kind: package` and
`kind: sealed`) and never opens the folder up as texts. enough's export makes a package by running a
program over the text and its fresh fabula (`package story, f, m, c, g`, with `context of story` and `graph of
story`), so the package's catalog names that program and run; it derives nothing. A package finds its fabula by its role in the catalog, `role: fabula`, never by the file's name, and
nothing is renamed on the way in or out. Unpacking verifies every digest and every span before it writes anything,
then writes the text beside the package as `<name>.md` and its fabula under the name the package carries it by
(`<name>.md.fabulan.cosm`; from a package that holds `fabula.cosm`, the text's twin `<name>.md.cosm`), whose
`source.path` and locators say the text's name again, with the morph, context and
graph as `<name>.morph.cosm`, `<name>.context.cosm` and `<name>.graph.cosm`; it writes nothing on a failure, and never
over a file that differs.

### 15.2 The catalog

```cosm
oes: thym/1
kind: package
id: thym/orchard-notes
name: The Hollins Lane orchard, autumn notes
contents:
  - {path: text.md, sha256: 54055e89856a29970eeb75baa1c24db60a13a5527a5a11b7cce650de07dc71c7, role: text}
  - {path: fabula.cosm, sha256: '0000000000000000000000000000000000000000000000000000000000000000', role: fabula}
  - {path: morph.cosm, sha256: '1111111111111111111111111111111111111111111111111111111111111111', role: morph}
made: {program: {name: publish-story, sha256: '2222222222222222222222222222222222222222222222222222222222222222'},
       trace: {run: 2026-11-01-1042-7f3a, sha256: '3333333333333333333333333333333333333333333333333333333333333333'},
       at: 2026-11-01T10:42:00Z, by: enough/0.5.0}
notice: "A Thym package. The text is its author's; the fabula, morph and context describe it. Readings made from it are the reader's and are labelled."
nodes: []
```

### 15.3 Single-file and encrypted forms

`package` lands the single-file form, with the folder form `<name>.thym/` beside it; it makes the encrypted form only
when sealing is asked for. The **single-file form**,
`<name>.package.cosm`, is the same catalog with each file's bytes as a block scalar under
`contents[].text`, so that one file travels. The **encrypted form**, `<name>.thym.enc`, is the single-file form
encrypted on the owner's machine and handed, with a key, to a chosen party: this is what a cryptotype and a cryptograph
*are*. The cipher is Comprise's bundle scheme, `comprise-bundle/0` (a data key per package, AES-256-GCM over chunks, an
encrypted manifest), vendored into enough so that one cipher serves both subjects; the catalog's `encrypted: {cipher,
key: shown-once}` field names it, and the key never leaves the owner. An index may hold only **consented match tokens**, hashes
of characteristics the owner chose to make matchable, so that a search can match an encrypted package without reading
it.

The encrypted form is a `thym/1` package catalog that holds nothing in the clear: `encrypted: {cipher:
comprise-bundle/0, aead, key: shown-once, hid, bundle, keyring, manifest, chunks}`, binary values in base64. The key is
Comprise's recovery code (fifteen random bytes as twenty-four base32 characters, shown as six groups of four), which
wraps the package's data key by PBKDF2-HMAC-SHA256 at 600,000 iterations, as Comprise's recovery keyring entry does; it
is shown once and stored nowhere. enough uses the `cryptography` package for AES-256-GCM, so a package sealed in enough
is Comprise's and opens there. Where AES-256-GCM is not available (a
vendored runtime without that package), the same layout is sealed with an encrypt-then-MAC AEAD built from HMAC-SHA256 alone (`aead:
hmac-sha256-ctr`: an HMAC keystream in counter mode, then a 16-byte HMAC tag, under keys split from the one key by
HKDF), and the file says so; a package sealed with AES-256-GCM opens only where AES-256-GCM is available.

A conforming reader of a sealed package refuses a file larger than its size cap before parsing it, refuses YAML
anchors and aliases in the file's clear part, and bounds what its list of chunks may open to. The limits are the
implementation's; that they exist is the rule, and each refusal is whole: nothing is opened and nothing is written.

### 15.4 The laws of a package

The author's text is the package's text as the author told it: `unpack` gives it back byte for byte, and what is checked is that
every span of the fabula resolves into it and that the fabula covers it. Every file's digest is in the catalog
(`digests`). The catalog names the program and the trace that made the package. Nothing is in `graph.cosm` without a
release recorded in the holograph (`released`). A package never names its author unless the author put the name in the
text.

---

## 16. Context

<!-- atem: the volume a text lives in; the occasion it is read on -->

### 16.1 Surrounding context

The **surrounding context** is the volume a text sits in: its volume's catalog in the home file system (Canon's `canon.cosm`), the project's catalog, or a
site's served catalog when a website serves packages. It is read, never written. `context of story` gives the catalog
excerpt around the text: its neighbours, the volume's name and scope, and the terms the volume defines. A program may
use it to link terms, to choose a morph the volume prefers, or to make a text's short in the light of its neighbours.

### 16.2 Occasional context

The **occasional context** is just-in-time: why this text, for whom, in what medium, at what moment, under what
constraints. It is a `thym/1` item of kind `context` with the fields `purpose`, `audience`, `medium`, `moment`, `hurry`
(a bool), `words` (a budget), `minutes` (a reading time), `language`, and any field a program names. The author's
occasion shapes the entailment (a note for a friend, a brief for a board); the interpreter's shapes the reading (on a
phone, in a hurry: the atem, expanded to three hundred words). A context may be declared in a program file and thrown
away:

```thym
thym 0

context on-the-train
  why: five minutes on a phone, standing.

  medium "phone"
  hurry true
  words 300
end

program read-my-way
  why: a package is read on the reader's terms: in a hurry, the short way in;
       otherwise an entailment in the reader's own morph, for this occasion.

  takes p: package, mine: morph, now: context
  gives r: short

  let f = fabula of p
  if now.medium is "phone" and now.hurry then
    give expand (atem f) with f to 300 words     -- the short way in
  else
    give read f with mine in now                 -- an entailment in my morph, labelled a reading
  end
end
```

---

## 17. The `thym/1` volumes and the `moves:` block

<!-- atem: programs, morphs, contexts, plans, traces, packages; how any manifest declares moves -->

`thym/1` is a built-in of the core of MacroCOSM OES (its section 18.7), and this section specifies it.

### 17.1 The catalog

A `thym/1` volume is one file. Its catalog declares `oes: thym/1` and says which of seven kinds of volume it is:

| `kind` | file | holds |
|---|---|---|
| `program` | `<name>.thym.cosm` beside the program | the enumeration of one `.thym` file (section 10); `source: {path, sha256, size}`, `front`, `built` |
| `morph` | `<name>.morph.cosm` | one or more `M:morph` items |
| `context` | `<name>.context.cosm` | one or more `C:context` items |
| `plan` | `<run-id>.plan.cosm` | `program`, `inputs` (each `{name, type, path, sha256}`; a folder's also `files` and `bytes`, a list's `members`, section 12.1), `estimate`, the `R:plan` item and its `R:node` items |
| `trace` | `<run-id>.trace.cosm` | `program`, `plan`, `environment`, `started`, `ended`, `outcome`, the `R:trace` item, its `R:record` items, and a copy of the plan's `R:node` items |
| `package` | `package.cosm` or `<name>.package.cosm` | `contents`, `made`, `notice` (section 15) |
| `folder` | `inputs/<name>.folder.cosm` in a run | a run's snapshot of a folder it took: `name`, `path`, `tree`, `commit`, `origin`, `files` (each `{path, sha256, size}`, with `binary: true` for a file that is not text) and `texts` (each text file's bytes as a block scalar) (section 20.3) |

Catalog keys: `oes`, `macrocosm`, `id`, `name`, `kind`, `source`, `front`, `built`, `program`, `plan`, `inputs`,
`estimate`, `models`, `environment`, `started`, `ended`, `outcome`, `contents`, `made`, `notice`, `encrypted`, `path`,
`tree`, `commit`, `origin`, `files`, `texts`, `nodes`. The id is `thym/<slug>`. A plan whose nodes ask carries
`models`, the route and the count of model calls (section 23).

### 17.2 The modules and their kinds

| module | kinds | what |
|---|---|---|
| **P** Programs | `program`, `move`, `step`, `contract`, `check` | a block, a user move, a statement, a step's contract, a contract block (`thym 1`) |
| **M** Morphs | `morph` | ten scales with evidence |
| **C** Contexts | `context` | an occasion |
| **R** Runs | `plan`, `node`, `trace`, `record` | a plan and its nodes; a trace and its records |
| **K** Packages | `package`, `reading` | a package's catalog entry; a saved reading's record |

Kinds are unique across the modules, as in every format. Every item has the envelope (id, type, name, summary,
status, visibility, provenance, pending, links) and may carry `made` (section 5.3).

### 17.3 Ids and the fields of each kind

`<module>:<kind>/<slug>`, with the slug grammar of `doc/1` (dots allowed, so a step can name its program):

| kind | id | fields beyond the envelope |
|---|---|---|
| `program` | `P:program/<name>` | `why`, `must` (a list), `decided` (a list of `{date, what}`), `takes`, `gives` (lists of `{name, type}`), `body` (verbatim), `lines`, `order`, `steps` (refs to its top-level steps), `moves` (refs to its local moves) |
| `move` | `P:move/<name>` or `P:move/<program>.<name>` | as `program` (`order` for a top-level move only), plus `params`; in `thym 1`, `keeps` and `depth` |
| `step` | `P:step/<program>.<n>` | `of` (ref), `n`, `text` (the line verbatim), `line`, `form` (`let`, `assert`, `if`, `for`, `emit`, `give`, `withhold`, `effect`), `move`, `calls` (every move the line calls), `binds`, `uses` (names), `asks`, `contracts` (refs), `slot` (a labelled emit's field, or a labelled give's output); `thym 1` adds the form `keep`; an `if` adds `lines` and `branches` (`{then, else}`, refs); a `for each` adds `lines` and `steps` (refs) |
| `contract` | `P:contract/<program>.<n>` | `of` (ref), `move`, `checks` (a list of check names) |
| `check` | `P:check/<name>` or `P:check/<program>.<name>` | `thym 1`: a contract block: `why`, `params`, `body` (verbatim), `lines`, `order`, `steps` (refs to `P:step/<name>.<n>`) |
| `morph` | `M:morph/<slug>` | `scales`, `toward`, `evidence`, `basis`, `confidence`, `pinned`, `derived` or `declared`, `shared` |
| `context` | `C:context/<slug>` | `purpose`, `audience`, `medium`, `moment`, `hurry`, `words`, `minutes`, `language`, and any field |
| `plan` | `R:plan/<run-id>` | `nodes` (refs, in order), `asks` (a count), `largest_prompt` (tokens) |
| `node` | `R:node/<n>` | `step` (`{program, n}`), `move`, `asks`, `takes` (names), `gives` (a name), `after` (refs), `budget` (with `depth` for a move that may call itself), `line`, `repeats`, `branch` (`then` or `else`), `slot` (a labelled `emit`'s field); in `thym 1` plans, `calls` (the moves a loop's header and body call), `members` (`{at_most: n}`), `keeps` (the contracts a called move keeps) |
| `trace` | `R:trace/<run-id>` | `records` (refs), `outcome` (`landed`, `refused`), `stopped_at` (a ref, when refused) |
| `record` | `R:record/<n>` | `node` (ref), `move`, `inputs`, `outputs` (lists of `{name, sha256, path}`), `engine`, `attempts`, `tokens`, `seconds`, `checks` (a list of `{name, ok, why}`), `tries`; `passes` for a loop run as one node |
| `package` | `K:package/<slug>` | as the catalog's `contents` and `made`, for an index that lists packages |
| `reading` | `K:reading/<slug>` | `of` (the package or text), `read_through`, `path`, `at`, `by` |

Steps are numbered from 1 in the order they are written. In a move local to a program, `<program>` reads
`<program>.<move>` (`P:step/open-house.offer-line.1`); a contract for a call nested inside a step adds `.<m>`
(`P:contract/publish-story.3.1`), as section 10 says.

### 17.4 Checks

The envelope checks the generic reader runs, and six of `thym/1`'s own, which a Thym compiler and runtime run; the manifest states
them as prose under `checks.own`, so a generic reader neither runs nor lists them, and lints a Thym volume on the
envelope alone: `program-compiles` (a `program` volume's `source` compiles to these items, by its own version line), `plan-acyclic`,
`trace-complete` (every node has a record, or the trace is `refused` with `stopped_at`), `scale-range`, `digests` (a
package's files match its catalog), `reading-labelled`.

### 17.5 Renderers

`program` (the file compiled back; lens `{kind: short, order: told}`), `plan` (a flowchart of nodes along `after`),
`trace` (a table of records: id, move, engine, attempts, seconds), and, by code, `text-tree` and `compile`.

### 17.6 The `moves:` block

Any manifest, a built-in's or a MiniCOSM's, may carry a `moves:` list. A format whose manifest another specification keeps declares its moves in
a sidecar `<name>.moves.cosm` beside the manifest, a mapping `{moves-of: <format>/<major>, moves: [...]}`; Comprise's
is `comprise.moves.cosm`. When both exist, the manifest's list wins and the sidecar is reported. The generic reader
keeps the block as an unknown key; the Thym compiler reads it. Each entry:

| key | holds |
|---|---|
| `name` | the move's name, a FEED headword, unique across the registry but for an entry that `extends` a move |
| `takes` | a list of accepted types for the operands, in order; alternatives joined by `\|`; empty when the move's argument is its `of` |
| `gives` | the type given |
| `modifiers` | a mapping, modifier word → the type it takes (`as: order`, `to: words`, `with: morph`, `of: package`) |
| `asks` | `true` when the move needs the model; absent or `false` otherwise |
| `contract` | the list of check names (section 7.3) |
| `scaffold` | the name of the rules-mode stand-in, when one exists |
| `code` | the reference implementation, informative: `enough.thym.moves.emf:entail` |
| `says` | one line, in FEED words, for the viewer and the readvisor |
| `since` | `1`: the move exists for `thym 1` programs only (section 4.9) |
| `extends` | `true`: the entry adds `as` kinds to a move another manifest declares, and nothing else (its `modifiers` are `{as: <kinds>}`); a call of one of its kinds gives the entry's `gives`, keeps its `contract` and runs its `code`. Ascribe's `project … as isograph` and `project … as allograph` are one, an entry whose `as` lists both, written as one string, `isograph | allograph`, since a manifest gives a modifier's alternatives as a single string and refuses a YAML list for one (section 6.2) |
| `thym-1` | a mapping of the keys a `thym 1` program sees in addition to, or in place of, the entry's own: `takes`, `gives`, `modifiers`, `contract`, `scaffold`, and the three below; a `thym 0` program sees the entry without it |
| `gives-when` | a list of `{as: <words>, gives: <type>}` or `{takes: <type>, gives: <type>}`: the type a call gives when its `as` word, or its first operand's type, is one of these |
| `contract-when` | the same shape, with `contract: [...]`: the call's contract when its `as` word or first operand's type matches; else `contract` |
| `scaffold-when` | the same shape for `scaffold`; a rule may say `scaffold: none`, and a call it matches then has no scaffold, so that `--rules` refuses it at plan time |

`gives` may also say `same-as-with` or `same-as-in`: the call gives the type of its `with` (or `in`) value.

---

## 18. Projections: the dial as a program

<!-- atem: a holotype transcoded by a program whose contracts are the schema's rules -->

An isotype is a holotype *transcoded*: `project h as isotype`, under a program that gives every item a density
(`fabula`, `short`, `atem`, or withheld) and a marking (`verified`, `stated`). The target schema's rules
(`comprise-isotype/0`: default-deny, assertions not measurements, withhold never falsify, epochs and bands, verified
only where derived, the standing gate) are the contract of `project` (section 6.3), so the schema stops being the
ceiling and becomes the law. The isotype's draft step is three preset programs (minimal, fuller, house), and a verified
owner may write their own. A release carries the digests of the program and the trace that made it. The Comprise side
is a specification of its own, Comprise OES (https://comprise.cosmoes.org/); Thym defines none of it, and a Thym
implementation reads what Comprise produces. A person's dial is the same move over a holograph, `project h as
isograph`, to the schema of Ascribe's isograph (Ascribe (https://ascribe.cosmoes.org/), its section 14.1), whose rules
are then the contract. `project h as allograph` makes the other projection a holder runs: the allograph, which keeps
only the holder's experience and domain expertise and is the one thing of a holograph a registry lists (Ascribe, its
sections 14.6 and 14.7). Each MiniCOSM declares the kinds it projects: `isotype` and `paratype` are Comprise OES's, and
`isograph` and `allograph` are Ascribe's. Listing an allograph is the implementation's act after the run; no move sends
anything to a registry. Ascribe's cryptograph and isomorph are made by the implementation, and moves for them are
reserved for a later edition; it makes match tokens no more, so no move is reserved for them.

A projection is an entailment made by rule: a holotype entails its isotype and its paratype, and a holograph its
isograph and its allograph (MacroCOSM OES, its section 18.1). What it makes holds by construction, since the schema's rules are its
contract and no model is asked. `entail` (section 6.3) makes an entailment by a model under contract, and what it makes
holds only because its checks hold it. The two kinds stay on the two sides of the line section 1 draws: `project`
transcodes, and `entail` transcognizes.

The example program, deterministic end to end:

```thym
thym 0

program open-house
  why: show what the house sells and what it wants, as the house says them; say how many
       people only in bands; keep everything internal inside.

  takes h: volume                  -- the holotype
  gives i: volume                  -- an isotype: comprise-isotype/0, and no more

  move offer-line(o: item): item
    give mark o as verified        -- an offer is what the house does now: verified
  end

  for each o in h where kind in [product, service, platform]
    emit offer-line o
  end
  for each a in h where kind is aim
    emit mark a as stated          -- an aim is the house's own words: stated
  end
  let staff = h where module is employees
  emit employees: band (count staff) as [none, some] marked verified     -- never a number
  withhold h where visibility is internal
  give project h as isotype
end
```

A preset that adds `atem` lines for the offers asks the model, and its plan says so; `project` itself never does.
An unlabelled `emit` adds an item to the projection; a labelled one (`emit employees: …`) puts a value into a field the
target schema names, and the schema says which fields may be filled. An item neither emitted nor withheld is left out
as if withheld, by default-deny, and the plan says how many such items there are, so the author sees what the program
never mentioned. The example is an illustration, not Comprise's *minimal* preset: Comprise emits `employees` only when
the holotype holds people or says it has none, and always fills `shape.markets`; the preset says so.

---

## 19. Agent-free

<!-- atem: the agent off: only deterministic plans run; scaffolds where they are honest -->

In agent-free mode the coprocessor is the refusing one: a plan with model-backed nodes is refused at plan time with
their count, the route and the first one's statement and line ("3 steps ask a model on the local route, the first `let f
= derive story` (line 11); agent-free is on"). A cloud model is a model too: agent-free refuses a plan on the cloud
route exactly as it refuses one on the local route, at plan time, before any broker is asked. A plan with no
model-backed node runs. With `--rules`, each model-backed move that declares a `scaffold` runs it instead: `derive`
gives the rules twin, `atem` the labelled scaffold, `entail` and `null` the ordered outline, and `measure` the seven
statistics scales with the three judgement scales pending; in `thym 1`, `derive … as code` gives its file's outline
marked pending, `entail` at a catem's depth the uses and interfaces in told order, `question` the bank's questions only,
and `settle` its rules part, leaving the answers that must be read again answered and unsettled, for a run with a model.
A move with no scaffold (`expand`, `morph`, `read`, `reword`, `derive` of a folder, `entail … as code`) still refuses,
at plan time: "1 step asks a model and has no scaffold: give code: entail f as code (line 12); --rules runs no model"
(with agent-free on, in the words above, which then add that the steps have no scaffold).
`survey`, `history`, `record` and the editing moves other than `reword` ask nothing, and run. The trace says `engine:
rules` for each scaffold, and every output is marked `state: pending`, as a fabula's rules mode marks a twin. The viewer
offers only plans that can run.

---

## 20. Folders and code

<!-- atem: a folder of code decompiled to a fabulac, and the cshort and catems it entails -->

`thym 1` reads a folder of code as a value, decompiles it into a fabulac, and compiles a fabulac back into a cshort and
its catems. The fabulac, the cshort and the catem are MacroCOSM OES's (its section 18.4.7); this section says how a
program reaches them.

### 20.1 The folder type

A **folder** is a directory tree read under one fixed rule, with a digest. Its value is the list of the files the rule
keeps, each `{path, sha256, size, binary}`, where `path` is relative to the folder, written with forward slashes and
without a leading `./`. The text of a text file is read when something walks or reads it.

**The rule** has no options. A folder holds every regular file under its root except:

1. any path one of whose parts begins with `.` (so `.git/`, `.venv/`, `.env`);
2. any path one of whose parts is `__pycache__` or `node_modules`;
3. symbolic links, which are never followed: a link is left out.

A file is **text** when its bytes are UTF-8 (a byte-order mark is tolerated), hold no zero byte, and number at most
1,000,000 bytes. Any other file is binary: it is counted and listed, and it is never read as text. A text's `lines`
are its line feeds, and one more when its last line has none. The rule uses no ignore-file semantics, on purpose:
those semantics are a program, not a rule, and the rule must be the same in every runtime.

The **tree digest** is MacroCOSM's, computed exactly as MacroCOSM OES, its section 18.4.1, gives it: over the files
that section's rule reads, in the order of their paths' UTF-8 bytes, the sha256 of each file's relative path, a zero
byte, its sha256 in hexadecimal and a line feed. A binary file is among them only when its only zero bytes lie past
its first 8,192 bytes. It is a fabulac's `source.tree`, and a fabulac is fresh while its folder's tree digest still matches. Everywhere a digest is asked for (`digest repo`, a plan's input
row, a record's inputs and outputs, `made`), a folder's digest is its tree digest.

Its fields, read with a dot, and as bare names in a `where` over the folder:

| field | of a folder | of a member (a text walked from it) |
|---|---|---|
| `path` | the path as given | relative to the folder walked |
| `name` | the last part | the file name |
| `files` | how many files the rule kept | — |
| `bytes` | their total size | — |
| `lines` | total lines of its text files | the file's lines |
| `tree` | the tree digest | — |
| `commit` | the clone's `HEAD` commit, read from its files (no `git` is run, so it says nothing of uncommitted changes), else `nothing` | — |
| `origin` | the clone's `origin` remote, else `nothing` | — |
| `suffix` | — | the part of the name after its last `.`, without the dot (`py`, `md`); `""` for none |
| `depth` | — | how many folders stand above it inside the folder walked (0 at the top) |
| `size` | — | bytes |
| `sha256` | — | the file's |
| `binary` | — | `true` for a file that is not text |

### 20.2 Walking and filtering

`for each t in repo` gives the folder's text files as `text` values, in path order. Binary files are not walked; they
are counted. Each member's provenance is hand-made, with `source: {folder: <tree>, path}`.

`repo where suffix is py` is a **folder**: the same root, only the files whose fields satisfy the condition, and a tree
digest of its own over the files it kept that MacroCOSM's rule reads. The same condition may stand on a loop,
`for each t in repo where suffix is py`. A `where` over a folder reads the member fields of the table above, over
binary files too, so `repo where binary` gives the binary files. `folders of d` gives a `list of folder`: the folders directly below `d` that the rule
keeps, in path order, each with its own fields and tree digest. `count` of a folder counts its text files.

```thym
thym 1

program python-files
  why: the Python files of a folder, one line each with its length in lines.

  takes repo: folder
  gives listing: short

  let rows = for each t in repo where suffix is py
    keep join [t.path, (say t.lines)] with " · "
  end
  give join rows
end
```

### 20.3 A folder as an input

A program takes a folder as `takes repo: folder`, and the person gives its path as the input (`repo=tool/`). A folder
needs no catalog. The plan records the input as `{name, type: folder, path, sha256: <tree digest>, files, bytes}`. At
run time the tree is read again, and a changed digest is the usual refusal (check `input`): "repo changed since it was
planned: tool/ has tree 3f2a…, the plan recorded 91c0…; plan it again".

A text input is a file the person keeps, and a replay needs it present. A folder is usually a working tree that moves
on, so **a run snapshots every folder it takes**: it writes `inputs/<name>.folder.cosm`, a `thym/1` volume of kind
`folder` (section 17.1) that lists every file with its digest and holds the bytes of each text file as a block scalar,
as the single-file package does (section 15.3). The catalog's shape:

```yaml
oes: thym/1
kind: folder
id: thym/2026-11-05-1530-a1b2.repo
name: tool/
path: tool/
tree: 91c0e3…
commit: 4b1f0c2…
origin: https://github.com/someone/tool
files:
  - {path: LICENSE, sha256: …, size: 1071}
  - {path: tool/cli.py, sha256: …, size: 4312}
  - {path: docs/logo.png, sha256: …, size: 20480, binary: true}
texts:
  - path: tool/cli.py
    text: |
      …
nodes: []
```

A replay reads a folder input from this snapshot and never from the disk, so it needs no repository (section 12.4).
A snapshot keeps no binary file's bytes, so a replay of a run whose folder output held a binary file is refused.
The cost is the text of the walked tree, once per run, and one row per binary file: a folder of about sixty files and
six thousand lines takes a few hundred kilobytes per snapshot. Sharing one snapshot across the runs of a job, by its
digest, is reserved for a later edition.

### 20.4 A folder as an output

A move may give a folder (`entail f as code`, section 20.7). A program that `gives code: folder` lands it as
`outputs/code/`, a directory holding exactly the folder's files, written into the run's stage and renamed into place
with every other output in one step: all or none (section 12.1). The trace's output row is `{name: code, sha256: <tree
digest>, path: outputs/code/}`. Where the host copies it next follows the kind of the value: a cshort lands beside its
fabulac as `<name>.cshort-<YYYY-MM-DD-HHMM>/` (MacroCOSM OES, its section 18.4.7). A folder has no catalog of its own,
so its `made` lives in the trace's record and in whatever file the move writes into it (for a cshort, the footer of its
`CSHORT.md`).

### 20.5 The flavour of a decompile

A fabula's flavour is said with `as`, the modifier every program already has: `derive t as prose` gives a fabulan,
`derive t as verse` a fabulap, and `derive t as code` the fabulac's reading of one file. With no `as`, a text derives as
it always has, to a fabulan: `derive t` and `derive t as prose` are the same call. A fabula from `derive <folder>` or
`survey` is a fabulac. `entail f as told` of a fabulan or a fabulap keeps its contract; `as code` and a catem's depths are
refused of either (check `flavour`): "f is a fabulap, a poem's fabula; only a fabulac entails a catem".

```thym
thym 1

program decompile-verse
  why: a poem decompiled into its fabula, line by line, with its metre and its rhymes, and a
       question for its author wherever a reading is a guess.
  must: nothing is fetched; the poem is the person's own copy.

  takes poem: text
  gives f: fabula

  let found = derive poem as verse
  assert found covers poem else "a line of the poem is in no item"
  let asked = question found
  give gather asked with found
end
```

`covers` of a fabulap reads the poem's lines rather than its sentences: every line that is not blank is in the span of
at least one item. That is `coverage` read for verse, defined with the fabulap's kinds (MacroCOSM OES, its section
18.4.6).

### 20.6 Decompiling a folder of code

A fabulac is built in stages, each one atomic run, so that a build that stops can take up again after the last stage
that landed. The stages, and the moves that make them:

| stage | the move | asks | what it gives, and what its contract holds |
|---|---|---|---|
| survey | `survey repo`, rules only | no | a fabulac outline: a `C:file` per file (language, lines, sha256), a `C:component` per module, package and class (a nested class too), a `C:interface` per public function, class, method, constant and command-line entry point, with its name, parameters and decorators from the syntax tree (a property with its setter is one interface, overloads are read on their function, a definition under a module-level `if`, `try` or `with` carries the condition, and a private class a public one inherits from, or a private name another module or a test imports, is an interface not exported), a `C:dependency` per import from outside the tree (an import of a module of the tree, beside the importer or named in `from <package> import <module>`, is that module) and per declared requirement, the types a module's stub (`.pyi`) gives its interfaces, a `C:setting` per environment variable read, per command-line option (its help as a user sees it, or marked a template where no rule can fill it) and per key of the program's own `[tool.<its name>]` table in its `pyproject.toml`, a `C:structure` per data shape (a data class, a named tuple, a typed dictionary, an enumeration, a class with annotated attributes, a type alias), each public documentation string past its first paragraph as a behaviour and each of its doctest examples as a case, the messages of the errors a function raises on its interface's `raises`, what a function prints, logs or exits with as a behaviour, a command's exit statuses on its interface's `gives`, the licence and the means. The repository's own tooling (its documentation's build, its scripts, its examples) is not the program. `files-found`, `code-span`, `licence-recorded` |
| history | `history repo with f`, rules only | no | the fabula so far, with the clone's history: changes grouped into episodes (the commits between two tags, split again where two commits stand more than fourteen days apart; where that gives more than twenty episodes, the commits between two tags alone; where that still does, one episode per year), a release for every tag with its date, placed by its commit, else by the newest commit whose subject names its version as a release, else unplaced, a maker per author: by name only where the repository states it (its licence's copyright holder, a line of an authors file, or an author or maintainer its packaging file names), otherwise as a numbered contributor, never by address. An implementation may bound the log it reads and keep only the newest changes as items, counting the rest in their episode and release (enough reads at most four hundred commits and keeps forty); a history that does not reach the first commit ends in a phase that says so. `history-grounded` |
| read | `derive t as code with f`, once per file, in a loop that collects | yes | that file's behaviours, structures, cases, terms, claims and events, read against the outline. `code-span`, `outline-cited`, `coverage` (every interface the outline lists for the file is the subject of a behaviour or has a structure of its name, and every component is the subject of a behaviour or has its `does`), `terms-grounded`, `stance-closed`. A test file's reading takes cases and structures only, and a file the outline gives no interface or component a structure that says what it is; a file longer than one request is read in parts, each covering the interfaces whose lines it holds, the first also the components, and a part a check's verdict is about is the only one asked again. Its scaffold gives the outline's own items for the file, marked pending |
| (join) | `gather readings with f` | no | the fabula so far with every reading in it, each reading's additions to the outline merged into the outline's own items. `nothing-lost`, `ids-unique` |
| fold | `derive repo with f` | yes | read as a whole: aims, audience, uses, requirements, decisions, exclusions, inspiration, and the atem. `fold-grounded`, `atem-shape`, `licence-recorded`. It has no scaffold: nothing but a model reads intent. A `derive` of a folder without `with` is refused: "derive of a folder folds what the stages found: derive repo with f" |
| question | `question f`, landed with `gather` | yes | the dialectic's questions where the build was unsure (section 22) |

Every stage's contract ends with `fabula-checks` and `provenance`, and the last program `keeps fabula-checks`. A
reading is `derive` because a file read as code is a text decompiled, and the fold is `derive` because a folder
decompiled with what is known of it is a decompile too; `read` keeps its meaning (section 14). `gather` takes a list
of fabulas or of items and gives the `with` volume with every one of them in it. An item whose id the volume already
has may add the fields the volume's item lacks, and add inside a field (a parameter's `means`, an error's `when`); a
field both say must agree, and a field a rules stage reads is never changed; a clash is refused, naming the item and
the field.

A file's reading holds only what it adds for its file: its own items, and what it adds to the outline's items of that
file (MacroCOSM OES, its section 18.4.7). Its `fabula-checks` runs on the reading together with the fabula it was read
with, and `its-own-file`, `code-span` and `outline-cited` on the reading's own items.

```thym
thym 1

-- The fabulac of a small Python repository, built in five runs. A host runs the programs of this file
-- in the order they are written, as one job: each lands the fabulac so far beside the folder, and a
-- job that stops takes up again after the last one that landed.

contract its-own-file(r: fabula, t: text)
  why: a file's reading speaks of that file and of no other.

  assert count r > 0 else "the reading found nothing in the file"
  for each i in r where i has span
    assert i.span.file is t.path else "an item points into another file"
  end
end

program survey-the-repo
  why: a repository's files, parts and interfaces are found from its syntax alone, before any
       model reads a line.
  must: nothing in the repository is run, imported or installed.
  decided 2026-11-05: this build reads pure Python a person could read in an afternoon: sixty
       files, six thousand lines.

  takes repo: folder
  gives f: fabula

  let code = repo where suffix is py
  assert count code > 0 else "there is no Python file here"
  assert count code < 61 else "more than sixty Python files: past what this build reads"
  assert code.lines < 6001 else "more than six thousand lines of Python: past what this build reads"
  give survey repo                                 -- files, parts, interfaces, licence: rules only
end

program read-the-history
  why: the clone's log and its tags say how the code came to be.
  decided 2026-11-05: history is the clone; issues and pull requests are reserved.

  takes repo: folder, f: fabula
  gives g: fabula

  give history repo with f                         -- changes in episodes, releases from tags: rules only
end

program read-every-file
  why: each Python file is read once by a model, against the outline, for what it does and how.

  takes repo: folder, f: fabula
  gives g: fabula

  move read-file(t: text, so-far: fabula): fabula
    keeps its-own-file against t
    give derive t as code with so-far              -- behaviours, structures, cases, terms, claims, events
  end

  let readings = for each t in repo where suffix is py
    keep read-file t, f
  end
  give gather readings with f
end

program fold-the-whole
  why: read as a whole, the code says what it is for, for whom, and what it will not do.

  takes repo: folder, f: fabula
  gives g: fabula

  give derive repo with f                          -- aims, uses, requirements, decisions, exclusions, the atem
end

program raise-the-questions
  why: where the build was unsure it asks the person who knows, and the questions land with the
       fabulac.
  decided 2026-11-05: the answers come back in a second run, settle; nothing waits inside a run.

  takes f: fabula
  gives g: fabula
  keeps fabula-checks

  let asked = question f
  give gather asked with f
end
```

**A file of several programs.** Thym's grammar describes each program of such a file and what it takes and gives; it
does not run them in sequence. Running a file whose programs each give one fabula as one build, in order, filling each
`fabula` input with the fabula the run before landed and taking up again after the last that landed, is the host's job,
specified with the fabulac (MacroCOSM OES, its section 18.4.7). A fabula built in several runs records every one of
them: its catalog's `derived` describes the last run that derived it, and `derived.runs` holds one entry per run that
wrote into the volume, a settle run included, with its program's name, its run, its model and its route (MacroCOSM
OES, its section 18.4.1). Under `--rules` a host runs survey and history and stops: the outline (MacroCOSM OES, its
section 18.4.7).

### 20.7 Compiling a fabulac

**`entail f as code`** gives a folder, the **cshort**: source code rebuilt from the fabulac, file by file, one model
request per file it rebuilds: every `C:file` in a programming language that is not a test, and the README (MacroCOSM
OES, its section 18.4.7). Each request carries the file's items: its components, its interfaces with their parameters,
the behaviours and cases about them (and the cases of an interface whose behaviours name this file's module or a private
helper of it: the file that does its work), the settings and dependencies it touches and the open questions about them;
and what it reaches in the other files: the interfaces of the modules it uses and of those its items name, with the
lines of the behaviours about each it names. The README is asked for in the format its name says. The move assembles the
files and writes `CSHORT.md`: the cshort's footer line first (MacroCOSM OES, its section 18.4.7), then the file list
with digests (the packaging file rules wrote among them, or why none was written), then the source's licence line. Its
contract is checked without executing anything: `parses`, `interfaces-present`, `files-present`, `footer` (`CSHORT.md`'s
first line is the footer, naming the fabulac's file, the language, the UTC day of the run and the model; its last line
is the licence line, equal to `source.licence`) and `provenance`. A failed check asks again only for the files it names,
within the node's attempts. `entail … as code` has no scaffold, so `--rules` refuses it at plan time.

**`entail f as line`, `as overview` and `as manual`** give a short, the **catem** at that depth. `line` is the atem's
line, the same as `atem f`'s; `overview` names every use; `manual` names every use and every interface a person
reaches (the command-line entry points and the public interface), with what they do. The contract is `coverage`
(every sentence traces to behaviours, uses or events), `no-invention`, `uses-told`, `footer` (the catem's footer names
its depth) and `provenance`, and the scaffold `uses-outline` lists the uses and interfaces in told order, in their own
words. The host saves a catem as `<name>.catem-<YYYY-MM-DD-HHMM>.md` beside the fabulac.

```thym
thym 1

program compile-python
  why: a fabulac compiled back into Python, file by file, with the manual of everything a person can do
       with the program.
  must: nothing it entails is run, imported or installed.
  decided 2026-11-05: a cshort is read in enough and never run there; the rebuild test runs outside.

  takes f: fabula
  gives code: folder, manual: short

  give code: entail f as code                      -- one file at a time; it parses, and every interface is there
  give manual: entail f as manual                  -- the catem at its deepest
end
```

### 20.8 What is never run

Nothing a program reads or makes from code is executed by Thym. `survey` reads syntax trees; `history` reads the
clone's log and tags through the host's engine, which answers only each commit's id, date, author's name, subject and
paths, and each tag's name, commit and date; `parses` and `interfaces-present` ask the host's syntax engine, whose
answer per file is recorded as an engine call (section 12.4), so a replay, and a runtime in another language, needs no
parser. Parsing is not running: nothing is imported, compiled into files on disk, or run. A cshort is viewed, never
run; whether it behaves as its source did is a test that runs outside Thym, in a sandbox of its own.

---

## 21. Editing

<!-- atem: edits as values: lines, changes, and one edit that applies them -->

In `thym 1`, edits are values. A program reads a text or a short as numbered lines, makes **changes**, each naming the
line it is about by number and digest, and then applies all its changes at once with one deterministic move, `edit`,
under a contract that no other line moved. A model is asked only for the wording of a replacement, inside a move that
asks (`reword`), and under that move's contract.

### 21.1 Lines and changes

A **line** is one line of a text or a short: the line's bytes without its line break, its `number` (from 1, in its
source), and the sha256 of its source and of itself. Its fields are `number`; `level` (the heading level, 1 to 6, of a
heading written with `#` marks, 0 otherwise); `title` (a heading's words without its `#` marks and without a leading section number such
as `3.` or `3.2`, `nothing` for other lines); and `blank` (a bool). A line fits wherever a string is taken.

A **change** is one edit: `{at: <line number>, was: <sha256 of that line>, of: <sha256 of the source>, do: replace |
drop | insert-before | insert-after, lines: [<new lines>]}`. It is plain data, and a program makes one only with the
moves below.

### 21.2 The moves

| move | reads aloud | gives |
|---|---|---|
| `lines of s` | "the lines of s" | every line of the text or short, blank ones included, numbered |
| `replace l with v` | "replace l with v" | a change: l's line becomes v (a string, a line, or a short of several lines) |
| `drop l` | "drop l" | a change: l's line goes |
| `insert v before l`, `insert v after l` | "insert v before l" | a change: v's lines go before or after l's; `insert` takes exactly one of `before` and `after` |
| `edit s with changes` | "edit s with the changes" | s with every change applied, of the same type as s |
| `reword l to 30 words` | "reword l to thirty words" | asks: l said again in at most N words, of the same type as l |
| `join xs`, `join xs with "…"` | "join the rows" | a short: the members one per line, or joined by the string |
| `say n` | "say n" | a string of a number, a date, a word or a bool |

The loops that build a list of changes are loops that collect (section 8.1), and `edit` is one deterministic node. A
text edited is a new value: it lands in the run's outputs and goes where the person names, never over its source
(`never-source` holds on `edit`, as on a reading).

### 21.3 Only the changed

`edit`'s contract, `only-the-changed`, holds when:

1. every change names its source: its `of` is the digest of the value being edited ("a change names line 3 of another
   text");
2. every change's line exists there with that digest ("line 12 changed since it was read");
3. no two `replace` or `drop` changes name one line, and inserts at one place keep their written order ("line 7 is
   replaced twice");
4. the output is the input with exactly those changes: every input line no change names appears byte for byte and in
   order, and the output holds no line that neither the input nor a change gave.

The first three check the program's changes, and the fourth checks the implementation. All four are deterministic.

### 21.4 `reword`

`reword` is the one editing move that asks. Its contract is `length` (at most N words, and at least 80 per hundred of
N), `one-line` (a `line` gives one line; an answer of several lines is repaired by joining them with a space, then
checked again), `nothing-added` (a narrow `no-invention` that needs no fabula: every name, number and word outside
FEED in the output is in the input) and `provenance`. A move that rewords may keep a contract of its own as well
(section 7.5), and is asked again until it holds or its attempts run out.

### 21.5 Two programs

`tighten` is the editing program people copy. It says every line of a short that runs past thirty words again in thirty
or fewer, and moves no other line:

```thym
thym 1

contract shorter(new: line, old: line)
  why: a reworded line says less in fewer words, never more.

  assert words new < words old else "the reworded line is not shorter than the line it replaces"
end

program tighten
  why: every line of a short that runs past thirty words is said again in thirty or fewer, and no
       other line moves.

  takes s: short
  gives t: short

  move tightened(l: line): line
    keeps shorter against l
    give reword l to 30 words
  end

  let changes = for each l in lines of s where words l > 30
    keep replace l with tightened l
  end
  give edit s with changes
end
```

Read aloud: contract shorter, a reworded line says less in fewer words. Program tighten takes s, a short, and gives t.
Move tightened, of a line, keeps shorter against the line, and gives the line reworded to thirty words. Let changes be:
for each line of s with more than thirty words, keep a replacement of the line with the tightened line. Give s, edited
with the changes. The `where words l > 30` belongs to the loop, since `lines` declares no `where` (section 4.5).

A deterministic editor, which asks nothing:

```thym
thym 1

program drop-the-todos
  why: every line that still says TODO leaves the draft, and nothing else changes.

  takes draft: text
  gives clean: text

  let changes = for each l in lines of draft where "TODO" in l
    keep drop l
  end
  give edit draft with changes
end
```

---

## 22. The dialectic in a program

<!-- atem: questions land in one run; answers settle in another -->

The dialectic is MacroCOSM's one way of asking a person what a source means and recording what they say (MacroCOSM
OES, its section 18.6): any volume may carry its questions and sessions. In a program it is three moves of `thym/1`,
`question`, `record` and `settle`, in **two atomic runs with a person between them**. The first run lands questions
with the volume. The person answers them, in a page or through an agent. The second run records the answers and
settles them into the items they are about. No run waits on a person, so "nothing partial" and replay hold as they
always have, and a replay of either run needs neither the person nor the model.

### 22.1 `question`

`question v` takes a fabula or a volume and gives a list of question items. It asks the model, with the scaffold
`bank`. Its rules part always runs first: it gives the opening questions of the manifest's bank for the volume's
flavour or format, a question for every `{pending: …}` field, and one for every item marked unsure (a confidence below
0.5, or pending) that holds no pending of its own (MacroCOSM OES, its section 18.6.5).
When the run asks the model, the model adds questions where the volume is unsure, ambiguous, in conflict or silent on
intent, and only there. It reads only the items a person can say something about: of a fabulac its aims, uses,
requirements, decisions, exclusions, behaviours, interfaces, structures and claims; of any other volume every item but
its files, changes, releases, test cases and dependencies as such; and in every flavour any item marked unsure or
pending. Under `--rules` the bank part alone runs. Each question says who raised it and is `open`. Its
contract is `addressed`, `no-duplicate` and `provenance`. `question` gives a list, and a program lands the questions with
the volume through `gather asked with f`.

### 22.2 `record` and the answers volume

A person's answers reach a program as an **answers volume**, which the page or an agent writes beside the volume it
answers, `<the twin's name without .cosm>.answers-<YYYY-MM-DD-HHMM>.cosm`, the stamp in UTC. It is a delta: the
session's record, and for each question answered, only its id, its new state and its new answers. Its catalog declares
the format of the volume it answers (`fabula/1` for a twin read under `emf/1`: an old spelling is never written),
carries that volume's `id`, and its `macrocosm:` when that volume has one; its `nodes:` hold exactly one `D:session`
item and, for each question answered, unknown or declined, a mapping of the question's `id`, its new `state` and its
new `answers`, each naming the session. An address asked without a question item (a format that asks from a bank
without writing question items, as Comprise OES does, or a bank asked directly) is an entry `{about, answers}`: the
address, `<item id>#<field path>`, and its new answers. A skipped question shows only in the session's `skipped`. It is
read only as a delta, never checked as a volume of that format on its own. To Thym it is a `volume`. A sitting written
and not yet recorded is read with the volume when its questions are listed: a question it answers is not put again, and
a second sitting may not answer it.

`record said in f` is code: it appends each answer to its question's answers (never rewriting one), sets the question's
state to `answered`, `unknown` or `declined`, and adds the session. It refuses an answers volume whose session the
volume already holds, so a set of answers is recorded once, and it checks every entry before it writes any. Its contract
is `addressed`, `only-the-asked` and `provenance`.

### 22.3 `settle`

`settle f` takes a fabula or a volume and gives the same, with every answered question folded into the item it is about.
It asks the model only where an answer means an item must be read again (a value about a whole item or a span of the
source, a value that would replace a structure, a yes-no answer about a field that is not `true` or `false`; MacroCOSM
OES, its section 18.6.4). Every other answer (a field filled from a text, a choice, a yes-no, a number, a date or a
reference) is written by rules, and a call that needs no reading asks nothing. An answer that the person does not know
(`unknown`) leaves the field `{pending: "<the person's own words>"}`, and a refusal to say lists the field in the item's
`withheld` and writes `provenance.state: not-disclosed`. Its scaffold, `direct`, runs the rules part only and leaves the
answers that must be read again answered and unsettled, for a run with a model. Its contract is `addressed`;
`only-the-asked` (the fields that change are exactly those the answered questions are about, with their provenance and
the questions' `settled` field); `fabula-checks`; and `provenance`: every field written carries `provenance: {mode:
dialectic, sources: [D:session/<id>], confidence}`. In a fabula the settle run joins `derived.runs`, and `derived`'s
single keys stay those of the run that derived it. A volume that is not a fabula, which the program of section 22.4 does
not take, a host settles by the same moves' rules: it records the answers, then settles them with no reading.

### 22.4 The two runs, read as a pair

The first run decompiles and lands the questions:

```thym
thym 1

program decompile-prose
  why: an essay decompiled into its fabula, with a question for its author wherever the reading
       was unsure.
  decided 2026-11-05: the questions land with the fabula; the answers come back in a second run.

  takes essay: text
  gives f: fabula

  let found = derive essay as prose
  assert found covers essay else "the fabula does not cover the essay"
  let asked = question found
  give gather asked with found
end
```

The person answers. The second run takes the fabula and the answers volume, and lands the settled fabula:

```thym
thym 1

program settle-the-answers
  why: what a person said is written into the fabula, each answer where its question pointed, and
       nothing else in it moves.
  decided 2026-11-05: a second run, never a run that waits; "I don't know" leaves the field open
       in the person's own words.

  takes f: fabula, said: volume
  gives g: fabula
  keeps only-the-asked against f

  let answered = record said in f
  give settle answered
end
```

---

## 23. Models in a run

<!-- atem: one program, one contract, a local or a cloud model -->

A model-backed step runs on the model chosen for its run, and the program does not change with the choice. The same
program, plan nodes, contracts, repairs, attempts and output budgets hold on every route; the route changes only the
model's id, the provider, the window (and so the verdict of preflight) and the cost. There is no tier of checks per
route: a local model at best effort fails more often, and is refused honestly; it is never let through.

### 23.1 The route

The **route** is chosen per run, and nowhere else: `local` (the default: the host's local model) or `cloud` (a cloud
model through a broker, the host's named one or one the person names by the provider's id). A run, or any job a host
starts that asks a model, that names no route runs on the local route, whatever model the host's other work uses; with
no local model running it runs by rules where it has a rules form, or refuses in words, and never falls back to the
cloud. On the command line it is `--model local`, `--model cloud` or `--model cloud:<id>` (section 11.3). A plan that
asks a model on a cloud route whose gate is closed is refused at plan time, check `cloud`, in the gate's own words: "the
cloud is not open for this run: 'local models only' is on in the broker". A plan that asks nothing runs on either route
and reaches no model. Nothing reaches a cloud model that the person did not choose for that run.

### 23.2 What the plan shows

A plan with a node that asks carries the catalog key `models` before anything runs:

```yaml
models: {route: cloud, provider: broker-name, model: vendor/large-model, calls: 61, at_most: 183, calls_open: [], window: 200000}
```

`calls` is the number of model requests the plan makes when every check passes the first time: a plain node that asks
counts one, and a node with calls in a loop counts its asking calls times its `members.at_most`. `at_most` is `calls`
times each node's attempts. `calls_open` lists the nodes whose count cannot be known at plan time: a recursive move
that asks, a loop over a collection of unknown size. A command line prints it under the plan's atem:
`61 model calls, at most 183, on the cloud (broker-name: vendor/large-model)`; on the local route,
`3 model calls, at most 9, on this machine (g40-04)`; with an open count it adds `; and more that cannot be counted
before it runs`, naming the steps. The plan's root summary is the same in both versions. A
plan compared by the conformance suite is compared without `models`, since the route is the run's choice, not the
program's.

### 23.3 What a run records

- `made` gains `route` and `provider` (section 5.3), and `engine` stays `model:<id>`, the model's own id.
- A candidate gains `route` and `provider` (section 12.2). A candidate recorded without them replays without them, so
  an older recorded run replays to the same bytes.
- The trace's environment holds the id of the model, as the route names it before the first request, the route, the
  provider, and the window of that model (section 12.3); where a provider answers with a more exact id of its own, that
  id is in `engine` and `made`.
- A fabula a program builds records which model made it, in its catalog's `derived`: `model`, `route`, `provider`,
  `program` (the program's name) and `run` for the last run that derived it, and one entry in `derived.runs` per run
  that wrote into it, a settle run included (section 20.6).

### 23.4 Budgets

Preflight (section 12.5) is unchanged in its rule, and reads the window of the route's model. `--calls N` sets a
ceiling on a run's model requests: the runtime counts every request, re-asks included, and the request past N refuses
the run, check `calls`: "`keep read-file t, f` (line 55, for t = `tool/cli.py`): this run reached its ceiling of 120 model
calls; nothing landed". A cloud plan whose `calls_open` is not empty is refused at plan time without `--calls` (check
`calls`): "this plan may ask the cloud model a number of times nobody can know before it runs (tree-of calls itself and
asks); give a ceiling with --calls". A local run needs no ceiling: it costs time, not money.

### 23.5 Agent-free

Agent-free refuses every model, local or cloud, at plan time (section 19). With `--rules`, the scaffolds run, on no
route at all.

---

## 24. Conformance

<!-- atem: what compilers and runtimes must do, and the suite that shows it -->

### 24.1 A compiler must

1. Read the grammar of section 4.8 for the version its line names, exactly, and refuse a version line it does not
   know. Compile a `thym 0` program against the `thym 0` view of every declaration, to the items and the plan it has
   always had, and refuse `thym 1` syntax under a `thym 0` line as "this needs `thym 1`" (section 4.9).
2. Resolve moves from every manifest's `moves:` block and every `*.moves.cosm` sidecar in the registry's folders, and
   refuse an unknown move with the nearest name.
3. Type every expression by section 5, refuse every type error with its line, and work out provenance.
4. Refuse the static contract failures of section 7.1 and the other compile errors of section 9, each with its check.
5. Enumerate into `thym/1` items that `compile` back byte for byte (section 10), and plan into an acyclic graph of
   nodes by section 11.1.
6. Return refusals as values with `stage`, `line`, `check` and `message`.

### 24.2 A runtime must

1. Refuse a plan at plan time when the environment cannot run it (section 9), with the count or the size.
2. Walk the plan in a topological order; run deterministic moves by their reference semantics; send model-backed moves
   to a coprocessor under their contracts; check every output against its contract before it becomes a value.
3. Land every output or none, several outputs and folder outputs included; write the trace with every record; name
   the run, and for a model-backed value the route, in every output's `made`.
4. Snapshot every folder a run takes, and replay a recorded run to byte-identical outputs with the replay
   coprocessor, reading folder inputs from their snapshots.
5. Refuse in the person's words (section 9), keep the run's ceiling of model calls, and refuse every model, local or
   cloud, when agent-free.
6. Keep the six laws.

### 24.3 The suite

The suite is a folder, portable together with MacroCOSM's own corpus, which holds the sample Holotype that `open-house`
runs on; the reference implementation carries both (https://github.com/0gsd/enough):

```text
README.md                       the layout, the inputs of each program, and what passing means
programs/<name>.thym            the programs: the three of this document first
inputs/                         the texts, twins, package, morph and context the programs run on
expected/<name>/items.cosm      the enumeration; compiles back to programs/<name>.thym byte for byte
expected/<name>/plan.cosm       the plan, compared without run ids, timestamps and prompt token counts
expected/<name>/outputs/        the outputs of deterministic runs, byte for byte
replay/<name>/<run-id>/         a recorded run: plan, trace, candidates; re-runs to the recorded outputs
bad/<slug>.thym                 programs that must be refused; the first line reads -- refused: <stage> <check> line <n>
```

A compiler conforms when every program in `programs/` compiles, enumerates to its `expected/<name>/items.cosm`, compiles
back byte for byte and plans to its `expected/<name>/plan.cosm`, and when every `bad/` program is refused at the stage,
check and line its first line names. A runtime conforms when every deterministic program's outputs match (run with
the clock pinned to 2026-11-01T12:00:00Z, so an epoch in a recorded output stays comparable)
`expected/<name>/outputs/` and every `replay/` run re-runs to its recorded outputs. A deterministic program whose
outputs carry its run's id (every item's `made`, a fabula's `derived.run`) cannot be frozen so: it is run as its latest
recording under `replay/<name>/`, with that run's id and clock, and its outputs are compared with the recording's byte
for byte. The three programs of this document
(sections 4.1, 16.2 and 18) are the suite's first three, byte for byte, and the suite's test compiles every block marked
`thym` here.

The suite reads each file by its own version line. Its `thym 0` files are those of edition 0.5.4, unchanged, but for
one: `bad/version.thym` names `thym 2`, since `thym 1` is a grammar. Beside them it holds `thym 1` programs with their
expected items, plans and outputs (among them `python-files` and `folder-outline` over a small folder of code with a
binary file, `aims-in-brief`, `drop-the-todos` and a deterministic contract block); a `thym 0` program whose loop
folds a nested call into one node; `bad/` files for every refusal sections 4.9, 7.5, 8 and 21 add, each read by the
version its own line names; and recorded runs of `tighten`, with one re-ask a kept contract forced, and of
`decompile-prose`.

### 24.4 Where an implementation and this text disagree

Where an implementation and this text disagree, one of them is in error: either the implementation does not conform, or
the text is corrected in a later edition. The Changes appendix (section 25) records which was corrected, with the
section it touched.

---

## 25. Changes

<!-- atem: what each edition changed, newest first -->

**Edition 0.6.0 · 2026-11-06.** The language gains a second grammar, and the text follows MacroCOSM's new taxonomy.

1. **`thym 1`, the second grammar, is a superset of `thym 0`'s syntax** (section 4.9). A `thym 0` program compiles and
   runs unchanged, against the `thym 0` view of every declaration; new syntax, or a move only `thym 1` sees, under a
   `thym 0` line is refused with "this needs `thym 1`". This edition's moves carry `since: 1`. A `thym 0` program may not
   `use` a `thym 1` file. Relabelling a `thym 0` program as `thym 1` can change the order of the items a loop of several
   statements emits.
2. **Corrected in both versions:** a call nested inside a statement of a loop's body is part of that statement's node
   and is evaluated with each member (section 11.1). Two kinds of program that compiled clean under edition 0.5.4 and
   ran wrong run right in this edition. Under `thym 1` a loop over a collection known only at run time is one node;
   under `thym 0` the three such loops that would still run wrong are refused at run, with the fix (section 8.1).
3. **`folder` is a type** (section 20), read under one fixed rule, with MacroCOSM's tree digest. A run snapshots every folder it
   takes, so a replay needs no repository.
4. **A loop collects** with `let … = for each … keep … end` (section 8.1).
5. **A program may define a check as a `contract` block**, and a move or a program `keeps` it (section 7.5). A failed
   kept contract asks the model again within the node's attempts. Its items are `P:check`.
6. **A user move may call itself** under a declared `depth:` (section 8.3); recursion is no longer reserved.
7. **Edits are values** (section 21): lines and changes, applied at once by `edit` under `only-the-changed`.
8. **A program may give several outputs**, each named on its `give` (section 8.2). All land or none.
9. **The dialectic is two atomic runs** (section 22): `question` lands questions, and `record` and `settle` land the
   answers. No run waits on a person.
10. **A model-backed step runs on the route chosen for its run** (section 23). `made`, the candidate and the trace say
    which route, provider and model; a plan says how many model calls it will make; `--model` and `--calls` choose and
    bound them; agent-free refuses a cloud model as it refuses a local one (section 19). The contract is one.
11. **Refusals name the statement as written and the person's names** (section 9), never a node or a temporary.
12. **`emf-checks` is `fabula-checks`.** The old name is read wherever it is written, and a `thym 0` program's
    enumeration keeps it. The moves `derive`, `tell`, `atem` and `expand` are declared by `fabula/1`, which replaces
    `emf/1`; `derive` and `tell` gain the flavours (`as prose`, `as verse`, `as code`, a catem's depths), and `survey`,
    `history`, `gather`, `question`, `record`, `settle`, the editing moves, `join`, `say` and `folders` are new, and
    so is Ascribe's `propose` (section 6.3). `in` takes a text on its right, a call needs no parentheses in a condition, a bare path names the
    one input of a program that takes one, and a list input is given member by member (sections 4.5, 11.3 and 12.1).
13. **Sections 20 to 23 are new.** Conformance, Changes and Withdrawn, sections 20, 21 and 22 of edition 0.5.4, are
    sections 24, 25 and 26, and the entry below names them by their numbers in this edition.
14. **The taxonomy.** Thym is the transcognition language that connects OESes; `thym/1` is a built-in of MacroCOSM's
    core, specified here, and is no longer called a MiniCOSM (section 17); the built-ins and the MiniCOSMs declare moves
    (sections 3 and 6.2). The name EMF is retired: a text's fabula, its twin, is a `fabula/1` volume, and `oes: emf/1`
    reads as a fabulan.
15. **Section 13.3 states one nine-letter rule**: a word with no band is rare at nine letters or more, and common at
    eight or fewer.
16. **A `give` inside a loop stays the check `type`**, and section 8.1 says so.
17. **Section 15.1 names the three forms of a package**, and a package carries its fabula under the name its twin
    had, which `unpack` keeps; a package made before this edition keeps `fabula.cosm`. `graph.cosm` is an isograph made
    for one text (sections 5.1 and 15.1). Section 15.3 is the rule for what `package` lands: the
    single-file form, with the folder form beside it, and the encrypted form only when sealing is asked for. A reader
    of a sealed package refuses a file over its size cap, YAML anchors and aliases in the clear part, and a list of
    chunks that opens past its bounds.
18. **A `use`d path stays inside the program's folder** (section 8.4).
19. **Section 1.3 says who stewards the specification**, in the sentence all five texts share.
20. **`project` takes `as isograph`**, Ascribe's kind, beside Comprise OES's `isotype` and `paratype`: each MiniCOSM
    declares the kinds it projects, in a `moves:` entry that `extends` the move (sections 4.5, 6.2, 6.3, 17.6 and 18).
21. **The grammar's `call` may have no operand**, as `fabula of p` and every accessor have always been written
    (section 4.8).
22. **A `moves:` entry may choose by its call** (sections 6.4 and 17.6): `gives-when`, `contract-when` and
    `scaffold-when` choose what a call gives, the contract it keeps and its scaffold by its `as` word or its first
    operand's type, and a rule that says `scaffold: none` makes a rules run refuse the call when the run is planned. A
    run's snapshot of a folder it took is a `thym/1` volume of kind `folder` (section 17.1). A move that asks more than
    once may name under `repair.failed` what it could not take, and a request asked again says why (section 12.2).

**Edition 0.5.4 · 2026-11-03.** The canonical edition at cosmoes.org (https://thym.cosmoes.org/).

- The name carries no number: Thym, not Thym 0. The edition is a field of the status line; a program's version line,
  `thym 0`, is unchanged and names the same grammar.
- The reference implementation is named (enough, https://github.com/0gsd/enough) rather than located by path;
  cross-references to MacroCOSM OES, Ascribe and Comprise OES are their cosmoes.org homes.
- Section 24.4 states the rule of disagreement: where an implementation and this text disagree, one of them is in error,
  and this appendix records which was corrected.
- The section of open questions and the roadmap is withdrawn (section 26). The gaps it listed are stated where they fall: recursion in user
  moves (section 8.3), the thresholds and the word lists of measurement (section 13.3), the Comprise side of projection
  (section 18); its settled items are recorded under version 0 below.
- The section of decisions in this version is this appendix.
- Section 1.3 states how the specification is kept and revised; section 11.2 describes the reference implementation's
  package without its file list; the third column of the check table (section 7.3) names where each check comes from by
  product rather than by module.
- The grammar, the types, the standard moves, the checks, the six laws, the `thym/1` MiniCOSM and every example are
  unchanged.

**Version 0 · 2026-11-01.** The first version of the language, whose grammar the version line `thym 0` names. The
reference compiler and runtime passed the conformance suite the same day, with a real-model run that replays. Two
readings of the text were corrected on the way and folded into their sections: `stance-kept` reads a claim across every
sentence that cites it (section 7.3), and the null telling's `register` exempts its fabula's own words (section 13.3).
The decisions of the version:

1. **Thym is a full procedural language folded into MacroCOSM.** The OES gains a verb; `thym/1` holds programs, morphs,
   contexts, plans, traces and packages; every MiniCOSM may declare moves.
2. **Its own text syntax, English-leaning, every keyword a FEED headword or a form of one.** Programs read aloud, and moves, not syntax,
   are how the language grows.
3. **Values are typed by density and carry provenance** in `made`; a value without it is hand-made.
4. **MiniCOSMs declare moves**, in a `moves:` block or a sidecar; the compiler hard-codes none.
5. **Deterministic unless marked `asks`.** The model is a coprocessor behind a contract, and replay by recorded
   candidates is the guarantee of reproducibility.
6. **Six laws:** coverage, grounding, monotone stance (on a fixed ladder), round trip, withhold-never-falsify,
   provenance.
7. **Plan, then interpret.** Nothing runs before the whole program is checked and planned, and a plan is a volume a
   person can read and refuse.
8. **Nothing partial**, at compile time or at run time.
9. **Programs are documents**, with `why`, `must` and `decided`, enumerated like a manual; the file is the source of
   truth.
10. **The null morph is the reference telling**, and a morph is a measured departure from it on ten scales; `formality`
    alone carries a direction, and `analytical-depth` is carried from the fabula.
11. **Readings are local, labelled and never the source.**
12. **A package is self-contained**: a folder, a single file, or encrypted with a key that never leaves the owner.
13. **Context is of two kinds**: surrounding (read-only) and occasional (an item, thrown away after use).
14. **The outsider's guess is a paratype.** Crypto- means encrypted everywhere; there is no outsider's graph of a
    person, ever.
15. **The dial is a projection program**, and the target schema's rules are the contract of `project`.
16. **Transcode, transcognize and transconceptualize** are the verbs: the mechanical move, the minded move under a
    contract, and the minded move that changes the frame; *transpile* is retired.
17. **Python reference, JavaScript-portable**; the conformance suite is a folder of `.thym` and `.cosm` files.
18. **The version line pins the grammar**: `thym 0`.

Settled the same day: the reading footer's wording (section 14); the encrypted package uses Comprise's bundle cipher,
`comprise-bundle/0`, and the key never leaves the owner (section 15.3); the holograph's modules are Ascribe's, under its
own manifest (https://ascribe.cosmoes.org/); the stance ladder as section 7.2 writes it; in enough, the `thym_run` and
`thym_check` tools sit behind its `macrocosm-oes` skill. On 2026-11-02 the reference implementation took the
`cryptography` package for AES-256-GCM, so that a package sealed in enough opens in Comprise, with the HMAC-SHA256 AEAD
where AES-256-GCM is absent (section 15.3).

---

## 26. Withdrawn

<!-- atem: withdrawn sections; what survives of them is in Changes -->

The open questions and roadmap, numbered section 22 before edition 0.5.4, were withdrawn in edition 0.5.4; their
content, where it survives, is in the Changes appendix (section 25). From this edition, the number 22 names the dialectic
in a program.

---

## Colophon

<!-- atem: copyright, the canonical edition and its source -->
Thym — Copyright © 2026 Graham Smith. The text is licensed under the Creative Commons Attribution 4.0 International licence (CC BY 4.0, https://creativecommons.org/licenses/by/4.0/). A copy carries the author, Graham Smith; the text's name and edition; and a link to its home, https://thym.cosmoes.org/. For Thym, the author makes the Open Web Foundation Final Specification Agreement 1.0 (OWFa 1.0) promise (https://www.openwebfoundation.org/the-agreements/the-owf-1-0-agreements-granted-claims/owfa-1-0). The names of the family are not licensed by either; the author holds them for now. The canonical edition is published at https://thym.cosmoes.org/; its source and history are at https://github.com/0gsd/cosmoes-site.
