# enough — Agent Guide (v0.6.0)

> **Audience:** another LLM agent (e.g. a Claude Code session) helping a
> human modify their local `enough` install. Not for end-users — for an
> end-user-facing intro see the [README](../README.md), and for the full
> user manual see [docs/HELP_CENTER.md](HELP_CENTER.md) (read in-app
> in the docs viewer, `#docs-mode`, as a DocOES volume — 0.4.4). This doc is dense,
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
local, and a message beginning **`/pal`** spends that slot once, by hand,
from an otherwise local turn (0.4.0 — see "`/pal`" under OPRO-API). A
**council** — several readvisors and the user speaking in turn on one
canvas — concludes into an answer, a document or **a whole new composure**
(0.4.0; see "Councils"). An optional **wikisink** subsystem puts an offline
copy of Wikipedia on the machine (see its own section below and
[docs/WIKISINK.md](WIKISINK.md)). **FEED**, the first-party enough english
dictionary (0.4.1), ships as text in `reflib/dict/`, is built into a local
SQLite file on first launch, and is read in its own full-frame mode, in a
word lightbox, and from a right-click on any word (see "The dictionary
(FEED)"). **Canon** (0.4.3; *Cacheawl* until then) is the machine-global
library at `~/enough/canon/` and its two-pane file manager; every volume of
it, and every project, carries a `canon.cosm` catalog written in
**MacroCOSM OES**, the `.cosm` grammar whose reader is `enough/macrocosm.py`
and whose spec ships as [docs/MACROCOSM_OES.md](MACROCOSM_OES.md). MacroCOSM
has a **core** — five built-in formats (`cosm`, `canon`, `fabula`, `doc`,
`thym`) and the dialectic — and two **MiniCOSMs**, Comprise and Ascribe. Any
text can be **decompiled** — on request, never automatically — into its
**fabula** (a twin beside it, `close.md.fabulan.cosm`, prose or verse),
compiled back into a **short** (an entailment of the fabula), and reduced to
an **atem**; in the 0.6 round a small
folder of Python is decompiled into a **fabulac** and compiled back into a
**cshort** and its **catems** (see "Canon", "MacroCOSM", "The fabula" and
"Building a fabulac"). Any volume may carry the **dialectic**'s questions,
which a person answers and a second step settles (see "The dialectic").
**Thym** (0.5.0; `thym 1` in the 0.6 round) is the transcognition language
that connects the OESes: a `.thym` program composes moves (derive, entail,
measure, package, project, edit, survey, question…), is compiled into a
plan a person can read, and runs with model-backed moves behind contracts,
on a model route chosen per run, leaving a trace that replays; a text
leaves as a **package** and is read again as a labelled **reading** (see
"Thym"). Its spec ships as [docs/THYM.md](THYM.md), and a person's
holograph is the second MiniCOSM, Ascribe ([docs/ASCRIBE.md](ASCRIBE.md);
see "Ascribe's module"). New projects start in the **text-planning**
paradigm, which absorbed the retired `default` (see "Add a new paradigm").

This guide tells you what files are involved in what, how the runtime
flows, what to edit when the user asks you to do common things, and the
patterns that will trip you up if you don't see them coming.

---

## Layout on disk

Three locations that matter:

| Path | What it is | Authority |
|---|---|---|
| `~/enough/` | The global install. Cloned from the repo by `bootstrap.sh`. Contains `defaults/` (templates that get copied / symlinked into every project), `canon/` (the machine-global library — see below), `readvisors/` (the user's own readvisors — see the row below), and the Python source. (The old `infoworld/` library was dissolved into the store on first 0.1.6 launch; the store itself was `cacheawl/` until 0.4.3.) | Edit these to affect every project. |
| `~/enough/config/` | User-global JSON config. `broker.json` (toggle states), `models.json` (active local model), `openrouter.json` (cloud-slot metadata, **no api key**), `allographs.json` (toward 0.7: what this machine keeps of each listed holograph, by hid: registry, tag, name, dangler, the listed run and the holograph's state it took; **no key, no token**, which live in the keychain), `ui.json` (theme/font/`ui_language`/**`chief_readvisor_name`** — the chief readvisor's name is one per machine, like the theme), `orchestrator.json` (auto-reset config), `wikisink.json` (wikisink install registry + watch/override registries + reading state), `desktop.json` (desktop-shell launch prefs: reopen toggle, last/known projects, onboarding state — shared-visible with the CLI, written by `desktop/src-tauri/src/config.rs`), `extras.json` (which optional dependency groups are installed — read by Python, bash **and** Rust; see "Document conversion"), `projects.json` (the home screen's project registry — see "The home screen"), and the transient `.home-open` handoff file. | Edit per-machine settings. |
| `~/enough/readvisors/` | The **user-global** readvisors source (0.3.5), seam **`ENOUGH_READVISORS_ROOT`**, resolved by `skeleton.user_readvisors_root()`. **Never auto-created** — a machine that never forged a readvisor carries no empty folder. It exists because a desktop build's `defaults/` is sealed inside the `.app` and is not writable, so the `readvisory` skill's `install_readvisor` needs somewhere to put a global one. Each entry is `<name>/AGENT.md` + `MOTIVATION.md`, symlinked into every project by the populator. | Edit to affect every project on this machine, including .app installs. |
| `~/enough/wikisink/` | Default wikisink location: the user's wikisink *data* (comments, overlays, preserved articles, rankings, run state) and — unless pointed elsewhere — the base `.zim` archive(s). Archives can live anywhere, external drives included; several installs can be registered at once. Hidden from the file-manager tree. | Managed via the 🚰 UI; don't hand-edit. |
| `~/enough/canon/` | The machine-global **Canon** store (0.4.3; `~/enough/cacheawl/` before, renamed in place on first use — see "Canon"): root-level folders are *volumes* (plain kept-forever text, or cached replicas ingested from a path/URL/wikisink), each carrying a backend-owned `canon.cosm` catalog and a hidden `.canon.json`. Global wiki saves land in the `wiki/` volume; the dissolved infoworld folders became the `personal`/`public`/`wiki` volumes. Seam **`ENOUGH_CANON_ROOT`** (the legacy `ENOUGH_CACHEAWL_ROOT` fallback was removed in 0.6). Hidden from every project's file tree. | Managed via Canon mode + the readvisors' `canon_*` tools; `canon.cosm` and `.canon.json` are backend-owned. |
| `~/enough/dict/` | FEED's state root (0.4.1), seam **`ENOUGH_DICT_ROOT`**: `feed.sqlite`, the official dictionary — **built** from the shipped `reflib/dict/` and disposable (rebuilt whenever the manifest digest moves) — and `user-dictionary.sqlite`, the user's own entries — **precious**: created on the first write, never rebuilt or deleted by code. Install-wide, not per project. See "The dictionary (FEED)". | `feed.sqlite` is the build's; the user DB changes only through the `dict_*` tools and `DELETE /api/dict/user/{word}`. Don't hand-edit either. |
| `~/enough/docoes/` | DocOES's built doc volumes (0.4.4), seam **`ENOUGH_DOCS_ROOT`**: one `<doc>.<lang>.doc.cosm` per telling — `macrocosm-oes.en` (the spec with the reference generated from the manifests), `thym.en`, `ascribe.en` and `comprise-oes.en` (the four OES specifications, at edition 0.6.0: the bundled editions, or the copies synced from cosmoes.org) and `help-center.<lang>` ×6 (the manual + its bubbles) — **built** by `enough/docoes.py` from the install's own markdown and manifests the first time a route or `doc_lookup` asks, and rebuilt whenever the source digest moves (like `feed.sqlite`). Disposable, never committed, never in a file tree. Install-wide. See "DocOES". | Only `docoes.build()` writes it (atomic `os.replace`). **Every DocOES CLI run and every scratch server exports the seam** — an unseamed `python -m enough.docoes lint …` builds into the real `~/enough/docoes/`. |
| `~/enough/thym/` | Thym's state root (0.5.0), seam **`ENOUGH_THYM_ROOT`** (read by `thym_host.host_root()` and `thym.trace.runs_dir`): `runs/<run-id>/` per run — `<run-id>.plan.cosm`, `<run-id>.trace.cosm`, `candidates/` (every coprocessor answer, `<node>[-<k>].<attempt>.cosm`, and every engine call, `<node>-e<k>.1.cosm`), `inputs/<name>.folder.cosm` (0.6: a snapshot of every `folder` input, taken when the run starts, so a replay needs no folder on disk), `stage/` while it runs, `outputs/<gives>.<ext>` (a `folder` output as `outputs/<name>/`) once every node has passed. **Never created by asking**: `GET /api/thym/runs` answers `[]` when it is absent; the first run makes it. Install-wide; records, not precious (a run is replayable from its folder). See "Thym". | Only the runtime writes it (`thym.run.run`, from `POST /api/thym/run`, `/api/canon/package`, `/api/canon/read`, `thym_run` and the CLI; since 0.6 also every stage of a fabulac build and compile, a fabula's settle and an isograph). **Every Thym CLI run and every scratch server exports the seam** — `python -m enough.thym run` without it writes into the real `~/enough/thym/`. |
| `~/enough/specs/` | The specifications synced from cosmoes.org (0.5.4), seam **`ENOUGH_SPECS_ROOT`** (`docoes.specs_root()`): the vendored client's folder — `<slug>/source.md` for `macrocosm-oes`, `thym`, `ascribe` and `comprise-oes`, `manifest.json` (the last manifest fetched, verbatim) and `state.json` (each document's name, edition, revised date, host and the source's sha256). Written only by the launch check (`enough/specs.py`: once per server start, a daemon thread, when the `specs_sync` preference is on and `ENOUGH_SPECS_SYNC` is not `0`); read by `docoes.spec_source()`, which uses a copy only while state.json's sha256 matches the file and (0.7) its edition is not older than the bundled one, and reads the bundled text otherwise. Never created by asking; disposable (the bundled texts are the floor). See "DocOES" → "The specifications from cosmoes.org". | Only the client writes it (temp file + `os.replace`, state.json last). **Every test and scratch rig exports the seam, `ENOUGH_SPECS_SYNC=0` and `ENOUGH_COSMOES_BASE` (a dead loopback port)** — nothing in the suite may reach cosmoes.org. |
| `<project>/rness/` | The per-project skeleton. Symlinks back into `~/enough/defaults/` for shipped paradigms/skills/policies/**readvisors** (and into `~/enough/readvisors/` for the user's own); per-project copies of `AGENT.md`, `MOTIVATION.md`, `active-paradigm`, `project.json`; per-project state in `io/`, `requests/`, `knowledge/`. Composure-round additions: **`rness/readvisors/`** (was `roles/`, migrated by `skeleton._migrate_roles_to_readvisors`), **`rness/io/composure/`** (where new `.comp` files land — in `_EMPTY_DIRS`, so it is back-filled on every launch), **`rness/composure-forms/`** (project forms; **not** in `_EMPTY_DIRS` — created on the first save-as-form) and **`rness/knowledge/councils/`** (exported council transcripts, created by `council.py` on the first conclude). 0.4.3 adds **`rness/canon.cosm`**, the project's catalog (backend-owned, write-refused, written lazily — see "Canon"). | Edit to affect just this project (never `rness/canon.cosm`). |
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
| [enough/server.py](../enough/server.py) | ~6710 | FastAPI app: chat dispatch, SSE streaming, file tree, model modal, broker modal, auto-reset orchestration, all `/api/*` endpoints (including `/api/wiki/*`, `/api/models/*`, `/api/skills*` — whose toggle is guarded by `skillaudit` — `/api/roles*` + `/api/readvisors/remove` + `/api/readvisor/chief`, `GET /api/pal/status`, the desktop-gated `POST /api/shutdown`, and `/api/home/*` + `/api/close-project`; see the `ENOUGH_DESKTOP*` note under "What NOT to touch"). Since 0.4.3 also Canon's store routes (`/api/canon/*`, registered by `_canon_route`; the pre-0.4.3 `/api/cacheawl/*` aliases were removed in 0.6), the derivation routes and their `CanonJobs` table, the MacroCOSM read routes (`/api/cosm*`, `/api/macrocosm/manifests`, `/api/macrocosm-spec`), the `canon:` path prefix (`STORE_PREFIXES`) and the project-catalog task in the lifespan. Mounts the composure, council and dictionary routers in one `include_router` call each, and starts FEED's background build in the lifespan (`dictionary.ensure_built(background=True)`; `cancel_build()` on shutdown). Owns `GET /api/intro` and the intro match in `POST /api/chat` (see "The readvisor panel"). Owns the `/pal` prefix branch in `POST /api/chat` and `_render_pal_bubbles`. Also owns the **mode boundary**: `create_app(home=…)`, the `ModeGate` ASGI middleware, `HOME_PATHS`/`HOME_PREFIXES`, and the `data-mode` marker templated into `/`. Since 0.4.4 the **agent-free boundary** too: `AgentFreeGate`, `AGENT_FREE_PATHS`/`AGENT_FREE_PREFIXES`/`AGENT_FREE_OPEN`, the switch in `POST /api/ui-config`, and `GET /api/canon/ingest-caps` (see "Agent-free mode"). Since 0.5.0 it mounts the Thym router (`thym_api.build_router(...)`, one `include_router`), asks `thym_api.thym_volume` first in `_cosm_volume` (so `/api/cosm` and `/api/cosm/lens` load `thym:` paths and `.thym` programs), serves `GET /api/thym-spec` (in `HOME_PATHS`), and gates `/api/canon/read` in `AGENT_FREE_PATHS` (see "Thym"). In the 0.6 round the derivation routes moved to `/api/fabula/derive|twin|compile` (the old `/api/canon/*` paths answer through 0.6, served by the new handlers from the loop over `retired_names.ROUTES`), each derivation job takes a `route` (`_body_route`, `_canon_mode(route)`, `_job_complete(route, source)`), and it mounts two more routers: `fabulac_job.build_router(...)` (`/api/fabula/build|resume|cancel|compile|compiled|cshort|catem`) and `dialectic_api.build_router(...)` (`/api/dialectic/*`, `POST /api/ascribe/isograph`, `POST /api/ascribe/allograph`); toward 0.7 also `allograph_api.build_router(...)` (Connect's sign-in, `POST /api/ascribe/subject`, `/api/allograph/*`), and hands the fabula tools a job starter (`_start_from_tool`; see "Building a fabulac" and "The dialectic"). | `create_app()`, `_drive_message()`, `_run_turn(session, message, pal=, log_user=)`, `_render_pal_bubbles()`, `Session.pal_turn`, `ModeGate`, `HOME_PATHS`, `HIDDEN_TREE_PATHS`, `STORE_PREFIXES`, `_canon_route()`, `_text_target()` (delegates to `canon_tools.text_target`), `_readvisor_origin()`, `request_process_exit()` / `request_process_exec()` (module-level so tests can swap them), `HANDOFF_EXIT_CODE`, all `@app.{get,post}` handlers |
| [enough/prompt.py](../enough/prompt.py) | ~2325 | Assembles the system prompt from `rness/` on every turn (no caching). Also owns skill/readvisor/paradigm enumeration + toggle-state helpers, the generated identity preface, the chief readvisor's name, and the gated tool-doc blocks. `set_skill_enabled()` is the dumb `.disabled` writer — the *guarded* door for skill toggles is `skillaudit.set_skill_enabled_guarded()` (see "Skill trust"). | `assemble_system_prompt(project_dir, readvisors=, profile=chat|council|lean, pal=)`, `assemble_for_window()` / `choose_profile()` / `lean_wanted()` / `estimate_tokens()` (0.5.1), `harness_guides()`, `harness_context()`, `readvisor_identity()`, `identity_preface()`, `chief_name()` / `valid_chief_name()` / `CHIEF_NAME_DEFAULT` / `CHIEF_NAME_MAX`, `readvisor_shape()`, `tool_instructions(project_dir, pal=, lean=)`, `TOOL_INSTRUCTIONS` (the core) / `GIRRAPH_` / `REVIEW_` / `WIKI_` (+ `WIKI_ABSENT_`, gate `_wiki_installed()`) / `CLOUD_` (gate `_cloud_usable()`) / `CANON_STORE_` / `KEEP_GOING_` / `COMPOSURE_TOOL_INSTRUCTIONS` / `READVISORY_TOOL_INSTRUCTIONS` / `DICTIONARY_TOOL_INSTRUCTIONS` / `CANON_TOOL_INSTRUCTIONS` (+ its gate `_macrocosm_available()`) / `FABULA_TOOL_INSTRUCTIONS` + `FABULA_ABSENT_INSTRUCTIONS` (0.6, by the `macrocosm-oes` skill) / `PAL_TOOL_INSTRUCTIONS` / `PAL_TURN_INSTRUCTION`, the `*_LEAN_INSTRUCTIONS` summaries, `LEAN_CUT` / `LEAN_SHARE` / `CHARS_PER_TOKEN`, `convert_instructions()`, `list_skills()` / `set_skill_enabled()`, `list_roles()` / `set_role_enabled()` / `_readvisors_dir()`, `list_paradigms()`, `get_active_paradigm()` / `set_active_paradigm()`, `HOME_PARADIGM` / `ensure_multipurpose_file()` (the `default` → home migration) |
| [enough/composure.py](../enough/composure.py) | ~3060 | The composure core (0.3.5): the `.comp` HTML5 parser/serializer, the sanitizer, markdown ⇄ rich text, the node-level op vocabulary (the only way content changes), `place_module`/`arrange`/`estimate_height`, the JSON document model the canvas renders from, the comments sidecar, the forms registry, the outline→composure converter, and the write-door denial. **No FastAPI import** — exercisable with no web layer. See "Composures". | `loads()` / `dumps()`, `model()`, `apply_ops()`, `path_lock()`, `OP_NAMES` / `SOURCES` / `MODULE_TYPES` / `BG_SWATCHES` / `SHIPPED_FORMS` / `CAPS`, `place_module()`, `estimate_height()`, `write_denial()`, `comments_path()` / `load_comments()` / `move_sidecars()`, `parse_outline()` / `outline_ops()` / `from_outline()`, `ComposureError` |
| [enough/composure_api.py](../enough/composure_api.py) | ~520 | HTTP translation only: `build_router(project_dir, resolve_path, emit)` → the `APIRouter` `create_app` mounts. Every `/api/composure*` route, the comments CRUD, `link-preview`, `webframe/refresh`, and the `composure` SSE event. | `build_router()`, `EVENT` |
| [enough/composure_tools.py](../enough/composure_tools.py) | ~490 | The nine readvisor composure tools; `register()` adds them to `tools._DISPATCH` / `_TRACE_TOGGLE` at `tools` import time. Gated by `composure_enabled`. | `TOOL_NAMES`, `register()`, `run_read_composure()` … `run_composure_from_outline()`, `CACHE_OVER_CHARS` |
| [enough/council.py](../enough/council.py) | ~1890 | The council engine (0.3.5, extended 0.4.0): the `composure:council` meta schema, participants + tints + charges, the rotation, the per-participant token budget and the mechanical fold, the framing texts, statement cleaning, the three output kinds (incl. the outline→composure conclusion and its one retry), reconvening, the pal seam, transcript export, and the `Council` class. **No FastAPI import.** Two seams: `run_council_turn` (where every test swaps the model out) and `PAL_CALL` (where the `/pal` lane wires the cloud in). | `Council`, `validate_meta()` / `validate_participants()` / `validate_output()` / `_charge()`, `speakers()` / `next_speaker()` / `advance()`, `build_messages()` / `identity_for()` / `fold_summary()`, `brief_markdown()` / `output_sentence()` / `brief_text()`, `conclude_composure()` / `outline_composure()` / `output_composure_path()` / `strip_code_fence()` / `OUTLINE_RETRY`, `reconvene_meta()` / `reconvene_input()` / `link_doc()`, `PAL_CALL` / `ask_pal_turn()` / `pal_participant()` / `pal_statement()` / `PAL_DISTILL` / `PAL_TINT` / `PAL_PROMPT_CHARS`, `share_for()` / `resolve_n_ctx()` / `probe_n_ctx()`, `run_council_turn()`, `turn_in_flight()` / `busy_paths()` / `reset_runtime()`, `OUTPUT_KINDS` / `OUTPUT_KINDS_LANDED` / `RESERVED_KINDS` / `COMPOSURE_OUTPUT_FORMS` / `MAX_CHARGE_CHARS` / `RECONVENE_EXCERPT_CHARS` / `CTX_CLOUD` / `FOLD_AT` / `MIN_TRANSCRIPT_TOKENS` / `MAX_PARTICIPANTS` / `MAX_ROUNDS_CAP`, `CouncilError` |
| [enough/council_api.py](../enough/council_api.py) | ~680 | `build_router(project_dir, resolve_path, emit, session)` → the `/api/council/*` router. HTTP translation, the two lock exclusions, the brief-module write at setup, `POST /api/council/reconvene`, and the `council` SSE event. | `build_router()` |
| [enough/readvisor_tools.py](../enough/readvisor_tools.py) | ~325 | `install_readvisor` (P7): the nine ordered refusals, the payload scan through a tempdir, the `.<name>.installing/` stage-then-rename write, and the `readvisors_changed` side effect. `register()` wires it into `tools._DISPATCH` at import time; gated by `readvisory_install`. | `TOOL_NAMES`, `register()`, `run_install_readvisor()`, `scan_documents()`, `shipped_names()` |
| [enough/pal_tools.py](../enough/pal_tools.py) | ~380 | `/pal` (0.4.0): the command parser, the turn window, the `ask_pal` tool runner and the result codec. **No cloud import at module level** (`enough.cloud` drags httpx + keyring in) — `run_ask_pal` imports it inside the function, and the untrusted-content markers are kept as literals that `tests/test_pal.py` pins to the real constants. `register()` wires `ask_pal` into `tools._DISPATCH` / `_TRACE_TOGGLE` at `tools` import time. Gated by nothing of its own: the cloud gate is the gate. | `TOOL_NAMES`, `register()`, `strip_command()`, `pal_turn()` / `turn_active()` / `reset_runtime()` / `PalTurn`, `run_ask_pal()`, `render_result_body()` / `parse_result_body()`, `USAGE_HINT` / `ALREADY_CLOUD_NOTE` / `denial_no_pal_turn()` / `denial_already_asked()` / `denial_too_long()`, `MAX_PROMPT_CHARS` / `MAX_TOKENS` / `CACHE_SOURCE` / `SIDE_EFFECT` / `RESULT_HEADER` |
| [enough/dictionary.py](../enough/dictionary.py) | ~1210 | FEED's engine (0.4.1): locations + seams, the background build of `feed.sqlite` from `reflib/dict` (digest-gated, temp file + `os.replace`, cancellable), the read API over both DBs (the user row wins; `origin` on every row), the nine sort keys and the SQL functions behind two of them, the in-process order cache, and the user-dictionary writes. Since 0.4.3 also `lookup_many()`, the batch lookup on one connection that grounds a fabula's terms. **No FastAPI import.** See "The dictionary (FEED)". | `source_dir()` / `state_root()` / `available()`, `ensure_built(background=)` / `build()` / `cancel_build()` / `status()`, `lookup()` / `lookup_many()` / `entry()` / `entries()` / `index()` / `position()` / `facets()`, `user_add()` / `user_update()` / `user_delete()`, `era_ord()` / `era_group_ord()` / `syllable_count()`, `normalize()`, `SORT_KEYS` / `FILTER_KEYS` / `JSON_COLUMNS` / `REQUIRED` / `REPORTED` / `MAX_LIMIT`, `DictionaryUnavailable` |
| [enough/dictionary_api.py](../enough/dictionary_api.py) | ~100 | `build_router()` → the `/api/dict/*` router; closes over nothing (the dictionary is install-wide). Plain `def` handlers on the thread pool: 400 for a bad sort/filter, 503 while unbuilt, 404 for an unknown `/entry`. | `build_router()` |
| [enough/dictionary_tools.py](../enough/dictionary_tools.py) | ~340 | The four readvisor FEED tools; `register()` wires them like `pal_tools`. Writes reach only the user DB and fire `dict_changed`. **No toggle** — the documentation is what is gated. | `TOOL_NAMES`, `SIDE_EFFECT`, `register()`, `run_dict_lookup()` / `run_dict_add_entry()` / `run_dict_update_entry()` / `run_dict_guide()`, `render_entry()`, `fields_from_call()` / `parse_form()`, `guide_text()` |
| [enough/intro.py](../enough/intro.py) | ~205 | The brief introduction (0.4.1): the text (`defaults/intro.md`, translations at `static/i18n/<lang>/intro.md`), the whole-message match `/api/chat` answers with no model turn, the `show_intro` tool and its `intro` side effect, and the reload re-render. | `text_for()` / `path_for()` / `english_path()`, `is_intro_request()` / `INTRO_PHRASES` / `INTRO_COMMAND` / `normalize()`, `bubble()`, `run_show_intro()`, `render_tool_result()` / `is_intro_text()`, `set_language_source()`, `register()` |
| [enough/skillaudit.py](../enough/skillaudit.py) | ~1020 | First-use audit of untrusted skills (0.2.2). Trust classification (symlink into *an* enough install's `defaults/skills/` = trusted — this install or a sibling one, since 0.2.7), the content fingerprint, the `verdict.json` sidecar, both audit passes (deterministic `payload_scanner.py` + a single non-streaming LLM completion — since 0.4.3 through `llm.complete(cloud_gate=False)`; `_complete` / `_message_text` / `_completion_budget` survive as thin wrappers for its tests), the in-flight registry, and the guarded toggle. Progress on the `skill-audit` SSE event. | `is_trusted()`, `fingerprint()` / `skill_fingerprint()`, `skill_state()`, `set_skill_enabled_guarded()`, `SkillAuditRefused`, `audit_skill()` / `audit_and_enable()`, `run_llm_audit()` (module-level test hook), `quarantine_untrusted()`, `trust_override()`, `read_verdict()` / `write_verdict()` |
| [enough/agent_free.py](../enough/agent_free.py) | ~85 | Agent-free mode (0.4.4): the one reader of the machine-global `agent_free` switch in ui.json (honours `ENOUGH_UI_CONFIG`; stat-cached; on only for a literal `true`) and the 409 sentence. Stdlib only, imports nothing from enough — `llm`, `cloud`, `supervisor`, `preflight`, `tools` and `server` all ask it. See "Agent-free mode". | `enabled()`, `value()`, `ui_config_path()`, `detail()`, `KEY`, `REASON` |
| [enough/broker.py](../enough/broker.py) | ~440 | Broker config (toggles), trace journal writer, canned denial messages. New toggles auto-render in the broker pane via `/api/broker`. | `TOGGLES` tuple, `load_config()`, `is_enabled()`, `trace()`, `denial_*()` |
| [enough/tools.py](../enough/tools.py) | ~1825 | Tool runners (`read_file`, `write_file`, `shell`, `fetch_url`, `read_highlights`, `navigate_to_highlight`, `cloud_pipeline`, girraph ops, wiki tool wrappers, the three `canon_*` store tools), the tool-call XML parser, the dispatch table. Seven import-time `register()` calls at the bottom fold in the composure, readvisor, pal, dictionary, MacroCOSM (`canon_tools`), Thym (`thym_tools`, 0.5.0) and intro tools. `read_file` alone may follow a `rness/` symlink into a shipped root, read-only (`_shipped_read_target`, 0.4.1). `fetch_and_cache()` is the shared fetch pipeline `run_fetch_url` and the webframe refresh both render. | `_DISPATCH` (~line 1680), `_TRACE_TOGGLE` (~line 1709), `execute()`, `_safe_join()` / `_shipped_read_target()`, `parse_tool_calls()`, `fetch_and_cache()`, `ToolResult.side_effects`, `_CLOUD_KEY_EXFIL_PATTERNS` |
| [enough/project_meta.py](../enough/project_meta.py) | ~300 | `rness/project.json`: the project's nice name + description, the `ui` block (`ui_scale`, `text_scale`, `readvisor_panel`) and the `composure` block (`launch`, `path`, `form`, `last`). Every reader gets a fully populated, validated view; a garbage value reads as the default rather than raising. | `load()`, `save()`, `save_ui()`, `save_composure()`, `touch_composure()` |
| [enough/convert.py](../enough/convert.py) | ~1395 | Document conversion (0.2.5): the format **registry** (`FORMATS`), engine probing + caching, twin/assets/manifest naming, the state machine, the job runner that drives the worker, export/sync/resolve, and the `pdf`-extra installer. Imports nothing heavy — docling and pandoc are only ever reached through `convert_worker`. See "Document conversion" below. | `FORMATS` / `formats_view()` / `engines()`, `pandoc_path()` / `typst_path()` / `docling_available()`, `twin_path()` / `assets_dir()` / `manifest_path()` / `pair_for()`, `state()` / `has_twin()`, `read_manifest()` / `write_manifest()`, `ConvertJobs`, `do_export()` / `sync_after_save()` / `resolve()`, `ExtraInstaller`, `installed_extras()` / `record_extra()`, `reset_engines()` |
| [enough/convert_worker.py](../enough/convert_worker.py) | ~840 | The out-of-process worker: `python -m enough.convert_worker`, one JSON job on stdin, NDJSON records on stdout, exit. pandoc is shelled out to; **docling runs in this process** — which is the whole reason the worker exists (torch must never be imported into the server). | `main()`, `_OPS` (`convert` / `export` / `prefetch`), `do_convert()` / `do_export()` / `do_prefetch()`, `_convert_docling()`, `_flatten_media()` / `_relink_docling_assets()` / `_normalize_images()`, `_Heartbeat`, `TWIN_FORMAT` |
| [enough/wikisink/](../enough/wikisink/) | ~2840 (pkg) | Local offline Wikipedia. `config.py` (install registry, schema v2 multi-install, data paths), `zim.py` (libzim reader, search, sanitize/rewrite), `download.py` (Kiwix flavor listing + resumable downloads), `overlay.py` (live-refreshed + preserved article stores), `comments.py` (per-article threads), `save.py` (save/read/unsave article folders + the clean HTML→markdown text pipeline), `update.py` (the "wikisink" update run), `rankings.py` (pageview snapshots), `report.py` (run report), `agent.py` (the four readvisor tool runners). | `config.load_config()` / `installs()` / `active_install()` / `unavailable_reason()`, `zim.get_article()` / `search()`, `download.DownloadManager`, `update.run_wikisink()` |
| [enough/cloud.py](../enough/cloud.py) | ~1080 | OpenRouter integration: keyring read/write, in-memory key cache, OpenAI-compatible streaming + non-streaming clients, health check, response caching to `rness/io/cloud-cache/`, the broker-driven `pipeline_run()`, and **`gate_status()`** — the one three-step gate every door that sends a prompt off this machine asks (0.4.0). | `set_api_key()` / `clear_api_key()` / `has_api_key()`, `_get_api_key_for_broker()`, `gate_status()`, `health_check()`, `chat_completion()`, `stream_chat_completion()`, `cache_completion()`, `wrap_untrusted_cloud_text()`, `pipeline_run()` |
| [enough/llm.py](../enough/llm.py) | ~320 | OpenAI-compatible client for the local llama-server: the streaming path for chat, and (0.4.3) **the one-shot door** — `complete()`, lifted from `skillaudit._complete`, routed like chat (local llama-server, or `cloud.chat_completion` when `current == "opro-api"` and the cloud gate is open; a cloud answer's meta says `provider: "openrouter"` since 0.6) — plus `reachable()`, which the derivation routes and tools ask before choosing model or rules mode. 0.6 adds `complete_local()` (llama-server only, whatever the chat's slot; what `model_route`'s local route calls) and `usage_of()` (a response's token counts). See "The fabula" and "Models" → "A model route per job". | `stream_chat()`, `check_llm_reachable()`, `complete(messages, *, llm_url, max_tokens=, temperature=, timeout=, cloud_gate=)` → `(text, meta)`, `complete_local(messages, *, llm_url, …)`, `usage_of()`, `reachable(llm_url)` → `(ok, reason)`, `LLMUnavailable`, `message_text()`, `completion_budget()` |
| [enough/model_route.py](../enough/model_route.py) | ~155 | A model route per job (0.6, pins P6): one factory gives a job its `complete(messages, **kw) -> (text, meta)` for the route it was given — `local` (llama-server, `llm.complete_local`) or `cloud` (`cloud.gate_status()` first, then `cloud.chat_completion`, the cloud cache with the job's own `source`, one broker-journal entry per call, never the prompt or the answer). A shut gate or agent-free raises `RouteRefused` in the gate's own words, with no fall back to local. `meta` carries `route`, `provider` (cloud), `model`, `usage`. See "Models" → "A model route per job". | `make_complete(route, *, model=, llm_url=, project_dir=, source=, temperature=, timeout=)`, `holds_generation_lock(route)`, `RouteRefused`, `ROUTES`, `JOURNAL_TOOL` |
| [enough/supervisor.py](../enough/supervisor.py) | ~500 | Manages the local llama-server subprocess. Adopts an existing process if one's already up; spawns its own otherwise. Skips spawning entirely when the active model is `opro-api`. Under 32 GB of RAM `_launch` adds the memory caps (`models.launch_caps`) and writes their one-line note at the head of the launch's part of `server.log`; its `on_ready` callback (one attribute, set by `create_app`) fires each time `/health` turns 200 after a launch, an adopt or a switch (0.4.3). Since 0.6 `_launch` passes `--alias <cute name>`, so the `model` id llama-server reports — and every record that carries it (`derived.model`, a Thym `engine: model:<id>`) — is the name people know (`g40-04`); an adopted server started before keeps its old id until relaunched. | `LlamaSupervisor`, `_resolve_startup_choice()`, `on_ready` / `_notify_ready()` |
| [enough/preflight.py](../enough/preflight.py) | ~355 | The context-window preflight (0.4.3): counts the default system prompt with llama-server's own `/tokenize`, reads the live window from `/props`, keeps a 2,048-token reserve, and decides whether the empty conversation offers a one-click larger window. Background-only, never raises into a request, skips cloud mode. stdlib + httpx. See "Models". | `Preflight` (`schedule()` / `run()` / `fields()` / `invalidate()` / `cancel()`), `evaluate()`, `suggest_ctx()`, async `count_tokens()` / `read_n_ctx()`, `n_ctx_from_error()`, `first_turn_advice()`, `RESERVE` / `WINDOWS` |
| [enough/models.py](../enough/models.py) | ~785 | Local-model registry (7 cute-named local models, defined in `defaults/models.json`; two carry separate MTP draft GGUFs, two carry a `llama_cpp_min_release` gate). Feasibility verdicts (RAM + free disk, and since 0.4.3 optionally one context window), the small-machine launch caps and the `--help` probe behind them, `install-menu` CLI for bootstrap.sh. Selection state in `~/enough/config/models.json`. | `load_registry()`, `load_state()`, `save_state()`, `resolve()`, `all_models_view()`, `feasibility(entry, ctx=None)`, `recommend_ctx()`, `launch_caps()`, `llama_server_flags()`, `release_gate()`, `install_menu_rows()` |
| [enough/model_download.py](../enough/model_download.py) | ~395 | Resumable GGUF downloads for the in-app model manager: main file then optional MTP draft, ranged-GET resume off a `.part`, one active download per process, cancel-keeps-partial, delete. Backs `/api/models/{download,delete}/*`; progress on the `model-dl` SSE event. | `ModelDownloadManager` (`start` / `cancel` / `delete` / `state`), `pending_phases()`, `partials()` |
| [enough/skeleton.py](../enough/skeleton.py) | ~1015 | Creates `rness/` for new projects (copies from `defaults/`), syncs global skills/**readvisors**/paradigms on every launch via dedicated populators, runs migrations. `_populate_skill_symlinks` also heals materialized copies of shipped skills (a byte-identical real dir left by a cloud-sync/dereferencing copy is swapped back to a symlink — 0.2.8) and calls `skillaudit.quarantine_untrusted()` — untrusted skills default OFF. `_populate_role_symlinks` walks **two** global sources (user-global then shipped) and re-aims managed links; `_migrate_roles_to_readvisors` renames `rness/roles/` in place (0.3.5). | `ensure_skeleton()`, `resync_globals()`, `_SKELETON_PLAN`, `_PROJECT_LOCAL_FILES`, `_EMPTY_DIRS`, `_populate_skill_symlinks` / `_populate_role_symlinks` / `_populate_paradigm_symlinks`, `user_readvisors_root()` / `shipped_readvisors_root()` / `_readvisor_sources()`, `_migrate_roles_to_readvisors()`, `cloud_sync_provider()` |
| [enough/footnotes.py](../enough/footnotes.py) | ~420 | Footnote surgery for in-progress markdown (0.2.7): parse/renumber/insert over standard `[^n]` refs + a terminal definitions block. Pure functions, offset-stable code-masking (fences + inline spans blanked to NULs), numeric labels managed, named tolerated, orphan defs never touched. `tests/test_footnotes.py` doubles as the spec for the `fn*` JS mirror in index.html. | `parse()`, `renumber()`, `next_number()`, `insert_at()`, `definitions_span()`, `REF_RE` / `DEF_RE` |
| [enough/paginate.py](../enough/paginate.py) | ~920 | Pagination (0.2.7): options schema + named size table, output naming (`name-YYYY-MM-DD.pdf` + `-1`/`-2`), the `.typ` surgery (pandoc-template split, balanced-bracket `#footnote[...]` extraction, endnote reflow, option preamble), pure 2-up/booklet imposition math, bundled-fonts lookup, and the PDF source-attachment probe that powers unpack-on-import. Heavy lifting (pandoc/typst/pypdf compile) runs in `convert_worker.do_paginate`. See "Pagination" below. | `validate()`, `sizes_view()` / `page_size_mm()`, `output_pdf()` / `pages_dir()` / `viewer_manifest_path()`, `fonts_dir()` / `font_paths()`, `embedded_source()` / `has_embedded_source()`, `sheet_order()` / `slot_rect()`, `split_template()` / `extract_footnotes()` / `place_endnotes()` / `preamble()` / `build_typ()`, `status()` / `run_paginate()`, `PaginateError` |
| [enough/highlights.py](../enough/highlights.py) | ~280 | Review-mode color highlights (yellow/green/blue/pink) stored in per-doc `.<filename>.highlights.json` sidecars. Tools `read_highlights` and `navigate_to_highlight` consume them. | — |
| [enough/girraph.py](../enough/girraph.py) | ~885 | The girraph primitive: parser/serializer for the plain-text `.girraph` IBIS format, node-level ops (the only way content changes), ASCII tree renderer, per-path write locks. Agent tools and UI endpoints both call through here. | `loads()` / `dumps()`, `add_node()` / `update_node()` / `link_nodes()` / `remove_node()`, `ascii_render()`, `path_lock()` |
| [enough/canon.py](../enough/canon.py) | ~2685 | Canon (0.4.3; the cacheawl store, moved and extended): volume CRUD, path/URL/wikisink **ingest** (with the Holotype privacy filter), the `canon.cosm` volume catalogs and the project catalog `rness/canon.cosm`, reconcile, the on-demand merirmaid mirror, the catalog/meta write-guards, transfer (copy/move), the one-time store-folder rename, the twin listing rules (`emf_state` is the one fresh/stale rule; since 0.6 `fabula_twins`, `listing_entry` and `superseded_entry` list a fabula under every name it may have, through `fabula_names`, and a catalog item names its twin as `fabula:`, read back by `item_fabula`, which also reads the `emf:` of catalogs made before), the launch-time `infoworld` migration, and (0.5.0) Thym packages as volume kinds: the suffixes `PACKAGE_FOLDER_SUFFIX` (`.thym`), `PACKAGE_FILE_SUFFIX` (`.package.cosm`), `SEALED_SUFFIX` (`.thym.enc`), `is_package_folder` (a `<stem>.thym/` whose `package.cosm` sniffs `oes: thym/1`) / `is_package_file` / `is_sealed_package` / `package_stem` / `package_text_name` / `packages_beside`; `file_kind` says `package` / `sealed`; the scan never recurses a package folder and the catalog lists one as a single `kind: package` item; `catalog_excerpt` (the surrounding context, built in memory). Root `~/enough/canon/` (`ENOUGH_CANON_ROOT`). Owns everything under the store. Still exports the generic folder→flowchart walker `home.py` builds project maps with. See "Canon". | `root()`, `migrate_store_folder()`, `create_volume()` / `list_volumes()` / `volume_tree()` / `rename_volume()` / `delete_volume()` / `require_volume()`, `run_ingest()`, `build_catalog()` / `regenerate_catalog()` / `project_catalog(project_dir, *, write=)`, `reconcile()` / `reconcile_all()`, `build_mirror()`, `folder_flowchart()`, `is_catalog_file()` / `catalog_write_denial()`, `emf_twin_path()` / `is_emf_twin()` / `fabula_twins()` / `emf_twins()` / `listing_entry()` / `superseded_entry()` / `item_fabula()` / `emf_state()` / `twin_header()`, `is_holotype_folder()`, `slug()` / `item_slugs()` / `file_kind()`, `transfer()`, `migrate_infoworld()`, `CanonError` / `CanonNotFound`, `CATALOG_ITEM_CAP` |
| [enough/macrocosm.py](../enough/macrocosm.py) | ~2655 | The MacroCOSM OES reference reader (0.4.3): the COSM YAML loader, manifests and the registry, volumes, paths/URIs, references, the generic checks, Mermaid lenses and the text tree, a CLI. Since 0.6 it knows the **core**: a manifest's `core: true` (`Registry.built_ins()` / `minicosms()`), a declaration's old spellings (`declaration.old`; `Declaration.how == "old"`), module D read from `core.modules.cosm` and inherited by every format, the generic checks `flavour` and `flavour-kind`, addresses `<id>#<field>`, a manifest's dialectic banks (`Manifest.banks()`) and `tree_digest(folder)`. **PyYAML + stdlib only, imports nothing from enough** — vendorable as one file. See "MacroCOSM". | `yaml_load()` / `dump()` / `sniff_declaration()`, `Registry` / `default_registry()` / `load_manifest()` (seven manifests since 0.5.0: the core's five built-ins and the two MiniCOSMs; `*.moves.cosm` sidecars and `core.modules.cosm` are not manifests), `Registry.built_ins()` / `minicosms()` / `by_name()` / `by_declaration()` / `known()`, `CORE_CHECKS`, `REGISTRY_ORDER`, `tree_digest()`, `Volume.name` (falls back to a catalog's `handle`, so a holograph is titled by its pseudonym — 0.5.0), `load_volume()` → `Volume`, `parse_path()` / `resolve_path()` / `qualified_uri()`, `resolve_ref()`, `lint()` → `Report`, `lenses()` / `to_mermaid()` / `to_text_tree()`, `Refusal` (falsy), `CHECKS`, `DEFAULT_MANIFEST_DIR` |
| [enough/docoes.py](../enough/docoes.py) | ~2250 | DocOES (0.4.4): a markdown document enumerated as a `doc/1` volume — sections, terms, examples, the decisions of a "Decisions …" or (0.5.4) "Changes" section, the help bubbles, and the reference (`R:` items) generated from the format manifests (grouped since 0.6 as the core's built-ins, then the MiniCOSMs); build-on-digest into `ENOUGH_DOCS_ROOT`; the byte-for-byte round trip; inventories and cross-volume refs; DocOES's seven checks; a CLI. Since 0.5.4 the four specifications resolve to a synced copy under `ENOUGH_SPECS_ROOT` when one is in use (since 0.7 only when its edition is not older than the bundled one), with their editions from `docs/specs.json` or the synced `state.json`. stdlib + PyYAML + `enough.macrocosm`. See "DocOES". | `DOCUMENTS`, `BUBBLE_DOCUMENT`, `tellings()`, `docs_root()`, `specs_root()`, `bundled_editions()`, `edition_key()`, `spec_info()` / `spec_source()` / `document_version()`, `OTHER_DOC_WORDS`, `validate_spec_source()`, `ensure_built()` / `is_fresh()` / `build()` / `load_built()`, `catalog_for()`, `compile_doc()`, `inventory()` / `resolve_xref()`, `lint_doc()`, `atem_problems()`, `DocsUnavailable` |
| [enough/specs.py](../enough/specs.py) | ~170 | The specifications kept current from cosmoes.org (0.5.4): the launch check — one daemon thread per server start running the vendored client's `sync` of the four sources into `ENOUGH_SPECS_ROOT`, each candidate validated by `docoes.validate_spec_source` (a real DocOES build) — its report for `GET /api/specs-status`, the `specs_sync` preference and the three seams. Never on the request path, never blocking startup, one request per launch, 3 s timeout, INFO when something updated. See "DocOES". | `SLUGS`, `PREF_KEY`, `USER_AGENT`, `launch_check()`, `status()`, `documents()`, `cosmoes_base()`, `sync_allowed()`, `preference_on()`, `reset_for_tests()` |
| [enough/cosmoes_client.py](../enough/cosmoes_client.py) | ~680 | **Vendored, never edited here** (0.5.4): cosmoes-site's `client/cosmoes_client.py` byte for byte, the commit it was taken from in `docs/specs.json`; the one sync client for cosmoes.org's `/manifest.json` and `/raw/*` — hosts restricted to cosmoes.org (loopback under a loopback base), sha256-verified, 5 MB-capped, same-host redirects only, an ETag, atomic writes, `state.json` last; `sync` never raises for a network or content fault. Stdlib only. A fix goes to cosmoes-site and is taken again by `scripts/sync_specs.py`. | `CosmoesClient`, `Report`, `Fetch`, `basic_validate`, `load_state`, `main` |
| [enough/canon_derive.py](../enough/canon_derive.py) | ~3300 | The derivation engine (0.4.3): text → fabula twin, fabula → short (markdown), text or passage → atem, pins. Since 0.6 it writes `oes: fabula/1` with a `flavour` under the new names (`FABULA_OES`; `EMF_OES` is only read), records `derived.route`/`provider`, carries an old twin's `shorts:`, pins and dialectic over a re-derive (`replace_twin`, `carry_dialectic`), asks for the new modules on the atem's own request (the whole-text pass) and reads verse through `enough/verse.py`. **Pure functions, no server imports**; every model call through an injected `complete`. See "The fabula". | `derive_emf()` (the name stays; it derives a fabula), `replace_twin()`, `carry_dialectic()`, `short_footer()`, `derive_atem()`, `compile_short()` / `compile_text()`, `record_short()`, `short_path()` (old name `compiled_path`, removed in 0.6), `default_order()` / `source_path()`, `pin_atem()` / `next_atem_id()` / `set_file_atem()`, `read_source()`, `write_atomic()` / `write_twin()`, `twin_path()` / `new_twin_path()` / `twin_state()`, `FABULA_OES` / `EMF_OES` / `FABULA_DECLARATIONS`, `candidate_terms()` / `entity_candidates()` / `chunk()`, `DeriveCancelled` / `DeriveError`, `TEXT_SUFFIXES` |
| [enough/canon_prompts.py](../enough/canon_prompts.py) | ~195 | The derivation prompts, plain strings (`.format` only); test-asserted to name the six stances, rule out pronouns, keep `EMF_SYSTEM` under 2,000 chars and carry the owner's atem definitions verbatim. 0.6 adds the whole-text pass's item shapes and rules (they follow `ATEM_SYSTEM` word for word in one request) and the verse prompts | `EMF_SYSTEM` / `EMF_USER` / `EMF_CONTINUE` / `EMF_RESTART` / `EMF_RETRY` / `EMF_REPAIR`, `ATEM_SYSTEM` / `ATEM_USER` / `ATEM_WHOLE_USER`, `WHOLE_ITEMS_PROSE` / `WHOLE_ITEMS_VERSE` / `WHOLE_RULES` / `WHOLE_DIGEST`, `VERSE_SYSTEM` / `VERSE_USER`, `COMPILE_SYSTEM` / `COMPILE_ORDER` / `COMPILE_USER` |
| [enough/canon_jobs.py](../enough/canon_jobs.py) | ~275 | The derivation job table (convert's shape): one writing job per file, the generation-lock rule for model-mode jobs, cooperative cancel, SSE event `canon`. 0.5.0 adds the kinds `thym` (a program's run) and `read` (a reading) and a nested `progress: {node, of, name, move, state}` that `JobContext.progress` passes through; 0.6 adds `fabulac` (a build) and `dialectic` (a settle), a record's `route` and `flavour`, and a cancel that may say what stayed | `CanonJobs` (`start` / `snapshot` / `cancel` / `active` / `holding` / `record`), `JobContext`, `EVENT`, `KINDS` |
| [enough/canon_tools.py](../enough/canon_tools.py) | ~1460 | The six MacroCOSM readvisor tools (`cosm_read`, `cosm_lint`, `fabula_derive` — `emf_derive` until 0.6 —, `atem`, `cosm_guide`, and since 0.4.4 `doc_lookup`), `text_target` — the derivation refusals the routes share, by flavour since 0.6 — the route a tool asks for (`check_route`, `model(route, project_dir)`), `lint_of` (a fabula's own checks, a holograph's, else the generic ones) and the `configure()` seam. `register()` wires them at `tools` import time. Never takes the generation lock (see "The fabula"). Since 0.5.0 `text_target` also refuses a Thym package folder and anything inside it (`inside_package`, beside `inside_holotype`: "a package is kept whole") | `TOOL_NAMES`, `register()`, `configure(llm_url=, jobs=)`, `text_target()` / `TextTargetError`, `inside_holotype()` / `inside_package()`, `catalog_after()`, `check_route()` / `model()`, `lint_of()`, `run_cosm_read()` … `run_fabula_derive()` (`run_emf_derive` an alias) … `run_cosm_guide()`, `run_doc_lookup()` / `find_doc_entry()`, `STORE_PREFIXES`, `TEXT_MAX` / `EMF_MODEL_MAX` |
| [enough/fabula.py](../enough/fabula.py) | ~360 | The fabula's own checks (0.6): the generic report plus the eight the `fabula` manifest keeps (`code-span`, `licence-recorded`, `question-about`, `question-shape`, `session-declared`, `reading-whose`, `interface-signature`, `case-outcome`) on a fabula, or the dialectic's three on any other volume holding D items. What the cosm viewer, `cosm_lint` and `/api/cosm/lint` run on a fabula; `python -m enough.fabula lint <path> [--json]`. Stdlib + PyYAML + `enough.macrocosm` | `lint()` (alias `lint_fabula`), `own_checks()`, `is_fabula()`, `flavour()`, `FABULA_CHECKS`, `DIALECTIC_CHECKS`, `OWN_CHECKS`, `CONTRACT_NAMES` |
| [enough/fabula_names.py](../enough/fabula_names.py) | ~390 | Every name a fabula has on disk, in one place (0.6): the twin's name per flavour, the old name, pairing a twin with its text, the twin a single slot shows (the one derived last), a folder's twins for a listing, a short's stem, the flavour suggestion. Stdlib + `enough.macrocosm`; never writes. See "The fabula" → "Names on disk" | `OES` / `OLD_OES` / `DECLARATIONS`, `FLAVOURS` / `TEXT_FLAVOURS`, `twin_name()` / `twin_path()` / `old_twin_path()`, `parse()`, `check_text_flavour()` / `FlavourError`, `declares_fabula()`, `text_twins()` / `primary()` / `find_twin()`, `text_of_twin()` / `is_twin()` / `superseded_by()`, `folder_twins()`, `short_stem()` / `standalone_names()`, `suggest_flavour()` |
| [enough/verse.py](../enough/verse.py) | ~815 | Verse by rule (0.6): stanzas and lines, stresses from FEED's pronunciations, metre and the rhyme scheme, the items a fabulap's rules write (`C:line`, `C:metre`, `C:rhyme`). No model | `read_poem()`, `scan()`, `metre()`, `rhyme_scheme()`, `feed_pronunciations()` |
| [enough/dialectic.py](../enough/dialectic.py) | ~2770 | The dialectic's deterministic core (0.6): module D on any volume — reading questions and sessions, raising them from a bank and from a volume's pending and unsure items, recording answers (into an answers volume beside the volume, or into it), settling, staleness and carrying over a re-derive; a volume written back byte for byte outside the change. No model, no network, no server, no Thym import; `python -m enough.dialectic list\|raise\|answer\|settle`. See "The dialectic" | `open_twin()` / `Twin`, `ledger_of()` / `Ledger`, `questions()` / `open_questions()` / `banks_for()`, `raise_questions()`, `record()` / `check_value()`, `answers_path()` / `is_answers_of()`, `mark_stale()` / `carry_over()`, `DialecticError` / `AnswerRefused` |
| [enough/dialectic_api.py](../enough/dialectic_api.py) | ~845 | HTTP translation for the dialectic (0.6): `build_router(...)` → `/api/dialectic/questions\|check\|answers\|raise\|ask-again\|settle`, `POST /api/ascribe/isograph` and `POST /api/ascribe/allograph` (one runner, `_projection`); one family of routes for every volume, dispatching on its format (a fabula, any `.cosm` volume, a holograph by Ascribe's rules); a settle is a CanonJob of kind `dialectic`. Also the plain functions the `dialectic` tool calls | `build_router()`, `listing()`, `record()`, `raise_bank()`, `ledger()`, `DialecticRouteError` |
| [enough/fabulac_job.py](../enough/fabulac_job.py) | ~1090 | A folder of Python decompiled into its fabulac as one resumable job of five Thym runs, and a fabulac compiled into a cshort and its catems (0.6); `build_router(...)` → `/api/fabula/build\|resume\|cancel\|compile\|compiled\|cshort\|cshort/file\|catem`. State is read from disk only. See "Building a fabulac" | `build_router()`, `build_state()`, `target_of()`, `BuildError`, `STAGES`, `STAGE_WORDS`, `PROGRAM_FILE`, `COMPILE_FILE` |
| [enough/fabulac_prompts.py](../enough/fabulac_prompts.py) | ~245 | The prompts of the fabulac's model-backed steps (`read`: a file against the outline; `fold`: the whole; `code` and `readme`: a cshort's files; `catem`), each system prompt under 2,000 characters. `thym_host` finds its `PROMPTS` by name (`thym_host.PROMPT_MODULES`) and puts them before its own builders for `derive` and `entail`. A host module, never vendored | `PROMPTS`, `BUILDERS`, `STEPS`, `messages()`, `step()` |
| [enough/repo_engine.py](../enough/repo_engine.py) | ~1045 | The fabulac's two engines (0.6), reached from Thym moves as `ctx.engines["repo"]` and `ctx.engines["syntax"]`: `repo` (`history`, `tree`, `files`, `text`: a clone's log and tags through one fixed `git log` / `git for-each-ref` command line that touches no index, work tree or network) and `syntax` (`outline`, `parse`, `manifest`: Python read by `ast` on its text, project files by `tomllib` / `configparser`; nothing imported, `setup.py` never run). Every answer is plain data, recorded for replay. A host module, never vendored | `engines()`, `REPO`, `SYNTAX`, `run_git()`, `language()` |
| [enough/fabula_tools.py](../enough/fabula_tools.py) | ~260 | The readvisor's `dialectic` and `fabulac` tools (0.6), behind the `macrocosm-oes` skill; a build, a compile or a settle started from a tool is a job like the page's, handed to the event loop (`configure(start=…)`) and run after the turn. See "Tools" | `TOOL_NAMES`, `register()`, `configure()`, `run_dialectic()`, `run_fabulac()`, `SHOWN` |
| [enough/retired_names.py](../enough/retired_names.py) | ~35 | The one table of the names 0.6 retired that still answer (three route paths, the tool `emf_derive`, the body word `what: emf`). **Goes in 0.7**: delete it, the loop in `server.create_app` that reads `ROUTES` and the lookup in `tools.execute` that reads `TOOLS` | `ROUTES`, `TOOLS`, `WORDS`, `tool()` |
| [enough/thym/](../enough/thym/) | ~19 800 (pkg) | **Thym** (0.5.0; `thym 1` in the 0.6 round): the compiler and the reference runtime of `docs/THYM.md`, one compiler reading two grammars (`thym 0` and `thym 1`). Compiler: `parse.py` (recursive descent, line-keeping; per-version tables `THYM0` / `THYM1`), `declarations.py` (every manifest's `moves:` and every `*.moves.cosm` sidecar; `since`, `thym-1:` views, `extends`), `types.py`, `check.py` (resolve, types, static contracts, contract blocks and `keeps`, recursion under `depth:`, the double compile that names "this needs `thym 1`"), `enumerate.py` (a `.thym` file ⇄ a `thym/1` program volume, byte for byte), `plan.py` (the loop node, the plan's `models`), `contracts.py`. Runtime: `values.py`, `registry.py`, `checks.py` (the dynamic checks of THYM.md 7.3), `coprocessor.py` (`Refusing…`, `Replay…`), `run.py`, `trace.py`, `engines.py` (the per-node call counter; engine calls recorded and replayed), `folder.py` (0.6: the folder rule, the tree digest, the folder snapshot; stdlib only), `vault.py` (the sealed package: Comprise's `comprise-bundle/0`), `conform.py`, `cli.py`, `__main__.py`. Moves: `moves/{emf,edit,morph,project,doc,pack}.py` and, since 0.6, `moves/{code,dialectic,ascribe}.py`. **Imports the stdlib, PyYAML and `enough.macrocosm` only** (`tests/test_thym_run.py` parses the runtime's imports): enough's engines plug in through `thym_host`, and Comprise vendors the package (see "Thym" → "What may live under `enough/thym/`"). See "Thym". | `check_file()` / `plan_file()`, `Refusal`, `parse.parse()`, `check.check()`, `enumerate.enumerate_file()` / `compile_volume()`, `plan.plan()` / `plan.build()`, `run.run()` / `run.replay()`, `trace.runs_dir()`, `conform.conform()`, `cli.main()` / `cli.plan_atem()`, `vault.seal()` / `vault.open()` |
| [enough/thym_host.py](../enough/thym_host.py) | ~1440 | enough's side of Thym. Since 0.6 the route a run uses (`check_route`, `route_info`, `route_complete` through `model_route`, `plan_for` with the plan's `models`, `asks_said` and `route_refusal` for a plan that asks, `route_preflight`, `holds_lock`), the sibling engines by name (`SIBLING_ENGINES`: `repo`, `syntax`, `dialectic`, `ascribe`; `pron` for verse when FEED is built, cut to `PRON_FIELDS`), the prompt modules found by name (`PROMPT_MODULES`), and the input check (`ACCEPTS`, `check_input`). Before that: `ModelCoprocessor` over a route's `complete` (schema'd answers, narrow repair, a prose-wrapped YAML answer failing `schema` and re-asked with `ONLY_THE_YAML`), the eight prompt builders (`PROMPTS`), `engines()` (canon, docoes, feed, the surrounding catalog; `feed` answers each entry cut to `FEED_FIELDS`, the six fields a run reads, so a recorded run's FEED records stay small: a new reader of a field adds it there), `preflight_hook` (a plan's largest prompt against the window, `preflight.evaluate`'s words), `Window` (the model's window, read once and only when a model runs), `runtime_kwargs`, `host_root()` (the seam), and the programs a run may pick (`SHIPPED_PROGRAMS` = `defaults/thym/`, `list_programs` project → canon → shipped, `find_program`) | `ModelCoprocessor`, `host_coprocessor()`, `preflight_hook()`, `Window`, `environment()`, `runtime_kwargs()`, `engines()` / `canon_engine()` / `docoes_engine()` / `catalog_engine()`, `PROMPTS`, `host_root()`, `agent_free()`, `SHIPPED_PROGRAMS`, `program_name()` / `list_programs()` / `find_program()`, `route_info()` / `plan_for()` / `route_refusal()` / `asks_said()`, `SIBLING_ENGINES`, `PROMPT_MODULES`, `check_input()` / `ACCEPTS`, `CLOUD_WINDOW` |
| [enough/thym_api.py](../enough/thym_api.py) | ~1145 | HTTP translation for Thym (0.5.0): `build_router(...)` → `GET /api/thym/programs|program|runs|trace`, `POST /api/thym/compile|plan|run`, `POST /api/canon/package|unpack|read`; runs and readings are CanonJobs; outputs land beside the first input all at once (`copy_all`, `land_beside`); `thym_volume` loads `thym:` paths and `.thym` files for `/api/cosm`; export, unpack and the reading's program are generated programs run through the runtime. Since 0.6 a plan or a run takes `route`, `model`, `calls` (`route_of`, `decide`) and every input by name, checked by type; a `folder` output lands as a folder | `build_router()`, `thym_volume()`, `make_plan()`, `asks_refusal()`, `land_beside()`, `list_runs()`, `export_package()`, `unpack_package()`, `reading_program()` / `reading_path()` |
| [enough/thym_tools.py](../enough/thym_tools.py) | ~590 | The readvisor's Thym tools, `thym_check` and `thym_run` (0.5.0) and `thym_moves` (0.6), behind the `macrocosm-oes` skill (`skill_on`); `register()` like `canon_tools`. No lock, no job; a run lands under the Thym root only | `register()`, `run_thym_check()`, `run_thym_run()`, `run_thym_moves()`, `documented()`, `skill_on()`, `SKILL_NAME`, `OUTPUTS_NOTE` |
| [enough/ascribe.py](../enough/ascribe.py) | ~2315 | Ascribe (0.5.0; the `ascribe/1` MiniCOSM), grown in the 0.6 round from a reader into the module: a holograph's own checks beside the generic and the dialectic's — `form-anchored` (never on D), `relation-declared`, `when-shape`, `strength-range`, `no-pii` (a warning inside the holograph, an error at a projection), `private-marker` (a note), `release-shape` — plus `id-module` held to the module folders and `catalog-key` to the hid and handle, each finding with its `advice`; the bank of 44 questions put to the holder alone, answers recorded in the holder's words, settling, form discovery and follow-ups, a reading's candidates, the private filter, releases, the isograph and the allograph (and, as engine functions, the cryptograph and the isomorph; match-token lists are withdrawn), the catalog's `subject`; `python -m enough.ascribe lint <folder> [--json]`. Stdlib + PyYAML + `enough.macrocosm`, `enough.fabula`, `enough.dialectic` (no server, no model). See "Ascribe's module". Spec: [docs/ASCRIBE.md](ASCRIBE.md) | `lint_holograph()`, `report_dict()` / `advice_of()`, `raise_bank()`, `queue()`, `ask_again()`, `record_answers()`, `settle_holograph()`, `answer()`, `follow_ups()`, `candidates()` / `land_candidates()`, `private_filter()`, `releases()` / `append_release()`, `isograph_doc()` / `project_isograph()`, `allograph_doc()` / `project_allograph()` / `allograph_problems()`, `holograph_state()`, `subject_of()` / `set_subject()`, `open_holograph()`, `thym_engine()`, `pii_findings()`, `ASCRIBE_CHECKS`, `PII_PATTERNS`, `AscribeError` |
| [enough/allograph_registry.py](../enough/allograph_registry.py) | ~950 | The Allograph Registry from the holder's side (toward 0.7; Ascribe 14.7 to 14.13): one Ed25519 key per listing in the keychain, tags and proof strings, `ascribe-statement/0` statements signed over canonical JSON, every registry operation behind one network seam (`TRANSPORT`), Connect's device-flow sign-in with the token in the keychain (`KEYCHAIN`; `ENOUGH_KEYCHAIN=memory`, `ENOUGH_CONNECT_URL`), what this machine keeps of a listing (`~/enough/config/allographs.json`) and the "holograph changed" notice. See "Ascribe's module" | `ListingKey`, `listing_key()`, `tag_of()`, `proof_string()`, `statement()`, `sign()`, `verify()`, `say()`, `list_allograph()`, `search()`, `session()`, `start_sign_in()` / `poll_sign_in()` / `sign_out()`, `listing_status()`, `run_state()`, `RegistryError` |
| [enough/allograph_api.py](../enough/allograph_api.py) | ~360 | HTTP translation for the registry (toward 0.7): `/api/connect/status\|sign-in\|poll\|sign-out`, `POST /api/ascribe/subject`, `/api/allograph/listing\|list\|withdraw\|proof\|prove\|unprove\|waiting\|accept\|remove\|attest\|bond\|unbond\|search\|entry\|faceplaces`; each route that sends answers 401 while not signed in | `build_router()` |
| [enough/home.py](../enough/home.py) | ~805 | The home screen (0.2.5): the project **registry** (`~/enough/config/projects.json`, seam `ENOUGH_PROJECTS_STATE`), the ¶/W/C counters ported from the top bar, the fingerprint cache (which since 0.2.8 also snapshots the `rness/project.json` display name/description so an unreachable folder's row keeps its nice name — live reads still win), seeding from the shell's `desktop.json` MRU (temp-dir paths — chiefly the wizard's `$TMPDIR/enough-onboarding` scratch — are refused, skipped, and pruned when the registry is durable, 0.2.8), the project map (via `canon.folder_flowchart`; its skip rule `_mirror_skip` is also what the project catalog enumerates), the add-guards + the osascript folder chooser, and both halves of the open/close handoff. Imports `server` **lazily, inside functions** — `server` imports `home` at module level, and that is the cycle-breaker. | `projects_state_path()` / `config_dir()` / `handoff_path()`, `read_registry()` / `save_registry()` / `register()` / `touch_opened()` / `set_hidden()`, `seed_from_desktop()`, `count_text()` / `fingerprint_of()` / `refresh_entry()` / `list_projects()`, `build_project_mirror()`, `check_addable()` / `add_project()` / `choose_folder()`, `write_handoff()` / `read_handoff()`, `exec_argv()` |
| [enough/logger.py](../enough/logger.py) | small | Stdlib logging setup. | — |
| [enough/static/index.html](../enough/static/index.html) | ~46700 | The entire frontend — HTML, CSS, vanilla JS, htmx. Single file. | model modal, broker modal, OPRO-API wizard + settings, file tree (+ option-click context menu), **the readvisor panel** (`#readvisor-panel`, the third `.layout` column — the conversation lives here now, not in a chat home pane), **the composure canvas** (`#composure` at the base layer: `COMP`, `COMP_TOOLS`, `COMP_MODULE_RENDERERS`, `COMP_FORM_BEHAVIORS`, ~126 `comp*` functions), **the composure base indicator + peek** (`html[data-comp-peek]`), SSE consumer, wikisink setup/installs modal + reader mode, the unified read/edit mode (mini ↔ full frame), girraph mode, merirmaid mode (+ lens entries), Canon split-view mode (`#canon-mode`, `cn*`), **the cosm viewer** (`#cosm-mode`, `COSM`, `cosm*`), **the docs viewer** (`#docs-mode`, `DOCS`, `DOCS_DENSITIES`, `DOCS_FAB`, `docs*` — the help center and the MacroCOSM spec at three densities, 0.4.4; it replaced ref mode and the spec viewer), **agent-free mode** (`AGENT_FREE`, `agentFree*`, the CSS block keyed on `html[data-agent-free]`), **the Canon chip + the fabula's face + atem card + job toasts** (`CANON`, `EMF_FACE`, `canon*`, `emfFace*`, `#atem-modal`, `atemCard*`), since 0.6 **the fabula card, the fabulac's card and the cshort viewer** (`FAB`, `FAB_ROUTE`, `fab*`, `#fabula-modal`, `#cshort-modal`; see "The fabula" → "The UI"), **the dialectic card** (`DLG`, `dlg*`, `#dialectic-modal`) and **Thym's editor strip and Thym at hand** (`THYM_ED`, `thymEd*`, `#thym-ref-modal`, `thymRef*`), the home frame + project map + handoff overlays (gated on `IS_HOME` / `body[data-mode]`), SVG icon pipeline (`data-icon`/`iconSrc`), MODE STACK registry, confirmOverlay, **the shared modal a11y helper** (`MODAL`, `modalSync()`), **the find bar** (`findBarAttach`, `FIND_BARS`), **dictionary mode** (`#dict-mode`, `DICT`, `dict*`), **the word data lightbox** (`#wdl-modal`, `WDL`, `wdl*`) and the **"dictionary entry" menu** (`#dict-ctx-menu`). **The five per-mode chat pills are gone** (review / edit / merirmaid / wiki / cacheawl, as Canon was then called) — there is one composer now, `#message` in the panel |

`defaults/` ships templates that get copied or symlinked into project
skeletons by `skeleton.py`:

- `defaults/AGENT.md`, `defaults/MOTIVATION.md` — root identity files (copied)
- `defaults/skills/<name>/SKILL.md` — bundled skills (symlinked)
- `defaults/paradigms/<name>.md` — bundled paradigms (symlinked);
  `text-planning` is the home one (`prompt.HOME_PARADIGM`); `default` was
  retired in 0.4.1
- `defaults/intro.md` — the brief introduction (0.4.1). Read in place from
  the install, never copied into a project: an edit reaches every project
- `defaults/readvisors/<name>/` — bundled readvisors, `AGENT.md` +
  `MOTIVATION.md` each (symlinked). Renamed from `defaults/roles/` in 0.3.5.
  They are not consultants you report from — every switched-on readvisor is
  part of one voice (see "Readvisors")
- `defaults/composure-forms/*.comp` — the five shipped composure forms
  (`blank` `cards` `scaffold` `journal` `council`). **Generated**, not
  hand-written — `scripts/gen_composure_forms.py` (`--check` verifies)
- `defaults/policies/*.md` — operating policies (symlinked)
- `defaults/cosm/manifests/*.manifest.cosm` — the seven format manifests
  the MacroCOSM reader loads (0.4.3; `doc` joined in 0.4.4, `ascribe` and
  `thym` in 0.5.0; in the 0.6 round `fabula` replaced `emf`): the core's
  five built-ins (`cosm`, `canon`, `fabula`, `doc`, `thym`, each saying
  `core: true`) and the two MiniCOSMs (`comprise`, `ascribe`). Read in place
  from the install, never copied into a project. Beside them,
  `core.modules.cosm` (0.6): the core's module D, the dialectic, which the
  registry gives every format that does not declare D itself (not a
  manifest; the registry glob skips it). `comprise.manifest.cosm` is synced
  from comprise-dev and never edited here, so Comprise's Thym moves live in
  the sidecar `comprise.moves.cosm` beside it (not a manifest either).
  `fabula`, `doc`, `thym` and `ascribe` carry their own `moves:` blocks.
  `defaults/cosm/NOTICE.md`: all rights reserved, not Apache (see
  "MacroCOSM" and "License")
- `docs/specs.json` (0.5.4) — the registry of the four bundled OES specifications as cosmoes-site
  publishes them (slug, name, edition, describes, host, revised; plus the bundled
  path and sha256 of each copy), the vendored client's source, commit and sha256,
  the cosmoes-site commit and the sync date. Written only by
  `scripts/sync_specs.py --cosmoes <checkout>`; read by `docoes.bundled_editions()`.
  The texts themselves — `docs/MACROCOSM_OES.md`, `docs/THYM.md`, `docs/ASCRIBE.md`,
  `docs/COMPRISE_OES.md` — are cosmoes-site's `specs/*.md` byte for byte: edited only
  there, never here (`tests/test_sync_specs.py` pins the hashes). The
  `defaults/cosm/chapters/` folder of 0.4.4–0.5.1 (Comprise's texts as chapters of
  the MacroCOSM volume) is gone: Comprise OES is a document of its own
- `defaults/thym/*.thym` — the nine programs shipped with enough. The three
  `thym 0` programs of 0.5.0, `publish-story`, `read-my-way`, `open-house`,
  are byte for byte the conformance suite's `tests/fixtures/thym/programs/`
  (`tests/test_thym_host.py` pins the equality); the six `thym 1` files of
  the 0.6 round, `decompile-python` (five programs, the fabulac build's
  stages), `compile-python`, `decompile-prose`, `decompile-verse`, `settle`
  and `tighten`, are each a ```` ```thym ```` block of `docs/THYM.md` byte for
  byte (`tests/test_thym_shipped.py`). Read in place, never copied; listed
  last by `run with…`
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
| [desktop/src-tauri/build.rs](../desktop/src-tauri/build.rs) | stages the source snapshot (pyproject, uv.lock, `enough/`, `defaults/`, licenses, `docs/HELP_CENTER.md` — the single file, so gitignored plan docs never ship; without it the .app's help center 404'd pre-0.2.8 — since 0.4.3 `docs/MACROCOSM_OES.md` beside it, which DocOES enumerates for the docs viewer (0.4.4), and, since 0.4.1, `reflib/dict`, FEED's ~380 MB text form: that subfolder only, not `reflib/`) into the bundle on every `cargo build`; since 0.2.7 also stages `enough/static/enough-loader_1-2.svg` into `desktop/ui/` (gitignored there) so the loading screen can show it |
| [desktop/ui/loading.html](../desktop/ui/loading.html) | the shell's own page; static, zero Tauri IPC exposed to the enough UI. Since 0.2.7 it shows the real loader graphic (mascot + wordmark, the same SVG `enough/static/loader.html` uses) instead of the wordmark set in type |
| [desktop/ui/onboarding.html](../desktop/ui/onboarding.html) | the first-run wizard: welcome → environment → models → extras. Drives the *existing* `/api/models*` endpoints through the Rust proxy; shares nothing with `index.html` |
| [desktop/src-tauri/tauri.conf.json](../desktop/src-tauri/tauri.conf.json) | `bundle.macOS.dmg` (0.4.1): a 660x400 window, enough.app at (180,170), Applications at (480,170), and a plain background PNG (`desktop/src-tauri/dmg/background.png`) — the background is what makes the bundler park hidden items off-window. [scripts/check_dmg_layout.py](../scripts/check_dmg_layout.py) `PATH.dmg` mounts a built image read-only, decodes its `.DS_Store` (stdlib only) and fails on a wrong position, a wrong window size, or any dotfile with an icon slot inside the window — the 0.4.0 DMG, built while Finder showed hidden files, gave `.VolumeIcon.icns` a slot and shoved both real icons |
| [desktop/fetch-sidecars.sh](../desktop/fetch-sidecars.sh) | checksum-pinned fetch of the `uv` and `llama.cpp` release binaries (they are gitignored, not vendored) |
| [desktop/RELEASE.md](../desktop/RELEASE.md) | the user-executed release checklist: sync the dictionary before the bump (and, since 0.5.4, sync the four OES specifications and the client from a cosmoes-site checkout with `scripts/sync_specs.py --check`), the Developer ID certificate (must be **G2**-issued; the original CA expires 2027-02-01), sign / notarize / staple / verify, the Finder hidden-files note for the DMG step, and `scripts/check_dmg_layout.py` (all 0.4.1 additions). The source of truth — reference it, don't restate it |

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
uv run python scripts/smoke_boot.py     # ~1.5s, 22 checks
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
  when you need a scratch server of your own. Since 0.7 the seams it and
  `tests/conftest.py` export are one list, [enough/seams.py](../enough/seams.py)
  (path seams under the scratch root, fixed ones on a dead loopback port,
  behaviour seams cleared); `tests/test_seams.py` fails when a module under
  `enough/` reads an `ENOUGH_*` variable the list does not name, so a new
  variable arrives with its seam. conftest's `session_floor` points `$HOME`
  and every seam at a session scratch folder before any fixture of any scope
  runs; the per-test seams sit on top of it.
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
   Right after it (0.4.1), **the brief introduction**: a whole-message
   match (`intro.is_intro_request`) is answered on the spot with the
   user's bubble plus the chief's intro bubble and **no model turn** —
   history and session log still get both. See "The readvisor panel".
1. **The `/pal` prefix, second** (0.4.0). `pal_tools.strip_command()` returns
   `None` for an ordinary message and otherwise the message with the token
   removed (`""` for a bare `/pal`). Four outcomes, and only one of them
   starts a pal turn, in this order: **gate shut** (`cloud.gate_status()`) →
   user bubble + a system bubble carrying the full `broker.denial_*` copy,
   **no turn at all**; **nothing after `/pal`** → user bubble +
   `pal_tools.USAGE_HINT`, no turn; **the active model is already
   `opro-api`** → `pal_tools.ALREADY_CLOUD_NOTE` as a system bubble plus an
   ordinary turn on the stripped text (`pal=False` — there is no pal to be a
   pal to); otherwise an ordinary-looking turn on the stripped text with
   `pal=True`. The gate is checked before the empty case on purpose: a user
   whose cloud is off should learn that from a bare `/pal` too. `_run_turn`
   is then called as `_run_turn(session, stripped, pal=…, log_user=typed)` —
   **what was typed and what was sent differ**, and the user's bubble, the
   history and the session log all keep the typed line.
2. The handler appends `{role: "user", content: ...}` to `session.history`
   and emits the bubble via SSE. The `turn_start` SSE event carries
   **`{"speaker": "<chief readvisor name>"}`** (`prompt.chief_name()`,
   read live) — the live bubble's byline comes from there, and the history
   renderer (`_render_turn_from_history`) uses the same value. The byline
   is always the *current* name, never the name at the time of the turn:
   one voice, one name, or a rename reads as two people.
3. `_drive_message` (in [server.py](../enough/server.py)) starts the tool
   loop, capped at `session.max_tool_iters` iterations.
4. On each iteration:
   - `assemble_system_prompt(project_dir)` rebuilds the system prompt
     **from disk** — a generated **identity preface**, `rness/AGENT.md`,
     `rness/MOTIVATION.md`, the project description + profile, the active
     readvisors, the active paradigm, policies, active skills, the tool
     instructions, the paradigm catalog. No caching; edits to any of these
     files land on the next message. Section order is: identity preface →
     Identity → Motivation → [Project Description] → [Project Profile] →
     [Active Readvisors] → Paradigm → [Paradigm Catalog] → [Policies] →
     [Skills] → [Current Intention] → Tools → Converted documents →
     Context → [Available Updates] → **[This turn]** (a pal turn only —
     `PAL_TURN_INSTRUCTION`, last, so it is never in `session.history` and
     never reads back as words the user typed).
   - **The preface is generated, not shipped** (`prompt.identity_preface()`,
     template `_IDENTITY_PREFACE_TMPL`). It has to be: `rness/AGENT.md` is a
     *copy* the user owns, so nothing written into `defaults/AGENT.md` ever
     reaches an existing project. It names the chief readvisor and states
     the two standing rules — **"enough acts; readvisors speak"** (tool
     effects are narrated as things *enough* did) and **"you are one voice,
     sometimes made of several"** (switched-on readvisors are part of who
     the chief is this turn, not a panel to report from).
   - **The tool docs are gated**
     (`prompt.tool_instructions(project_dir, pal=False)`): the always-on
     `TOOL_INSTRUCTIONS` core, plus `COMPOSURE_TOOL_INSTRUCTIONS` when
     `broker.is_enabled("composure_enabled")`, plus
     `READVISORY_TOOL_INSTRUCTIONS` when the `readvisory` skill is switched
     on in this project, plus `DICTIONARY_TOOL_INSTRUCTIONS` whenever FEED
     ships with the install (`dictionary.available()` — a manifest and a
     schema in the source dir, built or not), plus `CANON_TOOL_INSTRUCTIONS`
     (the "## MacroCOSM" block, 0.4.3) whenever the format manifests ship
     (`prompt._macrocosm_available()` — `fabula.manifest.cosm` in
     `macrocosm.DEFAULT_MANIFEST_DIR`, i.e. every project of every install;
     the `macrocosm-oes` skill does not gate it) and right after it, since
     0.6, `FABULA_TOOL_INSTRUCTIONS` ("## Dialectic and fabulacs", 539
     chars: the `dialectic` and `fabulac` tools) **when the `macrocosm-oes`
     skill is on in the project**, else `FABULA_ABSENT_INSTRUCTIONS` (one
     61-char line naming the two tools and the skill they come with), plus
     `PAL_TOOL_INSTRUCTIONS` when `pal=True`. Since 0.5.1 the girraph,
     review, wiki, cloud, canon-store and keep-going sections are blocks of
     their own too (see "Models" → the lean profile); the whole order is
     core → girraphs → review → wiki → cloud → canon store → keep going →
     composures → readvisors → dictionary → macrocosm (+ fabula) → pal. The
     first two gates **fail open** — an unreadable broker config leaves the
     composure block in, because a gate that hid working tools would be
     worse than a gate that costs a kilobyte. A project using neither pays
     what it paid before the composure round. **The pal gate is the narrow
     one**: the other two are switched on for a project and stay on, while
     the pal block rides on the single turn the user opened with `/pal`, so
     `ask_pal` costs an ordinary turn nothing.
     `tests/test_prompt_weight.py` pins the budgets — `CORE_BUDGET` 4 000
     chars, the always-on core plus the dictionary block (17 500 until
     0.5.1 moved the long sections out of the core; the core measures
     ~3 100 now); `FULL_BUDGET` 24 500, every gated block an ordinary turn
     can carry, every gate open; `LEAN_BUDGET` 22 500, a fresh project's
     whole lean prompt (what an 8,192-token window holds with the 2,048
     reserve); the MacroCOSM block (995 chars against the owner's
     `CANON_BLOCK_MAX` 1 000, its own test) rides outside `CORE_BUDGET`,
     bounded instead by
     `test_the_default_prompt_grows_by_at_most_the_canon_block`, which pins a
     fresh project's whole assembled prompt against HEAD
     (`HEAD_DEFAULT_PROMPT` = 74 307 chars, measured on 0.4.2); `PAL_BUDGET`
     1 200 for the pal block by itself — **and both directions of the coverage
     question**: every name in `tools._DISPATCH` is documented somewhere in
     `fully_enabled(project) + tool_instructions(pal=True)`, every
     `<tool name="x">` example names something dispatchable, no `<tool`
     example lacks its `name="..."`, and every example block round-trips
     through `tools.parse_tool_calls` — a tool is documented if the turn
     that can call it says so, not if every turn does. `FULL_BUDGET`
     measures what an **ordinary** turn can carry, and the pal block is not
     in it. A block that grows past its budget fails the test, so the next
     round that adds a tool raises a number on purpose. **The fabula block
     (0.6) is the skill's, not the install's**: a fresh project (every
     shipped skill off) pays its 61-char absent line and nothing more, and
     `test_the_canon_block_rides_on_the_install_not_the_skill` pins that
     switching the skill on swaps exactly that line for the 539-char block.
     It is not always on because the lean budget had about a hundred
     characters left, and three shipped 8k windows stopped holding the lean
     prompt with it.
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
5. Mid-loop pressure check: after each tool result, if pressure ≥
   `orchestrator.json`'s threshold, either auto-reset (write a
   continuation checkpoint to the active request file → wipe history →
   resume) or pause with a banner — depending on the orchestrator
   toggle.
6. **A context overflow** (0.4.3). When llama-server refuses a request
   before streaming (`LLMError`) and the detail looks like an overflow,
   `_run_turn` asks `_first_turn_overflow(session, system_prompt, detail)`.
   On **a first turn** — no assistant reply in `session.history` yet; a
   failed first try leaves only user messages, so a retry still counts — or
   on any turn whose **instructions alone leave no room** (prompt + 2,048 >
   window), the "things to try" list is replaced by
   `preflight.first_turn_advice`: both numbers, then the model window
   (or "send it in shorter parts" when the instructions fit and the message
   is what's too long). N comes from one `/tokenize` with a 5 s timeout,
   falling back to chars / 3.7 worded "about N"; M from the 400 itself
   (`n_ctx_from_error`: JSON `error.n_ctx`, or the message), then the
   preflight, then the supervisor. Only this branch sends the `error` SSE
   event with **`kind: "ctx_overflow"`**, which puts the context notice
   under the error. **Never suggest `/reset` or disabling skills there** —
   neither can help a prompt that is too big on its own. Later-turn
   overflows keep the old advice and send no `kind`. The text is English,
   like every backend error string. The preflight (see "Models") has
   usually said all this in the empty conversation already; it never gates
   `/api/chat`.

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
| Council outputs | `answer` → the ink-tinted conclusion module, no file; `document` → whatever `output.path` names, through `tools.run_write_file`; `composure` → `rness/io/composure/<council-slug>-output-<YYYY-MM-DD>.comp`, written whole at `rev 1` and linked back | none | no |
| Policies | `rness/policies/*.md` (symlink) | `defaults/policies/*.md` | yes, all of them |
| Project profile | `rness/knowledge/project-profile.md` | seeded empty | yes |
| Requests | `rness/requests/*.md` | none — a readvisor creates them | no (but readvisors read on demand) |
| Highlights | `<dirname>/.<filename>.highlights.json` | none | no — read via tools |
| Session logs | `rness/knowledge/session-logs/<date>.md` | none | no |
| Broker journal | `rness/knowledge/session-logs/<date>-broker.md` | none | no |
| Fetched web cache | `rness/io/input/<timestamp>-<hash>-<slug>.md` | none | no |
| Cloud cache | `rness/io/cloud-cache/<timestamp>-<slug>.md` + `_cloud-index.md` | none | no |
| Saved wiki articles | `<project>/wiki/<slug>/` or `~/enough/canon/wiki/<slug>/` (the global `wiki` volume; save dest `"canon"`, with `"infoworld"` accepted as a legacy alias; `"cacheawl"` was until 0.6) — folder of `article.html` (verbatim archive copy) + `_manifest.md` + hidden `.meta.json` | none — created on first save | no (readvisors read on demand) |
| Canon volumes | `~/enough/canon/<volume>/…` — root-level folders, each with a backend-owned `canon.cosm` catalog (visible, write-refused) + hidden `.canon.json` meta | none — created via UI/readvisor/migration | no (readvisors reach it via the `canon_*` tools, and read catalogs with `cosm_read`) |
| The project catalog | `rness/canon.cosm` (`scope: project`, structure only) | none — written by `canon.project_catalog()` | no (`cosm_read rness/canon.cosm`) |
| Fabula twins and atems | `<dir>/<text>.fabulan.cosm` or `.fabulap.cosm` beside `<text>` (`notes.md` ↔ `notes.md.fabulan.cosm`; the old `notes.md.cosm` reads forever and is replaced only when the text is decompiled again), hidden behind it in both trees; atems live inside it; a compile writes a short, a new visible `<stem>.short-<YYYY-MM-DD-HHMM>.md` beside the text, and appends it to the twin's `shorts:` list | none — written only on request (a click or a tool call) | no (`cosm_read`, `fabula_derive`, `atem`) |
| Fabulacs, cshorts, catems (0.6) | `<dir>/<folder>.fabulac.cosm` beside a folder of Python; `<name>.cshort-<YYYY-MM-DD-HHMM>/` (the rebuilt tree + `CSHORT.md`) and `<name>.catem-<YYYY-MM-DD-HHMM>.md` beside the fabulac | none — written by a build or a compile job | no (`fabulac` tool; `cosm_read` reads the fabulac) |
| Dialectic answers (0.6) | the volume's own module D (`D:question/…`, `D:session/…`); a sitting beside a single-file volume as `<name without .cosm>.answers-<YYYY-MM-DD-HHMM>.cosm` until it is settled; a holograph's in its `D/` folder | the format's bank (its manifest's `dialectic:` key) | no (`dialectic` tool) |
| Format manifests | — (install-wide) | `defaults/cosm/manifests/*.manifest.cosm` + `core.modules.cosm` | only `CANON_TOOL_INSTRUCTIONS`; the `macrocosm-oes` skill when on |
| Thym programs | `<anywhere>/<name>.thym` (the file is the truth; `<name>.thym.cosm` only when enumerated on request) | `defaults/thym/*.thym` (the shipped programs, read in place) | no — `thym_check`/`thym_run`/`thym_moves` read them on demand |
| Thym runs | `~/enough/thym/runs/<run-id>/` (plan, trace, candidates, outputs; seam `ENOUGH_THYM_ROOT`); a run with… copies its outputs beside the first input (`<stem>.<gives>.<ext>`) | none — written by `thym.run` | no |
| Packages and readings | `<dir>/<stem>.thym/` + `<stem>.package.cosm` (+ `<stem>.thym.enc` sealed) beside the text; `<dir>/<stem>.read-<morph>-YYYY-MM-DD-HHMM.md` | none — written by the runtime | no |
| Holographs | `<anywhere>/<folder>/holograph.cosm` + module folders; since 0.6 enough writes into one only at the holder's act (answers to the bank, settling, a reading's candidates the holder keeps, the record of a release) and writes an isograph beside it, `<holograph>.isograph-<epoch>.json`, and an allograph, `<holograph>.allograph-<run>.json` (0.7) | none | no (`dialectic`, `cosm_read`) |
| Wikisink registry/state | `~/enough/config/wikisink.json` (user-global, **not** per-project) | none | no |
| Wiki comments/overlays | `<wikisink data dir>/comments/`, `overlay/`, `preserved/` | none | no |
| FEED (the dictionary) | — (install-wide) | `reflib/dict/` (shipped text form) → `~/enough/dict/feed.sqlite` (built) | only `DICTIONARY_TOOL_INSTRUCTIONS`; entries are read through `dict_lookup` |
| The user's own dictionary | — (machine-global) `~/enough/dict/user-dictionary.sqlite` | created from `reflib/dict/schema.sql` on the first write | no — read through `dict_lookup`, where a user row wins |
| The brief introduction | — | `defaults/intro.md` (+ `static/i18n/<lang>/intro.md`) | no — `show_intro` documents it; the text goes on screen, not into the prompt |
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

### Context windows: defaults, small-machine caps, the preflight (0.4.3)

A fresh project's default system prompt is ~75k chars, ≈ 20k tokens on
every shipped tokenizer (docs/ctx-16gb-plan.md §1, gitignored), so a window
under ~22k cannot hold even a first message. Before 0.4.3 that surfaced as
llama-server's 400 on turn one at the whole 16–31 GB tier's defaults. Three
pieces answer it; none changes prompt text.

- **Defaults.** `recommend_ctx(entry, ram_gb)` picks the entry's
  `ctx_defaults` tier (`gte_64gb` / `gte_32gb` / `gte_16gb` / `lt_16gb`); a
  `ctx_overrides` entry in live state wins. 0.4.3 raised `gte_16gb` G40-04
  16,384 → 32,768 and G40-12 8,192 → 32,768 (G40-04 pays ~+256 MiB of KV;
  G40-12 is "tight" on 16 GB and fine with the caps below). G40-26 stays
  8,192 on purpose: 16k still can't hold the full prompt, so raising it
  costs memory for nothing until the prompt shrinks. An install whose user
  picked a window by hand keeps it — that is what the preflight is for.
- **`feasibility(entry, ctx=None)`.** With `ctx`, a window larger than
  `recommend_ctx(entry, this machine's RAM)` is a RAM "no" with a reason:
  the tiers *are* the measured memory story, so a window no tier ships here
  is one this machine is not promised. The result also carries the per-axis
  verdicts `ram` and `disk` (additive; callers without `ctx` see no change).
- **Launch caps under 32 GB.** llama-server's own defaults keep up to 32
  SWA/recurrent context checkpoints per slot (480 MiB each on G40-12, in
  host RAM — on a 16 GB machine these, not the KV, are the threat) and an
  8 GiB prompt cache. Below `CAP_RAM_GB` (32),
  `launch_caps(binary, ram_gb=None) -> (argv, note)` returns `LAUNCH_CAPS`
  (`--ctx-checkpoints 2 --cache-ram 2048`), **each flag only when this
  binary's `--help` lists it**, matched as a whole word so
  `--swa-checkpoints` or a look-alike never stands in — an older Homebrew
  llama.cpp still starts. The probe is `llama_server_flags(binary)`: every
  long flag `--help` prints, cached per (path, `st_mtime_ns`, `st_size`), so
  a `brew upgrade` re-probes and a model switch does not; a missing or
  broken binary lists nothing, and a failure is never cached. At 32 GB and
  up nothing is probed at all. `supervisor._launch` appends the argv,
  `log.info`s the note **and** writes `[enough] <note>` at the head of this
  launch's part of `~/enough/.llama-server/server.log` — nothing configures
  logging for the `enough.*` INFO lines, so server.log is where someone
  debugging memory actually looks. `llama_server.sh` applies the same rule
  in shell (`total_ram_gb`, `help_lists_flag`, `resolve_cap_flags`; prints
  `  caps:  …`; the bash-3.2-safe empty-array idiom). Deliberately absent:
  KV quantization (quality untested) and `--swa-checkpoints` as an alias
  (its semantics on old builds were never verified).

**The diet and the lean profile (0.5.1, plan §4b–4c).** Two kinds of cut:

- *In every profile, no behaviour change.* The `cloud_pipeline` example and
  rule ride only through an open cloud gate (`prompt._cloud_usable()` →
  `cloud.gate_status()`); the wiki block only with an installed archive
  (`_wiki_installed()` → `wikisink.config.installed()`), a four-line
  `WIKI_ABSENT_INSTRUCTIONS` naming the wiki tools otherwise; the paradigm
  lost its restatements of the highlight, security and fetching rules and
  its quick-reference table (the two fetching rules it alone stated moved
  to `allowlists.md`'s notes); `defaults/AGENT.md` lost its file-conventions
  recap of the Context block. The core `TOOL_INSTRUCTIONS` is now the
  preamble, the examples and the rules (~3.3k chars); the girraph, review,
  wiki, cloud, canon-store and keep-going sections are blocks of their own,
  assembled in the old order by `tool_instructions()`. A fresh project's
  chat prompt went 19,990 → ~18,100 gemma tokens.
- *The `lean` profile* — `assemble_system_prompt(profile="lean")`, ~6.0k
  gemma tokens (22.4k chars) for a fresh project: the policies as an index
  (`_load_policies(lean=True)`: two hard rules — the allowlists, the request
  file and `/reset` — then one line per file, its first paragraph as the
  trigger, user policies included), the paradigm cut at its
  `LEAN_CUT` marker (`<!-- lean-cut -->`; `text-planning.md` keeps home
  base, routing, posture and "Planning, in brief" above it, the full flow,
  skeleton and scaffold mode below; a paradigm without the marker rides
  whole), the composure / girraph / review / wiki / canon / cloud / twins /
  keep-going sections as `*_LEAN_INSTRUCTIONS` summaries each marked
  *(guide: X)*, the girraph summary only with a `.girraph` in the project
  (`_girraph_present`, three levels, skipping `rness/`) or the skill on —
  `GIRRAPH_ABSENT_LEAN_INSTRUCTIONS`, two lines, otherwise, so a map can
  still be started by name — and `HARNESS_CONTEXT_LEAN_TMPL` for the
  Context section. The **`harness_guide`**
  tool (`<topic>` composures | girraphs | review | wikisink | canon | cloud |
  twins; `tools.run_harness_guide`, `prompt.harness_guides()`) hands the full
  text back on demand — no file, no gate, exactly what the chat prompt would
  have said. It is documented in the core, so the chat profile knows it too.
- *The rule.* `lean_wanted(tokens, n_ctx)`: lean when the full prompt would
  take more than `LEAN_SHARE` (half) of the window. `_run_turn` applies it
  per turn through `assemble_for_window(project_dir, n_ctx, pal=)` (chars /
  `CHARS_PER_TOKEN` = 3.7, the fit test's estimator) and records the choice
  on `session.prompt_profile`; `/api/llm-status` reports it as
  `prompt_profile` beside the preflight's own `profile`. The preflight gets
  a second builder, `build_lean_prompt`, and when the exact full count wants
  lean it tokenizes the lean prompt instead and reports that — so the
  empty-conversation notice measures what the turn will send. Effect at the
  shipped defaults: lean at 8k, 16k and 32k, full at 64k and up; every
  8,192 window now holds the prompt with the reserve, which emptied
  `KNOWN_TOO_SMALL` down to G40-12 under 16 GB (4,096). A council turn is
  unaffected (its own profile); a `/pal` turn may be lean.
  **Measured:** the plan's behaviour eval (§5) ran twice on E4B
  (`docs/ctx16-eval/eval.py`, 16 scripted prompts, one reply each, scored
  on whether the first reply reaches for the right file, guide or tool;
  results in plan §10): round 2 chat 14/16 at 32k, lean 12/16 at 32k and
  14/16 at 8k — where the full prompt cannot start at all. Round 1 found
  two defects the texts now fix: the full prompt ran `rm` on a delete
  request because tier 1 had cut the paradigm's only "never delete without
  confirmation" rule as a duplicate (it is in `allowlists.md`'s notes now),
  and lean did not know girraphs existed in a fresh project. Lean's
  remaining misses: scaffolding without reading the plan (chat too), a
  research job without a request file. Not confirmed on real 16 / 24 GB
  hardware.

**The preflight** ([enough/preflight.py](../enough/preflight.py)) asks the
live model, before anyone types, whether enough's instructions fit:

- **What it measures.** `Preflight.run()` builds the prompt in a thread
  with the server's own `assemble_system_prompt(project_dir)` — the default
  `chat` profile, no pal block: the exact call `_run_turn` makes, never a
  fork of it — counts it with `POST /tokenize {content, with_pieces: false}`
  (exact, no BOS), reads the per-slot window from `GET /props` →
  `default_generation_settings.n_ctx`, and calls `evaluate()`. It fits when
  `prompt_tokens + RESERVE ≤ n_ctx`, `RESERVE = 2048` (a first message plus
  a thinking reply).
- **The verdict.** When it doesn't fit, `suggest_ctx` is the smallest of
  `WINDOWS` (32,768 / 65,536 / 131,072) that holds prompt + reserve and is
  ≤ the entry's `ctx_max`. `fix: "switch"` only when enough supervises a
  model the registry can name **and** the RAM axis of
  `feasibility(entry, ctx=suggest_ctx)` is above "no". Otherwise
  `fix: "none"` and a `fix_reason`, checked most fundamental first:
  `no_window`, then `unsupervised` (no supervisor, or a model enough can't
  name), then `memory`. At 16–31 GB that gives G40-04, Q35-09 and G40-12
  the button and G40-26, Q36-27 and Q38-04 `memory`; under 16 GB every
  model that runs there gets `memory`; at 32 GB and up, the button for a
  32k window.
- **When it runs.** `schedule(reason)` never awaits and is the only
  trigger: `"ready"` from `LlamaSupervisor.on_ready` (fired by
  `_notify_ready` each time `/health` turns 200 after a launch, an adopt or
  a switch; a raising callback is logged and swallowed), `"open"` at
  startup when nothing is supervised, `"page"` on every `GET /`, `"reset"`
  on `/api/reset` (so the empty state judges the prompt as it is now), and
  `"cloud"` when OPRO-API is chosen. It skips a supervised model that isn't
  ready yet (its `on_ready` calls again) and folds calls that land during a
  run into one rerun. `/api/model` calls `invalidate()` before
  `supervisor.switch`; a refused or failed switch re-measures the old
  model. `Session.preflight` is None in home mode and is cancelled at
  shutdown.
- **It never gates anything.** A failure — the model still loading, an old
  build without `/tokenize`, the 10 s timeout, a prompt that won't build —
  leaves the verdict unknown (`fits: null`, state `failed`). Cloud mode is
  `skipped` without a single request: the cloud's window is not ours to
  measure. A verdict measured against a model or window that is no longer
  live (the supervisor's `(current_cute, current_ctx)` moved) reads as
  unknown, and a run a switch overtook throws its result away.
- **`/api/llm-status`** carries it on all three shapes (supervised,
  `external`, `cloud`), additively — nothing was renamed: `prompt_tokens`
  (exact, or null), `n_ctx` (the live per-slot window, or null), `reserve`
  (always 2048), `fits` (**null = unknown**: not measured, failed, stale,
  cloud), `suggest_ctx`, `fix` (`"switch"` | `"none"` | null), `fix_reason`
  (a code; the page words it) and `preflight` (`idle` | `pending` | `done`
  | `failed` | `skipped`).
- **The page.** `ctxNoticePaint` (index.html) keeps one `.ctx-notice` at
  the top of whatever `#empty-hint` shows, true to `LLM_STATUS`, plus any
  `.ctx-notice--turn` under a `ctx_overflow` error (see "The request
  lifecycle"); `pollLoop` polls at 2 s while `preflight === 'pending'`, and
  a `MutationObserver` on `#conversation` repaints each new empty state.
  The button (`ctxNoticeSwitch`) POSTs `/api/model {cute, ctx: suggest_ctx}`
  — the model window's own request, so the window persists as that model's
  `ctx_overrides` entry and the conversation clears — then polls
  `/api/llm-status` until the model is ready, as `applyModel` does. With
  `fix: "none"` the notice words the reason and, except for `unsupervised`
  (the model window can't switch a server enough doesn't run), offers
  `openModelModal()`. Strings are the `chat.ctx.*` family (11 keys).
  **No memory figure** is shown on the button: nothing cheap at runtime
  carries KV geometry, and the plan's figures came from GGUF metadata and
  `llama_kv_cache` log lines that are architecture-specific and change
  between llama.cpp releases. uicheck screens: `readvisor-ctx-notice` (the
  button) and `readvisor-ctx-notice-none` (the `memory` reason); with no
  model in the scratch world they wrap `window.fetch` for
  `/api/llm-status` only, so the product's own `refreshLlmStatus()` paints
  and there is no production-only hook.
- **The fit test, and why its allowlist only shrinks.**
  `tests/test_prompt_weight.py` now pins fit as well as weight:
  `test_every_shipped_window_holds_the_default_prompt` requires every
  model × RAM-tier pair the model runs in (its RAM minimum below the tier's
  top) to ship `ctx_default ≥ tokens + 2,048`, tokens = chars / 3.7 of a
  fresh project's prompt (with a 130-char project path). The exceptions are
  `KNOWN_TOO_SMALL` — since 0.5.1 one pair, G40-12 on `lt_16gb` (4,096;
  the lean profile fits every 8,192 window, and the test measures the
  profile a window would get) — each with its reason. Each is a
  machine where a chat cannot open at the shipped default, so the list is
  debt, not configuration: the test fails on a new short pair **and** on a
  listed pair that fits now, so whichever change makes a pair fit (a leaner
  prompt, a raised tier) deletes it in the same commit. Companions check
  that every listed pair is a real pair and that
  `CTX_RESERVE == preflight.RESERVE`. The rest is covered by
  `tests/test_preflight.py` (a fake llama-server over
  `httpx.MockTransport`, the shipped registry, two end-to-end `_run_turn`
  overflow tests) and `tests/test_launch_caps.py` (a stand-in llama-server
  whose `--help` is scripted, plus three real runs of `llama_server.sh`
  under `/bin/bash` 3.2 with a fake `sysctl` and `curl`). A suite that
  records every `Popen` around a launch (`test_models_registry.py`'s
  `launcher` fixture, `test_llama_server_lookup.py`) pins `total_ram_gb` to
  64 — otherwise, on a small CI runner, the RAM probe and the `--help` probe
  land in the recorded argv.

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

### A model route per job (0.6)

The chat's slot decides the chat. Since the 0.6 round **a job that asks a
model names its own route** — `local` (llama-server, the one local slot) or
`cloud` (the cloud slot's provider, through the broker's gate) — and the
slot does not decide it (pins P6; THYM 23). One factory builds every such
job's model: [model_route.py](../enough/model_route.py)
`make_complete(route, *, model=, llm_url=, project_dir=, source=)` →
`complete(messages, **kw) -> (text, meta)`.

- **Local** calls `llm.complete_local` (llama-server only, whatever the
  chat's slot). `meta.model` is the id llama-server reports, which is the
  cute name since the supervisor launches it with `--alias`.
- **Cloud** asks `cloud.gate_status()` first: a shut gate raises
  `RouteRefused` with the gate's own `denial` (for example
  `broker.denial_local_models_only()`), no request is made, nothing is
  cached or journalled, and **there is never a fall back to local**. An
  open gate sends `cloud.chat_completion` (the job's `model`, else the
  configured one), caches the answer with the job's own `source` (`fabula`,
  `atem`, `compile`, `thym`), and writes one broker-journal entry (tool
  `model_route`; the job, provider, model and token counts — never the
  prompt or the answer). `meta` carries `route`, `provider` (`openrouter`),
  the provider's resolved `model` id and `usage`.
- **Agent-free** refuses both routes (`RouteRefused`, `"agent-free"`).
- **The lock.** `holds_generation_lock(route)`: a local job holds
  `session.generation_lock` (llama-server has one slot); a cloud job does
  not, so a cloud build runs beside a chat turn.
- **The record.** What a job writes says which model made it: a fabula's
  `derived.route` / `provider` / `model`, each entry of `derived.runs`, a
  short's `shorts[].route`, a Thym candidate's `route` / `provider` beside
  `engine: model:<id>`, and the job snapshot's `route` (`null` in rules
  mode).

**Where the route comes from, and the default.** A Thym plan or run, a
fabulac build or compile and a settle take `route` (`local`, `cloud`,
`cloud:<model id>`), `model` and `calls` in the request, `--model
local|cloud|cloud:<id>` and `--calls N` on `python -m enough.thym`, and
`<model>` (and `<calls>` for `thym_run`) in a tool call; **their default is
`local`**. A text's derivation, atem or short compile takes `route` too
(`_body_route`; `fabula_derive` and `atem` take `<route>`), and since lane
S2 **no route is `local` there as well**: `_body_route`, `_canon_mode`,
`_job_complete`, `_model_complete` (handed to Thym's, the fabulac's and the
dialectic's routers, so Thym's reading is local too), `_job_route` and
`canon_tools.model` / `_said_route` all read a missing route as `local`; on
the cloud slot a local job asks llama-server's `/health`
(`_local_reachable`) and runs by rules when it does not answer. Nothing
follows the chat's slot any more (`docs/fabula-landed-S2.md` has the table).
The page always says the route: `local` unless the person chose the cloud on
the card (see "The fabula" → "The UI").

**The plan's models line (THYM 23.2).** A plan that asks a model is planned
again with the route's reading (`thym_host.route_info`: llama-server's id
and window for local; the gate, model, provider and `CLOUD_WINDOW` =
32,768 for cloud) and carries `models: {route, provider, model, calls,
at_most, calls_open, window}`; `cli.models_line` says it in one line ("3
model calls, at most 9, on this machine (g40-04)", "… on the cloud
(openrouter: <model id>)", "; and more that cannot be counted before it
runs (…)"), and the CLI, `/api/thym/plan` and `thym_check` all show it.
**`calls`** is a ceiling on the model requests of one run: a cloud plan
whose count is open (`calls_open`) is refused until a ceiling is given;
a fabulac build applies it to each stage's run, and since 0.7 a ceiling
across the whole build too: `job_calls` in the build's body, by default
`calls` times the three stages that ask (`fabulac_job.job_ceiling`; none
when no `calls` is given, as before). Each asking stage runs under what is
left of it; one with nothing left does not start (the result's `refusal`,
check `calls`, and the build takes up again from it), one that reaches it
while running is refused in the job's words. The status carries
`job_at_most` beside the total made. The plan-time refusal
order is `thym_host.route_refusal`: agent-free, then a shut gate ("the
cloud is not open for this run: …"), then the missing ceiling, then the
window (`preflight_hook`).

### Agent-free mode (0.4.4)

Everything above is **free-agent mode**. One machine-global switch turns on
**agent-free mode**: no model at all (docs/docoes-044-plan.md §13). It is
`agent_free` in `~/enough/config/ui.json` (shipped `false` in
`defaults/ui-config.json`; the `ENOUGH_UI_CONFIG` seam, so no new state
location), read by [agent_free.py](../enough/agent_free.py) — stdlib only,
one stat per ask, on only for a literal `true`. `POST /api/ui-config
{"agent_free": bool}` writes it (`GET` always carries the effective value),
and the boot UI state (`BOOT_UI_STATE`) carries it for first paint.

- **Boot.** `__main__` and the lifespan read it before any model would
  start: no adopt, no launch, no preflight; `--no-supervise` skips its
  llama-server check. `LlamaSupervisor.bootstrap()` is a no-op, `_launch()`
  and `switch()` raise, `status()` answers `mode: "agent-free"`.
- **The runtime toggle.** On: running councils pause, the preflight is
  skipped, `supervisor.stop()` (owned or adopted, like a switch). Off:
  `supervisor.bootstrap()` — the ordinary startup choice. Each flip emits
  the `agent-free` SSE event `{agent_free, supervisor}`. Home saves the
  switch and has no model to stop.
- **The gate.** `AgentFreeGate` (raw ASGI, beside `ModeGate`; table
  `AGENT_FREE_PATHS` / `AGENT_FREE_PREFIXES` / `AGENT_FREE_OPEN`) answers
  409 `{"detail": "agent-free mode: …"}` to `POST /api/chat` (every
  message, `/pal` and `/intro` included), `/api/model`,
  `/api/cloud/health-check`, **`/api/transcribe`** (whisper is a model too)
  and every `POST /api/council/*` but `pause`; `POST /api/skills/toggle`
  answers 409 itself for a toggle-on that needs the first-use audit.
  Behind it, the backstops: `llm.complete`/`stream_chat` raise
  `LLMUnavailable("agent-free")`, `llm.reachable()` answers `(False,
  "agent-free")` without probing, `cloud.gate_status()` is shut (so `/pal`,
  `ask_pal`, `cloud_pipeline` and `/api/pal/status` say so), and
  `tools.execute` refuses. **Open while agent-free**: model downloads,
  their cancel and deletes; cloud key storage (`set-key` stores, its health
  check skipped), `clear-key`, `set-model`; `GET /api/reset`, `GET
  /api/intro`, `GET /api/stream`; council reads and `pause`; Canon (ingest
  included) and the derivations' rules path; every `/api/docs*` and
  `/api/cosm/inline*` route.
- **What still works.** Everything without a model: composures, the
  dictionary, wikisink, Canon (incl. `POST /api/canon/ingest`, which the
  ingest bar calls directly after a confirmation built from `GET
  /api/canon/ingest-caps`), convert, paginate, girraph/merirmaid, the cosm
  viewer, model downloads and deletes, setting a cloud key (its check is
  skipped). Derive / atem / compile take their rules path — `llm.reachable`
  answers `(False, "agent-free")` without probing — and their jobs and
  results carry `reason: "agent-free"` beside `mode: "rules"`. A skill
  toggle-on that needs the first-use audit is a 409.
- **Payloads.** `/api/llm-status` → `{mode: "agent-free", ready: false,
  agent_free: true, fits: null, preflight: "skipped", …}`; `/api/models` →
  `agent_free: true` and `supervisor.mode: "agent-free"`. Tests:
  `tests/test_agent_free.py`.
- **Thym (0.5.0).** `/api/canon/read` is in `AGENT_FREE_PATHS` (a reading
  always asks the model; `read` has no scaffold). `/api/thym/run` is **not**,
  on purpose: a plan with no `asks` runs agent-free (by code, job `reason:
  agent-free`), and one that asks is refused 409 at plan time with the count
  ("3 steps ask a model; agent-free is on"), the runtime's own words
  (`run._environment`; the coprocessor is the refusing one). `POST
  /api/thym/plan` says the same as a refusal with check `agent-free`; `GET`
  routes, compile and unpack stay open. The run card lists only programs
  with `asks: 0` and says how many it left out; "read through…" says a
  reading needs a model. `thym_check` is agent-free-safe as a runner, but
  `tools.execute` refuses every tool while agent-free is on, so no chat turn
  reaches it. `--rules` (and `mode: rules`) runs scaffolds; agent-free never
  does: it refuses an asking plan outright.
- **The 0.6 round.** `model_route` refuses both routes while agent-free is
  on. A fabulac build runs its two rules stages (survey, history) and stops
  with the outline (`derived.completeness: outline`), its job `done` with
  `complete: false` and the read stage's refusal ("…; agent-free is on");
  a compile writes no cshort (a cshort needs a model) and a catem only as
  its scaffold. The dialectic's routes stay open: questions are listed,
  raised from the bank and answered with no model, and a settle runs by
  rules (an answer whose item a model would have to read again waits).
- **The UI (index.html, U-A).** The slider is one control drawn twice:
  `#am-ui-switch` (in `#am-ui-item`, the UI window's controls row, also on
  home) and `#am-model-switch` (in `#am-model-row`, the model window, with
  `#am-model-reason`) — `button.am-switch[role=switch][aria-checked]` holding
  `.am-track > .am-knob` and four word spans (`agentmode.free` /
  `agentmode.agent`, the two words; `agentmode.off` / `agentmode.on`, the two
  phrases). `agentFreeUsesPhrases()`: when, whitespace aside, `off` ==
  free+agent and `on` == agent+free, the two words swap (CSS `order` + one
  FLIP transition, `agentFreePaintSwitch`); otherwise the whole phrase shows.
  en and ja swap; de, fr, es and zh use phrases (0.4.4's translator pass kept
  that: none of the four can swap the words grammatically). The knob rides
  with "free": left off, right on (owner's ruling). **The page state**:
  `AGENT_FREE` / `agentFreeOn()`; `agentFreeApply(on)` — the one door, never
  POSTs: sets `<html data-agent-free>`, closes the readvisor panel without
  saving it (`AF_RV_PRIOR` restores it), releases a pinned council, repaints
  the badge, the model window and both switches, fires the `document` event
  `agent-free`; `agentFreeToggle()` — the click: applies at once, then `POST
  /api/ui-config {"agent_free": bool}` (rolled back on failure), and off →
  `agentFreeWaitForModel()` polls `/api/llm-status`; `agentFreeSet(bool)`
  (window; the harness's). First paint: the head script sets the attribute
  from `BOOT_UI_STATE.agent_free`. Followers: SSE `agent-free` and
  `/api/llm-status`'s `agent_free`. **Every hidden site is in one CSS block,
  "Agent-free mode", keyed on `html[data-agent-free]`** (plus the JS braces:
  `rvSetState`, `rvAsk`, `introAsk`, `trySubmit`, the chat form's capture
  submit, the ⌘/ ⇧⌘/ ⌘K ⌘↵ keys, `compCouncilIs`, `ctxNoticeWanted`,
  `canonBusyPaint`, `wdlMissingHTML`, the council form skipped in "new from
  form…"; the keyboard rows marked `[data-af-hide]`) — add a new site
  there, not elsewhere. The model window greys its running controls
  (`.am-greyed`, `agentFreePaintModelWindow`); the home screen shows
  `#home-agentfree`. **Canon's ingest bar**: `submitCanonIngest()` →
  `submitCanonIngestDirect()` while on — a relative `path:` made absolute
  against the project, `GET /api/canon/ingest-caps`, then
  **`confirmOverlay({lines: true})`** (a message shown as lines,
  `#confirm-message-text.confirm-lines`; every other confirm unchanged),
  `cnIngestVolumeName` (the empty volume you stand in, else one named after
  the source, ` 2`/` 3` on a clash), `POST /api/canon/ingest`,
  `cnIngestWatch(box)` (a toast to the end). Derivations keyed on `reason ===
  "agent-free"` say `canon.agentFree`; the twin face and the viewer key off
  the twin's `derived.mode: rules` plus `agentFreeOn()`. D3 reworded the two
  merirmaid flashes (`mm.flash.noNodeAgentFree` / `noPatchAgentFree`) and
  wikisink's update toast (`wiki.toast.updateStartedAgentFree`) for the
  agent-free state; the broker window and the OpenRouter wizard stay as they
  are (owner's ruling). The owner's word rule: "agent" appears only in the
  slider's two states and its tooltip (`tests/test_vocabulary.py`'s
  allowlist holds each language's two phrases). **uicheck** screens
  `ui-modal-agentfree`, `project-agentfree`, `model-modal-agentfree`,
  `canon-ingest-agentfree`, `home-agentfree` (steps `AF_ON` / `AF_OFF`
  through `agentFreeSet`); scenario `agentfree-toggle`.

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

### The gate, in one place (0.4.0)

`cloud.gate_status()` is the three-step chain that used to live inline in
`tools.run_cloud_pipeline`: **`local_models_only` off, then a key present,
then the last health check green.**

```python
{"open": bool, "reason": str | None, "denial": str | None, "model_id": str | None}
```

- `reason` — one short clause naming what is shut, for a UI with room for a
  sentence.
- `denial` — the full `broker.denial_*` copy, which says how to fix it. This
  is what a tool hands the model and what the chat shows the user.
- `model_id` — the configured model **only when the gate is open**; `None`
  otherwise, rather than leaking the configured model from behind a shut
  door. Falls back to `cloud.DEFAULT_CONFIG["model_id"]` when the config's is
  blank.

Three callers: `tools.run_cloud_pipeline`, `pal_tools.run_ask_pal`, and
`GET /api/pal/status`. **The order of the checks is load-bearing**:
`status_snapshot()` reads the OS keyring, and on macOS a keyring read by a
process the user has not blessed raises a system dialog, so the toggle is
checked first and a user who switched the cloud off never sees one.
`tests/test_pal.py::test_the_toggle_is_checked_before_the_keyring` pins it.
`cloud_pipeline`'s behaviour is unchanged by the refactor — same three
denials, same order, same strings, and four tests say so.

### `/pal` — one question out, in the open (0.4.0)

A pal is **not a subsystem**. It is the OpenRouter endpoint already
configured in this slot, reached once, by hand, from an otherwise local
turn. No pal config, no pal modal, no pal model picker, **no broker toggle**:
if the cloud slot is usable a pal is usable, and if it is not, the existing
cloud denial is the whole explanation. The command branch lives in
`POST /api/chat` (step 1 of "The request lifecycle"); the tool and the turn
window live in [enough/pal_tools.py](../enough/pal_tools.py); the two prompt
blocks live in [prompt.py](../enough/prompt.py).

**Typing `/pal` is the consent.** There is no second confirm step, because a
confirm step that appears every time is a button people learn to click. What
replaces it is visibility: the outgoing prompt is rendered to the user
verbatim, before the answer, every time, live and after a reload, and is
never summarized or truncated on the way to the screen.

The turn window is `pal_tools.pal_turn(session, active=)`, a context manager,
and **the only thing that sets `session.pal_turn` or the module-level
`_active`**. The flag is cleared in a `finally` so it survives every way a
turn can end — clean return, LLM error, the auto-reset path, a cancelled
`asyncio` task. `active=False` yields `None` and touches nothing, so
`_drive_message` wraps an ordinary turn in the same statement.

`ask_pal`'s checks run cheapest-first, with the one-call limit **last** so a
model making a second call with a malformed prompt is told about the
malformed prompt rather than scolded for the limit: no pal turn → gate shut →
empty prompt → over `MAX_PROMPT_CHARS` (6 000, **refused, not truncated**) →
`tools._CLOUD_KEY_EXFIL_PATTERNS` match → already spent. The call itself is
`cloud.chat_completion` (non-streaming), `max_tokens = MAX_TOKENS` (1 200),
messages **exactly** `[{"role": "user", "content": prompt}]` — no system
message, no conversation, no project, which is what makes "the bubble shows
exactly what left the machine" literally true. **A failed call does not spend
the turn**: a network error, an empty answer and a malformed response all
leave the one call intact, because `PalTurn.exchanges` is appended to only
after a successful exchange.

The record, four places, one codec: `pal_tools.render_result_body()` writes
the tool-result body (`→ pal · <model id>`, the prompt, then the reply inside
`cloud.wrap_untrusted_cloud_text`'s markers) and `parse_result_body()` reads
it back. From it come the live bubbles (the `pal_exchange` SSE event, fired
by the generic `ToolResult.side_effects` path in `server._handle_tool` the
moment the result lands, so **before** the readvisor's next tokens), the
reloaded history (`server._render_pal_bubbles`, called on every
`<tool_result …>` message — every other tool result still renders as
nothing), and the session log. Plus `cloud.cache_completion(source="pal")` in
`rness/io/cloud-cache/`, and a broker-journal entry: the tool reads its
prompt from a **`<prompt>` tag rather than `<content>`** precisely so that
`tools._trace_args_for` carries the outgoing text into the journal verbatim
instead of summarizing it as `<N chars>`. A cleared conversation is the
normal case; the journal is what is left of it.

```
event: pal_exchange
data: {"model_id": "…", "prompt": "<byte-for-byte what was sent>",
       "reply": "<the model's text, unwrapped>"}
```

The two bubbles are `<div class="msg pal-sent">` (byline `→ pal · <model
id>`) then `<div class="msg pal">` (byline `pal · <model id>`), in that
order, identical live and on reload. **The CSS for them is landing with the
0.4.0 UI lane**, along with the composer's command-hint row; the server emits
the class names either way.

| Route | Method | Notes |
|---|---|---|
| `/api/pal/status` | GET | `{"available", "reason", "model_id"}` straight off `gate_status()`. Project-mode only (`ModeGate` 404s it in home mode). **It reads the keyring when the toggle is off** — call it when the composer first sees a `/`, not on every keystroke |

**The `:online` suffix costs zero code on our side.** OpenRouter documents
appending `:online` to any model slug as exactly equivalent to
`"plugins": [{"id": "web"}]`, giving the model web results and billing extra
per search, free models included
(<https://openrouter.ai/docs/features/web-search>, checked 2026-09-18 — the
page carries no version stamp). Nothing here special-cases it: set the
OPRO-API model id to e.g. `anthropic/claude-sonnet-4.5:online` in the
settings panel and `gate_status()` returns it, `ask_pal` passes it straight
through, and the bubbles show `pal · <model id>` with the suffix included —
which is the honest thing, since the user is paying for the difference.

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
   identifiers we coined ourselves). **The same list is scanned over an
   `ask_pal` prompt** before it leaves the machine (0.4.0) — a model that
   can be talked into asking a pal to exfiltrate is the same hole in a
   different door.
3. **Response wrapping.** `cloud.wrap_untrusted_cloud_text()` exists for
   any path where cloud-produced text becomes tool-result content. (Not
   used for ordinary chat completions in Architecture A, where the
   cloud IS the readvisor; meant for `cloud_pipeline` output and any future
   path where cloud content gets passed back as data.) An `ask_pal` reply is
   such a path: `pal_tools.render_result_body()` wraps it in the same
   markers, held there as **literals** so importing `pal_tools` does not drag
   httpx and keyring in with `enough.cloud` — `tests/test_pal.py` pins the
   literals to the real constants.
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
- `pal` — one `ask_pal` exchange (`pal_tools.CACHE_SOURCE`)
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
| `canon_enabled` | canon | Whether the readvisors' three `canon_*` tools work at all, and whether `fabula_derive`/`atem` may write into the store (a `canon:` path; project paths and reads never ask). Canon's UI is ungated; URL ingests still additionally honor the `fetch_url_*` toggles. Was `cacheawl_enabled` (group `cacheawl`) before 0.4.3: `broker.load_config` moves a stored value to the new key once (`_RENAMED_TOGGLES`) and rewrites the file |
| `composure_enabled` | composure | Whether the readvisors' nine composure tools work at all — **and** whether `COMPOSURE_TOOL_INSTRUCTIONS` is in the prompt (this is the one toggle that gates *docs* alongside the *tools* they describe; the gate fails open on an unreadable config). The canvas UI stays ungated, like wikisink and Canon |
| `readvisory_install` | readvisors | Whether `install_readvisor` may write a readvisor to disk. Off keeps the `readvisory` skill's interview and drafting and leaves the filing to the user. A new group — `/api/broker` renders whatever is in `TOGGLES`, so a new group needs no code |

**`/pal` deliberately added none** (0.4.0). `local_models_only` plus a
working key already decides whether a prompt may leave this machine; a
second switch would be a second thing to get wrong and a second place for
the two answers to disagree. Same reasoning for councils: they run on the
same model the chat does and are gated by nothing extra. And for the five
MacroCOSM tools (0.4.3): reading, linting and writing a twin inside the
project need no switch, and a write into the store rides on the existing
`canon_enabled` rather than a new one.

---

## Tools

| Tool | Runner | Gating |
|---|---|---|
| `read_file` | `tools.run_read_file` | path under project OR on file-read allowlist — OR, read-only, a path under `rness/` that leads through a skeleton symlink into a shipped root (`_shipped_read_target`, 0.4.1; see "What NOT to touch"). A convertible original returns its **twin** (converting first, on a daemon thread joined for `tools.CONVERT_BLOCKING_SECONDS` = 120) — see "Document conversion" |
| `write_file` | `tools.run_write_file` | path under project OR on file-rw allowlist; not in `rness/requests/done/`. **`.girraph` and `.comp` are refused whole-file** (`composure.write_denial()` covers `.comp` *and* its `.<name>.comp.comments.json` sidecar, and the message names the composure tools to use instead). Canon's catalogs and meta — a volume's `canon.cosm`, `rness/canon.cosm`, `.canon.json` — are refused too, before allowlist resolution (`canon.catalog_write_denial`). A refused sync-on-save of a syncing twin comes back as `ok=False` whose body says the twin *was* written |
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
| `canon_list` | `tools.run_canon_list` → `canon.py` | `canon_enabled` toggle; no arg = list volumes, `<volume>` = its contents tree (reconciles first). Renamed from `cachebox_list` in 0.4.3 with no alias; the old `<box>` tag was removed in 0.7 |
| `canon_create` | `tools.run_canon_create` → `canon.py` | `canon_enabled` toggle; creates an empty volume (name-validated) + its `canon.cosm` catalog |
| `canon_ingest` | `tools.run_canon_ingest` → `canon.py` | `canon_enabled` toggle; `path`/`url`/`wikisink` source to a depth. URL ingests also honor the `fetch_url_*` toggles; a Holotype's people, database and outside-the-model folders are skipped; runs in the background, volume registered `ingesting` up front |
| `cosm_read` | `canon_tools.run_cosm_read` | none (it reads); `<path>` a `.cosm` file, a volume folder or a text with a fabula twin (any of its names), project-relative or `canon:`; `<item>` optional (id, key, item/field/module path). The text tree capped to 80 lines / 8 000 chars, or one item as YAML |
| `cosm_lint` | `canon_tools.run_cosm_lint` | none; the volume's own report (`lint_of`, 0.6): a fabula's own checks (`fabula.lint`, nothing "not run"), a holograph's Ascribe checks, else `macrocosm.lint`; sections of ≤ 25 lines plus one "not run" line |
| `fabula_derive` | `canon_tools.run_fabula_derive` (`emf_derive` until 0.6; that name still runs it through 0.6 by `retired_names.TOOLS`, and no prompt names it) | `canon_enabled` for a store path only; `text_target`'s refusals (no Holotypes, no `.cosm`, no catalogs, text kinds only, never over a file of the twin's name that is not a fabula, `fabulac` refused for a text); `<flavour>` `fabulan` \| `fabulap` (absent: the twin's own, else the suggestion), `<route>` `local` \| `cloud`, `<copyable>` (a fabulap's lines keep their words), `<force>`; refused over `TEXT_MAX` (24 000 chars); **rules scaffold over `EMF_MODEL_MAX` (6 000)** even with a model; "already fresh" unless `<force>yes</force>`; holds the file's claim, **never the generation lock**; fires `canon` |
| `atem` | `canon_tools.run_atem` | as `fabula_derive` for `<path>` (writes the twin's `atem:`, a minimal twin when none; `<flavour>`, `<route>`); `<text>` writes nothing; model up to `TEXT_MAX`; fires `canon` on a write |
| `cosm_guide` | `canon_tools.run_cosm_guide` | none; no tags. The install's `macrocosm-oes` SKILL.md, for a model whose skill is off |
| `doc_lookup` | `canon_tools.run_doc_lookup` | none (it reads); `<term>` (or `<id>`, `<section>`): a word, a section number (`18.4`, `help 3`) or an id → its atem, definition, where it is defined and up to three sections that mention it, from the spec then the manual in the UI language; a term that names a closed list adds the list's values and meanings (0.4.4). Builds a doc volume on first use (see "DocOES") |
| `thym_check` | `thym_tools.run_thym_check` | the `macrocosm-oes` skill on in the project (else one line asking the user to switch it on); read-only, every mode. `<path>` or `<program>` (a name resolves project → canon → shipped), optional `<inputs>` lines `name=path`, `<model>` (0.6: `local` default, `cloud`, `cloud:<id>`). Answers `ok`, the CLI's plan line (`cli.plan_atem`, word for word), the models line and a route refusal line when the plan asks, and `takes`/`gives` (every output); without inputs it plans on placeholders and says the largest prompt was not measured; a refusal names the file and line (0.5.0) |
| `thym_run` | `thym_tools.run_thym_run` | the `macrocosm-oes` skill on; `<program>`, `<path>` (the first `takes`), further `<inputs>` lines (a folder input too), `<model>`, `<calls>` (0.6). Refused at plan time, nothing run: a plan that asks while no model runs or agent-free is on ("3 steps ask a model on the local route, the first `…` (line n); …"), a shut gate, an open cloud count with no `<calls>`, a preflight that does not fit, an asking plan over a text past `TEXT_MAX` (sent to the reader's run with…). No lock, no job; outputs and trace land under the Thym root only, the answer names every output (a folder as `name: path/ (a folder of N files)`); fires `canon` with `kind: thym` (0.5.0) |
| `thym_moves` | `thym_tools.run_thym_moves` | the `macrocosm-oes` skill on; read-only, every mode (0.6). `<version>` 1 (default) or 0, `<move>` for one: each move a program of that grammar may call, one line each — signature, "asks a model, scaffold X" or "asks nothing", contract, its `says` line — read from the declarations a compile reads. Dispatched only because the MacroCOSM block names it (`thym_tools.documented`) |
| `dialectic` | `fabula_tools.run_dialectic` | the `macrocosm-oes` skill on (0.6). `<path>` alone: the next one or two (`SHOWN` = 2) open questions of the volume (a text's fabula, a fabulac, a holograph, any `.cosm` volume), each with who answers it, its shape, `asks:`, `about:` and `hint:`, or "no questions yet (<do>raise</do> asks the format's bank)"; `<question>` + `<says>` (the person's words, verbatim) records an answer, `<state>` `unknown` \| `declined` \| `skip` instead (`through: agent`, the model's id): into an answers volume beside a single-file volume, into a holograph by Ascribe's rules; `<do>settle</do>` (a job, `<model>` its route) or `<do>raise</do>`. See "The dialectic" |
| `fabulac` | `fabula_tools.run_fabulac` | the `macrocosm-oes` skill on (0.6). `<path>` a folder of Python in the project or its `.fabulac.cosm`; `<do>` `status` (default: the stages landed, the next, a running job's files read and model calls), `build` (also takes a stopped build up again), `compile` (`<what>` `code` \| `line` \| `overview` \| `manual`), `cancel`; `<model>` the route (`local` unless the person chose the cloud for this job). A build or a compile is a job like the page's, started through `server._start_from_tool`: "job cnN: … (queued). It runs after this turn; ask for its status later." Without the app (a test, the command line) it says the job runs in the reader. See "Building a fabulac" |
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
| `dict_lookup` | `dictionary_tools.run_dict_lookup` | **no toggle** (it reads). FEED shipped and built — otherwise a sentence saying which ("not bundled", "still being prepared (N%)", "could not be prepared"), never a raise |
| `dict_add_entry` | `dictionary_tools.run_dict_add_entry` | no toggle; writes `user-dictionary.sqlite` only. `<word>` a–z + `pronunciation` / `pos` / `definition` required; refuses a word FEED already has as a headword; fires `dict_changed` |
| `dict_update_entry` | `dictionary_tools.run_dict_update_entry` | no toggle; the user's entry, or the user's own version of a FEED word (which then overrides it everywhere). An empty tag clears a column; fires `dict_changed` |
| `dict_guide` | `dictionary_tools.run_dict_guide` | none; no tags. The install's `lexicographer` SKILL.md, for a model whose skill is off |
| `show_intro` | `intro.run_show_intro` | none; documented in the always-on core with its one-time offer. Fires `intro` |
| `ask_pal` | `pal_tools.run_ask_pal` | **no toggle of its own** — the cloud gate is the gate. In order: a pal turn is open (the user typed `/pal`) → `cloud.gate_status()` open → a non-empty `<prompt>` (**not** `<content>`, though it is accepted as a fallback) → ≤ `MAX_PROMPT_CHARS` (6 000), refused not truncated → no `_CLOUD_KEY_EXFIL_PATTERNS` match → **one call per turn**, checked last. See "`/pal`" under OPRO-API |

All registered in `_DISPATCH` (~line 1700 in tools.py) and
`_TRACE_TOGGLE` (~line 1730) — twenty-seven of them add themselves through the
**eight** import-time `register()` calls at the bottom of tools.py
(`composure_tools.register()`, `readvisor_tools.register()`,
`pal_tools.register()`, `dictionary_tools.register()`,
`canon_tools.register()`, `thym_tools.register()` (0.5.0),
`fabula_tools.register()` (0.6), `intro.register()`). `tools.execute` looks a
name up in `retired_names.TOOLS` first, so a call by a name retired in 0.6
(`emf_derive`) runs its new name's runner through 0.6 (and its result says
the name it was called by); nothing documents the old name. The
`register()` call is the pattern to copy for any future tool
family: the op vocabulary stays in one module instead of spreading runners
through tools.py. The tool-call XML parser (`parse_tool_calls`) handles
arbitrary tool names — extra inner tags (beyond `<path>`, `<content>`,
`<command>`, `<url>`) end up in `ToolCall.extra` so new tools don't need
parser changes; `ask_pal`'s `<prompt>` is one of those, chosen because
`_trace_args_for` carries an unknown inner tag into the broker journal
verbatim and summarizes `<content>` as `<N chars>`.

A runner that changes something the frontend has open returns a
**`ToolResult.side_effects`** dict; `server._handle_tool` fans each key out
as an SSE event of that name. That is how a composure tool fires the
`composure` event, `install_readvisor` fires `readvisors_changed`,
`ask_pal` fires `pal_exchange`, the two dictionary writes fire
`dict_changed`, `show_intro` fires `intro`, and a `fabula_derive` or `atem`
write fires `canon` with a finished job snapshot (`id: "rv<n>"`, `by` set) —
the same event the derivation jobs emit. A build, compile or settle that
`fabulac` or `dialectic` starts is a real CanonJob, so its `canon` events
come from the job table itself.

Tool documentation that the readvisors read is in
[enough/prompt.py](../enough/prompt.py) under `TOOL_INSTRUCTIONS`,
`COMPOSURE_TOOL_INSTRUCTIONS`, `READVISORY_TOOL_INSTRUCTIONS`,
`DICTIONARY_TOOL_INSTRUCTIONS`, `CANON_TOOL_INSTRUCTIONS`,
`FABULA_TOOL_INSTRUCTIONS` (0.6) and `PAL_TOOL_INSTRUCTIONS`, beside the
0.5.1 blocks split out of the core (girraph, review, wiki, cloud, canon
store, keep going, each with its `*_LEAN_INSTRUCTIONS` summary), assembled
by `tool_instructions(project_dir, pal=False, lean=False)` (see "The request
lifecycle" for the gates). Every new tool needs an example block + prose
explanation in the right block — and `tests/test_prompt_weight.py` will fail
until it has one. **A new tool whose docs ride in the always-on core must
either gate its own block or raise `CORE_BUDGET` / `FULL_BUDGET` on
purpose**, and the lean profile must still fit `LEAN_BUDGET`. A tool whose
docs are in a block that would cross its cap waits outside `_DISPATCH` until
the block names it (`thym_tools.documented` did that for `thym_moves`), since
the test forbids a dispatchable tool no prompt names.

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
`message`, `wiki-search`, `mm-label-input`, `cn-ingest-value`,
`cn-prompt-input` (Canon's, `ca-*` before 0.4.3), `comp-title`,
`comp-search`, the council's `cc-*` fields, `rename-chief-input` and
`dict-q`. Note rung 3 outranks rung 5
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
`[merirmaid diagram: …]`, `[cacheawl store]` — Canon's old name) whether or not anything was
selected. Those did not survive, by owner decision — context stays empty
until something is selected. Restoring one would go in the same submit
hook.

### Two sides, and the brief introduction (0.4.1)

- **Sides.** `.msg.user` hugs the left of `.conversation`
  (`margin-right: auto`), `.msg.assistant` the right (`margin-left: auto`);
  both `width: fit-content`, `max-width: 86%`, with a 2px accent rule on
  the outer edge. Only the block moves — the text inside stays
  left-aligned, because right-justified prose, code and tables are hard to
  read. `system`, `rness` and pal bubbles are enough's own notes, not a
  voice, and reset to full width. The `.conversation {` rule itself is back
  after two releases missing (see `tests/test_css_integrity.py` under "The
  pre-commit suite").
- **The text.** One English file, `defaults/intro.md`, owner-editable;
  translations at `enough/static/i18n/<lang>/intro.md` when they exist,
  English otherwise (the `/api/help-center` rule). Not checked by
  `i18n_check.py`, so a missing translation is a fallback, not a failure.
- **Three doors, one text.** `GET /api/intro?lang=` → `{text, lang}`
  (`lang` is what was actually served). The whole-message match in
  `POST /api/chat`: after `intro.normalize()` (lowercase, punctuation
  dropped, a leading `/` kept), `/intro` matches any time and
  `INTRO_PHRASES` ("what can you do", "what can enough do", "what is
  enough", "what is this", "help") only while `session.history` is empty —
  later, "what is this?" is about something on screen — and never while a
  turn holds the generation lock. It answers through `_reply_without_turn`
  and still writes history and the session log. And the `show_intro` tool,
  always on, documented in the core together with the one-time offer
  after a bare greeting; its `intro` side effect `{html, text, speaker}`
  draws the bubble and its result tells the model the text is already on
  screen. Edit `INTRO_PHRASES` there and only there.
- **The bubble** is the chief's: `.msg.assistant.intro` with
  `data-markdown="intro"` and the escaped markdown source as its body;
  `introRender()` renders it once, and `introReveal()` scrolls to its
  *first* line. On reload `_render_turn_from_history` redraws it from either
  form (`intro.is_intro_text`, `intro.render_tool_result`).
- **The empty hint** is the plain *awaiting your first message.*
  (`server._default_empty_hint`; the "ask what they can do" line is gone).
  `introDecorateEmpty()` clones `#intro-link-tpl` — a button that sends
  `/intro` through the normal chat path — into whatever `#empty-hint` is
  showing, the server's, `/reset`'s or a model switch's alike.
  `defaults/AGENT.md`'s "First conversation" carries the same offer, but
  only into new projects (AGENT.md is a copy); the core tool doc reaches
  every project.

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
<meta name="composure:kind" content="plane">       <!-- page | plane -->
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
`create_app`'s `_resolve_project_path`, so `canon:` works (the legacy
`cacheawl:` was removed in 0.6) and traversal is a 400; a path that does not end in
`.comp` is a 400 that says so.

| Route | Method | Notes |
|---|---|---|
| `/api/composure?path=` | GET | `{path, rev, model}`. **Side effect:** stamps `rness/project.json`'s `composure.last`. That is the *only* place `last` is written |
| `/api/composure/ops` | POST | **The single write door.** `{path, base_rev?, source, create?, form?, title?, want_model?, ops[]}` → `{path, rev, changed[], stale, stale_changed, created, model?}` |
| `/api/composure/new` | POST | Describes a composure **without writing it**: `{path: null, pending_path, form, title, rev: 0, model}` |
| `/api/composure/list` | GET | `{composures: [...]}`, newest first; each row carries `content` (anything in it beyond an empty text box) and `startup` (the project opens with it) |
| `/api/composure/forms` | GET | Shipped first, then `rness/composure-forms/`; a project form with a shipped name **wins** and is listed once with `origin: "project"` |
| `/api/composure/save-as-form` | POST | `{path, name}` → `{form, path, forms}` |
| `/api/composure/rename` | POST | Retitles, renames the file to match, and **carries the comments sidecar**; `keep_filename: true` retitles only; 409 on a collision |
| `/api/composure/link-preview` | GET | `?path=&module=` — per type; **never raises** for a missing target, answers `{ok: false, detail}` |
| `/api/composure/webframe/refresh` | POST | Goes through `tools.fetch_and_cache` — the **same** gated pipeline as `fetch_url` — then writes `data-cache` and page 1 through ordinary ops with `source: "enough"`. A broker refusal comes back `200 {ok: false, denied: true, detail}` with the denial text verbatim |
| `/api/composure/comments` | GET/POST/PATCH/DELETE | Mirrors `/api/wiki/comments*`. Deleting the last comment removes the sidecar rather than leaving `{"comments": []}` |
| `/api/composure/launch` | GET | Resolved against what is actually on disk: `{launch, path, form, notice}`. `auto` (the default) opens the only composure with content, else the last one used among several, else a blank page; a `file`/`last`/`form` target that is gone falls back to `auto` with a `notice` |
| `/api/project/composure` | POST | `{launch: "auto"\|"new"\|"last"\|"file"\|"form", path?, form?}`. `file` + `path` is the startup composure (a composure's settings modal ticks it; unticking posts `auto`). A stored `blank` (0.3.5–0.4.1) reads as `auto`. **The `last` key is never accepted here** — it is stamped by opening a composure, and a rename through the app carries it and the startup `path` along |

**A stale `base_rev` is not an error.** Ops are last-writer-wins per module,
so the batch still lands; the reply says what moved underneath you in
`stale_changed` (`[]` when fresh, `null` when the history window no longer
covers `base_rev` — then refresh everything).

### The `composure` SSE event

```jsonc
// event: composure
{"path": "rness/io/composure/plane.comp", "rev": 12,
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

**Auto fit (0.4.1).** One `ResizeObserver` on `#comp-viewport`
(`compWatchViewport`): any size change — the sidebar, the readvisor panel
docked / full / closed, the comments panel, a window resize, a ui-scale step
— re-applies the view at once (so a page's width clamp tracks the 180 ms
grid transition frame by frame) and re-arms a `COMP_AUTOFIT_SETTLE_MS`
(160 ms) timer, so a transition ends in exactly **one** fit. A `plane` gets
`compFitAll(true)`, the fit button's own action; a `page` gets
`compApplyView(true)`, because its page-fit clamp already *is*
fit-and-centre for a sheet, and fit-all on a page is the bug the
`compOpenFit` note records. It never fires before a document is adopted, on
the observer's first report or out of a zero size (the stage appearing,
not changing — the saved view adopted from the file must win), while a
mode covers the canvas or it is only peeked at (`_compFitPending`, paid by
`compAutoFitFlush()` from `_modeRender` when the stack empties), or while a
drag, a pinch, a wheel burst (250 ms) or an eased move is under way —
those defer it, up to 25 tries, then leave it pending. So a hand zoom on a
plane lasts until the next size change: that is the rule, not a bug.

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
eleven stacked mode roots (`_ALL_MODE_ROOTS`; 0.4.3 added `#cosm-mode`, and 0.4.4's `#docs-mode` replaced `#ref-mode` and the 0.4.3 `#cosmspec-mode`)
so the canvas shows through, and Esc restores them
before it starts popping the stack. `_modeRender()` appends a permanent
base square to `#mode-stack`, rightmost, **with no exit ribbon** (see "What
NOT to touch").

---

## Councils (the engine, the budget, the lean profile)

A **council** is the multi-readvisor composure form: several readvisors and
the user speak in turn on one canvas, each statement a locked module, and
the whole thing concludes into **an answer, a document, or a whole new
composure** (all three land in 0.4.0).
[enough/council.py](../enough/council.py) is the engine,
[enough/council_api.py](../enough/council_api.py) the HTTP translation.
The backend contract below is final; the 0.4.0 **UI lane** is concurrently
adding the setup card's output-form select and charge inputs, the reconvene
control, the pal statement's collapsed prompt, and `POST /api/council/pal`
(the route that wires `council.PAL_CALL` to the `/pal` machinery) — each
marked below where it is not yet verifiable in code.

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
status round turn cursor next queue brief_module transcript reconvene
reconvened_from reconvened_to output_fallback`. `status` ∈
`setup | ready | running | paused | concluded`; `order` is `round-robin`,
the only one. Participant kinds are `chief`, `readvisor`, `user` and
**`pal`**. `RESERVED_KINDS` **is now `frozenset()`** — `pal` was its only
member and 0.4.0 gave it a voice, so a pal is named in the brief's roster
and in the export like anyone else. The name is kept rather than deleted
because `brief_text`, the export and `state()["reserved"]` all read it, and
the next reserved kind should cost one line instead of five call sites.
`charge` is no longer a hook either (see "Charges"), and `reconvene` is now
a fact about where this council came from rather than a placeholder.

Refusals are `CouncilError` → 400 with the sentence verbatim: unknown
status / kind / output kind / order / composure form; `max_rounds` outside
1–`MAX_ROUNDS_CAP` (20); more than `MAX_PARTICIPANTS` (12); a participant
with no name; duplicate ids; **two participants with the same name**
(statements are attributed by name); more than one chief; nobody who can
speak; a `document` output with no path or with a `.comp` path; a `charge`
over `MAX_CHARGE_CHARS` (200).

**Tints** are assigned once at setup and **stored on the participant**, so a
readvisor keeps its colour for the life of the council even when another is
added later: chief `paper`, user `blue`, readvisors
`yellow → green → pink → lilac → orange` cycling in participant order, pal
`gray`, the conclusion `ink`.

### The rotation

`speakers(meta)` is the chief plus the readvisors, in list order — the user
writes its own statements and a pal speaks only when it is asked, so neither
is in the rotation and neither takes a share of the window. A round closes
when the cursor wraps to 0, so `/round` means **finish the current round**.

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
   as minutes rather than a plane), `h` from `composure.estimate_height`,
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
| `/api/council/setup` | POST | Creates the composure from the `council` form when the path does not exist, **in the same atomic batch as the meta** — a refused setup writes nothing at all. 409 when the output document exists and `overwrite` was not sent, or when already concluded. Then, in a **second** batch, writes the brief module from `council.brief_markdown(meta)` (see "Setup writes the brief") |
| `/api/council/state?path=` | GET | The same body `/setup` returns. Cheap — reads the file and at most the cached `/props` probe, assembles no prompt, **safe to poll** |
| `/api/council/participants` | GET | The setup card's starting checklist: the chief, every **enabled** readvisor (display name from its `AGENT.md` H1, `folder` for the engine), and the user, tints already assigned |
| `/api/council/convene` · `/pause` | POST | `pause` cancels a background `/run`. **A statement that has started to land** (its commit is on a worker thread) **finishes landing before `/pause` returns** — `council._land_whole` shields the landing, waits it out, then re-raises the cancel — so the canvas and the turn counter always agree; a turn still being generated is dropped, nothing of it written (0.4.3; before, the cancel returned while `commit_statement` was still writing and the status write raced it). Cancelling a task cannot stop the thread it awaits, so any new code that commits through `asyncio.to_thread` under a cancellable task lands through `_land_whole` too |
| `/api/council/next` · `/round` · `/run` | POST | one turn · to the end of the round · a background task to `max_rounds` (returns at once, reports over SSE). 409 when this council is already running |
| `/api/council/say` | POST | Always queued first, then drained immediately when no turn is streaming. So the common case is "it appears now", the racy one is "it appears next", and neither is "it is lost" |
| `/api/council/conclude` | POST | One chief turn under `conclusion_framing`, committed tinted **`ink`**. Then: `answer` → that module *is* the output; `document` → written through **`tools.run_write_file`**, the same door and guards as the tool, then a `doc` link-in module under the conclusion; `composure` → the outline path below. Response carries `output`, `document`, `composure`, `output_fallback`, `retried`, `form`, `detail`, `transcript`, `module`, `text` + the full state. A kind outside `OUTPUT_KINDS_LANDED` is **501 before the turn runs** — today that set is all three, and the check stays because the next kind will land the way `composure` did |
| `/api/council/reconvene` | POST | `{path, title?}` → a **new** council composure carrying the same participants (ids, kinds, names, folders, tints, charges), `parameters`, `constraints`, `output` **including its path**, `max_rounds` and `order`, with a fresh `input` built by `reconvene_input()`. 409 when the council has not concluded. `_guard_chat()` applies (it writes files and shares the model); `_guard_council()` does not, because a reconvene starts no turn |
| `/api/council/pal` | POST | **Landing with the 0.4.0 UI lane**: the route that assigns `council.PAL_CALL` and calls `council.ask_pal_turn(path, user_ask)`. The engine seam exists and is tested; the route does not exist in `council_api.py` yet |

Setting a council meta on an existing non-council composure is allowed; its
`form` stays whatever it was, and **the frontend keys off `council` being
non-null, not off `form == "council"`**.

### The `council` SSE event, and the exclusions

```jsonc
// event: council
{"path": "…", "phase": "start"|"token"|"end"|"error"|"status",
 "turn": "3", "speaker": "Nadia", "speaker_kind": "readvisor",
 "text": "…",                                        // token | end | error
 "module": "m5", "rev": 7,                            // end
 "folded": 2, "tokens": 15012, "head": 14180, "budget": 13107,  // end
 "status": "running", "round": 1, "next": "chief", "next_name": "Ed"}
```

**`turn` is a string on `start`/`token`/`end`/`error`** (0.4.0; it was an
int). It is a *module's* turn, and `composure.Module.turn` is `str` because
`data-turn` is text — so the event now matches the data model instead of the
frontend having to coerce. Fixing it the other way would have changed
`Module.turn`, the `.comp` attribute and `module_model`, which three other
lanes read. **The `status` phase's `turn` is a different quantity and stays
an int**: it is the council's statement counter off the meta, the same value
and type as `council.turn` in `/api/council/state`.

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

### The three output kinds, and the composure fallback

`OUTPUT_KINDS = ("answer", "document", "composure")` and
`OUTPUT_KINDS_LANDED = frozenset(OUTPUT_KINDS)` — all three conclude.
`validate_output()` takes `{kind, path?, form?, overwrite?}`: `document`
needs a `path` and refuses a `.comp` one; **`composure` takes no path at all**
(the file is made beside the council on conclude and its path is written
*back* into `output.path`) but does take `form` ∈ `COMPOSURE_OUTPUT_FORMS`
(`scaffold` — each group a column — or `cards` — each group a row),
defaulting to `scaffold` and validated **at setup**.

`conclusion_framing(output)` appends `_CONCLUSION_SHAPE[kind]` to
`_CONCLUSION_FRAMING`. The composure shape asks for the outline grammar of
"`composure_from_outline` and the `scaffold` skill" below and nothing else —
no covering note, no code fence — and tells the chief to use `[gap: …]` cards
for what the council did not settle.

Then, in order, in `Council.conclude_composure()`:

1. one concluding completion, asked for the outline;
2. `outline_composure(title, form, markdown) -> Composure | None` decides
   whether it parsed. `None` — "did not parse" — when **any** of: empty after
   `strip_code_fence`, `parse_outline` raises, no groups or no cards in any
   group, or `from_outline` refuses it (today: over `MAX_MODULES` cards). All
   four mean the same thing to the retry. `strip_code_fence` unwraps a reply
   that is *entirely* one fence, because models fence markdown they were
   asked for far more often than they write markdown that is a fence;
3. `None` → **exactly one** retry: `council.OUTLINE_RETRY` appended as a
   final `user` message to the **same assembled prompt** (same speaker, one
   more instruction — re-reading a dozen files to say it would be a second
   prompt assembly for no gain). Two retries would be two more windows spent
   on a council that has already decided;
4. `None` again → the conclusion is committed as an ordinary `answer` module
   (ink-tinted), `output_fallback: "answer"` goes into the meta *and* the
   conclude response, `detail` says the outline would not parse twice, the
   transcript header says so too, and **no file is written**. The *second*
   attempt's prose is what is committed when it is non-empty (it is the
   model's most recent answer to the brief), otherwise the first — the
   council's decision is never thrown away because a small model would not
   write headings.

**Exactly one statement module is committed whichever way it goes**: the
first attempt is streamed but not committed, and the second `start` phase
replaces the pending card in the UI.

The file lands at
`rness/io/composure/<council-slug>-output-<YYYY-MM-DD>.comp` —
`output_composure_path()`, the council file's own stem slugified, never
overwriting (`-2`, `-3`, …), pure apart from the existence check. It is
built **whole, in memory** by `from_outline` before anything is written, so
a parse failure, a bad op or the module cap costs nothing on disk, and it is
then written with `comp_core.save` at `rev = 1` rather than through
`apply_ops`: there is no previous version to be stale against, no base rev
and no other writer, and `from_outline` has already validated every op. **`apply_ops`
is the door for *changing* a composure**, which this is not. The model's own
`# ` line is the new composure's title; the council's title is the fallback
for an outline that opened straight into `## `. Finally a `doc` link-in is
added to the **council** pointing at the new file, and the transcript header
gets `**Output.** composure (scaffold) → \`…\``.

`_stream_one` is the shared primitive underneath (`take_turn` is built on
it): one streamed completion, announced and committed by nobody, with three
knobs — `append` (a final user message: the outline retry, the pal
distillation), `quiet` (no `token` phase) and `announce_as` (the
`(name, kind)` the phases carry when that is not who is running). `_land` is
the shared tail: commit, `end`, `status`, `composure`. **Any future "one more
completion" should use these** rather than growing `take_turn` a fourth mode.

### Charges

`participants[].charge` is one line of accountability — "argues the reader's
side" — optional, `≤ MAX_CHARGE_CHARS` (200). `_charge()` collapses all
whitespace including newlines (a textarea that wrapped is not a user error)
and **refuses** anything over the cap with the length in the sentence, rather
than truncating: a charge silently cut in half would change what a
participant was told to do.

`identity_for()` appends it **last**, after the council framing, as its own
`## Your charge in this council` section — it is the most specific thing this
participant was told and the thing a long identity is most likely to bury.
**Only that participant's own charge reaches that participant's prompt.** It
is also already in the transcript export header
(`- **Nadia** (readvisor) — argues the reader's side`). The setup card's
per-participant charge input is **landing with the 0.4.0 UI lane**; the
server refuses the whole setup with a sentence carrying the number, so the
input should cap at 200 itself.

### Reconvene

A concluded council, sat again. `POST /api/council/reconvene {path, title?}`
returns the **new** council's full `/api/council/state` plus `path`, `from`
and `title`; the default title is `<title> · reconvened`.

What carries over unchanged: participants (ids, kinds, names, folders, tints,
charges), `parameters`, `constraints`, `output` (kind, form **and path**),
`max_rounds`, `order`. **The output path rides over whole**, including a
`document` output's: a second council writing to a path that now exists is
not silently overwritten — `_check_output_path` asks at setup and at conclude
exactly as it did the first time. (Blanking it would have made
`validate_output` refuse the meta outright.)

What is new is `input`, built by `reconvene_input()`: the prior input, a rule
("The council in `…` has already sat on this. What it produced is the
starting point now."), then the prior output as the thing on the table — for
`answer`, the last statement's text; for `document`/`composure`, a reference
line plus the first `RECONVENE_EXCERPT_CHARS` (2 000) of the file suffixed
` …(truncated)`. **A `.comp` is read through `comp_core.outline()`, not as
HTML** — the markup is not what the next council needs to argue with. An
unreadable file degrades to the reference line alone.

What is reset: `status: "ready"`, `round`/`turn`/`cursor` to 0, `queue`
empty, `transcript` null, `next` = the first speaker. `reconvene: true` and
`reconvened_from` record the lineage.

**The old council is not re-run, re-statused or re-written.** It gains
exactly two things: a `doc` link-in pointing at its successor, and
`reconvened_to`. Its status stays `concluded` and its transcript is
untouched. The new council gains the mirror link-in, so a chain of any length
is readable from either direction. The `#cc-done` reconvene button (and
showing the link instead when `reconvened_to` is already set — a council is
reconvened once) is **landing with the 0.4.0 UI lane**.

### The pal seam

**The council does not know how to reach a pal and must not learn.** The
gate, the cache, the broker trace, the exfiltration patterns and the one-call
limit all live with `/pal`. Two module attributes are the whole contract.

```python
council.PAL_CALL: Callable[[str], Any] = _pal_not_wired
# PAL_CALL(prompt) -> (model_id, reply_text)
```

- **Unwired it raises `NotImplementedError("pal lane")`**, which propagates
  to the caller untouched — `ask_pal_turn` re-raises rather than wrapping it,
  so the lane can turn it into whatever the closed-gate answer should be.
- It may be a plain function **or** a coroutine function; an awaitable return
  is awaited.
- Any *other* exception is wrapped as `CouncilError("the pal could not
  answer: …")` after an `error` phase is announced, and nothing is committed.
- To wire it: `council.PAL_CALL = my_pal_call`. Tests do exactly that, and so
  will `POST /api/council/pal` when it lands with the UI lane.

`council.ask_pal_turn(path, user_ask, *, project_dir=, rel_path=, llm_url=,
session=, emit=)` (module-level, taking a path *or* a built `Council`) and
`Council.ask_pal_turn(user_ask)` do, in order: refuse an empty ask; **one
chief completion through `run_council_turn`** — the whole assembled chief
prompt with `PAL_DISTILL` appended as a final `user` message carrying the
user's ask, the reply cleaned by `clean_statement` and cut to
`PAL_PROMPT_CHARS` (6 000), an empty result being a `CouncilError`; then
`PAL_CALL(prompt)`; then **one statement committed** through
`composure.apply_ops` with `source: "council"` exactly like every other
statement — `speaker_kind="pal"`, `speaker="pal · <model id>"`,
`bg=PAL_TINT` (`"gray"`, the one unused swatch). `PAL_DISTILL` tells the
chief the pal has seen none of this and to write ONE self-contained prompt
naming no file path, no project name, no participant's real name and no
private detail the question does not require.

The distillation streams with `quiet=True` — the user is not meant to read
the chief thinking; what matters is the prompt, and it lands in the module —
but **does** announce `start` and `error` as `speaker: "pal",
speaker_kind: "pal"`, so the pending card says `pal` from the first frame.
The module's page puts the outgoing prompt **first**, as a blockquote led by
`PAL_PROMPT_LEAD` (`→ pal`), with the reply beneath: nothing leaves this
machine without being written where the user can read it.

**A pal answer is an interjection.** `pal_participant(model_id)` is shaped
like a participant but is **never** in `meta["participants"]`, and `advance()`
only moves the cursor for `chief`/`readvisor` — so a pal statement takes a
turn *number* but not a slot. Whoever was about to speak still speaks next,
the round does not move, and the budget's even split is unchanged. The next
participant reads it as an ordinary `user`-role line prefixed
`pal · <model id>: …`, like any other speaker's statement.

### Setup writes the brief

A council set up through the API alone — by a tool, by a script, by anything
that is not the setup card — used to keep the shipped form's "What the
council is working from…" placeholder while the participants argued about
something else. `api_council_setup` now writes it from
`council.brief_markdown(meta)`: the four setup fields in the shape the
shipped form's placeholder has, empty ones skipped, `**Desired output.**`
always present.

The output clause comes from `output_sentence(meta)`, which the brief every
*participant* reads (`brief_text`) also uses, **so the canvas and the prompt
cannot drift**. It is an ordinary `set_page` from `source: "council"` — the
brief module has no speaker, so it is unlocked and this needed nothing new —
and the batch also records `brief_module` in the meta. It is a **second**
batch, not part of the first, because on a create the module's id is not
knowable until the form has been materialized; the frontend's own `set_page`
from `source: "ui"` still works and still wins if it runs after. English,
like every other document body (`docs/I18N.md` keeps what the readvisors read
in English). **A failure here is logged and swallowed** — a council whose
setup succeeded should not 500 because its cover page did not get written.

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
User-facing explainer: [docs/HELP_CENTER.md](HELP_CENTER.md) §21.

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
  a full-frame mode alongside the unified read/edit mode, merirmaid, Canon
  and the cosm viewer. Breadcrumb stack navigation through `@`/doc refs; pushing an
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
  (same reconcile philosophy as Canon's catalogs).

---

## Merirmaid (the Mermaid-diagram primitive)

A `.merirmaid` file is a Mermaid-syntax diagram with a small frontmatter
header, rendered to SVG live in the browser by a **vendored** (local, no
CDN) `enough/static/pele.global.js` — [Pele](https://github.com/obsidianmd/pele)
1.13.0, Obsidian's Mermaid renderer (MIT, shipped like `htmx.min.js`; the
global IIFE build from the npm tarball, pinned — Pele is young and moves
fast). Since 0.5.1; Mermaid's own 3.4 MB bundle drew the diagrams from
0.1.6 to 0.5.0. Pele renders synchronously (`pele.render(text, options)` →
`{svg, width, height, links}`), lays out itself, targets Mermaid 12.1.0
syntax, and takes its colours from CSS variables: `#merirmaid-mode` sets
`--pele-bg/fg/muted/line/surface/surface-alt/border/accent` from enough's
tokens, so a theme change needs no re-render (`mmOnThemeChange` is gone).
Every rendered node is `g.pele-node[data-id=<source id>]`, which is what
`mmNodeId()`, `mmWireNodes()` and the harness's `MM_NODES_READY` key on.
Every diagram looks different from 0.5.0 (a new layout engine). The
paradigm-shift from girraph: there is no owning
Python module for the *format* — the source is plain text a readvisor
writes with `write_file` and the frontend renders. The backend code that
produces `.merirmaid` text is the girraph-mirror generator in `girraph.py`
(the only one that writes a file) and on-demand renderers that write
nothing: Canon's volume mirror (`canon.build_mirror`; the persisted
`_cachebox.merirmaid` is gone since 0.4.3), the home screen's project map
(`home.build_project_mirror`) and the MacroCOSM lenses
(`GET /api/cosm/lens`, frontmatter `kind: cosm-lens`).

Format (formerly docs/merirmaid-plan.md, folded in here):

```
---
merirmaid: 1
title: How the broker gates tools
modality: wip            # wip | mirror
node-char-limit: 48      # soft per-node-label limit the editor surfaces
source: canon:wiki       # mirrors only — what this file mirrors
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
  diagram of some external structure (a girraph, a Canon volume's
  contents, a `.cosm` volume seen through a lens) — **read-only** in the UI,
  regenerated only by the system that owns the mirrored structure.
- **Whole-file writes are allowed** (unlike `.girraph` — no broker-assigned
  IDs to protect), with one family of exceptions: `run_write_file` and
  `POST /api/file` refuse a file whose frontmatter says `modality: mirror`
  *and* which lives under the Canon store (`~/enough/canon/`), along with
  Canon's own catalogs and meta. That guard is
  `canon.catalog_write_denial(target, project_dir)` (returns the denial
  string or `None`; the `cacheawl.mirror_write_denial` shim alias was
  removed in 0.6); both write paths call it — see "Canon".
- **Merirmaid mode** (`#merirmaid-mode` in index.html) is a full-frame mode
  like girraph mode: lazy-loads `pele.global.js` on first open (730 kB —
  never at page load), renders the SVG with `links: false`, strips Mermaid
  `click "path"` lines itself and wires them by hand to push targets onto a
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
  Canon (`mmOpenFolderInCanon`); file: copy path / copy contents / open in
  its natural mode via the `canon:` scheme (`mmCanonBox`; the legacy
  `cacheawl:` it also accepted was removed in 0.6), and since 0.4.3 **atem** for a text (`mmAtemItem`).
  The menu resolves nodes through the mirror payload's `node_map`
  (`{nodeId → {path, is_dir}}`).
- **Volume mirrors are drawn on demand, never persisted** (0.4.3; until
  then the box-root `_cachebox.merirmaid` was written to disk).
  `GET /api/canon/mirror?volume=…&path=…`
  draws the volume root or a subtree fresh per request. The 30px
  **squircle** launcher on volume headers and folder tiles opens these in
  the view-only face.
- **Lens entries (0.4.3).** `enterMerirmaidLens(path, lens)` pushes a stack
  entry `{kind: 'lens', path, lens, lenses}`; `renderMerirmaidTop`'s `lens`
  branch fetches `GET /api/cosm/lens` and sets `MM_CURRENT.lens` and the
  `node_map`. `#mm-lens` (the toolbar `<select>`, `mmSyncLensPicker`) shows
  only for lens entries and redraws in place; crumbs read `<name> · <lens>`.
  A lens node's menu offers **show item** (back to the cosm viewer, focused
  on the card), **open file** when the item carries a `path:` (`fs_path`),
  **atem** for a text, and copy label. Mindmap lenses (EMF `map`) offer
  only copy label: `mmNodeId` parses flowchart node ids alone (a recorded
  follow-up).

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
  (`<project>/wiki/<slug>/`) or to Canon's machine-global `wiki` volume
  (`~/enough/canon/wiki/<slug>/`) — the reader's single save button
  opens a two-choice flyout. `save.save_article(project_dir, path, dest)`
  takes `dest` in `{"project", "canon"}` (the frontend sends `"canon"`
  since 0.4.3); `save.py` still accepts the legacy `"infoworld"` as an
  **alias** (the `"cacheawl"` alias was removed in 0.6), writes the registry
  tag `"canon"`, and an unsave drops any of the three tags — `"cacheawl"`
  and `"infoworld"` from older saves included, since those are a person's
  registry, not a name in the API. `save_article_to_dir`'s default dest
  is `"canon"`. History: the global destination moved from
  `~/enough/infoworld/wiki/` to the cacheawl store in 0.1.6 (the whole
  infoworld library dissolved into cacheboxes), and the store became Canon
  in 0.4.3 — see "Canon".
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

## Canon (the machine-global library, 0.4.3)

**Cacheawl until 0.4.3**, renamed with compatibility shims that lived for one
release (in practice until 0.6, which removed them; the data migrations stay). Canon is three things under one name: the store at
`~/enough/canon/` where the user keeps text forever, the full-frame
two-pane file manager that browses it, and the de/recompiler that turns its
texts — and a project's — into fabula twins and atems (see "The
fabula"). The store's code lives in [enough/canon.py](../enough/canon.py);
`server.py` mounts `/api/canon/*` (the pre-0.4.3 `/api/cacheawl/*`
aliases were removed in 0.6) and hides the store (and a leftover
`~/enough/cacheawl/`) from every project tree. User-facing doc:
HELP_CENTER §12. Design record: `docs/canon-043-plan.md` and its
`docs/canon-landed-*.md` notes (local planning docs, untracked); its §14
lists the recorded follow-ups. A top-level folder is a **volume** — the
owner's word for UI copy and help; it was a *cachebox*. Code says `volume`
in new names, keeps `name` for the volume's name in `canon.py`'s public
signatures, and keeps `box` where it is on the wire. The catalogs' format
is spec §18.3 ([docs/MACROCOSM_OES.md](MACROCOSM_OES.md)).

**The store and its root.** `canon.root()` resolves `ENOUGH_CANON_ROOT` →
`~/enough/canon` (the legacy `ENOUGH_CACHEAWL_ROOT` fallback was removed in
0.6). On the default path only, the **one-time folder rename**
(`migrate_store_folder`): `~/enough/cacheawl` exists and `~/enough/canon`
doesn't → `os.rename`, one INFO line; **both exist** → `canon` is used and
one WARNING per process names both — never merged, never deleted; a failed
rename logs and keeps using the old folder. Never a symlink (cloud sync
breaks them).

```
~/enough/canon/
  rust-book/                 a volume (a top-level folder)
    canon.cosm               its catalog: visible, backend-owned, write-refused, regenerated
    .canon.json              meta: origin, status, ingest progress, fingerprint (hidden)
    ch01/…                   contents
    notes.md                 a text
    notes.md.fabulan.cosm    its fabula twin (hidden behind notes.md in listings; `notes.md.cosm` before 0.6)
  wiki/<slug>/article.html   saved wiki articles (the `wiki` volume)
  my-company/                a Holotype dropped in or ingested as a volume
    holotype.cosm            → the folder shows the holotype tag and opens in the cosm viewer
```

**Per volume, on its first reconcile or regenerate**: `.cachebox.json` →
`.canon.json` (`os.replace`, only when the new one is absent; `load_meta`
reads either until then); `_cachebox.merirmaid` is deleted only when its
frontmatter says `modality: mirror` (a non-mirror file of that name stays);
then `canon.cosm` is written, because a missing catalog always regenerates.

**Volume catalogs.** `regenerate_catalog(name)` writes `canon.cosm` (the
pure text is `build_catalog(name)`) with `macrocosm.dump`, tmp +
`os.replace`, **only when the bytes differ**, under a module lock. Keys:
`oes: canon/1`, `macrocosm: 0.6.0`, `id: canon/<slug(name)>`, `name`,
`scope: volume`, `origin` (None fields dropped), `status`, `created`,
`updated`, `counts {folders, files, articles, twins, atems}` (`twins` =
files with a fabula twin, `atems` = files carrying an atem), `nodes`.
`created`/`updated` are the meta's timestamps and the only times in the
body (no `mtime` on items); `updated` moves only when the content
fingerprint does, so reruns are byte-stable. Items are module `V`:

| Kind | Fields |
|---|---|
| `folder` | `parts` (listing order), `parent`; a folder holding `holotype.cosm` is one item with `holotype: true` and no `parts` — not recursed |
| `file` | `size`, `kind` (`canon.file_kind`), `twin {path, state}` for a convert twin, `fabula {path, state}` for a fabula twin (`emf {path, state}` in catalogs written before 0.6, still read: `canon.item_fabula`), `atem {line}` copied from the twin's `atem.line`; on an old-named twin that a new one superseded, `note: "an old-named twin, kept as an ordinary file: the twin of <text> is <new>"`; `short_of: <text path>` on a short beside its text and `shorts: [<paths>]` on that text (`canon.SHORT_RE`, `canon.short_text_name`; paths only, so the project catalog keeps them too) |
| `article` | a saved-article folder (`article.html` + `.meta.json`): `title`, `source`; not recursed |

Convert twins with their `.assets`, and fabula twins, are never items (they
hide behind what they belong to, as in the trees). Ids are
`V:<kind>/<slug>`; `canon.slug()` respells the relative path (`/` → `--`,
`.` → `-`, lowercase, anything outside `a-z0-9-` → `-`, hyphens trimmed at
both ends), and `item_slugs()` gives **each** colliding path
`-<sha6(path)>` — likewise a Windows-reserved slug (`con`, `aux`, …,
which the path grammar refuses) or an empty one. Cap `CATALOG_ITEM_CAP` =
5 000, walked breadth-first so shallow structure survives: a folder whose
contents would pass the cap is listed alone, with `counts {folders, files}`
and `pending: "too many files to enumerate here; open the folder in
Canon"`. Regenerated by create, rename, transfer (every touched volume),
each ingest stage, `migrate_infoworld`, every derive/atem/pin/compile write
in the volume, and `reconcile` on fingerprint drift, a missing catalog, or
a catalog whose sha differs from the one last written — somebody else's
edit is overwritten.

**The project catalog, `rness/canon.cosm`** (owner decision 16). The same
`canon/1` enumeration with `scope: project` and `id:
canon/~<slug(project name)>` (`~` never appears in a volume name), over
exactly what the sidebar shows — `home._mirror_skip(project_dir)` — minus
the top-level `rness/` (enough's machinery, and the catalog's own home; a
nested folder named `rness` is enumerated). **Structure only**: no `size`,
`mtime`, `created`, `updated`, `origin` or `status`, and `twin` / `fabula`
carry `{path}` with no state, so it changes only when files are added,
removed or renamed or twins and atems change, and a project under git sees
no churn from ordinary edits. `canon.project_catalog(project_dir, *,
write=True)` builds it and writes — only into an existing `rness/`, only
when the bytes differ. **Its triggers, all of them**: the server lifespan in
project mode (a background `asyncio.to_thread` task startup does not wait
for), `GET /api/canon/tree`, any `/api/cosm*` read of `rness/canon.cosm`,
`GET /api/canon/project-catalog`, and the end of every derive / atem / pin
/ compile in the project (a readvisor tool's write included). **Never** from
`/api/files` — the 3-second sidebar poll — or from `build_file_tree`; a test
deletes the file, polls `/api/files`, and asserts it stays gone. The home
screen's project map does not read it yet (still `folder_flowchart`; a
recorded follow-up).

**The on-demand mirror.** No merirmaid mirror is persisted any more.
`GET /api/canon/mirror?volume=&path=` draws the volume root or a subtree fresh
per request through `canon.build_mirror(name, subpath)` (over
`folder_flowchart`, the walker `home.py` also uses), with the payload it
had — `text`, `node_map`, `modality: mirror`, `subpath` — and `volume_path`
(0.4.3 also sent `box_path`, the same value, for one release; removed in 0.6). The MacroCOSM
view of a volume is its catalog's lenses (`/api/cosm/lens`).

**Listings.** Two trees share the rules in `canon.py`: `_scan_tree` (the
Canon grid, via `volume_tree` and `GET tree`) and `server.build_file_tree` /
`_walk_tree` (the project sidebar).

| Flag | Set on | Canon grid | Sidebar HTML (`_tree_to_html`) |
|---|---|---|---|
| `catalog: true` | a volume's root `canon.cosm`; the project's `rness/canon.cosm` | `cosm` glyph + "catalog" tag; double-click → the cosm viewer | `data-catalog="1"` |
| `cosm: true` | any other `*.cosm` | the `cosm` badge; → the cosm viewer | `data-cosm="1"` (a row click opens the viewer) |
| `holotype: true` | a folder holding `holotype.cosm` | `children: []` (not recursed), "holotype" tag, opens in the cosm viewer | `data-holotype="1"` on the dir `<li>` (contents still shown) |
| `emf: {path, state, flavour, others?}` | a text whose fabula twin sits beside it (the twin row is hidden); `others` lists a second twin of the other flavour. The listing key keeps its 0.4 name on the wire (pins P1.10) | `.cn-emf` badge button (opens the text with its fabula's face) | `data-emf`, `data-emf-state` |
| `old_twin: {of, twin}` (0.6) | an old-named `X.cosm` beside a flavour-named twin of the same text: listed as an ordinary file, with a note | — | — |

The twin rule, both trees (since 0.6, `fabula_names.folder_twins`):
`X.fabulan.cosm` or `X.fabulap.cosm` beside a file `X`, or the old name
`X.cosm`, whose first 8 lines declare `oes: fabula/1` or its old spelling
`oes: emf/1` (`macrocosm.sniff_declaration` — no YAML load during a tree
build). A fabula is identified by its declaration, never by its file name.
When a flavour-named twin and an old `X.cosm` both exist, the flavour-named
one is the twin. A text may have one twin per flavour; the single slot a
listing shows is the one derived last (`fabula_names.primary`). A
`X.fabulac.cosm` is a folder's, never a text's. State: `fresh` when the text's size + `mtime_ns` match the
twin's `source:`, else a sha256 compare, else `stale` (also `stale` when the
twin has no readable `source:`); `canon.emf_state` is the one rule
everything uses, and listings never write a twin. (Every node carried
`is_mirror`, always `false`, for one release; removed in 0.6.) Volume summaries gain `catalog: "canon.cosm"`
and `holotype` (the volume's root itself holds one). The Canon grid still
shows convert twins (unchanged); only the catalogs hide them.
`home._mirror_skip` now also hides fabula twins and paginated `X.pdf.pages/`,
so "what the sidebar shows" is exact again for the project map and the
project catalog.

**Routes.** Every handler answers under `/api/canon/*`, registered by
`server._canon_route` (0.4.3 stacked each pre-0.4.3 handler under
`/api/cacheawl/*` too, for one release; 0.6 removed those aliases). The
routes 404 in home mode. A volume is `volume` on the wire, in a query, a
body, a transfer's `src`/`dst` and an answer, and the tree's list is
`volumes` (0.7; the old keys answer until 0.8 through
`retired_names.FIELDS`, and the page sends only the new ones).

| Endpoint (`/api/canon/…`) | Method | Purpose |
|---|---|---|
| `tree` | GET | Split-view payload: project tree + every volume summary and tree in one call (key `volumes`). Reconciles every volume and the project catalog first |
| `create` | POST | `{name}` → a new empty volume + its catalog. Names: letters/digits/spaces/hyphens/underscores, no leading symbol, ≤ 64 chars; 400 bad/duplicate |
| `rename` | POST | `{name, new_name}`; 400 if the target exists (and for a missing volume, as before) |
| `delete` | POST | `{name, confirm: true}` — unconfirmed → 400, missing → 404; a permanent whole-folder delete the UI gates behind a confirm |
| `transfer` | POST | `{op: copy\|move, src, dst, overwrite?}`, each side `{root: project\|canon, volume?, path}` (the legacy `cachebox` for `canon` was removed in 0.6). Traversal-checked both sides; catalogs, meta and legacy mirrors refused as source or destination; no clobber without `overwrite: true`; regenerates each touched volume's catalog (`volumes_updated`; the `boxes_updated` beside it was removed in 0.6) |
| `ingest` | POST | `{volume, type: path\|url\|wikisink, value, depth?\|all?}` — the volume is registered `ingesting` synchronously, the work runs in a thread. `all` invalid for wikisink |
| `ingest-status` | GET | `?volume=` — poll while `ingesting`; failure ends `status: "failed"` + `ingest.error`, never a phantom complete |
| `mirror` | GET | `?volume=&path=` — the on-demand root or subtree mirror above; 404 for a missing volume |

| New route (no alias) | Returns |
|---|---|
| `GET /api/canon/catalog?volume=` | `{volume, path: "canon:<v>/canon.cosm", text, parsed: {catalog (no nodes), items}, problems}`; reconciles first; 404 missing volume |
| `GET /api/canon/project-catalog` | `{path: "rness/canon.cosm", text, parsed, problems}`; reconciles first |
| `GET /api/cosm`, `GET /api/cosm/lens`, `POST /api/cosm/lint`, `GET /api/macrocosm/manifests`, `GET /api/macrocosm-spec` | the MacroCOSM read routes — see "MacroCOSM" |
| `atem`, `atem/pin`, `job/{id}`, `job/{id}/cancel` under `/api/canon/`; `derive`, `twin`, `compile` under `/api/fabula/` (0.6; `/api/canon/derive`, `/api/canon/emf` and `/api/canon/compile` answer through 0.6) | the derivation routes — see "The fabula" |

Errors: `canon.CanonError` → 400; its subclass `CanonNotFound` (a missing
volume or folder) → 404 — routes no longer match "no cachebox" in prose.

Volume summary fields worth knowing: `origin.type` ∈ `folder` | `path` |
`url` | `wikisink` | `infoworld-migration`; `origin.depth` is 1–3, `"all"`,
or null; `status` ∈ `complete` | `ingesting` | `failed`; `ingest.phase`
walks queued → starting → copying/crawling/expanding →
capped/complete/failed. Ingest semantics: `path` copies text files
(binaries skipped by extension + null-byte sniff), never follows symlinks
out of the source root; `url` is a same-origin crawl to `depth` link
layers, robots.txt respected, pages pandoc'd to markdown; `wikisink`
fuzzy-matches an article then expands crosslinks `depth` layers.

- **`canon.py` owns everything under the store.** The only other writers
  are the derivation routes and the MacroCOSM tools, which write twins and
  compiled texts *into* a volume and then hand back to
  `canon.regenerate_catalog`. Use `ENOUGH_CANON_ROOT` in tests and scratch
  runs; never touch real user state.
- **Write-guards.** `canon.catalog_write_denial(target, project_dir)` —
  called by `POST /api/file` and `tools.run_write_file` before allowlist
  resolution — refuses a volume's `canon.cosm`, the project's
  `rness/canon.cosm`, `.canon.json` and `.cachebox.json` by name anywhere,
  `_cachebox.merirmaid` under the store, and any `modality: mirror`
  `.merirmaid` under the store. The message is `error: this catalog is kept
  by enough; change the files it lists instead.` plus one sentence naming
  the file (the mirror's still says `modality: mirror`). `is_catalog_file`
  is the predicate. Don't add a code path that writes these from anywhere
  but `canon.py`.
- **The `canon:<volume>/<rel>` path scheme** (`cacheawl:<box>/<rel>` was
  accepted for one release and removed in 0.6) (`server.STORE_PREFIXES`, `_store_prefix`;
  `canon_tools.STORE_PREFIXES` is a copy, and a test keeps the two equal
  because `canon_tools` must not import `server`). `_resolve_project_path`
  resolves the remainder against `canon.root()` — that is how Canon
  launches store files into read/edit, girraph, merirmaid and the cosm
  viewer, and how `/api/cosm*`, the derivation routes and the readvisor
  tools take store paths. Same traversal rules inside the store (absolute /
  `..` / empty → 400); the write-guards downstream see the resolved target.
  In-tree relative paths never reach the store — the prefix is the only
  door. The highlights routes pass a store path's resolved absolute location
  as `doc_rel` (before 0.4.3 `cacheawl:x/y.md` made a folder literally named
  `cacheawl:x` inside the project); convert and both paginate routes refuse
  the prefix.
- **Ingest runs in the background.** The volume is registered synchronously
  with `status: "ingesting"` before the response returns (so
  `GET /api/canon/ingest-status?volume=…` is immediately pollable); the work runs
  in a thread; failure ends `status: "failed"` with `ingest.error`. Caps:
  `INGEST_URL_PAGE_CAP` 500, `INGEST_WIKI_ARTICLE_CAP` 200,
  `INGEST_PATH_FILE_CAP` 20 000. URL ingests reuse the `fetch_url` plumbing,
  so they honor the `fetch_url_*` toggles *on top of* `canon_enabled`.
- **The Holotype filter (privacy).** In any folder of a `path` ingest that
  holds `holotype.cosm`, `_ingest_path` skips the files the comprise
  manifest's `volume.outside-the-model` names (`people.yaml`,
  `people.proposed.yaml`, `logo.svg`, `logo.png`) and its `volume.database`
  (`store.sqlite`), any `people*.yaml`, and prunes the folders it names
  (`feeds/`, `scans/`, `bindings/`, `reports/`) plus `snapshots/` without
  descending. People never leave Comprise. Read through
  `macrocosm.default_registry()`, with a hard-coded fallback carrying the
  same lists if the manifest can't be read.
- **Reconcile keeps catalogs honest.** `GET /api/canon/tree` and
  `canon_list <volume>` call `reconcile()` / `reconcile_all()` first — a
  cheap fingerprint check. Reconcile skips a volume mid-ingest, whose catalog
  is the one written at registration (`status: ingesting`).
- **Transfer is single-item** — a file or folder between the project and a
  volume (either direction) or between volumes.
- **The infoworld migration** (0.1.6) still runs at startup:
  `canon.migrate_infoworld()` dissolves `~/enough/infoworld/{personal,
  public,wiki}` into three same-named volumes, move-only and idempotent; its
  source root honors `ENOUGH_INFOWORLD_ROOT`.
- **Tools and the toggle.** `canon_list` / `canon_create` / `canon_ingest`
  (`tools.run_canon_*`, inner tag `<volume>`; the old `<box>` was removed in 0.7),
  renamed outright with no `cachebox_*` aliases (the docs ↔ dispatch drift
  tests would flag one), documented in the "## canon" section of
  `prompt.TOOL_INSTRUCTIONS`. Broker toggle `canon_enabled` ("canon tools",
  group `canon`); `broker.load_config` moves a stored `cacheawl_enabled` to
  it once and rewrites the file (a person's setting, so this migration
  stays; the `denial_cacheawl_disabled` alias was removed in 0.6). The MacroCOSM tools' store writes ride on the same
  toggle.
- **The shim, `enough/cacheawl.py`** (77 lines, 0.4.3 to 0.6; its docstring
  said one release): explicit re-exports of every public name of the old module onto
  Canon's — `box_dir` → `volume_dir`, `regenerate_mirror` →
  `regenerate_catalog`, `is_mirror_file` → `is_catalog_file`,
  `mirror_write_denial` → `catalog_write_denial`, the six `*cachebox*` CRUD
  names → `*_volume` / `list_volumes`, `CacheawlError = CanonError`, the rest
  (`root`, `load_meta`, `save_meta`, `folder_flowchart`, `build_mirror`,
  `transfer`, `reconcile`, `run_ingest`, `migrate_infoworld`, the constants
  …) as-is — plus `_require_box`, `_node_id` and `_content_files` for
  `tests/test_cacheawl.py` / `test_cacheawl_api.py`, which stayed as
  compatibility tests and went green through it. Its `META_NAME` was the new
  `.canon.json`. New code imports `canon`. **Removed in 0.6**, with those
  two test files (the owner's ruling for the fabula round).
- **The UI** is the full-frame split-view mode `#canon-mode` (mode-stack
  name `canon`, launcher `#canon-btn`, ids `cn-*`, functions `cn*`, state
  `CN_*`, i18n keys `cn.*` / `menu.cn.*` / `modes.canon.*` /
  `topbar.canon.*` / `wiki.saveCanon.*`; renamed from `#cacheawl-mode` /
  `ca*` / `CA_*`). The icon files keep their names (owner decision):
  `cacheawl.svg`, `cachebox*.svg`, `savewiki-cacheawl.svg`, the
  `data-icon="cacheawl"` indicator, and the saved-article update chip
  `#wiki-cachebox-update`. A project pane and a store pane,
  drag-to-copy / shift-drag-to-move (both `transfer`), an ingest bar that
  composes a chat request into the readvisor panel (`cn.ingest.request`,
  translated), per-file open into the natural mode via the `canon:` scheme
  (`cnLaunchFile`, `cnTilePath`), failures as `cnNotice` toasts rather than
  `alert()`. 0.4.3 tiles: a catalog tile, `*.cosm` badges, Holotype folders
  (`cnOpenTile` → `enterCosmMode`; shift-click "browse files" / "open
  raw"), the `.cn-emf` badge; shift-click on a text adds **atem** and
  **decompile** / **refresh twin** (`canonMenuItems`). The project pane head
  has `#cn-project-catalog-btn` (→ the cosm viewer on `rness/canon.cosm`),
  the store pane head a `(?)` (`data-help="canon"`). Ingest progress is
  **polled** (`ingest-status`), not streamed.

---

## MacroCOSM (the `.cosm` grammar and its reader, 0.4.3)

**MacroCOSM OES** is an organizational enumeration system: the shared
grammar and its **core**. A domain is enumerated as plain-text `.cosm` files
— a restricted YAML subset, no anchors, aliases, tags or multiple
documents, YAML 1.2 booleans — that are at once a file system and a
relational database, made to be rendered. The core holds the grammar's
parts, **five built-in formats** — `cosm/0` the product tree, `canon/1`
Canon, `fabula/1` the fabula, `doc/1` documents (DocOES), `thym/1` Thym's
volumes — the densities and the dialectic; a **MiniCOSM** is a domain's
OES with a specification of its own, and there are exactly two, `comprise/1`
(companies) and `ascribe/1` (a person). A built-in is never called a
MiniCOSM; "format" names either. A **manifest** declares a format (its own
id on disk stays `manifest: minicosm/0`, the old spelling of "manifest
format 0", so every existing manifest still loads; `core: true` marks a
built-in); a **volume** is one database of it — a folder, or a single
catalog file — whose catalog's first key names it (`oes: <format>/<major>`).
Items are mappings in a
`nodes:` list with a stable id `<module>:<kind>/<slug>` and a `type`;
references are fields and typed links (`{rel, to}`), never operator glyphs;
an unknown value is an open question (`{pending: "<the question, for whoever can answer it>"}`),
never a guess. The spec is [docs/MACROCOSM_OES.md](MACROCOSM_OES.md), synced
from cosmoes.org (its edition is in `docs/specs.json`):
§2 is the model on one page, §4 the file format, §5 the declaration, §11
ids/paths/URIs, §12 the checks, §13 the manifest, §14 renderers and lenses,
§18 the core (18.1 the core and its registry, 18.2–18.5 and 18.7 the five
built-ins, 18.4 the fabula with 18.4.6 verse and 18.4.7 code, 18.6 the
dialectic) and §19 the two MiniCOSMs, the seven formats enough ships, each
with an example (complete files for cosm, canon, fabula, doc, ascribe and
thym; a Holotype is a folder, so comprise's is a fragment); §20
conformance, §21 Changes. This
section summarizes and points; read the spec before you change the format, a
manifest or the reader. User-facing doc: HELP_CENTER §13 (the dialects; §13.1–13.2 the docs viewer)
and §12.3 (Holotypes and other `.cosm` files). Comprise (comprise-dev) is
the reference implementation of the first MiniCOSM and stays read-only from
here.

**The spec rule: the reader wins.** Where `docs/MACROCOSM_OES.md` and
`enough/macrocosm.py` disagree, the code is right and the spec is corrected
(spec §20.4 says how a disagreement is settled). `tests/test_macrocosm_spec.py`
loads every ```` ```cosm ```` block in the spec and holds it to the spec's own
promise — one complete file that loads, is not refused, and passes its
MiniCOSM's checks with every reference resolving inside the block — so an
edited example, or a reader change that breaks one, goes red. Fences:
`cosm` only for complete files, `yaml` for fragments, `text` for grammar.

### The reader, `enough/macrocosm.py`

~2 650 lines. **PyYAML + stdlib only, and it imports nothing from enough**
(a test parses its imports) and reads nothing under `$HOME` (a test greps for
`Path.home` / `expanduser`), so the file can be vendored into another repo
whole (comprise-dev is meant to — a recorded follow-up). `pyyaml>=6.0` is
declared in `pyproject.toml` (it was already in the lock transitively; no
DMG growth). It never writes a file — `dump` hands a writer the text — and
bad input never raises: a file that does not parse is a `Problem`, a
declaration it cannot read is a `Refusal`; only programming errors raise.

| API | What it does |
|---|---|
| `yaml_load(text)`, `read_text(path)`, `dump(mapping)` | Comprise's loader exactly (SafeLoader minus the YAML 1.1 bool resolver, so `yes`/`no`/`on`/`off` stay strings; timestamps → `datetime.date`); utf-8-sig + universal newlines; `safe_dump(sort_keys=False, allow_unicode=True, width=110)` with the declaration key first and never an anchor |
| `sniff_declaration(path, lines=8)` | `"fabula/1"`, `"emf/1"`, `"cosm 0.3"` … from the first 8 lines, no YAML — what tree builds call |
| `Registry(dirs)`, `default_registry()`, `load_manifest(path)` → `Manifest` | every `*.manifest.cosm` in order comprise, cosm, canon, fabula, doc (`REGISTRY_ORDER`), then by name; `.identify(catalog, filename=)` → `Declaration` \| `Refusal` (a `Declaration`'s `how` is `oes` for a format's own value, `old` for an old spelling its manifest lists in `declaration.old`, e.g. `emf/1` for the fabula); `.built_ins()` / `.minicosms()` (by the manifest's `core: true`); `.by_name()` / `.by_declaration()` (an old name finds its format); `.known()` (the refusal's list: `fabula/1 (also emf/1)`); `.find_catalog(folder)`; a second manifest naming a loaded format is skipped and reported. The registry also reads `core.modules.cosm` (the first manifest folder holding one) and gives its module D to every manifest that does not declare the letter, in memory (`Manifest.inherited`; the file is never touched), so D ids (`D:question/<slug>`, `D:session/<slug>`) parse in every format, a Holotype's and a COSM tree's included. `default_registry()` is cached and reads only `DEFAULT_MANIFEST_DIR` (`<repo>/defaults/cosm/manifests`) |
| `Manifest.banks()`, `own_checks()`, `kind_closed()`, `flavours` | (0.6) the dialectic's banks (named `dialectic.banks`, or Ascribe's older `dialectic.questions` read as one bank), the manifest's own check ids (listed `not_run` by this reader), a kind's own closed lists, the flavours a catalog may name (`flavour_of(catalog)`: its `flavour`, else `catalog.flavour-absent`, the fabula's `fabulan`) |
| `tree_digest(folder)` | (0.6) MacroCOSM's tree digest of a folder (appendix G's code, one function): `{files, bytes, skipped, tree, read}`; the digest a fabulac's `source.tree` holds. `enough/thym/folder.py` gives the same value |
| `load_volume(path, registry=None)` → `Volume` | never raises (OSError included). `Volume.items` is keyed by **`Item.key`** — the id for Canon, fabula and COSM trees, but `atom/<concern>//<id>` in a Holotype, where bare ids repeat across concerns; `volume.item(ref)` takes either. `problems`, `refused`, `declaration`, `catalog`, `parts`, `files`, `.by_module()` |
| `parse_path`, `item_path`, `resolve_path`, `items_under`, `qualified_uri`, `field_value` | paths (`<module>/<kind>/<slug>` through the manifest's levels, `#<field.path[n]>` for a field; Comprise prefixes the concern) and URIs (`oes:<minicosm>/<database>/<path>`) |
| `resolve_ref`, `walk_path`, `walk_pending`, `is_pending` | references (an id or `{rel, to}`; `None` for sentinels, open questions and parts) and open questions |
| `lint(volume)` → `Report` | `.errors .warnings .notes .pending .not_run .checks .ok`; `.to_dict()` is JSON-safe (`jsonable()` for dates) |
| `lenses(volume)`, `to_mermaid(volume, lens="map", *, max_nodes=200, clicks=False)`, `to_text_tree(volume)` | the renderers; both only read |

Two traps. **`Refusal` is falsy** — write `if vol.refused is not None:`;
`if vol.refused:` is always false. **`load_volume(folder)` looks for exact
catalog names in registry order** (`holotype.cosm`, `brand.cosm`,
`firm.cosm`, `canon.cosm`), so a Canon volume folder that also holds a
Holotype at its root loads as the Holotype — load `canon.cosm` by file to get
the catalog. A fabula twin is only ever loaded by its file
(`<text>.fabulan.cosm`, `<text>.fabulap.cosm` and the old `<text>.cosm` are
patterns, not names).

**The generic checks** (`macrocosm.CHECKS`; one `tests/fixtures/cosm/bad/`
volume and one test each): `load`, `duplicate-id`, `id-grammar`,
`id-module`, `type`, `type-prefix`, `identity-min`, `provenance`, `status`,
`visibility`, `ref-grammar`, `ref-unresolved`, `closed-list`,
`pending-shape`, `module-none`, `catalog-key`, and since 0.6 `flavour` (a
catalog's flavour outside the format's closed list) and `flavour-kind` (an
item of a kind outside the catalog's flavour, e.g. a `C:line` in a fabulan).
The core's three dialectic checks (`CORE_CHECKS`: `question-about`,
`question-shape`, `session-declared`) are not the reader's: `enough/fabula.py`
runs them, and the reader lists them `not_run` on any volume that holds a D
item. A manifest's `checks.envelope`
selects which run (`load` always does); all are errors except `module-none`
and `pending-shape` (warnings) and an unknown catalog key (a note), and
`checks.severity` overrides. A check id the reader does not implement is
listed in `not_run`, never silently passed — a Comprise Holotype lists 58
(Comprise's fourteen rules and its product-tree checks: owner decision 10,
"Comprise's own rules need Comprise"; enough does not reproduce them).
Report shape `{errors, warnings, notes, pending, not-run, ok}`; a problem is
`{check, item | file, field, message}`, an open question `{item, field,
question}`.

**Lenses.** `to_mermaid` returns `(body, node_map)`: a plain body with no
frontmatter, modules as subgraphs, items shaped by kind, reference fields
and typed links as labelled edges. `node_map[node] = {id, path, file,
fs_path}` (`fs_path` is the item's `path:` field, which Canon items carry);
past `max_nodes` a subgraph's remaining items collapse into one "… N more"
node (`id: None`, `more: N`). **`click` lines are off by default**: item
paths are not file paths, so a viewer resolves nodes through `node_map`. An
unknown lens raises `ValueError` — ask `lenses(volume)` first. Ids are stable
across runs. Per MiniCOSM: comprise `map`, `tree` (generic — its byte-copied
manifest declares none); cosm `tree`, `map`; canon `tree`, `map`; fabula
`claims` (a flowchart of E K P, edges `roles.*` + links, classed by stance)
and `map` (a mindmap of I L E K N C R P T).

**The CLI**: `python -m enough.macrocosm {lint,paths,tree,mermaid,identify}
<path> [target] [--lens ID] [--max-nodes N] [--json] [--manifests DIR]`.
Exit 0 ok, 1 errors / refused / nothing there, 2 an unknown lens.

### The manifests, `defaults/cosm/manifests/`

| Manifest | Declaration | Volume | Who writes it |
|---|---|---|---|
| `comprise.manifest.cosm` | `oes: comprise/1` (a `holotype.cosm` with no key, or the legacy `comprise: 0.1`, reads as it) | a Holotype: a folder, catalog `holotype.cosm`, one part per concern, modules C O M P R I S E (E is never in a file) | **synced, read-only**: a byte copy of comprise-dev's `oes/comprise-oes.manifest.cosm` (made by `scripts/sync_cosm.py`, retired in 0.5.4 and in git history at e318fcd). Never edit it here |
| `cosm.manifest.cosm` | legacy `cosm: 0.2` / `0.3` and `opi:` → `cosm/0` | a folder of `.cosm` files — the standalone product trees the context-ontology skill writes — module P, bare ids; `core: true` | written in enough |
| `canon.manifest.cosm` | `oes: canon/1` | one file, `canon.cosm` or `rness/canon.cosm`; module V; `core: true`; since 0.6 a file item's `fabula: {path, state}` (with `emf` kept, read) | written in enough |
| `fabula.manifest.cosm` (0.6; replaced `emf.manifest.cosm`) | `oes: fabula/1`, `old: [emf/1]`; a catalog `id: emf/<slug>` is read as it is (`catalog.id-old`) | one file, identified by its declaration: `<text>.fabulan.cosm`, `<text>.fabulap.cosm`, `<folder>.fabulac.cosm`, a standalone `<name>.fabulan.cosm` …, and the old `<text>.cosm`; catalog keys in order `oes, macrocosm, flavour, id, name, source, derived, atem, shorts, catems, nodes`; ten modules I L E K N C R P T X (the reader adds D), each kind's flavours noted; a `dialectic:` block of banks, one per flavour; `moves:` (derive, tell, atem, expand, and in `thym 1` survey and history); `core: true` | written in enough; own checks in `enough/fabula.py` |
| `doc.manifest.cosm` (0.4.4) | `oes: doc/1` | one file per telling, `<doc>.<lang>.doc.cosm`, built by enough into `ENOUGH_DOCS_ROOT`; modules S T R B | written in enough (see "DocOES") |
| `ascribe.manifest.cosm` (0.5.0) | `oes: ascribe/1` | a holograph: a folder, catalog `holograph.cosm` (the self: `id: ascribe/<hid>`, `handle`, `pseudonyms`, `sample`, no name), module folders A B C E I O Q S U Y (one kind each) and F (form, polyform, relation), and D for the dialectic; `links.starter`, not a closed `links.rels`; catalog `releases:` and `morphs:` (0.6); `dialectic:` (the 44 questions, read as the bank `ascribe`), `filter:`, `public-projection:` blocks (the isograph's and, toward 0.7, the allograph's schema; tokens withdrawn); catalog `subject` (0.7); `moves:` (`propose`, and the `project` extension that adds `as isograph` and `as allograph`) | written in enough; spec [docs/ASCRIBE.md](ASCRIBE.md); own checks in `enough/ascribe.py` (see "Ascribe's module") |
| `thym.manifest.cosm` (0.5.0) | `oes: thym/1` | one file of six kinds (`catalog.kind`: program, morph, context, plan, trace, package; a run's folder snapshot, `inputs/<name>.folder.cosm`, says `kind: folder`, which the manifest lists since 0.6, so lint is silent on one); modules P M C R K; a `moves:` block (the editing moves and the dialectic's three since 0.6); `core: true` | written in enough; spec [docs/THYM.md](THYM.md) §17 (see "Thym") |
| `core.modules.cosm` (0.6) | `modules-of: core` | **not a manifest**: the core's module D (`question`, `session`) and their closed lists keyed by kind; the registry gives D to every format that does not declare it | written in enough |
| `comprise.moves.cosm` (0.5.0) | `moves-of: comprise/1` | **a sidecar, not a manifest**: Comprise's Thym moves (`project`, `band`, `mark`, `withhold`), since its manifest is a byte copy; the registry glob passes it by and `thym.declarations` reads it | written in enough |

The six written here carry a comment header, `macrocosm: 0.6.0`, a `spec:`
naming the text's cosmoes.org home (`https://macro.cosmoes.org/`,
`https://thym.cosmoes.org/`, `https://ascribe.cosmoes.org/`; the bundled path
in the comment beside it) and the © line, and no round language ("a later
round", "built in 0.5.0" — 0.5.4 removed it; a gap is "reserved for a later
edition"). Since 0.5.0 a manifest may end in a `moves:` list (THYM.md §17.6;
spec §13.4): the generic reader keeps it as an unknown key and the Thym compiler
reads it. **The grammar version (0.6.0):** `MACROCOSM_VERSION = "0.6.0"` is what
enough writes into every catalog it makes (`canon.py`, `canon_derive.py`,
`docoes.py`); `MACROCOSM_VERSIONS = ("0.0.1", "0.0.2", "0.5.4", "0.6.0")` is
what the reader reads unchanged. 0.6.0's changes are additive (the core and its
built-ins, old spellings such as `emf/1`, module D in every format, references
by address), so every volume in people's Canon written under 0.0.1, 0.0.2 or
0.5.4 opens as it did. A catalog's or a manifest's `macrocosm:` outside the set
is a `macrocosm-version` **note** (`_version_note` in both loaders,
`Registry.notes` for a manifest), never a refusal. The texts' editions (0.6.0
for all four, in `docs/specs.json`) are a separate field, not the grammar version: `docoes` no longer reads
`MACROCOSM_VERSION` for a document's version. The optional keys 0.0.1 adds, which the reader reads (spec §13.5):
`volume.single-file`, `renderers[].lens`, `links.rels`, `closed-lists`,
`checks.severity`, `module-file.items`, a kind's own `required`, and
`catalog.<key>` closed lists (Canon's `scope` and `status`). A folder for a
person's own manifests, `~/enough/cosm/manifests/`, is mapped, not built:
the registry takes explicit dirs only. The folder, like the spec, is all
rights reserved (`defaults/cosm/NOTICE.md`; see "License").

**To add a format** (a MiniCOSM is a domain's, with a specification of its
own; a built-in is the core's, and is added only by MacroCOSM's own text):
write `<name>.manifest.cosm` in the `minicosm/0` key shape (copy
`canon.manifest.cosm`; `core: true` only for a built-in; a renamed format
keeps reading its earlier declarations through `declaration.old`, never by
rewriting a file), give it a subsection of spec §19 (a built-in: §18) with at
least one complete ```` ```cosm ```` example (so `test_macrocosm_spec.py`
holds it; give `_file_name` there its catalog name, and raise the example
count in `tests/test_docoes.py`), and add fixtures and tests beside the others in
`tests/test_macrocosm.py` (the registry tests count the manifests: seven, the core's five and the two MiniCOSMs). Nothing below the manifest needs code — the
checks, paths, the viewer, the lenses and the tools are generic.

### Fixtures, and the syncs

**The Comprise fixtures** (`tests/fixtures/cosm/`) are byte copies from
comprise-dev: for each Holotype on an **allowlist** (meadow, mozilla, wikimedia,
khan-academy) only the model — `holotype.cosm`, `atoms/**/*.cosm`,
`atoms/**/README*` — under `holotypes/<name>/`; the COSM 0.2 example tree under
`cosm02/meadow/`; and `manifest.json` (source commit, every file's sha256, a
digest). The script that copied them, `scripts/sync_cosm.py`, **retired in
0.5.4** with the chapters it also carried (git history at e318fcd has it,
should the samples or `defaults/cosm/manifests/comprise.manifest.cosm` ever
need refreshing); the fixtures stay as they are, and `tests/test_macrocosm.py`
still checks every copy against `manifest.json`. `tests/fixtures/cosm/NOTICE.md`
is hand-written. Beside the synced copies sit enough's own fixtures:
`canon/{rust-book,project}/canon.cosm`, `emf/{notes.md, notes.md.cosm,
standalone.cosm}` (kept as written: an `emf/1` twin under the old name, read
forever), and `bad/` (one volume per check, `flavour.cosm` and
`flavour-kind.cosm` since 0.6). The fabula round's own sit in
`tests/fixtures/fabula/` (the text's appendices byte for byte: a fabulan of
`guides/close.md`, a fabulap of a poem, `tally/` and its fabulac, a cshort's
head, a catem) and `tests/fixtures/dialectic/` (one answers volume per
flavour).

**The four public samples are the only Holotypes enough may hold.** The
allowlist stands though the script is gone: comprise-dev also holds private
client fixtures (its `fixtures/PRIVATE.md` says which), and nothing of theirs
may reach enough — not into tests, not into docs, not into a scratch run you
commit.

**The specifications' sync** (0.5.4) runs the other way, from cosmoes-site:
`scripts/sync_specs.py [--cosmoes DIR] [--check]` only ever **reads** a
cosmoes-site checkout (default `../../cosmoes-site`) and copies, byte for byte,
`specs/{macrocosm-oes,thym,ascribe,comprise-oes}.md` to `docs/MACROCOSM_OES.md`,
`docs/THYM.md`, `docs/ASCRIBE.md`, `docs/COMPRISE_OES.md` (the apex text `oes`
is not bundled) and `client/cosmoes_client.py` to `enough/cosmoes_client.py`,
and writes `docs/specs.json` (above). Exit 0 synced or nothing to do, 1
`--check` found a difference, 2 no checkout; a rerun over an unchanged checkout
writes nothing (the commit and date move only with a change). Run it before a
bump (desktop/RELEASE.md), and once more at the end of a round that edits a
text on cosmoes-site. Tests: `tests/test_sync_specs.py` (a fake checkout; the
shipped copies against `docs/specs.json`; `--check` against the real checkout
when one is beside this repo).

Conformance (`tests/test_macrocosm.py`, 212 tests + the grammar-version set and
the fixture guards; `tests/test_sync_specs.py`, 8; `tests/test_specs.py`, 7): the four load with 0 problems and 1 010 items (meadow 36, mozilla 524,
wikimedia 318, khan-academy 132 — measured against Comprise's own loader;
the plan's 1 070 was wrong), with the same open-question counts Comprise's
linter reports; every item's path round-trips id → path → id; every path
example in comprise-oes.md §6.7 resolves; the COSM 0.2 meadow tree loads as
`cosm/0`. Mozilla (524 items, 140 files) loads in ~0.27 s and lints in
~0.01 s more.

### Routes

Project routes unless noted; `path` is project-relative or `canon:`,
resolved through `_resolve_project_path`; the blocking work runs
in `asyncio.to_thread`.

| Route | Returns |
|---|---|
| `GET /api/cosm?path=` | a `.cosm` file or a volume folder → `{path, minicosm, major, title (the volume's name), manifest_title, uri, catalog (no nodes), modules: [{letter, name, subtitle, count, kinds: [{kind, items: [{id, key, path, name, summary, status, visibility, file, part, data}]}]}], problems, pending, lenses, report, files, refused, declared}`. `minicosm` holds the format's name (`fabula` for an `emf/1` twin too); `declared: {how, said}` says how the declaration was read (`how: old` for an old spelling); `report` is the volume's own (`fabula.lint` for a fabula, `ascribe.lint_holograph` with each finding's `advice` for a holograph, else `macrocosm.lint`). Modules in manifest order, every one even when empty (the core's D only when the volume holds D items); a refused volume is a 200 with `refused` set. A folder holding `holotype.cosm` loads as the Holotype; a store volume folder by its `canon.cosm`; any other folder by whatever catalog it holds; a volume catalog and `rness/canon.cosm` are reconciled first. A non-`.cosm` file is 400, a missing one 404 |
| `GET /api/cosm/lens?path=&lens=[&around=&depth=]` | `{text, node_map, lens, lenses, around}` (0.4.4: `around` = a key, id or path draws a local graph — the lens's edges `depth` steps out, 0–4, the centre in class `focus`; `around` in the answer is the centre's key or null): merirmaid frontmatter (`merirmaid: 1`, `title: <name> · <lens>`, `modality: mirror`, `kind: cosm-lens`, `source: <path>#<lens>`, `node-char-limit: 48`) + the `to_mermaid` body; 400 unknown lens / refused |
| `POST /api/cosm/lint` | `{path}` → the volume's own report (as `/api/cosm`'s: a fabula's own checks, a holograph's with `advice`, else the generic) `.to_dict()` + `path` |
| `GET /api/macrocosm/manifests` | `[{name, title, version, declaration, summary, core, old}]`, registry order (`core` true for a built-in; `old` the old spellings it reads) |
| `GET /api/macrocosm-spec?lang=` · `GET /api/thym-spec?lang=` (0.5.0) · `GET /api/ascribe-spec?lang=` · `GET /api/comprise-spec?lang=` (0.5.4) | one specification as raw markdown (`_spec_markdown(slug, lang)`): **the file DocOES builds from** — the copy synced from cosmoes.org when one is in use, else the bundled `docs/*.md` (`docoes.spec_source`) — with `/api/help-center`'s language whitelist (a `static/i18n/<lang>/<FILE>.md` would win; none ships, the specifications are English only); 404 with a sentence when the file is missing. **In `HOME_PATHS`**, open while agent-free. Since 0.4.4 the frontend reads the specifications through `/api/docs`; these routes are kept as the raw-markdown sources, like `/api/help-center` for the manual. `desktop/src-tauri/build.rs` stages the four files and `docs/specs.json` into the .app |
| `GET /api/specs-status` (0.5.4) | the launch check's report (`enough/specs.py`): `ran`, `reason` (`ENOUGH_SPECS_SYNC=0` / `preference off`), `checked`, `updated`, `unchanged`, `skipped`, `errors` (`[slug, kind, message]`), `elapsed`, `at`, `base`, `root`, `user_agent`, `enabled` (the preference), `allowed` (the seam), and `documents: {slug: {name, edition, revised, source: cosmoes \| bundled, path, home}}`. **In `HOME_PATHS`**; what the docs viewer's badge title says and what QA reads |
| `POST /api/cosm/inline {text, filename?}` · `POST /api/cosm/inline/lens {text, filename?, lens?, around?, depth?}` (0.4.4) | a volume read from text (`macrocosm.load_volume_text`, nothing written): `/api/cosm`'s payload with `path: "inline:<filename>"` (default `inline.cosm`; 400 no text, 413 over 256 KB, a refused declaration is a 200 with `refused`), and its lens. **Home-accessible** (the docs viewer's live examples) and open while agent-free |

A `.cosm` saved through read/edit is never refused for lint (the spec says
checks *may* gate writes; Comprise's "a write that adds an error is undone"
is Comprise's rule, not MacroCOSM's). Raw `.cosm` editing is plain text in
read/edit's edit face; there is no highlighter yet.

---

## DocOES (documents enumerated in their own grammar, 0.4.4)

**DocOES** (`oes: doc/1`, "Documentation OES") is one of the core's five built-in formats: one
markdown document taken apart into items — its sections (`S:section/<n>`,
numbered by the document's own numbering, `root`, `front`, or a slug), the
terms it defines (`T:term/<slug>`), its complete ```` ```cosm ```` examples
(`S:example/<n>`), the decisions of a "Decisions …" section or, since 0.5.4, of
a dated "Changes" section (`S:decision/<n>`, below), the help bubbles
(`B:bubble/<id>`, the manual only) — joined to the **reference** generated from
the format manifests (`R:minicosm`, `R:module`, `R:kind`, `R:list`, `R:check`,
`R:lens`, each with `provenance` naming the manifest path and a hash). The
kind keeps its name `R:minicosm/<name>` for every format, built-ins included,
so links into volumes built before still resolve; since 0.6 each such item
carries `core: true|false` (and the fabula's `old: [emf/1]`), the core's D
appears in every format as `R:module/<format>.D` with its two kinds, the
fabula's and the dialectic's checks are `R:check` items, and the exporter
groups the reference as the built-ins (5) then the MiniCOSMs (2)
(`docoes_html.FORMAT_GROUPS`). An overlay looks a format up by its name, then
by its old names, so a text that still says `emf` overlays the fabula. The
volume is the document's fabula; compiled "as told" it is the markdown again,
byte for byte (`compile_doc`; tested for the four specifications and all six
manual tellings). Spec: MacroCOSM OES §18.5 (`docs/MACROCOSM_OES.md`); plan:
`docs/docoes-044-plan.md` (local). User-facing: HELP_CENTER §13.1–13.2.

- **Documents** (`docoes.DOCUMENTS`, five, in this order). The four **OES
  specifications** (`Document.spec`), the canonical editions published at
  cosmoes.org and bundled byte for byte by `scripts/sync_specs.py` (0.5.4; see
  "The specifications from cosmoes.org" below): `macrocosm-oes` ("MacroCOSM
  OES", `docs/MACROCOSM_OES.md`, + the reference; its §, "README §" and P.N
  name sections of *other* documents and are never linked: `xref={"§": "",
  "README §": "", "P.": ""}`), `thym` ("Thym", `docs/THYM.md`), `ascribe`
  ("Ascribe", `docs/ASCRIBE.md`) and `comprise-oes` ("Comprise OES",
  `docs/COMPRISE_OES.md`, `own_p=True`: its P.N name its own chapter P, its §
  other documents). English only, no chapters, every plain use a mention;
  **names carry no number** — a document's `version` is its **edition**
  (`document_version()`: the synced `state.json`'s when a synced copy is in
  use, else `docs/specs.json`'s; 0.6.0 for all four), never `MACROCOSM_VERSION`
  (that is the grammar's). 0.6.0 counts: 125 / 56 / 11 / 53 (sections, terms,
  examples, decisions), 111 / 20 / 1 / 47, 45 / 15 / 1 / 22, 99 / 15 / 0 / 29.
  Then `help-center` — six tellings, `docs/HELP_CENTER.md` /
  `static/i18n/<lang>/help-center.md` with `static/help-docs.md` /
  `static/i18n/<lang>/help-docs.md`, `voice: rosa`, mentions counted
  "distinctive" (a plain use links only a name with a space, an inner
  capital/digit or a symbol). A translation takes its ids from the English:
  sections by number, terms by their place in the section, else the English
  item verbatim with `fallback: en` — so **a translated manual must mirror the
  English markdown's shape** (bold labels, term-shaped bullets), not only its
  headings. **Chapters are gone** (0.5.4): Comprise's texts were two synced
  read-only chapters of the MacroCOSM volume (`defaults/cosm/chapters/`,
  `scripts/sync_cosm.py`); Comprise OES is a document of its own now, and no
  registered document has chapters. The `Chapter` dataclass,
  `enumerate_markdown(chapter=)`, `compile_doc(chapter=)` and the exporter's
  chapter rendering remain, inert.
- **Where it is built**: `ENOUGH_DOCS_ROOT`, default `~/enough/docoes/`
  (`docs_root()`), one `<doc>.<lang>.doc.cosm` per telling, on first use and
  again whenever the digest moves (sha256 over the DocOES format number,
  enough's version, every source file — for a specification **the file
  actually read**, the synced copy or the bundled text, with its edition and
  revised date; for the manual also the editions of the documents its bubbles
  cite — and every manifest; `is_fresh` reads only the recorded digest). So a
  synced text picks itself up on the next open. `load_built(doc, lang)` =
  ensure + load, the `Volume` cached by mtime+size. Build ≈ 0.05–0.6 s a
  telling. Never committed, never in a file tree; `docoes.SOURCES` points the
  enumeration at another install root (the tests' miniature — which copies the
  real `docs/specs.json` so the editions resolve).
- **Writing for it.** A section's atem is its first sentence unless a
  `<!-- atem: … -->` comment is the first line under its heading; a term is
  defined by a bold first table cell, a `- **term** — definition` bullet, a
  paragraph opening `(A|An|The) **term** is|are|means|stands for …`, the "How
  to read this" table, or a `<!-- term: x -->` comment before a paragraph. Two
  definitions of one term are a `term-defined-once` warning. **Decisions**: a
  "Decisions …" section's numbered bold items, numbered as written; a
  **"Changes"** section (0.5.4: the texts' dated appendix, newest edition
  first — `**Edition 0.5.4 · 2026-11-03.** …` then a list; a qualifier after the
  date, `**Edition 0.5.4 · 2026-11-03, second revision.**`, joins the name) gives every item of
  every edition's list (numbered or bulleted, with or without a bold lead) and
  an edition's entry that has no list, numbered 1..N through the section, each
  with `edition` and, when dated, `dated` (`_decisions(changes=True)`,
  `_EDITION_HEAD`). **Cross-document citations** are written "<Name>
  (<home>), its section N": the core's `_SEC_REF` skips "its section N", and
  since 0.5.4 so do the exporter's `XREF_RE` and the viewer's `DOCS_XREF_RE`
  (a `(?<![Ii]ts\s)` lookbehind), so a text may cite another document's
  section without the number ever linking into the citing text. Since 0.7
  the core and the exporter skip it in all six languages, from one list,
  `docoes.OTHER_DOC_WORDS` (de *ihrem Abschnitt 4*, fr *sa section 4*, es
  *su sección 4*, ja *仕様書のセクション 4*, zh *它的第 4 节*; the
  convention for translators is in docs/I18N.md), and the viewer's
  `DOCS_XREF_RE` is to carry the same words;
  `tests/test_specs.py` checks that every section the four texts cite of one
  another exists in that document's headings (the texts are cosmoes-site's:
  a miss is reported, not fixed). DocOES's own checks (`lint_doc`):
  `atem-shape` (2–15 words, CJK 2–45 characters, a phrase, no final period, no
  ids or markup), `numbering`, `term-defined-once`, `unlinked-mentions` (a
  note), `empty-section`, `stale-provenance-hash`, `xref-unresolved`. The four
  specifications lint **0 errors / 0 warnings** at 0.6.0 (notes only); the
  manual has 4 known `term-defined-once` warnings (AGENT.md, MOTIVATION.md,
  council, input/) in every telling.
- **Bubbles about another document**: `BUBBLE_DOCUMENT = {"docs":
  "macrocosm-oes"}` — the docs viewer's bubble names the spec's section 2,
  so its "section N" become `xrefs` (`macrocosm-oes@0.6.0:section:2`, the
  edition in the reference), never `see` links into the manual.
- **The CLI rule.** `python -m enough.docoes build|lint|compile|inventory|
  status <doc> [--lang L] [--chapter SLUG] [--force] [--json]
  [--docs-root DIR]` — **always with `ENOUGH_DOCS_ROOT` (better: every seam
  of `scripts/smoke_boot.build_env()`, `ENOUGH_SPECS_ROOT` and
  `ENOUGH_SPECS_SYNC=0` included) pointed at a scratch dir**; without it the
  CLI builds into the real `~/enough/docoes/` and reads the real
  `~/enough/specs/`. `lint <slug>` and a byte-exact `compile <slug>` are the
  checks after a sync (every text is cosmoes-site's: a fault is fixed there).
- **The static export** (0.5.0, `enough/docoes_html.py`; lane X1, spec
  `docs/thym-landed-X1.md` §2): `python -m enough.docoes export <doc>
  <out-dir> [--lang L] [--densities short,atem,fabula] [--page
  short=short.html …] [--standalone] [--slug S] [--name N] [--version V]
  [--no-marks] [--reference] [--sources ROOT] [--docs-root DIR]`. `<doc>` is a
  registered slug or a markdown path inside the install (a path whose default
  slug is registered is that document: `docs/THYM.md` → `thym`, named "Thym";
  an explicit `--slug` naming a registered document exports the path ad hoc
  under that slug (0.5.1+, W1: so another checkout's text can be built as
  that document, `XREF_RULES` applied by slug); any other path is ad hoc —
  slug from the file name, name its H1, version the manifest named like the
  slug, if any). `--no-marks` leaves the margin marks (`<p class="docs-marks">`)
  out; `--reference` joins the R: items generated from the manifests to an ad
  hoc document. It builds the volume fresh into a **temporary directory**
  (never `docs_root()` unless `--docs-root` says so), reads it back through
  `load_volume`, and writes `<slug>/{short,atem,fabula}.html` — script-free,
  style-free fragments (`article.docoes`, one `<h1>`, the app's heading ids,
  xref and term rules ported from the docs viewer, every `href="#…"`
  resolving inside its fragment, no timestamps) — plus `docs.css` and a
  `manifest.json` merged across runs (`docoes-export/1`, sha256 per file).
  markdown-it-py renders (lazily imported; html off, so `<slug>`
  placeholders stay text). **cosmoes-site is the exporter's customer**
  (0.5.4): its `scripts/build_specs.py` runs this export once per text in an
  enough checkout to make the pages at macro./thym./ascribe./comprise.cosmoes.org
  and the apex; the apps' copies (enough's `docs/*.md`, Comprise's, Connect's)
  are synced *from* the site, never the other way. Nothing in the app calls
  it. Tests: `tests/test_docoes_export.py`.

### The specifications from cosmoes.org (0.5.4)

The four texts are edited only in cosmoes-site (`specs/`); enough bundles a
copy of each as the floor and refreshes it two ways.

- **At release time**: `scripts/sync_specs.py --cosmoes <checkout>` (above) →
  `docs/MACROCOSM_OES.md`, `docs/THYM.md`, `docs/ASCRIBE.md`,
  `docs/COMPRISE_OES.md`, `enough/cosmoes_client.py`, `docs/specs.json`.
- **At run time**: `enough/specs.py`'s **launch check**. At server start
  (home and project alike — the home screen opens the docs viewer too), when
  the preference is on and `ENOUGH_SPECS_SYNC` is not `0`, one daemon thread
  runs `CosmoesClient(base=ENOUGH_COSMOES_BASE or https://cosmoes.org,
  timeout=3, user_agent="cosmoes-client/1 (enough <version>)").sync(specs_root(),
  wants={slug: ["source"] for the four}, validate=docoes.validate_spec_source)`:
  one GET of `/manifest.json` (with `If-None-Match` once an ETag is kept; a 304
  means nothing moved), then one GET of `https://<host>/raw/source.md` per
  changed text, each verified against the manifest's sha256, size-capped,
  validated by a real DocOES build into a temporary docs root (`validate_
  spec_source`: UTF-8, a title, builds, loads, has sections — else the previous
  copy is kept), written whole, `state.json` last. Nothing of the user's is
  sent. The report lands in `_STATUS` for `GET /api/specs-status`; INFO when
  something updated, WARNING per error; `sync` never raises (a refused base is
  a `['*', 'client', …]` error line). One check per process
  (`launch_check` is a no-op the second time; `reset_for_tests()`).
- **Resolution** (`docoes.spec_source(slug)` / `spec_info`): `<specs
  root>/<slug>/source.md` when `state.json` lists the slug with a source
  sha256 that matches the file, else the bundled path; the edition, `revised`
  and `home` follow the same source (state.json's, else specs.json's). Since
  0.7 **the newer copy wins** (the same rule as Comprise's): the two editions
  compare as tuples of integers (`edition_key`, trailing zeros dropped), equal
  editions keep the synced copy (a later revision of the same edition), and a
  synced copy whose edition does not read never wins, so an app upgraded to a
  new major shows its own texts until a sync brings newer ones (the signed
  0.6.0 showed 0.5.4's until then). `spec_info`'s `set_aside`, also in each
  line of `/api/specs-status`'s `documents`, names the edition of an older
  synced copy the bundled text was preferred to. The
  catalog's `document` block carries `version` (the edition), `revised`,
  `source` (`cosmoes` | `bundled`) and `home`; `/api/docs`'s head carries it to
  the viewer, whose badge reads `<name> · edition <edition>`
  (`docs.badge.edition`, no "v") with the title "from cosmoes.org, revised
  <date>" or "bundled with enough <version>" (`docs.badge.fromCosmoes`,
  `docs.badge.bundled`). The `/api/*-spec` routes serve the same file.
- **Seams**: `ENOUGH_SPECS_ROOT` (default `~/enough/specs/`),
  `ENOUGH_COSMOES_BASE` (default `https://cosmoes.org`; the client accepts
  only that, a `.cosmoes.org` host, or `http://127.0.0.1…` / `http://localhost…`
  for a stand-in) and `ENOUGH_SPECS_SYNC` (`0` turns the check off).
  `tests/conftest.py` sets all three (`_STATE_SEAMS`, `_FIXED_SEAMS`:
  `ENOUGH_SPECS_SYNC=0`, `ENOUGH_COSMOES_BASE=http://127.0.0.1:1`), so does
  `smoke_boot.build_env()` (hence every uicheck and smoke server); a rig that
  wants the check on sets `ENOUGH_SPECS_SYNC=1` and points the base at its own
  loopback stand-in (`tests/test_specs.py`'s `Fake` is the pattern).
- **The preference**: `specs_sync`, a top-level ui.json bool (absent = on),
  `POST /api/ui-config {"specs_sync": bool}` like `agent_free`; the checkbox
  `#ui-specs-sync` in the UI window's controls row with the note
  `#ui-specs-sync-note` under it ("On launch enough asks cosmoes.org once for
  the specifications’ manifest and fetches only a changed text. Nothing of
  yours is sent."), global, so on the home screen too; takes effect at the
  next launch. HELP_CENTER §1.1 and §13.1 say so in six languages.
- **Tests**: `tests/test_specs.py` (the vendored client unchanged, one sync
  against a loopback stand-in — a changed text, an invalid one, a 304 on the
  second launch — the validator, the seams and the preference, the "its
  section" exemption in all three parsers, every cross-document citation
  resolving, the Changes decompiler), `tests/test_cosm_api.py` (the four
  routes, the synced copy served, `/api/specs-status`, the preference round
  trip), `tests/test_sync_specs.py`.

### Routes (all read-only, home-accessible, open while agent-free)

| Route | Answers |
|---|---|
| `GET /api/docs?doc=&lang=&density=atem\|short\|fabula[&section=][&module=]` | `doc` ∈ `macrocosm-oes`, `thym`, `ascribe`, `comprise-oes` (0.5.4), `help-center`; `lang` absent → the UI language, not one of the six → 404, a document without that telling → the author's with `requested_lang`. Head: `{doc, lang, requested_lang, density, id, title, uri, telling, tellings, document, chapters, built}`; **atem** + `items` (light: key, id, kind, module, name, atem, order, level, parent, number, anchor, chapter, fallback, in, of, defined_in); **short** + `sections` (telling order, `heading` + `body` verbatim, `mentioned_in`, `examples`) and `terms`; **fabula** = `/api/cosm`'s payload with `report = lint_doc`, `backrefs` (target → sources, minus `parts`/`parent`/`chapter`), `inventory`, `declared_lenses: [{id, kind, diagram, include, generic}]` (each lens's modules — the manifest's `include`, every module when none — and the reader's generic `tree`, `generic: true`; D3 0.4.4) and `page`. 202 `{building, progress}` while a build runs; 503 when it cannot be built. Payloads are JSON-encoded once per built volume |
| `GET /api/docs/status` · `POST /api/docs/build {doc?, lang?}` | every telling's `{built, fresh, digest, building, progress}` · start a background build (the UI window warms all ten: four specs + six manual tellings) |
| `GET /api/docs/lens?doc=&lang=&lens=&around=&depth=` | `/api/cosm/lens`'s shape for a doc volume (`map`, `graph`, `tree`; `graph` around an item by default) |
| `POST /api/docs/compile {doc, lang?, chapter?}` · `GET /api/docs/inventory?doc=&lang=` | the markdown, byte for byte · the inventory rows `{inventory, xref, id, kind, version, anchor, atem}` |

`POST /api/cosm/inline*` (see "MacroCOSM" → "Routes") serves the live
examples. `doc_lookup` (see "The fabula" → "The readvisor tools")
reads the same volumes through `load_built`, spec first, then the manual in
the live ui.json's language. Tests: `tests/test_docoes.py` (the enumeration,
the round trip, the real bubbles), `tests/test_docs_api.py` (routes, payloads,
the inline reader, the local graph, `doc_lookup`).

### The docs viewer

See "The help system" → "The docs viewer (0.4.4)" for its functions, its
three densities and its uicheck screens and scenarios.

---

## The fabula (twins, atems, shorts; on-demand derivation, 0.4.3, the fabula round 0.6)

**Decompile and compile.** An input — an essay, a poem, a folder of Python —
is **decompiled** into its **fabula**: everything found in it or derived from
it, enumerated as one `fabula/1` volume (a built-in of MacroCOSM's core). A
fabula is **compiled** back into a **short**, an entailment of it, and said
most plainly as an **atem**. Each step is an **entailment** (MacroCOSM OES
18.1): the whole entails what is made from it — an input its fabula, a fabula
a short, a short its atem, a fabulac a cshort or a catem; a projection is an
entailment made by rule. Three densities of one meaning: fabula · short ·
atem. For code the fabula is the spec (a **fabulac**), the short is source (a
**cshort**) and the atem's deep form is a **catem** (see "Building a
fabulac"). In Thym the moves are `derive` and `entail` (`tell`,
`entail`'s earlier spelling, reads as `entail` for good: see "Thym"); DocOES's
byte-exact `enumerate` / `compile` keep their names. A **twin** is the everyday word for
a text's fabula file kept beside it. Spec: MacroCOSM OES §18.4 (18.4.1 the
catalog, 18.4.2 the modules, 18.4.3 the conventions, 18.4.4 shorts, 18.4.5
examples, 18.4.6 verse, 18.4.7 code, 18.4.8 the checks) and §18.3.5
(atems). User-facing doc: HELP_CENTER §12.4 (a text's fabula: prose or
verse, old names, shorts), §12.5 (atems), §12.7 (a folder's fabulac),
§12.8 (cshorts and catems), §13.7 (the dialectic), §13.8 (a holograph and
Ascribe's rules) and §16.6 (where a job's model runs).

**The name.** The fabula was called EMF (*enumerated meaning fabula*) from
0.4.3 to 0.5.4, and EML before that; the 0.6 round retired the name. It
lives on only as the literal old spelling `oes: emf/1`, which every reader
reads forever as `fabula/1` (`how: old`), and in identifiers no person reads
(pins P1.10): the job kind `emf`, the listing key `emf: {…}`, `emf_path` in
the short compile's result (beside `fabula_path`), `canon_derive.derive_emf`,
`canon.emf_state`, the page's `emf-face`. Anything a person reads says
fabula. The EML aliases kept one release were removed in 0.6; an `eml/1`
file is not read.

**Flavours.** Which kind of input a fabula is of, the catalog's `flavour:`
(after `macrocosm`, before `id`): **`fabulan`** (narrative and non-fiction
prose), **`fabulap`** (poetry, metered verse, song lyrics), **`fabulac`**
(code). Absent — every `emf/1` file — it reads `fabulan`. Flavours are a
property of a fabula value in Thym, not type names. For a text the flavour is
the person's choice at decompile time (`flavour` on the route, `<flavour>` on
the tools; `fabulac` is refused for a text: "fabulac is the fabula of a
folder of code; a text is decompiled as fabulan (prose) or fabulap
(verse)"). With none given, a text with a twin keeps the flavour of the twin
it has (the one derived last), else enough suggests one
(`fabula_names.suggest_flavour`: `fabulap` when at least 4 non-blank lines,
at least 75 % of them at most 60 characters, at least two stanzas averaging
two lines or more, and no markdown heading, fence or table; `fabulan`
otherwise); the route answers `{job, flavour, suggested}`.

**The modules.** Ten, plus the core's D (see "The dialectic"). L E K P T X
and their kinds, fields and closed lists are exactly `emf/1`'s, so every old
twin is a valid fabulan; I N C R are new. A kind outside the catalog's
flavour fails `flavour-kind`.

| letter | module | kinds |
|---|---|---|
| I | Inspiration | `influence`, `allusion`, `occasion` |
| L | Lexicon | `term` (grounded in FEED) |
| E | Entities | `person`, `org`, `place`, `work`, `thing` |
| K | Concepts | `concept` |
| N | Intent | `aim`, `audience`, `use`, `requirement`, `decision`, `exclusion` |
| C | Construction | prose: `part`, `device`, `voice` · verse adds `line`, `metre`, `rhyme` · code: `file`, `component`, `interface`, `structure`, `behaviour`, `dependency`, `setting` |
| R | Production | `maker`, `change`, `phase`, `release`, `means`, `licence` |
| P | Propositions | `claim` (with its required **stance**: `axiom · observed · deduced · opinion · assumed · hearsay`), `reading` (prose and verse: an interpretation the text supports and does not state), `case` (code: an example with what is given and what is expected) |
| T | Transitions | `event` (in code: what happens, in order, when the program is used) |
| X | Atems | `atem` (pinned passage atems) |

An **atem** is the tightest fair, full, plain-English reduction of a text or
a passage: **the line** (one sentence of 15–25 words — in prose, "the atem"
means the line), then **focus** (≤ 2 sentences: what is happening, what the
author directs attention to), **push** (one sentence: what the author wants
the reader to take away, believe or do) and **pull** (one sentence: what the
reader should actually take away, naming hidden assumptions, opinion stated
as fact, dependencies). Those definitions are the owner's, word for word, in
the spec (§18.3.5), the prompts (test-asserted), the skill and the UI
tooltips — change one, change all four.

**The catalog**, in order: `oes: fabula/1`, `macrocosm: 0.6.0`, `flavour`,
`id: fabula/<slug>` (the text's path in its project or volume, by Canon's
slug rule: `guides/close.md` → `fabula/guides--close-md`; an old
`emf/<slug>` is read as it is), `name` (the text's first heading, else its
file name), `source: {path (relative to the twin), sha256, size, mtime_ns}`
(absent for a standalone; a fabulac's names a folder, see "Building a
fabulac"), `derived: {at, by (person, or the readvisor's name), model (model
mode only), route (local | cloud, model mode only), provider (cloud only),
mode: model|rules, completeness: full|atem|outline, chunks, dropped?}` (a
fabulac's adds `program`, `run` and `runs`, one entry per run that wrote into
it), `atem: {line, focus, push, pull}`, `shorts`, `catems` (fabulac only),
`nodes`. One-line flow mappings keep the header inside
`canon.TWIN_HEADER_LINES` (30), which is all a listing reads; an atem a model
wrote far too long can push the header past it, and the listing then shows
no line though the twin is fine. The checks are the generic ones plus the
fabula's own (`fabula.lint`; see the Code map), and the cosm viewer, the
`cosm_lint` tool and `POST /api/cosm/lint` all run them.

**Never automatic.** A twin or an atem is made only when a person asks (a
click, a menu, a selection) or a readvisor's tool call asks. Imports,
ingests, tree builds, listings and reconciles never call a model and never
derive anything.

### Names on disk, discovery, and old spellings

One helper holds every name: [enough/fabula_names.py](../enough/fabula_names.py)
(pins P3; never add a name rule anywhere else).

- **A text's twin** is `<the text's whole name>.<flavour>.cosm` beside it:
  `close.md` → `close.md.fabulan.cosm` or `close.md.fabulap.cosm` (no `.emf`
  extension anywhere). A text may have one twin per flavour; a single slot
  (the Canon chip, a listing's badge) shows the one derived last
  (`fabula_names.primary`), and every payload with the slot also names the
  other (`twins`, `others`). A converted original reads through its markdown
  twin: `report.pdf` → `report.pdf.md` → `report.pdf.md.fabulan.cosm` (no
  markdown twin yet → 400 "convert it first").
- **A fabula is identified by its declaration, never by its file name**
  (`fabula_names.declares_fabula`: `fabula/1` or `emf/1` in the first 8
  lines).
- **The old name** `<text>.cosm` (an `emf/1` twin of 0.4.3–0.5.4) is read
  forever. Nothing renames or removes it except **decompiling the text
  again**: `canon_derive.replace_twin` writes the new twin under the new name
  with the old twin's `shorts:`, pinned atems and dialectic carried over,
  loads it, and only when it loads clean (no refusal, no lint error) unlinks
  the old file (the result says `replaced: "notes.md.cosm"`); otherwise the
  old file stays. Everything else (an atem, a pin, a compile's `shorts:`
  entry) writes into an old twin in place, under its old name and
  declaration (an `emf/1` twin stays `emf/1`); listings, catalogs,
  reconcile, import and copy never write a twin. A fabulap decompile never
  touches an old (fabulan) twin.
- **Both present**: when `close.md.fabulan.cosm` and `close.md.cosm` both
  exist, the flavour-named one is the twin and the old one is listed as an
  ordinary file with a note (`old_twin` on a listing node; `note:` on a
  Canon catalog item).
- **A standalone fabula** (no `source:`): `<name>.fabulan.cosm` and so on;
  an old standalone `<name>.cosm` reads. **A folder's fabulac**:
  `tool/` → `tool.fabulac.cosm` beside it, never paired with a text.
- **Writers write only the new forms**: `fabula/1` with a `flavour`, a
  `fabula/<slug>` id; the old spelling only ever comes from a file that
  already says it. No migration: a reader never rewrites a declaration it
  did not write (pins P1.7).
- **Discovery sites**, all through the helper: the sidebar tree
  (`server._walk_tree`), Canon's grid and catalogs (`canon._scan_tree`,
  `_enumerate`), the volume mirror and the home mirror
  (`canon._volume_skip`, `home._mirror_skip`), the tools' `text_target`, the
  twin route, the compile's claim key, Thym's export and readings
  (`thym_api`), and a short's stem (`fabula_names.short_stem`:
  `close.md.fabulan.cosm` and `close.md.cosm` both give `close`).

**States.** `fresh | stale | absent` (`canon.emf_state` — see "Canon"); a
stale twin is kept and shown with its state and refreshed only on request.

**Where atems live: in the twin**, never in a new sidecar kind. A file's
atem is the twin's `atem:` block; asking for the atem alone makes a minimal
twin (`completeness: atem`, `nodes: []`; a new one is `fabula/1` with the
flavour asked), and `set_file_atem` on a full twin replaces only `atem:` (a
stale twin stays stale). A passage atem is shown in a card and written only
on **pin**, appended as `X:atem/<n>` with the passage's `span` (`pin_atem`,
`next_atem_id`; never touches an existing twin's `source:`). Every `X:atem`
is a person's pin: model-mode passage atems feed the file atem and are not
written, and a re-derive carries the old twin's `X:atem` items over (a dead
`of` reference becomes an open question). Canon copies a file's atem line
onto its catalog item. **Compile never overwrites**: a fabula → markdown
writes a new, visible short, `<stem>.short-<YYYY-MM-DD-HHMM>.md` beside the
twin (local time; `-2`, `-3` on a collision; `short_path`, which
`compiled_path` named for one release until 0.6), mirroring convert's
datestamped exports, and appends it to the twin's `shorts:` list (see
"Shorts" below).

### The engine

| Module | Role |
|---|---|
| [enough/canon_derive.py](../enough/canon_derive.py) | **Pure functions, no server imports**; every model call goes through an injected `complete(messages) -> (text, meta)` (or text). `derive_emf(text, *, source_name, source_stat, complete=None, lookup=None, by="person", rel_path=None, on_progress=None, should_stop=None, previous=None, flavour=None, route=None, provider=None, copyable=False, pron=None) -> (cosm_text, info)` — the name stays; it writes a `fabula/1` (`info`: `mode, model, chunks, items, dropped, normalized, continued, atem, counts, flavour, route, provider, whole`); `replace_twin(text, flavour, cosm) -> {path, removed}` (see "Names on disk"); `carry_dialectic` (a re-derive keeps the volume's D items, staling those whose item went); `derive_atem(text, *, context=None, complete=None, …) -> {line, focus, push, pull, stance_profile, mode, route?, provider?}`; `compile_short(volume_or_text, *, complete=None, source_name=None, order=None, source_text=None, now=None) -> (markdown, {order, mode, model, by, route?})` and `compile_text(…) -> markdown`; `record_short(twin_text, *, path, at, by, mode, order, route=None) -> twin_text`; `short_footer`; `default_order`, `source_path`, `short_path`; `pin_atem`, `set_file_atem`, `next_atem_id`; `read_source(path) -> (text, {sha256, size, mtime_ns})` of the very bytes decoded; `write_atomic` / `write_twin` (dotfile tmp + `os.replace`); `twin_path`, `new_twin_path`, `twin_state`; `chunk`, `candidate_terms`, `entity_candidates`, `outline`; `DeriveCancelled`, `DeriveError`; `TEXT_SUFFIXES` (`.md .markdown .mdown .mkd .txt .text`) |
| [enough/canon_prompts.py](../enough/canon_prompts.py) | plain strings, `.format` only: `EMF_SYSTEM` (< 2 000 chars, test-capped for small local models), `EMF_USER`, `EMF_CONTINUE`, `EMF_RESTART`, `EMF_RETRY`, `EMF_REPAIR`, `ATEM_SYSTEM`, `ATEM_USER`, `ATEM_WHOLE_USER`, `WHOLE_ITEMS_PROSE` / `WHOLE_ITEMS_VERSE` / `WHOLE_RULES` / `WHOLE_DIGEST` (0.6, the whole-text pass), `VERSE_SYSTEM` / `VERSE_USER` (0.6), `COMPILE_SYSTEM`, `COMPILE_USER`. Test-asserted: every system prompt names the six stances and rules out pronouns; the atem parts are the owner's definitions verbatim |
| [enough/canon_jobs.py](../enough/canon_jobs.py) | `CanonJobs`, convert's job-table shape: `start`, `snapshot`, `cancel`, `active`, `record`, and `holding(key)` — the per-file write claim; cooperative cancel through `JobContext.check()` / `should_stop()`; SSE event `canon`; 200 finished jobs kept for polling |
| `llm.complete` / `llm.reachable`; `model_route.make_complete` (0.6) | the one-shot door (see the code map), or a job's route (see "Models" → "A model route per job"): `meta = {model, route: local\|cloud, provider?, from_reasoning, finish_reason, usage?}` — `"length"` means cut off; `max_tokens` from `completion_budget` bounded by `/props` `n_ctx`; `reachable` is the cloud gate when `current == "opro-api"`, else local `/health`, where 503 "loading" is **not** ready |
| `dictionary.lookup_many(words)` | FEED grounding on **one** connection: `{normalize(w)[0]: entry \| None}`, forms folded to their headword, user rows win; with no FEED built every value is `None` — never a raise |

**Model or rules** is decided **once**, at the route (`server._canon_mode(route)`:
with no route, `llm.reachable(session.llm_url)` as before; `local` asks
llama-server's `/health`; `cloud` is model mode with the gate open, a 403 in
the gate's own words with it shut, rules while agent-free) or at the tool
(`canon_tools.model(route, project_dir)`), and never changes mid-job; a model that
dies mid-job fails it ("the model stopped answering (…); nothing was
written, run it again"). **Rules mode** — no model reachable, and every test
— writes a labelled **scaffold**: `L:term` items from `candidate_terms`
(tokens ≥ 4 letters, a ~300-word stop list, names never terms, forms folded
into their FEED headword, rarest FEED band first; `term_limit`: 40 per 2 000
words, at least 6, at most 60) grounded `feed: {word, pos, origin}` + `sense`,
or `feed: {pending: "not in FEED"}`; `E:` items from `entity_candidates`; no
K/P/T items; every item `confidence: 0.3`, `state: pending`, `pending: "a
model has not read this passage"`; the atem line is the first prose sentence
cut to 25 words, focus the first two sentences, push and pull open
questions. The twin says `derived.mode: rules`, the job messages say
"scaffold", and every UI surface says **"scaffold, no model"** (owner
decision 8) — never let one pass for a reading.

**Model mode, per passage** (chunked by heading, then ~1 200-token windows
with a paragraph of overlap; `max_tokens` = min(4 096, n_ctx − prompt
estimate − 512)), at most three completions: **the reading** (claims first,
then events, concepts, entities, terms and one atem, capped 8/4/4/6/8, with
up to 15 FEED words of the passage and their definitions); **one
continuation** when the reading was cut off (`finish_reason: "length"`, or a
last item that does not parse) — complete items kept, "continue the list
after <last id>", never a second; **one repair of only what failed** after
normalization — the failing items with their problems, "only these items,
corrected", and only stand-ins are taken back. **Normalization runs before
the checks**, deterministic and counted (`info["normalized"]`): fences
stripped; kinds through `KIND_SYNONYMS` and moved to their module
(`E:concept/x` → `K:concept/x`); stance and salience synonyms and prefixes
(`inferred` → deduced, `hig` → high); link rels by prefix; spans read however
written and clamped to the passage; provenance filled (`{mode: derived,
sources: [<file>#La-Lb], confidence: 0.7, state: known}`); a reference
written as words becomes the named item's id, else an open question keeping
the words; the model's own `feed` is discarded (grounding is the engine's).
Then ids are rebuilt `<M>:<kind>/<slug of name>`, passages merge (first wins,
spans extended, sources appended), dangling references become `{pending:
"<id> is not an item of this twin"}`, and **the lexicon floor** — the
rules-mode FEED-grounded terms — is always present, a model term naming a
floor word taking its place. A final whole-twin lint drops what still fails
(`derived.dropped`). The whole-text atem is one completion over the passages'
atems plus the first and last ~800 tokens. **Measured on gemma-4-E4B: ~105 s
for the twin of a 330-word note, ~13 s for a passage atem** — which is
why derivation is a background job, and why a chat-turn tool keeps the model
for short texts.

**The whole-text pass (0.6).** The new modules cost no further request: the
atem's one request is widened. Its system prompt is `ATEM_SYSTEM` word for
word followed by the flavour's item shapes (`WHOLE_ITEMS_PROSE` /
`WHOLE_ITEMS_VERSE`) and `WHOLE_RULES`; its user message adds a digest of
what the passages found; the reply is one YAML mapping, the atem's keys then
`nodes:`. It may write a fabulan's `I:*`, `N:aim/audience/decision/exclusion`,
`C:device`, `C:voice`, `R:maker`, `R:release` (a fabulap's `I:*`,
`N:aim/audience`, `R:maker`, `R:release`); any other kind is ignored and
counted (`info.whole.ignored`). The items are normalized like a passage's
and held to the conventions (`_policy`); what fails the fabula's checks gets
one repair turn, and what still fails is dropped and counted. The atem is read
first, so a reply whose `nodes:` is broken still gives its atem, and the
twin always lands. **Rules add structure** in both modes, from what the file
itself states: a `C:part` per section heading (the title heading left out),
and from front matter or a copyright line `R:maker`, `R:licence`,
`R:release`; paragraphs are not parts.

**Verse (0.6, a fabulap).** [enough/verse.py](../enough/verse.py) reads a
poem by rule, no model: stanzas and lines (`C:line`, its words kept only
when the person says the text may be copied, `copyable`), stresses from
FEED's pronunciations (`feed_pronunciations`; the host's `pron` engine cut to
`thym_host.PRON_FIELDS`), the metre (`C:metre`) and the rhyme scheme
(`C:rhyme`); the passages are cut by stanza (`verse_chunks`) and read with
`VERSE_SYSTEM`. A verse run in Thym (`derive t as verse`) records what its
rules read inside the recorded engine call, so it replays with no
dictionary.

### Shorts

**The model (SHORT, plan §15).** One fabula, many entailments. The fabula is
the text's order-free material (every item with a `span` saying where in the
text it was found); a **short** — *syuzhetic-hermeneutic open readable
text* — is an entailment enough compiles from it: an arrangement (syuzhetic) that
says how each thing is known as it goes (hermeneutic), plain markdown
that is yours, honest about its gaps and open to the reader's own reading
(open), as prose (readable text). The author's text is also a syuzhet of that
fabula but is never called a short; the atem sits outside the pair (the
breath: a reduction with its own push/pull shape). A fabulac's short is a
cshort, compiled by its own route (see "Building a fabulac"). Two orders:
**`told`** (`_told_lines`: every L/E/K/P/T item a span places — `lines`, or
`start`/`end` quotes found in the source text — sorted by first line, last
line, then term < entity < concept < claim < event, then twin order; grouped
under the source text's headings when it is passed (`_source_headings`: the
first heading is the short's own `# title` when it is H1 or the twin's name;
the rest keep relative depth from `##`; a `span.heading` string wins when a
twin records one); unplaced items last under `## Also in the fabula`; X atems
never told) and **`weight`** (today's outline: claims by salience grouped by
concept, events in before/after order, terms). The atem line leads both; each
claim's stance is said in words in both. `default_order`: `told` when the twin
has a `source` and its text is readable, else `weight`. Rules mode returns the
outline verbatim; model mode is one completion with `COMPILE_SYSTEM`
formatted with `COMPILE_ORDER[order]` and `COMPILE_USER` saying the order in
words (`ORDER_SAID`). Either way the engine appends `\n\n---\n\n` and **one
italic footer line** (`short_footer`): `*a short of notes.md, told as the
author told it, compiled from its fabula on 2026-10-23 by g40-04*` (rules:
"by rules, without a model"; a standalone: "a short of rain.fabulan.cosm, a
standalone fabula, told by weight, compiled on …"). A footer an earlier
edition wrote ("compiled from its EMF twin", "a standalone EMF") reads the
same and is never rewritten; Thym's `footer` check holds the new words and
reads the old. The footer and the "Also in the fabula" heading are English
data, like everything a compile writes.

**Engine, route, catalogs.** `short_path(twin, now)`: `notes.md.fabulan.cosm`
(or the old `notes.md.cosm`) → `notes.short-YYYY-MM-DD-HHMM.md`,
`rain.fabulan.cosm` → `rain.short-….md` (the stem is
`fabula_names.short_stem`'s), `-2`/`-3` on a collision (local time; an aware
`now` is converted). `record_short` inserts `shorts:` just above the
top-level `nodes:` (skipping a comment block that sits right above it) or
appends one block line `  - {path, at, by, mode, order, route?}` to an
existing block list — text-level, never a load/dump, so comments, quoting and
CRLF stay byte for byte (an old `emf/1` twin stays `emf/1`); `shorts: []` or a
flow list is rewritten as a block; it re-parses and refuses (`DeriveError`)
unless the result is the same document plus one entry. `by` is the model's id
or `rules`; `route` is written when a model told it; `at` UTC. `POST
/api/fabula/compile {path, order?, route?}` hands a text's fabula (anything
but a fabulac) to the short compile (`server._compile_short`, passed into
`fabulac_job.build_router`): it validates `order` (`told` | `weight`, case and
spaces forgiven; 400 "order must be told or weight"), computes the default
from `source_path` + `read_source`, claims **the text's key** for a twin
(`fabula_names.text_of_twin`, the key `canon_tools.text_target` gives a
decompile, so a compile's `shorts:` write never races a re-derive; a
standalone fabula claims its own path), writes the short, records it in the
fabula (a failed record is logged and reported `recorded: false`, the short
stays), then regenerates the catalog. Result `{written, fabula_path,
emf_path, mode, order, model, route, recorded}` (`emf_path` the same value as
`fabula_path` through 0.6, for the page). Canon's catalogs (`_enumerate`)
mark a `<stem>.short-<stamp>.md` whose text is beside it `short_of: <text
path>` and the text `shorts: [<paths>]` (listing order = date order) —
`canon.short_text_name`: a text with that stem (one with a twin first, then
`.md`), else the standalone fabula `<stem>.fabulan.cosm`, `.fabulap.cosm`,
`.fabulac.cosm` or `<stem>.cosm` that declares a fabula, else a file named
the stem (a converted original). A short is never hidden; the UI's "short"
tag on a Canon tile and a sidebar row is computed client-side by the same
rule (`canonShortOf`). There is no `short` tool: the reader's button is the
door.

### Routes, jobs and the `canon` SSE event

All project routes (404 in home mode); paths through
`_resolve_project_path`, so `canon:` works. The refusals live in
**`canon_tools.text_target(project_dir, path, flavour=None)`**, which raises
`TextTargetError(status, message)`; `server._text_target` delegates to it, so
the routes and the readvisor tools refuse in the same words (a test compares
all sixteen). Since 0.6 the three routes that read or write a fabula live
under `/api/fabula/`; the old paths (`/api/canon/derive`, `/api/canon/emf`,
`/api/canon/compile`) are served by the same handlers through 0.6
(`retired_names.ROUTES`), and `what: emf` still reads as `what: fabula`.
Every derivation route takes `route` (`local` | `cloud`; absent: `local`,
see "Models" → "A model route per job"): a shut gate is a 403 in the
gate's own words, nothing written, no fall back.
A job started with no `route` runs on this machine's model (`local`),
whatever model slot the chat is on; it asks the cloud only when the request
says `route: cloud` (and the cloud gate is open). With no local model
running it runs by rules, or refuses in words; it never falls back to the
cloud.
`GET /api/fabula/suggest?path=<text>` → `{path, suggested, why}`: the
flavour suggested for a text, twin or none.
`GET /api/fabula/models` → `{agent_free, local: {running, model, window},
cloud: {open, model, window, reason}}`: what a job would run on, read
before it starts.
A job of kind `compile` says `flavour` (`fabulac`, `fabulan`, `fabulap`)
and `what` (`code`, `line`, `overview`, `manual`, `short`) from its first
snapshot.

| Route | Body | Returns | Refusals |
|---|---|---|---|
| `POST /api/fabula/derive` | `{path, what: fabula\|atem, force?, flavour?, route?, copyable?}` | `{job, flavour, suggested}` | 400: no path; `what` not fabula or atem ("what must be fabula or atem"); a folder; a Holotype or anything inside one; a package; `canon.cosm` / `rness/canon.cosm` / `.canon.json` ("kept by enough"); any `.cosm` ("already enumerated"); binary; not markdown or plain text; empty; traversal; a flavour that is not `fabulan`/`fabulap`; a bad route. 403 a shut gate. 404 missing. 409: a file of the twin's name that is not a fabula ("… is not a fabula; move or rename it first"); "already fresh" (fabula: fresh **and** `completeness: full`; atem: fresh with a line) unless `force`; a job holds the file |
| `POST /api/canon/atem` | `{path, flavour?, route?}` → file atem (written; a minimal twin when none; never "already fresh") · `{path, selection: {text, start?, end?, lines?}}` → passage atem (not written; the result is `pinnable` with a `span`) · `{text}` or `{selection}` alone → the atem of the words (nothing written) | `{job}` | as derive for `path`; 400 nothing given, a selection that is not a mapping, text over 200 000 chars |
| `POST /api/canon/atem/pin` | `{path, atem: {line, focus?, push?, pull?}, span, of?, flavour?}` | `{twin_path, item_id, job}` — synchronous; `job` is a finished `kind: pin` snapshot, also emitted | as derive for `path`; 400 no line, no usable span, `of` not a list of ids; 409 while a job holds the file |
| `GET /api/fabula/twin?path=[&flavour=]` | the text (or a twin itself, any of its names) | `{twin_path, state: fresh\|stale, flavour, twins: {flavour: {path, state}}, suggested, cosm: <the /api/cosm payload>}` | 400 a flavour that is not `fabulan`/`fabulap`; 404 no file, or "<p> has no fabula yet" (the page then asks `/api/fabula/suggest`) |
| `GET /api/fabula/suggest?path=` (S2) | a text, a twin or a converted original | `{path, suggested: fabulan\|fabulap, why}` (`fabula_names.suggest_flavour`, the one rule) | 400 missing path, a folder, not readable as UTF-8, a bad path; 404 missing |
| `GET /api/fabula/models` (S2) | | `{agent_free, local: {running, model, window}, cloud: {open, model, window, reason}}`; agent-free asks nothing; `reason` is the gate's clause with no provider named; never an error for a model that is down | |
| `POST /api/fabula/compile` | `{path, order?, route?}` of a text's fabula (either declaration); a fabulac goes to its own compile (see "Building a fabulac") | `{job}`; result `{written, fabula_path, emf_path, mode, order, model, route, recorded}` — a short beside it, recorded in its `shorts:` | 404 missing; 400 not `.cosm`, not a fabula (says what it declares), refused, a bad `order`; 409 while the text's claim is held |
| `GET /api/canon/job/{id}` · `POST /api/canon/job/{id}/cancel` | | the snapshot | 404; cancel 409 unless queued or running |

The snapshot is the SSE event's data, the same dict:

```
{id: "cn7", kind: emf|atem|compile|pin|thym|read|fabulac|dialectic, path, state: queued|running|done|failed|cancelled,
 phase: waiting|starting|lexicon|reading|continuing|repairing|merging|atem|compiling|writing|cancelling|done|failed|cancelled,
 chunk, chunks, message, mode: model|rules, route?, flavour?, result, error, started_at, finished_at}
```

The kind `emf` is a fabula's derivation (the kind keeps its 0.4 name: the
page keys its toasts on it). `route` is the route a model-mode job used
(`null` in rules mode); `flavour` the decompile's. `path` is the text read
(`memo.pdf.md` for `memo.pdf`). Results: a derivation `{twin_path,
text_path, mode, model, route, provider, flavour, suggested, replaced?,
chunks, items, counts, dropped, normalized, continued, atem, state}`; file
atem `{twin_path, text_path, mode, model, route, flavour, suggested, atem,
stance_profile, written: true, state}`; passage/text atem `{line, focus, push,
pull, stance_profile, mode, model, written: false, pinnable, path, span}`;
compile as above; pin `{twin_path, item_id, text_path}`. **Claims**: one
writing job per file (a derivation and a file atem: the text's resolved
path; compile: the same text's path for a twin, its own path for a
standalone fabula; a pin holds the same claim for its write); passage and
text atems claim nothing. **Cancel**: queued → cancelled at once; running →
`phase: cancelling` ("the model finishes the passage it is reading"),
checked between passages, before the atem and before the write, ending
"cancelled after passage k of n; nothing was written". After every write:
`canon.regenerate_catalog(volume)` for a store path,
`canon.project_catalog(project_dir)` for a project path
(`canon_tools.catalog_after`, the routes' rule too).

**The concurrency rule — read it before you touch either side.** A
model-mode **job** on the local route is an asyncio task that holds
**`session.generation_lock`** — the lock every chat turn holds — for its
whole run, with the blocking work in `asyncio.to_thread`; while it waits it
is `queued`, "waiting for the model", and a chat message sent during a
derivation waits for it (the UI's busy line says so). A cloud job (0.6) and a
rules-mode job never take the lock. **A readvisor tool never takes the lock,
and never starts a job it would wait on.** A tool runs *inside* a chat turn
that already holds `generation_lock`, so a tool that waited on a lock-taking
job would wait for the turn that is waiting for it — a deadlock. So the text
tools (`fabula_derive`, `atem`) call `canon_derive` directly in the tool's
worker thread (llama-server is idle between the turn's streams, so a local
`complete` from there is safe) and hold only the file's claim
(`CanonJobs.holding`, a set under a threading lock — not the generation
lock), so a tool and a person's job never write one twin at once ("… is
being derived right now; try again when that job is done"). The 0.6 tools
that start long work (`fabulac` build and compile, `dialectic` settle) start
a real job instead and **do not wait for it**: `server._start_from_tool`
hands the start to the event loop from the turn's worker thread and returns
the job's first snapshot; a local job then sits `queued` on the lock the
turn holds and runs when the turn ends, and the tool's answer says so ("It
runs after this turn; ask for its status later").

### The readvisor tools ([enough/canon_tools.py](../enough/canon_tools.py))

Six tools, registered at `tools` import time like `dictionary_tools`, each
traced under `trace_log_enabled` (rows in the "Tools" table): `cosm_read`,
`cosm_lint`, `fabula_derive` (`emf_derive` until 0.6), `atem`, `cosm_guide`,
and `doc_lookup` (0.4.4, see "DocOES"). The same documentation block carries
Thym's `thym_check` and `thym_run` (0.5.0) and names `thym_moves` (0.6)
(`enough/thym_tools.py`, see "Thym"), which answer only with the
`macrocosm-oes` skill on; the fabula round's `dialectic` and `fabulac`
(`enough/fabula_tools.py`) have a block of their own that rides only with
the skill on (see "The request lifecycle"). `<path>` is project-relative or
`canon:<volume>/…`; a full path inside the project is made relative, any
other leading slash is dropped, exactly as the routes read it.

- **Model mode in a chat turn only for short texts.** `EMF_MODEL_MAX` = 6 000
  chars: over it, with a model answering, `fabula_derive` writes the rules
  scaffold and its `mode:` line says a full model pass belongs in the reader's
  decompile (a background job). `atem` keeps the model up to `TEXT_MAX`. Both
  refuse a text over `TEXT_MAX` = 24 000 chars ("… use decompile / atem in the
  reader instead"). `fabula_derive` answers "already fresh … pass
  `<force>yes</force>`" when re-deriving would not improve the twin; a rules
  scaffold of a short text is re-derived once a model answers. Both take
  `<flavour>` and `<route>` (0.6; a cloud route needs the gate open and is
  refused in the gate's own words, never falling back).
- **The seam.** `canon_tools.configure(llm_url=, jobs=)` is a module-level
  setter `create_app()` calls once, project mode only, with `session.llm_url`
  and the `CanonJobs` instance — no tool reached the session's model before.
  Unconfigured → rules mode; `configure()` with no arguments resets (the tests
  do, autouse). `fabula_tools.configure(project_dir=, start=, build=,
  compile=, settle=, jobs=)` is the same kind of seam for the 0.6 tools.
- `derived.by` for a tool write is `prompt.chief_name()`: tools run only in the
  chief's turns (council turns strip tool calls).
- **Store writes** (`fabula_derive` / `atem` on a `canon:` path) need
  `canon_enabled` and answer `broker.denial_canon_disabled()` before reading
  anything; reads, `cosm_guide`, project-path writes and inline atems never
  ask.
- Every write returns `side_effects={"canon": <snapshot>}` — a finished job in
  `canon_jobs`' shape with `id: "rv<n>"` and `by` — which `server._handle_tool`
  emits as SSE `canon` after the tool's own events; the UI repaints for any
  `done` snapshot and names who made it.
- **The docs block**: `prompt.CANON_TOOL_INSTRUCTIONS` ("## MacroCOSM", **995**
  chars against the owner's 1 000 cap — 994 in 0.5.0, 965 in 0.4.4 after
  `doc_lookup`, 809 in 0.4.3 — test-pinned; one example per tool, each
  round-tripping through `parse_tool_calls`; `fabula_derive` and the line
  naming `thym_moves` were paid for by shorter phrases), gated by
  `prompt._macrocosm_available()` — see "The request lifecycle". There is no
  room in it for an example of `thym_moves`, `<flavour>` or `<route>`; the
  skill documents them.
- **The skill**: `defaults/skills/macrocosm-oes/` (`SKILL.md` + a
  `references/README.md` of pointers to the spec, the manifests, the
  sidecar, `docs/THYM.md`, `defaults/thym/` and the reader — no copies)
  teaches the formats (the core's five built-ins and the two MiniCOSMs), the
  fabula's words and names, the six stances, the atem's parts, when to
  decompile and when an atem is enough, how to read a Holotype, Thym
  programs (and what `thym 1` adds), the dialectic and the fabulac, and is
  **the only documentation of `thym_moves`, `dialectic` and `fabulac` beyond
  their prompt lines** (the prompt names them; the skill explains them).
  **Off by default** like every shipped skill — the MacroCOSM block is always
  on; switched on, its guide (~8,800 chars with its front matter, the size it had in 0.5.4) rides in every turn, and the
  fabula block with it; switched off, it is one `cosm_guide` call away.
  **How a change reaches a project**: a shipped skill is a symlink from
  `rness/skills/macrocosm-oes` into the install's `defaults/skills/`, so an
  edit arrives with the install, in every project, on the next turn. A
  project that holds a **real directory** of it instead (a cloud-sync or
  dereferencing copy) is healed back to the symlink at launch only while its
  bytes equal this install's copy (`skeleton._populate_skill_symlinks`, step
  1.5); a copy of an older edition differs, so it stays as it is, counts as
  untrusted, and keeps the old text until the person replaces it (switch the
  skill off, delete the folder, relaunch).

### The UI (index.html)

The 0.6 round's page work is three lanes (notes `docs/fabula-landed-U1a.md`,
`-U1b.md`, `-U1c.md`): U1a the fabula card, the model line and the fabulac's
card and viewer (this section and "Building a fabulac" → "The UI"), U1b the
dialectic card ("The dialectic" → "The UI", "Ascribe's module" → "The UI"),
U1c Thym's editor, moves, plan reader and inputs ("Thym" → "The UI").
Words on screen say **fabula** and **twin**, never "EMF": "the fabula of
<name>" heads the face, the docs facet is "built-ins and MiniCOSMs".
Internal names keep the old word (`EMF_FACE`, `emf-*` classes, the job kind
`emf`, `data-emf`); an `emf/1` file's badge shows `fabula/1`. Nothing in the
page calls `/api/canon/derive|emf|compile` any more (the
`fabula-decompile-card` scenario asserts it on the wire): `canonRefreshDoc` →
`GET /api/fabula/twin`, `canonDecompile(path, {force, flip, flavour, route,
quiet})` → `POST /api/fabula/derive` (`what: fabula`, `route` always said),
`canonCompile(twin, order, route)` → `POST /api/fabula/compile`.

- **The fabula card** — `#fabula-modal` (a `*-modal`, so the MODAL helper
  gives it dialog semantics), one card with two faces; JS block "The fabula
  round in the page (0.6, U1a)", ending `window.__fabReady = true`, and every
  hook in older code is guarded by it. The **text face**:
  `fabDecompileOpen(path, state, {flip})` → `fabTextPaint` / `fabDecompileGo`.
  `canonDecompileAsk` (every "decompile" / "refresh twin": the chip, the twin
  button with no twin, the sidebar and Canon menus) opens it; 0.5.4's
  `confirmOverlay` is gone. Flavour radios prose · fabulan / verse · fabulap,
  preselected from the twin the text has (the one derived last), else the
  suggestion (`fabSuggestOf` → `GET /api/fabula/suggest` when the twin route
  404s), tagged "suggested" with a note that the choice is the person's. Per
  flavour: "its twin: X, up to date|out of date", "no twin of this flavour
  yet: it will be X", or the old-name line; with a fresh twin of the chosen
  flavour the button reads "decompile again" and sends `force`. Refusals (the
  shut gate's 403, a 400) stay on the card in the server's words (`quiet`); a
  face waiting to flip closes the card first and a refusal comes back as a
  toast. The **folder face** is the fabulac's (see "Building a fabulac").
  Both faces end with `#fab-dialectic` (`dlgFabLine`, see "The dialectic").
- **The model line** — one component for every card that starts model work:
  `fabRouteHTML(key, {ceiling, unit})` + `fabRouteOnEvent(e, key, cb)` +
  `fabRouteBody(key, body)` (adds `route`, and `calls` when a ceiling is
  given); a host calls `fabRouteReset(key)` and `fabGateLoad()` when it opens.
  `fabGateLoad` reads `GET /api/fabula/models` (S2; `FAB_ROUTE.models` holds
  `local` and `cloud`). Heading "where the model runs"; "here (<model>, a
  <window>-token window)" (`fab.route.hereWindow`), "here (no model is
  running)" or "here (this machine's model)"; a radio pair here / "cloud
  (<model>)" only while `cloud.open`; agent-free says "agent-free: a rules
  reading, no model". Here by default, reset every time a card opens, never
  remembered. Hosts: the text face, the fabulac face (ceiling "at most N
  model calls a stage", optional), the dialectic's settle (`'dlg'`), Thym's
  run card (`#thym-route-box`, `thymRouteHTML`; the ceiling marked "needed"
  when the plan's `models.calls_open` is not empty), and the face's short
  menu (`fabShortRoutePaint`: "the model: here (…)" and an "on the cloud,
  this once" `menuitemcheckbox`, forgotten after the one compile). A
  holograph never gets one.
- **`fabSet(el, html)`** writes a container only when its HTML changed and
  puts the focus back on the same control (by id, else by name and value), so
  a snapshot or a re-read can repaint under a person's hands. Use it for
  anything a job snapshot or an event repaints (the fabulac face, the
  dialectic card).
- **The tree's old twin.** `fabDecorateTree` reads S2's
  `data-old-twin` / `data-old-twin-of` on a row and tags it "old twin" with
  the note as its title.

- **The cosm viewer** — mode `cosm`, root `#cosm-mode`, icon `cosm`.
  `enterCosmMode(path, {focus})` → `GET /api/cosm`; re-entering the open path
  only re-focuses; `exitCosmMode()`. Toolbar: title, the declaration badge,
  the lens `<select>` (`#cosm-lens` → `enterMerirmaidLens`), **open raw**
  (`cosmRawOpen`: read/edit's *edit* face, because the read face would render
  the YAML as markdown; a folder volume with several files gets the
  `#cosm-raw-pop` list), **about this format** (`cosmAbout` → the docs viewer, spec at short,
  on the format's section via `COSM_SPEC_SECTION`: comprise 19.1, cosm 18.2, canon 18.3, fabula 18.4, doc 18.5, thym 18.7, ascribe 19.2), outline (`cosmRailToggle`; a sheet when
  narrow), find (`COSM_FIND`, `FIND_BARS.cosm`), the `(?)`
  (`data-help="cosm-viewer"`), mini/full. The rail (`cosmRailHTML`,
  `cosmChecksHTML`): name, counts or "N items", "scaffold, no model" for a
  rules twin, the URI with a copy button, modules → kinds with counts, the
  checks with every problem, the open questions, the not-run line. The column
  (`cosmBodyHTML`, `cosmCardHTML`, `cosmFieldsHTML`): a fabula's atem
  first (`cosmAtemHTML`), then per module and kind the item cards — envelope
  line, name with the stance badge (`.cst-<stance>`, a shape per stance so
  colour is never the only signal), summary, an item `pending:` as a marked
  question, every other field as a definition list; references are links
  (`cosmIndex`, `cosmResolve`, `cosmFocus` with a back pill), Canon `path`s
  open in their natural mode (`cosmOpenPath`). 40 cards per kind
  (`COSM_KIND_CAP`) + "show all", `content-visibility: auto` on cards;
  mozilla's 524 items open in ~320 ms. CSS block "The cosm viewer (0.4.3)",
  an inline-size container (`cosmmode`). Open everywhere `.cosm` is: the
  sidebar row click, Canon tiles, the project-catalog button, a lens node's
  "show item".
- **The host contract.** The viewer's content functions take the **host**
  they draw for as their last parameter, defaulting to the viewer — `COSM`
  (the viewer), `EMF_FACE` (the EMF face), `ATEM_HOST` (the atem card, resolves
  nothing) and, since 0.4.4, `DOCS_FAB` (the docs viewer's fabula density). A
  host is its state (`path, data, ix, shown, railWant`) plus `body()`,
  `rail()`, `railBtn()` and `viewer` (only the viewer offers the back pill and
  refreshes its find bar), and optionally `card` (0.4.4: `cosmCardHTML(it,
  kind, host)` calls `host.card` when set, else `cosmCardBaseHTML` — the docs
  viewer's prism card wraps the base card) and `unwrap`. Every host's cards
  now draw a `body` field as markdown under the summary (`cosmField`'s **body
  face**, `cosmBodyFace`; `body` joined `COSM_SKIP`), Holotype items included.
  `COSM_INLINE` (0.4.4) maps an `inline:<…>` handle to `{text, filename?,
  title}`: `cosmLoad` and `mmFetchLens` post it to `/api/cosm/inline*` instead
  of naming a path, and "open raw" hides for it. One component, four hosts, no
  fork — extend it the same way.
- **The Canon chip** — `#canon-chip-mini`, `#canon-chip-review`,
  `#canon-chip-edit`, beside the convert chip in the three reader headers.
  `canonPaintChips()` paints it from `canonOnDocOpen(path)` (called in
  `openReadEdit` right after `convertOnDocOpen`) and again after every face
  or size switch, a save, a readvisor turn's end and any finished write; state
  comes from the twin route (`GET /api/fabula/twin`; `CANON.doc`; 404 =
  absent). Shown for text
  paths only (`canonIsText`), project or `canon:`, never in home mode. The
  badge reuses `twin-on` / `twin-off` tinted `--accent-tool` (owner decision
  5), with the corner dot when stale; the buttons are **twin** (the fabula's face),
  **atem** (the whole file → the card) and **decompile** / **refresh twin**
  (both open the fabula card, above). The `(?)` (`data-help="canon-chip"`) sits on the read
  toolbar's chip only. Compact forms come from container queries on each
  header; beside a convert chip the read toolbar drops it below 900px.
- **The fabula's face** (`EMF_FACE` in code) — `#review-emf` (full), `#preview-emf` (mini):
  `emfFaceShow`, `emfFaceHide`, `emfFaceRender`, `emfFaceAct`. The twin drawn
  by the viewer's functions (host `EMF_FACE`) **in place of** the reading surface,
  at the reader's size. Head: "the fabula of <name>", stale / scaffold tags,
  lens, outline, open raw, **compile a short** — a split button
  (`.emf-short`: the main button sends no `order`, the caret `▾`
  opens `emfShortMenu()` with **as the author told it** / **by weight**, the
  default marked from the twin's `source`, and the model line's two items
  (`fabShortRoutePaint`); Esc, a click outside or a choice closes it, Esc
  going no further) → a toast "wrote notes.short-….md" with
  **open** — and **back to the text**. Remembered per text (`CANON.faces`) until read/edit closes;
  "twin" on a text with none decompiles first and flips when the job is done.
- **The atem card** — `#atem-modal`, a `*-modal`, so the shared MODAL helper
  gives it dialog semantics (its Esc is its own, capture-phase).
  `atemCardOpen({source, kind, path})`; states reading / answer / error
  (`atemCardPaint`). The answer is `cosmAtemHTML` — the line large in the serif
  italic, focus / push / pull under small caps, each with its definition
  tooltip (`cosmAtemParts()`) — plus `atemStancesHTML` (the six stances with
  counts) and, in rules mode, the scaffold note. Actions: **copy** (⇧ copies
  all four parts), **pin to twin** (a pinnable passage atem →
  `/api/canon/atem/pin`), **open twin**, **close** (while it reads, the job
  moves to a toast).
- **Right-click atem.** `dictCtxOpen(x, y, hit, where, sel)` gains **atem of
  selection** when `canonSelectionAt(e)` finds a non-empty selection on
  `#review-body`, `#preview-body`, `#edit-textarea`, `#mini-edit-textarea`,
  `#wiki-body` or `#docs-body` (0.4.4, at all three densities; a selection
  inside a docs link opens the menu too); a right-click on the
  selection opens the menu even off a word (elsewhere today's rule stands),
  "copy" then copies the selection, and a textarea selection is no longer
  replaced by the word under the pointer. It
  sends `selection: {text, start, end, lines?}` — start/end are the passage's
  own first and last ≤ 60 characters, `lines` come from `REVIEW_BLOCKS` or a
  pristine editor's offsets — and `path` only for a text the engine reads (a
  400 for the path falls back to an unpinnable atem of the words). Composure's
  `compOpenCtxMenu` offers it on text pages (`canonCompSelection`, no path, so
  never pinnable). Canon shift-click and the sidebar option-click gain
  **atem** and **decompile** / **refresh twin** (`canonMenuItems`), merirmaid's
  node menu **atem** for a text (`mmAtemItem`).
- **Jobs in the page.** `canonTrack(snap, {want: card|flip|toast})` registers
  what this tab started; `canonOnSnap` takes every snapshot (SSE `canon`, a
  1.5 s poll, cancel replies — a finished job never regresses); `canonToast`
  reuses convert's toast component with `canonPhaseText` and **cancel**; done →
  `canonAfterWrite(snap)` repaints the chip, the face, Canon's grids, the
  sidebar and an open viewer. A snapshot this tab did not start (another tab,
  a readvisor's `rv…` write) repaints the same way with no progress toast, and
  `canonByNotice` says who when `by` is set. **The busy line** `#canon-busy`
  above the composer (`canonBusyPaint`) shows while a model-mode job is queued
  or running: "a message you send now waits until it is done".
  **`window.__canonReady`** guards read/edit's calls into the Canon block —
  give any new call from read/edit code the same guard.
  **How a card follows a job (0.6).** A card registers the job it started,
  or one already running that it adopts (a tool's, another tab's), with
  `canonTrack(job, {want: 'fabulac' | 'dialectic' | …})`; `canonApply`
  hands each snapshot to the card's own `…JobOnSnap` (`fabJobOnSnap`,
  `dlgJobOnSnap`), `canonToast` ends in the card's words when the card is not
  showing that job (`fabToastEnd`; a `dialectic` branch with the job's
  message), `canonAfterWrite` repaints what the write touched
  (`fabAfterWrite`, `dlgAfterWrite`: the tree, Canon, an open viewer), and
  `canonBusyPaint` names the work ("building the fabulac of …", "settling the
  answers into …"). A compile snapshot is a fabulac's when `snap.flavour ===
  'fabulac'` (S2; `fabIsFabulacSnap` keeps `want` and the result's shape as a
  fallback). A new card adds a `want` of its own and a branch in each of the
  three.
- **uicheck**: screens `canon`, `canon-volume`, `cosm-viewer`,
  `cosm-viewer-holotype`, `cosm-viewer-mini`, `canon-chip`, `emf-face`, `emf-face-mini`, `emf-short-menu`
  (SHORT: the split button's menu open), `atem-card`, `atem-card-mini`;
  0.6 (U1a) screens `fabula-decompile`, `fabula-decompile-old` (an old-named
  twin beside a new one), `fabula-build`, `fabula-cosm`, `fabula-cshort`,
  `fabula-catem` (`thym-run` shows the model line); scenarios
  `fabula-decompile-card` (the card, not a job; verse suggested and checked;
  no cloud with the gate shut; Esc writes nothing; a decompile by rules lands
  `rain.md.fabulap.cosm`; the wire says `/api/fabula/derive`, `what: fabula`,
  `route: local`, no retired route), `fabulac-build-outline` and
  `cshort-read` (see "Building a fabulac"), seeded by `_seed_fabula` in
  `works/` (`tally/` + its fabulac with five runs, a cshort and a catem,
  `tiny-tool/`, the poem `rain.md`, `letter.md` with an old and a new twin);
  scenarios `canon-open-catalog`, `cosm-lens`,
  `twin-flip`, `atem-selection`, `atem-pin`, `compile-short` (SHORT, rules
  mode: the menu's two orders with told marked, Esc closing only the menu,
  compile → the "wrote press.short-….md" toast → the file with its footer, one
  more entry in the twin's `shorts:`, open). The seed
  (`scripts/uicheck/server.py`) writes `orchard/notes.md` + its fresh twin,
  `orchard/press.md` + its twin (the same pair renamed; `compile-short` writes
  beside it, one short per language), `orchard/ledger.md` (no twin, so the pin
  scenario has something to write and the hand-made twins never change) and
  `meadow/` (the public Holotype) into
  the scratch project, and a `field-notes` volume into the scratch store
  (`seed_canon`, which refuses any root outside the scratch dir). The
  0.4.3 spec-viewer screens and `cosmspec-contents` became the docs viewer's
  (see "DocOES" → "The docs viewer").

---

## Thym (the transcognition language, 0.5.0; `thym 1` in the 0.6 round)

**Thym** is the transcognition language that connects the OESes: it moves
meaning between densities and projections. Its own volumes (`thym/1`) are a
built-in of MacroCOSM's core, specified in Thym's own text; Thym is not a
MiniCOSM. A program (`<name>.thym`, its first line the version line `thym 0`
or `thym 1`) composes **moves** that the formats declare in their `moves:`
blocks — the fabula's `derive`, `entail`, `atem`, `expand` and (`thym 1`)
`survey`, `history`; DocOES's `enumerate`, `compile`; Thym's own `cut`,
`count`, `words`, `null`, `measure`, `morph`, `read`, `package`, `unpack`, the
accessors, and (`thym 1`) the editing moves and the dialectic's three;
Comprise's `project`, `band`, `mark`, `withhold` (in the sidecar); Ascribe's
`propose` (`thym 1`). **`entail`, once `tell`** (0.7, THYM 6.3): the move
that makes a short of a fabula was `tell`; `tell` is its earlier spelling,
read for good under `thym 0` and `thym 1` and never written.
`types.EARLIER_SPELLINGS` is the one table: the parser reads a `tell` call
as `entail` (so a step's `move` and `calls`, the contract and the plan's
nodes say `entail`, while the step's `text`, `name` and `body` keep the
program's words and `compile` gives the file back byte for byte); the
checker keeps `tell` reserved; `run.spelled_now` reads a plan, `trace.load`
a trace and the replay coprocessor a recorded candidate that says `tell` as
`entail`, so a run recorded before 0.7 replays. The compiler parses, resolves, types, checks the
static contracts, estimates, enumerates the program into `thym/1` items and
plans it; the runtime checks the plan against the machine, runs
deterministic moves in code and sends model-backed ones (`asks: true`) to a
**coprocessor** on the run's model route behind the move's contract, lands
every output or none, and writes a **trace** that replays byte for byte from
its recorded candidates and engine calls. Spec: [docs/THYM.md](THYM.md)
(§20 folders and code, §21 editing, §22 the dialectic in a program, §23
models in a run, §24 conformance; **the reference wins**: where it and
`enough/thym/` disagree one of them is in error and §24.4 says how it is
settled; `tests/test_thym_spec.py` compiles every ```` ```thym ```` block in
it against the real declarations). Design and rulings: `docs/thym-architecture.md`,
plan `docs/thym-050-plan.md`, lane notes `docs/thym-landed-*.md`, and for
`thym 1` `docs/fabula-pins-thym1.md` (sections 9 to 11 are rulings) and
`docs/fabula-landed-T1*.md` (all local, gitignored). User-facing:
HELP_CENTER §12.6 (packages, sealed packages, unpack, readings), §13.4
(programs, run with… and its inputs, the plan, the trace, morphs, the
readvisor's tools, agent free), §13.5 (`thym 1`) and §13.6 (writing a
program, Thym at hand).
`GET /api/thym-spec?lang=` serves THYM.md raw (`/api/macrocosm-spec`'s
twin, in `HOME_PATHS`, English only; a `static/i18n/<lang>/THYM.md` would win).

### The pieces

| Where | What |
|---|---|
| `enough/thym/` | the compiler, the runtime, the moves (see the Code map row); stdlib + PyYAML + `enough.macrocosm` only, so it is vendorable as the reader is (see "What may live under `enough/thym/`" below) |
| `enough/thym_host.py` | enough's engines behind the runtime: the model coprocessor on a route, the prompt builders (its own and the modules in `PROMPT_MODULES`), `engines()` (canon, docoes, feed, pron, the surrounding catalog, and the sibling engines `repo`, `syntax`, `dialectic`, `ascribe`), the preflight hook, the window, the route's reading for a plan, the input check, the Thym root, the program listing |
| `enough/thym_api.py` | the routes (below); mounted by `server.create_app` in one `include_router` |
| `enough/thym_tools.py` | `thym_check`, `thym_run`, `thym_moves` (see "The readvisor tools" below) |
| `enough/repo_engine.py`, `enough/fabulac_prompts.py` | the fabulac's engines and prompts (0.6; host modules, never vendored; see "Building a fabulac") |
| `enough/dialectic.py`, `enough/ascribe.py` | the engines behind the dialectic's and Ascribe's moves (`ctx.engines["dialectic"]`, `["ascribe"]`) |
| `defaults/cosm/manifests/thym.manifest.cosm` | the `thym/1` built-in: one file of six kinds (`program`, `morph`, `context`, `plan`, `trace`, `package`), modules P M C R K, and the `moves:` it owns |
| `moves:` in `fabula.manifest.cosm`, `doc.manifest.cosm`, `ascribe.manifest.cosm`; `comprise.moves.cosm` | the other formats' moves; the sidecar because Comprise's manifest is a byte copy |
| `defaults/thym/` | the nine shipped programs (see "The shipped programs" below) |
| `tests/fixtures/thym/` | the conformance suite (below) |

**The CLI.** `python -m enough.thym check|plan|run|trace|enumerate|compile|conform`
(`run <program> <inputs…> [--rules]`, `run --replay <run-id>`, `conform
[<suite>]`; since 0.6 `plan` and `run` take `--model local|cloud|cloud:<id>`
and `--calls N`; since 0.7 `check`, `plan`, `run`, `enumerate` and `compile` take
`--manifests DIR`, repeatable: the `*.manifest.cosm` and `*.moves.cosm` files there declare
an outside application's moves, known beside the bundled ones. A name a bundled move
already has is refused, never overridden; a move whose `code:` is not importable is known
to `check`, `plan` and `enumerate`, and `run` refuses it, saying its implementation must be
installed). **Always with `ENOUGH_THYM_ROOT` (better: every seam of
`scripts/smoke_boot.build_env()`) pointed at a scratch dir**; `conform` writes
into a temp root and reads only, the others write runs under the root.
`plan` prints one line, `cli.plan_atem`'s: "publish-story: 7 nodes, 3 ask a
model; largest prompt 307 tokens, output budget 0 words" — and, for a plan
that asks, the models line under it (see "Models" → "A model route per
job"); the routes and `thym_check` show the same lines. Since 0.7 `check`
prints every independent fault, one line each, and a trace names its
`inputs_root` relative to the run's root (`.` when the inputs lay elsewhere,
never the recording machine's folder; `trace.portable_inputs_root`): a replay
reads them against `--inputs-root`, else the folder the trace names under the
root, else the current folder (`run.replay(..., elsewhere=)`); a trace written
before names the absolute folder and is read as written. A replay's trace says
its own start (its moves still see the recorded run's clock). `cli.py` is copied
text-exactly into Comprise: `tests/test_thym_cli.py` refuses an added line
that names an app seam or an install path.

**Model mode and the window.** A plan carries its largest prompt;
`thym_host.preflight_hook` holds it against the route's window with
`preflight.evaluate`'s 2,048-token reserve and refuses with the number and
the window that would fit ("the plan's largest prompt is 307 tokens and the
model's window is 2,048 with 2,048 kept free; a 32,768-token window would hold
it"). The window is a `Window`, read once and **only when a plan asks a
model** — an eager read once sent `GET /props` to the owner's 8080 from a
test; `tests/test_thym_run.py` now fails if a deterministic run reads it. A
cloud route's window is `thym_host.CLOUD_WINDOW` (32,768). The route itself,
the plan's `models` block, the `calls` ceiling and the refusal order are in
"Models" → "A model route per job".

### `thym 1`: one compiler, two grammars

The version line chooses the grammar (`parse.GRAMMARS = {0: THYM0, 1:
THYM1}`): **every `thym 0` program compiles and runs unchanged, forever**,
and `thym 1` is a superset. New syntax in a `thym 0` file is refused by a
**double compile**: the file is parsed again as `thym 1`, and if that
compiles the refusal becomes `version` at the earliest line holding a
`thym 1` feature — "this needs `thym 1`: a call in a condition without
parentheses (words t) at line 6; the first line says thym 0"
(`check.needs_thym1`). A `use` of a `thym 1` file from a `thym 0` program is
refused at the `use` line. A move declared `since: 1` is free as a name in
`thym 0` and reserved in `thym 1`; a declaration's `thym-1:` mapping is the
move as `thym 1` sees it (`declarations.views(decls, version)`); a
`thym 2` line is refused ("this compiler reads thym 0 and thym 1"). What
`thym 1` adds:

- **Types** `folder` (a folder of files, by Thym's folder rule; its members
  are texts; a filter over a folder is a folder), `line` (a numbered line of
  a text or short; fits where a string is taken) and `change` (an edit made
  against a line). A fabula's flavour is a property of the value, not a new
  type: `entail f as code` of a fabula known to be a fabulap is refused
  `flavour` at compile ("only a fabulac entails code").
- **Several outputs** (`gives code: folder, size: number`) and labelled gives
  (`give code: …`); every output given once on every path (`no-give` names
  the output a path misses); a folder output lands as a folder.
- **A loop that collects**: `let names = for each … end` with `keep <expr>`
  inside; every keep one type, and the loop binds `list of T` after its
  `end`. A loop whose body is more than one plain statement (or that
  collects, or nests) plans as **one loop node** (`move: for`, named by the
  loop's own line, `calls` its moves, `members: {at_most: n}` where the plan
  alone knows the size), and runs its body member by member; a refusal
  inside names the body statement, its line and the pass ("assert w > 100000
  (line 9, for x = the first member): …").
- **Contracts and `keeps`**: a `contract <name>(<params>)` block (only
  `let`, `assert` and `for each` lines; never asks a model; never named like
  a standard check) states what a move or a program promises, and a head
  `keeps <name> [of <output>] [against <names>]` holds it to a contract
  block or any known check (`check.known_checks`: the text's table,
  everything a declaration names, and the registry's). A failed keep re-runs
  the body when the move asks, up to its attempts, with the verdicts in the
  repair; a program's keeps are checked before anything lands. A move's own
  `repair` mapping may say `replaces: true`; its `failed` then stands
  instead of the runtime's verdicts on its last output, so a move that asks
  again for one part carries that part's verdicts alone (S3:
  `thym/run.py` `_move_replaces`; `moves/code.py` uses it for a part re-ask).
- **Recursion under `depth`**: a user move that calls itself (directly or
  through a cycle) must say `depth: <1–64>` under its why ("move tree-of
  calls itself; a move that calls itself says how deep it may go: add
  `depth: 8` under its why"); the plan carries `budget.depth`, and the run
  counts it on the stack ("again went 2 deep; its depth is 1"). `thym 0`
  keeps "has no recursion".
- **Smaller joys**: a call on the left of a comparison without parentheses
  (`if count h > 3`), `in` with a text on its right (a word in a text), a
  loop's `where` after a call, a bare path for a program with one input.
- **Fixed in both versions**: a call nested in a `for each` is evaluated per
  member (it no longer receives the list), and every refusal names the
  statement as the person wrote it and its line — never `t3`, "node 2", an
  exception class or a `repr` (`run._worded`; a runtime fault's detail goes to
  the record's `fault`, never into the message).

**The new moves, by family** (each a FEED headword; `thym_moves` lists them
with their signatures):

| family | moves | declared in |
|---|---|---|
| editing (THYM 21) | `lines`, `replace`, `drop`, `insert` (`before` or `after`, exactly one, refused at compile otherwise), `edit` (every change applied at once; `only-the-changed`), `reword` (asks), `join`, `say`; helpers `folders`, `gather` (merges readings into a fabula: `nothing-lost`, `ids-unique`); `count` and `words` grown | `thym.manifest.cosm` (`enough/thym/moves/edit.py`) |
| code (THYM 20) | `survey` and `history` (rules), `derive t as code with f`, `derive repo with f` (the fold), `entail f as code` (a cshort), `entail f as line \| overview \| manual` (a catem) | `fabula.manifest.cosm` (`moves/code.py`); see "Building a fabulac" |
| prose and verse | `derive … as prose \| verse` chooses the flavour | `fabula.manifest.cosm` (`moves/emf.py`) |
| the dialectic (THYM 22) | `question` (asks; a bank and the rules by scaffold), `record` (code), `settle` (asks only where an item must be read again; scaffold `direct`) | `thym.manifest.cosm` (`moves/dialectic.py`); see "The dialectic" |
| Ascribe | `propose` (asks: a reading's candidates for a holograph), and `project h as isograph \| allograph` (one extension) | `ascribe.manifest.cosm` (`moves/ascribe.py`); see "Ascribe's module" |

**Engines and their recording.** A move reaches the host only through
`ctx.engines[<name>]`, plain functions whose answers are plain data
(integers and strings, THYM 12.6). The runtime records **every engine call**
as `candidates/<node>-e<k>.1.cosm` and a replay answers from the record, so a
run replays with no dictionary, no git and no model. Answers carry only the
fields the moves read: FEED's entries cut to `thym_host.FEED_FIELDS`,
pronunciations to `PRON_FIELDS`, the `repo` engine's history to what
`history` reads. A new field a move reads is added to those lists, or a
replay recorded before it breaks. A folder input is snapshotted to
`inputs/<name>.folder.cosm` at the start of the run; a replay reads the
folder from there, and a run whose folder changed since it was planned is
refused ("repo changed since it was planned: tool/ has tree 3f2a…, the
plan recorded 91c0…; plan it again").

**A move a second format extends** (`extends: true`). A format may add `as`
kinds to a move another format declares, without declaring the name twice:
Ascribe's `moves:` adds `isograph` and `allograph` to Comprise's `project`
in one entry (`modifiers: {as: 'isograph | allograph'}`, its own contract
and `code`, `since: 1`; the code chooses by the call's `as`). The kinds join the
move's `thym 1` view only (`declarations._extend`, a `contract-when` and a
`code_when` per kind); the runtime runs the extending owner's code for that
kind (`run._kind_code`); a check may be registered for one kind
(`checks.check(name, kind=)`), so `default-deny`, `no-counts` and `epoch`
hold an isograph or an allograph to Ascribe's rules while Comprise's still
hold an isotype.
`thym 0` sees `project` as it was ("this needs `thym 1`: the word isograph
after as of project").

### The shipped programs

`defaults/thym/` holds nine files, read in place, listed last by `run with…`
(`thym_host.SHIPPED_PROGRAMS`): the three `thym 0` programs of 0.5.0 —
`publish-story` (text → package; three nodes ask), `read-my-way` (package,
morph, context → short; asks), `open-house` (Holotype → isotype;
deterministic), byte for byte the suite's `programs/` (`tests/test_thym_host.py`)
— and six `thym 1` files of the 0.6 round: `decompile-python` (five
programs, the stages of a fabulac build), `compile-python` (a fabulac compiled
back into code and its manual), `decompile-prose`, `decompile-verse`, `settle` and
`tighten`. **Each of the six is a ```` ```thym ```` block of `docs/THYM.md`
byte for byte** (`tests/test_thym_shipped.py`): a change to one is a change
to the text, made on cosmoes-site first and synced back, never here alone.

### What may live under `enough/thym/`

Comprise vendors `enough/thym/` (its `scripts/refresh_thym.py`), so the
package stays portable:

- **Imports**: the standard library, PyYAML, `enough.macrocosm` and
  `enough.thym.*` only — never another `enough` module, never `$HOME`, an
  `ENOUGH_*` seam or an install path. `tests/test_thym_run.py`
  (`test_the_runtime_imports_only_what_it_may`) parses the runtime's
  imports; the moves follow the same rule. Everything of enough's — the
  model, FEED, git, the dialectic's and Ascribe's engines — plugs in through
  `thym_host` as an engine or a coprocessor.
- **New modules are few and named**: the 0.6 round added `folder.py`
  (standard library only), `moves/code.py`, `moves/dialectic.py` and
  `moves/ascribe.py`; the pins' vendoring list names the first three, and
  Comprise's refresh must keep all four. The host modules beside them
  (`repo_engine.py`, `fabulac_prompts.py`) are never vendored.
- **The eager import** in `moves/__init__.py` loads `doc, edit, emf, morph,
  pack` only; `project`, `code`, `dialectic` and `ascribe` are loaded by
  `registry.load_all` from the declarations' `code:` keys, so a vendored copy
  without an engine refuses in words ("the syntax engine is not here;
  enough's host registers it (enough.thym_host.engines)") instead of failing
  to import.

### The routes ([enough/thym_api.py](../enough/thym_api.py))

Project routes (ModeGate 404s them at home); refusals are 400/404/409 with a
plain sentence; outputs land beside the **first input**, all at once or not
at all (`copy_all`), replacing an earlier copy.

| Route | Answers |
|---|---|
| `GET /api/thym/programs` | `{programs: [{name, where (project/canon/shipped), rel, steps, asks, takes: [{name, type, accepts}], gives, outputs: [{name, type}], version, why}]}`, project → canon → shipped; a row that does not compile is `{name, where, rel, problem}` |
| `GET /api/thym/program?path=&where=` | `{name, rel, where, why, source, volume}` (a name, a project path, a `canon:` path or a shipped file name; 404 when none) |
| `POST /api/thym/compile {path, where?} \| {text}` | `{ok, name, refusal: {stage, check, line, message}, refusals, estimate, version, takes, outputs}`; `refusal` is the first fault, `refusals` (0.7) every independent fault the checker found, the first first (`[]` when it compiles): a parse error still stops at the first, a checking fault does not (`Refusal.more`; `check` and `thym_check` print one line each) |
| `POST /api/thym/plan {program, where?, inputs \| path, mode?, route?, model?, calls?}` | `{ok, plan, atem, mode, fits, refusal, why?, route, models, models_line, calls, inputs, outputs, writes, version}`; rules mode refuses a plan that asks (check `agent-free` or `no-model`), model mode runs the route's checks and the preflight. `inputs` fills every input by name, each checked by its type (`thym_host.check_input`: "notes.md is a file; repo takes a folder") |
| `POST /api/thym/run {program, where?, inputs \| path, mode?, route?, model?, calls?}` | `{job}`: a CanonJob of kind `thym`, claim key the first input's path (so a run and a decompile of one file exclude each other), the generation lock in model mode on the local route only; result `{run, trace, atem, outcome, mode, route, models, outputs: [{name, type, path, rel, files?, folder?}], refusal?}` (a folder output lands as `<stem>.<output>/`). Refused before any job: compile 400, plan 409 (asks while rules/agent-free, a shut gate, an open cloud count with no `calls`, preflight), `mode: model` with no model 409 |
| `GET /api/thym/moves?version=0\|1` | `{version, moves: [{name, owner, format, signature, takes, gives, asks, contract, scaffold, since, versions, says, extended, …}]}`: every move a program of that grammar may call, from the declarations the compiler reads, grouped by owner in THYM 6.2's order (`thym_tools.moves_payload`, the same listing the `thym_moves` tool reads); `extended: [{owner, as}]` where another format adds to a move; 400 for any other version. Read-only. Its one reader is the page's Thym at hand (`thymRefLoad`) |
| `GET /api/thym/runs` · `GET /api/thym/trace?run=` | the 200 newest runs, newest first (`[]` when the root is absent) · one run's head and `path: thym:runs/<run>/<run>.trace.cosm` |
| `POST /api/canon/package {path, morph?, context?, encrypt?}` | runs the generated program `export` over the text and its **fresh** twin (409 "derive the twin first"), lands `<stem>.thym/` and `<stem>.package.cosm`; `encrypt: true` writes `<stem>.thym.enc` and returns `key` **once**, in the response only. Synchronous, under the text's claim |
| `POST /api/canon/unpack {path, key?}` | verifies every digest and span first, then writes `<stem>.md`, its twin named as the package's fabula declares (`fabula/1` → `<stem>.md.<flavour>.cosm`, an old `emf/1` → `<stem>.md.cosm`; source and locators renamed), `<stem>.morph|context|graph.cosm`; 400 sealed without or with a wrong key; 409 bad digest, unresolved span, or a file beside it that differs (identical bytes are fine); nothing written on any refusal |
| `POST /api/canon/read {path, morph}` | `{job}`, kind `read`: the generated program `reading` (`read f with mine`, or the null); result `{reading, label: "read through <name>", run, trace, mode}`; the file `<text-stem>.read-<morph>-YYYY-MM-DD-HHMM.md` (`-2`, `-3`) beside the text or package, with `read_through:` front matter and the THYM.md §14 footer. **Agent-free gated**; rules mode fails the job ("read has no scaffold") |
| `GET /api/thym-spec?lang=` | THYM.md, raw markdown; home-accessible (in `server.py`, not the router) |

**`where`.** A shipped program and a project file can share a bare name
(`tighten.thym`): pass `where: shipped`, `project` or `canon` to `program`,
`compile`, `plan` and `run` to choose; without it the project's file wins,
then Canon's, then the shipped one, as before.

**`writes`.** A plan names where each output will land: `writes: [{name,
type, rel, folder?}]` in `gives` order, by `landing`, the run's own naming
(`plan_writes`; a package also its folder form). `rel` is null when the first
input is not a project or store file (the outputs then stay with the run) or
the type does not say its extension. The page reads it and works no name out
for itself.

**A list as an input.** An input of type `list of T` is given as a JSON
array of paths, in order (`inputs: {notes: ["a.md", "b.md"]}`); each member
is checked as a single input is, as `notes[n]`. Its plan row is `{name, type,
path, sha256, members: [{path, sha256}]}`: `path` the first member's, which
the outputs land beside, and `sha256` over the members' digests in order (a
folder member also carries `files` and `bytes`); the reply's `inputs` give
`members: [{rel, sha256}]` with the row's own `rel` null. It plans and runs
(lane T3; `docs/fabula-landed-T3.md`): the run reads each member as a single
input and holds it to its own digest, the record lists the list row and then
each member as `notes[n]`, and a list of folders is snapshotted member by
member. On the command line a list is given by its name once per member, in
order (`notes=a.md notes=b.md`; bare paths when it is the program's one
input); a saved plan is run with the same number of members. `thym_run` and
`thym_check` take `<inputs>` lines the same way.

**Jobs.** Runs and readings are CanonJobs (`canon_jobs.KINDS` gained
`thym`, `read`) whose snapshot carries `progress: {node, of, name, move,
state}` (state `running`/`done`/`skipped`/`refused`), mirrored into
`chunk`/`chunks`/`message` for the existing toasts. A run landed or refused is
`done` (the result says which); a plan-time refusal inside the job fails it.

**`thym:` paths in the cosm viewer.** `server._cosm_volume` asks
`thym_api.thym_volume` first, so `GET /api/cosm` and `/api/cosm/lens` load
`thym:runs/<run>/<run>.trace.cosm|plan.cosm` (from the Thym root) and any
`<x>.thym` **file** as its enumerated program volume. A `.thym` path that is a
**folder** (a package's folder form) falls through to the ordinary volume load
and draws the package catalog.

### Packages, sealed packages, readings (Canon)

A package is the self-contained export of a text (THYM.md §15): the folder
form `<stem>.thym/` (`text.md`, `fabula.cosm`, `morph.cosm`, `context.cosm`,
`graph.cosm` as present, and `package.cosm`, the catalog with every file's
sha256, the program and run that made it, and the notice) beside the
single-file form `<stem>.package.cosm` (the same catalog with each file's
bytes inline). Canon treats both as kinds (`kind: package`, `kind: sealed`
for `<stem>.thym.enc`), lists each as one thing, and marks a text node
`package: {path, folder, sealed}`. **The cipher** (`enough/thym/vault.py`) is
Comprise's `comprise-bundle/0` vendored: a data key per package, AES-256-GCM
over 4 MiB chunks, an encrypted manifest, the key as Comprise's recovery code
(15 bytes, 24 base32 characters in six groups of four) wrapping the data key
by PBKDF2-HMAC-SHA256 at 600,000 iterations. `cryptography` is a dependency
since 0.5.0 (the owner's ruling, 2026-11-02), so a package sealed here is
Comprise's scheme exactly; the file keeps an HMAC-SHA256 encrypt-then-MAC
AEAD (`aead: hmac-sha256-ctr`, named in the file) for an install without
it. The reader holds a stranger's file as Comprise's does (fabula round T0):
at most `MAX_SEALED` (256 MiB) before anything is parsed, the clear part read
as a YAML stream with no anchors or aliases and at most `MAX_SEALED_EVENTS`
pieces (`plain_yaml_events`), and what opens held to `MAX_OPENED_RATIO` (4)
times the file, by the objects' own sizes, before a repeated chunk is joined. The UI has no button for sealing or unpacking in 0.5.0 (the manual says
so); `run with…` → `publish-story` makes the two plain forms, and "read
through…" reads either.

### The readvisor tools ([enough/thym_tools.py](../enough/thym_tools.py))

`thym_check`, `thym_run` and (0.6) `thym_moves`, behind the `macrocosm-oes`
skill (`skill_on`: off → one line asking the user to switch it on, nothing
runs), registered like `canon_tools` and traced under `trace_log_enabled`;
the first two have examples in `CANON_TOOL_INSTRUCTIONS` (995 of 1,000
characters) and the third is named there in one phrase (no room for an
example; `thym_tools.documented` keeps a tool out of `_DISPATCH` until a
block names it). None takes the lock or starts a job — a tool runs inside a
chat turn that holds the generation lock (see "The fabula" → the concurrency
rule) — and a run lands under the Thym root only: the answer names every
output and the trace and says the reader's run with… is what lands them
beside the text. `<model>` chooses the route (`local` by default; never the
chat's slot) and `<calls>` the ceiling. Refused at plan time, nothing run:
an asking plan with no model or agent-free on (in the host's words, naming
the first statement that asks), a shut gate, an open cloud count with no
`<calls>`, a preflight miss, and an asking plan over a text past
`canon_tools.TEXT_MAX` (24,000 chars), which belongs to the reader's run
with…. A run fires `{"canon": snapshot(kind="thym", …)}`. Tests:
`tests/test_thym_tools.py`.

### The conformance suite

`tests/fixtures/thym/` (THYM.md §24.3; its `README.md` is the layout):
`programs/` (fifteen: the three of 0.5.0, byte for byte `defaults/thym/`,
and `thym 0` and `thym 1` programs for the fold, loops that collect,
contracts, bounded recursion, folders, editing, the fabulac survey, the
dialectic and a list as an input, `join-the-notes`), `inputs/` (the orchard notes and their twin, a package in folder
form, `plain-letter.morph.cosm`, `on-the-train.context.cosm`, the folders
`little-tool/` and `tiny-tool/`, a fabulan of `close.md` and an answers
volume for it, texts to edit), `expected/<name>/items.cosm` and `plan.cosm`
(and `outputs/` where a run is frozen; the clock is pinned to
2026-11-01T12:00:00Z), `bad/` (43 compile-time refusals, the first line
naming stage, check and line; each file is read by its own version line, and
conform says `(thym N)`), and **replay fixtures**, every one with engine
records, so each replays with no dictionary, no git and no model:
`replay/publish-story/2026-11-01-2148-35b5/` (checkpoint A's run,
re-recorded 2026-11-05 under its own id on Qwen3.8-27B with thinking off; the
first recording predated engine records, replayed with live engines, and
broke when `MACROCOSM_VERSION`, which Canon stamps into a derived fabula,
moved) and `…/2026-11-02-0843-ff92/` (its FEED records re-recorded
2026-11-05 with `thym_host.FEED_FIELDS`: 752 KB to 174 KB), and one each for
`tighten`, `settle-the-answers` and `survey-a-repo`. A deterministic program
whose outputs carry a run's id cannot be frozen: conform runs it as its
recording (that run's id and clock) and compares its outputs byte for byte.
`python -m enough.thym conform`: **119 passed / 0 failed / 0 skipped**, with
or without FEED. A run that records no engine calls replays only while every
engine answers as it did, so record engine calls for any new fixture. A
replay refuses at the first input, call or prompt whose digest differs,
before any engine or model work.

### The UI (index.html, U1)

What 0.6 added (U1a: the route; U1c: the rest; `docs/fabula-landed-U1c.md`)
is listed after the 0.5.0 block below.

One CSS block and one JS block, both "Thym in the page (0.5.0, U1)", ending
`window.__thymReady = true`; every hook into older code is guarded by it.
`THYM` (state), `thymBodyHTML` (the `thym/1` layouts in the cosm viewer:
program steps with contracts, plan graph `thymGraphHTML` + cost line
`thymCostLine`, trace cards `thymTraceBody`/`thymRecordHTML`, morph
`thymMorphBody`, package `thymPackageBody`), `enterProgramDoc` (a `.thym`
file in the docs viewer at three densities), `thymFaceScales` /
`thymScalesHTML` (the ten scales on the twin's face when a morph is found:
`X.thym/morph.cosm`, `<text>.morph.cosm`, `<stem>.morph.cosm`,
`<stem>.thym/morph.cosm`), `thymRunOpen` / `thymReadOpen` (the `#thym-modal`
card: programs project → canon → shipped, the plan and its cost, run, the job
tracked by `canonTrack(job, {want})`, the trace opened by its `thym:` path;
agent-free lists only `asks: 0`), the reading band (`#read-band-mini`,
`#read-band-review`, `#read-band-edit`; `thymBandPaint`: "read through
<name>" + the footer line, never dismissable, on any file named
`<stem>.read-<morph>-YYYY-MM-DD-HHMM[-n].md`), and the `thym-run:<id>`
handle `cosmLoad` resolves through `GET /api/thym/trace`. 126 keys in six
catalogs (`docs.title.program`, `modes.docs.program.*`, `thym.*`; translated
properly in wave 3), bubbles `thym`, `package`, `reading`. **uicheck**
screens `thym-program` (docs viewer, fabula), `thym-plan`, `thym-trace`
(cosm viewer), `thym-run` (the card on the orchard notes, publish-story
chosen; no model, so the plan's refusal shows), `thym-read` (a reading with
its band); scenarios `thym-run-roundtrip` (the deterministic `count-words`
on `orchard/harvest.md`: listed project-first, planned "it can run", run,
the trace opens with green checks, `orchard/harvest.n.txt` in the tree) and
`thym-read-labelled` (the band in every face and size, gone on close, the
text unchanged). Seeded by `scripts/uicheck/server.py` `_seed_thym` in
`orchard/`.

**0.6 (U1a, U1c, U1d; `docs/fabula-landed-U1d.md`).**

- **The run card's route and inputs.** `#thym-route-box` (`thymRouteHTML`,
  the model line of "The fabula" → "The UI") sits above the plan; `route` and
  `calls` go to `/api/thym/plan` and `/api/thym/run`, and a route change plans
  again. `THYM_PICK` holds `inputs`, `takes`, `outputs`, `source`, `preset`,
  `told`, `where`. `thymRunOpen({input, program, name, inputs})` always reads the
  program list; `thymProgramChosen` reads what the program takes (the list
  row, else `POST /api/thym/compile {path}`) and its source. One row per
  input in `#thym-inputs` (`role=group`; `thymInputsPaint`, `thymInputSet`):
  the name, the server's `accepts` words, a text field with a `<datalist>` of
  only what fits the type in the project's tree (`thymCandidates(type)`,
  `thymFits`: texts and shorts with readings left out; twins by flavour,
  labelled "prose · fabulan" …; folders, links left out; volumes, answers
  files labelled "answers"; morphs, contexts, packages in all three forms).
  Filled from the last inputs given to this program (localStorage
  `enough.thym.inputs`, per program, only paths still in the tree;
  `thymInRemember` / `thymInRemembered`), then the opener's `inputs`, then the
  text the card opened on (a fabula input gets its twin). The plan is asked
  only once every input is given ("give it {names} to see its plan"); the body
  is `{program, inputs: {name: path}}` (`thymInputsBody`; the `path`
  shorthand is no longer sent). The server checks every input again; its 400
  shows as the plan's error. A `list of …` input is a group of member fields
  in order (add another, remove; `thymListMembersHTML`,
  `thymMemberAdd|Remove|Set`), sent as a JSON array (`inputs: {xs: [...]}`);
  it is ready with one non-blank member. `where` is sent wherever a program
  is named (`thymProgramURL`, `THYM_PICK.where`, `DOCS.progWhere`), and each
  program radio carries `data-where`.
- **The plan reader.** `thymPlanPaint` → `thymPlanReadHTML(pl, {source,
  program, where})`, `thymPlanNodeHTML`, `thymStmtHTML`: the
  cost line (`atem`) and `models_line`; a refusal with its statement (the
  program's line from `GET /api/thym/program`'s `source`) and, for a project
  program, "edit it at line N"; "its steps, in the order they run", each node
  at its line with its statement, the asks badge and under it
  `members.at_most` ("a loop: at most N passes") or "a loop over a collection
  known only at run time", `keeps`, `budget.depth`, "up to N attempts, each
  checked", "its model calls are counted only as it runs" for a node in
  `models.calls_open`; "what it reads" (a folder's files and bytes and the
  snapshot sentence: the plan holds the tree digest; a list's members in
  order); "what it will write" reads the plan's `writes` (each output's path
  as the run will name it, beside the first input or a list's first member,
  all at once or none).
- **Outputs and refusals.** A landed run stays on the card: "what it made, N
  outputs", each by name and type with **open** and its path (a file where
  its kind reads, a folder in Canon's folder view, a package at its catalog),
  focus on the first open, "show the trace" in the foot; a run whose card was
  closed opens its trace from the toast. A refused run (`outcome: refused`):
  `thymToldLoad(run)` reads the trace — each failed record's failed checks
  with their `why` (a kept contract's `assert … else "…"` words), and "what
  the model was told when it was asked again" (the failures that rode into
  each re-ask, `record.tries`, THYM 12.2). The trace viewer's record cards
  fold the same under "attempts that failed: N".
- **The editor's strip** ("writing a program: the compiler beside the
  editor"): `#thym-ed` between the edit face's toolbar and its textarea, the
  mini editor's own `#thym-ed-mini`. `THYM_ED`, `thymEdOpen(path, size)`
  (called from `_showFullEdit` / `_showMiniEdit`, closed by `_hideFullEdit` /
  `_hideMini`, all guarded by `__thymReady`), `thymEdCheck` (`POST
  /api/thym/compile {text}` after a **700 ms** pause, `THYM_ED_WAIT`; never
  `/plan`, `/run` or a model — the scenario asserts the wire), `thymEdPaint`,
  `thymEdGo(line)`, `thymEdStep(back)`, `thymEdRefusals()` (steps through
  `refusals: [...]` if the compiler ever returns several); F8 / shift+F8 in
  the capture phase, only while no dialog is open; `saveEdit` repaints. The
  textarea is plain (no editor library), so a refusal is never painted on its
  line: the strip names the line as a button and F8 selects it. It says ✓ "it
  compiles: program {name}, nothing refused" or ✗ `line N` + the check + the
  compiler's message **verbatim**; the version line read from the first line
  (`thym.ed.v0|v1|vNone`); takes · gives · steps · asks once clean; "a plan
  and a run read the file as saved" while the text differs from disk; after a
  copy, where it came from. The state is a polite atomic live region.
  Buttons "the moves…" and "plan and run…", the `(?)` `thym-editor`. Entry
  points: the tree's option-click on a `.thym` ("edit the program"), the
  program page's "edit" (project files), a plan's "edit it at line N", a copy.
- **Thym at hand** — `#thym-ref-modal`, two tabs (`role=tablist`, arrow
  keys): `thymRefOpen`, `thymRefSkeleton`, `thymRefLoad`, `thymRefPaint`,
  `thymRefTab`, `thymRefMoveHTML`, `thymRefPut`, `thymRefCall`,
  `thymRefProgramsHTML`, `thymRefClose`. **the moves** from `GET
  /api/thym/moves?version=` (S4; no stand-in in the check), in the route's
  order, grouped by format (`thym/1`, `fabula/1`, `doc/1`, `comprise/1`,
  `ascribe/1`), a move another format adds to with one line per extension
  (`thymRefExtended`, "ascribe/1 adds `project … as isograph`"), searchable
  by any word of a move or of what an extension adds (↓ to the first **put
  it in**, there only while a program is open in the editor), the `thym 1` / `thym 0` switch
  (defaults to the open program's version line); **put it in** writes the
  call at the caret, selects its first operand, closes the dialog, returns
  focus to the text and checks again. **programs to start from**: every
  `where: shipped` row of `GET /api/thym/programs` with its `why:` line,
  **read it** and **copy into this project to change it**
  (`thymCopyProgram`: `GET /api/thym/program` for the source, `POST
  /api/file` to `programs/<file>.thym`, `-2`, `-3` …, opened in the editor
  with "a copy of {file}: yours to change; the original is unchanged"). Copies
  go to `programs/`, not the top, because a shipped program's `rel` is its
  bare file name and a top-level copy collided with it in the run card (U1c
  7.4; S4 tells a shipped program from a project file of the same name).
  "the moves…" is on the strip and a program's page; the run card's "read
  the shipped programs, or copy one to change it…" opens the same dialog at
  its programs tab. Bubble `thym-moves`.
- **The dialectic's second run.** The dialectic card offers, on a fabula
  with sittings, "run with {file}…" per sitting: it closes the card and opens
  run with… on `settle.thym` with `f` = the fabula and `said` = the sitting,
  planned at once.
- **uicheck (0.6).** Seeds in `_seed_thym`: `broken.thym` (refused at line
  9, `unknown-move`), `two-outs.thym` (`thym 1`: a folder and a short in, `n`
  and `listing` out), `little-repo/`, `long-lines.md`, the tighten replay
  trace. Screens `thym-editor`, `thym-editor-mini`, `thym-moves`,
  `thym-programs`, `thym-run-inputs`, `thym-run-asks`, `thym-run-landed`,
  `thym-run-refused` (the last two place a recorded shape; they run nothing),
  `thym-trace-tries`. Scenarios `thym-editor-checks` (the compiler's words
  byte for byte, the live region, F8, only `/api/thym/compile` on the wire),
  `thym-moves-put`, `thym-run-folder-outputs`, `thym-shipped-copy`,
  `thym-settle-from-dialectic`; `thym-run-roundtrip` now waits for the card's
  outputs, then "show the trace", and tells a shipped row by its
  `data-where`. U1d added the seeds `orchard/join-the-notes.thym` (a list of
  shorts) and a top-level `open-house.thym` beside the shipped one, the
  screens `thym-run-list` and `thym-run-same-name`, and the scenarios
  `thym-run-list`, `thym-moves-route` and `thym-same-name`; `thym-moves` and
  `thym-moves-put` read the real route (no stand-in).
  `tests/test_ui_check.py` pins them.

### Tests

`tests/test_thym_spec.py` (the spec's blocks compile; every `bad/` program
refused at its stage, check and line), `test_thym_compile.py`,
`test_thym_run.py` (incl. the import rule and "a deterministic run never
reads the window"), `test_thym_moves.py`, `test_thym_host.py` (shipped ==
suite programs; routes, engines), `test_thym_api.py` (the routes through the
app), `test_thym_tools.py`, `test_thym_cli.py` (`--model`, `--calls`, the
vendored file's added lines); for `thym 1` `test_thym_versions.py` (the two
grammars, the double compile, `since`), `test_thym_fold.py`,
`test_thym_loops.py`, `test_thym_keeps.py`, `test_thym_folders.py`,
`test_thym_edit.py`, `test_thym_code.py` + `test_repo_engine.py`,
`test_thym_dialectic.py`, `test_thym_shipped.py` (the nine programs, the
text's blocks, the `thym 1` table of 6.3 against the real declarations);
`test_canon_package.py` (the cipher; packages in Canon's scan, catalog and
mirror), `test_canon_tools.py` (package refusals), `test_cosm_api.py`
(`/api/thym-spec`), `test_ascribe.py`, `test_ascribe_module.py`; the UI's in
`test_ui_check.py`. None reaches a model: the coprocessor is a fake,
a replay, or the refusing one.

---

## Building a fabulac (a folder of Python, 0.6)

A folder of code is decompiled into a **fabulac** (a fabula of flavour
`fabulac`), compiled back into a **cshort** (source rebuilt from the
fabulac) and said at depth as a **catem** (everything a user can do with the
program). Spec: MacroCOSM OES §18.4.7, THYM §20 (20.6 decompiling, 20.7
compiling, 20.8 what is never run); pins P7. Files:
[enough/fabulac_job.py](../enough/fabulac_job.py) (the job, the compile, the
read-only views, their router), `enough/thym/moves/code.py` (the moves),
[enough/repo_engine.py](../enough/repo_engine.py) (the engines),
[enough/fabulac_prompts.py](../enough/fabulac_prompts.py) (the prompts),
`defaults/thym/decompile-python.thym` and `compile-python.thym` (the
programs). Lane notes: `docs/fabula-landed-T1-code.md`, `-SV.md`.

**The band (this edition).** Pure-Python source a person could read in an
afternoon: up to `code.BAND_FILES` = 60 Python files and `BAND_LINES` =
6,000 lines, no C extensions, no generated code. `survey` refuses past it
("more than sixty Python files: past what this build reads", "more than six
thousand lines of Python: past what this build reads"; "there is no Python
file here: this edition builds a fabulac of Python only"). The licence is
read from the repository and recorded in `source.licence` (the licence's
standard short identifier when the text is one the rule knows, else the
packaging metadata, else the licence file's first line); a repository with
none is built with `licence: {pending: …}` and `licence-recorded` warns. A
fabulac is built from a folder **in the project**, never in the Canon store
("a fabulac is built from a folder in the project, not in the Canon store").

**The fabulac on disk.** `tool/` → `tool.fabulac.cosm` beside it, one file.
Its `source` names a folder: `{path: tool/, kind: folder, language: python,
files, bytes, tree, commit?, origin?, licence}`, where `tree` is MacroCOSM's
tree digest over the files read (`macrocosm.tree_digest`, the same value as
`enough/thym/folder.py`'s) and **fresh means the digest still matches**. A
code item's `span` is `{file: pkg/mod.py, lines: "12-40"}`. `derived` holds
`program`, `run` and `runs` — one `{program, run, at, model?, route?,
provider?}` per run that wrote into it, `program` being the program's name
(its `program` line, e.g. `survey-the-repo`), so a fabulac built in five runs
says which model made each part. `completeness: outline` is a rules-only
skeleton.

**The five stages** (`fabulac_job.STAGES`; the five programs of the shipped
`decompile-python.thym`, always the shipped file, never a project's file of
that name), each **one atomic Thym run**, the job resumable between them:

| stage | program | asks | what it lands |
|---|---|---|---|
| survey | `survey-the-repo` | no (rules) | files, components and interfaces from the syntax tree, dependencies, settings, the licence, the means; `completeness: outline` |
| history | `read-the-history` | no (rules) | changes from the clone's log, grouped into episodes; releases from tags; makers as roles and counts (a name only where the repository states it) |
| read | `read-every-file` | yes | per file: behaviours, structures, cases from the tests, terms, concepts, claims, events (`derive t as code with f`, `gather`ed) |
| fold | `fold-the-whole` | yes | over the whole: aims, audiences, uses, requirements, decisions, exclusions, inspiration, the atem |
| question | `raise-the-questions` | yes | the dialectic's questions where the build was unsure (to `maker`) |

After each stage the fabulac so far is written over `<folder>.fabulac.cosm`
all at once, with the run in `derived.runs` (the host writes the entry for
the read and question stages, whose `gather` keeps the `with` volume's
catalog). **State is read from disk only** (`fabulac_job.build_state`): a
stage has landed when `derived.runs` holds its entry, checked against the
run's trace under the Thym root when it is there. A build takes up again
after the last stage that landed while the folder's tree digest equals
`source.tree`; a folder that moved is built again from the survey. Cancel,
refusal, crash, app quit: the stages that landed stay. **Modes** are decided
once before the job starts: in model mode every stage runs, the asking ones
on the job's route (`local` by default; `cloud` only when asked and the
gate is open); with no model, agent-free, or `mode: rules`, survey and
history run and the build stops with the outline, its job `done` with
`complete: false` and the read stage's refusal in the host's words.

**The engines** (`ctx.engines["repo"]`, `["syntax"]`; every call recorded
for replay): `repo.history(folder)` (newest commit first, at most 400
commits, bodies cut at 600 characters, at most 60 paths a commit; or
`{clone: false, why}`), `repo.tree`, `repo.files`, `repo.text`;
`syntax.outline(path, text)` (Python by `ast.parse` on the text: imports,
definitions with exact signatures, constants, environment reads, `argparse`
parsers as written), `syntax.parse`, `syntax.manifest` (`pyproject.toml` by
`tomllib`, `setup.cfg` by `configparser` with interpolation off,
`requirements*.txt` by line).

**Nothing read or entailed is ever run** (THYM 20.8). No file of the folder is
executed, imported or installed; `setup.py` is read as text, never run. Git
is reached by **one** fixed command line (`repo_engine.run_git`): a fixed
absolute binary (no PATH lookup), `shell=False`, standard input closed, a 20 s
timeout and an 8 MiB answer cap, every hook, pager, editor, credential
helper, ssh command, external diff, text conversion, signature program and
protocol switched off by `-c`, and only `git log … HEAD --` and `git
for-each-ref refs/tags` — no command that touches the index, the work tree or
the network. A cshort is **text in enough, never code**: its files are read
as bytes and decoded for the viewer, never imported, compiled or run, and a
link inside a cshort is not followed.

**Compiling** (`POST /api/fabula/compile` on a fabulac, or the tool's
`compile`). `what: code` (the default) runs `compile-python.thym`: `entail f
as code` writes the cshort file by file (asks once per file; contract
`parses`, `interfaces-present`, `files-present`, `footer`, `provenance` —
`parses` reads the syntax engine's outline of each rebuilt file, nothing
compiled) and the `manual` catem. `what: line | overview | manual` runs
`entail f as <depth>` alone. Without a model a cshort is refused ("a cshort
needs a model, and none is answering (…)"), and a catem is its scaffold
(`uses-outline`, state pending, recorded `mode: rules, by: rules`). The
cshort lands as the folder `<name>.cshort-<YYYY-MM-DD-HHMM>/` (the rebuilt
tree and `CSHORT.md`, whose first line is the footer — "*a cshort of
tool.fabulac.cosm, in Python, compiled on … by …; never run*" — then the file
table with digests, what was not rebuilt, and the source's licence line), a
catem as `<name>.catem-<YYYY-MM-DD-HHMM>.md` (its footer says its depth),
both beside the fabulac (UTC, `-2`, `-3` on a collision), recorded in the
fabulac's `shorts:` (`{path, at, by, mode, order: code, route?, language:
python, files}`; `files` the files rebuilt, `CSHORT.md` not counted) and
`catems:` (`{path, at, by, mode, route?, depth}`), every other byte kept. A
fabulac's own `atem:` stays the four-part atem; a catem at depth `line` is
that line.

**The routes** (`fabulac_job.build_router`; `path` the folder or its
`.fabulac.cosm`): `POST /api/fabula/build {path, route?, model?, calls?,
mode?, restart?}` → `{job, state, from}` (a CanonJob of kind `fabulac`; its
`progress` `{stage, program, n, of, files_read, files, calls, at_most,
route}`, message "stage 3 of 5: read, 2 of 5 files read"); `POST
/api/fabula/resume` (the same body; 409 "nothing to take up again: …");
`GET /api/fabula/build?path=` → `{state, job}`; `POST /api/fabula/cancel
{path}`; `POST /api/fabula/compile {path, what?, route?, model?, calls?,
mode?}` (kind `compile`; any fabula that is not a fabulac goes to the
text's short compile); `GET /api/fabula/compiled?path=` (the fabulac's
shorts and catems); `GET /api/fabula/cshort?path=` (the cshort's files,
`CSHORT.md`, footer, licence); `GET /api/fabula/cshort/file?path=&file=`
(one file as text; a link, a non-UTF-8 file or one over 1,000,000 bytes is
refused in words); `GET /api/fabula/catem?path=`. Refusals are plain
sentences in `{"detail": …}` — among them "<p> is a file; a fabulac is built
from a folder of Python", "<raw> is reached through a link; nothing is read
through a link", "rness/ is enough's own folder, …", "already built: <f>
holds every stage; pass restart to build it again", and the gate's own words
(403) for a shut cloud route. A job that stops says what landed and where
the build takes up again ("cancelled during read; nothing of it was written;
landed before it: survey, history; the build takes up again from read").
The full contract (bodies, results, every refusal) is
`docs/fabula-landed-SV.md` section 1.1.

**The rebuild test** (pins P7, outside enough): a frontier model given only
the fabulac writes the cshort; the original repository's own tests run
against it in a throwaway sandbox; a second model grades behaviour against
the fabulac. Nothing of it runs inside enough, and agents of this repo may
not clone or run third-party repositories.

### The UI (index.html, U1a)

User-facing: HELP_CENTER §12.7 (building) and §12.8 (compiling, reading,
never run). Lane note `docs/fabula-landed-U1a.md` 4 and 5.

- **The folder face** of `#fabula-modal`: `fabFolderOpen(folder | fabulac)`
  → `GET /api/fabula/build` (+ `/api/fabula/compiled`) → `fabFolderPaint`,
  painted through `fabSet`. Entry points: the tree's option-click on any
  folder that is not `rness/`, a Holotype or a `*.thym` package folder ("build
  its fabulac…"); on a `.fabulac.cosm` file "build and compile…"; the cosm
  viewer's `#cosm-fab-btn` "build and compile…" on a fabulac (`fabIsFabulac`:
  the name, or `catalog.flavour: fabulac`). The five stages ✓ landed (model,
  here / on the cloud, or "by rules"), ▸ running, · waits; "N Python files";
  one state line (none yet / moved / complete / outline / partway / folder
  gone). The model line with the per-stage ceiling.
- **Running.** `fabProgressText`: "stage n of 5: read · k of m files read · k
  model calls, at most n · here|on the cloud" (also the toast's line and
  `canonBusyPaint`'s), a bar from `chunk/chunks`; a queued build shows stage 1
  from its first snapshot (S2). Foot: **build** | **take up again** (`POST
  /api/fabula/resume`, when `landed > 0`, `!complete`, `!moved`) with "build
  again from the survey" beside it | **build again** (`restart: true` when
  complete); **cancel** (`POST /api/fabula/cancel`) while a job runs; "open the
  fabulac". A `done` job with `result.refusal` is the outline: the card and
  the toast show the job's `message` (S2 keeps it in the result). A build
  already running when the card opens is adopted: `canonTrack(job, {want:
  'fabulac'})`.
- **Compile.** "compile it": as code | a catem at depth line | overview |
  manual → `POST /api/fabula/compile {path: <fabulac>, what, route, calls?}`,
  with the line "a cshort is text to read: enough never runs it" and a refusal
  in the server's words (409 "a cshort needs a model, and none is answering
  (…)"). "what it has made" lists `GET /api/fabula/compiled` (by, route,
  date, files or depth, "not there any more", open).
- **The viewer** — `#cshort-modal`, `fabViewOpen(path)` / `fabViewPaint`. A
  cshort: "a cshort is source code to read: enough never runs it, and nothing
  here can." once in bold, the footer, the licence line, the file list (links
  listed, disabled), one file at a time from `GET /api/fabula/cshort/file` in
  a monospaced `<pre>` (markdown rendered). A catem: its depth line and the
  markdown with its footer. **No run, terminal or download control anywhere;
  keep it so** (the `cshort-read` scenario asserts it). Also from a cshort
  folder's / catem file's option-click ("read the cshort" / "read the catem")
  and a compile's done toast; the tree tags a cshort folder "cshort".
- **In the cosm viewer**, every fabula's rail gains `fabMadeHTML`: "made by
  <model> · on the cloud|here · <date>", an "N runs" disclosure of
  `derived.runs`, "an outline: …" for `completeness: outline`, "licence of the
  source: …" or the pending sentence.
- **uicheck.** Screens `fabula-build`, `fabula-cosm`, `fabula-cshort`,
  `fabula-catem`; scenarios `fabulac-build-outline` (the folder menu item; a
  build by rules lands survey and history, two ✓ and the job's words, take up
  again and open offered; the viewer shows build and compile… and the outline
  line) and `cshort-read` (open from the list; a `.py` as text in a `<pre>`;
  no run/terminal/download control; Esc closes only the viewer, focus back in
  the card). Seeded by `_seed_fabula` in `works/`.

---

## The dialectic (module D, 0.6)

The core's one primitive for asking a person what a source means and
recording what they say. Spec: MacroCOSM OES §18.6 (18.6.2 module D, 18.6.4
what an answer writes, 18.6.6 banks, 18.6.8 its checks), THYM §22 (the
dialectic in a program), Ascribe §8 (applied to a holograph); pins P4.
Files: [enough/dialectic.py](../enough/dialectic.py) (the deterministic
core), `enough/thym/moves/dialectic.py` (the three moves),
[enough/dialectic_api.py](../enough/dialectic_api.py) (the routes),
`enough/fabula_tools.py` (the tool). Lane notes:
`docs/fabula-landed-D1.md`, `-T1-dialectic.md`, `-SV.md`.

**Module D, which any volume may carry.** The core declares it in
`defaults/cosm/manifests/core.modules.cosm`, and every format inherits it
(the reader's registry adds it to every manifest that does not declare the
letter). Two kinds:

- `D:question/<slug>`: `about` (an item id, with an optional `#field`; a
  module or kind; or a span of the source), `asks` (the question, plain
  words), `why` (`missing` | `unsure` | `ambiguous` | `intent` | `conflict` |
  `counter`), `kind` (the answer's shape: `text` | `choice` | `yes-no` |
  `number` | `date` | `ref` | `span`), `options`, `to` (who can answer:
  `author` | `expert` | `maker` | `holder` | `owner` | a role's id |
  `anyone`), `raised` (`{by, at, run}`), `state` (`open` | `answered` |
  `unknown` | `declined` | `stale` | `withdrawn`) and `answers` (appended,
  never rewritten: `{at, by, says, value, confidence, session}`).
- `D:session/<id>`: `{at, with, through: person | agent, model, asked,
  answered, skipped}`.

What an answer writes carries `provenance: {mode: dialectic, sources:
[D:session/<id>], confidence}`; Ascribe's `session-<n>` and Comprise's
`elicit-…` stay valid spellings of a session. `{pending: "…"}` stays the
inline short form: a question may be about a pending field; "I don't know"
answers it `unknown` and leaves the field pending in the person's own words;
`declined` writes `provenance.state: not-disclosed`. The checks
(`question-about`, `question-shape`, `session-declared`) are
`enough/fabula.py`'s and run on any volume holding D items.

**Banks.** A manifest's `dialectic:` key holds banks of opening questions
(`Manifest.banks()`): the fabula carries one per flavour (17 fabulan, 25
fabulap, 17 fabulac; each entry says which kind it writes), Ascribe's 44
are one bank (`ascribe`, put to the holder alone), Comprise's are named by
its manifest. Beside a bank, the core's rules raise one question per
pending field and one per unsure item, and (0.7) one `why: conflict` per
case that says a different count of a thing than a behaviour it cites
("four lines" against "five lines": `dialectic.count_conflicts`, read from
their words, never the case's code; only where each side says one count of
it, and never a rate such as "one line per add").

**Two runs with a person between them, never a suspended run.** A run lands
questions; a person answers them (in the page, through an agent, or with
`python -m enough.dialectic answer`); a second run settles the answers into
the volume. "Nothing partial" and replay hold as they always did. In Thym:
`question` (volume → its questions; from a bank and the rules by scaffold,
or raised by the model when it asks), `record` (answers into the volume's
questions; code) and `settle` (folds answered questions into the items they
are about; asks the model only where an item must be read again in the
light of an answer; scaffold `direct`), held to `addressed`,
`no-duplicate`, `only-the-asked`, `provenance`. The shipped
`decompile-prose`, `decompile-verse` and `settle` programs are the two runs.

**An answers volume.** A sitting on a single-file volume is written beside
it, the volume untouched, as `<name without .cosm>.answers-<YYYY-MM-DD-HHMM>.cosm`
(`dialectic.answers_path`; `close.md.fabulan.cosm` →
`close.md.fabulan.answers-…cosm`, UTC, `-2` … on a collision); settling folds
it in. A sitting not yet settled is read with the volume when its questions
are listed, so a question it answers is not put again and cannot be answered
twice (`dialectic_api.ledger`). A holograph's answers go into its own module
D (`D/questions.cosm`, `D/<session>.cosm`), by Ascribe's rules.

**Settling.** A fabula: one `settle.thym` run per unsettled sitting, oldest
first, on the chosen route, each run's output replacing the volume all at
once; under rules (no model, agent-free, `mode: rules`) the run takes
`settle`'s scaffold `direct`. Any other volume, and a holograph, is settled
at once by rules (`settle_holograph` for a holograph); an answer whose item
a model would have to read again waits, and the reply says which. A
re-derive carries the volume's D items over and stales the questions whose
item went (`canon_derive.carry_dialectic`, `dialectic.carry_over`). The
volume is always written back **byte for byte outside the change**.

**The routes** (`dialectic_api.build_router`; one family for every volume,
dispatching on its format, so the card and the tool never choose by
format): `GET /api/dialectic/questions?path=` (the open queue — a
holograph's thinnest container first — the waiting, the counters, the
sittings), `POST /api/dialectic/check {path, question, value}` (the value as
it will be written, or the shape's words; for a holograph also the
personal-data refusal), `POST /api/dialectic/answers {path, answers: [{question,
value?, says?, dont_know?, declined?, skip?, confidence?}], through?, who?,
to?, model?}` (one sitting; an answer that cannot be kept is in `refused`
with its words and the rest are kept), `POST /api/dialectic/settle {path,
route?, model?, calls?, mode?}` (a CanonJob of kind `dialectic`), `POST
/api/dialectic/raise {path}` (the format's bank and the core's rule
questions, by rules), `POST /api/dialectic/ask-again {path, question}`.
`path` names the volume: a holograph, a `.cosm` volume, a folder with its
fabulac beside it, or a text (→ its twin). A write is made under the
volume's claim (409 "<p> is being derived right now; …"). The full contract
is `docs/fabula-landed-SV.md` section 1.3.
`GET /api/dialectic/questions` also lists `closed` (settled or declined
questions, newest first, at most 50; `closed_total` counts them all), and
each card's `candidate` says where a reading saw a candidate (`text`,
`sha256`, `span`, `confidence`, `made`), null for anything else. `POST
/api/dialectic/raise` with `dry: true` counts what it would raise (`count`,
`by` bank entry or rule) and writes nothing. A recorded sitting and a landed
settle send the `dialectic` event (`{path, session, what: recorded |
settled}`) on the app's event stream; since 0.7 so do a raise that landed
questions (`what: raised`, from the route or the tool) and a question asked
again (`what: asked-again`), each with `session: null`. (S3; `POST /api/dialectic/answers`'
`recorded` now says `answered`, `unknown` or `declined` for an address too.)

**The tool** `dialectic` puts **one or two questions at a time** (`SHOWN`
= 2) and records the person's words **verbatim** (`through: agent`, the
model's id); it never answers for them ("Never answer for them."), and
`<do>settle</do>` folds the answers in. See "Tools".

**The command line**: `python -m enough.dialectic list|raise|answer|settle
<volume>` (`answer` interactive by default: `?` I don't know, `-` skip, `x`
decline, `q` stop; `--from ANSWERS` records an answers volume; nothing but
the volume and its answers volumes is ever written). Run it under the seams.

### The UI (index.html, U1b)

User-facing: HELP_CENTER §13.7. Lane note `docs/fabula-landed-U1b.md`, with
S3's adoptions in `-U1c.md` 8. Markup `#dialectic-modal` (a `*-modal`), CSS
"0.6 (U1b): the dialectic card", JS block "The dialectic in the page (0.6,
U1b)" ending `window.__dlgReady = true`; every hook in older code is guarded
by it. State `DLG` (separate from `FAB` and the editor's).

- **Open.** `dlgOpen(path)` takes any volume path the routes take (a text, a
  twin, a fabulac or its folder, a holograph folder, a `.cosm`). From: the
  cosm viewer's `#cosm-dlg-btn` "questions" with the open count
  (`dlgCosmPaint`; a project volume whose listing answers, not `canon:`,
  `thym-run:` or inline volumes); the fabula card's `#fab-dialectic` line on
  both faces (`dlgFabLine`); a decompile's or a build's done toast that landed
  questions (`dlgToastOffer(toastId, volume, toastOpts)`, also for a Thym run
  that lands them); a settle's toast.
- **Listing and the queue.** `dlgLoad` → `GET /api/dialectic/questions`, plus
  `GET /api/cosm` of the volume (the ids a `ref` answer may name, module
  names). **One or two at a time**: `DLG_SHOWN = 2`, `dlgQueue` (the server's
  order; what a settle or a refusal put next at its head; nothing already in
  the sitting). `dlgQuestionHTML`: asks, why, for whom, about (a link that
  closes the card and opens the viewer on that item), hint, and the input
  `dlgInputHTML` fits the kind (text / `many` one to a line; choice as radios
  or checkboxes with "other:" when `options_open`; yes-no; number with
  min/max; date; ref with a datalist of the volume's ids filtered by the
  `options` prefixes; span), plus three toggle buttons (`aria-pressed`) "I
  don't know", "I'd rather not say", "skip for now".
- **The live check.** `dlgCheckSoon` / `dlgCheck` / `dlgCheckPaint`: `POST
  /api/dialectic/check` 450 ms after typing stops (at once for a radio or a
  checkbox); the refusal beside the field in `.dlg-check` (`aria-live=polite`,
  the field `aria-invalid`); a value written differently is said back
  ("written as: true").
- **Drafts and the sitting.** Drafts live in `DLG.drafts` per volume until
  recorded: closing the card, following an item link or another sitting
  landing loses nothing (words typed for a question answered elsewhere are
  said and kept). "keep these, and the next" holds the pair; "send the
  sitting (N)" (`dlgSend`) posts `{path, answers, through: "person"}` (never
  `who`); the reply is shown per question in the server's words; a refused
  answer comes back first with what was typed; a 422 puts every answer back.
- **The re-read.** `dlgOnEvent` on the `dialectic` SSE event (S3): an open
  card on the named volume reads its listing again, drafts kept, not while its
  own sitting is being sent; `dlgOnAgent` on the chat's `tool` event with
  `name: dialectic` says "the readvisor recorded answers beside this volume
  …"; also a re-read on window focus. The question area repaints only when
  what is shown changes (`DLG.mainKey`), so typing survives a re-read.
- **Settle, closed, raise.** `dlgSettleHTML` / `dlgSettle` / `dlgJobOnSnap`:
  a fabula's settle carries the model line (`fabRouteHTML('dlg', {ceiling:
  'cloud'})`) and is followed as a CanonJob (`want: 'dialectic'`); any other
  volume and a holograph are "settled at once, by rules" and send `{path}`
  only. After: the job's `message`, "waiting" (`waiting_in` → "in the sitting
  X, not settled yet", else "waits for a model to read <item> again"),
  `counters` and a holograph's `follow_ups` put next. On a fabula with
  sittings, "run with {file}…" per sitting opens Thym's run card on
  `settle.thym`. "answered before (n)" reads the listing's `closed`
  (`dlgClosed`) with "ask again" each (`POST /api/dialectic/ask-again`).
  "raise the questions" when the volume holds none (`dlgRaiseHTML` /
  `dlgRaise`), with the count read first by a dry raise (`dlgDryLoad`,
  "raising them asks N questions").
- **uicheck.** Seed `_seed_dialectic` in `talks/` reads the check's own
  fixtures, `scripts/uicheck/fixtures/dialectic/` (`DIALECTIC_OWN`; see "The
  browser check owns its fixtures" under the pre-commit suite), with
  `DIALECTIC_KINDS` added on top, and per-language `answer-<lang>/` and
  `self-ask-<lang>/` copies (the scenarios write). Screens
  `dialectic-card`, `dialectic-kinds-yes-number`, `-date-ref`,
  `-span-pending`, `dialectic-sitting`, `dialectic-waiting`,
  `dialectic-raise`, `dialectic-cosm-count` (and the four holograph screens
  under "Ascribe's module"). Scenarios `dialectic-answer-kinds` (every kind
  by keyboard alone; refusals with `aria-invalid`; nine recorded; settle by
  rules; the wire: `through: person`, no `who`, `route: local`) and
  `dialectic-holograph-no-cloud` (below). `_reset` in `interactions.py`
  closes the card.

---

## Ascribe's module (a person's holograph, 0.6)

Ascribe (`ascribe/1`, the second MiniCOSM) describes a self with no name: a
**holograph**, a folder with `holograph.cosm`. In the 0.6 round
[enough/ascribe.py](../enough/ascribe.py) grew from a reader into the
module. Spec: [docs/ASCRIBE.md](ASCRIBE.md) (4 the holograph, 8 the
dialectic applied, 9 reading a person's own texts, 10 checks, 11 the private
filter, 13 releases, 14 projections). Lane notes: `docs/fabula-landed-A1.md`,
`-TI.md` (rulings h). Toward 0.7 (cosmoes-site main, Ascribe 14.6 to
14.14): the allograph, the catalog's `subject`, and the Allograph Registry's
client (keys, statements, Connect's sign-in) are built; the registry itself
is Connect's (comprise-connect). Withdrawn by the text, and so not built: an
index of isographs, `verified` in an isograph, hosting a cryptograph, the
match-token list `ascribe-tokens/0`.

- **The holograph's checks** (`lint_holograph`): the generic ones, the
  dialectic's, and Ascribe's seven (`form-anchored`, never on D;
  `relation-declared`, `when-shape`, `strength-range`, `release-shape`,
  `no-pii` — a warning inside the holograph, an error at a projection —
  and `private-marker`, a note), each finding with its `advice`
  (`report_dict`). The cosm viewer, `cosm_lint` and `POST /api/cosm/lint`
  run them on a holograph.
- **The bank** (`raise_bank`): the 44 questions (`D:question/ascribe-a1` …)
  and the core's rule questions, every one `to: holder`; the queue puts the
  thinnest container first (`queue`). **Only the holder answers**: a
  session's `with` is always `{to: holder, who: the holder}` whatever a
  request says, and an answer that reads like personal data is refused
  ("this answer reads like personal data (…), which a holograph never holds:
  …"), nothing written, the question left open (`record_answers`).
- **Recording and settling** (`answer`, `settle_holograph`, `follow_ups`,
  form discovery): the holder's words recorded verbatim and folded into the
  nodes by Ascribe 8.3–8.5. Every write passes a check gate (no new error,
  no personal-data finding), else it is not made and a `why: counter`
  question is raised.
- **A reading's candidates** (`candidates`, `land_candidates`; the Thym move
  `propose`, which asks): proposals from a person's own text, each a
  candidate (`provenance: {mode: derived, state: pending}`) with its
  question, until the holder says yes.
- **The private filter** (`private_filter`, a pure function of the folder),
  before anything leaves — ingest, package, transfer, projection: everything
  beside a `.ascribe-private` marker, every `visibility: restricted` item,
  module D (except a transfer of the whole holograph into the holder's own
  keeping), what it cannot read (a link, a `.cosm` that does not parse) and,
  by the 0.6 rulings, **in every use** every candidate and every question
  about one, and the catalog's `releases:` (the holder's own account of what
  left).
- **Releases** (`releases`, `append_release`): every release is recorded in
  the catalog's `releases:`, appended and never rewritten, one isograph per
  epoch (any number of allographs). A writer records `isograph`,
  `allograph`, `cryptograph` or `isomorph`; a record `as: tokens`, made
  before match-token lists were withdrawn, still reads and lints clean, and
  `append_release` refuses a new one.
- **The isograph**: a local projection made by a Thym program, `project h
  as isograph` (`thym 1`; Ascribe's extension of Comprise's `project`), in
  which everything is `stated` and nothing `verified`. `POST
  /api/ascribe/isograph {path, program}` runs the holder's program by rules
  (a program that asks a model is refused: "no model reads a holograph for
  it"), appends the release (`as: isograph`, `trace: {run, sha256}`, `items`
  the ids that left) and writes `<holograph>.isograph-<epoch>.json` beside
  the holograph. The isograph names the run that made it (`run: <id>`, not
  a trace digest, which no run has until it lands); the release record
  carries the trace's digest.
- **The allograph** (Ascribe 14.6; `allograph_doc`, `project_allograph`,
  `allograph_problems`): `project h as allograph`, the same extension entry
  as the isograph's (`as: 'isograph | allograph'`, code
  `enough.thym.moves.ascribe:project`, which chooses by the call's `as`).
  Only E, S and U nodes, public, active, known at 0.5 or more, `valence`
  absent or `for`, anchored to FEED; one entry per kind and form (strongest
  band, latest decade); sorted E, S, U then form; no hid, no handle, no free
  text; `kind: person`, or `agent` when the catalog says `subject:
  character` (`subject_of`, `set_subject`; `catalog-key` refuses any other
  word). `POST /api/ascribe/allograph {path, program}` runs the holder's
  program by rules, appends the release (`as: allograph`) and writes
  `<holograph>.allograph-<run>.json` beside the holograph; it sends nothing.
  `holograph_state` is the digest of what the filter keeps (each `.cosm`
  file read as what it says), which a release, module D or a marker's files
  never move; the engine gives it beside the allograph, so the run records
  it with the engine's answer (`allograph_registry.run_state` reads it back).
- **The Allograph Registry, the holder's side**
  ([enough/allograph_registry.py](../enough/allograph_registry.py), routes in
  [enough/allograph_api.py](../enough/allograph_api.py)): one Ed25519 key per
  listing in the keychain (service `enough/allograph`, user the hid), its tag
  and proof strings, statements signed over canonical JSON, every operation
  of Ascribe 14.12, and Connect's device-flow sign-in with the token in the
  keychain (`enough/connect/<host>`, read once a process). Two seams:
  **`TRANSPORT`** (the one function that reaches the network) and
  **`KEYCHAIN`** (conftest puts a `MemoryKeychain` there for every test;
  `ENOUGH_KEYCHAIN=memory` does the same for a scratch server), and the
  address **`ENOUGH_CONNECT_URL`** (default https://compriseconnect.com; a dead
  loopback port in the suite and in `smoke_boot`). What this machine keeps of
  a listing (registry, tag, name, dangler, the listed run and the
  holograph's state it took) is `~/enough/config/allographs.json`, never the
  holograph. Routes: `/api/connect/status|sign-in|poll|sign-out`, `POST
  /api/ascribe/subject`, `/api/allograph/listing|list|withdraw|proof|prove|
  unprove|waiting|accept|remove|attest|bond|unbond|search|entry|faceplaces`;
  every one that sends answers 401 while not signed in to Connect.
- **The cryptograph and the isomorph** are engine functions of the module
  (`cryptograph`, `isomorph`), the holder's side only; no Thym move gives
  them in this edition. A writer makes no match-token list.

### The UI (index.html, U1b: a holograph)

User-facing: HELP_CENTER §13.8. A holograph opens the same `#dialectic-modal`
(see "The dialectic" → "The UI"), with:

- **`#dlg-rules`**: "for the holder alone", the personal-data rule (refused,
  nothing written; describe people by what they are to you, or by a
  pseudonym) and "nothing here goes to a cloud model", with the `holograph`
  bubble. The refusal is the server's words beside the field, as a check's
  (never a page error). S3 reworded `ascribe.REFUSED_PII` to "describe people
  by what they are to you (…), or by a pseudonym you declare" (the retired
  word "role" is out of user-facing text; `ascribe.ADVICE` keeps the
  specification's own wording, ASCRIBE §10.3, until the text changes).
- **No model anywhere.** No model line is drawn for a holograph; settle sends
  `{path}` only; no request names `who`, `route` or `model`. The
  `dialectic-holograph-no-cloud` scenario asserts it with the gate made to
  read open (through `/api/fabula/models`): a fabula's settle offers the cloud,
  a holograph's card never does, before, after a sitting and after settling;
  an email refused while typing and when sent, the other answer kept.
- **Candidates** (`dlgIsCandidate`: a `choice` of exactly yes/no/partly about
  an item): "a reading of your own text proposes this; it is not yours until
  you say so", its summary, yes / partly / no each with what it does, and
  (`dlgCandFromHTML`, from the card's `candidate`) "read from journal.md,
  line 3, 80 % sure" — never the words, which a holograph does not hold.
- **The isograph face**: `#cosm-iso-btn` "the isograph…" on a holograph in the
  viewer → `dlgIsoOpen` / `dlgIsoPaint` / `dlgIsoGo`: what an isograph is and
  what it leaves out, said before the button; the holder's programs (`GET
  /api/thym/programs`: in the project, compiling, one `volume` input, asking
  no model, else the sentence on what to write); "make the isograph" → `POST
  /api/ascribe/isograph`; after: "written: <file>", "the release was recorded
  in the holograph first: epoch, run, N items left", "open". Not made in a
  scenario (it records a release per epoch).
- **The viewer's report** shows each finding's `advice` on a line of its own
  (`cosmProblemHTML`; `cosmAdviceTrim` cuts the message's copy of it).
- **uicheck.** Seeds `self/` (sample-self, bank raised, two journal
  candidates landed, one affinity public), `self-pii/`, `open-self.thym`;
  screens `dialectic-holograph`, `dialectic-candidate`,
  `dialectic-isograph`, `dialectic-holograph-cosm`.

---

## The dictionary (FEED)

**FEED**, the **first-party enough english dictionary** (0.4.1): 116,911
headwords (209,829 words with their forms) as shipped in 0.6.0 —
pack 042 added the MacroCOSM/Comprise terms of art (atem, cosm, minicosm,
syuzhet …) and 19 OES senses of existing words, pack 044 the fabula
round's terms (fabulac, fabulan, fabulap, cshort, catem …), and pack 045
the five file-name words the 0.6.0 texts use (pyi, pyproject, toml, readme,
utf) with five inflections demoted to the forms they already were. The count
moves as the specifications' work needs words: the one in, one out rule of
2026-11-05 ran once, in pack 045, and was retired on 2026-11-06; there is no
cap and no growth pack on a schedule. `reflib/dict/manifest.json`'s `headwords` / `words` are the live
numbers, and a re-sync moves them — an original work, read-only to
the user and to the readvisors, with a second **user dictionary** beside it
that only the user's own words go into. Names are fixed: product name
lowercase in the UI ("feed", "first-party enough english dictionary"); code
prefix `dict` (module `enough/dictionary.py`, routes `/api/dict/*`, DOM ids
`dict-*`, mode-stack name `dict`, i18n keys `dict.*`); the lightbox is the
**word data lightbox**, ids `wdl-*`. User-facing doc: HELP_CENTER §14.

### Data flow

```
<lexicon checkout>/dictionary/          committed text form (JSON lines), private repo
   │  scripts/sync_dictionary.py        public-edition filter, line by line
   ▼
reflib/dict/                            shipped in the repo AND in the .app (build.rs)
   │  dictionary.ensure_built()         server lifespan, background thread
   ▼
$ENOUGH_DICT_ROOT/feed.sqlite           built, disposable   (default ~/enough/dict/)
$ENOUGH_DICT_ROOT/user-dictionary.sqlite  the user's words, precious
```

- **`scripts/sync_dictionary.py [--lexicon DIR] [--check]`** only ever
  *reads* the lexicon (default `../../enough-lexicon` from the repo root) and
  mirrors its layout into `reflib/dict/`: `schema.sql`, `meta.jsonl`,
  `labels.jsonl`, `frequency_bands.jsonl`, `words|forms|synonyms/<a-z>.jsonl`,
  plus its own `manifest.json`. The **public-edition filter**: in `words`,
  `notes` / `source` / `corrected_on` are nulled; rows whose `status` is
  neither null nor `live` are dropped with every `forms`/`synonyms` row
  naming them; `meta` keeps only `dictionary_version`, `languages`,
  `schema_version`, `title`. Key order is preserved and lines re-serialise
  exactly as the lexicon writes them, so a rerun over an unchanged lexicon
  is byte-stable; only files whose filtered content changed are rewritten;
  files with no source are removed. `manifest.json` is
  `{dictionary_version, schema_version, headwords, words, files: {relpath:
  sha256}, digest}` — `digest` is the sha256 of the sorted `relpath sha256`
  lines, **no timestamps**. Exit 0 synced / nothing to do, 1 `--check` found
  changes, 2 no lexicon. `NOTICE.md` is hand-written and never touched.
- **`reflib/dict/` is not under the Apache licence.** Its `NOTICE.md`: ©
  2026 Graham Smith, all rights reserved, bundled for use within enough
  only, licence to be decided. Never hand-edit anything in it (rerun the
  sync), never copy it elsewhere, and don't describe it as part of the
  open-source tree. It is the only part of `reflib/` that ships:
  `desktop/src-tauri/build.rs`'s `SNAPSHOT` names `reflib/dict` (~380 MB),
  not `reflib`.
- **The build** (`dictionary.build()`, via `ensure_built()`) runs when
  `feed.sqlite` is missing or its `meta.manifest_digest` differs from the
  manifest's `digest`. It executes `schema.sql`, bulk-inserts every JSONL
  file in 5 000-row batches (progress = bytes done / bytes total), adds one
  covering index the shipped schema doesn't have (`feed_sort`, over every
  column a sort, group or filter reads — `feed.sqlite` is disposable, so
  it may), stamps the digest and `user_version`, `ANALYZE`s, and
  `os.replace`s a `.feed-*.sqlite.tmp` built in the same dir — a reader
  never sees half a dictionary. Old temp files (> 1 h, so not a second
  project's live build) are swept. `cancel_build()` is the lifespan's
  shutdown hook. A missing source dir is `available: false`, never an
  exception at boot; a failed build reports through `status()["error"]`.
- **The user DB** is created lazily on the first write from the same
  `schema.sql` (FTS and triggers included), and is **never rebuilt or
  deleted by code**. Every write in the module goes there and nowhere else.

### Reading

Every read opens a fresh connection (tool runners and endpoints run on
worker threads): `feed.sqlite` with `mode=ro`, the user DB `ATTACH`ed as
`u` when it exists. `_merged()` is the one relation both halves are read
through — headwords from both, `word NOT IN (SELECT word FROM u.words)` on
the feed half, so **a word in both is the user's**, everywhere — and every
row carries `origin: "feed" | "user"` (`entry()` adds `overrides_feed`).

| Python | Route | Shape |
|---|---|---|
| `status()` | `GET /api/dict/status` | `{available, ready, building, progress, version, headwords, words, user_words, stale, error}` — cheap, polled by the UI while it builds |
| `lookup(word)` | `GET /api/dict/lookup?word=` | `{found, query, entry, matched_form, suggestions}`. `normalize()` lowercases, folds diacritics, strips surrounding punctuation and a possessive `'s`; a form resolves to its headword with `matched_form` set; a miss suggests by prefix, FTS on the word, shortened stems, then FTS on definitions |
| `lookup_many(words)` | — (0.4.3, Python only) | `{normalize(w)[0]: entry \| None}` on **one** connection — the per-call connect is the slow path; forms fold to their headword entry, user rows win, an unbuilt FEED gives every value `None` and never raises. The fabula engine's grounding (see "The fabula") |
| `entries(sort, then, dir, then_dir, offset, limit, letter, q, filters, grouped)` | `GET /api/dict/entries` | `{total, offset, rows, groups}`; rows are `SHORT_COLUMNS`, `limit` ≤ `MAX_LIMIT` (500); `groups` are the sections the page touches, each with its absolute offset |
| `index(sort, dir, filters, q, letter)` | `GET /api/dict/index` | the jump rail / thumb index: `[{key, label, count, offset}]`, offsets matching `entries()` for the same view whatever the sub-sort |
| `position(word, …view)` | `GET /api/dict/position` | where a word sits in one view, so a page can open at it; a miss in plain a–z still gets an `offset` plus `before`/`after` neighbours |
| `entry(word)` | `GET /api/dict/entry/{word}` | every column, JSON parsed, band and form-label meanings resolved, plus `syllables`, `era`, `overrides_feed`; 404 when absent |
| `facets()` | `GET /api/dict/facets` | sort keys, filter keys, domains / parts of speech / bands / origins with headword counts |
| `user_delete(word)` | `DELETE /api/dict/user/{word}` | the only write over HTTP (the WDL's delete); adding and changing go through the readvisor tools |

`dictionary_api.py` is HTTP translation only, the `composure_api.py` split:
`ValueError` → 400 (a bad sort, direction or filter, with the engine's
sentence), `DictionaryUnavailable` → 503 (not built yet; the UI reads
`/status`). Handlers are plain `def`, so FastAPI runs them on its thread
pool.

**Sort keys** (`SORT_KEYS`, each asc/desc, primary and sub-sort): `alpha`
(word), `length`, `domain`, `era`, `pos` (`pos_primary`), `frequency`
(band 0–8), `syllables`, `added` (`added_on`), `origin`. Ties always fall
back to `word`; NULLs sort last. Two of them have no column — **both DBs
keep the exact shipped schema** — so they are SQL functions registered on
every connection (`_register`): `era(first_use)` → `era_ord()`, a
chronological ordinal over every `first_use` phrasing the data uses (Old
English < late Old English < Middle English < late Middle English < 13th
century…; early/mid/late inside a century; a decade like "1990s" at its
middle; "by the 17th century" just after the bare one), and
`syllables(hyphenation)` → the count of `·` plus one. `era_group()` orders
whole groups. **`grouped=`** makes the sub-sort order the words *inside
each group* of the primary (a letter, a century) rather than only breaking
exact ties — the dictionary page always asks for it, since "alphabetical,
then length" is otherwise a no-op. `test_dictionary.py` sweeps every key ×
direction with a sub-sort and asserts every lexicon `first_use` string has
an ordinal.

**The order cache.** `_ordered()` sorts the whole headword list for one
view once — key `(sort, then, dirs, letter, q, filters, grouped, versions)`,
where `versions` is both files' `(mtime_ns, size, inode)` plus a write
generation — and keeps the six most recent views (`_ORDER_CACHE_SIZE`), so
paging and a deep jump are list slices. Every user write and every build
calls `_invalidate()`. A new code path that changes either DB must too.

**Filters** (`FILTER_KEYS`): `domain`, `pos`, `band`, `origin`;
comma-separated values in the query string.

### Writing (the user DB only)

`user_add(fields)` / `user_update(word, fields)` / `user_delete(word)`,
serialised by one lock. A word is lowercase a–z only (`WORD_RE`);
`definition`, `pos` and `pronunciation` are `REQUIRED`; JSON columns
accept lists (or one item per line); `frequency_rank` must be a band 0–8.
enough derives `letter`, `length`, `is_headword=1`, `pos_primary`, `ipa`
and stamps `source='user'`, `status='live'`, `added_on`/`updated_on`
(`DERIVED` — a caller's values for those are ignored). `user_add` refuses
a word FEED already has as a headword ("update it instead"); `user_update`
of a FEED word copies FEED's row into the user DB first, so the user's
version **overrides** it. Results are `{ok, word, missing, overrides_feed}`
— `missing` is the `REPORTED` columns still empty, which the readvisor is
told to mention once. Deleting an override brings FEED's entry back
(`restored_feed`).

### The readvisor's tools

[enough/dictionary_tools.py](../enough/dictionary_tools.py), registered at
`tools` import time like `pal_tools`:

- `dict_lookup <word>` — a compact, column-labelled entry (labels are the
  column names, so what the model reads is what it would write back), or
  "not in feed" with near words.
- `dict_add_entry` / `dict_update_entry` — one inner tag per column (they
  land in `ToolCall.extra`); list columns one item per line, word lists also
  one comma-separated line; `forms` lines parse as `word /ipa/ label, label`;
  an empty tag clears a column. Success fires the **`dict_changed`** side
  effect `{word, action}` — the frontend's `dictOnChanged()` drops every
  cache and redraws an open page or lightbox (the WDL's own delete calls
  it directly).
- `dict_guide` — no tags; hands back the shipped `lexicographer` SKILL.md
  minus frontmatter and tooltip line, **always from the install's own
  `defaults/`**, never a project copy (a project-local `lexicographer`
  folder would be an unaudited skill).

**No broker toggle.** The other gates guard something leaving the machine
or text entering the prompt; a word in the user's own dictionary is
neither, and it can be deleted from the lightbox. What is gated is the
*documentation*: `prompt.DICTIONARY_TOOL_INSTRUCTIONS` (~580 chars) rides in
every turn **whenever FEED ships** (`dictionary.available()`: a manifest and
a schema in the source dir, built or not — the tools say "still being
prepared" themselves), and is deliberately short; the column-by-column
guide is the **`lexicographer`** skill (off by default like every shipped
skill), which carries it in the Skills section when on, and is one
`dict_guide` call away when off. Every tool answer for an unavailable,
unbuilt or failed dictionary is a sentence for the model, never a raise.

### The frontend

All in index.html under the "FEED — dictionary mode, the word data
lightbox (WDL) and the "dictionary entry" context menu" banner.

- **Dictionary mode** (`#dict-mode`, mode-stack name `dict`, state in
  `DICT`). Launched by `enterDictMode({word?})` from `#ui-dict-btn`, beside
  Help in the UI modal's header (project mode only — a home server has no
  `/api/dict` routes). Pages are **measured, not scrolled**: `dictShow(start)`
  renders a run of entries from an offset into a `column-fill: auto` flow,
  counts what landed inside the frame and trims the rest; next = start +
  fit, previous retraces history or searches for the fullest page ending
  before `start`. So re-paginating on any resize, font, text-scale or panel
  change is just `dictShow(DICT.start)` (a `ResizeObserver` on
  `#dict-frame`). Rows come from `/api/dict/entries` in 100-row chunks, at
  most 40 chunks per view and 4 views. Group headings and the fore-edge
  thumb index (`dictEdge`, tabs sized by `--n` = the group's count) come
  from `/api/dict/index`. Order, filters and the first word on the page
  persist per viewer in `localStorage['enough.dict.v1']`. One column (B's
  specimen layout) whenever the frame is narrow. Text scale is applied as
  `font-size: calc(px * var(--txz))` rather than the `zoom` the other
  document surfaces use, because pagination measures rects against the
  frame and a second zoom layer would put them in different px.
- **Part-of-speech marks**: `.dpos-n|v|a|d|o` set `--pc`/`--ink` from the
  accent colours; `.dict-sh` draws the shape (square, triangle, diamond,
  dot, hollow ring) so colour is never the only signal; `dictSpineHTML`
  stacks one spine segment per part of speech.
- **The WDL** (`#wdl-modal`, `WDL`, `wdlOpen(word, {fromDict})`,
  `wdlRender()`). A `*-modal`, so it gets dialog semantics from the shared
  helper for free (see "Change the UI"). `WDL.stack` is the walk (≤ 60,
  the last six shown as the "your walk" trail); `wdlNav` pushes, `wdlBack`
  pops. Prev/next walk the dictionary's current view when it is open (or
  the plate came from it), else a–z, via `/api/dict/position` + a 3-row
  `/entries`. Any word of the running text is a link through
  `dictWordAtPoint`. A 200-entry lookup cache, cleared by `dictOnChanged`.
- **The context menu** (`#dict-ctx-menu`, `dictCtxOpen`). The rule: a
  right-click **on a word** — `dictCtxWhere()` names the surfaces: read
  face, preview, both edit textareas, `#conversation`, `#wiki-body`,
  `#docs-body` (0.4.4), `#help-body`, `#cosm-body` and the EMF
  face's cards (0.4.3), the dictionary, the WDL — opens "dictionary
  entry" + "copy" (and, since 0.4.3, **atem of selection** when a selection
  is under it — see "The fabula"); **anywhere else** (no word under the pointer, a link, an
  image, a control, a find bar) the system menu is untouched; **⇧-right-click
  is always the system menu**. The textarea's word comes from a transparent
  mirror laid over it for one synchronous hit test (`dictWordInTextarea`),
  so it follows the wrapping the user sees. Composure keeps its own module
  menu, which gains the same item (`compOpenCtxMenu(id, ev, dictHit)`).
  `dictEntryFor(word, where)` is the one dispatcher: WDL over the current
  mode, a page turn inside dictionary mode, a walk inside the WDL.
  **⌘⇧D / ctrl+⇧D** (`dictWordAtCaret`) goes to the same places for the
  selection or the word at the caret. The menu is in `MODAL.KEEP_LIVE` so
  it still works over an open WDL.
- **⌘F in dictionary mode** means "search the dictionary": `FIND_BARS.dict`
  is a duck-typed controller whose `open()` focuses `#dict-q` and whose
  `onEsc()` peels the menu, the options row and the search before the esc
  ladder closes the mode.

### Seams and tests

`ENOUGH_DICT_ROOT` (state root) and `ENOUGH_DICT_SOURCE` (source dir) are
both in `tests/conftest.py`'s `_STATE_SEAMS`, and the source seam points at
**nothing** (`no-dict-source`): otherwise every app a test boots would start
a 380 MB background build. Dictionary tests write a few-dozen-row fixture
lexicon, run it through the real `scripts/sync_dictionary.py` into a temp
`reflib/dict`, and point `ENOUGH_DICT_SOURCE` at that
(`tests/test_dictionary.py`'s `lexicon` / `source` / `built` fixtures;
`test_dictionary_tools.py` imports the same fixtures). The shipped copy is exercised
only by the opt-in `test_real_dictionary_build_and_timings`
(`ENOUGH_FEED_REAL=1`). `test_prompt_weight.py` fakes availability with a
one-line manifest and an empty schema. `scripts/smoke_boot.build_env()`
redirects `ENOUGH_DICT_ROOT` into the scratch dir and **pops**
`ENOUGH_DICT_SOURCE`, so the boot smoke builds the real `reflib/dict` and
asserts `/api/dict/status` is building or built. The uicheck registry has
`dict-mode`, `dict-sorted-filters`, `dict-search` and `wdl-plate` screens.

### Releasing a new dictionary

`desktop/RELEASE.md` owns the steps; don't duplicate them, follow them.
In short: **sync before the bump** (`uv run python
scripts/sync_dictionary.py`, then commit `reflib/dict` with the version
bump — every install rebuilds its `feed.sqlite` when the manifest digest
moves); everything after that is the ordinary release, including the DMG
layout check (`scripts/check_dmg_layout.py`, below).

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

`canon:` paths are refused (400) by every convert route (and
by both paginate routes): v1 is scoped to the project tree, and the store's
write-guards have no opinion about twins. (Canon's *listings* still read a
convert twin's state for a volume catalog's `twin:` entry, through
`convert.state()`, which may self-heal a manifest's cached stat as the
project tree already does.)

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
                  "/api/macrocosm-spec", "/api/convert/formats", "/api/shutdown",
                  # DocOES (0.4.4): read-only, from the install's own documents
                  "/api/docs", "/api/docs/status", "/api/docs/build", "/api/docs/lens",
                  "/api/docs/compile", "/api/docs/inventory",
                  "/api/cosm/inline", "/api/cosm/inline/lens"}
HOME_PREFIXES  = ("/api/home/", "/static/")
```

Two of those look surprising and both earn their place: the **formats
table** is a static registry the help center's `{{convert-formats}}` token
expands (and the help center works in home mode), and **`/api/shutdown`** is
how the shell quits a backend — a home backend is still a backend.
`/api/macrocosm-spec` (0.4.3) and the DocOES routes (0.4.4) are there because
the docs viewer is project-independent, like the help center before it — the
two inline routes too, because its live examples must load from home; Canon's `/api/canon/*` and the
`/api/cosm*` routes are project routes and
404 on a home server. Anything
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

`home.build_project_mirror()` calls `canon.folder_flowchart(base,
root_label, *, start, meta_lines, skip, max_depth)` — the node/edge/depth-cap
walker that was extracted out of `_mirror_body` for this. Frontmatter is
`merirmaid: 1` / `modality: mirror`, and **`modality: mirror` is what makes
the viewer read-only** (`mmRenderDiagram`'s `editable` flag is already
`modality === 'wip' && …`), so nothing had to be hidden. The `skip`
predicate is the *tree's* rule set (`home._mirror_skip`, which since 0.4.3
also hides fabula twins and paginated `X.pdf.pages/` folders, and is what the
project catalog `rness/canon.cosm` enumerates), so the map shows what the
sidebar would — it is not drawn from the catalog's lens yet (a recorded
follow-up);
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
llama-server, or `cloud.chat_completion()` when `opro-api` is active —
through `llm.complete(…, cloud_gate=False)` since 0.4.3 (the audit never
asked the cloud gate, and still doesn't; its cloud timeout became the
shared 600 s). No history, no generation lock, worker thread; the user
keeps chatting. The
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
  **manual**, where the docs viewer's short density expands it to a markdown
  pipe table before rendering (one row-builder, two renderings — see
  `convertFormatsHelpRows()` / `…Html()` / `…Markdown()`). Bubbles are governed by
  one per-project boolean (`GET`/`POST /api/help/bubbles`, stored in the
  multipurpose `rness/active-paradigm` file, default on, surfaced as the
  "help (?) bubbles" checkbox in the UI modal): on = every `[data-help]`
  row shows its `(?)` persistently (re-applied after `htmx:afterSettle`),
  off = none. There are no hover timers and no first-launch highlight
  machinery — that design was superseded. 0.4.3 renamed `## cacheawl` to
  `## canon` (now reachable from the store pane's `(?)`, so it left
  `UNREACHED_SECTIONS`) and added `cosm-viewer`, `cosmspec`, `canon-chip`
  and `atem-card`, each in all six files; 0.4.4 added `agentmode` (on the
  slider's wrapper, in the UI and model windows — `HELP_ANCHORS` gained
  `#ui-modal [data-help], #model-modal [data-help]`, and `openUIModal()` /
  `openModelModal()` call `applyHelpBubbles()`, since home never runs
  `loadHelpBubbles`) and `docs` (the docs viewer's `(?)`), and merged
  `cosmspec` into `docs`; 0.5.0 added `thym` (the run card's and a program
  card's `(?)`), `package` (a package's card) and `reading` (the reading
  band), each ending in an idea that names its Help Center section (13.4,
  12.6), so their cards' `see` point at the manual. DocOES also enumerates every bubble as a
  `B:bubble/<id>` item of the help volume (the fabula's cards); a bubble about
  another document is mapped in `docoes.BUBBLE_DOCUMENT` (`{"docs":
  "macrocosm-oes"}`), so its "section N" names that document's sections
  (cross-volume `xrefs`) instead of the manual's — keep every other bubble's
  section numbers the manual's. A `(?)` inside a full-frame mode
  works because `openHelp` lifts `#help-viewer` above the mode stack
  (`z = 32 + stack depth`), and above an open dialog (z 1001, leaving the
  mini reader open) so the atem card's `(?)` works too.
- **The manual.** `docs/HELP_CENTER.md` is the complete end-user manual
  (voice-matched to the project; edit it like documentation, verify
  claims against the code first). Since 0.4.4 it is read in-app as a
  **DocOES volume** in the docs viewer (below), one telling per language,
  launched from `#ui-help-center-btn` (`openHelpCenter()`) — a small **help**
  button inline in the UI modal's header row, beside the × (it kept its
  `.help-center-launch` class and its `hxc` icon); `#ui-dict-btn` and
  `#ui-specs-btn` ("MacroCOSM ▾") sit beside it — since 0.5.0 (lane X2) a
  small menu (`#ui-specs-menu[role=menu]`, `uiSpecsMenu(open)`; focus on
  the first item, ↑/↓/Home/End, Esc closes the menu before the window) of
  the four specifications in the same viewer: `#ui-cosmspec-btn`
  (MacroCOSM OES), `#ui-thym-btn` (Thym), `#ui-ascribe-btn` (Ascribe) and,
  since 0.5.4, `#ui-comprise-btn` (Comprise OES). Two more inline buttons
  wrapped the header row in de, fr, es and ja. `GET /api/help-center?lang=` still serves the raw markdown with the
  language whitelist — **kept** in 0.4.4 though the frontend no longer calls
  it: it is the manual's plain-text route, as `/api/macrocosm-spec` is the
  spec's, and the cheapest way for a tool or a person to read the source.
  **So the manual's numbering is UI**: section ids, "section 7.3" links and
  DocOES's item ids come from it, identical in all six languages;
  `test_content_integrity.py` keeps it contiguous and every cross-reference
  resolvable, `i18n_check.py` keeps the six heading structures equal, and
  renumbering English is a translation job too (0.4.4 renumbered §13.2 →
  §13.3 and added §10.7, §13.2, §16.5 in all six; 0.5.0 added §12.6 and §13.4
  in all six, with the same defined terms in the same places, so no telling
  falls back to English for them; the 0.6 round added §12.7, §12.8, §13.5 to
  §13.8 and §16.6, retitled §12.4, and defines the terms fabulac, cshort,
  catem, MiniCOSM and holograph).
- **The docs viewer (0.4.4)** — mode `docs`, root `#docs-mode` (carries
  `data-doc` and `data-density`), one viewer for five documents:
  `help-center` (icon `hxc`, the UI language's telling, badge "written by
  Rosa" from the catalog's `telling.voice`) and four specifications,
  `macrocosm-oes` (icon `macrocosm`), `thym` (icon `cosm`), `ascribe`
  (icon `readvisor-rename`; both 0.5.0, lane X2, the closest existing
  glyphs) and `comprise-oes` (icon `cosm`, 0.5.4). A spec is
  `DOCS_DOCS[doc].kind === 'spec'` (`docsIsSpec(doc)`):
  English only, so a translated UI gets `requested_lang` and the note
  `docs.note.specEnglish`; the toolbar says `docs.title.spec`; the badge is
  `<title> · edition <document.version>` (`docs.badge.edition`: "Thym ·
  edition 0.6.0" — names carry no number, the edition is a field, no "v")
  with a title saying where the text came from (`docs.badge.fromCosmoes` /
  `docs.badge.bundled`, from the head's `document.source` and `.revised`);
  the mode stack's icon title is the entry's
  `stack()` (`modes.docs.{spec,thym,ascribe,comprise}.icon`), its exit
  `modes.docs.spec.exit`. `COSM_SPEC_SECTION` and "about this format" stay
  on macrocosm-oes. Functions
  (window): `enterDocsMode({doc, lang, density, anchor})` (no `density` →
  the remembered one, `localStorage['enough.docs.density.<doc>']`, default
  `short`), `exitDocsMode()`, `openHelpCenter()`, `docsSetDensity(d,
  {anchor})` (keeps the place across densities), `docsToggleSize()`,
  `docsTocToggle()`, `docsBackGo()` (async; the back pill crosses densities:
  `docsBackMark`/`docsBackShow`), `docsFindOpen()`, `docsOpenItem(key)`,
  `docsTermOpen(key, el)` (= `docsTermCard`: a term link opens the term's
  card), `docsWarm()` (`POST /api/docs/build {}` once per page, from
  `openUIModal()`), `docsOnLanguage()` (from `setUILanguage`: re-tells the
  help center in place), `docsShowItemFromLens(key)`. State: `DOCS` (doc,
  lang, density, data, ix, cache, seq, at, back), `DOCS_DOCS` (per
  document), `DOCS_CTX` (the reader context), `DOCS_FIND`
  (`FIND_BARS.docs`), `DOCS_XREF_RE` + `DOCS_XREF_RULES` (six languages'
  "section N", lists and ranges, `§N`, `README §N`, `P.N`, resolved per
  scope: in the spec § and P.N are Comprise's chapter, README § its paradigm
  map). Loading: `docsLoad` → `GET /api/docs?doc=&lang=&density=` (202 →
  `docsBusy(progress.current)` and a 300 ms retry; 503 → `.ref-error`); one
  payload cache per open. Anchors anywhere: an item key (`S:section/18.4`,
  `T:term/atem`), a section number (`18.4`, `P.3`, `§2`) or a heading id
  (`docs-sec-18-4`; 0.4.3's `cs-sec-…` and 0.4.1's `ref-sec-…` still land).
  **`DOCS_DENSITIES`** maps a density to its renderer `async (data, at)`;
  a radio with no renderer is disabled. The density control
  `#docs-density[role=radiogroup]` holds three `button[role=radio]` (roving
  tabindex; arrows/Home/End move and choose):
  - `short` — every section's `heading + body` → `docsStripComments` (drops
    the whole-line `<!-- atem/term -->` markers outside fences) →
    `cosmSpecUnwrap` (the spec only: it is hard-wrapped at 120 columns) →
    `{{convert-formats}}` expanded → `renderMarkdown` → `<section
    class="docs-sec" data-key>`, ids `docs-<anchor>` (a chapter's
    `docs-<prefix>-<anchor>`); contents from `[data-toc]` headings
    (`docsBuildToc`); `refLinkSections(DOCS_CTX)` with `docsXrefResolve`;
    `docsLinkTerms` (each term's first use per section as
    `a.docs-term[data-term]`, never in its defining section; the help center
    links only distinctive words, and a bold use only when its case matches);
    margin marks `button.docs-mark[data-key]` (`◂ N` = `mentioned_in`, `❏ N`
    = examples; placeholders) flip to the section's card; `.docs-fb` "told in
    English" on a fallback section, `docs.note.fallback` counts them.
  - `atem` — `.docs-atem`: the outline (`a.docs-ol-row[data-go]`), the
    glossary (`dl.docs-gloss`), and, for the spec, the reference per
    MiniCOSM and the checks; find here searches names and atems only.
  - `fabula` (U2) — the cosm viewer's content component drawn for the
    **`DOCS_FAB` host** (`body` `#docs-body`, `rail` `#docs-toc`, `railBtn`
    `#docs-toc-btn`, `card` = `docsPrismHTML`, `viewer: false`); the root
    gains `.docs-fab`, and the cosm viewer's card/rail rules are written
    `:is(#cosm-mode, .emf-face, .docs-fab)`. The whole volume loads once and
    pages client-side (`docsFabPrepare`: section pages = a top-level section
    with its subtree and the examples/decisions in it; `DOCS_FAB.pages`,
    `pageOf`); facets by kind and by MiniCOSM (`.docs-chip[data-facet]`);
    the pager `nav.docs-fab-pager`. The **prism card** (`docsPrismHTML`
    around `cosmCardBaseHTML`; `DOCS_PRISM_SCHEMA` / `DOCS_PRISM_NOISE` sort
    the fields): atem first, the breadcrumb (`nav.docs-crumb`, each step →
    that section at short), then `dl.docs-facets` — identity (address, "cite
    it as", "edit at <file> §N" / "declared by <manifest>#<path>" / the
    chapter note), schema, checks, renderings (from the payload's
    `declared_lenses`: each lens's `include`; drawable ones draw around the
    item), examples, mentioned in (`backrefs` minus containment — equal to
    the short's margin mark) — and **graph around this** (`docsFabLens` →
    `enterMerirmaidLens('docs:<doc>.<lang>', lens, {around, depth: 1,
    label})` → `mmFetchLens(entry)` → `GET /api/docs/lens`; a node's "show
    item" → `docsShowItemFromLens`). **Live examples**: an `S:example` card
    posts its `body` to `/api/cosm/inline` (`docsLiveLoad`, the handle
    `inline:<doc>/<key>` in `COSM_INLINE`), shows the verdict, a lens picker
    and "open in the cosm viewer". Find at the fabula searches the cards
    drawn. Bubbles are cards (`docsBubbleHTML`, simple tags only).
  The 0.4.1 reader machinery (`refJump`, `refScrollTo`, `refTocApply/
  Toggle/IsSheet/Sync`, `refBackOffer/Hide/Go`, `refWireReader`,
  `refLinkSections`) now has one context, `DOCS_CTX`. **Gone in 0.4.4**:
  `#ref-mode`, `REF_CTX`, `REF_XREF_RE`, `enterRefMode`, `exitRefMode`,
  `refToggleSize`, `slugifyHeadings`, `refAfterRender`, `refBuildToc`;
  `#cosmspec-mode`, `CS_CTX`, `enterCosmSpecMode`, `exitCosmSpecMode`,
  `cosmSpecBadge`; U1's term popover `#docs-pop` (U2: a term link opens a
  card). Kept keys: `ref.toc.*`, `ref.find.label`, `ref.size.*`,
  `ref.back.*`; `cosmSpecUnwrap` moved into the docs block.
  **uicheck** screens `docs-help`, `docs-help-mini`, `docs-help-fr`,
  `docs-atem`, `docs-short`, `docs-spec`, `docs-spec-mini`, `docs-fabula`,
  `docs-fabula-mini`, `docs-card-term`, `docs-card-example-live`,
  `docs-graph`, `docs-thym`, `docs-ascribe`, `modal-ui-specs` (the ui
  window's MacroCOSM menu open), `home-docs-spec`,
  `home-docs-thym` (through the home ui window's menu item),
  `home-docs-help`, `home-docs-fabula` (the home screens fail when a route
  is not home-accessible), and `readvisor-and-minis` docks the viewer;
  scenarios `docs-find-contents` (the ref-mode gate), `docs-contents`,
  `docs-specs` (0.5.0, X2: the specs menu, and the specs' shared
  chrome, links and densities; screens `docs-thym`, `docs-ascribe`, `docs-comprise`), `docs-term-roundtrip`,
  `docs-example-live`, `docs-graph-roundtrip`; the four mode-stack
  scenarios use the docs viewer as their second mode.
  **Programs (0.5.0, U1)**: `DOCS_DOCS.program` reads any `.thym` file at
  three densities (`enterProgramDoc(path, {density, anchor})`, `DOCS_PROG`,
  `DOCS_PROGRAM_DENSITIES`; data from `GET /api/thym/program`, falling back to
  `/api/file/raw` + `<stem>.thym.cosm`); see "Thym" → "The UI".
- **Inline code in `renderMarkdown` (a 0.4.3 fix).** Before 0.4.3 the
  shared renderer double-escaped `<` and `&` inside backticks (every caller
  hands `renderInline` already-escaped text, which was then escaped again),
  so the Help Center showed `` `<volume>` `` as `&lt;volume&gt;`. Now only the
  two tags `escapeMarkdownInline` lets through, `<u>` and `<br>`, are
  re-escaped inside a code span. The code-span placeholders in `renderInline`
  are `\x00CS<n>\x00` — **real NUL bytes in index.html's source**, not the
  four-character escape (the `<u>`/`<br>` placeholders above them are
  written as `'\x00…'` escapes). A tool that strips or chokes on NULs will
  corrupt that line: edit around it, and check with `cat -v` that the two
  `^@` pairs survive.
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
  `:is(#review-mode, #docs-mode, #cosm-mode) .review-body`,
  `.emf-face .review-body`, `#edit-mode .edit-textarea`, `#wiki-body`,
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
  and serves translated manuals via `GET /api/help-center?lang=`; since
  0.4.4 the docs viewer reads them as DocOES tellings
  (`GET /api/docs?doc=help-center&lang=`), all six sharing one id set.
- `ui_language` is a top-level ui.json key (POST /api/ui-config,
  validated like `home_view`).
- **Every English string change must keep the catalogs in lockstep:**
  `uv run python scripts/i18n_check.py` prints the exact per-language
  to-do list, and `tests/test_i18n.py` fails CI until it's empty.
- The catalogs hold **1 161 keys** as of 0.4.3 (978 at 0.4.2; 1 150 before
  the 16 GB context fix added the eleven `chat.ctx.*` notice strings; the Canon
  round's rename moved `ca.*` → `cn.*`, `menu.ca.*` → `menu.cn.*`,
  `modes.cacheawl.*` → `modes.canon.*`, `topbar.cacheawl.*` →
  `topbar.canon.*`, `wiki.saveCacheawl.*` → `wiki.saveCanon.*`, and added
  the `cn.*`, `cosm.*`, `cs.*`, `canon.*`, `atem.*` and `emf.*` families).
  Brand words stay as they are in every language — canon (ja keeps it
  lowercase), cosm, MacroCOSM, EMF, atem, FEED — and
  `tests/test_content_integrity.py`'s `SAME_IN_EVERY_LANGUAGE` lists the
  ones a translation may leave byte-equal; "volume" is de *Band*, fr
  *volume*, es *volumen*, ja 巻, zh 卷. "Context window" is de
  *Kontextfenster* (kept apart from *Modell-Fenster*, the UI window), fr
  *fenêtre de contexte*, es *ventana de contexto*, ja コンテキストウィンドウ,
  zh 上下文窗口; the model window keeps each manual's §16 heading.

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
2. Optionally add it to the "Routing to other paradigms" list in
   [defaults/paradigms/text-planning.md](../defaults/paradigms/text-planning.md)
   — the home paradigm is the router that tells the readvisor when to
   switch — and have the new paradigm switch back by writing
   `text-planning` to `rness/active-paradigm` when its work is done.
3. Document the activation rule in the paradigm itself — when to switch
   in, when to switch out, what skill (if any) it pairs with.
4. No code changes; paradigm catalog is read from `rness/paradigms/`
   directly.

**The home paradigm** is `prompt.HOME_PARADIGM = "text-planning"` (0.4.1).
Until then it was `default`, which text-planning absorbed (routing, output
conventions, colour references, archival policy, security posture,
web-fetch rules); its skill-gated activation rule and its "switch to
default to draft" lines went. Every fallback lands on the constant:
`seed_multipurpose_file()` for a new project, `_render_multipurpose()`,
`set_help_bubbles()`, and `get_active_paradigm()` when the file is missing
or names a paradigm that isn't on disk — then the first paradigm that *is*,
so the prompt never silently loses its Paradigm section.
`ensure_multipurpose_file()` (every launch) migrates a stored `default`, in
the markdown or the legacy bare form, to the home paradigm, keeping the
help-bubble state — **unless** `rness/paradigms/default.md` is a real file
(`_kept_retired_paradigm`: a customised copy is the user's, and `default`
keeps working for them). The populator prunes the dangling `default.md`
symlink in the same launch; `tests/test_help_highlights.py` covers both
orders. Changing the home paradigm again means the constant **and** a
migration of the same shape.

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

### Add a council output kind

`output.kind` ∈ `answer | document | composure`, and all three land — but
`OUTPUT_KINDS_LANDED` stays, because the next kind should arrive the way
`composure` did: **validated at setup from the first release, refused with a
sentence at conclude until it is built.** Adding a kind:

1. Add the name to `council.OUTPUT_KINDS` and accept it in
   `council.validate_output()`, with whatever companion key it needs (`path`
   for `document`, `form` for `composure`) and a refusal sentence for the
   missing case. Unknown keys are dropped on purpose — validate it or it
   will not survive a round trip.
2. **Leave it out of `OUTPUT_KINDS_LANDED` until step 3 works.** That is the
   501: `api_council_conclude` refuses *before* the turn runs, so nothing is
   spent and the council stays runnable. Spending a completion and then
   failing is the one outcome to avoid.
3. Handle it in `POST /api/council/conclude` after the chief's conclusion
   statement is committed, alongside the `document` and `composure`
   branches. For a *file* output: **write through `tools.run_write_file`**,
   not `Path.write_text` — that is what keeps the allowlists, the
   `rness/requests/done/` prefix rule, the Canon catalog guard, the
   `.comp`/`.girraph` refusals, the undo stash and the convert-twin sync
   applying to a council's output. For a *composure* output the door is
   `comp_core.save` at `rev 1` on a document `from_outline` already built and
   validated in memory — see "The three output kinds".
4. If the kind needs the model to emit a shape, add it to
   `_CONCLUSION_SHAPE` and give it a retry constant, a "did not parse"
   predicate and **a fallback to `answer`** that commits the prose rather
   than losing the council's decision. Use `_stream_one(append=…)` for the
   retry; do not grow `take_turn` another mode.
5. Add a `doc` link-in module (`Council.link_doc`) under the conclusion so
   the artifact is one click from the council that produced it.
6. `tests/test_council.py` for the validation, `tests/test_council_api.py`
   for the conclude path, `tests/test_council_output.py` for the shape,
   the retry and the fallback.

### Add a tool runner

1. Define `run_<tool>(project_dir: Path, call: ToolCall) -> ToolResult`
   in [tools.py](../enough/tools.py).
2. Register in `_DISPATCH` (~line 1680 in tools.py) and `_TRACE_TOGGLE`
   (~line 1709). Both grep cleanly by name if line numbers drift again. A
   whole *family* of tools goes in its own module with a `register()` that
   `setdefault`s into both, called at the bottom of tools.py — the seven
   existing ones are `composure_tools`, `readvisor_tools`, `pal_tools`,
   `dictionary_tools`, `canon_tools`, `thym_tools` (0.5.0), `intro`.
3. If `ToolResult.render()` needs a specific attribute (e.g. `output=`
   for `cloud_pipeline`), add a branch in `render()`.
4. Add an XML example block + prose to `TOOL_INSTRUCTIONS` in
   [prompt.py](../enough/prompt.py) — **or to a gated block**, if the tool
   is not always available. `tests/test_prompt_weight.py` fails until it is
   documented somewhere in `fully_enabled(project) +
   tool_instructions(pal=True)`, and it fails again if the always-on core
   grew past `CORE_BUDGET`, the full prompt past `FULL_BUDGET` or the lean
   prompt past `LEAN_BUDGET`. Raising a number is a decision, not a fix.
5. If the tool needs a broker toggle (kill switch), add to
   `broker.TOGGLES` — UI updates itself. If it is gated by something that
   already exists (`ask_pal` is gated by the cloud gate and by the pal
   turn), do not add a second switch for the two answers to disagree over.

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
   `{{convert-formats}}` help token (help-docs.md + HELP_CENTER.md §7.2),
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
~42,800-line file with inline CSS and JS. Conventions:

- All modals follow the same `#<name>-modal` pattern with `.hidden`
  class and a `.modal-backdrop` for click-outside dismissal. **Since 0.4.1
  the id suffix is also the accessibility contract.** The shared helper
  (the "Modal a11y" section: `MODAL`, `modalSync()`, `modalStackTop()`)
  *watches* every `[id$="-modal"]`, `#confirm-overlay` and `#cn-prompt`
  with MutationObservers rather than rewriting anyone's open/close, and on
  open gives the panel `role=dialog` + `aria-modal` + an accessible name
  (its first heading or `[class*=title]`, via `aria-labelledby`), makes
  everything outside the top-most dialog `inert` (descending only into
  ancestors of what it keeps), remembers the opener and moves focus in —
  `[data-autofocus]`, else the first control in `.modal-body`, **never** a
  `.modal-head` button, so a reflexive Return can't "close project" —
  wraps Tab at both ends, and on close restores focus to the opener (or
  to the dialog underneath: the confirm overlay opens on top of other
  modals, so it's a stack). A new `*-modal` gets all of that for free if
  it provides: open/close by toggling `.hidden` (or `hidden`); a panel
  (`.modal-panel` or an element with `role="dialog"`) holding a heading;
  **its own Esc handler** (the helper leaves Esc alone, and a modal with
  none makes Esc do nothing at all); optionally `data-autofocus`. Not
  dialogs, on purpose: the popovers beside text (`#review-hl-popup`,
  `#fn-popup`, `#wiki-sel-popup`), context menus, `#help-viewer`,
  `#home-wait`. `MODAL.KEEP_LIVE` names what is never made inert (the help
  panel, the convert toasts, `#home-wait`, `#dict-ctx-menu`). Global key
  handlers check `modalStackTop()` to stay out of a dialog's way.
- **`findBarAttach(bar, opts)`** (0.4.1) binds the generic `.find-bar`
  markup (`.find-q`, `.find-count`, `.find-prev`, `.find-next`,
  `.find-close`) to any read-only document. `opts`: `root()` (searched),
  `scroller()`, `zoom()` (`UIZ() * TXZ()` on a `--txz` surface),
  `host()`, `available()`, `onLeave(top)`, `onEsc()`. Register the
  controller as `FIND_BARS[<mode-stack name>]` and ⌘F / ctrl+F (while that
  mode is on top) and the esc ladder pick it up. Matches paint through the
  CSS Custom Highlight API (`enough-find`, `enough-find-current`) where the
  engine has it — nothing in the document changes — else as
  `<mark class="find-hit">`, unwrapped on every rerun and close; at most
  `FIND_MAX` (2 000). Users today: the help center (`REF_FIND`), the spec
  viewer (`CS_FIND`), the cosm viewer (`COSM_FIND`, which searches the cards
  drawn so far — 40 per kind until "show all"), and dictionary mode's
  duck-typed controller, which turns ⌘F into "search the dictionary".
- **The top bar's fit** (`topbarFit()`, 0.4.1). The buttons and the mode
  squares never give way; `#project-name` ellipsizes down to about ten
  characters (fewer if the name is shorter); only then do the ¶ / W / C
  readouts drop, right to left (`.topbar[data-dc-drop="0".."3"]`). Flex
  cannot say "shrink this first, then hide that", so it measures — all in
  one space (`scrollWidth` / `clientWidth`), so `--uiz` needs no
  conversion — after every change that can move the balance
  (`topbarFitSoon()`: the counters' update, a `ResizeObserver` on
  `.topbar`). A new top-bar item belongs either in the never-give-way set
  or on that ladder.
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

- **The SVG icon pipeline.** The custom icons (66 in 0.4.3; `cosm`,
  `macrocosm` and `atem` are the newest, placeholders in the hand-drawn
  #000 line style the owner overwrites later) are built by
  [scripts/build_icons.py](../scripts/build_icons.py) (reading
  `scripts/icons-bbox.json`; strips hidden Illustrator layers, squares the
  viewBox at 82% fill) into `enough/static/icons/build/` — two variants per
  icon: `<name>.svg` (black line-work, light themes) and `<name>-dark.svg`
  (white, dark themes; produced by a black↔white swap incl. gradient stops).
  Don't hand-edit `build/`; edit the source SVG + rerun the script. In the
  DOM, every icon is `<img class="svg-icon" data-icon="<name>">`; `iconSrc()`
  resolves the variant, `setIcon(el, name)` swaps a toggle icon, and
  `refreshThemeIcons()` re-derives all variants on a live theme change (no
  reload). Reuse those helpers — don't write `<img src>` by hand. Since
  0.5.1 `iconSrc()` goes through `staticUrl(path)`, which stamps the URL
  with the server's version (`BOOT_UI_STATE.version`; bare when served
  statically), and `/static` answers `Cache-Control: no-cache`
  (`server._RevalidatingStatic`). Both because the 0.5.0 desktop app drew
  0.4.4's icons: an icon's path never changed between releases, the mount
  sent no freshness, and the webview kept the old files as fresh — the
  snapshot had the new ones, the server sent them, the page never asked.
  The header fixes it going forward; the stamp is what gets a new release's
  page past what an older one cached. Any new `fetch('/static/…')` goes
  through `staticUrl()` too (ui.json, help-docs.md and Pele already do).
  `tests/test_static_assets.py` keeps both.
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
    (`readedit`, `girraph`, `merirmaid`, `wikisink`, `canon` — `cacheawl`
    until 0.4.3 — `paginated`, `dict`, `cosm`, `docs` — 0.4.4's, which
    replaced `ref` and `cosmspec` — and
    `blobview`, which shares the mini panel). **Composure is not one of them** — it is the base layer
    below the stack (z < 30), permanent and uncloseable; see "Composures".
  - `modeRemove(name)` — splice at any depth, re-apply z-order, re-render
    indicators. **Bookkeeping only**: it does not run `onExit` and does not
    hide the mode's root, so callers tear the mode down first (see "What
    NOT to touch", and the block comment at its definition, which names all
    eleven callers — 0.4.3 added `exitCosmMode`, and 0.4.4's `exitDocsMode`
    replaced `exitRefMode` and `exitCosmSpecMode` —
    and the one legacy wrapper that is the exception). A mode
    "closed" with this alone leaves its render loop spinning behind an
    element that is still in the DOM. Empty stack = the bare composure
    canvas.
  - `modeRaise(name)` — z-order + indicators only, plus the optional
    `onRaise` hook (Canon wires `cnLoadTree()` to refresh stale data);
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
  warning. Use it for confirmations (e.g. the saved-article update run,
  `#wiki-cachebox-update`, or the Canon chip's "decompile it again?")
  instead of `confirm()`.
- **The mode system.** preview/review/edit were unified into ONE read/edit
  mode with two faces (read-eye / edit-pencil) that lives either as a mini
  side panel or a full frame (`full2mini` / `mini2full` toggle, dirty
  guards). Face toggling happens on dedicated `readedit-switch` buttons in
  the read/edit chrome (`#review-face-btn` / `#edit-face-btn` /
  `#mini-face-btn`) — the topbar indicator is not a button. The full-frame
  family is wikisink, girraph, merirmaid, Canon, read/edit, the cosm
  viewer, the dictionary, and the read-only **docs viewer** below — all stack
  citizens.
- **The docs viewer (`#docs-mode`, name `docs`, 0.4.4).** The read-only
  reader for enough's four documents, the help center and the three
  specifications (MacroCOSM OES, and since 0.5.0 Thym and Ascribe),
  over their DocOES volumes (`GET /api/docs`; see "DocOES" and "The help
  system"). It replaced **reference mode** (`#ref-mode`, retired at plan §5's
  gate) and the 0.4.3 **spec viewer** (`#cosmspec-mode`). It renders into a
  `.review-body`-styled frame (the pretty-markdown CSS is shared via
  `:is(#review-mode, #docs-mode, #cosm-mode) .review-body`, and
  `applyReviewContrast()` covers `docs-mode` alongside review/wiki). View
  only by design: no edit face, no highlighting, no chat affordance. The
  `ref-mini` class (the 0.4.1 reader's, now the docs viewer's alone) docks it
  to the right edge (`docsToggleSize()`); launched from the small **help**
  button in the UI modal's header (`openHelpCenter()`) and from the
  "MacroCOSM ▾" menu beside it (`#ui-cosmspec-btn`, `#ui-thym-btn`,
  `#ui-ascribe-btn`). The 3D icon-button gradient used on square chips is
  the shipped two-stop ramp `rgba(128,128,128,0.42) → 0.10 at 62% → 0`
  over `var(--btn-bg, var(--bg-raise))`.

### Add a full-frame mode (the checklist, as dictionary mode ran it)

Dictionary mode (0.4.1) was built from ref mode, and this is the list it
actually had to tick. Grep `dict` beside each step for the worked example.

1. **A root** `<div id="<name>-mode" aria-hidden="true">`, hidden by CSS
   until `.open`.
2. **Register the root**: `_MODE_ROOT_IDS` (name → id), `_ALL_MODE_ROOTS`
   (z-order resets), and the `html[data-comp-peek="1"]` hide list in the
   CSS — miss the last and the composure peek leaves your mode on screen.
3. **`enter<Name>Mode(opts)`**: return on `IS_HOME` if it needs project
   routes; add `.open`, `aria-hidden="false"`; `modePush(name, {icon,
   onExit, iconTitle: t('modes.<name>.icon', …), exitTitle:
   t('modes.<name>.exit', …)})`; idempotent — a second call re-targets and
   raises. Export it on `window` for launchers and the uicheck steps.
4. **`exit<Name>Mode()`**: tear down first (timers, menus, polling, DOM you
   don't keep), remove `.open`, `aria-hidden="true"`, and only then
   `modeRemove(name)` — it is bookkeeping only.
5. **An icon**: the source SVG in `enough/static/icons/`, then
   `scripts/build_icons.py` (both variants; the content-integrity test
   checks every `data-icon` has them).
6. **A launch point** (dict: `#ui-dict-btn` in the UI modal header,
   `closeUIModal(); enterDictMode();`) and, if it takes a target, a
   function to open it *at* something (`dictShowWord`) that raises an open
   mode instead of re-entering it.
7. **Keys**: one document `keydown` that acts only when
   `modeTop().name === name`, `!modalStackTop()`, the panel isn't `full`,
   the composure isn't peeked, the confirm overlay is hidden, and the caret
   isn't in a field or the readvisor panel.
8. **⌘F and extra Esc rungs** through a `FIND_BARS[name]` controller —
   a real `findBarAttach` or a duck-typed one — rather than edits to the
   esc ladder.
9. **Scales and geometry**: text scale through the `--txz` selector list,
   or `calc(px * var(--txz))` if the mode measures its own layout; pointer
   coordinates through `UIZ()` before they touch a positioned element; a
   `ResizeObserver` for relayout; a hook for font / text-scale changes that
   don't resize anything (`dictOnUIChange`, called from `applyUIConfig` /
   `applyUIScales`, guarded until the wiring exists).
10. **Strings**: every one `data-i18n*` or `t()`, mirrored byte-for-byte
    into `en/ui.json` (docs/I18N.md steps 1–3).
11. **Themes**: colours from the theme variables only (`--accent-*`,
    `--fg-*`, `--bg-*`, `--border`); look at all four themes.
12. **Dialogs it opens** are `*-modal`s with their own Esc, so the shared
    helper does the rest; a context menu it adds goes in `MODAL.KEEP_LIVE`
    if it must work over one.
13. **uicheck**: a `Screen` per state in `scripts/uicheck/screens.py` and a
    scenario per interaction contract in `scripts/uicheck/interactions.py`.
14. **Docs**: a HELP_CENTER section (and the renumbering that follows),
    this guide, and help-docs.md sections only if it adds `data-help` rows.

0.4.3 ran the list twice more and 0.4.4 once. The **docs viewer** is the
variant to copy when the new mode is another long document: it is one mode
over any DocOES volume (`DOCS_DOCS` holds the per-document settings, a new
document is a row in `docoes.DOCUMENTS` plus one there — `kind: 'spec'` for
a specification's chrome, as Thym and Ascribe were added in 0.5.0), and the 0.4.1
reader's `ref*` functions take its reader context (`DOCS_CTX`; see "The help
system"). The **cosm viewer** is the variant for a structured
view that a second surface also draws: write its content functions against a
*host* (`COSM` / `EMF_FACE` / `ATEM_HOST`; see "The fabula") so the EMF
face and the atem card reuse them without a fork. Both also had to join
`dictCtxWhere`'s surfaces, the `applyReviewContrast` list and the shared
`.review-body` selector lists.

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
  one-line file still parses (and a stored `default` is migrated to the
  home paradigm on launch — see "Add a new paradigm"), and every legacy
  help value (the old `all`
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
- **Canon's catalogs and meta are backend-owned — never hand-edit them.**
  A volume's `canon.cosm`, the project's `rness/canon.cosm` and every
  `.canon.json` are written only by `canon.py` (and the legacy
  `.cachebox.json` / `_cachebox.merirmaid` only ever migrated or deleted by
  it). Both write doors (`write_file`, `POST /api/file`) already refuse them
  through `canon.catalog_write_denial`, and transfer refuses them as either
  end; don't add a path that edits one from anywhere else — a catalog edited
  by hand is overwritten at the next reconcile (its sha no longer matches the
  last write). To change what a catalog lists, change the files.
- **Don't edit the synced Comprise manifest, and never copy Comprise's
  private fixtures.** `defaults/cosm/manifests/comprise.manifest.cosm` and
  `tests/fixtures/cosm/holotypes/` are byte copies made by
  `scripts/sync_cosm.py` (retired in 0.5.4; git history at e318fcd) from
  comprise-dev, which is read-only from this repo; a change belongs in
  comprise-dev, then a re-copy. The copies were named by allowlist — the
  four public Holotypes only; comprise-dev also holds a partner's
  client fixtures (its `fixtures/PRIVATE.md`), and nothing of theirs may
  reach enough — not a file, not a test, not a name in a doc or a commit.
- **A twin's `source:` and `derived:` blocks are the engine's.** They are
  how `emf_state` knows fresh from stale and how the UI knows a scaffold from
  a reading (and, since 0.6, which route and model made it); edit them by
  hand and a stale twin reads fresh, or a rules scaffold passes for a
  model's reading. Refresh a twin through decompile (`POST
  /api/fabula/derive` with `force`, or `fabula_derive`) instead. Items may be
  edited as raw text — a twin is the user's derived text — but a re-derive
  replaces everything except pinned `X:atem` items, the `shorts:` list and
  the dialectic's D items, which it carries. A fabulac's `derived.runs` is
  the build's state on disk: hand-edit it and a build resumes at the wrong
  stage.
- **Never rename, migrate or rewrite an old fabula.** `oes: emf/1` and
  `<text>.cosm` are read forever; the only thing that replaces an old twin is
  decompiling its text again (`canon_derive.replace_twin`). Listings,
  catalogs, reconcile, import, copy and every write that is not a decompile
  (an atem, a pin, a short's record) leave its name and declaration as they
  are. Every name rule lives in `enough/fabula_names.py`; add none elsewhere.
- **Nothing read or entailed is ever run.** A folder a fabulac is built from is
  read by its syntax and its git log only (`repo_engine`: one fixed git
  command line, no shell, no hooks, no network); a cshort is text, shown and
  never imported, compiled, installed or run. Keep it so: no route, tool or
  page action may offer to run a cshort or a file of a surveyed folder.
- **Derivation never happens on its own, and a tool never waits on a job.**
  Imports, ingests, tree builds, listings and reconciles must not call
  `canon_derive` or `llm.complete`. And the readvisor tools run inside a chat
  turn that already holds `session.generation_lock`: a tool that took the
  lock, or waited on a job that takes it, would deadlock the turn. A text
  tool calls the engine directly and holds the file's claim
  (`CanonJobs.holding`), as `canon_tools` does; a tool that starts long work
  (`fabulac`, `dialectic`'s settle) starts a job through
  `server._start_from_tool` and returns without waiting — see "The fabula" →
  the concurrency rule.
- **`enough/retired_names.py` goes in 0.7.** It is the one table of names the
  0.6 round retired that still answer (`/api/canon/emf`, `/api/canon/derive`,
  `/api/canon/compile`, the tool `emf_derive`, `what: emf`). Never document
  an old name, never add a new caller of one, and when 0.7 comes delete the
  table, the loop over `ROUTES` in `server.create_app` and the lookup of
  `TOOLS` in `tools.execute` together (`tests/test_dialectic_api.py` pins
  that every retired route is served by its new route's handler and that no
  prompt names a retired tool).
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
- **`session.pal_turn` must be cleared on every exit path.** It is set only
  by `pal_tools.pal_turn()`, a context manager that clears both it and the
  module-level `_active` in a `finally` — clean return, LLM error, the
  auto-reset path, a cancelled `asyncio` task. **A pal flag left set is a
  turn in which the model can send whatever it likes to the cloud without
  the user having asked for anything**, which is why `tests/test_pal.py`
  tests the window five ways. Never assign `session.pal_turn` or
  `pal_tools._active` by hand, and never open the window around anything
  wider than one `_run_turn`. Note also that **the one-call limit is per
  `_run_turn`**, so an auto-reset firing mid-pal-turn does *not* hand out a
  second call: the checkpoint and continue turns run inside the same window.
- **`council.PAL_CALL` defaults to a function that raises**
  (`NotImplementedError("pal lane")`), and `ask_pal_turn` re-raises it
  untouched rather than wrapping it in a `CouncilError` — that is how a
  caller tells "nobody wired a pal in" apart from "the pal could not
  answer", which *is* wrapped. Do not give it a silent no-op default, and do
  not import `pal_tools` or `cloud` into `council.py` to save the wiring:
  the gate, the cache, the trace, the exfil patterns and the one-call limit
  live with `/pal`, and a second copy of any of them is how one of them ends
  up a step short.
- **`council.RESERVED_KINDS` is `frozenset()` now.** Code that reads it
  still works and must keep working (`brief_text`, the transcript export and
  `state()["reserved"]` all read it), so do not delete the name because it
  is empty — the next reserved participant kind should cost one line instead
  of five call sites. Emptiness is not deadness.
- **The tool-doc budget is always on.** `tests/test_prompt_weight.py` pins
  `CORE_BUDGET` (4 000 since 0.5.1 — the always-on core plus the dictionary
  block; 17 500 before the long sections became blocks of their own),
  `FULL_BUDGET` (24 500, every gate open), `LEAN_BUDGET` (22 500, a fresh
  project's whole lean prompt), `PAL_BUDGET` (1 200), `CANON_BLOCK_MAX`
  (1 000, the MacroCOSM block) and, since 0.4.3, `HEAD_DEFAULT_PROMPT`
  (74 307 — a fresh project's whole assembled prompt at 0.4.2, which the
  default prompt may outgrow by at most the MacroCOSM block). A new tool
  therefore either **gates its documentation block** the way composures,
  readvisory, the dictionary, MacroCOSM, the fabula block (by the
  `macrocosm-oes` skill, 0.6) and pal do, or **raises the budget on purpose,
  in the same commit, with a reason** (0.4.1 did: +900; 0.4.3 did: +809,
  exactly the MacroCOSM block; the comment beside the constant says what
  for). The lean prompt is the tight one: an 8,192-token window must still
  hold it with the 2,048 reserve. `FULL_BUDGET` measures what an *ordinary* turn can carry, which
  is why the pal block is not counted in it — the per-turn gate is what
  bought that exemption, not an argument that the block is small.
- **A tier's `ctx_defaults` is a memory promise, and the fit test watches
  it (0.4.3).** `feasibility(entry, ctx=)` treats any window above the
  tier's default as a RAM "no", so raising a tier widens what the
  preflight's one-click fix will offer on every machine in it — do it only
  with a measurement behind it (docs/ctx-16gb-plan.md §3) and with
  `test_every_shipped_window_holds_the_default_prompt` agreeing; a pair
  that starts fitting comes off `KNOWN_TOO_SMALL` in the same commit, and a
  pair never goes *on* it to turn a red test green without the owner.
  Lowering a tier below a fresh project's prompt + 2,048 is exactly the
  first-turn 400 this test exists to stop.
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
- **`read_file` may read through `rness/` symlinks into shipped files —
  and nothing else may (0.4.1).** A shipped skill, paradigm, policy or
  readvisor in a project is a symlink out of it, so plain containment
  refused `read_file("rness/skills/<name>/SKILL.md")`, and a model whose
  skill was off could not read the very file the sidebar showed.
  `tools._shipped_read_target(project_dir, p)` is the one exception, and
  both halves must hold: the path **as written** sits under `rness/` with no
  `..` (an absolute spelling of the same path counts), **and** its fully
  resolved target sits inside a shipped root (`_shipped_roots()`: the
  install's `defaults/` and `skeleton.user_readvisors_root()`), so a
  symlink planted in the project and aimed anywhere else is still refused.
  `_safe_join(…, allow_shipped_read=True)` is passed by `read_file` only and
  ignored whenever `allow_outside_write` is set; writes through those
  symlinks stay refused. `tests/test_shipped_read.py` pins all of it. Don't
  widen the roots: everything under them already reaches the prompt, and a
  new root would make `read_file` a door to something that doesn't.
  (`dict_guide` predates this and still reads the install's copy itself.)
- **`reflib/dict/` is not open-source, and `user-dictionary.sqlite` is not
  disposable.** The first is FEED's shipped text form, all rights reserved
  (its `NOTICE.md`), regenerated only by `scripts/sync_dictionary.py` —
  never hand-edited, never copied into another repo or package. The second
  is the user's own words: no code path may rebuild, migrate-by-recreate or
  delete it; a schema change has to be an in-place migration. `feed.sqlite`
  is the opposite — delete it and the next launch rebuilds it.
- **The MacroCOSM spec and manifests are not open-source either.**
  `docs/MACROCOSM_OES.md`, everything under `defaults/cosm/` and the names
  MacroCOSM, MiniCOSM, MicroCOSM, Canon, EMF and atem are all rights
  reserved (`defaults/cosm/NOTICE.md`); the reader `enough/macrocosm.py` is
  Apache like the rest of enough. Don't relicense, vendor or describe the
  first as part of the open-source tree. Verroes, the spec's steward, is
  named once, in the spec's §1.3, and nowhere else (owner decision 11).
- **`index.html` contains literal NUL bytes, on purpose.** `renderInline`'s
  code-span placeholders are `\x00CS<n>\x00` written as real NULs, not the
  escape (see "The help system"). An editor or a script that drops NULs
  corrupts inline code everywhere the shared markdown renderer runs;
  `cat -v` shows them as `^@`.
- **Every new global-state location needs a seam, in both harnesses, in
  the same change.** The rule is not "add an `ENOUGH_*` variable"; it is
  add it *and* wire it into **`scripts/smoke_boot.build_env()`** and
  **`tests/conftest.py`'s `_STATE_SEAMS`** (autouse for the whole suite).
  `ENOUGH_READVISORS_ROOT` is the current example of why: without it an
  `install_readvisor` at global scope during a test or a scratch QA run
  writes into the developer's real `~/enough/readvisors/` and is then
  symlinked into every project they open afterwards — a leak that survives
  the run that caused it. Anything a test can reach that is not under
  `tmp_path` is a bug in the seam list, not in the test. The newest is
  `ENOUGH_CANON_ROOT` (0.4.3). A *renamed* location kept its old seam too
  for one release (`ENOUGH_CACHEAWL_ROOT`, read as a fallback until 0.6
  removed it); both harnesses now set the one seam that exists.
- **Don't put `--btn-bg` in `:root`.** Button chips use `var(--btn-bg,
  var(--bg-raise))`, and the fallback is load-bearing: old user configs that
  predate the `btn-bg` theme color rely on `--btn-bg` being *undefined* so
  the `--bg-raise` fallback kicks in. A `:root` default would defeat that.
  The shipped themes carry `btn-bg` in their theme `colors` (and the
  server backfills it for pre-0.1.6 configs — see `_merge_shipped_theme_keys`
  in server.py); the CSS default must stay absent.
- **The `canon:` scheme resolves through
  `_resolve_project_path` only.** That's the single door from the
  project-relative file endpoints — and `/api/cosm*`, the derivation routes
  and the MacroCOSM tools — into the machine-global store. Don't add other
  global-path prefixes or bypass the helper — the traversal check and the
  catalog/meta write-guards all hang off that one resolution point. A new
  prefix spelling goes into `server.STORE_PREFIXES` **and**
  `canon_tools.STORE_PREFIXES` (a test keeps them equal).
- **A dev server against your real home renames `~/enough/cacheawl` to
  `~/enough/canon` on first use.** `canon.root()` does the one-time folder
  rename on the default path, so `uv run enough` from a 0.4.3 checkout with
  your real `$HOME` and no `ENOUGH_CANON_ROOT` moves the owner's live store.
  A 0.4.2 app started afterwards recreates an empty `~/enough/cacheawl/`, and
  0.4.3 then warns "both exist" and keeps using `canon`. Intended behaviour —
  but QA against a scratch home (`smoke_boot.build_env()`), never the live
  one. Every project opened by a 0.4.3 server also gains `rness/canon.cosm`.
- **The pytest suite lives in `tests/`** (tracked since the seven-models
  round; it was gitignored before — `git log` has the story). Run
  `uv run pytest tests/ -q` before declaring done; it covers girraphs,
  project metadata, the Canon store + `/api/canon/*` + the `canon:` path
  scheme + the project catalog (`test_canon.py`, `test_canon_api.py`;
  the legacy `test_cacheawl*.py` went with the shim in 0.6), the MacroCOSM reader, its
  fixtures and the spec's examples (`test_macrocosm.py`,
  `test_sync_specs.py`, `test_specs.py`, `test_macrocosm_spec.py`), the cosm routes
  (`test_cosm_api.py`), the derivation engine, jobs and routes
  (`test_llm_complete.py`, `test_canon_derive.py`,
  `test_canon_derive_api.py` — rules mode, or a monkeypatched
  `llm.complete`; never a real model) and the MacroCOSM tools
  (`test_canon_tools.py`), the ui-config theme-key merge, the models
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
  **`ENOUGH_CANON_ROOT`** (its legacy `ENOUGH_CACHEAWL_ROOT` fallback was
  removed in 0.6),
  `ENOUGH_INFOWORLD_ROOT`, `ENOUGH_UI_CONFIG`,
  `ENOUGH_WEIGHTS_DIR`, `ENOUGH_EXTRAS_STATE`, `ENOUGH_LIVE_STATE`,
  `ENOUGH_MODELS_REGISTRY`, `ENOUGH_PROJECTS_STATE`,
  **`ENOUGH_READVISORS_ROOT`**, **`ENOUGH_DOCS_ROOT`** (0.4.4, the built doc
  volumes), **`ENOUGH_THYM_ROOT`** (0.5.0, Thym's runs), **`ENOUGH_SPECS_ROOT`**
  with **`ENOUGH_SPECS_SYNC=0`** and **`ENOUGH_COSMOES_BASE`** at a dead loopback
  port (0.5.4, the specifications synced from cosmoes.org: no test may reach
  it), **`ENOUGH_DICT_ROOT`** and
  **`ENOUGH_DICT_SOURCE`** (the latter pointed at *nothing*, so no test
  starts a 380 MB build — see "The dictionary (FEED)")
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
  and a council test that needs a model has bypassed it. The Canon round's
  derivation suites keep the same rule by monkeypatching `llm.complete` /
  `llm.reachable` (or running rules mode) — and they must patch the live
  state too: `models.LIVE_STATE` is resolved once, at import, before the
  autouse seam applies, so an unpatched `llm.complete` reads the developer's
  real `models.json` to choose local or cloud. The
  rest of the web layer is exercised via TestClient against `create_app()`.
  **The `ENOUGH_*` list is not sufficient on its own**: `broker.json`,
  `openrouter.json`, `orchestrator.json`, `~/enough/.llama-server/server.pid`
  and `~/enough/bin/` are plain `Path.home()` reads with no hook, so a
  suite (or a scratch server) that touches any of them must also
  `monkeypatch.setenv("HOME", …)`. `tests/test_llama_server_lookup.py`,
  `tests/test_platform_linux.py` and `scripts/smoke_boot.py` all do.
  **And three of them bind at import** (found in the 0.5.0 round, when
  `~/enough/config/broker.json` was rewritten during a wave with no writer
  identified): `broker.CONFIG_PATH`, `cloud.CONFIG_PATH` and
  `server.ORCHESTRATOR_CONFIG` are computed from `Path.home()` when the module
  is imported — at collection, before any fixture moves `$HOME` — so moving
  `$HOME` alone does not reach them. `tests/conftest.py`'s autouse fixture now
  patches all three into the test's `$HOME` for every test; a new module-level
  path computed from `Path.home()` needs the same line there.
- **A Thym package is kept whole (0.5.0).** A `<stem>.thym/` folder whose
  `package.cosm` sniffs `oes: thym/1` is one thing: Canon's scan never
  recurses it, its catalog lists it as one `kind: package` item, the mirror
  draws it as one node, and `canon_tools.text_target` refuses it and anything
  inside it ("a package is kept whole: unpack it beside itself, then derive the
  text it gives"). Never decompile, atem or write into a package folder; a
  digest in its catalog would stop matching. Unpack writes beside it, never
  over a file that differs, and nothing on a refusal.
- **The Thym root is the runtime's (0.5.0).** Only `thym.run` writes under
  `ENOUGH_THYM_ROOT`; a run lands all of its outputs or none (`stage/` then a
  move), and `candidates/` is what makes a replay byte-identical — editing a
  recorded candidate makes that run's replay refuse at the first digest that
  differs. The two replay fixtures under `tests/fixtures/thym/replay/` are
  frozen records of real-model runs: re-record, never hand-edit. A shipped
  program in `defaults/thym/` must stay byte-identical to its copy in
  `tests/fixtures/thym/programs/` (a test pins it).
- **The sealed package's key is shown once and stored nowhere.** `POST
  /api/canon/package {encrypt: true}` returns `key` in the response only; a
  test greps the project and the Thym root for it. Never log it, never put it
  in a trace, a snapshot or an SSE event.
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
   active-paradigm seed — the home paradigm, text-planning) only if
   absent — preserves user edits
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
   filesystem (e.g. a shared Canon volume in `~/enough/canon/`). A
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
- `pyyaml>=6.0` — the MacroCOSM reader's one dependency (0.4.3; declared
  explicitly, though it was already in the lock transitively)
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

A pytest suite lives in `tests/` (girraphs, project metadata, the Canon
store + endpoints + the `canon:` scheme, the ui-config theme-key merge, the
models registry/feasibility/downloads, the llama-server lookup, the desktop
shutdown gate, the platform seams, the shipped skills' frontmatter/tooltip/
script conventions, the skill trust model + first-use audit + `/api/skills*`,
document conversion + `/api/convert/*` + `/api/file/blob`,
the home screen + registry + handoff + `/api/home/*`,
the throttled wikisink newer-snapshot check, and — since 0.3.5 — the
composure format/ops/API/tools + the outline converter, the council engine
+ `/api/council/*`, the readvisors' migration/sources/install/removal, and
the prompt-weight budgets; since 0.4.1 the dictionary's sync filter, build,
reads, user entries and routes, its readvisor tools, the intro, the
shipped-read exception, the home-paradigm migration, and the CSS structure
of every page; since 0.4.3 the MacroCOSM reader against Comprise's public
samples and the spec's own examples, the project catalog, the cosm routes,
the derivation engine, jobs and routes, and the MacroCOSM tools; since 0.5.0
Thym; in the 0.6 round the fabula's names, writers and checks, verse, the
dialectic, the fabulac job, the model route, Ascribe's module and `thym 1`)
— **tracked since the
seven-models round**, so a fresh clone has it. Before declaring anything
done:

```bash
uv run pytest -q                        # ~3330 tests (+docling skips)
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

**MacroCOSM and Canon, day to day (0.4.3).**

- `uv run python scripts/sync_specs.py --check` says whether the four bundled
  specifications or the vendored client differ from a cosmoes-site checkout at
  `../../cosmoes-site` (or `--cosmoes DIR`; exit 2 when there is none); without
  `--check` it re-copies them into `docs/*.md`, `enough/cosmoes_client.py` and
  writes `docs/specs.json` (then run `tests/test_docoes.py` and
  `tests/test_sync_specs.py`). It only ever reads cosmoes-site.
  desktop/RELEASE.md runs it before every bump. (`scripts/sync_cosm.py`, the
  comprise-dev direction, retired in 0.5.4.)
- `GET /api/specs-status` on any running server says whether the launch check
  ran, what it updated and where each specification comes from.
- `uv run python -m enough.macrocosm lint|tree|paths|mermaid|identify
  <volume>` is the quickest look at any `.cosm` — no server, nothing
  imported from enough. `tests/fixtures/cosm/` has a volume of every kind to
  try it on.
- `ENOUGH_CANON_ROOT` is in
  `smoke_boot.build_env()` and `conftest._STATE_SEAMS`, so a scratch server
  built from `build_env()` has its own store. Without the seam, a dev server
  against your real home renames `~/enough/cacheawl` to `~/enough/canon` on
  first use (see "What NOT to touch").
- No test reaches a model, so a real-model check of the derivations is by
  hand: a scratch server with `--llm-url` pointed at a running llama-server,
  a scratch project holding a copy of `tests/fixtures/cosm/emf/notes.md`,
  decompile from the Canon chip. The reference timing is gemma-4-E4B: ~105 s
  for a 330-word note's twin, ~13 s for a passage atem.
- **The fabula round's command lines (0.6)**, every one under the seams
  (`HOME` and every `ENOUGH_*` in scratch, as `scripts/smoke_boot.build_env()`
  makes them; a one-file wrapper that execs a command with that env is the
  usual way): `uv run python -m enough.fabula lint <fabula> [--json]` (a
  fabula's own checks), `python -m enough.dialectic list|raise|answer|settle
  <volume>`, `python -m enough.ascribe lint <holograph>`, and `python -m
  enough.thym conform` (119 passed, 0 failed, 0 skipped since lane T3). A real-model check of a fabulac build is by hand, on
  a scratch project holding a small folder of your own Python (agents of
  this repo do not clone or run third-party repositories).
- **Validate a commit on an isolated export of the exact tree.** Each wave of
  the 0.6 round was checked on a clean `git archive` of the tree being
  committed (with other sessions in the same checkout: stage only your
  hunks, then `git archive $(git write-tree)` into a scratch folder, `uv sync
  --frozen` there, run the suite there), so a file left unstaged or a
  local-only fixture cannot make a green run lie. And a push to enough's
  main that changes the docs exporter's output (its CSS, a reference count)
  makes every open cosmoes-site pull request fail its `in-step` check until
  that request's export is rebuilt from the new main.

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
- **`tests/test_css_integrity.py`** (0.4.1, inside `pytest`) is the
  *stylesheet* half. Browsers never report a CSS syntax error; they
  recover, and the recovery can take a neighbour down with it. 0.3.5
  inserted the composure block directly above `.conversation {` and the
  selector line went with the edit: the declarations were left at
  rule-list level, the parser swallowed them — and the closing brace, and
  the `.empty-hint` selector after it — as one invalid prelude, and the
  chat lost its padding, its scroller and its centred empty hint for two
  releases while every test stayed green. So a small tokenizer (comments,
  strings, `url()`/parens, the two at-rule shapes) walks every `<style>` of
  every page under `enough/static` and fails, with page and line, on a
  declaration run at rule-list level (a `;` before any `{`), a prelude that
  runs into `}`, an empty selector, a `{` inside a declaration block (there
  is no CSS nesting here — teach it `&` the day there is), a declaration
  without a colon, and anything unclosed.
  `test_catches_the_0_3_5_orphaned_conversation_rule` keeps the original
  break as a fixture.
- **`scripts/ui_check.py`** is the *layout and behaviour* half: a real
  headless Chrome over the DevTools Protocol, driving two scratch enough
  servers (project + home). **Zero new dependencies** — CDP is JSON over
  one WebSocket and `websockets` already ships as a transitive of
  `uvicorn[standard]`. For every (screen × viewport × language) it asks
  the page to measure itself: clickables that something in their own
  layer covers, rects that overlap where the overlap costs a click, text
  clipped under `overflow:hidden`, controls outside the viewport with no
  scroller, targets under 16px. An element inside a card the browser is not
  drawing (`content-visibility: auto`, scrolled out of its scroller) is not
  measured (`scripts/uicheck/probes.js`, 0.6: `el.checkVisibility({
  contentVisibilityAuto: true })`): asking it for its rect still lays it out
  inside the card's placeholder height, so a long list spilled over the
  cards that were drawn and read as covered by them. Then it runs the MODE
  STACK scenarios once per language. No Chrome anywhere → one SKIPPED line and a green
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

**The browser check owns its fixtures (0.6).** A seed copies what it needs
from `scripts/uicheck/fixtures/` (today `dialectic/`: `close.md`, its
fabulan with nine questions and an answers volume, the files as they stood
at 43f70be; `DIALECTIC_OWN` in `scripts/uicheck/server.py`), never from the
suite's `tests/fixtures/`. The suite's fixtures follow the specifications'
examples and move whenever a text is corrected (the third errata pass put 29
open questions in the twin and broke two scenarios that counted nine); a
screen or scenario asserts what a person sees, so its data must change only
when the check's author changes it. Add new seed data there, not by reading a
suite fixture.

**A wait is made in short calls, with the budget in the check (0.6).** One
`js_await` has a 20 s reply limit, so a wait that looped inside the page for
longer could never be honoured under load ("no reply within 20.0s").
`_wait_js(d, cond, ms)` in `interactions.py` now polls from the harness: each
call reads the condition and returns at once (10 s limit a call; a busy
page's timeout is retried), and the budget `ms` is kept in Python. The 0.6
scenarios use `_ready(d, cond)` for a surface's ready condition (a minute)
and give a job 90 s and a plan 60 s. Never write a wait as one long in-page
loop.

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

**Not covered by the Apache licence:** `reflib/dict/`, FEED's dictionary
data. © 2026 Graham Smith, all rights reserved, bundled for use within
enough only; a licence is still to be decided. Its
[NOTICE.md](../reflib/dict/NOTICE.md) is authoritative.

**Nor are the OES specifications** (0.4.3; four since 0.5.4): MacroCOSM OES,
Thym, Ascribe and Comprise OES ([docs/MACROCOSM_OES.md](MACROCOSM_OES.md),
[THYM.md](THYM.md), [ASCRIBE.md](ASCRIBE.md), [COMPRISE_OES.md](COMPRISE_OES.md)
— the canonical editions published at cosmoes.org, bundled by
`scripts/sync_specs.py` and refreshed from there at run time), the MiniCOSM manifests in
`defaults/cosm/manifests/` and the names MacroCOSM, MiniCOSM, MicroCOSM,
Canon, fabula (EMF before) and atem are © 2026 Graham Smith: the
specifications and the manifests are published under CC BY 4.0 with a patent
promise under OWFa 1.0 in the author's name (enough reads the manifests and
shows the specs in its docs viewer); the names are licensed by neither, held
by the author for now, to move later to a body that is not a company.
[defaults/cosm/NOTICE.md](../defaults/cosm/NOTICE.md) is authoritative, and
`tests/fixtures/cosm/NOTICE.md` covers the synced Comprise samples. **The
reader, `enough/macrocosm.py`, is part of enough and Apache 2.0** with the
rest of the code. Both exceptions are listed in THIRD_PARTY_LICENSES.md's
"First-party material under separate terms", in `README.md`'s licence line,
and in the Help Center's footer.
