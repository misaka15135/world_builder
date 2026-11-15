#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

STATUSES = {'planned', 'in_progress', 'blocked', 'done', 'cancelled'}


def check_work_orders(root: Path) -> list[str]:
    """Validate the active plan and immutable historical inventory separately."""
    errors: list[str] = []
    work = root / 'work_order'
    try:
        registry = json.loads((work / 'registry.json').read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        return [f'cannot read work order registry: {exc}']
    if registry.get('version') != 1:
        return ['unsupported work order registry version']
    active = registry['active']
    archived = registry['archived']
    backlog = registry['backlog']
    ids = active + [entry['id'] for entry in archived]
    if len(ids) != len(set(ids)):
        errors.append('duplicate work order ID')
    if any(not re.fullmatch(r'\d{3}', x) for x in ids):
        errors.append('invalid work order ID')
    elif sorted(map(int, ids)) != list(range(len(ids))):
        errors.append('non-contiguous active/archive work order inventory')
    paths = list(work.glob('[0-9][0-9][0-9]_*.md'))
    if sorted(p.name[:3] for p in paths) != sorted(active):
        errors.append('active files differ from registry')
    index = (work / 'README.md').read_text(encoding='utf-8')
    backlog_text = (work / 'BACKLOG.md').read_text(encoding='utf-8')
    if set(re.findall(r'^## (B\d+)\b', backlog_text, re.M)) != set(backlog):
        errors.append('backlog IDs differ from registry')
    deps: dict[str, list[str]] = {}
    for path in paths:
        text = path.read_text(encoding='utf-8')
        status = re.search(r'^- 状态：(\w+)', text, re.M)
        if not status or status.group(1) not in STATUSES:
            errors.append(f'invalid status: {path.name}')
        if status and status.group(1) == 'done' and re.search(r'^- \[ \]', text, re.M):
            errors.append(f'done order contains pending item: {path.name}')
        if path.name not in index:
            errors.append(f'active order missing from index: {path.name}')
        dependency = re.search(r'^- 依赖：(.*)$', text, re.M)
        if not dependency:
            errors.append(f'missing dependency declaration: {path.name}')
        refs = re.findall(r'\b\d{3}\b', dependency.group(1)) if dependency else []
        deps[path.name[:3]] = refs
        for ref in refs:
            if ref not in active:
                errors.append(f'inactive/unknown dependency: {path.name} -> {ref}')
    visited: set[str] = set()
    def visit(node: str, stack: set[str]) -> None:
        if node in stack:
            errors.append(f'active dependency cycle at {node}')
            return
        if node in visited:
            return
        for ref in deps.get(node, []):
            visit(ref, stack | {node})
        visited.add(node)
    for node in deps:
        visit(node, set())
    known_targets = set(active) | set(backlog)
    for entry in archived:
        path = root / entry['path']
        if not path.is_file():
            errors.append(f'missing archived order: {entry["id"]}')
            continue
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry['archive_sha256']:
            errors.append(f'archive hash mismatch: {entry["id"]}')
        text = raw.decode('utf-8')
        status = re.search(r'^- 状态：(\w+)', text, re.M)
        if not status or status.group(1) != entry['status_at_archive']:
            errors.append(f'archive status changed: {entry["id"]}')
        if entry['disposition'] not in {'evidence', 'transferred'}:
            errors.append(f'invalid archive disposition: {entry["id"]}')
        if entry['disposition'] == 'transferred' and not entry['successors']:
            errors.append(f'unmapped archived work: {entry["id"]}')
        for ref in entry['successors']:
            if ref not in known_targets:
                errors.append(f'unknown successor: {entry["id"]} -> {ref}')
    for snapshot in registry['snapshots']:
        path = root / snapshot['path']
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != snapshot['sha256']:
            errors.append(f'archive snapshot changed: {snapshot["path"]}')
    expected = {entry['path'] for entry in archived} | {s['path'] for s in registry['snapshots']}
    actual = {p.relative_to(root).as_posix() for p in (work / 'archive' / 'legacy').glob('*.md')}
    if expected != actual:
        errors.append('archive files differ from registry')
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors: list[str] = []
    excluded = [root / 'adapters/unity/sample_project/Library',
                *(root / name for name in ('.venv', '.venv-desktop', 'dist', 'build'))]
    markdown_files = sorted(path for path in root.rglob('*.md')
                            if not any(path.is_relative_to(directory) for directory in excluded))
    local_links = 0
    for path in markdown_files:
        text = path.read_text(encoding='utf-8')
        if '喵' in text:
            errors.append(f'role text in engineering file: {path.relative_to(root).as_posix()}')
        if len(re.findall(r'^```', text, re.M)) % 2:
            errors.append(f'unbalanced code fence: {path.relative_to(root).as_posix()}')
        for match in re.finditer(r'\[[^\]\n]+\]\(([^)\n]+)\)', text):
            destination = match.group(1).split('#', 1)[0]
            if not destination or '://' in destination or destination.startswith('mailto:'):
                continue
            local_links += 1
            if not (path.parent / destination).resolve().exists():
                errors.append(f'missing link from {path.relative_to(root).as_posix()}: {destination}')
        for line in text.splitlines():
            if line.startswith('- [x] ') and not (line.startswith('- [x] ~~') and line.endswith('~~')):
                errors.append(f'completed item lacks strike-through: {path.relative_to(root).as_posix()}: {line}')
    json_files = sorted((root / 'schemas').glob('*.json')) + sorted((root / 'examples').glob('*.json'))
    for path in json_files:
        json.loads(path.read_text(encoding='utf-8'))
    errors.extend(check_work_orders(root))
    registry = json.loads((root / 'work_order/registry.json').read_text(encoding='utf-8'))
    print(json.dumps({'markdown_files':len(markdown_files), 'local_links':local_links,
                     'json_files':len(json_files) + 1, 'active_orders':len(registry['active']),
                     'archived_orders':len(registry['archived']), 'errors':errors}, ensure_ascii=False, indent=2))
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
