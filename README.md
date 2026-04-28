# enough

A **paradigmless personal computer harness** powered by a local LLM that
runs entirely on your Mac. Your conversations stay on your machine. Your
files stay on your machine. The model that's answering you also stays on
your machine — there's no API call to the cloud, no account to sign up
for, no subscription.

It ships almost empty. You make it useful by enabling skills, activating
roles, customizing paradigms, and giving it long-running tasks to track.
The agent helps you do all of this from your very first message.

> **Status:** v0.0.9 — pre-alpha but usable. Mac-only for now. The
> architecture is settled; the ideas on top of it are up to you.

---

## Who is this for?

If you're comfortable opening a Terminal window once to install something,
and you use Word, Google Docs, or similar tools daily, you're the
audience. Cloud LLM products feel scary or wasteful or both — `enough` is
the local-first counterpoint. No telemetry, no logs leaving your machine,
no model weights you don't own a copy of.

You don't need to be a programmer. You don't need to know what an LLM is
"under the hood." You do need to be willing to read a markdown file or
two and edit text in your favorite text editor (or in `enough`'s built-in
preview pane).

---

## What you'll need

- A **Mac** (Apple Silicon or recent Intel; Linux/Windows support is on
  the roadmap, not here yet)
- About **5–30 GB of free disk space**, depending on which AI model you
  pick during install (the smallest one is ~5 GB; the biggest is ~16 GB)
- About **10 minutes** for the install
- Comfort with running **one Terminal command** to get started

The installer takes care of everything else: it'll ask before installing
anything, and it explains what each step does as it runs.

---

## Installing it

Open Terminal and paste:

```bash
git clone https://github.com/0gsd/enough.git /tmp/enough-seed
cd /tmp/enough-seed
bash bootstrap.sh
```

The installer walks through nine steps in order, asking permission and
explaining each one:

1. Confirms you're on a Mac
2. Checks for Homebrew (the standard Mac package manager) — installs if missing
3. Installs the supporting tools: `llama.cpp` (the local AI runtime),
   `uv` (Python environment manager), `tor` (optional privacy proxy), and
   `whisper-cpp` (for voice input)
4. Clones `enough` itself into `~/enough/` (your home folder)
5. Sets up the Python environment
6. Lets you pick which AI model(s) to download — pick **tier 1** if you
   want the lightest setup, **tier 4** if you want all four models
7. Downloads a voice-recognition model (~140 MB) for the mic button
8. Installs an `enough` command on your PATH so you can run it from any folder
9. Tells you what to do next

After install, you can delete `/tmp/enough-seed/`. Your install lives at
`~/enough/`.

### The "open enough" launcher

There's also a double-clickable launcher in `shortcuts/`:
`enough-on.command` starts the local AI server and opens `enough` in your
browser, all from a Finder double-click. See [`shortcuts/README.md`](shortcuts/README.md)
for setup.

---

## Your first time

Open Terminal, navigate to any folder you want to work in (or create a
new one), and run:

```bash
enough
```

Your browser will open at `http://127.0.0.1:3456` showing a chat
interface, a file sidebar, and a model badge in the top-right.

The first time you launch in a folder, `enough` creates a hidden
`.rness/` directory in it — that's where the agent's identity, memory,
and configuration live. Type a message to start. The agent will likely
ask you what kind of work you want to do here and what personality it
should have.

That's it. That's the whole loop.

---

## The pieces

`enough` has a small set of concepts. Each is a markdown file or folder
you can read, edit, or toggle. Here's what they are and how to use them.

### Projects

A **project** is just a folder on your Mac. When you `cd` into it and run
`enough`, that folder becomes the agent's home: it has its own
identity (`AGENT.md`), its own running notes (`MOTIVATION.md`), its own
list of in-progress jobs (`.requests/`), its own session logs.

Run `enough` in `~/Documents/my-novel/` and it's your novelist agent. Run
it in `~/Documents/research/`, different folder, different agent, fresh
brain.

**One folder = one agent.** No multi-agent orchestration, no shared
state. If you want a different agent, go to a different folder.

The hidden `.rness/` directory inside your project is where all the
agent's stuff lives. Most of it you'll never touch directly — the sidebar
surfaces what matters.

### Skills

A **skill** is a packaged capability you can toggle on or off — like a
Word add-in or a Chrome extension. Each skill is a folder with a
`SKILL.md` describing what it does, and (optionally) helper scripts.

`enough` ships with four skills out of the box:

- **`docs-maintainer`** — reads codebases and writes accurate docs.
- **`irefy`** ("I read everything for you") — produces a one-page
  analytical digest of any long document.
- **`the-internet`** — fetches web pages through Tor for anonymized
  reading.
- **`wiki-links`** — historical fiction research helper.

**How to use them:** open the sidebar (left side of the window), expand
the **active skills** section. Each skill has a circle next to its name —
filled = on, empty = off. Click to toggle. Changes apply on your very
next message.

Skills default to **off** so the agent's system prompt stays small and
fast. Turn on only what you need for the current job.

To add a new skill globally, drop a folder into
`~/enough/defaults/skills/`. It'll show up (default-off) in every
project on your next `enough` launch.

### Roles (consultants)

A **role** is a different kind of voice the agent can consult — an
advisor with their own values, blind spots, and ways of pushing back.
The agent itself is the orchestrator; roles are voices it can summon for
a second opinion.

`enough` ships with one role:

- **`open-skeptic`** — an "enlightenable doomer." Skeptical that AI
  should be replicating human judgment, relationships, or care, but
  enthusiastic about AI as a productivity multiplier in its lane.
  Specific, persuadable, non-preachy. Useful when you want a sanity check
  on whether you're asking AI to do something it shouldn't.

**How to use them:** in the sidebar, expand the **roles (consultants)**
section. Toggle on a role to make its perspective available to the
orchestrator.

Once active, you can prompt the agent like:

> "What would open-skeptic say about this plan?"

Or just let the agent volunteer their perspective on its own — it knows
the active roles are available as advisors.

To add new roles globally, drop a folder containing `AGENT.md` and
`MOTIVATION.md` into `~/enough/defaults/roles/`.

### Paradigms

A **paradigm** is the agent's "operating manual" — how it structures
sessions, what its security posture is, how it handles requests, when to
write checkpoints. It's a single markdown file the agent reads every
turn.

`enough` ships with one paradigm: **`default.md`**. It covers things like:

- Show commands before running them
- Don't write outside the project folder unless the user opts in
- Cache public-domain web content into the project (with manifest)
- Don't auto-update memory files; propose changes for the user to apply

**How to use it:**

- For **most users**, don't touch it — the default is sensible.
- To **see what it says**, click `.rness/paradigms/default.md` in the
  sidebar. It opens in the preview pane.
- To **change it for one project only**: in the preview pane, click
  *"customize for this project"*. The default symlink is replaced with a
  project-local copy you can edit.
- To **change it for all projects**, edit `~/enough/defaults/paradigms/default.md`
  directly. Every project still using the default symlink picks up the
  change on the next message.

Power users can author multiple paradigm files and switch between them.
Most won't need to.

### Requests (long-horizon job tracking)

When you ask the agent to do something that takes more than one
conversation turn — write a 50-page report, build a piece of software,
research a topic across many sources — it creates a **request file**
under `.rness/.requests/`. This is its working memory for the job.

The file tracks:

- The original ask, paraphrased
- Sub-requests (parts of the work)
- Tasks (atomic, checkbox-style)
- Progress checkpoints — notes the agent leaves itself
- A continuation block (used when the conversation needs to reset
  mid-job; see auto-reset below)

**How to use them:**

- The agent creates and updates them automatically.
- The sidebar's **requests** section lists active requests, newest first.
  Click any one to see it in the preview pane.
- When the agent says it's done with a request, the preview pane gets a
  **mark done** button. One click moves the file to
  `.rness/.requests/done/`. That click is your approval — the agent
  can't move it itself.

This is how `enough` survives losing its memory mid-job. (See auto-reset.)

### Models and the token gauge

The little badge in the top-right (e.g., `Q35-09 · 16k`) shows which AI
model is loaded and how much "memory" (context window) it has. Click the
badge to open the **model & context** modal.

In there you can:

- **Switch models** — pick a different one and click *Apply & Restart*.
  The smaller models are faster and use less RAM; the bigger ones are
  smarter but slower.
- **Change the context window size** — bigger means the agent can
  remember more before it starts forgetting; smaller means less RAM and
  faster.
- **Watch the token-pressure gauge** — a colored bar that fills up as
  the conversation grows. Green is fine, yellow is "getting full," red
  is "about to overflow."
- **Toggle auto-reset** — see below.

Right next to the model badge is a smaller version of the token gauge,
always visible while you work. Hover for details.

### Auto-reset (for very long jobs)

Local AI models have a finite memory. When you push past it, you get an
error and the conversation breaks. This is annoying. `enough` has a
feature to handle it gracefully:

When you turn on **auto-reset** (in the model modal), the agent watches
its own token pressure. When it crosses the threshold (default 75%), it:

1. Pauses to write a fresh "continuation" note in its active request
   file — what it just did, what to do next, key state to remember
2. Wipes its conversational memory
3. Reads the request file again to remind itself
4. Continues the work

You see this happen in the chat pane: a gray banner explains it,
followed by the checkpoint exchange, a divider, then a fresh start where
the agent picks up the task. No data loss — the request file on disk is
the durable memory.

This is **off by default** because it's experimental. Try it on
medium-sized tasks first.

### infoworld (your private knowledge library)

`infoworld/` is a folder shared across all your `enough` projects. The
agent treats it as an "offline reference library" — it'll grep here
before relying on its training data.

It lives at `~/enough/infoworld/` and is symlinked into every project
as `infoworld/`. Three subfolders:

- `wiki/` — for Wikipedia dumps (you populate)
- `personal/` — your own notes, drafts, books, references
- `public/` — material you'd be OK sharing or publishing

**How to use it:** drop any plain text or markdown into the appropriate
subfolder. The agent will find it via `grep` when relevant. No indexing,
no embeddings, no setup — just text on disk.

To populate `wiki/` with Wikipedia content, see *Populating infoworld*
in [`docs/`](docs/) (or just paste Wikipedia article text into
`infoworld/personal/` for a lighter setup).

### Allowlists

`enough` is privacy-conservative by default. The agent can read and
write inside your project folder freely, but reaching outside it — onto
your wider Mac, or out to the internet — requires explicit permission.

These permissions live in `.rness/policies/allowlists.md` and have three
sections:

- **File-read prefixes** — paths the agent may read (default: just
  `~/enough/` so it can see its own defaults)
- **File-read-write prefixes** — paths the agent may also write to
  (default: empty — opt in deliberately)
- **Internet domains** — websites the agent may fetch from (default:
  Project Gutenberg, Wikipedia, Wikisource, the Internet Archive,
  Standard Ebooks — places generally safe for grabbing public-domain or
  CC-licensed text)

**How to use them:**

- Click `.rness/policies/allowlists.md` in the sidebar to see the
  current rules.
- Add a path or domain by editing the file (use *customize for this
  project* to make a project-local copy first).
- The agent will tell you when it tries to reach somewhere not on the
  list and ask whether to add it.

The internet allowlist is **guidance**, not a hard wall — the agent can
technically curl anywhere via its `shell` tool. The list shapes what it
will *willingly* fetch without asking.

### Session logs

Every conversation is automatically saved to
`.rness/knowledge/session-logs/<date>.md` — one file per day. You don't
need to do anything; the harness writes them. The agent can read them
later if it needs to remember a conversation from yesterday.

---

## What the agent can actually do (its tools)

The agent has three tools. They're how it does anything that isn't just
talking to you.

- **`read_file`** — reads a text file. By default, restricted to your
  project folder. Absolute paths (e.g. `~/enough/...`) work only if
  they're on the file-read allowlist.
- **`write_file`** — writes a text file. Same restrictions, plus the
  stricter file-read-write list for absolute paths. Can't write to
  `.rness/.requests/done/` (only the *mark done* button does that).
- **`shell`** — runs any shell command in your project folder. This is
  the deliberate "nuclear option" — it can in principle do anything
  your terminal can do. The agent is instructed to use it sparingly and
  show you what it's doing.

The tool loop is capped at 50 calls per turn, so a runaway agent can't
loop forever.

---

## A few tips for non-technical users

- **The "agent" is just text in, text out.** It's a model running locally,
  not a service. When you close `enough`, it stops. When you open it, it
  starts fresh (but reads its memory files).
- **Your work is in plain files.** Even the agent's "memory" is text.
  Open `.rness/AGENT.md` in TextEdit or any editor — that's literally
  what the agent thinks of itself.
- **You can't "break" things in a serious way.** The worst case is your
  project folder gets messy. `enough` doesn't touch other parts of your
  Mac without your explicit allowlist.
- **The first conversation in a new project is meta.** The agent will
  ask what kind of work you want to do. Tell it. That conversation will
  shape the agent's identity in `AGENT.md`.
- **If something feels wrong, type `/reset` in the chat.** It clears the
  conversation memory but keeps everything on disk. Then ask again.
- **The token gauge tells you how "full" the agent's brain is.** When
  it's red, the conversation is about to break. Either reset or turn on
  auto-reset.

---

## Customizing: global vs. per-project

`enough` is built on a "default + override" pattern.

**Global:** edit `~/enough/defaults/...` and every project that hasn't
been customized yet picks up the change. This is how you'd, for
example:

- Change every project's default paradigm
- Add a new skill available everywhere
- Add a new role available everywhere
- Update the read allowlist for every project

**Per-project:** in the preview pane, click *customize for this project*
on a symlinked file. That replaces the global symlink with a local copy
you can edit independently. Other projects keep using the global
default.

Symlinked files render *italic + muted* in the file tree. Project-local
copies render normally.

---

## What `enough` deliberately doesn't do

These are choices, not gaps:

- **No multi-agent orchestration.** One folder, one agent. If you want
  multiple agents working together, run multiple `enough` instances and
  let them coordinate through the filesystem.
- **No cloud anything.** No telemetry, no remote API, no model weights
  you don't own.
- **No authentication.** Localhost-only, single-user.
- **No automatic memory updates.** The agent proposes changes to
  `MOTIVATION.md`; you apply them.
- **No vector store / RAG.** The agent uses `grep`. This is fine at
  personal scale and avoids a whole category of complexity.
- **No paradigm switching mid-session** (yet).

---

## Customizing the install via Git

`~/enough/` is a clone of `github.com/0gsd/enough`. To pull in upstream
updates without losing your customizations, fork the repo on GitHub and
point your install at your fork:

```bash
cd ~/enough
git remote set-url origin git@github.com:YOU/enough.git
git remote add upstream git@github.com:0gsd/enough.git
git pull upstream main
```

---

## Development

The code is small and readable. Roughly:

- `enough/server.py` — FastAPI app: chat, SSE streaming, file tree, model modal, auto-reset orchestration
- `enough/prompt.py` — assembles the system prompt from `.rness/` on every turn
- `enough/tools.py` — `read_file` / `write_file` / `shell`, plus path safety
- `enough/skeleton.py` — creates `.rness/` for new projects, syncs globals on every launch
- `enough/llm.py` — talks to llama-server (local LLM via OpenAI-compatible API)
- `enough/supervisor.py` — manages the llama-server subprocess
- `enough/static/index.html` — the entire UI (htmx + vanilla JS)
- `defaults/` — the shipped templates that get copied or symlinked into every new project

To work on it:

```bash
git clone https://github.com/0gsd/enough.git
cd enough
uv sync
uv run enough --help
```

There's no automated test suite yet. Each release is verified via manual
end-to-end smoke tests against a running llama-server + browser session.

---

## License

Apache 2.0. See [LICENSE](LICENSE).

Third-party content (the bundled `defaults/skills/` packages) carries
its own licenses — see [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
