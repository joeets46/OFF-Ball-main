"""The live stream never stands still.

``next_event`` draws its event from the database state, so an event that
changes nothing draws itself again on every later tick. Pure Python, no
database: a fake sink stands in for PostgreSQL.
"""

from __future__ import annotations

from offsim.lifecycle import MODEL_VERSIONS
from offsim.rng import rng_for
from offsim.stream import deliveries, next_event


class FakeSink:
    """The sink calls ``next_event`` makes, in memory, with every match delivered."""

    def __init__(self, world, model_version: str | None) -> None:
        self.versions = {m.match_id: {model_version} - {None} for m in world.matches}
        self.captures = []

    def delivered_match_ids(self) -> set[int]:
        return set(self.versions)

    def model_versions(self, match_id: int) -> set[str]:
        return set(self.versions[match_id])

    def max_delivery_version(self, match_id: int) -> int:
        return max((c.delivery_version for c in self.captures if c.match.match_id == match_id),
                   default=1)

    def supersede_captures(self, match_id: int) -> None:
        pass

    def write_recording(self, recording) -> None:
        self.captures.append(recording.capture)


def _redetect_key(world) -> tuple[int, int]:
    """A tick key whose roll -- the stream's first draw -- picks a redetect."""
    return next(key for key in ((n, 0) for n in range(1000))
                if rng_for(world.seed, "stream", key).random() >= 0.75)


def test_redetect_roll_on_newest_model_redelivers_instead_of_idling(world):
    sink = FakeSink(world, MODEL_VERSIONS[-1])
    event = next_event(world, sink, _redetect_key(world))
    assert event.kind == "redeliver"
    assert sink.captures            # the database moved on, so the next tick differs


def test_redetect_that_changes_nothing_redelivers(world, monkeypatch):
    # No model rows (every action analyst-coded), and the re-run finds none either.
    sink = FakeSink(world, None)
    monkeypatch.setattr(deliveries, "rerun_detection", lambda *args: (0, 0))
    event = next_event(world, sink, _redetect_key(world))
    assert event.kind == "redeliver"
    assert sink.captures
