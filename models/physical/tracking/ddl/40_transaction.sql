-- =========================================================================
-- tracking -- captures, frames, positions and off-ball actions
--
-- Volume, per match and per capture: ~135,000 frames (25 a second over
-- 90 minutes) and ~3,000,000 player positions (22 players per frame). Only
-- the positions are partitioned; frames stay a plain table so positions can
-- reference them on frame_id alone.
-- =========================================================================

-- -------------------------------------------------------------------------
-- Capture. One delivered recording of one match. A match can be captured
-- twice (optical cameras and GPS vests) and re-delivered after the vendor
-- corrects player identity, so a capture is versioned.
-- -------------------------------------------------------------------------
CREATE TABLE tracking.capture (
    capture_id          BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    match_id            BIGINT       NOT NULL,
    capture_method      VARCHAR(10)  NOT NULL
        CHECK (capture_method IN ('optical', 'gps', 'hybrid')),
    delivery_version    SMALLINT     NOT NULL DEFAULT 1 CHECK (delivery_version > 0),
    is_current          BOOLEAN      NOT NULL DEFAULT TRUE,
    is_primary          BOOLEAN      NOT NULL DEFAULT TRUE,
    frames_per_second   SMALLINT     NOT NULL CHECK (frames_per_second BETWEEN 1 AND 100),
    -- The vendor's coordinate system, kept as delivered. Normalising to the
    -- 0..100 pitch used by pitch_zone needs all three, plus the pitch size on
    -- match and the direction of play on capture_period.
    coordinate_unit     VARCHAR(2)   NOT NULL DEFAULT 'm'
        CHECK (coordinate_unit IN ('m', 'cm')),
    coordinate_origin   VARCHAR(12)  NOT NULL DEFAULT 'centre'
        CHECK (coordinate_origin IN ('centre', 'bottom_left')),
    delivered_at        TIMESTAMPTZ  NOT NULL,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT ux_capture_version UNIQUE (match_id, capture_method, delivery_version)
);

COMMENT ON COLUMN tracking.capture.delivered_at IS
    'When the file arrived. The extraction watermark: frames carry no '
    'updated_at, and a whole capture is read when it is delivered.';
COMMENT ON COLUMN tracking.capture.is_current IS
    'False once a later delivery_version supersedes this one. Old frames are '
    'kept, so an extract that ignores this flag loads every match twice.';

-- -------------------------------------------------------------------------
-- Capture period. Teams change ends at half time, so the direction of play
-- is a fact about a period, not a match. Without it, every second-half x
-- coordinate is mirrored.
-- -------------------------------------------------------------------------
CREATE TABLE tracking.capture_period (
    capture_id          BIGINT       NOT NULL,
    -- 1 and 2 are the halves, 3 and 4 extra time, 5 the penalty shoot-out.
    period              SMALLINT     NOT NULL CHECK (period BETWEEN 1 AND 5),
    start_frame_number  INTEGER      NOT NULL CHECK (start_frame_number >= 0),
    end_frame_number    INTEGER      NOT NULL,
    home_attacks_positive_x BOOLEAN  NOT NULL,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

    PRIMARY KEY (capture_id, period),
    CONSTRAINT ck_capture_period_frame_order CHECK (start_frame_number <= end_frame_number)
);

-- -------------------------------------------------------------------------
-- Frame. One instant: where the ball is and who has it. Append-only.
-- -------------------------------------------------------------------------
CREATE TABLE tracking.frame (
    frame_id            BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    capture_id          BIGINT       NOT NULL,
    frame_number        INTEGER      NOT NULL CHECK (frame_number >= 0),
    period              SMALLINT     NOT NULL CHECK (period BETWEEN 1 AND 5),
    captured_at         TIMESTAMPTZ  NOT NULL,
    -- Milliseconds since the period kicked off. Restarts at 0 each period,
    -- so 45:00 of the second half is 2,700,000, not 5,400,000.
    period_clock_ms     INTEGER      NOT NULL CHECK (period_clock_ms >= 0),
    -- Ball position in the capture's own units and origin. Null when the
    -- cameras lose the ball, which is common in a crowded box.
    ball_x              NUMERIC(7,2),
    ball_y              NUMERIC(7,2),
    ball_z              NUMERIC(6,2) CHECK (ball_z IS NULL OR ball_z >= 0),
    ball_status         VARCHAR(5)   NOT NULL CHECK (ball_status IN ('alive', 'dead')),
    possession_side     CHAR(1)      CHECK (possession_side IS NULL OR possession_side IN ('H', 'A')),
    ball_carrier_player_id BIGINT,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT ux_frame_capture_number UNIQUE (capture_id, frame_number),
    CONSTRAINT ck_frame_ball_xy_pair CHECK ((ball_x IS NULL) = (ball_y IS NULL)),
    CONSTRAINT ck_frame_carrier_has_side
        CHECK (ball_carrier_player_id IS NULL OR possession_side IS NOT NULL)
);

COMMENT ON COLUMN tracking.frame.ball_carrier_player_id IS
    'Null when the ball is loose. Every other player in the frame is, by '
    'definition, off the ball -- this column is what off-ball means.';

-- -------------------------------------------------------------------------
-- Player frame position. Where one player is in one frame. The volume of
-- the whole schema lives here, so it is range-partitioned monthly on
-- captured_at, like tm_axs.scan, and append-only.
--
-- captured_at is copied from the frame because PostgreSQL requires the
-- partition key in the primary key. It must equal the frame's captured_at;
-- no CHECK can see across tables, so the loader is trusted with that.
-- -------------------------------------------------------------------------
CREATE TABLE tracking.player_frame_position (
    frame_id            BIGINT       NOT NULL,
    player_id           BIGINT       NOT NULL,
    captured_at         TIMESTAMPTZ  NOT NULL,
    -- Capture units and origin, as for the ball.
    x                   NUMERIC(7,2) NOT NULL,
    y                   NUMERIC(7,2) NOT NULL,
    -- 0-15 m/s: the fastest recorded footballers reach about 10.
    speed_mps           NUMERIC(4,2) CHECK (speed_mps IS NULL OR speed_mps BETWEEN 0 AND 15),
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

    PRIMARY KEY (frame_id, player_id, captured_at)
) PARTITION BY RANGE (captured_at);

COMMENT ON TABLE tracking.player_frame_position IS
    'Where every player is, 25 times a second. About three million rows per '
    'match. Monthly range partitions: queried per match, and retention is a DETACH.';

-- A year of partitions plus a catch-all. In production these are created by a
-- maintenance job; here they are explicit so the DDL loads standalone.
CREATE TABLE tracking.player_frame_position_2026_01 PARTITION OF tracking.player_frame_position
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
CREATE TABLE tracking.player_frame_position_2026_02 PARTITION OF tracking.player_frame_position
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
CREATE TABLE tracking.player_frame_position_2026_03 PARTITION OF tracking.player_frame_position
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
CREATE TABLE tracking.player_frame_position_2026_04 PARTITION OF tracking.player_frame_position
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE tracking.player_frame_position_2026_05 PARTITION OF tracking.player_frame_position
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE tracking.player_frame_position_2026_06 PARTITION OF tracking.player_frame_position
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE tracking.player_frame_position_2026_07 PARTITION OF tracking.player_frame_position
    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
CREATE TABLE tracking.player_frame_position_2026_08 PARTITION OF tracking.player_frame_position
    FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');
CREATE TABLE tracking.player_frame_position_2026_09 PARTITION OF tracking.player_frame_position
    FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');
CREATE TABLE tracking.player_frame_position_2026_10 PARTITION OF tracking.player_frame_position
    FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');
CREATE TABLE tracking.player_frame_position_2026_11 PARTITION OF tracking.player_frame_position
    FOR VALUES FROM ('2026-11-01') TO ('2026-12-01');
CREATE TABLE tracking.player_frame_position_2026_12 PARTITION OF tracking.player_frame_position
    FOR VALUES FROM ('2026-12-01') TO ('2027-01-01');
CREATE TABLE tracking.player_frame_position_default PARTITION OF tracking.player_frame_position DEFAULT;

COMMENT ON TABLE tracking.player_frame_position_default IS
    'Catch-all. Rows landing here mean the partition maintenance job has fallen '
    'behind; it should be monitored and stay empty.';

-- -------------------------------------------------------------------------
-- Off-ball action. A movement by a player without the ball, detected by a
-- model or coded by an analyst. Re-running the detection model replaces the
-- model's actions for a match, so these rows really are deleted.
-- -------------------------------------------------------------------------
CREATE TABLE tracking.off_ball_action (
    off_ball_action_id  BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    match_id            BIGINT       NOT NULL,
    player_id           BIGINT       NOT NULL,
    off_ball_action_type_id SMALLINT NOT NULL,
    -- Null when an analyst coded the action from video with no capture behind it.
    start_frame_id      BIGINT,
    end_frame_id        BIGINT,
    -- Business key into the hudl.instance this action led to: the run that
    -- created the shot. No foreign key: a different database.
    led_to_hudl_instance_id UUID,
    detection_method    VARCHAR(10)  NOT NULL CHECK (detection_method IN ('model', 'analyst')),
    detection_model_version VARCHAR(40),
    detection_confidence NUMERIC(4,3)
        CHECK (detection_confidence IS NULL OR detection_confidence BETWEEN 0 AND 1),
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT ck_off_ball_action_frame_pair
        CHECK ((start_frame_id IS NULL) = (end_frame_id IS NULL)),
    -- A model reports its version and a confidence; an analyst does neither.
    CONSTRAINT ck_off_ball_action_model_has_version
        CHECK ((detection_method = 'model') = (detection_model_version IS NOT NULL)),
    CONSTRAINT ck_off_ball_action_model_has_confidence
        CHECK ((detection_method = 'model') = (detection_confidence IS NOT NULL))
);

-- -------------------------------------------------------------------------
-- Off-ball action zone. Which zones an action passed through. A run in
-- behind starts in one zone and ends in another, so one column cannot say
-- where it went.
-- -------------------------------------------------------------------------
CREATE TABLE tracking.off_ball_action_zone (
    off_ball_action_id  BIGINT       NOT NULL,
    pitch_zone_id       SMALLINT     NOT NULL,
    entered_frame_id    BIGINT,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

    PRIMARY KEY (off_ball_action_id, pitch_zone_id)
);
