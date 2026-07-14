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
