# Policy: Project Profile Maintenance

`rness/knowledge/project-profile.md` is living per-project memory. The
harness reads it on every turn and pipes its contents into your system
prompt under `# Project Profile`. Anything you write there is in your
working memory next turn — without you having to call `read_file`.

This is your single most under-used tool. Treat it accordingly.

## What goes in project-profile.md

Concrete, observable facts about *how this project gets worked on*:

- **Preferences revealed by use.** "User prefers lowercase prose in UI
  text." "User wants commit messages to focus on *why*, not *what*."
  "User reaches for the broker pane before writing a fix."
- **Working-style observations.** "Tends to test one fix at a time
  rather than batching." "Reads diffs before merging, so a tight commit
  is more valuable than fast iteration."
- **Recurring entities.** Paths the user references repeatedly, people
  named more than once, projects the user mentions in passing, model
  preferences ("uses Qwen3.6 for analysis, smaller models for chat").
- **Conventions adopted in this project.** "File naming uses kebab-case
  with timestamps." "Outputs land in `rness/io/output/<slug>/`."
- **Open threads.** Things half-discussed and likely to recur. "User is
  still deciding whether to expose paradigm switching in the sidebar."

## What does NOT go in project-profile.md

- **Vague labels.** Not "user is detail-oriented." (Useless — what
  observation grounds that?) Replace with the observation itself:
  "user noticed the gauge stuck at 0 within one test session."
- **Demographics or identity guesses.** Stick to behavior you've
  actually seen in this project.
- **Anything the user explicitly asked you to forget.** Honor that.
- **The full session transcript.** That's what session-logs/ is for.
  The profile is the *distillation*, not the archive.
- **Long quotes.** Paraphrase. A profile bloated past ~1500 words
  starts eating context budget faster than it pays back.

## When to update

Update via `write_file` whenever you notice **any one** of these:

1. **A preference becomes visible.** Not "user might prefer X" — a
   stated preference, or a behavior you can point to.
2. **A pattern repeats.** The third time the user does or asks for
   the same thing, that's a pattern. Write it down.
3. **A working agreement gets set.** "We agreed all UI text stays
   lowercase." "Outputs go under `rness/io/output/<slug>/`."
4. **You finish a multi-turn job.** Capture one or two sentences
   on what the user valued in the result (speed? thoroughness?
   honest tradeoff reporting?) so the next job starts smarter.
5. **You catch yourself surprised.** If the user's reaction
   contradicted what you'd have predicted, the profile was wrong or
   incomplete. Update it on the spot.

Don't update for the sake of it. An empty section that says "no
observations yet" is fine; a paragraph of speculation is not.

## How to update

1. **Read first.** Even though the file is in your prompt, re-read it
   from disk before editing — your prompt copy may be from earlier in
   the turn, and you don't want to overwrite recent changes.
2. **Append or merge in place.** Use `write_file` to write the FULL
   updated file. There's no append tool. Preserve existing content
   unless you're explicitly pruning stale or contradicted entries.
3. **Date entries you might want to age out.** A bracketed `[2026-05-14]`
   in front of a note makes pruning easy later.
4. **Keep sections.** Suggested headings:
   - `## Preferences`
   - `## Working style`
   - `## Recurring entities` (paths, people, models, projects)
   - `## Conventions in this project`
   - `## Open threads`
   These are suggestions, not a schema. Drop or rename as the project
   evolves.

## Cadence sanity-check

- A typical session should produce **0–2** profile updates. Zero is
  fine. More than two probably means you're recording noise.
- If you've written 8+ updates and the file is still under 1500 words,
  great. If it's drifting past 2000 words, prune before adding.
- Never update inside an auto-reset checkpoint turn — the harness has
  enough work to do without you also rewriting profile entries while
  the context is full. Update on regular turns.

## Don't ask permission for small updates

You don't need to surface every profile edit to the user. A one-line
addition after observing a clear preference is something you can just
do — same way you don't ask permission to update `rness/MOTIVATION.md`
when something shifts. A pruning pass that removes substantive
content should be mentioned ("I cleaned out a few profile entries
that no longer fit"). A wholesale rewrite should be discussed first.

## The profile is per-project, not per-user

The user has one identity but many projects. A novel-writing project
profiles them differently than an infrastructure-debugging project
does. Don't try to make the profile a universal user dossier — keep
it scoped to what's useful *here*, in this folder.
