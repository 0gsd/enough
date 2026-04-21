# enough

A **paradigmless personal computer harness** powered by a local LLM. It ships
empty. You make it useful by defining your own paradigms, workflows, agents,
and knowledge stores through plain-text conventions in a `.rness/` directory.
The model helps you do this from the very first message.

One `enough` instance = one agent = one context = one `.rness/` directory.
Multi-agent? Run multiple instances in different directories. There is no
built-in orchestrator, no message bus, no agent framework. The filesystem is
the coordination surface.

Status: **v0.0.3 — pre-alpha.** The architecture is in place; the ideas on top
of it are up to you.

---

## What's inside

```
┌─────────────────────────────────────────────────┐
│  Browser (htmx)  ──SSE/HTTP──▶  FastAPI server  │
│                                      │          │
│                                      ▼          │
│                           llama-server (you run │
│                           it; localhost:8080)   │
└─────────────────────────────────────────────────┘

~/enough/                ← install dir (the "home base")
├── defaults/            ← source-of-truth templates for every new project
│   ├── AGENT.md
│   ├── MOTIVATION.md
│   ├── paradigms/default.md
│   ├── policies/{requests,context-management,read-allowlist}.md
│   ├── models/providers.md
│   ├── skills/          ← drop a skill folder here to make it global
│   └── routines/
├── infoworld/           ← per-user shared knowledge store
│   ├── wiki/
│   ├── personal/
│   └── public/
├── weights/             ← GGUF model file(s)
├── enough/              ← the Python package (CLI, server, skeleton, tools)
├── bootstrap.sh
└── llama_server.sh

./your-project/          ← any directory where you run `enough`
├── .rness/
│   ├── AGENT.md                     (COPY — diverges per project)
│   ├── MOTIVATION.md                (COPY)
│   ├── paradigms/default.md         (symlink → ~/enough/defaults/...)
│   ├── policies/                    (symlinked)
│   │   ├── requests.md
│   │   ├── context-management.md
│   │   └── read-allowlist.md
│   ├── models/providers.md          (symlink)
│   ├── skills/                      (one symlink per skill; toggle on/off in UI)
│   ├── routines/                    (symlinked, user-authored)
│   ├── requests/                    (per-project; active .md files)
│   │   └── done/                    (user confirms via "mark done" button)
│   └── knowledge/
│       ├── user-profile.md          (COPY)
│       └── session-logs/            (one .md per day)
├── infoworld/                       (symlink → ~/enough/infoworld/)
└── [whatever else you're working on]
```

Symlinked files render **italic + muted** in the UI. Click a symlinked file,
hit **"customize for this project"** in the preview pane, and the symlink is
replaced with a project-local copy you can edit. Edit a file in
`~/enough/defaults/` directly and every project still using the symlink
picks up the change on the next message.

---

## Install

### One-shot: `bootstrap.sh`

```bash
git clone git@github.com:0gsd/enough.git /tmp/enough-seed
cd /tmp/enough-seed
bash bootstrap.sh
```

The script is idempotent and walks through eight steps, explaining each
before it runs:

1. macOS platform check
2. Homebrew presence
3. Installs `llama.cpp`, `uv`, `tor` via brew (skips ones already installed)
4. Clones (or pulls) `github.com/0gsd/enough` to `~/enough`
5. `uv sync` inside `~/enough`
6. Model weights: either moves an existing GGUF you point to, or downloads
   the recommended Gemma 4 26B MoE Q4_K_M (~16 GB) from HuggingFace
7. Drops a shim at `~/.local/bin/enough` so the CLI is on PATH
8. Done message with next-steps

After that you can delete `/tmp/enough-seed` — `~/enough` is the install.

### Prerequisites if you're skipping the script

- **macOS** (Linux support is on the roadmap; nothing here is fundamentally
  Mac-only, it just hasn't been tested)
- **Python 3.11+**
- **Homebrew**
- **llama-server** (from [llama.cpp](https://github.com/ggml-org/llama.cpp))
  listening on `http://localhost:8080`
- **[uv](https://docs.astral.sh/uv/)**
- A GGUF model in `~/enough/weights/`. Recommended:
  [ggml-org/gemma-4-26B-A4B-it-GGUF][g4] Q4_K_M — 26B MoE, ~4B active
  parameters, ~16 GB on disk, fast on Apple Silicon.

[g4]: https://huggingface.co/ggml-org/gemma-4-26B-A4B-it-GGUF

---

## Running

```bash
# Start the LLM (once per boot; bundled toggle script handles flags):
MODEL=~/enough/weights/gemma-4-26B-A4B-it-Q4_K_M.gguf ~/enough/llama_server.sh start

# Go to any directory and launch enough there:
cd ~/my-project && enough
```

The browser opens to `http://127.0.0.1:3456`. First launch in a new
directory creates `.rness/` and symlinks the defaults in. Subsequent
launches in the same dir reuse what's there.

### CLI flags

```
enough [--dir PATH] [--port N] [--llm-url URL] [--no-browser] [--max-tool-iters N]
```

| flag | default | notes |
|---|---|---|
| `--dir` | cwd | project directory; refuses to run inside `~/enough/` itself |
| `--port` | `3456` | web UI port |
| `--llm-url` | `http://localhost:8080` | where llama-server is |
| `--no-browser` | off | don't auto-open the tab |
| `--max-tool-iters` | `50` | cap on tool invocations per user turn |

### `llama_server.sh` — LLM toggle

```bash
MODEL=<path> ./llama_server.sh start|stop|status|logs|toggle
```

Env defaults: `HOST=127.0.0.1 PORT=8080 NGL=99 CTX=32768 PARALLEL=1`.
Override any by exporting. Runtime state (pid, log) goes into
`.llama-server/` next to the script; that directory is gitignored.

The `--jinja` flag is applied automatically — it makes llama-server use the
chat template embedded in the GGUF, which `enough` relies on.

---

## The `.rness/` directory

Everything about your agent's identity, behavior, and memory lives here as
plain text. The system prompt is **re-assembled from these files on every
request** — edits take effect on the very next message, no restart needed.

Files fall into three categories:

**Copies (per-project, diverge from day one):**
- `AGENT.md` — who the agent is.
- `MOTIVATION.md` — accumulated learning; agent proposes updates at session
  end, you apply.
- `knowledge/user-profile.md` — what the agent knows about you.

**Symlinks to `~/enough/defaults/` (global defaults, upgrade-in-place):**
- `paradigms/default.md` — session structure, output conventions, security
  posture.
- `policies/requests.md` — long-horizon request tracking convention.
- `policies/context-management.md` — how to sense pressure and gracefully
  reset.
- `policies/read-allowlist.md` — which paths OUTSIDE the project dir the
  agent may read (default: `~/enough/` only).
- `models/providers.md` — model/provider notes.
- `skills/<name>/` — symlinked individually per skill. Drop a folder in
  `~/enough/defaults/skills/` to make it global; drop directly into a
  project's `.rness/skills/` to keep it project-local.
- `routines/*.md` — same pattern.

**Per-project, not sourced from defaults:**
- `requests/` + `requests/done/` — active and completed requests.
- `knowledge/session-logs/<YYYY-MM-DD>.md` — every exchange, written by
  the harness.

Optional:
- `INTENTION.md` — if present, injected as the current session intention.

### Editing in the UI

Click a file in the sidebar → preview pane opens. If it's a direct file
(copy), hit **edit** → textarea → **save** / **cancel**. If it's a symlinked
global default, you'll see a **"customize for this project"** button
instead — one click replaces the symlink with a project-local copy, and the
edit button appears.

The sidebar also has:
- **skills** — toggle any skill on/off. Disabled skills are excluded from
  the system prompt and tracked in `.rness/skills/.disabled`.
- **requests** — active request files, newest first. Click to preview; the
  preview chrome grows a **mark done** button that moves the file into
  `done/`.

---

## `infoworld/` — shared grounded knowledge

Lives at `~/enough/infoworld/`, symlinked into every project as `./infoworld`.
All projects on your machine see the same files; writes to
`infoworld/personal/` etc. persist across projects.

```
~/enough/infoworld/
├── wiki/       ← wikipedia dumps (user-populated)
├── personal/   ← your own docs, bibles, notes
└── public/     ← reference material that could reasonably be shared or
                  published (same behavior as personal/ for now; name
                  reserves the slot for a future distinction)
```

The system prompt tells the agent to `grep` / `read_file` here before
relying on training data. Smarter indexing / retrieval is a future-version
concern.

### Populating `infoworld/wiki/`

Two common paths:

1. **Kiwix ZIM extraction.** Download a `.zim` from
   [kiwix.org](https://kiwix.org/), then use
   [`zimdump`](https://github.com/openzim/zim-tools) to extract plaintext.
2. **Wikipedia dumps + WikiExtractor.** Grab `enwiki-latest-pages-articles.xml.bz2`
   from <https://dumps.wikimedia.org/enwiki/> and run
   [WikiExtractor](https://github.com/attardi/wikiextractor).

---

## Tools the agent has

Three tools, described in the system prompt:

- `read_file` — read a text file. Relative paths stay inside the project;
  absolute paths (e.g. `~/enough/defaults/...`) are allowed iff they match
  the **read allowlist** (`.rness/policies/read-allowlist.md`).
- `write_file` — write a text file. Relative paths only, `mkdir -p`
  behavior. Writing to `.rness/requests/done/` is blocked at the harness
  level — the "mark done" UI button is the only legitimate way to move
  files there (user approval = the rename).
- `shell` — run any shell command in the project directory. Unrestricted
  (the deliberate "nuclear option"); use sparingly.

Tool calls use an XML-ish tag format the model emits inline; the server
parses them with regex. Tool loop is capped per turn (default 50, set via
`--max-tool-iters`).

---

## Customizing globally

You edit `~/enough/defaults/` and every project still using the symlinks
picks up the change immediately.

```bash
nvim ~/enough/defaults/paradigms/default.md          # change the paradigm for ALL projects
nvim ~/enough/defaults/policies/read-allowlist.md    # broaden read access
ln -s /path/to/my/new-skill ~/enough/defaults/skills/ # add a global skill
```

`~/enough/` is a git checkout of `github.com/0gsd/enough`. If you plan to
maintain your own edits and still pull upstream updates, fork the repo, set
`~/enough`'s `origin` to your fork, and add upstream as a second remote:

```bash
cd ~/enough
git remote set-url origin git@github.com:YOU/enough.git
git remote add upstream git@github.com:0gsd/enough.git
git pull upstream main    # pull upstream changes into your fork
```

---

## What v0.0.3 *doesn't* do

Deliberate omissions — see [bootstrap spec](dev/) for the full thinking:

- No multi-agent coordination (one instance = one agent).
- No MOTIVATION.md auto-update (model proposes; you apply).
- No RAG / embedding / vector store. The model greps.
- No authentication. Localhost only.
- No persistent conversation history across restarts (session logs remain).
- No paradigm switching mid-session.
- No Linux / Windows (macOS only for now).

Shipped in v0.0.2:
- Auto-load for `skills/` and `policies/` into the system prompt.
- Inline editor in the preview pane.
- Skill on/off toggles (UI + `.disabled` file).
- Requests tracking (folders + seed policy + sidebar + mark-done).

Shipped in v0.0.3:
- `~/enough/` as the install dir.
- `bootstrap.sh` guided installer.
- Global defaults under `~/enough/defaults/`; symlinks + "customize for
  this project" UI affordance.
- `~/enough/infoworld/` as per-user shared knowledge store, symlinked into
  projects.
- Read allowlist policy; absolute-path reads now allowed inside the
  allowlisted prefixes.
- Kernel-level guards: refuse to launch inside `~/enough/`, block writes to
  `.rness/requests/done/`, detect slug-drift duplicate request files.

---

## Development

Decision records, process docs, and session checkpoints for each build live
under [`dev/.amanuensis/`](dev/.amanuensis). They capture the what/why of
every non-trivial choice since v0.01 — helpful for understanding why things
are the way they are and when something was a deliberate constraint vs. a
gap to fill.

```bash
uv sync               # create .venv, install deps
uv run enough --help
```

No tests yet. Each version has been verified via manual end-to-end smoke
against a running llama-server + browser session.

---

## License

Apache 2.0. See [LICENSE](LICENSE).
