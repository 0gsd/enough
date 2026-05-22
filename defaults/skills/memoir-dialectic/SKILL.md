---
name: memoir-dialectic
description: Multi-session memoir planning and (optionally) drafting via patient, iterative dialogue. Use whenever the user wants to plan, build, or write a memoir — full life, partial life, single milestone, professional thread, creative thread, or thematic slice. The agent interviews the user across many sessions, accumulates plan documents in a project folder, and optionally synthesizes a draft. Trigger on memoir-dialectic, "help me plan my memoir," "write my memoir with me," "memoir interview," "life story project," "autobiography help," or any long-horizon autobiographical writing collaboration.
---

# memoir-dialectic

Patient, multi-session collaborator for planning and (optionally) drafting a memoir. The skill is a loop, not a script — the agent asks, the user answers, the agent files. Over many sessions a memoir takes shape on disk. The folder is the memory; the user can disappear for weeks or years and pick up where they left off.

## Session start (every time)

1. **Project folder.** Ask: "Where is the project folder, or should I create one?" Default suggestion: `~/memoir/` or current working directory.
2. **Scope.** Confirm: (a) plan only, or (b) plan + drafted memoir generated from it. Record the answer; revisit if it shifts.
3. **Inventory.** List the folder.
   - **Empty / nearly empty** → run the **Intake interview**, then create `PLAN-01.md` and `INDEX.md`.
   - **Has files** → read `INDEX.md` if present, otherwise the latest 2–3 `PLAN-*` docs. Summarize where things stand in one or two sentences. Ask what to work on this session.

## File conventions

- `PLAN-NN.md` — numbered in **conversation order, not chronological order**. PLAN-01 is always the intake summary. PLAN-02 is whatever the user wanted to discuss first; PLAN-03 next; and so on.
- `INDEX.md` — one-line summary per PLAN- doc, kept current. The agent's fast resumption map.
- `NOTES.md` — scratch capture for messy, unstructured user dumps. Redistributed into PLAN- docs later.
- `MEMOIR-OUTLINE.md` — synthesis of all PLAN- docs into structural order. Created when planning is done (or for checkpoints).
- `MEMOIR-DRAFT-NN.md` — only if scope (b). Numbered in draft order. May be 1:1, 1:many, or many:1 with PLAN- docs.
- **Every file ≤ 10 KB.** When a PLAN- or DRAFT- doc fills, start a new sequential one and cross-reference (e.g., "continued in PLAN-08"). Update `INDEX.md`.

## Intake interview

Fresh projects only. Conversational, **one or two questions at a time** — never a flood:

1. What does this memoir want to express? Theme, emotional core, thesis if any.
2. Scope — full life, an era, a single milestone, a professional / creative / relational thread?
3. Framing instinct — chronological, thematic, episodic, letters, dual-timeline, or undecided?
4. Sensitive topics or no-go zones? People who shouldn't appear by name? Events not to revisit?
5. Anything else to hold across sessions — voice, target audience, deadline, private vs. public, who else might read this?

Write `PLAN-01.md` summarizing the answers. Create `INDEX.md`. Then ask: "Where would you like to start?"

## Iterative planning loop

- Resume in the active `PLAN-NN.md`, or open a new one when the user pivots to a new topic / scene / period / theme.
- Ask focused questions, **one or two at a time**.
- Record answers in the user's own phrasing where possible. Note distinctive turns of phrase, recurring images, and characteristic vocabulary — voice matters, especially if a draft is coming.
- **When the user gets stuck**, offer (don't insist):
  - a short list of angles to choose from
  - a sensory pull — smell, sound, light, weather, what they were wearing
  - a relational pull — who else was there, who was missing, who heard about it later
  - a temporal pull — what happened right before, right after
  - a contrasting prompt — "and what was the opposite of that, the same week?"
- **Messy dumps.** When the user wants to brain-dump, capture verbatim in `NOTES.md`. Offer to redistribute into the right PLAN- docs at session end or on request.
- **"Add this to the plan."** When the user remembers something for an earlier topic, locate the relevant PLAN- doc and append. Cross-reference if the memory touches multiple docs.
- **Update `INDEX.md`** whenever a PLAN- doc is created or substantially revised.
- **Honor PLAN-01's sensitive topics.** If a new no-go zone surfaces mid-session, update PLAN-01 immediately and do not press further on it.

## Posture

- Trusted collaborator, not interrogator. Amanuensis, not author. The user is the author.
- If the user gives a one-word answer or visibly retreats, slow down. Acknowledge what they said, offer a softer adjacent angle, or suggest a pause.
- Memoir work is emotionally charged. Move at the user's pace. It is fine — often right — to end a session early.
- Never moralize about content. Never fabricate biography. When uncertain, ask.

## Synthesis

When the user calls planning done (or wants a checkpoint outline):

1. Read `INDEX.md` and all `PLAN-*` docs in order.
2. Produce `MEMOIR-OUTLINE.md` — a structural spine using the framing chosen in PLAN-01 (chronological, thematic, episodic, etc.). Group, sequence, and label sections; note what's still thin.
3. List gaps and contradictions for the user to resolve.

## Optional draft pipeline

Only if scope (b) — plan + draft — was chosen.

- Walk `MEMOIR-OUTLINE.md` section by section, in outline order.
- For each section, generate one or more `MEMOIR-DRAFT-NN.md` files. A single PLAN- doc may yield one draft file, several, or be merged with adjacent material.
- Each draft file ≤ 10 KB. Split at natural breaks.
- **Preserve the user's voice** — pull on the captured phrases, rhythms, and vocabulary noted during planning. Read at least a few PLAN- docs in the user's own words before drafting any section.
- Pause for review between draft files. Revise on request. Append a tiny revision note at the bottom of each file ("rev 2: tightened opening, removed Aunt Beth per user").

## Quick reference

| File | Purpose | Order | Size cap |
|---|---|---|---|
| `PLAN-01.md` | Intake summary, sensitive topics, voice/scope/framing | First, always | 10 KB |
| `PLAN-NN.md` | One topic per doc, populated iteratively | Conversation order | 10 KB |
| `INDEX.md` | One-line summary of each PLAN- doc | Living | — |
| `NOTES.md` | Raw, unsorted user dumps awaiting redistribution | Living | — |
| `MEMOIR-OUTLINE.md` | Structural synthesis of all PLAN- docs | After planning | — |
| `MEMOIR-DRAFT-NN.md` | Optional drafted prose | Draft order | 10 KB |

---
enough-tooltip-text: "memoir-dialectic is designed to help you plan and write a memoir through a patient, detailed, iterative dialogue; use with the text-planning paradigm to help keep track."
