"""Allow the modular CLI to run with ``python -m cli``."""

from .app import main


if __name__ == "__main__":
    raise SystemExit(main())
