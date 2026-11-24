# offsim

Seeded fake data for the OFF-Ball `tracking` schema: football off-ball
player tracking. Clubs, squads and fixtures, then every player and the ball
25 times a second in the vendor's own coordinates, with runs, presses and
marks planted in the movement. The same seed always builds the same world.

It writes to its own database, `offball_sim`, never to the main `offball`.

## Commands

Start the database first (`docker compose up -d` from the repository root).

```bash
uv run offsim backfill --profile small --reset   # build a world and write it
uv run offsim validate                           # 4 business checks + DQ checks
uv run offsim run --ticks 6 --interval 5         # act like a live vendor
```

| Profile | Matches | Periods | Positions |
|---|--:|---|--:|
| `small` | 2 | 2 × 5 min | ~0.8 million |
| `medium` | 4 | 2 × 45 min | ~12 million |
| `full` | 12 | 2 × 45 min | ~36 million |

`--reset` drops and recreates the simulation database and loads the `common`
and `tracking` DDL from `models/physical/`; it refuses any database whose name
does not start with `offball_sim`. `--out DIR` writes vendor-style JSON files
instead of a database. `run` needs the seed the database was backfilled with.

## What is in the data on purpose

The traps from [docs/07](../../docs/07-integration-contract.md), so the checks
have something real to catch:

- every second match is delivered in **centimetres**, and has a second,
  non-primary **GPS capture at 10 fps** with no ball;
- teams **change ends at half time**, and each team makes a **substitution**;
- `run` **re-delivers** matches (a new capture version) and **re-runs the
  detection model**, which really deletes rows and fills the change log.

## The four business checks (`validate`)

1. One current primary capture per match.
2. Frame count matches `frames_per_second` × seconds played.
3. At most 11 players per side in a frame, all in the match squad.
4. Positions normalise onto the pitch (unit, origin, size, direction).

`tests/test_integration.py` breaks the data in each of those four ways and
proves exactly the matching check fails.

## Layout

| Module | Role |
|---|---|
| `config` | profiles, seed, database settings |
| `rng`, `registry` | one random stream per thing; vendor ids and business keys |
| `schema` | the tracking columns, parsed from the DDL |
| `world` | clubs, squads, fixtures and the frame-by-frame simulation |
| `values/` | invented names, pitch sizes, zones read from the DDL |
| `scenarios/` | run in behind, decoy run, overlap, press, mark |
| `lifecycle` | detection, re-delivery, model re-run |
| `sink/` | PostgreSQL (COPY) and vendor-style files |
| `backfill`, `stream/` | write it all at once, or as a live stream |
| `validate`, `dq` | business checks and technical checks |
