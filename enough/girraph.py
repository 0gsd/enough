"""Girraph: plain-text, IBIS-flavored graph documents (`.girraph`).

A girraph (pronounced "graph" — the `ir` is for iterative/recursive) maps
a contested question as issues, positions, arguments, and notes, where
any node can reference another girraph (recursion) or any markdown doc
(transclusion). This module owns the format: parser, serializer,
node-level ops, and the ASCII render view. The broker tools (tools.py)
and the UI endpoints (server.py) both call through here — no other code
should touch `.girraph` content directly.

Design constraints (from the enough charter — see docs/girraph-plan.md):

- **Files are the source of truth.** The `.girraph` file is canonical,
  human-readable, diffable plain text. No graph database; any index is
  a derived, disposable cache.
- **Small-model ergonomics.** Line-oriented records: one node = one
  line, plus optional detail blocks at the end of the file. A 16K-ctx
  local model can emit or patch a single line reliably.
- **Stable node IDs**, assigned at creation, never reused. The `next:`
  header line carries per-prefix high-water marks so deleting the
  highest-numbered node can never cause a recycled ID.
- **Round-trip safety.** Lines the parser doesn't understand are
  preserved verbatim (`freeform`) and reported as warnings — a flaky
  model or a 2056 text editor can't lose data by writing something the
  grammar doesn't cover.

Format (v0.1):

    %girraph 0.1
    title: Should enough ship a plugin API?
    next: a4 g2 n2 p3 q2

    q1 ? Should enough ship a plugin API?
    p1 ! Ship a minimal one < q1
    a1 + Ecosystem growth needs stable hooks < p1 by:graham
    a3 + Skills already cover 80% of cases < p2 [-> a2]
    n1 . Background reading < q1 ref:infoworld/plugins-survey.md
    g1 @ Subproblem: versioning < p1 ref:rness/girraphs/versioning.girraph

    q1 >
      Longer free-form details, markdown allowed.

Node line: `<id> <sigil> <label> [modifiers...]`. Modifiers are stripped
right-to-left from the end of the line: `< id` (parent edge), `[-> id]`
(cross-edge, repeatable), `ref:path`, `by:slug`. Whatever remains is the
label. Canonical on-disk syntax is pure ASCII (`[-> id]`, not `[→ id]`);
the parser accepts the arrow glyph, the serializer normalizes it away.
Emoji live in the render views only.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

FORMAT_VERSION = "0.1"
MAGIC_PREFIX = "%girraph"

# Node types, their one-char line sigils, render emoji, and the
# conventional ID prefix the broker assigns at creation. (Any prefix is
# legal when reading — these only govern what add_node generates.)
SIGIL_TO_TYPE = {
    "?": "issue",
    "!": "position",
    "+": "support",
    "-": "objection",
    ".": "note",
    "@": "girraph",
}
TYPE_TO_SIGIL = {v: k for k, v in SIGIL_TO_TYPE.items()}
TYPE_EMOJI = {
    "issue": "❓",
    "position": "💡",
    "support": "➕",
    "objection": "➖",
    "note": "📄",
    "girraph": "🦒",
}
TYPE_PREFIX = {
    "issue": "q",
    "position": "p",
    "support": "a",   # supports and objections are both "arguments"
    "objection": "a",
    "note": "n",
    "girraph": "g",
}

_ID_RE = re.compile(r"^[a-z]+[0-9]+$")
_NODE_LINE_RE = re.compile(r"^(?P<id>[a-z]+[0-9]+)\s+(?P<sigil>[?!+\-.@])\s+(?P<rest>.*)$")
_DETAIL_START_RE = re.compile(r"^(?P<id>[a-z]+[0-9]+)\s*>\s*$")
_NEXT_TOKEN_RE = re.compile(r"^([a-z]+)([0-9]+)$")

# Modifier patterns, each anchored to the END of the (remaining) line.
# Stripping repeats right-to-left until nothing matches; the leftover is
# the label. The arrow accepts both ASCII `->` and the `→` glyph.
_MOD_CROSS_RE = re.compile(r"\s*\[\s*(?:->|→)\s*(?P<id>[a-z]+[0-9]+)\s*\]\s*$")
_MOD_PARENT_RE = re.compile(r"\s*<\s*(?P<id>[a-z]+[0-9]+)\s*$")
_MOD_REF_RE = re.compile(r"(?:^|\s)ref:(?P<path>\S+)\s*$")
_MOD_BY_RE = re.compile(r"(?:^|\s)by:(?P<slug>[A-Za-z0-9_-]+)\s*$")


class GirraphError(ValueError):
    """Raised for unusable input or an op the format forbids. The message
    is written for the agent's eyes — actionable, names the fix."""


@dataclass
class Node:
    id: str
    type: str                       # issue | position | support | objection | note | girraph
    label: str
    parent: str | None = None
    cross: list[str] = field(default_factory=list)
    ref: str | None = None
    by: str | None = None
    detail: str = ""

    @property
    def sigil(self) -> str:
        return TYPE_TO_SIGIL[self.type]

    @property
    def emoji(self) -> str:
        return TYPE_EMOJI[self.type]


@dataclass
class Girraph:
    title: str = ""
    # Per-prefix high-water marks: {"q": 2} means q2 is the next q-id.
    next_marks: dict[str, int] = field(default_factory=dict)
    nodes: dict[str, Node] = field(default_factory=dict)  # insertion-ordered
    # Body order: ("node", id) and ("raw", verbatim-line) entries. The
    # serializer replays this so unparsed lines survive round-trips in
    # place instead of being shoved to the bottom (or worse, dropped).
    order: list[tuple[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # ---- structure helpers -------------------------------------------------

    def children(self, node_id: str) -> list[Node]:
        return [n for n in self.nodes.values() if n.parent == node_id]

    def roots(self) -> list[Node]:
        """Parentless nodes in file order. (Also nodes whose parent id
        doesn't resolve — a dangling parent is warned at parse time but
        the node still has to render somewhere.)"""
        return [
            n for n in self.nodes.values()
            if n.parent is None or n.parent not in self.nodes
        ]

    def root(self) -> Node | None:
        """The entry point: first parentless node. No `root:` header —
        derived, so there's one less invariant to keep consistent."""
        roots = self.roots()
        return roots[0] if roots else None

    def subtree_ids(self, node_id: str) -> list[str]:
        """node_id plus all tree descendants, cycle-safe."""
        out: list[str] = []
        stack = [node_id]
        seen: set[str] = set()
        while stack:
            nid = stack.pop(0)
            if nid in seen:
                continue
            seen.add(nid)
            out.append(nid)
            stack.extend(c.id for c in self.children(nid))
        return out


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _split_modifiers(rest: str) -> tuple[str, dict[str, object]]:
    """Strip trailing modifier tokens right-to-left; return (label, mods).

    mods keys: parent (str), cross (list[str], in written order),
    ref (str), by (str). Repeated parent/ref/by keep the LAST written
    (rightmost) value — matching "the line ends with the metadata"."""
    mods: dict[str, object] = {"cross": []}
    s = rest.rstrip()
    while True:
        m = _MOD_CROSS_RE.search(s)
        if m:
            mods["cross"].insert(0, m.group("id"))  # restore written order
            s = s[: m.start()].rstrip()
            continue
        m = _MOD_PARENT_RE.search(s)
        if m:
            mods.setdefault("parent", m.group("id"))
            s = s[: m.start()].rstrip()
            continue
        m = _MOD_REF_RE.search(s)
        if m:
            mods.setdefault("ref", m.group("path"))
            s = s[: m.start()].rstrip()
            continue
        m = _MOD_BY_RE.search(s)
        if m:
            mods.setdefault("by", m.group("slug"))
            s = s[: m.start()].rstrip()
            continue
        break
    return s.strip(), mods


def _parse_next_line(value: str) -> dict[str, int]:
    marks: dict[str, int] = {}
    for tok in value.split():
        m = _NEXT_TOKEN_RE.match(tok)
        if m:
            marks[m.group(1)] = int(m.group(2))
    return marks


def _dedent_detail(lines: list[str]) -> str:
    """Strip the common leading indent of the block's non-empty lines
    (canonical is two spaces; accept anything)."""
    indents = [
        len(ln) - len(ln.lstrip(" \t"))
        for ln in lines if ln.strip()
    ]
    cut = min(indents) if indents else 0
    out = [ln[cut:] if ln.strip() else "" for ln in lines]
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out)


def loads(text: str) -> Girraph:
    """Parse `.girraph` text. Never raises on malformed BODY content —
    unparsable lines are preserved as freeform + warned. Raises
    GirraphError only when the magic line is missing (probably not a
    girraph at all — refuse rather than mangle)."""
    lines = text.splitlines()
    if not lines or not lines[0].strip().startswith(MAGIC_PREFIX):
        raise GirraphError(
            f"not a girraph: first line must start with `{MAGIC_PREFIX}` "
            f"(e.g. `{MAGIC_PREFIX} {FORMAT_VERSION}`)."
        )
    g = Girraph()
    pending_details: dict[str, str] = {}

    i = 1
    # Header: `key: value` lines until the first blank or body line.
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            break
        if line.startswith("title:"):
            g.title = line[len("title:"):].strip()
            i += 1
        elif line.startswith("next:"):
            g.next_marks = _parse_next_line(line[len("next:"):])
            i += 1
        else:
            break  # body starts immediately (no blank separator — tolerate)

    # Body.
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        dm = _DETAIL_START_RE.match(line)
        if dm:
            # Detail block: consume following indented (or blank) lines.
            block: list[str] = []
            i += 1
            while i < len(lines) and (not lines[i].strip() or lines[i][0] in " \t"):
                block.append(lines[i])
                i += 1
            pending_details[dm.group("id")] = _dedent_detail(block)
            continue
        nm = _NODE_LINE_RE.match(line)
        if nm:
            nid = nm.group("id")
            if nid in g.nodes:
                g.warnings.append(
                    f"duplicate node id {nid!r} — keeping the first, "
                    f"preserving the duplicate line verbatim."
                )
                g.order.append(("raw", line))
                i += 1
                continue
            label, mods = _split_modifiers(nm.group("rest"))
            node = Node(
                id=nid,
                type=SIGIL_TO_TYPE[nm.group("sigil")],
                label=label,
                parent=mods.get("parent"),  # type: ignore[arg-type]
                cross=list(mods["cross"]),  # type: ignore[arg-type]
                ref=mods.get("ref"),        # type: ignore[arg-type]
                by=mods.get("by"),          # type: ignore[arg-type]
            )
            g.nodes[nid] = node
            g.order.append(("node", nid))
            i += 1
            continue
        g.warnings.append(f"unparsed line preserved verbatim: {line.strip()!r}")
        g.order.append(("raw", line))
        i += 1

    # Attach detail blocks (they may precede their node in sloppy files).
    for nid, detail in pending_details.items():
        if nid in g.nodes:
            g.nodes[nid].detail = detail
        else:
            g.warnings.append(
                f"detail block for unknown node {nid!r} preserved verbatim."
            )
            g.order.append(("raw", f"{nid} >"))
            for ln in detail.splitlines():
                g.order.append(("raw", f"  {ln}" if ln else ""))

    # Post-parse validation (warn, never destroy).
    for n in g.nodes.values():
        if n.parent and n.parent not in g.nodes:
            g.warnings.append(
                f"node {n.id} has unknown parent {n.parent!r} — treated as a root."
            )
        for c in n.cross:
            if c not in g.nodes:
                g.warnings.append(f"node {n.id} has cross-edge to unknown node {c!r}.")
        if n.type == "girraph" and not (n.ref or "").endswith(".girraph"):
            g.warnings.append(
                f"node {n.id} is `@` (nested girraph) but its ref "
                f"({n.ref or 'missing'}) is not a .girraph path."
            )
    # Parent-edge cycles (the tree backbone must be a tree; ref cycles
    # between files are legal and handled by the navigator instead).
    for n in g.nodes.values():
        seen = {n.id}
        cur = n.parent
        while cur and cur in g.nodes:
            if cur in seen:
                g.warnings.append(
                    f"parent-edge cycle involving {n.id} — rendering treats "
                    f"cycle members as roots; fix the `< parent` edges."
                )
                break
            seen.add(cur)
            cur = g.nodes[cur].parent
    return g


def load(path: Path) -> Girraph:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise GirraphError(f"no girraph at {path} — create one with add_node (no parent).")
    return loads(text)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def _node_line(n: Node) -> str:
    parts = [n.id, n.sigil]
    if n.label:
        parts.append(n.label)
    if n.parent:
        parts.append(f"< {n.parent}")
    for c in n.cross:
        parts.append(f"[-> {c}]")
    if n.ref:
        parts.append(f"ref:{n.ref}")
    if n.by:
        parts.append(f"by:{n.by}")
    return " ".join(parts)


def dumps(g: Girraph) -> str:
    """Canonical serialization: header, node list (one per line, freeform
    lines replayed in place), then detail blocks at the end of the file
    in node order — the node list stays a clean scannable table."""
    out: list[str] = [f"{MAGIC_PREFIX} {FORMAT_VERSION}"]
    if g.title:
        out.append(f"title: {g.title}")
    if g.next_marks:
        marks = " ".join(f"{p}{n}" for p, n in sorted(g.next_marks.items()))
        out.append(f"next: {marks}")
    out.append("")
    for kind, value in g.order:
        if kind == "node":
            node = g.nodes.get(value)
            if node is not None:
                out.append(_node_line(node))
        else:
            out.append(value)
    detailed = [g.nodes[v] for k, v in g.order if k == "node" and v in g.nodes and g.nodes[v].detail]
    for n in detailed:
        out.append("")
        out.append(f"{n.id} >")
        for ln in n.detail.splitlines():
            out.append(f"  {ln}" if ln.strip() else "")
    out.append("")
    return "\n".join(out)


def save(path: Path, g: Girraph) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps(g), encoding="utf-8")


# ---------------------------------------------------------------------------
# Node-level ops — the only way content changes. Both the agent tools and
# the UI endpoints call these; last-write-wins at node granularity.
# ---------------------------------------------------------------------------

def _normalize_type(type_or_sigil: str) -> str:
    t = (type_or_sigil or "").strip()
    if t in SIGIL_TO_TYPE:
        return SIGIL_TO_TYPE[t]
    if t in TYPE_TO_SIGIL:
        return t
    raise GirraphError(
        f"unknown node type {type_or_sigil!r}. use one of: "
        + ", ".join(f"{name} ({sig})" for sig, name in SIGIL_TO_TYPE.items())
    )


def assign_id(g: Girraph, node_type: str) -> str:
    """Next free ID for the type's prefix, honoring the high-water mark
    so IDs are never reused even after the max-numbered node is removed."""
    prefix = TYPE_PREFIX[node_type]
    highest = 0
    for nid in g.nodes:
        m = _NEXT_TOKEN_RE.match(nid)
        if m and m.group(1) == prefix:
            highest = max(highest, int(m.group(2)))
    n = max(g.next_marks.get(prefix, 1), highest + 1)
    g.next_marks[prefix] = n + 1
    return f"{prefix}{n}"


def add_node(
    g: Girraph,
    *,
    type: str,
    label: str,
    parent: str | None = None,
    ref: str | None = None,
    by: str | None = None,
    detail: str = "",
) -> Node:
    node_type = _normalize_type(type)
    label = " ".join((label or "").split())  # labels are single-line
    if not label and not ref:
        raise GirraphError("a node needs a label (or at least a ref).")
    if parent is not None and parent not in g.nodes:
        known = ", ".join(g.nodes) or "(none yet)"
        raise GirraphError(f"parent {parent!r} not found. known ids: {known}.")
    if node_type == "girraph" and not (ref or "").endswith(".girraph"):
        raise GirraphError(
            "`girraph` (@) nodes must carry ref:<path>.girraph — for a "
            "markdown doc reference use a note (.) with ref: instead."
        )
    node = Node(
        id=assign_id(g, node_type),
        type=node_type,
        label=label,
        parent=parent,
        ref=ref or None,
        by=by or None,
        detail=detail or "",
    )
    g.nodes[node.id] = node
    g.order.append(("node", node.id))
    return node


# Sentinel: distinguish "don't touch this field" from "clear it" (the
# tool layer maps an empty XML tag to empty string = clear).
_UNSET = object()


def update_node(
    g: Girraph,
    node_id: str,
    *,
    label: object = _UNSET,
    detail: object = _UNSET,
    ref: object = _UNSET,
    by: object = _UNSET,
    parent: object = _UNSET,
) -> Node:
    node = g.nodes.get(node_id)
    if node is None:
        known = ", ".join(g.nodes) or "(none)"
        raise GirraphError(f"no node {node_id!r}. known ids: {known}.")
    if label is not _UNSET:
        new_label = " ".join(str(label).split())
        if not new_label and not (node.ref if ref is _UNSET else ref):
            raise GirraphError("cannot clear the label of a node with no ref.")
        node.label = new_label
    if detail is not _UNSET:
        node.detail = str(detail)
    if ref is not _UNSET:
        new_ref = str(ref).strip()
        if node.type == "girraph" and not new_ref.endswith(".girraph"):
            raise GirraphError("a `@` node's ref must stay a .girraph path.")
        node.ref = new_ref or None
    if by is not _UNSET:
        node.by = str(by).strip() or None
    if parent is not _UNSET:
        new_parent = str(parent).strip() or None
        if new_parent is not None:
            if new_parent not in g.nodes:
                raise GirraphError(f"parent {new_parent!r} not found.")
            if new_parent in g.subtree_ids(node_id):
                raise GirraphError(
                    f"cannot reparent {node_id} under {new_parent} — that's "
                    f"inside its own subtree (would create a cycle)."
                )
        node.parent = new_parent
    return node


def link_nodes(g: Girraph, from_id: str, to_id: str) -> Node:
    src = g.nodes.get(from_id)
    if src is None:
        raise GirraphError(f"no node {from_id!r}.")
    if to_id not in g.nodes:
        raise GirraphError(f"no node {to_id!r} to link to.")
    if to_id == from_id:
        raise GirraphError("a cross-edge to itself says nothing.")
    if to_id in src.cross:
        return src  # idempotent
    src.cross.append(to_id)
    return src


def unlink_nodes(g: Girraph, from_id: str, to_id: str) -> Node:
    src = g.nodes.get(from_id)
    if src is None:
        raise GirraphError(f"no node {from_id!r}.")
    if to_id not in src.cross:
        raise GirraphError(f"{from_id} has no cross-edge to {to_id}.")
    src.cross.remove(to_id)
    return src


def remove_node(g: Girraph, node_id: str, *, cascade: bool = False) -> list[str]:
    """Remove a node. No orphaning, ever: a node with children is refused
    unless `cascade` (then the whole subtree goes). Cross-edges pointing
    at removed nodes are dropped from their source lines. Returns the
    removed ids. Caller (tool layer) owns user confirmation."""
    if node_id not in g.nodes:
        raise GirraphError(f"no node {node_id!r}.")
    kids = g.children(node_id)
    if kids and not cascade:
        listed = ", ".join(f"{c.id} ({c.label[:40]})" for c in kids)
        raise GirraphError(
            f"{node_id} has children: {listed}. pass cascade to remove the "
            f"whole subtree, or reparent/remove the children first."
        )
    doomed = g.subtree_ids(node_id) if cascade else [node_id]
    doomed_set = set(doomed)
    for nid in doomed:
        g.nodes.pop(nid, None)
    g.order = [
        (k, v) for (k, v) in g.order
        if not (k == "node" and v in doomed_set)
    ]
    for n in g.nodes.values():
        n.cross = [c for c in n.cross if c not in doomed_set]
    return doomed


# ---------------------------------------------------------------------------
# ASCII render — a derived view, never the storage format. Used by the
# read_girraph tool result, embeddable in docs, and good in a terminal.
#
# TODO(v2, deliberately out of v1 scope): graphviz/mermaid export as a
# sibling derived view, same signature shape as ascii_render().
# ---------------------------------------------------------------------------

def _render_node_line(n: Node, missing_ref: bool = False) -> str:
    label = n.label or (Path(n.ref).stem.replace("-", " ") if n.ref else "(unlabeled)")
    bits = [f"{n.id} {n.emoji} {label}"]
    for c in n.cross:
        bits.append(f"[→ {c}]")
    if n.ref:
        marker = "⚠ broken ref" if missing_ref else "ref"
        bits.append(f"→ {marker}:{n.ref}")
    if n.by:
        bits.append(f"(by:{n.by})")
    if n.detail:
        bits.append("(+detail)")
    return "  ".join(bits)


def ascii_render(
    g: Girraph,
    *,
    node: str | None = None,
    depth: int | None = None,
    project_dir: Path | None = None,
) -> str:
    """Indented tree with box-drawing connectors.

    `node` — subtree root (default: every root in file order).
    `depth` — levels BELOW the requested node(s) to include; None = all.
      Children beyond the limit collapse to a one-line count so a deep
      tree can never flood a context window.
    `project_dir` — when given, `ref:` targets are existence-checked and
      broken ones get the ⚠ marker.
    """
    lines: list[str] = []
    if g.title:
        lines.append(f"🦒 {g.title}")
        lines.append("")

    def ref_missing(n: Node) -> bool:
        if not n.ref or project_dir is None:
            return False
        return not (project_dir / n.ref).exists()

    rendered: set[str] = set()

    def walk(n: Node, prefix: str, level: int) -> None:
        kids = [k for k in g.children(n.id) if k.id not in rendered]
        if depth is not None and level >= depth and kids:
            count = len(g.subtree_ids(n.id)) - 1
            lines.append(
                f"{prefix}└─ … {len(kids)} children not shown "
                f"({count} nodes below; re-read with a higher depth or node={kids[0].id})"
            )
            # The hidden subtree is covered by the marker — keep the
            # unreachable-node sweep below from re-rendering it as roots.
            rendered.update(g.subtree_ids(n.id))
            return
        for i, kid in enumerate(kids):
            last = i == len(kids) - 1
            connector = "└─ " if last else "├─ "
            lines.append(prefix + connector + _render_node_line(kid, ref_missing(kid)))
            rendered.add(kid.id)
            walk(kid, prefix + ("   " if last else "│  "), level + 1)

    def render_root(s: Node) -> None:
        lines.append(_render_node_line(s, ref_missing(s)))
        rendered.add(s.id)
        walk(s, "", 0)

    if node is not None:
        start = g.nodes.get(node)
        if start is None:
            raise GirraphError(f"no node {node!r}.")
        render_root(start)
    else:
        for s in g.roots():
            render_root(s)
        # Nodes unreachable from any root (parent-edge cycles — warned at
        # parse time) still have to show up somewhere: surface them as
        # extra roots rather than silently dropping them from the view.
        for n in g.nodes.values():
            if n.id not in rendered:
                render_root(n)
    if not g.nodes:
        lines.append("(empty girraph — add_node to start the map)")
    return "\n".join(lines)


def new_girraph(title: str) -> Girraph:
    return Girraph(title=" ".join((title or "").split()))


# ---------------------------------------------------------------------------
# Concurrency — the conflict policy for simultaneous user-panel and
# agent edits. Every write is a read→patch→write of the whole file held
# under a per-path lock, and BOTH write paths (agent tools in tools.py,
# UI endpoints in server.py) go through node-level ops, so concurrent
# edits to different nodes both land. Same-node collisions are
# last-write-wins at node granularity — fine for one human + one agent.
# ---------------------------------------------------------------------------

_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def path_lock(path: Path) -> threading.Lock:
    """The write lock for one girraph file. Hold it across the whole
    load→mutate→save of any mutating op."""
    key = str(path.resolve())
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.Lock())
