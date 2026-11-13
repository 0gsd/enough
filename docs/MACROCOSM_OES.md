# MacroCOSM OES

*Edition 0.6.0 · revised 2026-11-06 · cosmoes.org home: https://macro.cosmoes.org/*

*This edition describes grammar version 0.6.0; files written under 0.5.4, 0.0.2 and 0.0.1 are read unchanged.*

MacroCOSM OES is an OES: a shared grammar and the core built into it. The grammar says how a domain is enumerated as
plain-text `.cosm` files that are at once a file system and a relational database, made to be rendered: how a file is
read, how a volume names the format it is written in, what an item is and which columns every item carries, how one
item points at another, how an unknown value is written down, how anything is addressed, which checks every volume can
be held to, how a manifest declares a format, and how a renderer draws one. It is the grammar that Comprise OES worked
out for companies, read out of it and written down on its own, so that nothing in it says "company". The core holds
five built-ins, written in the grammar and declared by manifests that ship with every reader: the product tree
(`cosm`), Canon, the home file system (`canon`), the fabula (`fabula`), documents (`doc`) and Thym's volumes (`thym`),
with the densities and the dialectic (section 18). Two MiniCOSMs, Comprise OES for companies and Ascribe for a person,
are written in it with specifications of their own (section 19).

**Status.** This text is normative. Its reference implementation is enough (https://github.com/0gsd/enough), which
reads every format registered in sections 18 and 19; Comprise is the reference implementation of Comprise OES. Where an
implementation and this text disagree, one of them is in error; the Changes appendix (section 21) records which was
corrected. *By reference* marks a part that is defined in another document, which is linked where it is named.

**The format does not change.** A MacroCOSM file is a `.cosm` file in the COSM YAML subset, exactly as Comprise OES
reads it. Version 0.0.1 names the grammar, generalizes it, and adds a few optional manifest keys so that a reader can
handle a format it has never seen without new code (section 13.5). Every Comprise Holotype and every standalone COSM
tree written under an earlier version reads unchanged.

## Contents

<!-- atem: every section of this specification, in order -->
1. Provenance and the name
2. The model on one page
3. Scales: MacroCOSM, MiniCOSM, MicroCOSM
4. The file format
5. The declaration
6. Volumes and catalogs
7. Items, kinds, fields
8. The envelope
9. References and links
10. Open questions
11. Ids, paths, URIs
12. Checks
13. The manifest
14. Renderers and lenses
15. Versions and signatures (by reference)
16. The private/public split (by reference)
17. MicroCOSMs
18. The core: the registry, the product tree, Canon, the fabula, documents, the dialectic, Thym's volumes
19. The MiniCOSMs: Comprise OES and Ascribe
20. Conformance
21. Changes
22. *Withdrawn in edition 0.5.4*

Appendix: the mapping to Comprise OES · Colophon

## How to read this

<!-- atem: the rule words, the words on screen, and what an example promises -->
**Must and may.** *Must* is a rule a conforming reader or writer keeps. *May* is a permission. *Should* is advice the
checks do not enforce.

**Words.** The words a person reads on screen come first. Where the spec must be exact, the term the files and the
reader use follows in parentheses.

| Here | In the files and the reader | Example |
|---|---|---|
| item | node, a mapping in a `nodes:` list | `P:claim/close-locks-the-day` |
| kind | type, the `type:` field | `claim` |
| open question | pending | `{pending: "…"}` |
| checks | lint | enough's `lint` command, run over a volume |
| volume | the database a catalog heads | a Holotype, a Canon volume, a text's fabula |
| part | a top-level division of a volume (Comprise: concern, *atom*) | `atoms/meadow/` |

**Examples.** Every block in this document marked `cosm` is one complete file: it starts with its declaration, it
loads, and it passes the checks its format selects, with every reference resolving inside the block. A block marked
`yaml` is a fragment of a file and may point at things outside it. A block marked `text` is grammar or a picture.

---

## 1. Provenance and the name

<!-- atem: where MacroCOSM came from, what its name means, and who keeps it -->

### 1.1 Lineage

MacroCOSM did not start as a grammar. It started as a way to describe one firm, and each version kept what the last
one learned.

| Version | Date | What it was | Its marks in the files |
|---|---|---|---|
| OPI v0.1 | 2026-10-02 | the first draft: a firm described as a tree of offerings, products and services, each answering the same questions; called *Ontology Programming Interface* | `opi:`, `.opi` files |
| COSM 0.2 | 2026-10-12 | the same tree as a plain-text schema and markup, *Context Ontology Schema and Markup*, written by the context-ontology skill: five levels, nine aspects, roles instead of people, a Mermaid drawing grammar | `cosm: 0.2`, `firm:`, bare ids such as `offering/ledger` |
| COSM 0.3 | 2026-10-20 | the tree taken whole into Comprise OES 1 as its chapter P, the product tree: the root renamed the brand, a `restricted` visibility, ids namespaced inside a Holotype | `cosm: 0.3`, `brand:`, `P:offering/ledger` |
| Comprise OES 1 | 2026-10-20 | the first MiniCOSM: a company as a folder that is also a relational database, eight modules, a declaration line, paths, a manifest, and a map naming MacroCOSM, MiniCOSM and MicroCOSM as *mapped, not built* | `oes: comprise/1`, `manifest: minicosm/0` |
| MacroCOSM OES 0.0.1 | 2026-10-22 | this document: the grammar Comprise mapped, written down apart from any one domain, with a reader that loads any MiniCOSM from its manifest | `oes: <minicosm>/<major>`, `macrocosm: 0.0.1` (reserved) |
| MacroCOSM OES 0.0.2 | 2026-11-02 | two MiniCOSMs more, `ascribe/1` (a self with no name, section 19.2) and `thym/1` (programs, morphs, contexts, plans, traces and packages, section 18.7); the `moves:` block of a manifest and the `<name>.moves.cosm` sidecar (section 13.4); the grammar unchanged | `macrocosm: 0.0.2` (reserved) |
| MacroCOSM OES 0.5.4 | 2026-11-03 | the canonical edition, published at https://macro.cosmoes.org/ with the MiniCOSM specifications at their own homes; the grammar unchanged, and files written under 0.0.2 read unchanged | `macrocosm: 0.5.4` (reserved) |
| MacroCOSM OES 0.6.0 | 2026-11-06 | an OES with a core: five built-ins (`cosm`, `canon`, `fabula`, `doc`, `thym`) and two MiniCOSMs, `comprise/1` and `ascribe/1` (sections 18 and 19); the fabula, in three flavours, in place of EMF, whose `emf/1` is read as an old spelling; the dialectic, module D, which every format inherits (section 18.6); in the grammar, `minicosm` is `format`, a declaration may have old spellings, and a reference may be an address; files written under 0.5.4, 0.0.2 and 0.0.1 read unchanged | `macrocosm: 0.6.0` (reserved), `oes: fabula/1`, `core: true` |

The earlier specifications stay where they are. COSM 0.2 is the context-ontology skill's own reference. Comprise OES is
published at https://comprise.cosmoes.org/, and the map of the family, which named the three scales, is the front page
of https://cosmoes.org/. This document points at their section numbers and does not repeat them.

### 1.2 The name

**COSM** is the family's name. It is no longer an acronym. It was *Context Ontology Schema and Markup*, and before that
*OPI*; both are history. It comes from *kosmos*, the Greek word for order, and for the world as an ordered whole. `.cosm`
is the family's one file extension.

**OES** stands for *organizational enumeration system*: a system that organizes a domain by enumerating everything in
it, as a file system that is also a relational database, made to be rendered. Each of the four parts of that sentence
is a promise.

- **Enumerating.** It lists what there is, item by item, each with its sources. What is not known is written as an
  open question addressed to whoever can answer it, never as a guess.
- **A file system.** Plain text files in folders, on the owner's own machine. Anyone can read them without an app, move
  them, keep them in version control, and leave with everything.
- **A relational database.** Every item has a primary key, its id. Its fields are columns, its references are foreign
  keys, and the checks are constraints. The same files can be indexed and queried.
- **Made to be rendered.** The description is never the end. It exists to be turned into other forms for other readers:
  a drawing, a summary, a text rewritten for one audience, an export for an agent, a public projection. A renderer can
  show only what the description holds, so the description is held to account.

**MacroCOSM**, **MiniCOSM** and **MicroCOSM** are the three scales of the family (section 3). The names borrow an old
idea, from Greek philosophy to the Renaissance: that a small world mirrors the order of the great one. Here each smaller
scale keeps the order of the larger and adds to it.

### 1.3 Stewardship

MacroCOSM OES is stewarded by Verroes (Graham Smith). The specification, the manifests registered in sections 18 and 19
and the names of the family are his. The texts and the manifests are licensed under CC BY 4.0, the author makes the
OWFa 1.0 promise, and the names are not licensed (see the colophon). Its canonical edition is published at
https://macro.cosmoes.org/; each edition says what changed in the Changes appendix (section 21). The reference
implementation is enough (https://github.com/0gsd/enough).

---

## 2. The model on one page

<!-- atem: a volume read as a file system and as a relational database -->
A volume is a file system that is also a relational database. Every part of the grammar has a place in both readings,
and a name on screen.

| MacroCOSM | As a file system | As a relational database | On screen | Section |
|---|---|---|---|---|
| volume | a folder with its catalog at the root, or one catalog file that holds everything | a database | a Holotype, a Canon volume, a text's fabula | 6 |
| catalog | the volume label: which language, which version, what is aboard | the catalog: the format, its version, the parts, the sources | (details) | 6.2 |
| part | a top-level folder (Comprise's concern) | a schema | concern | 6.4 |
| module | a folder named by one capital letter, or the items in one file whose ids carry that letter | a group of tables | module | 7.2 |
| kind | the items of one type, wherever they are written | a table | kind | 7.3 |
| item | an entry, addressed by its path | a row; its id is the primary key | item | 7.1 |
| field | an attribute | a column | field | 7.4 |
| the envelope | the entry's metadata: name, status, who may see it, where it came from | the system columns every table has | the line above every item | 8 |
| reference | a link to another entry | a foreign key | a link to the item | 9 |
| typed link | a labelled link | a join row with one column, the relation | a labelled link | 9.4 |
| open question | a placeholder entry, with who must fill it | NULL with a reason and someone to answer it | open question | 10 |
| checks | `fsck`, the file system check | constraints | checks | 12 |
| manifest | the format's definition, kept outside every volume | the schema definition | (about this format) | 13 |
| renderer, lens | a viewer | a report, a view | a drawing, a card, a text tree | 14 |
| path | a path | a qualified key | (details) | 11.2 |
| URI | a path qualified with the language and the volume | a fully qualified key | (details) | 11.3 |
| saved and signed version | a snapshot, a signed snapshot | a point-in-time copy, a signed checkpoint | (by reference) | 15 |
| the split | a read-only public mount of a projection | a default-deny view with fixed columns | Holotype and isotype | 16 |

**What is real in each reading.** The file system is the volume itself: plain text, canonical. The relational database
is real wherever a reader builds it from the files: the reader keeps a table of items keyed by id, a table of resolved
references, and the checks. A format may keep a local database beside its files for what must never be in a file
(Comprise keeps its people there); that database is outside the model (section 6.6).

**The one rule that makes both readings agree:** a path names the same thing a primary key does (section 11).

---

## 3. Scales: MacroCOSM, MiniCOSM, MicroCOSM

<!-- atem: the grammar and its core, a domain's OES, an organization's additions -->

| Scale | What it is | In this edition |
|---|---|---|
| **MacroCOSM** | an OES: the shared grammar, and the core built into it | this document, and its reference implementation, enough |
| **MiniCOSM** | a domain's OES with a specification of its own, declared by a manifest: its volume layout, modules, kinds, fields, references, checks and renderers | two: Comprise OES (`comprise`, companies) and Ascribe (`ascribe`, a person) (section 19) |
| **MicroCOSM** | one organization's extension on top of a MiniCOSM: the extra kinds, fields, checks or renderers it needs | reserved for a later edition (section 17) |

<!-- term: core -->
The **core** is what MacroCOSM holds built in: the grammar's parts, five built-ins, the three densities and the
dialectic (section 18).

<!-- term: built-in -->
A **built-in** is a kind of volume the core defines, declared by a manifest that ships with
every reader and says `core: true` (section 13.3): `cosm/0` the product tree, `canon/1` Canon, the home file system,
`fabula/1` the fabula, `doc/1` documents and `thym/1` Thym's volumes. A built-in is never a MiniCOSM, and a MiniCOSM is
never built in.

<!-- term: format -->
A **format** is what a declaration names: a built-in or a MiniCOSM (section 5). Wherever this document states a rule
for a format, the rule holds for both.

**What MacroCOSM gives every format.** All of it, unchanged: sections 4 to 14 of this document, the parts defined by
reference in sections 15 to 17, and the core's dialectic, whose module every format inherits (section 18.6).

**What a format declares.** Its manifest (section 13) says, in order: its name and version and the declaration a volume
uses to name it, with any legacy forms and old spellings it still reads; whether it is built in; its volume layout; its
modules and kinds, and for each kind at least the fields the checks follow; its reference forms and closed lists; the
checks that apply, with their severities; its renderers and lenses; the opening questions of its dialectic, when it has
any; and, when it has one, its public projection. A volume names its format with one line in its catalog and never
embeds the manifest.

**Each smaller scale keeps the order of the larger.** A format may add to the grammar (kinds, fields, envelope fields,
closed lists, checks, renderers) and may narrow what the grammar leaves open (which envelope fields are required, which
link relations are allowed). It may not change what the grammar means: an id, a path, a reference, an open question
and the declaration mean the same thing in every format.

---

## 4. The file format

<!-- atem: how a cosm file is written: its encoding, YAML subset and scalars -->

### 4.1 Encoding and shape

- A `.cosm` file is UTF-8, with or without a byte-order mark. CRLF and LF read the same.
- A file is one YAML document whose top level is a mapping. An empty file reads as an empty mapping.
- A file that does not parse, or whose top level is not a mapping, is a load problem (check `load`, section 12). The
  rest of the volume still loads. A reader never stops at the first problem; it collects every load problem and the
  checks report them as errors.

### 4.2 The COSM YAML subset

The subset is YAML without the parts that make a file mean something other than what it says.

| Forbidden | Why | A reader |
|---|---|---|
| anchors (`&name`) and aliases (`*name`) | one value in two places hides a reference that the checks cannot see | reports a load problem |
| tags (`!!str`, `!thing`) | a tag changes how a value is read; the subset has one way | reports a load problem |
| more than one document in a stream (`---` between documents) | a file is one mapping | reports a load problem |

A reader must not crash on a forbidden construct, and must name it in the problem. A writer must not produce one
(section 4.5).

### 4.3 Scalars

- **Booleans are YAML 1.2's:** `true` and `false`, in lower, title or upper case (`true`, `True`, `TRUE`). The YAML 1.1
  words `yes`, `no`, `on` and `off` are strings. (A field called `on:` depends on it.)
- **Everything else** resolves exactly as PyYAML's `SafeLoader` resolves it: integers, floats, nulls and timestamps
  included. Those rules are YAML 1.1's, so a few plain scalars are not what they look like.

| Written | Read as | So |
|---|---|---|
| `2019-03-01` | a date | a date field is a date, not a string |
| `2026-10-22T09:15:30Z` | a date and time, in UTC | |
| `cosm: 0.3` | the float 0.3 | a version compares as text (`0.3`), never as a number |
| `macrocosm: 0.0.2` | the string `0.0.2` (a reader keeps `0.0.1` as it is) | |
| `0.10` | the float 0.1 | |
| `7:00` | the integer 420 (base 60) | write times quoted: `"07:00"` |
| `012` | the integer 10 (octal) | write codes with leading zeros quoted: `"012"` |
| `~`, `null`, nothing after the colon | null | |
| `yes`, `on` | the strings `yes`, `on` | |

The reference loader is a few lines of Python. It is `SafeLoader` with the YAML 1.1 boolean resolver removed and a YAML
1.2 one put back, exactly as Comprise reads its Holotypes:

```python
import re, yaml

class Loader(yaml.SafeLoader):
    """SafeLoader with YAML 1.2 booleans: only true and false, in any of three cases."""

Loader.yaml_implicit_resolvers = {
    first: [(tag, rx) for tag, rx in resolvers if tag != 'tag:yaml.org,2002:bool']
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()}
Loader.add_implicit_resolver('tag:yaml.org,2002:bool',
                             re.compile(r'^(?:true|True|TRUE|false|False|FALSE)$'), list('tTfF'))
```

A second implementation in another language must reproduce these results, not YAML 1.2's own core schema.

### 4.4 Comments and style

- Comments are YAML's `#`. A reader ignores them; a semantic rewrite loses them (section 4.5).
- Block scalars (`|`, `>`) are legal for long prose.
- Flow mappings and sequences are idiomatic for short records: `provenance: {mode: derived, sources: [x], confidence: 0.8}`.
  A comma inside a flow value ends the value, so a value with a comma is quoted.
- Key order carries meaning in one place only: the declaration is the first key of a catalog (section 5). Elsewhere a
  reader ignores order and a writer keeps it.
- A `#` inside a plain scalar is a comment only when a space comes before it. Locators such as `close.md#L3` are safe
  unquoted, and are quoted in this document for clarity.

### 4.5 Writing

- A writer dumps with `yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=110)`, or an equivalent that
  produces the same subset.
- The declaration is written first.
- A dumper emits an anchor when the same object appears twice in the data. A writer copies values instead of sharing
  them, so no anchor is ever written.
- A writer quotes every scalar meant as text that the loader would read as something else (section 4.3).
- A semantic rewrite (load, change, dump) keeps every key and value and loses comments and layout. Byte-preserving edits
  of one item inside a file are Comprise's (its `edit` model); MacroCOSM reserves them for a later edition.

### 4.6 Text, not code

A `.cosm` file is data. A reader never executes anything in it, never follows an include, and never opens a file because
a value names it, except where the manifest's volume layout says where the files of a volume are (section 6). A path is
an address, never a door (section 11.2).

---

## 5. The declaration

<!-- atem: the line that names a volume's format, and what a reader refuses -->

### 5.1 The form

A catalog says which format it is written in with its first key:

```yaml
oes: canon/1
```

```text
declaration = "oes:" SP format "/" major
format      = lower *( lower / DIGIT / "-" )          ; the format's name, as its manifest gives it
major       = "0" / ( %x31-39 *DIGIT )                ; the format's major version, an integer
```

The value names a format, a built-in or a MiniCOSM (section 3), and a major version, never a minor one. It is spelled
exactly as the manifest's `declaration.value` gives it, or as one of the old spellings the manifest lists (section
5.2), and a reader refuses any other spelling, as Comprise does: `comprise/01` is refused, and so is a value with a
space before or after it. A change to a format that existing volumes can still be read under keeps its major; a change
that would make an existing volume mean something else needs a new major, and a change that would alter what a path
means needs a new format (section 11.3).

### 5.2 Identifying a catalog

The reader keeps a registry of the manifests it knows (section 13.6), in order: `comprise`, `cosm`, `canon`, `fabula`,
`doc`, then any other in name order (`ascribe`, `thym`).
Given a catalog, it decides which format the catalog is written in by these steps, in order. The first that applies
decides, and the reader reports which step it was: `oes`, `old`, `legacy` or `absent`.

1. **An `oes:` key decides.** If its value is a string naming a format in the registry and a major that manifest
   declares, the catalog is written in it. If its value is one of the old spellings a manifest's `declaration.old`
   lists, the catalog is written in that manifest's format, and the reader reports it as identified `old`. Anything
   else under `oes:` (an unknown name, an unknown major such as `comprise/2`, a value not spelled exactly, such as
   `comprise/01` or `' emf/1 '`, an empty value, a value that is not a string) is refused.
2. **A legacy key.** If the catalog has no `oes:` key, each manifest's `declaration.legacy` keys are tried in registry
   order. The first manifest that names a key present in the catalog (and, where it gives one, a matching value)
   claims it. Values compare as text, so `comprise: 0.1` matches the legacy value `'0.1'`.
3. **An absent default.** A manifest whose `declaration.absent` names its own declaration (Comprise's says
   `comprise/1`) claims a catalog with neither key, but only a catalog found where that manifest's `volume.catalog`
   puts it: `holotype.cosm` at the root of a folder, for Comprise. A default never claims a file at another name.
4. **Otherwise** the catalog is refused: it declares nothing the reader knows.

When a catalog carries both `oes:` and a legacy key, `oes:` decides and the legacy key is kept and ignored (Comprise's
`declaration.both: oes`).

<!-- term: old spelling -->
**Old spellings.** An **old spelling** is an `oes:` value under an earlier name of a format, which its manifest reads
and never writes: the manifest lists it in `declaration.old` (section 13.3). A format keeps its paths, so a volume
under an old spelling means exactly what it would mean under the format's own value. The fabula is the worked case.
Its manifest declares `fabula/1` and lists `emf/1` as old, so a twin written as

```yaml
oes: emf/1
id: emf/guides--close-md
```

is a fabula. The reader reports it as identified `old`; its items, paths and checks are the fabula's; its catalog id
keeps the old prefix and gives the same database name, `guides--close-md` (section 6.2); and a URI may name it either
way (section 11.3). The file keeps saying `oes: emf/1` (section 5.5).

### 5.3 Refusal

A refused catalog loads nothing. The reader returns a refusal, a value that says what the catalog declares and what the
reader knows, and never raises. For example:

```text
canon.cosm declares oes: canon/2, which this reader cannot read: this reader reads Canon as canon/1 only; nothing was
loaded
```

The checks report the refusal as one `load` error, and a viewer shows it in place of the volume.

### 5.4 Legacy forms

The core's built-ins:

| Format | Declaration | Old spellings | Also read | Absent |
|---|---|---|---|---|
| `cosm` | `oes: cosm/0` | none | `cosm: 0.2`, `cosm: 0.3`, and `opi:` with any value | refused |
| `canon` | `oes: canon/1` | none | nothing | refused |
| `fabula` | `oes: fabula/1` | `oes: emf/1`, read as a fabula whose flavour is `fabulan` (section 18.4) | nothing | refused |
| `doc` | `oes: doc/1` | none | nothing | refused |
| `thym` | `oes: thym/1` | none | nothing | refused |

The MiniCOSMs:

| Format | Declaration | Old spellings | Also read | Absent |
|---|---|---|---|---|
| `comprise` | `oes: comprise/1` | none | `comprise: 0.1`, the line in every Holotype made before Comprise OES 1 | `holotype.cosm` with no key reads as `comprise/1`, silently |
| `ascribe` | `oes: ascribe/1` | none | nothing | refused |

A legacy key and an old spelling are never errors. A reader keeps them.

### 5.5 Writing the declaration

- A writer creating a volume writes the declaration as the first key of its catalog, so a person or a tool sees it
  without parsing the file.
- A writer writes a format's own value, never an old spelling: a new fabula says `oes: fabula/1`, never `oes: emf/1`.
- A writer must not rewrite the declaration of a volume it did not create. There is no migration: a Holotype that says
  `comprise: 0.1` keeps saying it, and a twin that says `oes: emf/1` keeps saying it until its text is decompiled again
  and a new twin is written in its place (section 18.4).

### 5.6 The reserved key `macrocosm:`

A catalog or a manifest may carry `macrocosm: 0.6.0` (or an earlier `0.5.4`, `0.0.2` or `0.0.1`), after its declaration.
Readers keep the key and ignore it. It is reserved for the day the grammar itself needs a version test; until then no
reader refuses a file for what it says, and no writer is required to write it.

---

## 6. Volumes and catalogs

<!-- atem: a volume is one database, headed by its catalog -->

### 6.1 Volumes

A **volume** is one database of a format. It has one of two shapes, and the manifest's `volume` block says which.

| Shape | What it is | Its items | Formats |
|---|---|---|---|
| a folder volume | a folder with the catalog at its root and module files below it, in the places the manifest's `volume` block names | in module files, under `nodes:` (and, where a format says so, a named block such as `brand:`) | built in: `cosm` (a product tree); MiniCOSMs: `comprise` (a Holotype), `ascribe` (a holograph) |
| a single-file volume (`volume.single-file: true`) | one file: the catalog is the whole volume | under the catalog's own `nodes:` | built in: `canon` (a Canon volume's `canon.cosm`), `fabula` (a text's twin, or the fabula beside a folder of code), `doc` (one telling of a document), `thym` (a program's volume, a morph, a context, a plan, a trace or a package) |

A fabula of code describes a folder, but the fabula itself is one file beside it: the folder is its source, not its
volume.

A volume is what a URI names (section 11.3), what the checks run over, and what a renderer draws. Two volumes never
share an item: a reference between volumes is written as a URI, and the reader does not resolve it (section 9.3).

### 6.2 The catalog

The **catalog** is the file at the root of a volume that declares the format and says what the volume holds. It is
one YAML mapping.

- **The declaration** comes first (section 5).
- **The keys** a catalog may hold are the manifest's `catalog.keys`. A reader keeps every key, listed or not, and
  ignores the ones it does not understand. A key the manifest does not list is reported by the check `catalog-key` as a
  note. A writer must not invent catalog keys the manifest does not list without a new version of its format.
- **The catalog id** has the form the manifest's `catalog.id` gives: `holotype/<slug>`, `canon/<volume-slug>`,
  `fabula/<slug>`. A manifest may also list earlier forms in `catalog.id-old`, read and never written: the fabula's is
  `emf/<slug>`, so an old twin's `emf/guides--close-md` is read as it is. When the id is absent, the manifest's
  `catalog.id-absent` rule supplies it (Comprise: `holotype/<folder name>`). The id without its prefix, the current one
  or an old one, is the volume's **database name**, the second segment of its URI. A catalog with no `id` fails
  `catalog-key` where the manifest's `catalog.id` is a template, and where the manifest gives `catalog.id-absent` the
  reader supplies the id. Where a manifest gives both, the template wins: `catalog-key` reports the missing id as an
  error, and the reader still supplies the id, so the volume keeps a database name.
- **Sources.** A catalog may declare the sources its items cite (Comprise's `sources:`, with the fields the manifest's
  `catalog.source-fields` lists). Where a format checks that cited sources are declared, the check is its own.

### 6.3 The volume block

The manifest's `volume` block says where the files of a volume are (its keys are listed in section 13.3): the catalog's
file name, whether the volume is a single file, where a folder volume's parts, modules and module files are, and what
is `outside-the-model`. Files and folders outside the model sit inside the volume but are not part of it: they are not
read as module files, not checked, and skipped by a tool that copies the model elsewhere (Comprise's `people.yaml`,
`feeds/` and `scans/`; Canon's `.canon.json`). Keys a format adds for its own code (Comprise's `vendors`,
`snapshots`, `database`) are kept.

### 6.4 Parts

A format may divide a folder volume into top-level **parts**, each with its own modules. Comprise does: each concern
(*atom*) is a part, at `atoms/<concern>/`, declared in the catalog's `atoms:` list. A declared part without its folder
is a load problem; a folder under the parts' place that the catalog does not declare is a load problem.

An item belongs to exactly one part. Inside its own part an id is written bare; from another part it is written
qualified, `<part-prefix>//<id>` (section 11.1). A volume without parts (every single-file volume, and the standalone
product tree) has one implicit part, and its paths have no part segment (section 11.2).

### 6.5 Module files

In a folder volume, a **module file** is a `.cosm` file in the places the manifest names, at any depth. Each is one
mapping with one of the shapes the manifest's `module-file.shapes` lists. The two every format may use:

```yaml
nodes:                          # the items, each a mapping with a string id
  - id: O:role/Founder
    type: role
    name: Founder
```

```yaml
module: none                    # this module is empty on purpose
reason: people are never written into a file
```

- **File names are free.** No id and no path names a file; the file an item is written in is metadata. Moving an item
  to another file changes neither its id nor its path.
- **Order.** Files are read in path order, compared case-insensitively; items keep their order within a file.
- **Duplicates.** An id already loaded in the same module of the same part is a load problem; the first wins (check
  `duplicate-id`).
- **`module: none`** carries a `reason`. Without one it is a warning (check `module-none`), and the reason reads "no
  reason given".
- **An empty module** (no folder, or a folder with no items) is legal.

In a single-file volume there are no module files. Every item is in the catalog's `nodes:` list, and its module is the
letter at the start of its id.

### 6.6 What is never in a file

A format may keep some of what it describes out of its files on purpose. Comprise keeps people only in a sealed local
database beside the Holotype, and marks the kinds that live there `stored: database` in its manifest. A reader never
reads such kinds from a file, and a writer never writes them into one. The local database, where there is one, is outside
the model: the checks do not read it unless a format's own checks say so, and no export of the files includes it.

---

## 7. Items, kinds, fields

<!-- atem: items, the modules and kinds they belong to, and their fields -->

### 7.1 Items

An **item** is a row: a mapping with a string `id` and a `type`. It is written in a `nodes:` list, or in a named block
a format declares (Comprise and the product tree hold the brand under `brand:`, and read a legacy `firm:` the same
way). An entry of a `nodes:` list that is not a mapping, or has no string id, is a load problem; the rest of the file
still loads.

An item's id never changes. Its `name` is for display and may change freely.

### 7.2 Modules

A **module** is a group of kinds: a group of tables. It is named by one capital ASCII letter, and the manifest gives it
a `name` and a short `subtitle`: the fabula's `P` is *Propositions*, "what the text claims, and how it knows".

**Letters are local to a format.** The declaration says which format a volume is written in, and so which module a
letter names. `P` is Products in `comprise` and in the product tree, and Propositions in the fabula. The grammar
reserves one letter only: D is the dialectic's in every format, and a format whose manifest does not declare it
inherits the core's (section 18.6).

| Format | Modules |
|---|---|
| `cosm` (built in) | P Products |
| `canon` (built in) | V Volume |
| `fabula` (built in) | I Inspiration · L Lexicon · E Entities · K Concepts · N Intent · C Construction · R Production · P Propositions · T Transitions · X Atems |
| `doc` (built in) | S Structure · T Terms · R Reference · B Bubbles |
| `thym` (built in) | P Programs · M Morphs · C Contexts · R Runs · K Packages |
| `comprise` (MiniCOSM) | C Corporation · O Organizations · M Markets · P Products · R Representations · I Inventories · S Stacks · E Employees |
| `ascribe` (MiniCOSM) | A Affinities · B Beliefs · C Concerns · E Experiences · I Interests · O Opinions · Q Qualia · S Skills · U Understandings · Y Yearnings · F Forms |
| every format | D Dialectic, inherited from the core unless the format declares a D of its own |

### 7.3 Kinds

A **kind** is a table. It is declared under its module, with:

| Key | Holds |
|---|---|
| `refs` | the kind's reference fields: the fields the reference checks follow (section 9). An empty list says the kind has none |
| `checked` | further fields a check reads, beyond the envelope |
| `required` | the fields an item of the kind must carry (section 13.5) |
| `flavours` | in a format with flavours (the fabula's, section 18.4), the flavours whose volumes may hold the kind; the check `flavour-kind` reads it |
| `closed` | closed lists for the kind's own fields, `{<field>: [values]}`, applied to items of the kind over the manifest's `closed-lists` (section 13.3) |
| other keys | what a format's own code needs: a `level`, an exception id form (`id: 'P:<slug>'`), `stored: database`, `public: never`, a `note` |

An item's `type` must be a kind its module declares (check `type`), and must equal the kind in its id (check
`type-prefix`), except where the manifest declares an exception form (Comprise's brand, `P:<slug>`, whose id has no
kind). A manifest may map legacy kind names to current ones (Comprise reads `firm` as `brand` and `stack` as
`function`); a reader applies the map before checking and reports the legacy name as a note.

### 7.4 Fields

A **field** is a column. Every key of an item is a field.

- **Field paths.** A field inside a field is addressed by its **field path**: keys joined by `.`, list positions
  written `[n]`, counted from zero. `flow.outputs[0].to` is the `to` of the first output. The same field path addresses
  an open question (section 10) and follows `#` in a path (section 11.2).
- **Dotted reference fields** walk into lists and mappings. A kind that lists `rows.sku` as a reference field means
  the `sku` of every row.
- **Wildcard fields.** A reference field ending in `.*` names every value of a mapping (0.0.1). The fabula lists `roles.*`: every
  value under a claim's `roles:` is followed (section 9.6).
- **Unknown fields are kept, always.** A field the manifest does not declare is legal. A reader keeps it, shows it, and
  never drops it; a writer that rewrites an item keeps it.
- **Absent and `none`.** A format should read an absent field as "not yet asked", never as "nothing". Where nothing is
  the fact, the item says `none`.

---

## 8. The envelope

<!-- atem: the columns every item carries, whatever its kind -->

### 8.1 The columns every item has

The **envelope** is the set of columns every item carries, whatever its kind: the system columns of every table.
MacroCOSM's minimum envelope is nine fields.

| Field | Holds | Default check |
|---|---|---|
| `id` | the item's id (section 11.1) | `id-grammar`, `id-module`, `duplicate-id` |
| `type` | its kind | `type`, `type-prefix` |
| `name` | a label for display | `identity-min` when required |
| `summary` | one sentence saying what it is | `identity-min` when required |
| `status` | where it stands in its life | `status` |
| `visibility` | who may see it | `visibility` |
| `provenance` | how it is known, from what, how surely | `provenance` |
| `pending` | an open question about the whole item (section 10) | `pending-shape` |
| `links` | typed links to other items (section 9.4) | `ref-grammar`, `ref-unresolved`, `closed-list` |

### 8.2 Required fields

A format declares which envelope fields every item must carry, in its manifest's `envelope.required`. A required field
that is missing fails the check `identity-min`; only presence is checked, as in Comprise, so an empty value passes.

| Format | Required |
|---|---|
| `cosm` (built in) | `id type name summary owner` |
| `canon` (built in) | `id type name path` |
| `fabula` (built in) | `id type name summary provenance`; most kinds add `stance`, and some kinds fields of their own (section 18.4) |
| `doc` (built in) | `id type name summary` |
| `thym` (built in) | `id type name summary` |
| `comprise` (MiniCOSM) | `id type name summary provenance`; in P, `id type name summary owner` |
| `ascribe` (MiniCOSM) | `id type name summary provenance` |

### 8.3 Envelope fields a format adds

A format may add fields to its envelope (`envelope.fields`) and say which of them are references
(`envelope.references`). Comprise adds `owner` (a role, never a person), `since`, `until`, `mattering`, `body`, `at`,
`attributed-to`, `template`, `instances`, `counterparty`, `series` and `shared-with`, and checks `owner`, `at`,
`attributed-to`, `counterparty`, `shared-with` and `links` as references. Canon adds `path`, `parent`, `parts`,
`size`, `mtime`, `kind`, `twin`, `fabula` and `atem`. The fabula adds `span`, `salience` and `withheld`. DocOES adds
`atem`, `body`, `lines`, `order` and `chapter`, and checks `chapter` as a reference. Thym adds `made`. Ascribe adds
`span`, `form`, `of`, `parts`, `when`, `valence`, `strength` and `made`.

MacroCOSM's envelope has no `owner`. An owner is Comprise's addition, a role that answers for an item, and a format
without roles (a fabula, a file, a holograph, whose holder is its subject) has nothing to put there.

### 8.4 Status and visibility

Unless a manifest gives other lists, the closed lists are Comprise's:

| Field | Values |
|---|---|
| `status` | `active` · `dormant` · `planned` · `retired` |
| `visibility` | `public` · `internal` · `restricted` |

What an absent visibility means is the format's to say (Comprise: `internal` outside P, by level in P). Whatever it
says, these rules hold for every renderer:

- A hidden item is absent, not refused: lists leave it out, a renderer never draws it, and a reference to it from a
  visible item keeps the id and gains no name.
- An id is an address, not a secret.
- A path to a hidden item answers exactly as its id would (section 11.2).

### 8.5 Provenance

Sources or it didn't happen. `provenance` is a mapping:

| Field | Holds | Checked |
|---|---|---|
| `mode` | how it came to be known, from the closed list below | error otherwise |
| `sources` | a non-empty list of what it came from: source ids the catalog declares (Comprise), or locators in the source text (a fabula: `'close.md#L3-L7'`) | error when empty or not a list |
| `confidence` | a number from 0 to 1 | error otherwise |
| `state` | `known` (the default) · `pending` · `not-disclosed` · `stale` | error otherwise |
| other fields | what a format adds (Comprise: `synced-from`, `synced-at`, `max-age`) | as that format says |

**Modes**, Comprise's twelve: `dialectic` · `net-scan` · `system-scan` · `integration` · `structured-intake` · `manual`
· `derived` · `asserted` · `archetype` · `catalogue` · `directory` · `accounting`. `derived` is the mode every
derivation uses: an item a program made from other material, such as a fabula's item made from a text. `dialectic`
is the mode of what a person's answer wrote, through the core's dialectic (section 18.6).

An item may also carry `provenance.answered`, `{<field path>: {sources, confidence}}`: the fields an answer of the
dialectic filled in an item made some other way, each with its session and the person's confidence; and `withheld`, a
list of the field paths its subject declined to give (section 18.6.4).

`not-disclosed` is a fact, not a question: the subject declined to say. `pending` says the item stands on something not
yet confirmed.

**Identity instead of provenance.** The product tree carries COSM's identity instead of a provenance block:
`confidence` and `sources` at the top level of the item, with `owner` required. The manifest says so (Comprise's
`envelope.identity-in-P`), and the `provenance` check then reads those two fields where they are.

### 8.6 Unknown fields

Allowed, and kept. The envelope is a floor, not a ceiling.

---

## 9. References and links

<!-- atem: how one item points at another, and how a reader resolves it -->

### 9.1 What a reference is

A **reference** is an id written in a reference field: a foreign key. The reference fields are the kind's `refs`
(section 7.3) and the envelope's `references` (section 8.3). A value in a reference field takes one of these forms:

| Form | Example | Names |
|---|---|---|
| bare | `O:role/Founder` | an item in the same part |
| qualified | `atom/mozilla-org//C:ip/mozilla-trademarks` | an item in another part of the volume |
| a part | `atom/meadow` | a part (Comprise: a concern) |
| an exception form the manifest declares | `P:meadow` | Comprise's brand |
| a typed link | `{rel: depends-on, to: P:claim/meadow-closes-overnight}` | the item in its `to` |
| a sentinel | `none`, `self` | nothing, on purpose; the part itself |
| an open question | `{pending: "which entity is the licensor now?"}` | an answer still owed (section 10) |
| an address: an id, `#` and a field path | `N:audience/owners#who` | the item, and the field the path names in it (absent or open fields included) |
| a list of any of these | `parts: [V:file/readme-md, V:folder/guides]` | each of them |

A path is not a reference. Files hold ids.

### 9.2 Two ends

**Every reference must resolve.** A reference that names nothing in the volume fails the check `ref-unresolved`, an
error, unless the manifest's `references.exceptions` gives the case a lighter severity (Comprise: a vendor not yet
fetched is a warning). A value in a reference field that has none of the forms above fails `ref-grammar`.

### 9.3 Resolution

- A bare id resolves in its own part; a qualified id in the named part; a part id to the part. An address resolves as
  the id before its `#`, and its field path must parse (section 7.4); the field it names need not be present, since a
  question may be about a field nobody has filled (section 18.6).
- Resolution runs against the loaded volume, never against the disk, and never depends on who is reading.
- A URI written in a field (`oes:comprise/meadow/meadow/O/role/Founder`) is not a reference in this edition. It is kept
  as a value and not checked; resolving across volumes is reserved for a later edition.

### 9.4 Typed links

A **typed link** is a mapping `{rel: <word>, to: <id>}` in an item's `links:` list. It says how the item relates to the
target, and the `to` is checked like any reference.

```yaml
links:
  - {rel: depends-on, to: P:claim/meadow-closes-overnight}
  - {rel: defines, to: K:concept/close}
```

- `links:` may also hold bare ids: links with no relation named.
- Comprise also reads `id:` in place of `to:`. A link with neither is skipped.
- `rel` is free text unless the manifest closes it with `links.rels` (0.0.1). The fabula closes it to nine words
  (section 18.4); a `rel` outside a closed list fails `closed-list`.

### 9.5 Relations are fields

There is no syntax for a relation other than a field that holds an id. A relation's name is its field's name (`owner`,
`parent`, `defined-by`) or its typed link's `rel`. A format that needs a relation with attributes of its own (dates,
shares, sources) makes it an item: Comprise's relationships between concerns are items of the kind `C:bond`.

### 9.6 Wildcard fields and literals

In a wildcard reference field (`roles.*`), a value is checked as a reference only when it is **id-shaped**: when it
parses as an item id of a module the format declares. Any other string is a literal and is not checked:

```yaml
roles:
  actor: E:org/meadow                    # an id: checked, must resolve
  condition: only after the bank feeds arrive    # a literal: kept, not checked
```

An id-shaped value that names nothing still fails `ref-unresolved`. In a named reference field (one without `*`),
every value is checked, and a literal fails `ref-grammar`.

---

## 10. Open questions

<!-- atem: an unknown written down as a question, never as a guess -->
An **open question** (*pending*) is a value nobody has yet given, written where the value would go:

```yaml
terms: {pending: "funding amount and term are not published"}
feed: {pending: "not in FEED"}
pending: "Which entity holds the trademarks since the transfer?"
```

- **Pending beats plausible.** A writer must never guess a value. It writes the question instead.
- **The form.** `{pending: "<the question>"}` in place of any value, at any depth; or a `pending:` key on the item, for
  a question about the whole item. The question is a non-empty string; anything else fails the check `pending-shape`.
- **Who answers.** The question should be addressed to whoever can answer it. A format may say who that is by default
  (Comprise: the item's owner; a role answers for itself; otherwise "unassigned").
- **Its address.** The item's path plus `#` and the field path (`…/P/offering/mozilla-festival#economics.price`). A
  question on the whole item is addressed by the item's path alone.
- **What it does to the checks.** An open question is never an error and never fails a reference check. A format's
  own rule that needs the value reports itself *unverifiable* instead of passing or failing.
- **The report.** The checks list every open question with its item, its field path and the question (section 12.4).
- **Not the same as "not disclosed".** `provenance.state: not-disclosed` records that the subject declined to say: a
  fact, not a question.
- **Derivations.** A program that could not do its work writes a question, never a filler. When a fabula is made
  without a model, every item it writes says so: `pending: "a model has not read this passage"` (section 18.4).
- **Asking a person.** An open question is the inline form. The core's dialectic (section 18.6) can put it to a person
  and record the answer; an answer of "I don't know" leaves the open question in place, in that person's words.

---

## 11. Ids, paths, URIs

<!-- atem: how anything is addressed: an item's id, its path and its URI -->
Every item has an **id**, the primary key. Every part, module, kind, item and field has a **path**, the id respelled
as a location. Every volume and everything in it has a **URI**, the path qualified with the format and the volume.

### 11.1 Ids

```text
item-id      = module ":" kind "/" slug                 ; MacroCOSM's default form
qualified-id = part-prefix "//" item-id                 ; an item of another part (Comprise: "atom/" concern)
module       = %x41-5A                                  ; one capital letter the format declares
kind         = lower *( lower / DIGIT / "-" )           ; a kind that module declares
slug         = alnum [ *( slugch / "." ) slugch ]       ; [A-Za-z0-9]([A-Za-z0-9._@-]*[A-Za-z0-9_@-])?
alnum        = ALPHA / DIGIT
slugch       = ALPHA / DIGIT / "_" / "@" / "-"          ; a slug never ends in a dot
sentinel     = "none" / "self"
```

- **The manifest may declare other forms.** `ids.item-form` gives the format's form and `ids.item` a regular
  expression for it; `ids.brand-form` and a kind's `id:` give exceptions; `ids.qualified-form` gives the qualified form.
  Comprise's brand is `P:<slug>`, with no kind. The product tree writes ids bare, `<kind>/<slug>`, with the module left
  out (section 18.2).
- **Bare inside its own part.** An item's own id is written bare in its part's files. An id qualified with another part
  is an error (Comprise's check `id-atom`, which is its own).
- **Case is kept and significant.** `O:role/Founder` and `O:role/founder` are two items. A tool that ever used paths as
  file names on a case-insensitive file system would merge them, so such a tool must refuse the pair.
- **An id outside the slug set** (one with a slash in its slug, a colon, a `#`, a space or a non-ASCII letter) may still
  parse as an id where the format's id form allows it, but it has no path.
- **Never renamed.** The id is the key. Renaming a thing changes its `name`.

### 11.2 Paths

A path is an id respelled as a location, through the levels the manifest's `paths.levels` declares.

| Format | Levels | Item path |
|---|---|---|
| `cosm` (built in) | module, kind, item, field | `P/<kind>/<slug>` |
| `canon` (built in) | module, kind, item, field | `V/<kind>/<slug>` |
| `fabula` (built in) | module, kind, item, field | `<module>/<kind>/<slug>` |
| `doc` (built in) | module, kind, item, field | `<module>/<kind>/<slug>` |
| `thym` (built in) | module, kind, item, field | `<module>/<kind>/<slug>` |
| `comprise` (MiniCOSM) | concern, module, kind, item, field | `<concern>/<module>/<kind>/<slug>` |
| `ascribe` (MiniCOSM) | module, kind, item, field | `<module>/<kind>/<slug>` |

```text
path      = [ part "/" ] module [ "/" kind [ "/" slug [ "#" field ] ] ]    ; part present exactly when the format has parts
part-path = part                                                           ; a part alone (Comprise: a concern)
field     = key *( "." key / "[" 1*DIGIT "]" )
key       = ( ALPHA / DIGIT ) *( ALPHA / DIGIT / "_" / "-" )
```

**Properties.**

- **A respelling.** A path is computed from an id, and an id from a path, with no lookup.
- **Slug-based.** Built from slugs, which never change when an item is renamed.
- **Absolute.** In a format with parts, a path always starts with the part. There are no relative paths.
- **ASCII, and one spelling.** No colon, so a path is safe as a file name on Windows; no percent-encoding, no `..`, no
  leading or trailing slash. A path has exactly one spelling, and a reader refuses any other rather than guessing.
- **An address, never a door.** A path never touches the disk by itself. It names a row, and is resolved against the
  loaded volume. It is never joined to a folder to open a file.

**The shorter forms** name the levels above an item: `<part>`, `[<part>/]<module>`, `[<part>/]<module>/<kind>`. The
module and kind levels have no id; the path is their only name. A field follows only an item.

**Exception forms** respell through the manifest's `paths.map`. Comprise's brand `P:<slug>` has the path
`<concern>/P/brand/<slug>`, which is one-to-one because `P:brand/<slug>` is never a valid Comprise id.

**Refused, never normalized.** A reader refuses a path with: a leading or a trailing slash; an empty segment; a segment
that is `.` or `..`; percent-encoding, an encoded slash included; a backslash; whitespace, control characters or anything
outside ASCII; a colon; a segment ending in a dot; a second `#`; a module the format does not declare; a kind its module
does not declare; more segments than the format's levels allow; a segment that is a Windows reserved name (`con`,
`prn`, `aux`, `nul`, `com0` to `com9`, `lpt0` to `lpt9`), in any case, alone or before a dot (`con.txt`, `NUL.tar.gz`).

**Scope.** A path to an item the reader may not see answers exactly as its id would: nothing there, no name. A path is
never a way around visibility.

**Examples.** Each resolves: the Comprise ones on Comprise's public fixtures, the others on the complete examples in
sections 18 and 19.

| Path | Id | Names |
|---|---|---|
| `meadow` | `atom/meadow` | a concern of a Holotype |
| `meadow/P/brand/meadow` | `P:meadow` | Comprise's brand item |
| `meadow/O/role/Founder` | `O:role/Founder` | a role, case kept |
| `meadow/P/offering/ledger#flow.outputs[0].to` | `P:offering/ledger`, field `flow.outputs[0].to` | a field inside a list |
| `mozilla-foundation/P/offering/creative-futures` | `P:offering/creative-futures` | an offering |
| `P/offering/ledger` | `offering/ledger` | an offering of the product tree in 18.2 |
| `P/brand/meadow` | `meadow` | that tree's brand |
| `V/folder/guides` | `V:folder/guides` | a folder of the Canon volume in 18.3 |
| `V/file/guides--close-md#fabula.state` | `V:file/guides--close-md`, field `fabula.state` | the state of a text's fabula, its twin |
| `P/claim/close-locks-the-day` | `P:claim/close-locks-the-day` | a claim of the text's fabula in 18.4 |
| `P/claim/meadow-closes-overnight#roles.actor` | `P:claim/meadow-closes-overnight`, field `roles.actor` | a role slot |
| `X/atem/1` | `X:atem/1` | a passage atem |
| `S/section/1.1` | `S:section/1.1` | a section of the doc volume in 18.5 |
| `M/morph/plain-letter` | `M:morph/plain-letter` | a morph of the Thym volume in 18.7 |
| `A/affinity/sourdough-baking#strength` | `A:affinity/sourdough-baking`, field `strength` | a field of a holograph's node in 19.2 |

### 11.3 URIs

For use outside one volume, a path is qualified with the format and the volume's database name:

```text
uri      = "oes:" format "/" database [ "/" path ]
database = the catalog id without its prefix             ; holotype/meadow gives meadow; canon/~meadow-notes gives ~meadow-notes
```

```text
oes:comprise/meadow                                      the Holotype itself
oes:comprise/meadow/meadow/O/role/Founder                a role in it
oes:canon/meadow-handbook/V/file/guides--close-md        a file in a Canon volume
oes:canon/~meadow-notes/V/file/plan-md                   a file in a project's catalog
oes:fabula/guides--close-md/P/claim/close-locks-the-day  a claim in a text's fabula
oes:emf/guides--close-md/P/claim/close-locks-the-day     the same claim, by the old spelling
oes:doc/macrocosm-oes/S/section/18.5                      a section of this specification's doc volume
```

- **No version.** A URI carries no version, because a path keeps its meaning across every version of its format. A
  change that would alter what a path means must be a new format.
- **Old spellings.** A URI whose format segment is the name of an old spelling (section 5.2) names the same thing as
  the URI with the format's own name: `oes:emf/…` resolves exactly as `oes:fabula/…`. A writer writes the format's own
  name. An old twin whose catalog id is `emf/<slug>` has the database name `<slug>`, the same as it would have under
  `fabula/<slug>`.
- **Unique within one install.** A database name is unique among the volumes one reader knows, not in the world. A
  globally unique name, and a resolver for URIs across installs, are reserved for a later edition.
- **A private address.** A URI names a place. It opens nothing to a reader who may not see what is there.
- **In enough.** enough resolves URIs for its own volumes: `oes:canon/<volume>/…` for a Canon volume,
  `oes:canon/~<project>/…` for a project's catalog, `oes:fabula/<twin>/…` (or `oes:emf/<twin>/…`) for a fabula,
  `oes:comprise/<holotype>/<path>` for any Holotype Canon holds, and `oes:doc/<document>/…` for a doc volume.

---

## 12. Checks

<!-- atem: the checks every volume can be held to, and the report -->

### 12.1 What the checks are

The **checks** (*lint*) are the constraints of the database, run over the whole volume. The reader runs them on load,
and an implementation may offer them as a command (enough's is `lint`, run over a volume). They never raise and never
stop at the first problem. Each problem names its
check, its item (or its file), the field path where it applies, and a plain message.

MacroCOSM defines a fixed vocabulary of **generic checks** that any reader can run on any volume from its manifest
alone. A format may have checks of its own, written in its own code (Comprise's product-tree checks and its fourteen
rules). The generic reader does not run those, and says so (section 12.3).

### 12.2 The generic checks

| Check | Default severity | Catches |
|---|---|---|
| `load` | error | a file that does not parse, is not a mapping, or uses a forbidden construct; a `nodes:` entry with no string id; a volume layout that does not fit (a declared part with no folder, an undeclared folder); a refused declaration |
| `duplicate-id` | error | an id already loaded in the same module of the same part; the first wins |
| `id-grammar` | error | an id that does not parse in the format's id form |
| `id-module` | error | an id whose module the format does not declare, or, in a folder volume, an id whose module is not the module of the folder it is written in |
| `type` | error | a missing `type`, or a kind the item's module does not declare |
| `type-prefix` | error | an id whose kind disagrees with its `type`, outside the exception forms the manifest declares |
| `identity-min` | error | a field the manifest's `envelope.required` lists that the item does not carry; only presence is checked, as in Comprise, so an empty value passes |
| `provenance` | error | a provenance block missing where required, or malformed: a mode outside the list, sources empty or not a list, a confidence outside 0 to 1, a state outside the list |
| `status` | error | a `status` outside the status list |
| `visibility` | error | a `visibility` outside the visibility list |
| `ref-grammar` | error | a value in a named reference field that is not an id of a known form, a sentinel, a typed link or an open question |
| `ref-unresolved` | error | a reference that names nothing in the volume, unless the manifest's `references.exceptions` gives the case another severity |
| `closed-list` | error | a value outside its closed list, for any field the manifest's `closed-lists` names, and for a link's `rel` when `links.rels` closes it |
| `pending-shape` | warning | an open question whose question is empty or not a string |
| `module-none` | warning | a `module: none` with no `reason` |
| `catalog-key` | error | a catalog key the manifest's `catalog.keys` does not list (a note); a catalog id that fits neither `catalog.id` nor a form `catalog.id-old` lists, since the id names the database in every URI; a value outside the closed list the manifest gives a catalog key (section 13.5) |
| `flavour` | error | in a format with flavours, a catalog `flavour` outside the manifest's `catalog.flavour` list; an absent `flavour` reads as the manifest's `catalog.flavour-absent` |
| `flavour-kind` | error | an item whose kind lists `flavours` that do not include the catalog's flavour (section 7.3) |

### 12.3 Which checks run

- **`load` always runs.** A volume that could not be read cannot be checked.
- **The rest run when the manifest selects them**, by id, in `checks.envelope` (and `checks.load`, which Comprise uses
  for `load`). A duplicate id is always reported; under `duplicate-id` when the manifest selects it, under `load`
  otherwise, which is how Comprise reports it.
- **An unknown check id** in a manifest is kept and listed in the report as *not run*, with no error. Comprise's
  manifest selects checks the generic reader does not know (`id-atom`, `source-undeclared`, `owner`, `vendor-missing`,
  `bond`, `aim` and others); they are listed as not run, and a viewer says that Comprise's own rules need Comprise.
- **A format's own checks** are named in the manifest's `checks.own`. Given as a list of ids, each is listed in the
  report as *not run* by a reader that does not run it, so a person sees what the generic checks left unchecked; given
  as a string, it is prose, kept and shown as it is.
- **The core's own checks.** The dialectic's three, `question-about`, `question-shape` and `session-declared`
  (section 18.6.8), run on every volume that holds an item of module D. A reader that does not run them lists them as
  not run.
- **Severities.** A check reports at its default severity unless the manifest's optional `checks.severity` mapping
  (`{<check id>: error | warning | note}`, 0.0.1) gives another. The mapping sets the severity of a check's findings
  except those that are fixed: a problem found while loading (`load`, and a duplicate id) is always an error, and two
  findings are always notes, an unlisted catalog key (`catalog-key`) and a legacy kind read under its new name (`type`).
  Outside the fixed findings the mapping may raise a default severity or lower it: Ascribe's manifest, for one, holds
  its own `no-pii` check to a warning in a holograph.

### 12.4 The report

```text
report  = { errors, warnings, notes, pending, not-run, ok }
problem = { check, item (or file), field, message }
pending = { item, field, question }
ok      = true when there are no errors
```

`ok` is the verdict the generic checks give. A format may give further verdicts of its own (Comprise's "may this
version be signed?", section 15).

### 12.5 Checks and writes

A format may say that every write goes through its checks and that a write which adds an error is undone. Comprise
does. MacroCOSM does not require it: a reader may report problems after a write and keep the write. The dialectic holds its
own writes to the rule: a write `settle` would make that adds an error is not made (section 18.6.4). enough reports the
generic checks when a `.cosm` file is saved and never refuses the save.

### 12.6 What the generic checks do not verify

What a domain means. The generic checks say a volume is well formed and closed: every item is in a declared table,
every required column is filled, every closed value is in its list, every reference has two ends. They do not say that
a product tree balances, that a claim is true, or that a role is lawfully held. Those are a format's own checks, or a
person's judgement. Ids that differ only in case, and slugs outside the path set, are not checked in this edition.

---

## 13. The manifest

<!-- atem: the file declaring a format, so a reader needs no new code -->

### 13.1 What it is

A **manifest** is the machine-readable declaration of a format, a built-in or a MiniCOSM: what a program needs to read,
check and render its volumes. It is one `.cosm` file, outside every volume. A volume names its format by its
declaration and never embeds the manifest.

The word has a second sense in Comprise: the list of files and hashes in a saved version, a backup or a published
concern. Both mean "the list of everything aboard". They never meet on screen.

### 13.2 Its format

A manifest is written in the COSM YAML subset and starts with its own declaration, `manifest: minicosm/0`: the
manifest format, version 0. The value keeps the spelling it was first written with, for built-ins and MiniCOSMs alike,
so that every manifest already written still loads. Words that YAML 1.1 reads as booleans are quoted in a manifest, so
that a reader using any YAML loader reads it the same way.

### 13.3 The keys

These are the keys of Comprise's manifest, read generically, with the 0.0.1 additions marked, and the keys the core's
manifests add. A reader keeps every key, including the ones it does not use.

| Key | Holds | The generic reader uses it for |
|---|---|---|
| `manifest` | `minicosm/0` | knowing the file is a manifest |
| `name`, `title`, `version` | the format's name (the declaration's first half), its display title, its major version | the registry, the declaration |
| `core` | `true` for a built-in of the core; absent or `false` for a MiniCOSM. Comprise's and Ascribe's manifests never carry it | the registry's two lists (section 13.6) |
| `summary`, `spec`, `reference`, `predecessor` | one line; where its prose and its code are; what it replaced | display |
| `declaration` | `key` (`oes`), `value` (`<name>/<major>`), `old` (a list of earlier `oes:` values this manifest reads and never writes), `absent` (a declaration, or `refuse`), `legacy` (a list of `{key, value, reads-as}`), `both`, `unknown` (`refuse`) | identifying catalogs (section 5.2) |
| `format` | the extension, the subset, the forbidden constructs, the booleans, the encoding, the newlines | documentation; the reader's rules are section 4's |
| `volume` | `catalog`, `single-file` (0.0.1), the part and module places, `module-files`, `outside-the-model` | finding the files (section 6.3) |
| `catalog` | `keys`, `id`, `id-old` (earlier id forms, read and never written), `id-absent`, `source-fields`, and keys a format adds (Canon's `scope`; the fabula's `flavour` and `flavour-absent`, and the folder fields of a fabula of code) | `catalog-key`, `flavour`, the database name |
| `module-file` | `shapes`, `items` (0.0.1), `duplicate-id`, and format-specific keys | reading module files |
| `ids` | `item` (a regular expression), `item-form`, `brand-form`, `qualified-form`, the part's form, `inside-own-concern` | `id-grammar`, resolution |
| `paths` | `form`, `levels`, `segments` (one regular expression per level), `map`, `qualified`, `case`, `refused` | paths and URIs (section 11) |
| `envelope` | `fields`, `references`, `required` (and variants such as Comprise's `required-in-P`), `status`, `visibility`, `visibility-absent`, `provenance` (`fields`, `modes`, `states`, `state-default`), `open-question`, `sentinels`, `unknown-fields` | the envelope checks |
| `references` | `forms`, `dotted-fields`, `unresolved`, `exceptions`; an address, an id with `#` and a field path, is read in any reference field (section 9.1) | `ref-grammar`, `ref-unresolved` |
| `links` | `rels`, a closed list of typed-link relations (0.0.1) | `closed-list` on `links[].rel` |
| `closed-lists` | a mapping from a field name to its closed list of values, applied wherever that field appears (0.0.1) | `closed-list` |
| `modules` | for each letter: `name`, `subtitle`, `note`, and `kinds`, each with `refs`, `required` (0.0.1), `checked`, `flavours` (the flavours that may hold the kind), `closed` (closed lists for the kind's own fields, applied to its items over `closed-lists`) and format-specific keys | `type`, `type-prefix`, the reference checks, `closed-list`, `flavour-kind`, the viewer's rail |
| `checks` | `envelope` (the generic check ids that apply), `load`, `severity` (0.0.1), `own` (the format's own checks: a list of ids, or prose), and other keys of the format's own (`products`, `rules`, `equilibrium` …) | selecting checks; listing the own checks as not run (section 12.3) |
| `open-questions` | the form, who answers, the field path | the pending list |
| `dialectic` | the opening questions a format's volumes are asked, as banks of questions by module, kind or field, with who answers them; Ascribe's older shape, a list of questions per module, is read as one bank named after the manifest (section 18.6) | the dialectic's questions |
| `renderers` | a list of `{id, makes, code, status}`, and, from 0.0.1, `{id, lens}` | lenses (section 14) |
| `extension` | what a MicroCOSM may and may not do on top of this MiniCOSM | documentation (section 17) |
| `macrocosm` | reserved (section 5.6) | nothing |
| anything else | format-specific declarations (Comprise's `relationships`, `aims`, `versions`, `public-projection`) | kept; read only by that format's own code |

### 13.4 Read generically

A generic reader needs only the keys above to load, check and draw a volume. Everything it does not understand it keeps.
A manifest is never rewritten by a reader. The Comprise manifest that ships with enough is a byte copy of Comprise's own,
refreshed from it and never edited in enough.

A manifest may also carry a `moves:` list: the moves its format declares for Thym, the language that composes them
(https://thym.cosmoes.org/, where the block has a part of its own). Each entry names a move, what it takes and gives,
its modifiers, whether it asks the model, the contract its output is held to, its rules-mode stand-in and its reference
code. The generic reader keeps the block as one more key it does not use; the Thym compiler reads it, from every
manifest in the registry, when it resolves a program's names. A format whose manifest is kept by another
implementation, and copied into the registry unedited, declares its moves in a sidecar beside the manifest,
`<name>.moves.cosm`, a mapping
`{moves-of: <format>/<major>, moves: [...]}`: Comprise's is `comprise.moves.cosm`. A sidecar is not a manifest, and
the registry passes it by; where a manifest and a sidecar both declare moves, the manifest's list wins.

**The core's module D.** The dialectic's module (section 18.6) is declared once, by the core, in a file of modules that
ships with the manifests, `core.modules.cosm`, a mapping `{modules-of: core, modules: {D: …}, closed: …}` whose
`closed:` is keyed by kind, then by field. Like a sidecar it is not a manifest, and the registry passes it by. A reader merges its module D, with the closed lists of D's
own kinds, into every manifest that declares no module D, and adds `D` to a manifest's module segment where
`paths.segments.module` lists the letters. A manifest that declares module D itself keeps its declaration, which is the
dialectic's. Comprise's manifest, a byte copy, inherits D this way without being edited.

### 13.5 What 0.0.1 adds

Optional keys new in 0.0.1: `volume.single-file`, `renderers[].lens`, `links.rels`, `closed-lists`,
`checks.severity`, Canon's `catalog.scope`, and the reserved `macrocosm`. A reader that does not know
them keeps them and loses nothing it relied on before. The Changes appendix (section 21) records each.

Four more optional keys, which the reference implementation also reads:

- `module-file.items`: where a module file's items are. A list of entries `{key, kind, one, module}`, of which only `key`
  is required. `key` is the top-level key of the file that holds items: a list of items, or, with `one: true`, a single
  item. `kind` is the kind given to an item written without a `type` (a single item always takes it). `module` limits
  the entry to one module. Without the list the reader reads the list `module-file.shapes` names (`nodes:`) and
  Comprise's root item of the product tree. The cosm manifest lists `brand`, `firm`, `nodes`, `roles`, `externals` and
  `contracts`.
- A kind's own `required`, under `modules.<letter>.kinds.<kind>`: the fields an item of that kind must carry. It replaces
  the envelope's `required-in-<letter>` and `required` for that kind, and `identity-min` checks it. The cosm manifest's
  `role`, `external` and `contract` require only `id`.
- `catalog.<key>`, where `<key>` is listed in `catalog.keys` and the manifest gives it a list: the closed list of values
  that catalog key may hold. Canon's `scope` (`volume`, `project`) and `status` (`complete`, `ingesting`, `failed`) are
  two. A value outside the list fails `catalog-key`; an open question passes.
- A lens of a kind other than `mermaid`, under `renderers[].lens.kind`: DocOES declares a `short` and a `table`. A reader
  keeps it in the manifest for the code that renders it, and neither lists it among a volume's lenses nor draws it
  (section 14.3).

The core adds further optional keys, read the same way: `core`; `declaration.old`; `catalog.id-old`; a kind's
`flavours` and `closed`; `checks.own` as a list; `dialectic`; and the core's module D (section 13.4). A reader that
does not know them keeps them. Without them it refuses an old spelling and leaves module D undeclared, and every file it
read before still reads.

### 13.6 The registry

A reader loads every `*.manifest.cosm` in its manifest folders into a **registry**. enough ships its manifests
read-only; a folder for a person's own manifests is reserved for a later edition. The registry order is `comprise`,
`cosm`, `canon`, `fabula`, `doc`, then any other in name order (`ascribe`, then `thym`). A manifest that does not load,
or that names a format already in the registry, is skipped and reported; the first one wins. The registry keeps two
lists, the built-ins (the manifests that say `core: true`) and the MiniCOSMs (every other); which list a
manifest is in changes nothing about the order in which catalogs are identified. The registry is what step 1 of
section 5.2 compares a declaration and its old spellings against, and what a refusal lists as known, each format with
its old spellings after it.

---

## 14. Renderers and lenses

<!-- atem: how a volume is drawn: renderers, the text tree and Mermaid lenses -->

### 14.1 Renderers

A **renderer** turns a volume into another form. Renderers only read. Each applies the reader's scope first: a hidden
item is absent from everything it makes (section 8.4).

A format's own renderers are its own (Comprise's 3D Overview, Field Guide, export and isotype). MacroCOSM defines
three that any reader can make from a manifest alone: the **text tree**, the **Mermaid lenses**, and the item cards of a
structured viewer.

### 14.2 The text tree

`to_text_tree(volume)` writes the volume as indented text: the catalog's declaration, id and name; then each part, when
the volume has parts; each module by letter and name; and under each module its items, each as its name, its id and
kind, and its summary. Items nest by `parts` and `parent`: a part under the item that lists it, an item under its
`parent`. There is no line per kind and no per-kind count. An item that holds open questions is marked `(N open)`, N
being how many. The reader's command line prints it, and readvisor tools hand it to a model as context.

### 14.3 Lenses

A **lens** is a Mermaid rendering of a volume from one angle, declared in the manifest:

```yaml
renderers:
  - {id: tree, lens: {kind: mermaid, diagram: flowchart, include: [V], edges: [parent], shape: {folder: '[[ ]]', file: '[ ]', article: '([ ])'}}}
  - {id: claims, lens: {kind: mermaid, diagram: flowchart, include: [E, K, P], edges: ['roles.*', links], class-by: stance}}
```

| Lens key | Holds | Default |
|---|---|---|
| `kind` | `mermaid`, the only kind the generic renderer draws; a format may declare another (DocOES's `short` and `table`), which a reader keeps and neither lists among a volume's lenses nor draws | required |
| `diagram` | `flowchart` or `mindmap` | `flowchart` |
| `include` | the module letters to draw | every module |
| `edges` | reference fields (dotted and wildcard fields allowed), `links` (every typed link) or one link `rel` (only the typed links with that `rel`), and `parts` and `parent`, to draw as edges | every reference field, `links`, `parts` and `parent` |
| `shape` | a mapping from a kind to a Mermaid shape, written as its bracket pair with a space for the label (the pairs are listed below) | the kind's own shape (listed below); `'[ ]'`, a rectangle, for a kind with none |
| `class-by` | a field whose value names a class on each node, so a stylesheet can colour nodes by it (the fabula: `stance`) | none |

**Shapes.** The reader accepts these bracket pairs: `'[ ]'`, `'( )'`, `'([ ])'`, `'[[ ]]'`, `'[( )]'`, `'(( ))'`,
`'((( )))'`, `'> ]'`, `'{ }'`, `'{{ }}'`, `'[/ /]'`, `'[\ \]'`, `'[/ \]'` and `'[\ /]'`. A pair not in the list is drawn
as `'[ ]'`, and a value that is not a pair is ignored in favour of the kind's default. A kind with no `shape` entry takes
its default: the product tree's, which is `brand` `'(( ))'`, `suite` `'{{ }}'`, `offering` `'([ ])'`, `function`
`'[[ ]]'`, `product` `'[ ]'`, `service` `'( )'`, `role` `'> ]'` and `external` `'[/ /]'`; Canon's, which is `folder`
`'[[ ]]'`, `file` `'[ ]'` and `article` `'([ ])'`; and `'[ ]'` for any other kind. A mindmap draws only `'[ ]'`, `'( )'`,
`'(( ))'` and `'{{ }}'`: any other pair becomes `'( )'` if it opens with a parenthesis and `'[ ]'` if not.

**Generic lenses.** Every volume has the lens `map`, even when its manifest declares lenses of its own, unless one of
them is named `map`: a flowchart of every module, with every reference field, every typed link, and every `parts` and
`parent` as an edge. A Holotype is drawn this way, since Comprise's manifest declares its own renderers and no lens. A
volume whose items carry `parts` or `parent` also has the lens `tree`, unless the manifest declares one: a flowchart of
the items that are joined to another by `parts` or `parent`, with those as its only edges. A reader lists a volume's
lenses in this order: the manifest's, then `map`, then `tree`.

### 14.4 How the generic renderer draws

`to_mermaid(volume, lens)` returns the Mermaid text and a `node_map`.

**A flowchart:**

- each included module is a `subgraph`, titled with the module's letter and name;
- each visible item of an included module is a node, labelled with its `name` (its id when it has none), shaped by its
  kind, and given the class `class-by` names, when there is one. The lens's `shape` for the kind decides the shape;
  without one, the kind's default does: the product tree's for `brand`, `suite`, `offering`, `function`, `product`,
  `service`, `role` and `external`, Canon's for `folder`, `file` and `article`, and a rectangle for any other kind;
- each value of a listed reference field that resolves to a drawn item is an edge, labelled with the field's name; each
  typed link, when the lens lists `links` or that link's `rel`, is an edge labelled with its `rel`; each entry of a
  `parts` list and each `parent`, when listed, is an edge with no label, drawn from the parent to the part; references
  to items outside the drawing are left out;
- `node_map` maps every Mermaid node id to its item's path, so a viewer can open the item a person clicks. A `click`
  line is written for each node only when the caller asks (`clicks=True`), because an item path is not a file path.

**A mindmap** draws the same items as a tree under the volume's name, with a branch per module and a leaf per item, and
draws no edges.

**A large volume.** A drawing holds at most `max_nodes` items, 200 unless the caller says otherwise. Past that, the items
left over in each subgraph (in a mindmap, under each module) collapse into one node labelled "… N more", N being how
many; an edge to a collapsed item ends at that node, and in `node_map` that node maps to no item.

**A local graph.** Given an item (`around`: its key, id or path) and a `depth` (1 unless the caller says otherwise),
`to_mermaid` draws only that item and the items the lens's edges reach from it or to it within `depth` steps, as one
flowchart with no subgraphs, the item itself in the class `focus`.

**A volume from text.** `load_volume_text(text, filename=…)` reads one catalog held in memory, an example of this
specification say, exactly as `load_volume` reads a file of that name, so it can be checked and drawn where it stands
without writing anything to disk.

**Well formed.** Node ids are Mermaid-safe, unique in the diagram, and the same for the same volume every time; labels
are quoted, so no label can end a subgraph or break a line; subgraphs balance.

### 14.5 Lenses that ship

The core's built-ins first, then the MiniCOSMs.

| Format | Lens | Draws |
|---|---|---|
| `cosm` | `tree` | the product tree, from the brand to its units, joined by `parts` |
| `canon` | `tree` | the volume's folders, files and articles, joined by `parent` |
| `cosm`, `canon` | `map` (the generic lens) | every module, every reference field and typed link, `parts` and `parent` |
| `fabula` | `claims` | entities, concepts and claims, joined by role slots and typed links, coloured by stance |
| `fabula` | `map` | the fabula at a glance: its inspiration, lexicon, entities, concepts, intent, construction, production, claims and events, as a mindmap |
| `doc` | `manual` | the readable manual: the document compiled as told, its short density (a short, not a drawing) |
| `doc` | `map` | the document's sections and terms, as a mindmap |
| `doc` | `graph` | what an item mentions, defines and exemplifies, and what mentions it |
| `doc` | `inventory` | every item as one row: its id, kind, version, anchor and atem (a table, not a drawing) |
| `doc` | `tree` (the generic lens) | the document's sections, joined by `parts` and `parent` |
| `thym` | `program` | the program as written, compiled back from its items: its short density (a short, not a drawing) |
| `thym` | `plan` | a plan's nodes in the order they run, joined by what each runs after |
| `thym` | `trace` | every record of a run as one row (a table, not a drawing) |
| `comprise` | `map` (the generic lens) | every module, every reference field and typed link, `parts` and `parent` |
| `comprise` | `tree` (the generic lens) | the items joined by `parts` or `parent` |
| `ascribe` | `self` | the self at a glance: a branch for each of the ten modules and a leaf for each node, as a mindmap |
| `ascribe` | `graph` | every typed link between the nodes and the forms, coloured by valence |
| `ascribe` | `timeline` | every node that carries a `when`, one row each, in order (a table, not a drawing) |

In the reader's order, a volume has these lenses: a cosm tree, `tree` and `map`; a Canon volume, `tree` and `map`; a
fabula, `claims` and `map`; a doc volume, `map`, `graph` and `tree`; a Thym volume, `plan` and `map`; a Holotype, `map`
and `tree` (the `tree` only when its items carry `parts` or `parent`); a holograph, `self`, `graph` and `map`. The
fabula's own `map`, the mindmap, takes the place of the generic one, and so does DocOES's; its `manual` and `inventory`
are drawn by its own renderers, as Ascribe's `timeline` and Thym's `program` and `trace` are by theirs.
---

## 15. Versions and signatures (by reference)

<!-- atem: saved versions and signatures, defined in Comprise OES -->
*Defined here; specified in Comprise OES, in its section on versions (https://comprise.cosmoes.org/).*

- **A saved version** is an immutable copy of a volume's model files at a moment, with a manifest that holds every
  file's hash, the checks' verdict and its own hash. Taking one changes nothing.
- **A signed version** is a saved version the checks allowed, whose files still match their hashes, signed by the
  holders of the roles that govern the volume.
- **The diff** between two saved versions is item by item, with the field paths that moved.

Saving and signing are Comprise's; the generic reader does neither, and treats a Holotype's `snapshots/` folder as
outside the model.

Three other things carry versions, and none of them is a saved version: a format carries its major in the
declaration (`comprise/1`, section 5); the manifest format is `minicosm/0` (section 13.2); the grammar is 0.6.0, in the
reserved `macrocosm:` key (section 5.6). A path and a URI carry no version (section 11.3).

---

## 16. The private/public split (by reference)

<!-- atem: a private volume and its public projection: two documents, not a setting -->
*Defined here; specified in Comprise OES, in its section on the private/public split (https://comprise.cosmoes.org/).*

The split is two documents, not one document with a setting.

- **Holotype** — the complete, private description of one subject, kept by the subject, on the subject's machine.
- **isotype** — a small public projection of the Holotype: a separate document with fixed fields, each derived from the
  Holotype by one rule, default-deny, released and signed by the subject. A field added to the model later never flows
  into it by itself.

The words come from taxonomy, where a holotype is the one specimen that defines a species and an isotype is a duplicate
of it. In MacroCOSM they name the two halves of the split in every MiniCOSM, and both MiniCOSMs have one, since each
describes a subject who keeps it private:

| MiniCOSM | The private volume | Its public projection | How the projection is made |
|---|---|---|---|
| `comprise` | the Holotype | the isotype | by a fixed schema, each field derived by one rule (Comprise OES, its section on the private/public split) |
| `ascribe` | the holograph | the isograph, which the holder shares in private; the allograph, which the holder lists in the Allograph Registry | by a Thym program the holder runs over the holograph (Ascribe, https://ascribe.cosmoes.org/, on projections) |

A MiniCOSM with a split declares its public projection in its manifest (Comprise's and Ascribe's
`public-projection`), and the rules of the projection are its own.

The core's built-ins have no split. They declare no public projection: a product tree, a Canon volume, a fabula, a doc
volume and Thym's volumes are the owner's own files, and no reader sends them anywhere.

---

## 17. MicroCOSMs

<!-- atem: one organization's additions to a MiniCOSM, reserved for a later edition -->
*Described in the map of the family at https://cosmoes.org/ and in the `extension:` block of Comprise's manifest;
reserved for a later edition.*

A MicroCOSM is one organization's extension of a MiniCOSM.

**It may add:** kinds, in any module; fields, on any kind; checks, including stricter versions of the MiniCOSM's own;
renderers.

**It may never:** remove anything; rename anything; loosen anything (a closed list, a required field, a check's
severity); change what a path or an id means; weaken the split, by adding to a public projection or opening anything by
default.

What a MicroCOSM adds carries its name, `<microcosm>.<kind>` and `<microcosm>.<field>`, so that a later version of the
MiniCOSM can never collide with it. A volume written with a MicroCOSM is still a valid volume of its MiniCOSM: a reader
that does not know the MicroCOSM keeps its fields and ignores its checks.

How a volume says that it uses a MicroCOSM, and how a reader loads one, are reserved for a later edition.

---

## 18. The core

<!-- atem: what MacroCOSM holds built in: five formats, the densities, the dialectic -->
The core (section 3) is specified here: its registry and the model its built-ins share (section 18.1), each of the
five built-ins (sections 18.2 to 18.5, and 18.7 for Thym's volumes, which Thym's own text specifies), and the
dialectic, the one way any volume asks a person what its source means (section 18.6).

### 18.1 The core and its registry

<!-- atem: the five built-ins, their declarations, and the model they share -->
**What is built in.** Every reader ships the five manifests of the built-ins, each saying `core: true`, and the file of
modules that holds the dialectic's module D (section 13.4). They are read like any other manifest. Being built in means
that a reader always has them, and that reading their volumes needs no specification beyond this one and Thym's.

| Format | Declaration | Enumerates | Volume | Catalog | Modules | Section |
|---|---|---|---|---|---|---|
| `cosm` | `oes: cosm/0`; in the files, `cosm: 0.2` · `0.3`, `opi:` | one whole's product tree, outside any Holotype | a folder of `.cosm` files | the file holding `brand:` | P | 18.2 |
| `canon` | `oes: canon/1` | Canon, the home file system: a volume or a project, its folders, files and articles, and what has been derived from them | one file | `canon.cosm` | V | 18.3 |
| `fabula` | `oes: fabula/1`; old spelling `oes: emf/1` | one input decompiled, a text, a poem or a folder of code: everything found in it or derived from it, item by item | one file, beside its input | `<text>.fabulan.cosm`, `<text>.fabulap.cosm`, `<folder>.fabulac.cosm`; an older twin's `<text>.cosm` | I L E K N C R P T X | 18.4 |
| `doc` | `oes: doc/1` | one document: its sections, terms, examples and decisions, joined to the reference | one file per telling, built at runtime | `<doc>.<lang>.doc.cosm` | S T R B | 18.5 |
| `thym` | `oes: thym/1` | Thym's programs, morphs, contexts, plans, traces and packages, and a run's snapshots of the folders it took | one file, one of seven kinds | `<name>.thym.cosm`, `<name>.morph.cosm` … | P M C R K | 18.7 |

Every format, built in or not, has the dialectic's module D: the core's, merged in where its manifest does not
declare it (sections 13.4 and 18.6).

**Old spellings.** The core has one: `oes: emf/1`, which reads forever as a fabula whose flavour is `fabulan`, with
its catalog id `emf/<slug>` and its URIs `oes:emf/…` (sections 5.2, 6.2 and 11.3). A writer never writes it, and a
reader never rewrites it: a twin keeps it until its text is decompiled again (section 18.4). Where a manifest, a
program or a trace names the check `emf-checks`, it names the fabula's checks, `fabula-checks`, by their old name.
Where a program or a trace names the move `tell`, it names `entail` by its earlier spelling (Thym, its section 6.3).

<!-- term: decompile -->
**The model.** To **decompile** is to take an input apart into its fabula: everything that can be found in it or
derived from it, enumerated item by item. To compile is to make a short of a fabula, its items said again in an
order. The plainest thing that can be said of either is an atem. These are three densities of one meaning: the fabula is the material, a
short is one arrangement of it, and an atem is a reduction, with a hermeneutic shape of its own (section 18.3.5). For
code each density has a form of its own:

| Density | Prose and verse | Code |
|---|---|---|
| the input | a text: an essay, a story, a poem, a song | a folder of source |
| fabula | a `fabulan` (narrative and non-fiction prose) or a `fabulap` (poetry, metered verse, song lyrics) | a `fabulac`: the program's specification, item by item |
| short | a short: an entailment of the fabula in markdown, its items in an order (section 18.4.4) | a `cshort`: source code rebuilt from the fabulac, to be read and never run |
| atem | the atem: a line, with its focus, push and pull | the atem, as for any fabula; and a `catem`, a text saying everything a user can do with the program, at the depth `line`, `overview` or `manual` |

The flavour is a property of the fabula, named in its catalog; one format, `fabula/1`, holds all three (section 18.4).
A running program is outside the model: nothing in the core runs a cshort, imports it or installs it.

<!-- term: entailment -->
An **entailment** is the step that expands meaning by reducing data, and it is also what that step makes. The whole
entails what is made from it: an input entails its fabula, a fabula a short, and a short an atem; a codebase or an
application entails its fabulac, and a fabulac a cshort or a catem; a Holotype entails its isotype and its paratype, and a
holograph its isograph and its allograph. What is made says nothing its whole does not hold. It says it at a smaller size, or in another order or
voice. An entailment made by rule, a projection (section 16), holds by construction. An entailment made by a model holds
only because the contract's checks hold it: `no-invention` (it names nothing its whole lacks), `stance-kept` (it says
no claim more strongly than its whole does) and `coverage` (each of its sentences traces to items of its whole), as
Thym (https://thym.cosmoes.org/), its section 7.3, states them. Decompiling and compiling are both entailments; the
move `entail` makes one by a model, and `project` makes one by rule.

**The work is done by Thym's moves.** `derive` decompiles and `entail` compiles; a fabula of code is built in stages,
each one atomic run, and a job may resume between them (section 18.4.7); the dialectic's moves `question`, `record` and
`settle` ask a person and fold the answers in (section 18.6). The moves are declared in the manifests (section 13.4)
and specified in Thym (https://thym.cosmoes.org/), its sections 6.3 and 20. DocOES's byte-exact compile is a different
act, which gives a document back from its own volume (section 18.5).

**Models.** A fabula records which model made it: the model's own id, its route (`local`, a model on the person's own
machine, or `cloud`, a model reached through a broker), and for a cloud model its provider, once for each run that wrote
into the volume (section 18.4.1). The model is chosen for each run: the same programs run on a local model at its best
effort or on a cloud model through a broker, and nothing reaches a cloud model that the person did not choose for that
run: a run that names no route runs on the local model. A run made without a model is in rules mode and says so. With
its agent off, an implementation refuses every model, local or cloud (Thym, its section 19).

### 18.2 cosm: the product tree

<!-- atem: one whole's product tree, as COSM 0.2 and 0.3 wrote it -->
**What it enumerates.** One whole's product tree, as COSM 0.2 and 0.3 wrote it outside any Holotype: the brand, and
below it suites, offerings, functions, products and services, each answering the same nine questions (identity, flow,
substrate, rules, principles, economics, vocabulary, affect, mattering). The context-ontology skill writes trees in this
form. The built-in exists so that they open, check and draw beside everything else.

**Its declaration.** None of its own in the files: a tree's files say `cosm: 0.2` or `cosm: 0.3` (or `opi:`, the oldest
form), and each reads as `cosm/0`. `oes: cosm/0` is accepted too. enough writes no standalone trees.

**Its volume.** A folder of `.cosm` files. One holds `brand:` (COSM 0.2 said `firm:`, which reads the same), with the
tree's `roles:`, `externals:` and `contracts:`; any file may hold `nodes:`; an optional `doc.cosm` holds `reading:`,
`history:`, `findings:` and `sources:`, which carry the document rather than the model. The convention is three files,
`brand.cosm` (or `firm.cosm`), `nodes.cosm` and `doc.cosm`; one file holding all of it is a complete tree too.

**Its module and kinds.** One module, P.

| Kind | Level | What it is |
|---|---|---|
| `brand` | L4 | the whole: legal anchor, brand-wide rules, principles, vocabulary and mattering; it does no work of its own |
| `suite` | L3 | a portfolio of offerings sold or managed together; may nest |
| `offering` | L2 | a market-facing promise: audience, contract, price, service level |
| `function` | L1 | a cluster of units that share infrastructure and a job; may nest |
| `product` | L0 | a unit that does the work, as an artifact |
| `service` | L0 | a unit that does the work, as an activity |

Legacy kinds read as current ones: `firm` as `brand`, `stack` as `function`.

- **Ids are bare.** `offering/ledger`, `service/reconcile`; the brand's id is its slug alone (`meadow`). A reader treats
  them as P items: `offering/ledger` has the path `P/offering/ledger`, and the brand `P/brand/<slug>`.
- **The brand's kind is its block.** The item under `brand:` (or `firm:`) is the brand; a reader sets its `type` to
  `brand`.
- **Roles and externals are reference targets, not items.** `role/<Name>` names an entry of `roles:`, and `ext/<slug>`
  an entry of `externals:`. A reference to either resolves when the entry is declared.
- **Identity.** Every item carries `id`, `type`, `name`, `summary` and `owner` (a role), with `confidence` and `sources`
  at its top level. Its sources should be declared in `sources:`.
- **The reference fields** are the ones the tree's own grammar follows: `parts`, `owner`, `flow.inputs.from`,
  `flow.outputs.to` and `substrate.depends-on` (dotted fields, section 7.4), and a role's `governs` and `escalates-to`.

The tree's own checks (its levels, its flows, the seven conditions of equilibrium) belong to the context-ontology skill
and to Comprise; enough runs the generic checks only. A product-tree file taken out of a Holotype
(`atoms/<concern>/P/brand.cosm`) also says `cosm: 0.3`. Opened on its own it reads as a `cosm/0` tree whose references
outside P do not resolve; open the Holotype instead.

**A complete example.** A small tree in one file:

```cosm
cosm: 0.3

brand:
  id: meadow
  name: Meadow Software
  kind: company
  summary: Bookkeeping for small restaurants.
  owner: role/Founder
  confidence: 0.9
  sources: [session-1]
  parts: [offering/ledger]

roles:
  - {id: role/Founder, name: Founder}
  - {id: role/Support-Lead, name: Support Lead, governs: [service/reconcile], escalates-to: role/Founder}

externals:
  - {id: ext/banks, name: Bank feed providers, kind: vendor}
  - {id: ext/restaurants, name: Independent restaurants, kind: market}

nodes:
  - id: offering/ledger
    type: offering
    name: Meadow Ledger
    summary: Daily reconciled books with a one-page morning summary.
    owner: role/Founder
    confidence: 0.9
    sources: [session-1]
    parts: [service/reconcile]
    flow:
      outputs:
        - {resource: morning-summary, to: ext/restaurants, unit: 1/day/customer}
    economics:
      price: {model: flat, value: 49, unit: USD/month}
    mattering:
      to-the-whole: Without the ledger there is no company.
      weight: critical

  - id: service/reconcile
    type: service
    name: Reconcile
    summary: Matches every bank line to an entry overnight and locks the day.
    owner: role/Support-Lead
    confidence: 0.9
    sources: [session-1]
    flow:
      inputs:
        - {resource: transactions, from: ext/banks, unit: lines/day}
      outputs:
        - {resource: morning-summary, to: offering/ledger, unit: 1/day/customer}
    substrate:
      depends-on: [ext/banks]

sources:
  - {id: session-1, page: "Interview with the Founder, 2026-10-12", supports: the whole tree}
```

### 18.3 canon: Canon, the home file system

<!-- atem: a Canon volume or project: its files and their derivations -->
**What it enumerates.** A person's home file system, and what has been made from what it holds.

<!-- term: Canon -->
Canon is MacroCOSM's home file system: the volumes a person keeps, the file manager that browses them, and the
derivations that turn their texts into fabulas and atems. enough's library is its reference implementation, and the
names below that are enough's are given as its own. A **Canon volume** is a top-level folder of the home file
system. Its catalog enumerates what the volume holds (folders, files, saved articles) and what has been derived from
each file: its markdown twin, its fabula, its atem. The same built-in enumerates a project's files (section 18.3.4).

**Its declaration.** `oes: canon/1`. There is no legacy form, and a catalog without the key is refused.

**Its volume.** One file, `canon.cosm`, at the root of the volume's folder (`volume.single-file: true`).

- enough writes it whenever it reconciles the volume, and only enough writes it. A write to it from the editor or from
  an agent's tool is refused ("change the volume's files instead"), and a change made by any other program is
  overwritten at the next reconcile. It is visible in listings, marked as the catalog.
- `.canon.json` beside it holds the volume's fast-changing metadata (origin, ingest progress, fingerprint) and is
  outside the model.

#### 18.3.1 The catalog

| Key | Holds |
|---|---|
| `oes` | `canon/1` |
| `macrocosm` | reserved (section 5.6) |
| `id` | `canon/<volume-slug>`; for a project, `canon/~<project-slug>`. A volume's name never holds `~` |
| `name` | the volume's folder name; for a project, the project's name |
| `scope` | `volume` or `project`; absent reads as `volume` |
| `origin` | where a volume came from, as Canon's ingest recorded it: `{type, value, depth}`, `type` being `folder` (made empty), `path`, `url` or `wikisink` |
| `status` | a volume's ingest state: `complete`, `ingesting` or `failed` |
| `created`, `updated` | when a volume was made and last reconciled, as timestamps; never in a project's catalog |
| `counts` | `{folders, files, articles, twins, atems}`: the folder, file and article items; the files with a fabula; the files with an atem |
| `nodes` | the items |

#### 18.3.2 The module and its kinds

One module, V (Volume): *what the volume holds*.

| Kind | What it is | Its own fields |
|---|---|---|
| `folder` | a folder of the volume | `parts`; `holotype: true` when the folder holds a `holotype.cosm` |
| `file` | a file | `size`, `mtime`, `kind`, `twin`, `fabula`, `atem`, `short_of`, `shorts` |
| `article` | a saved article: a folder holding an `article.html` and its assets | `title`, `source` |

| Field | Holds |
|---|---|
| `path` | the real path inside the volume (or the project), relative, with `/` between folders, exactly as on disk. Required on every item |
| `parent` | the folder item that holds it; absent at the root. A reference |
| `parts` | a folder's items, in listing order. A reference |
| `size` | the size in bytes; never in a project's catalog |
| `mtime` | the modification time, when a writer records it; never in a project's catalog |
| `kind` | the file's format, in the word Canon's listings use (`markdown`, `text`, `pdf`, `html`, `image`, `cosm` …) |
| `twin` | the file's markdown twin, `{path, state}`, its state one of `fresh`, `edited`, `stale`, `conflict` |
| `fabula` | the file's fabula, its twin, `{path, state}`, its state `fresh` or `stale` (section 18.4.1). A catalog written before this edition names the field `emf`, its old spelling: a reader reads `emf` as `fabula`, and a writer writes `fabula` |
| `atem` | `{line}`: the file's atem line, copied from its fabula so a listing can show it without opening the twin |
| `short_of` | on a short (section 18.4.4), the path of the text it is a short of, when that text is beside it |
| `shorts` | on a text, the paths of the shorts beside it, in listing order, which is the order they were written |
| `title`, `source` | an article's title, and the address it was saved from |

**Required:** `id`, `type`, `name`, `path`. **Checks:** `load`, `duplicate-id`, `id-grammar`, `id-module`, `type`,
`identity-min`, `ref-unresolved`.

**What is never an item.** The catalog itself, `.canon.json`, a markdown twin (it appears as `twin:` on its original),
and a text's fabula (it appears as `fabula:` on its text). This matches what Canon's listings show: twins hide behind
the files they belong to. A short is the opposite: an ordinary `file` item, the person's to read and edit, which nothing hides;
its `short_of` and its text's `shorts` are all that mark it. A fabula with no sibling input, under either spelling of
its declaration, is an ordinary `file` item of kind `cosm`. A folder holding a
`holotype.cosm` is one `folder` item with `holotype: true`; the catalog does not enumerate its contents, since the
Holotype is a volume of its own and opens in the cosm viewer.

#### 18.3.3 Ids

An item's id is `V:<kind>/<slug>`, and its slug is its `path`, respelled: each `/` becomes `--`, each `.` becomes `-`,
the result is lowercased, and any character outside `a-z`, `0-9` and `-` becomes `-`. A hyphen left at either end is
trimmed. When two paths of one volume would give the same slug, each of them takes `-` and the first six hex digits of
the sha256 of its path as a suffix. `guides/close.md` is `V:file/guides--close-md`. The `path` field keeps the real
name, so nothing is lost; the lens's `node_map` is built from `path`.

The volume's own slug, in its catalog id, follows the same rule applied to its name.

#### 18.3.4 The project catalog

A project gets a catalog too: `rness/canon.cosm`, with `scope: project`.

- **What it enumerates.** Exactly what the project's file tree shows, minus `rness/`, which is enough's own machinery
  and holds the catalog itself. Dotfiles, ignored folders, and markdown twins with their asset folders stay out, as they
  stay out of the tree. Fabulas hide behind their sources. A folder holding a `holotype.cosm` is one item, not
  recursed.
- **Its id** is `canon/~<project-slug>`, the project's name slugged; its URI is `oes:canon/~<project-slug>/<path>`.
- **Structure only.** A project's catalog holds no `size`, no `mtime`, no timestamps, and no twin states: its `twin`
  and `fabula` entries carry the `path` alone, and a viewer works out the state when it shows one. The catalog changes only
  when files are added, removed or renamed, or when twins and atems appear, go or change, so a project kept in version
  control sees no churn from ordinary edits.
- **A cap.** At most 5,000 items. Past the cap, the folders not yet enumerated are listed without their contents, each
  with its `counts` and `pending: "too many files to enumerate here; open the folder in Canon"`.
- **When it is written.** When the project opens, when Canon reconciles the project's pane, when the catalog is read
  through the cosm viewer, and after any derivation in the project. It is written only when its bytes would change, and
  never from the file tree's own refresh.
- **Write-refused** like a volume's catalog.

How a project's catalog and a Canon volume's catalog of the same folder relate, when a project is copied into Canon, is
reserved for a later edition.

#### 18.3.5 Atems

An **atem** is the tightest fair, full, plain-English reduction of a text or of a passage of one. It has four parts.

| Part | What it is |
|---|---|
| **the line** | one sentence of 15 to 25 words that says what the whole says. *Fair*: the author would accept it. *Full*: nothing the text depends on is missing. *Plain*: everyday words, no term the text did not need. In prose, "the atem" means the line |
| **focus** | at most two sentences: what is happening in the text, the thing its author directs the reader's attention to |
| **push** | one sentence: what the author wants the reader to take away, believe or do |
| **pull** | one sentence: what the reader should actually take away: the usable point, with any hidden assumption, any opinion stated as fact, or any dependency the text leans on named plainly |

Push is the author's side and pull is the reader's. They agree when a text is honest and complete; where they differ, the
difference is the most useful thing an atem shows.

**Three densities of one meaning: fabula · short (SHORT) · atem.** A text's fabula holds its meaning item by item
(section 18.4); a SHORT, which the fabula entails, says it again as prose, in an order (section 18.4.4); an atem says
it in one line. The fabula is the material and a short is one arrangement of it. The atem is neither: it is a reduction, with a hermeneutic shape
of its own in push and pull. A fabula of code has the same four-part atem, and its catem says at a chosen depth what a
user can do with the program (sections 18.1 and 18.4.7).

- **Where an atem lives.** In the text's fabula. A file's atem is the twin's `atem:` block (section 18.4). Asking for
  the atem alone makes a minimal twin, `completeness: atem` with `nodes: []`. A passage's atem is shown to the person
  first; when they pin it, it is appended to the twin as an item `X:atem/<n>` with the passage's `span`. Canon copies a
  file's atem line onto the file's item.
- **Only on request.** An atem is made when a person asks (a click, a menu, a selection) or a readvisor's tool asks.
  Imports, ingests, listings and reconciles never make one.
- **Without a model,** enough writes a labelled scaffold: the line is the passage's first sentence, cut to 25 words; the
  focus is its first two sentences; push and pull are open questions, `{pending: "a model has not read this passage"}`;
  the twin records `derived.mode: rules`, and the card says "scaffold, no model".

#### 18.3.6 Examples

A Canon volume's catalog:

```cosm
oes: canon/1
macrocosm: 0.0.1
id: canon/meadow-handbook
name: meadow-handbook
origin: {type: path, value: ~/Documents/meadow-handbook, depth: 2}
status: complete
counts: {folders: 2, files: 3, articles: 1, twins: 1, atems: 1}
nodes:
  - id: V:file/readme-md
    type: file
    name: README.md
    path: README.md
    size: 640
    kind: markdown
  - id: V:folder/guides
    type: folder
    name: guides
    path: guides
    parts: [V:file/guides--close-md, V:file/guides--payroll-pdf]
  - id: V:file/guides--close-md
    type: file
    name: close.md
    path: guides/close.md
    parent: V:folder/guides
    size: 494
    kind: markdown
    fabula: {path: guides/close.md.fabulan.cosm, state: fresh}
    atem: {line: "Meadow closes each customer's books overnight once the bank feeds arrive, locks the day, and retries a failed close before anyone opens the summary."}
  - id: V:file/guides--payroll-pdf
    type: file
    name: payroll.pdf
    path: guides/payroll.pdf
    parent: V:folder/guides
    size: 182044
    kind: pdf
    twin: {path: guides/payroll.pdf.md, state: fresh}
  - id: V:folder/articles
    type: folder
    name: articles
    path: articles
    parts: [V:article/articles--double-entry-bookkeeping]
  - id: V:article/articles--double-entry-bookkeeping
    type: article
    name: double-entry-bookkeeping
    path: articles/double-entry-bookkeeping
    parent: V:folder/articles
    title: Double-entry bookkeeping
    source: https://en.wikipedia.org/wiki/Double-entry_bookkeeping
```

A project's catalog. The text `plan.md` has been edited since its twin was made, so its twin is stale, but the catalog
does not say so: a project's catalog records structure only.

```cosm
oes: canon/1
id: canon/~meadow-notes
name: meadow notes
scope: project
counts: {folders: 1, files: 2, articles: 0, twins: 2, atems: 2}
nodes:
  - id: V:file/plan-md
    type: file
    name: plan.md
    path: plan.md
    kind: markdown
    fabula: {path: plan.md.fabulan.cosm}
    atem: {line: "The plan moves Meadow's support hours earlier so that a failed overnight close is caught and explained before owners open for the day."}
  - id: V:folder/research
    type: folder
    name: research
    path: research
    parts: [V:file/research--interviews-txt]
  - id: V:file/research--interviews-txt
    type: file
    name: interviews.txt
    path: research/interviews.txt
    parent: V:folder/research
    kind: text
    fabula: {path: research/interviews.txt.fabulan.cosm}
    atem: {line: "Owners of six restaurants in Portland were interviewed in September 2026 about how and when they read their books."}
```

### 18.4 fabula: the fabula

<!-- atem: one input decompiled into everything it holds, item by item -->
**What it enumerates.** One input, a text, a poem or a folder of source code, taken apart into everything found in it
or derived from it.

<!-- term: fabula -->
A **fabula** enumerates all the inspiration, meaning, intent, construction, production and assertions that can be found
in an input or derived from it: what the work came from; the words it leans on, the particular things and people it
names and the ideas it uses; what it sets out to do, for whom, and what it chose; how it is built; who made it, with
what, and how it changed; what it claims, how it can be read, and what happens in it, in order; and its atems. A fabula
is not a summary. It is the input taken apart into items that can be checked, drawn, compared and compiled into the shorts
it entails. A text is what a person reads; its fabula is what the text holds, enumerated. Section 18.4.4 says where the
word comes from.

**Decompile, compile, atem.** The fabula sits in the middle of a chain of entailments (section 18.1): its input
entails it, and it entails its shorts and its atem:

- **decompiling** an input makes its fabula;
- **compiling** a fabula makes a short, an entailment of it (section 18.4.4), and for code a cshort, source rebuilt
  from it (section 18.4.7);
- an **atem** says it most plainly (section 18.3.5), and for code a catem says at depth everything a user can do
  (section 18.4.7).

In a Thym program the two acts are the moves `derive` and `entail` (Thym (https://thym.cosmoes.org/), its section 6; for
a folder of code, its section 20).

**Three flavours.** One format serves three kinds of input. A fabula's flavour says which, in the catalog's `flavour`
key, and every module and kind of section 18.4.2 says which flavours may hold it.

<!-- term: flavour -->
A fabula's **flavour** is the kind of input it is the fabula of, from a closed list of three: `fabulan`, `fabulap` and
`fabulac`. A fabula that names no flavour is a fabulan.

<!-- term: fabulan -->
A **fabulan** is the fabula of narrative or non-fiction prose: an essay, a guide, a story, a report, a page of notes.

<!-- term: fabulap -->
A **fabulap** is the fabula of poetry, metered verse or song lyrics. It adds the lines, the metre, the rhymes and the
form, and lets several readings of one line stand side by side (section 18.4.6).

<!-- term: fabulac -->
A **fabulac** is the fabula of code: a folder of source, enumerated as the specification of the program it holds
(section 18.4.7).

**Its declaration.** `oes: fabula/1`. The fabula is one of the built-ins of the core (section 18.1), and its manifest
ships with every reader. There is no legacy form, and a catalog without the key is refused. The fabula was first
published under the declaration `oes: emf/1`. That value is an old spelling of `fabula/1`: a reader identifies it as a
fabula (section 5.2), reports that it read an old spelling, and reads the file as a fabulan, since a file of that
spelling never names a flavour. A writer writes `fabula/1` and never `emf/1`, and a reader never rewrites a declaration
it did not write: a file that declares `oes: emf/1` keeps saying so until its text is decompiled again.

<!-- term: twin -->
**Its volume.** One file. A text's fabula kept beside it is the text's **twin**, named by adding the flavour and `.cosm`
to the text's whole name: `close.md` and `close.md.fabulan.cosm`, a poem `rose.txt` and `rose.txt.fabulap.cosm`. A
folder's fabulac sits beside the folder: `tool/` and `tool.fabulac.cosm`. A twin's `source:` names its input.

- **A fabula is identified by its declaration, never by its file name.** A twin named as the first edition named it,
  the text's whole name with `.cosm` added (`close.md.cosm`), is read forever.
- **An old-named twin decompiled again.** When a text whose twin has the old name is decompiled again, the new twin is
  written under the new name, the old twin's `shorts:` list is carried over into it, and the old file is then removed.
  This is the same act as refreshing a twin in place, under the new name. Nothing else ever renames or removes a twin.
- **Two names at once.** If both `close.md.fabulan.cosm` and `close.md.cosm` exist, the one named with its flavour is
  the twin, and the old one is listed as an ordinary file with a note saying so. A text may have one twin per flavour.
- **A standalone fabula** has no `source:` and is named `<name>.fabulan.cosm`, `<name>.fabulap.cosm` or
  `<name>.fabulac.cosm`; an old standalone `<name>.cosm` reads. It is read the same way as a twin.
- **One file, however large.** A fabulac is one file whatever the size of its folder. A fabula kept as a volume of
  several files, for a very large repository, is reserved for a later edition.
- **The flavour of a text** is the person's choice when the text is decompiled. An implementation may suggest
  `fabulap` for a text that looks like verse (short lines, stanza breaks, no headings) and `fabulan` otherwise.

#### 18.4.1 The catalog

The catalog's keys, in this order:

| Key | Flavours | Holds |
|---|---|---|
| `oes` | all | `fabula/1`; `emf/1` is read and never written |
| `macrocosm` | all | reserved (section 5.6) |
| `flavour` | all | `fabulan`, `fabulap` or `fabulac`; absent, `fabulan` |
| `id` | all | `fabula/<slug>`, the slug being the input's path in its volume or project, respelled by the Canon rule (section 18.3.3): the twin of `guides/close.md` is `fabula/guides--close-md`, and the fabulac of the folder `tool/` is `fabula/tool`. A twin written as `emf/<slug>` is read as it is |
| `name` | all | the text's title, or its file name when it has none; a folder's name |
| `source` | all | the input, in one of the two forms below; absent for a standalone fabula |
| `derived` | all | how the fabula was made (below) |
| `atem` | all | the whole input's atem: `{line, focus, push, pull}` (section 18.3.5). Every fabula has one, a fabulac too |
| `shorts` | all | the shorts compiled from the fabula, one entry per compile, appended (section 18.4.4); absent until the first |
| `catems` | fabulac | the catems compiled from the fabulac, one entry per compile, appended (section 18.4.7); absent until the first |
| `nodes` | all | the items |

**`source`**, in one of two forms:

| Form | Fields | Example |
|---|---|---|
| a text (fabulan, fabulap) | `path`, the text's file name relative to the fabula; `sha256`; `size`; `mtime_ns`. `kind: text` may be written and is the default | `{path: close.md, sha256: d297…1b14, size: 494, mtime_ns: 1792660324518000000}` |
| a folder (fabulac only) | `path`, the folder relative to the fabula, ending `/`; `kind: folder`; `language` (`python` in this edition); `files`, `bytes` and `skipped`, the counts of the files read; `tree`, the tree digest (below); `commit`, the hash of the commit checked out, when the folder is a clean git clone, and absent otherwise; `origin`, the clone's remote address, when known; `licence`, the licence's standard short identifier (`MIT`), else the first line of the licence file, else `{pending: "…"}` | `{path: days/, kind: folder, language: python, files: 3, bytes: 2988, skipped: 0, tree: c9c7…0900, licence: MIT}` |

A fabulac's source is always a folder; a fabulan's or a fabulap's is always a text.

**`derived`** says how the fabula was made. Its single keys describe the last run that derived the fabula from its
source; a run that only settles the dialectic's answers (section 18.6.4) changes none of them:

| Field | Holds | When |
|---|---|---|
| `at` | when, as a timestamp in UTC | always |
| `by` | at whose request: `person`, or the readvisor's name | always |
| `model` | the model's own id: for a local model, the name the implementation knows it by; for a cloud model, the provider's resolved id, of the form `vendor/model` | model mode |
| `route` | `local` or `cloud` | model mode |
| `provider` | the service that carried a cloud request, by its name | cloud only |
| `program` | the name of the Thym program that built the fabula, as its `program` line gives it (`raise-the-questions`); one file may hold several programs | when a Thym program did |
| `run` | the trace id of that program's run | with `program` |
| `mode` | `model` or `rules` | always |
| `completeness` | `full`; `atem`, a fabula that holds the atem and nothing else; or `outline`, a rules-only skeleton: a fabulac's (section 18.4.7), or a fabulap's, its lines, sounds and form with nothing read for meaning (section 18.4.6) | always |
| `chunks` | how many chunks the text was read in; for a fabulac, how many files a model read | always |
| `dropped` | how many items a derivation dropped because it could not repair them | when any were |
| `runs` | one entry per run that wrote into the fabula, in order, a settle run included: `{program, run, at, model, route, provider}`, `program` naming the program as above, the last three absent for a run made by rules alone | when a Thym program wrote into the fabula |

A fabula built in several runs, as a fabulac is, says through `runs` which model made each part of it; a resumed build
appends its runs. The single keys repeat the last entry that derived the fabula, so a reader that knows nothing of
`runs` still finds the model that made it.

**`shorts` and `catems` entries.**

| List | Entry | Notes |
|---|---|---|
| `shorts`, a prose or verse short | `{path, at, by, mode, order}`, and `route` when a model wrote it | `order` is `told` or `weight`; the path is `<text-stem>.short-<YYYY-MM-DD-HHMM>.md` (section 18.4.4) |
| `shorts`, a cshort | `{path, at, by, mode, order: code, route, language, files}` | `path` is the folder `<name>.cshort-<YYYY-MM-DD-HHMM>/`, with its `/`, taking `-2`, `-3` on a collision; `language` is the cshort's own; `files`, how many files it holds besides `CSHORT.md` (section 18.4.7) |
| `catems` | `{path, at, by, mode, route, depth}` | `depth` is `line`, `overview` or `manual`; the path is `<name>.catem-<YYYY-MM-DD-HHMM>.md`, taking `-2`, `-3` on a collision as shorts do (section 18.4.7) |

**Fresh and stale, for a text.** A twin is `fresh` while its text's size and modification time match the twin's
`source`, and, when they differ, while the text's sha256 still matches. Otherwise it is `stale`. A text with no twin is
`absent`. A stale twin is kept and shown with its state; it is refreshed only when someone asks.

**Fresh and stale, for a folder.** A fabulac is `fresh` while the tree digest computed again equals `source.tree`, and
`stale` otherwise; it is `absent` when its folder is gone, and the fabulac is kept. There is no shortcut by
modification time. The **tree digest** is computed exactly as follows, so that two implementations agree to the byte:

| Step | Rule |
|---|---|
| root | the folder `source.path` names, relative to the fabulac's file |
| walk | every regular file below the root, at any depth; symbolic links, to files or to folders, are never followed and never read |
| folders skipped whole, by name, at any depth | version control: `.git` `.hg` `.svn` `.bzr` `_darcs` `CVS`; environments: `.venv` `venv` `__pypackages__` `.tox` `.nox` `node_modules`, and any folder that holds a `pyvenv.cfg`; caches: `__pycache__` `.pytest_cache` `.mypy_cache` `.ruff_cache` `.hypothesis` `.ipynb_checkpoints` `.cache` `htmlcov`; build output: `build` `dist` `.eggs`, and any name ending `.egg-info`; any name containing `.cshort-` |
| files skipped | the names `.DS_Store` `Thumbs.db` `desktop.ini` `.coverage`; the endings `.pyc` `.pyo` `.pyd` `.so` `.dylib` `.dll` `.o` `.a` `.class`; names ending `.fabulac.cosm` or containing `.catem-`; a file over 1,000,000 bytes; a file with a NUL byte in its first 8,192 bytes; a file that does not decode as UTF-8, read strictly, as a whole |
| per file | the sha256 of the file's raw bytes as they are: line endings, encoding and Unicode form are left unchanged |
| order | ascending by the UTF-8 bytes of the relative path, written with `/`, as the file system spells it |
| digest | the sha256 of the concatenation, for each file in order, of: the relative path in UTF-8, one NUL byte, the file's sha256 as 64 lowercase hexadecimal digits, one LF byte. Written as 64 lowercase hexadecimal digits, with no prefix |
| counts | `files`, the files read; `bytes`, the sum of their sizes; `skipped`, the files skipped (a folder skipped whole counts nothing) |
| not used | `.gitignore` and every other ignore file; the git index; modification times |

#### 18.4.2 The modules and their kinds

Ten modules hold a fabula's items, grouped by the facet of the work each enumerates, and every fabula may also carry the
core's dialectic module D (section 18.6).

| Letter | Module | Facet | What it holds | Kinds |
|---|---|---|---|---|
| I | Inspiration | inspiration | what the work came from | `influence`, `allusion`, `occasion` |
| L | Lexicon | meaning | the words the work leans on | `term` |
| E | Entities | meaning | the particular things and people named | `person`, `org`, `place`, `work`, `thing` |
| K | Concepts | meaning | the ideas and universals the work uses | `concept` |
| N | Intent | intent | what the work sets out to do, for whom, and what it chose | `aim`, `audience`, `use`, `requirement`, `decision`, `exclusion` |
| C | Construction | construction | how the work is built | prose and verse: `part`, `device`, `voice`; verse only: `line`, `metre`, `rhyme`, `form`; code: `file`, `component`, `interface`, `structure`, `behaviour`, `dependency`, `setting` |
| R | Production | production | who made the work, with what, and how it changed | `maker`, `change`, `phase`, `release`, `means`, `licence` |
| P | Propositions | assertions | what the work claims, how it can be read, and what it must do | `claim`, `reading`, `case` |
| T | Transitions | assertions | what happens, in order | `event` |
| X | Atems | | the tight reductions of passages | `atem` |
| D | Dialectic | | what was asked about the work, and what was answered (section 18.6) | `question`, `session` |

The modules L, E, K and X, and the kinds `P:claim` and `T:event`, are unchanged since the fabula's first edition, in
their fields and their closed lists, so that every file that declares `oes: emf/1` is a valid fabulan.

**Every kind.** In the table, n is fabulan, p fabulap and c fabulac. A reference field is checked like every reference
(section 9); `roles.*` is the wildcard of section 9.6: a slot holds an item's id when the participant is an item of the
fabula, and a literal otherwise.

| Kind | What it holds | Flavours | Reference fields | Also checked |
|---|---|---|---|---|
| `I:influence` | something outside the work that shaped it: a work, a person, a tradition, a tool | n p c | `roles.*` | `stance`, `how` |
| `I:allusion` | a reference the text makes to another work without saying so | n p | `roles.*` | `stance`, `cue` |
| `I:occasion` | what the work was made for or prompted by: an event, a request, a need, a date | n p c | `roles.*` | `stance`, `when` |
| `L:term` | a word the work leans on | n p c | | `feed`, `sense` |
| `E:person` `E:org` `E:place` `E:work` `E:thing` | a particular named thing or person | n p c | | |
| `K:concept` | an idea or universal the work uses | n p c | `defined-by` | |
| `N:aim` | what the work sets out to do | n p c | `roles.*` | `stance`, `measure` |
| `N:audience` | whom it is for | n p c | | `stance`, `who`, `needs` |
| `N:use` | one thing a user can do with the program, end to end | c | `for`, `via` | `stance`, `steps`, `gets` |
| `N:requirement` | what the program must, should or may do or be | c | `met-by`, `checked-by` | `stance`, `force` |
| `N:decision` | a choice made between options | n p c | `by`, `changed-in` | `stance`, `chose`, `over`, `because` |
| `N:exclusion` | what the work deliberately does not do or cover | n p c | | `stance`, `horizon`, `because` |
| `C:part` | a division of the text | n p | `of` | `stance`, `division`, `number`, `heading` |
| `C:device` | a figure or technique at a place | n p | `where` | `stance`, `figure`, `effect`, `cue`, `senses`, `intended` |
| `C:voice` | who speaks, to whom, how | n p | `roles.*` | `stance`, `perspective`, `tone` |
| `C:line` | one line of verse | p | `part`, `metre` | `stance`, `number`, `text`, `stresses`, `syllables`, `rhyme`, `ending` |
| `C:metre` | a metre that governs lines | p | `lines`, `departures.line` | `stance`, `foot`, `feet`, `basis` |
| `C:rhyme` | one rhyme sound shared by lines | p | `lines` | `stance`, `scheme`, `sound`, `quality`, `placement` |
| `C:form` | the form a poem keeps: a sonnet, a villanelle, a ballad stanza, free verse | p | `parts`, `metre`, `departures.at` | `stance`, `form`, `scheme`, `rules`, `intended` |
| `C:file` | one file of the tree | c | `component` | `stance`, `path`, `language`, `holds`, `length`, `sha256`, `entry` |
| `C:component` | a package, module or group of files with one responsibility | c | `files`, `of`, `exposes`, `uses` | `stance`, `does` |
| `C:interface` | something another program or a person calls, types, reads or writes | c | `defined-in` | `stance`, `surface`, `signature`, `takes`, `gives`, `raises`, `exported` |
| `C:structure` | a shape of data: a class of records, a file format's record, a table | c | `defined-in` | `stance`, `shape`, `fields`, `invariants` |
| `C:behaviour` | what happens, for which input | c | `of` | `stance`, `when`, `does`, `edges`, `errors`, `intended` |
| `C:dependency` | something outside the tree that the code needs | c | `used-by` | `stance`, `package`, `version`, `scope`, `needed-for`, `licence` |
| `C:setting` | a value a user or an installer can change, or a constant that shapes behaviour | c | `read-by` | `stance`, `key`, `set-in`, `default`, `means` |
| `R:maker` | who made the work, and in what capacity | n p c | `who` | `stance`, `capacity` |
| `R:change` | one change: a commit, an entry in a change log, a revision between drafts | n p c | `by`, `touches`, `release`, `phase` | `stance`, `at`, `nature`, `because`, `commit` |
| `R:phase` | an episode: changes that belong together | n p c | `changes` | `stance`, `began`, `ended` |
| `R:release` | a version made public: a tag, an edition, a publication | n p c | `changes` | `stance`, `version`, `at`, `tag`, `venue` |
| `R:means` | a tool, method or material of production | n p c | | `stance`, `what`, `used-for`, `version` |
| `R:licence` | the terms on which the work may be used | n p c | | `stance`, `identifier`, `file`, `holder`, `year`, `first-line` |
| `P:claim` | what the work claims, and how the text knows it | n p c | `roles.*` | `stance`, `salience`, `span` |
| `P:reading` | an interpretation the text supports and does not state | n p | `of`, `grounds.of` | `stance`, `whose`, `grounds`, `intended`, `span` |
| `P:case` | an example: what is given and what is expected | c | `of` | `stance`, `given`, `expect`, `span` |
| `T:event` | what happens; in code, one step of what happens when the program is used | n p c | `agent`, `patient`, `before`, `after` | `when`, `span` |
| `X:atem` | the atem of a passage | n p c | `of` | `line`, `focus`, `push`, `pull`, `span` |
| `D:question` `D:session` | the dialectic's kinds (section 18.6) | n p c | as section 18.6 says | as section 18.6 says |

A kind outside the catalog's flavour is an error (`flavour-kind`, section 18.4.8): a fabulan holds no `C:line`, a
fabulap no `C:file`.

**The common rules.**

- **Required.** Every item carries the envelope's `id`, `type`, `name`, `summary` and `provenance`. Every item of the
  modules I, N, C and R, and every item of P, also carries `stance`; a few kinds require a field of their own, shown in
  bold below. The fabula adds `span`, `salience` and `withheld` to the envelope.
- **`stance`** is from the closed list of six of section 18.4.3. On a claim it is the text's own: how the text knows
  what it claims. On every other kind it is the fabula's: how the item is known. Confidence stays in `provenance`.
- **`span`** points an item back at its input: in a text `{lines: "12-18"}`, or `{start, end}` when lines do not serve
  (section 18.4.3); in a fabulac `{file: <path relative to source.path>, lines: "12-40"}`, read against
  `source.commit` when it is set and against `source.tree` otherwise.
- **An unknown** is `{pending: "…"}` (section 10), never a guess.

**The fields of the new kinds.** Shapes: *text* a string; *ref* an item's id, checked; *refs* a list of them; *lit* a
literal; *integer*, *bool*, *date*; a list in square brackets is closed. A bold field is required.

| Kind | Fields |
|---|---|
| `I:influence` | `roles.*`: `source` (an E item, or a literal) and `on` (the item it shaped, or a literal); `how` *text*, what was taken |
| `I:allusion` | `roles.*`: `to` (an `E:work`, a literal, or a question) and `at` (a `C:line` or `C:part`); `cue` *text*, the words that carry it, at most 60 characters |
| `I:occasion` | `roles.*`: `event`, `place`, `for`; `when` *lit* or *date* |
| `N:aim` | `measure` *text*, how one would know the aim is met; `roles.*`: `for` (an `N:audience`) |
| `N:audience` | `who` *text*; `needs` *text*, what they come with, and for |
| `N:use` | `for` *ref* `N:audience`; `via` *refs* `C:interface`; `steps`, a list of *text*, what is typed or done; `gets` *text*, the outcome |
| `N:requirement` | **`force`** [`must` `should` `may`]; `met-by` *refs* (`C:behaviour`, `C:interface`, `C:dependency`); `checked-by` *refs* `P:case` |
| `N:decision` | **`chose`** *text*; `over`, a list of `{option, because}`, what was not chosen and why; `because` *text*; `by` *ref* (an `R:maker` or the maker's E item); `changed-in` *refs* `R:change` |
| `N:exclusion` | `horizon` [`never` `later`]; `because` *text* |
| `C:part` | **`division`** [`chapter` `section` `paragraph` `scene` `list` `quotation` `stanza` `verse` `chorus` `refrain` `bridge` `other`]; `number` *integer*, its place among its siblings, from 1; `of` *ref* `C:part`, the part it sits in; `heading` *text* |
| `C:device` | **`figure`** *text*, an open word (`apostrophe`, `metaphor`, `symbol`, `image`, `alliteration`, `anaphora`, `refrain`, `caesura`, `turn`, `hook`, `irony`, `personification`, `appeal to authority` …); `where` *refs* (`C:line`, `C:part`, `L:term`, `P:claim`); `effect` *text*; `cue` *text*, the words that carry it, at most 60 characters; `senses`, for an image, a list from [`sight` `hearing` `touch` `taste` `smell` `movement`]; `intended` *bool*, whether the author meant it, absent until asked |
| `C:voice` | `roles.*`: `speaker`, `addressee`, `listener`; `perspective` [`first` `second` `third` `mixed`]; `tone` *text* |
| `C:line` | **`number`** *integer*, counted from 1 over the whole poem; `text`, the line as written (section 18.4.6 says when it is written); `part` *ref* `C:part`; `metre` *ref* `C:metre`; `stresses` *text* (`x` unstressed, `/` stressed, `\|` between feet); `syllables` *integer*; `rhyme` *text*, the line's letter in the scheme; `ending` [`stopped` `run-on`] |
| `C:metre` | `foot` [`iamb` `trochee` `anapaest` `dactyl` `spondee` `amphibrach` `mixed` `none`]; `feet` *integer* or *text* (`"2-3"`); `basis` [`accentual-syllabic` `accentual` `syllabic` `quantitative` `free`]; `lines` *refs* `C:line`; `departures`, a list of `{line, what}` |
| `C:rhyme` | `scheme` *text*, the letter; `sound` *text*; `lines` *refs* `C:line`; `quality` [`full` `slant` `eye` `identical`]; `placement` [`end` `internal`] |
| `C:form` | **`form`** *text*: a form's name from the table of section 18.4.6 (`Shakespearean sonnet`, `villanelle`, `ballad stanza`, `free verse`), else the poem's shape in plain words (`four quatrains, rhymed abcb`); `parts` *refs* `C:part`; `metre` *ref* `C:metre`; `scheme` *text*, the rhyme scheme, a space between stanzas (`abab cdcd efef gg`); `rules`, a list of `{rule, held}`, what the form asks (`fourteen lines`, `a turn at line 9`) and whether the poem keeps it, `held` a *bool*; `departures`, a list of `{at, what}`, `at` a `C:line` or a `C:part`; `intended` *bool*, whether the author meant the form, absent until asked |
| `C:file` | **`path`**, relative to `source.path`; `language`; `holds` *text*, the names it defines or one line on its content; `component` *ref*; `length` `{lines, bytes}`; `sha256`; `entry` *bool*, run directly |
| `C:component` | `files` *refs* `C:file`; `of` *ref* `C:component`; `does` *text*, its responsibility in one sentence; `exposes` *refs* `C:interface`; `uses` *refs* (`C:component`, `C:dependency`) |
| `C:interface` | **`surface`** [`function` `method` `class` `command` `format` `stream`]; `signature` *text*, exact: a Python `def` or `class` line with its annotations and defaults, and with its decorators before it on the same line (`@property def size(self)`), a command's usage line, a format's one-line grammar; `defined-in` *ref* `C:file`; `takes`, a list of `{name, type, default, required, means}`; `gives`, `{type, means}` for a function or `{output, exit}` for a command; `raises`, a list of `{error, when, message}`; `exported` *bool* |
| `C:structure` | `defined-in` *ref*; `shape` *text* (`a record class that cannot change`, `a JSON object per line`); `fields`, a list of `{name, type, default, required, means}`; `invariants`, a list of *text* |
| `C:behaviour` | **`does`** *text*; `of` *refs* (`C:interface`, `C:component`); `when` *text*, the trigger; `edges`, a list of `{given, then}`; `errors`, a list of `{when, message, exit}`; `intended` *bool*, absent until asked |
| `C:dependency` | **`scope`** [`standard` `run-time` `test` `build` `optional`]; `package`; `version`, a constraint; `needed-for` *text*; `used-by` *refs*; `licence` |
| `C:setting` | **`set-in`** [`environment` `file` `option` `constant`]; `key`; `default`; `type`; `means`; `read-by` *refs* `C:interface` |
| `R:maker` | `who` *ref* (an `E:person` or `E:org`); `capacity` [`author` `maintainer` `contributor` `editor` `translator` `publisher` `performer` `composer`] |
| `R:change` | `at` *date*; `by` *ref* `R:maker`; `nature` [`feature` `fix` `refactor` `removal` `docs` `tests` `build` `revision`]; `because` *text*; `touches` *refs*; `release` *ref* `R:release`; `phase` *ref* `R:phase`; `commit` *text* |
| `R:phase` | `began`, `ended` *date*; `changes` *refs* `R:change` |
| `R:release` | `version`; `at` *date*; `tag`; `venue` *text*, where it appeared; `changes` *refs* `R:change` |
| `R:means` | `what` *text*; `used-for` *text*; `version` |
| `R:licence` | `identifier`, the licence's standard short identifier (`MIT`) or plain words (`public domain`); `file`, a path; `holder`; `year` *text*, as the source writes it (`'1794'`); `first-line` |
| `P:reading` | **`of`** *refs* (the `C:line`, `L:term`, E item, `C:part` or `P:claim` it reads); **`whose`** `{by: [author expert critic model reader], name, work, session, model}`; `grounds`, a list of `{of, because}`, what in the text supports it; `intended` *bool*, whether the author meant it, absent until asked (section 18.4.6) |
| `P:case` | **`of`** *refs* (`C:interface`, `C:behaviour`, `N:requirement`, `N:use`); **`given`**, a mapping of `calls`, `arguments`, `input`, `env`, `file`, `files`; **`expect`**, a mapping of `value`, `output`, `error-output`, `exit`, `files`, `raises` |

In a fabulac the unchanged kinds take the program's terms: `L:term` its own vocabulary, E items the named things it
deals with (a holder, a service, a file it writes), `K:concept` the ideas the code relies on, `P:claim` what its
documents assert, and `T:event` the steps of a use, in order, each linked `{rel: part-of, to: N:use/<slug>}`.



#### 18.4.3 The conventions, in plain words

**Terms are grounded in FEED.** Every `L:term` says where its word stands in FEED, the dictionary enough ships:
`feed: {word, pos, origin}`, with `pos` the part of speech the work uses (one of those FEED lists for the word) and
`origin` either `feed` or `user` (a person's own dictionary). Its `sense` is the meaning the word has in this work:
FEED's definition when the work uses the word that way, the work's own sense when it does not. A word FEED does not hold
is written `feed: {pending: "not in FEED"}`, an open question, never a made-up entry. In a fabulac the terms are the
program's own vocabulary, grounded the same way.

**Claim summaries name everyone.** A claim's `summary` restates the claim as one sentence in which every participant is
named, by its name or its id, and no pronoun stands in for anyone. A reader can take any claim out of the fabula and it
still says exactly what it said.

**Participants fill named role slots.** A claim's `roles:` is a mapping from a role name to the participant that fills
it: `{actor: E:org/meadow, act: K:concept/close, after: E:thing/bank-feed}`. The role names are free (`actor`, `object`,
`instrument`, `source`, `holder`, `cause`, `effect`, `condition` …). A slot holds an item id whenever the participant is
an item of the fabula, and is then checked; otherwise it holds a literal (section 9.6). The kinds with `roles.*`
(influences, allusions, occasions, aims, voices) fill their slots the same way.

<!-- term: stance -->
A claim's **stance** is how the text knows it. Every claim has one, from a closed list of six, in the spirit of the
evidential markers some languages carry in their grammar:

| Stance | The text holds the claim as |
|---|---|
| `axiom` | given, or true by definition; the text does not argue for it |
| `observed` | seen, measured or done, at first hand |
| `deduced` | reasoned from other claims of the text, which the claim links to with `depends-on` or `supports` |
| `opinion` | a judgement or a preference of the author's |
| `assumed` | taken for granted: the text relies on it without stating it as a premise, or supposes it for the sake of argument |
| `hearsay` | reported from someone else, who fills the claim's `source` slot when the text names them |

**On every other kind, the stance is the fabula's.** An aim, a line, a behaviour or a reading carries a stance from the
same six, saying how the fabula knows the item: `observed`, read in the input (everything a rules stage reads from code
is observed); `deduced`, reasoned from other items of the fabula; `assumed`, taken without support; `hearsay`, someone
said so (an answer in the dialectic, a critic, a document); `opinion`, a judgement, such as a model's own reading;
`axiom`, given. The two senses never mix: a claim's stance says how the text knows what it says, and any other item's
says how its maker knows the item.

<!-- term: salience -->
A claim's **salience** is how much it matters to the text, from a closed list of four: `critical`, `high`, `normal` and
`low`. A short told by weight puts the claims in that order (section 18.4.4).

**Typed links instead of arrows.** A relation between two items is a typed link in the first item's `links:`, never a
symbol between them. The fabula closes the relations to nine:

| `rel` | The item … the target |
|---|---|
| `is-a` | is a kind or an instance of |
| `part-of` | is a part of |
| `depends-on` | holds only if the target holds |
| `supports` | is evidence or an argument for |
| `contradicts` | cannot hold together with |
| `resolves` | settles (a question, a tension, a contradiction) |
| `exemplifies` | is an example of |
| `defines` | gives the meaning of |
| `mentions` | names, without saying more about |

Every other relation a kind needs is a named reference field, never a tenth relation: implementing is `met-by`,
testing `checked-by`, being defined in a file `defined-in`; calling is `depends-on`, and a change that answers a
question `resolves` it.

<!-- term: span -->
An item's **span** points it back at its input: it says where the item comes from, `{lines: "3"}` or
`{lines: "12-18"}`, or, when lines do not serve, `{start: "<up to 60 characters>", end: "<up to 60 characters>"}`,
quoted from the passage's first and last words. In a fabulac the span names a file as well,
`{file: days.py, lines: "9-16"}`, its path relative to the source folder. A reader jumps from an item to its passage by
its span.

**Derived items carry their provenance.** Every item says `provenance: {mode, sources, confidence, state}`. A decompile
writes `mode: derived`, and its sources are locators in the input: the text's path and a line or a range,
`'close.md#L3'`, `'close.md#L12-L18'`; in a fabulac, a file's path, `'days.py#L9-L16'`. What a person's answer wrote is
`mode: dialectic`, its source the session it was given in (section 18.6). When an answer fills one field of an item made
some other way, the item keeps its mode, the session joins its `sources`, and `provenance.answered` names the field:
`{<field path>: {sources: [D:session/<id>], confidence}}`. A field a person declined to give is listed in the item's
`withheld`, and its `provenance.state` is `not-disclosed`.

**What was read is observed; what a model inferred says so.** A fabula keeps apart what the input shows and what was
made of it. An item read from the input, by rules or by a model, is `observed`, with a span that points at the words or
the code. An item a model reasoned to is `deduced`; one it took without support is `assumed`; a reading that is the
model's own is an `opinion`, `whose: {by: model}`, at a confidence of at most 0.5. Nothing a model supposed is written
as though the input said it.

**An unknown is a question, never a guess.** What the input does not settle, who a poem's speaker is, why a decision
was made, whether a behaviour is intended, is written `{pending: "<the question>"}` (section 10), or raised as a
question of the dialectic about the item's field (section 18.6), and is answered by a person, never filled in by a model
that does not know. A question can go to the author, an expert in the author's work, the program's maker, or anyone;
its answer, even that the person does not know, is written
back as section 18.6 says.

**A fabula records which model made it.** The catalog's `derived` names the model, its route and, for a cloud model,
its provider; `derived.runs` names them for every run that wrote into the fabula; and every item's provenance names its
mode and its sources. A fabula made partly on a local model and partly on a cloud model says which part came from which
(section 18.4.1). Nothing reaches a cloud model that the person did not choose for that job, and a job that names no
route runs on the local model, whatever entry point started it.

**A scaffold says it is one.** When no model is available, an implementation still writes a fabula, by rules: for a
text, candidate terms and entities from the text and FEED, and atems as in section 18.3.5; for a folder, the `outline`
of section 18.4.7. The catalog says `derived.mode: rules`. Every item a rules pass guesses at has `confidence: 0.3`,
`state: pending` and `pending: "a model has not read this passage"`, and the viewer says "scaffold, no model". What a
rules pass reads exactly, a file's digest, a function's signature, a stanza's lines, is `observed` at full confidence.
A scaffold is a starting point a person can see through, never a guess dressed as a reading.

**Made on request, never in passing.** A fabula is made when a person asks for it, or a readvisor's tool does. Nothing
that imports, copies, lists or reconciles files ever decompiles an input, and nothing ever fetches an input that is not
already on the person's disk.

**Compiled, it entails a short.** Compiling a fabula writes a short beside its input, a cshort or a catem beside its
folder, and never touches the input (sections 18.4.4 and 18.4.7).

#### 18.4.4 Shorts

<!-- term: short -->
A **short** of a text is an entailment of the text's fabula, compiled from it. Its name is an acronym, **SHORT**,
*syuzhetic-hermeneutic open readable text*. It is *syuzhetic*: an arrangement, the fabula's items put in an order. It is
*hermeneutic*: as it sets out each thing it says how the thing is known, every claim's stance in plain words. It is
*open*: it is plain markdown that anyone can read without enough, it is yours to edit, it is honest about its gaps, and
it is open to the reader's own reading. It is *readable text*: prose, not a database. The name covers only what is
compiled from a fabulan or a fabulap.

**One fabula, many entailments.** A text's twin is its fabula (section 18.4): the order-free material every short is
made from. Every claim is there with its stance, every event with its own before and after, every term grounded, and
each item's `span` says where in the author's text it was found.

<!-- term: syuzhet -->
A *syuzhet* is an arrangement of a fabula's material, its items in an order. The author's text is a syuzhet of the
same fabula, the first one, and it is the author's: it is never called a short, and it entails the fabula rather than
the other way round. A short is a syuzhet the fabula entails, compiled from it, and a text can have many. The atem sits outside the pair. It is the breath of the text, a reduction with its own hermeneutic
shape (push and pull), neither material nor arrangement.

**Two orders.** A short sets out the fabula's items in one of two orders:

- **as told** — every item where its span puts it, in the author's order: `told` in the files;
- **by weight** — the claims that matter most first, then the events, then the terms: `weight` in the files.

| Order | In words | How it orders |
|---|---|---|
| `told` | as the author told it | every item with a span, in the order of its span: by first line, then last line, and within one line the words, the names, the ideas, the claims, then the events. Under the text's own headings when the text can be read (a span given as quotes is then placed on its line). Items that no span places come last, under "Also in the fabula" |
| `weight` | by weight | the claims in order of salience, grouped by the concepts they lean on; then the events, in before/after order; then the terms |

Both open with the atem line, and both say each claim's stance in plain words ("the author holds that", "it is assumed
that", "reportedly"). Pinned passage atems are not set out: like the file's atem, they stand outside the short. With no
order given, a compile uses `told` when the fabula names a source text that can be read, and `weight` for a standalone
fabula. Without a model a short is the ordered outline itself, said in the items' own sentences; with one, a model
writes the outline as prose and is told which order it is in. A third order, the events first in the order they
happened, is reserved for a later edition.

A short of a fabulap (section 18.4.6) goes stanza by stanza: how the poem is built, its form and its metre, then each
stanza's lines with their stresses and rhymes (their words only where the fabulap holds them), its devices and its
readings, each reading said as whose it is. Told by weight, it ends with how the poem can be read.

**The file.** A short is written beside its text as `<text-stem>.short-<YYYY-MM-DD-HHMM>.md`, in local time:
`notes.md` gives `notes.short-2026-10-23-1042.md`. The stem is the text's, whatever the twin is called: the twins
`close.md.fabulan.cosm` and `close.md.cosm` both give `close.short-…md`, and a standalone `rain.fabulan.cosm` gives
`rain.short-…md`. A second compile in the same minute takes `-2`, then `-3`. Every compile is a new file. Nothing is
overwritten, and the text is never touched. A short is an ordinary markdown file, shown in every listing; Canon's
catalogs mark it `short_of` its text, and the text `shorts` (section 18.3.2).

**The footer.** Every short ends with one italic line that says what it is a short of, in which order, when, and by
which model or by rules:

```text
*a short of notes.md, told as the author told it, compiled from its fabula on 2026-10-23 by g40-04*
```

Without a model the line ends "by rules, without a model". A short of a standalone fabula says so: "a short of
rain.fabulan.cosm, a standalone fabula, told by weight, compiled on …". A footer written by an earlier edition, which
names the fabula by the name it had then, reads the same.

**The fabula records its entailments.** Each compile appends one entry to the fabula's `shorts:` list, `{path, at, by,
mode, order}`: the short's file name beside the twin; when, as a timestamp in UTC; the model's id, or `rules`; `model`
or `rules`; `told` or `weight`; and `route`, `local` or `cloud`, when a model wrote it. The list is made just above
`nodes:` the first time. Nothing else in the fabula changes: not its items, not its `source:` (a fresh twin stays
fresh), not a byte of the rest.

**A fabulac entails a cshort.** A fabulac's short is a cshort, source code rebuilt from the fabulac (section 18.4.7). It
is recorded in the same `shorts:` list, with `order: code`, but it is a folder of source and not prose:
the acronym SHORT names the entailment in prose and verse, and a cshort keeps only the word.

**Where the words come from.** *Fabula* and *syuzhet* are the Russian Formalists' pair: the story as it happened, and
the story as it is told. Their work on how a telling makes the familiar strange began with Viktor Shklovsky's *Art as
Technique* (1917), and Boris Tomashevsky's *Thematics* (1925) set the two terms out. MacroCOSM borrows the pair for
meaning rather than plot: the fabula is the material, and a short is one entailment of it.

#### 18.4.5 Examples

The text, `guides/close.md` in the Canon volume of section 18.3.6:

```markdown
# The morning close

Meadow closes every customer's books overnight, after the bank feeds arrive.
A close locks the day, so no entry in it can change.
The Support Lead reports that most owners read the morning summary before they open the restaurant.
A close that fails is retried at five; if the retry fails, the Support Lead calls the owner before seven.
Because the close waits for the feeds, a late feed delays the summary.
We think a summary that arrives every morning is why owners stay.
```

Its twin, `guides/close.md.fabulan.cosm`, made by a local model in a run of the program `decompile-prose`, and settled
by a second run, by rules (`derived.runs` lists both). It was decompiled again from a twin of the old name, whose one
short it carries over. Each of the six stances appears once on its claims. The first run also raised its questions by
rules: one for each entry of the fabulan's bank that applies, asked once of the volume but for `stand-by`, which is
asked of each of the six claims, and one for each pending value: twenty-two in all. Two of them were put to the author
in a first sitting and are shown here with the sitting; the other twenty are open and are left out. The question the
occasion's pending value raised was answered and settled into `I:occasion/why-written`, whose provenance says which
field the answer wrote. The bank's audience question, which is about module N and not about `N:audience/owners`, was
skipped and stays open.

```cosm
oes: fabula/1
macrocosm: 0.5.4
flavour: fabulan
id: fabula/guides--close-md
name: The morning close
source: {path: close.md, sha256: d297e46db2cbd55a0fb8af894c130604f087455510bec9417548ce3742191b14, size: 494, mtime_ns: 1792660324518000000}
derived:
  at: 2026-11-05T10:02:11Z
  by: person
  model: g40-04
  route: local
  program: decompile-prose
  run: 2026-11-05-1002-a1c4
  mode: model
  completeness: full
  chunks: 1
  runs:
    - {program: decompile-prose, run: 2026-11-05-1002-a1c4, at: 2026-11-05T10:02:11Z, model: g40-04, route: local}
    - {program: settle-the-answers, run: 2026-11-05-1031-b7e0, at: 2026-11-05T10:31:02Z}
atem:
  line: Meadow closes each customer's books overnight once the bank feeds arrive, locks the day, and retries a failed close before anyone opens the summary.
  focus: How Meadow's overnight close works, what it guarantees, and what it waits on.
  push: Trust the morning summary, because every day is locked and a failed close is caught before seven.
  pull: The summary is only as early as the bank feeds, which Meadow does not control, so a late feed still delays it.
shorts:
  - {path: close.short-2026-10-22-0931.md, at: 2026-10-22T09:31:12Z, by: g40-04, mode: model, order: told}
nodes:
  - id: I:occasion/why-written
    type: occasion
    name: Why the guide was written
    summary: Nothing in the text says what prompted Meadow to write the guide.
    stance: assumed
    roles: {event: an owner's call to support about a late morning summary}
    span: {lines: "1"}
    provenance:
      mode: derived
      sources: ['close.md#L1', D:session/session-1]
      confidence: 0.3
      state: pending
      answered: {roles.event: {sources: [D:session/session-1], confidence: 0.9}}
  - id: L:term/close
    type: term
    name: close
    summary: The word the text uses for locking one day of a customer's books.
    feed: {word: close, pos: noun, origin: feed}
    sense: Locking one day of the books so that no entry in the day can change.
    span: {lines: "3-7"}
    provenance: {mode: derived, sources: ['close.md#L3-L7'], confidence: 0.9, state: known}
  - id: L:term/morning-summary
    type: term
    name: morning summary
    summary: The phrase the text uses for the statement an owner reads each morning.
    feed: {pending: "not in FEED"}
    sense: The one-page statement of the books that an owner reads each morning.
    span: {lines: "5-8"}
    provenance: {mode: derived, sources: ['close.md#L5-L8'], confidence: 0.8, state: known}
  - id: E:org/meadow
    type: org
    name: Meadow
    summary: Meadow Software, the company whose overnight close the text describes.
    span: {lines: "3"}
    provenance: {mode: derived, sources: ['close.md#L3'], confidence: 0.9, state: known}
  - id: E:person/support-lead
    type: person
    name: the Support Lead
    summary: The holder of the Support Lead role at Meadow; the text names the role, never a person.
    span: {lines: "5-6"}
    provenance: {mode: derived, sources: ['close.md#L5-L6'], confidence: 0.9, state: known}
  - id: E:thing/bank-feed
    type: thing
    name: bank feeds
    summary: The transaction feeds from each customer's banks, which the close waits for.
    span: {lines: "3-7"}
    provenance: {mode: derived, sources: ['close.md#L3-L7'], confidence: 0.9, state: known}
  - id: K:concept/close
    type: concept
    name: the close
    summary: The overnight run that settles and locks one day of a customer's books.
    defined-by: P:claim/close-locks-the-day
    span: {lines: "3-7"}
    provenance: {mode: derived, sources: ['close.md#L3-L7'], confidence: 0.9, state: known}
  - id: K:concept/owner
    type: concept
    name: owner
    summary: A restaurant owner who is a customer of Meadow.
    span: {lines: "5-8"}
    provenance: {mode: derived, sources: ['close.md#L5-L8'], confidence: 0.8, state: known}
  - id: N:aim/trust-the-summary
    type: aim
    name: Owners trust the morning summary
    summary: The guide sets out to make owners trust the morning summary by showing that every day is locked and every failed close is caught.
    stance: deduced
    measure: An owner reads the summary before opening without calling support to ask whether it is final.
    roles: {for: N:audience/owners}
    links: [{rel: depends-on, to: P:claim/close-locks-the-day}]
    span: {lines: "3-8"}
    provenance: {mode: derived, sources: ['close.md#L3-L8'], confidence: 0.7, state: known}
  - id: N:audience/owners
    type: audience
    name: Restaurant owners
    summary: The guide is written for the restaurant owners who read the morning summary.
    stance: deduced
    who: restaurant owners who are Meadow's customers
    needs: To know whether the morning summary can be relied on, and what happens when the close fails.
    span: {lines: "5"}
    provenance: {mode: derived, sources: ['close.md#L5'], confidence: 0.8, state: known}
  - id: C:voice/meadow-we
    type: voice
    name: Meadow, in the first person plural
    summary: The guide speaks as Meadow, reporting in the third person until its last sentence, which says we.
    stance: observed
    perspective: mixed
    tone: plain, reassuring
    roles: {speaker: E:org/meadow, addressee: N:audience/owners}
    span: {lines: "3-8"}
    provenance: {mode: derived, sources: ['close.md#L3-L8'], confidence: 0.8, state: known}
  - id: R:maker/meadow
    type: maker
    name: Meadow, as author
    summary: Meadow wrote the guide; the text speaks as Meadow and names no writer.
    stance: deduced
    who: E:org/meadow
    capacity: author
    span: {lines: "8"}
    provenance: {mode: derived, sources: ['close.md#L8'], confidence: 0.7, state: known}
  - id: P:claim/meadow-closes-overnight
    type: claim
    name: Meadow closes overnight
    summary: Meadow closes the books of every customer overnight, after the bank feeds arrive.
    stance: observed
    salience: high
    roles: {actor: E:org/meadow, act: K:concept/close, after: E:thing/bank-feed}
    links: [{rel: depends-on, to: P:claim/every-customer-has-a-feed}]
    span: {lines: "3"}
    provenance: {mode: derived, sources: ['close.md#L3'], confidence: 0.9, state: known}
  - id: P:claim/every-customer-has-a-feed
    type: claim
    name: Every customer has a bank feed
    summary: Every customer of Meadow has at least one bank feed for the close to wait on.
    stance: assumed
    salience: normal
    roles: {holder: K:concept/owner, thing: E:thing/bank-feed}
    span: {lines: "3"}
    provenance: {mode: derived, sources: ['close.md#L3'], confidence: 0.6, state: known}
  - id: P:claim/close-locks-the-day
    type: claim
    name: A close locks the day
    summary: A close locks the day, so no entry in the day can change.
    stance: axiom
    salience: critical
    roles: {subject: K:concept/close}
    links: [{rel: defines, to: K:concept/close}]
    span: {lines: "4"}
    provenance: {mode: derived, sources: ['close.md#L4'], confidence: 0.9, state: known}
  - id: P:claim/owners-read-summary-first
    type: claim
    name: Owners read the summary first
    summary: The Support Lead reports that most owners read the morning summary before the owners open the restaurant.
    stance: hearsay
    salience: normal
    roles: {source: E:person/support-lead, actor: K:concept/owner, object: L:term/morning-summary}
    span: {lines: "5"}
    provenance: {mode: derived, sources: ['close.md#L5'], confidence: 0.8, state: known}
  - id: P:claim/late-feed-delays-summary
    type: claim
    name: A late feed delays the summary
    summary: A late bank feed delays the morning summary, because the close waits for the bank feeds.
    stance: deduced
    salience: normal
    roles: {cause: E:thing/bank-feed, effect: L:term/morning-summary}
    links: [{rel: depends-on, to: P:claim/meadow-closes-overnight}]
    span: {lines: "7"}
    provenance: {mode: derived, sources: ['close.md#L7'], confidence: 0.8, state: known}
  - id: P:claim/daily-summary-keeps-owners
    type: claim
    name: The daily summary keeps owners
    summary: Meadow holds that a morning summary arriving every day is why owners stay with Meadow.
    stance: opinion
    salience: low
    roles: {holder: E:org/meadow, actor: K:concept/owner, object: L:term/morning-summary}
    span: {lines: "8"}
    provenance: {mode: derived, sources: ['close.md#L8'], confidence: 0.8, state: known}
  - id: T:event/feeds-arrive
    type: event
    name: The bank feeds arrive
    summary: The bank feeds of every customer arrive overnight.
    agent: E:thing/bank-feed
    when: overnight
    span: {lines: "3"}
    provenance: {mode: derived, sources: ['close.md#L3'], confidence: 0.9, state: known}
  - id: T:event/close-runs
    type: event
    name: The close runs
    summary: Meadow runs the close for every customer once the bank feeds have arrived.
    agent: E:org/meadow
    patient: K:concept/close
    after: T:event/feeds-arrive
    when: overnight
    span: {lines: "3"}
    provenance: {mode: derived, sources: ['close.md#L3'], confidence: 0.9, state: known}
  - id: X:atem/1
    type: atem
    name: When the close fails
    summary: The atem of the passage on what happens when the overnight close fails or starts late.
    line: A failed close is retried at five and escalated by phone before seven, and any late bank feed pushes the summary back.
    focus: What happens when the overnight close fails or starts late.
    push: A failed close will not reach the owner's morning unnoticed, because a retry and a call stand in the way.
    pull: The safety net covers a failed close, not a late feed, so a slow bank still delays the summary.
    of: [K:concept/close]
    span: {lines: "6-7"}
    provenance: {mode: derived, sources: ['close.md#L6-L7'], confidence: 0.8, state: known}
  - id: D:question/audience
    type: question
    about: N
    asks: Whom did you write it for?
    why: missing
    kind: text
    to: author
    raised: {by: bank, from: fabulan/audience, at: 2026-11-05T10:02:11Z, run: 2026-11-05-1002-a1c4}
    state: open
  - id: D:question/why-written-roles-event
    type: question
    about: I:occasion/why-written#roles.event
    asks: "What prompted this guide: a support question, a failed close, a launch?"
    why: missing
    kind: text
    to: author
    raised: {by: move, from: question, at: 2026-11-05T10:02:11Z, run: 2026-11-05-1002-a1c4}
    state: answered
    answers:
      - {at: 2026-11-05T10:20:40Z, by: author, says: "An owner rang support asking why her summary was late, twice in a week.", value: an owner's call to support about a late morning summary, confidence: 0.9, session: D:session/session-1}
    settled: {at: 2026-11-05T10:31:02Z, run: 2026-11-05-1031-b7e0, wrote: [I:occasion/why-written#roles.event]}
  - id: D:session/session-1
    type: session
    at: 2026-11-05T10:18:05Z
    with: {to: author, who: Meadow's head of support}
    through: person
    asked: [D:question/audience, D:question/why-written-roles-event]
    answered: [D:question/why-written-roles-event]
    skipped: [D:question/audience]
```

A twin written before this edition, still read: the minimal twin made by asking for the atem of
`research/interviews.txt` (the project of section 18.3.6) with no model running. It declares the old spelling, names no
flavour, and is read as a fabulan whose id keeps its old form. It holds the atem and nothing else, and says it is a
scaffold.

```cosm
oes: emf/1
id: emf/research--interviews-txt
name: interviews.txt
source: {path: interviews.txt, sha256: 452787f27e8ffbcf380f0af7e7887e974cc198d3a270224861e09690675631c7, size: 240, mtime_ns: 1792600811204000000}
derived: {at: 2026-10-21T16:41:02Z, by: person, mode: rules, completeness: atem, chunks: 1}
atem:
  line: Owners of six restaurants in Portland were interviewed in September 2026 about how and when they read their books.
  focus: Owners of six restaurants in Portland were interviewed in September 2026 about how and when they read their books. Four said they check cash before ordering stock each morning.
  push: {pending: "a model has not read this passage"}
  pull: {pending: "a model has not read this passage"}
nodes: []
```

#### 18.4.6 Verse: the fabulap

A poem asks more of a fabula than prose does. Its lines are units of their own, so each is a `C:line` with its number
counted over the whole poem, its stanza, its stresses and its place in the rhyme scheme. Its metre and its rhymes are
items, `C:metre` and `C:rhyme`, each naming the lines it governs and, for a metre, where a line departs from it. Its
devices, its voice and its divisions are the prose kinds `C:device`, `C:voice` and `C:part`, with stanzas, verses,
choruses, refrains and bridges among the divisions. Its occasions and allusions are I items; the book or the album it
appeared in is an `R:release`. Rhymes are compared within a stanza, and the scheme's letters run on from one stanza to
the next: a sound that comes back in a later stanza takes a new letter there, and a second `C:rhyme`.

**Several readings stand side by side.** A poem often means more than one thing at once, and a fabulap does not choose.
Each interpretation is a `P:reading` whose `of` names what it reads: the line, the word, the image. Readings of the
same thing stand together, each saying whose it is and what in the text supports it:

| Whose | `whose` | `stance` | Provenance |
|---|---|---|---|
| the author's, through the dialectic | `{by: author, session: D:session/<id>}` | `hearsay` | `mode: dialectic`, its source the session |
| an expert's, through the dialectic | `{by: expert, name, session}` | `hearsay` | `mode: dialectic` |
| a named critic's | `{by: critic, name, work}`; a name not known is a question | `hearsay` | `mode: derived`, its sources the text |
| the model's own | `{by: model}`; `model` defaults to `derived.model` | `opinion` | `mode: derived`, confidence at most 0.5 |
| a reader's, a person's own note | `{by: reader, name}` | `opinion` | `mode: manual` |

`grounds` lists what supports a reading, each entry an item of the fabula and a sentence on why. Two readings that
cannot both hold link with `contradicts`; one that builds on another links `depends-on`; readings that may both be meant
carry no link, and `intended`, set by the dialectic, says which the author owns. A `C:device` says that a figure is
there; a reading says what it means.

**The author, or an expert in the author's work.** A poem's fabula cannot be made well from the text alone: who
speaks, what an image stands for, whether an ambiguity is meant, what was cut from a draft, only the poet knows, and
after the poet an expert in the poet's work. The fabulap's bank of opening questions asks the author these things, and
when the author cannot be asked the questions go `to: expert`. This is what the dialectic is for (section 18.6). Until
a question is answered, its field stays pending and the readings stay side by side.

**What a full fabulap holds.** A fabulap made at its best guess holds what one reading finds. A full one is built by
Thym's helper moves for verse, `scan` by rule and `construe` by a model (Thym (https://thym.cosmoes.org/), its section
20.9), and holds the poem along eight axes:

| Axis | What the fabulap holds | Kinds | Made by |
|---|---|---|---|
| sound | each line's stresses and syllables; the end and inner rhymes, and the scheme; alliteration, assonance, consonance | `C:line`, `C:rhyme`, `C:device` | rule, from FEED's pronunciations |
| form | the metre and its departures; the form the poem keeps, with each of its rules held or broken; where lines run on, and where they pause | `C:metre`, `C:form`, `C:line`, `C:device` | rule |
| structure | the stanzas and a lyric's sections; refrains, repeated lines and openings, the hook; where the poem turns; what happens in it, in order | `C:part`, `C:device`, `T:event` | rule; the turn and the events by a model |
| sense | the words it leans on and their senses, the things and people it names, the ideas it uses, what it states outright, each stanza's atem | L, E, K, `P:claim`, X | a model, grounded in FEED |
| figure | its figures, and its images with the senses they reach | `C:device` | a model |
| voice | who speaks, to whom, before whom, in which person, in what tone and register, and where the voice shifts | `C:voice` | a model; the speaker is asked |
| reference | what it echoes, the traditions and genres it answers to, its occasion, its maker and where it appeared | I, `R:maker`, `R:release`, `R:licence` | a model, from the poem and its header only |
| what is left open | its readings, side by side; the words and lines that hold two senses; what it never names; and what the author meant, which only the author says | `P:reading`, `L:term`, `D:question` | a model, then the dialectic |

What a rule reads exactly is `observed`, and what it reads through FEED's pronunciations is `deduced`. What a model
writes keeps the stance the poem gives it: a reading is the model's `opinion`, at a confidence of at most 0.5, and an
aim, an occasion or an influence the poem does not state is `assumed`, pending, and asked (Thym, its section 20.9).

**Its forms.** A rule names a form when the poem keeps the form's defining rules, the first in this table that it
keeps, and lists the form's other rules as held or not, with the lines or parts that depart from them:

| Form | Defining rules | Other rules |
|---|---|---|
| Shakespearean sonnet | 14 lines; three quatrains and a couplet, as the rhymes run (`abab cdcd efef gg`) | iambic pentameter; a turn at line 13 |
| Petrarchan sonnet | 14 lines; an octave rhymed `abbaabba` | a sestet on two or three sounds (`cdecde`, `cdcdcd`); iambic pentameter; a turn at line 9 |
| sonnet | 14 lines of pentameter, rhymed otherwise | a turn |
| villanelle | 19 lines: five tercets and a quatrain | `aba` throughout and `abaa` last; line 1 again at lines 6, 12 and 18, and line 3 at 9, 15 and 19 |
| sestina | 39 lines: six sestets and a tercet | the first stanza's six end words end every stanza's lines, each stanza taking them in the order 6 1 5 2 4 3 of the one before; all six in the tercet |
| terza rima | tercets, each one's middle line rhyming with the outer lines of the next (`aba bcb cdc`) | iambic pentameter; a closing line or couplet |
| rhyme royal | stanzas of 7 lines rhymed `ababbcc` | iambic pentameter |
| ottava rima | stanzas of 8 lines rhymed `abababcc` | iambic pentameter |
| Spenserian stanza | stanzas of 9 lines rhymed `ababbcbcc` | eight lines of iambic pentameter, then one of six feet |
| common metre | quatrains of 8, 6, 8 and 6 syllables | iambic; the second and fourth lines rhyme |
| long metre | quatrains of 8 syllables a line | iambic tetrameter; `abab` or `aabb` |
| short metre | quatrains of 6, 6, 8 and 6 syllables | iambic; the second and fourth lines rhyme |
| ballad stanza | quatrains of four beats and three, alternating | the second and fourth lines rhyme |
| limerick | 5 lines rhymed `aabba` | three beats in lines 1, 2 and 5, two in lines 3 and 4; feet of anapaests |
| triolet | 8 lines on two rhymes | line 1 again at lines 4 and 7, and line 2 at 8 |
| pantoum | quatrains, lines 2 and 4 of each coming back as lines 1 and 3 of the next | the last stanza ends on the poem's first line |
| ghazal | five couplets or more | every couplet's second line ends on the same word or words, as both lines of the first do |
| heroic couplets | rhymed couplets of pentameter (`aabbcc …`) | iambic |
| haiku | 3 lines | 5, 7 and 5 syllables; no rhyme |
| blank verse | 10 lines or more of iambic pentameter | no rhyme scheme |
| free verse | no metre (`basis: free`) and no rhyme scheme | |

The thresholds behind each rule are the conformance suite's. Syllables and beats are counted in English, through FEED,
so a haiku is counted by English syllables. A poem that keeps no form of the table is named by its shape (`four
quatrains, rhymed abcb`). The table is this edition's, and a later one may add to it.

**The questions.** The fabulap's bank asks the author, or an expert in the author's work when the author cannot be
asked, along the same axes: what set the poem going and what was in the author's ear (inspiration); what a reader
should feel by the last line, and what the poem is careful not to say (intent); who speaks, to whom, and whether the
voice shifts (voice); how a line is read aloud, and whether a break, a sound, a departure from the metre or the form
itself was meant (sound and form); which image weighs most and what a figure stands for (figure); whether an echo was
meant and, when the author cannot be asked, whether every word is as the author left it (reference); whether a reading
was meant, and which the author would refuse (what is left open); and, for a song, what it is sung to and where the
tune moves a word (a lyric). Each question names the item it is about, and its answer is written as section 18.6.4
says: an answer that the author meant a reading, a device or a form sets its `intended`.

**A lyric.** A song's words are verse, and a fabulap holds them as it holds a poem's, with three things more. Its
sections are the parts a lyric sheet labels, verse, chorus, bridge and the rest, and a chorus that comes back is one part
sung again. Its hook, the line a listener keeps, is found by rule as the line said most often, held as a guess, and
asked. Its sung line is not its spoken line: the fabulap scans the words as they are spoken, and says so. Without the
music a fabulap cannot know the melody, where the tune puts a word's stress or holds one syllable over several notes,
the rhythm and the pace of the setting, its harmony, which lines are sung and which spoken, or what a singer adds or
repeats. It holds what the author or an expert says of them: the tune as an `R:means` and its maker as an `R:maker` of
capacity `composer`, a recording or a performance as an `R:release`, and a stress the tune moves as a `C:device` at its
line; never the notes.

**What it leaves out.** This edition's fabulap does not hold the music of a song (above); the poem on the page beyond
its lines and stanzas (indentation, spacing, the shape the lines make, type, and the marks a line's text keeps when it is
written); prosody beyond stress (the length of syllables, pitch and pace) and every prosody but English's, which FEED
reads; the poem's life outside its text (drafts, variants, editions, translations, letters, the poet's life), which
reaches a fabulap only as an answer; readings in a school's name, which reach it only as a named critic's or a reader's
own; and a measure of the poem's style against the null morph, whose scales read prose (Thym, its section 13). Each is a
place a later edition can add to, by declaration (Thym, its section 20.9).

**A line's text is stored only when the source may be copied.** `C:line.text` is written only when the person says the
poem may be copied: it is their own work, or it is out of copyright. Otherwise the line's `span` is the pointer, and
the fabulap holds the line's number, stresses and rhyme without its words. Nor are its words in its `name`: a line whose
text is not written is named by its number (`line 5`). Single words the fabulap needs elsewhere, a term, a rhyme's
sounds, an allusion's cue, are not the line's words, and are kept. A line's stance is that of its words; how sure its
scansion is shows in its provenance's `confidence`. Nothing is ever fetched: a fabulap is made from the copy of the
poem on the person's disk, and no implementation goes looking for a text, a draft or a critic's reading.

The kinds' fields are in section 18.4.2.

**An example.** William Blake's *The Sick Rose*, first published in 1794 and out of copyright everywhere, as
`poems/the-sick-rose.txt`:

```text
The Sick Rose
William Blake, Songs of Experience (1794)

O Rose thou art sick.
The invisible worm,
That flies in the night
In the howling storm:

Has found out thy bed
Of crimson joy:
And his dark secret love
Does thy life destroy.
```

Its fabulap, `poems/the-sick-rose.txt.fabulap.cosm`, made on a cloud model. To keep the example short it holds the
lines of the second stanza only; a complete fabulap holds a `C:line` for every line of the poem. Two rival readings of
the worm stand side by side, the model's own and a critic's whose name is still a question, and three questions wait
for an expert in Blake's work, since the author cannot be asked. The lines' text is written because the poem is in the
public domain (`R:licence/public-domain`).

```cosm
oes: fabula/1
macrocosm: 0.5.4
flavour: fabulap
id: fabula/poems--the-sick-rose-txt
name: The Sick Rose
source: {path: the-sick-rose.txt, sha256: c35789bdb766ef26a13b65a2c3cb243ac59e9119731f361194ed5023c39fca58, size: 232, mtime_ns: 1793914431114080113}
derived: {at: 2026-11-05T11:40:00Z, by: person, model: vendor/large-model, route: cloud, provider: broker-name, mode: model, completeness: full, chunks: 1}
atem:
  line: An unseen worm flying through a stormy night finds a rose's bed of crimson joy, and its dark secret love destroys the rose's life.
  focus: A speaker tells a rose that it is sick, and names the cause, a worm whose hidden love is killing it.
  push: Something loved in secret, in the dark, destroys what it loves.
  pull: The poem never says what the rose or the worm stands for, so every reading of them, a canker, a lover, experience itself, is the reader's to argue for.
nodes:
  - id: L:term/bed
    type: term
    name: bed
    summary: The poem's word for the place the worm finds, the rose's bed of crimson joy.
    feed: {word: bed, pos: noun, origin: feed}
    sense: {pending: "a flower bed, a bed to sleep or love in, or both?"}
    span: {lines: "9-10"}
    provenance: {mode: derived, sources: ['the-sick-rose.txt#L9-L10'], confidence: 0.6, state: pending}
  - id: E:thing/rose
    type: thing
    name: the rose
    summary: The rose the poem addresses and declares sick.
    span: {lines: "4"}
    provenance: {mode: derived, sources: ['the-sick-rose.txt#L4'], confidence: 1, state: known}
  - id: E:thing/worm
    type: thing
    name: the invisible worm
    summary: The unseen worm that flies by night and destroys the rose with its love.
    span: {lines: "5-11"}
    provenance: {mode: derived, sources: ['the-sick-rose.txt#L5-L11'], confidence: 1, state: known}
  - id: C:part/stanza-2
    type: part
    name: Second stanza
    summary: The worm finds the rose's bed and its dark secret love destroys the rose's life.
    stance: observed
    division: stanza
    number: 2
    span: {lines: "9-12"}
    provenance: {mode: derived, sources: ['the-sick-rose.txt#L9-L12'], confidence: 1, state: known}
  - id: C:line/5
    type: line
    name: Has found out thy bed
    summary: The worm has found the rose's bed.
    stance: observed
    number: 5
    text: Has found out thy bed
    part: C:part/stanza-2
    metre: C:metre/two-beat
    stresses: x / | x x /
    rhyme: d
    ending: run-on
    span: {lines: "9"}
    provenance: {mode: derived, sources: ['the-sick-rose.txt#L9'], confidence: 0.8, state: known}
  - id: C:line/6
    type: line
    name: Of crimson joy
    summary: The bed is one of crimson joy.
    stance: observed
    number: 6
    text: 'Of crimson joy:'
    part: C:part/stanza-2
    metre: C:metre/two-beat
    stresses: x / | x /
    rhyme: e
    ending: stopped
    span: {lines: "10"}
    provenance: {mode: derived, sources: ['the-sick-rose.txt#L10'], confidence: 0.9, state: known}
  - id: C:line/7
    type: line
    name: And his dark secret love
    summary: The worm's love is dark and secret.
    stance: observed
    number: 7
    text: And his dark secret love
    part: C:part/stanza-2
    metre: C:metre/two-beat
    stresses: x x / | / x /
    rhyme: f
    ending: run-on
    span: {lines: "11"}
    provenance: {mode: derived, sources: ['the-sick-rose.txt#L11'], confidence: 0.6, state: known}
  - id: C:line/8
    type: line
    name: Does thy life destroy
    summary: That love destroys the rose's life.
    stance: observed
    number: 8
    text: Does thy life destroy.
    part: C:part/stanza-2
    metre: C:metre/two-beat
    stresses: x x / | x /
    rhyme: e
    ending: stopped
    span: {lines: "12"}
    provenance: {mode: derived, sources: ['the-sick-rose.txt#L12'], confidence: 0.9, state: known}
  - id: C:metre/two-beat
    type: metre
    name: Two beats a line
    summary: Every line carries two strong beats, in feet that mix anapaests and iambs, so the lines run short and quick.
    stance: deduced
    foot: mixed
    feet: 2
    basis: accentual
    lines: [C:line/5, C:line/6, C:line/7, C:line/8]
    departures:
      - {line: C:line/6, what: 'the shortest line, two iambs, four syllables'}
      - {line: C:line/7, what: '"dark" may take a third stress, slowing the line before the end'}
    provenance: {mode: derived, sources: ['the-sick-rose.txt#L4-L12'], confidence: 0.6, state: known}
  - id: C:rhyme/joy-destroy
    type: rhyme
    name: joy, destroy
    summary: Lines 6 and 8 rhyme joy with destroy, so the poem's last word answers its happiest one.
    stance: observed
    scheme: e
    sound: -oy
    lines: [C:line/6, C:line/8]
    quality: full
    placement: end
    provenance: {mode: derived, sources: ['the-sick-rose.txt#L10-L12'], confidence: 0.9, state: known}
  - id: C:voice/speaker-to-rose
    type: voice
    name: An unnamed speaker to the rose
    summary: An unnamed speaker addresses the rose as thou and tells it what is killing it.
    stance: observed
    perspective: second
    tone: grave, intimate
    roles: {speaker: {pending: "who speaks: the poet, a witness, a lover?"}, addressee: E:thing/rose}
    span: {lines: "4-12"}
    provenance: {mode: derived, sources: ['the-sick-rose.txt#L4-L12'], confidence: 0.8, state: known}
  - id: C:device/the-worm-as-symbol
    type: device
    name: The worm as a symbol
    summary: The worm is given flight, a love and a secret, more than any worm has, so it stands for something the poem never names.
    stance: deduced
    figure: symbol
    where: [C:line/7]
    effect: The image stays open, and the poem's readings divide over what the worm stands for.
    provenance: {mode: derived, sources: ['the-sick-rose.txt#L5-L11'], confidence: 0.8, state: known}
  - id: R:licence/public-domain
    type: licence
    name: Public domain
    summary: The poem is out of copyright everywhere; it was published in 1794 and its author died in 1827.
    stance: deduced
    identifier: public domain
    year: '1794'
    provenance: {mode: derived, sources: ['the-sick-rose.txt#L2'], confidence: 0.9, state: known}
  - id: P:reading/worm-is-a-canker
    type: reading
    name: The worm is a canker
    summary: Read plainly, the worm is a canker grub that eats into the rose from its bed, and the poem is about blight.
    stance: opinion
    of: [E:thing/worm]
    whose: {by: model}
    grounds:
      - {of: E:thing/worm, because: '"worm" is the plain word for a grub that eats into roses'}
      - {of: L:term/bed, because: 'a bed is where a rose grows'}
    span: {lines: "5-12"}
    provenance: {mode: derived, sources: ['the-sick-rose.txt#L5-L12'], confidence: 0.5, state: known}
  - id: P:reading/worm-as-desire
    type: reading
    name: The worm is a lover's desire
    summary: The worm is a lover whose possessive, hidden desire spoils the love it enters, and the bed of crimson joy is a bed of love.
    stance: hearsay
    of: [E:thing/worm, L:term/bed]
    whose: {by: critic, name: {pending: "which critic first argued this reading in print, and where?"}}
    grounds:
      - {of: C:line/7, because: 'the worm has a "love" that is dark and secret'}
      - {of: C:line/6, because: '"crimson joy" reads as passion as easily as colour'}
    span: {lines: "9-12"}
    provenance: {mode: derived, sources: ['the-sick-rose.txt#L9-L12'], confidence: 0.6, state: known}
  - id: D:question/speaker
    type: question
    about: C:voice/speaker-to-rose#roles.speaker
    asks: Who speaks the poem, and is the rose addressed as a flower, a woman, or both?
    why: unsure
    kind: text
    to: expert
    raised: {by: bank, from: fabulap/speaker, at: 2026-11-05T11:40:00Z, run: 2026-11-05-1140-c2d9}
    state: open
  - id: D:question/worm-intended
    type: question
    about: P:reading/worm-as-desire#intended
    asks: Did Blake mean the worm to be read as a lover's desire as well as a canker?
    why: ambiguous
    kind: yes-no
    to: expert
    raised: {by: bank, from: fabulap/both, at: 2026-11-05T11:40:00Z, run: 2026-11-05-1140-c2d9}
    state: open
  - id: D:question/bed
    type: question
    about: L:term/bed#sense
    asks: Is the "bed of crimson joy" a flower bed, a bed of love, or meant as both?
    why: ambiguous
    kind: choice
    options: [a flower bed, a bed of love, both]
    to: expert
    raised: {by: bank, from: fabulap/word, at: 2026-11-05T11:40:00Z, run: 2026-11-05-1140-c2d9}
    state: open
```

#### 18.4.7 Code: the fabulac, the cshort and the catem

**The model for code.** A fabulac is the specification of a program: everything a competent programmer would need, with
the fabulac alone, to write the program again. A **cshort** is source code rebuilt from a fabulac. A **catem** is a text
that says everything a user can do with the program. All three are files that are read; the running program is outside
this document, and no conforming implementation runs, imports or installs a program to decompile it or a cshort to
show it.

<!-- term: cshort -->
A **cshort** is a fabulac's short: a folder of source code rebuilt from the fabulac alone, shown and never run.

<!-- term: catem -->
A **catem** is a fabulac's atem at depth: a markdown text that says what a user can do with the program, at one of three
depths, `line`, `overview` or `manual`.

**What a fabulac holds, facet by facet.**

| Facet | In a fabulac |
|---|---|
| inspiration | the tools, programs and traditions it follows (`I:influence`); what prompted it or a change in it (`I:occasion`) |
| meaning | its own vocabulary (`L:term`), the things it deals with (E), the ideas it relies on (`K:concept`) |
| intent | its aims and audience; every `N:use`, one thing a user can do, end to end; its requirements, with `force` and what meets and checks them; the decisions recorded in its code, documents and history; what it deliberately leaves out (`N:exclusion`) |
| construction | every file of the tree read (`C:file`); its components; every interface a person or another program reaches, with its exact signature; its structures; its behaviours; its dependencies and settings |
| production | its makers, changes, episodes and releases, read from its history; the tools and languages it is made with (`R:means`); its licence (`R:licence`) |
| assertions | what its documents claim (`P:claim`); its cases, from its tests and its documents (`P:case`); the steps of each use, in order (`T:event`) |

**How much detail is enough.** Everything a user or a caller can observe is written exactly; everything that is a
choice inside a function is left to whoever rebuilds it, unless an `N:decision` says why it matters.

| Kind | Enough | Too much |
|---|---|---|
| `C:file` | its path, language, one line on what it holds, the names it defines, its digest and length | its contents, its imports one by one |
| `C:interface` | the exact signature; every parameter with its type, default and meaning; what it returns; every error a caller can see, with its message when a user sees it; whether it is public | its body, its local variables, the order of its statements |
| `C:structure` | every field with its type, default and meaning; the invariants a rebuild must keep (ordering, uniqueness, what is never 0) | how it is built in memory |
| `C:behaviour` | what happens for which input, in plain words and in order: what is read, what is decided, what is written, what is printed; every edge case and error message a user meets; exact output formats where a test or a user depends on them | a line-by-line paraphrase; loop variables; anything a competent programmer would choose the same way unprompted |
| `P:case` | what is given and what is expected, exactly as a test or a document pins them | the test's code |
| `C:dependency`, `C:setting` | the name, the version constraint or default, where it is read, what it changes | its documentation |

A fabulac holds no function bodies and no paraphrase of code line by line.

**The source folder and its licence.** A fabulac's `source` is the folder (section 18.4.1), its freshness the tree
digest. The licence is read from the folder and recorded twice: in `source.licence` and as an `R:licence` item. A folder
with no licence file is still decompiled, with `licence: {pending: "…"}`, and a viewer says that the licence is a
question (`licence-recorded`, section 18.4.8).

**History.** When the folder is a git clone, its history is read from the clone alone: its log, its tags, and the
documents and change logs in the tree. Commits are grouped into episodes (`R:phase`), tags become releases, and authors
become makers: by name only where the repository states that name itself (its licence's copyright holder, a line of an
authors file, or an author or maintainer its packaging file names), otherwise as a numbered contributor, and never by
address. An implementation may bound how much of the log it reads and how many changes it keeps as items; a history that
does not reach the first commit says so, and what is not kept item by item is counted in its episode and its release
(Thym (https://thym.cosmoes.org/), its section 20.6). A folder that is not a clone has only the history its own
documents hold. Issues, pull requests and anything else held outside the clone are reserved for a later edition.

**How a fabulac is built.** In five stages, each one whole run that lands its result before the next begins:

| Stage | Asks a model | Finds |
|---|---|---|
| survey | no | from the syntax tree and the files: every file, its components and interfaces with their names and parameters, its dependencies and settings, its licence and the means it is made with |
| history | no | from the clone: changes grouped into episodes, releases from tags, makers |
| read | yes, once per file | for each file, against the survey: behaviours, structures, cases from the tests, terms, concepts, claims, events |
| fold | yes | over the whole: aims, audience, uses, requirements, decisions, exclusions, inspiration, and the atem |
| question | yes | the dialectic's questions where the build was unsure (section 18.6) |

A file's reading holds only what it adds for its file. It may add to an item of the outline of its own file the fields
its kind takes that the outline lacks (an interface's `takes`, `gives` and `raises`; a structure's `fields` and
`invariants`; a component's `does`; a setting's `means`), and add inside one (a parameter's `means`), never changing
what a rules stage read.

After each stage the fabulac, with what the stage found, is written beside the folder, and a build that stops is resumed
after the last stage that landed, as long as the tree digest has not moved. The fabulac's `derived.runs` lists every
run. A build with no model runs the first two stages only and writes the `outline`: `derived.completeness: outline`, the
files, components, interfaces, dependencies, settings, licence and history, with nothing read for meaning or intent. A
Thym program that builds a fabulac is one file of five programs (Thym (https://thym.cosmoes.org/), its section 20). The
host runs the file's programs as one job, in the order they are written, filling each program's `fabula` input with the
fabulac the program before it landed, and a job that stops takes up again after the last program that landed. Each run
joins `derived.runs`, naming its program in `program` (`survey-the-repo`) and its own trace in `run`.

**What this edition specifies.** A conforming builder handles pure-Python source that a person could read in an
afternoon: no C extensions and no generated code, up to about sixty files and six thousand lines. Larger repositories,
other languages and a fabulac kept as a volume of several files are reserved for a later edition.

**The cshort.** Compiling a fabulac writes a folder beside it, `<name>.cshort-<YYYY-MM-DD-HHMM>/`, holding the rebuilt
tree and a `CSHORT.md`. The cshort rebuilds every `C:file` whose language is a programming language and that is not a
test, nor a type stub (`.pyi`), nor the repository's own tooling (its documentation's build, its scripts, its examples
and benchmarks), and the README; tests are rebuilt only when asked, since their content is held as `P:case` items. It
also carries a packaging file written by rules, never by a model, from what the survey recorded (the project's name, its
version where recorded, the Python floor, the dependencies and optional groups, and the modules and packages with their
layout), its first comment line saying that rules wrote it from the fabulac, so that the rebuilt program can be
installed and its tests run from the folder; where the survey recorded too little to write one truthfully, it writes
none and `CSHORT.md` says why. `CSHORT.md`'s first line is the footer, one italic line naming the fabulac, the language,
the day of the run (in UTC) and the model: "*a cshort of days.fabulac.cosm, in Python, compiled on 2026-11-05 by …*".
Then come a table of the files written, each with the `C:file` it came from (`rules` for the packaging file) and its
sha256, what was not rebuilt, why no packaging file was written when none was, and, last, the source's licence line,
`Licence of the source: <source.licence>` (with none recorded, `Licence of the source: not recorded (<the open
question>)`). A compile is recorded in the fabulac's `shorts:` (section 18.4.1). One fabulac may entail a cshort in another
language than its source's; the entry's `language` names the cshort's own.

A compile passes these checks, all without executing anything:

| Check | Holds |
|---|---|
| `parses` | every rebuilt file in a programming language is parsed by that language's parser with no syntax error. Parsing is not running: nothing is imported, compiled to disk or executed |
| `interfaces-present` | every `C:interface` of the fabulac is defined in the cshort's file it is `defined-in`, with the same name, the same surface and the same parameter names in the same order |
| `files-present` | the cshort holds every file it is required to rebuild, at its path, and the packaging file rules write whenever the fabulac records enough for one, exactly as they write it; and the digests `CSHORT.md` lists are the files' |
| `footer` | `CSHORT.md`'s first line is the footer, naming the fabulac's file, the language, the day of the run (in UTC) and the model; its last line is the licence line, agreeing with `source.licence` |
| `provenance` | the compile is recorded in `shorts:` with `path`, `at`, `by`, `mode`, `order: code`, `route`, `language` and `files`, and the footer names the run |

A conforming implementation shows a cshort, its files and its `CSHORT.md`, read-only. It never runs, imports or
installs a cshort or anything in it. Whether a cshort behaves as the original does is a question for a test outside the
implementation, in a sandbox of its own.

**The catem.** Compiling a fabulac at a depth writes a markdown file beside it, `<name>.catem-<YYYY-MM-DD-HHMM>.md`,
recorded in `catems:`. It ends with one italic footer line naming its depth.

| Depth | Says |
|---|---|
| `line` | the atem's line: what the program does, in one sentence |
| `overview` | every `N:use`, each with what a user types and gets |
| `manual` | every `N:use`, and every interface a person reaches (the command line, the public functions), with what each does, its options and its errors |

The fabulac's own `atem:` stays the four-part atem of section 18.3.5; a catem at depth `line` is that line.

**An example.** A program of one file, `days/days.py`, beside a README and a licence file holding the MIT licence:

```python
"""days: how many days until a date, or since it."""
import argparse
import datetime as dt
import sys

__version__ = "1.0.0"


def parse_date(text: str) -> dt.date:
    """Read a date written YYYY-MM-DD, or the word today."""
    if text == "today":
        return dt.date.today()
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        raise ValueError(f"not a date: {text!r} (write it as YYYY-MM-DD)") from None


def between(start: dt.date, end: dt.date) -> int:
    """Whole days from start to end; negative when end comes first."""
    return (end - start).days


def say(n: int) -> str:
    """One line for a count of days."""
    if n == 0:
        return "today"
    word = "day" if abs(n) == 1 else "days"
    return f"in {n} {word}" if n > 0 else f"{-n} {word} ago"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="days", description=__doc__)
    p.add_argument("date", help="the date, YYYY-MM-DD or today")
    p.add_argument("--from", dest="start", default="today", help="count from this date, not today")
    p.add_argument("--number", action="store_true", help="print the bare number of days")
    args = p.parse_args(argv)
    try:
        n = between(parse_date(args.start), parse_date(args.date))
    except ValueError as e:
        print(f"days: {e}", file=sys.stderr)
        return 1
    print(n if args.number else say(n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

```markdown
# days

How many days until a date, or since it. Python 3.10 or later, nothing else.

    python days.py 2026-12-25                      in 50 days
    python days.py 2026-11-01                      4 days ago
    python days.py 2027-01-01 --from 2026-12-25    in 7 days
    python days.py 2026-12-25 --number             50

A date is written YYYY-MM-DD, or `today`. A date that cannot be read is named on standard error, with exit status 1.
```

Its fabulac, `days.fabulac.cosm`, built in five runs: the survey and the history by rules, the reading of its one
file on a local model, the fold on a cloud model, and the questions on the local model again. It has been compiled
once into a cshort and once into a catem. A fuller fabulac, of a program of several modules with a history and tests,
is in the conformance corpus (section 20.3).

```cosm
oes: fabula/1
macrocosm: 0.5.4
flavour: fabulac
id: fabula/days
name: days
source: {path: days/, kind: folder, language: python, files: 3, bytes: 2988, skipped: 0, tree: c9c7254c01a9935a4bd05457ffa329e1da1e953b409fec26524e8ca5d2490900, licence: MIT}
derived:
  at: 2026-11-05T15:21:40Z
  by: person
  model: g40-04
  route: local
  program: raise-the-questions
  run: 2026-11-05-1521-9e07
  mode: model
  completeness: full
  chunks: 1
  runs:
    - {program: survey-the-repo, run: 2026-11-05-1512-0b31, at: 2026-11-05T15:12:03Z}
    - {program: read-the-history, run: 2026-11-05-1512-7c20, at: 2026-11-05T15:12:05Z}
    - {program: read-every-file, run: 2026-11-05-1513-41aa, at: 2026-11-05T15:14:52Z, model: g40-04, route: local}
    - {program: fold-the-whole, run: 2026-11-05-1515-d3f8, at: 2026-11-05T15:18:30Z, model: vendor/large-model, route: cloud, provider: broker-name}
    - {program: raise-the-questions, run: 2026-11-05-1521-9e07, at: 2026-11-05T15:21:40Z, model: g40-04, route: local}
atem:
  line: days prints how many whole days lie between today, or a date you give, and another date, as a phrase or as a bare number.
  focus: One command that reads one or two dates written YYYY-MM-DD and says the distance between them in days.
  push: Ask a date question in one line and get one line back, with nothing to install.
  pull: Only whole calendar days are counted, so times of day, time zones and dates written in words are outside what it does.
shorts:
  - {path: days.cshort-2026-11-05-1530/, at: 2026-11-05T15:30:12Z, by: vendor/large-model, mode: model, order: code, route: cloud, language: python, files: 2}
catems:
  - {path: days.catem-2026-11-05-1532.md, at: 2026-11-05T15:32:40Z, by: vendor/large-model, mode: model, route: cloud, depth: overview}
nodes:
  - id: I:influence/one-line-tools
    type: influence
    name: One-line tools
    summary: days follows the small command-line tools that answer one question with one line of output.
    stance: assumed
    roles: {source: {pending: "was days modelled on another tool, and which?"}, on: C:interface/command.days}
    provenance: {mode: derived, sources: ['README.md#L1-L3'], confidence: 0.3, state: pending}
  - id: L:term/day
    type: term
    name: day
    summary: The program's unit, a whole calendar day.
    feed: {word: day, pos: noun, origin: feed}
    sense: A calendar day; a count of days ignores the time of day.
    span: {file: days.py, lines: "19-21"}
    provenance: {mode: derived, sources: ['days.py#L19-L21'], confidence: 0.9, state: known}
  - id: N:aim/one-line-answer
    type: aim
    name: A date question in one line
    summary: days sets out to answer how far away a date is with one command and one line of output.
    stance: observed
    measure: Every example in the README prints exactly the line shown beside it.
    roles: {for: N:audience/terminal-users}
    span: {file: README.md, lines: "1-8"}
    provenance: {mode: derived, sources: ['README.md#L1-L8'], confidence: 0.9, state: known}
  - id: N:audience/terminal-users
    type: audience
    name: People at a terminal
    summary: People who keep a terminal open and want a date answer without a calendar or a spreadsheet.
    stance: deduced
    who: a person at a terminal with Python installed
    needs: A quick answer, and a bare number when a script wants one.
    provenance: {mode: derived, sources: ['README.md#L3-L8'], confidence: 0.7, state: known}
  - id: N:use/count-the-days
    type: use
    name: Count the days to a date
    summary: A person asks how many days until or since a date, from today or from another date, as a phrase or a number.
    stance: observed
    for: N:audience/terminal-users
    via: [C:interface/command.days]
    steps: ['python days.py 2026-12-25', 'python days.py 2027-01-01 --from 2026-12-25', 'python days.py 2026-12-25 --number']
    gets: 'One line: "in 50 days", "4 days ago", "today", or the bare number.'
    span: {file: README.md, lines: "5-8"}
    provenance: {mode: derived, sources: ['README.md#L5-L8'], confidence: 0.9, state: known}
  - id: N:requirement/standard-library
    type: requirement
    name: Standard library only
    summary: days runs on Python 3.10 or later with nothing else installed.
    stance: observed
    force: must
    met-by: [C:dependency/python]
    span: {file: README.md, lines: "3"}
    provenance: {mode: derived, sources: ['README.md#L3'], confidence: 0.9, state: known}
  - id: N:decision/iso-dates-only
    type: decision
    name: Dates are written YYYY-MM-DD
    summary: days reads a date only in the form YYYY-MM-DD, or the word today.
    stance: observed
    chose: the standard library's reading of an ISO date, and the one word today
    over: [{option: 'dates in words, such as "next friday"', because: {pending: "why are dates in words not read?"}}]
    span: {file: days.py, lines: "9-16"}
    provenance: {mode: derived, sources: ['days.py#L9-L16', 'README.md#L10'], confidence: 0.8, state: pending}
  - id: C:file/readme-md
    type: file
    name: README.md
    summary: What days does, the Python it needs, four examples with their output, and what happens to a bad date.
    stance: observed
    path: README.md
    language: markdown
    holds: the user's introduction
    length: {lines: 10, bytes: 443}
    sha256: 79477f12994c4a897333b8b63b40871c35ac42c65e1270e01c1eb7c597236a32
    span: {file: README.md, lines: "1-10"}
    provenance: {mode: derived, sources: ['README.md'], confidence: 1, state: known}
  - id: C:file/license
    type: file
    name: LICENSE
    summary: The MIT licence, copyright 2026 Meadow Software.
    stance: observed
    path: LICENSE
    language: text
    holds: the licence
    length: {lines: 16, bytes: 1072}
    sha256: 7a4a44c3502c5f7b39d1ef207e36d4096160690e16886d672d5cd16ca6032f41
    span: {file: LICENSE, lines: "1-16"}
    provenance: {mode: derived, sources: ['LICENSE'], confidence: 1, state: known}
  - id: C:file/days-py
    type: file
    name: days.py
    summary: The whole program, one module run directly.
    stance: observed
    path: days.py
    language: python
    holds: '__version__ = "1.0.0"; parse_date, between, say, main'
    length: {lines: 48, bytes: 1473}
    sha256: 53af8eb68722576d6ccaad6398ec919248c32fa8b0637b58e95bdfadb72bf682
    entry: true
    span: {file: days.py, lines: "1-48"}
    provenance: {mode: derived, sources: ['days.py'], confidence: 1, state: known}
  - id: C:interface/command.days
    type: interface
    name: days
    summary: The command line, one date and two options.
    stance: observed
    surface: command
    signature: 'days [-h] [--from START] [--number] date'
    defined-in: C:file/days-py
    takes:
      - {name: date, type: str, required: true, means: 'the date to count to, YYYY-MM-DD or today'}
      - {name: --from, type: str, default: today, means: 'the date to count from'}
      - {name: --number, type: bool, default: 'false', means: 'print the bare number of days, negative for a past date'}
    gives: {output: one line, exit: 0}
    raises:
      - {error: ValueError, when: either date cannot be read, message: "days: not a date: 'TEXT' (write it as YYYY-MM-DD)"}
    exported: true
    span: {file: days.py, lines: "32-44"}
    provenance: {mode: derived, sources: ['days.py#L32-L44'], confidence: 1, state: known}
  - id: C:interface/days.parse_date
    type: interface
    name: parse_date
    summary: Reads a date written YYYY-MM-DD, or the word today.
    stance: observed
    surface: function
    signature: 'def parse_date(text: str) -> dt.date'
    defined-in: C:file/days-py
    raises: [{error: ValueError, when: the text is not a date, message: "not a date: 'TEXT' (write it as YYYY-MM-DD)"}]
    span: {file: days.py, lines: "9-16"}
    provenance: {mode: derived, sources: ['days.py#L9-L16'], confidence: 1, state: known}
  - id: C:interface/days.between
    type: interface
    name: between
    summary: The whole days from one date to another, negative when the second comes first.
    stance: observed
    surface: function
    signature: 'def between(start: dt.date, end: dt.date) -> int'
    defined-in: C:file/days-py
    span: {file: days.py, lines: "19-21"}
    provenance: {mode: derived, sources: ['days.py#L19-L21'], confidence: 1, state: known}
  - id: C:interface/days.say
    type: interface
    name: say
    summary: One line of words for a count of days.
    stance: observed
    surface: function
    signature: 'def say(n: int) -> str'
    defined-in: C:file/days-py
    span: {file: days.py, lines: "24-29"}
    provenance: {mode: derived, sources: ['days.py#L24-L29'], confidence: 1, state: known}
  - id: C:interface/days.main
    type: interface
    name: main
    summary: Runs the command line and returns its exit status.
    stance: observed
    surface: function
    signature: 'def main(argv: list[str] | None = None) -> int'
    defined-in: C:file/days-py
    gives: {type: int, means: 0 when a line was printed, 1 when a date could not be read}
    span: {file: days.py, lines: "32-44"}
    provenance: {mode: derived, sources: ['days.py#L32-L44', 'days.py#L47-L48'], confidence: 1, state: known}
  - id: C:behaviour/count-and-say
    type: behaviour
    name: Count, then say it
    summary: days counts the whole days from the start date to the date and prints them as a phrase, or as a bare number.
    stance: observed
    of: [C:interface/command.days, C:interface/days.between, C:interface/days.say]
    when: days DATE [--from START] [--number]
    does: 'The count is DATE minus START in whole days. 0 prints "today"; a positive count prints "in N days"; a negative one prints "N days ago" with N positive; "day" replaces "days" when N is 1. With --number the count is printed as it is, sign included.'
    edges:
      - {given: 'days 2026-11-06 --from 2026-11-05', then: in 1 day}
      - {given: 'days 2026-11-05 --from 2026-11-05 --number', then: '0'}
    span: {file: days.py, lines: "24-29"}
    provenance: {mode: derived, sources: ['days.py#L19-L29', 'days.py#L39-L43'], confidence: 1, state: known}
  - id: C:behaviour/bad-date
    type: behaviour
    name: A date that cannot be read
    summary: A date that cannot be read is named on standard error and the program exits with status 1; a usage error is argparse's, status 2.
    stance: observed
    of: [C:interface/command.days, C:interface/days.parse_date]
    does: 'Prints "days: not a date: ''TEXT'' (write it as YYYY-MM-DD)" with TEXT as typed, and nothing on standard output.'
    edges:
      - {given: 'days 2026-02-30', then: an impossible date is refused like any other}
      - {given: 'days 20261225', then: 'refused on Python 3.10; read as 2026-12-25 on 3.11 and later, whose reading of ISO dates is wider'}
    intended: {pending: "should a compact date such as 20261225 be read on every Python, or refused on every one?"}
    span: {file: days.py, lines: "13-16"}
    provenance: {mode: derived, sources: ['days.py#L13-L16', 'days.py#L40-L42'], confidence: 0.9, state: known}
  - id: C:dependency/python
    type: dependency
    name: Python 3.10 and its standard library
    summary: days needs Python 3.10 or later, for its annotations, and uses only argparse, datetime and sys.
    stance: observed
    package: python
    version: '>=3.10'
    scope: standard
    needed-for: everything
    used-by: [C:file/days-py]
    span: {file: days.py, lines: "2-4"}
    provenance: {mode: derived, sources: ['README.md#L3', 'days.py#L2-L4'], confidence: 0.9, state: known}
  - id: R:licence/mit
    type: licence
    name: MIT
    summary: days is under the MIT licence, copyright 2026 Meadow Software.
    stance: observed
    identifier: MIT
    file: LICENSE
    holder: Meadow Software
    year: '2026'
    first-line: MIT License
    span: {file: LICENSE, lines: "1-3"}
    provenance: {mode: derived, sources: ['LICENSE#L1-L3'], confidence: 1, state: known}
  - id: P:case/four-examples
    type: case
    name: The README's four examples
    summary: The four examples of the README, counted from 2026-11-05, print the lines the README shows.
    stance: observed
    of: [C:behaviour/count-and-say, N:use/count-the-days]
    given: {env: 'today is 2026-11-05', arguments: ['2026-12-25', '2026-11-01', '2027-01-01 --from 2026-12-25', '2026-12-25 --number']}
    expect: {output: ['in 50 days', '4 days ago', 'in 7 days', '50'], exit: [0, 0, 0, 0]}
    span: {file: README.md, lines: "5-8"}
    provenance: {mode: derived, sources: ['README.md#L5-L8'], confidence: 1, state: known}
  - id: D:question/compact-dates
    type: question
    about: C:behaviour/bad-date#intended
    asks: Should a compact date such as 20261225 be read on every Python, or refused on every one?
    why: intent
    kind: choice
    options: [read everywhere, refused everywhere]
    to: maker
    raised: {by: model, from: fold, at: 2026-11-05T15:21:40Z, run: 2026-11-05-1521-9e07}
    state: open
  - id: D:question/dates-in-words
    type: question
    about: N:decision/iso-dates-only#over[0].because
    asks: Why are dates in words, such as "next friday", not read?
    why: missing
    kind: text
    to: maker
    raised: {by: bank, from: fabulac/tried, at: 2026-11-05T15:21:40Z, run: 2026-11-05-1521-9e07}
    state: open
```

The first lines of its cshort's `CSHORT.md`:

```markdown
*a cshort of days.fabulac.cosm, in Python, compiled on 2026-11-05 by vendor/large-model (cloud, broker-name); never run*

| file | from | sha256 |
|---|---|---|
| README.md | C:file/readme-md | <the sha256 of the file as written> |
| days.py | C:file/days-py | <the sha256 of the file as written> |

Not rebuilt: LICENSE (its licence is named below).

No packaging file was written: the fabulac does not record the project's name (its survey read no packaging file that names one).
```

Its catem at depth `overview`, `days.catem-2026-11-05-1532.md`:

```markdown
# What you can do with days

days says how many whole days lie between two dates. It needs Python 3.10 or later and nothing else. Run it as
`python days.py`.

## Count the days to a date

`python days.py DATE` says how far DATE is from today: `in 50 days`, `4 days ago`, or `today`, with `day` for a count of
one. `--from START` counts from START instead of today. `--number` prints the bare number, negative for a date already
past. A date is written YYYY-MM-DD, or `today`.

## When a date cannot be read

The date is named on standard error, as in `days: not a date: '2026-02-30' (write it as YYYY-MM-DD)`, and the exit
status is 1. A command typed wrongly prints the usage, with exit status 2.

*a catem of days.fabulac.cosm, at depth overview, compiled on 2026-11-05 by vendor/large-model (cloud, broker-name)*
```

#### 18.4.8 The fabula's checks

A fabula runs the generic checks of section 12.2 and its own. `fabula-checks` is the name a contract uses for all of
them passing with no error; its old name, `emf-checks`, is read wherever a manifest, a program or a trace says it.

| Check | Severity | Holds |
|---|---|---|
| `load` | error | as section 12.2 |
| `duplicate-id`, `id-grammar`, `id-module`, `type`, `type-prefix` | error | as section 12.2, over the modules I L E K N C R P T X D |
| `identity-min` | error | every item carries the fields its kind requires (section 18.4.2) |
| `provenance` | error | as section 12.2 |
| `status`, `visibility` | error | as section 12.2 |
| `ref-grammar`, `ref-unresolved` | error | every reference field of section 18.4.2 names an item of the fabula |
| `closed-list` | error | every closed list: `stance`, `salience`, `feed.origin`, the nine relations, and the closed lists of section 18.4.2 and of the dialectic |
| `pending-shape` | warning | as section 12.2 |
| `catalog-key` | error, or a note | as section 12.2; the id may keep the old form `emf/<slug>` |
| `flavour` | error | the catalog's `flavour` is `fabulan`, `fabulap` or `fabulac`, or absent |
| `flavour-kind` | error | every item's kind belongs to the catalog's flavour: "C:line/1: a line belongs to fabulap, not to a fabulan" |
| `code-span` | error | in a fabulac, every `span` is `{file, lines}`; its `file` is the path of a `C:file` of the fabulac; its `lines` are `n` or `n-m`, with n no greater than m, within the file's `length.lines` |
| `licence-recorded` | error; a warning while pending | a fabulac records `source.licence`, a value or a question, and holds an `R:licence` item |
| `question-about` | error | a question's `about` names an item, an item's field, a span of the right shape (in a fabulac, one whose file and lines exist), or a module or kind the fabula declares; a settled, stale or withdrawn question is skipped (section 18.6) |
| `question-shape` | error | a question's answers agree with its state (section 18.6) |
| `session-declared` | warning | a source `D:session/<id>` names a session of the fabula; the bare forms `session-<n>` and `elicit-…` are accepted without one |
| `reading-whose` | warning | an author's or an expert's reading names the session it was given in; a critic's names the critic, or asks who |
| `interface-signature` | warning | a `function`, `method`, `class`, `command` or `format` interface carries its `signature` |
| `case-outcome` | error | a case says what is given and what is expected |

The generic reader runs the checks of section 12.2, and `flavour` and `flavour-kind`, which the manifest drives. The
others are the fabula's own, run by the reference implementation, enough (https://github.com/0gsd/enough); a reader that
does not run them lists them as not run (section 12.3).

### 18.5 doc: documents (DocOES)

<!-- atem: one document taken apart into items and compiled back, byte for byte -->
**What it enumerates.** One document, taken apart and given back.

<!-- term: DocOES -->
**DocOES**, *Documentation OES*, takes a markdown document apart into items:
its sections, the terms it defines, the complete examples it shows and the decisions it records. It joins them to
items generated from the manifests (every format, module, kind, closed list, check and lens) and, for
enough's own manual, to the help bubbles that sit beside the controls. A doc volume is a document's fabula: the
material, item by item. Its short is the readable manual, compiled as told, and it gives back the markdown the
author wrote, byte for byte. This specification is enumerated this way, and so is enough's Help Center, in each of its
six languages.

**Its declaration.** `oes: doc/1`. There is no legacy form, and a catalog without the key is refused.

**Its volume.** One file per telling, `<doc>.<lang>.doc.cosm`: `macrocosm-oes.en.doc.cosm`,
`help-center.fr.doc.cosm`. enough builds it at runtime into its own state from the markdown and the manifests, and
builds it again whenever the document, a chapter, any manifest or enough's own version changes. It is never written by
hand, never committed and never shown in the file tree. The markdown stays the authoring surface: to change a doc
volume, change its document. The reference enumeration is enough's.

#### 18.5.1 The catalog

| Key | Holds |
|---|---|
| `oes` | `doc/1` |
| `macrocosm` | reserved (section 5.6) |
| `id` | `doc/<slug>`: `doc/macrocosm-oes`, `doc/help-center`. Every telling of a document has the same id |
| `name` | the document's title |
| `document` | the markdown this telling was enumerated from: `{path, sha256, version}` |
| `telling` | `{lang, voice}`: the language, one of `en`, `de`, `es`, `fr`, `ja` and `zh`; and the voice the document is written in, when it has one (the Help Center's is `rosa`) |
| `tellings` | the languages the document is written in |
| `chapters` | the synced documents inside the volume, one `{id, path, source, commit, sha256, prefix, version}` each |
| `built` | `{at, by, digest, manifests}`: when, by which enough, the digest of everything the volume was built from, and each manifest's `{name, version, sha256}` |
| `nodes` | the items |

#### 18.5.2 The modules and their kinds

| Letter | Module | What it holds | Kinds |
|---|---|---|---|
| S | Structure | what the document is made of | `section`, `example`, `decision`, `chapter` |
| T | Terms | the words it defines | `term` |
| R | Reference | what the manifests declare | `minicosm`, `module`, `kind`, `list`, `check`, `lens` |
| B | Bubbles | the help that sits beside a control | `bubble` |

| Kind | What it is | Reference fields | Its own fields |
|---|---|---|---|
| `section` | a heading and the text under it, down to the next heading | `parent`, `parts`, `mentions` | `number`, `level`, `heading`, `body`, `lines`, `order`, `anchor`, `xrefs` |
| `example` | a complete file the document shows in a block marked `cosm` | `in`, `declares` | `declaration`, `body`, `lines` |
| `decision` | one numbered decision of a section of decisions | `in`, `about` | `number`, `body`, `lines`, `xrefs` |
| `chapter` | a synced document inside the volume, read-only, in its author's own words | `parts` | `path`, `source`, `commit`, `sha256`, `prefix`, `version` |
| `term` | a word the document defines | `defined_in`, `also_defined_in`, `same_as` | `convention`, `in_the_files`, `lines` |
| `minicosm` | a format, built in or a MiniCOSM, as its manifest declares it; the kind keeps the name it was first written with | `modules`, `lenses` | `declaration`, `version` |
| `module` | a module of a format | `of`, `kinds` | `letter` |
| `kind` | a kind of a module, with the fields its manifest names | `of`, `lists` | `refs`, `fields`, `required`, `declared` |
| `list` | a closed list of values, with what each value means where this document says | `of` | `field`, `values`, `meanings` |
| `check` | a check, with the formats that select it | `selected_by` | `severity` |
| `lens` | a lens a format declares, or the generic one it gets | `of`, `draws` | `lens` |
| `bubble` | a help bubble: what a control is, how to use it, and ideas for it | `see` | `about`, `path`, `what`, `how`, `ideas`, `xrefs` |

**Envelope.** Required: `id`, `type`, `name`, `summary`. DocOES adds `atem`, `body`, `lines`, `order` and `chapter`
to the envelope, and `chapter` is a reference. Its status list adds two words to Comprise's four: `pending`, an item
proposed and not yet settled, and `attic`, an item retired that still resolves. **Closed lists:** a term's
`convention` (`table`, `bullet`, `sentence`, `glossary`, `marker`) and six link relations, `mentions`, `defines`,
`exemplifies`, `decides`, `see` and `same_as`. **Checks:** `load`, `duplicate-id`, `id-grammar`, `id-module`, `type`,
`type-prefix`, `identity-min`, `status`, `visibility`, `ref-grammar`, `ref-unresolved`, `closed-list`,
`pending-shape`, `catalog-key`, and seven of its own (section 18.5.4).

#### 18.5.3 The conventions, in plain words

**Every item has an atem.** `atem` is the one line the atem density shows: two to fifteen words (in Japanese and
Chinese, two to forty-five characters), one phrase, no final period, no ids and no markup, and unlike the atem of any
other item with the same name. It is made by rule, never by a model. A section's atem is the first sentence of its
first paragraph, cut at a clause break when it runs long; an HTML comment `<!-- atem: … -->` on the first line under
a heading sets it by hand, as this section's does. A term's atem is its definition, and a reference item's is this
specification's own line for it, or its manifest's subtitle. A model may offer a better line in the viewer, on
request; it is never written into the volume.

**Sections.** Every heading of the document is a section, except a heading inside a fenced block. A numbered heading
takes its number as its id: `### 18.3 canon: Canon, the home file system` is `S:section/18.3`, and Comprise's `#### P.3` is
`P.3`. The title is `S:section/root`, any text before it `S:section/front`, and any other heading without a number
takes its text, slugged: `S:section/how-to-read-this`. A section's `body` is the markdown between its heading and the
next heading, verbatim and never re-flowed; `heading` is the heading line itself; `lines` says where both are, and
`order` is the section's place in the telling. Its `parts` are the sections under it, and its `parent` the one above.

**Terms.** A term is enumerated where the document defines it in one of the conventions this specification and the
Help Center already use: a table row whose first cell is bold; a bullet that opens with a bold phrase and a dash or a
colon, `- **term** — what it is`; a paragraph that opens `**term** is …` or `A **term** is …`; and the first column
of the "How to read this" table, which defines only the words nothing else defines. Where no convention fits, an
HTML comment `<!-- term: x -->` before a paragraph makes the paragraph the definition of x. A term is defined once; a
second definition is kept as `also_defined_in` and reported.

**Mentions are computed.** A section's `mentions` are the sections it names ("section 18.4", "sections 4 to 14") and
the terms it uses, outside code. A term's use counts when it is written in bold anywhere, and in plain text when its
name is distinctive (more than one word, or a capital or a digit inside it); in this specification every plain use
counts. "Its section 10" names another document's section and is not a mention. What mentions an item is never
stored: a viewer reverses the typed links when it loads the volume.

**Examples.** Every block marked `cosm` is an example, `S:example/<n>`, numbered through the document. Its `body` is
the block, `declares` the format its declaration names, as a reference item, and `in` the section it is in. A block
marked `yaml` or `text` stays part of its section's body. A viewer loads an example as a volume of its own, checks it
and draws it.

**Decisions.** The numbered items of a section called "Decisions …" whose first words are bold are decisions,
`S:decision/<n>`: the bold words are a decision's name, and `about` the sections and terms it names.

**The reference, generated.** For every manifest in the registry the volume holds `R:minicosm/<name>`,
`R:module/<name>.<L>`, `R:kind/<name>.<L>.<kind>` with the kind's reference fields, checked fields, required fields
and closed lists, `R:list/<name>.<field>` for each closed list, and `R:lens/<name>.<lens>`; and `R:check/<id>` for each
generic check and each of DocOES's own, with the formats that select it. Each says where it came from:
`provenance: {mode: catalogue, sources: ['fabula.manifest.cosm#modules.P.kinds.claim'], hash}`,
the hash taken over that part of the manifest. The hand-written line for a check, a lens, a format, a kind or a
value of a closed list stays in this specification's own tables, joined by the id in the first cell: the checks of
sections 12.2 and 18.5.4, the lenses of section 14.5, the formats of sections 18.1 and 19, the kinds of sections 18.2,
18.3.2, 18.5.2 and 19.2, and the stances and relations of section 18.4.3. Nobody edits a generated item; its words are changed
where they are written.

<!-- term: chapter -->
A **chapter** is a document synced into the volume, read-only, in its author's own words, recorded with the commit it
came from and each file's sha256. A chapter's items take its prefix: a chapter with the prefix `comprise` gives
`S:section/comprise.4.1` and `T:term/comprise.concern`, and its `S:chapter/<slug>` item carries `provenance: {mode:
catalogue, sources: ['<repository> <path> @ <commit>'], hash}`. A chapter's term with the name of one of the document's
terms is `same_as` it.

**References across volumes.** Each doc volume has an inventory: one row per item, with its id, kind, version, anchor
and atem. A chapter has an inventory of its own, named by its prefix. A reference into another volume, or into a
chapter, is written `<inventory>@<version>:<kind>:<id>`, as in `comprise@1:section:2.5`, and kept in the item's
`xrefs`. It is not a reference in the sense of section 9, since a URI between volumes is a value (section 9.3); the
check `xref-unresolved` resolves it through the inventory instead.

<!-- term: telling -->
A *telling* is one language a document is written in, a volume of its own. All the tellings of a document share one
set of ids: the fabula has no language, and a section's name and body are its telling's. A translated telling takes
its ids from the author's, its sections by number and its terms by their place in the section; where a place cannot be
matched, the item is taken from the author's telling and says so, `fallback: en`. The word names this alone: what a
fabula is compiled into is an entailment (section 18.1).

**Voice.** The catalog's `telling` names the voice a document is written in. The Help Center's is `{lang: en, voice:
rosa}`, so a viewer can say who wrote it and a readvisor can quote it as hers.

**Bubbles.** In the Help Center's volume, each section of enough's help-bubbles document, or of its translation, is a
bubble,
`B:bubble/<id>`: its `what`, `how` and `ideas` verbatim, `about` the control it sits beside (its `data-help` id), and
`see` the manual's sections it names. A bubble about another document names that document's sections instead, and
keeps them as references across volumes, `xrefs`: the docs viewer's bubble points into this specification. Its atem
is the first sentence of `what`.

**Three densities.** A viewer shows a doc volume at three densities: the **fabula**, each item as a full card; the
**short**, the readable manual, compiled as told; and the **atem**, the document as an outline of its items' one-line
atems. Compiled as told, a doc volume's sections, each its heading and then its body, in `order`, are the document
again, byte for byte. That round trip is tested for this specification and for each telling of the Help Center.

**In enough.** The docs viewer shows the documents it holds at the three densities, from a project or from the home screen,
with no model needed. It asks for one telling at one density (`GET /api/docs?doc=&lang=&density=`), and the volume is
built the first time it is asked for, or again when its digest has moved; it draws a local graph around an item
(`GET /api/docs/lens`, section 14.4), loads a live example as a volume from text (`POST /api/cosm/inline`), and gives
back the markdown, byte for byte (`POST /api/docs/compile`). `GET /api/docs/inventory` serves the inventory. A
readvisor asks the same volumes with the tool `doc_lookup`: a word, a section number or an id, answered with its atem,
its definition and where it is defined.

#### 18.5.4 Its own checks

| Check | Default severity | Catches |
|---|---|---|
| `atem-shape` | error | an item with no atem; an atem that is not one phrase of two to fifteen words with no final period, ids or markup; one that repeats the atem of another item with the same name |
| `numbering` | error | a section number used twice, one that skips or repeats among its siblings, or one that does not start with its parent's |
| `term-defined-once` | warning | a term the document defines more than once; the first definition is kept |
| `unlinked-mentions` | note | a paragraph that opens with a bold phrase the way a definition does, when no term is enumerated for it |
| `empty-section` | note | a heading with no body and no sections under it |
| `stale-provenance-hash` | warning | a generated item whose part of a manifest has changed; a chapter that differs from its recorded copy; a document changed since its volume was built |
| `xref-unresolved` | error | a reference across volumes that names nothing in its inventory; a note when that inventory was not given |

A generic reader lists these seven as not run; enough runs them with the generic ones.

#### 18.5.5 An example

The text, a small handbook in the spirit of section 18.4.5, `handbook.md`:

```markdown
# The Meadow handbook

## 1. The close

<!-- atem: how Meadow locks a day of the books -->
A **close** is the overnight run that locks one day of a customer's books.

### 1.1 When a close fails

A failed close is retried at five. Section 1 says what it locks.
```

Its doc volume, as enough builds it. Compiled as told, its three sections give the text back exactly.

```cosm
oes: doc/1
macrocosm: 0.0.1
id: doc/meadow-handbook
name: The Meadow handbook
document:
  path: handbook.md
  sha256: 6a88887fd059cbf9f2ee82fb2648dccc14e728f27a995760c309f667ae2b4c2a
  version: '1'
telling:
  lang: en
tellings:
- en
built:
  at: '2026-10-23T10:00:00Z'
  by: enough/0.4.4
  digest: dcf85812fbb3650e52f42cf61a4a3d5c7f709d4a34f168d3a50efb278910a4d3
  manifests:
  - name: doc
    version: 1
    sha256: ffa5a64f64b05ca3ca61b1656525870773afa8c54305e9d7f6ad0a2bdaa2a213
nodes:
- id: S:section/root
  type: section
  name: The Meadow handbook
  summary: 'The Meadow handbook: The close'
  atem: 'The Meadow handbook: The close'
  level: 1
  heading: '# The Meadow handbook'
  parts:
  - S:section/1
  order: 1
  lines: 1-2
  anchor: the-meadow-handbook
  provenance:
    mode: derived
    sources:
    - handbook.md#L1-L2
    confidence: 1
    state: known
  body: |2+

- id: S:section/1
  type: section
  name: The close
  summary: A close is the overnight run that locks one day of a customer's books.
  atem: how Meadow locks a day of the books
  number: '1'
  level: 2
  heading: '## 1. The close'
  parent: S:section/root
  parts:
  - S:section/1.1
  order: 2
  lines: 3-7
  anchor: sec-1
  provenance:
    mode: derived
    sources:
    - handbook.md#L3-L7
    confidence: 1
    state: known
  body: |2+

    <!-- atem: how Meadow locks a day of the books -->
    A **close** is the overnight run that locks one day of a customer's books.

- id: T:term/close
  type: term
  name: close
  summary: A close is the overnight run that locks one day of a customer's books.
  atem: the overnight run that locks one day of a customer's books
  defined_in: S:section/1
  convention: sentence
  order: 3
  lines: '6'
  provenance:
    mode: derived
    sources:
    - handbook.md#L6
    confidence: 1
    state: known
- id: S:section/1.1
  type: section
  name: When a close fails
  summary: A failed close is retried at five.
  atem: A failed close is retried at five
  number: '1.1'
  level: 3
  heading: '### 1.1 When a close fails'
  parent: S:section/1
  mentions:
  - S:section/1
  - T:term/close
  order: 4
  lines: 8-10
  anchor: sec-1-1
  provenance:
    mode: derived
    sources:
    - handbook.md#L8-L10
    confidence: 1
    state: known
  body: |2

    A failed close is retried at five. Section 1 says what it locks.
```

### 18.6 The dialectic

<!-- atem: asking a person what a source means, and writing down the answer -->
<!-- term: dialectic -->
The **dialectic** is the core's one primitive for asking a person what a source means and recording what they say.
Every format inherits it: a fabula, a Canon volume, a document, a holograph and a Holotype ask and record the same way.

It exists because some of what a volume should hold is not in its source. A poem cannot be decompiled well without its
author, or an expert in the author's work: who speaks, to whom, whether an echo was meant, what was cut. A fabulac
improves the same way when the people who made the program say why a decision was made and whether a behaviour is
intended. A person fills in a holograph by being asked about themselves, and a company fills in its Holotype by being
asked about its concerns. In each case a program finds what it cannot know and a person says it.

<!-- term: question -->
A **question** asks one thing about one place in a volume. It is asked exhaustively but quickly: every question a
volume raises is put to someone in the end, one at a time, in plain words, in no one's voice. A question never
leads, never flatters and never speaks as the program or as anyone else; `{name}` and the item's own words are the only
particulars it carries.

#### 18.6.1 Two whole steps, never a waiting run

The dialectic is two runs with a person between them. Nothing waits inside a run.

1. **A run lands questions.** A program (Thym's `question` move, section 18.6.7) reads a volume and writes its open
   questions into it as items. The run is atomic: it lands every question it raised or none.
2. **A person answers.** At a screen, or through an agent that puts one or two questions at a time, the person answers,
   says "I don't know", declines, or skips. Their answers are recorded against the questions (`record`, by code and with
   no model), with the session they were given in: into the volume at once, or into an answers volume beside it that
   the second run reads (Thym (https://thym.cosmoes.org/), its section 22.2). No item the questions are about changes
   yet.
3. **A second run settles.** A program (`settle`) folds the answered questions into the items they are about and lands
   the result, atomic in the same way.

Nothing partial is ever landed, and every run replays: a replay of either run needs neither the person nor the model.
A volume between the two runs is whole and passes its checks; it simply holds open or answered questions.

#### 18.6.2 Module D

Module **D** (*Dialectic*) holds two kinds: `question` and `session`. Any volume may carry it, and every format
inherits it from the core without declaring it. The letter D is the core's in every format: no format gives it to a
module of its own, and a reader merges the core's module D into every manifest that does not declare it (section
13.4). Items of D carry the envelope's `id` and `type` and the fields below; each kind's own `required` replaces the
format's envelope requirements (section 13.5), and they need no `provenance` of their own, because the record is the
provenance.

**`D:question/<slug>`**: one question about one thing. Required: `id`, `type`, `about`, `asks`, `why`, `kind`, `to`,
`raised`, `state`.

| Field | Holds |
|---|---|
| `about` | what the question is about: an item id; an item id, `#` and a field path (section 11.2), `N:audience/owners#who`, which may point at a field that is absent or pending; a span of the source (`{lines}`, `{start, end}`, or `{file, lines}` in code); or, for a bank question asked of the volume with no item to attach to, the module (`I`) or the kind (`N:audience`) its bank entry names |
| `asks` | the question, in plain words and in no one's voice, `{name}` already filled |
| `why` | why it is asked, from a closed list: `missing` (nobody has said) · `unsure` (an item below confidence 0.5, or pending) · `ambiguous` (two readings stand) · `intent` (was it meant) · `conflict` (two answers or two items disagree) · `counter` (a check refused an answer; asked again differently) |
| `kind` | the answer's shape, from a closed list: `text` · `choice` · `yes-no` · `number` · `date` · `ref` · `span` |
| `options` | for `choice`, the choices (required); for `ref`, the id prefixes the answer may name (optional) |
| `options-open` | `true` when a `choice` also takes a word outside `options` |
| `many` | `true` when the answer is a list |
| `range` | `[low, high]`, for `number` |
| `hint` | a line shown under the question |
| `to` | who can answer: `author` · `expert` · `maker` · `holder` (Ascribe's subject) · `owner` (Comprise's item owner) · a role's id · `anyone` |
| `raised` | `{by, from, at, run}`: `by` is `bank`, `move`, `model` or `person`; `from` the bank entry (`fabulap/speaker`), the move or the stage that raised it; `at` a timestamp; `run` the run's trace id |
| `state` | `open` · `answered` · `unknown` · `declined` · `stale` · `withdrawn` (section 18.6.3) |
| `answers` | the answers, appended and never rewritten: each `{at, by, says, value, confidence, session, declined}`. `by` is a word of `to` or a role's id; `says` the person's words, verbatim; `value` what is written (null for "I don't know" and for a refusal); `confidence` how sure the person is, 0 to 1, and 1 for a value given with none (absent on "I don't know" or a refusal unless the person gave one); `session` the session's id; `declined: true` on a refusal |
| `settled` | `{at, run, wrote}`, written by `settle`: when, in which run, and the addresses it wrote (`[N:audience/owners#who]`). Absent until then |
| `ended` | `{at, by, because}`, for `stale` and `withdrawn` |

<!-- term: session -->
**`D:session/<slug>`**: one **session**, a sitting in which a person was asked questions. Required: `id`, `type`, `at`,
`with`, `through`.

| Field | Holds |
|---|---|
| `at` | when it began |
| `with` | `{to, who}`: the answerer's word from `to`, and a plain description of them. Never a name where the format forbids one (Ascribe, Comprise OES) |
| `through` | `person` (a person at a screen) or `agent` (an agent putting one or two questions at a time) |
| `model` | the agent's model, when `through: agent` |
| `covers` | `{part, module}`: the part and the module the session was about; a sitting across the whole volume is `{module: '*'}`, with no `part` |
| `asked`, `answered`, `skipped` | the session's questions, each in the order it happened: references to `D:question` items, or, where a format asks from a bank without writing question items, the addresses asked, `<item id>#<field path>` |

**Closed lists.** `why`, `kind`, `state` (of a question) and `through` (of a session) are closed, as above; a value
outside them fails `closed-list`. They apply to items of D only, never to a field of the same name in another module.
`answers.session` and a session's `asked`, `answered` and `skipped` are reference fields and must resolve; an
address resolves as section 9.3 says.

**Ids.** The slug of either kind is any slug of section 11.1. A session's slug may be `session-<n>` or
`elicit-<date>-<hex>`, the spellings Ascribe and Comprise OES use: `D:session/session-3` and
`D:session/elicit-2026-11-02-a3f9` are those sessions.

**Where the items live.** In a single-file volume, in the catalog's `nodes:` with the other items (section 6.5). In a
folder volume, in module files in the place the manifest gives module D, in the part the questions are about; where a
layout puts each module in a folder named by its letter, that folder is `D`. A question about an item of another part
names it by its qualified id (section 6.4). A MiniCOSM's own specification may say where its volumes keep these items:
Comprise OES keeps each session as a record under its catalog's `sessions:` and writes no question items, asking each
bank question of a field directly (Comprise OES (https://comprise.cosmoes.org/), its section 8). An answer to such an
address, asked without a question item, reaches an answers volume as an entry `{about, answers}` (Thym
(https://thym.cosmoes.org/), its section 22.2).

#### 18.6.3 The life of a question

| From | To | Moved by | What is written |
|---|---|---|---|
| (none) | `open` | a run (`question`): from a bank, from every open question and every item pending or below confidence 0.5, or raised by the model while reading; or a person raising one by hand | the question, with `raised`; nothing else changes |
| `open` | `open` | the person skips it | the session's `skipped` gains it; the question is unchanged |
| `open` | `answered` | `record`: an answer with a value | an answer appended; the item it is about is not touched yet |
| `open` | `unknown` | `record`: "I don't know" | an answer with `value: null` and the person's words in `says` |
| `open` | `declined` | `record`: a refusal to say | an answer with `declined: true` |
| `answered`, `unknown`, `declined` | the same, settled | a run (`settle`) | what section 18.6.4 says, into the item; the question gains `settled` |
| any | `open` | a person, a bank or a move asks again: another person, an expert after the author, a later session | earlier answers kept; the next answer is appended; an earlier `settled` stays as the record of the earlier write until the question is settled again, when the new settling replaces it (the earlier answer stays in `answers`) |
| `open`, `answered` | `stale` | `question` or `settle` finds that `about` no longer holds: its item is gone, the field was dropped (it held a value in the volume before and is absent now), or the source changed and the span's words are not found | `ended`, by the move, with the reason; nothing is written into items |
| `answered`, settled | the same | its own answer removed the item it is about, as a candidate a holder refuses is removed | nothing: the question keeps `settled` and its answers as the record, is not `stale`, and is not raised again |
| any | `withdrawn` | whoever raised it, or a move that finds it duplicates another | `ended`, with who and why |

**Re-asking appends.** A question keeps its id for its whole life. Answers are appended, never rewritten or removed,
so a volume shows everything anyone said and when. At most one question is open for one address from one bank entry,
move or person.

**A decompile done again** carries every D item over to the new volume when its `about` still resolves there, with
its answers, its state and its sessions. A question whose `about` no longer resolves goes `stale`. Settled answers are
not written again: the new decompile reads the source afresh, and an open question about what it found is raised anew.

#### 18.6.4 What an answer writes

`settle` writes each answer into what its question is `about`:

| `kind` | Written into a field | When `about` is a module or a kind |
|---|---|---|
| `text` | the answer, a string | a new item of the kind the bank entry `writes` (or, where the entry names none, the module's kind named like the entry's id, where it has one, else the module's first kind; section 18.6.6): `name` its first words, `summary` the answer, where the kind requires a stance, `stance: hearsay`, and every other field the kind requires, which the answer cannot fill, as an open question, `{pending: "what is the <field> of this <kind>?"}` (section 10), for a later run to ask |
| `choice` | one of `options` (or an open word where `options-open`) | as `text` |
| `yes-no` | `true` or `false` | not allowed: a yes-no question is always about a field |
| `number` | a number inside `range` | not allowed |
| `date` | an ISO date, a year or a year-month, as text when it is not a full date | not allowed |
| `ref` | an item's id that resolves, never an address (a list when `many`) | not allowed |
| `span` | a span, into `span` or appended to `grounds` | not allowed |

| The answer | The question | The item |
|---|---|---|
| a value | `answered` | the field holds the value |
| "I don't know" | `unknown` | the field stays an open question, `{pending: "<the person's own words>"}` (section 10) |
| a refusal | `declined` | the item gains `withheld: [<field path>]` and `provenance.state: not-disclosed` (section 8.5); a pending value there is removed |
| skipped | `open` | nothing |

**"I don't know" is an answer.** It is recorded, it closes the question, and the field stays open in the person's own
words, which are a better question than the one asked. **A refusal is a fact**, not a question: the subject declined to
say, and no later run asks the same person again unless a person opens the question again.

**An answer about a whole item** (`about: <item id>`). A value means the item must be read again (below). "I don't
know" gives the item `pending: "<the person's own words>"`. A refusal sets its `provenance.state: not-disclosed` and
removes its own `pending`, and lists nothing in `withheld`, since no field was asked.

**The provenance of what is written.** A new item carries `provenance: {mode: dialectic, sources: [D:session/<id>],
confidence: <the answer's>}`: the session is its source and the person's own confidence is its confidence. A field of
an existing item leaves the item's mode and its `provenance.state` as they were; the session's id is appended to the
item's `provenance.sources`, and `provenance.answered` gains one entry for the field, `{<field path>: {sources:
[D:session/<id>], confidence}}`. An item with no `provenance` gains one: `{mode: dialectic, sources:
[D:session/<id>], confidence}`, with that entry in `answered`.

**Rules first, the model only to read again.** `settle` writes every answer by rules, and asks a model only where an
item must be read again in the light of an answer: a value about a whole item or about a span of the source, a value
that would replace a mapping or a list in a field (other than a `many` list or a span), and a yes-no answer about a
field that holds something other than `true` or `false`. A yes-no answer into a field that holds `true` or `false`,
such as a reading's or a behaviour's `intended`, is written by rules. A run with no model leaves an answer that must
be read again `answered` and unsettled.

**A settle run is recorded.** In a fabula, a settle run joins `derived.runs` and changes none of `derived`'s single
keys, which describe the last run that derived the fabula from its source (section 18.4.1).

**A write that would add a check error is not made.** The answer stays recorded and the question stays as it was, and a
sibling question about the same address is raised with `why: counter`, asking again differently (a bank's `counters`
give its words; section 18.6.6). While the counter question stands, the question it counters waits: no run tries its
answer again, and settling the counter does not settle it.

#### 18.6.5 Open questions and the dialectic

The two are one thing in two lengths. `{pending: "…"}` (section 10) stays the inline short form, written where the value
would go, and every reader that lists open questions keeps working. A `D:question` is its long form: the same open
question with an address, an answerer, a reason, a shape and a record of what was said. A question raised about a
pending field is `about: <item>#<field>`, `why: missing`, `kind: text`, and `asks` the pending text with its first
letter capitalised when it is a question; words that are not become one, made from the field and the item's name, with
the words as its `hint` (`What is the reason for "Not thread-safe"?`). Settling an answer replaces the pending value;
settling "I don't know" rewrites it in the person's words. A volume may hold either form, or both for one field, and
neither is ever an error.

An item below confidence 0.5, or whose `provenance.state` is `pending`, raises one question about the whole item:
`why: unsure`, `kind: text`, asking whether the item is right and, if not, what is, with its summary quoted. An item
that holds a pending of its own raises the questions of its pending values instead, since they say what is unsure.

#### 18.6.6 Banks

<!-- term: bank -->
A **bank** is a format's list of opening questions, kept in its manifest's `dialectic:` key: what to ask of any volume
of the format before anything else is known.

```yaml
dialectic:
  writes: <one line: what an answer writes>
  answer-kinds: [text, choice, yes-no, number, date, ref, span]
  entry-fields: [id, about, asks, kind, options, to, why, many, hint, writes, only-with, at-most]
  banks:
    <bank name>:
      for: {flavour: fabulap}                # or {module: S}, or nothing: the whole format
      to: author                             # the default answerer; an entry may name another
      intro: <optional>
      counters: {<check id>: <question>}     # optional: the counter question for a refused write
      questions:
        - {id: speaker, about: C:voice#roles.speaker, asks: "Who is speaking in {name}?", kind: text, why: unsure}
```

An entry's `about` names a module (`I`: asked once of the volume), a kind (`C:voice`: asked of each item of that kind)
or a kind's field (`C:voice#roles.speaker`: asked of each item where the field is absent or pending). An entry about a
kind whose words fill nothing from the item (no `{name}` and no `{<field>}`) is asked once of the volume, about the
kind's module, when the volume holds an item of that kind: a question that would be asked alike of each test case is one
question. An entry may bound itself: `only-with: <field>` asks it only of an item whose field holds a value, and
`at-most: <n>` of at most n items, those a person can best speak to: a command first, then a public name at the top of
its module, then a public method, never first a private, dunder or abstract one; a setting a user sets before a
constant; a change whose words say something before a release or a change-log entry; within that, what the reading
marked unsure, then what carries an edge; ties to the newest. A field entry is not asked of an item that holds a pending
of that field's name: the pending asks it. `{name}`, and any `{<field>}`, are filled from the item when the question is
raised. A raised question's `raised.from` is `<bank name>/<entry id>`. An entry about a module may say `writes`: the
kind (`<kind>` of that module, or `<M>:<kind>`) that a new item written from its answer takes; absent, the module's kind
named like the entry's id (an entry `audience` about N writes an `N:audience`), where the module has one, else the
module's first kind (section 18.6.4).

**The older shape** keeps reading: `dialectic: {questions: {<letter>: ["…", …]}}` is one bank, named after the
manifest, each string an entry `{about: <letter>, asks: <the string>, kind: text, why: missing}` with the bank's
default answerer. A manifest may hold either shape, and a reader reads both.

A bank may keep its questions in a file of the format's own, named in `from: <file>` in place of `questions`; a
reader that does not have the file reads the bank as one with no questions.

**Each format carries its own banks.** The fabula carries one bank per flavour (section 18.4). Ascribe's opening
questions are a bank (Ascribe (https://ascribe.cosmoes.org/), its section 8), and so are Comprise OES's, module by
module (Comprise OES (https://comprise.cosmoes.org/), its section 8). This text specifies neither. The source ids
`session-<n>` and `elicit-…` written before this edition stay valid spellings of a session: a bare `session-1` in
`provenance.sources` names `D:session/session-1` whether or not the volume holds that item.

#### 18.6.7 The moves

The dialectic's three moves are Thym's (Thym (https://thym.cosmoes.org/), its section 22), declared with the core's:
`question` lands a volume's questions, from its banks and its open questions by rules and from a model where the
volume is unsure, ambiguous, in conflict or silent on intent; `record` writes a person's answers into the questions, by
code and with no model; `settle` folds the answered questions into the items they are about. Their contracts are
`addressed` (every `about` and every answer names something that resolves), `no-duplicate` (no two open questions ask
the same thing of one address), `only-the-asked` (only what the questions are about changes), and `provenance` (every
field written carries the session as its source).

#### 18.6.8 Its checks

| Check | Severity | Catches |
|---|---|---|
| `question-about` | error | an `about` that names nothing in the volume: an item that does not exist, a field path that does not parse, a span of the wrong shape (in a fabulac, one whose file or lines do not exist), a module or kind the format does not declare. A question that has `settled`, or whose state is `stale` or `withdrawn`, is skipped, since its answer may have removed what it was about, or it has ended because what it was about is gone |
| `question-shape` | error | a `choice` with no `options`; an `answered`, `unknown` or `declined` question with no answer; a last answer that disagrees with the state (a value for `answered`, `value: null` for `unknown`, `declined: true` for `declined`); an `open` question with `settled` and no answer; a `stale` or `withdrawn` question without `ended` |
| `session-declared` | warning | a source `D:session/<id>`, in provenance or in an answer, that names no session of the volume. A bare `session-<n>` or `elicit-…` with no item is accepted, with a note |

They are the core's checks, and run on every volume that holds an item of D. The generic checks run on D's items as
on any other: `closed-list` on the four closed lists, `ref-unresolved` on the reference fields.

#### 18.6.9 An example

The twin of `guides/close.md` (section 18.4.5) after one session, cut to four items and three of the dialectic's.
The decompile's run raised the questions by rules, among them one from the pending value of the occasion's event and
one from the fabulan bank's `audience` entry, which is about module N and so is asked once of the volume. The author
was asked those two, answered the first and skipped the second, and a second run settled the answer into
`I:occasion/why-written`; `derived.runs` lists that run beside the decompile, whose single keys stand.

```cosm
oes: fabula/1
macrocosm: 0.5.4
flavour: fabulan
id: fabula/guides--close-md
name: The morning close
source: {path: close.md, sha256: d297e46db2cbd55a0fb8af894c130604f087455510bec9417548ce3742191b14, size: 494, mtime_ns: 1792660324518000000}
derived:
  at: 2026-11-05T10:02:11Z
  by: person
  model: g40-04
  route: local
  program: decompile-prose
  run: 2026-11-05-1002-a1c4
  mode: model
  completeness: full
  chunks: 1
  runs:
    - {program: decompile-prose, run: 2026-11-05-1002-a1c4, at: 2026-11-05T10:02:11Z, model: g40-04, route: local}
    - {program: settle-the-answers, run: 2026-11-05-1031-b7e0, at: 2026-11-05T10:31:02Z}
atem:
  line: Meadow closes each customer's books overnight once the bank feeds arrive, locks the day, and retries a failed close before anyone opens the summary.
  focus: How Meadow's overnight close works, what it guarantees, and what it waits on.
  push: Trust the morning summary, because every day is locked and a failed close is caught before seven.
  pull: The summary is only as early as the bank feeds, which Meadow does not control, so a late feed still delays it.
nodes:
  - id: I:occasion/why-written
    type: occasion
    name: Why the guide was written
    summary: Nothing in the text says what prompted Meadow to write the guide.
    stance: assumed
    roles: {event: an owner's call to support about a late morning summary}
    span: {lines: "1"}
    provenance:
      mode: derived
      sources: ['close.md#L1', D:session/session-1]
      confidence: 0.3
      state: pending
      answered: {roles.event: {sources: [D:session/session-1], confidence: 0.9}}
  - id: K:concept/close
    type: concept
    name: the close
    summary: The overnight run that settles and locks one day of a customer's books.
    defined-by: P:claim/close-locks-the-day
    span: {lines: "3-7"}
    provenance: {mode: derived, sources: ['close.md#L3-L7'], confidence: 0.9, state: known}
  - id: P:claim/close-locks-the-day
    type: claim
    name: A close locks the day
    summary: A close locks the day, so no entry in the day can change.
    stance: axiom
    salience: critical
    roles: {subject: K:concept/close}
    links: [{rel: defines, to: K:concept/close}]
    span: {lines: "4"}
    provenance: {mode: derived, sources: ['close.md#L4'], confidence: 0.9, state: known}
  - id: N:audience/owners
    type: audience
    name: Restaurant owners
    summary: The guide is written for the restaurant owners who read the morning summary.
    stance: deduced
    who: restaurant owners who are Meadow's customers
    span: {lines: "5"}
    provenance: {mode: derived, sources: ['close.md#L5'], confidence: 0.8, state: known}
  - id: D:question/audience
    type: question
    about: N
    asks: Whom did you write it for?
    why: missing
    kind: text
    to: author
    raised: {by: bank, from: fabulan/audience, at: 2026-11-05T10:02:11Z, run: 2026-11-05-1002-a1c4}
    state: open
  - id: D:question/why-written-roles-event
    type: question
    about: I:occasion/why-written#roles.event
    asks: "What prompted this guide: a support question, a failed close, a launch?"
    why: missing
    kind: text
    to: author
    raised: {by: move, from: question, at: 2026-11-05T10:02:11Z, run: 2026-11-05-1002-a1c4}
    state: answered
    answers:
      - {at: 2026-11-05T10:20:40Z, by: author, says: "An owner rang support asking why her summary was late, twice in a week.", value: an owner's call to support about a late morning summary, confidence: 0.9, session: D:session/session-1}
    settled: {at: 2026-11-05T10:31:02Z, run: 2026-11-05-1031-b7e0, wrote: [I:occasion/why-written#roles.event]}
  - id: D:session/session-1
    type: session
    at: 2026-11-05T10:18:05Z
    with: {to: author, who: Meadow's head of support}
    through: person
    asked: [D:question/audience, D:question/why-written-roles-event]
    answered: [D:question/why-written-roles-event]
    skipped: [D:question/audience]
```

The answered question was the long form of the occasion's pending value: settling it replaced the pending value
with the answer. `I:occasion/why-written` keeps `mode: derived`, its confidence and its `state: pending`, because the
text did not show its occasion; the field the author gave names the session in `provenance.answered`, so the next run
of `question` asks whether the item as a whole is right (section 18.6.5). The skipped question stays open. Had the
author answered it, `settle` would have written a new `N:audience` item from the answer (section 18.6.4), beside the
one the reading found. Loaded against the fabula's manifest, the volume passes every generic check and the three of
section 18.6.8, with one question open.

### 18.7 thym: Thym's volumes

<!-- atem: Thym's programs, morphs, contexts, plans, traces and packages, one file each -->
**What it enumerates.** What Thym, the transcognition language that connects OESes, reads and writes. `thym/1` is a
built-in of the core, specified in Thym's own text and never a MiniCOSM. A `thym/1` volume is one of seven kinds: a
**program** volume, the enumeration of one `.thym` file, compiled back byte for byte; a **morph** volume of style
sheets, measured against the null morph or declared by hand on ten scales; a **context** volume of occasions; a
**plan**, what a program will do before it does it; a **trace**, what a run did, one record per node; a **package**, the
catalog of a text's self-contained export; and a **folder**, a run's snapshot of a folder it took, every file's digest
and every text file's bytes, so that the run replays without the folder. The full specification is Thym
(https://thym.cosmoes.org/), its section 17, which this section summarizes.

**Its declaration.** `oes: thym/1`. There is no legacy form, and a catalog without the key is refused.

**Its volume.** One file (`volume.single-file: true`), whose catalog's `kind` says which of the seven it is:
`<name>.thym.cosm` beside a program, `<name>.morph.cosm`, `<name>.context.cosm`, `<run-id>.plan.cosm`,
`<run-id>.trace.cosm` (both under the implementation's Thym root by default), `package.cosm` inside a
package's folder or `<name>.package.cosm` beside its text, and `inputs/<name>.folder.cosm` inside a run's folder. A
folder snapshot's catalog adds the keys `path`, `tree`, `commit`, `origin`, `files` and `texts`, and holds no items.

**Its modules and kinds.**

| Kind | Module | What it is |
|---|---|---|
| `program` | P Programs | a block of a program file: its heads, its body verbatim, its steps |
| `move` | P Programs | a move a program defines, with its parameters |
| `step` | P Programs | one statement of a program, verbatim, with the moves it calls |
| `contract` | P Programs | the checks a step's move must pass |
| `morph` | M Morphs | ten scales of a text's or a short's departure from the null morph, with evidence |
| `context` | C Contexts | an occasion: purpose, audience, medium, moment, hurry, words |
| `plan` | R Runs | what a program will do, before it does it |
| `node` | R Runs | one call or check of a plan, and the nodes it runs after |
| `trace` | R Runs | what a run did, and how it ended |
| `record` | R Runs | one node's run: engine, attempts, tokens, seconds and every check |
| `package` | K Packages | a package's catalog entry, for an index that lists packages |
| `reading` | K Packages | a saved reading's record: what it read, through which morph |

Every item may carry `made`, the provenance field Thym adds: the move, run, step and engine that made it. Six checks
are Thym's own (a program volume compiles to its items, a plan is acyclic, a trace is complete, a scale is in range, a
package's digests match, a reading is labelled); enough runs them, and a generic reader does not.

**Its moves.** The manifest ends in a `moves:` block (section 13.4): the moves of the core that no other built-in
owns, among them `cut`, `count`, `words`, `digest`, `null`, `measure`, `morph`, `read`, `package`, `unpack`, `lint`,
`trace` and the accessors `fabula`, `context`, `graph` and `isomorph`, and the dialectic's `question`, `record` and
`settle` (section 18.6). `fabula/1` and `doc/1` declare theirs in their own manifests, Ascribe's `propose` is in its manifest, and
Comprise's sit in `comprise.moves.cosm`. The full list, with each move's signature, is Thym's (its section 6.3).

**In enough.** enough is Thym's reference compiler and runtime (its `thym` command offers `check`, `plan`, `run`,
`trace` and `conform`); the cosm viewer draws a program's steps with their contracts, a plan as a graph and a trace as cards, and the docs viewer
reads a program at three densities.

**An example.** A morph declared by hand: a letter home, personal, a little hedged, never ornate.

```cosm
oes: thym/1
kind: morph
id: thym/plain-letter
name: plain-letter
nodes:
  - id: M:morph/plain-letter
    type: morph
    name: plain-letter
    summary: A letter home, personal, a little hedged, never ornate.
    declared: true
    shared: false
    scales: {register: 1, sentence-length: 1, paragraph-rhythm: 1, analytical-depth: 1, figurative-density: 1,
             stance-style: 3, person-voice: 4, formality: 2, humour: 1, allusion: 1}
    toward: casual
    pinned: []
    provenance: {mode: manual, sources: [plain-letter.morph.cosm], confidence: 1}
```

---

## 19. The MiniCOSMs

<!-- atem: the two domains with specifications of their own -->
A MiniCOSM is a domain's OES with a specification of its own, written in the grammar and declared by a manifest
that ships beside the core's and does not say `core: true` (section 3). There are two, each with its home: Comprise
OES (https://comprise.cosmoes.org/) for companies and Ascribe (https://ascribe.cosmoes.org/) for a person. Each has a
private/public split (section 16). This section says only how each sits in MacroCOSM; what each means is its own
specification's.

| MiniCOSM | Declaration | Enumerates | Volume | Catalog | Modules |
|---|---|---|---|---|---|
| `comprise` | `oes: comprise/1` | a company: its concerns, their relationships, eight modules each | a folder, the Holotype | `holotype.cosm` | C O M P R I S E |
| `ascribe` | `oes: ascribe/1` | one person, without a name: the holograph, ten kinds of node anchored to forms | a folder, the holograph | `holograph.cosm` | A B C E I O Q S U Y F |

Both inherit the core's module D, the dialectic (section 18.6).

### 19.1 comprise: Comprise OES

<!-- atem: a company as Comprise describes it, read here without Comprise's own rules -->
**What it enumerates.** Companies. A Holotype describes one company at a moment as a set of **concerns** (going
concerns: a corporation's branded face, a subsidiary, a joint venture) joined by **relationships**, each concern with
eight modules. The specification is Comprise's own, Comprise OES (https://comprise.cosmoes.org/); this section says
only how it sits in MacroCOSM.

**Its declaration.** `oes: comprise/1`. A `holotype.cosm` without the key reads as `comprise/1`, silently, and so does
the legacy line `comprise: 0.1` that every Holotype made before edition 1 of Comprise OES carries.

**Its volume.** A folder.

```text
<holotype>/
  holotype.cosm                         the catalog: oes: comprise/1, id, concerns, sources, sessions, grants
  atoms/<concern>/                      one part per concern the catalog declares
    C/ O/ M/ R/ I/ S/  **/*.cosm        module files, at any depth
    P/  brand.cosm nodes.cosm doc.cosm  the product tree, which keeps its own header, cosm: 0.3
    E/  README  or  none.cosm           people are never in a file
  codebases/<name>.fabulac.cosm         optional: the fabulacs its codebases point at
  vendors/  snapshots/                  read-only to everything but Comprise
  store.sqlite  people.yaml  feeds/  scans/  bindings/  reports/   outside the model
```

**Its modules.**

| Letter | Module | What it holds | Some kinds |
|---|---|---|---|
| C | Corporation | the legal body: ownership, contracts, filings, money | `entity`, `bond`, `contract`, `counterparty`, `finance`, `aim` |
| O | Organizations | roles, teams, seats and who decides | `role`, `unit`, `position`, `decision` |
| M | Markets | who it serves, through what, at what price | `audience`, `market`, `channel`, `pricebook` |
| P | Products | what it offers, and why that matters: the product tree | `brand`, `suite`, `offering`, `function`, `product`, `service` |
| R | Representations | what it says, and what others say back | `surface`, `claim`, `reflection` |
| I | Inventories | what exists, is stocked or is listed | `feed`, `sku`, `mapping`, `listing` |
| S | Stacks | the systems and vendors it runs on | `system`, `vendor`, `integration`, `codebase` |
| E | Employees | the people: counted, never named | stored only in the local database |

The full list of kinds and their reference fields is the manifest's `modules` block.

**In enough.** enough reads a Holotype, browses it in the cosm viewer, draws it with the default lens, runs the generic
checks and opens any of its files for raw editing. It does not run Comprise's own checks (the product tree's checks and
seven conditions, the fourteen rules); a viewer lists them as not run. When Canon copies a Holotype in, it skips the
manifest's `outside-the-model` entries and every `people*.yaml`, so people never leave Comprise. The manifest is a byte
copy of Comprise's, never edited in enough. Comprise's four public sample Holotypes (meadow, khan-academy, mozilla and
wikimedia) are the conformance corpus (section 20.3).

**An example.** A Holotype is a folder, so its catalog appears here as a fragment: it names a concern whose folder is
not in the block.

```yaml
oes: comprise/1
id: holotype/meadow
name: Meadow Software
summary: Bookkeeping for small restaurants; one concern, no relationships, three outside organizations.
sample: true
atoms:
  - atom/meadow
perspective: atom/meadow
sources:
  - {id: session-3, page: "Interview with the Founder, 2026-10-14", supports: "C, O, M, R, I, S"}
```

### 19.2 ascribe: a person's holograph

<!-- atem: one person described without a name, ten node kinds anchored to forms -->
**What it enumerates.** One person, described well enough that no name is needed. Ascribe's volume is a **holograph**:
the whole self, private, kept by its subject, as a Holotype is a company's. It holds what the person is drawn to,
believes, worries about, has lived through, wants to know, thinks, feels, can do, understands and longs for, each item
anchored to the thing it is about. There is no kind and no field for a name, an email address, a phone number, a postal
address, a birth date, a government id or an employer's legal name; people in a person's life appear by what they are
to the holder or by a pseudonym the catalog declares. The full specification is Ascribe (https://ascribe.cosmoes.org/); this section says how
it sits in MacroCOSM.

**Its declaration.** `oes: ascribe/1`. There is no legacy form, and a catalog without the key is refused.

**Its volume.** A folder whose catalog, `holograph.cosm`, is the self: `id: ascribe/<hid>` (twenty-six characters of
lowercase base32, the shape of a Comprise Connect `hid`), a pseudonymous `handle`, an optional one-line `summary`,
`pseudonyms` and `sample`. Beside it sit the module folders, `A/` to `Y/`, `F/` and, for the dialectic, `D/`, each holding
`.cosm` files of `nodes:`. The catalog may carry a few nodes of any module in its own `nodes:`, which is how the example below is one
file. A `.ascribe-private` marker names files that every ingest, package, transfer and projection leaves behind.

**Its modules and kinds.** Ten containers of the self, one kind each, the kind the singular of the module's name and the
letter its initial, and F for what they anchor to.

| Kind | Module | What it is |
|---|---|---|
| `affinity` | A Affinities | something the person is drawn to, or turns from |
| `belief` | B Beliefs | something the person holds to be true |
| `concern` | C Concerns | something that weighs on the person |
| `experience` | E Experiences | something that happened to the person, or that they did |
| `interest` | I Interests | something the person wants to know more about |
| `opinion` | O Opinions | something the person thinks, and would say so |
| `quale` | Q Qualia | how something feels from the inside |
| `skill` | S Skills | something the person can do |
| `understanding` | U Understandings | something the person has come to understand |
| `yearning` | Y Yearnings | something the person longs for |
| `form` | F Forms | a thing a self can be about, grounded in FEED where it is one word FEED has |
| `polyform` | F Forms | several forms taken together, with the links between them |
| `relation` | F Forms | a relation the author declares beyond the starter list, named by its slug |

**Its envelope** is Comprise's, so that the same moves work on both subjects, plus six fields of Ascribe's own: `form`
(what a node is about: every node of the ten kinds names a form or a polyform), `of` and `parts` (a hierarchy, a branch
or a flat list, as the author likes), `when` (a date, a year or an era word), `valence` (`for`, `against` or `mixed`)
and `strength` (1 to 5). Typed links use a starter list of relations (`is-a`, `part-of`, `about`, `because`, `before`,
`after`, `with`, `against`, `like`, `from`, `toward`, `see`) or a relation the holograph declares; the manifest keeps
`links.starter` rather than a closed `links.rels`, so the generic reader lets a declared relation through and Ascribe's
own check closes the list.

**In enough.** The reader loads, checks and draws a holograph like any volume, titled by its handle. Ascribe's own
checks (an anchored form, a declared relation, the shape of a `when`, the range of a `strength`, what reads like
personal data, and what a private marker would drop) are enough's (its `ascribe lint` command runs them over a
holograph's folder), and a generic reader runs none of them. The personal-data check warns in a holograph and refuses a projection while it finds anything. The
opening questions its manifest's `dialectic:` block holds are a bank of the core's dialectic, and a holograph's
sessions and questions are items of module D (section 18.6). Ascribe's projections, the isograph and the allograph, and the
Allograph Registry where a holder lists an allograph belong to Ascribe's own specification.

**An example.** A holograph small enough to be one file: two forms, a declared relation and two nodes.

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
  - id: F:relation/learned-in
    type: relation
    name: learned in
    summary: A skill picked up during the experience the link points to.
    provenance: {mode: manual, sources: [self], confidence: 1}
  - id: A:affinity/sourdough-baking
    type: affinity
    name: Baking sourdough
    summary: Bread from a starter kept going for years, baked twice a week.
    form: F:form/sourdough
    valence: for
    strength: 5
    when: 2016
    provenance: {mode: dialectic, sources: [session-1], confidence: 0.95}
  - id: S:skill/shaping-dough
    type: skill
    name: Shaping dough
    summary: A loaf shaped by feel, tight enough to hold its rise.
    form: F:form/sourdough
    strength: 4
    links:
      - {rel: learned-in, to: A:affinity/sourdough-baking}
    provenance: {mode: dialectic, sources: [session-1], confidence: 0.9}
```

---

## 20. Conformance

<!-- atem: what a conforming reader and writer must do, and the corpus -->

### 20.1 A reader must

1. Read a catalog and identify its format by section 5.2; refuse an unknown format or major, a value not spelled
   exactly (`comprise/01`, a value with spaces around it) or an empty declaration, with a plain error that names what
   the catalog declares and what the reader knows; return the refusal as a value and never raise.
2. Read every file as UTF-8 with an optional byte-order mark, LF or CRLF, YAML 1.2 booleans and `SafeLoader`'s other
   resolutions (section 4.3); report anchors, aliases, tags and multiple documents as load problems without crashing;
   never stop at the first problem.
3. Find a volume's items where its manifest's `volume` block says they are (section 6), keep the first of two items
   with one id, and report the second.
4. Keep every unknown field, unknown catalog key and unknown manifest key, and never drop one when it writes.
5. Resolve references against the loaded volume (section 9.3); treat a path as a respelling of an id; refuse a malformed
   path rather than normalize it; never touch the disk to resolve a path.
6. Run `load` always, and the generic checks the manifest selects; report unknown check ids as not run; report open
   questions with their item, field path and question (section 12).
7. Apply visibility before showing or drawing anything (section 8.4).
8. Keep `macrocosm:` and ignore it.
9. Read every old spelling a manifest lists as the format it stands for, and report it as old: `oes: emf/1` as
   `fabula/1`, a catalog id `emf/<slug>` with its database name, and a URI `oes:emf/…` as `oes:fabula/…` (sections
   5.2, 6.2 and 11.3).
10. Give every format the core's module D where its manifest does not declare it, run `flavour` and
    `flavour-kind` where the manifest selects them, apply a kind's own closed lists, and list a format's own checks as
    not run when it does not run them (sections 12.3 and 13.4).

### 20.2 A writer must

1. Write the declaration first in a new catalog, and never rewrite the declaration of a volume it did not create.
2. Write only the COSM YAML subset: no anchors (copy values instead of sharing them), no aliases, no tags, one document.
3. Write ids in the format's form, with the kind equal to `type`, and never rename one.
4. Write an open question, never a guess; give every fact its provenance.
5. Keep the fields it does not understand when it rewrites an item.
6. Write nothing into a file that its format keeps out of files (Comprise's people).
7. Where its format says that checks gate writes, leave the volume's checks no worse.
8. Write a catalog that a program owns (a Canon catalog) only from that program; and make derived items (a fabula,
   an atem) only when a person or a readvisor asks.
9. Write a format's own declaration value, never an old spelling: `oes: fabula/1`, never `oes: emf/1`; a URI with the
   format's own name; and a new catalog id in the manifest's `catalog.id` form. Leave an old spelling where it finds
   one (section 5.5).

### 20.3 The conformance corpus

A reader conforms to MacroCOSM OES when:

- Comprise's four public sample Holotypes (meadow, khan-academy, mozilla and wikimedia; 1,010 items between them) load
  through the generic reader and Comprise's manifest with no load problems, and every item has the path Comprise gives
  it;
- every block marked `cosm` in this document loads, identifies as the format it declares, and passes the checks its
  manifest selects with no errors; among them the fabula's examples of section 18.4, one of each flavour (a fabulan of
  a short guide, a fabulap of a poem and a fabulac of a small program), and the twin that keeps the old spelling
  `oes: emf/1`, which identifies as `fabula/1`, old;
- the fuller fabulac the reference implementation's corpus carries beside its program, a program of several modules
  with a history and tests, loads and passes the same way;
- every path in the table of section 11.2 resolves to the id beside it;
- each refusal case of section 5 (an unknown format, an unknown major, a misspelled value such as `comprise/01` or
  `' emf/1 '`, an empty `oes:`, a catalog with no declaration at a name no default claims) is refused, and each legacy
  case and each old spelling is read.

Where the reference implementation's tests and this list disagree, one of them is in error; the Changes appendix
(section 21) records which was corrected.

### 20.4 Where an implementation and this text disagree

Where an implementation and this text disagree, one of them is in error. The disagreement is settled by correcting the
one that is wrong, and the Changes appendix (section 21) records which was corrected, with the section it touched. No
disagreement stands as a rule of its own.

---

## 21. Changes

<!-- atem: what changed in each edition and version, newest first -->
Each entry records what changed in the text or the grammar, newest first. Where an implementation and this text
disagreed and one was corrected, the entry says which.

**Edition 0.6.0 · 2026-11-06.** MacroCOSM is an OES with a core.

1. **The taxonomy.** MacroCOSM OES is an OES: the grammar and the core built into it. The core holds five built-ins,
   `cosm/0` the product tree, `canon/1` Canon, `fabula/1` the fabula, `doc/1` documents and `thym/1` Thym's volumes,
   each declared by a manifest that says `core: true`; a built-in is never a MiniCOSM. There are two MiniCOSMs, Comprise
   OES and Ascribe, each with a specification of its own. What a declaration names is a **format**, and the grammar's
   nonterminal `minicosm` is `format` (sections 3, 5.1 and 18.1).
2. **Section 18 is "The core".** It opens with the core and its registry (18.1, new); the product tree, Canon, the
   fabula and documents keep their numbers (18.2 to 18.5); the dialectic is 18.6 (new); Thym's volumes stay 18.7.
   Comprise and Ascribe moved from 18.1 and 18.6 to a new section 19, The MiniCOSMs (19.1 and 19.2), which say how each
   sits in MacroCOSM as its own text now specifies it (Comprise's sessions and codebases, Ascribe's module D, private
   filter and projections), and Conformance, Changes and Withdrawn moved from 19, 20 and 21 to 20, 21 and 22.
3. **Canon is the core's home file system,** specified apart from any one implementation; enough's library is its
   reference implementation. A file's twin is named in its `fabula` field; `emf`, the field's old spelling, is read as
   `fabula` (section 18.3.2).
4. **The name EMF is retired.** The format is the fabula, declared `oes: fabula/1`. `oes: emf/1` is its old spelling,
   read forever as a fabula whose flavour is `fabulan` and never written; a catalog id `emf/<slug>` and a URI
   `oes:emf/…` are read with it, and the check name `emf-checks` is read as `fabula-checks` (sections 5.2, 5.4, 5.5,
   6.2, 11.3 and 18.1). A twin is named after its text and its flavour, and an older twin's `<text>.cosm` reads as it
   is (section 18.4).
5. **The fabula's flavours and four new modules.** One format holds three flavours, `fabulan` (prose), `fabulap`
   (verse) and `fabulac` (code), named by the catalog's `flavour:`. Four modules join L E K P T X, whose kinds, fields
   and closed lists are unchanged, so every older twin is a valid fabulan: I Inspiration, N Intent, C Construction and
   R Production. A fabulac is compiled into a cshort and told as a catem; a fabula records the model, route and
   provider of every run that wrote into it, a settle run included, while `derived`'s single keys describe the run that
   derived it (sections 18.1 and 18.4). A fabulap gives each line, its metre and its rhymes items of their own, and lets
   readings of one line stand side by side (section 18.4.6). A fabulac is the specification of a program, enough to
   write the program again from it alone; its source folder is fingerprinted by the tree digest; a cshort is a folder of
   rebuilt source with its `CSHORT.md` and a packaging file written by rules, never by a model, checked without
   executing anything; and no conforming implementation runs, imports or installs a program to decompile it or a
   cshort to show it (section 18.4.7). The fabula's own checks are listed in section 18.4.8.
6. **The dialectic.** One primitive of the core asks a person what a source means and records the answer: module D,
   with the kinds `question` and `session`, which every format inherits; the opening questions as banks under a
   manifest's `dialectic:` key; an entry may bound itself, `only-with: <field>` and `at-most: <n>` (section 18.6.6);
   and Thym's moves `question`, `record` and `settle`. A session lists the questions it
   asked, or, where a format asks from a bank without writing question items, the addresses it asked; a MiniCOSM's own
   text says where its volumes keep the items; a settled question whose answer removed its item is closed, not an
   error. An item records what an answer filled in `provenance.answered`, and what its subject declined in
   `withheld`. The dialectic's checks run on every volume that holds module D (sections 8.5, 10, 12.3, 12.5, 13 and
   18.6).
7. **The manifest's new keys.** `core`; `declaration.old`, with the reader reporting a catalog identified `old`;
   `catalog.id-old`; a kind's `flavours` and per-kind `closed` lists; `checks.own` as a list, each own check listed as
   not run by a reader that does not run it; `dialectic`; and the core's module D, declared once in `core.modules.cosm`.
   `thym/1` gains a seventh kind of volume, `folder`, a run's snapshot of a folder it took, with its own catalog keys
   (section 18.7). A reference may be an address, an id with `#` and a field path. Two generic checks are added,
   `flavour` and `flavour-kind`. The registry order is `comprise`, `cosm`, `canon`, `fabula`, `doc`, then any other by
   name, and the registry keeps the built-ins and the MiniCOSMs as two lists (sections 7.3, 9.1, 12.2, 12.3 and 13).
8. **Every table that lists formats lists every format,** grouped as the core's built-ins and the MiniCOSMs: sections
   5.3, 5.4, 6.1, 7.2, 8.2, 11.2 and 14.5.
9. **Both MiniCOSMs have a private/public split.** Comprise's projection is made by a fixed schema, Ascribe's by a Thym
   program; the core's built-ins have none (section 16).
10. **`owner` stays Comprise's.** MacroCOSM's envelope has no owner (section 8.3).
11. **A manifest may lower a severity.** `checks.severity` may raise or lower a default severity, except for the fixed
    findings; it was reserved (section 12.3). The rule on a catalog with no `id`, folded into section 6.2 in edition
    0.5.4, is confirmed and said plainly: where a manifest gives both a template and a supplied id, the template wins.
12. **Two decisions dated as they were made.** Decisions 26 and 27 of version 0.0.1, on shorts and on DocOES, have an
    entry of their own dated 2026-10-23.
13. **Conformance.** A reader reads every old spelling and inherits module D; a writer writes `fabula/1` and never
    `emf/1`; the corpus gains the fabula's examples (section 20).
14. **Stewardship.** One sentence, the same in all five texts of the family (section 1.3).
15. **The grammar version is 0.6.0,** in the reserved `macrocosm:` key (sections 5.6 and 15); files written under
    0.5.4, 0.0.2 and 0.0.1 read unchanged.

**Edition 0.5.4 · 2026-11-03.** The canonical edition, published at https://macro.cosmoes.org/.

1. **Names carry no number.** MacroCOSM OES, Comprise OES, Ascribe and Thym; the edition and the grammar version are
   fields of the status line, never part of a name.
2. **The grammar version is 0.5.4,** in the reserved `macrocosm:` key (sections 5.6 and 15); files written under 0.0.2
   and 0.0.1 read unchanged. Nothing in the grammar changed.
3. **The Comprise OES chapters are no longer appended to this document.** Comprise OES, Ascribe and Thym are published
   at their own homes, and sections 1.1, 18.7, 19.1, 19.2 and the appendix point at them; references to their
   sections are written in words.
4. **The roadmap sections were withdrawn.** Section 22 (open questions and roadmap, with its lists of what was mapped and
   what was left open) was withdrawn, and the *mapped* status marker with it; each gap is stated where it falls as
   reserved for a later edition (sections 4.5, 9.3, 11.3, 12.3, 13.6, 17, 18.3.4, 18.4.4 and 19.2), and the rule on a
   catalog with no `id` was folded into section 6.2.
5. **The text is normative.** The status paragraph, section 20.3 and section 20.4 no longer give the reader the last
   word: where an implementation and this text disagree, one of them is in error, and this section records which was
   corrected. Section 20.4's list of known disagreements (empty) was withdrawn.
6. **Reference implementations are named by their public repositories.** enough (https://github.com/0gsd/enough) for MacroCOSM and every
   registered MiniCOSM; Comprise for Comprise OES. Command lines remain as examples of each implementation's own.
7. **Section 18 is "The MiniCOSMs".** The seven registered MiniCOSMs, each with its home where it has one; the contents
   list names all seven.
8. **Small corrections.** The registry order of section 5.2 completed with `ascribe` and `thym` as section 13.6 gives
   it; the count of further optional keys in section 13.5 corrected from three to four; the colophon names where the
   canonical edition and its source are kept.

**Version 0.0.2 · 2026-11-02.**

1. **Two MiniCOSMs more:** `ascribe/1`, a self with no name (section 19.2), and `thym/1`, programs, morphs, contexts,
   plans, traces and packages (section 18.7).
2. **The `moves:` block of a manifest and the `<name>.moves.cosm` sidecar** (section 13.4), read by the Thym compiler
   and kept by the generic reader.
3. **The grammar unchanged.**

**Version 0.0.1 · 2026-10-23, the grammar unchanged.** Shorts and DocOES.

1. **What is compiled from a twin is a SHORT, written beside the text and recorded by the twin.** One fabula, many
   tellings: the EMF twin, *enumerated meaning fabula*, is the material and a short one arrangement of it. The author's
   text is the first arrangement and is never called a short; the atem stays outside the pair. Every compile is a new
   file in one of two orders, the author's or by weight, and the twin lists its shorts so the material knows its
   tellings.
2. **A document is enumerated in its own grammar.** DocOES (`doc/1`) takes a markdown document apart into its
   sections, terms, examples and decisions and joins them to the reference generated from the manifests; compiled as
   told, the volume gives the markdown back byte for byte. The markdown stays the authoring surface, the volume is
   built at runtime and never committed, every item carries a one-line atem made by rule, and this specification's
   own tables are the hand-written overlay on what is generated, so nobody edits a generated item.

**Version 0.0.1 · 2026-10-22.** The grammar written down apart from any one domain.

1. **MacroCOSM is the grammar Comprise mapped, made real.** Not a new taxonomy: Comprise OES already held every part of
   the grammar, and a second one would split the family.
2. **The format does not change.** One loader, Comprise's, for every `.cosm` file; every existing file reads as it is.
3. **One declaration grammar,** `oes: <minicosm>/<major>`, for every MiniCOSM, each manifest naming the legacy forms it
   reads: one line a person sees without parsing the file.
4. **An absent-declaration default claims only its own catalog file.** Comprise reads a `holotype.cosm` without `oes:`
   as `comprise/1`; a default applied everywhere would claim every YAML file a reader was shown.
5. **A refusal is a value, not an exception.** A viewer shows the refusal in place of the volume and goes on.
6. **`macrocosm:` is reserved and ignored.** Room for a grammar version test, without refusing any file.
7. **Single-file volumes.** A Canon volume and an EMF twin are one catalog each; a folder per text would double every
   tree.
8. **Module letters are local to a MiniCOSM.** The declaration says which language a volume speaks; letters reserved
   across languages would run out and buy nothing.
9. **Paths drop the part level when a MiniCOSM has no parts.** A single-file volume has one implicit part, and a segment
   that never varies is noise.
10. **Wildcard reference fields check only id-shaped values.** Role slots mix item ids with literals such as conditions;
    literals checked as ids would make every condition an error.
11. **Link relations may be closed.** EMF closes them so that twins can be drawn and compared; Comprise keeps its own
    free.
12. **Closed lists and severities by name, in the manifest.** A MiniCOSM's own vocabularies (stance, salience) and its
    severities are checked without new code.
13. **Lenses are declared in the manifest, with a default.** A MiniCOSM can be drawn without code; Comprise's manifest,
    a byte copy that declares no lens, draws with `map`.
14. **Generic checks only.** A MiniCOSM's own rules are its own code; Comprise's fourteen rules are not reproduced in
    the generic reader, and a viewer says plainly that they need Comprise.
15. **Checks may gate writes; MacroCOSM does not require it.** Comprise undoes a write that adds an error; enough edits
    raw text and reports problems after a save, never refusing it.
16. **`load` always runs.** Nothing can be checked that was not read.
17. **Versions, the split and MicroCOSMs are by reference.** Saved versions, signatures and the split are Comprise's
    (Comprise OES, its sections on versions and on the private/public split); MicroCOSMs are reserved for a later
    edition.
18. **A URI between volumes is a value, not a reference.** Resolving across volumes needs a registry of volumes the
    grammar does not define.
19. **The EMF twin's name adds `.cosm` to the text's whole name.** `notes.md` and `notes.md.cosm` sort together and pair
    by name; the family keeps one extension.
20. **An EMF twin's id respells the text's path.** Two texts with the same name in different folders must not share an
    address.
21. **A project's catalog records structure only.** No sizes, times or twin states, so that a project in version control
    does not change with every edit.
22. **An atem is a line with focus, push and pull,** and "the atem" in prose is the line. One sentence is what a person
    keeps; the three vectors are what a reader needs to trust it.
23. **Without a model, a labelled scaffold.** A derivation that could not read writes open questions and says so, never
    a filler.
24. **The specification shipped inside enough,** beside the reference reader (superseded in edition 0.5.4 by the
    canonical edition at https://macro.cosmoes.org/).
25. **All rights reserved for the specification and the manifests;** the reference implementation is licensed on its
    own terms.

---

## 22. Withdrawn

<!-- atem: the open questions and roadmap, withdrawn in edition 0.5.4 -->
The section on open questions and the roadmap was withdrawn in edition 0.5.4; its content, where it survives, is in the
Changes appendix (section 21) and in the sections that state each gap where it falls.

---

## Appendix: the mapping to Comprise OES

<!-- atem: where each part of this document comes from in Comprise OES -->
Section by section, where each part of this document comes from in Comprise OES (https://comprise.cosmoes.org/), the
map of the family (https://cosmoes.org/, called "the map" below) and Comprise's manifest, and what changed on the way.
A bare number in the middle column is a section of Comprise OES; `P.n` is a section of its chapter P, the product
tree; a decision is a numbered item of its Changes appendix.

| MacroCOSM OES | Comprise OES | What changed |
|---|---|---|
| 1 Provenance and the name | the opening note; the map; P.11 | the lineage carried one step further |
| 2 The model on one page | 1; the map | "Holotype" became "volume", "concern" became "part"; the store left the table |
| 3 Scales | the map | MacroCOSM's parts listed against this document's sections |
| 4 The file format | 2.5; the manifest's `format` | the loader written out; the YAML 1.1 surprises tabled |
| 5 The declaration | 2.3; decision 13 | any format; the absent default scoped to its own catalog file; a registry order; old spellings |
| 6 Volumes and catalogs | 2.1, 2.2, 2.4, 2.7 and 2.8; 3.1 for parts | single-file volumes; concerns generalized as parts |
| 7 Items, kinds, fields | 2.4; the opening of 5; 6.4.6 | module letters local to a format; wildcard fields |
| 8 The envelope | 4, 4.1, 4.2 and 4.3 | a nine-field minimum; required fields per format; no `owner` |
| 9 References and links | 7 | closed link relations; literals in wildcard fields; URIs as values |
| 10 Open questions | 8 | unchanged, with the `pending-shape` check |
| 11 Ids, paths, URIs | 6 | levels from the manifest; no part segment without parts |
| 12 Checks | 9.1 and 9.2 | a fixed generic vocabulary; unknown ids reported as not run |
| 13 The manifest | the map; the manifest; decisions 15 and 16 | read generically; optional 0.0.1 keys; the registry |
| 14 Renderers and lenses | 12; P.8 | lenses declared in the manifest; a default lens |
| 15 Versions and signatures | 10 | by reference |
| 16 The private/public split | 11 | by reference; the words named for every MiniCOSM, and both MiniCOSMs given a split |
| 17 MicroCOSMs | the map; the manifest's `extension` | unchanged; reserved for a later edition |
| 18.1 The core and its registry | none | the core's built-ins, their declarations and the model they share |
| 18.2 cosm | chapter P, P.7; COSM 0.2 | a built-in for trees outside a Holotype |
| 18.3 canon, 18.4 fabula, 18.5 doc, 18.6 the dialectic, 18.7 thym | none | the core, written in the grammar |
| 19.1 comprise | the whole of Comprise OES | how it sits in MacroCOSM |
| 19.2 ascribe | none | how Ascribe sits in MacroCOSM |
| 20 Conformance | 13 | the corpus named; where an implementation and this text disagree, one is in error |
| 21 Changes | 14 | this document's own |
| 22 (withdrawn) | the map; the *not built* of 12 | withdrawn in edition 0.5.4 |

**What stays Comprise's alone.** Concerns and relationships, the eight modules' kinds and fields, the product tree's
checks and its seven conditions (P.9), the fourteen rules and the verdict, the isotype's fields and rules, and the
people, who are never in a file: Comprise OES (https://comprise.cosmoes.org/) specifies each of them. MacroCOSM reads all
of them, keeps them, and leaves their meaning to Comprise.

---

## Colophon

<!-- atem: copyright, the canonical edition and its source -->
MacroCOSM OES — Copyright © 2026 Graham Smith. The text and its manifests are licensed under the Creative Commons Attribution 4.0 International licence (CC BY 4.0, https://creativecommons.org/licenses/by/4.0/). A copy carries the author, Graham Smith; the text's name and edition; and a link to its home, https://macro.cosmoes.org/. For MacroCOSM OES, the author makes the Open Web Foundation Final Specification Agreement 1.0 (OWFa 1.0) promise (https://www.openwebfoundation.org/the-agreements/the-owf-1-0-agreements-granted-claims/owfa-1-0). The names of the family are not licensed by either; the author holds them for now. The canonical edition is published at https://macro.cosmoes.org/; its source and history are at https://github.com/0gsd/cosmoes-site.
