# merirmaid — format & architecture plan (v0.1.6)

> Companion to [girraph-plan.md](girraph-plan.md). A **merirmaid** file is
> enough's flavor of a Mermaid diagram: plain Mermaid source wrapped in a
> small frontmatter header, rendered to SVG live in the browser by a
> vendored mermaid.js. The *ir* is for iterative/recursive, same joke as
> girraph. Pronounced "mermaid".

## Design decisions (pinned 2026-07-13, do not re-litigate in implementation)

1. **Plain text is the source of truth.** A `.merirmaid` file is Mermaid
   source + frontmatter — never a stored SVG. Rendering happens at view
   time in the frontend via a vendored (local, no CDN) `mermaid.min.js`
   in `enough/static/`, shipped the same way as `htmx.min.js`.
2. **Two modalities, built into the format from day one:**
   - `wip` — a working diagram / brainstorming whiteboard. Node *text*
     is user-editable in the merirmaid mode viewer (structure/node
     editing is agent-only for now, via chat).
   - `mirror` — a source-of-truth diagram that mirrors some external
     structure (the launch use case: a cachebox's contents). Read-only
     in the UI; only the system that owns the mirrored structure may
     regenerate it. The viewer shows a clear "mirror" indicator instead
     of edit affordances.
3. **No WYSIWYG structure editing in v0.1.6.** The chat pill overlay in
   merirmaid mode is the editing interface for structure — the user asks
   the agent, the agent rewrites the source.

## File format

Extension: `.merirmaid`. UTF-8 text:

```
---
merirmaid: 1
title: How the broker gates tools
modality: wip            # wip | mirror
node-char-limit: 48      # soft per-node-label limit the editor surfaces
source: cachebox:wiki    # mirrors only — what this file mirrors
generated: 2026-07-13T21:40:00Z   # mirrors only — last regeneration
---
flowchart TD
  A[tool call] --> B{broker toggle on?}
  B -- yes --> C[runner executes]
  B -- no --> D[canned denial]
```

- Frontmatter is `key: value` lines between `---` fences, first thing in
  the file. `merirmaid: 1` is required (format version). `title` and
  `modality` are required; the rest optional. Unknown keys are preserved.
- Everything after the closing fence is verbatim Mermaid source, any
  diagram type mermaid.js supports (flowchart, sequence, state, ER, …).
- **Linking diagrams as nodes:** use Mermaid `click` interactions with a
  relative path, e.g. `click A "other-diagram.merirmaid"`. The viewer
  intercepts clicks and pushes the target onto a breadcrumb stack
  (same navigation pattern as girraph mode's `@` refs). Targets may be
  `.merirmaid`, `.girraph`, or `.md` paths.
- `node-char-limit` is a *soft* limit: the in-node text editor shows a
  live count and warns past the limit but does not block. Agent-side,
  the girraph-merirmaid skill instructs generated diagrams to stay well
  under it (leave room for user edits).

## Who reads/writes what

| Actor | Read | Write |
|---|---|---|
| Agent | `read_file` (plain text — no special tool needed) | `write_file`, except **mirror files under `~/enough/cacheawl/`**, which only `enough/cacheawl.py` regenerates |
| Merirmaid mode UI | existing file-content endpoint | node-label edits patch the Mermaid source client-side and save through the existing file-write endpoint; refused for `modality: mirror` |
| cacheawl backend | — | owns `_cachebox.merirmaid` mirror files (see below) |

Unlike `.girraph`, whole-file writes of `.merirmaid` are **allowed** —
there are no broker-assigned IDs to protect. The one write restriction:
`run_write_file` and `POST /api/file` must refuse to modify a file whose
frontmatter says `modality: mirror` *and* which lives under
`~/enough/cacheawl/` (agent edits to a mirror would drift from the
structure it mirrors; the denial message should say to edit the cachebox
contents instead).

## The cachebox mirror contract

Every cachebox (a root folder in `~/enough/cacheawl/`) contains a
`_cachebox.merirmaid` at its root with:

- `modality: mirror`, `source: cachebox:<name>`, `generated: <ISO ts>`
- A `flowchart TD` whose root node is the cachebox, with folder nodes
  and file leaf nodes mirroring the tree (depth-capped presentation is
  fine for huge boxes — cap at the point where a subtree collapses into
  a single `[N files]` node), plus a metadata node (origin request,
  item count, total size, created/updated timestamps).
- Node ids derived from relative paths (slugified, stable across
  regenerations so diffs stay readable).

`enough/cacheawl.py` regenerates the mirror on every mutation it makes
(ingest, copy/move in or out, delete). Manual file drops the backend
didn't see get reconciled the next time cacheawl mode opens (the UI's
listing endpoint triggers a freshness check).

## Merirmaid mode (the viewer)

Full-frame mode like girraph mode, with the chat pill overlay. Toolbar:
title, modality badge, breadcrumbs for `click`-navigation. Body: the
rendered SVG. Interactions:

- Click a node's text (wip only) → in-place editor with live char count
  vs `node-char-limit`; save patches the label in the source and
  re-renders.
- Render errors (bad Mermaid) show the mermaid.js error plus the raw
  source in a `<pre>` — never a blank pane.
- Active-mode icon: `merirmaidmode.svg` top-right with the
  `ribbon-redx.svg` exit ribbon, per the v0.1.6 mode conventions.

---

# v0.1.7 additions — view/edit split, node menu, cacheawl squircles

> Draft spec for review (pinned 2026-07-21). Extends the viewer above.
> The engine is unchanged; this formalizes the two modalities as two UI
> faces and adds a per-node action menu + a launch affordance in cacheawl.

## Two faces of the same viewer: `mirror` (view-only) vs `wip` (edit)

The `modality` frontmatter field (already in the format) drives which face
the viewer opens in. Same render engine, different chrome:

- **`mirror` → view-only face.** Cool/slate chrome, a "mirror" badge, no
  label-edit affordances. The body is a read-only reflection of some
  external structure (a cachebox or a folder within one). This is the face
  the cacheawl squircles (below) launch.
- **`wip` → edit face.** Warm/amber chrome, a "wip" badge, in-place label
  editing as specified above. This is the brainstorm/mindmap face.

Color-coding the chrome by modality is the *only* new visual state — it
makes "am I looking at a live mirror or my own scratch diagram?" obvious
at a glance. The viewer takes a `readonly` flag derived from modality;
`mirror` forces it on regardless of source.

## Per-node action menu (shift-click a node)

Shift-click any node in the rendered SVG opens a small context menu. The
options are **filtered by node type**, and the menu is wired in **both**
faces (mirror and wip) — even though wip currently only surfaces the
copy-path option, the hook is there for future per-node actions.

- **Folder node** → *Copy path on disk* · *Open folder in cacheawl*
  (navigate the cacheawl grid to that folder).
- **File node** → *Copy path on disk* · *Copy file to clipboard* ·
  *Open in {mode} mode* (route the file to its natural viewer — text→
  read/edit, `.girraph`→girraph, `.merirmaid`→merirmaid — via the
  `cacheawl:<box>/<rel>` scheme).

For the menu to know a node's real on-disk path and type, the mirror
payload carries a **node map**: `{ nodeId → { path, is_dir } }`, where
`path` is relative to the box root (join with the box root for the
absolute disk path). See the cacheawl `mirror` endpoint below.

## On-demand sub-folder mirrors (no extra files on disk)

Every cachebox keeps its one persisted `_cachebox.merirmaid` at the root
(unchanged). **Sub-folder mirrors are generated on demand and never
written** — this honors the "no anonymous extra subfile in every folder"
constraint while still giving every folder a diagram.

- The generator (`_mirror_body` / `_mirror_text` in `cacheawl.py`) gains a
  `subpath` parameter to scope the flowchart to a subtree (root node =
  that folder, depth-capped as today).
- Nothing is persisted for sub-mirrors; they're produced per request and
  rendered live. The root box mirror remains a real file (the existing
  contract + the reconcile-on-listing freshness check are untouched).

## Launch affordance: the cacheawl squircle

A **30px squircle** icon sits in the upper-left of every cachebox header
*and* every folder node's hitbox in the cacheawl icon grid. Clicking it
opens the merirmaid **view-only** face:

- **Cachebox root** → opens the real `_cachebox.merirmaid` (`modality:
  mirror`).
- **Sub-folder** → opens the on-demand virtual mirror for that subtree.

The squircle is the *only* entry point that distinguishes "look at this
folder's shape" from the normal double-click-to-open-contents gesture, so
folders no longer need a visible mirror file to be diagrammable.

See [cacheawl-plan.md](cacheawl-plan.md) for the backing
`GET /api/cacheawl/mirror` endpoint and the squircle's grid placement.
