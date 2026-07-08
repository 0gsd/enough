# Wikisink — local Wikipedia for `enough`

Wikisink (the 🚰 button) puts an offline copy of English Wikipedia on
your machine: browsable in-app, full-text searchable, readable by the
agent, annotatable with persistent comments, and refreshable on demand
with an intelligence report on what changed. No internet needed after
setup — and when you *are* online, a "wikisink" run keeps the articles
you care about current.

## Setup

Click 🚰 for the first time. The wizard asks three things:

1. **Size.** Current builds from [Kiwix](https://kiwix.org) (all text-only
   unless noted):

   | flavor | what's in it | approx. size |
   |---|---|---|
   | `top1m_nopic` *(default)* | the 1M most-read articles | ~16 GB |
   | `all_nopic` | every English article | ~49 GB |
   | `top_nopic` | top ~50k articles | ~2.1 GB |
   | `top_mini` | top ~50k, intro sections only | ~320 MB |
   | `simple_all_nopic` | complete Simple English Wikipedia | ~950 MB |

   Live sizes are fetched from `download.kiwix.org` when the wizard opens.
   The "top" selections are built by Kiwix from Wikimedia pageview data
   and refresh with each snapshot (every 1–3 months).

2. **Storage.** Default `~/enough/wikisink`; any folder works, external
   drives included. About 5% headroom beyond the archive size is required.

3. **Confirmation.** The download is resumable (HTTP ranges), survives
   quits and restarts, and runs in the background — pause/resume/cancel
   from the same modal. Everything else in enough keeps working.

The archive is a single `.zim` file read in place — never extracted into
a million files, never shown in the file manager. Only articles you
explicitly save become visible files.

## Multiple installs

You can keep **several archives in several places** — say, the full
49 GB `all_nopic` on an external drive plus a small `top_mini` on the
internal disk as a fallback. Each completed download registers as an
*install*; the one marked **active** is what the reader and the agent
serve.

Click ⚙ (or 🚰 when the active archive is unreachable) to open the
installs list: every install shows its location and a live availability
dot. From there you can **switch to** any reachable install, **+ add an
install** in a new location, or **forget…** one you no longer want
tracked (the `.zim` file itself is never deleted — reclaim the space
yourself in Finder).

Detaching the drive that holds the active archive doesn't lose
anything: the install stays registered and simply shows as unreachable.
Reattach the drive and it works again — no re-setup. Meanwhile you can
switch to another install or add one. Your comments, watch registry,
and deletion overrides are independent of any single install and carry
across switches.

## Browsing (Wikisink view)

Once installed, 🚰 opens the reader on your last-viewed page (or a random
article the first time). Toolbar, left to right:

- **← →** history · **search box** with live title suggestions (Enter =
  full-text search over the whole archive) · **🎲** random article
- **source badge** — `ZIM <date>` (archive snapshot), `live <date>`
  (refreshed from Wikipedia by a wikisink run), or `preserved`
  (deletion override)
- **💬** add a comment pinned to the paragraph in view
- **📥** save to this project's `wiki/` folder (created on first save)
- **🌐** save to `~/enough/infoworld/wiki/` (shared across all projects)
- **🛡** deletion override (see below) · **🗨** comments panel · **⚙** settings

Internal links stay in-app; external links open in your browser. The
chat pill at the bottom talks to the agent: with text selected, your
question carries the quoted selection; without, it carries the article
reference so the agent can read the page itself (`read_wiki_article`).

A saved article is a **folder** — `wiki/<slug>/` in the project (📥) or
`~/enough/infoworld/wiki/<slug>/` (🌐) — containing `article.html` (the
article **exactly as the archive had it**) and `_manifest.md` (title,
source URL, **CC BY-SA 4.0** license, retrieval date, origin), so every
saved article is self-describing — and ready-made for attribution if
the text ends up in something you publish.

Clicking `article.html` in the file tree opens it **in the wikisink
reader** at full fidelity — infoboxes, tables, and all — even when no
archive is installed or its drive is detached. Its links browse the
live archive as usual. Saved copies aren't meant to be hand-edited
(they'd silently drift out of sync with the archive); re-save from the
reader to refresh one instead.

To **unsave**, hover the article's folder in the file tree for a
moment and click the 🗑 that appears. The saved copy is deleted after
confirmation; the article stays in the archive, and comments and
deletion overrides are untouched. The agent reads articles as clean
extracted text through its wiki tools either way, so saving is for
*you* (offline-offline copies, publishing attribution), not a
prerequisite for the agent.

## Comments

Select text → **💬 comment**, or use the toolbar 💬 for a paragraph-level
note. Threads live in the 🗨 panel: reply, resolve/reopen, delete, jump.

Comments attach to the *article*, not to a saved file, and they survive
updates by degrading gracefully:

1. **anchored** — the quoted text still exists; shown highlighted.
2. **re-pinned** — the exact text was edited away; the comment pins to
   its original paragraph (by position, then by section heading).
3. **orphaned** — paragraph's gone too; the comment stays in the panel,
   clearly labeled.

Nothing is ever deleted automatically.

## The wikisink (updating)

Ask the agent — "run a wikisink" — or it happens via the `wikisink`
tool. Every article you've **saved** (project or infoworld) or
**commented on** is *watched*. A run:

1. checks watched articles against live Wikipedia (batched, polite,
   descriptive User-Agent);
2. refreshes changed ones into a local **overlay** (the reader then
   serves the overlay copy — badge flips to `live`);
3. detects **edit spikes** — any watched article with >30 edits in a day
   or >10/day average since the last run, plus Wikipedia-wide top-edited
   candidates (flagged if they're in your local archive);
4. snapshots the daily **top-1000 pageview rankings** and diffs against
   the previous run: climbers, fallers, new entries, dropouts, plus
   view trends for your watched articles;
5. checks for **deletions** of watched or recently-viewed articles and
   scores how suspicious each one looks (see below);
6. notes when a **newer base snapshot** is available (replacing the
   multi-GB base is always your call, via ⚙).

The report arrives in chat as markdown — copy it from there; it is not
saved into your project unless you ask. The full uncapped version lands
in `<storage>/state/run-<timestamp>/report.md`. Interrupted runs younger
than 24h resume instead of refetching. `<scope>report-only</scope>`
skips the overlay refresh.

Two broker toggles govern all of this (🔀 pane, "wikisink" group):
`wikisink tools` gates the agent's access entirely; `live updates` can
force runs fully offline (report from local state only).

## Deletion overrides

Sometimes Wikipedia deletes an article that was useful — a niche
programming language cut for "notability" rather than quality. The run
report scores deletions: AfD/PROD/notability rationales score
suspicious; copyvio/vandalism/author-request score benign; watched and
commented articles score higher.

To keep one: open the article in the reader and click **🛡**. Your local
copy is copied into the preserved store, served forever (badge:
`preserved`), excluded from all future refreshes, and still searchable.
Click 🛡✓ to lift the override; the preserved file stays on disk until
you delete it yourself. Overriding is deliberately UI-only — the agent
can recommend it but never do it.

## Storage layout

```
<each install's folder>         (~/enough/wikisink, /Volumes/…, wherever)
  wikipedia_en_*.zim            that install's base archive
  downloads/*.part              resumable partial download
~/enough/wikisink/              your data, independent of any install*
  overlay/                      live-refreshed watched articles
  preserved/                    deletion-overridden articles
  comments/                     comment threads (one JSON per article)
  rankings/                     daily top-1000 pageview snapshots
  state/run-*/                  update-run scratch + full reports
~/enough/config/wikisink.json   config, install registry, watch registry, overrides
```

\* Setups created before multi-install support keep their data beside
the original archive location; fresh setups always keep it on the local
disk so comments and preserved articles never vanish with a drive.

None of this appears in the file manager — even if you point storage
inside a project folder, the tree filter hides it.

## Troubleshooting

- **"isn't reachable — the drive may be detached"** — the active
  archive lives on a volume that isn't mounted. Reattach the drive
  (nothing to redo; it heals instantly), or click 🚰 and switch to
  another install / add a new one.
- **Download interrupted?** Click 🚰 → resume. Partial data is kept in
  `downloads/*.part`; resume picks up mid-byte via HTTP ranges.
- **"not enough free space"** — the wizard needs archive size + 5%.
  Point storage at a bigger volume; external drives are fine.
- **`libzim` missing** — the reader returns "libzim isn't installed";
  run `uv sync` in the enough checkout and restart.
- **Sizes look stale in the wizard** — the live listing fetch failed;
  approximate fallback sizes are shown. Reopen when online.
- **Agent can't see wiki tools** — check the 🔀 broker pane's wikisink
  toggles.

## Licensing

Wikipedia text is **CC BY-SA 4.0** (legacy content CC BY-SA 3.0 + GFDL).
Personal offline reference is unrestricted; if you fold article text
into published work, attribute and share alike — every save's
frontmatter/manifest carries what you need. See
[Wikipedia:Copyrights](https://en.wikipedia.org/wiki/Wikipedia:Copyrights).

## Agent tools reference

| tool | args | does |
|---|---|---|
| `wiki_search` | `<query>`, `<limit>` | full-text search, titles + paths |
| `read_wiki_article` | `<path>` or `<title>` | article → markdown, cached under `rness/io/input/`, preview returned |
| `wiki_status` | — | install/watch/override state, last run |
| `wikisink` | `<scope>watched\|report-only</scope>` | the update run; returns the report |
