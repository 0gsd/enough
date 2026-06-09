# Mission: Girraph — build plan & tracking doc

Status: **v1 complete — shipped in 0.1.1**
Opened: 2026-06-09 · Built: 2026-06-09
Format approved by user 2026-06-09: as proposed, incl. `next:` header,
end-of-file detail blocks, no-orphan + explicit-cascade removal.

A girraph (pronounced "graph" — the `ir` is for iterative/recursive) is a
plain-text, IBIS-flavored graph document: issues, positions, arguments,
notes, where any node can recursively be another girraph, an inline
details view, or a reference to any markdown doc in the project or
infoworld. Core primitive, not a paradigm.

Charter constraints (non-negotiable):

- Files are the source of truth; any index is a derived, disposable cache.
- Small-model ergonomics: line-oriented records, one node = one line.
- Stable node IDs, assigned at creation, never reused.
- Depth-limited reads; lazy expansion, stubs for refs.
- No deletes without confirmation.

Prior art consulted: Argdown (argdown.org) — titles-as-identifiers,
indentation-as-tree, `+`/`-` relation sigils. We steal the sigil idea and
the "plain text argument map" spirit, but diverge on structure: Argdown
uses *indentation* for the tree, which forces whole-file rewrites to
reparent and is fragile for small models patching single lines. We use
*explicit parent edges* (`< id`) so every node line is self-contained and
independently patchable, and *stable short IDs* instead of title strings
(labels can be edited freely without breaking edges).

---

## Proposed file format (v0.1)

```
%girraph 0.1
title: Should enough ship a plugin API?
next: q2 p3 a4 n2 g2

q1 ? Should enough ship a plugin API?
p1 ! Ship a minimal one < q1
p2 ! Don't — skills are enough < q1
a1 + Ecosystem growth needs stable hooks < p1 by:graham
a2 - API surface = forever maintenance < p1 by:open-skeptic
a3 + Skills already cover 80% of cases < p2 [-> a2]
n1 . Background reading < q1 ref:infoworld/plugins-survey.md
g1 @ Subproblem: versioning policy < p1 ref:rness/girraphs/versioning.girraph

q1 >
  Longer free-form details for the root issue live in an
  indented block under `id >`. Markdown allowed.
```

### Grammar (line-oriented)

**Header** — `%girraph 0.1` magic line (required, first line), then
optional `title:` and `next:` lines, then a blank line.

- `next:` is a broker-maintained high-water-mark list (one token per ID
  prefix in use). It is what makes "IDs are never reused" a guarantee
  rather than a hope: without it, deleting the highest-numbered node and
  adding a new one would silently recycle the ID, and anything that
  referenced the old node (chat history, sidecars, cross-edges in other
  girraphs) would point at the wrong thing. If the line is absent
  (hand-authored file), the broker derives max+1 and adds it on first
  write.

**Node record** — `<id> <sigil> <label> [modifiers...]`, one per line.

- `id` — `[a-z]+[0-9]+`. Conventional prefixes: `q` issue, `p` position,
  `a` argument, `n` note, `g` nested girraph; any prefix is legal.
  Unique per file, assigned by the broker at creation, never reused.
- sigils / types (render emoji shown):
  - `?` issue ❓
  - `!` position 💡
  - `+` supporting argument ➕
  - `-` objecting argument ➖
  - `.` note / plain 📄
  - `@` nested girraph 🦒 (must carry a `ref:` to a `.girraph`)
- modifiers, recognized as trailing whitespace-delimited tokens and
  stripped right-to-left until a non-modifier token is hit; everything
  remaining is the label:
  - `< <id>` — parent edge (the tree backbone; at most one)
  - `[-> <id>]` — cross-edge, repeatable. Rendered as an inline `→`
    chip/annotation, never a drawn line. Parser also accepts `[→ id]`
    and sloppy spacing; canonical on-disk form is ASCII `[-> id]`
    (greppable, typable, 2056-proof — the emoji/arrow glyphs live in
    the render views only).
  - `ref:<path>` — transclusion. Project-root-relative path to a
    markdown doc (rendered read-only in place) or another `.girraph`
    (recursion). Same mechanism for both; that's the point.
  - `by:<slug>` — attribution: `user`, `agent`, or a role name.
    Kebab-case, no spaces.
- Canonical serialization order: `id sigil label < parent [-> x] ref:… by:…`.
  Known wrinkle: a hand-written label *ending* in something that parses
  as a modifier (e.g. "…suggested by:graham") will be read as metadata.
  Tools always serialize canonically; the ASCII render makes any
  misparse immediately visible; accepted as a plain-text tradeoff.

**Detail blocks** — a line `<id> >` followed by indented lines
(canonical two spaces; any leading whitespace accepted). Markdown
allowed. Parser accepts blocks anywhere; canonical serialization
collects them at the end of the file in node order, so the node list
stays a clean scannable table.

**Root** — the first node with no parent. (No `root:` header — derived,
one less thing for a small model to keep consistent. Multiple parentless
nodes = a forest; the first is the entry point.)

**Cycles** — legal via refs (`.girraph` A can ref B can ref A). The
navigator handles them (breadcrumbs + visited set); the format doesn't
forbid them. Parent edges within one file are validated acyclic.

**Round-trip safety** — lines the parser doesn't understand are
preserved verbatim ("freeform" lines), reported as warnings in tool
results, and never destroyed by the serializer. A flaky small model (or
a human in a text editor in 2056) can't lose data by writing something
the grammar doesn't cover.

**Broken refs** — a `ref:` whose target doesn't exist renders as a
⚠ broken-ref stub in every view (panel, ASCII, read_girraph), with a
repair affordance in the panel (re-point via `update_node`; the harness
suggests same-basename matches elsewhere in the project, in the spirit
of the broker index). The file itself is never auto-rewritten.

---

## Broker tools (agent-facing)

Same XML-ish conventions as the existing tools in `tools.py` / `prompt.py`.
All writes are node-level read→patch→write of the file under a per-path
lock; last-write-wins at node granularity (documented conflict policy
for simultaneous user-panel and agent edits). Agent `write_file` to
`*.girraph` is denied with a pointer at these ops.

```
<tool name="read_girraph">
  <path>plans/plugin-api.girraph</path>
  <node>p1</node>        <!-- optional; default: root -->
  <depth>1</depth>       <!-- optional; default 1 = node + children -->
</tool>
```
Returns the ASCII render of the requested subtree: `@`/`ref:` nodes as
one-line stubs (never auto-expanded), detail blocks elided to a
`(+detail)` marker, truncation notes where depth cut the tree, total
node count. Reading a doc-`ref` target = plain `read_file`.

```
<tool name="add_node">
  <path>plans/plugin-api.girraph</path>
  <type>objection</type>             <!-- issue|position|support|objection|note|girraph, or the sigil -->
  <label>API surface = forever maintenance</label>
  <parent>p1</parent>                <!-- optional; omitted ⇒ new root. Missing file + no parent ⇒ file created, label becomes title -->
  <ref>…</ref> <by>…</by> <detail>…</detail>   <!-- optional -->
</tool>
```
Broker assigns and returns the ID.

```
<tool name="update_node">
  <path>…</path> <id>a2</id>
  <label>…</label> <detail>…</detail> <ref>…</ref> <by>…</by>
  <!-- only tags present are patched; an empty tag clears the field -->
</tool>

<tool name="link_nodes">
  <path>…</path> <from>a3</from> <to>a2</to>
</tool>

<tool name="remove_node">
  <path>…</path> <id>a2</id>
  <cascade>true</cascade>     <!-- required if the node has children -->
  <confirmed>yes</confirmed>  <!-- must reflect explicit user confirmation this turn -->
</tool>
```
`remove_node` semantics (proposed): **no orphaning, ever** — removing a
node with children errors and lists them unless `cascade` is explicit;
cascade removes the subtree. Cross-edges pointing at removed nodes are
deleted from their source lines (journaled). Detail blocks go with their
nodes. Re-parenting (true "orphan then adopt") is `update_node` with a
`parent` field — deferred unless wanted in v1.

`prompt.py` gets a "Working with girraphs" section: when to reach for
one (mapping a wicked/contested problem, plan structure under
text-planning, any "let's map this out"), depth-limit etiquette, and the
checkpoint-native note — girraphs are the agent's map; after a context
reset, re-orient by `read_girraph` on the working branch only.

## UI: girraph panel

A third panel mode (alongside preview and review) for `.girraph` files.
htmx + vanilla only.

- Collapsible indented tree, type emoji, cross-edges as clickable `→ id`
  chips (jump-to-node).
- Click `@` node → navigate into the nested girraph; click doc-`ref`
  node → render that markdown read-only in place. Breadcrumb trail for
  the descent stack; visited-set so cycles can't trap.
- Inline label/detail editing + add-child / add-cross-edge affordances
  per node — all through the same server-side node ops as agent edits.
- Server endpoints mirroring the highlights API shape:
  `GET /api/girraph` (tree fragment), `POST /api/girraph/node`,
  `PATCH /api/girraph/node`, `DELETE /api/girraph/node`,
  `POST /api/girraph/link`.

## ASCII render view

Derived view (also a broker-exposed function so the agent can embed it
in docs): indented tree, type emoji, `[→ id]` annotations, detail blocks
elided to a marker. A view, never the storage format.

## Default skill: ibis-girraphiti

`defaults/skills/ibis-girraphiti/SKILL.md`, disabled by default,
following the SKILL.md format + description-field discipline from
`defaults/paradigms/workflow-design.md`. Carries the IBIS discipline:

- Issue vs position vs argument; when to split into a nested girraph.
- Anti-solution-jumping: no interventions until the user confirms the map.
- The imposed stopping rule (wicked problems have none; user
  confirmation of the map is ours).
- When to challenge framing vs record it; one question per turn while
  mapping.
- `by:` discipline — whose claim is each node, including future
  synthesized stakeholder roles.

Plus one short paragraph in `defaults/paradigms/text-planning.md`: when
ibis-girraphiti is enabled, plan structure lives in a girraph at the
project root.

## Out of scope for v1

- Query engine of any kind (grep covers it; an embedded index like Kuzu
  can come later as a derived cache without migration pain).
- Graphviz/mermaid export (TODO stub only).
- Drawn-edge graph layout.
- Multi-user/sync.

---

## Phases

- [x] **Phase 0 — format proposal** (this doc) → approved 2026-06-09
- [x] **Phase 1 — core module**: `enough/girraph.py` — parser,
      serializer, node ops, ASCII renderer, `next:` bookkeeping,
      freeform-line preservation. `tests/test_girraph.py` (20 tests)
      incl. malformed small-model input and round-trip stability.
- [x] **Phase 2 — broker tools**: five tools in `tools.py` + dispatch
      + trace logging; `write_file` denial for `.girraph`; `prompt.py`
      examples + "Working with girraphs" section.
      `tests/test_girraph_tools.py` (8 tests, every op).
- [x] **Phase 3 — server API**: `/api/girraph*` endpoints (GET tree,
      POST/PATCH/DELETE node, POST link, GET ref-candidates), per-path
      write lock shared with the tools, panel edits journaled via
      broker.trace. `tests/test_girraph_api.py` (5 tests).
- [x] **Phase 4 — UI panel**: `#girraph-mode` full-frame mode (the
      third, alongside review/edit), collapsible tree, breadcrumb
      stack with cycle-safe push (revisit = pop back), inline
      label/detail editing, add-child/cross-edge/remove affordances,
      doc-ref read-only transclusion, broken-ref ⚠ chip + repair
      prompt with same-basename suggestions. Smoke-tested live in a
      browser, including the deliberate A→B→A ref cycle.
- [x] **Phase 5 — skill + docs**: `defaults/skills/ibis-girraphiti/`
      (disabled by default per globals convention), text-planning
      paragraph, `docs/girraphs.md` explainer, AGENT_GUIDE girraph
      section + tools table + code map row.

## Acceptance checklist (from the mission)

- [x] Round-trip: agent creates via tools → user edits labels in panel →
      agent patches a node → file clean, diffable, correct.
      (test_round_trip_agent_user_agent + live smoke test)
- [x] Doc-ref renders read-only in panel; broken ref shows repair
      affordance. (live: 📄 chip rendered plugins-survey.md with a real
      table; ⚠ chip + candidates prompt on a broken ref)
- [x] Nested girraphs navigate in/out with breadcrumbs; a deliberately
      cyclic ref doesn't trap or crash. (live: stack popped back)
- [x] `read_girraph` at default depth on a deep tree returns stubs.
      (test_read_girraph_depth_stubs, test_ascii_render_depth_limits)
- [x] ASCII view of the example file looks good in a terminal. (verified)
- [x] Tests: parser/serializer incl. malformed input + every broker op.
      (33 tests total, `uv run pytest`)
- [x] Docs: `girraphs.md` explainer + AGENT_GUIDE update.

## Decision log

- 2026-06-09 — proposal drafted; explicit parent edges over Argdown
  indentation (single-line patchability); ASCII canonical syntax with
  emoji confined to views; `next:` header for ID never-reuse;
  detail blocks canonical at end-of-file; remove_node = no-orphan +
  explicit cascade. Approved by user same day, built same day.
- Conflict policy as documented in girraph.py: per-path lock around
  read→patch→write; last-write-wins at node granularity.
- UI confirmation for deletes = the panel's confirm dialog; agent
  confirmation = `<confirmed>yes</confirmed>` only after the user
  confirms in chat (enforced by prompt instructions + tool gate).
