"""Pressing: closing down the ball the moment it is lost."""

from __future__ import annotations

import math

from .base import Scenario


class Press(Scenario):
    """The two nearest outfield players sprint at the new ball carrier after a turnover."""

    type_code = "PRESS"

    def __init__(self, sim, rng):
        super().__init__(sim, rng)
        self._last: tuple[int, str | None] = (sim.period, None)

    def trigger(self) -> None:
        sim = self.sim
        now = (sim.period, sim.possession)
        turnover = now[0] == self._last[0] and None not in (now[1], self._last[1]) \
            and now[1] != self._last[1]
        self._last = now
        if not turnover or sim.carrier is None:
            return
        pressing = "A" if sim.possession == "H" else "H"
        carrier = sim.carrier
        nearest = sorted(self.free([p for p in sim.players(pressing) if sim.role(p) != "GK"]),
                         key=lambda p: math.dist(sim.pos[p], sim.pos[carrier]))[:2]

        def target(carrier=carrier):
            return tuple(sim.pos[carrier]) if carrier in sim.side else tuple(sim.ball[:2])

        for presser in nearest:
            self.start(presser, (1.5, 3.0), target)
