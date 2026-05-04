#!/usr/bin/env python3
"""Offline translation via MADLAD-400-3B-MT (CTranslate2 + SentencePiece).

Translates source text into one of ~419 languages, all locally — no network
hop after the model is downloaded. The model file is loaded once per
process; if you're translating many strings, prefer one invocation that
reads from stdin / a file over many one-shots.

Usage:
    # one-shot, text on the command line
    python translate.py --target es "Hello, world."

    # stdin → stdout (useful for piping or multi-paragraph input)
    cat draft.txt | python translate.py --target ja

    # batch mode: one input line per output line
    python translate.py --target fr --batch < lines.txt

    # list common BCP-47 codes that MADLAD accepts
    python translate.py --list-langs

Language codes are short (BCP-47-style) — e.g. "es", "fr", "ja", "zh",
"ar", "sw", "qu" (Quechua), "haw" (Hawaiian), "yo" (Yoruba). MADLAD
formats input as "<2{target_lang}> {text}"; this script handles the
prefix for you. See the model card for the full 419-language list:
https://huggingface.co/google/madlad400-3b-mt

If the model isn't installed yet, this script will tell you to run
bootstrap.py first rather than silently downloading several GB.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Resolved at runtime so a user override via TRANSLATOR_HOME flows through.
MODEL_DIRNAME = "madlad400-3b-ct2"
SP_MODEL_FILENAME = "sentencepiece.model"


def install_root() -> Path:
    """~/.local/share/translator/  (override with TRANSLATOR_HOME)."""
    return Path(
        os.environ.get(
            "TRANSLATOR_HOME",
            str(Path.home() / ".local" / "share" / "translator"),
        )
    )


def model_dir() -> Path:
    return install_root() / MODEL_DIRNAME


def _die(msg: str, code: int = 1) -> None:
    print(f"translate.py: {msg}", file=sys.stderr)
    sys.exit(code)


def _load_translator():
    """Import + instantiate ctranslate2.Translator and the SentencePiece
    processor. Done lazily so --list-langs and --help don't trip on
    missing weights."""
    try:
        import ctranslate2
        import sentencepiece as spm
    except ImportError as e:
        _die(
            f"missing dependency ({e.name}). install with: "
            f"pip install -r requirements.txt"
        )

    md = model_dir()
    if not md.is_dir():
        _die(
            f"model not found at {md}. run `python bootstrap.py --install` "
            f"to download MADLAD-400-3B-MT (~3 GB) first."
        )
    sp_path = md / SP_MODEL_FILENAME
    if not sp_path.is_file():
        _die(f"sentencepiece model missing at {sp_path}. re-run bootstrap.py.")

    sp = spm.SentencePieceProcessor()
    sp.Load(str(sp_path))
    # device="auto" picks Metal/CUDA when available, falls back to CPU.
    # int8 is the right default for the pre-converted weights at
    # santhosh/madlad400-3b-ct2 (already int8-quantized).
    translator = ctranslate2.Translator(str(md), device="auto", compute_type="int8")
    return translator, sp


def translate_one(translator, sp, target: str, text: str) -> str:
    """Translate a single string. MADLAD expects the target language as
    a "<2xx>" token PREFIXED to the source tokens (not as a separate
    field); we follow the recipe from the santhosh/madlad400-3b-ct2
    model card verbatim."""
    if not text.strip():
        return ""
    formatted = f"<2{target}> {text}"
    tokens = sp.EncodeAsPieces(formatted)
    results = translator.translate_batch([tokens])
    out_tokens = results[0].hypotheses[0]
    return sp.DecodePieces(out_tokens)


# A short, opinionated reference list. NOT exhaustive — MADLAD covers
# 419 languages. This is just to help users discover that yes, the
# unusual one they want is probably supported.
COMMON_LANGS = [
    ("en", "English"),
    ("es", "Spanish"),
    ("fr", "French"),
    ("de", "German"),
    ("it", "Italian"),
    ("pt", "Portuguese"),
    ("nl", "Dutch"),
    ("ru", "Russian"),
    ("zh", "Chinese (Simplified)"),
    ("ja", "Japanese"),
    ("ko", "Korean"),
    ("ar", "Arabic"),
    ("hi", "Hindi"),
    ("bn", "Bengali"),
    ("ur", "Urdu"),
    ("fa", "Persian"),
    ("tr", "Turkish"),
    ("vi", "Vietnamese"),
    ("th", "Thai"),
    ("id", "Indonesian"),
    ("ms", "Malay"),
    ("sw", "Swahili"),
    ("yo", "Yoruba"),
    ("ig", "Igbo"),
    ("ha", "Hausa"),
    ("am", "Amharic"),
    ("zu", "Zulu"),
    ("xh", "Xhosa"),
    ("haw", "Hawaiian"),
    ("mi", "Maori"),
    ("sm", "Samoan"),
    ("to", "Tongan"),
    ("qu", "Quechua"),
    ("ay", "Aymara"),
    ("gn", "Guarani"),
    ("nv", "Navajo"),
    ("iu", "Inuktitut"),
    ("cy", "Welsh"),
    ("ga", "Irish"),
    ("gd", "Scottish Gaelic"),
    ("eu", "Basque"),
    ("la", "Latin"),
    ("eo", "Esperanto"),
    ("yi", "Yiddish"),
    ("he", "Hebrew"),
    ("el", "Greek"),
    ("hy", "Armenian"),
    ("ka", "Georgian"),
    ("is", "Icelandic"),
]


def cmd_list_langs() -> int:
    print("Common BCP-47 codes accepted by MADLAD-400 (full list: 419 langs):")
    print()
    for code, name in COMMON_LANGS:
        print(f"  {code:<6}  {name}")
    print()
    print("Full set: https://huggingface.co/google/madlad400-3b-mt#languages")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Offline translation via MADLAD-400-3B-MT.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--target", "-t",
        help='target language code (e.g. "es", "ja", "haw"). required '
             'unless --list-langs.',
    )
    ap.add_argument(
        "text",
        nargs="?",
        help="source text. omit to read from stdin.",
    )
    ap.add_argument(
        "--batch",
        action="store_true",
        help="treat each input line as a separate translation; emit one "
             "output line per input line. ignored when text is on the "
             "command line.",
    )
    ap.add_argument(
        "--list-langs",
        action="store_true",
        help="print a short reference of common language codes and exit.",
    )
    args = ap.parse_args()

    if args.list_langs:
        return cmd_list_langs()
    if not args.target:
        ap.error("--target is required unless --list-langs")

    translator, sp = _load_translator()

    if args.text is not None:
        # one-shot from CLI
        print(translate_one(translator, sp, args.target, args.text))
        return 0

    # stdin
    raw = sys.stdin.read()
    if args.batch:
        for line in raw.splitlines():
            print(translate_one(translator, sp, args.target, line))
    else:
        # whole-stdin as one document; preserve paragraph breaks by
        # translating per-paragraph.
        paragraphs = raw.split("\n\n")
        out = [translate_one(translator, sp, args.target, p) for p in paragraphs]
        print("\n\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
