"""CLI entry point: `enough [--dir PATH | --home] [--port N] [--llm-url URL]`."""

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
    # Default None, not `Path.cwd()`, so `main()` can tell "the user asked
    # for this folder" from "nobody said" — which is the whole of the --home
    # exclusivity check. The cwd default is applied in main() instead.
    parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="Project directory (default: current working directory).",
    )
    parser.add_argument(
        "--home",
        action="store_true",
        help="Open the enough home screen instead of a project: the list of "
             "every folder enough has ever set up, with no project loaded. "
             "Mutually exclusive with --dir.",
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


def _open_loader(url: str) -> None:
    """Open a local file:// loader page that polls `url` and redirects when
    uvicorn is listening. Without this, the browser hits the port before
    uvicorn binds and shows its native "can't reach this site" page until the
    user manually refreshes."""
    loader_path = Path(__file__).parent / "static" / "loader.html"
    loader_url = (
        loader_path.resolve().as_uri()
        + "?target=" + urllib.parse.quote(url, safe="")
    )
    try:
        webbrowser.open(loader_url)
    except Exception:  # noqa: BLE001
        pass


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # Late imports so --help and --version don't require the full dep tree.
    from .llm import check_llm_reachable
    from .server import run
    from .skeleton import ensure_skeleton

    if args.home:
        if args.dir is not None:
            print("error: --home and --dir are mutually exclusive.", file=sys.stderr)
            print("       --home opens the launch screen, which has no project; "
                  "--dir opens one.", file=sys.stderr)
            return 2
        url = f"http://127.0.0.1:{args.port}"
        print(f"enough {__version__} — home (no project open)")
        print(f"  web:   {url}")
        print("  ctrl-c to stop")
        if not args.no_browser:
            _open_loader(url)
        # No project, so no llama supervision, no broker, no session — that
        # part `create_app(home=True)` enforces for itself. `supervise` and
        # `--llm-url` are still passed through as the *user's* intent, so that
        # opening a project from here re-execs with the flags they launched
        # with rather than with home's own emptiness.
        return run(
            project_dir=Path.cwd(),
            port=args.port,
            llm_url=args.llm_url,
            max_tool_iters=args.max_tool_iters,
            supervise=not args.no_supervise,
            home=True,
        )

    project_dir = (args.dir or Path.cwd()).resolve()
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
        _open_loader(url)

    # The return value is the process's exit status: 42 means "the user asked
    # for another project (or for home) — the handoff file says which", which
    # is what the desktop shell watches for. Every other exit is unchanged.
    return run(
        project_dir=project_dir,
        port=args.port,
        llm_url=args.llm_url,
        max_tool_iters=args.max_tool_iters,
        supervise=not args.no_supervise,
    )


if __name__ == "__main__":
    raise SystemExit(main())
