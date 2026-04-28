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

## On long tool loops — break into chunks the harness can intervene in

Local context windows are small (often 16–32K tokens). A single user
turn that runs many tool calls in a row — fetching a large page,
writing several long files, processing a corpus — will fill the window
even if no individual call is huge. Each tool result accumulates into
history, and history is sent on every subsequent inference.

The harness watches for this. When pressure crosses the auto-reset
threshold (default 75%), it will:

- **With auto-reset ON**: pause after your current tool result, ask
  you to write a Continuation block to the active request file, clear
  the conversation, then re-prompt you to resume from the request
  file. This happens automatically; you don't need to detect it.
- **With auto-reset OFF**: pause your turn after the current tool
  result and notify the user. The user has to send a follow-up
  message to continue.

You can help this work well:

1. **Always create a request file for jobs that involve more than one
   substantial tool call**, per `requests.md`. The file is what
   carries continuity through a reset — without it, post-reset you
   start blind.
2. **Update Progress Checkpoints frequently during long tool loops** —
   every 3–5 tool calls, especially after each "phase" (fetch done,
   plan done, draft 1 done, etc.). The harness's auto-checkpoint is a
   safety net, not a substitute for the running notes you keep
   yourself.
3. **Prefer many small writes over one huge write.** Writing a
   15,000-word output as 10 sequential `write_file` calls is fine —
   the harness will pause and resume across the gaps. Trying to emit
   15,000 words in a single turn is what causes the wall.
4. **When the harness pauses you**, don't fight it. Trust the request
   file's Continuation block to carry you across the gap, and use the
   resumed turn to read it and proceed.

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
