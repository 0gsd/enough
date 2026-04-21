# Policy: Read Allowlist

Files and directories OUTSIDE the project directory can be read by the
`read_file` tool only if their absolute path starts with an allowlisted
prefix below. The `shell` tool is unrestricted by this list (it's the
nuclear option; use it deliberately).

Writes are NEVER allowed outside the project directory, regardless of
this list — see the default paradigm's Security Posture.

## Allowlisted prefixes

- `~/enough/`

## Notes for the agent

- To read a file inside `~/enough/`, use `read_file` with the absolute
  path (e.g. `read_file ~/enough/defaults/paradigms/default.md`). The
  harness expands `~` to the user's home directory.
- To read a file inside an allowlisted location that is NOT under
  `~/enough/`, the user must first add its prefix to this file. If you
  need access to a directory not listed here, ask the user before
  trying.
- `../` traversal from relative paths is still rejected — always use
  absolute paths (starting with `/` or `~/`) when reaching outside the
  project.
- `infoworld/` appears inside the project as a symlink to
  `~/enough/infoworld/`, so reading from there uses relative paths
  (e.g. `infoworld/personal/foo.md`) and doesn't need allowlist
  approval.

## Notes for the user

- This file is symlinked into new projects from
  `~/enough/defaults/policies/read-allowlist.md`. Edits here affect
  every project still using the default symlink.
- To give one project a custom allowlist, click "customize for this
  project" in the preview pane — that replaces the symlink with a
  project-local copy you can edit independently.
