# Default Paradigm

This is the base interaction paradigm. It defines how sessions work.

## Session Structure
- Single agent, conversational mode
- No specific phase structure — freeform interaction

## Output Conventions
- Respond in plain text unless the user requests a specific format
- When creating files, explain what you're creating and why before doing it
- When using shell commands, show the command before executing it

## Archival Policy
- All exchanges are logged to session-logs/
- MOTIVATION.md updates are proposed at session end, not applied automatically

## Security Posture
- Tool use is unrestricted within the project directory.
- Reading files OUTSIDE the project directory is governed by the file-read
  allowlist in `.rness/policies/allowlists.md`. Absolute paths off that
  list are rejected by the tool layer.
- Writing files outside the project directory is governed by the (stricter)
  file-read-write allowlist in the same file. Empty by default — the user
  must explicitly opt a destination in.
- Network fetching: prefer `shell` with `curl -sSL` against domains on the
  internet allowlist in `.rness/policies/allowlists.md` (Project Gutenberg,
  Wikipedia/Wikisource, the Internet Archive, Standard Ebooks). For
  arbitrary domains or search-engine queries, ask the user first or use
  the `the-internet` skill if it's enabled (Tor-mediated).
- Do not move files out of the project directory yourself.
- In general, do not delete files (including within the project directory)
  unless explicitly asked and confirmed by the user.

## Web Caching Workflow

When the user asks you to "fetch", "cache", "grab", or "download" a public
text — a Project Gutenberg book, a Wikipedia article, a Wikisource page,
an archive.org item, etc. — and that text is CC0, CC-BY, or public
domain:

1. Verify the license. For Gutenberg/Wikisource/PD content this is
   automatic; for Wikipedia text use the CC-BY-SA-compatible plain-text
   export (e.g. `?action=raw` for the source, or the published HTML).
2. Pick a descriptive subfolder under `.rness/io/input/` — e.g.
   `.rness/io/input/gutenberg-walden/` or
   `.rness/io/input/wikipedia-french-revolution/`.
3. Fetch with `shell` + curl: `curl -sSL <url> -o <local-path>`. For
   Gutenberg, prefer the plain UTF-8 text variant
   (`https://www.gutenberg.org/cache/epub/<id>/pg<id>.txt`).
4. Drop a sibling `_manifest.md` in the same subfolder capturing:
   - source URL(s), retrieval date (use `date -u +"%Y-%m-%d"`)
   - license (CC0 / CC-BY / public domain — be specific)
   - any rights notes the source page mentions
5. Tell the user what you cached and where, so they can verify before
   you start consuming the text.

If the user asks for something that ISN'T on the internet allowlist, or
isn't clearly CC0/CC-BY/public domain, decline and ask before fetching.
"Decline" means propose the conservative alternative — adding the domain
to the allowlist, or using the user's existing `infoworld/` corpus —
rather than just refusing.
