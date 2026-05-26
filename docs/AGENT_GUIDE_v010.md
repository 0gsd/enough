# enough — Agent Guide (v0.1.0)

> **Audience:** another LLM agent (e.g. a Claude Code session) helping a
> human modify their local `enough` install. Not for end-users — for an
> end-user-facing intro see the [README](../README.md). This doc is dense,
> file-path-heavy, and assumes you can read Python and call tools.

`enough` is a paradigmless personal computer harness powered by a local
LLM. It runs on the user's machine, exposes a chat UI at
`http://127.0.0.1:3456`, and lets the user shape the agent's behavior by
editing markdown files. A fifth optional model slot routes through
OpenRouter when the user has explicitly enabled it; everything else stays
local.

This guide tells you what files are involved in what, how the runtime
flows, what to edit when the user asks you to do common things, and the
patterns that will trip you up if you don't see them coming.

---

## Layout on disk

Three locations that matter:

| Path | What it is | Authority |
|---|---|---|
| `~/enough/` | The global install. Cloned from the repo by `bootstrap.sh`. Contains `defaults/` (templates that get copied / symlinked into every project), `infoworld/` (shared knowledge library), and the Python source. | Edit these to affect every project. |
| `~/enough/config/` | User-global JSON config. `broker.json` (toggle states), `models.json` (active local model), `openrouter.json` (cloud-slot metadata, **no api key**), `ui.json` (theme/font), `orchestrator.json` (auto-reset config). | Edit per-machine settings. |
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
| [enough/server.py](../enough/server.py) | ~2080 | FastAPI app: chat dispatch, SSE streaming, file tree, model modal, broker modal, auto-reset orchestration, all `/api/*` endpoints. | `create_app()`, `_drive_message()`, all `@app.{get,post}` handlers |
| [enough/prompt.py](../enough/prompt.py) | ~750 | Assembles the system prompt from `rness/` on every turn (no caching). Also owns skill/role/paradigm enumeration + toggle-state helpers. | `assemble_system_prompt()`, `TOOL_INSTRUCTIONS`, `list_skills()` / `set_skill_enabled()`, `list_roles()` / `set_role_enabled()`, `list_paradigms()`, `get_active_paradigm()` / `set_active_paradigm()` |
| [enough/broker.py](../enough/broker.py) | ~340 | Broker config (toggles), trace journal writer, canned denial messages. New toggles auto-render in the broker pane via `/api/broker`. | `TOGGLES` tuple, `load_config()`, `is_enabled()`, `trace()`, `denial_*()` |
| [enough/tools.py](../enough/tools.py) | ~1100 | Tool runners (`read_file`, `write_file`, `shell`, `fetch_url`, `read_highlights`, `navigate_to_highlight`, `cloud_pipeline`), the tool-call XML parser, the dispatch table. | `_DISPATCH`, `_TRACE_TOGGLE`, `execute()`, `parse_tool_calls()`, `_CLOUD_KEY_EXFIL_PATTERNS` |
| [enough/cloud.py](../enough/cloud.py) | ~1000 | OpenRouter integration: keyring read/write, in-memory key cache, OpenAI-compatible streaming + non-streaming clients, health check, response caching to `rness/io/cloud-cache/`, the broker-driven `pipeline_run()`. | `set_api_key()` / `clear_api_key()` / `has_api_key()`, `_get_api_key_for_broker()`, `health_check()`, `chat_completion()`, `stream_chat_completion()`, `cache_completion()`, `pipeline_run()` |
| [enough/llm.py](../enough/llm.py) | ~125 | OpenAI-compatible client for the local llama-server. Streaming-only path for chat. | `stream_chat()`, `check_llm_reachable()` |
| [enough/supervisor.py](../enough/supervisor.py) | ~400 | Manages the local llama-server subprocess. Adopts an existing process if one's already up; spawns its own otherwise. Skips spawning entirely when the active model is `opro-api`. | `LlamaSupervisor`, `_resolve_startup_choice()` |
| [enough/models.py](../enough/models.py) | ~280 | Local-model registry (4 cute-named local models, defined in `defaults/models.json`). Selection state in `~/enough/config/models.json`. | `load_registry()`, `load_state()`, `save_state()`, `resolve()`, `all_models_view()` |
| [enough/skeleton.py](../enough/skeleton.py) | ~560 | Creates `rness/` for new projects (copies from `defaults/`), syncs global skills/roles/paradigms on every launch via dedicated populators, runs migrations. | `ensure_skeleton()`, `_SKELETON_PLAN`, `_PROJECT_LOCAL_FILES`, `_EMPTY_DIRS`, `_populate_skill_symlinks` / `_populate_role_symlinks` / `_populate_paradigm_symlinks` |
| [enough/highlights.py](../enough/highlights.py) | ~250 | Review-mode color highlights (yellow/green/blue/pink) stored in per-doc `.<filename>.highlights.json` sidecars. Tools `read_highlights` and `navigate_to_highlight` consume them. | — |
| [enough/logger.py](../enough/logger.py) | small | Stdlib logging setup. | — |
| [enough/static/index.html](../enough/static/index.html) | ~8000 | The entire frontend — HTML, CSS, vanilla JS, htmx. Single file. | model modal, broker modal, OPRO-API wizard + settings, file tree (+ option-click context menu), chat pane, SSE consumer |

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
| Active paradigm | `rness/active-paradigm` (one line, just the name) | seeded with `"default\n"` | yes — full file inlined |
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

### Local models (the four llama.cpp slots)

Registry template at [defaults/models.json](../defaults/models.json) —
ships 4 entries (cute names like `g40-04`, `q35-09`, `g40-26`, `q36-27`).
Each entry: `cute_name`, `label`, `family`, `gguf_filename`, `gguf_url`,
`disk_gb_approx`, `ram_gb_recommended_min`, `ctx_max`, `ctx_defaults`
(a RAM-tier → context-window map).

Live state at `~/enough/config/models.json`: just `{"current": "<cute>"}`
plus optional `ctx_overrides`.

`enough.models.resolve(cute)` merges the registry + live state +
filesystem (does the .gguf exist?) into a complete view. `all_models_view()`
returns the full list, used by `/api/models`.

To **add a new local model**: append an entry to
[defaults/models.json](../defaults/models.json). It shows up in the model
modal on next page load; the supervisor will spawn llama-server with it
when the user selects it.

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

The current toggle catalog (8 toggles, all default `True`):

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

All registered in `_DISPATCH` (~line 1026 in tools.py) and
`_TRACE_TOGGLE` (~line 1042). The tool-call XML parser
(`parse_tool_calls`) handles arbitrary tool names — extra inner tags
(beyond `<path>`, `<content>`, `<command>`, `<url>`) end up in
`ToolCall.extra` so new tools don't need parser changes.

Tool documentation that the agent reads is in
[enough/prompt.py](../enough/prompt.py) under `TOOL_INSTRUCTIONS`.
Every new tool needs an example block + prose explanation there.

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
2. Register in `_DISPATCH` (~line 1026 in tools.py) and `_TRACE_TOGGLE`
   (~line 1042). Both grep cleanly by name if line numbers drift again.
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
~8000-line file with inline CSS and JS. Conventions:

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

---

## What NOT to touch / surprising patterns

A list of things that will confuse you if you don't see them coming:

- **The active-paradigm file is one line.** `rness/active-paradigm`
  contains exactly the paradigm name (e.g. `text-planning\n`). It is
  read/written via `prompt.get_active_paradigm()` /
  `prompt.set_active_paradigm()`. Don't add YAML or extra metadata.
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
- **There's no automated test suite.** Smoke tests are written
  ad-hoc as Python scripts that exercise the imports + a TestClient
  against `create_app()`. See git history for examples.

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
   filesystem (e.g. shared `infoworld/`).

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

No automated test suite yet. Smoke tests are written as Python scripts
that exercise the modules directly (sometimes via FastAPI's TestClient
against `create_app()`). When making changes, run the relevant smoke
flow before declaring done — examples are in git history under recent
commits touching `cloud.py`, `tools.py`, and `server.py`.

---

## License

Apache 2.0. See [LICENSE](../LICENSE).

Third-party content (the bundled `defaults/skills/` packages) carries
its own licenses — see [THIRD_PARTY_LICENSES.md](../THIRD_PARTY_LICENSES.md).
