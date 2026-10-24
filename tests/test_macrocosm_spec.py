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
    if data.get("oes") == "emf/1":
        source = (data.get("source") or {}).get("path") or "text.md"
        return f"{Path(str(source)).name}.cosm"
    if data.get("oes") == "doc/1":
        telling = (data.get("telling") or {}).get("lang") or "en"
        return f"{str(data.get('id', 'doc/x')).split('/', 1)[-1]}.{telling}.doc.cosm"
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


def test_spec_examples_use_only_declared_catalog_keys(tmp_path):
    """Every key an example's catalog carries is one its manifest declares (no `catalog-key` note), and the EMF
    example carries the `shorts:` list SHORT added (plan §15), so the manifest's declaration of it is tested."""
    shorts = 0
    for index, text in enumerate(_blocks()):
        data = mc.yaml_load(text)
        path = tmp_path / f"{index}" / _file_name(data)
        path.parent.mkdir()
        path.write_text(text, encoding="utf-8")
        report = mc.lint(mc.load_volume(path))
        notes = [str(p) for p in report.notes if p.check == "catalog-key"]
        assert not notes, f"example {index + 1}: " + "; ".join(notes)
        if data.get("oes") == "emf/1" and isinstance(data.get("shorts"), list):
            shorts += 1
            for entry in data["shorts"]:
                assert set(entry) == {"path", "at", "by", "mode", "order"}, entry
                assert entry["order"] in ("told", "weight") and entry["mode"] in ("model", "rules")
    assert shorts >= 1, "no example shows an EMF's shorts: list"
