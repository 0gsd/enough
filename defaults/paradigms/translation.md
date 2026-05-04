# Translation Paradigm

This paradigm declares offline machine translation as a first-class
capability of this enough instance. When it's in scope, the agent has a
permanent, locally-hosted, ~419-language translator at hand — no cloud
dependency, no account, no rate limit.

The actual translation work is done by the `translator` skill (see
`.rness/.skills/translator/`). This paradigm tells you when and how to
reach for it.

## Capability summary

- **Default engine:** MADLAD-400-3B-MT (Apache 2.0), served via
  CTranslate2 with int8 quantization. ~3 GB on disk, runs on
  CPU or Apple Silicon.
- **Coverage:** ~419 languages, including most national languages and
  a meaningful long tail of indigenous, regional, and low-resource
  languages.
- **Round-trip:** plain text in, plain text out. Source language is
  auto-detected; only the target needs to be specified.
- **First-use cost:** one-time model download (~3 GB). After that,
  fully offline.

## When to route to the translator skill

Route translation requests to `translator` whenever the user wants to
move text between human languages. Specifically:

- Direct phrasing: "translate this", "say X in Y", "what does this
  mean", "render this in <language>", "how do you say X in Y".
- Implied phrasing: user pastes foreign-language text and asks "what's
  this", "summarize this", or "what's it about" — translate first if
  needed, then act on the translation.
- Long-form: user asks to read or summarize a foreign-language document
  — translate paragraph-by-paragraph (translate.py handles this
  automatically), then synthesize.
- Localization: user wants to render a draft (UI strings, README,
  email, announcement) in another language.

Don't route programming-language conversion or transliteration-only
requests to this skill — see the skill's "Don't use it for" section.

## Routing decision: which model variant?

There are three weight options, gated by license and resource trade-offs:

1. **MADLAD-400-3B (default).** Apache 2.0. The right choice for almost
   all requests. Use unless one of the conditions below applies.

2. **MADLAD-400-7B (opt-in).** Apache 2.0. Better quality across the
   board, especially on low-resource languages, at ~7 GB on disk. Use
   when:
    - The user explicitly asks for higher-quality translation.
    - The request is in a low-resource language pair AND the work is
      load-bearing (publication, legal, medical).
    - The 3B output looks visibly stilted or the user pushes back on
      quality.
   Install via `python scripts/bootstrap.py --install-7b` from the
   skill folder. Both can coexist; translate.py uses 3B by default.

3. **NLLB-200 (license-gated).** CC-BY-NC. Often better than MADLAD on
   the very long tail of low-resource languages. Strictly personal /
   non-commercial use. Use ONLY when:
    - The user has explicitly enabled it via the **NLLB opt-in flag**
      below.
    - AND the work is for personal, non-commercial purposes.
    - AND the target language is one MADLAD struggles with materially.

   Default state: **NLLB-200 is OFF.** To enable, the user adds the
   following line to this paradigm file:

       nllb_optin: true   # personal, non-commercial use only — I accept the CC-BY-NC terms

   Until that flag is present, do NOT install or invoke NLLB-200, even
   if the user asks for "the best possible translation". Surface the
   tradeoff first; let them opt in explicitly.

## Fallback policy

When MADLAD output looks degraded (visible repetition, untranslated
spans, near-gibberish), in this order:

1. **Re-attempt with paragraph splits.** Sometimes a long input causes
   degradation that a chunked re-run fixes.
2. **Suggest the 7B variant**, with the disk and time costs surfaced.
3. **Consult the Rosetta primers** at `.rness/knowledge/rosetta-primers/`
   if populated for the target language — Swadesh lists, grammar
   sketches, and parallel Genesis from the Long Now Rosetta Project.
   Use them as ground truth to verify or repair MADLAD output, not as
   a primary translation source.
4. **Suggest NLLB-200 opt-in**, only if appropriate per the rules above.
5. **Tell the user the limit.** If MADLAD and NLLB both fail, name the
   limit honestly: "this language pair is at the edge of what offline
   models do well — here's the literal output, here's where it likely
   went wrong, would you like me to consult a human translator
   reference, or fall back to a cloud service (with the privacy
   tradeoff)?"

## Modality & invocation

Translation lives entirely in the **runtime** — it is NOT baked into
the enough core, NOT served through llama-server, and NOT mediated by
the LLM at the inference layer. The flow is:

    user request
      → orchestrator LLM decides "this is a translation request"
      → orchestrator invokes the `translator` skill via the shell tool
      → translator runs ct2 + sentencepiece directly
      → result returned to orchestrator
      → orchestrator presents to user, with caveats if any

The LLM is the *router*, MADLAD is the *translator*. Don't try to
translate via prompt engineering if the skill is available — it'll be
slower, lower quality, and wastes the dedicated MT model that's already
on disk.

## Sovereignty & paradigmless principles

This paradigm exists because translation is a high-stakes capability
that, when delivered through cloud services, costs the user their
sovereignty over the text being translated. Diplomatic cables, legal
drafts, personal correspondence, medical records, queer love letters in
languages the writer's family won't see — none of those should leave
the user's machine for a translation feature to work.

The implementation choices reflect this:

- Filesystem only. No database, no vector store, no cloud cache.
- No SDK lock-in. Plain Python + ctranslate2 + sentencepiece +
  huggingface_hub. Anyone can read, audit, fork, or rip out the entire
  stack.
- Skill is portable. The `defaults/skills/translator/` folder drops
  cleanly into any other enough install.
- Models are user-controlled. They live at
  `~/.local/share/translator/` (override with `TRANSLATOR_HOME`); the
  user can move, mirror, archive, or delete them at any time.

## Configuration knobs

This paradigm currently exposes one explicit user-toggleable flag:

    nllb_optin: false    # set to true to enable CC-BY-NC NLLB-200 fallback
                         # (personal, non-commercial use only)

The rest is convention: the agent reads this file, knows the routing
rules above, and decides per-request which engine to invoke.
