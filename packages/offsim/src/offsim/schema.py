"""The tracking schema's columns, read from its DDL.

Not a copy of the column list: the DDL in ``models/physical/tracking/ddl/`` is
parsed each time, so a column added there and not generated here fails
``test_world`` rather than failing a load.

The parse relies on the layout every DDL file in the repository follows: a
column definition is indented four spaces and starts with a lowercase name,
while CHECK continuations and constraints are indented further or start with
a keyword.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache

from .config import tracking_ddl_dir

_CREATE = re.compile(r"CREATE\s+TABLE\s+tracking\.(\w+)\s*\(", re.IGNORECASE)
_COLUMN = re.compile(r"^ {4}([a-z_][a-z0-9_]*)\s+([A-Z]+|common\.\w+)")
_KEYWORDS = {"constraint", "primary", "unique", "check", "foreign"}

#: Columns the sink fills from ids the database assigns at load time
#: (IDENTITY keys of parent rows) or from reference tables seeded by the DDL.
#: The world cannot know them, so it supplies a link hint instead: a key
#: starting with "_", such as ``_frame_number``.
LINKED: dict[str, set[str]] = {
    "capture_period": {"capture_id"},
    "frame": {"capture_id"},
    "player_frame_position": {"frame_id"},
    "off_ball_action": {"off_ball_action_type_id", "start_frame_id", "end_frame_id"},
    "off_ball_action_zone": {"off_ball_action_id", "pitch_zone_id", "entered_frame_id"},
}


@dataclass(frozen=True)
class Column:
    name: str
    not_null: bool
    has_default: bool
    is_identity: bool


@cache
def tables() -> dict[str, tuple[Column, ...]]:
    """Every base table in the tracking DDL, with its columns in order."""
    found: dict[str, tuple[Column, ...]] = {}
    for path in sorted(tracking_ddl_dir().glob("*.sql")):
        # Comments go first: a parenthesis in prose would unbalance the body.
        sql = re.sub(r"--[^\n]*", "", path.read_text(encoding="utf-8"))
        for match in _CREATE.finditer(sql):
            body = _balanced(sql, match.end() - 1)
            cols = []
            for line in body.splitlines():
                m = _COLUMN.match(line)
                if not m or m.group(1) in _KEYWORDS:
                    continue
                upper = line.upper()
                cols.append(Column(
                    name=m.group(1),
                    not_null="NOT NULL" in upper or "PRIMARY KEY" in upper,
                    has_default="DEFAULT" in upper or "GENERATED" in upper,
                    is_identity="AS IDENTITY" in upper,
                ))
            found[match.group(1)] = tuple(cols)
    return found


def columns(table: str) -> list[str]:
    return [c.name for c in tables()[table]]


def required(table: str) -> set[str]:
    """Columns a row must supply: NOT NULL, with no default, and not linked."""
    return {
        c.name for c in tables()[table]
        if c.not_null and not c.has_default
    } - LINKED.get(table, set())


def check_row(table: str, row: dict) -> list[str]:
    """Problems with a generated row for ``table``; empty when it fits the DDL."""
    known = set(columns(table))
    given = {k for k in row if not k.startswith("_")}
    problems = [f"{table}.{k} is not a column" for k in sorted(given - known)]
    problems += [f"{table}.{k} is required but missing" for k in sorted(required(table) - given)]
    return problems


def _balanced(sql: str, open_paren: int) -> str:
    depth = 0
    for i in range(open_paren, len(sql)):
        if sql[i] == "(":
            depth += 1
        elif sql[i] == ")":
            depth -= 1
            if depth == 0:
                return sql[open_paren + 1 : i]
    return sql[open_paren:]
