"""The stream behind ``offsim run``.

Each tick is one event, as a club's data team would see it arrive:

- **deliver**: the next fixture's capture files land, with their actions;
- **redeliver**: the vendor sends an earlier match again after fixing player
  identity -- a new capture version, the old one kept but no longer current;
- **redetect**: a newer detection model re-runs over an earlier match and
  replaces its model actions, which really deletes rows.

Which event happens is drawn from the seed and the number of captures and
actions already in the database, so the same database state always leads to
the same next event.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from ..lifecycle import MODEL_VERSIONS, detect, redeliver, rerun_detection
from ..rng import rng_for
from ..world import World


@dataclass
class Event:
    kind: str            # deliver | redeliver | redetect | idle
    match_id: int | None
    detail: str


def next_event(world: World, sink, tick_key: tuple) -> Event:
    """Decide and perform one event."""
    delivered = sink.delivered_match_ids()
    pending = [m for m in world.matches if m.match_id not in delivered]
    done = [m for m in world.matches if m.match_id in delivered]
    r = rng_for(world.seed, "stream", tick_key)
    roll = r.random()

    if pending and (roll < 0.5 or not done):
        match = pending[0]
        sink.write_match(world, match)
        actions = 0
        for capture in world.captures(match):
            recording = world.record(capture)
            sink.write_recording(recording)
            if capture.is_primary:
                actions = sink.write_actions(match.match_id,
                                             detect(world, match, recording.actions))
        return Event("deliver", match.match_id,
                     f"{match.home.name} v {match.away.name}, {actions} actions")
    if not done:
        return Event("idle", None, "nothing delivered yet and nothing pending")

    match = r.choice(done)
    if roll < 0.75:
        version = redeliver(sink, world, match)
        return Event("redeliver", match.match_id, f"now delivery_version {version}")
    # Only ever forwards: a re-run deletes the older version's rows, so "not
    # used yet" would include versions already replaced.
    used = sink.model_versions(match.match_id)
    latest = max((MODEL_VERSIONS.index(v) for v in used), default=0)
    newer = list(MODEL_VERSIONS[latest + 1:])
    if not newer:
        return Event("idle", match.match_id, "already on the newest detection model")
    deleted, inserted = rerun_detection(sink, world, match, newer[0])
    return Event("redetect", match.match_id,
                 f"{newer[0]}: {deleted} model actions deleted, {inserted} inserted")


def run_stream(world: World, sink, conn, ticks: int, interval: float,
               log: Callable[[str], None] = print) -> list[Event]:
    events = []
    for tick in range(ticks):
        if tick and interval > 0:
            time.sleep(interval)
        # Captures and actions both move with every event, so the key never repeats.
        tick_key = conn.execute("SELECT (SELECT count(*) FROM tracking.capture), "
                                "(SELECT count(*) FROM tracking.off_ball_action)").fetchone()
        event = next_event(world, sink, tuple(tick_key))
        events.append(event)
        log(f"  tick {tick + 1}: {event.kind:<9} "
            f"{event.match_id or '':<7} {event.detail}")
    return events
