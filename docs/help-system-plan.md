# help system — externalized docs + first-launch bubble highlights (v0.1.7)

> Draft spec for review. Restructures how the `(?)` help affordance is
> stored and how it behaves on a project's first launch. Companion to the
> merirmaid/cacheawl plans. Nothing here is committed — red-line freely.

## Motivation (from the 0.1.7 planning round)

1. Help copy is hard to edit: it lives as a giant inline `HELP_DOCS`
   object of HTML strings inside `static/index.html` (~18 entries, from
   line ~6905). Editing means hand-escaping HTML inside a 15k-line file.
2. Only **3 of ~18** authored help docs are actually wired to a `(?)`
   bubble (`paradigm-active`, `roles`, `skills`). The rest — cacheawl,
   merirmaid, wikisink, rness, io, knowledge, AGENT.md, MOTIVATION.md,
   requests, policies, paradigms, mode-system — are written but attached
   to nothing.
3. The default skills/roles/paradigms lists inside the help text are
   hand-written comma-separated prose that drifts out of sync with what's
   actually installed.
4. New users don't discover the `(?)`s. We want the bubbles lit up on a
   project's first launch, then reverting to the quiet hover behavior
   once each has been seen.

## Design decisions (pinned 2026-07-21, do not re-litigate)

### 1. Help content moves to one combined markdown file

`enough/static/help-docs.md`, served statically, fetched once on load.
The inline `HELP_DOCS` object is replaced by a parse of this file.

Structure — one `##` section per bubble id, with three `###`
subsections. `ideas` is a real bulleted list:

```markdown
## cacheawl
name: cacheawl
path: ~/enough/cacheawl/

### what
the machine-global store of *cacheboxes* — top-level folders holding
text you want to keep forever, or cached replicas ingested from a path,
a website, or wikipedia. shared across every project, hidden from project
trees. inline <code>HTML</code> and [links](https://…) still allowed.

### how
open cacheawl mode from the topbar for the two-pane view …

### ideas
- ingest a docs site so the agent can work from it offline.
- move a finished artifact into a cachebox to keep it reachable everywhere.
- {{skills-list}}   <!-- token, see §3 -->
```

- The `name:` / `path:` lines directly under the `##` heading carry the
  title and path shown in the viewer (today's `doc.name` / `doc.path`).
- Everything renders through the **existing** `renderMarkdown()`
  (`index.html:10367`) — no new parser vendored. Inline HTML passes
  through as it does elsewhere, so the current rich links/`<code>` survive
  the migration verbatim.
- A tiny loader splits the file on `^## ` headings into
  `{id → {name, path, what, how, ideas[]}}`, reproducing today's
  `HELP_DOCS` shape so `helpDocToHtml()` / `openHelp()` are unchanged.

### 2. Every authored doc gets a bubble

Wire all `HELP_DOCS` ids to a real affordance. Sidebar sections get a
`data-help` attribute (as `paradigm`/`roles`/`skills` do today); topics
that aren't sidebar sections hang their `(?)` off the relevant chrome:

| bubble id | anchor |
|---|---|
| `paradigm-active` | sidebar `paradigm` head *(exists)* |
| `roles` | sidebar `roles` head *(exists)* |
| `skills` | sidebar `skills` head *(exists)* |
| `requests` | sidebar `requests` head |
| `rness` | sidebar `rness` root row |
| `knowledge`, `io`, `policies`, `paradigms` | their sidebar tree rows |
| `agent-md`, `motivation-md` | their sidebar tree rows |
| `cacheawl` / `infoworld` | the topbar **cacheawl** button |
| `merirmaid` | the merirmaid-mode toolbar |
| `wikisink`, `project-wiki`, `wiki-comments` | the 🚰 button / wiki reader chrome |
| `mode-system` | the read/edit mode top-right icon |

(Exact anchors are the implementer's call during the index.html wave;
the contract is: every id is reachable and participates in §4.)

### 3. Default skills/roles/paradigms lists are auto-generated

The help text uses tokens `{{skills-list}}`, `{{roles-list}}`,
`{{paradigms-list}}`. At render time the loader expands each token into a
bulleted list built from the **actual installed** items — the sidebar
already has this data (it renders those sections), so the expansion is
client-side, no new endpoint. Each bullet is `**name** — description`
pulled from the item's frontmatter. Adding/removing a skill updates the
help automatically; no hand-maintained prose.

## 4. First-launch bubble highlights

### Behavior

- On a project's **first launch** (rness instantiated anew — see
  `skeleton.py`), and only if the global setting (§5) is ON, every bubble
  id is seeded as **pending** in the project's state file (§6).
- While a bubble is pending, its `(?)` is shown **persistently** (a
  steady, gently-emphasized state — reuse `.help-trigger.shown` plus a
  `.pending` class for a subtle pulse), bypassing the 1s-hover gate.
- When the user **opens then closes** that bubble's help panel, its id is
  marked **viewed** (persisted via §6 endpoint). That bubble reverts to
  the existing quiet behavior: 1s hover → show, 5s after leave → fade
  (`_scheduleHelpShow` / `_scheduleHelpFade`, unchanged).
- Once all ids are viewed, the project is back to fully-quiet help.

### Frontend hooks

- On load, fetch the highlight state; for each pending id force its `(?)`
  visible and skip the hover timers.
- `closeHelp()` (or openHelp→close) marks the just-viewed id and POSTs the
  update, then relaxes that bubble to hover mode without a reload.

## 5. Global setting: "Highlight (?)s on new folder launch"

- A global (per-machine) toggle, **default ON**, surfaced in the UI-prefs
  modal (the ⚙/UI button) as a checkbox under the theme/font row.
- **Stored as a top-level key `help_highlight_on_new_project` in the live
  `ui.json`** (the existing ui-config file, `/api/ui-config`), NOT a new
  file — it rides the config that already exists. `_validate_current`
  rebuilds only `current` (theme/font), so the toggle lives at the top
  level to survive theme changes. Shipped in `defaults/ui-config.json`
  (default `true`); absent ⇒ treated as `true` by both the reader and the
  frontend. `skeleton._help_highlight_default()` reads it at instantiation.
- Toggling it OFF affects **future** first-launches only; it does not
  clear an existing project's pending highlights.

**Implementation note (as shipped):** the highlights section stores the
sentinel `all` on first launch rather than an enumerated id list — the
backend doesn't know the help id set (it lives in `help-docs.md`, a
frontend asset). The frontend expands `all` → `Object.keys(HELP_DOCS)`,
and as each bubble is viewed it POSTs the reduced **explicit** list back.
Endpoints: `GET /api/help/highlights` → `{pending: [...] | "all",
highlight_on_new_project}`, `POST /api/help/highlights {pending: [...]}`.

## 6. The multipurpose `rness/active-paradigm` file

Today it's a plain one-line file (`default\n`) read via `.splitlines()[0]`
(`prompt.py:get_active_paradigm`). It becomes markdown, multipurpose:

```markdown
# Active paradigm
default

# Help bubble highlights
<!-- ids still pending; removed as each is viewed. empty = all seen -->
- skills
- roles
- paradigm-active
- cacheawl
- merirmaid
…
```

- **Filename unchanged** (`rness/active-paradigm`, no extension) so the
  server hide-list, the `_PROJECT_LOCAL_FILES` pointer, and skeleton
  back-fill keep working untouched. Content is markdown regardless of
  extension.
- `get_active_paradigm()` reads the first non-heading, non-blank line
  under the `# Active paradigm` heading. **Back-compatible**: a legacy
  bare `default\n` still parses (no heading → first line is the value).
- `set_active_paradigm()` rewrites only the paradigm value, preserving the
  Help-bubble-highlights section.
- New helpers `get_help_highlights()` / `mark_help_viewed(id)` read/write
  the second section. A small endpoint (e.g. `POST /api/help/viewed`
  `{id}`) lets the frontend persist a view.
- **Hidden everywhere**: already hidden from the project tree
  (`server.py` hide-list, line ~111). Add it to the **cacheawl** project
  pane's hide filter too, so it never shows in the split view.
- Skeleton seeds the file at instantiation: `# Active paradigm\ndefault`
  plus a `# Help bubble highlights` list of all bubble ids **iff** the
  global setting is ON (else an empty highlights section).

## Migration / back-compat

- Existing projects with a bare `active-paradigm`: on next
  ensure-skeleton pass, upgrade in place to the markdown form, preserving
  the current paradigm value. Do **not** retroactively seed highlights for
  already-established projects (they're not "new folders").
- The inline `HELP_DOCS` object is deleted from index.html once the loader
  reads `help-docs.md`; `helpDocToHtml`/`openHelp`/`closeHelp` stay.

## Out of scope for this wave

- Per-bubble "dismiss without viewing." A pending bubble stays pending
  until its panel is actually opened.
- Localizing help-docs.md (single-language for now).
