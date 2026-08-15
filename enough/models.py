"""Model registry helpers: which GGUFs are supported, where they live, how
much RAM they want, and a RAM-aware context-window recommender.

- Registry template ships at `<install>/defaults/models.json` (shipped, git).
- Live state at `~/enough/config/models.json` — currently just
  `{"current": "<cute-name>"}`. Seeded from template on first access.
- Installed state is derived from whether the model's GGUF file exists at
  `~/enough/weights/<gguf_filename>`. No install-state file needed.
- Two env hooks, both for scratch/QA installs: `ENOUGH_WEIGHTS_DIR` moves the
  weights dir, `ENOUGH_MODELS_URL_BASE` rebases every download URL onto a
  local stub server. Neither is a user-facing setting.
- `find_llama_server()` is the ONE place the llama-server binary is located:
  `$ENOUGH_LLAMA_SERVER` → `~/enough/bin/llama-server` → PATH. Three
  installers depend on that order — the desktop app points rung 1 at its
  bundled sidecar, the Linux installer owns rung 2, Homebrew is rung 3 —
  so `supervisor._launch` and every release-probing helper below resolve
  through it rather than reaching for `shutil.which` themselves.

Also exposes a small CLI:
    python -m enough.models params [--cute NAME]
    python -m enough.models resolve-path [--cute NAME]
    python -m enough.models install-menu [--json]

…the first two of which `llama_server.sh` uses to turn a cute name into a
concrete model path + context window; the third is what `bootstrap.sh`
and the in-app model manager render as a per-model install picker.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("enough.models")


def _weights_dir_default() -> Path:
    """~/enough/weights, or ENOUGH_WEIGHTS_DIR when that's set — the test/dev
    hook that lets a scratch QA server download stub GGUFs without planting
    fakes in the real install (mirrors ENOUGH_WIKISINK_CONFIG /
    ENOUGH_CACHEAWL_ROOT). Read once at import: a server's environment
    doesn't change under it, and the suites monkeypatch WEIGHTS_DIR itself."""
    env = os.environ.get("ENOUGH_WEIGHTS_DIR")
    return Path(env).expanduser() if env else Path.home() / "enough" / "weights"


def _live_state_default() -> Path:
    """~/enough/config/models.json, or ENOUGH_LIVE_STATE when that's set —
    the companion hook to ENOUGH_WEIGHTS_DIR: a scratch QA server's model
    switches and ctx overrides land in its own state file instead of the
    real install's. Same read-once contract as _weights_dir_default."""
    env = os.environ.get("ENOUGH_LIVE_STATE")
    return Path(env).expanduser() if env else Path.home() / "enough" / "config" / "models.json"


INSTALL_ROOT = Path(__file__).resolve().parents[1]


def _registry_template_default() -> Path:
    """<install>/defaults/models.json, or ENOUGH_MODELS_REGISTRY when that's
    set — the third leg of the scratch-QA tripod (weights dir, live state,
    registry): lets a QA server run against a doctored registry (tiny stub
    sizes, artificial release gates) without touching the tracked template.
    Same read-once contract as the other two."""
    env = os.environ.get("ENOUGH_MODELS_REGISTRY")
    return Path(env).expanduser() if env else INSTALL_ROOT / "defaults" / "models.json"


REGISTRY_TEMPLATE = _registry_template_default()
LIVE_STATE = _live_state_default()
WEIGHTS_DIR = _weights_dir_default()
MEMINFO = Path("/proc/meminfo")   # Linux RAM probe; absent on macOS

# QA seam (docs/seven-models-plan.md §5, "Wave 2a"): with
# ENOUGH_MODELS_URL_BASE set, every registry gguf/draft URL is rebased onto
# it BY FILENAME, so a directory of tiny stub files behind any local server
# stands in for huggingface.co with no code change. Env only, read per call.
URL_BASE_ENV = "ENOUGH_MODELS_URL_BASE"

# Feasibility thresholds (see feasibility()). RAM headroom is what keeps
# the machine from swapping mid-generation; disk headroom is what keeps a
# download from filling the volume the user also lives on.
RAM_HEADROOM_GB = 8
DISK_SLACK_FACTOR = 1.2
DISK_HEADROOM_GB = 10
DISK_MIN_SLACK_GB = 2
# Above this total download size, the install menu stops pre-checking a
# model even when the verdict is "good" — a green light is not a reason
# to pull 16 GB nobody asked for.
MENU_DEFAULT_YES_MAX_GB = 8.0


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


def rebase_url(url: str | None, filename: str | None = None) -> str | None:
    """The URL a download should actually fetch: the registry's, unless
    ENOUGH_MODELS_URL_BASE redirects it. A rebase keeps only the LOCAL
    filename — `<base>/<gguf_filename>` — so the stub server is a plain
    directory of files named exactly as they land in the weights dir, with
    no upstream path structure to reproduce. (Not the URL's basename: the
    two differ for the -MTP-marked local names, q35-09 / q36-27.) Falls
    back to the URL basename when no filename is given. Unset (or empty)
    leaves the URL untouched."""
    base = (os.environ.get(URL_BASE_ENV) or "").strip()
    if not base or not url:
        return url
    return f"{base.rstrip('/')}/{filename or url.rsplit('/', 1)[-1]}"


# ---------------------------------------------------------------------------
# Host capability detection
# ---------------------------------------------------------------------------

def total_ram_gb() -> int:
    """Total physical RAM on this machine, in GB (rounded down). Uses
    sysctl on macOS and /proc/meminfo on Linux; falls back to 16 when
    neither answers (unknown platform, or sysctl present but without
    hw.memsize, which is the usual Linux shape)."""
    try:
        out = subprocess.check_output(
            ["sysctl", "-n", "hw.memsize"],
            text=True, stderr=subprocess.DEVNULL,
        )
        return int(out.strip()) // (1024 ** 3)
    except Exception:  # noqa: BLE001
        pass
    try:
        for line in MEMINFO.read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                # "MemTotal:       32611288 kB" — kB, always, per proc(5).
                return int(line.split()[1]) // (1024 ** 2)
    except Exception:  # noqa: BLE001
        pass
    return 16


def free_disk_gb() -> float:
    """Free space on the volume that holds ~/enough/weights, in GB. The
    directory is created if missing — disk_usage needs something to stat,
    and this is where every download lands anyway. 0.0 if even that
    fails (read-only volume, permissions), which reads as "no room" to
    feasibility() rather than silently passing."""
    try:
        WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
        return shutil.disk_usage(WEIGHTS_DIR).free / (1024 ** 3)
    except Exception:  # noqa: BLE001
        return 0.0


def draft_disk_gb(model_entry: dict) -> float:
    """Extra download for a separate MTP draft GGUF. 0.0 for entries with
    no draft file — plain models and the embedded-head MTP builds alike."""
    return float((model_entry.get("mtp") or {}).get("draft_disk_gb_approx") or 0.0)


def feasibility(model_entry: dict) -> dict:
    """Can this machine run — and store — this model? Returns

        {"verdict": "good" | "tight" | "no", "reasons": [<human strings>]}

    RAM and disk are judged separately and the worse verdict wins.
    `reasons` is empty for "good" and otherwise says what falls short, in
    words a user can act on. The download size counts the MTP draft file
    when the entry has one — the user pays for both.

    Thresholds: RAM good at min + 8 GB, tight at min. Disk good at
    1.2x the download plus 10 GB, tight at the download plus 2 GB."""
    ram = total_ram_gb()
    free = free_disk_gb()
    want_ram = int(model_entry.get("ram_gb_recommended_min") or 0)
    size = float(model_entry.get("disk_gb_approx") or 0.0) + draft_disk_gb(model_entry)
    reasons: list[str] = []

    if ram >= want_ram + RAM_HEADROOM_GB:
        ram_verdict = "good"
    elif ram >= want_ram:
        ram_verdict = "tight"
        reasons.append(
            f"wants {want_ram} GB RAM and this machine has {ram} — "
            "it will run, with little left for anything else"
        )
    else:
        ram_verdict = "no"
        reasons.append(f"wants {want_ram} GB RAM, this machine has {ram}")

    if free >= size * DISK_SLACK_FACTOR + DISK_HEADROOM_GB:
        disk_verdict = "good"
    elif free >= size + DISK_MIN_SLACK_GB:
        disk_verdict = "tight"
        reasons.append(
            f"needs ~{size:.0f} GB free and you have {free:.0f} — "
            "it fits with almost nothing to spare"
        )
    else:
        disk_verdict = "no"
        reasons.append(f"needs ~{size:.0f} GB free, you have {free:.0f}")

    rank = {"good": 0, "tight": 1, "no": 2}
    verdict = max(ram_verdict, disk_verdict, key=lambda v: rank[v])
    return {"verdict": verdict, "reasons": reasons}


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
          "llama_cpp_min_release": <int hard gate on loading at all, 0 if none>,
          "draft_filename": ..., "draft_url": ...,        (None without MTP draft)
          "draft_path": "<abs path or None if not downloaded>",
          "draft_installed": bool,
          "draft_disk_gb_approx": <float or None>,
          "feasibility": {"verdict": ..., "reasons": [...]},
        }

    `installed` reflects the MAIN gguf only. A model whose separate MTP
    draft file is missing is fully installed and launches plain — the
    draft is a speed bonus, never a requirement. Both URLs come back
    through rebase_url(), so a scratch install pointed at a stub server
    downloads stubs.
    """
    registry = load_registry()
    state = load_state()
    if cute is None:
        cute = state.get("current") or registry.get("default") or ""
    entry = _model_entry(registry, cute)
    gguf = WEIGHTS_DIR / entry["gguf_filename"]
    mtp = entry.get("mtp") or {}
    draft_name = mtp.get("draft_gguf_filename")
    draft = (WEIGHTS_DIR / draft_name) if draft_name else None
    return {
        "cute": cute,
        "label": entry.get("label", cute),
        "filename": entry["gguf_filename"],
        "url": rebase_url(entry["gguf_url"], entry["gguf_filename"]),
        "path": str(gguf) if gguf.is_file() else None,
        "installed": gguf.is_file(),
        "disk_gb_approx": entry.get("disk_gb_approx"),
        "ram_gb_recommended_min": entry.get("ram_gb_recommended_min"),
        "ctx_max": entry.get("ctx_max"),
        "ctx_recommended": recommend_ctx(entry, total_ram_gb()),
        "spec_args": spec_args(entry),
        "spec_min_release": int(mtp.get("llama_cpp_min_release", 0)),
        "llama_cpp_min_release": int(entry.get("llama_cpp_min_release") or 0),
        "draft_filename": draft_name,
        "draft_url": rebase_url(mtp.get("draft_gguf_url"), draft_name),
        "draft_path": str(draft) if draft and draft.is_file() else None,
        "draft_installed": bool(draft and draft.is_file()),
        "draft_disk_gb_approx": mtp.get("draft_disk_gb_approx"),
        "feasibility": feasibility(entry),
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


LLAMA_SERVER_ENV = "ENOUGH_LLAMA_SERVER"


def _enough_bin_dir() -> Path:
    """`~/enough/bin` — where the Linux installer drops the prebuilt
    llama.cpp release (docs/linux-plan.md §3.2). Derived from `Path.home()`,
    so a scratch `$HOME` moves it with everything else."""
    return Path.home() / "enough" / "bin"


def find_llama_server() -> str | None:
    """Locate the `llama-server` binary. Returns None when there isn't one.

    ONE lookup order for three platforms (docs/tauri-plan.md §4,
    docs/linux-plan.md §3.2):

    1. ``$ENOUGH_LLAMA_SERVER`` — an explicit path. The desktop shell points
       this at the sidecar inside enough.app; a power user can point it at
       any build they like.
    2. ``~/enough/bin/llama-server`` — where the Linux installer puts the
       prebuilt release archive's binary.
    3. ``PATH`` — Homebrew on macOS, distro packages / manual installs
       elsewhere.

    An override that doesn't resolve falls through to the next rung rather
    than failing hard (a stale env var in a shell profile shouldn't make a
    perfectly good brew install unreachable), but it says so in the log —
    silently running a *different* llama.cpp than the one you pointed at is
    the confusing failure, so it must at least be visible.

    Read per call, not cached at import: `PATH` and the env var are exactly
    the things a QA harness or a sidecar-spawning shell changes underneath a
    long-lived process, and one `which` is not worth memoizing.
    """
    env = os.environ.get(LLAMA_SERVER_ENV)
    if env:
        cand = Path(env).expanduser()
        if cand.is_file() and os.access(cand, os.X_OK):
            return str(cand)
        log.warning(
            "%s points at %s, which isn't an executable file — falling back "
            "to ~/enough/bin then PATH", LLAMA_SERVER_ENV, env,
        )
    cand = _enough_bin_dir() / "llama-server"
    if cand.is_file() and os.access(cand, os.X_OK):
        return str(cand)
    return shutil.which("llama-server")


def llama_release(binary: str | None = None) -> int:
    """Numeric b-release of the installed llama.cpp ('version: 9200 (…)'
    → 9200). 0 when the binary is missing or the output is unparseable.

    `binary=None` means "look it up" via `find_llama_server()`; callers that
    already resolved a path (the supervisor's launch path) pass it in so the
    version they gate on is the version they run."""
    if binary is None:
        binary = find_llama_server()
        if binary is None:
            return 0
    try:
        out = subprocess.run(
            [binary, "--version"],
            capture_output=True, text=True, timeout=10,
        )
        m = re.search(r"^version:\s*(\d+)", out.stdout + out.stderr, re.M)
        return int(m.group(1)) if m else 0
    except Exception:
        return 0


def release_gate(info: dict, binary: str | None = None) -> str | None:
    """The HARD per-model llama.cpp gate: None when the installed build
    can load this model at all, else a user-facing sentence explaining
    what to upgrade. Models without a top-level `llama_cpp_min_release`
    are never gated.

    This is the opposite of spec_flags()' soft gate — a too-old build
    there just loses speculative decoding, whereas here it can't load the
    architecture, and llama-server would fail with an opaque tensor error
    instead of something the user can act on."""
    need = int(info.get("llama_cpp_min_release") or 0)
    if need <= 0:
        return None
    have = llama_release(binary)
    if have >= need:
        return None
    got = f"b{have}" if have else "no llama.cpp on PATH"
    return (
        f"{info.get('label') or info.get('cute') or 'this model'} needs "
        f"llama.cpp b{need} or newer ({got}). "
        "run `brew upgrade llama.cpp`, then try again."
    )


def spec_flags(info: dict, binary: str | None = None) -> list[str]:
    """Speculative-decoding argv for a resolve()d model, gated on the
    installed llama.cpp release (older builds reject the unknown flags at
    startup). Empty when the model has no MTP heads, the build is too
    old, or the model's separate draft GGUF isn't downloaded — the
    draft-mtp spec type is meaningless without the tensors to draft from,
    wherever they live."""
    if not info.get("spec_args"):
        return []
    if info.get("draft_filename") and not info.get("draft_path"):
        return []
    if llama_release(binary) < int(info.get("spec_min_release") or 0):
        return []
    return str(info["spec_args"]).split()


def draft_flags(info: dict, binary: str | None = None) -> list[str]:
    """Draft-file argv for models whose MTP head ships as a SEPARATE GGUF
    (the qwen-3.8 shape) rather than embedded in the main file (q35/q36).
    Empty unless the draft file is actually on disk AND the spec flags
    are themselves active — `--spec-draft-model` without
    `--spec-type draft-mtp` would set up ordinary draft-model speculation,
    which is not what an MTP head is. A missing draft file means a plain
    launch, never an error."""
    if not info.get("draft_path"):
        return []
    if not spec_flags(info, binary):
        return []
    return ["--spec-draft-model", str(info["draft_path"])]


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


def install_menu_rows() -> list[dict]:
    """One row per registry model for the selective-install picker: what
    it is, what the download really costs (main GGUF + any MTP draft),
    whether this machine can run it, and whether its y/n prompt should
    come pre-answered yes.

    `default_yes` is deliberately conservative — only a not-yet-installed
    model with a "good" verdict AND a small download gets pre-checked.
    Everything else the user opts into on purpose."""
    reg = load_registry()
    rows: list[dict] = []
    for cute, entry in (reg.get("models") or {}).items():
        draft_gb = draft_disk_gb(entry)
        size = float(entry.get("disk_gb_approx") or 0.0) + draft_gb
        verdict = feasibility(entry)
        installed = (WEIGHTS_DIR / entry["gguf_filename"]).is_file()
        rows.append({
            "cute": cute,
            "label": entry.get("label", cute),
            "size_gb": round(size, 1),
            "disk_gb_approx": entry.get("disk_gb_approx"),
            "draft_disk_gb_approx": draft_gb or None,
            "installed": installed,
            "verdict": verdict["verdict"],
            "reasons": verdict["reasons"],
            "llama_cpp_min_release": int(entry.get("llama_cpp_min_release") or 0),
            "default_yes": (
                not installed
                and verdict["verdict"] == "good"
                and size <= MENU_DEFAULT_YES_MAX_GB
            ),
        })
    return rows


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
    # DRAFT_PATH is a path, so it gets its own var rather than riding in
    # SPEC_ARGS (which the shell word-splits). Empty when the model has
    # no separate draft file or it isn't downloaded.
    print(f"DRAFT_PATH={shlex.quote(info['draft_path'] or '')}")
    print(f"MIN_RELEASE={info['llama_cpp_min_release']}")
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


_VERDICT_GLYPH = {"good": "✓", "tight": "~", "no": "✗"}


def _cli_install_menu(args: argparse.Namespace) -> int:
    rows = install_menu_rows()
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    for r in rows:
        note = "already installed" if r["installed"] else "; ".join(r["reasons"])
        size = f"{r['size_gb']:.1f} GB"
        if r["draft_disk_gb_approx"]:
            size += f" (incl. {r['draft_disk_gb_approx']:.1f} draft)"
        line = f"{_VERDICT_GLYPH[r['verdict']]} {r['cute']:<7} {r['label']:<22} {size:<24}"
        print(f"{line}{note}".rstrip())
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

    p = sub.add_parser(
        "install-menu",
        help="per-model install picker: size + this machine's feasibility verdict",
    )
    p.add_argument("--json", action="store_true", help="machine-readable rows")
    p.set_defaults(fn=_cli_install_menu)

    p = sub.add_parser("set-current", help="set the live 'current' model")
    p.add_argument("cute")
    p.set_defaults(fn=_cli_set_current)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
