-- =========================================================================
-- tracking -- reference data
--
-- Both lists are club-maintained analysis vocabulary, not vendor protocol:
-- an analyst adds a zone or an action type without a release, so they are
-- tables rather than CHECK lists.
-- =========================================================================

-- -------------------------------------------------------------------------
-- Pitch zones. Defined once, in normalised coordinates (0..100, attacking
-- towards x = 100), so a zone means the same on every pitch and in both
-- halves. Raw frame coordinates must be normalised before a zone test.
-- -------------------------------------------------------------------------
CREATE TABLE tracking.pitch_zone (
    pitch_zone_id       SMALLINT     GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    zone_code           VARCHAR(30)  NOT NULL UNIQUE,
    name                VARCHAR(80)  NOT NULL,
    x_min               NUMERIC(5,2) NOT NULL CHECK (x_min BETWEEN 0 AND 100),
    x_max               NUMERIC(5,2) NOT NULL CHECK (x_max BETWEEN 0 AND 100),
    y_min               NUMERIC(5,2) NOT NULL CHECK (y_min BETWEEN 0 AND 100),
    y_max               NUMERIC(5,2) NOT NULL CHECK (y_max BETWEEN 0 AND 100),
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT ck_pitch_zone_x_order CHECK (x_min < x_max),
    CONSTRAINT ck_pitch_zone_y_order CHECK (y_min < y_max)
);

-- Zones overlap on purpose: the box is inside the final third. That is why
-- an action's zones are a list (off_ball_action_zone), not one column.
-- Box and half-space edges are the Laws of the Game markings on a 105 x 68 m
-- pitch: box 16.5 m deep and 40.32 m wide, goal area 18.32 m wide.
INSERT INTO tracking.pitch_zone (zone_code, name, x_min, x_max, y_min, y_max)
VALUES
    ('DEFENSIVE_THIRD',  'Defensive third',  0.00,  33.33,  0.00, 100.00),
    ('MIDDLE_THIRD',     'Middle third',    33.33,  66.67,  0.00, 100.00),
    ('FINAL_THIRD',      'Final third',     66.67, 100.00,  0.00, 100.00),
    ('PENALTY_BOX',      'Penalty box',     84.29, 100.00, 20.35,  79.65),
    ('LEFT_HALF_SPACE',  'Left half-space',  0.00, 100.00, 20.35,  36.53),
    ('RIGHT_HALF_SPACE', 'Right half-space', 0.00, 100.00, 63.47,  79.65);

-- -------------------------------------------------------------------------
-- Off-ball action types. The phase says whose ball it is: a run is made in
-- possession, a press out of it.
-- -------------------------------------------------------------------------
CREATE TABLE tracking.off_ball_action_type (
    off_ball_action_type_id SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    type_code           VARCHAR(30)  NOT NULL UNIQUE,
    name                VARCHAR(80)  NOT NULL,
    phase               VARCHAR(20)  NOT NULL
        CHECK (phase IN ('in_possession', 'out_of_possession')),
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);

INSERT INTO tracking.off_ball_action_type (type_code, name, phase)
VALUES
    ('RUN_IN_BEHIND', 'Run in behind',  'in_possession'),
    ('DECOY_RUN',     'Decoy run',      'in_possession'),
    ('OVERLAP',       'Overlap',        'in_possession'),
    ('PRESS',         'Press',          'out_of_possession'),
    ('MARK',          'Mark',           'out_of_possession'),
    ('COVER',         'Cover',          'out_of_possession'),
    ('RECOVERY_RUN',  'Recovery run',   'out_of_possession');
