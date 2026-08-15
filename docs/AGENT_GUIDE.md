# enough — Agent Guide (v0.2.0)

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
editing markdown files. A fifth optional model slot routes through
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
| `~/enough/config/` | User-global JSON config. `broker.json` (toggle states), `models.json` (active local model), `openrouter.json` (cloud-slot metadata, **no api key**), `ui.json` (theme/font), `orchestrator.json` (auto-reset config), `wikisink.json` (wikisink install registry + watch/override registries + reading state), `desktop.json` (desktop-shell launch prefs: reopen toggle, last/known projects, onboarding state — shared-visible with the CLI, written by `desktop/src-tauri/src/config.rs`). | Edit per-machine settings. |
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
| [enough/server.py](../enough/server.py) | ~3300 | FastAPI app: chat dispatch, SSE streaming, file tree, model modal, broker modal, auto-reset orchestration, all `/api/*` endpoints (including `/api/wiki/*`, `/api/models/*`, and the desktop-gated `POST /api/shutdown` — see the `ENOUGH_DESKTOP*` note under "What NOT to touch"). | `create_app()`, `_drive_message()`, `request_process_exit()` (module-level so tests can swap it), all `@app.{get,post}` handlers |
| [enough/prompt.py](../enough/prompt.py) | ~890 | Assembles the system prompt from `rness/` on every turn (no caching). Also owns skill/role/paradigm enumeration + toggle-state helpers. | `assemble_system_prompt()`, `TOOL_INSTRUCTIONS`, `list_skills()` / `set_skill_enabled()`, `list_roles()` / `set_role_enabled()`, `list_paradigms()`, `get_active_paradigm()` / `set_active_paradigm()` |
| [enough/broker.py](../enough/broker.py) | ~380 | Broker config (toggles), trace journal writer, canned denial messages. New toggles auto-render in the broker pane via `/api/broker`. | `TOGGLES` tuple, `load_config()`, `is_enabled()`, `trace()`, `denial_*()` |
| [enough/tools.py](../enough/tools.py) | ~1360 | Tool runners (`read_file`, `write_file`, `shell`, `fetch_url`, `read_highlights`, `navigate_to_highlight`, `cloud_pipeline`, girraph ops, wiki tool wrappers), the tool-call XML parser, the dispatch table. | `_DISPATCH`, `_TRACE_TOGGLE`, `execute()`, `parse_tool_calls()`, `_CLOUD_KEY_EXFIL_PATTERNS` |
| [enough/wikisink/](../enough/wikisink/) | ~2500 (pkg) | Local offline Wikipedia. `config.py` (install registry, schema v2 multi-install, data paths), `zim.py` (libzim reader, search, sanitize/rewrite), `download.py` (Kiwix flavor listing + resumable downloads), `overlay.py` (live-refreshed + preserved article stores), `comments.py` (per-article threads), `save.py` (save/read/unsave article folders + the clean HTML→markdown text pipeline), `update.py` (the "wikisink" update run), `rankings.py` (pageview snapshots), `report.py` (run report), `agent.py` (the four agent tool runners). | `config.load_config()` / `installs()` / `active_install()` / `unavailable_reason()`, `zim.get_article()` / `search()`, `download.DownloadManager`, `update.run_wikisink()` |
| [enough/cloud.py](../enough/cloud.py) | ~1000 | OpenRouter integration: keyring read/write, in-memory key cache, OpenAI-compatible streaming + non-streaming clients, health check, response caching to `rness/io/cloud-cache/`, the broker-driven `pipeline_run()`. | `set_api_key()` / `clear_api_key()` / `has_api_key()`, `_get_api_key_for_broker()`, `health_check()`, `chat_completion()`, `stream_chat_completion()`, `cache_completion()`, `pipeline_run()` |
| [enough/llm.py](../enough/llm.py) | ~125 | OpenAI-compatible client for the local llama-server. Streaming-only path for chat. | `stream_chat()`, `check_llm_reachable()` |
| [enough/supervisor.py](../enough/supervisor.py) | ~400 | Manages the local llama-server subprocess. Adopts an existing process if one's already up; spawns its own otherwise. Skips spawning entirely when the active model is `opro-api`. | `LlamaSupervisor`, `_resolve_startup_choice()` |
| [enough/models.py](../enough/models.py) | ~550 | Local-model registry (7 cute-named local models, defined in `defaults/models.json`; two carry separate MTP draft GGUFs, two carry a `llama_cpp_min_release` gate). Feasibility verdicts (RAM + free disk), `install-menu` CLI for bootstrap.sh. Selection state in `~/enough/config/models.json`. | `load_registry()`, `load_state()`, `save_state()`, `resolve()`, `all_models_view()`, `feasibility()`, `release_gate()`, `install_menu_rows()` |
| [enough/model_download.py](../enough/model_download.py) | ~330 | Resumable GGUF downloads for the in-app model manager: main file then optional MTP draft, ranged-GET resume off a `.part`, one active download per process, cancel-keeps-partial, delete. Backs `/api/models/{download,delete}/*`; progress on the `model-dl` SSE event. | `ModelDownloadManager` (`start` / `cancel` / `delete` / `state`), `pending_phases()`, `partials()` |
| [enough/skeleton.py](../enough/skeleton.py) | ~560 | Creates `rness/` for new projects (copies from `defaults/`), syncs global skills/roles/paradigms on every launch via dedicated populators, runs migrations. | `ensure_skeleton()`, `_SKELETON_PLAN`, `_PROJECT_LOCAL_FILES`, `_EMPTY_DIRS`, `_populate_skill_symlinks` / `_populate_role_symlinks` / `_populate_paradigm_symlinks` |
| [enough/highlights.py](../enough/highlights.py) | ~250 | Review-mode color highlights (yellow/green/blue/pink) stored in per-doc `.<filename>.highlights.json` sidecars. Tools `read_highlights` and `navigate_to_highlight` consume them. | — |
| [enough/girraph.py](../enough/girraph.py) | ~695 | The girraph primitive: parser/serializer for the plain-text `.girraph` IBIS format, node-level ops (the only way content changes), ASCII tree renderer, per-path write locks. Agent tools and UI endpoints both call through here. | `loads()` / `dumps()`, `add_node()` / `update_node()` / `link_nodes()` / `remove_node()`, `ascii_render()`, `path_lock()` |
| [enough/cacheawl.py](../enough/cacheawl.py) | ~1340 | The cacheawl store: cachebox CRUD, path/URL/wikisink **ingest**, the `_cachebox.merirmaid` mirror generator + reconcile, the mirror/sidecar write-guards, transfer (copy/move), and the launch-time `infoworld` migration. Root is `~/enough/cacheawl/` (or `ENOUGH_CACHEAWL_ROOT`). Owns everything under the store; nothing else writes there. | `root()`, `create_cachebox()` / `list_cacheboxes()` / `cachebox_tree()`, `run_ingest()`, `regenerate_mirror()` / `reconcile()` / `reconcile_all()`, `mirror_write_denial()`, `migrate_infoworld()` |
| [enough/logger.py](../enough/logger.py) | small | Stdlib logging setup. | — |
| [enough/static/index.html](../enough/static/index.html) | ~14800 | The entire frontend — HTML, CSS, vanilla JS, htmx. Single file. | model modal, broker modal, OPRO-API wizard + settings, file tree (+ option-click context menu), chat pane, SSE consumer, wikisink setup/installs modal + reader mode, the unified read/edit mode (mini ↔ full frame), girraph mode, merirmaid mode, cacheawl split-view mode, SVG icon pipeline (`data-icon`/`iconSrc`), `setActiveMode` registry, confirmOverlay |

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
| [desktop/src-tauri/src/main.rs](../desktop/src-tauri/src/main.rs) | window, native menu (Settings `CheckMenuItem` + Edit submenu), both quit paths, signal traps |
| [desktop/src-tauri/src/launch.rs](../desktop/src-tauri/src/launch.rs) | the launch flow: reopen-or-pick, `known_projects` MRU upkeep |
| [desktop/src-tauri/src/backend.rs](../desktop/src-tauri/src/backend.rs) | spawn / health-probe / stop the uvicorn child (`POST /api/shutdown` → SIGTERM → SIGKILL ladder; child in its own process group) |
| [desktop/src-tauri/src/config.rs](../desktop/src-tauri/src/config.rs) | `~/enough/config/desktop.json` — tmp+rename writes, unknown-key round-trip |
| [desktop/src-tauri/src/guards.rs](../desktop/src-tauri/src/guards.rs) | pre-flight refusals. **Deliberately mirrors** `enough/skeleton.py`'s `cloud_sync_provider` path list and the `~/enough` refusal in `enough/__main__.py` — touch one, touch the other (unit tests pin the list) |
| [desktop/src-tauri/src/http.rs](../desktop/src-tauri/src/http.rs) | ~60-line loopback-only HTTP/1.1 client (no client crate) |
| [desktop/src-tauri/src/bundled.rs](../desktop/src-tauri/src/bundled.rs) | where the bundle's payload lives (uv sidecar, llama.cpp, source snapshot), derived from `current_exe()` |
| [desktop/src-tauri/src/onboarding.rs](../desktop/src-tauri/src/onboarding.rs) | the first-run wizard's six IPC commands + the launch thread's wait loop |
| [desktop/src-tauri/build.rs](../desktop/src-tauri/build.rs) | stages the source snapshot (pyproject, uv.lock, `enough/`, `defaults/`, licenses) into the bundle on every `cargo build` |
| [desktop/ui/loading.html](../desktop/ui/loading.html) | the shell's only page; static, zero Tauri IPC exposed to the enough UI |
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
| Skills | `rness/skills/<name>/SKILL.md` (symlink) | `defaults/skills/<name>/SKILL.md` | the toggled-on ones, yes |
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

**Active vs available**: skills and roles ship as files but only become
part of the system prompt when toggled on in the sidebar. The
*disabled* set is persisted per-project as a plain newline-delimited
text file: `rness/skills/.disabled` and `rness/roles/.disabled`. Read/
written via `prompt._read_disabled_skills()` / `set_skill_enabled()` (and
the role-side equivalents). New globals appear in every project with
their name added to `.disabled` on first sync — i.e. defaulted off.
Paradigms are different — exactly one is active, named in
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
| `fetch_url_cache_and_convert` | fetch_url | Pandoc HTML→markdown + cache in `rness/io/input/` |
| `wikisink_enabled` | wikisink | Whether the agent's four wiki tools work at all (the 🚰 browser UI is ungated) |
| `wikisink_live_updates` | wikisink | Whether wikisink update runs may call the Wikipedia/Wikimedia APIs (off = report from local state only) |
| `cacheawl_enabled` | cacheawl | Whether the agent's three cachebox tools work at all (the cacheawl browser UI is ungated; URL ingests still additionally honor the `fetch_url_*` toggles) |

---

## Tools

| Tool | Runner | Gating |
|---|---|---|
| `read_file` | `tools.run_read_file` | path under project OR on file-read allowlist |
| `write_file` | `tools.run_write_file` | path under project OR on file-rw allowlist; not in `rness/requests/done/` |
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
User-facing explainer: [docs/HELP_CENTER.md](HELP_CENTER.md) §15.

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
  run).
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

## The help system

Three layers, all markdown (design formerly in docs/help-system-plan.md):

- **`(?)` bubbles.** Content lives in one combined file,
  `enough/static/help-docs.md` — one `## <id>` section per bubble, with
  `name:` / `path:` lines under the heading and `### what` / `### how` /
  `### ideas` bodies (inline HTML allowed; rendered through the existing
  `renderMarkdown()`). The tokens `{{skills-list}}` / `{{roles-list}}` /
  `{{paradigms-list}}` expand client-side into the *actually installed*
  set via `GET /api/help/defaults` (name + description from frontmatter)
  — never hand-maintain those lists in prose. Bubbles are governed by
  one per-project boolean (`GET`/`POST /api/help/bubbles`, stored in the
  multipurpose `rness/active-paradigm` file, default on, surfaced as the
  "help (?) bubbles" checkbox in the UI modal): on = every `[data-help]`
  row shows its `(?)` persistently (re-applied after `htmx:afterSettle`),
  off = none. There are no hover timers and no first-launch highlight
  machinery — that design was superseded.
- **The manual.** `docs/HELP_CENTER.md` is the complete end-user manual
  (voice-matched to the project; edit it like documentation, verify
  claims against the code first). `GET /api/help-center` serves it raw;
  the **reference mode** (`#ref-mode`, the `hxc` button at the top of
  the UI modal) renders it read-only in-app. See the mode-stack notes
  under "Change the UI".
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
2. The user runs `/update-enough` in their chat (or restarts enough) and
   the symlink lands in every project's `rness/skills/`.
3. The skill is **off by default** — user toggles it in the sidebar.
   No other code changes needed.

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

### Change the UI

[enough/static/index.html](../enough/static/index.html) is a single
~14800-line file with inline CSS and JS. Conventions:

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
  registry/feasibility/downloads, and the desktop shutdown gate. Suites
  isolate global state via env hooks — `ENOUGH_WIKISINK_CONFIG`,
  `ENOUGH_CACHEAWL_ROOT`, `ENOUGH_INFOWORLD_ROOT`, `ENOUGH_UI_CONFIG`,
  `ENOUGH_WEIGHTS_DIR`, `ENOUGH_LIVE_STATE`, `ENOUGH_MODELS_REGISTRY`
  (plus `ENOUGH_MODELS_URL_BASE`, which rebases the model download URLs
  onto a local stub server, keyed by local gguf_filename) — all
  pointed at `tmp_path`; **never run against real `~/enough` state.** The
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
```

Dependencies of note (Python, via `uv sync`):
- `fastapi`, `uvicorn[standard]`, `sse-starlette` — the web layer
- `httpx[socks]` — outbound HTTP, with SOCKS support for Tor routing
- `keyring>=24` — OS keyring for the OpenRouter api key
- `ctranslate2`, `sentencepiece`, `huggingface_hub` — translator skill

Plus external binaries installed by `bootstrap.sh` via Homebrew:
- `llama.cpp` — local LLM inference server (backs everything except OPRO-API)
- `whisper-cpp` — local speech-to-text for the chat mic button
- `tor` — anonymized off-allowlist web fetch via the broker
- `pandoc` — HTML → markdown conversion for fetched documents
- `harper` — local grammar/spell checker (Automattic, Apache-2.0).
  The analyzer skill's proofread mode shells out to `harper-cli`
  for the silent-fix pass; absence is handled gracefully (skill falls
  back to LLM-only scanning).

Plus, on Linux, the same roles filled differently (see "Platforms, and
CI"): llama.cpp is a checksum-pinned prebuilt release in `~/enough/bin/`
rather than a formula; pandoc and tor come from apt/dnf; whisper.cpp and
harper have no distro package and are built from their own repos.
`bootstrap.sh` prints those commands and installs none of them.

A pytest suite lives in `tests/` (girraphs, project metadata, the cacheawl
store + endpoints + `cacheawl:` scheme, the ui-config theme-key merge, the
models registry/feasibility/downloads, the llama-server lookup, the desktop
shutdown gate, the platform seams) — **tracked since the seven-models
round**, so a fresh clone has it. Before declaring anything done:

```bash
uv run pytest -q                        # 231 tests
uv run python scripts/smoke_boot.py     # real boot, scratch dir
bash tests/bootstrap_linux_harness.sh   # only if you touched bootstrap.sh
```

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
