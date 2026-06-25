# src/adorn/cli.py
"""adorn command-line entry point."""
import argparse
import os
from pathlib import Path

from . import __version__, commands

DEFAULT_ROOT = Path(os.path.expanduser("~/.config/adorn"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="adorn",
        description="Automated Desktop Ornamentation & Recoloring eNgine",
    )
    parser.add_argument("--root", help="catalog root (default ~/.config/adorn)")
    parser.add_argument("--version", action="version", version=f"adorn {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="list themes")
    sub.add_parser("current", help="show active theme")
    p_apply = sub.add_parser("apply", help="apply a theme")
    p_apply.add_argument("name")
    p_new = sub.add_parser("new", help="create a theme from a wallpaper")
    p_new.add_argument("name")
    p_new.add_argument("wallpaper")
    p_new.add_argument("--no-apply", action="store_true")
    p_recompile = sub.add_parser("recompile", help="recompile palette from wallpaper")
    p_recompile.add_argument("name")
    p_preview = sub.add_parser("preview", help="print a theme's palette as swatches")
    p_preview.add_argument("name")

    args = parser.parse_args(argv)
    root = Path(args.root) if args.root else DEFAULT_ROOT

    if args.command == "list":
        commands.cmd_list(root)
    elif args.command == "current":
        commands.cmd_current(root)
    elif args.command == "apply":
        commands.cmd_apply(root, args.name)
    elif args.command == "new":
        commands.cmd_new(root, args.name, args.wallpaper, do_apply=not args.no_apply)
    elif args.command == "recompile":
        commands.cmd_recompile(root, args.name)
    elif args.command == "preview":
        commands.cmd_preview(root, args.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
