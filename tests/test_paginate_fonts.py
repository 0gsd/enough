"""Probe: typst resolves the four bundled font families exactly as the
paginate options contract names them (paginate-plan.md §2.2 / §2.7) —
"EB Garamond", "Source Serif 4", "Source Sans 3", "Inter".

A family-name mismatch (e.g. a font whose internal Family name is "EB
Garamond 12" rather than "EB Garamond") doesn't raise — with
`ignore_system_fonts=True` it either resolves to nothing and the text falls
back to typst's built-in font, or (as verified directly against this
compiler below) surfaces as an "unknown font family" warning. Zero
font-related warnings from `typst.compile_with_warnings` on a probe that
sets each contract name in turn is therefore the acceptance bar, not just
"the compile didn't raise."

Skips cleanly when `defaults/fonts/` hasn't been bundled yet (an earlier
wave's checkout, or a stripped-down source tree) rather than failing the
whole suite. `enough.paginate` isn't imported here — that module is a
different wave's territory and may not exist yet — so the fonts dir is
located the same way `paginate.fonts_dir()` is specified to
(`skeleton._install_defaults_root() / "fonts"`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from enough import skeleton

# Verbatim from paginate-plan.md §2.2's "font" enum.
FONT_FAMILIES = ["EB Garamond", "Source Serif 4", "Source Sans 3", "Inter"]

# Family name -> bundled directory name under defaults/fonts/.
FAMILY_DIRS = {
    "EB Garamond": "eb-garamond",
    "Source Serif 4": "source-serif-4",
    "Source Sans 3": "source-sans-3",
    "Inter": "inter",
}

FONTS_DIR = skeleton._install_defaults_root() / "fonts"

pytestmark = pytest.mark.skipif(
    not FONTS_DIR.is_dir(),
    reason="defaults/fonts/ not bundled in this checkout (wave C not landed)")


def _probe_source() -> str:
    """One heading + one body line per family; each body line exercises
    regular, italic, bold, and bold-italic runs — the four styles §2.7
    requires every family to ship as static files."""
    families = ", ".join(f'"{f}"' for f in FONT_FAMILIES)
    return "\n".join([
        f"#let families = ({families})",
        "#for f in families {",
        "  set text(font: f, size: 11pt)",
        "  [== #f]",
        "  [Regular text with #emph[an italic run], "
        "#strong[a bold run], and #strong[#emph[a bold-italic run]].]",
        "}",
    ])


def test_bundled_font_dirs_present():
    """Every family directory has exactly its four static style files
    (no variable-font [wght] files, no extras) plus a verbatim upstream
    license."""
    for family, dirname in FAMILY_DIRS.items():
        d = FONTS_DIR / dirname
        assert d.is_dir(), f"{family}: missing directory {d}"
        entries = list(d.iterdir())
        font_files = [f for f in entries if f.suffix.lower() in (".ttf", ".otf")]
        assert len(font_files) == 4, (
            f"{family}: expected exactly 4 style files, "
            f"found {sorted(f.name for f in font_files)}")
        for f in font_files:
            assert "[" not in f.name, (
                f"{family}: {f.name} looks like a variable-font instance "
                "file — static instances only per §2.7")
        license_files = [f for f in entries
                          if f.name.lower() in ("ofl.txt", "license.md", "license.txt")]
        assert license_files, f"{family}: no OFL.txt/LICENSE file in {d}"


def test_typst_resolves_all_contract_family_names(tmp_path: Path):
    """Compile the probe with font_paths=[defaults/fonts] and
    ignore_system_fonts=True; assert zero warnings, i.e. typst found every
    one of the four contract family names among the bundled files rather
    than silently falling back."""
    typst = pytest.importorskip("typst")

    probe = tmp_path / "probe.typ"
    probe.write_text(_probe_source(), encoding="utf-8")
    out = tmp_path / "probe.pdf"

    _, warnings = typst.compile_with_warnings(
        str(probe), output=str(out), root=str(tmp_path),
        font_paths=[str(FONTS_DIR)], ignore_system_fonts=True)

    assert not warnings, (
        "typst raised warnings compiling the font probe (a family-name "
        f"mismatch would show up here): {[str(w) for w in warnings]}")
    assert out.is_file() and out.stat().st_size > 0


def test_unknown_family_does_warn(tmp_path: Path):
    """Sanity check on the detection mechanism itself: an unresolved family
    name against this same font_paths/ignore_system_fonts configuration
    does produce a warning, so a clean run of the test above is meaningful
    rather than a compiler that never warns."""
    typst = pytest.importorskip("typst")

    probe = tmp_path / "bad.typ"
    probe.write_text(
        '#set text(font: "Definitely Not A Bundled Family")\n[hello]',
        encoding="utf-8")
    out = tmp_path / "bad.pdf"

    _, warnings = typst.compile_with_warnings(
        str(probe), output=str(out), root=str(tmp_path),
        font_paths=[str(FONTS_DIR)], ignore_system_fonts=True)

    assert any("font" in str(w).lower() for w in warnings)
