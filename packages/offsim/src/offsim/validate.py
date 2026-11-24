"""The four business checks: the tracking gates in docs/07, run as SQL.

Each reads what an extract would read -- current captures only -- and fails
on exactly the mistake docs/07 says it catches. The data offsim writes is
built to contain those traps (centimetre captures, GPS at 10 fps, a half-time
substitute, re-deliveries), so a pass means they were handled, not avoided.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


#: (name, what it catches, SQL returning one row per failure, first column a label)
BUSINESS_CHECKS: tuple[tuple[str, str, str], ...] = (
    (
        "one current primary capture per match",
        "a re-delivery or a GPS capture double-counting every run",
        """
        SELECT m.match_id
        FROM tracking.match m
        LEFT JOIN tracking.capture c
               ON c.match_id = m.match_id AND c.is_current AND c.is_primary
        GROUP BY m.match_id
        HAVING count(c.capture_id) <> 1
        """,
    ),
    (
        "frame count matches frames_per_second",
        "a wrong frame rate, before it distorts every speed",
        """
        SELECT c.capture_id || '/period ' || f.period
        FROM tracking.capture c
        JOIN tracking.frame f ON f.capture_id = c.capture_id
        WHERE c.is_current
        GROUP BY c.capture_id, f.period, c.frames_per_second
        HAVING abs(count(*) - (extract(epoch FROM max(f.captured_at) - min(f.captured_at))
                               * c.frames_per_second + 1))
               > 0.01 * count(*) + 1
        """,
    ),
    (
        "at most 11 players per side, all in the squad",
        "a substitute's shirt number not resolved through match_squad",
        """
        SELECT f.frame_id || coalesce('/' || ms.team_side, '/not in squad')
        FROM tracking.player_frame_position p
        JOIN tracking.frame f ON f.frame_id = p.frame_id
        JOIN tracking.capture c ON c.capture_id = f.capture_id AND c.is_current
        LEFT JOIN tracking.match_squad ms
               ON ms.match_id = c.match_id AND ms.player_id = p.player_id
        GROUP BY f.frame_id, ms.team_side
        HAVING ms.team_side IS NULL OR count(*) > 11
        """,
    ),
    (
        "normalised positions on the pitch",
        "unit, origin or direction of play applied wrongly",
        """
        WITH n AS (
            SELECT p.frame_id, p.player_id,
                   (p.x / CASE c.coordinate_unit WHEN 'cm' THEN 100 ELSE 1 END
                        / m.pitch_length_m + 0.5) * 100 AS xr,
                   (p.y / CASE c.coordinate_unit WHEN 'cm' THEN 100 ELSE 1 END
                        / m.pitch_width_m + 0.5) * 100 AS yr,
                   (ms.team_side = 'H') = cp.home_attacks_positive_x AS attacks_positive
            FROM tracking.player_frame_position p
            JOIN tracking.frame f ON f.frame_id = p.frame_id
            JOIN tracking.capture c ON c.capture_id = f.capture_id AND c.is_current
            JOIN tracking.capture_period cp
              ON cp.capture_id = c.capture_id AND cp.period = f.period
            JOIN tracking.match m ON m.match_id = c.match_id
            JOIN tracking.match_squad ms
              ON ms.match_id = c.match_id AND ms.player_id = p.player_id
            WHERE c.coordinate_origin = 'centre'
        )
        SELECT frame_id || '/' || player_id
        FROM n
        WHERE NOT (CASE WHEN attacks_positive THEN xr ELSE 100 - xr END BETWEEN -5 AND 105
               AND CASE WHEN attacks_positive THEN yr ELSE 100 - yr END BETWEEN -5 AND 105)
        """,
    ),
)


def run_business_checks(conn) -> list[CheckResult]:
    return [_run(conn, name, catches, sql) for name, catches, sql in BUSINESS_CHECKS]


def _run(conn, name: str, catches: str, sql: str) -> CheckResult:
    rows = conn.execute(sql).fetchall()
    if not rows:
        return CheckResult(name, True, f"catches {catches}")
    sample = ", ".join(str(r[0]) for r in rows[:3])
    return CheckResult(name, False, f"{len(rows)} failing (e.g. {sample}); suggests {catches}")
