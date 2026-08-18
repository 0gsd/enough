Hi, this is Graham, the creator of enough. This document -- except this part, I mean -- is written and maintained primarily by agents. I will almost certainly salt and pepper some Grahamisms in there once in a while, but the idea is to not let my own desire to write fun stuff get in the way of comprehensive documentation.

# the enough help center

> Everything you can do with enough, in one place. Written against enough **0.2.2**, including the skills round (analyzer's new audit mode, the `anything-finder` skill, and the first-use audit that reads any skill enough didn't ship before it's allowed in), the August 2026 round (seven local models with feasibility-checked installs, and **enough.app** — the signed, notarized desktop application) and the July 2026 interface round (the mode stack, per-folder help bubbles, girraph→merirmaid mirrors). Where this document and the app in front of you disagree, the app is right and this document has a bug — corrections welcome at [enough.support](https://enough.support).

enough is a personal language system that runs on your own machine. You point it at a folder, talk to it, and it helps you plan, write, review, research, and translate. The models are local by default. Your files stay yours. And nearly everything you'll see it do is defined in plain markdown files that you can open, read, and change.

Hold onto one idea while you read: **the built-in features in this manual are a fraction of what enough can do.** The paradigms, roles, and skills in the box are a starter kit — working examples of three customization mechanisms, not the boundaries of them. The endgame is that you write your own, or have the agent write them with you: a paradigm for the way you plan essays, a role that argues like your toughest reader, a skill that encodes your house style. Section 2 explains how. It is the most important section in this document, and the manual will keep sending you back to it.

---

## 1. Installation, shortcuts, and this documentation

### 1.1 What you need

- A Mac with Apple Silicon. (enough is built and tested on macOS. Linux support is planned; Windows is feasible.)
- Disk space for at least one model — the smallest is about 5 GB.
- No accounts, no API keys, no subscriptions. Unless you later opt into the cloud model slot (section 11.2), everything runs locally.

### 1.2 Installing

Two doors, same house.

**The app — the short way.** Download the `enough` DMG from the releases page, open it, drag **enough** into Applications, and launch. macOS will note that it's an app from the internet — it's signed and notarized, so this is the friendly blue dialog with an **Open** button, once, not a warning to fight past. A first-run guide takes it from there: it builds its own Python environment, shows you the model list with an honest verdict about what fits *this* machine (section 11.1), lists which optional extras you already have, and asks you to pick a project folder. Most of the wait is model download. No Terminal, no Homebrew, no git.

The app carries its own inference engine and Python. The optional extras — voice input, webpage fetching, grammar checking, translation — are still separate programs; the guide's Extras page names each one, what turns off without it, and how to get it. Nothing is required, and nothing installs behind your back.

**The terminal — the long way, with more levers.** Clone the repository, then double-click `install-enough.command` inside the clone:

```bash
git clone https://github.com/0gsd/enough.git ~/Downloads/enough-seed
open ~/Downloads/enough-seed
```

The first time you double-click it, macOS Gatekeeper may balk at an "unidentified developer" — that caution is about the `.command` file, which isn't signed the way the app is. Right-click the file and choose **Open** once; macOS remembers the trust from then on.

The launcher runs `bootstrap.sh`, a ten-step interactive installer that asks before each step and explains what it's about to do. Ctrl-C is safe at any point. Re-running is safe too — it checks state first and picks up where you left off. The steps, roughly:

1. Check your platform.
2. Check for Homebrew, and help you install it if it's missing.
3. Install the helper programs enough leans on: `llama.cpp` (local model inference), `whisper-cpp` (voice input), `tor` (anonymized web fetches), `pandoc` (webpage-to-markdown conversion), and `harper` (local grammar checking, used by the analyzer skill).
4. Set up `~/enough/`, the global install directory.
5. Prepare the Python environment (via `uv`).
6. Download model weights. Every supported model is offered one at a time, each with its size and a feasibility check against your machine's memory and free disk — ✓ means comfortable, ~ means tight, ✗ means look elsewhere. Say yes to as many or as few as you like; section 11.1 describes them all, and anything you skip is a one-click install later.
7. Place the voice-input (whisper) model.
8. Place the offline-translation model, used by the `translator` skill.
9. Put the `enough` command on your PATH.
10. Done, with a printed list of next steps.

Updating later: run `update-enough.command` from `~/enough/`, or type `/update-enough` into the chat box. When new defaults ship, enough mentions it in the interface and points you at that command, so you don't need to go checking. `update-weights.command` refreshes model weights separately.

### 1.3 Launching

**From the app:** double-click. You get a folder picker — any folder can become a project — and the interface opens in the app's own window. The **enough** menu holds one setting, **Reopen Last Project on Launch**, off by default: flip it on and the app skips the picker and resumes where you were. One window, one project at a time; quit and relaunch to move.

**From the terminal:** enough runs per project folder. Open a terminal in any folder and run:

```bash
enough
```

then visit `http://127.0.0.1:3456` (enough opens it for you). Different folder, different project, different agent memory. The one folder you can't launch from is `~/enough/` itself — the CLI refuses, because that's the install, not a project.

If you'd rather never type the command, two launchers ship in `~/enough/shortcuts/`:

- **`enough-on.command`** — copy it into a project folder (`cp ~/enough/shortcuts/enough-on.command ~/some-project/`), then double-click it in Finder. A Terminal window opens in that folder with enough running; ⌘W or Ctrl-C stops it.
- **`setup-quick-action.sh`** — run once (`bash ~/enough/shortcuts/setup-quick-action.sh`) and you get a Finder Quick Action: right-click any folder → Quick Actions → **Launch in enough**. If the menu item doesn't show up, enable it under System Settings → Keyboard → Keyboard Shortcuts → Services → Files and Folders.

### 1.4 This documentation, and the rest of it

This file is the long-form manual. You also have:

- **In-harness help** — the `(?)` bubbles throughout the interface, each explaining the thing it's attached to: a *what*, a *how*, and an *ideas* list. See section 7.4.
- **The cheat sheets** — keyboard shortcuts and markdown syntax, one click away in the UI window. See section 7.3.
- **[enough.support](https://enough.support)** — the community forum: install help, workflow show-and-tell, and people who will happily help you build the customizations this manual keeps nudging you toward.

---

## 2. Workflow customization at a core level

If you read one section, read this one.

Most software hands you features. enough hands you mechanisms. The agent's personality, method, and skillset are assembled fresh on every single message from markdown files sitting on your disk:

- **`AGENT.md`** — who the agent is and how it operates (section 3.1)
- **`MOTIVATION.md`** — why: values, priorities, what "done" feels like
- **Policies** — hard rules about what it may read, write, and fetch (section 3.2)
- **The active paradigm** — the reasoning framework in force right now (section 12)
- **Enabled skills** — capabilities it can reach for (section 14)
- **Enabled roles** — other personas you can summon (section 13)
- **The project profile** — what it has learned about this project (section 5.1)

Edit any of these, in the app or in any text editor, and the change takes effect on the next message. No rebuild, no restart, no plugin API. If you can write a markdown file, you can reprogram your agent.

### 2.1 Global vs. project-local

Everything customizable follows one pattern: **defaults live in `~/enough/defaults/`, projects link to them, and any project can break the link.**

Edit a file in `~/enough/defaults/` and every project still linked to it picks up the change. In a project, open a linked file and click **customize** — the link becomes a project-local copy, and from then on that project goes its own way while the others keep following the global default. The file tree tells you which is which at a glance: linked files render *italic and muted*, local copies render normally.

New skills, roles, and paradigms dropped into `~/enough/defaults/` appear in every project on next launch. Skills and roles arrive toggled off, so nothing changes behind your back; you enable them per project when you want them. A skill that enough didn't ship — one you downloaded, one a friend sent, one your own agent wrote for you — gets read before it's allowed in. Section 14.6 covers that.

### 2.2 The three component types

| | Paradigm | Skill | Role |
|---|---|---|---|
| What it is | A reasoning framework — how the agent approaches work | A focused capability — vocabulary, recipes, procedures | A second persona you can summon — its own AGENT.md + MOTIVATION.md |
| How many active | Exactly one at a time | Any number toggled on | Any number toggled on |
| Lives at | `rness/paradigms/<name>.md` | `rness/skills/<name>/SKILL.md` | `rness/roles/<name>/` |
| Shipped examples | default, text-planning, translation, workflow-design | analyzer, anything-finder, girraph-merirmaid, memoir-dialectic, translator | block-breaker, open-skeptic |

### 2.3 Building your own

You can write these files by hand — they're markdown with a small YAML block at the top — but you don't have to. The shipped **workflow-design paradigm** (section 12.4) exists so the agent can build them with you. Say "build me a skill that…" or "create a role who…" or "make a paradigm for…" and the agent switches into workflow-design, asks its clarifying questions (scope? name? trigger conditions? companion files?), and writes the component properly, including the `description:` frontmatter that tells future turns when to reach for it.

Things people actually build:

- A **paradigm** for each distinct mode of their work — research, drafting, revision — with explicit rules for when to switch.
- A **skill** that encodes a newsletter's voice, a citation format, a dissertation's terminology.
- A **role** that's a rubber duck asking Socratic questions, or a skeptical peer reviewer, or a domain expert built from your own knowledge files.

The rest of this manual describes the built-ins. Read every one of them as a worked example you're allowed to copy, fork, and improve.

---

## 3. Agent Discussion — the home screen

When enough opens you land in the discussion view: the conversation with your agent, plus the sidebar showing your project. This is home. Every other mode stacks on top of it and eventually closes back down to it.

What's here:

- **The chat.** Type a message, hit ⌘Enter (or the send button). Responses stream in live, and the agent can act while it talks — reading and writing files, running shell commands, fetching pages — with each tool call appearing in the transcript as it happens.
- **The mic button.** Click it and dictate. Speech is transcribed by whisper.cpp locally; your voice never leaves the machine. The button pulses while recording. Click again to stop.
- **The sidebar.** The project's file tree, plus the control sections: the active **paradigm**, toggles for **skills** and **roles**, and your **requests**. Option-click any file or folder for a context menu (new file, new folder, copy path, copy name). ⌘\ hides and shows the whole sidebar.
- **The top bar.** Buttons for the model window, the broker, the UI window, wikisink (🚰), and cacheawl — and at the right edge, the indicators for whatever modes are currently stacked open (section 10).

### 3.1 AGENT.md and MOTIVATION.md

Every project carries its own copy of these two files in `rness/`. They are the root of the agent's identity, and both are loaded into every turn.

**`AGENT.md`** is the *how*: working instructions. Tone, guardrails, conventions, standing orders. "Keep prose lowercase." "Never touch files in `archive/`." "Ask before running shell commands longer than one line."

**`MOTIVATION.md`** is the *why*: values and priorities beyond the task in front of it. What the project is for, who it serves, which tradeoffs matter (correctness over speed? brevity over thoroughness?), what "done" feels like.

Click either file in the sidebar to read it; hit **customize** to fork your project-local copy, or edit it in any editor you like. Changes land on the next message. Roles use the same two-file pattern (section 13) — the main agent is not special, only first.

### 3.2 The policies folder and allowlists

`rness/policies/` holds the agent's hard rules. Not personality — law. Four policies ship by default:

- **`allowlists.md`** — the reach rules. Three lists:
  1. *File-read prefixes:* absolute paths the agent may read outside the project (default: `~/enough/`).
  2. *File-read-write prefixes:* paths it may also write outside the project. This list ships **empty**: out of the box, the agent writes only inside your project, and it stays that way until you deliberately add a path.
  3. *Internet domains:* hosts fetched directly (the defaults include `gutenberg.org`, `en.wikipedia.org`, `en.wikisource.org`, `archive.org`, `standardebooks.org`, and Kiwix's download host). A domain that's not on the list isn't blocked — the fetch is routed through a local Tor proxy instead, so an ad-hoc lookup doesn't leave your address in some server's logs. A broker toggle can disable that fallback, making off-list fetches fail outright.
- **`context-management.md`** — how the agent senses a filling context window and resets gracefully without losing state (section 5.3).
- **`requests.md`** — when and how the agent tracks long-running work as request files (section 5.3).
- **`profile-maintenance.md`** — what belongs in the project profile and what doesn't (section 5.1).

Policies are symlinked from the defaults like everything else, so you can tighten the allowlist globally or customize it for one project that needs looser (or stricter) reach. Editing `allowlists.md` is the single most common customization in practice: add the documentation sites you trust, add a shared folder the agent should be able to write into, and get on with your day.

---

## 4. Read/Edit mode

Click any file in the tree and it opens in the unified read/edit mode: one mode with two *faces* — a **read face** (the eye) for reviewing, an **edit face** (the pencil) for changing text.

### 4.1 Full vs. mini, and switching between everything

Read/edit comes in two sizes. **Mini** is a side panel beside the chat: keep a reference document at your elbow while you converse. (The mini panel deliberately omits the review toolbar — it's for reading and quick edits, not markup.) **Full** takes the whole frame, for long documents and serious editing.

Switch sizes with the mini↔full button in the panel chrome. Switch faces with the face-toggle button next to it. ⌘S saves in the edit face. And everything is dirty-guarded: if you have unsaved edits, enough prompts before letting anything discard them — navigating to another file, closing the mode, bouncing to a different document. You will not lose an hour of work to a stray click.

Like every full-frame mode, read/edit shows its icon in the top-right indicator area, with a small red-x ribbon hanging off it to close (section 10).

### 4.2 Highlighting

In the read face of any markdown document, select text and paint it one of four colors — **yellow, green, blue, pink** — from the toolbar or the popup that appears over a selection. The same toolbar offers light formatting: bold, italic, underline (⌘B / ⌘I / ⌘U).

Highlights are durable, and they live out-of-band: each document gets a hidden sidecar file (`.<filename>.highlights.json`) rather than markup spliced into your text, so the document itself stays clean. A colored band in the margin marks each highlighted line. Highlights persist across sessions, and overlapping colors stack.

Here's the part that changes how you work: the agent can see them. Its `read_highlights` tool lists every highlight in a document by color, and `navigate_to_highlight` jumps the view to one. That turns highlighting into a channel. Paint the four paragraphs you want rewritten yellow and the two you love green, then say "rewrite the yellow parts; keep the tone of the green ones." When you mention a color, the agent knows you mean your highlights.

### 4.3 Supported filetypes

- **Markdown (`.md`)** renders formatted in the read face and as source in the edit face. Markdown is enough's native tongue — nearly everything the system itself writes is markdown.
- **Plain text**, and anything text-like, opens in read/edit as text.
- **`.girraph`** files open in girraph mode instead (section 15).
- **`.merirmaid`** files open in merirmaid mode instead (section 16).
- **Saved Wikipedia articles** (`article.html` inside a `wiki/` folder) open in the wikisink reader at full fidelity (section 8.2).

enough is a text system. Binary formats — docx, pdf, images — are not first-class citizens in the viewer. The usual move is to ask the agent to convert what you need into markdown; pandoc is installed for exactly this kind of work.

---

## 5. The project folder and `rness/`

A project is a folder. Any folder. enough adds exactly one thing to it: `rness/`, the agent's externalized brain for this project. Everything the agent is, knows, and remembers here lives in that folder as ordinary files. You can read all of it, edit all of it, and put it under git if that's your habit.

The layout:

```
your-project/
  rness/
    AGENT.md            who the agent is here          (3.1)
    MOTIVATION.md       why it works                   (3.1)
    active-paradigm     which paradigm is in force     (12)
    paradigms/          available reasoning frameworks (12)
    skills/             available skills               (14)
    roles/              available personas             (13)
    policies/           the hard rules                 (3.2)
    knowledge/          project memory                 (5.1)
    io/                 input/output workspace          (5.2)
    requests/           long-running work tracking      (5.3)
  ...your actual files...
```

Symlinked entries (italic in the tree) follow the global defaults; customize any of them to fork a local copy (section 2.1). Files you drop into the project by any means — Finder, another editor, the agent — are equally visible to everyone on the next turn.

### 5.1 The knowledge folder

`rness/knowledge/` is per-project memory.

**`project-profile.md`** is the most useful file in the folder. Its contents are piped into the agent's system prompt on every turn: whatever is written here is in the agent's working memory, no lookup required. The agent maintains it as you work — observed preferences, recurring files and people, conventions you've adopted, threads left open — and you can edit it directly. State a standing preference once in the profile instead of repeating it every session. The profile-maintenance policy keeps the file disciplined: concrete observations rather than vague labels, distillation rather than archive.

**`session-logs/`** holds a dated markdown log of each session's turns, plus the broker's journal (section 6). Append-only history. Browse it, or grep it, when you need to reconstruct what happened last Tuesday.

Beyond those two, the folder is yours. Add a `glossary/` subfolder, a lessons-learned file, background notes — the agent can consult whatever you put here.

### 5.2 The io folder

`rness/io/` is the pass-through workspace:

- **`input/`** — drop files here for the agent to process. Fetched webpages also land here automatically, converted to markdown and cached, so a page fetched once is grounded forever.
- **`output/`** — where generated artifacts land. Review, keep what's good, clear the rest.
- **`cloud-cache/`** — if you use the cloud model slot, every cloud exchange is recorded here (section 11.2). Even cloud work leaves a local, greppable paper trail.

### 5.3 Requests: how long jobs survive

This one rarely makes the quick-start tours, but it's the mechanism that makes multi-session work possible, so it's worth two minutes.

When you ask for anything that will take more than a turn or two, the agent opens a **request file** in `rness/requests/`: a markdown record of the goal, progress checkpoints, and decisions made along the way. You don't have to ask for this. Recognizing the shape of a task is the agent's job.

The request file matters because context windows fill. enough watches conversational pressure, and — per the context-management policy — the agent checkpoints its state into the active request file before things overflow. Depending on your orchestrator setting, enough then either auto-resets (wiping the in-memory conversation and resuming fresh from the checkpoint) or pauses with a banner so you can reset when you're ready. Either way, the filesystem is the real memory, not the conversation: a fresh session reads the request file's Continuation block and picks up where things stood.

Finished requests move to `rness/requests/done/` — click **mark done** on an open request, or tell the agent. The done folder is write-protected from the agent, and it doubles as an honest journal of everything the two of you have actually shipped.

---

## 6. The broker window

The broker is enough's trust anchor. Every tool call the agent makes — every file read, file write, shell command, and web fetch — passes through it. The 🔀 broker window is where you watch and tune that.

Eleven toggles, in groups:

| Toggle | What it controls |
|---|---|
| trace log | Whether the broker writes its journal at all |
| local models only | Whether the cloud slot (OPRO-API) is even offered in the model picker |
| read_file / write_file / shell brokered | Per-tool trace logging, one toggle each — three in all (the allowlists are *always* enforced regardless) |
| fetch_url enabled | Whether the agent's web-fetch tool works at all |
| Tor for off-list fetches | Off-allowlist domains: route through Tor (on) or deny (off) |
| cache & convert fetches | Convert fetched pages to markdown and cache them in `rness/io/input/` |
| wikisink tools | Whether the agent's four wiki tools work (your own 🚰 browsing is never gated) |
| wikisink live updates | Whether update runs may contact Wikipedia at all (off = report from local state only) |
| cacheawl tools | Whether the agent's cachebox tools work (your own cacheawl mode is never gated) |

Everything defaults to on: the defaults trust the agent with the project and keep it honest with a paper trail. That trail — the **trace journal** — lands in `rness/knowledge/session-logs/<date>-broker.md`: timestamp, tool, decision, arguments, outcome, for every brokered call. And when a toggle or allowlist blocks something, the agent receives a clear denial message saying what was blocked and why, so it can tell you instead of failing silently.

Notice the design principle in that table: toggles that gate the agent's tools never gate *your* interface. Turning off cacheawl tools doesn't lock you out of cacheawl mode. It means the agent can't reach into the store on its own.

---

## 7. The UI window and help docs

The ⚙ UI button opens display preferences and the reference material. A small **help** button sits at the top right of that window, beside the ×: it opens this manual read-only, in the app, as a full-frame mode like any other (section 10).

### 7.1 Themes

Four ship with enough: **Enough Default** (deep blue-violet dark), **Pastel** (pale paper, in the spirit of the Terminal "Man Page" scheme), **Wireframe**, and **Darknest**. Switching is instant, and every icon in the interface re-derives its light or dark variant on the fly.

Themes aren't hardcoded. They live in `~/enough/config/ui.json` as named blocks of color values, each applied as a CSS custom property. Copy an existing block, rename it, change the colors, reload: your theme is in the dropdown. The `_doc` block at the top of the file explains each key.

### 7.2 Fonts

Same pattern. Four shipped stacks — SF Mono, system sans-serif, Georgia serif, Courier — and your own additions welcome in the same `ui.json`. For text size, use your browser's zoom (⌘+ / ⌘−); enough deliberately doesn't reinvent zoom.

### 7.3 Cheat sheets

Two columns of reference, right in the UI window.

**Keyboard shortcuts:**

| Keys | Action |
|---|---|
| esc | close the topmost open mode |
| ⌘ \ | show / hide the sidebar |
| ⌘ K | focus the chat input |
| ⌘ Enter | send the message |
| shift Enter | newline instead of send |
| ⌘ B / I / U | bold / italic / underline the selection (read face) |
| ⌘ S | save (edit face) |
| ⌥ click | file-tree context menu |

(On a non-Mac keyboard: Ctrl for ⌘, Alt for ⌥.)

**The markdown cheat sheet:** headings, lists, links, code, quotes — the whole quick reference, for anyone still getting fluent in markdown. Which is worth doing, since enough speaks it natively everywhere.

### 7.4 In-harness help (IHH)

The `(?)` bubbles scattered through the interface are the built-in help system: one bubble per concept — skills, roles, the paradigm selector, rness, io, knowledge, cacheawl, wikisink, the mode system, and so on — each with a **what**, a **how**, and an **ideas** list. The skills, roles, and paradigms bubbles list what's actually installed in *your* project, generated live, so that help never drifts out of sync with reality.

Bubbles are controlled per project folder by the "help (?) bubbles" checkbox in the UI window. On by default for a new folder, and the setting sticks per folder — so your seasoned daily-driver project can go quiet while a fresh experiment keeps its training wheels.

Even the help is customizable. The content lives in one markdown file (`enough/static/help-docs.md`); editing it edits the bubbles.

---

## 8. Wikisink

Wikisink (🚰) puts an offline copy of English Wikipedia on your machine: browsable in-app, full-text searchable, readable by the agent, annotatable, and refreshable on demand with a change report. After setup it needs no internet at all.

### 8.1 Setup

Click 🚰 for the first time and the wizard asks three things.

1. **Size.** Archives are Kiwix builds, text-only unless noted:

   | flavor | contents | approx. size |
   |---|---|---|
   | top 1M articles *(default)* | the million most-read | ~16 GB |
   | all of English Wikipedia | every article | ~49 GB |
   | top 50k | the most-read fifty thousand | ~2.1 GB |
   | top 50k mini | top ~50k, intro sections only | ~320 MB |
   | Simple English | complete Simple Wikipedia | ~950 MB |

2. **Storage.** Default is `~/enough/wikisink`; any folder works, external drives included. Leave about 5% headroom beyond the archive size.
3. **Confirmation.** The download is resumable and survives quits — pause, resume, or cancel from the same window while the rest of enough keeps working.

The archive is a single `.zim` file read in place. It is never extracted, and it never clutters your file manager. You can register **multiple installs** — say, the full archive on an external drive plus a small one on the internal disk — and switch between them in the ⚙ installs list. A detached drive breaks nothing: that install shows as unreachable until the drive returns, and your comments and overrides live independently of any single archive.

Once installed, 🚰 opens the reader: back and forward, live title suggestions in the search box (Enter runs full-text search over the whole archive), a 🎲 random-article die, and a source badge that tells you whether you're reading the archive snapshot (`ZIM <date>`), a fresher copy from an update run (`live <date>`), or a preserved copy (`preserved`). Internal links stay in-app; external links open in your browser. The chat pill at the bottom hands the current article — or your selected passage — straight to the agent.

**The newer-snapshot pill.** Kiwix rebuilds these archives periodically, and you shouldn't have to go looking. When a newer build of *your* flavor exists, a small pill appears in the reader toolbar — `newer snapshot: <date> · <size>`. Click it, confirm the size, and the upgrade runs in place: same storage folder, downloaded first and swapped in only when it's finished, the old file deleted after that and not before. Your comments, saves, and 🛡 overrides carry across untouched, because none of them live inside the archive. The pill becomes the progress readout while it downloads, then disappears. enough checks for this at most once a day, never while the reader is rendering, and stays quiet when you're offline — which is the normal state of an offline-Wikipedia feature. The same upgrade is available the long way round, in the ⚙ installs list, and the agent's wikisink runs report it too (section 8.3) — but pressing the button is always yours.

### 8.2 Saving and locking articles

**Saving.** The save button offers two destinations: this project's `wiki/` folder, or the machine-global wiki cachebox (`~/enough/cacheawl/wiki/`) shared by every project. Either way, a save is a folder — `article.html`, the article byte-for-byte as the archive had it, plus `_manifest.md` carrying the title, source URL, retrieval date, and the CC BY-SA license line. Every saved article is self-describing, which means that if its text ever ends up in something you publish, the attribution you need is already sitting next to it. Click a saved `article.html` in the tree and it opens in the reader at full fidelity — infoboxes, tables and all — even when no archive is reachable. To unsave, hover over the saved folder in the tree and click the 🗑 that appears.

Saving is for *you*: offline-offline copies, publishing attribution. The agent doesn't need saves — its tools read any article in the archive as clean text on demand.

**Comments.** Select text and hit 💬, or use the toolbar 💬 for a paragraph-level note. Threads live in the 🗨 panel: reply, resolve, reopen, jump. Comments attach to the *article*, not to any file, and they survive article updates by degrading gracefully. Text still present stays **anchored**. Text edited away gets **re-pinned** to its paragraph. A paragraph deleted outright leaves the comment **orphaned** in the panel — labeled, but never auto-deleted.

**Locking (deletion overrides).** Sometimes live Wikipedia deletes an article you relied on; the classic case is a niche topic cut for "notability" rather than quality. The 🛡 button preserves your local copy forever — served from then on with a `preserved` badge, excluded from future refreshes, still searchable. Update-run reports actually score detected deletions (notability-flavored rationales rate suspicious; copyright-violation ones rate benign), so you know which deletions deserve a look. And overriding is deliberately yours alone: the agent can recommend 🛡, but it can never press it.

### 8.3 The wikisink update, with change report

"Wikisink" is also a verb. Every article you've saved or commented on is *watched*, and asking the agent to "run a wikisink" (or letting it invoke its `wikisink` tool) checks the watched set against live Wikipedia and reports back. A run:

1. refreshes changed watched articles into a local overlay (their badge flips to `live`);
2. flags **edit spikes** — watched articles suddenly being edited dozens of times a day, plus Wikipedia-wide surge candidates;
3. diffs the daily **top-1000 pageview rankings** against the last run: climbers, fallers, new entries, dropouts, and view trends for your watched articles;
4. checks for **deletions** of watched or recently-viewed articles, scored for suspicion (section 8.2);
5. notes when a **newer base snapshot** is available. Replacing the multi-GB base archive is always your call — press the pill in the reader toolbar (section 8.1) or use the ⚙ installs list. There is no agent tool that swaps it.

The report arrives in chat as markdown; the full uncapped version is kept under the wikisink state folder. Runs are polite to Wikipedia — batched, honest User-Agent — and resumable if interrupted, and a `report-only` run skips the refresh step. Two broker toggles govern all of it: one gates the agent's wiki tools entirely, the other can force runs fully offline.

---

## 9. Cacheawl

Cacheawl is the machine-global text store: the place for things you want to keep forever and reach from every project. It lives at `~/enough/cacheawl/`, hidden from every project's file tree, shared across all your enough instances. (If you ran an earlier enough, your old `infoworld/` library was dissolved into cacheawl on first launch of 0.1.6 — `personal/`, `public/`, and `wiki/` became your first three cacheboxes. Nothing was lost.)

### 9.1 Cacheboxes and their merirmaid charts

A **cachebox** is a top-level folder in the store, and it comes in two flavors. **Plain boxes** hold kept-forever text you organize yourself: a `personal` box of reference notes, a `press` box of published pieces, whatever structure serves you. **Cached replicas** are boxes *ingested* from a source — a local folder, a website, or a set of Wikipedia articles — that remember where they came from.

Every box carries a **merirmaid chart**: `_cachebox.merirmaid`, a live diagram of the box's structure, regenerated whenever the contents change. Double-click it to see the shape of a box at a glance. The chart is a *mirror*, read-only by design, because it reflects reality — to change the chart, change the box. A cheap reconcile pass keeps mirrors honest even when you drop files in from Finder behind enough's back.

Open **cacheawl mode** from the top bar for a two-pane view, project on one side, store on the other. Drag a file across to copy it. Shift-drag to move. Shift-click for a context menu, and double-click to open any file in its natural mode — girraph, merirmaid, read/edit, or the wiki reader — straight from the store.

### 9.2 The cachebox and capturing local or web documents

The **ingest bar** in cacheawl mode (or a plain conversational ask) captures outside material into a box:

- **A local path** — replicate a folder of notes or documents into the store.
- **A website** — crawl a docs site or reference site to a chosen depth (capped around 500 pages) and keep it as local markdown. Web ingests honor your fetch toggles and allowlists, Tor routing included.
- **Wikipedia** — pull a topic's articles (capped around 200) out of your wikisink archive into permanent, project-independent text.

Ingests run in the background. The box appears immediately with an "ingesting" status you can watch, and a failed ingest says so rather than pretending it finished. The agent's cachebox tools (list, create, ingest) are gated by the cacheawl broker toggle; your own use of cacheawl mode never is.

Why bother? Because project folders are working space and cacheawl is library space. Ingest a framework's documentation once, and every future project can ground on it offline. Keep your evergreen reference notes in a box, and every agent you ever talk to can reach them. Finish an artifact and move it to a box, where it outlives its project.

---

## 10. Multiple active mode stacking

enough's full-frame modes — read/edit, girraph, merirmaid, wikisink, cacheawl — don't replace each other. They **stack**, like sheets of paper. Open cacheawl, open a girraph from inside a box, open a notes file over that: three modes deep, and closing each one reveals the one beneath exactly as you left it. Same scroll position, same descent, same unsaved edits.

The top bar shows one square indicator per open mode, newest on the left. Each carries a small red-x ribbon that closes that specific mode, even a buried one. Click a buried mode's indicator to raise it to the top without disturbing anything else. Esc always closes the topmost mode. When the last one closes, you're back at the home discussion — home is the empty stack.

Two conveniences worth knowing:

- The mini read/edit panel floats *over* a full-frame mode, so you can keep a document at your elbow while working in, say, girraph mode underneath.
- Opening a mode that's already somewhere in the stack doesn't duplicate it. It re-targets and raises the one you had.

---

## 11. The model window

The model badge in the top bar opens the model window: which brain is answering you, what else is available, and — if you choose — the cloud slot.

### 11.1 Local models: overview and usage recommendations

Seven supported local models — and the window is now also where you install them. Each row you don't have yet shows its download size and a feasibility verdict computed against *this machine's* memory and free disk: ✓ comfortable, ~ tight, ✗ not recommended. Downloads run with a live progress bar, survive a quit (they resume where they stopped), and can be cancelled without losing the part you already have. Installed models switch with a click, and any model except the active one can be deleted from its row when you want the disk back.

| cute name | model | disk | min RAM | notes |
|---|---|---|---|---|
| **G40-04** | Gemma 4 4B (E4B) | ~5.4 GB | 8 GB | the smallest; fits anywhere; the default |
| **Q35-09** | Qwen3.5-9B | ~5.9 GB | 10 GB | balanced mid-size; MTP speculative decoding |
| **G40-12** | Gemma 4 12B (QAT) | ~7.0 GB | 12 GB | quantization-aware trained; the 16 GB sweet spot |
| **G40-26** | Gemma 4 26B MoE (4B active) | ~15.6 GB | 20 GB | big-model quality at mid-model speed |
| **Q36-27** | Qwen3.6-27B dense | ~17.1 GB | 22 GB | the seasoned heavyweight; MTP; long legs |
| **Q38-04** | Qwen3.8 27B (4-bit) | ~19 GB + 1.7 draft | 24 GB | the newest Qwen; drafts its own speculation |
| **Q38-16** | Qwen3.8 27B (16-bit) | ~54 GB + 3.2 draft | 64 GB | full precision, for the biggest Macs |

One naming wrinkle, so it never trips you: in the two Q38 names, the number after the dash is the **quantization width**, not the parameter count — Q38-04 and Q38-16 are the *same* 27-billion-parameter model, at 4-bit and 16-bit precision. (G40-04, from the older convention, really is a 4-billion-parameter model.) The labels in the window spell this out so the cute names never have to.

Rules of thumb. On an 8–16 GB machine, live on G40-04, and make G40-12 the upgrade once you have headroom — quantization-aware training gives it unusually clean output for its size. On 32 GB, G40-12 or Q35-09 is a comfortable daily driver, with G40-26 or Q38-04 for the harder synthesis work. On 64 GB and up, Q38-04 or Q36-27 as your default and stop thinking about it. Q38-16 is its own category: the full-precision heavyweight for machines with serious unified memory and ~57 GB of disk to spare — if you have a Mac Studio and want the ceiling, this is the ceiling. Context windows scale with your RAM automatically — each model ships a sensible per-RAM-tier default, overridable in config — and the Qwen builds carry Multi-Token Prediction for free extra speed: built into the model file for Q35/Q36, and via a small companion "draft" file for the Q38 pair, which downloads alongside automatically.

One more note for terminal installs: a model can be *downloaded* on any llama.cpp but *run* only on a recent enough build. If yours is too old for a newer model, the window says so and names the fix (`brew upgrade llama.cpp`). App installs never see that note — the app ships its own inference engine.

Switching models restarts the local inference server and clears the in-memory conversation. Your files, logs, and request state all persist; a switch costs you chat scrollback, not work.

### 11.2 OpenRouter support (the OPRO-API slot)

enough is local-first, not local-only. A fifth model slot, **OPRO-API**, routes through OpenRouter to cloud models. It's off by default, deliberately effortful to enable, and honest about the trade: your prompts and outputs leave the machine, in exchange for frontier-model capability and, sometimes, lower cost than the hardware and electricity a comparable local model would demand.

Enabling it: flip **local models only** off in the broker, then click OPRO-API in the model window. A three-screen wizard walks you through it — three explicit confirmation checkboxes (you have an account, you understand billing, you understand the privacy trade), then your API key, then a live health check. The key is stored in the macOS Keychain. It is never written to any file, the agent has no way to read it, and the broker refuses shell commands that so much as look like attempts to get at it. Once verified, OPRO-API becomes selectable like any other model, and its settings panel offers re-test, key update, key removal, and your choice of any OpenRouter model id.

Two things keep cloud use accountable:

- **Everything is cached locally.** Every cloud exchange is written to `rness/io/cloud-cache/` with token counts and an index — a local paper trail your local agent can read later.
- **`cloud_pipeline`** lets the agent batch big jobs through the cloud slot — up to 200 steps, with per-step caching, optional per-step summarization, and a final compilation pass — writing results to disk instead of flooding the conversation. Ask for "a cloud pipeline that drafts all twelve chapter summaries" and the heavy lifting happens out-of-band, fully logged.

---

## 12. Paradigms

A paradigm is the agent's reasoning framework — the rules of engagement for how work happens. Exactly one is active at a time (shown at the top of the sidebar; click ● to switch), and the active paradigm's full text rides in the system prompt on every turn. The agent also sees a one-line catalog of the others, so it can suggest a switch — or make one — when your request would be better served elsewhere. An agent-initiated switch is nothing exotic: it writes the paradigm's name to `rness/active-paradigm` and tells you it's done so.

### 12.1 default

Freeform single-agent conversation. The paradigm for most work, and the router that watches for the moments when another paradigm fits better. It also carries the standing conventions — like knowing that "the yellow parts" means your highlights.

### 12.2 text-planning

For the long runway before prose: taking a novel, an essay collection, a non-fiction book, or a manifesto from "I think I want to write something" to a usable plan. The agent builds one plan document with you at the project root — patiently, iteratively, across as many sessions as it takes — and then, on request, generates per-section *scaffolds*: structural guides (beats, headers, voice reminders, word budgets) that you expand into prose yourself. The paradigm's defining rule: **it never writes your prose.** Scaffolds contain structure only. Your voice stays your voice. (It activates alongside the `analyzer` or `memoir-dialectic` skill; memoirs get handed off to memoir-dialectic, which is purpose-built for them.)

### 12.3 translation

Declares offline translation a first-class capability. It pairs with the `translator` skill (section 14.5): when a request involves moving text between human languages, the agent switches here, and if the skill is toggled off it tells you what you're missing — and keeps telling you until you flip it on. With the skill on, you have a ~419-language local translator with no account, no rate limit, and no network dependency.

### 12.4 workflow-design

The paradigm about enough itself, active whenever you're making or changing the workflow rather than working inside it: new skills, new roles, new paradigms, edits to AGENT.md or MOTIVATION.md. Here the agent behaves like a thoughtful collaborator on design — clarifying questions before building (scope? name? trigger conditions?), alternatives when your first instinct could be sharper, and a tracked request file for every build, since workflow changes outlive the conversations that produce them. This is the paradigm that makes section 2 real.

---

## 13. Roles

A role is a second persona you can summon into the conversation: its own `AGENT.md` and `MOTIVATION.md`, the same two-file pattern that defines your main agent, scoped to a complementary — or deliberately adversarial — character. Toggle roles per project in the sidebar. Enabled roles ride in the system prompt, and you call on them by name ("what would the open-skeptic say about this plan?").

### 13.1 block-breaker

A writing-block specialist, distilled from a real writer's answers about how they dissolve being stuck. It diagnoses before it prescribes — out of ideas, out of nerve, out of structure, and out of permission are four different problems — then reaches for constraints, rep-based brainstorming ("ten variations, then whittle"), weird reframes, and, when wanted, actual next sentences. Relentlessly anti-defeatist. Its core belief: for anyone writing voluntarily, block is always solvable, because the rules were made up and the cure can be made up too.

### 13.2 open-skeptic

An "enlightenable doomer": genuinely enthusiastic about AI where it's strong, professionally suspicious where it's oversold. Summon it when you're about to build a workflow and want the failure modes named early. It pushes back on asking AI to replicate human experience, on compounding-error chains with no human review, and on fluent confidence doing the work of expertise — while cheering for AI as collation engine, knowledge prosthesis, and rehearsal partner. It updates on evidence: show it a workflow that works and it says so, plainly.

### 13.3 Rolling your own

Two examples, one pattern — instructions plus motivation, in two markdown files. Roles are the cheapest way to add a voice you're missing: a Socratic rubber duck, a compliance reviewer, a reader persona for your target audience, a domain expert fed from your own knowledge files. Ask for one in the workflow-design paradigm and the agent will interview you and write both files.

---

## 14. Skills

A skill is a focused capability package: a folder with a `SKILL.md` (plus optional reference docs and scripts) that teaches the agent a procedure, a vocabulary, or a discipline. Toggle skills per project in the sidebar. Off means truly off — not in the prompt at all — and new skills arrive disabled, so nothing changes behind your back. A skill enough didn't ship gets read before it can be enabled at all (section 14.6). Turning everything off is legitimate too: pure conversation, no scaffolding, sometimes more room for the model to surprise you.

### 14.1 analyzer

Four analytical modes in one skill.

**Summarize** produces a one-page, even-handed digest of any text: what it's saying, who it's for, the author's motivation and biases, tone, key quotes.

**Proofread** does light copy-editing — typos, spelling — across full documents up to whole books, driven by Harper, a local rule-based grammar checker. It also produces a separate proof report of suggestions and repeated-phrase findings, so silent fixes and judgment calls stay distinguishable.

**Decide** hands your dilemma to three archetypal personas from a built-in roster of ten, who debate it on the record. You get a recommendation *and* the transcript, so you can weigh the reasoning rather than trust a verdict.

**Audit** reads something you haven't decided to trust yet — a skill someone sent you, a role, a paradigm — and tells you what it is. First a plain-English explanation of what the thing actually does and why you'd want it, then a safety pass: prompt-injection attempts, instructions that quietly widen the agent's reach, epistemic red flags, and any bundled code, which also gets a deterministic scan that doesn't involve a model at all. The verdict is one of three words — **pass**, **flag**, **fail** — backed by named findings, never a score. It's read-only: audit never runs, edits, installs, or enables the thing it's reading.

Reports land in `rness/io/output/analyzer/audits/<skill-name>/`: a dated `.md` you can read like any other file, plus a small `verdict.json` beside it. Ask for an audit by name any time — "vet this before I enable it", "what does this skill actually do" — and enough also runs this mode for you, unasked, the first time you switch on a skill it didn't ship. Both doors write the same report to the same folder. Section 14.6 has that story.

### 14.2 anything-finder

A search party for the things that don't come up on the first page. Three faces, one skill.

**find** is the default, and it carries a playbook for each of ten kinds of hard-to-find thing, plus an eleventh for missions that stall. **Texts** — public-domain books, poems, historical documents. **Video** — rare, lost, and out-of-print film and TV, with watch links and their legality stated. **Images** cleared for a cover or a zine. **Products** — obscure gear, synths, instruments, and where to actually buy one. **Articles** — the paper stuck behind a paywall, found as its legitimate open copy: preprint, repository, archive. **Code** — permissively licensed repos, including libraries that never touched GitHub. **Books** — read-alikes from what you already loved. **Audio** — sheet music, MIDI, samples, gear manuals. **Assets** — fonts, textures, 3D models, stock footage. **Data** — datasets, public APIs, government documents, newspaper archives.

Results come back as *find cards*: the link, why it's the right item, and — for anything copyright-sensitive — why it's clear to use, with the publication date or the explicit license spelled out. Ask it "find me a public-domain edition of *The Moonstone* clean enough to typeset", "where can I legally watch the 1974 version", "is there an MIT-licensed library that does this". The honest answers are part of the deal: "this exists but isn't legally available" and "three candidates, I'm 70% on the second" are real results here, and where the only route is a piracy site it will say so and hand you the library, the lending system, or the storefront instead.

**patents** is the prior-art face. Give it an invention and it runs a structured novelty search across granted patents, published applications, and the non-patent literature, then reports what it found and what that means for novelty and non-obviousness — with a not-legal-advice disclaimer that stays in every report, because that's what it is. "Has this been patented?" "Prior art on a magnetic bike lock that…" "Is my idea patentable?" Databases it couldn't reach come back labeled *unchecked*, never quietly as *empty*.

**venture** is the "is this a business?" face, and it composes the other two. A market sweep for what already exists, a prior-art check, and a competitive-landscape pass over companies, open-source alternatives, adjacent products, and the graveyard of the ones that tried and shut down. What you get is an even-handed read — what's crowded, what's adjacent, what's genuinely open, and the wedge the evidence actually supports — followed by the strongest case *for* and the strongest case *against*, every point anchored to a link, and a short list of questions only you can go answer. Ask it "should I build this", "does this exist as a product", "where's the market gap here". It will not score your idea, write your business plan, or tell you to raise money. And it treats an empty field as a question, not a green light.

Output goes to `rness/io/output/anything-finder/`. Everything it fetches goes through the broker like any other web access, so an off-allowlist domain routes through Tor — and when a source refuses to answer, the report names the host and tells you what to add to `allowlists.md`, instead of leaving a silent hole in the results.

### 14.3 girraph-merirmaid

The discipline skill for enough's two diagram primitives (sections 15 and 16). The girraph half teaches proper IBIS mapping: one question per turn, no solution-jumping, your confirmation as the stopping rule. The merirmaid half carries the Mermaid-authoring rules, like keeping node labels short enough that you can comfortably edit them. The modes work without the skill; with it, the agent becomes a genuinely disciplined mapping partner.

### 14.4 memoir-dialectic

A patient, multi-session memoir collaborator. It interviews you — one or two questions at a time, never a flood — and files everything: numbered plan documents in conversation order, an index for fast resumption, a notes file for messy brain-dumps, and eventually an outline synthesis and, only if you want it, drafts. The folder is the memory. You can disappear for weeks or years and it picks up where you left off. Built for the full range from complete life story to a single milestone, with explicit handling of sensitive topics and no-go zones, and careful preservation of your own phrasing — voice matters, especially if a draft is coming.

### 14.5 translator

Offline translation across ~419 languages via MADLAD-400 — a ~3 GB one-time download that runs on CPU or Apple Silicon and never phones home. Short phrases to whole documents, major languages to low-resource and indigenous ones. Translate a letter, localize a README, check what a passage means, roundtrip a phrase through a third language as a meaning-preservation test — all with the network unplugged. For certain low-resource languages, an optional NLLB-200 engine offers higher quality; it carries a non-commercial license, so it's opt-in via the translation paradigm.

### 14.6 Writing your own, and trusting other people's

The five above are demonstrations. The skill *mechanism* — markdown instructions, loaded when toggled on, with a `description:` that tells the agent when to engage — is the actual feature. House style guides, domain checklists, recurring report formats, data-handling procedures: if you can describe a competence in prose, you can hand it to your agent as a skill. Build your own with workflow-design (section 12.4), or fork one of the five and make it yours.

The other end of that loop is the skills that arrive from somewhere else. A skill is instructions your agent will follow, which means a skill from the internet deserves exactly as much suspicion as any other file from the internet. So enough reads them for you:

- **What enough ships is trusted, and looks like it always has.** The five above arrive as links into the install's own defaults. They toggle instantly. Nothing audits them.
- **Everything else is off until it's been read.** Drop a skill folder into `rness/skills/` — downloaded, sent by a friend, unzipped from a `.skill` — and it sits there disabled, marked *unverified* in the sidebar. The first time you switch it on, enough runs analyzer's audit mode over it (section 14.1) before a word of it reaches the agent. You watch it happen in the row: *unverified* → *auditing…* → *audited*.
- **Flagged means not enabled.** If the audit finds something, the row says *flagged* (or *failed*), the skill stays off, and you get two buttons: **read report** opens the full report in the reading view, and **enable anyway** asks you to confirm and then records the decision as yours — the finding isn't erased, it's overruled, and the row from then on reads *trusted by you*. The audit advises. You decide. (If you'd rather work in the file, editing that skill's `verdict.json` to `"verdict": "pass"` does the same thing.)
- **Edit a skill and it gets re-read.** The audit is tied to the exact bytes it read — file names and contents both. Change anything and the next time you toggle that skill on, it's audited again. That includes one you'd previously enabled anyway: an override describes one particular set of files at one particular moment, and it doesn't survive an edit.
- **Skills your agent writes for you count as untrusted too.** That's deliberate, not an oversight. When workflow-design writes a new `SKILL.md` into `rness/skills/`, the agent audits its own homework on first enable. It's near-instant when there's nothing to find.
- **With no model running, an audit can't finish** — and it says so, flagging with "the llm half of the audit couldn't run" rather than waving the skill through. Turn a model on and toggle again, or use *enable anyway* if you already know what's in there.

Reports live in `rness/io/output/analyzer/audits/<skill-name>/` — the same folder analyzer writes to when you ask for an audit in conversation. Two doors, one document, and it's an ordinary markdown file you can open, keep, or delete.

---

## 15. Girraph mode and the `.girraph` extension

It's pronounced "graph." The *ir* is silent — it stands for *iterative* and *recursive*. The animal is a 🦒, and the animal is also silent.

A girraph is a map of a hard question. Not a to-do list: a picture of a *disagreement*, including the productive ones you have with yourself. Some problems ("Should we homeschool?", "What is this book actually about?", "Do we take the funding?") sprout an objection from every answer and a new question under every objection. A list buries that fight. A girraph keeps it visible:

- ❓ **issues** — open questions, always phrased as questions
- 💡 **positions** — possible answers
- ➕ ➖ **arguments** — reasons for and against a position
- 📄 **notes** — background, constraints, references to documents
- 🦒 **nested girraphs** — a sub-question big enough for its own map

The lineage is IBIS, a 1970s method for "wicked problems" — the kind with no clean answer and no natural stopping point. The girraph is enough's plain-text take on it.

The format is a text file ending in `.girraph`, one line per thought, readable in any editor in 2026 or 2056:

```
%girraph 0.1
title: Should enough ship a plugin API?

q1 ? Should enough ship a plugin API?
p1 ! Ship a minimal one < q1
a1 + Ecosystem growth needs stable hooks < p1 by:graham
a2 - API surface = forever maintenance < p1 by:open-skeptic
```

`< q1` means "this answers q1"; `by:` remembers whose claim it is. No database, nothing hidden. The file is the map.

In the app, clicking a `.girraph` opens girraph mode: a collapsible tree you edit directly. Click a label to rewrite it. Hover a row for add, link, and remove buttons. Click a 🦒 chip to descend into a nested map — breadcrumbs bring you back — and click a 📄 chip to read a referenced document in place. In chat, say "girraph this" or "map this out," and the agent edits the same file through the same node-level operations you use, so you can both work the map at once. Deleting nodes always requires your confirmation, and children are never silently orphaned.

A girraph can also grow a **merirmaid mirror**: one click on the merirmaid button in the girraph toolbar creates a linked, auto-regenerating Mermaid diagram of the map — issues as hexagons, positions as stadiums, supports and objections stroked in their colors — that keeps itself current as the girraph changes. Map in girraph, glance in merirmaid.

Three habits make girraphs work. Phrase issues as questions ("How do we fund year two?", not "the money problem"). Attach arguments to positions, not issues — reasons are reasons for or against an *answer*. And split a branch into its own file before it sprawls. Enable the girraph-merirmaid skill and the agent will hold you to all three.

---

## 16. Merirmaid mode and the `.merirmaid` extension

Where a girraph maps an argument, a **merirmaid** depicts a structure. A `.merirmaid` file is a [Mermaid](https://mermaid.js.org/) diagram — flowchart, sequence diagram, state machine, ER diagram, anything Mermaid draws — with a small frontmatter header, rendered live in the browser. Locally, of course; no CDN, like everything in enough.

Two modalities, declared in the header:

- **wip** — a working whiteboard. Click any node's text and edit the label in place, with a live character count; structural changes (add a box, rewire an arrow) go through the agent via the chat pill. Ask for a diagram of your pipeline, your plot, your org, and the agent writes the source, the browser draws it, and you tune the words.
- **mirror** — a read-only reflection of a structure that lives elsewhere: a cachebox's contents (section 9.1) or a girraph (section 15). Mirrors regenerate when their source changes. To change the picture, change the thing.

Diagrams link. A node can point at another `.merirmaid`, a `.girraph`, or a markdown document, and clicking it navigates there, breadcrumbs marking the way back — so a set of diagrams becomes a navigable atlas of your project. And when a diagram has a syntax error, merirmaid mode shows the error plus the raw source rather than a blank pane. There is always something to fix from.

The girraph-merirmaid skill (section 14.3) carries the authoring discipline for both file types. One rule of thumb from it is worth repeating here: if the honest first move is asking a question, you want a girraph; if it's drawing a box and an arrow, you want a merirmaid.

---

## 17. Where to go from here

The fastest way to make enough yours:

1. Launch it in a real project — something you actually care about.
2. Spend one session talking, and let the project profile start accumulating.
3. Edit `MOTIVATION.md` to say what the project is actually for.
4. The first time you repeat an instruction, stop. Put it in `AGENT.md` instead.
5. The first time your work has a shape the defaults don't fit, say "let's design a paradigm for this" — or a skill, or a role — and let workflow-design walk you through it.

That loop — notice friction, encode the fix, keep working — is the whole game. The built-ins get you started. The system you end up with, nobody ships. You write it.

---

*enough is © 2026 Graham Smith, released under the Apache License 2.0. Wikipedia content reached through wikisink is CC BY-SA. This document: also yours to edit.*
