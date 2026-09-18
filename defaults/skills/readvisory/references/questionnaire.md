# The questionnaire

When the judgment belongs to somebody who is not in the room, you write them
a letter with questions in it. They answer it in their own time and send it
back.

The file goes here:

    rness/io/output/readvisory/<name>/questionnaire.md

It leaves the machine. You will not be there when it is read. So it has to
explain itself, ask for nothing it does not need, and be finishable in one
sitting.

---

## The shape — seven parts, in this order

1. **A greeting.** Their name, one line. The user tells you what to call them.
2. **Why they are being asked.** Two or three sentences, in plain words, and
   honest: their friend keeps wanting their opinion about a particular kind
   of question, and this is a way to have a version of it on hand. Say who
   asked. Say what it is for.
3. **What it costs.** How many questions, roughly how long ("fourteen
   questions, about twenty minutes"), and that skipping any of them is fine.
4. **What happens to the answers.** One or two sentences: their friend reads
   them, they stay on their friend's own computer, and they get turned into a
   short description of how they think about this subject. Say that they can
   see the result.
5. **How to reply.** Explicit and dull. See below.
6. **The questions.** Numbered from 1. Lettered options where there are
   options. Every choice question followed by "— why?".
7. **A closing line.** Thanks, and who to send it back to.

Nothing else. No headings from this skill, no mention of readvisors,
composures, enough, skills, or models. The person receiving it does not have
the software and does not need the vocabulary.

---

## The reply instructions

Put them just before the questions, as their own short block:

> **How to reply:** just write your answer under each number, in this same
> file or in the body of an email — whichever is easier. For the lettered
> questions, the letter alone is fine, but the *why* is the part that is
> actually useful, even if it is one line. Skip anything you would rather not
> answer. There are no wrong answers here; the point is how you think, not
> what the right answer is.

Say it once, plainly, and do not repeat it in every question.

---

## Wording rules

- **Plain language, short sentences.** No jargon, no house vocabulary.
- **Ask about the work, not about them.** Every question should be
  answerable without disclosing anything about their life. See `privacy.md`
  for the never-ask list; a questionnaire that touches it cannot be
  un-sent.
- **Options are not a test.** Every lettered option must be something a
  reasonable person actually believes. If one option is obviously correct,
  rewrite the question.
- **Free responses get a cap.** "A sentence or two" printed in the question
  saves the respondent an unnecessary decision.
- **Craft questions go first** — the ones about their actual subject. They
  are the interesting ones, and they set the tone for everything after.
- **Limits questions go last.** Ending on "what should this never do" leaves
  the respondent in charge, which is the right note to end on.
- **Never more than 18 questions.** Fourteen is the good number.

---

## After you write it

Three things, in this order:

1. **Tell the user where it is**, and offer them a sending note they can
   paste into their own mail — three sentences, in their voice, not yours.
   **enough does not send anything.** The user sends it, from their own
   account, with whatever context they want to add.
2. **Set the request file** to `**Status:** waiting-on-user`, and fill the
   Open questions line under Continuation:

       - **Open questions:** questionnaire.md is with <person>, sent by the
         user on <date>. Awaiting their answers. When they arrive, save them
         verbatim to rness/io/output/readvisory/<name>/answers.md and
         continue at step 4 (follow-ups to the user).

3. **Stop.** The session that picks this up may be a fortnight away and may
   know nothing but this file. Write the line for that session.

---

## A complete example

The brief: the user wants a readvisor that tells them whether a draft is
finished. The judgment belongs to a former editor of theirs. Folder name
`careful-reader`, display name `Careful Reader`.

The file, in full:

    # A few questions from Jonah

    Hi Marta,

    Jonah asked me to put this together. He says that the thing he misses
    most since you stopped working together is being able to hand you
    something and find out whether it was done — and that he still hears
    your voice in his head about it, but badly. So: fourteen questions about
    how you read an unfinished piece of writing. He is going to keep the
    answers on his own computer and use them as a sort of second opinion
    when he cannot tell whether a draft is finished. He will show you what
    it turns into if you would like to see it.

    It should take about twenty minutes. Skip anything you would rather not
    answer — a half-finished questionnaire is genuinely useful.

    **How to reply:** just write your answer under each number, in this file
    or in the body of an email, whichever is easier. For the lettered
    questions the letter alone is fine, but the *why* is the part that is
    actually useful, even if it is one line. There are no wrong answers
    here; the point is how you think about this, not what the right answer
    is.

    ---

    **1.** When somebody hands you a draft, what do you read first — the
    opening, the ending, or somewhere in the middle? And what are you
    checking for when you read it? *(A sentence or two.)*

    **2.** A draft that isn't working is usually:
    (a) not finished
    (b) not started — the real piece is underneath it somewhere
    (c) finished, and being fiddled with
    (d) the wrong length for what it is doing

    — why?

    **3.** What do you say to somebody who cannot stop revising? *(A
    sentence or two, in the words you would actually use.)*

    **4.** Facing a piece that is tangled, do you:
    (a) find the smallest thing you can fix
    (b) sketch the whole shape and look for the keystone
    (c) talk it through until the structure shows up
    (d) wait for the writer to frame it first

    — why?

    **5.** Under a deadline, what gets cut first?
    (a) scope (b) polish (c) talking to other people (d) rest

    — why?

    **6.** When the way forward on a piece isn't clear, what do you do
    first?
    (a) gather more material
    (b) try a small version you can learn from
    (c) commit to one approach and adjust as you go
    (d) wait for it to clarify itself

    — why?

    **7.** When a good piece of writing fails, the usual reason is:
    (a) it was aimed at the wrong reader
    (b) it was wrong about what it was actually saying
    (c) it wandered in the execution
    (d) somebody wasn't honest about it early enough

    — why?

    **8.** What is the first sign you notice that a piece is quietly going
    wrong — before anybody says so? *(A sentence or two.)*

    **9.** Given a confident opinion about a piece of writing, what is the
    first thing you privately check?
    (a) their record on this kind of writing
    (b) what would have to be true for them to be wrong
    (c) who disagrees, and why
    (d) whether the confidence matches the difficulty

    — why?

    **10.** You have thirty seconds and the writer is distracted. You:
    (a) give the shortest version of the note
    (b) tell a small story
    (c) ask one question
    (d) wait until you have their attention

    — why?

    **11.** Put these four cafés in the order you would send a friend to
    them, and say why the first one is first: the precise and quiet one;
    the warm and chaotic one; the fast and cheap one; the slow and rare one.

    **12.** If a piece of writing is *too clean*, what is missing?
    (a) real friction
    (b) the writer's actual voice
    (c) an unanswered question
    (d) anything that could be wrong

    — why?

    **13.** Is there anything a second opinion built out of your answers
    should **never** do?

    **14.** What kind of question should it hand straight back — the ones
    where the honest answer is "go ask somebody who actually knows about
    this", or "put it down for a week"?

    ---

    That's all of them. Thank you — genuinely. Send it back to Jonah
    whenever it suits you.

Fourteen questions: three craft (1–3), two method (4–5), one risk (6), two
failure (7–8), one judgment (9), one voice (10), two taste (11–12), two
limits (13–14). That is the standard slate from `coverage.md`, shaped to this
brief.

Note what the example does not do. It does not explain what a readvisor is.
It does not mention enough. It does not ask Marta anything about her life,
her employers, or her history with Jonah. And it says, in the first
paragraph, exactly what is going to happen to her answers.

---

## When the answers come back

They will not come back tidy. Expect:

- **Out of order**, or with the numbers dropped entirely.
- **Three questions merged into one paragraph.** Fine — one paragraph can
  cover three axes.
- **Skipped questions.** Do not chase them. A skipped limits question is
  worth asking the *user* about in the follow-up pass instead.
- **A letter with no why.** Use the letter, and note in `MOTIVATION.md` that
  the axis is thin.
- **A long story where a letter was expected.** This is usually the best
  thing in the file. Keep it verbatim; you will quote from it.
- **More than was asked.** People add things. Read the additions first —
  people volunteer what actually matters to them.

Save the whole thing verbatim to `answers.md`, exactly as received, including
their asides and the bits that answer nothing. Then read it once, whole,
before you decide anything is missing. Then go to `followups.md`.

If enough of it is missing that you cannot write a readvisor, say so to the
user plainly and offer them the choice: a short second questionnaire with
three questions, or a thinner readvisor now with the gaps named in it.
Either is a good answer. Guessing is not.
