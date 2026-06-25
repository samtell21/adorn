# src/adorn/cli.py
"""adorn command-line entry point."""
import argparse
import os
import sys
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
    p_new.add_argument("--saturation", type=float, default=None,
                       help="hue saturation floor 0..1 (default: manifest [mood] or 0.0)")
    p_new.add_argument("--scheme", default="default")
    p_recompile = sub.add_parser("recompile", help="recompile palette from wallpaper")
    p_recompile.add_argument("name")
    p_recompile.add_argument("--saturation", type=float, default=None,
                             help="hue saturation floor 0..1")
    p_render = sub.add_parser("render", help="re-derive apps/ fragments from palette+overrides")
    p_render.add_argument("name")
    p_preview = sub.add_parser("preview", help="print a theme's palette as swatches")
    p_preview.add_argument("name")
    sub.add_parser("init", help="scaffold a starter ~/.config/adorn config")

    args = parser.parse_args(argv)
    root = Path(args.root) if args.root else DEFAULT_ROOT

    try:
        if args.command == "list":
            commands.cmd_list(root)
        elif args.command == "current":
            commands.cmd_current(root)
        elif args.command == "apply":
            commands.cmd_apply(root, args.name)
        elif args.command == "new":
            commands.cmd_new(root, args.name, args.wallpaper,
                             do_apply=not args.no_apply, saturation_floor=args.saturation,
                             scheme=args.scheme)
        elif args.command == "render":
            commands.cmd_render(root, args.name)
        elif args.command == "recompile":
            commands.cmd_recompile(root, args.name, saturation_floor=args.saturation)
        elif args.command == "preview":
            commands.cmd_preview(root, args.name)
        elif args.command == "init":
            commands.cmd_init(root)
    except (FileNotFoundError, FileExistsError, ValueError) as e:
        print(f"adorn: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
