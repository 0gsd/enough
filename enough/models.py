"""Model registry helpers: which GGUFs are supported, where they live, how
much RAM they want, and a RAM-aware context-window recommender.

- Registry template ships at `<install>/defaults/models.json` (shipped, git).
- Live state at `~/enough/config/models.json` — currently just
  `{"current": "<cute-name>"}`. Seeded from template on first access.
- Installed state is derived from whether the model's GGUF file exists at
  `~/enough/weights/<gguf_filename>`. No install-state file needed.

Also exposes a small CLI:
    python -m enough.models params [--cute NAME]
    python -m enough.models resolve-path [--cute NAME]

…which `llama_server.sh` uses to turn a cute name into a concrete model
path + context window.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

INSTALL_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_TEMPLATE = INSTALL_ROOT / "defaults" / "models.json"
LIVE_STATE = Path.home() / "enough" / "config" / "models.json"
WEIGHTS_DIR = Path.home() / "enough" / "weights"


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------

def load_registry() -> dict:
    """Return the shipped registry template (the source of truth for model
    metadata). Raises FileNotFoundError if the install is missing it."""
    return json.loads(REGISTRY_TEMPLATE.read_text(encoding="utf-8"))


def load_state() -> dict:
    """Return the live state, seeding it from the template's 'default' if
    missing. Always returns {"current": "<name>"}."""
    if not LIVE_STATE.exists():
        LIVE_STATE.parent.mkdir(parents=True, exist_ok=True)
        try:
            reg = load_registry()
            cur = reg.get("default") or next(iter(reg.get("models", {})), "")
        except Exception:
            cur = ""
        save_state({"current": cur})
    try:
        return json.loads(LIVE_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"current": ""}


def save_state(state: dict) -> None:
    LIVE_STATE.parent.mkdir(parents=True, exist_ok=True)
    LIVE_STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Host capability detection
# ---------------------------------------------------------------------------

def total_ram_gb() -> int:
    """Total physical RAM on this machine, in GB (rounded down). Uses
    sysctl on macOS; falls back to 16 for unknown platforms."""
    try:
        out = subprocess.check_output(
            ["sysctl", "-n", "hw.memsize"],
            text=True, stderr=subprocess.DEVNULL,
        )
        return int(out.strip()) // (1024 ** 3)
    except Exception:
        # Linux could parse /proc/meminfo here when we extend support.
        return 16


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def _model_entry(registry: dict, cute: str) -> dict:
    models = registry.get("models", {})
    if cute in models:
        return models[cute]
    # Legacy / accidental uppercase forms.
    for key, entry in models.items():
        if key.lower() == cute.lower() or entry.get("cute_name", "").upper() == cute.upper():
            return entry
    raise KeyError(f"unknown model cute-name: {cute!r}")


def resolve(cute: str | None = None) -> dict:
    """Merge registry + state + filesystem into one per-model view. If
    `cute` is None, uses the live state's current. Returns:

        {
          "cute": "g40-04", "label": ..., "filename": ..., "url": ...,
          "path": "<abs path or None if not downloaded>",
          "installed": bool,
          "disk_gb_approx": ..., "ram_gb_recommended_min": ...,
          "ctx_max": ..., "ctx_recommended": <int>,
          "spec_args": "<llama-server speculative-decoding flags, or ''>",
          "spec_min_release": <int llama.cpp b-release required, 0 if n/a>,
        }
    """
    registry = load_registry()
    state = load_state()
    if cute is None:
        cute = state.get("current") or registry.get("default") or ""
    entry = _model_entry(registry, cute)
    gguf = WEIGHTS_DIR / entry["gguf_filename"]
    return {
        "cute": cute,
        "label": entry.get("label", cute),
        "filename": entry["gguf_filename"],
        "url": entry["gguf_url"],
        "path": str(gguf) if gguf.is_file() else None,
        "installed": gguf.is_file(),
        "disk_gb_approx": entry.get("disk_gb_approx"),
        "ram_gb_recommended_min": entry.get("ram_gb_recommended_min"),
        "ctx_max": entry.get("ctx_max"),
        "ctx_recommended": recommend_ctx(entry, total_ram_gb()),
        "spec_args": spec_args(entry),
        "spec_min_release": int((entry.get("mtp") or {}).get("llama_cpp_min_release", 0)),
    }


def spec_args(model_entry: dict) -> str:
    """llama-server flags for MTP speculative decoding, from the entry's
    optional 'mtp' block. Empty string when the model has no MTP heads."""
    mtp = model_entry.get("mtp") or {}
    if not mtp.get("spec_type"):
        return ""
    args = ["--spec-type", str(mtp["spec_type"])]
    if mtp.get("spec_draft_n_max"):
        args += ["--spec-draft-n-max", str(mtp["spec_draft_n_max"])]
    return " ".join(args)


def llama_release(binary: str = "llama-server") -> int:
    """Numeric b-release of the installed llama.cpp ('version: 9200 (…)'
    → 9200). 0 when the binary is missing or the output is unparseable."""
    try:
        out = subprocess.run(
            [binary, "--version"],
            capture_output=True, text=True, timeout=10,
        )
        m = re.search(r"^version:\s*(\d+)", out.stdout + out.stderr, re.M)
        return int(m.group(1)) if m else 0
    except Exception:
        return 0


def spec_flags(info: dict, binary: str = "llama-server") -> list[str]:
    """Speculative-decoding argv for a resolve()d model, gated on the
    installed llama.cpp release (older builds reject the unknown flags at
    startup). Empty when the model has no MTP heads or the build is too
    old."""
    if not info.get("spec_args"):
        return []
    if llama_release(binary) < int(info.get("spec_min_release") or 0):
        return []
    return str(info["spec_args"]).split()


def recommend_ctx(model_entry: dict, ram_gb: int) -> int:
    """Pick a context window based on total host RAM. Per-model tiers in
    the registry; falls back to tiered defaults for unknown entries."""
    tiers = model_entry.get("ctx_defaults") or {}
    if ram_gb >= 64:
        return int(tiers.get("gte_64gb", 65536))
    if ram_gb >= 32:
        return int(tiers.get("gte_32gb", 32768))
    if ram_gb >= 16:
        return int(tiers.get("gte_16gb", 16384))
    return int(tiers.get("lt_16gb", 8192))


def all_models_view() -> list[dict]:
    """Return resolve(cute) for every model in the registry, in registry
    order. Handy for the UI."""
    reg = load_registry()
    out: list[dict] = []
    for cute in reg.get("models", {}).keys():
        try:
            out.append(resolve(cute))
        except KeyError:
            continue
    return out


# ---------------------------------------------------------------------------
# CLI (used by llama_server.sh)
# ---------------------------------------------------------------------------

def _cli_params(args: argparse.Namespace) -> int:
    info = resolve(args.cute)
    if not info["installed"]:
        print(f"model {info['cute']} not installed at expected path", file=sys.stderr)
        return 2
    # Shell-sourceable (values quoted: labels have spaces/parens, and
    # SPEC_ARGS is a flag string the server script word-splits itself):
    print(f"MODEL_PATH={shlex.quote(str(info['path']))}")
    print(f"CTX_RECOMMENDED={info['ctx_recommended']}")
    print(f"MODEL_CUTE={shlex.quote(info['cute'])}")
    print(f"MODEL_LABEL={shlex.quote(str(info['label']))}")
    print(f"SPEC_ARGS={shlex.quote(info['spec_args'])}")
    print(f"SPEC_MIN_RELEASE={info['spec_min_release']}")
    return 0


def _cli_resolve_path(args: argparse.Namespace) -> int:
    info = resolve(args.cute)
    if not info["installed"]:
        print(f"model {info['cute']} not installed", file=sys.stderr)
        return 2
    print(info["path"])
    return 0


def _cli_list(_args: argparse.Namespace) -> int:
    for info in all_models_view():
        mark = "✓" if info["installed"] else " "
        size = f"{info['disk_gb_approx']:.1f} GB" if info["disk_gb_approx"] else "?"
        print(f"{mark} {info['cute']:<6}  {info['label']:<25}  {size:<8}  ctx≈{info['ctx_recommended']}")
    return 0


def _cli_set_current(args: argparse.Namespace) -> int:
    try:
        resolve(args.cute)
    except KeyError as e:
        print(str(e), file=sys.stderr)
        return 2
    state = load_state()
    state["current"] = args.cute
    save_state(state)
    print(args.cute)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="enough.models")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("params", help="shell-sourceable resolve of a model")
    p.add_argument("--cute", default=None)
    p.set_defaults(fn=_cli_params)

    p = sub.add_parser("resolve-path", help="print the gguf path only")
    p.add_argument("--cute", default=None)
    p.set_defaults(fn=_cli_resolve_path)

    p = sub.add_parser("list", help="list all registered models + install state")
    p.set_defaults(fn=_cli_list)

    p = sub.add_parser("set-current", help="set the live 'current' model")
    p.add_argument("cute")
    p.set_defaults(fn=_cli_set_current)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
