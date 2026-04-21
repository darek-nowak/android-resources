"""Command-line interface for extracting string resources from resources.arsc."""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

from .arsc import parse_resource_table


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arsc-strings",
        description="Extract the string table from an Android resources.arsc file.",
    )
    parser.add_argument(
        "arsc_file",
        metavar="FILE",
        type=Path,
        help="Path to the resources.arsc file.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text).",
    )
    parser.add_argument(
        "--pool",
        action="store_true",
        default=False,
        help=(
            "Dump the raw global string pool instead of resolved string resources. "
            "Useful for inspecting all value strings referenced in the table."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:  # pragma: no cover – entry point
    parser = _build_parser()
    args = parser.parse_args(argv)

    path: Path = args.arsc_file
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 1

    try:
        table = parse_resource_table(path.read_bytes())
    except (ValueError, struct.error) as exc:
        print(f"error: could not parse {path}: {exc}", file=sys.stderr)
        return 1

    if args.pool:
        _dump_pool(table.global_string_pool, args.format)
    else:
        _dump_resources(table.string_resources, args.format)

    return 0


def _dump_pool(pool, fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(pool.strings, ensure_ascii=False, indent=2))
    else:
        for i, s in enumerate(pool.strings):
            print(f"[{i}] {s!r}")


def _dump_resources(resources, fmt: str) -> None:
    if fmt == "json":
        rows = [
            {
                "id": f"0x{r.resource_id:08x}",
                "key": r.key,
                "value": r.value,
            }
            for r in resources
        ]
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for r in resources:
            print(f"0x{r.resource_id:08x}  {r.key!r:40s} = {r.value!r}")


# Allow ``python -m android_resources`` as an alias
if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
