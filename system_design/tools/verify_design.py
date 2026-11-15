#!/usr/bin/env python3
"""Validate design artifacts; does not test the product runtime."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from jsonschema import Draft202012Validator

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--repo', type=Path, default=root.parent)
args = parser.parse_args()
errors = []
counts = {}

def load(path):
    return json.loads((root / path).read_text(encoding='utf-8'))

def graph_errors(graph, available, outputs):
    problems = []
    tasks = {task['task_id']: task for task in graph['tasks']}
    if len(tasks) != len(graph['tasks']):
        problems.append('duplicate task')
    covered = set()
    visiting, visited = set(), set()
    def visit(key):
        if key in visiting:
            problems.append('cycle')
            return
        if key in visited:
            return
        visiting.add(key)
        for dep in tasks[key]['depends_on']:
            if dep not in tasks:
                problems.append('missing dependency')
            else:
                visit(dep)
        visiting.remove(key)
        visited.add(key)
    for key, task in tasks.items():
        if task['capability'] not in available:
            problems.append('unknown capability')
        covered.update(task['covers'])
        if set(task['covers']) - set(outputs.get(task['capability'], [])):
            problems.append('capability cannot produce declared requirement')
        visit(key)
    if set(graph['required']) - covered:
        problems.append('missing required coverage')
    finals = graph.get('final_review_task_ids', [])
    if not finals:
        problems.append('missing final review')
    ancestors = set()
    def collect(key):
        if key in ancestors or key not in tasks:
            return
        ancestors.add(key)
        for dep in tasks[key]['depends_on']:
            collect(dep)
    for final in finals:
        if final not in tasks or tasks[final]['capability'] != 'scene.review':
            problems.append('invalid final review')
        else:
            collect(final)
    for required in graph['required']:
        producers = {key for key, task in tasks.items() if required in task['covers'] and required in outputs.get(task['capability'], [])}
        if not producers or not producers.issubset(ancestors):
            problems.append('producer not covered by final review')
    return problems

schema = load('contracts/action.schema.json')
Draft202012Validator.check_schema(schema)
validator = Draft202012Validator(schema)
for expected, name in [(True, 'valid'), (False, 'invalid')]:
    items = load('examples/actions.' + name + '.json')
    counts['actions_' + name] = len(items)
    for index, item in enumerate(items):
        if validator.is_valid(item) != expected:
            errors.append(f'Action {name}[{index}] unexpected result')
graphs = load('examples/scenario_graphs.json')
for expected, name in [(True, 'valid'), (False, 'invalid')]:
    counts['graphs_' + name] = len(graphs[name])
    for graph in graphs[name]:
        valid = not graph_errors(graph, set(graphs['available_capabilities']), graphs['capability_outputs'])
        if valid != expected:
            errors.append(f'Graph {graph["name"]} unexpected result')
oas = load('contracts/openapi.design.json')
assert oas['openapi'] == '3.1.1'
counts['openapi_paths'] = len(oas['paths'])
operation_ids = []
for path, methods in oas['paths'].items():
    for operation in methods.values():
        operation_ids.append(operation['operationId'])
        parameters = {p['name'] for p in operation['parameters'] if p['in'] == 'path' and p['required']}
        if parameters != set(re.findall(r'\{(.*?)\}', path)):
            errors.append('OpenAPI path parameter mismatch: ' + path)
if len(operation_ids) != len(set(operation_ids)):
    errors.append('duplicate operationId')
for name, definition in oas['components']['schemas'].items():
    Draft202012Validator.check_schema(definition)
def references(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == '$ref':
                if not value.startswith('#/'):
                    errors.append('external OpenAPI reference: ' + value)
                else:
                    target = oas
                    try:
                        for part in value[2:].split('/'):
                            target = target[part.replace('~1', '/').replace('~0', '~')]
                    except KeyError:
                        errors.append('unresolved reference: ' + value)
            else:
                references(value)
    elif isinstance(node, list):
        for value in node:
            references(value)
references(oas)
counts['markdown_files'] = 0
counts['local_links'] = 0
for path in root.rglob('*.md'):
    counts['markdown_files'] += 1
    text = path.read_text(encoding='utf-8')
    if len(re.findall(r'^```', text, re.M)) % 2:
        errors.append('unbalanced fences: ' + path.name)
    if '\u55b5' in text:
        errors.append('role text: ' + path.name)
    for link in re.findall(r'\[[^\]\n]+\]\(([^)\n]+)\)', text):
        dest = link.split('#')[0]
        if not dest or '://' in dest or dest.startswith('mailto:'):
            continue
        counts['local_links'] += 1
        target = (path.parent / dest).resolve()
        if not target.is_relative_to(root):
            relative = Path('system_design') / path.relative_to(root).parent / dest
            target = (args.repo / relative).resolve()
        if not target.exists():
            errors.append(f'broken link {path.name}: {dest}')
counts['diagrams'] = 0
for source in sorted((root / 'diagrams').glob('*.mmd')):
    counts['diagrams'] += 1
    svg = source.with_suffix('.svg')
    try:
        tree = ET.parse(svg)
        if not tree.getroot().tag.endswith('svg'):
            errors.append('not SVG: ' + svg.name)
        text = svg.read_text()
        if 'Syntax error in text' in text:
            errors.append('diagram syntax error: ' + svg.name)
    except (OSError, ET.ParseError) as exc:
        errors.append(str(exc))
manifest = load('diagrams/render-manifest.json')
for entry in manifest['diagrams']:
    for key in ['source', 'svg']:
        path = root / 'diagrams' / entry[key]
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry[key + '_sha256']:
            errors.append('render manifest mismatch: ' + entry[key])
print(json.dumps({'scope': 'design structure, examples, DAG coverage, links and SVG XML; no product/target execution', 'counts': counts, 'errors': errors}, ensure_ascii=False, indent=2))
sys.exit(bool(errors))
