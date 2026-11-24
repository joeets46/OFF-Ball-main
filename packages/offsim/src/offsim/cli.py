"""The ``offsim`` command.

    offsim backfill --profile small --reset     build a world and write it
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import DEFAULT_SEED, PROFILES, SIM_DATABASE, database_url


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="offsim", description="Seeded fake data for the OFF-Ball tracking schema.")
    parser.add_argument("--db", default=None,
                        help=f"connection URL (default: the {SIM_DATABASE} database "
                             "on the repository's PostgreSQL)")
    commands = parser.add_subparsers(dest="command", required=True)

    bf = commands.add_parser("backfill", help="build a whole world and write it in one go")
    bf.add_argument("--profile", choices=sorted(PROFILES), default="small")
    bf.add_argument("--seed", type=int, default=DEFAULT_SEED)
    bf.add_argument("--reset", action="store_true",
                    help=f"drop and recreate the {SIM_DATABASE} database first")
    bf.add_argument("--out", type=Path, default=None,
                    help="write vendor-style files to this folder instead of a database")

    args = parser.parse_args(argv)
    url = args.db or database_url()

    if args.command == "backfill":
        from .backfill import run_backfill

        summary = run_backfill(PROFILES[args.profile], args.seed, url, args.reset, args.out)
        print(f"done: {summary.matches} matches, {summary.captures} captures, "
              f"{summary.frames:,} frames, {summary.actions} off-ball actions")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
