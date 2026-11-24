"""Write a world into the tracking schema.

Bulk paths use COPY. Frames and positions have one problem worth solving:
``frame.frame_id`` is IDENTITY, and COPY cannot supply it, so positions cannot
name their frame. They are copied into a temporary table keyed by frame
number, frames are copied next, and one INSERT ... SELECT joins the two on
(capture_id, frame_number). The database does the matching; Python never
holds a match's three million positions.
"""

from __future__ import annotations

from typing import Iterable

from .. import schema
from ..world import Recording, World


class PostgresSink:
    def __init__(self, conn) -> None:
        self.conn = conn
        self._type_ids: dict[str, int] | None = None
        self._zone_ids: dict[str, int] | None = None

    # -- masters ------------------------------------------------------------

    def write_masters(self, world: World) -> None:
        with self.conn.transaction():
            self._copy("match", [m.row() for m in world.matches])
            self._copy("player", [p.row() for p in world.players])
            self._copy("match_squad", [s.row() for s in world.squads])

    # -- captures, frames, positions ----------------------------------------

    def write_recording(self, recording: Recording) -> int:
        """One capture with its periods, frames and positions. Returns capture_id.

        Reading the frames is what simulates the match, so ``recording.actions``
        is complete once this returns.
        """
        capture = recording.capture
        frame_cols = [c for c in schema.columns("frame") if c not in ("frame_id", "created_at")]
        pos_cols = ["frame_number", "player_id", "captured_at", "x", "y", "speed_mps"]
        with self.conn.transaction(), self.conn.cursor() as cur:
            row = {k: v for k, v in capture.row().items() if not k.startswith("_")}
            cur.execute(
                f"INSERT INTO tracking.capture ({', '.join(row)}) "
                f"VALUES ({', '.join(['%s'] * len(row))}) RETURNING capture_id",
                list(row.values()))
            capture_id = cur.fetchone()[0]
            for period in capture.period_rows():
                period = {k: v for k, v in period.items() if not k.startswith("_")}
                period["capture_id"] = capture_id
                cur.execute(
                    f"INSERT INTO tracking.capture_period ({', '.join(period)}) "
                    f"VALUES ({', '.join(['%s'] * len(period))})", list(period.values()))

            cur.execute("""
                CREATE TEMP TABLE _offsim_position (
                    frame_number INTEGER, player_id BIGINT, captured_at TIMESTAMPTZ,
                    x NUMERIC(7,2), y NUMERIC(7,2), speed_mps NUMERIC(4,2)
                ) ON COMMIT DROP""")
            frames = []
            with cur.copy(f"COPY _offsim_position ({', '.join(pos_cols)}) FROM STDIN") as copy:
                for frame in recording.frames():
                    f = frame.row(capture)
                    f["capture_id"] = capture_id
                    frames.append(tuple(f[c] for c in frame_cols))
                    for p in frame.position_rows(capture):
                        copy.write_row((p["_frame_number"], p["player_id"], p["captured_at"],
                                        p["x"], p["y"], p["speed_mps"]))
            with cur.copy(f"COPY tracking.frame ({', '.join(frame_cols)}) FROM STDIN") as copy:
                for f in frames:
                    copy.write_row(f)
            cur.execute("""
                INSERT INTO tracking.player_frame_position
                    (frame_id, player_id, captured_at, x, y, speed_mps)
                SELECT f.frame_id, s.player_id, s.captured_at, s.x, s.y, s.speed_mps
                FROM _offsim_position s
                JOIN tracking.frame f
                  ON f.capture_id = %s AND f.frame_number = s.frame_number""", [capture_id])
        return capture_id

    # -- off-ball actions ---------------------------------------------------

    def write_actions(self, match_id: int, rows: Iterable[dict]) -> int:
        """Insert actions, resolving frame numbers against the current primary capture."""
        types, zones = self._reference()
        count = 0
        frame_of = """(SELECT f.frame_id FROM tracking.frame f
                        JOIN tracking.capture c ON c.capture_id = f.capture_id
                       WHERE c.match_id = %s AND c.is_current AND c.is_primary
                         AND f.frame_number = %s)"""
        with self.conn.transaction(), self.conn.cursor() as cur:
            for row in rows:
                cur.execute(f"""
                    INSERT INTO tracking.off_ball_action
                        (match_id, player_id, off_ball_action_type_id, start_frame_id,
                         end_frame_id, led_to_hudl_instance_id, detection_method,
                         detection_model_version, detection_confidence)
                    VALUES (%s, %s, %s, {frame_of}, {frame_of}, %s, %s, %s, %s)
                    RETURNING off_ball_action_id""",
                    [row["match_id"], row["player_id"], types[row["_type_code"]],
                     match_id, row["_start_frame_number"], match_id, row["_end_frame_number"],
                     row["led_to_hudl_instance_id"], row["detection_method"],
                     row["detection_model_version"], row["detection_confidence"]])
                action_id = cur.fetchone()[0]
                for code, entered in row["_zones"].items():
                    cur.execute(f"""
                        INSERT INTO tracking.off_ball_action_zone
                            (off_ball_action_id, pitch_zone_id, entered_frame_id)
                        VALUES (%s, %s, {frame_of})""",
                        [action_id, zones[code], match_id, entered])
                count += 1
        return count

    def delete_model_actions(self, match_id: int) -> int:
        with self.conn.transaction(), self.conn.cursor() as cur:
            cur.execute("DELETE FROM tracking.off_ball_action "
                        "WHERE match_id = %s AND detection_method = 'model'", [match_id])
            return cur.rowcount

    # -- capture versions ---------------------------------------------------

    def max_delivery_version(self, match_id: int) -> int:
        row = self.conn.execute("SELECT max(delivery_version) FROM tracking.capture "
                                "WHERE match_id = %s", [match_id]).fetchone()
        return row[0] or 0

    def supersede_captures(self, match_id: int) -> None:
        with self.conn.transaction():
            self.conn.execute("UPDATE tracking.capture SET is_current = FALSE "
                              "WHERE match_id = %s AND is_current", [match_id])

    # -- helpers ------------------------------------------------------------

    def _copy(self, table: str, rows: list[dict]) -> None:
        if not rows:
            return
        cols = [k for k in rows[0] if not k.startswith("_")]
        with self.conn.cursor() as cur, cur.copy(
                f"COPY tracking.{table} ({', '.join(cols)}) FROM STDIN") as copy:
            for row in rows:
                copy.write_row(tuple(row[c] for c in cols))

    def _reference(self) -> tuple[dict[str, int], dict[str, int]]:
        """Type and zone ids by code. The DDL seeds both, with IDENTITY keys."""
        if self._type_ids is None:
            self._type_ids = dict(self.conn.execute(
                "SELECT type_code, off_ball_action_type_id FROM tracking.off_ball_action_type"))
            self._zone_ids = dict(self.conn.execute(
                "SELECT zone_code, pitch_zone_id FROM tracking.pitch_zone"))
        return self._type_ids, self._zone_ids
