---
name: anything-finder
description: "Deep-search retrieval engine plus patent prior-art search plus honest business-viability reads. FIND locates hard-to-find things a plain web search won't surface: public-domain texts; rare / lost / out-of-print film, TV and video (legal watch links); cleared / PD / CC0 images for covers, posters, zines; hard-to-find products, gear, synths and instruments (buy links, or an honest closest-thing / market-gap answer); paywalled or buried articles and papers (legit open copies — preprints, repositories, archives); open-source repos by permissive license (MIT / Apache-2.0), including libraries off GitHub; novel read-alikes; plus sheet music, samples, fonts, 3D models, stock footage, datasets, public APIs, hardware manuals, PD comics. PATENTS runs a structured prior-art search across granted patents, published applications, and non-patent literature, and reports novelty and non-obviousness concerns with an explicit not-legal-advice disclaimer. VENTURE composes the market sweep, the prior-art check, and a competitive-landscape sweep into an even-handed viability read — what exists, what's adjacent, what's genuinely open, the strongest case for and against building it. Trigger on 'find me...', 'where can I get / download / watch...', 'does there exist a...', 'track down a...', 'I'm looking for...', 'is there an open-source / free / public-domain...', 'prior art', 'patent search', 'has this been patented', 'is my idea patentable', 'novelty search', 'freedom to operate', 'is this a business', 'should I build this', 'does this exist as a product', 'evaluate this idea', 'market gap', or any request to locate a rare, buried, license-sensitive, or format-specific thing — or to find out whether an idea already exists in the world."
---

# anything-finder

A retrieval engine for the things that don't come up on the first page of a
normal search — the out-of-print, the buried, the license-encumbered, the
"surely this exists somewhere." The job is to run a **clever, persistent,
multi-source finding mission** and return the result in exactly the shape the
user can use, with honest provenance.

Three faces, one engine:

- **find** — the eleven-category deep search. The default.
- **patents** — prior-art / novelty / freedom-to-operate search.
  `references/patents.md`.
- **venture** — "is this a business?" Composes the market sweep, the prior-art
  check, and a competitive-landscape sweep into an honest viability read.
  `references/venture.md`.

## Prime directives

Read these before every mission. They are what separate a good find from a
useless one.

1. **Legitimacy is the craft, not a constraint.** Setting a custom
   `User-Agent`, sending cookies, and reading archives are all normal, legal
   parts of retrieving publicly available content, and this skill uses them
   freely. What it does **not** do is pirate in-copyright works, or defeat an
   access control the user has no right to bypass. The liberating fact: for
   almost anything worth finding there *is* a legitimate route — a
   public-domain edition, an author's own copy, an institutional repository, a
   library lending system, an official archive, a permissive mirror. **Finding
   that legitimate route is the entire skill.** If the only route you can find
   is a piracy site, say so plainly and hand the user the legal alternatives
   instead (library systems, streaming locators, purchase links, hold
   requests).

2. **Provenance is part of the deliverable, not a footnote.** A found thing
   without a trustworthy source is a rumor. For every result, record where it
   came from, why you believe it's the real/correct/legal item, and — for
   anything copyright-sensitive — *why it's clear to use* (publication date,
   author death date + jurisdiction rule, explicit license, CC0/PD mark). See
   "The find card" below.

3. **Be honest about existence and confidence.** Rare-find missions often end
   in "this doesn't exist," "this exists but isn't legally available," or "I
   found three candidates and I'm 70% on the second one." Those are *good,
   valuable answers* when delivered clearly. Never manufacture a link. Never
   assert a thing is public domain, permissively licensed, or
   definitely-the-right-item unless you verified it. A ranked set of candidates
   with confidence beats one overconfident wrong answer.

4. **Persistence and cleverness beat brute force.** The difference between
   finding and not-finding is almost always *reformulation and knowing the
   right specialist source*. Don't run the same query five times. Rotate:
   exact-phrase, synonyms, the thing's insider/technical name, its era's
   terminology, `site:` operators against specialist databases, citation-trail
   following, and archive lookups. `references/techniques.md` is the playbook —
   consult it whenever a mission stalls.

## Reaching the web, in enough

This skill lives on the user's machine and every byte it pulls goes through the
broker. That is not an obstacle; it's the routing layer. The rules:

- **`fetch_url` is how you read the web.** It routes allowlisted domains
  directly and everything else through Tor, converts HTML to markdown, caches
  the result under `rness/io/input/<timestamp>-<hash>-<slug>.md`, and returns a
  preview plus that path. `read_file` the cache when you need the full text —
  that's what keeps a twelve-source mission out of your context window.
- **Never `curl` a page for its content.** No `shell` + `curl`/`wget` as a way
  around the broker. If `fetch_url` can't do something structurally (a POST, a
  header the tool doesn't expose), say so to the user first and let them
  decide.
- **A denial is an answer, not an obstacle to route around.** If `fetch_url`
  comes back with a broker denial — the tool is switched off, or the host is
  off-allowlist with the Tor toggle off — report exactly which host was
  refused and what the user can do about it (add the domain to
  `rness/policies/allowlists.md` under `## Internet domains`, or flip the
  toggle in the broker pane). Then continue the mission with the sources you
  *can* reach, and say in the deliverable which sources you couldn't check.
  Don't quietly try a different transport.
- **Tor blocks are normal.** Many big sites (Google, Cloudflare-fronted
  properties, some news outlets) reject Tor exit nodes. `fetch_url` says so in
  its result. Pivot to an on-allowlist source for the same information rather
  than retrying — `en.wikipedia.org`, `en.wikisource.org`, `www.gutenberg.org`,
  `archive.org`, `commons.wikimedia.org` all route direct and rarely block.
- **There is no web-search tool.** You reach a search engine the same way you
  reach anything else: `fetch_url` against a search URL. This is exactly why
  `references/techniques.md` matters — going straight to the *specialist*
  source (IMSLP, Reverb, Unpaywall, archive.org, PyPI, Google Patents) beats
  bouncing off a general search page.
- **If a local Wikipedia archive is installed**, `wiki_search` /
  `read_wiki_article` are faster and free for background and identification
  work — alternate titles, a person's dates, what a thing was called in its
  era. Use them before reaching outward.
- **The three bundled scripts are verification helpers, not a second
  transport.** They make their own narrow HTTP calls (a liveness probe, a
  registry license lookup, one file download with a provenance sidecar). Use
  them for what they do — don't reach for them to fetch page content that
  `fetch_url` should be fetching, and don't use them to reach a host the broker
  just refused.

## Universal workflow

1. **Understand the target.** Restate what the user is looking for in one line,
   and pin the *return format* they need. If the request is genuinely ambiguous
   in a way that changes the search (e.g., "find me Metropolis" — the 1927
   film? the Kafka? a font? a synth patch?), ask **one** sharp clarifying
   question. Otherwise proceed on the most likely reading and state your
   assumption.

2. **Classify the mission** using the router below and open the matching
   reference file(s). A mission can span several — "cleared cover art *and* a
   public-domain poem to letterpress on it" is images + texts.

3. **Run the deep search** per the reference file's playbook — specialist
   databases first, general web second, archives as fallback. Scale effort to
   difficulty: a couple of fetches for an easy find, 10–20+ for a genuinely
   buried one.

4. **Verify before you return.** Confirm links resolve
   (`scripts/link_check.py`), confirm licenses by reading the actual
   license/rights rather than a badge (`scripts/verify_license.py` for code),
   confirm a public-domain claim against the real jurisdiction rule, confirm a
   "rare film" URL is the actual work and a legal host.

5. **Return in the right shape** with find cards. Download files when the
   format calls for a file (images, fonts, some texts); otherwise return URLs.
   Saved files and written reports go under
   `rness/io/output/anything-finder/` — tell the user the path so they can open
   it from the file tree.

## The router

Precedence, top to bottom — the first rule that matches wins:

1. **Patent / novelty language** → `references/patents.md`.
   "prior art", "patent search", "patentability", "novelty search",
   "freedom to operate", "has this been patented", "check for existing
   patents", "patent conflict", "invention disclosure", "IP search", "patent
   clearance", "is my idea patentable".
2. **Business / idea-evaluation language** → `references/venture.md`.
   "is this a business", "should I build this", "does this exist as a
   product/company", "evaluate this idea", "market gap", "is there a market
   for", "has someone already built this", "would this be worth building".
   Venture then calls `patents` and `products` itself as steps — so a request
   that carries *both* patent and business language is a **venture** mission,
   not a patents one. A bare patent question stays a patents mission; don't
   escalate it into a business evaluation the user didn't ask for.
3. **Everything else** → the category table below.

| If the user wants… | Open | Returns |
|---|---|---|
| **(a)** Public-domain texts, poems, stories, historical documents | `references/texts.md` | Markdown + provenance |
| **(b)** Rare / lost / out-of-print films, TV, video | `references/video.md` | Watchable URLs (+ legality) |
| **(c)** Copyright-cleared / PD / CC0 images for covers, posters, zines | `references/images.md` | Image files + ref URLs + attribution |
| **(d)** Hard-to-find products, tech, gear, synths, instruments | `references/products.md` | Buy URLs, or honest "closest thing / gap" |
| **(e)** Paywalled or buried articles & academic papers | `references/articles.md` | Legit open-copy URLs |
| **(f/g)** Open-source repos (MIT/Apache-2), incl. libraries **not** on GitHub | `references/code.md` | Repo/package URLs + verified license |
| **(h)** New novels / read-alikes from liked books, authors, vibes | `references/books.md` | Kindle links or other storefronts |
| Sheet music, MIDI, samples, SFX, gear manuals, chord charts | `references/audio.md` | URLs / files as appropriate |
| Fonts, textures, 3D models, vectors, stock footage, PD comics | `references/assets.md` | Files or URLs + license |
| Datasets, public APIs, gov/legal docs, newspaper archives | `references/data.md` | URLs / files + access notes |
| Patents, prior art, novelty, freedom-to-operate | `references/patents.md` | Prior-art report + conflict assessment |
| "Is this a business / has someone built this / is there a gap" | `references/venture.md` | Viability read: exists / adjacent / open |
| **Any mission that stalls, or needs deep technique** | `references/techniques.md` | (cross-cutting playbook) |

If a request doesn't fit cleanly, pick the nearest category, and always fall
back to `references/techniques.md` for the general deep-search method. The
categories are a map, not a cage — the skill is *find anything*.

If a request is genuinely ambiguous **between faces** — "look into this idea
for me" could be a product hunt, a patent search, or a business read — ask one
clarifying question rather than guessing: *"Do you want me to find whether it
exists to buy, whether it's been patented, or whether it's a business?"*

## The find card

Every result — whatever the category — is presented with this compact block so
the user can trust and act on it. Keep it tight; don't pad it.

```
### <what it is>
- **Link / file:** <URL or saved filepath>
- **Source:** <where it lives — the specific site/archive/registry>
- **Provenance / why this is the real thing:** <1 line>
- **Rights:** <PD (jurisdiction + why) | CC0 | CC-BY (attribution string) | MIT | for-sale | in-copyright, legal host | unknown>
- **Confidence:** <high | medium | low> — <1 line on what would raise it>
```

For a mission returning several candidates, produce one card each, **ranked
best-first**, and open with a one-line verdict ("Best bet is #1; #2 is the
fallback if you need X").

## When the thing isn't found (or doesn't exist)

This is a first-class outcome, not a failure. Deliver:

- **What you searched** (sources + the query variations) so the user sees it
  was thorough. If the broker refused a host, name it here too — an unchecked
  source is different from a checked-and-empty one.
- **The most likely status**: doesn't exist / exists but not legally available
  online / exists only offline (name the library, archive, dealer, or physical
  medium) / exists under a different name (give it).
- **The closest alternatives** you *did* find, as find cards.
- For products specifically: the nearest existing item, the market/technical
  reason the exact thing may not exist, and — if apt — a DIY or commission
  path. See `references/products.md`.

## Output

Everything this skill writes goes to:

    rness/io/output/anything-finder/

Mirror any subfolder the user named. Create the directory if it doesn't exist.

Filename conventions:

- `find` → `<query-slug>-find.md`
- `patents` → `<invention-slug>-prior-art.md`
- `venture` → `<idea-slug>-venture.md`

Downloaded files (images, fonts, PDFs) land in the same folder alongside their
`.provenance.txt` sidecars. For a short answer — two or three cards — just
reply in chat; write a file when the deliverable is long, when files were
downloaded, or when the user will want it later.

## Safety boundary

This skill finds things people have a legitimate right to obtain. Decline,
briefly and without drama, to hunt for: instructions or materials for
weapons/harm, malware or exploit kits, sexual content involving minors,
someone's private personal information for tracking/stalking, or content whose
only available sources are piracy of in-copyright works (offer legal
alternatives instead, per directive 1). Everything else — the obscure, the
eccentric, the "surely this exists" — is fair game and the whole point.

Two more lines this skill does not cross: it does not give legal advice (the
patents face has its own load-bearing disclaimer — reproduce it verbatim), and
it does not give investment advice. A venture read is research about what
exists in the world; whether to spend money or time on it is the user's call.

## Bundled scripts

Use these instead of re-deriving the logic each mission. They are stdlib-only
and run under enough's Python:

- **`scripts/verify_license.py`** — Given a GitHub/GitLab repo URL **or** a
  package name on PyPI/npm/crates.io, fetches the actual license and reports
  the SPDX id, whether it's permissive (MIT/Apache-2.0/BSD/ISC) or
  copyleft/other, plus basic health signals (last activity, stars where
  available). Verifies rights for categories (f/g).
- **`scripts/fetch_asset.py`** — Downloads an image or file with a configurable
  `User-Agent`, saves it under `rness/io/output/anything-finder/`, and writes a
  `<name>.provenance.txt` sidecar with the source URL, license, and attribution
  string. Use for category (c) and any file-return where you need the actual
  file on disk with its rights attached.
- **`scripts/link_check.py`** — Takes URLs and reports which resolve; for dead
  ones, emits a Wayback Machine URL to try. Run before returning a card set so
  you never hand the user a dead link.

Invoke them through `shell` from the project directory:

```bash
python3 rness/skills/anything-finder/scripts/link_check.py <url> [<url>…]
```

Run any of them with `--help` for exact usage. If a host is unreachable, they
say so — report which host to allowlist rather than silently failing or
pretending you retrieved something.

---

*Find the legitimate route. Show your work. Say what you don't know.*

---
enough-tooltip-text: "use anything-finder to track down hard-to-find things online — public domain texts, rare films, cleared images, obscure gear, open-source code, papers behind paywalls — or to check whether an idea has been patented or already exists as a business."
