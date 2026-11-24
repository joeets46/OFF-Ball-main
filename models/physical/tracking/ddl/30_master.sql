-- =========================================================================
-- tracking -- matches, players and who wore which shirt
--
-- Keys are vendor-assigned BIGINTs, not IDENTITY: the vendor mints them and
-- the replica receives them, as with Shopify. Every reference to another
-- system is a business key with no REFERENCES clause, resolved through
-- common.entity_xref.
-- =========================================================================

-- -------------------------------------------------------------------------
-- Match. The vendor's record of a fixture, and the only place the pitch
-- size lives: it varies by venue, and every metre-to-normalised conversion
-- depends on it.
-- -------------------------------------------------------------------------
CREATE TABLE tracking.match (
    match_id            BIGINT       PRIMARY KEY,
    -- Business keys into the same fixture in other databases.
    hudl_game_id        UUID,
    tm_axs_event_code   common.dom_fixture_code,
    kickoff_at          TIMESTAMPTZ  NOT NULL,
    home_team_name      VARCHAR(160) NOT NULL,
    away_team_name      VARCHAR(160) NOT NULL,
    -- Laws of the Game, Law 1: length 90-120 m, width 45-90 m.
    pitch_length_m      NUMERIC(5,2) NOT NULL CHECK (pitch_length_m BETWEEN 90 AND 120),
    pitch_width_m       NUMERIC(5,2) NOT NULL CHECK (pitch_width_m BETWEEN 45 AND 90),
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT ck_match_length_exceeds_width CHECK (pitch_length_m > pitch_width_m)
);

COMMENT ON COLUMN tracking.match.match_id IS
    'Vendor-assigned. Not IDENTITY: the replica receives ids it did not mint.';
COMMENT ON COLUMN tracking.match.hudl_game_id IS
    'Business key into hudl.game, which knows the score. No foreign key: a '
    'different database. Resolved through common.entity_xref as a fixture.';

-- -------------------------------------------------------------------------
-- Player. The person as the tracking vendor knows them: a third record of
-- the same athlete, after sap_sfsf.per_person and hudl.player.
-- -------------------------------------------------------------------------
CREATE TABLE tracking.player (
    player_id           BIGINT       PRIMARY KEY,
    display_name        VARCHAR(160) NOT NULL,
    -- Business keys into the same athlete in other databases.
    hudl_player_id      UUID,
    sfsf_person_id_external VARCHAR(40),
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);

COMMENT ON COLUMN tracking.player.sfsf_person_id_external IS
    'Business key into sap_sfsf.per_person, the identity record. No foreign '
    'key: a different database. Resolved through common.entity_xref as an athlete.';

-- -------------------------------------------------------------------------
-- Match squad. A raw feed identifies a player as a side and a shirt number.
-- This is what makes "home 9" a person, for one match only: shirt numbers
-- are reissued between seasons and sometimes between matches.
-- -------------------------------------------------------------------------
CREATE TABLE tracking.match_squad (
    match_id            BIGINT       NOT NULL,
    player_id           BIGINT       NOT NULL,
    team_side           CHAR(1)      NOT NULL CHECK (team_side IN ('H', 'A')),
    shirt_number        SMALLINT     NOT NULL CHECK (shirt_number BETWEEN 1 AND 99),
    is_starter          BOOLEAN      NOT NULL,
    is_goalkeeper       BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

    PRIMARY KEY (match_id, player_id),
    CONSTRAINT ux_match_squad_shirt UNIQUE (match_id, team_side, shirt_number)
);
