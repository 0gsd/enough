---
name: readvisory
description: "Builds a new readvisor out of a real person's judgment, by interview, and installs it. Two ways to gather: LIVE — a patient interview of the user themselves, one or two questions at a time, twelve to eighteen in all; or QUESTIONNAIRE — a plain, email-ready file the user sends to someone whose advice they want on hand (a friend, a mentor, a colleague, a parent, a former editor), with the answers pasted back whenever they arrive. Always ends the same way: a follow-up pass to the user, a preview of both documents they can correct line by line, and their go-ahead before enough installs anything. Produces AGENT.md and MOTIVATION.md and installs them with the install_readvisor tool, in this project or on this machine. Use for 'make me a readvisor', 'build a readvisor', 'new readvisor', 'readvisory', 'interview me and turn it into a readvisor', 'I want my friend's judgment in here', 'profile how my old editor thinks', 'send my dad a questionnaire', 'turn these answers into a readvisor', 'I want a second opinion that argues like X', 'someone who will push back on me about Y', 'I miss asking her about this'. Not for renaming the chief readvisor, not for running a council — this makes the participants, it does not convene them."
---

# readvisory

A readvisor is a second opinion with a particular judgment behind it. This
skill makes one, from a real person, by asking them questions and writing
down what their answers reveal about how they think.

The person can be the user, interviewed live. Or it can be someone else, who
answers a questionnaire in their own time and sends it back. Either way the
work ends in the same two documents — `AGENT.md` and `MOTIVATION.md` — and
enough installs them as a readvisor the user can switch on.

**This is a favor, not a form.** Somebody is spending their attention so that
somebody else can keep asking them things. Be a trusted collaborator, not an
interrogator. Warm, curious, unhurried. If they joke, laugh. If they go
quiet, slow down. If they correct you, take it.

---

## Before the first substantive tool call

1. **Create a request file** per `rness/policies/requests.md`. This job is
   multi-turn by construction and often multi-*day* — a questionnaire can sit
   in somebody's inbox for a week. The request file is the tracker that lets
   a later session pick the work up cold. Show the user its path.
2. **Read `references/privacy.md`.** One page. It sets what you keep, what
   you abstract, and what you never ask about. Read it before the first
   question, not after the first slip.

---

## The series of events

| Step | What happens | Load |
|---|---|---|
| 1. Brief | What will this readvisor readvise on, whose judgment, what is it called | `references/question-bank.md` § brief-shaping |
| 2. Questions out | 12–18 questions, live or as a questionnaire | `references/question-bank.md`, `references/coverage.md`, `references/questionnaire.md` |
| 3. Answers in | Saved verbatim | — |
| 4. Follow-ups | 3–6 questions **to the user**, always | `references/followups.md` |
| 5. Synthesis preview | Both documents drafted, shown, corrected | `references/synthesis.md` |
| 6. Install | `install_readvisor`, project or global | this file |

Do not skip step 4. It is the step that makes an enough readvisor better than
a transcript.

---

## Step 1 — the brief

Three things, in plain conversation. Two or three turns, not a form.

1. **What will this readvisor readvise on?** The real answer is usually a
   kind of question the user keeps having: "whether a draft is finished",
   "when to cut a project", "how to say a hard thing to someone at work".
   Push gently past "general advice" — a readvisor with no subject gives
   horoscope answers.
2. **Whose judgment is it built from?** The user, live and now? Or someone
   else, by questionnaire? If someone else: what is that person to them, and
   what have they seen that person be right about? (Keep the answer — it
   feeds step 4.)
3. **What is it called?** Two names:
   - a **folder name** — kebab-case, lowercase, ≤ 40 characters:
     `block-breaker`, `careful-reader`, `aunt-rosa`;
   - a **display name** — what the user sees in the sidebar: `The
     Block-Breaker`, `Careful Reader`, `Aunt Rosa`.
   Suggest both from what they have told you; let them overrule.

`references/question-bank.md` opens with four brief-shaping questions that
turn a vague subject into a sharp one. Use them when the brief is soft.

Write the brief into the request file before going further.

---

## Step 2 — questions out

Choose **12–18 questions** from `references/question-bank.md`, using the
coverage checklist in `references/coverage.md` to decide which. Shape them to
the brief: a readvisor about cutting drafts needs different questions than
one about hard conversations.

### Live

One or two questions at a time. Never a flood. Let each answer change the
next question — that is the whole point of doing it live.
`references/coverage.md` has the next-question checklist; it is short, and
you should follow it literally.

Between questions, be a person: react to what they said, say what you are
hearing, ask "why" when the why is where the signal is.

### Questionnaire

Write the whole set as one self-contained file:

    rness/io/output/readvisory/<name>/questionnaire.md

`references/questionnaire.md` gives the exact shape — greeting, why they are
being asked, how long it takes, numbered questions with lettered choices, and
how to reply — plus a complete worked example. Follow it closely; the file
leaves the machine and you will not be there to explain it.

Then:

- Tell the user the path and what to say when they send it. **enough does not
  send anything** — the user does, by their own mail, in their own words.
- Set the request file to `**Status:** waiting-on-user` and fill the "Open
  questions" line under Continuation: what is awaited, from whom, and where
  the answers should land when they arrive.
- Stop. The work resumes whenever the answers do — possibly in a session
  weeks from now that knows nothing except the request file.

---

## Step 3 — answers in

The answers arrive one of two ways:

- **Pasted into chat.** Take them as given.
- **A file the user drops in `rness/io/input/`.** `read_file` it — any format
  enough converts is fine, the twin comes back as markdown.

Save them **verbatim**, exactly as written, to:

    rness/io/output/readvisory/<name>/answers.md

Verbatim matters. The abstraction happens in the synthesis, not here — you
will want the person's own phrasing later, and a paraphrase made now cannot
be un-made. `references/privacy.md` says what this does and does not mean.

Answers come back messy: out of order, three questions skipped, two answered
in one paragraph, a long story where a letter was expected. All fine. Read
them as a whole before deciding anything is missing.

---

## Step 4 — follow-ups, to the user, always

The respondent's answers say how that person thinks. They cannot say what the
user needs from them. That is a separate interview, and it is short.

Ask the **user** 3–6 questions: how they know this person's judgment, where
it has been right and where it has been wrong, what they want to be
challenged on, where this readvisor should defer to others, and what tone
they want from it.

When the user interviewed *themselves* in step 2, this pass becomes the
contradiction-and-stress round instead — the same slot, different questions.

`references/followups.md` has both versions, with examples, and says which
part of which document each answer feeds. Save the answers to:

    rness/io/output/readvisory/<name>/context.md

---

## Step 5 — synthesis preview

Draft both documents. Show them **in chat** before writing anything final.

`references/synthesis.md` is the reference for this step: the exact section
headings, the voice rules, how to mark an interpretive leap, how to write an
honest hand-off, what to do when the signal is thin, and the correction loop.
Read it fully — this is the step where a readvisor either sounds like a
person or like a personality test.

Invite three kinds of correction, by name:

- *"That's not quite right"* → rephrase it.
- *"You missed something"* → ask one more question, then rewrite.
- *"That's too identifying"* → abstract it, and check the neighbours.

Iterate until the user signs off. Keep the working drafts at
`rness/io/output/readvisory/<name>/AGENT.draft.md` and
`MOTIVATION.draft.md` so a reset does not lose them.

---

## Step 6 — install

Ask the user one question: **project or global?**

- **project** — `rness/readvisors/<name>/`, this project only, on in this
  project. Right for a readvisor tied to one piece of work.
- **global** — `~/enough/readvisors/<name>/`, available in every project on
  this machine, on here and off by default elsewhere. Right for a person's
  judgment the user will want again.

Then call the tool once, with the full text of both documents:

    <tool name="install_readvisor">
    <name>careful-reader</name>
    <scope>global</scope>
    <display>Careful Reader</display>
    <agent_md>
    # Careful Reader

    You are a readvisor built from a working newspaper editor's judgment
    about when a piece of writing is finished…

    ---
    enough-tooltip-text: "careful-reader tells you whether a draft is done, and what it is still owed."
    </agent_md>
    <motivation_md>
    # Motivational Substrate — Careful Reader

    The values and frame beneath the advice…
    </motivation_md>
    </tool>

Every field is required except `display`, which defaults to the folder name.
enough validates the name, checks both documents are non-empty and under
40 KB, requires the trailing `enough-tooltip-text:` line on `agent_md`, and
runs the same payload scan it runs on any untrusted skill. If it refuses, it
says exactly why — fix that and call again. Do not write the readvisor's
folder yourself with `write_file`; the tool is the only door.

Installing an existing name needs `<replace>yes</replace>` as an extra field,
and enough will still refuse to replace a readvisor that shipped with it.

Afterwards: fill in "End output" in the request file (both paths, the scope,
the display name), set `**Status:** waiting-on-user`, and tell the user it is
in the sidebar. **Never move the request file to `done/` yourself** — that
move is the user's approval act.

---

## Where everything lives

    rness/io/output/readvisory/<name>/
      questionnaire.md      the file the user sends out
      answers.md            what came back, verbatim
      context.md            the user's follow-up answers
      AGENT.draft.md        working draft
      MOTIVATION.draft.md   working draft

Installed readvisors land in `rness/readvisors/<name>/` or
`~/enough/readvisors/<name>/`, written by the tool. The working folder stays
where it is — it is the record of how this readvisor came to exist, and the
starting point if the user ever wants to deepen it.

---

## Boundaries

- **Never install without a yes.** The preview is not a formality.
- **Never invent judgment.** If the answers do not cover a domain, the
  readvisor is silent on it and `MOTIVATION.md` says so. A thin readvisor,
  honestly written, is more useful than a thick one that is making things up.
- **Never make the readvisor sound smarter than the person.** Same mind,
  better organised.
- **One readvisor per run.** If the user wants three, do three passes. They
  can argue with each other later, in a council.
- **The respondent is a third party.** `references/privacy.md` governs what
  reaches the documents. When in doubt, abstract one level and say that you
  did.
- **This skill does not rename the chief readvisor** and does not convene
  councils. It makes participants; the user decides what to do with them.

---
enough-tooltip-text: "use readvisory to build a new readvisor out of someone's real judgment — interview yourself live, or send a plain questionnaire to the person whose advice you keep wishing you could ask — and enough installs the result in this project or on this machine."
