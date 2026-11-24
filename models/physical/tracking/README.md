# `tracking` — Football player tracking (optical / GPS)

Tier **A**. 12 base tables plus 13 partitions, owning **0** of the 153 in-scope target tables.

**Source-only.** Not named in the upstream model, and it owns no target
table by design: no upstream table holds what this system records. See
[../../../docs/05-source-systems.md](../../../docs/05-source-systems.md).

## Native idiom modeled here

- **The frame is the native unit.** Every player and the ball, 25 times a second: `player_frame_position` is about three million rows per match, partitioned monthly like `tm_axs.scan`.
- **Coordinates are the vendor's.** Metres or centimetres from the centre spot, with the direction of play flipping at half time. `capture` and `capture_period` carry what normalising needs.
- **Players are shirt numbers on a side.** A raw feed says "home 9"; `match_squad` turns that into a player for one match.
- **Captures are versioned.** A vendor re-delivers a match after fixing player identity, so only the current primary capture is read.
- **`frame.ball_carrier_player_id` is what off-ball means**: every other player in the frame is off the ball.

## Target tables it owns

None. Everything here is source-tier data the target model cannot represent.

## Files

| File | Contents |
|---|---|
| `ddl/00_schema.sql` | Schema creation and the schema `COMMENT` |
| `ddl/20_reference.sql` | Configuration and reference data |
| `ddl/30_master.sql` | Master data |
| `ddl/40_transaction.sql` | Transactions, partitioned where volume warrants |
| `ddl/50_constraints.sql` | Foreign keys, declared last so one ordered pass loads |
| `ddl/60_indexes.sql` | Indexes serving named access paths |
| `ddl/70_audit.sql` | **GENERATED** -- watermark triggers, change log, role grants |
| `ddl/80_comments.sql` | Table descriptions, published by the data dictionary |

Numbered to load in order. `50_constraints.sql` runs after every table in
the schema exists, so a single forward pass works without deferred
constraints.

## Loading just this schema

```bash
bash tools/load.sh tracking
```

Cross-system references in this schema are business-key columns with no
`REFERENCES` clause, resolved through `common.entity_xref`. No foreign key
here crosses a schema boundary, which `offball-check` enforces.
