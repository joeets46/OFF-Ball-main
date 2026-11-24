"""Identifiers: the vendor's own keys and the business keys into other systems.

``tracking.match.match_id`` and ``tracking.player.player_id`` are
vendor-assigned, not IDENTITY, so the generator mints them here. The business
keys -- a Hudl game or player UUID, a SuccessFactors person id, a TM/AXS
event code -- are what ``common.entity_xref`` would later resolve, so they
must be stable for the same seed.
"""

from __future__ import annotations

from .rng import uuid_for

MATCH_ID_BASE = 700_000
PLAYER_ID_BASE = 4_100_000


class Registry:
    def __init__(self, seed: int) -> None:
        self.seed = seed

    def match_id(self, index: int) -> int:
        return MATCH_ID_BASE + index + 1

    def player_id(self, team_key: int, squad_index: int) -> int:
        return PLAYER_ID_BASE + team_key * 100 + squad_index + 1

    def hudl_game_id(self, match_id: int) -> str:
        return str(uuid_for(self.seed, "hudl_game", match_id))

    def hudl_player_id(self, player_id: int) -> str:
        return str(uuid_for(self.seed, "hudl_player", player_id))

    def hudl_instance_id(self, match_id: int, sequence: int) -> str:
        return str(uuid_for(self.seed, "hudl_instance", match_id, sequence))

    def sfsf_person_id(self, player_id: int) -> str:
        return f"SFP{player_id:09d}"

    def tm_axs_event_code(self, match_id: int) -> str:
        # Must satisfy common.dom_fixture_code: ^[A-Z0-9_-]{3,30}$.
        return f"OFS-{match_id}"
