---
name: historical-sources
description: Primary source text hunter for historical fiction. Finds, retrieves, translates, and adapts authentic historical documents—letters, speeches, chronicles, testimony, legal records, diaries, inscriptions—so they can be woven verbatim or near-verbatim into novels instead of invented prose. Use this skill whenever the user wants historical fiction grounded in real source material, when composing a novel that should read like found documents, when adapting historical voices into English, or when any other creative skill (wiki-links, don-brawn, ph-thrill, etc.) needs actual period text rather than pastiche. Also use when the user says things like "use real sources," "don't make it up," "I want actual historical language," "primary sources," or "verbatim historical text."
---

# Historical Sources — Primary Text Hunter & Adapter

Find authentic historical source material so that a novel can be built from real human voices rather than invented approximations.

## Before Starting: Read the References

Load these before beginning any source hunt:

1. `references/source-strategy.md` — Search methodology, source classification, copyright/public domain rules, translation and adaptation protocols, output format
2. `references/adaptation-guide.md` — Detailed rules for when and how to transform copyrighted or archaic text into usable novel prose while preserving authenticity

## Core Principle

Historical fiction is strongest when it sounds like history, not like a novelist imitating history. This skill exists to find the real thing: the actual words people wrote, said, testified, inscribed, or recorded—and to deliver them in a form that can be dropped into a novel.

The hierarchy of preference is:

1. **Verbatim transcription** — If the source is public domain, use it exactly as written (with modernized spelling where helpful)
2. **Faithful translation** — If the source is in another language, produce a literary English translation that preserves voice, rhythm, and period feel
3. **Close adaptation** — If the source is under copyright, adapt it: preserve the substance, restructure the expression, maintain the emotional and historical register
4. **Documented pastiche** — Last resort only. When no source text survives, write in the style of the period using documented vocabulary, syntax, and idiom, and clearly mark it as reconstruction

Every piece of text delivered by this skill is tagged with its category so the calling skill or user knows exactly what they're working with.

## Input Modes

### Mode 1: Direct User Request

The user provides:

1. **Historical context** — The event, period, location, or figure they're writing about
2. **What they need** — The kind of source text (letters, speeches, testimony, diary entries, legal records, etc.)
3. **Scene context** (optional) — What's happening in the novel at the point where this text will appear
4. **Voice needs** (optional) — Whose perspective, what register, what emotional tone
5. **Length** (optional) — How much source material they need (a line, a paragraph, several pages)

### Mode 2: Called by Another Skill

Another skill in `/mnt/skills/user/` passes a request programmatically. In this case:

- Accept the topic, period, and source-type parameters
- Default to gathering 3-5 usable source passages unless told otherwise
- Save output to `/home/claude/historical-sources-output/` for the calling skill to read
- Tag every passage with its source category, provenance, and any adaptation notes

When called by another skill, the calling skill's SKILL.md should include:

```
## Primary Source Dependency

Before writing scenes set in historical periods:
1. Read `/mnt/skills/user/historical-sources/SKILL.md`
2. Execute historical-sources with: period, location, source types needed, scene context
3. Read output from `/home/claude/historical-sources-output/`
4. Integrate source passages into the narrative per the tagging system
```

## Source Hunting Workflow

### Step 1: Scope the Hunt

From the user's request (or the calling skill's parameters), establish:

- **Period**: Exact dates or date range
- **Geography**: Where in the world
- **Language(s)**: What language(s) would primary sources be in
- **Source types needed**: Letters, chronicles, legal documents, speeches, diaries, inscriptions, songs, prayers, recipes, inventories, etc.
- **Figures**: Specific named people whose words are sought, if any
- **Register**: Formal/legal, intimate/personal, religious, mercantile, military, etc.

### Step 2: Search Strategy

Conduct intensive web research. This is the heavy lifting. The goal is to find actual text, not descriptions of text.

**Search tiers** (work through these systematically):

**Tier 1 — Known digital archives** (search these by name + topic):
- Project Gutenberg, Internet Archive, Sacred Texts, Perseus Digital Library
- Avalon Project (Yale), Medieval Sourcebook (Fordham), Early English Books Online
- National archives (UK, US, France, etc.), Library of Congress digital collections
- Google Books (for pre-1929 texts), HathiTrust
- Wikisource (multiple languages)

**Tier 2 — Targeted source searches**:
- `"[historical figure] letters transcription"`
- `"[event] primary source text"`
- `"[period] [region] diary transcription"`
- `"[event] eyewitness account full text"`
- `"[figure] speech full text"`
- `"[period] [document type] translation"`
- `"[topic] source documents anthology"`

**Tier 3 — Deep dives**:
- `"[figure] correspondence [recipient]"`
- `"[event] testimony transcript"`
- `"[year] [city] court records"`
- `"[period] [trade/profession] manual"`
- `"[region] [century] chronicle English translation"`
- Follow footnotes and bibliographies found in earlier searches
- Search for specific titles of known primary sources

**Tier 4 — Parallel and contextual sources**:
- Contemporary newspaper accounts
- Travel writing from the period
- Religious texts, sermons, liturgy in use at the time
- Commercial documents: prices, inventories, contracts
- Songs, poems, proverbs in common use
- Graffiti, inscriptions, marginalia

Use `web_fetch` aggressively. Search results snippets aren't enough—you need actual text. When a search reveals a promising source, fetch the full page and extract the relevant passages.

**Minimum search effort**: 8-15 web searches per request, with at least 3-5 `web_fetch` calls to retrieve actual source text. Do not settle for summaries or descriptions. Find the words.

### Step 3: Classify and Tag Each Source

Every passage gets tagged:

```
[SOURCE: verbatim | translation | adaptation | reconstruction]
[PROVENANCE: Author/speaker, date, document title, archive/collection]
[ORIGINAL LANGUAGE: if not English]
[COPYRIGHT STATUS: public domain | copyrighted — adapted | unknown — treated as copyrighted]
[ADAPTATION NOTES: if adapted, what was changed and why]
```

### Step 4: Process the Text

Apply the appropriate treatment based on the source classification. See `references/adaptation-guide.md` for detailed protocols.

**For verbatim public domain text:**
- Transcribe exactly, preserving original punctuation and phrasing
- Optionally modernize spelling (u/v, i/j, long s, etc.) — note if done
- Add [sic] for genuine errors only if they'd confuse a modern reader
- Preserve period-specific vocabulary even if unfamiliar

**For translation:**
- Produce a literary translation that prioritizes voice and period feel over literal accuracy
- Preserve sentence rhythms where possible — don't flatten archaic syntax into modern prose
- Keep untranslatable terms with inline glosses: *firmān* (royal decree)
- Note where translation involves interpretive choices

**For adaptation of copyrighted material:**
- Read `references/adaptation-guide.md` carefully
- Restructure sentences, substitute synonyms, reorder information
- Preserve the historical substance and emotional register
- The adapted version must not be recognizable as derived from any specific modern author's prose
- Document what the original source was and how the adaptation differs

**For reconstruction (last resort):**
- Base vocabulary, syntax, and idiom on documented sources from the same period and region
- Note the specific models used ("syntax modeled on Paston Letters; vocabulary from OED attestations pre-1450")
- Mark clearly: this is invented text in period style, not a real source

### Step 5: Assemble the Source Package

Organize the output as a structured document the user or calling skill can work from.

**For each passage delivered:**

1. **The text itself** — Ready to drop into a novel
2. **Source tag block** — Full provenance and classification
3. **Context note** — 2-3 sentences explaining what this document is, who wrote it, why, and what was happening when they wrote it
4. **Usage suggestion** — How this might function in a novel (as dialogue, interior monologue, a document a character reads, narration, epigraph, etc.)
5. **Related passages** — Pointers to other sources in the package that connect to this one

### Step 6: Output

**Filename**: `historical-sources-[topic-slug].md`

Save to:
- `/home/claude/historical-sources-output/` (for calling skills to read)
- `/mnt/user-data/outputs/` (for user to download)

## Integration with Other Skills

This skill is designed to be a research dependency for novel-writing skills. The expected workflow:

1. **wiki-links** generates a research dossier (people, events, connections, sensory detail)
2. **historical-sources** finds actual text from the period (letters, speeches, documents)
3. The novel-writing skill (ph-thrill, don-brawn, or a new one) weaves the source material into the narrative

When a novel-writing skill calls historical-sources, it should specify:
- Which scenes need source material
- What kind of voice is needed (personal, official, religious, mercantile, etc.)
- Whether the text will appear as quoted document, dialogue, narration, or interior monologue
- How much material is needed

## Quality Standards

Before finalizing, verify:

- [ ] Every passage is tagged with its source classification
- [ ] Verbatim passages have been verified against at least one digital source
- [ ] Translations preserve period voice and aren't flattened into modern English
- [ ] Adaptations are genuinely transformed, not just lightly paraphrased
- [ ] Reconstructions are documented with their stylistic models
- [ ] Provenance is specific: author, date, document title, where found
- [ ] No copyrighted text is presented as verbatim without adaptation
- [ ] The package includes enough material to be genuinely useful (not just one or two scraps)
- [ ] Context notes give the novelist enough to understand how to deploy each passage
- [ ] The material, taken together, could form the backbone of real scenes

## Depth Modes

### Focused (default when called by another skill)
- 3-5 source passages
- Targeted to a specific scene or chapter's needs
- 8-10 web searches
- Output: ~1,500-3,000 words

### Survey (default for direct user requests)
- 6-10 source passages across a range of voice types
- Broader coverage of the period's documentary landscape
- 12-18 web searches
- Output: ~3,000-6,000 words

### Deep Archive
- 10-20+ source passages
- Exhaustive search across multiple archives and languages
- 18-30 web searches with extensive web_fetch
- Multiple translation and adaptation layers
- Output: ~6,000-12,000 words
- Use when the user wants to build an entire novel primarily from source material

## Example Requests

**Direct user**: "I'm writing a novel set during the Siege of Constantinople in 1453. I need source material — what did people on both sides actually say and write? Letters, chronicles, anything."

**From wiki-links**: `{period: "1453", location: "Constantinople", types: ["chronicles", "letters", "diplomatic correspondence"], figures: ["Gennadius Scholarius", "Mehmed II", "Constantine XI"], depth: "survey"}`

**From a novel skill**: `{scene: "A Venetian merchant writing home during the siege", voice: "personal letter, educated merchant, frightened but practical", length: "2-3 paragraphs of letter text", period: "April 1453"}`
