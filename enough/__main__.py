"""CLI entry point: `enough [--dir PATH] [--port N] [--llm-url URL]`."""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

from . import __version__


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="enough",
        description="A paradigmless personal computer harness powered by a local LLM.",
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path.cwd(),
        help="Project directory (default: current working directory).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=3456,
        help="Port for the enough web server (default: 3456).",
    )
    parser.add_argument(
        "--llm-url",
        default="http://localhost:8080",
        help="Base URL of the llama-server (default: http://localhost:8080).",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open a browser window on launch.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"enough {__version__}",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # Late imports so --help and --version don't require the full dep tree.
    from .llm import check_llm_reachable
    from .server import run
    from .skeleton import ensure_skeleton

    project_dir = args.dir.resolve()
    project_dir.mkdir(parents=True, exist_ok=True)

    ok, why = check_llm_reachable(args.llm_url)
    if not ok:
        print(f"error: cannot reach llama-server at {args.llm_url}", file=sys.stderr)
        print(f"       {why}", file=sys.stderr)
        print("", file=sys.stderr)
        print("start it with something like:", file=sys.stderr)
        print("  llama-server -m <path-to.gguf> --host 127.0.0.1 --port 8080 -ngl 99 -c 8192 --jinja", file=sys.stderr)
        print("(or run ./llama_server.sh start from the enough repo root)", file=sys.stderr)
        return 2

    created = ensure_skeleton(project_dir)
    if created:
        print(f"created .rness/ skeleton in {project_dir}")

    url = f"http://127.0.0.1:{args.port}"
    print(f"enough {__version__} — serving {project_dir}")
    print(f"  web:   {url}")
    print(f"  llm:   {args.llm_url}")
    print("  ctrl-c to stop")

    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    run(
        project_dir=project_dir,
        port=args.port,
        llm_url=args.llm_url,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
