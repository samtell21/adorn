"""adorn command-line entry point (stub; subcommands added in Task 10)."""
import argparse

from . import __version__


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="adorn",
        description="Automated Desktop Ornamentation & Recoloring eNgine",
    )
    parser.add_argument("--version", action="version", version=f"adorn {__version__}")
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
