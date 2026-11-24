"""What happens to tracking data after the match, as a real estate sees it.

Three events, each one a trap docs/07 names:

- **Detection.** Planted actions are what really happened. What lands in
  ``tracking.off_ball_action`` is what a detection model found -- with a
  confidence, missing the faint ones -- plus a share an analyst coded from
  video, with no frames behind them.
- **Re-delivery.** The vendor sends a match again after fixing player
  identity. The old capture stays, marked not current.
- **Model re-run.** A new detection model replaces the model's actions for a
  match. Those rows are really deleted, which is what the change log is for.
"""

from __future__ import annotations

from .rng import rng_for
from .world import Match, OffBallAction, World

MODEL_VERSIONS = ("offsim-detect-1.0", "offsim-detect-1.1", "offsim-detect-2.0")
#: Below this confidence the model reports nothing.
DETECTION_THRESHOLD = 0.6
#: Share of actions an analyst codes by hand from video instead.
ANALYST_SHARE = 0.1


def detect(world: World, match: Match, actions: list[OffBallAction],
           model_version: str = MODEL_VERSIONS[0], include_analyst: bool = True) -> list[dict]:
    """off_ball_action rows for ``actions``, as a model and analysts would record them.

    Keys starting with "_" are link hints the sink resolves: the type and zone
    codes, and frame numbers in the match's current primary capture.
    """
    rows = []
    for i, a in enumerate(actions):
        # Whether an analyst coded it does not depend on the model version, so
        # a model re-run never touches the analysts' rows.
        analyst = rng_for(world.seed, "analyst", match.match_id, i).random() < ANALYST_SHARE
        base = {
            "_type_code": a.type_code,
            "match_id": match.match_id,
            "player_id": a.player_id,
            "led_to_hudl_instance_id": a.led_to_hudl_instance_id,
        }
        if analyst:
            if include_analyst:
                rows.append({**base, "_start_frame_number": None, "_end_frame_number": None,
                             "_zones": {z: None for z in a.zones},
                             "detection_method": "analyst",
                             "detection_model_version": None, "detection_confidence": None})
            continue
        confidence = rng_for(world.seed, "detect", match.match_id, model_version, i).uniform(0.45, 0.99)
        if confidence < DETECTION_THRESHOLD:
            continue
        rows.append({**base, "_start_frame_number": a.start_frame_number,
                     "_end_frame_number": a.end_frame_number, "_zones": dict(a.zones),
                     "detection_method": "model", "detection_model_version": model_version,
                     "detection_confidence": round(confidence, 3)})
    return rows


def plant(world: World, match: Match) -> list[OffBallAction]:
    """Re-simulate a match's primary capture to recover its planted actions."""
    recording = world.record(world.captures(match)[0])
    for _ in recording.frames():
        pass
    return recording.actions


def redeliver(sink, world: World, match: Match) -> int:
    """Deliver ``match`` again as a new capture version. Returns the new version."""
    version = sink.max_delivery_version(match.match_id) + 1
    sink.supersede_captures(match.match_id)
    for capture in world.captures(match, delivery_version=version):
        sink.write_recording(world.record(capture))
    return version


def rerun_detection(sink, world: World, match: Match, model_version: str) -> tuple[int, int]:
    """Replace the model's actions for ``match``. Returns (deleted, inserted)."""
    rows = detect(world, match, plant(world, match), model_version, include_analyst=False)
    deleted = sink.delete_model_actions(match.match_id)
    inserted = sink.write_actions(match.match_id, rows)
    return deleted, inserted
