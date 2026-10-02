---
name: lexicographer
description: Looks words up in FEED, the first-party enough english dictionary, and writes the user's own dictionary entries with them — a coinage, a family word, a term from their field, a private name for a thing, or their own version of a word FEED already has — one column at a time, in FEED's house style. Use for "is X a word", "what does X mean", "look up X", "add X to my dictionary", "put this word in the dictionary", "I made up a word", "my family says X", "fix the entry for X", "my version of X", "define X for me and keep it". Not for translating text (that is the translator skill) and not for spelling or grammar checks of a document (that is analyzer's proofread).
---

# lexicographer

FEED, the **first-party enough english dictionary**, ships with enough: about
96,000 headwords, each a row of columns. Beside it sits the user's **own
dictionary**, which starts empty and holds only what they add. A word in both
is the user's: their version wins everywhere in enough.

Three tools reach them (their tags are in the Tools section):
`dict_lookup`, `dict_add_entry`, `dict_update_entry`. With this skill
switched off, the same guide is one `dict_guide` call away. Writes only ever touch
the user's own dictionary. FEED itself cannot be changed; "fixing" a FEED
word makes the user's own version of it.

---

## The conversation

1. **Look it up first.** Always `dict_lookup` the word before anything
   else, even when you are sure it is new.
2. **If FEED has it, say so** in a sentence (its definition, briefly) and
   offer to show the full entry. Don't add it. If the user wants their own
   sense or wording, that is `dict_update_entry`, and say plainly that their
   version will stand in for FEED's.
3. **If it is new, draft what can be drafted**: pronunciation, part of
   speech, hyphenation, forms, often domain and frequency band. Don't invent
   what only the user knows.
4. **Ask for what can't be known**: what it means, how and where they use
   it, who says it, where it came from. A private or newly made word has no
   source but the user. One or two questions at a time.
5. **Confirm in plain words** before writing: "so: *glimmerwick*, a noun,
   said /ˈɡlɪmərˌwɪk/, meaning … — shall I add it?" Wait for a yes.
6. **Add it** with `dict_add_entry`, then tell them it is in their
   dictionary. The result names the columns **still empty**: mention them
   once and offer to fill any they care about. Leaving them empty is fine.

Never fill the rhyme columns (`perfect_rhymes`, `slant_rhymes`,
`homophones`) or the five-language columns (`fr_compare`, `fr_definition`,
and the same for `es`, `de`, `zh`, `ja`) unless the user asks for them.

---

## The columns

One inner tag per column, named exactly as below. List columns take one item
per line. `definition`, `pos` and `pronunciation` are required to add a
word; everything else can wait.

**word** — lowercase letters a–z only, no spaces, hyphens or apostrophes.
The headword itself, not an inflection: `glimmerwick`, not `glimmerwicks`.

**pronunciation** — broad General American IPA between slashes, rhotic.
`/i/` and `/u/` without length marks, `/ɡ/` not `/g/`, `/j/` not `/y/`,
`/ər/` for the unstressed r-vowel, `/ɑ/` (not `/ɒ/`). Mark primary stress
`ˈ` (and secondary `ˌ`) on every word of two or more syllables, before the
stressed syllable: `/ˈɑrdˌvɑrk/`. Two accepted pronunciations: each in its
own slashes, joined with `, ` — `/ˈtoʊmeɪtoʊ/, /təˈmɑtoʊ/`. Match a
derived word to its base word's sounds.

**pos** — parts of speech, `; `-separated, commonest first: `noun; verb`.
From FEED's list: noun, verb, adjective, adverb, interjection, preposition,
pronoun, conjunction, determiner, numeral, abbreviation, contraction,
prefix, article.

**definition** — 1–3 plain sentences, usually 12–35 words. Neutral, third
person, present tense. No addressing the reader, no jokes, no brackets, no
markdown. Several senses go in one definition, commonest first, joined by
"; also" or a new sentence. Usage labels do not go here.

**usage_note** — register, region, currency or field, as a short label
sentence: `Informal`, `Slang`, `Chiefly British`, `Chiefly British,
informal`, `Archaic`, `Literary`, `Dated`, `Offensive`, `Rare`. Empty for
an ordinary word. For a private word, something like `Family usage` or
`Used among the user's colleagues` is honest.

**domain** — exactly one field, from FEED's 45: agriculture, animals,
architecture, arts, astronomy, biology, business, chemistry, computing,
drink, earth science, economics, education, engineering, environment,
everyday life, fashion, film and media, finance, food, games, general,
geography, government, health, history, home, language, law, literature,
mathematics, medicine, military, music, mythology, philosophy, physics,
plants, politics, psychology, religion, society, sports, technology,
transportation. When nothing fits, `general`.

**first_use** — when the word was first used, in FEED's phrasing:
`Old English`, `Middle English`, `late Middle English`, `17th century`,
`early 20th century`, `mid 19th century`, `late 18th century`,
`by the 19th century`, or a decade, `1990s`, `2020s`. For the user's own
coinage, the decade they started saying it. Prefer the softer phrasing to a
date you can't stand behind.

**frequency_rank** — a band from 0 to 8, 8 the commonest:
8 extremely common (the, of, and) · 7 very common (have, time, people) ·
6 common (house, water, happy) · 5 familiar (window, borrow, gentle) ·
4 occasional (lantern, tidy, frugal) · 3 uncommon (procrastinate, gourd) ·
2 rare (honeypot, gloaming, subfolder) · 1 very rare (smoko, thrapple) ·
0 unrecorded (too rare to count: zorse, subitize). A private word is 0.

**hyphenation** — the word split into syllables with middle dots, for
typesetting: `aard·vark`, `ba·nan·a`, `glim·mer·wick`. A one-syllable word
is just the word.

**etymology** — the origin in one short sentence: `Borrowed from Hawaiian
a'a.` · `Imitative.` · `A blend of glimmer and wick, coined in the user's
family in the 2010s.` Only what is known; never invent a source language.

**examples** — two example sentences, one per line, each showing the word
in ordinary use. Plain, natural, no quotation marks around the sentence.

**synonyms**, **related**, **antonyms** — words, one per line (or one line,
comma-separated). Synonyms: zero to three true equivalents, each a word in
FEED. Related: see-also words. Antonyms only where a real opposite exists;
empty is normal.

**forms** — inflections, one per line: the form, its IPA, its label(s).
`glimmerwicks /ˈɡlɪmərˌwɪks/ pl.` · `runs /rʌnz/ 3rd sing.` · `ran /ræn/
past`. Labels: `pl.`, `3rd sing.`, `pres. part.`, `past`, `comp.`,
`superl.`, `var.`, `arch. var.`, `abbr.`, `form`; two labels for one
spelling are comma-separated (`aahs /ɑz/ pl., 3rd sing.`). Regular forms
only where they are natural.

enough fills the rest itself (`letter`, `length`, `ipa`, `pos_primary`,
`added_on`, `updated_on`, `status`, `source`): don't send them.

---

## An entry, whole

<tool name="dict_add_entry">
<word>glimmerwick</word>
<pronunciation>/ˈɡlɪmərˌwɪk/</pronunciation>
<pos>noun</pos>
<definition>The last small flame of a candle that has burned almost to the bottom, kept alight for company rather than for light.</definition>
<usage_note>Family usage</usage_note>
<domain>home</domain>
<first_use>2010s</first_use>
<frequency_rank>0</frequency_rank>
<hyphenation>glim·mer·wick</hyphenation>
<etymology>A blend of glimmer and wick, coined in the user's family.</etymology>
<examples>
We sat up talking until the glimmerwick went out.
She never blows out a glimmerwick; she waits for it.
</examples>
<forms>
glimmerwicks /ˈɡlɪmərˌwɪks/ pl.
</forms>
</tool>

To change one column later, send only that column with
`dict_update_entry`; an empty tag clears a column. To remove a word the user
uses the dictionary view.

---
enough-tooltip-text: "use lexicographer to look words up in feed, enough's own english dictionary, and to add your own words — coinages, family words, terms from your field — or your own version of a word feed already has."
