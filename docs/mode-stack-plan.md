# mode stack + topbar indicators + related 0.1.7 fixes

> Pinned spec for the July-2026 fix/feature round. Six items, one wave
> plan. Companion to [merirmaid-plan.md](merirmaid-plan.md),
> [cacheawl-plan.md](cacheawl-plan.md), [help-system-plan.md](help-system-plan.md)
> (whose first-launch-highlight design item 5 below SUPERSEDES).
> Implementation agents: treat the "Decisions" sections as contract;
> anything marked *implementer's choice* is yours.

The six items:

1. **3D icon buttons** — a subtle gray gradient layered over every square
   icon-button chip.
2. **Active-mode indicator redesign** — bar-height delineated squares on
   the titlebar background, not button chips.
3. **The mode STACK** — closing a mode returns to the mode it was opened
   over (with its state intact), not to the chat home; multiple
   indicators in the topbar; read/edit overlays any mode.
4. **Read/edit face toggle relocation** — off the topbar indicator, onto
   dedicated buttons in the read/edit chrome.
5. **Help bubbles on/off** — hover-reveal removed; one per-project
   toggle, default on.
6. **Girraph → merirmaid** — user-initiated linked mirror diagram of a
   girraph, regenerated automatically thereafter.

All frontend work is in `enough/static/index.html` (serialize agents on
it). Backend work (items 5+6) is `enough/{girraph,prompt,server,tools}.py`
and is parallel-safe against index.html work.

---

## 1. 3D icon buttons (CSS only)

Every square icon-button chip gets a vertical gradient **above the chip
background, behind the icon**: 50%-opacity mid-gray at the top fading to
transparent at the bottom.

```css
/* shared 3D lift for square icon chips */
background-image: linear-gradient(to bottom,
    rgba(128, 128, 128, 0.5), rgba(128, 128, 128, 0));
background-color: var(--btn-bg, var(--bg-raise));
```

Decisions:

- Mid-gray literal `rgb(128,128,128)` — theme-independent by design (user:
  "50% gray in any theme should work").
- Applies to: `.topbar .icon-btn`, the chat composer `.icon-chip` (mic /
  send), the wiki toolbar `.wt-icon`, the save-flyout `.save-choice`,
  `.mini-full-btn`, `.rt-mini-btn`, and any other **square chip painting
  `var(--btn-bg, var(--bg-raise))`**. Grep for that var to enumerate;
  add a shared class or a grouped selector block (*implementer's choice*)
  rather than repeating the gradient per-rule.
- Does NOT apply to: `.bare-toggle` (transparent by design), text
  buttons, the model badge, ribbons, and the NEW mode indicators of
  item 2 (they are deliberately not buttons).
- Keep `var(--btn-bg, var(--bg-raise))` as `background-color` — do not
  collapse into a single `background` shorthand that drops the fallback,
  and do not define `--btn-bg` in `:root` (see AGENT_GUIDE "What NOT to
  touch").
- If 0.5 alpha reads heavy against light themes during QA, tune down to
  taste (floor 0.30) — record the final value in this doc.
  **QA outcome:** 0.5 at the top edge read as a hard band on light
  themes; shipped as a two-stop ramp `rgba(128,128,128,0.42) → 0.10 at
  62% → 0` which keeps the 3D lift on both light and dark themes.

## 2. Active-mode indicator redesign

The current indicator (30×30 `--btn-bg` chip, item at topbar far right)
becomes a **delineated bar-height square on the titlebar background**:

- Size: the full topbar height (36px) square, flush with the bar's top
  and bottom edges (no vertical margin; it visually interrupts the bar).
- Background: `var(--bg-alt)` (the topbar's own background) — i.e. NO
  chip, NO border-radius, NO `--btn-bg`, NO item-1 gradient.
- Delineation: 1px **left and right** edge lines in literal 50% gray
  `#808080` (works on any theme). No top/bottom lines.
- Icon: fills the square minus ~2px padding (~32px vs the ~22px icons
  on button chips — the "~2x" the user asked for).
- The exit `ribbon-redx` keeps its exact current treatment: rotated 90°
  CW, hanging off the **left edge** of the square, vertically centered,
  overlapping the square's left edge by ~6px.
- The indicator is **not a button visually**; interactivity is defined
  by item 3 (raise-to-top for buried modes; the top-of-stack indicator
  is inert — no hover face-toggle anymore, see item 4).

## 3. The mode stack

### Problem

`setActiveMode` enforces exactly one live mode: registering a mode
supplants (tears down) the previous one, so closing ANY mode lands on
the chat home. Users think of modes as stacked windows: cacheawl →
girraph → read/edit should unwind in that order, each mode reappearing
exactly where it was.

### Data model (index.html)

Replace the single `ACTIVE_MODE` with an ordered stack:

```js
let MODE_STACK = [];   // bottom … top; each entry:
// { name, icon, iconTitle, exitTitle, onExit, rootId }
```

- `name` is unique in the stack — one live instance per mode
  (`readedit`, `girraph`, `merirmaid`, `cacheawl`, `wikisink`).
- `rootId` is the mode's full-frame overlay element id
  (`review-mode`/`edit-mode` pair for readedit, `girraph-mode`,
  `merirmaid-mode`, `wiki-mode`, `cacheawl-mode`). The stack manager
  owns each root's inline `z-index`; modes keep owning their `.open`
  class and internal DOM/state.

API (keep the old names as thin wrappers so stray call sites fail soft,
but update all call sites):

- `modePush(name, opts)` — replaces `setActiveMode`. If `name` is
  already in the stack: update its opts and **raise** it (the caller has
  already re-targeted its content — e.g. `enterGirraphMode` on a new
  file resets `GIRRAPH_STACK` itself). Else push on top. **No supplant
  teardown of the previous top** — it stays live underneath.
- `modeRemove(name)` — replaces `clearActiveMode` in every mode's exit
  function. Splices the entry (any depth), re-applies z-order, renders
  the indicators. Stack empty → chat home (identical to today's
  cleared state).
- `modeRaise(name)` — move to top + re-apply z-order. Used by indicator
  clicks.
- `modeTop()` — top entry or null (esc handler, guards).

Z-order: the full-frame overlays all currently sit at `z-index: 30`.
The manager assigns `z = 30 + index` inline on each entry's root(s).
Everything intentionally above the modes (confirm overlay 950+, modals
1000+, label editor, etc.) stays above `30 + 5`.

Supplant machinery (`onSupplant`, the auto-teardown in `setActiveMode`)
is **deleted**, including readedit's `_teardownReadEdit`-as-onSupplant
wiring — buried modes now legitimately keep their buffers and state.

### Behavior decisions

- **Opening a mode stacks it** on top of whatever is open, from
  anywhere: tree clicks, topbar buttons (wikisink/cacheawl), cacheawl
  tiles, girraph/merirmaid ref navigation, mm-node-menu, highlight
  navigation. The chat home is simply the empty stack.
- **Same mode, new target → bounce in place**: `openReadEdit` on a new
  path keeps its current dirty-buffer discard prompt, then replaces the
  readedit entry's content (entry keeps its stack position, raised to
  top). Same pattern for girraph→girraph, merirmaid→merirmaid,
  including read/edit → read/edit with a different document ("bounce
  from read/edit to read/edit"). Wikisink/cacheawl re-entry from their
  topbar buttons: if already stacked, just `modeRaise`.
- **Closing** (ribbon / esc / in-mode exits): runs that entry's
  `onExit` (readedit keeps its async dirty prompt), which calls
  `modeRemove(name)`. The reveal is free — the mode below never tore
  down. Closing a **buried** entry via its indicator ribbon is allowed
  (same path; no raise first).
- **Esc** targets `modeTop()` only.
- **Indicators**: one item-2 square per stack entry, rendered into the
  topbar right half (`#mode-stack` container replacing `#active-mode`),
  **top-of-stack leftmost**, evenly spaced between the centered project
  title and the right edge (`justify-content: space-evenly` across the
  right half). Each square carries its own left-edge ribbon (closes
  that entry). Clicking a **buried** square raises it (`modeRaise`);
  the top square is inert (`cursor: default`).
- **Raise ≠ re-enter**: raising must not reload/reset the mode (no
  `enter*` call) — just z-order + indicator re-render. Modes whose data
  may be stale (cacheawl tree) can refresh on raise via an optional
  `onRaise` hook — cacheawl wires `caLoadTree()`, others omit.
  (*implementer's choice* on the hook name/shape.)
- **Read/edit over anything**: `openReadEdit` works over wikisink,
  cacheawl, girraph, merirmaid — the "project nav lock" era is over;
  the sidebar tree stays fully live in every mode (it already is —
  `_reSyncTreeGrey` and any leftover lock affordances get deleted).
  - **mini size over a full-frame mode**: `#preview` (the mini panel)
    gets an inline z-index of `31 + index-of-readedit-entry` while
    readedit is stacked (cleared when not), so the side panel floats
    over the underlying mode's full-frame overlay, which stays visible
    around it.
  - **mini ↔ full** (`reSetSize`) never changes the stack — the
    readedit entry just swaps which of its containers shows. The
    canonical chain works: cacheawl → girraph → mini read/edit → full
    read/edit → back to mini (girraph visible behind) → close (girraph)
    → close (cacheawl, hierarchy position intact) → close (chat home).
- **Chat pills / SSE**: each mode's chat tail mirrors keep working
  regardless of depth; no changes needed beyond not tearing modes down.
- The `help-viewer` ↔ mini-panel mutual exclusion in `openHelp` stays
  as-is.

### Known interactions to preserve (regression list for QA)

- Dirty edit buffer survives: open editor → dirty → open girraph from
  tree → girraph stacks → close girraph → editor still dirty. (Old
  behavior silently DROPPED the buffer via onSupplant — the new
  behavior is strictly better; the discard prompt still guards
  readedit-to-readedit bounces and readedit close.)
- Girraph breadcrumb descent (`GIRRAPH_STACK`) and cacheawl descent
  (`CA_*_SUB`) survive burial and reveal untouched.
- `applyReviewContrast()` runs on wikisink and full-read entry — verify
  a buried full-read still renders correctly when revealed after
  wikisink closes above it.
- `updateDocCounters()` keys off readedit state — counters should
  reflect the readedit entry whenever it exists, regardless of depth
  (acceptable v1 simplification: counters show whenever readedit is
  stacked).

## 4. Read/edit face toggle relocation

The topbar indicator no longer toggles the read/edit face (indicators
are not buttons; `onIconClick`/`hoverIcon` machinery is deleted from the
stack registry — the readedit indicator still swaps its FACE icon
read-eye/pencil via the existing `updateActiveModeIcon` equivalent,
`modeUpdateIcon(name, icon, title)`).

Dedicated face-toggle buttons instead, all calling `reToggleFace()`,
icon `readedit-switch`, title "switch to edit face" / "switch to read
face" (swap per current face):

- **full read**: in the review toolbar's `.rt-size` group, next to
  `#review-mini-btn` (the full2mini switcher). id `review-face-btn`.
- **full edit**: in `.edit-actions`, next to `#edit-mini-btn`. id
  `edit-face-btn`.
- **mini (both faces)**: in `.preview-header`, next to `#mini-full-btn`
  (the mini2full switcher). id `mini-face-btn`.

These are square icon chips → they GET the item-1 gradient treatment.

## 5. Help bubbles on/off

Hover-reveal and first-launch-highlight machinery are **removed**,
replaced by one boolean:

- **on** → every `[data-help]` row shows its `(?)` button,
  persistently. No hover timers, no fade, no `pending` class. Re-apply
  after every `htmx:afterSettle` (the existing re-light pattern).
- **off** → no `(?)` buttons at all.

Decisions:

- **Scope: per project folder, sticky across launches, default ON for a
  folder's first launch** (the user's "respect state globally per
  folder").
- **Storage**: the multipurpose `rness/active-paradigm` file's
  help-bubble section, repurposed. `prompt.py`:
  `get_help_bubbles(rness) -> bool` / `set_help_bubbles(rness, bool)`
  replace `get_help_highlights`/`set_help_highlights`. Legacy section
  content (`all` / id lists / empty / missing) all read as **on**
  (missing file too); the section now stores `on`/`off`.
  `seed_multipurpose_file` seeds on; its `highlight_all` parameter,
  `skeleton._help_highlight_default()`, and the ui.json
  `help_highlight_on_new_project` key are removed (stale key in user
  configs is ignored harmlessly).
- **Endpoints**: `GET /api/help/bubbles` → `{"enabled": bool}`;
  `POST /api/help/bubbles` body `{"enabled": bool}`. The two
  `/api/help/highlights` endpoints are removed (this frontend is the
  only consumer).
- **UI**: the ui-modal checkbox `#ui-help-highlight` ("highlight (?)s on
  new folder launch") becomes `#ui-help-bubbles` — label "help bubbles",
  title "show (?) help bubbles in the sidebar (saved per folder)".
  Checked state loads from / posts to `/api/help/bubbles`.
- Frontend deletions: `_scheduleHelpShow`, `_scheduleHelpFade`, the
  sidebar mouseover/mouseout delegation for `[data-help]`,
  `HELP_PENDING`, `loadHelpHighlights`, `applyHelpHighlights`,
  `markHelpViewed`, and the `.pending` CSS. `_makeHelpButton` stays (the
  on-state renderer); `openHelp` no longer calls `markHelpViewed`. The
  🗑 unsave hover affordance is UNRELATED — keep it.

## 6. Girraph → merirmaid

A girraph can be turned into a linked Mermaid diagram, once,
user-initiated; afterwards the link is permanent and the diagram is
regenerated automatically (mirror semantics, like cachebox mirrors).

### Backend (`girraph.py` + `server.py` + `tools.py`)

- `girraph.to_mermaid(g: Girraph, *, source_rel: str, char_limit: int = 48)
  -> str` — renders a full `.merirmaid` file text:
  - frontmatter: `merirmaid: 1`, `modality: mirror`,
    `kind: girraph-mirror`, `source: <project-relative girraph path>`,
    `node-char-limit: 48`, `generated: <iso timestamp>`.
  - body: `flowchart TD`. Sensible organization (*pinned*):
    - node shapes by type — issue `?` `{{…}}` hexagon, position `!`
      `([…])` stadium, support `+` `[…]` rect, objection `-` `[…]`
      rect, note `.` `(…)` rounded, nested girraph `@` `[[…]]`
      subroutine.
    - labels: the node's emoji sigil + text, hard-truncated with `…` to
      `char_limit`; Mermaid-escaped (quote wrapping).
    - classDefs coloring support green-ish / objection red-ish (stroke
      only — fills stay theme-neutral).
    - tree edges `-->`, cross-links `-.->`.
    - `click <id> "<path>"` for every `ref:` target and for `@` nested
      girraphs — the existing merirmaid-mode click-interception then
      makes refs navigable.
  - node ids in the diagram = girraph ids (stable, already unique).
- Sibling path rule: `<dir>/<base>.merirmaid` next to
  `<dir>/<base>.girraph`. Link exists ⇔ that file exists AND its
  frontmatter says `kind: girraph-mirror` (cheap sniff).
- `POST /api/girraph/merirmaid` body `{"path": "<girraph path>"}` →
  creates the sibling (409 if a non-girraph-mirror file already claims
  the name), returns `{"merirmaid": "<path>"}`. Path resolution through
  `_resolve_project_path` (so `cacheawl:` girraphs work and traversal
  is checked).
- `GET /api/girraph` response gains `"merirmaid": "<path>"|null` — the
  frontend's link/button state, no extra round trip.
- **Regeneration**: after every successful girraph mutation through ANY
  door — the four `/api/girraph/*` node ops in server.py and the girraph
  tool runners in tools.py — regenerate the sibling IF it exists (same
  sniff), inside the existing `path_lock`. One shared helper
  (`girraph.refresh_mirror(path)` → regenerates or no-ops;
  *implementer's choice* where the call lands, but exactly one code
  path). External text-editor edits to the girraph do NOT auto-refresh
  (acceptable v1: next harness mutation catches up — same reconcile
  philosophy as cacheawl).
- The generated file lives in the project (or cachebox), `modality:
  mirror` → merirmaid mode renders it read-only. Under `~/enough/cacheawl/`
  the existing mirror write-guard applies to it automatically; in-project
  copies are agent-writable in principle but get clobbered on next regen
  — document in the girraph-merirmaid skill later, not this wave.
- Tests (local gitignored `tests/`): converter output (shapes, escaping,
  truncation, cross-links, click lines, round-trip against `loads`),
  endpoint create/409, regen-on-mutation, legacy help-bubble migration
  reads (item 5).

### Girraph-mode UI

- Toolbar gets a merirmaid-logo button (`data-icon="merirmaidmode"`,
  square chip → item-1 gradient), immediately after the `gp-mode-icon`,
  i.e. the view's upper left:
  - **no link yet** → "add merirmaid" state (title "create a linked
    merirmaid diagram of this girraph"). Click → POST, then open the
    new diagram in merirmaid mode (stacks atop girraph per item 3).
  - **link exists** → "open merirmaid" state (title "open the linked
    merirmaid diagram"). Click → `enterMerirmaidMode(path)` (stacks).
  - State comes from the `GET /api/girraph` `merirmaid` field, refreshed
    on every `renderGirraphTop()`; applies to whichever girraph is at
    the top of the descent stack.

---

## Wave plan / QA

- **Wave A (backend, parallel-safe)**: items 5-backend + 6-backend +
  tests.
- **Wave B (index.html, serialized)**: items 1 + 2 + 3 + 4 (one agent —
  they're one interlocking change to the same regions).
- **Wave C (index.html, after B)**: items 5-frontend + 6-frontend.
- QA between waves in a scratch env: fresh project dir +
  `ensure_skeleton()` before `create_app()`, ALL env hooks overridden
  (`ENOUGH_CACHEAWL_ROOT`, `ENOUGH_WIKISINK_CONFIG`, `ENOUGH_UI_CONFIG`,
  `ENOUGH_INFOWORLD_ROOT`) — never against live `~/enough`.
- `uv run pytest tests/ -q` green before done. Nothing committed until
  user review.

Canonical end-to-end QA script (the user's own scenario): cacheawl →
open girraph from a box → add merirmaid → merirmaid stacks → close →
girraph → open notes doc mini read/edit over it → expand to full →
back to mini (girraph visible behind) → close read/edit → girraph →
close girraph → cacheawl exactly where it was → close cacheawl → chat
home. Indicators throughout: correct order (top leftmost), even
spacing, raise-on-click for buried entries, per-square ribbons close
the right entry.
