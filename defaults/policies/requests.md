# Policy: Request Tracking

Long, multi-step jobs get tracked as plain-markdown files the agent
maintains across turns. Simple single-turn Q&A does NOT need this.

The request file doubles as the **durable state** across conversation
resets — see `context-management.md` for how it's used to recover when
the context window fills up.

## When to create a request file

Trigger on any of these:

- The user says "build/implement/research X" and it'll take more than one
  assistant turn.
- You need to write multiple files, or do multiple tool calls with
  dependencies between them.
- You need to hit approval gates or ask the user mid-stream.

Don't trigger on:

- A single file edit.
- A one-shot Q&A.
- A quick tool call with a clear self-contained answer.

## What `.rness/requests/` is for

This directory exists for **your** request-tracking markdown files (the schema
below) and nothing else. It is not a general scratch area.

- User artifacts you produce → `.rness/io/output/` (mirror any subfolder the
  user names there).
- Files the user hands you for a task → `.rness/io/input/`.
- If the user says "put X in `requests/`", they almost certainly mean "save
  the artifact and track it as a request." Do both: write the artifact under
  `.rness/io/output/` (mirroring any subfolder they named, e.g.
  `.rness/io/output/requests/X`), and create a tracking file here per the
  schema.

## Where requests live

- Active: `.rness/requests/<summary>_YYYY-MM-DD_HH-MM.md`
- Done:   `.rness/requests/done/<summary>_YYYY-MM-DD_HH-MM.md`

`<summary>` is a brief kebab-case description (4–8 words). Example:
`fetch-gutenberg-tractatus_2026-04-19_17-32.md`.

Get the timestamp with:

    <tool name="shell">
    <command>date +%Y-%m-%d_%H-%M</command>
    </tool>

## File structure

```markdown
# <Request title>

**Created:** YYYY-MM-DD HH:MM
**Status:** in-progress | waiting-on-user | complete

## Request
<The user's original ask, paraphrased in your own words so you're sure you
understood it. Preserve any specific constraints they named.>

## Sub-Requests

A sub-request is a coherent piece of work with more than one atomic task.
A request is composed of one or more sub-requests.

### 1. <sub-request summary>
Tasks (atomic — either done or not-done):
- [ ] task
- [x] task (completed)

### 2. <sub-request summary>
Tasks:
- [ ] ...

## Progress Checkpoints

Lightweight state dumps you write as work progresses. One per phase
transition, or every 3–5 major tool calls, whichever comes first. These
are what let the conversation survive a /reset.

### Checkpoint 1 — YYYY-MM-DD HH:MM
- **Just did:** <1–2 bullets>
- **About to:** <1–2 bullets>
- **Key state:** <file paths you wrote, variables/config the next turn
  needs, external process state like "tor is running at 127.0.0.1:9050">

### Checkpoint 2 — YYYY-MM-DD HH:MM
- ...

## Continuation

Filled in when you sense context pressure and propose a conversation
reset. Left empty while things are going smoothly.

- **Resume instructions:** <what the next turn should do first>
- **Required files:** <paths the next turn should `read_file`>
- **Open questions:** <anything the user might need to answer>

## End output
<Describe exactly what was produced when the request is complete. File
paths, links, summaries of decisions. Fill this in when Status becomes
`waiting-on-user`.>

## Notes
<Dead ends, surprises, things the user should know.>
```

## Workflow

1. **At the start of a complex request**, before doing substantive work,
   write the initial file with the Request section, your first-pass list
   of sub-requests, and any tasks you can foresee. Show the user the path.
2. **As you complete tasks**, update the file with `write_file`. Tick
   checkboxes, add tasks you didn't foresee, split/merge sub-requests as
   reality demands.
3. **Write a Progress Checkpoint** at every phase transition, or every
   3–5 major tool calls. Don't skip this — it's your safety net.
4. **When you believe the request is fulfilled**, fill in "End output",
   flip Status to `waiting-on-user`, and tell the user you're done.
5. **The user confirms via the UI** (a "mark done" button in the preview
   pane moves the file to `.rness/requests/done/`). Do NOT move it yourself
   — the move is the user's approval act.

## Before updating an active request file

DO NOT type the filename from memory. Your own slug spelling drifts across
turns (`decentralized` becomes `decentralative`; `harness` becomes
`harnesses`); typing a slightly different filename creates a new file
instead of updating the existing one. Instead, always list the directory
first:

    <tool name="shell">
    <command>ls .rness/requests/*.md</command>
    </tool>

and use the exact filename shown, verbatim, in your next `write_file`.

The harness will actively reject creation of a second file in
`.rness/requests/` that shares its `_YYYY-MM-DD_HH-MM` timestamp with an
existing active file — the error message will name the canonical file to
update.

## Examples of requests that need tracking

- "Build me a skill that indexes my infoworld/ wiki."
- "Research the last five papers on <topic> and write me a synthesis."
- "Refactor my paradigm files so they're less redundant."

## Examples of requests that do NOT need tracking

- "What does `.rness/paradigms/default.md` say?"
- "Rename this file to foo.md."
- "Add a comma to this sentence."
