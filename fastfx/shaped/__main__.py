from __future__ import annotations

import argparse
from pathlib import Path

from .core import load, write


def main() -> int:
    parser = argparse.ArgumentParser(description="Pure-Python SHAPED exporter")
    parser.add_argument("command", choices=("gzs", "bsp", "internal", "3dg1"))
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path, nargs="?")
    args = parser.parse_args()
    output = args.output or args.input.with_suffix(".asm")
    write(load(args.input), output, args.command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
