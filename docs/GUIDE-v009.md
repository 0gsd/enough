# enough — Complete User Guide (v0.0.9)

This is the in-depth guide to using **enough** at the v0.0.9 release. For
the project overview and philosophy, see the [README](../README.md). For
populating `infoworld/` with a large Wikipedia corpus, see
[LOCAL-WIKIPEDIA.md](LOCAL-WIKIPEDIA.md).

`enough` is a **paradigmless personal computer** powered by a local LLM
that runs entirely on your Mac. Your conversations stay on your machine.
Your files stay on your machine. The model that's answering you also
stays on your machine — there's no API call to the cloud, no account to
sign up for, no subscription.

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
- About **8–35 GB of free disk space**, depending on which AI model you
  pick during install (the smallest LLM is ~5 GB; the biggest is ~16 GB),
  plus ~3 GB if you opt to install the offline-translation model
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

The installer walks through ten steps in order, asking permission and
explaining each one:

1. Confirms you're on a Mac
2. Checks for Homebrew (the standard Mac package manager) — installs if missing
3. Installs the supporting tools: `llama.cpp` (the local AI runtime),
   `uv` (Python environment manager), `tor` (privacy proxy for
   off-allowlist web fetches), and `whisper-cpp` (for voice input)
4. Clones `enough` itself into `~/enough/` (your home folder)
5. Sets up the Python environment (this also installs the offline
   translation libraries: `ctranslate2`, `sentencepiece`, `huggingface_hub`)
6. Lets you pick which AI model(s) to download — pick **tier 1** if you
   want the lightest setup, **tier 4** if you want all four models
7. Downloads a voice-recognition model (~140 MB) for the mic button
8. Optionally downloads the offline translation model
   (MADLAD-400-3B-MT, ~3 GB). Powers the `translator` skill — translation
   across ~419 languages, fully offline. You can defer this and the
   skill will download the model on first use instead
9. Installs an `enough` command on your PATH so you can run it from any folder
10. Tells you what to do next

After install, you can delete `/tmp/enough-seed/`. Your install lives at
`~/enough/`.

### The "open enough" launcher

There's also a double-clickable launcher in `shortcuts/`:
`enough-on.command` starts the local AI server and opens `enough` in your
browser, all from a Finder double-click. See [`shortcuts/README.md`](../shortcuts/README.md)
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

The first time you launch in a folder, `enough` creates an `rness/`
directory in it — that's where the agent's identity, memory, and
configuration live. Type a message to start. The agent will likely ask
you what kind of work you want to do here and what personality it should
have.

That's it. That's the whole loop.

---

## The pieces

`enough` has a small set of concepts. Each is a markdown file or folder
you can read, edit, or toggle. Here's what they are and how to use them.

### Projects

A **project** is just a folder on your Mac. When you `cd` into it and run
`enough`, that folder becomes the agent's home: it has its own identity
(`AGENT.md`), its own running notes (`MOTIVATION.md`), its own profile
of how this project gets worked on (`knowledge/project-profile.md`), its
own list of in-progress jobs (`requests/`), its own session logs.

Run `enough` in `~/Documents/my-novel/` and it's your novelist agent. Run
it in `~/Documents/research/`, different folder, different agent, fresh
brain.

**One folder = one agent.** No multi-agent orchestration, no shared
state. If you want a different agent, go to a different folder.

The `rness/` directory inside your project is where all the agent's
stuff lives. Most of it you'll never touch directly — the sidebar
surfaces what matters.

### The agent's living memory: `project-profile.md`

`rness/knowledge/project-profile.md` is the agent's per-project working
memory. It's where the agent records observations about how *this
project* gets worked on — your preferences as it's seen them in this
folder, recurring people/files, conventions you've adopted, open
threads it expects to come back to.

This file is **piped into the system prompt on every turn**, so anything
the agent writes there is in its working memory next message — without
having to remember to `read_file` it. The
`profile-maintenance.md` policy tells the agent when to update it
(after observing a clear preference, when a pattern repeats, after
finishing a multi-turn job) and what *not* to put in (vague labels,
demographics, the full transcript).

The profile is **per-project, not per-user**: a novel-writing project
profiles you differently than an infra-debugging one. Different folder,
different brain, different profile.

You can edit `project-profile.md` yourself any time — the agent reads
the file fresh every turn, so your edits land immediately.

### Skills

A **skill** is a packaged capability you can toggle on or off — like a
Word add-in or a Chrome extension. Each skill is a folder with a
`SKILL.md` describing what it does, and (optionally) helper scripts.

`enough` ships with four skills out of the box:

- **`irefy`** ("I read everything for you") — produces a one-page
  analytical digest of any long document. Two scored indices (Conveyance
  Success and Conveyance Evil), three lenses (Intention, Method,
  Verdict). Use on Deep Research reports, blog posts, papers, anything.
- **`memoir-dialectic`** — patient, multi-session collaborator for
  planning and optionally drafting a memoir. The folder on disk is the
  memory; you can disappear for weeks and pick up where you left off.
- **`skillmd-scan`** — security and epistemic auditor for skill
  packages. Scans a skill's `SKILL.md`, references, and scripts for
  prompt-injection patterns and other risks before you install it.
- **`translator`** — offline machine translation across ~419 languages,
  powered by Google's MADLAD-400-3B-MT (Apache 2.0). After the one-time
  ~3 GB model download, translation works fully offline — no API call,
  no account, no rate limit. Routing is described in the companion
  `translation` paradigm.

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

`enough` ships with three paradigms:

**`default.md`** — the base interaction paradigm. Covers things like
showing commands before running them, not writing outside the project
folder unless you opt in, caching public-domain web content into the
project, and proposing rather than auto-applying changes to identity
files.

**`translation.md`** — declares offline translation as a first-class
capability. Tells the agent when to route requests to the `translator`
skill, which model variant to pick (3B default vs. opt-in 7B vs.
license-gated NLLB-200), how to fall back when MADLAD struggles on
low-resource pairs, and how to consult the bundled Rosetta primers at
`rness/knowledge/rosetta-primers/` for ground-truth verification.

**`workflow-design.md`** — the meta-paradigm for *building* enough
itself: adding skills, authoring roles, refining policies, editing
`rness/AGENT.md` or `rness/MOTIVATION.md`. The agent switches into this
one when you ask it to help you build or change part of its own
workflow.

**How to use it:**

- For **most users**, don't touch it — the default is sensible.
- The agent will **switch paradigms on its own** when your request
  better fits another one (e.g. you start a translation job; you ask
  to build a new skill). The active paradigm shows in the sidebar
  under **paradigm**.
- To **see what one says**, click `rness/paradigms/default.md` in the
  sidebar. It opens in the preview pane.
- To **change it for one project only**: in the preview pane, click
  *"customize for this project"*. The default symlink is replaced with a
  project-local copy you can edit.
- To **change it for all projects**, edit
  `~/enough/defaults/paradigms/default.md` directly. Every project
  still using the default symlink picks up the change on the next
  message.

### Requests (long-horizon job tracking)

When you ask the agent to do something that takes more than one
conversation turn — write a 50-page report, build a piece of software,
research a topic across many sources, run a skill across a long document
— it creates a **request file** under `rness/requests/`. This is its
working memory for the job.

The file tracks:

- The original ask, paraphrased
- Sub-requests (parts of the work)
- Tasks (atomic, checkbox-style)
- Progress checkpoints — notes the agent leaves itself
- A continuation block (used when the conversation needs to reset
  mid-job; see auto-reset below)

**You don't have to say "track this as a request."** The agent
recognizes the shape of a multi-step task on its own: skill
invocations, "use X on this file," "translate this document,"
"research X and write a synthesis." For one-shot Q&A and single file
edits, no request file is created.

**How to use them:**

- The agent creates and updates them automatically.
- The sidebar's **requests** section lists active requests, newest first.
  Click any one to see it in the preview pane.
- When the agent says it's done with a request, the preview pane gets a
  **mark done** button. One click moves the file to
  `rness/requests/done/`. That click is your approval — the agent
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
  is "about to overflow." Updates every turn (including mid-tool-loop;
  if the model doesn't ship a usage payload, a character-based estimate
  drives the gauge so it never sits frozen at zero).
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
   (the agent is explicitly required to call `write_file` here, so the
   note actually lands on disk)
2. Wipes its conversational memory
3. Reads the request file again to remind itself
4. Continues the work

You see this happen in the chat pane: a gray banner explains it,
followed by the checkpoint exchange, a divider, then a fresh start
where the agent picks up the task. No data loss — the request file on
disk is the durable memory.

This is **off by default** because it's experimental. Try it on
medium-sized tasks first.

### The broker (tool gateway)

Every tool call the agent makes flows through a layer called the
**broker**. The broker enforces allowlists, routes web fetches (direct
for trusted domains, via Tor for everything else), converts fetched
HTML to markdown, caches fetched documents, and writes a journal of
every action.

Click the **broker** button in the top nav to open the broker pane.
You'll see toggles for:

- **Trace logging** — every brokered tool call gets a markdown entry
  in `rness/knowledge/session-logs/<date>-broker.md`. The journal is
  your accountability trail; turn it off only for a quieter
  filesystem.
- **Per-tool brokering** — `read_file`, `write_file`, and `shell` each
  have a toggle that controls whether the broker logs them.
  Allowlist enforcement stays on regardless; the toggle is purely
  about journaling overhead.
- **`fetch_url` enabled** — the canonical web-fetch tool. When off,
  the agent falls back to `curl` via shell — no Tor, no markdown
  conversion, no caching.
- **`fetch_url`: Tor for off-allowlist domains** — when on (default),
  off-allowlist domains route through the local Tor proxy
  (`127.0.0.1:9050`) for anonymization. Turn it off to deny
  off-allowlist fetches outright.
- **`fetch_url`: cache + markdown convert** — fetched HTML gets
  pandoc-converted to markdown and cached under
  `rness/io/input/<timestamp>-<hash>-<slug>.md`, with a row in
  `_broker-index.md`. The agent gets a short preview instead of the
  full body, saving context window space.

From the broker pane you can also **open today's broker journal**
directly in the preview pane.

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

To populate `wiki/` with Wikipedia content, see
[LOCAL-WIKIPEDIA.md](LOCAL-WIKIPEDIA.md) (or just paste Wikipedia article
text into `infoworld/personal/` for a lighter setup).

### Allowlists

`enough` is privacy-conservative by default. The agent can read and
write inside your project folder freely, but reaching outside it — onto
your wider Mac, or out to the internet — requires explicit permission
(or, for the internet, anonymization via Tor).

These permissions live in `rness/policies/allowlists.md` and have three
sections:

- **File-read prefixes** — paths the agent may read (default: just
  `~/enough/` so it can see its own defaults)
- **File-read-write prefixes** — paths the agent may also write to
  (default: empty — opt in deliberately)
- **Internet domains** — websites the broker fetches **directly**
  (default: Project Gutenberg, Wikipedia, Wikisource, Wikimedia
  Commons, the Internet Archive, Standard Ebooks — places generally
  safe for grabbing public-domain or CC-licensed text). Off-allowlist
  domains aren't rejected — they're routed through Tor.

**How to use them:**

- Click `rness/policies/allowlists.md` in the sidebar to see the
  current rules.
- Add a path or domain by editing the file (use *customize for this
  project* to make a project-local copy first).
- To **block** off-allowlist internet fetches outright, open the
  broker pane and turn off "Tor for off-allowlist domains" — the
  agent will then get a polite denial when it tries to fetch a
  non-allowlisted domain.

### Session logs

Every conversation is automatically saved to
`rness/knowledge/session-logs/<date>.md` — one file per day, with a
companion `<date>-broker.md` for tool-call journaling. You don't need
to do anything; the harness writes them. The agent can read them later
if it needs to remember a conversation from yesterday.

---

## What the agent can actually do (its tools)

The agent has four tools. They're how it does anything that isn't just
talking to you.

- **`read_file`** — reads a text file. By default, restricted to your
  project folder. Absolute paths (e.g. `~/enough/...`) work only if
  they're on the file-read allowlist.
- **`write_file`** — writes a text file. Same restrictions, plus the
  stricter file-read-write list for absolute paths. Can't write to
  `rness/requests/done/` (only the *mark done* button does that).
- **`shell`** — runs any shell command in your project folder. This is
  the deliberate "nuclear option" — it can in principle do anything
  your terminal can do. The agent is instructed to use it sparingly and
  show you what it's doing.
- **`fetch_url`** — the canonical way to read from the web. Routes
  through the broker: allowlisted domains direct, others via Tor.
  Converts HTML to markdown via pandoc and caches under
  `rness/io/input/`. The agent gets a short preview + cache path; the
  full document doesn't go in the context window.

The tool loop is capped at 50 calls per turn, so a runaway agent can't
loop forever.

---

## A few tips for non-technical users

- **The "agent" is just text in, text out.** It's a model running locally,
  not a service. When you close `enough`, it stops. When you open it, it
  starts fresh (but reads its memory files).
- **Your work is in plain files.** Even the agent's "memory" is text.
  Open `rness/AGENT.md` in TextEdit or any editor — that's literally
  what the agent thinks of itself.
- **You can't "break" things in a serious way.** The worst case is your
  project folder gets messy. `enough` doesn't touch other parts of your
  Mac without your explicit allowlist.
- **The first conversation in a new project is meta.** The agent will
  ask what kind of work you want to do. Tell it. That conversation will
  shape the agent's identity in `AGENT.md` and seed
  `project-profile.md`.
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
- Add a new policy that should apply everywhere

When the project's `rness/` is missing defaults that have been added to
`~/enough/defaults/` since this project was created, the empty-state
chat banner shows a notice and the agent's system prompt gets an "FYI"
about it. Type `/update-enough` in the chat to apply.

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
- **No automatic memory updates *for identity files*.** The agent
  proposes changes to `AGENT.md` and `MOTIVATION.md`; you apply them.
  (The exception is `project-profile.md` — that's living per-project
  memory the agent maintains itself per the `profile-maintenance`
  policy.)
- **No vector store / RAG.** The agent uses `grep`. This is fine at
  personal scale and avoids a whole category of complexity.

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

- `enough/server.py` — FastAPI app: chat, SSE streaming, file tree,
  model modal, broker modal, auto-reset orchestration
- `enough/prompt.py` — assembles the system prompt from `rness/` on
  every turn (no caching, so edits land on the next message)
- `enough/broker.py` — broker config + trace logging + canned
  denial messages
- `enough/tools.py` — `read_file`, `write_file`, `shell`, `fetch_url`,
  plus path safety and Tor routing
- `enough/skeleton.py` — creates `rness/` for new projects, syncs
  global skills/roles on every launch, runs migrations
- `enough/llm.py` — talks to llama-server (local LLM via
  OpenAI-compatible API)
- `enough/supervisor.py` — manages the llama-server subprocess
- `enough/static/index.html` — the entire UI (htmx + vanilla JS)
- `defaults/` — the shipped templates that get copied or symlinked
  into every new project

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

Apache 2.0. See [LICENSE](../LICENSE).

Third-party content (the bundled `defaults/skills/` packages) carries
its own licenses — see [THIRD_PARTY_LICENSES.md](../THIRD_PARTY_LICENSES.md).
