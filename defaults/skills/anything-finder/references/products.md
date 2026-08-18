# Finding hard-to-find products → buy URLs, or an honest "closest thing / gap"

Goal: find where to buy the specific product the user is after (with a focus on tech and
musical instruments), OR — when it doesn't seem to exist — deliver a *genuinely useful*
answer: the closest existing items, why the exact thing may not exist, and any DIY /
commission / import route. "It doesn't exist, here's why, here's the nearest thing" is a
first-class result, not a dead end.

## Where to look

**General + long-tail retail:** the open web with precise model numbers; Amazon, eBay
(incl. completed/sold listings for discontinued gear + price reality), AliExpress/
Alibaba (for "surely a factory makes this" OEM/import items), Etsy (handmade/custom),
niche specialist retailers.

**Tech / electronics / components:** manufacturer sites (for spec confirmation + "where
to buy"), Digi-Key / Mouser / LCSC (components, dev boards), Adafruit / SparkFun / Pimoroni
(maker hardware), Newegg / B&H (consumer tech), Tindie (indie hardware), Crowd Supply /
Kickstarter / Indiegogo (does it exist yet as a project?). For discontinued tech, eBay
sold listings and forums reveal both availability and going rate.

**Musical instruments & audio gear:**
- **Reverb** (reverb.com) — the deep marketplace for new/used/vintage/boutique
  instruments, synths, pedals, and studio gear. First stop for anything musical.
- **Vintage/rare**: eBay, Reverb, specialist dealers, Chuck Levin's / Sweetwater / Thomann
  (EU) / Andertons, Perfect Circuit & Schneidersladen (synths/modular), ModularGrid (find
  a Eurorack module + who stocks it), Vintage King (studio).
- **Discontinued / boutique / one-person builders**: builder sites, Instagram/forum shops,
  Gearspace/MOD Wiggler/VG forums, waitlists.

**Discovery/aggregation:** Google Shopping, price-comparison engines, and — for "I don't
know the name of it but it does X" — search by *function and form* ("guitar pedal that
does <specific behavior>", "MIDI controller with <feature>"), then identify the product,
then find stock.

## Deep-search moves

- Nail the **exact identifier** (model number, revision, year) — vague names find nothing.
  If the user is fuzzy, first identify the precise product, then locate stock.
- Search **eBay sold/completed listings** for discontinued items: confirms it exists,
  what it really sells for, and how often one surfaces.
- Search **forums and subreddits** for the item — enthusiasts know the alternate names,
  the successor model, the clone, and the guy who still makes it.
- For "does this exist yet," check crowdfunding + the patent/prior-art angle
  (`references/patents.md` confirms whether someone has at least *designed* it). If the
  user's real question is "should I build this," that's `references/venture.md`, and this
  sweep is its first phase.
- International: the thing may exist only in another market (JP/EU/CN). Search local
  retailers and note import/voltage/region caveats.

## When it doesn't exist — deliver this

1. **State it clearly**: "I couldn't find this exact product for sale anywhere; here's
   what I did find and why."
2. **Closest existing items** as find cards, with how each differs from the ideal.
3. **Why the gap may exist**: technical limitation, tiny market, patent/licensing block,
   discontinued and never replaced, or it exists only as a DIY/mod.
4. **Paths to get it anyway** where apt: a DIY build (kit, schematic, module combo), a
   commission from a known builder, an OEM/factory-direct order, or a software/firmware
   substitute.

## Return format

```
### <Product — exact model/name>
- **Buy:** <URL(s), best price/condition first>
- **Source:** <Reverb | eBay (sold: $X range) | manufacturer | Digi-Key | Tindie…>
- **Condition / market:** <new | used | vintage; typical price; how often it appears>
- **Caveats:** <region/voltage, discontinued, waitlist, import duty>
- **Confidence:** <…>
```

Prices and stock move fast — note that the figures are as-of-now and give the user the
live link to confirm. Don't invent a listing; if you can't verify current stock, say the
item exists and point to the marketplace search that will surface it.
