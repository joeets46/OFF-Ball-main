"""Scenarios: recognisable off-ball movement planted in the simulation.

Each is a class built once per simulated match with its own random stream,
so adding or tuning one scenario never shifts another's numbers. Five of the
seven seeded action types are planted; COVER and RECOVERY_RUN are left for
analysts to code by hand.
"""

from __future__ import annotations

from .marking import Mark
from .pressing import Press
from .runs import DecoyRun, Overlap, RunInBehind

DEFAULT_SCENARIOS = (RunInBehind, DecoyRun, Overlap, Press, Mark)

__all__ = ["DEFAULT_SCENARIOS", "DecoyRun", "Mark", "Overlap", "Press", "RunInBehind"]
