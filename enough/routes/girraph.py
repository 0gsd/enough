"""The girraph panel's node operations (`/api/girraph*`).

Moved out of `enough/server.py`'s `create_app` in 0.8 (lane W2-SV), code unchanged: `build_router` is the old
factory's closure for this group, and the names it closed over come in on `ctx`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from .. import broker as _broker
from .common import AppContext


def build_router(ctx: AppContext) -> APIRouter:
    router = APIRouter()
    _resolve_project_path = ctx._resolve_project_path
    project_dir = ctx.project_dir

    # ---------- Girraph (plain-text IBIS map) node ops ----------
    #
    # The editable girraph panel calls these. Both this API and the
    # agent's girraph tools go through `enough.girraph`'s node-level ops
    # under the same per-path lock — that's the whole concurrency story
    # for simultaneous user-panel and agent edits (last-write-wins at
    # node granularity). Every mutation is journaled via broker.trace so
    # panel edits show up alongside tool calls in the session log.
    from .. import girraph as _girraph

    def _girraph_path(path: str) -> Path:
        target = _resolve_project_path(path)
        if not path.endswith(".girraph"):
            raise HTTPException(400, "not a .girraph path")
        return target

    def _merirmaid_echo(path: str) -> str:
        """The sibling `.merirmaid` path in the SAME scheme the request used —
        so a `canon:`-prefixed girraph answers with a
        mirror in the same prefix, and an in-tree girraph with an in-tree
        mirror."""
        if path.endswith(".girraph"):
            return path[: -len(".girraph")] + ".merirmaid"
        return path

    def _girraph_node_json(g: "_girraph.Girraph", n: "_girraph.Node") -> dict[str, Any]:
        ref_kind = ""
        ref_broken = False
        if n.ref:
            ref_kind = "girraph" if n.ref.endswith(".girraph") else "doc"
            ref_broken = not (project_dir / n.ref).exists()
        return {
            "id": n.id,
            "type": n.type,
            "sigil": n.sigil,
            "emoji": n.emoji,
            "label": n.label,
            "parent": n.parent,
            "cross": n.cross,
            "ref": n.ref,
            "ref_kind": ref_kind,
            "ref_broken": ref_broken,
            "by": n.by,
            "detail": n.detail,
        }

    def _girraph_tree_json(path: str, g: "_girraph.Girraph") -> dict[str, Any]:
        return {
            "path": path,
            "title": g.title,
            "warnings": g.warnings,
            "roots": [n.id for n in g.roots()],
            "nodes": [
                _girraph_node_json(g, g.nodes[v])
                for k, v in g.order if k == "node" and v in g.nodes
            ],
        }

    @router.get("/api/girraph")
    async def api_girraph_get(path: str = Query(...)) -> dict[str, Any]:
        target = _girraph_path(path)
        try:
            g = _girraph.load(target)
        except _girraph.GirraphError as e:
            raise HTTPException(404, str(e)) from None
        out = _girraph_tree_json(path, g)
        # The linked-mirror state, so the frontend's add/open-merirmaid
        # button needs no extra round trip. Echoed in the request's own path
        # scheme (canon: prefix preserved).
        out["merirmaid"] = _merirmaid_echo(path) if _girraph.has_mirror(target) else None
        return out

    @router.post("/api/girraph/node")
    async def api_girraph_add_node(request: Request) -> dict[str, Any]:
        form = await request.form()
        path = (form.get("path") or "").strip()
        target = _girraph_path(path)
        label = (form.get("label") or "").strip()
        parent = (form.get("parent") or "").strip() or None
        with _girraph.path_lock(target):
            if target.is_file():
                g = _girraph.load(target)
            elif parent:
                raise HTTPException(404, "girraph does not exist yet")
            else:
                g = _girraph.new_girraph(label)
            try:
                node = _girraph.add_node(
                    g,
                    type=(form.get("type") or "").strip(),
                    label=label,
                    parent=parent,
                    ref=(form.get("ref") or "").strip() or None,
                    by=(form.get("by") or "").strip() or None,
                    detail=form.get("detail") or "",
                )
            except _girraph.GirraphError as e:
                raise HTTPException(400, str(e)) from None
            _girraph.save(target, g)
        _broker.trace(
            project_dir, tool="girraph", decision="add node (panel)",
            args={"path": path, "id": node.id, "label": node.label[:60]},
            result_ok=True, result_summary=f"added {node.id}",
        )
        return {"path": path, "node": _girraph_node_json(g, node)}

    @router.patch("/api/girraph/node")
    async def api_girraph_update_node(request: Request) -> dict[str, Any]:
        form = await request.form()
        path = (form.get("path") or "").strip()
        node_id = (form.get("id") or "").strip()
        if not node_id:
            raise HTTPException(400, "missing id")
        target = _girraph_path(path)
        # Field absent from the form ⇒ untouched; present-but-empty ⇒ clear.
        patch = {
            f: form.get(f)
            for f in ("label", "detail", "ref", "by", "parent")
            if f in form
        }
        if not patch:
            raise HTTPException(400, "no updatable fields supplied")
        with _girraph.path_lock(target):
            try:
                g = _girraph.load(target)
                node = _girraph.update_node(g, node_id, **patch)
            except _girraph.GirraphError as e:
                raise HTTPException(400, str(e)) from None
            _girraph.save(target, g)
        _broker.trace(
            project_dir, tool="girraph", decision="update node (panel)",
            args={"path": path, "id": node_id, "fields": ",".join(sorted(patch))},
            result_ok=True, result_summary=f"patched {node_id}",
        )
        return {"path": path, "node": _girraph_node_json(g, node)}

    @router.delete("/api/girraph/node")
    async def api_girraph_remove_node(
        path: str = Query(...),
        id: str = Query(...),
        cascade: bool = Query(False),
    ) -> dict[str, Any]:
        # The panel's delete button shows its own are-you-sure dialog —
        # a user-initiated DELETE is the confirmation, mirroring how
        # "mark done" works for requests.
        target = _girraph_path(path)
        with _girraph.path_lock(target):
            try:
                g = _girraph.load(target)
                removed = _girraph.remove_node(g, id, cascade=cascade)
            except _girraph.GirraphError as e:
                raise HTTPException(400, str(e)) from None
            _girraph.save(target, g)
        _broker.trace(
            project_dir, tool="girraph", decision="remove node (panel)",
            args={"path": path, "id": id, "cascade": cascade},
            result_ok=True, result_summary=f"removed {', '.join(removed)}",
        )
        return {"path": path, "removed": removed}

    @router.post("/api/girraph/link")
    async def api_girraph_link(request: Request) -> dict[str, Any]:
        form = await request.form()
        path = (form.get("path") or "").strip()
        from_id = (form.get("from") or "").strip()
        to_id = (form.get("to") or "").strip()
        remove = (form.get("remove") or "").strip().lower() in ("true", "1", "yes")
        if not from_id or not to_id:
            raise HTTPException(400, "missing from/to")
        target = _girraph_path(path)
        with _girraph.path_lock(target):
            try:
                g = _girraph.load(target)
                if remove:
                    _girraph.unlink_nodes(g, from_id, to_id)
                else:
                    _girraph.link_nodes(g, from_id, to_id)
            except _girraph.GirraphError as e:
                raise HTTPException(400, str(e)) from None
            _girraph.save(target, g)
        verb = "unlink" if remove else "link"
        _broker.trace(
            project_dir, tool="girraph", decision=f"{verb} (panel)",
            args={"path": path, "from": from_id, "to": to_id},
            result_ok=True, result_summary=f"{verb}ed {from_id} -> {to_id}",
        )
        return {"path": path, "from": from_id, "to": to_id, "removed": remove}

    @router.post("/api/girraph/merirmaid")
    async def api_girraph_merirmaid(request: Request) -> dict[str, Any]:
        """Create (or idempotently regenerate) the sibling `.merirmaid` mirror
        for a girraph. 404 if the girraph is missing/unparsable; 409 if a
        `.merirmaid` already claims the sibling name but is NOT a
        girraph-mirror (a hand-authored diagram — we won't clobber it). When
        the sibling already IS a girraph-mirror this just regenerates it.
        Returns ``{"merirmaid": "<sibling path in the request's scheme>"}``."""
        body = await request.json()
        path = (body.get("path") or "").strip() if isinstance(body, dict) else ""
        target = _girraph_path(path)
        with _girraph.path_lock(target):
            try:
                _girraph.load(target)
            except _girraph.GirraphError as e:
                raise HTTPException(404, str(e)) from None
            mp = _girraph.mirror_path(target)
            if mp.exists() and not _girraph.has_mirror(target):
                raise HTTPException(
                    409,
                    f"{mp.name} already exists and is not a girraph mirror "
                    f"(modality/kind mismatch) — rename or remove it first.",
                )
            _girraph.create_mirror(target, path)
        _broker.trace(
            project_dir, tool="girraph", decision="create merirmaid (panel)",
            args={"path": path}, result_ok=True,
            result_summary=f"mirror for {path}",
        )
        return {"merirmaid": _merirmaid_echo(path)}

    @router.get("/api/girraph/ref-candidates")
    async def api_girraph_ref_candidates(name: str = Query(...)) -> dict[str, Any]:
        """Repair helper for broken refs: same-basename matches anywhere
        in the project (skipping dotdirs), in the spirit of the broker
        index. The panel offers these as one-click re-points."""
        base = Path(name).name
        if not base:
            raise HTTPException(400, "missing name")
        hits: list[str] = []
        root = project_dir.resolve()
        for p in root.rglob(base):
            if any(part.startswith(".") for part in p.relative_to(root).parts):
                continue
            hits.append(str(p.relative_to(root)))
            if len(hits) >= 20:
                break
        return {"name": base, "candidates": sorted(hits)}

    return router
