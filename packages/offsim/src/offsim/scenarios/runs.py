"""Runs: off-ball movement by the team in possession."""

from __future__ import annotations

from .base import Scenario


class RunInBehind(Scenario):
    """A forward sprints past the opposition's last outfield defender.

    The run that creates the chance: about one in three ends in a Hudl shot.
    """

    type_code = "RUN_IN_BEHIND"

    def trigger(self) -> None:
        sim = self.sim
        side = sim.possession
        if side is None or sim.carrier is None or sim.role(sim.carrier) not in ("DEF", "MID"):
            return
        forwards = self.free([p for p in sim.players(side) if sim.role(p) == "FWD"])
        for runner in forwards:
            if not self.chance(0.08):
                continue
            other = "A" if side == "H" else "H"
            # The opposition's last outfield line, from the runner's direction.
            line = max(100 - sim.normalised(p)[0] for p in sim.players(other)
                       if sim.role(p) != "GK")
            xn = min(line + 8, 94)
            yn = sim.normalised(runner)[1] * 0.8 + 10      # drift towards the centre
            target = sim.from_team(side, xn, yn)
            self.start(runner, (2.0, 3.5), lambda t=target: t, shot_chance=0.35)


class DecoyRun(Scenario):
    """A player sprints wide and forward to drag a defender away from the ball."""

    type_code = "DECOY_RUN"

    def trigger(self) -> None:
        sim = self.sim
        side = sim.possession
        if side is None or sim.carrier is None:
            return
        candidates = self.free([p for p in sim.players(side)
                                if sim.role(p) in ("MID", "FWD") and p != sim.carrier])
        for runner in candidates:
            if not self.chance(0.03):
                continue
            xn, yn = sim.normalised(runner)
            target = sim.from_team(side, min(xn + 15, 92), 6 if yn < 50 else 94)
            self.start(runner, (2.0, 3.0), lambda t=target: t)


class Overlap(Scenario):
    """A full-back overtakes the wide midfielder on the ball, along the touchline."""

    type_code = "OVERLAP"
    #: Wide midfield slot -> the full-back behind it.
    FLANK = {5: 1, 8: 4}

    def trigger(self) -> None:
        sim = self.sim
        side = sim.possession
        if side is None or sim.carrier is None or sim.slot(sim.carrier) not in self.FLANK:
            return
        back_slot = self.FLANK[sim.slot(sim.carrier)]
        backs = self.free([p for p in sim.players(side) if sim.slot(p) == back_slot])
        if not backs or not self.chance(0.3):
            return
        carrier, yn = sim.carrier, (6 if back_slot == 1 else 94)

        def target(carrier=carrier):
            xn = sim.normalised(carrier)[0] if carrier in sim.side else 60
            return sim.from_team(side, min(xn + 10, 94), yn)

        self.start(backs[0], (3.0, 4.0), target, shot_chance=0.1)
