#!/usr/bin/env python3
"""Render editable Mermaid sources using a separately installed pinned CLI."""
import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--mmdc', default='mmdc')
parser.add_argument('--chrome', required=True, help='Absolute path to a locally installed Chromium/Chrome executable')
args = parser.parse_args()
manifest = {'cli_version': '11.12.0', 'design_version': 'design-2026-11-11', 'diagrams': []}
with tempfile.TemporaryDirectory(prefix='wb-diagrams-') as folder:
    config = Path(folder) / 'puppeteer.json'
    config.write_text(json.dumps({'executablePath': str(Path(args.chrome).resolve())}))
    for source in sorted((root / 'diagrams').glob('*.mmd')):
        output = source.with_suffix('.svg')
        subprocess.run([args.mmdc, '-i', str(source), '-o', str(output), '-c', str(root / 'diagrams/mermaid-config.json'), '-p', str(config), '-b', 'white'], check=True)
        manifest['diagrams'].append({'source': source.name, 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'svg': output.name, 'svg_sha256': hashlib.sha256(output.read_bytes()).hexdigest()})
(root / 'diagrams/render-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
