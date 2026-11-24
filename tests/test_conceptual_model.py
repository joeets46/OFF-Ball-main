"""The conceptual model's entity count is measured, not hand-typed.

Pure Python, no database. The count quoted in the docs once said 38 while the
model held 61, and nothing noticed, because no test read it. These tests count
the entities in both conceptual files and require every quoted figure to match.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CONCEPTUAL = ROOT / "models" / "conceptual"

#: A bold entity row in a subject-area table: ``| **Fixture** | ... |``.
ROW_RE = re.compile(r"^\| \*\*([^*]+)\*\* \|", re.M)
#: An entity box in a Mermaid diagram: ``    FIXTURE { string name }``.
BOX_RE = re.compile(r"^\s+([A-Z_]+) \{", re.M)

#: Every place that quotes the count, and the pattern that captures it.
QUOTED = (
    ("models/conceptual/subject-areas.md", r"The (\d+) entities below"),
    ("models/conceptual/subject-areas.md", r"draws all (\d+) entities"),
    ("models/conceptual/conceptual-erd.md", r"^(\d+) entities in five subject areas"),
    ("docs/01-conceptual-model.md", r"^(\d+) business entities"),
    ("docs/README.md", r"\| (\d+) business entities"),
    ("README.md", r"\| (\d+) business entities"),
)


def _areas_entities() -> list[str]:
    """Entity rows in the five numbered sections of subject-areas.md."""
    text = (CONCEPTUAL / "subject-areas.md").read_text(encoding="utf-8")
    sections = re.split(r"^## ", text, flags=re.M)
    return [row for s in sections if re.match(r"\d\. ", s) for row in ROW_RE.findall(s)]


def _erd_entities() -> set[str]:
    """Distinct entity boxes in conceptual-erd.md, excluding the spine summary."""
    text = (CONCEPTUAL / "conceptual-erd.md").read_text(encoding="utf-8")
    return set(BOX_RE.findall(text.split("## The spine")[0]))


def test_both_files_count_the_same_entities():
    areas = _areas_entities()
    assert len(areas) == len(set(areas)), "an entity is listed in two subject areas"
    assert len(areas) == len(_erd_entities()), (
        f"subject-areas.md lists {len(areas)} entities, "
        f"conceptual-erd.md draws {len(_erd_entities())}"
    )


@pytest.mark.parametrize("path,pattern", QUOTED)
def test_quoted_count_matches_the_model(path, pattern):
    match = re.search(pattern, (ROOT / path).read_text(encoding="utf-8"), re.M)
    assert match, f"{path}: no entity count found for {pattern!r}"
    assert int(match.group(1)) == len(_areas_entities()), (
        f"{path} says {match.group(1)} entities; the model has {len(_areas_entities())}"
    )
