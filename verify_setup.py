#!/usr/bin/env python3
"""Setup entry point kept separate so setup and course verification agree."""

from run_lab import main


if __name__ == "__main__":
    raise SystemExit(main(["verify"]))
