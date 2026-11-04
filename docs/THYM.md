# Thym 0: the MacroCOSM language, its compiler and its runtime

Version 0 of the language, written 2026-11-01 for enough 0.5.0. It was a draft until checkpoint A of the 0.5.0 round,
when the reference compiler and runtime first passed the conformance suite on a real model (2026-11-01, the night
of the same day). From then on it is the specification, and `enough/thym/` is its reference implementation. Where the two disagree, the reference wins and this
text is corrected (section 20.4), as `docs/MACROCOSM_OES.md` promises for its reader.

The design behind this document, with the owner's rulings, is `docs/thym-architecture.md` (local). Thym is folded into
the MacroCOSM specification, `docs/MACROCOSM_OES.md`, and its words (item, kind, volume, catalog, module, check, lens,
atem) keep their meaning here.

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
17. The `thym/1` MiniCOSM and the `moves:` block
18. Projections: the dial as a program
19. Agent-free
20. Conformance
21. Decisions in this version
22. Open questions and roadmap

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

**The words of a text.** A text's meaning has MacroCOSM's three densities: the **fabula** (the EMF twin: order-free
material with stances and spans), the **short** (a telling) and the **atem** (one line, with focus, push and pull).
The author's text is a telling too, and is never called a short. Thym counts the text as a density as well, so a text
has four (section 5.2). Thym adds three nouns and three verbs:

- a **reading** is a telling of someone else's fabula in your morph, local and labelled (section 14);
- the **null morph** is the plainest telling that conforms, Thym's reference (section 13);
- a **package** is the self-contained export of a text with its fabula, morph, context and released graph (section 15);
- to **transcode** is to move a value mechanically: a deterministic move, the same answer every time (`enumerate`,
  `compile`, `cut`, `project`, `band`);
- to **transcognize** is to re-represent a value by choices a mind makes: a move that asks the model, behind a
  contract (`derive`, `tell`, `atem`, `expand`, `null`, `morph`, `read`); the heavy lifting of re-cognition;
- to **transconceptualize** is to transcognize with a change of frame: another morph, language, audience or occasion.

Move, program, plan, trace and coprocessor are the words of the model itself; section 2 says what each one is.

**Words on screen.** As in the MacroCOSM specification, the word a person reads comes first, and the word the files use
follows in parentheses where they differ. Thym's words are mostly the files' own: a statement of a program is a *step*
(`P:step`), a part of a plan is a *node* (`R:node`), and an entry of a trace is a *record* (`R:record`). A plan's node
is an item of kind `node`; it is not MacroCOSM's file word for an item.

**Blocks.** A block marked `thym` is one complete program file: it starts with its version line, it compiles under the
reference compiler with the standard moves, and its plan is well formed. A block marked `cosm` is one complete `.cosm`
file that loads and lints clean. A block marked `yaml` is a fragment and may point outside itself. A block marked
`python` sketches an interface. A block marked `text` is grammar, a transcript or a picture.

---

## 1. Provenance and the name

<!-- atem: where Thym comes from, how it is said, and who keeps it -->

### 1.1 Lineage

MacroCOSM OES 0.0.1 gave enough one grammar for volumes of items: Comprise's Holotypes, Canon's catalogs, EMF twins,
documents. Everything a reader does with them (load, check, draw) is generic. Everything that *moves* meaning between
them was not: deriving a twin, compiling a short, writing an atem and projecting an isotype were each a Python function
or a model prompt standing outside the format. Thym makes those moves first-class (section 2).

Three precedents shaped it.

- **DocOES** (MacroCOSM section 18.5). A document is enumerated into items and compiled back byte for byte, so the
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

The owner of enough keeps this specification. A program's version line, `thym 0`, pins the grammar of this document: a
program written under version 0 must compile under every later reference compiler. The language grows by moves, which
MiniCOSMs declare (section 17.6), and never by syntax within a version.

---

## 2. The model on one page

<!-- atem: programs compose moves over typed values; a compiler plans; a runtime runs and traces -->

```text
   author's side                   the three densities                  interpreter's side
   context · graph · morph        fabula · short · atem                 context · graph · morph
        │                               ▲      │                              │
        └── derive ── tell ── atem ─────┘      └── read ── expand ── cut ─────┘
                 (moves, each with a signature and a contract)

   program.thym ──compile──▶ items (thym/1) + plan (R:plan) ──run──▶ outputs + trace (R:trace)
                              ▲ inspectable before anything runs      ▲ replayable from its records
                                     a model-backed step ──▶ coprocessor (behind the contract)
```

- A **value** is a document that knows its type and its provenance: which move made it, from what, in which run. A
  text's type is its density (section 5).
- A **move** is one named step. It has a signature (what it takes and gives), a flag saying whether it **asks** the
  model, and a **contract**: the named checks that must hold on its output. The MiniCOSMs that own the standard moves
  declare them; a program may define its own.
- A **program** composes moves with bindings, choices and loops, and carries its reason in prose heads.
- The **compiler** parses, resolves, type-checks, contract-checks, estimates, enumerates the program into items, and
  plans it. It refuses whole: a program compiles entirely or not at all, and the refusal names the line.
- A **plan** is what a program will do, before it does it: a graph of nodes a person can read.
- The **runtime** checks the plan against the machine (a model present and large enough; agent-free or not; the inputs
  present), walks it in order, runs deterministic moves in code, and sends model-backed moves to the **coprocessor**:
  the model, behind the move's contract. A run lands all of its outputs or none.
- A **trace** is what a run did, one record per node. With the answers it recorded, it replays.
- Six **laws** bind every implementation (section 7.2).

---

## 3. The design rules

<!-- atem: seven rules every choice in this document answers to -->

1. **It reads.** Every keyword and every standard move is a FEED headword, or an inflected form of one (`takes`,
   `gives`, `has`, `covers`). A program can be read aloud to someone who
   has never seen one, and they follow it. People learn Thym for years the way they learn a craft: more moves, more
   morph scales, more contexts, never more syntax.
2. **Typed by density.** Every meaning value knows its density and its provenance. A move declares what it takes and
   gives, so an atem of a morph is a compile-time error.
3. **Moves are the primitives, and MiniCOSMs declare them.** `thym/1` declares the core; `emf/1`, `doc/1` and
   `comprise/1` declare their own (section 6.2). The language grows by MiniCOSM.
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
   `.cosm` in, `.cosm` out. The Python reference uses nothing a JavaScript runtime could not mirror (section 12.6).

---

## 4. Programs: the language

<!-- atem: the file, its blocks, its heads and statements, and the grammar in full -->

### 4.1 The file

A program file has the extension `.thym`. It is UTF-8 (a byte-order mark is tolerated), with LF or CRLF newlines. Its
first line that is neither blank nor a comment is the **version line**, `thym 0`. After it come `use` lines and blocks,
in any order. A comment runs from `--` to the end of the line. Blank lines are free. Indentation is free too: the
examples indent for the eye, and a compiler must read the same file with none.

A complete program, as it reads on the day the owner's drawing works end to end:

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

A `move` block may also stand inside a `program` block, before the program's statements; it is then local to that
program. Names are lowercase, `[a-z][a-z0-9-]*`. A name is unique among the blocks of its file, and differs from every
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
| `gives` | `gives <name>: <type>` | the output's name and type; one line; every path must then reach a `give` |

**Prose.** A prose head begins after its colon and runs to the end of its paragraph. It continues on the following
lines until a blank line, a line whose first word is a head keyword (`why` `must` `decided` `takes` `gives`), or `end`.
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
| `give` | `give <expr>` | gives the block's output; nothing after it on that path runs |
| `withhold` | `withhold <expr> [where <cond>]` | calls the move `withhold`: the items leave the output volume without a trace (section 18) |
| effect | `<expr>` | a move run for its effect (`lint v`, `trace`); its value is dropped |

### 4.5 Expressions and modifiers

An expression is a move call, a name, a literal, a field read, or an expression in parentheses. A **move call** is the
move's name, then its operands separated by commas, then its modifiers in the order its signature declares them:

```text
derive story
tell f as told
tell f by weight with rosa
expand (atem f) with f to 300 words
measure story against null of f
read f with mine in now
band (count staff) as [none, some] marked verified
project h as isotype
```

| modifier | after it | used by |
|---|---|---|
| `as` | a word or a list of words: an order (`told`, `weight`), a kind (`isotype`, `paratype`), a marking (`verified`, `stated`), the words of a band | `tell`, `project`, `mark`, `band` |
| `by` | an order | `tell` |
| `with` | a value: a morph, or a fabula | `tell`, `morph`, `read` (a morph); `expand` (a fabula) |
| `to` | a number and a unit: `300 words`, `12 sentences` | `cut` (words or sentences); `expand` (words) |
| `against` | a short: the null (`null of f`) | `measure` |
| `of` | a value | `null` and the accessors `fabula`, `context`, `graph`, `isomorph`, which take no operand: `of` is their argument |
| `in` | a context | `read` |
| `where` | a condition over items | `withhold`; and a filter on a volume or a list (`h where module is employees`) |
| `marked` | a marking: `verified`, `stated` | any expression that gives an item or a word; short for `mark … as …` |

A modifier's argument that begins with a move name is itself a call, and takes every modifier after it: `measure story
against null of f` is `measure(story, against: null(of: f))`. Parentheses group where the eye would otherwise misread.
A field is read with a dot: `now.medium`, `o.kind`.

**Conditions** join terms with `and`, `or` and `not`. A term compares two values with `is`, `is not`, `in` (membership
in a list), `<`, `>` or `=`; tests a field with `has` (the field is present); tests coverage with `covers` (section
7.3); or is a bare value of type `bool`.

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
| number | an integer; version 0 has no floats | `300`, `0` |
| string | double quotes; `\"` and `\\` are the only escapes | `"phone"` |
| date | `YYYY-MM-DD` | `2026-11-01` |
| word | a bare word where only a word can stand (section 4.5) | `told`, `verified`, `aim` |
| list | `[` values `]` | `[none, some]`, `[product, service, platform]` |
| density | `text` `fabula` `short` `atem` | |
| order | `told` `weight` | |
| marking | `verified` `stated` | |
| stance | `axiom` `observed` `deduced` `opinion` `assumed` `hearsay` | EMF's closed list |
| bool, nothing | `true` `false` `nothing` | `nothing` is the absent value an accessor may give |
| URI | `oes:<minicosm>/<database>[/<path>]`, as MacroCOSM section 11.3 writes it, or a relative file path | `oes:emf/notes-md`, `oes:thym/house/M/morph/rosa`, `notes.md` |

### 4.7 Keywords

Every keyword is a FEED headword or a form of one (`takes`, `gives`, `has` and `covers` are forms of `take`, `give`,
`have` and `cover`). The keywords of version 0 are:

```text
thym use program move morph context end
why must decided takes gives
let assert if then else for each in where emit give withhold
as by with to against of marked
is not and or has covers
true false nothing
```

The standard moves (section 6.3), the densities, the orders, the markings and the stances are reserved too: no block,
binding or user move may take one of these names. A few words are both a keyword or a type and a move (`morph`,
`context`, `package`, `graph`, `fabula`, `trace`); where the word stands decides which it is.

### 4.8 The grammar in full

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
call      := MOVENAME operand { "," operand } { modifier }
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

---

## 5. Values and types

<!-- atem: documents typed by density, each carrying what it was made from -->

### 5.1 The types

| type | what it is | carries |
|---|---|---|
| `text` | a markdown text | path or bytes, sha256 |
| `fabula` | an `emf/1` volume | its text's sha256 (spans resolve against it) |
| `short` | a telling | its fabula's sha256, its order, its morph (the null's when none was given) |
| `atem` | line + focus + push + pull | its source's sha256 and span |
| `item`, `volume` | any OES item or volume | URI, MiniCOSM, kind |
| `morph` | a `thym/1` morph: the ten scales | derived-from (text digests) or declared (a `morph` block) |
| `context` | surrounding (a catalog excerpt) or occasional (a `thym/1` context item) | |
| `graph` | an isograph or cryptograph excerpt | the release it came from |
| `package` | section 15 | contents and digests |
| `plan`, `trace`, `report` | sections 11 and 12; a `lint` report | |
| `number`, `string`, `bool`, `date`, `word`, `list of T` | plain values | |

The nine **meaning types** are `text fabula short atem item volume morph graph package`; a `context` is a meaning value
too when it is an occasional context item. Every meaning value carries **provenance** (section 5.3). The plain types
carry none.

### 5.2 Densities and what fits where

The four densities, `text`, `fabula`, `short` and `atem`, are types, and each move's signature says which it takes
(section 6.3). A value of one density is never silently read as another: `tell story`, where `story` is a `text`, is a
type error, and the message gives the fix ("derive it first").

### 5.3 Provenance

Every meaning value a move makes carries the move, its inputs' digests, the run (its trace's id), the step and the
node. Written
into a `.cosm`, this becomes the item's envelope provenance plus one field, `made`, which `thym/1` lists in its envelope
and every other MiniCOSM keeps as an unknown field:

```yaml
provenance: {mode: derived, sources: ["notes.md#sha256:54055e8…", "oes:thym/2026-11-01-1042-7f3a/R/record/3"], confidence: 0.9}
made: {move: tell, run: 2026-11-01-1042-7f3a, step: 3, node: R:node/4, engine: "model:g40-04"}
```

`made` is the law of provenance (section 7.2) in one field: Canon never holds a telling that does not say what it is a
telling of. A value a person wrote by hand has `made: {move: none}`, and a value read from disk without `made` is
treated as hand-made.

### 5.4 Bindings

`let` binds a name once, in the block where it appears. An inner block (the body of an `if` or a `for each`) sees the
names bound before it and may not rebind them. A loop variable is bound for the loop's body. A program's `takes` names
are bound for the whole program. A move's parameters are bound for its body, and a move sees no binding of the program
that calls it: it is called with values, never with the caller's scope.

---

## 6. Moves

<!-- atem: the primitives: a signature, an asks flag, a contract, and the MiniCOSM that owns each -->

### 6.1 What a move is

A move is one step, a transcoding or a transcognition, with four parts: a **signature** (its operands and modifiers with their types, and the
type it gives); an **asks** flag (true when the move needs the model); a **contract** (the named checks that must hold
on its output, section 7); and an **owner**, the MiniCOSM whose manifest declares it (section 17.6). A move
transcodes unless its declaration says `asks: true`, in which case it transcognizes. A model-backed move may have a **scaffold**: a deterministic
stand-in with a weaker output, which a run with `--rules` uses instead (section 19).

### 6.2 Who declares what

| MiniCOSM | moves |
|---|---|
| `thym/1` | `cut`, `count`, `words`, `digest`, `null`, `measure`, `morph`, `read`, `package`, `unpack`, `lint`, `trace`, and the accessors `fabula`, `context`, `graph`, `isomorph` |
| `emf/1` | `derive`, `tell`, `atem`, `expand` |
| `doc/1` | `enumerate`, `compile` |
| `comprise/1` | `project`, `band`, `mark`, `withhold`, in a sidecar, since enough never edits Comprise's manifest |

Section 17.6 gives the `moves:` block that declares them.

### 6.3 The standard moves of version 0

Each contract below is the `contract:` list of the move's declaration; section 7.3 says what each check holds.

| move | signature | asks | contract |
|---|---|---|---|
| `derive` | text → fabula | yes | `span-resolves` `stance-closed` `terms-grounded` `coverage` `emf-checks` `provenance` |
| `tell` | fabula \| item \| volume → short; `as` order or `by` order; `with` morph | yes | `coverage` `no-invention` `stance-kept` `scales-met` (with a morph) `footer` `provenance` |
| `atem` | text \| fabula \| short \| item → atem | yes | `atem-shape` `span-resolves` `provenance` |
| `expand` | atem → short; `with` fabula; `to` N words | yes | `coverage` `no-invention` `stance-kept` `length` `span-inside` `provenance` |
| `cut` | short → short; `to` N words or N sentences | no | `whole-sentences` `weight-order` `coverage` `provenance` |
| `null` | → short; `of` fabula | yes | `coverage` `no-invention` `stance-kept` `null-pinned` `provenance` |
| `measure` | text → morph; `against` short (the null) | yes | `scale-range` `scale-evidence` `provenance` |
| `morph` | short → short; `with` morph | yes | `coverage` `no-invention` `stance-kept` `scales-met` `provenance` |
| `read` | fabula → short; `with` morph; `in` context | yes | `coverage` `no-invention` `stance-kept` `scales-met` `labelled` `never-source` `provenance` |
| `project` | volume → volume; `as` kind (`isotype` or `paratype`) | no | the target schema's rules: `default-deny` `no-counts` `banded` `no-mark` `verified-derived` `standing-gate` `epoch` `provenance` |
| `band` | number → word; `as` a list of words (`[none, some]`: 0 is `none`; any other list: equal steps of ten) | no | `banded` |
| `mark` | item \| word → the same; `as` marking | no | `verified-only-where-derived` |
| `withhold` | item \| volume → nothing; `where` condition | no | `no-mark` |
| `enumerate` | text → volume (`doc/1`) | no | `byte-exact` `provenance` |
| `compile` | volume → text | no | `byte-exact` |
| `package` | text, fabula, morph, context, graph → package; the last three may be `nothing` | no | `digests` `released` `provenance` |
| `unpack` | package → text (the rest by accessor) | no | `digests` |
| `lint` | volume → report | no | none; the report holds the MiniCOSM's checks |
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
(section 13.2), and its scaffold gives those seven with the three pending.

### 6.4 Signatures in the manifest

A move's declaration is one mapping in a `moves:` list (section 17.6). `tell`'s, from `emf/1`'s manifest:

```yaml
moves:
  - name: tell
    takes: ['fabula | item | volume']
    gives: short
    modifiers: {as: order, by: order, with: morph}
    asks: true
    contract: [coverage, no-invention, stance-kept, footer, provenance]
    scaffold: outline                      # the rules-mode stand-in, or absent
    code: enough.thym.moves.emf:tell
    says: a telling of the fabula, in an order, in a morph
```

The compiler reads every manifest's moves when it resolves names. A program that names a move no manifest declares is
refused with the nearest name: "unknown move `summarise`; did you mean `tell`?" (check `unknown-move`).

---

## 7. Contracts and the six laws

<!-- atem: named checks on a move's output, six of which every implementation keeps -->

### 7.1 What a contract is

A contract is a list of named checks that must hold on a move's output before the output becomes a value. The
compiler checks the **static** part: it refuses a composition that cannot satisfy a contract, such as a `tell` whose
input is a `text`, or a `project … as isotype` that emits a bare count. The runtime checks the **dynamic** part on every
output. A model-backed output that fails is repaired narrowly, retried within its budget, and then refuses the run
(section 9). Most checks already exist as code in enough and Comprise; Thym names them and attaches them to moves.

### 7.2 The six laws

1. **Coverage.** A telling says nothing its fabula does not hold.
2. **Grounding.** Every span exists in its text; every term is in FEED or is a named entity.
3. **Monotone stance.** No move strengthens a claim's stance. The ladder, weakest first, is `hearsay` `assumed`
   `opinion` `deduced` `observed` `axiom`. A telling may say a claim more weakly than its fabula does, never more
   strongly.
4. **Round trip.** A package gives back its text (section 15.4), `compile` gives back a doc volume's markdown, and
   `compile` on a program's items gives back the `.thym` file: each byte for byte.
5. **Withhold, never falsify.** A projection leaves what it hides without a trace: no placeholder, no count of withheld
   things, no gap in an order that reveals them.
6. **Provenance.** Every meaning value says what it came from and which run made it (section 5.3).

### 7.3 The named checks

| check | holds when | exists today as |
|---|---|---|
| `span-resolves` | every `span` names lines or quotes that exist in the source text | `canon_derive` |
| `stance-closed` | every claim's stance is in EMF's closed list | the generic `closed-list` check |
| `terms-grounded` | every `L:term` is in FEED, or carries `{pending: "not in FEED"}`, or is a named entity | `canon_derive`'s lexicon floor |
| `coverage` | every sentence of a telling traces to one or more items of its fabula. As a condition it is written `f covers t`, for a fabula `f` and a text or short `t`: the fabula's items cover every claim-bearing sentence of `t` (prose or a list item of three or more words that does not end in a question mark; headings never count); the map `[{sentence, lines, items}]` lives in a derived fabula's `derived.covers` and in the check's verdict | new; the trace records the sentence → item map |
| `no-invention` | the telling names no entity, claim or event the fabula lacks | new |
| `stance-kept` | each claim's stance in the telling is at or below its fabula stance on the ladder; a sentence counts at the weakest stance its wording marks (a hedge reads as `hearsay`, a plain sentence as `observed`), and a claim told over several sentences is said at the weakest any of them marks | new |
| `footer` | a short ends with MacroCOSM 18.4.4's footer line | `short_footer` |
| `byte-exact` | the compiled bytes equal the source bytes | `docoes` |
| `atem-shape` | the line is 15 to 25 words; focus is at most two sentences; push is one; pull is one | MacroCOSM 18.3.5 |
| `length` | `to N words`: at most N words and at least 80 per hundred of N; `to N sentences`: N sentences or fewer | new |
| `span-inside` | the expanded short contains the claims of the atem's span | new |
| `whole-sentences` | `cut` removed whole sentences only | new |
| `weight-order` | `cut` removed the lowest-salience sentences first (by their items' salience) | new |
| `scale-range` | every scale is an integer from 1 to 5 | new |
| `scale-evidence` | every scale cites one to three sentences of the measured text, and gives its basis and confidence | new |
| `null-pinned` | every scale of the null telling is 1 (section 13.4 says why `analytical-depth` is) | new; the null morph's contract |
| `scales-met` | each scale of the output, measured, is within one step of the morph asked for; `analytical-depth` excepted, since the fabula sets it (section 13.4) | new |
| `labelled` | a reading carries `read_through: <morph name>` and the reading footer (section 14) | new |
| `never-source` | a reading's output path is not the path of any input, and no input file changed | new |
| `default-deny` | the projected volume holds only the fields its target schema names | Comprise `isotype.py` |
| `no-counts` | no number of anything internal reaches the projection; the only number allowed is one the schema names (a founded year) | Comprise |
| `banded` | a number leaves only as a word from the declared list, and a band changes only after the value has stayed past the boundary for 90 days | Comprise `band` |
| `no-mark` | a withheld item leaves no placeholder, count or gap | Comprise |
| `verified-derived` | `verified` only on fields the target schema derives (identity, shape, offers); `stated` on the subject's own words (aims) | Comprise |
| `verified-only-where-derived` | `mark … as verified` only on an item whose MiniCOSM lists it as derivable | new |
| `standing-gate` | a release as the subject needs first-party standing, or `sample: true` | Comprise `standing.py` |
| `epoch` | the date shown is the epoch, never the edit day; lists keep a fixed order that file order cannot change | Comprise |
| `digests` | every file in a package's catalog has the sha256 the catalog says | new |
| `released` | nothing is in `graph.cosm` without a release recorded in the holograph | new; Ascribe |
| `provenance` | every output carries `made` | new |
| `emf-checks` | the volume passes `emf/1`'s checks | `macrocosm.lint` |

### 7.4 `assert`

An `assert` line adds a check of the program's own. Its condition is evaluated at run time with the values at hand, and
false refuses the run with the message. `assert f covers story` is the usual one; its step's contract names the check
the condition uses (`covers` is `coverage`). A user move's `assert` lines become contracts of the move (section 8.3).

---

## 8. Control flow, bindings, user moves, `use`

<!-- atem: one choice, one loop, one output; moves that call moves; files that lend their moves -->

Bindings are section 5.4.

### 8.1 Choice and loop

`if … then … else … end` chooses. `for each … in … where … end` goes through the items of a volume or a fabula (in
`told` order: by span, then by id), the lines of a short, or the members of a list. `where` filters before the body
runs. The loop variable is bound for the body. The body may `emit`, `assert`, `let` new names and run moves for their
effect. It may not `give`: a program gives once, after its loops.

### 8.2 Three ways out

`give` gives the block's value, and every path of a block that `gives` must reach one. `emit` adds an item to the
program's output volume, or, with a slot (`emit employees: band …`), sets a field the target schema names; only
`project` consumes them, so a program that emits and never projects is refused, because the emitted items go nowhere. `withhold` marks items of a volume as withheld, and `project` leaves them out without a
mark.

### 8.3 User moves

A `move` block is a named program with parameters. It is called like a standard move, with its operands in parameter
order. It has a declared signature and inherits the contracts of the moves it uses, and its `assert` lines become
contracts of its own. A move may call other moves. A move that calls itself, directly or through another, is refused in
version 0. A move sees only its parameters.

```thym
thym 0

program story-in-brief
  why: a story, told plainly and then cut to a paragraph, for a listing.

  takes story: text
  gives brief: short

  move plain-paragraph(f: fabula): short
    let plain = tell f as told
    assert f covers plain else "the telling lost part of the fabula"
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
refusal names both files.

```thym
thym 0
use oes:thym/house

program tell-like-rosa
  why: a text told again in the house voice, for the help pages.

  takes t: text
  gives s: short

  let f = derive t
  give tell f as told with rosa
end
```

---

## 9. Errors: compile, plan, run

<!-- atem: three kinds at three times, each refusing whole, each with the line -->

| time | what is refused | with |
|---|---|---|
| **compile** | a parse error (`parse`); a version line that is not `thym 0` (`version`); an unknown move (`unknown-move`); an unknown URI or `use`d file (`unknown-uri`); two `use`d names that clash (`use-clash`); an unbound name (`unbound`); a type error (`type`); a name bound twice (`rebound`); recursion (`recursion`); a `give` inside a loop (`type`); a block that `gives`, with a path that never reaches a `give`, refused at the block's first line (`no-give`); emitted items with no `project` (`emit-without-project`); a static contract that cannot hold (the contract's check, such as `no-counts`) | the file and line, the check, and the fix where one is known |
| **plan** | a model-backed node while agent-free (`agent-free`, section 19); a prompt the machine's model cannot hold (`preflight`, the 16 GB rule, section 12.5); a missing or changed input (`input`: its digest differs from the plan's); a plan whose program cannot be read (`no-program`); a move with no implementation here (`move`), or none under `--rules` (`rules`) | the node, the count or the size, and what would make it run |
| **run** | a model-backed output that still fails its contract after narrow repair and its budget of attempts (the check's name), or that never fits the contract's schema (`schema`); a check the runtime lacks (the check's name, "not implemented"); a failed `assert`; a deterministic move that raises | the trace, which says the node, the check and the attempts; nothing is written |

A refusal is a value, not an exception: the CLI prints it and exits non-zero, the server returns it as the response,
and the viewer shows it in place of the plan or the outputs. It carries `stage` (`compile`, `plan` or `run`), `line`,
`check` and `message`, and like MacroCOSM's refusal it reads as a plain no.

---

## 10. Programs as documents

<!-- atem: a program enumerated into items, read at three densities, compiled back byte for byte -->

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
  contracts the move inherits.

`compile` on the items gives the file back byte for byte: the catalog's `front` (everything before the first block),
then each top-level item's `body` in `order`, is the file. The docs viewer shows a program at three densities like any
volume: its atem (the first sentence of the `why`), its short (the program as written, term-linked), and its fabula
(steps, moves and contracts as cards, with "mentioned in" across programs).

A program is also a text for every other move: `derive` on a `.thym` file gives a fabula of what it says, and an atem
of a program is the one line a listing shows.

---

## 11. The compiler

<!-- atem: seven stages, each refusing whole, ending in items and a plan a person can inspect -->

### 11.1 The stages

1. **Parse** the file into a tree, by recursive descent over the grammar of section 4.8. The tree keeps each
   statement's line and source text.
2. **Resolve** names, URIs, `use`d files, and the moves every manifest in the registry declares (section 17.6).
3. **Type-check** by density. Every expression gets a type, every call is matched to a signature, and the provenance
   of each value (what it will be made from, by which move) is worked out.
4. **Contract-check** the static part (section 7.1).
5. **Estimate**: count the model-backed nodes, the sizes of their inputs and the output budgets; work out the largest
   prompt the plan will build; and ask `preflight` whether the machine's model holds it.
6. **Enumerate** into `thym/1` items (section 10), written as `<name>.thym.cosm` beside the program when asked.
7. **Plan** into a directed acyclic graph of nodes, written as a `thym/1` volume of kind `plan` (section 17.3).

The nodes of a plan come in evaluation order, a nested call before the call that takes its value:

- one node per move call, a `marked` modifier included (it is a `mark` node of its own), and one per `assert`; a call
  of a user move is one node;
- one node per `if`, for its condition; each node of a branch says which branch it is in (`then` or `else`) and waits
  on the condition;
- for a `for each`, a node per member for each call in its body when the collection is known at plan time; otherwise
  one node per call, marked `repeats`, that takes the collection;
- no node for a `let` whose value is not a call; a filter (`h where …`) folds into the node that takes it.

A node takes names (inputs, bindings, or a temporary `t<n>` made by the nested call at node `n`) and gives at most one:
its binding, the block's `gives` name, or a temporary. A node runs after the nodes whose outputs it takes. The node that
gives a block's output also runs after every `assert`, `emit` and `withhold` before it, so nothing lands until every
check has passed. Its `after` list leaves out any node that another in the list already runs after.

A plan is inspectable before anything runs: the docs viewer draws it with the graph lens, the cosm viewer lists its
nodes with their `asks` flags and budgets, and agent-free mode refuses it on sight when it asks.

### 11.2 The package

`enough/thym/` is one Python package: `parse.py`, `types.py`, `check.py`, `enumerate.py`, `plan.py`, `run.py`,
`coprocessor.py`, `trace.py`, `contracts.py`, `moves/` and `cli.py`. The moves are implemented in `moves/`, by subject
(`emf`, `doc`, `project`, `edit`, `morph`, `pack`), as the manifests' `code` keys name them. The package imports the
standard library, PyYAML and `enough.macrocosm`, and nothing else of enough. The engines (`canon_derive`, `docoes`,
`llm`, `preflight`) plug in from outside, through the coprocessor and the moves' registration, so the compiler is
vendorable, as the reader is.

### 11.3 The command line

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

Every command reads `ENOUGH_THYM_ROOT` (default `~/enough/thym/`) for where runs live, and writes nowhere else unless it
is told the path.

---

## 12. The runtime

<!-- atem: a plan walked in order; the model as a contracted coprocessor; every run traced and replayable -->

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

### 12.2 The coprocessor

One interface; three implementations in enough; any number elsewhere.

```python
class Coprocessor(Protocol):
    def complete(self, contract: Contract, inputs: Inputs, *, budget: Budget) -> Candidate: ...

Contract  = {move, schema, checks, repair}                         # what the move needs back and what must hold
Inputs    = {name: (value, digest)}                                # the node's operands, by name
Budget    = {attempts, output_words, prompt_tokens_max, seconds}   # the node's budget and the machine's limits
Candidate = {output, engine, attempts, tokens, seconds, checks: [{name, ok, why}]}
```

- **`ModelCoprocessor`** is enough's: `llm.complete` with `canon_derive`'s machinery, generalised. It asks for
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
sha256; the environment (enough's version, the model's id and context size, agent-free or not, the machine's memory
band); when the run started and ended; and its outcome. One `R:record` item per node holds the node, the move, the
digests of the inputs and outputs, and the candidate's fields: the engine (`code` for a deterministic node, `rules`
for a scaffold, `model:<id>`, or `skipped` for a node on the branch not taken), attempts, tokens, seconds, and every
check with its verdict and, for a failed check, why; a node asked more than once also keeps `tries`, each failed
attempt's checks with their reasons, so a refused node explains all its tries. A record's tokens are its requests' and those of the model calls
its engines made, as the engine reports them where it does, else estimated; the environment's context size is the
model's window, read when a model runs and 0 when none does; and the trace's root item names the engines whose calls
the run recorded (`engines`, section 12.4). The trace also carries a copy of its plan's nodes, so that its
records' `node` references resolve inside the volume and the trace lints clean on its own. Traces live under `ENOUGH_THYM_ROOT/runs/` as
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

### 12.5 Budgets and the 16 GB rule

A plan carries the largest prompt it will build. At plan time the runtime asks `preflight` whether the machine's model
holds it; on a small machine a program may be refused with the number and the fix, as chat is today. Every node has an
`attempts` budget (3 for a model-backed node, 1 otherwise) and an output budget in words (the call's `to N words`, or
else the machine's). The trace records what each node cost.

### 12.6 Portability

No Python-only semantics. No reliance on mapping order beyond what the COSM YAML subset fixes. No floats in contracts:
bands and scales are integers, and the ratios of section 13.3 are integers per hundred or per thousand. Digests are
sha256: a text's over its bytes, a volume's over its catalog file, a file's always over its bytes, and a mapping's
over the reader's canonical dump (`macrocosm.dump`: keys in file order, LF newlines, UTF-8); the compiler's own
`dump` writes program volumes for people, with block scalars, and is never a digest's form. File paths are URIs. Time is UTC in traces and local only in file names. A JavaScript
runtime that passes the conformance suite is a conforming runtime, and the docs viewer could then make readings in the
page.

---

## 13. The null morph, the ten scales, morphs

<!-- atem: the plainest telling as the reference, and a morph as a measured departure from it -->

### 13.1 The null morph

The **null morph** is Thym's reference telling of a fabula. It tells in `told` order, one claim per sentence, in the
commonest FEED words that still say it. It says every stance in a fixed phrase ("the author holds that", "it is assumed
that", "reportedly"). It has no figure, no humour, no allusion and no contraction, and it is in the third person unless
the fabula's claims are in the first. It is one paragraph: a paragraph mark the model adds is read as none,
never as a departure. It is model-backed, with the tightest contract in the language, `null-pinned`:
every scale is 1. Its scaffold is the ordered outline told in the items' own sentences, which `--rules` gives (section
19). The null morph exists so that morphs are *differences*: a morph is what a text does that the null telling of its
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

Ratios are per hundred or per thousand words, compared as integers. The thresholds are version 0's. The conformance
suite pins them, and a later version may move them only with a decision recorded in section 21.

| scale | measure | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| `register` | the share of distinct words outside FEED's common band (FEED's bands 4 and up are common; a word with no band counts as common when it has eight letters or fewer; names never count; the null telling's register also exempts every word its fabula's items use, since it must say them), per hundred | < 2 | < 5 | < 10 | < 20 | ≥ 20 |
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
or three paragraphs, a statistics scale reports a confidence of at most 50, and a judgement scale at most 40. The word lists above are version 0's seed; the
reference keeps them in `enough/thym/moves/morph.py`. The statistics read English: the lists, the honorifics, the
stance phrases, FEED's bands and the rule of nine letters are English's, so a text in another language is measured
as if it were English (its judgement scales still hold, since the model reads the language); a later version may
give the lists per language.

### 13.4 Holomorph and isomorph

A **holomorph** is `measure t against null of f`, for a person's text `t` with fabula `f`: each scale's value as a
departure from the null, with its evidence. It is derived from any text the person writes with Ascribe active, and it
sharpens over a corpus: a corpus's morph is the scale-wise median of its texts' morphs, and each scale's confidence
rises with the number of texts. A person may **pin** a scale by hand; the pin wins, and the scale is listed as pinned.

`analytical-depth` is carried from the fabula rather than measured on the telling: a text's depth is its fabula's. A
telling may say fewer of the fabula's reasons than the fabula holds, never more, so the fabula's depth is a ceiling. The
null tells the claims without the reasons that link them, and so sits at 1. In a `read`, the morph's value is the ask,
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
  give tell f as told with plain-letter
end
```

As an item, a morph is `M:morph/<slug>` in a `thym/1` volume (section 17.3). It holds `scales` (scale → value, all ten);
`toward`, the direction of `formality`; `evidence`, `basis` and `confidence`, scale by scale, when it was measured;
`pinned` (a list of scale names); `derived` (`from`: text digests; `at`; `by`) or `declared: true`; and `shared`.

---

## 14. Readings

<!-- atem: someone else's fabula told in your morph: local, labelled, never the source -->

A **reading** is `read f with m in c`: a telling of a fabula in the reader's morph (their holomorph, or an isomorph they
chose), shaped by the reader's occasional context and made on the reader's machine. Its contract is `morph`'s with two
more checks. It is **labelled**: `read_through: <morph name>` in the file's front matter, and the reading footer at its
end. And it **never touches the source** (`never-source`): its path is never an input's path, and no input file changes.
A reading is saved beside the package or the text as `<text-stem>.read-<morph>-<YYYY-MM-DD-HHMM>.md`, in local time,
taking `-2`, then `-3`, on a collision, as shorts do.

The footer (the owner's wording, 2026-11-01):

```text
*a reading of notes.md through plain-letter, made here on 2026-11-01 by g40-04; the text stands unchanged*
```

The day is the UTC day, so a replay reproduces the line.

On screen a reading is always shown as "read through *name*", and the label is never hidden. A website that serves
packages may offer readings in its own isomorph and let a visitor override it with theirs. Nothing a reader does changes
what the author published. A reading of a reading is refused: `read` takes a fabula, and a reading is a short.

---

## 15. Packages

<!-- atem: the self-contained export of a text, in a folder, in one file, or encrypted -->

### 15.1 Folder form

`<name>.thym/` (a folder; a program is a file of the same suffix, `<name>.thym`, and a library tells the two apart by
the one being a folder with a `package.cosm` inside):

```text
text.md            the author's text, exactly as published
fabula.cosm        emf/1; every span resolves into text.md
morph.cosm         thym/1, kind morph (optional: the author's isomorph for this text)
context.cosm       thym/1, kind context (optional: the occasional context, and the surrounding volume's catalog excerpt)
graph.cosm         an isograph or cryptograph excerpt (optional; only what the holograph released for this text)
package.cosm       the catalog: contents with digests, the program and the trace that made it, the notice
```

`<name>` is the stem of the text the package was made from, and a package is saved beside that text: `notes.md` gives
`notes.thym/`, `notes.package.cosm` and `notes.thym.enc`. A reader of a library lists each form as one thing (Canon:
`kind: package`, `kind: sealed`) and never opens the folder up as texts. enough's export makes a package by running a
program over the text and its fresh EMF twin (`package story, f, m, c, g`, with `context of story` and `graph of
story`), so the package's catalog names that program and run; it derives nothing. Unpacking verifies every digest and
every span before it writes anything, then writes the text beside the package as `<name>.md` and its fabula as that
text's twin, `<name>.md.cosm`, whose `source.path` and locators say the text's name again, with the morph, context and
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
  - {path: fabula.cosm, sha256: 0000000000000000000000000000000000000000000000000000000000000000, role: fabula}
  - {path: morph.cosm, sha256: 1111111111111111111111111111111111111111111111111111111111111111, role: morph}
made: {program: {name: publish-story, sha256: 2222222222222222222222222222222222222222222222222222222222222222},
       trace: {run: 2026-11-01-1042-7f3a, sha256: 3333333333333333333333333333333333333333333333333333333333333333},
       at: 2026-11-01T10:42:00Z, by: enough/0.5.0}
notice: "A Thym package. The text is its author's; the fabula, morph and context describe it. Readings made from it are the reader's and are labelled."
nodes: []
```

### 15.3 Single-file and encrypted forms

`package` lands the single-file form, with the folder form `<name>.thym/` beside it. The **single-file form**,
`<name>.package.cosm`, is the same catalog with each file's bytes as a block scalar under
`contents[].text`, so that one file travels. The **encrypted form**, `<name>.thym.enc`, is the single-file form
encrypted on the owner's machine and handed, with a key, to a chosen party: this is what a cryptotype and a cryptograph
*are*. The cipher is Comprise's bundle scheme, `comprise-bundle/0` (a data key per package, AES-256-GCM over chunks, an
encrypted manifest), vendored into enough so that one cipher serves both subjects; the catalog's `encrypted: {cipher,
key: shown-once}` field names it, and the key never leaves the owner (the owner's ruling, 2026-11-01). An index may hold only **consented match tokens**, hashes
of characteristics the owner chose to make matchable, so that a search can match an encrypted package without reading
it.

The encrypted form is a `thym/1` package catalog that holds nothing in the clear: `encrypted: {cipher:
comprise-bundle/0, aead, key: shown-once, hid, bundle, keyring, manifest, chunks}`, binary values in base64. The key is
Comprise's recovery code (fifteen random bytes as twenty-four base32 characters, shown as six groups of four), which
wraps the package's data key by PBKDF2-HMAC-SHA256 at 600,000 iterations, as Comprise's recovery keyring entry does; it
is shown once and stored nowhere. enough depends on `cryptography` for AES-256-GCM (0.5.0, the owner's decision of
2026-11-02), so a package sealed in enough is Comprise's and opens there. Where AES-256-GCM is not available (a
vendored runtime without that package), the same layout is sealed with an encrypt-then-MAC AEAD built from HMAC-SHA256 alone (`aead:
hmac-sha256-ctr`: an HMAC keystream in counter mode, then a 16-byte HMAC tag, under keys split from the one key by
HKDF), and the file says so; a package sealed with AES-256-GCM opens only where AES-256-GCM is available.

### 15.4 The laws of a package

The author's text is the package's telling as told: `unpack` gives it back byte for byte, and what is checked is that
every span of the fabula resolves into it and that the fabula covers it. Every file's digest is in the catalog
(`digests`). The catalog names the program and the trace that made the package. Nothing is in `graph.cosm` without a
release recorded in the holograph (`released`). A package never names its author unless the author put the name in the
text.

---

## 16. Context

<!-- atem: the volume a text lives in, and the occasion it is read on -->

### 16.1 Surrounding context

The **surrounding context** is the volume a text sits in: its Canon volume's `canon.cosm`, the project's catalog, or a
site's served catalog when a website serves packages. It is read, never written. `context of story` gives the catalog
excerpt around the text: its neighbours, the volume's name and scope, and the terms the volume defines. A program may
use it to link terms, to choose a morph the volume prefers, or to tell a text in the light of its neighbours.

### 16.2 Occasional context

The **occasional context** is just-in-time: why this text, for whom, in what medium, at what moment, under what
constraints. It is a `thym/1` item of kind `context` with the fields `purpose`, `audience`, `medium`, `moment`, `hurry`
(a bool), `words` (a budget), `minutes` (a reading time), `language`, and any field a program names. The author's
occasion shapes the telling (a note for a friend, a brief for a board); the interpreter's shapes the reading (on a
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
       otherwise a telling in the reader's own morph, for this occasion.

  takes p: package, mine: morph, now: context
  gives r: short

  let f = fabula of p
  if now.medium is "phone" and now.hurry then
    give expand (atem f) with f to 300 words     -- the short way in
  else
    give read f with mine in now                 -- a telling in my morph, labelled a reading
  end
end
```

---

## 17. The `thym/1` MiniCOSM and the `moves:` block

<!-- atem: the MiniCOSM that holds programs, morphs, contexts, plans, traces and packages; and how any MiniCOSM declares moves -->

### 17.1 The catalog

A `thym/1` volume is one file. Its catalog declares `oes: thym/1` and says which of six kinds of volume it is:

| `kind` | file | holds |
|---|---|---|
| `program` | `<name>.thym.cosm` beside the program | the enumeration of one `.thym` file (section 10); `source: {path, sha256, size}`, `front`, `built` |
| `morph` | `<name>.morph.cosm` | one or more `M:morph` items |
| `context` | `<name>.context.cosm` | one or more `C:context` items |
| `plan` | `<run-id>.plan.cosm` | `program`, `inputs`, `estimate`, the `R:plan` item and its `R:node` items |
| `trace` | `<run-id>.trace.cosm` | `program`, `plan`, `environment`, `started`, `ended`, `outcome`, the `R:trace` item, its `R:record` items, and a copy of the plan's `R:node` items |
| `package` | `package.cosm` or `<name>.package.cosm` | `contents`, `made`, `notice` (section 15) |

Catalog keys: `oes`, `macrocosm`, `id`, `name`, `kind`, `source`, `front`, `built`, `program`, `plan`, `inputs`,
`estimate`, `environment`, `started`, `ended`, `outcome`, `contents`, `made`, `notice`, `encrypted`, `nodes`. The id
is `thym/<slug>`.

### 17.2 The modules and their kinds

| module | kinds | what |
|---|---|---|
| **P** Programs | `program`, `move`, `step`, `contract` | a block, a user move, a statement, a step's contract |
| **M** Morphs | `morph` | ten scales with evidence |
| **C** Contexts | `context` | an occasion |
| **R** Runs | `plan`, `node`, `trace`, `record` | a plan and its nodes; a trace and its records |
| **K** Packages | `package`, `reading` | a package's catalog entry; a saved reading's record |

Kinds are unique across the modules, as in every MiniCOSM. Every item has the envelope (id, type, name, summary,
status, visibility, provenance, pending, links) and may carry `made` (section 5.3).

### 17.3 Ids and the fields of each kind

`<module>:<kind>/<slug>`, with the slug grammar of `doc/1` (dots allowed, so a step can name its program):

| kind | id | fields beyond the envelope |
|---|---|---|
| `program` | `P:program/<name>` | `why`, `must` (a list), `decided` (a list of `{date, what}`), `takes`, `gives` (lists of `{name, type}`), `body` (verbatim), `lines`, `order`, `steps` (refs to its top-level steps), `moves` (refs to its local moves) |
| `move` | `P:move/<name>` or `P:move/<program>.<name>` | as `program` (`order` for a top-level move only), plus `params` |
| `step` | `P:step/<program>.<n>` | `of` (ref), `n`, `text` (the line verbatim), `line`, `form` (`let`, `assert`, `if`, `for`, `emit`, `give`, `withhold`, `effect`), `move`, `calls` (every move the line calls), `binds`, `uses` (names), `asks`, `contracts` (refs), `slot` (a labelled emit's field); an `if` adds `lines` and `branches` (`{then, else}`, refs); a `for each` adds `lines` and `steps` (refs) |
| `contract` | `P:contract/<program>.<n>` | `of` (ref), `move`, `checks` (a list of check names) |
| `morph` | `M:morph/<slug>` | `scales`, `toward`, `evidence`, `basis`, `confidence`, `pinned`, `derived` or `declared`, `shared` |
| `context` | `C:context/<slug>` | `purpose`, `audience`, `medium`, `moment`, `hurry`, `words`, `minutes`, `language`, and any field |
| `plan` | `R:plan/<run-id>` | `nodes` (refs, in order), `asks` (a count), `largest_prompt` (tokens) |
| `node` | `R:node/<n>` | `step` (`{program, n}`), `move`, `asks`, `takes` (names), `gives` (a name), `after` (refs), `budget`, `line`, `repeats`, `branch` (`then` or `else`), `slot` (a labelled `emit`'s field) |
| `trace` | `R:trace/<run-id>` | `records` (refs), `outcome` (`landed`, `refused`), `stopped_at` (a ref, when refused) |
| `record` | `R:record/<n>` | `node` (ref), `move`, `inputs`, `outputs` (lists of `{name, sha256, path}`), `engine`, `attempts`, `tokens`, `seconds`, `checks` (a list of `{name, ok, why}`) |
| `package` | `K:package/<slug>` | as the catalog's `contents` and `made`, for an index that lists packages |
| `reading` | `K:reading/<slug>` | `of` (the package or text), `read_through`, `path`, `at`, `by` |

Steps are numbered from 1 in the order they are written. In a move local to a program, `<program>` reads
`<program>.<move>` (`P:step/open-house.offer-line.1`); a contract for a call nested inside a step adds `.<m>`
(`P:contract/publish-story.3.1`), as section 10 says.

### 17.4 Checks

The envelope checks the generic reader runs, and six of `thym/1`'s own, which `enough/thym` runs; the manifest states
them as prose under `checks.own`, so a generic reader neither runs nor lists them, and lints a Thym volume on the
envelope alone: `program-compiles` (a `program` volume's `source` compiles to these items), `plan-acyclic`,
`trace-complete` (every node has a record, or the trace is `refused` with `stopped_at`), `scale-range`, `digests` (a
package's files match its catalog), `reading-labelled`.

### 17.5 Renderers

`program` (the file compiled back; lens `{kind: short, order: told}`), `plan` (a flowchart of nodes along `after`),
`trace` (a table of records: id, move, engine, attempts, seconds), and, by code, `text-tree` and `compile`.

### 17.6 The `moves:` block

Any MiniCOSM's manifest may carry a `moves:` list. A MiniCOSM whose manifest enough does not edit declares its moves in
a sidecar `<name>.moves.cosm` beside the manifest, a mapping `{moves-of: <minicosm>/<major>, moves: [...]}`; Comprise's
is `comprise.moves.cosm`. When both exist, the manifest's list wins and the sidecar is reported. The generic reader
keeps the block as an unknown key; the Thym compiler reads it. Each entry:

| key | holds |
|---|---|
| `name` | the move's name, a FEED headword, unique across the registry |
| `takes` | a list of accepted types for the operands, in order; alternatives joined by `\|`; empty when the move's argument is its `of` |
| `gives` | the type given |
| `modifiers` | a mapping, modifier word → the type it takes (`as: order`, `to: words`, `with: morph`, `of: package`) |
| `asks` | `true` when the move needs the model; absent or `false` otherwise |
| `contract` | the list of check names (section 7.3) |
| `scaffold` | the name of the rules-mode stand-in, when one exists |
| `code` | the reference implementation, informative: `enough.thym.moves.emf:tell` |
| `says` | one line, in FEED words, for the viewer and the readvisor |

---

## 18. Projections: the dial as a program

<!-- atem: an isotype is a holotype transcoded by a program whose contracts are the target schema's rules -->

An isotype is a holotype *transcoded*: `project h as isotype`, under a program that gives every item a density
(`fabula`, `short`, `atem`, or withheld) and a marking (`verified`, `stated`). The target schema's rules
(`comprise-isotype/0`: default-deny, assertions not measurements, withhold never falsify, epochs and bands, verified
only where derived, the standing gate) are the contract of `project` (section 6.3), so the schema stops being the
ceiling and becomes the law. The isotype's draft step becomes three preset programs (minimal, fuller, house), and a verified
owner may write their own. A release carries the digests of the program and the trace that made it. The Comprise side
is a specification of its own, for comprise-dev; enough builds none of it and reads what it produces.

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

<!-- atem: with the agent off, only deterministic plans run, and scaffolds stand in where they are honest -->

In agent-free mode the coprocessor is the refusing one: a plan with model-backed nodes is refused at plan time with
their count and the first one's line ("3 steps ask a model; agent-free is on"). A plan with none runs. With `--rules`,
each model-backed move that declares a `scaffold` runs it instead: `derive` gives the rules twin, `atem` the labelled
scaffold, `tell` and `null` the ordered outline, and `measure` the seven statistics scales with the three judgement
scales pending. A move with no scaffold (`expand`, `morph`, `read`) still refuses. The trace says `engine: rules` for
each scaffold, and every output is marked `state: pending`, as EMF's rules mode marks a twin. The viewer offers only
plans that can run.

---

## 20. Conformance

<!-- atem: what a compiler and a runtime must do, and the suite that shows it -->

### 20.1 A compiler must

1. Read the grammar of section 4.8 exactly, and refuse a file whose version line is not `thym 0`.
2. Resolve moves from every manifest's `moves:` block and every `*.moves.cosm` sidecar in the registry's folders, and
   refuse an unknown move with the nearest name.
3. Type every expression by section 5, refuse every type error with its line, and work out provenance.
4. Refuse the static contract failures of section 7.1 and the other compile errors of section 9, each with its check.
5. Enumerate into `thym/1` items that `compile` back byte for byte (section 10), and plan into an acyclic graph of
   nodes by section 11.1.
6. Return refusals as values with `stage`, `line`, `check` and `message`.

### 20.2 A runtime must

1. Refuse a plan at plan time when the environment cannot run it (section 9), with the count or the size.
2. Walk the plan in a topological order; run deterministic moves by their reference semantics; send model-backed moves
   to a coprocessor under their contracts; check every output against its contract before it becomes a value.
3. Land every output or none; write the trace with every record; name the run in every output's `made`.
4. Replay a recorded run to byte-identical outputs with the replay coprocessor.
5. Keep the six laws.

### 20.3 The suite

`tests/fixtures/thym/` in enough-dev, portable as a folder together with `tests/fixtures/cosm/`, MacroCOSM's own corpus,
which holds the sample Holotype that `open-house` runs on:

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
`expected/<name>/outputs/` and every `replay/` run re-runs to its recorded outputs. The three programs of this document
(sections 4.1, 16.2 and 18) are the suite's first three, byte for byte, and the suite's test compiles every block marked
`thym` here.

### 20.4 Where the reference wins

The reference landed on 2026-11-01 and passed checkpoint A (a real-model run that replays) the same night. Two
readings were corrected on the way and folded into their sections: `stance-kept` reads a claim across every sentence
that cites it (section 7.3), and the null telling's `register` exempts its fabula's own words (section 13.3). When a
further disagreement is found, the text is corrected and the disagreement recorded here with the section it touched,
until the next version folds it in.

---

## 21. Decisions in this version

<!-- atem: the decisions version 0 settled, one numbered line each -->
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

---

## 22. Open questions and roadmap

<!-- atem: what version 0 leaves for the round, and what waits for a later version -->

**For the 0.5.0 round:** the names of the three preset projection programs (Comprise's side); whether `bool` stays the
type word (FEED has it only in the bowls sense) and whether *transconceptualize*, the verb, enters FEED under R6 beside
the noun. Settled on 2026-11-01: the reading footer's wording (section 14); the encrypted package vendors Comprise's
bundle cipher (section 15.3); `thym_run` and `thym_check` sit behind the `macrocosm-oes` skill; the holograph's
modules (Ascribe OES 1, its own manifest); the stance ladder as section 7.2 writes it.

**Open in version 0:** the `register` measure where FEED has no frequency band for a word; the thresholds of section 13.3 before the first corpus; parallel nodes in the
reference runtime (allowed, not required).

**Later versions:** recursion in user moves; `for each` over the lines of a short with edits (a text editor in Thym);
user-defined check names beyond `assert`; a third order for `tell` (events first, as they happened); a JavaScript
runtime and readings in the page; Ascribe's module in enough; the bridge between Comprise's employees and Ascribe.

---

## Colophon

Written 2026-11-01 for enough 0.5.0, version 0 of the language. The design document with the owner's rulings is
`docs/thym-architecture.md` (local); the plan is `docs/thym-050-plan.md` (local). The MacroCOSM specification is
`docs/MACROCOSM_OES.md`. Copyright © 2026 Graham Smith. All rights reserved.
