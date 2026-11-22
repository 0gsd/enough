"""The scaffolder in enough: a plectrum to composure ops, a composure back to a state.

The plectrum's grammar and the scaffold's one-file state belong to the cross-harness skill
(`defaults/skills/scaffolder/references/plectrum.md`, `state.md`), and so does their only reader and
writer, `scripts/scaffold_state.py`. enough loads that file from its own `defaults/` (the bundled
copy, never a project's), the way `skillaudit` loads the analyzer's scanner, so there is one parser
and no copy to drift.

What lives where:

- the composure is the truth for layout and for the person's text. A frame is a `frame` module, a
  plecholder a `scaffold-box`; their module ids come from the plectrum's ids (`module_id`), so a
  changed plectrum finds the boxes it made without a lookup table;
- the plectrum is kept beside the composure as `<name>.plectrum.md` (`plectrum_path`). It carries
  what a composure has no field for: the front matter past the title and the thing, a box's
  `fixed`, `chips` and `place`, a frame's `copy-of`. A box's `as` is on the composure (0.9,
  `data-as`), so a change the person makes to it is saved, undone and exported like any field;
  a box made before 0.9 has none, and its `as` still comes from the plectrum.

`plectrum_ops` is the pure half of the `scaffold_from_plectrum` tool, as `outline_ops` is for
`composure_from_outline`. It never writes a box's text: the composure refuses a readvisor's text
anyway, and these ops never carry any. A plec the person has edited is theirs, and stays.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from . import composure as C

STATE_SCRIPT = (Path(__file__).resolve().parent.parent / "defaults" / "skills" / "scaffolder"
                / "scripts" / "scaffold_state.py")
PLECTRUM_SUFFIX = ".plectrum.md"
BOX_GAP = C.GRID
TEXT_BOX_H = C.BASE_SIZE[C.BOX][1]

_state: ModuleType | None = None


def state_module() -> ModuleType:
    """The skill's `scaffold_state.py`, loaded once from this install's own `defaults/`."""
    global _state
    if _state is None:
        name = "_enough_scaffold_state"
        spec = importlib.util.spec_from_file_location(name, STATE_SCRIPT)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load the scaffolder's state reader at {STATE_SCRIPT}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod  # its dataclass looks itself up here
        spec.loader.exec_module(mod)
        _state = mod
    return _state


def loads(text: str):
    """A plectrum or a state, read by the skill's own reader (raises its `StateError`)."""
    return state_module().loads(text)


def module_id(scaffold_id: str) -> str:
    """The composure module id of a plectrum id: `m` and 15 hex digits of its SHA-1. Stable, so
    an id that never changes in the plectrum never changes on the canvas either."""
    return "m" + hashlib.sha1(scaffold_id.encode("utf-8")).hexdigest()[:15]


def plectrum_path(comp_path: Path) -> Path:
    """`…/garden-2026-11-18.comp` → `…/garden-2026-11-18.plectrum.md`."""
    return comp_path.with_name(comp_path.name[: -len(C.SUFFIX)] + PLECTRUM_SUFFIX)


def frame_shape(shape: str) -> str:
    """The plectrum's three frame shapes on a composure's two: a letter is a page."""
    return "slide" if shape == "slide" else "page"


def composure_target(target: str | None) -> str:
    """`0` (no target) is the composure's empty target."""
    return "" if not target or target == "0" else target


def _has_text(m: C.Module) -> bool:
    return any(C.rich_to_md(p.rich).strip() for p in m.pages)


def _box_height(box: dict[str, Any], width: float) -> float:
    """A text box one card tall; a graphic as tall as its proportion asks, at most square."""
    if box["kind"] != "graphic":
        return TEXT_BOX_H
    shape = box.get("shape") or "16:9"
    ratio = {"portrait": 4 / 3, "landscape": 3 / 4, "square": 1.0}.get(shape)
    if ratio is None:
        w, h = (float(x) for x in shape.split(":"))
        ratio = h / w
    return round(max(TEXT_BOX_H / 2, min(width * ratio, width)), 2)


# ---------------------------------------------------------------------------
# A plectrum → composure ops
# ---------------------------------------------------------------------------

@dataclass
class Plan:
    """The ops that bring a composure to a plectrum, and what they do, for the tool's report."""
    ops: list[dict[str, Any]] = field(default_factory=list)
    added_frames: list[str] = field(default_factory=list)
    added_boxes: list[str] = field(default_factory=list)
    changed_boxes: list[str] = field(default_factory=list)
    moved_boxes: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    kept_words: list[str] = field(default_factory=list)
    kept_plecs: list[str] = field(default_factory=list)
    kept_frames: list[str] = field(default_factory=list)


def plectrum_ops(model: Any, comp: C.Composure, *, mid: Callable[[str], str] = module_id,
                  person: bool = False) -> Plan:
    """The ops that make `comp` (a scaffold: the `scaffold` form fresh, or one built before) hold
    the plectrum `model`: frames added, retitled, reshaped and put in order; boxes added, moved to
    another frame, retargeted, re-kinded and re-plecced; empty boxes the plectrum dropped removed.

    Never touched: a box's text (no op here carries any), a box that holds the person's words but
    left the plectrum (kept, and reported), a plec the person edited (kept, and reported). Frames
    are laid out in order, a deck's side by side and a page's or a document's one under another;
    a frame's boxes travel with it.

    `mid` maps a plectrum id to its module id (`module_id`; bringing a state in maps an id that is
    already a module id on `comp` to itself). `person` is the person's own state coming in: a plec
    they set is replaced by the state's, since both are theirs."""
    if C.scaffold_view(comp) is None:
        raise C.ComposureError(
            "this composure is not a scaffold. A new one is made from the scaffold form; an "
            "older composure becomes one only by the person's \"make this a scaffold\".")
    plan = Plan()
    meta = model.meta
    thing = meta["thing"]
    deck = thing == "deck"
    view = C.scaffold_view(comp) or {}
    if view.get("thing") != thing:
        plan.ops.append({"op": "set_scaffold", "thing": thing})
    if comp.title != meta["title"]:
        plan.ops.append({"op": "set_meta", "title": meta["title"]})

    mods = {m.id: m for m in comp.modules}
    geo = {m.id: [m.x, m.y, m.w, m.h] for m in comp.modules}
    want_frames = [(f, mid(f["id"])) for f in model.frames]
    want_boxes = {mid(b["id"]): (b, mid(f["id"]))
                  for f in model.frames for b in f["boxes"]}
    want_frame_ids = {fm for _, fm in want_frames}

    # Boxes the plectrum no longer holds: removed when empty, kept with the person's words.
    staying_loose: dict[str, list[str]] = {}
    for m in comp.modules:
        if m.type != C.BOX or m.id in want_boxes:
            continue
        if _has_text(m):
            plan.kept_words.append(m.title or m.id)
            staying_loose.setdefault(m.frame, []).append(m.id)
        else:
            plan.ops.append({"op": "remove_module", "id": m.id})
            plan.removed.append(m.title or m.id)
            geo.pop(m.id, None)

    old_order = C.frame_order(comp)
    kept_old = [fid for fid in old_order if fid not in want_frame_ids and staying_loose.get(fid)]
    final = [fm for _, fm in want_frames] + kept_old
    plan.kept_frames = [mods[fid].title or fid for fid in kept_old]
    anchor = (geo[old_order[0]][0], geo[old_order[0]][1]) if old_order else (0.0, 0.0)
    cursor_x, cursor_y = anchor

    frame_ops: list[dict[str, Any]] = []
    move_ops: list[dict[str, Any]] = []
    box_ops: list[dict[str, Any]] = []
    for fid in final:
        pf = next((f for f, fm in want_frames if fm == fid), None)
        existing = mods.get(fid)
        shape = frame_shape(pf.get("shape") or meta["shape"]) if pf else (existing.shape or "page")
        w, h = C.FRAME_SHAPES[shape]
        if existing is not None and existing.shape == shape:
            w, h = existing.w, max(h, existing.h) if shape == "page" else existing.h
        x, y = cursor_x, cursor_y
        # The boxes that stay on this frame travel with it.
        staying = [b.id for b in comp.modules if b.type == C.BOX and b.frame == fid
                   and b.id in geo and (b.id not in want_boxes or want_boxes[b.id][1] == fid)]
        if existing is not None:
            dx, dy = x - existing.x, y - existing.y
            patch: dict[str, Any] = {}
            if dx or dy:
                patch.update(x=round(x, 2), y=round(y, 2))
                for bid in staying:
                    geo[bid][0] += dx
                    geo[bid][1] += dy
                    move_ops.append({"op": "update_module", "id": bid,
                                     "x": round(geo[bid][0], 2), "y": round(geo[bid][1], 2)})
            if pf and existing.title != pf["name"]:
                patch["title"] = pf["name"]
            if existing.shape != shape:
                patch.update(shape=shape, w=w, h=h)
            geo[fid] = [x, y, w, h]
        else:
            geo[fid] = [x, y, w, h]
        incoming = [b for b in (pf["boxes"] if pf else [])
                    if mid(b["id"]) not in staying]
        new_h = _lay_out(plan, box_ops, geo, fid, shape, incoming, staying, mods,
                         fresh=existing is None, mid=mid, person=person)
        if new_h > h:
            h = geo[fid][3] = new_h
        if existing is None:
            plan.added_frames.append(pf["name"])
            frame_ops.append({"op": "add_frame", "id": fid, "shape": shape,
                              "title": pf["name"], "x": round(x, 2), "y": round(y, 2)})
            if h != C.FRAME_SHAPES[shape][1]:
                frame_ops.append({"op": "update_module", "id": fid, "h": round(h, 2)})
        else:
            if h != existing.h and "h" not in patch:
                patch["h"] = round(h, 2)
            if patch:
                frame_ops.append({"op": "update_module", "id": fid, **patch})
        # Fields of the boxes that stay put.
        for bid in staying:
            if bid in want_boxes:
                _patch_box(plan, box_ops, mods[bid], want_boxes[bid][0], person=person)
        if deck:
            cursor_x = x + w + C.GUTTER
        else:
            cursor_y = y + h + C.GUTTER

    # A frame the plectrum dropped goes first when nothing is on it (the form's empty page, so a
    # plectrum near the module cap still fits), else once its boxes have moved off.
    on_frame = {m.frame for m in comp.modules if m.type == C.BOX and m.id in geo}
    drop_now = [fid for fid in old_order if fid not in final and fid not in on_frame]
    drop_later = [fid for fid in old_order if fid not in final and fid in on_frame]
    plan.ops += [{"op": "remove_module", "id": fid} for fid in drop_now]
    plan.ops += frame_ops + move_ops + box_ops
    plan.ops += [{"op": "remove_module", "id": fid} for fid in drop_later]
    plan.removed += [mods[fid].title or fid for fid in drop_now + drop_later]
    added = [op["id"] for op in frame_ops if op["op"] == "add_frame"]
    if final != [fid for fid in old_order if fid in final] + added:
        plan.ops.append({"op": "reorder_frames", "order": final})
    return plan


def _lay_out(plan: Plan, box_ops: list[dict[str, Any]], geo: dict[str, list[float]], fid: str,
             shape: str, incoming: list[dict[str, Any]], staying: list[str],
             mods: dict[str, C.Module], *, fresh: bool,
             mid: Callable[[str], str] = module_id, person: bool = False) -> float:
    """Place the boxes coming onto frame `fid`, and return the height the frame needs.

    A fresh frame is laid out from the plectrum: its rows top to bottom, a row's boxes side by
    side in column order, a `place` box where its percentages say. On a frame that already holds
    boxes, a newcomer goes under the lowest of them, the frame's inner width wide."""
    fx, fy, fw, fh = geo[fid]
    pad = C.FRAME_PAD
    inner_w = fw - 2 * pad
    placed: dict[str, tuple[float, float, float, float]] = {}
    if fresh:
        rows: dict[int, list[dict[str, Any]]] = {}
        for b in incoming:
            if b.get("place"):
                left, top, width, height = (float(v) for v in b["place"].split())
                placed[b["id"]] = (fx + fw * left / 100, fy + fh * top / 100,
                                   max(1.0, fw * width / 100), max(1.0, fh * height / 100))
            else:
                rows.setdefault(b["row"], []).append(b)
        heights: list[float] = []
        for r in sorted(rows):
            row = sorted(rows[r], key=lambda b: b["col"])
            bw = (inner_w - BOX_GAP * (len(row) - 1)) / len(row)
            heights.append(max(_box_height(b, bw) for b in row))
        scale = 1.0
        if shape == "slide" and heights:
            room = fh - 2 * pad - BOX_GAP * (len(heights) - 1)
            scale = min(1.0, room / sum(heights)) if sum(heights) > 0 else 1.0
        y = fy + pad
        for r, rh in zip(sorted(rows), heights):
            row = sorted(rows[r], key=lambda b: b["col"])
            bw = (inner_w - BOX_GAP * (len(row) - 1)) / len(row)
            x = fx + pad
            for b in row:
                bh = _box_height(b, bw) * scale
                placed[b["id"]] = (x, y, bw, max(1.0, bh))
                x += bw + BOX_GAP
            y += rh * scale + BOX_GAP
    else:
        bottom = max((geo[b][1] + geo[b][3] for b in staying if b in geo), default=fy)
        y = max(fy + pad, bottom + BOX_GAP) if staying else fy + pad
        for b in incoming:
            bh = _box_height(b, inner_w)
            placed[b["id"]] = (fx + pad, y, inner_w, bh)
            y += bh + BOX_GAP
    for b in incoming:
        bid = mid(b["id"])
        x, y, w, h = (round(v, 2) for v in placed[b["id"]])
        geo[bid] = [x, y, w, h]
        if bid in mods:
            box_ops.append({"op": "move_to_frame", "id": bid, "frame": fid, "x": x, "y": y})
            box_ops.append({"op": "update_module", "id": bid, "w": w, "h": h})
            plan.moved_boxes.append(b["name"])
            _patch_box(plan, box_ops, mods[bid], b, person=person)
        else:
            op: dict[str, Any] = {"op": "add_module", "type": C.BOX, "id": bid, "frame": fid,
                                  "title": b["name"], "kind": b["kind"], "as": b["as"],
                                  "plec": b["plec"],
                                  "target": composure_target(b["target"]) if b["kind"] == "text"
                                  else "", "x": x, "y": y, "w": w, "h": h}
            if b["kind"] == "graphic":
                op["shape"] = b["shape"] or "16:9"
            box_ops.append(op)
            plan.added_boxes.append(b["name"])
    lows = [geo[k][1] + geo[k][3] for k in list(staying) + [mid(b["id"]) for b in incoming]
            if k in geo]
    need = (max(lows) + pad - fy) if lows else 0.0
    return need if shape == "page" else 0.0


def _patch_box(plan: Plan, box_ops: list[dict[str, Any]], m: C.Module, b: dict[str, Any], *,
               person: bool = False) -> None:
    """Title, kind, `as`, shape, target and plec, where the plectrum differs. A plec the person
    set is theirs: it is kept, and the report says so."""
    patch: dict[str, Any] = {}
    if m.title != b["name"]:
        patch["title"] = b["name"]
    if (m.as_ or "body") != (b["as"] or "body"):
        patch["as"] = b["as"]
    shape = (b["shape"] or "16:9") if b["kind"] == "graphic" else ""
    if (m.kind or "text") != b["kind"]:
        patch["kind"] = b["kind"]
    if (m.shape or "") != shape:
        patch["shape"] = shape
    target = composure_target(b["target"]) if b["kind"] == "text" else ""
    if (m.target or "") != target:
        patch["target"] = target
    if m.plec != b["plec"]:
        if m.plec_by == "person" and not person:
            plan.kept_plecs.append(b["name"])
        else:
            patch["plec"] = b["plec"]
    if patch:
        box_ops.append({"op": "update_module", "id": m.id, **patch})
        if b["name"] not in plan.changed_boxes:
            plan.changed_boxes.append(b["name"])


# ---------------------------------------------------------------------------
# A composure → the state
# ---------------------------------------------------------------------------

def _rows(boxes: list[C.Module]) -> dict[str, tuple[int, int]]:
    """Row and column of each box from where it sits: a box whose top is above the middle of the
    row's shortest box joins that row; a row's boxes count from the left."""
    rows: list[list[C.Module]] = []
    for m in sorted(boxes, key=lambda m: (m.y, m.x, m.id)):
        if rows and m.y < rows[-1][0].y + min(b.h for b in rows[-1]) / 2:
            rows[-1].append(m)
        else:
            rows.append([m])
    out: dict[str, tuple[int, int]] = {}
    for r, row in enumerate(rows, start=1):
        for c, m in enumerate(sorted(row, key=lambda m: (m.x, m.id)), start=1):
            out[m.id] = (r, c)
    return out


def state_from_composure(comp: C.Composure, plectrum: Any | None = None,
                         comments: dict[str, Any] | None = None) -> Any:
    """The scaffold's one-file state from a composure, with what the composure has no field for
    taken from the plectrum beside it. Frames in order, each frame's boxes by row and column, the
    person's text as markdown, their `written` marks, the version and the lock. A box no frame
    holds, and a frame with no box, are left out and named in `warnings`.

    `comments` is the composure's sidecar (`C.load_comments`): its findings become the state's
    `# Findings` (each about the state's id for its box), and its last check's time `checked`. A
    finding about a box the state leaves out is named in `warnings`."""
    S = state_module()
    view = C.scaffold_view(comp)
    if view is None:
        raise C.ComposureError("this composure is not a scaffold, so it has no scaffold state.")
    pframes = {module_id(f["id"]): f for f in plectrum.frames} if plectrum else {}
    pboxes = {module_id(b["id"]): b for b in plectrum.boxes()} if plectrum else {}
    base = dict(plectrum.meta) if plectrum else {
        "for": "(not said)", "writes": "(not said)", "next": None, "lang": comp.lang or "en",
        "aim": "thing", "extra": {}}
    thing = view["thing"]
    meta = {**base, "title": comp.title, "thing": thing}
    meta.setdefault("shape", S.default_shape(thing))
    meta.setdefault("unit", S.default_unit(thing))
    meta["version"] = view["version"]
    meta["parent"] = view["version"] - 1 if view["version"] > 1 else None
    locked = (view.get("locked") or {}).get("at")
    meta["locked"] = locked if locked and S.is_stamp(locked) else None
    stamp = (comments or {}).get("check") if isinstance((comments or {}).get("check"), dict) else None
    checked = stamp.get("at") if stamp else base.get("checked")
    meta["checked"] = checked if checked and S.is_stamp(str(checked)) else None
    meta["extra"] = dict(base.get("extra") or {})
    model = S.Scaffold(kind="scaffold", meta=meta)
    state_ids: dict[str, str] = {}
    for i, fid in enumerate(view["frames"], start=1):
        fm = comp.module(fid)
        pf = pframes.get(fid)
        held = [comp.module(b) for b in view["boxes"].get(fid, [])]
        held = [m for m in held if m is not None]
        if fm is None or not held:
            model.warnings.append(f"frame {fid} holds no box and is left out of the state.")
            continue
        own_shape = pf.get("shape") if pf else None
        if frame_shape(own_shape or meta["shape"]) != (fm.shape or "page"):
            own_shape = fm.shape or None
        frame = {"id": pf["id"] if pf else fid, "name": fm.title or (pf["name"] if pf else f"Frame {i}"),
                 "shape": own_shape, "copy_of": pf.get("copy_of") if pf else None,
                 "copy": pf.get("copy") if pf else None,
                 "extra": dict(pf.get("extra") or {}) if pf else {}, "boxes": []}
        places = _rows(held)
        for m in sorted(held, key=lambda m: places[m.id]):
            pb = pboxes.get(m.id) or {}
            state_ids[m.id] = pb.get("id") or m.id
            kind = m.kind or "text"
            row, col = places[m.id]
            page = m.pages[0].rich if m.pages else ""
            frame["boxes"].append({
                "id": pb.get("id") or m.id, "name": m.title or pb.get("name") or m.id,
                "as": m.as_ or pb.get("as") or "body", "kind": kind,
                "target": (m.target or "0") if kind == "text" else (m.target or None),
                "shape": (m.shape or "16:9") if kind == "graphic" else (m.shape or None),
                "row": row, "col": col, "place": pb.get("place"),
                "fixed": pb.get("fixed"), "chips": list(pb.get("chips") or []),
                "plec_by": m.plec_by or "readvisor",
                "state": "written" if m.state == "written" else None,
                "href": pb.get("href"), "plec": m.plec,
                "text": C.rich_to_md(page).strip("\n"), "extra": dict(pb.get("extra") or {}),
            })
        model.frames.append(frame)
    for bid in view.get("loose") or []:
        model.warnings.append(f"box {bid} sits on no frame and is left out of the state.")
    for c in (comments or {}).get("comments") or []:
        f = c.get("finding") if isinstance(c, dict) else None
        if not isinstance(f, dict):
            continue
        if f.get("box") not in state_ids:
            model.warnings.append(f"finding {f.get('id')} is about box {f.get('box')}, which the state "
                                  "leaves out, so the finding is left out too.")
            continue
        model.findings.append({
            "id": f.get("id"), "box": state_ids[f["box"]], "kind": f.get("kind"),
            "quote": f.get("quote") or None, "prefix": f.get("prefix") or None,
            "suffix": f.get("suffix") or None, "fix": f.get("fix"), "why": f.get("why") or None,
            "status": f.get("status"), "version": int(f.get("version") or 1), "extra": {}})
    problems = S.validate(model)
    if problems:
        raise S.StateError(problems[0])
    return model


def findings_from_state(model: Any, comp: C.Composure) -> list[dict[str, Any]]:
    """The state's `# Findings` as the sidecar's findings: each about its box's module id on `comp`
    (a plectrum id maps through `module_id`; a box the state names by its module id stays so). The
    fields the sidecar adds when a finding lands (`pass`, `answered_at`) are not in a state."""
    out: list[dict[str, Any]] = []
    for f in model.findings:
        box = str(f.get("box") or "")
        mid = box if comp.module(box) is not None else module_id(box)
        out.append({"id": f.get("id"), "box": mid, "kind": f.get("kind"),
                    "quote": f.get("quote") or "", "prefix": f.get("prefix") or "",
                    "suffix": f.get("suffix") or "", "fix": f.get("fix"), "why": f.get("why"),
                    "status": f.get("status"), "version": int(f.get("version") or 1)})
    return out


def plectrum_from_composure(comp: C.Composure, plectrum: Any | None = None) -> str:
    """The plectrum as the composure now holds it, in the writer's form."""
    S = state_module()
    return S.dumps(state_from_composure(comp, plectrum), "plectrum")


# ---------------------------------------------------------------------------
# The two doors (0.9): the state out of a composure, and a state's words in
# ---------------------------------------------------------------------------

STATE_SUFFIX = ".scaffold.md"


def side_plectrum(comp_path: Path) -> Any | None:
    """The plectrum kept beside the composure, read, or None when there is none or it does not read."""
    pp = plectrum_path(comp_path)
    if not pp.is_file():
        return None
    try:
        return loads(pp.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - a plectrum that does not read only loses what it carried
        return None


def state_text(comp_path: Path, doc_rel: str = "") -> str:
    """The scaffold's state file, as the skill's own writer (`scaffold_state.dumps`) writes it from the composure,
    the plectrum beside it and its findings. Locked or open alike: it only reads."""
    comp = C.load(comp_path)
    model = state_from_composure(comp, side_plectrum(comp_path), C.load_comments(comp_path, doc_rel))
    return state_module().dumps(model, "scaffold")


class BringError(Exception):
    """A state that cannot come into this scaffold, said in a sentence; `status` is the route's answer."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


@dataclass
class Bring:
    """What bringing a state in would do (the preview), and the ops that do it."""
    ops: list[dict[str, Any]] = field(default_factory=list)
    matching: list[str] = field(default_factory=list)   # the state's boxes the scaffold already has
    new: list[str] = field(default_factory=list)        # the state's boxes the scaffold does not have
    no_words: list[str] = field(default_factory=list)   # the scaffold's boxes the state brings no words for
    filled: list[str] = field(default_factory=list)     # boxes that get the state's words
    replace: list[dict[str, str]] = field(default_factory=list)  # boxes holding other words already: {id, name}
    kept: list[str] = field(default_factory=list)       # of those, the ones whose words stay
    removed: list[str] = field(default_factory=list)    # empty boxes and frames the state's layout drops
    pictures: list[str] = field(default_factory=list)   # graphic boxes whose picture does not travel
    plec_by: dict[str, str] = field(default_factory=dict)  # module id → who wrote its plec, as the file says
    findings: int = 0
    findings_here: int = 0
    locked: str | None = None
    checked: str | None = None
    thing: str = "page"
    title: str = ""
    model: Any = None

    def summary(self) -> dict[str, Any]:
        return {"matching": len(self.matching), "new": len(self.new), "no_words": len(self.no_words),
                "filled": self.filled, "replace": self.replace, "kept": self.kept, "removed": self.removed,
                "pictures": self.pictures, "findings": self.findings,
                "findings_brought": self.findings if self.findings and not self.findings_here else 0,
                "locked": self.locked, "checked": self.checked, "thing": self.thing, "title": self.title,
                "names": {"matching": self.matching, "new": self.new, "no_words": self.no_words}}


def _box_md(m: C.Module) -> str:
    return C.rich_to_md(m.pages[0].rich if m.pages else "").strip("\n")


def read_state(text: str) -> Any:
    """The person's file read by the one parser; a plectrum, or a file that does not read, is refused."""
    S = state_module()
    try:
        model = S.loads(text or "")
    except S.StateError as e:
        raise BringError(f"that file is not a scaffold's state enough can read, so nothing was brought in. {e}")
    if model.kind != "scaffold":
        raise BringError("that file is a plectrum (plectrum: 1): it has the layout and no words of yours, so there "
                         "is nothing to bring in. A state file starts with scaffold: 1.")
    return model


def bring_plan(model: Any, comp: C.Composure, *, replace: list[str] | None = None,
               findings_here: int = 0) -> Bring:
    """What bringing the state `model` into the scaffold `comp` does, as one batch of the person's ops (`ui`).

    The layout comes by `plectrum_ops` (the person's own plecs included). The words come by `set_page`: into an
    empty box, or a new one, always; into a box that already holds other words only when its module id is in
    `replace` (the person was shown it and said yes), else they stay and the box is named in `kept`. A box the state
    has no words for keeps whatever it holds. The `written` marks come with the words, and so does the version; a
    locked state comes in locked (`state.md`: a harness takes the state in with nothing lost), as the batch's last
    op. A box's picture does not travel: its path was the other harness's."""
    view = C.scaffold_view(comp)
    if view is None:
        raise BringError("this composure is not a scaffold, so a scaffold's state cannot come into it.")
    if C.scaffold_locked(comp):
        raise BringError("this scaffold is locked: nothing comes into it while it is. Unlock it (which makes the "
                         "next version as a new file), or bring the state into a fresh scaffold.", 409)
    meta = model.meta
    has_words = any(m.type == C.BOX and _has_text(m) for m in comp.modules)
    if meta["thing"] != view.get("thing") and has_words:
        raise BringError(f"that state is for a {meta['thing']}, and this scaffold makes a {view.get('thing')} with "
                         f"your words in it already, so it cannot hold it. Bring the state into a fresh scaffold, "
                         f"or change what this one becomes first.")
    S = state_module()
    parts = S.count(model)["parts"]
    if parts > C.MAX_MODULES:
        raise BringError(f"that state holds {parts} frames and boxes, and a composure holds {C.MAX_MODULES}, so it "
                         f"cannot come in whole. Split it into two scaffolds where it began.")

    def mid(x: str) -> str:
        m = comp.module(x)
        return x if m is not None and m.type in (C.BOX, C.FRAME) else module_id(x)

    plan = plectrum_ops(model, comp, mid=mid, person=True)
    out = Bring(model=model, thing=meta["thing"], title=meta["title"], findings=len(model.findings),
                findings_here=findings_here, locked=meta.get("locked"), checked=meta.get("checked"))
    # What goes is named by its title; the form's blank first page (no title, nothing on it) is nothing of
    # the person's, and goes unnamed.
    out.removed = [n for n in plan.removed if not (comp.module(n) is not None and not comp.module(n).title)]
    ops = list(plan.ops)
    allowed = set(replace or [])
    held = {m.id: m for m in comp.modules if m.type == C.BOX}
    brought: set[str] = set()
    for b in model.boxes():
        bid = mid(b["id"])
        name = b["name"]
        m = held.get(bid)
        (out.matching if m is not None else out.new).append(name)
        if b.get("plec_by") in ("readvisor", "person"):
            out.plec_by[bid] = b["plec_by"]
        if b["kind"] == "graphic" and b.get("href"):
            out.pictures.append(name)
        text = (b.get("text") or "").strip("\n")
        if not text.strip():
            continue
        if m is not None and _has_text(m):
            if _box_md(m).strip() == text.strip():
                brought.add(bid)
                if b.get("state") == "written" and m.state != "written":
                    ops.append({"op": "update_module", "id": bid, "state": "written"})
                continue
            out.replace.append({"id": bid, "name": name})
            if bid not in allowed:
                out.kept.append(name)
                continue
        brought.add(bid)
        out.filled.append(name)
        ops.append({"op": "set_page", "module": bid, "n": 1, "rich": C.md_to_rich(text)})
        if b.get("state") == "written":
            ops.append({"op": "update_module", "id": bid, "state": "written"})
    gone = set(plan.removed)
    for m in comp.modules:
        if m.type == C.BOX and m.id not in brought and (m.title or m.id) not in gone:
            out.no_words.append(m.title or m.id)
    if int(meta.get("version") or 1) != int(view.get("version") or 1):
        ops.append({"op": "set_scaffold", "version": int(meta.get("version") or 1)})
    if out.locked:
        ops.append({"op": "lock_scaffold", "empty": [mid(b["id"]) for b in model.boxes()]})
    out.ops = ops
    return out


def undo_ops(before: C.Composure, after: C.Composure) -> list[dict[str, Any]]:
    """The ops that bring `after` back to `before`, as one undo step: frames and boxes the batch removed come back
    with their text, the ones it added go, every field and text it changed is set back, and the frames' order, the
    thing, the version and the title are as they were. (A plec put back by the person's undo is theirs, `ui`.)"""
    b_mods = {m.id: m for m in before.modules if m.type in (C.BOX, C.FRAME)}
    a_mods = {m.id: m for m in after.modules if m.type in (C.BOX, C.FRAME)}
    ops: list[dict[str, Any]] = []
    for fid, f in b_mods.items():
        if f.type == C.FRAME and fid not in a_mods:
            ops.append({"op": "add_frame", "id": fid, "shape": f.shape or "page", "title": f.title,
                        "x": f.x, "y": f.y})
            ops.append({"op": "update_module", "id": fid, "w": f.w, "h": f.h})
    for bid, m in b_mods.items():
        a = a_mods.get(bid)
        if m.type == C.BOX and a is not None and a.frame != m.frame and m.frame:
            ops.append({"op": "move_to_frame", "id": bid, "frame": m.frame, "x": m.x, "y": m.y})
    for bid, m in b_mods.items():
        if m.type != C.BOX or bid in a_mods:
            continue
        op: dict[str, Any] = {"op": "add_module", "type": C.BOX, "id": bid, "title": m.title,
                              "kind": m.kind or "text", "as": m.as_ or "", "plec": m.plec,
                              "target": m.target or "", "x": m.x, "y": m.y, "w": m.w, "h": m.h, "z": m.z,
                              "rich": m.pages[0].rich if m.pages else ""}
        if m.frame:
            op["frame"] = m.frame
        if m.kind == "graphic":
            op["shape"] = m.shape or "16:9"
        if m.href:
            op["href"] = m.href
        if m.state in ("written", "empty", "over"):
            op["state"] = m.state
        ops.append(op)
    for key, m in b_mods.items():
        a = a_mods.get(key)
        if a is None:
            continue
        patch: dict[str, Any] = {}
        for k in ("x", "y", "w", "h", "title"):
            if getattr(a, k) != getattr(m, k):
                patch[k] = getattr(m, k)
        if m.type == C.BOX:
            for k, attr in (("kind", "kind"), ("as", "as_"), ("plec", "plec"), ("target", "target"),
                            ("shape", "shape")):
                if (getattr(a, attr) or "") != (getattr(m, attr) or ""):
                    patch[k] = getattr(m, attr) or ""
            if (a.state or "empty") != (m.state or "empty") and m.state in ("written", "empty", "over"):
                patch["state"] = m.state
        elif (a.shape or "page") != (m.shape or "page"):
            patch["shape"] = m.shape or "page"
        if patch:
            ops.append({"op": "update_module", "id": key, **patch})
        if m.type == C.BOX:
            old = m.pages[0].rich if m.pages else ""
            new = a.pages[0].rich if a.pages else ""
            if old != new:
                ops.append({"op": "set_page", "module": key, "n": 1, "rich": old})
    ops += [{"op": "remove_module", "id": i} for i, m in a_mods.items() if m.type == C.BOX and i not in b_mods]
    ops += [{"op": "remove_module", "id": i} for i, m in a_mods.items() if m.type == C.FRAME and i not in b_mods]
    if C.frame_order(before) and (C.frame_order(after) != C.frame_order(before) or set(b_mods) != set(a_mods)):
        ops.append({"op": "reorder_frames", "order": C.frame_order(before)})
    bv, av = C.scaffold_view(before) or {}, C.scaffold_view(after) or {}
    if bv.get("thing") and bv.get("thing") != av.get("thing"):
        ops.append({"op": "set_scaffold", "thing": bv["thing"]})
    if int(bv.get("version") or 1) != int(av.get("version") or 1):
        ops.append({"op": "set_scaffold", "version": int(bv.get("version") or 1)})
    if before.title != after.title:
        ops.append({"op": "set_meta", "title": before.title})
    return ops


__all__ = [
    "Bring", "BringError", "PLECTRUM_SUFFIX", "Plan", "STATE_SUFFIX", "bring_plan", "composure_target", "findings_from_state", "frame_shape", "loads",
    "module_id",
    "plectrum_from_composure", "plectrum_ops", "plectrum_path", "state_from_composure",
    "read_state", "side_plectrum", "state_module", "state_text", "undo_ops",
]
