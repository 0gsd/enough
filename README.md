# enough

A **paradigmless personal computer harness** powered by a local LLM. It ships
empty. You make it useful by defining your own paradigms, workflows, agents,
and knowledge stores through plain-text conventions in a `.rness/` directory.
The model helps you do this from the very first message.

One `enough` instance = one agent = one context = one `.rness/` directory.
Multi-agent? Run multiple instances in different directories. There is no
built-in orchestrator, no message bus, no agent framework. The filesystem is
the coordination surface.

Status: **v0.0.2 — pre-alpha.** The architecture is in place; the ideas on top
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

./your-project/
├── .rness/           ← agent config, paradigms, skills, knowledge
│   ├── AGENT.md              identity
│   ├── MOTIVATION.md         evolving drive
│   ├── paradigms/default.md  interaction conventions
│   ├── skills/               user-added (SKILL.md or flat .md);
│   │                         toggle on/off in the UI
│   ├── routines/             user-added
│   ├── policies/
│   │   └── requests.md       seed: long-horizon request tracking
│   ├── requests/             active request .md files
│   │   └── done/             moved here when user clicks "mark done"
│   ├── knowledge/
│   │   ├── user-profile.md   what the agent knows about you
│   │   └── session-logs/     one .md per day, full transcript
│   └── models/providers.md
├── infoworld/        ← grounded truth store
│   ├── wiki/                 wikipedia dumps (user-populated)
│   └── personal/             your own reference material
└── [whatever else you're working on]
```

---

## Prerequisites

- **Python 3.11+**
- **llama-server** (from [llama.cpp](https://github.com/ggml-org/llama.cpp))
  listening on `http://localhost:8080` with a GGUF model loaded.
  Recommended model: [ggml-org/gemma-4-26B-A4B-it-GGUF][g4] Q4_K_M — a 26B MoE
  with only 4B active parameters, ~16 GB on disk, runs well on Apple Silicon.
- [`uv`](https://docs.astral.sh/uv/) or `pip` for installing.

[g4]: https://huggingface.co/ggml-org/gemma-4-26B-A4B-it-GGUF

---

## Quick start

```bash
# 1. get llama-server on PATH (macOS homebrew shown; see llama.cpp README for others)
brew install llama.cpp

# 2. download a GGUF somewhere on disk, e.g.:
#    ~/models/gemma-4-26B-A4B-it-Q4_K_M.gguf

# 3. clone and install enough
git clone git@github.com:0gsd/enough.git
cd enough
uv sync                    # or: pip install -e .

# 4. start llama-server (the bundled toggle script handles the flags)
MODEL=~/models/gemma-4-26B-A4B-it-Q4_K_M.gguf ./llama_server.sh start

# 5. launch enough in any project directory
cd ~/my-new-project
uv run --project /path/to/enough enough        # or just `enough` if installed globally
```

`enough` will:
1. Create a `.rness/` and `infoworld/` skeleton if they don't exist.
2. Open a browser tab at <http://127.0.0.1:3456>.
3. Put you face-to-face with a blank-slate agent who wants to help you define
   what this instance of `enough` is for.

### Flags

```
enough [--dir PATH] [--port N] [--llm-url URL] [--no-browser]
```

| flag | default | notes |
|---|---|---|
| `--dir` | cwd | project directory |
| `--port` | `3456` | web UI port |
| `--llm-url` | `http://localhost:8080` | where llama-server is |
| `--no-browser` | off | don't auto-open |

---

## `./llama_server.sh` — the bundled toggle

Optional convenience. Configurable via env vars:

```bash
MODEL=~/models/something.gguf ./llama_server.sh start    # start
./llama_server.sh stop                                    # stop
./llama_server.sh status                                  # status + health
./llama_server.sh logs                                    # tail log
./llama_server.sh                                         # toggle
```

Defaults: `HOST=127.0.0.1 PORT=8080 NGL=99 CTX=8192`. Override any by
exporting. Runtime state (pid, log) goes into the gitignored `.llama-server/`
next to the script.

If you'd rather run llama-server yourself, the canonical invocation is:

```bash
llama-server -m <path.gguf> --host 127.0.0.1 --port 8080 -ngl 99 -c 8192 --jinja
```

The `--jinja` flag is important — it makes llama-server use the chat template
embedded in the GGUF, which `enough` relies on.

---

## The `.rness/` directory

Everything about your agent's identity, behavior, and memory lives here as
plain text. The system prompt is **re-assembled from these files on every
request**, so edits take effect on the very next message — no restart needed.

- `AGENT.md` — who the agent is. Initially blank-slate.
- `MOTIVATION.md` — accumulated learning. The agent proposes updates at
  session end; you approve or edit before saving.
- `paradigms/default.md` — the active interaction paradigm. Session
  structure, output conventions, archival policy, security posture. Make more
  paradigms as you need them; for v0.02 only `default.md` is loaded.
- `skills/` — drop-in skills. Two layouts supported:
  `.rness/skills/<name>/SKILL.md` (folder-based, Claude Code convention) or
  `.rness/skills/<name>.md` (flat). Auto-loaded into the system prompt.
  Toggle on/off in the sidebar without moving files; disabled skills are
  listed in `.rness/skills/.disabled`.
- `policies/` — policy files auto-loaded into the system prompt under a
  `# Policies` section. Ships with `requests.md` (see below); add your own
  conventions here.
- `requests/` + `requests/done/` — long-horizon work tracking. The agent
  creates an `.md` file per complex multi-step request, maintains it across
  turns (sub-requests → tasks → end output), and the user clicks "mark done"
  in the preview pane to move it into `done/`. See the seed policy.
- `routines/` — user-populated, not auto-loaded.
- `knowledge/session-logs/` — one `.md` per day, every exchange appended,
  including tool calls.
- `knowledge/user-profile.md` — what the agent knows about you. Starts empty.
- `models/providers.md` — model/provider notes.

Optional:
- `INTENTION.md` — if you put one here, it's injected into the system prompt
  as the current session intention.

### Edit any of these in-browser

Click a file in the sidebar → the preview pane opens. Hit the **edit**
button in the preview chrome → inline textarea with save / cancel. All
edits write straight to disk and take effect on the next message. You can
still use your normal editor; it's just a convenience for quick paradigm
tweaks.

---

## `infoworld/` — grounded knowledge store

```
infoworld/
├── wiki/       ← wikipedia dumps, offline reference
└── personal/   ← your own docs, bibles, notes, whatever
```

For v0.01 this is **just a directory convention**. The system prompt tells the
agent to `grep` here before relying on training data. Smarter indexing /
retrieval is a future-version concern.

### Populating `infoworld/wiki/`

Two common paths:

1. **Kiwix ZIM extraction.** Download a `.zim` from
   [kiwix.org](https://kiwix.org/), then use
   [`zimdump`](https://github.com/openzim/zim-tools) to extract plaintext.
2. **Wikipedia dumps + WikiExtractor.** Grab `enwiki-latest-pages-articles.xml.bz2`
   from <https://dumps.wikimedia.org/enwiki/> and run
   [WikiExtractor](https://github.com/attardi/wikiextractor) for plaintext
   output in a nested directory structure.

Then drop the plaintext into `infoworld/wiki/`. The agent will find it via
`shell` + `grep`.

---

## Tools the agent has

The model gets three tools, described in its system prompt:

- `read_file` — read a text file, relative path only.
- `write_file` — write a text file, relative path only, `mkdir -p` behavior.
- `shell` — run any shell command in the project directory.

Rules:
- Paths are relative to the project directory. Absolute paths and `../`
  traversal are rejected.
- Shell has no sandbox in v0.01. Everything is logged.
- Tool loop is capped at **10 iterations per user turn.**

Tool calls use an XML-ish tag format the model emits inline; the server parses
them with regex (the model's output isn't guaranteed to be well-formed XML, so
we don't use an XML parser). See
[`enough/prompt.py`](enough/prompt.py) for the exact instructions.

---

## What v0.02 *doesn't* do

Deliberate omissions — see [bootstrap spec](dev/) for the full thinking:

- No multi-agent coordination (one instance = one agent).
- No MOTIVATION auto-update (model proposes; you apply).
- No RAG / embedding / vector store. The model greps.
- No authentication. Localhost only.
- No persistent conversation history across restarts (session logs remain).
- No paradigm switching mid-session.

Added in v0.02 (see `dev/.amanuensis/`):
- Auto-load for `skills/` and `policies/` into the system prompt.
- Inline editor in the preview pane.
- Skill on/off toggles (UI + `.disabled` file).
- Requests tracking (folders + seed policy + sidebar + mark-done).

---

## Development

Decision records, process docs, and session checkpoints for this build live
under [`dev/.amanuensis/`](dev/.amanuensis). They capture the what/why of
every non-trivial choice during the v0.01 build, for future-self or
contributors.

```bash
uv sync               # create .venv, install deps
uv run enough --help
```

No tests yet. v0.0.1 was verified via manual end-to-end smoke against a
running llama-server.

---

## License

Apache 2.0. See [LICENSE](LICENSE).
