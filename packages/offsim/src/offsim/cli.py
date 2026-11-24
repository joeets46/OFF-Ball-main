"""The ``offsim`` command.

    offsim backfill --profile small --reset     build a world and write it
    offsim validate                             the 4 business checks, then DQ
    offsim run --ticks 6 --interval 5           act like a live vendor
"""

from __future__ import annotations

import argparse
import dataclasses
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

    commands.add_parser("validate", help="run the 4 business checks and the DQ checks")

    rn = commands.add_parser("run", help="deliver, re-deliver and re-detect over time")
    rn.add_argument("--profile", choices=sorted(PROFILES), default="small",
                    help="period length for newly delivered matches (match the backfill)")
    rn.add_argument("--seed", type=int, default=DEFAULT_SEED,
                    help="must be the seed the database was backfilled with")
    rn.add_argument("--ticks", type=int, default=6)
    rn.add_argument("--interval", type=float, default=5.0, help="seconds between ticks")

    args = parser.parse_args(argv)
    url = args.db or database_url()

    if args.command == "backfill":
        from .backfill import run_backfill

        summary = run_backfill(PROFILES[args.profile], args.seed, url, args.reset, args.out)
        print(f"done: {summary.matches} matches, {summary.captures} captures, "
              f"{summary.frames:,} frames, {summary.actions} off-ball actions")
        return 0
    if args.command == "validate":
        return _validate(url)
    if args.command == "run":
        return _run(url, PROFILES[args.profile], args.seed, args.ticks, args.interval)
    return 1


def _validate(url: str) -> int:
    import psycopg

    from .dq import change_log_summary, run_dq_checks
    from .validate import run_business_checks

    with psycopg.connect(url) as conn:
        sections = (("business checks (docs/07)", run_business_checks(conn)),
                    ("data quality", run_dq_checks(conn)))
        failed = 0
        for title, results in sections:
            print(title)
            for r in results:
                failed += not r.passed
                print(f"  {'PASS' if r.passed else 'FAIL'}  {r.name}\n        {r.detail}")
        deletes = change_log_summary(conn)
        if deletes:
            print("change log deletes: " + ", ".join(f"{t} {n}" for t, n in deletes.items()))
    print("all checks passed" if not failed else f"{failed} check(s) failed")
    return 1 if failed else 0


def _run(url: str, profile, seed: int, ticks: int, interval: float) -> int:
    import psycopg

    from .scenarios import DEFAULT_SCENARIOS
    from .sink import PostgresSink
    from .stream import run_stream
    from .world import build_world

    # Every fixture of the season, so there are matches left to deliver.
    world = build_world(dataclasses.replace(profile, matches=12), seed, DEFAULT_SCENARIOS)
    with psycopg.connect(url, autocommit=True) as conn:
        first = conn.execute("SELECT hudl_game_id::text FROM tracking.match "
                             "ORDER BY match_id LIMIT 1").fetchone()
        if first is None:
            print("no matches yet: run `offsim backfill --reset` first")
            return 1
        if first[0] != world.matches[0].hudl_game_id:
            print(f"this database was not built with seed {seed}; pass the backfill's --seed")
            return 1
        print(f"streaming {ticks} tick(s), {interval:g} s apart")
        run_stream(world, PostgresSink(conn), conn, ticks, interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
