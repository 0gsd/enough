# Finding prior art → patents, applications, and non-patent literature

Conduct a structured prior art search for a given invention idea, searching
granted patents, published patent applications (which includes pending
submissions), and non-patent literature across US and international patent
offices. Produce a clear, actionable report assessing potential conflicts with
patentability.

This face fires on: prior art, patent search, patentability, novelty search,
freedom-to-operate, patent landscape, "is my idea patentable", "has this been
patented", "check for existing patents", "patent conflict", invention
disclosure, IP search, patent clearance. It is the first line of defense before
spending money on a patent attorney — not a replacement for one.

If the user's question is really *"is this a business?"* rather than *"is this
patentable?"*, this is a step inside `references/venture.md`, not the whole
mission. Read the router in `SKILL.md`.

## Important Disclaimer

**Always include this disclaimer in the output report, verbatim:**

> This prior art search is an informal, AI-assisted preliminary scan. It is NOT a
> substitute for a professional patentability opinion from a registered patent attorney
> or agent. Patent law is complex — concepts like claim construction, obviousness
> (35 U.S.C. § 103), and written description requirements require expert legal judgment.
> Use this report as a starting point for discussion with qualified IP counsel, not as
> a final determination.

## Workflow

### Phase 1: Invention Decomposition

Before searching, analyze the user's invention description and extract:

1. **Core Novelty Statement**: What is the user claiming is new? One sentence.
2. **Technical Domain**: The broad field (e.g., "machine learning," "bicycle mechanics,"
   "food preservation").
3. **Key Functional Elements**: 3-7 specific technical features or components that
   together define the invention. These become your search axes.
4. **Closest Conventional Approach**: What existing technology does this most resemble
   or improve upon? This grounds the search.

Present this decomposition to the user and confirm before proceeding. If the user's
description is vague, ask clarifying questions — a good prior art search depends on
understanding what specifically is claimed as novel.

### Phase 2: Search Strategy

Design 5-10 search queries targeting different facets of the invention. The search
strategy should cover:

**A. Direct novelty searches** (2-3 queries)
- Search for the core invention concept as described
- Use the most specific technical terms from the decomposition
- Query shapes:
  - `patent [core concept] [key technical term]`
  - `site:patents.google.com [technical description]`
  - `USPTO patent application [concept keywords]`

**B. Component/element searches** (2-3 queries)
- Search for individual novel elements or combinations
- These catch patents that solve sub-problems your invention also solves
- Example: If invention is "a drone that uses sonar for indoor navigation,"
  search for `patent drone indoor navigation sonar` AND separately for
  `patent UAV ultrasonic obstacle avoidance`

**C. Alternative terminology searches** (1-2 queries)
- Patent claims use specific (sometimes archaic) language
- Search using synonyms, broader terms, and patent-specific vocabulary
- Example: "machine learning" → also search "neural network," "classifier,"
  "trained model," "artificial intelligence system"

**D. Domain/classification searches** (1-2 queries)
- Search within the relevant CPC (Cooperative Patent Classification) class
- Look up likely CPC codes first: `CPC patent classification [domain]`
- Then search: `patent [CPC code] [key feature]`

**E. Non-patent prior art** (1 query)
- Academic papers, product launches, open-source projects
- These count as prior art even though they're not patents
- `[invention concept] research paper OR whitepaper OR "open source"`

### Phase 3: Execution

Everything here goes through `fetch_url` — see "Reaching the web, in enough" in
`SKILL.md`. There is no web-search tool: you reach a search engine or a patent
database the same way you reach any page, by fetching its URL. Prefer going
straight at the databases.

The databases worth going straight at:

- **Google Patents** — `https://patents.google.com/?q=<terms>` for a result
  list, `https://patents.google.com/patent/<PATENT_ID>/en` for a specific
  document. Indexes granted patents *and* published applications, US and
  international, with full text.
- **USPTO** — Patent Public Search (`ppubs.uspto.gov`), and `patentsview.org`
  for structured queries.
- **Espacenet** (EPO, `worldwide.espacenet.com`) — the best international
  coverage; **WIPO Patentscope** (`patentscope.wipo.int`) for PCT applications.
- **Free full-text alternatives** when the above are blocked or heavy:
  `patft.uspto.gov`, `freepatentsonline.com`, `lens.org`.
- For **non-patent prior art**: the sources in `references/articles.md`
  (arXiv, PubMed Central, Unpaywall/OpenAlex, Semantic Scholar) and
  `references/code.md` (registries, forges) — open-source projects and papers
  are prior art too, and they're often what actually kills a novelty claim.

For each query:

1. **Fetch the search or database URL** with `fetch_url`, then `read_file` the
   cached result to read it properly.
2. **Scan results** for relevance — look at titles, snippets, dates.
3. **Fetch the most relevant Google Patents or USPTO pages** to read abstracts,
   claims, and descriptions.
4. For Google Patents results, fetch the patent page at:
   `https://patents.google.com/patent/[PATENT_ID]/en`
5. Record for each relevant hit:
   - Patent/application number
   - Title
   - Filing date and publication date
   - Status (granted, published application, abandoned, expired)
   - Assignee/applicant
   - Key claims that relate to the user's invention
   - A 1-2 sentence summary of overlap with the user's idea

**Search volume**: Aim for 6-10 searches and 3-6 fetches of individual patent
documents. This is a thorough-but-not-exhaustive scan. More is better if the
invention is in a crowded field.

**If the broker refuses a host**: say which one, in the report's methodology
section, and treat that database as *unchecked* rather than *empty*. A prior-art
report whose coverage gaps are invisible is worse than one that names them.
`patents.google.com` is not on enough's default internet allowlist, so it routes
through Tor — which Google frequently rejects. When that happens, pivot to
Espacenet, Patentscope, or FreePatentsOnline, and tell the user they can add
`patents.google.com` to `rness/policies/allowlists.md` if they'd rather fetch it
directly.

**Coverage note on pending applications**: Google Patents indexes published patent
applications (typically published 18 months after filing). Truly secret applications
that haven't been published yet are NOT searchable by anyone — not even professional
patent searchers. Make this clear in the report.

### Phase 4: Analysis & Report

Produce a report saved to
`rness/io/output/anything-finder/<invention-slug>-prior-art.md` with these
sections:

#### Report Structure

```
# Prior Art Search Report
## Invention Under Review
[Core novelty statement and key elements from Phase 1]

## Disclaimer
[Standard disclaimer from above, verbatim]

## Search Methodology
[Brief summary of search strategy, queries used, databases covered,
 and any database that could not be reached]

## Findings

### Category A: High-Relevance Prior Art
[Patents/applications that overlap significantly with the core novelty.
 For each: number, title, date, status, assignee, claim overlap summary,
 link to Google Patents page]

### Category B: Moderate-Relevance Prior Art
[Patents that share some elements but differ in key ways.
 For each: same fields as above, plus note on what differs]

### Category C: Background/Context Prior Art
[Patents in the same domain that establish the state of the art
 but don't directly conflict. Brief listing.]

### Non-Patent Prior Art
[Any academic papers, products, or publications found]

## Conflict Assessment

### Novelty (35 U.S.C. § 102)
[Is there a single reference that anticipates ALL elements of the invention?
 If yes, novelty is likely destroyed. If no, novelty may survive.]

### Non-Obviousness (35 U.S.C. § 103)
[Could a person of ordinary skill combine 2-3 references to arrive at
 the invention? This is the harder question. Provide honest assessment.]

### Recommended Next Steps
[Specific, actionable recommendations:
 - Areas where the invention appears novel
 - Areas of concern
 - Suggested claim narrowing strategies
 - Whether to proceed to a professional search]

## Appendix: Search Queries Used
[Full list of queries for reproducibility]
```

### Phase 5: Presentation

1. Save the report to
   `rness/io/output/anything-finder/<invention-slug>-prior-art.md`.
2. Tell the user the path — they can open it from the file tree.
3. Give a brief verbal summary in chat highlighting the most important
   findings. Don't paste the whole report into the conversation.
4. Ask if the user wants to dig deeper into any specific reference.

## Search Tips

- **Date matters**: More recent patents in the same space are more concerning
  for patentability but may also show the field is active (good for investment)
- **Application vs. granted**: Published applications that were later abandoned
  still count as prior art for novelty purposes
- **Claim language**: Focus on independent claims (Claim 1, sometimes Claims 1,
  10, 15) — these define the broadest scope of protection
- **Patent families**: A single invention may have US, EP, WO, CN versions.
  Note the family when relevant.
- **Expired patents**: An expired patent means you're free to practice that
  technology, but it still counts as prior art against your own patent application

## Edge Cases

- **Very broad/vague ideas**: Push back gently. "An app that uses AI to help
  people" is not searchable. Ask the user to describe the specific technical
  mechanism that makes their idea different.
- **Extremely niche ideas**: If initial searches return nothing, widen the search
  to adjacent domains. Absence of prior art is good news but should be stated
  with appropriate uncertainty.
- **Software patents**: Note that software patentability has additional hurdles
  (Alice/Mayo framework, 35 U.S.C. § 101). Flag this in the report if relevant.
- **Design patents**: If the invention is primarily aesthetic rather than
  functional, note that design patent search requires visual comparison, which
  this text-based search may not fully cover.
