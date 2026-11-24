-- =========================================================================
-- tracking -- foreign keys
--
-- A capture's frames and positions cascade from it: they have no meaning
-- outside the recording that produced them, so when a superseded capture is
-- finally purged it goes whole. Players and vocabularies do not cascade: a player's
-- positions outlive any one squad entry, and a zone in use must stay.
--
-- No foreign key leaves the schema. hudl_game_id, tm_axs_event_code,
-- hudl_player_id, sfsf_person_id_external and led_to_hudl_instance_id are
-- business keys into other databases, resolved through common.entity_xref.
-- =========================================================================

ALTER TABLE tracking.match_squad
    ADD CONSTRAINT fk_match_squad_match
        FOREIGN KEY (match_id) REFERENCES tracking.match (match_id)
        ON DELETE CASCADE;

ALTER TABLE tracking.match_squad
    ADD CONSTRAINT fk_match_squad_player
        FOREIGN KEY (player_id) REFERENCES tracking.player (player_id)
        ON DELETE RESTRICT;

ALTER TABLE tracking.capture
    ADD CONSTRAINT fk_capture_match
        FOREIGN KEY (match_id) REFERENCES tracking.match (match_id)
        ON DELETE RESTRICT;

ALTER TABLE tracking.capture_period
    ADD CONSTRAINT fk_capture_period_capture
        FOREIGN KEY (capture_id) REFERENCES tracking.capture (capture_id)
        ON DELETE CASCADE;

ALTER TABLE tracking.frame
    ADD CONSTRAINT fk_frame_capture
        FOREIGN KEY (capture_id) REFERENCES tracking.capture (capture_id)
        ON DELETE CASCADE;

ALTER TABLE tracking.frame
    ADD CONSTRAINT fk_frame_ball_carrier
        FOREIGN KEY (ball_carrier_player_id) REFERENCES tracking.player (player_id)
        ON DELETE RESTRICT;

ALTER TABLE tracking.player_frame_position
    ADD CONSTRAINT fk_player_frame_position_frame
        FOREIGN KEY (frame_id) REFERENCES tracking.frame (frame_id)
        ON DELETE CASCADE;

ALTER TABLE tracking.player_frame_position
    ADD CONSTRAINT fk_player_frame_position_player
        FOREIGN KEY (player_id) REFERENCES tracking.player (player_id)
        ON DELETE RESTRICT;

ALTER TABLE tracking.off_ball_action
    ADD CONSTRAINT fk_off_ball_action_match
        FOREIGN KEY (match_id) REFERENCES tracking.match (match_id)
        ON DELETE RESTRICT;

ALTER TABLE tracking.off_ball_action
    ADD CONSTRAINT fk_off_ball_action_player
        FOREIGN KEY (player_id) REFERENCES tracking.player (player_id)
        ON DELETE RESTRICT;

ALTER TABLE tracking.off_ball_action
    ADD CONSTRAINT fk_off_ball_action_type
        FOREIGN KEY (off_ball_action_type_id)
        REFERENCES tracking.off_ball_action_type (off_ball_action_type_id)
        ON DELETE RESTRICT;

-- SET NULL, not CASCADE: an action outlives the capture it was measured on,
-- because analysts also code actions with no capture at all.
ALTER TABLE tracking.off_ball_action
    ADD CONSTRAINT fk_off_ball_action_start_frame
        FOREIGN KEY (start_frame_id) REFERENCES tracking.frame (frame_id)
        ON DELETE SET NULL;

ALTER TABLE tracking.off_ball_action
    ADD CONSTRAINT fk_off_ball_action_end_frame
        FOREIGN KEY (end_frame_id) REFERENCES tracking.frame (frame_id)
        ON DELETE SET NULL;

ALTER TABLE tracking.off_ball_action_zone
    ADD CONSTRAINT fk_off_ball_action_zone_action
        FOREIGN KEY (off_ball_action_id) REFERENCES tracking.off_ball_action (off_ball_action_id)
        ON DELETE CASCADE;

ALTER TABLE tracking.off_ball_action_zone
    ADD CONSTRAINT fk_off_ball_action_zone_zone
        FOREIGN KEY (pitch_zone_id) REFERENCES tracking.pitch_zone (pitch_zone_id)
        ON DELETE RESTRICT;

ALTER TABLE tracking.off_ball_action_zone
    ADD CONSTRAINT fk_off_ball_action_zone_entered_frame
        FOREIGN KEY (entered_frame_id) REFERENCES tracking.frame (frame_id)
        ON DELETE SET NULL;
