#!/usr/bin/env python3
"""
build_icons.py — normalize the Adobe Illustrator SVG icon exports in
enough/static/icons/ into small, consistently-padded, theme-aware icons.

WHY
---
The 33 icons in enough/static/icons/ are raw Illustrator exports. Illustrator
bakes every artboard/layer it has ever seen for a symbol into each exported
file and just toggles the ones you don't want with a CSS class that sets
`display: none;`. That means every file on disk drags along 10-30 completely
invisible copies of *other* icons (different layers with ids like "comment",
"speak", "projectnav-on", ...), which is why files that should be a couple of
KB balloon to 100-220 KB. On top of that, the visible artwork's padding
inside its viewBox is whatever the Illustrator artboard happened to be, so
some icons fill the canvas edge-to-edge, others float in a sea of margin,
and at least one (savewiki-project.svg) has visible geometry that spills
outside the viewBox entirely (y=-4.56).

WHAT THIS SCRIPT DOES
---------------------
For every enough/static/icons/*.svg it emits two files into
enough/static/icons/build/:

1. <name>.svg  (the "light" variant, used by the pastel + wireframe themes)
   - Drops the "Generator: Adobe Illustrator..." comment (this happens for
     free: Python's XML parser does not retain comments, so simply
     re-serializing the parsed tree omits it).
   - Parses the <style> block embedded in <defs>, finds every CSS class
     whose rule is exactly `display: none;`, deletes every element in the
     document carrying that class (the whole subtree — these are always
     top-level Illustrator layer <g>s in practice, but the code does not
     assume that), and deletes the now-pointless CSS rule itself.
   - Also strips any element carrying an inline `style="display:none"` /
     `style="display: none;"`, for robustness against future exports that
     might not use the class-based pattern.
   - Prunes <defs> children (linearGradient / radialGradient / clipPath /
     etc.) that are no longer referenced by anything left in the document:
     it looks for url(#id) inside the CSS rules of classes still applied
     to a surviving element, inside every attribute of every surviving
     element (fill=, stop-color=, clip-path=, xlink:href=...), and follows
     xlink:href chains between gradients (e.g. <linearGradient id="g2"
     xlink:href="#g1"/> inherits g1's <stop>s, so keeping g2 means keeping
     g1 too). Everything unreached by that walk is deleted. This is where
     most of the byte savings come from, since a file may define 40
     gradients for one visible + N invisible layers, and needs at most a
     handful for the one layer that's left.
   - Rewrites the root viewBox to a SQUARE, centered on the icon's visible
     bounding box (as given by scripts/icons-bbox.json, NOT recomputed
     here — see below), with side = max(visW, visH) / 0.82. That puts the
     visible artwork at ~82% of the canvas for every icon regardless of
     how its original artboard was sized, so the whole icon set gets
     uniform, comparable padding for the first time.
   - Strips any fixed width="" / height="" from the root <svg> so it is
     sized purely by CSS via its viewBox.

2. <name>-dark.svg  — identical to the light variant, plus a black<->white
   color swap for the two dark themes (enough-default, darknest):
   - Wherever a color shows up — fill:/stroke:/stop-color: in <style> CSS
     rules, fill=/stroke=/stop-color= presentation attributes, or those
     same properties inside an inline style="" attribute — a near-black
     color becomes #fff and a near-white color becomes #000.
   - "Near-black" = every RGB channel <= 70 (includes the literal keywords
     `black`, #000, #000000). "Near-white" = every channel >= 225
     (includes `white`, #fff, #ffffff). Every other color (mid greys, and
     every hue) is left completely alone.
   - This deliberately reaches into gradient <stop stop-color="..."/>
     elements too, so a black-to-color gradient becomes white-to-color.
   - `fill: none` / `stroke: none` are not colors and are left untouched
     (the classifier simply never matches the literal token "none").
   - This is NOT a CSS/SVG invert filter — only near-black and near-white
     literal colors move; nothing else in the palette shifts.

Both variants are written with square, bbox-matched viewBoxes; only the
color values differ between them.

GROUND TRUTH: scripts/icons-bbox.json
--------------------------------------
Recomputing an SVG's true rendered bounding box from raw path data (with
transforms, stroke widths, nested groups, etc.) is exactly the kind of thing
that's easy to get subtly wrong from first principles. scripts/icons-bbox.json
instead stores real numbers measured in a browser (Chrome getBBox(), with
the hidden display:none layers already excluded) for every icon file this
script knows about. This script trusts that file completely for the visible
bbox of each icon and never tries to re-derive one from path geometry.

If you add a new icon and re-run this script before re-measuring, there
will be no entry for it in icons-bbox.json; the script falls back to using
that icon's existing (unmodified) viewBox and prints a loud warning telling
you to go measure it (open the icon in a browser, call
`document.querySelector('svg').getBBox()` after hiding the display:none
layers, or however your measurement workflow works) and add an entry.

CONTACT SHEET
-------------
enough/static/icons/build/_contact-sheet.html is a plain static page for a
human to eyeball every icon at once: each icon's light variant is shown on
both a pastel (#faf5dc) and a plain white (#ffffff) swatch, and its dark
variant on both a near-black (#1a1a2e) and pure black (#000000) swatch, all
via relative <img src="..."> tags so the page works straight off disk.

IDEMPOTENCY
-----------
This script only ever reads from enough/static/icons/*.svg (the originals)
and scripts/icons-bbox.json; it always writes fresh output into
enough/static/icons/build/, so it is safe to re-run any number of times,
including after new icons are dropped into enough/static/icons/.

USAGE
-----
    python3 scripts/build_icons.py

Run from anywhere; paths are resolved relative to this file's location.
"""

import copy
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
ICONS_DIR = REPO_ROOT / "enough" / "static" / "icons"
BUILD_DIR = ICONS_DIR / "build"
BBOX_JSON = SCRIPT_DIR / "icons-bbox.json"

FILL_RATIO = 0.82  # visible art occupies ~82% of the new square canvas

# Per-icon overrides, applied on top of icons-bbox.json.
#
# projectnav-on.svg embeds a rasterized soft-glow PNG behind the toggle
# knob whose footprint (90x90) dwarfs the pill itself (54x23.62). Left
# alone, the glow inflates the measured bbox and the "on" pill renders
# ~40% smaller than projectnav-off's — unacceptable for a two-state
# toggle pair. We strip the <image> glow at build time and normalize on
# the pill-only bbox (browser-measured; identical to projectnav-off's),
# so the pair aligns pixel-for-pixel. The UI recreates the glow with a
# CSS drop-shadow on the on-state, which scales cleanly at any size.
#
# comment.svg carries a WIDE bbox (91.2x77.76). Under the default 0.82
# square-canvas fill, its long side lands at 82% of the canvas but its
# short (vertical) side only fills ~70%, so on the wiki toolbar it reads
# visibly shorter than its square-ish neighbors (d6, wikisink-settings).
# A per-icon `fill_ratio` override packs the art tighter in the square so
# its height fill matches those neighbors (~0.95 → ~81% vertical fill).
#
# girraphmode.svg has the same problem rotated 90°: a TALL bbox
# (79.2x116.16, the giraffe), whose width fills only ~56% of the square
# under the default 0.82 — it reads visibly smaller than merirmaidmode
# and friends in the topbar chip and cacheawl badges. Same fill_ratio
# treatment as comment.svg.
SPECIAL_CASES = {
    "projectnav-on.svg": {
        "strip_images": True,
        "visBBox": {"x": 18.6, "y": 33.31, "w": 54, "h": 23.62},
    },
    "comment.svg": {
        "fill_ratio": 0.95,
    },
    "girraphmode.svg": {
        "fill_ratio": 0.95,
    },
}

COLOR_PROPS = ("fill", "stroke", "stop-color")


def svg_tag(local):
    return f"{{{SVG_NS}}}{local}"


def xlink_attr(local):
    return f"{{{XLINK_NS}}}{local}"


# ---------------------------------------------------------------------------
# Style block helpers
# ---------------------------------------------------------------------------

RULE_RE = re.compile(r"\.([\w-]+)\s*\{([^}]*)\}")


def split_decls(body):
    """Split a CSS rule body into a list of (prop, value) tuples."""
    out = []
    for chunk in body.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" not in chunk:
            continue
        prop, _, val = chunk.partition(":")
        out.append((prop.strip(), val.strip()))
    return out


def find_hidden_classes_and_strip_rules(style_text):
    """
    Returns (new_style_text, hidden_classes_set).

    Any CSS rule whose *only* declaration is display:none is a hidden-layer
    marker: its class goes in hidden_classes_set and the rule is deleted
    from the returned style text. Rules that mix display:none with other
    declarations (not seen in current exports, but handled defensively)
    keep their other declarations and only the display:none part is razed.
    """
    hidden_classes = set()

    def repl(m):
        cls, body = m.group(1), m.group(2)
        decls = split_decls(body)
        is_display_none = lambda p, v: p.lower() == "display" and v.lower().replace(" ", "") == "none"
        if decls and all(is_display_none(p, v) for p, v in decls):
            hidden_classes.add(cls)
            return ""  # drop the whole rule
        remaining = [(p, v) for p, v in decls if not is_display_none(p, v)]
        if len(remaining) == len(decls):
            return m.group(0)  # untouched, no display:none present
        # Rebuild rule with the display:none declaration(s) removed.
        new_body = "\n        " + "\n        ".join(f"{p}: {v};" for p, v in remaining) + "\n      "
        return f".{cls} {{{new_body}}}"

    new_text = RULE_RE.sub(repl, style_text)
    # tidy up any run of blank lines left behind by a deleted rule
    new_text = re.sub(r"\n{3,}", "\n\n", new_text)
    return new_text, hidden_classes


def strip_unused_class_rules(style_text, used_classes):
    """
    Remove CSS rules for classes that no element in the (already
    hidden-layer-pruned) document carries any more. Without this, a class
    that only ever decorated elements inside a now-deleted hidden layer
    (e.g. `.st2 { fill: url(#linear-gradient1); }`) would survive as dead
    text in <style> whose url(#linear-gradient1) reference then makes
    prune_defs() think that gradient is still needed, when nothing in the
    document can actually reach it any more. Doing this keeps every
    remaining CSS rule's references trustworthy, and is itself a solid
    chunk of the size win: most classes in an Illustrator export exist for
    exactly one now-invisible layer.
    """

    def repl(m):
        cls = m.group(1)
        return m.group(0) if cls in used_classes else ""

    new_text = RULE_RE.sub(repl, style_text)
    new_text = re.sub(r"\n{3,}", "\n\n", new_text)
    return new_text


URL_REF_RE = re.compile(r"url\(#([^)\s]+)\)")


def refs_in_text(text):
    return set(URL_REF_RE.findall(text))


# ---------------------------------------------------------------------------
# Color classification for the dark variant
# ---------------------------------------------------------------------------

HEX_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _hex_channels(hexpart):
    if len(hexpart) == 3:
        return tuple(int(c * 2, 16) for c in hexpart)
    return tuple(int(hexpart[i : i + 2], 16) for i in (0, 2, 4))


def classify_swap(value):
    """
    Returns the replacement color string if `value` is a near-black or
    near-white color, else None (leave untouched). Never matches 'none',
    'transparent', 'currentcolor', gradient references, or mid-palette
    colors/hues.
    """
    v = value.strip()
    low = v.lower()
    if low in ("none", "transparent", "currentcolor"):
        return None
    if low == "black":
        return "#fff"
    if low == "white":
        return "#000"
    m = HEX_RE.match(v)
    if not m:
        return None
    r, g, b = _hex_channels(m.group(1))
    if r <= 70 and g <= 70 and b <= 70:
        return "#fff"
    if r >= 225 and g >= 225 and b >= 225:
        return "#000"
    return None


COLOR_DECL_RE = re.compile(
    r"\b(fill|stroke|stop-color)(\s*:\s*)([^;}\n]+?)(\s*;?)(?=\s*(?:\n|;|\}))"
)


def swap_colors_in_css_text(text):
    """Swap fill:/stroke:/stop-color: values in a chunk of CSS text. Returns
    (new_text, swap_count)."""
    count = 0

    def repl(m):
        nonlocal count
        prop, sep, val, term = m.group(1), m.group(2), m.group(3), m.group(4)
        newval = classify_swap(val)
        if newval is None or newval == val.strip():
            return m.group(0)
        count += 1
        return f"{prop}{sep}{newval}{term}"

    new_text = COLOR_DECL_RE.sub(repl, text)
    return new_text, count


def swap_colors_in_inline_style(style_attr_value):
    return swap_colors_in_css_text(style_attr_value)


def swap_colors_on_attributes(root):
    """Swap fill=/stroke=/stop-color= presentation attributes and any
    inline style="" attribute on every element in the tree. Returns swap
    count."""
    count = 0
    for el in root.iter():
        for prop in COLOR_PROPS:
            if prop in el.attrib:
                newval = classify_swap(el.attrib[prop])
                if newval is not None and newval != el.attrib[prop].strip():
                    el.set(prop, newval)
                    count += 1
        if "style" in el.attrib:
            new_style, n = swap_colors_in_inline_style(el.attrib["style"])
            if n:
                el.set("style", new_style)
                count += n
    return count


DRAW_TAGS = {"path", "rect", "circle", "ellipse", "polygon", "polyline", "line"}
STYLE_FILL_RE = re.compile(r"(?<![-\w])fill\s*:")


def build_class_fill_map(style_text):
    """Maps class name -> True if that class's CSS rule sets a 'fill'
    declaration (of any kind, color or gradient url()). Used to figure out
    whether a shape that has no fill=/style="" of its own is nonetheless
    colored via its class, versus truly falling back to the SVG/CSS
    initial fill value of black."""
    out = {}
    for m in RULE_RE.finditer(style_text):
        cls, body = m.group(1), m.group(2)
        out[cls] = any(p.lower() == "fill" for p, _ in split_decls(body))
    return out


def element_has_explicit_fill(el, class_fill_map):
    if "fill" in el.attrib:
        return True
    style_attr = el.attrib.get("style")
    if style_attr and STYLE_FILL_RE.search(style_attr):
        return True
    cls = el.get("class")
    if cls:
        for c in cls.split():
            if class_fill_map.get(c):
                return True
    return False


def swap_implicit_black_fills(root, class_fill_map):
    """
    Illustrator line-work is often exported as plain <path>/<rect>/...
    elements with no fill attribute and no class that sets one at all —
    they render black purely because that's CSS's initial value for
    'fill'. A literal color/CSS-rule swap never touches these (there is
    no color token to find), so on the dark variant they would silently
    stay black. This walks every drawable shape and, if neither the
    element itself nor any of its ancestors set an explicit fill anywhere
    in the chain, stamps fill="#fff" directly on it (the near-black ->
    white rule, just applied to the implicit default instead of a literal
    value). Returns count of elements patched this way.
    """
    parent_map = {}
    for parent in root.iter():
        for child in parent:
            parent_map[child] = parent

    count = 0
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag not in DRAW_TAGS:
            continue
        node = el
        explicit = False
        while node is not None:
            if element_has_explicit_fill(node, class_fill_map):
                explicit = True
                break
            node = parent_map.get(node)
        if not explicit:
            el.set("fill", "#fff")
            count += 1
    return count


# ---------------------------------------------------------------------------
# Number formatting
# ---------------------------------------------------------------------------


def fmt_num(x):
    s = f"{x:.4f}".rstrip("0").rstrip(".")
    if s in ("", "-0"):
        s = "0"
    return s


# ---------------------------------------------------------------------------
# Core per-file processing
# ---------------------------------------------------------------------------


class IconResult:
    def __init__(self):
        self.bytes_before = 0
        self.bytes_after_light = 0
        self.bytes_after_dark = 0
        self.hidden_stripped = 0
        self.dark_swaps = 0
        self.warning = None


def is_inline_display_none(style_val):
    return re.sub(r"\s+", "", style_val).lower().startswith("display:none")


def strip_hidden_elements(root, hidden_classes):
    """Remove every element (and its subtree) that carries one of
    hidden_classes, or an inline display:none style. Returns count of
    elements removed at the point they were found (before removal, so
    nested duplicates under an already-marked ancestor are not double
    counted since we skip failed removals)."""
    parent_map = {}
    for parent in root.iter():
        for child in parent:
            parent_map[child] = parent

    to_remove = []
    for el in root.iter():
        cls = el.get("class")
        classes = cls.split() if cls else []
        hidden_by_class = any(c in hidden_classes for c in classes)
        style_val = el.get("style")
        hidden_by_style = bool(style_val) and is_inline_display_none(style_val)
        if hidden_by_class or hidden_by_style:
            to_remove.append(el)

    removed = 0
    for el in to_remove:
        parent = parent_map.get(el)
        if parent is None:
            continue
        try:
            parent.remove(el)
            removed += 1
        except ValueError:
            pass  # already gone because an ancestor was removed first
    return removed


def strip_image_elements(root):
    """Remove every raster <image> element (SPECIAL_CASES strip_images).
    Returns count removed."""
    parent_map = {c: p for p in root.iter() for c in p}
    removed = 0
    for el in list(root.iter(svg_tag("image"))):
        parent = parent_map.get(el)
        if parent is not None:
            parent.remove(el)
            removed += 1
    return removed


DEFS_PRUNABLE_TAGS = {
    "linearGradient",
    "radialGradient",
    "pattern",
    "clipPath",
    "filter",
    "mask",
    "symbol",
}


def prune_defs(root, style_text):
    """
    Remove <defs> children that are no longer referenced by anything left
    in the document. Returns count removed.
    """
    defs_el = root.find(svg_tag("defs"))
    if defs_el is None:
        return 0

    # Which classes are still applied to a surviving element?
    used_classes = set()
    for el in root.iter():
        cls = el.get("class")
        if cls:
            used_classes.update(cls.split())

    # References visible in the CSS rules of classes still in use.
    refs = set()
    for m in RULE_RE.finditer(style_text):
        cls, body = m.group(1), m.group(2)
        if cls in used_classes:
            refs |= refs_in_text(body)

    # References visible in any attribute of any surviving element
    # (fill="url(#x)", clip-path="url(#x)", xlink:href="#x", ...).
    for el in root.iter():
        for attr_name, attr_val in el.attrib.items():
            refs |= refs_in_text(attr_val)
            local = attr_name.split("}")[-1]
            if local == "href" and attr_val.startswith("#"):
                refs.add(attr_val[1:])

    # Map of defs-child id -> element, to resolve href chains between them
    # (e.g. linearGradient2 inherits stops from linearGradient1 via
    # xlink:href, so keeping 2 means keeping 1 too).
    id_map = {}
    for child in list(defs_el):
        local = child.tag.split("}")[-1]
        if local in DEFS_PRUNABLE_TAGS:
            cid = child.get("id")
            if cid:
                id_map[cid] = child

    keep = set()
    queue = [r for r in refs if r in id_map]
    while queue:
        cid = queue.pop()
        if cid in keep:
            continue
        keep.add(cid)
        el = id_map[cid]
        for attr_name, attr_val in el.attrib.items():
            local = attr_name.split("}")[-1]
            if local == "href" and attr_val.startswith("#"):
                ref_id = attr_val[1:]
                if ref_id in id_map and ref_id not in keep:
                    queue.append(ref_id)
            for extra in refs_in_text(attr_val):
                if extra in id_map and extra not in keep:
                    queue.append(extra)

    removed = 0
    for child in list(defs_el):
        local = child.tag.split("}")[-1]
        if local in DEFS_PRUNABLE_TAGS:
            cid = child.get("id")
            if cid is not None and cid not in keep:
                defs_el.remove(child)
                removed += 1
    return removed


def rewrite_viewbox(root, bbox_entry, filename, warnings):
    if bbox_entry is None:
        warnings.append(
            f"WARNING: no icons-bbox.json entry for '{filename}' — leaving its "
            f"existing viewBox unchanged. Please measure its visible bbox "
            f"(Chrome getBBox() with hidden layers excluded) and add an entry "
            f"to {BBOX_JSON.name}, then re-run this script."
        )
        return
    vb = bbox_entry["visBBox"]
    x, y, w, h = vb["x"], vb["y"], vb["w"], vb["h"]
    fill_ratio = bbox_entry.get("fill_ratio", FILL_RATIO)
    side = max(w, h) / fill_ratio
    cx = x + w / 2
    cy = y + h / 2
    new_x = cx - side / 2
    new_y = cy - side / 2
    root.set("viewBox", f"{fmt_num(new_x)} {fmt_num(new_y)} {fmt_num(side)} {fmt_num(side)}")


def strip_fixed_size(root):
    for attr in ("width", "height"):
        if attr in root.attrib:
            del root.attrib[attr]


def get_style_el(root):
    defs_el = root.find(svg_tag("defs"))
    if defs_el is None:
        return None
    return defs_el.find(svg_tag("style"))


def serialize(root):
    ET.indent(ET.ElementTree(root), space="  ")
    body = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n"


def process_icon(path, bbox_data, warnings):
    result = IconResult()
    raw = path.read_bytes()
    result.bytes_before = len(raw)

    tree = ET.parse(path)
    root = tree.getroot()

    style_el = get_style_el(root)
    style_text = style_el.text if style_el is not None else ""

    new_style_text, hidden_classes = find_hidden_classes_and_strip_rules(style_text)
    result.hidden_stripped = strip_hidden_elements(root, hidden_classes)

    special = SPECIAL_CASES.get(path.name)
    if special and special.get("strip_images"):
        result.hidden_stripped += strip_image_elements(root)

    # Now that the hidden layers are gone, drop CSS rules for classes
    # nothing in the document uses any more (see strip_unused_class_rules
    # docstring) before we decide what <defs> entries are still reachable.
    used_classes = {c for el in root.iter() for c in (el.get("class") or "").split()}
    new_style_text = strip_unused_class_rules(new_style_text, used_classes)
    if style_el is not None:
        style_el.text = new_style_text

    prune_defs(root, new_style_text)

    bbox_entry = bbox_data.get(path.name)
    rewrite_viewbox(root, bbox_entry, path.name, warnings)
    strip_fixed_size(root)

    # --- light variant ---
    light_str = serialize(root)
    result.bytes_after_light = len(light_str.encode("utf-8"))

    # --- dark variant (deep copy, then swap colors) ---
    class_fill_map = build_class_fill_map(new_style_text)
    dark_root = copy.deepcopy(root)
    dark_style_el = get_style_el(dark_root)
    swap_count = 0
    if dark_style_el is not None and dark_style_el.text:
        swapped_text, n = swap_colors_in_css_text(dark_style_el.text)
        dark_style_el.text = swapped_text
        swap_count += n
    swap_count += swap_colors_on_attributes(dark_root)
    # Illustrator line-work with no fill at all renders black by CSS's
    # initial value; patch those to explicit white too (see docstring on
    # swap_implicit_black_fills).
    swap_count += swap_implicit_black_fills(dark_root, class_fill_map)
    result.dark_swaps = swap_count

    dark_str = serialize(dark_root)
    result.bytes_after_dark = len(dark_str.encode("utf-8"))

    return result, light_str, dark_str


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_output(name, svg_text, bbox_entry):
    problems = []
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as e:
        return [f"{name}: XML PARSE ERROR: {e}"]

    if re.search(r"display\s*:\s*none", svg_text, re.IGNORECASE):
        problems.append(f"{name}: still contains display:none")

    vb = root.get("viewBox")
    if not vb:
        problems.append(f"{name}: missing viewBox")
    else:
        parts = [float(p) for p in vb.split()]
        vx, vy, vw, vh = parts
        if abs(vw - vh) > 1e-6:
            problems.append(f"{name}: viewBox not square ({vw} x {vh})")
        if bbox_entry is not None:
            bb = bbox_entry["visBBox"]
            if not (
                vx <= bb["x"] + 1e-6
                and vy <= bb["y"] + 1e-6
                and vx + vw >= bb["x"] + bb["w"] - 1e-6
                and vy + vh >= bb["y"] + bb["h"] - 1e-6
            ):
                problems.append(f"{name}: viewBox does not fully contain visBBox")
    return problems


# ---------------------------------------------------------------------------
# Contact sheet
# ---------------------------------------------------------------------------

CONTACT_SHEET_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Icon build contact sheet</title>
<style>
  body {{ font-family: -apple-system, sans-serif; background: #222; color: #eee; margin: 0; padding: 24px; }}
  h1 {{ font-size: 18px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; }}
  .card {{ background: #333; border-radius: 8px; padding: 10px; }}
  .name {{ font-size: 12px; margin: 6px 0 8px; word-break: break-all; }}
  .swatches {{ display: flex; gap: 6px; flex-wrap: wrap; }}
  .swatch {{ flex: 1 1 45%; min-width: 90px; border-radius: 4px; padding: 8px; display: flex; align-items: center; justify-content: center; }}
  .swatch img {{ width: 48px; height: 48px; display: block; }}
  .label {{ font-size: 9px; text-align: center; margin-top: 4px; opacity: .7; }}
</style>
</head>
<body>
<h1>Icon build contact sheet ({count} icons)</h1>
<div class="grid">
{cards}
</div>
</body>
</html>
"""

CARD_TEMPLATE = """  <div class="card">
    <div class="name">{name}</div>
    <div class="swatches">
      <div class="swatch" style="background:#faf5dc"><img src="{light}"></div>
      <div class="swatch" style="background:#ffffff"><img src="{light}"></div>
      <div class="swatch" style="background:#1a1a2e"><img src="{dark}"></div>
      <div class="swatch" style="background:#000000"><img src="{dark}"></div>
    </div>
  </div>"""


def build_contact_sheet(names):
    cards = "\n".join(
        CARD_TEMPLATE.format(name=n, light=f"{n}.svg", dark=f"{n}-dark.svg") for n in names
    )
    return CONTACT_SHEET_TEMPLATE.format(count=len(names), cards=cards)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    if not ICONS_DIR.is_dir():
        print(f"ERROR: {ICONS_DIR} not found", file=sys.stderr)
        return 1

    bbox_raw = json.loads(BBOX_JSON.read_text())
    bbox_data = {k: v for k, v in bbox_raw.items() if not k.startswith("_")}
    # SPECIAL_CASES bbox / fill_ratio overrides win over the measured JSON
    # (both process_icon and validate_output see the effective value).
    for fname, spec in SPECIAL_CASES.items():
        if fname not in bbox_data:
            continue
        if "visBBox" in spec:
            bbox_data[fname] = {**bbox_data[fname], "visBBox": spec["visBBox"]}
        if "fill_ratio" in spec:
            bbox_data[fname] = {**bbox_data[fname], "fill_ratio": spec["fill_ratio"]}

    svg_paths = sorted(p for p in ICONS_DIR.glob("*.svg") if p.is_file())
    if not svg_paths:
        print(f"No .svg files found in {ICONS_DIR}", file=sys.stderr)
        return 1

    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    warnings = []
    rows = []
    names = []
    all_problems = []
    total_before = 0
    total_after = 0

    for path in svg_paths:
        name = path.stem
        names.append(name)
        result, light_str, dark_str = process_icon(path, bbox_data, warnings)

        (BUILD_DIR / f"{name}.svg").write_text(light_str, encoding="utf-8")
        (BUILD_DIR / f"{name}-dark.svg").write_text(dark_str, encoding="utf-8")

        bbox_entry = bbox_data.get(path.name)
        all_problems += validate_output(f"{name}.svg", light_str, bbox_entry)
        all_problems += validate_output(f"{name}-dark.svg", dark_str, bbox_entry)

        total_before += result.bytes_before
        total_after += result.bytes_after_light + result.bytes_after_dark

        rows.append(
            (
                path.name,
                result.bytes_before,
                result.bytes_after_light,
                result.bytes_after_dark,
                result.hidden_stripped,
                result.dark_swaps,
            )
        )

    sheet_path = BUILD_DIR / "_contact-sheet.html"
    sheet_path.write_text(build_contact_sheet(names), encoding="utf-8")

    # --- report ---
    print(f"{'file':<26}{'before':>10}{'light':>10}{'dark':>10}{'hidden':>9}{'swaps':>8}")
    for name, before, light, dark, hidden, swaps in rows:
        print(f"{name:<26}{before:>10}{light:>10}{dark:>10}{hidden:>9}{swaps:>8}")

    print()
    print(f"Total icons processed: {len(rows)}")
    print(f"Total source bytes:    {total_before:,}")
    print(f"Total build bytes:     {total_after:,} (light+dark combined, incl. contact sheet not counted)")
    if total_before:
        pct = 100 * (1 - total_after / total_before)
        print(f"Reduction:             {pct:.1f}%")

    build_dir_total = sum(f.stat().st_size for f in BUILD_DIR.iterdir() if f.is_file())
    print(f"build/ directory size (incl. contact sheet): {build_dir_total:,} bytes")

    if warnings:
        print()
        print("Warnings:")
        for w in warnings:
            print(f"  {w}")

    if all_problems:
        print()
        print("VALIDATION PROBLEMS:")
        for p in all_problems:
            print(f"  {p}")
        return 1

    print()
    print("All outputs validated OK (well-formed XML, no display:none, square viewBox containing visBBox).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
