"""Every `ENOUGH_*` environment variable, and how a scratch run sets each one.

One list, read by both halves of the rule that no test and no scratch server touches the person's real state:
`tests/conftest.py` (every test, and under every fixture of any scope a session floor) and
`scripts/smoke_boot.py`'s `build_env()` (the servers the pre-commit suite and the UI check boot).
`tests/test_seams.py` fails when a module under `enough/` reads an `ENOUGH_*` variable this module does not name,
and when this module names one nothing reads.

Nothing in the app imports this module; each module reads its own variables where it uses them. Stdlib only.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Mapping

INSTALL_ROOT = Path(__file__).resolve().parents[1]

# Seams that name a path, each mapped to its place under a scratch root. A scratch run points every one of them
# there, so nothing it writes or reads can be the person's own.
PATH_SEAMS: dict[str, str] = {
    # The model layer (models.py): the weights, the live model state, and the registry, which `scratch_env`
    # fills with a copy of defaults/models.json so a test that rewrites it cannot touch the checkout.
    "ENOUGH_WEIGHTS_DIR": "weights",
    "ENOUGH_LIVE_STATE": "live-models.json",
    "ENOUGH_MODELS_REGISTRY": "models.json",
    # The stores.
    "ENOUGH_CANON_ROOT": "canon",
    "ENOUGH_INFOWORLD_ROOT": "no-infoworld",
    "ENOUGH_WIKISINK_CONFIG": "wikisink.json",
    "ENOUGH_UI_CONFIG": "ui.json",
    "ENOUGH_EXTRAS_STATE": "extras.json",
    # The home screen's project registry; the handoff file and desktop.json are derived from its folder.
    "ENOUGH_PROJECTS_STATE": "config/projects.json",
    # The user-global readvisors (0.3.5): without it a global install_readvisor files into ~/enough/readvisors/.
    "ENOUGH_READVISORS_ROOT": "readvisors",
    # FEED (0.4.1): the built dictionary and the person's own entries; and its source, pointed at nothing, so a
    # booted app does not start a 380 MB build from reflib/dict. A rig that wants the build (the smoke boot, a
    # dictionary test) points the source at the checkout's reflib/dict or at a fixture of its own.
    "ENOUGH_DICT_ROOT": "dict",
    "ENOUGH_DICT_SOURCE": "no-dict-source",
    # DocOES (0.4.4): the built doc volumes.
    "ENOUGH_DOCS_ROOT": "docoes",
    # Thym (0.5.0): runs (plans, traces, candidates, outputs).
    "ENOUGH_THYM_ROOT": "thym",
    # The specifications synced from cosmoes.org (0.5.4).
    "ENOUGH_SPECS_ROOT": "specs",
}

# Seams that name a service or a switch, held at a fixed value: no scratch run may reach huggingface.co or
# cosmoes.org (port 1 never listens, so a stray request fails at once instead of downloading), and the launch
# check of the specifications is off. A test of the check or of a download sets them for itself.
FIXED_SEAMS: dict[str, str] = {
    "ENOUGH_MODELS_URL_BASE": "http://127.0.0.1:1/weights",
    "ENOUGH_COSMOES_BASE": "http://127.0.0.1:1",
    "ENOUGH_SPECS_SYNC": "0",
}

# Seams that change behaviour rather than location, cleared: a developer who has one exported would otherwise get
# a different run than CI. A rig that needs one sets it after `scratch_env` (the smoke boot turns the desktop gate
# on with a token of its own and points the llama-server override at a file that does not exist; the lookup
# ladder's and the shutdown gate's tests set theirs). The ones marked "shell" are read by the desktop shell or
# the shell scripts and passed on to the backend, not read under enough/.
BEHAVIOUR_SEAMS: tuple[str, ...] = (
    "ENOUGH_LLAMA_SERVER",       # models.find_llama_server's first rung, a path; absent = ~/enough/bin, then PATH
    "ENOUGH_DESKTOP",            # the desktop capability gate (server.py, convert.py)
    "ENOUGH_DESKTOP_TOKEN",      # the shutdown route's token (server.py)
    "ENOUGH_DESKTOP_UV",         # the uv the shell spawned the backend with (convert.py)
    "ENOUGH_DESKTOP_CODE",       # shell: which checkout the desktop app runs
    "ENOUGH_DESKTOP_LLM_URL",    # shell: the llama-server URL the desktop app hands the backend
    "ENOUGH_VULKAN_ICD_DIRS",    # shell: llama_server.sh's Vulkan driver folders
    "ENOUGH_REPO_URL",           # shell: bootstrap.sh's clone source
)

# Variables read under enough/ that are plain flags, naming no path and no service, so they need no seam. Each
# entry says why. Empty today: every variable the app reads is one of the seams above.
FLAGS_WITHOUT_SEAM: dict[str, str] = {}


def every_name() -> set[str]:
    """Every variable this module accounts for."""
    return set(PATH_SEAMS) | set(FIXED_SEAMS) | set(BEHAVIOUR_SEAMS) | set(FLAGS_WITHOUT_SEAM)


def scratch_values(scratch: Path) -> dict[str, str]:
    """The value of every path and fixed seam for a run whose scratch root is `scratch`. Writes nothing."""
    out = {var: str(Path(scratch) / rel) for var, rel in PATH_SEAMS.items()}
    out.update(FIXED_SEAMS)
    return out


def fill_registry(scratch: Path) -> Path:
    """Copy the shipped model registry to where `ENOUGH_MODELS_REGISTRY` points under `scratch`."""
    dest = Path(scratch) / PATH_SEAMS["ENOUGH_MODELS_REGISTRY"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(INSTALL_ROOT / "defaults" / "models.json", dest)
    return dest


def scratch_env(scratch: Path, base: Mapping[str, str] | None = None) -> dict[str, str]:
    """`base` (default: empty) with every path and fixed seam pointed under `scratch`, the registry copied there,
    and every behaviour seam removed. `$HOME` is the caller's: the half of enough's state with no seam of its own
    is reached only through it."""
    env = dict(base or {})
    for var in BEHAVIOUR_SEAMS:
        env.pop(var, None)
    env.update(scratch_values(scratch))
    fill_registry(scratch)
    return env
