"""The MacroCOSM spec's complete examples are real files.

docs/MACROCOSM_OES.md promises that every block marked ```cosm is one
complete file of the MiniCOSM it declares: it loads, it is not refused, and
it passes its MiniCOSM's checks with every reference resolving inside the
block. This test holds the spec to that promise with the reference reader
(where they disagree the reader wins, and the spec is corrected).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from enough import macrocosm as mc

SPEC = Path(__file__).resolve().parents[1] / "docs" / "MACROCOSM_OES.md"
_BLOCK = re.compile(r"^```cosm\n(.*?)^```", re.S | re.M)


def _blocks() -> list[str]:
    return _BLOCK.findall(SPEC.read_text(encoding="utf-8"))


def _file_name(data: dict) -> str:
    """The name each example would have on disk: the catalog name its
    MiniCOSM expects, so identify() sees it as a reader would."""
    if data.get("oes") == "canon/1":
        return "canon.cosm"
    if data.get("oes") == "eml/1":
        source = (data.get("source") or {}).get("path") or "text.md"
        return f"{Path(str(source)).name}.cosm"
    return "brand.cosm"


def test_spec_exists_and_has_examples():
    assert SPEC.is_file(), "docs/MACROCOSM_OES.md is missing"
    assert len(_blocks()) >= 4


@pytest.mark.parametrize("index", range(len(_blocks()) if SPEC.is_file() else 0))
def test_spec_example_loads_and_lints_clean(index, tmp_path):
    text = _blocks()[index]
    data = mc.yaml_load(text)
    assert isinstance(data, dict) and data, f"example {index + 1} is not a mapping"
    first = next(iter(data))
    assert first in ("oes", "cosm"), f"example {index + 1} does not start with its declaration ({first})"
    path = tmp_path / _file_name(data)
    path.write_text(text, encoding="utf-8")
    volume = mc.load_volume(path)
    assert volume.refused is None, f"example {index + 1} refused: {volume.refused}"
    report = mc.lint(volume)
    assert report.ok, f"example {index + 1}: " + "; ".join(str(e) for e in report.errors)
    assert not report.warnings, f"example {index + 1}: " + "; ".join(str(w) for w in report.warnings)
