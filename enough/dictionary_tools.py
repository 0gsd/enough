"""The readvisor's three FEED tools: look a word up, add the user's own word,
change an entry.

Registered into `tools._DISPATCH` the way `pal_tools` is. Everything goes
through `enough.dictionary`'s Python API, and every write lands in the user's
own dictionary (`user-dictionary.sqlite`) and nowhere else: FEED itself is
read-only here, and "changing" a FEED word makes the user's own version of
it, which then wins everywhere.

`dict_guide` hands back the `lexicographer` skill's column guide, from the
install's own copy: the skill is off by default like every shipped skill, so
this is how the guide reaches a model that lacks it, without a path to
remember. (`read_file` can also follow the skill's symlink since 0.4.1.)

There is no broker toggle. The other tool gates guard something leaving the
machine (`ask_pal`) or text entering the system prompt (`install_readvisor`);
a word in the user's own dictionary is neither, and it can be deleted from
the dictionary view. The documentation is gated instead, on the
`lexicographer` skill (see `prompt.DICTIONARY_TOOL_INSTRUCTIONS`).

Each result is written for the model to act on: a compact reading of the
entry (not the rhyme lists or the five-language columns), and for the
user's own words the columns still empty, so the model can ask about them.
A dictionary that is not built or not shipped is a sentence, never a raise.

Spec: docs/feed-041-plan.md ("FEED and the readvisor").
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

log = logging.getLogger("enough.dictionary_tools")

TOOL_NAMES: tuple[str, ...] = ("dict_lookup", "dict_add_entry", "dict_update_entry", "dict_guide")

#: The SSE event a successful write emits, so an open dictionary view can
#: refresh: `{word, action}`.
SIDE_EFFECT = "dict_changed"

#: List columns: one item per line in a tool call.
LIST_COLUMNS = ("examples", "synonyms", "related", "antonyms", "forms")
#: Word lists that also accept one comma-separated line.
_WORD_LISTS = ("synonyms", "related", "antonyms", "homophones", "perfect_rhymes", "slant_rhymes")

#: The form labels FEED uses (its `labels` table).
FORM_LABELS = ("pl.", "3rd sing.", "pres. part.", "past", "comp.", "superl.", "var.", "arch. var.",
               "abbr.", "form")

_BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


def _tools():
    from . import tools as _t
    return _t


def _feed():
    from . import dictionary as _d
    return _d


def _result(name: str, key: str, ok: bool, body: str, side_effects: dict | None = None) -> Any:
    return _tools().ToolResult(name, key, ok, body, side_effects=side_effects or {})


def _err(name: str, key: str, message: str) -> Any:
    return _result(name, key, False, message)


def _unavailable(name: str, key: str) -> Any | None:
    """A sentence for the model when there is no dictionary to read, else None."""
    try:
        st = _feed().status()
    except Exception as e:  # noqa: BLE001 — a status failure is still not a raise
        log.warning("dictionary status failed: %s", e)
        return _err(name, key, "error: the dictionary could not be opened just now. "
                               "Tell the user, and carry on without it.")
    if not st.get("available"):
        return _err(name, key, "error: this install of enough has no dictionary (FEED is not "
                               "bundled). Tell the user; there is nothing to look up or add to.")
    if not st.get("ready") and st.get("error") and not st.get("building"):
        return _err(name, key, f"error: the dictionary could not be prepared ({st['error']}). "
                               f"Tell the user; restarting enough retries it.")
    if not st.get("ready"):
        pct = int(round(float(st.get("progress") or 0) * 100))
        return _err(name, key, f"error: the dictionary is still being prepared ({pct}% done). "
                               f"Tell the user it will be ready in a minute or two, and try again "
                               f"then.")
    return None


# ---------------------------------------------------------------------------
# Rendering an entry
# ---------------------------------------------------------------------------

def _list(value: Any) -> list:
    return value if isinstance(value, list) else ([] if value in (None, "") else [value])


def _form_text(f: Any) -> str:
    if not isinstance(f, dict):
        return str(f)
    out = f.get("word") or ""
    if f.get("pronunciation"):
        out += f" {f['pronunciation']}"
    if f.get("labels"):
        out += f" ({', '.join(f['labels'])})"
    return out


def render_entry(e: dict, *, matched_form: str | None = None) -> str:
    """A compact, column-labelled reading of one entry. Labels are the column
    names, so what the model reads is what it would write back."""
    word = e.get("word") or "?"
    if e.get("origin") == "user":
        whose = ("the user's own version of a feed word" if e.get("overrides_feed")
                 else "the user's own entry")
    else:
        whose = "feed"
    lines = [f"{word} — {whose}"]
    if matched_form:
        lines.append(f"({matched_form} is a form of {word})")
    for col in ("pronunciation", "pos", "definition", "usage_note", "domain", "first_use"):
        if e.get(col):
            lines.append(f"{col}: {e[col]}")
    band = e.get("frequency_rank")
    if band is not None:
        name = ((e.get("frequency_band") or {}).get("name") or "").lower()
        lines.append(f"frequency_rank: {band}" + (f" ({name})" if name else ""))
    for col in ("hyphenation", "etymology"):
        if e.get(col):
            lines.append(f"{col}: {e[col]}")
    examples = _list(e.get("examples"))
    if examples:
        lines.append("examples:")
        lines += [f"- {x}" for x in examples]
    for col in ("synonyms", "related", "antonyms"):
        items = _list(e.get(col))
        if items:
            lines.append(f"{col}: {', '.join(str(x) for x in items)}")
    forms = _list(e.get("forms"))
    if forms:
        lines.append("forms: " + "; ".join(_form_text(f) for f in forms))
    if e.get("origin") == "user":
        empty = [c for c in _feed().REPORTED if e.get(c) in (None, "", [])]
        if empty:
            lines.append(f"still empty: {', '.join(empty)}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Reading a call's columns
# ---------------------------------------------------------------------------

def _items(raw: str, col: str) -> list[str]:
    lines = [_BULLET_RE.sub("", ln).strip() for ln in (raw or "").splitlines()]
    lines = [ln for ln in lines if ln]
    if col in _WORD_LISTS and len(lines) == 1 and "," in lines[0]:
        lines = [w.strip() for w in lines[0].split(",") if w.strip()]
    return lines


def parse_form(line: str) -> dict | None:
    """`aardvarks /ˈɑrdˌvɑrks/ pl.` (pronunciation and labels optional; several
    labels comma-separated) -> a `forms` item."""
    m = re.match(r"^\s*([^\s/(]+)\s*(/[^/]*/)?\s*\(?(.*?)\)?\s*$", line)
    if not m:
        return None
    labels = [lb.strip() for lb in (m.group(3) or "").split(",") if lb.strip()]
    return {"word": m.group(1).strip().lower(), "pronunciation": (m.group(2) or "").strip(),
            "labels": labels, "synonyms": []}


def fields_from_call(call: Any) -> tuple[str, dict]:
    """(word, {column: value}) from a call's inner tags. List columns arrive one
    item per line; `forms` lines are parsed into form records."""
    extra = dict(getattr(call, "extra", None) or {})
    word = (extra.pop("word", "") or "").strip()
    fields: dict[str, Any] = {}
    for col, raw in extra.items():
        col = col.strip().lower()
        if col in LIST_COLUMNS or col in _WORD_LISTS:
            items = _items(raw, col)
            if col == "forms":
                fields[col] = [f for f in (parse_form(x) for x in items) if f]
            else:
                fields[col] = items
        elif col == "frequency_rank":
            # "3 (uncommon)" is a band with its name beside it.
            m = re.match(r"^\s*(\d+)\b", raw or "")
            fields[col] = m.group(1) if m else raw
        else:
            fields[col] = raw
    return word, fields


def _write_summary(verb: str, res: dict) -> str:
    word = res.get("word") or "?"
    if res.get("ok"):
        head = f"ok — {verb} {word!r} in the user's own dictionary"
        if res.get("overrides_feed"):
            head += " (their version now stands in for feed's everywhere)"
        missing = res.get("missing") or []
        tail = (f"\nstill empty: {', '.join(missing)} — ask the user about any that matter to "
                f"them, or leave them." if missing else "\nevery column a conversation can fill is filled.")
        return head + "." + tail
    msg = f"error: {res.get('error') or 'the entry was not saved'}"
    if res.get("missing"):
        msg += f"\nneeded first: {', '.join(res['missing'])}"
    if "unknown column" in (res.get("error") or ""):
        msg += (f"\ncolumns you can write: {', '.join(_feed().REPORTED)} (the rhyme and "
                f"five-language columns too, but only when the user asks for them)")
    return msg


# ---------------------------------------------------------------------------
# The tools
# ---------------------------------------------------------------------------

def run_dict_lookup(project_dir: Path, call: Any) -> Any:
    """`dict_lookup <word>` — the entry, or "not in feed" with near words."""
    word, _fields = fields_from_call(call)
    if not word:
        return _err("dict_lookup", "", "error: dict_lookup needs the word in a <word> tag.")
    blocked = _unavailable("dict_lookup", word)
    if blocked is not None:
        return blocked
    D = _feed()
    try:
        res = D.lookup(word)
    except D.DictionaryUnavailable as e:
        return _err("dict_lookup", word, f"error: the dictionary is not ready ({e}). Try again "
                                         f"in a minute.")
    except Exception as e:  # noqa: BLE001
        log.exception("dict_lookup failed")
        return _err("dict_lookup", word, f"error: the lookup failed ({type(e).__name__}).")
    if res.get("found"):
        return _result("dict_lookup", word, True,
                       render_entry(res["entry"], matched_form=res.get("matched_form")))
    near = res.get("suggestions") or []
    body = f"{res.get('query') or word!r} is not in feed or the user's own dictionary."
    if near:
        body += f"\nnear words: {', '.join(near)}"
    return _result("dict_lookup", word, True, body)


def _run_write(name: str, call: Any, add: bool) -> Any:
    word, fields = fields_from_call(call)
    if not word:
        return _err(name, "", f"error: {name} needs the word in a <word> tag.")
    blocked = _unavailable(name, word)
    if blocked is not None:
        return blocked
    D = _feed()
    try:
        if add:
            res = D.user_add(dict(fields, word=word))
        else:
            res = D.user_update(word, fields)
    except D.DictionaryUnavailable as e:
        return _err(name, word, f"error: the dictionary is not ready ({e}).")
    except Exception as e:  # noqa: BLE001
        log.exception("%s failed", name)
        return _err(name, word, f"error: the entry could not be saved ({type(e).__name__}: {e}).")
    body = _write_summary("added" if add else "updated", res)
    if not res.get("ok"):
        return _err(name, res.get("word") or word, body)
    return _result(name, res["word"], True, body,
                   {SIDE_EFFECT: {"word": res["word"], "action": "add" if add else "update"}})


def guide_text() -> str | None:
    """The shipped `lexicographer` SKILL.md, frontmatter and tooltip line
    dropped. Always the install's copy, never a project's: a project-local
    `lexicographer` folder would be an unaudited skill."""
    from . import prompt as _prompt
    from . import skeleton as _skeleton
    path = _skeleton._install_defaults_root() / "skills" / "lexicographer" / "SKILL.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    _meta, body = _prompt._parse_paradigm_frontmatter(text)
    lines = [ln for ln in body.strip().splitlines() if not ln.startswith("enough-tooltip-text:")]
    while lines and lines[-1].strip() in ("", "---"):
        lines.pop()
    return "\n".join(lines).strip()


def run_dict_guide(project_dir: Path, call: Any) -> Any:
    """`dict_guide` — no tags. The column-by-column guide to writing an entry."""
    text = guide_text()
    if not text:
        return _err("dict_guide", "", "error: this install has no lexicographer guide. Write the "
                                      "entry in plain, neutral style and ask the user what you "
                                      "cannot know.")
    return _result("dict_guide", "", True, text)


def run_dict_add_entry(project_dir: Path, call: Any) -> Any:
    """`dict_add_entry <word> <column>…` — a new word in the user's dictionary."""
    return _run_write("dict_add_entry", call, add=True)


def run_dict_update_entry(project_dir: Path, call: Any) -> Any:
    """`dict_update_entry <word> <column>…` — change the user's entry, or make
    their own version of a feed entry. An empty tag clears that column."""
    return _run_write("dict_update_entry", call, add=False)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_RUNNERS = {
    "dict_lookup": run_dict_lookup,
    "dict_add_entry": run_dict_add_entry,
    "dict_update_entry": run_dict_update_entry,
    "dict_guide": run_dict_guide,
}


def register() -> None:
    """Add the three tools to `tools._DISPATCH` and `_TRACE_TOGGLE`. Idempotent,
    called once at `tools` import time; traced under the universal toggle, like
    every other tool that writes something of the user's."""
    t = _tools()
    for tool_name, runner in _RUNNERS.items():
        t._DISPATCH.setdefault(tool_name, runner)
        t._TRACE_TOGGLE.setdefault(tool_name, "trace_log_enabled")


__all__ = ["FORM_LABELS", "SIDE_EFFECT", "TOOL_NAMES", "fields_from_call", "parse_form", "register",
           "guide_text", "render_entry", "run_dict_add_entry", "run_dict_guide", "run_dict_lookup",
           "run_dict_update_entry"]
