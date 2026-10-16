"""Extract credential-free, recorded parameters for the client baseline rebuild."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from world_builder.agents.contracts import ROOT, strict_json, digest
from world_builder.agents.runtime import write_json

if __name__=='__main__':
    source=ROOT/'artifacts/nature046/live-v3'
    accepted=strict_json((source/'accepted.json').read_bytes())
    result=strict_json((source/'result.json').read_bytes())
    path=ROOT/'examples/nature047_reference.json'
    if path.exists():raise SystemExit('Reference exists; do not overwrite')
    write_json(path,{'parameters':{s:accepted['plans'][s] for s in ('B','D')},
                    'source_world_id':result['world_id'],'accepted_sha256':digest(accepted),
                    'source_worldpkg_sha256':result['worldpkg_sha256'],'source_contract':accepted['contract_version']})
    print('Recorded reference parameters prepared (no raw calls or credentials).')
