# enough — Agent Guide (v0.2.8)

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

`enough` is a paradigmless personal computer harness powered by a local
LLM. It runs on the user's machine, exposes a chat UI at
`http://127.0.0.1:3456`, and lets the user shape the agent's behavior by
editing markdown files. Started with `--home` instead of a project it
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
| `~/enough/` | The global install. Cloned from the repo by `bootstrap.sh`. Contains `defaults/` (templates that get copied / symlinked into every project), `cacheawl/` (the machine-global file store — see below), and the Python source. (The old `infoworld/` library is dissolved into `cacheawl/` on first 0.1.6 launch.) | Edit these to affect every project. |
| `~/enough/config/` | User-global JSON config. `broker.json` (toggle states), `models.json` (active local model), `openrouter.json` (cloud-slot metadata, **no api key**), `ui.json` (theme/font), `orchestrator.json` (auto-reset config), `wikisink.json` (wikisink install registry + watch/override registries + reading state), `desktop.json` (desktop-shell launch prefs: reopen toggle, last/known projects, onboarding state — shared-visible with the CLI, written by `desktop/src-tauri/src/config.rs`), `extras.json` (which optional dependency groups are installed — read by Python, bash **and** Rust; see "Document conversion"), `projects.json` (the home screen's project registry — see "The home screen"), and the transient `.home-open` handoff file. | Edit per-machine settings. |
| `~/enough/wikisink/` | Default wikisink location: the user's wikisink *data* (comments, overlays, preserved articles, rankings, run state) and — unless pointed elsewhere — the base `.zim` archive(s). Archives can live anywhere, external drives included; several installs can be registered at once. Hidden from the file-manager tree. | Managed via the 🚰 UI; don't hand-edit. |
| `~/enough/cacheawl/` | The machine-global **cacheawl** store: root-level folders are *cacheboxes* (plain kept-forever text, or cached replicas ingested from a path/URL/wikisink). Global wiki saves land in the `wiki/` box; the dissolved infoworld folders become the `personal`/`public`/`wiki` boxes. Overridable via `ENOUGH_CACHEAWL_ROOT`. Hidden from every project's file tree. | Managed via the cacheawl mode UI + agent tools; sidecars are backend-owned. |
| `<project>/rness/` | The agent's per-project skeleton. Symlinks back into `~/enough/defaults/` for shipped paradigms/skills/policies/roles; per-project copies of `AGENT.md`, `MOTIVATION.md`, `active-paradigm`; per-project state in `io/`, `requests/`, `knowledge/`. | Edit to affect just this project. |

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
| [enough/server.py](../enough/server.py) | ~4180 | FastAPI app: chat dispatch, SSE streaming, file tree, model modal, broker modal, auto-reset orchestration, all `/api/*` endpoints (including `/api/wiki/*`, `/api/models/*`, `/api/skills*` — whose toggle is guarded by `skillaudit` — the desktop-gated `POST /api/shutdown`, and `/api/home/*` + `/api/close-project`; see the `ENOUGH_DESKTOP*` note under "What NOT to touch"). Also owns the **mode boundary**: `create_app(home=…)`, the `ModeGate` ASGI middleware, `HOME_PATHS`/`HOME_PREFIXES`, and the `data-mode` marker templated into `/`. | `create_app()`, `_drive_message()`, `ModeGate`, `HOME_PATHS`, `request_process_exit()` / `request_process_exec()` (module-level so tests can swap them), `HANDOFF_EXIT_CODE`, all `@app.{get,post}` handlers |
| [enough/prompt.py](../enough/prompt.py) | ~890 | Assembles the system prompt from `rness/` on every turn (no caching). Also owns skill/role/paradigm enumeration + toggle-state helpers. `set_skill_enabled()` is the dumb `.disabled` writer — the *guarded* door for skill toggles is `skillaudit.set_skill_enabled_guarded()` (see "Skill trust"). | `assemble_system_prompt()`, `TOOL_INSTRUCTIONS`, `convert_instructions()`, `list_skills()` / `set_skill_enabled()`, `list_roles()` / `set_role_enabled()`, `list_paradigms()`, `get_active_paradigm()` / `set_active_paradigm()` |
| [enough/skillaudit.py](../enough/skillaudit.py) | ~900 | First-use audit of untrusted skills (0.2.2). Trust classification (symlink into *an* enough install's `defaults/skills/` = trusted — this install or a sibling one, since 0.2.7), the content fingerprint, the `verdict.json` sidecar, both audit passes (deterministic `payload_scanner.py` + a single non-streaming LLM completion), the in-flight registry, and the guarded toggle. Progress on the `skill-audit` SSE event. | `is_trusted()`, `fingerprint()` / `skill_fingerprint()`, `skill_state()`, `set_skill_enabled_guarded()`, `SkillAuditRefused`, `audit_skill()` / `audit_and_enable()`, `run_llm_audit()` (module-level test hook), `quarantine_untrusted()`, `trust_override()`, `read_verdict()` / `write_verdict()` |
| [enough/broker.py](../enough/broker.py) | ~380 | Broker config (toggles), trace journal writer, canned denial messages. New toggles auto-render in the broker pane via `/api/broker`. | `TOGGLES` tuple, `load_config()`, `is_enabled()`, `trace()`, `denial_*()` |
| [enough/tools.py](../enough/tools.py) | ~1360 | Tool runners (`read_file`, `write_file`, `shell`, `fetch_url`, `read_highlights`, `navigate_to_highlight`, `cloud_pipeline`, girraph ops, wiki tool wrappers), the tool-call XML parser, the dispatch table. | `_DISPATCH`, `_TRACE_TOGGLE`, `execute()`, `parse_tool_calls()`, `_CLOUD_KEY_EXFIL_PATTERNS` |
| [enough/convert.py](../enough/convert.py) | ~1365 | Document conversion (0.2.5): the format **registry** (`FORMATS`), engine probing + caching, twin/assets/manifest naming, the state machine, the job runner that drives the worker, export/sync/resolve, and the `pdf`-extra installer. Imports nothing heavy — docling and pandoc are only ever reached through `convert_worker`. See "Document conversion" below. | `FORMATS` / `formats_view()` / `engines()`, `pandoc_path()` / `typst_path()` / `docling_available()`, `twin_path()` / `assets_dir()` / `manifest_path()` / `pair_for()`, `state()` / `has_twin()`, `read_manifest()` / `write_manifest()`, `ConvertJobs`, `do_export()` / `sync_after_save()` / `resolve()`, `ExtraInstaller`, `installed_extras()` / `record_extra()`, `reset_engines()` |
| [enough/convert_worker.py](../enough/convert_worker.py) | ~620 | The out-of-process worker: `python -m enough.convert_worker`, one JSON job on stdin, NDJSON records on stdout, exit. pandoc is shelled out to; **docling runs in this process** — which is the whole reason the worker exists (torch must never be imported into the server). | `main()`, `_OPS` (`convert` / `export` / `prefetch`), `do_convert()` / `do_export()` / `do_prefetch()`, `_convert_docling()`, `_flatten_media()` / `_relink_docling_assets()` / `_normalize_images()`, `_Heartbeat`, `TWIN_FORMAT` |
| [enough/wikisink/](../enough/wikisink/) | ~2500 (pkg) | Local offline Wikipedia. `config.py` (install registry, schema v2 multi-install, data paths), `zim.py` (libzim reader, search, sanitize/rewrite), `download.py` (Kiwix flavor listing + resumable downloads), `overlay.py` (live-refreshed + preserved article stores), `comments.py` (per-article threads), `save.py` (save/read/unsave article folders + the clean HTML→markdown text pipeline), `update.py` (the "wikisink" update run), `rankings.py` (pageview snapshots), `report.py` (run report), `agent.py` (the four agent tool runners). | `config.load_config()` / `installs()` / `active_install()` / `unavailable_reason()`, `zim.get_article()` / `search()`, `download.DownloadManager`, `update.run_wikisink()` |
| [enough/cloud.py](../enough/cloud.py) | ~1000 | OpenRouter integration: keyring read/write, in-memory key cache, OpenAI-compatible streaming + non-streaming clients, health check, response caching to `rness/io/cloud-cache/`, the broker-driven `pipeline_run()`. | `set_api_key()` / `clear_api_key()` / `has_api_key()`, `_get_api_key_for_broker()`, `health_check()`, `chat_completion()`, `stream_chat_completion()`, `cache_completion()`, `pipeline_run()` |
| [enough/llm.py](../enough/llm.py) | ~125 | OpenAI-compatible client for the local llama-server. Streaming-only path for chat. | `stream_chat()`, `check_llm_reachable()` |
| [enough/supervisor.py](../enough/supervisor.py) | ~400 | Manages the local llama-server subprocess. Adopts an existing process if one's already up; spawns its own otherwise. Skips spawning entirely when the active model is `opro-api`. | `LlamaSupervisor`, `_resolve_startup_choice()` |
| [enough/models.py](../enough/models.py) | ~550 | Local-model registry (7 cute-named local models, defined in `defaults/models.json`; two carry separate MTP draft GGUFs, two carry a `llama_cpp_min_release` gate). Feasibility verdicts (RAM + free disk), `install-menu` CLI for bootstrap.sh. Selection state in `~/enough/config/models.json`. | `load_registry()`, `load_state()`, `save_state()`, `resolve()`, `all_models_view()`, `feasibility()`, `release_gate()`, `install_menu_rows()` |
| [enough/model_download.py](../enough/model_download.py) | ~330 | Resumable GGUF downloads for the in-app model manager: main file then optional MTP draft, ranged-GET resume off a `.part`, one active download per process, cancel-keeps-partial, delete. Backs `/api/models/{download,delete}/*`; progress on the `model-dl` SSE event. | `ModelDownloadManager` (`start` / `cancel` / `delete` / `state`), `pending_phases()`, `partials()` |
| [enough/skeleton.py](../enough/skeleton.py) | ~710 | Creates `rness/` for new projects (copies from `defaults/`), syncs global skills/roles/paradigms on every launch via dedicated populators, runs migrations. `_populate_skill_symlinks` also heals materialized copies of shipped skills (a byte-identical real dir left by a cloud-sync/dereferencing copy is swapped back to a symlink — 0.2.8) and calls `skillaudit.quarantine_untrusted()` — untrusted skills default OFF. | `ensure_skeleton()`, `resync_globals()`, `_SKELETON_PLAN`, `_PROJECT_LOCAL_FILES`, `_EMPTY_DIRS`, `_populate_skill_symlinks` / `_populate_role_symlinks` / `_populate_paradigm_symlinks` |
| [enough/footnotes.py](../enough/footnotes.py) | ~330 | Footnote surgery for in-progress markdown (0.2.7): parse/renumber/insert over standard `[^n]` refs + a terminal definitions block. Pure functions, offset-stable code-masking (fences + inline spans blanked to NULs), numeric labels managed, named tolerated, orphan defs never touched. `tests/test_footnotes.py` doubles as the spec for the `fn*` JS mirror in index.html. | `parse()`, `renumber()`, `next_number()`, `insert_at()`, `definitions_span()`, `REF_RE` / `DEF_RE` |
| [enough/paginate.py](../enough/paginate.py) | ~920 | Pagination (0.2.7): options schema + named size table, output naming (`name-YYYY-MM-DD.pdf` + `-1`/`-2`), the `.typ` surgery (pandoc-template split, balanced-bracket `#footnote[...]` extraction, endnote reflow, option preamble), pure 2-up/booklet imposition math, bundled-fonts lookup, and the PDF source-attachment probe that powers unpack-on-import. Heavy lifting (pandoc/typst/pypdf compile) runs in `convert_worker.do_paginate`. See "Pagination" below. | `validate()`, `sizes_view()` / `page_size_mm()`, `output_pdf()` / `pages_dir()` / `viewer_manifest_path()`, `fonts_dir()` / `font_paths()`, `embedded_source()` / `has_embedded_source()`, `sheet_order()` / `slot_rect()`, `split_template()` / `extract_footnotes()` / `place_endnotes()` / `preamble()` / `build_typ()`, `status()` / `run_paginate()`, `PaginateError` |
| [enough/highlights.py](../enough/highlights.py) | ~250 | Review-mode color highlights (yellow/green/blue/pink) stored in per-doc `.<filename>.highlights.json` sidecars. Tools `read_highlights` and `navigate_to_highlight` consume them. | — |
| [enough/girraph.py](../enough/girraph.py) | ~695 | The girraph primitive: parser/serializer for the plain-text `.girraph` IBIS format, node-level ops (the only way content changes), ASCII tree renderer, per-path write locks. Agent tools and UI endpoints both call through here. | `loads()` / `dumps()`, `add_node()` / `update_node()` / `link_nodes()` / `remove_node()`, `ascii_render()`, `path_lock()` |
| [enough/cacheawl.py](../enough/cacheawl.py) | ~1470 | The cacheawl store: cachebox CRUD, path/URL/wikisink **ingest**, the `_cachebox.merirmaid` mirror generator + reconcile, the mirror/sidecar write-guards, transfer (copy/move), and the launch-time `infoworld` migration. Root is `~/enough/cacheawl/` (or `ENOUGH_CACHEAWL_ROOT`). Owns everything under the store; nothing else writes there. Since 0.2.5 it also exports the generic folder→flowchart walker `home.py` builds project maps with. | `root()`, `create_cachebox()` / `list_cacheboxes()` / `cachebox_tree()`, `run_ingest()`, `regenerate_mirror()` / `reconcile()` / `reconcile_all()`, `folder_flowchart()`, `mirror_write_denial()`, `migrate_infoworld()` |
| [enough/home.py](../enough/home.py) | ~740 | The home screen (0.2.5): the project **registry** (`~/enough/config/projects.json`, seam `ENOUGH_PROJECTS_STATE`), the ¶/W/C counters ported from the top bar, the fingerprint cache (which since 0.2.8 also snapshots the `rness/project.json` display name/description so an unreachable folder's row keeps its nice name — live reads still win), seeding from the shell's `desktop.json` MRU (temp-dir paths — chiefly the wizard's `$TMPDIR/enough-onboarding` scratch — are refused, skipped, and pruned when the registry is durable, 0.2.8), the project map (via `cacheawl.folder_flowchart`), the add-guards + the osascript folder chooser, and both halves of the open/close handoff. Imports `server` **lazily, inside functions** — `server` imports `home` at module level, and that is the cycle-breaker. | `projects_state_path()` / `config_dir()` / `handoff_path()`, `read_registry()` / `save_registry()` / `register()` / `touch_opened()` / `set_hidden()`, `seed_from_desktop()`, `count_text()` / `fingerprint_of()` / `refresh_entry()` / `list_projects()`, `build_project_mirror()`, `check_addable()` / `add_project()` / `choose_folder()`, `write_handoff()` / `read_handoff()`, `exec_argv()` |
| [enough/logger.py](../enough/logger.py) | small | Stdlib logging setup. | — |
| [enough/static/index.html](../enough/static/index.html) | ~20000 | The entire frontend — HTML, CSS, vanilla JS, htmx. Single file. | model modal, broker modal, OPRO-API wizard + settings, file tree (+ option-click context menu), chat pane, SSE consumer, wikisink setup/installs modal + reader mode, the unified read/edit mode (mini ↔ full frame), girraph mode, merirmaid mode, cacheawl split-view mode, the home frame + project map + handoff overlays (gated on `IS_HOME` / `body[data-mode]`), SVG icon pipeline (`data-icon`/`iconSrc`), `setActiveMode` registry, confirmOverlay |

`defaults/` ships templates that get copied or symlinked into project
skeletons by `skeleton.py`:

- `defaults/AGENT.md`, `defaults/MOTIVATION.md` — root identity files (copied)
- `defaults/skills/<name>/SKILL.md` — bundled skills (symlinked)
- `defaults/paradigms/<name>.md` — bundled paradigms (symlinked)
- `defaults/roles/<name>/` — bundled consultant personas (symlinked)
- `defaults/policies/*.md` — operating policies (symlinked)
- `defaults/models.json` — local-model registry template
- `defaults/openrouter-config.json` — cloud-slot metadata template
- `defaults/ui-config.json` — UI prefs template

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
uv run python scripts/smoke_boot.py     # ~1.4s, 17 assertions
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

1. The handler appends `{role: "user", content: ...}` to `session.history`
   and emits the bubble via SSE.
2. `_drive_message` (in [server.py](../enough/server.py)) starts the tool
   loop, capped at `session.max_tool_iters` iterations.
3. On each iteration:
   - `assemble_system_prompt(project_dir)` rebuilds the system prompt
     **from disk** — `rness/AGENT.md`, `rness/MOTIVATION.md`, the active
     paradigm, active skills, active roles, the project profile, the
     tool instructions, the paradigm catalog. No caching; edits to any
     of these files land on the next message.
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
| Agent identity | `rness/AGENT.md` (copied) | `defaults/AGENT.md` | yes — top of prompt |
| Motivation | `rness/MOTIVATION.md` (copied) | `defaults/MOTIVATION.md` | yes |
| Active paradigm | `rness/active-paradigm` (multipurpose markdown: paradigm name + help-bubbles state — see "What NOT to touch") | seeded by `prompt.seed_multipurpose_file()` | the active paradigm's full file, yes |
| Paradigms | `rness/paradigms/<name>.md` (symlink) | `defaults/paradigms/<name>.md` | the active one, yes |
| Skills | `rness/skills/<name>/SKILL.md` (symlink = shipped/trusted; a real dir = untrusted) | `defaults/skills/<name>/SKILL.md` | the toggled-on ones, yes |
| Skill audits | `rness/io/output/analyzer/audits/<skill>/<YYYY-MM-DD>-audit.md` + `verdict.json` | none — written by `skillaudit.py` or by analyzer's `audit` mode | no |
| Roles | `rness/roles/<name>/AGENT.md`+`MOTIVATION.md` (symlink) | `defaults/roles/<name>/` | the toggled-on ones, yes |
| Policies | `rness/policies/*.md` (symlink) | `defaults/policies/*.md` | yes, all of them |
| Project profile | `rness/knowledge/project-profile.md` | seeded empty | yes |
| Requests | `rness/requests/*.md` | none — agent creates | no (but agent reads on demand) |
| Highlights | `<dirname>/.<filename>.highlights.json` | none | no — read via tools |
| Session logs | `rness/knowledge/session-logs/<date>.md` | none | no |
| Broker journal | `rness/knowledge/session-logs/<date>-broker.md` | none | no |
| Fetched web cache | `rness/io/input/<timestamp>-<hash>-<slug>.md` | none | no |
| Cloud cache | `rness/io/cloud-cache/<timestamp>-<slug>.md` + `_cloud-index.md` | none | no |
| Saved wiki articles | `<project>/wiki/<slug>/` or `~/enough/cacheawl/wiki/<slug>/` (the global wiki cachebox; `"infoworld"` accepted as a legacy alias) — folder of `article.html` (verbatim archive copy) + `_manifest.md` + hidden `.meta.json` | none — created on first save | no (agent reads on demand) |
| Cacheboxes | `~/enough/cacheawl/<box>/…` — root-level box folders + backend-owned `.cachebox.json` + `_cachebox.merirmaid` sidecars | none — created via UI/agent/migration | no (agent reaches via cachebox tools) |
| Wikisink registry/state | `~/enough/config/wikisink.json` (user-global, **not** per-project) | none | no |
| Wiki comments/overlays | `<wikisink data dir>/comments/`, `overlay/`, `preserved/` | none | no |
| Converted documents | `<dir>/<name>.<ext>.md` (the twin — a user file), `<name>.<ext>.assets/` + hidden `.<name>.<ext>.convert.json` (both backend-owned) | none — written by `convert.py` on first open | no (the agent gets the twin through `read_file`; the *registry* is rendered into the prompt by `prompt.convert_instructions()`) |

**Active vs available**: skills and roles ship as files but only become
part of the system prompt when toggled on in the sidebar. The
*disabled* set is persisted per-project as a plain newline-delimited
text file: `rness/skills/.disabled` and `rness/roles/.disabled`. Read/
written via `prompt._read_disabled_skills()` / `set_skill_enabled()` (and
the role-side equivalents). New globals appear in every project with
their name added to `.disabled` on first sync — i.e. defaulted off.
**Untrusted skills also default off**, by a second route:
`skillaudit.quarantine_untrusted()` (called from
`skeleton._populate_skill_symlinks`, so every launch and every
`/api/skills`) names any untrusted skill without a matching `pass`
verdict into `.disabled`. Without it a hand-dropped or agent-written
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
   place ([`cloud._auth_headers()`](../enough/cloud.py)). The agent has
   no callable path to the key.

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

The agent and broker run in the **same Python process** — there is no
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
   cloud IS the agent; meant for `cloud_pipeline` output and any future
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
- `chat` — an interactive agent turn (one per `_drive_message` iteration)
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
This keeps multi-hundred-thousand-token batches out of the agent's
context window.

200-step ceiling per pipeline; output_path is constrained to inside the
project directory (path-traversal protection).

---

## The broker

A single Python module — [enough/broker.py](../enough/broker.py) — in
the same process as the agent. Three jobs:

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
   error strings for the agent. The runner returns one of these as the
   tool body when a precondition fails.

The current toggle catalog (11 toggles, all default `True`):

| Key | Group | Affects |
|---|---|---|
| `trace_log_enabled` | general | Whether broker journal entries get written |
| `local_models_only` | general | Whether OPRO-API appears in the model picker |
| `read_file_brokered` | read_file | Trace-logging for `read_file` (allowlist always enforced) |
| `write_file_brokered` | write_file | Trace-logging for `write_file` (allowlist always enforced) |
| `shell_brokered` | shell | Trace-logging for `shell` (no allowlist for shell by design) |
| `fetch_url_enabled` | fetch_url | Whether `fetch_url` works at all (otherwise agent falls back to `curl` via shell) |
| `fetch_url_tor_for_offlist` | fetch_url | Off-allowlist fetches via Tor (vs outright denial) |
| `fetch_url_cache_and_convert` | fetch_url | HTML→markdown (pandoc, a base dep since 0.2.5) + cache in `rness/io/input/` |
| `wikisink_enabled` | wikisink | Whether the agent's four wiki tools work at all (the 🚰 browser UI is ungated) |
| `wikisink_live_updates` | wikisink | Whether wikisink update runs may call the Wikipedia/Wikimedia APIs (off = report from local state only) |
| `cacheawl_enabled` | cacheawl | Whether the agent's three cachebox tools work at all (the cacheawl browser UI is ungated; URL ingests still additionally honor the `fetch_url_*` toggles) |

---

## Tools

| Tool | Runner | Gating |
|---|---|---|
| `read_file` | `tools.run_read_file` | path under project OR on file-read allowlist. A convertible original returns its **twin** (converting first, on a daemon thread joined for `tools.CONVERT_BLOCKING_SECONDS` = 120) — see "Document conversion" |
| `write_file` | `tools.run_write_file` | path under project OR on file-rw allowlist; not in `rness/requests/done/`. A refused sync-on-save of a syncing twin comes back as `ok=False` whose body says the twin *was* written |
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

All registered in `_DISPATCH` (~line 1447 in tools.py) and
`_TRACE_TOGGLE` (~line 1475). The tool-call XML parser
(`parse_tool_calls`) handles arbitrary tool names — extra inner tags
(beyond `<path>`, `<content>`, `<command>`, `<url>`) end up in
`ToolCall.extra` so new tools don't need parser changes.

Tool documentation that the agent reads is in
[enough/prompt.py](../enough/prompt.py) under `TOOL_INSTRUCTIONS`.
Every new tool needs an example block + prose explanation there.

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
  `by:<slug>` attribution (`user`, `agent`, or a role name).
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
  writes `.girraph` content. The agent's five tools (`tools.py`) and
  the UI's `/api/girraph*` endpoints (`server.py`) both call its
  node-level ops under `girraph.path_lock()` — that's the concurrency
  story (last-write-wins at node granularity) for simultaneous
  user-panel and agent edits.
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
Python module for the *format* — the source is plain text the agent
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
shows a live count and warns past it but doesn't block; agent-authored
diagrams should stay well under it (leave room for user edits).

Architecture notes:

- **Two modalities, in the frontmatter.** `modality: wip` is a working
  whiteboard — node *label* text is user-editable in merirmaid mode (with a
  live char count vs the soft `node-char-limit`); structure edits are
  agent-only, via the chat pill. `modality: mirror` is a source-of-truth
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
readable by the agent, annotatable with comments, and refreshable
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
  installs manager in the 🚰 modal. The agent's `wiki_status` reports
  install availability and tells the agent to *suggest* the modal —
  there is intentionally no agent tool for switching, forgetting, or
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
  archive download. There is deliberately **no agent tool** that swaps a base
  archive; the agent's `wikisink` run only *reports* that a newer snapshot
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
  exists only as the agent-facing text pipeline
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
  backend mutation. **Both the agent's `write_file` and `POST /api/file`
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
  composes an agent chat request, and per-file open into the natural mode
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
door is `skillaudit.set_skill_enabled_guarded()`. There is **no agent tool
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
anywhere else are untrusted — including a `SKILL.md` the agent wrote
itself, which is intended (the agent audits its own output). Both the
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
synthetic agent turn: it assembles analyzer's `references/audit.md`
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
  `enough/static/help-docs.md` — one `## <id>` section per bubble, with
  `name:` / `path:` lines under the heading and `### what` / `### how` /
  `### ideas` bodies (inline HTML allowed; rendered through the existing
  `renderMarkdown()`). The tokens `{{skills-list}}` / `{{roles-list}}` /
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

## Tasks you might be asked to do

### Add a new skill

1. Create `defaults/skills/<name>/SKILL.md` with YAML frontmatter
   (`name`, `description`). Optionally add `references/`, `scripts/`,
   `assets/` subfolders.
2. `description:` **must be a single line.** `prompt._parse_paradigm_frontmatter`
   splits on the first `:`, so a YAML folded block (`description: >`)
   silently degrades to the string `">"` and the agent never learns when to
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
into a project's `rness/skills/` by hand, or written there by the agent
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
   proactively" (the `default` paradigm's prompt tells the agent when
   to switch).
3. Document the activation rule in the paradigm itself — when to switch
   in, when to switch out, what skill (if any) it pairs with.
4. No code changes; paradigm catalog is read from `rness/paradigms/`
   directly.

### Add a new role

1. Create `defaults/roles/<name>/AGENT.md` and `MOTIVATION.md`.
2. `skeleton.py` symlinks the directory on next launch / update.
3. User toggles in the sidebar.

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
~18,700-line file with inline CSS and JS. Conventions:

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
    (`readedit`, `girraph`, `merirmaid`, `wikisink`, `cacheawl`, `ref`).
  - `modeRemove(name)` — splice at any depth, re-apply z-order, re-render
    indicators. Empty stack = the chat home.
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
    the top square is inert.
  - **Esc** targets `modeTop()` only, guarded so it doesn't fire while
    the confirm overlay is up, while a chat composer / search / inline
    edit field is focused, or while ANY modal is open (`_escModalOpen` —
    modals own esc for themselves).
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
  only by design: no edit face, no highlighting, no chat pill. The
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
user-confirmed in the UI — the agent gets read/search/update-run tools
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
  time; roles are individually toggleable.** Three different
  on/off patterns for three concepts — don't conflate them.
- **`prompt.set_skill_enabled()` is not the door for a skill toggle.**
  It's the raw `.disabled` writer. Every toggle-on must go through
  `skillaudit.set_skill_enabled_guarded()`, which can raise
  `SkillAuditRefused` or return `needs_audit`. If you add a second route
  that enables a skill (a new endpoint, a tool runner, a migration), route
  it through the guard or you've reopened the hole
  `quarantine_untrusted()` exists to close. Roles have no equivalent —
  only skills are audited.
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
  `ENOUGH_MODELS_REGISTRY`, `ENOUGH_PROJECTS_STATE`
  (plus `ENOUGH_MODELS_URL_BASE`, which rebases the model download URLs
  onto a local stub server, keyed by local gguf_filename) — all
  pointed at `tmp_path`; **never run against real `~/enough` state.**
  `ENOUGH_PROJECTS_STATE` is the one that is **autouse for the whole suite**
  (`tests/conftest.py`): half the suite calls `ensure_skeleton()`, which now
  registers, so without it a test run would file the developer's tmp dirs on
  their real home screen. That seam has to be closed by default, not by
  remembering — and note it is also read by the **Rust shell**
  (`config::enough_config_dir()`), which is where the `.home-open` handoff
  lands. The
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
3. Symlinks `_SKELETON_PLAN` entries (policies, AGENT/MOTIVATION,
   `knowledge/rosetta-primers`) from `~/enough/defaults/...` on
   first-time `rness/` creation
4. Runs three populators on **every** launch — `_populate_skill_symlinks`,
   `_populate_role_symlinks`, `_populate_paradigm_symlinks` — so newly
   shipped skills/roles/paradigms appear in existing projects without
   the user running `/update-enough`. Each populator globs
   `~/enough/defaults/<kind>/`, symlinks anything new, prunes dangling
   symlinks left over from removed globals. Skills/roles default-off
   (added to `.disabled`); paradigms have no off concept — exactly one
   is active at a time.
5. Creates `_EMPTY_DIRS` (requests, session-logs, io, etc.) as needed
6. Runs migrations for older project layouts

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
3. **One folder, one agent.** No multi-agent orchestration; no shared
   state across projects. Different folder → different agent →
   different memory. This is a discipline, not a limitation. Users
   running multiple `enough` instances coordinate through the
   filesystem (e.g. a shared cachebox in `~/enough/cacheawl/`).

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
and the throttled wikisink newer-snapshot check) — **tracked since the
seven-models round**, so a fresh clone has it. Before declaring anything
done:

```bash
uv run pytest -q                        # 422 tests (+12 docling skips)
uv run python scripts/smoke_boot.py     # real boot, scratch dir
bash tests/bootstrap_linux_harness.sh   # only if you touched bootstrap.sh
```

Rust, if you touched the shell: `cargo test` in `desktop/src-tauri/`
(37 tests — the launch routing and the exit-42 handshake are pure functions
precisely so they're covered here).

CI runs exactly those three on ubuntu-latest and macos-latest. Anything
not covered by them is smoke-tested via ad-hoc Python scripts that
exercise the modules directly (sometimes via FastAPI's TestClient against
`create_app()`) — examples are in git history under recent commits
touching `cloud.py`, `tools.py`, and `server.py`.

---

## License

Apache 2.0. See [LICENSE](../LICENSE).

Third-party content (the bundled `defaults/skills/` packages) carries
its own licenses — see [THIRD_PARTY_LICENSES.md](../THIRD_PARTY_LICENSES.md).
