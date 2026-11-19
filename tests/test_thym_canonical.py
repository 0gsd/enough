"""The canonical dump's vectors (THYM 12.6 "The canonical dump"; 24.3 lists them as suite data): every
`tests/fixtures/thym/canonical/<name>.json` is a mapping whose canonical dump is `<name>.cosm`, byte for byte. The
reference runtime's dump (`enough.macrocosm.dump`) is held to them here, the page's in tests/test_thym_js_runtime.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from enough import macrocosm as mc

CANONICAL = Path(__file__).resolve().parent / "fixtures" / "thym" / "canonical"
NAMES = sorted(p.stem for p in CANONICAL.glob("*.json"))


def test_every_vector_is_a_pair_and_the_folder_holds_nothing_else():
    assert NAMES, "the suite's canonical/ folder is empty"
    assert sorted(p.name for p in CANONICAL.iterdir()) == sorted([f"{n}.json" for n in NAMES] +
                                                                  [f"{n}.cosm" for n in NAMES])


@pytest.mark.parametrize("name", NAMES)
def test_the_reference_dumps_each_mapping_to_its_bytes(name: str):
    data = json.loads((CANONICAL / f"{name}.json").read_text(encoding="utf-8"))
    want = (CANONICAL / f"{name}.cosm").read_bytes()
    assert isinstance(data, dict)
    assert mc.dump(data).encode("utf-8") == want
    assert mc.yaml_load(want.decode("utf-8")) == data                  # and it reads back as the mapping


def test_the_vectors_the_text_names_are_there():
    """THYM 12.6's rules, one vector each (the pins of the text's 0.8 edition, W1-TX2 case 1)."""
    got = {}
    for n in NAMES:
        got.update({k: (CANONICAL / f"{n}.cosm").read_text(encoding="utf-8")
                    for k in json.loads((CANONICAL / f"{n}.json").read_text(encoding="utf-8"))})
    lines = "".join(got.values())
    for line in ("'yes': 'yes'\n", "num: '123'\n", "date: '2026-11-01'\n", "empty: ''\n", "trail: 'trail '\n",
                 "t: 'true\n\n  '\n", 'tab: "a\\tb"\n', 'uni: "café \\Lx"\n', "nbsp: a\u00a0b\n"):
        assert line in lines, line
    assert (CANONICAL / "declaration-first.cosm").read_text(encoding="utf-8") == "oes: thym/1\nid: x\n"
    first = (CANONICAL / "folded.cosm").read_text(encoding="utf-8").split("\n", 1)[0]
    assert first.startswith("long: word ") and len(first) == 115          # folded at the first space past column 110
