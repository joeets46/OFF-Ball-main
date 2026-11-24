"""Profiles, the seed, and where things live.

A profile says how much world to build. The volume is in the positions: 22
players at 25 frames a second is 1,320 rows per match-second, so a full
90-minute match is about three million rows and ``small`` stays small by
playing short periods, not by thinning the frames.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

#: The seed used when none is given. Any integer works; the same one always
#: rebuilds the same world.
DEFAULT_SEED = 20260207

#: Four clubs: enough for a double round robin of 12 matches.
TEAMS = 4

#: The database offsim writes to. Deliberately not the main `offball`
#: database, so simulated rows never mix with a working copy of the model.
SIM_DATABASE = "offball_sim"


@dataclass(frozen=True)
class Profile:
    name: str
    matches: int
    #: Length of each of the two periods. A float so tests can play seconds.
    period_minutes: float
    #: Optical capture rate. GPS captures run at their own, lower rate.
    fps: int = 25
    gps_fps: int = 10


PROFILES: dict[str, Profile] = {
    "small": Profile("small", matches=2, period_minutes=5),
    "medium": Profile("medium", matches=4, period_minutes=45),
    "full": Profile("full", matches=12, period_minutes=45),
}


def repo_root() -> Path:
    """The OFF-Ball repository, which this package lives inside."""
    # packages/offsim/src/offsim/config.py -> parents[4] is the repo root.
    return Path(__file__).resolve().parents[4]


def tracking_ddl_dir() -> Path:
    return repo_root() / "models" / "physical" / "tracking" / "ddl"


def database_url(database: str = SIM_DATABASE) -> str:
    """Connection string for ``database``, from the same settings as the repo.

    ``OFFSIM_DATABASE_URL`` wins outright. Otherwise the POSTGRES_* values come
    from the environment or the repository's ``.env``, exactly as the test
    suite reads them, with only the database name changed.
    """
    if os.environ.get("OFFSIM_DATABASE_URL"):
        return os.environ["OFFSIM_DATABASE_URL"]
    values = dict(_read_dotenv())
    values.update({k: v for k, v in os.environ.items() if k.startswith("POSTGRES_")})
    user = values.get("POSTGRES_USER", "offball")
    password = values.get("POSTGRES_PASSWORD", "offball")
    host = values.get("POSTGRES_HOST", "localhost")
    port = values.get("POSTGRES_PORT", "55432")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def _read_dotenv() -> list[tuple[str, str]]:
    path = repo_root() / ".env"
    if not path.exists():
        return []
    pairs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            pairs.append((key.strip(), value.strip()))
    return pairs
