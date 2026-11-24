"""Pitch sizes and pitch zones.

Sizes stay inside Law 1 (length 90-120 m, width 45-90 m), and vary on
purpose: normalising with one default size is a trap docs/07 names.

Zones are read from the seed rows in the tracking DDL rather than copied, so
the zones a scenario reports are exactly the zones the database holds.
"""

from __future__ import annotations

import random
import re
from functools import cache

from ..config import tracking_ddl_dir

_LENGTHS = (100.0, 102.0, 105.0, 105.0, 110.0)
_WIDTHS = (64.0, 66.0, 68.0, 68.0, 70.0)

_ZONE_ROW = re.compile(
    r"\('([A-Z_]+)',\s*'[^']*',\s*([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)\)"
)


def pitch_size(r: random.Random) -> tuple[float, float]:
    return r.choice(_LENGTHS), r.choice(_WIDTHS)


@cache
def zones() -> dict[str, tuple[float, float, float, float]]:
    """zone_code -> (x_min, x_max, y_min, y_max), from 20_reference.sql."""
    sql = (tracking_ddl_dir() / "20_reference.sql").read_text(encoding="utf-8")
    seed = sql.split("INSERT INTO tracking.pitch_zone", 1)[1].split(";", 1)[0]
    return {m.group(1): tuple(float(v) for v in m.groups()[1:]) for m in _ZONE_ROW.finditer(seed)}


def zones_at(xn: float, yn: float) -> list[str]:
    """Every zone containing a normalised, team-frame point. Zones overlap."""
    return [code for code, (x0, x1, y0, y1) in zones().items()
            if x0 <= xn <= x1 and y0 <= yn <= y1]
