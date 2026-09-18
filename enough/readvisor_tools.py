"""`install_readvisor` — the door the `readvisory` skill files through.

One tool, registered into `tools._DISPATCH` the same way the composure
tools are, because growing `tools.py` by a page every time a subsystem
arrives is how a dispatch table stops being readable.

What makes this tool different from `write_file` (which could, after all,
write two markdown files) is that it is a **door**, and doors check things:

- the name is a folder name on the user's disk forever, so it is validated
  like one, and a shipped readvisor's name cannot be taken by accident;
- both documents must have the canonical shape (`prompt.readvisor_shape`),
  because "all readvisors work in roughly the same way" is a promise the
  install door is the only place able to keep;
- both documents are run through the same deterministic payload scanner
  skillaudit uses on an untrusted skill, because a readvisor's AGENT.md is
  read straight into the system prompt of every later turn. A readvisor
  forged from a third party's questionnaire answers is, in the most literal
  sense, text from outside that the model will follow.

The install is otherwise deliberately dull: two files and a folder, in one
of exactly two places.

    project → <project>/rness/readvisors/<name>/   (a real dir, on here)
    global  → ~/enough/readvisors/<name>/          (symlinked everywhere)

A global install lands in the user's own home rather than the install's
`defaults/`, because on a desktop build `defaults/` is inside the sealed
.app bundle and is not writable. See `skeleton.user_readvisors_root`.
"""

from __future__ import annotations

import logging
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from . import broker
from . import prompt as prompt_mod
from . import skeleton

log = logging.getLogger("enough.readvisors")

TOOL_NAMES: tuple[str, ...] = ("install_readvisor",)

#: A folder name on disk, and a name the user will type at their readvisor.
_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
NAME_MAX = 40

#: Each document is prose. 40 KB is several times the longest shipped one,
#: and small enough that a runaway generation is refused rather than filed.
DOC_MAX_BYTES = 40_000


# ---------------------------------------------------------------------------
# Plumbing
# ---------------------------------------------------------------------------

def _tools():
    from . import tools as _t
    return _t


def _field(call: Any, name: str) -> str:
    return (getattr(call, "extra", None) or {}).get(name, "").strip()


def _err(key: str, message: str) -> Any:
    return _tools().ToolResult("install_readvisor", key, False, message)


def _ok(key: str, message: str, side_effects: dict[str, Any]) -> Any:
    return _tools().ToolResult("install_readvisor", key, True, message,
                               side_effects=side_effects)


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------

def shipped_names() -> set[str]:
    """Names that ship with enough. Reserved: a user readvisor called
    `block-breaker` would be shadowed by the shipped one in some projects
    and not others depending on install order, which is exactly the kind of
    "it works on my other machine" that costs an afternoon."""
    root = skeleton.shipped_readvisors_root(skeleton._install_defaults_root())
    if not root.is_dir():
        return set()
    try:
        return {e.name for e in root.iterdir()
                if e.is_dir() and not e.name.startswith(".")}
    except OSError:
        return set()


def scan_documents(project_dir: Path, agent_md: str, motivation_md: str) -> dict[str, Any]:
    """Run the bundled deterministic payload scanner over the two documents.

    The scanner takes a directory, so the documents are written to a throwaway
    one under the OS temp dir — never inside the project, because a scan that
    leaves its own input lying around in `rness/` is a scan that will one day
    be read back as a readvisor.

    Returns the scanner's own dict (`findings` / `verdict` / …), or
    `{"error": …}` when no scanner could be loaded."""
    from . import skillaudit
    with tempfile.TemporaryDirectory(prefix="enough-readvisor-scan-") as tmp:
        target = Path(tmp)
        (target / "AGENT.md").write_text(agent_md, encoding="utf-8")
        (target / "MOTIVATION.md").write_text(motivation_md, encoding="utf-8")
        return skillaudit.run_payload_scan(project_dir, target)


def _quote_findings(scan: dict[str, Any], limit: int = 5) -> str:
    """The refusal's evidence. The readvisor is told what was found and
    where, not merely that something was: it has to be able to tell the user
    which paragraph to look at, and a respondent's honest answer that merely
    resembles a pattern should be fixable in one edit."""
    findings = scan.get("findings") or []
    lines: list[str] = []
    for f in findings[:limit]:
        where = f.get("file") or "?"
        line_no = f.get("line")
        loc = f"{where}:{line_no}" if line_no else where
        text = (f.get("text") or "").strip()
        why = (f.get("explanation") or "").strip()
        lines.append(f"  - [{f.get('pattern', '?')} "
                     f"{f.get('confidence', '?')}] {loc}: {text}")
        if why:
            lines.append(f"    {why}")
    if len(findings) > limit:
        lines.append(f"  - … and {len(findings) - limit} more")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# The tool
# ---------------------------------------------------------------------------

def run_install_readvisor(project_dir: Path, call: Any) -> Any:
    """`install_readvisor <name> <scope> <agent_md> <motivation_md> [display]`

    Every refusal is phrased so the readvisor can act on it without asking
    the user to read an error message."""
    name = (_field(call, "name") or (call.path or "") or "").strip()
    scope = (_field(call, "scope") or "project").strip().lower()
    agent_md = (call.extra or {}).get("agent_md", "") or ""
    motivation_md = (call.extra or {}).get("motivation_md", "") or ""
    replace = _field(call, "replace").lower() in ("yes", "true", "1")

    if not broker.is_enabled("readvisory_install"):
        return _err(name, broker.denial_readvisory_install_disabled())

    # --- the name -----------------------------------------------------
    if not name:
        return _err("", "install_readvisor needs a <name> — the kebab-case "
                        "folder name for the readvisor, e.g. "
                        "<name>hard-questions</name>.")
    if len(name) > NAME_MAX or not _NAME_RE.match(name):
        return _err(name, (
            f"error: {name!r} is not a usable readvisor name. Use lowercase "
            f"letters, digits and single hyphens, at most {NAME_MAX} "
            f"characters — it becomes a folder on the user's disk."))
    if scope not in ("project", "global"):
        return _err(name, "error: <scope> must be `project` (this project "
                          "only) or `global` (every project on this machine). "
                          "Ask the user which they want.")

    shipped = shipped_names()
    if name in shipped:
        return _err(name, (
            f"error: {name!r} is a readvisor that ships with enough, so that "
            f"name is taken. Pick another one — the display name can still be "
            f"whatever the user likes."))

    # --- the documents ------------------------------------------------
    for label, text in (("<agent_md>", agent_md), ("<motivation_md>", motivation_md)):
        if not text.strip():
            return _err(name, f"error: {label} is empty. A readvisor is its "
                              f"two documents; both have to be written before "
                              f"it can be installed.")
        if len(text.encode("utf-8")) > DOC_MAX_BYTES:
            return _err(name, (
                f"error: {label} is over {DOC_MAX_BYTES // 1000} KB. That is "
                f"far longer than any shipped readvisor — tighten it, or the "
                f"user pays for the excess in every single turn."))

    problems = prompt_mod.readvisor_shape(agent_md, motivation_md)
    if problems:
        return _err(name, (
            "error: the two documents don't have the readvisor shape yet:\n"
            + "\n".join(f"  - {p}" for p in problems)
            + "\n\nThe shape is in the readvisory skill's "
              "`assets/AGENT.md.template` and `assets/MOTIVATION.md.template`. "
              "Every readvisor works roughly the same way, however different "
              "they sound."))

    scan = scan_documents(project_dir, agent_md, motivation_md)
    if "error" not in scan and skillaudit_floor(scan) != "pass":
        return _err(name, (
            "error: refused — the deterministic scanner found something in "
            "these documents that a system prompt should not carry:\n"
            + _quote_findings(scan)
            + "\n\nThis text goes into the system prompt of every later turn, "
              "so anything that reads as an instruction to the machine rather "
              "than a description of a person has to come out first. Show the "
              "user the finding and rewrite that passage."))

    # --- the folder ---------------------------------------------------
    if scope == "global":
        root = skeleton.user_readvisors_root()
        where = "~/enough/readvisors/"
    else:
        root = prompt_mod._readvisors_dir(project_dir / "rness")
        where = f"{root.name}/"
    dest = root / name

    if dest.is_symlink():
        # A link, i.e. a readvisor that lives somewhere else and is merely
        # visible here. Writing through it would edit the original for every
        # project at once, which is never what "install into this project"
        # meant.
        return _err(name, (
            f"error: {name!r} already names a readvisor that lives elsewhere "
            f"and is only linked into this project. Pick another name."))
    if dest.exists() and not replace:
        return _err(name, (
            f"error: a readvisor named {name!r} already exists at "
            f"{where}{name}/. Installing over it would discard what is "
            f"there. Ask the user whether to replace it, and if they say so, "
            f"call again with <replace>yes</replace>."))

    try:
        root.mkdir(parents=True, exist_ok=True)
        staging = dest.with_name(f".{name}.installing")
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True)
        (staging / "AGENT.md").write_text(agent_md.strip() + "\n", encoding="utf-8")
        (staging / "MOTIVATION.md").write_text(motivation_md.strip() + "\n",
                                               encoding="utf-8")
        # Swap last, so a crash mid-write never leaves half a readvisor
        # where the loader will find it.
        if dest.is_symlink():
            dest.unlink()
        elif dest.is_dir():
            shutil.rmtree(dest)
        staging.rename(dest)
    except OSError as e:
        return _err(name, f"error: could not write {where}{name}/: {e}")

    # A global install has to be linked into THIS project before the user
    # can switch it on here; elsewhere it arrives default-off on next launch,
    # like every other new global.
    if scope == "global":
        try:
            defaults = skeleton._install_defaults_root()
            skeleton._populate_role_symlinks(project_dir, defaults)
        except OSError:
            log.warning("could not link the new global readvisor into %s",
                        project_dir, exc_info=True)

    enable(project_dir, name)
    display = _field(call, "display") or prompt_mod._display_name(agent_md, name)
    scope_note = (
        "every project on this machine — switched on here, and switched off "
        "in the others until the user says otherwise"
        if scope == "global" else "this project"
    )
    return _ok(name, (
        f"ok — installed {display} as {name!r} in {where}{name}/ and switched "
        f"it on. It is available to {scope_note}. Tell the user it will join "
        f"the conversation from the next message, and that they can switch it "
        f"off any time in the readvisors list in the sidebar."
    ), {"readvisors_changed": {"name": name, "scope": scope, "action": "install"}})


def enable(project_dir: Path, name: str) -> None:
    """Switch a readvisor on in this project, tolerating a read-only
    `.disabled` — the folder is already written, and a failure to toggle is
    a thing the user can fix with one click."""
    try:
        prompt_mod.set_role_enabled(project_dir / "rness", name, True)
    except OSError:
        log.warning("could not enable readvisor %s in %s", name, project_dir,
                    exc_info=True)


def skillaudit_floor(scan: dict[str, Any]) -> str:
    """`skillaudit.scan_floor`, reached lazily so importing this module does
    not drag the audit machinery in.

    Note that the install door treats `flag` and `fail` alike, unlike a skill
    audit, which escalates a `flag` to the model for a second opinion. A
    skill is code with a job to do and its findings need judging; a readvisor
    is prose about a person, and prose about a person has no legitimate
    reason to look like an exfiltration pattern."""
    from . import skillaudit
    return skillaudit.scan_floor(scan)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_RUNNERS = {"install_readvisor": run_install_readvisor}


def register() -> None:
    """Add the tool to `tools._DISPATCH` and `_TRACE_TOGGLE`. Idempotent,
    and called once at `tools` import time. It traces under the universal
    `trace_log_enabled` toggle: writing a new voice into the user's system
    prompt is precisely the kind of thing the broker journal exists to
    reconstruct afterwards."""
    t = _tools()
    for tool_name, runner in _RUNNERS.items():
        t._DISPATCH.setdefault(tool_name, runner)
        t._TRACE_TOGGLE.setdefault(tool_name, "trace_log_enabled")


__all__ = ["register", "TOOL_NAMES", "run_install_readvisor", "scan_documents",
           "shipped_names"]
