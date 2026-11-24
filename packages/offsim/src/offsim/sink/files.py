"""Write a world as a tracking vendor would deliver it: files, one per capture.

``match_<id>.json`` holds the match and its squad; ``capture_<id>_<method>_v<n>.jsonl``
holds one frame per line with its positions; ``actions_<id>.json`` the
detected off-ball actions. Nothing is normalised -- the files carry the same
units, origin and direction as the capture rows say.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ..world import Recording, World


def _plain(value):
    return value.isoformat() if isinstance(value, datetime) else value


class FileSink:
    def __init__(self, out_dir: Path) -> None:
        self.out = Path(out_dir)
        self.out.mkdir(parents=True, exist_ok=True)

    def write_masters(self, world: World) -> None:
        for match in world.matches:
            body = {"match": match.row(),
                    "squad": [s.row() for s in world.squad(match)],
                    "players": [p.row() for p in world.players
                                if p.team_key in (match.home.key, match.away.key)]}
            self._json(f"match_{match.match_id}.json", body)

    def write_recording(self, recording: Recording) -> str:
        capture = recording.capture
        match_id, method, version = capture.key
        name = f"capture_{match_id}_{method}_v{version}.jsonl"
        header = {k: v for k, v in capture.row().items() if not k.startswith("_")}
        header["periods"] = [{k: v for k, v in p.items() if not k.startswith("_")}
                             for p in capture.period_rows()]
        with (self.out / name).open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps({"capture": header}, default=_plain) + "\n")
            for frame in recording.frames():
                row = {k: v for k, v in frame.row(capture).items() if not k.startswith("_")}
                row["positions"] = [list(p) for p in frame.positions]
                fh.write(json.dumps(row, default=_plain) + "\n")
        return name

    def write_actions(self, match_id: int, rows: list[dict]) -> int:
        self._json(f"actions_{match_id}.json", rows)
        return len(rows)

    def _json(self, name: str, body) -> None:
        (self.out / name).write_text(json.dumps(body, indent=1, default=_plain) + "\n",
                                     encoding="utf-8", newline="\n")
