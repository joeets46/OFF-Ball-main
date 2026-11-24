-- =========================================================================
-- tracking -- Football player tracking (optical / GPS)
--
-- Source-only. NOT named in the upstream model's
-- operational_systems_of_records, and it owns none of the 153 in-scope MVM
-- tables: no upstream table holds a player position, so there is nothing for
-- it to feed. It is modeled because off-ball play -- what the 21 players
-- without the ball are doing -- exists nowhere else in the estate.
--
-- Native idiom modeled here:
--   * The frame is the native unit. Every player and the ball, 25 times a
--     second. player_frame_position is about three million rows per match
--     and is partitioned monthly, like tm_axs.scan.
--   * Coordinates are the vendor's, not the lakehouse's. Metres or
--     centimetres from the centre spot, and the attacking direction flips at
--     half time. capture and capture_period carry what is needed to
--     normalise; nothing is normalised at rest.
--   * Players are shirt numbers on a side. A raw feed says "home 9", not a
--     person; match_squad is what turns that into a player for one match.
--   * Data arrives as a file per match, and can arrive again. A vendor
--     re-delivers a capture after fixing player identity, so captures are
--     versioned and only one is current.
--   * Off-ball actions are detected, not observed. A model or an analyst
--     derives them from the frames, and re-running the model replaces them.
-- =========================================================================

CREATE SCHEMA IF NOT EXISTS tracking;

COMMENT ON SCHEMA tracking IS
    'Football player tracking (optical / GPS) -- frame-by-frame positions of '
    'every player and the ball, and the off-ball actions derived from them. '
    'Source-only: owns no upstream target table. Extract pattern: file per '
    'match, keyed on capture.delivered_at.';
