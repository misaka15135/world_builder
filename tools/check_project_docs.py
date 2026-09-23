#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors: list[str] = []
    markdown_files = sorted(root.rglob("*.md"))
    local_links = 0

    for path in markdown_files:
        text = path.read_text(encoding="utf-8")
        if "喵" in text:
            errors.append(f"role text in engineering file: {path.relative_to(root)}")
        if len(re.findall(r"^```", text, re.MULTILINE)) % 2:
            errors.append(f"unbalanced code fence: {path.relative_to(root)}")
        for match in re.finditer(r"\[[^\]\n]+\]\(([^)\n]+)\)", text):
            destination = match.group(1).split("#", 1)[0]
            if not destination or "://" in destination or destination.startswith("mailto:"):
                continue
            local_links += 1
            if not (path.parent / destination).resolve().exists():
                errors.append(f"missing link from {path.relative_to(root)}: {destination}")
        for line in text.splitlines():
            if line.startswith("- [x] ") and not (line.startswith("- [x] ~~") and line.endswith("~~")):
                errors.append(f"completed item lacks strike-through: {path.relative_to(root)}: {line}")

    for path in sorted((root / "schemas").glob("*.json")) + sorted((root / "examples").glob("*.json")):
        json.loads(path.read_text(encoding="utf-8"))

    orders = sorted((root / "work_order").glob("[0-9][0-9][0-9]_*.md"))
    numbers = [int(path.name[:3]) for path in orders]
    if numbers != list(range(13)):
        errors.append(f"unexpected work order sequence: {numbers}")
    index = (root / "work_order" / "README.md").read_text(encoding="utf-8")
    for path in orders:
        text = path.read_text(encoding="utf-8")
        status_match = re.search(r"^- 状态：(\w+)", text, re.MULTILINE)
        row = next((line for line in index.splitlines() if line.startswith(f"| {path.name[:3]} |")), None)
        if status_match is None or row is None or f"| {status_match.group(1)} |" not in row:
            errors.append(f"index status mismatch: {path.name}")
        if status_match and status_match.group(1) == "done" and re.search(r"^- \[ \]", text, re.MULTILINE):
            errors.append(f"done order contains pending item: {path.name}")
        if status_match and status_match.group(1) not in {"planned", "in_progress", "blocked", "done", "cancelled"}:
            errors.append(f"invalid work order status: {path.name}")

    summary = {
        "markdown_files": len(markdown_files),
        "local_links": local_links,
        "json_files": len(list((root / "schemas").glob("*.json"))) + len(list((root / "examples").glob("*.json"))),
        "work_orders": len(orders),
        "errors": errors,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
