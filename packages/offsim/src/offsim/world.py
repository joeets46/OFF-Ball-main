"""Build the whole world: clubs, squads, matches, and every frame of every capture.

Clubs, players, matches and squads are small and built up front. Frames are
not: a full match is about three million positions, so each match is
simulated on demand from its own seed. That lets a sink stream a season
without holding it in memory, and lets one match be rebuilt on its own.

Inside the simulation everything is in metres in the *home frame*: origin at
the bottom-left corner behind the home goal, home attacking towards +x. Only
on the way out is a position converted to what a tracking vendor delivers:
origin at the centre spot, metres or centimetres, and the ends swapped at
half time. Those three conversions are exactly the traps docs/07 describes,
and the data is built to contain them.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterator, Protocol, Sequence

from .config import DEFAULT_SEED, TEAMS, Profile
from .registry import Registry
from .rng import rng_for

SEASON_START = datetime(2026, 2, 7, 15, 0, tzinfo=timezone.utc)
HALF_TIME = timedelta(minutes=15)
#: Files arrive hours after full time, never live.
DELIVERY_DELAY = timedelta(hours=3)

#: A 4-4-2 in team-frame normalised coordinates: 0..100, attacking towards
#: x = 100, y = 0 on the team's right.
FORMATION: tuple[tuple[str, float, float], ...] = (
    ("GK", 6, 50),
    ("DEF", 22, 15), ("DEF", 20, 38), ("DEF", 20, 62), ("DEF", 22, 85),
    ("MID", 45, 15), ("MID", 42, 38), ("MID", 42, 62), ("MID", 45, 85),
    ("FWD", 62, 40), ("FWD", 62, 60),
)
SUBSTITUTE_ROLES = ("GK", "DEF", "MID", "MID", "FWD")

#: Movement, in SI units.
CRUISE_SHARE = 0.55       # share of top speed used when not sprinting
ACCELERATION = 3.5        # m/s^2
STEERING_GAIN = 1.2       # 1/s: how hard a player closes on their target
PASS_SPEED = 15.0         # m/s along the ground
TURNOVER_CHANCE = 0.15    # per completed pass
DEAD_BALL_CHANCE = 0.04   # per completed pass: out of play, a foul


# ---------------------------------------------------------------------------
# Masters
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Team:
    key: int
    name: str
    short_name: str
    #: The home ground's pitch, Law 1: 90-120 m by 45-90 m.
    pitch_length_m: float
    pitch_width_m: float


@dataclass(frozen=True)
class Player:
    player_id: int
    team_key: int
    display_name: str
    shirt_number: int
    role: str                # GK | DEF | MID | FWD
    #: Index into FORMATION for a starter; -1 for a substitute.
    slot: int
    max_speed_mps: float
    hudl_player_id: str
    sfsf_person_id_external: str

    def row(self) -> dict:
        return {
            "player_id": self.player_id,
            "display_name": self.display_name,
            "hudl_player_id": self.hudl_player_id,
            "sfsf_person_id_external": self.sfsf_person_id_external,
        }


@dataclass(frozen=True)
class Match:
    index: int
    match_id: int
    home: Team
    away: Team
    kickoff_at: datetime
    hudl_game_id: str
    tm_axs_event_code: str
    home_attacks_positive_x_first: bool
    #: The unit the vendor delivers this match in. Alternates, on purpose.
    coordinate_unit: str
    #: Whether GPS vests produced a second, non-primary capture.
    has_gps_capture: bool

    @property
    def pitch_length_m(self) -> float:
        return self.home.pitch_length_m

    @property
    def pitch_width_m(self) -> float:
        return self.home.pitch_width_m

    def home_attacks_positive_x(self, period: int) -> bool:
        return self.home_attacks_positive_x_first if period == 1 else not self.home_attacks_positive_x_first

    def row(self) -> dict:
        return {
            "match_id": self.match_id,
            "hudl_game_id": self.hudl_game_id,
            "tm_axs_event_code": self.tm_axs_event_code,
            "kickoff_at": self.kickoff_at,
            "home_team_name": self.home.name,
            "away_team_name": self.away.name,
            "pitch_length_m": self.pitch_length_m,
            "pitch_width_m": self.pitch_width_m,
        }


@dataclass(frozen=True)
class SquadEntry:
    match_id: int
    player_id: int
    team_side: str           # H | A
    shirt_number: int
    is_starter: bool
    is_goalkeeper: bool

    def row(self) -> dict:
        return {
            "match_id": self.match_id,
            "player_id": self.player_id,
            "team_side": self.team_side,
            "shirt_number": self.shirt_number,
            "is_starter": self.is_starter,
            "is_goalkeeper": self.is_goalkeeper,
        }


# ---------------------------------------------------------------------------
# Captures and frames
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Capture:
    match: Match
    method: str              # optical | gps
    fps: int
    coordinate_unit: str
    is_primary: bool
    delivery_version: int
    delivered_at: datetime
    frames_per_period: int

    @property
    def key(self) -> tuple[int, str, int]:
        """What identifies a capture before the database gives it an id."""
        return (self.match.match_id, self.method, self.delivery_version)

    def row(self) -> dict:
        return {
            "_capture": self.key,
            "match_id": self.match.match_id,
            "capture_method": self.method,
            "delivery_version": self.delivery_version,
            "is_current": True,
            "is_primary": self.is_primary,
            "frames_per_second": self.fps,
            "coordinate_unit": self.coordinate_unit,
            "coordinate_origin": "centre",
            "delivered_at": self.delivered_at,
        }

    def period_rows(self) -> list[dict]:
        n = self.frames_per_period
        return [
            {
                "_capture": self.key,
                "period": period,
                "start_frame_number": (period - 1) * n,
                "end_frame_number": period * n - 1,
                "home_attacks_positive_x": self.match.home_attacks_positive_x(period),
            }
            for period in (1, 2)
        ]


@dataclass(slots=True)
class Frame:
    frame_number: int
    period: int
    captured_at: datetime
    period_clock_ms: int
    ball: tuple[float, float, float] | None
    ball_status: str
    possession_side: str | None
    ball_carrier_player_id: int | None
    #: (player_id, x, y, speed_mps), in the capture's units and origin.
    positions: list[tuple[int, float, float, float]]

    def row(self, capture: Capture) -> dict:
        ball = self.ball or (None, None, None)
        return {
            "_capture": capture.key,
            "frame_number": self.frame_number,
            "period": self.period,
            "captured_at": self.captured_at,
            "period_clock_ms": self.period_clock_ms,
            "ball_x": ball[0],
            "ball_y": ball[1],
            "ball_z": ball[2],
            "ball_status": self.ball_status,
            "possession_side": self.possession_side,
            "ball_carrier_player_id": self.ball_carrier_player_id,
        }

    def position_rows(self, capture: Capture) -> Iterator[dict]:
        for player_id, x, y, speed in self.positions:
            yield {
                "_capture": capture.key,
                "_frame_number": self.frame_number,
                "player_id": player_id,
                "captured_at": self.captured_at,
                "x": x,
                "y": y,
                "speed_mps": speed,
            }


@dataclass
class OffBallAction:
    """A planted off-ball action, in frame numbers of the optical capture."""

    player_id: int
    type_code: str
    start_frame_number: int
    end_frame_number: int
    zone_codes: list[str] = field(default_factory=list)
    led_to_hudl_instance_id: str | None = None


class Scenario(Protocol):
    """Something that steers players for a while and records what it did.

    Called once per frame, before players move. Returns target overrides --
    player_id -> (x, y, sprint) in home-frame metres -- and appends to
    ``sim.actions`` when an action completes.
    """

    def step(self, sim: "MatchSim") -> dict[int, tuple[float, float, bool]]: ...


class Recording:
    """One capture of one match: its rows, its frames, and what was planted.

    ``frames()`` simulates as it goes. ``actions`` is complete once the frames
    have been read to the end.
    """

    def __init__(self, world: "World", capture: Capture, scenarios: Sequence[Scenario]):
        self.world = world
        self.capture = capture
        self.scenarios = scenarios
        self.actions: list[OffBallAction] = []

    def frames(self) -> Iterator[Frame]:
        match = self.capture.match
        sim = MatchSim(self.world, match, self.world.profile.fps,
                       rng_for(self.world.seed, "match", match.match_id, "motion"),
                       self.scenarios)
        self.actions = sim.actions
        if self.capture.method == "optical":
            yield from (self._vendor(f) for f in sim.run())
            return
        # GPS vests: a lower rate, no ball, a little positional noise. Sampled
        # from the same simulated match so the two captures agree.
        noise = rng_for(self.world.seed, "match", match.match_id, "gps")
        ratio = self.world.profile.fps / self.capture.fps
        next_k = {1: 0, 2: 0}
        for f in sim.run():
            period_index = f.frame_number - (f.period - 1) * sim.frames_per_period
            k = next_k[f.period]
            if k >= self.capture.frames_per_period or period_index != math.floor(k * ratio):
                continue
            next_k[f.period] = k + 1
            f.frame_number = (f.period - 1) * self.capture.frames_per_period + k
            f.period_clock_ms = round(k * 1000 / self.capture.fps)
            f.ball, f.possession_side, f.ball_carrier_player_id = None, None, None
            f.ball_status = "alive"
            f.positions = [(p, x + noise.gauss(0, 0.3), y + noise.gauss(0, 0.3), s)
                           for p, x, y, s in f.positions]
            yield self._vendor(f)

    def _vendor(self, f: Frame) -> Frame:
        """Home-frame metres -> the capture's units, centre origin, period direction."""
        match = self.capture.match
        half_l, half_w = match.pitch_length_m / 2, match.pitch_width_m / 2
        flip = -1.0 if not match.home_attacks_positive_x(f.period) else 1.0
        scale = 100.0 if self.capture.coordinate_unit == "cm" else 1.0

        def conv(x: float, y: float) -> tuple[float, float]:
            return (round(flip * (x - half_l) * scale, 2), round(flip * (y - half_w) * scale, 2))

        if f.ball is not None:
            bx, by = conv(f.ball[0], f.ball[1])
            f.ball = (bx, by, round(f.ball[2] * scale, 2))
        f.positions = [(p, *conv(x, y), round(s, 2)) for p, x, y, s in f.positions]
        return f


# ---------------------------------------------------------------------------
# The world
# ---------------------------------------------------------------------------

@dataclass
class World:
    profile: Profile
    seed: int
    teams: list[Team]
    players: list[Player]
    matches: list[Match]
    squads: list[SquadEntry]
    #: match_id -> side -> (starter slot replaced at half time, substitute id)
    substitutions: dict[int, dict[str, tuple[int, int]]]
    scenarios: tuple[Scenario, ...] = ()

    def team_players(self, team_key: int) -> list[Player]:
        return [p for p in self.players if p.team_key == team_key]

    def squad(self, match: Match) -> list[SquadEntry]:
        return [s for s in self.squads if s.match_id == match.match_id]

    def lineup(self, match: Match, period: int) -> list[tuple[int, str, int]]:
        """(player_id, side, formation slot) for everyone on the pitch in ``period``."""
        out = []
        for side, team in (("H", match.home), ("A", match.away)):
            off_slot, sub_id = self.substitutions[match.match_id][side]
            for p in self.team_players(team.key):
                if p.slot < 0:
                    continue
                if period == 2 and p.slot == off_slot:
                    out.append((sub_id, side, p.slot))
                else:
                    out.append((p.player_id, side, p.slot))
        return out

    def captures(self, match: Match, delivery_version: int = 1) -> list[Capture]:
        period_seconds = self.profile.period_minutes * 60
        full_time = match.kickoff_at + HALF_TIME + timedelta(seconds=2 * period_seconds)
        delivered = full_time + DELIVERY_DELAY + timedelta(days=delivery_version - 1)
        out = [Capture(match, "optical", self.profile.fps, match.coordinate_unit, True,
                       delivery_version, delivered, round(period_seconds * self.profile.fps))]
        if match.has_gps_capture:
            out.append(Capture(match, "gps", self.profile.gps_fps, "m", False,
                               delivery_version, delivered,
                               round(period_seconds * self.profile.gps_fps)))
        return out

    def record(self, capture: Capture) -> Recording:
        return Recording(self, capture, self.scenarios)


def build_world(profile: Profile, seed: int = DEFAULT_SEED,
                scenarios: Sequence[Scenario] = ()) -> World:
    registry = Registry(seed)
    teams = [_team(key, seed) for key in range(TEAMS)]

    players: list[Player] = []
    for team in teams:
        roles = [(role, slot) for slot, (role, _, _) in enumerate(FORMATION)]
        roles += [(role, -1) for role in SUBSTITUTE_ROLES]
        for index, (role, slot) in enumerate(roles):
            player_id = registry.player_id(team.key, index)
            r = rng_for(seed, "player", player_id)
            top = r.uniform(7.8, 8.6) if role == "GK" else r.uniform(8.6, 9.8)
            players.append(Player(
                player_id=player_id, team_key=team.key,
                display_name=f"{team.short_name} {index + 1}",
                shirt_number=index + 1, role=role, slot=slot,
                max_speed_mps=round(top, 2),
                hudl_player_id=registry.hudl_player_id(player_id),
                sfsf_person_id_external=registry.sfsf_person_id(player_id),
            ))

    fixtures = _double_round_robin(TEAMS)
    if profile.matches > len(fixtures):
        raise ValueError(f"at most {len(fixtures)} matches with {TEAMS} teams")

    matches, squads, substitutions = [], [], {}
    per_round = TEAMS // 2
    for index in range(profile.matches):
        home_key, away_key = fixtures[index]
        match_id = registry.match_id(index)
        r = rng_for(seed, "match", match_id)
        match = Match(
            index=index, match_id=match_id,
            home=teams[home_key], away=teams[away_key],
            kickoff_at=SEASON_START + timedelta(weeks=index // per_round,
                                                hours=2.5 * (index % per_round)),
            hudl_game_id=registry.hudl_game_id(match_id),
            tm_axs_event_code=registry.tm_axs_event_code(match_id),
            home_attacks_positive_x_first=r.random() < 0.5,
            coordinate_unit="cm" if index % 2 else "m",
            has_gps_capture=bool(index % 2),
        )
        matches.append(match)
        substitutions[match_id] = {}
        for side, team in (("H", match.home), ("A", match.away)):
            squad = [p for p in players if p.team_key == team.key]
            squads += [SquadEntry(match_id, p.player_id, side, p.shirt_number,
                                  p.slot >= 0, p.role == "GK") for p in squad]
            substitutions[match_id][side] = _half_time_sub(squad, r)

    return World(profile, seed, teams, players, matches, squads, substitutions,
                 tuple(scenarios))


def _team(key: int, seed: int) -> Team:
    r = rng_for(seed, "team", key)
    letter = "ABCDEFGH"[key]
    return Team(key=key, name=f"Club {letter}", short_name=letter * 3,
                pitch_length_m=float(r.choice((100, 102, 105, 105, 110))),
                pitch_width_m=float(r.choice((64, 66, 68, 68, 70))))


def _double_round_robin(n: int) -> list[tuple[int, int]]:
    """Circle-method rounds, then the same rounds with home and away swapped."""
    teams = list(range(n))
    rounds = []
    for _ in range(n - 1):
        rounds.append([(teams[i], teams[n - 1 - i]) for i in range(n // 2)])
        teams = [teams[0], teams[-1], *teams[1:-1]]
    first = [pair for rnd in rounds for pair in rnd]
    return first + [(away, home) for home, away in first]


def _half_time_sub(squad: list[Player], r: random.Random) -> tuple[int, int]:
    """One outfield starter off at half time, replaced by a substitute of the same role."""
    starter = r.choice([p for p in squad if p.slot > 0])
    bench = [p for p in squad if p.slot < 0 and p.role == starter.role]
    return starter.slot, bench[0].player_id


# ---------------------------------------------------------------------------
# The simulation
# ---------------------------------------------------------------------------

class MatchSim:
    """Moves 22 players and a ball, one frame at a time, in home-frame metres.

    Deliberately simple: each player steers towards a formation spot that
    shifts with the ball and with possession, plus slow random drift. The
    ball is passed between teammates and sometimes lost. Scenarios layer
    recognisable off-ball movement on top.
    """

    def __init__(self, world: World, match: Match, fps: int, rng: random.Random,
                 scenarios: Sequence[Scenario] = ()):
        self.world, self.match, self.rng = world, match, rng
        self.scenarios = scenarios
        self.fps = fps
        self.dt = 1.0 / fps
        self.length, self.width = match.pitch_length_m, match.pitch_width_m
        self.frames_per_period = round(world.profile.period_minutes * 60 * fps)
        self.by_id = {p.player_id: p for p in world.players}
        self.actions: list[OffBallAction] = []
        # Live state, reset at each kickoff.
        self.period = 1
        self.frame_number = 0
        self.on_pitch: list[tuple[int, str, int]] = []
        self.side: dict[int, str] = {}
        self._slot: dict[int, int] = {}
        self.pos: dict[int, list[float]] = {}
        self.vel: dict[int, list[float]] = {}
        self.drift: dict[int, list[float]] = {}
        self.ball = [0.0, 0.0, 0.0]
        self.carrier: int | None = None
        self.possession: str | None = None
        self._flight: tuple[list[float], list[float], float, float, int] | None = None
        self._hold = 0.0
        self._dead = 0.0

    # -- frames of reference ------------------------------------------------

    def to_home(self, side: str, x: float, y: float) -> tuple[float, float]:
        """Team-frame metres -> home-frame metres. Its own inverse."""
        return (x, y) if side == "H" else (self.length - x, self.width - y)

    def team_x(self, side: str, x_home: float) -> float:
        """How far up the pitch a home-frame x is, for ``side``, in metres."""
        return x_home if side == "H" else self.length - x_home

    def anchor(self, player_id: int) -> tuple[float, float]:
        """Where the formation wants this player now, in home-frame metres."""
        side = self.side[player_id]
        role, fx, fy = FORMATION[self._slot[player_id]]
        bx, by = self.to_home(side, self.ball[0], self.ball[1])
        bxn, byn = bx / self.length * 100, by / self.width * 100
        if role == "GK":
            fy += 0.1 * (byn - 50)
        else:
            if self.possession is not None:
                fx += 12 if self.possession == side else -6
            fx += 0.25 * (bxn - 50)
            fy += 0.2 * (byn - 50)
        fx, fy = min(max(fx, 2), 98), min(max(fy, 2), 98)
        return self.to_home(side, fx / 100 * self.length, fy / 100 * self.width)

    # -- the loop -----------------------------------------------------------

    def run(self) -> Iterator[Frame]:
        match = self.match
        for period in (1, 2):
            self._kickoff(period)
            start = match.kickoff_at + (period - 1) * (
                timedelta(minutes=self.world.profile.period_minutes) + HALF_TIME)
            for i in range(self.frames_per_period):
                self.frame_number = (period - 1) * self.frames_per_period + i
                overrides: dict[int, tuple[float, float, bool]] = {}
                for scenario in self.scenarios:
                    overrides.update(scenario.step(self))
                self._move_players(overrides)
                self._move_ball()
                yield Frame(
                    frame_number=self.frame_number, period=period,
                    captured_at=start + timedelta(milliseconds=i * 1000 / self.fps),
                    period_clock_ms=round(i * 1000 / self.fps),
                    ball=(self.ball[0], self.ball[1], self.ball[2]),
                    ball_status="dead" if self._dead > 0 else "alive",
                    possession_side=self.possession,
                    ball_carrier_player_id=self.carrier,
                    positions=[(pid, self.pos[pid][0], self.pos[pid][1],
                                math.hypot(*self.vel[pid])) for pid, _, _ in self.on_pitch],
                )

    def _kickoff(self, period: int) -> None:
        self.period = period
        self.on_pitch = self.world.lineup(self.match, period)
        self.side = {pid: side for pid, side, _ in self.on_pitch}
        self._slot = {pid: slot for pid, _, slot in self.on_pitch}
        self.ball = [self.length / 2, self.width / 2, 0.0]
        self.possession = None
        for pid, _, _ in self.on_pitch:
            self.pos[pid] = list(self.anchor(pid))
            self.vel[pid] = [0.0, 0.0]
            self.drift.setdefault(pid, [0.0, 0.0])
        kicking = "H" if period == 1 else "A"
        forwards = [pid for pid, side, slot in self.on_pitch
                    if side == kicking and FORMATION[slot][0] == "FWD"]
        self.carrier = forwards[0]
        self.possession = kicking
        self._flight, self._dead = None, 0.0
        self._hold = self.rng.uniform(1.0, 3.0)

    def _move_players(self, overrides: dict[int, tuple[float, float, bool]]) -> None:
        dt, rng = self.dt, self.rng
        for pid, side, _ in self.on_pitch:
            player = self.by_id[pid]
            if pid in overrides:
                tx, ty, sprint = overrides[pid]
            else:
                tx, ty = self.anchor(pid)
                sprint = False
                # Slow random drift around the formation spot.
                d = self.drift[pid]
                d[0] += -0.5 * d[0] * dt + 3.0 * math.sqrt(dt) * rng.gauss(0, 1)
                d[1] += -0.5 * d[1] * dt + 3.0 * math.sqrt(dt) * rng.gauss(0, 1)
                tx, ty = tx + d[0], ty + d[1]
                if pid == self.carrier:
                    # Carry the ball forwards.
                    tx += 6 if side == "H" else -6
            cap = player.max_speed_mps * (1.0 if sprint else CRUISE_SHARE)
            px, py = self.pos[pid]
            want_x, want_y = (tx - px) * STEERING_GAIN, (ty - py) * STEERING_GAIN
            want = math.hypot(want_x, want_y)
            if want > cap:
                want_x, want_y = want_x * cap / want, want_y * cap / want
            v = self.vel[pid]
            dvx, dvy = want_x - v[0], want_y - v[1]
            dv = math.hypot(dvx, dvy)
            limit = ACCELERATION * dt
            if dv > limit:
                dvx, dvy = dvx * limit / dv, dvy * limit / dv
            v[0] += dvx
            v[1] += dvy
            self.pos[pid] = [min(max(px + v[0] * dt, -1.0), self.length + 1.0),
                             min(max(py + v[1] * dt, -1.0), self.width + 1.0)]

    def _move_ball(self) -> None:
        rng, dt = self.rng, self.dt
        if self._dead > 0:
            self._dead -= dt
            if self._dead <= 0:
                self.carrier = self._nearest(self.possession)
                self._hold = rng.uniform(1.0, 3.0)
            return
        if self._flight is not None:
            start, end, elapsed, duration, receiver = self._flight
            elapsed += dt
            s = min(elapsed / duration, 1.0)
            dist = math.dist(start, end)
            self.ball = [start[0] + (end[0] - start[0]) * s,
                         start[1] + (end[1] - start[1]) * s,
                         4 * min(6.0, dist * 0.06) * s * (1 - s)]
            self._flight = (start, end, elapsed, duration, receiver)
            if s >= 1.0:
                self._flight = None
                roll = rng.random()
                if roll < DEAD_BALL_CHANCE:
                    self._dead = rng.uniform(2.0, 5.0)
                elif roll < DEAD_BALL_CHANCE + TURNOVER_CHANCE:
                    self.possession = "A" if self.possession == "H" else "H"
                    self.carrier = self._nearest(self.possession)
                else:
                    self.carrier = receiver
                self._hold = rng.uniform(1.5, 5.0)
            return
        if self.carrier is None:
            return
        cx, cy = self.pos[self.carrier]
        self.ball = [cx, cy, 0.0]
        self._hold -= dt
        if self._hold <= 0:
            self._pass()

    def _pass(self) -> None:
        carrier, side = self.carrier, self.side[self.carrier]
        mates = [pid for pid, s, _ in self.on_pitch if s == side and pid != carrier]
        here = self.team_x(side, self.pos[carrier][0])
        weights = [0.2 if self.by_id[pid].role == "GK"
                   else 1 + max(0.0, self.team_x(side, self.pos[pid][0]) - here) / 10
                   for pid in mates]
        receiver = self.rng.choices(mates, weights)[0]
        start, end = list(self.ball[:2]), list(self.pos[receiver])
        duration = max(0.3, math.dist(start, end) / PASS_SPEED)
        self._flight = (start, end, 0.0, duration, receiver)
        self.carrier = None

    def _nearest(self, side: str | None) -> int:
        candidates = [pid for pid, s, _ in self.on_pitch if s == side]
        return min(candidates, key=lambda pid: math.dist(self.pos[pid], self.ball[:2]))
