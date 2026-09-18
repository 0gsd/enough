<!-- enough help content. One `## <id>` section per (?) bubble.
     Edit freely: `name:`/`path:` head the section; `### what`,
     `### how`, `### ideas` bodies may contain inline HTML.
     Four expansion tokens, all resolved client-side so nothing here
     drifts from what's actually installed:
       {{skills-list}} {{roles-list}} {{paradigms-list}}
         → the live installed set (see /api/help/defaults)
       {{convert-formats}}
         → the convertible-file-type table, with this machine's engine
           availability (see /api/convert/formats). Never hand-list
           file extensions in help text; use the token. -->

## wikisink
name: wikisink
path: ~/enough/wikisink/

### what
your local, offline copy of (a slice of) english wikipedia — a single Kiwix ZIM archive read in place, never extracted, so the file manager only ever shows articles you explicitly save. the 🚰 button opens a browser-style reader with full-text search, cross-links, a random-article die, a readvisor chat pill, comments, and a single <strong>save button</strong> whose flyout offers two destinations (this project's <code>wiki/</code>, or the global <code>~/enough/cacheawl/wiki/</code> cachebox shared across projects). your readvisors can search and read the whole archive through their wiki tools.

### how
first click of 🚰 runs the setup wizard: pick a size (top-1M-articles no-images ≈ 16 GB is the default; full english ≈ 49 GB; smaller options too), pick a storage folder (external drives work), confirm, and let the resumable download run — pause, quit, resume anytime. you can keep <em>several installs</em> in different places (say, the full archive on an external drive plus a small one on the internal disk) and switch between them in the ⚙ installs list; if a drive is detached, its install just shows as unreachable until the drive returns. once installed, ask your chief readvisor to run a <strong>wikisink</strong> to refresh your saved/commented ("watched") articles from live wikipedia and get a report: watched-article changes, edit spikes, pageview movers &amp; losers, and suspicious deletions. the 🛡 button on any article is the <em>deletion override</em>: keep your local copy forever, excluded from updates. ⚙ opens the installs manager, including base-archive replacement when a newer snapshot ships. you don't have to go looking for that: when a newer build of your flavor exists, a small pill appears in the reader toolbar (<code>newer snapshot: date · size</code>) — click it, confirm the size, and the same in-place upgrade runs, downloading first and swapping in only when it's done. the check happens at most once a day, never blocks the reader, and stays silent when you're offline.

### ideas
- save the articles a project leans on into its <code>wiki/</code> folder — full-fidelity copies that open back in the reader, each with a CC BY-SA attribution manifest built in.
- comment on claims you doubt, then run a wikisink later — comments survive article updates (re-pinned or orphaned, never lost) and commented articles are watched automatically.
- when a wikisink report flags a suspicious deletion (deleted for "notability" rather than quality — the classic case), open the article and hit 🛡 before the next base-archive swap.

## project-wiki
name: wiki/
path: wiki/

### what
wikipedia articles saved into this project from the wikisink browser (the save button → "this project"). each save is a folder: <code>article.html</code> (the article exactly as the archive had it — click it to read in the wikisink viewer, full fidelity, infoboxes and all) plus <code>_manifest.md</code> (source URL, CC BY-SA license, retrieval date, origin).

### how
created automatically on your first project-level save — no setup. wikisink update runs treat everything here as <em>watched</em>: refreshed from live wikipedia and reported on. re-saving an article overwrites the folder with the freshest copy; to remove one, hover its folder in the tree a moment and click the 🗑 that appears. saved copies aren't meant to be hand-edited — they'd drift out of sync with the archive. (the save button's other choice saves to the global <code>~/enough/cacheawl/wiki/</code> cachebox instead, shared across all projects.)

### ideas
- saved articles open in the reader even when the archive's drive is detached — they're your offline-offline copies.
- your readvisors read articles through their wiki tools (clean text extraction), so they can ground themselves on saved and archived articles alike.
- wikipedia text is CC BY-SA: if part of an article ends up in something you publish, the manifest has everything you need for attribution.

## wiki-comments
name: comments
path: ~/enough/wikisink/comments/

### what
google-docs-style comments on wikipedia articles — highlight text and hit 💬, or use the toolbar 💬 to pin a comment to a paragraph. threads support replies and resolve/reopen. comments attach to the <em>article</em>, not to any saved file, so they follow the article whether it's saved, merely browsed, updated, or even deleted from live wikipedia.

### how
select text in the wikisink reader → 💬 comment. anchoring degrades gracefully when articles change: exact text match first; if the quoted text was edited away, the comment re-pins to its paragraph (marked "re-pinned"); if the paragraph is gone too it survives as "orphaned" in the panel. nothing is ever deleted automatically. commenting on an article adds it to the watched set for wikisink updates.

### ideas
- comment on statistics or claims likely to change — after a wikisink run, re-pinned comments are a signal that exact spot was edited.
- ask your chief readvisor about a highlighted passage via 🤖 in the selection popup — the passage is quoted into the chat automatically.

## paradigm-active
name: paradigm
path: rness/active-paradigm

### what
the reasoning framework your readvisors are currently working in. exactly one paradigm is active at any time; click another to switch. the active paradigm is loaded in full into the system prompt every turn, and your chief readvisor also sees a brief catalog of the other available paradigms, so they can suggest (or initiate) a switch when the work would benefit from one.

### how
click ● next to a paradigm to make it active for this project. the choice is recorded in <code>rness/active-paradigm</code>. a switch your chief readvisor initiates happens by writing that file too, and takes effect on the next turn. add new paradigms by dropping a markdown file into <code>~/enough/defaults/paradigms/</code> (or into your project's <code>rness/paradigms/</code> for project-local ones). a YAML frontmatter block at the top — <code>name:</code> and <code>description:</code> — tells your readvisors what the paradigm is for.

### ideas
- Paradigms available in this project: {{paradigms-list}}
- write a paradigm for a distinct mode of work (research vs. writing, exploration vs. execution) and switch between them as the day unfolds.
- a paradigm description is essentially "when should I use this" — write it for your chief readvisor's benefit, since that's the signal they read to recommend switching.

## requests
name: requests/
path: rness/requests/

### what
persistent task and sub-task containers. each request is a markdown file capturing the goal of your request, your chief readvisor's reasoning so far, and a continuation block so work can resume across context resets — these are the unit of long-running effort in enough. they are also helpful to continue work if you hit a context window. completed requests live alongside the active ones in <code>rness/requests/done/</code>.

### how
new requests appear in <code>rness/requests/</code> automatically as you and your chief readvisor work — click any file in the project tree to view it in the file panel. from there you can <em>mark done</em> (the file moves to <code>rness/requests/done/</code>) or <em>customize</em>. to start a request manually, drop a markdown file into <code>rness/requests/</code> with a brief goal at the top.

### ideas
- treat a request as a long-running project — break a vague intent into one and let your chief readvisor flesh it out across multiple sessions.
- browse <code>rness/requests/done/</code> as a journal of what you've actually completed — it's the most honest record of the work you and your chief readvisor have actually shipped.
- at context window auto-reset checkpoints, your chief readvisor writes a Continuation block to the active request — read it before resuming if you want to redirect.

## skills
name: skills
path: rness/skills/

### what
per-project toggle switches for skills — units of focused capability symlinked from <code>~/enough/defaults/skills/</code>. active skills add vocabulary, recipes, or behaviors your readvisors will reach for during conversation. skills enough ships are <em>trusted</em> and toggle instantly; anything else under <code>rness/skills/</code> — downloaded, gifted, or written for you by your own chief readvisor — is <em>untrusted</em> until it's been read, and the first time you switch it on, enough audits it before a word of it reaches your readvisors.

### how
click ● / ○ to toggle a skill on or off for this project. you can add project-level skills to <code>rness/skills/</code> — skill statuses are saved per project. to install new skills globally, drop a folder into <code>~/enough/defaults/skills/</code>; it appears in every project (off by default). edit a global skill at the source and the change propagates everywhere it's symlinked. an untrusted skill shows a small mark beside its name that walks <em>unverified</em> → <em>auditing…</em> → <em>audited</em>; if the audit finds something the row reads <em>flagged</em>, the skill stays off, and you get two buttons — <em>read report</em> (opens the full report) and <em>enable anyway</em> (confirms, then records the call as yours). reports land in <code>rness/io/output/analyzer/audits/&lt;skill&gt;/</code>. edit a skill's files afterwards and it's re-read on the next toggle-on.

### ideas
- Skills available in this project: {{skills-list}}
- build global or project-local skills to capture your house style or domain conventions.
- turn everything off for "pure conversation" — sometimes the model has more breathing room for emergent epiphanies with no scaffolding.
- ask your chief readvisor to <em>audit</em> a skill before you enable it (analyzer's fourth mode) — same report the first-use audit writes, just on your schedule.

## roles
name: readvisors
path: rness/readvisors/

### what
the other readers in the room. a readvisor is a folder holding AGENT.md (who they are) and MOTIVATION.md (what they care about) — one shape, fixed headings, so every readvisor works the same way despite its own voice and quirks. switched on here, they are folded into your chief readvisor's single voice in ordinary conversation; in a council composure each one speaks separately, under its own name.

### how
click ● / ○ to switch one on or off for this project. each row's tooltip names its origin: <em>shipped</em> ones come with enough (<code>defaults/readvisors/</code>) and have no remove button; <em>global</em> ones are yours, live in <code>~/enough/readvisors/</code> and show up in every project on this machine; <em>project</em> ones belong to this folder alone (<code>rness/readvisors/&lt;name&gt;/</code>). the × on a global or project row deletes it, after a confirm. the <em>readvisory</em> skill interviews you and writes a new one.

### ideas
- Readvisors available in this project: {{roles-list}}
- build a "rubber duck" that asks Socratic questions instead of answering.
- use your knowledge base's files with the <em>workflow-design</em> paradigm to make a domain expert (legal, design, copy).
- switch on two who disagree, then hold a council and let them argue it out on the canvas.

## rness
name: rness/
path: rness/

### what
the project's externalized system. rness/ is where each project's config, instructions, knowledge files, and history logs live — everything your readvisors use for this project. it sits at the top of the project so you can edit it directly with any file manager or editor; the enough UI also surfaces its contents in the sidebar.

### how
some contents are symlinks to <code>~/enough/defaults/</code> and update centrally. to diverge for a project, open a file and click <em>customize</em> — it becomes a project-local copy. add new files freely via conversations or your system's file manager; your readvisors will see any files added locally on the next turn.

### ideas
- get to know the components that drive your enough workflow and edit them wherever you like.
- treat it as living documentation — what would a new teammate, or a new readvisor, need to know?
- periodically prune stale knowledge so your readvisors don't cite obsolete decisions.

## agent-md
name: AGENT.md
path: rness/AGENT.md

### what
who your chief readvisor is and how they operate here: their working instructions for this project, used on every turn alongside MOTIVATION.md. everything in here shapes how they talk, what they do, and what they avoid.

### how
click the file to view it; hit <em>customize</em> to fork a project-local copy and edit. or open <code>rness/AGENT.md</code> in any editor — saved changes take effect on the next message.

### ideas
- add project-specific guardrails (e.g., "always double-check both spelling and factuality before finalzing an edit").
- list the naming conventions of your project so your chief readvisor doesn't have to guess (or hallucinnovate).
- encode the collaboration style you want — terse, exploratory, deferential, blunt.

## motivation-md
name: MOTIVATION.md
path: rness/MOTIVATION.md

### what
your chief readvisor's "why" for this project — values, priorities, and goals beyond the literal task list. used alongside AGENT.md every turn.

### how
same as AGENT.md — click to preview, customize for a project-local copy, or edit the file directly.

### ideas
- spell out tradeoffs you care about: correctness over speed, brevity over thoroughness, etc.
- name the user-facing experience the project aims for, in your own words.
- describe what "done" feels like — your chief readvisor will calibrate their sense of progress against that.

## paradigms
name: paradigms/
path: rness/paradigms/

### what
the full set of reasoning frameworks available in this project. each paradigm is a markdown file with a YAML frontmatter block (<code>name</code> + <code>description</code>) and a body describing how to approach work — heuristics, decision criteria, when to ask vs. act. exactly one is active at any time (see the <strong>paradigm</strong> section at the top of the sidebar to switch).

### how
symlinked from <code>~/enough/defaults/paradigms/</code>. edit globally to update behavior across every project; click <em>customize</em> on any file to fork it just for this project. new paradigms can be added simply by dropping a markdown file into the defaults folder — give it a frontmatter <code>name:</code> and <code>description:</code> so your chief readvisor knows when to recommend it.

### ideas
- Paradigms available in this project: {{paradigms-list}}
- write a paradigm for a distinct mode of work (research vs. writing, exploration vs. execution) and switch between them as the day unfolds.
- a paradigm description is essentially "when should I use this" — write it for your chief readvisor's benefit, since that's the signal they read to recommend switching.

## policies
name: policies/
path: rness/policies/

### what
hard rules your readvisors must follow — what tools to use, which files they can read or write, how to format requests, how to handle context-window pressure, and which paths are allowlisted.

### how
symlinked from <code>~/enough/defaults/policies/</code>. edit globally to update the rules for every project, or customize per-project. allowlists in particular are the most common thing to tune, as both local paths and web URLs need to be explicitly listed.

### ideas
- tighten the read/write allowlist when working with secrets or sensitive code.
- add a policy for how to handle long-running scripts or background processes.
- define your own checkpoint format if the default Continuation block doesn't fit.

## knowledge
name: knowledge/
path: rness/knowledge/

### what
project-specific knowledge that doesn't belong in <code>rness/io/</code> or <code>~/enough/infoworld/</code>: always contains <code>project-profile.md</code> (living notes your chief readvisor keeps about this project — your preferences and working style as observed here, recurring people / files, conventions adopted) and <code>session-logs/</code> (each turn's prompt and response, saved as markdown).

### how
<code>project-profile.md</code> is piped into the system prompt on every turn — both you and your chief readvisor can edit it. session logs are append-only. add new subfolders for any project-local memory you want your readvisors to consult.

### ideas
- maintain a glossary subfolder for project-specific jargon.
- let your chief readvisor write a "lessons learned" file as you iterate together.
- archive old session logs periodically so your readvisors' searches stay fast.

## io
name: io/
path: rness/io/

### what
a project-level space for files your readvisors read from (<code>input/</code>) or write to (<code>output/</code>). useful when you want a file worked on without polluting the project root.

### how
drop files into <code>rness/io/input/</code> and your readvisors will see them. anything they generate lands in <code>rness/io/output/</code> — review and move what you want to keep, then clear the rest. documents count: a word file or a pdf dropped in here opens as a markdown twin and reads like any other file, to you and to them.

### ideas
- drop a CSV or transcript into <code>input/</code> and ask your chief readvisor to summarize it.
- drop the pdf someone emailed you into <code>input/</code>, click it, and read it as markdown — the original stays exactly as it arrived.
- collect multiple draft outputs in <code>output/</code> and pick the best one (or have the model cross-evaluate them).
- clear both periodically — your readvisors don't need yesterday's scratch work in their context.

## infoworld
name: cacheawl
path: ~/enough/cacheawl/

### what
the machine-global file store, shared across every enough project. (this replaces the old <code>infoworld/</code> library — on your first launch of this version, your <code>personal/</code>, <code>public/</code>, and <code>wiki/</code> folders were moved here, each becoming a cachebox.) a <em>cachebox</em> is a top-level folder in the store: either plain text you want to keep forever, or a "cached replica" ingested from a local path, a website, or a set of wikipedia articles. the store is hidden from every project's file tree and managed through cacheawl mode + your readvisors' cachebox tools.

### how
open cacheawl mode (the topbar cacheawl button) for a two-pane view: your project on one side, the cacheboxes on the other. drag a file across to copy it, shift-drag to move; the ingest bar composes a request to your chief readvisor to pull in a path/site/wiki topic. or just ask in the panel — your readvisors can list, create, and ingest into cacheboxes (gated by the "cacheawl tools" broker toggle). each box carries an auto-generated <code>_cachebox.merirmaid</code> diagram of its contents (read-only — it regenerates from the files) and hidden metadata; you never edit those directly.

### ideas
- ingest a documentation site to a shallow depth so your readvisors can ground on it fully offline.
- keep a <code>personal</code> cachebox of reference material queryable from any project.
- save wikipedia articles you rely on to the global <code>wiki</code> cachebox — shared everywhere, not tied to one project.

## mode-system
name: read / edit mode
path: the file viewer

### what
clicking a file opens it in one unified <strong>read/edit mode</strong> with two faces — a read face (eye) and an edit face (pencil). it lives either as a mini side panel next to the chat or expanded to a full frame; use the mini↔full toggle to switch. edits are dirty-guarded, so you won't lose unsaved changes by navigating away by accident. files enough doesn't display natively still open: a word file, pdf, deck or workbook opens as its markdown <em>twin</em> (see the <em>converted document</em> bubble on any such row), and an image opens in a plain viewer with fit and 1:1 sizes.

### how
single-click a file in the tree to open it in the mini panel; expand it to a full frame when you want room. flip between the read (eye) and edit (pencil) faces with the dedicated face-toggle buttons in the read/edit chrome. every open mode shows a square indicator top-right (newest on the left) with a little red-x ribbon to close it — modes <em>stack</em>, so closing one reveals the mode beneath exactly as you left it. click a buried indicator to bring that mode forward; press <code>esc</code> to close the topmost mode. the same indicator + ribbon pattern covers every full-frame mode (wikisink, girraph, merirmaid, cacheawl, and the read-only <strong>help center</strong> reference mode, launched from the small <strong>help</strong> button at the top right of the ui window).

### ideas
- keep a file open in the mini panel while you chat — reference and conversation side by side.
- go full-frame for long documents or when editing, back to mini when you just need a peek.

## converted-file
name: converted document
path: the original, plus its markdown twin

### what
a document enough doesn't display natively — a word file, a pdf, a deck, a workbook — shown as <em>one</em> row that opens as markdown. click it and you get its <strong>twin</strong>: a markdown copy written beside the original (<code>memo.docx</code> → <code>memo.docx.md</code>) that reads, highlights and edits like any other markdown file. the twin, any images lifted out of the document (<code>memo.docx.assets/</code>) and a small hidden manifest are folded into that single row, so the tree stays as tidy as your folder looks in finder. the badge at the right edge of the row says where things stand: quiet means the twin matches the original; a highlighted badge with a dot means either you've edited the twin (and can export those changes back) or the original changed outside enough — and red means both, which is the one case enough asks you about. a hollow badge means "not converted yet", or, for pdfs, that the pdf extra isn't installed.

### how
click once. the first time you open each <em>type</em> of document a short modal explains what's about to happen; after that it just opens. edit the twin like any file, then use <strong>export</strong> in the document's chrome: the default writes a datestamped copy beside the original (<code>memo-2026-08-19-1042.docx</code>), and "overwrite the original" is one radio below it, with an undo offer afterwards. the same modal carries <em>keep the original in sync</em> — every save of the twin rewrites the original for you — offered only for the formats that can be written back. if the original changed underneath you (edited in word, re-exported from somewhere), enough notices on open or on save and asks which side wins: keep your twin, export over the original, or re-convert from the original — and the twin it replaces is stashed for undo either way. <strong>originals are never rewritten unless you ask</strong>, and every overwrite leaves an undo.

### ideas
- what enough can open this way, and what it can write back: {{convert-formats}}
- ask your chief readvisor to read a document by name — <code>read_file</code> on <code>report.pdf</code> hands them the twin, converting one first if there isn't one yet.
- reading pdfs, powerpoint decks and excel workbooks needs the <strong>pdf extra</strong> (⚙ ui window → extras): about 250 MB to download, about 1 GB installed, plus about 0.7 GB of document models in <code>~/enough/weights/docling/</code>. <em>writing</em> pdfs out of markdown works on every install, no extra.

## merirmaid
name: merirmaid
path: *.merirmaid

### what
enough's flavor of a <a href="https://mermaid.js.org/" target="_blank" rel="noopener">Mermaid</a> diagram: plain-text diagram source with a small header, rendered live to a picture in the browser (flowcharts, sequence diagrams, state machines, ER diagrams — anything Mermaid supports). two kinds: a <em>wip</em> diagram you can tweak, and a <em>mirror</em> that reflects some structure (like a cachebox's contents) and is read-only.

### how
ask your chief readvisor to draw or revise a diagram — they write the <code>.merirmaid</code> source; opening the file renders it. in a wip diagram you can click a node's text to edit the label in place (with a live character count); structural changes go through your chief readvisor via the chat pill. nodes can link to other diagrams or docs — click them to follow, with breadcrumbs to step back. a bad diagram shows the error plus the raw source, never a blank pane. mirror diagrams show a "mirror" badge instead of edit handles.

### ideas
- have your chief readvisor diagram a process or architecture you're reasoning about, then refine it in conversation.
- link a set of diagrams together with clickable nodes to build a navigable map.
- pair it with girraphs: a girraph for the argument, a merirmaid for the flow.

## cacheawl
name: cacheawl
path: ~/enough/cacheawl/

### what
the machine-global store of <em>cacheboxes</em> — top-level folders holding text you want to keep forever, or cached replicas ingested from a local path, a website, or wikipedia articles. shared across every project and hidden from project file trees. this is where the old <code>infoworld</code> library now lives.

### how
open cacheawl mode from the topbar for the two-pane view (project ↔ cacheboxes): drag to copy a file between them, shift-drag to move, and use the ingest bar to ask your chief readvisor to pull a source into a box. or just say so in the panel — your readvisors can list, create, and ingest into boxes when the "cacheawl tools" broker toggle is on (url ingests also respect your fetch_url toggles). every box shows an auto-generated diagram of its contents (<code>_cachebox.merirmaid</code>, read-only) and keeps hidden metadata you don't touch.

### ideas
- ingest a docs site or a folder of notes so your readvisors can work from it offline.
- move a finished artifact into a cachebox to keep it out of the working project but still reachable everywhere.
- double-click a box's diagram to see its shape at a glance in the merirmaid viewer.

## footnotes
name: footnotes
path: (inside your markdown files)

### what
real footnotes for texts in progress. write <code>[^1]</code> in the prose and put <code>[^1]: the note itself</code> at the bottom of the file — in the reading view each note appears as a small card in the margin, aligned with its marker. cards are editable in place: flip one to edit, save or cancel, done. the file on disk stays plain, portable markdown.

### how
in the editor, type <code>[^]</code> and it becomes the next footnote number automatically, or use the toolbar's insert-footnote button at the cursor. drop a new footnote between two existing ones and everything after it renumbers itself, definitions included. named footnotes like <code>[^aside]</code> are left exactly as you wrote them. a marker with no definition yet shows an empty card — type into it and saving writes the definition for you.

### ideas
- draft with quick <code>[^]</code> markers and fill the bodies later from the margin cards.
- footnote numbering stays clean no matter what order you write in — paginate relies on this, so a "prose complete" text needs no cleanup pass.

## paginate
name: paginate
path: (next to the markdown it came from)

### what
turns a completed text into a cleanly typeset pdf — real pages, chapters starting fresh, footnotes reconciled to wherever you want them (on the page, at each chapter's end, or gathered in a final footnotes section). the markdown stays the editable original; the pdf is a dated snapshot beside it, e.g. <code>book-2026-08-23.pdf</code>.

### how
open a markdown file in the reading view and hit the paginate button in the toolbar. pick a page size (letter, a4, trade paperback… or custom), portrait or landscape, one of the bundled fonts, a margin, and optionally page numbers and running headers (your text, or the chapter name). 2-up puts two pages per sheet; booklet interleaves them so a double-sided print folds into a stapleable book. "bring pdf into enough" adds a page-by-page view with arrow-key turning and fullscreen. every exported pdf secretly carries its own source markdown, so importing one back into a project restores the text — footnotes and all — exactly.

### ideas
- proof a draft in trade size with chapter-end notes before deciding the final shape.
- print a booklet of a short piece: booklet layout, half letter, staple the result.
- send someone the pdf; if it ever comes back without the original, importing it recovers the markdown perfectly.

## composure
name: composure
path: rness/io/composure/

### what
the canvas that is always there behind everything else — the base layer of the window, not a mode you enter or leave. a <strong>composure</strong> is a <code>.comp</code> file: boxes of writing (<em>modules</em>) and freehand ink on an unbounded desk you pan and zoom. it opens in any browser as a plain page, with no enough installed, because the file itself is ordinary html.

### how
the toolbar runs along the top: the title (rename by typing and clicking away), the read/edit switch, the tools, undo/redo, the zoom group, search, the comments panel and the composures menu. pan with two fingers, space-drag or the middle button; zoom with pinch, ⌘-scroll, ⌘+ / ⌘− / ⌘0, or "fit". there is no save button — everything is written as you go, and a composure you open and never touch writes no file at all. zoom far enough out and each module folds down to its <em>face</em>: its title, as large as fits, with the body greeked, so sixty cards read as sixty titles.

### ideas
- keep one board per project as the map you look at before you start writing.
- a <code>.comp</code> module that points at another <code>.comp</code> turns a board into a drill-down: clicking it swaps the canvas underneath you.
- select a passage inside a module and it rides along with your next message to your readvisor, fenced and labelled.

## composure-modules
name: modules
path: (inside a .comp file)

### what
the boxes on a composure. a <strong>text</strong> module is writing — headings, lists, checklists, quotes, links, highlights — with as many pages as you want inside it. the other five point at something: a <strong>file</strong> in this project, a <strong>wikisink</strong> article, a <strong>web link</strong>, a cached <strong>web page</strong>, or an <strong>image</strong>. a pointing module shows a live preview while you are reading, and clicking it opens the real thing.

### how
the add-module button opens a short list of the six types. with a module selected in edit mode the inspector appears beside it: background swatch, text size, pages, front/back, the type's own field (a file picker, an article search, an address), and a comment button. drag to move, drag a handle to resize, arrow keys to nudge (hold shift for a bigger step), delete to remove — with a warning first if there is writing in it, and ⌘Z to take it back. text that outgrows its box offers you a new page rather than silently growing.

### ideas
- give a module a title and it keeps its name when you zoom out past reading size.
- the <code>ink</code> and <code>clear</code> swatches are for structure — a dark card for a heading row, a clear one for a label that is not a card at all.
- point a module at a file you keep re-opening; the board becomes a desk with the right papers already on it.

## composure-tools
name: tools
path: (the composure toolbar)

### what
four tools, and they only exist while you are editing: <strong>pointer</strong> (V) selects, moves, resizes and rubber-bands; <strong>text</strong> (T) puts the caret inside a module; <strong>pencil</strong> (P) draws; <strong>eraser</strong> (E) rubs out. ink is freehand polylines lying on the desk, under the modules, so a note can cross three cards and an arrow can join two.

### how
with the pencil, just draw — the line is smoothed and simplified when you let go. hold <strong>shift</strong> while you drag and you get a straight segment with an arrowhead on the end. the eraser is a circle that stays the same size on screen however far you zoom; dragging it through a line removes the part under the circle and leaves the two ends as separate strokes, and ⌘Z puts the line back in one piece. pick a stroke up with the pointer tool by clicking near it — the inspector then offers the five ink colours, and delete removes it. lines thin more slowly than the drawing shrinks, so a zoomed-out sketch still reads as a sketch.

### ideas
- circle the three cards that belong together before you decide what the group is called.
- shift-drag arrows between modules to show what follows what, then move the modules; the arrow stays where you drew it, which is usually the honest answer.
- draw in red over a board you are reviewing and erase the marks when you have dealt with them.

## journal
name: journal
path: rness/io/composure/

### what
a composure form for keeping a dated record. one module, one entry per page. opening a journal lands you on <em>today's</em> page with the caret already in it — and that page exists only in memory until you type something, so opening the journal and thinking better of it leaves nothing behind.

### how
write. the entry saves itself as you go, and if you leave without filing it the journal reopens on that same unfinished draft. when the entry is done, hit <strong>file this entry</strong>: the page is stamped with the date and becomes permanently read-only — enough will refuse to change it afterwards, and the caret will not go into it. filing moves you on to a fresh page for next time. flipping back through filed entries is safe: turning a page you did not write in saves nothing at all. you can still comment on filed text, which is the point of filing it.

### ideas
- file at the end of a working session rather than the end of a day; the date is a fact, not a deadline.
- comment on an old filed entry when it turns out to have been wrong — the record stays, and the second thought sits beside it.
- ask your readvisor to read the journal when you want a summary of where a long piece of work actually went.

## readvisor-panel
name: readvisor panel
path: (the right-hand panel)

### what
the conversation, in a column of its own beside whatever you are working on. your <strong>chief readvisor</strong> is named at the top, with any other readvisors you have switched on listed next to them — in ordinary conversation they answer as one voice, drawing on all of those perspectives.

### how
⌘/ opens and closes it; ⇧⌘/ gives it the whole window and ⌘/ again brings it back. it sits beside the canvas or beside any open mode, so you never have to close what you are reading in order to ask about it. select text — in a document, in a wikisink article, in a composure module — and a chip appears above the message box showing exactly what is about to be attached; × drops it. when a turn finishes while the panel is closed, a dot appears on its button in the top bar.

### ideas
- leave it docked while you write and ask in passing; it is a colleague at the next desk, not a window you open.
- attach a selection rather than describing it — the exact words go across, fenced, with where they came from.
- give it the whole window when you want to read a long answer properly, then dock it again to act on it.

## council
name: council
path: (a composure whose form is council)

### what
several readvisors and you, thinking about one thing in turn, in writing, on the canvas. a council is an ordinary composure with the brief at the top and one card per statement below it, tinted per speaker and headed with a name and a turn number. the statements belong to the engine: you can move them, restyle them, ink over them and comment on them, but not rewrite them.

### how
fill in the brief — input, parameters, constraints, desired output — tick who is in the room, give anyone a one-line <em>charge</em> if they are here for something particular ("owns continuity", "argues the reader's side"), set the max rounds, and press convene. then drive it: <em>next turn</em> takes one statement, <em>run a round</em> goes all the way around, <em>run to the end</em> runs to the round cap, <em>pause</em> stops it, <em>conclude</em> asks the chief for the decision. the composer at the bottom is yours: whatever you say takes the next slot without costing anybody their turn, and <code>/pal</code> typed there sends one distilled question out to the cloud model and brings the answer back as a statement. concluding writes what the council decided in the shape you chose — a highlighted card, a markdown file at a path of your choosing, or a whole new composure of cards beside this one — and exports the transcript to <code>rness/knowledge/councils/</code>. a concluded council can be <em>reconvened</em>: a new council with the same room, the same charges and what this one decided as its starting point.

### ideas
- give one readvisor the counter-case and find out whether it survives contact with the others.
- a charge is the cheapest way to stop three readvisors saying the same thing three ways.
- set the output to a document when the decision should leave the canvas as a file you can cite, or to a composure when what you want is the shape of the decision rather than its paragraphs.
- say something yourself the moment a council starts circling; an interjection is cheaper than another round.
- reconvene rather than starting over when the answer was right but not finished.

## chief-readvisor
name: chief readvisor
path: (the name on every reply)

### what
the one readvisor you are always talking to. it has a name — Ed out of the box — and that name signs every reply in the conversation, heads the readvisor panel, and speaks first in a council. the name is global: one per machine, kept beside your theme and your interface language rather than inside any one project.

### how
press the rename button beside the × in this header, type a new name and save. 1 to 24 characters: letters and digits, plus space, hyphen, apostrophe and full stop, in whatever script you like. every surface showing the name catches up straight away, with no reload. a council that has already spoken keeps the name its statements were signed with — statements are attributed by name, and a rename part-way through would read as two people.

### ideas
- pick something you would say out loud; you are going to be reading it all day.
- rename before you convene a council, not during one.

## pal
name: pal
path: (the OPRO-API model slot)

### what
one question, sent out, in the open. a <strong>pal</strong> is the cloud model you already configured in the OPRO-API slot, reached once, by hand, from a turn that is otherwise entirely local. there is no pal setting, no pal account and no second switch: if the cloud slot works, a pal works, and if it does not, the broker's usual explanation is the whole story. typing <code>/pal</code> is the consent — there is no confirm step, because a confirm step that appears every time is a button people learn to click. what replaces it is that the prompt which leaves this machine is shown to you word for word, before the answer, every time, live and after a reload.

### how
start a message with <code>/pal</code> and the rest of it is the ask: <code>/pal what is the state of the art for on-device speech recognition?</code>. type <code>/</code> as the first character and a hint row appears above the composer naming the model that would be reached; tab or a click completes it, and when the cloud slot is shut the row greys itself and says why. your readvisor then thinks it through here first — its own knowledge, the files in this project, the wiki tools — works out what it genuinely cannot settle locally, sends <strong>one</strong> refined prompt, and answers you in its own voice saying which parts came from the pal. one call per <code>/pal</code> message. the same command works in a council's composer, where the chief distils the brief and the whole transcript into the prompt; the answer lands as a gray statement whose first line folds away what was sent.

### ideas
- put <code>:online</code> on the end of the model id in the OpenRouter settings — <code>anthropic/claude-sonnet-4.5:online</code> — and your pal answers with the web in front of it. it bills extra per search, and it is the fix for a model frozen at its training cutoff.
- keep it for what a local model cannot have: this week's news, a library released last month, a second opinion on a judgement call you have already made.
- read the outgoing bubble before you read the answer. it is the only place that shows exactly what left, and it is there on purpose.
