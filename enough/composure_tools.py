"""The readvisor's composure tools, registered into `tools._DISPATCH`.

Nine tools, all of them thin: they parse the XML inner tags a small local
model can reliably emit, hand the work to `enough/composure.py`'s node-level
ops, and render the result as a sentence. Every refusal the readvisor sees
is a `ComposureError` message from the core, so the model, the canvas and
the user are all reading the same words.

Two rules the tools enforce that the UI does not:

- the `composure_enabled` broker toggle gates all eight (the canvas itself
  is ungated, exactly like wikisink and cacheawl); and
- `comp_remove_module` needs `<confirmed>yes</confirmed>`, meaning the user
  said so in their own words this turn. Never pre-fill it.

Registration is one import-time call — `register()` at the bottom, invoked
from `tools.py`'s import of this module — so there is no second dispatch
table to keep in step.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from . import broker
from . import composure as comp_core
from .composure import ComposureError

log = logging.getLogger("enough.composure")

TOOL_NAMES: tuple[str, ...] = (
    "read_composure", "new_composure", "comp_add_module", "comp_update_module",
    "comp_set_page", "comp_remove_module", "comp_arrange", "comp_save_as_form",
    "composure_from_outline",
)

#: Past this many characters a `read_composure` body is cached under
#: `rness/io/input/` and the tool returns a preview + the path — the same
#: deal `read_wiki_article` and `fetch_url` offer, for the same reason.
CACHE_OVER_CHARS = 4000
PREVIEW_CHARS = 1200


# ---------------------------------------------------------------------------
# Plumbing
# ---------------------------------------------------------------------------

def _tools():
    from . import tools as _t
    return _t


def _denied(name: str) -> Any:
    return _tools().ToolResult(name, "", False, broker.denial_composure_disabled())


def _err(name: str, key: str, message: str) -> Any:
    return _tools().ToolResult(name, key, False, message)


def _ok(name: str, key: str, body: str) -> Any:
    return _tools().ToolResult(name, key, True, body)


def _resolve(project_dir: Path, rel: str) -> Path:
    """Project-contained `.comp` path. Uses `tools._safe_join`, so the
    traversal rules are the same ones every other tool obeys."""
    if not rel:
        raise ComposureError(
            "this tool needs a <path> to a .comp file, e.g. "
            "rness/io/composure/plan-2026-09-17.comp")
    if not rel.endswith(comp_core.SUFFIX):
        raise ComposureError(
            f"{rel!r} is not a composure — composure paths end in "
            f"{comp_core.SUFFIX}. Use read_file for ordinary documents.")
    try:
        return _tools()._safe_join(project_dir, rel)
    except ValueError as e:
        raise ComposureError(f"error: {e}") from None


def _field(call: Any, name: str) -> str:
    return (call.extra.get(name) or "").strip()


def _apply(project_dir: Path, rel: str, ops: list[dict[str, Any]], *,
           create: bool = False, form: str = "blank",
           title: str = "") -> comp_core.OpsResult:
    target = _resolve(project_dir, rel)
    return comp_core.apply_ops(
        target, None, ops, source="readvisor", create=create, form=form,
        title=title, project_dir=project_dir, rel_path=rel,
    )


def _emit(result: comp_core.OpsResult) -> dict[str, Any]:
    """The side effect that puts an op batch from a readvisor onto the same
    SSE channel the canvas already listens to. `tools.ToolResult.side_effects`
    is fanned out by `server._handle_tool` after the result is recorded."""
    return {comp_core.EVENT: {
        "path": result.path,
        "rev": result.rev,
        "changed": result.changed,
        "source": "readvisor",
        "created": result.created,
    }}


def _module_fields(call: Any) -> dict[str, Any]:
    """The inner tags `comp_add_module` and `comp_update_module` share.
    Only tags actually present become op keys, so an update is a patch."""
    out: dict[str, Any] = {}
    for tag in ("title", "bg", "scale", "x", "y", "w", "h", "z", "href",
                "url", "article", "install", "refresh", "near"):
        value = _field(call, tag)
        if value:
            out[tag] = value
    for numeric in ("scale", "x", "y", "w", "h", "z"):
        if numeric in out:
            try:
                out[numeric] = float(out[numeric])
            except ValueError:
                raise ComposureError(
                    f"<{numeric}> must be a number (got {out[numeric]!r})."
                ) from None
    if _field(call, "fullport").lower() in ("1", "true", "yes"):
        out["fullport"] = True
    return out


# ---------------------------------------------------------------------------
# read_composure
# ---------------------------------------------------------------------------

def run_read_composure(project_dir: Path, call: Any) -> Any:
    """`<path>` alone → the outline. Add `<module>` (and optionally
    `<page>`) → that module's full text as markdown."""
    name = "read_composure"
    if not broker.is_enabled("composure_enabled"):
        return _denied(name)
    rel = (call.path or "").strip()
    try:
        target = _resolve(project_dir, rel)
        comp = comp_core.load(target)
    except ComposureError as e:
        return _err(name, rel, str(e))
    module = _field(call, "module")
    if not module:
        return _ok(name, rel, comp_core.outline(comp, rel))
    page_raw = _field(call, "page")
    try:
        page = int(page_raw) if page_raw else None
    except ValueError:
        return _err(name, rel, f"<page> must be a number (got {page_raw!r}).")
    try:
        body = comp_core.page_markdown(comp, module, page)
    except ComposureError as e:
        return _err(name, rel, str(e))
    if len(body) <= CACHE_OVER_CHARS:
        return _ok(name, rel, body)
    cache_rel = _cache_long_read(project_dir, comp, rel, module, body)
    preview = body[:PREVIEW_CHARS]
    return _ok(name, rel, (
        f"{preview}\n… (+{len(body) - PREVIEW_CHARS} chars)\n\n"
        f"full text cached at: {cache_rel} — read_file it if you need the rest."
    ))


def _cache_long_read(project_dir: Path, comp: comp_core.Composure, rel: str,
                     module: str, body: str) -> str:
    """Long module text lands under `rness/io/input/` instead of the context
    window — the same rule `read_wiki_article` follows."""
    import datetime as dt
    stamp = dt.datetime.now().strftime("%Y-%m-%d-%H%M")
    slug = comp_core.slugify(f"{comp.title}-{module}")
    filename = f"{stamp}-comp-{slug}.md"
    dest = project_dir / "rness" / "io" / "input" / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(f"# {comp.title} — {module}\n\nfrom {rel}\n\n{body}",
                    encoding="utf-8")
    return f"rness/io/input/{filename}"


# ---------------------------------------------------------------------------
# new_composure
# ---------------------------------------------------------------------------

def run_new_composure(project_dir: Path, call: Any) -> Any:
    """`<form>` + `<title>` → a real file. Unlike the canvas's lazy
    create, a readvisor asking for a composure means it is about to put
    something in it, so the file is written immediately and the path comes
    back for the follow-up ops."""
    name = "new_composure"
    if not broker.is_enabled("composure_enabled"):
        return _denied(name)
    form = _field(call, "form") or "blank"
    title = _field(call, "title") or (call.content or "").strip()
    if not title:
        return _err(name, form,
                    "new_composure needs a <title> — it names the file and "
                    "the canvas heading.")
    try:
        comp = comp_core.new_composure(form, title, project_dir)
        rel = comp_core.new_path(project_dir, comp.title)
        target = _resolve(project_dir, rel)
        with comp_core.path_lock(target):
            comp_core.save(target, comp)
    except ComposureError as e:
        return _err(name, form, str(e))
    result = comp_core.OpsResult(path=rel, rev=0, changed=[], stale=False,
                                 stale_changed=[], created=True, composure=comp)
    out = _ok(name, rel, (
        f"ok — created {rel} from the {comp.form} form.\n\n"
        f"{comp_core.outline(comp, rel)}"
    ))
    out.side_effects = _emit(result)
    return out


# ---------------------------------------------------------------------------
# module ops
# ---------------------------------------------------------------------------

def run_comp_add_module(project_dir: Path, call: Any) -> Any:
    """`<path>` `<type>` [`<title>` `<bg>` `<x>`/`<y>`/`<w>`/`<h>` …] plus
    `<content>` as markdown. Geometry is optional: leave it out and the
    server places the module in a free slot."""
    name = "comp_add_module"
    if not broker.is_enabled("composure_enabled"):
        return _denied(name)
    rel = (call.path or "").strip()
    mtype = _field(call, "type") or "text"
    try:
        op: dict[str, Any] = {"op": "add_module", "type": mtype,
                              **_module_fields(call)}
        body = call.content
        if body:
            op["markdown"] = body.lstrip("\n")
        result = _apply(project_dir, rel, [op])
    except ComposureError as e:
        return _err(name, rel, str(e))
    mid = result.changed[0] if result.changed else "?"
    out = _ok(name, rel, (
        f"ok — added {mtype} module {mid} to {rel} (rev {result.rev}). "
        f"Use that id in comp_set_page / comp_update_module."
    ))
    out.side_effects = _emit(result)
    return out


def run_comp_update_module(project_dir: Path, call: Any) -> Any:
    """Patch a module's geometry, background, scale, title, z or type
    fields. Never its text — that is `comp_set_page`."""
    name = "comp_update_module"
    if not broker.is_enabled("composure_enabled"):
        return _denied(name)
    rel = (call.path or "").strip()
    module = _field(call, "module") or _field(call, "id")
    if not module:
        return _err(name, rel, "comp_update_module needs a <module> id "
                               "(read_composure lists them).")
    try:
        fields = _module_fields(call)
        mtype = _field(call, "type")
        if mtype:
            fields["type"] = mtype
        if not fields:
            return _err(name, rel,
                        "comp_update_module needs at least one field to "
                        "change: title, bg, scale, x, y, w, h, z, type, href, "
                        "url, article, refresh.")
        result = _apply(project_dir, rel,
                        [{"op": "update_module", "id": module, **fields}])
    except ComposureError as e:
        return _err(name, rel, str(e))
    out = _ok(name, rel, f"ok — updated module {module} in {rel} "
                         f"(rev {result.rev}): {', '.join(sorted(fields))}.")
    out.side_effects = _emit(result)
    return out


def run_comp_set_page(project_dir: Path, call: Any) -> Any:
    """Replace one page's text with `<content>` (markdown). `<page>`
    defaults to 1; `<append>true</append>` adds a new page instead."""
    name = "comp_set_page"
    if not broker.is_enabled("composure_enabled"):
        return _denied(name)
    rel = (call.path or "").strip()
    module = _field(call, "module") or _field(call, "id")
    if not module:
        return _err(name, rel, "comp_set_page needs a <module> id.")
    if call.content is None:
        return _err(name, rel, "comp_set_page needs <content> (markdown).")
    markdown = call.content.lstrip("\n")
    append = _field(call, "append").lower() in ("1", "true", "yes")
    page_raw = _field(call, "page")
    try:
        page = int(page_raw) if page_raw else 1
    except ValueError:
        return _err(name, rel, f"<page> must be a number (got {page_raw!r}).")
    op = ({"op": "add_page", "module": module, "markdown": markdown}
          if append else
          {"op": "set_page", "module": module, "n": page, "markdown": markdown})
    try:
        result = _apply(project_dir, rel, [op])
    except ComposureError as e:
        return _err(name, rel, str(e))
    what = "added a page to" if append else f"rewrote page {page} of"
    out = _ok(name, rel, f"ok — {what} module {module} in {rel} "
                         f"(rev {result.rev}, {len(markdown)} chars in).")
    out.side_effects = _emit(result)
    return out


def run_comp_remove_module(project_dir: Path, call: Any) -> Any:
    """Remove a module. Requires the user's explicit confirmation this
    turn — a canvas the readvisor can silently empty is not a canvas the
    user can trust."""
    name = "comp_remove_module"
    if not broker.is_enabled("composure_enabled"):
        return _denied(name)
    rel = (call.path or "").strip()
    module = _field(call, "module") or _field(call, "id")
    if not module:
        return _err(name, rel, "comp_remove_module needs a <module> id.")
    if _field(call, "confirmed").lower() not in ("yes", "y", "true"):
        return _err(name, rel, (
            f"error: removing module {module} needs the user's explicit "
            f"confirmation. Ask them, and only after they say so add "
            f"<confirmed>yes</confirmed> to the call. Never pre-fill it."
        ))
    try:
        result = _apply(project_dir, rel,
                        [{"op": "remove_module", "id": module}])
    except ComposureError as e:
        return _err(name, rel, str(e))
    out = _ok(name, rel, f"ok — removed module {module} from {rel} "
                         f"(rev {result.rev}).")
    out.side_effects = _emit(result)
    return out


def run_comp_arrange(project_dir: Path, call: Any) -> Any:
    """Lay a named list of modules out as a grid or a single column. The
    order you pass is the order they end up in."""
    name = "comp_arrange"
    if not broker.is_enabled("composure_enabled"):
        return _denied(name)
    rel = (call.path or "").strip()
    raw = _field(call, "modules") or _field(call, "ids") or (call.content or "")
    ids = [i for i in raw.replace(",", " ").split() if i]
    if not ids:
        return _err(name, rel, "comp_arrange needs <modules> — a space- or "
                               "comma-separated list of module ids.")
    op: dict[str, Any] = {"op": "arrange", "ids": ids,
                          "mode": _field(call, "mode") or "grid"}
    cols = _field(call, "cols")
    if cols:
        try:
            op["cols"] = int(cols)
        except ValueError:
            return _err(name, rel, f"<cols> must be a number (got {cols!r}).")
    try:
        result = _apply(project_dir, rel, [op])
    except ComposureError as e:
        return _err(name, rel, str(e))
    out = _ok(name, rel, f"ok — arranged {len(ids)} module(s) in {rel} as a "
                         f"{op['mode']} (rev {result.rev}).")
    out.side_effects = _emit(result)
    return out


def run_comp_save_as_form(project_dir: Path, call: Any) -> Any:
    """Save a composure as a reusable project form."""
    name = "comp_save_as_form"
    if not broker.is_enabled("composure_enabled"):
        return _denied(name)
    rel = (call.path or "").strip()
    form_name = _field(call, "name") or _field(call, "form")
    if not form_name:
        return _err(name, rel, "comp_save_as_form needs a <name> for the form.")
    try:
        target = _resolve(project_dir, rel)
        comp = comp_core.load(target)
        dest = comp_core.save_as_form(project_dir, comp, form_name)
    except ComposureError as e:
        return _err(name, rel, str(e))
    return _ok(name, rel, (
        f"ok — saved {rel} as the project form {dest.stem!r}. "
        f"new_composure can use it by that name from now on."
    ))


# ---------------------------------------------------------------------------
# composure_from_outline (P5b)
# ---------------------------------------------------------------------------

def run_composure_from_outline(project_dir: Path, call: Any) -> Any:
    """`<title>` `<form>` + a markdown outline in `<content>` → a whole
    composure, laid out, in one call.

    Why this exists: a small local model asked for fourteen module tool calls
    in a row produces nine, two in the wrong group and one a duplicate. Asked
    for one markdown outline it does fine. So the structure is written as
    markdown and converted deterministically — the `scaffold` skill teaches
    the grammar, and this tool is the only thing that parses it."""
    name = "composure_from_outline"
    if not broker.is_enabled("composure_enabled"):
        return _denied(name)
    title = _field(call, "title")
    form = (_field(call, "form") or "scaffold").lower()
    body = (call.content or "").lstrip("\n")
    if not body.strip():
        return _err(name, title, (
            "composure_from_outline needs the outline in <content>: one '# ' "
            "title line, a '## ' per group, and a '### ' (or a top-level list "
            "item) per card."))
    if form not in comp_core.OUTLINE_FORMS:
        return _err(name, form, (
            f"unknown outline form {form!r}. forms: "
            f"{', '.join(comp_core.OUTLINE_FORMS)} — scaffold puts each group "
            f"in a column, cards puts each group in a row, blank makes one "
            f"full page."))
    try:
        doc = comp_core.parse_outline(body)
        if title:
            doc.title = title
        if not doc.title:
            return _err(name, "", (
                "that outline has no title. Put one in <title>, or start the "
                "content with a '# ' line."))
        comp = comp_core.new_composure(form, doc.title, project_dir)
        ops = comp_core.outline_ops(
            doc, form, clear_ids=[m.id for m in comp.modules])
        rel = comp_core.new_path(project_dir, doc.title)
        result = comp_core.apply_ops(
            _resolve(project_dir, rel), None, ops, source="readvisor",
            create=True, form=form, title=doc.title,
            project_dir=project_dir, rel_path=rel)
    except ComposureError as e:
        return _err(name, title or form, str(e))
    cards = sum(1 for m in result.composure.modules if m.bg != "gray")
    gaps = [m for m in result.composure.modules if m.bg == comp_core.GAP_BG]
    note = (f" {len(gaps)} gap card(s): "
            + ", ".join(comp_core.first_line(m.pages[0].rich, 60)
                        for m in gaps) if gaps else "")
    out = _ok(name, rel, (
        f"ok — made {rel} from the outline: {len(doc.groups)} group(s), "
        f"{cards} card(s), {len(result.composure.modules)} modules in all."
        f"{note}\n\n{comp_core.outline(result.composure, rel)}"
    ))
    out.side_effects = _emit(result)
    return out


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_RUNNERS = {
    "read_composure": run_read_composure,
    "new_composure": run_new_composure,
    "comp_add_module": run_comp_add_module,
    "comp_update_module": run_comp_update_module,
    "comp_set_page": run_comp_set_page,
    "comp_remove_module": run_comp_remove_module,
    "comp_arrange": run_comp_arrange,
    "comp_save_as_form": run_comp_save_as_form,
    "composure_from_outline": run_composure_from_outline,
}


def register() -> None:
    """Add the nine tools to `tools._DISPATCH` and `_TRACE_TOGGLE`.

    Idempotent, and called once at `tools` import time. They trace under
    the universal `trace_log_enabled` toggle like the girraph ops: a
    node-level edit to a shared canvas is exactly what the broker journal
    exists to reconstruct."""
    t = _tools()
    for tool_name, runner in _RUNNERS.items():
        t._DISPATCH.setdefault(tool_name, runner)
        t._TRACE_TOGGLE.setdefault(tool_name, "trace_log_enabled")


__all__ = ["register", "TOOL_NAMES", *sorted(_RUNNERS)]
