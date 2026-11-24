"""Technical data quality: the things a loader gets wrong, not the business.

Separate from validate.py because a failure here is a bug in whatever wrote
the rows, while a business-check failure is a trap in the data the pipeline
has to handle.
"""

from __future__ import annotations

from .validate import CheckResult, _run

DQ_CHECKS: tuple[tuple[str, str, str], ...] = (
    (
        "default partition is empty",
        "partition maintenance falling behind",
        "SELECT frame_id FROM tracking.player_frame_position_default",
    ),
    (
        "positions carry their frame's captured_at",
        "a loader copying the partition key wrongly (no CHECK can see across tables)",
        """
        SELECT p.frame_id || '/' || p.player_id
        FROM tracking.player_frame_position p
        JOIN tracking.frame f ON f.frame_id = p.frame_id
        WHERE p.captured_at <> f.captured_at
        """,
    ),
    (
        "ball carrier is in the squad, on the side in possession",
        "possession and carrier written from different sources",
        """
        SELECT f.frame_id
        FROM tracking.frame f
        JOIN tracking.capture c ON c.capture_id = f.capture_id
        WHERE f.ball_carrier_player_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM tracking.match_squad ms
              WHERE ms.match_id = c.match_id
                AND ms.player_id = f.ball_carrier_player_id
                AND ms.team_side = f.possession_side)
        """,
    ),
    (
        "off-ball actions point at their match's current primary capture",
        "actions resolved against the wrong capture, or left behind by a re-delivery",
        """
        SELECT a.off_ball_action_id
        FROM tracking.off_ball_action a
        JOIN tracking.frame f ON f.frame_id IN (a.start_frame_id, a.end_frame_id)
        JOIN tracking.capture c ON c.capture_id = f.capture_id
        WHERE NOT (c.match_id = a.match_id AND c.is_current AND c.is_primary)
        UNION ALL
        SELECT z.off_ball_action_id
        FROM tracking.off_ball_action_zone z
        JOIN tracking.off_ball_action a ON a.off_ball_action_id = z.off_ball_action_id
        JOIN tracking.frame f ON f.frame_id = z.entered_frame_id
        JOIN tracking.capture c ON c.capture_id = f.capture_id
        WHERE NOT (c.match_id = a.match_id AND c.is_current AND c.is_primary)
        """,
    ),
)


def run_dq_checks(conn) -> list[CheckResult]:
    return [_run(conn, name, catches, sql) for name, catches, sql in DQ_CHECKS]


def change_log_summary(conn) -> dict[str, int]:
    """Deletes recorded per table: what an extract would have to tombstone."""
    return dict(conn.execute(
        "SELECT table_name, count(*) FROM tracking._change_log "
        "WHERE operation = 'D' GROUP BY table_name ORDER BY table_name").fetchall())
