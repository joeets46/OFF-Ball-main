"""Marking: a defender tracks one attacker, staying goal-side."""

from __future__ import annotations

import math

from .base import Scenario

#: How far goal-side of the attacker the marker holds, in metres.
GOAL_SIDE_M = 1.5
#: Only attackers this close are worth picking up.
PICK_UP_M = 15.0


class Mark(Scenario):
    type_code = "MARK"

    def trigger(self) -> None:
        sim = self.sim
        attacking = sim.possession
        if attacking is None:
            return
        defending = "A" if attacking == "H" else "H"
        targets = [p for p in sim.players(attacking) if sim.role(p) in ("MID", "FWD")]
        for marker in self.free([p for p in sim.players(defending) if sim.role(p) == "DEF"]):
            if not self.chance(0.03):
                continue
            near = [p for p in targets if math.dist(sim.pos[p], sim.pos[marker]) < PICK_UP_M]
            if not near:
                continue
            man = min(near, key=lambda p: math.dist(sim.pos[p], sim.pos[marker]))
            # The defending team's own goal line in home-frame x.
            own_goal_x = 0.0 if defending == "H" else sim.length

            def target(man=man, own_goal_x=own_goal_x):
                mx, my = sim.pos[man] if man in sim.side else sim.pos[marker]
                step = GOAL_SIDE_M if own_goal_x > mx else -GOAL_SIDE_M
                return mx + step, my

            self.start(marker, (3.0, 6.0), target)
