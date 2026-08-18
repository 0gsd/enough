<!-- enough help content. One `## <id>` section per (?) bubble.
     Edit freely: `name:`/`path:` head the section; `### what`,
     `### how`, `### ideas` bodies may contain inline HTML.
     {{skills-list}} / {{roles-list}} / {{paradigms-list}} expand to
     the live installed set (see /api/help/defaults). -->

## wikisink
name: wikisink
path: ~/enough/wikisink/

### what
your local, offline copy of (a slice of) english wikipedia — a single Kiwix ZIM archive read in place, never extracted, so the file manager only ever shows articles you explicitly save. the 🚰 button opens a browser-style reader with full-text search, cross-links, a random-article die, an agent chat pill, comments, and a single <strong>save button</strong> whose flyout offers two destinations (this project's <code>wiki/</code>, or the global <code>~/enough/cacheawl/wiki/</code> cachebox shared across projects). the agent can search and read the whole archive via its wiki tools.

### how
first click of 🚰 runs the setup wizard: pick a size (top-1M-articles no-images ≈ 16 GB is the default; full english ≈ 49 GB; smaller options too), pick a storage folder (external drives work), confirm, and let the resumable download run — pause, quit, resume anytime. you can keep <em>several installs</em> in different places (say, the full archive on an external drive plus a small one on the internal disk) and switch between them in the ⚙ installs list; if a drive is detached, its install just shows as unreachable until the drive returns. once installed, ask the agent to run a <strong>wikisink</strong> to refresh your saved/commented ("watched") articles from live wikipedia and get a report: watched-article changes, edit spikes, pageview movers &amp; losers, and suspicious deletions. the 🛡 button on any article is the <em>deletion override</em>: keep your local copy forever, excluded from updates. ⚙ opens the installs manager, including base-archive replacement when a newer snapshot ships. you don't have to go looking for that: when a newer build of your flavor exists, a small pill appears in the reader toolbar (<code>newer snapshot: date · size</code>) — click it, confirm the size, and the same in-place upgrade runs, downloading first and swapping in only when it's done. the check happens at most once a day, never blocks the reader, and stays silent when you're offline.

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
- the agent reads articles through its wiki tools (clean text extraction), so it can ground itself on saved and archived articles alike.
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
- ask the agent about a highlighted passage via 🤖 in the selection popup — the passage is quoted into the chat automatically.

## paradigm-active
name: paradigm
path: rness/active-paradigm

### what
the reasoning framework the agent is currently using. exactly one paradigm is active at any time; click another to switch. the active paradigm is loaded in full into the system prompt every turn, and the agent also sees a brief catalog of the other available paradigms so it can suggest (or initiate) a switch when the work would benefit from one.

### how
click ● next to a paradigm to make it active for this project. the choice is recorded in <code>rness/active-paradigm</code>. agent-initiated switches happen by writing that file too, and take effect on the next turn. add new paradigms by dropping a markdown file into <code>~/enough/defaults/paradigms/</code> (or into your project's <code>rness/paradigms/</code> for project-local ones). a YAML frontmatter block at the top — <code>name:</code> and <code>description:</code> — tells the agent what the paradigm is for.

### ideas
- Paradigms available in this project: {{paradigms-list}}
- write a paradigm for a distinct mode of work (research vs. writing, exploration vs. execution) and switch between them as the day unfolds.
- a paradigm description is essentially "when should I use this" — write it for the agent's benefit, since that's the signal it reads to recommend switching.

## requests
name: requests/
path: rness/requests/

### what
persistent task and sub-task containers. each request is a markdown file capturing the goal of your request, the agent's reasoning so far, and a continuation block so work can resume across context resets — these are the unit of long-running effort in enough. they are also helpful to continue work if you hit a context window. completed requests live alongside the active ones in <code>rness/requests/done/</code>.

### how
new requests appear in <code>rness/requests/</code> automatically as you and the agent work — click any file in the project tree to view it in the file panel. from there you can <em>mark done</em> (the file moves to <code>rness/requests/done/</code>) or <em>customize</em>. to start a request manually, drop a markdown file into <code>rness/requests/</code> with a brief goal at the top.

### ideas
- treat a request as a long-running project — break a vague intent into one and let the agent flesh it out across multiple sessions.
- browse <code>rness/requests/done/</code> as a journal of what you've actually completed — it's the most honest record of your work with this agent.
- at context window auto-reset checkpoints, the agent writes a Continuation block to the active request — read it before resuming if you want to redirect.

## skills
name: skills
path: rness/skills/

### what
per-project toggle switches for skills — units of focused capability symlinked from <code>~/enough/defaults/skills/</code>. active skills add vocabulary, recipes, or behaviors the agent will reach for during conversation. skills enough ships are <em>trusted</em> and toggle instantly; anything else under <code>rness/skills/</code> — downloaded, gifted, or written for you by your own agent — is <em>untrusted</em> until it's been read, and the first time you switch it on, enough audits it before a word of it reaches the agent.

### how
click ● / ○ to toggle a skill on or off for this project. you can add project-level skills to <code>rness/skills/</code> — skill statuses are saved per project. to install new skills globally, drop a folder into <code>~/enough/defaults/skills/</code>; it appears in every project (off by default). edit a global skill at the source and the change propagates everywhere it's symlinked. an untrusted skill shows a small mark beside its name that walks <em>unverified</em> → <em>auditing…</em> → <em>audited</em>; if the audit finds something the row reads <em>flagged</em>, the skill stays off, and you get two buttons — <em>read report</em> (opens the full report) and <em>enable anyway</em> (confirms, then records the call as yours). reports land in <code>rness/io/output/analyzer/audits/&lt;skill&gt;/</code>. edit a skill's files afterwards and it's re-read on the next toggle-on.

### ideas
- Skills available in this project: {{skills-list}}
- build global or project-local skills to capture your house style or domain conventions.
- turn everything off for "pure conversation" — sometimes the model has more breathing room for emergent epiphanies with no scaffolding.
- ask the agent to <em>audit</em> a skill before you enable it (analyzer's fourth mode) — same report the first-use audit writes, just on your schedule.

## roles
name: roles
path: rness/roles/

### what
consultant agents you can summon in conversation, sourced from <code>~/enough/defaults/roles/</code>. each role is a folder containing AGENT.md (instructions) and MOTIVATION.md (drives) — the same pair of files that defines the main agent, but scoped to a complementary (or adversarial) persona.

### how
click ● / ○ to enable a role for this project. add new roles globally by creating <code>~/enough/defaults/roles/&lt;name&gt;/</code> with AGENT.md and MOTIVATION.md inside; project-level works and edits propagate, just like skills.

### ideas
- Roles available in this project: {{roles-list}}
- build a "rubber duck" that asks Socratic questions instead of answering.
- use your knowledge base's files with the <em>workflow-design</em> paradigm to craft a domain expert (legal, design, copy) role.

## rness
name: rness/
path: rness/

### what
the project's externalized system. rness/ is where each project's config, instructions, knowledge files, and history logs live — everything the agent uses for this project. it sits at the top of the project so you can edit it directly with any file manager or editor; the enough UI also surfaces its contents in the sidebar.

### how
some contents are symlinks to <code>~/enough/defaults/</code> and update centrally. to diverge for a project, open a file and click <em>customize</em> — it becomes a project-local copy. add new files freely via conversations or your system's file manager; the agent will discover any files added locally on its next turn.

### ideas
- get to know the components that drive your enough workflow and edit them wherever you like.
- treat it as living documentation — what would a new teammate or agent or role need to know?
- periodically prune stale knowledge so the agent doesn't cite obsolete decisions.

## agent-md
name: AGENT.md
path: rness/AGENT.md

### what
the agent's working instructions for this project. used for every turn alongside MOTIVATION.md. everything in here shapes how the agent talks, what it does, and what it avoids.

### how
click the file to view it; hit <em>customize</em> to fork a project-local copy and edit. or open <code>rness/AGENT.md</code> in any editor — saved changes take effect on the next message.

### ideas
- add project-specific guardrails (e.g., "always double-check both spelling and factuality before finalzing an edit").
- list the naming conventions of your project so the agent doesn't have to guess (or hallucinnovate).
- encode the collaboration style you want — terse, exploratory, deferential, blunt.

## motivation-md
name: MOTIVATION.md
path: rness/MOTIVATION.md

### what
the agent's "why" for this project — values, priorities, and goals beyond the literal task list. used alongside AGENT.md every turn.

### how
same as AGENT.md — click to preview, customize for a project-local copy, or edit the file directly.

### ideas
- spell out tradeoffs you care about: correctness over speed, brevity over thoroughness, etc.
- name the user-facing experience the project aims for, in your own words.
- describe what "done" feels like — the agent will calibrate its sense of progress against that.

## paradigms
name: paradigms/
path: rness/paradigms/

### what
the full set of reasoning frameworks available in this project. each paradigm is a markdown file with a YAML frontmatter block (<code>name</code> + <code>description</code>) and a body describing how to approach work — heuristics, decision criteria, when to ask vs. act. exactly one is active at any time (see the <strong>paradigm</strong> section at the top of the sidebar to switch).

### how
symlinked from <code>~/enough/defaults/paradigms/</code>. edit globally to update behavior across every project; click <em>customize</em> on any file to fork it just for this project. new paradigms can be added simply by dropping a markdown file into the defaults folder — give it a frontmatter <code>name:</code> and <code>description:</code> so the agent knows when to recommend it.

### ideas
- Paradigms available in this project: {{paradigms-list}}
- write a paradigm for a distinct mode of work (research vs. writing, exploration vs. execution) and switch between them as the day unfolds.
- a paradigm description is essentially "when should I use this" — write it for the agent's benefit, since that's the signal it reads to recommend switching.

## policies
name: policies/
path: rness/policies/

### what
hard rules the agent must follow — what tools to use, which files it can read or write, how to format requests, how to handle context-window pressure, and which paths are allowlisted.

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
project-specific knowledge that doesn't belong in <code>rness/io/</code> or <code>~/enough/infoworld/</code>: always contains <code>project-profile.md</code> (living notes the agent keeps about this project — your preferences and working style as observed here, recurring people / files, conventions adopted) and <code>session-logs/</code> (each turn's prompt and response, saved as markdown).

### how
<code>project-profile.md</code> is piped into the system prompt on every turn — both the agent and you can edit it. session logs are append-only. add new subfolders for any project-local memory you want the agent to consult.

### ideas
- maintain a glossary subfolder for project-specific jargon.
- let the agent write a "lessons learned" file as you iterate together.
- archive old session logs periodically so agent searches stay fast.

## io
name: io/
path: rness/io/

### what
a project-level space for files the agent reads from (<code>input/</code>) or writes to (<code>output/</code>). useful when you want the agent to process a file without polluting the project root.

### how
drop files into <code>rness/io/input/</code> and the agent will see them. anything the agent generates lands in <code>rness/io/output/</code> — review and move what you want to keep, then clear the rest.

### ideas
- drop a CSV or transcript into <code>input/</code> and ask the agent to summarize.
- collect multiple draft outputs in <code>output/</code> and pick the best one (or have the model cross-evaluate them).
- clear both periodically — the agent doesn't need yesterday's scratch work in its context.

## infoworld
name: cacheawl
path: ~/enough/cacheawl/

### what
the machine-global file store, shared across every enough project. (this replaces the old <code>infoworld/</code> library — on your first launch of this version, your <code>personal/</code>, <code>public/</code>, and <code>wiki/</code> folders were moved here, each becoming a cachebox.) a <em>cachebox</em> is a top-level folder in the store: either plain text you want to keep forever, or a "cached replica" ingested from a local path, a website, or a set of wikipedia articles. the store is hidden from every project's file tree and managed through cacheawl mode + the agent's cachebox tools.

### how
open cacheawl mode (the topbar cacheawl button) for a two-pane view: your project on one side, the cacheboxes on the other. drag a file across to copy it, shift-drag to move; the ingest bar composes a request to the agent to pull in a path/site/wiki topic. or just ask the agent — it can list, create, and ingest into cacheboxes (gated by the "cacheawl tools" broker toggle). each box carries an auto-generated <code>_cachebox.merirmaid</code> diagram of its contents (read-only — it regenerates from the files) and hidden metadata; you never edit those directly.

### ideas
- ingest a documentation site to a shallow depth so the agent can ground on it fully offline.
- keep a <code>personal</code> cachebox of reference material queryable from any project.
- save wikipedia articles you rely on to the global <code>wiki</code> cachebox — shared everywhere, not tied to one project.

## mode-system
name: read / edit mode
path: the file viewer

### what
clicking a file opens it in one unified <strong>read/edit mode</strong> with two faces — a read face (eye) and an edit face (pencil). it lives either as a mini side panel next to the chat or expanded to a full frame; use the mini↔full toggle to switch. edits are dirty-guarded, so you won't lose unsaved changes by navigating away by accident.

### how
single-click a file in the tree to open it in the mini panel; expand it to a full frame when you want room. flip between the read (eye) and edit (pencil) faces with the dedicated face-toggle buttons in the read/edit chrome. every open mode shows a square indicator top-right (newest on the left) with a little red-x ribbon to close it — modes <em>stack</em>, so closing one reveals the mode beneath exactly as you left it. click a buried indicator to bring that mode forward; press <code>esc</code> to close the topmost mode. the same indicator + ribbon pattern covers every full-frame mode (wikisink, girraph, merirmaid, cacheawl, and the read-only <strong>help center</strong> reference mode, launched from the small <strong>help</strong> button at the top right of the ui window).

### ideas
- keep a file open in the mini panel while you chat — reference and conversation side by side.
- go full-frame for long documents or when editing, back to mini when you just need a peek.

## merirmaid
name: merirmaid
path: *.merirmaid

### what
enough's flavor of a <a href="https://mermaid.js.org/" target="_blank" rel="noopener">Mermaid</a> diagram: plain-text diagram source with a small header, rendered live to a picture in the browser (flowcharts, sequence diagrams, state machines, ER diagrams — anything Mermaid supports). two kinds: a <em>wip</em> diagram you can tweak, and a <em>mirror</em> that reflects some structure (like a cachebox's contents) and is read-only.

### how
ask the agent to draw or revise a diagram — it writes the <code>.merirmaid</code> source; opening the file renders it. in a wip diagram you can click a node's text to edit the label in place (with a live character count); structural changes go through the agent via the chat pill. nodes can link to other diagrams or docs — click them to follow, with breadcrumbs to step back. a bad diagram shows the error plus the raw source, never a blank pane. mirror diagrams show a "mirror" badge instead of edit handles.

### ideas
- have the agent diagram a process or architecture you're reasoning about, then refine it in conversation.
- link a set of diagrams together with clickable nodes to build a navigable map.
- pair it with girraphs: a girraph for the argument, a merirmaid for the flow.

## cacheawl
name: cacheawl
path: ~/enough/cacheawl/

### what
the machine-global store of <em>cacheboxes</em> — top-level folders holding text you want to keep forever, or cached replicas ingested from a local path, a website, or wikipedia articles. shared across every project and hidden from project file trees. this is where the old <code>infoworld</code> library now lives.

### how
open cacheawl mode from the topbar for the two-pane view (project ↔ cacheboxes): drag to copy a file between them, shift-drag to move, and use the ingest bar to ask the agent to pull a source into a box. or talk to the agent directly — it can list, create, and ingest into boxes when the "cacheawl tools" broker toggle is on (url ingests also respect your fetch_url toggles). every box shows an auto-generated diagram of its contents (<code>_cachebox.merirmaid</code>, read-only) and keeps hidden metadata you don't touch.

### ideas
- ingest a docs site or a folder of notes so the agent can work from it offline.
- move a finished artifact into a cachebox to keep it out of the working project but still reachable everywhere.
- double-click a box's diagram to see its shape at a glance in the merirmaid viewer.
