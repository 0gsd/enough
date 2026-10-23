"""The readvisor's MacroCOSM tools: read a `.cosm` volume, lint it, decompile
a text into its EMF twin, make an atem, and fetch the guide (0.4.3, P6).

Registered into `tools._DISPATCH` the way `dictionary_tools` is. The reading
is `enough.macrocosm`'s (the text tree, the generic checks); the writing is
`enough.canon_derive`'s pure functions, called directly.

**Never a job, never the lock.** A tool runs inside a chat turn, and a chat
turn holds `session.generation_lock` for its whole length. The UI's
derivations go through `CanonJobs`, whose model-mode jobs take that same
lock; a tool that started one would wait for the turn that is waiting for
the tool. So the tools call `derive_emf`/`derive_atem` in the tool's own
worker thread, with a `complete` closure over `llm.complete` at this
session's model (the model is idle between a turn's streams). They still
honour the job table's per-file claims (`CanonJobs.holding`), so a tool and
a derivation the person started never write one twin at once.

**The seams.** A tool runner is handed a project directory and a call and
nothing else, so `configure(llm_url=, jobs=)` is how the server hands over
the session's model URL and its job table, once, in `create_app()` (project
mode). Unconfigured (a test, a script), every derivation runs by rules and
writes a labelled scaffold, exactly as the routes do with no model. The
readvisor's name for `derived.by` is `prompt.chief_name()`: tools run only
in the chief's chat turns (a council strips tool calls).

**The refusals are the routes'.** `text_target()` is the one place that
decides which texts can be decompiled or given an atem (no Holotypes, no
`.cosm`, no catalogs, text kinds only, never overwrite a non-EMF `X.cosm`);
the server's `/api/canon/derive`, `/atem` and `/atem/pin` delegate to it, so
the UI and the tools refuse exactly the same things in the same words.

Gates: reading is always allowed, and so is writing a twin beside a project
text (like the FEED tools, nothing leaves the machine and nothing enters the
system prompt). A write into the Canon store (`canon:` paths) answers to the
`canon_enabled` broker toggle with the existing denial. The documentation
(`prompt.CANON_TOOL_INSTRUCTIONS`, under 1,000 chars) is in every project,
like the FEED tools': the tools are always there. The guide is the shipped
`macrocosm-oes` skill, off by default like every shipped skill (an enabled
skill rides in every turn), and one `cosm_guide` call away when it is off.

**Model mode is for short texts.** A small local model takes a minute or more
per ~1,200 characters, and the chat turn waits: `emf_derive` uses the model
only up to EMF_MODEL_MAX characters and writes the rules scaffold above that,
saying the full pass belongs in the reader's decompile (a background job).
`atem` is one or a few completions, so it keeps the TEXT_MAX limit only.

A write is announced as SSE event `canon` (the UI's job event) through the
result's side effects: a finished-job snapshot in `canon_jobs`' shape, id
`rv<n>`, plus `by`, so open trees and reader chips repaint.

Spec: docs/canon-043-plan.md §9; docs/canon-landed-P6.md.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import itertools
import logging
from pathlib import Path
from typing import Any, Callable, Iterator

log = logging.getLogger("enough.canon_tools")

TOOL_NAMES: tuple[str, ...] = ("cosm_read", "cosm_lint", "emf_derive", "atem", "cosm_guide")

#: The shipped skill whose body `cosm_guide` hands back.
SKILL_NAME = "macrocosm-oes"

#: The SSE event a write emits: the UI's derivation-job event (`canon_jobs.EVENT`).
SIDE_EFFECT = "canon"

#: The virtual prefixes that address the Canon store instead of the project.
#: The same tuple as `server.STORE_PREFIXES` (a test keeps them equal).
STORE_PREFIXES: tuple[str, ...] = ("canon:", "cacheawl:")

#: Over this a text is the reader's work, not a chat turn's: a model reads it
#: passage by passage, a minute or more each, while the turn waits.
TEXT_MAX = 24_000
#: The longest text `emf_derive` gives the model inside a chat turn
#: (gemma-4-E4B: 85–105 s for ~1,200 characters, the orchestrator's measure).
#: Longer texts get the rules scaffold and a pointer to the reader.
EMF_MODEL_MAX = 6_000
EML_MODEL_MAX = EMF_MODEL_MAX     # the name before EMF (plan §16), kept one release
#: The reader's words for that, in the result.
LONG_FOR_A_TURN = ("a full model pass on a text this long belongs in the reader's decompile, which runs in "
                   "the background")

#: What one `cosm_read` may put into the conversation.
TREE_MAX_LINES = 80
TREE_MAX_CHARS = 8_000
ITEM_MAX_CHARS = 6_000
LIST_MAX = 60
#: Lines per section of a lint report, and not-run ids named in its one line.
LINT_SECTION_MAX = 25
NOT_RUN_SHOWN = 12

_SEQ = itertools.count(1)

# The seams (`configure`). Module-level for the reason `pal_tools._active` is:
# a runner gets a project dir and a call, and enough runs one turn at a time.
_llm_url: str | None = None
_jobs: Any = None


def configure(*, llm_url: str | None = None, jobs: Any = None) -> None:
    """Hand the tools this session's model URL and its `CanonJobs` table.
    Called once by `create_app()` in project mode; `configure()` with nothing
    resets both (tests)."""
    global _llm_url, _jobs
    _llm_url = llm_url or None
    _jobs = jobs


def _tools():
    from . import tools as _t
    return _t


def _result(name: str, key: str, ok: bool, body: str, side_effects: dict | None = None) -> Any:
    return _tools().ToolResult(name, key, ok, body, side_effects=side_effects or {})


def _err(name: str, key: str, message: str) -> Any:
    return _result(name, key, False, message if message.startswith("error:") else f"error: {message}")


# ---------------------------------------------------------------------------
# Paths, and the refusals shared with the routes
# ---------------------------------------------------------------------------

class TextTargetError(Exception):
    """A refusal, with the HTTP status the routes answer it with (400, 404, 409)."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def store_prefix(path: str) -> str | None:
    """The Canon prefix `path` starts with, or None for a project path."""
    for prefix in STORE_PREFIXES:
        if path.startswith(prefix):
            return prefix
    return None


def tidy_rel(path: str) -> str:
    """A path tidied the way the routes report it back: project-relative, or
    `canon:`/`cacheawl:` + the path in the store (empty and `.` segments
    dropped, backslashes read as slashes)."""
    path = (path or "").strip()
    prefix = store_prefix(path) or ""
    parts = [p for p in path[len(prefix):].replace("\\", "/").split("/") if p not in ("", ".")]
    return prefix + "/".join(parts)


def resolve(project_dir: Path, path: str) -> Path:
    """Where a route path points, by the routes' rule (`server._resolve_project_path`):
    a `canon:` path into the store, anything else into the project; absolute
    paths and `..` refused ("invalid path"). The final component is not
    resolved, so in-tree symlinks keep their logical place."""
    from . import canon as _canon
    prefix = store_prefix(path)
    if prefix:
        rel = Path(path[len(prefix):].lstrip("/"))
        if rel.is_absolute() or ".." in rel.parts or not rel.parts:
            raise TextTargetError(400, "invalid path")
        return _canon.root().resolve() / rel
    p = Path(path)
    if p.is_absolute() or ".." in p.parts:
        raise TextTargetError(400, "invalid path")
    return project_dir.resolve() / p


def where(rel: str) -> tuple[str | None, str]:
    """`(volume, path in its volume)` for a store path, `(None, rel)` for a
    project path: the catalog to regenerate and the EMF catalog id's path (P0
    decision 16). A file at the store's root has no volume."""
    prefix = store_prefix(rel)
    if not prefix:
        return None, rel
    parts = rel[len(prefix):].split("/")
    return (parts[0], "/".join(parts[1:])) if len(parts) > 1 else (None, parts[0])


def inside_holotype(project_dir: Path, target: Path) -> bool:
    """True when `target` is a Holotype folder or anything inside one, looking
    up no further than the project or the store root."""
    from . import canon as _canon
    stops = {project_dir.resolve(), _canon.root().resolve()}
    p = target if target.is_dir() else target.parent
    for _ in range(64):
        if _canon.is_holotype_folder(p):
            return True
        if p in stops or p.parent == p:
            return False
        p = p.parent
    return False


def text_target(project_dir: Path, path: str) -> dict[str, Any]:
    """Resolve and vet the text a derive, an atem or a pin names (blocking).

    Refusals (`TextTargetError`, with the routes' statuses and words): a
    missing file (404), a folder, a Holotype or anything in one (owner:
    browsed, not decompiled), a catalog or meta enough keeps, any `.cosm`
    (already enumerated), binaries, kinds that aren't markdown or plain text,
    an empty file, and a `X.cosm` beside the text that is not an EMF twin
    (409: deriving would overwrite it). A converted original (`report.pdf`)
    is read through its markdown twin (`report.pdf.md`), or refused with
    "convert it first".

    Returns `{path, target, text_rel, twin, twin_rel, volume, id_rel, key}`:
    the tidied request path, the text read, its path as the routes report it,
    its twin and the twin's path, the Canon volume (None for a project path),
    the catalog id's path, and the claim key (the resolved text)."""
    from . import canon as _canon
    from . import canon_derive as _canon_derive
    from . import convert as _convert
    rel = tidy_rel(path)
    if not rel or rel in STORE_PREFIXES:
        raise TextTargetError(400, "missing path")
    target = resolve(project_dir, rel)
    name = target.name
    if not target.exists():
        raise TextTargetError(404, f"no such file: {rel}")
    if inside_holotype(project_dir, target):
        raise TextTargetError(400, "a Holotype is browsed, not decompiled: open it in the cosm viewer")
    if target.is_dir():
        raise TextTargetError(400, f"{rel} is a folder; derive reads one text at a time")
    if _canon.is_catalog_file(target, project_dir) or name in (
            _canon.CATALOG_NAME, _canon.META_NAME, _canon.LEGACY_META_NAME):
        raise TextTargetError(400, f"{name} is kept by enough; derive reads your texts")
    if name.endswith(".cosm"):
        raise TextTargetError(400, f"{name} is already enumerated (a .cosm file); derive reads texts")
    text_rel = rel
    suffix = target.suffix.lower()
    if suffix not in _canon_derive.TEXT_SUFFIXES and (
            _convert.is_convertible(target) or _canon.looks_binary(target)):
        md = _convert.twin_path(target)
        if md.is_file():
            target, text_rel = md, rel + ".md"
        elif _convert.is_convertible(target):
            raise TextTargetError(400, f"{name} is not a text yet: convert it first, then derive its markdown")
        else:
            raise TextTargetError(400, f"{name} is a binary file; derive reads markdown and plain text")
    elif suffix and suffix not in _canon_derive.TEXT_SUFFIXES:
        raise TextTargetError(400, f"derive reads markdown and plain text, not {suffix} files")
    elif _canon.looks_binary(target):
        raise TextTargetError(400, f"{name} looks binary; derive reads markdown and plain text")
    twin = _canon_derive.twin_path(target)
    if twin.exists() and not _canon.is_emf_twin(twin):
        raise TextTargetError(409, f"{twin.name} already exists and is not an EMF twin; move or rename it first")
    try:
        if not target.read_bytes().strip():
            raise TextTargetError(400, f"{target.name} is empty: there is nothing to derive")
    except OSError as e:
        raise TextTargetError(400, f"{target.name} could not be read ({e})") from None
    volume, id_rel = where(text_rel)
    return {"path": rel, "target": target, "text_rel": text_rel, "twin": twin,
            "twin_rel": text_rel + ".cosm", "volume": volume, "id_rel": id_rel, "key": str(target)}


def catalog_after(project_dir: Path, rel: str) -> None:
    """After a twin is written: the Canon volume's catalog (store paths) or the
    project catalog (project paths), through canon.py's own writers, as the
    routes do. A catalog hiccup is logged; the write already landed."""
    from . import canon as _canon
    volume, _ = where(rel)
    try:
        if store_prefix(rel):
            if volume:
                _canon.require_volume(volume)
                _canon.regenerate_catalog(volume)
        else:
            _canon.project_catalog(project_dir)
    except _canon.CanonError:
        pass
    except Exception:  # noqa: BLE001 — heals at the next reconcile
        log.exception("canon: catalog after a tool write failed")


def _tool_path(project_dir: Path, raw: str | None) -> str:
    """The call's path as the routes take it. Models often echo a file's full
    path; one inside the project is made project-relative. Anything else is
    left for the refusals."""
    raw = (raw or "").strip()
    if not raw or store_prefix(raw):
        return raw
    p = Path(raw).expanduser()
    if p.is_absolute():
        for root in (project_dir, project_dir.resolve()):
            try:
                return p.relative_to(root).as_posix() or "."
            except ValueError:
                continue
    return raw


def _refusal(name: str, raw: str, e: TextTargetError) -> Any:
    msg = str(e)
    if msg == "invalid path":
        msg = f"invalid path {raw!r}: give a project-relative path, or canon:<volume>/<path> for the Canon store"
    return _err(name, raw, msg)


def _store_write_denied(path: str) -> bool:
    from . import broker
    return bool(store_prefix(path)) and not broker.is_enabled("canon_enabled")


# ---------------------------------------------------------------------------
# The model, the readvisor, the claim, the event
# ---------------------------------------------------------------------------

CompleteFn = Callable[[list], tuple]


def model() -> tuple[CompleteFn | None, str]:
    """`(complete, "model")` when this session's model answers, else
    `(None, why)`: rules mode, a labelled scaffold. Decided once per call, like
    the routes; a model that stops answering mid-call fails the call in words
    and nothing is written."""
    from . import llm as _llm
    url = _llm_url
    if not url:
        return None, "no model is wired to the tools here"
    try:
        ok, why = _llm.reachable(url)
    except Exception as e:  # noqa: BLE001
        return None, f"the model could not be asked ({type(e).__name__})"
    if not ok:
        return None, why or "the model is not answering"

    def complete(messages: list) -> tuple:
        try:
            return _llm.complete(messages, llm_url=url)
        except _llm.LLMUnavailable as e:
            raise RuntimeError(f"the model became unavailable ({e}); nothing was written") from e
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"the model stopped answering ({e}); nothing was written") from e

    return complete, "model"


def readvisor_name() -> str:
    """Who asked, for `derived.by`: the chief readvisor (the only speaker whose
    turns run tools)."""
    try:
        from . import prompt as _prompt
        return _prompt.chief_name()
    except Exception:  # noqa: BLE001
        return "readvisor"


@contextlib.contextmanager
def _claim(t: dict[str, Any]) -> Iterator[None]:
    """Hold the text's claim in the job table for the write, so a derivation
    the person started and a tool never write one twin at once."""
    jobs = _jobs
    if jobs is None:
        yield
        return
    with jobs.holding(t["key"], t["text_rel"]):
        yield


def _stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def snapshot(*, kind: str, path: str, mode: str, result: dict, message: str, started: str,
             chunks: int = 1, by: str = "") -> dict[str, Any]:
    """A finished job in `canon_jobs`' snapshot shape (the `canon` event's
    payload), for a write a tool made on the spot."""
    return {"id": f"rv{next(_SEQ)}", "kind": kind, "path": path, "state": "done", "phase": "done",
            "chunk": chunks, "chunks": chunks, "message": message, "mode": mode, "result": result,
            "error": None, "started_at": started, "finished_at": _stamp(), "by": by}


# ---------------------------------------------------------------------------
# Reading volumes
# ---------------------------------------------------------------------------

class _ReadError(Exception):
    pass


def _read_target(project_dir: Path, path: str) -> Path:
    """A path a read names: `canon:` into the store (the routes' rule), a
    project path by `read_file`'s rules (allowlisted absolute paths, shipped
    skills through `rness/`)."""
    if store_prefix(path):
        rel = tidy_rel(path)
        if rel in STORE_PREFIXES:
            raise _ReadError("name a volume: canon:<volume>, or a .cosm file in one")
        try:
            return resolve(project_dir, rel)
        except TextTargetError as e:
            raise _ReadError(f"{e} {path!r}") from None
    try:
        return _tools()._safe_join(project_dir, path, allow_outside_read=True, allow_shipped_read=True)
    except ValueError as e:
        raise _ReadError(str(e)) from None


def load(project_dir: Path, path: str) -> tuple[Any, str]:
    """`(volume, note)` for a `.cosm` file or a volume folder, loaded the way
    the cosm viewer's routes load it: the project catalog and a Canon volume's
    catalog reconciled first; a folder holding `holotype.cosm` as the
    Holotype; a store volume folder by its `canon.cosm`; any other folder by
    the catalog it holds. A text with an EMF twin reads as its twin (`note`
    says so). Raises `_ReadError` in words."""
    from . import canon as _canon
    from . import canon_derive as _canon_derive
    from . import macrocosm as _macrocosm
    target = _read_target(project_dir, path)
    prefix = store_prefix(path)
    if prefix:
        parts = [p for p in tidy_rel(path)[len(prefix):].split("/") if p]
        if parts and (len(parts) == 1 or parts[1:] == [_canon.CATALOG_NAME]):
            try:
                _canon.reconcile(parts[0])
            except _canon.CanonError:
                pass
    else:
        try:
            if target.resolve() == (project_dir / _canon.PROJECT_CATALOG).resolve():
                _canon.project_catalog(project_dir)
        except OSError:
            pass
    if not target.exists():
        raise _ReadError(f"no such file or folder: {path}")
    if target.is_dir():
        cat = target / _canon.CATALOG_NAME
        store_volume = False
        try:
            store_volume = target.resolve().parent == _canon.root().resolve()
        except OSError:
            pass
        if not _canon.is_holotype_folder(target) and store_volume and cat.is_file():
            return _macrocosm.load_volume(cat), ""
        return _macrocosm.load_volume(target), ""
    if target.suffix != ".cosm":
        twin = _canon_derive.twin_path(target)
        if _canon.is_emf_twin(twin):
            return _macrocosm.load_volume(twin), f"(reading {twin.name}, the EMF twin of {target.name})"
        hint = (" It has no EMF twin yet; emf_derive makes one, when the user asks."
                if target.suffix.lower() in _canon_derive.TEXT_SUFFIXES else "")
        raise _ReadError(f"{path} is not a .cosm file or a volume folder.{hint}")
    return _macrocosm.load_volume(target), ""


def declaration_text(vol: Any) -> str:
    """How the volume names its MiniCOSM, in words."""
    d = vol.declaration
    if d is None:
        return vol.oes or "none"
    if d.how == "oes":
        return f"{d.value} (`oes: {d.said or d.value}`)"
    if d.how == "legacy":
        return f"{d.value} (legacy `{d.key}: {d.said}`, read as {d.value})"
    return f"{d.value} (no declaration key: {vol.catalog_file or 'its catalog'} reads as {d.minicosm})"


def _head(vol: Any, report: Any, path: str, note: str) -> list[str]:
    lines = [f"{vol.name} — a {vol.oes} volume ({vol.manifest.title if vol.manifest else vol.oes}) at {path}"]
    if note:
        lines.append(note)
    lines.append(f"declared: {declaration_text(vol)}")
    lines.append(f"{len(vol.items)} items · {len(report.pending)} open questions · "
                 f"{len(report.errors)} errors, {len(report.warnings)} warnings (cosm_lint lists them)")
    return lines


# -- the text tree, capped ---------------------------------------------------

_BRANCHES = ("├── ", "└── ")
_INDENTS = ("│   ", "    ")


def _parse_tree(text: str) -> tuple[str, list]:
    """`macrocosm.to_text_tree` output → `(header, [[label, children], …])`."""
    lines = text.rstrip("\n").split("\n")
    roots: list = []
    stack: list = []
    for ln in lines[1:]:
        i = 0
        while ln[i:i + 4] in _INDENTS:
            i += 4
        if ln[i:i + 4] not in _BRANCHES:
            continue
        depth = min(i // 4, len(stack))
        node = [ln[i + 4:], []]
        if depth == 0:
            roots.append(node)
        else:
            stack[depth - 1][1].append(node)
        del stack[depth:]
        stack.append(node)
    return lines[0], roots


def _size(node: list) -> int:
    return 1 + sum(_size(c) for c in node[1])


def _render(nodes: list, prefix: str, depth: int, cap: int, free: int, out: list[str]) -> None:
    """Draw `nodes` at `depth`: levels above `free` in full, deeper ones `cap`
    siblings at a time, the rest as one "… (N more)" line. A branch whose
    children are all cut says so on its own line instead."""
    keep = nodes if depth < free else nodes[:cap]
    hidden = sum(_size(n) for n in nodes[len(keep):])
    entries = [(n[0], n[1]) for n in keep] + ([(f"… ({hidden} more)", [])] if hidden else [])
    for i, (label, kids) in enumerate(entries):
        last = i == len(entries) - 1
        if kids and cap == 0 and depth + 1 >= free:
            label, kids = f"{label}  … ({sum(_size(k) for k in kids)} more)", []
        out.append(prefix + (_BRANCHES[1] if last else _BRANCHES[0]) + label)
        if kids:
            _render(kids, prefix + (_INDENTS[1] if last else _INDENTS[0]), depth + 1, cap, free, out)


def capped_tree(vol: Any) -> tuple[str, bool]:
    """The volume's text tree, at most TREE_MAX_LINES lines and TREE_MAX_CHARS.
    The structure (parts and modules) is drawn whole while it fits; items
    are cut first: summaries kept, then fewer siblings per branch (each cut
    marked "… (N more)", N counting everything under it too), then no
    summaries; only then are the modules cut too. Returns `(tree, cut)`."""
    from . import macrocosm as _macrocosm
    structure = 2 if vol.parts else 1
    plans = ([(structure, True, c) for c in (12, 8, 5)]
             + [(structure, False, c) for c in (12, 8, 5, 3, 2, 1, 0)])
    if structure > 1:
        plans += [(1, False, c) for c in (3, 2, 1, 0)]
    trees = {s: _macrocosm.to_text_tree(vol, summaries=s) for s in (True, False)}
    out: list[str] = []
    for free, summaries, cap in plans:
        text = trees[summaries]
        header, roots = _parse_tree(text)
        out = [header]
        _render(roots, "", 0, cap, free, out)
        if len(out) <= TREE_MAX_LINES and sum(len(x) + 1 for x in out) <= TREE_MAX_CHARS:
            cut = not summaries or len(out) < len(text.rstrip("\n").split("\n"))
            return "\n".join(out), cut
    kept: list[str] = []
    size = 0
    for ln in out:
        if len(kept) >= TREE_MAX_LINES or size + len(ln) + 1 > TREE_MAX_CHARS:
            kept.append(f"… (the tree goes on: {len(out) - len(kept)} more lines)")
            break
        kept.append(ln)
        size += len(ln) + 1
    return "\n".join(kept), True


def _yaml_text(value: Any, limit: int = ITEM_MAX_CHARS) -> str:
    import yaml
    from . import macrocosm as _macrocosm
    text = yaml.safe_dump(_macrocosm.jsonable(value), sort_keys=False, allow_unicode=True, width=100,
                          default_flow_style=None).rstrip("\n")
    if text.endswith("\n..."):
        text = text[:-4].rstrip("\n")
    if len(text) > limit:
        text = text[:limit].rstrip() + f"\n… (cut: {len(text) - limit:,} more characters)"
    return text


def _item_line(vol: Any, it: Any) -> str:
    from . import macrocosm as _macrocosm
    s = f"{it.name}  [{it.id} · {it.kind}]"
    p = _macrocosm.item_path(vol, it)
    if p and p != it.id:
        s += f"  path {p}"
    summ = it.data.get("summary")
    if isinstance(summ, str) and summ.strip():
        summ = " ".join(summ.split())
        s += "  — " + (summ if len(summ) <= 80 else summ[:79].rstrip() + "…")
    return s


def _item_body(vol: Any, it: Any) -> list[str]:
    from . import macrocosm as _macrocosm
    lines = ["", f"{it.name}  [{it.id} · {it.kind}]"]
    p = _macrocosm.item_path(vol, it)
    if p:
        lines.append(f"path: {p}")
    if it.part:
        lines.append(f"part: {it.part}")
    lines.append(f"file: {it.file}")
    n_open = sum(1 for _ in _macrocosm.walk_pending(it.data))
    if n_open:
        lines.append(f"open questions: {n_open} (pending: nobody has given these yet; never guess them)")
    lines.append("fields:")
    lines.append(_yaml_text(it.data))
    return lines


def _find(vol: Any, ref: str) -> list[str] | str:
    """The lines for `<item>` (an id, a key or a path), or an error sentence."""
    from . import macrocosm as _macrocosm
    it = vol.item(ref)
    if it is not None:
        return _item_body(vol, it)
    hits = [x for x in vol.items.values() if x.id == ref]
    if len(hits) > 1:
        lines = ["", f"{len(hits)} items have the id {ref}; name one by its path:"]
        lines += [f"- {_item_line(vol, x)}  (key {x.key})" for x in hits[:LIST_MAX]]
        return lines
    found = _macrocosm.resolve_path(vol, ref)
    if isinstance(found, tuple):
        owner, value = found
        return ["", f"{ref} (a field of {owner.name}  [{owner.id}])", _yaml_text(value)]
    if found is not None:
        return _item_body(vol, found)
    under = _macrocosm.items_under(vol, ref)
    if under:
        lines = ["", f"{ref}: {len(under)} items"]
        lines += [f"- {_item_line(vol, x)}" for x in under[:LIST_MAX]]
        if len(under) > LIST_MAX:
            lines.append(f"… ({len(under) - LIST_MAX} more)")
        return lines
    return (f"there is no item {ref!r} in {vol.name}. cosm_read without <item> shows the tree and its ids; "
            f"an item's path or a module or kind path works too.")


def run_cosm_read(project_dir: Path, call: Any) -> Any:
    """`cosm_read <path> [<item>]` — the volume's text tree (capped), or one
    item's fields; with the declaration and the open-question count."""
    from . import macrocosm as _macrocosm
    path = (call.path or "").strip()
    if not path:
        return _err("cosm_read", "", "cosm_read needs a <path>: a .cosm file or a volume folder "
                                     "(project-relative, or canon:<volume>).")
    try:
        vol, note = load(project_dir, path)
    except _ReadError as e:
        return _err("cosm_read", path, str(e))
    except Exception as e:  # noqa: BLE001
        log.exception("cosm_read failed")
        return _err("cosm_read", path, f"{path} could not be read ({type(e).__name__}: {e})")
    if vol.refused is not None:
        return _err("cosm_read", path, f"{path} is refused by the reader: {vol.refused}")
    report = _macrocosm.lint(vol)
    lines = _head(vol, report, path, note)
    ref = (call.extra.get("item") or "").strip()
    if ref:
        found = _find(vol, ref)
        if isinstance(found, str):
            return _err("cosm_read", path, found)
        return _result("cosm_read", path, True, "\n".join(lines + found))
    tree, cut = capped_tree(vol)
    lines += ["", tree]
    if cut:
        lines.append("")
        lines.append("cut to fit a chat turn: name what you need with <item> — an id or a path "
                     "(a module or kind path lists its items).")
    return _result("cosm_read", path, True, "\n".join(lines))


# ---------------------------------------------------------------------------
# Linting
# ---------------------------------------------------------------------------

def _section(title: str, rows: list[str]) -> list[str]:
    if not rows:
        return []
    out = [f"{title}:"] + [f"- {r}" for r in rows[:LINT_SECTION_MAX]]
    if len(rows) > LINT_SECTION_MAX:
        out.append(f"… ({len(rows) - LINT_SECTION_MAX} more)")
    return out


def report_lines(vol: Any, report: Any, path: str) -> list[str]:
    """A lint report as plain lines: the count line, errors, warnings, notes,
    open questions, and the checks the MiniCOSM keeps to its own tools."""
    from . import macrocosm as _macrocosm
    e, w, n, q = len(report.errors), len(report.warnings), len(report.notes), len(report.pending)
    lines = [f"{path} — {vol.oes}, {len(vol.items)} items: {e} errors · {w} warnings · {n} notes · "
             f"{q} open questions ({len(report.checks)} checks run)"]
    if report.ok and not (w or n):
        lines.append("clean: every check that ran passed.")
    lines += _section("errors", [str(p) for p in report.errors])
    lines += _section("warnings", [str(p) for p in report.warnings])
    lines += _section("notes", [str(p) for p in report.notes])
    pend = []
    for key, fpath, question in report.pending:
        qv = _macrocosm.jsonable(question)
        pend.append(f"{key}{' · ' + fpath if fpath else ''}: {qv}")
    lines += _section("open questions (pending: nobody has given these yet; never guess them)", pend)
    if report.not_run:
        shown = ", ".join(report.not_run[:NOT_RUN_SHOWN])
        more = f", … ({len(report.not_run) - NOT_RUN_SHOWN} more)" if len(report.not_run) > NOT_RUN_SHOWN else ""
        lines.append(f"not run: {len(report.not_run)} checks the {vol.minicosm} MiniCOSM keeps to its own tools "
                     f"({shown}{more})")
    return lines


def run_cosm_lint(project_dir: Path, call: Any) -> Any:
    """`cosm_lint <path>` — the generic checks' report, as plain lines."""
    from . import macrocosm as _macrocosm
    path = (call.path or "").strip()
    if not path:
        return _err("cosm_lint", "", "cosm_lint needs a <path>: a .cosm file or a volume folder.")
    try:
        vol, note = load(project_dir, path)
    except _ReadError as e:
        return _err("cosm_lint", path, str(e))
    except Exception as e:  # noqa: BLE001
        log.exception("cosm_lint failed")
        return _err("cosm_lint", path, f"{path} could not be read ({type(e).__name__}: {e})")
    if vol.refused is not None:
        return _err("cosm_lint", path, f"{path} is refused by the reader, so nothing was checked: {vol.refused}")
    lines = report_lines(vol, _macrocosm.lint(vol), path)
    if note:
        lines.insert(1, note)
    return _result("cosm_lint", path, True, "\n".join(lines))


# ---------------------------------------------------------------------------
# Writing: the EMF twin and the atem
# ---------------------------------------------------------------------------

def _too_long(name: str, n: int, what: str) -> str:
    return (f"{name} has {n:,} characters (over {TEXT_MAX:,}); that's long for a chat turn — "
            f"use {what} in the reader instead.")


def _part_text(v: Any) -> str:
    if isinstance(v, dict) and isinstance(v.get("pending"), str):
        return f"(open: {v['pending']})"
    return str(v)


def atem_lines(atem: dict) -> list[str]:
    from . import canon_derive as _canon_derive
    block = _canon_derive.atem_block(atem)
    lines = [f"{part}: {_part_text(block[part])}" for part in ("line", "focus", "push", "pull")]
    prof = atem.get("stance_profile") or {}
    if prof:
        lines.append("stances: " + " · ".join(f"{k} {v}" for k, v in prof.items()))
    return lines


def _mode_note(mode: str, model_id: Any, why: str) -> str:
    """The `mode:` line's value: the model's id, or what a scaffold is and why."""
    if mode == "model":
        return f"model ({model_id})" if model_id else "model"
    return f"rules — a scaffold, no model read it ({why})"


def _module_counts(counts: dict) -> str:
    from . import canon_derive as _canon_derive
    from . import macrocosm as _macrocosm
    names: dict[str, str] = {}
    try:
        man = _macrocosm.default_registry().get("emf")
        if man is not None:
            names = {m: str(man.module(m).get("name") or m) for m in man.modules()}
    except Exception:  # noqa: BLE001 — names are a nicety
        pass
    return " · ".join(f"{m} {names.get(m, m)} {counts.get(m, 0)}" for m in _canon_derive.MODULE_ORDER)


def run_emf_derive(project_dir: Path, call: Any) -> Any:
    """`emf_derive <path> [<force>yes</force>]` — decompile a text into its EMF
    twin (`notes.md` → `notes.md.cosm`), by this session's model when it
    answers and the text is at most EMF_MODEL_MAX characters, by rules
    otherwise. Refuses what the reader's decompile refuses, and texts over
    TEXT_MAX."""
    from . import canon as _canon
    from . import canon_derive as _canon_derive
    from . import canon_jobs as _canon_jobs
    raw = (call.path or "").strip()
    if not raw:
        return _err("emf_derive", "", "emf_derive needs the text in a <path> tag (project-relative, or "
                                      "canon:<volume>/<path>).")
    path = _tool_path(project_dir, raw)
    if _store_write_denied(path):
        from . import broker
        return _err("emf_derive", raw, broker.denial_canon_disabled())
    try:
        t = text_target(project_dir, path)
    except TextTargetError as e:
        return _refusal("emf_derive", raw, e)
    started = _stamp()
    try:
        size = len(_canon_derive.read_source(t["target"])[0])
    except OSError as e:
        return _err("emf_derive", raw, f"{t['target'].name} could not be read ({e})")
    if size > TEXT_MAX:
        return _err("emf_derive", raw, _too_long(t["target"].name, size, "decompile"))
    complete, why = model()
    if complete is not None and size > EMF_MODEL_MAX:
        complete, why = None, f"{size:,} characters: {LONG_FOR_A_TURN}"
    mode = "model" if complete is not None else "rules"
    force = (call.extra.get("force") or "").strip().lower() in ("yes", "true", "1")
    if not force and _canon_derive.twin_state(t["target"]) == "fresh":
        derived = _canon.twin_header(t["twin"]).get("derived")
        derived = derived if isinstance(derived, dict) else {}
        if derived.get("completeness") == "full" and (derived.get("mode") == "model" or mode == "rules"):
            return _result("emf_derive", raw, True,
                           f"already fresh: {t['twin_rel']} is up to date with {t['text_rel']} "
                           f"({derived.get('mode') or '?'} mode, by {derived.get('by') or '?'}). Read it with "
                           f"cosm_read; pass <force>yes</force> to derive it again.")
    by = readvisor_name()
    try:
        with _claim(t):
            text, stat = _canon_derive.read_source(t["target"])
            if len(text) > TEXT_MAX:
                return _err("emf_derive", raw, _too_long(t["target"].name, len(text), "decompile"))
            if complete is not None and len(text) > EMF_MODEL_MAX:       # it grew since the first read
                complete, why = None, f"{len(text):,} characters: {LONG_FOR_A_TURN}"
            twin = t["twin"]
            previous = twin.read_text(encoding="utf-8") if _canon.is_emf_twin(twin) else None
            cosm, info = _canon_derive.derive_emf(
                text, source_name=t["target"].name, source_stat=stat, rel_path=t["id_rel"],
                complete=complete, by=by, previous=previous)
            _canon_derive.write_twin(twin, cosm)
    except _canon_jobs.CanonJobError as e:
        return _err("emf_derive", raw, str(e))
    except Exception as e:  # noqa: BLE001 — a model that died, a file that vanished: words, nothing written
        log.warning("emf_derive failed: %s", e)
        return _err("emf_derive", raw, f"the decompile failed: {e}")
    catalog_after(project_dir, t["text_rel"])
    state = _canon_derive.twin_state(t["target"])
    atem = info.get("atem") or {}
    n = info["chunks"]
    lines = [f"ok — wrote {t['twin_rel']}, the EMF twin of {t['text_rel']} ({n} passage{'' if n == 1 else 's'}; "
             f"by {by}).",
             f"mode: {_mode_note(info['mode'], info.get('model'), why)}",
             f"items: {_module_counts(info.get('counts') or {})} — {info['items']} in all"
             + (f", {info['dropped']} dropped (failed the checks)" if info.get("dropped") else "")]
    if info["mode"] == "rules":
        lines.append("a scaffold holds terms and names only; concepts, claims and events need a model.")
    lines.append(f"atem: {_part_text(atem.get('line'))}")
    lines.append(f"read it with cosm_read on {t['twin_rel']}.")
    message = f"wrote {twin.name}" + (" (a scaffold: no model read it)" if info["mode"] == "rules" else "")
    result = {"twin_path": t["twin_rel"], "text_path": t["text_rel"], "mode": info["mode"],
              "model": info.get("model"), "chunks": info["chunks"], "items": info["items"],
              "counts": info.get("counts") or {}, "dropped": info.get("dropped", 0), "atem": atem,
              "state": state}
    snap = snapshot(kind="emf", path=t["text_rel"], mode=info["mode"], result=result, message=message,
                    started=started, chunks=info["chunks"], by=by)
    return _result("emf_derive", raw, True, "\n".join(lines), {SIDE_EFFECT: snap})


def run_atem(project_dir: Path, call: Any) -> Any:
    """`atem <path>` — the file's atem, written into its twin's `atem:` block
    (a minimal twin when there is none). `atem <text>` — the atem of a passage
    given inline, written nowhere (with a `<path>` too, that file is its
    context)."""
    from . import canon as _canon
    from . import canon_derive as _canon_derive
    from . import canon_jobs as _canon_jobs
    raw = (call.path or "").strip()
    inline = (call.extra.get("text") or "").strip()
    if not raw and not inline:
        return _err("atem", "", "atem needs a <path> (a text file) or a <text> (the passage itself).")
    path = _tool_path(project_dir, raw)
    complete, why = model()

    if inline:
        if len(inline) > TEXT_MAX:
            return _err("atem", raw, _too_long("that passage", len(inline), "atem"))
        context = None
        if path:
            try:
                t = text_target(project_dir, path)
                whole, _stat = _canon_derive.read_source(t["target"])
                context = f"a passage of {_canon_derive.text_title(whole, t['target'].name)}"
            except TextTargetError as e:
                return _refusal("atem", raw, e)
        try:
            atem = _canon_derive.derive_atem(inline, context=context, complete=complete)
        except Exception as e:  # noqa: BLE001
            return _err("atem", raw, f"the atem failed: {e}")
        lines = atem_lines(atem) + [f"mode: {_mode_note(atem['mode'], atem.get('model'), why)}",
                                    "written: nowhere (an atem of a passage given inline)"]
        return _result("atem", raw or "text", True, "\n".join(lines))

    if _store_write_denied(path):
        from . import broker
        return _err("atem", raw, broker.denial_canon_disabled())
    try:
        t = text_target(project_dir, path)
    except TextTargetError as e:
        return _refusal("atem", raw, e)
    started = _stamp()
    by = readvisor_name()
    try:
        with _claim(t):
            text, stat = _canon_derive.read_source(t["target"])
            if len(text) > TEXT_MAX:
                return _err("atem", raw, _too_long(t["target"].name, len(text), "atem"))
            title = _canon_derive.text_title(text, t["target"].name)
            atem = _canon_derive.derive_atem(text, context=f"the whole of {title}", complete=complete)
            twin = t["twin"]
            existing = twin.read_text(encoding="utf-8") if _canon.is_emf_twin(twin) else None
            cosm = _canon_derive.set_file_atem(
                existing, atem, source_name=t["target"].name, source_stat=stat, rel_path=t["id_rel"],
                by=by, model=atem.get("model"), title=title)
            _canon_derive.write_twin(twin, cosm)
    except _canon_jobs.CanonJobError as e:
        return _err("atem", raw, str(e))
    except Exception as e:  # noqa: BLE001
        log.warning("atem failed: %s", e)
        return _err("atem", raw, f"the atem failed: {e}")
    catalog_after(project_dir, t["text_rel"])
    if existing is None:
        where_ = f"into {t['twin_rel']}, a new minimal twin (completeness: atem, no items yet), by {by}"
    else:
        where_ = f"into {t['twin_rel']} (its atem: block; the twin's items are kept), by {by}"
    lines = atem_lines(atem) + [f"mode: {_mode_note(atem['mode'], atem.get('model'), why)}",
                                f"written: {where_}"]
    block = _canon_derive.atem_block(atem)
    result = {"twin_path": t["twin_rel"], "text_path": t["text_rel"], "mode": atem["mode"],
              "model": atem.get("model"), "atem": block, "stance_profile": atem.get("stance_profile") or {},
              "written": True, "state": _canon_derive.twin_state(t["target"])}
    snap = snapshot(kind="atem", path=t["text_rel"], mode=atem["mode"], result=result,
                    message=f"wrote the atem into {twin.name}", started=started, by=by)
    return _result("atem", raw, True, "\n".join(lines), {SIDE_EFFECT: snap})


# ---------------------------------------------------------------------------
# The guide
# ---------------------------------------------------------------------------

def guide_text() -> str | None:
    """The shipped `macrocosm-oes` SKILL.md, front matter and tooltip line
    dropped. Always the install's copy, never a project's: a project-local
    folder of that name would be an unaudited skill."""
    from . import prompt as _prompt
    from . import skeleton as _skeleton
    path = _skeleton._install_defaults_root() / "skills" / SKILL_NAME / "SKILL.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    _meta, body = _prompt._parse_paradigm_frontmatter(text)
    lines = [ln for ln in body.strip().splitlines() if not ln.startswith("enough-tooltip-text:")]
    while lines and lines[-1].strip() in ("", "---"):
        lines.pop()
    return "\n".join(lines).strip() or None


def run_cosm_guide(project_dir: Path, call: Any) -> Any:
    """`cosm_guide` — no tags. The macrocosm-oes guide: what MacroCOSM is, the
    MiniCOSMs, the stances, the atem, when to decompile, how to read a
    Holotype, and the tools in order."""
    text = guide_text()
    if not text:
        return _err("cosm_guide", "", "this install has no macrocosm-oes guide. Read and lint before you "
                                      "derive, decompile only when the user asks, and never guess an open "
                                      "question.")
    return _result("cosm_guide", "", True, text)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_RUNNERS = {
    "cosm_read": run_cosm_read,
    "cosm_lint": run_cosm_lint,
    "emf_derive": run_emf_derive,
    "atem": run_atem,
    "cosm_guide": run_cosm_guide,
}


def register() -> None:
    """Add the five tools to `tools._DISPATCH` and `_TRACE_TOGGLE`. Idempotent,
    called once at `tools` import time; traced under the universal toggle,
    like every other tool that writes something of the user's."""
    t = _tools()
    for tool_name, runner in _RUNNERS.items():
        t._DISPATCH.setdefault(tool_name, runner)
        t._TRACE_TOGGLE.setdefault(tool_name, "trace_log_enabled")


__all__ = ["EMF_MODEL_MAX", "LONG_FOR_A_TURN", "SIDE_EFFECT", "SKILL_NAME", "STORE_PREFIXES", "TEXT_MAX",
           "TOOL_NAMES", "TextTargetError", "atem_lines", "capped_tree", "catalog_after", "configure",
           "declaration_text", "guide_text", "inside_holotype", "load", "model", "readvisor_name", "register",
           "report_lines", "resolve", "run_atem", "run_cosm_guide", "run_cosm_lint", "run_cosm_read",
           "run_emf_derive", "snapshot", "store_prefix", "text_target", "tidy_rel", "where"]
