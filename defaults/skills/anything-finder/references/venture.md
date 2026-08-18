# "Is this a business?" → an honest viability read

The composed face. Someone has an idea and wants to know whether the world
already has it, whether anyone's making money at it, whether it's fenced off by
patents, and whether there's real open ground. Three sweeps feed one answer:

1. **What exists to buy today** — the market sweep (`references/products.md`).
2. **Who's building it** — the competitive-landscape sweep (below).
3. **What's claimed** — the prior-art check (`references/patents.md`).

Then the read: what exists, what's adjacent, what's genuinely open, what a
defensible wedge would look like, the strongest case for and against, and what
the user should go verify themselves.

**What this is not.** Not a business plan. Not a pitch deck. Not a market-size
model — you cannot compute a TAM from search results, and a number invented to
look rigorous is worse than no number. Not investment advice: this is research
about what exists in the world, and whether to spend money or years on it is
the user's call, not yours. And not a verdict — like a debate, it ends with the
strongest version of both cases and the user judging.

Every claim in the output carries a link. An assertion without a source is a
vibe, and vibes are exactly what the user came here to get past.

---

## Phase 0 — pin the idea

Write, in one line each, and show them to the user before searching:

1. **The thing**: what it is, in a sentence a stranger would understand.
2. **Who it's for**: the specific person or business with the problem.
3. **What they do today**: the status quo it would replace — a product, a
   spreadsheet, a person, a workaround, or nothing.
4. **The claimed wedge**: what the user thinks makes it different or better.

If the idea is too vague to search ("an app that uses AI to help people"), ask
one sharp clarifying question and stop. A viability read on an unsearchable
idea is theater. The question that usually unlocks it: *"What does someone do
today instead, and what specifically is bad about that?"*

Also note the **shape** of the venture, because it changes what "exists"
means: a product, a service, a marketplace, a tool, a piece of hardware, a
content business. A tool with three open-source equivalents is in a different
position than a service with three regional competitors.

---

## Phase 1 — the market sweep (what you can buy today)

Run `references/products.md` against the idea. The question is narrow: **can
someone hand over money for this right now, and to whom?**

- Search by *function*, not by the user's name for it — the existing product
  almost certainly calls itself something else. Rotate vocabulary hard
  (`references/techniques.md` §1).
- Check the obvious storefronts and marketplaces for the category, plus the
  long tail: app stores, Product Hunt, GitHub, the relevant vertical
  marketplace (Reverb for gear, Shopify apps, VS Code / Figma / browser
  extension stores, npm/PyPI for developer tools).
- Check **crowdfunding** (Kickstarter, Crowd Supply, Indiegogo) — for hardware
  especially, this is where "does it exist yet" is answered, and where you find
  the projects that *tried and failed to ship*.
- Note pricing where visible. What a thing costs tells you who it's sold to.

Produce find cards for the closest three to eight things that exist. If nothing
exists, that is a finding — carry it to Phase 4, where the honest question is
*why*.

---

## Phase 2 — the competitive-landscape sweep

Wider than the storefront: who is *working* on this, whether or not they're
selling yet.

- **Companies**: search the problem language, not just the product language.
  Company blogs, careers pages ("we're building X"), and comparison pages
  ("<known player> alternatives") surface competitors faster than the front
  page of a search engine. A comparison page is a competitor list someone else
  already compiled.
- **Funding and formation signals**: Crunchbase-style profiles, accelerator
  batch listings (YC, Techstars), press releases. A funded competitor is
  evidence the thesis is credible *and* that the window is narrowing — say
  both.
- **Open-source alternatives**: `references/code.md`. In tooling especially,
  the real competitor is a free MIT-licensed repo with 4k stars, not a company.
  Verify the license (`scripts/verify_license.py`) — a copyleft core changes
  what a commercial build on top can look like.
- **Adjacent products**: things that solve the same *job* by another route. The
  spreadsheet, the agency, the Notion template, the WhatsApp group. Most ideas
  compete with a workaround, not with a product.
- **The graveyard**: search for the dead ones — `"shutting down"`,
  `"sunsetting"`, `"post-mortem"`, plus the category. A field littered with
  well-funded corpses is the single most informative thing you can find, and
  the most commonly skipped. Read the post-mortems; founders are unusually
  honest in them.
- **Where the users complain**: the relevant subreddit, forum, HN thread,
  review pages for the incumbents. One-star reviews are a free list of unmet
  needs, in the users' own words.

---

## Phase 3 — the prior-art check

Run `references/patents.md`, at *landscape* depth rather than clearance depth:
the question here is "is this fenced?", not "am I clear to ship?".

- Look for granted patents and published applications held by the incumbents
  found in Phase 2 — assignee search is the highest-yield move at this stage.
- Report the **claim overlap** in plain language: what a patent actually covers
  and how close it sits to the user's wedge.
- Include the disclaimer from `patents.md` **verbatim** in the output. It is
  load-bearing and it stays.
- Two honest framings to hold at once: a dense patent thicket is a barrier to
  entry against the user, *and* against everyone else. Whether that's bad news
  depends on which side of it they end up on.
- If the user's wedge is the sort of thing that gets patented, say plainly that
  a real freedom-to-operate opinion is an attorney's job and this is not that.

---

## Phase 4 — the open ground

Now synthesize. Three lists, each item link-cited:

- **Crowded.** What is thoroughly solved and well-served. Entering here means
  competing on execution against people who already ship.
- **Adjacent.** Solved for a *neighboring* user, use case, price point,
  geography, or platform. This is where most real wedges live: the same thing
  for a different person.
- **Genuinely open.** Nobody found doing it, or everyone doing it badly in a
  way the evidence supports (bad reviews, dead companies, forum complaints).
  Be careful here: "I couldn't find it" and "it isn't there" are different
  claims, and you can only make the first one honestly.

Then state **the wedge, if there is one** — the specific, narrow, defensible
first move the evidence actually supports. One or two sentences, tied to what
you found. If the evidence doesn't support a wedge, say that instead; "the
honest read is that this is a feature of an existing product, not a business"
is a valuable answer and a cheap one to receive now.

**The empty-field trap**: an empty field is not automatically an opportunity.
Ask why it's empty and give your best supported answer — too small to sustain a
business, structurally unprofitable, regulated, requires a distribution channel
nobody has, or genuinely overlooked. All five happen. Distinguishing them is
most of the value of this whole exercise.

---

## Phase 5 — the two cases

Even-handed, like a debate. Build **the strongest version of each case** from
the evidence you gathered, not from the tone of the user's request. Someone who
loves their idea is best served by the sharpest possible case against it, and
someone who's talked themselves out of one deserves the sharpest case for.

- **The case for**: 3–5 points, each anchored to something you found. Unmet
  need with a citation, a dying incumbent, an underserved segment, a technology
  or price shift that just made it possible, an open license where you expected
  a closed one.
- **The case against**: 3–5 points, same standard. A funded competitor eighteen
  months ahead, a free tool that's good enough, the four post-mortems that all
  name the same failure, a patent sitting on the wedge, a distribution problem
  with no visible answer, a market that pays nothing.

No scoring. No percentages. No "7/10 opportunity." The reader is the decider,
and a number would only launder your guess into something that looks like a
measurement.

---

## Phase 6 — go verify this yourself

Close with 3–6 **falsifiable questions the search cannot answer** but the user
can, cheaply, in a week. This is the most actionable part of the deliverable —
write it like you mean it.

Good ones are specific and have a method attached:

- "Ask five of <specific user type> what they do today and what it costs them —
  if fewer than three describe the workaround you're assuming, the premise is
  wrong."
- "Check whether <incumbent> already ships this in their paid tier; their
  pricing page didn't say and the docs are behind a login."
- "Find out whether <regulation/certification> applies before you build; the
  three shutdown post-mortems all named it."
- "Confirm someone will pre-pay. A waitlist is not a sale."

Bad ones are "do more market research."

---

## Output

Write to `rness/io/output/anything-finder/<idea-slug>-venture.md`:

```markdown
# Venture read — <idea in a phrase>

## The idea, as I understood it
[the four lines from Phase 0 — thing / who / status quo / claimed wedge]

## The short version
[3–5 sentences. What exists, what's open, what the honest read is.
 No hedging, no hype, no recommendation-as-verdict.]

## What exists today
[find cards from Phase 1 — ranked by closeness to the idea]

## Who's building it
[find cards from Phase 2 — companies, funded projects, open-source
 alternatives with verified licenses, adjacent products, and the graveyard]

## What's claimed
[Phase 3 — patents and applications with assignee, date, status, claim
 overlap in plain language, and the patents.md disclaimer verbatim]

## Crowded / adjacent / open
[three lists, link-cited]

## The wedge the evidence supports
[one or two sentences — or an honest "none that I can see, and here's why"]

## The case for
[3–5 points, each with its evidence]

## The case against
[3–5 points, each with its evidence]

## Go verify this yourself
[3–6 falsifiable questions with methods attached]

## What I couldn't check
[sources the broker refused, databases that blocked Tor, paywalled
 industry reports, anything behind a login — named, so the user can see the
 shape of the gap]

---
*Research, not investment advice. Sources are linked so you can check my work.*
```

Keep the whole thing under about 2,000 words. A viability read that nobody
finishes reading has failed at the only job it had.

---

## Calibration

- **Effort**: this is three sweeps, so budget accordingly — roughly 10–20
  fetches across the three phases for a normal idea, more for a crowded field.
  Don't shortchange the graveyard and the complaint threads; they're where the
  non-obvious findings are.
- **Absence of evidence**: say "I did not find" rather than "there is no." Name
  the sources you checked so the negative has a shape.
- **Recency**: note the date on everything. A competitor's last blog post in
  2023 means something. Prices, funding, and "who's alive" all rot fast — tell
  the user the read is as-of-today.
- **Don't launder speculation.** If you're reasoning past the evidence — and
  sometimes you should — mark the sentence as inference and say what would
  confirm it.
- **The user's enthusiasm is not your input.** Neither is your own. The
  evidence is the input.
