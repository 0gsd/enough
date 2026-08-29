#!/usr/bin/env python3
"""Structural parity check for the UI translations (i18n round).

Run it after ANY change to English chrome strings or help content:

    uv run python scripts/i18n_check.py

It compares every shipped language under enough/static/i18n/ against the
English sources and prints exactly what is missing or stale, per
language, per file. Exit 0 = everything in lockstep; exit 1 = the report
is your to-do list. tests/test_i18n.py runs the same checks, so a
release can't ship drift silently. The full update process lives in
docs/I18N.md.

What "parity" means here (structure, not wording):
  ui.json          key set identical to en/ui.json; values non-empty
  help-docs.md     same `## <id>` set as static/help-docs.md; identical
                   `path:` values; same {{token}} usage; same number of
                   fenced-code markers
  help-center.md   same heading counts per level as docs/HELP_CENTER.md;
                   same {{token}} usage; same fenced-code markers

The canonical en/ui.json is additionally checked against index.html: the
key set used in markup (data-i18n*) plus t() call sites must equal the
catalog exactly — no dead keys, no unlisted keys.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STATIC = REPO / "enough" / "static"
I18N = STATIC / "i18n"
LANGS = ("fr", "es", "de", "zh", "ja")  # en is the baked-in source

INDEX = STATIC / "index.html"
EN_CATALOG = I18N / "en" / "ui.json"
EN_HELP_DOCS = STATIC / "help-docs.md"
EN_HELP_CENTER = REPO / "docs" / "HELP_CENTER.md"


def _catalog_keys(path: Path) -> tuple[set[str], list[str]]:
    """(key set, problems) for one ui.json catalog."""
    problems: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return set(), [f"{path.name}: unreadable/invalid JSON ({e})"]
    strings = data.get("strings")
    if not isinstance(strings, dict):
        return set(), [f"{path.name}: no 'strings' object"]
    for k, v in strings.items():
        if not isinstance(v, str) or not v.strip():
            problems.append(f"{path.name}: empty/non-string value for key '{k}'")
    meta = data.get("_meta") or {}
    lang = path.parent.name
    if meta.get("language") != lang:
        problems.append(f"{path.name}: _meta.language should be '{lang}'")
    return set(strings), problems


def _index_keys() -> set[str]:
    """Every i18n key index.html actually uses (markup attrs + t() calls)."""
    html = INDEX.read_text(encoding="utf-8")
    keys = set(re.findall(r'data-i18n(?:-title|-placeholder|-aria)?="([^"]+)"', html))
    keys |= set(re.findall(r"\bt\(\s*'([^']+)'\s*,", html))
    return keys


def _help_doc_sections(path: Path) -> tuple[set[str], dict[str, str]]:
    """({ids}, {id: path-line-value}) for a help-docs.md file."""
    ids: set[str] = set()
    paths: dict[str, str] = {}
    cur = None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m and not line.startswith("###"):
            cur = m.group(1)
            ids.add(cur)
            continue
        m = re.match(r"^path:\s*(.*)$", line)
        if m and cur is not None and cur not in paths:
            paths[cur] = m.group(1).strip()
    return ids, paths


def _tokens(text: str) -> Counter:
    return Counter(re.findall(r"\{\{[a-z-]+\}\}", text))


def _fences(text: str) -> int:
    return len(re.findall(r"^```", text, re.M))


def _heading_counts(text: str) -> Counter:
    return Counter(len(m.group(1)) for m in re.finditer(r"^(#{1,4})\s", text, re.M))


def check() -> list[str]:
    """All problems across the shipped languages, formatted for humans."""
    problems: list[str] = []

    # --- the canonical catalog vs index.html ---
    if not EN_CATALOG.is_file():
        return [f"MISSING {EN_CATALOG.relative_to(REPO)} — run the sweep first"]
    en_keys, probs = _catalog_keys(EN_CATALOG)
    problems += [f"en: {p}" for p in probs]
    used = _index_keys()
    for k in sorted(used - en_keys):
        problems.append(f"en: index.html uses key '{k}' missing from en/ui.json")
    for k in sorted(en_keys - used):
        problems.append(f"en: en/ui.json key '{k}' is unused in index.html (dead key)")

    en_ids, en_paths = _help_doc_sections(EN_HELP_DOCS)
    en_docs_text = EN_HELP_DOCS.read_text(encoding="utf-8")
    en_center_text = EN_HELP_CENTER.read_text(encoding="utf-8")

    # --- each shipped language ---
    for lang in LANGS:
        base = I18N / lang
        if not base.is_dir():
            problems.append(f"{lang}: missing folder enough/static/i18n/{lang}/")
            continue

        cat = base / "ui.json"
        if not cat.is_file():
            problems.append(f"{lang}: missing ui.json")
        else:
            keys, probs = _catalog_keys(cat)
            problems += [f"{lang}: {p}" for p in probs]
            for k in sorted(en_keys - keys):
                problems.append(f"{lang}: ui.json missing key '{k}'")
            for k in sorted(keys - en_keys):
                problems.append(f"{lang}: ui.json has unknown key '{k}' (not in en)")

        hd = base / "help-docs.md"
        if not hd.is_file():
            problems.append(f"{lang}: missing help-docs.md")
        else:
            text = hd.read_text(encoding="utf-8")
            ids, paths = _help_doc_sections(hd)
            for i in sorted(en_ids - ids):
                problems.append(f"{lang}: help-docs.md missing section '## {i}'")
            for i in sorted(ids - en_ids):
                problems.append(f"{lang}: help-docs.md extra section '## {i}'")
            for i, p in sorted(en_paths.items()):
                if i in ids and paths.get(i, "") != p:
                    problems.append(
                        f"{lang}: help-docs.md '## {i}' path line differs "
                        f"(paths are never translated)")
            if _tokens(text) != _tokens(en_docs_text):
                problems.append(f"{lang}: help-docs.md {{{{token}}}} usage differs from English")
            if _fences(text) != _fences(en_docs_text):
                problems.append(f"{lang}: help-docs.md fenced-code count differs from English")

        hc = base / "help-center.md"
        if not hc.is_file():
            problems.append(f"{lang}: missing help-center.md")
        else:
            text = hc.read_text(encoding="utf-8")
            if _heading_counts(text) != _heading_counts(en_center_text):
                problems.append(
                    f"{lang}: help-center.md heading structure differs from English "
                    f"({dict(_heading_counts(text))} vs {dict(_heading_counts(en_center_text))})")
            if _tokens(text) != _tokens(en_center_text):
                problems.append(f"{lang}: help-center.md {{{{token}}}} usage differs from English")
            if _fences(text) != _fences(en_center_text):
                problems.append(f"{lang}: help-center.md fenced-code count differs from English")

    return problems


def main() -> int:
    problems = check()
    if not problems:
        n = len(LANGS)
        print(f"i18n parity OK — en catalog + {n} languages in lockstep.")
        return 0
    print(f"i18n parity: {len(problems)} problem(s)\n")
    for p in problems:
        print(f"  - {p}")
    print("\nFix the files above (docs/I18N.md documents the process), then re-run.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
