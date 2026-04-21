---
name: wiki-links
description: Historical fiction research assistant that takes a topic (historical event, person, era, location) and returns a richly interconnected web of 5-10 related entries — people, parallel events, cultural details, geographic context, and surprising factoids — designed to give historical fiction authors a constellation of authentic material to weave into their narratives. Works standalone or as a research dependency called by other creative skills in the same directory.
---

# Wiki-Links — Historical Research Web Generator

Take a historical topic and return a research dossier of interconnected entries that a historical fiction author can mine for authentic detail, surprising connections, and narrative possibilities.

## Before Researching: Read the Reference

Load `references/research-strategy.md` before beginning. It contains the research methodology, entry format templates, and quality standards.

## Input Modes

Wiki-links accepts input in two ways:

### Mode 1: Direct User Input

The user provides:

1. **Topic** — A historical event, person, era, place, or moment (e.g., "The 1906 San Francisco earthquake", "Cleopatra's court", "The building of the Trans-Siberian Railway")
2. **Focus** (optional) — A lens to prioritize (e.g., "daily life", "politics", "technology", "food and drink", "lesser-known figures")
3. **Depth** (optional) — `summary` (default) or `deep`. Summary gives concise entries; deep gives expanded entries with sourced details.
4. **Era radius** (optional) — How far to range from the core event. Default: ±10 years and same broad geographic region.

### Mode 2: Called by Another Skill

Another skill in the same `/mnt/skills/user/` directory provides a topic programmatically. In this case, wiki-links should:

- Accept whatever topic description is passed
- Default to `summary` depth unless told otherwise
- Return its output as a structured text block the calling skill can parse
- Save output to `/home/claude/wiki-links-output/` for the calling skill to read

When called by another skill, the calling skill's SKILL.md should include a section like:

```
## Historical Research Dependency

Before writing, generate research material:
1. Read `/mnt/skills/user/wiki-links/SKILL.md`
2. Execute wiki-links with topic: [the historical event for this episode/chapter/scene]
3. Read the output from `/home/claude/wiki-links-output/`
4. Incorporate relevant details into the narrative
```

## Research Workflow

### Step 1: Establish the Core

Identify the central topic and its key parameters:
- **What**: The event/person/phenomenon
- **When**: Specific dates or date range
- **Where**: Geographic location(s)
- **Who**: Primary figures involved
- **Why it matters**: Historical significance in 1-2 sentences

Use web_search to verify and enrich your training knowledge. Do NOT rely on memory alone for dates, names, or specific claims. Search first, then synthesize.

### Step 2: Cast the Research Net

Conduct 5-10 web searches to build out the constellation. Search strategy:

1. **The core topic** — Get the facts right
2. **"[topic] lesser known facts"** — The stuff that isn't in the first paragraph of Wikipedia
3. **"[location] [year] daily life"** — What ordinary people were doing
4. **"[topic] contemporaries"** or **"[year] [region] notable figures"** — Who else was around
5. **"[topic] consequences"** or **"[topic] caused by"** — Upstream and downstream connections
6. **"[year] [region] culture"** or **"[year] inventions"** — What was happening in parallel
7. **Specific people discovered in earlier searches** — Follow the threads
8. **"[topic] myths misconceptions"** — What most people get wrong (gold for fiction)
9. **"[location] [era] food clothing architecture"** — Sensory details for world-building
10. **"[topic] primary sources letters diaries"** — Authentic voices

Do not stop at surface-level results. Follow interesting leads. If a search reveals a fascinating minor character, search for them specifically. The goal is to surface material that would take an author hours of their own research to find.

### Step 3: Assemble the Web

From your research, select 5-10 entries that form the most interesting and useful constellation. Each entry should connect to at least 2 other entries in the web. Prioritize:

- **Surprise** — Things the author probably doesn't know
- **Sensory detail** — Things that make a scene feel real (what people wore, ate, smelled)
- **Narrative potential** — Things that suggest stories, conflicts, irony
- **Accuracy** — Every claim must be verifiable; flag anything uncertain
- **Variety** — Mix people, events, objects, places, and cultural details

### Step 4: Write the Dossier

Format the output following the templates in `references/research-strategy.md`.

The dossier has three sections:

**I. Core Brief** — 3-5 paragraph overview of the topic with key facts, timeline, and significance. This is the author's foundation.

**II. The Web** — 5-10 interconnected entries, each following the entry template. Every entry includes cross-references to other entries in the web (the "wiki links").

**III. Author's Toolkit** — A curated list of:
- **Sensory palette**: 5-8 period-specific sensory details (sounds, smells, textures, colors)
- **Vocabulary**: 8-12 period-specific words, slang, or technical terms with definitions
- **Common misconceptions**: 2-4 things most people get wrong about this topic
- **Narrative hooks**: 3-5 ironic, dramatic, or surprising facts that could drive a plot

### Step 5: Output

**Filename**: `wiki-links-[topic-slug].md`

Save to:
- `/home/claude/wiki-links-output/` (for calling skills to read)
- `/mnt/user-data/outputs/` (for user to download)

## Quality Standards

Before finalizing, verify:

- [ ] All dates, names, and factual claims have been verified via web search
- [ ] Each entry in the web cross-references at least 2 other entries
- [ ] The constellation includes a mix of types (people, events, objects, cultural details)
- [ ] Sensory details are specific and period-accurate, not generic
- [ ] Uncertain claims are flagged with [UNVERIFIED] 
- [ ] The dossier would save an author at least 2-3 hours of research
- [ ] Entries prioritize the surprising and narratively useful over the obvious
- [ ] No entry is just a Wikipedia summary — each has been enriched with specific detail

## Depth Modes

### Summary (default)
- Core brief: 3-5 paragraphs
- Web entries: 5-8 entries, each 100-200 words
- Author's toolkit: Concise lists
- Total output: ~2,000-3,500 words
- Searches: 5-8

### Deep
- Core brief: 5-8 paragraphs
- Web entries: 8-10 entries, each 200-400 words
- Author's toolkit: Expanded with examples and context
- Total output: ~4,000-6,000 words
- Searches: 8-12
