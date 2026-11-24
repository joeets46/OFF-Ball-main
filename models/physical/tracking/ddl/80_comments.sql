-- =========================================================================
-- tracking -- table comments
-- =========================================================================

COMMENT ON TABLE tracking.pitch_zone IS
    'Named areas of a normalised 0..100 pitch -- thirds, the box, the half-spaces. What makes space something a query can ask about.';
COMMENT ON TABLE tracking.off_ball_action_type IS
    'Kinds of off-ball action, each in or out of possession: a run in behind, a decoy run, a press, a mark.';
COMMENT ON TABLE tracking.match IS
    'The tracking vendor''s record of a fixture, and the only place the pitch size lives. The same fixture exists as hudl.game and tm_axs.event.';
COMMENT ON TABLE tracking.player IS
    'The athlete as the tracking vendor knows them: a third record of the same person, after sap_sfsf.per_person and hudl.player.';
COMMENT ON TABLE tracking.match_squad IS
    'Which shirt number each player wore on which side in one match. Raw frames say "home 9"; this is what makes that a person.';
COMMENT ON TABLE tracking.capture IS
    'One delivered recording of one match, with its frame rate and coordinate system. Versioned, because vendors re-deliver after fixing player identity.';
COMMENT ON TABLE tracking.capture_period IS
    'Frame range and direction of play per period. Teams change ends at half time, so without this every second-half x coordinate is mirrored.';
COMMENT ON TABLE tracking.frame IS
    'One instant of a capture: where the ball is and who has it. Append-only, about 135,000 rows per match.';
COMMENT ON TABLE tracking.off_ball_action IS
    'A movement by a player without the ball, detected by a model or coded by an analyst, optionally linked to the Hudl instance it led to. No upstream equivalent.';
COMMENT ON TABLE tracking.off_ball_action_zone IS
    'The pitch zones an off-ball action passed through. Associative: a run starts in one zone and ends in another.';
