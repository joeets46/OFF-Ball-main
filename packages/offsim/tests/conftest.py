"""Shared fixtures for the offsim tests.

World tests play 12-second periods: enough for passes, turnovers and the half-
time switch, at a fraction of the cost of the five-minute ``small`` profile.
"""

from __future__ import annotations

import dataclasses

import pytest

from offsim.config import PROFILES
from offsim.world import build_world

SEED = 7
TINY = dataclasses.replace(PROFILES["small"], name="tiny", period_minutes=0.2)


@pytest.fixture(scope="session")
def seed():
    return SEED


@pytest.fixture(scope="session")
def tiny():
    return TINY


@pytest.fixture(scope="session")
def world():
    return build_world(TINY, SEED)


@pytest.fixture(scope="session")
def recorded(world):
    """Every capture of every match, frames read once: capture -> (recording, frames)."""
    out = {}
    for match in world.matches:
        for capture in world.captures(match):
            recording = world.record(capture)
            out[capture.key] = (recording, list(recording.frames()))
    return out
