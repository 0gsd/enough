# Policy: Allowlists

Three lists govern what the agent can reach beyond the project directory:

1. **File-read prefixes** — absolute paths the `read_file` tool may read.
2. **File-read-write prefixes** — absolute paths `write_file` may also write to.
   (A path on this list is implicitly readable too — no need to add it twice.)
3. **Internet domains** — hostnames the agent may fetch from when using
   `shell` with curl/wget. Guidance, not enforcement: the `shell` tool itself
   doesn't restrict outbound connections (it's the nuclear option). Treat
   anything off this list as out-of-bounds and ask first.

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

These are domains generally safe to fetch from for caching public-domain,
CC0, and CC-BY texts into `.rness/io/input/`. The agent SHOULD NOT make
arbitrary web requests, run search-engine queries, or follow redirects to
non-listed hosts without first asking the user.

- `gutenberg.org`
- `www.gutenberg.org`
- `en.wikipedia.org`
- `en.wikisource.org`
- `commons.wikimedia.org`
- `archive.org`
- `standardebooks.org`

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
- For internet fetching: prefer `shell` with `curl -sSL <url> -o <path>`
  to a path under `.rness/io/input/<source-name>/`. Save a sibling
  `_manifest.md` capturing source URL, license (CC0 / CC-BY / public
  domain — verify before fetching), retrieval date, and any rights
  notes. Decline non-CC0/CC-BY/public-domain content unless the user
  explicitly approves it.

## Notes for the user

- This file is symlinked into new projects from
  `~/enough/defaults/policies/allowlists.md`. Edits here affect every
  project still using the default symlink.
- To give one project a custom allowlist, click "customize for this
  project" in the preview pane — that replaces the symlink with a
  project-local copy you can edit independently.
- Internet domains are guidance, not enforcement: anything the `shell`
  tool can curl, the agent can technically reach. The list shapes what
  the agent will *willingly* fetch without asking.
