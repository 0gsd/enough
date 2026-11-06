# MacroCOSM OES, edition 0.5.4: the shapes of its tables (an excerpt)

The tables of the edition before the fabula round, kept so that the overlay is held to read a text synced before 0.6
(`emf` rows, MiniCOSM headers). Excerpted byte for byte from docs/MACROCOSM_OES.md at 0.5.4 (b0d0573).

## 14. Renderers and lenses

### 14.5 Lenses that ship

| MiniCOSM | Lens | Draws |
|---|---|---|
| `canon` | `tree` | the volume's folders, files and articles, joined by `parent` |
| `cosm` | `tree` | the product tree, from the brand to its units, joined by `parts` |
| `emf` | `claims` | entities, concepts and claims, joined by role slots and typed links, coloured by stance |
| `emf` | `map` | the text's lexicon, entities, concepts, claims and events as a mindmap |
| `comprise`, `cosm`, `canon` | `map` (the generic lens) | every module, every reference field and typed link, `parts` and `parent` |

## 18. The MiniCOSMs

<!-- atem: the seven registered MiniCOSMs, one manifest each -->
Seven MiniCOSMs are registered, one manifest each, with one sidecar of moves beside them (section 13.4). Three are
specified in documents of their own: Comprise OES at https://comprise.cosmoes.org/, Ascribe at
https://ascribe.cosmoes.org/ and Thym at https://thym.cosmoes.org/; the other four are specified in this section.

| MiniCOSM | Declaration | Enumerates | Volume | Catalog | Modules |
|---|---|---|---|---|---|
| `comprise` | `oes: comprise/1` | a company: its concerns, their relationships, eight modules each | a folder, the Holotype | `holotype.cosm` | C O M P R I S E |
| `cosm` | `cosm: 0.2` · `0.3`, `opi:` | one whole's product tree, outside any Holotype | a folder of `.cosm` files | the file holding `brand:` | P |
| `canon` | `oes: canon/1` | a Canon volume, or a project: folders, files, articles, and what has been derived from them | one file | `canon.cosm` | V |
| `emf` | `oes: emf/1` | one text: its words, the things and ideas it names, its claims, its events, its atems | one file, beside the text | `<text>.cosm` | L E K P T X |
| `doc` | `oes: doc/1` | one document: its sections, terms, examples and decisions, joined to the reference | one file per telling, built by enough | `<doc>.<lang>.doc.cosm` | S T R B |
| `ascribe` | `oes: ascribe/1` | one person, without a name: the holograph, ten kinds of node anchored to forms | a folder, the holograph | `holograph.cosm` | A B C E I O Q S U Y F |
| `thym` | `oes: thym/1` | Thym's programs, morphs, contexts, plans, traces and packages | one file, one of six kinds | `<name>.thym.cosm`, `<name>.morph.cosm` … | P M C R K |

