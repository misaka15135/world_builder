"""Check that the stage E skill's routed research remains usable."""
from __future__ import annotations

import re
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "skills/building-design/SKILL.md"


def test_building_skill_references_are_discoverable_and_resolve() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\nname: building-design\n")
    references = re.findall(r"\]\((references/[^)]+\.md)\)", text)
    assert len(references) >= 3
    for reference in references:
        path = SKILL.parent / reference
        assert path.is_file(), reference
        content = path.read_text(encoding="utf-8")
        assert "https://" in content, reference
        for local_link in re.findall(r"\]\(([^:)]+\.md)\)", content):
            assert (path.parent / local_link).is_file(), (reference, local_link)
