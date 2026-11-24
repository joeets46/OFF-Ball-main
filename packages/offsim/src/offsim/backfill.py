"""Build a whole world and write it in one go.

``--reset`` drops and recreates the simulation database, then loads the
``common`` and ``tracking`` DDL straight from ``models/physical/`` -- the same
files the repository's own tests load -- so the simulated rows always meet
the current schema.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

from .config import SIM_DATABASE, Profile, repo_root, tracking_ddl_dir
from .lifecycle import detect
from .scenarios import DEFAULT_SCENARIOS
from .sink import FileSink, PostgresSink
from .world import World, build_world

#: Load order for the schema files; the same numbered layout every schema uses.
DDL_ORDER = ("00_schema", "10_domains_and_enums", "20_reference", "30_master",
             "31_master_pii", "40_transaction", "50_constraints", "60_indexes",
             "70_audit", "80_comments")

COUNTED = ("match", "player", "match_squad", "capture", "frame",
           "player_frame_position", "off_ball_action", "off_ball_action_zone")


@dataclass
class Summary:
    matches: int = 0
    captures: int = 0
    frames: int = 0
    actions: int = 0


def backfill(world: World, sink, log: Callable[[str], None] = print) -> Summary:
    """Write every match of ``world`` to ``sink``: masters, captures, actions."""
    summary = Summary()
    sink.write_masters(world)
    for match in world.matches:
        for capture in world.captures(match):
            recording = world.record(capture)
            sink.write_recording(recording)
            summary.captures += 1
            summary.frames += 2 * capture.frames_per_period
            if capture.is_primary:
                summary.actions += sink.write_actions(
                    match.match_id, detect(world, match, recording.actions))
        summary.matches += 1
        log(f"  match {match.match_id}  {match.home.name} v {match.away.name}  "
            f"({match.coordinate_unit}{', +gps' if match.has_gps_capture else ''})")
    return summary


def run_backfill(profile: Profile, seed: int, url: str, reset: bool,
                 out: Path | None = None, log: Callable[[str], None] = print) -> Summary:
    """The ``offsim backfill`` command."""
    world = build_world(profile, seed, DEFAULT_SCENARIOS)
    if out is not None:
        log(f"writing profile {profile.name} (seed {seed}) as files to {out}")
        return backfill(world, FileSink(out), log)

    import psycopg

    if reset:
        log(f"resetting database {_dbname(url)}")
        reset_database(url)
    with psycopg.connect(url, autocommit=True) as conn:
        if conn.execute("SELECT count(*) FROM tracking.match").fetchone()[0]:
            raise SystemExit(f"{_dbname(url)} already holds simulated data; use --reset")
        log(f"writing profile {profile.name} (seed {seed}) to {_dbname(url)}")
        summary = backfill(world, PostgresSink(conn), log)
        for table in COUNTED:
            n = conn.execute(f"SELECT count(*) FROM tracking.{table}").fetchone()[0]
            log(f"  {table:<22} {n:>10,}")
    return summary


def reset_database(url: str) -> None:
    """Drop and recreate the simulation database, then load common + tracking."""
    import psycopg

    name = _dbname(url)
    if not name.startswith(SIM_DATABASE):
        # The guard that keeps --reset away from a working database.
        raise SystemExit(f"refusing to reset {name!r}: only {SIM_DATABASE}* databases")
    admin = urlunsplit(urlsplit(url)._replace(path="/postgres"))
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        conn.execute(f'CREATE DATABASE "{name}"')
    with psycopg.connect(url, autocommit=True) as conn:
        for path in schema_files():
            conn.execute(path.read_text(encoding="utf-8"))


def schema_files() -> list[Path]:
    sql = repo_root() / "models" / "physical" / "sql"
    files = [sql / "01_common.sql", sql / "02_common_comments.sql"]
    files += [p for stem in DDL_ORDER if (p := tracking_ddl_dir() / f"{stem}.sql").exists()]
    return files


def _dbname(url: str) -> str:
    return urlsplit(url).path.lstrip("/")
