#!/usr/bin/env python3
"""Offline candidate-stack compatibility probe, not a product integration test."""
import asyncio
import copy
import importlib.metadata
import json
import platform
import sqlite3
import subprocess
import sys
import tomllib
from pathlib import Path

import httpx
import mcp
from mcp_types import LATEST_PROTOCOL_VERSION
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict
from jsonschema import Draft202012Validator

root = Path(__file__).resolve().parents[1]
checks = []
versions = {name: importlib.metadata.version(name) for name in ['fastapi','uvicorn','pydantic','jsonschema','httpx','mcp','keyring','platformdirs']}
config = tomllib.loads((root/'implementation/runtime.design.toml').read_text())
validator = Draft202012Validator(json.loads((root/'implementation/runtime-config.schema.json').read_text()))
validator.check_schema(validator.schema)
validator.validate(config)
checks.append('toml_schema_positive')
for name, section, key, value in [('multiple_http_workers','server','workers',2),('redirects','transport','follow_redirects',True),('unknown_field','runtime','unlimited',True),('invalid_budget','runtime','max_model_calls',0)]:
    bad = copy.deepcopy(config)
    bad[section][key] = value
    assert not validator.is_valid(bad), name
    checks.append(name+'_rejected')
assert config['runtime']['max_output_tokens'] <= config['runtime']['max_total_tokens']
assert config['transport']['max_keepalive_connections'] <= config['transport']['max_connections']
assert config['limits']['max_blob_bytes'] <= config['limits']['max_candidate_bytes']
checks.append('configuration_cross_field_invariants')

class Probe(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid')
    count: int

app = FastAPI()
@app.post('/probe')
async def probe(value: Probe):
    return {'count': value.count}

async def asgi_probe():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://offline-probe') as client:
        good = await client.post('/probe', json={'count': 2})
        bad = await client.post('/probe', json={'count': '2'})
        extra = await client.post('/probe', json={'count': 2,'force':True})
        assert good.status_code == 200 and good.json()['count'] == 2
        assert bad.status_code == 422 and extra.status_code == 422
asyncio.run(asgi_probe())
checks.extend(['fastapi_httpx_asgi_roundtrip','pydantic_strict_and_extra_rejection'])

with sqlite3.connect(':memory:') as db:
    db.execute('CREATE VIRTUAL TABLE search_probe USING fts5(content)')
    db.execute('CREATE VIRTUAL TABLE spatial_probe USING rtree(id,min_x,max_x,min_y,max_y)')
    db.execute('CREATE TABLE strict_probe (id INTEGER PRIMARY KEY) STRICT')
    assert db.execute("SELECT json_valid('{}')").fetchone()[0] == 1
checks.append('sqlite_json_fts5_rtree_strict')
assert str(LATEST_PROTOCOL_VERSION) == '2026-07-28'
checks.append('mcp_sdk_import_and_protocol_constant')
subprocess.run([sys.executable,'-m','pip','check'],check=True,capture_output=True,text=True)
checks.append('pip_dependency_consistency')
sql = json.loads(subprocess.check_output([sys.executable,str(root/'tools/verify_repository_design.py')],text=True))
assert not sql['errors']
result={'checked_at':'2026-11-12','scope':'isolated candidate dependency imports, ASGI DTOs, configuration and in-memory SQL; no product/model/MCP server/target execution','python':platform.python_version(),'platform':platform.platform(),'sqlite':sqlite3.sqlite_version,'versions':versions,'checks':checks,'sql_design':sql,'errors':[]}
print(json.dumps(result,ensure_ascii=False,indent=2))
