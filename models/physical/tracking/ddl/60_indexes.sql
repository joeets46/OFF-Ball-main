-- =========================================================================
-- tracking -- indexes
--
-- The dominant query is "where was this player, and who had the ball, over
-- this passage of this match": a frame range joined to positions. That join,
-- the off-ball action lookups and the per-match extract are what the indexes
-- here serve.
-- =========================================================================

-- -------------------------------------------------------------------------
-- Matches, players, squads.
-- -------------------------------------------------------------------------
CREATE INDEX ix_match_kickoff         ON tracking.match (kickoff_at DESC);
-- Resolution against the same fixture and athlete in other systems.
CREATE INDEX ix_match_hudl_game       ON tracking.match (hudl_game_id) WHERE hudl_game_id IS NOT NULL;
CREATE INDEX ix_player_hudl           ON tracking.player (hudl_player_id) WHERE hudl_player_id IS NOT NULL;
CREATE INDEX ix_player_sfsf
    ON tracking.player (sfsf_person_id_external) WHERE sfsf_person_id_external IS NOT NULL;
-- A player's matches. The match side is already the leading primary-key column.
CREATE INDEX ix_match_squad_player    ON tracking.match_squad (player_id);

-- -------------------------------------------------------------------------
-- Captures. One current primary capture per match: the one an extract reads.
-- A second would double every run and every metre covered.
-- -------------------------------------------------------------------------
CREATE UNIQUE INDEX ux_capture_one_current_primary
    ON tracking.capture (match_id) WHERE is_current AND is_primary;

-- -------------------------------------------------------------------------
-- Frames and positions. (capture_id, frame_number) is already indexed by its
-- UNIQUE constraint, which serves every frame-range read.
-- -------------------------------------------------------------------------
CREATE INDEX ix_frame_ball_carrier
    ON tracking.frame (ball_carrier_player_id) WHERE ball_carrier_player_id IS NOT NULL;
-- One player's trajectory across a match.
CREATE INDEX ix_player_frame_position_player_time
    ON tracking.player_frame_position (player_id, captured_at);

-- -------------------------------------------------------------------------
-- Off-ball actions.
-- -------------------------------------------------------------------------
CREATE INDEX ix_off_ball_action_match_player ON tracking.off_ball_action (match_id, player_id);
CREATE INDEX ix_off_ball_action_type  ON tracking.off_ball_action (off_ball_action_type_id);
-- "Which runs led to a shot" is the question off-ball analysis exists for.
CREATE INDEX ix_off_ball_action_led_to
    ON tracking.off_ball_action (led_to_hudl_instance_id) WHERE led_to_hudl_instance_id IS NOT NULL;
CREATE INDEX ix_off_ball_action_start_frame
    ON tracking.off_ball_action (start_frame_id) WHERE start_frame_id IS NOT NULL;
CREATE INDEX ix_off_ball_action_zone_zone ON tracking.off_ball_action_zone (pitch_zone_id);

-- -------------------------------------------------------------------------
-- Extraction watermarks. Frames and positions have none: they are read a
-- whole capture at a time, found through capture.delivered_at.
-- -------------------------------------------------------------------------
CREATE INDEX ix_capture_delivered_at  ON tracking.capture (delivered_at);
CREATE INDEX ix_match_updated_at      ON tracking.match (updated_at);
CREATE INDEX ix_player_updated_at     ON tracking.player (updated_at);
CREATE INDEX ix_match_squad_updated_at ON tracking.match_squad (updated_at);
CREATE INDEX ix_off_ball_action_updated_at ON tracking.off_ball_action (updated_at);
