# Policy: Context Management

Long working sessions fill the LLM's context window. When that happens the
backend errors with "context exceeded", work stalls, and the conversation
feels broken. This policy defines how you sense pressure building and
gracefully reset without losing state.

**The filesystem is your long-term memory.** Active request files, session
logs, the user's paradigm, and `MOTIVATION.md` all persist. In-memory
conversation history is the expensive part — and the part you can shed.

## Self-monitoring

You don't have a direct token counter, but these signals add up to
pressure:

| Signal | Weight | How to detect |
|---|---|---|
| Tool calls this turn or recent turns | High | Count them |
| Large file contents read into context | High | A 10KB+ file you just `read_file`'d is ~2.5K tokens |
| Tool outputs with lots of text (web scrapes, long shell stdout) | High | Same math |
| Re-explaining things you covered earlier | High | You find yourself repeating ground |
| Many sub-requests in the active request file | Medium | Each round adds context |
| Hard error: "context exceeded" or 400 from the LLM | Certain | Pressure is already critical |

Levels:
- **Low** (most turns): Do nothing special.
- **Medium** (15+ tool calls, or a few large reads): Write a fresh
  Progress Checkpoint so your state is safe even if you crash.
- **High** (20+ tool calls or a turn that returned a lot of file content):
  Write a checkpoint AND a Continuation block. Warn the user that a reset
  may soon be wise.
- **Critical** (LLM returned context-exceeded, or you just can't remember
  the early task): Write a final checkpoint + Continuation, tell the user
  to `/reset`, and stop.

## Graceful reset protocol

When pressure is high or critical:

1. **Flush to the request file.** Write one more Progress Checkpoint that
   captures "just did / about to / key state" comprehensively. This is the
   last thing the new session will see that was authored by the old one.
2. **Write a Continuation block.** Three concrete fields:
   - What the next turn should do first.
   - Which files it should `read_file` to rebuild context.
   - Any open questions for the user.
3. **Tell the user:** something like *"I've checkpointed
   `.rness/.requests/<file>.md`. Context is getting heavy — mind hitting
   /reset? I'll pick up from the checkpoint on the next message."*
4. **On the next turn (post-reset)**, read the request file, scan the
   Progress Checkpoints (newest first) and the Continuation block, then
   proceed with the named next step.

## Don't over-checkpoint

- Simple Q&A doesn't need any of this.
- If you've already written 3 checkpoints and the user hasn't reset,
  things are probably fine — keep working.
- One checkpoint per phase transition is usually plenty.

## Artifacts beyond the request file

When context is fresh after a reset, these are your other memory
sources — read them on demand, not pre-emptively:

- `.rness/knowledge/session-logs/<today>.md` — every prior exchange in
  the current day's session, written by the harness.
- `.rness/MOTIVATION.md` — accumulated learnings about the user and the
  project. Terse; worth a skim at the start of any substantive turn.
- `.rness/AGENT.md`, `.rness/paradigms/default.md` — your identity and
  interaction rules. Always loaded into the system prompt; you don't need
  to re-read them.
- Any file you wrote in the project — `read_file` it when you need the
  specifics again, don't hold the contents in your head.

## When to re-create instead of recover

If a reset happens in the middle of a very delicate piece of work (e.g.,
you were 40% through a 2000-line code refactor and the Continuation would
need to describe the edit state token-by-token), tell the user it's
cleaner to start that sub-request fresh from a known-good baseline. Don't
fake continuity when the bookkeeping cost exceeds the re-work cost.
