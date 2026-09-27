"""The stage E design rules must stay available to whoever extends the designer."""
from __future__ import annotations

from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "skills/building-design/SKILL.md"


def test_building_skill_exists_and_covers_the_design_decisions() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\nname: building-design"), "frontmatter identifies the skill"
    for topic in ("体量", "比例", "立面", "屋顶", "材质", "入口", "竖向交通", "室内", "采光"):
        assert topic in text, topic
    # The rules that the adapters actually enforce have to be stated with their
    # numbers, otherwise the skill cannot be checked against a failing export.
    for number in ("3.0 m", "0.6 m", "2.0 m", "2.4 m", "1.0 m", "0.3 m"):
        assert number in text, number
    # Capability limits stay honest: the skill must say what the target cannot do.
    assert "圆柱" in text and "自由曲面" in text and "还没有" in text
    # Sources and their access status are recorded, including the blocked ones.
    assert "2026-09-27" in text and "Cloudflare" in text
