#!/usr/bin/env python3
"""Model bootstrapper for the translator skill.

Downloads the pre-converted CTranslate2 weights for MADLAD-400-3B-MT
(Apache 2.0, ~3 GB) into ~/.local/share/translator/madlad400-3b-ct2/
on first use. Idempotent: safe to re-run; verifies completeness before
re-downloading.

Subcommands:
    --check            Is the default model installed? (yes/no + exit code)
    --install          Download MADLAD-400-3B-MT weights (~3 GB)
    --install-7b       Also fetch the int8 7B variant (~7 GB), opt-in
    --status           Report what's installed under TRANSLATOR_HOME
    --where            Print the install root and exit
    --uninstall        Remove the default 3B install (asks first)

Trust model:
    Downloads come from huggingface.co over HTTPS. The huggingface_hub
    library performs SHA-256 verification against the repo's metadata
    automatically; we don't second-guess it.

Models:
    3B (default): santhosh/madlad400-3b-ct2  (Apache 2.0)
    7B (opt-in): avans06/madlad400-7b-mt-bt-ct2-int8_float16  (Apache 2.0)

Override the install root with the TRANSLATOR_HOME env var.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

DEFAULT_REPO_3B = "santhosh/madlad400-3b-ct2"
DEFAULT_REPO_7B = "avans06/madlad400-7b-mt-bt-ct2-int8_float16"
DIR_3B = "madlad400-3b-ct2"
DIR_7B = "madlad400-7b-ct2"


def install_root() -> Path:
    return Path(
        os.environ.get(
            "TRANSLATOR_HOME",
            str(Path.home() / ".local" / "share" / "translator"),
        )
    )


def _die(msg: str, code: int = 1) -> None:
    print(f"bootstrap.py: {msg}", file=sys.stderr)
    sys.exit(code)


def _has_huggingface_hub() -> bool:
    try:
        import huggingface_hub  # noqa: F401
        return True
    except ImportError:
        return False


def is_installed(local_dir: Path) -> bool:
    """A model dir is 'installed' if it contains the ct2 binary plus the
    sentencepiece model. The HF snapshot will create more files than
    this; these two are the load-bearing ones for translate.py."""
    if not local_dir.is_dir():
        return False
    return (local_dir / "model.bin").is_file() and (
        local_dir / "sentencepiece.model"
    ).is_file()


def download_model(repo_id: str, local_dir: Path) -> None:
    """Snapshot-download `repo_id` into `local_dir`. huggingface_hub
    handles resume, hash verification, and parallel chunked download
    on its own."""
    if not _has_huggingface_hub():
        _die(
            "huggingface_hub is not installed. "
            "run: pip install -r requirements.txt"
        )
    from huggingface_hub import snapshot_download

    local_dir.mkdir(parents=True, exist_ok=True)
    print(f"downloading {repo_id} -> {local_dir}", file=sys.stderr)
    print("  (this is ~3 GB for the 3B model; ~7 GB for the 7B)", file=sys.stderr)
    snapshot_download(
        repo_id=repo_id,
        local_dir=str(local_dir),
        # The HF cache layer is a separate concern from where the model
        # ultimately lives for our skill — copy weights into local_dir
        # instead of leaving symlinks pointing back into ~/.cache. Means
        # the user can `rm -rf ~/.cache/huggingface` without breaking us.
        local_dir_use_symlinks=False,
    )
    if not is_installed(local_dir):
        _die(
            f"download finished but {local_dir} is missing model.bin or "
            f"sentencepiece.model. retry, or check disk space."
        )
    print(f"installed: {local_dir}", file=sys.stderr)


def cmd_check() -> int:
    if is_installed(install_root() / DIR_3B):
        print("ok: MADLAD-400-3B-MT is installed.")
        return 0
    print("missing: MADLAD-400-3B-MT not found. run: bootstrap.py --install")
    return 1


def cmd_install() -> int:
    target = install_root() / DIR_3B
    if is_installed(target):
        print(f"already installed at {target}", file=sys.stderr)
        return 0
    download_model(DEFAULT_REPO_3B, target)
    return 0


def cmd_install_7b() -> int:
    target = install_root() / DIR_7B
    if is_installed(target):
        print(f"already installed at {target}", file=sys.stderr)
        return 0
    download_model(DEFAULT_REPO_7B, target)
    return 0


def _dir_size_gb(p: Path) -> float:
    if not p.is_dir():
        return 0.0
    total = 0
    for root, _dirs, files in os.walk(p):
        for f in files:
            try:
                total += (Path(root) / f).stat().st_size
            except OSError:
                pass
    return total / (1024 ** 3)


def cmd_status() -> int:
    root = install_root()
    print(f"install root: {root}")
    if not root.is_dir():
        print("  (not yet created — nothing installed)")
        return 0
    for sub in sorted(root.iterdir()):
        if not sub.is_dir():
            continue
        marker = "✓" if is_installed(sub) else "✗ (incomplete)"
        size = _dir_size_gb(sub)
        print(f"  {sub.name:<32} {size:>5.2f} GB   {marker}")
    return 0


def cmd_where() -> int:
    print(install_root())
    return 0


def cmd_uninstall() -> int:
    target = install_root() / DIR_3B
    if not target.is_dir():
        print(f"nothing to uninstall at {target}", file=sys.stderr)
        return 0
    answer = input(f"remove {target}? [y/N] ").strip().lower()
    if answer != "y":
        print("aborted.", file=sys.stderr)
        return 1
    shutil.rmtree(target)
    print(f"removed {target}", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Model bootstrapper for the translator skill.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true",
                   help="is the default 3B model installed?")
    g.add_argument("--install", action="store_true",
                   help="download MADLAD-400-3B-MT weights (~3 GB)")
    g.add_argument("--install-7b", action="store_true",
                   help="also download the int8 7B variant (~7 GB), opt-in")
    g.add_argument("--status", action="store_true",
                   help="list installed translation models and their sizes")
    g.add_argument("--where", action="store_true",
                   help="print the install root path and exit")
    g.add_argument("--uninstall", action="store_true",
                   help="remove the default 3B install (asks first)")
    args = ap.parse_args()

    if args.check:       return cmd_check()
    if args.install:     return cmd_install()
    if args.install_7b:  return cmd_install_7b()
    if args.status:      return cmd_status()
    if args.where:       return cmd_where()
    if args.uninstall:   return cmd_uninstall()
    return 2  # unreachable; argparse enforces exclusivity


if __name__ == "__main__":
    sys.exit(main())
