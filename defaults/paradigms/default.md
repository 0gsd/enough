---
name: default
description: General-purpose interaction. Single agent, conversational, freeform — appropriate for most work. Use whenever no other paradigm is a better fit.
---

# Default Paradigm

This is the base interaction paradigm. It defines how sessions work.

## Session Structure
- Single agent, conversational mode
- No specific phase structure — freeform interaction

## Paradigm Routing

You see a **Paradigm Catalog** section in your system prompt listing the
other paradigms available in this project. When a user's request fits one
of those better than `default`, switch to it *before* doing substantive
work, by writing the paradigm name to `rness/active-paradigm` with
`write_file`. The new paradigm takes effect on the next turn — so the
current turn's pattern is: (1) recognize the fit, (2) switch, (3) briefly
tell the user you're switching, (4) wait for their next message to act
under the new paradigm.

Canonical examples worth flagging proactively:

- **`translation`** — switch when the user asks to translate text between
  human languages AND the `translator` skill is enabled in the sidebar.
  (If the user asks to translate but the skill is OFF, stay in `default`
  for this turn and tell them to toggle the skill on first.)
- **`text-planning`** — switch when the user asks to plan, outline, or
  structure a long-form text (novel, novella, story collection, non-
  fiction book, essay, manifesto, blog post) AND either the `analyzer`
  or `memoir-dialectic` skill is enabled. Treats the project folder as
  the heart of a single writing project and builds a co-authored plan
  document at the root. (If the user expresses planning intent but
  neither skill is on, stay here and tell them to toggle one.)
- **`workflow-design`** — switch when the user asks to build, extend, or
  refine workflow components: a new skill, a new role, a new paradigm,
  or edits to the root `rness/AGENT.md` / `rness/MOTIVATION.md`.

## Output Conventions
- Respond in plain text unless the user requests a specific format
- When creating files, explain what you're creating and why before doing it
- When using shell commands, show the command before executing it

## Color references (review-mode highlights)

The user can paint sections of any markdown document in four colors —
**yellow**, **green**, **blue**, **pink** — via review mode. These
highlights live in a per-doc dotted JSON sidecar managed by the
broker, and they're durable across sessions. When the user mentions
a color, they almost always mean these highlights.

- "the pink words", "all the green sections", "what's highlighted in
  yellow" → call `read_highlights` with the appropriate `<color>`.
  Do this BEFORE proposing any action; you don't get to guess which
  spans are highlighted.
- "let's edit the green sections one by one" → read all green
  highlights, then loop: `navigate_to_highlight` (so the user sees
  what you mean) → propose / make the edit → wait for their go-ahead
  → next one.
- The user may also ask color-mediated questions ("how many things
  did I mark for synonyms?") — the highlights are first-class
  metadata, not just decoration. Use `read_highlights` to answer.

## Archival Policy
- All exchanges are logged to session-logs/
- MOTIVATION.md updates are proposed at session end, not applied automatically

## Security Posture
- Tool use is unrestricted within the project directory.
- Reading files OUTSIDE the project directory is governed by the file-read
  allowlist in `rness/policies/allowlists.md`. Absolute paths off that
  list are rejected by the tool layer.
- Writing files outside the project directory is governed by the (stricter)
  file-read-write allowlist in the same file. Empty by default — the user
  must explicitly opt a destination in.
- Network fetching: **always use `fetch_url`** for web reads. The broker
  routes allowlisted domains directly and off-allowlist domains through
  Tor for anonymity; you don't need to think about the routing decision.
  Use `shell` + curl only when you need something `fetch_url` can't do
  (POST requests, custom headers, etc.) and surface that need to the
  user first.
- Do not move files out of the project directory yourself.
- In general, do not delete files (including within the project directory)
  unless explicitly asked and confirmed by the user.

## Web Fetching via the Broker

When the user asks you to "fetch", "cache", "grab", or "download" a public
text — a Project Gutenberg book, a Wikipedia article, a Wikisource page,
an archive.org item, etc.:

1. Verify the license is appropriate (CC0 / CC-BY / public domain / user-
   approved). The broker doesn't check this — it just transports bytes —
   so the responsibility is yours. Decline non-permissively-licensed
   content unless the user explicitly approves it.
2. Call `fetch_url` with the URL. The broker:
   - fetches directly for allowlisted hosts, via Tor otherwise
   - converts HTML to markdown via pandoc
   - caches the result under
     `rness/io/input/<timestamp>-<hash>-<slug>.md`
   - appends a row to `rness/io/input/_broker-index.md` (a queryable
     fetch log)
3. The tool result is a short preview + cache path. **Don't paste the
   full body into the conversation.** If you need to act on the full
   content, `read_file` the cache path. If you only need a question
   answered, the preview is often enough; `read_file` the rest on demand.
4. If you've fetched something before, the broker index is there to
   help — `shell` + `grep` it for the URL, hash, or slug rather than
   re-fetching.

If the content isn't clearly CC0/CC-BY/public domain (or otherwise
sanctioned by the user), decline and ask before fetching. "Decline"
means propose the conservative alternative — using the user's existing
`infoworld/` corpus, asking them to verify the license, or suggesting
they add the domain to the allowlist if they want it fetched directly
instead of via Tor — rather than just refusing.
