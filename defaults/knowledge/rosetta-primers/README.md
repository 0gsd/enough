# Rosetta Primers

Bundled, CC-licensed reference material for the languages MADLAD-400
covers — useful as a sanity check, a few-shot grounding source, and a
fallback when the offline translator struggles.

Currently empty. This directory is a placeholder; populate it (or ask
the agent to populate it) from the **Long Now Rosetta Project** on the
Internet Archive:

  https://archive.org/details/rosettaproject

Recommended first-pass material per language:

- **Swadesh list** (~200 core vocabulary items). Compact, dense
  evidence of what the language *looks like* in its native script.
  Useful for verifying MADLAD's lexical choices.
- **Grammar sketch** (1–10 pages). Phonology, morphology, basic
  syntax. Useful for understanding why MADLAD might be producing odd
  word order or missing inflection.
- **Parallel Genesis chapters 1–3** (~2,500 words). The most widely
  parallelized text in human history; gives you aligned source/target
  evidence in essentially every written language. Useful for any
  serious quality check.

## How the translator skill uses these

The skill itself does NOT read this directory automatically — these
are reference materials *for the agent*. When MADLAD output looks
suspect, the orchestrator can grep here for the target language,
quote relevant Swadesh entries or grammar notes, and use them to
verify or repair the translation.

## License hygiene

The Rosetta Project corpus on the Internet Archive is largely CC-BY
or CC-BY-SA, but per-source licensing varies. When you populate a
language subfolder, drop a `_manifest.md` next to the files capturing:

- Source URL(s)
- Retrieval date (use `date -u +"%Y-%m-%d"`)
- License (be specific: CC0 / CC-BY / CC-BY-SA / public domain)
- Any rights notes the source page mentions

Same convention as `rness/io/input/` web caches — see
`rness/paradigms/default.md` for the canonical workflow.

## Suggested layout

    rosetta-primers/
    ├── README.md  (this file)
    ├── haw/
    │   ├── _manifest.md
    │   ├── swadesh.md
    │   ├── grammar-sketch.md
    │   └── genesis-1-3.txt
    ├── qu/
    │   └── ...
    └── nv/
        └── ...

One subfolder per ISO/BCP-47 language code. Keep it flat; depth here
just makes grep slower without helping the agent.
