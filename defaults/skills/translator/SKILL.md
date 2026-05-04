---
name: translator
description: Offline translation across ~419 languages via MADLAD-400-3B-MT (CTranslate2 + SentencePiece). No cloud. No account. The model downloads once (~3 GB) and runs locally on CPU or Apple Silicon thereafter. Use whenever the user wants to translate text TO or FROM a non-English language — short phrases, paragraphs, whole documents, idioms, low-resource languages, indigenous languages, dead languages MADLAD has seen, polite forms, casual registers. Also trigger on "translate", "say this in <lang>", "what does <foreign text> mean", "render this in <language>", "<lang> for <phrase>", "how do you say X in Y", "localize", or any request that involves moving text between human languages. DO NOT use for code translation between programming languages. DO NOT use for transliteration (script conversion) without a target meaning — MADLAD translates meaning, not glyphs.
---

# translator

Offline machine translation in ~419 languages, running entirely on the
user's machine. Backed by Google's MADLAD-400-3B-MT (Apache 2.0),
served through CTranslate2 with int8 quantization for fast CPU/Metal
inference, and SentencePiece for tokenization.

The model downloads once on first use (~3 GB) into
`~/.local/share/translator/madlad400-3b-ct2/` and never phones home
again. After install, translation works with the network unplugged.

---

## When to use

**Use it for:**

- Translating user-supplied text into another language ("translate this
  to Japanese", "say this in Welsh", "what's this in Quechua")
- Translating foreign-language text the user encounters into English
  ("what does this say", "translate this passage")
- Localizing UI strings, README sections, emails, social posts
- Reading low-resource and indigenous languages MADLAD covers (Hawaiian,
  Yoruba, Navajo, Quechua, Aymara, etc. — see `--list-langs` or the
  model card for the full set)
- Roundtripping a phrase through a third language as a sanity check on
  meaning preservation
- Anything where the user wants translation WITHOUT sending their text
  to Google Translate / DeepL / OpenAI

**Don't use it for:**

- Code translation between programming languages (Python → Rust etc.)
- Transliteration alone (Cyrillic → Latin script with no semantic
  transfer) — MADLAD translates meaning; glyph conversion is a
  different tool
- Sign-language gloss, IPA narrow transcription, or constructed
  languages MADLAD wasn't trained on (Klingon, Dothraki, etc.)
- Live conversation interpretation — this is one-shot batch translation,
  not a streaming interpreter

For higher quality on **low-resource languages specifically** (under-served
African, indigenous American, and Pacific languages), the user can opt
into the NLLB-200 paradigm — see `.rness/paradigms/translation.md`.
NLLB-200 is CC-BY-NC, so it's gated behind that paradigm flag for
personal-use-only contexts. Don't reach for it without checking the
paradigm.

---

## Prerequisites

Python deps (once):

    pip install -r requirements.txt

Then download the default model (~3 GB, one-time):

    python scripts/bootstrap.py --install

`scripts/bootstrap.py --check` is a fast yes/no gate you can call
before any translation to confirm the model is present.

---

## Workflow

Before translating, confirm the model is present:

    python scripts/bootstrap.py --check

If the exit code is non-zero, install it:

    python scripts/bootstrap.py --install

Then translate. Three invocation patterns, in order of preference:

**1. Single short phrase, text on the command line:**

    python scripts/translate.py --target es "Hello, world."

The output is the translated text on stdout. The `<2es>` prefix MADLAD
expects is added for you — you pass plain text, you get plain text.

**2. Paragraph or document via stdin:**

    cat draft.md | python scripts/translate.py --target ja

Paragraph breaks (blank lines) are preserved; each paragraph is
translated independently so the model doesn't lose track over very long
inputs.

**3. Many short strings via stdin, one per output line:**

    python scripts/translate.py --target fr --batch < strings.txt

Use this for UI string lists, glossaries, or any case where each input
line is its own translation unit.

---

## Tool reference

### `scripts/translate.py`

    python scripts/translate.py --target <lang> [text]
    python scripts/translate.py --target <lang> < file.txt
    python scripts/translate.py --target <lang> --batch < lines.txt
    python scripts/translate.py --list-langs

`<lang>` is a short BCP-47-style code: `es`, `fr`, `ja`, `zh`, `ar`,
`sw`, `qu`, `haw`, etc. MADLAD covers ~419 languages — `--list-langs`
prints a curated reference of common ones, but the canonical full list
lives at https://huggingface.co/google/madlad400-3b-mt#languages.

The model auto-detects the source language; you only specify the target.
Mixed-language inputs work but the model will translate the whole thing
into the target.

### `scripts/bootstrap.py`

    python scripts/bootstrap.py --check          # is the 3B model installed?
    python scripts/bootstrap.py --install        # download MADLAD-400-3B-MT (~3 GB)
    python scripts/bootstrap.py --install-7b     # opt-in: also fetch the 7B variant (~7 GB)
    python scripts/bootstrap.py --status         # what's installed and how big
    python scripts/bootstrap.py --where          # print install root
    python scripts/bootstrap.py --uninstall      # remove the 3B install (asks first)

Models go to `~/.local/share/translator/`. Override with the
`TRANSLATOR_HOME` env var if the user wants them somewhere else (e.g.
on an external SSD).

---

## Calibration notes

### Quality expectations

- **High-resource pairs** (en ↔ es/fr/de/ja/zh/etc.): excellent. Often
  competitive with cloud services on prose; sometimes better on idiom.
- **Mid-resource pairs** (en ↔ vi/sw/tr/he/etc.): very good. Occasional
  literal-ness on idiom; names usually preserved well.
- **Low-resource pairs** (en ↔ qu/haw/yo/nv/etc.): mixed. The 3B model
  knows the language but may produce stilted output, repeat tokens, or
  hallucinate near script boundaries. For serious work in these
  languages, consider:
    - The 7B variant (`bootstrap.py --install-7b`) — same family,
      meaningfully better
    - The NLLB-200 paradigm option, if the user has accepted its
      CC-BY-NC license terms
    - The Rosetta primers reference set in
      `.rness/knowledge/rosetta-primers/` — bundled Swadesh lists,
      grammar sketches, and parallel Genesis translations from the
      Long Now Rosetta Project, useful as a sanity check or as
      few-shot grounding when MADLAD is shaky

### Performance expectations

- First translation in a fresh process: 5–15s (model loading dominates).
- Subsequent translations in the same process: sub-second for short
  strings, a few seconds per paragraph.
- If you're translating many strings, prefer **one** invocation over
  many — the load cost amortizes across the batch.

### Context-window note

MADLAD is a sentence-to-paragraph model, not a long-document model. Very
long single inputs (>2000 tokens) may degrade. translate.py handles this
by splitting on paragraph breaks (`\n\n`) and translating each chunk
independently — so a 50-paragraph document works fine. If the user has
one paragraph that's 3000 words long, that's where you'd want to split
manually first.

---

## Integration

This skill is invoked directly by the orchestrator agent (you) via the
`shell` tool. It does NOT call other skills, and is NOT called by other
skills as a library. The contract is:

1. The user expresses a translation need (in any phrasing).
2. You decide the source/target language pair from the request.
3. You shell out to `translate.py` with the right `--target`.
4. You return the result to the user, plus any caveats — flag low-
   resource pairs as "best-effort, may be stilted", suggest the 7B
   variant or NLLB if the user is doing serious work.

The skill should NEVER be invoked through the LLM — translate.py is a
direct ct2 call. Sending translation work to llama-server is a category
error: the LLM is the *router*, MADLAD is the *translator*.

---

## Sovereignty notes

This skill is a deliberate implementation of enough's "no cloud
dependency, no SDK lock-in" principle for a high-stakes capability:

- All weights are Apache 2.0 (3B and 7B variants both).
- No vendor account, no API key, no rate limit.
- After the one-time model download, translation works fully offline —
  on a laptop on a plane, in a tent, in a SCIF.
- The skill folder is portable: copy `defaults/skills/translator/` into
  any RNESS install and it works after `pip install -r requirements.txt
  && python bootstrap.py --install`.
- No filesystem state outside `~/.local/share/translator/` (the model
  cache) and the project's own session logs (the agent's choice).

If the user wants higher-quality translation for low-resource languages
and is willing to accept a non-commercial license for personal use, the
NLLB-200 paradigm (gated behind a flag in
`.rness/paradigms/translation.md`) provides that path — explicitly,
with the license tradeoff visible.
