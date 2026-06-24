"""adorn package entry point for `python -m adorn`."""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
