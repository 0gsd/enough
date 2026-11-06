"""The lowest Python the project says it runs on must be able to read every module.

`pyproject.toml` says `requires-python >= 3.11`, and `enough/thym/` is copied text-exact into another application that
runs on 3.11. The suite itself runs on a newer interpreter, which reads syntax the floor cannot (a string literal
broken across lines inside an f-string's braces reached a release tree that way). Where a `python3.11` is installed
this asks it to compile every module, writing nothing; where none is, the test is skipped and says so.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

PROBE = r"""
import pathlib, sys
bad = []
for root in sys.argv[1:]:
    for p in sorted(pathlib.Path(root).rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        try:
            compile(p.read_text(encoding="utf-8"), str(p), "exec")
        except SyntaxError as e:
            bad.append(f"{p}:{e.lineno}: {e.msg}")
print("\n".join(bad))
"""


def test_the_floor_python_reads_every_module():
    floor = shutil.which("python3.11")
    if not floor:
        pytest.skip("no python3.11 on this machine; the floor's grammar is not checked here")
    out = subprocess.run([floor, "-I", "-c", PROBE, str(REPO / "enough"), str(REPO / "scripts")],
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "", "Python 3.11 cannot read:\n" + out.stdout
