# Policy: Allowlists

Three lists govern what the agent can reach beyond the project directory:

1. **File-read prefixes** — absolute paths the `read_file` tool may read.
2. **File-read-write prefixes** — absolute paths `write_file` may also write to.
   (A path on this list is implicitly readable too — no need to add it twice.)
3. **Internet domains** — hostnames the broker fetches directly (without
   anonymization). See "Internet domains" below for the routing rules.

Writes outside the project directory are rejected unless the destination
is on the file-read-write prefix list. Reads from absolute paths off both
lists are rejected.

## File-read prefixes

- `~/enough/`

## File-read-write prefixes

(empty by default — add a prefix here only when you intentionally want the
agent to be able to write outside the project. paths on the file-read list
above are read-only.)

## Internet domains

These are domains the broker fetches **directly** when the agent uses
the `fetch_url` tool. Off-list domains aren't rejected — they're routed
through the local Tor proxy (127.0.0.1:9050) for anonymity. The
allowlist is the boundary between "fetch fast, identifiable" and "fetch
slower, anonymized."

- `gutenberg.org`
- `www.gutenberg.org`
- `en.wikipedia.org`
- `en.wikisource.org`
- `commons.wikimedia.org`
- `archive.org`
- `standardebooks.org`
- `download.kiwix.org`
- `dumps.wikimedia.org`
- `wikimedia.org`

## Notes for the agent

- To read a file inside `~/enough/`, use `read_file` with the absolute
  path (e.g. `read_file ~/enough/defaults/paradigms/default.md`). The
  harness expands `~` to the user's home directory.
- To read a file inside an allowlisted location that is NOT under
  `~/enough/`, the user must first add its prefix to the file-read or
  file-read-write list. If you need access to a directory not listed,
  ask the user before trying.
- `../` traversal from relative paths is still rejected — always use
  absolute paths (starting with `/` or `~/`) when reaching outside the
  project.
- `infoworld/` appears inside the project as a symlink to
  `~/enough/infoworld/`, so reading from there uses relative paths
  (e.g. `infoworld/personal/foo.md`) and doesn't need allowlist
  approval.
- For internet fetching, **use `fetch_url`** — not `shell` + curl. The
  broker handles routing (direct for allowlisted hosts, Tor for
  everything else), converts HTML to markdown via pandoc, caches the
  result under `rness/io/input/<timestamp>-<hash>-<slug>.md`, and
  indexes it in `rness/io/input/_broker-index.md`. The tool result is
  a short preview + cache path; read the full content via `read_file`
  if needed. This keeps fetched documents out of your context window.
- License/rights are still your responsibility. The broker does not
  check copyright — it just transports bytes. When caching content
  the user might publish or otherwise re-use, confirm the license
  (CC0 / CC-BY / public domain / explicit user approval) before
  treating it as freely usable.

## Notes for the user

- This file is symlinked into new projects from
  `~/enough/defaults/policies/allowlists.md`. Edits here affect every
  project still using the default symlink.
- To give one project a custom allowlist, click "customize for this
  project" in the preview pane — that replaces the symlink with a
  project-local copy you can edit independently.
- Off-allowlist internet fetches now go through Tor automatically. To
  block off-allowlist fetches entirely, open the **broker** pane in
  the top nav and turn off the "Tor for off-allowlist domains" toggle.
