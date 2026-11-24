"""offsim end to end against a real PostgreSQL 18 (docker compose up -d).

Backfills a tiny world into its own ``offball_sim_test`` database, proves the
four business checks pass, then breaks the data in each of the four ways
docs/07 warns about and proves the matching check -- and only that one --
fails. Breakages run inside a rolled-back transaction, so each starts clean.
Skipped, not failed, when the database is not running.
"""

from __future__ import annotations

import dataclasses

import pytest

from offsim.backfill import backfill, reset_database
from offsim.cli import main as cli_main
from offsim.config import database_url
from offsim.dq import change_log_summary, run_dq_checks
from offsim.lifecycle import redeliver, rerun_detection
from offsim.sink import PostgresSink
from offsim.stream import run_stream
from offsim.validate import BUSINESS_CHECKS, run_business_checks

pytestmark = pytest.mark.database

TEST_DATABASE = "offball_sim_test"
CHECK = [name for name, _, _ in BUSINESS_CHECKS]


@pytest.fixture(scope="module")
def sim(make_world):
    psycopg = pytest.importorskip("psycopg")
    try:
        psycopg.connect(database_url("postgres"), connect_timeout=3).close()
    except Exception as exc:  # noqa: BLE001 - any connection problem means skip
        pytest.skip(f"PostgreSQL not reachable ({exc.__class__.__name__}); "
                    "start it with: docker compose up -d")
    url = database_url(TEST_DATABASE)
    reset_database(url)
    world = make_world()
    conn = psycopg.connect(url, autocommit=True)
    sink = PostgresSink(conn)
    backfill(world, sink, log=lambda _: None)
    yield conn, world, sink, url
    conn.close()
    with psycopg.connect(database_url("postgres"), autocommit=True) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{TEST_DATABASE}" WITH (FORCE)')


def _failing(conn) -> set[str]:
    return {r.name for r in run_business_checks(conn) if not r.passed}


def _count(conn, table: str, where: str = "TRUE") -> int:
    return conn.execute(f"SELECT count(*) FROM tracking.{table} WHERE {where}").fetchone()[0]


# -- a clean backfill ----------------------------------------------------------

def test_backfill_writes_every_table(sim):
    conn, world, _, _ = sim
    assert _count(conn, "match") == len(world.matches)
    frames = sum(2 * c.frames_per_period for m in world.matches for c in world.captures(m))
    assert _count(conn, "frame") == frames
    assert _count(conn, "player_frame_position") == frames * 22
    assert _count(conn, "off_ball_action") > 0
    assert _count(conn, "off_ball_action_zone") > 0


def test_business_checks_pass(sim):
    assert _failing(sim[0]) == set()


def test_dq_checks_pass(sim):
    failing = [r for r in run_dq_checks(sim[0]) if not r.passed]
    assert not failing, failing


def test_cli_validate_exits_zero(sim, capsys):
    assert cli_main(["--db", sim[3], "validate"]) == 0
    assert "all checks passed" in capsys.readouterr().out


# -- each docs/07 trap trips exactly its own check -----------------------------

BREAKAGES = {
    "no current capture": (
        CHECK[0],
        "UPDATE tracking.capture SET is_current = FALSE WHERE match_id = "
        "(SELECT min(match_id) FROM tracking.match)",
    ),
    "wrong frame rate": (
        CHECK[1],
        "UPDATE tracking.capture SET frames_per_second = 10 WHERE capture_method = 'optical'",
    ),
    "a twelfth player": (
        CHECK[2],
        """INSERT INTO tracking.player_frame_position (frame_id, player_id, captured_at, x, y)
           SELECT f.frame_id, ms.player_id, f.captured_at, 0, 0
           FROM tracking.frame f
           JOIN tracking.capture c ON c.capture_id = f.capture_id AND c.is_current
           JOIN tracking.match_squad ms
             ON ms.match_id = c.match_id AND NOT ms.is_starter AND ms.team_side = 'H'
           WHERE f.period = 1
           LIMIT 1""",
    ),
    "centimetres labelled as metres": (
        CHECK[3],
        "UPDATE tracking.capture SET coordinate_unit = 'm' WHERE coordinate_unit = 'cm'",
    ),
}


@pytest.mark.parametrize("breakage", list(BREAKAGES))
def test_each_trap_trips_its_own_check(sim, breakage):
    conn = sim[0]
    expected, sql = BREAKAGES[breakage]
    with conn.transaction(force_rollback=True):
        conn.execute(sql)
        assert _failing(conn) == {expected}
    assert _failing(conn) == set()


# -- lifecycle -----------------------------------------------------------------

def test_redelivery_keeps_one_current_capture(sim):
    conn, world, sink, _ = sim
    match = world.matches[0]
    before = _count(conn, "capture", f"match_id = {match.match_id}")
    assert redeliver(sink, world, match) == 2
    assert _count(conn, "capture", f"match_id = {match.match_id}") == before * 2
    assert _count(conn, "capture",
                  f"match_id = {match.match_id} AND is_current AND delivery_version = 1") == 0
    assert _failing(conn) == set()


def test_model_rerun_really_deletes(sim):
    conn, world, sink, _ = sim
    match = world.matches[1]
    analyst = f"match_id = {match.match_id} AND detection_method = 'analyst'"
    analyst_before = _count(conn, "off_ball_action", analyst)
    logged_before = change_log_summary(conn).get("off_ball_action", 0)
    deleted, inserted = rerun_detection(sink, world, match, "offsim-detect-1.1")
    assert deleted > 0 and inserted > 0
    assert change_log_summary(conn)["off_ball_action"] == logged_before + deleted
    assert _count(conn, "off_ball_action", analyst) == analyst_before
    assert _count(conn, "off_ball_action",
                  f"match_id = {match.match_id} AND detection_model_version = 'offsim-detect-1.0'") == 0


def test_stream_keeps_every_check_passing(sim, make_world, tiny):
    conn, _, sink, _ = sim
    season = make_world(dataclasses.replace(tiny, matches=12))
    events = run_stream(season, sink, conn, ticks=4, interval=0, log=lambda _: None)
    assert all(e.kind != "idle" for e in events)
    assert _failing(conn) == set()
    assert not [r for r in run_dq_checks(conn) if not r.passed]
