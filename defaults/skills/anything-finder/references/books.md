# Finding new novels / read-alikes → Kindle links or other storefronts

Goal: from books, authors, or a vibe the user already enjoys, surface **new** reading they
haven't named, and return each as a **Kindle link if available**, otherwise another
storefront/library link. This is recommendation + retrieval: find genuinely apt matches,
then locate where to get each.

## Finding the matches (discovery)

- **Reason from what they gave you.** Extract the *actual* appeal: is it the prose style,
  the structure, the subgenre, the mood, the setting, the ideas? "Like Gene Wolfe" for the
  unreliable narration and dense diction is a different search than "like Gene Wolfe" for
  far-future SF. Name the axis you're matching on.
- **Read-alike sources**: LibraryThing (similar-books + "readers also enjoyed"),
  TheStoryGraph (mood/pace-based similarity), Goodreads ("readers also enjoyed," listopia
  lists), the "if you liked X try Y" columns from Book Riot / Lit Hub / Tor.com / LARB,
  and — via the web — librarian read-alike guides (NoveList-style). Wikipedia's
  genre/movement pages surface adjacent authors.
- **Freshness**: the user wants *new* reading — bias toward books they likely haven't hit,
  including recent releases and deeper-cut backlist, not just the three most-famous
  comps. Include at least one non-obvious pick and say why it fits.
- **Award/venue signals** for quality in a lane: relevant genre awards, notable indie
  presses, or a specific translator/imprint if the appeal is translated literary fiction.

Aim for 4–8 recommendations, each with a one-line "why this, given what you like."

## Locating each book (retrieval)

For each recommended title, find the best link, **Kindle first** per the request:
1. **Amazon Kindle** — search the title + author; return the product URL if a Kindle
   edition exists. Note if it's in **Kindle Unlimited** (free to subscribers).
2. If **no Kindle edition**: give the next-best link — Kobo, Apple Books, Google Play
   Books, the **publisher's** store, **Bookshop.org** (print, indie-supporting),
   or the author's site.
3. **Library option** — always worth noting: **Libby/OverDrive** and **Hoopla** lend
   ebooks free with a library card; **WorldCat** finds a print copy nearby. Many readers
   prefer this; include it as a line, not just for out-of-print books.
4. **Out of print / hard to get**: used via AbeBooks/Biblio/eBay; if the work is old
   enough to be public domain, hand them the free legal etext (see `texts.md`) instead of
   a purchase link.

Verify links resolve before returning (`scripts/link_check.py`).

## Return format

Open with a one-line framing of the through-line you matched on, then a card per book:

```
### <Title> — <Author> (<year>)
- **Get it:** Kindle: <URL>  ·  <Kindle Unlimited: yes/no>  ·  alt: <Libby / Bookshop / Kobo>
- **Why you'll like it:** <1–2 lines tying it to the user's stated taste>
- **Heads-up:** <optional — content, length, "slow burn," "first of a trilogy," translation>
- **Confidence:** <how sure the match is>
```

If Kindle genuinely doesn't carry a title, say so and give the working alternative — don't
fabricate an Amazon URL. If the user's taste is very specific/niche and matches are thin,
return the few strong ones plus an honest "the field is small here; these are the closest."
