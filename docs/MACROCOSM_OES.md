# MacroCOSM OES

*Specification v0.0.1 · 2026-10-23*

MacroCOSM OES is the shared grammar every MiniCOSM is written in. It says how a domain is enumerated as plain-text
`.cosm` files that are at once a file system and a relational database, made to be rendered: how a file is read, how a
volume names the language it is written in, what an item is and which columns every item carries, how one item points
at another, how an unknown value is written down, how anything is addressed, which checks every volume can be held to,
how a manifest declares a MiniCOSM, and how a renderer draws one. It is the grammar that Comprise OES 1 worked out for
companies, read out of it and written down on its own, so that nothing in it says "company". Four MiniCOSMs are
written in it today: `comprise`, `cosm`, `canon` and `emf` (section 18).

**Status.** Normative for version 0.0.1. The reference reader is `enough/macrocosm.py`. Where this text and the reader
disagree, **the reader wins**, and this text is corrected. Section 19.4 collects every disagreement known at the time
of writing. *By reference* marks a part that is defined elsewhere and not built here; *mapped* marks a part that is
planned and not built anywhere.

**The format does not change.** A MacroCOSM file is a `.cosm` file in the COSM YAML subset, exactly as Comprise OES 1
reads it. Version 0.0.1 names the grammar, generalizes it, and adds a few optional manifest keys so that a reader can
handle a MiniCOSM it has never seen without new code (section 13.5). Every Comprise Holotype and every standalone COSM
tree made so far reads unchanged.

## Contents

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
17. MicroCOSMs (mapped)
18. The MiniCOSMs enough ships: comprise, cosm, canon, emf
19. Conformance
20. Decisions in this version
21. Open questions and roadmap

Appendix: the mapping to Comprise OES 1 · Colophon

## How to read this

**Must and may.** *Must* is a rule a conforming reader or writer keeps. *May* is a permission. *Should* is advice the
checks do not enforce.

**Words.** The words a person reads on screen come first. Where the spec must be exact, the term the files and the
reader use follows in parentheses.

| Here | In the files and the reader | Example |
|---|---|---|
| item | node, a mapping in a `nodes:` list | `P:claim/close-locks-the-day` |
| kind | type, the `type:` field | `claim` |
| open question | pending | `{pending: "…"}` |
| checks | lint | `python -m enough.macrocosm lint <volume>` |
| volume | the database a catalog heads | a Holotype, a Canon volume, an EMF twin |
| part | a top-level division of a volume (Comprise: concern, *atom*) | `atoms/meadow/` |

**Examples.** Every block in this document marked `cosm` is one complete file: it starts with its declaration, it
loads, and it passes the checks its MiniCOSM selects, with every reference resolving inside the block. A block marked
`yaml` is a fragment of a file and may point at things outside it. A block marked `text` is grammar or a picture.

---

## 1. Provenance and the name

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

The earlier specifications stay where they are. COSM 0.2 is the context-ontology skill's own reference. Comprise OES 1
is `oes/comprise-oes.md` in the Comprise repository, with its map in `oes/README.md` and its manifest in
`oes/comprise-oes.manifest.cosm`. This document points at their section numbers and does not repeat them.

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

MacroCOSM is stewarded by Verroes (Graham Smith). The specification, the MiniCOSM manifests that ship with enough and
the names of the family are his (see the colophon). The reference reader is part of enough.

---

## 2. The model on one page

A volume is a file system that is also a relational database. Every part of the grammar has a place in both readings,
and a name on screen.

| MacroCOSM | As a file system | As a relational database | On screen | Section |
|---|---|---|---|---|
| volume | a folder with its catalog at the root, or one catalog file that holds everything | a database | a Holotype, a Canon volume, an EMF twin | 6 |
| catalog | the volume label: which language, which version, what is aboard | the catalog: the MiniCOSM, its version, the parts, the sources | (details) | 6.2 |
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
references, and the checks. A MiniCOSM may keep a local database beside its files for what must never be in a file
(Comprise keeps its people there); that database is outside the model (section 6.6).

**The one rule that makes both readings agree:** a path names the same thing a primary key does (section 11).

---

## 3. Scales: MacroCOSM, MiniCOSM, MicroCOSM

| Scale | What it is | In this version |
|---|---|---|
| **MacroCOSM** | the whole language: the shared grammar every MiniCOSM is written in | this document, and the reader `enough/macrocosm.py` |
| **MiniCOSM** | an OES for one domain, declared by a manifest: its volume layout, modules, kinds, fields, references, checks and renderers | four ship with enough: `comprise`, `cosm`, `canon`, `emf` (section 18) |
| **MicroCOSM** | one organization's extension on top of a MiniCOSM: the extra kinds, fields, checks or renderers it needs | mapped, not built (section 17) |

**What MacroCOSM gives every MiniCOSM.** All of it, unchanged: sections 4 to 14 of this document, and the parts
defined by reference in sections 15 to 17.

**What a MiniCOSM declares.** Its manifest (section 13) says, in order: its name and version and the declaration a
volume uses to name it, with any legacy forms it still reads; its volume layout; its modules and kinds, and for each kind
at least the fields the checks follow; its reference forms and closed lists; the checks that apply, with their
severities; its renderers and lenses; and, when it has one, its public projection. A volume names its MiniCOSM with one
line in its catalog and never embeds the manifest.

**Each smaller scale keeps the order of the larger.** A MiniCOSM may add to MacroCOSM (kinds, fields, envelope fields,
closed lists, checks, renderers) and may narrow what MacroCOSM leaves open (which envelope fields are required, which
link relations are allowed). It may not change what the grammar means: an id, a path, a reference, an open question
and the declaration mean the same thing in every MiniCOSM.

---

## 4. The file format

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
| `macrocosm: 0.0.1` | the string `0.0.1` | |
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
  of one item inside a file are Comprise's (its `edit` model) and are mapped for MacroCOSM (section 21).

### 4.6 Text, not code

A `.cosm` file is data. A reader never executes anything in it, never follows an include, and never opens a file because
a value names it, except where the manifest's volume layout says where the files of a volume are (section 6). A path is
an address, never a door (section 11.2).

---

## 5. The declaration

### 5.1 The form

A catalog says which MiniCOSM it is written in with its first key:

```yaml
oes: canon/1
```

```text
declaration = "oes:" SP minicosm "/" major
minicosm    = lower *( lower / DIGIT / "-" )          ; the MiniCOSM's name, as its manifest gives it
major       = "0" / ( %x31-39 *DIGIT )                ; the MiniCOSM's major version, an integer
```

The value names a MiniCOSM and a major version, never a minor one. It is spelled exactly as the manifest's
`declaration.value` gives it, and a reader refuses any other spelling, as Comprise does: `comprise/01` is refused, and so
is a value with a space before or after it. A change to a MiniCOSM that existing volumes can still be read under keeps
its major; a change that would make an existing volume mean something else needs a new major, and a change that would
alter what a path means needs a new MiniCOSM (section 11.3).

### 5.2 Identifying a catalog

The reader keeps a registry of the manifests it knows (section 13.6), in order: `comprise`, `cosm`, `canon`, `emf`.
Given a catalog, it decides which MiniCOSM the catalog is written in by these steps, in order. The first that applies
decides.

1. **An `oes:` key decides.** If its value is a string naming a MiniCOSM in the registry and a major that manifest
   declares, the catalog is written in it. Anything else under `oes:` (an unknown name, an unknown major such as
   `comprise/2`, a value not spelled exactly, such as `comprise/01` or `' emf/1 '`, an empty value, a value that is not
   a string) is refused.
2. **A legacy key.** If the catalog has no `oes:` key, each manifest's `declaration.legacy` keys are tried in registry
   order. The first manifest that names a key present in the catalog (and, where it gives one, a matching value)
   claims it. Values compare as text, so `comprise: 0.1` matches the legacy value `'0.1'`.
3. **An absent default.** A manifest whose `declaration.absent` names its own declaration (Comprise's says
   `comprise/1`) claims a catalog with neither key, but only a catalog found where that manifest's `volume.catalog`
   puts it: `holotype.cosm` at the root of a folder, for Comprise. A default never claims a file at another name.
4. **Otherwise** the catalog is refused: it declares nothing the reader knows.

When a catalog carries both `oes:` and a legacy key, `oes:` decides and the legacy key is kept and ignored (Comprise's
`declaration.both: oes`).

### 5.3 Refusal

A refused catalog loads nothing. The reader returns a refusal, a value that says what the catalog declares and what the
reader knows, and never raises. For example:

```text
canon.cosm declares oes: canon/2, which this reader cannot read: it reads comprise/1, cosm/0, canon/1, emf/1;
nothing was loaded from this volume
```

The checks report the refusal as one `load` error, and a viewer shows it in place of the volume.

### 5.4 Legacy forms

| MiniCOSM | Declaration | Also read | Absent |
|---|---|---|---|
| `comprise` | `oes: comprise/1` | `comprise: 0.1`, the line in every Holotype made before Comprise OES 1 | `holotype.cosm` with no key reads as `comprise/1`, silently |
| `cosm` | `oes: cosm/0` | `cosm: 0.2`, `cosm: 0.3`, and `opi:` with any value | refused |
| `canon` | `oes: canon/1` | nothing | refused |
| `emf` | `oes: emf/1` | nothing | refused |

A legacy key is never an error. A reader keeps it.

### 5.5 Writing the declaration

- A writer creating a volume writes the declaration as the first key of its catalog, so a person or a tool sees it
  without parsing the file.
- A writer must not rewrite the declaration of a volume it did not create. There is no migration: a Holotype that says
  `comprise: 0.1` keeps saying it.

### 5.6 The reserved key `macrocosm:`

A catalog or a manifest may carry `macrocosm: 0.0.1`, after its declaration. Readers keep the key and ignore it. It is
reserved for the day the grammar itself needs a version test; until then no reader refuses a file for what it says,
and no writer is required to write it.

---

## 6. Volumes and catalogs

### 6.1 Volumes

A **volume** is one database of a MiniCOSM. It has one of two shapes, and the manifest's `volume` block says which.

| Shape | What it is | Its items | MiniCOSMs |
|---|---|---|---|
| a folder volume | a folder with the catalog at its root and module files below it, in the places the manifest's `volume` block names | in module files, under `nodes:` (and, where a MiniCOSM says so, a named block such as `brand:`) | `comprise` (a Holotype), `cosm` (a product tree) |
| a single-file volume (`volume.single-file: true`) | one file: the catalog is the whole volume | under the catalog's own `nodes:` | `canon` (a Canon volume's `canon.cosm`), `emf` (a text's twin) |

A volume is what a URI names (section 11.3), what the checks run over, and what a renderer draws. Two volumes never
share an item: a reference between volumes is written as a URI, and the reader does not resolve it (section 9.3).

### 6.2 The catalog

The **catalog** is the file at the root of a volume that declares the MiniCOSM and says what the volume holds. It is
one YAML mapping.

- **The declaration** comes first (section 5).
- **The keys** a catalog may hold are the manifest's `catalog.keys`. A reader keeps every key, listed or not, and
  ignores the ones it does not understand. A key the manifest does not list is reported by the check `catalog-key` as a
  note. A writer must not invent catalog keys the manifest does not list without a new version of its MiniCOSM.
- **The catalog id** has the form the manifest's `catalog.id` gives: `holotype/<slug>`, `canon/<volume-slug>`,
  `emf/<slug>`. When it is absent, the manifest's `catalog.id-absent` rule supplies it (Comprise: `holotype/<folder
  name>`). The id without its prefix is the volume's **database name**, the second segment of its URI.
- **Sources.** A catalog may declare the sources its items cite (Comprise's `sources:`, with the fields the manifest's
  `catalog.source-fields` lists). Where a MiniCOSM checks that cited sources are declared, the check is its own.

### 6.3 The volume block

The manifest's `volume` block says where the files of a volume are (its keys are listed in section 13.3): the catalog's
file name, whether the volume is a single file, where a folder volume's parts, modules and module files are, and what
is `outside-the-model`. Files and folders outside the model sit inside the volume but are not part of it: they are not
read as module files, not checked, and skipped by a tool that copies the model elsewhere (Comprise's `people.yaml`,
`feeds/` and `scans/`; Canon's `.canon.json`). Keys a MiniCOSM adds for its own code (Comprise's `vendors`,
`snapshots`, `database`) are kept.

### 6.4 Parts

A MiniCOSM may divide a folder volume into top-level **parts**, each with its own modules. Comprise does: each concern
(*atom*) is a part, at `atoms/<concern>/`, declared in the catalog's `atoms:` list. A declared part without its folder
is a load problem; a folder under the parts' place that the catalog does not declare is a load problem.

An item belongs to exactly one part. Inside its own part an id is written bare; from another part it is written
qualified, `<part-prefix>//<id>` (section 11.1). A volume without parts (every single-file volume, and the standalone
product tree) has one implicit part, and its paths have no part segment (section 11.2).

### 6.5 Module files

In a folder volume, a **module file** is a `.cosm` file in the places the manifest names, at any depth. Each is one
mapping with one of the shapes the manifest's `module-file.shapes` lists. The two every MiniCOSM may use:

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

A MiniCOSM may keep some of what it describes out of its files on purpose. Comprise keeps people only in a sealed local
database beside the Holotype, and marks the kinds that live there `stored: database` in its manifest. A reader never
reads such kinds from a file, and a writer never writes them into one. The local database, where there is one, is outside
the model: the checks do not read it unless a MiniCOSM's own checks say so, and no export of the files includes it.

---

## 7. Items, kinds, fields

### 7.1 Items

An **item** is a row: a mapping with a string `id` and a `type`. It is written in a `nodes:` list, or in a named block
a MiniCOSM declares (Comprise and the product tree hold the brand under `brand:`, and read a legacy `firm:` the same
way). An entry of a `nodes:` list that is not a mapping, or has no string id, is a load problem; the rest of the file
still loads.

An item's id never changes. Its `name` is for display and may change freely.

### 7.2 Modules

A **module** is a group of kinds: a group of tables. It is named by one capital ASCII letter, and the manifest gives it
a `name` and a short `subtitle`: EMF's `P` is *Propositions*, "what the text claims, and how it knows".

**Letters are local to a MiniCOSM.** The declaration says which language a volume is written in, and so which module a
letter names. `P` is Products in `comprise` and in the product tree, and Propositions in `emf`. Nothing in the grammar
reserves a letter.

| MiniCOSM | Modules |
|---|---|
| `comprise` | C Corporation · O Organizations · M Markets · P Products · R Representations · I Inventories · S Stacks · E Employees |
| `cosm` | P Products |
| `canon` | V Volume |
| `emf` | L Lexicon · E Entities · K Concepts · P Propositions · T Transitions · X Atems |

### 7.3 Kinds

A **kind** is a table. It is declared under its module, with:

| Key | Holds |
|---|---|
| `refs` | the kind's reference fields: the fields the reference checks follow (section 9). An empty list says the kind has none |
| `checked` | further fields a check reads, beyond the envelope |
| other keys | what a MiniCOSM's own code needs: a `level`, an exception id form (`id: 'P:<slug>'`), `stored: database`, `public: never`, a `note` |

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
- **Wildcard fields.** A reference field ending in `.*` names every value of a mapping (0.0.1). EMF lists `roles.*`: every
  value under a claim's `roles:` is followed (section 9.6).
- **Unknown fields are kept, always.** A field the manifest does not declare is legal. A reader keeps it, shows it, and
  never drops it; a writer that rewrites an item keeps it.
- **Absent and `none`.** A MiniCOSM should read an absent field as "not yet asked", never as "nothing". Where nothing is
  the fact, the item says `none`.

---

## 8. The envelope

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

A MiniCOSM declares which envelope fields every item must carry, in its manifest's `envelope.required`. A required field
that is missing fails the check `identity-min`; only presence is checked, as in Comprise, so an empty value passes.

| MiniCOSM | Required |
|---|---|
| `comprise` | `id type name summary provenance`; in P, `id type name summary owner` |
| `cosm` | `id type name summary owner` |
| `canon` | `id type name path` |
| `emf` | `id type name summary provenance` |

### 8.3 Envelope fields a MiniCOSM adds

A MiniCOSM may add fields to its envelope (`envelope.fields`) and say which of them are references
(`envelope.references`). Comprise adds `owner` (a role, never a person), `since`, `until`, `mattering`, `body`, `at`,
`attributed-to`, `template`, `instances`, `counterparty`, `series` and `shared-with`, and checks `owner`, `at`,
`attributed-to`, `counterparty`, `shared-with` and `links` as references. Canon adds `path`, `parent`, `parts`,
`size`, `mtime`, `kind`, `twin`, `emf` and `atem`. EMF adds `span` and `salience`.

### 8.4 Status and visibility

Unless a manifest gives other lists, the closed lists are Comprise's:

| Field | Values |
|---|---|
| `status` | `active` · `dormant` · `planned` · `retired` |
| `visibility` | `public` · `internal` · `restricted` |

What an absent visibility means is the MiniCOSM's to say (Comprise: `internal` outside P, by level in P). Whatever it
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
| `sources` | a non-empty list of what it came from: source ids the catalog declares (Comprise), or locators in the source text (EMF: `'close.md#L3-L7'`) | error when empty or not a list |
| `confidence` | a number from 0 to 1 | error otherwise |
| `state` | `known` (the default) · `pending` · `not-disclosed` · `stale` | error otherwise |
| other fields | what a MiniCOSM adds (Comprise: `synced-from`, `synced-at`, `max-age`) | as that MiniCOSM says |

**Modes**, Comprise's twelve: `dialectic` · `net-scan` · `system-scan` · `integration` · `structured-intake` · `manual`
· `derived` · `asserted` · `archetype` · `catalogue` · `directory` · `accounting`. `derived` is the mode every
derivation uses: an item a program made from other material, such as an EMF item made from a text.

`not-disclosed` is a fact, not a question: the subject declined to say. `pending` says the item stands on something not
yet confirmed.

**Identity instead of provenance.** The product tree carries COSM's identity instead of a provenance block:
`confidence` and `sources` at the top level of the item, with `owner` required. The manifest says so (Comprise's
`envelope.identity-in-P`), and the `provenance` check then reads those two fields where they are.

### 8.6 Unknown fields

Allowed, and kept. The envelope is a floor, not a ceiling.

---

## 9. References and links

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
| a list of any of these | `parts: [V:file/readme-md, V:folder/guides]` | each of them |

A path is not a reference. Files hold ids.

### 9.2 Two ends

**Every reference must resolve.** A reference that names nothing in the volume fails the check `ref-unresolved`, an
error, unless the manifest's `references.exceptions` gives the case a lighter severity (Comprise: a vendor not yet
fetched is a warning). A value in a reference field that has none of the forms above fails `ref-grammar`.

### 9.3 Resolution

- A bare id resolves in its own part; a qualified id in the named part; a part id to the part.
- Resolution runs against the loaded volume, never against the disk, and never depends on who is reading.
- A URI written in a field (`oes:comprise/meadow/meadow/O/role/Founder`) is not a reference in 0.0.1. It is kept as a
  value and not checked; resolving across volumes is mapped (section 21).

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
- `rel` is free text unless the manifest closes it with `links.rels` (0.0.1). EMF closes it to nine words (section
  18.4); a `rel` outside a closed list fails `closed-list`.

### 9.5 Relations are fields

There is no syntax for a relation other than a field that holds an id. A relation's name is its field's name (`owner`,
`parent`, `defined-by`) or its typed link's `rel`. A MiniCOSM that needs a relation with attributes of its own (dates,
shares, sources) makes it an item: Comprise's relationships between concerns are items of the kind `C:bond`.

### 9.6 Wildcard fields and literals

In a wildcard reference field (`roles.*`), a value is checked as a reference only when it is **id-shaped**: when it
parses as an item id of a module the MiniCOSM declares. Any other string is a literal and is not checked:

```yaml
roles:
  actor: E:org/meadow                    # an id: checked, must resolve
  condition: only after the bank feeds arrive    # a literal: kept, not checked
```

An id-shaped value that names nothing still fails `ref-unresolved`. In a named reference field (one without `*`),
every value is checked, and a literal fails `ref-grammar`.

---

## 10. Open questions

An **open question** (*pending*) is a value nobody has yet given, written where the value would go:

```yaml
terms: {pending: "funding amount and term are not published"}
feed: {pending: "not in FEED"}
pending: "Which entity holds the trademarks since the transfer?"
```

- **Pending beats plausible.** A writer must never guess a value. It writes the question instead.
- **The form.** `{pending: "<the question>"}` in place of any value, at any depth; or a `pending:` key on the item, for
  a question about the whole item. The question is a non-empty string; anything else fails the check `pending-shape`.
- **Who answers.** The question should be addressed to whoever can answer it. A MiniCOSM may say who that is by default
  (Comprise: the item's owner; a role answers for itself; otherwise "unassigned").
- **Its address.** The item's path plus `#` and the field path (`…/P/offering/mozilla-festival#economics.price`). A
  question on the whole item is addressed by the item's path alone.
- **What it does to the checks.** An open question is never an error and never fails a reference check. A MiniCOSM's
  own rule that needs the value reports itself *unverifiable* instead of passing or failing.
- **The report.** The checks list every open question with its item, its field path and the question (section 12.4).
- **Not the same as "not disclosed".** `provenance.state: not-disclosed` records that the subject declined to say: a
  fact, not a question.
- **Derivations.** A program that could not do its work writes a question, never a filler. When enough derives an EMF
  twin without a model, every item it writes says so: `pending: "a model has not read this passage"` (section 18.4).

---

## 11. Ids, paths, URIs

Every item has an **id**, the primary key. Every part, module, kind, item and field has a **path**, the id respelled
as a location. Every volume and everything in it has a **URI**, the path qualified with the MiniCOSM and the volume.

### 11.1 Ids

```text
item-id      = module ":" kind "/" slug                 ; MacroCOSM's default form
qualified-id = part-prefix "//" item-id                 ; an item of another part (Comprise: "atom/" concern)
module       = %x41-5A                                  ; one capital letter the MiniCOSM declares
kind         = lower *( lower / DIGIT / "-" )           ; a kind that module declares
slug         = alnum [ *( slugch / "." ) slugch ]       ; [A-Za-z0-9]([A-Za-z0-9._@-]*[A-Za-z0-9_@-])?
alnum        = ALPHA / DIGIT
slugch       = ALPHA / DIGIT / "_" / "@" / "-"          ; a slug never ends in a dot
sentinel     = "none" / "self"
```

- **The manifest may declare other forms.** `ids.item-form` gives the MiniCOSM's form and `ids.item` a regular
  expression for it; `ids.brand-form` and a kind's `id:` give exceptions; `ids.qualified-form` gives the qualified form.
  Comprise's brand is `P:<slug>`, with no kind. The product tree writes ids bare, `<kind>/<slug>`, with the module left
  out (section 18.2).
- **Bare inside its own part.** An item's own id is written bare in its part's files. An id qualified with another part
  is an error (Comprise's check `id-atom`, which is its own).
- **Case is kept and significant.** `O:role/Founder` and `O:role/founder` are two items. A tool that ever used paths as
  file names on a case-insensitive file system would merge them, so such a tool must refuse the pair.
- **An id outside the slug set** (one with a slash in its slug, a colon, a `#`, a space or a non-ASCII letter) may still
  parse as an id where the MiniCOSM's id form allows it, but it has no path.
- **Never renamed.** The id is the key. Renaming a thing changes its `name`.

### 11.2 Paths

A path is an id respelled as a location, through the levels the manifest's `paths.levels` declares.

| MiniCOSM | Levels | Item path |
|---|---|---|
| `comprise` | concern, module, kind, item, field | `<concern>/<module>/<kind>/<slug>` |
| `cosm` | module, kind, item, field | `P/<kind>/<slug>` |
| `canon` | module, kind, item, field | `V/<kind>/<slug>` |
| `emf` | module, kind, item, field | `<module>/<kind>/<slug>` |

```text
path      = [ part "/" ] module [ "/" kind [ "/" slug [ "#" field ] ] ]    ; part present exactly when the MiniCOSM has parts
part-path = part                                                           ; a part alone (Comprise: a concern)
field     = key *( "." key / "[" 1*DIGIT "]" )
key       = ( ALPHA / DIGIT ) *( ALPHA / DIGIT / "_" / "-" )
```

**Properties.**

- **A respelling.** A path is computed from an id, and an id from a path, with no lookup.
- **Slug-based.** Built from slugs, which never change when an item is renamed.
- **Absolute.** In a MiniCOSM with parts, a path always starts with the part. There are no relative paths.
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
outside ASCII; a colon; a segment ending in a dot; a second `#`; a module the MiniCOSM does not declare; a kind its module
does not declare; more segments than the MiniCOSM's levels allow; a segment that is a Windows reserved name (`con`,
`prn`, `aux`, `nul`, `com0` to `com9`, `lpt0` to `lpt9`), in any case, alone or before a dot (`con.txt`, `NUL.tar.gz`).

**Scope.** A path to an item the reader may not see answers exactly as its id would: nothing there, no name. A path is
never a way around visibility.

**Examples.** Each resolves: the Comprise ones on Comprise's public fixtures, the others on the complete examples in
section 18.

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
| `V/file/guides--close-md#emf.state` | `V:file/guides--close-md`, field `emf.state` | the state of a text's EMF twin |
| `P/claim/close-locks-the-day` | `P:claim/close-locks-the-day` | a claim of the EMF twin in 18.4 |
| `P/claim/meadow-closes-overnight#roles.actor` | `P:claim/meadow-closes-overnight`, field `roles.actor` | a role slot |
| `X/atem/1` | `X:atem/1` | a passage atem |

### 11.3 URIs

For use outside one volume, a path is qualified with the MiniCOSM and the volume's database name:

```text
uri      = "oes:" minicosm "/" database [ "/" path ]
database = the catalog id without its prefix             ; holotype/meadow gives meadow; canon/~meadow-notes gives ~meadow-notes
```

```text
oes:comprise/meadow                                      the Holotype itself
oes:comprise/meadow/meadow/O/role/Founder                a role in it
oes:canon/meadow-handbook/V/file/guides--close-md        a file in a Canon volume
oes:canon/~meadow-notes/V/file/plan-md                   a file in a project's catalog
oes:emf/guides--close-md/P/claim/close-locks-the-day     a claim in a text's EMF twin
```

- **No version.** A URI carries no version, because a path keeps its meaning across every version of its MiniCOSM. A
  change that would alter what a path means must be a new MiniCOSM.
- **Unique within one install.** A database name is unique among the volumes one reader knows, not in the world. A
  globally unique name, and a resolver for URIs across installs, are mapped (section 21).
- **A private address.** A URI names a place. It opens nothing to a reader who may not see what is there.
- **In enough.** enough resolves URIs for its own volumes: `oes:canon/<volume>/…` for a Canon volume,
  `oes:canon/~<project>/…` for a project's catalog, `oes:emf/<twin>/…` for an EMF twin, and
  `oes:comprise/<holotype>/<path>` for any Holotype Canon holds.

---

## 12. Checks

### 12.1 What the checks are

The **checks** (*lint*) are the constraints of the database, run over the whole volume. The reader runs them on load:
`python -m enough.macrocosm lint <volume>`. They never raise and never stop at the first problem. Each problem names its
check, its item (or its file), the field path where it applies, and a plain message.

MacroCOSM defines a fixed vocabulary of **generic checks** that any reader can run on any volume from its manifest
alone. A MiniCOSM may have checks of its own, written in its own code (Comprise's product-tree checks and its fourteen
rules). The generic reader does not run those, and says so (section 12.3).

### 12.2 The generic checks

| Check | Default severity | Catches |
|---|---|---|
| `load` | error | a file that does not parse, is not a mapping, or uses a forbidden construct; a `nodes:` entry with no string id; a volume layout that does not fit (a declared part with no folder, an undeclared folder); a refused declaration |
| `duplicate-id` | error | an id already loaded in the same module of the same part; the first wins |
| `id-grammar` | error | an id that does not parse in the MiniCOSM's id form |
| `id-module` | error | an id whose module the MiniCOSM does not declare, or, in a folder volume, an id whose module is not the module of the folder it is written in |
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
| `catalog-key` | error | a catalog key the manifest's `catalog.keys` does not list (a note); a catalog id that does not fit `catalog.id`, which names the database in every URI; a value outside the closed list the manifest gives a catalog key (section 13.5) |

### 12.3 Which checks run

- **`load` always runs.** A volume that could not be read cannot be checked.
- **The rest run when the manifest selects them**, by id, in `checks.envelope` (and `checks.load`, which Comprise uses
  for `load`). A duplicate id is always reported; under `duplicate-id` when the manifest selects it, under `load`
  otherwise, which is how Comprise reports it.
- **An unknown check id** in a manifest is kept and listed in the report as *not run*, with no error. Comprise's
  manifest selects checks the generic reader does not know (`id-atom`, `source-undeclared`, `owner`, `vendor-missing`,
  `bond`, `aim` and others); they are listed as not run, and a viewer says that Comprise's own rules need Comprise.
- **Severities.** A check reports at its default severity unless the manifest's optional `checks.severity` mapping
  (`{<check id>: error | warning | note}`, 0.0.1) gives another. The mapping sets the severity of a check's findings
  except those that are fixed: a problem found while loading (`load`, and a duplicate id) is always an error, and two
  findings are always notes, an unlisted catalog key (`catalog-key`) and a legacy kind read under its new name (`type`).

### 12.4 The report

```text
report  = { errors, warnings, notes, pending, not-run, ok }
problem = { check, item (or file), field, message }
pending = { item, field, question }
ok      = true when there are no errors
```

`ok` is the verdict the generic checks give. A MiniCOSM may give further verdicts of its own (Comprise's "may this
version be signed?", section 15).

### 12.5 Checks and writes

A MiniCOSM may say that every write goes through its checks and that a write which adds an error is undone. Comprise
does. MacroCOSM does not require it: a reader may report problems after a write and keep the write. enough reports the
generic checks when a `.cosm` file is saved and never refuses the save.

### 12.6 What the generic checks do not verify

What a domain means. The generic checks say a volume is well formed and closed: every item is in a declared table,
every required column is filled, every closed value is in its list, every reference has two ends. They do not say that
a product tree balances, that a claim is true, or that a role is lawfully held. Those are a MiniCOSM's own checks, or a
person's judgement. Ids that differ only in case, and slugs outside the path set, are not checked in 0.0.1.

---

## 13. The manifest

### 13.1 What it is

A **manifest** is the machine-readable declaration of a MiniCOSM: what a program needs to read, check and render its
volumes. It is one `.cosm` file, outside every volume. A volume names its MiniCOSM by its declaration and never embeds
the manifest.

The word has a second sense in Comprise: the list of files and hashes in a saved version, a backup or a published
concern. Both mean "the list of everything aboard". They never meet on screen.

### 13.2 Its format

A manifest is written in the COSM YAML subset and starts with its own declaration, `manifest: minicosm/0`: the
manifest format, version 0. Words that YAML 1.1 reads as booleans are quoted in a manifest, so that a reader using any
YAML loader reads it the same way.

### 13.3 The keys

These are the keys of Comprise's manifest, read generically, with the 0.0.1 additions marked. A reader keeps every key,
including the ones it does not use.

| Key | Holds | The generic reader uses it for |
|---|---|---|
| `manifest` | `minicosm/0` | knowing the file is a manifest |
| `name`, `title`, `version` | the MiniCOSM's name (the declaration's first half), its display title, its major version | the registry, the declaration |
| `summary`, `spec`, `reference`, `predecessor` | one line; where its prose and its code are; what it replaced | display |
| `declaration` | `key` (`oes`), `value` (`<name>/<major>`), `absent` (a declaration, or `refuse`), `legacy` (a list of `{key, value, reads-as}`), `both`, `unknown` (`refuse`) | identifying catalogs (section 5.2) |
| `format` | the extension, the subset, the forbidden constructs, the booleans, the encoding, the newlines | documentation; the reader's rules are section 4's |
| `volume` | `catalog`, `single-file` (0.0.1), the part and module places, `module-files`, `outside-the-model` | finding the files (section 6.3) |
| `catalog` | `keys`, `id`, `id-absent`, `source-fields`, and keys a MiniCOSM adds (Canon's `scope`) | `catalog-key`, the database name |
| `module-file` | `shapes`, `items` (0.0.1), `duplicate-id`, and MiniCOSM-specific keys | reading module files |
| `ids` | `item` (a regular expression), `item-form`, `brand-form`, `qualified-form`, the part's form, `inside-own-concern` | `id-grammar`, resolution |
| `paths` | `form`, `levels`, `segments` (one regular expression per level), `map`, `qualified`, `case`, `refused` | paths and URIs (section 11) |
| `envelope` | `fields`, `references`, `required` (and variants such as Comprise's `required-in-P`), `status`, `visibility`, `visibility-absent`, `provenance` (`fields`, `modes`, `states`, `state-default`), `open-question`, `sentinels`, `unknown-fields` | the envelope checks |
| `references` | `forms`, `dotted-fields`, `unresolved`, `exceptions` | `ref-grammar`, `ref-unresolved` |
| `links` | `rels`, a closed list of typed-link relations (0.0.1) | `closed-list` on `links[].rel` |
| `closed-lists` | a mapping from a field name to its closed list of values, applied wherever that field appears (0.0.1) | `closed-list` |
| `modules` | for each letter: `name`, `subtitle`, `note`, and `kinds`, each with `refs`, `required` (0.0.1), `checked` and MiniCOSM-specific keys | `type`, `type-prefix`, the reference checks, the viewer's rail |
| `checks` | `envelope` (the generic check ids that apply), `load`, `severity` (0.0.1), and the MiniCOSM's own (`products`, `rules`, `equilibrium` …) | selecting checks (section 12.3) |
| `open-questions` | the form, who answers, the field path | the pending list |
| `renderers` | a list of `{id, makes, code, status}`, and, from 0.0.1, `{id, lens}` | lenses (section 14) |
| `extension` | what a MicroCOSM may and may not do on top of this MiniCOSM | documentation (section 17) |
| `macrocosm` | reserved (section 5.6) | nothing |
| anything else | MiniCOSM-specific declarations (Comprise's `relationships`, `aims`, `versions`, `public-projection`) | kept; read only by that MiniCOSM's own code |

### 13.4 Read generically

A generic reader needs only the keys above to load, check and draw a volume. Everything it does not understand it keeps.
A manifest is never rewritten by a reader. The Comprise manifest that ships with enough is a byte copy of Comprise's own,
refreshed from it and never edited in enough.

### 13.5 What 0.0.1 adds

Optional keys new in 0.0.1: `volume.single-file`, `renderers[].lens`, `links.rels`, `closed-lists`,
`checks.severity`, Canon's `catalog.scope`, and the reserved `macrocosm`. A reader that does not know
them keeps them and loses nothing it relied on before. Section 20 gives the reason for each.

Three more optional keys, which the reference reader (`enough/macrocosm.py`) also reads:

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

### 13.6 The registry

A reader loads every `*.manifest.cosm` in its manifest folders into a **registry**. enough's are
`defaults/cosm/manifests/` (shipped, read-only); a folder for a person's own manifests, `~/enough/cosm/manifests/`, is
mapped. The registry order is `comprise`, `cosm`, `canon`, `emf`, then any other in name order. A manifest that does not
load, or that names a MiniCOSM already in the registry, is skipped and reported; the first one wins. The registry is
what step 1 of section 5.2 compares a declaration against, and what a refusal lists as known.

---

## 14. Renderers and lenses

### 14.1 Renderers

A **renderer** turns a volume into another form. Renderers only read. Each applies the reader's scope first: a hidden
item is absent from everything it makes (section 8.4).

A MiniCOSM's own renderers are its own (Comprise's 3D Overview, Field Guide, export and isotype). MacroCOSM defines
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
| `kind` | `mermaid` (the only kind in 0.0.1) | required |
| `diagram` | `flowchart` or `mindmap` | `flowchart` |
| `include` | the module letters to draw | every module |
| `edges` | reference fields (dotted and wildcard fields allowed), `links` (every typed link) or one link `rel` (only the typed links with that `rel`), and `parts` and `parent`, to draw as edges | every reference field, `links`, `parts` and `parent` |
| `shape` | a mapping from a kind to a Mermaid shape, written as its bracket pair with a space for the label (the pairs are listed below) | the kind's own shape (listed below); `'[ ]'`, a rectangle, for a kind with none |
| `class-by` | a field whose value names a class on each node, so a stylesheet can colour nodes by it (EMF: `stance`) | none |

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

**Well formed.** Node ids are Mermaid-safe, unique in the diagram, and the same for the same volume every time; labels
are quoted, so no label can end a subgraph or break a line; subgraphs balance.

### 14.5 Lenses that ship

| MiniCOSM | Lens | Draws |
|---|---|---|
| `canon` | `tree` | the volume's folders, files and articles, joined by `parent` |
| `cosm` | `tree` | the product tree, from the brand to its units, joined by `parts` |
| `emf` | `claims` | entities, concepts and claims, joined by role slots and typed links, coloured by stance |
| `emf` | `map` | the text's lexicon, entities, concepts, claims and events as a mindmap |
| `comprise`, `cosm`, `canon` | `map` (the generic lens) | every module, every reference field and typed link, `parts` and `parent` |
| `comprise` | `tree` (the generic lens) | the items joined by `parts` or `parent` |

In the reader's order, a volume has these lenses: a Holotype, `map` and `tree` (the `tree` only when its items carry
`parts` or `parent`); a cosm tree, `tree` and `map`; a Canon volume, `tree` and `map`; an EMF, `claims` and `map`. EMF's
own `map`, the mindmap, takes the place of the generic one.

---

## 15. Versions and signatures (by reference)

*Defined here, built in Comprise OES 1 (its section 10), not built in MacroCOSM 0.0.1.*

- **A saved version** is an immutable copy of a volume's model files at a moment, with a manifest that holds every
  file's hash, the checks' verdict and its own hash. Taking one changes nothing.
- **A signed version** is a saved version the checks allowed, whose files still match their hashes, signed by the
  holders of the roles that govern the volume.
- **The diff** between two saved versions is item by item, with the field paths that moved.

In 0.0.1 enough neither saves nor signs volumes. A reader treats a Holotype's `snapshots/` folder as outside the model.

Three other things carry versions, and none of them is a saved version: a MiniCOSM carries its major in the
declaration (`comprise/1`, section 5); the manifest format is `minicosm/0` (section 13.2); the grammar is 0.0.1, in the
reserved `macrocosm:` key (section 5.6). A path and a URI carry no version (section 11.3).

---

## 16. The private/public split (by reference)

*Defined here, built in Comprise OES 1 (its section 11), not built in MacroCOSM 0.0.1.*

The split is two formats, not one format with a setting.

- The **Holotype** is the complete, private description of one subject, kept by the subject, on the subject's machine.
- The **isotype** is a small public projection of it: a separate document with fixed fields, each derived from the
  Holotype by one rule, default-deny, released and signed by the subject. A field added to the model later never flows
  into it by itself.

The words come from taxonomy, where a holotype is the one specimen that defines a species and an isotype is a duplicate
of it. In MacroCOSM they name the two halves of the split in every MiniCOSM, not only Comprise's. In enough today a
Holotype means a Comprise volume, because Comprise is the only MiniCOSM with a split. Canon and EMF declare no public
projection in 0.0.1; their volumes are the owner's own files, and nothing in enough sends them anywhere.

A MiniCOSM with a split declares its public projection in its manifest (Comprise's `public-projection`), and the rules of
the projection are its own.

---

## 17. MicroCOSMs (mapped)

*Mapped in Comprise's `oes/README.md` (its section 5) and the `extension:` block of its manifest. Not built anywhere.*

A **MicroCOSM** is one organization's extension of a MiniCOSM.

**It may add:** kinds, in any module; fields, on any kind; checks, including stricter versions of the MiniCOSM's own;
renderers.

**It may never:** remove anything; rename anything; loosen anything (a closed list, a required field, a check's
severity); change what a path or an id means; weaken the split, by adding to a public projection or opening anything by
default.

What a MicroCOSM adds carries its name, `<microcosm>.<kind>` and `<microcosm>.<field>`, so that a later version of the
MiniCOSM can never collide with it. A volume written with a MicroCOSM is still a valid volume of its MiniCOSM: a reader
that does not know the MicroCOSM keeps its fields and ignores its checks.

How a volume says that it uses a MicroCOSM, and how a reader loads one, are not decided in 0.0.1 (section 21).

---

## 18. The MiniCOSMs enough ships

Four manifests ship in `defaults/cosm/manifests/`, one per MiniCOSM.

| MiniCOSM | Declaration | Enumerates | Volume | Catalog | Modules |
|---|---|---|---|---|---|
| `comprise` | `oes: comprise/1` | a company: its concerns, their relationships, eight modules each | a folder, the Holotype | `holotype.cosm` | C O M P R I S E |
| `cosm` | `cosm: 0.2` · `0.3`, `opi:` | one whole's product tree, outside any Holotype | a folder of `.cosm` files | the file holding `brand:` | P |
| `canon` | `oes: canon/1` | a Canon volume, or a project: folders, files, articles, and what has been derived from them | one file | `canon.cosm` | V |
| `emf` | `oes: emf/1` | one text: its words, the things and ideas it names, its claims, its events, its atems | one file, beside the text | `<text>.cosm` | L E K P T X |

### 18.1 comprise: Comprise OES 1

**What it enumerates.** Companies. A Holotype describes one company at a moment as a set of **concerns** (going
concerns: a corporation's branded face, a subsidiary, a joint venture) joined by **relationships**, each concern with
eight modules. The spec is Comprise's own, `oes/comprise-oes.md`; this section says only how it sits in MacroCOSM.

**Its declaration.** `oes: comprise/1`. A `holotype.cosm` without the key reads as `comprise/1`, silently, and so does
the legacy line `comprise: 0.1` that every Holotype made before Comprise OES 1 carries.

**Its volume.** A folder.

```text
<holotype>/
  holotype.cosm                         the catalog: oes: comprise/1, id, concerns, sources, grants
  atoms/<concern>/                      one part per concern the catalog declares
    C/ O/ M/ R/ I/ S/  **/*.cosm        module files, at any depth
    P/  brand.cosm nodes.cosm doc.cosm  the product tree, which keeps its own header, cosm: 0.3
    E/  README  or  none.cosm           people are never in a file
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
wikimedia) are the conformance corpus (section 19.3).

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

### 18.2 cosm: the standalone product tree

**What it enumerates.** One whole's product tree, as COSM 0.2 and 0.3 wrote it outside any Holotype: the brand, and
below it suites, offerings, functions, products and services, each answering the same nine questions (identity, flow,
substrate, rules, principles, economics, vocabulary, affect, mattering). The context-ontology skill still writes trees in
this form. The MiniCOSM exists so that they open, check and draw beside everything else.

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

The tree's own checks (its levels, its flows, the seven conditions of equilibrium) belong to the skill's `cosm.py` and
to Comprise; enough runs the generic checks only. A product-tree file taken out of a Holotype
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

### 18.3 canon: the store's enumeration

**What it enumerates.** Canon is enough's library: the store at `~/enough/canon/`, the file manager that browses it,
and the derivations that turn its texts into EMF twins and atems. A **Canon volume** is a top-level folder of the
store. Its catalog enumerates what the volume holds (folders, files, saved articles) and what has been derived from
each file: its markdown twin, its EMF twin, its atem. The same MiniCOSM enumerates a project's files (section 18.3.4).

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
| `counts` | `{folders, files, articles, twins, atems}`: the folder, file and article items; the files with an EMF twin; the files with an atem |
| `nodes` | the items |

#### 18.3.2 The module and its kinds

One module, V (Volume): *what the volume holds*.

| Kind | What it is | Its own fields |
|---|---|---|
| `folder` | a folder of the volume | `parts`; `holotype: true` when the folder holds a `holotype.cosm` |
| `file` | a file | `size`, `mtime`, `kind`, `twin`, `emf`, `atem`, `short_of`, `shorts` |
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
| `emf` | the file's EMF twin, `{path, state}`, its state `fresh` or `stale` (section 18.4.1) |
| `atem` | `{line}`: the file's atem line, copied from its EMF twin so a listing can show it without opening the twin |
| `short_of` | on a short (section 18.4.4), the path of the text it is a short of, when that text is beside it |
| `shorts` | on a text, the paths of the shorts beside it, in listing order, which is the order they were written |
| `title`, `source` | an article's title, and the address it was saved from |

**Required:** `id`, `type`, `name`, `path`. **Checks:** `load`, `duplicate-id`, `id-grammar`, `id-module`, `type`,
`identity-min`, `ref-unresolved`.

**What is never an item.** The catalog itself, `.canon.json`, a markdown twin (it appears as `twin:` on its original),
and an EMF twin (it appears as `emf:` on its text). This matches what Canon's listings show: twins hide behind the files
they belong to. A short is the opposite: an ordinary `file` item, the person's to read and edit, which nothing hides;
its `short_of` and its text's `shorts` are all that mark it. An `emf/1` file with no sibling text is an ordinary `file`
item of kind `cosm`. A folder holding a
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
  stay out of the tree. EMF twins hide behind their texts. A folder holding a `holotype.cosm` is one item, not
  recursed.
- **Its id** is `canon/~<project-slug>`, the project's name slugged; its URI is `oes:canon/~<project-slug>/<path>`.
- **Structure only.** A project's catalog holds no `size`, no `mtime`, no timestamps, and no twin states: its `twin`
  and `emf` entries carry the `path` alone, and a viewer works out the state when it shows one. The catalog changes only
  when files are added, removed or renamed, or when twins and atems appear, go or change, so a project kept in version
  control sees no churn from ordinary edits.
- **A cap.** At most 5,000 items. Past the cap, the folders not yet enumerated are listed without their contents, each
  with its `counts` and `pending: "too many files to enumerate here; open the folder in Canon"`.
- **When it is written.** When the project opens, when Canon reconciles the project's pane, when the catalog is read
  through the cosm viewer, and after any derivation in the project. It is written only when its bytes would change, and
  never from the file tree's own refresh.
- **Write-refused** like a volume's catalog.

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

**Three densities of one meaning: fabula (EMF) · short (SHORT) · atem.** A text's EMF twin, the fabula, holds its
meaning item by item (section 18.4); a SHORT tells it again as prose, in an order (section 18.4.4); an atem says it in
one line. The fabula is the material and a short is one arrangement of it. The atem is neither: it is a reduction, with
a hermeneutic shape of its own in push and pull.

- **Where an atem lives.** In the text's EMF twin. A file's atem is the twin's `atem:` block (section 18.4). Asking for
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
    emf: {path: guides/close.md.cosm, state: fresh}
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
    emf: {path: plan.md.cosm}
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
    emf: {path: research/interviews.txt.cosm}
    atem: {line: "Owners of six restaurants in Portland were interviewed in September 2026 about how and when they read their books."}
```

### 18.4 emf: a text's enumeration

**What it enumerates.** One text. **EMF** stands for *enumerated meaning fabula*: the fabula of a text, enumerated — the
order-free material a telling is made from. A text is decompiled into the words it leans on, the particular things and
people it names, the ideas it uses, the claims it makes and how it knows each one, the events it narrates in order, and
its atems; *fabula*, for short, is the everyday word for what that makes (section 18.4.4 says where the word comes
from). An EMF twin is not a summary. It is the text's meaning taken apart into items that can be checked, drawn,
compared and compiled back into prose. A text is what a person reads; its twin is what the text says, enumerated.

**Its declaration.** `oes: emf/1`. There is no legacy form, and a catalog without the key is refused.

**Its volume.** One file. An **EMF twin** sits beside its text and is named by adding `.cosm` to the text's whole name:
`close.md` and `close.md.cosm`. There is no `.emf` extension; the family has one. A twin's `source:` names its text;
an EMF file with no `source:` is a standalone EMF, read the same way.

#### 18.4.1 The catalog

| Key | Holds |
|---|---|
| `oes` | `emf/1` |
| `macrocosm` | reserved (section 5.6) |
| `id` | `emf/<slug>`, the slug being the text's path in its volume or project, respelled by the Canon rule (section 18.3.3): the twin of `guides/close.md` is `emf/guides--close-md` |
| `name` | the text's title, or its file name when it has none |
| `source` | the text: `{path, sha256, size, mtime_ns}`, its `path` relative to the twin (the sibling's file name); absent for a standalone EMF |
| `derived` | how the twin was made: `{at, by, model, mode, completeness, chunks}`: when; at whose request (`person`, or the readvisor's name); the model's id (absent in rules mode); `mode`, `model` or `rules`; `completeness`, `full` or `atem`; how many chunks the text was read in. A derivation that dropped items it could not repair records how many in `dropped` |
| `atem` | the whole text's atem: `{line, focus, push, pull}` (section 18.3.5) |
| `shorts` | the shorts compiled from the twin, one `{path, at, by, mode, order}` per compile, appended (section 18.4.4); absent until the first |
| `nodes` | the items |

**Fresh and stale.** A twin is `fresh` while its text's size and modification time match the twin's `source`, and,
when they differ, while the text's sha256 still matches. Otherwise it is `stale`. A text with no twin is `absent`. A
stale twin is kept and shown with its state; it is refreshed only when someone asks.

#### 18.4.2 The modules and their kinds

| Letter | Module | What it holds | Kinds | Reference fields | Also checked |
|---|---|---|---|---|---|
| L | Lexicon | the words the text leans on | `term` | | `feed`, `sense` |
| E | Entities | the particular things and people named | `person`, `org`, `place`, `work`, `thing` | | |
| K | Concepts | the ideas and universals the text uses | `concept` | `defined-by` | |
| P | Propositions | what the text claims, and how it knows | `claim` | `roles.*` | `stance`, `salience`, `span` |
| T | Transitions | what happens, in order | `event` | `agent`, `patient`, `before`, `after` | `when`, `span` |
| X | Atems | the tight reductions of passages | `atem` | `of` | `line`, `focus`, `push`, `pull`, `span` |

**Envelope.** Required: `id`, `type`, `name`, `summary`, `provenance`. EMF adds `span` and `salience` to the envelope.
**Closed lists:** `stance` (below), `salience` (`critical` · `high` · `normal` · `low`), and the nine link relations.
**Checks:** `load`, `duplicate-id`, `id-grammar`, `id-module`, `type`, `identity-min`, `provenance`, `ref-unresolved`,
`closed-list`.

#### 18.4.3 The conventions, in plain words

**Terms are grounded in FEED.** Every `L:term` says where its word stands in FEED, the dictionary enough ships:
`feed: {word, pos, origin}`, with `pos` the part of speech the text uses (one of those FEED lists for the word) and
`origin` either `feed` or `user` (a person's own dictionary). Its `sense` is the meaning the word has in this text: FEED's
definition when the text uses the word that way, the text's own sense when it does not. A word FEED does not hold is
written `feed: {pending: "not in FEED"}`, an open question, never a made-up entry.

**Claim summaries name everyone.** A claim's `summary` restates the claim as one sentence in which every participant is
named, by its name or its id, and no pronoun stands in for anyone. A reader can take any claim out of the twin and it
still says exactly what it said.

**Participants fill named role slots.** A claim's `roles:` is a mapping from a role name to the participant that fills
it: `{actor: E:org/meadow, act: K:concept/close, after: E:thing/bank-feed}`. The role names are free (`actor`, `object`,
`instrument`, `source`, `holder`, `cause`, `effect`, `condition` …). A slot holds an item id whenever the participant is
an item of the twin, and is then checked; otherwise it holds a literal (section 9.6).

**Every claim has a stance:** how the text knows it. The stance is required, and comes from a closed list of six, in the
spirit of the evidential markers some languages carry in their grammar:

| Stance | The text holds the claim as |
|---|---|
| `axiom` | given, or true by definition; the text does not argue for it |
| `observed` | seen, measured or done, at first hand |
| `deduced` | reasoned from other claims of the text, which the claim links to with `depends-on` or `supports` |
| `opinion` | a judgement or a preference of the author's |
| `assumed` | taken for granted: the text relies on it without stating it as a premise, or supposes it for the sake of argument |
| `hearsay` | reported from someone else, who fills the claim's `source` slot when the text names them |

**Typed links instead of arrows.** A relation between two items is a typed link in the first item's `links:`, never a
symbol between them. EMF closes the relations to nine:

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

**Every item points back at the text.** `span` says where in the text the item comes from: `{lines: "3"}` or
`{lines: "12-18"}`, or, when lines do not serve, `{start: "<up to 60 characters>", end: "<up to 60 characters>"}`,
quoted from the passage's first and last words. A reader jumps from an item to its passage by its span.

**Derived items carry their provenance.** Every item says `provenance: {mode: derived, sources: [...], confidence,
state}`. Its sources are locators in the text: the text's path and a line or a range, `'close.md#L3'`,
`'close.md#L12-L18'`.

**A scaffold says it is one.** When no model is available, enough still writes a twin, by rules: candidate terms and
entities from the text and FEED, and atems as in section 18.3.5. The catalog says `derived.mode: rules`. Every item it
writes has `confidence: 0.3`, `state: pending`, and `pending: "a model has not read this passage"`, and the viewer says
"scaffold, no model". A scaffold is a starting point a person can see through, never a guess dressed as a reading.

**Made on request, never in passing.** A twin is made when a person asks for it, or a readvisor's tool does. Nothing
that imports, copies, lists or reconciles files ever decompiles a text.

**Compiled back, it is told again.** Compiling a twin writes a short beside its text, and never touches the text
(section 18.4.4).

#### 18.4.4 Shorts

**What a short is.** A **SHORT**, *syuzhetic-hermeneutic open readable text*, is a telling of a text that enough
compiles from its EMF twin. It is *syuzhetic*: an arrangement, the twin's items put in an order. It is *hermeneutic*:
as it tells each thing it says how the thing is known, every claim's stance in plain words. It is *open*: it is plain
markdown that anyone can read without enough, it is yours to edit, it is honest about its gaps, and it is open to the
reader's own reading. It is *readable text*: prose, not a database. The name covers only what enough compiles.

**One fabula, many tellings.** A text's EMF twin is its fabula (section 18.4): the order-free material a telling is made
from. Every claim is there with its stance, every event with its own before and after, every term grounded, and each
item's `span` says where in the telling it was found. A *syuzhet* is a telling of that material, an arrangement of it.
The author's text is a syuzhet of the same fabula, the first one, and it is the author's: it is never called a short. A
short is a syuzhet enough compiles, and a text can have many. The atem sits outside the pair. It is the breath of the
text, a reduction with its own hermeneutic shape (push and pull), neither material nor arrangement.

**Two orders.**

| Order | In words | How it tells |
|---|---|---|
| `told` | as the author told it | every item with a span, in the order of its span: by first line, then last line, and within one line the words, the names, the ideas, the claims, then the events. Under the text's own headings when the text can be read (a span given as quotes is then placed on its line). Items that no span places come last, under "Also in the fabula" |
| `weight` | by weight | the claims in order of salience, grouped by the concepts they lean on; then the events, in before/after order; then the terms |

Both open with the atem line, and both say each claim's stance in plain words ("the author holds that", "it is assumed
that", "reportedly"). Pinned passage atems are not told: like the file's atem, they stand outside the telling. With no
order given, a compile tells `told` when the twin names a source text that can be read, and `weight` for a standalone
EMF. Without a model a short is the ordered outline itself, said in the items' own sentences; with one, a model writes
the outline as prose and is told which order it is in. A third order, the events first in the order they happened, is
planned.

**The file.** A short is written beside its text as `<text-stem>.short-<YYYY-MM-DD-HHMM>.md`, in local time:
`notes.md` gives `notes.short-2026-10-23-1042.md`, and a standalone `rain.cosm` gives `rain.short-…md`. A second compile
in the same minute takes `-2`, then `-3`. Every compile is a new file. Nothing is overwritten, and the text is never
touched. A short is an ordinary markdown file, shown in every listing; Canon's catalogs mark it `short_of` its text,
and the text `shorts` (section 18.3.2).

**The footer.** Every short ends with one italic line that says what it is a short of, in which order, when, and by
which model or by rules:

```text
*a short of notes.md, told as the author told it, compiled from its EMF twin on 2026-10-23 by g40-04*
```

Without a model the line ends "by rules, without a model". A short of a standalone EMF says so: "a short of rain.cosm,
a standalone EMF, told by weight, compiled on …".

**The fabula records its tellings.** Each compile appends one entry to the twin's `shorts:` list, `{path, at, by,
mode, order}`: the short's file name beside the twin; when, as a timestamp in UTC; the model's id, or `rules`; `model`
or `rules`; `told` or `weight`. The list is made just above `nodes:` the first time. Nothing else in the twin changes:
not its items, not its `source:` (a fresh twin stays fresh), not a byte of the rest.

**Where the words come from.** *Fabula* and *syuzhet* are the Russian Formalists' pair: the story as it happened, and
the story as it is told. Their work on how a telling makes the familiar strange began with Viktor Shklovsky's *Art as
Technique* (1917), and Boris Tomashevsky's *Thematics* (1925) set the two terms out. MacroCOSM borrows the pair for
meaning rather than plot: the twin is the material, and a short is one telling of it.

#### 18.4.5 An example

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

Its twin, `guides/close.md.cosm`, made by a model and compiled once into a short. Each of the six stances appears
once.

```cosm
oes: emf/1
macrocosm: 0.0.1
id: emf/guides--close-md
name: The morning close
source: {path: close.md, sha256: d297e46db2cbd55a0fb8af894c130604f087455510bec9417548ce3742191b14, size: 494, mtime_ns: 1792660324518000000}
derived: {at: 2026-10-22T09:15:30Z, by: person, model: g40-04, mode: model, completeness: full, chunks: 1}
atem:
  line: Meadow closes each customer's books overnight once the bank feeds arrive, locks the day, and retries a failed close before anyone opens the summary.
  focus: How Meadow's overnight close works, what it guarantees, and what it waits on.
  push: Trust the morning summary, because every day is locked and a failed close is caught before seven.
  pull: The summary is only as early as the bank feeds, which Meadow does not control, so a late feed still delays it.
shorts:
  - {path: close.short-2026-10-22-0931.md, at: 2026-10-22T09:31:12Z, by: g40-04, mode: model, order: told}
nodes:
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
```

A minimal twin, made by asking for the atem of `research/interviews.txt` (the project of section 18.3.6) with no model
running. It holds the atem and nothing else, and says it is a scaffold.

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

---

## 19. Conformance

### 19.1 A reader must

1. Read a catalog and identify its MiniCOSM by section 5.2; refuse an unknown MiniCOSM or major, a value not spelled
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

### 19.2 A writer must

1. Write the declaration first in a new catalog, and never rewrite the declaration of a volume it did not create.
2. Write only the COSM YAML subset: no anchors (copy values instead of sharing them), no aliases, no tags, one document.
3. Write ids in the MiniCOSM's form, with the kind equal to `type`, and never rename one.
4. Write an open question, never a guess; give every fact its provenance.
5. Keep the fields it does not understand when it rewrites an item.
6. Write nothing into a file that its MiniCOSM keeps out of files (Comprise's people).
7. Where its MiniCOSM says that checks gate writes, leave the volume's checks no worse.
8. Write a catalog that a program owns (a Canon catalog) only from that program; and make derived items (an EMF twin,
   an atem) only when a person or a readvisor asks.

### 19.3 The conformance corpus

A reader conforms to MacroCOSM OES 0.0.1 when:

- Comprise's four public sample Holotypes (meadow, khan-academy, mozilla and wikimedia; 1,010 items between them) load
  through the generic reader and Comprise's manifest with no load problems, and every item has the path Comprise gives
  it;
- every block marked `cosm` in this document loads, identifies as the MiniCOSM it declares, and passes the checks its
  manifest selects with no errors;
- every path in the table of section 11.2 resolves to the id beside it;
- each refusal case of section 5 (an unknown MiniCOSM, an unknown major, a misspelled value such as `comprise/01` or
  `' emf/1 '`, an empty `oes:`, a catalog with no declaration at a name no default claims) is refused, and each legacy
  case is read.

The reader's own tests are the tie-break. Where they and this list disagree, the tests win and this section is
corrected.

### 19.4 Where the reader wins

No disagreement between this text and `enough/macrocosm.py` is known at the time of writing. When one is found, the
text is corrected and the disagreement is recorded here, with the section it touched, until the next version folds it
in.

---

## 20. Decisions in this version

1. **MacroCOSM is the grammar Comprise mapped, made real.** Not a new taxonomy. Comprise OES 1 already held every part
   of the grammar; a second one would split the family.
2. **The format does not change.** One loader, Comprise's, for every `.cosm` file. Hundreds of existing files read as
   they are.
3. **One declaration grammar,** `oes: <minicosm>/<major>`, for every MiniCOSM, with each manifest naming the legacy
   forms it still reads. One line a person sees without parsing the file.
4. **An absent-declaration default claims only its own catalog file.** Comprise reads a `holotype.cosm` without `oes:`
   as `comprise/1`; a generic reader that applied the default everywhere would claim every YAML file it was shown.
5. **A refusal is a value, not an exception.** A viewer shows the refusal in place of the volume and goes on.
6. **`macrocosm:` is reserved and ignored.** Room for a grammar version test later, without refusing any file today.
7. **Single-file volumes.** A Canon volume and an EMF twin are one catalog each; a folder per text would double every
   tree.
8. **Module letters are local to a MiniCOSM.** The declaration already says which language a volume speaks; reserving
   letters across languages would run out of letters and buy nothing.
9. **Paths drop the part level when a MiniCOSM has no parts.** A single-file volume has one implicit part, and a segment
   that never varies is noise.
10. **Wildcard reference fields check only id-shaped values.** Role slots mix item ids with literals such as conditions;
    checking literals as ids would make every condition an error.
11. **Link relations may be closed.** EMF closes them so that twins can be drawn and compared; Comprise keeps its own
    free.
12. **Closed lists and severities by name, in the manifest.** A MiniCOSM's own vocabularies (stance, salience) and its
    severities are checked without new code.
13. **Lenses are declared in the manifest, with a default.** A MiniCOSM can be drawn without code; Comprise's manifest,
    a byte copy that declares no lens, still draws with `map`.
14. **Generic checks only.** A MiniCOSM's own rules are its own code. Reproducing Comprise's fourteen rules in enough
    would fork Comprise; a viewer says plainly that they need Comprise.
15. **Checks may gate writes; MacroCOSM does not require it.** Comprise undoes a write that adds an error. enough edits
    raw text and reports problems after a save, never refusing it.
16. **`load` always runs.** Nothing can be checked that was not read.
17. **Versions, the split and MicroCOSMs are by reference or mapped.** They are built only in Comprise, or nowhere; their
    mechanics stay Comprise's until a second MiniCOSM needs them.
18. **A URI between volumes is a value, not a reference.** Resolving across volumes needs a registry of volumes this
    version does not define.
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
24. **The specification lives in enough for now.** Comprise vendors it later, with the reader.
25. **All rights reserved for the specification and the manifests; the reader is Apache 2.0** with the rest of enough.
26. **What enough compiles from a twin is a SHORT, written beside the text and recorded by the twin.** One fabula, many
    tellings: the EMF twin, *enumerated meaning fabula*, is the material and a short one arrangement of it. The author's
    text is the first arrangement and is never called a short; the atem stays outside the pair. Every compile is a new
    file in one of two orders, the author's or by weight, and the twin lists its shorts so the material knows its
    tellings.

---

## 21. Open questions and roadmap

### 21.1 Mapped, not built

- **MicroCOSMs** (section 17). How a volume says that it uses one, how a reader loads one, and how its names are kept
  apart from a later version of its MiniCOSM's own.
- **Shared public forms.** A vocabulary of kinds of thing that many subjects name ("chair", "M4 screw", "invoice",
  "lease"), each defined once, in public, and cited by id from any MiniCOSM that needs it, so that two volumes that name
  the same kind of thing name it checkably.
- **People, as a MiniCOSM with its own rules.** It comes last, and comes with rules no other MiniCOSM has: the person
  holds the keys, only the person releases anything, and no other subject's volume ever holds a person's private detail.
- **Style-profile renderers.** Today a renderer decides how a volume looks. Later a renderer follows two envelopes,
  whose planned names are the **Holomorph**, an author's intent envelope carried with the text, and the **Isomorph**, a
  reader's own profile (how much detail, which words, which pictures, beginner or expert). The same truth is then retold
  for a beginner, set as story problems, told as narrative or drawn as a scene. These morph-driven renderers need a later
  version of the grammar.
- **Other MiniCOSMs.** An industry or a market, a body of knowledge or a practice, an institution, a built world.
- **Universal addressing.** A globally unique database name, and a resolver for URIs across installs.
- **Editing in place.** Byte-preserving edits of one item inside a file, so that a structured viewer can edit without
  losing comments; syntax highlighting for `.cosm` in the editor.
- **SQL views** over the reader's tables, one per kind.

### 21.2 Left open by this version

- Whether a person's own manifests may precede the shipped ones in the registry, and how a reader reports a clash.
- Whether `checks.severity` may lower a default severity, or only raise it.
- Whether ids that differ only in case, and ids whose slugs fall outside the path set, become generic checks.
- Whether a URI written in a field becomes a reference, once volumes have a registry.
- Whether a catalog with no `id` is an error. When the manifest's `catalog.id` is a template, `catalog-key` reports a
  missing id as an error; when the manifest gives `catalog.id-absent`, a reader supplies the id instead (section 6.2).
  No manifest that ships has both, since the two that give `id-absent` (comprise and cosm) do not select `catalog-key`.
  A manifest that had both would get the error and the supplied id.
- How a project's catalog and a Canon volume's catalog of the same folder relate when a project is copied into Canon.

---

## Appendix: the mapping to Comprise OES 1

Section by section, where each part of this document comes from in Comprise OES 1 (`oes/comprise-oes.md`), its map
(`oes/README.md`) and its manifest (`oes/comprise-oes.manifest.cosm`), and what changed on the way.

| MacroCOSM OES 0.0.1 | Comprise OES 1 | What changed |
|---|---|---|
| 1 Provenance and the name | the opening note; README §2; P.11 | the lineage carried one step further |
| 2 The model on one page | §1, the map | "Holotype" became "volume", "concern" became "part"; the store left the table |
| 3 Scales | README §2–§4 | MacroCOSM's parts listed against this document's sections |
| 4 The file format | §2.5; the manifest's `format` | the loader written out; the YAML 1.1 surprises tabled |
| 5 The declaration | §2.3; decision 13 | any MiniCOSM; the absent default scoped to its own catalog file; a registry order |
| 6 Volumes and catalogs | §2.1, §2.2, §2.4, §2.7, §2.8; §3.1 for parts | single-file volumes; concerns generalized as parts |
| 7 Items, kinds, fields | §2.4; §5's opening; §6.4.6 | module letters local to a MiniCOSM; wildcard fields |
| 8 The envelope | §4, §4.1, §4.2, §4.3 | a nine-field minimum; required fields per MiniCOSM |
| 9 References and links | §7 | closed link relations; literals in wildcard fields; URIs as values |
| 10 Open questions | §8 | unchanged, with the `pending-shape` check |
| 11 Ids, paths, URIs | §6 | levels from the manifest; no part segment without parts |
| 12 Checks | §9.1, §9.2 | a fixed generic vocabulary; unknown ids reported as not run |
| 13 The manifest | README §4; the manifest; decisions 15–16 | read generically; optional 0.0.1 keys; the registry |
| 14 Renderers and lenses | §12; P.8 | lenses declared in the manifest; a default lens |
| 15 Versions and signatures | §10 | by reference |
| 16 The private/public split | §11 | by reference; the words named for every MiniCOSM |
| 17 MicroCOSMs | README §5; the manifest's `extension` | mapped, unchanged |
| 18.1 comprise | the whole of Comprise OES 1 | how it sits in MacroCOSM |
| 18.2 cosm | chapter P, P.7; COSM 0.2 | a MiniCOSM for trees outside a Holotype |
| 18.3 canon, 18.4 emf | none | new MiniCOSMs, written in the grammar |
| 19 Conformance | §13 | the corpus named; the reader wins |
| 20 Decisions | §14 | this version's own |
| 21 Roadmap | README §7; §12's *not built* | the morph-driven renderers named |

**What stays Comprise's alone.** Concerns and relationships (its §3), the eight modules' kinds and fields (§5), the
product tree's checks and its seven conditions (P.9), the fourteen rules and the verdict (§9.3, §9.4), the isotype's
fields and rules (§11.3), and the people, who are never in a file (§2.6, §2.8). MacroCOSM reads all of them, keeps them,
and leaves their meaning to Comprise.

---

## Colophon

MacroCOSM OES — Copyright © 2026 Graham Smith. All rights reserved.

This specification is not covered by enough's Apache License 2.0; see `defaults/cosm/NOTICE.md` for its terms.
