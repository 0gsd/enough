"""The brief introduction to enough, delivered without a model call.

One owner-editable English text, `defaults/intro.md`, with translations at
`enough/static/i18n/<lang>/intro.md` when they exist (English otherwise, the
same fallback `/api/help-center` uses). The install file is the single
source: there is no per-user or per-project copy, so an edit reaches every
project at once.

Three doors, one text:

- `GET /api/intro?lang=` — for the empty conversation's affordance;
- a whole-message match in `/api/chat` on a short, explicit list of
  "what is this?" questions (and `/intro`), answered on the spot;
- the `show_intro` tool, which the chief readvisor calls when the user takes
  them up on the offer of an introduction. Its result tells the model the
  text is already on screen, so it is not said twice.

The bubble is the chief readvisor's (the text is written in their voice) and
carries the markdown source with `data-markdown`, for the chat to render.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Callable

from . import prompt as prompt_mod

log = logging.getLogger("enough.intro")

INSTALL_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = Path(__file__).resolve().parent / "static"
LANGS = ("en", "fr", "es", "de", "zh", "ja")

TOOL_NAMES: tuple[str, ...] = ("show_intro",)

#: The SSE event `show_intro` asks the chat for: `{html, text, speaker}`.
SIDE_EFFECT = "intro"

#: What a chat message must be, whole, after `normalize()`, to be answered
#: with the introduction instead of a model turn. Edit here and only here.
#: Everything but `/intro` counts only while the conversation is empty: later
#: on, "what is this?" is far more likely to be about something on screen.
INTRO_PHRASES: tuple[str, ...] = (
    "what can you do",
    "what can enough do",
    "what is enough",
    "what is this",
    "help",
)
INTRO_COMMAND = "/intro"

#: The `show_intro` result, addressed to the model.
RESULT_SHOWN = (
    "ok — the introduction to enough is now on the user's screen, just above "
    "your reply, in your voice. Don't repeat or summarize it; ask what they "
    "would like to do first, or answer what they asked alongside it."
)
RESULT_MISSING = (
    "error: this install has no introduction text (defaults/intro.md is "
    "missing). Tell the user in a sentence or two what enough is instead."
)

# The UI language, supplied by the server (it owns the ui config). Tests and
# a server that never set it get English.
_language_source: Callable[[], str] | None = None


def set_language_source(fn: Callable[[], str] | None) -> None:
    global _language_source
    _language_source = fn


def current_language() -> str:
    try:
        lang = _language_source() if _language_source else "en"
    except Exception:  # noqa: BLE001 — a language lookup never costs the intro
        lang = "en"
    return lang if lang in LANGS else "en"


# ---------------------------------------------------------------------------
# The text
# ---------------------------------------------------------------------------

def english_path() -> Path:
    return INSTALL_ROOT / "defaults" / "intro.md"


def path_for(lang: str | None) -> Path:
    """The file to serve for `lang`: its translation when one ships, else the
    English source. `lang` is used as a path only when it is one of ours."""
    if lang in LANGS and lang != "en":
        translated = STATIC_DIR / "i18n" / lang / "intro.md"
        if translated.is_file():
            return translated
    return english_path()


def text_for(lang: str | None = None) -> str | None:
    """The introduction's markdown, or None when the install has none."""
    path = path_for(lang if lang is not None else current_language())
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def is_intro_text(content: str) -> bool:
    """True when an assistant history entry is the introduction (in any
    shipped language), so a reload draws it as the intro bubble again."""
    body = (content or "").strip()
    if not body:
        return False
    return any(body == text_for(lang) for lang in LANGS)


# ---------------------------------------------------------------------------
# The match
# ---------------------------------------------------------------------------

def normalize(message: str) -> str:
    """Lowercase, punctuation dropped (a leading `/` kept), whitespace
    collapsed: "What can you do?!" and "what can you do" are one question."""
    s = (message or "").strip().lower()
    s = s.replace("’", "'")
    s = re.sub(r"[^\w\s/]", " ", s)
    return " ".join(s.split())


def is_intro_request(message: str, *, conversation_empty: bool) -> bool:
    n = normalize(message)
    if n == INTRO_COMMAND:
        return True
    return conversation_empty and n in INTRO_PHRASES


# ---------------------------------------------------------------------------
# The bubble
# ---------------------------------------------------------------------------

def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def bubble(text: str, speaker: str | None = None) -> str:
    """The intro as the chief readvisor's message. The body is the escaped
    markdown source; `data-markdown` asks the chat to render it."""
    who = speaker if speaker is not None else prompt_mod.chief_name()
    return (f'<div class="msg assistant intro" data-markdown="intro">'
            f'<div class="role">{_escape(who)}</div>'
            f'<div class="body">{_escape(text)}</div></div>')


# ---------------------------------------------------------------------------
# The tool
# ---------------------------------------------------------------------------

def _tools():
    from . import tools as _t
    return _t


def run_show_intro(project_dir: Path, call: Any) -> Any:
    """`show_intro` — no arguments. Puts the introduction on screen."""
    text = text_for()
    if not text:
        return _tools().ToolResult("show_intro", "", False, RESULT_MISSING)
    speaker = prompt_mod.chief_name()
    return _tools().ToolResult(
        "show_intro", "", True, RESULT_SHOWN,
        side_effects={SIDE_EFFECT: {"html": bubble(text, speaker), "text": text,
                                    "speaker": speaker}},
    )


def render_tool_result(tool_result: str) -> list[str]:
    """On reload: the intro bubble a `show_intro` result stands for, or
    nothing for any other tool result."""
    body = (tool_result or "").lstrip()
    if not body.startswith('<tool_result name="show_intro"') or RESULT_SHOWN not in body:
        return []
    text = text_for()
    return [bubble(text)] if text else []


_RUNNERS = {"show_intro": run_show_intro}


def register() -> None:
    """Add `show_intro` to `tools._DISPATCH` and `_TRACE_TOGGLE`. Idempotent,
    called once at `tools` import time; traced under the universal toggle."""
    t = _tools()
    for tool_name, runner in _RUNNERS.items():
        t._DISPATCH.setdefault(tool_name, runner)
        t._TRACE_TOGGLE.setdefault(tool_name, "trace_log_enabled")


__all__ = [
    "INTRO_COMMAND", "INTRO_PHRASES", "RESULT_SHOWN", "SIDE_EFFECT", "TOOL_NAMES",
    "bubble", "current_language", "is_intro_request", "is_intro_text", "normalize",
    "path_for", "register", "render_tool_result", "run_show_intro", "set_language_source",
    "text_for",
]
