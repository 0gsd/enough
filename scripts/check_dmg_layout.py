#!/usr/bin/env python3
"""Check that a built enough DMG has the intended Finder layout.

    uv run python scripts/check_dmg_layout.py PATH.dmg

Mounts the image read-only (no Finder window, not browsable), reads its
.DS_Store, and always detaches. Exits non-zero unless:

  * enough.app is at (180, 170) and Applications at (480, 170),
  * the window is 660x400, and
  * no dot-prefixed item (.VolumeIcon.icns, .background, ...) has an icon
    slot INSIDE the window. A dotfile parked beyond the right/bottom edge is
    fine - that is what the bundler's off-window clause produces.

Background: the 0.4.0 DMG was built while Finder showed hidden files, which
gave .VolumeIcon.icns a slot at (115,82) and moved both real icons. See
desktop/RELEASE.md section 4.

Pure standard library; macOS only (hdiutil).
"""
from __future__ import annotations

import plistlib
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

WANT_WINDOW = (660, 400)
WANT_ICONS = {"enough.app": (180, 170), "Applications": (480, 170)}


def parse_ds_store(data: bytes):
    """Return ({name: (x, y)}, window_size_or_None) from raw .DS_Store bytes.

    Iloc record: <u32 name length in UTF-16 units> <name UTF-16BE> 'Iloc'
    'blob' <u32 16> <u32 x> <u32 y> <8 bytes padding>. The bwsp record
    holds a binary plist whose WindowBounds is "{{x, y}, {w, h}}".
    """
    icons: dict[str, tuple[int, int]] = {}
    for m in re.finditer(rb"Iloc" + rb"blob" + b"\x00\x00\x00\x10", data):
        i = m.start()
        x, y = struct.unpack(">II", data[m.end() : m.end() + 8])
        for n in range(1, 256):  # find the name whose length prefix matches
            a = i - 2 * n
            if a < 4:
                break
            if struct.unpack(">I", data[a - 4 : a])[0] == n:
                try:
                    name = data[a:i].decode("utf-16-be")
                except UnicodeDecodeError:
                    continue
                icons[name] = (x, y)
                break
    window = None
    m = re.search(rb"bwspblob(.{4})", data, re.S)
    if m:
        (ln,) = struct.unpack(">I", m.group(1))
        plist = plistlib.loads(data[m.end() : m.end() + ln])
        nums = re.findall(r"-?\d+", str(plist.get("WindowBounds", "")))
        if len(nums) == 4:
            window = (int(nums[2]), int(nums[3]))
    return icons, window


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    dmg = Path(argv[1]).expanduser()
    if not dmg.is_file():
        print(f"no such file: {dmg}")
        return 2
    with tempfile.TemporaryDirectory(prefix="dmgcheck.") as mp:
        subprocess.run(
            ["hdiutil", "attach", "-nobrowse", "-readonly", "-mountpoint", mp, str(dmg)],
            check=True, stdout=subprocess.DEVNULL,
        )
        try:
            ds = Path(mp) / ".DS_Store"
            if not ds.is_file():
                print("FAIL: image has no .DS_Store (no layout was written)")
                return 1
            icons, window = parse_ds_store(ds.read_bytes())
            present = sorted(p.name for p in Path(mp).iterdir())
        finally:
            subprocess.run(["hdiutil", "detach", "-quiet", mp], check=False)

    failures: list[str] = []
    rows: list[tuple[str, str, str, str]] = []

    wtxt = f"{window[0]}x{window[1]}" if window else "missing"
    ok = window == WANT_WINDOW
    rows.append(("window", f"{WANT_WINDOW[0]}x{WANT_WINDOW[1]}", wtxt, "OK" if ok else "FAIL"))
    if not ok:
        failures.append(f"window is {wtxt}, want {WANT_WINDOW[0]}x{WANT_WINDOW[1]}")

    for name, want in WANT_ICONS.items():
        got = icons.get(name)
        ok = got == want
        rows.append((name, str(want), str(got) if got else "no slot", "OK" if ok else "FAIL"))
        if not ok:
            failures.append(f"{name} is at {got}, want {want}")

    w, h = window or WANT_WINDOW
    for name, pos in sorted(icons.items()):
        if not name.startswith("."):
            continue
        inside = 0 <= pos[0] < w and 0 <= pos[1] < h
        rows.append((name, "off-window", str(pos), "FAIL" if inside else "OK"))
        if inside:
            failures.append(f"{name} has an icon slot inside the window at {pos}")

    widths = [max(len(r[i]) for r in rows + [("item", "expected", "found", "")]) for i in range(3)]
    print(f"{dmg.name}  (volume contents: {', '.join(present)})")
    print(f"{'item'.ljust(widths[0])}  {'expected'.ljust(widths[1])}  {'found'.ljust(widths[2])}  result")
    for r in rows:
        print(f"{r[0].ljust(widths[0])}  {r[1].ljust(widths[1])}  {r[2].ljust(widths[2])}  {r[3]}")
    if failures:
        print("\nFAIL")
        for f in failures:
            print("  - " + f)
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
