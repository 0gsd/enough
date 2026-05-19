"""CLI entry point: `enough [--dir PATH] [--port N] [--llm-url URL]`."""

from __future__ import annotations

import argparse
import sys
import urllib.parse
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
        "--max-tool-iters",
        type=int,
        default=50,
        help="Cap on tool invocations per user turn (default: 50). "
             "Prevents runaway tool loops; raise for heavier multi-step work.",
    )
    parser.add_argument(
        "--no-supervise",
        action="store_true",
        help="Don't supervise llama-server. Useful if you want to run "
             "llama-server manually via llama_server.sh. In that mode the "
             "in-UI model switcher is disabled.",
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

    # Refuse to launch inside the install directory (~/enough) or anywhere
    # beneath it. Creating a rness/ there would write symlinks pointing at
    # global defaults that are in the same tree — confusing at best,
    # corrupting at worst. Keep the install immutable to enough itself.
    install_dir = Path.home() / "enough"
    try:
        install_resolved = install_dir.resolve(strict=False)
        project_dir.relative_to(install_resolved)
    except ValueError:
        pass  # project_dir is NOT under ~/enough/ — fine
    else:
        print(
            f"error: {project_dir} is inside the enough install directory "
            f"({install_resolved}).",
            file=sys.stderr,
        )
        print(
            "       enough refuses to create a rness/ here because its files would "
            "collide with global defaults.",
            file=sys.stderr,
        )
        print(
            "       cd to any other directory and run `enough` there — e.g. "
            "`mkdir ~/my-project && cd $_ && enough`.",
            file=sys.stderr,
        )
        return 2

    if args.no_supervise:
        ok, why = check_llm_reachable(args.llm_url)
        if not ok:
            print(f"error: cannot reach llama-server at {args.llm_url}", file=sys.stderr)
            print(f"       {why}", file=sys.stderr)
            print("", file=sys.stderr)
            print("since you passed --no-supervise, enough won't launch it for you.", file=sys.stderr)
            print("start it yourself with:", file=sys.stderr)
            print("  MODEL=<cute-name> ~/enough/llama_server.sh start", file=sys.stderr)
            print("or drop --no-supervise to let enough launch and manage llama-server.", file=sys.stderr)
            return 2

    created = ensure_skeleton(project_dir)
    if created:
        print(f"created rness/ skeleton in {project_dir}")
    else:
        # Existing project — check whether ~/enough/defaults/ has gained
        # any new shared defaults this rness/ is missing. Just notify;
        # the user opts in via /update-enough in the chat.
        from .skeleton import detect_drift
        missing = detect_drift(project_dir)
        if missing:
            print(f"  ! {len(missing)} new default(s) available from ~/enough/defaults/:")
            for _src, dst, _mode in missing:
                print(f"      - {dst}")
            print(f"    type /update-enough in the chat box to apply, or ignore.")

    url = f"http://127.0.0.1:{args.port}"
    print(f"enough {__version__} — serving {project_dir}")
    print(f"  web:   {url}")
    print(f"  llm:   {args.llm_url}")
    print("  ctrl-c to stop")

    if not args.no_browser:
        # Open a local file:// loader page that polls `url` and redirects
        # when uvicorn is listening. Without this, the browser hits the
        # port before uvicorn binds and shows its native "can't reach
        # this site" page until the user manually refreshes.
        loader_path = Path(__file__).parent / "static" / "loader.html"
        loader_url = (
            loader_path.resolve().as_uri()
            + "?target=" + urllib.parse.quote(url, safe="")
        )
        try:
            webbrowser.open(loader_url)
        except Exception:
            pass

    run(
        project_dir=project_dir,
        port=args.port,
        llm_url=args.llm_url,
        max_tool_iters=args.max_tool_iters,
        supervise=not args.no_supervise,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
