# OES: the paradigm map

*What an organizational enumeration system is, the three scales of COSM, and where Comprise OES sits among them.
Written 2026-10-20 for phase 10 (decision Q54, slice 30b). The spec is `comprise-oes.md`; the machine-readable
declaration is `comprise-oes.manifest.cosm`. `MO.md`, in the repository, says why any of this exists.*

## The short version

Comprise describes a company as a file system that is also a relational database. Every concern (one company, or one
part of a group, described on its own) is a folder, every module a set of tables, every item a row with a path. A
system of that shape is an **OES**, an *organizational enumeration system* (section 1), and the shape is not special to
companies. Written down once, as a shared grammar, it can describe an industry, a body of knowledge, an institution or
a built world the same way. The shared grammar is **MacroCOSM**. A grammar specialized for one domain is a **MiniCOSM**; **Comprise OES** is the first.
One organization's additions on top of a MiniCOSM are a **MicroCOSM**. Only Comprise OES is built. The rest is mapped,
so that Comprise OES fits it when it comes.

## 1. What an OES is

An **OES**, an *organizational enumeration system*, is a system that organizes a domain by enumerating everything in it,
as a file system that is also a relational database, made to be rendered.

- **Enumerating.** It lists what there is, item by item, each with its sources. What is unknown is an open question with
  the name of the role that can answer it, never a guess.
- **A file system.** Plain text files in folders, on the subject's own machine. Anyone can read them without the app,
  move them, keep them in version control, and leave with everything.
- **A relational database.** Every item has a primary key (its id), its fields are columns, its references are foreign
  keys, and checks are constraints. The same files can be indexed and queried.
- **Made to be rendered.** The description is never the end. It exists to be turned into other forms for other
  readers: a 3D scene, a summary, chapters for a person, an export for an agent, a public projection. A renderer can
  only show what the description holds, so the description is held to account.

## 2. Three scales

**COSM** is the family's name. It is no longer an acronym: it was *Context Ontology Schema and Markup*, and before that
*OPI*; both are history. It comes from *kosmos*, order and world. `.cosm` is the family's file extension.

| Scale | What it is | Example | State |
|---|---|---|---|
| **MacroCOSM** | the whole language: the shared grammar every MiniCOSM is written in | (one) | mapped, not built |
| **MiniCOSM** | an OES for one domain, declared by a manifest: its folders, kinds, fields, references, checks and renderers | **Comprise OES** (companies) | Comprise OES 1 is built |
| **MicroCOSM** | one organization's extension on top of a MiniCOSM: the extra kinds, fields or checks it needs | (none yet) | mapped, not built |

The names borrow an old idea, from Greek philosophy to the Renaissance: that a small world mirrors the order of the
great one. Here each smaller scale keeps the order of the larger and adds to it.

## 3. What MacroCOSM gives every MiniCOSM

The shared grammar. Every MiniCOSM inherits all of it, unchanged. Comprise OES is where each part was first worked out;
the right-hand column says where.

| Part | What it is | In Comprise OES |
|---|---|---|
| **Paths, and a URI form** | every top-level part (a concern, in Comprise OES), module, kind, item and field has an address that respells its id as a location; a qualified form adds the MiniCOSM and the database: `oes:<minicosm>/<database>/<path>` | `mozilla-foundation/P/offering/creative-futures`; `oes:comprise/mozilla/mozilla-foundation/P/offering/creative-futures` (spec §6) |
| **Items, fields and references** | an item is a row with a stable id and a kind; its fields are columns; a reference is an id written in a field, and every reference must have two ends | `P:offering/ledger`; `owner: O:role/Founder` (§4, §7) |
| **The envelope** | the columns every item has, whatever its kind: owner (a role, never a person), status, visibility, provenance (how it is known, from what sources, how surely) | §4 |
| **Open questions** | a value nobody has given yet, written where the value would go, with who can answer it; never a guess | `{pending: "…"}` (§8) |
| **Checks** | constraints on the whole database, run on every write; a write that breaks one is undone; a verdict says whether this moment may be signed | the lint, P's checks, the fourteen rules (§9) |
| **Saved and signed versions** | an immutable copy of the files at a moment, with a manifest of hashes; a copy the checks allowed, signed by the roles that govern it | snapshots and attestations (§10) |
| **The private/public split** | two formats, not one with a setting: the complete private description (the **Holotype**), kept by its subject, and a small public projection of it (the **isotype**), default-deny, released and signed by the subject | the Holotype, `comprise-isotype/0` (§11) |
| **Renderers** | anything that turns the database into another form; renderers only read, and show a reader only what that reader may see | the 3D Overview, the Field Guide, the export (§12) |
| **The manifest** | the machine-readable declaration of a MiniCOSM: what a program needs to read, check and render its databases | `comprise-oes.manifest.cosm` |

The words *Holotype* and *isotype* come from taxonomy, where a holotype is the one specimen that defines a species and
an isotype is a duplicate of it. They name the two halves of the split in every MiniCOSM, not only Comprise's.

## 4. What a MiniCOSM declares

A MiniCOSM is declared by its **manifest**: one `.cosm` file, outside every database, that says

1. its **name and version** (`comprise`, `1`), and the **declaration** a database uses to name it (`oes: comprise/1`),
   with any legacy forms it still reads;
2. its **volume layout** (the folder one database is): the catalog file at its root, which says what the database
   holds, the folders for subjects and modules, and where versions and the local database live;
3. its **modules and kinds**, and for each kind its **fields**: at least the reference fields, which the checks follow;
4. its **reference kinds**: the id forms, the relationship kinds, the closed lists;
5. its **checks**, by id, with their severities and what the verdict means;
6. its **renderers**;
7. its **public projection**: the fixed fields of the isotype, and the rule that derives each one.

A database names its MiniCOSM with one line in its catalog and never embeds the manifest. A reader that does not know
the MiniCOSM or the version a database declares refuses it with a plain error.

*The word manifest* has two senses in Comprise. This one is a declaration of a language. The other is the list of files
and hashes in a saved version, a backup or a published atom. Both mean "the list of everything aboard". They never
meet on screen.

## 5. What a MicroCOSM may change

A MicroCOSM is one organization's extension of a MiniCOSM. It is mapped here, not built.

**It may add:**

- kinds, in any module;
- fields, on any kind;
- checks, including stricter versions of the MiniCOSM's own;
- renderers.

**It may never:**

- remove anything;
- rename anything;
- loosen anything: a closed list, a required field, a check's severity;
- change what a path or an id means;
- weaken the split: it adds nothing to the public projection, and opens nothing by default. Only the MiniCOSM, in a new
  version of its projection format, can add a public field, and only as one the subject opts into.

What a MicroCOSM adds carries its name, `<microcosm>.<kind>` and `<microcosm>.<field>`, so a later version of the
MiniCOSM can never collide with it. A database written with a MicroCOSM is still a valid database of its MiniCOSM: a
reader that does not know the MicroCOSM keeps its fields and ignores its checks.

## 6. Where Comprise OES sits

Comprise OES is the first MiniCOSM, and the one MacroCOSM is being read out of.

- **Its domain** is companies: each company is a set of **concerns** (going concerns: a corporation's branded face, a
  subsidiary, a joint venture) joined by **relationships** (owns, controls, licenses, supplies…). Each concern has eight
  modules, C · O · M · P · R · I · S · E: Corporation, Organizations, Markets, Products, Representations, Inventories,
  Stacks, Employees.
- **Its database** is a **Holotype**: one folder describing one company, at a moment.
- **Its chapter P** is the old COSM product tree (the brand, suites, offerings, functions, products and services, each
  answering nine questions), whole.
- **Its reference implementation** is `core/` in this repository: where the spec and the code disagree, the code wins.
- **Its version** is 1. Every Holotype made so far is a Comprise OES 1 Holotype as it stands; the legacy line
  `comprise: 0.1` reads as `oes: comprise/1`.

Comprise OES is shaped to slot into MacroCOSM: the parts in section 3 are written so that nothing in them says
"company".

## 7. Connections to the wider ecosystem

None of this is built. It is the reason the grammar is shared.

- **Other MiniCOSMs, for other subjects.** An industry or a market, a body of knowledge or a practice, an institution,
  a built world (a fiction, a game, a franchise), and later people. Each declares its own kinds and checks in its own
  manifest, and keeps the grammar, the envelope and the split. People come last and come with their own rules: the
  person holds the keys, only the person releases, and no other subject's database ever holds a person's private detail.
- **A shared vocabulary of public forms.** Kinds of thing that many subjects name: "chair", "M4 screw", "invoice",
  "lease". A form is defined once, in public, and every MiniCOSM that needs it cites it instead of redefining it, the
  way an item cites another by id. Two companies that sell M4 screws then sell the same kind of thing, checkably.
- **Renderers driven by a reader's own style profile.** Today a renderer decides how a Holotype looks. Later a reader
  brings a profile (how much detail, which words, which pictures, beginner or expert) and the renderer follows it: the
  same truth, rewritten for beginners, set as story problems, told as narrative, drawn as a scene. The trade calls the
  text cases *transcreation*.
- **Universal addressing.** Because every item has a path, and a path qualified with its MiniCOSM and its database is a
  URI, anything described anywhere can be pointed at: by a person, by an agent, by another database's reference. What
  the reader may see at that address is still the subject's choice.

## 8. The picture

```
                 MacroCOSM: the shared grammar (mapped, not built)
   paths and URIs . items, fields, references . the envelope . open questions
   checks . saved and signed versions . the split . renderers . the manifest
                                  |
        +-------------------------+--------------------------+
        |                         |                          |
  Comprise OES 1           an industry OES           a built-world OES  ...   MiniCOSMs
  companies, C O M P R I S E   (not built)              (not built)
        |                                  \               /
        |                     cite: shared public forms ("chair", "M4 screw") (not built)
        |
  a MicroCOSM: one organization's added kinds, fields, checks (not built)
        |
  Holotypes: one private volume per subject  --- projection --->  isotype: public, signed, default-deny
        |                                                              |
  renderers: the 3D Overview, the Field Guide, the export ...    the Index, only if the subject lists it
        ^
  a reader's style profile (not built)

  every box above is addressable:  oes:<minicosm>/<database>/<concern>/<module>/<kind>/<slug>#<field>
```

## 9. What is built today

| Part | State | Where |
|---|---|---|
| Comprise OES 1: the format, the eight modules, the checks | built | `core/`, the fixtures, the app |
| The spec and the manifest | written (this phase) | `oes/comprise-oes.md`, `oes/comprise-oes.manifest.cosm` |
| The declaration `oes: comprise/1` | built: read, default, write and refuse (slice 30c) | `core/model.py`, `core/align.py` |
| Paths (CLI, MCP, the export, `/h/{key}/at/<path>`, the item page's Details) | built (slice 30c) | `core/paths.py`, spec §6 |
| The qualified URI `oes:comprise/<holotype>/<path>` | read by the CLI and MCP within one install; no resolver across installs | spec §6.4.7 |
| The split: Holotype, isotype, encrypted backups, the Index | built | the app, the vault, the Index |
| Saved and signed versions | built | `snapshots/` |
| Renderers: 3D Overview, circles, Field Guide, export, reports, isotype | built | spec §12 |
| A manifest reader (load a MiniCOSM from its manifest) | not built | |
| MacroCOSM as a separate grammar | not built (mapped here) | |
| MicroCOSMs | not built | |
| Other MiniCOSMs | not built | |
| Shared public forms | not built | |
| Style-profile renderers | not built | |

## 10. In this folder

| File | What it is |
|---|---|
| `README.md` | this map |
| `comprise-oes.md` | Comprise OES 1, the spec: the map, the volume, the modules (P is the product tree), paths, checks, versions, the split, renderers, conformance, and the decisions in this version |
| `comprise-oes.manifest.cosm` | the first MiniCOSM manifest, machine-readable; loads with `yaml.safe_load` and agrees with `core/schema.py` |
