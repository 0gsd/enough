# enough — Agent Guide (v0.3.5)

> **Audience:** another LLM agent (e.g. a Claude Code session) helping a
> human modify their local `enough` install. Not for end-users — for an
> end-user-facing intro see the [README](../README.md), and for the full
> user manual see [docs/HELP_CENTER.md](HELP_CENTER.md) (served in-app
> via the help-center reference mode). This doc is dense,
> file-path-heavy, and assumes you can read Python and call tools.
> The historical planning docs (girraph-plan, girraphs, merirmaid-plan,
> cacheawl-plan, mode-stack-plan, help-system-plan) were folded into
> this guide and removed from the repo — don't go looking for them; the
> load-bearing content is in the sections below.
>
> **A word about the word "agent".** Inside enough the assistant is the
> **chief readvisor** and the personas the user switches on are
> **readvisors** — "agent" is not the product's vocabulary any more
> (0.3.5; see "Readvisors" below). This guide keeps saying *agent* for
> exactly one thing: **you**, the external coding agent reading it. Where
> a sentence below means the thing that answers in the chat, it says
> readvisor. Identifiers do not move: `AGENT.md`, `MOTIVATION.md`,
> `AGENT_GUIDE.md`, `--accent-agent`, `/api/roles*`, `#roles-list`,
> `{{roles-list}}` and every `*_role*` Python name are unchanged on
> purpose — only folder names migrated (`roles/` → `readvisors/`).

`enough` is a **personal language system** powered by a local LLM. It runs
on the user's machine, exposes its UI at `http://127.0.0.1:3456`, and lets
the user shape their readvisors' behavior by editing markdown files. The
home surface of a project is a **composure** — the canvas at the base
layer (see "Composures" below) — with the conversation alongside it in the
**readvisor panel**, a third grid column on the right. The assistant in
that panel is the **chief readvisor**, named `Ed` out of the box and
renamable per machine. Started with `--home` instead of a project enough
serves the **home screen** — the project list every launch begins at (see
its own section below). A fifth optional model slot routes through
OpenRouter when the user has explicitly enabled it; everything else stays
local. An optional **wikisink** subsystem puts an offline copy of
Wikipedia on the machine (see its own section below and
[docs/WIKISINK.md](WIKISINK.md)).

This guide tells you what files are involved in what, how the runtime
flows, what to edit when the user asks you to do common things, and the
patterns that will trip you up if you don't see them coming.

---

## Layout on disk

Three locations that matter:

| Path | What it is | Authority |
|---|---|---|
| `~/enough/` | The global install. Cloned from the repo by `bootstrap.sh`. Contains `defaults/` (templates that get copied / symlinked into every project), `cacheawl/` (the machine-global file store — see below), `readvisors/` (the user's own readvisors — see the row below), and the Python source. (The old `infoworld/` library is dissolved into `cacheawl/` on first 0.1.6 launch.) | Edit these to affect every project. |
| `~/enough/config/` | User-global JSON config. `broker.json` (toggle states), `models.json` (active local model), `openrouter.json` (cloud-slot metadata, **no api key**), `ui.json` (theme/font/`ui_language`/**`chief_readvisor_name`** — the chief readvisor's name is one per machine, like the theme), `orchestrator.json` (auto-reset config), `wikisink.json` (wikisink install registry + watch/override registries + reading state), `desktop.json` (desktop-shell launch prefs: reopen toggle, last/known projects, onboarding state — shared-visible with the CLI, written by `desktop/src-tauri/src/config.rs`), `extras.json` (which optional dependency groups are installed — read by Python, bash **and** Rust; see "Document conversion"), `projects.json` (the home screen's project registry — see "The home screen"), and the transient `.home-open` handoff file. | Edit per-machine settings. |
| `~/enough/readvisors/` | The **user-global** readvisors source (0.3.5), seam **`ENOUGH_READVISORS_ROOT`**, resolved by `skeleton.user_readvisors_root()`. **Never auto-created** — a machine that never forged a readvisor carries no empty folder. It exists because a desktop build's `defaults/` is sealed inside the `.app` and is not writable, so the `readvisory` skill's `install_readvisor` needs somewhere to put a global one. Each entry is `<name>/AGENT.md` + `MOTIVATION.md`, symlinked into every project by the populator. | Edit to affect every project on this machine, including .app installs. |
| `~/enough/wikisink/` | Default wikisink location: the user's wikisink *data* (comments, overlays, preserved articles, rankings, run state) and — unless pointed elsewhere — the base `.zim` archive(s). Archives can live anywhere, external drives included; several installs can be registered at once. Hidden from the file-manager tree. | Managed via the 🚰 UI; don't hand-edit. |
| `~/enough/cacheawl/` | The machine-global **cacheawl** store: root-level folders are *cacheboxes* (plain kept-forever text, or cached replicas ingested from a path/URL/wikisink). Global wiki saves land in the `wiki/` box; the dissolved infoworld folders become the `personal`/`public`/`wiki` boxes. Overridable via `ENOUGH_CACHEAWL_ROOT`. Hidden from every project's file tree. | Managed via the cacheawl mode UI + the readvisors' cachebox tools; sidecars are backend-owned. |
| `<project>/rness/` | The per-project skeleton. Symlinks back into `~/enough/defaults/` for shipped paradigms/skills/policies/**readvisors** (and into `~/enough/readvisors/` for the user's own); per-project copies of `AGENT.md`, `MOTIVATION.md`, `active-paradigm`, `project.json`; per-project state in `io/`, `requests/`, `knowledge/`. Composure-round additions: **`rness/readvisors/`** (was `roles/`, migrated by `skeleton._migrate_roles_to_readvisors`), **`rness/io/composure/`** (where new `.comp` files land — in `_EMPTY_DIRS`, so it is back-filled on every launch), **`rness/composure-forms/`** (project forms; **not** in `_EMPTY_DIRS` — created on the first save-as-form) and **`rness/knowledge/councils/`** (exported council transcripts, created by `council.py` on the first conclude). | Edit to affect just this project. |
| `<dir>/.<name>.comp.comments.json` | A composure's comments sidecar, beside the `.comp` it belongs to. Backend-owned, hidden from the tree by the leading dot, carried along by `composure.move_sidecars()` on a rename. Both write doors refuse it by name. | Managed via the composure comment endpoints; don't hand-edit. |

Plus one **off-disk** location: the **OS keyring** (macOS Keychain /
Linux Secret Service / Windows Credential Manager), service
`enough-broker`, account `openrouter-api-key`. The OpenRouter api key
lives there and ONLY there. The on-disk `~/enough/config/openrouter.json`
holds metadata (`enabled`, `model_id`, `key_in_keychain`,
`last_verified_at`, `last_verified_ok`, `last_error`) but never the key
value. See "OPRO-API" below for the full architecture.

---

## Code map

Every Python module in `enough/`:

| Module | Lines | Role | Key entry points |
|---|---:|---|---|
| [enough/server.py](../enough/server.py) | ~4580 | FastAPI app: chat dispatch, SSE streaming, file tree, model modal, broker modal, auto-reset orchestration, all `/api/*` endpoints (including `/api/wiki/*`, `/api/models/*`, `/api/skills*` — whose toggle is guarded by `skillaudit` — `/api/roles*` + `/api/readvisors/remove` + `/api/readvisor/chief`, the desktop-gated `POST /api/shutdown`, and `/api/home/*` + `/api/close-project`; see the `ENOUGH_DESKTOP*` note under "What NOT to touch"). Mounts the composure and council routers in one `include_router` call each. Also owns the **mode boundary**: `create_app(home=…)`, the `ModeGate` ASGI middleware, `HOME_PATHS`/`HOME_PREFIXES`, and the `data-mode` marker templated into `/`. | `create_app()`, `_drive_message()`, `ModeGate`, `HOME_PATHS`, `HIDDEN_TREE_PATHS`, `_readvisor_origin()`, `request_process_exit()` / `request_process_exec()` (module-level so tests can swap them), `HANDOFF_EXIT_CODE`, all `@app.{get,post}` handlers |
| [enough/prompt.py](../enough/prompt.py) | ~1660 | Assembles the system prompt from `rness/` on every turn (no caching). Also owns skill/readvisor/paradigm enumeration + toggle-state helpers, the generated identity preface, the chief readvisor's name, and the gated tool-doc blocks. `set_skill_enabled()` is the dumb `.disabled` writer — the *guarded* door for skill toggles is `skillaudit.set_skill_enabled_guarded()` (see "Skill trust"). | `assemble_system_prompt(project_dir, readvisors=, profile=)`, `readvisor_identity()`, `identity_preface()`, `chief_name()` / `valid_chief_name()` / `CHIEF_NAME_DEFAULT` / `CHIEF_NAME_MAX`, `readvisor_shape()`, `tool_instructions()`, `TOOL_INSTRUCTIONS` / `COMPOSURE_TOOL_INSTRUCTIONS` / `READVISORY_TOOL_INSTRUCTIONS`, `convert_instructions()`, `list_skills()` / `set_skill_enabled()`, `list_roles()` / `set_role_enabled()` / `_readvisors_dir()`, `list_paradigms()`, `get_active_paradigm()` / `set_active_paradigm()` |
| [enough/composure.py](../enough/composure.py) | ~3060 | The composure core (0.3.5): the `.comp` HTML5 parser/serializer, the sanitizer, markdown ⇄ rich text, the node-level op vocabulary (the only way content changes), `place_module`/`arrange`/`estimate_height`, the JSON document model the canvas renders from, the comments sidecar, the forms registry, the outline→composure converter, and the write-door denial. **No FastAPI import** — exercisable with no web layer. See "Composures". | `loads()` / `dumps()`, `model()`, `apply_ops()`, `path_lock()`, `OP_NAMES` / `SOURCES` / `MODULE_TYPES` / `BG_SWATCHES` / `SHIPPED_FORMS` / `CAPS`, `place_module()`, `estimate_height()`, `write_denial()`, `comments_path()` / `load_comments()` / `move_sidecars()`, `parse_outline()` / `outline_ops()` / `from_outline()`, `ComposureError` |
| [enough/composure_api.py](../enough/composure_api.py) | ~520 | HTTP translation only: `build_router(project_dir, resolve_path, emit)` → the `APIRouter` `create_app` mounts. Every `/api/composure*` route, the comments CRUD, `link-preview`, `webframe/refresh`, and the `composure` SSE event. | `build_router()`, `EVENT` |
| [enough/composure_tools.py](../enough/composure_tools.py) | ~490 | The nine readvisor composure tools; `register()` adds them to `tools._DISPATCH` / `_TRACE_TOGGLE` at `tools` import time. Gated by `composure_enabled`. | `TOOL_NAMES`, `register()`, `run_read_composure()` … `run_composure_from_outline()`, `CACHE_OVER_CHARS` |
| [enough/council.py](../enough/council.py) | ~1340 | The council engine (0.3.5): the `composure:council` meta schema, participants + tints, the rotation, the per-participant token budget and the mechanical fold, the framing texts, statement cleaning, transcript export, and the `Council` class. **No FastAPI import.** One seam (`run_council_turn`) is where every test swaps the model out. | `Council`, `validate_meta()` / `validate_participants()` / `validate_output()`, `speakers()` / `next_speaker()` / `advance()`, `build_messages()` / `identity_for()` / `fold_summary()`, `share_for()` / `resolve_n_ctx()` / `probe_n_ctx()`, `run_council_turn()`, `turn_in_flight()` / `busy_paths()` / `reset_runtime()`, `CTX_CLOUD` / `FOLD_AT` / `MIN_TRANSCRIPT_TOKENS` / `MAX_PARTICIPANTS` / `MAX_ROUNDS_CAP`, `CouncilError` |
| [enough/council_api.py](../enough/council_api.py) | ~530 | `build_router(project_dir, resolve_path, emit, session)` → the `/api/council/*` router. HTTP translation, the two lock exclusions, and the `council` SSE event. | `build_router()` |
| [enough/readvisor_tools.py](../enough/readvisor_tools.py) | ~325 | `install_readvisor` (P7): the nine ordered refusals, the payload scan through a tempdir, the `.<name>.installing/` stage-then-rename write, and the `readvisors_changed` side effect. `register()` wires it into `tools._DISPATCH` at import time; gated by `readvisory_install`. | `TOOL_NAMES`, `register()`, `run_install_readvisor()`, `scan_documents()`, `shipped_names()` |
| [enough/skillaudit.py](../enough/skillaudit.py) | ~1040 | First-use audit of untrusted skills (0.2.2). Trust classification (symlink into *an* enough install's `defaults/skills/` = trusted — this install or a sibling one, since 0.2.7), the content fingerprint, the `verdict.json` sidecar, both audit passes (deterministic `payload_scanner.py` + a single non-streaming LLM completion), the in-flight registry, and the guarded toggle. Progress on the `skill-audit` SSE event. | `is_trusted()`, `fingerprint()` / `skill_fingerprint()`, `skill_state()`, `set_skill_enabled_guarded()`, `SkillAuditRefused`, `audit_skill()` / `audit_and_enable()`, `run_llm_audit()` (module-level test hook), `quarantine_untrusted()`, `trust_override()`, `read_verdict()` / `write_verdict()` |
| [enough/broker.py](../enough/broker.py) | ~440 | Broker config (toggles), trace journal writer, canned denial messages. New toggles auto-render in the broker pane via `/api/broker`. | `TOGGLES` tuple, `load_config()`, `is_enabled()`, `trace()`, `denial_*()` |
| [enough/tools.py](../enough/tools.py) | ~1745 | Tool runners (`read_file`, `write_file`, `shell`, `fetch_url`, `read_highlights`, `navigate_to_highlight`, `cloud_pipeline`, girraph ops, wiki tool wrappers), the tool-call XML parser, the dispatch table. Two import-time `register()` calls at the bottom fold in the composure and readvisor tools. `fetch_and_cache()` is the shared fetch pipeline `run_fetch_url` and the webframe refresh both render. | `_DISPATCH` (~line 1627), `_TRACE_TOGGLE` (~line 1656), `execute()`, `parse_tool_calls()`, `fetch_and_cache()`, `ToolResult.side_effects`, `_CLOUD_KEY_EXFIL_PATTERNS` |
| [enough/project_meta.py](../enough/project_meta.py) | ~300 | `rness/project.json`: the project's nice name + description, the `ui` block (`ui_scale`, `text_scale`, `readvisor_panel`) and the `composure` block (`launch`, `path`, `form`, `last`). Every reader gets a fully populated, validated view; a garbage value reads as the default rather than raising. | `load()`, `save()`, `save_ui()`, `save_composure()`, `touch_composure()` |
| [enough/convert.py](../enough/convert.py) | ~1395 | Document conversion (0.2.5): the format **registry** (`FORMATS`), engine probing + caching, twin/assets/manifest naming, the state machine, the job runner that drives the worker, export/sync/resolve, and the `pdf`-extra installer. Imports nothing heavy — docling and pandoc are only ever reached through `convert_worker`. See "Document conversion" below. | `FORMATS` / `formats_view()` / `engines()`, `pandoc_path()` / `typst_path()` / `docling_available()`, `twin_path()` / `assets_dir()` / `manifest_path()` / `pair_for()`, `state()` / `has_twin()`, `read_manifest()` / `write_manifest()`, `ConvertJobs`, `do_export()` / `sync_after_save()` / `resolve()`, `ExtraInstaller`, `installed_extras()` / `record_extra()`, `reset_engines()` |
| [enough/convert_worker.py](../enough/convert_worker.py) | ~840 | The out-of-process worker: `python -m enough.convert_worker`, one JSON job on stdin, NDJSON records on stdout, exit. pandoc is shelled out to; **docling runs in this process** — which is the whole reason the worker exists (torch must never be imported into the server). | `main()`, `_OPS` (`convert` / `export` / `prefetch`), `do_convert()` / `do_export()` / `do_prefetch()`, `_convert_docling()`, `_flatten_media()` / `_relink_docling_assets()` / `_normalize_images()`, `_Heartbeat`, `TWIN_FORMAT` |
| [enough/wikisink/](../enough/wikisink/) | ~2840 (pkg) | Local offline Wikipedia. `config.py` (install registry, schema v2 multi-install, data paths), `zim.py` (libzim reader, search, sanitize/rewrite), `download.py` (Kiwix flavor listing + resumable downloads), `overlay.py` (live-refreshed + preserved article stores), `comments.py` (per-article threads), `save.py` (save/read/unsave article folders + the clean HTML→markdown text pipeline), `update.py` (the "wikisink" update run), `rankings.py` (pageview snapshots), `report.py` (run report), `agent.py` (the four readvisor tool runners). | `config.load_config()` / `installs()` / `active_install()` / `unavailable_reason()`, `zim.get_article()` / `search()`, `download.DownloadManager`, `update.run_wikisink()` |
| [enough/cloud.py](../enough/cloud.py) | ~1030 | OpenRouter integration: keyring read/write, in-memory key cache, OpenAI-compatible streaming + non-streaming clients, health check, response caching to `rness/io/cloud-cache/`, the broker-driven `pipeline_run()`. | `set_api_key()` / `clear_api_key()` / `has_api_key()`, `_get_api_key_for_broker()`, `health_check()`, `chat_completion()`, `stream_chat_completion()`, `cache_completion()`, `pipeline_run()` |
| [enough/llm.py](../enough/llm.py) | ~120 | OpenAI-compatible client for the local llama-server. Streaming-only path for chat. | `stream_chat()`, `check_llm_reachable()` |
| [enough/supervisor.py](../enough/supervisor.py) | ~470 | Manages the local llama-server subprocess. Adopts an existing process if one's already up; spawns its own otherwise. Skips spawning entirely when the active model is `opro-api`. | `LlamaSupervisor`, `_resolve_startup_choice()` |
| [enough/models.py](../enough/models.py) | ~680 | Local-model registry (7 cute-named local models, defined in `defaults/models.json`; two carry separate MTP draft GGUFs, two carry a `llama_cpp_min_release` gate). Feasibility verdicts (RAM + free disk), `install-menu` CLI for bootstrap.sh. Selection state in `~/enough/config/models.json`. | `load_registry()`, `load_state()`, `save_state()`, `resolve()`, `all_models_view()`, `feasibility()`, `release_gate()`, `install_menu_rows()` |
| [enough/model_download.py](../enough/model_download.py) | ~395 | Resumable GGUF downloads for the in-app model manager: main file then optional MTP draft, ranged-GET resume off a `.part`, one active download per process, cancel-keeps-partial, delete. Backs `/api/models/{download,delete}/*`; progress on the `model-dl` SSE event. | `ModelDownloadManager` (`start` / `cancel` / `delete` / `state`), `pending_phases()`, `partials()` |
| [enough/skeleton.py](../enough/skeleton.py) | ~1015 | Creates `rness/` for new projects (copies from `defaults/`), syncs global skills/**readvisors**/paradigms on every launch via dedicated populators, runs migrations. `_populate_skill_symlinks` also heals materialized copies of shipped skills (a byte-identical real dir left by a cloud-sync/dereferencing copy is swapped back to a symlink — 0.2.8) and calls `skillaudit.quarantine_untrusted()` — untrusted skills default OFF. `_populate_role_symlinks` walks **two** global sources (user-global then shipped) and re-aims managed links; `_migrate_roles_to_readvisors` renames `rness/roles/` in place (0.3.5). | `ensure_skeleton()`, `resync_globals()`, `_SKELETON_PLAN`, `_PROJECT_LOCAL_FILES`, `_EMPTY_DIRS`, `_populate_skill_symlinks` / `_populate_role_symlinks` / `_populate_paradigm_symlinks`, `user_readvisors_root()` / `shipped_readvisors_root()` / `_readvisor_sources()`, `_migrate_roles_to_readvisors()`, `cloud_sync_provider()` |
| [enough/footnotes.py](../enough/footnotes.py) | ~420 | Footnote surgery for in-progress markdown (0.2.7): parse/renumber/insert over standard `[^n]` refs + a terminal definitions block. Pure functions, offset-stable code-masking (fences + inline spans blanked to NULs), numeric labels managed, named tolerated, orphan defs never touched. `tests/test_footnotes.py` doubles as the spec for the `fn*` JS mirror in index.html. | `parse()`, `renumber()`, `next_number()`, `insert_at()`, `definitions_span()`, `REF_RE` / `DEF_RE` |
| [enough/paginate.py](../enough/paginate.py) | ~920 | Pagination (0.2.7): options schema + named size table, output naming (`name-YYYY-MM-DD.pdf` + `-1`/`-2`), the `.typ` surgery (pandoc-template split, balanced-bracket `#footnote[...]` extraction, endnote reflow, option preamble), pure 2-up/booklet imposition math, bundled-fonts lookup, and the PDF source-attachment probe that powers unpack-on-import. Heavy lifting (pandoc/typst/pypdf compile) runs in `convert_worker.do_paginate`. See "Pagination" below. | `validate()`, `sizes_view()` / `page_size_mm()`, `output_pdf()` / `pages_dir()` / `viewer_manifest_path()`, `fonts_dir()` / `font_paths()`, `embedded_source()` / `has_embedded_source()`, `sheet_order()` / `slot_rect()`, `split_template()` / `extract_footnotes()` / `place_endnotes()` / `preamble()` / `build_typ()`, `status()` / `run_paginate()`, `PaginateError` |
| [enough/highlights.py](../enough/highlights.py) | ~280 | Review-mode color highlights (yellow/green/blue/pink) stored in per-doc `.<filename>.highlights.json` sidecars. Tools `read_highlights` and `navigate_to_highlight` consume them. | — |
| [enough/girraph.py](../enough/girraph.py) | ~885 | The girraph primitive: parser/serializer for the plain-text `.girraph` IBIS format, node-level ops (the only way content changes), ASCII tree renderer, per-path write locks. Agent tools and UI endpoints both call through here. | `loads()` / `dumps()`, `add_node()` / `update_node()` / `link_nodes()` / `remove_node()`, `ascii_render()`, `path_lock()` |
| [enough/cacheawl.py](../enough/cacheawl.py) | ~1470 | The cacheawl store: cachebox CRUD, path/URL/wikisink **ingest**, the `_cachebox.merirmaid` mirror generator + reconcile, the mirror/sidecar write-guards, transfer (copy/move), and the launch-time `infoworld` migration. Root is `~/enough/cacheawl/` (or `ENOUGH_CACHEAWL_ROOT`). Owns everything under the store; nothing else writes there. Since 0.2.5 it also exports the generic folder→flowchart walker `home.py` builds project maps with. | `root()`, `create_cachebox()` / `list_cacheboxes()` / `cachebox_tree()`, `run_ingest()`, `regenerate_mirror()` / `reconcile()` / `reconcile_all()`, `folder_flowchart()`, `mirror_write_denial()`, `migrate_infoworld()` |
| [enough/home.py](../enough/home.py) | ~805 | The home screen (0.2.5): the project **registry** (`~/enough/config/projects.json`, seam `ENOUGH_PROJECTS_STATE`), the ¶/W/C counters ported from the top bar, the fingerprint cache (which since 0.2.8 also snapshots the `rness/project.json` display name/description so an unreachable folder's row keeps its nice name — live reads still win), seeding from the shell's `desktop.json` MRU (temp-dir paths — chiefly the wizard's `$TMPDIR/enough-onboarding` scratch — are refused, skipped, and pruned when the registry is durable, 0.2.8), the project map (via `cacheawl.folder_flowchart`), the add-guards + the osascript folder chooser, and both halves of the open/close handoff. Imports `server` **lazily, inside functions** — `server` imports `home` at module level, and that is the cycle-breaker. | `projects_state_path()` / `config_dir()` / `handoff_path()`, `read_registry()` / `save_registry()` / `register()` / `touch_opened()` / `set_hidden()`, `seed_from_desktop()`, `count_text()` / `fingerprint_of()` / `refresh_entry()` / `list_projects()`, `build_project_mirror()`, `check_addable()` / `add_project()` / `choose_folder()`, `write_handoff()` / `read_handoff()`, `exec_argv()` |
| [enough/logger.py](../enough/logger.py) | small | Stdlib logging setup. | — |
| [enough/static/index.html](../enough/static/index.html) | ~30200 | The entire frontend — HTML, CSS, vanilla JS, htmx. Single file. | model modal, broker modal, OPRO-API wizard + settings, file tree (+ option-click context menu), **the readvisor panel** (`#readvisor-panel`, the third `.layout` column — the conversation lives here now, not in a chat home pane), **the composure canvas** (`#composure` at the base layer: `COMP`, `COMP_TOOLS`, `COMP_MODULE_RENDERERS`, `COMP_FORM_BEHAVIORS`, ~126 `comp*` functions), **the composure base indicator + peek** (`html[data-comp-peek]`), SSE consumer, wikisink setup/installs modal + reader mode, the unified read/edit mode (mini ↔ full frame), girraph mode, merirmaid mode, cacheawl split-view mode, the home frame + project map + handoff overlays (gated on `IS_HOME` / `body[data-mode]`), SVG icon pipeline (`data-icon`/`iconSrc`), MODE STACK registry, confirmOverlay. **The five per-mode chat pills are gone** (review / edit / merirmaid / wiki / cacheawl) — there is one composer now, `#message` in the panel |

`defaults/` ships templates that get copied or symlinked into project
skeletons by `skeleton.py`:

- `defaults/AGENT.md`, `defaults/MOTIVATION.md` — root identity files (copied)
- `defaults/skills/<name>/SKILL.md` — bundled skills (symlinked)
- `defaults/paradigms/<name>.md` — bundled paradigms (symlinked)
- `defaults/readvisors/<name>/` — bundled readvisors, `AGENT.md` +
  `MOTIVATION.md` each (symlinked). Renamed from `defaults/roles/` in 0.3.5.
  They are not consultants you report from — every switched-on readvisor is
  part of one voice (see "Readvisors")
- `defaults/composure-forms/*.comp` — the five shipped composure forms
  (`blank` `cards` `scaffold` `journal` `council`). **Generated**, not
  hand-written — `scripts/gen_composure_forms.py` (`--check` verifies)
- `defaults/policies/*.md` — operating policies (symlinked)
- `defaults/models.json` — local-model registry template
- `defaults/openrouter-config.json` — cloud-slot metadata template
- `defaults/ui-config.json` — UI prefs template (theme, font, `ui_language`,
  `chief_readvisor_name` default `"Ed"`)

## The desktop shell

Top-level [desktop/](../desktop/) is the macOS app around the backend:
Tauri v2 + Rust, **no Node build step** — plain `cargo build` in
`desktop/src-tauri/` produces the whole binary (the shell's one static
page is embedded at compile time via `tauri::generate_context!`).
Toolchain: `brew install rustup` (keg-only — put
`/opt/homebrew/opt/rustup/bin` on PATH), `rustup default stable`. Rust
unit tests: `cargo test` in `desktop/src-tauri/`.

| File | Role |
|---|---|
| [desktop/src-tauri/src/main.rs](../desktop/src-tauri/src/main.rs) | window, native menu (five submenus: app · File · Edit · View · Window — `Reopen Last Project on Launch`, **File → Close Project ⌘W**, **View → Show Hidden Projects**), both quit paths, signal traps |
| [desktop/src-tauri/src/launch.rs](../desktop/src-tauri/src/launch.rs) | the launch **state machine** (0.2.5): boot a backend → park on it → decide what its exit meant → boot the next one, forever. Two pure, unit-tested decisions: `initial_target()` (home vs. the remembered project) and `after_exit()` (the exit-42 handshake). `known_projects` MRU upkeep; the folder picker survives only as the `home_broken` fallback |
| [desktop/src-tauri/src/backend.rs](../desktop/src-tauri/src/backend.rs) | spawn / health-probe / stop the uvicorn child (`POST /api/shutdown` → SIGTERM → SIGKILL ladder; child in its own process group). Carries `Mode {Home, Project}` — set by the spawn that wrote the argv, and the single source of truth for menu enablement. `enough_args()` is extracted so a test can look at it; the readiness probe is **mode-dependent** (home probes `/api/home/projects`, because a home server 404s `/api/project`) |
| [desktop/src-tauri/src/config.rs](../desktop/src-tauri/src/config.rs) | `~/enough/config/desktop.json` — tmp+rename writes, unknown-key round-trip. Also `enough_config_dir()` (follows `ENOUGH_PROJECTS_STATE`'s parent, mirroring `home.config_dir()`) and `ui_flag()`, the read-only peek at `ui.json` the View checkbox uses |
| [desktop/src-tauri/src/guards.rs](../desktop/src-tauri/src/guards.rs) | pre-flight refusals. **Deliberately mirrors** `enough/skeleton.py`'s `cloud_sync_provider` path list and the `~/enough` refusal in `enough/__main__.py` — touch one, touch the other (unit tests pin the list) |
| [desktop/src-tauri/src/http.rs](../desktop/src-tauri/src/http.rs) | ~60-line loopback-only HTTP/1.1 client (no client crate) |
| [desktop/src-tauri/src/bundled.rs](../desktop/src-tauri/src/bundled.rs) | where the bundle's payload lives (uv sidecar, llama.cpp, source snapshot), derived from `current_exe()` |
| [desktop/src-tauri/src/onboarding.rs](../desktop/src-tauri/src/onboarding.rs) | the first-run wizard's six IPC commands + the launch thread's wait loop |
| [desktop/src-tauri/build.rs](../desktop/src-tauri/build.rs) | stages the source snapshot (pyproject, uv.lock, `enough/`, `defaults/`, licenses, `docs/HELP_CENTER.md` — the single file, so gitignored plan docs never ship; without it the .app's help center 404'd pre-0.2.8) into the bundle on every `cargo build`; since 0.2.7 also stages `enough/static/enough-loader_1-2.svg` into `desktop/ui/` (gitignored there) so the loading screen can show it |
| [desktop/ui/loading.html](../desktop/ui/loading.html) | the shell's own page; static, zero Tauri IPC exposed to the enough UI. Since 0.2.7 it shows the real loader graphic (mascot + wordmark, the same SVG `enough/static/loader.html` uses) instead of the wordmark set in type |
| [desktop/ui/onboarding.html](../desktop/ui/onboarding.html) | the first-run wizard: welcome → environment → models → extras. Drives the *existing* `/api/models*` endpoints through the Rust proxy; shares nothing with `index.html` |
| [desktop/fetch-sidecars.sh](../desktop/fetch-sidecars.sh) | checksum-pinned fetch of the `uv` and `llama.cpp` release binaries (they are gitignored, not vendored) |
| [desktop/RELEASE.md](../desktop/RELEASE.md) | the user-executed sign / notarize / staple / verify checklist |

The shell talks to the backend it spawned through the `ENOUGH_DESKTOP*`
env gate (see "What NOT to touch"). The .app runs the source snapshot
sealed inside its own bundle — never `~/enough` — while state stays in
`~/enough` exactly as for a CLI install; **so a project created by the .app
symlinks its `rness/` skeleton into the .app**, the same way a CLI project
symlinks into `~/enough/defaults`. Full decision record: the
"Milestone 2a landed" and "Milestone 2b landed" blocks in
docs/tauri-plan.md (local planning doc, untracked).

---

## Platforms, and CI

enough runs on **macOS** (where it grew up) and **Linux** (backend port
landed 0.2.0, proven by CI, not yet claimed in the user-facing manual —
see the "Phase 3 landed" block in docs/linux-plan.md, a local planning
doc, untracked). The platform-specific surface is deliberately tiny and
enumerated here:

| Seam | File | Shape |
|---|---|---|
| llama-server lookup | [enough/models.py](../enough/models.py) `find_llama_server()` | `$ENOUGH_LLAMA_SERVER` → `~/enough/bin/llama-server` → PATH. Three installers depend on the order — see "What NOT to touch" |
| llama-server lookup, from shell | `python -m enough.models llama-server-path` | `llama_server.sh` asks through this CLI verb instead of running its own `command -v llama-server`, so the shell launcher can't disagree with the supervisor. Falls back to a bare PATH lookup only when `uv` is absent |
| absence-message wording | `models.install_hint(mac=…, linux=…)` + `LLAMA_CPP_{INSTALL,UPGRADE}_HINT` | the ONE place "how do I install this" branches. Used by `release_gate()`, `supervisor._launch`, `/api/transcribe`. Don't inline a new `sys.platform` check — add a call |
| who's on my port | [enough/supervisor.py](../enough/supervisor.py) `_find_pid_on_port()` | pidfile → `lsof` → `ss -ltnp` (Ubuntu 24.04 ships `ss` and no `lsof`) |
| reveal in file manager | [enough/server.py](../enough/server.py) `/api/reveal` | `open -R` (darwin) / `xdg-open` (linux) / 501. On Linux a **file** reveals as its parent folder — `xdg-open` has no `-R`, and opening the file would *launch* it |
| total RAM | `models.total_ram_gb()` | `sysctl hw.memsize` then `/proc/meminfo` (`models.MEMINFO`, monkeypatchable) |
| keyring | [enough/cloud.py](../enough/cloud.py) | Keychain / Secret Service / Credential Manager — the `keyring` library already handles it, and the error copy already names all three |
| installer | [bootstrap.sh](../bootstrap.sh) | `uname` → `platform_darwin`/`platform_linux` + `deps_darwin`/`deps_linux` function groups. Step numbers auto-increment (`STEP_N`) so the preludes can differ; both platforms land on ten. macOS = brew; Linux = a checksum-pinned llama.cpp release archive into `~/enough/bin/` and optional extras *printed*, never installed |

**CI: [.github/workflows/ci.yml](../.github/workflows/ci.yml).** One `test`
job on `[ubuntu-latest, macos-latest]`, triggered by push to `main` and
every pull request. Steps: checkout → setup-uv → `bash -n bootstrap.sh
llama_server.sh` → `uv sync --frozen` → `uv run pytest -q` → the boot
smoke → the bootstrap harness. Actions are pinned by commit SHA (bumping
one means bumping the SHA and its comment); `UV_PYTHON` is pinned to
3.12; `--frozen` means CI never re-resolves the lockfile. `bash -n` runs
on macOS too **on purpose**: macOS bash is 3.2, which is bootstrap.sh's
compatibility floor, so that job is the bash-3.2 linter for free.

Two of those steps are scripts you can and should run locally:

```bash
uv run python scripts/smoke_boot.py     # ~1.5s, 21 checks
bash tests/bootstrap_linux_harness.sh   # ~5s, 66 assertions (-v to watch)
```

- **[scripts/smoke_boot.py](../scripts/smoke_boot.py)** boots a real
  `python -m enough` subprocess against a scratch project and asserts:
  `/api/project` answers, the `rness/` skeleton got built, `GET /` serves
  the UI, `/api/models` lists 7 models each with a feasibility verdict,
  `total_ram_gb > 0`, `/api/llm-status` degrades gracefully (200,
  `ready: False`) with no llama-server anywhere, and `POST /api/shutdown`
  403s without the desktop token / 200s with it / exits within 30s. It
  redirects **every** `ENOUGH_*` seam *and `$HOME`* into a temp dir (the
  `$HOME` half is not optional — `broker.json`, `openrouter.json`,
  `orchestrator.json` and `~/enough/.llama-server/server.pid` have no env
  hook), and picks a free port for `--llm-url` so it can never adopt or
  kill the developer's real llama-server on 8080. Copy its `build_env()`
  when you need a scratch server of your own.
- **[tests/bootstrap_linux_harness.sh](../tests/bootstrap_linux_harness.sh)**
  runs the *real* bootstrap.sh with `uname`, `curl`, `git`, `uv`, `brew`,
  `ldconfig` and the checksum tools shimmed — seven scenarios covering the
  arch/Vulkan decision, the checksum-mismatch abort, a missing
  prerequisite, an idempotent re-run, and (scenario G) a **macOS
  no-regression check** pinning the ten step labels and the six brew
  formulae. Nothing is downloaded or installed. If you touch bootstrap.sh,
  run this.

**A clean `POST /api/shutdown` exits with wait status `-SIGTERM`, not 0.**
`server.request_process_exit()` SIGTERMs the process; uvicorn's
`capture_signals` re-raises the captured signal after the graceful
shutdown completes and default handlers are restored. Both are clean; a
non-zero *exit* code is not. Anything that reads the child's status needs
to accept both.

---

## The request lifecycle

When a user message arrives at `POST /api/chat`:

0. **The council exclusion, first.** If `council.turn_in_flight()` is true,
   `/api/chat` does **not** start a turn: it echoes the user's own bubble
   plus a `msg system` bubble explaining that a council is speaking, and
   returns. Queueing behind `session.generation_lock` would answer minutes
   later against a question the user stopped waiting on; the message text
   stays on screen, one copy-paste from being re-sent. (The mirror rule —
   a council control refused while a *chat* turn streams — is a 409 from
   the council router. See "Councils".)
1. The handler appends `{role: "user", content: ...}` to `session.history`
   and emits the bubble via SSE. The `turn_start` SSE event carries
   **`{"speaker": "<chief readvisor name>"}`** (`prompt.chief_name()`,
   read live) — the live bubble's byline comes from there, and the history
   renderer (`_render_turn_from_history`) uses the same value. The byline
   is always the *current* name, never the name at the time of the turn:
   one voice, one name, or a rename reads as two people.
2. `_drive_message` (in [server.py](../enough/server.py)) starts the tool
   loop, capped at `session.max_tool_iters` iterations.
3. On each iteration:
   - `assemble_system_prompt(project_dir)` rebuilds the system prompt
     **from disk** — a generated **identity preface**, `rness/AGENT.md`,
     `rness/MOTIVATION.md`, the project description + profile, the active
     readvisors, the active paradigm, policies, active skills, the tool
     instructions, the paradigm catalog. No caching; edits to any of these
     files land on the next message. Section order is: identity preface →
     Identity → Motivation → [Project Description] → [Project Profile] →
     [Active Readvisors] → Paradigm → [Paradigm Catalog] → [Policies] →
     [Skills] → [Current Intention] → Tools → Converted documents →
     Context → [Available Updates].
   - **The preface is generated, not shipped** (`prompt.identity_preface()`,
     template `_IDENTITY_PREFACE_TMPL`). It has to be: `rness/AGENT.md` is a
     *copy* the user owns, so nothing written into `defaults/AGENT.md` ever
     reaches an existing project. It names the chief readvisor and states
     the two standing rules — **"enough acts; readvisors speak"** (tool
     effects are narrated as things *enough* did) and **"you are one voice,
     sometimes made of several"** (switched-on readvisors are part of who
     the chief is this turn, not a panel to report from).
   - **The tool docs are gated** (`prompt.tool_instructions(project_dir)`):
     the always-on `TOOL_INSTRUCTIONS` core, plus
     `COMPOSURE_TOOL_INSTRUCTIONS` when `broker.is_enabled("composure_enabled")`,
     plus `READVISORY_TOOL_INSTRUCTIONS` when the `readvisory` skill is
     switched on in this project. Both gates **fail open** — an unreadable
     broker config leaves the composure block in, because a gate that hid
     working tools would be worse than a gate that costs a kilobyte. A
     project using neither pays what it paid before the composure round.
     `tests/test_prompt_weight.py` pins the budgets (core ≤ 17 500 chars,
     fully enabled ≤ 22 000) **and both directions of the coverage
     question**: every name in `tools._DISPATCH` is documented somewhere in
     the fully-enabled prompt, and every `<tool name="x">` example names
     something dispatchable. Headroom under the full budget is deliberately
     tiny, so the next round that adds a tool has to raise the number on
     purpose.
   - **Routing decision**: read `current` from `models.load_state()`. If
     `opro-api`, dispatch to `cloud.stream_chat_completion()`. Otherwise
     dispatch to `llm.stream_chat()` (the local llama-server). Both
     return async generators that yield content tokens and populate a
     `usage_sink` dict.
   - Stream tokens; emit `token` SSE events; accumulate into `buffer`;
     watch for a complete tool-call XML block via
     `tools.first_tool_call_end()`. If one appears, truncate at the end
     of the call, close the generator, and dispatch the tool.
   - Append `{role: "assistant", content: buffer}` to history.
   - **If cloud**: write `rness/io/cloud-cache/<timestamp>-<slug>.md`
     via `cloud.cache_completion()` (so a future local-LLM agent or a
     later session can read what happened).
   - If a tool call was found: execute via `tools.execute()`, get back a
     `ToolResult`, append its `render()` output as a user message
     (formatted as a `<tool_result>` XML tag), continue the loop.
   - If no tool call: end the turn.
4. Mid-loop pressure check: after each tool result, if pressure ≥
   `orchestrator.json`'s threshold, either auto-reset (write a
   continuation checkpoint to the active request file → wipe history →
   resume) or pause with a banner — depending on the orchestrator
   toggle.

The user's edits to identity files land on the **next message** because
the system prompt is reassembled every turn. There is no per-session
cache.

---

## Concepts ↔ files

| Concept | Per-project file(s) | Defaults template | Lives in system prompt? |
|---|---|---|---|
| Chief readvisor identity | `rness/AGENT.md` (copied) | `defaults/AGENT.md` | yes — under the generated identity preface |
| The chief's **name** | — (machine-global) | `defaults/ui-config.json` → `chief_readvisor_name`, default `"Ed"` | yes — interpolated into the preface |
| Motivation | `rness/MOTIVATION.md` (copied) | `defaults/MOTIVATION.md` | yes |
| Active paradigm | `rness/active-paradigm` (multipurpose markdown: paradigm name + help-bubbles state — see "What NOT to touch") | seeded by `prompt.seed_multipurpose_file()` | the active paradigm's full file, yes |
| Paradigms | `rness/paradigms/<name>.md` (symlink) | `defaults/paradigms/<name>.md` | the active one, yes |
| Skills | `rness/skills/<name>/SKILL.md` (symlink = shipped/trusted; a real dir = untrusted) | `defaults/skills/<name>/SKILL.md` | the toggled-on ones, yes |
| Skill audits | `rness/io/output/analyzer/audits/<skill>/<YYYY-MM-DD>-audit.md` + `verdict.json` | none — written by `skillaudit.py` or by analyzer's `audit` mode | no |
| Readvisors | `rness/readvisors/<name>/AGENT.md`+`MOTIVATION.md` — a **symlink** when it came from a global source, a **real dir** when it is this project's own | `defaults/readvisors/<name>/` (shipped) or `~/enough/readvisors/<name>/` (user-global) | the toggled-on ones, yes — combined into one voice under "Active Readvisors" |
| Composures | `<anywhere>/<name>.comp` (new ones land in `rness/io/composure/`) | `defaults/composure-forms/<form>.comp` + `rness/composure-forms/` | no — reached through the composure tools |
| Composure comments | `<dir>/.<name>.comp.comments.json` | none — written by `composure.py` | no |
| Council transcripts | `rness/knowledge/councils/<YYYY-MM-DD>-<slug>.md` | none — written on conclude | no (readable on demand) |
| Council outputs | whatever `output.path` names, through `tools.run_write_file` | none | no |
| Policies | `rness/policies/*.md` (symlink) | `defaults/policies/*.md` | yes, all of them |
| Project profile | `rness/knowledge/project-profile.md` | seeded empty | yes |
| Requests | `rness/requests/*.md` | none — a readvisor creates them | no (but readvisors read on demand) |
| Highlights | `<dirname>/.<filename>.highlights.json` | none | no — read via tools |
| Session logs | `rness/knowledge/session-logs/<date>.md` | none | no |
| Broker journal | `rness/knowledge/session-logs/<date>-broker.md` | none | no |
| Fetched web cache | `rness/io/input/<timestamp>-<hash>-<slug>.md` | none | no |
| Cloud cache | `rness/io/cloud-cache/<timestamp>-<slug>.md` + `_cloud-index.md` | none | no |
| Saved wiki articles | `<project>/wiki/<slug>/` or `~/enough/cacheawl/wiki/<slug>/` (the global wiki cachebox; `"infoworld"` accepted as a legacy alias) — folder of `article.html` (verbatim archive copy) + `_manifest.md` + hidden `.meta.json` | none — created on first save | no (readvisors read on demand) |
| Cacheboxes | `~/enough/cacheawl/<box>/…` — root-level box folders + backend-owned `.cachebox.json` + `_cachebox.merirmaid` sidecars | none — created via UI/readvisor/migration | no (readvisors reach it via the cachebox tools) |
| Wikisink registry/state | `~/enough/config/wikisink.json` (user-global, **not** per-project) | none | no |
| Wiki comments/overlays | `<wikisink data dir>/comments/`, `overlay/`, `preserved/` | none | no |
| Converted documents | `<dir>/<name>.<ext>.md` (the twin — a user file), `<name>.<ext>.assets/` + hidden `.<name>.<ext>.convert.json` (both backend-owned) | none — written by `convert.py` on first open | no (a readvisor gets the twin through `read_file`; the *registry* is rendered into the prompt by `prompt.convert_instructions()`) |

**Active vs available**: skills and readvisors ship as files but only become
part of the system prompt when toggled on in the sidebar. The
*disabled* set is persisted per-project as a plain newline-delimited
text file: `rness/skills/.disabled` and `rness/readvisors/.disabled`. Read/
written via `prompt._read_disabled_skills()` / `set_skill_enabled()` (and
the readvisor-side equivalents, still named `_read_disabled_roles()` /
`set_role_enabled()` — see the note on identifiers at the top). New globals
appear in every project with their name added to `.disabled` on first sync
— i.e. defaulted off. **One exception, and it is load-bearing:** a link the
populator pruned as dangling in step 1 and re-created in step 2 is a *heal*,
not an arrival, and keeps its toggle. Without it the 0.3.5 folder rename
would have switched every readvisor the user had switched on back off.
**Untrusted skills also default off**, by a second route:
`skillaudit.quarantine_untrusted()` (called from
`skeleton._populate_skill_symlinks`, so every launch and every
`/api/skills`) names any untrusted skill without a matching `pass`
verdict into `.disabled`. Without it a hand-dropped or readvisor-written
directory would be live in the system prompt having never passed a
toggle. Paradigms are different — exactly one is active, named in
`rness/active-paradigm`.

---

## Models

Two layers.

### Local models (the seven llama.cpp slots)

Registry template at [defaults/models.json](../defaults/models.json) —
ships 7 entries (`g40-04`, `q35-09`, `g40-12`, `g40-26`, `q36-27`,
`q38-04`, `q38-16`; note `q38-*` suffixes mean quant bits, not params).
Each entry: `cute_name`, `label`, `family`, `gguf_filename`, `gguf_url`,
`disk_gb_approx`, `ram_gb_recommended_min`, `ctx_max`, `ctx_defaults`
(a RAM-tier → context-window map). Optional: `llama_cpp_min_release`
(hard gate on switching/launching — `models.release_gate()` is the single
source of the user-facing message) and an `mtp` block for speculative
decoding, in two shapes: embedded head tensors (`q35-09`/`q36-27`) or a
separate draft GGUF (`q38-*`: `draft_gguf_filename`/`draft_gguf_url`/
`draft_disk_gb_approx`; a missing draft file always launches plain).

Live state at `~/enough/config/models.json`: just `{"current": "<cute>"}`
plus optional `ctx_overrides`.

`enough.models.resolve(cute)` merges the registry + live state +
filesystem (does the .gguf exist?) into a complete view, including a
machine-feasibility verdict (`feasibility()`: RAM + free-disk, good /
tight / no). `all_models_view()` returns the full list, used by
`/api/models` (whose payload also carries the installed llama.cpp
release and a `download` snapshot from the in-app download manager,
`enough/model_download.py` — resumable downloads, `model-dl` SSE events,
`/api/models/download|cancel|delete` endpoints).

To **add a new local model**: append an entry to
[defaults/models.json](../defaults/models.json). It shows up in the model
modal on next page load; the supervisor will spawn llama-server with it
when the user selects it. `bootstrap.sh` step 6 reads the same registry
(via `python -m enough.models install-menu`), so no shell tables to sync.

To **change which local model is active**: write to
`~/enough/config/models.json` via `models.save_state({...})`, or POST to
`/api/model` with `{cute: "..."}` — the supervisor restarts llama-server,
the in-memory conversation clears, and the new model is live on the next
message.

### The cloud slot (OPRO-API)

The fifth slot. Not in `models.json` (cloud entries don't have gguf
files or RAM tiers). Instead, the `/api/models` handler in
[server.py](../enough/server.py) (search for `@app.get("/api/models")`)
injects a synthetic entry with `cloud: true` when the
`local_models_only` broker toggle is OFF. The entry's `installed` flag
mirrors `key_present AND last_verified_ok`, gating selection.

`current = "opro-api"` triggers special behavior:
- `supervisor._resolve_startup_choice()` returns `(None, _)` — no
  llama-server spawned, no RAM used.
- `/api/llm-status` synthesizes a `mode: "cloud"` payload from
  `cloud.status_snapshot()` instead of reporting supervisor state.
- `_drive_message`'s routing branch picks `cloud.stream_chat_completion`
  over `llm.stream_chat` on every turn.
- Every completion gets cached to `rness/io/cloud-cache/`.

To **switch to OPRO-API**: POST to `/api/model` with `{cute: "opro-api"}`.
The endpoint validates the three gates (toggle off, key present, key
healthy) and either persists the selection or returns a 400 with the
appropriate `broker.denial_*` message.

---

## OPRO-API (the cloud slot) — full architecture

The user has chosen to pierce the local-only default. They have an
OpenRouter account, generated a key, and want to use a cloud model
through enough's interface. Three reasons that matters as design context:

1. **Cost.** Hardware capable of running large local models is expensive
   to acquire and (often) to electrify. OpenRouter's prices on capable
   cloud models are sometimes lower than the marginal cost of local
   inference. The local-only default is a privacy choice; the OPRO-API
   slot acknowledges that cost is a separate axis.
2. **Privacy trade.** When the user picks OPRO-API, prompts and outputs
   leave the machine. The wizard and UI surface this explicitly — three
   separate confirmation checkboxes, repeated in plain language.
3. **Trust boundary.** The api key is the user's; we treat it as a
   liability, not an asset. We store it in the OS keyring, never on
   disk in plaintext. We construct outbound headers in exactly one
   place ([`cloud._auth_headers()`](../enough/cloud.py)). No readvisor has
   a callable path to the key.

### Storage

The key lives in the **OS keyring** under service `enough-broker`,
account `openrouter-api-key`. Accessed via the
[`keyring`](https://github.com/jaraco/keyring) library (cross-platform:
Keychain on macOS, Secret Service on Linux, Credential Manager on
Windows). The single in-memory module-level cache
(`cloud._API_KEY_CACHE`) populates on first read and invalidates on
`set_api_key` / `clear_api_key`. The function
`cloud._get_api_key_for_broker()` is the only entry point that returns
the value, and it's underscore-prefixed as a convention; no code in
[tools.py](../enough/tools.py) calls it.

The metadata file `~/enough/config/openrouter.json` stores **only**:
`enabled`, `model_id`, `key_in_keychain` (reconciled against keyring
ground truth on every read), `last_verified_at`, `last_verified_ok`,
`last_verified_model`, `last_error`. There's a paranoia check in
`save_cloud_config()` that refuses to persist any string matching the
OpenRouter key pattern, even if a caller accidentally stuffs one in.

### Enablement flow (the wizard)

User-facing UX lives in [index.html](../enough/static/index.html).
Briefly:

1. User flips `local_models_only` off in the broker pane → OPRO-API
   appears in the model modal as "needs setup."
2. Click OPRO-API row → 3-screen modal:
   - **Screen 1**: three confirmation checkboxes (account, billing,
     privacy/cost). The Next button is disabled until all three are
     checked.
   - **Screen 2**: paste API key field (password type with show-toggle).
   - **Screen 3**: live result of an auto-fired health check against
     the zero-cost `openrouter/free` auto-selector.
3. On success, OPRO-API in the model modal shows as "ready" and
   becomes selectable.

After onboarding, the settings panel (inline in the model modal when
OPRO-API is selected) exposes:
- **Re-test key** — POST `/api/cloud/health-check`
- **Update key** — re-opens the wizard at screen 2 (skips understanding)
- **Remove key** — POST `/api/cloud/clear-key` (with confirm dialog).
  Leaves `local_models_only` as-is; user flips it back themselves if
  they want OPRO-API to fully disappear from the picker.
- **Change model id** — POST `/api/cloud/set-model` with `{model_id: ...}`.
  No client-side validation; bad ids fail at request time.

### The /api/cloud/* endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/cloud/status` | GET | Returns the status snapshot. Never includes the api key. |
| `/api/cloud/set-key` | POST | `{api_key}` → stores in keyring + auto-runs health check. |
| `/api/cloud/clear-key` | POST | Removes from keyring + resets verified-state metadata. |
| `/api/cloud/health-check` | POST | Re-pings `openrouter/free`. |
| `/api/cloud/set-model` | POST | `{model_id}` → updates the active OpenRouter model id. |

### Defense-in-depth

The readvisors and the broker run in the **same Python process** — there is no
process-level sandbox. The strongest defenses are:

1. **Key never in a user-readable file.** Keychain access by a process
   the user hasn't previously authorized triggers an OS-level prompt on
   macOS. That's a real boundary.
2. **Shell-pattern denial.** Before `run_shell` invokes `subprocess.run`,
   it scans the command against `_CLOUD_KEY_EXFIL_PATTERNS` in
   [tools.py](../enough/tools.py) — `enough-broker`, `openrouter-api-key`,
   `keyring.get_password|set_password|delete_password`, and
   `secret-tool {lookup,search,store}`. Match → return
   `broker.denial_cloud_key_exfiltration_attempt()` without executing.
   Patterns are intentionally narrow (false positives are rare on
   identifiers we coined ourselves).
3. **Response wrapping.** `cloud.wrap_untrusted_cloud_text()` exists for
   any path where cloud-produced text becomes tool-result content. (Not
   used for ordinary chat completions in Architecture A, where the
   cloud IS the readvisor; meant for `cloud_pipeline` output and any future
   path where cloud content gets passed back as data.)
4. **Cache-write redaction.** Before writing a cache file,
   `cloud._redact()` scrubs anything matching the OpenRouter key
   pattern. The key shouldn't ever flow into cache content, but if it
   did (e.g. an error message echoed the request body), the redaction
   means it doesn't land on disk in user-readable form.

### Caching

Every cloud completion is recorded under
`rness/io/cloud-cache/<YYYY-MM-DD>-<HHMMSS>-<slug>.md` with frontmatter
(`timestamp`, `model`, `source`, `prompt_tokens`, `completion_tokens`,
`total_tokens`) and a body that includes the last user message + full
response. A queryable summary table lives at
`rness/io/cloud-cache/_cloud-index.md`.

`source` values:
- `chat` — an interactive readvisor turn (one per `_drive_message` iteration)
- `pipeline-step` — one step of a `cloud_pipeline` run
- `pipeline-summary` — a follow-up summary call (only when
  `compile.method == "summarize_each"`); includes a
  `summarizes_step_cache` back-reference to the step it summarizes
- `pipeline-final` — the final-pass call of a pipeline

Future local-LLM agents (or the same agent in a later session) can
grep / read the cache to see what happened during cloud sessions.

### The cloud_pipeline tool

Broker-driven multi-step batch execution. Agent invokes via:

```xml
<tool name="cloud_pipeline">
<content>
{
  "steps": [{"prompt": "..."}, {"prompt": "..."}, ...],
  "compile": {"method": "concat" | "summarize_each", ...},
  "final_pass": {"prompt": "...{compiled}..."},
  "output_path": "rness/io/output/...",
  "model": "openrouter/auto"
}
</content>
</tool>
```

Spec validation, execution, caching, compilation, optional final pass,
and output-path writing all happen in
[`cloud.pipeline_run()`](../enough/cloud.py). The tool runner
[`tools.run_cloud_pipeline()`](../enough/tools.py) handles the gating
chain (toggle off → key present → key healthy → spec parses) before
delegating.

`compile.method`:
- `"concat"` — join step outputs with `separator` (default `"\n\n"`).
- `"summarize_each"` — make a follow-up cloud call per step using
  `summary_prompt` (must contain literal `{step}`), join the summaries.
  Full step outputs stay on disk in their individual caches; the
  compiled artifact and any final-pass input are built from the
  summaries. Use when a final pass over many large steps would
  otherwise exceed the model's context window.

The tool returns a small summary body (steps run, totals, output path,
cache counts); the actual prose lives on disk for `read_file` retrieval.
This keeps multi-hundred-thousand-token batches out of the readvisor's
context window.

200-step ceiling per pipeline; output_path is constrained to inside the
project directory (path-traversal protection).

---

## The broker

A single Python module — [enough/broker.py](../enough/broker.py) — in
the same process as the readvisors. Three jobs:

1. **Configure.** Toggles live in `broker.TOGGLES` (a tuple of `Toggle`
   dataclasses). Each has `key`, `label`, `description`, `default`, and
   `group`. Persisted to `~/enough/config/broker.json`. The
   `/api/broker` endpoint iterates `TOGGLES` and renders one htmx-clickable
   row per toggle — adding a toggle to the tuple makes it appear in the
   UI with **no other code changes**.
2. **Trace.** `broker.trace()` appends entries to
   `rness/knowledge/session-logs/<date>-broker.md`. Each entry: timestamp,
   tool name, decision, args summary, outcome. Gated by
   `trace_log_enabled`.
3. **Deny.** `broker.denial_*()` functions return canned, actionable
   error strings for the readvisor. The runner returns one of these as the
   tool body when a precondition fails.

The current toggle catalog (13 toggles, all default `True`):

| Key | Group | Affects |
|---|---|---|
| `trace_log_enabled` | general | Whether broker journal entries get written |
| `local_models_only` | general | Whether OPRO-API appears in the model picker |
| `read_file_brokered` | read_file | Trace-logging for `read_file` (allowlist always enforced) |
| `write_file_brokered` | write_file | Trace-logging for `write_file` (allowlist always enforced) |
| `shell_brokered` | shell | Trace-logging for `shell` (no allowlist for shell by design) |
| `fetch_url_enabled` | fetch_url | Whether `fetch_url` works at all (otherwise a readvisor falls back to `curl` via shell) |
| `fetch_url_tor_for_offlist` | fetch_url | Off-allowlist fetches via Tor (vs outright denial) |
| `fetch_url_cache_and_convert` | fetch_url | HTML→markdown (pandoc, a base dep since 0.2.5) + cache in `rness/io/input/` |
| `wikisink_enabled` | wikisink | Whether the readvisors' four wiki tools work at all (the 🚰 browser UI is ungated) |
| `wikisink_live_updates` | wikisink | Whether wikisink update runs may call the Wikipedia/Wikimedia APIs (off = report from local state only) |
| `cacheawl_enabled` | cacheawl | Whether the readvisors' three cachebox tools work at all (the cacheawl browser UI is ungated; URL ingests still additionally honor the `fetch_url_*` toggles) |
| `composure_enabled` | composure | Whether the readvisors' nine composure tools work at all — **and** whether `COMPOSURE_TOOL_INSTRUCTIONS` is in the prompt (this is the one toggle that gates *docs* alongside the *tools* they describe; the gate fails open on an unreadable config). The canvas UI stays ungated, like wikisink and cacheawl |
| `readvisory_install` | readvisors | Whether `install_readvisor` may write a readvisor to disk. Off keeps the `readvisory` skill's interview and drafting and leaves the filing to the user. A new group — `/api/broker` renders whatever is in `TOGGLES`, so a new group needs no code |

---

## Tools

| Tool | Runner | Gating |
|---|---|---|
| `read_file` | `tools.run_read_file` | path under project OR on file-read allowlist. A convertible original returns its **twin** (converting first, on a daemon thread joined for `tools.CONVERT_BLOCKING_SECONDS` = 120) — see "Document conversion" |
| `write_file` | `tools.run_write_file` | path under project OR on file-rw allowlist; not in `rness/requests/done/`. **`.girraph` and `.comp` are refused whole-file** (`composure.write_denial()` covers `.comp` *and* its `.<name>.comp.comments.json` sidecar, and the message names the composure tools to use instead). A refused sync-on-save of a syncing twin comes back as `ok=False` whose body says the twin *was* written |
| `export_document` | `tools.run_export_document` | path under project OR on the file-**rw** allowlist (it writes a real document); `<target>` from `convert.EXPORT_TARGETS`, `<mode>` `copy` (default) or `overwrite` |
| `shell` | `tools.run_shell` | exfiltration patterns denied; otherwise no path constraint |
| `fetch_url` | `tools.run_fetch_url` | `fetch_url_enabled` toggle; host on allowlist OR Tor toggle on |
| `read_highlights` | `tools.run_read_highlights` | path under project |
| `navigate_to_highlight` | `tools.run_navigate_to_highlight` | path under project |
| `cloud_pipeline` | `tools.run_cloud_pipeline` | `local_models_only` off + key present + key healthy + spec parses |
| `read_girraph` | `tools.run_read_girraph` | `.girraph` path under project or read allowlist; depth-limited (default 1), refs returned as stubs |
| `add_node` | `tools.run_girraph_add_node` | `.girraph` path; parentless call on a missing file creates it |
| `update_node` | `tools.run_girraph_update_node` | `.girraph` path; patches only fields present, empty tag clears |
| `link_nodes` | `tools.run_girraph_link_nodes` | `.girraph` path; `<remove>true</remove>` unlinks |
| `remove_node` | `tools.run_girraph_remove_node` | `<confirmed>yes</confirmed>` required (user must confirm); children require `<cascade>true</cascade>` — no orphaning |
| `wiki_search` | `tools.run_wiki_search` → `wikisink/agent.py` | `wikisink_enabled` toggle + an installed, reachable archive |
| `read_wiki_article` | `tools.run_read_wiki_article` → `wikisink/agent.py` | same; full text cached under `rness/io/input/`, preview returned |
| `wiki_status` | `tools.run_wiki_status` → `wikisink/agent.py` | `wikisink_enabled` toggle (works without an archive — that's the point) |
| `wikisink` | `tools.run_wikisink` → `wikisink/agent.py` | `wikisink_enabled` toggle; network calls additionally gated by `wikisink_live_updates` |
| `cachebox_list` | `tools.run_cachebox_list` → `cacheawl.py` | `cacheawl_enabled` toggle; no arg = list boxes, `<box>` = its contents tree (reconciles first) |
| `cachebox_create` | `tools.run_cachebox_create` → `cacheawl.py` | `cacheawl_enabled` toggle; creates an empty box (name-validated) + its mirror |
| `cachebox_ingest` | `tools.run_cachebox_ingest` → `cacheawl.py` | `cacheawl_enabled` toggle; `path`/`url`/`wikisink` source to a depth. URL ingests also honor the `fetch_url_*` toggles; runs in the background, box registered `ingesting` up front |
| `read_composure` | `composure_tools.run_read_composure` | `composure_enabled`; `.comp` path. No `<module>` → the outline (three header lines + one line per module). With `<module>` → that module as markdown, cached to `rness/io/input/` over `CACHE_OVER_CHARS` = 4000 |
| `new_composure` | `composure_tools.run_new_composure` | `composure_enabled`; `<form>` from `SHIPPED_FORMS` + project forms. Writes the file **immediately** (unlike the canvas's lazy create) |
| `comp_add_module` | `composure_tools.run_comp_add_module` | `composure_enabled`; omit geometry and let `place_module` choose |
| `comp_update_module` | `composure_tools.run_comp_update_module` | `composure_enabled`; a patch — only keys present are touched, **never** page text |
| `comp_set_page` | `composure_tools.run_comp_set_page` | `composure_enabled`; `<append>true</append>` adds a page instead of replacing |
| `comp_remove_module` | `composure_tools.run_comp_remove_module` | `composure_enabled`; `<confirmed>yes</confirmed>` required, like `remove_node` |
| `comp_arrange` | `composure_tools.run_comp_arrange` | `composure_enabled`; `<mode>` `grid` \| `column`; the order of `<modules>` is the resulting reading order |
| `comp_save_as_form` | `composure_tools.run_comp_save_as_form` | `composure_enabled`; writes a reusable form into `rness/composure-forms/` |
| `composure_from_outline` | `composure_tools.run_composure_from_outline` | `composure_enabled`; one markdown outline → a whole composure, deterministically. The `scaffold` skill teaches the grammar — see "Composures" |
| `install_readvisor` | `readvisor_tools.run_install_readvisor` | **`readvisory_install`** toggle; kebab-case `<name>` ≤ 40 chars, `<scope>` `project`\|`global`, both documents non-empty and ≤ 40 KB, `prompt.readvisor_shape()` clean, the payload scan clean, destination not a symlink, `<replace>yes</replace>` to overwrite |

All registered in `_DISPATCH` (~line 1627 in tools.py) and
`_TRACE_TOGGLE` (~line 1656) — the last twelve add themselves through the
two import-time `register()` calls at the bottom of tools.py
(`composure_tools.register()`, `readvisor_tools.register()`), which is the
pattern to copy for any future tool family: the op vocabulary stays in one
module instead of spreading runners through tools.py. The tool-call XML
parser (`parse_tool_calls`) handles arbitrary tool names — extra inner tags
(beyond `<path>`, `<content>`, `<command>`, `<url>`) end up in
`ToolCall.extra` so new tools don't need parser changes.

A runner that changes something the frontend has open returns a
**`ToolResult.side_effects`** dict; `server._handle_tool` fans each key out
as an SSE event of that name. That is how a composure tool fires the
`composure` event and `install_readvisor` fires `readvisors_changed`.

Tool documentation that the readvisors read is in
[enough/prompt.py](../enough/prompt.py) under `TOOL_INSTRUCTIONS`,
`COMPOSURE_TOOL_INSTRUCTIONS` and `READVISORY_TOOL_INSTRUCTIONS`, assembled
by `tool_instructions(project_dir)` (see "The request lifecycle" for the
gates). Every new tool needs an example block + prose explanation in the
right one of the three — and `tests/test_prompt_weight.py` will fail until
it has one.

---

## Readvisors (the chief, voltron, install, the folder migration)

A **readvisor** is a persona: a folder holding `AGENT.md` (its identity,
with a `# <Display Name>` H1) and `MOTIVATION.md` (its drive). The one that
always speaks is the **chief readvisor** — named `Ed` out of the box. The
ones the user switches on in the sidebar are folded into the chief's own
voice; they are not consultants the chief reports from. That is the
"voltron" rule, and `prompt._READVISORS_FRAMING` is where it is said to the
model. `_ROLES_FRAMING` survives as an alias of the same string.

Renamed from *roles* in 0.3.5. **Identifiers did not move** — `AGENT.md`,
`MOTIVATION.md`, `/api/roles`, `/api/roles/toggle`, `#roles-list`,
`{{roles-list}}`, `.role-row` / `.role-toggle` / `.role-name`, and every
Python name (`list_roles`, `set_role_enabled`, `_load_roles`,
`_populate_role_symlinks`, `_read_disabled_roles`, `_is_role_file`). Folder
names did.

### Three origins, three ranks

| rank | where | how it looks in `rness/readvisors/` |
|---|---|---|
| 1 · project | `rness/readvisors/<name>/` | a **real directory** — wins by existing; the populator never replaces one with a link |
| 2 · user-global | `~/enough/readvisors/<name>/` (seam `ENOUGH_READVISORS_ROOT`) | a symlink |
| 3 · shipped | `<install>/defaults/readvisors/<name>/` | a symlink |

`skeleton._readvisor_sources(defaults_root)` returns 2 then 3 in precedence
order; rank 1 is not in the list at all because it wins by not being
overwritten. `GET /api/roles` renders each row with `data-name` and
**`data-origin`** ∈ `shipped | global | project` (`server._readvisor_origin`,
read from the filesystem; an unreadable entry reads as `shipped`, the one
origin with no destructive affordance). Non-shipped rows also carry a
`<button class="role-remove">` with **no `hx-*` of its own** — removing
deletes files, so the frontend wires it through `confirmOverlay` first.

The populator also **re-aims** links, which is what heals a project moved
between machines or installs. A link is re-aimable ("managed") when its
resolved target's *parent directory* is named `roles` or `readvisors`
(`_is_managed_readvisor_link`); a link the user pointed anywhere else is
left where it points.

### The folder migration

`skeleton._migrate_roles_to_readvisors(project_dir)`, called from
`ensure_skeleton` right after `_migrate_undot` and **before** the
populators, so a project still on `rness/.roles/` gets undotted and then
renamed in one launch.

| on disk | what happens |
|---|---|
| only `roles/` | one atomic `rename()` — carries `.disabled`, `.gitkeep`, real dirs and symlinks alike |
| both | merge INTO `readvisors/`, which is authoritative: real directories missing from it are moved, the two `.disabled` files are **unioned** (off under either name stays off), symlinks and `.gitkeep` are deleted because the populator re-creates them, then `rmdir` — which declines if anything survived |
| only `readvisors/`, or neither | no-op |
| `readvisors` is a file or symlink | left strictly alone — someone did that on purpose |
| read-only parent | logged, no raise; the project keeps using `roles/` |

**Every reader and writer of the folder goes through
`prompt._readvisors_dir(rness)`** — `readvisors` if it is a dir, else
`roles` if that is, else `readvisors` — so a project whose migration could
not run keeps working. `server.HIDDEN_TREE_PATHS` and `server._is_role_file`
name **both** folders for the same reason.
`skeleton.shipped_readvisors_root(defaults_root)` does the same one level
up, which is also what a *sibling older install* looks like from here.

### The chief's name

Machine-global, beside the theme and the UI language:
`chief_readvisor_name` in `~/enough/config/ui.json`, seeded from
`defaults/ui-config.json` with `"Ed"`.

- `prompt.CHIEF_NAME_DEFAULT` / `CHIEF_NAME_MAX` (24).
- `prompt.valid_chief_name(raw) -> str | None` — trimmed; 1–24 chars;
  a letter or digit first, then letters, digits, space, `-`, `'`, `.`.
  Unicode-aware (`エド` validates), so a user can name their readvisor in
  their own script.
- `prompt.chief_name()` reads ui.json through `ENOUGH_UI_CONFIG` and lands
  on `"Ed"` for **every** failure (missing, unreadable, bad json, absent
  key, invalid value). A missing name must never stop a turn.
- `prompt._ui_config_path()` is a deliberate ~6-line copy of
  `server._ui_config_live_path()`. **The prompt layer must stay importable
  without FastAPI** — the council engine and the tests build prompts with
  no app running. Don't "deduplicate" it by importing `server`.

Two write doors, deliberately different:

| Route | Method | Shape |
|---|---|---|
| `/api/readvisor/chief` | GET | `{name, default, max_length}` |
| `/api/readvisor/chief` | POST | `{name}` → `{ok, name}`; **400 on an invalid name** — the user typed it into a box and is owed an answer |
| `/api/ui-config` | POST | also accepts `chief_readvisor_name`, validated the same way, but an invalid value is silently **dropped** (matching `ui_language`) |

`/api/ui-config` returns the entire theme catalog, so POSTing a name back
through it would make a stale client overwrite a theme change made in
another window. That is why the dedicated pair exists.

### The prompt API

```python
prompt.assemble_system_prompt(project_dir, readvisors="voltron"|"none",
                              profile="chat"|"council") -> str
prompt.readvisor_identity(project_dir, folder_name) -> str
prompt.identity_preface(name=None) -> str
```

- `readvisors="none"` drops the Active Readvisors section **and nothing
  else**. A council's chief needs it: every other readvisor is a separate
  participant with its own prompt, so folding them into the chief as well
  would put each of them in the room twice.
- `readvisor_identity` returns ONE readvisor's two documents under the same
  `## Readvisor:` / `### Identity` / `### Motivation` headings, with **no**
  voltron framing. It **ignores the enabled/disabled toggle on purpose**:
  the sidebar toggle governs the combined voice of ordinary conversation,
  while a council picks its participants in its own setup card. Returns
  `""` for a missing or empty readvisor — "no identity" means "not a
  participant".
- `profile="council"` is the lean prompt; see "Councils".
- Both default to the pre-0.3.5 behaviour, byte for byte.

### `install_readvisor` and the shape contract

`prompt.readvisor_shape(agent_md, motivation_md) -> list[str]` (`[]` is a
pass) reads its required headings from
`defaults/skills/readvisory/assets/AGENT.md.template` and
`MOTIVATION.md.template` **at call time** — editing a template IS editing
the contract. It reports missing headings, misordered headings, empty
sections, a missing `# <Display Name>` H1, and a missing trailing
`enough-tooltip-text:` line. Missing templates ⇒ `[]` (a partial install
has no shape to enforce; better than refusing every install).

It is enforced at the **install door** and over the shipped readvisors by
`tests/test_readvisors_defaults.py`. **The loader never enforces it** — a
hand-made readvisor that predates the shape still loads and still works.

[enough/readvisor_tools.py](../enough/readvisor_tools.py) refuses in this
order, each refusal phrased so the readvisor can act without making the
user read an error:

1. `readvisory_install` toggle off → `broker.denial_readvisory_install_disabled()`
2. missing name / not kebab-case / > 40 chars
3. scope not `project` or `global`
4. the name is a **shipped** readvisor's
5. either document empty, or over 40 KB
6. `readvisor_shape` problems, quoted in full
7. **payload scan** findings, quoted (pattern id, confidence, file, line)
8. the destination is a **symlink** — a global readvisor visible here;
   writing through it would edit it for every project at once
9. the destination exists and `<replace>yes</replace>` was not given

`scan_documents()` writes the two documents to a `tempfile` directory —
**never inside the project**, or the scan's own input would one day be read
back as a readvisor — and calls `skillaudit.run_payload_scan()`, i.e. the
same bundled `payload_scanner.py` the skill audit uses. **Unlike a skill
audit, this door treats `flag` and `fail` alike**: a skill is code whose
findings need judging; a readvisor is prose about a person, and prose about
a person has no legitimate reason to look like an exfiltration pattern.

Writes stage into `.<name>.installing/` and `rename()` into place, so a
crash never leaves half a readvisor where the loader will find it. On
success the readvisor is switched ON here (and at global scope also linked
into this project immediately; elsewhere it arrives default-off on the next
launch), and the runner returns the side effect
`{"readvisors_changed": {name, scope, action: "install"}}`, which
`server._handle_tool` emits as an SSE event of that name.

`POST /api/readvisors/remove {name}` → `{ok, name, origin}`; **403** for a
shipped readvisor, 400 for a bad name, 404 when it is not here. `project`
deletes the real folder, `global` deletes it from `~/enough/readvisors/`
and unlinks the local link. **Either way the name is cleared from
`.disabled`** — otherwise a later readvisor of that name would arrive
switched off for no visible reason.

---

## The readvisor panel

The conversation. It is the third column of `.layout`, not an overlay:
`grid-template-columns: var(--sb-w) 1fr var(--rv-w)`, so a docked panel
sits side by side with whatever is in `main.content` and "click back to the
doc without collapsing chat" is free. `--rv-dock-w` is
`clamp(340px, calc(27vw / var(--uiz, 1)), 480px)` — **the `/ var(--uiz)` is
the coordinate contract, not decoration** (see "Display scales").

It keeps the existing ids — `#conversation`, `#chat-form`, `#message`,
`#send-btn`, `#mic-btn` — so nothing about the chat wire changed.

**Neither side column is ever `display: none`.** A `display:none` grid item
stops being an item and the stage slides sideways; closed means 0 width
plus `visibility: hidden`, which also takes the panel out of the tab order.

### State

One attribute on `<html>`, not a class on `#layout`:

| `data-rv` | `data-rv-overlay` | meaning |
|---|---|---|
| `closed` | — | third column 0 wide, panel invisible |
| `open` | absent | a real third grid column |
| `open` | `"1"` | floats over main's right edge |
| `full` | — | panel covers the stage |

An attribute because the `<head>` `BOOT_UI_STATE` block sets it **before
first paint** — a column that starts wrong and animates to right is a
visible lurch on every launch. The head block pre-computes the overlay
decision from the same numbers the CSS clamp uses.

- `RV_STATE` is the JS mirror; **`rvSetState(next, {skipSave, focus})` is
  the one door.** It fires a `readvisor-panel` `CustomEvent` on `document`
  (`detail: {state, overlay}`) whenever the state actually changes — that
  is the hook anything laying out the stage listens on, and **the grid is
  still resizing for ~180 ms after it** (the composure canvas also waits on
  `#layout`'s `transitionend`).
- `rvToggle()` closed ↔ open (from full it collapses to closed);
  `rvToggleFull()` open ↔ full; **`rvAsk()`** opens docked + focuses the
  composer — that is what every "ask your readvisor about this" affordance
  calls.
- `rvApplyOverlay()` recomputes push-vs-float on state change, on `resize`
  and from the ⌘\ sidebar handler; threshold `RV_MIN_STAGE = 480` CSS px of
  remaining stage. `rvDockWidth()` mirrors the CSS clamp.
- `rvForceClosed(on, reasonText)` closes without persisting, disables the
  toggle with `reasonText` as its tooltip, and restores the prior state on
  `false`. Built, not yet called.
- Persisted per project as `ui.readvisor_panel` ∈ `"open" | "closed"`
  (`project_meta._clean_panel`, default `"open"`). **`"full"` is a gesture
  and is never persisted.** `save_ui`'s 4th argument left at `None` keeps
  what is on disk, so the scale steppers and the panel toggle cannot
  clobber each other.

**`rv-full` does not collapse main to 0**, though the spec said it should: a
0-width `main.content` gives the edit textarea a 0-width scroll box, and the
mode stack requires a buried mode's buffer, scroll and dirty state to
survive. `full` positions the panel absolutely over main instead
(`left: var(--sb-w)`, `z-index: 60`, opaque) — pixel-identical on screen,
main's geometry untouched.

### Esc, keyboard, and selection context

Esc order as implemented (extended by composure — see below):

1. any open modal — owns esc itself
2. the confirm overlay — stops esc in its own capture listener
3. a focused composer / search / inline-edit field — **inert**
4. an open composure menu — closes it
5. `rv-full` — drops to docked
6. composure peek — puts the stacked modes back
7. the top of the mode stack

**A docked panel is never closed by esc.** `_escComposerFocused()` lists
`message`, `wiki-search`, `mm-label-input`, `ca-ingest-value`,
`ca-prompt-input`, `comp-title`, `comp-search`. Note rung 3 outranks rung 5
and the panel focuses the composer whenever it opens, so esc in `rv-full`
does nothing until the caret leaves the composer — known, recorded, and the
one-line fix (make esc in `#message` blur) is parked.

`⌘/` toggles docked, `⇧⌘/` toggles full (matched on `key === '/' || '?' ||
e.code === 'Slash'`, because several layouts report a different `key` with
shift held). `⌘K` focuses the one composer and opens the panel on the way.

**There is one form and one composer**, so a selection preamble is
prepended **once**, in a capture-phase `submit` listener on `document` —
capture always beats htmx's bubble-phase listener on the form, so the value
htmx serializes already carries it and the user sees exactly what was
attached in their own bubble. `rvPendingSelection()` returns
`{where, text, preamble, clear}` for readedit, wikisink and composure (via
`compPendingSelection()`, consulted both at the top when nothing is stacked
or while peeking, **and** at the marked end — composure is the base layer,
so the original early `return null` would have made the extension point
unreachable). The chip is `#rv-chip`.

**Behaviour change worth knowing:** the five old pills also stamped a
*bare* context line on every message (`[wikisink article: …]`,
`[merirmaid diagram: …]`, `[cacheawl store]`) whether or not anything was
selected. Those did not survive, by owner decision — context stays empty
until something is selected. Restoring one would go in the same submit
hook.

---

## Composures (the `.comp` format, the one door, the canvas)

0.3.5. A **composure** is a canvas document: a `.comp` file holding
**modules** (boxes) laid out in world coordinates, each with one or more
**pages** of rich text, plus an ink layer. A **form** is a template
(`blank` `cards` `scaffold` `journal` `council`). The canvas is the
project's **base layer** — it lives where `#conversation` lived, below the
mode stack (z < 30), and it is not a stack citizen: you cannot close it,
you peek past it.

[enough/composure.py](../enough/composure.py) owns the format and the ops;
[enough/composure_api.py](../enough/composure_api.py) is HTTP translation
only; [enough/composure_tools.py](../enough/composure_tools.py) is the
readvisors' door. The frontend is one CSS block and one JS block in
index.html under `COMPOSURE` banner comments, every identifier prefixed
`comp` / `COMP_`.

### The format

HTML5, complete, human-readable, and renderable by any browser with no
enough installed — the serializer writes a generated `<style>` block for
exactly that. It **never** contains `<script>`, event-handler attributes,
`<iframe>`, `<object>`, `<embed>`, `<form>`, `<link>`, external `<img>`, or
`javascript:` / `data:` URLs.

```html
<!doctype html>
<html lang="en" data-composure="1">
<head>
<meta charset="utf-8">
<title>Chapter map</title>
<meta name="generator" content="enough 0.3.0">
<meta name="composure:version" content="1">
<meta name="composure:form" content="cards">
<meta name="composure:kind" content="board">       <!-- page | board -->
<meta name="composure:rev" content="12">
<meta name="composure:created" content="2026-09-17T14:03:00Z">
<meta name="composure:modified" content="2026-09-17T15:10:00Z">
<meta name="composure:view" content='{"x":0,"y":0,"zoom":1}'>
<meta name="composure:council" content='{…}'>      <!-- council form only -->
<style>/* generated on every write, never parsed back */</style>
</head>
<body>
<main class="comp-canvas">
<svg class="comp-ink" xmlns="http://www.w3.org/2000/svg">
<polyline data-id="s1" data-w="2" data-color="ink" points="10,10 14,12"/>
</svg>
<section class="comp-module" data-id="m1" data-type="text" data-x="0"
         data-y="0" data-w="816" data-h="1056" data-z="1" data-bg="paper"
         data-scale="1" data-title="" data-cur="1" style="…">
  <div class="comp-page" data-n="1">…sanitized rich text…</div>
</section>
</main>
</body>
</html>
```

Guarantees, all pinned by `tests/test_composure.py`:

- **`dumps(loads(x)) == x`** for anything `dumps` produced. Attribute order,
  module order, number formatting and JSON key order are fixed.
- Geometry rounds to 2 decimals on write; ink points to 1.
- **Unknown `composure:*` meta keys and unknown `data-*` on modules and
  pages round-trip**, capped at `MAX_EXTRA_ATTRS` = 24 each. Non-`data-*`
  attributes (`class`, `style`, `id`) are regenerated and never preserved.
- **`loads()` sanitizes every page as it parses.** There is no window in
  which unsanitized markup exists in memory.
- Every module has at least one page; a module serialized with zero pages
  reads back with one empty page (that is how the `journal` form expresses
  "no pages yet").
- `data-n` is renumbered 1..N on read — a convenience for a human reading
  the file, not an identity.

World units: 1 unit = 1 CSS px at zoom 1. `FULLPORT` = 816×1056 (US Letter
at 96 dpi), `FULLPORT_PAD` = 72, 16-unit base text, `GRID` 24 / `GUTTER` 48.
Coordinates may be negative. Vocabulary constants all live in
`enough.composure`: `MODULE_TYPES` (`text doc wiki weblink webframe image`),
`BG_SWATCHES` (ten, `paper`…`clear`), `INK_COLORS`, `KINDS`,
`REFRESH_MODES`, `SHIPPED_FORMS`, `SOURCES`, `OP_NAMES`, `COMMENT_STATES`,
`BASE_SIZE`, and `SCALE_MIN`/`MAX`/`STEP` — **the scale ladder is anchored
at 1.0**, not built upward from 0.5 (a ladder from the minimum misses 1.0 by
1.4 % and every new module would save at `scale=1.0136`); use
`scale_ladder()` for the rungs.

### One door — node-level ops, exactly like girraph

**Content changes ONLY through node-level ops applied by
`composure.apply_ops()` under `composure.path_lock()`.** The canvas and the
readvisor tools use the same op vocabulary; the server parses → mutates →
sanitizes → serializes, and nothing a client or a model sends is ever
written through verbatim. **Whole-file writes to `*.comp` are refused at
both existing write doors** (`POST /api/file`, the `write_file` tool) via
`composure.write_denial()`, whose message names the tools to use instead.
There is deliberately **no endpoint that accepts `.comp` HTML**. Same
reasoning as the girraph section below: a file is the source of truth, a
small model can patch one node safely and cannot rewrite a document safely,
and a user typing in one module while a readvisor edits another must not
clobber each other.

| op | Required | Optional | Notes |
|---|---|---|---|
| `add_module` | `type` | `id` `x` `y` `w` `h` `z` `bg` `scale` `title` `fullport` `near` `href` `url` `article` `install` `refresh` `speaker` `speaker_kind` `turn` `markdown`\|`rich` `pages[]` | Omit `x`/`y` → `place_module`. Omit `w`/`h` → median of same-type modules, else `BASE_SIZE × scale`. Omit `z` → max+1. `fullport: true` forces 816×1056 |
| `update_module` | `id` | `type` `x` `y` `w` `h` `z` `cur` `bg` `scale` `title` `href` `url` `article` `install` `refresh` `cache` `speaker` `speaker_kind` `turn` | A patch: only keys present are touched. **Never** page text |
| `remove_module` | `id` | — | Refused on a locked (council) module |
| `set_page` | `module` `n` | `markdown` \| `rich` | Replaces the page |
| `add_page` | `module` | `n` `markdown`\|`rich` `date` | Appends by default; renumbers; sets `cur` |
| `remove_page` | `module` `n` | — | Refuses the last page ("remove the module instead") |
| `file_page` | `module` `n` | `date` (default today) | The journal's one-way door |
| `add_strokes` | `strokes[]` | — | `{id?, color, width, points}`; points as `[[x,y],…]` or an SVG points string |
| `remove_strokes` | `ids[]` | — | Silent about ids already gone |
| `replace_strokes` | — | `remove[]` `add[]` | The eraser's split, atomic |
| `set_meta` | — | `title` `kind` `view` | Nothing else — `form` and `council` are **not** settable here |
| `arrange` | `ids[]` | `mode` (`grid`\|`column`) `pack` `x` `y` `gutter` `cols` | The order of `ids` is the resulting reading order. `pack` (column only) stacks each module under the previous using its **own** height |
| `set_council` | `council` | — | **Refused for every source but `"council"`** — see "Councils" |

`markdown` and `rich` are mutually exclusive; sending both is refused.
`rich` is sanitized, `markdown` is converted and then sanitized. A batch is
**atomic**: the whole batch is validated and applied against a copy, then
written tmp+rename, so a failing op leaves the file byte-identical.

Caps (`composure.CAPS`, returned in the model so the frontend can draw
gauges): **200 modules**, **500 pages per module**, **400 KB per page**
(`MAX_PAGE_CHARS`), **5 000 strokes**, **2 000 points per stroke**, **8 MB
per file**, rich-text nesting depth 32, title 200 chars. Internal ceilings
you will meet if you feed it something hostile: `MAX_RICH_INPUT_CHARS`
2 000 000 (what the sanitizer will even look at) and `MAX_TAGS_PER_PAGE`
20 000 (the nested-formatting-bomb ceiling).

Every refusal is a `ComposureError` whose message is written to be read —
the API turns it into a 400 `detail`, the tools return it as the tool body,
and the frontend surfaces it verbatim in `#comp-notice`. Unknown names list
the allowed set; `no module 'mX' on this composure` lists the ids.

### The JSON document model

`composure.model(comp)` is the contract the canvas renders from — returned
under `model` by `GET /api/composure`, and by an ops reply when `stale` is
true or `want_model` was set. Top level: `version title form kind rev
created modified view council bounds modules strokes meta warnings caps`.
One module carries `id type known_type x y w h z bg known_bg scale title
cur fields speaker speaker_kind turn locked page_count pages data`; one
page carries `n rich first_line chars date filed locked data`.

Three fields decide behaviour:

- **`known_type` / `known_bg` false** mean a *newer* enough wrote something
  this one does not understand. Render as a text card / paper and **do not
  normalize the value** — round-tripping it is the promise.
- **`module.locked`** is `bool(speaker)`: a council statement, whose text
  the engine owns. **`page.locked` == `page.filed`**: a filed journal page,
  permanently read-only. Both still accept moves, restyles and comments.
- **`modules` is in FILE order, never z order.** `z` is a field;
  bring-forward / send-back is an `update_module` with a new `z`.

### Endpoints

All project-mode (home 404s them via `ModeGate`). Every `path` goes through
`create_app`'s `_resolve_project_path`, so `cacheawl:` works and traversal
is a 400; a path that does not end in `.comp` is a 400 that says so.

| Route | Method | Notes |
|---|---|---|
| `/api/composure?path=` | GET | `{path, rev, model}`. **Side effect:** stamps `rness/project.json`'s `composure.last`. That is the *only* place `last` is written |
| `/api/composure/ops` | POST | **The single write door.** `{path, base_rev?, source, create?, form?, title?, want_model?, ops[]}` → `{path, rev, changed[], stale, stale_changed, created, model?}` |
| `/api/composure/new` | POST | Describes a composure **without writing it**: `{path: null, pending_path, form, title, rev: 0, model}` |
| `/api/composure/list` | GET | `{composures: [...]}`, newest first |
| `/api/composure/forms` | GET | Shipped first, then `rness/composure-forms/`; a project form with a shipped name **wins** and is listed once with `origin: "project"` |
| `/api/composure/save-as-form` | POST | `{path, name}` → `{form, path, forms}` |
| `/api/composure/rename` | POST | Retitles, renames the file to match, and **carries the comments sidecar**; `keep_filename: true` retitles only; 409 on a collision |
| `/api/composure/link-preview` | GET | `?path=&module=` — per type; **never raises** for a missing target, answers `{ok: false, detail}` |
| `/api/composure/webframe/refresh` | POST | Goes through `tools.fetch_and_cache` — the **same** gated pipeline as `fetch_url` — then writes `data-cache` and page 1 through ordinary ops with `source: "enough"`. A broker refusal comes back `200 {ok: false, denied: true, detail}` with the denial text verbatim |
| `/api/composure/comments` | GET/POST/PATCH/DELETE | Mirrors `/api/wiki/comments*`. Deleting the last comment removes the sidecar rather than leaving `{"comments": []}` |
| `/api/composure/launch` | GET | Resolved against what is actually on disk: `{launch, path, form, notice}` |
| `/api/project/composure` | POST | `{launch: "blank"\|"last"\|"file"\|"form", path?, form?}`. **`last` is never accepted here** — it is stamped by opening a composure |

**A stale `base_rev` is not an error.** Ops are last-writer-wins per module,
so the batch still lands; the reply says what moved underneath you in
`stale_changed` (`[]` when fresh, `null` when the history window no longer
covers `base_rev` — then refresh everything).

### The `composure` SSE event

```jsonc
// event: composure
{"path": "rness/io/composure/board.comp", "rev": 12,
 "changed": ["m4f2a91c", "ink"],        // "ink" = the stroke layer moved
 "source": "ui" | "readvisor" | "council" | "enough",
 "created": false}
```

Fired after **every** applied batch — from the API router, and from the
readvisor tools via `ToolResult.side_effects` fanned out by
`server._handle_tool`.

### The canvas

Three coordinate spaces, and this is the part to hold in your head before
touching any positioning code:

```
TOP-LEVEL px   what clientX/clientY and getBoundingClientRect() speak,
               because `body { zoom: var(--uiz) }` sits above them
STAGE px       viewport-local, inside the zoomed body — what clientWidth and
               style.left/top speak.  stage = (top-level − viewportRect) / UIZ()
WORLD units    the format's own units, 1 unit = 1 CSS px at Z = 1
               stage = (world − origin) × Z
```

`compEventToStage(ev)` is where the `/ UIZ()` happens; `compEventToWorld`,
`compStageToWorld` / `compWorldToStage`, `compZ()`, `compOrigin(Z)` and
`compApplyView(eased)` are the rest of the set. **Composure ignores
`--txz`**, like the diagram canvases. Screen-constant chrome uses two
mechanisms on purpose: *inside* the world, anything that must stay one size
divides by `var(--comp-z)` (borders, radii, shadows); *outside* the world,
`#comp-overlay` is screen space and needs no counter-scaling at all (resize
handles, marquee, refresh flash).

`compPanelFactor()` reads `data-rv` on `<html>` and `sidebar-collapsed` on
`#layout` — **not measured widths**, because the grid is still animating
when it is asked. `compClampZ` applies the hard 0.05–8 range and then the
page-fit rule for `kind=page` while `!COMP.zoomed`, computed at read time
rather than written into `userZoom` so it cannot ratchet down as panels come
and go.

**Saving is ops, not a save button.** `compQueue(op, key)` coalesces by key
(`geo:<id>`, `bg:<id>`, `z:<id>`, `scale:<id>`, `cur:<id>`,
`page:<id>:<n>`, `meta:view`), so a five-second drag produces exactly one
`update_module`. Flush points: a 1.2 s debounce, leaving the caret, a tool
or face change, **before any chat send**, and `pagehide`/`beforeunload` via
`sendBeacon` (Starlette's `request.json()` parses the body regardless of
content type, so no backend accommodation was needed). Undo is a client
op-inverse stack capped at 100 — the server never learns anything special
happened.

**Lazy create.** `POST /api/composure/new` writes nothing; the client
carries `pending_path` and puts `create: true` + `form` + `title` on the
first op batch. A composure the user opens and never touches writes no
file. After a create the client fires one throwaway
`GET /api/composure?path=` purely to stamp `composure.last`.

Three registries are the extension points, and **P4c-2 / the council UI
plug into them** without touching anything else:

```js
COMP_MODULE_RENDERERS   type  -> function (module, page, hostEl)
COMP_TOOLS              tool  -> {edit: true}
COMP_FORM_BEHAVIORS     form  -> function ({fresh})
```

**Landing in P4c-2 / the council UI** (seams exist, drawn and disabled
today): the pencil and eraser (`COMP_TOOLS` entries + dropping `disabled`
from `#comp-tool-pencil` / `#comp-tool-eraser`; the stroke layer already
renders read-only), the five **link-in module renderers** (`doc` `wiki`
`weblink` `webframe` `image` — until one exists the type falls through to
`compRenderPlaceholder`), **comments** (`#comp-insp-slot`,
`#comp-comments-btn`), **search** (`#comp-search`), the **journal's** filing
behaviour, and the **council setup card**
(`COMP_FORM_BEHAVIORS.journal` / `.council` both carry a `TODO` naming their
phase; `_default` handles any form with no entry, including project forms).
The backend contracts for all of them are final and documented above.

The base layer also owns the **peek**: `html[data-comp-peek="1"]` hides the
nine stacked mode roots so the canvas shows through, and Esc restores them
before it starts popping the stack. `_modeRender()` appends a permanent
base square to `#mode-stack`, rightmost, **with no exit ribbon** (see "What
NOT to touch").

---

## Councils (the engine, the budget, the lean profile)

A **council** is the multi-readvisor composure form: several readvisors and
the user speak in turn on one canvas, each statement a locked module, and
the whole thing concludes into an answer, a document, or (0.4.0) a new
composure. [enough/council.py](../enough/council.py) is the engine,
[enough/council_api.py](../enough/council_api.py) the HTTP translation.
**The council UI is landing with the council setup card** — the backend
contract below is final.

### The file is the state

One JSON object in `<meta name="composure:council">`. It **is** the state
machine; there is no council state anywhere else, in memory or otherwise.
`council.validate_meta()` normalizes it and **drops unknown keys on
purpose** — a key nobody validates is a key that will one day contradict one
that is. `Council` holds a path and three handles and nothing else, so two
instances over the same path behave identically. That is the whole of "a
restart mid-council loses nothing", and it is why `_RUNS`, `_IN_FLIGHT` and
`_LOCKS` are runtime-only and `reset_runtime()` is safe.

Keys: `input parameters constraints output participants order max_rounds
status round turn cursor next queue brief_module transcript reconvene`.
`status` ∈ `setup | ready | running | paused | concluded`; `order` is
`round-robin`, the only one. Participant kinds are `chief`, `readvisor`,
`user` and **`pal`** — `pal` is reserved for 0.4.0: it validates,
round-trips, and is **ignored everywhere else** (never speaks, never enters
the rotation, never counts toward the budget). `charge` and `reconvene` are
likewise 0.4.0 hooks that validate and round-trip **now**, and `charge` is
already injected into that participant's identity, so a council saved by a
later enough behaves correctly here instead of silently dropping somebody's
accountability.

Refusals are `CouncilError` → 400 with the sentence verbatim: unknown
status / kind / output kind / order; `max_rounds` outside 1–`MAX_ROUNDS_CAP`
(20); more than `MAX_PARTICIPANTS` (12); a participant with no name;
duplicate ids; **two participants with the same name** (statements are
attributed by name); more than one chief; nobody who can speak; a `document`
output with no path or with a `.comp` path.

**Tints** are assigned once at setup and **stored on the participant**, so a
readvisor keeps its colour for the life of the council even when another is
added later: chief `paper`, user `blue`, readvisors
`yellow → green → pink → lilac → orange` cycling in participant order, pal
`gray`, the conclusion `ink`.

### The rotation

`speakers(meta)` is the chief plus the readvisors, in list order — the user
writes its own statements and the pal is reserved, so neither is in the
rotation. A round closes when the cursor wraps to 0, so `/round` means
**finish the current round**.

**A queued user statement takes the next slot**, and committing it does
**not** move the cursor — so after the user speaks, the participant whose
turn it was still speaks next. That is what makes "say something at any
time" an interjection rather than a reshuffle.

`ready` is runnable: pressing *next turn* on a freshly set-up council speaks
rather than lecturing. Only `setup` (a meta written by hand) and
`concluded` (terminal) refuse.

### The budget, and the lean profile

```
n_ctx  = supervisor.current_ctx → llama-server /props → 8192
         (cloud slot: CTX_CLOUD = 32768, a documented constant)
share  = max(512, floor(n_ctx / N))          N = speaking participants
fold when   estimate(messages) > FOLD_AT (0.80) × share
estimate    len(content) // 3                (server.py's own ratio)
```

`CTX_CLOUD = 32768` because the OpenRouter slot has no `/props` and its
models range from 8K to a million: 32 768 is at or under every model the
slot ships a preset for, so a council that fits here fits everywhere, and
being wrong costs a fold that was not needed rather than a hard overflow
mid-turn. The `/props` probe is cached for 60 s (a model switch relaunches
llama-server with a new window).

**The fold is mechanical** — no second LLM call, because a council that
spends a completion summarizing itself pays twice for the same window.
While the estimate is over budget, one more of the oldest statements moves
into a single `user` message (`Earlier in this council: - Name (turn n):
<first sentence>`). **The brief is pinned and never folds, and the most
recent statement is never folded** — a participant that cannot see the thing
it is answering has nothing to say. `MIN_TRANSCRIPT_TOKENS = 1024` is the
floor: once the transcript is down to about two statements the fold stops
even if the total is still over budget, because at that point the *head* is
what is over budget and the head is not foldable. The honest answer there is
a bigger `n_ctx`, and every turn says so on the SSE `end` phase
(`folded`, `tokens`, `head`, `budget`).

**`assemble_system_prompt(project_dir, readvisors="none", profile="council")`
emits who the chief is and nothing else**: the identity preface, Identity,
Motivation, the project description, and the project profile when it is not
the stock template. It omits Active Readvisors, the paradigm and paradigm
catalog, all policies, skills, Current Intention, the tool instructions, the
converted-documents section, the harness context and the drift notice.

That is not thrift, it is correctness: **a council turn calls no tools,
reads no files, switches no paradigm and files no request.** Every omitted
section is instruction for something that cannot happen in the room. The
chief's head went from the whole chat prompt (~21 000 tokens — *larger than
its entire share* at `n_ctx = 32768` with two speakers, so every council
folded to the floor on its third statement) to ~2 400. A readvisor
participant's head is ~575, because its identity has always been just its
own two documents. `profile` defaults to `"chat"`, byte-identical to what
`assemble_system_prompt` has always returned, and `readvisors=` still works
independently.

### Message lists, and cleaning what a model emits

Built **from the transcript in the `.comp`, every turn, from scratch** — a
new `Council` over the same path produces byte-identical message lists. The
perspective flips per participant: **my** statements are `assistant` turns,
everyone else's are `user` turns prefixed `Name: `, so a model reads a
conversation it has been part of rather than a transcript it is being asked
to comment on.

Identities: chief = the lean profile + `chief_framing(chief)`; readvisor =
`readvisor_identity(project_dir, folder)` + the project description +
`readvisor_framing(name, chief)`. **`folder` is why participants carry it** —
a readvisor whose `AGENT.md` has a prettier H1 than its directory name would
otherwise be looked up by display name and find nothing. A participant whose
folder is missing gets an honest one-paragraph stand-in rather than an empty
prompt. Neither path contains a `<tool name=` example or a `# Tools`
section, and `tests/test_prompt_weight.py` pins that.

`strip_tool_calls()` removes complete `<tool …>…</tool>` blocks **and** a
dangling `<tool …>` at the end of a truncated stream, and logs how many —
stripping rather than refusing, because the statement around the call is
usually fine and a council that dies because one participant typed XML is
worse than a council with one thin statement. `clean_statement()` also drops
a self-signature (`Ed: …` from Ed) — the card already carries the name.

### Transcript IO

Every statement lands through `composure.apply_ops(..., source="council")`.
One batch, two ops, one rev, one SSE:

1. `add_module` — `type: text`, `w: 816` (fullport width, so a council reads
   as minutes rather than a board), `h` from `composure.estimate_height`,
   `bg` = the speaker's tint, `title` = `"<name> · turn <n>"`, plus
   `speaker` / `speaker_kind` / `turn`. **Setting `speaker` is what makes
   the module `locked`.**
2. `arrange` — `mode: "column"`, **`pack: true`**, over
   `[brief, …every statement…, the new one]`, anchored at the brief's own
   `x`/`y`. So the transcript is a single column top to bottom however the
   user has been dragging things around, and it re-tidies after a restart.

**The frontend corrects a statement's height with an ordinary
`update_module` geometry op from `source: "ui"`, and nothing special was
needed to allow it.** The council lock (`_check_writable`) is only on the
*content* ops — `set_page`, `add_page`, `remove_page`, `remove_module` — so
`update_module` already accepted geometry, background, scale, title and z on
a locked module. That is the promise: *you can move it, restyle it and
comment on it, but not rewrite it.* One hole was closed to make it safe —
see the `update_module` trap under "What NOT to touch".

`composure.estimate_height(text, width, scale=, pad=, title=)` is the
server's guess: wrap each paragraph at `(width − 2·pad) / (16·scale·0.5)`
chars, blank line between paragraphs, ×1.5 line box, add the static sheet's
padding (72 for a fullport-width module, 16 otherwise), clamp to 120–2400,
round **up** to the 24-unit grid. Deliberately generous — a box slightly too
tall reads as a margin, one slightly too short reads as a bug. Deterministic
and monotone, and `from_outline` uses the same function, so a card and a
statement are wrong in the same direction by the same amount.

### Endpoints

| Route | Method | Notes |
|---|---|---|
| `/api/council/setup` | POST | Creates the composure from the `council` form when the path does not exist, **in the same atomic batch as the meta** — a refused setup writes nothing at all. 409 when the output document exists and `overwrite` was not sent, or when already concluded |
| `/api/council/state?path=` | GET | The same body `/setup` returns. Cheap — reads the file and at most the cached `/props` probe, assembles no prompt, **safe to poll** |
| `/api/council/participants` | GET | The setup card's starting checklist: the chief, every **enabled** readvisor (display name from its `AGENT.md` H1, `folder` for the engine), and the user, tints already assigned |
| `/api/council/convene` · `/pause` | POST | `pause` cancels a background `/run`; **the turn already streaming finishes and is committed** — a half-written statement thrown away is a worse surprise than one extra paragraph |
| `/api/council/next` · `/round` · `/run` | POST | one turn · to the end of the round · a background task to `max_rounds` (returns at once, reports over SSE). 409 when this council is already running |
| `/api/council/say` | POST | Always queued first, then drained immediately when no turn is streaming. So the common case is "it appears now", the racy one is "it appears next", and neither is "it is lost" |
| `/api/council/conclude` | POST | One chief turn under `conclusion_framing`, committed tinted **`ink`**. Then: `answer` → that module *is* the output; `document` → written through **`tools.run_write_file`**, the same door and guards as the tool, then a `doc` link-in module under the conclusion; `composure` → **501 before the turn runs**, so nothing is spent and the council stays runnable |

Setting a council meta on an existing non-council composure is allowed; its
`form` stays whatever it was, and **the frontend keys off `council` being
non-null, not off `form == "council"`**.

### The `council` SSE event, and the exclusions

```jsonc
// event: council
{"path": "…", "phase": "start"|"token"|"end"|"error"|"status",
 "turn": 3, "speaker": "Nadia", "speaker_kind": "readvisor",
 "text": "…",                                        // token | end | error
 "module": "m5", "rev": 7,                            // end
 "folded": 2, "tokens": 15012, "head": 14180, "budget": 13107,  // end
 "status": "running", "round": 1, "next": "chief", "next_name": "Ed"}
```

Every committed batch **also** fires the ordinary `composure` event with
`source: "council"`, so the canvas refreshes the new module exactly the way
it refreshes any other batch. The `council` channel is for the streaming
text and the controls; the `composure` channel is for the document.

- **A council turn holds `session.generation_lock`** for the whole streamed
  completion, so an ordinary chat turn cannot overlap it.
- **`/api/chat` while a council turn streams** refuses politely — see step 0
  of "The request lifecycle".
- **A council control while a chat turn streams** is 409 ("your readvisor is
  answering in the chat right now — councils and the chat share one
  model…"). `/say` and `/state` are exempt: queueing a statement and reading
  state cost no model time. A second council control while a council turn
  streams is also 409, and turns on one path are additionally serialized by
  a per-path `asyncio.Lock`.
- **The auto-reset / context-pressure machinery never sees council
  traffic.** It reads `session.history` and `session.last_usage`; council
  turns touch neither.

Transcripts export to `rness/knowledge/councils/<YYYY-MM-DD>-<slug>.md`,
never overwriting (a second export the same day gets `-2`).

### `composure_from_outline` and the `scaffold` skill

Small local models are unreliable at long chains of module tool calls — ask
for fourteen cards and you get nine, two in the wrong group and one a
duplicate. Ask for one markdown outline and they do fine. So structure is
produced as markdown, in one shot, and converted **deterministically**: ids
are `m1…mN` in creation order and every coordinate is a function of the
text, so the same outline always produces the same document.

```
# The title of the composure        one line, the title
## A group                          a column (scaffold) or a row (cards)
### A card                          a card; the text beneath it is its body
- A top-level list item             also a card; indented lines are its body
### [gap: what is missing?]         tinted orange, titled "gap"
```

`####` and deeper, tables, nested list items and front matter are **not**
structure — they stay in the body as the text they are. A `###` before any
`##` opens an implicit group named `Cards`. Text before the first card is
preamble and is dropped. A gap card keeps its bracketed question as the
**first line of its body** — losing the question would make the most useful
card on the canvas the only blank one.

The grammar is exactly what `defaults/skills/scaffold/SKILL.md` teaches, and
**the skill's two worked examples in `references/structure.md` are lifted at
test time and used as fixtures**, so the skill cannot drift away from the
parser without `tests/test_composure_outline.py` going red. Layout
constants (`CARD_W` 320, `HEADER_H` 96, `CARD_GAP` 24, `COL_GAP` 48,
`BAND_GAP` 72, `MAX_CARDS_PER_COLUMN` 12, `CARD_H_MAX` 600) live in
`composure.py`; a `scaffold` puts `premise`/`logline`/`thesis` in a top band
and `ending(s)`/`denouement(s)`/`resolution(s)`/`close` in a bottom row, and
wraps a group over 12 cards into a continuation column with its own
`<name> (cont.)` header.

**The form supplies the kind and the styling, not its placeholder modules** —
every shipped form ships content, and `from_outline` removes it in the same
atomic batch, because a scaffold of somebody's actual story should not
arrive with "Act one goes here" still sitting on it.

```python
composure.parse_outline(markdown) -> OutlineDoc              # pure parse
composure.outline_ops(doc, form, clear_ids=[]) -> list[dict] # the op batch
composure.from_outline(title, form, markdown) -> Composure   # both, in memory
```

`from_outline` is the pure half — a `Composure` you can render, diff or
assert about, with no file and no project. The tool applies the same
`outline_ops` through `apply_ops`, so the write goes through the one door
like everything else.

---

## Girraphs (the IBIS-map primitive)

A girraph (pronounced "graph") is a plain-text argument map in a
`.girraph` file: issues `?`, positions `!`, supporting/objecting
arguments `+`/`-`, notes `.`, nested girraphs `@`. Nodes are
one-per-line with stable broker-assigned IDs, `< parent` tree edges,
`[-> id]` cross-edges, `ref:<path>` transclusions (markdown doc or
another `.girraph` — that's the recursion), `by:<slug>` attribution,
and optional indented detail blocks collected at the end of the file.
User-facing explainer: [docs/HELP_CENTER.md](HELP_CENTER.md) §16.

Format spec (formerly docs/girraph-plan.md, folded in here):

```
%girraph 0.1
title: Should enough ship a plugin API?
next: q2 p3 a4 n2 g2

q1 ? Should enough ship a plugin API?
p1 ! Ship a minimal one < q1
a1 + Ecosystem growth needs stable hooks < p1 by:graham
a2 - API surface = forever maintenance < p1 by:open-skeptic
n1 . Background reading < q1 ref:rness/knowledge/plugins-survey.md
g1 @ Subproblem: versioning < p1 ref:rness/girraphs/versioning.girraph

q1 >
  Indented free-form detail block under `id >`. Markdown allowed.
```

- **Header**: `%girraph 0.1` magic line (required, first), optional
  `title:` and `next:`, then a blank line. `next:` is the
  broker-maintained per-prefix high-water-mark list that makes "IDs are
  never reused" a guarantee; absent (hand-authored file) the broker
  derives max+1 and adds it on first write.
- **Node record**: `<id> <sigil> <label> [modifiers...]`, one per line.
  `id` is `[a-z]+[0-9]+` (conventional prefixes: `q` issue, `p`
  position, `a` argument, `n` note, `g` nested girraph; any prefix
  legal). Sigils: `?` issue ❓, `!` position 💡, `+` support ➕,
  `-` objection ➖, `.` note 📄, `@` nested girraph 🦒 (must carry a
  `ref:` to a `.girraph`).
- **Modifiers** (stripped right-to-left off the line end; the rest is
  the label): `< <id>` parent edge (at most one), `[-> <id>]`
  cross-edge (repeatable; ASCII canonical, `[→ id]` accepted),
  `ref:<path>` transclusion (project-root-relative; markdown doc or
  another `.girraph` — same mechanism, that's the recursion),
  `by:<slug>` attribution (`user`, `agent` — the on-disk literal, unchanged
  because it is data — or a readvisor name).
  Canonical order: `id sigil label < parent [-> x] ref:… by:…`. A label
  *ending* in modifier-shaped text will be misparsed as metadata —
  known plain-text tradeoff; tools always serialize canonically.
- **Detail blocks**: `<id> >` + indented lines; parser accepts them
  anywhere, canonical serialization collects them at end-of-file in
  node order.
- **Root**: the first parentless node (derived — no `root:` header).
  Multiple parentless nodes = a forest. Parent edges are validated
  acyclic per file; cycles via `ref:` are legal and the navigator's
  visited-set handles them.
- **remove_node semantics**: no orphaning, ever — removing a node with
  children errors and lists them unless `<cascade>true</cascade>`;
  cross-edges pointing at removed nodes are deleted from their source
  lines (journaled); `<confirmed>yes</confirmed>` must reflect explicit
  user confirmation this turn.
- Prior art: Argdown (sigils, plain-text spirit) — but explicit parent
  edges instead of indentation, so every node line is independently
  patchable by a small model; stable IDs instead of title strings.

Architecture notes:

- **`enough/girraph.py` owns the format.** Nothing else parses or
  writes `.girraph` content. The readvisors' five tools (`tools.py`) and
  the UI's `/api/girraph*` endpoints (`server.py`) both call its
  node-level ops under `girraph.path_lock()` — that's the concurrency
  story (last-write-wins at node granularity) for simultaneous
  user-panel and readvisor edits.
- **Whole-file writes are denied** for `.girraph` paths in both
  `run_write_file` and `POST /api/file`. Files remain the source of
  truth (a text editor outside the harness can still edit them);
  any index is a derived, disposable cache.
- **IDs are never reused.** The `next:` header line carries per-prefix
  high-water marks maintained by the broker; `assign_id()` honors it
  even after the max-numbered node is deleted.
- **Round-trip safety.** Unparsable lines are preserved verbatim and
  surfaced as warnings — the serializer never destroys content it
  didn't understand. Tests in `tests/test_girraph*.py` pin this.
- **The UI panel** (`#girraph-mode` in index.html, `gp*` functions) is
  a full-frame mode alongside the unified read/edit mode, merirmaid, and
  cacheawl. Breadcrumb stack navigation through `@`/doc refs; pushing an
  already-visited path pops back to it, which is what makes cyclic refs
  navigable.
- **The default skill** `defaults/skills/girraph-merirmaid/` (renamed
  from `ibis-girraphiti` in 0.1.6) carries the IBIS discipline
  (anti-solution-jumping, the user-confirmation stopping rule, `by:`
  etiquette) *and* the Mermaid-generation rules for merirmaid files, with
  `references/` docs for both. Disabled by default like all new globals —
  and because the rename creates a fresh global, existing projects get it
  defaulted off (re-enable in the sidebar).
- **Mermaid export is no longer a girraph TODO.** It shipped in 0.1.6 as
  the sibling **merirmaid** primitive (see the merirmaid section below) —
  a girraph is not converted to Mermaid; the two are separate formats for
  separate jobs. Still out of v1 scope for girraph: a query engine (grep
  suffices; an embedded index like Kuzu could later be added as a derived
  cache without migration pain).
- **Girraph → merirmaid mirrors (0.1.7).** A girraph can grow a linked,
  auto-regenerating Mermaid mirror: `girraph.to_mermaid()` renders a full
  `.merirmaid` text (frontmatter `modality: mirror`, `kind:
  girraph-mirror`, `source: <girraph path>`; issue `{{…}}` hexagon,
  position `([…])` stadium, support/objection rects with green/red
  stroke-only classDefs, note `(…)`, nested girraph `[[…]]`; tree edges
  `-->`, cross-links `-.->`; `click <id> "<path>"` for every ref). The
  sibling-path rule: `<dir>/<base>.merirmaid` next to the `.girraph`;
  the link exists ⇔ that file exists AND its frontmatter says
  `kind: girraph-mirror`. `POST /api/girraph/merirmaid` creates it
  (409 if a non-mirror file claims the name); `GET /api/girraph`
  returns a `merirmaid` field for the UI's add/open toolbar button.
  After every successful girraph mutation through ANY door (the
  `/api/girraph/*` node ops and the girraph tool runners),
  `girraph.refresh_mirror(path)` regenerates the sibling if it exists,
  inside the existing `path_lock`. External text-editor edits to the
  girraph do NOT auto-refresh — the next harness mutation catches up
  (same reconcile philosophy as cacheawl).

---

## Merirmaid (the Mermaid-diagram primitive)

A `.merirmaid` file is a Mermaid diagram with a small frontmatter header,
rendered to SVG live in the browser by a **vendored** (local, no CDN)
`enough/static/mermaid.min.js` (v11.16.0, MIT — shipped like
`htmx.min.js`). The paradigm-shift from girraph: there is no owning
Python module for the *format* — the source is plain text a readvisor
writes with `write_file` and the frontend renders. The backend code that
touches `.merirmaid` content is the cachebox mirror generator in
`cacheawl.py` and the girraph-mirror generator in `girraph.py`.

Format (formerly docs/merirmaid-plan.md, folded in here):

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
```

`merirmaid: 1`, `title`, and `modality` are required; unknown keys are
preserved. Everything after the closing fence is verbatim Mermaid
source, any diagram type. Diagrams link via Mermaid `click` interactions
with a relative path (`click A "other.merirmaid"`); targets may be
`.merirmaid`, `.girraph`, or `.md` — the viewer intercepts and pushes
onto its breadcrumb stack. `node-char-limit` is soft: the in-node editor
shows a live count and warns past it but doesn't block; readvisor-authored
diagrams should stay well under it (leave room for user edits).

Architecture notes:

- **Two modalities, in the frontmatter.** `modality: wip` is a working
  whiteboard — node *label* text is user-editable in merirmaid mode (with a
  live char count vs the soft `node-char-limit`); structure edits are
  readvisor-only, asked for in the readvisor panel (the per-mode chat pills
  are gone — see "The readvisor panel"). `modality: mirror` is a source-of-truth
  diagram of some external structure (the launch case: a cachebox's
  contents) — **read-only** in the UI, regenerated only by the system that
  owns the mirrored structure.
- **Whole-file writes are allowed** (unlike `.girraph` — no broker-assigned
  IDs to protect), with exactly one exception: `run_write_file` and
  `POST /api/file` refuse to modify a file whose frontmatter says
  `modality: mirror` *and* which lives under `~/enough/cacheawl/`. That
  guard is `cacheawl.mirror_write_denial(target)` (returns the denial string
  or `None`); both write paths call it.
- **Merirmaid mode** (`#merirmaid-mode` in index.html) is a full-frame mode
  like girraph mode: lazy-loads mermaid.js on first open, renders the SVG,
  intercepts Mermaid `click "path"` interactions to push targets onto a
  breadcrumb stack (`.merirmaid`/`.girraph`/`.md`), and shows the raw source
  in a `<pre>` on a render error instead of a blank pane. Active-mode icon
  top-right with the exit ribbon, per the mode conventions (see "Change the
  UI").
- **The girraph-merirmaid skill** carries the Mermaid-authoring rules
  (stay well under `node-char-limit` to leave room for user edits, etc.).
- **Two faces, one viewer (0.1.7).** `modality` drives the chrome:
  `mirror` → view-only face (cool/slate toolbar tint, "mirror" badge,
  no label editing — forced regardless of source); `wip` → edit face
  (warm/amber tint, in-place label editing). Shift-click any node opens
  a per-node action menu filtered by type — folder: copy path / open in
  cacheawl; file: copy path / copy contents / open in its natural mode
  via the `cacheawl:` scheme. The menu resolves nodes through the
  mirror payload's `node_map` (`{nodeId → {path, is_dir}}`).
- **On-demand sub-folder mirrors.** Only the box-root
  `_cachebox.merirmaid` is persisted; `GET /api/cacheawl/mirror?box=…
  &path=…` generates subtree mirrors fresh per request (never written
  to disk). The 30px **squircle** launcher on cachebox headers and
  folder tiles opens these in the view-only face.

---

## Wikisink (local offline Wikipedia)

The 🚰 subsystem: a Kiwix `.zim` archive of (a slice of) English
Wikipedia, read in place via `libzim`, browsable in-app, searchable and
readable by the readvisors, annotatable with comments, and refreshable
against live Wikipedia. User-facing doc: [docs/WIKISINK.md](WIKISINK.md).
All code lives in the [enough/wikisink/](../enough/wikisink/) package;
`server.py` mounts the `/api/wiki/*` endpoints and hides wikisink dirs
from the file tree.

Architecture notes:

- **`wikisink/config.py` owns all state** — one JSON file at
  `~/enough/config/wikisink.json` (schema **v2**). It is user-global,
  not per-project: every project shares the same archives, watch
  registry, comments, and overrides. `ENOUGH_WIKISINK_CONFIG` overrides
  the path (test/dev hook — use it; never touch real user state in
  tests).
- **Multiple installs, one active.** `installs[]` is a registry of base
  archives, each with its own `storage_dir` (internal disk, external
  drives, anywhere); `active_install` names the one being served.
  Installs are **only created by completed downloads** (there is no
  adopt-existing-file path) and "forget" only unregisters — the `.zim`
  file is never deleted, except an old snapshot after an explicit
  in-place upgrade (`replace_id`).
- **Availability is a live property, not an error.** An install whose
  file isn't reachable (drive detached) stays registered.
  `config.installed()` = active archive servable *right now*;
  `config.configured()` = any install registered;
  `config.unavailable_reason()` = the user-facing explanation
  distinguishing never-installed from drive-detached. `zim.py` raises
  `WikisinkUnavailable` with that reason; endpoints surface it as a 503
  with an actionable message.
- **`volume_mounted()` guards every mkdir** under user-chosen paths.
  Without it, `mkdir -p /Volumes/<name>/...` while a drive is detached
  silently plants a phantom directory on the macOS boot volume that
  shadows the next mount. If you add any code that creates directories
  under a wikisink path, route it through the config helpers or apply
  the same guard.
- **Archives vs data.** Each install's `storage_dir` holds only the
  `.zim` and its resumable `downloads/*.part`. The user's own data
  (comments, overlays, preserved articles, rankings, run state) lives
  under `data_dir` — local disk for fresh setups, so it survives drive
  detachment; pre-v2 configs keep data beside their original archive
  location (migration moves no files). Reads from an unreachable data
  dir degrade gracefully (empty stores); writes fail loudly.
- **v1 → v2 migration is automatic and one-way** (`config._migrate_v1`),
  runs inside `load_config()` when an on-disk config has `version < 2`,
  and persists on the next `save_config()`. Don't reintroduce the old
  top-level `storage_dir` / `zim` keys — `active_zim_meta()` is the
  compat shim for provenance strings.
- **Switching installs is deliberately UI-only** (like deletion
  overrides): `POST /api/wiki/installs/activate`, driven from the
  installs manager in the 🚰 modal. The `wiki_status` tool reports
  install availability and tells the readvisor to *suggest* the modal —
  there is intentionally no readvisor tool for switching, forgetting, or
  overriding.
- **`/api/wiki/*` endpoint map**: `status` (installs + availability +
  counts; must stay instant — no network), `article`, `search`,
  `suggest`, `random`, `comments` (+ reply), `save`, `saved` (GET —
  render a saved folder through the reader's sanitize pipeline; works
  archive-less), `unsave` (POST — delete a saved folder + registry
  tag), `flavors`, `diskspace`, `setup` (start download; optional
  `replace_id`; 409s on duplicate target),
  `download/{pause,resume,cancel}`, `installs/activate`, `installs`
  (DELETE = forget), `overrides`, `override`, `wikisink` (the update
  run), `newer-snapshot` (0.2.2 — the reader's throttled check; see
  below).
- **The reader's newer-snapshot check (0.2.2).**
  `download.newer_snapshot_throttled(cfg, max_age_s=86400)` →
  `{"newer": entry|None, "checked_at": iso|None, "checked": bool}`. No
  install → answers `None` without asking anything. Inside the window →
  cached-only, never network. Outside → one live listing fetch, then it
  stamps the clock **even on failure**, so an offline machine retries
  tomorrow rather than on every reader open. Exceptions are swallowed and
  logged. The clock is `listing_checked_at` (ISO8601 UTC), a top-level key
  in `~/enough/config/wikisink.json` declared in `config._defaults()` —
  `save_config` drops unrecognised keys, so a new key has to be declared
  there or it silently evaporates. Exposed as `GET /api/wiki/newer-snapshot`;
  this could **not** fold into `/api/wiki/status` (documented instant and
  network-free) or `/api/wiki/flavors` (unthrottled, and the setup wizard
  wants a forced live fetch). The reader paints what it already knows on
  `enterWikiMode()`, then fires the check in the background — never blocking
  render, silent on failure.
- **The reader badge shares the manage list's upgrade path.** The badge
  (`#wiki-newer-badge` in `.wiki-toolbar`) is visible only when the entry's
  flavor matches the *active* install's. Click → `confirmOverlay` → the
  existing `POST /api/wiki/setup` with `replace_id`, i.e. the identical
  in-place swap the 🚰 manage list arms (`wikiStartReplace()` was split into
  `wikiPrepReplace(nsOpt)` + confirm copy so both callers can't drift).
  During the download the badge is the progress readout off the existing
  **`wiki_download`** event — note `wiki_sink` is the update-*run* event, not
  the download one — and hides on `done`. It stays silent for a first-ever
  archive download. There is deliberately **no readvisor tool** that swaps a base
  archive; the `wikisink` run only *reports* that a newer snapshot
  exists (same rule as install switching and deletion overrides).
- **Save targets, two of them.** A save goes either to the project
  (`<project>/wiki/<slug>/`) or to the machine-global wiki cachebox
  (`~/enough/cacheawl/wiki/<slug>/`) — the reader's single save button
  opens a two-choice flyout. `save.save_article(project_dir, path, dest)`
  takes `dest` in `{"project", "cacheawl"}`; the frontend still sends the
  legacy value `"infoworld"`, which `save.py` accepts as an **alias** for
  `"cacheawl"`. The global destination moved from `~/enough/infoworld/wiki/`
  to the cacheawl store in 0.1.6 (the whole infoworld library dissolved
  into cacheboxes — see the Cacheawl section).
- **Saved articles are verbatim HTML folders, not markdown.** The
  stored `article.html` is the archive/overlay copy byte-for-byte
  (plus an attribution comment); sanitization happens at *view* time
  via `GET /api/wiki/saved`, so saved articles render identically to
  live browsing. Don't convert saves to markdown — that loses complex
  tables and invites hand-edits that drift from the archive. Markdown
  exists only as the readvisor-facing text pipeline
  (`save.article_markdown()`, used by `read_wiki_article`'s cache).
- **The reader caches one `Archive` handle** (`zim.py` module singleton
  under a lock). It is dropped whenever the file goes missing and on
  `reset_archive()` (called after installs change) — a remounted drive
  must never reuse a dead file handle.
- **Frontend states** for the 🚰 modal (`setWikiSetupState` in
  index.html): `manage | choose | confirm | downloading | paused |
  error | done`. `manage` is the installs list (availability dots,
  switch/forget, newer-snapshot upgrade offer); `choose` is the flavor
  wizard, reached on first-ever setup or via "+ add an install".
  Download progress streams over the `wiki_download` SSE event.

---

## Cacheawl (the machine-global file store)

The store at `~/enough/cacheawl/` where the user keeps text forever. All
code lives in [enough/cacheawl.py](../enough/cacheawl.py); `server.py`
mounts the `/api/cacheawl/*` endpoints and hides the store from every
project tree (like wikisink dirs).

The `/api/cacheawl/*` endpoint map (the contract the UI was built
against, formerly docs/cacheawl-plan.md):

| Endpoint | Method | Purpose |
|---|---|---|
| `tree` | GET | Split-view payload: project tree + every cachebox summary+tree in one call. Reconciles every box first. |
| `create` | POST | `{name}` → new empty box. Names: letters/digits/spaces/hyphens/underscores, no leading symbol, ≤64 chars; 400 on bad/duplicate. |
| `rename` | POST | `{name, new_name}`; 400 if the target exists. |
| `delete` | POST | `{name, confirm: true}` — unconfirmed → 400; permanent whole-folder delete; UI gates behind a confirm dialog. |
| `transfer` | POST | `{op: copy\|move, src, dst, overwrite?}` — each side `{root: project\|cachebox, box?, path}`. Traversal-checked both sides; sidecars refused; no clobber without `overwrite: true`; regenerates mirrors for boxes touched (`result.boxes_updated`). |
| `ingest` | POST | `{box, type: path\|url\|wikisink, value, depth?\|all?}` — box registered `ingesting` synchronously, work in background. `all` invalid for wikisink. |
| `ingest-status` | GET | `?box=` — poll while `ingesting`; failure ends `status: "failed"` + `ingest.error`, never a phantom complete. |
| `mirror` | GET | `?box=&path=` — the box-root `_cachebox.merirmaid` (path empty; reconciled first) or an on-demand, never-persisted subtree mirror. Payload carries `text`, `node_map`, `modality`, `subpath`, `box_path`. Read-only. |

Cachebox summary fields worth knowing: `origin.type` ∈ `folder` |
`path` | `url` | `wikisink` | `infoworld-migration`; `origin.depth` is
1–3, `"all"`, or null; `status` ∈ `complete` | `ingesting` | `failed`;
`ingest.phase` walks queued → starting → copying/crawling/expanding →
capped/complete/failed. Tree nodes: `{name, path, is_dir, size,
is_mirror, children?}` — folders before files, each group alphabetical;
`is_mirror` routes to the merirmaid viewer, never the text editor.
Ingest semantics: `path` copies text files (binaries skipped by
extension + null-byte sniff), never follows symlinks out of the source
root; `url` is a same-origin crawl to `depth` link layers, robots.txt
respected, pages pandoc'd to markdown; `wikisink` fuzzy-matches an
article then expands crosslinks `depth` layers.

- **A cachebox is a root-level folder** in the store. Only direct children
  of `cacheawl/` are cacheboxes; anything deeper is a plain folder. Some
  boxes are plain kept-forever text; others are **cached replicas** ingested
  from a `path` / `url` / `wikisink` source recorded in `origin`.
- **`cacheawl.py` owns everything under the store.** Nothing else writes
  there. The root is resolvable via `ENOUGH_CACHEAWL_ROOT` (a test/dev hook
  mirroring `ENOUGH_WIKISINK_CONFIG` — use it; never touch real user state
  in tests).
- **Two backend-owned sidecars per box, both write-refused.**
  `.cachebox.json` is hidden metadata (origin, status, timestamps, a tree
  fingerprint used by reconcile). `_cachebox.merirmaid` is an
  auto-generated `modality: mirror` diagram of the box, regenerated on every
  backend mutation. **Both the readvisors' `write_file` and `POST /api/file`
  refuse to modify them** — the mirror via `mirror_write_denial()` (`403` /
  tool error telling the caller to change the box contents instead), the
  `.cachebox.json` by name. Don't add a code path that writes them from
  anywhere but `cacheawl.py`.
- **The `cacheawl:<box>/<rel>` path scheme.** `server.py`'s
  `_resolve_project_path` accepts virtual paths prefixed `cacheawl:` and
  resolves the remainder against `cacheawl.root()` — that's how cacheawl
  mode launches store files into the read/edit, girraph, and merirmaid
  modes without global-path endpoints. Same traversal rules apply inside
  the store (absolute / `..` / empty → `400`); the mirror + sidecar
  write-guards downstream see the resolved target and keep applying. In-tree
  relative paths never reach the store — the prefix is the only door.
- **Ingest runs in the background.** The box is registered synchronously
  with `status: "ingesting"` before the response returns (so
  `GET /api/cacheawl/ingest-status?box=…` is immediately pollable); the work
  runs in a thread. On failure the box ends `status: "failed"` with
  `ingest.error` set — never a phantom "complete". Hard caps live in
  `cacheawl.py` (`INGEST_URL_PAGE_CAP` ~500, `INGEST_WIKI_ARTICLE_CAP` ~200,
  `INGEST_PATH_FILE_CAP`). URL ingests reuse the shared `fetch_url` plumbing,
  so they honor the `fetch_url_*` toggles *on top of* `cacheawl_enabled`.
- **Reconcile keeps mirrors honest.** `GET /api/cacheawl/tree` (and the
  `cachebox_list` tool) call `reconcile()` / `reconcile_all()` first — a
  cheap fingerprint check that regenerates a stale mirror so manual file
  drops the backend didn't perform show up.
- **Transfer is single-item.** `POST /api/cacheawl/transfer` copies/moves a
  file or folder between the project and a box (either direction) or between
  boxes; traversal-checked on both sides; sidecars can be neither source nor
  destination; refuses to clobber without `overwrite: true`.
- **The infoworld migration.** On first 0.1.6 launch,
  `cacheawl.migrate_infoworld()` (called from `create_app`'s startup)
  dissolves `~/enough/infoworld/{personal,public,wiki}` into three
  same-named cacheboxes. Idempotent and **move-only** (`os.rename` within a
  volume; cross-volume copies-then-verifies before removing the source). A
  missing infoworld root is a clean no-op; an already-migrated box is left
  alone. The source root honors `ENOUGH_INFOWORLD_ROOT` (paired test hook)
  so suites never move the real library. Global wiki saves that used to land
  in `~/enough/infoworld/wiki/` now land in the `wiki` cachebox; `"infoworld"`
  survives as a legacy `dest` alias in `save.py`.
- **The UI** is a full-frame split-view mode (`#cacheawl-mode` in
  index.html): a project pane and a cachebox pane, drag-to-copy /
  shift-drag-to-move (both mapping to `transfer`), an ingest bar that
  composes a chat request into the readvisor panel, and per-file open into the natural mode
  via the `cacheawl:` scheme. Ingest progress is **polled**
  (`ingest-status`), not streamed, in v1.

---

## Document conversion (twins, engines, the `pdf` extra)

0.2.5. enough does not render PDFs or lay out Word files; it converts them
to markdown you can edit and exports the edits back.
[enough/convert.py](../enough/convert.py) owns the policy,
[enough/convert_worker.py](../enough/convert_worker.py) does the work in a
child process. Design record: `docs/convert-plan.md` (local planning doc,
untracked) — its four "landed" blocks are the final word where the earlier
sections disagree.

**Vocabulary, used identically in code, UI, and help:** *original*
(`memo.docx`, never rewritten except by an explicit overwrite-export),
*twin* (`memo.docx.md`, the editable markdown), *assets*
(`memo.docx.assets/`, pictures lifted out), *manifest*
(`.memo.docx.convert.json`, the hidden sidecar), *engine* (`pandoc` |
`docling`, plus `typst` for PDF export).

**Naming is the pairing** — there is no database and no watcher. `twin =
<original name> + ".md"`, so it can never collide with a real `report.md`;
assets and manifest derive the same way (`convert.twin_path()` /
`assets_dir()` / `manifest_path()`). `pair_for()` accepts *either* end of the
pair (or a plain `.md`), so no caller has to know which handle it holds.
`_walk_tree` hides the twin, the assets dir and the manifest and hangs the
attributes below on the original's row.

### The registry

`convert.FORMATS: dict[str, FormatSpec]` — seven extensions, each with
`label`, `reader`, `writer`, `sync_ok`, `notes`. It is the **single** source
for the file-type question, rendered by `formats_view()` into
`GET /api/convert/formats`, and from there into (a) the export modal, (b) the
`{{convert-formats}}` help token, and (c) `prompt.convert_instructions()`'s
generated system-prompt section. **Never hand-list extensions anywhere** —
not in help text, not in the prompt, not in a modal.

pandoc owns the round-trippable office/ebook family in **both** directions
(`.docx .odt .rtf .epub`); docling owns `.pdf .pptx .xlsx` **read-only**;
PDF *export* is pandoc `-t typst` → `typst.compile()`. A docx never goes
through docling — one tool both ways is what keeps the round trip
self-consistent. `notes` is user-facing copy, not a comment.

### Engines and their probes

| Engine | Probe | Notes |
|---|---|---|
| pandoc | `pandoc_path()`: `shutil.which("pandoc")` → `pypandoc.get_pandoc_path()` → `None` | Base dependency (`pypandoc-binary`). A Homebrew pandoc the user chose wins; the wheel's copy is the floor. `engines()["pandoc"]["where"]` is `"path"` or `"bundled"` — never `"brew"`, which would be a guess. **"pandoc unavailable" is an anomaly (a broken venv), never a normal state** — help text must not describe it as one |
| typst | `typst_path()` (CLI) or the `typst` wheel | Base dependency. The wheel installs a Python module and **no console script**, so `--pdf-engine=typst` is unavailable; only the wheel route is implemented |
| docling | `docling_available()` = `DOCLING_ENGINE_WIRED and docling_installed() and docling_models_present()` | The `pdf` extra. `docling_installed()` (packages) and `docling_models_present()` (weights on disk) are reported separately so the UI can say which half is missing |

All three are cached in one module-level `_engine_cache`; **`reset_engines()`
after an extras install** is what makes the engines flip without a server
restart. `DOCLING_ENGINE_WIRED` is a deliberate constant, not dead code: it
is the one lever that turns PDF reading off in a build, and `engines()`
reports it as `wired` so the UI can distinguish "no engine in this build"
from "engine present, models missing". `engine_missing_message()` therefore
has **two branches** — extra absent, and extra present but weights absent —
and any copy that only says "install the PDF extra" is wrong for the second.

### States and the manifest

`convert.STATES` = `fresh` · `edited` · `stale` · `conflict` ·
`unconverted` · `engine-missing`. `state(original)` compares the original's
and the twin's `(size, mtime_ns)` against the manifest and hashes only when
those moved. One self-heal write: when a stat moved but the sha256 didn't (a
Finder touch, a `cp -p`) the cached stat is rewritten and the file counts as
unchanged — so `state()` is *almost* pure, and the write is wrapped so a
read-only volume degrades to "right answer, cache didn't stick".

`has_twin()` requires **original + twin + manifest**, all three. A
hand-written `notes.pdf.md` with no manifest is an ordinary visible markdown
file, not a hidden twin.

Manifest (`schema: 1`, tmp+rename, unknown schema reads as *absent* →
re-convert rather than raise):

```jsonc
{"schema": 1, "original": "memo.docx", "twin": "memo.docx.md",
 "assets": "memo.docx.assets" | null, "engine": {"name": "pandoc", "version": "3.9",
 "ocr": "ocrmac" | "rapidocr" | null},          // ocr is recorded for .pdf only
 "converted_at": "…Z",
 "source": {"sha256": "…", "size": 0, "mtime_ns": 0},
 "twin_sha256": "…", "twin_size": 0, "twin_mtime_ns": 0,
 "sync": false, "last_export": {…} | null}
```

### The worker protocol

`sys.executable -m enough.convert_worker`, one job in as JSON on **stdin**,
newline-delimited JSON out on **stdout**, exit. Nothing in the worker is
imported by the server process — that is the point (torch is heavy, a
converter crash must not take the server down, a fresh install needs no
restart, and cancel is a `kill` rather than a cooperative flag nobody could
honour mid-pandoc). stderr is folded in as a diagnostic tail only, because
torch and transformers narrate their warm-up there.

```jsonc
// in  (one line, on stdin) — ops in convert_worker._OPS
{"op": "convert", "original": "…", "twin": "…", "assets": "…", "engine": "pandoc"}
{"op": "export",  "twin": "…", "out": "…", "target": ".docx",
 "resource_path": "…", "reference_doc": "…"|null}   // reference_doc: .docx/.odt overwrite only
{"op": "prefetch", "artifacts_dir": "…"}      // the pdf extra's model download
// out (NDJSON, on stdout)
{"event": "progress", "pct": 0-100|null, "message": "…"}
{"event": "done", "result": {…}}
{"event": "error", "error": "…"}
```

Twins are written as **`TWIN_FORMAT = "gfm-raw_html+footnotes"`**: the gfm
writer otherwise emits raw HTML for anything markdown can't express
(`<figure>` around captioned images, odt's empty anchor spans) and
`renderMarkdown` escapes raw HTML, so those would render as literal angle
brackets. Readers are untouched. Both engines land on **one** asset layout —
flat, relative, `![alt](memo.docx.assets/img-1.png)` — via `_flatten_media`
(pandoc mirrors the container's folders) and `_relink_docling_assets`
(docling writes absolute paths and 80-char content-hash filenames). Docling
runs in-process with `generate_picture_images=True`, `images_scale=2.0`,
`image_placeholder=""`, and a `_Heartbeat` thread for progress, since
`DocumentConverter.convert()` takes no callback.

### Endpoints

| Endpoint | Method | Shape |
|---|---|---|
| `/api/convert/formats` | GET | `formats_view()`: `{formats: [...], export_targets, image_exts, engines}` — the one source described above |
| `/api/convert/status` | GET | `?path=` either end of the pair → `{state, manifest, spec, …}` |
| `/api/convert` | POST | start a job (`{path, force?}`) → `{job}`. **Per-path**, not one-at-a-time: 409 only when a job for *that* path is running (claimed under a lock, so a double-click can't start two) |
| `/api/convert/job/{id}` | GET | snapshot — the polling backstop for the SSE |
| `/api/convert/job/{id}/cancel` | POST | kills the worker; leaves nothing behind |
| `/api/convert/export` | POST | `{path, target, mode: "copy"\|"overwrite"}`. A failed overwrite restores the original from its `.undo` stash before re-raising |
| `/api/convert/sync` | POST | flip "keep the original in sync" (pandoc-family formats only) |
| `/api/convert/resolve` | POST | `{choice: "keep"\|"export"\|"reconvert"}` for a `conflict`/`stale`; `reconvert` stashes the old twin to `.undo` first |
| `/api/convert/install` + `/install/status` | POST/GET | the `pdf` extra installer (single-slot) |
| `/api/file/blob` | GET | raw bytes for the image viewer / view-original, from an explicit extension→type table (`convert.BLOB_MEDIA_TYPES`), **not** `mimetypes.guess_type`. Always `X-Content-Type-Options: nosniff`; SVG additionally carries `convert.SVG_CSP`; `text/html` is unreachable by construction (415). `&meta=1` returns `{path, size, media_type, width: null, height: null}` — the frontend reads dimensions off the loaded `<img>` |

`cacheawl:` paths are refused (400) by every convert route: v1 is scoped to
the project tree, and the store's write-guards have no opinion about twins.

### The two SSE events

```jsonc
// event: "convert" — job progress, exports, and sync-on-save
{"job": "cv3"|null, "path": "memo.docx", "op": "convert"|"export"|"sync",
 "state": "running"|"done"|"failed"|"cancelled"|"synced"|"conflict",
 "progress": 0-100|null, "message": "…", "result": {…}|null, "error": "…"|null,
 "original": "memo.docx"}          // op:"sync" only, project-relative
// event: "convert-install" — uv's output, line by line, then the prefetch's
{"job": "ix1", "extra": "pdf", "state": "running"|"done"|"failed",
 "message": "<latest line>", "error": "…"|null, "line": "<this line>"}
```

`path` is always the **original's** project-relative path, even when the twin
was the thing saved — one tree row is the identity for everything.

### Tree attributes (the frontend's contract)

`_walk_tree` / `_tree_to_html` emit these on a file row's `<li>`:
`data-convertible="1"`, `data-convert-state="<state>"`, `data-converted="1"`,
`data-twin="memo.docx.md"`, `data-image="1"`, and
`data-help="converted-file"` (on the inner `.file-row`). The `<a>`'s
`hx-get` is deliberately unchanged — the frontend intercepts the click in the
existing capture-phase `#tree` listener; the backend still answers the plain
binary-file preview for anyone who reaches it directly.

### The `pdf` extra: `extras.json`, and the uv gotcha

`~/enough/config/extras.json` — `{"pdf": {"installed_at": "…Z",
"lock_sha256": "…"}}` — records what was installed *out of band*, because an
optional-dependency group is **not** in uv's default set: a later plain
`uv sync` removes it. Every path that syncs therefore re-asks for it with
`--extra <name>`. **Three readers, and they must stay in step:**

| Reader | Where | Seam |
|---|---|---|
| Python | `convert.extras_state_path()` / `installed_extras()` / `ExtraInstaller.sync_argv()` | `$ENOUGH_EXTRAS_STATE` → `~/enough/config/extras.json` |
| bash | `update-enough.command` (inline `python3` heredoc) | same variable, same default |
| Rust | `desktop/src-tauri/src/onboarding.rs` `extras_state_path()` / `env_sync_blocking()` | same variable → `config::state_home()/config/extras.json` |

All three validate each key against `[a-z0-9][a-z0-9._-]*` before it becomes
an argv element — a key beginning with `-` must never reach uv as a flag —
and a missing, malformed, or unreadable file reads as "no extras", never as a
failed launch. `sync_argv()` also appends `--frozen` when `ENOUGH_DESKTOP` is
set: the .app runs a sealed snapshot against a committed lockfile, where
re-resolving would defeat the `exclude-newer` cooldown.

**Model weights** live in `weights_dir()` = `$ENOUGH_WEIGHTS_DIR/docling`
(default `~/enough/weights/docling`), fetched by the worker's `prefetch` op —
in the worker, not in-process, because importing docling means importing
torch into the server. `record_extra()` runs **before** the prefetch
deliberately: the packages really are installed by then, and a network drop
mid-download must not leave the extra unrecorded and liable to be uninstalled
by the next update. Measured: 52 packages, ~1 GB in `.venv`, 669 MiB / 701 MB
of weights, ~0.9 s/page for a digital PDF plus a ~10 s model load.

`tests/test_convert_docling.py` reads `ENOUGH_WEIGHTS_DIR` **at import
time**, before any fixture redirects it, and skips the whole file when
`<that>/docling` is empty — so a bare `uv run pytest` (and CI) skips its 11
tests rather than downloading 670 MB, while a scratch QA run with the seam
pointed at a populated dir runs them all.

---

## Pagination (footnotes, the paginate modal, the paged viewer)

0.2.7. Two halves sharing one engine.

**Footnotes in progress.** Storage is deliberately boring: standard `[^1]`
refs with a `[^1]: body` definitions block at the end of the file, so every
pandoc/typst path keeps working and the file stands alone. `footnotes.py`
owns the surgery; the same rules are mirrored in index.html as `fnParse` /
`fnRenumber` / `fnNextNumber` / `fnInsertAt` (tests/test_footnotes.py is the
contract for both — change one side, run the other's spec). The full read
face renders each definition as a margin card aligned with its ref
(positioning modeled on `positionReviewMarks`); each card has its own
read/edit face with Save/Cancel (toggle-while-dirty saves; cancel reverts).
The edit face inserts via a toolbar button or by typing `[^]`, which expands
to the next number and renumbers everything after it. Only numeric labels
are managed; named ones (`[^intro]`) render and paginate but are never
renumbered. Refs inside code fences or inline code are not footnotes.

**Paginate.** The read-face toolbar's `paginate` button opens
`#paginate-modal` (options schema pinned in `paginate.validate()`): footnote
placement (page / chapter end / book end), nine named page sizes + custom
(ratio + mm/in), portrait/landscape, single / 2-up / booklet, one of four
bundled OFL font families (`defaults/fonts/` — EB Garamond, Source Serif 4,
Source Sans 3, Inter; `ignore_system_fonts=True` keeps output identical
across machines), a single margin value, centered page numbers, running
headers (free text or chapter name; left/right pages differ only in 2-up /
booklet), the export name, and "bring pdf into enough".

The worker op (`convert_worker.do_paginate`) runs: `footnotes.renumber` →
pandoc `-t typst --standalone` → `paginate.build_typ` → `typst.compile`
(PDF, plus per-page SVGs when bringing in) → pypdf imposition when 2-up /
booklet → pypdf attachment embed, always. **The `.typ` surgery cuts
pandoc's `#show: doc => conf(...)` wrapper out** (keeping its helper
definitions) and substitutes our preamble — injecting *after* the wrapper
leaves page 1 at US-letter; `test_split_template_against_real_pandoc` pins
the marker against the installed pandoc. Chapters = the smallest heading
level present (H1 if any, else H2, …); chapter headings get
`#pagebreak(weak: true)`. Endnote placements replace `#footnote[...]`
(balanced-bracket, escape-aware) with `#super[n]` and emit numbered note
lists per chapter or as a final `= Footnotes` section — no hyperlinks, by
design (print-correct).

**Round trip.** Every exported PDF carries `enough-source.md` (the
renumbered source) and `enough-paginate.json` as PDF attachments. A PDF
with those attachments is convertible with engine `"unpack"` — no docling,
no `pdf` extra — and its twin is the embedded markdown verbatim, so
footnotes survive re-import exactly. Foreign PDFs keep the docling path
unchanged. `has_embedded_source()` is `(size, mtime)`-cached because the
tree walk asks it per PDF per build.

**The paged viewer.** `bring_in` writes `<pdf>.pages/page-NNNN.svg` + a
hidden `.<pdf>.paginate.json` manifest (both hidden from the tree; the PDF
row carries `data-paginated` / `data-pages`). `#paginated-mode` is a
mode-stack full-frame surface: prev/next, arrow keys, page N/M, fullscreen.
It always shows *logical* pages — an imposed (2-up/booklet) PDF prints as
sheets but reads as pages.

### Endpoints

| Route | Method | Notes |
|---|---|---|
| `/api/paginate/status?path=` | GET | fonts, size table, engine booleans, default name + options, prior paginations of this source — the modal never hardcodes any of it |
| `/api/paginate` | POST | §schema in `paginate.validate()`; synchronous like export (`run_worker`, 600s); emits the `convert` SSE event on success |

Viewer pages and the manifest are served by the existing
`GET /api/file/blob` (`.json` joined the allowed blob types for this).

## The home screen (registry, mode gate, exit-42 handoff)

0.2.5. Before a project is open, enough runs the **home screen**: the same
server and the same `index.html`, with no project attached.
[enough/home.py](../enough/home.py) owns the state and the policy,
[enough/server.py](../enough/server.py) owns the mode boundary and the
routes, and `desktop/src-tauri/src/launch.rs` owns the state machine on the
shell side. Design record: `docs/home-plan.md` (local planning doc,
untracked) — its three "landed" blocks are the final word where the earlier
sections disagree.

### One app factory, two modes

`create_app(project_dir, …, home: bool = False)`. With `home=True` the
lifespan builds **no Session, no supervisor, no broker, no wikisink** and
seeds no project state; `__main__.py` grows a `--home` flag that is mutually
exclusive with `--dir` (the shell has never passed `--dir` — it uses `cwd` —
which is exactly what makes `--home` legal there).

The boundary is **`server.ModeGate`**, a raw-ASGI middleware class.
Deliberately *not* `@app.middleware("http")`: Starlette's
`BaseHTTPMiddleware` proxies the receive channel, and a long-lived
`/api/stream` response needs that untouched. What a home server answers is
one frozenset plus one prefix tuple:

```python
HOME_PATHS     = {"/", "/favicon.ico", "/api/ui-config", "/api/help-center",
                  "/api/convert/formats", "/api/shutdown"}
HOME_PREFIXES  = ("/api/home/", "/static/")
```

Two of those look surprising and both earn their place: the **formats
table** is a static registry the help center's `{{convert-formats}}` token
expands (and the help center works in home mode), and **`/api/shutdown`** is
how the shell quits a backend — a home backend is still a backend. Anything
else 404s with a JSON `detail` in the house voice. In project mode the gate
inverts: `/api/home/*` 404s and everything else passes. `/api/close-project`
is the one route that crosses — it lives on the project side, so it 404s in
home mode like everything else off the list. Note for anyone adding a home
feature: `/api/help/defaults`, `/api/help/bubbles` and `/api/stream` are
project-scoped and **do** 404 on a home server, which is why the frontend
gates `loadHelpDocs()`, `loadHelpBubbles()` and the EventSource on
`IS_HOME`.

The frontend learns the mode from **`<body data-mode="home|project">`**,
templated by the `/` route. See the `<body>` invariant under "What NOT to
touch" before you edit `index.html`.

### The registry

`~/enough/config/projects.json`, schema 1, backend-owned, one writer,
tmp+rename. Every folder enough has ever put an `rness/` into, plus cached
metadata:

```jsonc
{"schema": 1, "seeded": true, "projects": [
  {"path": "/Users/g/writing/novel",          // canonical abs path — the key
   "created_at": "…Z", "last_opened": "…Z", "last_edited": "…Z",
   "counts": {"p": 812, "w": 54210, "c": 331904},
   "fingerprint": {"files": 37, "max_mtime_ns": 175…, "bytes": 401223},
   "hidden": false}]}
```

Rules that are load-bearing:

- **The seam is `ENOUGH_PROJECTS_STATE`, and it names the *file*.**
  Everything else home touches derives from its **directory** —
  `home.config_dir()` is `projects_state_path().parent`, and both the
  handoff file and the `desktop.json` the seed reads hang off it. That is
  what makes a scratch QA run airtight: redirect the registry and you cannot
  then read the developer's real MRU or drop a handoff file in their real
  config dir. **This seam has a second reader in another language** —
  `config::enough_config_dir()` in the Rust shell does the same `parent`
  derivation so the shell looks for `.home-open` where Python put it.
  (`config::config_path()`, desktop.json, deliberately does *not* follow the
  seam — it's the shell's own file, and leaving it on `$HOME` is what makes
  a registry-only seam produce an empty scratch seed. `update-enough.command`
  does not read the seam at all.)
- **Corrupt / unreadable / foreign-`schema` reads as an empty registry and
  is never rewritten until a real save** — the desktop.json rule. Unknown
  top-level keys survive a save (pinned by a test).
- **Registration happens in exactly two places**: `skeleton.ensure_skeleton()`
  (so every enough-ification registers, however triggered) and project-server
  boot in the lifespan (which also stamps `last_opened`, and picks up
  pre-registry projects on their first open). Both are wrapped so a
  read-only or full `~/enough` logs a warning and never stops a project
  opening.
- **Seeding from the shell's `known_projects` MRU is once-only**, gated by a
  `seeded: true` flag rather than add-if-absent — otherwise a hidden project
  the shell still lists would resurrect on the next home boot. It runs
  off-thread in the home lifespan, and takes an entry only if the folder
  still exists *and* still has an `rness/`.
- **A missing project is never dropped and never zeroed.** It keeps its last
  known counts and renders `missing: true`; a project on an unmounted drive
  shows what it had when you last saw it.
- **There is no delete and no "forget".** `POST /api/home/hide` sets a
  registry-only `hidden` flag; the listing always returns every entry and the
  frontend filters. Un-enough-ification is out of scope, on purpose (user
  call: "forget" reads like deleting `rness/`).

### The counters (a second implementation of the top bar's rules)

`home.count_text()` is the three lines of `updateDocCounters()` in
index.html, quoted in its docstring and ported straight across:
paragraphs = `re.split(r"\n\s*\n", src)` filtered on `.strip()`, words =
`len(src.strip().split())`, chars = `len(src)`. The named agreement test is
`test_count_text_agrees_with_the_top_bar_rules` — same fixture text, the
three numbers computed by hand from the JS and written in as constants, so
the JS is not ported twice. **One knowing difference**: `len()` counts code
points, JS `.length` counts UTF-16 units, so astral emoji disagree on `c`
alone.

The counted file set is `server._walk_tree`'s visibility rules —
**imported from `server`, not copied**, so they cannot drift — with two
deliberate departures: **twins are counted** (a `report.pdf.md` is the
user's text; hiding it behind the original is a display decision) and
**`rness/` is not**, wherever it appears in the tree.

Stats are cached behind a cheap `fingerprint_of()`
(`{files, max_mtime_ns, bytes}`, one `stat` per markdown file, no file
opened unless it moved). `GET /api/home/projects` refreshes only the entries
whose fingerprint changed, in a thread, and writes the registry back **at
most once** per request. `last_edited` is derived from `max_mtime_ns`, not
stored separately.

### The project map

`home.build_project_mirror()` calls `cacheawl.folder_flowchart(base,
root_label, *, start, meta_lines, skip, max_depth)` — the node/edge/depth-cap
walker that was extracted out of `_mirror_body` for this. Frontmatter is
`merirmaid: 1` / `modality: mirror`, and **`modality: mirror` is what makes
the viewer read-only** (`mmRenderDiagram`'s `editable` flag is already
`modality === 'wip' && …`), so nothing had to be hidden. The `skip`
predicate is the *tree's* rule set, so the map shows what the sidebar would;
the `🛈` node reads entirely from the **cached** registry entry, so clicking
a tile costs one directory walk and no re-counting.

### Endpoints

| Route | Mode | Notes |
|---|---|---|
| `GET /api/home/projects` | home | `{"projects": [row, …]}` — nine keys, always: `path, name, description, created_at, last_opened, last_edited, counts, missing, hidden`. `name`/`description` are read **live** from `rness/project.json`; `counts` is never null. Stats refresh first. Server-side order is `last_opened → last_edited → created_at`, newest first — the frontend's default sort |
| `GET /api/home/mirror?path=` | home | `{path, name, text}`; 404 when the path isn't registered |
| `POST /api/home/add` | home | `{"path": …}` or `{}` (empty ⇒ raise the osascript chooser). `200 {project, created}` · `200 {cancelled:true}` · `200 {dialog_unavailable, detail}` · `409 {detail, project}` (already listed — the frontend just opens it) · `400 {detail}` (a guard refusal; surface it **verbatim**) |
| `POST /api/home/open` | home | `{"path": …}` → `{"handoff": …}`, either `"desktop"` or `"exec"`; 404 unregistered · 409 no `rness/` · 400 no path |
| `POST /api/home/hide` | home | `{"path", "hidden": bool}` → `{path, hidden}`; registry only |
| `POST /api/close-project` | **project** | the reverse of `/api/home/open`; same `{"handoff": …}` shape |

**Add guards** (`home.check_addable()`): refuse `~/enough` and anything
inside it (reusing `__main__`'s wording so both front doors say the same
thing), refuse a cloud-synced path, refuse a path that doesn't exist or
isn't a directory. The cloud-sync check **reuses
`skeleton.cloud_sync_provider()`** rather than porting `guards.rs` back —
the Rust is the copy, and says so in its own docstring. The asymmetry is
deliberate: skeleton's caller *warns*, home's *refuses*, with the reason
spelled out for the modal.

**The folder chooser** is `osascript -e 'POSIX path of (choose folder …)'`,
three statements (`try/activate/end try`, then `choose folder`, then `POSIX
path of`), run off-thread with a 180 s timeout. The `activate` is wrapped
because a sandbox that refuses it must not take the script down; without it
the dialog can open *behind* the enough window. Cancel is `-128` (or
"cancel" in stderr) and answers `None`, not an error. Non-macOS or any
failure ⇒ `dialog_unavailable`, and the frontend shows a typed-path field.

### The handoff: exit code 42 and `.home-open`

The contract the Rust rests on is two lines long:

| flow | exit code | `<config dir>/.home-open` |
|---|---|---|
| home + `POST /api/home/open`, `ENOUGH_DESKTOP=1` | **42** | present, `<abs path>\n` |
| project + `POST /api/close-project` (or ⌘W) | **42** | absent |

**The shell's rule: exit 42 → read *and delete* `.home-open` → open what it
names, or home when it isn't there.** Deletion is unconditional once the
file exists — including when it's empty or unparsable — so a stale handoff
can never strand the shell reopening the same project. `home.write_handoff()`
is tmp+rename; `home.read_handoff(consume=True)` is the Python half (tests
use it); `launch::consume_handoff()` is the Rust half, with 4 retries 40 ms
apart for a rename not yet observed on a network-backed home.

Two mechanics worth knowing before you touch `run()` in server.py:

- **`run()` drives `uvicorn.Server` itself and returns an exit status.**
  It has to: `request_process_exit()`'s SIGTERM-to-self *cannot* produce an
  exit code, because uvicorn's `capture_signals` re-raises the captured
  signal after its graceful shutdown and the process dies **by the signal**.
  `request_process_exit(delay, code=None)` keeps the old SIGTERM behavior
  exactly (so `/api/shutdown` and `smoke_boot` are unchanged); with a `code`
  it records the status and sets `Server.should_exit` directly — the same
  graceful drain without the signal, and **open SSE streams still drain**
  (sse-starlette polls uvicorn's `should_exit`).
- **CLI (no `ENOUGH_DESKTOP`) re-execs instead**, via
  `request_process_exec(home.exec_argv(...))`. `exec_argv` is canonical, not
  a copy of `sys.argv`: `[sys.executable, "-m", "enough", "--port", …,
  "--no-browser", "--llm-url", …, "--max-tool-iters", …, ("--no-supervise")?,
  ("--home" | "--dir", …)]`. `-m enough` runs the same install whether this
  process came from the console script, `python -m`, or `uv run`, and
  **every flag rides in both directions, `--llm-url` included** — a QA run
  pointed at a scratch llama-server must not come back from
  project → home → project pointed at the machine's real one. Both handoffs
  stop an **owned** llama-server first (`only_if_owned=True`), same as
  `/api/shutdown`.

### The launch state machine (Rust)

`launch::run` used to end in one of three terminal states. It is now a loop:
**bring a backend up, park until it goes away, work out what the exit meant,
bring up the next one.** There was no backend-exit watcher before 0.2.5 —
`watch()` (200 ms poll) is new code, not a new branch.

- **`initial_target(reopen, last, is_project)`** — `reopen_last_project` on
  **and** a `last_active_project` that still holds an `rness/` → that
  project; everything else → `Home`. It takes the filesystem as a closure,
  which is how `cargo test` covers the routing without a window.
- **`after_exit(code, handoff)`** — the table above, as a pure function.
- **`home_broken`** — set when `boot(Home)` fails, or when a home backend
  exits non-42 on its own. While set, a `Home` target opens the 2a folder
  picker instead. This is the picker's only remaining life, and it is also
  the loop-breaker: without it a home screen that dies at startup is an
  unbounded dialog loop. **Cancelling the picker still exits the app, but
  only on that path** (see `docs/tauri-plan.md` §2's superseded note).
- **⌘W** (`request_close_project`) is the same graceful door as quit —
  `POST /api/shutdown` with the per-launch token, then the SIGTERM/SIGKILL
  ladder — then a `--home` spawn. The backend moves into a **third
  `AppState` slot, `closing_backend`**, so the watcher doesn't read a clean
  exit as a crash and a quit arriving mid-close doesn't orphan a uvicorn;
  the worker also **discards any handoff file** the backend managed to write
  on its way out. ⌘W's answer is home whatever else happened.
- **`View → Show Hidden Projects`** reads the *persisted* value
  (`config::ui_flag("home_show_hidden")` off `ui.json`), computes
  `next = !persisted`, and evals `window.homeSetShowHidden(next)` — the
  frontend setter, which re-renders and POSTs to `/api/ui-config` itself.
  `WebviewWindow::eval` returns `Result<()>`, not a value, and a
  `#[tauri::command]` was rejected outright because
  `capabilities/default.json` lists no `remote` origin — the enough UI on
  127.0.0.1 has no IPC surface at all, and opening one for a check mark
  would be a bad trade. Consequence, stated plainly: the check mark can be
  one flip stale between a click on the page's own `hidden` chip and the
  next time the menu acts.
- **The window goes back to `loading.html` between backends via a real
  `navigate` to `tauri://localhost/loading.html`**, not `location.replace` —
  the window may be showing a page on 127.0.0.1, where a relative URL would
  resolve against the backend.

### ui-config keys home owns

`home_view` (`"icons"|"list"`) and `home_show_hidden` (bool) round-trip
through `/api/ui-config` beside `seen_convert_intro`, top-level, in the
machine-global `~/enough/config/ui.json` — which is also why the theme is
the same on home and in the project. **No default is injected** for
`home_view`: the key is simply absent until someone POSTs one, so the
frontend owns the default.

---

## Skill trust and the first-use audit

All of it lives in [enough/skillaudit.py](../enough/skillaudit.py) (0.2.2).
`prompt.set_skill_enabled()` stays a dumb `.disabled` writer; the guarded
door is `skillaudit.set_skill_enabled_guarded()`. There is **no readvisor tool
for skill toggling** — `tools.py` has no skill path — so the HTTP endpoint
is the only door, and the choke point is complete.

**Trust classification** — `is_trusted(project_dir, name)`: the entry under
`rness/skills/` is a symlink whose `resolve(strict=True)` lands inside
`skeleton._install_defaults_root() / "skills"` **or** directly inside the
`defaults/skills/` of any other enough install — structurally,
`<root>/defaults/skills/<entry>` with the package at `<root>/enough/`
(`_is_install_skills_root()`). The second clause is 0.2.7: the CLI install
(`~/enough`) and the .app's `enough-src` snapshot coexist on one Mac, and a
project's links point at whichever install created them, so before it the
.app audited — and badged, and flagged — every shipped skill in a project
the CLI had made. A look-alike path with no `enough/__init__.py` beside it
is not an install; a link to a file or folder *inside* a sibling's shipped
skill is not a shipped skill. Real directories and symlinks pointing
anywhere else are untrusted — including a `SKILL.md` a readvisor wrote
itself, which is intended (the readvisors audit their own output). Both the
folder (`<name>/`) and flat (`<name>.md`) layouts are handled.

**Fingerprint** — `fingerprint(target)` is sha256 over, for every regular
file under the skill root sorted by POSIX relative path,
`<relpath>\0<sha256(filebytes)>\n`, returned as `"sha256:<hex>"`. Skips
`SKIP_DIR_PARTS` (`__pycache__ .git node_modules .pytest_cache .mypy_cache
.ruff_cache`) and `SKIP_FILE_NAMES` (`.DS_Store`). Names *and* contents
count (a rename moves it); mtimes, permissions and absolute paths do not (a
copy or re-clone doesn't). `_FP_CACHE` is keyed on a stat signature so the
10 s sidebar poll doesn't re-hash whole trees — **mtimes gate the cache
only, never the recipe.**

**Toggle-on decision table** (`set_skill_enabled_guarded`):

| Condition | Result |
|---|---|
| trusted | enable |
| verdict matches fingerprint, `pass` | enable |
| verdict matches fingerprint, `flag`/`fail` | raise `SkillAuditRefused` (`.skill/.verdict/.summary/.report/.fingerprint`, `.as_dict()`); skill written OFF |
| no verdict, or fingerprint moved | `{"ok": False, "state": "needs_audit"}`; skill written OFF; caller schedules `audit_skill()` |

Refusal and `needs_audit` both write the skill **off explicitly** rather
than merely declining to write. Toggle-*off* never audits.

**Two passes.** (1) `run_payload_scan()` imports `payload_scanner.py`
resolved through the project's own skills dir — `SCANNER_HOSTS` names
`analyzer` first and the pre-0.2.2 host it was merged from second, for
installs that predate the merge; `LEGACY_REFS` does the same for the two
protocol documents — and
only from a host skill that is itself trusted, else it falls back to the
install's `defaults/skills/` (a rogue `analyzer` directory can't supply the
scanner). `scan_floor()` maps the script's own vocabulary onto ours:
`CLEAN`→`pass`, `FINDINGS PRESENT`→`flag`, `DO NOT INSTALL`→`fail`. That
verdict is a **floor**; a `fail` floor short-circuits before spending a
model. A missing or broken scanner is not a failed audit — the LLM pass
still runs. **Read that floor for what it is:** the deterministic pass is a
floor for *code* payloads (py/sh/js) plus a light markdown-injection check
(P9: credential names next to a way off the machine, base64 blobs in prose,
"ignore previous instructions" phrasing — all MEDIUM, never HIGH), and
prose *intent* is judged by the LLM pass — so a `CLEAN` scan means "no
payload shape matched", not "safe", and the scanner is never the safety net
on its own. (2) `run_llm_audit()` — a dedicated server-side runner, *not* a
synthetic readvisor turn: it assembles analyzer's `references/audit.md`
(+ `audit-threat-model.md` when present; `LEGACY_REFS` for pre-merge
installs) plus the skill's own files (`MAX_PROMPT_CHARS` 24k,
`MAX_FILE_CHARS` 6k) and makes ONE non-streaming completion call — local
llama-server, or `cloud.chat_completion()` when `opro-api` is active. No
history, no generation lock, worker thread; the user keeps chatting. The
model answers `VERDICT: pass|flag|fail` / `SUMMARY:` / `NOTES:`, and an
**unparsable reply is a `flag`, never a `pass`**. **Transport failure →
`flag`** (`phase: "protocol", status: "error"`), not a pass and not a hard
error. Final verdict = worst of (scanner floor, LLM verdict).

**Decode parameters are measured, not taste** (`AUDIT_TEMPERATURE` 0.7,
`AUDIT_MAX_TOKENS` 12000, bounded by `_completion_budget()` against the
`n_ctx` llama-server reports on `/props`): at temperature 0 a reasoning
model loops in its own reasoning channel, and 1200 tokens is below the floor
for a 17k-token audit prompt — see the Wave D table in
[docs/skills-round-plan.md](skills-round-plan.md). When `content` comes back
empty but `reasoning_content` doesn't, the verdict is read out of the
reasoning; a `pass` found there is downgraded to `flag` (an answer that
never arrived is not an endorsement), and `parse_audit_reply()` takes the
*last* verdict line and ignores a restated `VERDICT: pass|flag|fail`
template.

**`run_llm_audit` is the test hook.** Module-level, looked up at call time,
swapped in tests exactly like `server.request_process_exit`. Every test in
`tests/test_skill_audit.py` uses it; no test may reach a model.

**Outputs** — `AUDITS_REL = "rness/io/output/analyzer/audits"`, then
`<skill>/verdict.json` and `<skill>/<YYYY-MM-DD>-audit.md`. Same folder and
filename convention analyzer's `audit` mode writes to, so both doors
produce the same document in the same place. `verdict.json` is exactly six
keys — `{"skill", "fingerprint", "verdict", "summary", "report", "at"}` —
plus `"override": true` on a user override; `report` is
**project-root-relative**. Read `verdict.json` by name: the folder may also
hold dated reports, an optional `<date>-payload-scan.json`, and an
`unpacked/` dir. A re-audit overwrites the sidecar and drops any
`"override"` key (an override describes one set of files at one moment).

**Concurrency** — `try_claim()` / `release()` guard one audit per (project,
skill); the endpoint claims synchronously before handing work to a thread,
so a double-click can't start two scans. `is_auditing()` backs the
`auditing` row state.

**Not re-audited mid-session (v1).** An already-enabled skill whose files
change is not re-audited or disabled live; `quarantine_untrusted()`
deliberately leaves a *stale* `pass` alone. It re-audits on the next
toggle-on, when the fingerprint mismatch is noticed.

### Endpoints and the SSE event

| Endpoint | Method | Shape |
|---|---|---|
| `/api/skills` | GET | Unchanged contract (HTML `<ul class="skills">`). Rows now carry `data-skill`, `data-audit-state`, `data-audit-report`, and a `.skill-mark` pill; a blocked row is followed by `<li class="skill-note">` with *read report* / *enable anyway*. Calls `resync_globals()` first, so every render also re-quarantines. |
| `/api/skills/toggle` | POST | Unchanged form (`name`, `enabled`) and unchanged 200-HTML response, now guarded. A refusal answers **200 with the re-rendered list** (htmx swaps in the flagged row and its affordances) and mirrors the structured payload onto the event stream. |
| `/api/skills/{name}/trust` | POST | **New (0.2.2).** Records `{"verdict":"pass","override":true,…}` preserving the existing `report`, enables the skill, returns `{"ok":true,"skill":…,"verdict":{…}}`. 404 when no such skill. |

Row states rendered by `_SKILL_MARKS` in server.py: `unverified`,
`auditing…`, `audited` (pass), `flagged`, `failed`, and `trusted by you`
when `override` is set. A trusted (shipped) row renders byte-identically to
pre-0.2.2 — no mark at all.

SSE event **`skill-audit`**, one payload shape throughout:

```json
{"skill": "keysnoop", "phase": "scan"|"protocol",
 "status": "running"|"pass"|"flag"|"fail"|"error",
 "report": "rness/io/output/analyzer/audits/keysnoop/2026-08-17-audit.md",
 "summary": "it asks for your ssh keys…",
 "fingerprint": "sha256:…"}
```

Sequence: `scan/running` → `scan/<floor>` → `protocol/running` →
`protocol/<final>`. The two server-emitted terminal cases (a refused
toggle, and the trust override) add `"enabled": <bool>` — a superset,
harmless to a consumer that ignores it.

**Two override routes**, both supported and both documented for users:
the *enable anyway* button (`POST /api/skills/{name}/trust`), and
hand-editing `verdict.json` to `{"verdict": "pass"}` — the fingerprint must
match the files as they stand.

---

## The help system

Three layers, all markdown (design formerly in docs/help-system-plan.md):

- **`(?)` bubbles.** Content lives in one combined file,
  `enough/static/help-docs.md` (English; translations mirror it at
  `static/i18n/<lang>/help-docs.md` — see docs/I18N.md before editing
  either side) — one `## <id>` section per bubble, with
  `name:` / `path:` lines under the heading and `### what` / `### how` /
  `### ideas` bodies (inline HTML allowed; rendered through the existing
  `renderMarkdown()`). The tokens `{{skills-list}}` / `{{roles-list}}`
  (the token name is unchanged; it expands the **readvisors**) /
  `{{paradigms-list}}` expand client-side into the *actually installed*
  set via `GET /api/help/defaults` (name + description from frontmatter),
  and `{{convert-formats}}` into the file-type table via
  `GET /api/convert/formats` — never hand-maintain those lists in prose.
  All four are expanded by `_helpExpandTokens()` in index.html;
  `{{convert-formats}}` is the one token that also appears in the
  **manual**, where `enterRefMode()` expands it to a markdown pipe table
  before rendering (one row-builder, two renderings — see
  `convertFormatsHelpRows()` / `…Html()` / `…Markdown()`). Bubbles are governed by
  one per-project boolean (`GET`/`POST /api/help/bubbles`, stored in the
  multipurpose `rness/active-paradigm` file, default on, surfaced as the
  "help (?) bubbles" checkbox in the UI modal): on = every `[data-help]`
  row shows its `(?)` persistently (re-applied after `htmx:afterSettle`),
  off = none. There are no hover timers and no first-launch highlight
  machinery — that design was superseded.
- **The manual.** `docs/HELP_CENTER.md` is the complete end-user manual
  (voice-matched to the project; edit it like documentation, verify
  claims against the code first). `GET /api/help-center` serves it raw;
  the **reference mode** (`#ref-mode`) renders it read-only in-app,
  launched from `#ui-help-center-btn` — since 0.2.2 a normal small
  **help** button inline in the UI modal's header row, right-aligned
  beside the ×, rather than the old full-width banner. It kept its
  `.help-center-launch` class name, its `hxc` icon, and its `onclick`;
  only the CSS shrank. See the mode-stack notes under "Change the UI".
- **Cheat sheets.** Keyboard shortcuts + markdown reference live inline
  in the UI modal markup (`.ui-cols` in index.html). The esc row reads
  "close the topmost open mode (modes stack)" — keep it true to
  `modeTop()` semantics if you touch either.

---

## Display scales (ui scale / text scale, 0.2.9)

Two per-project zooms, set from the steppers in the UI modal
(`#ui-controls-row`) and persisted in `rness/project.json` under `"ui"`
(`project_meta.save_ui`, `POST /api/project/ui`; `load()` always returns
the block, defaults 1.0/1.0). The `/` route templates them into the
inline `BOOT_UI_STATE` literal (`/*UI_STATE_JSON*/null` — replaced the
same way as `<!-- PROJECT_NAME -->`) so a head script applies them
before first paint. Home mode templates `{"home": true}`: no project,
no scales, controls hidden by the `body[data-mode="home"]` CSS block.

Mechanism, all CSS custom properties on `<html>`:

- `--uiz` — whole-UI zoom: `body { zoom: var(--uiz, 1) }`.
- `--txz` — content-only zoom, multiplicative, applied to the **mode
  document surfaces** only (one selector list next to the body rule:
  review/ref `.review-body`, `#edit-mode .edit-textarea`, `#wiki-body`,
  `#preview-body`). Extending text scale to a new surface = adding one
  selector there. The readvisor panel, sidebar, modals and the
  girraph/merirmaid/**composure** canvases follow `--uiz` alone, on
  purpose (diagram and canvas layout would distort).

Step limits live in `uiScaleLimits()` — resolution-aware (≥640 real px
of layout, legibility floor looser on retina, text max tightens as ui
grows, ceiling 2.0 → 3.0 on ≥5120-physical-px displays), recomputed per
attempted step, and they gate *changes only* (a value stranded out of
range by a window shrink can always step back toward range). A denied
step wiggles the button + pulses the value red (`.limit-wiggle` /
`.limit-pulse`, removed on animationend). Clicking a value resets that
scale to 1.0.

**The coordinate contract — read before touching positioning code.**
CSS zoom means `getBoundingClientRect()`, `clientX/Y`,
`innerWidth/Height` return *top-level* CSS px, while `style.left/top`,
`scrollTop`, `offsetHeight`, `clientHeight` on elements inside the
zoomed body are in *zoomed-local* px. Converting between them divides
by the effective zoom: `UIZ()` for chrome (context menus, the
highlight/footnote popups, `#mm-label-editor`, `#wiki-sel-popup`), and
`UIZ() * TXZ()` inside a `--txz` surface (footnote cards, linenav
marks). Never mix a rect with `clientHeight` (rect height instead), and
never assign a raw `clientX` to a positioned element's style. The
composure canvas adds a third space on top of this — see its own
section; `compEventToStage()` is the one place its `/ UIZ()` happens,
and `--rv-dock-w`'s `calc(27vw / var(--uiz, 1))` is the same rule in
CSS. Same
deal in CSS for viewport units: every `vh/vw/vmin` length divides by
`var(--uiz, 1)` (grep `/ var(--uiz` for the pattern) so real-viewport
fits keep fitting.

---

## UI languages (i18n, 0.3.0)

Chrome + help content ship in en/fr/es/de/zh/ja; everything the readvisors
read or write stays English on purpose. **docs/I18N.md is the process
doc — read it before touching any translated surface or any English
string that has a `data-i18n*` key.** The short version:

- Engine at the top of index.html's main script ("UI language (i18n
  round)"): `t(key, english)`, `applyI18n()` over `data-i18n` /
  `-title` / `-placeholder` / `-aria`, `setUILanguage()`; inline
  English is the permanent fallback and gets memoized into
  `data-i18n-src*` so switches round-trip live.
- `enough/static/i18n/<lang>/{ui.json,help-docs.md,help-center.md}`;
  `en/ui.json` is the canonical catalog and must stay byte-identical
  to the inline English. The server (`UI_LANGUAGES`, `_ui_language()`)
  whitelists codes, templates the boot language into `BOOT_UI_STATE`,
  and serves translated manuals via `GET /api/help-center?lang=`.
- `ui_language` is a top-level ui.json key (POST /api/ui-config,
  validated like `home_view`).
- **Every English string change must keep the catalogs in lockstep:**
  `uv run python scripts/i18n_check.py` prints the exact per-language
  to-do list, and `tests/test_i18n.py` fails CI until it's empty.

---

## Tasks you might be asked to do

### Add a new skill

1. Create `defaults/skills/<name>/SKILL.md` with YAML frontmatter
   (`name`, `description`). Optionally add `references/`, `scripts/`,
   `assets/` subfolders.
2. `description:` **must be a single line.** `prompt._parse_paradigm_frontmatter`
   splits on the first `:`, so a YAML folded block (`description: >`)
   silently degrades to the string `">"` and the readvisor never learns when to
   engage the skill. `tests/test_skills_defaults.py` rejects it explicitly.
   Same file pins the other two conventions: frontmatter `name:` must equal
   the directory name, and `enough-tooltip-text:` must be present and be the
   **last non-empty line** of the file (it is not frontmatter; it feeds
   `{{skills-list}}` via `GET /api/help/defaults`).
3. Bundled `scripts/` must run on stdlib plus what `pyproject.toml` already
   pins. If a script needs a dep enough doesn't ship, make it degrade with a
   clear message rather than adding a dependency. The suite `py_compile`s
   every bundled script.
4. The user runs `/update-enough` in their chat (or restarts enough) and
   the symlink lands in every project's `rness/skills/`.
5. The skill is **off by default** — user toggles it in the sidebar.
   No other code changes needed.

A skill added under `defaults/skills/` is **trusted** (it's a symlink into
an enough install — this one or a sibling) and never audited. A skill created anywhere else — dropped
into a project's `rness/skills/` by hand, or written there by a readvisor
under the workflow-design paradigm — is **untrusted**: it is quarantined off
on the next sync and gets a first-use audit the first time it's toggled on.
See "Skill trust and the first-use audit". Don't work around that by
writing a new skill into `defaults/skills/` on the user's behalf when they
asked for a project-local one; the audit is the feature.

### Add a new paradigm

1. Create `defaults/paradigms/<name>.md` with YAML frontmatter (`name`,
   `description`).
2. Optionally update [defaults/paradigms/default.md](../defaults/paradigms/default.md)
   to mention the new paradigm under "Canonical examples worth flagging
   proactively" (the `default` paradigm's prompt tells the readvisor when
   to switch).
3. Document the activation rule in the paradigm itself — when to switch
   in, when to switch out, what skill (if any) it pairs with.
4. No code changes; paradigm catalog is read from `rness/paradigms/`
   directly.

### Add a new readvisor

Three places it can live, and the choice is the interesting part — see
"Readvisors" for the ranks.

**By hand, shipped with enough** (a readvisor everybody gets):

1. Create `defaults/readvisors/<name>/AGENT.md` and `MOTIVATION.md`.
   `AGENT.md` needs a `# <Display Name>` H1 (that is what the sidebar and
   a council's participant list show) and a trailing `enough-tooltip-text:`
   line.
2. Match the shape the `readvisory` skill's templates define —
   `defaults/skills/readvisory/assets/{AGENT.md,MOTIVATION.md}.template`.
   `prompt.readvisor_shape()` reads them **at call time**, and
   `tests/test_readvisors_defaults.py` runs it over every shipped
   readvisor, so a new one has to conform or the suite goes red.
3. `skeleton._populate_role_symlinks` symlinks the directory on the next
   launch / `/update-enough`.
4. It arrives **switched off** in every project (its name goes into
   `rness/readvisors/.disabled` on first sync) — the user toggles it.

**By hand, for one machine** (no repo edit, works on a sealed .app install):
the same two files under `~/enough/readvisors/<name>/`. Nothing creates
that directory for you; `mkdir -p` it. It outranks a shipped readvisor of
the same name, and arrives off in every project the same way.

**Through the `readvisory` skill** — the supported route, and the one to
suggest when a user asks for "a new readvisor". The skill interviews the
user, drafts both documents, and finishes with `install_readvisor`
(`<scope>project</scope>` or `global`). That door enforces the shape, runs
the payload scan, refuses to write through a symlink, and stages into
`.<name>.installing/` before renaming into place. It needs the
`readvisory_install` broker toggle on, and the skill itself switched on —
which is also what puts `READVISORY_TOOL_INSTRUCTIONS` in the prompt, so
with the skill off the tool's documentation is unreachable advice and is
correctly absent.

Removal for the user-made cases is `POST /api/readvisors/remove {name}`
behind the confirm overlay; shipped readvisors answer 403 ("switch it off
instead").

### Add a composure module type

The type vocabulary is small on purpose and round-tripping an unknown type
is a promise the format makes — so read `known_type` in the model before
you decide you need a new one.

1. Add the name to `composure.MODULE_TYPES` and a `(w, h)` row to
   `composure.BASE_SIZE`.
2. If it carries a target, add its field to the module's `fields` dict and
   to the `add_module` / `update_module` optional-key lists, with a
   validator beside the existing `href` (project-relative path) and `url`
   (http(s)) checks. Refusals name the allowed shape; keep that.
3. Teach `GET /api/composure/link-preview` how to preview it in
   [composure_api.py](../enough/composure_api.py) — and keep the rule that
   it **never raises**: a missing target is `{ok: false, detail: "<a
   sentence>"}`.
4. Frontend: one entry in `COMP_MODULE_RENDERERS`, keyed by the type name.
   A renderer owns everything inside `hostEl` and gets the module and its
   current page. Until it exists the type falls through to
   `compRenderPlaceholder`, which is a working state, not a broken one.
5. Tests: `tests/test_composure.py` for the round trip and the op
   validation, `tests/test_composure_api.py` for the preview.

Do **not** add a type by teaching a renderer a string the backend has never
heard of — `known_type: false` is for a *newer* enough's types, not for
skipping step 1.

### Add a composure form

A form is a `.comp` like any other; the only thing that makes it a form is
where it lives.

- **A project form** is `POST /api/composure/save-as-form` (or the
  `comp_save_as_form` tool) over an existing composure. It lands in
  `rness/composure-forms/<slug>.comp` and shows up in
  `GET /api/composure/forms` with `origin: "project"`. A project form whose
  name collides with a shipped one **wins**, and is listed once. No code.
- **A shipped form** is a row in `scripts/gen_composure_forms.py` plus a
  name in `composure.SHIPPED_FORMS`. **The five in
  `defaults/composure-forms/` are generated, never hand-written** — after
  any change to `dumps`, the style block or `md_to_rich`, run
  `uv run python scripts/gen_composure_forms.py` and commit the result
  (`--check` is the CI-shaped assertion).
- A form with behaviour beyond its content gets an entry in
  `COMP_FORM_BEHAVIORS` in index.html; `_default` handles every form
  without one, which is what makes project forms work for free.
- **The form supplies the kind and the styling, not its placeholder
  modules** where a generator is involved: `from_outline` clears the form's
  own content in the same atomic batch it adds the outline's.

### Add a council output kind (the 0.4.0 hook)

Today `output.kind` ∈ `answer | document | composure`, and `composure`
answers **501 before the conclusion turn runs**, so nothing is spent and
the council stays runnable. Adding a kind:

1. Accept the name in `council.validate_output()`, with whatever companion
   key it needs (`path` for `document`, `form` for `composure`) and a
   refusal sentence for the missing case. Unknown keys are dropped on
   purpose — validate it or it will not survive a round trip.
2. Handle it in `POST /api/council/conclude` *after* the chief's
   conclusion statement is committed, alongside the `document` branch.
   **Write through `tools.run_write_file`**, not `Path.write_text` — that
   is what keeps the allowlists, the `rness/requests/done/` prefix rule,
   the cachebox mirror guard, the `.comp`/`.girraph` refusals, the undo
   stash and the convert-twin sync applying to a council's output.
3. Add a `doc` link-in module under the conclusion so the artifact is one
   click from the council that produced it, the way `document` does.
4. Refuse *before* the turn when the kind cannot land (the 501 pattern):
   spending a completion and then failing is the one outcome to avoid.
5. `tests/test_council.py` for the validation, `tests/test_council_api.py`
   for the conclude path.

### Add a tool runner

1. Define `run_<tool>(project_dir: Path, call: ToolCall) -> ToolResult`
   in [tools.py](../enough/tools.py).
2. Register in `_DISPATCH` (~line 1447 in tools.py) and `_TRACE_TOGGLE`
   (~line 1475). Both grep cleanly by name if line numbers drift again.
3. If `ToolResult.render()` needs a specific attribute (e.g. `output=`
   for `cloud_pipeline`), add a branch in `render()`.
4. Add an XML example block + prose to `TOOL_INSTRUCTIONS` in
   [prompt.py](../enough/prompt.py).
5. If the tool needs a broker toggle (kill switch), add to
   `broker.TOGGLES` — UI updates itself.

### Add a convertible file format

The registry is the whole recipe; resist the urge to special-case anywhere
else.

1. Add one row to `convert.FORMATS` in
   [convert.py](../enough/convert.py): `label` (user-facing, used verbatim
   by the intro modal's a/an rule and by every generated table), `reader`
   (`"pandoc"` | `"docling"`), `writer` (`"pandoc"` | `"typst"` | `None`),
   `sync_ok` (only true when the writer can rewrite the original in place),
   and one honest `notes` sentence — it is copy, and it ships to users.
2. Teach the worker the format name: `convert_worker.PANDOC_READERS` (and
   `PANDOC_WRITERS` / `NEEDS_STANDALONE` if it is also an export target), or
   `DOCLING_FORMATS`.
3. If it is a new **export** target, add the extension to
   `convert.EXPORT_TARGETS` too.
4. Stop. `GET /api/convert/formats`, the export modal, the
   `{{convert-formats}}` help token (help-docs.md + HELP_CENTER.md §5.2),
   and `prompt.convert_instructions()`'s system-prompt section all render
   the registry — none of them needs an edit, and none of them may
   hand-list an extension.
5. Tests: `tests/test_convert.py` asserts registry shape and the round
   trip; add a fixture generated at test time (never checked in — see
   `tests/conftest.py`) rather than a binary in the repo.

### Add a broker toggle

Append a `Toggle(...)` to the `TOGGLES` tuple in
[broker.py](../enough/broker.py). The `/api/broker` handler iterates
`TOGGLES` so the new row appears in the broker pane with no other
changes. If you want denial messaging tied to the toggle being off,
add a `denial_<thing>()` helper at the bottom of broker.py.

### Add an /api/* endpoint

Define an async handler inside `create_app()` in
[server.py](../enough/server.py) (FastAPI route decorators). Keep
imports late (inside the function) where possible to avoid circular
imports — `cloud`, `models`, `tools` are typical late imports.

### Add a column to the home list view

The list view's columns are `name · ¶ · W · C · last updated · created`.
Adding one is a four-step change, and the order matters:

1. **Is the value already in the registry entry?** If not, it belongs in
   `home.refresh_entry()` — computed during the fingerprint-gated refresh, so
   it costs nothing on an unchanged project — and in the `~/enough/config/projects.json`
   schema. Do not add a per-render walk; the whole point of the fingerprint
   is that `GET /api/home/projects` opens no files when nothing moved.
2. **Add it to `home.row()`.** That function is the payload contract and the
   API test asserts its exact key set, so the test fails until you do —
   which is the intended order.
3. **Render it in index.html's home module**: the `.hl-head` header button
   (with a sort key) and the `.hl-row` cell. Numbers go through
   `toLocaleString` and carry the `.num` class; dates use the compact
   `YYYY-MM-DD HH:MM` stamp, not the tiles' relative phrasing.
4. **Sorting**: nulls sink in *both* directions (a never-edited project is
   "unknown", not "oldest") and ties break on name. Text columns open A→Z,
   everything else opens newest/most-first.

Six columns already crowd a ~700px window, so a seventh wants a reason.
Counting-rule changes are a different job — see the counters subsection of
"The home screen", and remember the numbers are asserted to agree with the
top bar's.

### Change the UI

[enough/static/index.html](../enough/static/index.html) is a single
~30,200-line file with inline CSS and JS. Conventions:

- All modals follow the same `#<name>-modal` pattern with `.hidden`
  class and a `.modal-backdrop` for click-outside dismissal.
- htmx is used for the broker toggle list (declarative) and the model
  list reload (fetch-based JS). New simple lists can use either.
- Color variables (`--accent-agent`, `--accent-tool`, `--accent-error`,
  etc.) live at the top of the file's `<style>` block; use them
  consistently.
- New endpoints that the frontend hits typically need a corresponding
  fetch/htmx call in the relevant `open<Thing>Modal()` or render
  function.

The 0.1.6 UI revamp added several mechanisms you'll want to reuse rather
than reinvent:

- **The SVG icon pipeline.** 33 custom icons are built by
  [scripts/build_icons.py](../scripts/build_icons.py) (reading
  `scripts/icons-bbox.json`; strips hidden Illustrator layers, squares the
  viewBox at 82% fill) into `enough/static/icons/build/` — two variants per
  icon: `<name>.svg` (black line-work, light themes) and `<name>-dark.svg`
  (white, dark themes; produced by a black↔white swap incl. gradient stops).
  Don't hand-edit `build/`; edit the source SVG + rerun the script. In the
  DOM, every icon is `<img class="svg-icon" data-icon="<name>">`; `iconSrc()`
  resolves the variant, `setIcon(el, name)` swaps a toggle icon, and
  `refreshThemeIcons()` re-derives all variants on a live theme change (no
  reload). Reuse those helpers — don't write `<img src>` by hand.
- **Theme-aware icon variants.** The active variant comes from the theme's
  `icons` key (`"dark"` | `"light"`), reflected onto the root as the
  `data-icons` attribute; themes predating the key fall back to a luminance
  heuristic on their `bg`.
- **`btn-bg` color key.** Button chips paint on `var(--btn-bg,
  var(--bg-raise))` — a new theme color that **falls back to `--bg-raise`
  when absent** (so old user configs still look right). See "What NOT to
  touch" about never defining `--btn-bg` in `:root`.
- **The MODE STACK** (formerly docs/mode-stack-plan.md; search `MODE_STACK`
  in index.html) is the contract every full-frame mode registers through.
  Modes don't supplant each other — they stack like windows, and closing
  one reveals the mode beneath with its state intact. The API:
  - `modePush(name, opts)` — open/register. `opts`:
    `{icon, onExit, iconTitle?, exitTitle?, onRaise?, rootId?}`. If `name`
    is already stacked, its opts update and it **raises** in place (the
    caller has already re-targeted content — e.g. `enterGirraphMode` on a
    new file resets `GIRRAPH_STACK` itself). One live instance per name
    (`readedit`, `girraph`, `merirmaid`, `wikisink`, `cacheawl`, `ref`,
    `paginated`). **Composure is not one of them** — it is the base layer
    below the stack (z < 30), permanent and uncloseable; see "Composures".
  - `modeRemove(name)` — splice at any depth, re-apply z-order, re-render
    indicators. **Bookkeeping only**: it does not run `onExit` and does not
    hide the mode's root, so callers tear the mode down first (see "What
    NOT to touch", and the block comment at its definition, which names all
    eight callers and the one legacy wrapper that is the exception). A mode
    "closed" with this alone leaves its render loop spinning behind an
    element that is still in the DOM. Empty stack = the bare composure
    canvas.
  - `modeRaise(name)` — z-order + indicators only, plus the optional
    `onRaise` hook (cacheawl wires `caLoadTree()` to refresh stale data);
    **never** a re-enter.
  - `modeTop()` / `modeUpdateIcon(name, icon, title)` — top entry;
    in-place icon swap (read/edit's eye↔pencil face).
  - Z-order: the manager assigns `z = 30 + index` inline on each entry's
    root(s) (roots in `_MODE_ROOT_IDS` / `_ALL_MODE_ROOTS`; readedit owns
    `review-mode` + `edit-mode`, and `#preview` floats at `31 + index`
    while readedit is stacked, so the mini panel sits over buried
    full-frame modes). Confirm overlay (950+) and modals (1000+) stay
    above everything.
  - **Indicators**: one bar-height square per entry in `#mode-stack`
    (topbar right half), **top-of-stack leftmost**, `--bg-alt` background,
    1px 50%-gray left/right edge lines, no chip/gradient (deliberately
    not buttons). Each carries its own `ribbon-redx` off its left edge
    (closes that entry, even buried); clicking a buried square raises it;
    the top square is inert — **except while `rv-full`, where clicking any
    indicator drops the panel to docked and raises that mode**. The
    rightmost square is composure's permanent **base indicator** and is the
    one square with **no ribbon**, by design; clicking it toggles the peek.
  - **Esc** targets `modeTop()` only, guarded so it doesn't fire while
    the confirm overlay is up, while a chat composer / search / inline
    edit field is focused, or while ANY modal is open (`_escModalOpen` —
    modals own esc for themselves). **A modal with no esc listener of its
    own therefore makes esc do nothing at all** — every modal needs one.
    **Esc in the chat composer (`#message`) BLURS it** (0.3.5): the rungs
    below a focused field are otherwise unreachable, because the readvisor
    panel focuses the composer whenever it opens. A second esc then follows
    the normal order. Only `#message` — the search and inline-edit fields
    handle esc themselves, for their own "never mind".
  - `setActiveMode` / `clearActiveMode` survive only as thin compat
    wrappers (push / remove-top). Wire new modes through the stack, not
    ad-hoc show/hide.
- **`confirmOverlay(...)`** is the reusable ribbon dialog (`#confirm-overlay`):
  ribbon-check confirms, ribbon-redx cancels, ribbon-alert marks the
  warning. Use it for confirmations (e.g. the cachebox-update wikisink run)
  instead of `confirm()`.
- **The mode system.** preview/review/edit were unified into ONE read/edit
  mode with two faces (read-eye / edit-pencil) that lives either as a mini
  side panel or a full frame (`full2mini` / `mini2full` toggle, dirty
  guards). Face toggling happens on dedicated `readedit-switch` buttons in
  the read/edit chrome (`#review-face-btn` / `#edit-face-btn` /
  `#mini-face-btn`) — the topbar indicator is not a button. The full-frame
  family is wikisink, girraph, merirmaid, cacheawl, read/edit, and the
  read-only **reference mode** below — all stack citizens.
- **Reference mode (`#ref-mode`, name `ref`).** The read-only manual
  viewer: fetches `GET /api/help-center` (which serves the repo's
  `docs/HELP_CENTER.md`) and renders it through `renderMarkdown` into a
  `.review-body`-styled frame (the pretty-markdown CSS is shared via
  `:is(#review-mode, #ref-mode) .review-body` selectors, and
  `applyReviewContrast()` covers `ref-mode` alongside review/wiki). View
  only by design: no edit face, no highlighting, no chat affordance. The
  `ref-mini` class docks it to the right edge for side-by-side reading
  (`refToggleSize()`); launched from the big `hxc`-icon button at the top
  of the UI modal. The 3D icon-button gradient used on square chips is
  the shipped two-stop ramp `rgba(128,128,128,0.42) → 0.10 at 62% → 0`
  over `var(--btn-bg, var(--bg-raise))`.

### Add a new local model

Append an entry to [defaults/models.json](../defaults/models.json) with
all the required fields. The model appears in the model modal on next
page load. Users have to install the gguf separately (or trigger a
download via the install path — see `bootstrap.sh` step 6 logic).

### Change the OpenRouter model id default

Edit [defaults/openrouter-config.json](../defaults/openrouter-config.json)
(the `model_id` field). Note: this is only the default; existing users'
`~/enough/config/openrouter.json` keeps whatever value they last set
via the settings panel. There's no auto-migration.

### Modify wikisink

Read the Wikisink section above first, then
[docs/WIKISINK.md](WIKISINK.md) for the user-facing contract. Rules of
thumb: all state changes go through `wikisink/config.py` helpers (never
hand-roll JSON edits or mkdirs); anything that could remove or replace
user-visible data (archives, preserved articles, comments) must be
user-confirmed in the UI — the readvisors get read/search/update-run tools
only; test against a scratch config via `ENOUGH_WIKISINK_CONFIG` and a
tiny real ZIM (openzim's `zim-testing-suite` has ~40 KB ones) rather
than mocking libzim. Adding a wikisink flavor = append to
`download.FLAVORS`; the wizard and listing regex pick it up.

---

## What NOT to touch / surprising patterns

A list of things that will confuse you if you don't see them coming:

- **The active-paradigm file is multipurpose markdown (0.1.7).**
  `rness/active-paradigm` (filename unchanged, no extension) carries a
  `# Active paradigm` section (the paradigm name on the first
  non-heading line) and a `# Help bubbles` section storing `on`/`off`.
  Read/write ONLY via `prompt.get_active_paradigm()` /
  `set_active_paradigm()` / `get_help_bubbles()` / `set_help_bubbles()`
  — `set_*` preserves the other section. Back-compatible: a legacy bare
  `default\n` still parses, and every legacy help value (the old `all`
  sentinel, id lists, empty/missing) reads as bubbles-on. Don't add
  YAML or further sections.
- **Adding to `broker.TOGGLES` is a UI change.** The `/api/broker`
  handler iterates the tuple; the frontend renders whatever comes back.
  No CSS or JS update needed for the row itself.
- **`/api/models` injects OPRO-API at response time, NOT in `models.json`.**
  The local model registry stays pure (gguf-based). The cloud entry is
  synthesized in the endpoint handler when `local_models_only` is off.
- **The OpenRouter api key has exactly one storage location: the OS
  keyring.** Don't add a fallback to env vars, config files, or
  command-line flags. The single-source-of-truth is part of the threat
  model.
- **`_get_api_key_for_broker()` is the only function that returns the
  key value.** Underscore-prefixed as a reminder. If you find yourself
  needing the key elsewhere, your design is probably wrong — push the
  network call into `cloud.py` instead.
- **`cloud.pipeline_run()` normalizes `project_dir` with `.resolve()`
  at entry.** On macOS, `/var` is a symlink to `/private/var`. Without
  the resolve, `relative_to()` calls in the result-dict construction
  fail with confusing "not a subpath" errors. If you write new code
  that does `relative_to(project_dir)`, follow the same pattern.
- **Chat dispatch reads the active model from disk on every turn.**
  Cheap; lets the user switch models mid-session. Don't cache it.
- **The system prompt is reassembled on every turn.** Edits to
  `rness/*` land on the next message. There is NO per-session cache.
  Performance is fine — the disk reads are tiny.
- **`ToolResult.render()` uses different attribute names per tool.**
  `path=` for file ops, `url=` for fetch_url, `command=` for shell,
  `output=` for cloud_pipeline. If you add a tool, decide what the
  attribute should be and add a branch.
- **Skills are off by default; paradigms are exactly one active at a
  time; readvisors are individually toggleable.** Three different
  on/off patterns for three concepts — don't conflate them. And a
  readvisor's sidebar toggle governs only the *combined* voice of ordinary
  conversation: `prompt.readvisor_identity()` ignores it on purpose,
  because a council picks its participants in its own setup card.
- **`prompt.set_skill_enabled()` is not the door for a skill toggle.**
  It's the raw `.disabled` writer. Every toggle-on must go through
  `skillaudit.set_skill_enabled_guarded()`, which can raise
  `SkillAuditRefused` or return `needs_audit`. If you add a second route
  that enables a skill (a new endpoint, a tool runner, a migration), route
  it through the guard or you've reopened the hole
  `quarantine_untrusted()` exists to close. Readvisors have no equivalent
  toggle guard — only skills are audited. Their door is different:
  `install_readvisor` scans **before** writing and treats `flag` and `fail`
  alike, because prose about a person has no legitimate reason to look like
  an exfiltration pattern.
- **Wikisink state is user-global, not per-project.** One
  `~/enough/config/wikisink.json` for the whole machine. Comments and
  watches attach to *articles* (stable slug+hash keys via
  `config.article_key()`), not to saved files or to any one archive —
  they survive archive swaps and install switches.
- **`installed` ≠ `configured` in wikisink.** A registered install on a
  detached drive is configured-but-not-installed; treat that as a
  normal, recoverable state (offer switching/reattaching), never as
  "not set up" — the old single-install code made that mistake and
  would have sent a user with 49 GB on a detached drive back through
  the setup wizard.
- **Never `mkdir` under a `/Volumes/...` path without
  `config.volume_mounted()`.** See the Wikisink section for why.
- **The `pdf` extra's third requirement line is load-bearing.**
  `pyproject.toml`'s `pdf` extra lists `docling-ibm-models[opencv-python-headless]`
  *in addition to* the two `docling-slim[...]` lines, and it is not a
  duplicate: TableFormer's predictor imports `cv2` at module scope, but
  `docling-slim`'s `models-local` asks for `docling-ibm-models` with **no**
  extras and opencv is optional there — so `do_table_structure=True` raises
  `ModuleNotFoundError: No module named 'cv2'` without it. The same hole is
  in `docling-slim[standard]` and in the full `docling` distribution, so
  swapping distributions does not fix it. Don't tidy the line away, and
  don't "simplify" the comment above it. (Headless because a conversion
  worker has no display and the GUI build drags in Qt.)
- **Twin manifests and assets dirs are backend-owned.**
  `.<original>.convert.json` and `<original>.assets/` are written only by
  `convert.py` / `convert_worker.py`, and `_walk_tree` hides both. A
  re-convert *clears* the assets dir before extracting, which is what keeps
  `img-1.png` stable across re-converts — so nothing user-authored may ever
  be stored there. The twin itself is the opposite: it is the user's file,
  edited freely, and every code path writes it **first and
  unconditionally** — a refused sync is a flag on the response, never a lost
  edit.
- **`index.html` must contain exactly one `<body`.** The `/` route marks the
  mode with `html.replace("<body>", '<body data-mode="home">', 1)`, so the
  *first* occurrence of the literal string wins. Wave B broke this within
  the hour by writing `<body>` in a CSS comment above the real tag: the
  replace hit the comment, the page came up unmarked, and a home server
  rendered in full project chrome. There are warnings at both comment sites
  and a regression test — `test_mode_marker_lands_on_the_real_body_tag` —
  that pins `html.count("<body") == 1` on the *served* page rather than
  merely checking that the attribute string appears. If you need to write the tag
  in a comment, spell it `<body` without the `>`, or don't.
- **`~/enough/config/.home-open` is a transient handoff file, not state.**
  Written tmp+rename by `home.write_handoff()` (one absolute path plus a
  newline), read **and deleted** by whoever consumes it — `launch::consume_handoff()`
  in the shell, `home.read_handoff(consume=True)` in Python. Never read it
  without consuming, never leave one behind: a stale file opens a stale
  project at the *next* exit 42. Its directory follows
  `ENOUGH_PROJECTS_STATE`'s parent on both sides.
- **Close Project does not clear `last_active_project`.** With
  `reopen_last_project` **on**, quitting from the home screen after a ⌘W
  still reopens that project next launch. That is deliberate: the toggle is
  the user's control for "start me on home", and clearing the key would be a
  silent new rule. Documented in HELP_CENTER §2.5; don't "fix" it without
  changing both.
- **⌘W belongs to Close Project now, and the Window menu lost
  `PredefinedMenuItem::close_window`.** The predefined item carries ⌘W on
  macOS and passing `None` there overrides the *text*, not the accelerator —
  two items on ⌘W is a conflict. The app is one window and closing it quits,
  so ⌘Q and the red button cover the ground. ⌘W is also unbound in the page,
  by agreement, so a browser tab keeps the browser's meaning.
- **Cachebox sidecars are backend-owned.** `_cachebox.merirmaid` and
  `.cachebox.json` are written only by `cacheawl.py`. Both write endpoints
  (`write_file`, `POST /api/file`) already refuse them; don't add a path
  that edits a mirror from anywhere else — it would drift from the box it
  mirrors and get clobbered on the next regeneration. To change what a
  mirror shows, change the box contents.
- **Never whole-file-write a `.comp`.** Both write doors already refuse it
  (`composure.write_denial()`, called from `run_write_file` and
  `POST /api/file`), and the refusal also covers the
  `.<name>.comp.comments.json` sidecar. There is deliberately **no endpoint
  that accepts `.comp` HTML** and no client may construct it. Content
  changes only through node-level ops on `POST /api/composure/ops` under
  `composure.path_lock()` — that is what lets the user type in one module
  while a readvisor edits another. If you find yourself wanting a
  whole-file door "just for a migration", write the migration as a batch
  of ops.
- **`update_module` refuses to change `speaker` / `speaker_kind` / `turn`
  from any source but `"council"`.** Those three fields *are* the lock
  (`Module.locked` is `bool(speaker)`), so without the guard a `ui` batch
  could blank `speaker`, unlock a council statement, and rewrite it on the
  next op — which would make the transcript a suggestion rather than a
  record. `add_module` **with** a `speaker` is still open to any source
  (forging a card in your own file is not an attack), and so is every
  non-speaker field on a locked module: geometry, background, scale, title
  and z all still apply, which is exactly how the frontend corrects a
  statement's height. The content ops (`set_page`, `add_page`,
  `remove_page`, `remove_module`) are where `_check_writable` lives.
  Likewise **`set_meta` refuses `form` and `council`** — the engine's own
  door is `set_council`, and that op is refused for every source but
  `"council"`.
- **The composure base indicator has no exit ribbon, by design.** Every
  other square in `#mode-stack` carries its own `ribbon-redx`; the base
  square (rightmost, `data-mode="composure"`) does not, because composure
  cannot be closed — you peek past it. A harness scenario that asserts
  "every indicator has a ribbon" is wrong, not the UI: the correct
  assertion is exactly one ribbonless square, rightmost, and ribbons on all
  the others.
- **`modeRemove(name)` is bookkeeping only.** It splices the stack entry,
  re-applies z-order and re-renders the indicators — it does **not** run
  `onExit` and does **not** hide the mode's root. Callers must tear the
  mode down first; the public door for "close this mode" is its own
  `onExit` (`modeTop().onExit()`), which is what the ribbon path calls.
  Calling `modeRemove` on its own leaves a visible, unreachable mode.
- **The coordinate contract applies to the composure canvas too, and it has
  three spaces rather than two.** Pointer coordinates are top-level CSS px
  and must be divided by `UIZ()` before they become stage px, and by `Z`
  again before they become world units — `compEventToStage()` is the one
  place that division happens, so route through it rather than doing the
  arithmetic inline. **Composure ignores `--txz`**, like the diagram
  canvases. Inside `#comp-world`, anything that must stay one size on
  screen divides by `var(--comp-z)`; anything that can live in
  `#comp-overlay` (screen space) should, because it then needs no
  counter-scaling at all. See "Display scales" for the general rule.
- **Inside a composure page, Esc belongs to the user only if the user
  placed the caret.** `COMP.caretAuto` records whether the *canvas* put the
  caret there (the blank form's opening blink) or the user did. Esc in a
  focused page leaves the text tool and **consumes the press only when
  `caretAuto` is false**; a caret the canvas placed is not something the
  user chose, so Esc keeps travelling and means what it always means.
  Typing into it makes the caret the user's. The other half is
  `compMayTakeFocus()`: the canvas never takes the caret from a modal, from
  a contenteditable, or from a composer with a draft in it — it *will* take
  it from an **empty** `#message`, which holds focus at boot only because
  the textarea carries `autofocus`.
- **Every new global-state location needs a seam, in both harnesses, in
  the same change.** The rule is not "add an `ENOUGH_*` variable"; it is
  add it *and* wire it into **`scripts/smoke_boot.build_env()`** and
  **`tests/conftest.py`'s `_STATE_SEAMS`** (autouse for the whole suite).
  `ENOUGH_READVISORS_ROOT` is the current example of why: without it an
  `install_readvisor` at global scope during a test or a scratch QA run
  writes into the developer's real `~/enough/readvisors/` and is then
  symlinked into every project they open afterwards — a leak that survives
  the run that caused it. Anything a test can reach that is not under
  `tmp_path` is a bug in the seam list, not in the test.
- **Don't put `--btn-bg` in `:root`.** Button chips use `var(--btn-bg,
  var(--bg-raise))`, and the fallback is load-bearing: old user configs that
  predate the `btn-bg` theme color rely on `--btn-bg` being *undefined* so
  the `--bg-raise` fallback kicks in. A `:root` default would defeat that.
  The shipped themes carry `btn-bg` in their theme `colors` (and the
  server backfills it for pre-0.1.6 configs — see `_merge_shipped_theme_keys`
  in server.py); the CSS default must stay absent.
- **The `cacheawl:` scheme resolves through `_resolve_project_path` only.**
  That's the single door from the project-relative file endpoints into the
  machine-global store. Don't add other global-path prefixes or bypass the
  helper — the traversal check and the mirror/sidecar write-guards all hang
  off that one resolution point.
- **The pytest suite lives in `tests/`** (tracked since the seven-models
  round; it was gitignored before — `git log` has the story). Run
  `uv run pytest tests/ -q` before declaring done; it covers girraphs,
  project metadata, the cacheawl store + `/api/cacheawl/*` + the
  `cacheawl:` scheme, the ui-config theme-key merge, the models
  registry/feasibility/downloads, the desktop shutdown gate, the shipped
  skills' conventions (`test_skills_defaults.py`), the skill trust model +
  first-use audit + `/api/skills*` (`test_skill_audit.py`), document
  conversion (`test_convert.py` — registry, naming, the state machine, the
  docx round trip, exports; `test_convert_api.py` — every `/api/convert/*`
  route, `/api/file/blob`, tree hiding, the SSE shapes;
  `test_convert_docling.py` — the docling engine, skipped without prefetched
  weights; `conftest.py` builds the `.docx` fixture with pandoc at test
  time rather than checking a binary into the repo), the home screen
  (`test_home.py` — the counting agreement with the top bar, the counted
  file set, the registry round trip + corrupt-read + unknown-key survival,
  the fingerprint short-circuit, seeding, the add guards, the handoff file,
  `exec_argv`, the project map, the `ModeGate` both ways, every
  `/api/home/*` payload, and the `<body>` marker), and the
  throttled newer-snapshot check (`test_wikisink_newer_snapshot.py` —
  which, like every other suite, can never reach kiwix.org or a model).
  Suites
  isolate global state via env hooks — `ENOUGH_WIKISINK_CONFIG`,
  `ENOUGH_CACHEAWL_ROOT`, `ENOUGH_INFOWORLD_ROOT`, `ENOUGH_UI_CONFIG`,
  `ENOUGH_WEIGHTS_DIR`, `ENOUGH_EXTRAS_STATE`, `ENOUGH_LIVE_STATE`,
  `ENOUGH_MODELS_REGISTRY`, `ENOUGH_PROJECTS_STATE`,
  **`ENOUGH_READVISORS_ROOT`**
  (plus `ENOUGH_MODELS_URL_BASE`, which rebases the model download URLs
  onto a local stub server, keyed by local gguf_filename) — all
  pointed at `tmp_path`; **never run against real `~/enough` state.**
  `tests/conftest.py`'s `_STATE_SEAMS` is **autouse for the whole suite**,
  which is how `ENOUGH_PROJECTS_STATE` and `ENOUGH_READVISORS_ROOT` are
  closed by default rather than by remembering: half the suite calls
  `ensure_skeleton()`, which registers the project, so without the first a
  test run would file the developer's tmp dirs on their real home screen —
  and the second is what stops a global-scope `install_readvisor` test
  writing into their real `~/enough/readvisors/`. Note the projects seam is
  also read by the **Rust shell** (`config::enough_config_dir()`), which is
  where the `.home-open` handoff lands. The composure round's suites
  (`test_composure.py`, `test_composure_api.py`, `test_composure_tools.py`,
  `test_composure_outline.py`, `test_project_meta_composure.py`,
  `test_council.py`, `test_council_api.py`, `test_prompt_weight.py`,
  `test_readvisors.py`, `test_readvisors_defaults.py`,
  `test_fetch_and_cache.py`) never reach a model or the network:
  `council.run_council_turn` is the one seam every council test replaces,
  and a council test that needs a model has bypassed it. The
  rest of the web layer is exercised via TestClient against `create_app()`.
  **The `ENOUGH_*` list is not sufficient on its own**: `broker.json`,
  `openrouter.json`, `orchestrator.json`, `~/enough/.llama-server/server.pid`
  and `~/enough/bin/` are plain `Path.home()` reads with no hook, so a
  suite (or a scratch server) that touches any of them must also
  `monkeypatch.setenv("HOME", …)`. `tests/test_llama_server_lookup.py`,
  `tests/test_platform_linux.py` and `scripts/smoke_boot.py` all do.
- **The `ENOUGH_DESKTOP*` vars are NOT scratch-isolation hooks** — they
  are the desktop shell's capability gate, set by the shell when it
  spawns a backend. `ENOUGH_DESKTOP=1` enables `POST /api/shutdown` (the
  route 404s without it, so a CLI `enough` has no shutdown surface);
  `ENOUGH_DESKTOP_TOKEN` is a per-launch secret the caller must echo in
  the `X-Enough-Desktop-Token` header (mismatch → 403; it's CSRF
  protection, not a local-process boundary). `ENOUGH_DESKTOP_CODE` and
  `ENOUGH_DESKTOP_UV` are read by the *shell*, not the backend: they
  override which checkout it runs (`uv run --project $ENOUGH_DESKTOP_CODE`)
  and which `uv` binary it uses; `ENOUGH_DESKTOP_LLM_URL` (2b) makes it
  pass `--llm-url`, which is the one piece of shared state the `ENOUGH_*`
  hooks can't isolate — a scratch run without it would reach the machine's
  real llama-server on 8080. Decisions + rationale: the "Milestone 2a
  landed" and "Milestone 2b landed" blocks in docs/tauri-plan.md (local
  planning doc, untracked).
- **`ENOUGH_LLAMA_SERVER` is a real lookup rung, not a test hook.**
  `models.find_llama_server()` is the single place the llama-server binary
  is located — `$ENOUGH_LLAMA_SERVER` → `~/enough/bin/llama-server` →
  PATH — and `supervisor._launch`, `llama_release()`, `release_gate()`,
  `spec_flags()` and `draft_flags()` all resolve through it (pass an
  explicit `binary=` only when you already resolved one and want the
  version you gate on to be the version you run). Three installers depend
  on that order: the desktop app points rung 1 at its bundled sidecar, the
  Linux installer owns rung 2 (`bootstrap.sh` unpacks a checksum-pinned
  llama.cpp release archive into `~/enough/bin/` — `.so` files flat beside
  the binary, because its only RPATH is `$ORIGIN` and the `libggml-cpu-*`
  backends are `dlopen`'d from the same dir), Homebrew is rung 3. Don't
  reintroduce a bare `shutil.which("llama-server")` anywhere — **including
  in shell**: `llama_server.sh` asks
  `python -m enough.models llama-server-path` rather than running its own
  `command -v llama-server`, because on Linux the pinned build is
  deliberately not on PATH and the two would have silently disagreed.

---

## Customization patterns: global vs project-local

`enough` is built on a "default + override" pattern.

**Global** — edit `~/enough/defaults/...` and every project that hasn't
been customized yet picks up the change on next launch (or after the
user types `/update-enough`).

**Per-project** — in the preview pane, click *customize for this
project* on a symlinked file. The symlink gets replaced with a local
copy. Other projects keep using the global default. Symlinked files
render *italic + muted* in the file tree; project-local copies render
normally.

`skeleton.ensure_skeleton()` runs on every launch and:
1. Creates `rness/` if missing
2. Copies `_PROJECT_LOCAL_FILES` (AGENT.md, MOTIVATION.md, profile,
   active-paradigm seed) only if absent — preserves user edits
3. Applies `_SKELETON_PLAN` on first-time `rness/` creation —
   `AGENT.md`/`MOTIVATION.md` are **copied**, the four policies and
   `knowledge/rosetta-primers` are **symlinked** from `~/enough/defaults/...`
4. Runs three populators on **every** launch — `_populate_skill_symlinks`,
   `_populate_role_symlinks`, `_populate_paradigm_symlinks` — so newly
   shipped skills/readvisors/paradigms appear in existing projects without
   the user running `/update-enough`. Each populator globs
   `~/enough/defaults/<kind>/`, symlinks anything new, prunes dangling
   symlinks left over from removed globals. Skills and readvisors
   default-off (added to `.disabled`) — **except a name pruned as dangling
   and re-created in the same pass, which is a heal and keeps its toggle**;
   paradigms have no off concept, exactly one is active at a time. The
   readvisor populator additionally walks **two** global sources
   (`~/enough/readvisors/` then the install's `defaults/readvisors/`) and
   re-aims managed links — see "Readvisors".
5. Creates `_EMPTY_DIRS` (requests, session-logs, io, `rness/readvisors`,
   `rness/io/composure`, etc.) as needed
6. Runs migrations for older project layouts — including
   `_migrate_roles_to_readvisors`, which runs after `_migrate_undot` and
   **before** the populators

---

## Philosophy (the "why" for agents reading this)

Three threads worth being aware of when you're advising the user on
modifications:

1. **Local-first as a default, not a religion.** Privacy is the pro;
   cost is a separate axis. The hardware to run capable local models is
   expensive (acquisition + electricity), sometimes more than equivalent
   cloud inference. OPRO-API is the considered escape valve: a piercing
   that's intentionally hard to enable accidentally, with the trade-offs
   spelled out at every step. The right framing for a user weighing it
   is: "privacy is what local-first guarantees; cost is where the
   numbers might favor cloud — your call."
2. **The broker is the trust anchor.** Every tool call goes through it.
   Allowlists, toggles, denials, journal. When you're tempted to bypass
   the broker for "simplicity," you're proposing to take a permission
   decision out of the user's hands. Don't.
3. **One folder, one chief readvisor.** No cross-project orchestration and
   no shared state across projects: different folder → different readvisor
   → different memory. This is a discipline, not a limitation. Users
   running multiple `enough` instances coordinate through the
   filesystem (e.g. a shared cachebox in `~/enough/cacheawl/`). A
   **council** does not break the rule — it is several readvisors *of this
   project* speaking in turn on one canvas, sharing one model and one
   window, not several enoughs talking to each other.

---

## Development

```bash
git clone https://github.com/0gsd/enough.git
cd enough
uv sync                    # installs all deps including keyring
uv run enough --help
uv run enough --home       # the launch screen; no project, no llm, no broker
```

Dependencies of note (Python, via `uv sync`):
- `fastapi`, `uvicorn[standard]`, `sse-starlette` — the web layer
- `httpx[socks]` — outbound HTTP, with SOCKS support for Tor routing
- `keyring>=24` — OS keyring for the OpenRouter api key
- `ctranslate2`, `sentencepiece`, `huggingface_hub` — translator skill
- `pypandoc-binary`, `typst` — the document converters (0.2.5). **Base
  deps, not extras**: every install, DMG included, ships a pandoc and a
  typst, so HTML→markdown, the docx/odt/rtf/epub round trip, and
  markdown→PDF all work with no Homebrew and no extra step. A user's own
  `pandoc` on PATH still wins (`convert.pandoc_path()`)
- optional extra `pdf` (`uv sync --extra pdf`, normally installed from the
  UI) — docling + torch for PDF/deck/workbook *reading*. See "Document
  conversion"

Plus external binaries installed by `bootstrap.sh` via Homebrew:
- `llama.cpp` — local LLM inference server (backs everything except OPRO-API)
- `whisper-cpp` — local speech-to-text for the chat mic button
- `tor` — anonymized off-allowlist web fetch via the broker
- `harper` — local grammar/spell checker (Automattic, Apache-2.0).
  The analyzer skill's proofread mode shells out to `harper-cli`
  for the silent-fix pass; absence is handled gracefully (skill falls
  back to LLM-only scanning).

(pandoc left that list in 0.2.5 — it comes from the venv now. `bootstrap.sh`
no longer offers to install it on either platform, and
`tests/bootstrap_linux_harness.sh` has two `check_no_grep`s defending that.)

Plus, on Linux, the same roles filled differently (see "Platforms, and
CI"): llama.cpp is a checksum-pinned prebuilt release in `~/enough/bin/`
rather than a formula; tor comes from apt/dnf; whisper.cpp and
harper have no distro package and are built from their own repos.
`bootstrap.sh` prints those commands and installs none of them.

A pytest suite lives in `tests/` (girraphs, project metadata, the cacheawl
store + endpoints + `cacheawl:` scheme, the ui-config theme-key merge, the
models registry/feasibility/downloads, the llama-server lookup, the desktop
shutdown gate, the platform seams, the shipped skills' frontmatter/tooltip/
script conventions, the skill trust model + first-use audit + `/api/skills*`,
document conversion + `/api/convert/*` + `/api/file/blob`,
the home screen + registry + handoff + `/api/home/*`,
the throttled wikisink newer-snapshot check, and — since 0.3.5 — the
composure format/ops/API/tools + the outline converter, the council engine
+ `/api/council/*`, the readvisors' migration/sources/install/removal, and
the prompt-weight budgets) — **tracked since the
seven-models round**, so a fresh clone has it. Before declaring anything
done:

```bash
uv run pytest -q                        # 1065 tests (+docling skips)
uv run python scripts/smoke_boot.py     # real boot, scratch dir
bash tests/bootstrap_linux_harness.sh   # only if you touched bootstrap.sh
```

Rust, if you touched the shell: `cargo test` in `desktop/src-tauri/`
(43 tests — the launch routing, `window_title` and the exit-42 handshake are
pure functions precisely so they're covered here).

CI runs exactly those three on ubuntu-latest and macos-latest. Anything
not covered by them is smoke-tested via ad-hoc Python scripts that
exercise the modules directly (sometimes via FastAPI's TestClient against
`create_app()`) — examples are in git history under recent commits
touching `cloud.py`, `tools.py`, and `server.py`.

### The pre-commit suite

One command has to be green before every commit:

```bash
uv run python scripts/precommit.py            # everything (~6 min)
uv run python scripts/precommit.py --quick    # what the hook runs (~90 s)
uv run python scripts/precommit.py --list
uv run python scripts/precommit.py --only ui -v
```

Install the hook once per clone — nothing in the repo runs `git config`
for you:

```bash
git config core.hooksPath .githooks
```

`.githooks/pre-commit` runs the suite in `--quick` mode. The bypass is the
ordinary `git commit --no-verify`, and it is there for the case where the
suite itself is what you are fixing.

**Six stages**, each timed, each one PASS/FAIL/SKIP line. The first five
are what CI already runs (`bash -n`, `pytest -q`, `i18n_check.py`,
`smoke_boot.py`, `bootstrap_linux_harness.sh`); the sixth is new.

- **`tests/test_content_integrity.py`** (inside `pytest`, so CI gets it
  free) is the *content* half. `i18n_check.py` compares key **sets**;
  this compares the things sets cannot see. Every `en/ui.json` value is
  byte-identical to the inline English in index.html (docs/I18N.md has
  always claimed that; nothing enforced it until now), including
  `t('key', 'English')` call sites. A key used at several sites carries
  the same English everywhere. `{placeholders}` and inline HTML survive
  into all five translations. A translated value byte-equal to its
  English is flagged unless it is a brand word or a listed cognate. The
  reachable help ids (static `data-help` ∪ `server._HELP_IDS` ∪
  `converted-file`) and the `## <id>` sections of `help-docs.md` are a
  bijection, modulo an explicit `UNREACHED_SECTIONS` list. Every help
  section has `name:`/`path:` and `### what`/`### how`/`### ideas` in
  order, and every `{{token}}` is one `_helpExpandTokens()` actually
  implements (scraped from index.html, not hard-coded). HELP_CENTER.md's
  `## N.` / `### N.M` numbering is contiguous and its "section N"
  cross-references resolve. Every icon name the frontend asks for has
  both built SVG variants. All seven places that name the version agree.
- **`scripts/ui_check.py`** is the *layout and behaviour* half: a real
  headless Chrome over the DevTools Protocol, driving two scratch enough
  servers (project + home). **Zero new dependencies** — CDP is JSON over
  one WebSocket and `websockets` already ships as a transitive of
  `uvicorn[standard]`. For every (screen × viewport × language) it asks
  the page to measure itself: clickables that something in their own
  layer covers, rects that overlap where the overlap costs a click, text
  clipped under `overflow:hidden`, controls outside the viewport with no
  scroller, targets under 16px. Then it runs the MODE STACK scenarios
  once per language. No Chrome anywhere → one SKIPPED line and a green
  run; CI has no guarantee of a browser.

**The rule that keeps it alive: every UI change adds or updates its
screen(s) and scenario(s) in the same change.** A new modal, mode or
panel gets a `Screen` in `scripts/uicheck/screens.py`; a new interaction
contract gets a scenario in `scripts/uicheck/interactions.py`. A harness
that describes a UI that no longer exists is worse than no harness,
because it is still green.

Extending the registry is meant to be cheap. A `Screen` is a name, a mode
(`project` or `home`), and two lists of tiny declarative steps — `click
#id`, `key Escape`, `eval openUIModal()`, `wait_for <selector>`,
`wait_gone <selector>`, `wait_idle`. Steps drive the product's own entry
points rather than poking the DOM, and an `eval` step is a *trigger*: the
`wait_for` after it is the wait (several `enter*Mode()` functions are
async, and `confirmOverlay()` returns a promise that only settles when a
user answers). `--list` prints the registry; `--screens`, `--langs` and
`--viewports` narrow a run while you are writing one.

Nothing here touches your real state. Both servers boot through
`smoke_boot.build_env()` — every `ENOUGH_*` seam and `$HOME` inside a temp
dir — and `tests/conftest.py` does the same for every test via an autouse
fixture. The UI language is flipped with `POST /api/ui-config`, which
lands in the scratch `$HOME`, never in your `~/enough/config/ui.json`.

**Two lists of accepted failures**, and they work the same way on
purpose: both are green today, both go red when something NEW appears,
and both go red when a listed item is fixed and its entry is left behind.

- `KNOWN_FINDINGS` in `tests/test_content_integrity.py` — content drift
  that exists in today's tree and belongs to a later lane. Keep it tiny;
  an entry that survives a release is an entry nobody will ever action.
- `scripts/uicheck/baseline.json` — accepted layout findings, keyed by
  `(screen | class | selector-path)` and deliberately **not** by pixel
  values, viewport or language, so an entry survives a re-layout and dies
  with the element it names. `--update-baseline` rewrites it; read the
  diff, because a key that disappears means something got fixed. It is a
  to-do list, not an amnesty — and **every entry is justified by family in
  `scripts/uicheck/baseline-notes.md`**, which says what each one is, why
  it is accepted and which lane should fix it. Add an entry, add a
  paragraph; fix one, delete both.

One thing the harness will not do, and it is deliberate: **Escape is
dispatched from inside the page, not through `Input.dispatchKeyEvent`.** On
a tab the browser has activated, an Escape input event deadlocks headless
Chrome's *browser* process — every tab and the DevTools HTTP endpoint with
it — which is what made `--quick` stop dead for three phases. See
`_SYNTHETIC_KEYS` in `scripts/uicheck/driver.py` for the measurements and
for what a synthetic event does and does not still prove. Every step and
every scenario also has a hard wall-clock budget backed by a watchdog that
cuts the socket, because the pre-commit hook runs this and a hook that can
hang is a hook that gets uninstalled.

---

## License

Apache 2.0. See [LICENSE](../LICENSE).

Third-party content (the bundled `defaults/skills/` packages) carries
its own licenses — see [THIRD_PARTY_LICENSES.md](../THIRD_PARTY_LICENSES.md).
