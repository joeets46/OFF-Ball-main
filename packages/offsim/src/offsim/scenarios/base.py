"""What every scenario shares: start an action, steer it, finish and record it."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable

from ..world import MatchSim, OffBallAction


@dataclass
class Active:
    player_id: int
    side: str
    period: int
    start_frame: int
    end_frame: int
    #: Recomputed every frame, so a press follows the ball carrier.
    target: Callable[[], tuple[float, float]]
    shot_chance: float = 0.0
    zones: dict[str, int] = field(default_factory=dict)


class Scenario:
    """Base class. Subclasses set ``type_code`` and implement ``trigger``."""

    type_code = ""

    def __init__(self, sim: MatchSim, rng: random.Random) -> None:
        self.sim, self.rng = sim, rng
        self.active: list[Active] = []

    # -- for subclasses -----------------------------------------------------

    def trigger(self) -> None:
        """Called every frame; calls ``start`` for any action that begins now."""
        raise NotImplementedError

    def chance(self, per_second: float) -> bool:
        """True with probability ``per_second`` spread evenly across a second's frames."""
        return self.rng.random() < per_second / self.sim.fps

    def free(self, player_ids: list[int]) -> list[int]:
        return [pid for pid in player_ids if pid not in self.sim.busy]

    def start(self, player_id: int, seconds: tuple[float, float],
              target: Callable[[], tuple[float, float]], shot_chance: float = 0.0) -> None:
        sim = self.sim
        frames = round(self.rng.uniform(*seconds) * sim.fps)
        sim.busy.add(player_id)
        self.active.append(Active(player_id, sim.side[player_id], sim.period,
                                  sim.frame_number, sim.frame_number + frames,
                                  target, shot_chance))

    # -- the per-frame loop -------------------------------------------------

    def step(self) -> dict[int, tuple[float, float, bool]]:
        sim = self.sim
        self.trigger()
        overrides: dict[int, tuple[float, float, bool]] = {}
        still: list[Active] = []
        for a in self.active:
            if a.period != sim.period or a.player_id not in sim.side:
                continue          # half time, or substituted
            for zone in sim.zones_now(a.player_id):
                a.zones.setdefault(zone, sim.frame_number)
            if sim.frame_number >= a.end_frame:
                shot = sim.possession == a.side and self.rng.random() < a.shot_chance
                sim.finish(OffBallAction(a.player_id, self.type_code, a.start_frame,
                                         sim.frame_number, a.zones), leads_to_shot=shot)
                continue
            tx, ty = a.target()
            overrides[a.player_id] = (tx, ty, True)
            still.append(a)
        self.active = still
        return overrides
