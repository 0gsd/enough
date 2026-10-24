# Comprise OES 1

*The specification of Comprise OES, version 1: the MiniCOSM for companies. Written 2026-10-20 for phase 10 (decision
Q54, slice 30b). It replaces COSM 0.3, the earlier spec of the product tree (now history), as the description of the
format; COSM 0.3's product tree is chapter P below, whole. Read `oes/README.md` first for where this sits; `MO.md`, in
the repository, says why.*

**Status.** Normative. The code in `core/` is the reference reader and writer. Where this text and the code disagree,
**the code wins**, and the text is corrected; every disagreement known today is marked *code wins* where it occurs and
collected in chapter P.12 and section 13.4. *Not built* marks what is mapped and not yet in the code.

**The format does not change.** A Comprise OES file is a `.cosm` file: the COSM YAML subset (section 2.5) and, for
sketches, the one-line shorthand (P.6), exactly as Holotypes were written before this version. Version 1 names the
format and maps it; it adds one line to the catalog (section 2.3) and one way to address things (section 6). Every
Holotype made so far is a Comprise OES 1 Holotype as it stands.

## Contents

1. The map: a file system that is also a relational database
2. The volume
3. Concerns and relationships
4. The envelope
5. The eight modules
6. Paths
7. References
8. Open questions
9. Checks
10. Versions
11. The private/public split
12. Renderers
13. Conformance
14. Decisions in this version

## How to read this

**Words.** The words a person reads on screen come first (they are `MO.md`'s). Where the spec must be exact, the model's
own term follows in parentheses, because it is the one the files, the ids and the command line use. *Details*, in the
table below, is the disclosure on a page that shows ids, files and paths.

| Here | The model's term | In the files |
|---|---|---|
| concern | atom | `atom/<slug>`, `atoms/<slug>/` |
| relationship | bond | `C:bond/<slug>` |
| outside organization | stub | `C:counterparty/<slug>` |
| item | node | `<Module>:<kind>/<slug>` |
| kind | type | `type:` |
| open question | pending | `{pending: "…"}` |
| checks | lint, equilibrium rules | `python -m core lint` |
| saved version, signed version | snapshot, attestation | `snapshots/<stamp>/` |
| the local database | store | `store.sqlite` |
| export for agents | pack | `CONTEXT.md` |

**Must and may.** *Must* is a rule a conforming reader or writer keeps. *May* is a permission. *Should* is advice the
checks do not enforce.

**Sources.** `core/schema.py` (kinds, references, closed lists, the id grammar), `core/model.py` (loading and
resolution), `core/paths.py` (paths), `core/lint.py` (the envelope and the fourteen rules), the vendored `cosm.py`
(chapter P's checks), `core/isotype.py` (the public projection), `plan/comprise-model.md` (the model, draft 1), and
COSM 0.3 (decision Q29; the full COSM 0.2 and 0.3 text survives in `plan/cosm/cosm-spec.md`, and the vendored
`references/cosm-spec.md` is now a pointer to this spec that keeps only the nine aspects' sections the app reads). The
machine-readable form of everything here that a program needs is `oes/comprise-oes.manifest.cosm`.

---

## 1. The map

A Holotype is a file system that is also a relational database. Every part of Comprise OES has a place in both.

| Comprise OES | As a file system | As a relational database | On screen | Section |
|---|---|---|---|---|
| Holotype | a volume: one folder, `holotype.cosm` at its root | a database | Holotype | 2 |
| `holotype.cosm` | the volume label and superblock | the catalog: the MiniCOSM and version, the concerns, the sources | (Details) | 2.2 |
| concern (*atom*) | a top-level folder, `atoms/<slug>/` | a schema | concern | 3.1 |
| module (C … E) | a folder per letter | a group of tables | module | 5 |
| kind (*type*) | a `.cosm` file (or several) holding that kind's items | a table | kind | 5 |
| item (*node*) | an entry, addressed by its path | a row; its id is the primary key | item | 4 |
| field | an attribute | a column | field | 4, 6.4.6 |
| the envelope (owner, status, visibility, provenance) | the entry's metadata: owner, permissions, origin | system columns every table has | responsible role, who can see it, source | 4 |
| reference (`P:offering/x` in a field) | a link | a foreign key | a link to the item | 7 |
| relationship (*bond*) | a link between two concerns' folders, with its own attributes | a join row with columns (bases, dates, sources) | relationship | 3.2 |
| outside organization (*stub*) | a mount point for something outside the volume | a foreign table | outside organization | 3.3 |
| open question (*pending*) | a placeholder entry, with who must fill it | NULL with a reason and an owner | open question | 8 |
| checks (lint, the fourteen rules) | `fsck`, the file system check | constraints | checks | 9 |
| saved version (*snapshot*) | a snapshot of the volume | a point-in-time copy | saved version | 10 |
| signed version (*attestation*) | a signed snapshot | a signed checkpoint | signed version | 10 |
| the local database (*store*) | the volume's index (what Spotlight keeps), plus a sealed vault for people | materialized indexes; the people tables, sealed | the local database | 2.8 |
| isotype | a read-only public mount of a projection | a view: default-deny, fixed columns | isotype | 11 |
| export (*pack*, `CONTEXT.md`) | an archive for one reader | a dump for one audience | export for agents | 12 |
| renderer | a viewer | a report | the 3D Overview, the Summary, the chapters… | 12 |
| backup (*bundle*) | an encrypted disk image | an encrypted backup | backup | 11 |
| path | a path | a qualified key | (Details) | 6 |

**What is real in each reading.** The file system is the Holotype itself: plain text, on the subject's machine,
canonical. The relational database is real in part. `store.sqlite` holds a `nodes` table (one row per item, keyed by
concern and id, with its envelope columns and the whole item as JSON), an `edges` table (one row per resolved
reference: source, field path, target) and a full-text index, all rebuilt from the files by `python -m core index`;
and it holds the tables that are canonical and never in a file (the people, feed rows, series, accounts, releases).
SQL views over the local database, one per kind, are *not built*: the "table" of a kind is, today, the set of items
whose id carries that kind.

The two readings agree because one rule holds: **a path names the same thing a primary key does** (section 6).

---

## 2. The volume

### 2.1 Layout

```
<holotype>/                              the volume
  holotype.cosm                          the catalog (2.2): `oes: comprise/1`, id, concerns, sources, grants
  atoms/<concern>/                       one folder per concern declared in the catalog
    C/ O/ M/ R/ I/ S/   *.cosm           module files (2.4), at any depth under the module's folder
    P/  brand.cosm nodes.cosm doc.cosm   the product tree (chapter P.7)
    E/  README  or  none.cosm            people are never in a file (2.6)
  vendors/<domain>/<slug>/               a vendor-published atom, fetched and verified; read-only (3.5)
  snapshots/<stamp>/                     saved and signed versions; read-only (10)
  store.sqlite                           the local database (2.8)
  people.yaml  people.proposed.yaml      the people file, imported once into the local database
  feeds/<slug>/runs/  scans/  bindings/  reports/   kept payloads, replay pages, reviewed sources, report definitions
  logo.svg | logo.png                    optional: replaces the drawn company mark
```

A module folder's letter is read case-insensitively (`p/` loads as `P/`); a writer must write the capital. A folder
under `atoms/` that the catalog does not declare is a load error. A declared concern without a folder is a load error.

### 2.2 The catalog: `holotype.cosm`

One YAML mapping. Its keys:

| Key | Holds | Read by |
|---|---|---|
| `oes` | the declaration: `comprise/1` (2.3) | the loader |
| `comprise` | legacy: `0.1` in every Holotype made before phase 10; read as `oes: comprise/1` | the loader |
| `id` | `holotype/<slug>`; when absent the reader uses `holotype/<folder name>` | everything |
| `name`, `summary` | the subject's name and one line | the pages, the export |
| `sample` | `true` for a sample (fictional, or public sources only); only the literal `true` counts | the pages, the isotype |
| `alignment` | who said whose company this is, and how (a claim, never proof) | standing |
| `atoms` | the concerns: a list of `atom/<slug>` (or `{id: atom/<slug>}`) | the loader |
| `perspective` | the concern you stand in by default, `atom/<slug>` | the renderers, the isotype |
| `sources` | every source an item outside P cites: `{id, page, url, supports, date}` | the checks (`source-undeclared`) |
| `attestations` | the signed versions on record | versions |
| `grants` | scoped, time-limited permissions for an agent to read: `net-scan`, `reflections`, `system-scan`, `directory`, `accounting`, `mcp`, `vendor` | scans, feeds, rule 9 |
| `groups` | named sets of concerns (*atom groups*), usable as a relationship's end | rule 8 |
| `limits` | thresholds for findings, e.g. `roles-per-person` (default 3) | rule 13 |
| `store-key` | where the key that seals the people tables is kept: `{keychain: <service>}`, a name, never the key | the local database |

Unknown keys are kept and ignored. A writer must not invent keys the catalog does not list without a version change.

### 2.3 The declaration: `oes: comprise/1`

A Holotype says which MiniCOSM it is written in with one line in its catalog:

```yaml
oes: comprise/1
```

The value is `<MiniCOSM>/<version>`: the MiniCOSM's name (lowercase), a slash, its major version (an integer).

1. **Read.** A reader must accept `oes: comprise/1`.
2. **Default.** A catalog with no `oes:` key is read as `comprise/1`, silently. This covers every Holotype made so far,
   which says `comprise: 0.1`. The legacy key is read and kept; it is never an error.
3. **Both.** When a catalog has both, `oes:` decides and `comprise:` is ignored.
4. **Write.** A writer creating a Holotype must write `oes: comprise/1` as the first line of the catalog. It must not
   rewrite the line of a Holotype it did not create: no migration.
5. **Refuse.** A catalog declaring a MiniCOSM or a version the reader does not know (`oes: industry/1`,
   `oes: comprise/2`), or an `oes:` with no value, is refused with a plain error naming what it declares and what the
   reader knows. Nothing is loaded from it: the checks report the error and `python -m core lint` exits 1, the app will
   not register it, and a registered Holotype whose catalog is changed to such a line answers 409 until it is changed
   back.

*Status:* built (decision Q54, slice 30c). `core/model.py` reads, defaults and refuses (`declaration`); `core/align.py`
writes the line into every new catalog.

The P files keep their own header, `cosm: 0.3` (chapter P.7). It names the product tree's format, not the MiniCOSM.

### 2.4 Module files

A module file is a `.cosm` file anywhere under `atoms/<concern>/<letter>/`, at any depth (`R/reflections/*.cosm` is
legal). Every such file is one YAML mapping with one of two shapes:

```yaml
nodes:                         # the items, each a mapping with a string id
  - id: C:charter/articles
    type: charter
    …
```

```yaml
module: none                   # this module is empty on purpose
reason: people are not imported in a public sample; the model records seats, not holders
```

- **File names are free.** The convention is one file per family of kinds (`C/entity.cosm`, `C/bonds.cosm`,
  `M/markets.cosm`), and a file may hold items of several kinds: Mozilla Foundation's `C/entity.cosm` holds its
  entity, two charters, a policy, four filings and an event. No id and no path names a file (section 6.4.2).
- **Order.** Files are read in path order, case-insensitively; items keep their file order.
- **Duplicates.** An id already loaded in the same module of the same concern is a load error; the first wins.
- **`module: none`** must carry a `reason`. Without one it is a warning, and the reason reads "no reason given".
- **An empty module** (no folder, or a folder with no items) is legal: every concern has all eight modules.

### 2.5 Reading a file

- UTF-8, with or without a byte-order mark; CRLF and LF read the same.
- YAML 1.2 booleans only: `true` and `false`, in lower, title or upper case. `yes`, `no`, `on` and `off` are strings. (A claim's `on:` field
  depends on it.)
- The COSM subset: no anchors, no aliases, no tags, no multi-document streams. A writer must not produce them.
- A file that does not parse, or whose top level is not a mapping, is a load error; the rest still loads. The reader
  never stops at the first problem: load problems are collected and reported by the checks as errors.

### 2.6 E: people are never in a file

`atoms/<concern>/E/` holds a `README` saying where the people are, or a `none.cosm` with `module: none` and a reason.
The people of a concern live only in the local database (2.8), imported from `people.yaml`. A Holotype's files hold
counts and roles, never names. *Not checked:* the checks do not refuse an item written into an E file today; a writer
must not write one (section 13.3).

### 2.7 Other folders

`vendors/` (3.5) and `snapshots/` (10) are read-only to the app. `feeds/`, `scans/` and `bindings/` hold what sources
brought in and what a person reviewed. `reports/` holds report definitions (`<slug>.report.yaml`). None of them is part
of the model; none is read by the checks except where a section says so.

### 2.8 The local database

`store.sqlite`, one per Holotype. Two kinds of table:

- **Derived** (rebuilt from the files by `python -m core index`): `nodes`, `edges`, `nodes_fts`.
- **Canonical, never in a file:** the people (`people_meta`, `persons`, `assignments`, `memberships`, `credentials`,
  `access`), sealed field by field; `series`; feed runs, synced SKUs, listings, levels and drift; scan runs, the scan log
  and candidates; logins, invites, tokens, keys (public halves only) and the audit; standing statements and evidence;
  isotype settings and releases.

No export of a Holotype includes the canonical tables, and no `.cosm` file ever holds what they hold.

---

## 3. Concerns and relationships

### 3.1 Concerns (*atoms*)

A **concern** is one bounded whole, described on its own. It is usually a company: the branded face of a corporation,
sometimes a sub-brand, sometimes the corporation itself. Its id is `atom/<slug>`; its folder is `atoms/<slug>/`; its
slug is lowercase ASCII letters, digits, dots and hyphens, starting with a letter or digit.

**The test.** A candidate is a concern when it has ownership distinct from the perspective concern's (the concern the
Holotype is written from, below): outside owners, a partner, a franchisee, a licensee, a public float; or when it has
its own legal shell and its own offerings. Otherwise:

| It is only | So it is |
|---|---|
| a legal shell (a payroll vehicle, an IP holding company, a licence holder) | a `C:entity` inside a concern |
| a brand | an `R:brand` scoped to a unit or suite |
| a P&L | a `C:finance` keyed by a unit or a `C:segment` |
| a person | never a concern: the mark in `C:ip`, the seat in O, the public identity in `R:persona` |

**Never nest.** No concern contains another. What looks like nesting is a relationship (`owns`, `member-of`,
`operates`), drawn as a derived tree (3.2). The **perspective** (`holotype.cosm perspective:`) is the concern a reader
stands in by default.

A concern's display name is its anchor entity's name (`C:entity` with `anchor: true`), else its brand's name, else its
id.

### 3.2 Relationships (*bonds*)

A **relationship** is a typed, dated, sourced tie between two concerns, or between a concern and an outside
organization, a group or a vendor-published atom. It is an item of kind `C:bond`. Holding structures, licences, supply,
regulation and franchising are all relationships. The rules named below are the fourteen of section 9.3. From
`fixtures/mozilla`, a sample built from public sources, abridged:

```yaml
- id: C:bond/foundation-controls-org
  type: bond
  name: Foundation controls Mozilla.org
  kinds: [controls]
  from: atom/mozilla-foundation
  to: atom/mozilla-org
  control: full
  accounting: consolidated
  inherits: [principles]
  status: active
  visibility: public
  provenance: {mode: net-scan, sources: ['https://wiki.mozilla.org/Mozilla_org'], confidence: 0.8, state: known}
```

| Field | Holds | Checked |
|---|---|---|
| `kinds` | a non-empty list from the closed list below; a relationship may carry several | error otherwise |
| `from`, `to` | each a concern, a `C:counterparty`, a vendor-published atom or a declared group | rule 8 |
| `economic`, `voting`, `nci` | shares from 0 to 1 | error otherwise; an `owns` without `economic` is a warning |
| `control` | `full` · `joint` · `significant` · `de-facto` · `none`, with `basis:` saying why | error otherwise |
| `accounting` | `consolidated` · `equity` · `fair-value` · `cost` · `none` | error otherwise; rule 11 |
| `scope` | items the relationship applies to | as references |
| `contract` | the `C:contract` behind it | as a reference |
| `inherits` | what flows along it: rules, principles, vocabulary, policies, systems | not checked |
| `template`, `instances` | a class of relationships ("31 franchisees") | rule 14 |
| `terms`, `since`, `until`, `status` | as the envelope | |

**Kinds:** owns · controls · licenses · operates · makes-for · distributes-for · supplies · franchises · funds ·
guarantees · shares-services-with · succeeded · affiliated · competes-with · member-of · hosts · manages · commits ·
pledges · co-invests · sponsors · leases-to · regulated-by · accredited-by · builds-on · bargains-with ·
common-control.

**Mirrored.** A relationship between two concerns of the same Holotype is written in both, with the same id, in each
concern's C module. Rule 8 fails when the copy is missing, and warns when the copies disagree on `kinds`, `from` or
`to`. A relationship to an outside organization lives only in the concern that names it.

**The derived tree.** Concerns never nest, so the tree a group reads as is computed from the `owns` relationships every
time and never stored (`python -m core tree`): roots are concerns nobody owns that own something; a concern owned two
ways appears under each owner with the share on each edge and is counted once; a cycle is cut where it closes and said.
Effective ownership is computed over `owns`, cycle-safe (rule 11).

### 3.3 Outside organizations (*stubs*)

An **outside organization** is one the Holotype names but does not model: a bank, a platform, a supplier, a former
company. It is an item of kind `C:counterparty` in the concern that deals with it, and the index of everything that
names it: relationships, contracts, channels, feeds, vendors, surfaces.

- It should carry a `global-id` where one exists (an LEI, a company-registry number, a domain), so two Holotypes that
  name the same outsider name the same thing.
- A platform's terms go in `platform-terms` (take rate, merchant of record, who owns the customer, payout cadence).
- `atom:` names the concern it is, when it is modelled in this Holotype.
- It can be promoted to a concern without changing any id that points at it.

In the file-system reading it is a mount point: a named place where something outside the volume would attach.

### 3.4 Groups

A **group** (*atom group*) is a named set of concerns ("the group", a reporting segment), declared in the catalog's
`groups:`. A group may be a relationship's end. Its id is free text. *Not built:* groups as perspectives, rollup scopes
and Holotype roots, which `plan/comprise-model.md` describes.

### 3.5 Vendor-published atoms

A vendor may publish one of its concerns at `https://<domain>/.well-known/comprise/<slug>/`: its public files, a
manifest of hashes, an attestation and the public keys (`python -m core publish`). A customer fetches it
(`python -m core fetch`) into `vendors/<domain>/<slug>/`, verified file by file; its id is `vendor/<domain>/<slug>`.

- It is the vendor's, never the customer's: loaded as a separate input, never edited, never linted as the customer's
  (its problems are notes).
- A `C:counterparty` whose global id matches is **upgraded**: the relationships that pointed at the outside organization
  now point at the vendor id, and the stub stays as each relationship's `counterparty`.
- A reference to a vendor id that has not been fetched is a warning (`vendor-missing`), never an error.
- Only the vendor as a whole has an id in the customer's Holotype. Its items have ids only in the vendor's own Holotype
  (section 6.4.5).

---

## 4. The envelope

Every item carries the same envelope: the system columns of every table. Outside P:

| Field | Holds | Checked |
|---|---|---|
| `id` | `<Module>:<kind>/<slug>`, written bare inside its own concern | error unless it parses, names this module, and is not qualified with another concern |
| `type` | the kind; must be one of the module's kinds, and equal the id's kind | error |
| `name`, `summary` | a label and one sentence | error when missing (`identity-min`) |
| `owner` | the responsible role: an `O:role/…`, never a person; may be an open question | error otherwise |
| `since`, `until` | dates; no `until` means active | |
| `status` | `active` · `dormant` · `planned` · `retired` | error otherwise |
| `visibility` | `public` · `internal` · `restricted` | error otherwise (4.2) |
| `provenance` | `{mode, sources, confidence, state}`, plus `synced-from`, `synced-at`, `max-age` for synced items | error when missing or malformed (4.3) |
| `pending` | an open question about the whole item | section 8 |
| `links` | typed links `{rel, to}` or ids | as references |
| `mattering` | why it matters, and to whom (chapter P.3.9) | |
| `body` | Markdown prose | full-text indexed |
| `at` | where it is, as an id; on a filing, an event or a reflection, a date | as a reference unless a date; `site/…` is refused (13.4) |
| `attributed-to` | the concern something belongs to when it sits in another's books | as a reference |
| `template`, `instances` | a shell record that stands for many ("store manager × 31,000") | rule 14 |
| `counterparty` | the `C:counterparty` the item concerns | as a reference; rule 10 |
| `series` | pointers to time series in the local database | |
| `shared-with` | the concern or group a shared item is shared with | as a reference |

The envelope's reference fields are `owner`, `at`, `attributed-to`, `counterparty`, `shared-with` and `links`. Every
other field is the kind's own (section 5). Unknown fields are allowed: the model is young, and a reader must keep what
it does not understand.

### 4.1 P is different

Items in P (chapter P) carry COSM's identity instead: `confidence` and `sources` at the top level rather than a
`provenance` block, `owner` required (P's `identity-min`), `consensus` optional, and `kind` on the brand. Their sources
must be declared in the catalog's `sources:` or a P `doc.cosm` `sources:` (a warning otherwise). P's own checks (P.9)
check the rest of a P item's identity and its visibility. The envelope's `status` list and its reference fields are not
checked on P items; instead every id-like string in a P item that points outside P must resolve (P.5.2).

### 4.2 Visibility

| Value | Who sees it |
|---|---|
| `public` | everyone; the only value any public rendering (the external export, a published atom, the isotype) may show |
| `internal` | every signed-in reader of the Holotype; never a public rendering |
| `restricted` | the operator, the Holotype's admins, and the module editors (*stewards*) of its module in its concern; nobody else (the command line runs without a session and sees everything) |
| absent | outside P, as `internal`; in P, by level (chapter P.3.1) |

A hidden item is absent, not refused: lists leave it out, its page answers as one that does not exist, renderers never
draw it, and a reference to it from a visible item keeps the id but gains no name. An id is an address, not a secret.

A pointer to an `E:person` from outside E is legal only in a `restricted` item (an error otherwise).

### 4.3 Provenance

Sources or it didn't happen.

| Field | Holds | Checked |
|---|---|---|
| `mode` | dialectic · net-scan · system-scan · integration · structured-intake · manual · derived · asserted · archetype · catalogue · directory · accounting | error otherwise |
| `sources` | a non-empty list of source ids declared in the catalog or a P doc | error when empty; warning when undeclared |
| `confidence` | a number from 0 to 1 | error otherwise |
| `state` | `known` (default) · `pending` · `not-disclosed` · `stale` | error otherwise; `stale` makes the module unverifiable (rule 9) |
| `synced-from` | the `I:feed` an `integration` item came from | warning when missing |
| `synced-at`, `max-age` | when it was synced, and how old it may get (`30d`, `12h`, `2w`, `3m`) | rule 9 |

`not-disclosed` is a fact, not a question: the subject declined to say.

---

## 5. The eight modules

Every concern has the eight modules, C · O · M · P · R · I · S · E. Each is a chapter: its kinds, what each holds, and
which of its fields are references (checked as references, section 7) or read by a check (section 9). A module may be
empty, or `module: none` with a reason.

The reference fields below are `core/schema.py`'s, exactly. A dotted field (`rows.sku`) walks into lists and mappings:
the `sku` of every row.

### Chapter C · Corporation

*The legal body: ownership, contracts, filings, money.* The shell, whatever its legal form.

| Kind | Holds | References | Also checked |
|---|---|---|---|
| `entity` | a legal shell. Several per concern; one is the anchor (`anchor: true`), the corporation behind the brand. `form`: corporation · llc · llp · partnership · sole-proprietor · nonprofit · cooperative · trust · foundation · public-body · dao · unincorporated · none. `roles[]`, `jurisdiction`, `global-id`, `domains` | `natural-person` (restricted) | rule 14 |
| `bond` | a relationship (3.2) | `from`, `to`, `contract`, `scope` | kinds, bases; rules 8, 11 |
| `instrument` | a share class, note, option or other instrument and its holders | `holders.holder` | never public |
| `captable` | who holds which instruments | `instruments` | never public |
| `contract` | an agreement; `scope: template` plus instances for a standard form | `between`, `scope`, `guarantors` | |
| `filing` | a return, a registration, an annual report | `entity` | |
| `licence` | a regulator's permission: scope, geography, what it enables, conditions, cycle | `enables`, `regulator` | |
| `certification` | a standard met, and who certified it | `issuer` | |
| `charter` | articles, bylaws, a trust deed, an operating agreement, a constitution | `entity` | |
| `asset` | equipment, property, a lease, cash in trust, securities, a fleet, a collection | `custodian`, `used-by`, `financed-by` | |
| `segment` | a reporting rollup: its members are concerns or P items | `members` | |
| `counterparty` | an outside organization (3.3) | `atom` | rules 8, 10 |
| `policy` | a local source that rules cite (tip pool, refunds, comps) | | |
| `ip` | marks, patents, copyrights, a likeness; `co-owners` | `co-owners` | |
| `governance` | the board and its committees | `elected-by` | |
| `finance` | figures for a period, `by` a concern, unit or segment, on a `basis` | `by` | rule 11; never public |
| `event` | something the concern did; its coverage is an `R:reflection` | | |
| `aim` | what the concern seeks from outside (`stance: seeking`) or is open to (`open`), with a `kind`: customers · partners · suppliers · distribution · technology · talent · capital · other | `prompted-by` | kind and stance required; `horizon` a date, a year or a few words |

### Chapter O · Organizations

*Roles, teams, seats and who decides.* People appear in the files only as roles.

| Kind | Holds | References | Also checked |
|---|---|---|---|
| `role` | a named position with duties, decision rights and an escalation path; `pool: true` when several people share it; `variance` for how it behaves. Its slug is often capitalized (`O:role/Founder`) | `governs`, `escalates-to` | rule 5: governs something, owns something, or is a pool |
| `unit` | a team or division; `twin: P:suite/…` when it is also a line of what is sold; `covered-by` a bargaining contract | `twin`, `covered-by`, `parent` | |
| `position` | a seat people sit in; `reports-to` one position, or `none` for the one at the top; `template` plus `instances` for many | `roles`, `primary`, `reports-to`, `dotted-to`, `unit` | rules 5, 12 (`requires-credential`) |
| `chart` | an organization chart, from its root | `root` | |
| `decision-right` | who may decide what | `holder`, `over` | |
| `decision` | a vote, a resolution, a consent | `by`, `about` | |

### Chapter M · Markets

*Who it serves, through what, at what price.*

| Kind | Holds | References | Also checked |
|---|---|---|---|
| `audience` | a kind of people served, funding or supplying: `relation[]` (customer · supplier · member · investor · voter · donor · student · franchisee · licensee · beneficiary · regulator), `side` (served · funding · supplying), `geography` | `served-by` | isotype markets |
| `market` | a market by taxonomy (NAICS, NACE, ISIC, GICS, UNSPSC, HS, a product taxonomy, custom): `taxonomy`, `code` | | isotype markets |
| `geography` | a region served or worked in | | isotype markets |
| `channel` | how it sells: `counterparty` (required), `model` (sale · revshare · flat-licence · reseller), `seller` (self · counterparty), `tenders[]` | `tenders` | rule 10 |
| `account` | a named revenue-side customer, sponsor or payer; should be restricted | `contract`, `channel`, `pricebook` | |
| `competitor` | a competitor | | |
| `positioning` | how a unit places itself | `unit` | |
| `pricebook` | a list or a rate card: `kind`, `set-by`, `currency`, `rates[]` | `for`, `rates.sku`, `rates.offering` | rule 3: a rate must agree with the offering's price |
| `sizing` | a market size, with its measure and date | `market` | |

### Chapter P · Products: the product tree

*What it offers, and why that matters.* Chapter P is COSM 0.3, the product tree, rewritten in Comprise OES's terms.
Everything normative in COSM 0.3 is kept; what COSM 0.3 described and the code does not do is marked *not built*
(P.11); where its text and the code disagree, the code wins (P.12).

#### P.1 What P describes

P describes what a concern offers as a tree under its **brand**: the whole it sells under one face. Every item in the
tree answers the same nine questions (P.3). The brand does no work of its own; it is the name for the state its parts
settle into when their flows balance and their rules agree. The tree points at roles, never at people.

P describes things that matter to people as the sum of their parts. Three kinds of people are in scope: those who work
on it (*inside*), those who have already chosen it (*chosen*), and those who may one day (*prospective*). People who
will never meet it are out of scope on purpose: a model that claimed to matter to them would be marketing.

#### P.2 Levels (*strata*)

Five levels. An item may directly contain anything strictly below it, so a level may be skipped: a brand may hold a
service directly.

| Level | Kind | What it is | Typically contains | May not hold |
|---|---|---|---|---|
| L4 | `brand` | the whole: legal anchor, brand-wide rules, principles, vocabulary and mattering; does no work | suite, offering; a function that serves every offering | flow, substrate, economics, affect |
| L3 | `suite` | a portfolio of offerings sold or managed together; may nest | suite, offering; a function that serves its offerings | |
| L2 | `offering` | a market-facing promise: audience, contract, price, service level | function, product, service | |
| L1 | `function` | a cluster of units that share infrastructure and a job (make, sell, fulfil, support); may nest | function, product, service | |
| L0 | `product` · `service` | the unit that does the work: a product is an artifact, a service an activity | nothing: what is inside goes in `substrate` | parts |

P has one more kind, `release` (`P:release/<unit>@<version>`: date, channels, build, notes, listings), declared in the
schema. *Code wins:* P's checks do not know the kind, and a `P:release` item fails them as an unknown kind (P.12).

**Invariants**, checked except where marked:

1. A direct part sits at a strictly lower level, except that a suite may contain a suite and a function a function
   (`strata`).
2. Containment is acyclic (`acyclic`).
3. Every item reaches the brand through `parts` (`orphan`).
4. The brand holds no flow, substrate, economics or affect (`brand-holds-nothing`). It should hold at least one part
   (*not checked*).
5. Products and services hold no parts (`strata`).
6. The level is declared by the kind, never inferred from depth.
7. An item has exactly one parent (`single-parent`). Shared use is `feeds` or `depends-on`, never a second parent.

The lower the level, the more description an item carries; the higher, the more it relates and the less it says.

#### P.3 The nine questions (*aspects*)

Every item answers nine questions. A field left out means *not yet asked*, never *none*: write `none` when that is the
fact. A `band` is an ordinal the concern defines (`small | medium | large`), used wherever an exact number would go
stale or leak.

1. **identity**: what is it?
2. **flow**: what does it take in and put out?
3. **substrate**: what does it run on?
4. **rules**: what must it, may it, must it not?
5. **principles**: what is it for, and what does it trade off?
6. **economics**: what does it cost and earn?
7. **vocabulary**: what do its words mean here?
8. **affect**: how is it meant to feel?
9. **mattering**: to whom does it matter, and why?

##### P.3.1 identity

| Field | Holds |
|---|---|
| `id` | `P:<kind>/<slug>`; the brand's is `P:<slug>`, with no kind. Never renamed; `name` is for display |
| `name`, `summary` | a label; one sentence |
| `type` | `brand` · `suite` · `offering` · `function` · `product` · `service` (and `release`, see P.2) |
| `owner` | the accountable role, `O:role/…`; required |
| `since`, `until` | lifecycle bounds; no `until` means active |
| `status` | the envelope's; the isotype offers only items with no status or `active` |
| `version` | of this description, not of the thing; optional, unused by the code |
| `confidence`, `consensus` | 0 to 1: how sure the elicitation was; how much the sources agreed |
| `sources` | the sources it came from (4.1) |
| `visibility` | `public` · `internal` · `restricted`. When absent: `public` for the brand, suites and offerings; `internal` for functions; for a product or service, `public` only when one of its flows touches a market or a channel (P.5.2) |
| `kind` | the brand only: `company` · `nonprofit` · `public-body` · `project` · `community` · `product-line` · `other` |

##### P.3.2 flow

| Field | Holds |
|---|---|
| `inputs[]` | `{resource, from, unit, rate?}`; `from` is an item or an external (P.5.2) |
| `outputs[]` | `{resource, to, unit, rate?}` |
| `capacity` | `{nominal, peak, unit}` |
| `latency` | `{target, p99, unit}` |
| `errors` | `{rate, modes[]}` |
| `degradation` | past capacity: `queue` · `shed` · `degrade` · `fail` |
| `schedule` | `continuous` · `batch` · `on-demand` |

##### P.3.3 substrate

| Field | Holds |
|---|---|
| `assets[]`, `platforms[]`, `tools[]` | what it runs on |
| `vendors[]` | third parties it cannot run without |
| `roles-required[]` | `{role, load: band}` |
| `budget` | a band |
| `depends-on[]` | what it needs to exist, which it neither contains nor consumes |

##### P.3.4 rules

A rule is written as `"<actor> <aim> <object>"` under `must`, `may` or `must-not`. The actor is a role (`O:role/…`),
the reserved actor `all-roles`, or an external.

| Field | Holds |
|---|---|
| `must` · `may` · `must-not` | the rule |
| `when` | the condition; optional |
| `else` | the sanction or fallback; optional for `may` |
| `counts-as` | a constitutive rule: `"<entity> counts as <function> when <properties>"` |
| `source` | a statute, a policy, a contract, or `local` |
| `scope` | `self` (default) · `descendants` |

##### P.3.5 principles

| Field | Holds |
|---|---|
| `purpose` | one sentence |
| `value[]` | `{to, proposition}`: what it offers, and to which item or audience |
| `priorities[]` | ordered trade-offs: `"accuracy over speed"` |
| `quality[]` | `{goal, measure}` |
| `decides[]` | what it settles without escalation |

##### P.3.6 economics

| Field | Holds |
|---|---|
| `price` | `{model, value?, unit?}`; model `free` · `flat` · `usage` · `seat` · `tiered` · `internal`; or `none` |
| `cost` | `{model, band}` |
| `margin` | a band |
| `settles-with[]` | `{node, basis}`: an internal chargeback or revenue share |

Every offering has a price, `none`, or an open question (rule 3).

##### P.3.7 vocabulary

| Field | Holds |
|---|---|
| `terms[]` | `{term, means, maps-to?, overrides?}`; `overrides: true` declares a deliberate divergence from an inherited word |
| `assumes[]` | what it takes for granted |
| `trusts[]` | `{node, for}`: what it assumes an upstream item has done |
| `boundary[]` | what it declines to know about |

##### P.3.8 affect

Offerings must declare affect; other items may.

| Field | Holds |
|---|---|
| `audience` | who feels it: an item, an external or an audience |
| `elicits[]` | `{feeling, intensity 0–1, when?}` |
| `avoids[]` | feelings to prevent |
| `probes[]` | hooks a simulation can call; default `satisfaction` · `motivation` · `anticipation` · `reward` |
| `tone[]` | register words |

##### P.3.9 mattering

The aspect the rest exist for. Affect says how an item is meant to feel; mattering says why it counts: what would be
lost, and by whom, if it stopped tomorrow.

| Field | Holds |
|---|---|
| `to-the-whole` | one sentence: what the whole loses without it. Required on every item but the brand |
| `weight` | `critical` · `major` · `supporting` · `peripheral` |
| `inside[]` | `{who, because, stakes?}`: the people who work on it; `who` lists roles |
| `chosen[]` | `{who, because, stakes?}`: people who have already chosen it; required on offerings and the brand |
| `prospective[]` | `{who, because, barrier?}`: people who may; required on offerings and the brand |

Each entry may carry its own `confidence` and `sources`, and any entry or field may be an open question. Two people who
choose the same thing for different reasons are two entries. Mattering does not inherit and does not sum. The question
that draws it out is always the same: *if this stopped tomorrow, who would notice first, and what would they lose?*

#### P.4 Roles, not people

People never appear in P. Names, emails, pronouns and personality words must not be written; the checks flag personal
pronouns and pairs of capitalized words that look like a name (P.9). People appear only as roles, `O:role/<Slug>`, which live in O (chapter O): a name, duties, decision rights, an escalation path,
the items it governs, and `variance` for behaviour that matters to the business.

When a person's behaviour matters, it is recorded in one of three systemic forms: `variance` on the role (execution,
cadence drift), a rule's threshold and a flow's latency, or divergent vocabulary between items that feed each other.

#### P.5 Relations and inheritance

##### P.5.1 Relations

Six relations. None is a separate edge object: each lives in the aspect it belongs to, so an item is self-contained and
the graph is derived.

| Relation | From → to | Written in |
|---|---|---|
| part-of | item → item, strictly downward | `parts:` on the parent |
| feeds | item → item or external | `flow.outputs[].to` and `flow.inputs[].from` |
| depends-on | item → item or external | `substrate.depends-on` |
| governed-by | item → role | `owner:`, and `governs:` on the role in O |
| bound-by | item ↔ item or external | a `C:contract` in chapter C |
| maps | term → term | `vocabulary.terms[].maps-to` |

`feeds` is declared at both ends: the provider says where its output goes, the consumer where its input comes from.
An edge only one end declares is a warning (`flow-mirror`), except where either end is a brand, suite, offering or
function, whose flows are derived from their parts.

##### P.5.2 Externals

In a Holotype, P declares no externals of its own. **Every reference out of P is an external**, and its kind is
derived from what it names:

| A reference to | Is an external of kind |
|---|---|
| `M:audience/…`, `M:account/…`, `M:market/…` | market |
| `M:channel/…` | channel |
| `S:vendor/…` | vendor |
| `S:system/…`, `S:platform/…` | platform |
| `C:counterparty/…`, a concern, an id in another concern | partner |

A reference out of P that resolves to nothing is an error (`ref-unresolved`).

##### P.5.3 Inheritance

Three aspects flow down the tree; six do not.

| Aspect | Inherits |
|---|---|
| rules | yes, when `scope: descendants` |
| principles (`priorities`) | yes |
| vocabulary | yes |
| identity, flow, substrate, economics, affect, mattering | no |

A child may redefine an inherited word, but must say so with `overrides: true` (or map it with `maps-to`); silent
redefinition of a brand word is an error (`override-explicit`). A child may add rules and may narrow a `may`; it must not
weaken an inherited `must` or `must-not` (*not checked*, P.12). The effective item, with every inherited line marked with
the ancestor it came from, is what an item's card shows.

#### P.6 The sketch (shorthand)

For whiteboards, interviews and chat. One item per line; indentation is containment; the first line is the brand.
Expanding a sketch writes the canonical YAML with an open question on every aspect the sketch did not fill (`python -m
core align sketch`, which runs cosm.py's `expand` and adds the Comprise namespaces).

| Mark | Means | Lands in |
|---|---|---|
| `suite/` `offering/` `function/` `product/` `service/` | the kind | identity |
| indentation | part-of | `parts` |
| `> target` | feeds | `flow.outputs`, and the target's inputs |
| `~ target` | depends-on | `substrate` |
| `@Role` | owner | identity |
| `$49/mo` `$4/seat` | price | economics |
| `:) feeling` | elicits | affect |
| `! "must …"` | a rule | rules |

```text
meadow @Founder ! "must-not store card numbers"
  suite/books
    offering/ledger @Founder $49/mo :) relief, trust
      function/ingest ~ext/banks
        service/bank-sync > service/reconcile
        product/csv-importer > service/reconcile
      service/reconcile > offering/ledger
  offering/payroll @Payroll-Owner $4/seat :) fairness
    service/tip-out > offering/payroll
offering/ledger > offering/payroll, service/tip-out
```

A cross-tree edge is written at column zero. Nothing the sketch does not say is guessed.

#### P.7 The files of P

```
atoms/<concern>/P/
  brand.cosm      cosm: 0.3, then brand: (the L4 item, id P:<slug>)
  nodes.cosm      nodes: (every other item of the tree)
  doc.cosm        reading:, history:, findings:, sources: (the document, not the model)
```

- `cosm: 0.3` heads each file. A file without it loads; `opi:` (the oldest key) is read the same way.
- `brand:` holds the root item. A COSM 0.2 `firm:` block is read as `brand:`; a writer must write `brand:`.
- `reading` (how to read the draft: date, author, mode, perspective, note), `history` (dated events that explain the
  shape), `findings` (what the structure already shows: check, nodes, finding, proposal) and `sources` (the P items'
  sources) carry the document. The export renders them; nothing is assembled by hand.
- `roles:`, `externals:` and `contracts:` inside P are legacy: still read, never written. Roles live in O, contracts in C,
  externals are derived (P.5.2).
- Ids in P files are namespaced (`P:offering/ledger`, `O:role/Founder`); the tooling strips and restores the namespace
  when it hands the tree to cosm.py.
- `type: firm` loads as `brand`, and `type: stack` as `function`, with a note. A writer must write the current kinds.
- P may be `module: none` with a reason. A concern whose P has neither a brand nor `module: none` is an error.

#### P.8 Drawings

Every drawing is a view over the same items, never drawn by hand. The text is canonical; the drawing is derived.

| Level | Mermaid shape | Reads as |
|---|---|---|
| brand | `id((Name))` | the whole |
| suite | `id{{Name}}` | a portfolio |
| offering | `id([Name])` | a promise |
| function | `id[[Name]]` | a cluster |
| product | `id[Name]` | an artifact |
| service | `id(Name)` | an activity |
| role | `id>Name]` | a position |
| external | `id[/Name/]` | a market, channel, vendor or partner |

| Relation | Mermaid |
|---|---|
| part-of | nesting, or `---` in flat views |
| feeds | `==>`, labelled with the resource |
| depends-on | `-.->` |
| governed-by | `--o`, from the role to the item |
| bound-by | `<-->`, labelled with the contract |
| maps | `-. maps .-` |

Built views (cosm.py `render`): `map` (the tree with feeds over it), `tree`, `flow`, `affect`, `mattering`. *Not built:*
`substrate` and `rules`. The app draws P in its own renderers (section 12); the card (`card`) and the text tree
(`ascii`) are cosm.py's.

#### P.9 P's checks

Two levels. The per-item checks run on every write; the seven conditions judge the whole tree, and rule 1 (section 9)
reports them. Severities: an error blocks, a warning is recorded, a note is advice.

| Check | Severity | Fails when |
|---|---|---|
| `type` | error | the kind is not one of P's levels |
| `type-prefix` | error | the id's kind disagrees with `type` (the brand's id has no kind) |
| `legacy` | note | `firm` or `stack` was read as `brand` or `function` |
| `identity-min` | error | id, name, type, summary or owner is missing |
| `visibility` | error | not `public`, `internal` or `restricted` |
| `strata` | error | a part is undeclared or not strictly below (suite in suite and function in function allowed); a unit holds parts |
| `role-exists` | error | the owner is not a declared role |
| `brand-holds-nothing` | error | the brand has flow, substrate, economics or affect |
| `flow-ends` | error | an input has no `from` or an output no `to` |
| `external-exists` | error | a `from`, `to` or `depends-on` names nothing |
| `units` | warning | a rate without a unit |
| `rule-syntax` | warning / error | the actor is not a role, `all-roles` or an external (warning); a rule has no aim (error) |
| `override-explicit` | error | a brand word is redefined without `overrides: true` or `maps-to` |
| `affect-on-offerings` | warning | an offering declares no affect |
| `mattering` | error | mattering is not a mapping |
| `mattering-declared` | warning | no mattering, or no `to-the-whole` (brand exempt) |
| `mattering-weight` | error | `weight` is not one of the four |
| `mattering-refs` | error | a `who` names no declared role, external or item |
| `mattering-because` | warning | an entry has `who` but no `because` |
| `mattering-on-offerings` | warning | an offering or the brand lacks inside, chosen or prospective |
| `mattering-inside` | note | an owned item has no `inside` entry |
| `confidence` | note | `confidence` or `sources` missing |
| `no-humans` | warning | a personal pronoun in identity, rules or principles; a singular one in mattering |
| `no-humans?` | note | two capitalized words that could be a person's name |
| `orphan`, `single-parent`, `acyclic` | error | containment is broken (P.2) |
| `flow-mirror` | warning | a feeds edge only one end declares (P.5.1) |

**The seven conditions** (*equilibrium*). The tree is in equilibrium only when all seven are `ok`:

1. **flow-balance.** Every internal input with a rate is supplied, within 10%, by its providers' rated outputs for the
   same resource. No internal flows: `ok`. Any internal edge whose rate is missing or open: *unverifiable*.
2. **rule-consistency.** No `must` and `must-not` share an aim.
3. **closure.** No `orphan`, `external-exists`, `role-exists`, `brand-holds-nothing` or `mattering-refs` error.
4. **vocabulary-closure.** Two items joined by a feeds edge never define the same word differently.
5. **role-coverage.** Every role of the concern owns an item of the tree, has a `governs` list, or is a pool.
6. **affect-declared.** Every offering has an affect audience and at least one feeling.
7. **mattering-declared.** The brand and every offering name all three constituencies; every other item says what the
   whole loses without it. An open question makes it *unverifiable*, not a violation.

Equilibrium is a property of a description, not a promise about the business. A concern can be in equilibrium and
losing money. It means the description is closed: nothing dangles, nothing contradicts, nothing points outside without
saying so.

#### P.10 How P renders for an audience

The **internal** rendering holds everything. The **external** rendering keeps the shape of the whole (the brand, the
suites, the offerings, the public units, the words, the externals, mattering to the chosen and the prospective) and
drops substrate, costs, margins, settlements, role details, open questions, findings, checks and every item that is not
public by P.3.1. The top of the tree looks the same to a customer as to an employee; only the depth differs. The pack,
a published atom and the isotype's offers all use this rule.

#### P.11 What COSM 0.3 described that Comprise OES 1 does not build

Kept as the map of where P can go. None of it is in the code today.

| COSM 0.3 | State in Comprise OES 1 |
|---|---|
| simulation: units as queues, aggregates by min-cut, role variance as jitter, rule gates, affect probes, scenarios | *not built* |
| `whatif`, `harmonize` (nine checks), `propose`, `rank`, `uat`, `qa`, `hooks` | *not built*; the findings in `doc.cosm` use harmonize's words |
| `depersonalize` (proposing role substitutions) | *not built*; the `no-humans` checks find, a person fixes |
| `export` to JSON-LD, Turtle, OWL, SHACL, ArchiMate, CSV; `import` | *not built* |
| `save`, `put`, `remove`, `where`, `upstream`, `downstream`, `glossary`, `capacity`, `cost` as an API | *not built* as an API; the app's editor writes through the checks |
| `sketch` (the tree back as shorthand) | *not built*; `expand` is |
| the Remote Assistance Protocol (grants, propose mode, the remote queue) | replaced by Comprise's own: grants in the catalog, proposals a person accepts, the audit (section 10) |
| the State Library, `history`, `diff`, `at`, `attest` | replaced by saved and signed versions (section 10) |
| mattering shares, an affect scale, firms within firms, product internals | open questions of COSM 0.3; firms within firms are now concerns and relationships (section 3) |

#### P.12 Where COSM 0.3's text and the code disagree

The code wins in every row.

| COSM 0.3's text says | The code does |
|---|---|
| its header: v0.2 | the tree is 0.3 (Q29: the brand, `restricted`); P files say `cosm: 0.3`, and so does cosm.py's `VERSION` (`0.3`, the line `expand` writes) |
| `rule-syntax` is an error when the actor is not a role | a warning; an external may also be an actor; only a rule with no aim is an error |
| `no-humans` is an error | a warning (pronouns) and a note (a name-like pair); outside P, a pronoun in name or summary is a warning and a pointer to `E:person` from an unrestricted item an error |
| `term-resolves` (warning) and `no-weakening` (error) | not checked |
| `role-exists` covers rule actors | covers the owner only |
| rule-consistency: a `must` and a `must-not` whose `when` can both hold | a `must` and a `must-not` with the same text |
| flow balance within a tolerance the brand sets, default 10% | always 10% |
| the API table counts six equilibrium conditions | there are seven, in text and code |
| `snapshot` is refused unless equilibrium holds | a saved version is always taken and records the verdict; signing is refused unless the checks allow it (section 10) |
| one node per file, or many under `nodes:` | the convention is `brand.cosm`, `nodes.cosm`, `doc.cosm`; any `*.cosm` under P is read |
| the `substrate` and `rules` views | not built |
| `P:release` is a P kind (`plan/comprise-model.md`) | in the schema, but P's checks reject it as an unknown kind |

### Chapter R · Representations and reflections

*What it says, and what others say back.*

| Kind | Holds | References | Also checked |
|---|---|---|---|
| `surface` | where it speaks: a website, a store page, a listing, a profile; `kind`, `url` | `presents`, `hosted-on` | rule 10 for platform surfaces; the isotype's domains come from public `kind: website` surfaces with no counterparty |
| `brand` | a further brand, scoped to a unit or suite (the concern's own brand is P's brand item) | `scope` | |
| `persona` | a sanctioned public identity; its link to a person is restricted | | |
| `claim` | something it says: `text`, `about`, `on`, `evidence` (`state`: whole · partial · contested · unsupported) | `about`, `on`, `evidence.by` | rule 7 |
| `rendering` | a document made for an audience from a perspective | `audience`, `perspective` | |
| `reflection` | what others say: a review, a rating, coverage, a regulator's finding | `about`, `surface` | rule 9 via a reflections grant |

### Chapter I · Inventories

*What exists, is stocked or is listed.*

| Kind | Holds | References | Also checked |
|---|---|---|---|
| `feed` | a live source (a shop platform, a CSV, rows typed by hand, an MCP source): `adapter`, `schedule`, `max-age`, `counterparty` | `system`, `mapping` | rules 9, 10 |
| `sku` | a stock item: `kind` (finished-good · raw-material · digital · subscription-plan · service-sku · bundle · …), `unit`, `billing`, `entitles` | `entitles`, `requires`, `parent`, `priced-by` | rule 2 |
| `mapping` | rows from SKUs to P units (`maps-to` or `entitles`), and exclusions with reasons | `feed`, `rows.sku`, `rows.maps-to`, `rows.entitles`, `exclusions.sku` | rule 2 |
| `location` | a place stock sits: `site`, `kind`, `stock-owner` | `stock-owner` | |
| `series` | a measure over time on an item (on-hand, available, balance, …); its points may live in the local database | `of` | |
| `listing` | an item listed on a channel, at a release | `sku`, `channel`, `version` | |
| `position` | a fund's holding | `bond`, `instrument` | |
| `capacity` | beds, seats, hours, servers, with occupancy | `of` | |
| `usage-stat`, `order-stat` | series that feed P's rates | `of` | |

SKUs a feed brings in live in the local database, not the files; a mapping row may name one (section 7.4).

### Chapter S · Stacks

*The systems and vendors it runs on.*

| Kind | Holds | References | Also checked |
|---|---|---|---|
| `system` | a system it runs: `category`, `regulatory-criticality` | `vendor`, `admin`, `used-by` | rule 4: an owner and a referrer, or it is orphan spend |
| `platform` | one declared platform from the shipped catalogue of platform shapes | | rule 10 |
| `vendor` | a supplier of systems or services | `contract` | rule 10 |
| `integration` | data moving between two systems | `from`, `to` | |
| `datastore` | where a system keeps data | `system` | |
| `account` | an account on a system, and who holds it | `system`, `holder` | |
| `codebase` | source code, and what it runs | `runs` | |

### Chapter E · Employees

*The people: counted here, never named.* Every person with a position, a membership or a credential. E is the only
module with personal data, and it is never in a file (2.6). Its kinds are tables in the local database:

| Kind | Where | References |
|---|---|---|
| `person` | `persons`, the name and data sealed | |
| `assignment` | `assignments`: a person in a position, with a share, dates and the employer | `position`, `employer` |
| `membership` | `memberships`: a person in an audience (member-owner, partner, player) | `audience` |
| `credential` | `credentials`: a licence or certification a person holds; issuer, scope and data sealed | |
| `access` | `access` | |
| `intake`, `continuity` | a person's profile, inside `persons.data` | |
| `broadcast` | declared; *not built* | |

Pages show E as counts. Rules 6, 12 and 13 read it from the local database; without it they are unverifiable, unless
E is `module: none` (or the database says `people: none`) with a reason.

---

## 6. Paths

Every concern, module, kind, item and field has a **path**: its id respelled as a location.

```
mozilla-foundation/P/offering/creative-futures      ⇄   atom/mozilla-foundation//P:offering/creative-futures
```

A path is `<concern>/<module>/<kind>/<slug>`, with `#<field>` for a field. The shorter prefixes name the folder
levels. Paths are accepted beside ids, never instead of them.

### 6.1 Properties

- **A respelling.** A path is computed from an id, and an id from a path, with no lookup. Every item of the six fixtures
  (1,227 items) has a path, and every path turns back into its id.
- **Slug-based.** It is built from slugs, which never change when an item is renamed.
- **Absolute.** It always starts with the concern. There are no relative paths: a bare id inside a concern becomes a
  path by adding that concern.
- **ASCII, and one spelling.** No colon, so it is safe as a file name on Windows; no percent-encoding, no `..`, no
  leading or trailing slash. A path has exactly one spelling, and a reader refuses any other rather than guessing.
- **An address, never a door.** A path never touches the disk by itself. It names a row; it is never joined to a folder
  to open a file.

### 6.2 Grammar

```
path         = concern-path / vendor-path
concern-path = concern [ "/" module [ "/" kind [ "/" slug [ "#" field ] ] ] ]
vendor-path  = "vendor/" domain "/" concern                    ; a vendor-published atom, as a whole
concern      = alnum *( lower / DIGIT / "." / "-" )            ; ATOM_RE's slug: [a-z0-9][a-z0-9.-]*
domain       = concern                                          ; the vendor's domain, lowercase
module       = "C" / "O" / "M" / "P" / "R" / "I" / "S" / "E"
kind         = lower *( lower / DIGIT / "-" )                   ; a kind the module declares, or "brand" in P
slug         = alnumx [ *( alnumx / "." ) alnumx ]              ; [A-Za-z0-9]([A-Za-z0-9._@-]*[A-Za-z0-9_@-])?
alnumx       = ALPHA / DIGIT / "_" / "@" / "-"
field        = key *( "." key / "[" 1*DIGIT "]" )
key          = ( ALPHA / DIGIT ) *( ALPHA / DIGIT / "_" / "-" )
```

A kind segment must be a kind of that module in the manifest; `brand` is accepted in P (6.4.1). A field may follow
only an item. Segments are case-sensitive: module letters are capitals, kinds and concerns lowercase, slugs as written.

### 6.3 From an id to a path, and back

| The id | The path | Names |
|---|---|---|
| `atom/<concern>` | `<concern>` | a concern (its folder) |
| (a concern, a letter) | `<concern>/<M>` | a module (its folder; a group of tables) |
| (a concern, a letter, a kind) | `<concern>/<M>/<kind>` | a kind (a table) |
| `<M>:<kind>/<slug>` inside `<concern>` | `<concern>/<M>/<kind>/<slug>` | an item (a row) |
| `atom/<concern>//<M>:<kind>/<slug>` | `<concern>/<M>/<kind>/<slug>` | the same item, from anywhere |
| `P:<slug>` inside `<concern>` | `<concern>/P/brand/<slug>` | P's brand item |
| an item and a field path | `<item path>#<field>` | a field (a cell) |
| `vendor/<domain>/<slug>` | `vendor/<domain>/<slug>` | a vendor-published atom |

The module and kind levels have no id today; the path is their only name. The reverse is the same table read right to
left. The concern of a bare id is the concern whose files hold it.

### 6.4 Edge cases, settled

#### 6.4.1 P's brand item

The brand's id has no kind: `P:<slug>`. Its path puts the kind in: `<concern>/P/brand/<slug>`.

```
mozilla-foundation/P/brand/mozilla-foundation    ⇄   P:mozilla-foundation   (in atom/mozilla-foundation)
mzla/P/brand/thunderbird                         ⇄   P:thunderbird          (in atom/mzla)
```

This is one-to-one because `P:brand/<slug>` is never a valid id: the checks require the brand's id to have no kind and
every other P item's kind to match its type. `<concern>/P/brand` is the brand's table, with one row. The brand's slug
need not equal the concern's (`mzla`'s brand is `thunderbird`). `<concern>/P/<slug>` is not a path: the third segment
is always a kind. `R:brand/…` is an ordinary R item (`mozilla-foundation/R/brand/mozilla-foundation`).

#### 6.4.2 Kinds that share a file

The kind level is a table, not a file. `mozilla-foundation/C/charter/articles` names the charter wherever it is
written; it happens to be in `C/entity.cosm`, beside the entity, a policy, filings and an event. Moving an item to
another file changes neither its id nor its path. The file is metadata, shown in Details and in messages.

#### 6.4.3 Relationships

A relationship between two concerns is written in both (3.2), with one id. Each copy has a path in its own concern, and
both name the same relationship:

```
mozilla-foundation/C/bond/foundation-controls-org    the copy in the from concern (cite this one)
mozilla-org/C/bond/foundation-controls-org           the mirror in the to concern
```

Cite the copy in the `from` concern. A relationship to an outside organization has one copy, in the concern that names
it.

#### 6.4.4 Outside organizations

An outside organization is an ordinary item of C: `mozilla-corporation/C/counterparty/google`. Its global id is a
field (`#global-id`), not a path: a path addresses the volume, never the world.

#### 6.4.5 Vendor-published atoms

A vendor-published atom's path is its id, `vendor/<domain>/<slug>`, and nothing below it. Its items have no address in
the customer's Holotype in Comprise OES 1: they belong to the vendor's own Holotype, where they are an ordinary concern,
and the qualified form (6.4.7) addresses them there. `vendor/<domain>/<slug>` never collides with a concern named
`vendor`, because a concern path's second segment is a module letter, a capital, and a domain never is. No fixture holds
a vendor-published atom, so this section uses placeholders.

#### 6.4.6 Fields

`#` and a field path name a field of an item. The field path is the one the checks already write for open questions:
keys joined by `.`, list positions as `[n]`, counted from zero.

```
mozilla-foundation/C/contract/artists-make-technology#terms
mozilla-foundation/P/offering/mozilla-festival#economics.price
meadow/P/offering/ledger#flow.outputs[0].to
mozilla-foundation/C/bond/foundation-licenses-corporation#scope[0]
```

A field path names a value that is there; a path to a missing field names nothing. An open question on a whole item
(a `pending:` key on the item) is addressed by the item's path with no field. A key outside the `key` rule (one with a
slash or a space) has no field path. In a URL, `#` is the fragment: the browser keeps it across the redirect, so
`/h/{key}/at/<path>#<field>` opens the item's page. *Not built:* the page does not yet scroll to or select the field;
the command line and MCP address fields (6.5).

#### 6.4.7 The qualified form

For use outside one install, a path is qualified with the MiniCOSM and the Holotype:

```
oes:comprise/<holotype>/<path>
oes:comprise/mozilla/mozilla-foundation/P/offering/creative-futures
oes:comprise/meadow/meadow/P/brand/meadow
oes:comprise/mozilla                                    the Holotype itself
```

`<holotype>` is the Holotype's id without `holotype/` (`holotype/mozilla` → `mozilla`). The form carries no version:
a path keeps its meaning across versions of a MiniCOSM, and a change that would alter a path's meaning must be a new
MiniCOSM. A Holotype's id is unique within one install's registry, not in the world. *Not built:* a globally unique
Holotype name (Connect's Holotype id, or an isotype's handle on the Index) and a resolver for qualified paths across
installs. A qualified path names a private address; it opens nothing to a reader who may not see it.

#### 6.4.8 Case, characters and what has no path

- Ids and paths are case-sensitive and keep their case: `meadow/O/role/Founder`. Two ids that differ only in case are
  two items, and a case-insensitive file system (Windows, macOS by default) would merge them if a writer ever used paths
  as file names. Comprise OES 1 never does; a tool that does must refuse such a pair. *Not checked:* the checks do not yet
  warn about ids that differ only in case.
- A slug uses ASCII letters, digits, `.`, `_`, `@` and `-`, and never ends in `.` (Windows drops a trailing dot). This is
  the set the tooling already reads in bare P ids, and it holds `P:release/<unit>@<version>`. No segment is a Windows
  reserved name, alone or before a dot (6.6).
- An id whose slug falls outside that set (one with a slash, a colon, a `#`, a space or a non-ASCII letter) parses as an
  id but has **no path** in Comprise OES 1. The CLI says so. *Not checked:* the checks do not yet warn about such ids;
  none exists in any fixture.
- The catalog's own entries (sources, grants, groups, attestations) have no path in Comprise OES 1.

### 6.5 Where paths are accepted

Beside ids, never instead of them:

| Where | What it does |
|---|---|
| the CLI | `python -m core path <holotype> <id-or-path>` prints the path, the id, what it names, its name, its file and its qualified form; it also takes a qualified path or an id with `#<field>`, and `--atom atom/<slug>` says which concern a bare id is read in. It exits 1 when nothing is there |
| MCP | `node` takes an id or a path (either may end in `#<field>`) and returns `path`; `context`, `pending` and `lint` take a concern's path `<slug>` as their `atom`; `search` hits carry `path`; `pending` keeps `path` (the field path, as before) and adds `item_path` (`<item path>#<field>`) |
| the export | each item's heading carries its path after its id, and each open question its address `<item path>#<field>` |
| the app | `/h/{key}/at/<path>` redirects: a concern to the Overview rooted at it, a module to its chapter, a kind to the Overview rooted at that table (a kind of P, or a kind with nothing visible in it, to the module's chapter), an item to its page, a vendor-published atom to its page. The item page shows its path in Details, with Copy |

The app's own links stay id-based (`/h/{key}/node/<concern>/<id>`); `/at/` is how a path opens. A browser never sends
`#<field>` to the server, so `/at/` opens items and folders, and the CLI and MCP address fields. `/at/` takes the path
only, never the qualified form: it already knows the Holotype.

*Status:* built (slice 30c): `core/paths.py`, the `path` command in `core/cli.py`, `core/mcpserver.py`, `core/pack.py`,
and the `/at/` route and the item page's Details in `app/`.

### 6.6 Scope and safety

- A path to something the reader may not see answers exactly as its id would: the same 404, no name, no link. A path is
  never a way around visibility.
- Refused, never normalized: `..` and `.`; an empty segment; a leading slash (an absolute path) or a trailing one;
  percent-encoding, an encoded slash included (the app checks the path exactly as it was sent); a backslash; whitespace,
  control characters and anything outside ASCII; a colon; a segment ending in a dot; a segment that is a Windows reserved
  name (`con`, `prn`, `aux`, `nul`, `com0` to `com9`, `lpt0` to `lpt9`, in any case, wherever it stands), alone or before
  a dot (`con.txt`, `NUL.tar.gz`: Windows reserves those too); a second `#`; a kind its module does not declare; more
  than four segments.
- A path is resolved against the loaded Holotype, never against the disk.

### 6.7 Examples

Every example in this document resolves on the fixtures; the read-only script that checks them prints each with its id.

| Path | Id | Names |
|---|---|---|
| `mozilla-foundation` | `atom/mozilla-foundation` | a concern |
| `mozilla-foundation/P` | (atom/mozilla-foundation, P) | its Products module, 33 items |
| `mozilla-foundation/P/offering` | (atom/mozilla-foundation, P, offering) | its offerings, 8 items |
| `mozilla-foundation/P/offering/creative-futures` | `P:offering/creative-futures` | an offering |
| `mozilla-foundation/P/brand/mozilla-foundation` | `P:mozilla-foundation` | the brand item |
| `mzla/P/brand/thunderbird` | `P:thunderbird` | a brand whose slug is not the concern's |
| `mozilla-foundation/R/brand/mozilla-foundation` | `R:brand/mozilla-foundation` | an R brand |
| `mozilla-foundation/C/charter/articles` | `C:charter/articles` | a charter, in `C/entity.cosm` |
| `mozilla-foundation/M/geography/operations` | `M:geography/operations` | a geography, in `M/markets.cosm` |
| `mozilla-corporation/S/codebase/firefox` | `S:codebase/firefox` | a codebase, in `S/systems.cosm` |
| `mozilla-foundation/C/bond/foundation-controls-org` | `C:bond/foundation-controls-org` | a relationship, from end |
| `mozilla-org/C/bond/foundation-controls-org` | `atom/mozilla-org//C:bond/foundation-controls-org` | its mirror |
| `mozilla-corporation/C/counterparty/google` | `C:counterparty/google` | an outside organization |
| `mozilla-org/C/ip/mozilla-trademarks` | `atom/mozilla-org//C:ip/mozilla-trademarks` | a mark, as another concern cites it |
| `mozilla-foundation/O/role/Executive-Director` | `O:role/Executive-Director` | a role (case kept) |
| `mozilla-foundation/P/offering/mozilla-festival#economics.price` | (`P:offering/mozilla-festival`, `economics.price`) | an open question's field |
| `mozilla-ai/E` | (atom/mozilla-ai, E) | a module that is `none`, with its reason |
| `meadow/P/brand/meadow` | `P:meadow` | Meadow's brand |
| `meadow/P/offering/ledger#flow.outputs[0].to` | (`P:offering/ledger`, `flow.outputs[0].to`) | a field inside a list |
| `meadow/O/role/Founder` | `O:role/Founder` | a role |
| `meadow/C/counterparty/banks` | `C:counterparty/banks` | an outside organization |
| `meadow/I/sku/ledger-monthly` | `I:sku/ledger-monthly` | a stock item |
| `meadow/E` | (atom/meadow, E) | a module holding only a README |

---

## 7. References

A reference is an id written in a field: a foreign key.

### 7.1 Forms

| Form | Example | Names |
|---|---|---|
| bare | `O:role/Founder` | an item in the same concern |
| qualified | `atom/mozilla-org//C:ip/mozilla-trademarks` | an item in another concern of the Holotype |
| a concern | `atom/mozilla-org` | a concern |
| the brand | `P:meadow` | P's brand item |
| a vendor | `vendor/<domain>/<slug>` | a fetched vendor-published atom |
| a typed link | `{rel: …, to: <id>}` | the `to` (or `id`) inside it |
| a sentinel | `none`, `self` | nothing, on purpose; the concern itself |
| an open question | `{pending: "…"}` | an answer still owed (section 8) |

An item's own id is written bare in its concern's files; an item id that names another concern is an error
(`id-atom`). References to items of the same concern are written bare too.

### 7.2 Where references are checked

The envelope's reference fields (section 4) and each kind's reference fields (section 5) are checked as references:
each value must be an id string of one of the forms above that resolves, or a sentinel, or an open question. In P every
string that looks like an id outside P is checked the same way (P.5.2). A path is not a reference: files hold ids.

### 7.3 Resolution

A bare id resolves in its own concern's module; a qualified id in the named concern; `atom/<slug>` to the concern;
`vendor/…` to the fetched vendor. Anything else resolves to nothing, and that is an error (`ref-unresolved`), with
three exceptions:

- a vendor id not yet fetched is a warning (`vendor-missing`);
- a SKU named by a mapping row, a price-book rate or an exclusion that a feed brought in resolves against the local
  database; before any feed has been pulled it is a warning (`sku-unverified`);
- a typed link with neither `to` nor `id` is skipped.

### 7.4 Scope

A reference to an item the reader may not see stays as the id with no name (4.2). Resolution never depends on the
reader; display does.

### 7.5 Named relations

`plan/comprise-model.md` names the cross-module relations (owner, holds, serves, sold-through, priced-by, maps-to or
entitles, listed-on, runs-on, presents, about, bound-by, shared-with, feeds, attributed-to, at, twin, counterparty,
licensed-by, requires-credential, member-of). In Comprise OES 1 each is a field; the relation's name is the field's,
and the checks know them only as reference fields. A typed link's `rel` is free text.

---

## 8. Open questions

An **open question** (*pending*) is a value nobody has yet given, written where the value would go:

```yaml
terms: {pending: "funding amount and term are not published"}
pending: After the 2026 transfer the FAQ says Mozilla.org owns the trademarks; which entity is the licensor now?
```

- **Pending beats plausible.** A writer must never guess a value; it writes the question instead.
- **Who answers.** The item's owner; a role answers for itself; otherwise "unassigned". The checks list every open
  question with its item, its field path and who can answer it (`python -m core pending`).
- **Its address.** The item's path plus the field path (`…/C/contract/artists-make-technology#terms`); an open question
  on the whole item is the item's path.
- **What it does to the checks.** An open value is never an error. It makes a rule *unverifiable* where the rule needs
  the value (a price, a rate, a reporting line, a counterparty), and an unverifiable rule refuses signing.
- **Not the same as "not disclosed".** `provenance.state: not-disclosed` says the subject declined to say: a fact.
- **Not the same as "to fill in".** *To fill in* counts the details the question bank would still ask about an item,
  its open questions included; an item with nothing left to fill in is **complete**. The three health figures (open
  questions, to fill in, complete) come from one place, `core/health.py`.

---

## 9. Checks

The checks (*lint*) are the constraints of the database, run on the whole Holotype: `python -m core lint <dir>`. Every
write the app makes goes through them, and a write that adds an error is undone.

### 9.1 What runs

1. **Load problems**: every file that would not parse or did not fit (errors).
2. **The envelope** on every item (section 4), and the reference checks (section 7).
3. **P's checks** per concern (P.9), reported with a `P` prefix.
4. **The fourteen rules** per concern.
5. **Notes**: each fetched vendor-published atom; items still exactly as an archetype gave them.

### 9.2 The envelope's checks

| Check | Severity | Fails when |
|---|---|---|
| `load` | error | a file did not parse, or a declared concern or an undeclared folder did not fit |
| `id-grammar`, `id-module`, `id-atom` | error | an id does not parse, names another module, or is qualified with another concern |
| `type`, `type-prefix` | error | the kind is not the module's, or disagrees with the id |
| `identity-min` | error | name or summary missing |
| `provenance` | error / warning | missing or malformed (error); `integration` without `synced-from` (warning) |
| `source-undeclared` | warning | a source id the catalog and the P docs do not declare |
| `status`, `visibility` | error | not one of the closed values |
| `owner` | error | the owner is not an `O:role` |
| `ref`, `ref-grammar`, `ref-unresolved` | error | a reference is not a string, not an id, or names nothing |
| `vendor-missing`, `sku-unverified` | warning | section 7.3 |
| `no-humans` | error / warning | a pointer to `E:person` from an unrestricted item (error); a singular pronoun in name or summary (warning) |
| `bond`, `bond-mirror` | error / warning | section 3.2 |
| `aim` | error | kind or stance missing or outside its list; a malformed horizon |
| `module-none` | warning | `module: none` without a reason |

### 9.3 The fourteen rules

Each rule reports one of: **pass**, **fail**, **unverifiable**, **finding**. The bold titles below are in this
document's words. The names the checks print (the CLI, the checks page, the export, MCP's `lint` `rules[].name`) are the
manifest's, which keep the model's words where the two differ: rule 1 is `product tree in equilibrium`, rule 7
`claims about real nodes`, rule 8 `bonds two-ended and sourced`, rule 9 `no stale synced nodes`. One line each:

1. **The product tree in equilibrium.** P's seven conditions all `ok`, and no P error (`module: none` passes).
2. **SKUs map to P units.** Every stock item maps to at least one P unit, by `maps-to` or `entitles`, or is excluded with a reason.
3. **Offerings priced.** Every offering has a price or `none`, and every price-book rate agrees with it.
4. **Systems owned and referred.** Every system has an owner and something that refers to it; otherwise a finding (orphan spend).
5. **Positions, roles, owners.** Every position reports to a position (one `none` at most); every role governs or owns something, or is a pool; every owner resolves.
6. **Employed persons assigned.** Every active person of an employment kind holds at least one current assignment, to a position that exists.
7. **Claims about real items.** Every claim is about something that exists, and no claim restates a `must-not`; partial, contested or unsupported evidence is a finding.
8. **Relationships two-ended and sourced.** Both ends are concerns, outside organizations, vendors or groups; mirrored where both are modelled; with sources.
9. **No stale synced items.** No item marked stale or past its `max-age`, no active feed never pulled or overdue, no reflections grant overdue.
10. **Counterparties resolve.** Every channel, feed, vendor, platform and platform surface names one `C:counterparty` (a direct channel, or a feed read from a file, by hand or from an MCP source, may say `none`).
11. **No double-counted rollups.** Effective ownership over `owns` is cycle-safe, and no `C:finance` consolidates a concern held at equity or cost.
12. **Credentialed positions.** A position that requires a credential is held by someone who holds it.
13. **Bus factor.** A person holding more roles than the limit (default 3) is a finding.
14. **Shell records to promote.** A non-anchor entity or a template instance with its own owners or offerings is a finding: promote it to a concern.

Rules 6, 12 and 13 read the local database; without it they are unverifiable, unless the people are `none` with a
reason.

### 9.4 The verdict

- **ok**: no error and no failed rule. This is the exit code.
- **ATTEST: allowed**: ok, and no rule unverifiable. Findings never block. This is "can this version be signed?"

---

## 10. Versions

- **A saved version** (*snapshot*) is an immutable copy of the model files at a moment, at `snapshots/<stamp>/`: the
  catalog, everything under `atoms/`, the bindings and the fetched vendors; never the local database, the people file,
  feed payloads or scan runs. Its `manifest.yaml` holds when and by whom, every file's sha256, each concern's content
  hash and item count, the export's hash, the checks' verdict, the people counts, the perspective concern's standing,
  and its own hash. Taking one changes nothing and is always allowed.
- **The diff** is item by item, between two saved versions or one and now: concerns and items added and removed, items
  changed with the field paths that moved, an open question answered, a value reopened. A reader's hidden items stay out.
- **As of.** A saved version opens read-only (`as_of`), and reports run against it. `snapshot timeline` is the change
  across all of them.
- **A signed version** (*attestation*) is a saved version the checks allowed, whose files still match their hashes,
  signed by the holders of the roles that govern it: one Ed25519 signature per signer over a canonical statement (the
  Holotype, the stamp, the manifest hash, the export hash, the signer, the roles, the time), in `attestation.yaml` beside
  it. Signers are person ids, never names. Signing needs a first-party perspective concern. A signed version is a signed
  snapshot; never "legally equivalent" to anything.
- **Hashes.** A concern's content hash is the sha256 of its module files in path order. The export's hash moves with
  its content.

---

## 11. The private/public split

**The Holotype is private by construction; the isotype is public by construction.** Two formats, not one format with a
setting.

### 11.1 The private side

- The files stay on the subject's machine. Nothing leaves unless a person set up where it goes.
- People are only in the local database, sealed field by field under a key kept in the keychain: encrypted
  (AES-256-GCM) when the optional `cryptography` package is present, tamper-evident only (HMAC) without it, and
  plaintext when there is no key at all, which `people list` says plainly.
- Credentials are in the keychain, never in a file; private keys under the home folder, never in a Holotype.
- A backup (`comprise-bundle/0`) is encrypted on the machine before it leaves; Comprise Connect stores ciphertext and
  holds no key.
- Inside, visibility (4.2) decides who reads what: `restricted` items reach only their module's editors.

### 11.2 Renderings for an audience

| Rendering | Shows |
|---|---|
| the export, `internal` | everything; people as counts; open questions, mismatches and checks |
| the export, `external` | public items only; no owners, provenance, open questions, links, places, sharing, costs, roles, mismatches or checks; no E; no C finance, cap tables or instruments; P by P.10 |
| the export, `agent-for-support` | the public items of every module, plus all of P and R; no C finance; no E |
| a published atom | the external rule, as files a vendor serves, signed |

### 11.3 The isotype: a view, default-deny

The isotype (`comprise-isotype/0`) is a separate document with a fixed schema, computed from the Holotype by rules, one
rule per field. It is a view with fixed columns: a field added to the model later never flows into it by itself.

```
{isotype, hid, epoch, cadence, sample, identity, shape, offers, seeks, open_to}
identity:  name, domains, jurisdiction, founded, kind
shape:     employees (some | none), structure (single | group), markets
offers[]:  name, summary, kind (suite, offering, function, product, service, audience)
seeks[], open_to[]:  kind (the aim kinds), summary
```

| Field | Derived from |
|---|---|
| `identity.name`, `kind`, `founded` | the public brand (P.10), and a public anchor entity for the founded year |
| `identity.jurisdiction` | a public anchor entity only |
| `identity.domains` | public `kind: website` surfaces with no counterparty, and a public anchor entity's domains |
| `shape.employees` | `some` when the database holds an employed person or a public position is live; `none` only when E says so in its reason; else absent |
| `shape.structure` | `group` when public `owns`, `controls` or `common-control` relationships join concerns; `single` when none touches it; else absent |
| `shape.markets` | public audiences (at most 12), the regions they and public geographies name, public markets (at most 6) |
| `offers` | the live, public suites and offerings of every member (products and services when there are none), at most 50 |
| `seeks`, `open_to` | public, live or planned `C:aim` items, by stance |

**The rules that bind it** (decision Q50):

- **Assertions, not measurements.** No counts of anything internal; the only number is the founded year.
- **Withhold, never falsify.** What is not public is left out and leaves no mark. An offer whose summary holds a
  digit keeps its name and loses the summary; an aim or a market with a digit is left out.
- **Verified and stated.** Identity, shape and offers are derived from the Holotype (*verified*); seeks and open to are
  the company's own words (*stated*).
- **Epochs and bands.** The date is the epoch (`2026-Q4`, `2026-10`, `2026-W43`), never the day of an edit; lists are
  sorted so file order leaks nothing; a banded number moves only after 90 days past the boundary.
- **One release per epoch, signed.** Quarterly by default; monthly or weekly by choice. A release needs a first-party
  concern, unless the Holotype is a sample, whose isotype says `sample: true` and is signed by the install's sample key.
- **Opt-indexed.** Nothing is listed on the Index unless the subject released it and chose to list it.

*Not built:* the dial, more isotype fields a subject may open one at a time, each opt-in and marked verified or stated.

---

## 12. Renderers

A **renderer** turns a Holotype into another form. Renderers only read. Each applies the reader's scope (4.2): a hidden
item is absent.

| Renderer | Makes | Where |
|---|---|---|
| the 3D Overview | the scene: a campus with a building per concern, its modules as blocks, kinds, items as bricks, fields as stairs | `core/overview3d.py`, `app/static/overview3d/` |
| the circles (V1) | concerns, modules, kinds and items as circles within circles | `core/overview.py`, `app/static/overview.js` |
| the Field Guide | the Summary, the eight chapters, the item pages, the questions | `app/fieldguide.py`, `app/fieldpages.py` |
| the text tree | P as indented text, with the relationships and the derived tree | `python -m core ascii`, `tree` |
| the export | `CONTEXT.md` for an audience and a scope, with its hash | `core/pack.py`, `python -m core pack` |
| reports | columns and rows from a definition, as of now or a saved version | `core/reports.py` |
| the diff and the timeline | change between saved versions | `core/snapshot.py` |
| the company mark | an isometric cluster in the module colours, sized by contents | `core/mark.py` |
| the published atom | a concern's public files, signed, for a vendor to serve | `core/publish.py` |
| the isotype | the public projection (11.3) | `core/isotype.py` |
| P's card and Mermaid views | one item's nine aspects; `map`, `tree`, `flow`, `affect`, `mattering` | cosm.py, through `core/cosm_bridge.py` |
| the deck | PDF, SVG and HTML pages of a product tree | the skill's `cosm_deck.py`; the app does not call it |

*Not built:* renderers driven by a reader's own style profile; rewritings for beginners, story problems and narrative
(the text cases of what the trade calls *transcreation*).

---

## 13. Conformance

### 13.1 A reader must

1. Read the catalog; accept `oes: comprise/1`; read a catalog without `oes:` as Comprise OES 1; refuse an unknown
   MiniCOSM or version with a plain error (2.3).
2. Load every declared concern's eight modules from `*.cosm` files at any depth, as UTF-8 with an optional BOM, with
   YAML 1.2 booleans, never stopping at the first problem (2.4, 2.5).
3. Read P's `brand:` (and a legacy `firm:`) with `nodes:`, and the legacy kinds `firm` and `stack` (P.7).
4. Keep unknown fields and unknown catalog keys.
5. Resolve references as section 7 says; treat a path as a respelling of an id (section 6), resolved against the loaded
   Holotype, never the disk.
6. Apply visibility (4.2) before showing anything: a hidden item is absent, and a reference to it keeps its id and no
   name.
7. Never read the local database's people into anything but counts, outside E's own pages.

### 13.2 A writer must

1. Write `oes: comprise/1` first in a new catalog, and never rewrite another's (2.3).
2. Write only the COSM YAML subset: no anchors, aliases, tags or multiple documents.
3. Write ids bare inside their own concern, with the kind equal to `type`, and the brand as `P:<slug>`.
4. Write `brand:`, never `firm:`; roles in O, contracts in C; no `externals:` in P.
5. Never write a person into a file: no names, no `E` items, people only in the local database.
6. Write an open question, never a guess. Cite sources for every fact.
7. Write nothing a person did not accept: a model, scan, feed or agent only proposes.
8. Leave a Holotype's checks no worse: a write that adds an error is undone.

### 13.3 What the checks verify, and what they do not

**Verified:** the load, the `oes:` declaration included (2.3); the id grammar; kinds per module; the envelope's closed
lists, required fields and provenance; owners are roles; every reference resolves (with the exceptions in 7.3);
relationship kinds and bases; aims; P's per-item checks and seven conditions; the fourteen rules.

**Not verified** (a writer must still keep them):

- that no item is written into an E file;
- that exactly one entity per concern is the anchor, and that the brand holds at least one part;
- that a `restricted` item's pointer to a person is lawful;
- inherited `must` and `must-not` are not weakened (P.12);
- that ids differ by more than case, and that every slug is path-safe (6.4.8);
- that an `M:account` is restricted.

### 13.4 Where the code wins

Besides chapter P.12:

| Text elsewhere says | The code does |
|---|---|
| HELP_CENTER §8: one file per type family under `{C,O,M,P,R,I,S}/` | reads any `*.cosm` at any depth under a module folder |
| `plan/comprise-model.md` §5 lists C's kinds without `aim` | `C:aim` exists (slice 26a) |
| `plan/comprise-model.md` §4: the envelope includes `pending, links, mattering, body` | the same, plus `shared-with` as an envelope reference |
| `plan/comprise-model.md` §8: E is canonical in the store | as written; the store's `access` table also holds team access levels |
| `plan/comprise-model.md` §1, §4: any item may say `at: site/…` | `at` must be an id or a date; `site/…` is a `ref-grammar` error, because sites are not items yet (`I:location` keeps `site` as free text) |
| COSM 0.3's API: "ids are the only handles" | paths are accepted beside ids (section 6) |

---

## 14. Decisions in this version

Made by the writer of slice 30b, 2026-10-20, without asking, as the brief required. Slice 30c built on them, so a
change to what a path means now needs a new MiniCOSM (decision 9).

1. **The spec is one document**, with the product tree as chapter P and the other seven modules as chapters of the same
   shape. COSM 0.3's normative text survives in chapter P; its unbuilt API is a table (P.11).
2. **Paths are a pure respelling of ids.** No lookup, no index. Checked: all 1,227 items of the six fixtures round-trip.
3. **The brand's path is `<concern>/P/brand/<slug>`**, mapping to `P:<slug>`. One-to-one because `P:brand/<slug>` is
   never a valid id. `<concern>/P/<slug>` is not a path.
4. **The kind level is a table, never a file.** Neither ids nor paths name files; the file is metadata.
5. **A relationship has one path per copy**, each in its own concern; cite the copy in the `from` concern.
6. **Outside organizations are ordinary C items.** Their global id is a field, not part of a path.
7. **A vendor-published atom is addressed only as a whole**, `vendor/<domain>/<slug>`, which is also its id. Its items
   are addressed in the vendor's own Holotype by the qualified form. The case of the second segment keeps it apart from
   a concern called `vendor`.
8. **Fields use the checks' own field paths** after `#`: keys by `.`, list positions by `[n]` from zero. Fields only
   follow items. An open question on a whole item is the item's path.
9. **The qualified form is `oes:comprise/<holotype>/<path>`**, with the Holotype's id slug and no version. A path must
   keep its meaning across versions; a change of meaning is a new MiniCOSM. A globally unique Holotype name is not built.
10. **Case is kept and significant.** The slug's characters are the ones the tooling already reads (`[A-Za-z0-9._@-]`,
    no trailing dot). An id outside them has no path; a warning for it, and for ids that differ only in case, is
    proposed and not built (slice 30c did not add it), and not specified as a check here.
11. **One spelling.** A reader refuses a malformed path rather than normalizing it: no trailing slash, no `..`, no `%`.
12. **The catalog's entries have no path** in version 1 (sources, grants, groups, attestations).
13. **When a catalog has both `oes:` and `comprise:`, `oes:` decides.** An unknown version of a known MiniCOSM is refused
    like an unknown MiniCOSM. A new catalog carries the declaration as its first line, so a person or a tool sees it
    without parsing the file.
14. **P files keep `cosm: 0.3`.** It is the product tree's format version, read by P's checks, and says nothing about
    the MiniCOSM.
15. **The manifest is a `.cosm` file outside every Holotype**, beside this spec. A Holotype names its MiniCOSM by the
    declaration only and never embeds the manifest. The word *manifest* has two senses in Comprise: this declaration of a
    language, and the hash list of a saved version, a bundle or a published atom. They never meet on screen.
16. **The manifest's fields per kind are the schema's reference fields, exactly**, plus the fields a check reads. Every
    other field is open, as the schema says. P lists its nine aspects. E's kinds are marked as stored in the local
    database.
17. **An absent visibility outside P reads as `internal`**: visible to every signed-in reader, never public. This is
    what the code does; the spec states it.
18. **`P:release` stays declared and is marked as rejected by P's checks.** The disagreement is listed, not resolved:
    fixing it is a code change (the schema or cosm.py), outside this slice.
19. **Words.** The spec says concern, item, relationship, open question, outside organization and kind, with the model's
    term in parentheses where exactness needs it. Ids, file names and check names keep the model's words, because they
    are the format.
