Hi, this is Graham, the creator of enough. This document -- except this part, I mean -- is written and maintained primarily by agents. I will almost certainly salt and pepper some Grahamisms in there once in a while, but the idea is to not let my own desire to write fun stuff get in the way of comprehensive documentation.

# the enough help center

> Everything you can do with enough, in one place. Written against enough **0.4.1**. New in this round: **the dictionary** — FEED, the first-party enough english dictionary: about 96,000 words with their sounds, families and histories, built on your own machine, a right-click away from any word you're reading, and with room beside it for words of your own (section 13); **text-planning** as the home paradigm every project starts in, with the old `default` paradigm folded into it (section 16); a brief introduction to enough, one click away in an empty conversation (section 5); and a contents list, find, and live section links in this manual (section 10). From the round before: **`/pal`**, where your chief readvisor thinks locally first and then sends one refined question to the cloud model you configured, showing you exactly what left the machine (section 15.3); and councils that finish into an answer, a document, or a whole new composure, with an optional one-line charge per readvisor and a way to reconvene a council that has already concluded (section 18). From the composure round: the canvas that is now the floor of every project, with the conversation in a panel beside it (sections 4 and 5); **readvisors**, which is what roles are called now, led by a chief readvisor named Ed (section 17); **councils**, where several readvisors think about one thing in turn, in writing, while you watch (section 18); and two skills, `readvisory` and `scaffold` (section 19). A project made before then has its `rness/roles/` folder renamed to `rness/readvisors/` the next time you open it, with your on/off settings intact (section 8). Also here, from the rounds before: the home screen (every project you've ever started, in one list, with a way in and a way back out — section 2), the convert round (PDFs, Word documents, ebooks, decks and workbooks open as editable markdown twins, with export, sync, and an image viewer — section 7), the skills round (analyzer's new audit mode, the `anything-finder` skill, and the first-use audit that reads any skill enough didn't ship before it's allowed in), the August 2026 round (seven local models with feasibility-checked installs, and **enough.app** — the signed, notarized desktop application), the July 2026 interface round (the mode stack, per-folder help bubbles, girraph→merirmaid mirrors), and the 0.3.0 preferences round (per-project ui and text scaling, and the interface + help in six languages — section 10). Where this document and the app in front of you disagree, the app is right and this document has a bug — corrections welcome at [enough.support](https://enough.support).

enough is a personal language system that runs on your own machine. You point it at a folder, talk to it, and it helps you plan, write, review, research, and translate. The models are local by default. Your files stay yours. And nearly everything you'll see it do is defined in plain markdown files that you can open, read, and change.

Hold onto one idea while you read: **the built-in features in this manual are a fraction of what enough can do.** The paradigms, readvisors, and skills in the box are a starter kit — working examples of three customization mechanisms, not the boundaries of them. The endgame is that you write your own, or have your chief readvisor write them with you: a paradigm for the way you plan essays, a readvisor that argues like your toughest reader, a skill that encodes your house style. Section 3 explains how. It is the most important section in this document, and the manual will keep sending you back to it.

---

## 1. Installation, shortcuts, and this documentation

### 1.1 What you need

- A Mac with Apple Silicon. (enough is built and tested on macOS. Linux support is planned; Windows is feasible.)
- Disk space for at least one model — the smallest is about 5 GB.
- No accounts, no API keys, no subscriptions. Unless you later opt into the cloud model slot (section 15.2), everything runs locally.

### 1.2 Installing

Two doors, same house.

**The app — the short way.** Download the `enough` DMG from the releases page, open it, drag **enough** into Applications, and launch. macOS will note that it's an app from the internet — it's signed and notarized, so this is the friendly blue dialog with an **Open** button, once, not a warning to fight past. A first-run guide takes it from there: it builds its own Python environment, shows you the model list with an honest verdict about what fits *this* machine (section 15.1), lists which optional extras you already have, and hands you over to the home screen to choose the folder you want to work in (section 2). Most of the wait is model download. No Terminal, no Homebrew, no git.

The app carries its own inference engine and Python. The optional extras — voice input, webpage fetching, grammar checking, translation — are still separate programs; the guide's Extras page names each one, what turns off without it, and how to get it. Nothing is required, and nothing installs behind your back. One extra isn't a separate program at all: **PDF reading** installs from inside enough whenever you want it (section 7.8).

**The terminal — the long way, with more levers.** Clone the repository, then double-click `install-enough.command` inside the clone:

```bash
git clone https://github.com/0gsd/enough.git ~/Downloads/enough-seed
open ~/Downloads/enough-seed
```

The first time you double-click it, macOS Gatekeeper may balk at an "unidentified developer" — that caution is about the `.command` file, which isn't signed the way the app is. Right-click the file and choose **Open** once; macOS remembers the trust from then on.

The launcher runs `bootstrap.sh`, a ten-step interactive installer that asks before each step and explains what it's about to do. Ctrl-C is safe at any point. Re-running is safe too — it checks state first and picks up where you left off. The steps, roughly:

1. Check your platform.
2. Check for Homebrew, and help you install it if it's missing.
3. Install the helper programs enough leans on: `llama.cpp` (local model inference), `whisper-cpp` (voice input), `tor` (anonymized web fetches), and `harper` (local grammar checking, used by the analyzer skill). The document converters — pandoc, for turning fetched web pages and Word files into markdown, and typst, for writing PDFs — aren't on that list any more: they ship inside enough's own Python environment, installed in step 5, on every platform. If you happen to have your own pandoc from Homebrew, enough uses that one instead.
4. Set up `~/enough/`, the global install directory.
5. Prepare the Python environment (via `uv`).
6. Download model weights. Every supported model is offered one at a time, each with its size and a feasibility check against your machine's memory and free disk — ✓ means comfortable, ~ means tight, ✗ means look elsewhere. Say yes to as many or as few as you like; section 15.1 describes them all, and anything you skip is a one-click install later.
7. Place the voice-input (whisper) model.
8. Place the offline-translation model, used by the `translator` skill.
9. Put the `enough` command on your PATH.
10. Done, with a printed list of next steps.

Updating later: run `update-enough.command` from `~/enough/`, or type `/update-enough` into the chat box. When new defaults ship, enough mentions it in the interface and points you at that command, so you don't need to go checking. `update-weights.command` refreshes model weights separately.

### 1.3 Launching

**From the app:** double-click, and you land on the **home screen** — every folder you've ever made into an enough project, in one list, with a way to add another. Pick one and it opens. That's section 2, and it's worth reading before this one.

The **enough** menu holds one setting, **Reopen Last Project on Launch**, off by default: flip it on and the app skips home and puts you straight back where you were. One window, one project at a time — and **File → Close Project** (⌘W) drops you back to home whenever you want to move, without quitting (section 2.5).

There is still a plain folder picker in there, but you'll probably never meet it: it's the fallback for the case where the home screen itself can't come up — a half-finished update, a broken install — so that a bad day still leaves you a way into your work.

**From the terminal:** enough runs per project folder. Open a terminal in any folder and run:

```bash
enough
```

then visit `http://127.0.0.1:3456` (enough opens it for you). Different folder, different project, different memory. The one folder you can't launch from is `~/enough/` itself — the CLI refuses, because that's the install, not a project.

You get the home screen too, from anywhere:

```bash
enough --home
```

Same screen, same list, in your browser instead of the app window. Open a project from it and the terminal you started it in becomes that project's terminal.

If you'd rather never type the command, two launchers ship in `~/enough/shortcuts/`:

- **`enough-on.command`** — copy it into a project folder (`cp ~/enough/shortcuts/enough-on.command ~/some-project/`), then double-click it in Finder. A Terminal window opens in that folder with enough running; ⌘W or Ctrl-C stops it.
- **`setup-quick-action.sh`** — run once (`bash ~/enough/shortcuts/setup-quick-action.sh`) and you get a Finder Quick Action: right-click any folder → Quick Actions → **Launch in enough**. If the menu item doesn't show up, enable it under System Settings → Keyboard → Keyboard Shortcuts → Services → Files and Folders.

### 1.4 This documentation, and the rest of it

This file is the long-form manual. You also have:

- **In-harness help** — the `(?)` bubbles throughout the interface, each explaining the thing it's attached to: a *what*, a *how*, and an *ideas* list. See section 10.6.
- **The cheat sheets** — keyboard shortcuts and markdown syntax, one click away in the UI window. See section 10.5.
- **[enough.support](https://enough.support)** — the community forum: install help, workflow show-and-tell, and people who will happily help you build the customizations this manual keeps nudging you toward.

And all of it — this manual, the bubbles, the interface around them — reads in six languages: English, French, Spanish, German, Chinese, and Japanese. Section 10.4 has the dropdown and the fine print.

---

## 2. The home screen

Before you're in a project, you're on **home**: one frame listing every folder you have ever turned into an enough project, plus a tile for adding another. It is deliberately the quietest screen in the application. No chat, no sidebar, no model, no readvisor — nothing is running yet and nothing is being thought about. Just your projects, and the ⚙ UI button in the top bar for the theme and this manual.

You'll see it:

- the first time you launch, when the first-run guide finishes;
- every launch after that, unless **Reopen Last Project on Launch** is on (section 1.3);
- whenever you close a project (section 2.5);
- from the terminal, any time, with `enough --home`.

The one way *not* to see it is that toggle. Turn **Reopen Last Project on Launch** on and enough goes straight back to the project you were in; home never interposes. Turn it off and home is where every launch begins. That switch is the whole of the setting — there is nothing else to configure.

### 2.1 The grid, the list, and ¶ W C

Two views, toggled by the pair of buttons at the top right of the frame, and enough remembers which one you prefer.

**Icons** is the browsing view: a folder glyph, the project's name, and one plain-English line underneath — *edited 3 days ago*, or an actual date once it's older than a week.

**List** is the comparing view. Six columns:

| column | what it is |
|---|---|
| name | the project's display name (the one you set in the project title bar, or the folder name) |
| ¶ | paragraphs |
| W | words |
| C | characters |
| last updated | the most recent change to any of the files those counts cover |
| created | when the folder became an enough project |

Those three middle columns are the same three readouts enough puts in the top bar while you have a document open — ¶ for paragraphs (blank-line separated blocks), W for words, C for characters including spaces and newlines — added up across the whole project. The rule about *which* files get counted is worth one sentence, because it's the one that makes the numbers mean something: every markdown file the project's own file tree would show you, **including the twins of converted documents** (a `.docx` you're editing here is your writing), and **not** anything inside `rness/` (enough's own scaffolding is not your book). So the number in the W column is, near enough, how much you have written.

Click any column heading to sort by it; click the same one again to reverse. Projects with nothing to report — never opened, never counted — sink to the bottom either way rather than pretending to be the oldest. The default order is most-recently-edited first.

A project whose folder isn't there right now — an unplugged external drive, a folder you moved in Finder — renders greyed, with the path it remembers in the tooltip. It is **not** dropped from the list, and it keeps the counts it had the last time you saw it. A project on a drive in a drawer is not a project you've lost.

### 2.2 Clicking a project: the map

A single click doesn't open a project. It draws you a **map** of it: a read-only merirmaid diagram (section 21) of the folder's visible contents, with a small information node at the top carrying the path, the file count, the ¶ and W totals, and when the project was created, last opened and last edited. It's the same kind of picture cacheawl draws for a cachebox (section 12.1), pointed at a project instead.

The map is for the moment when you have four folders with plausible names and you want to know which one has the chapters in it. Look, and then decide.

When you've decided, the toolbar's **open project** button opens it. Esc, or the ribbon at the top right, takes you back to the grid. And if you already knew which one you wanted, **double-click** the tile or row and it opens without the detour.

Opening looks the same either way: the loader appears for a second or two while enough shuts down the home screen and starts the project up in its place, and then you're on the project's composure (section 4) exactly as if you had launched into that folder directly.

### 2.3 Adding a folder

The last tile in the grid — the one with the plus — is how a folder becomes a project.

Click it and macOS opens its own folder chooser. Pick any folder of notes, drafts, or documents; enough adds `rness/` to it (section 8), registers it on your home screen, and opens it. The tile says *waiting for the folder chooser…* while the dialog is up, so take as long as you like browsing.

Two kinds of folder are refused, and enough tells you which and why rather than failing vaguely:

- **`~/enough` itself, or anything inside it.** That's the install, not a project. (The `enough` command refuses the same folder for the same reason.)
- **Anything inside a cloud-synced folder** — Google Drive, Dropbox, iCloud Drive. This one isn't fussiness. A project's `rness/` is built out of symlinks back into the global defaults, and the sync clients rewrite or break symlinks as a matter of routine; you'd get a project that quietly stops following your global settings, on the machine where you didn't notice. Keep projects on local disk and sync the finished work instead.

A folder that's already on your home screen isn't an error — enough just opens it.

If the folder chooser can't be raised at all (a machine that isn't a Mac, a sandbox that refuses), the modal offers a plain text field to type the path into instead, with the reason shown above it. Everything downstream is identical.

### 2.4 Hiding a project

Home lists everything, forever, and after a year of experiments that gets long. So: **option-click any tile or row to hide it.**

Hiding is a note in enough's own list and nothing else. It says so when it asks: the folder on disk is not touched, `rness/` is not touched, and not one word in it changes. There is no "delete this project" on the home screen, and that's deliberate — deleting a project means deleting a folder full of your writing, and that is a job for Finder, where you can see what you're doing.

The **hidden** chip beside the view buttons brings them back, labelled with how many there are. Hidden projects render greyed with *hidden* on their line; option-click one to unhide it (no confirmation — it's instant and it's instantly reversible). In the app you can drive the same switch from **View → Show Hidden Projects**.

### 2.5 Closing a project, and coming back

Two doors, same room.

**In the app:** **File → Close Project**, or **⌘W**. The project's backend shuts down gracefully and the home screen comes up in its place, a second or so later.

**Anywhere, app or browser:** the **close project → home** button at the top of the ⚙ UI window (section 10). It asks first, because closing ends the session — the conversation in front of you is over, the same as it would be on a quit — and then lands you in exactly the same place ⌘W would.

Neither one touches your folder. Your files, your `rness/`, your request files, and your session logs are all exactly where you left them; only the running conversation ends.

One consequence of the new ⌘W worth knowing if you've used enough for a while: **⌘W no longer closes the window.** enough is a one-window application and closing that window quits it, so ⌘Q and the red button already covered the ground, and ⌘W had a better job to do.

And one interaction between this and the reopen setting, because it will otherwise surprise you exactly once: **closing a project does not make enough forget it.** If **Reopen Last Project on Launch** is on and you close a project, sit on home for a while, and then quit — the next launch reopens that project, not home. The toggle is the setting that decides where you start; Close Project is the button that decides where you are right now. If you want to start on home from now on, turn the toggle off.

### 2.6 What home remembers

Three small things, all machine-global — they follow you from project to project and back to home, and they are not stored in any project folder:

- **The theme and font** (section 10.1). Home wears whatever you last chose, and a theme you switch to *on* the home screen is the theme your project opens in. This is the one that used to annoy people: the launch screen and the work screen now agree, always.
- **Icons or list**, from section 2.1.
- **Whether hidden projects are showing**, from section 2.4.

Everything else about a project lives in that project's folder, where you can read it.

---

## 3. Workflow customization at a core level

If you read one section, read this one.

Most software hands you features. enough hands you mechanisms. Your chief readvisor's personality, method, and skillset are assembled fresh on every single message from markdown files sitting on your disk:

- **`AGENT.md`** — who your chief readvisor is and how they operate (section 5.3)
- **`MOTIVATION.md`** — why: values, priorities, what "done" feels like
- **Policies** — hard rules about what may be read, written, and fetched (section 5.4)
- **The active paradigm** — the reasoning framework in force right now (section 16)
- **Enabled skills** — capabilities they can reach for (section 19)
- **Enabled readvisors** — other judgments folded into the voice, or seated in a council (section 17)
- **The project profile** — what has been learned about this project (section 8.1)

Edit any of these, in the app or in any text editor, and the change takes effect on the next message. No rebuild, no restart, no plugin API. If you can write a markdown file, you can reprogram your readvisors.

### 3.1 Global vs. project-local

Everything customizable follows one pattern: **defaults live in `~/enough/defaults/`, projects link to them, and any project can break the link.**

Edit a file in `~/enough/defaults/` and every project still linked to it picks up the change. In a project, open a linked file and click **customize** — the link becomes a project-local copy, and from then on that project goes its own way while the others keep following the global default. The file tree tells you which is which at a glance: linked files render *italic and muted*, local copies render normally.

New skills and paradigms dropped into `~/enough/defaults/` appear in every project on next launch; readvisors have a second, writable home of their own at `~/enough/readvisors/` (section 17). Skills and readvisors arrive toggled off, so nothing changes behind your back; you enable them per project when you want them. A skill that enough didn't ship — one you downloaded, one a friend sent, one written for you during a session — gets read before it's allowed in. Section 19.9 covers that.

### 3.2 The three component types

| | Paradigm | Skill | Readvisor |
|---|---|---|---|
| What it is | A reasoning framework — how work gets approached | A focused capability — vocabulary, recipes, procedures | A second judgment — its own AGENT.md + MOTIVATION.md |
| How many active | Exactly one at a time | Any number toggled on | Any number toggled on |
| Lives at | `rness/paradigms/<name>.md` | `rness/skills/<name>/SKILL.md` | `rness/readvisors/<name>/` |
| Shipped examples | text-planning (home), translation, workflow-design | analyzer, anything-finder, girraph-merirmaid, lexicographer, memoir-dialectic, readvisory, scaffold, translator | block-breaker, open-skeptic |

### 3.3 Building your own

You can write these files by hand — they're markdown with a small YAML block at the top — but you don't have to. The shipped **workflow-design paradigm** (section 16.3) exists so your chief readvisor can build them with you. Say "build me a skill that…" or "make a paradigm for…" and they switch into workflow-design, ask their clarifying questions (scope? name? trigger conditions? companion files?), and write the component properly, including the `description:` frontmatter that tells future turns when to reach for it. Readvisors have their own way in — the `readvisory` skill (section 19.6), which interviews a person rather than a specification.

Things people actually build:

- A **paradigm** for each distinct mode of their work — research, drafting, revision — with explicit rules for when to switch.
- A **skill** that encodes a newsletter's voice, a citation format, a dissertation's terminology.
- A **readvisor** that's a rubber duck asking Socratic questions, or a skeptical peer reviewer, or the friend whose taste they trust most, interviewed once and kept.

The rest of this manual describes the built-ins. Read every one of them as a worked example you're allowed to copy, fork, and improve.

---

## 4. Composure — the base of the stack

Open a project and you land on a **composure**: a canvas filling the window, with the conversation in a panel beside it (section 5). This is the ground floor. It isn't a mode you enter and leave — every other mode stacks on top of it and eventually closes back down to it, and there is no way to close it, because there would be nothing underneath. (The *home screen* of section 2 is the other thing entirely — that's where you are before a project is open; this is where you are once one is.)

A composure is a `.comp` file: boxes of writing, and freehand ink, on an unbounded desk you pan and zoom around. The boxes are called **modules**. There is no save button — everything is written as you go — and the file itself is ordinary HTML, so a `.comp` opens as a plain, readable page in any browser, on a machine with no enough installed at all. That is not a side effect. A document you can only read inside the program that made it is a document you have lent to somebody.

What's around it:

- **The toolbar**, across the top of the canvas: the composure's title (type in it, click away, it's renamed), the read/edit switch, the tools, **add a module**, undo and redo, the zoom group, search, the comments toggle, and the **composures** menu — new from form…, open…, save as form….
- **The sidebar.** The project's file tree, plus the control sections: the active **paradigm**, toggles for **skills** and **readvisors**, and your **requests**. Option-click any file or folder for a context menu (new file, new folder, copy path, copy name). ⌘\ hides and shows the whole sidebar.
- **The top bar.** Buttons for the model window, the broker, the UI window, wikisink (🚰), and cacheawl; the indicators for whatever modes are currently stacked open (section 14); and, at the far right, the toggle for the readvisor panel.

### 4.1 Getting around

**Pan** with a two-finger scroll, by holding space and dragging, or with the middle mouse button. **Zoom** with a pinch, with ⌘-scroll about the pointer, with ⌘+ / ⌘− / ⌘0, or with **fit**, which frames everything you have and centres it. The zoom readout in the toolbar is a button: click it for 100%.

Three things move the view on their own, and all three are trying to help.

**The fit, whenever the room changes.** On a board — any composure that isn't shaped like a page — a change in the space the canvas has to work with ends exactly where **fit** would put you: everything in view, centred. Hide the sidebar, open or close the readvisor panel, give it the whole window and take it back, open the comments, resize the window, step the ui scale: a moment after the change settles, so does the board. It waits for you, too. It never takes the view while you're dragging, pinching or scrolling, and while a mode is stacked over the composure it holds off until you come back down to it. Zooming by hand still works as it always did; it lasts until the next time the room changes.

**The panel steps.** On a page, hiding a side panel doesn't only make the canvas wider, it makes it *bigger*: text on a page reads at about 12 point with both the sidebar and the readvisor panel open, about 14 with one of them hidden, and about 16 with both. The change animates over a fifth of a second, anchored on your caret if you're typing and on the middle of the view if you're not, so you don't lose your place.

**The page fit.** A composure shaped like a page — blank, journal, council — is centred and held at whatever zoom makes its full width fit, with a comfortable margin, until the first time you zoom by hand. A wider window shows more desk around the sheet rather than a bigger sheet. Only the width is fitted: a page is taller than most windows, so the bottom of one is always a pan away. When the room changes, a page keeps that arrangement — the width refitted, the sheet re-centred, your reading position where it was — rather than being shrunk to show the whole of a long sheet at once.

**Faces.** Zoom far enough out and each module folds down to its **face**: its title, set as large as the box allows, with the body greeked. So sixty cards read as sixty titles instead of sixty grey rectangles, and a board you built at reading size is still a board at a glance. Give a module a title and you decide what that face says. Ink, meanwhile, thins more slowly than everything else shrinks, so a zoomed-out sketch still reads as a sketch.

### 4.2 The four tools

The read/edit switch works the way it does everywhere else in enough: an eye for reading, a pencil for changing things. The tools only exist in the edit face, and each has a letter.

- **Pointer (V)** selects. Click a module, drag it to move it, drag a handle to resize it, rubber-band across empty desk to catch several. Shift-click adds or removes one. Arrow keys nudge; hold shift for a bigger step. Delete removes — with a warning first if there's writing in it, and ⌘Z to take it back. Double-click a text module and you're in the text tool inside it.
- **Text (T)** puts the caret in a text module. It can't make boxes, and clicking empty desk does nothing; that's the add-module button's job. Inside a page you get bold and italic, heading levels, lists, checklists, quotes, code, links and the four highlight colors — with the markdown you already type: `# `, `- `, `1. `, `[] `, `> ` and a fenced block all turn into the real thing as you type them. Anything you paste is reduced to plain structure first.
- **Pencil (P)** draws. Just draw; the line is smoothed and simplified when you let go. Hold **shift** while you drag and you get a straight segment with an arrowhead on the end, which is how you say *this, then that*.
- **Eraser (E)** rubs out. It's a circle that stays the same size on screen however far you have zoomed. Drag it through a line and the part under the circle goes, leaving the two ends behind as separate strokes; ⌘Z puts the line back in one piece.

Ink lies on the desk, *under* the modules, so a note can cross three cards and an arrow can join two. Pick a stroke up with the pointer tool by clicking near it, and the inspector offers the five ink colors — ink, red, blue, green, yellow — and a delete.

### 4.3 Modules: the six kinds

A **text** module is writing, with as many pages inside it as you want. The other five point at something, show you a live preview of it while you're reading, and open the real thing when you click:

- **a file in this project** — its first lines, and a click opens it exactly as clicking it in the tree would (converted documents and all). Point one at a `.comp` and the click swaps the canvas underneath you, which is what turns a board into a drill-down.
- **a wikisink article** — the lead paragraphs, and a click opens the wikisink reader there (section 11). On a machine with no archive yet the card says so, keeps the article name, and fills itself in once one is installed.
- **a link to the web** — the title and the host. A click opens it in your browser, like every other external link in the app.
- **a cached web page** — the page's text as of the last fetch, with the date and a **refresh** button. Refreshing goes through the broker exactly like any other web read, so your fetch toggles, allowlists and Tor routing all apply — and if the broker refuses, the card shows you its refusal in the broker's own words, so you know which switch to go and look at.
- **an image** — the picture, scaled to fit the box. A click opens the image viewer (section 7.9).

**add a module** opens a short list of the six. enough places and sizes the new one for you, near what you were looking at, and selects it.

### 4.4 The inspector

Select something in the edit face and a small panel appears beside it — never on top of it — with everything that applies:

- **Ten background swatches**: paper, yellow, pink, blue, green, orange, lilac and gray, plus **ink**, which is a dark card, and **clear**, which is no card at all. The last two are for structure: a dark card for a heading row, a clear one for a label that shouldn't look like a note.
- **Text size**, smaller and bigger, for that module only.
- **Pages**: add one, remove one. A module with more than one page carries page-turn buttons and an `n / N` label, and text that outgrows a page offers **continue on a new page →** rather than quietly growing forever.
- **Order**: bring forward, send back.
- **The type's own field**, when there is one — a file picker that searches your project tree as you type, a wikisink search box, an address field, a refresh policy.
- **Comment on this module**, and **delete**.

Select several modules and the inspector says how many and offers what still makes sense.

### 4.5 Forms, and saving your own

A **form** is a composure template. Five ship:

- **blank** — one page-shaped sheet, opening in the edit face with the caret already blinking in it.
- **cards** — a board of text cards in a grid, opening zoomed out to fit.
- **scaffold** — a board laid out as columns of beats, with a band across the top for the premise and a row along the bottom for the endings. It is what the `scaffold` skill (section 19.7) fills when it turns a pile of notes into a structure.
- **journal** — a dated record. One module, one entry per page. Opening a journal lands you on *today's* page with the caret in it, and that page exists only in memory until you type something, so opening the journal and thinking better of it leaves nothing behind. The entry saves itself as you go; leave without filing it and the journal reopens on that same unfinished draft. **file this entry** stamps it with the date and makes it permanently read-only — enough will refuse to change it afterwards and the caret won't go into it — and moves you on to a fresh page. Flipping back through filed entries is safe: turning a page you didn't write in saves nothing at all. You can still comment on filed text, which is rather the point of filing it.
- **council** — a room of readvisors thinking about one thing in turn. That's section 18.

**save as form…**, in the composures menu, keeps the composure you're looking at as a form of your own. It lands in `rness/composure-forms/` and joins the list from then on, in this project. A form of yours that shares a shipped form's name wins.

### 4.6 Search, comments, and taking things back

**Search** reads the plain text of every module and every page — or of one module, when exactly one is selected. Enter and shift-Enter walk the hits with a count beside the field. A hit is a *place*, not a highlight: the canvas eases over to it, turns to its page if it's on another one, and flashes briefly over the words. Nothing in your text is touched to show you where it is. Esc clears the query.

**Comments** work the way wikisink's do (section 11.2), on the same cards. Select text inside a module and comment on it, or comment on a whole module from the inspector or the menu a right-click on it opens; the comments button in the toolbar opens the panel. Reply, resolve, reopen, jump. Text you later edit away gets re-pinned to its module; a module deleted outright leaves the comment **orphaned** in the panel, labelled, never silently dropped. Comments live in a hidden file beside the `.comp` rather than in it, so the composure itself stays clean — and they work on things you can't edit at all, like a filed journal page or a council statement.

**Undo** is ⌘Z, redo is ⇧⌘Z, up to a hundred steps per composure you have open. Inside a page of text your browser's own undo takes over, which is the right one there.

### 4.7 Where composures live, and what opens on launch

New composures land in `rness/io/composure/`, named after their title and the date. They're ordinary files: copy them, put them under git, mail one to someone who has never heard of enough.

Nothing is written until something is written *in*. A composure you open and never touch leaves no file behind at all — not even an empty one. Once there is something to save, the save state in the toolbar keeps you posted: *saving…*, then *saved*, or *not saved — retrying* if the server is briefly unreachable, which is the honest message rather than a silent lie.

Which composure you land on is yours to set. The **project** window — the one with the project's name, description and folder — carries an **on launch, open** row with four answers: *a new blank page*, *the last composure used*, *a specific composure…*, or *a new one from a form…*. If the thing you pointed it at has since been renamed or deleted, enough opens a blank page and says so in one line, rather than failing at you on the way in.

And any `.comp` in the file tree opens with a click. It doesn't stack on top of what you're doing — it *becomes* what the canvas is showing, because there is only ever one floor.

### 4.8 Peeking past the stack

The mode-stack indicators in the top bar (section 14) end in a permanent square for composure. It has no close ribbon, because there's nothing to close.

Click it while you have modes stacked and every one of them hides, showing you the canvas underneath with all their state exactly as it was — your scroll position, your unsaved edits, your descent into a nested girraph. Click it again, or click any other indicator, and they come straight back. Esc while peeking restores the stack first and pops it second.

It is for the moment when the thing you need to check is on the board and you don't want to dismantle three modes to see it.

### 4.9 What your readvisors can do to a composure

They can read one, make one from a form, add and restyle and rearrange modules, write a page, save a composure as a form, and — with the `scaffold` skill (section 19.7) — turn a whole outline into a laid-out board in a single move. All of it is gated by the **composure tools** toggle in the broker (section 9); your own canvas is never gated, the same way your own wikisink and cacheawl browsing never is.

What they cannot do is write a `.comp` as a file. Both of the ordinary file-writing doors refuse the extension outright, so every change a readvisor makes goes through the same small set of operations you use, one at a time, through the same door, on the record. It means a model that gets confused cannot corrupt a document — the worst it can do is add a card you didn't want, and ⌘Z is right there.

When a readvisor changes a module while you're looking at the composure, it refreshes in place with a brief flash. The one module that never gets refreshed under you is the one you are typing in.

---

## 5. The readvisor panel

The conversation lives in a column down the right-hand side, beside whatever you're working on rather than instead of it. Your **chief readvisor** is named at the top — **Ed**, until you rename them (section 17) — with any other readvisors you have switched on listed next to them. In ordinary conversation they answer as one voice, drawing on all of those perspectives; a council (section 18) is where they speak separately.

Type a message and hit ⌘Enter, or the send button. Responses stream in live, and enough can act while your readvisor talks — reading and writing files, running shell commands, fetching pages — with each tool call appearing in the transcript as it happens. The **mic button** dictates: speech is transcribed by whisper.cpp locally, your voice never leaves the machine, and the button pulses while it records. Click again to stop.

The two voices keep to their own sides of the column: your messages sit against the left edge, your chief readvisor's against the right, each with a thin rule in its own colour along the outer edge, so a long exchange still reads as an exchange at a glance. Only the blocks move — the text inside them stays left-aligned, because right-aligned prose is hard to read. enough's own notes (a refusal, a hint, the question a `/pal` sent out) run the full width, since they aren't anybody's voice.

**A brief introduction.** An empty conversation offers one: a small link, *a brief introduction to enough*, under the waiting line. Click it, or type `/intro` at any point, and your chief readvisor puts a short tour on screen — what a project is, the composure, read/edit, the readvisors, the paradigms, the dictionary and the rest of the local reference, and where the full manual lives. No model writes it, so it arrives at once and says the same thing every time. Asking "what can you do?" or "what is enough?" as your very first message gets you the same introduction; later in a conversation those questions go to your readvisor like anything else, because by then "what is this?" usually means something on the screen. And if you open with a plain hello, your chief may offer the introduction before anything else. It follows your interface language where a translation of it exists, and is in English otherwise.

### 5.1 Docked, full, closed

Three states, one toggle at the far right of the top bar.

**Docked** is the default, and the one to live in. It's a real column beside the canvas — or beside any mode you have stacked over it — so you never have to close what you're reading in order to ask about it. On a window too narrow for that, where docking would squeeze the stage below about 480 pixels, the panel floats over the stage's right edge instead of pushing it further.

**Full** gives the panel the whole window, with the conversation centred in a readable column. This is the throwback: the old Discussion view, for when the answer is long and you want to sit with it.

**Closed** is a column of zero width. A turn that finishes while the panel is closed puts a dot on its button in the top bar — *something landed while you weren't looking*, not *there is a good answer* — and opening the panel clears it.

⌘/ opens and closes. ⇧⌘/ gives it the whole window, and ⌘/ brings it back. ⌘K always focuses the message box, opening the panel on the way if it was shut. Esc drops a full panel back to docked — but Esc is inert while the caret is in the message box, and opening the panel puts it there, so click away first. **Esc never closes a docked panel**, deliberately: that would be the one keystroke everybody hits by accident.

Open or closed is remembered per project, in that project's own files, and applied before the window first paints, so nothing lurches on launch. Full is a gesture rather than a setting, and is never remembered.

**One exception, and it's a council.** While a council is on the canvas (section 18) the panel is held closed and its toggle is disabled, with a tooltip saying why: councils and the chat share one model, and there is only one of it. Leaving the council gives you the panel back exactly as you had it — your own preference is remembered, not overwritten.

### 5.2 Sending a selection

Select text anywhere the panel can see it — a document in read/edit, a wikisink article, a module on a composure — and a chip appears above the message box naming where it came from and quoting the start of it. Send, and that passage rides along with your message, fenced, labelled with exactly what the chip said. The × on the chip drops it.

Attaching beats describing. The exact words go across, and your readvisor is told where they came from rather than having to go looking. And nothing *else* is attached: a mode sitting open behind the panel doesn't quietly stamp itself onto every message you send. What you chose is what goes.

### 5.3 AGENT.md and MOTIVATION.md

Every project carries its own copy of these two files in `rness/`. They are the root of your chief readvisor's identity here, and both are loaded into every turn.

**`AGENT.md`** is the *how*: working instructions. Tone, guardrails, conventions, standing orders. "Keep prose lowercase." "Never touch files in `archive/`." "Ask before running shell commands longer than one line."

**`MOTIVATION.md`** is the *why*: values and priorities beyond the task in front of them. What the project is for, who it serves, which tradeoffs matter (correctness over speed? brevity over thoroughness?), what "done" feels like.

Click either file in the sidebar to read it; hit **customize** to fork your project-local copy, or edit it in any editor you like. Changes land on the next message. Every other readvisor uses the same two files (section 17) — the chief isn't a different kind of thing, only the one who speaks by default.

### 5.4 The policies folder and allowlists

`rness/policies/` holds the hard rules. Not personality — law. Four policies ship by default:

- **`allowlists.md`** — the reach rules. Three lists:
  1. *File-read prefixes:* absolute paths your readvisors may read outside the project (default: `~/enough/`).
  2. *File-read-write prefixes:* paths they may also write outside the project. This list ships **empty**: out of the box, nothing is written outside your project, and it stays that way until you deliberately add a path.
  3. *Internet domains:* hosts fetched directly (the defaults include `gutenberg.org`, `en.wikipedia.org`, `en.wikisource.org`, `archive.org`, `standardebooks.org`, and Kiwix's download host). A domain that's not on the list isn't blocked — the fetch is routed through a local Tor proxy instead, so an ad-hoc lookup doesn't leave your address in some server's logs. A broker toggle can disable that fallback, making off-list fetches fail outright.
- **`context-management.md`** — how a filling context window gets noticed, and how to reset out of it gracefully without losing state (section 8.3).
- **`requests.md`** — when and how long-running work is tracked as request files (section 8.3).
- **`profile-maintenance.md`** — what belongs in the project profile and what doesn't (section 8.1).

Policies are symlinked from the defaults like everything else, so you can tighten the allowlist globally or customize it for one project that needs looser (or stricter) reach. Editing `allowlists.md` is the single most common customization in practice: add the documentation sites you trust, add a shared folder your readvisors should be able to write into, and get on with your day.

---

## 6. Read/Edit mode

Click any file in the tree and it opens in the unified read/edit mode: one mode with two *faces* — a **read face** (the eye) for reviewing, an **edit face** (the pencil) for changing text.

### 6.1 Full vs. mini, and switching between everything

Read/edit comes in two sizes. **Mini** is a side panel beside the chat: keep a reference document at your elbow while you converse. (The mini panel deliberately omits the review toolbar — it's for reading and quick edits, not markup.) **Full** takes the whole frame, for long documents and serious editing.

Switch sizes with the mini↔full button in the panel chrome. Switch faces with the face-toggle button next to it. ⌘S saves in the edit face. When what you're looking at is the twin of a converted document, the chrome also names the original and carries an **export** button for writing your changes back into it (section 7.5). And everything is dirty-guarded: if you have unsaved edits, enough prompts before letting anything discard them — navigating to another file, closing the mode, bouncing to a different document. You will not lose an hour of work to a stray click.

While a document is open, three counters appear in the top bar and keep up with your typing: **¶** paragraphs, **W** words, **C** characters. (The home screen's list view shows you the same three totals for a whole project — section 2.1.) When the window gets narrow, the buttons and the mode indicators keep their places: the project's name shortens first, down to about ten characters, and only then do the counters step out, right to left.

Like every full-frame mode, read/edit shows its icon in the top-right indicator area, with a small red-x ribbon hanging off it to close (section 14).

### 6.2 Highlighting

In the read face of any markdown document, select text and paint it one of four colors — **yellow, green, blue, pink** — from the toolbar or the popup that appears over a selection. The same toolbar offers light formatting: bold, italic, underline (⌘B / ⌘I / ⌘U).

Highlights are durable, and they live out-of-band: each document gets a hidden sidecar file (`.<filename>.highlights.json`) rather than markup spliced into your text, so the document itself stays clean. A colored band in the margin marks each highlighted line. Highlights persist across sessions, and overlapping colors stack.

Here's the part that changes how you work: your readvisors can see them. The `read_highlights` tool lists every highlight in a document by color, and `navigate_to_highlight` jumps the view to one. That turns highlighting into a channel. Paint the four paragraphs you want rewritten yellow and the two you love green, then say "rewrite the yellow parts; keep the tone of the green ones." When you mention a color, your readvisor knows you mean your highlights.

### 6.3 Supported filetypes

- **Markdown (`.md`)** renders formatted in the read face and as source in the edit face. Markdown is enough's native tongue — nearly everything the system itself writes is markdown.
- **Plain text**, and anything text-like, opens in read/edit as text.
- **`.girraph`** files open in girraph mode instead (section 20).
- **`.merirmaid`** files open in merirmaid mode instead (section 21).
- **Saved Wikipedia articles** (`article.html` inside a `wiki/` folder) open in the wikisink reader at full fidelity (section 11.2).
- **Word documents, PDFs, ebooks, decks, workbooks** open as an editable markdown **twin** — one row in the tree, one click, and an **export** button in the chrome for writing your changes back. That's section 7, and it's the whole story.
- **Images** (`.png`, `.jpg`, `.gif`, `.webp`, `.bmp`, `.svg`) open in a plain viewer (section 7.9). Images *inside* a document render in the read face like any other picture in markdown.

enough is still a text system, and it stays one: it renders markdown, not page layout. What it does with everything else is convert it — losslessly enough to work in, honestly enough to tell you what didn't survive.

---

## 7. Working with PDFs, Word documents, and other files

enough doesn't render a PDF, lay out a Word document, or draw a spreadsheet, and it doesn't pretend to. What it does instead is quieter and, for the kind of work you do here, more useful: it converts the document into markdown you can actually read, edit, highlight, and hand to your readvisors — and it keeps that markdown tied to the original, so your changes can go back.

Nothing about this is a separate mode or a separate app. You click the file. It opens.

### 7.1 The twin

Open `memo.docx` and enough writes `memo.docx.md` beside it. That second file is the **twin**: a plain markdown copy of the document, sitting in your project folder, yours to edit like anything else. Making it never modifies the original.

In the file tree you still see one row — `memo.docx`. The twin, the folder of pictures lifted out of the document (`memo.docx.assets/`), and a small hidden file recording what was converted from what are all folded into that one row, so your project keeps looking the way it looks in Finder. Click the row and the twin opens in read/edit mode (section 6) with everything that mode gives you: two faces, ⌘S, the dirty guard — and, once you go full-frame, highlights.

Two consequences worth knowing. The naming can't collide: a `memo.md` you wrote yourself is a different file from `memo.docx.md`, and enough never mixes them up. And if you delete `memo.docx` in Finder, nothing breaks — the twin quietly becomes an ordinary markdown file in your tree, which is all it ever was.

Your readvisors see the same thing you do. Ask for `report.pdf` to be read and they get the twin, converting one first if there isn't one yet; ask for something to be changed and they edit the twin, exactly where your own edits go.

### 7.2 What enough can open this way

This list comes from the app itself rather than from prose someone has to remember to update — if you're reading this outside enough, open the help center in the app (section 10) to see it filled in:

{{convert-formats}}

### 7.3 The badge in the tree

Every convertible document carries a small badge at the right edge of its row, and the badge has exactly one job: telling you whether the two halves still agree.

- **Quiet** — converted, and both sides match. Nothing to do.
- **Lit, in your color** — you've edited the twin. Those changes are in the markdown and not yet in the original; export when you're ready (section 7.5).
- **Lit, in your readvisor's color** — the original changed outside enough since it was converted. Somebody edited it in Word; a new copy landed on top of it; it came down from a shared drive.
- **Lit, in the error color** — both of the above. This is the one case enough will ask you about, and it does (section 7.7).
- **Hollow** — convertible, not converted yet. Click it and it converts.
- **Hollow, and clicking explains an extra** — a PDF, deck, or workbook on an install that can't read those yet (section 7.8).

Hover the badge for the same thing in a sentence. Clicking the badge does exactly what clicking the filename does.

### 7.4 The first time you open one

The first time you open each *type* of document, a short modal explains what's about to happen — what a twin is, where it goes, that the original stays put. One OK button. It's once per type, not once per file: your second Word document just opens.

Conversion of an office document is quick, well under a second for anything typical. You'll see a small toast in the corner while it runs, with a **cancel** button on the slow ones. PDFs take longer and get an honest progress bar (section 7.8).

### 7.5 Exporting your changes back

An open twin carries an **export** button in its chrome. One modal, three decisions:

**Which format.** The original's own format is preselected, and the rest of the export targets are there too — a Word document can go out as a PDF, an EPUB, or a self-contained HTML page. Anything the format can't do is shown greyed with the reason, never silently missing.

**A copy, or the original.** The default is a **datestamped copy** written beside the original — `memo-2026-08-19-1042.docx` — and the exact filename is previewed in the modal before you commit. Nothing is at risk: you get a new file, the old one is untouched. The second option overwrites the original in place, and it's offered only when the format you're exporting to is the original's own. Take it and enough offers you an **undo** afterwards: keep the new file, or put the old bytes back, byte for byte.

**Whether to keep it in sync** from now on — section 7.6.

A word about what survives the trip. Overwriting a `.docx` or `.odt` uses the original as a style reference, so page size, fonts, and any running headers and footers come back with your text — things markdown has no way to express and would otherwise be lost. What markdown genuinely can't carry doesn't come back: tracked changes and comments (accepted and dropped on the way in), text boxes, fields, precise image sizing. That asymmetry is why the datestamped copy is the default, and why enough never rewrites an original on its own initiative.

### 7.6 Keeping the original in sync

Tick **keep the original in sync** in the export modal and every save of the twin quietly rewrites the original too. Edit in enough, and the `.docx` on your disk is current whenever a colleague asks for it. It's a per-file setting, it applies the moment you tick it, and a small confirmation appears each time a save carries through.

It's offered for the formats that can be written back — Word, OpenDocument, Rich Text, EPUB; the "keep in sync" column in section 7.2 is the authority. PDFs can't join in, and the reason is worth stating plainly: enough can *write* a PDF from markdown, but it re-typesets the document from scratch. A synced PDF would replace your carefully laid-out original with a plain re-set of its words, every time you saved. That isn't a sync, it's a demolition, so it isn't offered.

### 7.7 When both sides changed

The original can move on without you. You edit the twin here; someone edits the `.docx` in Word; now there are two versions of the truth.

enough notices. It compares the original against what it recorded at conversion time at each moment that matters — when the tree is drawn, when you open the document, when you save, when you export — and a file that was merely *touched* (copied, backed up, opened and closed) doesn't count: the check reads contents, not just timestamps.

When both sides really have changed, you get a modal with three choices in plain words:

- **Keep my twin.** Nothing is written. The badge goes back to "you changed it" and you decide later.
- **Export over the original.** Your markdown wins; the original is rewritten, with an undo offered as usual.
- **Re-convert from the original.** The original wins; a fresh twin is written — and your old twin is stashed beside it as an undo file rather than deleted.

No choice in that modal destroys something you can't get back. That's the design rule the whole feature is built on.

### 7.8 Reading PDFs, decks, and workbooks: the PDF extra

Reading a PDF is a harder problem than reading a Word file. A `.docx` still knows what a heading is; a PDF knows only where the ink went, and getting a table, a two-column layout, or a scan back out of it takes real document models. Those models are large, so they're not in the base install — they're one click away instead: **⚙ UI window → extras → install the PDF extra**.

What it costs, honestly:

- about **250 MB to download**, and about **1 GB on disk** once installed;
- plus about **0.7 GB of model weights**, fetched once and kept in `~/enough/weights/docling/`;
- a few minutes, most of it download. The installer streams its log into the window so you can watch, and the engines switch on live — no restart.

What you get: **PDFs**, including scanned ones (the text is read out of the pixels by OCR); **PowerPoint decks**, whose slides become headed sections; and **Excel workbooks**, whose sheets become markdown tables.

Speed, measured rather than guessed, on Apple silicon: about **0.9 seconds per page** for a digital PDF, plus a one-off **~10 second** model load per conversion. So a one-page PDF takes about ten seconds, a hundred-page book about a minute and a half, and a deck or workbook a couple of seconds. Long conversions show progress and can be cancelled; cancelling leaves nothing behind — no half-written twin, no stray folders.

Two things save you a puzzled moment later. First: **writing PDFs needs none of this.** Any twin exports to PDF on every install, extra or no extra, because the typesetter that does it ships with enough. The extra is for *reading*. Second: if the "needs an extra" message appears on a machine where you're sure you installed it, read which sentence you got — the packages and the model weights are two separate downloads, and a connection that dropped mid-fetch can leave you with the first and not the second. Running the install again finishes the job and re-downloads nothing you already have.

Updates keep the extra. `update-enough.command` (and `/update-enough`) remember what you installed and ask for it again on every sync, so a routine update never quietly takes PDF reading away.

### 7.9 Images, and looking at the original

Click an image and it opens in a plain viewer: fit-to-width by default, click to switch to actual size and scroll around it, a checkerboard behind anything transparent, and the name, pixel dimensions, and file size in the header. It's read-only. enough is not an image editor and has no ambitions there.

Pictures *inside* a document are a different matter, and they come across: the photo in your Word file is extracted into `memo.docx.assets/` and renders in the twin's read face exactly like any other markdown image.

And when the twin isn't enough, a PDF's chrome carries **view original**: it opens the actual PDF in the panel, so you can check the twin against the real page. Close it and you're back in the twin, where you left off.

### 7.10 What conversion costs you, in two sentences

Two limits are worth naming out loud rather than letting you discover them. A workbook's sheets arrive as back-to-back tables with **no sheet-name headings** — the reader doesn't emit them, and enough would rather leave a gap than invent a label. And a picture pulled out of a PDF gets the alt text "Image", every time: there's no caption in the file to give it a better one.

Beyond that, the standing promise: **your originals are never modified unless you ask.** Converting only ever writes new files beside them. Export-overwrite is the single path that touches an original, it takes a deliberate click, and it leaves you an undo.

---

## 8. The project folder and `rness/`

A project is a folder. Any folder. enough adds exactly one thing to it: `rness/`, the externalized brain for this project. Everything your readvisors are, know, and remember here lives in that folder as ordinary files. You can read all of it, edit all of it, and put it under git if that's your habit.

The layout:

```
your-project/
  rness/
    AGENT.md            who your chief readvisor is    (5.3)
    MOTIVATION.md       why they work                  (5.3)
    active-paradigm     which paradigm is in force     (16)
    paradigms/          available reasoning frameworks (16)
    skills/             available skills               (19)
    readvisors/         the readvisors you can turn on (17)
    policies/           the hard rules                 (5.4)
    composure-forms/    composure forms you saved      (4.5)
    knowledge/          project memory                 (8.1)
      councils/         exported council transcripts   (18)
    io/                 input/output workspace          (8.2)
      composure/        where new composures land       (4.7)
    requests/           long-running work tracking      (8.3)
  ...your actual files...
```

Two of those arrive only when you need them: `composure-forms/` the first time you save a composure as a form, `knowledge/councils/` the first time a council concludes. An empty folder that never explains itself is a folder you end up asking about.

**If this project predates 0.3.5** it has a `rness/roles/` folder rather than `rness/readvisors/`. enough renames it the next time you open the project, in one move, carrying your project-local readvisors and your on/off settings across intact. If it can't — a read-only disk, a folder something else has a grip on — nothing breaks: everything keeps working under the old name, and the rename is tried again next launch.

Symlinked entries (italic in the tree) follow the global defaults; customize any of them to fork a local copy (section 3.1). Files you drop into the project by any means — Finder, another editor, a readvisor — are equally visible to everyone on the next turn.

A converted document (section 7) adds files here too, always beside the original and always named after it: `memo.docx` gets a twin at `memo.docx.md`, its pictures in `memo.docx.assets/`, and a hidden `.memo.docx.convert.json` recording what was converted from what and when. The tree folds all three into the original's row, but they're ordinary files on your disk — you can copy the pair to another machine, put them under git, or delete the twin and click the original again to get a fresh one. The hidden manifest is enough's bookkeeping; leave it alone and it stays accurate. Delete it and enough simply treats the document as never converted.

### 8.1 The knowledge folder

`rness/knowledge/` is per-project memory.

**`project-profile.md`** is the most useful file in the folder. Its contents are piped into the system prompt on every turn: whatever is written here is in your chief readvisor's working memory, no lookup required. They maintain it as you work — observed preferences, recurring files and people, conventions you've adopted, threads left open — and you can edit it directly. State a standing preference once in the profile instead of repeating it every session. The profile-maintenance policy keeps the file disciplined: concrete observations rather than vague labels, distillation rather than archive.

**`session-logs/`** holds a dated markdown log of each session's turns, plus the broker's journal (section 9). Append-only history. Browse it, or grep it, when you need to reconstruct what happened last Tuesday.

Beyond those two, the folder is yours. Add a `glossary/` subfolder, a lessons-learned file, background notes — your readvisors can consult whatever you put here.

### 8.2 The io folder

`rness/io/` is the pass-through workspace:

- **`input/`** — drop files here to be processed. Fetched webpages also land here automatically, converted to markdown and cached, so a page fetched once is grounded forever.
- **`output/`** — where generated artifacts land. Review, keep what's good, clear the rest.
- **`cloud-cache/`** — if you use the cloud model slot, every cloud exchange is recorded here (section 15.2). Even cloud work leaves a local, greppable paper trail.

### 8.3 Requests: how long jobs survive

This one rarely makes the quick-start tours, but it's the mechanism that makes multi-session work possible, so it's worth two minutes.

When you ask for anything that will take more than a turn or two, a **request file** opens in `rness/requests/`: a markdown record of the goal, progress checkpoints, and decisions made along the way. You don't have to ask for this. Recognizing the shape of a task is your chief readvisor's job.

The request file matters because context windows fill. enough watches conversational pressure, and — per the context-management policy — your chief readvisor checkpoints their state into the active request file before things overflow. Depending on your orchestrator setting, enough then either auto-resets (wiping the in-memory conversation and resuming fresh from the checkpoint) or pauses with a banner so you can reset when you're ready. Either way, the filesystem is the real memory, not the conversation: a fresh session reads the request file's Continuation block and picks up where things stood.

Finished requests move to `rness/requests/done/` — click **mark done** on an open request, or say so in the panel. The done folder is write-protected from your readvisors, and it doubles as an honest journal of everything the two of you have actually shipped.

---

## 9. The broker window

The broker is enough's trust anchor. Every tool call your readvisors make — every file read, file write, shell command, and web fetch — passes through it. The 🔀 broker window is where you watch and tune that.

Thirteen toggles, in groups:

| Toggle | What it controls |
|---|---|
| trace log | Whether the broker writes its journal at all |
| local models only | Whether the cloud slot (OPRO-API) is even offered in the model picker |
| read_file / write_file / shell brokered | Per-tool trace logging, one toggle each — three in all (the allowlists are *always* enforced regardless) |
| fetch_url enabled | Whether the web-fetch tool works at all |
| Tor for off-list fetches | Off-allowlist domains: route through Tor (on) or deny (off) |
| cache & convert fetches | Convert fetched pages to markdown and cache them in `rness/io/input/` |
| wikisink tools | Whether your readvisors' four wiki tools work (your own 🚰 browsing is never gated) |
| wikisink live updates | Whether update runs may contact Wikipedia at all (off = report from local state only) |
| cacheawl tools | Whether your readvisors' cachebox tools work (your own cacheawl mode is never gated) |
| composure tools | Whether your readvisors may read and edit composures (your own canvas is never gated — section 4.9) |
| forge new readvisors | Whether the `readvisory` skill may install a finished readvisor for you (section 19.6). Off keeps the interview and the drafting and leaves the filing to you |

The window's header also carries the one button in enough that changes what somebody is called: **rename chief readvisor**. It opens a small field, takes one to twenty-four characters, and the new name is in the byline of the next thing your chief says. It's a machine-wide setting, like the theme — one chief, one name, everywhere. There's no history to it: the byline is always the current name, because a rename that reached back through your transcript would read as two different people having been in the room.

Everything defaults to on: the defaults trust your readvisors with the project and keep them honest with a paper trail. That trail — the **trace journal** — lands in `rness/knowledge/session-logs/<date>-broker.md`: timestamp, tool, decision, arguments, outcome, for every brokered call. And when a toggle or allowlist blocks something, the readvisor receives a clear denial message saying what was blocked and why, so they can tell you instead of failing silently.

Notice the design principle in that table: toggles that gate your readvisors' tools never gate *your* interface. Turning off cacheawl tools doesn't lock you out of cacheawl mode. It means nothing can reach into the store on your behalf.

---

## 10. The UI window and help docs

The ⚙ UI button opens display preferences and the reference material. A small **help** button sits at the top right of that window, beside the ×: it opens this manual read-only, in the app, as a full-frame mode like any other (section 14). Beside it sits **dictionary**, which opens FEED, enough's own english dictionary (section 13).

**Reading the manual.** The manual's toolbar has a **contents** button: a list of every numbered section and subsection, beside the text when there's room for it and folded away when there isn't (in the narrow side-panel size, say), with the section you're reading marked as you scroll. **find**, or ⌘F while the manual is on top, opens a find bar: every match is marked in place with a count beside the field, Return and shift-Return walk through them, and Esc closes it. And wherever this manual says "section 7.3", those words are a link that takes you there. Every jump — a contents click, a section link, a find that carried you somewhere far — leaves a small **↩ back to where you were** pill behind it, and one click puts you back where you were reading.

The way out rides the title bar now: **close project → home**, up beside the help button, which ends this session and returns you to the home screen (section 2.5). It asks before it does it, and it notes what it doesn't do — the folder on disk is untouched. In the app you'd more likely reach for ⌘W; this button is the same thing, and it's the *only* one if you're running enough in a browser. (It isn't there on the home screen itself, where there's no project to close.)

It also holds the one thing in enough you can install from inside enough: the **extras** row for **PDF reading** (section 7.8). The row says where you stand — not installed, installing, installed, or installed-but-not-finished — and the install button streams its whole log into the window as it runs, so a long download is something you can watch rather than something you wait out. When it finishes, PDFs start opening; nothing needs restarting.

### 10.1 Themes

Four ship with enough: **Enough Default** (deep blue-violet dark), **Pastel** (pale paper, in the spirit of the Terminal "Man Page" scheme), **Wireframe**, and **Darknest**. Switching is instant, and every icon in the interface re-derives its light or dark variant on the fly.

Themes aren't hardcoded. They live in `~/enough/config/ui.json` as named blocks of color values, each applied as a CSS custom property. Copy an existing block, rename it, change the colors, reload: your theme is in the dropdown. The `_doc` block at the top of the file explains each key.

### 10.2 Fonts

Same pattern. Four shipped stacks — SF Mono, system sans-serif, Georgia serif, Courier — and your own additions welcome in the same `ui.json`. For size, see the two dials below (section 10.3) — and in a browser tab, plain old browser zoom (⌘+ / ⌘−) still works fine on top of them.

### 10.3 Sizing — ui scale and text scale

Browser zoom was always the answer here, until the desktop app arrived without a browser wrapped around it. So enough grew its own, and took the chance to do one better: two dials instead of one, on the row under the theme.

**ui scale** resizes *everything* — icons, labels, the sidebar, the chat, this very window — in steps of 0.1×. **text scale** resizes only the document in front of you: the page in read/edit, a wikisink article, the file preview, this manual in its reference mode. They multiply, and they don't interfere: a 0.9× interface around 1.5× text is a perfectly good way to read a manuscript, and the reverse is a perfectly good way to shrink one out of the way of your afternoon. Click either number to snap that dial back to 1.0× and leave the other alone.

Both are remembered **per project folder** — the manuscript you read from across the room and the notes you keep at the desk each hold their own sizes, and neither drags the other along. The home screen stays at plain size, so the dials don't appear there.

The limits breathe with your screen: roughly 0.5× to 2× on today's displays, tightening in a small window so the interface always keeps enough room to be itself, loosening on very large, very dense screens (the 8K wall of 2046 gets 3×). When a step would cross the line, the button wiggles, the number pulses red, and nothing changes — that's the whole error message.

### 10.4 Languages

The interface speaks six: English, French, Spanish, German, Chinese, and Japanese. The **ui language** dropdown on the same row switches everything you're looking at — labels, tooltips, the `(?)` bubbles, this manual — live, no restart. The choice is machine-wide, riding `ui.json` the way the theme does, so home and every project agree on it.

What it deliberately does *not* touch: your files, your chat, your readvisors. Talk to them in whatever language suits you — the local models are comfortable in all six of these — but enough keeps its own scaffolding (skills, paradigms, prompts, project files) in English, because that's the language the models read most reliably. A few generated things stay English too — lists drawn live from what's installed on *your* machine, like the skills in a bubble or the file-format table. And anywhere a translation hasn't caught up with a new English label, you'll see the English rather than a blank: less pretty, never broken. Spot one? That's a bug — [enough.support](https://enough.support) welcomes it.

### 10.5 Cheat sheets

Two columns of reference, right in the UI window.

**Keyboard shortcuts:**

| Keys | Action |
|---|---|
| esc | close the topmost open mode |
| ⌘ \ | show / hide the sidebar |
| ⌘ / | show / hide the readvisor panel |
| ⇧ ⌘ / | give the readvisor panel the whole window |
| ⌘ K | focus the chat input |
| ⌘ Enter | send the message |
| shift Enter | newline instead of send |
| ⌘ B / I / U | bold / italic / underline the selection (read face) |
| ⌘ S | save (edit face) |
| ⌥ click | file-tree context menu |
| ⇧ ⌘ D | dictionary entry for the selected word, or the word at the caret |
| right-click a word | dictionary entry menu (hold shift for the system menu) |

(On a non-Mac keyboard: Ctrl for ⌘, Alt for ⌥.)

Those are the shortcuts the interface itself handles, so they work in the app and in a browser tab alike. The app adds two of its own, from the menu bar: **⌘W** closes the project and returns you to the home screen (section 2.5) — it does *not* close the window any more — and **⌘Q** quits, as it always has.

**The markdown cheat sheet:** headings, lists, links, code, quotes — the whole quick reference, for anyone still getting fluent in markdown. Which is worth doing, since enough speaks it natively everywhere.

### 10.6 In-harness help (IHH)

The `(?)` bubbles scattered through the interface are the built-in help system: one bubble per concept — skills, readvisors, the readvisor panel, the paradigm selector, composure and its modules and tools, the journal, rness, io, knowledge, cacheawl, wikisink, the mode system, converted documents, and so on — each with a **what**, a **how**, and an **ideas** list. The skills, readvisors, and paradigms bubbles list what's actually installed in *your* project, and the converted-document bubble draws its table of file types from the app's own format registry — all generated live, so that help never drifts out of sync with reality. (The same table appears in section 7.2 of this manual, from the same source.)

Bubbles are controlled per project folder by the "help (?) bubbles" checkbox in the UI window. On by default for a new folder, and the setting sticks per folder — so your seasoned daily-driver project can go quiet while a fresh experiment keeps its training wheels.

Even the help is customizable. The content lives in one markdown file (`enough/static/help-docs.md`); editing it edits the bubbles.

---

## 11. Wikisink

Wikisink (🚰) puts an offline copy of English Wikipedia on your machine: browsable in-app, full-text searchable, readable by your readvisors, annotatable, and refreshable on demand with a change report. After setup it needs no internet at all.

### 11.1 Setup

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

Once installed, 🚰 opens the reader: back and forward, live title suggestions in the search box (Enter runs full-text search over the whole archive), a 🎲 random-article die, and a source badge that tells you whether you're reading the archive snapshot (`ZIM <date>`), a fresher copy from an update run (`live <date>`), or a preserved copy (`preserved`). Internal links stay in-app; external links open in your browser. Select a passage and it appears as a chip above the message box in the readvisor panel, ready to go across with your next message (section 5.2).

**The newer-snapshot pill.** Kiwix rebuilds these archives periodically, and you shouldn't have to go looking. When a newer build of *your* flavor exists, a small pill appears in the reader toolbar — `newer snapshot: <date> · <size>`. Click it, confirm the size, and the upgrade runs in place: same storage folder, downloaded first and swapped in only when it's finished, the old file deleted after that and not before. Your comments, saves, and 🛡 overrides carry across untouched, because none of them live inside the archive. The pill becomes the progress readout while it downloads, then disappears. enough checks for this at most once a day, never while the reader is rendering, and stays quiet when you're offline — which is the normal state of an offline-Wikipedia feature. The same upgrade is available the long way round, in the ⚙ installs list, and wikisink runs report it too (section 11.3) — but pressing the button is always yours.

### 11.2 Saving and locking articles

**Saving.** The save button offers two destinations: this project's `wiki/` folder, or the machine-global wiki cachebox (`~/enough/cacheawl/wiki/`) shared by every project. Either way, a save is a folder — `article.html`, the article byte-for-byte as the archive had it, plus `_manifest.md` carrying the title, source URL, retrieval date, and the CC BY-SA license line. Every saved article is self-describing, which means that if its text ever ends up in something you publish, the attribution you need is already sitting next to it. Click a saved `article.html` in the tree and it opens in the reader at full fidelity — infoboxes, tables and all — even when no archive is reachable. To unsave, hover over the saved folder in the tree and click the 🗑 that appears.

Saving is for *you*: offline-offline copies, publishing attribution. Your readvisors don't need saves — their tools read any article in the archive as clean text on demand.

**Comments.** Select text and hit 💬, or use the toolbar 💬 for a paragraph-level note. Threads live in the 🗨 panel: reply, resolve, reopen, jump. Comments attach to the *article*, not to any file, and they survive article updates by degrading gracefully. Text still present stays **anchored**. Text edited away gets **re-pinned** to its paragraph. A paragraph deleted outright leaves the comment **orphaned** in the panel — labeled, but never auto-deleted.

**Locking (deletion overrides).** Sometimes live Wikipedia deletes an article you relied on; the classic case is a niche topic cut for "notability" rather than quality. The 🛡 button preserves your local copy forever — served from then on with a `preserved` badge, excluded from future refreshes, still searchable. Update-run reports actually score detected deletions (notability-flavored rationales rate suspicious; copyright-violation ones rate benign), so you know which deletions deserve a look. And overriding is deliberately yours alone: a readvisor can recommend 🛡, but can never press it.

### 11.3 The wikisink update, with change report

"Wikisink" is also a verb. Every article you've saved or commented on is *watched*, and asking your readvisor to "run a wikisink" (or letting them reach for the `wikisink` tool) checks the watched set against live Wikipedia and reports back. A run:

1. refreshes changed watched articles into a local overlay (their badge flips to `live`);
2. flags **edit spikes** — watched articles suddenly being edited dozens of times a day, plus Wikipedia-wide surge candidates;
3. diffs the daily **top-1000 pageview rankings** against the last run: climbers, fallers, new entries, dropouts, and view trends for your watched articles;
4. checks for **deletions** of watched or recently-viewed articles, scored for suspicion (section 11.2);
5. notes when a **newer base snapshot** is available. Replacing the multi-GB base archive is always your call — press the pill in the reader toolbar (section 11.1) or use the ⚙ installs list. There is no tool that swaps it.

The report arrives in chat as markdown; the full uncapped version is kept under the wikisink state folder. Runs are polite to Wikipedia — batched, honest User-Agent — and resumable if interrupted, and a `report-only` run skips the refresh step. Two broker toggles govern all of it: one gates your readvisors' wiki tools entirely, the other can force runs fully offline.

---

## 12. Cacheawl

Cacheawl is the machine-global text store: the place for things you want to keep forever and reach from every project. It lives at `~/enough/cacheawl/`, hidden from every project's file tree, shared across all your enough instances. (If you ran an earlier enough, your old `infoworld/` library was dissolved into cacheawl on first launch of 0.1.6 — `personal/`, `public/`, and `wiki/` became your first three cacheboxes. Nothing was lost.)

### 12.1 Cacheboxes and their merirmaid charts

A **cachebox** is a top-level folder in the store, and it comes in two flavors. **Plain boxes** hold kept-forever text you organize yourself: a `personal` box of reference notes, a `press` box of published pieces, whatever structure serves you. **Cached replicas** are boxes *ingested* from a source — a local folder, a website, or a set of Wikipedia articles — that remember where they came from.

Every box carries a **merirmaid chart**: `_cachebox.merirmaid`, a live diagram of the box's structure, regenerated whenever the contents change. Double-click it to see the shape of a box at a glance. The chart is a *mirror*, read-only by design, because it reflects reality — to change the chart, change the box. A cheap reconcile pass keeps mirrors honest even when you drop files in from Finder behind enough's back.

Open **cacheawl mode** from the top bar for a two-pane view, project on one side, store on the other. Drag a file across to copy it. Shift-drag to move. Shift-click for a context menu, and double-click to open any file in its natural mode — girraph, merirmaid, read/edit, or the wiki reader — straight from the store.

### 12.2 The cachebox and capturing local or web documents

The **ingest bar** in cacheawl mode (or a plain conversational ask) captures outside material into a box:

- **A local path** — replicate a folder of notes or documents into the store.
- **A website** — crawl a docs site or reference site to a chosen depth (capped around 500 pages) and keep it as local markdown. Web ingests honor your fetch toggles and allowlists, Tor routing included.
- **Wikipedia** — pull a topic's articles (capped around 200) out of your wikisink archive into permanent, project-independent text.

Ingests run in the background. The box appears immediately with an "ingesting" status you can watch, and a failed ingest says so rather than pretending it finished. Your readvisors' cachebox tools (list, create, ingest) are gated by the cacheawl broker toggle; your own use of cacheawl mode never is.

Why bother? Because project folders are working space and cacheawl is library space. Ingest a framework's documentation once, and every future project can ground on it offline. Keep your evergreen reference notes in a box, and every readvisor you ever talk to can reach them. Finish an artifact and move it to a box, where it outlives its project.

---

## 13. The dictionary (FEED)

enough comes with a dictionary of its own: **FEED**, the **first-party enough english dictionary**. It's an original work, written for enough rather than licensed from somewhere else — about 96,000 headwords, each with its pronunciation, its part of speech and a plain definition, and most with examples, forms, an origin, a date of first use, a measure of how common the word is, its rhymes, its relatives, and its counterparts in five other languages.

It lives on your machine. enough ships the dictionary as plain text and builds it into a database the first time it runs after an install or an update — `~/enough/dict/feed.sqlite` — in the background, while you get on with something else. Open the dictionary while that's still going and it says *setting the type…* with a percentage, and carries on by itself. Looking a word up never touches the network: what you read, and which words you wondered about, stay on the machine.

### 13.1 Opening it

From the ⚙ UI window: the **dictionary** button sits beside **help** at the top of it (section 10). The dictionary opens as a full-frame mode, stacked like any other (section 14), so whatever you were reading is still underneath when you close it, and Esc takes you back.

It's a reading surface. You can't type into its entries or rearrange them; adding and changing words goes through your chief readvisor (section 13.7).

### 13.2 Turning pages

It's laid out like a printed dictionary rather than a list you scroll: as many entries as fit in the window, in two to four columns when there's room, and a page you turn. → and ←, Page Down and Page Up, space and shift-space all turn it; so does one swipe of the trackpad or one turn of the wheel — a page per gesture — and so do the buttons at the foot, which name the word waiting on the next page and the one left behind on the last. Home and End go to the first page and the last.

Along the top of every page run the **guide words**, as in any printed dictionary: the first word on the page at the left, the last at the right, and between them a reminder of the order you're reading in. A heading marks the place where each new group begins — a letter, a domain, a century. At the foot sit a count of where you are — which entries are on the page, out of how many (there are no page numbers, since a page holds as many entries as your window does) — and **open anywhere**, which opens the dictionary at a random page and lights up one word on it. It's a good way to lose ten minutes.

Down the right-hand edge is the **thumb index**, the notched tabs cut into the fore-edge of a big desk dictionary: a tab for each letter, each as tall as its share of the book, so you can see at a glance that S is fat and X is thin. Click a tab to open the dictionary there. The tabs follow whatever order you're reading in — domains under a domain sort, centuries under an era sort — and the one you're in is marked.

Each entry is short: the headword with dots between its syllables (*lan·tern*), its pronunciation, its part of speech, the definition, a usage label where there is one, and a few related words, each a link that turns to that word's page. ↑ and ↓ move a selection through the entries; Return, or a double-click, opens the selected one in full (section 13.5). When the dictionary is narrow — a small window, or squeezed beside a docked readvisor panel — the page becomes a single column of fuller entries, each with a small frequency gauge, a timeline of when the word arrived, and its domain.

**The part-of-speech marks.** Every entry carries a mark for each part of speech it has, in a colour and a shape, so colour is never the only signal: a **square** for a noun, a **triangle** for a verb, a **diamond** for an adjective, a **round dot** for an adverb, and a **hollow ring** for everything else. In the columns the mark sits in front of the abbreviation (*n.*, *v.*, *adj.*…) and as a thin bar down the edge of the entry; a word that is both a noun and a verb carries both.

### 13.3 Sorting, and sorting again

Alphabetical is only where it starts. **sort** orders the whole dictionary by any of nine things — alphabetical, length, domain, era, part of speech, frequency, syllables, recently added, and origin — and the button beside it reverses the order, in plain words: *short first* or *long first*, *oldest first* or *newest first*, *rarest first* or *commonest first*.

**then** is a second order inside the first, and it's where the fun is. Sort by domain, then by era, and every field of knowledge lines its words up in the order English picked them up — music's oldest words first, its newest last. Sort by length, then alphabetically, and you can read every five-letter word in the book in order, which is a puzzle-maker's whole afternoon. Sort by frequency, rarest first, and the dictionary opens on the words almost nobody uses. While a second order is on, each entry shows its value for it in the margin.

**more** opens two short rows. **try** holds a handful of one-click orders — *domain, then era*; *length, then alphabetical*; *rarest first*; *era, then alphabetical*; *newest words first*; *yours only*. **only** narrows the book to one domain, one part of speech, one frequency band, or to FEED's words or your own, and **clear** lifts the lot. The count at the top right says how many entries you're looking at, and out of how many.

The dictionary remembers your order, your filters and the page you were on, and opens there next time.

### 13.4 Finding a word

Type in the search box at the top — / or ⌘F gets you there — and the page becomes the results: every entry whose headword or definition contains what you typed, with the matches marked. Press Return on an exact word and the search steps aside and the dictionary turns to that word's page instead, in whatever order you're reading. Esc clears the search and puts you back on the page you were on before it.

A form of a word — *ran*, say — takes you to the word it belongs to, and the card for a form you looked up says which form of what it is. A word FEED doesn't have opens its card (section 13.5) with the news, a few near words it does have, and where the word would fall if it were there.

### 13.5 The word lightbox

Double-click an entry, or select it and press Return, and it opens full size, as a card over whatever you were doing. Everything FEED knows about the word is on it, and most of it is on the first view:

- the headword, its syllables and pronunciation, and its parts of speech with their marks;
- how common it is, as a gauge from 0 to 8 with the band's name beside it;
- a strip of facts — domain (and how many words share it), first use, syllables, letters, and whether the entry is FEED's or yours;
- a timeline from Old English to the 2020s, with the word's arrival marked on it;
- the **sense**, any **usage** label, **examples** with the word picked out, its **forms** (plurals, tenses and the rest, each with its own pronunciation), what it's a **form of** if it is one, and its **origin**.

Three tabs hold the rest, a click away (or 1, 2 and 3): **words** — synonyms, antonyms, related words and homophones; **rhymes** — perfect and slant; and **languages** — the word set beside its counterparts in French, Spanish, German, Chinese and Japanese, with the definition translated into each. Whatever FEED hasn't recorded for a word, the card says so, rather than leaving a blank where you'd go looking.

**Walking from word to word.** Every word listed on the card is a link, and so is every word of the definition, the examples and the origin: click one and the card becomes that word's. The trail you've walked runs across the top as **your walk**, and **‹ back** (or ⌫) retraces it a step at a time. ← and → move to the previous and next entries in the order you're reading, with *entry n of m* to say where you are. **show on its page** — **open in the dictionary**, when you came from somewhere else — closes the card and opens the dictionary at the word. Esc, the ×, or a click outside the card closes it.

### 13.6 "dictionary entry", anywhere you read

Right-click a word — in a document's read face or edit face, in the conversation, on a composure page, in a wikisink article, in this manual — and a small menu offers **dictionary entry**, which opens that word's card over whatever you're doing, and **copy**. Select a short phrase first and right-click inside it, and it's the phrase that gets looked up. Inside the dictionary the same item turns to the word's page; inside the card, it walks the card there. ⇧⌘D does the same for the selected word, or the word at the caret, with no menu at all. On a composure, the menu you already get when you right-click a module gains the same item whenever the pointer is on a word.

The system's own menu hasn't gone anywhere; it's moved over by one key. A right-click that isn't on a word — between words, past the end of a line, on a link, on a picture — gets the system menu exactly as it always did. And a right-click with **shift** held gets the system menu every time, word or no word: that's the way to spelling suggestions, the system's own look-up, and paste in a text field. The menu says so on its last line, so there's nothing to remember.

### 13.7 Your own dictionary

FEED itself never changes under you, but it isn't the only dictionary here. Beside it sits **your own**, which starts empty and holds only what you put in it: a word your family made up, a term from your field, a name you have for a thing, a coinage of your own — or your own version of a word FEED already has.

You add to it by asking your chief readvisor. "Put *glimmerwick* in my dictionary." "My team calls a meeting that should have been an email a *dronefest* — add it?" "I'd like my own definition of *draft*." The conversation goes the way a careful lexicographer's would. Your readvisor looks the word up first, and if FEED has it, says so and offers to show you rather than quietly adding a second one. If it's new, they draft what can be drafted — pronunciation, part of speech, syllables, forms — and ask you for what only you know: what it means, how and where you use it, who says it, where it came from, a question or two at a time. Then they read the entry back to you in plain words and wait for a yes before they write anything. Afterwards they'll mention, once, which parts are still empty; leaving them empty is fine.

Your words are interleaved with FEED's on every page and in every order, marked **yours**, and *yours only* under **more** shows them by themselves. A word in both dictionaries is yours: your version stands in for FEED's everywhere in enough — on the page, on the card (marked *overrides feed*), and in what your readvisor finds when they look the word up.

They live in one file, `~/enough/dict/user-dictionary.sqlite`, apart from FEED's and machine-wide like your theme, so every project sees the same words. An update rebuilds FEED's file from scratch and never touches yours.

To take one of your entries out, open its card and press **delete your entry**; it asks first. Deleting your version of a FEED word brings FEED's own entry back. Changing an entry is another conversation — "change the example for *glimmerwick*" — since the dictionary itself is only for reading.

Your readvisor has the dictionary to hand in every project, skill or no skill. The `lexicographer` skill (section 19.4) is for when you'll be adding words often: switched on, it carries FEED's whole house style into every turn, so your entries come out sounding like the rest of the book without your readvisor having to go and fetch the style guide first.

---

## 14. Multiple active mode stacking

enough's full-frame modes — read/edit, girraph, merirmaid, wikisink, cacheawl, the dictionary, this manual — don't replace each other. They **stack**, like sheets of paper. Open cacheawl, open a girraph from inside a box, open a notes file over that: three modes deep, and closing each one reveals the one beneath exactly as you left it. Same scroll position, same descent, same unsaved edits.

The top bar shows one square indicator per open mode, newest on the left. Each carries a small red-x ribbon that closes that specific mode, even a buried one. Click a buried mode's indicator to raise it to the top without disturbing anything else. When the last one closes, you're back on the composure — the empty stack (section 4).

**The base square.** At the right-hand end of those indicators sits one that is always there and has no ribbon: composure. There's nothing to close, because it's the floor. Clicking it is the **peek** gesture of section 4.8 — every stacked mode hides, you look at the canvas, and clicking it again (or any other indicator) brings them all back untouched.

**The readvisor panel isn't in the stack at all.** It's a column beside it (section 5), so a docked panel and three stacked modes coexist without either getting in the other's way, and Esc never closes the panel when it's docked.

**Esc, in order.** Esc means *back out of the innermost thing*, and the innermost thing isn't always a mode:

1. an open modal, which handles its own Esc;
2. a confirmation overlay;
3. a text field you're typing in — where Esc is deliberately inert, so a stray press can't throw away a message you were composing (a search field is the exception: there Esc clears the search first, then lets go);
4. an open composure menu;
5. a full-window readvisor panel, which drops back to docked;
6. a peek, which puts the stacked modes back;
7. and only then, the topmost mode.

Two conveniences worth knowing:

- The mini read/edit panel floats *over* a full-frame mode, so you can keep a document at your elbow while working in, say, girraph mode underneath.
- Opening a mode that's already somewhere in the stack doesn't duplicate it. It re-targets and raises the one you had.

---

## 15. The model window

The model badge in the top bar opens the model window: which brain is answering you, what else is available, and — if you choose — the cloud slot.

### 15.1 Local models: overview and usage recommendations

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

### 15.2 OpenRouter support (the OPRO-API slot)

enough is local-first, not local-only. A fifth model slot, **OPRO-API**, routes through OpenRouter to cloud models. It's off by default, deliberately effortful to enable, and honest about the trade: your prompts and outputs leave the machine, in exchange for frontier-model capability and, sometimes, lower cost than the hardware and electricity a comparable local model would demand.

Enabling it: flip **local models only** off in the broker, then click OPRO-API in the model window. A three-screen wizard walks you through it — three explicit confirmation checkboxes (you have an account, you understand billing, you understand the privacy trade), then your API key, then a live health check. The key is stored in the macOS Keychain. It is never written to any file, your readvisors have no way to read it, and the broker refuses shell commands that so much as look like attempts to get at it. Once verified, OPRO-API becomes selectable like any other model, and its settings panel offers re-test, key update, key removal, and your choice of any OpenRouter model id.

Two things keep cloud use accountable:

- **Everything is cached locally.** Every cloud exchange is written to `rness/io/cloud-cache/` with token counts and an index — a local paper trail your local readvisors can read later.
- **`cloud_pipeline`** lets your readvisors batch big jobs through the cloud slot — up to 200 steps, with per-step caching, optional per-step summarization, and a final compilation pass — writing results to disk instead of flooding the conversation. Ask for "a cloud pipeline that drafts all twelve chapter summaries" and the heavy lifting happens out-of-band, fully logged.

### 15.3 `/pal` — one question out

Sometimes your local model is out of its depth and you'd like one outside opinion. A **pal** is that: not a new setting or a second account, just the cloud model you already configured in the OPRO-API slot, reached once, by hand, from an otherwise local turn.

Start a message with `/pal` and the rest of it is the ask:

`/pal what's the current state of the art for on-device speech recognition?`

Three things then happen, in order. Your chief readvisor thinks about it here first, with what's already on the machine — its own knowledge, the files in your project, the wiki tools — and works out what it genuinely can't settle locally. It composes **one** prompt and sends that to the cloud model. Then it answers you in its own voice, saying plainly which parts came from the pal and which are its own.

**You see what left.** Before the answer arrives, the exact text that went out appears as its own bubble, word for word — never shortened, never summarized on the way to the screen — with the reply under it. Both are still there after a reload, and both are written into your session log and the cloud cache. Typing `/pal` *is* the consent; there's no second confirm step, because a confirmation that appears every time is a button you learn to click without reading. What replaces it is that you can always see what went.

**The gate is the cloud slot's gate, exactly the same one.** `/pal` works when **local models only** is off in the broker, a key is stored, and the last health check passed (15.2). If any of those isn't true, `/pal` tells you which one and how to fix it — and no turn runs, so nothing is spent and nothing leaves. Type `/` as the first character in the composer and a hint row tells you the same thing before you commit: greyed out with the reason when the slot isn't usable, and naming the model it would ask when it is, which is the difference between a command and a surprise on your bill.

**One call per `/pal`.** Your readvisor gets exactly one question out per message you start that way. If the answer didn't cover it, it says so and you can send another. And nothing leaves this machine on any other turn: without `/pal` in front, the tool simply isn't there, and a readvisor who thinks an outside opinion would help has to say so and let you decide.

If the model you're already talking to *is* OPRO-API, there's no pal to ask — the cloud model is who you're talking to. `/pal` says so, drops the token, and sends the rest of the message as usual.

**A pal is frozen at its training cutoff unless you ask for the web.** OpenRouter documents a suffix for exactly this: put `:online` on the end of the model id in the OPRO-API settings panel — `anthropic/claude-sonnet-4.5:online` — and your question goes out with web search results attached. That's OpenRouter's own feature and there's no code of ours behind it; enough passes the model id through untouched, and the bubbles show it with the suffix on, because it costs extra per search and you should be able to see that you asked for it.

---

## 16. Paradigms

A paradigm is the reasoning framework your readvisors work inside — the rules of engagement for how work happens. Exactly one is active at a time (shown at the top of the sidebar; click ● to switch), and the active paradigm's full text rides in the system prompt on every turn. Your chief readvisor also sees a one-line catalog of the others, so they can suggest a switch — or make one — when your request would be better served elsewhere. A switch made for you is nothing exotic: the paradigm's name is written to `rness/active-paradigm` and you are told it happened.

### 16.1 text-planning

**Home.** Every new project starts here, and every other paradigm comes back here when its work is done. Most of the time it doesn't feel like a framework at all: freeform conversation, one voice, for questions, reading, research, editing, file work, and drafting when you ask for drafting. It carries the standing conventions — knowing that "the yellow parts" means your highlights, where generated files go, how web pages are fetched — and it's the router that notices when one of the other paradigms would serve a request better, and switches.

It's also where a piece of writing gets planned, and that's the long runway before prose: taking a novel, an essay collection, a non-fiction book, a paper or a manifesto from "I think I want to write something" to a usable plan. None of that machinery appears until you show planning intent — "help me plan a novel", "let's structure my essay collection" — and no skill needs switching on for it. Then your chief readvisor builds one plan document with you at the project root — patiently, iteratively, across as many sessions as it takes — and, on request, generates per-section *scaffolds*: structural guides (beats, headers, voice reminders, word budgets) that you expand into prose yourself. The rule that defines it: **the plan and the scaffolds never contain prose.** They hold structure only, and your voice stays your voice. Drafting is a separate thing you can ask for in so many words — "draft chapter 1 from the plan" — and it's written to its own file, never into the plan; your readvisor won't offer it unprompted. A project that turns out to be a memoir gets pointed at `memoir-dialectic` (section 19.5), which is purpose-built for one.

**If a project was on `default`.** `default` was the home paradigm until this round, and text-planning has absorbed everything it did. A project that had `default` active is moved to text-planning the next time you open it, with your help-bubble setting left as it was. The one exception is a project where you customized `default.md` into a file of your own: that copy is yours, so the project keeps it, and keeps using it, until you switch.

### 16.2 translation

Declares offline translation a first-class capability. It pairs with the `translator` skill (section 19.8): when a request involves moving text between human languages, your readvisor switches here, and if the skill is toggled off they tell you what you're missing — and keeps telling you until you flip it on. With the skill on, you have a ~419-language local translator with no account, no rate limit, and no network dependency.

### 16.3 workflow-design

The paradigm about enough itself, active whenever you're making or changing the workflow rather than working inside it: new skills, new readvisors, new paradigms, edits to AGENT.md or MOTIVATION.md. Here your chief readvisor behaves like a thoughtful collaborator on design — clarifying questions before building (scope? name? trigger conditions?), alternatives when your first instinct could be sharper, and a tracked request file for every build, since workflow changes outlive the conversations that produce them. This is the paradigm that makes section 3 real.

---

## 17. Readvisors

A **readvisor** is a judgment you can keep: its own `AGENT.md` and `MOTIVATION.md`, the same two files that define your chief readvisor, scoped to one particular way of reading a problem. Toggle them per project in the **readvisors** section of the sidebar.

The one at the top of the readvisor panel is your **chief readvisor**, and out of the box they're called **Ed**. That name is yours to change — **rename chief readvisor**, in the broker window's header (section 9). The chief is not a different kind of thing from the rest; they're just the one who answers when you haven't asked for anyone in particular.

**Several readvisors, one voice.** Switch three on and you do not get three answers. In ordinary conversation their perspectives, their expertise and their cautions are folded into what your chief says — one voice, sometimes made of several. When a particular perspective is driving a point, you'll usually be told which. If you want them speaking separately, under their own names, in turn, that is what a **council** is (section 18).

**Three places they come from**, and the sidebar row says which:

- **shipped** — the two below, arriving as links into enough's own defaults, like every other shipped component.
- **global** — anything in `~/enough/readvisors/`, which is yours and which every project on this machine can see. It is never created for you; it appears the first time something puts a readvisor in it. (This is the writable one. The defaults folder inside a desktop install is sealed.)
- **project** — a real folder in this project's `rness/readvisors/`, belonging to this project alone.

A global and a shipped readvisor with the same name lose to a project-local one; a project's own copy always wins, which is what makes "customize" mean something.

**Removing one.** Non-shipped rows carry an ×. It asks first, because it deletes files: a project readvisor's folder goes, a global one goes from `~/enough/readvisors/` and out of this project's list. What enough shipped can't be removed this way — there's nothing there to delete that an update wouldn't put back. And a removed name is cleared from the project's off-list too, so a readvisor of the same name arriving later isn't mysteriously switched off.

### 17.1 block-breaker

A writing-block specialist, distilled from a real writer's answers about how they dissolve being stuck — which is exactly what the `readvisory` skill (section 19.6) does, and this is what its output looks like. It diagnoses before it prescribes — out of ideas, out of nerve, out of structure, and out of permission are four different problems — then reaches for constraints, rep-based brainstorming ("ten variations, then whittle"), weird reframes, and, when wanted, actual next sentences. Relentlessly anti-defeatist. Its core belief: for anyone writing voluntarily, block is always solvable, because the rules were made up and the cure can be made up too.

### 17.2 open-skeptic

An "enlightenable doomer": genuinely enthusiastic about AI where it's strong, professionally suspicious where it's oversold. Summon it when you're about to build a workflow and want the failure modes named early. It pushes back on asking AI to replicate human experience, on compounding-error chains with no human review, and on fluent confidence doing the work of expertise — while cheering for AI as collation engine, knowledge prosthesis, and rehearsal partner. It updates on evidence: show it a workflow that works and it says so, plainly.

### 17.3 Making your own

Two examples, one shape. Every readvisor is the same pair of markdown files with the same headings: `AGENT.md`, which opens with the display name you see in the sidebar and then describes how this person thinks, and `MOTIVATION.md`, which says what they care about, what they protect against, and where they go wrong. That shape is checked when one is installed — not when one is loaded, so a readvisor you wrote by hand years ago still works exactly as it did.

You can write both files yourself. The supported way is the **`readvisory` skill** (section 19.6), which builds one out of a real person's judgment by asking them questions — you, live, or someone whose advice you'd like on hand, by a questionnaire you send them. Readvisors are the cheapest way to add a reading you're missing: a Socratic rubber duck, a compliance reviewer, your target reader, the editor who always caught the thing you couldn't see.

---

## 18. Councils

A **council** is a composure where your readvisors think about one thing in turn, in writing, under their own names, while you watch it happen. It is the other half of section 17: the same readvisors who are normally folded into one voice, unfolded, disagreeing on the record.

It is an ordinary composure, so everything in section 4 still applies. The **brief** sits at the top; each statement lands beneath it as a card titled with who said it and which turn it was, tinted to that speaker — your chief on paper, you in blue, each readvisor in its own color for the life of the council, the conclusion in ink. The column re-tidies itself as it grows, however much you have been dragging things around.

Statements are the council's, not yours. You can move them, restyle them, comment on them, and zoom out and read the whole thing as a column of faces — but you cannot rewrite one, and neither can any readvisor. A transcript you can edit is a suggestion, not a record. The brief stays an ordinary module and stays editable.

### 18.1 Setting one up

New from the **council** form and you get a setup card with four fields for the brief:

- **input** — the thing being decided. One question, as sharp as you can make it.
- **parameters** — how you want it run. "Two rounds, then decide."
- **constraints** — what's off the table. "Do not rewrite the prose."
- **desired output** — one of three: **a decided answer**, written on the canvas at the end; **a document**, written to a path you name; or **a new composure**, a whole board of cards built out of what the council decided. Choose composure and a second control appears beside it for the layout — *scaffold*, where each group of cards is a column, or *cards*, where each group is a row. What each one actually does at the end is 18.3.

Then the room. The checklist starts with your chief readvisor, every readvisor you have switched on in this project, and **you**; untick anyone you don't want. Up to twelve, and no two participants may share a name, because a statement is attributed by name and two Nadias is not a council, it's a mix-up. **max rounds** defaults to 3 and can be anything from 1 to 20.

Every participant row also takes an optional **charge**: one line saying what that person is there to do. "owns continuity." "argues the reader's side." "second set of eyes." It goes into that participant's own instructions and nobody else's, last, after everything else they were told — it's the most specific thing they have, and the easiest thing for a long profile to bury. One line is the whole idea; 200 characters is the cap, and anything longer comes back refused rather than quietly trimmed, because half a charge is a different job. Charges also ride into the transcript export, next to the name, so a reader months later knows who was arguing what and why.

**convene** starts it.

### 18.2 Running it

Six controls, and they do exactly what they say.

- **next turn** — one statement, from whoever is up next.
- **run a round** — turns until the rotation comes back around. Pressed straight after convening, that's everybody; pressed with one slot left, that's one.
- **run to the end** — rounds until it hits your maximum, in the background, reporting as it goes.
- **pause** — stops after the statement being written. A half-finished statement thrown away is a worse surprise than one extra paragraph.
- **the brief** — back to the setup card, to read what everyone is working from or to change the output before concluding.
- **conclude** — the last turn. That's 18.3.

Turns stream. A card appears at the foot of the column with the speaker's name and turn number on it, fills in as the words arrive, and settles into a real module when the statement is done. The rotation is the chief and the readvisors in the order they're listed; it goes round, and a round closes when it wraps.

**You can say something at any time.** The composer at the foot of the council takes your own statement and it goes in as a card like anyone else's, tinted blue. If nobody is speaking it lands immediately; if a turn is streaming it takes the very next slot and shows as pending until it does. Either way it's an *interjection*, not a reshuffle: the readvisor whose turn it was still speaks next.

**You can put a question to a pal, too.** If the cloud slot is usable (15.3), type `/pal` and your ask into the council composer — `/pal is there a name for the pattern we're circling?` — and your chief distils the discussion so far and your question into one self-contained prompt, sends that out, and the reply lands as a statement in its own gray tint, spoken by `pal · <model id>`. The prompt that left the machine is folded into the top of that card: collapsed so twenty statements stay readable, never hidden, one click from open. Like your own statements it's an interjection — it takes a turn number but not a slot, so whoever was about to speak still speaks next, and the round doesn't move.

**The readvisor panel is closed for the duration**, with its toggle disabled and a tooltip explaining why (section 5.1). Councils and the chat share one model and there is only one of it, so a chat turn would either queue behind the council or fight it. The same is true the other way: a council control pressed while your chief is mid-answer in the chat comes back with a sentence saying so rather than quietly waiting.

### 18.3 Concluding: the answer, the document, the composure, the transcript

**conclude** runs one final turn in which your chief readvisor says where it lands — crediting the arguments that carried it, naming the disagreement that didn't resolve rather than smoothing it over, and saying what's still open. That statement is committed like any other, tinted ink.

What happens next depends on the **desired output** you chose at setup:

- **an answer** — nothing further. That final card is the output, and it's on the canvas where the council is.
- **a document** — the conclusion is written as a markdown file at a path in your project that you name. It goes through the same door as every other file write, with the same allowlists and the same undo, and it will not overwrite an existing file until you've seen the confirmation and said yes. Then a link-in module is added under the conclusion pointing at it, so the document is one click from the council that produced it.
- **a composure** — the conclusion comes back as an outline, and enough builds it into a new composure beside this one, at `rness/io/composure/<council>-output-<date>.comp`, in the layout you picked at setup. Each group is a column or a row, each card is one piece of what the council decided, and what it *didn't* settle can come through as an open question — a card titled `[gap: who owns the migration?]`, tinted so you can find them all at a glance. A link-in module goes under the conclusion pointing at the new file, so the board is one click from the council that produced it. It never overwrites an existing file: a second one gets `-2`.

That last one asks a model to write headings in an exact shape, and not every model does it first time. If the outline doesn't parse, enough asks once more with the grammar spelled out. If the second try doesn't parse either, you get the conclusion as an ordinary answer card instead, with one line saying that's what happened, and no file is written. The council's decision is never thrown away because the headings came out wrong — and it's never retried a third time, because a council that has already decided shouldn't spend two more turns on formatting.

Whichever you chose, the whole thing is also exported as plain markdown to `rness/knowledge/councils/<date>-<title>.md`: the brief, who was in the room and what each of them was there for, the round count, and every statement in order. It never overwrites an earlier export. A council that happened is a thing you can grep, cite, and hand to somebody, months after the composure has been dragged somewhere else.

A concluded council is finished. The controls go, and what it shows you from then on is the transcript path, the output, and the way to reconvene it (18.5).

### 18.4 What it costs, honestly

**It is slow, and it's meant to be.** Each statement is a complete model turn — the participant reads the brief and everything said so far, and writes. Four participants over three rounds is twelve turns, one after another, on one local model. There is no trick that makes that faster, and a council is worth convening exactly when the thinking is worth twelve turns.

**The window is shared out evenly.** Every participant who speaks gets an equal share of the model's context window — half each for two, a quarter each for four. That share has to hold the participant's own identity plus as much of the council as will fit. When it gets close to full, enough folds the oldest statements down into a single line each, a one-line memory of who said what: *Earlier in this council: Ed (turn 1): …*. The brief is never folded, and neither is the statement somebody is answering right now — a participant who can't see the thing it's replying to has nothing to say.

That folding is mechanical — it takes the first sentence, it doesn't ask a model to summarize, because a council that spends completions summarizing itself pays twice for the same window. Every turn reports whether it folded anything. When it starts folding early and often, the honest fix isn't a smaller council, it's a bigger context window in the model window (section 15.1) or a model with room for one.

### 18.5 Reconvening

A council concludes, and sometimes the question doesn't. **reconvene**, on a concluded council, starts a fresh one from it: the same room — the same participants with their names, tints and charges — the same parameters, constraints, desired output and round limit, and a brief that is the *old* brief plus what the council actually produced, set down as the thing now on the table. An answer comes across as the conclusion itself; a document or a composure comes across as a reference to the file and the first couple of thousand characters of it. The new council opens ready, at turn zero, with nobody having spoken yet.

The old council isn't re-run or rewritten. Its status, its statements and its transcript stay exactly as they were; it gains a link-in pointing at its successor, and the new one gains a link-in pointing back, so the chain reads from either end and neither end is a dead end. A council is reconvened once — after that the button is a link to the council it became.

---

## 19. Skills

A skill is a focused capability package: a folder with a `SKILL.md` (plus optional reference docs and scripts) that teaches your readvisors a procedure, a vocabulary, or a discipline. Toggle skills per project in the sidebar. Off means truly off — not in the prompt at all — and new skills arrive disabled, so nothing changes behind your back. A skill enough didn't ship gets read before it can be enabled at all (section 19.9). Turning everything off is legitimate too: pure conversation, no scaffolding, sometimes more room for the model to surprise you.

### 19.1 analyzer

Four analytical modes in one skill.

**Summarize** produces a one-page, even-handed digest of any text: what it's saying, who it's for, the author's motivation and biases, tone, key quotes.

**Proofread** does light copy-editing — typos, spelling — across full documents up to whole books, driven by Harper, a local rule-based grammar checker. It also produces a separate proof report of suggestions and repeated-phrase findings, so silent fixes and judgment calls stay distinguishable.

**Decide** hands your dilemma to three archetypal personas from a built-in roster of ten, who debate it on the record. You get a recommendation *and* the transcript, so you can weigh the reasoning rather than trust a verdict.

**Audit** reads something you haven't decided to trust yet — a skill someone sent you, a readvisor, a paradigm — and tells you what it is. First a plain-English explanation of what the thing actually does and why you'd want it, then a safety pass: prompt-injection attempts, instructions that quietly widen a readvisor's reach, epistemic red flags, and any bundled code, which also gets a deterministic scan that doesn't involve a model at all. The verdict is one of three words — **pass**, **flag**, **fail** — backed by named findings, never a score. It's read-only: audit never runs, edits, installs, or enables the thing it's reading.

Reports land in `rness/io/output/analyzer/audits/<skill-name>/`: a dated `.md` you can read like any other file, plus a small `verdict.json` beside it. Ask for an audit by name any time — "vet this before I enable it", "what does this skill actually do" — and enough also runs this mode for you, unasked, the first time you switch on a skill it didn't ship. Both doors write the same report to the same folder. Section 19.9 has that story.

### 19.2 anything-finder

A search party for the things that don't come up on the first page. Three faces, one skill.

**find** is the default, and it carries a playbook for each of ten kinds of hard-to-find thing, plus an eleventh for missions that stall. **Texts** — public-domain books, poems, historical documents. **Video** — rare, lost, and out-of-print film and TV, with watch links and their legality stated. **Images** cleared for a cover or a zine. **Products** — obscure gear, synths, instruments, and where to actually buy one. **Articles** — the paper stuck behind a paywall, found as its legitimate open copy: preprint, repository, archive. **Code** — permissively licensed repos, including libraries that never touched GitHub. **Books** — read-alikes from what you already loved. **Audio** — sheet music, MIDI, samples, gear manuals. **Assets** — fonts, textures, 3D models, stock footage. **Data** — datasets, public APIs, government documents, newspaper archives.

Results come back as *find cards*: the link, why it's the right item, and — for anything copyright-sensitive — why it's clear to use, with the publication date or the explicit license spelled out. Ask it "find me a public-domain edition of *The Moonstone* clean enough to typeset", "where can I legally watch the 1974 version", "is there an MIT-licensed library that does this". The honest answers are part of the deal: "this exists but isn't legally available" and "three candidates, I'm 70% on the second" are real results here, and where the only route is a piracy site it will say so and hand you the library, the lending system, or the storefront instead.

**patents** is the prior-art face. Give it an invention and it runs a structured novelty search across granted patents, published applications, and the non-patent literature, then reports what it found and what that means for novelty and non-obviousness — with a not-legal-advice disclaimer that stays in every report, because that's what it is. "Has this been patented?" "Prior art on a magnetic bike lock that…" "Is my idea patentable?" Databases it couldn't reach come back labeled *unchecked*, never quietly as *empty*.

**venture** is the "is this a business?" face, and it composes the other two. A market sweep for what already exists, a prior-art check, and a competitive-landscape pass over companies, open-source alternatives, adjacent products, and the graveyard of the ones that tried and shut down. What you get is an even-handed read — what's crowded, what's adjacent, what's genuinely open, and the wedge the evidence actually supports — followed by the strongest case *for* and the strongest case *against*, every point anchored to a link, and a short list of questions only you can go answer. Ask it "should I build this", "does this exist as a product", "where's the market gap here". It will not score your idea, write your business plan, or tell you to raise money. And it treats an empty field as a question, not a green light.

Output goes to `rness/io/output/anything-finder/`. Everything it fetches goes through the broker like any other web access, so an off-allowlist domain routes through Tor — and when a source refuses to answer, the report names the host and tells you what to add to `allowlists.md`, instead of leaving a silent hole in the results.

### 19.3 girraph-merirmaid

The discipline skill for enough's two diagram primitives (sections 20 and 21). The girraph half teaches proper IBIS mapping: one question per turn, no solution-jumping, your confirmation as the stopping rule. The merirmaid half carries the Mermaid-authoring rules, like keeping node labels short enough that you can comfortably edit them. The modes work without the skill; with it, your readvisor becomes a genuinely disciplined mapping partner.

### 19.4 lexicographer

The house style of the dictionary (section 13), handed to your readvisor. Your chief can look words up and add them to your own dictionary with this skill off — the dictionary is always within reach — but with it on, the whole column-by-column guide rides along on every turn: how a pronunciation is written (broad American IPA, stress marked), which of FEED's 45 domains a word belongs to, how a first use is phrased ("late 18th century", "2010s"), what the frequency bands mean, where the syllable dots go. It also carries the conversation's shape — look it up first, draft what can be drafted, ask what only you can answer, read it back, and add it only on your yes — so a word your family has been saying for twenty years comes out looking as though it was always in the book.

Ask it "is *flumpet* a word?", "add *glimmerwick* to my dictionary", "my version of *draft*, please". It isn't for translating text — that's `translator` — and it isn't a proofreader; that's analyzer.

### 19.5 memoir-dialectic

A patient, multi-session memoir collaborator. It interviews you — one or two questions at a time, never a flood — and files everything: numbered plan documents in conversation order, an index for fast resumption, a notes file for messy brain-dumps, and eventually an outline synthesis and, only if you want it, drafts. The folder is the memory. You can disappear for weeks or years and it picks up where you left off. Built for the full range from complete life story to a single milestone, with explicit handling of sensitive topics and no-go zones, and careful preservation of your own phrasing — voice matters, especially if a draft is coming.

### 19.6 readvisory

The skill that makes a readvisor (section 17), by interviewing a person rather than writing a specification.

Two ways to gather. **Live**: it interviews *you*, patiently, one or two questions at a time, twelve to eighteen in all, about how you actually decide the kind of thing this readvisor is going to be asked about. **Questionnaire**: it writes a plain, email-ready file you send to somebody whose judgment you'd like on hand — a friend, a mentor, a former editor, a parent — who answers it in their own time, and you paste the answers back whenever they arrive. A questionnaire can sit in an inbox for a week, so the whole job is tracked in a request file (section 8.3) that a session weeks later can pick up cold.

Both routes end the same way: a short follow-up pass to *you* (the step that makes a readvisor better than a transcript), then both documents drafted and shown to you to correct line by line, and only then, with your go-ahead, installed — into this project, or into `~/enough/readvisors/` where every project on the machine can see it. Both documents are read by the same safety scan a downloaded skill gets before anything is written, and the **forge new readvisors** toggle in the broker (section 9) decides whether the last step is enough's to take or yours.

It has a clear sense of what it is not for. It won't rename your chief readvisor and it won't convene a council: it makes the participants, it doesn't run the meeting.

### 19.7 scaffold

Turns a pile of thinking into a structure you can look at.

Give it a brain dump — pasted in the panel, a file in the project, or a composure that already exists — and it reads for shape rather than for sentences. It knows story shapes (arcs, beats, continuity threads, denouements, endings) and argument shapes (claim, grounds, warrant, counter-case, close) and plan shapes (goal, phases, dependencies, risks, done-when). It asks at most two clarifying questions, often none, and then hands the result to enough, which lays it out as a composure: one card per beat or section or phase, grouped into columns or rows, on the canvas in front of you (section 4.5).

The rule that makes it worth having: **it never invents material to fill a hole.** Where the structure needs something you haven't written, it writes a `[gap: …]` card instead — tinted orange, keeping the question — so the shape shows you what you still owe it. A story where you know the ending and not the turn gets a gap card saying exactly that, and it is usually the most useful card on the board.

It doesn't write the piece. It writes the structure, and every card on it is yours to edit the moment it lands.

(One name, two things, and it's worth separating them once: the *scaffolds* the text-planning paradigm generates — section 16.1 — are per-section structural guides written as markdown for you to expand into prose. This skill produces a whole composure. They get on well; a plan built in text-planning is a good brain dump to hand this one.)

### 19.8 translator

Offline translation across ~419 languages via MADLAD-400 — a ~3 GB one-time download that runs on CPU or Apple Silicon and never phones home. Short phrases to whole documents, major languages to low-resource and indigenous ones. Translate a letter, localize a README, check what a passage means, roundtrip a phrase through a third language as a meaning-preservation test — all with the network unplugged. For certain low-resource languages, an optional NLLB-200 engine offers higher quality; it carries a non-commercial license, so it's opt-in via the translation paradigm.

### 19.9 Writing your own, and trusting other people's

The eight above are demonstrations. The skill *mechanism* — markdown instructions, loaded when toggled on, with a `description:` that tells a readvisor when to engage — is the actual feature. House style guides, domain checklists, recurring report formats, data-handling procedures: if you can describe a competence in prose, you can hand it to your readvisors as a skill. Build your own with workflow-design (section 16.3), or fork one of the eight and make it yours.

The other end of that loop is the skills that arrive from somewhere else. A skill is instructions your readvisors will follow, which means a skill from the internet deserves exactly as much suspicion as any other file from the internet. So enough reads them for you:

- **What enough ships is trusted, and looks like it always has.** The eight above arrive as links into the install's own defaults. They toggle instantly. Nothing audits them.
- **Everything else is off until it's been read.** Drop a skill folder into `rness/skills/` — downloaded, sent by a friend, unzipped from a `.skill` — and it sits there disabled, marked *unverified* in the sidebar. The first time you switch it on, enough runs analyzer's audit mode over it (section 19.1) before a word of it reaches a readvisor. You watch it happen in the row: *unverified* → *auditing…* → *audited*.
- **Flagged means not enabled.** If the audit finds something, the row says *flagged* (or *failed*), the skill stays off, and you get two buttons: **read report** opens the full report in the reading view, and **enable anyway** asks you to confirm and then records the decision as yours — the finding isn't erased, it's overruled, and the row from then on reads *trusted by you*. The audit advises. You decide. (If you'd rather work in the file, editing that skill's `verdict.json` to `"verdict": "pass"` does the same thing.)
- **Edit a skill and it gets re-read.** The audit is tied to the exact bytes it read — file names and contents both. Change anything and the next time you toggle that skill on, it's audited again. That includes one you'd previously enabled anyway: an override describes one particular set of files at one particular moment, and it doesn't survive an edit.
- **A skill written for you during a session counts as untrusted too.** That's deliberate, not an oversight. When workflow-design writes a new `SKILL.md` into `rness/skills/`, enough audits that homework on first enable. It's near-instant when there's nothing to find.
- **With no model running, an audit can't finish** — and it says so, flagging with "the llm half of the audit couldn't run" rather than waving the skill through. Turn a model on and toggle again, or use *enable anyway* if you already know what's in there.

Reports live in `rness/io/output/analyzer/audits/<skill-name>/` — the same folder analyzer writes to when you ask for an audit in conversation. Two doors, one document, and it's an ordinary markdown file you can open, keep, or delete.

---

## 20. Girraph mode and the `.girraph` extension

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

In the app, clicking a `.girraph` opens girraph mode: a collapsible tree you edit directly. Click a label to rewrite it. Hover a row for add, link, and remove buttons. Click a 🦒 chip to descend into a nested map — breadcrumbs bring you back — and click a 📄 chip to read a referenced document in place. In the panel, say "girraph this" or "map this out," and your readvisor edits the same file through the same node-level operations you use, so you can both work the map at once. Deleting nodes always requires your confirmation, and children are never silently orphaned.

A girraph can also grow a **merirmaid mirror**: one click on the merirmaid button in the girraph toolbar creates a linked, auto-regenerating Mermaid diagram of the map — issues as hexagons, positions as stadiums, supports and objections stroked in their colors — that keeps itself current as the girraph changes. Map in girraph, glance in merirmaid.

Three habits make girraphs work. Phrase issues as questions ("How do we fund year two?", not "the money problem"). Attach arguments to positions, not issues — reasons are reasons for or against an *answer*. And split a branch into its own file before it sprawls. Enable the girraph-merirmaid skill and your readvisor will hold you to all three.

---

## 21. Merirmaid mode and the `.merirmaid` extension

Where a girraph maps an argument, a **merirmaid** depicts a structure. A `.merirmaid` file is a [Mermaid](https://mermaid.js.org/) diagram — flowchart, sequence diagram, state machine, ER diagram, anything Mermaid draws — with a small frontmatter header, rendered live in the browser. Locally, of course; no CDN, like everything in enough.

Two modalities, declared in the header:

- **wip** — a working whiteboard. Click any node's text and edit the label in place, with a live character count; structural changes (add a box, rewire an arrow) go through your readvisor — ask in the panel. Ask for a diagram of your pipeline, your plot, your org, and your readvisor writes the source, the browser draws it, and you tune the words.
- **mirror** — a read-only reflection of a structure that lives elsewhere: a cachebox's contents (section 12.1) or a girraph (section 20). Mirrors regenerate when their source changes. To change the picture, change the thing.

Diagrams link. A node can point at another `.merirmaid`, a `.girraph`, or a markdown document, and clicking it navigates there, breadcrumbs marking the way back — so a set of diagrams becomes a navigable atlas of your project. And when a diagram has a syntax error, merirmaid mode shows the error plus the raw source rather than a blank pane. There is always something to fix from.

The girraph-merirmaid skill (section 19.3) carries the authoring discipline for both file types. One rule of thumb from it is worth repeating here: if the honest first move is asking a question, you want a girraph; if it's drawing a box and an arrow, you want a merirmaid.

---

## 22. Where to go from here

The fastest way to make enough yours:

1. Launch it in a real project — something you actually care about.
2. Spend one session talking, and let the project profile start accumulating.
3. Edit `MOTIVATION.md` to say what the project is actually for.
4. The first time you repeat an instruction, stop. Put it in `AGENT.md` instead.
5. The first time your work has a shape the defaults don't fit, say "let's design a paradigm for this" — or a skill, or a readvisor — and let workflow-design walk you through it.

That loop — notice friction, encode the fix, keep working — is the whole game. The built-ins get you started. The system you end up with, nobody ships. You write it.

---

*enough is © 2026 Graham Smith, released under the Apache License 2.0. The dictionary's own text — FEED's words, definitions and the rest — is © 2026 Graham Smith too, but it is not under that licence: it's bundled for use inside enough, with all rights reserved for now. Wikipedia content reached through wikisink is CC BY-SA. This document: also yours to edit.*
